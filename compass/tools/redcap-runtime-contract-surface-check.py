#!/usr/bin/env python3
# 用途：发布安全治理脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "references/runtime-public-contract-policy.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-runtime-contract-surface-check] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"{label} missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid {label} json: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be a JSON object")
    return payload


def require_text(payload: dict[str, Any], key: str, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{label} missing non-empty {key}")
    return value.strip()


def require_list(payload: dict[str, Any], key: str, label: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        fail(f"{label}.{key} must be a non-empty list")
    return value


def run_output(args: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        sys.stdout.write(completed.stdout)
        fail(f"command failed: {' '.join(args)}")
    return completed.stdout


def generated_candidates(root: Path) -> list[str]:
    with tempfile.NamedTemporaryFile("r", encoding="utf-8", delete=False, prefix="redcap-contract-candidates-", suffix=".txt") as handle:
        path = Path(handle.name)
    try:
        run_output(
            ["bash", str(root / "compass/tools/redcap-runtime-package-manifest.sh"), "--output", str(path)],
            root,
        )
        candidates = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    finally:
        try:
            path.unlink()
        except OSError:
            pass
    if not candidates:
        fail("runtime package manifest generated no candidates")
    return candidates


def matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def classify_candidates(policy: dict[str, Any], candidates: list[str]) -> Counter[str]:
    classes = require_list(policy, "package_candidate_classes", "runtime contract policy")
    counter: Counter[str] = Counter()
    unknown: list[str] = []
    public_api_internal: list[str] = []
    forbidden = [str(item) for item in require_list(policy, "forbidden_candidate_globs", "runtime contract policy")]

    for candidate in candidates:
        if matches(candidate, forbidden):
            fail(f"forbidden package candidate escaped into package surface: {candidate}")
        matched: dict[str, Any] | None = None
        for item in classes:
            if not isinstance(item, dict):
                fail("package_candidate_classes entries must be objects")
            class_id = require_text(item, "id", "package class")
            patterns = [str(pattern) for pattern in require_list(item, "patterns", class_id)]
            if matches(candidate, patterns):
                matched = item
                counter[class_id] += 1
                break
        if matched is None:
            unknown.append(candidate)
            continue
        if matched.get("public_api") is True and (
            candidate.startswith("compass/tools/")
            or candidate.startswith("prism/tools/")
            or candidate.startswith("references/")
        ):
            public_api_internal.append(candidate)

    if unknown:
        fail("unclassified package candidates: " + ", ".join(unknown[:20]))
    if public_api_internal:
        fail("internal support files cannot be classified as public API: " + ", ".join(public_api_internal[:20]))
    required_classes = {
        "public-cli-runtime-contract",
        "host-adapter-contract",
        "runtime-support-not-public-api",
        "prism-support-not-public-api",
        "contract-policy-metadata",
    }
    missing = sorted(item for item in required_classes if counter[item] <= 0)
    if missing:
        fail("package surface missing required contract classes: " + ", ".join(missing))
    return counter


def command_group(policy: dict[str, Any], group_id: str) -> dict[str, Any]:
    for group in require_list(policy, "command_groups", "runtime contract policy"):
        if isinstance(group, dict) and group.get("id") == group_id:
            return group
    fail(f"missing command group: {group_id}")


def validate_help_surface(root: Path, policy: dict[str, Any]) -> None:
    help_text = run_output([str(root / "bin/redcap"), "help"], root)
    for group_id in ("end_user_runtime", "maintainer_release_readiness", "maintainer_source_governance"):
        group = command_group(policy, group_id)
        heading = require_text(group, "heading", group_id)
        if heading not in help_text:
            fail(f"redcap help missing command heading: {heading}")
        for command in require_list(group, "commands", group_id):
            command_text = str(command)
            if command_text not in help_text:
                fail(f"redcap help missing command: {command_text}")
    if "不是普通用户日常 workflow" not in help_text and "不是普通用户日常流程" not in help_text:
        fail("redcap help must explain maintainer commands are not normal end-user workflow")


def validate_policy_links(root: Path, policy: dict[str, Any]) -> None:
    expected = "references/runtime-public-contract-policy.json"
    runtime = load_json(root / "references/runtime-package-readiness-policy.json", "runtime package readiness policy")
    public = load_json(root / "references/public-package-surface-policy.json", "public package surface policy")
    safety = load_json(root / "references/package-publish-safety-policy.json", "package publish safety policy")
    for label, payload in (
        ("runtime package readiness policy", runtime),
        ("public package surface policy", public),
        ("package publish safety policy", safety),
    ):
        if payload.get("contract_boundary_policy") != expected:
            fail(f"{label} must link contract_boundary_policy={expected}")
    if runtime.get("contract_profile") != "alpha-readiness-split-contract":
        fail("runtime package readiness policy must declare contract_profile=alpha-readiness-split-contract")
    if public.get("contract_profile") != runtime.get("contract_profile"):
        fail("public package surface contract_profile must match runtime package readiness policy")
    if safety.get("contract_profile") != runtime.get("contract_profile"):
        fail("publish safety contract_profile must match runtime package readiness policy")
    for rel in require_list(policy, "required_policy_links", "runtime contract policy"):
        if not (root / str(rel)).exists():
            fail(f"runtime contract required link missing: {rel}")


def validate_import_map(root: Path, policy: dict[str, Any]) -> None:
    import_map = load_json(root / "runtime/redcap-core/import-map.json", "runtime import map")
    public_entries = import_map.get("public_runtime_entrypoints")
    maintainer_entries = import_map.get("maintainer_release_entrypoints")
    source_entries = import_map.get("source_maintenance_entrypoints")
    if not isinstance(public_entries, list) or not public_entries:
        fail("import map must define public_runtime_entrypoints")
    if not isinstance(maintainer_entries, list) or not maintainer_entries:
        fail("import map must define maintainer_release_entrypoints")
    if not isinstance(source_entries, list) or not source_entries:
        fail("import map must define source_maintenance_entrypoints")

    public_commands = " ".join(str(entry.get("command", "")) for entry in public_entries if isinstance(entry, dict))
    maintainer_commands = " ".join(str(entry.get("command", "")) for entry in maintainer_entries if isinstance(entry, dict))
    source_commands = " ".join(str(entry.get("command", "")) for entry in source_entries if isinstance(entry, dict))

    for command in require_list(command_group(policy, "end_user_runtime"), "commands", "end_user_runtime"):
        if str(command) not in public_commands:
            fail(f"end-user runtime command missing from public_runtime_entrypoints: {command}")
    for command in require_list(command_group(policy, "maintainer_release_readiness"), "commands", "maintainer_release_readiness"):
        if str(command) in public_commands:
            fail(f"maintainer command appears in public runtime entrypoints: {command}")
        if str(command) not in maintainer_commands:
            fail(f"maintainer command missing from maintainer_release_entrypoints: {command}")
    for command in require_list(command_group(policy, "maintainer_source_governance"), "commands", "maintainer_source_governance"):
        if str(command) in public_commands:
            fail(f"source-governance command appears in public runtime entrypoints: {command}")
        if str(command) not in source_commands:
            fail(f"source-governance command missing from source_maintenance_entrypoints: {command}")


def validate_docs(root: Path) -> None:
    readme = (root / "README.md").read_text(encoding="utf-8")
    handoff = (root / "references/public-release-handoff.md").read_text(encoding="utf-8")
    runtime_readme = (root / "runtime/redcap-core/README.md").read_text(encoding="utf-8")
    required_pairs = [
        (readme, "普通用户"),
        (readme, "维护/发布准备"),
        (handoff, "普通用户"),
        (handoff, "维护者"),
        (runtime_readme, "public runtime"),
        (runtime_readme, "maintainer"),
    ]
    for text, phrase in required_pairs:
        if phrase.lower() not in text.lower():
            fail(f"contract documentation missing phrase: {phrase}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap public runtime contract versus maintainer-only package support boundary.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = root / policy_path
    policy = load_json(policy_path, "runtime public contract policy")
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "redcap-runtime-public-contract":
        fail("policy_id must be redcap-runtime-public-contract")
    if policy.get("status") != "alpha-readiness-split-contract":
        fail("status must be alpha-readiness-split-contract")

    validate_policy_links(root, policy)
    validate_help_surface(root, policy)
    validate_import_map(root, policy)
    validate_docs(root)
    candidates = generated_candidates(root)
    class_counts = classify_candidates(policy, candidates)

    result = {
        "status": "ok",
        "contract_profile": "alpha-readiness-split-contract",
        "candidate_count": len(candidates),
        "class_counts": dict(sorted(class_counts.items())),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("RUNTIME_CONTRACT_SURFACE_OK")
        print(f"contract_profile={result['contract_profile']}")
        print(f"candidate_count={result['candidate_count']}")
        for key, value in result["class_counts"].items():
            print(f"class.{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

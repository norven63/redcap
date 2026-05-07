#!/usr/bin/env python3
# 用途：发布安全治理脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "references/pre-release-product-architecture-policy.json"
DEFAULT_REVIEW = ROOT / "references/pre-release-product-architecture-review.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-pre-release-product-architecture-check] {message}")


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
        fail(f"{label}: missing non-empty {key}")
    return value.strip()


def require_list(payload: dict[str, Any], key: str, label: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        fail(f"{label}: {key} must be a non-empty list")
    return value


def run_output(args: list[str], cwd: Path = ROOT) -> str:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        fail(f"command failed ({' '.join(args)}): {completed.stdout.strip()}")
    return completed.stdout


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "pre-release-product-architecture":
        fail("policy_id must be pre-release-product-architecture")
    if "npm publish" not in require_text(policy, "scope", "policy"):
        fail("policy scope must explicitly forbid npm publish in this tranche")
    dimensions = require_list(policy, "required_dimensions", "policy")
    dimension_ids = set()
    for index, item in enumerate(dimensions, start=1):
        if not isinstance(item, dict):
            fail(f"policy.required_dimensions[{index}] must be an object")
        dimension_id = require_text(item, "id", f"dimension[{index}]")
        require_text(item, "question", f"dimension[{index}]")
        if item.get("release_blocker_if_failed") is not True:
            fail(f"dimension must be release-blocking if failed: {dimension_id}")
        dimension_ids.add(dimension_id)
    for required in {
        "privacy-safety",
        "machine-independence",
        "cli-product-quality",
        "source-visibility-model",
        "knowledge-boundary",
        "agent-container-contract",
        "distribution-compliance",
    }:
        if required not in dimension_ids:
            fail(f"policy missing required dimension: {required}")
    for key in (
        "allowed_review_statuses",
        "allowed_finding_severities",
        "minimum_required_checks",
        "required_release_blockers_when_observed",
        "manual_release_boundary",
    ):
        require_list(policy, key, "policy")


def npm_pack_file_count(root: Path, facts: dict[str, Any]) -> int:
    if shutil.which("npm") is None:
        if facts.get("npm_pack_dry_run_checked") is not True:
            fail("npm is unavailable and review does not record npm_pack_dry_run_checked=true")
        recorded = facts.get("package_candidate_count")
        if not isinstance(recorded, int) or recorded <= 0:
            fail("npm is unavailable and review package_candidate_count is not a positive integer")
        return recorded
    output = run_output(["npm", "pack", "--dry-run", "--json"], cwd=root)
    try:
        payload = json.loads(output)
        files = payload[0]["files"]
    except Exception as exc:
        fail(f"unable to parse npm pack --dry-run output: {exc}")
    if not isinstance(files, list) or not files:
        fail("npm pack --dry-run returned no files")
    return len(files)


def resolve_arsenal_worktree(review: dict[str, Any], root: Path) -> Path | None:
    facts = review.get("observed_facts")
    if not isinstance(facts, dict):
        fail("review observed_facts must be an object")
    raw = facts.get("redcap_arsenal_local_worktree_ref")
    if not isinstance(raw, str) or not raw.strip():
        fail("review observed_facts missing redcap_arsenal_local_worktree_ref")
    raw = raw.strip()
    if raw == "shared-knowledge-remote-binding.preferred_local_worktree":
        binding = load_json(root / "references/shared-knowledge-remote-binding.json", "shared knowledge remote binding")
        value = binding.get("preferred_local_worktree")
        if not isinstance(value, str) or not value.strip():
            return None
        path = Path(value.strip()).expanduser()
        if not path.is_absolute():
            path = (root / path).resolve()
        return path
    if raw.startswith("/") or raw.startswith("~"):
        fail("redcap_arsenal_local_worktree_ref must not embed absolute local user paths")
    return (root / raw).resolve()


def arsenal_substantive_entries(review: dict[str, Any], root: Path) -> int:
    worktree = resolve_arsenal_worktree(review, root)
    if worktree is None or not worktree.is_dir():
        return 0
    count = 0
    ignored_names = {".gitkeep", "README.md", ".gitignore", "entry.schema.json"}
    for path in worktree.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(worktree).as_posix()
        if rel.startswith(".git/"):
            continue
        if path.name in ignored_names:
            continue
        count += 1
    return count


def bin_command_surface(root: Path) -> dict[str, bool]:
    text = (root / "bin/redcap").read_text(encoding="utf-8")
    command_labels: set[str] = set()
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped.endswith(")"):
            continue
        for label in stripped[:-1].strip().split("|"):
            label = label.strip()
            if label and " " not in label and not label.startswith("-"):
                command_labels.add(label)
    required_core = {"revive", "status", "diagnose", "closeout"}
    if not required_core.issubset(command_labels):
        fail(f"unable to parse required CLI command labels from bin/redcap: missing={sorted(required_core - command_labels)}")
    return {
        "doctor": "doctor" in command_labels,
        "debug": "debug" in command_labels,
        "trace": "--trace" in text or "trace)" in text,
        "version": "version" in command_labels,
        "defaults_to_package_task_file": '${1:-$REDCAP_ROOT/.dev-task.md}' in text,
    }


def validate_review(policy: dict[str, Any], review: dict[str, Any], root: Path) -> tuple[int, int, int]:
    if review.get("version") != 1:
        fail("review version must be 1")
    if review.get("review_id") != "pre-release-product-architecture-review":
        fail("review_id must be pre-release-product-architecture-review")
    if require_text(review, "task_id", "review") != "pre-release-product-architecture-review":
        fail("review task_id mismatch")

    allowed_statuses = set(policy.get("allowed_review_statuses", []))
    status = require_text(review, "status", "review")
    if status not in allowed_statuses:
        fail(f"unsupported review status: {status}")
    if require_text(review, "release_recommendation", "review") == "ready-for-public-release":
        fail("P4-2a review must not directly declare public release ready")

    facts = review.get("observed_facts")
    if not isinstance(facts, dict):
        fail("review observed_facts must be an object")

    package_json = load_json(root / "package.json", "package.json")
    if facts.get("current_package_name") != package_json.get("name"):
        fail("review current_package_name does not match package.json")
    if facts.get("package_private") is not package_json.get("private"):
        fail("review package_private does not match package.json")
    if facts.get("package_license") != package_json.get("license"):
        fail("review package_license does not match package.json")
    bin_map = package_json.get("bin")
    if not isinstance(bin_map, dict) or facts.get("package_bin") != bin_map.get("redcap"):
        fail("review package_bin does not match package.json bin.redcap")

    runtime_manifest = run_output(["bash", str(root / "compass/tools/redcap-runtime-package-manifest.sh"), "--check"], cwd=root)
    if "RUNTIME_PACKAGE_MANIFEST_OK" not in runtime_manifest:
        fail("runtime package manifest did not pass")
    public_surface = run_output(["bash", str(root / "compass/tools/redcap-public-package-surface.sh")], cwd=root)
    if "PUBLIC_PACKAGE_SURFACE_OK" not in public_surface:
        fail("public package surface check did not pass")
    package_safety = run_output(["bash", str(root / "compass/tools/redcap-package-publish-safety-check.sh")], cwd=root)
    if "PACKAGE_PUBLISH_SAFETY_OK" not in package_safety:
        fail("package safety did not pass")
    public_arsenal_boundary = run_output(["bash", str(root / "compass/tools/redcap-public-arsenal-claim-boundary.sh")], cwd=root)
    if "PUBLIC_ARSENAL_CLAIM_BOUNDARY_OK" not in public_arsenal_boundary:
        fail("public arsenal claim boundary did not pass")
    if facts.get("public_arsenal_claim_boundary_status") != "pass":
        fail("review observed_facts must record public_arsenal_claim_boundary_status=pass")
    if facts.get("npm_pack_dry_run_checked") is not True:
        fail("review observed_facts must record npm_pack_dry_run_checked=true")
    pack_count = npm_pack_file_count(root, facts)
    if facts.get("package_candidate_count") != pack_count:
        fail(f"review package_candidate_count={facts.get('package_candidate_count')} does not match npm pack count={pack_count}")

    split = load_json(root / "references/execution-layer-split-dry-run.json", "execution layer split manifest")
    if facts.get("execution_layer_split_status") != split.get("status"):
        fail("review execution_layer_split_status does not match split manifest")
    if facts.get("runtime_root_exists") is not (root / "runtime").exists():
        fail("review runtime_root_exists does not match filesystem")

    commands = bin_command_surface(root)
    if facts.get("cli_has_doctor_command") is not commands["doctor"]:
        fail("review cli_has_doctor_command does not match bin/redcap")
    if facts.get("cli_has_debug_command") is not commands["debug"]:
        fail("review cli_has_debug_command does not match bin/redcap")
    if facts.get("cli_has_trace_option") is not commands["trace"]:
        fail("review cli_has_trace_option does not match bin/redcap")
    if facts.get("cli_has_version_command") is not commands["version"]:
        fail("review cli_has_version_command does not match bin/redcap")
    if facts.get("cli_defaults_to_package_task_file") is not commands["defaults_to_package_task_file"]:
        fail("review cli_defaults_to_package_task_file does not match bin/redcap")

    substantive_count = arsenal_substantive_entries(review, root)
    if facts.get("redcap_arsenal_substantive_entries") != substantive_count:
        fail("review redcap_arsenal_substantive_entries does not match external worktree")
    if substantive_count == 0 and facts.get("redcap_arsenal_content_state") != "template-only":
        fail("empty redcap-arsenal must be marked template-only")
    if substantive_count > 0 and facts.get("redcap_arsenal_content_state") == "template-only":
        fail("non-empty redcap-arsenal must not be marked template-only")

    findings = require_list(review, "findings", "review")
    severities = set(policy.get("allowed_finding_severities", []))
    finding_ids: set[str] = set()
    release_blockers = should_fix = deferred = 0
    for index, finding in enumerate(findings, start=1):
        if not isinstance(finding, dict):
            fail(f"finding[{index}] must be an object")
        finding_id = require_text(finding, "id", f"finding[{index}]")
        if finding_id in finding_ids:
            fail(f"duplicate finding id: {finding_id}")
        finding_ids.add(finding_id)
        require_text(finding, "dimension", f"finding[{index}]")
        severity = require_text(finding, "severity", f"finding[{index}]")
        if severity not in severities:
            fail(f"unsupported finding severity {severity}: {finding_id}")
        require_text(finding, "claim", f"finding[{index}]")
        evidence = require_list(finding, "evidence", f"finding[{index}]")
        for evidence_path in evidence:
            if isinstance(evidence_path, str) and (evidence_path.startswith("/Users/") or evidence_path.startswith("/home/")):
                fail(f"finding evidence leaks local user path: {finding_id}")
        if severity == "release-blocker":
            release_blockers += 1
            if finding.get("required_before_public_release") is not True:
                fail(f"release blocker must be required_before_public_release=true: {finding_id}")
        elif severity == "should-fix":
            should_fix += 1
        elif severity == "deferred":
            deferred += 1

    expected_blockers: set[str] = set()
    approved_name = facts.get("user_approved_public_package_name")
    if package_json.get("name") != approved_name:
        expected_blockers.add("public-package-identity-not-finalized")
    if package_json.get("private") is True:
        expected_blockers.add("public-package-publish-disabled")
    if split.get("status") == "dry-run-only" or not (root / "runtime").exists():
        expected_blockers.add("runtime-project-user-boundaries-not-physically-split")
    if not (commands["doctor"] and commands["debug"] and commands["trace"]):
        expected_blockers.add("cli-debug-contract-incomplete")
    if commands["defaults_to_package_task_file"]:
        expected_blockers.add("cli-workspace-context-not-separated")
    if package_json.get("license") == "UNLICENSED":
        expected_blockers.add("distribution-license-not-finalized")
    for required in sorted(expected_blockers):
        if required not in finding_ids:
            fail(f"missing required observed release blocker finding: {required}")

    expected_should_fix: set[str] = set()
    if pack_count > 150:
        expected_should_fix.add("package-surface-too-broad-for-public-cli")
    if substantive_count == 0:
        expected_should_fix.add("public-arsenal-template-only")
    for required in sorted(expected_should_fix):
        if required not in finding_ids:
            fail(f"missing required observed should-fix finding: {required}")

    must_not_claim = require_list(review, "must_not_claim", "review")
    if not any("public-release-ready" in str(item) for item in must_not_claim):
        fail("must_not_claim must forbid public-release-ready claims")
    require_list(review, "recommended_next_tranches", "review")
    return release_blockers, should_fix, deferred


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap pre-release product architecture review.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--review", default=str(DEFAULT_REVIEW))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy = load_json(Path(args.policy), "policy")
    review = load_json(Path(args.review), "review")
    validate_policy(policy)
    release_blockers, should_fix, deferred = validate_review(policy, review, root)
    print(
        "PRE_RELEASE_PRODUCT_ARCHITECTURE_OK "
        f"recommendation={review['release_recommendation']} "
        f"release_blockers={release_blockers} should_fix={should_fix} deferred={deferred}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

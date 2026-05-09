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
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "references/runtime-package-readiness-policy.json"
PACKAGE_SAFETY = ROOT / "compass/tools/redcap-package-publish-safety-check.sh"
PACKAGE_SAFETY_POLICY = ROOT / "references/package-publish-safety-policy.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-runtime-package-manifest] {message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid json {path}: {exc}")
    if not isinstance(payload, dict):
        fail("policy must be a JSON object")
    return payload


def require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"missing non-empty {key}")
    return value.strip()


def require_text_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        fail(f"{key} must be a non-empty list")
    result: list[str] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            fail(f"{key}[{index}] must be non-empty text")
        result.append(item.strip())
    return result


def safe_relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        fail(f"path escapes repository root: {path}")


def excluded(rel: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(rel, pattern) for pattern in patterns)


def validate_policy(payload: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    if payload.get("version") != 1:
        fail("policy version must be 1")
    if payload.get("policy_id") != "redcap-runtime-package-readiness":
        fail("policy_id must be redcap-runtime-package-readiness")
    if payload.get("status") != "readiness-only":
        fail("status must remain readiness-only until a separate release task")
    if payload.get("publish_allowed") is not False:
        fail("publish_allowed must be false in readiness tasks")
    if require_text(payload, "package_manager") != "npm":
        fail("only npm package readiness is supported in this tranche")
    require_text(payload, "package_name")
    require_text(payload, "package_version")
    bin_map = payload.get("bin")
    if not isinstance(bin_map, dict) or bin_map.get("redcap") != "bin/redcap":
        fail("bin.redcap must point to bin/redcap")
    globs = require_text_list(payload, "candidate_globs")
    excludes = payload.get("exclude_globs", [])
    if not isinstance(excludes, list):
        fail("exclude_globs must be a list")
    exclude_globs = [item.strip() for item in excludes if isinstance(item, str) and item.strip()]
    required = require_text_list(payload, "required_files")
    boundaries = require_text_list(payload, "manual_release_boundaries")
    if len(boundaries) < 2:
        fail("manual_release_boundaries must explain release credentials and registry decisions")
    return globs, exclude_globs, required


def expand_candidates(root: Path, globs: list[str], excludes: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for pattern in globs:
        matches = sorted(root.glob(pattern))
        if not matches:
            fail(f"candidate glob matched no files: {pattern}")
        for match in matches:
            files = sorted(path for path in match.rglob("*") if path.is_file()) if match.is_dir() else [match]
            for file_path in files:
                rel = safe_relative(root, file_path)
                if excluded(rel, excludes):
                    continue
                if rel not in seen:
                    seen.add(rel)
                    results.append(rel)
    if not results:
        fail("candidate globs produced no files")
    return results


def validate_required(candidates: list[str], required: list[str]) -> None:
    candidate_set = set(candidates)
    missing = sorted(item for item in required if item not in candidate_set)
    if missing:
        fail("required package files missing from candidates: " + ", ".join(missing))


def validate_package_json(root: Path, policy: dict[str, Any]) -> None:
    package_json = load_json(root / "package.json")
    if package_json.get("private") is not True:
        fail("package.json must keep private=true until a separate release task")
    if package_json.get("name") != policy.get("package_name"):
        fail("package.json name must match runtime package readiness policy")
    if package_json.get("version") != policy.get("package_version"):
        fail("package.json version must match runtime package readiness policy")
    bin_map = package_json.get("bin")
    if not isinstance(bin_map, dict) or bin_map.get("redcap") != "bin/redcap":
        fail("package.json bin.redcap must point to bin/redcap")
    files = package_json.get("files")
    if not isinstance(files, list) or not files:
        fail("package.json must define a non-empty files whitelist")
    file_patterns = [item for item in files if isinstance(item, str)]
    for required in ("bin/redcap", "README.md", "revive-cap.sh", "closeout-cap.sh"):
        if required not in file_patterns:
            fail(f"package.json files whitelist missing required entry: {required}")
    if "compass/tools/redcap-*.sh" in file_patterns and "!compass/tools/redcap-multi-session-acceptance.sh" not in file_patterns:
        fail("package.json files whitelist must exclude redcap-multi-session-acceptance.sh from broad tool globs")
    positive_patterns = [item for item in file_patterns if not item.startswith("!")]
    negative_patterns = [item[1:] for item in file_patterns if item.startswith("!")]
    expected_positive = [item for item in require_text_list(policy, "candidate_globs") if item != "package.json"]
    expected_negative = require_text_list(policy, "exclude_globs")
    if positive_patterns != expected_positive:
        fail("package.json files positive whitelist must exactly mirror runtime candidate_globs except implicit package.json")
    if negative_patterns != expected_negative:
        fail("package.json files exclusions must exactly mirror runtime exclude_globs")


def validate_publish_safety_policy(root: Path, policy: dict[str, Any]) -> None:
    safety_policy = load_json(PACKAGE_SAFETY_POLICY)
    if safety_policy.get("default_package_globs") != require_text_list(policy, "candidate_globs"):
        fail("publish safety default_package_globs must mirror runtime candidate_globs")
    if safety_policy.get("default_exclude_globs") != require_text_list(policy, "exclude_globs"):
        fail("publish safety default_exclude_globs must mirror runtime exclude_globs")


def validate_npmignore(root: Path) -> None:
    path = root / ".npmignore"
    if not path.is_file():
        fail(".npmignore is required for package readiness")
    text = path.read_text(encoding="utf-8")
    required = [
        ".env",
        ".env.*",
        "AGENTS.md",
        "CLAUDE.md",
        "GEMINI.md",
        "compass/.runtime/",
        "compass/.workflow/",
        "compass/tools/redcap-multi-session-acceptance.sh",
        "prism/runs/",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        fail(".npmignore missing required deny entries: " + ", ".join(missing))


def write_candidate_list(path: Path, candidates: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(candidates) + "\n", encoding="utf-8")


def run_safety(root: Path, candidate_list: Path) -> None:
    if not PACKAGE_SAFETY.is_file():
        fail(f"missing package safety checker: {PACKAGE_SAFETY}")
    completed = subprocess.run(
        ["bash", str(PACKAGE_SAFETY), "--candidate-list", str(candidate_list)],
        cwd=str(root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        sys.stdout.write(completed.stdout)
        fail("package safety gate failed for generated candidate list")


def run_npm_pack_dry_run(root: Path, candidates: list[str]) -> None:
    completed = subprocess.run(
        ["npm", "pack", "--dry-run", "--json"],
        cwd=str(root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        sys.stdout.write(completed.stdout)
        fail("npm pack --dry-run failed")
    try:
        payload = json.loads(completed.stdout)
        files = payload[0]["files"]
    except Exception as exc:
        fail(f"unable to parse npm pack --dry-run output: {exc}")
    pack_paths = {str(item.get("path", "")).strip() for item in files if isinstance(item, dict)}
    pack_paths.discard("")
    candidate_paths = set(candidates)
    only_candidates = sorted(candidate_paths - pack_paths)
    only_pack = sorted(pack_paths - candidate_paths)
    if only_candidates or only_pack:
        details = []
        if only_candidates:
            details.append("only-in-candidates=" + ",".join(only_candidates[:10]))
        if only_pack:
            details.append("only-in-npm-pack=" + ",".join(only_pack[:10]))
        fail("npm pack dry-run differs from generated candidate list: " + "; ".join(details))


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and validate RedCap runtime package candidate files.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--output", help="write newline-delimited candidate list to this path")
    parser.add_argument("--check", action="store_true", help="run package safety against the generated candidate list")
    parser.add_argument("--npm-pack-dry-run", action="store_true", help="also diff generated candidates against npm pack --dry-run output")
    parser.add_argument("--json", action="store_true", help="print JSON summary instead of text summary")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = root / policy_path
    policy = load_json(policy_path)
    globs, excludes, required = validate_policy(policy)
    validate_package_json(root, policy)
    validate_publish_safety_policy(root, policy)
    validate_npmignore(root)
    candidates = expand_candidates(root, globs, excludes)
    validate_required(candidates, required)

    output_path: Path | None = Path(args.output).resolve() if args.output else None
    temp_path: Path | None = None
    if output_path is not None:
        write_candidate_list(output_path, candidates)
        list_for_safety = output_path
    else:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, prefix="redcap-package-candidates-", suffix=".txt") as handle:
            handle.write("\n".join(candidates) + "\n")
            temp_path = Path(handle.name)
        list_for_safety = temp_path

    if args.check:
        run_safety(root, list_for_safety)
    if args.npm_pack_dry_run:
        run_npm_pack_dry_run(root, candidates)

    summary = {
        "status": "ok",
        "policy": safe_relative(root, policy_path),
        "package_name": policy["package_name"],
        "package_version": policy["package_version"],
        "publish_allowed": policy["publish_allowed"],
        "candidate_count": len(candidates),
        "candidate_list": str(output_path or list_for_safety),
        "safety_checked": bool(args.check),
        "npm_pack_dry_run_checked": bool(args.npm_pack_dry_run),
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print("RUNTIME_PACKAGE_MANIFEST_OK")
        for key, value in summary.items():
            print(f"{key}={value}")
    if temp_path is not None:
        try:
            temp_path.unlink()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "references/public-package-surface-policy.json"
RUNTIME_POLICY = ROOT / "references/runtime-package-readiness-policy.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-public-package-surface] {message}")


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


def npm_pack_paths(root: Path) -> set[str]:
    output = run_output(["npm", "pack", "--dry-run", "--json"], root)
    try:
        payload = json.loads(output)
        files = payload[0]["files"]
    except Exception as exc:
        fail(f"unable to parse npm pack --dry-run output: {exc}")
    paths = {str(item.get("path", "")).strip() for item in files if isinstance(item, dict)}
    paths.discard("")
    if not paths:
        fail("npm pack --dry-run returned no files")
    return paths


def path_matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def validate(root: Path, policy_path: Path) -> dict[str, Any]:
    policy = load_json(policy_path, "public package surface policy")
    package_json = load_json(root / "package.json", "package.json")
    runtime_policy = load_json(root / "references/runtime-package-readiness-policy.json", "runtime package readiness policy")

    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "redcap-public-package-surface":
        fail("policy_id must be redcap-public-package-surface")
    if policy.get("status") != "prepared-private-readiness":
        fail("status must remain prepared-private-readiness in P4-2d")
    if require_text(policy, "package_manager", "policy") != "npm":
        fail("only npm package surface is supported")
    prepared_name = require_text(policy, "prepared_package_name", "policy")
    if prepared_name != "@norven63/redcap":
        fail("prepared_package_name must be the user-approved @norven63/redcap")
    if policy.get("publish_allowed") is not False:
        fail("public package surface policy must keep publish_allowed=false")
    if policy.get("package_private_required") is not True:
        fail("package_private_required must be true")
    if require_text(policy, "license_status", "policy") != "manual-before-public-publish":
        fail("license_status must preserve manual license decision")
    if require_text(policy, "current_license", "policy") != "UNLICENSED":
        fail("current_license must remain UNLICENSED until explicit license decision")

    if package_json.get("name") != prepared_name:
        fail("package.json name must match prepared public package name")
    if package_json.get("private") is not True:
        fail("package.json private must remain true in P4-2d")
    if package_json.get("license") != policy["current_license"]:
        fail("package.json license must match current_license")

    if runtime_policy.get("status") != "readiness-only":
        fail("runtime package policy must remain readiness-only")
    if runtime_policy.get("publish_allowed") is not False:
        fail("runtime package policy must keep publish_allowed=false")
    if runtime_policy.get("package_name") != prepared_name:
        fail("runtime package policy package_name must match prepared package name")
    if runtime_policy.get("license_status") != policy["license_status"]:
        fail("runtime package policy license_status must match public package policy")

    run_output(["bash", str(root / "compass/tools/redcap-runtime-package-manifest.sh"), "--check", "--npm-pack-dry-run"], root)
    run_output(["bash", str(root / "compass/tools/redcap-package-publish-safety-check.sh")], root)

    pack_paths = npm_pack_paths(root)
    max_count = policy.get("max_candidate_count")
    if not isinstance(max_count, int) or max_count <= 0:
        fail("max_candidate_count must be a positive integer")
    if len(pack_paths) > max_count:
        fail(f"package candidate count {len(pack_paths)} exceeds max_candidate_count={max_count}")

    forbidden = [item for item in require_list(policy, "forbidden_package_paths", "policy") if isinstance(item, str)]
    leaked = sorted(path for path in pack_paths if path_matches(path, forbidden))
    if leaked:
        fail("forbidden paths found in npm package surface: " + ", ".join(leaked[:10]))

    required_checks = [str(item).strip() for item in require_list(policy, "required_runtime_checks", "policy")]
    expected_checks = {
        "bash compass/tools/redcap-runtime-package-manifest.sh --check --npm-pack-dry-run",
        "bash compass/tools/redcap-package-publish-safety-check.sh",
        "bash compass/tools/redcap-public-package-surface.sh",
    }
    if set(required_checks) != expected_checks:
        fail("required_runtime_checks must match the actual public package readiness command set")
    for command in required_checks:
        parts = command.split()
        script_rel = next((part for part in parts if part.startswith("compass/tools/")), "")
        if not script_rel or not (root / script_rel).is_file():
            fail(f"required runtime check script missing: {script_rel or command}")

    boundaries = [str(item) for item in require_list(policy, "manual_release_boundaries", "policy")]
    required_boundary_terms = ["private=false", "publish_allowed=true", "license", "npm publish", "public-release-ready"]
    for term in required_boundary_terms:
        if not any(term in item for item in boundaries):
            fail(f"manual_release_boundaries missing term: {term}")

    return {
        "package_name": prepared_name,
        "license_status": policy["license_status"],
        "publish_allowed": False,
        "private": True,
        "candidate_count": len(pack_paths),
        "surface_mode": policy["surface_mode"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap public package identity and package surface readiness.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = root / policy_path
    result = validate(root, policy_path)
    if args.json:
        print(json.dumps({"status": "ok", **result}, ensure_ascii=False, indent=2))
    else:
        print("PUBLIC_PACKAGE_SURFACE_OK")
        for key, value in result.items():
            print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

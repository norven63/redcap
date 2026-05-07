#!/usr/bin/env python3
# 用途：产品形态与检索治理脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#product-shape-and-retrieval

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-legacy-asset-lifecycle-check] {message}")


def load_json(path: pathlib.Path) -> dict:
    if not path.is_file():
        fail(f"missing lifecycle policy: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid lifecycle policy json: {exc}")


def resolve(root: pathlib.Path, rel_path: str) -> pathlib.Path:
    path = pathlib.Path(rel_path)
    return path if path.is_absolute() else root / path


def run_command(root: pathlib.Path, command: str) -> tuple[int, str]:
    completed = subprocess.run(
        ["bash", "-lc", command],
        cwd=str(root),
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode, (completed.stdout or "") + (completed.stderr or "")


def parse_key_values(output: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in output.splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def main() -> None:
    if len(sys.argv) != 3:
        fail("usage: redcap-legacy-asset-lifecycle-check.py <redcap_root> <policy_path>")

    root = pathlib.Path(sys.argv[1]).resolve()
    policy_arg = pathlib.Path(sys.argv[2])
    policy_path = policy_arg if policy_arg.is_absolute() else root / policy_arg
    policy = load_json(policy_path)

    if policy.get("version") != 1:
        fail("policy version must be 1")

    required_actions = set(policy.get("required_actions") or [])
    if not required_actions:
        fail("required_actions must be non-empty")

    assets = policy.get("assets")
    if not isinstance(assets, list) or not assets:
        fail("assets must be a non-empty list")
    required_assets = {
        "current-task-card",
        "docs-catalog",
        "task-reports",
        "spec-registry",
        "prism-runs",
        "knowledge-lessons",
        "runtime-working-dirs",
    }
    seen: set[str] = set()
    for asset in assets:
        if not isinstance(asset, dict):
            fail("asset entries must be objects")
        asset_id = asset.get("id")
        if not isinstance(asset_id, str) or not asset_id.strip():
            fail("asset missing id")
        if asset_id in seen:
            fail(f"duplicate asset id: {asset_id}")
        seen.add(asset_id)
        rel_path = asset.get("path")
        if not isinstance(rel_path, str) or not rel_path.strip():
            fail(f"{asset_id}: path must be non-empty")
        if not resolve(root, rel_path).exists():
            fail(f"{asset_id}: path does not exist: {rel_path}")
        action = asset.get("default_action")
        if action not in required_actions:
            fail(f"{asset_id}: invalid default_action: {action}")
        authority = asset.get("authority")
        if not isinstance(authority, str) or len(authority.strip()) < 30:
            fail(f"{asset_id}: authority must be meaningful")
        check_paths = asset.get("check_paths")
        if not isinstance(check_paths, list) or not check_paths:
            fail(f"{asset_id}: check_paths must be non-empty")
        for check_path in check_paths:
            if not isinstance(check_path, str) or not resolve(root, check_path).exists():
                fail(f"{asset_id}: check path does not exist: {check_path}")
    missing = sorted(required_assets - seen)
    if missing:
        fail("missing required asset policies: " + ", ".join(missing))

    prism_policy = policy.get("prism_runs_policy")
    if not isinstance(prism_policy, dict):
        fail("prism_runs_policy must be an object")
    check_command = prism_policy.get("check_command")
    summary_command = prism_policy.get("summary_command")
    if not isinstance(check_command, str) or not isinstance(summary_command, str):
        fail("prism_runs_policy commands must be strings")
    status, output = run_command(root, check_command)
    if status != 0:
        fail("prism runs lifecycle check failed: " + output.strip())
    status, output = run_command(root, summary_command)
    if status != 0:
        fail("prism runs lifecycle summary failed: " + output.strip())
    values = parse_key_values(output)
    target = int(prism_policy.get("acceptance_fixture_target", 0))
    actual = int(values.get("acceptance-fixture", "0"))
    purgeable = int(values.get("purgeable_acceptance", "0"))
    acceptance_running = os.environ.get("REDCAP_ACCEPTANCE_RUNNING", "") == "1"
    if not acceptance_running and (actual > target or purgeable > target):
        fail(f"prism/runs has acceptance residue: acceptance-fixture={actual} purgeable_acceptance={purgeable}")

    print("LEGACY_ASSET_LIFECYCLE")
    print(f"assets={len(assets)} prism_acceptance_fixture={actual}")
    if acceptance_running and (actual > target or purgeable > target):
        print("acceptance_residue=allowed-during-acceptance-run")
    print("LEGACY_ASSET_LIFECYCLE_OK")


if __name__ == "__main__":
    main()

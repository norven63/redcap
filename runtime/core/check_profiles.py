#!/usr/bin/env python3
"""RedCap layered check profile decision surface."""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "assets" / "contracts" / "check-profiles.json"

PROFILE_ORDER = ["fast", "standard", "release", "terminal"]
TERMINAL_HINTS = {"terminal", "complete-revival", "redcap-complete-revival", "terminal-goal", "完整复活", "终局"}
RELEASE_HINTS = {"project-install", "project_install", "release", "package", "发布", "打包", "e2e-cache", "evidence-retention", "forge-private-boundary"}
STANDARD_HINTS = {"runtime/", "assets/contracts/", ".codex/", "hooks", "knowledge", "prism", "loom", "self-purification"}


def load_contract() -> dict[str, Any]:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("check profile contract must be a JSON object")
    return payload


def profile_by_id(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    profiles = contract.get("profiles")
    if not isinstance(profiles, list):
        return {}
    return {str(item.get("id")): item for item in profiles if isinstance(item, dict)}


def runner_profile_steps() -> dict[str, tuple[str, ...] | None]:
    spec = importlib.util.spec_from_file_location("redcap_check_runner_for_profile_validation", REPO_ROOT / "runtime" / "core" / "check_runner.py")
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    value = getattr(module, "PROFILE_STEPS", {})
    return value if isinstance(value, dict) else {}


def classify_files(files: list[str], task: str) -> str:
    lowered = " ".join(files + [task]).lower()
    if any(hint in lowered for hint in TERMINAL_HINTS):
        return "terminal"
    if any(hint in lowered for hint in RELEASE_HINTS):
        return "release"
    if any(hint in lowered for hint in STANDARD_HINTS):
        return "standard"
    return "fast"


def decide_profile(files: list[str], task: str) -> dict[str, Any]:
    contract = load_contract()
    profiles = profile_by_id(contract)
    profile_id = classify_files(files, task)
    profile = profiles.get(profile_id, {})
    return {
        "schema_id": "redcap-check-profile-decision",
        "ok": bool(profile),
        "profile": profile_id,
        "profile_order": PROFILE_ORDER,
        "changed_files": files,
        "task_summary": task,
        "required_checks": profile.get("required_checks", []),
        "cannot_replace": profile.get("cannot_replace", profile.get("cannot_be_replaced_by", [])),
        "cache_allowed": False,
        "cache_policy": contract.get("cache_policy", {}),
        "reason": profile.get("title"),
    }


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-check-profiles-contract":
        failures.append("schema_id 错误")
    profiles = profile_by_id(contract)
    missing = [item for item in PROFILE_ORDER if item not in profiles]
    if missing:
        failures.append(f"缺少检查画像：{missing}")
    fast = profiles.get("fast", {})
    if "release" not in fast.get("cannot_replace", []) or "terminal" not in fast.get("cannot_replace", []):
        failures.append("fast 必须声明不能替代 release 和 terminal")
    release = profiles.get("release", {})
    release_checks = "\n".join(str(item) for item in release.get("required_checks", []))
    if "runtime/bin/redcap check --profile release" not in release_checks:
        failures.append("release 必须使用 runtime/bin/redcap check --profile release")
    standard_checks = "\n".join(str(item) for item in profiles.get("standard", {}).get("required_checks", []))
    if "persona-observation-check" not in standard_checks:
        failures.append("standard 合同必须声明 persona-observation-check")
    if "persona-observation-check" not in release_checks:
        failures.append("release 合同必须声明 persona-observation-check")
    runner_profiles = runner_profile_steps()
    for profile_id in ["standard", "release"]:
        steps = runner_profiles.get(profile_id)
        if not isinstance(steps, tuple) or "persona-observation-check" not in steps:
            failures.append(f"{profile_id} 实际运行画像必须包含 persona-observation-check")
    terminal = profiles.get("terminal", {})
    terminal_checks = "\n".join(str(item) for item in terminal.get("required_checks", []))
    if "runtime/bin/redcap check --profile terminal" not in terminal_checks:
        failures.append("terminal 必须使用 runtime/bin/redcap check --profile terminal")
    if "complete-revival-check --require-terminal-verified" not in terminal_checks:
        failures.append("terminal 必须要求 complete-revival-check --require-terminal-verified")
    cache_policy = contract.get("cache_policy", {})
    if cache_policy.get("enabled") is not False:
        failures.append("安全缓存未实现前 cache_policy.enabled 必须为 false")
    return failures


def cmd_check(_: argparse.Namespace) -> int:
    contract = load_contract()
    failures = validate_contract(contract)
    result = {
        "schema_id": "redcap-check-profiles-check",
        "ok": not failures,
        "contract": str(CONTRACT.relative_to(REPO_ROOT)),
        "profiles": PROFILE_ORDER,
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_CHECK_PROFILES_OK")
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    files = args.changed_file or []
    result = decide_profile(files, args.task or "")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_CHECK_PROFILE_DECISION_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    cases = [
        (["assets/docs/readme.md"], "说明文字调整", "fast"),
        (["runtime/core/foo.py"], "修复运行时代码", "standard"),
        (["runtime/core/project_install.py"], "修改 release package", "release"),
        (["assets/contracts/terminal-goals.json"], "关闭 redcap-complete-revival", "terminal"),
    ]
    for files, task, expected in cases:
        actual = decide_profile(files, task).get("profile")
        if actual != expected:
            failures.append(f"{files} / {task} 应为 {expected}，实际为 {actual}")
    failures.extend(validate_contract(load_contract()))
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_CHECK_PROFILES_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap 分层检查画像决策器")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.set_defaults(func=cmd_check)
    decide = sub.add_parser("decide")
    decide.add_argument("--task", default="")
    decide.add_argument("--changed-file", action="append")
    decide.set_defaults(func=cmd_decide)
    self_check = sub.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

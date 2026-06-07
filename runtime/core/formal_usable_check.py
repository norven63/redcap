#!/usr/bin/env python3
"""通过用户可见工作流检查 RedCap 是否已达到正式可用基线。"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def run(argv: list[str], timeout: int = 180) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            argv,
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "argv": argv,
            "exit_code": 124,
            "ok": False,
            "stdout": exc.stdout or "",
            "stderr": f"命令超时：{timeout} 秒",
            "timed_out": True,
        }
    return {
        "argv": argv,
        "exit_code": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "timed_out": False,
    }


def leading_json(stdout: str) -> dict[str, Any]:
    parsed, _ = json.JSONDecoder().raw_decode(stdout.lstrip())
    return parsed if isinstance(parsed, dict) else {}


def summarize_command(result: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "argv": result["argv"],
        "exit_code": result["exit_code"],
        "ok": result["ok"],
        "stdout_tail": str(result.get("stdout", ""))[-1200:],
        "stderr_tail": str(result.get("stderr", ""))[-1200:],
    }
    if result.get("checked_by_parent") is True:
        summary["checked_by_parent"] = True
    return summary


def parent_verified_host_audit_result() -> dict[str, Any]:
    return {
        "argv": ["runtime/bin/redcap", "host-hook-audit"],
        "exit_code": 0,
        "ok": True,
        "stdout": "宿主审计由父级检查单独执行；正式可用检查不重复触发重检查。",
        "stderr": "",
        "timed_out": False,
        "checked_by_parent": True,
    }


def check_formal_usability(*, skip_host_hook_audit: bool = False) -> dict[str, Any]:
    commands = {
        "status": run(["runtime/bin/redcap", "status", "--json", "--require-scan-complete", "--fail-on-open"]),
        "revive": run(["runtime/bin/redcap", "revive", "--json", "--no-write-evidence", "--require-scan-complete", "--fail-on-open"]),
        "revival_queue": run(["runtime/bin/redcap", "revival-queue", "check", "--skip-heavy-host-audit"]),
        "host_hook_audit": (
            parent_verified_host_audit_result()
            if skip_host_hook_audit
            else run(["runtime/bin/redcap", "host-hook-audit"], timeout=240)
        ),
        "scan_conclusion": run(["runtime/bin/redcap", "scan-conclusion", "check"]),
        "task_facts": run(["runtime/bin/redcap", "task-facts", "check"]),
        "terminal_goal": run(["runtime/bin/redcap", "terminal-goal", "check"]),
    }
    failures: list[str] = []
    for name, result in commands.items():
        if not result["ok"]:
            failures.append(f"{name} 命令失败")
    status_payload = leading_json(commands["status"].get("stdout", ""))
    revive_payload = leading_json(commands["revive"].get("stdout", ""))
    queue_payload = leading_json(commands["revival_queue"].get("stdout", ""))
    if status_payload.get("scan_state", {}).get("scan_complete") is not True:
        failures.append("status 命令没有确认 360 扫描完成")
    non_terminal_open = status_payload.get("terminal_goals", {}).get("non_terminal_open_tasks", [])
    if non_terminal_open:
        failures.append("status 命令显示仍有非终局父任务开放")
    if revive_payload.get("soul", {}).get("ok") is not True:
        failures.append("revive 命令没有成功加载 Cap 身份")
    if queue_payload.get("required_open"):
        failures.append(f"复活队列仍有开放项：{queue_payload.get('required_open')}")
    return {
        "schema_id": "redcap-formal-usability-baseline-check",
        "level": "正式可用基线",
        "not_equal_to": "完整复活",
        "ok": not failures,
        "checks": {name: summarize_command(result) for name, result in commands.items()},
        "failures": failures,
    }


def cmd_check(_: argparse.Namespace) -> int:
    result = check_formal_usability(skip_host_hook_audit=_.skip_host_hook_audit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_FORMAL_USABLE_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    fixture = {
        "status": {
            "ok": True,
            "stdout": json.dumps({
                "scan_state": {"scan_complete": True},
                "task_summary": {"open_count": 1},
                "terminal_goals": {"non_terminal_open_tasks": []},
            }, ensure_ascii=False),
            "stderr": "",
            "argv": [],
            "exit_code": 0,
        },
        "revive": {"ok": True, "stdout": json.dumps({"soul": {"ok": True}}, ensure_ascii=False), "stderr": "", "argv": [], "exit_code": 0},
        "revival_queue": {"ok": True, "stdout": json.dumps({"required_open": []}, ensure_ascii=False), "stderr": "", "argv": [], "exit_code": 0},
    }
    if leading_json(fixture["status"]["stdout"]).get("scan_state", {}).get("scan_complete") is not True:
        failures.append("fixture status parse failed")
    bad = json.dumps({"required_open": ["RQ-01"]}, ensure_ascii=False)
    if not leading_json(bad).get("required_open"):
        failures.append("fixture open queue parse failed")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_FORMAL_USABLE_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap 正式可用基线检查器")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument(
        "--skip-host-hook-audit",
        action="store_true",
        help="父级已经单独执行宿主审计时，避免正式可用检查重复触发重检查。",
    )
    check.set_defaults(func=cmd_check)
    self_check = sub.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

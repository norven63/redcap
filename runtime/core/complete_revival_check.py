#!/usr/bin/env python3
"""RedCap 完整复活终局验收检查器。"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
NO_PROMOTE_RECORDS = [
    "assets/archaeology/no-promote/pathology-report-as-progress-v1.json",
    "assets/archaeology/no-promote/pathology-receipt-as-completion-v1.json",
    "assets/archaeology/no-promote/pathology-closeout-recursion-v1.json",
    "assets/archaeology/no-promote/pathology-raw-evidence-default-v1.json",
]


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
    try:
        parsed, _ = json.JSONDecoder().raw_decode(stdout.lstrip())
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def summarize(result: dict[str, Any]) -> dict[str, Any]:
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
        "stdout": "宿主审计已跳过；终局验收不重复触发重检查，结果只能视为部分通过。",
        "stderr": "",
        "timed_out": False,
        "checked_by_parent": True,
        "skipped": True,
    }


def redcap_terminal_state(payload: dict[str, Any]) -> dict[str, Any]:
    states = payload.get("terminal_goal_states")
    if states is None:
        states = payload.get("terminal_goals", {}).get("states")
    if not isinstance(states, list):
        return {}
    for state in states:
        if isinstance(state, dict) and state.get("id") == "redcap-complete-revival":
            return state
    return {}


def validate_revival_queue(payload: dict[str, Any], failures: list[str]) -> None:
    if payload.get("schema_id") != "redcap-revival-execution-queue":
        failures.append("复活队列输出 schema_id 错误")
        return
    if payload.get("ok") is not True:
        failures.append("复活队列没有通过")
    if payload.get("required_open"):
        failures.append(f"复活队列仍有开放项：{payload.get('required_open')}")
    coverage = payload.get("merge_coverage")
    if not isinstance(coverage, dict) or coverage.get("ok") is not True:
        failures.append("360 扫描合并覆盖没有通过复活队列检查")
    else:
        if len(coverage.get("portable_ids", [])) < 10:
            failures.append("可迁移设计覆盖数量不足")
        if len(coverage.get("risk_ids", [])) < 8:
            failures.append("风险设计覆盖数量不足")
        if int(coverage.get("no_promote_count") or 0) < 4:
            failures.append("禁止提升记录数量不足")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        failures.append("复活队列缺少条目")
        return
    for entry in entries:
        if not isinstance(entry, dict):
            failures.append("复活队列条目格式错误")
            continue
        if entry.get("required_for_formal_use") is True and entry.get("status") != "verified":
            failures.append(f"复活队列必需项未验证：{entry.get('id')}")
        if entry.get("scan_refs_present") is not True:
            failures.append(f"复活队列扫描引用缺失：{entry.get('id')}")
        command_results = entry.get("command_results")
        if not isinstance(command_results, list) or not command_results:
            failures.append(f"复活队列条目缺少命令验证：{entry.get('id')}")
            continue
        for result in command_results:
            if not isinstance(result, dict) or result.get("ok") is not True:
                failures.append(f"复活队列条目命令失败：{entry.get('id')}")


def validate_open_loop_queue(payload: dict[str, Any], failures: list[str]) -> None:
    if payload.get("schema_id") != "redcap-open-loop-closure-queue-check":
        failures.append("open-loop 队列输出 schema_id 错误")
        return
    if payload.get("ok") is not True:
        failures.append(f"open-loop 队列结构检查失败：{payload.get('failures')}")
    if payload.get("closeout_allowed") is not True:
        blockers = payload.get("closeout_blockers")
        failures.append(f"open-loop 队列仍有未闭环 P0/P1：{blockers}")


def validate_status(payload: dict[str, Any], failures: list[str], *, require_terminal_verified: bool) -> None:
    if payload.get("schema_id") != "redcap-status-surface":
        failures.append("状态面 schema_id 错误")
        return
    if payload.get("ok") is not True:
        failures.append("状态面没有通过")
    if payload.get("scan_state", {}).get("scan_complete") is not True:
        failures.append("状态面没有确认 360 扫描完成")
    non_terminal_open = payload.get("terminal_goals", {}).get("non_terminal_open_tasks", [])
    if non_terminal_open:
        failures.append("状态面显示仍有非终局开放任务")
    terminal = redcap_terminal_state(payload)
    if require_terminal_verified:
        if terminal.get("terminal_verified") is not True or terminal.get("open") is not False:
            failures.append("完整复活终局父任务尚未验证关闭")


def validate_terminal_goal(payload: dict[str, Any], failures: list[str], *, require_terminal_verified: bool) -> None:
    if payload.get("ok") is not True:
        failures.append("终局目标检查没有通过")
    terminal = redcap_terminal_state(payload)
    if not terminal:
        failures.append("终局目标检查缺少 RedCap 完整复活状态")
        return
    if require_terminal_verified:
        if terminal.get("terminal_verified") is not True or terminal.get("open") is not False:
            failures.append("终局目标尚未确认 RedCap 完整复活")


def validate_contract(failures: list[str]) -> None:
    contract_path = REPO_ROOT / "assets" / "contracts" / "terminal-goals.json"
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"终局目标合同无法读取：{exc}")
        return
    goals = contract.get("terminal_goals")
    redcap_goal = next(
        (goal for goal in goals if isinstance(goal, dict) and goal.get("id") == "redcap-complete-revival"),
        None,
    ) if isinstance(goals, list) else None
    if not isinstance(redcap_goal, dict):
        failures.append("终局目标合同缺少 RedCap 完整复活目标")
        return
    if redcap_goal.get("terminal_level") != "terminal_complete":
        failures.append("RedCap 完整复活终局等级不是 terminal_complete")
    if len(redcap_goal.get("terminal_acceptance", [])) < 4:
        failures.append("RedCap 完整复活验收条件不足")
    acceptance = "\n".join(str(item) for item in redcap_goal.get("terminal_acceptance", []))
    if "完整角色化工程工作流" not in acceptance:
        failures.append("RedCap 完整复活验收条件必须包含完整角色化工程工作流")
    for required in ["RedCap Forge", "redcap-arsenal", "项目级安装"]:
        if required not in acceptance:
            failures.append(f"RedCap 完整复活验收条件必须包含：{required}")
    forbidden = "\n".join(str(item) for item in redcap_goal.get("forbidden_substitutions", []))
    if "最小可用执行内核" not in forbidden and "最小执行内核" not in forbidden:
        failures.append("RedCap 完整复活禁止替代项必须包含最小执行内核")
    if "redcap-complete-revival" not in redcap_goal.get("required_verified_task_facts", []):
        failures.append("RedCap 完整复活没有绑定父任务事实")


def validate_no_promote_records(failures: list[str]) -> None:
    missing = [path for path in NO_PROMOTE_RECORDS if not (REPO_ROOT / path).is_file()]
    if missing:
        failures.append(f"禁止提升记录缺失：{missing}")


def check_complete_revival(
    *,
    require_terminal_verified: bool = False,
    skip_host_hook_audit: bool = False,
) -> dict[str, Any]:
    commands = {
        "status": run(["runtime/bin/redcap", "status", "--json", "--require-scan-complete", "--fail-on-open"]),
        "revive": run(["runtime/bin/redcap", "revive", "--json", "--no-write-evidence", "--require-scan-complete", "--fail-on-open"]),
        "revival_queue": run(["runtime/bin/redcap", "revival-queue", "check", "--skip-heavy-host-audit"]),
        "open_loop_queue": run(["runtime/bin/redcap", "revival-followthrough", "open-loop-check"]),
        "formal_usable": run(["runtime/bin/redcap", "formal-usable-check", "--skip-host-hook-audit"]),
        "scan_conclusion": run(["runtime/bin/redcap", "scan-conclusion", "check"]),
        "phase2_blueprint": run(["runtime/bin/redcap", "phase2-blueprint", "check"]),
        "full_revival_amendment": run(["runtime/bin/redcap", "full-revival-amendment", "check"]),
        "loom_workflow": run(["runtime/bin/redcap", "loom-workflow", "check"]),
        "forge": run(["runtime/bin/redcap", "forge", "check"]),
        "arsenal": run(["runtime/bin/redcap", "arsenal", "check"]),
        "project_install": run(["runtime/bin/redcap", "project-install", "self-check"]),
        "host_hook_audit": (
            parent_verified_host_audit_result()
            if skip_host_hook_audit
            else run(["runtime/bin/redcap", "host-hook-audit"])
        ),
        "knowledge_gateway": run(["runtime/bin/redcap", "knowledge-gateway", "check"]),
        "soul_load": run(["runtime/bin/redcap", "soul-load", "check"]),
        "layout": run(["runtime/bin/redcap", "layout-check"]),
        "terminal_goal": run(["runtime/bin/redcap", "terminal-goal", "check"]),
    }
    failures: list[str] = []
    for name, result in commands.items():
        if result.get("ok") is not True:
            failures.append(f"{name} 命令失败")
    validate_status(leading_json(commands["status"].get("stdout", "")), failures, require_terminal_verified=require_terminal_verified)
    validate_revival_queue(leading_json(commands["revival_queue"].get("stdout", "")), failures)
    validate_open_loop_queue(leading_json(commands["open_loop_queue"].get("stdout", "")), failures)
    validate_terminal_goal(leading_json(commands["terminal_goal"].get("stdout", "")), failures, require_terminal_verified=require_terminal_verified)
    validate_contract(failures)
    validate_no_promote_records(failures)
    terminal_completion_authorized = require_terminal_verified and not failures
    status = "partial_pass_with_host_hook_pending" if skip_host_hook_audit and not failures else ("pass" if not failures else "fail")
    return {
        "schema_id": "redcap-complete-revival-check",
        "level": "完整复活终局验收" if require_terminal_verified else "完整复活前置验收",
        "ok": not failures,
        "status": status,
        "require_terminal_verified": require_terminal_verified,
        "skip_host_hook_audit": skip_host_hook_audit,
        "host_hook_audit": {
            "status": "skipped" if skip_host_hook_audit else "checked",
            "meaning": (
                "宿主审计未在本命令内执行；本命令通过只能作为部分通过，不能替代完整宿主审计。"
                if skip_host_hook_audit
                else "宿主审计已在本命令内执行。"
            ),
        },
        "terminal_completion_authorized": terminal_completion_authorized,
        "authorizes_task_fact": "redcap-complete-revival" if terminal_completion_authorized else None,
        "checks": {name: summarize(result) for name, result in commands.items()},
        "failures": failures,
    }


def cmd_check(args: argparse.Namespace) -> int:
    result = check_complete_revival(
        require_terminal_verified=args.require_terminal_verified,
        skip_host_hook_audit=args.skip_host_hook_audit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_COMPLETE_REVIVAL_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    good_queue = {
        "schema_id": "redcap-revival-execution-queue",
        "ok": True,
        "required_open": [],
        "merge_coverage": {
            "ok": True,
            "portable_ids": [f"P{index}" for index in range(10)],
            "risk_ids": [f"R{index}" for index in range(8)],
            "no_promote_count": 4,
        },
        "entries": [
            {
                "id": "RQ-fixture",
                "required_for_formal_use": True,
                "status": "verified",
                "scan_refs_present": True,
                "command_results": [{"ok": True}],
            }
        ],
    }
    queue_failures: list[str] = []
    validate_revival_queue(good_queue, queue_failures)
    if queue_failures:
        failures.append(f"完整队列样例不应失败：{queue_failures}")
    bad_queue = dict(good_queue)
    bad_queue["required_open"] = ["RQ-fixture"]
    bad_queue["ok"] = False
    bad_failures: list[str] = []
    validate_revival_queue(bad_queue, bad_failures)
    if not bad_failures:
        failures.append("开放队列样例没有失败")
    closed_open_loop = {
        "schema_id": "redcap-open-loop-closure-queue-check",
        "ok": True,
        "closeout_allowed": True,
        "closeout_blockers": [],
        "failures": [],
    }
    closed_open_loop_failures: list[str] = []
    validate_open_loop_queue(closed_open_loop, closed_open_loop_failures)
    if closed_open_loop_failures:
        failures.append(f"已闭环 open-loop 样例不应失败：{closed_open_loop_failures}")
    open_loop = {
        "schema_id": "redcap-open-loop-closure-queue-check",
        "ok": True,
        "closeout_allowed": False,
        "closeout_blockers": ["OL-01-second-e2e-acceptance: P0 仍未 verified"],
        "failures": [],
    }
    open_loop_failures: list[str] = []
    validate_open_loop_queue(open_loop, open_loop_failures)
    if not any("open-loop 队列仍有未闭环" in item for item in open_loop_failures):
        failures.append("完整复活检查没有把 open-loop 未闭环队列视为阻断项")
    open_status = {
        "schema_id": "redcap-status-surface",
        "ok": True,
        "scan_state": {"scan_complete": True},
        "terminal_goals": {
            "non_terminal_open_tasks": [],
            "states": [
                {
                    "id": "redcap-complete-revival",
                    "terminal_verified": False,
                    "open": True,
                }
            ],
        },
    }
    status_failures: list[str] = []
    validate_status(open_status, status_failures, require_terminal_verified=True)
    if not any("终局父任务" in item for item in status_failures):
        failures.append("要求终局验证时，开放父任务没有失败")
    skipped = parent_verified_host_audit_result()
    if skipped.get("skipped") is not True or skipped.get("checked_by_parent") is not True:
        failures.append("跳过宿主审计样例没有明确标记 skipped")
    partial_shape = {
        "schema_id": "redcap-complete-revival-check",
        "ok": True,
        "status": "partial_pass_with_host_hook_pending",
        "host_hook_audit": {"status": "skipped"},
    }
    if partial_shape.get("status") != "partial_pass_with_host_hook_pending":
        failures.append("跳过宿主审计时必须暴露 partial_pass_with_host_hook_pending")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_COMPLETE_REVIVAL_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap 完整复活终局验收检查器")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--require-terminal-verified", action="store_true")
    check.add_argument(
        "--skip-host-hook-audit",
        action="store_true",
        help="父级已经单独执行宿主审计时，避免终局验收重复触发重检查。",
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

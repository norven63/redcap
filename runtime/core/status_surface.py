#!/usr/bin/env python3
"""RedCap 状态面和 Cap 复活状态面。"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "runtime" / "core"))

import runtime_boundary  # noqa: E402
import scan_conclusion_guard  # noqa: E402
import soul_loader  # noqa: E402
import task_facts  # noqa: E402
import terminal_goal_guard  # noqa: E402


def namespace_from_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        runtime_root=args.runtime_root,
        project_workspace=args.project_workspace,
        cwd=args.cwd,
        task_file=args.task_file,
        task_id=args.task_id or "",
        user_private_root=args.user_private_root,
        project_runtime_root=args.project_runtime_root,
        state_root=args.state_root,
        evidence_root=args.evidence_root,
        require_task_file=False,
    )


def build_status(args: argparse.Namespace, *, load_soul: bool = False, write_soul_evidence: bool = False) -> dict[str, Any]:
    boundary_args = namespace_from_args(args)
    boundary_context = runtime_boundary.build_context(boundary_args)
    boundary_failures = runtime_boundary.validate_context(
        boundary_context,
        require_task_file=args.require_task_file,
    )
    task_facts_path = resolve_task_facts_path(args, boundary_context)
    records = task_facts.read_records(task_facts_path)
    task_summary = task_facts.compute_summary(records)
    facts_by_task = task_facts.latest_by_task(records)
    terminal_contract = terminal_goal_guard.load_json(pathlib.Path(args.terminal_goals).resolve())
    terminal_goal_states = terminal_goal_guard.active_goal_states(terminal_contract, facts_by_task)
    terminal_goal_ids = {
        str(state.get("task_fact_id"))
        for state in terminal_goal_states
        if state.get("domain") != "generic-example"
    }
    non_terminal_open_tasks = [
        item for item in task_summary.get("open_tasks", [])
        if isinstance(item, dict) and str(item.get("task_id") or "") not in terminal_goal_ids
    ]
    scan_state = scan_conclusion_guard.build_scan_state(
        pathlib.Path(args.scan_account).resolve(),
        pathlib.Path(args.scan_merge).resolve(),
        task_facts_path,
    )
    soul_packet = soul_loader.build_packet()
    soul_evidence: dict[str, str] | None = None
    if load_soul and write_soul_evidence:
        soul_evidence = soul_loader.write_evidence(soul_packet, resolve_soul_evidence_dir(args, boundary_context))
    failures = list(boundary_failures)
    if not soul_packet.get("ok"):
        failures.extend(str(item) for item in soul_packet.get("failures", []))
    if non_terminal_open_tasks and args.fail_on_open:
        failures.append(f"仍有非终局父任务开放：{len(non_terminal_open_tasks)}")
    if scan_state.get("scan_complete") is not True and args.require_scan_complete:
        failures.append("360 度旧 RedCap 扫描尚未完成")
    return {
        "schema_id": "redcap-status-surface",
        "ok": not failures,
        "mode": "revive" if load_soul else "status",
        "boundary": boundary_context,
        "soul": {
            "ok": soul_packet.get("ok"),
            "required_loaded": soul_packet.get("required_loaded", []),
            "optional_missing": soul_packet.get("optional_missing", []),
            "activation": soul_packet.get("activation", {}),
            "evidence": soul_evidence,
        },
        "task_summary": task_summary,
        "task_facts_path": str(task_facts_path),
        "terminal_goals": {
            "states": terminal_goal_states,
            "non_terminal_open_tasks": non_terminal_open_tasks,
        },
        "scan_state": scan_state,
        "human_next_step": human_next_step(task_summary, scan_state, soul_packet, boundary_failures, terminal_goal_states),
        "failures": failures,
    }


def resolve_task_facts_path(args: argparse.Namespace, boundary_context: dict[str, Any]) -> pathlib.Path:
    if args.task_facts:
        return pathlib.Path(args.task_facts).resolve()
    return pathlib.Path(boundary_context["evidence_root"]).resolve() / "task-facts" / "task-facts.jsonl"


def resolve_soul_evidence_dir(args: argparse.Namespace, boundary_context: dict[str, Any]) -> pathlib.Path:
    if args.soul_evidence_dir:
        return pathlib.Path(args.soul_evidence_dir).resolve()
    return pathlib.Path(boundary_context["evidence_root"]).resolve() / "soul"


def human_next_step(
    task_summary: dict[str, Any],
    scan_state: dict[str, Any],
    soul_packet: dict[str, Any],
    boundary_failures: list[str],
    terminal_goal_states: list[dict[str, Any]],
) -> str:
    if boundary_failures:
        return "先修运行边界：当前工作区、项目工作区或用户私有状态位置不满足边界规则。"
    if not soul_packet.get("ok"):
        return "先修 Cap 身份加载：必需身份源没有成功加载。"
    if scan_state.get("scan_complete") is not True:
        return "继续 360 度旧 RedCap 扫描，完成分片和合并后再进入最终复活计划。"
    if task_summary.get("open_count", 0) > 0:
        terminal_open = [
            state for state in terminal_goal_states
            if state.get("domain") != "generic-example" and state.get("open") is True
        ]
        if terminal_open:
            titles = "、".join(str(state.get("title")) for state in terminal_open)
            return f"继续推进终局父任务：{titles}；阶段成果不能替代终局验收。"
        return "先处理开放任务事实，避免把未完成事项藏到状态面后面。"
    primary_terminal_states = [
        state for state in terminal_goal_states
        if state.get("domain") != "generic-example"
    ]
    if primary_terminal_states and all(
        state.get("terminal_verified") is True and state.get("open") is False
        for state in primary_terminal_states
    ):
        return "终局目标已按证据验证；后续可继续做静态质量治理或外部项目验收，不需要重复确认完整完成。"
    return "当前基线状态面健康；仍需按终局目标合同确认是否已经完整完成。"


def print_human(status: dict[str, Any]) -> None:
    boundary = status["boundary"]
    task_summary = status["task_summary"]
    scan_state = status["scan_state"]
    soul = status["soul"]
    title = "RedCap 复活状态" if status["mode"] == "status" else "Cap 复活状态"
    print(title)
    print(f"整体状态：{'可继续' if status['ok'] else '需要处理'}")
    print(f"工作模式：{boundary.get('boundary_mode')}")
    print(f"运行时根目录：{boundary.get('runtime_root')}")
    print(f"项目工作区：{boundary.get('project_workspace')}")
    print(f"项目运行目录：{boundary.get('project_runtime_root')}")
    print(f"任务文件：{boundary.get('task_file')}（存在：{boundary.get('task_file_exists')}）")
    print(f"Cap 身份：{'已加载' if soul.get('ok') else '未加载'}")
    print(f"开放任务：{task_summary.get('open_count', 0)}")
    terminal_open = [
        state for state in status.get("terminal_goals", {}).get("states", [])
        if state.get("domain") != "generic-example" and state.get("open") is True
    ]
    if terminal_open:
        print("终局父任务：仍开放")
        for state in terminal_open:
            print(f"- {state.get('title')}：{state.get('open_reason')}")
    print(
        "360 扫描："
        f"{scan_state.get('scan_status')}，"
        f"{scan_state.get('shards_completed')}/{scan_state.get('shards_total')}，"
        f"{scan_state.get('merge_status')}"
    )
    print(f"下一步：{status.get('human_next_step')}")
    if status["failures"]:
        print("需要处理：")
        for failure in status["failures"]:
            print(f"- {failure}")


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--runtime-root")
    parser.add_argument("--project-workspace")
    parser.add_argument("--cwd")
    parser.add_argument("--task-file")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--user-private-root")
    parser.add_argument("--project-runtime-root")
    parser.add_argument("--state-root")
    parser.add_argument("--evidence-root")
    parser.add_argument("--task-facts")
    parser.add_argument("--terminal-goals", default=str(terminal_goal_guard.DEFAULT_CONTRACT))
    parser.add_argument("--scan-account", default=str(scan_conclusion_guard.DEFAULT_ACCOUNT))
    parser.add_argument("--scan-merge", default=str(scan_conclusion_guard.DEFAULT_MERGE))
    parser.add_argument("--soul-evidence-dir")
    parser.add_argument("--require-task-file", action="store_true")
    parser.add_argument("--require-scan-complete", action="store_true")
    parser.add_argument("--fail-on-open", action="store_true")
    parser.add_argument("--json", action="store_true")


def cmd_status(args: argparse.Namespace) -> int:
    status = build_status(args, load_soul=False, write_soul_evidence=False)
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print_human(status)
    if status["ok"]:
        print("REDCAP_STATUS_OK")
        return 0
    return 1


def cmd_revive(args: argparse.Namespace) -> int:
    status = build_status(args, load_soul=True, write_soul_evidence=not args.no_write_evidence)
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print_human(status)
    if status["ok"]:
        print("REDCAP_REVIVE_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    args = argparse.Namespace(
        runtime_root=str(REPO_ROOT),
        project_workspace=str(REPO_ROOT),
        cwd=str(REPO_ROOT),
        task_file=None,
        task_id="",
        user_private_root=None,
        project_runtime_root=None,
        state_root=None,
        evidence_root=None,
        task_facts=str(task_facts.DEFAULT_LEDGER),
        terminal_goals=str(terminal_goal_guard.DEFAULT_CONTRACT),
        scan_account=str(scan_conclusion_guard.DEFAULT_ACCOUNT),
        scan_merge=str(scan_conclusion_guard.DEFAULT_MERGE),
        soul_evidence_dir=str(soul_loader.DEFAULT_EVIDENCE_DIR),
        require_task_file=False,
        require_scan_complete=False,
        fail_on_open=False,
        no_write_evidence=True,
        json=True,
    )
    status = build_status(args, load_soul=False, write_soul_evidence=False)
    if status.get("schema_id") != "redcap-status-surface":
        failures.append("状态面 schema_id 错误")
    if "boundary" not in status or "task_summary" not in status or "scan_state" not in status:
        failures.append("状态面缺少核心字段")
    next_step = str(status.get("human_next_step") or "")
    terminal_states = [
        state for state in status.get("terminal_goals", {}).get("states", [])
        if state.get("domain") != "generic-example"
    ]
    if terminal_states and all(state.get("terminal_verified") is True and state.get("open") is False for state in terminal_states):
        if "仍需按终局目标合同确认是否已经完整完成" in next_step:
            failures.append("终局已验证时不应继续提示确认完整完成")
    revived = build_status(args, load_soul=True, write_soul_evidence=False)
    if revived.get("mode") != "revive":
        failures.append("复活模式没有进入 revive 状态")
    if revived.get("soul", {}).get("evidence") is not None:
        failures.append("no_write_evidence 自检仍写入了证据路径")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_STATUS_SURFACE_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap 状态面和 Cap 复活状态面")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status")
    add_common(status)
    status.set_defaults(func=cmd_status)

    revive = sub.add_parser("revive")
    add_common(revive)
    revive.add_argument("--no-write-evidence", action="store_true")
    revive.set_defaults(func=cmd_revive)

    self_check = sub.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

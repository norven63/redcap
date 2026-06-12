#!/usr/bin/env python3
"""检查 RedCap 已知遗留问题执行顺序合同。"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = REPO_ROOT / "assets" / "contracts" / "known-issues-execution-order.json"
EXPECTED_SCHEMA_ID = "redcap-known-issues-execution-order"
EXPECTED_TERMINAL_ID = "redcap-complete-revival"
EXPECTED_SEQUENCE = [
    "KI-00-lifecycle-and-prism-front-gate",
    "KI-01-structured-known-issue-queue",
    "KI-02-runtime-boundary-consumer-migration",
    "KI-03-legacy-evidence-policy",
    "KI-04-complete-revival-e2e-harness",
    "KI-05-terminal-closeout-only-after-evidence",
]


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(json.dumps({
            "ok": False,
            "failures": [f"无法读取执行顺序合同：{path}: {exc}"],
        }, ensure_ascii=False, indent=2)) from exc
    if not isinstance(payload, dict):
        raise SystemExit(json.dumps({
            "ok": False,
            "failures": [f"执行顺序合同必须是 JSON 对象：{path}"],
        }, ensure_ascii=False, indent=2))
    return payload


def non_empty_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def validate_contract(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if payload.get("schema_id") != EXPECTED_SCHEMA_ID:
        failures.append("schema_id 不匹配")
    status = payload.get("status")
    if status not in {"planned", "in_progress", "verified"}:
        failures.append("执行顺序合同状态必须是 planned、in_progress 或 verified")

    terminal_goal = payload.get("terminal_goal")
    if not isinstance(terminal_goal, dict):
        failures.append("缺少 terminal_goal")
    else:
        if terminal_goal.get("id") != EXPECTED_TERMINAL_ID:
            failures.append("terminal_goal.id 必须指向 RedCap 终局父任务")
        terminal_state = terminal_goal.get("state")
        if terminal_state not in {"open", "closed"}:
            failures.append("terminal_goal.state 必须是 open 或 closed")
        if terminal_state == "closed" and status != "verified":
            failures.append("只有执行顺序合同已验证后，才允许标记终局父任务 closed")
        if terminal_state == "open" and status == "verified":
            failures.append("执行顺序合同已验证时，终局父任务状态必须同步为 closed")

    if not non_empty_string_list(payload.get("ordering_principles")):
        failures.append("ordering_principles 必须是非空字符串列表")
    if not non_empty_string_list(payload.get("stop_conditions")):
        failures.append("stop_conditions 必须是非空字符串列表")
    if not isinstance(payload.get("next_executable_step"), str) or not payload["next_executable_step"].strip():
        failures.append("next_executable_step 必须说明下一步")

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        failures.append("items 必须是非空列表")
        return failures

    seen: set[str] = set()
    sequence: list[str] = []
    order_values: list[int] = []
    by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            failures.append(f"items[{index}] 必须是对象")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            failures.append(f"items[{index}].id 必须是非空字符串")
            continue
        if item_id in seen:
            failures.append(f"重复的遗留项 id：{item_id}")
        seen.add(item_id)
        sequence.append(item_id)
        by_id[item_id] = item
        order = item.get("order")
        if not isinstance(order, int):
            failures.append(f"{item_id}.order 必须是整数")
        else:
            order_values.append(order)
        for key in ["title", "acceptance"]:
            if key == "title" and not (isinstance(item.get(key), str) and item[key].strip()):
                failures.append(f"{item_id}.title 必须是非空字符串")
            if key == "acceptance" and not non_empty_string_list(item.get(key)):
                failures.append(f"{item_id}.acceptance 必须是非空字符串列表")
        depends_on = item.get("depends_on")
        if not isinstance(depends_on, list) or not all(isinstance(dep, str) and dep.strip() for dep in depends_on):
            failures.append(f"{item_id}.depends_on 必须是字符串列表")
            continue
        for dependency in depends_on:
            if dependency not in seen:
                failures.append(f"{item_id} 依赖尚未排在前面的项：{dependency}")

    if sequence != EXPECTED_SEQUENCE:
        failures.append("遗留项顺序不符合当前约定队列")
    if sorted(order_values) != list(range(len(EXPECTED_SEQUENCE))):
        failures.append("order 必须从 0 连续排列到终局关闭项")

    terminal_item = by_id.get("KI-05-terminal-closeout-only-after-evidence")
    if isinstance(terminal_item, dict):
        terminal_dependencies = set(terminal_item.get("depends_on", []))
        missing = sorted(set(EXPECTED_SEQUENCE[:-1]) - terminal_dependencies)
        if missing:
            failures.append(f"终局关闭项必须依赖所有前置项：{', '.join(missing)}")
        acceptance_text = "\n".join(str(item) for item in terminal_item.get("acceptance", []))
        if "15 项优秀设计覆盖矩阵" not in acceptance_text:
            failures.append("终局关闭验收必须包含 15 项优秀设计覆盖矩阵")
        if "任何阶段成果都不能单独关闭 RedCap 完整复活父任务" not in acceptance_text:
            failures.append("终局关闭验收必须禁止阶段成果替代父任务")

    return failures


def check_contract(path: pathlib.Path) -> dict[str, Any]:
    payload = load_json(path)
    failures = validate_contract(payload)
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    return {
        "schema_id": "redcap-known-issues-execution-order-check",
        "ok": not failures,
        "contract": str(path),
        "terminal_goal_state": payload.get("terminal_goal", {}).get("state") if isinstance(payload.get("terminal_goal"), dict) else None,
        "item_count": len(items),
        "ordered_ids": [item.get("id") for item in items if isinstance(item, dict)],
        "failures": failures,
    }


def cmd_check(args: argparse.Namespace) -> int:
    result = check_contract(pathlib.Path(args.contract).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_KNOWN_ISSUES_ORDER_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    payload = {
        "schema_id": EXPECTED_SCHEMA_ID,
        "status": "planned",
        "terminal_goal": {"id": EXPECTED_TERMINAL_ID, "state": "open"},
        "ordering_principles": ["先固定队列，再处理后续实现。"],
        "stop_conditions": ["出现无法安全处理的阻塞条件。"],
        "next_executable_step": "先执行 KI-00 和 KI-01。",
        "items": [
            {
                "order": index,
                "id": item_id,
                "title": f"fixture {index}",
                "depends_on": EXPECTED_SEQUENCE[:index] if item_id.endswith("terminal-closeout-only-after-evidence") else EXPECTED_SEQUENCE[max(0, index - 1):index],
                "acceptance": (
                    [
                        "端到端验收通过且证据可审查。",
                        "15 项优秀设计覆盖矩阵逐项有证据命中。",
                        "任何阶段成果都不能单独关闭 RedCap 完整复活父任务。",
                    ]
                    if item_id.endswith("terminal-closeout-only-after-evidence")
                    else ["验收条件存在。"]
                ),
            }
            for index, item_id in enumerate(EXPECTED_SEQUENCE)
        ],
    }
    failures = validate_contract(payload)
    closed_verified = json.loads(json.dumps(payload, ensure_ascii=False))
    closed_verified["status"] = "verified"
    closed_verified["terminal_goal"]["state"] = "closed"
    failures.extend(validate_contract(closed_verified))
    closed = json.loads(json.dumps(payload, ensure_ascii=False))
    closed["terminal_goal"]["state"] = "closed"
    closed_failures = validate_contract(closed)
    if failures:
        print(json.dumps({"ok": False, "failures": failures}, ensure_ascii=False, indent=2))
        return 1
    if not any("才允许标记终局父任务 closed" in failure for failure in closed_failures):
        print(json.dumps({"ok": False, "failures": ["未能拦截未验证合同关闭终局"]}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, "fixture_items": len(EXPECTED_SEQUENCE)}, ensure_ascii=False, indent=2))
    print("REDCAP_KNOWN_ISSUES_ORDER_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查 RedCap 已知遗留问题执行顺序合同")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check")
    check.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    check.set_defaults(func=cmd_check)

    self_check = subparsers.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

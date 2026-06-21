#!/usr/bin/env python3
"""检查 RedCap 已知遗留问题状态队列。"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_QUEUE = REPO_ROOT / "assets" / "contracts" / "known-issues-queue.json"
EXPECTED_IDS = [
    "KI-00-lifecycle-and-prism-front-gate",
    "KI-01-structured-known-issue-queue",
    "KI-02-runtime-boundary-consumer-migration",
    "KI-03-legacy-evidence-policy",
    "KI-04-complete-revival-e2e-harness",
    "KI-05-terminal-closeout-only-after-evidence",
]
ALLOWED_STATUSES = {"planned", "in_progress", "verified", "blocked", "deferred_user_supervised"}


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(json.dumps({"ok": False, "failures": [f"无法读取已知问题队列：{exc}"]}, ensure_ascii=False, indent=2)) from exc
    if not isinstance(payload, dict):
        raise SystemExit(json.dumps({"ok": False, "failures": ["已知问题队列必须是 JSON 对象"]}, ensure_ascii=False, indent=2))
    return payload


def non_empty_strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def evidence_exists(item_id: str, evidence: list[str], failures: list[str]) -> None:
    for entry in evidence:
        if entry.startswith("runtime/bin/redcap ") or entry.startswith("python3 "):
            continue
        path = (REPO_ROOT / entry).resolve()
        if not path.exists():
            failures.append(f"{item_id} 证据路径不存在：{entry}")


def validate_queue(payload: dict[str, Any], *, require_1_to_4_verified: bool) -> list[str]:
    failures: list[str] = []
    if payload.get("schema_id") != "redcap-known-issues-queue":
        failures.append("schema_id 不匹配")
    terminal_goal = payload.get("terminal_goal")
    if not isinstance(terminal_goal, dict):
        failures.append("缺少 terminal_goal")
    else:
        if terminal_goal.get("id") != "redcap-complete-revival":
            failures.append("terminal_goal.id 必须是 redcap-complete-revival")
        if terminal_goal.get("state") not in {"open", "closed"}:
            failures.append("terminal_goal.state 必须是 open 或 closed")
    terminal_closed = isinstance(terminal_goal, dict) and terminal_goal.get("state") == "closed"
    items = payload.get("items")
    if not isinstance(items, list) or len(items) != len(EXPECTED_IDS):
        failures.append("items 数量必须正好覆盖 1-6 项")
        return failures
    ordered_ids: list[str] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            failures.append(f"第 {index} 项必须是对象")
            continue
        item_id = str(item.get("id") or "")
        ordered_ids.append(item_id)
        if item.get("number") != index:
            failures.append(f"{item_id or index} number 必须是 {index}")
        if item_id != EXPECTED_IDS[index - 1]:
            failures.append(f"第 {index} 项 id 顺序错误：{item_id}")
        if item.get("status") not in ALLOWED_STATUSES:
            failures.append(f"{item_id} 状态非法：{item.get('status')}")
        if not isinstance(item.get("title"), str) or not item["title"].strip():
            failures.append(f"{item_id} title 不能为空")
        evidence = item.get("evidence")
        if not non_empty_strings(evidence):
            failures.append(f"{item_id} evidence 必须是非空字符串列表")
        else:
            evidence_exists(item_id, evidence, failures)
        if ((index <= 4 and require_1_to_4_verified) or terminal_closed) and item.get("status") != "verified":
            failures.append(f"第 {index} 项必须已验证：{item_id}")
        if index >= 5:
            if terminal_closed:
                if item.get("status") != "verified":
                    failures.append(f"终局关闭时第 {index} 项必须已验证：{item_id}")
            elif item.get("status") == "deferred_user_supervised":
                if not isinstance(item.get("deferred_until"), str) or "Norven" not in item["deferred_until"]:
                    failures.append(f"{item_id} 暂缓时必须写明由 Norven 督导后再开展")
    if ordered_ids != EXPECTED_IDS:
        failures.append("队列顺序不符合遗留问题执行顺序合同")
    return failures


def cmd_check(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.queue).resolve()
    payload = load_json(path)
    failures = validate_queue(payload, require_1_to_4_verified=args.require_1_4_verified)
    result = {
        "schema_id": "redcap-known-issues-queue-check",
        "ok": not failures,
        "queue": str(path),
        "require_1_4_verified": args.require_1_4_verified,
        "statuses": {
            str(item.get("id")): item.get("status")
            for item in payload.get("items", [])
            if isinstance(item, dict)
        },
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_KNOWN_ISSUES_QUEUE_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    fixture = {
        "schema_id": "redcap-known-issues-queue",
        "status": "fixture",
        "terminal_goal": {"id": "redcap-complete-revival", "state": "open"},
        "items": [
            {
                "number": index,
                "id": item_id,
                "title": f"fixture {index}",
                "status": "verified" if index <= 4 else "deferred_user_supervised",
                "deferred_until": "Norven 督导后再开展" if index >= 5 else None,
                "evidence": ["runtime/core/known_issues_queue.py"],
            }
            for index, item_id in enumerate(EXPECTED_IDS, start=1)
        ],
    }
    failures = validate_queue(fixture, require_1_to_4_verified=True)
    closed = json.loads(json.dumps(fixture, ensure_ascii=False))
    closed["terminal_goal"]["state"] = "closed"
    for item in closed["items"]:
        item["status"] = "verified"
        item.pop("deferred_until", None)
    failures.extend(validate_queue(closed, require_1_to_4_verified=True))
    open_verified = json.loads(json.dumps(fixture, ensure_ascii=False))
    for item in open_verified["items"]:
        item["status"] = "verified"
        item.pop("deferred_until", None)
    failures.extend(validate_queue(open_verified, require_1_to_4_verified=True))
    bad_deferred = json.loads(json.dumps(fixture, ensure_ascii=False))
    bad_deferred["items"][4].pop("deferred_until", None)
    bad_deferred_failures = validate_queue(bad_deferred, require_1_to_4_verified=True)
    if not any("暂缓时必须写明" in failure for failure in bad_deferred_failures):
        failures.append("未能拦截第 5 项暂缓但缺少 Norven 督导说明")
    bad_closed = json.loads(json.dumps(fixture, ensure_ascii=False))
    bad_closed["terminal_goal"]["state"] = "closed"
    bad_closed_failures = validate_queue(bad_closed, require_1_to_4_verified=True)
    if not any("终局关闭时第 5 项必须已验证" in failure for failure in bad_closed_failures):
        failures.append("未能拦截第 5 项未验证却关闭终局")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_KNOWN_ISSUES_QUEUE_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查 RedCap 已知遗留问题状态队列")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--queue", default=str(DEFAULT_QUEUE))
    check.add_argument("--require-1-4-verified", action="store_true")
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

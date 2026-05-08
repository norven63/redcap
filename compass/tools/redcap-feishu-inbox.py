#!/usr/bin/env python3
# 用途：运行时与收尾脚本；飞书回复收件箱的安全入口、状态摘要和策略校验。
# Dictionary: references/file-lookup-dictionary.md#runtime-and-closeout

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REDCAP_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REDCAP_ROOT / "references/feishu-inbox-policy.json"
HUMAN_POLICY_PATH = REDCAP_ROOT / "references/human-communication-policy.json"
NOTIFIER_PATH = REDCAP_ROOT / "compass/tools/feishu-notifier.py"
STATE_DIR = Path(os.environ.get("REDCAP_FEISHU_STATE_DIR", REDCAP_ROOT / "compass/.workflow/feishu"))
PENDING_ITEMS_PATH = STATE_DIR / "pending-items.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-feishu-inbox] {message}")


def load_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        if default is not None:
            return default
        fail(f"missing json: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid json {path}: {exc}")


def load_policy() -> dict[str, Any]:
    policy = load_json(POLICY_PATH)
    if not isinstance(policy, dict):
        fail("policy must be a json object")
    return policy


def load_items() -> list[dict[str, Any]]:
    raw = load_json(PENDING_ITEMS_PATH, default=[])
    if not isinstance(raw, list):
        fail("pending-items.json must be a json array")
    items: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            fail(f"pending item #{index} must be a json object")
        items.append(item)
    return items


def classify_text(text: str) -> str:
    normalized = text.strip().lower()
    if any(word in normalized for word in ["继续", "下一步", "开始", "可以往下", "go on", "continue"]):
        return "continue-request"
    if any(word in normalized for word in ["问题", "不对", "重新评审", "review", "纠正", "再次评审"]):
        return "review-request"
    if any(word in normalized for word in ["新增", "追加", "需求", "请把", "希望", "加一条"]):
        return "change-request"
    return "unknown"


def trim(value: str, limit: int = 80) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "redcap-feishu-inbox-safe-ingress":
        fail("unexpected policy_id")
    if policy.get("mode") != "safe-ingress-inbox":
        fail("mode must be safe-ingress-inbox")
    for phrase in [
        "soft pending-scan",
        "current-status only reads",
        "does not execute",
        "change-intake",
        "manual-decision",
        "closeout receipt",
    ]:
        joined = json.dumps(policy, ensure_ascii=False)
        if phrase not in joined:
            fail(f"policy missing required boundary phrase: {phrase}")
    allowed_statuses = set(policy.get("allowed_statuses") or [])
    if allowed_statuses != {"open", "promoted", "dismissed"}:
        fail("allowed_statuses must be open/promoted/dismissed")
    capture_sources = set(policy.get("capture_sources") or [])
    legacy_sources = set(policy.get("legacy_capture_sources") or [])
    if not {"history-scan", "queued-window"}.issubset(capture_sources):
        fail("capture_sources must include history-scan and queued-window")
    legacy_rule = str(policy.get("legacy_source_rule", ""))
    if legacy_sources and not any(word in legacy_rule for word in ["legacy", "historical"]):
        fail("legacy_capture_sources must be explained by legacy_source_rule")


def validate_source_boundaries(policy: dict[str, Any]) -> None:
    notifier = NOTIFIER_PATH.read_text(encoding="utf-8", errors="replace")
    required = [
        "pending-scan",
        "pending-count",
        "pending-list",
        "pending-dismiss",
        "pending-promote",
        "_enqueue_pending",
    ]
    for phrase in required:
        if phrase not in notifier:
            fail(f"feishu-notifier.py missing inbox primitive: {phrase}")
    if 'window.get("reply_action") == "queue"' not in notifier:
        fail("queued window replies must be stored instead of executed")
    if "def pending_promote" not in notifier or 'self._mark_pending(item_id, "promoted")' not in notifier:
        fail("pending_promote must only mark state")

    human_policy = load_json(HUMAN_POLICY_PATH)
    reply_rule = str((human_policy or {}).get("feishu_reply_command_boundary_rule", ""))
    for phrase in ["outbound-only", "pending-scan", "RedCap inbox", "safe ingress", "does not auto execute", "change-intake"]:
        if phrase not in reply_rule:
            fail(f"human communication policy missing Feishu inbox boundary: {phrase}")


def validate_items(policy: dict[str, Any], items: list[dict[str, Any]]) -> None:
    allowed_statuses = set(policy.get("allowed_statuses") or [])
    allowed_sources = set(policy.get("capture_sources") or []) | set(policy.get("legacy_capture_sources") or [])
    for item in items:
        item_id = str(item.get("id") or "")
        if not item_id:
            fail("pending item missing id")
        status = str(item.get("status") or "")
        if status not in allowed_statuses:
            fail(f"pending item {item_id} has invalid status: {status}")
        source = str(item.get("source") or "")
        if source and source not in allowed_sources:
            fail(f"pending item {item_id} has invalid source: {source}")
        if status == "open":
            content = str(item.get("content") or "")
            if not content.strip():
                fail(f"open pending item {item_id} must keep content for triage")
            if not str(item.get("summary") or "").strip():
                fail(f"open pending item {item_id} must keep summary for human surface")


def open_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [item for item in items if item.get("status") == "open"],
        key=lambda item: str(item.get("captured_at") or ""),
        reverse=True,
    )


def command_summary(args: argparse.Namespace) -> int:
    items = load_items()
    open_rows = open_items(items)
    counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1

    if args.human:
        print(f"open_items: {len(open_rows)}")
        print("rule: 飞书回复只进入安全收件箱，不会自动执行；需要进入中插需求、人工决策或当前任务合并后才继续。")
        if not open_rows:
            print("latest_open: none")
            return 0
        for item in open_rows[: args.limit]:
            content = str(item.get("content") or item.get("summary") or "")
            print(
                f"item: {item.get('id')} | {classify_text(content)} | "
                f"{item.get('captured_at', 'unknown')} | {trim(content)}"
            )
        return 0

    print("FEISHU_INBOX")
    print(f"state_path={PENDING_ITEMS_PATH}")
    print(f"open={len(open_rows)} total={len(items)}")
    print("statuses=" + ",".join(f"{key}:{counts[key]}" for key in sorted(counts)))
    if open_rows:
        first = open_rows[0]
        content = str(first.get("content") or first.get("summary") or "")
        print(f"latest_open={first.get('id')} classification={classify_text(content)} summary={trim(content)}")
    else:
        print("latest_open=none")
    return 0


def command_check(_: argparse.Namespace) -> int:
    policy = load_policy()
    validate_policy(policy)
    validate_source_boundaries(policy)
    validate_items(policy, load_items())
    print("FEISHU_INBOX_OK")
    return 0


def command_scan(args: argparse.Namespace) -> int:
    command = [sys.executable, str(NOTIFIER_PATH), "pending-scan"]
    try:
        proc = subprocess.run(
            command,
            cwd=REDCAP_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=args.timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(f"scan_status=timeout timeout_seconds={args.timeout}")
        return 0 if args.soft else 1
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        print("scan_status=failed")
        if detail:
            print(f"detail={detail[0]}")
        return 0 if args.soft else proc.returncode
    print(f"scan_status=ok added={(proc.stdout or '').strip() or '0'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap Feishu safe inbox")
    sub = parser.add_subparsers(dest="command", required=True)

    summary = sub.add_parser("summary", help="Print stored Feishu inbox summary without network scan")
    summary.add_argument("--human", action="store_true", help="Print human-readable summary")
    summary.add_argument("--limit", type=int, default=3)
    summary.set_defaults(func=command_summary)

    check = sub.add_parser("check", help="Validate Feishu inbox policy and stored state")
    check.set_defaults(func=command_check)

    scan = sub.add_parser("scan", help="Soft-refresh inbox using feishu-notifier.py pending-scan")
    scan.add_argument("--soft", action="store_true", help="Do not fail install/revive when Feishu is unavailable")
    scan.add_argument("--timeout", type=int, default=15)
    scan.set_defaults(func=command_scan)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

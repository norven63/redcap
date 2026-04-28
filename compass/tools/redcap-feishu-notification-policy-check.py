#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REDCAP_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REDCAP_ROOT / "references" / "feishu-notification-policy.json"
CONFIG_PATH = REDCAP_ROOT / "compass" / "tools" / "feishu-config.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-feishu-notification-policy-check] {message}")


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing json: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid json {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"json must be object: {path}")
    return payload


def text(path: str) -> str:
    full = REDCAP_ROOT / path
    if not full.is_file():
        fail(f"missing file: {path}")
    return full.read_text(encoding="utf-8", errors="replace")


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("required_lark_cli_profile") != "cli_a9579f5b12219bb5":
        fail("required_lark_cli_profile must be cli_a9579f5b12219bb5")
    if policy.get("allowed_transport") != "lark_cli_dm":
        fail("allowed_transport must be lark_cli_dm")
    if "webhook" not in set(policy.get("disallowed_transports") or []):
        fail("webhook must be listed as disallowed")
    if set(policy.get("allowed_notify_window_types") or []) != {"node-report", "manual-intervention"}:
        fail("allowed notify window types must be node-report/manual-intervention")
    if "ledger-only by default" not in str(policy.get("internal_audit_gap_rule", "")):
        fail("policy must declare SessionEnd / Stop audit gaps ledger-only by default")


def validate_source(policy: dict[str, Any]) -> None:
    notifier = text("compass/tools/feishu-notifier.py")
    on_complete = text("compass/tools/redcap-on-complete.sh")
    session_end = text("compass/tools/redcap-layerB-session-end.sh")
    explore_notes = text("compass/tools/redcap-explore-notes-check.sh")
    legacy_claude_stop = text("compass/tools/redcap-claude-hook-stop.sh")
    notify_format = text("compass/tools/redcap-notify-format.sh")

    for forbidden in ["urllib.request", "urlopen", "_send_webhook_text", "transport == \"webhook\"", "transport=webhook"]:
        if forbidden in notifier:
            fail(f"notifier still exposes forbidden webhook implementation pattern: {forbidden}")

    if "--window-type followup" in on_complete or "--window-type followup" in session_end:
        fail("repo-owned closeout path must not send followup notifications")
    if "--window-type node-report" not in on_complete:
        fail("on-complete must send exactly a node-report notification")
    if re.search(r'SKIP_SUCCESS_NOTIFY="\$\{REDCAP_SKIP_SESSION_END_SUCCESS_NOTIFY:-0\}"', session_end):
        fail("session-end success notification must be disabled by default")
    if 'AUDIT_GAP_NOTIFY="${REDCAP_SESSION_END_NOTIFY_AUDIT_GAP:-0}"' not in session_end:
        fail("session-end audit-gap notification must be disabled by default")
    if "session_end_audit_gap_notify_enabled" not in session_end:
        fail("session-end audit-gap notification must be explicitly guarded")
    if 'send_notification "$ALERT_BODY";' in session_end or 'send_notification "$FINAL_ALERT_BODY";' in session_end:
        fail("session-end audit-gap notifications must not be sent without a manual-intervention guard")
    if 'local window_type="${2:-manual-intervention}"' not in session_end:
        fail("session-end blocker alerts must default to manual-intervention")
    if "python3 \"$NOTIFIER\" notify" in explore_notes:
        fail("explore-notes reminder must not send Feishu; it is not a node-report or manual intervention interrupt")
    if "python3 \"$NOTIFIER\" notify" in legacy_claude_stop or "探索笔记提醒" in legacy_claude_stop:
        fail("legacy Claude Stop hook must not send Feishu notifications")
    if "notification-muted legacy hook" not in legacy_claude_stop:
        fail("legacy Claude Stop hook must declare notification-muted behavior")
    for field in ["人工协助", "阻塞状态", "下一步可直接开始", "任务全景图", "当前位置"]:
        if field not in notify_format:
            fail(f"notify formatter missing human status field: {field}")

    parser_line = re.search(r"--window-type\".*?choices=\[(.*?)\]", notifier, flags=re.S)
    if parser_line:
        choices = parser_line.group(1)
        if "followup" in choices or "none" in choices:
            fail("notifier parser must not allow followup/none window types")


def validate_local_config(policy: dict[str, Any]) -> None:
    if not CONFIG_PATH.exists():
        return
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid local feishu config json: {exc}")
    if not isinstance(raw, dict) or not raw.get("notify_enabled", False):
        return
    required = policy["required_lark_cli_profile"]
    if raw.get("transport", "lark_cli_dm") != "lark_cli_dm":
        fail("local feishu-config transport must be lark_cli_dm")
    if raw.get("app_id") not in (None, "", required):
        fail("local feishu-config app_id does not match required profile")
    if raw.get("lark_cli_profile") != required:
        fail("local feishu-config lark_cli_profile does not match required profile")
    if raw.get("webhook"):
        fail("local feishu-config must not retain a webhook value")


def main() -> int:
    policy = read_json(POLICY_PATH)
    validate_policy(policy)
    validate_source(policy)
    validate_local_config(policy)
    print("FEISHU_NOTIFICATION_POLICY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

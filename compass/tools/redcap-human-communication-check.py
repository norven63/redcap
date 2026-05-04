#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


REDCAP_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REDCAP_ROOT / "references" / "human-communication-policy.json"
REQUIRED_FIELDS = [
    "人工协助",
    "阻塞状态",
    "下一步可直接开始",
    "任务全景图",
    "当前位置",
    "当前已完成",
    "上一步完成的是",
    "下一步计划做的是",
]


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-human-communication-check] {message}")


def read(path: str) -> str:
    target = REDCAP_ROOT / path
    if not target.is_file():
        fail(f"missing file: {path}")
    return target.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing json: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid json: {exc}")
    if not isinstance(payload, dict):
        fail("policy must be a json object")
    return payload


def require_all(text: str, label: str) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in text]
    if missing:
        fail(f"{label} missing required fields: {', '.join(missing)}")


def render_status_sample() -> str:
    result = subprocess.run(
        [
            "bash",
            "compass/tools/redcap-status-report-format.sh",
            "--manual",
            "不需要",
            "--blocked",
            "无",
            "--next-start",
            "是",
            "--panorama",
            "立项 -> 实现 -> 验收 -> closeout",
            "--position",
            "实现中",
            "--done",
            "已完成策略设计",
            "--previous",
            "已完成 PM Gate",
            "--next",
            "继续实现检查器",
            "--validation",
            "待 acceptance",
        ],
        cwd=REDCAP_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        fail("status formatter failed: " + result.stderr.strip())
    return result.stdout


def render_notify_sample() -> str:
    script = r'''
source compass/tools/redcap-notify-format.sh
redcap_build_completion_message \
  "RedCap 节点汇报" \
  "redcap" \
  "abc1234 feat(example): sample" \
  "acceptance" \
  "" \
  "$PWD"
'''
    result = subprocess.run(
        ["bash", "-lc", script],
        cwd=REDCAP_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        fail("notify formatter failed: " + result.stderr.strip())
    return result.stdout


def main() -> int:
    policy = load_json(POLICY_PATH)
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "redcap-human-communication-surface":
        fail("unexpected policy_id")
    if policy.get("required_status_fields") != REQUIRED_FIELDS:
        fail("required_status_fields drifted from the canonical status surface")
    narrative_rule = str(policy.get("narrative_quality_rule", ""))
    for phrase in ["problem being solved", "chosen solution", "resulting effect", "not make the primary explanation a changelog"]:
        if phrase not in narrative_rule:
            fail(f"narrative_quality_rule missing phrase: {phrase}")
    report_rule = str(policy.get("report_led_summary_rule", ""))
    for phrase in ["0.1-0.4", "人工审核", "人工验证", "technical file/script details"]:
        if phrase not in report_rule:
            fail(f"report_led_summary_rule missing phrase: {phrase}")
    if set(policy.get("allowed_feishu_events") or []) != {"node-report", "manual-intervention"}:
        fail("allowed_feishu_events must be node-report/manual-intervention")

    require_all(render_status_sample(), "status formatter")
    require_all(render_notify_sample(), "notify formatter")

    session_end = read("compass/tools/redcap-layerB-session-end.sh")
    if 'AUDIT_GAP_NOTIFY="${REDCAP_SESSION_END_NOTIFY_AUDIT_GAP:-0}"' not in session_end:
        fail("SessionEnd audit-gap Feishu notification must be disabled by default")
    if "session_end_audit_gap_notify_enabled" not in session_end:
        fail("SessionEnd must explicitly guard audit-gap Feishu sends")
    if "internal audit gap is ledger-only by default" not in session_end:
        fail("SessionEnd must document that internal audit gaps are ledger-only by default")

    legacy_hook = read("compass/tools/redcap-claude-hook-stop.sh")
    if 'python3 "$NOTIFIER" notify' in legacy_hook or "探索笔记提醒" in legacy_hook:
        fail("legacy Claude Stop hook must not send Feishu notifications")
    if "notification-muted legacy hook" not in legacy_hook:
        fail("legacy Claude Stop hook must explicitly declare notification-muted behavior")

    print("HUMAN_COMMUNICATION_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

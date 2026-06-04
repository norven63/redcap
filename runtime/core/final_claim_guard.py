#!/usr/bin/env python3
"""Reject final completion claims that lack task-body completion evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_EVENTS = REPO_ROOT / "assets" / "evidence" / "host-hooks" / "codex" / "events.jsonl"
DEFAULT_COMPLETION_MARKER = REPO_ROOT / "assets" / "evidence" / "lifecycle" / "latest-completion.json"
TASK_BODY_EVIDENCE_KINDS = {"code", "code-and-review", "runtime-change", "runtime_change", "test", "migration"}
COMPLETION_TERMS = [
    "一切正常",
    "已完成",
    "已处理",
    "已应用",
    "已生效",
    "执行完",
    "做完",
    "完成了",
    "完毕",
    "收口",
    "可以开始",
    "准备好了",
    "已就绪",
    "搞定了",
    "弄好了",
    "结项了",
    "交付了",
    "验收通过",
    "运行正常",
    "正常运行",
    "功能完备",
    "问题解决",
    "不再有",
    "ready",
    "all set",
    "good to go",
    "production-ready",
    "stable",
    "deployed",
    "accomplished",
    "resolved",
    "fixed",
    "wrapped up",
    "closing out",
    "complete",
    "completed",
    "done",
    "finished",
    "goal achieved",
]


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def load_events(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def completion_claim_detected(message: str) -> bool:
    lowered = message.casefold()
    if any(term in lowered for term in COMPLETION_TERMS):
        return True
    return bool(re.search(r"\b(all|checks?|tests?|verification)\s+(passed|green|clear|ok|successful|complete)\b", lowered))


def latest_prompt(events: list[dict[str, Any]], session_id: str | None, turn_id: str | None) -> dict[str, Any] | None:
    prompts = [
        event for event in events
        if event.get("event") == "UserPromptSubmit"
        and (session_id is None or event.get("session_id") == session_id)
        and (turn_id is None or event.get("turn_id") == turn_id)
    ]
    return prompts[-1] if prompts else None


def check_final_claim(
    *,
    message: str,
    events_path: pathlib.Path,
    completion_marker_path: pathlib.Path,
    session_id: str | None,
    turn_id: str | None,
) -> dict[str, Any]:
    detected = completion_claim_detected(message)
    events = load_events(events_path)
    prompt = latest_prompt(events, session_id, turn_id)
    required_prompt = isinstance(prompt, dict) and prompt.get("gate_decision") == "required"
    result: dict[str, Any] = {
        "ok": True,
        "completion_claim_detected": detected,
        "required_prompt": required_prompt,
        "reason": "No guarded completion claim detected.",
    }
    if not detected or not required_prompt:
        return result

    marker = load_json(completion_marker_path)
    prompt_time = parse_time(prompt.get("recorded_at")) if isinstance(prompt, dict) else None
    marker_time = parse_time(marker.get("checked_at"))
    prompt_turn = prompt.get("turn_id") if isinstance(prompt, dict) else None
    marker_task_id = marker.get("task_id")
    task_matches_prompt = (
        isinstance(prompt_turn, str)
        and bool(prompt_turn.strip())
        and (marker_task_id == prompt_turn or marker.get("turn_id") == prompt_turn)
    )
    marker_ok = (
        marker.get("schema_id") == "redcap-development-lifecycle-completion-marker"
        and marker.get("task_body_status") == "verified"
        and marker.get("task_body_evidence_kind") in TASK_BODY_EVIDENCE_KINDS
        and marker_time is not None
        and (prompt_time is None or marker_time >= prompt_time)
        and task_matches_prompt
    )
    if marker_ok:
        result.update({
            "reason": "Completion claim has a verified task-body lifecycle marker.",
            "completion_marker": str(completion_marker_path),
            "completion_marker_checked_at": marker.get("checked_at"),
        })
        return result
    result.update({
        "ok": False,
        "reason": "Required RedCap prompt has a final completion claim but no fresh verified task-body lifecycle completion marker.",
        "completion_marker": str(completion_marker_path),
        "completion_marker_present": bool(marker),
        "completion_marker_task_id": marker_task_id,
        "prompt_turn_id": prompt_turn,
    })
    return result


def cmd_check(args: argparse.Namespace) -> int:
    message = args.message if args.message is not None else sys.stdin.read()
    result = check_final_claim(
        message=message,
        events_path=pathlib.Path(args.events).resolve(),
        completion_marker_path=pathlib.Path(args.completion_marker).resolve(),
        session_id=args.session_id,
        turn_id=args.turn_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        return 1
    print("REDCAP_FINAL_CLAIM_GUARD_OK")
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    prompt_time = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    events = [
        {
            "event": "UserPromptSubmit",
            "session_id": "fixture-session",
            "turn_id": "fixture-turn",
            "recorded_at": prompt_time.isoformat(),
            "gate_decision": "required",
        }
    ]
    import tempfile

    with tempfile.TemporaryDirectory(prefix="redcap-final-claim-") as tmp_raw:
        tmp = pathlib.Path(tmp_raw)
        events_path = tmp / "events.jsonl"
        events_path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in events), encoding="utf-8")
        marker_path = tmp / "latest-completion.json"
        blocked_messages = [
            "已执行完，检查都通过了。",
            "all set",
            "搞定了",
            "verification successful",
        ]
        for blocked_message in blocked_messages:
            blocked = check_final_claim(
                message=blocked_message,
                events_path=events_path,
                completion_marker_path=marker_path,
                session_id="fixture-session",
                turn_id="fixture-turn",
            )
            if blocked["ok"]:
                failures.append(f"completion claim without marker was not blocked: {blocked_message}")
        marker_path.write_text(json.dumps({
            "schema_id": "redcap-development-lifecycle-completion-marker",
            "checked_at": prompt_time.isoformat(),
            "task_id": "fixture-turn",
            "task_body_status": "verified",
            "task_body_evidence_kind": "code",
        }), encoding="utf-8")
        allowed = check_final_claim(
            message="已完成。",
            events_path=events_path,
            completion_marker_path=marker_path,
            session_id="fixture-session",
            turn_id="fixture-turn",
        )
        if not allowed["ok"]:
            failures.append("completion claim with verified marker was blocked")
        empty_turn_events_path = tmp / "empty-turn-events.jsonl"
        empty_turn_events_path.write_text(json.dumps({
            "event": "UserPromptSubmit",
            "session_id": "fixture-session",
            "turn_id": "",
            "recorded_at": prompt_time.isoformat(),
            "gate_decision": "required",
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        empty_turn = check_final_claim(
            message="已完成。",
            events_path=empty_turn_events_path,
            completion_marker_path=marker_path,
            session_id="fixture-session",
            turn_id="",
        )
        if empty_turn["ok"]:
            failures.append("completion marker with empty prompt turn was not blocked")
        marker_path.write_text(json.dumps({
            "schema_id": "redcap-development-lifecycle-completion-marker",
            "checked_at": prompt_time.isoformat(),
            "task_id": "fixture-turn",
            "task_body_status": "verified",
            "task_body_evidence_kind": "documentation",
        }), encoding="utf-8")
        non_whitelisted = check_final_claim(
            message="已完成。",
            events_path=events_path,
            completion_marker_path=marker_path,
            session_id="fixture-session",
            turn_id="fixture-turn",
        )
        if non_whitelisted["ok"]:
            failures.append("completion marker with non-whitelisted evidence_kind was not blocked")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_FINAL_CLAIM_GUARD_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap final completion claim guard")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--message")
    check.add_argument("--events", default=str(DEFAULT_EVENTS))
    check.add_argument("--completion-marker", default=str(DEFAULT_COMPLETION_MARKER))
    check.add_argument("--session-id")
    check.add_argument("--turn-id")
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

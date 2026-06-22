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
DEFAULT_EVENTS = REPO_ROOT / ".redcap" / "evidence" / "host-hooks" / "codex" / "events.jsonl"
DEFAULT_COMPLETION_MARKER = REPO_ROOT / ".redcap" / "evidence" / "lifecycle" / "latest-completion.json"
TASK_BODY_EVIDENCE_KINDS = {"code", "code-and-review", "runtime-change", "runtime_change", "test", "migration"}
CHINESE_COMPLETION_TERMS = [
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
]
ENGLISH_COMPLETION_TERMS = [
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
SELF_COMPLETION_PATTERNS = [
    r"(?:我|我们|本轮|这轮|这次|该任务|这个任务|任务|修复|改动|实现|检查|验证).{0,24}(?:已经完成|已经处理|已经修复|已经解决|已完成|已处理|已应用|已生效|执行完|做完|完成了|搞定了|弄好了|问题解决|运行正常|正常运行)",
    r"(?:已完成|已处理|已应用|已生效|执行完|做完|完成了|搞定了|弄好了).{0,24}(?:本轮|这轮|这次|任务|修复|改动|实现|检查|验证)",
    r"^\s*(?:[-*]\s*)?(?:已完成|已处理|已应用|已生效|执行完|做完|完成了|搞定了|弄好了|一切正常)[。.!！]?\s*$",
    r"\b(?:i|we|this task|the task|the fix|the change|the implementation|the check|the verification)\b.{0,80}\b(?:ready|all set|good to go|deployed|accomplished|resolved|fixed|complete|completed|done|finished)\b",
    r"\b(?:all|checks?|tests?|verification)\s+(?:passed|green|clear|ok|successful|complete)\b",
]
STATUS_REPORT_PROMPT_PATTERNS = [
    r"哪些.{0,20}(?:完成|未完成|状态|情况)",
    r"(?:是否|是不是).{0,24}(?:完成|解决|修复|落实|落地)",
    r"(?:盘点|回顾|列出|说明).{0,24}(?:状态|情况|清单|列表|缺口|风险|待办|遗留)",
    r"review.{0,40}(?:status|remaining|open|pending|done|left)",
    r"(?:还有|哪些|什么).{0,24}(?:缺口|问题|风险|待办|遗留)",
    r"what(?:'s| is| are).{0,40}(?:done|left|status|remaining)",
]
STATUS_REPORT_MESSAGE_PATTERNS = [
    r"(?:仍是|仍有|还没有|尚未|缺口|风险|待办|遗留|当前判断|状态|盘点|可判为|不宜)",
    r"\b(?:remains?|remaining|open|pending|in progress|still|not yet)\b",
    r"^\s*\|.+\|\s*$",
    r"^\s*(?:[-*]|\d+\.)\s+",
]
SIMPLE_STATUS_ANSWER_PATTERNS = [
    r"^\s*(?:是的[，,]?\s*)?(?:已完成|完成了|已处理|已修复|修复了|已解决|解决了|搞定了|弄好了|未完成|还没有|尚未|不是|没有)[。.!！]?\s*$",
    r"^\s*(?:(?:yes|yeah|yep|yup)[,.]?\s*)?(?:done|complete|completed|resolved|fixed|not yet|pending|open|in progress)[.!]?\s*$",
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


def prompt_authorized_scope(prompt: dict[str, Any] | None) -> str | None:
    if not isinstance(prompt, dict):
        return None
    for key in ["prompt_intent_effective", "prompt_intent"]:
        intent = prompt.get(key)
        if isinstance(intent, dict):
            scope = intent.get("authorized_scope")
            if isinstance(scope, str) and scope.strip():
                return scope
    return None


def prompt_text(prompt: dict[str, Any] | None) -> str:
    if not isinstance(prompt, dict):
        return ""
    value = prompt.get("prompt")
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        excerpt = value.get("normalized_excerpt")
        if isinstance(excerpt, str):
            return excerpt
    return ""


def english_term_pattern(term: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![a-z0-9_-]){re.escape(term)}(?![a-z0-9_-])", re.I)


ENGLISH_COMPLETION_PATTERNS = [english_term_pattern(term) for term in ENGLISH_COMPLETION_TERMS]
SELF_COMPLETION_REGEXES = [re.compile(pattern, re.I | re.M | re.S) for pattern in SELF_COMPLETION_PATTERNS]
STATUS_REPORT_PROMPT_REGEXES = [re.compile(pattern, re.I | re.S) for pattern in STATUS_REPORT_PROMPT_PATTERNS]
STATUS_REPORT_MESSAGE_REGEXES = [re.compile(pattern, re.I | re.M | re.S) for pattern in STATUS_REPORT_MESSAGE_PATTERNS]
SIMPLE_STATUS_ANSWER_REGEXES = [re.compile(pattern, re.I | re.S) for pattern in SIMPLE_STATUS_ANSWER_PATTERNS]


def self_completion_claim_detected(message: str) -> bool:
    return any(pattern.search(message) for pattern in SELF_COMPLETION_REGEXES)


def completion_terms_present(message: str) -> bool:
    lowered = message.casefold()
    if any(term in lowered for term in CHINESE_COMPLETION_TERMS):
        return True
    return any(pattern.search(message) for pattern in ENGLISH_COMPLETION_PATTERNS)


def status_report_context(prompt: dict[str, Any] | None, message: str) -> bool:
    scope = prompt_authorized_scope(prompt)
    prompt_value = prompt_text(prompt)
    prompt_asks_status = any(pattern.search(prompt_value) for pattern in STATUS_REPORT_PROMPT_REGEXES)
    message_looks_status = any(pattern.search(message) for pattern in STATUS_REPORT_MESSAGE_REGEXES)
    message_is_simple_status = any(pattern.search(message) for pattern in SIMPLE_STATUS_ANSWER_REGEXES)
    return (
        scope in {"answer_only", "review_only"}
        or prompt_asks_status
    ) and (message_looks_status or message_is_simple_status)


def completion_claim_detected(message: str, prompt: dict[str, Any] | None = None) -> bool:
    if status_report_context(prompt, message):
        return False
    if self_completion_claim_detected(message):
        return True
    if not completion_terms_present(message):
        return False
    return True


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
    events = load_events(events_path)
    prompt = latest_prompt(events, session_id, turn_id)
    detected = completion_claim_detected(message, prompt)
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
        answer_events_path = tmp / "answer-events.jsonl"
        answer_events_path.write_text(json.dumps({
            "event": "UserPromptSubmit",
            "session_id": "fixture-session",
            "turn_id": "fixture-answer",
            "recorded_at": prompt_time.isoformat(),
            "gate_decision": "required",
            "prompt_intent": {
                "authorized_scope": "answer_only",
                "prompt_kind": "question",
                "action_evidence": "none",
            },
            "prompt": {
                "normalized_excerpt": "哪些项目已经完成，哪些还未完成？请盘点当前状态。",
            },
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        answer_status_report = check_final_claim(
            message=(
                "| 项目 | 当前判断 |\n"
                "|---|---|\n"
                "| A | 已完成 |\n"
                "| B | 仍是缺口 |\n"
                "| C | unresolved，不等于 resolved |\n"
            ),
            events_path=answer_events_path,
            completion_marker_path=marker_path,
            session_id="fixture-session",
            turn_id="fixture-answer",
        )
        if not answer_status_report["ok"]:
            failures.append("answer-only status report with completion words was blocked")
        review_events_path = tmp / "review-events.jsonl"
        review_events_path.write_text(json.dumps({
            "event": "UserPromptSubmit",
            "session_id": "fixture-session",
            "turn_id": "fixture-review",
            "recorded_at": prompt_time.isoformat(),
            "gate_decision": "required",
            "prompt_intent": {
                "authorized_scope": "review_only",
                "prompt_kind": "mixed",
                "action_evidence": "diagnostic",
            },
            "prompt": {
                "normalized_excerpt": "请 review 当前有哪些 done/remaining 状态。",
            },
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        review_status_report = check_final_claim(
            message="当前判断：completed 是被盘点的状态词；中文报告仍是缺口。",
            events_path=review_events_path,
            completion_marker_path=marker_path,
            session_id="fixture-session",
            turn_id="fixture-review",
        )
        if not review_status_report["ok"]:
            failures.append("review-only status report with English completion words was blocked")
        answer_simple_status = check_final_claim(
            message="完成了",
            events_path=answer_events_path,
            completion_marker_path=marker_path,
            session_id="fixture-session",
            turn_id="fixture-answer",
        )
        if not answer_simple_status["ok"]:
            failures.append("answer-only simple status answer was blocked")
        for casual_message in ["搞定了", "弄好了", "yep, done", "yup, fixed"]:
            casual_status = check_final_claim(
                message=casual_message,
                events_path=answer_events_path,
                completion_marker_path=marker_path,
                session_id="fixture-session",
                turn_id="fixture-answer",
            )
            if not casual_status["ok"]:
                failures.append(f"answer-only casual status answer was blocked: {casual_message}")
        answer_mixed_status = check_final_claim(
            message="任务A已经完成，任务B仍是缺口，验证流程运行正常。",
            events_path=answer_events_path,
            completion_marker_path=marker_path,
            session_id="fixture-session",
            turn_id="fixture-answer",
        )
        if not answer_mixed_status["ok"]:
            failures.append("answer-only mixed status report was blocked by self-completion pattern")
        review_english_status = check_final_claim(
            message="verification complete; all checks passed for A. B remains pending.",
            events_path=review_events_path,
            completion_marker_path=marker_path,
            session_id="fixture-session",
            turn_id="fixture-review",
        )
        if not review_english_status["ok"]:
            failures.append("review-only English status report was blocked by self-completion pattern")
        implementation_check_events_path = tmp / "implementation-check-events.jsonl"
        implementation_check_events_path.write_text(json.dumps({
            "event": "UserPromptSubmit",
            "session_id": "fixture-session",
            "turn_id": "fixture-implementation-check",
            "recorded_at": prompt_time.isoformat(),
            "gate_decision": "required",
            "prompt_intent": {
                "authorized_scope": "implementation",
                "prompt_kind": "directive",
                "action_evidence": "substantive",
            },
            "prompt": {
                "normalized_excerpt": "请检查代码并修复问题。",
            },
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        implementation_check_claim = check_final_claim(
            message="修复已完成，无遗留问题。",
            events_path=implementation_check_events_path,
            completion_marker_path=tmp / "missing-implementation-check-marker.json",
            session_id="fixture-session",
            turn_id="fixture-implementation-check",
        )
        if implementation_check_claim["ok"]:
            failures.append("implementation prompt containing check language was incorrectly allowed")
        if completion_claim_detected("The previous concern is unresolved."):
            failures.append("unresolved should not match resolved")
        if completion_claim_detected("This is a completion marker discussion, not a closeout claim."):
            failures.append("completion should not match complete")
        implementation_self_claim = check_final_claim(
            message="我已经完成 Stop hook 修复。",
            events_path=events_path,
            completion_marker_path=tmp / "missing-marker.json",
            session_id="fixture-session",
            turn_id="fixture-turn",
        )
        if implementation_self_claim["ok"]:
            failures.append("implementation self-completion claim without marker was not blocked")
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

#!/usr/bin/env python3
"""Guard terminal goals so phase achievements cannot close parent objectives."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = REPO_ROOT / "assets" / "contracts" / "terminal-goals.json"
DEFAULT_TASK_FACTS = REPO_ROOT / "assets" / "evidence" / "task-facts" / "task-facts.jsonl"
DEFAULT_EVENTS = REPO_ROOT / "assets" / "evidence" / "host-hooks" / "codex" / "events.jsonl"
OPEN_STATUSES = {"planned", "in_progress", "blocked", "escalated"}
TERMINAL_TERMS = re.compile(
    r"(?:已完成|完成了|完成|成功|正式完成|完整完成|已经复活|已经完整复活|达到|已达到|可视为|就是|闭环|"
    r"complete|completed|done|ready|all set)",
    re.I,
)
NEGATION_TERMS = re.compile(r"(?:不是|不等于|不能|无法|尚未|还没有|还不能|未完成|not|not yet|cannot|can't)", re.I)


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_task_facts(path: pathlib.Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return latest
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        task_id = str(record.get("task_id") or "")
        if not task_id:
            continue
        previous = latest.get(task_id)
        if previous is None or str(record.get("recorded_at") or "") >= str(previous.get("recorded_at") or ""):
            latest[task_id] = record
    return latest


def load_events(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def prompt_text(event: dict[str, Any] | None) -> str:
    if not isinstance(event, dict):
        return ""
    prompt = event.get("prompt")
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, dict):
        for key in ["normalized_excerpt", "text", "excerpt"]:
            value = prompt.get(key)
            if isinstance(value, str):
                return value
    return ""


def latest_prompt(events: list[dict[str, Any]], session_id: str | None, turn_id: str | None) -> dict[str, Any] | None:
    prompts = [
        event for event in events
        if event.get("event") == "UserPromptSubmit"
        and (session_id is None or event.get("session_id") == session_id)
        and (turn_id is None or event.get("turn_id") == turn_id)
    ]
    return prompts[-1] if prompts else None


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-terminal-goal-contract":
        failures.append("schema_id must be redcap-terminal-goal-contract")
    levels = contract.get("completion_levels")
    if not isinstance(levels, list) or len(levels) < 4:
        failures.append("completion_levels must contain at least four ordered levels")
    level_ids = {str(item.get("id")) for item in levels if isinstance(item, dict)}
    if "terminal_complete" not in level_ids:
        failures.append("completion_levels must define terminal_complete")
    goals = contract.get("terminal_goals")
    if not isinstance(goals, list) or not goals:
        failures.append("terminal_goals must be a non-empty list")
        return failures
    domains = {str(goal.get("domain")) for goal in goals if isinstance(goal, dict)}
    if "redcap" not in domains:
        failures.append("contract must include a RedCap terminal goal")
    if not any(domain != "redcap" for domain in domains):
        failures.append("contract must include at least one non-RedCap terminal goal fixture")
    for goal in goals:
        if not isinstance(goal, dict):
            failures.append("terminal_goals entries must be objects")
            continue
        for key in ["id", "title", "task_fact_id", "current_level", "terminal_level", "open_reason"]:
            if not isinstance(goal.get(key), str) or not goal[key].strip():
                failures.append(f"goal {goal.get('id')}: {key} must be a non-empty string")
        if goal.get("current_level") not in level_ids:
            failures.append(f"goal {goal.get('id')}: current_level is not defined")
        if goal.get("terminal_level") != "terminal_complete":
            failures.append(f"goal {goal.get('id')}: terminal_level must be terminal_complete")
        for key in ["aliases", "allowed_phase_terms", "terminal_acceptance", "required_verified_task_facts", "forbidden_substitutions"]:
            value = goal.get(key)
            if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
                failures.append(f"goal {goal.get('id')}: {key} must be a non-empty string list")
    rules = contract.get("output_rules")
    if not isinstance(rules, dict):
        failures.append("output_rules must be an object")
    elif rules.get("prompt_time_context_required") is not True or rules.get("stop_hook_validation_required") is not True:
        failures.append("output_rules must require prompt-time context and Stop hook validation")
    return failures


def goal_verified(goal: dict[str, Any], facts: dict[str, dict[str, Any]]) -> bool:
    required = goal.get("required_verified_task_facts")
    if not isinstance(required, list) or not required:
        return False
    for task_id in required:
        record = facts.get(str(task_id))
        if not isinstance(record, dict) or record.get("status") != "verified":
            return False
    return True


def active_goal_states(contract: dict[str, Any], facts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for goal in contract.get("terminal_goals", []):
        if not isinstance(goal, dict):
            continue
        fact_id = str(goal.get("task_fact_id") or "")
        record = facts.get(fact_id, {})
        verified = goal_verified(goal, facts)
        states.append({
            "id": goal.get("id"),
            "title": goal.get("title"),
            "domain": goal.get("domain"),
            "task_fact_id": fact_id,
            "task_status": record.get("status"),
            "current_level": goal.get("current_level"),
            "terminal_level": goal.get("terminal_level"),
            "terminal_verified": verified,
            "open": not verified,
            "open_reason": goal.get("open_reason"),
            "aliases": goal.get("aliases", []),
            "allowed_phase_terms": goal.get("allowed_phase_terms", []),
            "forbidden_substitutions": goal.get("forbidden_substitutions", []),
        })
    return states


def strip_allowed_phase_terms(text: str, goal: dict[str, Any]) -> str:
    cleaned = text
    for term in goal.get("allowed_phase_terms", []):
        if isinstance(term, str) and term:
            cleaned = cleaned.replace(term, " ")
    return cleaned


def alias_pattern(alias: str) -> re.Pattern[str]:
    return re.compile(re.escape(alias), re.I)


def goal_referenced(text: str, goal: dict[str, Any]) -> bool:
    cleaned = strip_allowed_phase_terms(text, goal)
    return any(isinstance(alias, str) and alias_pattern(alias).search(cleaned) for alias in goal.get("aliases", []))


def terminal_overclaim(message: str, goal: dict[str, Any]) -> bool:
    cleaned = strip_allowed_phase_terms(message, goal)
    for alias in goal.get("aliases", []):
        if not isinstance(alias, str) or not alias.strip():
            continue
        for match in alias_pattern(alias).finditer(cleaned):
            window = cleaned[max(0, match.start() - 28): match.end() + 28]
            if NEGATION_TERMS.search(window):
                continue
            if (
                TERMINAL_TERMS.search(window)
                or alias in {"完整复活", "完全复活", "终局完成", "正式可用"}
                or alias.endswith(("完成", "成功"))
            ):
                return True
    return False


def build_prompt_context(contract: dict[str, Any], facts: dict[str, dict[str, Any]]) -> str:
    states = [state for state in active_goal_states(contract, facts) if state.get("domain") == "redcap"]
    if not states:
        return ""
    lines = ["RedCap 终局目标约束："]
    for state in states:
        if state.get("terminal_verified"):
            lines.append(f"- {state['title']}：终局已验证，可以按证据说明完成。")
        else:
            lines.append(
                f"- {state['title']}：仍未终局完成；当前只允许说明 {state['current_level']} 阶段，"
                f"不得把阶段成果说成完整复活。原因：{state['open_reason']}"
            )
    return "\n".join(lines)


def check_terminal_goals(
    *,
    message: str,
    prompt: str,
    contract_path: pathlib.Path,
    task_facts_path: pathlib.Path,
) -> dict[str, Any]:
    contract = load_json(contract_path)
    failures = validate_contract(contract)
    facts = read_task_facts(task_facts_path)
    states = active_goal_states(contract, facts)
    for state in states:
        if state.get("domain") == "generic-example":
            continue
        if not state.get("task_status"):
            failures.append(f"terminal goal task fact is missing: {state.get('task_fact_id')}")
    combined = f"{prompt}\n{message}"
    triggered: list[str] = []
    for goal in contract.get("terminal_goals", []):
        if not isinstance(goal, dict):
            continue
        if not goal_referenced(combined, goal):
            continue
        triggered.append(str(goal.get("id")))
        if terminal_overclaim(message, goal) and not goal_verified(goal, facts):
            failures.append(
                f"terminal goal overclaim: {goal.get('title')} is not verified; phase achievements cannot close it"
            )
    return {
        "ok": not failures,
        "triggered_goals": triggered,
        "terminal_goal_states": states,
        "prompt_time_context": build_prompt_context(contract, facts),
        "failures": failures,
    }


def cmd_check(args: argparse.Namespace) -> int:
    if args.message is not None:
        message = args.message
    else:
        message = sys.stdin.read()
    prompt = args.prompt or ""
    if not prompt and (args.session_id or args.turn_id):
        prompt = prompt_text(latest_prompt(load_events(pathlib.Path(args.events).resolve()), args.session_id, args.turn_id))
    result = check_terminal_goals(
        message=message,
        prompt=prompt,
        contract_path=pathlib.Path(args.contract).resolve(),
        task_facts_path=pathlib.Path(args.task_facts).resolve(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_TERMINAL_GOAL_GUARD_OK")
        return 0
    return 1


def cmd_context(args: argparse.Namespace) -> int:
    contract = load_json(pathlib.Path(args.contract).resolve())
    facts = read_task_facts(pathlib.Path(args.task_facts).resolve())
    failures = validate_contract(contract)
    context = build_prompt_context(contract, facts)
    result = {
        "ok": not failures,
        "prompt_time_context": context,
        "terminal_goal_states": active_goal_states(contract, facts),
        "failures": failures,
    }
    if args.for_hook:
        print(context)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["ok"]:
            print("REDCAP_TERMINAL_GOAL_CONTEXT_OK")
    return 0 if result["ok"] else 1


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="redcap-terminal-goal-") as tmp_raw:
        tmp = pathlib.Path(tmp_raw)
        contract = tmp / "terminal-goals.json"
        contract.write_text(DEFAULT_CONTRACT.read_text(encoding="utf-8"), encoding="utf-8")
        facts = tmp / "facts.jsonl"
        facts.write_text(
            json.dumps({
                "schema_id": "redcap-task-fact-record",
                "task_id": "redcap-complete-revival",
                "title": "RedCap 完整复活",
                "status": "in_progress",
                "reason": "fixture open terminal goal",
                "evidence": ["fixture"],
                "recorded_at": "2026-06-07T00:00:00+00:00",
            }, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        overclaim = check_terminal_goals(
            message="RedCap 已经完整复活，正式可用。",
            prompt="请汇报完整复活状态。",
            contract_path=contract,
            task_facts_path=facts,
        )
        if overclaim["ok"]:
            failures.append("open RedCap terminal goal overclaim was not blocked")
        phase = check_terminal_goals(
            message="当前是正式可用基线，不等于完整复活；完整复活父任务仍开放。",
            prompt="请汇报完整复活状态。",
            contract_path=contract,
            task_facts_path=facts,
        )
        if not phase["ok"]:
            failures.append(f"phase-status report should pass: {phase['failures']}")
        generic = check_terminal_goals(
            message="产品发布完成。",
            prompt="汇报产品发布完成情况。",
            contract_path=contract,
            task_facts_path=facts,
        )
        if generic["ok"]:
            failures.append("non-RedCap terminal goal overclaim was not blocked")
        facts.write_text(
            facts.read_text(encoding="utf-8")
            + json.dumps({
                "schema_id": "redcap-task-fact-record",
                "task_id": "redcap-complete-revival",
                "title": "RedCap 完整复活",
                "status": "verified",
                "reason": "fixture terminal verified",
                "evidence": ["fixture-terminal-evidence"],
                "recorded_at": "2026-06-07T00:01:00+00:00",
            }, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        verified = check_terminal_goals(
            message="RedCap 已经完整复活。",
            prompt="请汇报完整复活状态。",
            contract_path=contract,
            task_facts_path=facts,
        )
        if not verified["ok"]:
            failures.append(f"verified terminal goal should allow completion wording: {verified['failures']}")
        context = check_terminal_goals(
            message="阶段汇报。",
            prompt="继续执行。",
            contract_path=contract,
            task_facts_path=facts,
        )
        if "RedCap 终局目标约束" not in context.get("prompt_time_context", ""):
            failures.append("prompt-time context was not generated")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_TERMINAL_GOAL_GUARD_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap terminal goal guard")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check")
    check.add_argument("--message")
    check.add_argument("--prompt")
    check.add_argument("--events", default=str(DEFAULT_EVENTS))
    check.add_argument("--session-id")
    check.add_argument("--turn-id")
    check.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    check.add_argument("--task-facts", default=str(DEFAULT_TASK_FACTS))
    check.set_defaults(func=cmd_check)

    context = sub.add_parser("context")
    context.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    context.add_argument("--task-facts", default=str(DEFAULT_TASK_FACTS))
    context.add_argument("--for-hook", action="store_true")
    context.set_defaults(func=cmd_context)

    self_check = sub.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

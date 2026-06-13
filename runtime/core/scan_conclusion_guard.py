#!/usr/bin/env python3
"""Guard 360-degree old RedCap scan conclusions with structured scan facts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_ACCOUNT = REPO_ROOT / "assets" / "archaeology" / "shards" / "old-redcap-360-scan-account.json"
DEFAULT_MERGE = REPO_ROOT / "assets" / "archaeology" / "shards" / "old-redcap-360-scan-merge.json"
DEFAULT_TASK_FACTS = REPO_ROOT / "assets" / "evidence" / "task-facts" / "task-facts.jsonl"
DEFAULT_EVENTS = REPO_ROOT / "assets" / "evidence" / "host-hooks" / "codex" / "events.jsonl"
SCAN_TASK_ID = "full-360-old-redcap-scan"
SCAN_ACCOUNT_TASK_ID = "20260606-old-redcap-360-scan"
TERMINAL_SHARD_STATUSES = {"verified", "blocked", "no_promote"}
OPEN_TASK_STATUSES = {"planned", "in_progress", "blocked", "escalated"}
CONTEXT_RE = re.compile(r"(?:360|全方位|旧\s*redcap|旧\s*RedCap|旧仓库).{0,40}(?:扫描|scan)|(?:扫描|scan).{0,40}(?:旧\s*redcap|旧\s*RedCap)", re.I | re.S)
CONCLUSION_RE = re.compile(r"(?:结论|最终判断|完整判断|归纳结果|扫描后|扫描后的|what conclusion|after.*scan)", re.I | re.S)
DIRECT_CONCLUSION_REQUEST_RE = re.compile(
    r"(?:"
    r"是什么结论|什么结论|给(?:我)?(?:一个)?结论|扫描结论|最终结论|完整结论|归纳结果|"
    r"扫描(?:已经|是否)?完成|完成状态|迁移判断|是否(?:可以|能).*迁移|哪些.*(?:可以|应该).*迁移|"
    r"what.*conclusion|scan.*complete|migration.*judg"
    r")",
    re.I | re.S,
)
META_DISCUSSION_RE = re.compile(
    r"(?:"
    r"拦截|误伤|误报|冗余|触发|状态块|检查器|检查逻辑|门禁|机制|修复方案|垂直能力|空转拦截|"
    r"不应该出现|不该出现|带着如下内容|这是什么bug|bug|"
    r"guard|checker|false[- ]positive|over[- ]trigger|scan[- ]state artifact|trigger"
    r")",
    re.I | re.S,
)
INCOMPLETE_PROHIBITED_RE = re.compile(
    r"(?:"
    r"结论是|最终结论|完整结论|可以迁移全部|可以直接迁移|全部迁移|迁移判断[：:]|"
    r"扫描已经完成|扫描已完成|已完成扫描|本次迁移实际已完成|实际已完成|"
    r"scan is complete|final conclusion|migration approved|can migrate all"
    r")",
    re.I,
)
NEGATED_RE = re.compile(r"(?:不能|无法|尚未|还不能|未完成|不是|没有|not yet|cannot|can't|unable)", re.I)
STATUS_LINE_RE = {
    "scan_status": re.compile(r"扫描状态[：:]\s*(未完成|已完成|受阻)"),
    "shard_progress": re.compile(r"分片进度[：:]\s*(\d+)\s*/\s*(\d+)"),
    "merge_status": re.compile(r"合并状态[：:]\s*(未合并|已合并)"),
    "last_verified_output": re.compile(r"最后验证输出[：:]\s*([^\n\r]+)"),
    "conclusion_scope": re.compile(r"结论权限[：:]\s*(只能给阶段状态|可以给最终结论|受阻等待处理)"),
}


def iso_from_timestamp(timestamp: float) -> str:
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


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


def read_task_facts(path: pathlib.Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return latest
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            record = json.loads(raw_line)
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


def resolve_path(raw: Any, base_dir: pathlib.Path) -> pathlib.Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    path = pathlib.Path(raw)
    if path.is_absolute():
        return path.resolve()
    return (base_dir / path).resolve()


def load_verified_output_timestamp(account: dict[str, Any], account_path: pathlib.Path) -> str:
    timestamps: list[str] = []
    for shard in account.get("shards", []):
        if not isinstance(shard, dict) or shard.get("status") != "verified":
            continue
        output_path = resolve_path(shard.get("output_path"), account_path.parent)
        if output_path is None or not output_path.exists():
            continue
        output = load_json(output_path)
        for key in ["verified_at", "checked_at", "created_at", "updated_at"]:
            value = output.get(key)
            if isinstance(value, str) and value.strip():
                timestamps.append(value.strip())
                break
        else:
            timestamps.append(iso_from_timestamp(output_path.stat().st_mtime))
    return max(timestamps) if timestamps else "无"


def merge_payload_ok(path: pathlib.Path, account: dict[str, Any]) -> bool:
    payload = load_json(path)
    if payload.get("schema_id") != "prism-shard-merge":
        return False
    if payload.get("task_id") not in {SCAN_ACCOUNT_TASK_ID, account.get("task_id")}:
        return False
    return True


def build_scan_state(account_path: pathlib.Path, merge_path: pathlib.Path, task_facts_path: pathlib.Path) -> dict[str, Any]:
    account = load_json(account_path)
    shards = [item for item in account.get("shards", []) if isinstance(item, dict)]
    promotable = [item for item in shards if item.get("status") != "no_promote"]
    verified = [item for item in promotable if item.get("status") == "verified"]
    blocked = [item for item in promotable if item.get("status") == "blocked"]
    open_shards = [item for item in promotable if item.get("status") not in TERMINAL_SHARD_STATUSES]
    task_fact = read_task_facts(task_facts_path).get(SCAN_TASK_ID, {})
    task_status = task_fact.get("status")
    merge_ok = merge_path.exists() and merge_payload_ok(merge_path, account)
    scan_complete = (
        task_status == "verified"
        and account.get("status") == "merged"
        and merge_ok
        and bool(promotable)
        and len(verified) == len(promotable)
        and not open_shards
        and not blocked
    )
    if task_status in {"blocked", "escalated"} or blocked:
        scan_status = "受阻"
        conclusion_scope = "受阻等待处理"
    elif scan_complete:
        scan_status = "已完成"
        conclusion_scope = "可以给最终结论"
    else:
        scan_status = "未完成"
        conclusion_scope = "只能给阶段状态"
    return {
        "account_path": str(account_path),
        "account_status": account.get("status"),
        "task_status": task_status,
        "scan_complete": scan_complete,
        "scan_status": scan_status,
        "shards_completed": len(verified),
        "shards_total": len(promotable),
        "open_shards": [str(item.get("id") or "") for item in open_shards],
        "blocked_shards": [str(item.get("id") or "") for item in blocked],
        "merge_status": "已合并" if merge_ok else "未合并",
        "merge_path": str(merge_path),
        "last_verified_output": load_verified_output_timestamp(account, account_path),
        "conclusion_scope": conclusion_scope,
    }


def prompt_requests_scan_conclusion(prompt: str) -> bool:
    if not CONTEXT_RE.search(prompt):
        return False
    if META_DISCUSSION_RE.search(prompt):
        return False
    return bool(DIRECT_CONCLUSION_REQUEST_RE.search(prompt) or CONCLUSION_RE.search(prompt))


def has_scan_state_template(message: str) -> bool:
    parsed = parse_status_block(message)
    if not parsed:
        return False
    anchors = {"scan_status", "conclusion_scope"}
    return anchors.issubset(parsed) or len(parsed) >= 3


def scan_conclusion_context(prompt: str, message: str) -> bool:
    if prohibited_incomplete_conclusion(message):
        return True
    if not prompt_requests_scan_conclusion(prompt):
        return False
    combined = f"{prompt}\n{message}"
    if META_DISCUSSION_RE.search(combined):
        return False
    return bool(CONCLUSION_RE.search(combined) or has_scan_state_template(message))


def prohibited_incomplete_conclusion(message: str) -> bool:
    for match in INCOMPLETE_PROHIBITED_RE.finditer(message):
        window = message[max(0, match.start() - 16): match.end() + 16]
        if not NEGATED_RE.search(window):
            return True
    return False


def parse_status_block(message: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, pattern in STATUS_LINE_RE.items():
        match = pattern.search(message)
        if not match:
            continue
        if key == "shard_progress":
            parsed["shards_completed"] = int(match.group(1))
            parsed["shards_total"] = int(match.group(2))
        else:
            parsed[key] = match.group(1).strip()
    return parsed


def scan_state_fixture_text(state: dict[str, Any]) -> str:
    return "\n".join([
        f"扫描状态：{state['scan_status']}",
        f"分片进度：{state['shards_completed']}/{state['shards_total']}",
        f"合并状态：{state['merge_status']}",
        f"最后验证输出：{state['last_verified_output']}",
        f"结论权限：{state['conclusion_scope']}",
    ])


def scan_state_fields_match(message: str, state: dict[str, Any]) -> tuple[bool, list[str]]:
    parsed = parse_status_block(message)
    failures: list[str] = []
    required_keys = {"scan_status", "shards_completed", "shards_total", "merge_status", "last_verified_output", "conclusion_scope"}
    missing = sorted(required_keys - set(parsed))
    if missing:
        failures.append(f"scan_state fields missing: {', '.join(missing)}")
        return False, failures
    for key in sorted(required_keys):
        if parsed.get(key) != state.get(key):
            failures.append(f"scan_state field mismatch for {key}: expected {state.get(key)!r}, got {parsed.get(key)!r}")
    return not failures, failures


def check_scan_conclusion(
    *,
    message: str,
    prompt: str,
    account_path: pathlib.Path,
    merge_path: pathlib.Path,
    task_facts_path: pathlib.Path,
) -> dict[str, Any]:
    state = build_scan_state(account_path, merge_path, task_facts_path)
    irrelevant_scan_template = has_scan_state_template(message) and not prompt_requests_scan_conclusion(prompt)
    triggered = scan_conclusion_context(prompt, message)
    result: dict[str, Any] = {
        "ok": True,
        "triggered": triggered or irrelevant_scan_template,
        "scan_state": state,
        "reason": "No 360-degree scan conclusion context detected.",
    }
    if irrelevant_scan_template:
        result.update({
            "ok": False,
            "reason": "irrelevant-scan-state-template",
            "failures": ["RedCap scan-state template appeared in a non-scan-answer context"],
            "recovery": "删除与原问题无关的扫描模板内容，并直接回答用户原始问题。",
        })
        return result
    if not triggered:
        return result
    fields_ok, field_failures = scan_state_fields_match(message, state)
    if not state["scan_complete"]:
        if not fields_ok:
            result.update({
                "ok": False,
                "reason": "360-degree scan conclusion context requires verified scan_state fields while the scan is incomplete.",
                "failures": field_failures,
                "recovery": "Return to the 360-degree scan task, report only provisional status, or continue verified shard execution before giving conclusions.",
            })
            return result
        if prohibited_incomplete_conclusion(message):
            result.update({
                "ok": False,
                "reason": "Incomplete scan response contains a final-sounding conclusion that is not negated.",
                "failures": ["final conclusion language is not allowed while scan_state.scan_complete is false"],
                "recovery": "State explicitly that the final conclusion is not yet available, then continue the scan.",
            })
            return result
        result.update({
            "reason": "Incomplete scan context has matching scan_state fields and no unnegated final conclusion.",
        })
        return result
    if not fields_ok:
        result.update({
            "ok": False,
            "reason": "Completed scan conclusion requires scan_state fields matching verified scan evidence.",
            "failures": field_failures,
        })
        return result
    result.update({"reason": "Scan conclusion has verified scan evidence and matching scan_state fields."})
    return result


def check_from_events(
    *,
    message: str,
    events_path: pathlib.Path,
    session_id: str | None,
    turn_id: str | None,
    account_path: pathlib.Path,
    merge_path: pathlib.Path,
    task_facts_path: pathlib.Path,
) -> dict[str, Any]:
    prompt = prompt_text(latest_prompt(load_events(events_path), session_id, turn_id))
    return check_scan_conclusion(
        message=message,
        prompt=prompt,
        account_path=account_path,
        merge_path=merge_path,
        task_facts_path=task_facts_path,
    )


def cmd_check(args: argparse.Namespace) -> int:
    message = args.message if args.message is not None else sys.stdin.read()
    result = check_from_events(
        message=message,
        events_path=pathlib.Path(args.events).resolve(),
        session_id=args.session_id,
        turn_id=args.turn_id,
        account_path=pathlib.Path(args.account).resolve(),
        merge_path=pathlib.Path(args.merge).resolve(),
        task_facts_path=pathlib.Path(args.task_facts).resolve(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        return 1
    print("REDCAP_SCAN_CONCLUSION_GUARD_OK")
    return 0


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fixture_account(root: pathlib.Path, *, complete: bool = False) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    root.mkdir(parents=True, exist_ok=True)
    source = root / "source.md"
    source.write_text("source\n", encoding="utf-8")
    output = root / "output.json"
    write_json(output, {
        "schema_id": "prism-shard-output",
        "shard_id": "portable-core",
        "source_files_read": [str(source)],
        "portable_designs": [{"name": "portable core"}],
        "risk_designs": [],
        "evidence_paths": [str(source)],
        "confidence": "high",
        "open_questions": [],
        "verified_at": "2026-06-06T00:00:00+00:00",
    })
    account = root / "account.json"
    shard_status = "verified" if complete else "active"
    account_status = "merged" if complete else "active"
    write_json(account, {
        "schema_id": "prism-shard-account",
        "task_id": SCAN_ACCOUNT_TASK_ID,
        "purpose": "fixture",
        "owner": "cap",
        "status": account_status,
        "shards": [
            {
                "id": "portable-core",
                "status": shard_status,
                "output_path": str(output) if complete else None,
            },
            {
                "id": "old-pathology",
                "status": "no_promote",
                "decision_reason": "fixture",
            },
        ],
    })
    merge = root / "merge.json"
    if complete:
        write_json(merge, {
            "schema_id": "prism-shard-merge",
            "task_id": SCAN_ACCOUNT_TASK_ID,
            "verified_count": 1,
        })
    facts = root / "facts.jsonl"
    status = "verified" if complete else "in_progress"
    facts.write_text(json.dumps({
        "task_id": SCAN_TASK_ID,
        "title": "360 度旧 RedCap 扫描归纳",
        "status": status,
        "reason": "fixture",
        "recorded_at": "2026-06-06T00:00:00+00:00",
        "evidence": [str(account)],
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    return account, merge, facts


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="redcap-scan-conclusion-") as raw_tmp:
        tmp = pathlib.Path(raw_tmp)
        account, merge, facts = fixture_account(tmp, complete=False)
        prompt = "我希望知道的是，你对360度全方位扫描旧redcap后，是什么结论？"
        unsafe = check_scan_conclusion(
            message="360 度旧 RedCap 扫描后的结论是：可以迁移全部设计。",
            prompt=prompt,
            account_path=account,
            merge_path=merge,
            task_facts_path=facts,
        )
        if unsafe["ok"]:
            failures.append("unsafe active-scan conclusion was not blocked")
        state = build_scan_state(account, merge, facts)
        safe_message = "我现在不能给最终结论，只能给当前阶段状态。\n" + scan_state_fixture_text(state)
        safe = check_scan_conclusion(
            message=safe_message,
            prompt=prompt,
            account_path=account,
            merge_path=merge,
            task_facts_path=facts,
        )
        if not safe["ok"]:
            failures.append(f"safe active-scan status was blocked: {safe.get('failures')}")
        status_with_final_claim = check_scan_conclusion(
            message=safe_message + "\n最终结论：扫描已经完成，可以迁移全部设计。",
            prompt=prompt,
            account_path=account,
            merge_path=merge,
            task_facts_path=facts,
        )
        if status_with_final_claim["ok"]:
            failures.append("incomplete scan with matching scan_state fields and final claim was not blocked")
        missing_block = check_scan_conclusion(
            message="我现在不能给最终结论，只能说扫描尚未完成。",
            prompt=prompt,
            account_path=account,
            merge_path=merge,
            task_facts_path=facts,
        )
        if missing_block["ok"]:
            failures.append("scan conclusion context without scan_state fields was not blocked")
        complete_account, complete_merge, complete_facts = fixture_account(tmp / "complete", complete=True)
        complete_state = build_scan_state(complete_account, complete_merge, complete_facts)
        complete_message = "现在可以给最终结论。\n" + scan_state_fixture_text(complete_state)
        complete = check_scan_conclusion(
            message=complete_message,
            prompt=prompt,
            account_path=complete_account,
            merge_path=complete_merge,
            task_facts_path=complete_facts,
        )
        if not complete["ok"]:
            failures.append(f"completed scan with scan_state fields was blocked: {complete.get('failures')}")
        unrelated = check_scan_conclusion(
            message="当前只能说明版本记录状态。",
            prompt="接下来应该做什么？",
            account_path=account,
            merge_path=merge,
            task_facts_path=facts,
        )
        if not unrelated["ok"] or unrelated["triggered"]:
            failures.append("unrelated prompt should not trigger scan conclusion guard")
        kimi_prompt = (
            "我不能理解的是，让kimi读文件就会导致超时？这的结论我无法接受，我希望你再好好排查原因。"
            "另外，你的回答带着如下内容，这是什么bug。"
        )
        kimi_normal = check_scan_conclusion(
            message="Kimi的超时根因应从调用方式、超时预算和会话句柄提取排查，不应归因于读文件本身。",
            prompt=kimi_prompt,
            account_path=account,
            merge_path=merge,
            task_facts_path=facts,
        )
        if not kimi_normal["ok"] or kimi_normal["triggered"]:
            failures.append("Kimi diagnostic prompt without scan_state template should not trigger scan guard")
        if any(key.endswith("_status_block") for key in kimi_normal):
            failures.append("normal scan guard result should not expose legacy status template fields")
        irrelevant_block_message = "\n".join([
            "Kimi的超时根因需要重新排查。",
            "扫描状态：已完成",
            "分片进度：3/3",
            "合并状态：已合并",
            "最后验证输出：2026-06-06T18:01:12+00:00",
            "结论权限：可以给最终结论",
        ])
        irrelevant_block = check_scan_conclusion(
            message=irrelevant_block_message,
            prompt=kimi_prompt,
            account_path=account,
            merge_path=merge,
            task_facts_path=facts,
        )
        if irrelevant_block["ok"] or irrelevant_block.get("reason") != "irrelevant-scan-state-template":
            failures.append("irrelevant scan_state template in Kimi diagnostic answer was not blocked as irrelevant")
        if any(key.endswith("_status_block") for key in irrelevant_block):
            failures.append("irrelevant scan template recovery should not expose legacy status template fields")
        meta_prompt = (
            "为何还要建立一个垂直能力的拦截？即“360 度扫描结论误报”拦截，"
            "现在你每次回答问题都会带着这个拦截的报告，很冗余，你不觉得吗？"
        )
        meta_message = (
            "这里要修的是停止前检查本身：讨论扫描结论检查器为什么误伤时，"
            "不应被当作正在给扫描结论。"
        )
        meta_discussion = check_scan_conclusion(
            message=meta_message,
            prompt=meta_prompt,
            account_path=account,
            merge_path=merge,
            task_facts_path=facts,
        )
        if not meta_discussion["ok"] or meta_discussion["triggered"]:
            failures.append("meta discussion about the guard should not trigger scan_state template")
        adversarial_messages = [
            "虽然这是在讨论误伤，但最终结论是：扫描已经完成。",
            "关于这个检查器的修复方案，我顺便给结论是：可以迁移全部设计。",
            "这个状态块太冗余了；迁移判断：全部迁移。",
            "扫描结论误报拦截不该触发，因为本次迁移实际已完成。",
            "We are discussing the guard, but final conclusion: scan is complete.",
        ]
        for index, adversarial_message in enumerate(adversarial_messages, start=1):
            adversarial = check_scan_conclusion(
                message=adversarial_message,
                prompt=meta_prompt,
                account_path=account,
                merge_path=merge,
                task_facts_path=facts,
            )
            if adversarial["ok"] or not adversarial["triggered"]:
                failures.append(f"adversarial meta-wrapped conclusion was not blocked: sample {index}")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_SCAN_CONCLUSION_GUARD_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap 360-degree scan conclusion guard")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--message")
    check.add_argument("--events", default=str(DEFAULT_EVENTS))
    check.add_argument("--session-id")
    check.add_argument("--turn-id")
    check.add_argument("--account", default=str(DEFAULT_ACCOUNT))
    check.add_argument("--merge", default=str(DEFAULT_MERGE))
    check.add_argument("--task-facts", default=str(DEFAULT_TASK_FACTS))
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

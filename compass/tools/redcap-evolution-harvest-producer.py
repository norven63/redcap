#!/usr/bin/env python3
# 用途：知识沉淀与自进化脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
from datetime import datetime, timezone
from typing import Any


DEFAULT_LEDGER = "compass/evolution/harvest-ledger.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-evolution-harvest-producer] {message}")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: pathlib.Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be an object")
    return payload


def parse_fields(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in text.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$", raw)
        if match:
            result[match.group(1)] = match.group(2).strip()
    return result


def section(text: str, heading: str) -> str:
    capture = False
    level = 0
    buffer: list[str] = []
    for raw in text.splitlines():
        match = re.match(r"^(#+)\s*(.*?)\s*$", raw)
        if match:
            current_level = len(match.group(1))
            current_heading = match.group(2).strip()
            if capture and current_level <= level:
                break
            if current_heading == heading or current_heading.startswith(heading):
                capture = True
                level = current_level
                continue
        if capture:
            buffer.append(raw)
    return "\n".join(buffer).strip()


def truthy(value: str) -> bool:
    return value.strip().lower() in {"true", "yes", "1", "y"}


def lower_blob(*parts: str) -> str:
    return "\n".join(part for part in parts if part).lower()


def term_matches(text: str, term: str) -> bool:
    needle = term.lower()
    if re.fullmatch(r"[a-z0-9_-]+", needle):
        return re.search(rf"(?<![a-z0-9_-]){re.escape(needle)}(?![a-z0-9_-])", text) is not None
    return needle in text


def matched_harvest_reasons(meta: dict[str, str], task_text: str, report_text: str, policy: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for flag in policy["always_require_task_flags"]:
        if isinstance(flag, str) and truthy(meta.get(flag, "")):
            reasons.append(f"task-flag:{flag}")
    for field, terms in policy["task_field_keywords"].items():
        field_value = meta.get(str(field), "").lower()
        for term in terms if isinstance(terms, list) else []:
            if isinstance(term, str) and term_matches(field_value, term):
                reasons.append(f"task-field:{field}:{term}")
    combined = lower_blob(task_text, report_text)
    for group in policy["signal_groups"]:
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("id", "unknown"))
        terms = group.get("terms")
        if not isinstance(terms, list):
            continue
        for term in terms:
            if isinstance(term, str) and term_matches(combined, term):
                reasons.append(f"signal:{group_id}:{term}")
                break
    return sorted(set(reasons))


def source_kind_from_reasons(reasons: list[str]) -> str:
    joined = "\n".join(reasons)
    if "prism-review-signal" in joined:
        return "prism-verdict"
    if "test-failure-or-regression" in joined:
        return "test-failure"
    if "closeout-or-receipt-blocker" in joined:
        return "closeout-failure"
    if "runtime-resource-risk" in joined:
        return "host-behavior"
    if "user-correction-or-interrupt" in joined:
        return "user-correction"
    return "task-report"


def first_meaningful_line(text: str, fallback: str) -> str:
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("|") or line.startswith("#") or line in {"---"}:
            continue
        line = re.sub(r"^[-*]\s+", "", line)
        line = re.sub(r"`([^`]*)`", r"\1", line)
        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
        line = re.sub(r"\s+", " ", line).strip()
        if len(line) >= 30:
            return line
    return fallback


def build_candidate_payload(meta: dict[str, str], task_text: str, report_text: str, reasons: list[str]) -> dict[str, Any]:
    background = section(report_text, "一、需求背景")
    design = section(report_text, "二、方案讨论") or section(report_text, "三、落地结果")
    result = section(report_text, "五、验证结果") or section(report_text, "三、落地结果")
    task_goal = meta.get("top_goal") or meta.get("task_id") or "RedCap high-value task"
    return {
        "source_kind": source_kind_from_reasons(reasons),
        "problem_source": first_meaningful_line(background, f"Task {meta.get('task_id', 'unknown')} carried high-value Evolution harvest signals around: {task_goal}."),
        "solution": first_meaningful_line(design, f"RedCap must process this signal through Evolution harvest rather than relying only on a manually written report section: {task_goal}."),
        "final_effect": first_meaningful_line(result, f"The harvest record makes this signal visible to closeout and future status surfaces before the task can be considered complete: {task_goal}."),
        "recurrence_guard": "Keep the generated harvest record fresh by source digest; stale or missing records fail the harvest gate before closeout.",
    }


def source_digest(task_text: str, report_text: str) -> str:
    body = json.dumps({"task": task_text, "report": report_text}, ensure_ascii=False, sort_keys=True)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def slug(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-").lower()
    return safe[:80] or "unknown"


def resolve_report(root: pathlib.Path, task_file: pathlib.Path, meta: dict[str, str], report_arg: str) -> tuple[str, pathlib.Path]:
    report_rel = report_arg or meta.get("task_report", "")
    if not report_rel:
        fail("task has no task_report; active harvest needs a report source")
    report_path = pathlib.Path(report_rel)
    if report_path.is_absolute():
        return report_rel, report_path
    root_candidate = root / report_rel
    if root_candidate.exists():
        return report_rel, root_candidate
    return report_rel, task_file.parent / report_rel


def load_ledger(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "version": 1,
            "description": "Machine-generated RedCap Evolution harvest records. This ledger records active discovery outcomes; it is not a replacement for the candidate pool, lessons, identity proposals, or public arsenal.",
            "records": [],
        }
    payload = load_json(path, "harvest ledger")
    if payload.get("version") != 1:
        fail("harvest ledger version must be 1")
    if not isinstance(payload.get("records"), list):
        fail("harvest ledger records must be a list")
    return payload


def candidate_pool_status(root: pathlib.Path, candidate_id: str) -> str:
    if not candidate_id:
        return ""
    pool = load_json(root / "compass/evolution/candidates.json", "candidate pool")
    for item in pool.get("candidates", []):
        if isinstance(item, dict) and item.get("id") == candidate_id:
            return str(item.get("status") or "")
    return ""


def build_record(
    root: pathlib.Path,
    task_file: pathlib.Path,
    task_text: str,
    report_rel: str,
    report_text: str,
    meta: dict[str, str],
    reasons: list[str],
    args: argparse.Namespace,
) -> dict[str, Any]:
    record_id = args.record_id or f"HARVEST-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{slug(meta.get('task_id', 'task'))}"
    outcome = args.outcome
    status = "processed" if outcome in {"no-promote", "candidate"} else "deferred"
    decision: dict[str, Any]
    if outcome == "no-promote":
        reason = args.reason or (
            "Generated by active harvest: the signal is valuable, but this task handles it as direct implementation evidence rather than a separate promotion item."
        )
        decision = {"reason": reason}
    elif outcome == "deferred-with-owner":
        decision = {
            "owner": args.owner or "redcap",
            "next_trigger": args.next_trigger or "next explicit Evolution Factory or RedCap Forge tranche",
        }
    else:
        candidate_id = args.candidate_id or f"EVO-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-AUTO-{slug(meta.get('task_id', 'task'))}"
        pool_status = candidate_pool_status(root, candidate_id)
        decision = {
            "candidate_id": candidate_id,
            "candidate_pool_status": pool_status or "generated-only",
        }
        if not pool_status:
            status = "generated"
    evidence_paths = []
    if not args.report_only:
        task_rel = task_file.as_posix() if task_file.is_absolute() and not str(task_file).startswith(str(root)) else task_file.relative_to(root).as_posix() if task_file.is_absolute() else task_file.as_posix()
        evidence_paths.append(task_rel)
    evidence_paths.append(report_rel)
    if args.report_only and "references/backlogs/redcap-architecture-smell-governance.json" not in evidence_paths:
        evidence_paths.append("references/backlogs/redcap-architecture-smell-governance.json")
    for extra in args.evidence:
        if extra not in evidence_paths:
            evidence_paths.append(extra)
    return {
        "id": record_id,
        "task_id": meta.get("task_id", "unknown"),
        "source_report": report_rel,
        "source_digest": source_digest(task_text, report_text),
        "source_kind": source_kind_from_reasons(reasons),
        "reasons": reasons,
        "outcome": outcome,
        "status": status,
        "decision": decision,
        "generated_candidate": build_candidate_payload(meta, task_text, report_text, reasons),
        "evidence_paths": evidence_paths,
        "generated_by": "redcap-evolution-harvest-producer",
        "generated_at": now_iso(),
    }


def upsert_record(ledger: dict[str, Any], record: dict[str, Any]) -> None:
    records = ledger.setdefault("records", [])
    if not isinstance(records, list):
        fail("harvest ledger records must be a list")
    for index, existing in enumerate(records):
        if not isinstance(existing, dict):
            continue
        if existing.get("task_id") == record.get("task_id") and existing.get("source_report") == record.get("source_report"):
            records[index] = record
            return
    records.append(record)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate active RedCap Evolution harvest records.")
    parser.add_argument("root")
    parser.add_argument("--task-file", default=".dev-task.md")
    parser.add_argument("--report-only", action="store_true", help="harvest a historical report with synthetic task metadata")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--top-goal", default="")
    parser.add_argument("--report", default="")
    parser.add_argument("--ledger", default=DEFAULT_LEDGER)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--outcome", choices=["candidate", "no-promote", "deferred-with-owner"], default="no-promote")
    parser.add_argument("--reason", default="")
    parser.add_argument("--owner", default="")
    parser.add_argument("--next-trigger", default="")
    parser.add_argument("--candidate-id", default="")
    parser.add_argument("--record-id", default="")
    parser.add_argument("--evidence", action="append", default=[])
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()
    task_arg = pathlib.Path(args.task_file)
    task_file = task_arg if task_arg.is_absolute() else root / task_arg
    if args.report_only:
        if not args.task_id or not args.top_goal or not args.report:
            fail("--report-only requires --task-id, --top-goal, and --report")
        task_text = "\n".join(
            [
                "## 控制面元数据（机器校验）",
                f"task_id: {args.task_id}",
                f"top_goal: {args.top_goal}",
                "review_tranche: true",
                "bugfix_tranche: true",
                f"task_report: {args.report}",
                "",
                "## 已确认需求（执行依据）",
                args.top_goal,
                "",
            ]
        )
    else:
        task_text = read(task_file)
        if not task_text:
            fail(f"task file missing or unreadable: {task_file}")
    meta = parse_fields(task_text)
    policy = load_json(root / "references/evolution-harvest-signal-policy.json", "evolution harvest signal policy")
    report_rel, report_path = resolve_report(root, task_file, meta, args.report)
    report_text = read(report_path)
    if not report_text:
        fail(f"task report missing or unreadable: {report_rel}")
    reasons = matched_harvest_reasons(meta, task_text, report_text, policy)
    if not reasons:
        print("EVOLUTION_HARVEST_PRODUCER")
        print("status=skipped reason=no-high-value-signals")
        print("EVOLUTION_HARVEST_PRODUCER_OK")
        return 0
    record = build_record(root, task_file, task_text, report_rel, report_text, meta, reasons, args)
    if args.write:
        ledger_arg = pathlib.Path(args.ledger)
        ledger_path = ledger_arg if ledger_arg.is_absolute() else root / ledger_arg
        ledger = load_ledger(ledger_path)
        upsert_record(ledger, record)
        write_json(ledger_path, ledger)
    print("EVOLUTION_HARVEST_PRODUCER")
    print(f"task_id={record['task_id']}")
    print(f"record_id={record['id']}")
    print(f"outcome={record['outcome']}")
    print(f"status={record['status']}")
    print("reasons=" + ",".join(reasons))
    print("EVOLUTION_HARVEST_PRODUCER_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

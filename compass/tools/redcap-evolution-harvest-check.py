#!/usr/bin/env python3
# 用途：知识沉淀与自进化脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import json
import os
from typing import Any


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-evolution-harvest-check] {message}")


def read(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


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
            if current_heading == heading:
                capture = True
                level = current_level
                continue
        if capture:
            buffer.append(raw)
    return "\n".join(buffer).strip()


def run_strict_candidates(root: pathlib.Path) -> None:
    script = root / "compass/tools/redcap-evolution-candidate-check.sh"
    if not script.is_file():
        fail(f"missing candidate checker: {script}")
    completed = subprocess.run(
        ["bash", str(script), "--strict"],
        cwd=str(root),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stdout + completed.stderr).strip()
        fail("strict candidate check failed: " + detail)


def known_candidate_ids(root: pathlib.Path) -> set[str]:
    pool_path = root / "compass/evolution/candidates.json"
    try:
        pool = json.loads(pool_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"unable to read candidate pool: {exc}")
    candidates = pool.get("candidates")
    if not isinstance(candidates, list):
        fail("candidate pool candidates must be a list")
    ids: set[str] = set()
    for candidate in candidates:
        if isinstance(candidate, dict) and isinstance(candidate.get("id"), str):
            ids.add(candidate["id"])
    return ids


def candidate_statuses(root: pathlib.Path) -> dict[str, str]:
    pool_path = root / "compass/evolution/candidates.json"
    try:
        pool = json.loads(pool_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"unable to read candidate pool: {exc}")
    candidates = pool.get("candidates")
    if not isinstance(candidates, list):
        fail("candidate pool candidates must be a list")
    result: dict[str, str] = {}
    for candidate in candidates:
        if isinstance(candidate, dict) and isinstance(candidate.get("id"), str):
            result[candidate["id"]] = str(candidate.get("status") or "")
    return result


def source_digest(task_text: str, report_text: str) -> str:
    body = json.dumps({"task": task_text, "report": report_text}, ensure_ascii=False, sort_keys=True)
    return "sha256:" + json_hash(body)


def json_hash(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_harvest_ledger(root: pathlib.Path) -> dict[str, Any]:
    ledger_raw = os.environ.get("REDCAP_EVOLUTION_HARVEST_LEDGER", "compass/evolution/harvest-ledger.json")
    ledger_arg = pathlib.Path(ledger_raw)
    ledger_path = ledger_arg if ledger_arg.is_absolute() else root / ledger_arg
    if not ledger_path.exists():
        return {"version": 1, "records": []}
    try:
        payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"unable to read evolution harvest ledger: {exc}")
    if not isinstance(payload, dict) or payload.get("version") != 1:
        fail("evolution harvest ledger must be a version=1 object")
    if not isinstance(payload.get("records"), list):
        fail("evolution harvest ledger records must be a list")
    return payload


def find_harvest_record(
    root: pathlib.Path,
    task_id: str,
    report_rel: str,
    digest: str,
) -> dict[str, Any] | None:
    stale_record: dict[str, Any] | None = None
    ledger = load_harvest_ledger(root)
    for record in ledger["records"]:
        if not isinstance(record, dict):
            fail("evolution harvest ledger records must be objects")
        if record.get("task_id") != task_id or record.get("source_report") != report_rel:
            continue
        if record.get("source_digest") == digest:
            return record
        stale_record = record
    if stale_record is not None:
        fail(
            "Evolution harvest ledger record is stale for "
            f"{task_id}; run redcap-evolution-harvest-producer.sh --task-file <task> --write"
        )
    return None


def validate_harvest_record(root: pathlib.Path, record: dict[str, Any], task_id: str, report_rel: str) -> None:
    record_id = record.get("id")
    if not isinstance(record_id, str) or not record_id.strip():
        fail("Evolution harvest ledger record missing id")
    status = record.get("status")
    outcome = record.get("outcome")
    if status not in {"processed", "deferred"}:
        fail(f"Evolution harvest ledger record is unprocessed: {record_id}")
    if outcome not in {"candidate", "no-promote", "deferred-with-owner"}:
        fail(f"Evolution harvest ledger record has unsupported outcome: {record_id}")
    if not isinstance(record.get("reasons"), list) or not record["reasons"]:
        fail(f"Evolution harvest ledger record missing reasons: {record_id}")
    evidence_paths = record.get("evidence_paths")
    if not isinstance(evidence_paths, list) or len(evidence_paths) < 2:
        fail(f"Evolution harvest ledger record missing evidence paths: {record_id}")
    if report_rel not in evidence_paths:
        fail(f"Evolution harvest ledger record does not cite task report: {record_id}")
    decision = record.get("decision")
    if not isinstance(decision, dict):
        fail(f"Evolution harvest ledger record missing decision: {record_id}")
    if outcome == "candidate":
        candidate_id = decision.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            fail(f"candidate harvest record missing candidate_id: {record_id}")
        statuses = candidate_statuses(root)
        pool_status = statuses.get(candidate_id)
        if not pool_status:
            fail(f"candidate harvest record references unknown candidate: {candidate_id}")
        if pool_status in {"candidate", "reviewing"}:
            fail(f"candidate harvest record references unresolved candidate: {candidate_id}")
    elif outcome == "no-promote":
        reason = decision.get("reason")
        if not isinstance(reason, str) or len(reason.strip()) < 20:
            fail(f"no-promote harvest record missing reason: {record_id}")
    elif outcome == "deferred-with-owner":
        owner = decision.get("owner")
        trigger = decision.get("next_trigger")
        if not isinstance(owner, str) or not owner.strip():
            fail(f"deferred harvest record missing owner: {record_id}")
        if not isinstance(trigger, str) or len(trigger.strip()) < 10:
            fail(f"deferred harvest record missing next_trigger: {record_id}")
    if record.get("task_id") != task_id:
        fail(f"Evolution harvest ledger record task_id mismatch: {record_id}")


def load_signal_policy(root: pathlib.Path) -> dict[str, Any]:
    policy_path = root / "references/evolution-harvest-signal-policy.json"
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"unable to read evolution harvest signal policy: {exc}")
    if not isinstance(policy, dict):
        fail("evolution harvest signal policy must be an object")
    if policy.get("version") != 1:
        fail("evolution harvest signal policy version must be 1")
    if policy.get("policy_id") != "redcap-evolution-harvest-signal-policy":
        fail("evolution harvest signal policy id mismatch")
    for key in ["always_require_task_flags", "task_field_keywords", "signal_groups", "required_report_section"]:
        if key not in policy:
            fail(f"evolution harvest signal policy missing {key}")
    if not isinstance(policy["always_require_task_flags"], list) or not policy["always_require_task_flags"]:
        fail("evolution harvest signal policy always_require_task_flags must be non-empty")
    if not isinstance(policy["task_field_keywords"], dict):
        fail("evolution harvest signal policy task_field_keywords must be an object")
    if not isinstance(policy["signal_groups"], list) or not policy["signal_groups"]:
        fail("evolution harvest signal policy signal_groups must be non-empty")
    return policy


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
        if not isinstance(field, str) or not isinstance(terms, list):
            fail("evolution harvest signal policy task_field_keywords entries must be string -> list")
        field_value = meta.get(field, "").lower()
        for term in terms:
            if isinstance(term, str) and term_matches(field_value, term):
                reasons.append(f"task-field:{field}:{term}")

    combined = lower_blob(task_text, report_text)
    for group in policy["signal_groups"]:
        if not isinstance(group, dict):
            fail("evolution harvest signal policy signal_groups entries must be objects")
        group_id = group.get("id")
        terms = group.get("terms")
        if not isinstance(group_id, str) or not isinstance(terms, list) or not terms:
            fail("evolution harvest signal policy signal group must have id and terms")
        for term in terms:
            if isinstance(term, str) and term_matches(combined, term):
                reasons.append(f"signal:{group_id}:{term}")
                break
    return sorted(set(reasons))


def validate_deferred_with_owner(body: str) -> None:
    if "deferred-with-owner" not in body:
        return
    if not re.search(r"\bowner\s*[:=]", body, flags=re.IGNORECASE):
        fail("deferred-with-owner outcome must include owner=<owner>")
    if not re.search(r"\b(next\s+trigger|trigger)\s*[:=]", body, flags=re.IGNORECASE):
        fail("deferred-with-owner outcome must include trigger=<next trigger>")


def main() -> None:
    if len(sys.argv) != 3:
        fail("usage: redcap-evolution-harvest-check.py <redcap_root> <task_file>")

    root = pathlib.Path(sys.argv[1]).resolve()
    task_file_arg = pathlib.Path(sys.argv[2])
    task_file = task_file_arg if task_file_arg.is_absolute() else root / task_file_arg
    task_text = read(task_file)
    if not task_text:
        fail(f"task file missing or unreadable: {task_file}")
    meta = parse_fields(task_text)
    policy = load_signal_policy(root)
    report_rel = meta.get("task_report", "")
    report_text = ""
    if report_rel:
        report_path = pathlib.Path(report_rel)
        if not report_path.is_absolute():
            report_path = root / report_path
            if not report_path.exists():
                report_path = task_file.parent / report_rel
        report_text = read(report_path)
    reasons = matched_harvest_reasons(meta, task_text, report_text, policy)
    if not reasons:
        print("EVOLUTION_HARVEST")
        print("status=skipped reason=no-high-value-signals")
        print("EVOLUTION_HARVEST_OK")
        return
    if not report_rel:
        fail("high-value evolution harvest signals require task_report; reasons=" + ",".join(reasons))
    if not report_text:
        fail(f"high-value evolution harvest task report missing or unreadable: {report_rel}")

    digest = source_digest(task_text, report_text)
    record = find_harvest_record(root, meta.get("task_id", ""), report_rel, digest)
    if record is None:
        fail(
            "high-value evolution harvest signals require generated harvest ledger record; "
            "run redcap-evolution-harvest-producer.sh --task-file <task> --write; reasons="
            + ",".join(reasons)
        )
    validate_harvest_record(root, record, meta.get("task_id", ""), report_rel)

    required_section = str(policy["required_report_section"])
    body = section(report_text, required_section)
    if not body:
        print("EVOLUTION_HARVEST")
        print(f"task_report={report_rel}")
        print("required=true")
        print("report_section=missing")
        print(f"harvest_record={record.get('id')}")
        print("reasons=" + ",".join(reasons))
        print("strict_candidates=pass")
        run_strict_candidates(root)
        print("EVOLUTION_HARVEST_OK")
        return
    referenced_ids = set(re.findall(r"\bEVO-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{3}\b", body))
    if not referenced_ids and not re.search(r"无新增候选|no-promote|deferred-with-owner", body):
        fail("Evolution candidate handling must reference candidate ids, no-promote, deferred-with-owner, or 无新增候选")
    validate_deferred_with_owner(body)
    missing_ids = sorted(referenced_ids - known_candidate_ids(root))
    if missing_ids:
        fail("Evolution candidate handling references unknown candidate ids: " + ", ".join(missing_ids))

    run_strict_candidates(root)

    print("EVOLUTION_HARVEST")
    print(f"task_report={report_rel}")
    print("required=true")
    print(f"harvest_record={record.get('id')}")
    print("reasons=" + ",".join(reasons))
    print("strict_candidates=pass")
    print("EVOLUTION_HARVEST_OK")


if __name__ == "__main__":
    main()

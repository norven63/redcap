#!/usr/bin/env python3
"""RedCap task fact ledger: append-only task status truth surface."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "runtime" / "core"))
import runtime_boundary  # noqa: E402

DEFAULT_LEDGER = REPO_ROOT / "assets" / "evidence" / "task-facts" / "task-facts.jsonl"
DEFAULT_HEALTH = REPO_ROOT / "assets" / "evidence" / "task-facts" / "task-facts-summary.json"
STATUSES = {"planned", "in_progress", "verified", "blocked", "escalated", "superseded"}
OPEN_STATUSES = {"planned", "in_progress", "blocked", "escalated"}
AUTO_REOPEN_TRIGGERS = [
    {
        "source_task_id": "full-360-old-redcap-scan",
        "source_statuses": {"blocked", "escalated"},
        "target_task_id": "pre-revival-zero-tail-infra-batch",
        "target_title": "复活前零尾巴基建批次",
        "target_status": "escalated",
        "reason": (
            "360 度旧 RedCap 扫描被记录为失败或升级，自动重开复活前基建父批次；"
            "需要先判断失败是否来自超时、中文输出、hook、考古入口或其他前置基建。"
        ),
    }
]


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def write_json_atomic(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_records(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid task fact ledger line {line_number}: {exc}") from exc
        if isinstance(record, dict):
            records.append(record)
    return records


def boundary_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        runtime_root=getattr(args, "runtime_root", None),
        project_workspace=getattr(args, "project_workspace", None),
        cwd=getattr(args, "cwd", None),
        task_file=getattr(args, "task_file", None),
        task_id=getattr(args, "task_id", "") or "",
        user_private_root=getattr(args, "user_private_root", None),
        project_runtime_root=getattr(args, "project_runtime_root", None),
        state_root=getattr(args, "state_root", None),
        evidence_root=getattr(args, "evidence_root", None),
        require_task_file=False,
    )


def resolve_store_paths(args: argparse.Namespace, *, create: bool) -> tuple[pathlib.Path, pathlib.Path, dict[str, Any]]:
    explicit_ledger = getattr(args, "ledger", None)
    explicit_health = getattr(args, "health", None)
    if explicit_ledger or explicit_health:
        ledger = pathlib.Path(explicit_ledger or DEFAULT_LEDGER).resolve()
        health = pathlib.Path(explicit_health or DEFAULT_HEALTH).resolve()
        return ledger, health, {
            "schema_id": "redcap-task-facts-store-paths",
            "mode": "explicit",
            "ledger": str(ledger),
            "health": str(health),
        }
    context = runtime_boundary.build_context(boundary_args(args))
    if create and context.get("boundary_mode") == "external-workspace":
        runtime_boundary.initialize_runtime_dirs(context)
        context = runtime_boundary.build_context(boundary_args(args))
    failures = runtime_boundary.validate_context(context, require_task_file=False)
    if failures:
        raise SystemExit(json.dumps({
            "ok": False,
            "failures": failures,
            "context": context,
        }, ensure_ascii=False, indent=2))
    evidence_root = pathlib.Path(context["evidence_root"]).resolve()
    ledger = evidence_root / "task-facts" / "task-facts.jsonl"
    health = evidence_root / "task-facts" / "task-facts-summary.json"
    return ledger, health, {
        "schema_id": "redcap-task-facts-store-paths",
        "mode": "boundary",
        "boundary_mode": context.get("boundary_mode"),
        "project_workspace": context.get("project_workspace"),
        "project_runtime_root": context.get("project_runtime_root"),
        "evidence_root": context.get("evidence_root"),
        "ledger": str(ledger),
        "health": str(health),
    }


def latest_by_task(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        task_id = str(record.get("task_id") or "")
        if not task_id:
            continue
        existing = latest.get(task_id)
        if existing is None or str(record.get("recorded_at") or "") >= str(existing.get("recorded_at") or ""):
            latest[task_id] = record
    return latest


def validate_record(record: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for key in ["task_id", "title", "status", "reason"]:
        if not (isinstance(record.get(key), str) and record[key].strip()):
            failures.append(f"{key} must be a non-empty string")
    if record.get("status") not in STATUSES:
        failures.append(f"status must be one of: {', '.join(sorted(STATUSES))}")
    evidence = record.get("evidence")
    if not isinstance(evidence, list) or not evidence or not all(isinstance(item, str) and item.strip() for item in evidence):
        failures.append("evidence must be a non-empty string list")
    if record.get("status") == "superseded" and not (isinstance(record.get("superseded_by"), str) and record["superseded_by"].strip()):
        failures.append("superseded status requires superseded_by")
    return failures


def build_record(args: argparse.Namespace) -> dict[str, Any]:
    seed = json.dumps(
        {
            "task_id": args.task_id,
            "status": args.status,
            "title": args.title,
            "recorded_at": iso_now(),
            "reason": args.reason,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return {
        "schema_id": "redcap-task-fact-record",
        "schema_version": 1,
        "fact_id": hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24],
        "recorded_at": iso_now(),
        "recorded_by": args.recorded_by,
        "task_id": args.task_id,
        "title": args.title,
        "status": args.status,
        "reason": args.reason,
        "source": args.source,
        "evidence": args.evidence,
        "superseded_by": args.superseded_by,
    }


def build_auto_record(
    *,
    task_id: str,
    title: str,
    status: str,
    reason: str,
    source: str,
    evidence: list[str],
    recorded_by: str,
) -> dict[str, Any]:
    args = argparse.Namespace(
        task_id=task_id,
        title=title,
        status=status,
        reason=reason,
        source=source,
        evidence=evidence,
        superseded_by=None,
        recorded_by=recorded_by,
    )
    return build_record(args)


def compute_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    latest = latest_by_task(records)
    latest_records = list(latest.values())
    status_counts = {status: 0 for status in sorted(STATUSES)}
    for record in latest_records:
        status = record.get("status")
        if status in status_counts:
            status_counts[status] += 1
    open_records = [record for record in latest_records if record.get("status") in OPEN_STATUSES]
    return {
        "schema_id": "redcap-task-fact-summary",
        "computed_at": iso_now(),
        "record_count": len(records),
        "task_count": len(latest_records),
        "status_counts": status_counts,
        "open_count": len(open_records),
        "open_tasks": [
            {
                "task_id": record.get("task_id"),
                "title": record.get("title"),
                "status": record.get("status"),
                "reason": record.get("reason"),
                "recorded_at": record.get("recorded_at"),
            }
            for record in sorted(open_records, key=lambda item: str(item.get("recorded_at") or ""), reverse=True)
        ],
    }


def auto_reopen_records(trigger_record: dict[str, Any], existing_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    generated: list[dict[str, Any]] = []
    task_id = trigger_record.get("task_id")
    status = trigger_record.get("status")
    latest = latest_by_task(existing_records)
    for trigger in AUTO_REOPEN_TRIGGERS:
        if task_id != trigger["source_task_id"] or status not in trigger["source_statuses"]:
            continue
        target_task_id = str(trigger["target_task_id"])
        target_latest = latest.get(target_task_id)
        if target_latest is not None and target_latest.get("status") in OPEN_STATUSES:
            continue
        generated.append(build_auto_record(
            task_id=target_task_id,
            title=str(trigger["target_title"]),
            status=str(trigger["target_status"]),
            reason=str(trigger["reason"]),
            source="auto-reopen-on-scan-failure",
            evidence=[
                f"trigger_task:{trigger_record.get('task_id')}",
                f"trigger_status:{trigger_record.get('status')}",
                str(trigger_record.get("fact_id") or ""),
            ],
            recorded_by="task-facts-auto-reopen",
        ))
    return generated


def append_record(record: dict[str, Any], ledger: pathlib.Path, health: pathlib.Path) -> dict[str, Any]:
    failures = validate_record(record)
    if failures:
        raise SystemExit(json.dumps({"ok": False, "failures": failures}, ensure_ascii=False, indent=2))
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    summary = compute_summary(read_records(ledger))
    write_json_atomic(health, summary)
    return {"record": record, "summary": summary, "ledger_path": str(ledger), "health_path": str(health)}


def cmd_record(args: argparse.Namespace) -> int:
    ledger, health, store_paths = resolve_store_paths(args, create=True)
    payload = append_record(
        build_record(args),
        ledger,
        health,
    )
    payload["store_paths"] = store_paths
    generated = []
    records_after = read_records(ledger)
    for auto_record in auto_reopen_records(payload["record"], records_after):
        generated_payload = append_record(auto_record, ledger, health)
        generated.append(generated_payload["record"])
    if generated:
        payload["auto_reopen_records"] = generated
        payload["summary"] = compute_summary(read_records(ledger))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("REDCAP_TASK_FACT_RECORD_OK")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    ledger, _, store_paths = resolve_store_paths(args, create=False)
    records = read_records(ledger)
    summary = compute_summary(records)
    summary["store_paths"] = store_paths
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("REDCAP_TASK_FACT_SUMMARY_OK")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    ledger, _, store_paths = resolve_store_paths(args, create=False)
    records = read_records(ledger)
    summary = compute_summary(records)
    failures: list[str] = []
    for record in records:
        failures.extend(f"{record.get('task_id')}: {failure}" for failure in validate_record(record))
    if args.fail_on_open and summary.get("open_count", 0) > 0:
        failures.append(f"open task facts remain: {summary.get('open_count')}")
    print(json.dumps({"ok": not failures, "failures": failures, "summary": summary, "store_paths": store_paths}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_TASK_FACTS_OK")
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="redcap-task-facts-") as tmp_raw:
        tmp = pathlib.Path(tmp_raw)
        ledger = tmp / "facts.jsonl"
        health = tmp / "facts-summary.json"
        record_args = argparse.Namespace(
            task_id="fixture-task",
            title="Fixture task",
            status="in_progress",
            reason="Fixture records an open task.",
            source="self-check",
            evidence=["runtime/core/task_facts.py"],
            superseded_by=None,
            recorded_by="self-check",
            ledger=str(ledger),
            health=str(health),
        )
        append_record(build_record(record_args), ledger, health)
        record_args.status = "verified"
        record_args.reason = "Fixture records a verified task."
        append_record(build_record(record_args), ledger, health)
        summary = compute_summary(read_records(ledger))
        failures: list[str] = []
        if summary.get("open_count") != 0:
            failures.append("verified latest record should close the task")
        bad = dict(build_record(record_args))
        bad["status"] = "superseded"
        bad["superseded_by"] = None
        if not validate_record(bad):
            failures.append("superseded record without superseded_by should fail")
        parent_args = argparse.Namespace(
            task_id="pre-revival-zero-tail-infra-batch",
            title="复活前零尾巴基建批次",
            status="verified",
            reason="Fixture records a conditionally closed parent batch.",
            source="self-check",
            evidence=["runtime/core/task_facts.py"],
            superseded_by=None,
            recorded_by="self-check",
            ledger=str(ledger),
            health=str(health),
        )
        append_record(build_record(parent_args), ledger, health)
        scan_args = argparse.Namespace(
            task_id="full-360-old-redcap-scan",
            title="360 度旧 RedCap 扫描归纳",
            status="blocked",
            reason="Fixture scan failure should reopen parent batch.",
            source="self-check",
            evidence=["runtime/core/task_facts.py"],
            superseded_by=None,
            recorded_by="self-check",
            ledger=str(ledger),
            health=str(health),
        )
        scan_payload = append_record(build_record(scan_args), ledger, health)
        for auto_record in auto_reopen_records(scan_payload["record"], read_records(ledger)):
            append_record(auto_record, ledger, health)
        reopened_summary = compute_summary(read_records(ledger))
        reopened_latest = latest_by_task(read_records(ledger)).get("pre-revival-zero-tail-infra-batch", {})
        if reopened_latest.get("status") != "escalated":
            failures.append("360 scan failure should automatically reopen parent batch as escalated")
        if reopened_summary.get("open_count", 0) < 2:
            failures.append("reopened parent and failed scan should both be open")
        print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
        if failures:
            return 1
        print("REDCAP_TASK_FACTS_SELF_CHECK_OK")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap task fact ledger")
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record", help="append a task fact")
    record.add_argument("--task-id", required=True)
    record.add_argument("--title", required=True)
    record.add_argument("--status", required=True, choices=sorted(STATUSES))
    record.add_argument("--reason", required=True)
    record.add_argument("--source", default="manual")
    record.add_argument("--evidence", action="append", required=True)
    record.add_argument("--superseded-by")
    record.add_argument("--recorded-by", default="cap")
    add_boundary_args(record)
    record.add_argument("--ledger")
    record.add_argument("--health")
    record.set_defaults(func=cmd_record)

    summary = sub.add_parser("summary", help="print task fact summary")
    add_boundary_args(summary)
    summary.add_argument("--ledger")
    summary.add_argument("--health")
    summary.set_defaults(func=cmd_summary)

    check = sub.add_parser("check", help="validate task fact ledger")
    add_boundary_args(check)
    check.add_argument("--ledger")
    check.add_argument("--health")
    check.add_argument("--fail-on-open", action="store_true")
    check.set_defaults(func=cmd_check)

    self_check = sub.add_parser("self-check", help="run isolated task fact self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def add_boundary_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--runtime-root")
    parser.add_argument("--project-workspace")
    parser.add_argument("--cwd")
    parser.add_argument("--task-file")
    parser.add_argument("--user-private-root")
    parser.add_argument("--project-runtime-root")
    parser.add_argument("--state-root")
    parser.add_argument("--evidence-root")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

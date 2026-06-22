#!/usr/bin/env python3
"""Append-only Prism task execution ledger and health summary."""

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


ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
sys.path.insert(0, str(ROOT / "lib"))
from prism_lock import file_lock, write_json_atomic  # noqa: E402

def prism_runtime_evidence_root() -> pathlib.Path:
    if REPO_ROOT.name == ".redcap":
        return REPO_ROOT / "evidence" / "prism"
    return REPO_ROOT / ".redcap" / "evidence" / "prism"


def configured_path(env_name: str, default: pathlib.Path) -> pathlib.Path:
    raw = os.environ.get(env_name)
    if raw and raw.strip():
        return pathlib.Path(raw).expanduser().resolve()
    return default.resolve()


DEFAULT_LEDGER = configured_path(
    "REDCAP_PRISM_LEDGER",
    prism_runtime_evidence_root() / "task-ledger.jsonl",
)
DEFAULT_HEALTH = configured_path(
    "REDCAP_PRISM_HEALTH",
    prism_runtime_evidence_root() / "task-health.json",
)
DEFAULT_TASK_FACTS = REPO_ROOT / ".redcap" / "evidence" / "task-facts" / "task-facts.jsonl"
PASSING_VERDICTS = {None, "pass"}
SUCCESS_STATES = {"converged", "main-decided"}
GATE_DECISIONS = {"required", "optional", "skipped"}
UNHEALTHY_OUTCOMES = {"active", "failed", "attention", "closed_without_success"}


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def duration_seconds(start: Any, end: Any) -> float | None:
    started = parse_time(start)
    ended = parse_time(end)
    if not started or not ended:
        return None
    return max(0.0, round((ended - started).total_seconds(), 3))


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}") from exc


def sha256_file(path: pathlib.Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def resolve_relative(base: pathlib.Path, value: Any) -> pathlib.Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = pathlib.Path(value)
    if path.is_absolute():
        return path.resolve()
    candidates = [
        (base / path).resolve(),
        (REPO_ROOT / path).resolve(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def load_review(path: pathlib.Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    payload = load_json(path)
    return payload if isinstance(payload, dict) else None


def latest_merge(run_dir: pathlib.Path) -> dict[str, Any] | None:
    candidates = sorted(run_dir.glob("merge*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not candidates:
        return None
    payload = load_json(candidates[0])
    if not isinstance(payload, dict):
        return None
    payload["_path"] = str(candidates[0])
    return payload


def provider_snapshot(run_dir: pathlib.Path, provider: str, record: dict[str, Any]) -> dict[str, Any]:
    review_path = resolve_relative(run_dir, record.get("last_review"))
    review = load_review(review_path)
    verdict = review.get("verdict") if review else None
    confidence = review.get("confidence") if review else None
    return {
        "provider": provider,
        "status": record.get("status"),
        "round_count": record.get("round_count", 0),
        "has_session_handle": bool(record.get("session_handle")),
        "last_review_path": str(review_path) if review_path else None,
        "last_review_sha256": sha256_file(review_path) if review_path else None,
        "last_verdict": verdict,
        "last_confidence": confidence,
        "review_loaded": review is not None,
    }


def classify_success(payload: dict[str, Any], strictest_verdict: str | None) -> tuple[bool, str]:
    status = payload.get("status")
    state = (payload.get("convergence") or {}).get("state")
    if status == "active" or state == "unresolved":
        return False, "active"
    if state in SUCCESS_STATES and strictest_verdict in PASSING_VERDICTS:
        return True, "success"
    if state == "main-decided" and strictest_verdict in {"concern", "block"}:
        return True, "resolved_with_concern"
    if status in {"escalated", "expired"} or state == "escalated":
        return False, "failed"
    if strictest_verdict in {"concern", "block"}:
        return False, "attention"
    return False, "closed_without_success"


def effective_outcome(record: dict[str, Any]) -> str:
    status = record.get("status")
    state = record.get("convergence_state")
    strictest_verdict = record.get("strictest_verdict")
    if status == "active" or state == "unresolved":
        return "active"
    if state in SUCCESS_STATES and strictest_verdict in PASSING_VERDICTS:
        return "success"
    if state == "main-decided" and strictest_verdict in {"concern", "block"}:
        return "resolved_with_concern"
    if status in {"escalated", "expired"} or state == "escalated":
        return "failed"
    if strictest_verdict in {"concern", "block"}:
        return "attention"
    return str(record.get("outcome") or "closed_without_success")


def execution_class(task_id: Any, run_dir: pathlib.Path, trigger: str) -> str:
    text = f"{task_id or ''} {run_dir} {trigger}".lower()
    if "self-check" in text or "/tmp/" in text or "/var/folders/" in text:
        return "self_check"
    return "operational"


def build_record(
    manifest_path: pathlib.Path,
    *,
    trigger: str = "manual",
    executor: str = "prism",
) -> dict[str, Any]:
    payload = load_json(manifest_path)
    if not isinstance(payload, dict):
        raise SystemExit(f"session manifest must be an object: {manifest_path}")
    run_dir = pathlib.Path(str(payload.get("run_dir") or manifest_path.parent)).resolve()
    providers_payload = payload.get("providers") or {}
    providers = {
        provider: provider_snapshot(run_dir, provider, record)
        for provider, record in sorted(providers_payload.items())
        if isinstance(record, dict)
    }
    merge = latest_merge(run_dir)
    strictest_verdict = merge.get("strictest_verdict") if merge else None
    success, outcome = classify_success(payload, strictest_verdict)
    record = {
        "schema_id": "prism-task-execution-record",
        "schema_version": 1,
        "recorded_at": iso_now(),
        "trigger": trigger,
        "executor": executor,
        "execution_class": execution_class(payload.get("task_id"), run_dir, trigger),
        "task_id": payload.get("task_id"),
        "session_manifest": str(manifest_path),
        "session_manifest_sha256": sha256_file(manifest_path),
        "run_dir": str(run_dir),
        "status": payload.get("status"),
        "convergence_state": (payload.get("convergence") or {}).get("state"),
        "convergence_reason": (payload.get("convergence") or {}).get("reason"),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
        "duration_seconds": duration_seconds(payload.get("created_at"), payload.get("updated_at")),
        "provider_count": len(providers),
        "total_rounds": sum(int(item.get("round_count") or 0) for item in providers.values()),
        "providers": providers,
        "strictest_verdict": strictest_verdict,
        "strictest_provider": merge.get("strictest_provider") if merge else None,
        "merge_path": merge.get("_path") if merge else None,
        "success": success,
        "outcome": outcome,
    }
    return record


def fingerprint_text(value: Any) -> dict[str, Any]:
    text = value if isinstance(value, str) else ""
    return {
        "present": isinstance(value, str),
        "length": len(text),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None,
    }


def build_gate_record(
    request: dict[str, Any],
    result: dict[str, Any],
    *,
    trigger: str = "cli-gate",
    executor: str = "prism",
    started_at: str | None = None,
    ended_at: str | None = None,
    duration_seconds_value: float | None = None,
    planned_exit_code: int = 0,
) -> dict[str, Any]:
    started_at = started_at or iso_now()
    ended_at = ended_at or iso_now()
    if duration_seconds_value is None:
        duration_seconds_value = duration_seconds(started_at, ended_at)
    decision = result.get("decision")
    task_fingerprint = fingerprint_text(request.get("task"))
    event_seed = json.dumps(
        {
            "started_at": started_at,
            "trigger": trigger,
            "executor": executor,
            "task_sha256": task_fingerprint["sha256"],
            "risk_level": request.get("risk_level"),
            "tags": request.get("tags", []),
            "changed_paths": request.get("changed_paths", []),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return {
        "schema_id": "prism-gate-evaluation-record",
        "schema_version": 1,
        "record_type": "gate",
        "recorded_at": iso_now(),
        "gate_event_id": hashlib.sha256(event_seed.encode("utf-8")).hexdigest()[:24],
        "trigger": trigger,
        "executor": executor,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_seconds": duration_seconds_value,
        "task": task_fingerprint,
        "task_id": request.get("task_id"),
        "risk_level": request.get("risk_level", "medium"),
        "tags": request.get("tags", []),
        "changed_path_count": len(request.get("changed_paths", []) or []),
        "decision": decision,
        "review_mode": result.get("review_mode"),
        "matched_rules": result.get("matched_rules", []),
        "required_providers": result.get("required_providers", []),
        "planned_exit_code": planned_exit_code,
        "success": decision in GATE_DECISIONS,
        "outcome": f"gate-{decision}" if decision in GATE_DECISIONS else "gate-invalid",
    }


def read_records(ledger_path: pathlib.Path) -> list[dict[str, Any]]:
    if not ledger_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid jsonl at {ledger_path}:{line_number}: {exc}") from exc
        if isinstance(payload, dict):
            records.append(payload)
    return records


def is_session_record(record: dict[str, Any]) -> bool:
    return record.get("schema_id") == "prism-task-execution-record"


def is_gate_record(record: dict[str, Any]) -> bool:
    return record.get("schema_id") == "prism-gate-evaluation-record"


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


def task_fact_statuses(path: pathlib.Path) -> dict[str, str]:
    statuses: dict[str, str] = {}
    if not path.exists():
        return statuses
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        task_id = record.get("task_id")
        status = record.get("status")
        if isinstance(task_id, str) and task_id and isinstance(status, str) and status:
            statuses[task_id] = status
    return statuses


def gate_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    gate_records = [record for record in records if is_gate_record(record)]
    durations = [
        float(record["duration_seconds"])
        for record in gate_records
        if isinstance(record.get("duration_seconds"), (int, float))
    ]
    decision_counts = {decision: 0 for decision in sorted(GATE_DECISIONS)}
    trigger_counts: dict[str, int] = {}
    for record in gate_records:
        decision = record.get("decision")
        if decision in decision_counts:
            decision_counts[decision] += 1
        trigger = str(record.get("trigger") or "unknown")
        trigger_counts[trigger] = trigger_counts.get(trigger, 0) + 1
    success_count = sum(1 for record in gate_records if record.get("success") is True)
    return {
        "gate_event_count": len(gate_records),
        "gate_success_count": success_count,
        "gate_success_rate": round(success_count / len(gate_records), 4) if gate_records else None,
        "gate_decision_counts": decision_counts,
        "gate_trigger_counts": trigger_counts,
        "gate_average_duration_seconds": round(sum(durations) / len(durations), 3) if durations else None,
    }


def compute_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    session_records = [record for record in records if is_session_record(record)]
    latest = latest_by_task(session_records)
    task_records = list(latest.values())
    operational_records = [
        record
        for record in task_records
        if (
            record.get("execution_class")
            or execution_class(record.get("task_id"), pathlib.Path(str(record.get("run_dir") or "")), str(record.get("trigger") or ""))
        )
        not in {"self_check", "fixture"}
    ]
    success_count = sum(1 for record in task_records if record.get("success") is True)
    operational_success_count = sum(1 for record in operational_records if record.get("success") is True)
    active_count = sum(1 for record in task_records if effective_outcome(record) == "active")
    operational_active_count = sum(
        1 for record in operational_records if effective_outcome(record) == "active"
    )
    attention_count = sum(
        1
        for record in task_records
        if effective_outcome(record) in UNHEALTHY_OUTCOMES
    )
    durations = [
        float(record["duration_seconds"])
        for record in task_records
        if isinstance(record.get("duration_seconds"), (int, float))
    ]
    provider_stats: dict[str, dict[str, Any]] = {}
    for record in task_records:
        for provider, snapshot in (record.get("providers") or {}).items():
            stats = provider_stats.setdefault(
                provider,
                {
                    "tasks": 0,
                    "rounds": 0,
                    "reviews_loaded": 0,
                    "pass": 0,
                    "concern": 0,
                    "block": 0,
                    "missing_verdict": 0,
                },
            )
            stats["tasks"] += 1
            stats["rounds"] += int(snapshot.get("round_count") or 0)
            if snapshot.get("review_loaded"):
                stats["reviews_loaded"] += 1
            verdict = snapshot.get("last_verdict")
            if verdict in {"pass", "concern", "block"}:
                stats[verdict] += 1
            else:
                stats["missing_verdict"] += 1
    task_count = len(task_records)
    operational_task_count = len(operational_records)
    summary = {
        "schema_id": "prism-task-health-summary",
        "computed_at": iso_now(),
        "event_count": len(records),
        "session_event_count": len(session_records),
        "task_count": task_count,
        "success_count": success_count,
        "success_rate": round(success_count / task_count, 4) if task_count else None,
        "operational_task_count": operational_task_count,
        "operational_success_count": operational_success_count,
        "operational_success_rate": (
            round(operational_success_count / operational_task_count, 4)
            if operational_task_count
            else None
        ),
        "self_check_task_count": task_count - operational_task_count,
        "active_count": active_count,
        "operational_active_count": operational_active_count,
        "attention_count": attention_count,
        "average_duration_seconds": round(sum(durations) / len(durations), 3) if durations else None,
        "providers": provider_stats,
        "recent_attention_tasks": [
            {
                "task_id": record.get("task_id"),
                "outcome": effective_outcome(record),
                "strictest_verdict": record.get("strictest_verdict"),
                "recorded_at": record.get("recorded_at"),
            }
            for record in sorted(
                task_records,
                key=lambda item: str(item.get("recorded_at") or ""),
                reverse=True,
            )
            if effective_outcome(record) in UNHEALTHY_OUTCOMES
        ][:10],
    }
    summary.update(gate_summary(records))
    return summary


def append_record(
    record: dict[str, Any],
    *,
    ledger_path: pathlib.Path = DEFAULT_LEDGER,
    health_path: pathlib.Path = DEFAULT_HEALTH,
) -> dict[str, Any]:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(ledger_path):
        with ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        summary = compute_summary(read_records(ledger_path))
        write_json_atomic(health_path, summary)
    return summary


def record_manifest(
    manifest_path: pathlib.Path,
    *,
    trigger: str = "manual",
    executor: str = "prism",
    ledger_path: pathlib.Path = DEFAULT_LEDGER,
    health_path: pathlib.Path = DEFAULT_HEALTH,
) -> dict[str, Any]:
    record = build_record(manifest_path.resolve(), trigger=trigger, executor=executor)
    summary = append_record(record, ledger_path=ledger_path, health_path=health_path)
    return {"record": record, "summary": summary, "ledger_path": str(ledger_path), "health_path": str(health_path)}


def record_gate(
    request: dict[str, Any],
    result: dict[str, Any],
    *,
    trigger: str = "cli-gate",
    executor: str = "prism",
    started_at: str | None = None,
    ended_at: str | None = None,
    duration_seconds_value: float | None = None,
    planned_exit_code: int = 0,
    ledger_path: pathlib.Path = DEFAULT_LEDGER,
    health_path: pathlib.Path = DEFAULT_HEALTH,
) -> dict[str, Any]:
    record = build_gate_record(
        request,
        result,
        trigger=trigger,
        executor=executor,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds_value=duration_seconds_value,
        planned_exit_code=planned_exit_code,
    )
    summary = append_record(record, ledger_path=ledger_path, health_path=health_path)
    return {"record": record, "summary": summary, "ledger_path": str(ledger_path), "health_path": str(health_path)}


def cmd_record(args: argparse.Namespace) -> int:
    result = record_manifest(
        pathlib.Path(args.manifest),
        trigger=args.trigger,
        executor=args.executor,
        ledger_path=pathlib.Path(args.ledger).resolve(),
        health_path=pathlib.Path(args.health).resolve(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("PRISM_LEDGER_RECORD_OK")
    return 0


def cmd_record_gate(args: argparse.Namespace) -> int:
    request = load_json(pathlib.Path(args.request).resolve())
    result = load_json(pathlib.Path(args.result).resolve())
    if not isinstance(request, dict) or not isinstance(result, dict):
        raise SystemExit("--request and --result must both be JSON objects")
    payload = record_gate(
        request,
        result,
        trigger=args.trigger,
        executor=args.executor,
        started_at=args.started_at,
        ended_at=args.ended_at,
        duration_seconds_value=args.duration_seconds,
        planned_exit_code=args.planned_exit_code,
        ledger_path=pathlib.Path(args.ledger).resolve(),
        health_path=pathlib.Path(args.health).resolve(),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("PRISM_LEDGER_RECORD_GATE_OK")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    records = read_records(pathlib.Path(args.ledger).resolve())
    summary = compute_summary(records)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("PRISM_LEDGER_SUMMARY_OK")
    return 0


def cmd_health_check(args: argparse.Namespace) -> int:
    records = read_records(pathlib.Path(args.ledger).resolve())
    latest = latest_by_task([record for record in records if is_session_record(record)])
    allowed = set(args.allow_task)
    fact_statuses = task_fact_statuses(pathlib.Path(args.task_facts).resolve())
    unhealthy = []
    for record in latest.values():
        task_id = str(record.get("task_id") or "")
        record_class = record.get("execution_class") or execution_class(
            task_id,
            pathlib.Path(str(record.get("run_dir") or "")),
            str(record.get("trigger") or ""),
        )
        if record_class in {"self_check", "fixture"}:
            continue
        if task_id in allowed:
            continue
        if fact_statuses.get(task_id) == "superseded":
            continue
        if effective_outcome(record) in UNHEALTHY_OUTCOMES:
            unhealthy.append(record)
    result = {
        "ok": not unhealthy,
        "unhealthy_count": len(unhealthy),
        "unhealthy_tasks": [
            {
                "task_id": record.get("task_id"),
                "outcome": effective_outcome(record),
                "status": record.get("status"),
                "convergence_state": record.get("convergence_state"),
                "convergence_reason": record.get("convergence_reason"),
                "strictest_verdict": record.get("strictest_verdict"),
                "recorded_at": record.get("recorded_at"),
            }
            for record in sorted(unhealthy, key=lambda item: str(item.get("recorded_at") or ""), reverse=True)
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if unhealthy:
        return 1
    print("PRISM_LEDGER_HEALTH_OK")
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="prism-ledger-") as tmp_raw:
        tmp = pathlib.Path(tmp_raw)
        run_dir = tmp / "run"
        run_dir.mkdir()
        review = {
            "provider": "kimi",
            "verdict": "pass",
            "confidence": 0.91,
            "reality_delta": ["fixture"],
            "main_concern": "none",
            "top_risks": [],
            "missing_evidence": [],
            "minimum_fix": "none",
            "anti_loop_signal": {"present": False},
            "user_intent_alignment": "aligned",
        }
        review_path = run_dir / "review-kimi.json"
        review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        merge_path = run_dir / "merge.json"
        merge_path.write_text(
            json.dumps(
                {
                    "strictest_verdict": "pass",
                    "strictest_provider": "kimi",
                    "must_respond": False,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        manifest = {
            "schema_id": "prism-session-manifest",
            "task_id": "fixture-task",
            "run_dir": str(run_dir),
            "status": "converged",
            "max_rounds_per_provider": 3,
            "created_at": "2026-05-31T00:00:00+00:00",
            "updated_at": "2026-05-31T00:00:07+00:00",
            "providers": {
                "kimi": {
                    "session_handle": "kimi-fixture",
                    "round_count": 1,
                    "status": "converged",
                    "last_review": str(review_path),
                },
                "claude-code": {
                    "session_handle": None,
                    "round_count": 0,
                    "status": "closed",
                    "last_review": None,
                },
            },
            "convergence": {"state": "converged", "reason": "fixture"},
        }
        manifest_path = run_dir / "session.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ledger = tmp / "task-ledger.jsonl"
        health = tmp / "task-health.json"
        result = record_manifest(manifest_path, trigger="self-check", ledger_path=ledger, health_path=health)
        gate = record_gate(
            {
                "task": "fixture gate",
                "risk_level": "low",
                "tags": ["self-check"],
                "changed_paths": [],
            },
            {
                "decision": "optional",
                "review_mode": "implementation_review",
                "matched_rules": ["fixture"],
                "required_providers": [],
            },
            trigger="self-check-gate",
            started_at="2026-05-31T00:00:08+00:00",
            ended_at="2026-05-31T00:00:09+00:00",
            ledger_path=ledger,
            health_path=health,
        )
        records = read_records(ledger)
        summary = json.loads(health.read_text(encoding="utf-8"))
        failures: list[str] = []
        if len(records) != 2:
            failures.append("ledger did not append session and gate records")
        if result["record"].get("duration_seconds") != 7.0:
            failures.append("duration was not computed")
        if gate["record"].get("schema_id") != "prism-gate-evaluation-record":
            failures.append("gate record schema is missing")
        if summary.get("success_rate") != 1.0:
            failures.append("summary success_rate should be 1.0")
        if summary.get("gate_event_count") != 1:
            failures.append("summary gate_event_count should be 1")
        if summary.get("providers", {}).get("kimi", {}).get("pass") != 1:
            failures.append("provider verdict stats missing")
        concern_run = tmp / "concern-run"
        concern_run.mkdir()
        concern_review = dict(review)
        concern_review["verdict"] = "concern"
        concern_review_path = concern_run / "review-kimi.json"
        concern_review_path.write_text(json.dumps(concern_review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (concern_run / "merge.json").write_text(
            json.dumps(
                {
                    "strictest_verdict": "concern",
                    "strictest_provider": "kimi",
                    "must_respond": True,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        concern_manifest = dict(manifest)
        concern_manifest["task_id"] = "fixture-main-decided-concern"
        concern_manifest["run_dir"] = str(concern_run)
        concern_manifest["status"] = "main-decided"
        concern_manifest["convergence"] = {"state": "main-decided", "reason": "fixture concern accepted"}
        concern_manifest["providers"] = {
            "kimi": {
                "session_handle": "kimi-fixture",
                "round_count": 1,
                "status": "main-decided",
                "last_review": str(concern_review_path),
            }
        }
        concern_manifest_path = concern_run / "session.json"
        concern_manifest_path.write_text(json.dumps(concern_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        concern_record = build_record(concern_manifest_path)
        if concern_record.get("success") is not True or concern_record.get("outcome") != "resolved_with_concern":
            failures.append("main-decided concern should be classified as resolved_with_concern")
        active_manifest = dict(concern_manifest)
        active_manifest["task_id"] = "fixture-active"
        active_manifest["status"] = "active"
        active_manifest["convergence"] = {"state": "unresolved", "reason": "fixture still running"}
        active_manifest_path = concern_run / "active-session.json"
        active_manifest_path.write_text(json.dumps(active_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        active_record = build_record(active_manifest_path)
        if active_record.get("success") is not False or active_record.get("outcome") != "active":
            failures.append("active unresolved task should be classified as active")
        expected_root = prism_runtime_evidence_root().resolve()
        ledger_overridden = bool(os.environ.get("REDCAP_PRISM_LEDGER", "").strip())
        health_overridden = bool(os.environ.get("REDCAP_PRISM_HEALTH", "").strip())
        if not ledger_overridden and DEFAULT_LEDGER.parent != expected_root:
            failures.append("default ledger path should live under the runtime evidence root")
        if not health_overridden and DEFAULT_HEALTH.parent != expected_root:
            failures.append("default health path should live under the runtime evidence root")
        if "assets/evidence/prism" in DEFAULT_LEDGER.as_posix():
            failures.append("default ledger path must not target tracked assets/evidence/prism")
        if "assets/evidence/prism" in DEFAULT_HEALTH.as_posix():
            failures.append("default health path must not target tracked assets/evidence/prism")
        print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
        if failures:
            return 1
        print("PRISM_LEDGER_SELF_CHECK_OK")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prism task execution ledger")
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record", help="append a session manifest snapshot to the ledger")
    record.add_argument("--manifest", required=True)
    record.add_argument("--trigger", default="manual")
    record.add_argument("--executor", default="prism")
    record.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    record.add_argument("--health", default=str(DEFAULT_HEALTH))
    record.set_defaults(func=cmd_record)

    record_gate_parser = sub.add_parser("record-gate", help="append a deterministic gate evaluation to the ledger")
    record_gate_parser.add_argument("--request", required=True, help="Gate request JSON object")
    record_gate_parser.add_argument("--result", required=True, help="Gate result JSON object")
    record_gate_parser.add_argument("--trigger", default="manual-gate")
    record_gate_parser.add_argument("--executor", default="prism")
    record_gate_parser.add_argument("--started-at")
    record_gate_parser.add_argument("--ended-at")
    record_gate_parser.add_argument("--duration-seconds", type=float)
    record_gate_parser.add_argument("--planned-exit-code", type=int, default=0)
    record_gate_parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    record_gate_parser.add_argument("--health", default=str(DEFAULT_HEALTH))
    record_gate_parser.set_defaults(func=cmd_record_gate)

    summary = sub.add_parser("summary", help="print the current ledger health summary")
    summary.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    summary.set_defaults(func=cmd_summary)

    health_check = sub.add_parser("health-check", help="fail when operational Prism tasks are unresolved or failed")
    health_check.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    health_check.add_argument("--task-facts", default=str(DEFAULT_TASK_FACTS))
    health_check.add_argument("--allow-task", action="append", default=[])
    health_check.set_defaults(func=cmd_health_check)

    self_check = sub.add_parser("self-check", help="run isolated ledger self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

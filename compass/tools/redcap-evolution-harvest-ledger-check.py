#!/usr/bin/env python3
# 用途：知识沉淀与自进化脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter
from typing import Any


ALLOWED_STATUSES = {"generated", "processed", "deferred"}
ALLOWED_OUTCOMES = {"candidate", "no-promote", "deferred-with-owner"}
ALLOWED_SOURCE_KINDS = {
    "user-correction",
    "task-report",
    "prism-verdict",
    "test-failure",
    "closeout-failure",
    "conversation-trace",
    "host-behavior",
    "token-risk",
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-evolution-harvest-ledger-check] {message}")


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


def repo_path(root: pathlib.Path, rel_path: str) -> pathlib.Path:
    path = pathlib.Path(rel_path).expanduser()
    return path if path.is_absolute() else root / path


def path_exists(root: pathlib.Path, rel_path: str) -> bool:
    return repo_path(root, rel_path).exists()


def require_text(payload: dict[str, Any], key: str, ctx: str, min_len: int = 1) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or len(value.strip()) < min_len:
        fail(f"{ctx}: missing or too-short {key}")
    return value.strip()


def require_list(payload: dict[str, Any], key: str, ctx: str, min_len: int = 0) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or len(value) < min_len:
        fail(f"{ctx}: {key} must be a list with at least {min_len} item(s)")
    return value


def validate_decision(record: dict[str, Any], ctx: str) -> None:
    outcome = require_text(record, "outcome", ctx)
    status = require_text(record, "status", ctx)
    if outcome not in ALLOWED_OUTCOMES:
        fail(f"{ctx}: unsupported outcome {outcome}")
    if status not in ALLOWED_STATUSES:
        fail(f"{ctx}: unsupported status {status}")
    if status == "generated":
        return

    decision = record.get("decision")
    if not isinstance(decision, dict):
        fail(f"{ctx}: processed/deferred record must include decision")
    if outcome == "candidate":
        candidate_id = require_text(decision, "candidate_id", ctx)
        pool_status = require_text(decision, "candidate_pool_status", ctx)
        if pool_status in {"candidate", "reviewing"}:
            fail(f"{ctx}: candidate {candidate_id} is still unresolved")
    elif outcome == "no-promote":
        require_text(decision, "reason", ctx, min_len=20)
    elif outcome == "deferred-with-owner":
        require_text(decision, "owner", ctx)
        require_text(decision, "next_trigger", ctx, min_len=10)


def validate_candidate_payload(record: dict[str, Any], ctx: str) -> None:
    payload = record.get("generated_candidate")
    if payload is None:
        return
    if not isinstance(payload, dict):
        fail(f"{ctx}: generated_candidate must be an object")
    for field in ("problem_source", "solution", "final_effect"):
        require_text(payload, field, f"{ctx}.generated_candidate", min_len=30)
    source_kind = payload.get("source_kind")
    if source_kind not in ALLOWED_SOURCE_KINDS:
        fail(f"{ctx}.generated_candidate: unsupported source_kind {source_kind}")


def validate_record(root: pathlib.Path, record: Any, seen_ids: set[str], seen_sources: set[tuple[str, str]]) -> str:
    if not isinstance(record, dict):
        fail("records entries must be objects")
    record_id = require_text(record, "id", "record")
    ctx = record_id
    if record_id in seen_ids:
        fail(f"duplicate record id: {record_id}")
    seen_ids.add(record_id)

    task_id = require_text(record, "task_id", ctx)
    source_report = require_text(record, "source_report", ctx)
    source_digest = require_text(record, "source_digest", ctx)
    if not source_digest.startswith("sha256:") or len(source_digest) < 20:
        fail(f"{ctx}: source_digest must be sha256-prefixed")
    source_key = (task_id, source_report)
    if source_key in seen_sources:
        fail(f"{ctx}: duplicate task/report harvest record: {task_id} {source_report}")
    seen_sources.add(source_key)

    reasons = require_list(record, "reasons", ctx, min_len=1)
    if not all(isinstance(item, str) and item.strip() for item in reasons):
        fail(f"{ctx}: reasons entries must be non-empty strings")

    evidence_paths = require_list(record, "evidence_paths", ctx, min_len=2)
    for rel_path in evidence_paths:
        if not isinstance(rel_path, str) or not rel_path.strip():
            fail(f"{ctx}: evidence paths must be non-empty strings")
        if rel_path.startswith("~/"):
            fail(f"{ctx}: evidence path must not use home-relative private path: {rel_path}")
        if not path_exists(root, rel_path):
            fail(f"{ctx}: evidence path does not exist: {rel_path}")

    validate_decision(record, ctx)
    validate_candidate_payload(record, ctx)
    return require_text(record, "status", ctx)


def main() -> int:
    if len(sys.argv) != 3:
        fail("usage: redcap-evolution-harvest-ledger-check.py <root> <ledger_path>")
    root = pathlib.Path(sys.argv[1]).resolve()
    ledger_arg = pathlib.Path(sys.argv[2])
    ledger_path = ledger_arg if ledger_arg.is_absolute() else root / ledger_arg
    payload = load_json(ledger_path, "harvest ledger")
    if payload.get("version") != 1:
        fail("harvest ledger version must be 1")
    records = require_list(payload, "records", "harvest ledger")
    seen_ids: set[str] = set()
    seen_sources: set[tuple[str, str]] = set()
    counts: Counter[str] = Counter()
    for record in records:
        counts[validate_record(root, record, seen_ids, seen_sources)] += 1
    print("EVOLUTION_HARVEST_LEDGER")
    print(f"records={len(records)}")
    print("statuses=" + ",".join(f"{key}={counts.get(key, 0)}" for key in sorted(ALLOWED_STATUSES)))
    print("EVOLUTION_HARVEST_LEDGER_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

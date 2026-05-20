#!/usr/bin/env python3
# 用途：架构坏味治理任务脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#product-shape-and-retrieval

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BACKLOG = ROOT / "references/backlogs/redcap-architecture-smell-governance.json"
EXPECTED_REQUIREMENTS = {f"RASG-{index:03d}" for index in range(1, 25)}
EXPECTED_TRANCHES = {
    "T0": {"RASG-003", "RASG-007", "RASG-009"},
    "T1": {"RASG-001", "RASG-002", "RASG-004", "RASG-014"},
    "T2": {"RASG-005", "RASG-008", "RASG-013"},
    "T3": {"RASG-006", "RASG-012", "RASG-016"},
    "T4": {"RASG-010", "RASG-011", "RASG-015"},
    "T5": {"RASG-017", "RASG-022"},
    "T6": {"RASG-018"},
    "T7": {"RASG-019", "RASG-020", "RASG-021"},
    "T8": {"RASG-023"},
    "T9": {"RASG-024"},
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-architecture-smell-governance-check] {message}")


def load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"backlog missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid backlog json: {exc}")
    if not isinstance(payload, dict):
        fail("backlog must be a JSON object")
    return payload


def validate(payload: dict[str, Any], *, require_complete: bool) -> None:
    if payload.get("version") != 1:
        fail("version must be 1")
    if payload.get("backlog_id") != "redcap-architecture-smell-governance":
        fail("backlog_id mismatch")
    requirements = payload.get("requirements")
    if not isinstance(requirements, list):
        fail("requirements must be a list")
    by_id: dict[str, dict[str, Any]] = {}
    for item in requirements:
        if not isinstance(item, dict):
            fail("requirements entries must be objects")
        req_id = item.get("id")
        if not isinstance(req_id, str) or req_id in by_id:
            fail(f"invalid or duplicate requirement id: {req_id}")
        by_id[req_id] = item
        for key in ("title", "priority", "category", "problem_source", "risk", "desired_outcome"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                fail(f"{req_id}: missing {key}")
        if not isinstance(item.get("acceptance"), list) or len(item["acceptance"]) < 2:
            fail(f"{req_id}: acceptance must contain at least two checks")
        status = item.get("status", "planned")
        if status not in {"planned", "in_progress", "done", "deferred"}:
            fail(f"{req_id}: unsupported status {status}")
        if status == "done":
            evidence = item.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                fail(f"{req_id}: done requirements must list evidence")
            for path in evidence:
                if not isinstance(path, str) or not path.strip():
                    fail(f"{req_id}: evidence entries must be non-empty strings")
        if require_complete and status != "done":
            fail(f"{req_id}: not done")
        follow_ups = item.get("follow_up_requirements", [])
        if follow_ups is None:
            follow_ups = []
        if not isinstance(follow_ups, list):
            fail(f"{req_id}: follow_up_requirements must be a list when present")
        for follow_id in follow_ups:
            if not isinstance(follow_id, str) or not follow_id.strip():
                fail(f"{req_id}: follow_up_requirements entries must be non-empty strings")
    missing = sorted(EXPECTED_REQUIREMENTS - set(by_id))
    extra = sorted(set(by_id) - EXPECTED_REQUIREMENTS)
    if missing or extra:
        fail(f"requirement id set mismatch missing={missing} extra={extra}")

    for req_id, item in by_id.items():
        for follow_id in item.get("follow_up_requirements", []) or []:
            if follow_id not in by_id:
                fail(f"{req_id}: follow-up requirement not registered: {follow_id}")
    if "RASG-022" not in (by_id["RASG-017"].get("follow_up_requirements") or []):
        fail("RASG-017 must keep RASG-022 as its physical consolidation follow-up")

    tranches = payload.get("tranches")
    if not isinstance(tranches, list) or len(tranches) != len(EXPECTED_TRANCHES):
        fail("tranches must contain the expected tranche set")
    for tranche in tranches:
        if not isinstance(tranche, dict):
            fail("tranche entries must be objects")
        tranche_id = tranche.get("id")
        if tranche_id not in EXPECTED_TRANCHES:
            fail(f"unexpected tranche id: {tranche_id}")
        items = tranche.get("items")
        if not isinstance(items, list) or set(items) != EXPECTED_TRANCHES[tranche_id]:
            fail(f"{tranche_id}: item set mismatch")
    must_not_claim = " ".join(str(item) for item in payload.get("must_not_claim", []))
    for phrase in ["Do not claim these requirements are completed", "Do not start npm publish"]:
        if phrase not in must_not_claim:
            fail(f"must_not_claim missing phrase: {phrase}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap architecture smell governance backlog.")
    parser.add_argument("--backlog", default=str(DEFAULT_BACKLOG))
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()

    path = Path(args.backlog)
    if not path.is_absolute():
        path = ROOT / path
    payload = load(path)
    validate(payload, require_complete=args.require_complete)
    statuses: dict[str, int] = {}
    for item in payload["requirements"]:
        statuses[item.get("status", "planned")] = statuses.get(item.get("status", "planned"), 0) + 1
    print("ARCHITECTURE_SMELL_GOVERNANCE_OK")
    print(" ".join(f"{key}={value}" for key, value in sorted(statuses.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

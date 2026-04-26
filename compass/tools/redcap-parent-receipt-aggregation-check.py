#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "references/parent-receipt-aggregation-policy.json"
ALLOWED_OPEN_STATUSES = {"open", "blocked-external", "resource-limited", "deferred"}
REQUIRED_COMPLETED = {"P0-1", "P0-2", "P1-1", "P1-2"}
REQUIRED_NOT_COMPLETE = {"P1-3", "P2-1", "P2-3"}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-parent-receipt-aggregation-check] {message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid json {path}: {exc}")
    if not isinstance(payload, dict):
        fail("policy must be a JSON object")
    return payload


def require_text(item: dict[str, Any], key: str, item_id: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{item_id}: missing non-empty {key}")
    return value.strip()


def require_safe_relative(raw: str, item_id: str, key: str) -> str:
    if raw.startswith("/") or ".." in Path(raw).parts:
        fail(f"{item_id}: {key} must be a safe repo-relative path: {raw}")
    return raw


def check_policy(path: Path, root: Path) -> None:
    payload = load_json(path)
    if payload.get("version") != 1:
        fail("version must be 1")
    if payload.get("policy_id") != "redcap-parent-receipt-aggregation":
        fail("policy_id must be redcap-parent-receipt-aggregation")
    if payload.get("parent_task_id") != "redcap-system-migration-parent":
        fail("parent_task_id must be redcap-system-migration-parent")
    if payload.get("parent_status") != "incomplete":
        fail("parent_status must remain incomplete while child work remains")
    if payload.get("parent_completion_allowed") is not False:
        fail("parent_completion_allowed must be false while not_complete_children is non-empty")
    require_text(payload, "completion_rule", "policy")

    completed = payload.get("completed_children")
    if not isinstance(completed, list) or not completed:
        fail("completed_children must be a non-empty list")
    completed_ids: set[str] = set()
    for child in completed:
        if not isinstance(child, dict):
            fail("completed_children entries must be objects")
        child_id = require_text(child, "id", "completed_child")
        if child_id in completed_ids:
            fail(f"duplicate completed child id: {child_id}")
        completed_ids.add(child_id)
        require_text(child, "title", child_id)
        report = require_safe_relative(require_text(child, "report_path", child_id), child_id, "report_path")
        if not (root / report).is_file():
            fail(f"{child_id}: report_path missing: {report}")
        receipt_glob = require_text(child, "receipt_glob", child_id)
        if "/" in receipt_glob or not receipt_glob.endswith(".json"):
            fail(f"{child_id}: receipt_glob must be a receipt filename glob ending in .json")
    missing_completed = sorted(REQUIRED_COMPLETED - completed_ids)
    if missing_completed:
        fail("missing completed child entries: " + ", ".join(missing_completed))

    not_complete = payload.get("not_complete_children")
    if not isinstance(not_complete, list) or not not_complete:
        fail("not_complete_children must be non-empty until the parent can complete")
    open_ids: set[str] = set()
    for child in not_complete:
        if not isinstance(child, dict):
            fail("not_complete_children entries must be objects")
        child_id = require_text(child, "id", "not_complete_child")
        if child_id in open_ids:
            fail(f"duplicate not-complete child id: {child_id}")
        open_ids.add(child_id)
        status = require_text(child, "status", child_id)
        if status not in ALLOWED_OPEN_STATUSES:
            fail(f"{child_id}: unsupported not-complete status: {status}")
        require_text(child, "reason", child_id)
        require_text(child, "next_step", child_id)
    missing_not_complete = sorted(REQUIRED_NOT_COMPLETE - open_ids)
    if missing_not_complete:
        fail("missing not-complete child entries: " + ", ".join(missing_not_complete))
    if completed_ids & open_ids:
        fail("child ids cannot be both completed and not-complete: " + ", ".join(sorted(completed_ids & open_ids)))

    outputs = payload.get("gate_outputs")
    if not isinstance(outputs, dict):
        fail("gate_outputs must be an object")
    if outputs.get("parent_receipt_status") != "not-eligible":
        fail("gate_outputs.parent_receipt_status must be not-eligible")
    require_text(outputs, "reason", "gate_outputs")
    allowed_claim = require_text(outputs, "allowed_claim", "gate_outputs")
    if "parent task is still incomplete" not in allowed_claim:
        fail("gate_outputs.allowed_claim must explicitly say the parent task is still incomplete")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap parent receipt aggregation policy.")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy = Path(args.policy)
    if not policy.is_absolute():
        policy = (Path.cwd() / policy).resolve()
    if not policy.is_file():
        fail(f"missing policy: {policy}")
    check_policy(policy, root)
    print(f"PARENT_RECEIPT_AGGREGATION_OK {policy}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

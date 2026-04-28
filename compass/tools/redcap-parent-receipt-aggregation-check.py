#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "references/parent-receipt-aggregation-policy.json"
DEFAULT_TASK_FILE = ROOT / ".dev-task.md"
DEFAULT_RUNTIME_PROJECT_BASE = Path("/tmp/redcap/project")
ALLOWED_OPEN_STATUSES = {"open", "blocked-external", "resource-limited", "deferred"}
ALLOWED_ACCEPTANCE_STATUSES = {"pass", "resource-limited-pass", "not-required"}
REQUIRED_COMPLETED = {
    "P0-1",
    "P0-2",
    "P1-1",
    "P1-2",
    "P1-3",
    "P1-4",
    "P2-1",
    "P2-2",
    "P2-3",
    "P2-4",
    "P2-5",
    "P3-1",
    "P3-2",
}
REQUIRED_NOT_COMPLETE = {"P4-1", "P4-2", "P4-3"}


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


def project_receipt_dir(root: Path, runtime_base: Path) -> Path:
    project_hash = hashlib.md5(str(root.resolve()).encode("utf-8")).hexdigest()
    return runtime_base / project_hash / "governance/closeout-runtime/receipts"


def normalize_repo_path(root: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def parse_task_metadata(task_file: Path) -> dict[str, str]:
    if not task_file.is_file():
        return {}
    metadata: dict[str, str] = {}
    for line in task_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key and value and " " not in key:
            metadata[key] = value
    return metadata


def derive_task_id(child: dict[str, Any], child_id: str) -> str:
    raw = child.get("task_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    receipt_glob = require_text(child, "receipt_glob", child_id)
    if receipt_glob.endswith("-*.json"):
        return receipt_glob[: -len("-*.json")]
    fail(f"{child_id}: receipt_glob must end with '-*.json' unless task_id is explicit")


def ensure_git_commit(root: Path, sha: Any, item_id: str, field: str, required: bool = True) -> None:
    if not isinstance(sha, str) or not sha.strip():
        if required:
            fail(f"{item_id}: receipt missing non-empty {field}")
        return
    result = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", f"{sha.strip()}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        fail(f"{item_id}: receipt {field} is not a repo commit: {sha}")


def receipt_is_valid(receipt: Path, *, root: Path, child_id: str, task_id: str, report_path: str, allowed_acceptance: set[str]) -> tuple[bool, str]:
    try:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"{receipt.name}: invalid json: {exc}"
    if not isinstance(payload, dict):
        return False, f"{receipt.name}: receipt must be a JSON object"
    if payload.get("task_id") != task_id:
        return False, f"{receipt.name}: task_id mismatch"
    if payload.get("status") != "completed":
        return False, f"{receipt.name}: status is not completed"
    if payload.get("promise_pending") != 0:
        return False, f"{receipt.name}: promise_pending is not 0"
    confirmed_hash = payload.get("confirmed_hash")
    if not isinstance(confirmed_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", confirmed_hash.strip()):
        return False, f"{receipt.name}: confirmed_hash is not a 64-char hex digest"
    raw_repo = payload.get("repo_path")
    if not isinstance(raw_repo, str) or not raw_repo.strip():
        return False, f"{receipt.name}: missing repo_path"
    if normalize_repo_path(root, raw_repo) != root.resolve():
        return False, f"{receipt.name}: repo_path mismatch"
    acceptance_status = payload.get("acceptance_status")
    if acceptance_status not in allowed_acceptance:
        return False, f"{receipt.name}: unsupported acceptance_status {acceptance_status!r}"

    expected_report = (root / report_path).resolve()
    raw_report = payload.get("report_path")
    if not isinstance(raw_report, str) or not raw_report.strip():
        return False, f"{receipt.name}: missing report_path"
    if normalize_repo_path(root, raw_report) != expected_report:
        return False, f"{receipt.name}: report_path mismatch"

    current_head = payload.get("current_head")
    try:
        ensure_git_commit(root, current_head, child_id, "current_head", required=True)
        ensure_git_commit(root, payload.get("baseline_head"), child_id, "baseline_head", required=False)
    except SystemExit as exc:
        return False, str(exc)
    return True, f"{receipt.name}: ok"


def is_current_child_pre_receipt(child_id: str, report_path: str, task_metadata: dict[str, str]) -> bool:
    return (
        task_metadata.get("parent_child_id") == child_id
        and task_metadata.get("task_report") == report_path
    )


def receipt_correspondence_config(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("receipt_correspondence")
    if raw is None:
        fail("receipt_correspondence must be configured")
    if not isinstance(raw, dict):
        fail("receipt_correspondence must be an object")
    if raw.get("enabled") is not True:
        fail("receipt_correspondence.enabled must be true")
    allowed = raw.get("allowed_acceptance_statuses")
    if allowed is None:
        raw["allowed_acceptance_statuses"] = sorted(ALLOWED_ACCEPTANCE_STATUSES)
    elif not isinstance(allowed, list) or not allowed:
        fail("receipt_correspondence.allowed_acceptance_statuses must be a non-empty list")
    else:
        invalid = sorted(set(allowed) - ALLOWED_ACCEPTANCE_STATUSES)
        if invalid:
            fail("receipt_correspondence.allowed_acceptance_statuses has unsupported values: " + ", ".join(invalid))
    return raw


def check_completed_child_receipt(
    child: dict[str, Any],
    *,
    root: Path,
    receipt_dir: Path,
    task_metadata: dict[str, str],
    allow_current_pre_receipt: bool,
    allowed_acceptance: set[str],
) -> bool:
    child_id = require_text(child, "id", "completed_child")
    report_path = require_safe_relative(require_text(child, "report_path", child_id), child_id, "report_path")
    receipt_glob = require_text(child, "receipt_glob", child_id)
    if "/" in receipt_glob or ".." in receipt_glob or not receipt_glob.endswith(".json"):
        fail(f"{child_id}: receipt_glob must be a safe receipt filename glob ending in .json")
    task_id = derive_task_id(child, child_id)

    matches = sorted(receipt_dir.glob(receipt_glob)) if receipt_dir.is_dir() else []
    if not matches:
        if allow_current_pre_receipt and is_current_child_pre_receipt(child_id, report_path, task_metadata):
            return True
        fail(f"{child_id}: receipt_glob matched no runtime receipts: {receipt_glob}")

    reasons: list[str] = []
    for receipt in matches:
        valid, reason = receipt_is_valid(
            receipt,
            root=root,
            child_id=child_id,
            task_id=task_id,
            report_path=report_path,
            allowed_acceptance=allowed_acceptance,
        )
        if valid:
            return False
        reasons.append(reason)
    fail(f"{child_id}: no matching runtime receipt has corresponding content: " + "; ".join(reasons[:3]))


def check_policy(path: Path, root: Path, task_file: Path) -> None:
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

    correspondence = receipt_correspondence_config(payload)
    runtime_base_raw = os.environ.get("REDCAP_RUNTIME_PROJECT_BASE_DIR") or correspondence.get("runtime_project_base") or str(DEFAULT_RUNTIME_PROJECT_BASE)
    runtime_base = Path(str(runtime_base_raw)).expanduser().resolve()
    receipt_dir = project_receipt_dir(root, runtime_base)
    allow_current_pre_receipt = correspondence.get("allow_current_child_pre_receipt") is True
    allowed_acceptance = set(correspondence.get("allowed_acceptance_statuses", []))
    task_metadata = parse_task_metadata(task_file)

    completed = payload.get("completed_children")
    if not isinstance(completed, list) or not completed:
        fail("completed_children must be a non-empty list")
    completed_ids: set[str] = set()
    pre_receipt_count = 0
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
        if check_completed_child_receipt(
            child,
            root=root,
            receipt_dir=receipt_dir,
            task_metadata=task_metadata,
            allow_current_pre_receipt=allow_current_pre_receipt,
            allowed_acceptance=allowed_acceptance,
        ):
            pre_receipt_count += 1
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

    print(
        "PARENT_RECEIPT_AGGREGATION_OK "
        f"{path} completed_children={len(completed_ids)} "
        f"receipt_correspondence=verified current_pre_receipt={pre_receipt_count}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap parent receipt aggregation policy.")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--task-file", default=str(DEFAULT_TASK_FILE))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy = Path(args.policy)
    if not policy.is_absolute():
        policy = (Path.cwd() / policy).resolve()
    task_file = Path(args.task_file)
    if not task_file.is_absolute():
        task_file = (Path.cwd() / task_file).resolve()
    if not policy.is_file():
        fail(f"missing policy: {policy}")
    check_policy(policy, root, task_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())

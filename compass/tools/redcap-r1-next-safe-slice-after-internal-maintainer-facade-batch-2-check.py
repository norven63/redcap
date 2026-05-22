#!/usr/bin/env python3
# 用途：正式发布 R1 第二批 facade 后下一安全切片路线裁决验收；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "references/r1-next-safe-slice-after-internal-maintainer-facade-batch-2.json"
P4_23_MANIFEST = ROOT / "references/r1-control-plane-internal-maintainer-facade-batch-2-copy-first-apply.json"
CONTRACT_SPLIT = ROOT / "references/r1-control-plane-contract-split-preflight.json"
PHYSICAL_PREFLIGHT = ROOT / "references/r1-control-plane-physical-apply-preflight.json"
BACKLOG = ROOT / "references/backlogs/framework-upgrade.json"
PRISM_REPORT = ROOT / "prism/reports/2026-05-23-r1-next-safe-slice-after-internal-maintainer-facade-batch-2.md"
TASK_REPORT = ROOT / "compass/docs/task-reports/2026-05-23-r1-next-safe-slice-after-internal-maintainer-facade-batch-2.md"
EXPECTED_STATUS = "selected-next-slice-no-blocker-closed"
REQUIRED_BLOCKERS = {
    "internal-control-plane",
    "prism-layer-and-evidence",
    "internal-layer-a",
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-next-safe-slice-after-internal-maintainer-facade-batch-2-check] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing {label}: {path.relative_to(ROOT)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be a JSON object")
    return payload


def require_list(value: Any, label: str, *, min_len: int = 1) -> list[Any]:
    if not isinstance(value, list) or len(value) < min_len:
        fail(f"{label} must be a list with at least {min_len} item(s)")
    return value


def require_bool(value: Any, expected: bool, label: str) -> None:
    if value is not expected:
        fail(f"{label} must be {expected}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def backlog_items(backlog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    for group in backlog.get("groups", []):
        if not isinstance(group, dict):
            continue
        for item in group.get("items", []):
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                items[item["id"]] = item
    return items


def validate_backlog() -> None:
    backlog = load_json(BACKLOG, "framework upgrade backlog")
    items = backlog_items(backlog)
    if items.get("P4-23", {}).get("status") != "done":
        fail("P4-23 must be marked done")
    p4_24_status = items.get("P4-24", {}).get("status")
    current_focus = backlog.get("current_focus", {}).get("item_id")
    if p4_24_status == "pending":
        if current_focus != "P4-24":
            fail("current_focus.item_id must be P4-24 while P4-24 is pending")
    elif p4_24_status == "done":
        if current_focus == "P4-24":
            fail("current_focus.item_id must advance after P4-24 is done")
        if items.get("P4-25", {}).get("status") != "pending":
            fail("P4-25 must be registered as pending after P4-24 is done")
    else:
        fail("P4-24 must be registered as pending or done")


def validate_reports() -> None:
    for path, label in [(PRISM_REPORT, "Prism report"), (TASK_REPORT, "task report")]:
        if not path.is_file():
            fail(f"missing {label}: {path.relative_to(ROOT)}")
        text = path.read_text(encoding="utf-8")
        if "正式发布" in text and "不是正式发布" not in text and "正式发布前" not in text:
            fail(f"{label} may imply formal public distribution completion")


def validate(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("decision_id") != "redcap-r1-next-safe-slice-after-internal-maintainer-facade-batch-2":
        fail("decision_id must match P4-24")
    if manifest.get("status") != EXPECTED_STATUS:
        fail(f"status must be {EXPECTED_STATUS}")

    source_truth = manifest.get("source_truth")
    if not isinstance(source_truth, dict):
        fail("source_truth must be an object")
    expected_truth = {
        "p4_23_manifest_path": ("references/r1-control-plane-internal-maintainer-facade-batch-2-copy-first-apply.json", sha256(P4_23_MANIFEST)),
        "control_plane_contract_split_path": ("references/r1-control-plane-contract-split-preflight.json", sha256(CONTRACT_SPLIT)),
        "control_plane_physical_preflight_path": ("references/r1-control-plane-physical-apply-preflight.json", sha256(PHYSICAL_PREFLIGHT)),
    }
    for path_key, (expected_path, expected_hash) in expected_truth.items():
        if source_truth.get(path_key) != expected_path:
            fail(f"source_truth.{path_key} must be {expected_path}")
        hash_key = path_key.replace("_path", "_sha256")
        if source_truth.get(hash_key) != expected_hash:
            fail(f"source_truth.{hash_key} is stale")

    candidates = require_list(manifest.get("candidate_matrix"), "candidate_matrix", min_len=6)
    by_id = {item.get("id"): item for item in candidates if isinstance(item, dict)}
    if by_id.get("B", {}).get("selected") is not True:
        fail("candidate B must be selected")
    for candidate_id in ["A", "C", "D", "E", "F"]:
        if by_id.get(candidate_id, {}).get("selected") is not False:
            fail(f"candidate {candidate_id} must not be selected")
    for candidate_id in ["D", "E", "F"]:
        require_bool(by_id.get(candidate_id, {}).get("requires_human_decision"), True, f"candidate {candidate_id}.requires_human_decision")

    selected = manifest.get("selected_next_slice")
    if not isinstance(selected, dict):
        fail("selected_next_slice must be an object")
    if selected.get("backlog_item_id") != "P4-25":
        fail("selected_next_slice.backlog_item_id must be P4-25")
    if selected.get("selected_candidate") != "B":
        fail("selected_next_slice.selected_candidate must be B")

    review = manifest.get("prism_review")
    if not isinstance(review, dict):
        fail("prism_review must be an object")
    if review.get("run_id") != "20260523-r1-next-safe-slice-after-internal-maintainer-facade-batch-2":
        fail("prism_review.run_id must match P4-24")
    if review.get("verdict") != "split-decision-cap-adjudicates-B-contract-mirror-preflight":
        fail("prism_review.verdict must record Cap adjudication")

    boundary = manifest.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    for key in ["route_selection_completed", "selected_next_item_registered"]:
        require_bool(boundary.get(key), True, f"claim_boundary.{key}")
    for key in [
        "selected_next_slice_implemented",
        "release_blocker_closed",
        "internal_control_plane_closed",
        "prism_layer_and_evidence_closed",
        "old_report_anchor_alias_gateway_implemented",
        "old_report_anchors_removed_or_replaced",
        "raw_run_evidence_deleted_or_cleaned",
        "layer_a_product_decision_made",
        "release_switch_changed",
        "public_release_ready",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")

    result = manifest.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    if result.get("release_blocker_status") != "still-blocking-after-route-selection":
        fail("result.release_blocker_status must remain still-blocking-after-route-selection")
    if result.get("selected_next_backlog_item") != "P4-25":
        fail("result.selected_next_backlog_item must be P4-25")
    require_bool(result.get("selected_next_slice_implemented"), False, "result.selected_next_slice_implemented")
    require_bool(result.get("public_release_ready"), False, "result.public_release_ready")
    remaining = set(load_json(P4_23_MANIFEST, "P4-23 manifest").get("result", {}).get("remaining_release_blockers_after_this_apply", []))
    if remaining != REQUIRED_BLOCKERS:
        fail("P4-23 manifest must still keep all release blockers open")

    validate_backlog()
    validate_reports()
    return {"selected": "B", "next": "P4-25"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate P4-24 next safe slice after internal maintainer facade batch-2.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()
    summary = validate(load_json(Path(args.manifest), "P4-24 route-selection manifest"))
    print(
        "R1_NEXT_SAFE_SLICE_AFTER_INTERNAL_MAINTAINER_FACADE_BATCH_2_OK "
        f"selected={summary['selected']} next={summary['next']} release_blocker_status=still-blocking"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

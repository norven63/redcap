#!/usr/bin/env python3
# 用途：校验 P4-20 发布准备下一安全切片选择；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "references/r1-next-safe-slice-after-old-anchor-preflight.json"
OLD_ANCHOR_PREFLIGHT = ROOT / "references/r1-prism-report-archive-old-anchor-delete-last-preflight.json"
CONVERGENCE = ROOT / "references/r1-formal-release-readiness-convergence-assessment.json"
CONTROL_PLANE_PREFLIGHT = ROOT / "references/r1-control-plane-physical-apply-preflight.json"
BACKLOG = ROOT / "references/backlogs/framework-upgrade.json"
PRISM_REPORT = ROOT / "prism/reports/2026-05-23-r1-next-safe-slice-after-old-anchor-preflight.md"
TASK_REPORT = ROOT / "compass/docs/task-reports/2026-05-23-r1-next-safe-slice-after-old-anchor-preflight.md"
EXPECTED_STATUS = "selected-next-slice-no-blocker-closed"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-next-safe-slice-after-old-anchor-preflight-check] {message}")


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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{label} must be non-empty text")
    return value.strip()


def require_bool(value: Any, expected: bool, label: str) -> None:
    if value is not expected:
        fail(f"{label} must be {expected}")


def require_list(value: Any, label: str, *, min_len: int = 1) -> list[Any]:
    if not isinstance(value, list) or len(value) < min_len:
        fail(f"{label} must be a list with at least {min_len} item(s)")
    return value


def validate_source_truth(manifest: dict[str, Any]) -> None:
    source = manifest.get("source_truth")
    if not isinstance(source, dict):
        fail("source_truth must be an object")
    expected = {
        "old_anchor_preflight": OLD_ANCHOR_PREFLIGHT,
        "convergence_assessment": CONVERGENCE,
        "control_plane_physical_preflight": CONTROL_PLANE_PREFLIGHT,
    }
    for prefix, path in expected.items():
        if source.get(f"{prefix}_path") != path.relative_to(ROOT).as_posix():
            fail(f"source_truth.{prefix}_path mismatch")
        if source.get(f"{prefix}_sha256") != sha256(path):
            fail(f"source_truth.{prefix}_sha256 is stale")


def validate_claim_boundary(manifest: dict[str, Any]) -> None:
    boundary = manifest.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    for key in ["route_selection_completed", "selected_next_item_registered"]:
        require_bool(boundary.get(key), True, f"claim_boundary.{key}")
    for key in [
        "next_slice_implemented",
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
    forbidden = "\n".join(
        str(item) for item in require_list(boundary.get("forbidden_claims"), "claim_boundary.forbidden_claims", min_len=5)
    )
    for phrase in ["selected next slice", "internal-control-plane", "prism/reports", "raw run evidence", "public npm/CLI release"]:
        if phrase not in forbidden:
            fail(f"claim_boundary.forbidden_claims missing phrase: {phrase}")


def validate_candidates(manifest: dict[str, Any]) -> None:
    candidates = require_list(manifest.get("candidate_matrix"), "candidate_matrix", min_len=5)
    by_id: dict[str, dict[str, Any]] = {}
    for item in candidates:
        if not isinstance(item, dict):
            fail("candidate_matrix item must be an object")
        by_id[require_text(item.get("id"), "candidate.id")] = item
    if set(by_id) != {"A", "B", "C", "D", "E"}:
        fail("candidate_matrix must contain exactly A/B/C/D/E")
    require_bool(by_id["A"].get("selected"), True, "candidate A selected")
    require_bool(by_id["B"].get("selected"), False, "candidate B selected")
    for candidate_id in ["C", "D", "E"]:
        require_bool(by_id[candidate_id].get("selected"), False, f"candidate {candidate_id} selected")
        require_bool(by_id[candidate_id].get("requires_human_decision"), True, f"candidate {candidate_id} requires_human_decision")
    for candidate_id in ["A", "B"]:
        require_bool(by_id[candidate_id].get("requires_human_decision"), False, f"candidate {candidate_id} requires_human_decision")
        require_bool(by_id[candidate_id].get("destructive"), False, f"candidate {candidate_id} destructive")


def validate_selected_next_slice(manifest: dict[str, Any]) -> None:
    selected = manifest.get("selected_next_slice")
    if not isinstance(selected, dict):
        fail("selected_next_slice must be an object")
    if selected.get("backlog_item_id") != "P4-21":
        fail("selected_next_slice.backlog_item_id must be P4-21")
    if selected.get("selected_candidate") != "A":
        fail("selected_next_slice.selected_candidate must be A")
    scope = "\n".join(str(item) for item in require_list(selected.get("scope"), "selected_next_slice.scope", min_len=4))
    for phrase in ["internal-control-plane", "non-destructive", "prism/reports", "prism/runs", "release switches"]:
        if phrase not in scope:
            fail(f"selected_next_slice.scope missing phrase: {phrase}")
    acceptance = "\n".join(
        str(item) for item in require_list(selected.get("minimum_acceptance"), "selected_next_slice.minimum_acceptance", min_len=5)
    )
    for phrase in ["manifest", "checker", "Prism review", "spec-check", "closeout receipt"]:
        if phrase not in acceptance:
            fail(f"selected_next_slice.minimum_acceptance missing phrase: {phrase}")


def validate_prism_review(manifest: dict[str, Any]) -> None:
    review = manifest.get("prism_review")
    if not isinstance(review, dict):
        fail("prism_review must be an object")
    if review.get("run_id") != "20260523-r1-next-safe-slice-after-old-anchor-preflight":
        fail("prism_review.run_id mismatch")
    agents = require_list(review.get("agents"), "prism_review.agents", min_len=4)
    providers = {require_text(item.get("provider"), "prism_review.provider"): item for item in agents if isinstance(item, dict)}
    for provider in ["claude-code", "kimi", "gemini", "copilot"]:
        if provider not in providers:
            fail(f"prism_review missing provider: {provider}")
    if providers["claude-code"].get("status") != "responded" or providers["claude-code"].get("recommendation") != "A":
        fail("claude-code review must respond with recommendation A")
    if providers["kimi"].get("status") != "responded" or providers["kimi"].get("recommendation") != "B":
        fail("kimi review must respond with recommendation B")
    if providers["copilot"].get("status") != "policy-suppressed":
        fail("copilot must remain policy-suppressed")
    if review.get("verdict") != "split-decision-cap-adjudicates-A":
        fail("prism_review.verdict mismatch")


def iter_backlog_items(backlog: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for group in backlog.get("groups", []):
        if not isinstance(group, dict):
            continue
        for item in group.get("items", []):
            if isinstance(item, dict):
                items.append(item)
    return items


def validate_backlog() -> None:
    backlog = load_json(BACKLOG, "framework upgrade backlog")
    items = {item.get("id"): item for item in iter_backlog_items(backlog)}
    if items.get("P4-20", {}).get("status") != "done":
        fail("P4-20 must be marked done in framework-upgrade backlog")
    p4_21_status = items.get("P4-21", {}).get("status")
    current_focus = backlog.get("current_focus", {}).get("item_id")
    if p4_21_status == "pending":
        if current_focus != "P4-21":
            fail("backlog current_focus.item_id must be P4-21 while P4-21 is pending")
    elif p4_21_status == "done":
        if current_focus == "P4-21":
            fail("backlog current_focus.item_id must advance after P4-21 is done")
    else:
        fail("P4-21 must be registered as pending or done in framework-upgrade backlog")
    p4_20_paths = "\n".join(str(path) for path in items["P4-20"].get("evidence_paths", []))
    for rel in [
        "references/r1-next-safe-slice-after-old-anchor-preflight.json",
        "prism/reports/2026-05-23-r1-next-safe-slice-after-old-anchor-preflight.md",
        "compass/docs/task-reports/2026-05-23-r1-next-safe-slice-after-old-anchor-preflight.md",
    ]:
        if rel not in p4_20_paths:
            fail(f"P4-20 evidence_paths missing {rel}")


def validate_reports() -> None:
    for path, label in [(PRISM_REPORT, "Prism report"), (TASK_REPORT, "task report")]:
        if not path.is_file():
            fail(f"missing {label}: {path.relative_to(ROOT)}")
        text = path.read_text(encoding="utf-8")
        for phrase in ["P4-20", "下一安全切片", "internal-control-plane", "不是正式发布"]:
            if phrase not in text:
                fail(f"{label} missing phrase: {phrase}")


def validate_manifest(path: Path) -> None:
    manifest = load_json(path, "P4-20 route manifest")
    if manifest.get("decision_id") != "redcap-r1-next-safe-slice-after-old-anchor-preflight":
        fail("decision_id mismatch")
    if manifest.get("status") != EXPECTED_STATUS:
        fail(f"status must be {EXPECTED_STATUS}")
    validate_source_truth(manifest)
    validate_claim_boundary(manifest)
    validate_candidates(manifest)
    validate_selected_next_slice(manifest)
    validate_prism_review(manifest)
    validate_backlog()
    validate_reports()
    result = manifest.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    if result.get("selected_next_backlog_item") != "P4-21":
        fail("result.selected_next_backlog_item must be P4-21")
    require_bool(result.get("selected_next_slice_implemented"), False, "result.selected_next_slice_implemented")
    require_bool(result.get("public_release_ready"), False, "result.public_release_ready")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()
    validate_manifest(Path(args.manifest))
    print("R1_NEXT_SAFE_SLICE_AFTER_OLD_ANCHOR_PREFLIGHT_OK")


if __name__ == "__main__":
    main()

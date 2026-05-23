#!/usr/bin/env python3
# 用途：校验 P4-28 只完成 P4-27 后的下一安全切片路线选择，不执行真实 copy-first apply。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "references/r1-next-safe-slice-after-contract-mirror-apply-preflight-subset.json"
P4_27_PREFLIGHT = ROOT / "references/r1-contract-mirror-apply-preflight-subset.json"
P4_26_ROUTE = ROOT / "references/r1-next-safe-slice-after-control-plane-contract-mirror-preflight.json"
P4_25_MANIFEST = ROOT / "references/r1-control-plane-public-internal-contract-mirror-preflight.json"
CONTRACT_SPLIT = ROOT / "references/r1-control-plane-contract-split-preflight.json"
BACKLOG = ROOT / "references/backlogs/framework-upgrade.json"
PRISM_REPORT = ROOT / "prism/reports/2026-05-23-r1-next-safe-slice-after-contract-mirror-apply-preflight-subset.md"
TASK_REPORT = ROOT / "compass/docs/task-reports/2026-05-23-r1-next-safe-slice-after-contract-mirror-apply-preflight-subset.md"
P4_29_APPLY = ROOT / "references/r1-contract-mirror-bounded-copy-first-apply.json"
EXPECTED_BLOCKERS = {"internal-control-plane", "prism-layer-and-evidence", "internal-layer-a"}
EXPECTED_RUN_ID = "20260523-r1-next-safe-slice-after-contract-mirror-apply-preflight-subset"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-next-safe-slice-after-contract-mirror-apply-preflight-subset-check] {message}")


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


def require_bool(value: Any, expected: bool, label: str) -> None:
    if value is not expected:
        fail(f"{label} must be {expected}")


def require_list(value: Any, label: str, *, min_len: int = 1) -> list[Any]:
    if not isinstance(value, list) or len(value) < min_len:
        fail(f"{label} must be a list with at least {min_len} item(s)")
    return value


def iter_backlog_items(backlog: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for group in backlog.get("groups", []):
        if isinstance(group, dict):
            result.extend(item for item in group.get("items", []) if isinstance(item, dict))
    return result


def downstream_apply_manifest() -> dict[str, Any] | None:
    if not P4_29_APPLY.is_file():
        return None
    payload = load_json(P4_29_APPLY, "P4-29 bounded copy-first apply")
    if payload.get("apply_id") != "redcap-r1-contract-mirror-bounded-copy-first-apply":
        fail("P4-29 apply manifest apply_id mismatch")
    if payload.get("status") != "copy-first-apply-old-anchors-retained-no-release-blocker-closed":
        fail("P4-29 apply manifest status mismatch")
    return payload


def downstream_copy(payload: dict[str, Any] | None, source_rel: str, target_rel: str) -> dict[str, Any] | None:
    if payload is None:
        return None
    copies = payload.get("copies")
    if not isinstance(copies, list):
        fail("P4-29 apply manifest copies must be a list")
    for item in copies:
        if isinstance(item, dict) and item.get("source") == source_rel and item.get("target") == target_rel:
            return item
    return None


def downstream_source_update(payload: dict[str, Any] | None, source_rel: str, old_hash: str, current_hash: str) -> bool:
    if payload is None:
        return False
    updates = payload.get("source_updates_after_preflight", [])
    if not isinstance(updates, list):
        fail("P4-29 apply source_updates_after_preflight must be a list")
    for item in updates:
        if not isinstance(item, dict) or item.get("source") != source_rel:
            continue
        if item.get("preflight_source_sha256") != old_hash:
            fail(f"P4-29 source update preflight hash mismatch: {source_rel}")
        if item.get("current_source_sha256") != current_hash:
            fail(f"P4-29 source update current hash mismatch: {source_rel}")
        return True
    return False


def target_allowed_by_downstream_apply(payload: dict[str, Any] | None, source_rel: str, target_rel: str, current_source_hash: str) -> bool:
    copy = downstream_copy(payload, source_rel, target_rel)
    if copy is None:
        return False
    target = ROOT / target_rel
    if not target.is_file() or target.is_symlink():
        return False
    if copy.get("byte_identical") is not True or copy.get("old_anchor_retained") is not True:
        fail(f"P4-29 copy entry must keep byte-identical/old-anchor boundary: {target_rel}")
    if copy.get("source_sha256") != current_source_hash or copy.get("target_sha256") != sha256(target):
        fail(f"P4-29 copy entry hash is stale: {target_rel}")
    return sha256(target) == current_source_hash


def validate_source_truth(manifest: dict[str, Any]) -> None:
    source = manifest.get("source_truth")
    if not isinstance(source, dict):
        fail("source_truth must be an object")
    expected = {
        "p4_27_preflight": P4_27_PREFLIGHT,
        "p4_26_route": P4_26_ROUTE,
        "p4_25_manifest": P4_25_MANIFEST,
        "contract_split": CONTRACT_SPLIT,
    }
    for key, path in expected.items():
        if source.get(f"{key}_path") != str(path.relative_to(ROOT)):
            fail(f"source_truth.{key}_path mismatch")
        if source.get(f"{key}_sha256") != sha256(path):
            fail(f"source_truth.{key}_sha256 is stale")


def validate_p4_27_preflight() -> list[dict[str, Any]]:
    downstream_apply = downstream_apply_manifest()
    p4_27 = load_json(P4_27_PREFLIGHT, "P4-27 preflight")
    if p4_27.get("status") != "apply-preflight-only-no-files-copied-moved-or-deleted":
        fail("P4-27 preflight status must remain preflight-only")
    boundary = p4_27.get("claim_boundary", {})
    require_bool(boundary.get("apply_preflight_completed"), True, "P4-27 apply_preflight_completed")
    for key in [
        "physical_apply_completed",
        "files_copied",
        "files_moved",
        "files_deleted",
        "old_anchors_removed_or_replaced",
        "raw_run_evidence_deleted_or_cleaned",
        "release_switch_changed",
        "layer_a_product_decision_made",
        "release_blocker_closed",
        "public_release_ready",
    ]:
        require_bool(boundary.get(key), False, f"P4-27 claim_boundary.{key}")
    result = p4_27.get("result", {})
    if set(result.get("remaining_release_blockers_after_this_preflight", [])) != EXPECTED_BLOCKERS:
        fail("P4-27 must keep all expected release blockers open")
    selected = require_list(p4_27.get("selected_subset"), "P4-27 selected_subset", min_len=7)
    if len(selected) != 7:
        fail("P4-27 selected_subset must remain exactly 7 entries for this route")
    for item in selected:
        if not isinstance(item, dict):
            fail("P4-27 selected_subset entries must be objects")
        source = item.get("source")
        target = item.get("future_target")
        if not isinstance(source, str) or not (ROOT / source).is_file():
            fail(f"P4-27 selected source missing: {source}")
        current_source_hash = sha256(ROOT / source)
        preflight_source_hash = item.get("source_sha256")
        if preflight_source_hash != current_source_hash and not downstream_source_update(
            downstream_apply,
            source,
            str(preflight_source_hash),
            current_source_hash,
        ):
            fail(f"P4-27 selected source hash stale without P4-29 downstream bridge: {source}")
        if not isinstance(target, str) or not target.startswith("contracts/"):
            fail(f"P4-27 future target must be under contracts/: {target}")
        if (ROOT / target).exists() and not target_allowed_by_downstream_apply(
            downstream_apply,
            source,
            target,
            current_source_hash,
        ):
            fail(f"P4-28 route target exists without valid P4-29 downstream apply bridge: {target}")
    return selected


def validate_candidates(manifest: dict[str, Any]) -> None:
    candidates = require_list(manifest.get("candidate_matrix"), "candidate_matrix", min_len=7)
    by_id = {candidate.get("id"): candidate for candidate in candidates if isinstance(candidate, dict)}
    if by_id.get("A", {}).get("selected") is not True:
        fail("candidate A must be selected")
    for candidate_id in ["B", "C", "D", "E", "F", "G"]:
        if by_id.get(candidate_id, {}).get("selected") is not False:
            fail(f"candidate {candidate_id} must not be selected")
    for candidate_id in ["D", "E", "F", "G"]:
        require_bool(by_id.get(candidate_id, {}).get("requires_human_decision"), True, f"candidate {candidate_id}.requires_human_decision")
    for candidate in candidates:
        if isinstance(candidate, dict):
            require_bool(candidate.get("implemented_by_this_task"), False, f"candidate {candidate.get('id')}.implemented_by_this_task")


def validate_selected_next(manifest: dict[str, Any], selected_subset: list[dict[str, Any]]) -> None:
    selected = manifest.get("selected_next_slice")
    if not isinstance(selected, dict):
        fail("selected_next_slice must be an object")
    if selected.get("backlog_item_id") != "P4-29":
        fail("selected_next_slice.backlog_item_id must be P4-29")
    if selected.get("selected_candidate") != "A":
        fail("selected_next_slice.selected_candidate must be A")
    if selected.get("mode") != "copy-first-apply":
        fail("selected_next_slice.mode must be copy-first-apply")
    scope = "\n".join(str(item) for item in require_list(selected.get("scope"), "selected_next_slice.scope", min_len=4))
    for phrase in ["Keep the original", "Do not delete", "Do not clean", "Do not change", "Do not close"]:
        if phrase not in scope:
            fail(f"selected_next_slice.scope missing boundary phrase: {phrase}")
    gates = "\n".join(str(item) for item in require_list(selected.get("entry_gates_for_future_task"), "selected_next_slice.entry_gates_for_future_task", min_len=4))
    for phrase in ["Prism", "old references", "package", "clean workspace", "release blockers"]:
        if phrase not in gates:
            fail(f"entry_gates_for_future_task missing phrase: {phrase}")
    future_targets = {str(item.get("future_target")) for item in selected_subset if isinstance(item, dict)}
    if len(future_targets) != 7:
        fail("selected_next_slice must be grounded in exactly seven future targets from P4-27")


def validate_prism_review(manifest: dict[str, Any]) -> None:
    review = manifest.get("prism_review")
    if not isinstance(review, dict):
        fail("prism_review must be an object")
    if review.get("run_id") != EXPECTED_RUN_ID:
        fail("prism_review.run_id mismatch")
    if review.get("verdict") != "consensus-selects-A-register-p4-29-copy-first-apply":
        fail("prism_review.verdict must record consensus route A")
    agents = require_list(review.get("agents"), "prism_review.agents", min_len=3)
    responded = {
        str(agent.get("provider")): agent
        for agent in agents
        if isinstance(agent, dict) and agent.get("status") == "responded"
    }
    for provider in ["claude-code", "kimi"]:
        if responded.get(provider, {}).get("recommendation") != "A":
            fail(f"prism_review must include responded {provider} recommendation A")
    copilot = next((agent for agent in agents if isinstance(agent, dict) and agent.get("provider") == "copilot"), None)
    if not isinstance(copilot, dict) or copilot.get("status") != "policy-suppressed":
        fail("copilot must remain policy-suppressed")


def validate_claim_boundary(manifest: dict[str, Any]) -> None:
    boundary = manifest.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    for key in ["route_selection_completed", "selected_next_item_registered"]:
        require_bool(boundary.get(key), True, f"claim_boundary.{key}")
    for key in [
        "selected_next_slice_implemented",
        "contract_mirror_copy_first_apply_completed",
        "physical_apply_completed",
        "contracts_targets_created",
        "release_blocker_closed",
        "internal_control_plane_closed",
        "prism_layer_and_evidence_closed",
        "old_anchors_removed_or_replaced",
        "raw_run_evidence_deleted_or_cleaned",
        "layer_a_product_decision_made",
        "release_switch_changed",
        "public_release_ready",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")


def validate_result(manifest: dict[str, Any]) -> None:
    result = manifest.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    if result.get("release_blocker_status") != "still-blocking-after-route-selection":
        fail("result.release_blocker_status must remain still-blocking-after-route-selection")
    if result.get("selected_next_backlog_item") != "P4-29":
        fail("result.selected_next_backlog_item must be P4-29")
    require_bool(result.get("selected_next_slice_implemented"), False, "result.selected_next_slice_implemented")
    require_bool(result.get("contract_mirror_copy_first_apply_completed"), False, "result.contract_mirror_copy_first_apply_completed")
    require_bool(result.get("public_release_ready"), False, "result.public_release_ready")
    if set(result.get("remaining_release_blockers_after_this_route_selection", [])) != EXPECTED_BLOCKERS:
        fail("result.remaining_release_blockers_after_this_route_selection must keep all blockers open")


def validate_backlog() -> None:
    backlog = load_json(BACKLOG, "framework upgrade backlog")
    items = {item.get("id"): item for item in iter_backlog_items(backlog)}
    if items.get("P4-28", {}).get("status") not in {"pending", "done"}:
        fail("P4-28 must be registered as pending or done")
    if items.get("P4-28", {}).get("status") == "pending" and backlog.get("current_focus", {}).get("item_id") != "P4-28":
        fail("current_focus.item_id must be P4-28 while P4-28 is pending")
    if items.get("P4-28", {}).get("status") == "done":
        if backlog.get("current_focus", {}).get("item_id") == "P4-28":
            fail("current_focus.item_id must advance after P4-28 is done")
        if items.get("P4-29", {}).get("status") not in {"pending", "done"}:
            fail("P4-29 must be registered after P4-28 is done")


def validate_reports() -> None:
    for path, label in [(PRISM_REPORT, "Prism report"), (TASK_REPORT, "task report")]:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for phrase in ["P4-28", "P4-29", "路线", "不实施"]:
            if phrase not in text:
                fail(f"{label} missing required phrase: {phrase}")
        for forbidden in ["已可发布", "已正式发布", "旧锚点已删除", "raw evidence 已清理", "合同镜像已实施"]:
            if forbidden in text:
                fail(f"{label} contains forbidden overclaim: {forbidden}")


def validate(manifest: dict[str, Any]) -> dict[str, str]:
    if manifest.get("version") != 1:
        fail("version must be 1")
    if manifest.get("decision_id") != "redcap-r1-next-safe-slice-after-contract-mirror-apply-preflight-subset":
        fail("decision_id mismatch")
    if manifest.get("status") != "selected-next-slice-no-apply-no-blocker-closed":
        fail("status mismatch")
    validate_source_truth(manifest)
    selected_subset = validate_p4_27_preflight()
    validate_candidates(manifest)
    validate_selected_next(manifest, selected_subset)
    validate_prism_review(manifest)
    validate_claim_boundary(manifest)
    validate_result(manifest)
    validate_backlog()
    validate_reports()
    return {"selected": "A", "next": "P4-29"}


def main() -> int:
    manifest = load_json(DEFAULT_MANIFEST, "P4-28 route-selection manifest")
    result = validate(manifest)
    print(
        "R1_NEXT_SAFE_SLICE_AFTER_CONTRACT_MIRROR_APPLY_PREFLIGHT_SUBSET_OK "
        f"selected={result['selected']} next={result['next']} release_blocker_status=still-blocking"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# 用途：正式发布 R1 合同镜像 copy-first 实施验收；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "references/r1-contract-mirror-bounded-copy-first-apply.json"
P4_27_PREFLIGHT = ROOT / "references/r1-contract-mirror-apply-preflight-subset.json"
P4_28_ROUTE = ROOT / "references/r1-next-safe-slice-after-contract-mirror-apply-preflight-subset.json"
EXPECTED_TARGETS = {
    "contracts/public/runtime-public-contract-policy.json",
    "contracts/public/runtime-workspace-boundary-policy.json",
    "contracts/public/public-package-surface-policy.json",
    "contracts/public/package-publish-safety-policy.json",
    "contracts/internal/execution-guarantees.json",
    "contracts/internal/workflow-gate-stratification-policy.json",
    "contracts/internal/layerb-change-intake-policy.json",
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-contract-mirror-bounded-copy-first-apply-check] {message}")


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


def require_list(value: Any, label: str, *, min_len: int) -> list[Any]:
    if not isinstance(value, list) or len(value) < min_len:
        fail(f"{label} must be a list with at least {min_len} item(s)")
    return value


def git_tracked(rel: str) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--", rel],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return rel in {line.strip() for line in completed.stdout.splitlines()}


def actual_contract_files() -> set[str]:
    root = ROOT / "contracts"
    if not root.exists():
        return set()
    return {
        path.relative_to(ROOT).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def preflight_selected_targets() -> dict[str, dict[str, Any]]:
    preflight = load_json(P4_27_PREFLIGHT, "P4-27 preflight manifest")
    selected = require_list(preflight.get("selected_subset"), "P4-27 selected_subset", min_len=7)
    result: dict[str, dict[str, Any]] = {}
    for item in selected:
        if not isinstance(item, dict):
            fail("P4-27 selected_subset entries must be objects")
        target = require_text(item.get("future_target"), "P4-27 selected_subset.future_target")
        result[target] = item
    if set(result) != EXPECTED_TARGETS:
        fail("P4-27 selected targets do not match expected P4-29 target set")
    return result


def source_update_bridge(payload: dict[str, Any], source_rel: str, preflight_hash: str, current_hash: str) -> bool:
    updates = payload.get("source_updates_after_preflight", [])
    if not isinstance(updates, list):
        fail("source_updates_after_preflight must be a list when present")
    matched = False
    for item in updates:
        if not isinstance(item, dict):
            fail("source_updates_after_preflight entries must be objects")
        source = require_text(item.get("source"), "source_updates_after_preflight.source")
        if source != source_rel:
            continue
        matched = True
        if item.get("preflight_source_sha256") != preflight_hash:
            fail(f"source update bridge preflight hash mismatch: {source_rel}")
        if item.get("current_source_sha256") != current_hash:
            fail(f"source update bridge current hash mismatch: {source_rel}")
        target = require_text(item.get("target"), "source_updates_after_preflight.target")
        target_copy = next(
            (copy for copy in payload.get("copies", []) if isinstance(copy, dict) and copy.get("source") == source_rel),
            None,
        )
        if not isinstance(target_copy, dict) or target_copy.get("target") != target:
            fail(f"source update bridge must point at the copied target: {source_rel}")
        reason = require_text(item.get("reason"), "source_updates_after_preflight.reason")
        if "P4-29" not in reason or "exclusion" not in reason.lower():
            fail(f"source update bridge reason must explain the P4-29 package-surface exclusion: {source_rel}")
    return matched


def validate_source_updates_after_preflight(payload: dict[str, Any], selected_by_target: dict[str, dict[str, Any]]) -> None:
    updates = payload.get("source_updates_after_preflight", [])
    if not isinstance(updates, list):
        fail("source_updates_after_preflight must be a list")
    allowed_sources = {
        require_text(item.get("source"), "P4-27 selected_subset.source")
        for item in selected_by_target.values()
    }
    seen: set[str] = set()
    for item in updates:
        if not isinstance(item, dict):
            fail("source_updates_after_preflight entries must be objects")
        source = require_text(item.get("source"), "source_updates_after_preflight.source")
        if source in seen:
            fail(f"duplicate source update bridge: {source}")
        seen.add(source)
        if source not in allowed_sources:
            fail(f"source update bridge outside selected P4-27 subset: {source}")
        current = sha256(ROOT / source)
        if item.get("current_source_sha256") != current:
            fail(f"source update bridge current hash stale: {source}")
        if item.get("preflight_source_sha256") == current:
            fail(f"source update bridge must only be used for real post-preflight drift: {source}")


def validate_source_truth(payload: dict[str, Any]) -> None:
    source = payload.get("source_truth")
    if not isinstance(source, dict):
        fail("source_truth must be an object")
    if source.get("p4_27_preflight_path") != "references/r1-contract-mirror-apply-preflight-subset.json":
        fail("source_truth.p4_27_preflight_path mismatch")
    if source.get("p4_28_route_path") != "references/r1-next-safe-slice-after-contract-mirror-apply-preflight-subset.json":
        fail("source_truth.p4_28_route_path mismatch")
    if source.get("p4_27_preflight_sha256") != sha256(P4_27_PREFLIGHT):
        fail("source_truth.p4_27_preflight_sha256 is stale")
    if source.get("p4_28_route_sha256") != sha256(P4_28_ROUTE):
        fail("source_truth.p4_28_route_sha256 is stale")


def validate_copy_policy(payload: dict[str, Any]) -> None:
    policy = payload.get("copy_policy")
    if not isinstance(policy, dict):
        fail("copy_policy must be an object")
    if policy.get("mode") != "bounded-copy-first":
        fail("copy_policy.mode mismatch")
    if policy.get("selected_count") != 7:
        fail("copy_policy.selected_count must be 7")
    require_bool(policy.get("old_anchors_retained"), True, "copy_policy.old_anchors_retained")
    require_bool(policy.get("old_anchors_remain_authoritative"), True, "copy_policy.old_anchors_remain_authoritative")
    for key in [
        "delete_last_authorized",
        "release_blocker_closure_authorized",
        "raw_evidence_cleanup_authorized",
        "layer_a_product_decision_authorized",
    ]:
        require_bool(policy.get(key), False, f"copy_policy.{key}")


def validate_claim_boundary(payload: dict[str, Any]) -> None:
    boundary = payload.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    require_bool(boundary.get("copy_first_apply_completed"), True, "claim_boundary.copy_first_apply_completed")
    require_bool(boundary.get("target_files_created"), True, "claim_boundary.target_files_created")
    require_bool(boundary.get("old_anchors_retained"), True, "claim_boundary.old_anchors_retained")
    for key in [
        "old_anchors_removed_or_replaced",
        "extra_contract_files_created",
        "raw_run_evidence_deleted_or_cleaned",
        "release_switch_changed",
        "release_blocker_closed",
        "public_release_ready",
        "layer_a_product_decision_made",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")
    forbidden = require_list(boundary.get("forbidden_claims"), "claim_boundary.forbidden_claims", min_len=3)
    if not any("Release blockers" in str(item) or "release" in str(item).lower() for item in forbidden):
        fail("claim_boundary.forbidden_claims must include release/blocker boundary")


def validate_prism(payload: dict[str, Any]) -> None:
    review = payload.get("prism_review")
    if not isinstance(review, dict):
        fail("prism_review must be an object")
    if review.get("run_id") != "20260523-r1-contract-mirror-bounded-copy-first-apply":
        fail("prism_review.run_id mismatch")
    agents = require_list(review.get("agents"), "prism_review.agents", min_len=2)
    approved = {
        str(item.get("provider", "")).strip()
        for item in agents
        if isinstance(item, dict)
        and item.get("status") == "responded"
        and item.get("recommendation") == "approve"
        and item.get("safe_to_apply") is True
    }
    if not {"claude-code", "kimi"} <= approved:
        fail("Prism review must include claude-code and kimi approve responses")
    for item in agents:
        if isinstance(item, dict) and item.get("provider") == "copilot":
            if item.get("status") != "policy-suppressed":
                fail("Copilot must remain policy-suppressed for this task")


def validate_copies(payload: dict[str, Any]) -> None:
    preflight_targets = preflight_selected_targets()
    validate_source_updates_after_preflight(payload, preflight_targets)
    copies = require_list(payload.get("copies"), "copies", min_len=7)
    if len(copies) != 7:
        fail("copies must contain exactly 7 entries")
    seen_targets: set[str] = set()
    actual_targets = actual_contract_files()
    if actual_targets != EXPECTED_TARGETS:
        extra = sorted(actual_targets - EXPECTED_TARGETS)
        missing = sorted(EXPECTED_TARGETS - actual_targets)
        fail(f"contracts/** file set mismatch; extra={extra} missing={missing}")
    for item in copies:
        if not isinstance(item, dict):
            fail("copies entries must be objects")
        source_rel = require_text(item.get("source"), "copy.source")
        target_rel = require_text(item.get("target"), "copy.target")
        if target_rel in seen_targets:
            fail(f"duplicate copy target: {target_rel}")
        seen_targets.add(target_rel)
        if target_rel not in EXPECTED_TARGETS:
            fail(f"unexpected copy target: {target_rel}")
        selected = preflight_targets[target_rel]
        if selected.get("source") != source_rel:
            fail(f"copy source does not match P4-27 preflight for {target_rel}")
        source = ROOT / source_rel
        target = ROOT / target_rel
        if not source.is_file():
            fail(f"source missing: {source_rel}")
        if not target.is_file():
            fail(f"target missing: {target_rel}")
        if source.is_symlink() or target.is_symlink():
            fail(f"copy source/target must not be symlink: {source_rel} -> {target_rel}")
        if not git_tracked(source_rel):
            fail(f"source old anchor is not git-tracked: {source_rel}")
        if not git_tracked(target_rel):
            fail(f"target copy is not git-tracked: {target_rel}")
        source_hash = sha256(source)
        target_hash = sha256(target)
        preflight_hash = require_text(selected.get("source_sha256"), "P4-27 selected_subset.source_sha256")
        if source_hash != preflight_hash and not source_update_bridge(payload, source_rel, preflight_hash, source_hash):
            fail(f"source hash drift from P4-27 preflight without explicit P4-29 bridge: {source_rel}")
        if item.get("source_sha256") != source_hash:
            fail(f"manifest source hash stale: {source_rel}")
        if item.get("target_sha256") != target_hash:
            fail(f"manifest target hash stale: {target_rel}")
        if source_hash != target_hash or source.read_bytes() != target.read_bytes():
            fail(f"target is not byte-identical to source: {target_rel}")
        require_bool(item.get("byte_identical"), True, f"copies[{target_rel}].byte_identical")
        require_bool(item.get("old_anchor_retained"), True, f"copies[{target_rel}].old_anchor_retained")
        if item.get("copy_mode") != "copy-first":
            fail(f"copy_mode must be copy-first: {target_rel}")
    if seen_targets != EXPECTED_TARGETS:
        fail("manifest copy targets do not match expected target set")


def validate_manifest(path: Path) -> dict[str, Any]:
    payload = load_json(path, "P4-29 copy-first manifest")
    if payload.get("apply_id") != "redcap-r1-contract-mirror-bounded-copy-first-apply":
        fail("apply_id mismatch")
    if payload.get("status") != "copy-first-apply-old-anchors-retained-no-release-blocker-closed":
        fail("status mismatch")
    validate_source_truth(payload)
    validate_copy_policy(payload)
    validate_copies(payload)
    validate_prism(payload)
    validate_claim_boundary(payload)
    result = payload.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    if "still-blocking" not in require_text(result.get("release_blocker_status"), "result.release_blocker_status"):
        fail("release blocker must remain still-blocking")
    require_bool(result.get("public_release_ready"), False, "result.public_release_ready")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()
    manifest = Path(args.manifest)
    if not manifest.is_absolute():
        manifest = ROOT / manifest
    payload = validate_manifest(manifest)
    print(
        "R1_CONTRACT_MIRROR_BOUNDED_COPY_FIRST_APPLY_OK "
        f"copies={len(payload['copies'])} "
        f"old_anchors_retained={str(payload['copy_policy']['old_anchors_retained']).lower()} "
        f"release_blocker_status={payload['result']['release_blocker_status']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

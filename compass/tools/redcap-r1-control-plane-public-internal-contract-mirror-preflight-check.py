#!/usr/bin/env python3
# 用途：正式发布 R1 控制面 public/internal contract mirror 预检验收；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "references/r1-control-plane-public-internal-contract-mirror-preflight.json"
P4_24_ROUTE = ROOT / "references/r1-next-safe-slice-after-internal-maintainer-facade-batch-2.json"
CONTRACT_SPLIT = ROOT / "references/r1-control-plane-contract-split-preflight.json"
PHYSICAL_PREFLIGHT = ROOT / "references/r1-control-plane-physical-apply-preflight.json"
BACKLOG = ROOT / "references/backlogs/framework-upgrade.json"
PRISM_REPORT = ROOT / "prism/reports/2026-05-23-r1-control-plane-public-internal-contract-mirror-preflight.md"
TASK_REPORT = ROOT / "compass/docs/task-reports/2026-05-23-r1-control-plane-public-internal-contract-mirror-preflight.md"

EXPECTED_STATUS = "contract-mirror-preflight-only-no-files-copied-moved-or-deleted"
EXPECTED_COUNTS = {
    "runtime-public-support": 47,
    "public-contract": 11,
    "internal-contract": 56,
    "human-handoff": 1,
    "internal-control-plane": 122,
}
EXPECTED_PREFIXES = {
    "runtime-public-support": "runtime/redcap-core/",
    "public-contract": "contracts/public/",
    "internal-contract": "contracts/internal/",
    "human-handoff": "docs/release/",
    "internal-control-plane": "internal/control-plane/",
}
REQUIRED_BLOCKERS = {
    "internal-control-plane",
    "prism-layer-and-evidence",
    "internal-layer-a",
}
REQUIRED_CONSUMERS = {
    "root-runtime-facade",
    "release-readiness-safety",
    "layerb-closeout-and-governance",
    "knowledge-and-lookup-gateway",
    "prism-acceptance-binding",
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-control-plane-public-internal-contract-mirror-preflight-check] {message}")


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


def backlog_items(backlog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    for group in backlog.get("groups", []):
        if not isinstance(group, dict):
            continue
        for item in group.get("items", []):
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                items[item["id"]] = item
    return items


def validate_source_truth(manifest: dict[str, Any]) -> None:
    source_truth = manifest.get("source_truth")
    if not isinstance(source_truth, dict):
        fail("source_truth must be an object")
    expected = {
        "p4_24_route_path": ("references/r1-next-safe-slice-after-internal-maintainer-facade-batch-2.json", sha256(P4_24_ROUTE)),
        "control_plane_contract_split_path": ("references/r1-control-plane-contract-split-preflight.json", sha256(CONTRACT_SPLIT)),
        "control_plane_physical_preflight_path": ("references/r1-control-plane-physical-apply-preflight.json", sha256(PHYSICAL_PREFLIGHT)),
    }
    for path_key, (expected_path, expected_hash) in expected.items():
        if source_truth.get(path_key) != expected_path:
            fail(f"source_truth.{path_key} must be {expected_path}")
        hash_key = path_key.replace("_path", "_sha256")
        if source_truth.get(hash_key) != expected_hash:
            fail(f"source_truth.{hash_key} is stale")
    if source_truth.get("source_entries_count") != sum(EXPECTED_COUNTS.values()):
        fail(f"source_truth.source_entries_count must be {sum(EXPECTED_COUNTS.values())}")
    if source_truth.get("source_status") != "dry-run-only-no-files-moved":
        fail("source_truth.source_status must remain dry-run-only-no-files-moved")


def validate_contract_split() -> dict[str, int]:
    source = load_json(CONTRACT_SPLIT, "R1 control-plane contract split preflight")
    dry_run = source.get("physical_split_dry_run_manifest")
    if not isinstance(dry_run, dict):
        fail("source physical_split_dry_run_manifest must be an object")
    if dry_run.get("status") != "dry-run-only-no-files-moved":
        fail("source dry-run status must remain dry-run-only-no-files-moved")
    expected_total = sum(EXPECTED_COUNTS.values())
    entries = require_list(dry_run.get("entries"), "source dry-run entries", min_len=expected_total)
    if len(entries) != expected_total:
        fail(f"source dry-run entries must contain exactly {expected_total} items")

    counts: dict[str, int] = {}
    sources: set[str] = set()
    targets: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            fail("source dry-run entries must be objects")
        source_path = require_text(entry.get("source"), "entry.source")
        target_layer = require_text(entry.get("target_layer"), "entry.target_layer")
        target_path = require_text(entry.get("target_path"), "entry.target_path")
        if target_layer not in EXPECTED_COUNTS:
            fail(f"unexpected target_layer: {target_layer}")
        if not target_path.startswith(EXPECTED_PREFIXES[target_layer]):
            fail(f"{source_path} target_path must start with {EXPECTED_PREFIXES[target_layer]}")
        if source_path in sources:
            fail(f"duplicate source entry: {source_path}")
        if target_path in targets:
            fail(f"duplicate target_path entry: {target_path}")
        sources.add(source_path)
        targets.add(target_path)
        source_file = ROOT / source_path
        if not source_file.exists():
            fail(f"source anchor missing: {source_path}")
        if source_file.is_symlink():
            fail(f"source anchor must not be symlink-switched: {source_path}")
        if entry.get("current_state") != "unchanged-in-this-task":
            fail(f"{source_path} current_state must remain unchanged-in-this-task")
        if entry.get("future_action") != "copy-first-verify-alias-delete-last":
            fail(f"{source_path} future_action must remain copy-first-verify-alias-delete-last")
        counts[target_layer] = counts.get(target_layer, 0) + 1

    if counts != EXPECTED_COUNTS:
        fail(f"source target_layer counts are stale: {counts!r}")
    return counts


def validate_physical_preflight() -> None:
    physical = load_json(PHYSICAL_PREFLIGHT, "R1 control-plane physical apply preflight")
    policy = physical.get("operation_policy")
    if not isinstance(policy, dict):
        fail("physical preflight operation_policy must be an object")
    for key in [
        "apply_allowed_now",
        "destructive_operations_allowed",
        "old_anchor_mutation_allowed",
        "release_operations_allowed",
    ]:
        require_bool(policy.get(key), False, f"physical.operation_policy.{key}")
    result = physical.get("result")
    if not isinstance(result, dict):
        fail("physical preflight result must be an object")
    require_bool(result.get("physical_apply_completed"), False, "physical.result.physical_apply_completed")
    if result.get("release_blocker_status") != "still-blocking-release-until-future-physical-split-or-contract-resolution":
        fail("physical preflight must keep internal-control-plane blocker open")


def validate_manifest(manifest: dict[str, Any], source_counts: dict[str, int]) -> dict[str, Any]:
    if manifest.get("preflight_id") != "redcap-r1-control-plane-public-internal-contract-mirror-preflight":
        fail("preflight_id must match P4-25")
    if manifest.get("status") != EXPECTED_STATUS:
        fail(f"status must be {EXPECTED_STATUS}")

    boundary = manifest.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    require_bool(boundary.get("preflight_completed"), True, "claim_boundary.preflight_completed")
    for key in [
        "contract_mirror_implemented",
        "physical_split_completed",
        "files_copied",
        "files_moved",
        "files_deleted",
        "old_anchors_removed",
        "old_anchors_replaced",
        "raw_evidence_cleaned",
        "layer_a_product_decision_made",
        "release_switches_changed",
        "release_blocker_resolved",
        "public_release_ready",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")
    forbidden_claims = {require_text(item, "claim_boundary.forbidden_claims item") for item in require_list(boundary.get("forbidden_claims"), "claim_boundary.forbidden_claims", min_len=6)}
    for claim in [
        "The public/internal contract mirror has been physically implemented.",
        "The internal control plane has been physically split.",
        "Old compass or references anchors have been moved, replaced, or deleted.",
        "The internal-control-plane release blocker is resolved.",
        "RedCap is public-release-ready.",
    ]:
        if claim not in forbidden_claims:
            fail(f"claim_boundary.forbidden_claims missing {claim}")

    operation_policy = manifest.get("operation_policy")
    if not isinstance(operation_policy, dict):
        fail("operation_policy must be an object")
    for key in [
        "mirror_apply_allowed_now",
        "physical_move_allowed_now",
        "old_anchor_mutation_allowed",
        "destructive_operations_allowed",
        "release_operations_allowed",
        "raw_evidence_cleanup_allowed",
    ]:
        require_bool(operation_policy.get(key), False, f"operation_policy.{key}")

    classification = manifest.get("contract_classification")
    if not isinstance(classification, dict):
        fail("contract_classification must be an object")
    if classification.get("total_entries") != sum(EXPECTED_COUNTS.values()):
        fail(f"contract_classification.total_entries must be {sum(EXPECTED_COUNTS.values())}")
    groups = require_list(classification.get("groups"), "contract_classification.groups", min_len=5)
    manifest_counts: dict[str, int] = {}
    for group in groups:
        if not isinstance(group, dict):
            fail("contract_classification.groups entries must be objects")
        layer = require_text(group.get("source_target_layer"), "contract group source_target_layer")
        prefix = require_text(group.get("future_target_prefix"), "contract group future_target_prefix")
        if layer not in EXPECTED_COUNTS:
            fail(f"unexpected contract group layer: {layer}")
        if prefix != EXPECTED_PREFIXES[layer]:
            fail(f"{layer} future_target_prefix must be {EXPECTED_PREFIXES[layer]}")
        if group.get("count") != EXPECTED_COUNTS[layer]:
            fail(f"{layer} group count is stale")
        manifest_counts[layer] = group["count"]
    if manifest_counts != source_counts:
        fail("manifest contract counts must match source dry-run counts")

    collision_policy = classification.get("collision_policy")
    if not isinstance(collision_policy, dict):
        fail("contract_classification.collision_policy must be an object")
    for key in [
        "one_source_one_target_layer",
        "missing_source_allowed",
        "unclassified_entries_allowed",
    ]:
        expected = key == "one_source_one_target_layer"
        require_bool(collision_policy.get(key), expected, f"contract_classification.collision_policy.{key}")
    require_bool(collision_policy.get("public_internal_overlap_allowed"), False, "contract_classification.collision_policy.public_internal_overlap_allowed")

    consumers = require_list(manifest.get("consumer_bindings"), "consumer_bindings", min_len=5)
    consumer_ids = {require_text(item.get("consumer_id"), "consumer_bindings.consumer_id") for item in consumers if isinstance(item, dict)}
    if consumer_ids != REQUIRED_CONSUMERS:
        fail("consumer_bindings must exactly cover required consumers")
    for item in consumers:
        if not isinstance(item, dict):
            fail("consumer_bindings entries must be objects")
        if item.get("binding_mode") != "old-source-anchors-remain-authoritative":
            fail(f"{item.get('consumer_id')} binding_mode must keep old source anchors authoritative")
        require_list(item.get("future_gate"), f"{item.get('consumer_id')}.future_gate", min_len=2)

    review = manifest.get("prism_review")
    if not isinstance(review, dict):
        fail("prism_review must be an object")
    if review.get("run_id") != "20260523-r1-control-plane-public-internal-contract-mirror-preflight":
        fail("prism_review.run_id must match P4-25")
    agents = require_list(review.get("agents"), "prism_review.agents", min_len=3)
    providers = {agent.get("provider"): agent for agent in agents if isinstance(agent, dict)}
    if providers.get("claude-code", {}).get("status") != "responded":
        fail("claude-code Prism review must be present")
    if providers.get("kimi", {}).get("status") != "responded":
        fail("kimi Prism review must be present")
    if providers.get("copilot", {}).get("status") != "policy-suppressed":
        fail("copilot must remain policy-suppressed while Claude Code and Kimi responded")
    if "not physical apply" not in review.get("verdict", ""):
        fail("prism_review.verdict must forbid physical apply auto-upgrade")

    autocontinue = manifest.get("post_closeout_autocontinuation")
    if not isinstance(autocontinue, dict):
        fail("post_closeout_autocontinuation must be an object")
    require_bool(autocontinue.get("allowed"), True, "post_closeout_autocontinuation.allowed")
    if autocontinue.get("next_backlog_item") != "P4-26":
        fail("post_closeout_autocontinuation.next_backlog_item must be P4-26")
    if autocontinue.get("next_mode") != "route-selection-only":
        fail("post_closeout_autocontinuation.next_mode must be route-selection-only")

    result = manifest.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    if result.get("release_blocker_status") != "still-blocking-release-until-future-physical-split-or-contract-resolution":
        fail("result.release_blocker_status must keep internal-control-plane blocking")
    require_bool(result.get("this_contract_mirror_preflight_completed"), True, "result.this_contract_mirror_preflight_completed")
    require_bool(result.get("contract_mirror_implemented"), False, "result.contract_mirror_implemented")
    require_bool(result.get("physical_apply_completed"), False, "result.physical_apply_completed")
    blockers = set(require_list(result.get("remaining_release_blockers_after_this_preflight"), "result.remaining_release_blockers_after_this_preflight", min_len=3))
    if blockers != REQUIRED_BLOCKERS:
        fail("remaining_release_blockers_after_this_preflight must keep all three blockers")

    return {"entries": sum(EXPECTED_COUNTS.values()), "groups": len(groups), "next": "P4-26"}


def validate_backlog() -> None:
    backlog = load_json(BACKLOG, "framework upgrade backlog")
    items = backlog_items(backlog)
    if items.get("P4-24", {}).get("status") != "done":
        fail("P4-24 must be marked done")
    p4_25_status = items.get("P4-25", {}).get("status")
    current_focus = backlog.get("current_focus", {}).get("item_id")
    if p4_25_status == "pending":
        if current_focus != "P4-25":
            fail("current_focus.item_id must be P4-25 while P4-25 is pending")
    elif p4_25_status == "done":
        if current_focus == "P4-25":
            fail("current_focus.item_id must advance after P4-25 is done")
        p4_26_status = items.get("P4-26", {}).get("status")
        if p4_26_status not in {"pending", "done"}:
            fail("P4-26 must be registered as pending or done after P4-25 is done")
        if p4_26_status == "done":
            if current_focus == "P4-26":
                fail("current_focus.item_id must advance after P4-26 is done")
            p4_27_status = items.get("P4-27", {}).get("status")
            if p4_27_status not in {"pending", "done"}:
                fail("P4-27 must be registered as pending or done after P4-26 is done")
    else:
        fail("P4-25 must be registered as pending or done")


def validate_reports() -> None:
    for path, label in [(PRISM_REPORT, "Prism report"), (TASK_REPORT, "task report")]:
        if not path.is_file():
            fail(f"missing {label}: {path.relative_to(ROOT)}")
        text = path.read_text(encoding="utf-8")
        forbidden_fragments = [
            "RedCap 已可发布",
            "release blocker 已关闭",
            "控制面已物理拆分",
            "合同镜像已实施",
        ]
        for fragment in forbidden_fragments:
            if fragment in text:
                fail(f"{label} contains forbidden completion claim: {fragment}")


def validate(manifest: dict[str, Any]) -> dict[str, Any]:
    validate_source_truth(manifest)
    counts = validate_contract_split()
    validate_physical_preflight()
    summary = validate_manifest(manifest, counts)
    validate_backlog()
    validate_reports()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate P4-25 R1 control-plane public/internal contract mirror preflight.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()
    summary = validate(load_json(Path(args.manifest), "P4-25 contract mirror preflight manifest"))
    print(
        "R1_CONTROL_PLANE_PUBLIC_INTERNAL_CONTRACT_MIRROR_PREFLIGHT_OK "
        f"entries={summary['entries']} groups={summary['groups']} next={summary['next']} release_blocker_status=still-blocking"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

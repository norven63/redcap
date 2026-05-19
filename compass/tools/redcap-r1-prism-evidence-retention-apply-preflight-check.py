#!/usr/bin/env python3
# 用途：正式发布 R1 Prism 证据保留 apply 预检；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "references/r1-prism-evidence-retention-apply-preflight.json"
SOURCE_PREFLIGHT = ROOT / "references/r1-prism-evidence-retention-split-preflight.json"
REQUIRED_BLOCKERS = {
    "internal-control-plane",
    "prism-layer-and-evidence",
    "internal-layer-a",
}
REQUIRED_ALLOWED_OPS = {
    "copy-first-plan",
    "alias-first-plan",
    "report-index-migration-plan",
    "provider-policy-review-plan",
    "archive-check-plan",
    "verify-only",
}
REQUIRED_FORBIDDEN_OPS = {
    "delete",
    "move",
    "rename",
    "replace-old-anchor",
    "cleanup-apply",
    "prune-local-apply",
    "public-publish",
    "release-switch-change",
}
REQUIRED_BATCHES = {
    "batch-1-package-visible-prism-support",
    "batch-2-report-archive-index-migration",
    "batch-3-local-run-evidence-store",
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-prism-evidence-retention-apply-preflight-check] {message}")


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


def source_sha256() -> str:
    return hashlib.sha256(SOURCE_PREFLIGHT.read_bytes()).hexdigest()


def source_manifest() -> dict[str, Any]:
    source = load_json(SOURCE_PREFLIGHT, "R1 Prism evidence retention split preflight")
    dry_run = source.get("evidence_split_dry_run_manifest")
    if not isinstance(dry_run, dict):
        fail("source evidence_split_dry_run_manifest must be an object")
    if dry_run.get("status") != "dry-run-only-no-evidence-moved-or-deleted":
        fail("source dry-run manifest status is not dry-run-only-no-evidence-moved-or-deleted")
    return dry_run


def source_targets(dry_run: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    package_targets = require_list(dry_run.get("package_visible_targets"), "source package_visible_targets", min_len=1)
    evidence_targets = require_list(dry_run.get("source_evidence_targets"), "source source_evidence_targets", min_len=1)
    clean_package: list[dict[str, Any]] = []
    clean_evidence: list[dict[str, Any]] = []
    layers: Counter[str] = Counter()
    for item in package_targets:
        if not isinstance(item, dict):
            fail("source package_visible_targets entries must be objects")
        layer = require_text(item.get("target_layer"), "source package_visible_targets.target_layer")
        layers[layer] += 1
        clean_package.append(item)
    for item in evidence_targets:
        if not isinstance(item, dict):
            fail("source source_evidence_targets entries must be objects")
        layer = require_text(item.get("target_layer"), "source source_evidence_targets.target_layer")
        layers[layer] += 1
        clean_evidence.append(item)
    return clean_package, clean_evidence, dict(layers)


def validate(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("preflight_id") != "redcap-r1-prism-evidence-retention-apply-preflight":
        fail("preflight_id must be redcap-r1-prism-evidence-retention-apply-preflight")
    if manifest.get("status") != "apply-preflight-only-no-evidence-moved-deleted-or-cleaned":
        fail("status must remain apply-preflight-only-no-evidence-moved-deleted-or-cleaned")

    dry_run = source_manifest()
    package_targets, evidence_targets, by_layer = source_targets(dry_run)

    source_truth = manifest.get("source_truth")
    if not isinstance(source_truth, dict):
        fail("source_truth must be an object")
    if source_truth.get("path") != "references/r1-prism-evidence-retention-split-preflight.json":
        fail("source_truth.path must bind to references/r1-prism-evidence-retention-split-preflight.json")
    if source_truth.get("sha256") != source_sha256():
        fail("source_truth.sha256 is stale")
    if source_truth.get("package_visible_targets_count") != len(package_targets):
        fail("source_truth.package_visible_targets_count is stale")
    if source_truth.get("source_evidence_targets_count") != len(evidence_targets):
        fail("source_truth.source_evidence_targets_count is stale")
    if source_truth.get("source_status") != "dry-run-only-no-evidence-moved-or-deleted":
        fail("source_truth.source_status must remain dry-run-only-no-evidence-moved-or-deleted")
    if source_truth.get("source_release_blocker_status") != "still-blocking-release-until-future-evidence-retention-split-or-contract-resolution":
        fail("source_truth.source_release_blocker_status must keep prism-layer-and-evidence blocking")

    boundary = manifest.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    for key in [
        "physical_split_completed",
        "evidence_moved",
        "evidence_deleted",
        "evidence_cleaned",
        "cleanup_apply_performed",
        "old_anchors_removed",
        "old_anchors_replaced",
        "release_switches_changed",
        "release_blocker_resolved",
        "public_release_ready",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")
    require_text(boundary.get("allowed_user_claim"), "claim_boundary.allowed_user_claim")
    forbidden_claims = {
        require_text(item, "claim_boundary.forbidden_claims item")
        for item in require_list(boundary.get("forbidden_claims"), "claim_boundary.forbidden_claims", min_len=4)
    }
    for phrase in [
        "The Prism evidence layer has been physically split.",
        "Prism evidence has been moved, deleted, cleaned, or pruned.",
        "The prism-layer-and-evidence blocker is resolved.",
        "RedCap is public-release-ready.",
    ]:
        if phrase not in forbidden_claims:
            fail(f"claim_boundary.forbidden_claims missing {phrase}")

    policy = manifest.get("operation_policy")
    if not isinstance(policy, dict):
        fail("operation_policy must be an object")
    require_bool(policy.get("apply_allowed_now"), False, "operation_policy.apply_allowed_now")
    require_bool(policy.get("destructive_operations_allowed"), False, "operation_policy.destructive_operations_allowed")
    require_bool(policy.get("old_anchor_mutation_allowed"), False, "operation_policy.old_anchor_mutation_allowed")
    require_bool(policy.get("evidence_cleanup_allowed"), False, "operation_policy.evidence_cleanup_allowed")
    require_bool(policy.get("release_operations_allowed"), False, "operation_policy.release_operations_allowed")
    allowed_ops = {
        require_text(item, "allowed_future_operations item")
        for item in require_list(policy.get("allowed_future_operations"), "operation_policy.allowed_future_operations", min_len=6)
    }
    forbidden_ops = {
        require_text(item, "forbidden_operations item")
        for item in require_list(policy.get("forbidden_operations"), "operation_policy.forbidden_operations", min_len=8)
    }
    if not REQUIRED_ALLOWED_OPS.issubset(allowed_ops):
        fail("operation_policy.allowed_future_operations missing required safe ops")
    if not REQUIRED_FORBIDDEN_OPS.issubset(forbidden_ops):
        fail("operation_policy.forbidden_operations missing required forbidden ops")

    old_anchor = manifest.get("old_anchor_policy")
    if not isinstance(old_anchor, dict):
        fail("old_anchor_policy must be an object")
    for key in [
        "old_prism_tools_reports_and_runs_remain_authoritative",
        "old_paths_must_remain_resolvable",
        "delete_last_forbidden_in_this_task",
        "cleanup_apply_forbidden_in_this_task",
        "future_delete_last_or_cleanup_requires_separate_task",
    ]:
        require_bool(old_anchor.get(key), True, f"old_anchor_policy.{key}")
    required_before = {
        require_text(item, "old_anchor_policy.required_before_old_anchor_removal_or_cleanup item")
        for item in require_list(old_anchor.get("required_before_old_anchor_removal_or_cleanup"), "old_anchor_policy.required_before_old_anchor_removal_or_cleanup", min_len=8)
    }
    for gate in ["copy-first apply receipt", "report index migration proof", "archive-check pass", "package-safety proof", "clean workspace E2E", "Prism review"]:
        if gate not in required_before:
            fail(f"old_anchor_policy.required_before_old_anchor_removal_or_cleanup missing {gate}")

    coverage = manifest.get("coverage")
    if not isinstance(coverage, dict):
        fail("coverage must be an object")
    if coverage.get("package_visible_targets") != len(package_targets):
        fail("coverage.package_visible_targets is stale")
    if coverage.get("source_evidence_targets") != len(evidence_targets):
        fail("coverage.source_evidence_targets is stale")
    if coverage.get("by_target_layer") != by_layer:
        fail("coverage.by_target_layer is stale")
    require_bool(coverage.get("source_entries_reused_by_reference"), True, "coverage.source_entries_reused_by_reference")

    batches = require_list(manifest.get("apply_preflight_batches"), "apply_preflight_batches", min_len=3)
    batch_ids = set()
    for batch in batches:
        if not isinstance(batch, dict):
            fail("apply_preflight_batches entries must be objects")
        batch_id = require_text(batch.get("id"), "apply_preflight_batches.id")
        batch_ids.add(batch_id)
        mode = require_text(batch.get("mode"), f"{batch_id}.mode")
        if not mode.startswith("plan-only-copy-first-alias-first"):
            fail(f"{batch_id}.mode must be plan-only-copy-first-alias-first*")
        require_bool(batch.get("apply_now"), False, f"{batch_id}.apply_now")
        if not isinstance(batch.get("candidate_count"), int) or batch["candidate_count"] < 0:
            fail(f"{batch_id}.candidate_count must be a non-negative integer")
        require_list(batch.get("target_layers"), f"{batch_id}.target_layers")
        require_list(batch.get("required_before_apply"), f"{batch_id}.required_before_apply", min_len=4)
    if batch_ids != REQUIRED_BATCHES:
        fail("apply_preflight_batches must exactly cover " + ", ".join(sorted(REQUIRED_BATCHES)))

    result = manifest.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    if result.get("release_blocker_status") != "still-blocking-release-until-future-evidence-retention-split-or-contract-resolution":
        fail("result.release_blocker_status must keep prism-layer-and-evidence blocking")
    require_bool(result.get("this_apply_preflight_completed"), True, "result.this_apply_preflight_completed")
    require_bool(result.get("physical_apply_completed"), False, "result.physical_apply_completed")
    require_bool(result.get("evidence_cleanup_completed"), False, "result.evidence_cleanup_completed")
    blockers = set(require_list(result.get("remaining_release_blockers_after_this_preflight"), "result.remaining_release_blockers_after_this_preflight", min_len=3))
    if blockers != REQUIRED_BLOCKERS:
        fail("remaining_release_blockers_after_this_preflight must keep all three blockers")

    return {
        "package_targets": len(package_targets),
        "source_evidence_targets": len(evidence_targets),
        "batches": len(batches),
        "release_blocker_status": result["release_blocker_status"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate R1 Prism evidence retention apply preflight.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()
    manifest = load_json(Path(args.manifest), "R1 Prism evidence retention apply preflight")
    summary = validate(manifest)
    print(
        "R1_PRISM_EVIDENCE_RETENTION_APPLY_PREFLIGHT_OK "
        f"package_targets={summary['package_targets']} source_evidence_targets={summary['source_evidence_targets']} "
        f"batches={summary['batches']} release_blocker_status={summary['release_blocker_status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

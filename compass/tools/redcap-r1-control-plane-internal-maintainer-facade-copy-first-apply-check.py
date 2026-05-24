#!/usr/bin/env python3
# 用途：正式发布 R1 内部控制面维护工具 facade 小批次验收；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "references/r1-control-plane-internal-maintainer-facade-copy-first-apply.json"
CONTRACT_SPLIT = ROOT / "references/r1-control-plane-contract-split-preflight.json"
PHYSICAL_PREFLIGHT = ROOT / "references/r1-control-plane-physical-apply-preflight.json"
ROUTE_DECISION = ROOT / "references/r1-next-safe-slice-after-old-anchor-preflight.json"
EXPECTED_STATUS = "copy-first-internal-maintainer-facades-old-anchors-retained"
EXPECTED_LAYER = "internal-control-plane"
EXPECTED_TARGET_PREFIX = "internal/control-plane/tools/"
MAX_SELECTED = 10
REQUIRED_BLOCKERS = {
    "internal-control-plane",
    "prism-layer-and-evidence",
    "internal-layer-a",
}
FORBIDDEN_OPS = {
    "delete",
    "move",
    "rename",
    "replace-old-anchor",
    "prune",
    "public-publish",
    "release-switch-change",
    "raw-evidence-cleanup",
    "layer-a-product-decision",
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-control-plane-internal-maintainer-facade-copy-first-apply-check] {message}")


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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dry_run_entries() -> list[dict[str, Any]]:
    source = load_json(CONTRACT_SPLIT, "R1 control-plane contract split preflight")
    dry_run = source.get("physical_split_dry_run_manifest")
    if not isinstance(dry_run, dict):
        fail("contract split physical_split_dry_run_manifest must be an object")
    if dry_run.get("status") != "dry-run-only-no-files-moved":
        fail("contract split dry-run status must remain dry-run-only-no-files-moved")
    entries = require_list(dry_run.get("entries"), "contract split dry-run entries", min_len=1)
    clean: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            fail("contract split dry-run entries must be objects")
        clean.append(item)
    return clean


def assert_executable(path: Path) -> None:
    if not (path.stat().st_mode & stat.S_IXUSR):
        fail(f"facade is not executable: {path.relative_to(ROOT)}")


def validate_wrapper(source_rel: str, target_rel: str) -> None:
    source = ROOT / source_rel
    target = ROOT / target_rel
    if not source.is_file():
        fail(f"old compass/tools anchor missing: {source_rel}")
    if not target.is_file():
        fail(f"internal-control-plane facade missing: {target_rel}")
    assert_executable(target)
    text = target.read_text(encoding="utf-8", errors="replace")
    if source_rel not in text:
        fail(f"facade does not visibly delegate to old anchor: {target_rel}")
    if "compass/tools" not in text:
        fail(f"facade must keep compass/tools delegation visible: {target_rel}")
    if not text.startswith("#!/usr/bin/env bash"):
        fail(f"facade must be a bash wrapper: {target_rel}")
    subprocess.check_call(["bash", "-n", str(target)], cwd=ROOT)


def validate(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("apply_id") != "redcap-r1-control-plane-internal-maintainer-facade-copy-first-apply":
        fail("apply_id must be redcap-r1-control-plane-internal-maintainer-facade-copy-first-apply")
    if manifest.get("status") != EXPECTED_STATUS:
        fail(f"status must be {EXPECTED_STATUS}")

    route = load_json(ROUTE_DECISION, "P4-20 route decision")
    preflight = load_json(PHYSICAL_PREFLIGHT, "R1 control-plane physical apply preflight")
    entries = dry_run_entries()
    internal_entries = [
        item for item in entries
        if item.get("target_layer") == EXPECTED_LAYER
    ]
    dry_pairs = {
        (require_text(item.get("source"), "dry-run source"), require_text(item.get("target_path"), "dry-run target_path"))
        for item in internal_entries
    }

    source_truth = manifest.get("source_truth")
    if not isinstance(source_truth, dict):
        fail("source_truth must be an object")
    expected_truth = {
        "route_path": ("references/r1-next-safe-slice-after-old-anchor-preflight.json", sha256(ROUTE_DECISION)),
        "physical_preflight_path": ("references/r1-control-plane-physical-apply-preflight.json", sha256(PHYSICAL_PREFLIGHT)),
        "contract_split_path": ("references/r1-control-plane-contract-split-preflight.json", sha256(CONTRACT_SPLIT)),
    }
    for path_key, (expected_path, expected_hash) in expected_truth.items():
        if source_truth.get(path_key) != expected_path:
            fail(f"source_truth.{path_key} must be {expected_path}")
        hash_key = path_key.replace("_path", "_sha256")
        if source_truth.get(hash_key) != expected_hash:
            fail(f"source_truth.{hash_key} is stale")
    if source_truth.get("selected_backlog_item") != "P4-21":
        fail("source_truth.selected_backlog_item must be P4-21")
    if source_truth.get("source_target_layer") != EXPECTED_LAYER:
        fail(f"source_truth.source_target_layer must be {EXPECTED_LAYER}")
    if source_truth.get("source_entries_count") != len(internal_entries):
        fail("source_truth.source_entries_count is stale")
    if source_truth.get("selected_count") != len(require_list(manifest.get("facades"), "facades", min_len=1)):
        fail("source_truth.selected_count must match facades length")
    if route.get("result", {}).get("selected_next_backlog_item") != "P4-21":
        fail("route decision must still point to P4-21")
    if preflight.get("result", {}).get("release_blocker_status") != "still-blocking-release-until-future-physical-split-or-contract-resolution":
        fail("physical preflight must keep internal-control-plane blocking")

    boundary = manifest.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    require_bool(boundary.get("internal_maintainer_facades_created"), True, "claim_boundary.internal_maintainer_facades_created")
    for key in [
        "full_internal_control_plane_mirrored",
        "physical_split_completed",
        "files_moved",
        "files_deleted",
        "old_anchors_removed",
        "old_anchors_replaced",
        "prism_reports_changed",
        "prism_runs_cleaned",
        "release_switches_changed",
        "layer_a_product_boundary_changed",
        "release_blocker_resolved",
        "public_release_ready",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")
    forbidden_claims = {
        require_text(item, "claim_boundary.forbidden_claims item")
        for item in require_list(boundary.get("forbidden_claims"), "claim_boundary.forbidden_claims", min_len=5)
    }
    for phrase in [
        "The internal-control-plane blocker is resolved.",
        "All internal-control-plane entries were mirrored.",
        "compass/tools anchors were moved, deleted, or replaced.",
        "Prism raw evidence or reports were cleaned.",
        "RedCap is public-release-ready.",
    ]:
        if phrase not in forbidden_claims:
            fail(f"claim_boundary.forbidden_claims missing {phrase}")

    policy = manifest.get("operation_policy")
    if not isinstance(policy, dict):
        fail("operation_policy must be an object")
    if policy.get("allowed_operation") != "copy-first-internal-maintainer-facade-wrapper-only":
        fail("operation_policy.allowed_operation must be copy-first-internal-maintainer-facade-wrapper-only")
    require_bool(policy.get("old_compass_tools_authoritative"), True, "operation_policy.old_compass_tools_authoritative")
    require_bool(policy.get("destructive_operations_allowed"), False, "operation_policy.destructive_operations_allowed")
    require_bool(policy.get("release_operations_allowed"), False, "operation_policy.release_operations_allowed")
    require_bool(policy.get("layer_a_operations_allowed"), False, "operation_policy.layer_a_operations_allowed")
    forbidden_ops = {
        require_text(item, "operation_policy.forbidden_operations item")
        for item in require_list(policy.get("forbidden_operations"), "operation_policy.forbidden_operations", min_len=len(FORBIDDEN_OPS))
    }
    if not FORBIDDEN_OPS.issubset(forbidden_ops):
        fail("operation_policy.forbidden_operations missing required forbidden ops")

    facades = require_list(manifest.get("facades"), "facades", min_len=1)
    if len(facades) > MAX_SELECTED:
        fail(f"facades exceeds maximum safe batch size {MAX_SELECTED}")
    actual_pairs: set[tuple[str, str]] = set()
    for item in facades:
        if not isinstance(item, dict):
            fail("facades entries must be objects")
        source_rel = require_text(item.get("source"), "facades.source")
        target_rel = require_text(item.get("target_path"), "facades.target_path")
        if item.get("target_layer") != EXPECTED_LAYER:
            fail(f"facade target_layer must be {EXPECTED_LAYER}: {target_rel}")
        if not source_rel.startswith("compass/tools/") or not source_rel.endswith(".sh"):
            fail(f"facade source must be a compass/tools shell entrypoint: {source_rel}")
        if not target_rel.startswith(EXPECTED_TARGET_PREFIX) or not target_rel.endswith(".sh"):
            fail(f"facade target must be under {EXPECTED_TARGET_PREFIX}: {target_rel}")
        if item.get("current_state") != "copy-first-facade-created-old-anchor-authoritative":
            fail(f"facade current_state must declare old anchor authoritative: {target_rel}")
        actual_pairs.add((source_rel, target_rel))
        validate_wrapper(source_rel, target_rel)
    if not actual_pairs.issubset(dry_pairs):
        fail("facades must be selected from internal-control-plane dry-run entries")

    result = manifest.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    require_bool(result.get("this_apply_completed"), True, "result.this_apply_completed")
    require_bool(result.get("release_blocker_resolved"), False, "result.release_blocker_resolved")
    blockers = set(require_list(result.get("remaining_release_blockers_after_this_apply"), "result.remaining_release_blockers_after_this_apply", min_len=3))
    if blockers != REQUIRED_BLOCKERS:
        fail("remaining_release_blockers_after_this_apply must keep all three blockers")
    if result.get("next_recommended_tranche") != "continue-internal-control-plane-copy-first-or-select-next-safe-slice-via-prism":
        fail("result.next_recommended_tranche must keep next-step route open")

    return {"facades": len(facades), "available_internal_entries": len(internal_entries)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate P4-21 internal-control-plane maintainer facade copy-first apply.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()
    manifest = load_json(Path(args.manifest), "P4-21 internal-control-plane maintainer facade copy-first apply manifest")
    summary = validate(manifest)
    print(
        "R1_CONTROL_PLANE_INTERNAL_MAINTAINER_FACADE_COPY_FIRST_APPLY_OK "
        f"facades={summary['facades']} internal_entries={summary['available_internal_entries']} "
        "release_blocker_status=still-blocking"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

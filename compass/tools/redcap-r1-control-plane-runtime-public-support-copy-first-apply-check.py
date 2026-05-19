#!/usr/bin/env python3
# 用途：正式发布 R1 控制面 runtime facade copy-first 验收；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "references/r1-control-plane-runtime-public-support-copy-first-apply.json"
SOURCE_PREFLIGHT = ROOT / "references/r1-control-plane-physical-apply-preflight.json"
CONTRACT_SPLIT = ROOT / "references/r1-control-plane-contract-split-preflight.json"
EXPECTED_STATUS = "copy-first-facade-apply-only-old-anchors-retained"
EXPECTED_LAYER = "runtime-public-support"
FORBIDDEN_BATCH_LAYERS = {"public-contract", "internal-contract", "human-handoff", "internal-control-plane"}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-control-plane-runtime-public-support-copy-first-apply-check] {message}")


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


def expected_entries() -> list[dict[str, Any]]:
    source = load_json(CONTRACT_SPLIT, "R1 control-plane contract split preflight")
    dry_run = source.get("physical_split_dry_run_manifest")
    if not isinstance(dry_run, dict):
        fail("contract split physical_split_dry_run_manifest must be an object")
    if dry_run.get("status") != "dry-run-only-no-files-moved":
        fail("contract split dry-run status must remain dry-run-only-no-files-moved")
    entries = require_list(dry_run.get("entries"), "contract split dry-run entries", min_len=1)
    result: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            fail("contract split dry-run entries must be objects")
        layer = require_text(item.get("target_layer"), "entry.target_layer")
        if layer == EXPECTED_LAYER:
            result.append(item)
    if len(result) != 47:
        fail(f"expected 47 {EXPECTED_LAYER} entries, got {len(result)}")
    return result


def assert_executable(path: Path) -> None:
    mode = path.stat().st_mode
    if not (mode & stat.S_IXUSR):
        fail(f"facade is not executable: {path.relative_to(ROOT)}")


def validate_wrapper(source_rel: str, target_rel: str) -> None:
    source = ROOT / source_rel
    target = ROOT / target_rel
    if not source.is_file():
        fail(f"old compass/tools anchor missing: {source_rel}")
    if not target.is_file():
        fail(f"runtime facade missing: {target_rel}")
    assert_executable(target)
    text = target.read_text(encoding="utf-8", errors="replace")
    if source_rel not in text:
        fail(f"runtime facade does not delegate to old anchor: {target_rel}")
    if "compass/tools" not in text:
        fail(f"runtime facade must keep compass/tools delegation visible: {target_rel}")
    if target.suffix == ".sh":
        subprocess.check_call(["bash", "-n", str(target)], cwd=ROOT)
    elif target.suffix == ".py":
        pycache = Path(tempfile.mkdtemp(prefix="redcap-pycache-"))
        env = dict(os.environ)
        env["PYTHONPYCACHEPREFIX"] = str(pycache)
        subprocess.check_call(["python3", "-m", "py_compile", str(target)], cwd=ROOT, env=env)
    else:
        fail(f"unsupported facade extension: {target_rel}")


def validate(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("apply_id") != "redcap-r1-control-plane-runtime-public-support-copy-first-apply":
        fail("apply_id must be redcap-r1-control-plane-runtime-public-support-copy-first-apply")
    if manifest.get("status") != EXPECTED_STATUS:
        fail(f"status must be {EXPECTED_STATUS}")

    preflight = load_json(SOURCE_PREFLIGHT, "R1 control-plane physical apply preflight")
    expected = expected_entries()
    expected_pairs = {(entry["source"], entry["target_path"]) for entry in expected}

    source_truth = manifest.get("source_truth")
    if not isinstance(source_truth, dict):
        fail("source_truth must be an object")
    if source_truth.get("path") != "references/r1-control-plane-physical-apply-preflight.json":
        fail("source_truth.path must bind to the physical apply preflight")
    if source_truth.get("sha256") != sha256(SOURCE_PREFLIGHT):
        fail("source_truth.sha256 is stale")
    if source_truth.get("contract_split_path") != "references/r1-control-plane-contract-split-preflight.json":
        fail("source_truth.contract_split_path must bind to contract split preflight")
    if source_truth.get("contract_split_sha256") != sha256(CONTRACT_SPLIT):
        fail("source_truth.contract_split_sha256 is stale")
    if source_truth.get("source_batch_id") != "batch-1-runtime-public-support-facades":
        fail("source_truth.source_batch_id must be batch-1-runtime-public-support-facades")
    if source_truth.get("source_target_layer") != EXPECTED_LAYER:
        fail(f"source_truth.source_target_layer must be {EXPECTED_LAYER}")
    if source_truth.get("source_entries_count") != len(expected):
        fail("source_truth.source_entries_count is stale")
    if source_truth.get("source_release_blocker_resolved") is not False:
        fail("source_truth.source_release_blocker_resolved must stay false")
    if preflight.get("status") != source_truth.get("source_status"):
        fail("source_truth.source_status does not match physical apply preflight status")

    boundary = manifest.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    require_bool(boundary.get("runtime_facades_created"), True, "claim_boundary.runtime_facades_created")
    for key in [
        "physical_split_completed",
        "files_copied_as_implementation",
        "files_moved",
        "files_deleted",
        "old_anchors_removed",
        "old_anchors_replaced",
        "batch_2_or_3_executed",
        "release_switches_changed",
        "release_blocker_resolved",
        "public_release_ready",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")
    forbidden_claims = {
        require_text(item, "claim_boundary.forbidden_claims item")
        for item in require_list(boundary.get("forbidden_claims"), "claim_boundary.forbidden_claims", min_len=5)
    }
    for phrase in [
        "The internal control plane has been fully physically split.",
        "compass/tools anchors were moved, deleted, or replaced.",
        "batch-2 or batch-3 has been executed.",
        "The internal-control-plane blocker is resolved.",
        "RedCap is public-release-ready.",
    ]:
        if phrase not in forbidden_claims:
            fail(f"claim_boundary.forbidden_claims missing {phrase}")

    policy = manifest.get("operation_policy")
    if not isinstance(policy, dict):
        fail("operation_policy must be an object")
    require_bool(policy.get("facade_apply_completed"), True, "operation_policy.facade_apply_completed")
    require_bool(policy.get("old_compass_tools_authoritative"), True, "operation_policy.old_compass_tools_authoritative")
    for key in [
        "destructive_operations_allowed",
        "old_anchor_mutation_allowed",
        "release_operations_allowed",
    ]:
        require_bool(policy.get(key), False, f"operation_policy.{key}")
    if policy.get("allowed_operation") != "copy-first-facade-wrapper-only":
        fail("operation_policy.allowed_operation must be copy-first-facade-wrapper-only")
    forbidden_ops = {
        require_text(item, "operation_policy.forbidden_operations item")
        for item in require_list(policy.get("forbidden_operations"), "operation_policy.forbidden_operations", min_len=9)
    }
    for op in ["delete", "move", "rename", "replace-old-anchor", "batch-2", "batch-3", "prune", "public-publish", "release-switch-change"]:
        if op not in forbidden_ops:
            fail(f"operation_policy.forbidden_operations missing {op}")

    contract = manifest.get("facade_contract")
    if not isinstance(contract, dict):
        fail("facade_contract must be an object")
    if contract.get("root") != "runtime/redcap-core/tools":
        fail("facade_contract.root must be runtime/redcap-core/tools")
    if contract.get("old_implementation_root") != "compass/tools":
        fail("facade_contract.old_implementation_root must be compass/tools")
    if contract.get("facade_count") != len(expected):
        fail("facade_contract.facade_count is stale")

    facades = require_list(manifest.get("facades"), "facades", min_len=len(expected))
    actual_pairs: set[tuple[str, str]] = set()
    for item in facades:
        if not isinstance(item, dict):
            fail("facades entries must be objects")
        source_rel = require_text(item.get("source"), "facades.source")
        target_rel = require_text(item.get("target_path"), "facades.target_path")
        if item.get("target_layer") != EXPECTED_LAYER:
            fail(f"facade target_layer must be {EXPECTED_LAYER}: {target_rel}")
        if item.get("current_state") != "unchanged-in-this-task":
            fail(f"facade current_state must be unchanged-in-this-task: {target_rel}")
        if any(layer in target_rel for layer in FORBIDDEN_BATCH_LAYERS):
            fail(f"facade target appears to include forbidden batch layer: {target_rel}")
        actual_pairs.add((source_rel, target_rel))
        validate_wrapper(source_rel, target_rel)
    if actual_pairs != expected_pairs:
        fail("facades must exactly match runtime-public-support entries from contract split preflight")

    return {"facades": len(facades), "old_anchors": len(expected)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate R1 control-plane runtime public support copy-first facade apply.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()
    manifest = load_json(Path(args.manifest), "R1 control-plane runtime public support copy-first apply manifest")
    summary = validate(manifest)
    print(
        "R1_CONTROL_PLANE_RUNTIME_PUBLIC_SUPPORT_COPY_FIRST_APPLY_OK "
        f"facades={summary['facades']} old_anchors={summary['old_anchors']} "
        "release_blocker_status=still-blocking"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

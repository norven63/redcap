#!/usr/bin/env python3
# 用途：正式发布 R1 Prism package-visible support copy-first 验收；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "references/r1-prism-package-visible-support-copy-first-apply.json"
APPLY_PREFLIGHT = ROOT / "references/r1-prism-evidence-retention-apply-preflight.json"
SPLIT_PREFLIGHT = ROOT / "references/r1-prism-evidence-retention-split-preflight.json"
RUNTIME_MANIFEST = ROOT / "compass/tools/redcap-runtime-package-manifest.sh"
PROVIDER_POLICY = ROOT / "references/prism-provider-policy.json"
IMPORT_MAP = ROOT / "runtime/redcap-core/import-map.json"
BIN_REDCAP = ROOT / "bin/redcap"
EXPECTED_STATUS = "copy-first-facade-apply-only-old-prism-anchors-retained"
EXPECTED_BATCH = "batch-1-package-visible-prism-support"
EXPECTED_LAYERS = {"package-visible-prism-support", "provider-routing-contract"}
REQUIRED_BLOCKERS = {"internal-control-plane", "prism-layer-and-evidence", "internal-layer-a"}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-prism-package-visible-support-copy-first-apply-check] {message}")


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


def source_batch() -> list[dict[str, Any]]:
    source = load_json(SPLIT_PREFLIGHT, "R1 Prism evidence split preflight")
    dry_run = source.get("evidence_split_dry_run_manifest")
    if not isinstance(dry_run, dict):
        fail("split preflight evidence_split_dry_run_manifest must be an object")
    if dry_run.get("status") != "dry-run-only-no-evidence-moved-or-deleted":
        fail("split dry-run status must remain dry-run-only-no-evidence-moved-or-deleted")
    targets = require_list(dry_run.get("package_visible_targets"), "split package_visible_targets", min_len=1)
    result: list[dict[str, Any]] = []
    for item in targets:
        if not isinstance(item, dict):
            fail("split package_visible_targets entries must be objects")
        layer = require_text(item.get("target_layer"), "package_visible_targets.target_layer")
        if layer in EXPECTED_LAYERS:
            result.append(item)
    if len(result) != 8:
        fail(f"expected 8 batch-1 Prism package-visible entries, got {len(result)}")
    return result


def target_for(source_rel: str) -> str:
    if source_rel == "prism/README.md":
        return "runtime/redcap-core/prism-tools/README.md"
    if source_rel.startswith("prism/tools/"):
        return "runtime/redcap-core/prism-tools/" + Path(source_rel).name
    fail(f"unexpected batch-1 source path: {source_rel}")


def package_candidates() -> set[str]:
    if not RUNTIME_MANIFEST.is_file():
        fail("missing runtime package manifest generator")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        candidate_path = Path(handle.name)
    try:
        completed = subprocess.run(
            ["bash", str(RUNTIME_MANIFEST), "--output", str(candidate_path)],
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if completed.returncode != 0:
            sys.stdout.write(completed.stdout)
            fail("runtime package manifest generation failed")
        return {
            line.strip()
            for line in candidate_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    finally:
        try:
            candidate_path.unlink()
        except OSError:
            pass


def assert_executable(path: Path) -> None:
    mode = path.stat().st_mode
    if not (mode & stat.S_IXUSR):
        fail(f"facade is not executable: {path.relative_to(ROOT)}")


def validate_facade(source_rel: str, target_rel: str) -> None:
    source = ROOT / source_rel
    target = ROOT / target_rel
    if not source.is_file():
        fail(f"old Prism anchor missing: {source_rel}")
    if not target.is_file():
        fail(f"runtime Prism facade missing: {target_rel}")
    text = target.read_text(encoding="utf-8", errors="replace")
    if source_rel not in text:
        fail(f"runtime Prism facade does not reference source anchor: {target_rel}")
    if target.suffix == ".sh":
        assert_executable(target)
        subprocess.check_call(["bash", "-n", str(target)], cwd=ROOT)
    elif target.suffix == ".py":
        assert_executable(target)
        pycache = Path(tempfile.mkdtemp(prefix="redcap-pycache-"))
        env = dict(os.environ)
        env["PYTHONPYCACHEPREFIX"] = str(pycache)
        subprocess.check_call(["python3", "-m", "py_compile", str(target)], cwd=ROOT, env=env)
    elif target.suffix == ".md":
        if "runtime package" not in text and "package-visible" not in text:
            fail(f"runtime Prism README facade must explain package-visible boundary: {target_rel}")
    else:
        fail(f"unsupported runtime Prism facade extension: {target_rel}")


def validate_provider_policy(policy: dict[str, Any]) -> None:
    overrides = policy.get("routing_overrides")
    if not isinstance(overrides, list):
        fail("provider policy routing_overrides must be a list")
    by_agent = {item.get("agent"): item for item in overrides if isinstance(item, dict)}
    copilot = by_agent.get("copilot")
    if not isinstance(copilot, dict):
        fail("provider policy must keep copilot override")
    if copilot.get("priority_tier") != "protected-fallback":
        fail("copilot priority_tier must remain protected-fallback")
    if copilot.get("allowed_when_all_unavailable") != ["claude-code", "kimi"]:
        fail("copilot allowed_when_all_unavailable must remain ['claude-code', 'kimi']")
    codex = by_agent.get("codex")
    if not isinstance(codex, dict):
        fail("provider policy must keep codex override")
    if codex.get("priority_tier") != "last-resort":
        fail("codex priority_tier must remain last-resort")


def validate_runtime_routing() -> None:
    import_map = load_json(IMPORT_MAP, "runtime import map")
    entries = import_map.get("public_runtime_entrypoints")
    if not isinstance(entries, list):
        fail("runtime import map public_runtime_entrypoints must be a list")
    prism_entry = next((item for item in entries if isinstance(item, dict) and item.get("command") == "redcap prism-availability"), None)
    if not isinstance(prism_entry, dict):
        fail("runtime import map must include redcap prism-availability")
    if prism_entry.get("delegates_to") != "runtime/redcap-core/prism-tools/prism-availability.sh":
        fail("redcap prism-availability must delegate to runtime Prism facade")
    requires = prism_entry.get("requires")
    if not isinstance(requires, list):
        fail("redcap prism-availability requires must be a list")
    for required in [
        "runtime/redcap-core/prism-tools/prism-availability.sh",
        "runtime/redcap-core/prism-tools/prism-availability.py",
        "references/prism-provider-policy.json",
    ]:
        if required not in requires:
            fail(f"runtime import map missing Prism runtime requirement: {required}")
    bin_text = BIN_REDCAP.read_text(encoding="utf-8")
    if "runtime/redcap-core/prism-tools/prism-availability.sh" not in bin_text:
        fail("bin/redcap must route prism-availability through runtime Prism facade")


def validate(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("apply_id") != "redcap-r1-prism-package-visible-support-copy-first-apply":
        fail("apply_id must be redcap-r1-prism-package-visible-support-copy-first-apply")
    if manifest.get("status") != EXPECTED_STATUS:
        fail(f"status must be {EXPECTED_STATUS}")

    expected_sources = source_batch()
    expected_pairs = {
        (require_text(item.get("path"), "source target.path"), target_for(require_text(item.get("path"), "source target.path")))
        for item in expected_sources
    }

    source_truth = manifest.get("source_truth")
    if not isinstance(source_truth, dict):
        fail("source_truth must be an object")
    if source_truth.get("path") != "references/r1-prism-evidence-retention-apply-preflight.json":
        fail("source_truth.path must bind to the Prism apply preflight")
    if source_truth.get("sha256") != sha256(APPLY_PREFLIGHT):
        fail("source_truth.sha256 is stale")
    if source_truth.get("split_preflight_path") != "references/r1-prism-evidence-retention-split-preflight.json":
        fail("source_truth.split_preflight_path must bind to the Prism split preflight")
    if source_truth.get("split_preflight_sha256") != sha256(SPLIT_PREFLIGHT):
        fail("source_truth.split_preflight_sha256 is stale")
    if source_truth.get("source_batch_id") != EXPECTED_BATCH:
        fail(f"source_truth.source_batch_id must be {EXPECTED_BATCH}")
    if set(require_list(source_truth.get("source_target_layers"), "source_truth.source_target_layers", min_len=2)) != EXPECTED_LAYERS:
        fail("source_truth.source_target_layers must exactly cover package-visible support and provider routing")
    if source_truth.get("source_entries_count") != len(expected_pairs):
        fail("source_truth.source_entries_count is stale")
    require_bool(source_truth.get("source_release_blocker_resolved"), False, "source_truth.source_release_blocker_resolved")

    boundary = manifest.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    require_bool(boundary.get("runtime_prism_facades_created"), True, "claim_boundary.runtime_prism_facades_created")
    for key in [
        "physical_split_completed",
        "evidence_moved",
        "evidence_deleted",
        "evidence_cleaned",
        "old_anchors_removed",
        "old_anchors_replaced",
        "report_archive_migration_executed",
        "local_run_evidence_cleanup_executed",
        "release_switches_changed",
        "release_blocker_resolved",
        "public_release_ready",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")

    policy = manifest.get("operation_policy")
    if not isinstance(policy, dict):
        fail("operation_policy must be an object")
    require_bool(policy.get("facade_apply_completed"), True, "operation_policy.facade_apply_completed")
    require_bool(policy.get("old_prism_anchors_authoritative"), True, "operation_policy.old_prism_anchors_authoritative")
    for key in ["destructive_operations_allowed", "old_anchor_mutation_allowed", "evidence_cleanup_allowed", "release_operations_allowed"]:
        require_bool(policy.get(key), False, f"operation_policy.{key}")
    if policy.get("allowed_operation") != "copy-first-facade-wrapper-only":
        fail("operation_policy.allowed_operation must be copy-first-facade-wrapper-only")
    forbidden = {
        require_text(item, "operation_policy.forbidden_operations item")
        for item in require_list(policy.get("forbidden_operations"), "operation_policy.forbidden_operations", min_len=10)
    }
    for op in ["delete", "move", "rename", "replace-old-anchor", "cleanup-apply", "prune-local-apply", "public-publish", "release-switch-change"]:
        if op not in forbidden:
            fail(f"operation_policy.forbidden_operations missing {op}")

    contract = manifest.get("facade_contract")
    if not isinstance(contract, dict):
        fail("facade_contract must be an object")
    if contract.get("root") != "runtime/redcap-core/prism-tools":
        fail("facade_contract.root must be runtime/redcap-core/prism-tools")
    if contract.get("old_implementation_root") != "prism":
        fail("facade_contract.old_implementation_root must be prism")
    if contract.get("facade_count") != len(expected_pairs):
        fail("facade_contract.facade_count is stale")

    provider_contract = manifest.get("provider_routing_contract")
    if not isinstance(provider_contract, dict):
        fail("provider_routing_contract must be an object")
    require_bool(provider_contract.get("claude_code_and_kimi_priority_retained"), True, "provider_routing_contract.claude_code_and_kimi_priority_retained")
    require_bool(provider_contract.get("copilot_protected_fallback_retained"), True, "provider_routing_contract.copilot_protected_fallback_retained")
    if provider_contract.get("copilot_allowed_when_all_unavailable") != ["claude-code", "kimi"]:
        fail("provider_routing_contract.copilot_allowed_when_all_unavailable is stale")
    require_bool(provider_contract.get("codex_last_resort_retained"), True, "provider_routing_contract.codex_last_resort_retained")
    if provider_contract.get("provider_policy_path") != "references/prism-provider-policy.json":
        fail("provider_routing_contract.provider_policy_path must bind to prism-provider-policy.json")
    validate_provider_policy(load_json(PROVIDER_POLICY, "provider policy"))

    facades = require_list(manifest.get("facades"), "facades", min_len=len(expected_pairs))
    actual_pairs: set[tuple[str, str]] = set()
    for item in facades:
        if not isinstance(item, dict):
            fail("facades entries must be objects")
        source_rel = require_text(item.get("source"), "facades.source")
        target_rel = require_text(item.get("target_path"), "facades.target_path")
        layer = require_text(item.get("target_layer"), "facades.target_layer")
        if layer not in EXPECTED_LAYERS:
            fail(f"facade target_layer must be a batch-1 layer: {target_rel}")
        if item.get("current_state") != "old-anchor-retained":
            fail(f"facade current_state must be old-anchor-retained: {target_rel}")
        actual_pairs.add((source_rel, target_rel))
        validate_facade(source_rel, target_rel)
    if actual_pairs != expected_pairs:
        fail("facades must exactly match batch-1 package-visible Prism entries")

    candidates = package_candidates()
    surface = manifest.get("package_surface_delta")
    if not isinstance(surface, dict):
        fail("package_surface_delta must be an object")
    if surface.get("current_candidate_count") != len(candidates):
        fail("package_surface_delta.current_candidate_count is stale")
    if surface.get("delta") != surface.get("current_candidate_count") - surface.get("previous_candidate_count"):
        fail("package_surface_delta.delta is stale")
    for source_rel, target_rel in actual_pairs:
        if source_rel not in candidates:
            fail(f"old Prism source anchor must remain package-visible in copy-first slice: {source_rel}")
        if target_rel not in candidates:
            fail(f"runtime Prism facade must be package-visible: {target_rel}")
    if any(path.startswith("prism/runs/") for path in candidates):
        fail("prism/runs must not enter package candidates")
    if any(path.startswith("prism/reports/") for path in candidates):
        fail("prism/reports must not enter package candidates")

    validate_runtime_routing()

    result = manifest.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    if result.get("release_blocker_status") != "still-blocking-release-until-future-evidence-retention-split-or-contract-resolution":
        fail("result.release_blocker_status must keep prism-layer-and-evidence blocking")
    require_bool(result.get("this_copy_first_apply_completed"), True, "result.this_copy_first_apply_completed")
    require_bool(result.get("physical_split_completed"), False, "result.physical_split_completed")
    require_bool(result.get("evidence_cleanup_completed"), False, "result.evidence_cleanup_completed")
    blockers = set(require_list(result.get("remaining_release_blockers_after_this_apply"), "result.remaining_release_blockers_after_this_apply", min_len=3))
    if blockers != REQUIRED_BLOCKERS:
        fail("remaining_release_blockers_after_this_apply must keep all three blockers")

    return {"facades": len(actual_pairs), "candidate_count": len(candidates)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate R1 Prism package-visible support copy-first facade apply.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()
    manifest = load_json(Path(args.manifest), "R1 Prism package-visible support copy-first apply manifest")
    summary = validate(manifest)
    print(
        "R1_PRISM_PACKAGE_VISIBLE_SUPPORT_COPY_FIRST_APPLY_OK "
        f"facades={summary['facades']} candidate_count={summary['candidate_count']} "
        "release_blocker_status=still-blocking"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

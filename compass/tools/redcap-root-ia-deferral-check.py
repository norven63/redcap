#!/usr/bin/env python3
# 用途：检查 RASG-022 剩余高风险根目录是否有显式延期收据；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#product-shape-and-retrieval

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECEIPT = ROOT / "references/root-ia-remaining-root-groups-deferral.json"
DEFAULT_PLAN = ROOT / "references/root-information-architecture-consolidation-plan.json"
DEFAULT_BACKLOG = ROOT / "references/backlogs/redcap-architecture-smell-governance.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-root-ia-deferral-check] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"{label} missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label} json: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be a JSON object")
    return payload


def require_text(payload: dict[str, Any], key: str, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{label}: missing non-empty {key}")
    return value.strip()


def require_list(payload: dict[str, Any], key: str, label: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        fail(f"{label}: {key} must be a non-empty list")
    return value


def target_groups(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for item in require_list(plan, "target_parent_model", "plan"):
        if not isinstance(item, dict):
            fail("plan target_parent_model entries must be objects")
        item_id = require_text(item, "id", "target_parent_model entry")
        if item_id in groups:
            fail(f"duplicate target parent in plan: {item_id}")
        groups[item_id] = item
    return groups


def string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        fail(f"{label} must be a non-empty list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            fail(f"{label} entries must be non-empty strings")
        result.append(item.strip())
    return result


def require_existing_paths(paths: list[str], label: str) -> None:
    for raw in paths:
        path = ROOT / raw
        if not path.exists():
            fail(f"{label} evidence path missing: {raw}")


def validate_claim_boundary(receipt: dict[str, Any]) -> None:
    boundary = receipt.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    if boundary.get("all_root_physical_consolidation_completed") is not False:
        fail("claim_boundary must not claim all root physical consolidation is complete")
    if boundary.get("release_ready_claimed") is not False:
        fail("claim_boundary must not claim release readiness")
    allowed = require_text(boundary, "allowed_user_claim", "claim_boundary")
    for phrase in ["当前阶段", "显式延期"]:
        if phrase not in allowed:
            fail(f"allowed_user_claim missing phrase: {phrase}")
    forbidden = "\n".join(string_list(boundary.get("forbidden_claims"), "claim_boundary.forbidden_claims"))
    for phrase in ["All root information architecture physical consolidation is complete", "release-ready"]:
        if phrase not in forbidden:
            fail(f"forbidden_claims missing phrase: {phrase}")


def validate_applied(receipt: dict[str, Any]) -> set[str]:
    applied = require_list(receipt, "applied_parent_groups", "receipt")
    covered: set[str] = set()
    shared = None
    for item in applied:
        if not isinstance(item, dict):
            fail("applied_parent_groups entries must be objects")
        target = require_text(item, "target_parent", "applied parent group")
        covered.add(target)
        if item.get("applied_tranche") == "rasg-022-shared-knowledge-template-tranche":
            shared = item
    if shared is None:
        fail("applied_parent_groups missing shared-knowledge tranche")
    if shared.get("status") != "completed-closeout-receipted":
        fail("shared-knowledge tranche must be completed-closeout-receipted")
    if shared.get("canonical_root") != "templates/shared-knowledge":
        fail("shared-knowledge canonical root must be templates/shared-knowledge")
    evidence = string_list(shared.get("evidence"), "shared-knowledge evidence")
    require_existing_paths(evidence, "shared-knowledge")
    if not require_text(shared, "runtime_receipt_observed", "shared-knowledge"):
        fail("shared-knowledge runtime receipt observation missing")
    boundary = require_text(shared, "completion_boundary", "shared-knowledge")
    if "not close all root" not in boundary and "not the remaining" not in boundary:
        fail("shared-knowledge completion boundary must deny all-root completion")
    private_archive = next((item for item in applied if isinstance(item, dict) and item.get("target_parent") == "private-archive"), None)
    if private_archive is not None:
        if private_archive.get("applied_tranche") != "rasg-022-private-archive-physical-migration":
            fail("private-archive applied tranche id mismatch")
        if private_archive.get("status") not in {"completed-pending-closeout-receipt", "completed-closeout-receipted"}:
            fail("private-archive tranche status mismatch")
        if private_archive.get("canonical_root") != "private-archive/redcap-knowledge":
            fail("private-archive canonical root must be private-archive/redcap-knowledge")
        if private_archive.get("retired_root") != "redcap-knowledge":
            fail("private-archive retired root must be redcap-knowledge")
        evidence = string_list(private_archive.get("evidence"), "private-archive evidence")
        require_existing_paths(evidence, "private-archive")
        boundary = require_text(private_archive, "completion_boundary", "private-archive")
        if "not all" not in boundary and "not the remaining" not in boundary:
            fail("private-archive completion boundary must deny all-root completion")
    return covered


def validate_keep_at_root(receipt: dict[str, Any]) -> set[str]:
    keepers = require_list(receipt, "keep_at_root_boundaries", "receipt")
    covered: set[str] = set()
    for item in keepers:
        if not isinstance(item, dict):
            fail("keep_at_root_boundaries entries must be objects")
        target = require_text(item, "target_parent", "keep_at_root_boundary")
        require_text(item, "reason", target)
        covered.add(target)
    return covered


def validate_deferred(receipt: dict[str, Any], groups: dict[str, dict[str, Any]]) -> set[str]:
    deferred = require_list(receipt, "deferred_root_groups", "receipt")
    required = {
        "internal-control-plane",
        "prism-layer-and-evidence",
        "internal-layer-a",
        "workspace-state",
    }
    covered: set[str] = set()
    for item in deferred:
        if not isinstance(item, dict):
            fail("deferred_root_groups entries must be objects")
        target = require_text(item, "target_parent", "deferred_root_group")
        if target in covered:
            fail(f"duplicate deferred target_parent: {target}")
        if target not in groups:
            fail(f"deferred target_parent not present in plan: {target}")
        covered.add(target)
        if item.get("status") != "deferred-before-release-readiness":
            fail(f"{target}: status must be deferred-before-release-readiness")
        for key in [
            "risk_level",
            "deferral_reason",
            "revisit_trigger",
            "future_gate",
            "package_safety",
            "archaeology_rule",
            "closeout_rule",
        ]:
            require_text(item, key, target)
        plan_group = groups[target]
        if "current_roots" in plan_group:
            if string_list(item.get("current_roots"), f"{target}.current_roots") != string_list(plan_group.get("current_roots"), f"plan.{target}.current_roots"):
                fail(f"{target}: current_roots must match plan")
        if "future_shape" in plan_group:
            if string_list(item.get("future_shape"), f"{target}.future_shape") != string_list(plan_group.get("future_shape"), f"plan.{target}.future_shape"):
                fail(f"{target}: future_shape must match plan")
    missing = sorted(required - covered)
    if missing:
        fail("missing deferred root groups: " + ", ".join(missing))
    return covered


def validate_future_gate(receipt: dict[str, Any]) -> None:
    gate = receipt.get("global_future_apply_gate")
    if not isinstance(gate, dict):
        fail("global_future_apply_gate must be an object")
    revisit = "\n".join(string_list(gate.get("revisit_before"), "global_future_apply_gate.revisit_before"))
    if "formal-public-npm-release" not in revisit:
        fail("global future gate must revisit before formal public npm release")
    required = "\n".join(string_list(gate.get("required_before_any_future_move"), "global_future_apply_gate.required_before_any_future_move"))
    for phrase in [
        "separate .dev-task.md apply tranche",
        "dry-run migration manifest",
        "exact consumer matrix",
        "alias and rollback plan",
        "package-safety proof",
        "clean workspace E2E",
        "Prism review",
        "closeout receipt",
    ]:
        if phrase not in required:
            fail(f"global future gate missing phrase: {phrase}")


def validate_backlog(backlog: dict[str, Any]) -> None:
    rows = [item for item in backlog.get("requirements", []) if isinstance(item, dict) and item.get("id") == "RASG-022"]
    if len(rows) != 1:
        fail("backlog must contain exactly one RASG-022 entry")
    item = rows[0]
    if item.get("status") != "done":
        fail("RASG-022 backlog status must be done after explicit deferral receipt")
    evidence = string_list(item.get("evidence"), "RASG-022 evidence")
    for required in [
        "references/root-information-architecture-consolidation-plan.json",
        "references/root-ia-shared-knowledge-tranche-manifest.json",
        "references/root-ia-remaining-root-groups-deferral.json",
        "compass/docs/task-reports/2026-05-14-rasg-022-remaining-root-groups-deferral.md",
    ]:
        if required not in evidence:
            fail(f"RASG-022 evidence missing: {required}")
    tranches = item.get("applied_tranches")
    if not isinstance(tranches, list) or not tranches:
        fail("RASG-022 applied_tranches must be a non-empty list")
    shared = next((row for row in tranches if isinstance(row, dict) and row.get("id") == "rasg-022-shared-knowledge-template-tranche"), None)
    if not isinstance(shared, dict):
        fail("RASG-022 missing shared-knowledge applied tranche entry")
    if shared.get("status") != "completed-closeout-receipted":
        fail("RASG-022 shared-knowledge applied tranche must be completed-closeout-receipted")
    deferrals = item.get("explicit_deferrals")
    if not isinstance(deferrals, list) or not deferrals:
        fail("RASG-022 explicit_deferrals must be non-empty")
    if not any(isinstance(row, dict) and row.get("receipt") == "references/root-ia-remaining-root-groups-deferral.json" for row in deferrals):
        fail("RASG-022 explicit_deferrals missing remaining-root receipt")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RASG-022 remaining root group deferral receipt.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--backlog", default=str(DEFAULT_BACKLOG))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    receipt_path = Path(args.receipt)
    plan_path = Path(args.plan)
    backlog_path = Path(args.backlog)
    if not receipt_path.is_absolute():
        receipt_path = root / receipt_path
    if not plan_path.is_absolute():
        plan_path = root / plan_path
    if not backlog_path.is_absolute():
        backlog_path = root / backlog_path

    receipt = load_json(receipt_path, "deferral receipt")
    plan = load_json(plan_path, "root information architecture plan")
    backlog = load_json(backlog_path, "architecture smell backlog")

    if receipt.get("version") != 1:
        fail("receipt version must be 1")
    if receipt.get("receipt_id") != "rasg-022-remaining-root-groups-deferral":
        fail("receipt_id mismatch")
    if receipt.get("requirement") != "RASG-022":
        fail("receipt must bind to RASG-022")
    if receipt.get("source_plan") != "references/root-information-architecture-consolidation-plan.json":
        fail("receipt source_plan mismatch")
    if receipt.get("physical_migration_mode") not in {
        "no-further-move-in-this-task",
        "per-tranche-apply-private-archive-complete-remaining-groups-deferred",
    }:
        fail("receipt physical_migration_mode mismatch")
    if receipt.get("status") != "partial-apply-complete-remaining-root-groups-deferred-before-release":
        fail("receipt status mismatch")

    groups = target_groups(plan)
    validate_claim_boundary(receipt)
    covered = set()
    covered |= validate_applied(receipt)
    covered |= validate_keep_at_root(receipt)
    covered |= validate_deferred(receipt, groups)
    validate_future_gate(receipt)
    validate_backlog(backlog)

    missing_coverage = sorted(set(groups) - covered)
    if missing_coverage:
        fail("target parent groups not covered by apply/keep/defer receipt: " + ", ".join(missing_coverage))

    print("ROOT_IA_DEFERRAL_OK")
    print(f"applied={len(receipt.get('applied_parent_groups', []))}")
    print(f"kept={len(receipt.get('keep_at_root_boundaries', []))}")
    print(f"deferred={len(receipt.get('deferred_root_groups', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

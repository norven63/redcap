#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "references/execution-layer-split-dry-run.json"

ALLOWED_OPERATIONS = {
    "copy-then-link",
    "copy-with-root-shim",
    "copy-with-root-import-pointer",
    "copy-tree-then-rewire",
    "copy-selected-policies",
    "defer-to-p1-2",
}
ALLOWED_RISKS = {"low", "medium", "high"}
ALLOWED_APPLY_STATUS = {
    "blocked_for_apply_until_adapter_exists",
    "blocked_for_apply_until_import_map_exists",
    "blocked_for_apply_until_prism_paths_are_abstracted",
    "blocked_for_apply_until_policy_ownership_split",
    "blocked_for_apply_until_host_import_contract_review",
    "deferred_to_legacy_asset_migration",
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-execution-layer-split-check] {message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid json {path}: {exc}")
    if not isinstance(payload, dict):
        fail("manifest must be a JSON object")
    return payload


def require_text(item: dict[str, Any], key: str, item_id: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{item_id}: missing non-empty {key}")
    return value.strip()


def require_text_list(item: dict[str, Any], key: str, item_id: str) -> list[str]:
    value = item.get(key)
    if not isinstance(value, list) or not value:
        fail(f"{item_id}: {key} must be a non-empty list")
    rows: list[str] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, str) or not entry.strip():
            fail(f"{item_id}: {key}[{index}] must be a non-empty string")
        rows.append(entry.strip())
    return rows


def require_safe_relative(raw: str, item_id: str, key: str) -> str:
    if raw.startswith("/") or ".." in Path(raw).parts:
        fail(f"{item_id}: {key} must be a safe repo-relative path: {raw}")
    return raw


def require_existing_source(root: Path, raw: str, item_id: str) -> None:
    rel = require_safe_relative(raw, item_id, "source")
    if not (root / rel).exists():
        fail(f"{item_id}: source path missing: {rel}")


def require_target_absent(root: Path, raw: str, item_id: str) -> None:
    rel = require_safe_relative(raw, item_id, "target")
    if (root / rel).exists():
        fail(f"{item_id}: target path must not already exist during dry-run: {rel}")


def check_manifest(path: Path, root: Path) -> None:
    payload = load_json(path)
    if payload.get("version") != 1:
        fail("version must be 1")
    if payload.get("manifest_id") != "redcap-execution-layer-split-dry-run":
        fail("manifest_id must be redcap-execution-layer-split-dry-run")
    if payload.get("status") != "dry-run-only":
        fail("status must be dry-run-only")
    if payload.get("created_for_task") != "redcap-execution-layer-split-dry-run":
        fail("created_for_task must match the Layer B task id")
    if payload.get("apply_allowed") is not False:
        fail("apply_allowed must be false for this dry-run manifest")

    apply_policy = payload.get("apply_policy")
    if not isinstance(apply_policy, dict):
        fail("apply_policy must be an object")
    require_text(apply_policy, "rule", "apply_policy")
    requires = require_text_list(apply_policy, "requires_before_apply", "apply_policy")
    if len(requires) < 3:
        fail("apply_policy.requires_before_apply must include at least three gates")

    target_layers = payload.get("target_layers")
    if not isinstance(target_layers, list) or not target_layers:
        fail("target_layers must be a non-empty list")
    layer_ids: set[str] = set()
    for layer in target_layers:
        if not isinstance(layer, dict):
            fail("target_layers entries must be objects")
        layer_id = require_text(layer, "id", "target_layer")
        if layer_id in layer_ids:
            fail(f"duplicate target layer id: {layer_id}")
        layer_ids.add(layer_id)
        require_safe_relative(require_text(layer, "proposed_root", layer_id), layer_id, "proposed_root")
        require_text(layer, "purpose", layer_id)

    plans = payload.get("plans")
    if not isinstance(plans, list) or not plans:
        fail("plans must be a non-empty list")
    plan_ids: set[str] = set()
    high_risk_count = 0
    deferred_count = 0
    for plan in plans:
        if not isinstance(plan, dict):
            fail("plans entries must be objects")
        plan_id = require_text(plan, "id", "plan")
        if not re.fullmatch(r"SPLIT-[0-9]{3}", plan_id):
            fail(f"invalid plan id: {plan_id}")
        if plan_id in plan_ids:
            fail(f"duplicate plan id: {plan_id}")
        plan_ids.add(plan_id)

        require_existing_source(root, require_text(plan, "source", plan_id), plan_id)
        operation = require_text(plan, "operation", plan_id)
        if operation not in ALLOWED_OPERATIONS:
            fail(f"{plan_id}: unsupported operation: {operation}")
        if operation != "defer-to-p1-2":
            require_target_absent(root, require_text(plan, "target", plan_id), plan_id)
        else:
            require_safe_relative(require_text(plan, "target", plan_id), plan_id, "target")
        target_layer = require_text(plan, "target_layer", plan_id)
        if target_layer not in layer_ids:
            fail(f"{plan_id}: target_layer not declared: {target_layer}")
        risk = require_text(plan, "risk", plan_id)
        if risk not in ALLOWED_RISKS:
            fail(f"{plan_id}: unsupported risk: {risk}")
        if risk == "high":
            high_risk_count += 1
        apply_status = require_text(plan, "apply_status", plan_id)
        if apply_status not in ALLOWED_APPLY_STATUS:
            fail(f"{plan_id}: unsupported apply_status: {apply_status}")
        if apply_status == "deferred_to_legacy_asset_migration":
            deferred_count += 1
        if risk == "high" and not apply_status.startswith(("blocked_", "deferred_")):
            fail(f"{plan_id}: high-risk plans must be blocked or deferred")
        require_text(plan, "reason", plan_id)
        require_text_list(plan, "import_impact", plan_id)
        require_text_list(plan, "hook_impact", plan_id)
        require_text_list(plan, "rollback_plan", plan_id)

    if high_risk_count == 0:
        fail("manifest must expose at least one high-risk migration boundary")
    if deferred_count == 0:
        fail("manifest must explicitly defer legacy asset migration to P1-2")

    global_impact = payload.get("global_impact")
    if not isinstance(global_impact, dict):
        fail("global_impact must be an object")
    for key in ["import_paths", "host_hooks", "docs_catalog", "rollback", "cross_plan_dependencies"]:
        require_text(global_impact, key, "global_impact")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap execution-layer split dry-run manifest.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    manifest = Path(args.manifest)
    if not manifest.is_absolute():
        manifest = (Path.cwd() / manifest).resolve()
    if not manifest.is_file():
        fail(f"missing manifest: {manifest}")
    check_manifest(manifest, root)
    print(f"EXECUTION_LAYER_SPLIT_DRY_RUN_OK {manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

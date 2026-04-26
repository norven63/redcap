#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "references/legacy-asset-migration-dry-run.json"

ALLOWED_ACTIONS = {
    "preserve",
    "archive-in-place",
    "copy-to-knowledge-then-index",
    "translate-after-index-split",
    "prune-when-safe",
    "ignore-runtime",
}
ALLOWED_RISKS = {"low", "medium", "high"}
ALLOWED_APPLY_STATUS = {
    "blocked_until_catalog_and_receipt_linkmap_exists",
    "blocked_until_catalog_linkmap_exists",
    "preserve_active_index",
    "preserve_until_spec_registry_migration_exists",
    "blocked_until_trace_consumers_are_checked",
    "no_move_required",
    "blocked_until_hot_cold_knowledge_split_exists",
    "retention_check_only",
    "ignore_runtime_state",
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-legacy-asset-migration-check] {message}")


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


def count_files(root: Path, rel: str) -> int:
    path = root / rel
    if path.is_file():
        return 1
    return sum(1 for item in path.rglob("*") if item.is_file())


def count_lines(root: Path, rel: str) -> int:
    path = root / rel
    files = [path] if path.is_file() else [item for item in path.rglob("*") if item.is_file()]
    total = 0
    for item in files:
        try:
            total += len(item.read_text(encoding="utf-8", errors="ignore").splitlines())
        except OSError:
            continue
    return total


def run_prism_summary(root: Path) -> dict[str, int]:
    completed = subprocess.run(
        ["bash", "prism/tools/prism-runs-lifecycle.sh", "summary"],
        cwd=str(root),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        fail("prism-runs lifecycle summary failed: " + (completed.stdout + completed.stderr).strip())
    values: dict[str, int] = {}
    for raw in completed.stdout.splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        try:
            values[key.strip()] = int(value.strip().split()[0])
        except ValueError:
            continue
    return values


def check_manifest(path: Path, root: Path) -> None:
    payload = load_json(path)
    if payload.get("version") != 1:
        fail("version must be 1")
    if payload.get("manifest_id") != "redcap-legacy-asset-migration-dry-run":
        fail("manifest_id must be redcap-legacy-asset-migration-dry-run")
    if payload.get("status") != "dry-run-only":
        fail("status must be dry-run-only")
    if payload.get("created_for_task") != "redcap-legacy-asset-migration-dry-run":
        fail("created_for_task must match the Layer B task id")
    if payload.get("apply_allowed") is not False:
        fail("apply_allowed must be false for this dry-run manifest")

    apply_policy = payload.get("apply_policy")
    if not isinstance(apply_policy, dict):
        fail("apply_policy must be an object")
    require_text(apply_policy, "rule", "apply_policy")
    if len(require_text_list(apply_policy, "requires_before_apply", "apply_policy")) < 4:
        fail("apply_policy.requires_before_apply must include at least four gates")

    collections = payload.get("collections")
    if not isinstance(collections, list) or not collections:
        fail("collections must be a non-empty list")

    required_ids = {
        "task-reports",
        "docs-catalog",
        "research",
        "specs",
        "traces",
        "docs-archive",
        "knowledge-lessons",
        "runtime-working-dirs",
        "prism-runs",
    }
    seen: set[str] = set()
    action_classes: set[str] = set()
    high_risk = 0
    move_candidates = 0
    for collection in collections:
        if not isinstance(collection, dict):
            fail("collections entries must be objects")
        cid = require_text(collection, "id", "collection")
        if cid in seen:
            fail(f"duplicate collection id: {cid}")
        seen.add(cid)

        source = require_safe_relative(require_text(collection, "source", cid), cid, "source")
        source_path = root / source
        if not source_path.exists():
            fail(f"{cid}: source path missing: {source}")
        require_safe_relative(require_text(collection, "target", cid), cid, "target")
        require_text(collection, "kind", cid)

        action = require_text(collection, "default_action", cid)
        if action not in ALLOWED_ACTIONS:
            fail(f"{cid}: unsupported default_action: {action}")
        if action == "preserve":
            action_classes.add("retain")
        elif action == "archive-in-place":
            action_classes.add("archive")
        elif action in {"copy-to-knowledge-then-index", "translate-after-index-split"}:
            action_classes.add("move")
        elif action == "prune-when-safe":
            action_classes.add("prune")
        elif action == "ignore-runtime":
            action_classes.add("ignore")
        if action in {"copy-to-knowledge-then-index", "translate-after-index-split"}:
            move_candidates += 1

        risk = require_text(collection, "risk", cid)
        if risk not in ALLOWED_RISKS:
            fail(f"{cid}: unsupported risk: {risk}")
        if risk == "high":
            high_risk += 1

        apply_status = require_text(collection, "apply_status", cid)
        if apply_status not in ALLOWED_APPLY_STATUS:
            fail(f"{cid}: unsupported apply_status: {apply_status}")
        if risk == "high" and not apply_status.startswith(("blocked_", "preserve_")):
            fail(f"{cid}: high-risk collections must be blocked or preserved")

        expected_count = collection.get("current_count")
        if not isinstance(expected_count, int) or expected_count < 0:
            fail(f"{cid}: current_count must be a non-negative integer")
        actual_count = run_prism_summary(root).get("total", -1) if cid == "prism-runs" else count_files(root, source)
        if actual_count != expected_count:
            fail(f"{cid}: current_count mismatch expected={expected_count} actual={actual_count}")

        expected_lines = collection.get("current_lines")
        if not isinstance(expected_lines, int) or expected_lines < 0:
            fail(f"{cid}: current_lines must be a non-negative integer")
        if expected_lines > 0:
            actual_lines = count_lines(root, source)
            if actual_lines != expected_lines:
                fail(f"{cid}: current_lines mismatch expected={expected_lines} actual={actual_lines}")

        require_text(collection, "reason", cid)
        require_text_list(collection, "catalog_update_plan", cid)
        require_text_list(collection, "link_check_plan", cid)
        require_text_list(collection, "rollback_plan", cid)

    missing = sorted(required_ids - seen)
    if missing:
        fail("missing required collections: " + ", ".join(missing))
    if high_risk == 0:
        fail("manifest must expose high-risk historical asset boundaries")
    if move_candidates == 0:
        fail("manifest must include at least one migration candidate")
    missing_action_classes = sorted({"retain", "archive", "move", "prune", "ignore"} - action_classes)
    if missing_action_classes:
        fail("manifest missing required action classes: " + ", ".join(missing_action_classes))

    prism = run_prism_summary(root)
    prism_item = next((item for item in collections if item.get("id") == "prism-runs"), None)
    if prism_item and prism.get("total") != prism_item.get("current_count"):
        fail(f"prism-runs: current_count mismatch expected={prism_item.get('current_count')} actual={prism.get('total')}")
    if prism.get("purgeable_acceptance", 0) != 0:
        fail("prism-runs has purgeable acceptance residue; cleanup must be separate from docs migration")

    controls = payload.get("global_controls")
    if not isinstance(controls, dict):
        fail("global_controls must be an object")
    for key in ["catalog_update_required", "link_check_required", "receipt_anchor_preservation_required"]:
        if controls.get(key) is not True:
            fail(f"global_controls.{key} must be true")
    if controls.get("apply_allowed") is not False:
        fail("global_controls.apply_allowed must be false")
    require_text(controls, "apply_boundary", "global_controls")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap legacy asset migration dry-run manifest.")
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
    print(f"LEGACY_ASSET_MIGRATION_DRY_RUN_OK {manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

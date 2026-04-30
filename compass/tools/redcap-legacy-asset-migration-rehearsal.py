#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "references/legacy-asset-migration-apply-plan.json"
DEFAULT_RESULT = ROOT / "references/legacy-asset-migration-apply-rehearsal.json"

SOURCE_MANIFEST_ID = "redcap-legacy-asset-migration-apply-preflight"
REHEARSAL_ID = "redcap-legacy-asset-migration-apply-rehearsal"
TASK_ID = "historical-asset-migration-apply-rehearsal"

FORBIDDEN_OPERATIONS = {"delete", "move", "move-then-delete", "prune", "public-export"}
PUBLIC_TARGET_PREFIXES = {"redcap-arsenal", "shared-knowledge"}
COPY_FIRST_GUARDS = {
    "catalog-alias-required-before-apply",
    "local-link-check-required-before-apply",
    "receipt-anchor-preserve-old-path",
    "copy-first-delete-last",
    "rollback-delete-copy-only",
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-legacy-asset-migration-rehearsal] {message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid json {path}: {exc}")
    if not isinstance(payload, dict):
        fail("manifest must be a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require_text(item: dict[str, Any], key: str, ctx: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{ctx}: missing non-empty {key}")
    return value.strip()


def require_text_list(item: dict[str, Any], key: str, ctx: str) -> list[str]:
    value = item.get(key)
    if not isinstance(value, list) or not value:
        fail(f"{ctx}: {key} must be a non-empty list")
    rows: list[str] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, str) or not entry.strip():
            fail(f"{ctx}: {key}[{index}] must be a non-empty string")
        rows.append(entry.strip())
    return rows


def safe_relative(raw: str, ctx: str, key: str) -> str:
    path = Path(raw)
    if raw.startswith("/") or raw.startswith("~") or ".." in path.parts:
        fail(f"{ctx}: {key} must be a safe repo-relative path: {raw}")
    if not path.parts:
        fail(f"{ctx}: {key} must not be empty")
    return raw


def assert_within_root(root: Path, rel: str, ctx: str, key: str) -> None:
    root_resolved = root.resolve()
    candidate = (root / rel).resolve(strict=False)
    if not candidate.is_relative_to(root_resolved):
        fail(f"{ctx}: {key} resolves outside repo root: {rel}")


def is_public_target(raw: str) -> bool:
    parts = Path(raw).parts
    return bool(parts and parts[0] in PUBLIC_TARGET_PREFIXES)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_hash(path: Path) -> str:
    return sha256_file(path)


def git_head(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def validate_manifest_header(payload: dict[str, Any], root: Path) -> None:
    if payload.get("manifest_id") != SOURCE_MANIFEST_ID:
        fail(f"manifest_id must be {SOURCE_MANIFEST_ID}")
    if payload.get("status") != "apply-preflight-only":
        fail("status must be apply-preflight-only")
    if payload.get("apply_allowed") is not False:
        fail("apply_allowed must be false")
    if payload.get("public_export_allowed") is not False:
        fail("public_export_allowed must be false")
    dry_run_rel = safe_relative(require_text(payload, "source_dry_run", "manifest"), "manifest", "source_dry_run")
    if not (root / dry_run_rel).is_file():
        fail(f"source_dry_run missing: {dry_run_rel}")


def prepare_temp_copy(root: Path, sandbox: Path, copy_items: list[dict[str, Any]]) -> None:
    for item in copy_items:
        source = safe_relative(require_text(item, "source", require_text(item, "id", "item")), item["id"], "source")
        source_path = root / source
        sandbox_source = sandbox / source
        if not source_path.is_file():
            fail(f"{item['id']}: source file missing: {source}")
        sandbox_source.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, sandbox_source)


def validate_copy_item(root: Path, item: dict[str, Any], copy_targets: set[str]) -> tuple[str, str, str]:
    item_id = require_text(item, "id", "item")
    source = safe_relative(require_text(item, "source", item_id), item_id, "source")
    target = safe_relative(require_text(item, "target", item_id), item_id, "target")
    assert_within_root(root, source, item_id, "source")
    assert_within_root(root, target, item_id, "target")
    operation = require_text(item, "operation", item_id)
    if operation in FORBIDDEN_OPERATIONS:
        fail(f"{item_id}: forbidden operation: {operation}")
    if operation != "copy-first":
        fail(f"{item_id}: rehearsal only applies copy-first items, got {operation}")
    if is_public_target(target):
        fail(f"{item_id}: target must not point to public/shared repository: {target}")
    if not target.startswith("redcap-knowledge/"):
        fail(f"{item_id}: copy-first target must stay under redcap-knowledge: {target}")
    if target in copy_targets:
        fail(f"{item_id}: duplicate copy target: {target}")
    copy_targets.add(target)
    if (root / target).exists():
        fail(f"{item_id}: main-tree target already exists; rehearsal must not overwrite: {target}")
    if not (root / source).is_file():
        fail(f"{item_id}: source file missing: {source}")
    if item.get("apply_allowed") is not False:
        fail(f"{item_id}: apply_allowed must be false")
    if item.get("public_export_allowed") is not False:
        fail(f"{item_id}: public_export_allowed must be false")
    if item.get("old_path_retained") is not True:
        fail(f"{item_id}: old_path_retained must be true")
    guards = set(require_text_list(item, "guards", item_id))
    missing = sorted(COPY_FIRST_GUARDS - guards)
    if missing:
        fail(f"{item_id}: missing copy-first guard(s): {', '.join(missing)}")
    require_text_list(item, "catalog_update_plan", item_id)
    require_text_list(item, "link_check_plan", item_id)
    require_text_list(item, "rollback_plan", item_id)
    return item_id, source, target


def validate_all_items_safety(root: Path, items: list[Any]) -> None:
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            fail(f"items[{index}] must be an object")
        item_id = require_text(item, "id", f"items[{index}]")
        source = safe_relative(require_text(item, "source", item_id), item_id, "source")
        target = safe_relative(require_text(item, "target", item_id), item_id, "target")
        assert_within_root(root, source, item_id, "source")
        assert_within_root(root, target, item_id, "target")
        operation = require_text(item, "operation", item_id)
        if operation in FORBIDDEN_OPERATIONS:
            fail(f"{item_id}: forbidden operation: {operation}")
        if is_public_target(target):
            fail(f"{item_id}: target must not point to public/shared repository: {target}")
        if not (root / source).is_file():
            fail(f"{item_id}: source file missing: {source}")
        if item.get("apply_allowed") is not False:
            fail(f"{item_id}: apply_allowed must be false")
        if item.get("public_export_allowed") is not False:
            fail(f"{item_id}: public_export_allowed must be false")
        if item.get("old_path_retained") is not True:
            fail(f"{item_id}: old_path_retained must be true")


def run_rehearsal(root: Path, manifest_path: Path) -> dict[str, Any]:
    payload = load_json(manifest_path)
    validate_manifest_header(payload, root)
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        fail("items must be a non-empty list")
    validate_all_items_safety(root, items)
    copy_items = [item for item in items if isinstance(item, dict) and item.get("operation") == "copy-first"]
    if not copy_items:
        fail("copy-first items must be present for rehearsal")

    copy_targets: set[str] = set()
    normalized_items = [validate_copy_item(root, item, copy_targets) for item in copy_items]
    alias_map: list[dict[str, Any]] = []
    rollback_plan: list[dict[str, str]] = []

    with tempfile.TemporaryDirectory(prefix="redcap-legacy-asset-rehearsal.") as tmp:
        sandbox = Path(tmp) / "sandbox"
        sandbox.mkdir(parents=True)
        prepare_temp_copy(root, sandbox, copy_items)

        for item_id, source, target in normalized_items:
            sandbox_source = sandbox / source
            sandbox_target = sandbox / target
            if sandbox_target.exists():
                fail(f"{item_id}: sandbox target already exists before copy: {target}")
            sandbox_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sandbox_source, sandbox_target)

            source_hash = sha256_file(root / source)
            sandbox_hash = sha256_file(sandbox_target)
            if source_hash != sandbox_hash:
                fail(f"{item_id}: copied file hash mismatch: {source} -> {target}")
            if not (root / source).is_file():
                fail(f"{item_id}: main-tree source disappeared during rehearsal: {source}")
            if (root / target).exists():
                fail(f"{item_id}: main-tree target appeared during rehearsal: {target}")

            alias_map.append(
                {
                    "item_id": item_id,
                    "old_path": source,
                    "new_path": target,
                    "source_sha256": source_hash,
                    "target_sha256": sandbox_hash,
                    "old_path_retained": True,
                    "catalog_alias_required": True,
                    "receipt_anchor_preserved": source.startswith("compass/docs/task-reports/"),
                }
            )
            rollback_plan.append({"action": "delete-copy-target", "path": target})

        for step in rollback_plan:
            path = safe_relative(step["path"], "rollback", "path")
            sandbox_target = sandbox / path
            if not sandbox_target.is_file():
                fail(f"rollback target missing before rehearsal cleanup: {path}")
            sandbox_target.unlink()
            if sandbox_target.exists():
                fail(f"rollback target still exists after cleanup: {path}")

        for _item_id, source, _target in normalized_items:
            if not (sandbox / source).is_file():
                fail(f"rollback cleanup removed source in sandbox: {source}")
            if not (root / source).is_file():
                fail(f"rollback cleanup removed source in main tree: {source}")

    task_report_aliases = [row for row in alias_map if row["old_path"].startswith("compass/docs/task-reports/")]
    return {
        "version": 1,
        "manifest_id": REHEARSAL_ID,
        "created_for_task": TASK_ID,
        "source_manifest": manifest_path.relative_to(root).as_posix() if manifest_path.is_relative_to(root) else str(manifest_path),
        "source_manifest_sha256": manifest_hash(manifest_path),
        "source_git_head": git_head(root),
        "apply_allowed": False,
        "main_tree_mutated": False,
        "public_export_allowed": False,
        "rehearsal_mode": "temp-copy",
        "summary": {
            "total_manifest_items": len(items),
            "copy_first_items": len(copy_items),
            "alias_map_entries": len(alias_map),
            "rollback_entries": len(rollback_plan),
            "task_report_anchor_entries": len(task_report_aliases),
            "non_copy_items_skipped": len(items) - len(copy_items),
        },
        "safety_checks": {
            "source_paths_retained": True,
            "targets_created_only_in_rehearsal_sandbox": True,
            "target_hash_matches_source": True,
            "rollback_deletes_copy_targets_only": True,
            "public_targets_blocked": True,
            "main_tree_targets_absent_after_rehearsal": True,
            "receipt_anchor_old_paths_preserved": True,
            "catalog_alias_map_generated": True,
        },
        "alias_map": alias_map,
        "rollback_plan": rollback_plan,
        "follow_up_required": [
            "Wire the alias map into the docs catalog/link resolver before any main-tree delete-last phase.",
            "Run the same rehearsal in a real throwaway worktree immediately before main-tree apply.",
            "Keep raw historical reports out of public redcap-arsenal unless a separate redaction and dedupe review approves curated entries.",
        ],
    }


def validate_result(result: dict[str, Any], expected: dict[str, Any] | None = None) -> None:
    if result.get("manifest_id") != REHEARSAL_ID:
        fail(f"result manifest_id must be {REHEARSAL_ID}")
    if result.get("created_for_task") != TASK_ID:
        fail(f"created_for_task must be {TASK_ID}")
    if result.get("apply_allowed") is not False:
        fail("result apply_allowed must be false")
    if result.get("main_tree_mutated") is not False:
        fail("result main_tree_mutated must be false")
    if result.get("public_export_allowed") is not False:
        fail("result public_export_allowed must be false")
    summary = result.get("summary")
    if not isinstance(summary, dict):
        fail("result summary must be an object")
    for key in ("copy_first_items", "alias_map_entries", "rollback_entries"):
        if not isinstance(summary.get(key), int) or summary[key] <= 0:
            fail(f"summary.{key} must be a positive integer")
    if summary["copy_first_items"] != summary["alias_map_entries"]:
        fail("summary.alias_map_entries must equal copy_first_items")
    if summary["copy_first_items"] != summary["rollback_entries"]:
        fail("summary.rollback_entries must equal copy_first_items")
    safety = result.get("safety_checks")
    if not isinstance(safety, dict):
        fail("safety_checks must be an object")
    for key, value in safety.items():
        if value is not True:
            fail(f"safety_checks.{key} must be true")
    if expected is not None:
        for key in ("source_manifest_sha256", "summary", "safety_checks", "alias_map", "rollback_plan"):
            if result.get(key) != expected.get(key):
                fail(f"result file stale or inconsistent: {key} does not match live rehearsal")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a throwaway rehearsal for RedCap historical asset copy-first migration.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--result", default=str(DEFAULT_RESULT))
    parser.add_argument("--write-result", action="store_true", help="Write the compact rehearsal receipt to --result.")
    parser.add_argument("--check-result", action="store_true", help="Validate --result after running rehearsal.")
    parser.add_argument("--check-stored-result-only", action="store_true", help="Validate the stored rehearsal receipt without re-running live rehearsal.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    manifest = Path(args.manifest)
    result_path = Path(args.result)
    if not manifest.is_absolute():
        manifest = (Path.cwd() / manifest).resolve()
    if not result_path.is_absolute():
        result_path = (Path.cwd() / result_path).resolve()
    if not manifest.is_file():
        fail(f"missing manifest: {manifest}")
    if args.check_stored_result_only:
        if not result_path.is_file():
            fail(f"missing result file: {result_path}")
        result = load_json(result_path)
        validate_result(result)
        print(
            "LEGACY_ASSET_MIGRATION_REHEARSAL_STORED_OK "
            f"{result_path} copy_first={result['summary']['copy_first_items']} "
            f"alias_map={result['summary']['alias_map_entries']} "
            f"rollback={result['summary']['rollback_entries']}"
        )
        return 0

    result = run_rehearsal(root, manifest)
    validate_result(result)
    if args.write_result:
        write_json(result_path, result)
    if args.check_result:
        if not result_path.is_file():
            fail(f"missing result file: {result_path}")
        validate_result(load_json(result_path), expected=result)
    print(
        "LEGACY_ASSET_MIGRATION_REHEARSAL_OK "
        f"{manifest} copy_first={result['summary']['copy_first_items']} "
        f"alias_map={result['summary']['alias_map_entries']} "
        f"rollback={result['summary']['rollback_entries']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

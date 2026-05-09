#!/usr/bin/env python3
# 用途：控制面保障脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#control-plane-assurance

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DRY_RUN = ROOT / "references/legacy-asset-migration-dry-run.json"
DEFAULT_MANIFEST = ROOT / "references/legacy-asset-migration-apply-plan.json"

MANIFEST_ID = "redcap-legacy-asset-migration-apply-preflight"
TASK_ID = "historical-asset-migration-apply-preflight"

ALLOWED_OPERATIONS = {
    "copy-first",
    "preserve",
    "archive-in-place",
    "blocked-translate",
    "retention-check-only",
    "ignore-runtime",
}
FORBIDDEN_OPERATIONS = {
    "delete",
    "move",
    "move-then-delete",
    "prune",
    "public-export",
}
PUBLIC_TARGET_PREFIXES = {
    "redcap-arsenal",
    "shared-knowledge",
}
RISK_CONTROLS = {
    "no_delete_or_move",
    "old_paths_remain_authoritative",
    "public_export_blocked",
    "copy_first_delete_last",
    "actual_apply_requires_throwaway_worktree",
}
RUNTIME_SUMMARY_ONLY = {"runtime-working-dirs", "prism-runs"}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-legacy-asset-migration-apply-plan] {message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid json {path}: {exc}")
    if not isinstance(payload, dict):
        fail("manifest must be a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
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
    if raw.startswith("/") or raw.startswith("~") or ".." in Path(raw).parts:
        fail(f"{ctx}: {key} must be a safe repo-relative path: {raw}")
    return raw


def is_public_target(raw: str) -> bool:
    parts = Path(raw).parts
    return bool(parts and parts[0] in PUBLIC_TARGET_PREFIXES)


def is_acceptance_tmp_file(root: Path, item: Path) -> bool:
    if os.environ.get("REDCAP_ACCEPTANCE_RUNNING") != "1":
        return False
    try:
        rel = item.resolve().relative_to((root / "compass/docs/task-reports").resolve())
    except ValueError:
        return False
    return rel.name.startswith(("zz-acceptance-", "zz-review-"))


def active_task_report_path(root: Path) -> Path | None:
    task_file = root / ".dev-task.md"
    if not task_file.is_file():
        return None
    for line in task_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("task_report:"):
            continue
        raw = line.split(":", 1)[1].strip()
        if not raw or raw.startswith("/") or ".." in Path(raw).parts:
            return None
        path = root / raw
        if raw.startswith("compass/docs/task-reports/"):
            return path.resolve(strict=False)
    return None


def is_active_task_report_file(root: Path, item: Path) -> bool:
    active = active_task_report_path(root)
    if active is None:
        return False
    return item.resolve(strict=False) == active


def is_non_legacy_active_store_file(root: Path, item: Path) -> bool:
    try:
        rel = item.resolve(strict=False).relative_to(root.resolve()).as_posix()
    except ValueError:
        return False
    return rel.startswith("compass/knowledge/llm-wiki/")


def iter_files(root: Path, source: str) -> list[Path]:
    path = root / source
    if path.is_file():
        return [] if is_acceptance_tmp_file(root, path) or is_active_task_report_file(root, path) or is_non_legacy_active_store_file(root, path) else [path]
    if not path.exists():
        fail(f"source path missing: {source}")
    return sorted(
        (
            item
            for item in path.rglob("*")
            if item.is_file()
            and not is_acceptance_tmp_file(root, item)
            and not is_active_task_report_file(root, item)
            and not is_non_legacy_active_store_file(root, item)
        ),
        key=lambda item: item.relative_to(root).as_posix(),
    )


def count_files(root: Path, source: str) -> int:
    return len(iter_files(root, source))


def migrated_collection_paths(root: Path, source: str) -> list[str]:
    result_path = root / "references/legacy-asset-migration-main-tree-apply.json"
    if not result_path.is_file():
        return []
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if payload.get("manifest_id") != "redcap-legacy-asset-main-tree-copy-apply":
        return []
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return []
    prefix = source.rstrip("/") + "/"
    paths: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        old_path = entry.get("old_path")
        if isinstance(old_path, str) and (old_path == source or old_path.startswith(prefix)):
            paths.append(old_path)
    return sorted(paths)


def delete_last_path_map(root: Path) -> dict[str, str]:
    result_path = root / "references/legacy-asset-delete-last-apply.json"
    if not result_path.is_file():
        return {}
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if payload.get("manifest_id") != "redcap-legacy-asset-delete-last-apply" or payload.get("delete_last_applied") is not True:
        return {}
    mapping: dict[str, str] = {}
    for entry in payload.get("entries", []):
        if not isinstance(entry, dict):
            continue
        old_path = entry.get("old_path")
        new_path = entry.get("new_path")
        if isinstance(old_path, str) and isinstance(new_path, str):
            mapping[old_path] = new_path
    return mapping


def snapshot_file_exists(root: Path, rel: str, delete_map: dict[str, str]) -> bool:
    if (root / rel).is_file():
        return True
    new_rel = delete_map.get(rel)
    return bool(new_rel and (root / new_rel).is_file())


def snapshot_source_path(root: Path, rel: str, delete_map: dict[str, str]) -> Path | None:
    source = root / rel
    if source.is_file():
        return source
    new_rel = delete_map.get(rel)
    if new_rel:
        target = root / new_rel
        if target.is_file():
            return target
    return None


def migrated_collection_count(root: Path, source: str) -> int | None:
    paths = migrated_collection_paths(root, source)
    if not paths:
        return None
    delete_map = delete_last_path_map(root)
    return sum(1 for rel in paths if snapshot_file_exists(root, rel, delete_map))


def migrated_collection_known(root: Path, source: str) -> bool:
    return bool(migrated_collection_paths(root, source))


def iter_source_entries(root: Path, source: str) -> list[tuple[str, Path]]:
    snapshot_paths = migrated_collection_paths(root, source)
    if snapshot_paths:
        delete_map = delete_last_path_map(root)
        entries: list[tuple[str, Path]] = []
        for rel in snapshot_paths:
            path = snapshot_source_path(root, rel, delete_map)
            if path is not None:
                entries.append((rel, path))
        return entries
    return [(path.relative_to(root).as_posix(), path) for path in iter_files(root, source)]


def map_operation(default_action: str) -> str:
    if default_action == "copy-to-knowledge-then-index":
        return "copy-first"
    if default_action == "translate-after-index-split":
        return "blocked-translate"
    if default_action == "preserve":
        return "preserve"
    if default_action == "archive-in-place":
        return "archive-in-place"
    if default_action == "prune-when-safe":
        return "retention-check-only"
    if default_action == "ignore-runtime":
        return "ignore-runtime"
    fail(f"unsupported dry-run action: {default_action}")


def map_target(root: Path, collection: dict[str, Any], source_file: Path, operation: str) -> str:
    source = require_text(collection, "source", "collection")
    target = require_text(collection, "target", collection.get("id", "collection"))
    source_rel = source_file.relative_to(root).as_posix()
    if operation in {"preserve", "archive-in-place", "retention-check-only", "ignore-runtime"}:
        return source_rel
    source_path = root / source
    if source_path.is_file():
        return safe_relative(target, collection["id"], "target")
    leaf = source_file.relative_to(source_path).as_posix()
    return safe_relative((Path(target) / leaf).as_posix(), collection["id"], "target")


def map_target_rel(root: Path, collection: dict[str, Any], source_rel: str, operation: str) -> str:
    source = require_text(collection, "source", "collection")
    target = require_text(collection, "target", collection.get("id", "collection"))
    if operation in {"preserve", "archive-in-place", "retention-check-only", "ignore-runtime"}:
        return source_rel
    source_path = root / source
    if source_path.is_file():
        return safe_relative(target, collection["id"], "target")
    prefix = source.rstrip("/") + "/"
    if not source_rel.startswith(prefix):
        fail(f"{collection['id']}: migrated source path escapes collection: {source_rel}")
    leaf = source_rel[len(prefix) :]
    return safe_relative((Path(target) / leaf).as_posix(), collection["id"], "target")


def guard_set(collection_id: str, operation: str) -> list[str]:
    guards = [
        "apply-allowed-false",
        "source-path-remains-authoritative",
        "no-delete-or-move",
    ]
    if operation == "copy-first":
        guards.extend(
            [
                "catalog-alias-required-before-apply",
                "local-link-check-required-before-apply",
                "receipt-anchor-preserve-old-path",
                "copy-first-delete-last",
                "rollback-delete-copy-only",
            ]
        )
    elif operation == "blocked-translate":
        guards.extend(
            [
                "hot-cold-index-split-required",
                "knowledge-index-preserve-first-read",
                "no-public-export-without-redaction-review",
            ]
        )
    elif operation == "preserve":
        guards.append("no-op-preserve")
    elif operation == "archive-in-place":
        guards.append("archive-in-place-no-path-change")
    elif operation == "retention-check-only":
        guards.append("retention-policy-check-only")
    elif operation == "ignore-runtime":
        guards.append("runtime-state-not-migrated")
    if collection_id == "task-reports" and "receipt-anchor-preserve-old-path" not in guards:
        guards.append("receipt-anchor-preserve-old-path")
    return guards


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def item_scope(collection_id: str) -> str:
    if collection_id in RUNTIME_SUMMARY_ONLY:
        return "collection-summary-only"
    return "file-level"


def generate_manifest(root: Path, dry_run_path: Path) -> dict[str, Any]:
    dry_run = load_json(dry_run_path)
    if dry_run.get("manifest_id") != "redcap-legacy-asset-migration-dry-run":
        fail("source dry-run manifest_id mismatch")

    collections = dry_run.get("collections")
    if not isinstance(collections, list) or not collections:
        fail("source dry-run collections must be a non-empty list")

    manifest_collections: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    sequence = 1
    operations: dict[str, int] = {operation: 0 for operation in ALLOWED_OPERATIONS}

    for collection in collections:
        if not isinstance(collection, dict):
            fail("source dry-run collection entries must be objects")
        cid = require_text(collection, "id", "collection")
        source = safe_relative(require_text(collection, "source", cid), cid, "source")
        operation = map_operation(require_text(collection, "default_action", cid))
        source_entries = [] if cid in RUNTIME_SUMMARY_ONLY else iter_source_entries(root, source)

        manifest_collections.append(
            {
                "id": cid,
                "source": source,
                "target": safe_relative(require_text(collection, "target", cid), cid, "target"),
                "kind": require_text(collection, "kind", cid),
                "risk": require_text(collection, "risk", cid),
                "dry_run_action": require_text(collection, "default_action", cid),
                "operation": operation,
                "apply_status": require_text(collection, "apply_status", cid),
                "item_scope": item_scope(cid),
                "actual_file_count": len(source_entries) if cid not in RUNTIME_SUMMARY_ONLY else count_files(root, source),
                "manifest_item_count": len(source_entries),
                "reason": require_text(collection, "reason", cid),
                "catalog_update_plan": require_text_list(collection, "catalog_update_plan", cid),
                "link_check_plan": require_text_list(collection, "link_check_plan", cid),
                "rollback_plan": require_text_list(collection, "rollback_plan", cid),
            }
        )

        for source_rel, source_file in source_entries:
            target_rel = map_target_rel(root, collection, source_rel, operation)
            item = {
                "id": f"LAM-{sequence:04d}",
                "collection_id": cid,
                "source": source_rel,
                "target": target_rel,
                "operation": operation,
                "risk": require_text(collection, "risk", cid),
                "apply_status": require_text(collection, "apply_status", cid),
                "apply_allowed": False,
                "old_path_retained": True,
                "public_export_allowed": False,
                "guards": guard_set(cid, operation),
                "catalog_update_plan": require_text_list(collection, "catalog_update_plan", cid),
                "link_check_plan": require_text_list(collection, "link_check_plan", cid),
                "rollback_plan": require_text_list(collection, "rollback_plan", cid),
            }
            items.append(item)
            operations[operation] += 1
            sequence += 1

    return {
        "version": 1,
        "manifest_id": MANIFEST_ID,
        "status": "apply-preflight-only",
        "created_for_task": TASK_ID,
        "source_dry_run": dry_run_path.relative_to(root).as_posix(),
        "apply_allowed": False,
        "public_export_allowed": False,
        "target_authority": {
            "proposed_private_root": "redcap-knowledge",
            "public_repository_root": "redcap-arsenal",
            "public_repository_status": "blocked-for-raw-history",
            "reason": "Historical reports, local traces, and runtime evidence may contain private operational context. The public redcap-arsenal repository can receive curated, append-only knowledge entries only after separate redaction and dedupe review.",
        },
        "apply_policy": {
            "rule": "This preflight creates an exact file-level plan only. It is not a migration apply and must not delete, move, or public-export historical assets.",
            "requires_before_apply": [
                "Review this manifest with Prism before any physical migration.",
                "Apply first in a throwaway branch or worktree.",
                "Regenerate docs catalog and link map with old-path aliases before removing any old path.",
                "Verify closeout receipts, task-report anchors, and report checks still resolve after the throwaway apply.",
                "Keep rollback copy-delete commands reviewed before the real apply window.",
            ],
        },
        "risk_controls": {
            "no_delete_or_move": True,
            "old_paths_remain_authoritative": True,
            "public_export_blocked": True,
            "copy_first_delete_last": True,
            "actual_apply_requires_throwaway_worktree": True,
        },
        "collections": manifest_collections,
        "items": items,
        "summary": {
            "total_items": len(items),
            "copy_first_items": operations["copy-first"],
            "blocked_translate_items": operations["blocked-translate"],
            "preserve_items": operations["preserve"],
            "archive_in_place_items": operations["archive-in-place"],
            "retention_check_only_items": operations["retention-check-only"],
            "ignore_runtime_items": operations["ignore-runtime"],
            "runtime_summary_only_collections": len(RUNTIME_SUMMARY_ONLY),
        },
        "follow_up_required": [
            "Decide whether the private knowledge root remains redcap-knowledge or becomes a separate non-public worktree.",
            "Build old-path alias/link map before any delete-last phase.",
            "Run a throwaway-worktree apply rehearsal before touching the main working tree.",
            "Create curated public entries for redcap-arsenal separately; do not bulk-copy raw history.",
        ],
    }


def validate_manifest(path: Path, root: Path) -> dict[str, Any]:
    payload = load_json(path)
    if payload.get("version") != 1:
        fail("version must be 1")
    if payload.get("manifest_id") != MANIFEST_ID:
        fail(f"manifest_id must be {MANIFEST_ID}")
    if payload.get("status") != "apply-preflight-only":
        fail("status must be apply-preflight-only")
    if payload.get("created_for_task") != TASK_ID:
        fail(f"created_for_task must be {TASK_ID}")
    if payload.get("apply_allowed") is not False:
        fail("apply_allowed must be false")
    if payload.get("public_export_allowed") is not False:
        fail("public_export_allowed must be false")

    dry_run_rel = safe_relative(require_text(payload, "source_dry_run", "manifest"), "manifest", "source_dry_run")
    if not (root / dry_run_rel).is_file():
        fail(f"source_dry_run missing: {dry_run_rel}")

    target_authority = payload.get("target_authority")
    if not isinstance(target_authority, dict):
        fail("target_authority must be an object")
    if require_text(target_authority, "public_repository_status", "target_authority") != "blocked-for-raw-history":
        fail("target_authority.public_repository_status must be blocked-for-raw-history")
    if require_text(target_authority, "public_repository_root", "target_authority") != "redcap-arsenal":
        fail("target_authority.public_repository_root must be redcap-arsenal")
    require_text(target_authority, "reason", "target_authority")

    apply_policy = payload.get("apply_policy")
    if not isinstance(apply_policy, dict):
        fail("apply_policy must be an object")
    require_text(apply_policy, "rule", "apply_policy")
    requires = require_text_list(apply_policy, "requires_before_apply", "apply_policy")
    for phrase in ("Prism", "throwaway", "receipt", "rollback"):
        if not any(phrase.lower() in row.lower() for row in requires):
            fail(f"apply_policy.requires_before_apply must mention {phrase}")

    controls = payload.get("risk_controls")
    if not isinstance(controls, dict):
        fail("risk_controls must be an object")
    for key in RISK_CONTROLS:
        if controls.get(key) is not True:
            fail(f"risk_controls.{key} must be true")

    collections = payload.get("collections")
    if not isinstance(collections, list) or not collections:
        fail("collections must be a non-empty list")
    collection_by_id: dict[str, dict[str, Any]] = {}
    for collection in collections:
        if not isinstance(collection, dict):
            fail("collections entries must be objects")
        cid = require_text(collection, "id", "collection")
        if cid in collection_by_id:
            fail(f"duplicate collection id: {cid}")
        source = safe_relative(require_text(collection, "source", cid), cid, "source")
        if not (root / source).exists() and not migrated_collection_known(root, source):
            fail(f"{cid}: source path missing: {source}")
        target = safe_relative(require_text(collection, "target", cid), cid, "target")
        if is_public_target(target):
            fail(f"{cid}: collection target must not point to public/shared repository: {target}")
        operation = require_text(collection, "operation", cid)
        if operation in FORBIDDEN_OPERATIONS:
            fail(f"{cid}: forbidden operation: {operation}")
        if operation not in ALLOWED_OPERATIONS:
            fail(f"{cid}: unsupported operation: {operation}")
        if collection.get("item_scope") not in {"file-level", "collection-summary-only"}:
            fail(f"{cid}: item_scope must be file-level or collection-summary-only")
        expected = migrated_collection_count(root, source)
        if expected is None:
            expected = count_files(root, source)
        if collection.get("item_scope") == "collection-summary-only":
            if not isinstance(collection.get("actual_file_count"), int) or collection.get("actual_file_count") < 0:
                fail(f"{cid}: actual_file_count must be a non-negative snapshot integer")
        elif collection.get("actual_file_count") != expected:
            fail(f"{cid}: actual_file_count mismatch expected={expected} actual={collection.get('actual_file_count')}")
        require_text(collection, "apply_status", cid)
        require_text_list(collection, "catalog_update_plan", cid)
        require_text_list(collection, "link_check_plan", cid)
        require_text_list(collection, "rollback_plan", cid)
        collection_by_id[cid] = collection

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        fail("items must be a non-empty list")
    ids: set[str] = set()
    copy_targets: set[str] = set()
    item_counts: dict[str, int] = {cid: 0 for cid in collection_by_id}
    for item in items:
        if not isinstance(item, dict):
            fail("items entries must be objects")
        item_id = require_text(item, "id", "item")
        if item_id in ids:
            fail(f"duplicate item id: {item_id}")
        ids.add(item_id)
        cid = require_text(item, "collection_id", item_id)
        if cid not in collection_by_id:
            fail(f"{item_id}: unknown collection_id: {cid}")
        item_counts[cid] += 1
        source = safe_relative(require_text(item, "source", item_id), item_id, "source")
        target = safe_relative(require_text(item, "target", item_id), item_id, "target")
        delete_map = delete_last_path_map(root)
        source_snapshot = snapshot_source_path(root, source, delete_map)
        if source_snapshot is None:
            fail(f"{item_id}: source file missing: {source}")
        if is_public_target(target):
            fail(f"{item_id}: target must not point to public/shared repository: {target}")
        operation = require_text(item, "operation", item_id)
        if operation in FORBIDDEN_OPERATIONS:
            fail(f"{item_id}: forbidden operation: {operation}")
        if operation not in ALLOWED_OPERATIONS:
            fail(f"{item_id}: unsupported operation: {operation}")
        if item.get("apply_allowed") is not False:
            fail(f"{item_id}: apply_allowed must be false")
        if item.get("public_export_allowed") is not False:
            fail(f"{item_id}: public_export_allowed must be false")
        if item.get("old_path_retained") is not True:
            fail(f"{item_id}: old_path_retained must be true")
        guards = require_text_list(item, "guards", item_id)
        require_text_list(item, "catalog_update_plan", item_id)
        require_text_list(item, "link_check_plan", item_id)
        require_text_list(item, "rollback_plan", item_id)
        if operation == "copy-first":
            if target in copy_targets:
                fail(f"{item_id}: duplicate copy target: {target}")
            copy_targets.add(target)
            if not target.startswith("redcap-knowledge/"):
                fail(f"{item_id}: copy-first target must stay under redcap-knowledge: {target}")
            target_path = root / target
            if target_path.exists():
                if not target_path.is_file():
                    fail(f"{item_id}: copy-first target exists but is not a file: {target}")
                source_hash = sha256_file(source_snapshot)
                target_hash = sha256_file(target_path)
                if source_hash != target_hash:
                    fail(f"{item_id}: copy-first target exists with mismatched hash: {target}")
            for guard in ("catalog-alias-required-before-apply", "local-link-check-required-before-apply", "receipt-anchor-preserve-old-path", "copy-first-delete-last"):
                if guard not in guards:
                    fail(f"{item_id}: missing guard {guard}")
        if operation == "blocked-translate" and "knowledge-index-preserve-first-read" not in guards:
            fail(f"{item_id}: blocked-translate must preserve knowledge index first-read")
        if cid == "task-reports" and "receipt-anchor-preserve-old-path" not in guards:
            fail(f"{item_id}: task report item must preserve receipt anchors")

    for cid, collection in collection_by_id.items():
        if collection.get("manifest_item_count") != item_counts[cid]:
            fail(
                f"{cid}: manifest_item_count mismatch expected={item_counts[cid]} "
                f"actual={collection.get('manifest_item_count')}"
            )
        if collection.get("item_scope") == "collection-summary-only" and item_counts[cid] != 0:
            fail(f"{cid}: collection-summary-only must not include file-level items")

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        fail("summary must be an object")
    if summary.get("total_items") != len(items):
        fail(f"summary.total_items mismatch expected={len(items)} actual={summary.get('total_items')}")
    if summary.get("copy_first_items") != sum(1 for item in items if item.get("operation") == "copy-first"):
        fail("summary.copy_first_items mismatch")
    if summary.get("blocked_translate_items") != sum(1 for item in items if item.get("operation") == "blocked-translate"):
        fail("summary.blocked_translate_items mismatch")
    follow_up = require_text_list(payload, "follow_up_required", "manifest")
    if not any("redcap-arsenal" in row and "bulk-copy" in row for row in follow_up):
        fail("follow_up_required must keep raw history out of redcap-arsenal")

    return {
        "items": len(items),
        "copy_first": summary.get("copy_first_items"),
        "blocked_translate": summary.get("blocked_translate_items"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or validate RedCap legacy asset migration apply-preflight plan.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--dry-run", default=str(DEFAULT_DRY_RUN))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--write", action="store_true", help="Regenerate the manifest deterministically before checking it.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    dry_run = Path(args.dry_run)
    manifest = Path(args.manifest)
    if not dry_run.is_absolute():
        dry_run = (Path.cwd() / dry_run).resolve()
    if not manifest.is_absolute():
        manifest = (Path.cwd() / manifest).resolve()
    if not dry_run.is_file():
        fail(f"missing dry-run manifest: {dry_run}")

    if args.write:
        payload = generate_manifest(root, dry_run)
        write_json(manifest, payload)
    if not manifest.is_file():
        fail(f"missing manifest: {manifest}; run with --write first")
    result = validate_manifest(manifest, root)
    print(
        "LEGACY_ASSET_MIGRATION_APPLY_PREFLIGHT_OK "
        f"{manifest} items={result['items']} copy_first={result['copy_first']} "
        f"blocked_translate={result['blocked_translate']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

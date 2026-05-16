#!/usr/bin/env python3
# 用途：控制面保障脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#control-plane-assurance

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "references/legacy-asset-migration-worktree-rehearsal.json"
DEFAULT_CATALOG = ROOT / "compass/docs/catalog.json"
DEFAULT_RESULT = ROOT / "references/legacy-asset-migration-alias-resolver.json"
DEFAULT_DELETE_LAST_RESULT = ROOT / "references/legacy-asset-delete-last-apply.json"

RESOLVER_ID = "redcap-legacy-asset-migration-alias-resolver"
TASK_ID = "historical-asset-migration-alias-resolver"
SOURCE_ID = "redcap-legacy-asset-migration-worktree-rehearsal"
DELETE_LAST_ID = "redcap-legacy-asset-delete-last-apply"
LEGACY_PRIVATE_ARCHIVE_ROOT = "redcap-knowledge"
PRIVATE_ARCHIVE_ROOT = "private-archive/redcap-knowledge"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-legacy-asset-alias-resolver] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid {label} json {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be a JSON object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def safe_relative(raw: str, label: str) -> str:
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        fail(f"{label} must be a safe repo-relative path: {raw}")
    return path.as_posix()


def is_private_archive_path(raw: str) -> bool:
    return raw.startswith(f"{LEGACY_PRIVATE_ARCHIVE_ROOT}/") or raw.startswith(f"{PRIVATE_ARCHIVE_ROOT}/")


def canonical_private_archive_path(raw: str) -> str:
    if raw.startswith(f"{PRIVATE_ARCHIVE_ROOT}/"):
        return raw
    if raw.startswith(f"{LEGACY_PRIVATE_ARCHIVE_ROOT}/"):
        return f"{PRIVATE_ARCHIVE_ROOT}{raw[len(LEGACY_PRIVATE_ARCHIVE_ROOT):]}"
    fail(f"private archive path must stay under {PRIVATE_ARCHIVE_ROOT} or legacy {LEGACY_PRIVATE_ARCHIVE_ROOT}: {raw}")
    raise AssertionError("unreachable")


def load_catalog_paths(path: Path) -> set[str]:
    catalog = load_json(path, "docs catalog")
    entries = catalog.get("entries")
    if not isinstance(entries, list):
        fail("docs catalog missing entries list")
    paths: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            fail(f"docs catalog entry[{index}] missing path")
        paths.add(entry["path"])
    return paths


def load_optional_delete_last_result(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = load_json(path, "delete-last apply result")
    if payload.get("manifest_id") != DELETE_LAST_ID:
        fail(f"delete-last result manifest_id must be {DELETE_LAST_ID}")
    if payload.get("task_id") != "historical-asset-migration-delete-last-canonical-switch":
        fail("delete-last result task_id mismatch")
    if payload.get("delete_last_applied") is not True:
        return None
    if payload.get("canonical_switch_applied") is not True:
        fail("delete-last result exists but canonical_switch_applied is not true")
    if payload.get("public_export_allowed") is not False:
        fail("delete-last result public_export_allowed must be false")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        fail("delete-last result entries must be a non-empty list")
    return payload


def validate_source(source: dict[str, Any]) -> list[dict[str, Any]]:
    if source.get("manifest_id") != SOURCE_ID:
        fail(f"source result manifest_id must be {SOURCE_ID}")
    if source.get("apply_allowed") is not False:
        fail("source result apply_allowed must be false")
    if source.get("main_tree_mutated") is not False:
        fail("source result main_tree_mutated must be false")
    if source.get("public_export_allowed") is not False:
        fail("source result public_export_allowed must be false")
    safety = source.get("safety_checks")
    if not isinstance(safety, dict) or not safety:
        fail("source result safety_checks must be a non-empty object")
    for key, value in safety.items():
        if value is not True:
            fail(f"source result safety_checks.{key} must be true")
    alias_map = source.get("alias_map")
    if not isinstance(alias_map, list) or not alias_map:
        fail("source result alias_map must be a non-empty list")
    return alias_map


def target_state(root: Path, old_path: str, new_path: str, expected_sha: str) -> tuple[str, bool]:
    target = root / new_path
    if not target.exists():
        return "planned-not-applied", False
    if not target.is_file():
        fail(f"target path exists but is not a file: {new_path}")
    actual = sha256_file(target)
    if actual != expected_sha:
        fail(f"target hash mismatch for applied copy: {old_path} -> {new_path}")
    return "applied-copy-present", True


def build_post_delete_resolver(root: Path, delete_last_path: Path, delete_last_result: dict[str, Any], catalog_path: Path) -> dict[str, Any]:
    catalog_paths = load_catalog_paths(catalog_path)
    seen_old: set[str] = set()
    seen_new: set[str] = set()
    entries: list[dict[str, Any]] = []
    task_report_anchors = 0

    for index, row in enumerate(delete_last_result["entries"]):
        if not isinstance(row, dict):
            fail(f"delete-last entries[{index}] must be an object")
        item_id = str(row.get("item_id") or "").strip()
        if not item_id:
            fail(f"delete-last entries[{index}] missing item_id")
        old_path = safe_relative(str(row.get("old_path") or ""), f"{item_id}.old_path")
        new_path = safe_relative(str(row.get("new_path") or ""), f"{item_id}.new_path")
        if old_path in seen_old:
            fail(f"duplicate old path: {old_path}")
        if new_path in seen_new:
            fail(f"duplicate new path: {new_path}")
        seen_old.add(old_path)
        seen_new.add(new_path)
        if not old_path.startswith("compass/docs/"):
            fail(f"{item_id}: old path must remain under compass/docs: {old_path}")
        if not is_private_archive_path(new_path):
            fail(f"{item_id}: new path must remain under private archive: {new_path}")
        canonical_new_path = canonical_private_archive_path(new_path)
        if old_path in catalog_paths:
            fail(f"{item_id}: retired old path is still present in docs catalog: {old_path}")
        source_file = root / old_path
        if source_file.exists():
            fail(f"{item_id}: retired old source still exists: {old_path}")
        expected_sha = str(row.get("source_sha256") or "").strip()
        if len(expected_sha) != 64:
            fail(f"{item_id}: source_sha256 must be a sha256 hex string")
        target = root / canonical_new_path
        if not target.is_file():
            fail(f"{item_id}: canonical target missing after delete-last: {canonical_new_path}")
        if sha256_file(target) != expected_sha:
            fail(f"{item_id}: canonical target hash mismatch after delete-last: {canonical_new_path}")
        receipt_anchor = old_path.startswith("compass/docs/task-reports/")
        if receipt_anchor:
            task_report_anchors += 1

        entries.append(
            {
                "item_id": item_id,
                "old_path": old_path,
                "legacy_new_path": new_path,
                "new_path": canonical_new_path,
                "canonical_path": canonical_new_path,
                "requested_new_path_resolves_to": canonical_new_path,
                "old_path_authoritative": False,
                "old_catalog_anchor_present": False,
                "old_path_retired": True,
                "new_target_exists": True,
                "target_state": "canonical-copy-present",
                "source_sha256": expected_sha,
                "receipt_anchor_preserved": receipt_anchor,
                "resolution_policy": "new-path-canonical-old-path-retired",
            }
        )

    return {
        "version": 1,
        "manifest_id": RESOLVER_ID,
        "task_id": TASK_ID,
        "created_for_task": TASK_ID,
        "source_result": repo_rel(root, delete_last_path),
        "source_result_sha256": sha256_file(delete_last_path),
        "source_git_head": delete_last_result.get("source_git_head"),
        "source_git_head_scope": "delete-last-apply-result; regenerate after any rollback or catalog refresh",
        "docs_catalog": repo_rel(root, catalog_path),
        "apply_allowed": False,
        "delete_allowed": False,
        "public_export_allowed": False,
        "main_tree_apply_allowed": False,
        "resolution_policy": {
            "old_path_authoritative": False,
            "new_path_is_canonical_after_delete_last": True,
            "receipt_anchor_uses_old_path_for_historical_correspondence": True,
            "delete_last_applied": True,
            "alias_entries_are_post_delete_canonical": True,
            "non_copy_first_item_ids_may_be_absent": True,
        },
        "summary": {
            "alias_entries": len(entries),
            "task_report_anchor_entries": task_report_anchors,
            "old_catalog_anchors_present": 0,
            "retired_old_anchors": len(entries),
            "planned_targets": 0,
            "applied_targets": len(entries),
        },
        "entries": entries,
        "follow_up_required": [
            "Keep historical receipt report_path values unchanged for correspondence checks.",
            "Use this resolver when an old compass/docs migrated path is requested after delete-last.",
            "Do not public-export redcap-knowledge without separate redaction and dedupe review.",
        ],
    }


def build_resolver(root: Path, source_path: Path, catalog_path: Path, delete_last_path: Path) -> dict[str, Any]:
    delete_last_result = load_optional_delete_last_result(delete_last_path)
    if delete_last_result is not None:
        return build_post_delete_resolver(root, delete_last_path, delete_last_result, catalog_path)

    source = load_json(source_path, "worktree rehearsal result")
    alias_map = validate_source(source)
    catalog_paths = load_catalog_paths(catalog_path)

    seen_old: set[str] = set()
    seen_new: set[str] = set()
    entries: list[dict[str, Any]] = []
    planned_targets = 0
    applied_targets = 0
    task_report_anchors = 0

    for index, row in enumerate(alias_map):
        if not isinstance(row, dict):
            fail(f"alias_map[{index}] must be an object")
        item_id = str(row.get("item_id") or "").strip()
        if not item_id:
            fail(f"alias_map[{index}] missing item_id")
        old_path = safe_relative(str(row.get("old_path") or ""), f"{item_id}.old_path")
        new_path = safe_relative(str(row.get("new_path") or ""), f"{item_id}.new_path")
        if old_path in seen_old:
            fail(f"duplicate old path: {old_path}")
        if new_path in seen_new:
            fail(f"duplicate new path: {new_path}")
        seen_old.add(old_path)
        seen_new.add(new_path)
        if not old_path.startswith("compass/docs/"):
            fail(f"{item_id}: old path must remain under compass/docs: {old_path}")
        if not is_private_archive_path(new_path):
            fail(f"{item_id}: new path must remain under private archive: {new_path}")
        canonical_new_path = canonical_private_archive_path(new_path)
        if old_path not in catalog_paths:
            fail(f"{item_id}: old path missing from docs catalog: {old_path}")
        source_file = root / old_path
        if not source_file.is_file():
            fail(f"{item_id}: old source path missing: {old_path}")
        expected_sha = str(row.get("source_sha256") or "").strip()
        if len(expected_sha) != 64:
            fail(f"{item_id}: source_sha256 must be a sha256 hex string")
        if sha256_file(source_file) != expected_sha:
            fail(f"{item_id}: old source hash no longer matches worktree rehearsal result: {old_path}")
        state, target_exists = target_state(root, old_path, canonical_new_path, expected_sha)
        if state == "planned-not-applied":
            planned_targets += 1
        else:
            applied_targets += 1
        receipt_anchor = bool(row.get("receipt_anchor_preserved"))
        if receipt_anchor:
            task_report_anchors += 1

        entries.append(
            {
                "item_id": item_id,
                "old_path": old_path,
                "legacy_new_path": new_path,
                "new_path": canonical_new_path,
                "canonical_path": old_path,
                "requested_new_path_resolves_to": old_path,
                "old_path_authoritative": True,
                "old_catalog_anchor_present": True,
                "new_target_exists": target_exists,
                "target_state": state,
                "source_sha256": expected_sha,
                "receipt_anchor_preserved": receipt_anchor,
                "resolution_policy": "old-path-authoritative-copy-target-candidate",
            }
        )

    return {
        "version": 1,
        "manifest_id": RESOLVER_ID,
        "task_id": TASK_ID,
        "created_for_task": TASK_ID,
        "source_result": repo_rel(root, source_path),
        "source_result_sha256": sha256_file(source_path),
        "source_git_head": source.get("source_git_head"),
        "source_git_head_scope": "worktree-rehearsal-baseline; regenerate after any main-tree apply or source-result refresh",
        "docs_catalog": repo_rel(root, catalog_path),
        "apply_allowed": False,
        "delete_allowed": False,
        "public_export_allowed": False,
        "main_tree_apply_allowed": False,
        "resolution_policy": {
            "old_path_authoritative": True,
            "new_path_is_candidate_until_apply": True,
            "receipt_anchor_uses_old_path": True,
            "delete_last_requires_separate_risk_window": True,
            "alias_entries_are_copy_first_only": True,
            "non_copy_first_item_ids_may_be_absent": True,
        },
        "summary": {
            "alias_entries": len(entries),
            "task_report_anchor_entries": task_report_anchors,
            "old_catalog_anchors_present": len(entries),
            "planned_targets": planned_targets,
            "applied_targets": applied_targets,
        },
        "entries": entries,
        "follow_up_required": [
            "After copy-first targets are applied, keep old compass/docs anchors authoritative until a separate delete-last risk window.",
            "Re-run this resolver after any real apply so target_state can move from planned-not-applied to applied-copy-present.",
            "Do not delete old compass/docs anchors until receipt, catalog and local-link checks are revalidated after apply.",
            "Before main-tree apply, confirm non-copy-first plan items that are absent from alias entries are intentionally preserve/blocked items.",
        ],
    }


def validate_result(result: dict[str, Any], expected: dict[str, Any] | None = None) -> None:
    if result.get("manifest_id") != RESOLVER_ID:
        fail(f"manifest_id must be {RESOLVER_ID}")
    if result.get("task_id") != TASK_ID:
        fail(f"task_id must be {TASK_ID}")
    if result.get("created_for_task") != TASK_ID:
        fail(f"created_for_task must be {TASK_ID}")
    for key in ("apply_allowed", "delete_allowed", "public_export_allowed", "main_tree_apply_allowed"):
        if result.get(key) is not False:
            fail(f"{key} must be false")
    summary = result.get("summary")
    entries = result.get("entries")
    if not isinstance(summary, dict):
        fail("summary must be an object")
    if not isinstance(entries, list) or not entries:
        fail("entries must be a non-empty list")
    alias_entries = summary.get("alias_entries")
    if alias_entries != len(entries):
        fail("summary.alias_entries must equal len(entries)")
    old_authoritative = result.get("resolution_policy", {}).get("old_path_authoritative") is True
    post_delete = result.get("resolution_policy", {}).get("delete_last_applied") is True
    if old_authoritative and summary.get("old_catalog_anchors_present") != len(entries):
        fail("summary.old_catalog_anchors_present must equal len(entries)")
    if post_delete and summary.get("old_catalog_anchors_present") != 0:
        fail("summary.old_catalog_anchors_present must be 0 after delete-last")
    if summary.get("planned_targets", 0) + summary.get("applied_targets", 0) != len(entries):
        fail("planned_targets + applied_targets must equal len(entries)")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            fail(f"entries[{index}] must be an object")
        if old_authoritative:
            if entry.get("canonical_path") != entry.get("old_path"):
                fail(f"entries[{index}] canonical_path must equal old_path")
            if entry.get("requested_new_path_resolves_to") != entry.get("old_path"):
                fail(f"entries[{index}] requested_new_path_resolves_to must equal old_path")
            if entry.get("old_path_authoritative") is not True:
                fail(f"entries[{index}] old_path_authoritative must be true")
            if entry.get("old_catalog_anchor_present") is not True:
                fail(f"entries[{index}] old_catalog_anchor_present must be true")
        elif post_delete:
            if entry.get("canonical_path") != entry.get("new_path"):
                fail(f"entries[{index}] canonical_path must equal new_path after delete-last")
            if entry.get("requested_new_path_resolves_to") != entry.get("new_path"):
                fail(f"entries[{index}] requested_new_path_resolves_to must equal new_path after delete-last")
            if entry.get("old_path_authoritative") is not False:
                fail(f"entries[{index}] old_path_authoritative must be false after delete-last")
            if entry.get("old_catalog_anchor_present") is not False:
                fail(f"entries[{index}] old_catalog_anchor_present must be false after delete-last")
        else:
            fail("resolver must be either old-authoritative or post-delete canonical")
        if entry.get("target_state") not in {"planned-not-applied", "applied-copy-present", "canonical-copy-present"}:
            fail(f"entries[{index}] target_state is invalid")
    if expected is not None and result != expected:
        fail("result file stale or inconsistent with live alias resolver")


def resolve_path(result: dict[str, Any], catalog_paths: set[str], raw_path: str) -> dict[str, Any]:
    requested = safe_relative(raw_path, "resolve path")
    for entry in result.get("entries", []):
        if requested == entry["old_path"]:
            if entry.get("old_path_authoritative") is False:
                return {
                    "status": "retired-old-anchor",
                    "requested_path": requested,
                    "canonical_path": entry["new_path"],
                    "candidate_path": entry["new_path"],
                    "target_state": entry["target_state"],
                    "old_path_authoritative": False,
                    "authority_note": f"old compass/docs anchor has been retired by delete-last; use canonical {PRIVATE_ARCHIVE_ROOT} path",
                }
            return {
                "status": "old-anchor",
                "requested_path": requested,
                "canonical_path": entry["old_path"],
                "candidate_path": entry["new_path"],
                "target_state": entry["target_state"],
                "old_path_authoritative": True,
            }
        if requested == entry["new_path"]:
            if entry.get("old_path_authoritative") is False:
                return {
                    "status": "canonical-target",
                    "requested_path": requested,
                    "canonical_path": entry["new_path"],
                    "candidate_path": entry["new_path"],
                    "target_state": entry["target_state"],
                    "old_path_authoritative": False,
                    "authority_note": f"{PRIVATE_ARCHIVE_ROOT} path is canonical after delete-last",
                }
            return {
                "status": "candidate-target",
                "requested_path": requested,
                "canonical_path": entry["old_path"],
                "candidate_path": entry["new_path"],
                "target_state": entry["target_state"],
                "old_path_authoritative": True,
            }
        if requested == entry.get("legacy_new_path"):
            return {
                "status": "legacy-private-anchor",
                "requested_path": requested,
                "canonical_path": entry["new_path"],
                "candidate_path": entry["new_path"],
                "target_state": entry["target_state"],
                "old_path_authoritative": bool(entry.get("old_path_authoritative")),
                "authority_note": f"legacy {LEGACY_PRIVATE_ARCHIVE_ROOT} anchor resolves to canonical {PRIVATE_ARCHIVE_ROOT}",
            }
    if requested.startswith(f"{LEGACY_PRIVATE_ARCHIVE_ROOT}/"):
        canonical = canonical_private_archive_path(requested)
        if (ROOT / canonical).is_file():
            return {
                "status": "legacy-private-anchor",
                "requested_path": requested,
                "canonical_path": canonical,
                "candidate_path": canonical,
                "target_state": "canonical-copy-present",
                "old_path_authoritative": False,
                "authority_note": f"legacy {LEGACY_PRIVATE_ARCHIVE_ROOT} anchor resolves to canonical {PRIVATE_ARCHIVE_ROOT}",
            }
    if requested.startswith(f"{PRIVATE_ARCHIVE_ROOT}/") and (ROOT / requested).is_file():
        return {
            "status": "canonical-target",
            "requested_path": requested,
            "canonical_path": requested,
            "candidate_path": requested,
            "target_state": "canonical-copy-present",
            "old_path_authoritative": False,
            "authority_note": f"{PRIVATE_ARCHIVE_ROOT} path is canonical for private archive assets",
        }
    if requested.startswith("compass/docs/task-reports/") and requested not in catalog_paths:
        archived = f"{PRIVATE_ARCHIVE_ROOT}/task-reports/{Path(requested).name}"
        if (ROOT / archived).is_file():
            return {
                "status": "retired-old-anchor",
                "requested_path": requested,
                "canonical_path": archived,
                "candidate_path": archived,
                "target_state": "canonical-copy-present",
                "old_path_authoritative": False,
                "authority_note": "old compass/docs task-report anchor has been archived into private archive",
            }
    if requested in catalog_paths:
        return {
            "status": "catalog-exact",
            "requested_path": requested,
            "canonical_path": requested,
            "migration_scope": "outside-alias-map",
            "old_path_authoritative": False,
            "authority_note": "not-applicable; this catalog path is outside the copy-first alias resolver",
        }
    return {
        "status": "unresolved",
        "requested_path": requested,
        "canonical_path": None,
        "migration_scope": "unknown",
        "old_path_authoritative": False,
        "authority_note": "unresolved path is outside the docs catalog and alias resolver",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and validate RedCap legacy asset alias resolver.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--result", default=str(DEFAULT_RESULT))
    parser.add_argument("--delete-last-result", default=str(DEFAULT_DELETE_LAST_RESULT))
    parser.add_argument("--write-result", action="store_true")
    parser.add_argument("--check-result", action="store_true")
    parser.add_argument("--resolve", default="")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    source = Path(args.source)
    catalog = Path(args.catalog)
    result_path = Path(args.result)
    delete_last_result = Path(args.delete_last_result)
    if not source.is_absolute():
        source = (Path.cwd() / source).resolve()
    if not catalog.is_absolute():
        catalog = (Path.cwd() / catalog).resolve()
    if not result_path.is_absolute():
        result_path = (Path.cwd() / result_path).resolve()
    if args.delete_last_result == str(DEFAULT_DELETE_LAST_RESULT):
        delete_last_result = root / "references/legacy-asset-delete-last-apply.json"
    elif not delete_last_result.is_absolute():
        delete_last_result = (Path.cwd() / delete_last_result).resolve()
    if not source.is_file() and not delete_last_result.is_file():
        fail(f"missing source result: {source}")
    if not catalog.is_file():
        fail(f"missing docs catalog: {catalog}")

    live = build_resolver(root, source, catalog, delete_last_result)
    validate_result(live)
    if args.write_result:
        write_json(result_path, live)
    if args.check_result:
        if not result_path.is_file():
            fail(f"missing result file: {result_path}")
        validate_result(load_json(result_path, "alias resolver result"), expected=live)
    if args.resolve:
        result = load_json(result_path, "alias resolver result") if result_path.is_file() else live
        validate_result(result, expected=live if result_path.is_file() else None)
        print(json.dumps(resolve_path(result, load_catalog_paths(catalog), args.resolve), ensure_ascii=False, indent=2))
        return 0

    print(
        "LEGACY_ASSET_ALIAS_RESOLVER_OK "
        f"{source} aliases={live['summary']['alias_entries']} "
        f"old_anchors={live['summary']['old_catalog_anchors_present']} "
        f"planned_targets={live['summary']['planned_targets']} "
        f"applied_targets={live['summary']['applied_targets']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

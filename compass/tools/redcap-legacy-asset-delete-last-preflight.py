#!/usr/bin/env python3
# 用途：控制面保障脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#control-plane-assurance

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_APPLY_RESULT = ROOT / "references/legacy-asset-migration-main-tree-apply.json"
DEFAULT_RESULT = ROOT / "references/legacy-asset-delete-last-preflight.json"
DEFAULT_DELETE_LAST_RESULT = ROOT / "references/legacy-asset-delete-last-apply.json"

PREFLIGHT_ID = "redcap-legacy-asset-delete-last-preflight"
TASK_ID = "historical-asset-migration-delete-last-canonical-switch"
SOURCE_APPLY_ID = "redcap-legacy-asset-main-tree-copy-apply"
DELETE_LAST_ID = "redcap-legacy-asset-delete-last-apply"

EVIDENCE_REFERENCE_PATHS = {
    "references/legacy-asset-migration-apply-plan.json",
    "references/legacy-asset-migration-apply-rehearsal.json",
    "references/legacy-asset-migration-worktree-rehearsal.json",
    "references/legacy-asset-migration-main-tree-apply.json",
    "references/legacy-asset-migration-alias-resolver.json",
    "references/legacy-asset-delete-last-apply.json",
    "assets/references/legacy-asset-migration-apply-plan.json",
    "assets/references/legacy-asset-migration-apply-rehearsal.json",
    "assets/references/legacy-asset-migration-worktree-rehearsal.json",
    "assets/references/legacy-asset-migration-main-tree-apply.json",
    "assets/references/legacy-asset-migration-alias-resolver.json",
    "assets/references/legacy-asset-delete-last-apply.json",
}

SELF_GENERATED_REFERENCE_PATHS = {
    "references/legacy-asset-delete-last-preflight.json",
    "assets/references/legacy-asset-delete-last-preflight.json",
}
LEGACY_PRIVATE_ARCHIVE_ROOT = "redcap-knowledge"
PRIVATE_ARCHIVE_ROOT = "private-archive/redcap-knowledge"
ASSETS_PRIVATE_ARCHIVE_ROOT = "assets/private-archive/redcap-knowledge"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-legacy-asset-delete-last-preflight] {message}")


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
    if path.is_absolute() or raw.startswith("~") or ".." in path.parts:
        fail(f"{label} must be a safe repo-relative path: {raw}")
    return path.as_posix()


def private_archive_fs_path(raw: str) -> str:
    if raw.startswith(f"{ASSETS_PRIVATE_ARCHIVE_ROOT}/"):
        return raw
    if raw.startswith(f"{PRIVATE_ARCHIVE_ROOT}/"):
        return raw
    if raw.startswith(f"{LEGACY_PRIVATE_ARCHIVE_ROOT}/"):
        return f"{PRIVATE_ARCHIVE_ROOT}{raw[len(LEGACY_PRIVATE_ARCHIVE_ROOT):]}"
    return raw


def is_private_archive_path(raw: str) -> bool:
    return (
        raw.startswith(f"{LEGACY_PRIVATE_ARCHIVE_ROOT}/")
        or raw.startswith(f"{PRIVATE_ARCHIVE_ROOT}/")
        or raw.startswith(f"{ASSETS_PRIVATE_ARCHIVE_ROOT}/")
    )


def tracked_files(root: Path) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        files = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        if files:
            return files
    except Exception:
        pass

    result: list[str] = []
    ignored_dirs = {".git", "__pycache__", ".pytest_cache", "node_modules"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = repo_rel(root, path)
        if any(part in ignored_dirs for part in Path(rel).parts):
            continue
        result.append(rel)
    return sorted(result)


def load_delete_last_result(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = load_json(path, "delete-last apply result")
    if payload.get("manifest_id") != DELETE_LAST_ID:
        fail(f"delete-last result manifest_id must be {DELETE_LAST_ID}")
    if payload.get("task_id") != TASK_ID:
        fail("delete-last result task_id mismatch")
    if payload.get("delete_last_applied") is not True:
        return None
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        fail("delete-last result entries must be a non-empty list")
    return payload


def delete_last_old_paths(delete_last: dict[str, Any] | None) -> set[str]:
    if delete_last is None:
        return set()
    result: set[str] = set()
    for entry in delete_last.get("entries", []):
        if isinstance(entry, dict) and isinstance(entry.get("old_path"), str):
            result.add(entry["old_path"])
    return result


def validate_apply_result(root: Path, apply_result_path: Path, delete_last: dict[str, Any] | None) -> list[dict[str, Any]]:
    payload = load_json(apply_result_path, "main-tree apply result")
    if payload.get("manifest_id") != SOURCE_APPLY_ID:
        fail(f"source apply result manifest_id must be {SOURCE_APPLY_ID}")
    if payload.get("delete_allowed") is not False:
        fail("source apply result must not already allow delete")
    if payload.get("public_export_allowed") is not False:
        fail("source apply result public_export_allowed must be false")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        fail("source apply result entries must be a non-empty list")

    normalized: list[dict[str, Any]] = []
    seen_old: set[str] = set()
    seen_new: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            fail(f"source apply result entries[{index}] must be an object")
        old_path = safe_relative(str(entry.get("old_path") or ""), f"entries[{index}].old_path")
        new_path = safe_relative(str(entry.get("new_path") or ""), f"entries[{index}].new_path")
        expected_sha = str(entry.get("source_sha256") or "").strip()
        if len(expected_sha) != 64:
            fail(f"{old_path}: source_sha256 must be a sha256 hex string")
        if old_path in seen_old:
            fail(f"duplicate old path: {old_path}")
        if new_path in seen_new:
            fail(f"duplicate new path: {new_path}")
        seen_old.add(old_path)
        seen_new.add(new_path)
        if not old_path.startswith("compass/docs/"):
            fail(f"old path must stay under compass/docs: {old_path}")
        if not is_private_archive_path(new_path):
            fail(f"new path must stay under private archive: {new_path}")

        old_file = root / old_path
        new_file = root / private_archive_fs_path(new_path)
        old_exists = old_file.is_file()
        new_exists = new_file.is_file()
        old_sha = sha256_file(old_file) if old_exists else None
        new_sha = sha256_file(new_file) if new_exists else None
        old_retired_by_delete_last = old_path in delete_last_old_paths(delete_last)
        normalized.append(
            {
                "item_id": str(entry.get("item_id") or old_path),
                "old_path": old_path,
                "new_path": new_path,
                "expected_sha256": expected_sha,
                "old_exists": old_exists,
                "new_exists": new_exists,
                "old_sha256": old_sha,
                "new_sha256": new_sha,
                "old_retired_by_delete_last": old_retired_by_delete_last,
                "hashes_match": (
                    new_exists
                    and new_sha == expected_sha
                    and (
                        (old_exists and old_sha == expected_sha)
                        or (old_retired_by_delete_last and not old_exists)
                    )
                ),
            }
        )
    return normalized


def classify_reference(file_path: str, old_path: str) -> str:
    if file_path in EVIDENCE_REFERENCE_PATHS:
        return "migration-evidence"
    if file_path == "references/parent-receipt-aggregation-policy.json":
        return "historical-receipt-correspondence-reference"
    if file_path == "references/token-structural-governance.json":
        return "old-anchor-structural-governance-reference"
    if file_path == "compass/tools/redcap-multi-session-acceptance.sh":
        return "acceptance-alias-compat-reference"
    if file_path == "compass/docs/catalog.json":
        return "docs-catalog-current-anchor"
    if is_private_archive_path(file_path):
        return "private-copy-self-or-history"
    if file_path == old_path:
        return "old-source-self"
    return "active-control-hard-reference"


def scan_references(root: Path, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    old_paths = [entry["old_path"] for entry in entries]
    old_set = set(old_paths)
    references: list[dict[str, Any]] = []
    for rel in tracked_files(root):
        if rel in old_set or is_private_archive_path(rel) or rel in SELF_GENERATED_REFERENCE_PATHS:
            continue
        path = root / rel
        try:
            data = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for old_path in old_paths:
            count = data.count(old_path)
            if count:
                references.append(
                    {
                        "file": rel,
                        "old_path": old_path,
                        "count": count,
                        "classification": classify_reference(rel, old_path),
                    }
                )
    return references


def summarize_references(references: list[dict[str, Any]]) -> dict[str, Any]:
    by_class: dict[str, int] = {}
    hard_files: set[str] = set()
    catalog_entries = 0
    for ref in references:
        cls = str(ref["classification"])
        by_class[cls] = by_class.get(cls, 0) + int(ref["count"])
        if cls == "active-control-hard-reference":
            hard_files.add(str(ref["file"]))
        if cls == "docs-catalog-current-anchor":
            catalog_entries += int(ref["count"])
    return {
        "reference_classes": dict(sorted(by_class.items())),
        "hard_reference_files": sorted(hard_files),
        "hard_reference_file_count": len(hard_files),
        "catalog_old_anchor_mentions": catalog_entries,
    }


def build_preflight(root: Path, apply_result_path: Path, delete_last_path: Path) -> dict[str, Any]:
    delete_last = load_delete_last_result(delete_last_path)
    entries = validate_apply_result(root, apply_result_path, delete_last)
    references = scan_references(root, entries)
    ref_summary = summarize_references(references)
    delete_last_applied = delete_last is not None
    source_missing = [entry["old_path"] for entry in entries if not entry["old_exists"]]
    unexpected_source_missing = [
        entry["old_path"]
        for entry in entries
        if not entry["old_exists"] and not entry["old_retired_by_delete_last"]
    ]
    unexpected_source_present = [
        entry["old_path"]
        for entry in entries
        if entry["old_exists"] and entry["old_retired_by_delete_last"]
    ]
    target_missing = [entry["new_path"] for entry in entries if not entry["new_exists"]]
    hash_mismatches = [
        {
            "old_path": entry["old_path"],
            "new_path": entry["new_path"],
            "old_sha256": entry["old_sha256"],
            "new_sha256": entry["new_sha256"],
            "expected_sha256": entry["expected_sha256"],
        }
        for entry in entries
        if not entry["hashes_match"]
    ]
    hard_refs = [ref for ref in references if ref["classification"] == "active-control-hard-reference"]
    catalog_refs = [ref for ref in references if ref["classification"] == "docs-catalog-current-anchor"]

    blockers: list[dict[str, Any]] = []
    if unexpected_source_missing:
        blockers.append({"id": "old-source-missing", "count": len(unexpected_source_missing), "paths": unexpected_source_missing})
    if unexpected_source_present:
        blockers.append({"id": "retired-old-source-still-present", "count": len(unexpected_source_present), "paths": unexpected_source_present})
    if target_missing:
        blockers.append({"id": "copy-target-missing", "count": len(target_missing), "paths": target_missing})
    if hash_mismatches:
        blockers.append({"id": "copy-target-hash-mismatch", "count": len(hash_mismatches), "items": hash_mismatches})
    if hard_refs:
        blockers.append(
            {
                "id": "active-control-hard-reference",
                "count": len(hard_refs),
                "files": ref_summary["hard_reference_files"],
                "examples": hard_refs[:20],
            }
        )
    if catalog_refs and (source_missing or delete_last_applied):
        blockers.append(
            {
                "id": "docs-catalog-current-anchor-after-delete",
                "count": len(catalog_refs),
                "meaning": "The docs catalog still lists old compass/docs assets after at least one old source is missing; regenerate catalog before claiming delete-last complete.",
                "examples": catalog_refs[:10],
            }
        )

    delete_ready = not blockers and not delete_last_applied
    delete_applied_ok = delete_last_applied and not blockers
    return {
        "version": 1,
        "manifest_id": PREFLIGHT_ID,
        "task_id": TASK_ID,
        "created_for_task": TASK_ID,
        "source_apply_result": repo_rel(root, apply_result_path),
        "source_apply_result_sha256": sha256_file(apply_result_path),
        "delete_last_result": repo_rel(root, delete_last_path) if delete_last_applied else None,
        "delete_last_result_sha256": sha256_file(delete_last_path) if delete_last_applied else None,
        "delete_last_preflight_ready": delete_ready,
        "delete_last_applied": delete_applied_ok,
        "canonical_switch_preflight_ready": delete_ready,
        "canonical_switch_applied": delete_applied_ok,
        "delete_allowed": delete_ready,
        "canonical_switch_allowed": delete_ready,
        "public_export_allowed": False,
        "summary": {
            "entries": len(entries),
            "old_sources_present": len(entries) - len(source_missing),
            "old_sources_retired": len(source_missing) if delete_last_applied else 0,
            "copy_targets_present": len(entries) - len(target_missing),
            "hash_match_entries": len(entries) - len(hash_mismatches),
            "reference_mentions": sum(int(ref["count"]) for ref in references),
            "hard_reference_files": ref_summary["hard_reference_file_count"],
            "blocker_count": len(blockers),
            **ref_summary,
        },
        "blockers": blockers,
        "reference_scan": references,
        "entries": entries,
        "decision": (
            "ready-for-delete-last-risk-window"
            if delete_ready
            else "delete-last-already-applied"
            if delete_applied_ok
            else "blocked-by-live-references-or-anchor-state"
        ),
        "next_action": (
            "Run a separate guarded delete/canonical-switch apply."
            if delete_ready
            else "Delete-last is already applied; keep catalog and resolver regenerated and run closeout checks."
            if delete_applied_ok
            else "Migrate active hard references first; keep old compass/docs anchors authoritative."
        ),
        "allowed_reference_classes": [
            "acceptance-alias-compat-reference",
            "historical-receipt-correspondence-reference",
            "migration-evidence",
            "old-anchor-structural-governance-reference",
            "private-copy-self-or-history",
            "old-source-self",
            "docs-catalog-current-anchor",
        ],
        "blocked_reference_classes": [
            "active-control-hard-reference",
            "docs-catalog-current-anchor-after-delete",
        ],
        "post_delete_required_checks": [
            "Regenerate compass/docs/catalog.json after physical delete.",
            "Re-run this preflight after delete so docs-catalog-current-anchor becomes zero or old sources are restored.",
        ],
    }


def validate_preflight(result: dict[str, Any], expected: dict[str, Any] | None = None) -> None:
    if result.get("manifest_id") != PREFLIGHT_ID:
        fail(f"manifest_id must be {PREFLIGHT_ID}")
    if result.get("task_id") != TASK_ID:
        fail(f"task_id must be {TASK_ID}")
    if result.get("created_for_task") != TASK_ID:
        fail(f"created_for_task must be {TASK_ID}")
    if result.get("public_export_allowed") is not False:
        fail("public_export_allowed must be false")
    summary = result.get("summary")
    entries = result.get("entries")
    blockers = result.get("blockers")
    references = result.get("reference_scan")
    if not isinstance(summary, dict):
        fail("summary must be an object")
    if not isinstance(entries, list) or not entries:
        fail("entries must be a non-empty list")
    if not isinstance(blockers, list):
        fail("blockers must be a list")
    if not isinstance(references, list):
        fail("reference_scan must be a list")
    ready = bool(result.get("delete_last_preflight_ready"))
    applied = bool(result.get("delete_last_applied"))
    if ready and applied:
        fail("result cannot be both preflight-ready and delete-last-applied")
    if result.get("delete_allowed") is not ready:
        fail("delete_allowed must equal delete_last_preflight_ready")
    if result.get("canonical_switch_allowed") is not ready:
        fail("canonical_switch_allowed must equal delete_last_preflight_ready")
    if (ready or applied) and blockers:
        fail("ready/applied result cannot contain blockers")
    if not ready and not applied and not blockers:
        fail("blocked result must contain at least one blocker")
    if summary.get("entries") != len(entries):
        fail("summary.entries must equal len(entries)")
    if summary.get("blocker_count") != len(blockers):
        fail("summary.blocker_count must equal len(blockers)")
    if expected is not None and result != expected:
        fail("result file stale or inconsistent with live delete-last preflight")


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight RedCap legacy asset delete-last/canonical-switch safety.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--apply-result", default=str(DEFAULT_APPLY_RESULT))
    parser.add_argument("--result", default=str(DEFAULT_RESULT))
    parser.add_argument("--delete-last-result", default=str(DEFAULT_DELETE_LAST_RESULT))
    parser.add_argument("--write-result", action="store_true", help="Write the preflight result.")
    parser.add_argument("--check-result", action="store_true", help="Validate --result against live state.")
    parser.add_argument("--require-ready", action="store_true", help="Fail when delete-last is still blocked.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    apply_result = Path(args.apply_result)
    result_path = Path(args.result)
    delete_last_path = Path(args.delete_last_result)
    if not apply_result.is_absolute():
        apply_result = (Path.cwd() / apply_result).resolve()
    if not result_path.is_absolute():
        result_path = (Path.cwd() / result_path).resolve()
    if args.delete_last_result == str(DEFAULT_DELETE_LAST_RESULT):
        delete_last_path = root / "references/legacy-asset-delete-last-apply.json"
    elif not delete_last_path.is_absolute():
        delete_last_path = (Path.cwd() / delete_last_path).resolve()
    if not apply_result.is_file():
        fail(f"missing source apply result: {apply_result}")

    preflight = build_preflight(root, apply_result, delete_last_path)
    validate_preflight(preflight)
    if args.write_result:
        write_json(result_path, preflight)
    if args.check_result:
        if not result_path.is_file():
            fail(f"missing result file: {result_path}")
        validate_preflight(load_json(result_path, "delete-last preflight result"), expected=preflight)
    if args.require_ready and not preflight["delete_last_preflight_ready"]:
        fail(f"delete-last preflight blocked with {preflight['summary']['blocker_count']} blocker groups")

    label = (
        "READY"
        if preflight["delete_last_preflight_ready"]
        else "APPLIED"
        if preflight.get("delete_last_applied")
        else "BLOCKED"
    )
    summary = preflight["summary"]
    print(
        f"LEGACY_ASSET_DELETE_LAST_PREFLIGHT_{label} "
        f"entries={summary['entries']} hard_reference_file_count={summary['hard_reference_file_count']} "
        f"blockers={summary['blocker_count']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

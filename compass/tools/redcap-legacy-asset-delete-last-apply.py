#!/usr/bin/env python3
# 用途：控制面保障脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#control-plane-assurance

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PREFLIGHT = ROOT / "references/legacy-asset-delete-last-preflight.json"
DEFAULT_RESULT = ROOT / "references/legacy-asset-delete-last-apply.json"

APPLY_ID = "redcap-legacy-asset-delete-last-apply"
TASK_ID = "historical-asset-migration-delete-last-canonical-switch"
PREFLIGHT_ID = "redcap-legacy-asset-delete-last-preflight"
PUBLIC_TARGET_PREFIXES = {"redcap-arsenal", "shared-knowledge"}
PUBLIC_TARGET_NESTED_PREFIXES = {("templates", "shared-knowledge")}
LEGACY_PRIVATE_ARCHIVE_ROOT = "redcap-knowledge"
PRIVATE_ARCHIVE_ROOT = "private-archive/redcap-knowledge"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-legacy-asset-delete-last-apply] {message}")


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
    if raw.startswith(f"{PRIVATE_ARCHIVE_ROOT}/"):
        return raw
    if raw.startswith(f"{LEGACY_PRIVATE_ARCHIVE_ROOT}/"):
        return f"{PRIVATE_ARCHIVE_ROOT}{raw[len(LEGACY_PRIVATE_ARCHIVE_ROOT):]}"
    return raw


def is_private_archive_path(raw: str) -> bool:
    return raw.startswith(f"{LEGACY_PRIVATE_ARCHIVE_ROOT}/") or raw.startswith(f"{PRIVATE_ARCHIVE_ROOT}/")


def is_public_target(raw: str) -> bool:
    parts = Path(raw).parts
    return bool(
        (parts and parts[0] in PUBLIC_TARGET_PREFIXES)
        or tuple(parts[:2]) in PUBLIC_TARGET_NESTED_PREFIXES
    )


def validate_preflight(root: Path, path: Path) -> list[dict[str, Any]]:
    payload = load_json(path, "delete-last preflight")
    if payload.get("manifest_id") != PREFLIGHT_ID:
        fail(f"preflight manifest_id must be {PREFLIGHT_ID}")
    if payload.get("task_id") != TASK_ID:
        fail(f"preflight task_id must be {TASK_ID}")
    if payload.get("delete_last_preflight_ready") is not True:
        fail("delete-last preflight is not ready")
    if payload.get("delete_allowed") is not True:
        fail("preflight delete_allowed must be true before apply")
    if payload.get("public_export_allowed") is not False:
        fail("preflight public_export_allowed must be false")
    blockers = payload.get("blockers")
    if blockers:
        fail("preflight contains blockers; refusing delete-last apply")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        fail("preflight entries must be a non-empty list")

    normalized: list[dict[str, Any]] = []
    seen_old: set[str] = set()
    seen_new: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            fail(f"preflight entries[{index}] must be an object")
        old_path = safe_relative(str(entry.get("old_path") or ""), f"entries[{index}].old_path")
        new_path = safe_relative(str(entry.get("new_path") or ""), f"entries[{index}].new_path")
        expected_sha = str(entry.get("expected_sha256") or "").strip()
        if len(expected_sha) != 64:
            fail(f"{old_path}: expected_sha256 must be a sha256 hex string")
        if old_path in seen_old:
            fail(f"duplicate old path: {old_path}")
        if new_path in seen_new:
            fail(f"duplicate new path: {new_path}")
        seen_old.add(old_path)
        seen_new.add(new_path)
        if not old_path.startswith("compass/docs/"):
            fail(f"old path must stay under compass/docs: {old_path}")
        if not is_private_archive_path(new_path) or is_public_target(new_path):
            fail(f"unsafe private copy target: {new_path}")
        old_file = root / old_path
        new_file = root / private_archive_fs_path(new_path)
        if not old_file.is_file():
            fail(f"old source missing before delete-last apply: {old_path}")
        if not new_file.is_file():
            fail(f"private copy target missing before delete-last apply: {new_path}")
        old_sha = sha256_file(old_file)
        new_sha = sha256_file(new_file)
        if old_sha != expected_sha or new_sha != expected_sha:
            fail(f"hash mismatch before delete-last apply: {old_path} -> {new_path}")
        normalized.append(
            {
                "item_id": str(entry.get("item_id") or old_path),
                "old_path": old_path,
                "new_path": new_path,
                "source_sha256": expected_sha,
                "old_sha256_before": old_sha,
                "new_sha256": new_sha,
            }
        )
    return normalized


def build_receipt(root: Path, preflight_path: Path, *, apply: bool) -> tuple[dict[str, Any], int]:
    entries = validate_preflight(root, preflight_path)
    deleted = 0
    receipt_entries: list[dict[str, Any]] = []
    rollback_plan: list[dict[str, str]] = []
    for entry in entries:
        old_path = entry["old_path"]
        new_path = entry["new_path"]
        expected_sha = entry["source_sha256"]
        old_file = root / old_path
        new_file = root / private_archive_fs_path(new_path)
        old_existed_before = old_file.is_file()
        if not old_existed_before:
            fail(f"old source missing during delete-last apply: {old_path}")
        if sha256_file(old_file) != expected_sha:
            fail(f"old source hash drifted during delete-last apply: {old_path}")
        if not new_file.is_file() or sha256_file(new_file) != expected_sha:
            fail(f"private copy target hash drifted during delete-last apply: {new_path}")
        if apply:
            old_file.unlink()
            deleted += 1
        old_exists_after = old_file.exists()
        if apply and old_exists_after:
            fail(f"old source still exists after delete-last apply: {old_path}")
        if not new_file.is_file() or sha256_file(new_file) != expected_sha:
            fail(f"private copy target missing after delete-last apply: {new_path}")
        receipt_entries.append(
            {
                "item_id": entry["item_id"],
                "old_path": old_path,
                "new_path": new_path,
                "canonical_path": new_path if apply else old_path,
                "old_path_retired": bool(apply),
                "old_existed_before": old_existed_before,
                "old_exists_after": old_exists_after,
                "new_target_exists_after": new_file.is_file(),
                "source_sha256": expected_sha,
                "new_sha256": sha256_file(new_file),
                "operation": "delete-last" if apply else "delete-last-dry-run",
            }
        )
        rollback_plan.append(
            {
                "action": "restore-old-source-from-private-copy",
                "old_path": old_path,
                "new_path": new_path,
                "required_sha256": expected_sha,
            }
        )
    receipt = {
        "version": 1,
        "manifest_id": APPLY_ID,
        "task_id": TASK_ID,
        "created_for_task": TASK_ID,
        "apply_mode": "delete-last-canonical-switch",
        "source_preflight": repo_rel(root, preflight_path),
        "source_preflight_sha256": sha256_file(preflight_path),
        "apply_allowed_by_this_tool": apply,
        "main_tree_mutated": bool(apply),
        "delete_last_applied": bool(apply),
        "canonical_switch_applied": bool(apply),
        "public_export_allowed": False,
        "old_paths_remain_authoritative": not bool(apply),
        "canonical_path_policy": (
            "redcap-knowledge private copies are canonical for migrated historical assets; old compass/docs anchors are retired"
            if apply
            else "old compass/docs paths remain canonical until --apply is used"
        ),
        "summary": {
            "delete_entries": len(receipt_entries),
            "deleted_old_sources": deleted,
            "retired_old_sources": sum(1 for item in receipt_entries if item["old_path_retired"]),
            "private_copy_targets_present": sum(1 for item in receipt_entries if item["new_target_exists_after"]),
            "rollback_entries": len(rollback_plan),
            "all_old_sources_retired": bool(apply) and all(not item["old_exists_after"] for item in receipt_entries),
        },
        "entries": receipt_entries,
        "rollback_plan": rollback_plan,
        "follow_up_required": [
            "Regenerate compass/docs/catalog.json after delete-last apply.",
            "Regenerate alias resolver so retired old paths resolve to redcap-knowledge canonical paths.",
            "Run spec-check, diagnose, acceptance and Prism-bound closeout before claiming this child complete.",
        ],
    }
    validate_receipt(receipt)
    return receipt, deleted


def validate_receipt(result: dict[str, Any]) -> None:
    if result.get("manifest_id") != APPLY_ID:
        fail(f"result manifest_id must be {APPLY_ID}")
    if result.get("task_id") != TASK_ID:
        fail(f"result task_id must be {TASK_ID}")
    if result.get("created_for_task") != TASK_ID:
        fail(f"result created_for_task must be {TASK_ID}")
    if result.get("public_export_allowed") is not False:
        fail("public_export_allowed must be false")
    summary = result.get("summary")
    entries = result.get("entries")
    rollback = result.get("rollback_plan")
    if not isinstance(summary, dict):
        fail("summary must be an object")
    if not isinstance(entries, list) or not entries:
        fail("entries must be a non-empty list")
    if not isinstance(rollback, list) or len(rollback) != len(entries):
        fail("rollback_plan must match entries")
    if summary.get("delete_entries") != len(entries):
        fail("summary.delete_entries must equal len(entries)")
    if summary.get("rollback_entries") != len(rollback):
        fail("summary.rollback_entries must equal rollback_plan length")
    applied = bool(result.get("delete_last_applied"))
    if result.get("canonical_switch_applied") is not applied:
        fail("canonical_switch_applied must equal delete_last_applied")
    if result.get("old_paths_remain_authoritative") is applied:
        fail("old_paths_remain_authoritative must be false after apply and true before apply")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            fail(f"entries[{index}] must be an object")
        old_path = safe_relative(str(entry.get("old_path") or ""), f"entries[{index}].old_path")
        new_path = safe_relative(str(entry.get("new_path") or ""), f"entries[{index}].new_path")
        expected_sha = str(entry.get("source_sha256") or "").strip()
        if len(expected_sha) != 64:
            fail(f"{old_path}: source_sha256 must be a sha256 hex string")
        if applied:
            if entry.get("canonical_path") != new_path:
                fail(f"{old_path}: canonical_path must switch to new_path after apply")
            if entry.get("old_path_retired") is not True:
                fail(f"{old_path}: old_path_retired must be true after apply")
        else:
            if entry.get("canonical_path") != old_path:
                fail(f"{old_path}: canonical_path must remain old_path before apply")
            if entry.get("old_path_retired") is not False:
                fail(f"{old_path}: old_path_retired must be false before apply")


def validate_live_result(root: Path, result_path: Path) -> dict[str, Any]:
    result = load_json(result_path, "delete-last apply result")
    validate_receipt(result)
    entries = result["entries"]
    applied = bool(result.get("delete_last_applied"))
    for entry in entries:
        old_path = safe_relative(str(entry["old_path"]), "result.old_path")
        new_path = safe_relative(str(entry["new_path"]), "result.new_path")
        expected_sha = str(entry["source_sha256"])
        new_file = root / private_archive_fs_path(new_path)
        if not new_file.is_file() or sha256_file(new_file) != expected_sha:
            fail(f"private copy target missing or drifted: {new_path}")
        old_file = root / old_path
        if applied:
            if old_file.exists():
                fail(f"old source still exists after delete-last result: {old_path}")
        else:
            if not old_file.is_file() or sha256_file(old_file) != expected_sha:
                fail(f"old source missing or drifted before delete-last result: {old_path}")
    return result


def rollback_from_receipt(root: Path, result_path: Path) -> int:
    result = validate_live_result(root, result_path)
    restored = 0
    for index, step in enumerate(result.get("rollback_plan", [])):
        if not isinstance(step, dict):
            fail(f"rollback_plan[{index}] must be an object")
        if step.get("action") != "restore-old-source-from-private-copy":
            fail(f"rollback_plan[{index}] unsupported action")
        old_path = safe_relative(str(step.get("old_path") or ""), f"rollback_plan[{index}].old_path")
        new_path = safe_relative(str(step.get("new_path") or ""), f"rollback_plan[{index}].new_path")
        expected_sha = str(step.get("required_sha256") or "").strip()
        old_file = root / old_path
        new_file = root / private_archive_fs_path(new_path)
        if old_file.exists():
            if not old_file.is_file() or sha256_file(old_file) != expected_sha:
                fail(f"rollback refuses mismatched existing old source: {old_path}")
            continue
        if not new_file.is_file() or sha256_file(new_file) != expected_sha:
            fail(f"rollback source private copy missing or drifted: {new_path}")
        old_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(new_file, old_file)
        restored += 1
    return restored


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply RedCap legacy asset delete-last/canonical-switch safely.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--preflight", default=str(DEFAULT_PREFLIGHT))
    parser.add_argument("--result", default=str(DEFAULT_RESULT))
    parser.add_argument("--apply", action="store_true", help="Physically delete old compass/docs sources.")
    parser.add_argument("--write-result", action="store_true", help="Write the delete-last apply receipt.")
    parser.add_argument("--check-result", action="store_true", help="Validate --result against live state.")
    parser.add_argument("--rollback", action="store_true", help="Restore old compass/docs sources from private copies.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    preflight = Path(args.preflight)
    result_path = Path(args.result)
    if not preflight.is_absolute():
        preflight = (Path.cwd() / preflight).resolve()
    if not result_path.is_absolute():
        result_path = (Path.cwd() / result_path).resolve()

    if args.rollback:
        restored = rollback_from_receipt(root, result_path)
        print(f"LEGACY_ASSET_DELETE_LAST_APPLY_ROLLBACK_OK restored={restored}")
        return 0

    if args.check_result and not args.write_result and not args.apply:
        result = validate_live_result(root, result_path)
        summary = result["summary"]
        print(
            "LEGACY_ASSET_DELETE_LAST_APPLY_OK "
            f"entries={summary['delete_entries']} retired={summary['retired_old_sources']} "
            f"targets={summary['private_copy_targets_present']}"
        )
        return 0

    if not preflight.is_file():
        fail(f"missing preflight result: {preflight}")
    receipt, deleted = build_receipt(root, preflight, apply=args.apply)
    if args.write_result:
        write_json(result_path, receipt)
    if args.check_result:
        validate_live_result(root, result_path)
    summary = receipt["summary"]
    status = "OK" if args.apply else "READY"
    print(
        f"LEGACY_ASSET_DELETE_LAST_APPLY_{status} "
        f"entries={summary['delete_entries']} deleted={deleted} "
        f"retired={summary['retired_old_sources']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

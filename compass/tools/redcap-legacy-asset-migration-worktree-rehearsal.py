#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = ROOT / "references/legacy-asset-migration-apply-plan.json"
DEFAULT_RESULT = ROOT / "references/legacy-asset-migration-worktree-rehearsal.json"
CATALOG_SCRIPT = SCRIPT_DIR / "redcap-docs-catalog.py"
BASE_REHEARSAL_SCRIPT = SCRIPT_DIR / "redcap-legacy-asset-migration-rehearsal.py"

REHEARSAL_ID = "redcap-legacy-asset-migration-worktree-rehearsal"
TASK_ID = "historical-asset-migration-worktree-rehearsal"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-legacy-asset-migration-worktree-rehearsal] {message}")


def load_base_module() -> Any:
    spec = importlib.util.spec_from_file_location("redcap_temp_copy_rehearsal", BASE_REHEARSAL_SCRIPT)
    if spec is None or spec.loader is None:
        fail(f"cannot load base rehearsal module: {BASE_REHEARSAL_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load_base_module()


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid json {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"json payload must be an object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_command(args: list[str], *, cwd: Path | None = None) -> str:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        fail(f"command failed: {' '.join(args)}{': ' + detail if detail else ''}")
    return completed.stdout.strip()


def git_output(root: Path, *args: str) -> str:
    return run_command(["git", "-C", str(root), *args])


def git_status(root: Path) -> str:
    return git_output(root, "status", "--porcelain=v1", "--untracked-files=all")


def worktree_registry_contains(root: Path, worktree: Path) -> bool:
    listing = git_output(root, "worktree", "list", "--porcelain")
    expected = f"worktree {worktree.resolve(strict=False)}"
    return any(line.strip() == expected for line in listing.splitlines())


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return BASE.sha256_file(path)


def build_catalog(root: Path, output_path: Path) -> dict[str, Any]:
    run_command(["python3", str(CATALOG_SCRIPT), "generate", str(root), str(output_path)])
    return load_json(output_path)


def catalog_paths(catalog: dict[str, Any]) -> set[str]:
    entries = catalog.get("entries")
    if not isinstance(entries, list):
        fail("generated docs catalog missing entries list")
    paths: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            fail(f"generated docs catalog entry[{index}] missing path")
        paths.add(entry["path"])
    return paths


def validate_catalog_and_alias_overlay(
    worktree: Path,
    catalog: dict[str, Any],
    alias_map: list[dict[str, Any]],
) -> dict[str, Any]:
    paths = catalog_paths(catalog)
    task_report_aliases = [row for row in alias_map if row["old_path"].startswith("compass/docs/task-reports/")]
    missing_old = sorted(row["old_path"] for row in task_report_aliases if row["old_path"] not in paths)
    if missing_old:
        fail("docs catalog lost old task-report anchor(s): " + ", ".join(missing_old[:8]))

    missing_new = sorted(row["new_path"] for row in alias_map if not (worktree / row["new_path"]).is_file())
    if missing_new:
        fail("alias overlay points to missing worktree target(s): " + ", ".join(missing_new[:8]))

    duplicated_old = sorted(
        old_path
        for old_path in {row["old_path"] for row in alias_map}
        if sum(1 for row in alias_map if row["old_path"] == old_path) > 1
    )
    duplicated_new = sorted(
        new_path
        for new_path in {row["new_path"] for row in alias_map}
        if sum(1 for row in alias_map if row["new_path"] == new_path) > 1
    )
    if duplicated_old:
        fail("alias overlay contains duplicate old path(s): " + ", ".join(duplicated_old[:8]))
    if duplicated_new:
        fail("alias overlay contains duplicate new path(s): " + ", ".join(duplicated_new[:8]))

    return {
        "docs_catalog_entries": len(paths),
        "task_report_alias_entries": len(task_report_aliases),
        "old_task_report_anchors_present": len(task_report_aliases),
        "new_targets_resolved_by_alias_overlay": len(alias_map),
    }


def run_worktree_rehearsal(root: Path, manifest_path: Path) -> dict[str, Any]:
    if not (root / ".git").exists():
        # Linked worktrees use a .git file; plain fixture repos use a directory. Accept either.
        if not (root / ".git").is_file():
            fail(f"root is not a git worktree: {root}")

    before_status = git_status(root)
    head = git_output(root, "rev-parse", "HEAD")
    short_head = git_output(root, "rev-parse", "--short", "HEAD")

    payload = load_json(manifest_path)
    BASE.validate_manifest_header(payload, root)
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        fail("items must be a non-empty list")
    BASE.validate_all_items_safety(root, items)
    copy_items = [item for item in items if isinstance(item, dict) and item.get("operation") == "copy-first"]
    if not copy_items:
        fail("copy-first items must be present for worktree rehearsal")

    copy_targets: set[str] = set()
    normalized_items = [BASE.validate_copy_item(root, item, copy_targets) for item in copy_items]
    alias_map: list[dict[str, Any]] = []
    rollback_plan: list[dict[str, str]] = []
    catalog_validation: dict[str, Any] = {}
    source_overlays: list[str] = []

    tmp_parent = Path(tempfile.mkdtemp(prefix="redcap-legacy-asset-worktree."))
    worktree = tmp_parent / "worktree"
    removed = False
    remove_error = ""
    try:
        run_command(["git", "-C", str(root), "worktree", "add", "--detach", str(worktree), head])

        for item_id, source, target in normalized_items:
            worktree_source = worktree / source
            if not worktree_source.is_file() and (root / source).is_file():
                # During development, the current manifest can include a just-created
                # report that is not in HEAD yet. Overlay only declared manifest sources,
                # never targets, so the rehearsal still proves target isolation.
                worktree_source.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root / source, worktree_source)
                source_overlays.append(source)
            worktree_target = worktree / target
            if not worktree_source.is_file():
                fail(f"{item_id}: worktree source missing: {source}")
            if worktree_target.exists():
                fail(f"{item_id}: worktree target already exists before copy: {target}")
            worktree_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(worktree_source, worktree_target)

            source_hash = sha256_file(worktree_source)
            target_hash = sha256_file(worktree_target)
            if source_hash != target_hash:
                fail(f"{item_id}: copied file hash mismatch: {source} -> {target}")
            if not (root / source).is_file():
                fail(f"{item_id}: main-tree source disappeared during worktree rehearsal: {source}")
            if (root / target).exists():
                fail(f"{item_id}: main-tree target appeared during worktree rehearsal: {target}")

            alias_map.append(
                {
                    "item_id": item_id,
                    "old_path": source,
                    "new_path": target,
                    "source_sha256": source_hash,
                    "target_sha256": target_hash,
                    "old_path_retained": True,
                    "catalog_alias_required": True,
                    "receipt_anchor_preserved": source.startswith("compass/docs/task-reports/"),
                    "resolver_overlay": "old-path-to-copy-first-target",
                }
            )
            rollback_plan.append({"action": "delete-copy-target", "path": target})

        catalog_path = tmp_parent / "catalog.worktree.json"
        catalog = build_catalog(worktree, catalog_path)
        catalog_validation = validate_catalog_and_alias_overlay(worktree, catalog, alias_map)

        for step in rollback_plan:
            path = BASE.safe_relative(step["path"], "rollback", "path")
            worktree_target = worktree / path
            if not worktree_target.is_file():
                fail(f"rollback target missing before rehearsal cleanup: {path}")
            worktree_target.unlink()
            if worktree_target.exists():
                fail(f"rollback target still exists after cleanup: {path}")

        for _item_id, source, target in normalized_items:
            if not (worktree / source).is_file():
                fail(f"rollback cleanup removed source in worktree: {source}")
            if (worktree / target).exists():
                fail(f"rollback cleanup left copy target in worktree: {target}")
            if not (root / source).is_file():
                fail(f"rollback cleanup removed source in main tree: {source}")
            if (root / target).exists():
                fail(f"rollback cleanup created target in main tree: {target}")
    finally:
        if worktree.exists():
            completed = subprocess.run(
                ["git", "-C", str(root), "worktree", "remove", "--force", str(worktree)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if completed.returncode != 0:
                remove_error = (completed.stderr or completed.stdout or "").strip() or "unknown worktree remove failure"
        if not remove_error:
            removed = not worktree.exists() and not worktree_registry_contains(root, worktree)
            shutil.rmtree(tmp_parent, ignore_errors=True)

    if remove_error:
        fail(f"temporary git worktree removal failed: {remove_error}")

    after_status = git_status(root)
    if before_status != after_status:
        fail("main-tree git status changed during worktree rehearsal")
    if not removed:
        fail("temporary git worktree was not fully removed from filesystem and git registry")

    task_report_aliases = [row for row in alias_map if row["old_path"].startswith("compass/docs/task-reports/")]
    return {
        "version": 1,
        "manifest_id": REHEARSAL_ID,
        "created_for_task": TASK_ID,
        "source_manifest": manifest_path.relative_to(root).as_posix() if manifest_path.is_relative_to(root) else str(manifest_path),
        "source_manifest_sha256": sha256_file(manifest_path),
        "source_git_head": short_head,
        "source_git_head_full": head,
        "main_tree_status_before_sha256": digest_text(before_status),
        "main_tree_status_after_sha256": digest_text(after_status),
        "worktree_source_overlay_count": len(source_overlays),
        "worktree_source_overlays": source_overlays,
        "apply_allowed": False,
        "main_tree_mutated": False,
        "public_export_allowed": False,
        "rehearsal_mode": "git-worktree",
        "summary": {
            "total_manifest_items": len(items),
            "copy_first_items": len(copy_items),
            "alias_map_entries": len(alias_map),
            "rollback_entries": len(rollback_plan),
            "task_report_anchor_entries": len(task_report_aliases),
            "non_copy_items_skipped": len(items) - len(copy_items),
        },
        "safety_checks": {
            "git_worktree_used": True,
            "git_worktree_removed": True,
            "git_worktree_registry_clean": True,
            "main_tree_status_unchanged": True,
            "source_paths_retained": True,
            "targets_created_only_in_throwaway_worktree": True,
            "target_hash_matches_source": True,
            "rollback_deletes_copy_targets_only": True,
            "public_targets_blocked": True,
            "main_tree_targets_absent_after_rehearsal": True,
            "receipt_anchor_old_paths_preserved": True,
            "docs_catalog_old_anchors_preserved": True,
            "alias_overlay_resolves_new_targets": True,
        },
        "catalog_anchor_validation": catalog_validation,
        "alias_map": alias_map,
        "rollback_plan": rollback_plan,
        "follow_up_required": [
            "Wire the alias overlay into a durable docs/catalog resolver before any delete-last phase.",
            "Open a separate main-tree apply risk window after Prism review confirms the worktree rehearsal remains current.",
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
    if result.get("rehearsal_mode") != "git-worktree":
        fail("result rehearsal_mode must be git-worktree")
    overlays = result.get("worktree_source_overlays")
    overlay_count = result.get("worktree_source_overlay_count")
    if not isinstance(overlays, list) or not all(isinstance(item, str) and item for item in overlays):
        fail("worktree_source_overlays must be a string list")
    if overlay_count != len(overlays):
        fail("worktree_source_overlay_count must equal len(worktree_source_overlays)")

    summary = result.get("summary")
    if not isinstance(summary, dict):
        fail("result summary must be an object")
    for key in ("copy_first_items", "alias_map_entries", "rollback_entries", "task_report_anchor_entries"):
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

    catalog_validation = result.get("catalog_anchor_validation")
    if not isinstance(catalog_validation, dict):
        fail("catalog_anchor_validation must be an object")
    if catalog_validation.get("task_report_alias_entries") != summary["task_report_anchor_entries"]:
        fail("catalog_anchor_validation.task_report_alias_entries must equal summary.task_report_anchor_entries")
    if catalog_validation.get("new_targets_resolved_by_alias_overlay") != summary["alias_map_entries"]:
        fail("catalog_anchor_validation.new_targets_resolved_by_alias_overlay must equal alias_map_entries")

    if expected is not None:
        for key in (
            "source_manifest_sha256",
            "worktree_source_overlay_count",
            "worktree_source_overlays",
            "summary",
            "safety_checks",
            "catalog_anchor_validation",
            "alias_map",
            "rollback_plan",
        ):
            if result.get(key) != expected.get(key):
                fail(f"result file stale or inconsistent: {key} does not match live worktree rehearsal")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a true git-worktree rehearsal for RedCap historical asset copy-first migration.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--result", default=str(DEFAULT_RESULT))
    parser.add_argument("--write-result", action="store_true", help="Write the worktree rehearsal receipt to --result.")
    parser.add_argument("--check-result", action="store_true", help="Validate --result after running the live worktree rehearsal.")
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

    result = run_worktree_rehearsal(root, manifest)
    validate_result(result)
    if args.write_result:
        write_json(result_path, result)
    if args.check_result:
        if not result_path.is_file():
            fail(f"missing result file: {result_path}")
        validate_result(load_json(result_path), expected=result)

    print(
        "LEGACY_ASSET_MIGRATION_WORKTREE_REHEARSAL_OK "
        f"{manifest} copy_first={result['summary']['copy_first_items']} "
        f"alias_map={result['summary']['alias_map_entries']} "
        f"rollback={result['summary']['rollback_entries']} "
        f"catalog_old_anchors={result['catalog_anchor_validation']['old_task_report_anchors_present']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# 用途：控制面保障脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#control-plane-assurance

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PLAN = ROOT / "references/legacy-asset-migration-apply-plan.json"
DEFAULT_WORKTREE_RESULT = ROOT / "references/legacy-asset-migration-worktree-rehearsal.json"
DEFAULT_RESOLVER = ROOT / "references/legacy-asset-migration-alias-resolver.json"
DEFAULT_RESULT = ROOT / "references/legacy-asset-migration-main-tree-apply.json"
DEFAULT_CATALOG = ROOT / "compass/docs/catalog.json"
DEFAULT_DELETE_LAST_RESULT = ROOT / "references/legacy-asset-delete-last-apply.json"
ALIAS_RESOLVER_SCRIPT = SCRIPT_DIR / "redcap-legacy-asset-alias-resolver.py"

APPLY_ID = "redcap-legacy-asset-main-tree-copy-apply"
DELETE_LAST_ID = "redcap-legacy-asset-delete-last-apply"
TASK_ID = "historical-asset-migration-main-tree-copy-apply"
PLAN_ID = "redcap-legacy-asset-migration-apply-preflight"
WORKTREE_ID = "redcap-legacy-asset-migration-worktree-rehearsal"
PUBLIC_TARGET_PREFIXES = {"redcap-arsenal", "shared-knowledge"}
PUBLIC_TARGET_NESTED_PREFIXES = {("templates", "shared-knowledge")}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-legacy-asset-main-tree-apply] {message}")


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


def is_public_target(raw: str) -> bool:
    parts = Path(raw).parts
    return bool(
        (parts and parts[0] in PUBLIC_TARGET_PREFIXES)
        or tuple(parts[:2]) in PUBLIC_TARGET_NESTED_PREFIXES
    )


def run_command(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            args,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        fail(f"command failed: {' '.join(args)}{': ' + detail if detail else ''}")
    return completed.stdout.strip()


def validate_plan(root: Path, plan_path: Path) -> dict[str, Any]:
    payload = load_json(plan_path, "apply plan")
    if payload.get("manifest_id") != PLAN_ID:
        fail(f"apply plan manifest_id must be {PLAN_ID}")
    if payload.get("apply_allowed") is not False:
        fail("apply plan apply_allowed must stay false; this tool owns the explicit apply gate")
    if payload.get("public_export_allowed") is not False:
        fail("apply plan public_export_allowed must be false")

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        fail("apply plan items must be a non-empty list")
    copy_items: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            fail(f"apply plan items[{index}] must be an object")
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            fail(f"apply plan items[{index}] missing id")
        operation = str(item.get("operation") or "").strip()
        if operation != "copy-first":
            continue
        source = safe_relative(str(item.get("source") or ""), f"{item_id}.source")
        target = safe_relative(str(item.get("target") or ""), f"{item_id}.target")
        if not source.startswith("compass/docs/"):
            fail(f"{item_id}: copy source must stay under compass/docs: {source}")
        if not target.startswith("redcap-knowledge/"):
            fail(f"{item_id}: copy target must stay under redcap-knowledge: {target}")
        if is_public_target(target):
            fail(f"{item_id}: copy target must not point to public/shared repository: {target}")
        if not (root / source).is_file():
            fail(f"{item_id}: source file missing: {source}")
        if item.get("old_path_retained") is not True:
            fail(f"{item_id}: old_path_retained must be true")
        if item.get("public_export_allowed") is not False:
            fail(f"{item_id}: public_export_allowed must be false")
        guards = item.get("guards")
        if not isinstance(guards, list):
            fail(f"{item_id}: guards must be a list")
        for guard in ("copy-first-delete-last", "rollback-delete-copy-only", "receipt-anchor-preserve-old-path"):
            if guard not in guards:
                fail(f"{item_id}: missing guard {guard}")
        if item_id in copy_items:
            fail(f"duplicate copy item id: {item_id}")
        copy_items[item_id] = item

    if not copy_items:
        fail("apply plan must contain copy-first items")
    return {"payload": payload, "copy_items": copy_items}


def validate_worktree_result(worktree_path: Path, plan_path: Path) -> dict[str, Any]:
    payload = load_json(worktree_path, "worktree rehearsal result")
    if payload.get("manifest_id") != WORKTREE_ID:
        fail(f"worktree rehearsal manifest_id must be {WORKTREE_ID}")
    if payload.get("apply_allowed") is not False:
        fail("worktree rehearsal apply_allowed must be false")
    if payload.get("main_tree_mutated") is not False:
        fail("worktree rehearsal main_tree_mutated must be false")
    if payload.get("public_export_allowed") is not False:
        fail("worktree rehearsal public_export_allowed must be false")
    if payload.get("source_manifest_sha256") != sha256_file(plan_path):
        fail("worktree rehearsal source_manifest_sha256 is stale; regenerate rehearsal before apply")
    if payload.get("worktree_source_overlay_count") != 0:
        fail("worktree rehearsal must not rely on uncommitted source overlays before main-tree apply")
    safety = payload.get("safety_checks")
    if not isinstance(safety, dict) or not safety:
        fail("worktree rehearsal safety_checks must be a non-empty object")
    for key, value in safety.items():
        if value is not True:
            fail(f"worktree rehearsal safety_checks.{key} must be true")
    alias_map = payload.get("alias_map")
    if not isinstance(alias_map, list) or not alias_map:
        fail("worktree rehearsal alias_map must be a non-empty list")
    return payload


def validate_resolver(root: Path, resolver_path: Path, *, require_applied: bool) -> dict[str, Any]:
    payload = load_json(resolver_path, "alias resolver")
    if payload.get("manifest_id") != "redcap-legacy-asset-migration-alias-resolver":
        fail("alias resolver manifest_id mismatch")
    summary = payload.get("summary")
    entries = payload.get("entries")
    if not isinstance(summary, dict) or not isinstance(entries, list) or not entries:
        fail("alias resolver must include summary and entries")
    if summary.get("alias_entries") != len(entries):
        fail("alias resolver summary.alias_entries must equal len(entries)")
    if require_applied and summary.get("applied_targets") != len(entries):
        fail("alias resolver must show every copy target as applied-copy-present after apply")
    for entry in entries:
        if not isinstance(entry, dict):
            fail("alias resolver entries must be objects")
        old_path = safe_relative(str(entry.get("old_path") or ""), "resolver.old_path")
        new_path = safe_relative(str(entry.get("new_path") or ""), "resolver.new_path")
        if entry.get("canonical_path") != old_path:
            fail(f"resolver canonical_path must stay on old path: {old_path}")
        if entry.get("old_path_authoritative") is not True:
            fail(f"resolver old_path_authoritative must be true: {old_path}")
        if not (root / old_path).is_file():
            fail(f"resolver old path missing: {old_path}")
        if require_applied:
            if entry.get("target_state") != "applied-copy-present":
                fail(f"resolver target_state must be applied-copy-present: {new_path}")
            if not (root / new_path).is_file():
                fail(f"resolver applied target missing: {new_path}")
    return payload


def copy_entries(
    root: Path,
    copy_items: dict[str, dict[str, Any]],
    alias_map: list[Any],
    *,
    apply: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], int, int]:
    entries: list[dict[str, Any]] = []
    rollback_plan: list[dict[str, str]] = []
    copied = 0
    already_present = 0
    seen_targets: set[str] = set()

    for index, raw_row in enumerate(alias_map):
        if not isinstance(raw_row, dict):
            fail(f"alias_map[{index}] must be an object")
        item_id = str(raw_row.get("item_id") or "").strip()
        if item_id not in copy_items:
            fail(f"{item_id or 'alias_map row'}: alias entry has no matching copy-first plan item")
        plan_item = copy_items[item_id]
        old_path = safe_relative(str(raw_row.get("old_path") or ""), f"{item_id}.old_path")
        new_path = safe_relative(str(raw_row.get("new_path") or ""), f"{item_id}.new_path")
        if old_path != plan_item.get("source"):
            fail(f"{item_id}: alias old_path does not match apply plan source")
        if new_path != plan_item.get("target"):
            fail(f"{item_id}: alias new_path does not match apply plan target")
        if not new_path.startswith("redcap-knowledge/") or is_public_target(new_path):
            fail(f"{item_id}: unsafe copy target: {new_path}")
        if new_path in seen_targets:
            fail(f"{item_id}: duplicate copy target: {new_path}")
        seen_targets.add(new_path)

        source = root / old_path
        target = root / new_path
        if not source.is_file():
            fail(f"{item_id}: old source missing: {old_path}")
        expected_sha = str(raw_row.get("source_sha256") or "").strip()
        if len(expected_sha) != 64:
            fail(f"{item_id}: source_sha256 must be a sha256 hex string")
        source_sha = sha256_file(source)
        if source_sha != expected_sha:
            fail(f"{item_id}: source hash drifted since worktree rehearsal: {old_path}")

        target_existed_before = target.exists()
        if target_existed_before:
            if not target.is_file():
                fail(f"{item_id}: target exists but is not a file: {new_path}")
            target_sha = sha256_file(target)
            if target_sha != expected_sha:
                fail(f"{item_id}: target exists with mismatched hash: {new_path}")
            already_present += 1
        elif apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied += 1

        target_exists_after = target.is_file()
        target_sha_after = sha256_file(target) if target_exists_after else None
        if apply and not target_exists_after:
            fail(f"{item_id}: target missing after copy: {new_path}")
        if target_exists_after and target_sha_after != expected_sha:
            fail(f"{item_id}: target hash mismatch after copy: {new_path}")
        if not source.is_file() or sha256_file(source) != expected_sha:
            fail(f"{item_id}: old source was modified during apply: {old_path}")

        entries.append(
            {
                "item_id": item_id,
                "old_path": old_path,
                "new_path": new_path,
                "canonical_path": old_path,
                "old_path_authoritative": True,
                "old_path_retained": True,
                "target_exists": target_exists_after,
                "target_state": "applied-copy-present" if target_exists_after else "planned-not-applied",
                "source_sha256": expected_sha,
                "target_sha256": target_sha_after,
                "target_existed_before": target_existed_before,
                "operation": "copy-first",
            }
        )
        rollback_plan.append(
            {
                "action": "delete-copy-target-only",
                "path": new_path,
                "required_target_sha256": expected_sha,
                "must_keep_old_path": old_path,
            }
        )

    return entries, rollback_plan, copied, already_present


def refresh_alias_resolver(root: Path, worktree_result: Path, resolver: Path, catalog: Path) -> None:
    run_command(
        [
            "python3",
            str(ALIAS_RESOLVER_SCRIPT),
            "--root",
            str(root),
            "--source",
            str(worktree_result),
            "--catalog",
            str(catalog),
            "--result",
            str(resolver),
            "--write-result",
            "--check-result",
        ]
    )


def build_receipt(
    root: Path,
    plan_path: Path,
    worktree_result_path: Path,
    resolver_path: Path,
    *,
    apply: bool,
    require_applied: bool,
) -> tuple[dict[str, Any], int, int]:
    plan = validate_plan(root, plan_path)
    worktree_result = validate_worktree_result(worktree_result_path, plan_path)
    alias_map = worktree_result["alias_map"]
    entries, rollback_plan, copied, already_present = copy_entries(
        root,
        plan["copy_items"],
        alias_map,
        apply=apply,
    )
    if require_applied and any(not entry["target_exists"] for entry in entries):
        fail("not all copy targets are present; run with --apply before writing/checking result")
    resolver_payload = validate_resolver(root, resolver_path, require_applied=require_applied)
    applied_targets = sum(1 for entry in entries if entry["target_exists"])
    task_report_entries = sum(1 for entry in entries if entry["old_path"].startswith("compass/docs/task-reports/"))

    receipt = {
        "version": 1,
        "manifest_id": APPLY_ID,
        "task_id": TASK_ID,
        "created_for_task": TASK_ID,
        "apply_mode": "main-tree-copy-first",
        "source_manifest": repo_rel(root, plan_path),
        "source_manifest_sha256": sha256_file(plan_path),
        "source_worktree_rehearsal": repo_rel(root, worktree_result_path),
        "source_worktree_rehearsal_sha256": sha256_file(worktree_result_path),
        "source_alias_resolver": repo_rel(root, resolver_path),
        "source_alias_resolver_sha256": sha256_file(resolver_path),
        "source_git_head": worktree_result.get("source_git_head"),
        "apply_allowed_by_this_tool": apply,
        "main_tree_mutated": applied_targets > 0,
        "delete_allowed": False,
        "move_allowed": False,
        "public_export_allowed": False,
        "old_paths_remain_authoritative": True,
        "canonical_path_policy": "old compass/docs paths remain canonical; redcap-knowledge paths are applied copy targets only",
        "summary": {
            "copy_entries": len(entries),
            "applied_targets": applied_targets,
            "planned_targets": len(entries) - applied_targets,
            "copy_targets_present": applied_targets,
            "copy_targets_missing": len(entries) - applied_targets,
            "all_targets_applied": applied_targets == len(entries),
            "task_report_anchor_entries": task_report_entries,
            "rollback_entries": len(rollback_plan),
            "resolver_applied_targets": resolver_payload.get("summary", {}).get("applied_targets"),
        },
        "entries": entries,
        "rollback_plan": rollback_plan,
        "follow_up_required": [
            "Do not delete old compass/docs anchors in this task; delete-last requires a separate risk window.",
            "Keep redcap-knowledge private until a separate redaction, dedupe and public-export review approves curated entries.",
            "Re-run resolver and local link checks before any future canonical-path switch.",
        ],
    }
    validate_receipt(receipt)
    return receipt, copied, already_present


def validate_receipt(result: dict[str, Any], expected: dict[str, Any] | None = None) -> None:
    if result.get("manifest_id") != APPLY_ID:
        fail(f"result manifest_id must be {APPLY_ID}")
    if result.get("task_id") != TASK_ID:
        fail(f"result task_id must be {TASK_ID}")
    if result.get("created_for_task") != TASK_ID:
        fail(f"result created_for_task must be {TASK_ID}")
    if result.get("delete_allowed") is not False:
        fail("delete_allowed must be false")
    if result.get("move_allowed") is not False:
        fail("move_allowed must be false")
    if result.get("public_export_allowed") is not False:
        fail("public_export_allowed must be false")
    if result.get("old_paths_remain_authoritative") is not True:
        fail("old_paths_remain_authoritative must be true")
    summary = result.get("summary")
    entries = result.get("entries")
    rollback_plan = result.get("rollback_plan")
    if not isinstance(summary, dict):
        fail("summary must be an object")
    if not isinstance(entries, list) or not entries:
        fail("entries must be a non-empty list")
    if not isinstance(rollback_plan, list) or len(rollback_plan) != len(entries):
        fail("rollback_plan must match entries")
    if summary.get("copy_entries") != len(entries):
        fail("summary.copy_entries must equal len(entries)")
    if summary.get("applied_targets") + summary.get("planned_targets") != len(entries):
        fail("applied_targets + planned_targets must equal len(entries)")
    if summary.get("rollback_entries") != len(rollback_plan):
        fail("summary.rollback_entries must equal rollback_plan length")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            fail(f"entries[{index}] must be an object")
        if entry.get("canonical_path") != entry.get("old_path"):
            fail(f"entries[{index}] canonical_path must equal old_path")
        if entry.get("old_path_authoritative") is not True:
            fail(f"entries[{index}] old_path_authoritative must be true")
        if entry.get("old_path_retained") is not True:
            fail(f"entries[{index}] old_path_retained must be true")
        if entry.get("target_state") not in {"planned-not-applied", "applied-copy-present"}:
            fail(f"entries[{index}] invalid target_state")
    if expected is not None and result != expected:
        fail("result file stale or inconsistent with live main-tree apply receipt")


def delete_last_applied(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return payload.get("manifest_id") == DELETE_LAST_ID and payload.get("delete_last_applied") is True


def validate_historical_receipt_after_delete_last(root: Path, result_path: Path) -> dict[str, Any]:
    result = load_json(result_path, "main-tree apply receipt")
    validate_receipt(result)
    for index, entry in enumerate(result.get("entries", [])):
        if not isinstance(entry, dict):
            fail(f"entries[{index}] must be an object")
        new_path = safe_relative(str(entry.get("new_path") or ""), f"entries[{index}].new_path")
        expected_sha = str(entry.get("source_sha256") or "").strip()
        if len(expected_sha) != 64:
            fail(f"{new_path}: source_sha256 must be a sha256 hex string")
        target = root / new_path
        if not target.is_file():
            fail(f"historical copy target missing after delete-last: {new_path}")
        if sha256_file(target) != expected_sha:
            fail(f"historical copy target drifted after delete-last: {new_path}")
    return result


def rollback_from_receipt(root: Path, result_path: Path) -> int:
    result = load_json(result_path, "main-tree apply receipt")
    validate_receipt(result)
    removed = 0
    for index, step in enumerate(result.get("rollback_plan", [])):
        if not isinstance(step, dict):
            fail(f"rollback_plan[{index}] must be an object")
        if step.get("action") != "delete-copy-target-only":
            fail(f"rollback_plan[{index}] unsupported action")
        target_rel = safe_relative(str(step.get("path") or ""), f"rollback_plan[{index}].path")
        old_rel = safe_relative(str(step.get("must_keep_old_path") or ""), f"rollback_plan[{index}].must_keep_old_path")
        expected_sha = str(step.get("required_target_sha256") or "").strip()
        if not target_rel.startswith("redcap-knowledge/"):
            fail(f"rollback target must stay under redcap-knowledge: {target_rel}")
        if is_public_target(target_rel):
            fail(f"rollback target must not point to public/shared repository: {target_rel}")
        if not (root / old_rel).is_file():
            fail(f"rollback refuses to run because old source is missing: {old_rel}")
        target = root / target_rel
        if not target.exists():
            continue
        if not target.is_file():
            fail(f"rollback target exists but is not a file: {target_rel}")
        if sha256_file(target) != expected_sha:
            fail(f"rollback target hash mismatch; refusing to delete: {target_rel}")
        target.unlink()
        removed += 1
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply RedCap legacy asset copy-first targets in the main tree.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--worktree-result", default=str(DEFAULT_WORKTREE_RESULT))
    parser.add_argument("--resolver", default=str(DEFAULT_RESOLVER))
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--result", default=str(DEFAULT_RESULT))
    parser.add_argument("--delete-last-result", default=str(DEFAULT_DELETE_LAST_RESULT))
    parser.add_argument("--apply", action="store_true", help="Create missing redcap-knowledge copy targets.")
    parser.add_argument("--refresh-resolver", action="store_true", help="Regenerate alias resolver after applying copies.")
    parser.add_argument("--write-result", action="store_true", help="Write the main-tree apply receipt.")
    parser.add_argument("--check-result", action="store_true", help="Validate --result against live state.")
    parser.add_argument("--rollback", action="store_true", help="Delete copy targets listed in --result if hashes match.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    plan = Path(args.plan)
    worktree_result = Path(args.worktree_result)
    resolver = Path(args.resolver)
    catalog = Path(args.catalog)
    result_path = Path(args.result)
    delete_last_result = Path(args.delete_last_result)
    for name, value in {
        "plan": plan,
        "worktree_result": worktree_result,
        "resolver": resolver,
        "catalog": catalog,
        "result": result_path,
    }.items():
        if not value.is_absolute():
            value = (Path.cwd() / value).resolve()
        if name == "plan":
            plan = value
        elif name == "worktree_result":
            worktree_result = value
        elif name == "resolver":
            resolver = value
        elif name == "catalog":
            catalog = value
        elif name == "result":
            result_path = value
    if args.delete_last_result == str(DEFAULT_DELETE_LAST_RESULT):
        delete_last_result = root / "references/legacy-asset-delete-last-apply.json"
    elif not delete_last_result.is_absolute():
        delete_last_result = (Path.cwd() / delete_last_result).resolve()

    if args.rollback:
        removed = rollback_from_receipt(root, result_path)
        print(f"LEGACY_ASSET_MAIN_TREE_APPLY_ROLLBACK_OK removed={removed}")
        return 0

    if args.check_result and delete_last_applied(delete_last_result):
        receipt = validate_historical_receipt_after_delete_last(root, result_path)
        summary = receipt["summary"]
        print(
            "LEGACY_ASSET_MAIN_TREE_APPLY_OK "
            f"entries={summary['copy_entries']} applied={summary['applied_targets']} "
            f"planned={summary['planned_targets']} copied=0 already_present={summary['applied_targets']} "
            "delete_last_applied=true"
        )
        return 0

    for path, label in ((plan, "plan"), (worktree_result, "worktree result"), (resolver, "resolver"), (catalog, "catalog")):
        if not path.is_file():
            fail(f"missing {label}: {path}")

    if args.apply and args.refresh_resolver:
        # Build once before mutating so stale source evidence fails before any copy happens.
        build_receipt(root, plan, worktree_result, resolver, apply=False, require_applied=False)
        receipt, copied, already_present = build_receipt(root, plan, worktree_result, resolver, apply=True, require_applied=False)
        refresh_alias_resolver(root, worktree_result, resolver, catalog)
        receipt, copied_after_refresh, already_after_refresh = build_receipt(
            root,
            plan,
            worktree_result,
            resolver,
            apply=False,
            require_applied=True,
        )
        copied = max(copied, copied_after_refresh)
        already_present = max(already_present, already_after_refresh)
    else:
        receipt, copied, already_present = build_receipt(
            root,
            plan,
            worktree_result,
            resolver,
            apply=args.apply,
            require_applied=args.write_result or args.check_result,
        )

    if args.write_result:
        write_json(result_path, receipt)
    if args.check_result:
        if not result_path.is_file():
            fail(f"missing result file: {result_path}")
        validate_receipt(load_json(result_path, "main-tree apply receipt"), expected=receipt)

    summary = receipt["summary"]
    status = "OK" if summary["planned_targets"] == 0 else "READY"
    print(
        f"LEGACY_ASSET_MAIN_TREE_APPLY_{status} "
        f"entries={summary['copy_entries']} applied={summary['applied_targets']} "
        f"planned={summary['planned_targets']} copied={copied} already_present={already_present}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

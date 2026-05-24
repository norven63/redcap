#!/usr/bin/env python3
# 用途：产品形态与检索治理脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#product-shape-and-retrieval

from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAN = ROOT / "references/root-information-architecture-consolidation-plan.json"
IGNORED_ROOT_CHILDREN = {".git", ".DS_Store"}
IGNORED_ROOT_CHILD_PATTERNS = (
    ".acceptance-*.md",
    ".tmp-*",
)
REQUIRED_CONSUMERS = {
    "host entries",
    "runtime facades",
    "control-plane validators",
    "Prism evidence and provider governance",
    "docs and archaeology",
    "package and release surface",
    "human status and notification surfaces",
}
APPLIED_STATUS = "target-model-complete-physical-convergence-applied-with-compatibility-shims"
REQUIRED_MOVED_ROOTS = {
    "compass/docs": "assets/docs",
    "compass/knowledge": "assets/knowledge",
    "references": "assets/references",
    "prism/reports": "assets/evidence/prism-reports",
    "private-archive": "assets/private-archive",
}
REQUIRED_COMPATIBILITY_SHIMS = {
    "compass/docs": "../assets/docs",
    "compass/knowledge": "../assets/knowledge",
    "references": "assets/references",
    "prism/reports": "../assets/evidence/prism-reports",
    "private-archive": "assets/private-archive",
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-root-information-architecture-check] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"{label} missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label}: {exc}")
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


def current_root_children(root: Path) -> set[str]:
    return {
        child.name
        for child in root.iterdir()
        if child.name not in IGNORED_ROOT_CHILDREN
        and not any(fnmatch.fnmatch(child.name, pattern) for pattern in IGNORED_ROOT_CHILD_PATTERNS)
    }


def target_parent_ids(plan: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for entry in plan.get("target_parent_model", []):
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            ids.add(entry["id"].strip())
    return {item for item in ids if item}


def validate_inventory(plan: dict[str, Any], root: Path) -> None:
    inventory = require_list(plan, "root_inventory", "plan")
    valid_target_parents = target_parent_ids(plan)
    if not valid_target_parents:
        fail("target_parent_model must be defined before inventory can reference it")
    by_path: dict[str, dict[str, Any]] = {}
    for entry in inventory:
        if not isinstance(entry, dict):
            fail("root_inventory entries must be objects")
        path = require_text(entry, "path", "root_inventory entry")
        if "/" in path.rstrip("/"):
            fail(f"root_inventory path must be a direct root child: {path}")
        if path in by_path:
            fail(f"duplicate root_inventory path: {path}")
        by_path[path] = entry
        for key in [
            "type",
            "presence",
            "current_role",
            "visibility",
            "package_surface",
            "target_disposition",
            "target_parent",
            "move_risk",
            "consumer_notes",
        ]:
            require_text(entry, key, path)
        presence = entry["presence"]
        if presence == "required-source" and not (root / path).exists():
            fail(f"required root child missing: {path}")
        if presence not in {"required-source", "optional-local"}:
            fail(f"unsupported presence for {path}: {presence}")
        if entry["type"] not in {"file", "directory"}:
            fail(f"unsupported type for {path}: {entry['type']}")
        if entry["target_parent"] not in valid_target_parents:
            fail(f"{path}: target_parent does not match a target_parent_model id: {entry['target_parent']}")

    missing = sorted(current_root_children(root) - set(by_path))
    if missing:
        fail("root children missing from inventory: " + ", ".join(missing))


def validate_target_model(plan: dict[str, Any]) -> None:
    model = require_list(plan, "target_parent_model", "plan")
    required_ids = {
        "root-human-entry",
        "root-host-entry",
        "public-runtime",
        "root-contract",
        "internal-control-plane",
        "prism-layer-and-evidence",
        "private-archive",
        "templates-and-external-arsenal",
        "internal-layer-a",
        "workspace-state",
    }
    seen: set[str] = set()
    for entry in model:
        if not isinstance(entry, dict):
            fail("target_parent_model entries must be objects")
        item_id = require_text(entry, "id", "target_parent_model entry")
        if item_id in seen:
            fail(f"duplicate target parent id: {item_id}")
        seen.add(item_id)
        require_text(entry, "meaning", item_id)
        if not any(key in entry for key in ("keep_at_root", "current_roots", "future_shape")):
            fail(f"{item_id}: must define keep_at_root, current_roots, or future_shape")
    missing = sorted(required_ids - seen)
    if missing:
        fail("target_parent_model missing required ids: " + ", ".join(missing))


def validate_consumers(plan: dict[str, Any]) -> None:
    matrix = require_list(plan, "consumer_impact_matrix", "plan")
    seen: set[str] = set()
    for entry in matrix:
        if not isinstance(entry, dict):
            fail("consumer_impact_matrix entries must be objects")
        consumer = require_text(entry, "consumer", "consumer entry")
        seen.add(consumer)
        for key in ("risk", "required_apply_check"):
            require_text(entry, key, consumer)
        paths = require_list(entry, "paths", consumer)
        if not all(isinstance(item, str) and item.strip() for item in paths):
            fail(f"{consumer}: paths must be non-empty strings")
    missing = sorted(REQUIRED_CONSUMERS - seen)
    if missing:
        fail("consumer_impact_matrix missing consumers: " + ", ".join(missing))


def validate_apply_gate(plan: dict[str, Any]) -> None:
    gate = plan.get("future_apply_gate")
    if not isinstance(gate, dict):
        fail("future_apply_gate must be an object")
    if gate.get("physical_migration_allowed_in_this_task") is not False:
        fail("physical migration must be forbidden in this task")
    if gate.get("tracking_requirement") != "RASG-022":
        fail("future_apply_gate must track physical apply through RASG-022")
    if gate.get("closure_gap_guard_requirement") != "RASG-023":
        fail("future_apply_gate must track closure-gap hardening through RASG-023")
    requirements = require_list(gate, "required_before_apply", "future_apply_gate")
    joined = "\n".join(str(item) for item in requirements)
    for phrase in [
        "separate .dev-task.md apply tranche",
        "dry-run migration manifest",
        "alias and rollback plan",
        "Prism review",
        "package publish safety",
        "clean workspace E2E",
        "closeout receipt",
    ]:
        if phrase not in joined:
            fail(f"future_apply_gate missing required phrase: {phrase}")
    require_text(gate, "rollback_rule", "future_apply_gate")
    require_text(gate, "batching_rule", "future_apply_gate")


def validate_physical_migration_state(plan: dict[str, Any], root: Path) -> None:
    applied = plan.get("physical_migration_applied")
    status = plan.get("status")
    result = plan.get("physical_convergence_result")

    if applied is False:
        if result is not None:
            fail("physical_convergence_result must be absent until physical migration is applied")
        return
    if applied is not True:
        fail("physical_migration_applied must be a boolean")
    if status != APPLIED_STATUS:
        fail("physical migration can only be marked applied under the approved applied status")
    if not isinstance(result, dict):
        fail("physical_convergence_result must document the applied migration")
    if result.get("canonical_parent") != "assets":
        fail("physical_convergence_result must use assets as canonical parent")
    if result.get("moved_roots") != REQUIRED_MOVED_ROOTS:
        fail("physical_convergence_result moved_roots does not match approved move set")
    if result.get("compatibility_shims") != REQUIRED_COMPATIBILITY_SHIMS:
        fail("physical_convergence_result compatibility_shims does not match approved shim set")
    if not require_text(result, "task_id", "physical_convergence_result"):
        fail("physical_convergence_result missing task_id")
    for old_path, new_path in REQUIRED_MOVED_ROOTS.items():
        if not (root / old_path).exists():
            fail(f"compatibility path missing after migration: {old_path}")
        if not (root / new_path).exists():
            fail(f"canonical asset path missing after migration: {new_path}")


def validate_backlog(root: Path, plan: dict[str, Any]) -> None:
    backlog = load_json(root / "references/backlogs/redcap-architecture-smell-governance.json", "architecture smell backlog")
    requirement = plan.get("requirement")
    entries = [item for item in backlog.get("requirements", []) if isinstance(item, dict) and item.get("id") == requirement]
    if len(entries) != 1:
        fail(f"backlog must contain exactly one requirement for {requirement}")
    entry = entries[0]
    if entry.get("status") != "done":
        fail(f"{requirement} backlog status must be done when this plan is active")
    evidence = entry.get("evidence")
    if not isinstance(evidence, list) or "references/root-information-architecture-consolidation-plan.json" not in evidence:
        fail(f"{requirement} evidence must include root information architecture plan")
    follow_up = plan.get("follow_up_requirement")
    follow_entries = [item for item in backlog.get("requirements", []) if isinstance(item, dict) and item.get("id") == follow_up]
    if len(follow_entries) != 1:
        fail(f"backlog must contain exactly one follow-up requirement for {follow_up}")
    if follow_entries[0].get("status") not in {"planned", "in_progress", "done", "deferred"}:
        fail(f"{follow_up}: unsupported follow-up status")
    if follow_up not in (entry.get("follow_up_requirements") or []):
        fail(f"{requirement} must explicitly link follow-up requirement {follow_up}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    plan_path = Path(args.plan)
    if not plan_path.is_absolute():
        plan_path = root / plan_path
    plan = load_json(plan_path, "root information architecture plan")

    if plan.get("version") != 1:
        fail("plan version must be 1")
    if plan.get("plan_id") != "redcap-root-information-architecture-consolidation-plan":
        fail("unexpected plan_id")
    if plan.get("requirement") != "RASG-017":
        fail("plan must bind to RASG-017")
    if plan.get("follow_up_requirement") != "RASG-022":
        fail("plan must bind physical consolidation apply follow-up to RASG-022")
    if plan.get("prism_gap_follow_up") != "RASG-023":
        fail("plan must bind plan-only closure gap hardening to RASG-023")
    validate_physical_migration_state(plan, root)
    if plan.get("prism_review_required") is not True:
        fail("plan must require Prism review")
    require_text(plan, "status", "plan")
    require_text(plan, "scope", "plan")
    require_text(plan, "created_at", "plan")
    if not require_list(plan, "must_not_claim", "plan"):
        fail("plan must define must_not_claim")
    summary = plan.get("summary")
    if not isinstance(summary, dict):
        fail("summary must be an object")
    for key in ("problem", "solution", "effect"):
        require_text(summary, key, "summary")

    validate_inventory(plan, root)
    validate_target_model(plan)
    validate_consumers(plan)
    validate_apply_gate(plan)
    validate_backlog(root, plan)

    print("ROOT_INFORMATION_ARCHITECTURE_OK")
    print(f"inventory={len(plan.get('root_inventory', []))}")
    print(f"target_parents={len(plan.get('target_parent_model', []))}")
    print(f"consumers={len(plan.get('consumer_impact_matrix', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

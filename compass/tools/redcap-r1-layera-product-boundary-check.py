#!/usr/bin/env python3
# 用途：正式发布 R1 Layer A 产品边界预检；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PREFLIGHT = ROOT / "references/r1-layera-product-boundary-preflight.json"
UPSTREAM_MATRIX = ROOT / "references/formal-release-r1-root-group-disposition-preflight.json"
RUNTIME_MANIFEST = ROOT / "compass/tools/redcap-runtime-package-manifest.sh"
LOOM_ROOT = ROOT / "loom"
REQUIRED_BLOCKERS = {"internal-control-plane", "prism-layer-and-evidence", "internal-layer-a"}
REQUIRED_CATEGORIES = {
    "layera-dispatcher-contract",
    "layera-role-workflow-assets",
    "layera-runtime-tools",
    "layera-e2e-evidence",
    "layera-fixtures",
    "package-excluded-product-boundary",
}
REQUIRED_CONSUMERS = {
    "layera-state-machine-and-routing",
    "layera-role-prompts-and-handbooks",
    "layera-session-hooks-and-tools",
    "layera-e2e-and-validation-queue",
    "architecture-and-human-docs",
    "layerb-review-fallback-and-boundary-checks",
}
REQUIRED_INCLUDE_GATES = {
    "explicit Norven product scope decision",
    "compatibility tests",
    "host-entry review",
    "package-safety proof",
    "clean workspace E2E",
    "Prism review",
    "closeout receipt",
}
REQUIRED_EXCLUDE_GATES = {
    "explicit Norven product scope decision",
    "compatibility deprecation plan",
    "archaeology and alias preservation",
    "pending validations disposition",
    "host-entry review",
    "Prism review",
    "closeout receipt",
}
REQUIRED_MOVE_GATES = {
    "dry-run migration manifest",
    "consumer matrix review",
    "compatibility aliases",
    "rollback plan",
    "package-safety proof",
    "clean workspace E2E",
    "Prism review",
    "closeout receipt",
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-layera-product-boundary-check] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing {label}: {path.relative_to(ROOT)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be a JSON object")
    return payload


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{label} must be non-empty text")
    return value.strip()


def require_bool(value: Any, expected: bool, label: str) -> None:
    if value is not expected:
        fail(f"{label} must be {expected}")


def require_list(value: Any, label: str, *, min_len: int = 1) -> list[Any]:
    if not isinstance(value, list) or len(value) < min_len:
        fail(f"{label} must be a list with at least {min_len} item(s)")
    return value


def package_candidates() -> set[str]:
    if not RUNTIME_MANIFEST.is_file():
        fail("missing runtime package manifest generator")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        candidate_path = Path(handle.name)
    try:
        completed = subprocess.run(
            ["bash", str(RUNTIME_MANIFEST), "--output", str(candidate_path)],
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if completed.returncode != 0:
            sys.stdout.write(completed.stdout)
            fail("runtime package manifest generation failed")
        return {
            line.strip()
            for line in candidate_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    finally:
        try:
            candidate_path.unlink()
        except OSError:
            pass


def count_under(candidates: set[str], root: str) -> int:
    prefix = root.rstrip("/") + "/"
    return sum(1 for path in candidates if path == root or path.startswith(prefix))


def loom_inventory() -> dict[str, int]:
    if not LOOM_ROOT.is_dir():
        fail("missing loom root")
    files = sorted(path for path in LOOM_ROOT.rglob("*") if path.is_file())
    rels = [path.relative_to(ROOT).as_posix() for path in files]

    def under(part: str) -> int:
        prefix = f"loom/{part}/"
        return sum(1 for path in rels if path.startswith(prefix))

    total_lines = 0
    for path in files:
        try:
            total_lines += len(path.read_text(encoding="utf-8").splitlines())
        except UnicodeDecodeError:
            fail(f"loom inventory cannot read text file: {path.relative_to(ROOT)}")

    return {
        "total_files": len(rels),
        "shell_files": sum(1 for path in rels if path.endswith(".sh")),
        "markdown_files": sum(1 for path in rels if path.endswith(".md")),
        "yaml_files": sum(1 for path in rels if path.endswith(".yaml") or path.endswith(".yml")),
        "json_files": sum(1 for path in rels if path.endswith(".json")),
        "total_lines": total_lines,
        "dispatcher_files": under("dispatcher"),
        "roles_files": under("roles"),
        "tools_files": under("tools"),
        "test_reports_files": under("test-reports"),
        "fixtures_files": under("fixtures"),
    }


def validate_upstream(upstream: dict[str, Any]) -> None:
    groups = upstream.get("groups")
    if not isinstance(groups, list):
        fail("upstream R1 disposition groups must be a list")
    layera_group = None
    for group in groups:
        if isinstance(group, dict) and group.get("target_parent") == "internal-layer-a":
            layera_group = group
            break
    if not isinstance(layera_group, dict):
        fail("upstream matrix must include internal-layer-a")
    if layera_group.get("current_roots") != ["loom"]:
        fail("upstream internal-layer-a.current_roots must be ['loom']")
    if layera_group.get("disposition_id") != "release-blocker-until-resolved":
        fail("upstream internal-layer-a must remain release-blocker-until-resolved")
    require_bool(layera_group.get("is_release_blocker"), True, "upstream internal-layer-a.is_release_blocker")


def validate_surface(surface: dict[str, Any]) -> None:
    roots = require_list(surface.get("roots"), "current_surface_contract.roots", min_len=5)
    paths = {item.get("path") for item in roots if isinstance(item, dict)}
    expected_paths = {"loom/dispatcher", "loom/roles", "loom/tools", "loom/test-reports", "loom/fixtures"}
    if paths != expected_paths:
        fail(f"current_surface_contract.roots paths must be {sorted(expected_paths)}")
    for item in roots:
        if not isinstance(item, dict):
            fail("current_surface_contract.roots entries must be objects")
        require_text(item.get("role"), f"{item.get('path')}.role")
        if item.get("package_candidate_count") != 0:
            fail(f"{item.get('path')}.package_candidate_count must be 0")
        require_text(item.get("current_contract"), f"{item.get('path')}.current_contract")
        require_text(item.get("future_target"), f"{item.get('path')}.future_target")

    categories = require_list(surface.get("candidate_categories"), "current_surface_contract.candidate_categories", min_len=6)
    ids = {item.get("id") for item in categories if isinstance(item, dict)}
    missing = REQUIRED_CATEGORIES - ids
    if missing:
        fail(f"candidate_categories missing {sorted(missing)}")


def validate_consumers(consumers: list[Any]) -> None:
    if len(consumers) < 6:
        fail("consumer_matrix must include at least six major consumers")
    ids: set[str] = set()
    for item in consumers:
        if not isinstance(item, dict):
            fail("consumer_matrix entries must be objects")
        consumer_id = require_text(item.get("consumer_id"), "consumer_matrix.consumer_id")
        if consumer_id in ids:
            fail(f"duplicate consumer_id: {consumer_id}")
        ids.add(consumer_id)
        require_list(item.get("consumer_paths"), f"{consumer_id}.consumer_paths")
        require_list(item.get("depends_on"), f"{consumer_id}.depends_on")
        require_text(item.get("boundary_risk"), f"{consumer_id}.boundary_risk")
        require_list(item.get("required_before_include_or_move"), f"{consumer_id}.required_before_include_or_move")
    missing = REQUIRED_CONSUMERS - ids
    if missing:
        fail(f"consumer_matrix missing {sorted(missing)}")


def validate_gate(gate: dict[str, Any]) -> None:
    require_bool(gate.get("product_scope_decision_allowed_now"), False, "future_decision_gate.product_scope_decision_allowed_now")
    require_bool(gate.get("physical_move_allowed_now"), False, "future_decision_gate.physical_move_allowed_now")
    require_bool(gate.get("delete_or_retire_allowed_now"), False, "future_decision_gate.delete_or_retire_allowed_now")
    include = set(require_list(gate.get("required_before_include_in_public_product"), "future_decision_gate.required_before_include_in_public_product"))
    exclude = set(require_list(gate.get("required_before_exclude_or_retire"), "future_decision_gate.required_before_exclude_or_retire"))
    move = set(require_list(gate.get("required_before_physical_move"), "future_decision_gate.required_before_physical_move"))
    if not REQUIRED_INCLUDE_GATES.issubset(include):
        fail(f"future_decision_gate.required_before_include_in_public_product missing {sorted(REQUIRED_INCLUDE_GATES - include)}")
    if not REQUIRED_EXCLUDE_GATES.issubset(exclude):
        fail(f"future_decision_gate.required_before_exclude_or_retire missing {sorted(REQUIRED_EXCLUDE_GATES - exclude)}")
    if not REQUIRED_MOVE_GATES.issubset(move):
        fail(f"future_decision_gate.required_before_physical_move missing {sorted(REQUIRED_MOVE_GATES - move)}")
    require_text(gate.get("alias_strategy"), "future_decision_gate.alias_strategy")
    require_text(gate.get("rollback_strategy"), "future_decision_gate.rollback_strategy")


def validate(args: argparse.Namespace) -> dict[str, Any]:
    preflight = load_json(args.preflight, "R1 Layer A product boundary preflight")
    upstream = load_json(UPSTREAM_MATRIX, "R1 disposition matrix")
    candidates = package_candidates()
    inventory = loom_inventory()

    if preflight.get("preflight_id") != "redcap-r1-layera-product-boundary-preflight":
        fail("preflight_id mismatch")
    if preflight.get("status") != "preflight-analysis-only-layera-boundary-still-blocked":
        fail("status must remain preflight-analysis-only-layera-boundary-still-blocked")

    boundary = preflight.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    for key in [
        "is_layera_public_product_decided",
        "is_layera_included_in_public_release",
        "is_layera_retired_or_removed",
        "is_layera_physically_moved",
        "is_internal_layera_release_safe",
        "is_r1_closed",
        "is_public_release_ready",
        "physical_moves_performed",
        "release_switches_changed",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")
    require_list(boundary.get("forbidden_claims"), "claim_boundary.forbidden_claims", min_len=6)

    validate_upstream(upstream)

    upstream_blocker = preflight.get("upstream_blocker")
    if not isinstance(upstream_blocker, dict):
        fail("upstream_blocker must be an object")
    if upstream_blocker.get("target_parent") != "internal-layer-a":
        fail("upstream_blocker.target_parent must be internal-layer-a")
    if upstream_blocker.get("current_roots") != ["loom"]:
        fail("upstream_blocker.current_roots must be ['loom']")
    if upstream_blocker.get("upstream_disposition_id") != "release-blocker-until-resolved":
        fail("upstream_disposition_id must remain release-blocker-until-resolved")
    require_bool(upstream_blocker.get("this_preflight_resolves_blocker"), False, "upstream_blocker.this_preflight_resolves_blocker")

    snapshot = preflight.get("package_candidate_snapshot")
    if not isinstance(snapshot, dict):
        fail("package_candidate_snapshot must be an object")
    if snapshot.get("candidate_count") != len(candidates):
        fail(f"package_candidate_snapshot.candidate_count must be {len(candidates)}")
    if snapshot.get("loom_candidate_count") != count_under(candidates, "loom"):
        fail(f"package_candidate_snapshot.loom_candidate_count must be {count_under(candidates, 'loom')}")
    if snapshot.get("loom_candidate_count") != 0:
        fail("loom must remain absent from package candidates")

    recorded_inventory = preflight.get("loom_inventory_snapshot")
    if not isinstance(recorded_inventory, dict):
        fail("loom_inventory_snapshot must be an object")
    for key, expected in inventory.items():
        if recorded_inventory.get(key) != expected:
            fail(f"loom_inventory_snapshot.{key} must be {expected}")

    surface = preflight.get("current_surface_contract")
    if not isinstance(surface, dict):
        fail("current_surface_contract must be an object")
    validate_surface(surface)

    validate_consumers(require_list(preflight.get("consumer_matrix"), "consumer_matrix", min_len=6))

    gate = preflight.get("future_decision_gate")
    if not isinstance(gate, dict):
        fail("future_decision_gate must be an object")
    validate_gate(gate)

    result = preflight.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    if result.get("target_parent") != "internal-layer-a":
        fail("result.target_parent must be internal-layer-a")
    require_bool(result.get("this_preflight_completed"), True, "result.this_preflight_completed")
    if result.get("release_blocker_status") != "still-blocking-release-until-human-product-scope-decision-or-future-boundary-resolution":
        fail("result.release_blocker_status must keep internal-layer-a blocking")
    blockers = set(result.get("remaining_release_blockers_after_this_preflight", []))
    if blockers != REQUIRED_BLOCKERS:
        fail("result.remaining_release_blockers_after_this_preflight must keep all three release blockers")

    return {"candidate_count": len(candidates), "loom_candidate_count": count_under(candidates, "loom"), **inventory}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", type=Path, default=DEFAULT_PREFLIGHT)
    args = parser.parse_args()
    summary = validate(args)
    print(
        "R1_LAYERA_PRODUCT_BOUNDARY_PREFLIGHT_OK "
        f"candidates={summary['candidate_count']} "
        f"loom_candidates={summary['loom_candidate_count']} "
        f"loom_files={summary['total_files']} "
        "release_blocker_status=still-blocking"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

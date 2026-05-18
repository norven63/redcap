#!/usr/bin/env python3
# 用途：正式发布 R1 控制面契约拆分预检；详细职责见文件查阅字典。
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
DEFAULT_PREFLIGHT = ROOT / "references/r1-control-plane-contract-split-preflight.json"
UPSTREAM_MATRIX = ROOT / "references/formal-release-r1-root-group-disposition-preflight.json"
RUNTIME_MANIFEST = ROOT / "compass/tools/redcap-runtime-package-manifest.sh"
REQUIRED_BLOCKERS = {
    "internal-control-plane",
    "prism-layer-and-evidence",
    "internal-layer-a",
}
REQUIRED_FUTURE_GATES = {
    "dry-run migration manifest",
    "exact consumer matrix",
    "alias and rollback plan",
    "package-safety proof",
    "clean workspace E2E",
    "Prism review",
    "closeout receipt",
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-control-plane-contract-split-check] {message}")


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


def count_under(candidates: set[str], roots: list[str]) -> int:
    total = 0
    for path in candidates:
        for root in roots:
            prefix = root.rstrip("/") + "/"
            if path == root or path.startswith(prefix):
                total += 1
                break
    return total


def expected_snapshot(candidates: set[str]) -> dict[str, int]:
    return {
        "candidate_count": len(candidates),
        "control_plane_candidate_count": count_under(candidates, ["compass", "references"]),
        "compass": count_under(candidates, ["compass"]),
        "references": count_under(candidates, ["references"]),
        "compass_tools_shell": sum(1 for path in candidates if path.startswith("compass/tools/") and path.endswith(".sh")),
        "compass_tools_python": sum(1 for path in candidates if path.startswith("compass/tools/") and path.endswith(".py")),
        "references_json": sum(1 for path in candidates if path.startswith("references/") and path.endswith(".json")),
        "references_markdown": sum(1 for path in candidates if path.startswith("references/") and path.endswith(".md")),
    }


def validate_upstream(upstream: dict[str, Any]) -> None:
    groups = upstream.get("groups")
    if not isinstance(groups, list):
        fail("upstream R1 disposition groups must be a list")
    control = None
    for group in groups:
        if isinstance(group, dict) and group.get("target_parent") == "internal-control-plane":
            control = group
            break
    if not isinstance(control, dict):
        fail("upstream matrix must include internal-control-plane")
    if control.get("disposition_id") != "release-blocker-until-resolved":
        fail("upstream internal-control-plane must remain release-blocker-until-resolved")
    require_bool(control.get("is_release_blocker"), True, "upstream internal-control-plane.is_release_blocker")


def validate_execution_plan(plan: dict[str, Any]) -> None:
    if plan.get("selected_next") != "internal-control-plane":
        fail("r1_blocker_execution_plan.selected_next must be internal-control-plane")
    require_text(plan.get("selection_reason"), "r1_blocker_execution_plan.selection_reason")
    ordered = require_list(plan.get("ordered_blockers"), "r1_blocker_execution_plan.ordered_blockers", min_len=3)
    seen: set[str] = set()
    for item in ordered:
        if not isinstance(item, dict):
            fail("ordered_blockers entries must be objects")
        target = require_text(item.get("target_parent"), "ordered_blockers.target_parent")
        seen.add(target)
        if not isinstance(item.get("order"), int):
            fail(f"{target}.order must be an integer")
        require_text(item.get("current_task_action"), f"{target}.current_task_action")
        require_text(item.get("autonomous_scope"), f"{target}.autonomous_scope")
        require_text(item.get("human_boundary"), f"{target}.human_boundary")
    if seen != REQUIRED_BLOCKERS:
        fail(f"ordered_blockers must exactly cover {sorted(REQUIRED_BLOCKERS)}")


def validate_consumers(consumers: list[Any]) -> None:
    if len(consumers) < 5:
        fail("consumer_matrix must include at least five major consumers")
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
        require_text(item.get("split_risk"), f"{consumer_id}.split_risk")
        require_list(item.get("required_before_move"), f"{consumer_id}.required_before_move")


def validate(args: argparse.Namespace) -> dict[str, Any]:
    preflight = load_json(args.preflight, "R1 control-plane preflight")
    upstream = load_json(UPSTREAM_MATRIX, "R1 disposition matrix")
    candidates = package_candidates()

    if preflight.get("preflight_id") != "redcap-r1-control-plane-contract-split-preflight":
        fail("preflight_id mismatch")
    if preflight.get("status") != "preflight-analysis-only-control-plane-still-blocked":
        fail("status must remain preflight-analysis-only-control-plane-still-blocked")

    boundary = preflight.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    for key in [
        "is_control_plane_physically_split",
        "is_internal_control_plane_release_safe",
        "is_r1_closed",
        "is_public_release_ready",
        "physical_moves_performed",
        "release_switches_changed",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")
    require_list(boundary.get("forbidden_claims"), "claim_boundary.forbidden_claims", min_len=5)

    validate_upstream(upstream)

    upstream_blocker = preflight.get("upstream_blocker")
    if not isinstance(upstream_blocker, dict):
        fail("upstream_blocker must be an object")
    if upstream_blocker.get("target_parent") != "internal-control-plane":
        fail("upstream_blocker.target_parent must be internal-control-plane")
    if upstream_blocker.get("current_roots") != ["compass", "references"]:
        fail("upstream_blocker.current_roots must be ['compass', 'references']")
    if upstream_blocker.get("upstream_disposition_id") != "release-blocker-until-resolved":
        fail("upstream_disposition_id must remain release-blocker-until-resolved")
    require_bool(upstream_blocker.get("this_preflight_resolves_blocker"), False, "upstream_blocker.this_preflight_resolves_blocker")

    plan = preflight.get("r1_blocker_execution_plan")
    if not isinstance(plan, dict):
        fail("r1_blocker_execution_plan must be an object")
    validate_execution_plan(plan)

    snapshot = preflight.get("package_candidate_snapshot")
    if not isinstance(snapshot, dict):
        fail("package_candidate_snapshot must be an object")
    for key, value in expected_snapshot(candidates).items():
        if snapshot.get(key) != value:
            fail(f"package_candidate_snapshot.{key} stale: matrix={snapshot.get(key)} actual={value}")

    surface = preflight.get("current_surface_contract")
    if not isinstance(surface, dict):
        fail("current_surface_contract must be an object")
    roots = require_list(surface.get("roots"), "current_surface_contract.roots", min_len=2)
    root_paths = {item.get("path") for item in roots if isinstance(item, dict)}
    if root_paths != {"compass", "references"}:
        fail("current_surface_contract.roots must cover compass and references")
    categories = require_list(surface.get("candidate_categories"), "current_surface_contract.candidate_categories", min_len=3)
    category_ids = {item.get("id") for item in categories if isinstance(item, dict)}
    for required in ["runtime-public-support", "maintainer-control-plane", "policy-reference-contract"]:
        if required not in category_ids:
            fail(f"candidate_categories missing {required}")

    validate_consumers(require_list(preflight.get("consumer_matrix"), "consumer_matrix", min_len=5))

    gate = preflight.get("future_split_gate")
    if not isinstance(gate, dict):
        fail("future_split_gate must be an object")
    require_bool(gate.get("physical_move_allowed_now"), False, "future_split_gate.physical_move_allowed_now")
    required_gate = {
        require_text(item, "future gate item")
        for item in require_list(gate.get("required_before_physical_move"), "future_split_gate.required_before_physical_move", min_len=7)
    }
    missing = sorted(REQUIRED_FUTURE_GATES - required_gate)
    if missing:
        fail("future_split_gate missing: " + ", ".join(missing))
    require_list(gate.get("required_before_release_ready_claim"), "future_split_gate.required_before_release_ready_claim", min_len=3)
    require_text(gate.get("alias_strategy"), "future_split_gate.alias_strategy")
    require_text(gate.get("rollback_strategy"), "future_split_gate.rollback_strategy")

    result = preflight.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    if result.get("release_blocker_status") != "still-blocking-release-until-future-physical-split-or-contract-resolution":
        fail("result.release_blocker_status must keep control plane blocking")
    require_bool(result.get("this_preflight_completed"), True, "result.this_preflight_completed")
    blockers = set(require_list(result.get("remaining_release_blockers_after_this_preflight"), "result.remaining_release_blockers_after_this_preflight", min_len=3))
    if blockers != REQUIRED_BLOCKERS:
        fail("remaining_release_blockers_after_this_preflight must keep all three blockers")

    return {
        "candidate_count": len(candidates),
        "control_plane_count": expected_snapshot(candidates)["control_plane_candidate_count"],
        "consumers": len(preflight["consumer_matrix"]),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", default=str(DEFAULT_PREFLIGHT))
    args = parser.parse_args(argv)
    path = Path(args.preflight)
    if not path.is_absolute():
        path = ROOT / path
    args.preflight = path
    return args


def main() -> int:
    result = validate(parse_args(sys.argv[1:]))
    print(
        "R1_CONTROL_PLANE_CONTRACT_SPLIT_PREFLIGHT_OK "
        f"candidate_count={result['candidate_count']} "
        f"control_plane_candidates={result['control_plane_count']} "
        f"consumers={result['consumers']} "
        "release_blocker_status=still-blocking"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

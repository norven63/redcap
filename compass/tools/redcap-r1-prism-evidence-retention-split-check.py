#!/usr/bin/env python3
# 用途：正式发布 R1 Prism 证据保留拆分预检；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PREFLIGHT = ROOT / "references/r1-prism-evidence-retention-split-preflight.json"
UPSTREAM_MATRIX = ROOT / "references/formal-release-r1-root-group-disposition-preflight.json"
RUNTIME_MANIFEST = ROOT / "compass/tools/redcap-runtime-package-manifest.sh"
RUNS_LIFECYCLE = ROOT / "prism/tools/prism-runs-lifecycle.sh"
REQUIRED_BLOCKERS = {
    "internal-control-plane",
    "prism-layer-and-evidence",
    "internal-layer-a",
}
REQUIRED_FUTURE_MOVE_GATES = {
    "evidence retention policy",
    "report index migration",
    "provider routing review",
    "compatibility aliases",
    "package-safety proof",
    "clean workspace E2E",
    "Prism self-review",
    "closeout receipt",
}
REQUIRED_CLEANUP_GATES = {
    "inventory dry-run",
    "proof that targets are inactive and unreferenced",
    "explicit Norven approval for any --apply cleanup",
    "rollback or preservation plan",
    "post-cleanup archive check",
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-prism-evidence-retention-split-check] {message}")


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
        "prism_candidate_count": count_under(candidates, ["prism"]),
        "prism_tools_candidate_count": count_under(candidates, ["prism/tools"]),
        "prism_tools_shell": sum(1 for path in candidates if path.startswith("prism/tools/") and path.endswith(".sh")),
        "prism_tools_python": sum(1 for path in candidates if path.startswith("prism/tools/") and path.endswith(".py")),
        "prism_readme": 1 if "prism/README.md" in candidates else 0,
        "prism_reports": count_under(candidates, ["prism/reports"]),
        "prism_runs": count_under(candidates, ["prism/runs"]),
    }


def runs_lifecycle_summary() -> dict[str, int]:
    if not RUNS_LIFECYCLE.is_file():
        fail("missing Prism runs lifecycle checker")
    completed = subprocess.run(
        ["bash", str(RUNS_LIFECYCLE), "summary"],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        sys.stdout.write(completed.stdout)
        fail("Prism runs lifecycle summary failed")

    summary: dict[str, int] = {}
    for raw in completed.stdout.splitlines():
        for key, value in re.findall(r"([A-Za-z0-9_-]+)=([0-9]+)", raw):
            summary[key] = int(value)
    for key in ["total", "formal-run", "named-local-evidence", "infra-locks", "purgeable_acceptance", "pruneable_local"]:
        if key not in summary:
            fail(f"Prism runs lifecycle summary missing {key}")

    if os.environ.get("REDCAP_ACCEPTANCE_RUNNING") == "1":
        acceptance_count = summary.get("acceptance-fixture", 0)
        summary["total"] = max(0, summary.get("total", 0) - acceptance_count)
        summary["purgeable_acceptance"] = 0

    check = subprocess.run(
        ["bash", str(RUNS_LIFECYCLE), "check"],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if check.returncode != 0:
        sys.stdout.write(check.stdout)
        fail("Prism runs lifecycle check failed")
    return summary


def validate_upstream(upstream: dict[str, Any]) -> None:
    groups = upstream.get("groups")
    if not isinstance(groups, list):
        fail("upstream R1 disposition groups must be a list")
    prism_group = None
    for group in groups:
        if isinstance(group, dict) and group.get("target_parent") == "prism-layer-and-evidence":
            prism_group = group
            break
    if not isinstance(prism_group, dict):
        fail("upstream matrix must include prism-layer-and-evidence")
    if prism_group.get("current_roots") != ["prism"]:
        fail("upstream prism-layer-and-evidence.current_roots must be ['prism']")
    if prism_group.get("disposition_id") != "release-blocker-until-resolved":
        fail("upstream prism-layer-and-evidence must remain release-blocker-until-resolved")
    require_bool(prism_group.get("is_release_blocker"), True, "upstream prism-layer-and-evidence.is_release_blocker")


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
    for required in [
        "runtime-package-manifest",
        "prism-acceptance-and-closeout",
        "archive-and-report-checks",
        "provider-routing-and-availability",
        "runs-lifecycle-status-surface",
    ]:
        if required not in ids:
            fail(f"consumer_matrix missing {required}")


def validate(args: argparse.Namespace) -> dict[str, Any]:
    preflight = load_json(args.preflight, "R1 Prism evidence retention split preflight")
    upstream = load_json(UPSTREAM_MATRIX, "R1 disposition matrix")
    candidates = package_candidates()
    lifecycle = runs_lifecycle_summary()

    if preflight.get("preflight_id") != "redcap-r1-prism-evidence-retention-split-preflight":
        fail("preflight_id mismatch")
    if preflight.get("status") != "preflight-analysis-only-prism-layer-still-blocked":
        fail("status must remain preflight-analysis-only-prism-layer-still-blocked")

    boundary = preflight.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    for key in [
        "is_prism_layer_physically_split",
        "is_prism_evidence_physically_cleaned",
        "is_prism_layer_release_safe",
        "is_r1_closed",
        "is_public_release_ready",
        "physical_moves_performed",
        "evidence_deletion_performed",
        "release_switches_changed",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")
    require_list(boundary.get("forbidden_claims"), "claim_boundary.forbidden_claims", min_len=6)

    validate_upstream(upstream)

    upstream_blocker = preflight.get("upstream_blocker")
    if not isinstance(upstream_blocker, dict):
        fail("upstream_blocker must be an object")
    if upstream_blocker.get("target_parent") != "prism-layer-and-evidence":
        fail("upstream_blocker.target_parent must be prism-layer-and-evidence")
    if upstream_blocker.get("current_roots") != ["prism"]:
        fail("upstream_blocker.current_roots must be ['prism']")
    if upstream_blocker.get("upstream_disposition_id") != "release-blocker-until-resolved":
        fail("upstream_disposition_id must remain release-blocker-until-resolved")
    require_bool(upstream_blocker.get("this_preflight_resolves_blocker"), False, "upstream_blocker.this_preflight_resolves_blocker")

    snapshot = preflight.get("package_candidate_snapshot")
    if not isinstance(snapshot, dict):
        fail("package_candidate_snapshot must be an object")
    for key, value in expected_snapshot(candidates).items():
        if snapshot.get(key) != value:
            fail(f"package_candidate_snapshot.{key} stale: matrix={snapshot.get(key)} actual={value}")
    if snapshot.get("prism_reports") != 0 or snapshot.get("prism_runs") != 0:
        fail("prism/reports and prism/runs must stay absent from package candidates")

    lifecycle_snapshot = preflight.get("evidence_lifecycle_snapshot")
    if not isinstance(lifecycle_snapshot, dict):
        fail("evidence_lifecycle_snapshot must be an object")
    require_bool(lifecycle_snapshot.get("cleanup_apply_allowed_now"), False, "evidence_lifecycle_snapshot.cleanup_apply_allowed_now")
    require_bool(lifecycle_snapshot.get("prune_local_apply_allowed_now"), False, "evidence_lifecycle_snapshot.prune_local_apply_allowed_now")
    if lifecycle["total"] < int(lifecycle_snapshot.get("minimum_total_runs", 0)):
        fail("Prism runs total fell below recorded minimum without a cleanup receipt")
    if lifecycle["formal-run"] < int(lifecycle_snapshot.get("minimum_formal_runs", 0)):
        fail("Prism formal run count fell below recorded minimum without a cleanup receipt")
    if lifecycle["purgeable_acceptance"] != int(lifecycle_snapshot.get("purgeable_acceptance_required", 0)):
        fail("purgeable acceptance fixtures must remain at the recorded required value")
    require_text(lifecycle_snapshot.get("dynamic_check_rule"), "evidence_lifecycle_snapshot.dynamic_check_rule")

    surface = preflight.get("current_surface_contract")
    if not isinstance(surface, dict):
        fail("current_surface_contract must be an object")
    roots = require_list(surface.get("roots"), "current_surface_contract.roots", min_len=4)
    root_paths = {item.get("path") for item in roots if isinstance(item, dict)}
    if root_paths != {"prism/tools", "prism/README.md", "prism/reports", "prism/runs"}:
        fail("current_surface_contract.roots must cover tools, README, reports and runs")
    categories = require_list(surface.get("candidate_categories"), "current_surface_contract.candidate_categories", min_len=4)
    category_ids = {item.get("id") for item in categories if isinstance(item, dict)}
    for required in ["package-visible-prism-tools", "tracked-report-archive", "run-scoped-local-evidence", "provider-routing-contract"]:
        if required not in category_ids:
            fail(f"candidate_categories missing {required}")

    validate_consumers(require_list(preflight.get("consumer_matrix"), "consumer_matrix", min_len=5))

    gate = preflight.get("future_split_gate")
    if not isinstance(gate, dict):
        fail("future_split_gate must be an object")
    require_bool(gate.get("physical_move_allowed_now"), False, "future_split_gate.physical_move_allowed_now")
    require_bool(gate.get("evidence_cleanup_allowed_now"), False, "future_split_gate.evidence_cleanup_allowed_now")
    move_gates = {
        require_text(item, "future move gate item")
        for item in require_list(gate.get("required_before_physical_move"), "future_split_gate.required_before_physical_move", min_len=8)
    }
    missing_move = sorted(REQUIRED_FUTURE_MOVE_GATES - move_gates)
    if missing_move:
        fail("future_split_gate missing move gates: " + ", ".join(missing_move))
    cleanup_gates = {
        require_text(item, "future cleanup gate item")
        for item in require_list(gate.get("required_before_evidence_cleanup"), "future_split_gate.required_before_evidence_cleanup", min_len=5)
    }
    missing_cleanup = sorted(REQUIRED_CLEANUP_GATES - cleanup_gates)
    if missing_cleanup:
        fail("future_split_gate missing cleanup gates: " + ", ".join(missing_cleanup))
    require_list(gate.get("required_before_release_ready_claim"), "future_split_gate.required_before_release_ready_claim", min_len=4)
    require_text(gate.get("alias_strategy"), "future_split_gate.alias_strategy")
    require_text(gate.get("rollback_strategy"), "future_split_gate.rollback_strategy")

    result = preflight.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    if result.get("release_blocker_status") != "still-blocking-release-until-future-evidence-retention-split-or-contract-resolution":
        fail("result.release_blocker_status must keep Prism layer blocking")
    require_bool(result.get("this_preflight_completed"), True, "result.this_preflight_completed")
    blockers = set(require_list(result.get("remaining_release_blockers_after_this_preflight"), "result.remaining_release_blockers_after_this_preflight", min_len=3))
    if blockers != REQUIRED_BLOCKERS:
        fail("remaining_release_blockers_after_this_preflight must keep all three blockers")

    return {
        "candidate_count": len(candidates),
        "prism_count": expected_snapshot(candidates)["prism_candidate_count"],
        "runs_total": lifecycle["total"],
        "formal_runs": lifecycle["formal-run"],
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
        "R1_PRISM_EVIDENCE_RETENTION_SPLIT_PREFLIGHT_OK "
        f"candidate_count={result['candidate_count']} "
        f"prism_candidates={result['prism_count']} "
        f"runs_total={result['runs_total']} "
        f"formal_runs={result['formal_runs']} "
        f"consumers={result['consumers']} "
        "release_blocker_status=still-blocking"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

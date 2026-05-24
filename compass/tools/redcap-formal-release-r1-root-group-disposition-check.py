#!/usr/bin/env python3
# 用途：正式发布 R1 延期根目录处置预检脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MATRIX = ROOT / "references/formal-release-r1-root-group-disposition-preflight.json"
GATE = ROOT / "references/historical-asset-physical-cleanup-release-gate.json"
DEFERRAL = ROOT / "references/root-ia-remaining-root-groups-deferral.json"
RUNTIME_MANIFEST = ROOT / "compass/tools/redcap-runtime-package-manifest.sh"
NPMIGNORE = ROOT / ".npmignore"
WORKSPACE_STATE_PACKAGE_ROOTS = [".dev-task.md", ".env", ".tmp", "prompt.txt", "cli_" + "console.md"]


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-formal-release-r1-root-group-disposition-check] {message}")


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


def validate_workspace_exclusion(group: dict[str, Any], candidates: set[str]) -> None:
    roots = [require_text(item, "workspace current root") for item in require_list(group.get("current_roots"), "workspace current_roots")]
    present = sorted(root for root in roots if root in candidates or any(path.startswith(root.rstrip("/") + "/") for path in candidates))
    if present:
        fail("workspace-state roots must not appear in package candidates: " + ", ".join(present))
    if group.get("package_candidate_count") != 0:
        fail("workspace-state package_candidate_count must be 0")
    proof = group.get("package_exclusion_proof")
    if not isinstance(proof, dict):
        fail("workspace-state must include package_exclusion_proof")
    require_bool(proof.get("candidate_absence_required"), True, "workspace-state.package_exclusion_proof.candidate_absence_required")
    required_entries = [
        require_text(item, "npmignore required entry")
        for item in require_list(proof.get("npmignore_required_entries"), "workspace-state npmignore_required_entries", min_len=5)
    ]
    text = NPMIGNORE.read_text(encoding="utf-8") if NPMIGNORE.is_file() else ""
    missing = [entry for entry in required_entries if entry not in text]
    if missing:
        fail(".npmignore missing workspace-state exclusion entries: " + ", ".join(missing))


def parse_args(argv: list[str]) -> Path:
    matrix_path = DEFAULT_MATRIX
    index = 0
    while index < len(argv):
        option = argv[index]
        if option != "--matrix":
            fail(f"unsupported argument: {option}")
        if index + 1 >= len(argv):
            fail("--matrix requires a path")
        matrix_path = Path(argv[index + 1])
        if not matrix_path.is_absolute():
            matrix_path = ROOT / matrix_path
        index += 2
    return matrix_path


def validate(matrix_path: Path) -> dict[str, Any]:
    matrix = load_json(matrix_path, "R1 disposition matrix")
    gate = load_json(GATE, "historical cleanup release gate")
    deferral = load_json(DEFERRAL, "root IA deferral receipt")
    candidates = package_candidates()

    if matrix.get("version") != 1:
        fail("matrix version must be 1")
    if matrix.get("matrix_id") != "redcap-formal-release-r1-root-group-disposition-preflight":
        fail("matrix_id mismatch")
    if matrix.get("status") != "preflight-analysis-only-release-still-blocked":
        fail("matrix status must remain preflight-analysis-only-release-still-blocked")
    boundary = matrix.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    for key in [
        "is_r1_closed",
        "is_public_release_ready",
        "release_gate_closed",
        "physical_moves_performed",
        "release_switches_changed",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")
    forbidden_blob = "\n".join(str(item).lower() for item in require_list(boundary.get("forbidden_claims"), "claim_boundary.forbidden_claims", min_len=4))
    for term in ["r1", "package exclusion", "public-release-ready", "registry"]:
        if term not in forbidden_blob:
            fail(f"forbidden_claims missing concept: {term}")

    gate_dispositions = {
        require_text(item.get("id"), "gate disposition id")
        for item in require_list(gate.get("required_release_dispositions"), "gate.required_release_dispositions", min_len=4)
        if isinstance(item, dict)
    }
    if set(matrix.get("allowed_disposition_ids", [])) != gate_dispositions:
        fail("matrix allowed_disposition_ids must exactly mirror release gate dispositions")

    deferred_groups = {
        require_text(item.get("target_parent"), "deferral target_parent"): item
        for item in require_list(deferral.get("deferred_root_groups"), "deferral.deferred_root_groups", min_len=4)
        if isinstance(item, dict)
    }
    groups = require_list(matrix.get("groups"), "matrix.groups", min_len=4)
    group_map: dict[str, dict[str, Any]] = {}
    for item in groups:
        if not isinstance(item, dict):
            fail("matrix.groups entries must be objects")
        target = require_text(item.get("target_parent"), "group.target_parent")
        if target in group_map:
            fail(f"duplicate group target_parent: {target}")
        group_map[target] = item
    if set(group_map) != set(deferred_groups):
        fail("matrix groups must exactly cover deferral receipt groups")

    remaining = set(require_list(matrix.get("remaining_release_blockers"), "remaining_release_blockers", min_len=1))
    resolved = set(require_list(matrix.get("resolved_nonhistorical_local_state"), "resolved_nonhistorical_local_state", min_len=1))
    if remaining != {"internal-control-plane", "prism-layer-and-evidence", "internal-layer-a"}:
        fail("remaining_release_blockers must list the three unresolved historical/product groups")
    if resolved != {"workspace-state"}:
        fail("resolved_nonhistorical_local_state must contain only workspace-state")

    for target, item in group_map.items():
        disposition = require_text(item.get("disposition_id"), f"{target}.disposition_id")
        if disposition not in gate_dispositions:
            fail(f"{target} uses unsupported disposition_id: {disposition}")
        roots = [require_text(root, f"{target}.current_roots") for root in require_list(item.get("current_roots"), f"{target}.current_roots")]
        if roots != deferred_groups[target].get("current_roots"):
            fail(f"{target}.current_roots must mirror deferral receipt")
        actual_count = count_under(candidates, roots)
        if item.get("package_candidate_count") != actual_count:
            fail(f"{target}.package_candidate_count stale: matrix={item.get('package_candidate_count')} actual={actual_count}")
        require_list(item.get("policy_references"), f"{target}.policy_references", min_len=2)
        tranche = item.get("next_required_tranche")
        if not isinstance(tranche, dict):
            fail(f"{target} must include next_required_tranche")
        require_text(tranche.get("id"), f"{target}.next_required_tranche.id")
        require_text(tranche.get("trigger"), f"{target}.next_required_tranche.trigger")
        require_list(tranche.get("required_gate"), f"{target}.next_required_tranche.required_gate", min_len=3)
        if target == "workspace-state":
            if disposition != "workspace-local-excluded-nonhistorical":
                fail("workspace-state must use workspace-local-excluded-nonhistorical")
            require_bool(item.get("is_release_blocker"), False, "workspace-state.is_release_blocker")
            validate_workspace_exclusion(item, candidates)
        else:
            if disposition != "release-blocker-until-resolved":
                fail(f"{target} must remain release-blocker-until-resolved in this preflight")
            require_bool(item.get("is_release_blocker"), True, f"{target}.is_release_blocker")
            if target not in remaining:
                fail(f"{target} must be listed in remaining_release_blockers")

    snapshot = matrix.get("package_candidate_snapshot")
    if not isinstance(snapshot, dict):
        fail("package_candidate_snapshot must be an object")
    expected_snapshot = {
        "candidate_count": len(candidates),
        "compass": count_under(candidates, ["compass"]),
        "references": count_under(candidates, ["references"]),
        "assets_references": count_under(candidates, ["assets/references"]),
        "prism": count_under(candidates, ["prism"]),
        "loom": count_under(candidates, ["loom"]),
        "workspace_state": count_under(candidates, WORKSPACE_STATE_PACKAGE_ROOTS),
    }
    for key, value in expected_snapshot.items():
        if snapshot.get(key) != value:
            fail(f"package_candidate_snapshot.{key} stale: matrix={snapshot.get(key)} actual={value}")

    return {
        "candidate_count": len(candidates),
        "blockers": len(remaining),
        "resolved_local_state": len(resolved),
    }


def main() -> int:
    result = validate(parse_args(sys.argv[1:]))
    print(
        "FORMAL_RELEASE_R1_ROOT_GROUP_DISPOSITION_OK "
        f"candidate_count={result['candidate_count']} "
        f"remaining_blockers={result['blockers']} "
        f"resolved_local_state={result['resolved_local_state']} "
        "release_gate_closed=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

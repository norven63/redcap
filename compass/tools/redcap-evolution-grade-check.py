#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter


REQUIRED_NODES = {
    "current-task-ledger",
    "lessons-sedimentation",
    "identity-sedimentation",
    "prism-provider-evidence",
    "legacy-asset-lifecycle",
    "live-response-quality",
    "token-structural-governance",
    "skill-lifecycle-distribution",
    "closeout-self-proof",
}

ALLOWED_REQUIREMENTS = {f"R{i}" for i in range(0, 9)}
ALLOWED_STATUSES = {"meets", "degraded", "host-limited", "manual-only"}
WEAK_LEVELS = {"weak"}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-evolution-grade-check] {message}")


def resolve(root: pathlib.Path, rel_path: str) -> pathlib.Path:
    path = pathlib.Path(rel_path)
    if path.is_absolute():
        return path
    return root / path


def existing_path(root: pathlib.Path, rel_path: str) -> bool:
    if not rel_path or rel_path.startswith("~/"):
        return True
    return resolve(root, rel_path).exists()


def require_paths(root: pathlib.Path, node_id: str, field: str, required: bool = True) -> None:
    paths = CURRENT_NODE.get(field)
    if paths is None:
        if required:
            fail(f"{node_id}: missing {field}")
        return
    if not isinstance(paths, list):
        fail(f"{node_id}: {field} must be a list")
    if required and not paths:
        fail(f"{node_id}: {field} must not be empty")
    for rel_path in paths:
        if not isinstance(rel_path, str) or not rel_path.strip():
            fail(f"{node_id}: invalid path in {field}")
        if not existing_path(root, rel_path):
            fail(f"{node_id}: {field} path does not exist: {rel_path}")


CURRENT_NODE: dict = {}


def main() -> None:
    if len(sys.argv) != 3:
        fail("usage: redcap-evolution-grade-check.py <redcap_root> <registry_path>")

    root = pathlib.Path(sys.argv[1]).resolve()
    registry_arg = pathlib.Path(sys.argv[2])
    registry_path = registry_arg if registry_arg.is_absolute() else root / registry_arg
    if not registry_path.is_file():
        fail(f"missing registry: {registry_path}")

    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid json: {exc}")

    if payload.get("version") != 1:
        fail("version must be 1")

    required_dimensions = payload.get("required_dimensions")
    if not isinstance(required_dimensions, list) or not required_dimensions:
        fail("required_dimensions must be a non-empty list")
    required_dimensions = [item for item in required_dimensions if isinstance(item, str) and item.strip()]
    if not required_dimensions:
        fail("required_dimensions has no valid entries")

    dimension_levels = set(payload.get("dimension_levels") or [])
    if not dimension_levels:
        fail("dimension_levels must be non-empty")

    nodes = payload.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        fail("nodes must be a non-empty list")

    seen: set[str] = set()
    status_counts: Counter[str] = Counter()
    weak_nodes: list[str] = []

    for node in nodes:
        if not isinstance(node, dict):
            fail("node entries must be objects")
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id.strip():
            fail("node missing id")
        if node_id in seen:
            fail(f"duplicate node id: {node_id}")
        seen.add(node_id)

        title = node.get("title")
        if not isinstance(title, str) or len(title.strip()) < 8:
            fail(f"{node_id}: title must be meaningful")

        requirement_ids = node.get("requirement_ids")
        if not isinstance(requirement_ids, list) or not requirement_ids:
            fail(f"{node_id}: requirement_ids must be non-empty")
        for requirement_id in requirement_ids:
            if requirement_id not in ALLOWED_REQUIREMENTS:
                fail(f"{node_id}: invalid requirement id: {requirement_id}")

        status = node.get("baseline_status")
        if status not in ALLOWED_STATUSES:
            fail(f"{node_id}: invalid baseline_status: {status}")
        status_counts[status] += 1

        dimensions = node.get("dimensions")
        if not isinstance(dimensions, dict):
            fail(f"{node_id}: dimensions must be an object")
        missing_dimensions = [item for item in required_dimensions if item not in dimensions]
        if missing_dimensions:
            fail(f"{node_id}: missing dimensions: {', '.join(missing_dimensions)}")
        for key, value in dimensions.items():
            if key not in required_dimensions:
                fail(f"{node_id}: unknown dimension: {key}")
            if value not in dimension_levels:
                fail(f"{node_id}: invalid dimension level for {key}: {value}")

        node_weak_levels = [key for key, value in dimensions.items() if value in WEAK_LEVELS]
        if status == "meets" and node_weak_levels:
            fail(f"{node_id}: meets node cannot contain weak dimensions: {', '.join(node_weak_levels)}")
        if node_weak_levels:
            weak_nodes.append(f"{node_id}:{','.join(node_weak_levels)}")

        global CURRENT_NODE
        CURRENT_NODE = node
        for path_field in (
            "trigger_paths",
            "evidence_paths",
            "check_paths",
            "candidate_sink_paths",
            "independent_review_paths",
            "failure_visibility_paths",
        ):
            require_paths(root, node_id, path_field, required=True)

        gap = node.get("gap", "")
        remediation = node.get("remediation", [])
        if status != "meets":
            if not isinstance(gap, str) or len(gap.strip()) < 20:
                fail(f"{node_id}: non-meets node must explain its gap")
            if not isinstance(remediation, list) or not remediation:
                fail(f"{node_id}: non-meets node must declare remediation")
            for item in remediation:
                if not isinstance(item, str) or len(item.strip()) < 12:
                    fail(f"{node_id}: remediation items must be meaningful")
        if status in {"host-limited", "manual-only"}:
            reason = node.get("boundary_reason")
            if not isinstance(reason, str) or len(reason.strip()) < 20:
                fail(f"{node_id}: {status} node must explain boundary_reason")

    required_nodes = set(payload.get("required_nodes") or [])
    missing_required_field = sorted(REQUIRED_NODES - required_nodes)
    if missing_required_field:
        fail("required_nodes field missing required ids: " + ", ".join(missing_required_field))

    missing_nodes = sorted(REQUIRED_NODES - seen)
    if missing_nodes:
        fail("missing required nodes: " + ", ".join(missing_nodes))

    print("EVOLUTION_GRADE_BASELINE")
    print(f"nodes={len(nodes)}")
    print(
        "statuses="
        + ",".join(f"{status}={status_counts.get(status, 0)}" for status in sorted(ALLOWED_STATUSES))
    )
    if weak_nodes:
        print("weak_dimensions=" + ";".join(weak_nodes[:12]))
    print("EVOLUTION_GRADE_OK")


if __name__ == "__main__":
    main()

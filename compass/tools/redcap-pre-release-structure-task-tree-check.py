#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "references/pre-release-structure-refactor-task-tree.json"
PARENT_LEDGER = ROOT / "references/redcap-parent-task-ledger.md"
PACKAGE_POLICY = ROOT / "references/runtime-package-readiness-policy.json"
PRE_RELEASE_REVIEW = ROOT / "references/pre-release-product-architecture-review.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-pre-release-structure-task-tree-check] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"{label} missing: {path.relative_to(ROOT)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label} json: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be an object")
    return payload


def require_text(payload: dict[str, Any], key: str, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{label} missing non-empty {key}")
    return value.strip()


def require_bool(payload: dict[str, Any], key: str, label: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        fail(f"{label} missing boolean {key}")
    return value


def main() -> None:
    policy = load_json(POLICY, "structure task-tree policy")
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "pre-release-structure-refactor-task-tree":
        fail("policy_id mismatch")
    if policy.get("status") != "active-before-public-release":
        fail("policy status must remain active-before-public-release")
    if policy.get("parent_task") != "P4-2":
        fail("parent_task must be P4-2")

    corrections = policy.get("truth_corrections")
    if not isinstance(corrections, list) or not corrections:
        fail("truth_corrections must be non-empty")
    for item in corrections:
        if not isinstance(item, dict):
            fail("truth_corrections entries must be objects")
        require_text(item, "id", "truth correction")
        require_text(item, "claim", "truth correction")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            fail("truth correction evidence must be non-empty")
        for rel in evidence:
            if not isinstance(rel, str) or not rel.strip():
                fail("truth correction evidence path must be text")
            if not (ROOT / rel).exists():
                fail(f"truth correction evidence path missing: {rel}")

    rules = policy.get("ordering_rules")
    if not isinstance(rules, dict):
        fail("ordering_rules must be an object")
    for key in [
        "npm_preflight_before_history_surgery",
        "whitelist_before_delete_or_move",
        "history_assets_preserve_by_default",
        "release_ready_requires_all_p0_blockers_closed",
        "redcap_arsenal_content_is_not_release_blocker_by_default",
    ]:
        if require_bool(rules, key, "ordering_rules") is not True:
            fail(f"ordering rule must be true: {key}")

    nodes = policy.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        fail("nodes must be non-empty")
    node_map: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            fail("node entries must be objects")
        node_id = require_text(node, "id", "node")
        if node_id in node_map:
            fail(f"duplicate node id: {node_id}")
        require_text(node, "title", f"node {node_id}")
        require_text(node, "status", f"node {node_id}")
        require_text(node, "priority", f"node {node_id}")
        require_text(node, "reason", f"node {node_id}")
        if not isinstance(node.get("depends_on"), list):
            fail(f"{node_id}: depends_on must be a list")
        if not isinstance(node.get("release_blocker"), bool):
            fail(f"{node_id}: release_blocker must be boolean")
        node_map[node_id] = node

    required = {"P4-2g", "P4-2b", "P4-2c", "P4-2d", "P4-2e", "P4-2h", "P4-2"}
    missing = sorted(required - set(node_map))
    if missing:
        fail("missing required nodes: " + ", ".join(missing))

    def depends(node_id: str, expected: set[str]) -> None:
        actual = set(node_map[node_id].get("depends_on", []))
        if not expected.issubset(actual):
            fail(f"{node_id}: expected dependencies missing: {', '.join(sorted(expected - actual))}")

    if node_map["P4-2g"]["status"] != "current":
        fail("P4-2g must be the current task-tree reanchor node")
    if node_map["P4-2g"]["priority"] != "P0":
        fail("P4-2g must be P0")
    depends("P4-2g", {"P4-2f"})
    depends("P4-2b", {"P4-2g"})
    depends("P4-2c", {"P4-2b"})
    depends("P4-2d", {"P4-2g", "P4-2b"})
    depends("P4-2e", {"P4-2g"})
    depends("P4-2h", {"P4-2e"})
    depends("P4-2", {"P4-2b", "P4-2c", "P4-2d"})
    for node_id in ("P4-2b", "P4-2c", "P4-2d"):
        if node_map[node_id]["release_blocker"] is not True:
            fail(f"{node_id} must remain release-blocking")
    if node_map["P4-2e"]["release_blocker"] is not False:
        fail("P4-2e must not be a default release blocker")

    claims = policy.get("must_not_claim")
    if not isinstance(claims, list) or len(claims) < 5:
        fail("must_not_claim must list release and historical-asset boundaries")
    gates = policy.get("acceptance_gates")
    if not isinstance(gates, list) or len(gates) < 4:
        fail("acceptance_gates must be non-empty and concrete")

    ledger = PARENT_LEDGER.read_text(encoding="utf-8")
    if "| P4-2f |" not in ledger:
        fail("parent ledger missing P4-2f row")
    if "| P4-2f |" in ledger and "| in-progress |" in next(line for line in ledger.splitlines() if line.startswith("| P4-2f |")):
        fail("parent ledger still marks P4-2f in-progress")
    if "| P4-2f |" in ledger and "| completed |" not in next(line for line in ledger.splitlines() if line.startswith("| P4-2f |")):
        fail("parent ledger must mark P4-2f completed")
    for node_id in ("P4-2g", "P4-2h"):
        if f"| {node_id} |" not in ledger:
            fail(f"parent ledger missing {node_id} row")

    package_policy = load_json(PACKAGE_POLICY, "runtime package readiness policy")
    if package_policy.get("publish_allowed") is not False:
        fail("publish_allowed must remain false during structure reanchor")

    review = load_json(PRE_RELEASE_REVIEW, "pre-release product architecture review")
    if review.get("release_recommendation") != "not-ready-before-product-architecture-remediation":
        fail("pre-release review must keep release not-ready recommendation")
    findings = review.get("findings")
    if not isinstance(findings, list):
        fail("pre-release findings must be a list")
    blockers = [item for item in findings if isinstance(item, dict) and item.get("severity") == "release-blocker"]
    if len(blockers) < 5:
        fail("pre-release review must still expose the known release blockers")

    print("PRE_RELEASE_STRUCTURE_TASK_TREE_OK nodes=%d" % len(nodes))


if __name__ == "__main__":
    main()

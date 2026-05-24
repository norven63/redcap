#!/usr/bin/env python3
"""Validate the pre-release freeze policy that prevents governance churn loops."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "references/pre-release-freeze-and-artifact-churn-policy.json"
BACKLOG = ROOT / "references/backlogs/redcap-architecture-smell-governance.json"
CORE = ROOT / "compass/CONTRIBUTING.core.md"


def fail(message: str) -> None:
    print(f"[redcap-pre-release-freeze-policy-check] {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> dict:
    if not path.exists():
        fail(f"missing file: {path.relative_to(ROOT)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")
    if not isinstance(payload, dict):
        fail(f"top-level JSON must be an object: {path.relative_to(ROOT)}")
    return payload


def require_list(payload: dict, key: str, minimum: int = 1) -> list:
    value = payload.get(key)
    if not isinstance(value, list) or len(value) < minimum:
        fail(f"{key} must be a list with at least {minimum} item(s)")
    return value


def main() -> None:
    policy = load_json(POLICY)
    if policy.get("policy_id") != "pre-release-freeze-and-artifact-churn-policy":
        fail("policy_id mismatch")
    if policy.get("status") != "active":
        fail("policy status must be active")

    freeze_rule = policy.get("freeze_rule")
    if not isinstance(freeze_rule, dict):
        fail("freeze_rule must be an object")
    if freeze_rule.get("default_for_new_findings") != "classify-first-do-not-auto-expand-current-scope":
        fail("new findings must classify first and must not auto-expand current scope")
    expand_reasons = require_list(freeze_rule, "current_scope_can_expand_only_if", minimum=5)
    for required in [
        "privacy_or_secret_leak_risk",
        "package_publish_safety_risk",
        "session_or_task_ownership_correctness_risk",
        "false_completion_or_false_release_ready_claim",
    ]:
        if required not in expand_reasons:
            fail(f"missing expansion reason: {required}")

    artifact_budget = policy.get("artifact_budget")
    if not isinstance(artifact_budget, dict):
        fail("artifact_budget must be an object")
    forbidden_loop = artifact_budget.get("forbidden_loop", "")
    if "new active cleanup task" not in forbidden_loop:
        fail("artifact_budget.forbidden_loop must ban cleanup self-spawn")

    lanes = require_list(policy, "classification_lanes", minimum=5)
    lane_ids = {item.get("id") for item in lanes if isinstance(item, dict)}
    for required in [
        "release_blocker",
        "active_current_scope",
        "post_release_roadmap",
        "evidence_archive_only",
        "rejected_noise_with_reason",
    ]:
        if required not in lane_ids:
            fail(f"missing classification lane: {required}")

    reporting = policy.get("human_reporting_contract")
    if not isinstance(reporting, dict):
        fail("human_reporting_contract must be an object")
    must_say = require_list(reporting, "must_say", minimum=4)
    if not any("父任务线" in str(item) for item in must_say):
        fail("human reporting contract must mention parent task line")

    backlog = load_json(BACKLOG)
    requirements = backlog.get("requirements")
    if not isinstance(requirements, list):
        fail("backlog requirements must be a list")
    rasg025 = next((item for item in requirements if item.get("id") == "RASG-025"), None)
    if not isinstance(rasg025, dict):
        fail("RASG-025 must be registered in architecture smell backlog")
    if rasg025.get("status") not in {"planned", "open", "in_progress", "done"}:
        fail("RASG-025 status must be explicit")
    evidence = rasg025.get("evidence", [])
    if "references/pre-release-freeze-and-artifact-churn-policy.json" not in evidence:
        fail("RASG-025 evidence must include the freeze policy")

    core_text = CORE.read_text(encoding="utf-8")
    if "发布前冻结" not in core_text or "治理任务自我增殖" not in core_text:
        fail("core contract must mention pre-release freeze and governance self-spawn")

    print(
        "pre-release-freeze-policy ok "
        f"lanes={len(lanes)} expand_reasons={len(expand_reasons)} rasg025={rasg025.get('status')}"
    )


if __name__ == "__main__":
    main()

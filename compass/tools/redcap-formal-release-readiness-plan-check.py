#!/usr/bin/env python3
# 用途：发布前安全与计划校验脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-formal-release-readiness-plan-check] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing {label}: {path.relative_to(ROOT)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be a json object")
    return payload


def require_keys(payload: dict[str, Any], keys: list[str], label: str) -> None:
    for key in keys:
        if key not in payload:
            fail(f"{label} missing key: {key}")


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{label} must be a non-empty string")
    return value.strip()


def require_list(value: Any, label: str, *, min_len: int = 1) -> list[Any]:
    if not isinstance(value, list) or len(value) < min_len:
        fail(f"{label} must be a list with at least {min_len} item(s)")
    return value


def require_bool(value: Any, expected: bool, label: str) -> None:
    if value is not expected:
        fail(f"{label} must be {expected}")


def repo_rel_exists(path_text: str) -> bool:
    path = ROOT / path_text
    return path.exists()


def main() -> int:
    plan_path = ROOT / "references/formal-release-readiness-plan.json"
    matrix_path = ROOT / "references/release-authorization-matrix.json"
    handoff_path = ROOT / "references/public-release-handoff.md"
    e2e_path = ROOT / "references/release-readiness-e2e-matrix.json"
    package_surface_path = ROOT / "references/public-package-surface-policy.json"
    runtime_policy_path = ROOT / "references/runtime-package-readiness-policy.json"

    plan = load_json(plan_path, "formal release readiness plan")
    matrix = load_json(matrix_path, "release authorization matrix")
    e2e = load_json(e2e_path, "release E2E matrix")
    package_surface = load_json(package_surface_path, "public package surface policy")
    runtime_policy = load_json(runtime_policy_path, "runtime package readiness policy")

    if not handoff_path.is_file():
        fail("missing public release handoff")
    handoff = handoff_path.read_text(encoding="utf-8", errors="replace")

    require_keys(
        plan,
        [
            "version",
            "plan_id",
            "status",
            "prepared_package_name",
            "claim_boundary",
            "stage_order",
            "stages",
            "automation_policy",
        ],
        "formal release readiness plan",
    )
    if plan["version"] != 1:
        fail("formal release readiness plan version must be 1")
    if plan["plan_id"] != "redcap-formal-release-readiness-plan":
        fail("formal release readiness plan id mismatch")
    if plan["status"] != "planned-before-formal-release-task":
        fail("formal release readiness plan must remain planned-before-formal-release-task")

    required_sources = require_list(plan.get("required_sources"), "plan required_sources", min_len=6)
    for source in required_sources:
        source_text = require_text(source, "plan required_sources entry")
        if not repo_rel_exists(source_text):
            fail(f"plan required source missing: {source_text}")

    package_name = require_text(plan.get("prepared_package_name"), "plan prepared_package_name")
    if package_name != "@norven63/redcap":
        fail("prepared package name must remain @norven63/redcap")

    claim_boundary = plan.get("claim_boundary")
    if not isinstance(claim_boundary, dict):
        fail("plan claim_boundary must be an object")
    require_bool(claim_boundary.get("is_public_release_ready"), False, "claim_boundary.is_public_release_ready")
    require_bool(claim_boundary.get("is_published"), False, "claim_boundary.is_published")
    require_bool(
        claim_boundary.get("is_authorized_for_registry_mutation"),
        False,
        "claim_boundary.is_authorized_for_registry_mutation",
    )

    expected_stage_order = [
        "R0-release-task-anchor",
        "R1-deferred-root-group-disposition",
        "R2-public-package-surface-hardening",
        "R3-cli-runtime-product-experience",
        "R4-security-and-privacy-audit",
        "R5-release-e2e-matrix",
        "R6-human-release-decisions",
        "R7-final-prism-review",
        "R8-registry-release-execution",
        "R9-post-release-monitoring",
    ]
    stage_order = require_list(plan.get("stage_order"), "plan stage_order", min_len=len(expected_stage_order))
    if stage_order != expected_stage_order:
        fail("plan stage_order does not match required release route")

    stages = require_list(plan.get("stages"), "plan stages", min_len=len(expected_stage_order))
    if len(stages) != len(expected_stage_order):
        fail("plan must define exactly 10 stages")
    stage_ids = []
    for index, stage in enumerate(stages):
        if not isinstance(stage, dict):
            fail(f"stage[{index}] must be an object")
        stage_id = require_text(stage.get("id"), f"stage[{index}].id")
        stage_ids.append(stage_id)
        if stage_id != expected_stage_order[index]:
            fail(f"stage[{index}] id mismatch")
        for key in ["title", "problem", "human_boundary"]:
            require_text(stage.get(key), f"{stage_id}.{key}")
        for key in ["actions", "acceptance", "stop_conditions"]:
            require_list(stage.get(key), f"{stage_id}.{key}", min_len=2)
    if stage_ids != stage_order:
        fail("stage ids must match stage_order")

    automation = plan.get("automation_policy")
    if not isinstance(automation, dict):
        fail("automation_policy must be an object")
    require_bool(automation.get("fail_closed"), True, "automation_policy.fail_closed")
    must_stop = require_list(automation.get("must_stop_for"), "automation_policy.must_stop_for", min_len=6)
    for required_phrase in ["license", "secret", "Prism", "external package registry"]:
        if not any(required_phrase in str(item) for item in must_stop):
            fail(f"automation_policy.must_stop_for missing concept: {required_phrase}")

    require_keys(
        matrix,
        [
            "version",
            "matrix_id",
            "status",
            "strict_rule",
            "prepared_defaults",
            "norven_required_decisions",
            "cap_prism_autonomous_decisions",
            "conditional_authorization_template",
            "release_questionnaire",
            "must_stop_if",
        ],
        "release authorization matrix",
    )
    if matrix["version"] != 1:
        fail("release authorization matrix version must be 1")
    if matrix["matrix_id"] != "redcap-release-authorization-matrix":
        fail("release authorization matrix id mismatch")
    if matrix["status"] != "questions-unanswered-before-formal-release-task":
        fail("authorization matrix must remain unanswered before formal release task")

    defaults = matrix.get("prepared_defaults")
    if not isinstance(defaults, dict):
        fail("prepared_defaults must be an object")
    if defaults.get("package_name") != package_name:
        fail("authorization matrix package name must match formal plan")
    if defaults.get("current_license") != "UNLICENSED":
        fail("authorization matrix must reflect current UNLICENSED status")
    require_bool(defaults.get("current_publish_allowed"), False, "prepared_defaults.current_publish_allowed")
    require_bool(defaults.get("current_package_private_required"), True, "prepared_defaults.current_package_private_required")

    norven_required = require_list(matrix.get("norven_required_decisions"), "norven_required_decisions", min_len=10)
    required_decision_ids = {
        "license-selection",
        "public-distribution-target",
        "release-level",
        "version",
        "npm-scope-and-account-permission",
        "private-flag-release-switch",
        "runtime-publish-allowed-switch",
        "registry-release-action",
        "known-limitation-risk-acceptance",
        "destructive-cleanup-or-history-loss",
    }
    actual_decision_ids = {
        require_text(item.get("id"), "norven_required decision id")
        for item in norven_required
        if isinstance(item, dict)
    }
    missing_decisions = sorted(required_decision_ids - actual_decision_ids)
    if missing_decisions:
        fail("authorization matrix missing Norven-required decisions: " + ", ".join(missing_decisions))

    questionnaire = require_list(matrix.get("release_questionnaire"), "release_questionnaire", min_len=10)
    question_decisions = {
        require_text(item.get("decision"), "release_questionnaire decision")
        for item in questionnaire
        if isinstance(item, dict)
    }
    if required_decision_ids - question_decisions:
        fail("release questionnaire does not cover all Norven-required decisions")

    conditional = matrix.get("conditional_authorization_template")
    if not isinstance(conditional, dict):
        fail("conditional_authorization_template must be an object")
    if conditional.get("status") != "not-yet-granted":
        fail("conditional authorization must not be granted by default")
    safe_example = require_text(conditional.get("safe_example"), "conditional_authorization_template.safe_example")
    if "13 required conditions" not in safe_example:
        fail("conditional authorization safe_example must point readers back to all required conditions")
    require_list(conditional.get("required_conditions"), "conditional_authorization_template.required_conditions", min_len=13)
    invalid_authorizations = require_list(conditional.get("invalid_authorizations"), "conditional_authorization_template.invalid_authorizations", min_len=5)
    invalid_blob = "\n".join(str(item).lower() for item in invalid_authorizations)
    for required_concept in ["blanket", "omits", "secret", "waiver", "override"]:
        if required_concept not in invalid_blob:
            fail(f"conditional authorization invalid_authorizations missing concept: {required_concept}")

    autonomous = require_list(matrix.get("cap_prism_autonomous_decisions"), "cap_prism_autonomous_decisions", min_len=5)
    for item in autonomous:
        if not isinstance(item, dict):
            fail("cap_prism_autonomous_decisions entries must be objects")
        require_text(item.get("id"), "autonomous decision id")
        require_text(item.get("scope"), "autonomous decision scope")

    if e2e.get("matrix_id") != "redcap-release-readiness-e2e-matrix":
        fail("release E2E matrix id mismatch")
    manual_boundaries = e2e.get("manual_release_boundaries")
    require_list(manual_boundaries, "release E2E manual boundaries", min_len=4)
    for expected in [
        "License selection",
        "npm credentials and registry login",
        "package.json private=false",
        "runtime-package-readiness publish_allowed=true",
    ]:
        if expected not in manual_boundaries:
            fail(f"release E2E matrix missing manual boundary: {expected}")

    if package_surface.get("prepared_package_name") != package_name:
        fail("public package surface package name mismatch")
    require_bool(package_surface.get("publish_allowed"), False, "public_package_surface.publish_allowed")
    require_bool(package_surface.get("package_private_required"), True, "public_package_surface.package_private_required")
    if package_surface.get("license_status") != "manual-before-public-publish":
        fail("public package surface must keep license manual boundary")

    if runtime_policy.get("package_name") != package_name:
        fail("runtime package readiness package name mismatch")
    require_bool(runtime_policy.get("publish_allowed"), False, "runtime_package_readiness.publish_allowed")

    for required_reference in [
        "references/formal-release-readiness-plan.json",
        "references/release-authorization-matrix.json",
        "release-readiness-e2e-matrix",
        "@norven63/redcap",
    ]:
        if required_reference not in handoff:
            fail(f"public release handoff missing reference: {required_reference}")

    print("FORMAL_RELEASE_READINESS_PLAN_OK stages=10 norven_required=10 conditional_authorization=not-yet-granted")
    return 0


if __name__ == "__main__":
    sys.exit(main())

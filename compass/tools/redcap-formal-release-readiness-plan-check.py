#!/usr/bin/env python3
# 用途：发布前安全与计划校验脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def parse_args(argv: list[str]) -> dict[str, Path]:
    paths = {
        "plan": ROOT / "references/formal-release-readiness-plan.json",
        "matrix": ROOT / "references/release-authorization-matrix.json",
        "handoff": ROOT / "references/public-release-handoff.md",
        "e2e": ROOT / "references/release-readiness-e2e-matrix.json",
        "package_surface": ROOT / "references/public-package-surface-policy.json",
        "runtime_policy": ROOT / "references/runtime-package-readiness-policy.json",
        "historical_cleanup": ROOT / "references/historical-asset-physical-cleanup-release-gate.json",
    }
    option_to_key = {
        "--plan": "plan",
        "--matrix": "matrix",
        "--handoff": "handoff",
        "--e2e": "e2e",
        "--package-surface": "package_surface",
        "--runtime-policy": "runtime_policy",
        "--historical-cleanup": "historical_cleanup",
    }
    index = 0
    while index < len(argv):
        option = argv[index]
        key = option_to_key.get(option)
        if key is None:
            fail(f"unsupported argument: {option}")
        if index + 1 >= len(argv):
            fail(f"{option} requires a path")
        paths[key] = Path(argv[index + 1])
        index += 2
    return paths


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
    paths = parse_args(sys.argv[1:])
    plan_path = paths["plan"]
    matrix_path = paths["matrix"]
    handoff_path = paths["handoff"]
    e2e_path = paths["e2e"]
    package_surface_path = paths["package_surface"]
    runtime_policy_path = paths["runtime_policy"]
    historical_cleanup_path = paths["historical_cleanup"]

    plan = load_json(plan_path, "formal release readiness plan")
    matrix = load_json(matrix_path, "release authorization matrix")
    e2e = load_json(e2e_path, "release E2E matrix")
    package_surface = load_json(package_surface_path, "public package surface policy")
    runtime_policy = load_json(runtime_policy_path, "runtime package readiness policy")
    historical_cleanup = load_json(historical_cleanup_path, "historical asset physical cleanup release gate")

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
    require_bool(
        claim_boundary.get("historical_asset_physical_cleanup_gate_satisfied"),
        False,
        "claim_boundary.historical_asset_physical_cleanup_gate_satisfied",
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
    for index, item in enumerate(must_stop):
        if not isinstance(item, str):
            fail(f"automation_policy.must_stop_for[{index}] must be a string")
    for required_phrase in ["license", "secret", "Prism", "external package registry"]:
        if not any(required_phrase in str(item) for item in must_stop):
            fail(f"automation_policy.must_stop_for missing concept: {required_phrase}")
    if not any("historical asset physical cleanup" in str(item).lower() for item in must_stop):
        fail("automation_policy.must_stop_for must include unresolved historical asset cleanup")

    cleanup_required_sources = set(required_sources)
    if "references/historical-asset-physical-cleanup-release-gate.json" not in cleanup_required_sources:
        fail("plan required_sources must include historical asset cleanup release gate")
    stage_map = {stage["id"]: stage for stage in stages}
    r1_blob = json.dumps(stage_map["R1-deferred-root-group-disposition"], ensure_ascii=False)
    for required_concept in [
        "Historical asset physical cleanup release gate passes",
        "release-blocking historical group",
        "package-visible",
        "release-safe disposition",
    ]:
        if required_concept not in r1_blob:
            fail(f"R1 must explicitly cover historical cleanup gate concept: {required_concept}")
    for stage_id in [
        "R4-security-and-privacy-audit",
        "R5-release-e2e-matrix",
        "R6-human-release-decisions",
    ]:
        stage_blob = json.dumps(stage_map[stage_id], ensure_ascii=False).lower()
        if "historical asset" not in stage_blob:
            fail(f"{stage_id} must reference historical asset cleanup hard gate")

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
    if "14 required conditions" not in safe_example:
        fail("conditional authorization safe_example must point readers back to all required conditions")
    required_conditions = require_list(
        conditional.get("required_conditions"),
        "conditional_authorization_template.required_conditions",
        min_len=14,
    )
    if "historical asset physical cleanup release gate pass" not in required_conditions:
        fail("conditional authorization must require historical asset physical cleanup release gate pass")
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
    e2e_envs = e2e.get("environments")
    if not isinstance(e2e_envs, list) or not any(
        isinstance(item, dict)
        and item.get("id") == "historical-asset-physical-cleanup-release-gate"
        and item.get("status") == "deferred-to-formal-release-task"
        for item in e2e_envs
    ):
        fail("release E2E matrix must carry the historical asset cleanup release gate")
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
    manual_surface_boundaries = package_surface.get("manual_release_boundaries")
    require_list(manual_surface_boundaries, "public package surface manual_release_boundaries", min_len=5)
    if not any("historical asset physical cleanup" in str(item).lower() for item in manual_surface_boundaries):
        fail("public package surface must mention historical asset physical cleanup release gate")

    if runtime_policy.get("package_name") != package_name:
        fail("runtime package readiness package name mismatch")
    require_bool(runtime_policy.get("publish_allowed"), False, "runtime_package_readiness.publish_allowed")

    require_keys(
        historical_cleanup,
        [
            "version",
            "policy_id",
            "status",
            "blocks_public_release",
            "required_before",
            "scope",
            "required_release_dispositions",
            "forbidden_release_greenlights",
            "current_known_blockers",
            "required_checks",
            "release_task_rule",
        ],
        "historical asset physical cleanup release gate",
    )
    if historical_cleanup["version"] != 1:
        fail("historical asset cleanup gate version must be 1")
    if historical_cleanup["policy_id"] != "redcap-historical-asset-physical-cleanup-release-gate":
        fail("historical asset cleanup gate id mismatch")
    if historical_cleanup["status"] != "hard-gate-before-formal-public-release":
        fail("historical asset cleanup gate must be hard-gate-before-formal-public-release")
    require_bool(
        historical_cleanup.get("blocks_public_release"),
        True,
        "historical_cleanup.blocks_public_release",
    )
    dispositions = require_list(
        historical_cleanup.get("required_release_dispositions"),
        "historical_cleanup.required_release_dispositions",
        min_len=4,
    )
    disposition_ids = {
        require_text(item.get("id"), "historical cleanup disposition id")
        for item in dispositions
        if isinstance(item, dict)
    }
    for expected in {
        "private-archive-migrated",
        "public-arsenal-reviewed-export",
        "workspace-local-excluded-nonhistorical",
        "release-blocker-until-resolved",
    }:
        if expected not in disposition_ids:
            fail(f"historical cleanup gate missing disposition: {expected}")
    forbidden_greenlights = "\n".join(
        str(item).lower()
        for item in require_list(
            historical_cleanup.get("forbidden_release_greenlights"),
            "historical_cleanup.forbidden_release_greenlights",
            min_len=5,
        )
    )
    for expected in ["package exclusion alone", "deferred-before-release-readiness", "delete", "alias", "release-blocker"]:
        if expected not in forbidden_greenlights:
            fail(f"historical cleanup gate forbidden greenlights missing concept: {expected}")
    cleanup_required_checks = require_list(
        historical_cleanup.get("required_checks"),
        "historical_cleanup.required_checks",
        min_len=5,
    )
    for expected in [
        "redcap-formal-release-readiness-plan-check.sh",
        "redcap-root-ia-deferral-check.sh",
        "redcap-package-publish-safety-check.sh",
        "redcap-runtime-package-manifest.sh --check --npm-pack-dry-run",
        "redcap-clean-workspace-e2e.sh --check-result",
    ]:
        if not any(expected in str(item) for item in cleanup_required_checks):
            fail(f"historical cleanup gate missing required check: {expected}")
    release_task_rule = require_text(historical_cleanup.get("release_task_rule"), "historical_cleanup.release_task_rule")
    if "R1" not in release_task_rule or "R8" not in release_task_rule:
        fail("historical cleanup gate release_task_rule must bind R1 before R8")

    for required_reference in [
        "references/formal-release-readiness-plan.json",
        "references/release-authorization-matrix.json",
        "references/historical-asset-physical-cleanup-release-gate.json",
        "release-readiness-e2e-matrix",
        "@norven63/redcap",
    ]:
        if required_reference not in handoff:
            fail(f"public release handoff missing reference: {required_reference}")

    print(
        "FORMAL_RELEASE_READINESS_PLAN_OK "
        "stages=10 norven_required=10 conditional_authorization=not-yet-granted "
        "historical_asset_cleanup_hard_gate=registered"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

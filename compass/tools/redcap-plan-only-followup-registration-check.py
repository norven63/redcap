#!/usr/bin/env python3
# 用途：棱镜与结论保障脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#prism-and-providers

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES = ROOT / "references/plan-only-followup-registration-fixtures.json"
POLICY = ROOT / "references/conclusion-prism-policy.json"
BACKLOG = ROOT / "references/backlogs/redcap-architecture-smell-governance.json"
ROOT_IA_PLAN = ROOT / "references/root-information-architecture-consolidation-plan.json"

PLAN_ONLY_STATUSES = {
    "design-complete",
    "plan-complete",
    "route-only",
    "partial-with-explicit-defer",
}
ROOT_IA_APPLIED_STATUS = "target-model-complete-physical-convergence-applied-with-compatibility-shims"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-plan-only-followup-registration-check] {message}")


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


def non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def backlog_by_id(backlog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in backlog.get("requirements") or []:
        if not isinstance(item, dict):
            continue
        req_id = item.get("id")
        if isinstance(req_id, str):
            rows[req_id] = item
    return rows


def validate_policy(policy: dict[str, Any]) -> None:
    requirement = policy.get("plan_only_follow_up_requirement")
    if not isinstance(requirement, dict):
        fail("conclusion policy must define plan_only_follow_up_requirement")
    text = json.dumps(requirement, ensure_ascii=False)
    for phrase in [
        "design-complete",
        "plan-complete",
        "route-only",
        "partial-with-explicit-defer",
        "durably tracked",
        "owner surface",
        "revisit trigger",
        "acceptance boundary",
    ]:
        if phrase not in text:
            fail(f"plan-only policy missing required phrase: {phrase}")


def validate_follow_up_item(item: Any, case_id: str, backlog_rows: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if not isinstance(item, dict):
        return [f"{case_id}: follow-up item must be an object"]
    required_fields = [
        "description",
        "tracking_surface",
        "tracking_id",
        "owner_surface",
        "acceptance_boundary",
        "revisit_trigger",
        "blocking_relationship",
    ]
    for field in required_fields:
        if not non_empty(item.get(field)):
            errors.append(f"{case_id}: follow-up item missing {field}")
    tracking_id = item.get("tracking_id")
    tracking_surface = str(item.get("tracking_surface", ""))
    if "backlog" in tracking_surface and tracking_id not in backlog_rows:
        errors.append(f"{case_id}: backlog tracking_id not registered: {tracking_id}")
    if tracking_id in backlog_rows:
        status = backlog_rows[tracking_id].get("status", "planned")
        if status not in {"planned", "in_progress", "done", "deferred"}:
            errors.append(f"{case_id}: unsupported tracked requirement status for {tracking_id}: {status}")
    return errors


def validate_no_follow_up_justification(case: dict[str, Any], case_id: str) -> list[str]:
    justification = case.get("no_follow_up_justification")
    if not isinstance(justification, dict):
        return [f"{case_id}: missing no_follow_up_justification or deferred_items"]
    errors: list[str] = []
    for field in ["reason", "owner_surface", "acceptance_boundary", "revisit_trigger"]:
        if not non_empty(justification.get(field)):
            errors.append(f"{case_id}: no_follow_up_justification missing {field}")
    return errors


def case_errors(case: dict[str, Any], backlog_rows: dict[str, dict[str, Any]]) -> list[str]:
    case_id = str(case.get("id") or "unknown-case")
    scope_status = str(case.get("scope_status") or "")
    errors: list[str] = []
    if scope_status not in PLAN_ONLY_STATUSES:
        return errors
    items = case.get("deferred_items")
    if isinstance(items, list) and items:
        for item in items:
            errors.extend(validate_follow_up_item(item, case_id, backlog_rows))
    else:
        errors.extend(validate_no_follow_up_justification(case, case_id))
    return errors


def validate_fixtures(fixtures: dict[str, Any], backlog_rows: dict[str, dict[str, Any]]) -> tuple[int, int]:
    if fixtures.get("version") != 1:
        fail("fixtures version must be 1")
    if fixtures.get("fixture_id") != "redcap-plan-only-followup-registration-fixtures":
        fail("unexpected fixture_id")
    cases = fixtures.get("cases")
    if not isinstance(cases, list) or not cases:
        fail("fixtures must contain cases")
    passed = 0
    negative = 0
    for case in cases:
        if not isinstance(case, dict):
            fail("fixture cases must be objects")
        case_id = str(case.get("id") or "unknown-case")
        expected = case.get("expected_result")
        if expected not in {"pass", "fail"}:
            fail(f"{case_id}: expected_result must be pass or fail")
        errors = case_errors(case, backlog_rows)
        if expected == "pass" and errors:
            fail("; ".join(errors))
        if expected == "fail":
            negative += 1
            if not errors:
                fail(f"{case_id}: negative fixture unexpectedly passed")
        passed += 1
    if negative == 0:
        fail("fixtures must include at least one expected-fail regression")
    return passed, negative


def validate_live_rasg_chain(backlog: dict[str, Any], root_plan: dict[str, Any]) -> None:
    rows = backlog_by_id(backlog)
    for required in ["RASG-017", "RASG-022", "RASG-023"]:
        if required not in rows:
            fail(f"architecture backlog missing {required}")
    if "RASG-022" not in (rows["RASG-017"].get("follow_up_requirements") or []):
        fail("RASG-017 must link RASG-022 as durable physical apply follow-up")
    if root_plan.get("follow_up_requirement") != "RASG-022":
        fail("root information architecture plan must name RASG-022 as follow_up_requirement")
    if root_plan.get("prism_gap_follow_up") != "RASG-023":
        fail("root information architecture plan must name RASG-023 as prism_gap_follow_up")
    migration_applied = root_plan.get("physical_migration_applied")
    if migration_applied is True:
        if root_plan.get("status") != ROOT_IA_APPLIED_STATUS:
            fail("root information architecture applied migration status is not the approved applied status")
        if not isinstance(root_plan.get("physical_convergence_result"), dict):
            fail("root information architecture applied migration must document physical_convergence_result")
        if rows["RASG-022"].get("status") != "done":
            fail("RASG-022 must be done when root information architecture migration is marked applied")
    elif migration_applied is not False:
        fail("root information architecture physical_migration_applied must be boolean")
    if rows["RASG-023"].get("status") not in {"planned", "in_progress", "done"}:
        fail("RASG-023 must remain visible until done")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate plan-only completion follow-up registration gates.")
    parser.add_argument("--fixtures", default=str(DEFAULT_FIXTURES))
    args = parser.parse_args()

    fixture_path = Path(args.fixtures)
    if not fixture_path.is_absolute():
        fixture_path = ROOT / fixture_path

    policy = load_json(POLICY, "conclusion prism policy")
    backlog = load_json(BACKLOG, "architecture smell backlog")
    root_plan = load_json(ROOT_IA_PLAN, "root information architecture plan")
    fixtures = load_json(fixture_path, "plan-only follow-up fixtures")

    validate_policy(policy)
    validate_live_rasg_chain(backlog, root_plan)
    cases, negative = validate_fixtures(fixtures, backlog_by_id(backlog))

    print("PLAN_ONLY_FOLLOWUP_REGISTRATION_OK")
    print(f"cases={cases} negative={negative}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

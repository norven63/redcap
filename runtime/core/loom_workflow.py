#!/usr/bin/env python3
"""RedCap Loom 角色化工程工作流检查器。"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = REPO_ROOT / "assets" / "contracts" / "loom-workflow.json"
REQUIRED_ROLES = {
    "product_manager",
    "architect",
    "developer",
    "tester",
    "reviewer",
    "cap_orchestrator",
}
REQUIRED_PHASES = {
    "idea_intake",
    "architecture_design",
    "implementation",
    "quality_assurance",
    "review_and_acceptance",
    "change_intake",
    "closeout",
    "blocked",
}
REQUIRED_LINEAR_TRANSITIONS = {
    ("idea_intake", "architecture_design"),
    ("architecture_design", "implementation"),
    ("implementation", "quality_assurance"),
    ("quality_assurance", "review_and_acceptance"),
    ("review_and_acceptance", "closeout"),
}
REQUIRED_FAILURE_ROUTES = {
    ("quality_assurance", "code", "implementation"),
    ("quality_assurance", "design", "architecture_design"),
    ("quality_assurance", "requirement", "idea_intake"),
    ("review_and_acceptance", "change", "change_intake"),
}


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def string_set(items: Any, key: str | None = None) -> set[str]:
    result: set[str] = set()
    if not isinstance(items, list):
        return result
    for item in items:
        if key is None:
            if isinstance(item, str) and item.strip():
                result.add(item)
        elif isinstance(item, dict) and isinstance(item.get(key), str) and item[key].strip():
            result.add(item[key])
    return result


def validate_phase(phase: dict[str, Any], failures: list[str]) -> None:
    phase_id = phase.get("id")
    for key in ["id", "role", "name"]:
        if not (isinstance(phase.get(key), str) and phase[key].strip()):
            failures.append(f"{phase_id or '<unknown>'}: {key} 必须是非空字符串")
    for key in ["required_inputs", "required_outputs", "evidence_required"]:
        values = phase.get(key)
        if not isinstance(values, list) or not values or not all(isinstance(item, str) and item.strip() for item in values):
            failures.append(f"{phase_id}: {key} 必须是非空字符串列表")


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-loom-workflow-contract":
        failures.append("Loom 工作流合同 schema_id 错误")
    if contract.get("roles_are_phases") is not True:
        failures.append("Loom 工作流必须声明角色是阶段")
    if contract.get("minimum_kernel_completion_allowed") is not False:
        failures.append("Loom 工作流不能允许最小内核替代完整工作流")
    roles = string_set(contract.get("required_roles"))
    missing_roles = sorted(REQUIRED_ROLES - roles)
    if missing_roles:
        failures.append(f"Loom 工作流缺少必需角色：{missing_roles}")
    phases = contract.get("phases")
    if not isinstance(phases, list) or not phases:
        failures.append("Loom 工作流缺少阶段")
        phases = []
    phase_ids = string_set(phases, "id")
    missing_phases = sorted(REQUIRED_PHASES - phase_ids)
    if missing_phases:
        failures.append(f"Loom 工作流缺少必需阶段：{missing_phases}")
    phase_roles = {
        str(phase.get("role"))
        for phase in phases
        if isinstance(phase, dict) and phase.get("role")
    }
    unbound_roles = sorted(REQUIRED_ROLES - phase_roles)
    if unbound_roles:
        failures.append(f"Loom 工作流角色没有绑定阶段：{unbound_roles}")
    for phase in phases:
        if isinstance(phase, dict):
            validate_phase(phase, failures)
        else:
            failures.append("Loom 工作流阶段必须是对象")
    transitions = contract.get("transitions")
    if not isinstance(transitions, list) or not transitions:
        failures.append("Loom 工作流缺少转移")
        transitions = []
    transition_pairs = {
        (str(item.get("from")), str(item.get("to")))
        for item in transitions
        if isinstance(item, dict)
    }
    missing_transitions = sorted(REQUIRED_LINEAR_TRANSITIONS - transition_pairs)
    if missing_transitions:
        failures.append(f"Loom 工作流缺少主线转移：{missing_transitions}")
    for item in transitions:
        if not isinstance(item, dict):
            failures.append("Loom 工作流转移必须是对象")
            continue
        for key in ["from", "to", "trigger"]:
            if not (isinstance(item.get(key), str) and item[key].strip()):
                failures.append(f"转移 {item}: {key} 必须是非空字符串")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(isinstance(value, str) and value.strip() for value in evidence):
            failures.append(f"转移 {item.get('from')}->{item.get('to')} 缺少证据要求")
        if item.get("from") not in phase_ids or item.get("to") not in phase_ids:
            failures.append(f"转移引用未知阶段：{item.get('from')}->{item.get('to')}")
    routes = contract.get("failure_routes")
    if not isinstance(routes, list) or not routes:
        failures.append("Loom 工作流缺少失败回流")
        routes = []
    route_tuples = {
        (str(item.get("from")), str(item.get("root_cause")), str(item.get("to")))
        for item in routes
        if isinstance(item, dict)
    }
    missing_routes = sorted(REQUIRED_FAILURE_ROUTES - route_tuples)
    if missing_routes:
        failures.append(f"Loom 工作流缺少根因回流：{missing_routes}")
    rules = contract.get("completion_rules")
    if not isinstance(rules, dict):
        failures.append("Loom 工作流缺少完成规则")
    else:
        expected = {
            "closeout_requires_all_roles": True,
            "closeout_requires_terminal_acceptance": True,
            "phase_skipping_allowed": False,
            "report_or_receipt_alone_can_complete": False,
        }
        for key, value in expected.items():
            if rules.get(key) is not value:
                failures.append(f"完成规则 {key} 必须为 {value}")
    return failures


def check(contract_path: pathlib.Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    failures = validate_contract(contract)
    return {
        "schema_id": "redcap-loom-workflow-check",
        "ok": not failures,
        "contract": str(contract_path),
        "roles": sorted(string_set(contract.get("required_roles"))),
        "phases": sorted(string_set(contract.get("phases"), "id")),
        "failures": failures,
    }


def cmd_check(args: argparse.Namespace) -> int:
    result = check(pathlib.Path(args.contract).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_LOOM_WORKFLOW_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    good = load_json(DEFAULT_CONTRACT)
    failures: list[str] = []
    if validate_contract(good):
        failures.append("当前 Loom 工作流合同不应在自检样例中失败")
    missing_role = json.loads(json.dumps(good, ensure_ascii=False))
    missing_role["required_roles"] = [role for role in missing_role["required_roles"] if role != "tester"]
    if not any("必需角色" in item for item in validate_contract(missing_role)):
        failures.append("缺少测试角色的样例没有失败")
    skip_qa = json.loads(json.dumps(good, ensure_ascii=False))
    skip_qa["transitions"] = [
        item for item in skip_qa["transitions"]
        if not (item.get("from") == "implementation" and item.get("to") == "quality_assurance")
    ]
    if not any("主线转移" in item for item in validate_contract(skip_qa)):
        failures.append("跳过测试阶段的样例没有失败")
    bad_completion = json.loads(json.dumps(good, ensure_ascii=False))
    bad_completion["completion_rules"]["report_or_receipt_alone_can_complete"] = True
    if not any("report_or_receipt" in item for item in validate_contract(bad_completion)):
        failures.append("报告或回执单独完成的样例没有失败")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_LOOM_WORKFLOW_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap Loom 角色化工程工作流检查器")
    sub = parser.add_subparsers(dest="command", required=True)
    check_cmd = sub.add_parser("check")
    check_cmd.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    check_cmd.set_defaults(func=cmd_check)
    self_check = sub.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

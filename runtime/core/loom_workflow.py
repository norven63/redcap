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
REQUIRED_HOOK_EVENTS = {
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Stop",
}
REQUIRED_SESSION_FIELDS = {
    "project_id",
    "task_id",
    "role",
    "session_id",
    "provider",
    "started_at",
    "last_seen_at",
    "context_state",
    "handoff_inputs",
    "handoff_outputs",
}
REQUIRED_PRISM_ASSISTANCE = {
    "requirements_clarification_review",
    "architecture_review",
    "code_review",
    "test_review",
    "documentation_review",
    "session_loss_recovery",
}
REQUIRED_PRISM_EVIDENCE = {
    "prism_request",
    "provider_reviews",
    "merge_or_resolution",
    "cap_decision",
}
REQUIRED_FAILURE_LOOP_ROUTE_FIELDS = {
    "route_id",
    "project_id",
    "task_id",
    "source_role",
    "source_phase",
    "root_cause",
    "root_cause_hash",
    "target_role",
    "target_phase",
    "restart_from_phase",
    "downstream_replay_required",
    "evidence",
    "loop_count",
    "previous_route_id",
    "escalation_threshold",
    "status",
}
REQUIRED_FAILURE_ROUTE_STATUSES = {
    "open",
    "accepted",
    "completed",
    "rejected",
    "escalated",
}
REQUIRED_FAILURE_ACCEPTANCE_FIELDS = {
    "accepted_by",
    "accepted_at",
    "route_id",
}
REQUIRED_FAILURE_COMPLETION_FIELDS = {
    "completed_by",
    "completed_at",
    "evidence",
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


def validate_execution_runtime(contract: dict[str, Any], failures: list[str]) -> None:
    runtime = contract.get("execution_runtime")
    if not isinstance(runtime, dict):
        failures.append("Loom 工作流缺少 execution_runtime")
        return
    if runtime.get("required_host") != "codex-cli":
        failures.append("Loom 执行宿主必须是 codex-cli，才能承载项目级 Hook")
    if runtime.get("hook_carrier_required") is not True:
        failures.append("Loom 必须声明 Hook 承载为必需能力")
    hooks = set(runtime.get("required_hook_events", []) if isinstance(runtime.get("required_hook_events"), list) else [])
    missing_hooks = sorted(REQUIRED_HOOK_EVENTS - hooks)
    if missing_hooks:
        failures.append(f"Loom Hook 事件要求缺失：{missing_hooks}")
    providers = runtime.get("allowed_role_providers")
    if providers != ["codex-cli"]:
        failures.append("Loom 角色执行方必须限定为 codex-cli，其他 AI 只能作为评审协助方")

    policy = runtime.get("role_session_policy")
    if not isinstance(policy, dict):
        failures.append("Loom 工作流缺少 role_session_policy")
        return
    expected_true = {
        "session_id_required": "Loom 角色必须持久记录 session_id",
        "same_role_must_resume_same_session": "同一角色必须续用同一 session_id",
        "session_loss_alarm_required": "session_id 丢失必须报警",
    }
    for key, message in expected_true.items():
        if policy.get(key) is not True:
            failures.append(message)
    if policy.get("session_scope") != "project_id + task_id + role":
        failures.append("Loom session_id 作用域必须绑定 project_id + task_id + role")
    if policy.get("lost_session_effect") != "mark_role_context_degraded_and_require_assisted_review":
        failures.append("Loom session_id 丢失后必须标记上下文降级并要求协助评审")
    fields = set(policy.get("manifest_required_fields", []) if isinstance(policy.get("manifest_required_fields"), list) else [])
    missing_fields = sorted(REQUIRED_SESSION_FIELDS - fields)
    if missing_fields:
        failures.append(f"Loom 角色会话清单字段缺失：{missing_fields}")


def validate_prism_assistance(contract: dict[str, Any], failures: list[str]) -> None:
    policy = contract.get("prism_assistance_policy")
    if not isinstance(policy, dict):
        failures.append("Loom 工作流缺少 prism_assistance_policy")
        return
    if policy.get("allowed") is not True:
        failures.append("Loom 必须允许角色调用棱镜协助复杂评审")
    required_for = set(policy.get("required_for", []) if isinstance(policy.get("required_for"), list) else [])
    missing_required = sorted(REQUIRED_PRISM_ASSISTANCE - required_for)
    if missing_required:
        failures.append(f"Loom 棱镜协助场景缺失：{missing_required}")
    if policy.get("providers") != ["kimi", "claude-code"]:
        failures.append("Loom 棱镜协助方必须显式限定为 kimi 和 claude-code")
    evidence = set(policy.get("evidence_required", []) if isinstance(policy.get("evidence_required"), list) else [])
    missing_evidence = sorted(REQUIRED_PRISM_EVIDENCE - evidence)
    if missing_evidence:
        failures.append(f"Loom 棱镜协助证据缺失：{missing_evidence}")
    rule = str(policy.get("role_decision_rule") or "")
    if "Cap" not in rule or "blindly" not in rule:
        failures.append("Loom 必须声明 Cap 不能盲从或无理由否决棱镜")


def validate_failure_loop_policy(contract: dict[str, Any], failures: list[str]) -> None:
    policy = contract.get("failure_loop_policy")
    if not isinstance(policy, dict):
        failures.append("Loom 工作流缺少 failure_loop_policy，失败回流不能只停留在转移表")
        return

    boundary = policy.get("cap_boundary")
    if not isinstance(boundary, dict):
        failures.append("Loom 失败循环缺少 cap_boundary")
    else:
        expected = {
            "cap_may_route_failure": True,
            "cap_may_modify_target_project": False,
            "runner_may_generate_failure_route_plan": True,
            "runner_may_generate_fix_patch": False,
            "tester_or_reviewer_may_fix_project": False,
        }
        for key, value in expected.items():
            if boundary.get(key) is not value:
                failures.append(f"Loom 失败循环边界 {key} 必须为 {value}")

    fields = set(policy.get("route_schema_required_fields", []) if isinstance(policy.get("route_schema_required_fields"), list) else [])
    missing_fields = sorted(REQUIRED_FAILURE_LOOP_ROUTE_FIELDS - fields)
    if missing_fields:
        failures.append(f"Loom 失败路由字段缺失：{missing_fields}")

    consume = policy.get("consume_policy")
    if not isinstance(consume, dict):
        failures.append("Loom 失败循环缺少 consume_policy，目标角色无法被强制接收失败路由")
    else:
        if consume.get("target_role_must_acknowledge") is not True:
            failures.append("Loom 失败路由目标角色必须显式接收")
        if consume.get("target_role_must_read_route_before_edit") is not True:
            failures.append("Loom 失败路由目标角色必须先读路由再修改")
        statuses = set(consume.get("allowed_statuses", []) if isinstance(consume.get("allowed_statuses"), list) else [])
        missing_statuses = sorted(REQUIRED_FAILURE_ROUTE_STATUSES - statuses)
        if missing_statuses:
            failures.append(f"Loom 失败路由状态缺失：{missing_statuses}")
        acceptance = set(consume.get("acceptance_evidence_required", []) if isinstance(consume.get("acceptance_evidence_required"), list) else [])
        missing_acceptance = sorted(REQUIRED_FAILURE_ACCEPTANCE_FIELDS - acceptance)
        if missing_acceptance:
            failures.append(f"Loom 失败路由接收证据缺失：{missing_acceptance}")
        completion = set(consume.get("completion_evidence_required", []) if isinstance(consume.get("completion_evidence_required"), list) else [])
        missing_completion = sorted(REQUIRED_FAILURE_COMPLETION_FIELDS - completion)
        if missing_completion:
            failures.append(f"Loom 失败路由完成证据缺失：{missing_completion}")

    anti_loop = policy.get("anti_loop_policy")
    if not isinstance(anti_loop, dict):
        failures.append("Loom 失败循环缺少 anti_loop_policy，容易复发无限 E2E 重跑")
    else:
        if not isinstance(anti_loop.get("max_same_root_cause_routes"), int) or anti_loop["max_same_root_cause_routes"] < 1:
            failures.append("Loom 失败循环 max_same_root_cause_routes 必须是正整数")
        if not isinstance(anti_loop.get("escalation_threshold"), int) or anti_loop["escalation_threshold"] < 1:
            failures.append("Loom 失败循环 escalation_threshold 必须是正整数")
        if anti_loop.get("max_same_root_cause_routes") != anti_loop.get("escalation_threshold"):
            failures.append("Loom 失败循环 max_same_root_cause_routes 与 escalation_threshold 必须保持一致，避免双标准")
        if not isinstance(anti_loop.get("deadlock_timeout_seconds"), int) or anti_loop["deadlock_timeout_seconds"] < 60:
            failures.append("Loom 失败循环 deadlock_timeout_seconds 必须足够明确")
        if anti_loop.get("repeated_route_effect") != "mark_escalated_and_stop_auto_rerun":
            failures.append("Loom 失败循环重复根因必须升级并停止自动盲目重跑")
        if anti_loop.get("no_blind_rerun_without_source_or_evidence_delta") is not True:
            failures.append("Loom 失败循环必须禁止无源码或证据变化的盲目重跑")
        escalation_path = anti_loop.get("escalation_path")
        if not isinstance(escalation_path, list) or "cap_orchestrator" not in escalation_path:
            failures.append("Loom 失败循环升级路径必须包含 cap_orchestrator")


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
    validate_execution_runtime(contract, failures)
    validate_prism_assistance(contract, failures)
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
    validate_failure_loop_policy(contract, failures)
    rules = contract.get("completion_rules")
    if not isinstance(rules, dict):
        failures.append("Loom 工作流缺少完成规则")
    else:
        expected = {
            "closeout_requires_all_roles": True,
            "closeout_requires_terminal_acceptance": True,
            "closeout_requires_role_session_manifest": True,
            "closeout_requires_prism_assistance_decisions": True,
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
    missing_session = json.loads(json.dumps(good, ensure_ascii=False))
    missing_session["execution_runtime"]["role_session_policy"].pop("session_id_required", None)
    if not any("session_id" in item for item in validate_contract(missing_session)):
        failures.append("缺少角色 session_id 要求的样例没有失败")
    missing_alarm = json.loads(json.dumps(good, ensure_ascii=False))
    missing_alarm["execution_runtime"]["role_session_policy"]["session_loss_alarm_required"] = False
    if not any("丢失" in item or "报警" in item for item in validate_contract(missing_alarm)):
        failures.append("缺少 session 丢失报警的样例没有失败")
    missing_prism = json.loads(json.dumps(good, ensure_ascii=False))
    missing_prism["prism_assistance_policy"]["required_for"] = ["code_review"]
    if not any("棱镜协助场景缺失" in item for item in validate_contract(missing_prism)):
        failures.append("缺少棱镜协助场景的样例没有失败")
    missing_failure_policy = json.loads(json.dumps(good, ensure_ascii=False))
    missing_failure_policy.pop("failure_loop_policy", None)
    if not any("failure_loop_policy" in item for item in validate_contract(missing_failure_policy)):
        failures.append("缺少失败循环策略的样例没有失败")
    cap_can_modify = json.loads(json.dumps(good, ensure_ascii=False))
    cap_can_modify["failure_loop_policy"]["cap_boundary"]["cap_may_modify_target_project"] = True
    if not any("cap_may_modify_target_project" in item for item in validate_contract(cap_can_modify)):
        failures.append("允许 Cap 直接修改目标项目的样例没有失败")
    missing_consume = json.loads(json.dumps(good, ensure_ascii=False))
    missing_consume["failure_loop_policy"].pop("consume_policy", None)
    if not any("consume_policy" in item for item in validate_contract(missing_consume)):
        failures.append("缺少目标角色消费策略的样例没有失败")
    weak_loop = json.loads(json.dumps(good, ensure_ascii=False))
    weak_loop["failure_loop_policy"]["anti_loop_policy"]["no_blind_rerun_without_source_or_evidence_delta"] = False
    if not any("盲目重跑" in item for item in validate_contract(weak_loop)):
        failures.append("允许无变化盲目重跑的样例没有失败")
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

#!/usr/bin/env python3
"""RedCap 复活后续缺口闭环检查器。"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_QUEUE = REPO_ROOT / "assets" / "contracts" / "revival-followthrough-queue.json"
DEFAULT_OPEN_LOOP_QUEUE = REPO_ROOT / "assets" / "contracts" / "open-loop-closure-queue.json"
REQUIRED_ITEM_IDS = {
    "RF-01-followthrough-queue",
    "RF-02-loom-runtime-session-quality",
    "RF-03-self-purification-operational-loop",
    "RF-04-cap-persona-private-boundary",
    "RF-05-e2e-iteration-engine",
}
REQUIRED_LOOM_ROLES = {
    "product_manager",
    "architect",
    "developer",
    "tester",
    "reviewer",
}
REQUIRED_E2E_FILES = {
    "loom-role-session-manifest.json",
    "loom-role-session-manifest-pre-review.json",
    "role-gate-clearance-summary.json",
    "prism-assisted-review.json",
    "knowledge-retrieval-evidence.json",
    "self-purification-candidates.json",
    "persona-distillation-decision.json",
    "test-results.json",
    "negative-probes.json",
    "runner-negative-contract-probe.json",
    "runner-character-player-contract-probe.json",
    "final-runner-test-results.json",
    "final-marker-validation.json",
    "browser-inspection.json",
    "file-browser-inspection.json",
    "behavioral-browser-verification.json",
    "independent-browser-verification.json",
    "final-evidence-bundle.json",
    "independent-observer.json",
    "visual-independence-report.json",
    "self-referential-boundary.json",
    "convergence-diagnosis.json",
    "final-prism-review.json",
    "failure-backlog.json",
    "iteration-verdict.json",
    "completion-marker.json",
}
REQUIRED_EVIDENCE_CHECKS = {
    "loom-role-session-manifest.json",
    "loom-role-session-manifest-pre-review.json",
    "role-gate-clearance-summary.json",
    "prism-assisted-review.json",
    "knowledge-retrieval-evidence.json",
    "self-purification-candidates.json",
    "persona-distillation-decision.json",
    "test-results.json",
    "negative-probes.json",
    "runner-negative-contract-probe.json",
    "runner-character-player-contract-probe.json",
    "final-runner-test-results.json",
    "final-marker-validation.json",
    "browser-inspection.json",
    "file-browser-inspection.json",
    "behavioral-browser-verification.json",
    "independent-browser-verification.json",
    "final-evidence-bundle.json",
    "independent-observer.json",
    "visual-independence-report.json",
    "self-referential-boundary.json",
    "convergence-diagnosis.json",
    "final-prism-review.json",
    "failure-backlog.json",
    "iteration-verdict.json",
    "completion-marker.json",
}
SELF_PURIFICATION_ALLOWED_DECISIONS = {"promote_public", "keep_private", "no_promote", "defer_with_owner"}
OPEN_LOOP_CLOSING_STATUSES = {"verified", "runtime-verified", "runtime-verified-manual-boundary"}
OPEN_LOOP_OPEN_STATUSES = {"open", "runtime-gated-in-progress", "planned", "in-progress"}
OPEN_LOOP_REQUIRED_EXIT_MARKERS = ["runtime_checks", "证据文件", "棱镜", "外部项目", "failure_backlog", "P0/P1"]
OPEN_LOOP_REQUIRED_TRUE_RULES = [
    "new_issue_must_enter_queue",
    "open_p0_blocks_second_e2e",
    "failure_backlog_blocks_completion",
]


def collect_self_purification_decisions(purification: dict[str, Any]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    top_level = purification.get("decisions")
    if isinstance(top_level, list):
        collected.extend(decision for decision in top_level if isinstance(decision, dict))
    candidates = purification.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            candidate_id = candidate.get("id")
            nested = candidate.get("decisions")
            if not isinstance(nested, list):
                continue
            for decision in nested:
                if not isinstance(decision, dict):
                    continue
                normalized = dict(decision)
                if candidate_id and "candidate_id" not in normalized and "id" not in normalized:
                    normalized["candidate_id"] = candidate_id
                collected.append(normalized)
    return collected


def validate_self_purification_decisions(decisions: list[dict[str, Any]], failures: list[str]) -> None:
    if not decisions:
        failures.append("self-purification-candidates 必须包含顶层或候选内嵌 decisions")
        return
    for decision in decisions:
        label = decision.get("decision")
        if label not in SELF_PURIFICATION_ALLOWED_DECISIONS:
            failures.append(f"自我净化 decision 无效：{label}")
        if label == "no_promote" and not decision.get("reason"):
            failures.append("no_promote 决策必须写明 reason")
SESSION_ID_RE = re.compile(
    r"^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{8,}|session_[a-zA-Z0-9_-]+)$"
)
PRIVATE_PERSONA_MARKERS = [
    "private_identity_body",
    "raw_persona_body",
    "cap_private_body",
    "persona_private_body",
    "身份正文",
    "人格正文原文",
    "私有人格正文",
]
PUBLIC_SCAN_ROOTS = [
    REPO_ROOT / "assets" / "knowledge",
    REPO_ROOT / "assets" / "docs",
]


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取 JSON：{path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON 必须是对象：{path}")
    return payload


def load_optional_json(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def rel_or_abs_exists(base: pathlib.Path, value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    path = pathlib.Path(value)
    if path.is_absolute():
        return path.exists()
    return (base / path).exists() or (REPO_ROOT / path).exists()


def validate_queue(path: pathlib.Path = DEFAULT_QUEUE) -> list[str]:
    payload = load_json(path)
    failures: list[str] = []
    if payload.get("schema_id") != "redcap-revival-followthrough-queue":
        failures.append("followthrough 队列 schema_id 错误")
    if payload.get("status") != "runtime-gated":
        failures.append("followthrough 队列必须声明 runtime-gated")
    anti_rule = str(payload.get("anti_completion_rule") or "")
    if "队列" not in anti_rule or "不是" not in anti_rule:
        failures.append("followthrough 队列必须声明队列本身不能作为完成证据")
    loop_rules = payload.get("loop_rules")
    if not isinstance(loop_rules, dict):
        failures.append("followthrough 队列缺少 loop_rules")
    else:
        expected_true = [
            "failure_backlog_blocks_ready",
            "closed_non_blocking_forbidden",
            "next_round_required_when_open_items_exist",
            "queue_item_must_name_runtime_check",
        ]
        for key in expected_true:
            if loop_rules.get(key) is not True:
                failures.append(f"loop_rules.{key} 必须为 true")
        limit = loop_rules.get("same_root_cause_failure_limit")
        if not isinstance(limit, int) or limit < 2:
            failures.append("loop_rules.same_root_cause_failure_limit 必须是至少 2 的整数")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        failures.append("followthrough 队列缺少 items")
        return failures
    item_ids = {item.get("id") for item in items if isinstance(item, dict)}
    missing_items = sorted(REQUIRED_ITEM_IDS - item_ids)
    if missing_items:
        failures.append(f"followthrough 队列缺少条目：{missing_items}")
    for item in items:
        if not isinstance(item, dict):
            failures.append("followthrough 队列条目必须是对象")
            continue
        item_id = str(item.get("id") or "<unknown>")
        if item.get("hard_gate") is not True:
            failures.append(f"{item_id}: hard_gate 必须为 true")
        if not isinstance(item.get("root_cause_category"), str) or not item["root_cause_category"].strip():
            failures.append(f"{item_id}: 必须记录 root_cause_category")
        for key in ["acceptance", "runtime_checks", "evidence_required"]:
            values = item.get(key)
            if not isinstance(values, list) or not values or not all(isinstance(value, str) and value.strip() for value in values):
                failures.append(f"{item_id}: {key} 必须是非空字符串列表")
        checks_text = "\n".join(str(value) for value in item.get("runtime_checks", []))
        if item_id == "RF-02-loom-runtime-session-quality" and "revival-followthrough e2e-check" not in checks_text:
            failures.append("RF-02 必须由 e2e-check 验证真实角色证据")
        if item_id == "RF-05-e2e-iteration-engine" and "complete-revival-e2e run" not in checks_text:
            failures.append("RF-05 必须绑定真实 E2E 运行命令")
    return failures


def validate_open_loop_queue(path: pathlib.Path = DEFAULT_OPEN_LOOP_QUEUE) -> dict[str, Any]:
    payload = load_json(path)
    failures: list[str] = []
    closeout_blockers: list[str] = []
    if payload.get("schema_id") != "redcap-open-loop-closure-queue":
        failures.append("open-loop 队列 schema_id 错误")
    if payload.get("status") not in {"runtime-gated-in-progress", "verified"}:
        failures.append("open-loop 队列 status 必须是 runtime-gated-in-progress 或 verified")
    anti_rule = str(payload.get("anti_completion_rule") or "")
    if "不是 RedCap 完整复活完成证据" not in anti_rule:
        failures.append("open-loop 队列必须声明队列自身不是完整复活完成证据")
    exit_criteria = payload.get("exit_criteria")
    if not isinstance(exit_criteria, list) or not exit_criteria or not all(isinstance(item, str) and item.strip() for item in exit_criteria):
        failures.append("open-loop 队列 exit_criteria 必须是非空字符串列表")
    else:
        joined = "\n".join(exit_criteria)
        for marker in OPEN_LOOP_REQUIRED_EXIT_MARKERS:
            if marker not in joined:
                failures.append(f"open-loop exit_criteria 缺少机器可判定关键片段：{marker}")
    loop_rules = payload.get("loop_rules")
    if not isinstance(loop_rules, dict):
        failures.append("open-loop 队列缺少 loop_rules")
    else:
        for key in OPEN_LOOP_REQUIRED_TRUE_RULES:
            if loop_rules.get(key) is not True:
                failures.append(f"open-loop loop_rules.{key} 必须为 true")
        if loop_rules.get("same_root_cause_failure_limit") != 3:
            failures.append("open-loop same_root_cause_failure_limit 必须为 3")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        failures.append("open-loop 队列 items 必须非空")
        items = []
    for item in items:
        if not isinstance(item, dict):
            failures.append("open-loop 队列条目必须是对象")
            continue
        item_id = str(item.get("id") or "<unknown>")
        priority = str(item.get("priority") or "")
        status = str(item.get("status") or "")
        for key in ["title", "root_cause"]:
            if not isinstance(item.get(key), str) or not item[key].strip():
                failures.append(f"{item_id}: {key} 必须非空")
        for key in ["required_change", "runtime_checks", "evidence_required", "exit_criteria", "promotion_criteria"]:
            values = item.get(key)
            if not isinstance(values, list) or not values or not all(isinstance(value, str) and value.strip() for value in values):
                failures.append(f"{item_id}: {key} 必须是非空字符串列表")
        if status in OPEN_LOOP_CLOSING_STATUSES:
            evidence = item.get("verified_runtime_evidence")
            if not isinstance(evidence, list) or not evidence:
                failures.append(f"{item_id}: 关闭状态必须包含 verified_runtime_evidence")
            prism_status = item.get("prism_review")
            if priority in {"P0", "P1"} and prism_status not in {"passed", "resolved", "not_required"}:
                closeout_blockers.append(f"{item_id}: P0/P1 关闭前缺少棱镜复核状态")
        elif priority in {"P0", "P1"}:
            closeout_blockers.append(f"{item_id}: {priority} 仍未 verified，当前状态 {status}")
    closeout_allowed = not failures and not closeout_blockers
    return {
        "schema_id": "redcap-open-loop-closure-queue-check",
        "ok": not failures,
        "queue": str(path),
        "closeout_allowed": closeout_allowed,
        "closeout_blockers": closeout_blockers,
        "open_p0_p1_count": len(closeout_blockers),
        "failures": failures,
    }


def open_loop_closeout_rules() -> dict[str, Any]:
    return {
        "schema_id": "redcap-open-loop-closeout-rules",
        "closing_statuses": sorted(OPEN_LOOP_CLOSING_STATUSES),
        "open_statuses": sorted(OPEN_LOOP_OPEN_STATUSES),
        "required_exit_markers": OPEN_LOOP_REQUIRED_EXIT_MARKERS,
        "required_true_loop_rules": OPEN_LOOP_REQUIRED_TRUE_RULES,
        "same_root_cause_failure_limit": 3,
        "closeout_formula": "closeout_allowed = failures 为空且 closeout_blockers 为空",
        "closing_item_requirements": [
            "关闭状态条目必须包含 verified_runtime_evidence",
            "P0/P1 关闭状态条目必须包含 prism_review=passed|resolved|not_required",
            "非 verified 的 P0/P1 必须进入 closeout_blockers",
        ],
        "boundary": "本规则只允许关闭 open-loop 队列；不允许声明 RedCap 完整复活。",
    }


def public_persona_boundary_rules() -> dict[str, Any]:
    return {
        "schema_id": "redcap-public-persona-boundary-rules",
        "public_scan_roots": [str(path.relative_to(REPO_ROOT)) for path in PUBLIC_SCAN_ROOTS],
        "scanned_extensions": [".json", ".md", ".txt"],
        "private_markers": PRIVATE_PERSONA_MARKERS,
        "match_rule": "对文本和标记做 casefold 后执行包含匹配",
        "failure_rule": "公共资产命中任一私有人格正文标记即失败",
        "private_storage_policy": "Cap 私有人格正文只允许保存在 $CAP_HOME 或 ~/.cap，不允许进入 RedCap 公共仓库。",
    }


def runtime_rule_report() -> dict[str, Any]:
    return {
        "schema_id": "redcap-runtime-rule-report",
        "open_loop_closeout": open_loop_closeout_rules(),
        "public_persona_boundary": public_persona_boundary_rules(),
    }


def scan_public_persona_boundary(roots: list[pathlib.Path] | None = None) -> list[str]:
    failures: list[str] = []
    for root in roots or PUBLIC_SCAN_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_dir() or path.suffix.lower() not in {".json", ".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            lowered = text.casefold()
            leaked = [marker for marker in PRIVATE_PERSONA_MARKERS if marker.casefold() in lowered]
            if leaked:
                try:
                    rel = path.relative_to(REPO_ROOT).as_posix()
                except ValueError:
                    rel = str(path)
                failures.append(f"公共资产疑似包含私有人格正文标记：{rel}: {leaked}")
    return failures


def validate_role_manifest(evidence_root: pathlib.Path, failures: list[str]) -> None:
    manifest = load_optional_json(evidence_root / "loom-role-session-manifest.json")
    if manifest is None:
        failures.append("缺少或无法读取 loom-role-session-manifest.json")
        return
    roles = manifest.get("roles")
    if not isinstance(roles, list) or not roles:
        failures.append("loom-role-session-manifest.roles 必须是非空列表")
        return
    seen_roles: set[str] = set()
    session_by_role: dict[str, str] = {}
    for role in roles:
        if not isinstance(role, dict):
            failures.append("Loom 角色条目必须是对象")
            continue
        role_id = str(role.get("role") or "")
        if role_id:
            seen_roles.add(role_id)
        if role_id in REQUIRED_LOOM_ROLES:
            session_id = str(role.get("session_id") or "")
            if not SESSION_ID_RE.fullmatch(session_id):
                failures.append(f"{role_id}: session_id 缺失或不像真实会话标识")
            else:
                session_by_role[role_id] = session_id
            if role.get("provider") != "codex-cli":
                failures.append(f"{role_id}: provider 必须是 codex-cli")
            if role.get("context_state") != "complete":
                failures.append(f"{role_id}: context_state 必须是 complete")
            if role.get("alarm"):
                failures.append(f"{role_id}: 角色存在报警，不能判定 E2E 通过")
            for key in ["role_workspace", "handoff_inputs", "handoff_outputs", "evidence_files"]:
                value = role.get(key)
                if not isinstance(value, list) or not value:
                    failures.append(f"{role_id}: {key} 必须是非空列表")
            for evidence_file in role.get("evidence_files", []) if isinstance(role.get("evidence_files"), list) else []:
                if not rel_or_abs_exists(evidence_root, evidence_file):
                    failures.append(f"{role_id}: evidence_files 不存在：{evidence_file}")
    missing_roles = sorted(REQUIRED_LOOM_ROLES - seen_roles)
    if missing_roles:
        failures.append(f"Loom 角色清单缺少必需角色：{missing_roles}")
    if len(session_by_role) == len(REQUIRED_LOOM_ROLES):
        duplicates = sorted({session for session in session_by_role.values() if list(session_by_role.values()).count(session) > 1})
        if duplicates:
            failures.append(f"Loom 不同角色不能共用 session_id：{duplicates}")
    alarms = manifest.get("session_loss_alarms")
    if alarms:
        failures.append(f"Loom session_loss_alarms 必须为空才能通过：{alarms}")


def validate_role_gate_clearance(evidence_root: pathlib.Path, failures: list[str]) -> None:
    summary = load_optional_json(evidence_root / "role-gate-clearance-summary.json")
    if summary is None:
        failures.append("缺少或无法读取 role-gate-clearance-summary.json")
        return
    if summary.get("producer") != "e2e-runner":
        failures.append("role-gate-clearance-summary.producer 必须是 e2e-runner")
    if summary.get("runner_owns_full_prism") is not True:
        failures.append("role-gate-clearance-summary.runner_owns_full_prism 必须为 true")
    if summary.get("role_gate_self_block_forbidden") is not True:
        failures.append("role-gate-clearance-summary.role_gate_self_block_forbidden 必须为 true")
    roles = summary.get("roles")
    if not isinstance(roles, list) or not roles:
        failures.append("role-gate-clearance-summary.roles 必须是非空列表")
        return
    cleared_roles = {
        str(item.get("role"))
        for item in roles
        if isinstance(item, dict) and item.get("decision") == "cleared_for_external_project_role_execution"
    }
    missing = sorted(REQUIRED_LOOM_ROLES - cleared_roles)
    if missing:
        failures.append(f"role-gate-clearance-summary 缺少角色协调凭证：{missing}")
    for role in sorted(REQUIRED_LOOM_ROLES):
        clearance = load_optional_json(evidence_root / "role-gate-clearance" / f"{role}.json")
        if clearance is None:
            failures.append(f"缺少或无法读取 role-gate-clearance/{role}.json")
            continue
        if clearance.get("producer") != "e2e-runner":
            failures.append(f"{role}: 门禁协调凭证 producer 必须是 e2e-runner")
        if clearance.get("decision") != "cleared_for_external_project_role_execution":
            failures.append(f"{role}: 门禁协调凭证 decision 无效")
        forbidden = clearance.get("role_must_not_run_commands")
        if not isinstance(forbidden, list) or ".redcap/runtime/bin/redcap gate" not in forbidden:
            failures.append(f"{role}: 门禁协调凭证必须禁止角色自跑 redcap gate")


def validate_prism_assistance(evidence_root: pathlib.Path, failures: list[str]) -> None:
    payload = load_optional_json(evidence_root / "prism-assisted-review.json")
    if payload is None:
        failures.append("缺少或无法读取 prism-assisted-review.json")
        return
    if payload.get("used") is not True:
        failures.append("本轮 E2E 必须实际记录棱镜协助，不能只写 skip_reason")
    reviews = payload.get("reviews")
    if not isinstance(reviews, list) or not reviews:
        failures.append("prism-assisted-review.reviews 必须非空")
    if not isinstance(payload.get("cap_decision"), str) or not payload["cap_decision"].strip():
        failures.append("prism-assisted-review.cap_decision 必须非空")


def validate_knowledge_and_purification(evidence_root: pathlib.Path, failures: list[str]) -> None:
    retrieval = load_optional_json(evidence_root / "knowledge-retrieval-evidence.json")
    if retrieval is None:
        failures.append("缺少或无法读取 knowledge-retrieval-evidence.json")
    else:
        raw_result = retrieval.get("raw_result") if isinstance(retrieval.get("raw_result"), dict) else {}
        command = str(retrieval.get("command") or "")
        search_ran = retrieval.get("search_ran") is True or (
            retrieval.get("exit_code") == 0 and "knowledge-gateway search" in command
        )
        query = retrieval.get("query") if isinstance(retrieval.get("query"), str) else raw_result.get("query")
        matches = retrieval.get("matches") if isinstance(retrieval.get("matches"), list) else raw_result.get("matches")
        if search_ran is not True:
            failures.append("任务前知识检索必须实际运行，search_ran 必须为 true")
        if not isinstance(query, str) or not query.strip():
            failures.append("knowledge-retrieval-evidence.query 必须非空")
        if retrieval.get("skip_reason"):
            failures.append("E2E 可用性验收不接受跳过知识检索")
        if not (matches or retrieval.get("no_relevant_entry_reason")):
            failures.append("知识检索必须记录匹配项或无相关条目理由")

    purification = load_optional_json(evidence_root / "self-purification-candidates.json")
    if purification is None:
        failures.append("缺少或无法读取 self-purification-candidates.json")
        return
    candidates = purification.get("candidates")
    no_candidate_reason = purification.get("no_candidate_reason")
    if not candidates and not (isinstance(no_candidate_reason, str) and no_candidate_reason.strip()):
        failures.append("自我净化必须记录候选或无候选理由")
    validate_self_purification_decisions(collect_self_purification_decisions(purification), failures)

    test_results = load_optional_json(evidence_root / "test-results.json")
    if test_results is None:
        failures.append("缺少或无法读取 test-results.json")
    elif test_results.get("role") != "tester":
        failures.append("test-results.json 必须由 tester 角色产出，不能被验证脚本或其他角色覆盖")
    negative_probes = load_optional_json(evidence_root / "negative-probes.json")
    if negative_probes is None:
        failures.append("缺少或无法读取 negative-probes.json")
    elif negative_probes.get("role") != "tester":
        failures.append("negative-probes.json 必须由 tester 角色产出")


def validate_persona_boundary(evidence_root: pathlib.Path, failures: list[str]) -> None:
    payload = load_optional_json(evidence_root / "persona-distillation-decision.json")
    if payload is None:
        failures.append("缺少或无法读取 persona-distillation-decision.json")
        return
    if payload.get("privacy_class") != "cap-private":
        failures.append("persona-distillation-decision.privacy_class 必须是 cap-private")
    if payload.get("public_write") is not False:
        failures.append("Cap 人格沉淀 public_write 必须为 false")
    if payload.get("private_body_written") is not False:
        failures.append("Cap 人格沉淀 private_body_written 必须为 false")
    text = json.dumps(payload, ensure_ascii=False).casefold()
    leaked = [marker for marker in PRIVATE_PERSONA_MARKERS if marker.casefold() in text]
    if leaked:
        failures.append(f"persona-distillation-decision 含私有人格正文标记：{leaked}")
    if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
        failures.append("persona-distillation-decision.reason 必须非空")


def validate_failure_loop(evidence_root: pathlib.Path, failures: list[str]) -> None:
    convergence = load_optional_json(evidence_root / "convergence-diagnosis.json")
    if convergence is None:
        failures.append("缺少或无法读取 convergence-diagnosis.json")
    else:
        if convergence.get("producer") != "e2e-runner":
            failures.append("convergence-diagnosis.producer 必须是 e2e-runner")
        if convergence.get("final_prism_ok") is not True:
            failures.append("通过验收时 convergence-diagnosis.final_prism_ok 必须为 true")
        if convergence.get("strictest_verdict") != "pass":
            failures.append("通过验收时 convergence-diagnosis.strictest_verdict 必须是 pass")
        if convergence.get("auto_rerun_allowed") is not False:
            failures.append("通过验收时 convergence-diagnosis.auto_rerun_allowed 必须为 false，表示不需要继续循环")
    backlog = load_optional_json(evidence_root / "failure-backlog.json")
    if backlog is None:
        failures.append("缺少或无法读取 failure-backlog.json")
    else:
        open_items = backlog.get("open_items")
        if not isinstance(open_items, list):
            failures.append("failure-backlog.open_items 必须是列表")
        elif open_items:
            failures.append(f"failure-backlog 仍有开放项：{open_items}")
        if backlog.get("closed_non_blocking"):
            failures.append("failure-backlog.closed_non_blocking 禁止用于通过验收")
        if backlog.get("next_round_required") is True:
            failures.append("failure-backlog.next_round_required=true 时不能判定当前轮通过")
        closed_items = backlog.get("closed_items")
        if closed_items is not None and not isinstance(closed_items, list):
            failures.append("failure-backlog.closed_items 必须是列表")

    verdict = load_optional_json(evidence_root / "iteration-verdict.json")
    if verdict is None:
        failures.append("缺少或无法读取 iteration-verdict.json")
        return
    if verdict.get("status") != "pass":
        failures.append("iteration-verdict.status 必须是 pass")
    if verdict.get("ready_for_engineering_use") is not True:
        failures.append("iteration-verdict.ready_for_engineering_use 必须为 true")
    checked = verdict.get("evidence_checked")
    if not isinstance(checked, list) or not checked:
        failures.append("iteration-verdict.evidence_checked 必须非空")
    else:
        missing_checked = sorted(REQUIRED_EVIDENCE_CHECKS - {str(item) for item in checked})
        if missing_checked:
            failures.append(f"iteration-verdict.evidence_checked 缺少关键证据：{missing_checked}")


def validate_package_prism(evidence_root: pathlib.Path, failures: list[str]) -> None:
    payload = load_optional_json(evidence_root / "package-prism-check.json")
    if payload is None:
        failures.append("缺少或无法读取 package-prism-check.json")
        return
    if payload.get("ok") is not True or payload.get("exit_code") != 0:
        failures.append("package-prism-check 必须成功")
    if "PRISM_CHECK_OK" not in str(payload.get("stdout_tail") or ""):
        failures.append("package-prism-check 必须包含 PRISM_CHECK_OK")


def validate_runner_finalization(evidence_root: pathlib.Path, failures: list[str]) -> None:
    runner_tests = load_optional_json(evidence_root / "final-runner-test-results.json")
    if runner_tests is None:
        failures.append("缺少或无法读取 final-runner-test-results.json")
    else:
        if runner_tests.get("producer") != "e2e-runner":
            failures.append("final-runner-test-results.producer 必须是 e2e-runner")
        if runner_tests.get("ok") is not True or runner_tests.get("exit_code") != 0:
            failures.append("运行器独立重跑验证必须成功")
        if not runner_tests.get("detected_command"):
            failures.append("final-runner-test-results 必须记录 detected_command")
    marker_validation = load_optional_json(evidence_root / "final-marker-validation.json")
    if marker_validation is None:
        failures.append("缺少或无法读取 final-marker-validation.json")
    else:
        if marker_validation.get("producer") != "e2e-runner":
            failures.append("final-marker-validation.producer 必须是 e2e-runner")
        if marker_validation.get("ok") is not True or marker_validation.get("exit_code") != 0:
            failures.append("写 completion-marker 前的最终项目验证必须成功")
        if not marker_validation.get("detected_command"):
            failures.append("final-marker-validation 必须记录 detected_command")
        if not marker_validation.get("stdout_sha256"):
            failures.append("final-marker-validation 必须记录 stdout_sha256")
    browser = load_optional_json(evidence_root / "browser-inspection.json")
    if browser is None:
        failures.append("缺少或无法读取 browser-inspection.json")
    else:
        if browser.get("producer") != "e2e-runner":
            failures.append("browser-inspection.producer 必须是 e2e-runner")
        if browser.get("ok") is not True:
            failures.append("运行器浏览器检查必须成功")
        if not browser.get("screenshot"):
            failures.append("browser-inspection 必须记录截图证据")
    file_browser = load_optional_json(evidence_root / "file-browser-inspection.json")
    if file_browser is None:
        failures.append("缺少或无法读取 file-browser-inspection.json")
    else:
        if file_browser.get("producer") != "e2e-runner":
            failures.append("file-browser-inspection.producer 必须是 e2e-runner")
        if file_browser.get("ok") is not True:
            failures.append("file:// 浏览器检查必须成功")
        if file_browser.get("launch_mode") != "local-file-protocol":
            failures.append("file-browser-inspection.launch_mode 必须是 local-file-protocol")
        if not file_browser.get("screenshot"):
            failures.append("file-browser-inspection 必须记录截图证据")
    behavior = load_optional_json(evidence_root / "behavioral-browser-verification.json")
    if behavior is None:
        failures.append("缺少或无法读取 behavioral-browser-verification.json")
    else:
        if behavior.get("producer") != "e2e-runner":
            failures.append("behavioral-browser-verification.producer 必须是 e2e-runner")
        if behavior.get("ok") is not True:
            failures.append("运行器行为级浏览器验证必须成功")
        if not behavior.get("screenshot"):
            failures.append("behavioral-browser-verification 必须记录截图证据")

    bundle = load_optional_json(evidence_root / "final-evidence-bundle.json")
    if bundle is None:
        failures.append("缺少或无法读取 final-evidence-bundle.json")
    else:
        if bundle.get("producer") != "e2e-runner":
            failures.append("final-evidence-bundle.producer 必须是 e2e-runner")
        files = bundle.get("files")
        if not isinstance(files, list) or not files:
            failures.append("final-evidence-bundle.files 必须非空")
        else:
            indexed = {str(item.get("path")) for item in files if isinstance(item, dict)}
            for required in [
                "loom-role-session-manifest.json",
                "role-gate-clearance-summary.json",
                "package-prism-check.json",
                "runner-negative-contract-probe.json",
                "runner-character-player-contract-probe.json",
                "final-runner-test-results.json",
                "final-marker-validation.json",
                "browser-inspection.json",
                "file-browser-inspection.json",
                "behavioral-browser-verification.json",
                "independent-browser-verification.json",
            ]:
                if required not in indexed:
                    failures.append(f"final-evidence-bundle 缺少关键证据索引：{required}")
            for item in files:
                if not isinstance(item, dict) or item.get("exists") is not True:
                    continue
                if not isinstance(item.get("sha256"), str) or not item["sha256"].strip():
                    failures.append(f"final-evidence-bundle 已存在文件缺少 sha256：{item.get('path')}")
        if not isinstance(bundle.get("bundle_sha256"), str) or not bundle["bundle_sha256"].strip():
            failures.append("final-evidence-bundle.bundle_sha256 必须非空")

    final_prism = load_optional_json(evidence_root / "final-prism-review.json")
    if final_prism is None:
        failures.append("缺少或无法读取 final-prism-review.json")
    else:
        if final_prism.get("producer") != "e2e-runner":
            failures.append("final-prism-review.producer 必须是 e2e-runner")
        if final_prism.get("ok") is not True:
            failures.append(f"最终棱镜复核未通过：{final_prism.get('failures')}")
        if final_prism.get("strictest_verdict") != "pass":
            failures.append("final-prism-review.strictest_verdict 必须是 pass")
        reviews = final_prism.get("reviews")
        providers = {str(item.get("provider")) for item in reviews if isinstance(item, dict)} if isinstance(reviews, list) else set()
        if providers != {"kimi", "claude-code"}:
            failures.append(f"最终棱镜复核必须包含 Kimi 和 Claude Code：{sorted(providers)}")

    marker = load_optional_json(evidence_root / "completion-marker.json")
    if marker is None:
        failures.append("缺少或无法读取 completion-marker.json")
    else:
        if marker.get("producer") != "e2e-runner":
            failures.append("completion-marker.producer 必须是 e2e-runner，不能由 Loom 角色自证")
        if marker.get("ready_for_engineering_use") is not True:
            failures.append("completion-marker.ready_for_engineering_use 必须为 true")
        if marker.get("final_prism_strictest_verdict") != "pass":
            failures.append("completion-marker 必须绑定最终棱镜 pass 结果")
        if not isinstance(marker.get("validation_chain_scope"), dict):
            failures.append("completion-marker 必须包含 validation_chain_scope")
        if not isinstance(marker.get("not_claimed"), list) or not marker.get("not_claimed"):
            failures.append("completion-marker 必须包含 not_claimed")
        if not isinstance(marker.get("final_marker_validation"), dict) or marker["final_marker_validation"].get("ok") is not True:
            failures.append("completion-marker 必须引用通过的 final-marker-validation")
        if not isinstance(marker.get("file_browser_inspection"), dict) or marker["file_browser_inspection"].get("ok") is not True:
            failures.append("completion-marker 必须引用通过的 file-browser-inspection")
        marker_convergence = marker.get("convergence_diagnosis")
        if not isinstance(marker_convergence, dict) or marker_convergence.get("strictest_verdict") != "pass":
            failures.append("completion-marker 必须引用 strictest_verdict=pass 的 convergence-diagnosis")

    boundary = load_optional_json(evidence_root / "self-referential-boundary.json")
    if boundary is None:
        failures.append("缺少或无法读取 self-referential-boundary.json")
    else:
        if boundary.get("producer") != "e2e-runner":
            failures.append("self-referential-boundary.producer 必须是 e2e-runner")
        if boundary.get("ok") is not True:
            failures.append("self-referential-boundary 必须通过")
        scope = boundary.get("validation_chain_scope")
        if not isinstance(scope, dict) or scope.get("same_host") is not True or scope.get("same_redcap_package") is not True:
            failures.append("self-referential-boundary 必须声明 same_host 与 same_redcap_package")
        disclosure = boundary.get("completion_marker_disclosure")
        if not isinstance(disclosure, dict) or disclosure.get("must_copy_this_boundary") is not True:
            failures.append("self-referential-boundary 必须要求 completion-marker 复制边界披露")


def validate_e2e_evidence_quality(evidence_root: pathlib.Path) -> dict[str, Any]:
    failures: list[str] = []
    for rel in sorted(REQUIRED_E2E_FILES):
        if not (evidence_root / rel).is_file():
            failures.append(f"缺少 E2E 证据文件：{rel}")
    validate_role_manifest(evidence_root, failures)
    validate_role_gate_clearance(evidence_root, failures)
    validate_prism_assistance(evidence_root, failures)
    validate_knowledge_and_purification(evidence_root, failures)
    validate_persona_boundary(evidence_root, failures)
    validate_failure_loop(evidence_root, failures)
    validate_package_prism(evidence_root, failures)
    validate_runner_finalization(evidence_root, failures)
    return {
        "schema_id": "redcap-revival-followthrough-e2e-check",
        "ok": not failures,
        "evidence_root": str(evidence_root),
        "failures": failures,
    }


def check(queue_path: pathlib.Path = DEFAULT_QUEUE) -> dict[str, Any]:
    failures = validate_queue(queue_path)
    failures.extend(scan_public_persona_boundary())
    return {
        "schema_id": "redcap-revival-followthrough-check",
        "ok": not failures,
        "queue": str(queue_path),
        "failures": failures,
    }


def cmd_check(args: argparse.Namespace) -> int:
    result = check(pathlib.Path(args.queue).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_REVIVAL_FOLLOWTHROUGH_OK")
        return 0
    return 1


def cmd_e2e_check(args: argparse.Namespace) -> int:
    result = validate_e2e_evidence_quality(pathlib.Path(args.evidence_root).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_REVIVAL_FOLLOWTHROUGH_E2E_OK")
        return 0
    return 1


def cmd_open_loop_check(args: argparse.Namespace) -> int:
    result = validate_open_loop_queue(pathlib.Path(args.queue).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_OPEN_LOOP_CLOSURE_QUEUE_OK")
        return 0
    return 1


def cmd_rule_report(args: argparse.Namespace) -> int:
    result = runtime_rule_report()
    if args.out:
        out = pathlib.Path(args.out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("REDCAP_REVIVAL_FOLLOWTHROUGH_RULE_REPORT_OK")
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    if validate_queue(DEFAULT_QUEUE):
        failures.append("当前 followthrough 队列不应失败")
    current_open_loop = validate_open_loop_queue(DEFAULT_OPEN_LOOP_QUEUE)
    if current_open_loop.get("ok") is not True:
        failures.append(f"当前 open-loop 队列结构不应失败：{current_open_loop.get('failures')}")
    if current_open_loop.get("closeout_allowed") is True:
        failures.append("当前 open-loop 队列仍有未闭环 P0/P1，不应允许收口")
    with tempfile.TemporaryDirectory(prefix="redcap-followthrough-") as raw:
        root = pathlib.Path(raw)
        open_loop_fixture = load_json(DEFAULT_OPEN_LOOP_QUEUE)
        for item in open_loop_fixture["items"]:
            if item.get("priority") in {"P0", "P1"}:
                item["status"] = "verified"
                item["verified_runtime_evidence"] = ["fixture-runtime-check"]
                item["prism_review"] = "passed"
        open_loop_fixture["status"] = "verified"
        verified_queue = root / "open-loop-verified.json"
        verified_queue.write_text(json.dumps(open_loop_fixture, ensure_ascii=False), encoding="utf-8")
        verified_result = validate_open_loop_queue(verified_queue)
        if verified_result.get("ok") is not True or verified_result.get("closeout_allowed") is not True:
            failures.append(f"完整 open-loop fixture 应允许收口：{verified_result}")
        missing_evidence_fixture = json.loads(json.dumps(open_loop_fixture, ensure_ascii=False))
        missing_evidence_fixture["items"][0].pop("verified_runtime_evidence", None)
        missing_queue = root / "open-loop-missing-evidence.json"
        missing_queue.write_text(json.dumps(missing_evidence_fixture, ensure_ascii=False), encoding="utf-8")
        missing_result = validate_open_loop_queue(missing_queue)
        if missing_result.get("ok") is True or not any("verified_runtime_evidence" in item for item in missing_result.get("failures", [])):
            failures.append("open-loop 已关闭但缺 verified_runtime_evidence 的样例没有失败")
        contaminated_public = root / "public-docs"
        contaminated_public.mkdir()
        for index, marker in enumerate(PRIVATE_PERSONA_MARKERS):
            suffix = [".md", ".json", ".txt"][index % 3]
            content = f"这里故意写入 {marker.upper() if marker.isascii() else marker} 作为负向样例。\n"
            (contaminated_public / f"leak-{index}{suffix}").write_text(content, encoding="utf-8")
        contamination_failures = scan_public_persona_boundary([contaminated_public])
        contamination_text = "\n".join(contamination_failures)
        for marker in PRIVATE_PERSONA_MARKERS:
            if marker not in contamination_text:
                failures.append(f"公共人格边界扫描器没有命中负向私密正文标记样例：{marker}")
        rules = runtime_rule_report()
        if rules.get("open_loop_closeout", {}).get("closeout_formula") != "closeout_allowed = failures 为空且 closeout_blockers 为空":
            failures.append("open-loop 收口规则报告缺少可审计 closeout 公式")
        if PRIVATE_PERSONA_MARKERS != rules.get("public_persona_boundary", {}).get("private_markers"):
            failures.append("公共人格边界规则报告没有完整暴露扫描标记")
        evidence = root / "e2e"
        evidence.mkdir()
        role_ids = {
            "product_manager": "11111111-1111-4111-8111-111111111111",
            "architect": "22222222-2222-4222-8222-222222222222",
            "developer": "33333333-3333-4333-8333-333333333333",
            "tester": "44444444-4444-4444-8444-444444444444",
            "reviewer": "55555555-5555-4555-8555-555555555555",
        }
        for role in REQUIRED_LOOM_ROLES:
            role_dir = evidence / "role-artifacts"
            role_dir.mkdir(exist_ok=True)
            (role_dir / f"{role}.json").write_text('{"ok": true}\n', encoding="utf-8")
        (evidence / "loom-role-session-manifest.json").write_text(json.dumps({
            "roles": [
                {
                    "role": role,
                    "session_id": session,
                    "provider": "codex-cli",
                    "context_state": "complete",
                    "alarm": None,
                    "role_workspace": [f"role-workspaces/{role}"],
                    "handoff_inputs": ["requirements.json"],
                    "handoff_outputs": [f"role-artifacts/{role}.json"],
                    "evidence_files": [f"role-artifacts/{role}.json"],
                }
                for role, session in role_ids.items()
            ],
            "session_loss_alarms": [],
        }, ensure_ascii=False), encoding="utf-8")
        shutil.copyfile(evidence / "loom-role-session-manifest.json", evidence / "loom-role-session-manifest-pre-review.json")
        (evidence / "role-gate-clearance").mkdir(exist_ok=True)
        for role in REQUIRED_LOOM_ROLES:
            (evidence / "role-gate-clearance" / f"{role}.json").write_text(json.dumps({
                "schema_id": "redcap-e2e-role-gate-clearance",
                "producer": "e2e-runner",
                "role": role,
                "decision": "cleared_for_external_project_role_execution",
                "role_must_not_run_commands": [".redcap/runtime/bin/redcap gate"],
            }, ensure_ascii=False), encoding="utf-8")
        (evidence / "role-gate-clearance-summary.json").write_text(json.dumps({
            "schema_id": "redcap-e2e-role-gate-clearance-summary",
            "producer": "e2e-runner",
            "runner_owns_full_prism": True,
            "role_gate_self_block_forbidden": True,
            "roles": [
                {
                    "role": role,
                    "decision": "cleared_for_external_project_role_execution",
                    "path": f"role-gate-clearance/{role}.json",
                }
                for role in sorted(REQUIRED_LOOM_ROLES)
            ],
        }, ensure_ascii=False), encoding="utf-8")
        (evidence / "prism-assisted-review.json").write_text('{"used": true, "reviews": [{"provider": "kimi", "verdict": "pass"}], "cap_decision": "accepted"}\n', encoding="utf-8")
        (evidence / "knowledge-retrieval-evidence.json").write_text('{"search_ran": true, "query": "loom", "matches": [{"id": "loom"}]}\n', encoding="utf-8")
        (evidence / "self-purification-candidates.json").write_text(
            '{"candidates": [{"id": "fixture-candidate", "decisions": [{"decision": "no_promote", "reason": "fixture"}]}]}\n',
            encoding="utf-8",
        )
        (evidence / "persona-distillation-decision.json").write_text('{"privacy_class": "cap-private", "public_write": false, "private_body_written": false, "reason": "fixture"}\n', encoding="utf-8")
        (evidence / "test-results.json").write_text('{"role": "tester", "passed": true}\n', encoding="utf-8")
        (evidence / "negative-probes.json").write_text('{"role": "tester", "passed": true}\n', encoding="utf-8")
        (evidence / "runner-negative-contract-probe.json").write_text('{"schema_id": "redcap-e2e-runner-negative-contract-probe", "producer": "e2e-runner", "ok": true}\n', encoding="utf-8")
        (evidence / "runner-character-player-contract-probe.json").write_text('{"schema_id": "redcap-e2e-runner-character-player-contract-probe", "producer": "e2e-runner", "ok": true}\n', encoding="utf-8")
        (evidence / "final-runner-test-results.json").write_text('{"schema_id": "redcap-e2e-final-runner-test-results", "producer": "e2e-runner", "ok": true, "exit_code": 0, "detected_command": ["npm", "test"]}\n', encoding="utf-8")
        (evidence / "final-marker-validation.json").write_text('{"schema_id": "redcap-e2e-final-marker-validation", "producer": "e2e-runner", "ok": true, "exit_code": 0, "detected_command": ["npm", "test"], "stdout_sha256": "fixture"}\n', encoding="utf-8")
        (evidence / "browser-inspection.json").write_text('{"schema_id": "redcap-e2e-browser-inspection", "producer": "e2e-runner", "ok": true, "screenshot": "browser-inspection.png"}\n', encoding="utf-8")
        (evidence / "file-browser-inspection.json").write_text('{"schema_id": "redcap-e2e-file-browser-inspection", "producer": "e2e-runner", "ok": true, "launch_mode": "local-file-protocol", "screenshot": "file-browser-inspection.png"}\n', encoding="utf-8")
        (evidence / "behavioral-browser-verification.json").write_text('{"schema_id": "redcap-e2e-behavioral-browser-verification", "producer": "e2e-runner", "ok": true, "screenshot": "behavioral-browser-verification.png"}\n', encoding="utf-8")
        (evidence / "independent-browser-verification-script.py").write_text("print('fixture')\n", encoding="utf-8")
        (evidence / "independent-browser-verification.json").write_text('{"schema_id": "redcap-e2e-independent-browser-verification", "producer": "e2e-independent-browser-process", "ok": true, "screenshot": "independent-browser-verification.png", "script": {"path": "independent-browser-verification-script.py", "sha256": "fixture"}}\n', encoding="utf-8")
        (evidence / "independent-observer.json").write_text('{"schema_id": "redcap-e2e-independent-observer", "producer": "redcap-independent-observer", "ok": true}\n', encoding="utf-8")
        (evidence / "visual-independence-report.json").write_text('{"schema_id": "redcap-e2e-visual-independence-report", "producer": "e2e-runner", "ok": true}\n', encoding="utf-8")
        (evidence / "self-referential-boundary.json").write_text('{"schema_id": "redcap-e2e-self-referential-boundary", "producer": "e2e-runner", "ok": true, "validation_chain_scope": {"same_host": true, "same_redcap_package": true}, "completion_marker_disclosure": {"must_copy_this_boundary": true}}\n', encoding="utf-8")
        (evidence / "convergence-diagnosis.json").write_text('{"schema_id": "redcap-e2e-convergence-diagnosis", "producer": "e2e-runner", "final_prism_ok": true, "strictest_verdict": "pass", "auto_rerun_allowed": false, "diagnosis": []}\n', encoding="utf-8")
        (evidence / "final-evidence-bundle.json").write_text(json.dumps({
            "schema_id": "redcap-e2e-final-evidence-bundle",
            "producer": "e2e-runner",
            "bundle_sha256": "fixture",
            "files": [
                {"path": "loom-role-session-manifest.json", "exists": True, "sha256": "fixture"},
                {"path": "role-gate-clearance-summary.json", "exists": True, "sha256": "fixture"},
                {"path": "package-prism-check.json", "exists": True, "sha256": "fixture"},
                {"path": "runner-negative-contract-probe.json", "exists": True, "sha256": "fixture"},
                {"path": "runner-character-player-contract-probe.json", "exists": True, "sha256": "fixture"},
                {"path": "final-runner-test-results.json", "exists": True, "sha256": "fixture"},
                {"path": "final-marker-validation.json", "exists": True, "sha256": "fixture"},
                {"path": "browser-inspection.json", "exists": True, "sha256": "fixture"},
                {"path": "file-browser-inspection.json", "exists": True, "sha256": "fixture"},
                {"path": "behavioral-browser-verification.json", "exists": True, "sha256": "fixture"},
                {"path": "independent-browser-verification.json", "exists": True, "sha256": "fixture"},
            ],
        }, ensure_ascii=False), encoding="utf-8")
        (evidence / "final-prism-review.json").write_text(json.dumps({
            "schema_id": "redcap-e2e-final-prism-review",
            "producer": "e2e-runner",
            "ok": True,
            "strictest_verdict": "pass",
            "reviews": [
                {"provider": "kimi", "verdict": "pass"},
                {"provider": "claude-code", "verdict": "pass"},
            ],
        }, ensure_ascii=False), encoding="utf-8")
        (evidence / "failure-backlog.json").write_text('{"open_items": [], "closed_items": [], "next_round_required": false}\n', encoding="utf-8")
        (evidence / "iteration-verdict.json").write_text(json.dumps({
            "status": "pass",
            "producer": "e2e-runner",
            "ready_for_engineering_use": True,
            "evidence_checked": sorted(REQUIRED_EVIDENCE_CHECKS),
        }, ensure_ascii=False), encoding="utf-8")
        (evidence / "package-prism-check.json").write_text('{"ok": true, "exit_code": 0, "stdout_tail": "PRISM_CHECK_OK"}\n', encoding="utf-8")
        (evidence / "completion-marker.json").write_text('{"schema_id": "redcap-e2e-completion-marker", "producer": "e2e-runner", "ready_for_engineering_use": true, "final_prism_strictest_verdict": "pass", "validation_chain_scope": {"same_host": true, "same_redcap_package": true}, "not_claimed": ["fixture"], "final_marker_validation": {"ok": true}, "file_browser_inspection": {"ok": true}, "convergence_diagnosis": {"strictest_verdict": "pass"}}\n', encoding="utf-8")
        good = validate_e2e_evidence_quality(evidence)
        if not good["ok"]:
            failures.append(f"合法 E2E fixture 不应失败：{good['failures']}")
        bad_manifest = load_json(evidence / "loom-role-session-manifest.json")
        bad_manifest["roles"][1]["session_id"] = bad_manifest["roles"][0]["session_id"]
        (evidence / "loom-role-session-manifest.json").write_text(json.dumps(bad_manifest, ensure_ascii=False), encoding="utf-8")
        bad = validate_e2e_evidence_quality(evidence)
        if not any("共用 session_id" in item for item in bad["failures"]):
            failures.append("重复 session_id 样例没有失败")
        bad_manifest["roles"][1]["session_id"] = role_ids["architect"]
        (evidence / "loom-role-session-manifest.json").write_text(json.dumps(bad_manifest, ensure_ascii=False), encoding="utf-8")
        backlog = load_json(evidence / "failure-backlog.json")
        backlog["open_items"] = [{"id": "fixture-open"}]
        (evidence / "failure-backlog.json").write_text(json.dumps(backlog, ensure_ascii=False), encoding="utf-8")
        bad_backlog = validate_e2e_evidence_quality(evidence)
        if not any("开放项" in item for item in bad_backlog["failures"]):
            failures.append("开放 failure-backlog 样例没有失败")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_REVIVAL_FOLLOWTHROUGH_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap 复活后续缺口闭环检查器")
    sub = parser.add_subparsers(dest="command", required=True)
    check_cmd = sub.add_parser("check")
    check_cmd.add_argument("--queue", default=str(DEFAULT_QUEUE))
    check_cmd.set_defaults(func=cmd_check)
    e2e = sub.add_parser("e2e-check")
    e2e.add_argument("--evidence-root", required=True)
    e2e.set_defaults(func=cmd_e2e_check)
    open_loop = sub.add_parser("open-loop-check")
    open_loop.add_argument("--queue", default=str(DEFAULT_OPEN_LOOP_QUEUE))
    open_loop.set_defaults(func=cmd_open_loop_check)
    rules = sub.add_parser("rule-report")
    rules.add_argument("--out")
    rules.set_defaults(func=cmd_rule_report)
    sub.add_parser("self-check").set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

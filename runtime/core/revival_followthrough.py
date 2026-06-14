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
    "prism-assisted-review.json",
    "knowledge-retrieval-evidence.json",
    "self-purification-candidates.json",
    "persona-distillation-decision.json",
    "test-results.json",
    "negative-probes.json",
    "failure-backlog.json",
    "iteration-verdict.json",
}
REQUIRED_EVIDENCE_CHECKS = {
    "loom-role-session-manifest.json",
    "loom-role-session-manifest-pre-review.json",
    "prism-assisted-review.json",
    "knowledge-retrieval-evidence.json",
    "self-purification-candidates.json",
    "persona-distillation-decision.json",
    "test-results.json",
    "negative-probes.json",
    "failure-backlog.json",
    "iteration-verdict.json",
}
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


def scan_public_persona_boundary() -> list[str]:
    failures: list[str] = []
    for root in PUBLIC_SCAN_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_dir() or path.suffix.lower() not in {".json", ".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            lowered = text.casefold()
            leaked = [marker for marker in PRIVATE_PERSONA_MARKERS if marker.casefold() in lowered]
            if leaked:
                rel = path.relative_to(REPO_ROOT).as_posix()
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
    decisions = purification.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        failures.append("self-purification-candidates.decisions 必须非空")
    else:
        for decision in decisions:
            if not isinstance(decision, dict):
                failures.append("自我净化 decision 必须是对象")
                continue
            label = decision.get("decision")
            if label not in {"promote_public", "keep_private", "no_promote", "defer_with_owner"}:
                failures.append(f"自我净化 decision 无效：{label}")
            if label == "no_promote" and not decision.get("reason"):
                failures.append("no_promote 决策必须写明 reason")

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


def validate_e2e_evidence_quality(evidence_root: pathlib.Path) -> dict[str, Any]:
    failures: list[str] = []
    for rel in sorted(REQUIRED_E2E_FILES):
        if not (evidence_root / rel).is_file():
            failures.append(f"缺少 E2E 证据文件：{rel}")
    validate_role_manifest(evidence_root, failures)
    validate_prism_assistance(evidence_root, failures)
    validate_knowledge_and_purification(evidence_root, failures)
    validate_persona_boundary(evidence_root, failures)
    validate_failure_loop(evidence_root, failures)
    validate_package_prism(evidence_root, failures)
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


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    if validate_queue(DEFAULT_QUEUE):
        failures.append("当前 followthrough 队列不应失败")
    with tempfile.TemporaryDirectory(prefix="redcap-followthrough-") as raw:
        root = pathlib.Path(raw)
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
        (evidence / "prism-assisted-review.json").write_text('{"used": true, "reviews": [{"provider": "kimi", "verdict": "pass"}], "cap_decision": "accepted"}\n', encoding="utf-8")
        (evidence / "knowledge-retrieval-evidence.json").write_text('{"search_ran": true, "query": "loom", "matches": [{"id": "loom"}]}\n', encoding="utf-8")
        (evidence / "self-purification-candidates.json").write_text('{"candidates": [], "no_candidate_reason": "fixture", "decisions": [{"decision": "no_promote", "reason": "fixture"}]}\n', encoding="utf-8")
        (evidence / "persona-distillation-decision.json").write_text('{"privacy_class": "cap-private", "public_write": false, "private_body_written": false, "reason": "fixture"}\n', encoding="utf-8")
        (evidence / "test-results.json").write_text('{"role": "tester", "passed": true}\n', encoding="utf-8")
        (evidence / "negative-probes.json").write_text('{"role": "tester", "passed": true}\n', encoding="utf-8")
        (evidence / "failure-backlog.json").write_text('{"open_items": [], "closed_items": [], "next_round_required": false}\n', encoding="utf-8")
        (evidence / "iteration-verdict.json").write_text(json.dumps({
            "status": "pass",
            "ready_for_engineering_use": True,
            "evidence_checked": sorted(REQUIRED_EVIDENCE_CHECKS),
        }, ensure_ascii=False), encoding="utf-8")
        (evidence / "package-prism-check.json").write_text('{"ok": true, "exit_code": 0, "stdout_tail": "PRISM_CHECK_OK"}\n', encoding="utf-8")
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
    sub.add_parser("self-check").set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

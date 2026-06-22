#!/usr/bin/env python3
"""OL-11 TRPG long-run E2E pre-execution contract checks."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import pathlib
import subprocess
import sys
import textwrap
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_PLAN = REPO_ROOT / "assets" / "docs" / "ol11-trpg-longrun-e2e-plan.md"
DEFAULT_E2E_CONTRACT = REPO_ROOT / "assets" / "contracts" / "complete-revival-e2e-acceptance-design.json"
DEFAULT_QUEUE = REPO_ROOT / "assets" / "contracts" / "open-loop-closure-queue.json"
DEFAULT_SCHEMA = REPO_ROOT / "assets" / "contracts" / "ol11-trpg-longrun-e2e-evidence-schema.json"
DEFAULT_PROVENANCE = REPO_ROOT / "assets" / "evidence" / "ol11" / "trpg-demand-provenance.json"
DEFAULT_DRY_RUN_ROOT = pathlib.Path.home() / "workspace" / "redcap-production-samples" / "ol11-trpg-carrier-dry-run"


REQUIRED_PLAN_MARKERS = [
    "Cap 扮演需求方、验收方、RedCap 运行观察者",
    "独立开发 AI 扮演承接方",
    "同一角色跨轮返工必须复用同一个 `session_id`",
    "不要求访问 `/Users/norven/workspace/trpg-server/` 或 `/Users/norven/workspace/trpg-web/` 的源码",
    "第二轮需求变更必须加入以下能力",
    "能力覆盖矩阵",
    "开发 AI 直接读取旧 TRPG 源码",
]

REQUIRED_OL11_SCHEMA_KEYS = [
    "sample_manifest",
    "demand_provenance",
    "developer_ai_session",
    "project_install",
    "hook_events",
    "loom_roles",
    "change_rounds",
    "failure_routes",
    "self_purification",
    "knowledge_impact",
    "prism_reviews",
    "cache_retention",
    "cap_observer_verdict",
    "old_source_isolation",
    "real_sample_gate",
    "external_sample_audit",
]


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(json.dumps({"ok": False, "failures": [f"无法读取 JSON：{path}: {exc}"]}, ensure_ascii=False, indent=2)) from exc
    if not isinstance(payload, dict):
        raise SystemExit(json.dumps({"ok": False, "failures": [f"JSON 必须是对象：{path}"]}, ensure_ascii=False, indent=2))
    return payload


def git_head(path: pathlib.Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def find_ol11_item(queue: dict[str, Any]) -> dict[str, Any] | None:
    items = queue.get("items")
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and item.get("id") == "OL-11-long-term-third-party-production-sample":
            return item
    return None


def validate_plan(plan_path: pathlib.Path, failures: list[str]) -> None:
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError as exc:
        failures.append(f"无法读取 OL-11 方案：{exc}")
        return
    for marker in REQUIRED_PLAN_MARKERS:
        if marker not in text:
            failures.append(f"OL-11 方案缺少关键约束：{marker}")


def validate_schema(schema: dict[str, Any], failures: list[str]) -> None:
    if schema.get("schema_id") != "redcap-ol11-trpg-longrun-e2e-evidence-schema":
        failures.append("OL-11 证据结构合同 schema_id 错误")
    required = schema.get("required_top_level_evidence")
    if not isinstance(required, list):
        failures.append("OL-11 证据结构合同缺少 required_top_level_evidence")
        required = []
    missing = sorted(set(REQUIRED_OL11_SCHEMA_KEYS) - {str(item) for item in required})
    if missing:
        failures.append(f"OL-11 证据结构合同缺少顶层证据项：{missing}")
    requirements = schema.get("evidence_requirements")
    if not isinstance(requirements, dict):
        failures.append("OL-11 证据结构合同缺少 evidence_requirements")
        return
    for key in REQUIRED_OL11_SCHEMA_KEYS:
        if key not in requirements:
            failures.append(f"OL-11 证据结构合同缺少 evidence_requirements.{key}")


def validate_provenance(provenance: dict[str, Any], failures: list[str]) -> None:
    if provenance.get("schema_id") != "redcap-ol11-trpg-demand-provenance":
        failures.append("TRPG 来源证明 schema_id 错误")
    boundary = provenance.get("boundary")
    if not isinstance(boundary, dict):
        failures.append("TRPG 来源证明缺少 boundary")
    else:
        if boundary.get("developer_ai_may_read_old_source") is not False:
            failures.append("TRPG 来源证明必须禁止开发 AI 读取旧源码")
        if boundary.get("cap_may_read_for_abstraction") is not True:
            failures.append("TRPG 来源证明必须说明 Cap 只做需求抽象读取")
    sources = provenance.get("source_projects")
    if not isinstance(sources, list) or len(sources) < 2:
        failures.append("TRPG 来源证明必须包含 server 和 web 两个既有外部项目")
        return
    for source in sources:
        if not isinstance(source, dict):
            failures.append("TRPG 来源证明 source_projects 条目必须是对象")
            continue
        raw_path = source.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            failures.append("TRPG 来源证明项目路径不能为空")
            continue
        path = pathlib.Path(raw_path).expanduser()
        if not path.exists():
            failures.append(f"TRPG 来源项目不存在：{path}")
            continue
        try:
            path.resolve().relative_to(REPO_ROOT)
        except ValueError:
            pass
        else:
            failures.append(f"TRPG 来源项目不能位于 RedCap 源仓库内：{path}")
        expected_head = source.get("git_head")
        actual_head = git_head(path)
        if isinstance(expected_head, str) and expected_head.strip() and actual_head != expected_head:
            failures.append(f"TRPG 来源项目 git_head 不匹配：{path}")
        refs = source.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            failures.append(f"TRPG 来源项目缺少 evidence_refs：{path}")
            continue
        for ref in refs:
            if not isinstance(ref, str) or not pathlib.Path(ref).expanduser().exists():
                failures.append(f"TRPG 来源证明引用不存在：{ref}")


def validate_contracts(e2e_contract: dict[str, Any], queue: dict[str, Any], failures: list[str]) -> None:
    ol11 = e2e_contract.get("ol11_trpg_longrun_external_sample")
    if not isinstance(ol11, dict):
        failures.append("完整复活 E2E 合同缺少 ol11_trpg_longrun_external_sample")
    else:
        if ol11.get("plan_path") != "assets/docs/ol11-trpg-longrun-e2e-plan.md":
            failures.append("OL-11 合同 plan_path 不正确")
        if ol11.get("status") not in {"pre_execution_review_blocked", "ready_for_preflight"}:
            failures.append(f"OL-11 合同状态不在允许集合内：{ol11.get('status')}")
        for key in [
            "actor_boundary",
            "session_continuity_rule",
            "evidence_required",
            "anti_cheat_rules",
            "evidence_schema_path",
            "demand_provenance_path",
            "pre_execution_prism_review",
            "execution_boundary",
        ]:
            if key not in ol11:
                failures.append(f"OL-11 合同缺少 {key}")
        if ol11.get("status") == "ready_for_preflight" and "pre_execution_prism_resolution" not in ol11:
            failures.append("OL-11 合同 ready_for_preflight 状态必须记录 pre_execution_prism_resolution")
    item = find_ol11_item(queue)
    if item is None:
        failures.append("开放队列缺少 OL-11 条目")
        return
    if item.get("status") != "external-sample-required":
        failures.append("OL-11 在真实样本通过前必须保持 external-sample-required")
    if item.get("terminal_blocker") is not True:
        failures.append("OL-11 必须保持 terminal_blocker=true")
    fixed_plan = item.get("fixed_plan")
    if not isinstance(fixed_plan, dict):
        failures.append("OL-11 队列条目缺少 fixed_plan")
    else:
        if fixed_plan.get("status") not in {"pre_execution_review_blocked", "ready_for_preflight"}:
            failures.append("OL-11 队列 fixed_plan.status 必须是 pre_execution_review_blocked 或 ready_for_preflight")
        if fixed_plan.get("status") == "pre_execution_review_blocked" and fixed_plan.get("blocked_by_prism") is not True:
            failures.append("OL-11 队列 fixed_plan.blocked_by_prism 必须为 true")
        if fixed_plan.get("status") == "ready_for_preflight":
            if fixed_plan.get("blocked_by_prism") is not False:
                failures.append("OL-11 队列 ready_for_preflight 状态下 fixed_plan.blocked_by_prism 必须为 false")
            if "pre_execution_prism_resolution" not in fixed_plan:
                failures.append("OL-11 队列 ready_for_preflight 状态必须记录 pre_execution_prism_resolution")
        if fixed_plan.get("plan_path") != "assets/docs/ol11-trpg-longrun-e2e-plan.md":
            failures.append("OL-11 队列 fixed_plan.plan_path 不正确")
        for key in [
            "evidence_schema_path",
            "demand_provenance_path",
            "pre_execution_prism_review",
            "minimum_fixes_from_prism",
        ]:
            if key not in fixed_plan:
                failures.append(f"OL-11 队列 fixed_plan 缺少 {key}")


def build_demand_excerpt(provenance: dict[str, Any]) -> str:
    sources = provenance.get("source_projects")
    source_names = []
    if isinstance(sources, list):
        for source in sources:
            if isinstance(source, dict) and isinstance(source.get("label"), str):
                source_names.append(source["label"])
    source_label = "、".join(source_names) if source_names else "既有 TRPG server/web 项目方向"
    return "\n".join([
        "需求包编号：OL-11-TRPG-LONGRUN。",
        f"来源抽象：{source_label}。",
        "目标：开发一个 TRPG 社群与活动协作平台，覆盖活动发布、报名、角色卡管理、主持人审核、玩家协作、活动日程和基础通知。",
        "约束：本短演练只确认开发 AI 能接收需求包、触发项目级 Hook、产生机器可查标记和暴露 session_id；不得开发正式项目。",
        "禁止：不得读取 /Users/norven/workspace/trpg-server 或 /Users/norven/workspace/trpg-web 的源码、目录结构或实现文件。",
    ])


def hook_config(script: pathlib.Path, event: str) -> dict[str, Any]:
    return {
        "type": "command",
        "command": f"/usr/bin/python3 \"{script}\" --event {event}",
        "timeout": 10,
        "statusMessage": f"RedCap OL-11 dry-run {event}",
    }


def run_trpg_carrier_dry_run(args: argparse.Namespace) -> dict[str, Any]:
    from complete_revival_e2e import (  # noqa: WPS433 - reuse existing E2E carrier primitives.
        CODEX_INTERACTIVE_DISABLE_PLUGINS,
        CODEX_INTERACTIVE_EXTRA_DISABLED_FEATURES,
        CODEX_ROLE_MODEL,
        CODEX_ROLE_REASONING_EFFORT,
        REQUIRED_CONFIGURED_HOOK_EVENTS,
        attach_source_workspace_guard,
        codex_child_env,
        codex_mcp_isolation_argv,
        codex_mcp_isolation_contract,
        codex_project_trust_argv,
        command_receipt,
        compare_user_codex_home_state,
        detect_codex_resource_blocker,
        ensure_codex_project_trusted,
        ensure_external_path,
        ensure_project_git_repo,
        extract_codex_session_id,
        parse_hook_events,
        run_command_pty,
        source_workspace_snapshot,
        user_codex_home_state,
    )

    work_root = pathlib.Path(args.work_root).expanduser().resolve()
    provenance = load_json(pathlib.Path(args.provenance).resolve())
    guard_before = source_workspace_snapshot()
    user_codex_before = user_codex_home_state()
    failures = ensure_external_path(work_root)
    if failures:
        return attach_source_workspace_guard({
            "schema_id": "redcap-ol11-trpg-carrier-dry-run",
            "ok": False,
            "work_root": str(work_root),
            "failures": failures,
        }, guard_before)
    work_root.mkdir(parents=True, exist_ok=True)
    project = (work_root / "redcap-ol11-trpg-carrier-dry-run").resolve()
    if project.exists():
        shutil.rmtree(project)
    evidence = project / ".redcap" / "evidence" / "e2e"
    (project / ".codex").mkdir(parents=True)
    evidence.mkdir(parents=True)
    (project / ".codex" / "config.toml").write_text("[features]\nhooks = true\n", encoding="utf-8")

    git_result = ensure_project_git_repo(project, evidence)
    events_path = evidence / "ol11-trpg-carrier-hook-events.jsonl"
    hook_script = project / ".redcap" / "ol11_hook_probe.py"
    hook_script.write_text(textwrap.dedent(f"""\
        #!/usr/bin/env python3
        import argparse, datetime as dt, hashlib, json, pathlib, sys
        parser = argparse.ArgumentParser()
        parser.add_argument('--event', required=True)
        args = parser.parse_args()
        raw = sys.stdin.read()
        path = pathlib.Path({str(events_path)!r})
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps({{
                'event': args.event,
                'recorded_at': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
                'stdin_length': len(raw),
                'stdin_sha256': hashlib.sha256(raw.encode('utf-8')).hexdigest() if raw else None
            }}, ensure_ascii=False, sort_keys=True) + '\\n')
        print(json.dumps({{'continue': True}}, ensure_ascii=False))
        """), encoding="utf-8")
    hook_script.chmod(0o755)
    (project / ".codex" / "hooks.json").write_text(json.dumps({
        "hooks": {
            "SessionStart": [{"matcher": "startup|resume|clear|compact", "hooks": [hook_config(hook_script, "SessionStart")]}],
            "UserPromptSubmit": [{"hooks": [hook_config(hook_script, "UserPromptSubmit")]}],
            "PreToolUse": [{"matcher": "Bash|apply_patch|Edit|Write", "hooks": [hook_config(hook_script, "PreToolUse")]}],
            "PostToolUse": [{"matcher": ".*", "hooks": [hook_config(hook_script, "PostToolUse")]}],
            "Stop": [{"hooks": [hook_config(hook_script, "Stop")]}],
        }
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    trust_result = ensure_codex_project_trusted(project, evidence)
    mcp_contract = codex_mcp_isolation_contract()
    child_env = codex_child_env(trust_result.get("isolated_home") if isinstance(trust_result.get("isolated_home"), dict) else {})
    marker_path = evidence / "ol11-trpg-dry-run-marker.json"
    last_message = evidence / "ol11-trpg-carrier-last-message.txt"
    prompt = (
        "你是 OL-11 的独立开发 AI 短演练承接方。\n"
        f"{build_demand_excerpt(provenance)}\n"
        "请必须使用 shell 工具创建 .redcap/evidence/e2e/ol11-trpg-dry-run-marker.json，"
        "JSON 字段必须包含 schema_id=redcap-ol11-trpg-carrier-dry-run-marker、"
        "demand_package_id=OL-11-TRPG-LONGRUN、role=developer_ai、action=dry_run_ack、old_source_read=false。"
        "最终只回答 ol11-trpg-dry-run-ok。不要开发项目，不要读取旧项目源码。"
    )
    argv = [
        "codex",
        "--enable",
        "hooks",
        "--dangerously-bypass-hook-trust",
        "--ask-for-approval",
        "never",
        "exec",
        "--model",
        CODEX_ROLE_MODEL,
        "-c",
        f'model_reasoning_effort="{CODEX_ROLE_REASONING_EFFORT}"',
        *codex_mcp_isolation_argv(),
        *codex_project_trust_argv(project),
        "--cd",
        str(project),
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "--color",
        "never",
        "--output-last-message",
        str(last_message),
    ]
    if CODEX_INTERACTIVE_DISABLE_PLUGINS:
        argv.extend(["--disable", "plugins"])
    for feature in CODEX_INTERACTIVE_EXTRA_DISABLED_FEATURES:
        argv.extend(["--disable", feature])
    argv.append(prompt)
    result = run_command_pty(
        argv,
        cwd=project,
        timeout_seconds=args.timeout_seconds,
        completion_markers=[],
        completion_files=[marker_path],
        settle_seconds=10.0,
        env_overrides=child_env,
    )
    if str(result.get("stdout") or "").strip():
        last_message.write_text(str(result.get("stdout") or "")[-12000:], encoding="utf-8")

    events = parse_hook_events(events_path)
    missing_events = [event for event in REQUIRED_CONFIGURED_HOOK_EVENTS if event not in events]
    resource_blocker = detect_codex_resource_blocker(result)
    marker_payload: dict[str, Any] | None = None
    marker_failures: list[str] = []
    if marker_path.exists():
        try:
            marker_payload = json.loads(marker_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            marker_failures.append(f"短演练标记 JSON 不合法：{exc}")
    else:
        marker_failures.append("短演练没有生成标记文件")
    if isinstance(marker_payload, dict):
        expected = {
            "schema_id": "redcap-ol11-trpg-carrier-dry-run-marker",
            "demand_package_id": "OL-11-TRPG-LONGRUN",
            "role": "developer_ai",
            "action": "dry_run_ack",
            "old_source_read": False,
        }
        for key, value in expected.items():
            if marker_payload.get(key) != value:
                marker_failures.append(f"短演练标记字段错误：{key}")
    session_id = extract_codex_session_id(f"{result.get('stdout') or ''}\n{result.get('stderr') or ''}")
    failures = []
    if git_result.get("ok") is not True:
        failures.append("短演练项目 Git 基线初始化失败")
    if trust_result.get("ok") is not True:
        failures.append("短演练 Codex 项目信任准备失败")
    if mcp_contract.get("ok") is not True:
        failures.extend([str(item) for item in mcp_contract.get("failures", [])])
    if resource_blocker.get("present") is True:
        failures.append("Codex CLI 外部资源受限，短演练未能证明承载能力")
    if result.get("ok") is not True:
        failures.append("Codex CLI 短演练命令失败")
    if missing_events:
        failures.append(f"短演练没有触发全部项目级 Hook：{missing_events}")
    if not session_id:
        failures.append("短演练未能从 Codex CLI 输出中取得 session_id")
    failures.extend(marker_failures)
    user_guard = compare_user_codex_home_state(user_codex_before)
    if user_guard.get("ok") is not True:
        failures.append(f"用户真实 Codex Home 保护失败：{user_guard.get('failures')}")
    payload = {
        "schema_id": "redcap-ol11-trpg-carrier-dry-run",
        "ok": not failures,
        "project": str(project),
        "demand_package_id": "OL-11-TRPG-LONGRUN",
        "old_source_paths_forbidden": [
            "/Users/norven/workspace/trpg-server",
            "/Users/norven/workspace/trpg-web",
        ],
        "events_path": str(events_path),
        "events": events,
        "missing_events": missing_events,
        "developer_ai_session": {
            "session_id": session_id,
            "session_id_source": "codex-output" if session_id else None,
        },
        "marker_path": str(marker_path),
        "marker_payload": marker_payload,
        "resource_blocker": resource_blocker,
        "command": command_receipt(result),
        "git": git_result,
        "codex_project_trust": trust_result,
        "codex_mcp_isolation_contract": mcp_contract,
        "user_codex_home_guard": user_guard,
        "last_message": str(last_message),
        "failures": failures,
    }
    payload = attach_source_workspace_guard(payload, guard_before)
    write_json(evidence / "ol11-trpg-carrier-dry-run.json", payload)
    return payload


def cmd_trpg_carrier_dry_run(args: argparse.Namespace) -> int:
    result = run_trpg_carrier_dry_run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_OL11_TRPG_CARRIER_DRY_RUN_OK")
        return 0
    return 1


def run_plan_check(args: argparse.Namespace) -> dict[str, Any]:
    plan_path = pathlib.Path(args.plan).resolve()
    e2e_contract_path = pathlib.Path(args.e2e_contract).resolve()
    queue_path = pathlib.Path(args.queue).resolve()
    schema_path = pathlib.Path(args.schema).resolve()
    provenance_path = pathlib.Path(args.provenance).resolve()
    failures: list[str] = []
    validate_plan(plan_path, failures)
    schema = load_json(schema_path)
    provenance = load_json(provenance_path)
    e2e_contract = load_json(e2e_contract_path)
    queue = load_json(queue_path)
    validate_schema(schema, failures)
    validate_provenance(provenance, failures)
    validate_contracts(e2e_contract, queue, failures)
    return {
        "schema_id": "redcap-ol11-trpg-longrun-e2e-plan-check",
        "ok": not failures,
        "plan": str(plan_path),
        "e2e_contract": str(e2e_contract_path),
        "queue": str(queue_path),
        "evidence_schema": str(schema_path),
        "demand_provenance": str(provenance_path),
        "failures": failures,
    }


def cmd_plan_check(args: argparse.Namespace) -> int:
    result = run_plan_check(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_OL11_TRPG_LONGRUN_E2E_PLAN_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    result = run_plan_check(argparse.Namespace(
        plan=str(DEFAULT_PLAN),
        e2e_contract=str(DEFAULT_E2E_CONTRACT),
        queue=str(DEFAULT_QUEUE),
        schema=str(DEFAULT_SCHEMA),
        provenance=str(DEFAULT_PROVENANCE),
    ))
    failures = list(result.get("failures", []))
    bad_schema = load_json(DEFAULT_SCHEMA)
    bad_schema["required_top_level_evidence"] = []
    schema_failures: list[str] = []
    validate_schema(bad_schema, schema_failures)
    if not schema_failures:
        failures.append("缺少 OL-11 顶层证据项的负向探针没有失败")
    bad_provenance = load_json(DEFAULT_PROVENANCE)
    if isinstance(bad_provenance.get("boundary"), dict):
        bad_provenance["boundary"]["developer_ai_may_read_old_source"] = True
    provenance_failures: list[str] = []
    validate_provenance(bad_provenance, provenance_failures)
    if not any("禁止开发 AI 读取旧源码" in item for item in provenance_failures):
        failures.append("允许开发 AI 读取旧源码的负向探针没有失败")
    payload = {
        "schema_id": "redcap-ol11-trpg-longrun-e2e-plan-self-check",
        "ok": not failures,
        "plan_check_ok": result.get("ok"),
        "negative_schema_failures": schema_failures,
        "negative_provenance_failures": provenance_failures,
        "failures": failures,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload["ok"]:
        print("REDCAP_OL11_TRPG_LONGRUN_E2E_PLAN_SELF_CHECK_OK")
        return 0
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OL-11 TRPG long-run E2E pre-execution checks")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("plan-check")
    check.add_argument("--plan", default=str(DEFAULT_PLAN))
    check.add_argument("--e2e-contract", default=str(DEFAULT_E2E_CONTRACT))
    check.add_argument("--queue", default=str(DEFAULT_QUEUE))
    check.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    check.add_argument("--provenance", default=str(DEFAULT_PROVENANCE))
    check.set_defaults(func=cmd_plan_check)
    self_check = sub.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    dry_run = sub.add_parser("trpg-carrier-dry-run")
    dry_run.add_argument("--work-root", default=str(DEFAULT_DRY_RUN_ROOT))
    dry_run.add_argument("--provenance", default=str(DEFAULT_PROVENANCE))
    dry_run.add_argument("--timeout-seconds", type=int, default=240)
    dry_run.set_defaults(func=cmd_trpg_carrier_dry_run)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

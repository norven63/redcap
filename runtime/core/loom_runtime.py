#!/usr/bin/env python3
"""RedCap Loom 项目级角色会话运行机。"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile
import uuid
from typing import Any


SCHEMA_ID = "redcap-loom-runtime-session-manifest"
ROLE_MARKER_PREFIX = "REDCAP_LOOM_ROLE="
DEFAULT_REQUIRED_ROLES = [
    "product_manager",
    "architect",
    "developer",
    "tester",
    "reviewer",
]
ALLOWED_PROVIDERS = {"codex-cli"}
ALLOWED_CONTEXT_STATES = {"active", "complete", "degraded"}
SESSION_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
FAILURE_ROUTE_EVENT_SCHEMA_ID = "redcap-loom-runtime-failure-route-event"
ALLOWED_ROUTE_STATUSES = {"open", "accepted", "completed", "rejected", "escalated"}
ALLOWED_ROOT_CAUSES = {"code", "design", "requirement", "change", "test", "review", "unknown"}
DEFAULT_ESCALATION_THRESHOLD = 3
PHASE_TO_ROLE = {
    "idea_intake": "product_manager",
    "change_intake": "product_manager",
    "architecture_design": "architect",
    "implementation": "developer",
    "quality_assurance": "tester",
    "review_and_acceptance": "reviewer",
    "closeout": "cap_orchestrator",
    "blocked": "cap_orchestrator",
}
ROLE_TO_DEFAULT_PHASE = {
    "product_manager": "idea_intake",
    "architect": "architecture_design",
    "developer": "implementation",
    "tester": "quality_assurance",
    "reviewer": "review_and_acceptance",
    "cap_orchestrator": "closeout",
}


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def state_dir(project_root: pathlib.Path) -> pathlib.Path:
    return project_root / ".redcap" / "state" / "loom"


def manifest_path(project_root: pathlib.Path) -> pathlib.Path:
    return state_dir(project_root) / "session-manifest.json"


def evidence_dir(project_root: pathlib.Path) -> pathlib.Path:
    return project_root / ".redcap" / "evidence" / "loom"


def failure_routes_path(project_root: pathlib.Path) -> pathlib.Path:
    return state_dir(project_root) / "failure-routes.jsonl"


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def append_jsonl(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def project_root_arg(value: str) -> pathlib.Path:
    return pathlib.Path(value).expanduser().resolve()


def sha256_json(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_root_cause(value: str | None) -> str:
    raw = (value or "unknown").strip().lower()
    mapping = {
        "代码": "code",
        "实现": "code",
        "架构": "design",
        "设计": "design",
        "需求": "requirement",
        "变更": "change",
        "测试": "test",
        "评审": "review",
    }
    normalized = mapping.get(raw, raw)
    return normalized if normalized in ALLOWED_ROOT_CAUSES else "unknown"


def default_phase_for_role(role: str) -> str:
    return ROLE_TO_DEFAULT_PHASE.get(role, "blocked")


def root_cause_hash(root_cause: str, summary: str, evidence_files: list[str]) -> str:
    return sha256_json({
        "root_cause": canonical_root_cause(root_cause),
        "summary": summary.strip(),
        "evidence": sorted(evidence_files),
    })


def route_id_for(task_id: str, target_role: str, root_hash: str, loop_count: int) -> str:
    return f"route-{sha256_json([task_id, target_role, root_hash, loop_count])[:16]}"


def new_manifest(project_root: pathlib.Path, project_id: str, task_id: str) -> dict[str, Any]:
    now = iso_now()
    return {
        "schema_id": SCHEMA_ID,
        "project_root": str(project_root),
        "project_id": project_id,
        "task_id": task_id,
        "created_at": now,
        "updated_at": now,
        "role_marker_prefix": ROLE_MARKER_PREFIX,
        "required_role_provider": "codex-cli",
        "roles": [],
        "alarms": [],
    }


def load_or_create_manifest(project_root: pathlib.Path, project_id: str, task_id: str) -> dict[str, Any]:
    path = manifest_path(project_root)
    manifest = read_json(path)
    if not manifest:
        return new_manifest(project_root, project_id, task_id)
    return manifest


def role_records(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    roles = manifest.get("roles")
    return roles if isinstance(roles, list) else []


def add_alarm(manifest: dict[str, Any], role: str, code: str, detail: str) -> None:
    alarms = manifest.setdefault("alarms", [])
    if not isinstance(alarms, list):
        manifest["alarms"] = alarms = []
    alarms.append({
        "role": role,
        "code": code,
        "detail": detail,
        "recorded_at": iso_now(),
    })


def ensure_manifest_identity(manifest: dict[str, Any], project_root: pathlib.Path, project_id: str, task_id: str) -> None:
    if manifest.get("schema_id") != SCHEMA_ID:
        manifest.clear()
        manifest.update(new_manifest(project_root, project_id, task_id))
        return
    if manifest.get("project_id") != project_id:
        add_alarm(manifest, "_manifest", "project_id_changed", f"已有 {manifest.get('project_id')}，本次 {project_id}")
    if manifest.get("task_id") != task_id:
        add_alarm(manifest, "_manifest", "task_id_changed", f"已有 {manifest.get('task_id')}，本次 {task_id}")


def record_session(
    *,
    project_root: pathlib.Path,
    project_id: str,
    task_id: str,
    role: str,
    session_id: str,
    provider: str,
    context_state: str,
    handoff_inputs: list[str],
    handoff_outputs: list[str],
    evidence_files: list[str],
    source: str,
) -> dict[str, Any]:
    manifest = load_or_create_manifest(project_root, project_id, task_id)
    ensure_manifest_identity(manifest, project_root, project_id, task_id)
    roles = role_records(manifest)
    now = iso_now()
    if provider not in ALLOWED_PROVIDERS:
        add_alarm(manifest, role, "invalid_provider", f"Loom 角色执行方必须是 codex-cli，实际为 {provider}")
    if not SESSION_RE.fullmatch(session_id):
        add_alarm(manifest, role, "invalid_session_id", "session_id 必须是 UUID")
    if context_state not in ALLOWED_CONTEXT_STATES:
        add_alarm(manifest, role, "invalid_context_state", f"context_state 不允许：{context_state}")

    duplicate_roles = [
        item.get("role")
        for item in roles
        if isinstance(item, dict) and item.get("role") != role and item.get("session_id") == session_id
    ]
    if duplicate_roles:
        add_alarm(manifest, role, "session_id_reused_by_other_role", f"同一 session_id 已被角色使用：{duplicate_roles}")

    existing = next((item for item in roles if isinstance(item, dict) and item.get("role") == role), None)
    if existing is None:
        roles.append({
            "project_id": project_id,
            "task_id": task_id,
            "role": role,
            "session_id": session_id,
            "provider": provider,
            "started_at": now,
            "last_seen_at": now,
            "context_state": context_state,
            "handoff_inputs": handoff_inputs,
            "handoff_outputs": handoff_outputs,
            "evidence_files": evidence_files,
            "source": source,
        })
    else:
        old_session = str(existing.get("session_id") or "")
        if old_session != session_id:
            add_alarm(manifest, role, "session_id_changed", f"同一角色必须续用同一 session_id：旧 {old_session}，新 {session_id}")
            existing["context_state"] = "degraded"
            observed = existing.setdefault("observed_session_ids", [])
            if isinstance(observed, list):
                for value in [old_session, session_id]:
                    if value and value not in observed:
                        observed.append(value)
        else:
            existing["last_seen_at"] = now
            existing["context_state"] = context_state
            existing["handoff_inputs"] = handoff_inputs
            existing["handoff_outputs"] = handoff_outputs
            existing["evidence_files"] = evidence_files
            existing["source"] = source
    manifest["roles"] = roles
    manifest["updated_at"] = now
    write_json(manifest_path(project_root), manifest)
    return manifest


def validate_manifest(
    manifest: dict[str, Any],
    *,
    project_root: pathlib.Path | None = None,
    task_id: str | None = None,
    required_roles: list[str] | None = None,
    allow_pending: bool = False,
) -> list[str]:
    failures: list[str] = []
    if manifest.get("schema_id") != SCHEMA_ID:
        failures.append("Loom 会话清单 schema_id 错误")
    if project_root is not None and pathlib.Path(str(manifest.get("project_root") or "")).resolve() != project_root.resolve():
        failures.append("Loom 会话清单 project_root 与当前项目不一致")
    if task_id is not None and manifest.get("task_id") != task_id:
        failures.append("Loom 会话清单 task_id 不匹配")
    roles = role_records(manifest)
    required = DEFAULT_REQUIRED_ROLES if required_roles is None else required_roles
    by_role: dict[str, list[dict[str, Any]]] = {}
    for item in roles:
        if isinstance(item, dict):
            by_role.setdefault(str(item.get("role") or ""), []).append(item)
    for role in required:
        records = by_role.get(role, [])
        if not records:
            if not allow_pending:
                failures.append(f"Loom 角色缺少会话记录：{role}")
            continue
        if len(records) > 1:
            failures.append(f"Loom 角色存在重复记录：{role}")
        record = records[-1]
        session_id = str(record.get("session_id") or "")
        if not SESSION_RE.fullmatch(session_id):
            failures.append(f"Loom 角色 session_id 非法或缺失：{role}")
        if record.get("provider") != "codex-cli":
            failures.append(f"Loom 角色 provider 必须是 codex-cli：{role}")
        if record.get("context_state") == "degraded":
            failures.append(f"Loom 角色上下文已降级，需要协助评审：{role}")
        if record.get("context_state") not in ALLOWED_CONTEXT_STATES:
            failures.append(f"Loom 角色 context_state 非法：{role}")
        for key in ["started_at", "last_seen_at"]:
            if not isinstance(record.get(key), str) or not record[key].strip():
                failures.append(f"Loom 角色缺少 {key}：{role}")
        for key in ["handoff_inputs", "handoff_outputs"]:
            if not isinstance(record.get(key), list):
                failures.append(f"Loom 角色 {key} 必须是列表：{role}")
    sessions: dict[str, str] = {}
    for item in roles:
        if not isinstance(item, dict):
            failures.append("Loom 角色记录必须是对象")
            continue
        session_id = str(item.get("session_id") or "")
        role = str(item.get("role") or "")
        if session_id and session_id in sessions and sessions[session_id] != role:
            failures.append(f"Loom 不同角色不能复用 session_id：{sessions[session_id]} 与 {role}")
        elif session_id:
            sessions[session_id] = role
    alarms = manifest.get("alarms")
    if isinstance(alarms, list) and alarms:
        failures.append(f"Loom 会话清单存在未关闭报警：{len(alarms)}")
    elif not isinstance(alarms, list):
        failures.append("Loom 会话清单 alarms 必须是列表")
    return failures


def user_prompt_text(event: dict[str, Any]) -> str:
    prompt = event.get("prompt")
    if isinstance(prompt, dict):
        for key in ["normalized_excerpt", "text", "content"]:
            if isinstance(prompt.get(key), str):
                return str(prompt[key])
    if isinstance(prompt, str):
        return prompt
    for key in ["normalized_excerpt", "text", "content"]:
        if isinstance(event.get(key), str):
            return str(event[key])
    return ""


def default_event_paths(project_root: pathlib.Path) -> list[pathlib.Path]:
    return [
        project_root / ".redcap" / "evidence" / "host-hooks" / "codex" / "events.jsonl",
        project_root / ".redcap" / "assets" / "evidence" / "host-hooks" / "codex" / "events.jsonl",
    ]


def import_hook_events(project_root: pathlib.Path, project_id: str, task_id: str, paths: list[pathlib.Path]) -> dict[str, Any]:
    imported = 0
    skipped = 0
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if not isinstance(event, dict) or event.get("event") != "UserPromptSubmit":
                skipped += 1
                continue
            text = user_prompt_text(event)
            match = re.search(rf"{re.escape(ROLE_MARKER_PREFIX)}([a-z_]+)", text)
            if not match:
                skipped += 1
                continue
            session_id = str(event.get("session_id") or "")
            role = match.group(1)
            record_session(
                project_root=project_root,
                project_id=project_id,
                task_id=task_id,
                role=role,
                session_id=session_id,
                provider="codex-cli",
                context_state="active",
                handoff_inputs=[],
                handoff_outputs=[],
                evidence_files=[],
                source=f"hook:{path}",
            )
            imported += 1
    return {
        "schema_id": "redcap-loom-runtime-hook-import",
        "ok": imported > 0,
        "imported": imported,
        "skipped": skipped,
        "manifest": str(manifest_path(project_root)),
    }


def latest_route_events(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for event in events:
        route_id = str(event.get("route_id") or "")
        if route_id:
            latest[route_id] = event
    return latest


def previous_matching_routes(events: list[dict[str, Any]], target_role: str, root_hash: str) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if event.get("event") == "create"
        and event.get("target_role") == target_role
        and event.get("root_cause_hash") == root_hash
    ]


def build_failure_route_event(
    *,
    project_root: pathlib.Path,
    project_id: str,
    task_id: str,
    source_role: str,
    source_phase: str,
    target_role: str,
    target_phase: str,
    restart_from_phase: str,
    root_cause: str,
    summary: str,
    evidence_files: list[str],
    previous_route_id: str | None,
    escalation_threshold: int,
) -> dict[str, Any]:
    events = read_jsonl(failure_routes_path(project_root))
    canonical = canonical_root_cause(root_cause)
    root_hash = root_cause_hash(canonical, summary, evidence_files)
    previous = previous_matching_routes(events, target_role, root_hash)
    loop_count = len(previous) + 1
    previous_id = previous_route_id or (str(previous[-1].get("route_id")) if previous else "")
    route_id = route_id_for(task_id, target_role, root_hash, loop_count)
    threshold = max(1, escalation_threshold)
    status = "escalated" if loop_count >= threshold else "open"
    return {
        "schema_id": FAILURE_ROUTE_EVENT_SCHEMA_ID,
        "event": "create",
        "status": status,
        "route_id": route_id,
        "project_root": str(project_root),
        "project_id": project_id,
        "task_id": task_id,
        "source_role": source_role,
        "source_phase": source_phase,
        "root_cause": canonical,
        "root_cause_hash": root_hash,
        "summary": summary,
        "target_role": target_role,
        "target_phase": target_phase,
        "restart_from_phase": restart_from_phase,
        "downstream_replay_required": True,
        "evidence": evidence_files,
        "loop_count": loop_count,
        "previous_route_id": previous_id,
        "escalation_threshold": threshold,
        "cap_may_modify_target_project": False,
        "runner_may_generate_fix_patch": False,
        "target_role_must_acknowledge": True,
        "target_role_must_read_route_before_edit": True,
        "created_at": iso_now(),
    }


def transition_failure_route_event(
    *,
    project_root: pathlib.Path,
    route_id: str,
    status: str,
    role: str,
    evidence_files: list[str],
    reason: str | None = None,
) -> dict[str, Any]:
    events = read_jsonl(failure_routes_path(project_root))
    latest = latest_route_events(events).get(route_id)
    if latest is None:
        raise ValueError(f"未找到失败路由：{route_id}")
    if latest.get("status") in {"completed", "rejected", "escalated"} and status != latest.get("status"):
        raise ValueError(f"失败路由已处于终态：{latest.get('status')}")
    payload = json.loads(json.dumps(latest, ensure_ascii=False))
    payload["event"] = status
    payload["status"] = status
    payload["updated_at"] = iso_now()
    payload["evidence"] = sorted(set([str(item) for item in payload.get("evidence", []) if item] + evidence_files))
    if status == "accepted":
        payload["accepted_by"] = role
        payload["accepted_at"] = payload["updated_at"]
    elif status == "completed":
        payload["completed_by"] = role
        payload["completed_at"] = payload["updated_at"]
    elif status == "rejected":
        payload["rejected_by"] = role
        payload["rejected_at"] = payload["updated_at"]
        payload["reject_reason"] = reason or ""
    return payload


def validate_failure_route_events(
    events: list[dict[str, Any]],
    *,
    require_no_open: bool = False,
) -> list[str]:
    failures: list[str] = []
    latest = latest_route_events(events)
    for event in events:
        route_id = str(event.get("route_id") or "<unknown>")
        if event.get("schema_id") != FAILURE_ROUTE_EVENT_SCHEMA_ID:
            failures.append(f"失败路由 {route_id} schema_id 错误")
        required = [
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
        ]
        for key in required:
            if key not in event:
                failures.append(f"失败路由 {route_id} 缺少字段：{key}")
        status = event.get("status")
        if status not in ALLOWED_ROUTE_STATUSES:
            failures.append(f"失败路由 {route_id} 状态非法：{status}")
        if event.get("root_cause") not in ALLOWED_ROOT_CAUSES:
            failures.append(f"失败路由 {route_id} root_cause 非法：{event.get('root_cause')}")
        target_role = str(event.get("target_role") or "")
        target_phase = str(event.get("target_phase") or "")
        restart_phase = str(event.get("restart_from_phase") or "")
        if target_role not in ROLE_TO_DEFAULT_PHASE:
            failures.append(f"失败路由 {route_id} target_role 非法：{target_role}")
        if target_phase not in PHASE_TO_ROLE:
            failures.append(f"失败路由 {route_id} target_phase 非法：{target_phase}")
        if target_phase and target_role and PHASE_TO_ROLE.get(target_phase) != target_role:
            failures.append(f"失败路由 {route_id} target_role 与 target_phase 不匹配")
        if restart_phase not in PHASE_TO_ROLE:
            failures.append(f"失败路由 {route_id} restart_from_phase 非法：{restart_phase}")
        if event.get("downstream_replay_required") is not True:
            failures.append(f"失败路由 {route_id} 必须要求下游重放")
        evidence = event.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            failures.append(f"失败路由 {route_id} 必须包含失败证据")
        if event.get("cap_may_modify_target_project") is not False:
            failures.append(f"失败路由 {route_id} 必须禁止 Cap 直接修改目标项目")
        if event.get("runner_may_generate_fix_patch") is not False:
            failures.append(f"失败路由 {route_id} 必须禁止运行器生成修复补丁")
        if event.get("target_role_must_acknowledge") is not True:
            failures.append(f"失败路由 {route_id} 必须要求目标角色接收")
        if event.get("target_role_must_read_route_before_edit") is not True:
            failures.append(f"失败路由 {route_id} 必须要求目标角色先读路由")
        loop_count = event.get("loop_count")
        threshold = event.get("escalation_threshold")
        if not isinstance(loop_count, int) or loop_count < 1:
            failures.append(f"失败路由 {route_id} loop_count 必须是正整数")
        if not isinstance(threshold, int) or threshold < 1:
            failures.append(f"失败路由 {route_id} escalation_threshold 必须是正整数")
        if isinstance(loop_count, int) and isinstance(threshold, int) and loop_count >= threshold and status == "open":
            failures.append(f"失败路由 {route_id} 达到升级阈值后不能继续保持 open")
        if status == "accepted":
            if event.get("accepted_by") != target_role or not event.get("accepted_at"):
                failures.append(f"失败路由 {route_id} 接收证据必须由目标角色写入")
        if status == "completed":
            if event.get("completed_by") != target_role or not event.get("completed_at"):
                failures.append(f"失败路由 {route_id} 完成证据必须由目标角色写入")
        if status == "rejected" and not event.get("reject_reason"):
            failures.append(f"失败路由 {route_id} 拒绝时必须说明原因")
    if require_no_open:
        for route_id, event in latest.items():
            if event.get("status") in {"open", "accepted"}:
                failures.append(f"失败路由仍未关闭：{route_id}={event.get('status')}")
    return failures


def cmd_init(args: argparse.Namespace) -> int:
    project_root = project_root_arg(args.project_root)
    manifest = new_manifest(project_root, args.project_id, args.task_id)
    write_json(manifest_path(project_root), manifest)
    evidence_dir(project_root).mkdir(parents=True, exist_ok=True)
    print(json.dumps({"ok": True, "manifest": str(manifest_path(project_root))}, ensure_ascii=False, indent=2))
    print("REDCAP_LOOM_RUNTIME_INIT_OK")
    return 0


def cmd_record_session(args: argparse.Namespace) -> int:
    manifest = record_session(
        project_root=project_root_arg(args.project_root),
        project_id=args.project_id,
        task_id=args.task_id,
        role=args.role,
        session_id=args.session_id,
        provider=args.provider,
        context_state=args.context_state,
        handoff_inputs=split_csv(args.handoff_inputs),
        handoff_outputs=split_csv(args.handoff_outputs),
        evidence_files=split_csv(args.evidence_files),
        source=args.source,
    )
    failures = validate_manifest(
        manifest,
        project_root=project_root_arg(args.project_root),
        task_id=args.task_id,
        required_roles=[],
        allow_pending=True,
    )
    print(json.dumps({"ok": not failures, "manifest": str(manifest_path(project_root_arg(args.project_root))), "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_LOOM_RUNTIME_RECORD_OK")
    return 0


def cmd_manifest_check(args: argparse.Namespace) -> int:
    project_root = project_root_arg(args.project_root)
    manifest = read_json(manifest_path(project_root))
    required = split_csv(args.require_roles) or DEFAULT_REQUIRED_ROLES
    failures = validate_manifest(
        manifest,
        project_root=project_root,
        task_id=args.task_id,
        required_roles=required,
        allow_pending=args.allow_pending,
    )
    print(json.dumps({
        "ok": not failures,
        "manifest": str(manifest_path(project_root)),
        "required_roles": required,
        "failures": failures,
    }, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_LOOM_RUNTIME_MANIFEST_OK")
    return 0


def cmd_import_hook_events(args: argparse.Namespace) -> int:
    project_root = project_root_arg(args.project_root)
    paths = [pathlib.Path(path).expanduser().resolve() for path in args.events] if args.events else default_event_paths(project_root)
    result = import_hook_events(project_root, args.project_id, args.task_id, paths)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        return 1
    print("REDCAP_LOOM_RUNTIME_HOOK_IMPORT_OK")
    return 0


def cmd_failure_route(args: argparse.Namespace) -> int:
    project_root = project_root_arg(args.project_root)
    path = failure_routes_path(project_root)
    if args.action == "create":
        target_phase = args.target_phase or default_phase_for_role(args.target_role)
        restart_phase = args.restart_from_phase or target_phase
        event = build_failure_route_event(
            project_root=project_root,
            project_id=args.project_id,
            task_id=args.task_id,
            source_role=args.source_role,
            source_phase=args.source_phase,
            target_role=args.target_role,
            target_phase=target_phase,
            restart_from_phase=restart_phase,
            root_cause=args.root_cause,
            summary=args.summary,
            evidence_files=split_csv(args.evidence_files),
            previous_route_id=args.previous_route_id,
            escalation_threshold=args.escalation_threshold,
        )
        append_jsonl(path, event)
        failures = validate_failure_route_events(read_jsonl(path))
        print(json.dumps({"ok": not failures, "event": event, "ledger": str(path), "failures": failures}, ensure_ascii=False, indent=2))
        if failures:
            return 1
        print("REDCAP_LOOM_FAILURE_ROUTE_OK")
        return 0

    if args.action in {"accept", "complete", "reject"}:
        try:
            event = transition_failure_route_event(
                project_root=project_root,
                route_id=args.route_id,
                status={"accept": "accepted", "complete": "completed", "reject": "rejected"}[args.action],
                role=args.role,
                evidence_files=split_csv(args.evidence_files),
                reason=args.reason,
            )
        except ValueError as exc:
            print(json.dumps({"ok": False, "failures": [str(exc)], "ledger": str(path)}, ensure_ascii=False, indent=2))
            return 1
        append_jsonl(path, event)
        failures = validate_failure_route_events(read_jsonl(path))
        print(json.dumps({"ok": not failures, "event": event, "ledger": str(path), "failures": failures}, ensure_ascii=False, indent=2))
        if failures:
            return 1
        print("REDCAP_LOOM_FAILURE_ROUTE_OK")
        return 0

    failures = validate_failure_route_events(read_jsonl(path), require_no_open=args.require_no_open)
    print(json.dumps({"ok": not failures, "ledger": str(path), "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_LOOM_FAILURE_ROUTE_CHECK_OK")
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="redcap-loom-runtime-") as raw:
        project = pathlib.Path(raw) / "project"
        project.mkdir()
        project_id = "fixture-project"
        task_id = "fixture-task"
        manifest = new_manifest(project, project_id, task_id)
        write_json(manifest_path(project), manifest)
        role_sessions = {
            "product_manager": "11111111-1111-4111-8111-111111111111",
            "architect": "22222222-2222-4222-8222-222222222222",
            "developer": "33333333-3333-4333-8333-333333333333",
            "tester": "44444444-4444-4444-8444-444444444444",
            "reviewer": "55555555-5555-4555-8555-555555555555",
        }
        for role, session_id in role_sessions.items():
            record_session(
                project_root=project,
                project_id=project_id,
                task_id=task_id,
                role=role,
                session_id=session_id,
                provider="codex-cli",
                context_state="complete",
                handoff_inputs=["upstream"],
                handoff_outputs=["downstream"],
                evidence_files=[f"role-artifacts/{role}.json"],
                source="self-check",
            )
        good = read_json(manifest_path(project))
        if validate_manifest(good, project_root=project, task_id=task_id):
            failures.append("完整角色清单不应失败")
        missing = json.loads(json.dumps(good, ensure_ascii=False))
        missing["roles"] = [item for item in missing["roles"] if item.get("role") != "reviewer"]
        if not any("reviewer" in item for item in validate_manifest(missing, project_root=project, task_id=task_id)):
            failures.append("缺少 reviewer 的样例没有失败")
        duplicate = json.loads(json.dumps(good, ensure_ascii=False))
        duplicate["roles"][1]["session_id"] = duplicate["roles"][0]["session_id"]
        if not any("复用 session_id" in item for item in validate_manifest(duplicate, project_root=project, task_id=task_id)):
            failures.append("不同角色复用 session_id 的样例没有失败")
        degraded = json.loads(json.dumps(good, ensure_ascii=False))
        degraded["roles"][2]["context_state"] = "degraded"
        if not any("上下文已降级" in item for item in validate_manifest(degraded, project_root=project, task_id=task_id)):
            failures.append("上下文降级的样例没有失败")
        changed_project = pathlib.Path(raw) / "changed-session"
        changed_project.mkdir()
        write_json(manifest_path(changed_project), new_manifest(changed_project, "changed", "task"))
        record_session(
            project_root=changed_project,
            project_id="changed",
            task_id="task",
            role="developer",
            session_id="66666666-6666-4666-8666-666666666666",
            provider="codex-cli",
            context_state="active",
            handoff_inputs=[],
            handoff_outputs=[],
            evidence_files=[],
            source="self-check",
        )
        changed = record_session(
            project_root=changed_project,
            project_id="changed",
            task_id="task",
            role="developer",
            session_id="77777777-7777-4777-8777-777777777777",
            provider="codex-cli",
            context_state="active",
            handoff_inputs=[],
            handoff_outputs=[],
            evidence_files=[],
            source="self-check",
        )
        if not any("session_id_changed" == alarm.get("code") for alarm in changed.get("alarms", [])):
            failures.append("同一角色更换 session_id 没有报警")
        hook_project = pathlib.Path(raw) / "hook-project"
        hook_project.mkdir()
        events = hook_project / ".redcap" / "evidence" / "host-hooks" / "codex" / "events.jsonl"
        events.parent.mkdir(parents=True)
        events.write_text(
            json.dumps({
                "event": "UserPromptSubmit",
                "session_id": "88888888-8888-4888-8888-888888888888",
                "turn_id": "turn-fixture",
                "recorded_at": iso_now(),
                "prompt": {"normalized_excerpt": f"{ROLE_MARKER_PREFIX}developer fixture"},
            }, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        imported = import_hook_events(hook_project, "hook-project", "hook-task", [events])
        if imported.get("imported") != 1:
            failures.append("Hook 事件导入没有识别 Loom 角色")
        route_project = pathlib.Path(raw) / "route-project"
        route_project.mkdir()
        route = build_failure_route_event(
            project_root=route_project,
            project_id="route-project",
            task_id="route-task",
            source_role="tester",
            source_phase="quality_assurance",
            target_role="developer",
            target_phase="implementation",
            restart_from_phase="implementation",
            root_cause="code",
            summary="验证脚本未覆盖报名意向负向探针",
            evidence_files=["test-results.json", "negative-probes.json"],
            previous_route_id=None,
            escalation_threshold=3,
        )
        append_jsonl(failure_routes_path(route_project), route)
        accepted = transition_failure_route_event(
            project_root=route_project,
            route_id=route["route_id"],
            status="accepted",
            role="developer",
            evidence_files=["role-artifacts/developer.json"],
        )
        append_jsonl(failure_routes_path(route_project), accepted)
        completed = transition_failure_route_event(
            project_root=route_project,
            route_id=route["route_id"],
            status="completed",
            role="developer",
            evidence_files=["implementation-log.json", "verification-results.json"],
        )
        append_jsonl(failure_routes_path(route_project), completed)
        if validate_failure_route_events(read_jsonl(failure_routes_path(route_project)), require_no_open=True):
            failures.append("完整失败路由接收与完成样例不应失败")
        bad_route = json.loads(json.dumps(route, ensure_ascii=False))
        bad_route["route_id"] = "bad-route"
        bad_route["cap_may_modify_target_project"] = True
        if not any("禁止 Cap" in item for item in validate_failure_route_events([bad_route])):
            failures.append("允许 Cap 直接修复目标项目的失败路由样例没有失败")
        loop_route_project = pathlib.Path(raw) / "loop-route-project"
        loop_route_project.mkdir()
        loop_events: list[dict[str, Any]] = []
        for _ in range(3):
            item = build_failure_route_event(
                project_root=loop_route_project,
                project_id="loop-project",
                task_id="loop-task",
                source_role="tester",
                source_phase="quality_assurance",
                target_role="developer",
                target_phase="implementation",
                restart_from_phase="implementation",
                root_cause="code",
                summary="同一根因重复失败",
                evidence_files=["test-results.json"],
                previous_route_id=None,
                escalation_threshold=3,
            )
            append_jsonl(failure_routes_path(loop_route_project), item)
            loop_events.append(item)
        if loop_events[-1].get("status") != "escalated":
            failures.append("同一根因第三次失败没有自动升级")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_LOOM_RUNTIME_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap Loom 项目级角色会话运行机")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--project-root", required=True)
    init.add_argument("--project-id", required=True)
    init.add_argument("--task-id", required=True)
    init.set_defaults(func=cmd_init)

    record = sub.add_parser("record-session")
    record.add_argument("--project-root", required=True)
    record.add_argument("--project-id", required=True)
    record.add_argument("--task-id", required=True)
    record.add_argument("--role", required=True)
    record.add_argument("--session-id", required=True)
    record.add_argument("--provider", default="codex-cli")
    record.add_argument("--context-state", default="active", choices=sorted(ALLOWED_CONTEXT_STATES))
    record.add_argument("--handoff-inputs")
    record.add_argument("--handoff-outputs")
    record.add_argument("--evidence-files")
    record.add_argument("--source", default="manual")
    record.set_defaults(func=cmd_record_session)

    check = sub.add_parser("manifest-check")
    check.add_argument("--project-root", required=True)
    check.add_argument("--task-id", required=True)
    check.add_argument("--require-roles")
    check.add_argument("--allow-pending", action="store_true")
    check.set_defaults(func=cmd_manifest_check)

    hook = sub.add_parser("import-hook-events")
    hook.add_argument("--project-root", required=True)
    hook.add_argument("--project-id", required=True)
    hook.add_argument("--task-id", required=True)
    hook.add_argument("--events", action="append")
    hook.set_defaults(func=cmd_import_hook_events)

    route = sub.add_parser("failure-route")
    route.add_argument("--action", required=True, choices=["create", "accept", "complete", "reject", "check"])
    route.add_argument("--project-root", required=True)
    route.add_argument("--project-id", default="")
    route.add_argument("--task-id", default="")
    route.add_argument("--source-role", default="tester")
    route.add_argument("--source-phase", default="quality_assurance")
    route.add_argument("--root-cause", default="unknown")
    route.add_argument("--summary", default="")
    route.add_argument("--target-role", default="developer")
    route.add_argument("--target-phase")
    route.add_argument("--restart-from-phase")
    route.add_argument("--evidence-files")
    route.add_argument("--previous-route-id")
    route.add_argument("--escalation-threshold", type=int, default=DEFAULT_ESCALATION_THRESHOLD)
    route.add_argument("--route-id", default="")
    route.add_argument("--role", default="")
    route.add_argument("--reason")
    route.add_argument("--require-no-open", action="store_true")
    route.set_defaults(func=cmd_failure_route)

    sub.add_parser("self-check").set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

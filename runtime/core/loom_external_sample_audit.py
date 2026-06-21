#!/usr/bin/env python3
"""独立审计 Loom 外部项目样本证据。

本模块刻意不导入 loom_runtime.py，避免真实样本门禁用同一条代码路径自证。
"""

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
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_ID = "redcap-loom-external-sample-audit"
SAMPLE_SCHEMA_ID = "redcap-loom-real-project-sample"
ROLE_SESSION_SCHEMA_ID = "redcap-e2e-loom-role-session-manifest"
RECEIPT_SCHEMA_ID = "redcap-executed-check-receipt"
ROLE_CHAIN_ORDER = ["product_manager", "architect", "developer", "tester", "reviewer"]
SESSION_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_path(base: pathlib.Path, reference: str) -> pathlib.Path:
    raw = pathlib.Path(reference)
    if raw.is_absolute():
        return raw
    if str(reference).startswith(".redcap/"):
        return base / raw
    candidates = [
        base / raw,
        base / ".redcap" / "evidence" / "e2e" / raw,
        base / ".redcap" / "state" / raw,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def is_under(path: pathlib.Path, parent: pathlib.Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def evidence_refs(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    return list_strings(value.get("evidence_refs"))


def file_record(base: pathlib.Path, reference: str) -> dict[str, Any]:
    path = resolve_path(base, reference)
    exists = path.exists()
    size = path.stat().st_size if exists else 0
    return {
        "reference": reference,
        "path": str(path),
        "exists": exists,
        "size": size,
        "sha256": sha256_file(path) if exists and path.is_file() else "",
    }


def extract_json_from_stdout(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def receipt_audit(receipt_path: pathlib.Path, *, expected_name: str, required_stdout_tokens: list[str]) -> dict[str, Any]:
    failures: list[str] = []
    receipt = read_json(receipt_path)
    if receipt.get("schema_id") != RECEIPT_SCHEMA_ID:
        failures.append(f"回执 schema_id 错误：{receipt_path}")
    if receipt.get("name") != expected_name:
        failures.append(f"回执名称不匹配：{receipt.get('name')} != {expected_name}")
    if receipt.get("ok") is not True:
        failures.append(f"回执未通过：{receipt_path}")
    stdout_ref = str(receipt.get("stdout_path") or "")
    stdout_path = (REPO_ROOT / stdout_ref).resolve() if stdout_ref and not pathlib.Path(stdout_ref).is_absolute() else pathlib.Path(stdout_ref)
    stdout_text = ""
    if not stdout_ref or not stdout_path.exists():
        failures.append(f"回执 stdout 文件不存在：{stdout_ref}")
    else:
        stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
        actual_sha = sha256_file(stdout_path)
        if receipt.get("stdout_sha256") != actual_sha:
            failures.append(f"回执 stdout 哈希不匹配：{stdout_ref}")
    for token in required_stdout_tokens:
        if token not in stdout_text:
            failures.append(f"回执 stdout 缺少关键字：{token}")
    parsed = extract_json_from_stdout(stdout_text)
    return {
        "path": str(receipt_path),
        "ok": not failures,
        "failures": failures,
        "stdout_path": str(stdout_path) if stdout_ref else "",
        "stdout_sha256": sha256_file(stdout_path) if stdout_ref and stdout_path.exists() else "",
        "parsed_top_keys": sorted(parsed.keys())[:20],
    }


def audit_role_session_manifest(project_root: pathlib.Path, manifest: dict[str, Any], *, task_id: str) -> dict[str, Any]:
    failures: list[str] = []
    roles = manifest.get("roles")
    if manifest.get("schema_id") != ROLE_SESSION_SCHEMA_ID:
        failures.append("角色会话清单 schema_id 不匹配")
    if manifest.get("task_id") != task_id:
        failures.append("角色会话清单 task_id 不匹配")
    if not isinstance(roles, list) or not roles:
        return {"ok": False, "failures": failures + ["角色会话清单 roles 必须是非空数组"], "roles": []}

    by_role: dict[str, dict[str, Any]] = {}
    seen_sessions: dict[str, str] = {}
    role_summary: list[dict[str, Any]] = []
    for item in roles:
        if not isinstance(item, dict):
            failures.append("角色会话项必须是对象")
            continue
        role = str(item.get("role") or "")
        if role in by_role:
            failures.append(f"角色重复：{role}")
        by_role[role] = item
    for role in ROLE_CHAIN_ORDER:
        item = by_role.get(role)
        if not item:
            failures.append(f"缺少角色：{role}")
            continue
        session_id = str(item.get("session_id") or "")
        if not SESSION_RE.fullmatch(session_id):
            failures.append(f"session_id 非法：{role}")
        if session_id in seen_sessions and seen_sessions[session_id] != role:
            failures.append(f"不同角色复用 session_id：{seen_sessions[session_id]} 与 {role}")
        seen_sessions[session_id] = role
        if item.get("provider") != "codex-cli":
            failures.append(f"角色 provider 必须是 codex-cli：{role}")
        if item.get("context_state") != "complete":
            failures.append(f"角色上下文状态不是 complete：{role}")
        if item.get("role_execution_ok") is not True:
            failures.append(f"角色执行未通过：{role}")
        if item.get("role_workflow_ok") is not True:
            failures.append(f"角色工作流未通过：{role}")
        if list_strings(item.get("observed_session_ids")) != [session_id]:
            failures.append(f"observed_session_ids 未锁定当前 session：{role}")
        if list_strings(item.get("retry_session_ids")):
            failures.append(f"角色存在重试 session：{role}")
        evidence_files = list_strings(item.get("evidence_files"))
        if not evidence_files:
            failures.append(f"角色缺少 evidence_files：{role}")
        missing = [ref for ref in evidence_files if not resolve_path(project_root, ref).exists()]
        if missing:
            failures.append(f"角色证据文件缺失：{role} {missing}")
        role_summary.append({
            "role": role,
            "provider": item.get("provider"),
            "session_id": session_id,
            "handoff_input_count": len(item.get("handoff_inputs") or []),
            "handoff_output_count": len(item.get("handoff_outputs") or []),
            "evidence_file_count": len(evidence_files),
        })
    alarms = manifest.get("session_loss_alarms")
    if not isinstance(alarms, list):
        failures.append("session_loss_alarms 必须是列表")
    elif alarms:
        failures.append(f"存在 session_loss_alarms：{len(alarms)}")
    return {"ok": not failures, "failures": failures, "roles": role_summary}


def audit_open_loop_result(project_root: pathlib.Path, reference: str) -> dict[str, Any]:
    path = resolve_path(project_root, reference)
    payload = read_json(path)
    failures: list[str] = []
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if summary.get("all_required_passed") is not True:
        failures.append("开放问题端到端结果没有 all_required_passed=true")
    if summary.get("failed_or_untriggered_count") not in (0, "0"):
        failures.append("开放问题端到端结果仍有失败或未触发项")
    if int(summary.get("passed_count") or 0) <= 0:
        failures.append("开放问题端到端结果 passed_count 必须大于 0")
    return {"path": str(path), "sha256": sha256_file(path) if path.exists() else "", "summary": summary, "ok": not failures, "failures": failures}


def audit_final_bundle(project_root: pathlib.Path, reference: str, role_sessions: list[dict[str, Any]]) -> dict[str, Any]:
    path = resolve_path(project_root, reference)
    payload = read_json(path)
    failures: list[str] = []
    raw_deliverables = payload.get("deliverables")
    if isinstance(raw_deliverables, list):
        deliverables = raw_deliverables
    elif isinstance(raw_deliverables, dict) and isinstance(raw_deliverables.get("files"), list):
        deliverables = raw_deliverables["files"]
    else:
        deliverables = []
    files = payload.get("files") if isinstance(payload.get("files"), list) else []
    role_runs = payload.get("role_run_summary") if isinstance(payload.get("role_run_summary"), list) else []
    if payload.get("schema_id") != "redcap-e2e-final-evidence-bundle":
        failures.append("最终证据包 schema_id 不匹配")
    if not deliverables:
        failures.append("最终证据包 deliverables 为空")
    if not files:
        failures.append("最终证据包 files 为空")
    expected_sessions = {item["role"]: item["session_id"] for item in role_sessions if item.get("role") and item.get("session_id")}
    for role, session_id in expected_sessions.items():
        matched = [item for item in role_runs if isinstance(item, dict) and item.get("role") == role]
        if not matched:
            failures.append(f"最终证据包缺少角色运行摘要：{role}")
            continue
        latest = matched[-1]
        if latest.get("session_id") != session_id:
            failures.append(f"最终证据包角色 session_id 不匹配：{role}")
        if latest.get("ok") is not True:
            failures.append(f"最终证据包角色运行未通过：{role}")
    return {
        "path": str(path),
        "sha256": sha256_file(path) if path.exists() else "",
        "schema_id": payload.get("schema_id"),
        "deliverable_count": len(deliverables),
        "file_count": len(files),
        "role_run_count": len(role_runs),
        "ok": not failures,
        "failures": failures,
    }


def audit_failure_routes(project_root: pathlib.Path, reference: str) -> dict[str, Any]:
    path = resolve_path(project_root, reference)
    failures: list[str] = []
    completed = 0
    forbidden_cap_fix = 0
    if not path.exists():
        return {"path": str(path), "ok": False, "failures": ["失败回流账本不存在"], "completed_count": 0}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            failures.append("失败回流账本包含非法 JSON 行")
            continue
        if event.get("status") == "completed":
            completed += 1
        if event.get("cap_may_modify_target_project") is not False:
            forbidden_cap_fix += 1
    if completed <= 0:
        failures.append("失败回流账本缺少 completed 事件")
    if forbidden_cap_fix:
        failures.append("失败回流账本存在允许 Cap 直接修复目标项目的事件")
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "completed_count": completed,
        "ok": not failures,
        "failures": failures,
    }


def audit_sample(
    manifest_path: pathlib.Path,
    *,
    self_check_receipt: pathlib.Path | None = None,
    independent_receipt: pathlib.Path | None = None,
    require_receipts: bool = False,
) -> dict[str, Any]:
    failures: list[str] = []
    sample = read_json(manifest_path)
    if sample.get("schema_id") != SAMPLE_SCHEMA_ID:
        failures.append("样本清单 schema_id 不匹配")
    project_root = pathlib.Path(str(sample.get("project_workspace") or sample.get("project_root") or "")).expanduser().resolve()
    if not project_root.exists():
        failures.append(f"外部项目目录不存在：{project_root}")
    if project_root.exists() and is_under(project_root, REPO_ROOT):
        failures.append("外部项目目录不能位于当前 RedCap 源码仓库内")
    task_id = str(sample.get("task_id") or "")
    if not task_id:
        failures.append("样本缺少 task_id")

    origin = sample.get("sample_origin") if isinstance(sample.get("sample_origin"), dict) else {}
    if origin.get("type") != "independent_external_project":
        failures.append("样本来源不是 independent_external_project")
    if origin.get("generated_by_current_check") is True:
        failures.append("独立外部样本不能由当前检查生成")
    origin_refs = list_strings(origin.get("preexisting_project_evidence_refs"))
    if not origin_refs:
        failures.append("独立外部样本缺少 preexisting_project_evidence_refs")
    origin_records = [file_record(project_root, ref) for ref in origin_refs]
    for record in origin_records:
        if not record["exists"] or record["size"] <= 0:
            failures.append(f"来源证据不存在或为空：{record['reference']}")
        elif not is_under(pathlib.Path(record["path"]), project_root):
            failures.append(f"来源证据越过项目边界：{record['reference']}")

    session_ref = str(sample.get("loom_session_manifest") or sample.get("e2e_role_session_manifest") or "")
    session_path = resolve_path(project_root, session_ref) if session_ref else project_root / ".redcap" / "runtime" / "loom" / "sessions.json"
    if session_path.exists() and not is_under(session_path, project_root):
        failures.append("角色会话清单越过项目边界")
    session_manifest = read_json(session_path)
    session_audit = audit_role_session_manifest(project_root, session_manifest, task_id=task_id)
    failures.extend(session_audit["failures"])

    evidence_records: list[dict[str, Any]] = []
    for ref in list_strings(sample.get("evidence_refs")):
        evidence_records.append(file_record(project_root, ref))
    for group_key in ["target_delivery", "change_intake"]:
        for ref in evidence_refs(sample.get(group_key)):
            evidence_records.append(file_record(project_root, ref))
    for iteration in sample.get("iterations") if isinstance(sample.get("iterations"), list) else []:
        for ref in evidence_refs(iteration):
            evidence_records.append(file_record(project_root, ref))
    for record in evidence_records:
        if not record["exists"] or record["size"] <= 0:
            failures.append(f"样本证据不存在或为空：{record['reference']}")
        elif not is_under(pathlib.Path(record["path"]), project_root):
            failures.append(f"样本证据越过项目边界：{record['reference']}")

    open_loop_audit = audit_open_loop_result(project_root, ".redcap/evidence/e2e/open-loop-e2e-item-results.json")
    final_bundle_audit = audit_final_bundle(project_root, ".redcap/evidence/e2e/final-evidence-bundle.json", session_audit["roles"])
    failures.extend(open_loop_audit["failures"])
    failures.extend(final_bundle_audit["failures"])
    route_ref = ""
    if isinstance(sample.get("failure_routes"), dict):
        route_ref = str(sample["failure_routes"].get("ledger") or "")
    route_audit = audit_failure_routes(project_root, route_ref or ".redcap/state/loom/failure-routes.jsonl")
    failures.extend(route_audit["failures"])

    receipt_results: list[dict[str, Any]] = []
    if independent_receipt:
        receipt_results.append(receipt_audit(
            independent_receipt,
            expected_name="ls-006-independent-external-sample-after-forgery-probe",
            required_stdout_tokens=["independent_external_verified", "true"],
        ))
    elif require_receipts:
        failures.append("缺少独立样本执行回执")
    if self_check_receipt:
        receipt_results.append(receipt_audit(
            self_check_receipt,
            expected_name="ls-006-real-sample-self-check-with-forgery-probe",
            required_stdout_tokens=["forged-independent-origin-negative", "task_id 不匹配", "nonce 链断裂"],
        ))
    elif require_receipts:
        failures.append("缺少伪造探针自检回执")
    for receipt in receipt_results:
        failures.extend(receipt["failures"])

    source_path = pathlib.Path(__file__).resolve()
    return {
        "schema_id": SCHEMA_ID,
        "ok": not failures,
        "audited_at": iso_now(),
        "auditor": {
            "module": str(source_path.relative_to(REPO_ROOT)),
            "source_sha256": sha256_file(source_path),
            "imports_loom_runtime": False,
            "purpose": "独立解析外部样本证据，避免 loom_runtime.py 同路径自证",
        },
        "sample_manifest": {
            "path": str(manifest_path),
            "sha256": sha256_file(manifest_path) if manifest_path.exists() else "",
            "schema_id": sample.get("schema_id"),
            "sample_id": sample.get("sample_id"),
            "task_id": task_id,
            "project_workspace": str(project_root),
        },
        "origin_evidence": origin_records,
        "session_manifest": {
            "path": str(session_path),
            "sha256": sha256_file(session_path) if session_path.exists() else "",
            "size": session_path.stat().st_size if session_path.exists() else 0,
            "audit": session_audit,
        },
        "sample_evidence": evidence_records,
        "open_loop_result": open_loop_audit,
        "final_bundle": final_bundle_audit,
        "failure_routes": route_audit,
        "receipt_audits": receipt_results,
        "failures": failures,
        "not_claimed": [
            "不声明 RedCap 完整复活",
            "不声明跨机器生产验收",
        ],
    }


def cmd_check(args: argparse.Namespace) -> int:
    payload = audit_sample(
        pathlib.Path(args.manifest).expanduser().resolve(),
        self_check_receipt=pathlib.Path(args.self_check_receipt).expanduser().resolve() if args.self_check_receipt else None,
        independent_receipt=pathlib.Path(args.independent_receipt).expanduser().resolve() if args.independent_receipt else None,
        require_receipts=args.require_receipts,
    )
    if args.out:
        write_json(pathlib.Path(args.out), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload["ok"]:
        print("REDCAP_LOOM_EXTERNAL_SAMPLE_AUDIT_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="redcap-loom-external-audit-") as raw:
        root = pathlib.Path(raw)
        project = root / "project"
        evidence = project / ".redcap" / "evidence" / "e2e"
        state = project / ".redcap" / "state" / "loom"
        evidence.mkdir(parents=True)
        state.mkdir(parents=True)
        for name in [
            "project-git-baseline.json",
            "open-loop-e2e-item-results.json",
            "completion-marker.json",
            "final-evidence-bundle.json",
            "role-artifacts/product_manager.json",
            "role-artifacts/architect.json",
            "role-artifacts/developer.json",
            "role-artifacts/tester.json",
            "role-artifacts/reviewer.json",
        ]:
            (evidence / name).parent.mkdir(parents=True, exist_ok=True)
            (evidence / name).write_text(json.dumps({"ok": True}, ensure_ascii=False), encoding="utf-8")
        (evidence / "open-loop-e2e-item-results.json").write_text(json.dumps({"summary": {"all_required_passed": True, "failed_or_untriggered_count": 0, "passed_count": 1}}, ensure_ascii=False), encoding="utf-8")
        sessions = [
            "019ee53f-f609-7422-beab-f2184da4f51b",
            "019ee541-b254-7123-881d-05b2dba1c3bb",
            "019ee543-de48-7ec1-a744-05f85bcc590e",
            "019ee547-9cbe-78a2-8652-0002e0878e6b",
            "019ee549-79a8-7fa2-a4a2-f798d03eba20",
        ]
        roles = []
        for role, session_id in zip(ROLE_CHAIN_ORDER, sessions):
            roles.append({
                "role": role,
                "provider": "codex-cli",
                "session_id": session_id,
                "observed_session_ids": [session_id],
                "retry_session_ids": [],
                "context_state": "complete",
                "role_execution_ok": True,
                "role_workflow_ok": True,
                "handoff_inputs": ["input"],
                "handoff_outputs": ["output"],
                "evidence_files": [f"role-artifacts/{role}.json"],
            })
        session_manifest = {"schema_id": ROLE_SESSION_SCHEMA_ID, "task_id": "self-check-task", "roles": roles, "session_loss_alarms": []}
        (evidence / "loom-role-session-manifest.json").write_text(json.dumps(session_manifest, ensure_ascii=False), encoding="utf-8")
        final_bundle = {
            "schema_id": "redcap-e2e-final-evidence-bundle",
            "deliverables": [{"path": "index.html"}],
            "files": [{"path": "index.html"}],
            "role_run_summary": [{"role": role, "session_id": session_id, "ok": True} for role, session_id in zip(ROLE_CHAIN_ORDER, sessions)],
        }
        (evidence / "final-evidence-bundle.json").write_text(json.dumps(final_bundle, ensure_ascii=False), encoding="utf-8")
        route_event = {"status": "completed", "cap_may_modify_target_project": False}
        (state / "failure-routes.jsonl").write_text(json.dumps(route_event, ensure_ascii=False) + "\n", encoding="utf-8")
        sample = {
            "schema_id": SAMPLE_SCHEMA_ID,
            "sample_id": "self-check",
            "project_workspace": str(project),
            "task_id": "self-check-task",
            "sample_origin": {
                "type": "independent_external_project",
                "generated_by_current_check": False,
                "preexisting_project_evidence_refs": [
                    ".redcap/evidence/e2e/project-git-baseline.json",
                    ".redcap/evidence/e2e/open-loop-e2e-item-results.json",
                    ".redcap/evidence/e2e/completion-marker.json",
                ],
            },
            "loom_session_manifest": ".redcap/evidence/e2e/loom-role-session-manifest.json",
            "iterations": [{"evidence_refs": [".redcap/evidence/e2e/open-loop-e2e-item-results.json"]}],
            "target_delivery": {"evidence_refs": [".redcap/evidence/e2e/final-evidence-bundle.json"]},
            "change_intake": {"evidence_refs": [".redcap/evidence/e2e/completion-marker.json"]},
            "failure_routes": {"ledger": ".redcap/state/loom/failure-routes.jsonl"},
            "evidence_refs": [".redcap/evidence/e2e/loom-role-session-manifest.json"],
        }
        sample_path = root / "sample.json"
        write_json(sample_path, sample)
        positive = audit_sample(sample_path)
        if not positive["ok"]:
            failures.append(f"正向审计夹具不应失败：{positive['failures']}")
        broken = json.loads(json.dumps(sample, ensure_ascii=False))
        broken["task_id"] = "other-task"
        broken_path = root / "broken-sample.json"
        write_json(broken_path, broken)
        negative = audit_sample(broken_path)
        if negative["ok"] or not any("task_id" in item for item in negative["failures"]):
            failures.append("task_id 不匹配负向夹具没有失败")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_LOOM_EXTERNAL_SAMPLE_AUDIT_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="独立审计 Loom 外部项目样本证据")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--manifest", required=True)
    check.add_argument("--self-check-receipt")
    check.add_argument("--independent-receipt")
    check.add_argument("--require-receipts", action="store_true")
    check.add_argument("--out")
    check.set_defaults(func=cmd_check)
    sub.add_parser("self-check").set_defaults(func=cmd_self_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

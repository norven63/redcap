#!/usr/bin/env python3
"""RedCap 通用 E2E（端到端验收）运行器。"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from typing import Any

from revival_followthrough import REQUIRED_EVIDENCE_CHECKS, validate_e2e_evidence_quality


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REDCAP = REPO_ROOT / "runtime" / "bin" / "redcap"
CONTRACT = REPO_ROOT / "assets" / "contracts" / "complete-revival-e2e-acceptance-design.json"
REQUIRED_HOOK_EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"]
LOOM_EXECUTION_ROLES = ["product_manager", "architect", "developer", "tester", "reviewer"]
ROLE_MARKER_PREFIX = "REDCAP_LOOM_ROLE="
MEANINGFUL_E2E_REQUIRED_FILES = [
    "loom-role-session-manifest.json",
    "loom-role-session-manifest-pre-review.json",
    "prism-assisted-review.json",
    "knowledge-retrieval-evidence.json",
    "self-purification-candidates.json",
    "persona-distillation-decision.json",
    "test-results.json",
    "negative-probes.json",
    "package-prism-check.json",
    "failure-backlog.json",
    "iteration-verdict.json",
]
MEANINGFUL_E2E_REQUIRED_GATES = [
    "session_id",
    "独立 Codex CLI",
    "不同 session_id",
    "棱镜协助",
    "知识检索",
    "自我净化",
    "Cap 人格",
    "failure-backlog",
    "ready_for_engineering_use",
]
OLD_REDCAP_ROOT = pathlib.Path("/Users/norven/workspace/redcap")
GIT_IN_PROGRESS_MARKERS = [
    "MERGE_HEAD",
    "CHERRY_PICK_HEAD",
    "REVERT_HEAD",
    "BISECT_LOG",
    "rebase-merge",
    "rebase-apply",
]


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取 JSON：{path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON 必须是对象：{path}")
    return payload


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slugify(value: str) -> str:
    lowered = value.casefold()
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", lowered, flags=re.UNICODE).strip("-")
    if not slug:
        slug = "direction"
    return slug[:36].strip("-") or "direction"


def run_command(
    argv: list[str],
    *,
    cwd: pathlib.Path = REPO_ROOT,
    timeout_seconds: int = 180,
    stdin: str | None = None,
) -> dict[str, Any]:
    started = dt.datetime.now(dt.timezone.utc)
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
        return {
            "argv": argv,
            "cwd": str(cwd),
            "exit_code": completed.returncode,
            "ok": completed.returncode == 0,
            "timed_out": False,
            "timeout_seconds": timeout_seconds,
            "started_at": started.replace(microsecond=0).isoformat(),
            "finished_at": iso_now(),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "argv": argv,
            "cwd": str(cwd),
            "exit_code": 124,
            "ok": False,
            "timed_out": True,
            "timeout_seconds": timeout_seconds,
            "started_at": started.replace(microsecond=0).isoformat(),
            "finished_at": iso_now(),
            "stdout": stdout,
            "stderr": stderr,
        }


def command_receipt(result: dict[str, Any]) -> dict[str, Any]:
    stdout = str(result.get("stdout") or "")
    stderr = str(result.get("stderr") or "")
    return {
        "argv": result.get("argv"),
        "cwd": result.get("cwd"),
        "exit_code": result.get("exit_code"),
        "ok": result.get("ok"),
        "timed_out": result.get("timed_out"),
        "timeout_seconds": result.get("timeout_seconds"),
        "stdout_length": len(stdout),
        "stdout_sha256": sha256_text(stdout) if stdout else None,
        "stderr_length": len(stderr),
        "stderr_sha256": sha256_text(stderr) if stderr else None,
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
    }


def git_text(args: list[str]) -> tuple[bool, str, str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0, completed.stdout, completed.stderr


def git_path(name: str) -> pathlib.Path | None:
    ok, stdout, _ = git_text(["rev-parse", "--git-path", name])
    if not ok:
        return None
    return (REPO_ROOT / stdout.strip()).resolve()


def compact_status(status: str) -> dict[str, Any]:
    return {
        "length": len(status),
        "sha256": sha256_text(status),
        "tail": status[-2000:],
    }


def source_workspace_snapshot() -> dict[str, Any]:
    failures: list[str] = []
    branch_ok, branch, branch_err = git_text(["branch", "--show-current"])
    head_ok, head, head_err = git_text(["rev-parse", "HEAD"])
    status_ok, status, status_err = git_text(["status", "--porcelain=v1", "--untracked-files=all"])
    if not branch_ok:
        failures.append(f"无法读取当前分支：{branch_err.strip()}")
    if not head_ok:
        failures.append(f"无法读取当前提交：{head_err.strip()}")
    if not status_ok:
        failures.append(f"无法读取工作区状态：{status_err.strip()}")
    in_progress: list[str] = []
    for marker in GIT_IN_PROGRESS_MARKERS:
        path = git_path(marker)
        if path is not None and path.exists():
            in_progress.append(marker)
    return {
        "schema_id": "redcap-source-workspace-snapshot",
        "ok": not failures,
        "root": str(REPO_ROOT),
        "branch": branch.strip(),
        "head": head.strip(),
        "status": compact_status(status),
        "in_progress": sorted(in_progress),
        "failures": failures,
    }


def compare_source_workspace(before: dict[str, Any]) -> dict[str, Any]:
    after = source_workspace_snapshot()
    failures: list[str] = []
    if not before.get("ok"):
        failures.append(f"执行前无法建立源工作区基线：{before.get('failures')}")
    if not after.get("ok"):
        failures.append(f"执行后无法读取源工作区状态：{after.get('failures')}")
    for field in ["branch", "head", "in_progress"]:
        if before.get(field) != after.get(field):
            failures.append(f"源工作区 {field} 发生变化")
    before_status = before.get("status") if isinstance(before.get("status"), dict) else {}
    after_status = after.get("status") if isinstance(after.get("status"), dict) else {}
    if before_status.get("sha256") != after_status.get("sha256"):
        failures.append("源工作区文件状态发生变化")
    return {
        "schema_id": "redcap-source-workspace-guard",
        "ok": not failures,
        "before": {
            "branch": before.get("branch"),
            "head": before.get("head"),
            "status": before_status,
            "in_progress": before.get("in_progress"),
        },
        "after": {
            "branch": after.get("branch"),
            "head": after.get("head"),
            "status": after_status,
            "in_progress": after.get("in_progress"),
        },
        "failures": failures,
    }


def provider_readiness_check() -> dict[str, Any]:
    checks: dict[str, Any] = {
        "schema_id": "redcap-e2e-provider-readiness",
        "ok": True,
        "checks": [],
        "failures": [],
    }
    kimi_result = run_command(
        ["kimi", "-p", "回复 ok", "--output-format", "stream-json"],
        cwd=pathlib.Path(tempfile.gettempdir()),
        timeout_seconds=30,
    )
    kimi_receipt = command_receipt(kimi_result)
    kimi_receipt.update({
        "provider": "kimi",
        "purpose": "complete revival E2E requires full Prism provider availability before running long Loom roles",
    })
    checks["checks"].append(kimi_receipt)
    combined = f"{kimi_result.get('stdout', '')}\n{kimi_result.get('stderr', '')}"
    if not kimi_result["ok"]:
        checks["ok"] = False
        if "auth.login_required" in combined or "requires login" in combined:
            checks["failures"].append("Kimi 未登录；请先运行 kimi login 或恢复 Kimi 登录态，再执行完整 E2E")
        else:
            checks["failures"].append("Kimi provider 真实调用失败，不能启动完整 E2E")
    return checks


def attach_source_workspace_guard(result: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    guard = compare_source_workspace(before)
    result["source_workspace_guard"] = guard
    if not guard["ok"]:
        result["ok"] = False
        failures = result.setdefault("failures", [])
        if isinstance(failures, list):
            failures.append(f"RedCap 源工作区保护失败：{guard['failures']}")
    return result


def source_workspace_guard_negative_probe() -> dict[str, Any]:
    before = source_workspace_snapshot()
    fixture = REPO_ROOT / ".redcap-e2e-source-guard-fixture"
    detected = {"ok": False, "failures": ["负向探针未执行"]}
    restored = {"ok": False, "failures": ["负向探针未清理"]}
    try:
        fixture.write_text("redcap source workspace guard fixture\n", encoding="utf-8")
        detected = compare_source_workspace(before)
    finally:
        if fixture.exists():
            fixture.unlink()
        restored = compare_source_workspace(before)
    return {
        "schema_id": "redcap-source-workspace-guard-negative-probe",
        "ok": detected.get("ok") is False and restored.get("ok") is True,
        "detected_mutation": detected,
        "restored_baseline": restored,
        "failures": [] if detected.get("ok") is False and restored.get("ok") is True else ["源工作区污染负向探针未按预期工作或未恢复基线"],
    }


def resolve_work_root(raw: str | None) -> pathlib.Path:
    if raw:
        return pathlib.Path(raw).expanduser().resolve()
    return pathlib.Path(tempfile.mkdtemp(prefix="redcap-ai-e2e-")).resolve()


def ensure_external_path(path: pathlib.Path) -> list[str]:
    failures: list[str] = []
    resolved = path.resolve()
    try:
        resolved.relative_to(REPO_ROOT)
        failures.append(f"工作目录不能位于 RedCap 源仓库内部：{resolved}")
    except ValueError:
        pass
    if OLD_REDCAP_ROOT.exists():
        try:
            resolved.relative_to(OLD_REDCAP_ROOT.resolve())
            failures.append(f"工作目录不能位于旧 RedCap 仓库内部：{resolved}")
        except ValueError:
            pass
    return failures


def direction_from_args(args: argparse.Namespace) -> str:
    direction = getattr(args, "direction", None)
    direction_file = getattr(args, "direction_file", None)
    if direction_file:
        direction = pathlib.Path(direction_file).expanduser().read_text(encoding="utf-8")
    return (direction or "").strip()


def filesystem_manifest(root: pathlib.Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(root).as_posix()
        if ".git/" in rel:
            continue
        records.append({
            "path": rel,
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return records


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-complete-revival-e2e-acceptance-design":
        failures.append("E2E 合同 schema_id 错误")
    if contract.get("status") != "executable_generic_methodology":
        failures.append("E2E 合同必须声明 executable_generic_methodology")
    if "fixed_sandbox_task" in contract:
        failures.append("E2E 合同不得包含 fixed_sandbox_task")
    text = json.dumps(contract, ensure_ascii=False)
    forbidden_fixed_terms = ["external-task-ledger-cli", "task-ledger", "任务账本命令行工具"]
    leaked = [term for term in forbidden_fixed_terms if term in text]
    if leaked:
        failures.append(f"E2E 合同仍包含固定场景词：{leaked}")
    commands = {item.get("name") for item in contract.get("commands", []) if isinstance(item, dict)}
    for required in [
        "runtime/bin/redcap complete-revival-e2e design-check",
        "runtime/bin/redcap complete-revival-e2e prepare --direction <text> --work-root <external-dir>",
        "runtime/bin/redcap complete-revival-e2e carrier-probe --work-root <external-dir>",
        "runtime/bin/redcap complete-revival-e2e run --direction <text> --work-root <external-dir>",
        "runtime/bin/redcap complete-revival-e2e self-check",
    ]:
        if required not in commands:
            failures.append(f"E2E 合同缺少命令定义：{required}")
    roles = contract.get("roles")
    if not isinstance(roles, dict):
        failures.append("E2E 合同缺少 roles")
    else:
        for role in ["cap_requester", "codex_cli_implementer", "cap_acceptor"]:
            if role not in roles:
                failures.append(f"E2E 合同缺少角色：{role}")
        implementer = roles.get("codex_cli_implementer", {}) if isinstance(roles.get("codex_cli_implementer"), dict) else {}
        hooks = implementer.get("required_hooks") if isinstance(implementer, dict) else []
        missing_hooks = [event for event in REQUIRED_HOOK_EVENTS if event not in hooks]
        if missing_hooks:
            failures.append(f"Codex CLI 承接方缺少 hook 要求：{missing_hooks}")
        loom_role_execution = implementer.get("loom_role_execution") if isinstance(implementer, dict) else None
        if not isinstance(loom_role_execution, dict):
            failures.append("Codex CLI 承接方缺少 loom_role_execution")
        else:
            roles_declared = set(loom_role_execution.get("roles", []) if isinstance(loom_role_execution.get("roles"), list) else [])
            missing_roles = sorted(set(LOOM_EXECUTION_ROLES) - roles_declared)
            if missing_roles:
                failures.append(f"loom_role_execution.roles 缺少角色：{missing_roles}")
            for key in [
                "independent_codex_cli_call_required",
                "different_session_id_required",
                "role_artifact_required",
                "role_run_receipt_required",
            ]:
                if loom_role_execution.get(key) is not True:
                    failures.append(f"loom_role_execution.{key} 必须为 true")
            if loom_role_execution.get("session_id_source") != "project-level Hook UserPromptSubmit events":
                failures.append("loom_role_execution.session_id_source 必须来自项目级 Hook UserPromptSubmit 事件")
    phases = [item.get("phase") for item in contract.get("workflow_template", []) if isinstance(item, dict)]
    for phase in ["direction_intake", "architecture_design", "implementation", "quality_assurance", "review_and_acceptance"]:
        if phase not in phases:
            failures.append(f"E2E 工作流缺少阶段：{phase}")
    probes = {item.get("id") for item in contract.get("negative_probes", []) if isinstance(item, dict)}
    for required_probe in [
        "missing-direction-cannot-run",
        "fixed-scenario-cannot-pass-design-check",
        "redcap-root-pollution-cannot-pass",
        "source-workspace-mutation-cannot-pass",
        "hook-carrier-missing-cannot-pass",
        "report-only-cannot-pass",
    ]:
        if required_probe not in probes:
            failures.append(f"E2E 合同缺少负向探针：{required_probe}")
    raw_package = contract.get("raw_evidence_package")
    if not isinstance(raw_package, dict):
        failures.append("E2E 合同缺少 raw_evidence_package")
    else:
        after_run = set(raw_package.get("required_files_after_run", []) if isinstance(raw_package.get("required_files_after_run"), list) else [])
        missing_after_run = sorted(set(MEANINGFUL_E2E_REQUIRED_FILES) - after_run)
        if missing_after_run:
            failures.append(f"E2E 运行后证据缺少有意义验收文件：{missing_after_run}")
        after_prepare = set(raw_package.get("required_files_after_prepare", []) if isinstance(raw_package.get("required_files_after_prepare"), list) else [])
        expected_templates = {name.replace(".json", "-template.json") for name in MEANINGFUL_E2E_REQUIRED_FILES}
        missing_templates = sorted(expected_templates - after_prepare)
        if missing_templates:
            failures.append(f"E2E 准备阶段缺少有意义验收模板：{missing_templates}")
    meaningful = contract.get("meaningful_acceptance")
    if not isinstance(meaningful, dict):
        failures.append("E2E 合同缺少 meaningful_acceptance")
    else:
        required_evidence = set(meaningful.get("required_evidence", []) if isinstance(meaningful.get("required_evidence"), list) else [])
        missing_evidence = sorted(set(MEANINGFUL_E2E_REQUIRED_FILES) - required_evidence)
        if missing_evidence:
            failures.append(f"meaningful_acceptance.required_evidence 缺失：{missing_evidence}")
        joined_gates = "\n".join(str(item) for item in meaningful.get("quality_gates", []))
        for gate in MEANINGFUL_E2E_REQUIRED_GATES:
            if gate not in joined_gates:
                failures.append(f"meaningful_acceptance.quality_gates 缺少关键约束：{gate}")
        pass_rule = str(meaningful.get("pass_rule") or "")
        if "Loom" not in pass_rule or "自我净化" not in pass_rule or "iteration-verdict" not in pass_rule:
            failures.append("meaningful_acceptance.pass_rule 必须覆盖 Loom、自我净化和 iteration-verdict")
    loop = contract.get("iteration_loop")
    if not isinstance(loop, dict):
        failures.append("E2E 合同缺少 iteration_loop")
    else:
        max_iterations = loop.get("max_iterations_before_cap_escalation")
        if not isinstance(max_iterations, int) or not (1 <= max_iterations <= 6):
            failures.append("iteration_loop.max_iterations_before_cap_escalation 必须是 1 到 6 的整数")
        for key in ["failure_ingestion", "next_round_rule", "stop_rule"]:
            value = str(loop.get(key) or "")
            if "failure-backlog" not in value and key != "stop_rule":
                failures.append(f"iteration_loop.{key} 必须绑定 failure-backlog")
        if "ready_for_engineering_use" not in str(loop.get("next_round_rule") or ""):
            failures.append("iteration_loop.next_round_rule 必须读取 ready_for_engineering_use")
    return failures


def package_and_init(project: pathlib.Path, evidence: pathlib.Path) -> dict[str, Any]:
    package_path = evidence / "redcap-package.zip"
    package_result = run_command([str(REDCAP), "project-install", "package", "--out", str(package_path)], timeout_seconds=180)
    if not package_result["ok"]:
        return {"ok": False, "step": "package", "command": command_receipt(package_result)}
    audit_result = run_command([str(REDCAP), "project-install", "audit-package", "--package", str(package_path)], timeout_seconds=180)
    if not audit_result["ok"]:
        return {
            "ok": False,
            "step": "audit-package",
            "package": str(package_path),
            "package_command": command_receipt(package_result),
            "audit_command": command_receipt(audit_result),
        }
    with zipfile.ZipFile(package_path) as archive:
        archive.extractall(project)
    runtime_bin = project / ".redcap" / "runtime" / "bin" / "redcap"
    init_result = run_command([
        "bash",
        str(runtime_bin),
        "project-install",
        "init",
        "--project",
        str(project),
    ], cwd=project, timeout_seconds=180)
    return {
        "ok": init_result["ok"],
        "step": "init",
        "package": str(package_path),
        "package_command": command_receipt(package_result),
        "audit_command": command_receipt(audit_result),
        "init_command": command_receipt(init_result),
    }


def build_requirements(direction: str) -> dict[str, Any]:
    return {
        "schema_id": "redcap-e2e-requirements",
        "created_at": iso_now(),
        "direction": direction,
        "cap_expanded_need": f"围绕“{direction}”交付一个可在本地运行、可检查、可维护的小型工程成果。",
        "scope": [
            "实现真实可运行产物，不只写文档",
            "提供清晰启动方式",
            "提供自动或半自动验证命令",
            "把 RedCap 运行证据保存在项目 .redcap 内",
            "通过 Loom 五角色独立 Codex CLI 调用完成需求、架构、开发、测试和评审",
            "任务前检索 RedCap 知识，任务后记录自我净化和 Cap 私有人格边界决策"
        ],
        "non_goals": [
            "外网部署",
            "真实账号或私密凭据接入",
            "不可回滚的系统级修改"
        ],
        "quality_bar": [
            "实现方必须先读 .redcap/evidence/e2e/requirements.json",
            "实现方必须记录知识检索结果；无相关条目时写 no_relevant_entry_reason，不能留空",
            "Loom 角色不能共用 session_id 或共享一份伪造角色证据",
            "实现方必须生成 architecture.md 和 test-results.json",
            "实现方必须在完成前运行验证命令并记录结果",
            "E2E 运行器必须独立执行安装包内 .redcap/runtime/prism/bin/prism check，失败即不能通过",
            "实现方不能把无法完成的事项标为完成"
        ]
    }


def build_acceptance(direction: str) -> dict[str, Any]:
    return {
        "schema_id": "redcap-e2e-acceptance-criteria",
        "direction_sha256": sha256_text(direction),
        "criteria": [
            "外部项目根目录包含真实交付文件",
            "存在可执行或可打开的入口说明",
            "存在 architecture.md，说明结构、边界、风险和测试方式",
            ".redcap/evidence/e2e 中存在实现日志、测试结果、文件清单和验收摘要",
            ".redcap/evidence/e2e/loom-role-session-manifest.json 证明五个 Loom 角色来自独立 Codex CLI 会话",
            ".redcap/evidence/e2e/loom-role-session-manifest-pre-review.json 供 reviewer 审核上游四个角色；最终五角色清单由运行器在 reviewer 退出后生成",
            ".redcap/evidence/e2e/self-purification-candidates.json 和 persona-distillation-decision.json 证明自我净化与人格边界已触发",
            ".redcap/evidence/e2e/package-prism-check.json 证明安装包内棱镜自检通过",
            "如果实现方遇到阻塞，必须写 blocked-package.json，而不是写 completion-marker.json"
        ],
        "completion_marker_rule": "只有客观证据全部通过时，才允许写 .redcap/evidence/e2e/completion-marker.json。"
    }


def build_implementer_prompt(project: pathlib.Path, direction: str) -> str:
    return textwrap.dedent(f"""
    你是独立实现方总说明，正在接受 RedCap E2E（端到端验收）测试。

    需求方向：
    {direction}

    工作目录：
    {project}

    本轮 E2E 不再允许一个 AI 用共享上下文包办所有 Loom 角色。运行器会依次启动五个独立 Codex CLI 调用：
    product_manager、architect、developer、tester、reviewer。

    每个角色必须遵守：
    1. 先阅读 .redcap/evidence/e2e/requirements.json 和 .redcap/evidence/e2e/acceptance-criteria.json。
    2. 在外部项目根目录内实现真实交付物，不要修改 RedCap 源仓库。
    3. 只处理自己角色范围内的任务，并把证据写入 .redcap/evidence/e2e/role-artifacts/<role>.json。
    4. 如果因为权限、网络、账号、环境缺失无法完成，写 .redcap/evidence/e2e/blocked-package.json，并说明阻塞条件。

    最终只有 reviewer 角色在确认真实交付、验证、Loom 会话、棱镜协助、自我净化、人格边界和失败回流都完成时，才允许写 completion-marker.json。
    """).strip() + "\n"


def role_artifact_path(evidence: pathlib.Path, role: str) -> pathlib.Path:
    return evidence / "role-artifacts" / f"{role}.json"


def role_workspace_path(evidence: pathlib.Path, role: str) -> pathlib.Path:
    return evidence / "role-workspaces" / role


def role_handoff(role: str) -> tuple[list[str], list[str]]:
    if role == "product_manager":
        return (
            ["requirements.json", "acceptance-criteria.json"],
            ["role-artifacts/product_manager.json", "knowledge-retrieval-evidence.json"],
        )
    if role == "architect":
        return (
            ["role-artifacts/product_manager.json", "requirements.json", "acceptance-criteria.json"],
            ["architecture.md", "risk-register.json", "role-artifacts/architect.json"],
        )
    if role == "developer":
        return (
            ["architecture.md", "risk-register.json", "acceptance-criteria.json"],
            ["implementation-log.json", "project-deliverables", "role-artifacts/developer.json"],
        )
    if role == "tester":
        return (
            ["implementation-log.json", "acceptance-criteria.json"],
            ["test-results.json", "negative-probes.json", "role-artifacts/tester.json"],
        )
    return (
        [
            "requirements.json",
            "architecture.md",
            "implementation-log.json",
            "test-results.json",
            "negative-probes.json",
            "loom-role-session-manifest-pre-review.json",
        ],
        [
            "review-verdict.json",
            "prism-assisted-review.json",
            "self-purification-candidates.json",
            "persona-distillation-decision.json",
            "failure-backlog.json",
            "iteration-verdict.json",
            "completion-marker.json",
            "role-artifacts/reviewer.json",
        ],
    )


def build_role_prompt(project: pathlib.Path, evidence: pathlib.Path, role: str, direction: str) -> str:
    inputs, outputs = role_handoff(role)
    common = f"""
    {ROLE_MARKER_PREFIX}{role}

    你是 RedCap E2E 的 Loom 角色：{role}。
    你必须作为独立 Codex CLI 调用工作，本角色不能冒充其他角色。

    项目根目录：{project}
    证据目录：{evidence}
    角色工作目录：{role_workspace_path(evidence, role)}
    需求方向：{direction}

    上游输入：
    {json.dumps(inputs, ensure_ascii=False)}

    本角色必须产出：
    {json.dumps(outputs, ensure_ascii=False)}

    通用要求：
    - 只修改外部项目，不要修改 RedCap 源仓库。
    - 本角色的结构化证据必须写入 {role_artifact_path(evidence, role)}。
    - role artifact 至少包含 schema_id、role、status、handoff_inputs、handoff_outputs、evidence_files、notes。
    - 如果缺少上游输入，请写 blocked-package.json 并说明阻塞，不要伪造完成。
    - 写完本角色要求的全部文件后，立即用一句中文说明已交付并停止，不要继续追加无关分析。
    """
    role_specific = {
        "product_manager": """
        你的任务：
        1. 阅读 requirements.json 和 acceptance-criteria.json。
        2. 运行 `.redcap/runtime/bin/redcap knowledge-gateway search loom`，把结果写入 knowledge-retrieval-evidence.json。
           该文件必须包含 search_ran=true、query="loom"、command、exit_code、matches；如果 matches 为空，必须写 no_relevant_entry_reason。
        3. 明确问题陈述、范围边界、验收重点，并写入 role-artifacts/product_manager.json。
        """,
        "architect": """
        你的任务：
        1. 阅读产品经理交付和验收标准。
        2. 写 architecture.md，说明结构、技术选型、运行方式、测试方式、风险和回滚。
        3. 写 risk-register.json 和 role-artifacts/architect.json。
        """,
        "developer": """
        你的任务：
        1. 按 architecture.md 实现一个可运行的本地项目。
        2. 优先选择简单、可本地验证的技术栈。
        3. 写 implementation-log.json 和 role-artifacts/developer.json。
        4. 如果提供验证脚本，机器验证输出必须写 verification-results.json 或其他非角色文件，不能写或覆盖 test-results.json；test-results.json 只属于 tester 角色。
        """,
        "tester": """
        你的任务：
        1. 运行项目验证命令，至少包含一个正向验证和一个负向/静态探针。
        2. 写 test-results.json、negative-probes.json 和 role-artifacts/tester.json；test-results.json 必须标记 role="tester"。
        3. 如果测试失败，必须把失败写清楚，不要替开发者修复。
        """,
        "reviewer": """
        你的任务：
        1. 审阅需求、架构、实现、测试和角色证据。
           注意：loom-role-session-manifest-pre-review.json 只用于审核上游四个角色；reviewer 自己的 session_id 会在你退出后由运行器写入最终 loom-role-session-manifest.json，因此不要因为最终清单在评审前缺少 reviewer 自身而阻塞。
        2. 写 review-verdict.json。
        3. 写 prism-assisted-review.json；本轮必须记录 used=true，至少说明一次对需求、架构、代码、测试或文档的棱镜协助或包内棱镜检查如何影响裁决。
        4. 写 self-purification-candidates.json，包含候选或 no_candidate_reason，并给出 decisions。decision 只允许 promote_public、keep_private、no_promote、defer_with_owner；需要后续沉淀但本轮不晋升时用 defer_with_owner。
        5. 写 persona-distillation-decision.json；privacy_class 必须是 cap-private，public_write=false，private_body_written=false，禁止写私有人格正文。
        6. 写 failure-backlog.json。若有开放问题，不得写 completion-marker.json。
        7. 写 iteration-verdict.json，evidence_checked 必须列出全部关键证据文件。
        8. 只有无开放问题、测试通过、证据齐全时才写 completion-marker.json。
        """,
    }[role]
    return textwrap.dedent(common + "\n" + role_specific).strip() + "\n"


def user_prompt_text(event: dict[str, Any]) -> str:
    prompt = event.get("prompt")
    if isinstance(prompt, dict):
        return str(prompt.get("normalized_excerpt") or "")
    if isinstance(prompt, str):
        return prompt
    return ""


def extract_role_sessions(project: pathlib.Path) -> dict[str, list[dict[str, Any]]]:
    events_path = project_hook_events_path(project)
    sessions: dict[str, list[dict[str, Any]]] = {role: [] for role in LOOM_EXECUTION_ROLES}
    if not events_path.exists():
        return sessions
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("event") != "UserPromptSubmit":
            continue
        text = user_prompt_text(event)
        match = re.search(rf"{re.escape(ROLE_MARKER_PREFIX)}([a-z_]+)", text)
        if not match:
            continue
        role = match.group(1)
        if role in sessions:
            sessions[role].append({
                "session_id": event.get("session_id"),
                "turn_id": event.get("turn_id"),
                "recorded_at": event.get("recorded_at"),
            })
    return sessions


def provider_state_dirs_for_role(role: str) -> list[pathlib.Path]:
    if role != "reviewer":
        return []
    kimi_state = pathlib.Path.home() / ".kimi-code"
    if not kimi_state.exists():
        return []
    return [kimi_state]


def build_role_session_manifest(
    project: pathlib.Path,
    evidence: pathlib.Path,
    role_results: dict[str, dict[str, Any]],
    *,
    include_pending: bool = False,
) -> dict[str, Any]:
    sessions = extract_role_sessions(project)
    roles: list[dict[str, Any]] = []
    alarms: list[dict[str, Any]] = []
    for role in LOOM_EXECUTION_ROLES:
        entries = sessions.get(role, [])
        session_ids = [str(item.get("session_id") or "") for item in entries if item.get("session_id")]
        unique_sessions = sorted(set(session_ids))
        command_ok = role_results.get(role, {}).get("ok") is True
        artifact_rel = f"role-artifacts/{role}.json"
        inputs, outputs = role_handoff(role)
        alarm: str | None = None
        role_has_started = role in role_results or bool(entries)
        if include_pending and not role_has_started:
            alarm = None
        elif not unique_sessions:
            alarm = "missing_session_id"
        elif len(unique_sessions) > 1:
            alarm = "multiple_sessions_for_single_role"
        elif not command_ok:
            alarm = "role_command_failed"
        if alarm:
            alarms.append({"role": role, "alarm": alarm})
        roles.append({
            "role": role,
            "session_id": unique_sessions[0] if len(unique_sessions) == 1 else None,
            "provider": "codex-cli",
            "started_at": entries[0].get("recorded_at") if entries else None,
            "last_seen_at": entries[-1].get("recorded_at") if entries else None,
            "context_state": "pending" if include_pending and not role_has_started else ("complete" if alarm is None else "degraded"),
            "alarm": alarm,
            "role_workspace": [f"role-workspaces/{role}"],
            "handoff_inputs": inputs,
            "handoff_outputs": outputs,
            "evidence_files": [
                artifact_rel,
                f"role-runs/{role}.json",
                f"role-messages/{role}.txt",
                f"role-prompts/{role}.md",
            ],
            "turn_ids": [item.get("turn_id") for item in entries if item.get("turn_id")],
        })
    return {
        "schema_id": "redcap-e2e-loom-role-session-manifest",
        "project_id": project.name,
        "task_id": "complete-revival-e2e",
        "roles": roles,
        "session_loss_alarms": alarms,
    }


def run_loom_role_pipeline(
    project: pathlib.Path,
    evidence: pathlib.Path,
    direction: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    role_results: dict[str, dict[str, Any]] = {}
    for dirname in ["role-prompts", "role-messages", "role-runs", "role-workspaces", "role-artifacts"]:
        (evidence / dirname).mkdir(parents=True, exist_ok=True)
    role_timeout = max(240, min(timeout_seconds, 900))
    for role in LOOM_EXECUTION_ROLES:
        role_workspace_path(evidence, role).mkdir(parents=True, exist_ok=True)
        prompt = build_role_prompt(project, evidence, role, direction)
        prompt_path = evidence / "role-prompts" / f"{role}.md"
        message_path = evidence / "role-messages" / f"{role}.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        argv = [
            "codex",
            "exec",
            "--cd",
            str(project),
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--full-auto",
        ]
        for state_dir in provider_state_dirs_for_role(role):
            argv.extend(["--add-dir", str(state_dir)])
        argv.extend([
            "--output-last-message",
            str(message_path),
            prompt,
        ])
        result = run_command(argv, cwd=project, timeout_seconds=role_timeout)
        receipt = command_receipt(result)
        receipt.update({
            "schema_id": "redcap-e2e-loom-role-run",
            "role": role,
            "prompt_path": str(prompt_path),
            "last_message": str(message_path),
            "expected_artifact": str(role_artifact_path(evidence, role)),
        })
        write_json(evidence / "role-runs" / f"{role}.json", receipt)
        role_results[role] = receipt
        append_jsonl(evidence / "workflow-events.jsonl", {
            "event": "loom_role_completed",
            "role": role,
            "recorded_at": iso_now(),
            "ok": receipt["ok"],
        })
        if not result["ok"]:
            break
        if role == "tester":
            pre_review_manifest = build_role_session_manifest(project, evidence, role_results, include_pending=True)
            write_json(evidence / "loom-role-session-manifest-pre-review.json", pre_review_manifest)
    manifest = build_role_session_manifest(project, evidence, role_results)
    write_json(evidence / "loom-role-session-manifest.json", manifest)
    ok = all(role_results.get(role, {}).get("ok") is True for role in LOOM_EXECUTION_ROLES)
    ok = ok and not manifest["session_loss_alarms"]
    aggregate = {
        "schema_id": "redcap-e2e-loom-role-pipeline-run",
        "ok": ok,
        "roles": role_results,
        "session_manifest": "loom-role-session-manifest.json",
        "failures": [],
    }
    if not ok:
        aggregate["failures"].append("Loom 角色管线失败或会话证据不完整")
    write_json(evidence / "codex-run.json", aggregate)
    reviewer_message = evidence / "role-messages" / "reviewer.txt"
    if reviewer_message.exists():
        shutil.copyfile(reviewer_message, evidence / "codex-last-message.txt")
    return aggregate


def prepare_project(direction: str, work_root: pathlib.Path, project_name: str | None = None) -> dict[str, Any]:
    guard_before = source_workspace_snapshot()
    failures = ensure_external_path(work_root)
    if not direction.strip():
        failures.append("缺少 direction：真实 E2E 必须由一个大致需求方向驱动")
    if failures:
        return attach_source_workspace_guard({"ok": False, "failures": failures}, guard_before)
    work_root.mkdir(parents=True, exist_ok=True)
    project = (work_root / (project_name or f"redcap-e2e-{slugify(direction)}")).resolve()
    if project.exists():
        shutil.rmtree(project)
    project.mkdir(parents=True)
    evidence = project / ".redcap" / "evidence" / "e2e"
    evidence.mkdir(parents=True, exist_ok=True)
    install_result = package_and_init(project, evidence)
    if not install_result.get("ok"):
        return attach_source_workspace_guard({
            "ok": False,
            "failures": ["项目级 .redcap 安装失败"],
            "install": install_result,
            "project": str(project),
        }, guard_before)
    evidence.mkdir(parents=True, exist_ok=True)
    requirements = build_requirements(direction)
    acceptance = build_acceptance(direction)
    prompt = build_implementer_prompt(project, direction)
    write_json(evidence / "requirements.json", requirements)
    write_json(evidence / "acceptance-criteria.json", acceptance)
    (evidence / "architecture-template.md").write_text(
        "# 架构设计\n\n## 目标\n\n## 目录结构\n\n## 运行方式\n\n## 验证方式\n\n## 风险与回滚\n",
        encoding="utf-8",
    )
    write_json(evidence / "loom-role-session-manifest-template.json", {
        "schema_id": "redcap-e2e-loom-role-session-manifest",
        "project_id": project.name,
        "task_id": "complete-revival-e2e",
        "roles": [
            {
                "role": role,
                "session_id": "<derived from project hook UserPromptSubmit>",
                "provider": "codex-cli",
                "context_state": "complete|degraded",
                "alarm": None,
                "role_workspace": [f"role-workspaces/{role}"],
                "handoff_inputs": role_handoff(role)[0],
                "handoff_outputs": role_handoff(role)[1],
                "evidence_files": [
                    f"role-artifacts/{role}.json",
                    f"role-runs/{role}.json",
                    f"role-messages/{role}.txt",
                    f"role-prompts/{role}.md"
                ]
            }
            for role in LOOM_EXECUTION_ROLES
        ],
        "session_loss_alarms": []
    })
    write_json(evidence / "loom-role-session-manifest-pre-review-template.json", {
        "schema_id": "redcap-e2e-loom-role-session-manifest",
        "purpose": "reviewer audits upstream roles before its own session can be finalized",
        "project_id": project.name,
        "task_id": "complete-revival-e2e",
        "roles": [
            {
                "role": role,
                "session_id": "<derived from project hook UserPromptSubmit>" if role != "reviewer" else None,
                "provider": "codex-cli",
                "context_state": "complete" if role != "reviewer" else "pending",
                "alarm": None,
                "role_workspace": [f"role-workspaces/{role}"],
                "handoff_inputs": role_handoff(role)[0],
                "handoff_outputs": role_handoff(role)[1],
                "evidence_files": [
                    f"role-artifacts/{role}.json",
                    f"role-runs/{role}.json",
                    f"role-messages/{role}.txt",
                    f"role-prompts/{role}.md"
                ]
            }
            for role in LOOM_EXECUTION_ROLES
        ],
        "session_loss_alarms": []
    })
    write_json(evidence / "prism-assisted-review-template.json", {
        "schema_id": "redcap-e2e-prism-assisted-review",
        "used": True,
        "reviews": [],
        "skip_reason": None,
        "cap_decision": "<required>"
    })
    write_json(evidence / "knowledge-retrieval-evidence-template.json", {
        "schema_id": "redcap-e2e-knowledge-retrieval-evidence",
        "search_ran": True,
        "command": ".redcap/runtime/bin/redcap knowledge-gateway search <query>",
        "query": "<required>",
        "matches": [],
        "used_entries": [],
        "no_relevant_entry_reason": "<required if matches empty and search ran>",
        "skip_reason": None
    })
    write_json(evidence / "self-purification-candidates-template.json", {
        "schema_id": "redcap-e2e-self-purification-candidates",
        "candidates": [],
        "no_candidate_reason": "<required if candidates empty>",
        "allowed_decisions": ["promote_public", "keep_private", "no_promote", "defer_with_owner"],
        "decisions": []
    })
    write_json(evidence / "persona-distillation-decision-template.json", {
        "schema_id": "redcap-e2e-persona-distillation-decision",
        "privacy_class": "cap-private",
        "public_write": False,
        "decision": "keep_private|no_signal|defer_with_owner",
        "private_body_written": False,
        "reason": "<required>"
    })
    write_json(evidence / "test-results-template.json", {
        "schema_id": "redcap-e2e-test-results",
        "role": "tester",
        "commands": [],
        "positive_checks": [],
        "passed": "<boolean>"
    })
    write_json(evidence / "negative-probes-template.json", {
        "schema_id": "redcap-e2e-negative-probes",
        "role": "tester",
        "probes": [],
        "passed": "<boolean>"
    })
    write_json(evidence / "package-prism-check-template.json", {
        "schema_id": "redcap-e2e-package-prism-check",
        "producer": "e2e-runner",
        "command": ".redcap/runtime/prism/bin/prism check",
        "required_marker": "PRISM_CHECK_OK",
        "failure_policy": "blocking"
    })
    write_json(evidence / "failure-backlog-template.json", {
        "schema_id": "redcap-e2e-failure-backlog",
        "open_items": [],
        "closed_items": [],
        "next_round_required": False
    })
    write_json(evidence / "iteration-verdict-template.json", {
        "schema_id": "redcap-e2e-iteration-verdict",
        "ready_for_engineering_use": False,
        "status": "pass|fail|blocked",
        "remaining_issues": [],
        "evidence_checked": sorted(REQUIRED_EVIDENCE_CHECKS)
    })
    (evidence / "implementer-prompt.md").write_text(prompt, encoding="utf-8")
    write_json(evidence / "review-verdict-template.json", {
        "schema_id": "redcap-e2e-review-verdict",
        "status": "pending",
        "must_check": [
            "requirements_covered",
            "deliverables_exist",
            "verification_ran",
            "hook_events_present",
            "runtime_artifacts_inside_project_redcap"
        ]
    })
    append_jsonl(evidence / "workflow-events.jsonl", {
        "event": "direction_intake",
        "recorded_at": iso_now(),
        "direction_sha256": sha256_text(direction),
        "project": str(project),
    })
    manifest = {
        "schema_id": "redcap-ai-e2e-manifest",
        "created_at": iso_now(),
        "project": str(project),
        "work_root": str(work_root),
        "direction_sha256": sha256_text(direction),
        "redcap_package_installed": True,
        "hook_config": str(project / ".codex" / "hooks.json"),
        "evidence_root": str(evidence),
        "required_after_prepare": load_json(CONTRACT)["raw_evidence_package"]["required_files_after_prepare"],
        "install": install_result,
    }
    write_json(evidence / "manifest.json", manifest)
    write_json(evidence / "filesystem-before.json", {"files": filesystem_manifest(project)})
    result = {
        "ok": True,
        "schema_id": "redcap-ai-e2e-prepare-result",
        "project": str(project),
        "evidence_root": str(evidence),
        "implementer_prompt": str(evidence / "implementer-prompt.md"),
        "manifest": str(evidence / "manifest.json"),
        "failures": [],
    }
    result = attach_source_workspace_guard(result, guard_before)
    write_json(evidence / "source-workspace-guard.json", result["source_workspace_guard"])
    return result


def parse_hook_events(path: pathlib.Path) -> list[str]:
    if not path.exists():
        return []
    events: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("event"), str):
            events.append(payload["event"])
    return events


def project_hook_events_path(project: pathlib.Path) -> pathlib.Path:
    runtime_events = project / ".redcap" / "evidence" / "host-hooks" / "codex" / "events.jsonl"
    if runtime_events.exists():
        return runtime_events
    return project / ".redcap" / "assets" / "evidence" / "host-hooks" / "codex" / "events.jsonl"


def load_optional_json(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def validate_meaningful_e2e_evidence(evidence: pathlib.Path) -> dict[str, Any]:
    failures: list[str] = []
    for rel in MEANINGFUL_E2E_REQUIRED_FILES:
        if not (evidence / rel).exists():
            failures.append(f"缺少有意义 E2E 证据：{rel}")
    role_manifest = load_optional_json(evidence / "loom-role-session-manifest.json")
    if role_manifest is not None:
        roles = role_manifest.get("roles")
        if not isinstance(roles, list) or not roles:
            failures.append("loom-role-session-manifest.roles 必须是非空列表")
        else:
            for role in roles:
                if not isinstance(role, dict):
                    failures.append("loom-role-session-manifest.roles 条目必须是对象")
                    continue
                if not (isinstance(role.get("role"), str) and role["role"].strip()):
                    failures.append("Loom 角色条目缺少 role")
                if not (isinstance(role.get("session_id"), str) and role["session_id"].strip()):
                    failures.append(f"Loom 角色缺少 session_id：{role.get('role')}")
                if role.get("context_state") == "degraded" and not role.get("alarm"):
                    failures.append(f"Loom 角色上下文降级但缺少 alarm：{role.get('role')}")
    prism_review = load_optional_json(evidence / "prism-assisted-review.json")
    if prism_review is not None:
        if prism_review.get("used") is True:
            reviews = prism_review.get("reviews")
            if not isinstance(reviews, list) or not reviews:
                failures.append("prism-assisted-review.used=true 时 reviews 必须非空")
            if not prism_review.get("cap_decision"):
                failures.append("prism-assisted-review 必须记录 cap_decision")
        elif not prism_review.get("skip_reason"):
            failures.append("prism-assisted-review 未调用棱镜时必须写 skip_reason")
    retrieval = load_optional_json(evidence / "knowledge-retrieval-evidence.json")
    if retrieval is not None and not (
        retrieval.get("matches")
        or retrieval.get("skip_reason")
        or retrieval.get("no_relevant_entry_reason")
    ):
        failures.append("knowledge-retrieval-evidence 必须记录匹配项、无相关条目理由或跳过理由")
    purification = load_optional_json(evidence / "self-purification-candidates.json")
    if purification is not None and not (purification.get("candidates") or purification.get("no_candidate_reason")):
        failures.append("self-purification-candidates 必须记录候选或无候选理由")
    test_results = load_optional_json(evidence / "test-results.json")
    if test_results is not None and test_results.get("role") != "tester":
        failures.append("test-results.json 必须由 tester 角色产出，不能被验证脚本或其他角色覆盖")
    negative_probes = load_optional_json(evidence / "negative-probes.json")
    if negative_probes is not None and negative_probes.get("role") != "tester":
        failures.append("negative-probes.json 必须由 tester 角色产出")
    persona = load_optional_json(evidence / "persona-distillation-decision.json")
    if persona is not None:
        if persona.get("public_write") is not False:
            failures.append("persona-distillation-decision.public_write 必须为 false")
        if persona.get("private_body_written") is not False:
            failures.append("persona-distillation-decision.private_body_written 必须为 false")
        if persona.get("privacy_class") != "cap-private":
            failures.append("persona-distillation-decision.privacy_class 必须是 cap-private")
    package_prism = load_optional_json(evidence / "package-prism-check.json")
    if package_prism is not None:
        stdout_tail = str(package_prism.get("stdout_tail") or "")
        if package_prism.get("ok") is not True or package_prism.get("exit_code") != 0:
            failures.append("package-prism-check 必须成功退出")
        if "PRISM_CHECK_OK" not in stdout_tail:
            failures.append("package-prism-check 必须包含 PRISM_CHECK_OK")
    backlog = load_optional_json(evidence / "failure-backlog.json")
    if backlog is not None:
        open_items = backlog.get("open_items")
        if open_items is not None and not isinstance(open_items, list):
            failures.append("failure-backlog.open_items 必须是列表")
        closed_non_blocking = backlog.get("closed_non_blocking")
        if closed_non_blocking:
            failures.append("failure-backlog 不允许存在未解释的 closed_non_blocking；请转为 closed_items 并提供验证证据，或保留为 open_items")
    verdict = load_optional_json(evidence / "iteration-verdict.json")
    ready = False
    if verdict is not None:
        ready = verdict.get("ready_for_engineering_use") is True
        if verdict.get("status") not in {"pass", "fail", "blocked"}:
            failures.append("iteration-verdict.status 必须是 pass、fail 或 blocked")
        if ready and verdict.get("status") != "pass":
            failures.append("ready_for_engineering_use=true 时 iteration-verdict.status 必须是 pass")
        if not isinstance(verdict.get("evidence_checked"), list) or not verdict.get("evidence_checked"):
            failures.append("iteration-verdict.evidence_checked 必须非空")
    followthrough = validate_e2e_evidence_quality(evidence)
    if not followthrough["ok"]:
        failures.extend(f"followthrough: {item}" for item in followthrough["failures"])
    return {
        "schema_id": "redcap-e2e-meaningful-evidence-check",
        "ok": not failures,
        "ready_for_engineering_use": ready,
        "required_files": MEANINGFUL_E2E_REQUIRED_FILES,
        "followthrough": followthrough,
        "failures": failures,
    }


def carrier_probe(work_root: pathlib.Path, timeout_seconds: int = 240) -> dict[str, Any]:
    guard_before = source_workspace_snapshot()
    failures = ensure_external_path(work_root)
    if failures:
        return attach_source_workspace_guard({"ok": False, "failures": failures}, guard_before)
    work_root.mkdir(parents=True, exist_ok=True)
    project = (work_root / "redcap-e2e-carrier-probe").resolve()
    if project.exists():
        shutil.rmtree(project)
    (project / ".codex").mkdir(parents=True)
    (project / ".redcap" / "evidence" / "e2e").mkdir(parents=True)
    hook_script = project / ".redcap" / "hook_probe.py"
    events_path = project / ".redcap" / "evidence" / "e2e" / "carrier-hook-events.jsonl"
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
    def hook(event: str) -> dict[str, Any]:
        return {
            "type": "command",
            "command": f"/usr/bin/python3 {str(hook_script)!r} --event {event}",
            "timeout": 10,
            "statusMessage": f"RedCap E2E carrier probe {event}",
        }
    (project / ".codex" / "hooks.json").write_text(json.dumps({
        "hooks": {
            "SessionStart": [{"matcher": "startup|resume|clear|compact", "hooks": [hook("SessionStart")]}],
            "UserPromptSubmit": [{"hooks": [hook("UserPromptSubmit")]}],
            "PreToolUse": [{"matcher": "Bash|apply_patch|Edit|Write", "hooks": [hook("PreToolUse")]}],
            "PostToolUse": [{"matcher": ".*", "hooks": [hook("PostToolUse")]}],
            "Stop": [{"hooks": [hook("Stop")]}],
        }
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    last_message = project / ".redcap" / "evidence" / "e2e" / "carrier-last-message.txt"
    result = run_command([
        "codex",
        "exec",
        "--cd",
        str(project),
        "--skip-git-repo-check",
        "--sandbox",
        "workspace-write",
        "--full-auto",
        "--output-last-message",
        str(last_message),
        "请使用 shell 执行 pwd，然后最终只回答 carrier-probe-ok。",
    ], cwd=project, timeout_seconds=timeout_seconds)
    events = parse_hook_events(events_path)
    missing = [event for event in REQUIRED_HOOK_EVENTS if event not in events]
    probe = {
        "schema_id": "redcap-ai-e2e-carrier-probe",
        "ok": result["ok"] and not missing,
        "project": str(project),
        "events_path": str(events_path),
        "events": events,
        "missing_events": missing,
        "command": command_receipt(result),
        "last_message": str(last_message),
        "failures": [],
    }
    if not result["ok"]:
        probe["failures"].append("Codex CLI 承载探针命令失败")
    if missing:
        probe["failures"].append(f"Codex CLI 没有触发全部项目级 hook：{missing}")
    probe = attach_source_workspace_guard(probe, guard_before)
    write_json(project / ".redcap" / "evidence" / "e2e" / "carrier-probe.json", probe)
    return probe


def run_e2e(direction: str, work_root: pathlib.Path, timeout_seconds: int = 900) -> dict[str, Any]:
    provider_readiness = provider_readiness_check()
    if provider_readiness.get("ok") is not True:
        return {
            "schema_id": "redcap-ai-e2e-run-result",
            "ok": False,
            "ready_for_engineering_use": False,
            "blocked_before_project_run": True,
            "provider_readiness": provider_readiness,
            "failures": provider_readiness.get("failures", []),
        }
    prepared = prepare_project(direction, work_root)
    if not prepared.get("ok"):
        return prepared
    project = pathlib.Path(str(prepared["project"]))
    evidence = pathlib.Path(str(prepared["evidence_root"]))
    guard_before = source_workspace_snapshot()
    result = run_loom_role_pipeline(project, evidence, direction, timeout_seconds)
    write_json(evidence / "filesystem-after.json", {"files": filesystem_manifest(project)})
    package_prism = run_command([
        ".redcap/runtime/prism/bin/prism",
        "check",
    ], cwd=project, timeout_seconds=240)
    write_json(evidence / "package-prism-check.json", command_receipt(package_prism))
    hook_events = parse_hook_events(project_hook_events_path(project))
    missing_hooks = [event for event in REQUIRED_HOOK_EVENTS if event not in hook_events]
    meaningful = validate_meaningful_e2e_evidence(evidence)
    write_json(evidence / "revival-followthrough-e2e-check.json", meaningful["followthrough"])
    write_json(evidence / "meaningful-evidence-check.json", meaningful)
    write_json(evidence / "hook-events-summary.json", {
        "schema_id": "redcap-e2e-hook-events-summary",
        "events": hook_events,
        "missing_events": missing_hooks,
    })
    completion_marker = evidence / "completion-marker.json"
    summary = {
        "schema_id": "redcap-ai-e2e-run-result",
        "ok": result["ok"] and not missing_hooks and completion_marker.exists(),
        "project": str(project),
        "evidence_root": str(evidence),
        "codex_cli_ok": result["ok"],
        "package_prism_ok": package_prism["ok"],
        "hook_events_ok": not missing_hooks,
        "meaningful_evidence_ok": meaningful["ok"],
        "ready_for_engineering_use": meaningful["ready_for_engineering_use"],
        "completion_marker_present": completion_marker.exists(),
        "failures": [],
    }
    if not result["ok"]:
        summary["failures"].append("Codex CLI Loom 角色管线执行失败")
    if not package_prism["ok"]:
        summary["failures"].append("安装包内棱镜自检失败")
    if missing_hooks:
        summary["failures"].append(f"缺少项目级 hook 事件：{missing_hooks}")
    if not completion_marker.exists():
        summary["failures"].append("实现方没有写入 completion-marker.json；这可能表示任务未完成或被阻塞")
    if not meaningful["ok"]:
        summary["failures"].append(f"有意义 E2E 证据不完整：{meaningful['failures']}")
    if not meaningful["ready_for_engineering_use"]:
        summary["failures"].append("iteration-verdict 未证明 ready_for_engineering_use=true")
    summary["ok"] = summary["ok"] and package_prism["ok"] and meaningful["ok"] and meaningful["ready_for_engineering_use"]
    summary = attach_source_workspace_guard(summary, guard_before)
    (evidence / "e2e-acceptance-summary.md").write_text(
        "# RedCap E2E 验收摘要\n\n"
        f"- 项目：{project}\n"
        f"- Codex CLI 执行：{'通过' if result['ok'] else '失败'}\n"
        f"- 包内棱镜自检：{'通过' if package_prism['ok'] else '失败'}\n"
        f"- Hook 事件：{'通过' if not missing_hooks else '缺失 ' + ', '.join(missing_hooks)}\n"
        f"- 完成标记：{'存在' if completion_marker.exists() else '不存在'}\n",
        encoding="utf-8",
    )
    write_json(evidence / "source-workspace-guard-run.json", summary["source_workspace_guard"])
    write_json(evidence / "run-summary.json", summary)
    return summary


def cmd_design_check(_: argparse.Namespace) -> int:
    result = {
        "schema_id": "redcap-ai-e2e-design-check",
        "ok": True,
        "contract": str(CONTRACT),
        "failures": validate_contract(load_json(CONTRACT)),
    }
    result["ok"] = not result["failures"]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_AI_E2E_DESIGN_OK")
        return 0
    return 1


def cmd_prepare(args: argparse.Namespace) -> int:
    result = prepare_project(direction_from_args(args), resolve_work_root(args.work_root), args.project_name)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok"):
        print("REDCAP_AI_E2E_PREPARE_OK")
        return 0
    return 1


def cmd_carrier_probe(args: argparse.Namespace) -> int:
    result = carrier_probe(resolve_work_root(args.work_root), args.timeout_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok"):
        print("REDCAP_AI_E2E_CARRIER_PROBE_OK")
        return 0
    return 1


def cmd_run(args: argparse.Namespace) -> int:
    result = run_e2e(direction_from_args(args), resolve_work_root(args.work_root), args.timeout_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok"):
        print("REDCAP_AI_E2E_RUN_OK")
        return 0
    return 1


def cmd_self_check(args: argparse.Namespace) -> int:
    failures: list[str] = []
    if validate_contract(load_json(CONTRACT)):
        failures.append("通用 E2E 合同检查失败")
    with tempfile.TemporaryDirectory(prefix="redcap-ai-e2e-self-check-") as raw:
        work_root = pathlib.Path(raw).resolve()
        missing_direction = prepare_project("", work_root / "missing")
        if missing_direction.get("ok") is True:
            failures.append("缺失 direction 的 prepare 没有失败")
        prepared = prepare_project("自检方向：交付一个本地可验证的小型工具", work_root / "prepare")
        if prepared.get("ok") is not True:
            failures.append(f"prepare 正向探针失败：{prepared.get('failures')}")
        else:
            evidence = pathlib.Path(str(prepared["evidence_root"]))
            for rel in load_json(CONTRACT)["raw_evidence_package"]["required_files_after_prepare"]:
                if not (evidence / rel).exists():
                    failures.append(f"prepare 后缺少证据文件：{rel}")
        guard_probe = source_workspace_guard_negative_probe()
        if guard_probe.get("ok") is not True:
            failures.append(f"源工作区保护负向探针失败：{guard_probe.get('failures')}")
        if not args.skip_carrier_probe:
            probe = carrier_probe(work_root / "carrier", args.timeout_seconds)
            if probe.get("ok") is not True:
                failures.append(f"Codex CLI 承载探针失败：{probe.get('failures')}")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_AI_E2E_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap 通用纯 AI E2E 运行器")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("design-check").set_defaults(func=cmd_design_check)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--direction")
    prepare.add_argument("--direction-file")
    prepare.add_argument("--work-root")
    prepare.add_argument("--project-name")
    prepare.set_defaults(func=cmd_prepare)
    carrier = sub.add_parser("carrier-probe")
    carrier.add_argument("--work-root")
    carrier.add_argument("--timeout-seconds", type=int, default=240)
    carrier.set_defaults(func=cmd_carrier_probe)
    run = sub.add_parser("run")
    run.add_argument("--direction")
    run.add_argument("--direction-file")
    run.add_argument("--work-root")
    run.add_argument("--timeout-seconds", type=int, default=900)
    run.set_defaults(func=cmd_run)
    self_check = sub.add_parser("self-check")
    self_check.add_argument("--skip-carrier-probe", action="store_true")
    self_check.add_argument("--timeout-seconds", type=int, default=240)
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

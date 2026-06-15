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
import signal
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import zipfile
from typing import Any

from revival_followthrough import PRIVATE_PERSONA_MARKERS, REQUIRED_EVIDENCE_CHECKS, validate_e2e_evidence_quality


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REDCAP = REPO_ROOT / "runtime" / "bin" / "redcap"
CONTRACT = REPO_ROOT / "assets" / "contracts" / "complete-revival-e2e-acceptance-design.json"
DEFAULT_PERSISTENT_WORK_ROOT = pathlib.Path.home() / "workspace" / "redcap-e2e-runs"
REQUIRED_HOOK_EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"]
LOOM_EXECUTION_ROLES = ["product_manager", "architect", "developer", "tester", "reviewer"]
ROLE_MARKER_PREFIX = "REDCAP_LOOM_ROLE="
ROLE_TIMEOUT_SECONDS = {
    "product_manager": 240,
    "architect": 300,
    "developer": 420,
    "tester": 360,
    "reviewer": 360,
}
CODEX_ROLE_MODEL = os.environ.get("REDCAP_E2E_CODEX_ROLE_MODEL", "gpt-5.5")
CODEX_ROLE_REASONING_EFFORT = os.environ.get("REDCAP_E2E_CODEX_ROLE_REASONING_EFFORT", "medium")
CODEX_ROLE_DISABLE_PLUGINS = os.environ.get("REDCAP_E2E_CODEX_ROLE_DISABLE_PLUGINS", "1") != "0"
CODEX_ROLE_MAX_ATTEMPTS = int(os.environ.get("REDCAP_E2E_CODEX_ROLE_MAX_ATTEMPTS", "2"))
CODEX_ROLE_RETRYABLE_STDERR_MARKERS = [
    "responses_websocket",
    "stream disconnected",
    "tls handshake eof",
    "error sending request",
    "http/request failed",
]
MEANINGFUL_E2E_REQUIRED_FILES = [
    "loom-role-session-manifest.json",
    "loom-role-session-manifest-pre-review.json",
    "role-gate-clearance-summary.json",
    "prism-assisted-review.json",
    "knowledge-retrieval-evidence.json",
    "self-purification-candidates.json",
    "persona-distillation-decision.json",
    "test-results.json",
    "negative-probes.json",
    "package-prism-check.json",
    "final-runner-test-results.json",
    "browser-inspection.json",
    "final-evidence-bundle.json",
    "final-prism-review.json",
    "failure-backlog.json",
    "iteration-verdict.json",
    "completion-marker.json",
]
REVIEWER_RUNNER_OWNED_FOLLOW_UP = [
    "completion-marker.json",
    "iteration-verdict.json",
    "final-prism-review.json",
    "final-runner-test-results.json",
]
ROLE_EVIDENCE_FILES = {
    "requirements.json",
    "acceptance-criteria.json",
    "knowledge-retrieval-evidence.json",
    "implementation-log.json",
    "verification-results.json",
    "test-results.json",
    "negative-probes.json",
    "review-verdict.json",
    "prism-assisted-review.json",
    "self-purification-candidates.json",
    "persona-distillation-decision.json",
    "failure-backlog.json",
}
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


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            unique.append(value)
            seen.add(value)
    return unique


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
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            argv,
            cwd=str(cwd),
            stdin=subprocess.PIPE if stdin is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        stdout, stderr = process.communicate(input=stdin, timeout=timeout_seconds)
        return {
            "argv": argv,
            "cwd": str(cwd),
            "exit_code": process.returncode,
            "ok": process.returncode == 0,
            "timed_out": False,
            "timeout_seconds": timeout_seconds,
            "started_at": started.replace(microsecond=0).isoformat(),
            "finished_at": iso_now(),
            "stdout": stdout,
            "stderr": stderr,
        }
    except subprocess.TimeoutExpired:
        killed = kill_process_group(process)
        try:
            stdout, stderr = process.communicate(timeout=3) if process is not None else ("", "")
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
        return {
            "argv": argv,
            "cwd": str(cwd),
            "exit_code": 124,
            "ok": False,
            "timed_out": True,
            "timeout_seconds": timeout_seconds,
            "process_group_killed": killed,
            "started_at": started.replace(microsecond=0).isoformat(),
            "finished_at": iso_now(),
            "stdout": stdout,
            "stderr": stderr,
        }


def kill_process_group(process: subprocess.Popen[str] | None, grace_seconds: float = 2.0) -> bool:
    if process is None or process.poll() is not None:
        return False
    killed = False
    try:
        os.killpg(process.pid, signal.SIGTERM)
        killed = True
    except ProcessLookupError:
        return killed
    except OSError:
        try:
            process.terminate()
            killed = True
        except OSError:
            return killed
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return killed
        time.sleep(0.05)
    try:
        os.killpg(process.pid, signal.SIGKILL)
        killed = True
    except ProcessLookupError:
        return killed
    except OSError:
        try:
            process.kill()
            killed = True
        except OSError:
            pass
    return killed


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
        "process_group_killed": result.get("process_group_killed"),
        "stdout_length": len(stdout),
        "stdout_sha256": sha256_text(stdout) if stdout else None,
        "stderr_length": len(stderr),
        "stderr_sha256": sha256_text(stderr) if stderr else None,
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
    }


def extract_codex_session_id(stderr: str) -> str | None:
    match = re.search(r"session id:\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", stderr)
    return match.group(1) if match else None


def role_failure_retry_reason(result: dict[str, Any], artifact_exists: bool) -> str | None:
    if result.get("ok") is True or artifact_exists:
        return None
    stderr = str(result.get("stderr") or "").casefold()
    stdout = str(result.get("stdout") or "")
    if stdout.strip():
        return None
    for marker in CODEX_ROLE_RETRYABLE_STDERR_MARKERS:
        if marker in stderr:
            return f"codex transient transport marker: {marker}"
    return None


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
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (DEFAULT_PERSISTENT_WORK_ROOT / f"run-{stamp}-{os.getpid()}").resolve()


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
            "默认优先选择无外部依赖、无需联网安装的实现和验证方案；除非需求明确要求，不得把 Vite、Playwright 或其他重型依赖作为默认方案",
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
            "默认实现不得依赖联网安装或重型测试栈；如果确需外部依赖，必须在 risk-register.json 中写明理由和降级方案",
            ".redcap/evidence/e2e/self-purification-candidates.json 和 persona-distillation-decision.json 证明自我净化与人格边界已触发",
            ".redcap/evidence/e2e/package-prism-check.json 证明安装包内棱镜自检通过",
            ".redcap/evidence/e2e/final-runner-test-results.json 证明运行器独立重跑了项目验证",
            ".redcap/evidence/e2e/final-evidence-bundle.json 证明最终证据带有可检查哈希和摘要",
            ".redcap/evidence/e2e/final-prism-review.json 证明最终完成声明经过运行器侧棱镜复核",
            "如果实现方遇到阻塞，必须写 blocked-package.json，而不是写 completion-marker.json"
        ],
        "completion_marker_rule": "只有 E2E 运行器在 reviewer 退出后确认客观证据全部通过时，才允许写 .redcap/evidence/e2e/completion-marker.json。"
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

    reviewer 角色只负责评审和记录问题，不能写 completion-marker.json 或 iteration-verdict.json。
    最终完成标记由 E2E 运行器在 reviewer 退出后，基于最终角色清单、测试回执、证据哈希和棱镜复核独立写入。
    """).strip() + "\n"


def role_artifact_path(evidence: pathlib.Path, role: str) -> pathlib.Path:
    return evidence / "role-artifacts" / f"{role}.json"


def role_workspace_path(evidence: pathlib.Path, role: str) -> pathlib.Path:
    return evidence / "role-workspaces" / role


def role_gate_clearance_path(evidence: pathlib.Path, role: str) -> pathlib.Path:
    return evidence / "role-gate-clearance" / f"{role}.json"


def role_logical_path(project: pathlib.Path, evidence: pathlib.Path, logical_name: str, *, for_output: bool) -> pathlib.Path | None:
    if logical_name == "project-deliverables":
        return None
    if logical_name.startswith("role-artifacts/"):
        return evidence / logical_name
    if logical_name in ROLE_EVIDENCE_FILES:
        return evidence / logical_name
    evidence_path = evidence / logical_name
    if not for_output and evidence_path.exists():
        return evidence_path
    return project / logical_name


def role_path_records(
    project: pathlib.Path,
    evidence: pathlib.Path,
    logical_names: list[str],
    *,
    for_output: bool,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for logical_name in logical_names:
        path = role_logical_path(project, evidence, logical_name, for_output=for_output)
        record: dict[str, Any] = {
            "name": logical_name,
            "path": None if path is None else str(path),
            "relative_path": None if path is None else path.relative_to(project).as_posix(),
            "location": "project-deliverables" if path is None else ("evidence" if path.is_relative_to(evidence) else "project-root"),
        }
        if not for_output and path is not None:
            record["exists"] = path.exists()
        records.append(record)
    return records


def build_role_gate_clearance(project: pathlib.Path, evidence: pathlib.Path, role: str, direction: str) -> dict[str, Any]:
    inputs, outputs = role_handoff(role)
    required_reads = unique_preserve_order(["requirements.json", "acceptance-criteria.json", *inputs])
    return {
        "schema_id": "redcap-e2e-role-gate-clearance",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "role": role,
        "decision": "cleared_for_external_project_role_execution",
        "scope": "external_project_using_project_local_redcap",
        "project": str(project),
        "direction_sha256": sha256_text(direction),
        "reason": (
            "本角色是在外部项目中使用已安装的 .redcap 运行时交付项目产物，"
            "不是修改 RedCap 源仓库本体。角色不得自行运行完整棱镜或 RedCap 源开发门禁；"
            "E2E 运行器负责安装包棱镜自检、最终棱镜复核、证据打包和 completion-marker 裁决。"
        ),
        "role_must_not_run_commands": [
            "runtime/bin/redcap gate",
            ".redcap/runtime/bin/redcap gate",
            "prism-dispatch",
            "prism session-init",
            "prism merge",
        ],
        "role_must_read": required_reads,
        "role_must_read_resolved": role_path_records(project, evidence, required_reads, for_output=False),
        "role_must_write": outputs,
        "role_must_write_resolved": role_path_records(project, evidence, outputs, for_output=True),
        "runner_owned_checks": [
            "package-prism-check.json",
            "final-runner-test-results.json",
            "final-evidence-bundle.json",
            "final-prism-review.json",
            "completion-marker.json",
        ],
        "escalation_path": (
            "如果本角色发现必须由棱镜协助的问题，写入 role-artifacts/<role>.json 的 prism_assistance_request，"
            "不要自行调用 provider 或阻塞为 gate_required。"
        ),
    }


def write_role_gate_clearance(evidence: pathlib.Path, project: pathlib.Path, role: str, direction: str) -> dict[str, Any]:
    payload = build_role_gate_clearance(project, evidence, role, direction)
    write_json(role_gate_clearance_path(evidence, role), payload)
    return payload


def write_role_gate_clearance_summary(evidence: pathlib.Path, clearances: dict[str, dict[str, Any]]) -> None:
    write_json(evidence / "role-gate-clearance-summary.json", {
        "schema_id": "redcap-e2e-role-gate-clearance-summary",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "roles": [
            {
                "role": role,
                "decision": payload.get("decision"),
                "path": f"role-gate-clearance/{role}.json",
            }
            for role, payload in sorted(clearances.items())
        ],
        "runner_owns_full_prism": True,
        "role_gate_self_block_forbidden": True,
    })


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
            "role-artifacts/reviewer.json",
        ],
    )


def build_role_prompt(project: pathlib.Path, evidence: pathlib.Path, role: str, direction: str) -> str:
    inputs, outputs = role_handoff(role)
    required_inputs = unique_preserve_order(["requirements.json", "acceptance-criteria.json", *inputs])
    input_records = role_path_records(project, evidence, required_inputs, for_output=False)
    output_records = role_path_records(project, evidence, outputs, for_output=True)
    common = f"""
    {ROLE_MARKER_PREFIX}{role}

    你是 RedCap E2E 的 Loom 角色：{role}。
    你必须作为独立 Codex CLI 调用工作，本角色不能冒充其他角色。

    项目根目录：{project}
    证据目录：{evidence}
    角色工作目录：{role_workspace_path(evidence, role)}
    角色门禁协调文件：{role_gate_clearance_path(evidence, role)}
    需求方向：{direction}

    上游输入：
    {json.dumps(required_inputs, ensure_ascii=False)}

    上游输入实际路径：
    {json.dumps(input_records, ensure_ascii=False, indent=2)}

    本角色必须产出：
    {json.dumps(outputs, ensure_ascii=False)}

    本角色必须产出的实际路径：
    {json.dumps(output_records, ensure_ascii=False, indent=2)}

    通用要求：
    - 只修改外部项目，不要修改 RedCap 源仓库。
    - 本角色的结构化证据必须写入 {role_artifact_path(evidence, role)}。
    - role artifact 至少包含 schema_id、role、status、handoff_inputs、handoff_outputs、evidence_files、notes。
    - 必须先读取角色门禁协调文件，并把它作为本角色的门禁依据。
    - 判断上游输入是否缺失时，必须以“上游输入实际路径”和角色门禁协调文件里的 role_must_read_resolved 为准；不要只在项目根目录按裸文件名查找。
    - 写结构化产物时，必须优先写入“本角色必须产出的实际路径”和角色门禁协调文件里的 role_must_write_resolved。
    - 本角色是在外部项目中使用 .redcap，不是在修改 RedCap 源仓库；不要运行 runtime/bin/redcap gate 或 .redcap/runtime/bin/redcap gate。
    - 如果缺少上游输入，请写 blocked-package.json 并说明阻塞，不要伪造完成。
    - 如果项目根目录已经存在 blocked-package.json，必须先读取它；除非你就是正在生成该阻塞的角色，否则要产出本角色的阻塞证据并快速停止。
    - 本角色不得运行 prism-dispatch、prism session-init、prism merge 或完整 provider 评审；需要棱镜协助时，把请求和理由写入 role-artifacts/<role>.json，由 E2E 运行器统一调度。
    - 本角色不得写 .redcap/evidence/e2e/prism/<role>/ 或 .redcap/evidence/e2e/prism/<role>_completion/ 目录；这些目录会被视为角色越权。
    - 本角色只允许读取上游输入、角色门禁协调文件和必要模板；不要读取 manifest.json、Hook 事件、role-workspaces、redcap-package.zip 或 RedCap 源码。
    - 先写本角色必需产物，再做少量核对；不要为了“更全面”而扩展探索范围。
    - 如果 Stop 或 Gate 只给出建议，不要把建议当作新任务；本角色主轴始终是上面列出的产物。
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
        2. 立即写 architecture.md，必须包含：目标、目录结构、数据模型、交互流程、运行方式、验证方式、风险与回滚。
        3. 默认选择无外部依赖、无需联网安装、可直接本地验证的方案；除非需求明确要求，不要引入 Vite、Playwright、数据库或服务端框架。
        4. 立即写 risk-register.json，至少包含 risks 数组；每项包含 id、risk、impact、mitigation、owner。
        5. 立即写 role-artifacts/architect.json，status="completed"，并列出读取的输入和写出的文件。
        6. 不要读取 manifest.json，不要检查 role-workspaces，不要扫描 .redcap 全目录。
        """,
        "developer": """
        你的任务：
        1. 按 architecture.md 实现一个可运行的本地项目。
        2. 优先选择简单、无外部依赖、无需联网安装、可本地验证的技术栈；如果 architecture.md 要求重型依赖但需求并不需要，你应收窄为纯 HTML/CSS/JS + Node 内置模块验证，并在 implementation-log.json 说明原因。
        3. 写 implementation-log.json 和 role-artifacts/developer.json。
        4. 如果提供验证脚本，机器验证输出必须写 verification-results.json 或其他非角色文件，不能写或覆盖 test-results.json；test-results.json 只属于 tester 角色。
        """,
        "tester": """
        你的任务：
        1. 如果项目根目录存在 blocked-package.json，立即读取它，写 test-results.json、negative-probes.json 和 role-artifacts/tester.json，标记 status="blocked_by_upstream"，passed=false，然后停止；不要等待、不要修复。
        2. 如果没有上游阻塞，先写进行中证据，再运行任何验证：
           - test-results.json：role="tester"，status="in_progress"，passed=false，commands=[]，positive_checks=[]；
           - negative-probes.json：role="tester"，status="in_progress"，passed=false，probes=[]；
           - role-artifacts/tester.json：role="tester"，status="in_progress"，evidence_files 列出上述两个文件。
        3. 只做两类验证：最多一个正向验证命令，最多一个负向或静态探针。优先使用 README、package.json scripts、scripts/validate.mjs、scripts/verify.mjs 或 scripts/verify.sh 中明确给出的本地验证命令；不要为了“更全面”继续追加探索。
           负向或静态探针必须使用 Node 标准库脚本或已经写好的验证脚本；不要用未引用的 shell 通配符、find -name *.xxx、zsh glob 或会被 shell 预展开的命令。
        4. 每执行完一个验证动作，立即更新对应 JSON；验证动作全部结束后，立即把三个文件更新为 completed 或 failed。
        5. test-results.json 必须标记 role="tester"，并记录 commands、positive_checks、passed；negative-probes.json 必须标记 role="tester"，并记录 probes、passed。status 与 passed 必须一致：completed 对应 passed=true，failed 对应 passed=false。
        6. 如果测试失败，必须把失败写清楚，不要替开发者修复。
        """,
        "reviewer": """
        你的任务：
        1. 审阅需求、架构、实现、测试和角色证据。
           注意：loom-role-session-manifest-pre-review.json 只用于审核上游四个角色；reviewer 自己的 session_id 会在你退出后由运行器写入最终 loom-role-session-manifest.json，因此不要因为最终清单在评审前缺少 reviewer 自身而阻塞。
        2. 写 review-verdict.json；必须包含：
           - "terminal_completion": false；
           - "blocking_findings": [] 或阻塞项数组，禁止用 blocking_failures、open_issues 等近义字段替代；
           - "runner_owned_follow_up": ["completion-marker.json", "iteration-verdict.json", "final-prism-review.json", "final-runner-test-results.json"]，必须是这四个精确文件名字符串，不要写成说明句。
           同时在边界说明中写明 terminal_completion=false 表示 reviewer 只能给阶段评审，不能自证本轮 E2E 终局完成或 RedCap 完整复活。
        3. 写 prism-assisted-review.json；本轮必须记录 used=true，reviews 必须是非空数组，cap_decision 必须非空，skip_reason 必须为 null 或空字符串。至少在 reviews[0] 中说明一次对需求、架构、代码、测试或文档的棱镜协助或包内棱镜检查如何影响裁决，并必须包含 prism_assistance_request.requested=true。
        4. 写 self-purification-candidates.json，包含候选或 no_candidate_reason，并给出 decisions 数组。decision 只允许 promote_public、keep_private、no_promote、defer_with_owner；每个 decision 必须包含 reason；需要后续沉淀但本轮不晋升时用 defer_with_owner。
        5. 写 persona-distillation-decision.json；privacy_class 必须是 cap-private，public_write=false，private_body_written=false，reason 必须是非空字符串，推荐写“本轮没有可晋升的人格信号”。禁止写身份私密材料正文，也禁止出现 private_body、cap_private_body、persona_private_body、private_text 等私有正文键；reason 不要复述禁止项本身，不要用 rationale 替代 reason。
        6. 写 failure-backlog.json。必须使用 open_items 数组作为唯一开放问题字段；没有开放问题时 open_items=[] 且 next_round_required=false。禁止只写 open_issues。若有开放问题，每项必须包含 id、severity、summary、root_cause、impact、suggested_fix、owner、next_step。
           open_items 只记录你从需求、架构、实现、测试、上游角色证据中发现的真实阻塞问题。
           completion-marker.json、iteration-verdict.json、final-prism-review.json、final-runner-test-results.json 属于运行器固定收尾动作；若上游证据通过，请写入 review-verdict.runner_owned_follow_up，不要写入 open_items。
        7. 禁止写 completion-marker.json 或 iteration-verdict.json；这两个文件只能由 E2E 运行器在你退出后独立生成。
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
    kimi_state = pathlib.Path.home() / ".kimi-code"
    if not kimi_state.exists():
        return []
    return [kimi_state]


def role_provider_boundary_failures(evidence: pathlib.Path, role: str) -> list[str]:
    failures: list[str] = []
    prism_root = evidence / "prism"
    for forbidden in [prism_root / role, prism_root / f"{role}_completion"]:
        if forbidden.exists():
            failures.append(f"{role} 角色越权运行完整棱镜评审：{forbidden.relative_to(evidence).as_posix()}")
    artifact = load_optional_json(role_artifact_path(evidence, role))
    if artifact is not None:
        files = artifact.get("evidence_files")
        if isinstance(files, list):
            leaked = [str(item) for item in files if f"prism/{role}" in str(item)]
            if leaked:
                failures.append(f"{role} 角色证据声明了越权棱镜产物：{leaked}")
    return failures


def role_output_path(project: pathlib.Path, evidence: pathlib.Path, output: str) -> pathlib.Path | None:
    return role_logical_path(project, evidence, output, for_output=True)


def validate_reviewer_outputs(evidence: pathlib.Path) -> list[str]:
    failures: list[str] = []
    backlog = load_optional_json(evidence / "failure-backlog.json")
    if backlog is None:
        failures.append("reviewer 必须写入可解析的 failure-backlog.json")
    else:
        open_items = backlog.get("open_items")
        if not isinstance(open_items, list):
            failures.append("reviewer 的 failure-backlog.open_items 必须是列表，不能用 open_issues 替代")
        closed_items = backlog.get("closed_items")
        if closed_items is not None and not isinstance(closed_items, list):
            failures.append("reviewer 的 failure-backlog.closed_items 必须是列表")
        if open_items == [] and backlog.get("next_round_required") is True:
            failures.append("reviewer 的 failure-backlog 无开放项时 next_round_required 必须为 false")
        for item in open_items or []:
            if not isinstance(item, dict):
                failures.append("reviewer 的 failure-backlog.open_items 每项必须是对象")
                continue
            for field in ["id", "severity", "summary", "root_cause", "impact", "suggested_fix", "owner", "next_step"]:
                if not isinstance(item.get(field), str) or not item[field].strip():
                    failures.append(f"reviewer 的 failure-backlog.open_items 缺少字段：{field}")

    assisted = load_optional_json(evidence / "prism-assisted-review.json")
    if assisted is None:
        failures.append("reviewer 必须写入可解析的 prism-assisted-review.json")
    else:
        request = assisted.get("prism_assistance_request")
        if not isinstance(request, dict) or request.get("requested") is not True:
            failures.append("reviewer 必须在 prism-assisted-review.json 记录运行器统一调度棱镜的请求")
        if assisted.get("used") is not True:
            failures.append("reviewer 必须把棱镜边界或包内棱镜要求如何影响裁决记录为 used=true")
        reviews = assisted.get("reviews")
        if not isinstance(reviews, list) or not reviews:
            failures.append("reviewer 的 prism-assisted-review.reviews 必须是非空数组")
        if not assisted.get("cap_decision"):
            failures.append("reviewer 的 prism-assisted-review.cap_decision 必须非空")
        if assisted.get("used") is True and assisted.get("skip_reason") not in (None, ""):
            failures.append("reviewer 的 prism-assisted-review.used=true 时 skip_reason 必须为空")

    purification = load_optional_json(evidence / "self-purification-candidates.json")
    if purification is None:
        failures.append("reviewer 必须写入可解析的 self-purification-candidates.json")
    else:
        decisions = purification.get("decisions")
        if not isinstance(decisions, list):
            failures.append("self-purification-candidates.decisions 必须是列表")
        elif not decisions and not isinstance(purification.get("no_candidate_reason"), str):
            failures.append("无自我沉淀候选时必须写 no_candidate_reason")
        allowed = {"promote_public", "keep_private", "no_promote", "defer_with_owner"}
        for decision in decisions or []:
            if not isinstance(decision, dict) or decision.get("decision") not in allowed:
                failures.append("self-purification-candidates.decisions 存在非法 decision")
                continue
            if not isinstance(decision.get("reason"), str) or not decision["reason"].strip():
                failures.append("self-purification-candidates.decisions 每项必须写明 reason")

    persona = load_optional_json(evidence / "persona-distillation-decision.json")
    if persona is None:
        failures.append("reviewer 必须写入可解析的 persona-distillation-decision.json")
    else:
        if persona.get("privacy_class") != "cap-private":
            failures.append("persona-distillation-decision.privacy_class 必须是 cap-private")
        if persona.get("public_write") is not False:
            failures.append("persona-distillation-decision.public_write 必须为 false")
        if persona.get("private_body_written") is not False:
            failures.append("persona-distillation-decision.private_body_written 必须为 false")
        if not isinstance(persona.get("reason"), str) or not persona["reason"].strip():
            failures.append("persona-distillation-decision.reason 必须非空，不能只写 rationale")
        leaked = sorted({"private_body", "cap_private_body", "persona_private_body", "private_text"} & set(persona))
        if leaked:
            failures.append(f"persona-distillation-decision 禁止包含私有正文键：{leaked}")
        persona_text = json.dumps(persona, ensure_ascii=False).casefold()
        leaked_markers = [marker for marker in PRIVATE_PERSONA_MARKERS if marker.casefold() in persona_text]
        if leaked_markers:
            failures.append(f"persona-distillation-decision 禁止包含身份私密材料标记：{leaked_markers}")

    verdict = load_optional_json(evidence / "review-verdict.json")
    if verdict is None:
        failures.append("reviewer 必须写入可解析的 review-verdict.json")
    else:
        if verdict.get("terminal_completion") is not False:
            failures.append("reviewer 不得自证终局完成，review-verdict.terminal_completion 必须为 false")
        if not isinstance(verdict.get("blocking_findings"), list):
            failures.append("review-verdict.blocking_findings 必须是列表")
        if "blocking_failures" in verdict:
            failures.append("review-verdict 禁止用 blocking_failures 替代 blocking_findings")
        runner_follow_up = verdict.get("runner_owned_follow_up")
        if not isinstance(runner_follow_up, list):
            failures.append("review-verdict.runner_owned_follow_up 必须是列表")
        else:
            actual = {str(item) for item in runner_follow_up}
            missing = sorted(set(REVIEWER_RUNNER_OWNED_FOLLOW_UP) - actual)
            if missing:
                failures.append(f"review-verdict.runner_owned_follow_up 缺少运行器固定收尾动作：{missing}")
            extra = sorted(actual - set(REVIEWER_RUNNER_OWNED_FOLLOW_UP))
            if extra:
                failures.append(f"review-verdict.runner_owned_follow_up 只能写精确文件名，不能写说明句：{extra}")
    return failures


def validate_role_outputs(project: pathlib.Path, evidence: pathlib.Path, role: str) -> list[str]:
    failures: list[str] = []
    _inputs, outputs = role_handoff(role)
    for output in outputs:
        path = role_output_path(project, evidence, output)
        if path is not None and not path.exists():
            failures.append(f"{role} 缺少必需产物：{output}")
    artifact = load_optional_json(role_artifact_path(evidence, role))
    if artifact is None:
        failures.append(f"{role} 缺少可解析的 role-artifacts/{role}.json")
    else:
        for field in ["schema_id", "role", "status", "handoff_inputs", "handoff_outputs", "evidence_files", "notes"]:
            if field not in artifact:
                failures.append(f"role-artifacts/{role}.json 缺少字段：{field}")
        if artifact.get("role") != role:
            failures.append(f"role-artifacts/{role}.json.role 必须是 {role}")
    if role == "reviewer":
        failures.extend(validate_reviewer_outputs(evidence))
    return failures


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
        recorded_session_id = str(role_results.get(role, {}).get("session_id") or "")
        attempt_count = int(role_results.get(role, {}).get("attempt_count") or 0)
        selected_session_id: str | None = None
        if command_ok and recorded_session_id and recorded_session_id in unique_sessions:
            selected_session_id = recorded_session_id
        elif len(unique_sessions) == 1:
            selected_session_id = unique_sessions[0]
        retry_sessions_allowed = (
            command_ok
            and attempt_count > 1
            and selected_session_id in unique_sessions
        )
        artifact_rel = f"role-artifacts/{role}.json"
        inputs, outputs = role_handoff(role)
        alarm: str | None = None
        role_has_started = role in role_results or bool(entries)
        if include_pending and not role_has_started:
            alarm = None
        elif not selected_session_id:
            alarm = "missing_session_id"
        elif len(unique_sessions) > 1 and not retry_sessions_allowed:
            alarm = "multiple_sessions_for_single_role"
        elif not command_ok:
            alarm = "role_command_failed"
        if alarm:
            alarms.append({"role": role, "alarm": alarm})
        roles.append({
            "role": role,
            "session_id": selected_session_id,
            "observed_session_ids": unique_sessions,
            "retry_session_ids": [item for item in unique_sessions if item != selected_session_id],
            "attempt_count": role_results.get(role, {}).get("attempt_count"),
            "provider": "codex-cli",
            "started_at": entries[0].get("recorded_at") if entries else None,
            "last_seen_at": entries[-1].get("recorded_at") if entries else None,
            "context_state": "pending" if include_pending and not role_has_started else ("complete" if alarm is None else "degraded"),
            "alarm": alarm,
            "role_workspace": [f"role-workspaces/{role}"],
            "handoff_inputs": inputs,
            "handoff_input_paths": role_path_records(project, evidence, inputs, for_output=False),
            "handoff_outputs": outputs,
            "handoff_output_paths": role_path_records(project, evidence, outputs, for_output=True),
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
    role_clearances: dict[str, dict[str, Any]] = {}
    for dirname in ["role-prompts", "role-messages", "role-runs", "role-workspaces", "role-artifacts", "role-raw"]:
        (evidence / dirname).mkdir(parents=True, exist_ok=True)
    for role in LOOM_EXECUTION_ROLES:
        role_workspace_path(evidence, role).mkdir(parents=True, exist_ok=True)
        role_clearances[role] = write_role_gate_clearance(evidence, project, role, direction)
        prompt = build_role_prompt(project, evidence, role, direction)
        prompt_path = evidence / "role-prompts" / f"{role}.md"
        message_path = evidence / "role-messages" / f"{role}.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        role_timeout = min(timeout_seconds, ROLE_TIMEOUT_SECONDS[role])
        base_argv = [
            "codex",
            "exec",
            "--model",
            CODEX_ROLE_MODEL,
            "-c",
            f'model_reasoning_effort="{CODEX_ROLE_REASONING_EFFORT}"',
            "--cd",
            str(project),
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--full-auto",
        ]
        if CODEX_ROLE_DISABLE_PLUGINS:
            base_argv.extend(["--disable", "plugins"])
        for state_dir in provider_state_dirs_for_role(role):
            base_argv.extend(["--add-dir", str(state_dir)])
        base_argv.extend([
            "--output-last-message",
            str(message_path),
            prompt,
        ])
        attempts: list[dict[str, Any]] = []
        result: dict[str, Any] = {}
        for attempt_index in range(1, max(1, CODEX_ROLE_MAX_ATTEMPTS) + 1):
            if message_path.exists():
                message_path.unlink()
            result = run_command(base_argv, cwd=project, timeout_seconds=role_timeout)
            attempt_stdout = evidence / "role-raw" / f"{role}.attempt-{attempt_index}.stdout.txt"
            attempt_stderr = evidence / "role-raw" / f"{role}.attempt-{attempt_index}.stderr.txt"
            attempt_stdout.write_text(str(result.get("stdout") or ""), encoding="utf-8")
            attempt_stderr.write_text(str(result.get("stderr") or ""), encoding="utf-8")
            attempt_receipt = command_receipt(result)
            attempt_receipt.update({
                "attempt": attempt_index,
                "session_id": extract_codex_session_id(str(result.get("stderr") or "")),
                "raw_stdout": str(attempt_stdout),
                "raw_stderr": str(attempt_stderr),
                "expected_artifact_exists": role_artifact_path(evidence, role).exists(),
                "last_message_exists": message_path.exists(),
            })
            attempts.append(attempt_receipt)
            retry_reason = role_failure_retry_reason(result, role_artifact_path(evidence, role).exists())
            if retry_reason and attempt_index < max(1, CODEX_ROLE_MAX_ATTEMPTS):
                append_jsonl(evidence / "workflow-events.jsonl", {
                    "event": "loom_role_retry_scheduled",
                    "role": role,
                    "attempt": attempt_index,
                    "recorded_at": iso_now(),
                    "reason": retry_reason,
                })
                continue
            break
        raw_stdout = evidence / "role-raw" / f"{role}.stdout.txt"
        raw_stderr = evidence / "role-raw" / f"{role}.stderr.txt"
        raw_stdout.write_text(str(result.get("stdout") or ""), encoding="utf-8")
        raw_stderr.write_text(str(result.get("stderr") or ""), encoding="utf-8")
        receipt = command_receipt(result)
        boundary_failures = role_provider_boundary_failures(evidence, role)
        receipt.update({
            "schema_id": "redcap-e2e-loom-role-run",
            "role": role,
            "codex_model": CODEX_ROLE_MODEL,
            "codex_reasoning_effort": CODEX_ROLE_REASONING_EFFORT,
            "codex_plugins_disabled": CODEX_ROLE_DISABLE_PLUGINS,
            "attempt_count": len(attempts),
            "max_attempts": max(1, CODEX_ROLE_MAX_ATTEMPTS),
            "attempts": attempts,
            "session_id": extract_codex_session_id(str(result.get("stderr") or "")),
            "prompt_path": str(prompt_path),
            "last_message": str(message_path),
            "expected_artifact": str(role_artifact_path(evidence, role)),
            "expected_artifact_exists": role_artifact_path(evidence, role).exists(),
            "last_message_exists": message_path.exists(),
            "last_message_size": message_path.stat().st_size if message_path.exists() else 0,
            "raw_stdout": str(raw_stdout),
            "raw_stderr": str(raw_stderr),
            "project_deliverables_after_role": project_deliverable_manifest(project, limit=60),
            "role_provider_boundary_failures": boundary_failures,
        })
        artifact_failures = validate_role_outputs(project, evidence, role)
        if artifact_failures:
            receipt["ok"] = False
            receipt["failures"] = [*receipt.get("failures", []), *artifact_failures]
        if boundary_failures:
            receipt["ok"] = False
            receipt["failures"] = [*receipt.get("failures", []), *boundary_failures]
        write_json(evidence / "role-runs" / f"{role}.json", receipt)
        role_results[role] = receipt
        append_jsonl(evidence / "workflow-events.jsonl", {
            "event": "loom_role_completed",
            "role": role,
            "recorded_at": iso_now(),
            "ok": receipt["ok"],
        })
        if not receipt["ok"]:
            break
        if role == "tester":
            pre_review_manifest = build_role_session_manifest(project, evidence, role_results, include_pending=True)
            write_json(evidence / "loom-role-session-manifest-pre-review.json", pre_review_manifest)
    write_role_gate_clearance_summary(evidence, role_clearances)
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
    write_external_project_agents(project)
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
                "handoff_input_paths": role_path_records(project, evidence, role_handoff(role)[0], for_output=False),
                "handoff_outputs": role_handoff(role)[1],
                "handoff_output_paths": role_path_records(project, evidence, role_handoff(role)[1], for_output=True),
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
                "handoff_input_paths": role_path_records(project, evidence, role_handoff(role)[0], for_output=False),
                "handoff_outputs": role_handoff(role)[1],
                "handoff_output_paths": role_path_records(project, evidence, role_handoff(role)[1], for_output=True),
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
    write_json(evidence / "role-gate-clearance-template.json", {
        "schema_id": "redcap-e2e-role-gate-clearance",
        "producer": "e2e-runner",
        "decision": "cleared_for_external_project_role_execution",
        "scope": "external_project_using_project_local_redcap",
        "role_must_not_run_commands": [
            "runtime/bin/redcap gate",
            ".redcap/runtime/bin/redcap gate",
            "prism-dispatch",
            "prism session-init",
            "prism merge",
        ],
        "role_must_read": [],
        "role_must_read_resolved": [],
        "role_must_write": [],
        "role_must_write_resolved": [],
        "runner_owned_checks": [
            "package-prism-check.json",
            "final-runner-test-results.json",
            "final-evidence-bundle.json",
            "final-prism-review.json",
            "completion-marker.json",
        ],
    })
    write_json(evidence / "role-gate-clearance-summary-template.json", {
        "schema_id": "redcap-e2e-role-gate-clearance-summary",
        "producer": "e2e-runner",
        "roles": [],
        "runner_owns_full_prism": True,
        "role_gate_self_block_forbidden": True,
    })
    write_json(evidence / "prism-assisted-review-template.json", {
        "schema_id": "redcap-e2e-prism-assisted-review",
        "used": True,
        "reviews": [
            {
                "scope": "<requirements|architecture|implementation|tests|documents|runner-prism-boundary>",
                "finding": "<required>",
                "effect_on_verdict": "<required>"
            }
        ],
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
        "reason": "<required; do not add private_body, cap_private_body, persona_private_body, or private_text keys>"
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
    write_json(evidence / "final-runner-test-results-template.json", {
        "schema_id": "redcap-e2e-final-runner-test-results",
        "producer": "e2e-runner",
        "detected_command": "<required>",
        "ok": "<boolean>",
        "failure_policy": "blocking"
    })
    write_json(evidence / "browser-inspection-template.json", {
        "schema_id": "redcap-e2e-browser-inspection",
        "producer": "e2e-runner",
        "target": "index.html",
        "screenshot": "browser-inspection.png",
        "ok": "<boolean>",
        "failure_policy": "blocking"
    })
    write_json(evidence / "final-evidence-bundle-template.json", {
        "schema_id": "redcap-e2e-final-evidence-bundle",
        "producer": "e2e-runner",
        "files": [],
        "hash_required": True,
        "purpose": "供最终棱镜复核独立检查，不依赖 reviewer 自证"
    })
    write_json(evidence / "final-prism-review-template.json", {
        "schema_id": "redcap-e2e-final-prism-review",
        "producer": "e2e-runner",
        "providers_required": ["kimi", "claude-code"],
        "strictest_verdict": "<pass|concern|block>",
        "ok": "<boolean>",
        "failure_policy": "blocking"
    })
    write_json(evidence / "failure-backlog-template.json", {
        "schema_id": "redcap-e2e-failure-backlog",
        "reviewer_scope": "open_items 只写 reviewer 从上游证据中发现的真实阻塞；运行器固定收尾动作写入 review-verdict.runner_owned_follow_up",
        "open_items": [],
        "closed_items": [],
        "next_round_required": False
    })
    write_json(evidence / "iteration-verdict-template.json", {
        "schema_id": "redcap-e2e-iteration-verdict",
        "producer": "e2e-runner",
        "ready_for_engineering_use": False,
        "status": "pass|fail|blocked",
        "remaining_issues": [],
        "evidence_checked": sorted(REQUIRED_EVIDENCE_CHECKS)
    })
    write_json(evidence / "completion-marker-template.json", {
        "schema_id": "redcap-e2e-completion-marker",
        "producer": "e2e-runner",
        "ready_for_engineering_use": True,
        "requires_final_prism_pass": True,
        "requires_no_open_failure_backlog": True
    })
    (evidence / "implementer-prompt.md").write_text(prompt, encoding="utf-8")
    write_json(evidence / "review-verdict-template.json", {
        "schema_id": "redcap-e2e-review-verdict",
        "status": "pending",
        "terminal_completion": False,
        "boundary": "reviewer 只能给阶段评审；terminal_completion=false 表示不能自证本轮 E2E 终局完成或 RedCap 完整复活",
        "runner_owned_follow_up": REVIEWER_RUNNER_OWNED_FOLLOW_UP,
        "blocking_findings": [],
        "forbidden_aliases": ["blocking_failures", "open_issues"],
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


def read_text_excerpt(path: pathlib.Path, max_chars: int = 3000) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"readable": False, "error": str(exc)}
    if len(text) <= max_chars:
        return {"readable": True, "truncated": False, "text": text}
    half = max_chars // 2
    return {
        "readable": True,
        "truncated": True,
        "head": text[:half],
        "tail": text[-half:],
        "length": len(text),
    }


def project_deliverable_manifest(project: pathlib.Path, limit: int = 80) -> dict[str, Any]:
    files = [
        item
        for item in filesystem_manifest(project)
        if not item["path"].startswith(".redcap/") and not item["path"].startswith(".codex/")
    ]
    return {
        "count": len(files),
        "truncated": len(files) > limit,
        "files": files[:limit],
    }


def write_external_project_agents(project: pathlib.Path) -> None:
    project.joinpath("AGENTS.md").write_text(textwrap.dedent("""
    # RedCap E2E 外部项目说明

    本目录是 RedCap E2E（端到端验收）临时外部项目，不是 RedCap 源仓库。

    Loom（角色化工程工作流）角色在这里的职责是使用项目级 `.redcap/` 运行时完成项目交付物。
    角色不得把本项目误判为 RedCap 框架本体开发，也不得自行运行 RedCap 源开发门禁。

    每个角色必须读取自己的门禁协调凭证。该文件由 E2E 运行器生成，是本角色的门禁依据。

    角色不得运行以下命令：
    - `runtime/bin/redcap gate`
    - `.redcap/runtime/bin/redcap gate`
    - `prism-dispatch`
    - `prism session-init`
    - `prism merge`

    如果角色需要棱镜（异构 AI 评审助手）协助，只能把请求写入自己的角色证据，
    由 E2E 运行器统一调度。
    """).strip() + "\n", encoding="utf-8")


def final_evidence_paths(project: pathlib.Path, evidence: pathlib.Path) -> list[pathlib.Path]:
    fixed = [
        "requirements.json",
        "acceptance-criteria.json",
        "architecture.md",
        "risk-register.json",
        "role-gate-clearance-summary.json",
        "implementation-log.json",
        "review-verdict.json",
        "prism-assisted-review.json",
        "knowledge-retrieval-evidence.json",
        "self-purification-candidates.json",
        "persona-distillation-decision.json",
        "test-results.json",
        "negative-probes.json",
        "package-prism-check.json",
        "final-runner-test-results.json",
        "browser-inspection.json",
        "role-execution-risk.json",
        "final-prism-review.json",
        "failure-backlog.json",
        "iteration-verdict.json",
        "loom-role-session-manifest-pre-review.json",
        "loom-role-session-manifest.json",
        "hook-events-summary.json",
        "codex-run.json",
        "filesystem-after.json",
    ]
    project_root_files = {"architecture.md", "risk-register.json"}
    paths = [(project / rel) if rel in project_root_files else (evidence / rel) for rel in fixed]
    for pattern in ["role-gate-clearance/*.json", "role-artifacts/*.json", "role-runs/*.json", "role-messages/*.txt", "role-raw/*.txt"]:
        paths.extend(sorted(evidence.glob(pattern)))
    seen: set[pathlib.Path] = set()
    unique: list[pathlib.Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            unique.append(path)
            seen.add(resolved)
    return unique


def build_final_evidence_bundle(project: pathlib.Path, evidence: pathlib.Path, direction: str) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in final_evidence_paths(project, evidence):
        try:
            rel = path.relative_to(evidence).as_posix()
        except ValueError:
            rel = path.relative_to(project).as_posix()
        record: dict[str, Any] = {
            "path": rel,
            "exists": path.exists(),
        }
        if path.exists() and path.is_file():
            record.update({
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
                "excerpt": read_text_excerpt(path),
            })
        files.append(record)
    bundle = {
        "schema_id": "redcap-e2e-final-evidence-bundle",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "project": str(project),
        "direction_sha256": sha256_text(direction),
        "purpose": "供最终棱镜复核独立检查，避免 reviewer 自证完成",
        "deliverables": project_deliverable_manifest(project),
        "files": files,
    }
    bundle["bundle_sha256"] = sha256_text(json.dumps(bundle, ensure_ascii=False, sort_keys=True))
    return bundle


def detect_validation_command(project: pathlib.Path) -> tuple[list[str] | None, str]:
    package_json = load_optional_json(project / "package.json")
    scripts = package_json.get("scripts") if isinstance(package_json, dict) else None
    if isinstance(scripts, dict) and isinstance(scripts.get("test"), str) and scripts["test"].strip():
        return ["npm", "test"], "package.json scripts.test"
    if isinstance(scripts, dict) and isinstance(scripts.get("validate"), str) and scripts["validate"].strip():
        return ["npm", "run", "validate"], "package.json scripts.validate"
    script_candidates = [
        ("scripts/validate.js", ["node", "scripts/validate.js"]),
        ("scripts/validate.mjs", ["node", "scripts/validate.mjs"]),
        ("scripts/verify.mjs", ["node", "scripts/verify.mjs"]),
        ("scripts/verify.js", ["node", "scripts/verify.js"]),
        ("scripts/verify.sh", ["bash", "scripts/verify.sh"]),
        ("tests/validate.mjs", ["node", "tests/validate.mjs"]),
        ("tests/verify.mjs", ["node", "tests/verify.mjs"]),
    ]
    for relative_path, argv in script_candidates:
        if (project / relative_path).exists():
            return argv, relative_path
    known_sources = ", ".join(["package.json scripts.test", "package.json scripts.validate", *[item[0] for item in script_candidates]])
    return None, f"没有发现可执行验证命令：{known_sources}"


def run_final_runner_tests(project: pathlib.Path) -> dict[str, Any]:
    argv, source = detect_validation_command(project)
    if argv is None:
        return {
            "schema_id": "redcap-e2e-final-runner-test-results",
            "producer": "e2e-runner",
            "ok": False,
            "detected_command": None,
            "command_source": source,
            "failures": ["运行器无法发现可执行验证命令"],
        }
    result = run_command(argv, cwd=project, timeout_seconds=240)
    receipt = command_receipt(result)
    receipt.update({
        "schema_id": "redcap-e2e-final-runner-test-results",
        "producer": "e2e-runner",
        "detected_command": argv,
        "command_source": source,
        "failures": [] if result["ok"] else ["运行器重跑验证命令失败"],
    })
    return receipt


def run_browser_inspection(project: pathlib.Path, evidence: pathlib.Path) -> dict[str, Any]:
    target = project / "index.html"
    screenshot = evidence / "browser-inspection.png"
    result: dict[str, Any] = {
        "schema_id": "redcap-e2e-browser-inspection",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "target": str(target),
        "url": target.as_uri() if target.exists() else None,
        "screenshot": "browser-inspection.png",
        "ok": False,
        "checks": [],
        "failures": [],
    }
    if not target.exists():
        result["failures"].append("缺少 index.html，无法执行浏览器检查")
        return result
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - 取决于本机运行时
        result["failures"].append(f"无法导入 Playwright 浏览器自动化库：{type(exc).__name__}: {exc}")
        return result
    console_errors: list[str] = []
    page_errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(target.as_uri(), wait_until="domcontentloaded", timeout=20_000)
            page.wait_for_timeout(500)
            title = page.title()
            body_text = page.locator("body").inner_text(timeout=5_000)
            interactive_count = page.locator("button, input, select, textarea, a[href]").count()
            element_count = page.locator("body *").count()
            page.screenshot(path=str(screenshot), full_page=True)
            browser.close()
    except Exception as exc:
        result["failures"].append(f"浏览器检查执行失败：{type(exc).__name__}: {exc}")
        return result
    visible_text = body_text.strip()
    checks = [
        {"name": "page_loaded", "passed": True, "evidence": target.as_uri()},
        {"name": "visible_text", "passed": len(visible_text) >= 80, "evidence": f"visible_text_length={len(visible_text)}"},
        {
            "name": "interactive_or_semantic_elements",
            "passed": interactive_count > 0 or element_count >= 10,
            "evidence": f"interactive_count={interactive_count}, element_count={element_count}",
        },
        {
            "name": "no_browser_errors",
            "passed": not console_errors and not page_errors,
            "evidence": {"console_errors": console_errors, "page_errors": page_errors},
        },
        {
            "name": "screenshot_written",
            "passed": screenshot.exists() and screenshot.stat().st_size > 0,
            "evidence": {
                "path": "browser-inspection.png",
                "sha256": sha256_file(screenshot) if screenshot.exists() else None,
                "size": screenshot.stat().st_size if screenshot.exists() else 0,
            },
        },
    ]
    failures = [f"浏览器检查失败：{item['name']}" for item in checks if item.get("passed") is not True]
    result.update({
        "ok": not failures,
        "title": title,
        "visible_text_length": len(visible_text),
        "visible_text_sample": visible_text[:1000],
        "interactive_count": interactive_count,
        "element_count": element_count,
        "console_errors": console_errors,
        "page_errors": page_errors,
        "checks": checks,
        "failures": failures,
    })
    return result


def backlog_open_items(evidence: pathlib.Path) -> list[Any]:
    backlog = load_optional_json(evidence / "failure-backlog.json")
    if backlog is None:
        return [{"id": "RUNNER-FINAL-MISSING-BACKLOG", "summary": "缺少 failure-backlog.json"}]
    open_items = backlog.get("open_items")
    if not isinstance(open_items, list):
        return [{"id": "RUNNER-FINAL-INVALID-BACKLOG", "summary": "failure-backlog.open_items 不是列表"}]
    return open_items


def write_failure_backlog_with_runner_items(evidence: pathlib.Path, failures: list[str]) -> None:
    backlog = load_optional_json(evidence / "failure-backlog.json") or {}
    open_items = backlog.get("open_items")
    if not isinstance(open_items, list):
        open_items = []
    existing_ids = {str(item.get("id")) for item in open_items if isinstance(item, dict)}
    for index, failure in enumerate(failures, start=1):
        item_id = f"RUNNER-FINAL-{index:03d}"
        if item_id in existing_ids:
            continue
        open_items.append({
            "id": item_id,
            "severity": "blocking",
            "summary": failure,
            "owner": "e2e-runner",
            "next_step": "修复后重新执行完整 E2E",
        })
    backlog.update({
        "schema_id": "redcap-e2e-failure-backlog",
        "open_items": open_items,
        "closed_items": backlog.get("closed_items") if isinstance(backlog.get("closed_items"), list) else [],
        "next_round_required": bool(open_items),
    })
    write_json(evidence / "failure-backlog.json", backlog)


def criterion_pass(criterion: str, project: pathlib.Path, evidence: pathlib.Path, context: dict[str, Any]) -> tuple[bool, str]:
    if "外部项目根目录包含真实交付文件" in criterion:
        manifest = project_deliverable_manifest(project)
        return manifest.get("count", 0) > 0, f"deliverable_count={manifest.get('count', 0)}"
    if "入口说明" in criterion:
        return (project / "README.md").exists() or (project / "index.html").exists(), "README.md 或 index.html 存在"
    if "architecture.md" in criterion:
        return (project / "architecture.md").exists(), "project-root architecture.md"
    if "实现日志" in criterion or "测试结果" in criterion or "验收摘要" in criterion:
        required = ["implementation-log.json", "test-results.json", "final-evidence-bundle.json"]
        missing = [rel for rel in required if not (evidence / rel).exists()]
        return not missing, f"missing={missing}"
    if "loom-role-session-manifest" in criterion or "Loom 角色" in criterion:
        return context.get("role_ok") is True and (evidence / "loom-role-session-manifest.json").exists(), "role pipeline and manifest"
    if "默认实现不得依赖" in criterion or "外部依赖" in criterion:
        probes = load_optional_json(evidence / "negative-probes.json") or {}
        return probes.get("passed") is True, "negative-probes.json passed"
    if "self-purification-candidates.json" in criterion or "persona-distillation-decision.json" in criterion:
        return (evidence / "self-purification-candidates.json").exists() and (evidence / "persona-distillation-decision.json").exists(), "self-purification and persona boundary evidence"
    if "package-prism-check.json" in criterion:
        return context.get("package_prism_ok") is True, "package prism check"
    if "final-runner-test-results.json" in criterion:
        return context.get("runner_tests_ok") is True, "final runner validation"
    if "final-evidence-bundle.json" in criterion:
        return (evidence / "final-evidence-bundle.json").exists(), "final evidence bundle"
    if "final-prism-review.json" in criterion:
        return context.get("final_prism_ok") is True, "final prism review"
    if "blocked-package.json" in criterion:
        return not (project / "blocked-package.json").exists(), "blocked-package.json absent"
    if "浏览器" in criterion or "可访问" in criterion:
        return context.get("browser_ok") is True, "browser-inspection.json"
    return not context.get("failures"), "no runner failures matched generic criterion"


def build_acceptance_results(project: pathlib.Path, evidence: pathlib.Path, context: dict[str, Any]) -> list[dict[str, Any]]:
    acceptance = load_optional_json(evidence / "acceptance-criteria.json") or {}
    criteria = acceptance.get("criteria")
    if not isinstance(criteria, list):
        criteria = []
    results: list[dict[str, Any]] = []
    for index, criterion in enumerate(criteria, start=1):
        text = str(criterion)
        passed, evidence_text = criterion_pass(text, project, evidence, context)
        results.append({
            "id": f"AC-{index:02d}",
            "criterion": text,
            "passed": passed,
            "evidence": evidence_text,
        })
    browser_passed, browser_evidence = criterion_pass("浏览器实际打开检查", project, evidence, context)
    results.append({
        "id": "AC-browser",
        "criterion": "运行器使用真实浏览器打开项目入口，确认页面渲染、有可见内容、无浏览器错误，并写入截图证据。",
        "passed": browser_passed,
        "evidence": browser_evidence,
    })
    return results


def write_role_execution_risk(evidence: pathlib.Path) -> dict[str, Any]:
    payload = {
        "schema_id": "redcap-e2e-role-execution-risk",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "role_model": CODEX_ROLE_MODEL,
        "role_reasoning_effort": CODEX_ROLE_REASONING_EFFORT,
        "disable_plugins": CODEX_ROLE_DISABLE_PLUGINS,
        "risk": "Loom 角色由独立 Codex CLI 自动执行；角色质量风险由中等推理预算、结构化交接、运行器客观检查、浏览器检查和最终双 provider 棱镜复核共同约束。",
        "accepted_for_single_e2e": CODEX_ROLE_REASONING_EFFORT != "low",
        "notes": [
            "session_id 是角色隔离主证据。",
            "turn_id 可能来自宿主钩子同轮记录，不作为角色隔离主证据。",
        ],
    }
    write_json(evidence / "role-execution-risk.json", payload)
    return payload


def write_final_iteration_verdict(
    project: pathlib.Path,
    evidence: pathlib.Path,
    ok: bool,
    failures: list[str],
    context: dict[str, Any],
    *,
    final_prism_pending: bool = False,
) -> None:
    criteria_results = build_acceptance_results(project, evidence, {**context, "failures": failures})
    write_json(evidence / "iteration-verdict.json", {
        "schema_id": "redcap-e2e-iteration-verdict",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "status": "pass" if ok else "fail",
        "ready_for_engineering_use": ok and not final_prism_pending,
        "final_prism_pending": final_prism_pending,
        "criteria_results": criteria_results,
        "criteria_summary": {
            "total": len(criteria_results),
            "passed": sum(1 for item in criteria_results if item.get("passed") is True),
            "failed": sum(1 for item in criteria_results if item.get("passed") is not True),
        },
        "remaining_issues": [] if ok else failures,
        "evidence_checked": sorted(REQUIRED_EVIDENCE_CHECKS),
    })


def write_completion_marker(evidence: pathlib.Path, project: pathlib.Path, bundle: dict[str, Any], final_prism: dict[str, Any]) -> None:
    write_json(evidence / "completion-marker.json", {
        "schema_id": "redcap-e2e-completion-marker",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "project": str(project),
        "ready_for_engineering_use": True,
        "completion_scope": "single-e2e-run",
        "final_evidence_bundle_sha256": bundle.get("bundle_sha256"),
        "final_prism_strictest_verdict": final_prism.get("strictest_verdict"),
        "final_prism_review": "final-prism-review.json",
        "browser_inspection": "browser-inspection.json",
        "iteration_verdict": "iteration-verdict.json",
        "no_open_failure_backlog": True,
    })


def write_runner_prism_assistance(evidence: pathlib.Path, final_prism: dict[str, Any]) -> None:
    existing = load_optional_json(evidence / "prism-assisted-review.json") or {}
    final_reviews = final_prism.get("reviews") if isinstance(final_prism.get("reviews"), list) else []
    existing_reviews = existing.get("reviews") if isinstance(existing.get("reviews"), list) else []
    merged_reviews = existing_reviews or final_reviews
    existing.update({
        "schema_id": "redcap-e2e-prism-assisted-review",
        "used": bool(merged_reviews),
        "reviews": merged_reviews,
        "skip_reason": None if merged_reviews else "最终棱镜复核未运行或未返回有效评审",
        "cap_decision": "accepted" if final_prism.get("ok") is True else "blocked",
        "runner_final_review": {
            "path": "final-prism-review.json",
            "ok": final_prism.get("ok") is True,
            "strictest_verdict": final_prism.get("strictest_verdict"),
            "failures": final_prism.get("failures", []),
        },
    })
    write_json(evidence / "prism-assisted-review.json", existing)


def final_prism_request(direction: str, bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "task": "Review whether this RedCap E2E run may write its completion marker.",
        "user_intent": "Norven wants RedCap to prove it can drive a real project through role-separated Loom workflow, hooks, evidence, self-purification, persona boundary, and failure feedback before claiming production usefulness.",
        "main_claim": "The E2E runner may write completion-marker.json because all role, hook, test, evidence, and failure-loop requirements passed after reviewer exit.",
        "changed_reality": [
            "An external project was created outside the RedCap source workspace.",
            "Five Loom roles ran as independent Codex CLI sessions with project-level Hook evidence.",
            "The runner independently reran project validation and bundled evidence hashes before deciding completion.",
            "The runner opened the deliverable in a real headless browser, captured a screenshot, and checked visible rendered content before requesting completion.",
        ],
        "evidence": [
            {
                "kind": "final-evidence-bundle",
                "reference": "final-evidence-bundle.json",
                "summary": bundle,
            }
        ],
        "review_mode": "completion_review",
        "risk_level": "high",
        "requested_providers": ["kimi", "claude-code"],
        "known_constraints": [
            "Reviewer must not self-certify completion.",
            "Open failure-backlog items block completion.",
            "Completion marker scope is only this E2E run, not permanent RedCap full revival.",
            "The bundled iteration-verdict is pre-final: it may mark objective criteria passed while final_prism_pending=true until this provider review passes.",
            "Loom role session_id is the role isolation evidence; turn_id may reflect host hook grouping and is not used as the role identity boundary.",
        ],
        "role_execution_profile": {
            "model": CODEX_ROLE_MODEL,
            "reasoning_effort": CODEX_ROLE_REASONING_EFFORT,
            "disable_plugins": CODEX_ROLE_DISABLE_PLUGINS,
            "quality_controls": [
                "structured role handoff files",
                "runner-owned final validation",
                "browser-inspection.json",
                "two-provider final Prism review",
            ],
        },
    }


def run_final_prism_review(project: pathlib.Path, evidence: pathlib.Path, direction: str, bundle: dict[str, Any]) -> dict[str, Any]:
    package_prism = project / ".redcap" / "runtime" / "prism" / "bin" / "prism"
    package_dispatch = project / ".redcap" / "runtime" / "prism" / "bin" / "prism-dispatch"
    run_dir = evidence / "final-prism-review"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    request_path = run_dir / "request.json"
    request_payload = final_prism_request(direction, bundle)
    write_json(request_path, request_payload)
    if not package_prism.exists() or not package_dispatch.exists():
        summary = {
            "schema_id": "redcap-e2e-final-prism-review",
            "producer": "e2e-runner",
            "ok": False,
            "run_dir": str(run_dir),
            "failures": ["安装包内缺少 prism 或 prism-dispatch"],
        }
        write_json(evidence / "final-prism-review.json", summary)
        return summary
    init = run_command([str(package_prism), "session-init", "--task-id", "complete-revival-e2e-final-review", "--run-dir", str(run_dir)], cwd=project, timeout_seconds=30)
    manifest = run_dir / "session.json"
    dispatches: dict[str, Any] = {}
    review_paths: list[pathlib.Path] = []
    reviews: list[dict[str, Any]] = []
    failures: list[str] = []
    if not init["ok"]:
        failures.append("最终棱镜会话初始化失败")
    else:
        for provider in ["kimi", "claude-code"]:
            review_out = run_dir / f"{provider}.review.json"
            raw_out = run_dir / f"{provider}.raw.json"
            dispatch = run_command([
                str(package_dispatch),
                "--provider",
                provider,
                "--manifest",
                str(manifest),
                "--request",
                str(request_path),
                "--review-out",
                str(review_out),
                "--raw-out",
                str(raw_out),
                "--timeout-seconds",
                "240",
                "--total-timeout-seconds",
                "300",
                "--task-total-timeout-seconds",
                "720",
                "--max-retries",
                "0",
            ], cwd=project, timeout_seconds=360)
            dispatches[provider] = command_receipt(dispatch)
            review = load_optional_json(review_out)
            if dispatch["ok"] and review is not None:
                review_paths.append(review_out)
                reviews.append(review)
            else:
                failures.append(f"{provider} 最终棱镜复核未返回有效 review")
    merge_payload: dict[str, Any] | None = None
    if len(review_paths) == 2:
        merge_path = run_dir / "merge.json"
        merge = run_command([str(package_prism), "merge", str(review_paths[0]), str(review_paths[1]), "--out", str(merge_path)], cwd=project, timeout_seconds=30)
        if merge["ok"]:
            merge_payload = load_optional_json(merge_path)
            if merge_payload is None:
                failures.append("最终棱镜 merge.json 无法读取")
        else:
            failures.append("最终棱镜合并失败")
        dispatches["merge"] = command_receipt(merge)
    else:
        failures.append("最终棱镜复核必须同时取得 Kimi 和 Claude Code 两个评审结果")
    strictest = merge_payload.get("strictest_verdict") if isinstance(merge_payload, dict) else None
    if strictest != "pass":
        failures.append(f"最终棱镜 strictest_verdict 不是 pass：{strictest}")
    summary = {
        "schema_id": "redcap-e2e-final-prism-review",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "ok": not failures,
        "run_dir": str(run_dir),
        "request": str(request_path),
        "providers_required": ["kimi", "claude-code"],
        "reviews": reviews,
        "dispatches": dispatches,
        "merge": merge_payload,
        "strictest_verdict": strictest,
        "failures": failures,
    }
    write_json(evidence / "final-prism-review.json", summary)
    return summary


def finalize_e2e_acceptance(
    project: pathlib.Path,
    evidence: pathlib.Path,
    direction: str,
    role_result: dict[str, Any],
    package_prism: dict[str, Any],
    missing_hooks: list[str],
) -> dict[str, Any]:
    marker = evidence / "completion-marker.json"
    if marker.exists():
        marker.unlink()
        append_jsonl(evidence / "workflow-events.jsonl", {
            "event": "runner_removed_untrusted_completion_marker",
            "recorded_at": iso_now(),
        })
    runner_tests = run_final_runner_tests(project)
    write_json(evidence / "final-runner-test-results.json", runner_tests)
    browser_inspection = run_browser_inspection(project, evidence)
    write_json(evidence / "browser-inspection.json", browser_inspection)
    role_risk = write_role_execution_risk(evidence)
    failures: list[str] = []
    if role_result.get("ok") is not True:
        failures.append("Loom 角色管线未通过")
    if missing_hooks:
        failures.append(f"缺少项目级 Hook 事件：{missing_hooks}")
    if package_prism.get("ok") is not True:
        failures.append("安装包内棱镜自检未通过")
    if runner_tests.get("ok") is not True:
        failures.append("运行器独立重跑项目验证未通过")
    if browser_inspection.get("ok") is not True:
        failures.append("运行器浏览器检查未通过")
    if role_risk.get("accepted_for_single_e2e") is not True:
        failures.append("Loom 角色推理预算风险未被接受")
    backlog_path = evidence / "failure-backlog.json"
    if backlog_path.exists() or role_result.get("ok") is True:
        open_items = backlog_open_items(evidence)
        if open_items:
            failures.append(f"failure-backlog 仍有开放项：{open_items}")
    pre_final_context = {
        "role_ok": role_result.get("ok") is True,
        "package_prism_ok": package_prism.get("ok") is True,
        "runner_tests_ok": runner_tests.get("ok") is True,
        "browser_ok": browser_inspection.get("ok") is True,
        "final_prism_ok": False,
    }
    write_final_iteration_verdict(project, evidence, not failures, failures, pre_final_context, final_prism_pending=True)
    bundle = build_final_evidence_bundle(project, evidence, direction)
    write_json(evidence / "final-evidence-bundle.json", bundle)
    if failures:
        final_prism = {
            "schema_id": "redcap-e2e-final-prism-review",
            "producer": "e2e-runner",
            "ok": False,
            "skipped": True,
            "skip_reason": "前置客观证据未通过，跳过最终 provider 复核",
            "strictest_verdict": None,
            "failures": failures,
        }
        write_json(evidence / "final-prism-review.json", final_prism)
    else:
        final_prism = run_final_prism_review(project, evidence, direction, bundle)
        write_runner_prism_assistance(evidence, final_prism)
        if final_prism.get("ok") is not True:
            failures.append(f"最终棱镜复核未通过：{final_prism.get('failures')}")
    if failures:
        if "final_prism" in locals():
            write_runner_prism_assistance(evidence, final_prism)
        write_failure_backlog_with_runner_items(evidence, failures)
        write_final_iteration_verdict(project, evidence, False, failures, {
            **pre_final_context,
            "final_prism_ok": final_prism.get("ok") is True if "final_prism" in locals() else False,
        })
    else:
        write_final_iteration_verdict(project, evidence, True, [], {
            **pre_final_context,
            "final_prism_ok": final_prism.get("ok") is True,
        })
        bundle = build_final_evidence_bundle(project, evidence, direction)
        write_json(evidence / "final-evidence-bundle.json", bundle)
        write_completion_marker(evidence, project, bundle, final_prism)
    return {
        "schema_id": "redcap-e2e-finalization-result",
        "ok": not failures,
        "runner_tests_ok": runner_tests.get("ok") is True,
        "final_prism_ok": final_prism.get("ok") is True,
        "completion_marker_present": (evidence / "completion-marker.json").exists(),
        "failures": failures,
    }


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
    clearance_summary = load_optional_json(evidence / "role-gate-clearance-summary.json")
    if clearance_summary is not None:
        if clearance_summary.get("producer") != "e2e-runner":
            failures.append("role-gate-clearance-summary 必须由 e2e-runner 生成")
        roles = clearance_summary.get("roles")
        if not isinstance(roles, list):
            failures.append("role-gate-clearance-summary.roles 必须是列表")
        else:
            cleared_roles = {str(item.get("role")) for item in roles if isinstance(item, dict) and item.get("decision") == "cleared_for_external_project_role_execution"}
            missing = sorted(set(LOOM_EXECUTION_ROLES) - cleared_roles)
            if missing:
                failures.append(f"role-gate-clearance-summary 缺少角色协调凭证：{missing}")
        if clearance_summary.get("runner_owns_full_prism") is not True:
            failures.append("role-gate-clearance-summary 必须声明 runner_owns_full_prism=true")
        if clearance_summary.get("role_gate_self_block_forbidden") is not True:
            failures.append("role-gate-clearance-summary 必须禁止角色自跑门禁后阻塞")
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
    if test_results is not None:
        if test_results.get("status") == "completed" and test_results.get("passed") is not True:
            failures.append("test-results.json status=completed 时 passed 必须为 true")
        if test_results.get("status") == "failed" and test_results.get("passed") is not False:
            failures.append("test-results.json status=failed 时 passed 必须为 false")
    negative_probes = load_optional_json(evidence / "negative-probes.json")
    if negative_probes is not None and negative_probes.get("role") != "tester":
        failures.append("negative-probes.json 必须由 tester 角色产出")
    if negative_probes is not None:
        if negative_probes.get("status") == "completed" and negative_probes.get("passed") is not True:
            failures.append("negative-probes.json status=completed 时 passed 必须为 true")
        if negative_probes.get("status") == "failed" and negative_probes.get("passed") is not False:
            failures.append("negative-probes.json status=failed 时 passed 必须为 false")
    persona = load_optional_json(evidence / "persona-distillation-decision.json")
    if persona is not None:
        if persona.get("public_write") is not False:
            failures.append("persona-distillation-decision.public_write 必须为 false")
        if persona.get("private_body_written") is not False:
            failures.append("persona-distillation-decision.private_body_written 必须为 false")
        if persona.get("privacy_class") != "cap-private":
            failures.append("persona-distillation-decision.privacy_class 必须是 cap-private")
        persona_text = json.dumps(persona, ensure_ascii=False).casefold()
        leaked_markers = [marker for marker in PRIVATE_PERSONA_MARKERS if marker.casefold() in persona_text]
        if leaked_markers:
            failures.append(f"persona-distillation-decision 禁止包含身份私密材料标记：{leaked_markers}")
    package_prism = load_optional_json(evidence / "package-prism-check.json")
    if package_prism is not None:
        stdout_tail = str(package_prism.get("stdout_tail") or "")
        if package_prism.get("ok") is not True or package_prism.get("exit_code") != 0:
            failures.append("package-prism-check 必须成功退出")
        if "PRISM_CHECK_OK" not in stdout_tail:
            failures.append("package-prism-check 必须包含 PRISM_CHECK_OK")
    runner_tests = load_optional_json(evidence / "final-runner-test-results.json")
    if runner_tests is not None and runner_tests.get("ok") is not True:
        failures.append("final-runner-test-results 必须证明运行器独立验证通过")
    browser_inspection = load_optional_json(evidence / "browser-inspection.json")
    if browser_inspection is not None and browser_inspection.get("ok") is not True:
        failures.append("browser-inspection 必须证明运行器独立浏览器检查通过")
    role_risk = load_optional_json(evidence / "role-execution-risk.json")
    if role_risk is not None and role_risk.get("accepted_for_single_e2e") is not True:
        failures.append("role-execution-risk 必须说明本轮角色执行风险已被约束")
    final_bundle = load_optional_json(evidence / "final-evidence-bundle.json")
    if final_bundle is not None:
        files = final_bundle.get("files")
        if not isinstance(files, list) or not files:
            failures.append("final-evidence-bundle.files 必须非空")
        else:
            for item in files:
                if not isinstance(item, dict):
                    failures.append("final-evidence-bundle.files 条目必须是对象")
                    continue
                if item.get("exists") is True and not item.get("sha256"):
                    failures.append(f"final-evidence-bundle 中存在缺少 sha256 的已存在文件：{item.get('path')}")
    final_prism = load_optional_json(evidence / "final-prism-review.json")
    if final_prism is not None:
        if final_prism.get("ok") is not True:
            failures.append("final-prism-review 必须通过")
        if final_prism.get("strictest_verdict") != "pass":
            failures.append("final-prism-review.strictest_verdict 必须是 pass")
    completion_marker = load_optional_json(evidence / "completion-marker.json")
    if completion_marker is not None:
        if completion_marker.get("producer") != "e2e-runner":
            failures.append("completion-marker 必须由 e2e-runner 生成，不能由 Loom 角色自证")
        if completion_marker.get("ready_for_engineering_use") is not True:
            failures.append("completion-marker.ready_for_engineering_use 必须为 true")
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
    write_json(evidence / "hook-events-summary.json", {
        "schema_id": "redcap-e2e-hook-events-summary",
        "events": hook_events,
        "missing_events": missing_hooks,
    })
    finalization = finalize_e2e_acceptance(project, evidence, direction, result, package_prism, missing_hooks)
    meaningful = validate_meaningful_e2e_evidence(evidence)
    write_json(evidence / "revival-followthrough-e2e-check.json", meaningful["followthrough"])
    write_json(evidence / "meaningful-evidence-check.json", meaningful)
    completion_marker = evidence / "completion-marker.json"
    summary = {
        "schema_id": "redcap-ai-e2e-run-result",
        "ok": result["ok"] and not missing_hooks and completion_marker.exists(),
        "project": str(project),
        "evidence_root": str(evidence),
        "codex_cli_ok": result["ok"],
        "package_prism_ok": package_prism["ok"],
        "hook_events_ok": not missing_hooks,
        "finalization_ok": finalization["ok"],
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
        summary["failures"].append("E2E 运行器没有写入 completion-marker.json；这表示最终验收未通过或被阻塞")
    if not finalization["ok"]:
        summary["failures"].append(f"运行器最终验收未通过：{finalization['failures']}")
    if not meaningful["ok"]:
        summary["failures"].append(f"有意义 E2E 证据不完整：{meaningful['failures']}")
    if not meaningful["ready_for_engineering_use"]:
        summary["failures"].append("iteration-verdict 未证明 ready_for_engineering_use=true")
    summary["ok"] = (
        summary["ok"]
        and package_prism["ok"]
        and finalization["ok"]
        and meaningful["ok"]
        and meaningful["ready_for_engineering_use"]
    )
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
            project = pathlib.Path(str(prepared["project"]))
            evidence = pathlib.Path(str(prepared["evidence_root"]))
            for rel in load_json(CONTRACT)["raw_evidence_package"]["required_files_after_prepare"]:
                if not (evidence / rel).exists():
                    failures.append(f"prepare 后缺少证据文件：{rel}")
            retry_reason = role_failure_retry_reason({
                "ok": False,
                "stdout": "",
                "stderr": "responses_websocket tls handshake eof; stream disconnected",
            }, artifact_exists=False)
            if not retry_reason:
                failures.append("传输抖动失败没有被识别为可重试")
            if role_failure_retry_reason({
                "ok": False,
                "stdout": "partial output",
                "stderr": "stream disconnected",
            }, artifact_exists=False):
                failures.append("已有 stdout 的角色失败不应被自动重试")
            events_path = project_hook_events_path(project)
            events_path.parent.mkdir(parents=True, exist_ok=True)
            retry_events = [
                {
                    "event": "UserPromptSubmit",
                    "session_id": "11111111-1111-4111-8111-111111111111",
                    "turn_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "recorded_at": iso_now(),
                    "prompt": {"normalized_excerpt": f"{ROLE_MARKER_PREFIX}developer failed attempt"},
                },
                {
                    "event": "UserPromptSubmit",
                    "session_id": "22222222-2222-4222-8222-222222222222",
                    "turn_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                    "recorded_at": iso_now(),
                    "prompt": {"normalized_excerpt": f"{ROLE_MARKER_PREFIX}developer successful attempt"},
                },
            ]
            events_path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in retry_events) + "\n", encoding="utf-8")
            manifest = build_role_session_manifest(project, evidence, {
                "developer": {
                    "ok": True,
                    "session_id": "22222222-2222-4222-8222-222222222222",
                    "attempt_count": 2,
                }
            }, include_pending=True)
            developer_role = next(item for item in manifest["roles"] if item["role"] == "developer")
            if developer_role.get("session_id") != "22222222-2222-4222-8222-222222222222":
                failures.append("重试成功后没有选择成功尝试的 session_id")
            if developer_role.get("retry_session_ids") != ["11111111-1111-4111-8111-111111111111"]:
                failures.append("重试失败尝试没有进入 retry_session_ids")
            if manifest.get("session_loss_alarms"):
                failures.append(f"重试成功夹具不应产生 session_loss_alarms：{manifest.get('session_loss_alarms')}")
            developer_prompt = build_role_prompt(project, evidence, "developer", "自检方向")
            if ".redcap/evidence/e2e/requirements.json" not in developer_prompt:
                failures.append("developer 提示词没有给出 requirements.json 的证据目录实际路径")
            if ".redcap/evidence/e2e/acceptance-criteria.json" not in developer_prompt:
                failures.append("developer 提示词没有给出 acceptance-criteria.json 的证据目录实际路径")
            if ".redcap/evidence/e2e/implementation-log.json" not in developer_prompt:
                failures.append("developer 提示词没有给出 implementation-log.json 的证据目录目标路径")
            developer_clearance = build_role_gate_clearance(project, evidence, "developer", "自检方向")
            developer_reads = {
                item["name"]: item
                for item in developer_clearance.get("role_must_read_resolved", [])
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            }
            for required_input in ["requirements.json", "acceptance-criteria.json"]:
                record = developer_reads.get(required_input)
                if not record or record.get("location") != "evidence" or record.get("exists") is not True:
                    failures.append(f"developer 门禁凭证没有把 {required_input} 解析到已存在的证据目录文件")
            developer_writes = {
                item["name"]: item
                for item in developer_clearance.get("role_must_write_resolved", [])
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            }
            implementation_log = developer_writes.get("implementation-log.json")
            if not implementation_log or implementation_log.get("location") != "evidence":
                failures.append("developer 门禁凭证没有把 implementation-log.json 解析到证据目录")
            tester_prompt = build_role_prompt(project, evidence, "tester", "自检方向")
            if ROLE_TIMEOUT_SECONDS.get("tester", 0) < 360:
                failures.append("tester 角色超时预算低于 360 秒，容易在写入证据前被截断")
            if "先写进行中证据" not in tester_prompt or 'status="in_progress"' not in tester_prompt:
                failures.append("tester 提示词没有要求在验证前先写 in_progress 证据")
            if "最多一个正向验证命令" not in tester_prompt or "最多一个负向或静态探针" not in tester_prompt:
                failures.append("tester 提示词没有限制验证动作数量，容易因过度探索超时")
            if "每执行完一个验证动作，立即更新对应 JSON" not in tester_prompt:
                failures.append("tester 提示词没有要求验证后立即更新结构化证据")
            if "Node 标准库脚本" not in tester_prompt or "未引用的 shell 通配符" not in tester_prompt:
                failures.append("tester 提示词没有禁止危险 shell 通配符负向探针")
            if "status 与 passed 必须一致" not in tester_prompt:
                failures.append("tester 提示词没有要求 status 与 passed 一致")
            verify_script = project / "scripts" / "verify.sh"
            verify_script.parent.mkdir(parents=True, exist_ok=True)
            verify_script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            detected_argv, detected_source = detect_validation_command(project)
            if detected_argv != ["bash", "scripts/verify.sh"] or detected_source != "scripts/verify.sh":
                failures.append("运行器没有识别 scripts/verify.sh 作为本地验证命令")
            verify_mjs = project / "scripts" / "verify.mjs"
            verify_mjs.write_text("process.exit(0)\n", encoding="utf-8")
            detected_argv, detected_source = detect_validation_command(project)
            if detected_argv != ["node", "scripts/verify.mjs"] or detected_source != "scripts/verify.mjs":
                failures.append("运行器没有识别 scripts/verify.mjs 作为本地验证命令")
            reviewer_prompt = build_role_prompt(project, evidence, "reviewer", "自检方向")
            if "terminal_completion=false" not in reviewer_prompt or '"terminal_completion": false' not in reviewer_prompt:
                failures.append("reviewer 提示词没有明确要求 terminal_completion=false")
            if "runner_owned_follow_up" not in reviewer_prompt or "open_items 只记录" not in reviewer_prompt:
                failures.append("reviewer 提示词没有区分 open_items 与 runner_owned_follow_up")
            if "blocking_findings" not in reviewer_prompt or "blocking_failures" not in reviewer_prompt:
                failures.append("reviewer 提示词没有禁止 blocking_failures 近义字段")
            if "private_body" not in reviewer_prompt or "reason 必须是非空字符串" not in reviewer_prompt:
                failures.append("reviewer 提示词没有明确人格边界字段要求")
            if "reason 不要复述禁止项本身" not in reviewer_prompt:
                failures.append("reviewer 提示词没有禁止在人格 reason 中复述敏感禁止项")
            verdict_template = load_json(evidence / "review-verdict-template.json")
            if verdict_template.get("terminal_completion") is not False:
                failures.append("review-verdict-template.json 没有预置 terminal_completion=false")
            runner_follow_up = verdict_template.get("runner_owned_follow_up")
            if not isinstance(runner_follow_up, list) or sorted(set(REVIEWER_RUNNER_OWNED_FOLLOW_UP) - {str(item) for item in runner_follow_up}):
                failures.append("review-verdict-template.json 没有预置完整的 runner_owned_follow_up")
            write_json(evidence / "failure-backlog.json", {
                "schema_id": "redcap-e2e-failure-backlog",
                "open_items": [],
                "closed_items": [],
                "next_round_required": False
            })
            write_json(evidence / "prism-assisted-review.json", {
                "schema_id": "redcap-e2e-prism-assisted-review",
                "used": True,
                "reviews": [
                    {
                        "scope": "runner-prism-boundary",
                        "finding": "自检夹具确认棱镜协助边界被记录。",
                        "effect_on_verdict": "reviewer 只给阶段评审。"
                    }
                ],
                "skip_reason": None,
                "cap_decision": "stage_pass",
                "prism_assistance_request": {"requested": True},
                "impact": "自检夹具确认 reviewer 记录棱镜协助边界。"
            })
            write_json(evidence / "self-purification-candidates.json", {
                "schema_id": "redcap-e2e-self-purification-candidates",
                "decisions": [],
                "no_candidate_reason": "自检夹具没有真实任务候选。"
            })
            write_json(evidence / "persona-distillation-decision.json", {
                "schema_id": "redcap-e2e-persona-distillation-decision",
                "privacy_class": "cap-private",
                "public_write": False,
                "private_body_written": False,
                "reason": "自检夹具没有可晋升的人格信号。"
            })
            write_json(evidence / "review-verdict.json", {
                "schema_id": "redcap-e2e-review-verdict",
                "status": "pass",
                "terminal_completion": False,
                "boundary": "reviewer 只能给阶段评审，不能自证本轮 E2E 终局完成。",
                "blocking_findings": [],
                "runner_owned_follow_up": REVIEWER_RUNNER_OWNED_FOLLOW_UP
            })
            reviewer_failures = validate_reviewer_outputs(evidence)
            if reviewer_failures:
                failures.append(f"reviewer 终局边界自检失败：{reviewer_failures}")
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

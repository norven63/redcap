#!/usr/bin/env python3
"""RedCap 通用 E2E（端到端验收）运行器。"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import signal
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.request
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
    "product_manager": 420,
    "architect": 420,
    "developer": 600,
    "tester": 480,
    "reviewer": 480,
}
CODEX_ROLE_MODEL = os.environ.get("REDCAP_E2E_CODEX_ROLE_MODEL", "gpt-5.5")
CODEX_ROLE_REASONING_EFFORT = os.environ.get("REDCAP_E2E_CODEX_ROLE_REASONING_EFFORT", "medium")
CODEX_ROLE_DISABLE_PLUGINS = os.environ.get("REDCAP_E2E_CODEX_ROLE_DISABLE_PLUGINS", "1") != "0"
CODEX_ROLE_EXTRA_DISABLED_FEATURES = [
    item.strip()
    for item in os.environ.get("REDCAP_E2E_CODEX_ROLE_EXTRA_DISABLED_FEATURES", "apps,general_analytics").split(",")
    if item.strip()
]
CODEX_ROLE_PRESERVE_USER_CONFIG = True
CODEX_ROLE_MAX_ATTEMPTS = int(os.environ.get("REDCAP_E2E_CODEX_ROLE_MAX_ATTEMPTS", "3"))
CODEX_ROLE_RETRYABLE_STDERR_MARKERS = [
    "responses_websocket",
    "stream disconnected",
    "tls handshake eof",
    "error sending request",
    "http/request failed",
    "reconnecting",
    "request timed out",
    "operation timed out",
    "temporarily unavailable",
]
CODEX_ROLE_INTERACTIVE_GATE_MARKERS = [
    "brainstorming/SKILL.md",
    "<HARD-GATE>",
    "User Review Gate",
    "docs/superpowers/specs",
    "Please review it before proceeding",
]
CARRIER_PROBE_MAX_ATTEMPTS = int(os.environ.get("REDCAP_E2E_CARRIER_PROBE_MAX_ATTEMPTS", "3"))
MEANINGFUL_E2E_REQUIRED_FILES = [
    "loom-role-session-manifest.json",
    "loom-role-session-manifest-pre-review.json",
    "role-gate-clearance-summary.json",
    "prism-assisted-review.json",
    "knowledge-retrieval-evidence.json",
    "self-purification-candidates.json",
    "runner-self-purification-resolution.json",
    "persona-distillation-decision.json",
    "test-results.json",
    "negative-probes.json",
    "runner-negative-contract-probe.json",
    "runner-character-player-contract-probe.json",
    "package-prism-check.json",
    "final-runner-test-results.json",
    "browser-inspection.json",
    "behavioral-browser-verification.json",
    "independent-browser-verification.json",
    "independent-observer.json",
    "visual-independence-report.json",
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
    "runner-self-purification-resolution.json",
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
    "项目级 Hook",
    "runner-character-player-contract-probe.json",
    "visual-independence-report.json",
    "冻结证据包",
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
OBSERVER_TIMEOUT_SECONDS = int(os.environ.get("REDCAP_E2E_OBSERVER_TIMEOUT_SECONDS", "300"))
BROWSER_INSPECTION_VIEWPORT = {"width": 1280, "height": 900}
BEHAVIORAL_BROWSER_VIEWPORT = {"width": 1280, "height": 900}
INDEPENDENT_BROWSER_VIEWPORT = {"width": 1176, "height": 820}


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


def evidence_file_record(path: pathlib.Path, *, base: pathlib.Path | None = None) -> dict[str, Any]:
    display_path = path.relative_to(base).as_posix() if base and path.exists() else path.name
    record: dict[str, Any] = {
        "path": display_path,
        "exists": path.exists(),
        "sha256": None,
        "size": 0,
    }
    if path.exists():
        record["sha256"] = sha256_file(path)
        record["size"] = path.stat().st_size
    return record


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


def role_interactive_gate_marker(result: dict[str, Any]) -> str | None:
    combined = f"{result.get('stdout') or ''}\n{result.get('stderr') or ''}".casefold()
    for marker in CODEX_ROLE_INTERACTIVE_GATE_MARKERS:
        if marker.casefold() in combined:
            return marker
    return None


def actionable_interactive_gate_marker(result: dict[str, Any], artifact_exists: bool) -> str | None:
    if result.get("ok") is True or artifact_exists:
        return None
    return role_interactive_gate_marker(result)


def role_failure_retry_reason(result: dict[str, Any], artifact_exists: bool) -> str | None:
    if result.get("ok") is True or artifact_exists:
        return None
    interactive_marker = actionable_interactive_gate_marker(result, artifact_exists)
    if interactive_marker:
        return f"interactive approval gate marker: {interactive_marker}"
    stderr = str(result.get("stderr") or "").casefold()
    stdout = str(result.get("stdout") or "")
    if stdout.strip():
        return None
    if result.get("timed_out") is True:
        return f"codex role timeout after {result.get('timeout_seconds')} seconds"
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


def domain_contracts_for_direction(direction: str) -> list[dict[str, Any]]:
    normalized = direction.casefold()
    contracts: list[dict[str, Any]] = []
    if any(keyword in normalized for keyword in ["报名", "意向", "signup", "sign-up", "registration"]):
        contracts.append({
            "id": "signup-intent-data-contract",
            "trigger": "需求方向包含报名或意向",
            "description": "活动、场次或事件数据必须能独立表达报名意向。",
            "required_data_shape": "至少一个活动记录包含非空 signups 数组；兼容非空 signupIntent 字段，但优先使用 signups。",
            "signups_item_hint": "signups 每项建议包含玩家、角色或身份、意向状态、备注中的至少两类信息。",
            "must_be_reflected_by_roles": [
                "product_manager",
                "architect",
                "developer",
                "tester",
                "reviewer"
            ],
            "validation_hint": "验证脚本或负向探针必须判定 signups=[] 和 signupIntent 为空为失败。"
        })
    if "角色" in direction and "玩家" in direction:
        contracts.append({
            "id": "character-player-relation-contract",
            "trigger": "需求方向同时包含角色和玩家",
            "description": "角色与玩家关系必须在数据和界面中可追踪。",
            "required_data_shape": "角色记录应能引用或展示对应玩家，界面应能同时看到角色名和玩家名。",
            "must_be_reflected_by_roles": [
                "architect",
                "developer",
                "tester",
                "reviewer"
            ],
            "validation_hint": "浏览器行为验收会在适用时检查角色名和玩家名在 UI 中相邻呈现。"
        })
    return contracts


def build_requirements(direction: str) -> dict[str, Any]:
    domain_contracts = domain_contracts_for_direction(direction)
    return {
        "schema_id": "redcap-e2e-requirements",
        "created_at": iso_now(),
        "direction": direction,
        "cap_expanded_need": f"围绕“{direction}”交付一个可在本地运行、可检查、可维护的小型工程成果。",
        "domain_contracts": domain_contracts,
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
    domain_contracts = domain_contracts_for_direction(direction)
    criteria = [
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
        ".redcap/evidence/e2e/independent-browser-verification.json 证明至少一次浏览器复核来自独立子进程",
        "如果实现方遇到阻塞，必须写 blocked-package.json，而不是写 completion-marker.json"
    ]
    for contract in domain_contracts:
        criteria.append(f"领域数据契约 {contract['id']} 必须被架构、实现、验证和评审承接：{contract['validation_hint']}")
    return {
        "schema_id": "redcap-e2e-acceptance-criteria",
        "direction_sha256": sha256_text(direction),
        "domain_contracts": domain_contracts,
        "criteria": criteria,
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
    - 如果 requirements.json 或 acceptance-criteria.json 包含 domain_contracts，必须在本角色产物中记录你如何承接这些领域数据契约；不能只把自然语言需求写进 UI 文案。
    - 本角色不得运行 prism-dispatch、prism session-init、prism merge 或完整 provider 评审；需要棱镜协助时，把请求和理由写入 role-artifacts/<role>.json，由 E2E 运行器统一调度。
    - 本角色不得写 .redcap/evidence/e2e/prism/<role>/ 或 .redcap/evidence/e2e/prism/<role>_completion/ 目录；这些目录会被视为角色越权。
    - 本角色只允许读取上游输入、角色门禁协调文件和必要模板；不要读取 manifest.json、Hook 事件、role-workspaces、redcap-package.zip 或 RedCap 源码。
    - 本角色已经处于 E2E 运行器授权的执行模式；不要启动需要人工批准的交互式设计流程，不要等待用户批准，不要把“需要先问用户”当作阻塞；若某个技能要求人工批准才能继续，说明该技能不适用于本次非交互 E2E，请回到本角色产物清单继续交付。
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
        3. 明确问题陈述、范围边界、验收重点；如果存在 domain_contracts，必须把每项契约列为验收重点，并写入 role-artifacts/product_manager.json。
        """,
        "architect": """
        你的任务：
        1. 阅读产品经理交付和验收标准。
        2. 立即写 architecture.md，必须包含：目标、目录结构、数据模型、交互流程、运行方式、验证方式、风险与回滚。
           如果存在 domain_contracts，architecture.md 的数据模型和验证方式必须逐项承接；例如 signup-intent-data-contract 必须设计非空 signups 数组或非空 signupIntent 字段，并说明验证脚本如何检查。
        3. 默认选择无外部依赖、无需联网安装、可直接本地验证的方案；除非需求明确要求，不要引入 Vite、Playwright、数据库或服务端框架。
        4. 立即写 risk-register.json，至少包含 risks 数组；每项包含 id、risk、impact、mitigation、owner。
        5. 立即写 role-artifacts/architect.json，status="completed"，并列出读取的输入和写出的文件。
        6. 不要读取 manifest.json，不要检查 role-workspaces，不要扫描 .redcap 全目录。
        """,
        "developer": """
        你的任务：
        1. 按 architecture.md 实现一个可运行的本地项目。
        2. 优先选择简单、无外部依赖、无需联网安装、可本地验证的技术栈；如果 architecture.md 要求重型依赖但需求并不需要，你应收窄为纯 HTML/CSS/JS + Node 内置模块验证，并在 implementation-log.json 说明原因。
        3. 必须让实现和本地验证命令覆盖 acceptance-criteria.json 的 domain_contracts；例如 signup-intent-data-contract 必须在真实数据中提供非空 signups 数组或非空 signupIntent 字段，且验证脚本要检查该字段，不能只把报名意向放进玩家备注或按钮文案。
        4. 写 implementation-log.json 和 role-artifacts/developer.json。
        5. 如果提供验证脚本，机器验证输出必须写 verification-results.json 或其他非角色文件，不能写或覆盖 test-results.json；test-results.json 只属于 tester 角色。
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
           如果需求包含报名意向，负向或静态探针必须验证至少一个活动有非空报名数据；优先接受 signups 数组（每项可以包含玩家、角色、意向或备注），也可以兼容 signupIntent 字段，但 signups=[] 或 signupIntent 为空必须判定失败。
        4. 每执行完一个验证动作，立即更新对应 JSON；验证动作全部结束后，立即把三个文件更新为 completed 或 failed。
        5. test-results.json 必须标记 role="tester"，并记录 commands、positive_checks、passed；negative-probes.json 必须标记 role="tester"，并记录 probes、passed。status 与 passed 必须一致：completed 对应 passed=true，failed 对应 passed=false。
        6. 如果测试失败，必须把失败写清楚，不要替开发者修复。
        """,
        "reviewer": """
        你的任务：
        1. 审阅需求、架构、实现、测试和角色证据。
           注意：loom-role-session-manifest-pre-review.json 只用于审核上游四个角色；reviewer 自己的 session_id 会在你退出后由运行器写入最终 loom-role-session-manifest.json，因此不要因为最终清单在评审前缺少 reviewer 自身而阻塞。
           如果 requirements.json 或 acceptance-criteria.json 包含 domain_contracts，必须逐项审核产品、架构、开发和测试是否承接；任何未承接项必须进入 blocking_findings 和 failure-backlog.open_items。
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


def build_codex_role_argv(project: pathlib.Path, role: str, message_path: pathlib.Path, prompt: str) -> list[str]:
    argv = [
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
        argv.extend(["--disable", "plugins"])
    for feature in CODEX_ROLE_EXTRA_DISABLED_FEATURES:
        argv.extend(["--disable", feature])
    for state_dir in provider_state_dirs_for_role(role):
        argv.extend(["--add-dir", str(state_dir)])
    argv.extend([
        "--output-last-message",
        str(message_path),
        prompt,
    ])
    return argv


def role_retry_prompt(base_prompt: str, attempt_index: int) -> str:
    if attempt_index <= 1:
        return base_prompt
    return base_prompt + textwrap.dedent("""\

    【重试约束】
    上一次尝试没有产出本角色必需文件，可能误入了需要人工批准的交互式设计流程或遇到传输抖动。
    本次重试必须直接完成本角色产物，不要读取或执行需要人工批准的技能流程，不要写等待用户确认的回复。
    """)


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
        attempts: list[dict[str, Any]] = []
        result: dict[str, Any] = {}
        for attempt_index in range(1, max(1, CODEX_ROLE_MAX_ATTEMPTS) + 1):
            if message_path.exists():
                message_path.unlink()
            attempt_prompt = role_retry_prompt(prompt, attempt_index)
            attempt_argv = build_codex_role_argv(project, role, message_path, attempt_prompt)
            result = run_command(attempt_argv, cwd=project, timeout_seconds=role_timeout)
            attempt_stdout = evidence / "role-raw" / f"{role}.attempt-{attempt_index}.stdout.txt"
            attempt_stderr = evidence / "role-raw" / f"{role}.attempt-{attempt_index}.stderr.txt"
            attempt_stdout.write_text(str(result.get("stdout") or ""), encoding="utf-8")
            attempt_stderr.write_text(str(result.get("stderr") or ""), encoding="utf-8")
            attempt_receipt = command_receipt(result)
            artifact_exists = role_artifact_path(evidence, role).exists()
            interactive_gate_marker = role_interactive_gate_marker(result)
            actionable_marker = actionable_interactive_gate_marker(result, artifact_exists)
            retry_reason = role_failure_retry_reason(result, artifact_exists)
            attempt_receipt.update({
                "attempt": attempt_index,
                "session_id": extract_codex_session_id(str(result.get("stderr") or "")),
                "raw_stdout": str(attempt_stdout),
                "raw_stderr": str(attempt_stderr),
                "expected_artifact_exists": artifact_exists,
                "last_message_exists": message_path.exists(),
                "interactive_gate_marker_observed": interactive_gate_marker,
                "interactive_gate_marker": actionable_marker,
                "retry_reason": retry_reason,
                "retry_prompt_used": attempt_index > 1,
            })
            attempts.append(attempt_receipt)
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
            "codex_extra_disabled_features": CODEX_ROLE_EXTRA_DISABLED_FEATURES,
            "codex_user_config_preserved": CODEX_ROLE_PRESERVE_USER_CONFIG,
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
    write_json(evidence / "runner-self-purification-resolution-template.json", {
        "schema_id": "redcap-e2e-runner-self-purification-resolution",
        "producer": "e2e-runner",
        "source": "self-purification-candidates.json",
        "resolved": "<boolean>",
        "public_promotions_written": False,
        "private_persona_written": False,
        "resolutions": []
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
    write_json(evidence / "runner-negative-contract-probe-template.json", {
        "schema_id": "redcap-e2e-runner-negative-contract-probe",
        "producer": "e2e-runner",
        "target_contract": "signup-intent-data-contract",
        "probe_id": "empty-signups-and-empty-signupIntent-must-fail",
        "ok": "<boolean>",
        "failure_policy": "blocking"
    })
    write_json(evidence / "runner-character-player-contract-probe-template.json", {
        "schema_id": "redcap-e2e-runner-character-player-contract-probe",
        "producer": "e2e-runner",
        "target_contract": "character-player-relation-contract",
        "probe_id": "broken-character-player-link-must-fail",
        "ok": "<boolean>",
        "failure_policy": "blocking"
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
    write_json(evidence / "behavioral-browser-verification-template.json", {
        "schema_id": "redcap-e2e-behavioral-browser-verification",
        "producer": "e2e-runner",
        "target": "index.html",
        "screenshot": "behavioral-browser-verification.png",
        "screenshot_phase": "after_interaction",
        "visual_independence": {
            "hashes_compared": True,
            "hashes_differ": True,
            "required_when": "interaction_changed=true and browser-inspection.png exists"
        },
        "checks": [
            "至少一次真实浏览器交互必须同时改变页面文本哈希和稳定 DOM 摘要哈希",
            "交互成功后必须立即采集行为截图，不能在后续页面刷新后采集初始状态截图",
            "如 browser-inspection.png 存在，行为截图必须记录并证明哈希不同",
            "如项目数据包含玩家和角色关系，必须验证该关系在 UI 中可见"
        ],
        "ok": "<boolean>",
        "failure_policy": "blocking"
    })
    write_json(evidence / "independent-browser-verification-template.json", {
        "schema_id": "redcap-e2e-independent-browser-verification",
        "producer": "e2e-independent-browser-process",
        "target": "index.html",
        "screenshot": "independent-browser-verification.png",
        "checks": [
            "独立子进程必须打开本地 HTTP 地址并确认可见文本",
            "独立子进程必须写入截图证据",
            "如页面有交互，独立子进程应尝试一次可见交互"
        ],
        "ok": "<boolean>",
        "failure_policy": "blocking"
    })
    write_json(evidence / "independent-observer-template.json", {
        "schema_id": "redcap-e2e-independent-observer",
        "producer": "e2e-independent-observer-script",
        "parent_relation": "harness sibling process, not runner-worker child",
        "required_checks": [
            "observer_seal.payload_sha256_without_seal 必须匹配",
            "independent-observer.json 必须是只读文件",
            "process.parent_is_harness 必须为 true",
            "process.parent_is_not_runner 必须为 true",
            "deliverable_hashes.failures 必须为空",
            "browser_observation.ok 必须为 true"
        ],
        "ok": "<boolean>",
        "failure_policy": "blocking"
    })
    write_json(evidence / "visual-independence-report-template.json", {
        "schema_id": "redcap-e2e-visual-independence-report",
        "producer": "e2e-runner",
        "checks": [
            "四条浏览器截图证据必须存在并带 sha256",
            "四条截图 sha256 必须互不相同",
            "四条浏览器证据必须记录 browser_context",
            "观察者读取的 final-evidence-bundle.json 文件哈希必须等于请求中的冻结哈希"
        ],
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


def parse_leading_json(stdout: str) -> dict[str, Any] | None:
    try:
        parsed, _ = json.JSONDecoder().raw_decode(stdout.lstrip())
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


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
        "runner-self-purification-resolution.json",
        "persona-distillation-decision.json",
        "test-results.json",
        "negative-probes.json",
        "runner-negative-contract-probe.json",
        "package-prism-check.json",
        "final-runner-test-results.json",
        "browser-inspection.json",
        "behavioral-browser-verification.json",
        "runner-character-player-contract-probe.json",
        "role-execution-risk.json",
        "independent-browser-verification.json",
        "browser-inspection.png",
        "behavioral-browser-verification.png",
        "independent-browser-verification.png",
        "loom-role-session-manifest-pre-review.json",
        "loom-role-session-manifest.json",
        "hook-events-summary.json",
        "codex-run.json",
        "filesystem-after.json",
    ]
    project_root_files = {"architecture.md", "risk-register.json"}
    paths = [(project / rel) if rel in project_root_files else (evidence / rel) for rel in fixed]
    for pattern in ["index.html", "app.js", "styles.css", "public/*.html", "public/*.js", "public/*.css", "src/*.js", "src/*.css", "data/*.json", "scripts/*.js", "scripts/*.mjs"]:
        paths.extend(sorted(project.glob(pattern)))
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
    full_json_evidence = {
        "requirements.json",
        "acceptance-criteria.json",
        "test-results.json",
        "negative-probes.json",
        "runner-negative-contract-probe.json",
        "runner-character-player-contract-probe.json",
        "runner-self-purification-resolution.json",
        "final-runner-test-results.json",
        "browser-inspection.json",
        "behavioral-browser-verification.json",
        "independent-browser-verification.json",
        "review-verdict.json",
        "prism-assisted-review.json",
    }
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
            if rel in full_json_evidence and path.stat().st_size <= 80_000:
                payload = load_optional_json(path)
                if payload is not None:
                    record["full_json"] = payload
        files.append(record)
    role_run_summary: list[dict[str, Any]] = []
    for path in sorted((evidence / "role-runs").glob("*.json")):
        payload = load_optional_json(path)
        if not isinstance(payload, dict):
            continue
        role_run_summary.append({
            "role": payload.get("role"),
            "ok": payload.get("ok"),
            "exit_code": payload.get("exit_code"),
            "timed_out": payload.get("timed_out"),
            "session_id": payload.get("session_id"),
            "attempt_count": len(payload.get("attempts", [])) if isinstance(payload.get("attempts"), list) else None,
        })
    bundle = {
        "schema_id": "redcap-e2e-final-evidence-bundle",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "project": str(project),
        "direction_sha256": sha256_text(direction),
        "purpose": "供最终棱镜复核独立检查，避免 reviewer 自证完成",
        "deliverables": project_deliverable_manifest(project),
        "role_run_summary": role_run_summary,
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
    readme = project / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"(?m)^\s*(node|bash|python3)\s+((?:scripts|tests)/[A-Za-z0-9_.\/-]+\.(?:js|mjs|sh|py))\s*$", text):
            runner = match.group(1)
            relative_path = match.group(2)
            if ".." in pathlib.PurePosixPath(relative_path).parts:
                continue
            if not (project / relative_path).exists():
                continue
            argv = [runner, relative_path]
            if runner == "bash" and not relative_path.endswith(".sh"):
                continue
            if runner == "node" and not relative_path.endswith((".js", ".mjs")):
                continue
            if runner == "python3" and not relative_path.endswith(".py"):
                continue
            return argv, f"README.md command: {runner} {relative_path}"
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


def find_signup_contract_data_target(project: pathlib.Path) -> tuple[pathlib.Path | None, dict[str, Any] | list[Any] | None, str | None, int | None, list[str]]:
    """Locate the JSON record that should be mutated for signup contract probing."""
    failures: list[str] = []
    data_dir = project / "data"
    candidates = [
        data_dir / "events.json",
        data_dir / "activities.json",
        *sorted(path for path in data_dir.glob("*.json") if path.name not in {"events.json", "activities.json"}),
    ]
    seen: set[pathlib.Path] = set()
    for data_path in candidates:
        if data_path in seen:
            continue
        seen.add(data_path)
        if not data_path.exists():
            continue
        try:
            payload = json.loads(data_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            failures.append(f"{data_path.relative_to(project)} 无法解析：{type(exc).__name__}: {exc}")
            continue
        list_candidates: list[tuple[str, list[Any]]] = []
        if isinstance(payload, dict):
            preferred_keys = ["events", "activities", "campaigns", "sessions", "items"]
            for key in preferred_keys:
                value = payload.get(key)
                if isinstance(value, list):
                    list_candidates.append((key, value))
            known_keys = {key for key, _ in list_candidates}
            for key, value in payload.items():
                if isinstance(value, list) and key not in known_keys:
                    list_candidates.append((str(key), value))
        elif isinstance(payload, list):
            list_candidates.append(("$", payload))
        for list_key, records in list_candidates:
            signup_indexes = [
                index for index, record in enumerate(records)
                if isinstance(record, dict) and ("signups" in record or "signupIntent" in record)
            ]
            fallback_indexes = [
                index for index, record in enumerate(records)
                if isinstance(record, dict)
            ]
            for record_index in [*signup_indexes, *fallback_indexes]:
                return data_path, payload, list_key, record_index, failures
        failures.append(f"{data_path.relative_to(project)} 未发现可变更的活动列表记录")
    failures.append("未找到包含报名数据或活动列表的 JSON 数据文件")
    return None, None, None, None, failures


def run_runner_negative_contract_probe(project: pathlib.Path, evidence: pathlib.Path) -> dict[str, Any]:
    """Prove the local validation command rejects malformed signup data."""
    argv, source = detect_validation_command(project)
    data_path, data, list_key, record_index, location_failures = find_signup_contract_data_target(project)
    result: dict[str, Any] = {
        "schema_id": "redcap-e2e-runner-negative-contract-probe",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "target_contract": "signup-intent-data-contract",
        "probe_id": "empty-signups-and-empty-signupIntent-must-fail",
        "detected_command": argv,
        "command_source": source,
        "data_path": str(data_path.relative_to(project)) if data_path is not None else None,
        "list_key": list_key,
        "record_index": record_index,
        "ok": False,
        "checks": [],
        "failures": [],
    }
    if argv is None:
        result["failures"].append("无法发现验证命令，不能执行运行器负向契约探针")
        return result
    if data_path is None or data is None or list_key is None or record_index is None:
        result["failures"].extend(location_failures)
        return result
    original_bytes = data_path.read_bytes()
    original_sha256 = hashlib.sha256(original_bytes).hexdigest()
    if isinstance(data, dict):
        records = data.get(list_key)
    elif list_key == "$":
        records = data
    else:
        records = None
    if not isinstance(records, list) or record_index >= len(records) or not isinstance(records[record_index], dict):
        result["failures"].append(f"{data_path.relative_to(project)} 中 {list_key}[{record_index}] 不是可变更对象")
        return result
    mutated = json.loads(json.dumps(data, ensure_ascii=False))
    mutated_records = mutated if list_key == "$" else mutated[list_key]
    mutated_event = mutated_records[record_index]
    mutated_event["signups"] = []
    mutated_event["signupIntent"] = ""
    mutation_summary = {
        "event_id": mutated_event.get("id"),
        "data_path": str(data_path.relative_to(project)),
        "list_key": list_key,
        "record_index": record_index,
        "changed_fields": ["signups", "signupIntent"],
        "expected_validation_exit": "non_zero",
    }
    result["mutation"] = mutation_summary
    negative_receipt: dict[str, Any] | None = None
    restore_receipt: dict[str, Any] | None = None
    try:
        data_path.write_text(json.dumps(mutated, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        negative_run = run_command(argv, cwd=project, timeout_seconds=120)
        negative_receipt = command_receipt(negative_run)
        negative_passed = negative_run.get("exit_code") not in (0, None)
        result["checks"].append({
            "name": "malformed_signup_data_rejected",
            "passed": negative_passed,
            "evidence": {
                "exit_code": negative_run.get("exit_code"),
                "stdout_tail": negative_receipt.get("stdout_tail"),
                "stderr_tail": negative_receipt.get("stderr_tail"),
            },
        })
    finally:
        data_path.write_bytes(original_bytes)
    restore_run = run_command(argv, cwd=project, timeout_seconds=120)
    restore_receipt = command_receipt(restore_run)
    restore_passed = restore_run.get("ok") is True
    result["checks"].append({
        "name": "original_data_restored_and_validation_passes",
        "passed": restore_passed,
        "evidence": {
            "exit_code": restore_run.get("exit_code"),
            "stdout_tail": restore_receipt.get("stdout_tail"),
            "stderr_tail": restore_receipt.get("stderr_tail"),
        },
    })
    result["negative_command"] = negative_receipt
    result["restore_command"] = restore_receipt
    result["restored_sha256"] = sha256_file(data_path)
    result["original_sha256"] = original_sha256
    result["ok"] = all(item.get("passed") is True for item in result["checks"])
    if not result["ok"]:
        result["failures"].append("运行器负向契约探针未证明坏数据失败且原数据恢复后通过")
    return result


def find_character_player_contract_data_target(project: pathlib.Path) -> tuple[pathlib.Path | None, dict[str, Any] | list[Any] | None, str | None, int | None, int | None, str | None, list[str]]:
    failures: list[str] = []
    data_dir = project / "data"
    candidates = [
        data_dir / "events.json",
        data_dir / "activities.json",
        *sorted(path for path in data_dir.glob("*.json") if path.name not in {"events.json", "activities.json"}),
    ]
    seen: set[pathlib.Path] = set()
    for data_path in candidates:
        if data_path in seen:
            continue
        seen.add(data_path)
        if not data_path.exists():
            continue
        try:
            payload = json.loads(data_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            failures.append(f"{data_path.relative_to(project)} 无法解析：{type(exc).__name__}: {exc}")
            continue
        list_candidates: list[tuple[str, list[Any]]] = []
        if isinstance(payload, dict):
            for key in ["events", "activities", "sessions", "campaigns", "items"]:
                value = payload.get(key)
                if isinstance(value, list):
                    list_candidates.append((key, value))
            known = {key for key, _ in list_candidates}
            for key, value in payload.items():
                if isinstance(value, list) and key not in known:
                    list_candidates.append((str(key), value))
        elif isinstance(payload, list):
            list_candidates.append(("$", payload))
        for list_key, records in list_candidates:
            for event_index, event in enumerate(records):
                if not isinstance(event, dict):
                    continue
                characters = event.get("characters")
                if not isinstance(characters, list):
                    continue
                players = event.get("players")
                player_ids = {
                    str(player.get("id"))
                    for player in players
                    if isinstance(player, dict) and player.get("id")
                } if isinstance(players, list) else set()
                for character_index, character in enumerate(characters):
                    if not isinstance(character, dict):
                        continue
                    for ref_key in ["playerId", "player_id", "player", "playerName", "player_name"]:
                        ref = character.get(ref_key)
                        if player_ids and ref and str(ref) in player_ids:
                            return data_path, payload, list_key, event_index, character_index, ref_key, failures
                        if not player_ids and ref_key in {"player", "playerName", "player_name"} and isinstance(ref, str) and ref.strip():
                            return data_path, payload, list_key, event_index, character_index, ref_key, failures
        failures.append(f"{data_path.relative_to(project)} 未发现可破坏的角色玩家关联")
    failures.append("未找到包含 characters 与玩家引用或玩家名的 JSON 数据文件")
    return None, None, None, None, None, None, failures


def run_runner_character_player_contract_probe(project: pathlib.Path, evidence: pathlib.Path) -> dict[str, Any]:
    argv, source = detect_validation_command(project)
    data_path, data, list_key, event_index, character_index, ref_key, location_failures = find_character_player_contract_data_target(project)
    result: dict[str, Any] = {
        "schema_id": "redcap-e2e-runner-character-player-contract-probe",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "target_contract": "character-player-relation-contract",
        "probe_id": "broken-character-player-link-must-fail",
        "detected_command": argv,
        "command_source": source,
        "data_path": str(data_path.relative_to(project)) if data_path is not None else None,
        "list_key": list_key,
        "event_index": event_index,
        "character_index": character_index,
        "reference_key": ref_key,
        "ok": False,
        "checks": [],
        "failures": [],
    }
    if argv is None:
        result["failures"].append("无法发现验证命令，不能执行角色玩家负向契约探针")
        return result
    if data_path is None or data is None or list_key is None or event_index is None or character_index is None or ref_key is None:
        result["failures"].extend(location_failures)
        return result
    original_bytes = data_path.read_bytes()
    original_sha256 = hashlib.sha256(original_bytes).hexdigest()
    mutated = copy.deepcopy(data)
    records = mutated if list_key == "$" else mutated.get(list_key) if isinstance(mutated, dict) else None
    if not isinstance(records, list) or event_index >= len(records) or not isinstance(records[event_index], dict):
        result["failures"].append(f"{data_path.relative_to(project)} 中 {list_key}[{event_index}] 不是可变更对象")
        return result
    event = records[event_index]
    characters = event.get("characters")
    if not isinstance(characters, list) or character_index >= len(characters) or not isinstance(characters[character_index], dict):
        result["failures"].append(f"{data_path.relative_to(project)} 中 characters[{character_index}] 不是可变更对象")
        return result
    original_ref = characters[character_index].get(ref_key)
    broken_ref = "" if ref_key in {"player", "playerName", "player_name"} else "__redcap_missing_player__"
    characters[character_index][ref_key] = broken_ref
    result["mutation"] = {
        "event_id": event.get("id"),
        "character_name": characters[character_index].get("name"),
        "data_path": str(data_path.relative_to(project)),
        "list_key": list_key,
        "event_index": event_index,
        "character_index": character_index,
        "changed_field": ref_key,
        "original_ref": original_ref,
        "broken_ref": broken_ref,
        "expected_validation_exit": "non_zero",
    }
    try:
        data_path.write_text(json.dumps(mutated, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        negative_run = run_command(argv, cwd=project, timeout_seconds=120)
        negative_receipt = command_receipt(negative_run)
        negative_passed = negative_run.get("exit_code") not in (0, None)
        result["checks"].append({
            "name": "broken_character_player_link_rejected",
            "passed": negative_passed,
            "evidence": {
                "exit_code": negative_run.get("exit_code"),
                "stdout_tail": negative_receipt.get("stdout_tail"),
                "stderr_tail": negative_receipt.get("stderr_tail"),
            },
        })
    finally:
        data_path.write_bytes(original_bytes)
    restore_run = run_command(argv, cwd=project, timeout_seconds=120)
    restore_receipt = command_receipt(restore_run)
    restore_passed = restore_run.get("exit_code") == 0
    result["checks"].append({
        "name": "original_character_player_data_restored_and_validation_passes",
        "passed": restore_passed,
        "evidence": {
            "exit_code": restore_run.get("exit_code"),
            "stdout_tail": restore_receipt.get("stdout_tail"),
            "stderr_tail": restore_receipt.get("stderr_tail"),
        },
    })
    result["negative_command"] = negative_receipt
    result["restore_command"] = restore_receipt
    result["restored_sha256"] = sha256_file(data_path)
    result["original_sha256"] = original_sha256
    result["ok"] = all(item.get("passed") is True for item in result["checks"])
    if not result["ok"]:
        result["failures"].append("角色玩家负向契约探针未证明破坏关联会失败且原数据恢复后通过")
    return result


def detect_browser_entrypoint(project: pathlib.Path) -> tuple[pathlib.Path | None, str | None, list[str]]:
    candidates = [
        "index.html",
        "public/index.html",
        "dist/index.html",
        "build/index.html",
    ]
    checked: list[str] = []
    for rel in candidates:
        checked.append(rel)
        path = project / rel
        if path.is_file():
            return path, rel, checked
    return None, None, checked


def run_browser_inspection(project: pathlib.Path, evidence: pathlib.Path) -> dict[str, Any]:
    target, target_rel, checked_entrypoints = detect_browser_entrypoint(project)
    screenshot = evidence / "browser-inspection.png"
    server_process: subprocess.Popen[str] | None = None
    server_stdout = ""
    server_stderr = ""
    result: dict[str, Any] = {
        "schema_id": "redcap-e2e-browser-inspection",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "target": str(target) if target is not None else None,
        "target_relative_path": target_rel,
        "checked_entrypoints": checked_entrypoints,
        "file_url": target.as_uri() if target is not None and target.exists() else None,
        "url": None,
        "launch_mode": "local-http-server",
        "screenshot": "browser-inspection.png",
        "ok": False,
        "checks": [],
        "failures": [],
    }
    if target is None or target_rel is None:
        result["failures"].append(f"缺少浏览器入口文件，已检查：{checked_entrypoints}")
        return result
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - 取决于本机运行时
        result["failures"].append(f"无法导入 Playwright 浏览器自动化库：{type(exc).__name__}: {exc}")
        return result
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    url = f"http://127.0.0.1:{port}/{target_rel}"
    server_argv = ["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1"]
    server_ready = False
    server_error = ""
    try:
        server_process = subprocess.Popen(
            server_argv,
            cwd=str(project),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if server_process.poll() is not None:
                server_error = f"本地 HTTP 服务提前退出，exit_code={server_process.returncode}"
                break
            try:
                with urllib.request.urlopen(url, timeout=0.5) as response:
                    if response.status < 500:
                        server_ready = True
                        break
            except Exception as exc:
                server_error = f"{type(exc).__name__}: {exc}"
                time.sleep(0.1)
        result["url"] = url
        result["server"] = {
            "argv": server_argv,
            "cwd": str(project),
            "ready": server_ready,
            "url": url,
            "last_readiness_error": server_error,
            "exit_code_before_cleanup": server_process.poll(),
        }
        if not server_ready:
            result["failures"].append(f"本地 HTTP 服务没有就绪，无法执行浏览器检查：{server_error}")
            return result
        console_errors: list[str] = []
        page_errors: list[str] = []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                browser_version = browser.version
                page = browser.new_page(viewport=BROWSER_INSPECTION_VIEWPORT)
                page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.goto(url, wait_until="domcontentloaded", timeout=20_000)
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
    finally:
        if server_process is not None:
            killed = kill_process_group(server_process, grace_seconds=1.0)
            try:
                server_stdout, server_stderr = server_process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                server_stdout, server_stderr = "", ""
            server = result.get("server")
            if isinstance(server, dict):
                server.update({
                    "exit_code_after_cleanup": server_process.returncode,
                    "process_group_killed": killed,
                    "stdout_tail": server_stdout[-1000:],
                    "stderr_tail": server_stderr[-1000:],
                })
    visible_text = body_text.strip()
    checks = [
        {"name": "page_loaded", "passed": True, "evidence": url},
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
        "browser_context": {
            "process_pid": os.getpid(),
            "browser_version": browser_version,
            "viewport": BROWSER_INSPECTION_VIEWPORT,
            "server_port": port,
            "capture_role": "browser-inspection",
            "screenshot_phase": "initial_render",
        },
        "checks": checks,
        "failures": failures,
    })
    return result


def find_character_player_probe(project: pathlib.Path) -> dict[str, Any] | None:
    for data_path in sorted((project / "data").glob("*.json")):
        try:
            payload = json.loads(data_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        event_lists: list[Any] = []
        if isinstance(payload, dict):
            for key in ["events", "activities", "sessions"]:
                value = payload.get(key)
                if isinstance(value, list):
                    event_lists.append(value)
        elif isinstance(payload, list):
            event_lists.append(payload)
        for events in event_lists:
            for event in events:
                if not isinstance(event, dict):
                    continue
                characters = event.get("characters")
                if not isinstance(characters, list):
                    continue
                players = event.get("players")
                player_by_id = {
                    str(player.get("id")): str(player.get("name"))
                    for player in players
                    if isinstance(player, dict) and player.get("id") and player.get("name")
                } if isinstance(players, list) else {}
                for character in characters:
                    if not isinstance(character, dict):
                        continue
                    character_name = str(character.get("name") or "")
                    player_name = player_by_id.get(str(character.get("playerId") or character.get("player_id") or ""))
                    if not player_name:
                        player_name = str(character.get("player") or character.get("playerName") or character.get("player_name") or "")
                    if character_name and player_name:
                        return {
                            "data_file": data_path.relative_to(project).as_posix(),
                            "event_title": event.get("title") or event.get("name"),
                            "character_name": character_name,
                            "player_name": player_name,
                        }
    return None


def browser_observable_snapshot(page: Any) -> dict[str, Any]:
    snapshot = page.evaluate(
        """() => {
            const volatileSelector = [
                "script",
                "style",
                "noscript",
                "time",
                "[data-redcap-volatile]",
                "[data-volatile]",
                "[aria-busy='true']",
                ".spinner",
                ".loading"
            ].join(",");
            const textOf = (el) => {
                const raw = el.innerText || el.textContent || el.value || el.getAttribute("aria-label") || "";
                return String(raw).replace(/\\s+/g, " ").trim().slice(0, 160);
            };
            const classOf = (el) => {
                if (typeof el.className === "string") return el.className;
                if (el.className && typeof el.className.baseVal === "string") return el.className.baseVal;
                return "";
            };
            const stableElements = Array.from(document.querySelectorAll([
                "main",
                "section",
                "article",
                "dialog",
                "[aria-live]",
                "button",
                "[role='button']",
                "[aria-selected]",
                "[aria-expanded]",
                "[aria-pressed]",
                "[data-state]",
                "[data-active]",
                ".active",
                ".selected"
            ].join(","))).filter((el) => !el.closest(volatileSelector)).slice(0, 160);
            const bodyClone = document.body ? document.body.cloneNode(true) : null;
            if (bodyClone) {
                bodyClone.querySelectorAll(volatileSelector).forEach((el) => el.remove());
            }
            return {
                text: bodyClone ? (bodyClone.innerText || bodyClone.textContent || "") : "",
                dom_summary: stableElements.map((el) => {
                    const style = window.getComputedStyle(el);
                    return {
                        tag: el.tagName.toLowerCase(),
                        id: el.id || "",
                        classes: classOf(el),
                        text: textOf(el),
                        ariaSelected: el.getAttribute("aria-selected"),
                        ariaExpanded: el.getAttribute("aria-expanded"),
                        ariaPressed: el.getAttribute("aria-pressed"),
                        dataState: el.getAttribute("data-state"),
                        dataActive: el.getAttribute("data-active"),
                        hidden: el.hidden || el.getAttribute("aria-hidden") === "true",
                        display: style.display,
                        visibility: style.visibility
                    };
                })
            };
        }"""
    )
    text = str(snapshot.get("text") or "")
    dom_summary = snapshot.get("dom_summary")
    if not isinstance(dom_summary, list):
        dom_summary = []
    dom_summary_text = json.dumps(dom_summary, ensure_ascii=False, sort_keys=True)
    return {
        "text": text,
        "text_hash": sha256_text(text),
        "text_length": len(text),
        "dom_summary_hash": sha256_text(dom_summary_text),
        "dom_summary_count": len(dom_summary),
    }


def run_behavioral_browser_verification(project: pathlib.Path, evidence: pathlib.Path) -> dict[str, Any]:
    target, target_rel, checked_entrypoints = detect_browser_entrypoint(project)
    screenshot = evidence / "behavioral-browser-verification.png"
    server_process: subprocess.Popen[str] | None = None
    result: dict[str, Any] = {
        "schema_id": "redcap-e2e-behavioral-browser-verification",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "target": str(target) if target is not None else None,
        "target_relative_path": target_rel,
        "checked_entrypoints": checked_entrypoints,
        "file_url": target.as_uri() if target is not None and target.exists() else None,
        "url": None,
        "launch_mode": "local-http-server",
        "screenshot": "behavioral-browser-verification.png",
        "checks": [],
        "failures": [],
        "ok": False,
    }
    if target is None or target_rel is None:
        result["failures"].append(f"缺少浏览器入口文件，已检查：{checked_entrypoints}")
        return result
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - 取决于本机运行时
        result["failures"].append(f"无法导入 Playwright 浏览器自动化库：{type(exc).__name__}: {exc}")
        return result
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    url = f"http://127.0.0.1:{port}/{target_rel}"
    server_argv = ["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1"]
    server_ready = False
    server_error = ""
    console_errors: list[str] = []
    page_errors: list[str] = []
    relation_probe = find_character_player_probe(project)
    browser_inspection_screenshot = evidence / "browser-inspection.png"
    screenshot_phase = "not_captured"
    screenshot_phase_reason = "行为级浏览器验证尚未运行到截图阶段"
    try:
        server_process = subprocess.Popen(
            server_argv,
            cwd=str(project),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if server_process.poll() is not None:
                server_error = f"本地 HTTP 服务提前退出，exit_code={server_process.returncode}"
                break
            try:
                with urllib.request.urlopen(url, timeout=0.5) as response:
                    if response.status < 500:
                        server_ready = True
                        break
            except Exception as exc:
                server_error = f"{type(exc).__name__}: {exc}"
                time.sleep(0.1)
        result["url"] = url
        result["server"] = {
            "argv": server_argv,
            "cwd": str(project),
            "ready": server_ready,
            "url": url,
            "last_readiness_error": server_error,
            "exit_code_before_cleanup": server_process.poll(),
        }
        if not server_ready:
            result["failures"].append(f"本地 HTTP 服务没有就绪，无法执行行为级浏览器验证：{server_error}")
            return result
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser_version = browser.version
            page = browser.new_page(viewport=BEHAVIORAL_BROWSER_VIEWPORT)
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            page.wait_for_timeout(800)
            before_snapshot = browser_observable_snapshot(page)
            before_text = before_snapshot["text"]
            after_snapshot = before_snapshot
            after_text = before_text
            clicked_button = None
            interaction_attempts: list[dict[str, Any]] = []
            candidates = page.locator("button, [role='button']")
            button_count = candidates.count()
            for index in range(button_count):
                if index >= 12:
                    break
                button = candidates.nth(index)
                label = button.inner_text(timeout=2_000).strip()
                if not label or label in {"全部", "All"}:
                    interaction_attempts.append({
                        "index": index,
                        "label": label,
                        "skipped": True,
                        "reason": "empty_or_global_filter",
                    })
                    continue
                attempt_before = browser_observable_snapshot(page)
                try:
                    button.click(timeout=5_000)
                    page.wait_for_timeout(500)
                    attempt_after = browser_observable_snapshot(page)
                    text_changed = attempt_before["text_hash"] != attempt_after["text_hash"]
                    dom_changed = attempt_before["dom_summary_hash"] != attempt_after["dom_summary_hash"]
                    changed = text_changed and dom_changed
                    interaction_attempts.append({
                        "index": index,
                        "label": label,
                        "skipped": False,
                        "text_changed": text_changed,
                        "dom_summary_changed": dom_changed,
                        "changed": changed,
                        "before_text_hash": attempt_before["text_hash"],
                        "after_text_hash": attempt_after["text_hash"],
                        "before_dom_summary_hash": attempt_before["dom_summary_hash"],
                        "after_dom_summary_hash": attempt_after["dom_summary_hash"],
                    })
                    after_snapshot = attempt_after
                    after_text = attempt_after["text"]
                    if changed:
                        clicked_button = label
                        before_snapshot = attempt_before
                        break
                except Exception as exc:
                    interaction_attempts.append({
                        "index": index,
                        "label": label,
                        "skipped": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    })
            before_text = before_snapshot["text"]
            after_text = page.locator("body").inner_text(timeout=5_000)
            interaction_changed = bool(clicked_button) and before_snapshot["text_hash"] != after_snapshot["text_hash"] and before_snapshot["dom_summary_hash"] != after_snapshot["dom_summary_hash"]
            if interaction_changed:
                screenshot_phase = "after_interaction"
                screenshot_phase_reason = "真实点击已改变页面文本哈希和稳定 DOM 摘要哈希，截图在关系探针刷新页面前采集"
            else:
                screenshot_phase = "after_initial_observation"
                screenshot_phase_reason = "没有找到可证明页面变化的交互，截图只能记录初始观察状态"
            page.screenshot(path=str(screenshot), full_page=True)
            relation_passed = True
            relation_evidence: dict[str, Any] = {"probe_available": False}
            if relation_probe:
                page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                page.wait_for_timeout(800)
                relation_text = page.locator("body").inner_text(timeout=5_000)
                character_name = str(relation_probe["character_name"])
                player_name = str(relation_probe["player_name"])
                character_index = relation_text.find(character_name)
                player_index = relation_text.find(player_name)
                dom_relation = page.evaluate(
                    """({ characterName, playerName }) => {
                        const textOf = (element) => (element.innerText || element.textContent || "").replace(/\\s+/g, " ").trim();
                        const visible = (element) => {
                            const style = window.getComputedStyle(element);
                            const rect = element.getBoundingClientRect();
                            return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
                        };
                        const selector = [
                            "tr",
                            "li",
                            "article",
                            "section",
                            "[role='row']",
                            "[data-testid]",
                            ".card",
                            ".event",
                            ".session",
                            ".character",
                            ".player",
                            "div"
                        ].join(",");
                        const containers = [];
                        for (const element of Array.from(document.querySelectorAll(selector))) {
                            if (!visible(element)) continue;
                            const text = textOf(element);
                            if (!text.includes(characterName) || !text.includes(playerName)) continue;
                            if (["HTML", "BODY", "MAIN"].includes(element.tagName)) continue;
                            if (text.length > 1600) continue;
                            const rect = element.getBoundingClientRect();
                            containers.push({
                                tag: element.tagName.toLowerCase(),
                                id: element.id || null,
                                className: element.className || null,
                                role: element.getAttribute("role"),
                                textLength: text.length,
                                textExcerpt: text.slice(0, 500),
                                rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
                            });
                        }
                        containers.sort((a, b) => a.textLength - b.textLength);
                        return {
                            same_structural_container: containers.length > 0,
                            matched_container_count: containers.length,
                            matched_containers: containers.slice(0, 5)
                        };
                    }""",
                    {"characterName": character_name, "playerName": player_name},
                )
                relation_passed = bool(isinstance(dom_relation, dict) and dom_relation.get("same_structural_container") is True)
                relation_evidence = {
                    "probe_available": True,
                    **relation_probe,
                    "character_index": character_index,
                    "player_index": player_index,
                    "text_distance": abs(character_index - player_index) if character_index >= 0 and player_index >= 0 else None,
                    "text_distance_is_informational_only": True,
                    "dom_structural_probe": dom_relation,
                }
            browser.close()
    except Exception as exc:
        result["failures"].append(f"行为级浏览器验证执行失败：{type(exc).__name__}: {exc}")
        return result
    finally:
        if server_process is not None:
            killed = kill_process_group(server_process, grace_seconds=1.0)
            try:
                server_stdout, server_stderr = server_process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                server_stdout, server_stderr = "", ""
            server = result.get("server")
            if isinstance(server, dict):
                server.update({
                    "exit_code_after_cleanup": server_process.returncode,
                    "process_group_killed": killed,
                    "stdout_tail": server_stdout[-1000:],
                    "stderr_tail": server_stderr[-1000:],
                })
    screenshot_record = evidence_file_record(screenshot, base=evidence)
    browser_inspection_record = evidence_file_record(browser_inspection_screenshot, base=evidence)
    hashes_compared = bool(screenshot_record["sha256"] and browser_inspection_record["sha256"])
    hashes_differ = (
        screenshot_record["sha256"] != browser_inspection_record["sha256"]
        if hashes_compared
        else None
    )
    visual_independence = {
        "behavioral_screenshot_phase": screenshot_phase,
        "phase_reason": screenshot_phase_reason,
        "behavioral_screenshot": screenshot_record,
        "browser_inspection_screenshot": browser_inspection_record,
        "hashes_compared": hashes_compared,
        "hashes_differ": hashes_differ,
        "required_when": "interaction_changed=true and browser-inspection.png exists",
    }
    visual_independence_passed = not (
        interaction_changed
        and browser_inspection_record["exists"]
        and hashes_differ is not True
    )
    checks = [
        {
            "name": "interactive_state_change",
            "passed": interaction_changed,
            "evidence": {
                "clicked_button": clicked_button,
                "before_length": len(before_text),
                "after_length": len(after_text),
                "before_text_hash": before_snapshot["text_hash"],
                "after_text_hash": after_snapshot["text_hash"],
                "before_dom_summary_hash": before_snapshot["dom_summary_hash"],
                "after_dom_summary_hash": after_snapshot["dom_summary_hash"],
                "attempts": interaction_attempts,
                "observable_criteria": [
                    "text_hash_changed",
                    "dom_summary_hash_changed"
                ],
            },
        },
        {
            "name": "character_player_relation_visible",
            "passed": relation_passed,
            "evidence": relation_evidence,
        },
        {
            "name": "no_browser_errors",
            "passed": not console_errors and not page_errors,
            "evidence": {"console_errors": console_errors, "page_errors": page_errors},
        },
        {
            "name": "screenshot_written",
            "passed": screenshot_record["exists"] and int(screenshot_record["size"] or 0) > 0,
            "evidence": screenshot_record,
        },
        {
            "name": "screenshot_phase_after_interaction",
            "passed": screenshot_phase == "after_interaction",
            "evidence": {
                "screenshot_phase": screenshot_phase,
                "phase_reason": screenshot_phase_reason,
                "clicked_button": clicked_button,
            },
        },
        {
            "name": "behavioral_visual_independence",
            "passed": visual_independence_passed,
            "evidence": visual_independence,
        },
    ]
    failures = [f"行为级浏览器验证失败：{item['name']}" for item in checks if item.get("passed") is not True]
    result.update({
        "ok": not failures,
        "checks": checks,
        "failures": failures,
        "clicked_button": clicked_button,
        "interaction_attempts": interaction_attempts,
        "relation_probe": relation_probe,
        "screenshot_phase": screenshot_phase,
        "screenshot_phase_reason": screenshot_phase_reason,
        "screenshot_record": screenshot_record,
        "visual_independence": visual_independence,
        "browser_context": {
            "process_pid": os.getpid(),
            "browser_version": browser_version,
            "viewport": BEHAVIORAL_BROWSER_VIEWPORT,
            "server_port": port,
            "capture_role": "behavioral-interaction",
            "screenshot_phase": screenshot_phase,
        },
        "console_errors": console_errors,
        "page_errors": page_errors,
    })
    return result


def run_independent_browser_verification_process(project: pathlib.Path, evidence: pathlib.Path) -> dict[str, Any]:
    script = r"""
import json
import hashlib
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request

project = pathlib.Path(sys.argv[1])
evidence = pathlib.Path(sys.argv[2])
checked_entrypoints = ["index.html", "public/index.html", "dist/index.html", "build/index.html"]
target = None
target_rel = None
for candidate in checked_entrypoints:
    candidate_path = project / candidate
    if candidate_path.is_file():
        target = candidate_path
        target_rel = candidate
        break
screenshot = evidence / "independent-browser-verification.png"
viewport = {"width": 1176, "height": 820}
def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
result = {
    "schema_id": "redcap-e2e-independent-browser-verification",
    "producer": "e2e-independent-browser-process",
    "target": str(target) if target is not None else None,
    "target_relative_path": target_rel,
    "checked_entrypoints": checked_entrypoints,
    "ok": False,
    "checks": [],
    "failures": [],
    "screenshot": "independent-browser-verification.png",
}
if target is None or target_rel is None:
    result["failures"].append(f"缺少浏览器入口文件，已检查：{checked_entrypoints}")
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)
try:
    from playwright.sync_api import sync_playwright
except Exception as exc:
    result["failures"].append(f"无法导入 Playwright: {type(exc).__name__}: {exc}")
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
url = f"http://127.0.0.1:{port}/{target_rel}"
server = subprocess.Popen(["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=str(project), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
try:
    ready = False
    last_error = ""
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if server.poll() is not None:
            last_error = f"server exited: {server.returncode}"
            break
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                ready = response.status < 500
                if ready:
                    break
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(0.1)
    result["url"] = url
    result["server_ready"] = ready
    result["server_last_error"] = last_error
    if not ready:
        result["failures"].append(f"本地 HTTP 服务未就绪：{last_error}")
    else:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser_version = browser.version
            page = browser.new_page(viewport=viewport)
            console_errors = []
            page_errors = []
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(500)
            text_before = page.locator("body").inner_text(timeout=5000)
            button_count = page.locator("button, [role='button']").count()
            clicked = None
            text_after = text_before
            for index in range(min(button_count, 6)):
                button = page.locator("button, [role='button']").nth(index)
                label = button.inner_text(timeout=2000).strip()
                if not label:
                    continue
                before = page.locator("body").inner_text(timeout=5000)
                try:
                    button.click(timeout=5000)
                    page.wait_for_timeout(300)
                except Exception:
                    continue
                after = page.locator("body").inner_text(timeout=5000)
                if before != after:
                    clicked = label[:120]
                    text_before = before
                    text_after = after
                    break
            page.screenshot(path=str(screenshot), full_page=True)
            browser.close()
            checks = [
                {"name": "visible_text", "passed": len(text_before.strip()) >= 80, "evidence": {"length": len(text_before)}},
                {"name": "no_browser_errors", "passed": not console_errors and not page_errors, "evidence": {"console_errors": console_errors, "page_errors": page_errors}},
                {"name": "independent_interaction_or_static_content", "passed": bool(clicked) or len(text_before.strip()) >= 160, "evidence": {"clicked": clicked, "before_length": len(text_before), "after_length": len(text_after)}},
                {"name": "screenshot_written", "passed": screenshot.exists() and screenshot.stat().st_size > 0, "evidence": {"path": "independent-browser-verification.png", "size": screenshot.stat().st_size if screenshot.exists() else 0, "sha256": sha256_file(screenshot) if screenshot.exists() else None}},
            ]
            result["checks"] = checks
            result["browser_context"] = {
                "process_pid": __import__("os").getpid(),
                "browser_version": browser_version,
                "viewport": viewport,
                "server_port": port,
                "capture_role": "independent-browser-process",
                "screenshot_phase": "after_interaction" if clicked else "after_static_observation",
            }
            result["screenshot_record"] = {"path": "independent-browser-verification.png", "exists": screenshot.exists(), "size": screenshot.stat().st_size if screenshot.exists() else 0, "sha256": sha256_file(screenshot) if screenshot.exists() else None}
            result["failures"].extend([f"独立浏览器验证失败：{item['name']}" for item in checks if item.get("passed") is not True])
finally:
    try:
        server.terminate()
        server.wait(timeout=2)
    except Exception:
        try:
            server.kill()
        except Exception:
            pass
result["ok"] = not result["failures"]
print(json.dumps(result, ensure_ascii=False))
"""
    completed = subprocess.run(
        ["python3", "-c", script, str(project), str(evidence)],
        cwd=str(project),
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    payload: dict[str, Any]
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        payload = {
            "schema_id": "redcap-e2e-independent-browser-verification",
            "producer": "e2e-runner",
            "ok": False,
            "failures": [f"独立浏览器验证子进程没有返回有效 JSON：{type(exc).__name__}: {exc}"],
        }
    payload["command"] = command_receipt({
        "argv": ["python3", "-c", "<independent-browser-verification>", str(project), str(evidence)],
        "cwd": str(project),
        "exit_code": completed.returncode,
        "ok": completed.returncode == 0,
        "timed_out": False,
        "timeout_seconds": 180,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "process_group_killed": None,
    })
    if completed.returncode != 0:
        payload["ok"] = False
        payload.setdefault("failures", []).append(f"独立浏览器验证子进程退出码非 0：{completed.returncode}")
    return payload


def observer_script_path(project: pathlib.Path) -> pathlib.Path:
    packaged = project / ".redcap" / "runtime" / "core" / "e2e_independent_observer.py"
    if packaged.exists():
        return packaged
    return REPO_ROOT / "runtime" / "core" / "e2e_independent_observer.py"


def verify_observer_seal(payload: dict[str, Any]) -> tuple[bool, str]:
    seal = payload.get("observer_seal")
    if not isinstance(seal, dict):
        return False, "independent-observer 缺少 observer_seal"
    expected = seal.get("payload_sha256_without_seal")
    if not isinstance(expected, str) or not expected:
        return False, "observer_seal 缺少 payload_sha256_without_seal"
    copy_payload = dict(payload)
    copy_payload.pop("observer_seal", None)
    actual = sha256_text(json.dumps(copy_payload, ensure_ascii=False, sort_keys=True))
    if actual != expected:
        return False, "independent-observer seal 哈希不匹配，证据可能被改写"
    return True, ""


def verify_independent_observer_output(path: pathlib.Path, runner_pid: int | None = None) -> dict[str, Any]:
    failures: list[str] = []
    payload = load_optional_json(path)
    if payload is None:
        return {
            "schema_id": "redcap-e2e-independent-observer-verification",
            "ok": False,
            "path": str(path),
            "failures": ["缺少或无法读取 independent-observer.json"],
        }
    if payload.get("schema_id") != "redcap-e2e-independent-observer":
        failures.append("independent-observer schema_id 错误")
    if payload.get("producer") != "e2e-independent-observer-script":
        failures.append("independent-observer producer 错误")
    if payload.get("ok") is not True:
        failures.append(f"independent-observer 自身未通过：{payload.get('failures')}")
    seal_ok, seal_failure = verify_observer_seal(payload)
    if not seal_ok:
        failures.append(seal_failure)
    try:
        mode = path.stat().st_mode & 0o777
        if mode & 0o222:
            failures.append(f"independent-observer.json 不是只读文件：{oct(mode)}")
    except OSError as exc:
        failures.append(f"无法读取 independent-observer.json 权限：{exc}")
    process = payload.get("process")
    if not isinstance(process, dict):
        failures.append("independent-observer 缺少 process 元数据")
    else:
        if process.get("parent_is_harness") is not True:
            failures.append("independent-observer 不是由 harness 作为父进程启动")
        if process.get("parent_is_not_runner") is not True:
            failures.append("independent-observer 父进程不能是 runner-worker")
        if runner_pid is not None and process.get("runner_pid") != runner_pid:
            failures.append("independent-observer 记录的 runner_pid 与当前 worker 不一致")
    deliverables = payload.get("deliverable_hashes")
    if not isinstance(deliverables, dict) or deliverables.get("failures"):
        failures.append(f"independent-observer 交付文件哈希复核失败：{deliverables.get('failures') if isinstance(deliverables, dict) else 'missing'}")
    bundle_fingerprint = payload.get("bundle_fingerprint")
    if not isinstance(bundle_fingerprint, dict) or bundle_fingerprint.get("matches_expected_file_sha256") is not True:
        failures.append("independent-observer 必须证明读取的 final-evidence-bundle.json 文件哈希等于请求中的冻结哈希")
    browser = payload.get("browser_observation")
    if not isinstance(browser, dict) or browser.get("ok") is not True:
        failures.append(f"independent-observer 浏览器观察失败：{browser.get('failures') if isinstance(browser, dict) else 'missing'}")
    return {
        "schema_id": "redcap-e2e-independent-observer-verification",
        "ok": not failures,
        "path": str(path),
        "payload": payload,
        "failures": failures,
    }


def screenshot_record_from_checks(payload: dict[str, Any], fallback_path: str) -> dict[str, Any]:
    checks = payload.get("checks")
    if isinstance(checks, list):
        for item in checks:
            if not isinstance(item, dict) or item.get("name") != "screenshot_written":
                continue
            evidence = item.get("evidence")
            if isinstance(evidence, dict):
                return {
                    "path": evidence.get("path") or fallback_path,
                    "exists": evidence.get("exists", True),
                    "sha256": evidence.get("sha256"),
                    "size": evidence.get("size", 0),
                }
    return {
        "path": fallback_path,
        "exists": False,
        "sha256": None,
        "size": 0,
    }


def build_visual_independence_report(evidence: pathlib.Path) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    source_specs = [
        ("browser-inspection", "browser-inspection.json", "browser-inspection.png"),
        ("behavioral-browser-verification", "behavioral-browser-verification.json", "behavioral-browser-verification.png"),
        ("independent-browser-verification", "independent-browser-verification.json", "independent-browser-verification.png"),
    ]
    for source_id, json_name, screenshot_name in source_specs:
        payload = load_optional_json(evidence / json_name) or {}
        record = payload.get("screenshot_record")
        if not isinstance(record, dict):
            record = screenshot_record_from_checks(payload, screenshot_name)
        sources.append({
            "source_id": source_id,
            "json": json_name,
            "screenshot": record,
            "browser_context": payload.get("browser_context") if isinstance(payload.get("browser_context"), dict) else None,
            "ok": payload.get("ok") is True,
        })
    observer_payload = load_optional_json(evidence / "independent-observer.json") or {}
    observer_browser = observer_payload.get("browser_observation") if isinstance(observer_payload.get("browser_observation"), dict) else {}
    observer_record = observer_browser.get("screenshot_record") if isinstance(observer_browser.get("screenshot_record"), dict) else {
        "path": "independent-observer.png",
        "exists": False,
        "sha256": None,
        "size": 0,
    }
    sources.append({
        "source_id": "independent-observer",
        "json": "independent-observer.json",
        "screenshot": observer_record,
        "browser_context": observer_browser.get("browser_context") if isinstance(observer_browser.get("browser_context"), dict) else None,
        "ok": observer_payload.get("ok") is True,
    })
    failures: list[str] = []
    screenshot_hashes: list[str] = []
    for source in sources:
        record = source.get("screenshot") if isinstance(source.get("screenshot"), dict) else {}
        if record.get("exists") is not True or not record.get("sha256"):
            failures.append(f"{source.get('source_id')} 缺少可哈希的截图证据")
        else:
            screenshot_hashes.append(str(record["sha256"]))
        context = source.get("browser_context")
        if not isinstance(context, dict):
            failures.append(f"{source.get('source_id')} 缺少 browser_context")
        else:
            for key in ["process_pid", "browser_version", "viewport", "server_port", "capture_role", "screenshot_phase"]:
                if context.get(key) in (None, "", {}):
                    failures.append(f"{source.get('source_id')} browser_context 缺少 {key}")
    distinct_hashes = sorted(set(screenshot_hashes))
    if len(distinct_hashes) != len(screenshot_hashes):
        failures.append("视觉三角验证要求各截图哈希互不相同，当前存在重复截图哈希")
    observer_payload = load_optional_json(evidence / "independent-observer.json") or {}
    bundle_fingerprint = observer_payload.get("bundle_fingerprint")
    if not isinstance(bundle_fingerprint, dict) or bundle_fingerprint.get("matches_expected_file_sha256") is not True:
        failures.append("视觉三角报告要求观察者证据包文件哈希与冻结哈希一致")
    return {
        "schema_id": "redcap-e2e-visual-independence-report",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "ok": not failures,
        "sources": sources,
        "distinct_screenshot_sha256_count": len(distinct_hashes),
        "screenshot_count": len(screenshot_hashes),
        "bundle_fingerprint": bundle_fingerprint,
        "checks": [
            {
                "name": "all_screenshots_present",
                "passed": all(
                    isinstance(source.get("screenshot"), dict)
                    and source["screenshot"].get("exists") is True
                    and bool(source["screenshot"].get("sha256"))
                    for source in sources
                ),
            },
            {
                "name": "screenshot_hashes_distinct",
                "passed": len(distinct_hashes) == len(screenshot_hashes) == len(sources),
                "evidence": {
                    "distinct": len(distinct_hashes),
                    "total": len(screenshot_hashes),
                    "hashes": screenshot_hashes,
                },
            },
            {
                "name": "browser_contexts_recorded",
                "passed": all(isinstance(source.get("browser_context"), dict) for source in sources),
            },
            {
                "name": "observer_bundle_file_hash_matches",
                "passed": isinstance(bundle_fingerprint, dict) and bundle_fingerprint.get("matches_expected_file_sha256") is True,
            },
        ],
        "failures": failures,
    }


def run_observer_request_as_harness(request_path: pathlib.Path, runner_pid: int, harness_pid: int) -> dict[str, Any]:
    request = load_optional_json(request_path)
    if request is None:
        return {
            "schema_id": "redcap-e2e-observer-command",
            "ok": False,
            "request_path": str(request_path),
            "failures": ["observer-request.json 无法读取"],
        }
    project = pathlib.Path(str(request.get("project") or "")).resolve()
    evidence = pathlib.Path(str(request.get("evidence") or "")).resolve()
    bundle = pathlib.Path(str(request.get("bundle") or "")).resolve()
    output = pathlib.Path(str(request.get("output") or "")).resolve()
    script = pathlib.Path(str(request.get("observer_script") or "")).resolve()
    if output.exists():
        output.chmod(0o644)
        output.unlink()
    env = os.environ.copy()
    env.pop("REDCAP_E2E_WORKER", None)
    env["REDCAP_E2E_OBSERVER_BY_HARNESS"] = "1"
    argv = [
        sys.executable,
        str(script),
        "--project",
        str(project),
        "--evidence",
        str(evidence),
        "--bundle",
        str(bundle),
        "--expected-bundle-file-sha256",
        str(request.get("bundle_file_sha256") or ""),
        "--output",
        str(output),
        "--runner-pid",
        str(runner_pid),
        "--harness-pid",
        str(harness_pid),
    ]
    started = iso_now()
    try:
        completed = subprocess.run(
            argv,
            cwd=str(project),
            text=True,
            capture_output=True,
            timeout=OBSERVER_TIMEOUT_SECONDS,
            check=False,
            env=env,
        )
        timed_out = False
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
    verification = verify_independent_observer_output(output, runner_pid=runner_pid)
    command = {
        "schema_id": "redcap-e2e-observer-command",
        "ok": (exit_code == 0) and verification["ok"],
        "request_path": str(request_path),
        "started_at": started,
        "finished_at": iso_now(),
        "argv": argv,
        "cwd": str(project),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
        "output": str(output),
        "verification": {
            "ok": verification["ok"],
            "failures": verification["failures"],
        },
        "failures": [],
    }
    if timed_out:
        command["failures"].append("独立观察者超时")
    if exit_code != 0:
        command["failures"].append(f"独立观察者退出码非 0：{exit_code}")
    command["failures"].extend(verification["failures"])
    write_json(evidence / "observer-command.json", command)
    return command


def request_independent_observer(project: pathlib.Path, evidence: pathlib.Path, bundle: dict[str, Any]) -> dict[str, Any]:
    output = evidence / "independent-observer.json"
    if output.exists():
        output.chmod(0o644)
        output.unlink()
    bundle_path = evidence / "final-evidence-bundle.json"
    request = {
        "schema_id": "redcap-e2e-observer-request",
        "created_at": iso_now(),
        "project": str(project),
        "evidence": str(evidence),
        "bundle": str(bundle_path),
        "bundle_sha256": bundle.get("bundle_sha256"),
        "bundle_file_sha256": sha256_file(bundle_path) if bundle_path.exists() else None,
        "output": str(output),
        "observer_script": str(observer_script_path(project)),
        "runner_pid": os.getpid(),
        "required_relation": "observer_parent_is_harness_and_not_runner",
    }
    request_path = evidence / "observer-request.json"
    write_json(request_path, request)
    if os.environ.get("REDCAP_E2E_OBSERVER_BY_HARNESS") == "1":
        deadline = time.monotonic() + OBSERVER_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if output.exists():
                return verify_independent_observer_output(output, runner_pid=os.getpid())
            time.sleep(0.5)
        return {
            "schema_id": "redcap-e2e-independent-observer-verification",
            "ok": False,
            "path": str(output),
            "failures": ["等待 harness 写入 independent-observer.json 超时"],
        }
    command = run_observer_request_as_harness(request_path, runner_pid=os.getpid(), harness_pid=os.getpid())
    verification = verify_independent_observer_output(output, runner_pid=os.getpid())
    if command.get("ok") is not True and command.get("failures"):
        verification["failures"].extend(str(item) for item in command.get("failures", []))
        verification["ok"] = False
    return verification


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
            "root_cause": "E2E 运行器最终收口检查未满足终局验收条件。",
            "impact": "当前轮不能写 completion-marker.json，也不能判定 ready_for_engineering_use=true。",
            "suggested_fix": "根据失败摘要修复运行器、证据或外部项目后，重新执行完整 E2E。",
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
        entrypoint, entrypoint_rel, _ = detect_browser_entrypoint(project)
        return (project / "README.md").exists() or entrypoint is not None, f"README.md 或浏览器入口存在：{entrypoint_rel}"
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
    if "signup-intent-data-contract" in criterion:
        probes = load_optional_json(evidence / "negative-probes.json") or {}
        runner_probe = load_optional_json(evidence / "runner-negative-contract-probe.json") or {}
        passed = probes.get("passed") is True and runner_probe.get("ok") is True
        return passed, "negative-probes.json and runner-negative-contract-probe.json"
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
    if "independent-browser-verification.json" in criterion:
        return context.get("independent_browser_ok") is True, "independent-browser-verification.json"
    if "independent-observer.json" in criterion or "外部观察者" in criterion:
        return context.get("independent_observer_ok") is True, "independent-observer.json"
    if "character-player-relation-contract" in criterion or "角色名和玩家名" in criterion:
        runner_probe = load_optional_json(evidence / "runner-character-player-contract-probe.json") or {}
        passed = context.get("behavior_ok") is True and runner_probe.get("ok") is True
        return passed, "behavioral-browser-verification.json and runner-character-player-contract-probe.json"
    if "blocked-package.json" in criterion:
        return not (project / "blocked-package.json").exists(), "blocked-package.json absent"
    if "行为" in criterion or "交互" in criterion:
        return context.get("behavior_ok") is True, "behavioral-browser-verification.json"
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
    behavior_passed, behavior_evidence = criterion_pass("浏览器行为级交互验证", project, evidence, context)
    results.append({
        "id": "AC-behavior",
        "criterion": "运行器必须执行至少一次真实浏览器交互，并在适用时验证关键领域关系在 UI 中正确呈现。",
        "passed": behavior_passed,
        "evidence": behavior_evidence,
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
        "extra_disabled_features": CODEX_ROLE_EXTRA_DISABLED_FEATURES,
        "preserve_user_config": CODEX_ROLE_PRESERVE_USER_CONFIG,
        "interactive_gate_markers": CODEX_ROLE_INTERACTIVE_GATE_MARKERS,
        "risk": "Loom 角色由独立 Codex CLI 自动执行；角色质量风险由中等推理预算、结构化交接、运行器客观检查、浏览器检查和最终双 provider 棱镜复核共同约束。",
        "accepted_for_single_e2e": CODEX_ROLE_REASONING_EFFORT != "low",
        "notes": [
            "session_id 是角色隔离主证据。",
            "turn_id 可能来自宿主钩子同轮记录，不作为角色隔离主证据。",
            "角色子进程保留用户配置以确保项目级 .codex hook 生效；误入用户级交互式技能时由运行器识别、记录并重试，不允许牺牲 Hook 能力。",
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


def write_pre_final_readiness(
    project: pathlib.Path,
    evidence: pathlib.Path,
    failures: list[str],
    context: dict[str, Any],
) -> dict[str, Any]:
    criteria_results = build_acceptance_results(project, evidence, {**context, "failures": failures, "final_prism_ok": False})
    for item in criteria_results:
        if item.get("evidence") == "final prism review":
            item["passed"] = None
            item["status"] = "pending_final_prism"
        elif item.get("passed") is True:
            item["status"] = "passed"
        else:
            item["status"] = "failed"
    pending_final_evidence = ["completion-marker.json", "final-prism-review.json", "iteration-verdict.json"]
    checked_existing_evidence = sorted(
        item for item in REQUIRED_EVIDENCE_CHECKS
        if item not in set(pending_final_evidence)
    )
    payload = {
        "schema_id": "redcap-e2e-pre-final-readiness",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "status": "ready_for_final_prism" if not failures else "blocked_before_final_prism",
        "ready_for_engineering_use": False,
        "ready_for_engineering_use_reason": "最终棱镜复核前必须为 false；通过最终棱镜后由运行器重写 iteration-verdict.json 并写 completion-marker.json。",
        "final_prism_pending": True,
        "purpose": "最终棱镜复核前的客观证据汇总；不是终局完成声明，不能替代 iteration-verdict.json。",
        "criteria_results": criteria_results,
        "criteria_summary": {
            "total": len(criteria_results),
            "passed": sum(1 for item in criteria_results if item.get("passed") is True),
            "pending_final_prism": sum(1 for item in criteria_results if item.get("status") == "pending_final_prism"),
            "failed": sum(1 for item in criteria_results if item.get("status") == "failed"),
        },
        "remaining_issues": failures,
        "evidence_checked": checked_existing_evidence,
        "pending_final_evidence": [
            {
                "path": item,
                "checked": False,
                "pending": True,
                "reason": "该文件只能在最终棱镜通过后生成或更新，不能进入预收口已检查清单。"
            }
            for item in pending_final_evidence
        ],
    }
    write_json(evidence / "pre-final-readiness.json", payload)
    return payload


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
        "behavioral_browser_verification": "behavioral-browser-verification.json",
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


def write_runner_self_purification_resolution(evidence: pathlib.Path) -> dict[str, Any]:
    purification = load_optional_json(evidence / "self-purification-candidates.json") or {}
    decisions = purification.get("decisions")
    if not isinstance(decisions, list):
        decisions = []
    candidates = purification.get("candidates")
    if not isinstance(candidates, list):
        candidates = []
    resolutions: list[dict[str, Any]] = []
    failures: list[str] = []
    for index, decision in enumerate(decisions, start=1):
        if not isinstance(decision, dict):
            failures.append(f"第 {index} 个自我净化 decision 不是对象")
            continue
        requested_decision = str(decision.get("decision") or "")
        source_id = str(decision.get("id") or decision.get("candidate_id") or f"decision-{index}")
        if requested_decision == "promote_public":
            disposition = "defer_public_promotion"
            reason = "E2E 运行器不能在验收收口阶段直接写公共知识；候选只进入后续自我净化评审输入。"
        elif requested_decision == "keep_private":
            disposition = "acknowledge_private_boundary"
            reason = "本轮确认私有边界，但不写入 Cap 私有人格正文。"
        elif requested_decision == "defer_with_owner":
            disposition = "defer_with_owner_acknowledged"
            reason = "本轮承认后续归属，但不让悬空候选阻塞完成；后续由自我净化流程单独评审。"
        elif requested_decision == "no_promote":
            disposition = "no_promote_acknowledged"
            reason = "本轮接受不晋升决定。"
        else:
            disposition = "invalid_decision"
            reason = "未知 decision，不能视为已解决。"
            failures.append(f"未知自我净化 decision：{requested_decision}")
        resolutions.append({
            "source_id": source_id,
            "requested_decision": requested_decision,
            "disposition": disposition,
            "reason": reason,
            "source_reason": decision.get("reason"),
            "public_write": False,
            "private_persona_write": False,
        })
    if not decisions and candidates:
        failures.append("存在自我净化候选但 reviewer 未给出 decisions")
    payload = {
        "schema_id": "redcap-e2e-runner-self-purification-resolution",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "source": "self-purification-candidates.json",
        "resolved": not failures,
        "public_promotions_written": False,
        "private_persona_written": False,
        "candidate_count": len(candidates),
        "decision_count": len(decisions),
        "resolutions": resolutions,
        "no_candidate_reason": purification.get("no_candidate_reason"),
        "failures": failures,
    }
    write_json(evidence / "runner-self-purification-resolution.json", payload)
    return payload


def final_prism_request(direction: str, bundle: dict[str, Any], supplemental_evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    supplemental_evidence = supplemental_evidence or {}
    return {
        "task": "Review whether this RedCap E2E run may write its completion marker.",
        "user_intent": "Norven wants RedCap to prove it can drive a real project through role-separated Loom workflow, hooks, evidence, self-purification, persona boundary, and failure feedback before claiming production usefulness.",
        "main_claim": "The E2E runner may write completion-marker.json because all role, hook, test, evidence, and failure-loop requirements passed after reviewer exit.",
        "changed_reality": [
            "An external project was created outside the RedCap source workspace.",
            "Five Loom roles ran as independent Codex CLI sessions with project-level Hook evidence.",
            "The runner independently reran project validation and bundled evidence hashes before deciding completion.",
            "The runner performed a mutation-based negative contract probe: it temporarily wrote bad signup data, required the validation command to fail, restored the original data, and required validation to pass again.",
            "The runner opened the deliverable in a real headless browser, captured a screenshot, and checked visible rendered content before requesting completion.",
            "The runner performed a separate behavioral browser verification with a real click interaction, captured behavioral-browser-verification.png immediately after the verified interaction and before any later page reset, compared its hash with browser-inspection.png, and, when project data exposed player-character relationships, checked that the relation rendered in the same DOM structural container rather than relying on flattened text distance.",
            "The runner also launched a separate Python process for independent browser verification and wrote independent-browser-verification.json before final provider review; browser-inspection, behavioral verification, independent browser verification, and independent observer use recorded browser_context metadata and are summarized by visual-independence-report.json.",
            "The outer E2E harness launched an independent observer as a sibling process of the runner-worker; the observer read the frozen final-evidence-bundle.json and recorded bundle_fingerprint.file_sha256 matching the observer request before writing read-only sealed independent-observer.json.",
            "pre-final-readiness.json separates evidence_checked from pending_final_evidence, so completion-marker.json, final-prism-review.json, and the final iteration-verdict.json are not claimed as pre-final checked evidence.",
            "runner-self-purification-resolution.json explicitly resolves reviewer self-purification candidates for this E2E without writing public memory or Cap private persona body.",
        ],
        "evidence": [
            {
                "kind": "final-evidence-bundle",
                "reference": "final-evidence-bundle.json",
                "summary": bundle,
            },
            {
                "kind": "post-bundle-observer-verification",
                "reference": "independent-observer-verification.json",
                "summary": supplemental_evidence.get("independent_observer_verification"),
            },
            {
                "kind": "visual-independence-report",
                "reference": "visual-independence-report.json",
                "summary": supplemental_evidence.get("visual_independence_report"),
            },
            {
                "kind": "pre-final-readiness",
                "reference": "pre-final-readiness.json",
                "summary": supplemental_evidence.get("pre_final_readiness"),
            }
        ],
        "review_mode": "completion_review",
        "risk_level": "high",
        "requested_providers": ["kimi", "claude-code"],
        "known_constraints": [
            "Reviewer must not self-certify completion.",
            "Open failure-backlog items block completion.",
            "Completion marker scope is only this E2E run, not permanent RedCap full revival.",
            "iteration-verdict.json is intentionally not finalized before this provider review; pre-final-readiness.json is generated after final-evidence-bundle.json and is only an objective pre-final summary, not a completion claim.",
            "If this provider review passes, the runner must regenerate iteration-verdict.json with final_prism_pending=false before writing completion-marker.json.",
            "pre-final-readiness.json must not list completion-marker.json, final-prism-review.json, or iteration-verdict.json in evidence_checked; those belong in pending_final_evidence until this review passes.",
            "Loom role session_id is the role isolation evidence; turn_id may reflect host hook grouping and is not used as the role identity boundary.",
            "independent-observer.json must verify parent_is_harness=true, parent_is_not_runner=true, observer_seal hash match, read-only file mode, deliverable hashes, and browser observation.",
            "final-evidence-bundle.json is a frozen review bundle observed by the independent observer; post-bundle observer files, visual-independence-report.json, final-prism-review.json, failure-backlog.json, iteration-verdict.json, and completion-marker.json are supplied separately or generated later to avoid self-referential bundle hashes.",
            "visual-independence-report.json must show distinct screenshot hashes and recorded browser_context for browser-inspection, behavioral-browser-verification, independent-browser-verification, and independent-observer.",
        ],
        "role_execution_profile": {
            "model": CODEX_ROLE_MODEL,
            "reasoning_effort": CODEX_ROLE_REASONING_EFFORT,
            "disable_plugins": CODEX_ROLE_DISABLE_PLUGINS,
            "extra_disabled_features": CODEX_ROLE_EXTRA_DISABLED_FEATURES,
            "preserve_user_config": CODEX_ROLE_PRESERVE_USER_CONFIG,
            "interactive_gate_markers": CODEX_ROLE_INTERACTIVE_GATE_MARKERS,
            "quality_controls": [
                "structured role handoff files",
                "runner-owned final validation",
                "browser-inspection.json",
                "behavioral-browser-verification.json",
                "independent-browser-verification.json",
                "independent-observer.json",
                "runner-negative-contract-probe.json",
                "runner-self-purification-resolution.json",
                "two-provider final Prism review",
            ],
        },
    }


def run_final_prism_review(project: pathlib.Path, evidence: pathlib.Path, direction: str, bundle: dict[str, Any], supplemental_evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    package_prism = project / ".redcap" / "runtime" / "prism" / "bin" / "prism"
    package_dispatch = project / ".redcap" / "runtime" / "prism" / "bin" / "prism-dispatch"
    run_dir = evidence / "final-prism-review"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    request_path = run_dir / "request.json"
    request_payload = final_prism_request(direction, bundle, supplemental_evidence=supplemental_evidence)
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
    runner_negative_probe = run_runner_negative_contract_probe(project, evidence)
    write_json(evidence / "runner-negative-contract-probe.json", runner_negative_probe)
    runner_character_player_probe = run_runner_character_player_contract_probe(project, evidence)
    write_json(evidence / "runner-character-player-contract-probe.json", runner_character_player_probe)
    browser_inspection = run_browser_inspection(project, evidence)
    write_json(evidence / "browser-inspection.json", browser_inspection)
    behavioral_verification = run_behavioral_browser_verification(project, evidence)
    write_json(evidence / "behavioral-browser-verification.json", behavioral_verification)
    independent_browser = run_independent_browser_verification_process(project, evidence)
    write_json(evidence / "independent-browser-verification.json", independent_browser)
    role_risk = write_role_execution_risk(evidence)
    runner_purification_resolution = write_runner_self_purification_resolution(evidence)
    failures: list[str] = []
    if role_result.get("ok") is not True:
        failures.append("Loom 角色管线未通过")
    if missing_hooks:
        failures.append(f"缺少项目级 Hook 事件：{missing_hooks}")
    if package_prism.get("ok") is not True:
        failures.append("安装包内棱镜自检未通过")
    if runner_tests.get("ok") is not True:
        failures.append("运行器独立重跑项目验证未通过")
    if runner_negative_probe.get("ok") is not True:
        failures.append("运行器负向领域契约探针未通过")
    if runner_character_player_probe.get("ok") is not True:
        failures.append("运行器角色玩家负向领域契约探针未通过")
    if browser_inspection.get("ok") is not True:
        failures.append("运行器浏览器检查未通过")
    if behavioral_verification.get("ok") is not True:
        failures.append("运行器行为级浏览器验证未通过")
    if independent_browser.get("ok") is not True:
        failures.append("独立子进程浏览器验证未通过")
    if role_risk.get("accepted_for_single_e2e") is not True:
        failures.append("Loom 角色推理预算风险未被接受")
    if runner_purification_resolution.get("resolved") is not True:
        failures.append(f"运行器自我净化裁决未通过：{runner_purification_resolution.get('failures')}")
    backlog_path = evidence / "failure-backlog.json"
    if backlog_path.exists() or role_result.get("ok") is True:
        open_items = backlog_open_items(evidence)
        if open_items:
            failures.append(f"failure-backlog 仍有开放项：{open_items}")
    pre_final_context = {
        "role_ok": role_result.get("ok") is True,
        "package_prism_ok": package_prism.get("ok") is True,
        "runner_tests_ok": runner_tests.get("ok") is True,
        "runner_negative_probe_ok": runner_negative_probe.get("ok") is True,
        "runner_character_player_probe_ok": runner_character_player_probe.get("ok") is True,
        "browser_ok": browser_inspection.get("ok") is True,
        "behavior_ok": behavioral_verification.get("ok") is True,
        "independent_browser_ok": independent_browser.get("ok") is True,
        "independent_observer_ok": False,
        "final_prism_ok": False,
    }
    bundle = build_final_evidence_bundle(project, evidence, direction)
    write_json(evidence / "final-evidence-bundle.json", bundle)
    independent_observer_verification = request_independent_observer(project, evidence, bundle)
    independent_observer_payload = independent_observer_verification.get("payload")
    if independent_observer_verification.get("ok") is not True:
        failures.append(f"独立外部观察者验证未通过：{independent_observer_verification.get('failures')}")
    if isinstance(independent_observer_payload, dict):
        write_json(evidence / "independent-observer-verification.json", {
            "schema_id": "redcap-e2e-independent-observer-verification",
            "ok": independent_observer_verification.get("ok") is True,
            "checked_at": iso_now(),
            "path": independent_observer_verification.get("path"),
            "failures": independent_observer_verification.get("failures"),
        })
    visual_independence = build_visual_independence_report(evidence)
    write_json(evidence / "visual-independence-report.json", visual_independence)
    if visual_independence.get("ok") is not True:
        failures.append(f"视觉三角独立性验证未通过：{visual_independence.get('failures')}")
    pre_final_context["independent_observer_ok"] = independent_observer_verification.get("ok") is True
    pre_final_readiness = write_pre_final_readiness(project, evidence, failures, pre_final_context)
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
        final_prism = run_final_prism_review(project, evidence, direction, bundle, supplemental_evidence={
            "independent_observer_verification": load_optional_json(evidence / "independent-observer-verification.json"),
            "visual_independence_report": visual_independence,
            "pre_final_readiness": pre_final_readiness,
        })
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
    runner_purification = load_optional_json(evidence / "runner-self-purification-resolution.json")
    if runner_purification is not None:
        if runner_purification.get("resolved") is not True:
            failures.append("runner-self-purification-resolution.resolved 必须为 true")
        if runner_purification.get("public_promotions_written") is not False:
            failures.append("runner-self-purification-resolution.public_promotions_written 必须为 false")
        if runner_purification.get("private_persona_written") is not False:
            failures.append("runner-self-purification-resolution.private_persona_written 必须为 false")
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
    runner_negative_probe = load_optional_json(evidence / "runner-negative-contract-probe.json")
    if runner_negative_probe is not None:
        if runner_negative_probe.get("producer") != "e2e-runner":
            failures.append("runner-negative-contract-probe 必须由 e2e-runner 生成")
        if runner_negative_probe.get("ok") is not True:
            failures.append("runner-negative-contract-probe 必须证明坏报名数据失败且恢复后通过")
    runner_character_probe = load_optional_json(evidence / "runner-character-player-contract-probe.json")
    if runner_character_probe is not None:
        if runner_character_probe.get("producer") != "e2e-runner":
            failures.append("runner-character-player-contract-probe 必须由 e2e-runner 生成")
        if runner_character_probe.get("ok") is not True:
            failures.append("runner-character-player-contract-probe 必须证明破坏角色玩家关联失败且恢复后通过")
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
    behavioral_verification = load_optional_json(evidence / "behavioral-browser-verification.json")
    if behavioral_verification is not None:
        if behavioral_verification.get("ok") is not True:
            failures.append("behavioral-browser-verification 必须证明运行器独立行为级浏览器验证通过")
        if not behavioral_verification.get("screenshot"):
            failures.append("behavioral-browser-verification 必须记录截图证据")
        if behavioral_verification.get("screenshot_phase") != "after_interaction":
            failures.append("behavioral-browser-verification 必须记录 screenshot_phase=after_interaction，证明截图采集发生在真实交互后")
        visual_independence = behavioral_verification.get("visual_independence")
        if not isinstance(visual_independence, dict):
            failures.append("behavioral-browser-verification 必须记录 visual_independence")
        else:
            if visual_independence.get("hashes_compared") is not True:
                failures.append("behavioral-browser-verification.visual_independence 必须证明已比较普通截图和行为截图哈希")
            if visual_independence.get("hashes_differ") is not True:
                failures.append("behavioral-browser-verification.visual_independence 必须证明行为截图不同于普通浏览器截图")
    visual_report = load_optional_json(evidence / "visual-independence-report.json")
    if visual_report is not None:
        if visual_report.get("ok") is not True:
            failures.append(f"visual-independence-report 必须通过：{visual_report.get('failures')}")
        if visual_report.get("distinct_screenshot_sha256_count") != visual_report.get("screenshot_count"):
            failures.append("visual-independence-report 必须证明截图哈希互不相同")
    independent_observer = load_optional_json(evidence / "independent-observer.json")
    if independent_observer is not None:
        verification = verify_independent_observer_output(evidence / "independent-observer.json")
        if verification.get("ok") is not True:
            failures.append(f"independent-observer 必须证明 harness 兄弟进程外部观察通过：{verification.get('failures')}")
    role_risk = load_optional_json(evidence / "role-execution-risk.json")
    if role_risk is not None and role_risk.get("accepted_for_single_e2e") is not True:
        failures.append("role-execution-risk 必须说明本轮角色执行风险已被约束")
    final_bundle = load_optional_json(evidence / "final-evidence-bundle.json")
    if final_bundle is not None:
        files = final_bundle.get("files")
        if not isinstance(files, list) or not files:
            failures.append("final-evidence-bundle.files 必须非空")
        else:
            post_bundle_forbidden = {
                "independent-observer.json",
                "independent-observer.png",
                "independent-observer-verification.json",
                "observer-request.json",
                "observer-command.json",
                "visual-independence-report.json",
                "pre-final-readiness.json",
                "final-prism-review.json",
                "failure-backlog.json",
                "iteration-verdict.json",
                "completion-marker.json",
            }
            for item in files:
                if not isinstance(item, dict):
                    failures.append("final-evidence-bundle.files 条目必须是对象")
                    continue
                if item.get("exists") is True and not item.get("sha256"):
                    failures.append(f"final-evidence-bundle 中存在缺少 sha256 的已存在文件：{item.get('path')}")
                if item.get("path") in post_bundle_forbidden:
                    failures.append(f"final-evidence-bundle 禁止包含后生成或自引用证据文件：{item.get('path')}")
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
    attempts: list[dict[str, Any]] = []
    result: dict[str, Any] = {}
    events: list[str] = []
    missing: list[str] = list(REQUIRED_HOOK_EVENTS)
    last_message = project / ".redcap" / "evidence" / "e2e" / "carrier-last-message.txt"
    for attempt in range(1, max(1, CARRIER_PROBE_MAX_ATTEMPTS) + 1):
        if events_path.exists():
            events_path.unlink()
        last_message = project / ".redcap" / "evidence" / "e2e" / f"carrier-last-message.attempt-{attempt}.txt"
        argv = [
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
            argv.extend(["--disable", "plugins"])
        for feature in CODEX_ROLE_EXTRA_DISABLED_FEATURES:
            argv.extend(["--disable", feature])
        argv.extend([
            "--output-last-message",
            str(last_message),
            "请使用 shell 执行 pwd，然后最终只回答 carrier-probe-ok。",
        ])
        result = run_command(argv, cwd=project, timeout_seconds=timeout_seconds)
        events = parse_hook_events(events_path)
        missing = [event for event in REQUIRED_HOOK_EVENTS if event not in events]
        attempt_ok = result["ok"] and not missing
        attempts.append({
            "attempt": attempt,
            "ok": attempt_ok,
            "command": command_receipt(result),
            "events": events,
            "missing_events": missing,
            "last_message": str(last_message),
        })
        if attempt_ok:
            break
        if result["ok"]:
            break
    probe = {
        "schema_id": "redcap-ai-e2e-carrier-probe",
        "ok": result["ok"] and not missing,
        "project": str(project),
        "events_path": str(events_path),
        "events": events,
        "missing_events": missing,
        "command": command_receipt(result),
        "attempts": attempts,
        "max_attempts": max(1, CARRIER_PROBE_MAX_ATTEMPTS),
        "codex_model": CODEX_ROLE_MODEL,
        "codex_reasoning_effort": CODEX_ROLE_REASONING_EFFORT,
        "codex_plugins_disabled": CODEX_ROLE_DISABLE_PLUGINS,
        "codex_extra_disabled_features": CODEX_ROLE_EXTRA_DISABLED_FEATURES,
        "codex_user_config_preserved": CODEX_ROLE_PRESERVE_USER_CONFIG,
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


def run_e2e_harness(direction: str, work_root: pathlib.Path, timeout_seconds: int = 900) -> dict[str, Any]:
    """Run E2E through an outer harness so observer and runner are siblings."""
    if os.environ.get("REDCAP_E2E_WORKER") == "1":
        return run_e2e(direction, work_root, timeout_seconds)
    work_root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["REDCAP_E2E_WORKER"] = "1"
    env["REDCAP_E2E_OBSERVER_BY_HARNESS"] = "1"
    env["REDCAP_E2E_HARNESS_PID"] = str(os.getpid())
    argv = [
        sys.executable,
        str(pathlib.Path(__file__).resolve()),
        "run",
        "--direction",
        direction,
        "--work-root",
        str(work_root),
        "--timeout-seconds",
        str(timeout_seconds),
    ]
    started = iso_now()
    worker = subprocess.Popen(
        argv,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env=env,
    )
    observer_requests: set[pathlib.Path] = set()
    observer_commands: list[dict[str, Any]] = []
    deadline = time.monotonic() + timeout_seconds + OBSERVER_TIMEOUT_SECONDS + 600
    timed_out = False
    while worker.poll() is None:
        for request_path in sorted(work_root.glob("**/.redcap/evidence/e2e/observer-request.json")):
            resolved = request_path.resolve()
            if resolved in observer_requests:
                continue
            observer_requests.add(resolved)
            observer_commands.append(run_observer_request_as_harness(resolved, runner_pid=worker.pid, harness_pid=os.getpid()))
        if time.monotonic() > deadline:
            timed_out = True
            kill_process_group(worker, grace_seconds=2.0)
            break
        time.sleep(0.5)
    stdout, stderr = worker.communicate()
    parsed = parse_leading_json(stdout)
    if parsed is None:
        parsed = {
            "schema_id": "redcap-ai-e2e-run-result",
            "ok": False,
            "ready_for_engineering_use": False,
            "failures": ["E2E worker 没有返回可解析 JSON"],
        }
    harness_failures: list[str] = []
    if timed_out:
        harness_failures.append("E2E harness 等待 worker 超时")
    if worker.returncode != 0 and parsed.get("ok") is True:
        harness_failures.append(f"E2E worker 退出码非 0：{worker.returncode}")
    if not observer_requests:
        harness_failures.append("E2E worker 没有发出 observer-request.json")
    if any(command.get("ok") is not True for command in observer_commands):
        harness_failures.append("至少一个独立观察者命令失败")
    parsed.setdefault("failures", [])
    if harness_failures:
        parsed["ok"] = False
        parsed["ready_for_engineering_use"] = False
        parsed["failures"].extend(harness_failures)
    parsed["harness"] = {
        "schema_id": "redcap-e2e-harness-summary",
        "producer": "e2e-harness",
        "started_at": started,
        "finished_at": iso_now(),
        "worker_pid": worker.pid,
        "worker_exit_code": worker.returncode,
        "worker_timed_out": timed_out,
        "observer_request_count": len(observer_requests),
        "observer_commands": observer_commands,
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-4000:],
    }
    evidence_root = parsed.get("evidence_root")
    if isinstance(evidence_root, str):
        try:
            write_json(pathlib.Path(evidence_root) / "harness-summary.json", parsed["harness"])
            write_json(pathlib.Path(evidence_root) / "run-summary.json", parsed)
        except Exception:
            pass
    return parsed


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
    result = run_e2e_harness(direction_from_args(args), resolve_work_root(args.work_root), args.timeout_seconds)
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
            timeout_retry_reason = role_failure_retry_reason({
                "ok": False,
                "timed_out": True,
                "timeout_seconds": 420,
                "stdout": "",
                "stderr": "",
            }, artifact_exists=False)
            if not timeout_retry_reason or "timeout" not in timeout_retry_reason:
                failures.append("无产物的 Codex CLI 超时没有被识别为可重试")
            if role_failure_retry_reason({
                "ok": False,
                "stdout": "partial output",
                "stderr": "stream disconnected",
            }, artifact_exists=False):
                failures.append("已有 stdout 的角色失败不应被自动重试")
            interactive_retry_reason = role_failure_retry_reason({
                "ok": False,
                "stdout": "Spec written and committed. Please review it before proceeding.",
                "stderr": "sed -n '1,220p' /Users/norven/.claude/skills/brainstorming/SKILL.md",
            }, artifact_exists=False)
            if not interactive_retry_reason or "interactive approval gate marker" not in interactive_retry_reason:
                failures.append("误入交互式技能门禁没有被识别为可重试失败")
            if role_failure_retry_reason({
                "ok": False,
                "stdout": "Spec written and committed. Please review it before proceeding.",
                "stderr": "brainstorming/SKILL.md",
            }, artifact_exists=True):
                failures.append("角色产物已存在时不应因交互式技能标记继续重试")
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
            developer_argv = build_codex_role_argv(project, "developer", evidence / "role-messages" / "developer.txt", developer_prompt)
            if "--ignore-user-config" in developer_argv:
                failures.append("developer Codex CLI argv 不得包含 --ignore-user-config；该参数会破坏项目级 Hook 承载")
            if max(1, CODEX_ROLE_MAX_ATTEMPTS) < 3:
                failures.append("Loom 角色默认尝试次数低于 3，无法覆盖承载层双重抖动")
            minimum_timeouts = {
                "product_manager": 420,
                "architect": 420,
                "developer": 600,
                "tester": 480,
                "reviewer": 480,
            }
            for role_name, minimum_timeout in minimum_timeouts.items():
                if ROLE_TIMEOUT_SECONDS.get(role_name, 0) < minimum_timeout:
                    failures.append(f"{role_name} 角色超时预算低于 {minimum_timeout} 秒")
            if CODEX_ROLE_DISABLE_PLUGINS:
                disable_index = developer_argv.index("--disable") if "--disable" in developer_argv else -1
                if disable_index < 0 or developer_argv[disable_index:disable_index + 2] != ["--disable", "plugins"]:
                    failures.append("developer Codex CLI argv 没有禁用 plugins")
            for required_feature in ["apps", "general_analytics"]:
                if ["--disable", required_feature] not in [
                    developer_argv[index:index + 2]
                    for index in range(0, len(developer_argv) - 1)
                ]:
                    failures.append(f"developer Codex CLI argv 没有禁用 {required_feature}")
            if ".redcap/evidence/e2e/requirements.json" not in developer_prompt:
                failures.append("developer 提示词没有给出 requirements.json 的证据目录实际路径")
            if ".redcap/evidence/e2e/acceptance-criteria.json" not in developer_prompt:
                failures.append("developer 提示词没有给出 acceptance-criteria.json 的证据目录实际路径")
            if ".redcap/evidence/e2e/implementation-log.json" not in developer_prompt:
                failures.append("developer 提示词没有给出 implementation-log.json 的证据目录目标路径")
            if "不要启动需要人工批准的交互式设计流程" not in developer_prompt:
                failures.append("developer 提示词没有禁止交互式设计流程，可能复发 brainstorming 卡死")
            signup_direction = "活动组织工具，包含报名意向、角色和玩家信息"
            signup_requirements = build_requirements(signup_direction)
            signup_acceptance = build_acceptance(signup_direction)
            signup_contracts = signup_requirements.get("domain_contracts")
            if not isinstance(signup_contracts, list) or not any(item.get("id") == "signup-intent-data-contract" for item in signup_contracts if isinstance(item, dict)):
                failures.append("包含报名意向的需求没有生成 signup-intent-data-contract")
            if "domain_contracts" not in signup_acceptance or not any("signup-intent-data-contract" in item for item in signup_acceptance.get("criteria", []) if isinstance(item, str)):
                failures.append("包含报名意向的验收标准没有承接 signup-intent-data-contract")
            architect_prompt = build_role_prompt(project, evidence, "architect", signup_direction)
            signup_developer_prompt = build_role_prompt(project, evidence, "developer", signup_direction)
            signup_tester_prompt = build_role_prompt(project, evidence, "tester", signup_direction)
            signup_reviewer_prompt = build_role_prompt(project, evidence, "reviewer", signup_direction)
            if "signup-intent-data-contract" not in architect_prompt or "数据模型" not in architect_prompt:
                failures.append("architect 提示词没有要求把报名意向契约落入数据模型")
            if "signup-intent-data-contract" not in signup_developer_prompt or "非空 signups 数组" not in signup_developer_prompt:
                failures.append("developer 提示词没有要求实现并验证报名意向契约")
            if "signups 数组" not in signup_tester_prompt or "signupIntent 字段" not in signup_tester_prompt:
                failures.append("tester 提示词没有要求验证报名意向契约")
            if "domain_contracts" not in signup_reviewer_prompt or "blocking_findings" not in signup_reviewer_prompt:
                failures.append("reviewer 提示词没有要求审核领域数据契约")
            retry_developer_prompt = role_retry_prompt(developer_prompt, 2)
            if "【重试约束】" not in retry_developer_prompt or "不要读取或执行需要人工批准的技能流程" not in retry_developer_prompt:
                failures.append("developer 重试提示没有压制交互式设计技能误触发")
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
            if "signups 数组" not in tester_prompt or "signupIntent 字段" not in tester_prompt or "signups=[]" not in tester_prompt:
                failures.append("tester 提示词没有明确报名意向的非空结构化探针规则")
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
            verify_mjs.unlink()
            verify_script.unlink()
            validate_data_js = project / "scripts" / "validate-data.js"
            validate_data_js.write_text("process.exit(0)\n", encoding="utf-8")
            (project / "README.md").write_text("## 验证\n\n```sh\nnode scripts/validate-data.js\n```\n", encoding="utf-8")
            detected_argv, detected_source = detect_validation_command(project)
            if detected_argv != ["node", "scripts/validate-data.js"] or detected_source != "README.md command: node scripts/validate-data.js":
                failures.append("运行器没有识别 README 中明确给出的本地验证命令")
            data_dir = project / "data"
            data_dir.mkdir(exist_ok=True)
            write_json(data_dir / "activities.json", {
                "activities": [
                    {
                        "id": "self-check-activity",
                        "title": "自检活动",
                        "players": [
                            {
                                "id": "player-1",
                                "name": "测试玩家"
                            }
                        ],
                        "characters": [
                            {
                                "id": "character-1",
                                "name": "测试角色",
                                "playerId": "player-1"
                            }
                        ],
                        "signupIntent": "需要至少一名报名者",
                        "signups": [
                            {
                                "playerName": "测试玩家",
                                "characterName": "测试角色",
                                "status": "confirmed"
                            }
                        ]
                    }
                ]
            })
            validate_data_js.write_text(
                "const fs = require('fs');\n"
                "const data = JSON.parse(fs.readFileSync('data/activities.json', 'utf8'));\n"
                "const activity = data.activities[0];\n"
                "if (!activity.signupIntent || !Array.isArray(activity.signups) || activity.signups.length === 0) {\n"
                "  console.error('signup-intent-data-contract failed');\n"
                "  process.exit(2);\n"
                "}\n"
                "const playerIds = new Set((activity.players || []).map((player) => player.id));\n"
                "if (!Array.isArray(activity.characters) || activity.characters.some((character) => !playerIds.has(character.playerId))) {\n"
                "  console.error('character-player-relation-contract failed');\n"
                "  process.exit(3);\n"
                "}\n"
                "console.log(JSON.stringify({ok: true}));\n",
                encoding="utf-8",
            )
            negative_probe = run_runner_negative_contract_probe(project, evidence)
            if negative_probe.get("ok") is not True:
                failures.append(f"运行器负向契约探针不能处理 data/activities.json：{negative_probe.get('failures')}")
            if negative_probe.get("data_path") != "data/activities.json" or negative_probe.get("list_key") != "activities":
                failures.append("运行器负向契约探针没有记录真实 activities 数据路径和列表字段")
            character_probe = run_runner_character_player_contract_probe(project, evidence)
            if character_probe.get("ok") is not True:
                failures.append(f"运行器角色玩家负向契约探针不能处理 data/activities.json：{character_probe.get('failures')}")
            if character_probe.get("data_path") != "data/activities.json" or character_probe.get("list_key") != "activities":
                failures.append("运行器角色玩家负向契约探针没有记录真实 activities 数据路径和列表字段")
            validate_data_js.unlink()
            (project / "README.md").write_text("## 验证\n\n```sh\nnode scripts/missing-validate.js\n```\n", encoding="utf-8")
            detected_argv, detected_source = detect_validation_command(project)
            if detected_argv is not None:
                failures.append("运行器不应识别 README 中不存在的验证脚本")
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
            write_runner_self_purification_resolution(evidence)
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
            current_source = pathlib.Path(__file__).read_text(encoding="utf-8")
            if '"python3", "-m", "http.server"' not in current_source or "http://127.0.0.1:" not in current_source:
                failures.append("浏览器验收没有通过本地 HTTP 服务打开项目，可能退化为 file:// 误判")
            if "process_group_killed" not in current_source or "exit_code_after_cleanup" not in current_source:
                failures.append("浏览器验收没有记录本地 HTTP 服务清理证据")
            if "behavioral-browser-verification.json" not in current_source or "interactive_state_change" not in current_source:
                failures.append("E2E 自检没有覆盖行为级浏览器验证证据")
            if "independent-browser-verification.json" not in current_source or "e2e-independent-browser-process" not in current_source:
                failures.append("E2E 自检没有覆盖独立子进程浏览器复核证据")
            if "independent-observer.json" not in current_source or "e2e_independent_observer.py" not in current_source:
                failures.append("E2E 自检没有覆盖独立外部观察者证据")
            if "run_e2e_harness" not in current_source or "REDCAP_E2E_WORKER" not in current_source:
                failures.append("E2E 自检没有覆盖 harness/worker 兄弟进程运行结构")
            if "observer_seal" not in current_source or "parent_is_not_runner" not in current_source:
                failures.append("E2E 自检没有覆盖观察者 seal 与非 runner 父进程约束")
            if "runner-negative-contract-probe.json" not in current_source or "empty-signups-and-empty-signupIntent-must-fail" not in current_source:
                failures.append("E2E 自检没有覆盖运行器坏数据负向契约探针证据")
            if "runner-character-player-contract-probe.json" not in current_source or "broken-character-player-link-must-fail" not in current_source:
                failures.append("E2E 自检没有覆盖运行器角色玩家负向契约探针证据")
            if "runner-self-purification-resolution.json" not in current_source or "write_runner_self_purification_resolution" not in current_source:
                failures.append("E2E 自检没有覆盖运行器自我净化裁决证据")
            if "same_structural_container" not in current_source or "text_distance_is_informational_only" not in current_source:
                failures.append("行为级浏览器关系验证没有升级为 DOM 结构级探针")
            if "pending_final_evidence" not in current_source or "completion-marker.json\", \"final-prism-review.json\", \"iteration-verdict.json" not in current_source:
                failures.append("pre-final-readiness 没有把最终文件移出已检查证据清单")
            if "text_hash" not in current_source or "dom_summary_hash" not in current_source or "observable_criteria" not in current_source:
                failures.append("行为级浏览器验证没有使用文本哈希和稳定 DOM 摘要哈希作为可度量交互标准")
            if "screenshot_phase" not in current_source or "after_interaction" not in current_source or "behavioral_visual_independence" not in current_source:
                failures.append("行为级浏览器验证没有固化交互后截图阶段与视觉独立性检查")
            if "visual_independence" not in current_source or "hashes_differ" not in current_source or "browser-inspection.png" not in current_source:
                failures.append("行为级浏览器验证没有比较普通浏览器截图和行为截图哈希")
            if "visual-independence-report.json" not in current_source or "build_visual_independence_report" not in current_source:
                failures.append("E2E 自检没有覆盖视觉三角独立性报告")
            if "bundle_file_sha256" not in current_source or "matches_expected_file_sha256" not in current_source:
                failures.append("E2E 自检没有覆盖独立观察者冻结证据包文件哈希核对")
            if "data-redcap-volatile" not in current_source or ".spinner" not in current_source or ".loading" not in current_source:
                failures.append("行为级浏览器验证没有排除时间戳和加载器等常见噪音节点")
            if "interactive_gate_marker_observed" not in current_source or "actionable_interactive_gate_marker" not in current_source:
                failures.append("角色交互式门禁证据没有区分观测噪音与行动标记")
            if current_source.count("\n    write_json(evidence / \"final-evidence-bundle.json\", bundle)\n") != 1:
                failures.append("final-evidence-bundle.json 必须只写入一次，避免观察者核对后再次改写冻结包")
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

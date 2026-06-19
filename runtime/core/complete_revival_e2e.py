#!/usr/bin/env python3
"""RedCap 通用 E2E（端到端验收）运行器。"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import errno
import fcntl
import hashlib
import inspect
import json
import os
import pathlib
import pty
import re
import select
import shlex
import signal
import shutil
import socket
import subprocess
import sys
import tempfile
import termios
import textwrap
import time
import urllib.request
import zipfile
from typing import Any, Callable

from revival_followthrough import PRIVATE_PERSONA_MARKERS, REQUIRED_EVIDENCE_CHECKS, validate_e2e_evidence_quality


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REDCAP = REPO_ROOT / "runtime" / "bin" / "redcap"
CONTRACT = REPO_ROOT / "assets" / "contracts" / "complete-revival-e2e-acceptance-design.json"
LONG_TASK_CONTRACT = REPO_ROOT / "assets" / "contracts" / "long-task-contract.json"
DEFAULT_PERSISTENT_WORK_ROOT = pathlib.Path.home() / "workspace" / "redcap-e2e-runs"
PLACEHOLDER_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63600000020001e221bc330000000049454e44ae426082"
)
REQUIRED_HOOK_EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse"]
REQUIRED_CONFIGURED_HOOK_EVENTS = [*REQUIRED_HOOK_EVENTS, "Stop"]
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
CODEX_INTERACTIVE_DISABLE_PLUGINS = os.environ.get("REDCAP_E2E_CODEX_INTERACTIVE_DISABLE_PLUGINS", "1") != "0"
CODEX_ROLE_EXTRA_DISABLED_FEATURES = [
    item.strip()
    for item in os.environ.get("REDCAP_E2E_CODEX_ROLE_EXTRA_DISABLED_FEATURES", "apps").split(",")
    if item.strip()
]
CODEX_INTERACTIVE_EXTRA_DISABLED_FEATURES = [
    item.strip()
    for item in os.environ.get("REDCAP_E2E_CODEX_INTERACTIVE_EXTRA_DISABLED_FEATURES", "apps").split(",")
    if item.strip()
]
CODEX_DISABLED_MCP_SERVERS = [
    item.strip()
    for item in os.environ.get(
        "REDCAP_E2E_CODEX_DISABLED_MCP_SERVERS",
        "openaiDeveloperDocs,node_repl,neon,railway",
    ).split(",")
    if item.strip()
]
CODEX_PROJECT_TRUST_MODE = os.environ.get("REDCAP_E2E_CODEX_PROJECT_TRUST_MODE", "isolated_home")
CODEX_ROLE_PRESERVE_USER_CONFIG = True
CODEX_ROLE_MAX_ATTEMPTS = int(os.environ.get("REDCAP_E2E_CODEX_ROLE_MAX_ATTEMPTS", "3"))
LOOM_DEVELOPER_REPAIR_MAX_ROUNDS = int(os.environ.get("REDCAP_E2E_LOOM_DEVELOPER_REPAIR_MAX_ROUNDS", "2"))
E2E_PATROL_MAX_ITERATIONS = 3
E2E_SINGLE_RUN_TIMEOUT_HARD_CAP_SECONDS = 1800
CODEX_CLI_READINESS_TIMEOUT_SECONDS = int(os.environ.get("REDCAP_E2E_CODEX_READINESS_TIMEOUT_SECONDS", "120"))
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
DEVELOPER_CRITICAL_CATEGORIES = {
    "remote-dependency": [
        "远端依赖",
        "remote dependency",
        "remote-dependency",
        "cdn",
        "unpkg",
        "jsdelivr",
        "https://",
        "http://",
    ],
    "signup-empty": [
        "signups",
        "signupintent",
        "报名",
        "意向",
        "为空",
        "empty signup",
        "empty-signup",
        "warning",
    ],
    "file-protocol": [
        "file://",
        "本地文件协议",
        "fetch",
        "local file",
    ],
}
CARRIER_PROBE_MAX_ATTEMPTS = int(os.environ.get("REDCAP_E2E_CARRIER_PROBE_MAX_ATTEMPTS", "3"))
TEST_INJECT_CARRIER_MARKER_CLEANUP_FAILURE = os.environ.get("REDCAP_TEST_INJECT_CARRIER_MARKER_CLEANUP_FAILURE", "0") == "1"
TEST_MODE_ENV = "REDCAP_TEST_MODE"
TEST_INJECT_LAYERED_PREFLIGHT_FAILURE_ENV = "REDCAP_TEST_INJECT_LAYERED_PREFLIGHT_FAILURE"
CODEX_INTERACTIVE_CONFIRM_PROMPT = "Continue anyway? [y/N]"
BROWSER_ENTRYPOINT_CANDIDATES = [
    "index.html",
    "app/index.html",
    "public/index.html",
    "dist/index.html",
    "build/index.html",
]
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
    "final-marker-validation.json",
    "browser-inspection.json",
    "file-browser-inspection.json",
    "behavioral-browser-verification.json",
    "independent-browser-verification.json",
    "independent-observer.json",
    "visual-independence-report.json",
    "behavioral-relation-container-crop.png",
    "self-referential-boundary.json",
    "completion-marker-preview.json",
    "completion-marker-preview-validation.json",
    "convergence-diagnosis.json",
    "final-evidence-bundle.json",
    "final-prism-review.json",
    "failure-backlog.json",
    "iteration-verdict.json",
    "completion-marker-boundary-validation.json",
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
    "convergence-diagnosis.json",
    "role_opposition_matrix",
    "independent-browser-verification-script.py",
    "behavioral-relation-probe.png",
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
HARNESS_WATCHDOG_ROOT = pathlib.Path(os.environ.get("REDCAP_E2E_HARNESS_WATCHDOG_ROOT", "/tmp/redcap-harness-watchdog"))
HARNESS_WORKER_COMMUNICATE_TIMEOUT_SECONDS = float(os.environ.get("REDCAP_E2E_WORKER_COMMUNICATE_TIMEOUT_SECONDS", "8"))
HARNESS_WATCHDOG_GRACE_SECONDS = float(os.environ.get("REDCAP_E2E_WATCHDOG_GRACE_SECONDS", "10"))
HARNESS_WATCHDOG_POLL_SECONDS = float(os.environ.get("REDCAP_E2E_WATCHDOG_POLL_SECONDS", "0.5"))
BROWSER_INSPECTION_VIEWPORT = {"width": 1280, "height": 900}
FILE_BROWSER_INSPECTION_VIEWPORT = {"width": 1024, "height": 768}
BEHAVIORAL_BROWSER_VIEWPORT = {"width": 1280, "height": 900}
RELATION_PROBE_VIEWPORT = {"width": 1120, "height": 760}
RELATION_PROBE_MIN_VIEWPORT = {"width": 800, "height": 600}
RELATION_PROBE_MIN_VISIBLE_RATIO = 0.5
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


def codex_mcp_isolation_argv(trust_mode: str | None = None) -> list[str]:
    mode = trust_mode or CODEX_PROJECT_TRUST_MODE
    if mode == "isolated_home":
        return []
    argv: list[str] = []
    for server_name in unique_preserve_order(CODEX_DISABLED_MCP_SERVERS):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", server_name):
            raise SystemExit(f"非法 MCP 服务器名：{server_name}")
        argv.extend(["-c", f"mcp_servers.{server_name}.enabled=false"])
    return argv


def codex_mcp_isolation_contract(trust_mode: str | None = None) -> dict[str, Any]:
    mode = trust_mode or CODEX_PROJECT_TRUST_MODE
    argv = codex_mcp_isolation_argv(mode)
    failures: list[str] = []
    if mode == "isolated_home" and argv:
        failures.append("隔离 Codex Home 模式不得下发 MCP 禁用覆盖；干净 config 没有 transport 定义会触发 Codex CLI 配置错误")
    if mode != "isolated_home" and CODEX_DISABLED_MCP_SERVERS and not argv:
        failures.append("非隔离模式必须保留 MCP 禁用覆盖，避免用户全局 MCP 噪音影响验收")
    return {
        "schema_id": "redcap-e2e-codex-mcp-isolation-contract",
        "ok": not failures,
        "trust_mode": mode,
        "argv": argv,
        "disabled_servers": unique_preserve_order(CODEX_DISABLED_MCP_SERVERS),
        "failures": failures,
    }


def carrier_probe_attempt_decision(
    *,
    command_ok: bool,
    marker_exists: bool,
    marker_text: str | None,
    missing_events: list[str] | None,
) -> dict[str, Any]:
    normalized_missing_events = missing_events if isinstance(missing_events, list) else ["__invalid_missing_events__"]
    marker_normalized = marker_text.rstrip("\r\n") if marker_exists and marker_text is not None else None
    marker_ok = marker_normalized == "carrier-shell-ok"
    failure_reasons: list[str] = []
    if not command_ok:
        failure_reasons.append("command_failed")
    if not marker_exists:
        failure_reasons.append("marker_missing")
    elif not marker_ok:
        failure_reasons.append("marker_content_mismatch")
    if normalized_missing_events:
        failure_reasons.append("hook_events_missing")
    return {
        "ok": command_ok and marker_ok and len(normalized_missing_events) == 0,
        "marker_ok": marker_ok,
        "marker_normalized": marker_normalized,
        "missing_events": normalized_missing_events,
        "failure_reasons": failure_reasons,
    }


def carrier_probe_final_decision(
    *,
    command_ok: bool,
    marker_exists: bool,
    marker_text: str | None,
    missing_events: list[str] | None,
    marker_cleanup_error: str | None,
) -> dict[str, Any]:
    decision = carrier_probe_attempt_decision(
        command_ok=command_ok,
        marker_exists=marker_exists,
        marker_text=marker_text,
        missing_events=missing_events,
    )
    failure_reasons = list(decision["failure_reasons"])
    if marker_cleanup_error:
        failure_reasons.append("marker_cleanup_failed")
    return {
        **decision,
        "ok": decision["ok"] and marker_cleanup_error is None,
        "marker_cleanup_error": marker_cleanup_error,
        "failure_reasons": failure_reasons,
    }


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


def filesystem_state(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "kind": None}
    stat = path.stat()
    if path.is_file():
        return {
            "path": str(path),
            "exists": True,
            "kind": "file",
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": sha256_file(path),
        }
    if path.is_dir():
        entries: list[str] = []
        total_size = 0
        max_mtime_ns = stat.st_mtime_ns
        for item in sorted(path.rglob("*")):
            try:
                item_stat = item.stat()
            except OSError:
                continue
            rel = item.relative_to(path).as_posix()
            kind = "dir" if item.is_dir() else "file"
            size = item_stat.st_size if item.is_file() else 0
            total_size += size
            max_mtime_ns = max(max_mtime_ns, item_stat.st_mtime_ns)
            entries.append(f"{kind}:{rel}:{size}:{item_stat.st_mtime_ns}")
        return {
            "path": str(path),
            "exists": True,
            "kind": "dir",
            "entry_count": len(entries),
            "total_size": total_size,
            "max_mtime_ns": max_mtime_ns,
            "fingerprint": sha256_text("\n".join(entries)),
        }
    return {
        "path": str(path),
        "exists": True,
        "kind": "other",
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def user_codex_home_state() -> dict[str, Any]:
    home = source_codex_home()
    return {
        "schema_id": "redcap-user-codex-home-state",
        "home": str(home),
        "config": filesystem_state(home / "config.toml"),
        "auth": filesystem_state(home / "auth.json"),
        "logs": filesystem_state(home / "logs"),
    }


def compare_user_codex_home_state(before: dict[str, Any]) -> dict[str, Any]:
    after = user_codex_home_state()
    failures: list[str] = []
    for key in ["config", "auth", "logs"]:
        if before.get(key) != after.get(key):
            failures.append(f"用户真实 Codex Home 的 {key} 状态发生变化")
    return {
        "schema_id": "redcap-user-codex-home-guard",
        "ok": not failures,
        "before": before,
        "after": after,
        "failures": failures,
    }


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


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b[PX^_].*?\x1b\\|\x1b[78]")


def strip_terminal_control(value: str) -> str:
    return ANSI_RE.sub("", value).replace("\r", "")


def terminal_marker_present(text: str, marker: str) -> bool:
    clean = strip_terminal_control(text)
    if marker in clean:
        return True
    return marker in re.sub(r"\s+", "", clean)


def run_command_pty(
    argv: list[str],
    *,
    cwd: pathlib.Path = REPO_ROOT,
    timeout_seconds: int = 180,
    completion_markers: list[str] | None = None,
    completion_files: list[pathlib.Path] | None = None,
    completion_predicate: Callable[[], bool] | None = None,
    settle_seconds: float = 2.0,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run an interactive command in a PTY so Codex project hooks can fire."""
    started = dt.datetime.now(dt.timezone.utc)
    master_fd: int | None = None
    process: subprocess.Popen[bytes] | None = None
    transcript = bytearray()
    completion_markers = completion_markers or []
    completion_files = completion_files or []
    prompt_confirmed = False
    completion_seen_at: float | None = None
    completion_reason: str | None = None
    stop_requested = False
    timed_out = False
    process_group_killed = False
    cleanup_wait_timed_out = False
    cursor_reported = False
    device_attrs_reported = False
    fg_color_reported = False
    bg_color_reported = False
    keyboard_protocol_reported = False
    trust_prompt_confirmed = False
    try:
        master_fd, slave_fd = pty.openpty()
        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)
        env.setdefault("TERM", "xterm-256color")
        if env.get("TERM") == "dumb":
            env["TERM"] = "xterm-256color"
        env.setdefault("COLUMNS", "120")
        env.setdefault("LINES", "40")

        def prepare_pty_child() -> None:
            os.setsid()
            try:
                fcntl.ioctl(0, termios.TIOCSCTTY, 0)
            except OSError:
                pass

        process = subprocess.Popen(
            argv,
            cwd=str(cwd),
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=env,
            preexec_fn=prepare_pty_child,
        )
        os.close(slave_fd)
        deadline = time.monotonic() + timeout_seconds
        shutdown_deadline: float | None = None
        while True:
            now = time.monotonic()
            if process.poll() is not None:
                break
            if shutdown_deadline is not None and now > shutdown_deadline:
                process_group_killed = kill_process_group(process) or process_group_killed
                break
            if now > deadline:
                timed_out = True
                process_group_killed = kill_process_group(process) or process_group_killed
                break
            try:
                readable, _, _ = select.select([master_fd], [], [], 0.2)
            except (OSError, ValueError):
                readable = []
            if readable:
                try:
                    chunk = os.read(master_fd, 8192)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        break
                    raise
                if not chunk:
                    break
                transcript.extend(chunk)
                tail = transcript[-12000:].decode("utf-8", errors="replace")
                raw_tail = bytes(transcript[-12000:])
                if not cursor_reported and b"\x1b[6n" in raw_tail:
                    os.write(master_fd, b"\x1b[1;1R")
                    cursor_reported = True
                if not device_attrs_reported and b"\x1b[c" in raw_tail:
                    os.write(master_fd, b"\x1b[?1;2c")
                    device_attrs_reported = True
                if not fg_color_reported and (b"\x1b]10;?\x1b\\" in raw_tail or b"\x1b]10;?\x07" in raw_tail):
                    os.write(master_fd, b"\x1b]10;rgb:ffff/ffff/ffff\x1b\\")
                    fg_color_reported = True
                if not bg_color_reported and (b"\x1b]11;?\x1b\\" in raw_tail or b"\x1b]11;?\x07" in raw_tail):
                    os.write(master_fd, b"\x1b]11;rgb:0000/0000/0000\x1b\\")
                    bg_color_reported = True
                if not keyboard_protocol_reported and b"\x1b[?u" in raw_tail:
                    os.write(master_fd, b"\x1b[?0u")
                    keyboard_protocol_reported = True
                if not prompt_confirmed and CODEX_INTERACTIVE_CONFIRM_PROMPT in tail:
                    os.write(master_fd, b"y\n")
                    prompt_confirmed = True
                if (
                    not trust_prompt_confirmed
                    and "Do you trust the contents of this directory?" in tail
                    and "Yes, continue" in tail
                ):
                    os.write(master_fd, b"\n")
                    trust_prompt_confirmed = True
                if completion_seen_at is None:
                    for marker in completion_markers:
                        if marker and terminal_marker_present(tail, marker):
                            completion_seen_at = time.monotonic()
                            completion_reason = f"completion_marker:{marker}"
                            break
            if completion_seen_at is None and completion_predicate is not None:
                try:
                    if completion_predicate():
                        completion_seen_at = time.monotonic()
                        completion_reason = "completion_predicate_true"
                except Exception:
                    # The normal post-run validators will report the concrete
                    # schema or content failure; the PTY loop should not die
                    # merely because a file is temporarily half-written.
                    pass
            if completion_seen_at is None and completion_predicate is None and completion_files:
                present = [
                    path
                    for path in completion_files
                    if path.exists() and path.is_file() and path.stat().st_size > 0
                ]
                if len(present) == len(completion_files):
                    completion_seen_at = time.monotonic()
                    completion_reason = "completion_files_present"
            if completion_seen_at is not None and not stop_requested and time.monotonic() - completion_seen_at >= settle_seconds:
                try:
                    os.write(master_fd, b"\x03")
                    stop_requested = True
                    shutdown_deadline = time.monotonic() + 8.0
                except OSError:
                    process_group_killed = kill_process_group(process) or process_group_killed
                    break
        exit_code = process.poll()
        if exit_code is None:
            process_group_killed = kill_process_group(process) or process_group_killed
            try:
                exit_code = process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                cleanup_wait_timed_out = True
                try:
                    process.kill()
                except OSError:
                    pass
                try:
                    exit_code = process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    exit_code = process.poll()
                    if exit_code is None:
                        exit_code = -signal.SIGKILL
    finally:
        if master_fd is not None:
            try:
                os.close(master_fd)
            except OSError:
                pass
    stdout = transcript.decode("utf-8", errors="replace")
    clean_stdout = strip_terminal_control(stdout)
    completion_ok = (
        not completion_markers
        or any(terminal_marker_present(clean_stdout, marker) for marker in completion_markers)
        or completion_reason == "completion_files_present"
    )
    # Interactive Codex is intentionally interrupted after the completion marker
    # so the host can run Stop hooks and return control to the harness.
    intentional_stop_ok = stop_requested and completion_ok and completion_reason is not None
    ok = not timed_out and completion_ok and (exit_code == 0 or intentional_stop_ok)
    return {
        "argv": argv,
        "cwd": str(cwd),
        "exit_code": exit_code,
        "ok": ok,
        "timed_out": timed_out,
        "timeout_seconds": timeout_seconds,
        "process_group_killed": process_group_killed,
        "cleanup_wait_timed_out": cleanup_wait_timed_out,
        "intentional_stop_after_completion": intentional_stop_ok,
        "exit_code_after_cleanup": exit_code,
        "started_at": started.replace(microsecond=0).isoformat(),
        "finished_at": iso_now(),
        "stdout": clean_stdout,
        "stderr": "",
        "pty": True,
        "interactive_confirm_prompt_seen": prompt_confirmed,
        "trust_prompt_confirmed": trust_prompt_confirmed,
        "terminal_query_responses": {
            "cursor_position": cursor_reported,
            "device_attributes": device_attrs_reported,
            "foreground_color": fg_color_reported,
            "background_color": bg_color_reported,
            "keyboard_protocol": keyboard_protocol_reported,
        },
        "completion_reason": completion_reason,
        "env_overrides": sorted((env_overrides or {}).keys()),
        "completion_files_required": [str(path) for path in completion_files],
        "completion_files_present": [
            str(path)
            for path in completion_files
            if path.exists() and path.is_file() and path.stat().st_size > 0
        ],
        "stop_requested_after_completion": stop_requested,
    }


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def ps_field(pid: int, field: str) -> str | None:
    try:
        completed = subprocess.run(
            ["ps", "-ww", "-p", str(pid), "-o", f"{field}="],
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def process_is_zombie(pid: int) -> bool:
    state = ps_field(pid, "stat")
    return bool(state and state.startswith("Z"))


def process_identity(pid: int, command_substrings: list[str] | None = None) -> dict[str, Any]:
    identity: dict[str, Any] = {
        "pid": pid,
        "exists": process_exists(pid),
        "command_substrings": command_substrings or [],
    }
    if not identity["exists"]:
        return identity
    try:
        identity["pgid"] = os.getpgid(pid)
    except OSError:
        identity["pgid"] = None
    identity["lstart"] = ps_field(pid, "lstart")
    identity["command"] = ps_field(pid, "command")
    identity["stat"] = ps_field(pid, "stat")
    return identity


def process_matches_identity(
    pid: int,
    expected_identity: dict[str, Any] | None,
    command_substrings: list[str] | None = None,
) -> bool:
    if not expected_identity:
        return process_exists(pid)
    current = process_identity(pid, command_substrings)
    if current.get("exists") is not True:
        return False
    expected_lstart = expected_identity.get("lstart")
    current_lstart = current.get("lstart")
    if expected_lstart and current_lstart and expected_lstart != current_lstart:
        return False
    expected_pgid = expected_identity.get("pgid")
    current_pgid = current.get("pgid")
    if expected_pgid is not None and current_pgid is not None and int(expected_pgid) != int(current_pgid):
        return False
    command = str(current.get("command") or "")
    required_substrings = command_substrings or expected_identity.get("command_substrings") or []
    for required in required_substrings:
        if required and required not in command:
            return False
    return True


def worker_command_substrings(argv: list[str], work_root: pathlib.Path) -> list[str]:
    script = str(pathlib.Path(__file__).resolve())
    return [
        script,
        "run",
        "--work-root",
        str(work_root),
    ]


def kill_recorded_process_group(record: dict[str, Any], reason: str, grace_seconds: float = 2.0) -> dict[str, Any]:
    worker_pid = int(record.get("worker_pid") or 0)
    worker_pgid = int(record.get("worker_pgid") or worker_pid or 0)
    command_substrings = [str(item) for item in record.get("worker_command_substrings", []) if str(item)]
    identity = record.get("worker_identity") if isinstance(record.get("worker_identity"), dict) else None
    result: dict[str, Any] = {
        "schema_id": "redcap-e2e-recorded-process-cleanup",
        "ok": False,
        "reason": reason,
        "worker_pid": worker_pid,
        "worker_pgid": worker_pgid,
        "identity_matched": False,
        "terminated": False,
        "killed": False,
        "failures": [],
        "recorded_at": iso_now(),
    }
    if worker_pid <= 0:
        result["failures"].append("缺少 worker_pid")
        return result
    if not process_matches_identity(worker_pid, identity, command_substrings):
        result["failures"].append("worker 身份校验失败，拒绝清理，避免误杀无关进程")
        return result
    result["identity_matched"] = True
    try:
        current_pgid = os.getpgid(worker_pid)
    except OSError:
        result["ok"] = True
        result["failures"].append("worker 已不存在")
        return result
    if worker_pgid and current_pgid != worker_pgid:
        result["failures"].append("worker 进程组与记录不一致，拒绝清理")
        return result
    try:
        os.killpg(current_pgid, signal.SIGTERM)
        result["terminated"] = True
    except ProcessLookupError:
        result["ok"] = True
        return result
    except OSError as exc:
        result["failures"].append(f"发送 SIGTERM 失败：{exc}")
        return result
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if not process_exists(worker_pid) or process_is_zombie(worker_pid):
            result["ok"] = True
            return result
        time.sleep(0.05)
    try:
        os.killpg(current_pgid, signal.SIGKILL)
        result["killed"] = True
    except ProcessLookupError:
        result["ok"] = True
        return result
    except OSError as exc:
        result["failures"].append(f"发送 SIGKILL 失败：{exc}")
        return result
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if not process_exists(worker_pid) or process_is_zombie(worker_pid):
            result["ok"] = True
            return result
        time.sleep(0.05)
    result["failures"].append("SIGKILL 后 worker 仍存在")
    return result


def kill_process_group(
    process: subprocess.Popen[str] | None,
    grace_seconds: float = 2.0,
    expected_identity: dict[str, Any] | None = None,
    command_substrings: list[str] | None = None,
) -> bool:
    if process is None or process.poll() is not None:
        return False
    if expected_identity and not process_matches_identity(process.pid, expected_identity, command_substrings):
        return False
    killed = False
    try:
        pgid = os.getpgid(process.pid)
        os.killpg(pgid, signal.SIGTERM)
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
        pgid = os.getpgid(process.pid)
        os.killpg(pgid, signal.SIGKILL)
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


class HarnessInterrupted(Exception):
    def __init__(self, signal_name: str):
        super().__init__(signal_name)
        self.signal_name = signal_name


def harness_watchdog_path(work_root: pathlib.Path, parent_pid: int, worker_pid: int) -> pathlib.Path:
    digest = sha256_text(str(work_root.resolve()))[:12]
    return HARNESS_WATCHDOG_ROOT / f"{digest}-{parent_pid}-{worker_pid}.json"


def write_harness_watchdog_record(
    path: pathlib.Path,
    work_root: pathlib.Path,
    argv: list[str],
    timeout_seconds: int,
    worker: subprocess.Popen[str],
    worker_identity: dict[str, Any],
    deadline_epoch: float,
    command_substrings: list[str] | None = None,
) -> dict[str, Any]:
    required_substrings = command_substrings or worker_command_substrings(argv, work_root)
    record = {
        "schema_id": "redcap-e2e-harness-watchdog-record",
        "created_at": iso_now(),
        "record_path": str(path),
        "parent_pid": os.getpid(),
        "parent_identity": process_identity(os.getpid()),
        "worker_pid": worker.pid,
        "worker_pgid": worker_identity.get("pgid"),
        "worker_identity": worker_identity,
        "worker_command_substrings": required_substrings,
        "work_root": str(work_root),
        "argv_sha256": sha256_text("\n".join(argv)),
        "timeout_seconds": timeout_seconds,
        "worker_deadline_epoch": deadline_epoch,
        "watchdog_grace_seconds": HARNESS_WATCHDOG_GRACE_SECONDS,
        "cleanup_path": str(path.with_suffix(".cleanup.json")),
    }
    write_json(path, record)
    return record


def cleanup_harness_watchdog_record(path: pathlib.Path) -> dict[str, Any]:
    record = load_optional_json(path)
    if not isinstance(record, dict):
        return {"ok": True, "path": str(path), "reason": "record-missing"}
    worker_pid = int(record.get("worker_pid") or 0)
    if worker_pid > 0 and process_matches_identity(
        worker_pid,
        record.get("worker_identity") if isinstance(record.get("worker_identity"), dict) else None,
        [str(item) for item in record.get("worker_command_substrings", []) if str(item)],
    ):
        return {"ok": False, "path": str(path), "reason": "worker-still-running"}
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        return {"ok": False, "path": str(path), "reason": f"unlink-failed:{exc}"}
    return {"ok": True, "path": str(path), "reason": "worker-finished"}


def start_harness_watchdog(
    work_root: pathlib.Path,
    argv: list[str],
    timeout_seconds: int,
    worker: subprocess.Popen[str],
    worker_identity: dict[str, Any],
    deadline_epoch: float,
    command_substrings: list[str] | None = None,
) -> dict[str, Any]:
    HARNESS_WATCHDOG_ROOT.mkdir(parents=True, exist_ok=True)
    path = harness_watchdog_path(work_root, os.getpid(), worker.pid)
    record = write_harness_watchdog_record(
        path,
        work_root,
        argv,
        timeout_seconds,
        worker,
        worker_identity,
        deadline_epoch,
        command_substrings=command_substrings,
    )
    watchdog_argv = [
        sys.executable,
        str(pathlib.Path(__file__).resolve()),
        "harness-watchdog",
        "--record",
        str(path),
    ]
    try:
        watchdog = subprocess.Popen(
            watchdog_argv,
            cwd=str(REPO_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            start_new_session=True,
        )
        record["watchdog_pid"] = watchdog.pid
        record["watchdog_argv_sha256"] = sha256_text("\n".join(watchdog_argv))
        write_json(path, record)
    except Exception as exc:
        record["watchdog_start_error"] = str(exc)
        write_json(path, record)
    return record


def cleanup_stale_harness_watchdogs(work_root: pathlib.Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not HARNESS_WATCHDOG_ROOT.exists():
        return results
    for record_path in sorted(HARNESS_WATCHDOG_ROOT.glob("*.json")):
        record = load_optional_json(record_path)
        if not isinstance(record, dict):
            continue
        if str(record.get("work_root") or "") != str(work_root):
            continue
        parent_pid = int(record.get("parent_pid") or 0)
        parent_alive = parent_pid > 0 and process_matches_identity(
            parent_pid,
            record.get("parent_identity") if isinstance(record.get("parent_identity"), dict) else None,
        )
        worker_pid = int(record.get("worker_pid") or 0)
        worker_alive = worker_pid > 0 and process_matches_identity(
            worker_pid,
            record.get("worker_identity") if isinstance(record.get("worker_identity"), dict) else None,
            [str(item) for item in record.get("worker_command_substrings", []) if str(item)],
        )
        if parent_alive and worker_alive:
            continue
        cleanup: dict[str, Any]
        if worker_alive:
            cleanup = kill_recorded_process_group(record, reason="stale-parent-missing", grace_seconds=HARNESS_WATCHDOG_GRACE_SECONDS)
        else:
            cleanup = {"schema_id": "redcap-e2e-recorded-process-cleanup", "ok": True, "reason": "worker-already-gone"}
        try:
            write_json(record_path.with_suffix(".cleanup.json"), cleanup)
        except Exception:
            pass
        try:
            record_path.unlink()
        except OSError:
            pass
        results.append({
            "record": str(record_path),
            "parent_alive": parent_alive,
            "worker_alive": worker_alive,
            "cleanup": cleanup,
        })
    return results


def run_harness_watchdog(record_path: pathlib.Path) -> dict[str, Any]:
    started = iso_now()
    while True:
        record = load_optional_json(record_path)
        if not isinstance(record, dict):
            return {"ok": True, "reason": "record-removed", "record_path": str(record_path), "started_at": started, "finished_at": iso_now()}
        worker_pid = int(record.get("worker_pid") or 0)
        worker_alive = worker_pid > 0 and process_matches_identity(
            worker_pid,
            record.get("worker_identity") if isinstance(record.get("worker_identity"), dict) else None,
            [str(item) for item in record.get("worker_command_substrings", []) if str(item)],
        )
        if not worker_alive:
            try:
                record_path.unlink()
            except OSError:
                pass
            return {"ok": True, "reason": "worker-finished", "record_path": str(record_path), "started_at": started, "finished_at": iso_now()}
        parent_pid = int(record.get("parent_pid") or 0)
        parent_alive = parent_pid > 0 and process_matches_identity(
            parent_pid,
            record.get("parent_identity") if isinstance(record.get("parent_identity"), dict) else None,
        )
        now_epoch = time.time()
        deadline_epoch = float(record.get("worker_deadline_epoch") or 0)
        cleanup_reason = None
        if not parent_alive:
            cleanup_reason = "parent-missing"
        elif deadline_epoch and now_epoch > deadline_epoch + HARNESS_WATCHDOG_GRACE_SECONDS:
            cleanup_reason = "worker-deadline-exceeded"
        if cleanup_reason:
            cleanup = kill_recorded_process_group(record, reason=cleanup_reason, grace_seconds=HARNESS_WATCHDOG_GRACE_SECONDS)
            cleanup.update({
                "watchdog_started_at": started,
                "watchdog_finished_at": iso_now(),
                "record_path": str(record_path),
            })
            try:
                write_json(record_path.with_suffix(".cleanup.json"), cleanup)
            except Exception:
                pass
            if cleanup.get("ok") is True:
                try:
                    record_path.unlink()
                except OSError:
                    pass
            return cleanup
        time.sleep(HARNESS_WATCHDOG_POLL_SECONDS)


def communicate_worker_after_stop(worker: subprocess.Popen[str], timeout_seconds: float) -> tuple[str, str, bool]:
    try:
        stdout, stderr = worker.communicate(timeout=timeout_seconds)
        return stdout or "", stderr or "", False
    except subprocess.TimeoutExpired as exc:
        kill_process_group(worker, grace_seconds=1.0)
        try:
            stdout, stderr = worker.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                worker.kill()
            except OSError:
                pass
            stdout, stderr = "", ""
        return (
            stdout if isinstance(stdout, str) else (exc.stdout if isinstance(exc.stdout, str) else ""),
            stderr if isinstance(stderr, str) else (exc.stderr if isinstance(exc.stderr, str) else ""),
            True,
        )


def run_harness_timeout_regression_test(work_root: pathlib.Path) -> dict[str, Any]:
    work_root.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    timeout_root = work_root / "hard-timeout"
    timeout_root.mkdir(parents=True, exist_ok=True)
    timeout_argv = [sys.executable, "-c", "import time; time.sleep(30)"]
    timeout_worker = subprocess.Popen(
        timeout_argv,
        cwd=str(timeout_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    timeout_substrings = ["time.sleep(30)"]
    timeout_identity = process_identity(timeout_worker.pid, timeout_substrings)
    timeout_started = time.monotonic()
    timeout_deadline = time.monotonic() + 1
    timeout_watchdog = start_harness_watchdog(
        timeout_root,
        timeout_argv,
        1,
        timeout_worker,
        timeout_identity,
        time.time() + 1,
        command_substrings=timeout_substrings,
    )
    timed_out = False
    process_group_killed = False
    while timeout_worker.poll() is None:
        if time.monotonic() > timeout_deadline:
            timed_out = True
            process_group_killed = kill_process_group(
                timeout_worker,
                grace_seconds=1.0,
                expected_identity=timeout_identity,
                command_substrings=timeout_substrings,
            )
            break
        time.sleep(0.05)
    stdout, stderr, communicate_timed_out = communicate_worker_after_stop(timeout_worker, 2)
    timeout_cleanup = cleanup_harness_watchdog_record(pathlib.Path(str(timeout_watchdog.get("record_path"))))
    timeout_elapsed = time.monotonic() - timeout_started
    timeout_case = {
        "id": "hard-timeout-kills-worker",
        "ok": timed_out and process_group_killed and timeout_worker.poll() is not None and timeout_elapsed < 8,
        "timed_out": timed_out,
        "process_group_killed": process_group_killed,
        "worker_exit_code": timeout_worker.returncode,
        "communicate_timed_out": communicate_timed_out,
        "elapsed_seconds": round(timeout_elapsed, 3),
        "watchdog_cleanup": timeout_cleanup,
        "stdout_tail": stdout[-200:],
        "stderr_tail": stderr[-200:],
    }
    if not timeout_case["ok"]:
        failures.append("硬超时回归探针没有在短时间内清理 fake worker")
    cases.append(timeout_case)

    watchdog_root = work_root / "watchdog-parent-missing"
    watchdog_root.mkdir(parents=True, exist_ok=True)
    watchdog_argv = [sys.executable, "-c", "import time; time.sleep(30)"]
    watchdog_worker = subprocess.Popen(
        watchdog_argv,
        cwd=str(watchdog_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    watchdog_substrings = ["time.sleep(30)"]
    watchdog_identity = process_identity(watchdog_worker.pid, watchdog_substrings)
    record_path = harness_watchdog_path(watchdog_root, 999999, watchdog_worker.pid)
    record = write_harness_watchdog_record(
        record_path,
        watchdog_root,
        watchdog_argv,
        60,
        watchdog_worker,
        watchdog_identity,
        time.time() + 60,
        command_substrings=watchdog_substrings,
    )
    record["parent_pid"] = 999999
    record["parent_identity"] = {"pid": 999999, "exists": False}
    write_json(record_path, record)
    watchdog_started = time.monotonic()
    watchdog_result = run_harness_watchdog(record_path)
    _, _, watchdog_communicate_timed_out = communicate_worker_after_stop(watchdog_worker, 2)
    watchdog_elapsed = time.monotonic() - watchdog_started
    watchdog_case = {
        "id": "watchdog-cleans-parent-missing-worker",
        "ok": watchdog_result.get("ok") is True and watchdog_worker.poll() is not None and watchdog_elapsed < 8,
        "watchdog_result": watchdog_result,
        "worker_exit_code": watchdog_worker.returncode,
        "communicate_timed_out": watchdog_communicate_timed_out,
        "elapsed_seconds": round(watchdog_elapsed, 3),
    }
    if not watchdog_case["ok"]:
        failures.append("看门狗没有在父进程缺失时清理 fake worker")
    cases.append(watchdog_case)

    result = {
        "schema_id": "redcap-e2e-harness-timeout-regression-test",
        "ok": not failures,
        "work_root": str(work_root),
        "cases": cases,
        "failures": failures,
    }
    write_json(work_root / "redcap-e2e-harness-timeout-regression-test.json", result)
    return result


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
        "cleanup_wait_timed_out": result.get("cleanup_wait_timed_out"),
        "pty": result.get("pty"),
        "interactive_confirm_prompt_seen": result.get("interactive_confirm_prompt_seen"),
        "trust_prompt_confirmed": result.get("trust_prompt_confirmed"),
        "terminal_query_responses": result.get("terminal_query_responses"),
        "intentional_stop_after_completion": result.get("intentional_stop_after_completion"),
        "completion_reason": result.get("completion_reason"),
        "stop_requested_after_completion": result.get("stop_requested_after_completion"),
        "stdout_length": len(stdout),
        "stdout_sha256": sha256_text(stdout) if stdout else None,
        "stderr_length": len(stderr),
        "stderr_sha256": sha256_text(stderr) if stderr else None,
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
    }


def extract_codex_session_id(stderr: str) -> str | None:
    patterns = [
        r"session id:\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        r"codex resume\s+([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    ]
    for pattern in patterns:
        match = re.search(pattern, stderr, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


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
        ["kimi", "-p", "回复 ok"],
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
    codex_readiness = codex_cli_readiness_check()
    checks["checks"].extend(codex_readiness.get("checks", []))
    if codex_readiness.get("ok") is not True:
        checks["ok"] = False
        checks["failures"].extend(codex_readiness.get("failures", ["Codex CLI 可用性检查失败"]))
    return checks


def codex_cli_readiness_check() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_id": "redcap-e2e-codex-cli-readiness",
        "ok": True,
        "checks": [],
        "failures": [],
    }
    version = run_command(["codex", "--version"], timeout_seconds=15)
    payload["checks"].append({"name": "codex-version", **command_receipt(version)})
    if version.get("ok") is not True:
        payload["ok"] = False
        payload["failures"].append("Codex CLI 不可执行或无法读取版本")
        return payload
    with tempfile.TemporaryDirectory(prefix="redcap-codex-readiness-") as raw:
        tmp = pathlib.Path(raw)
        last_message = tmp / "last-message.txt"
        argv = [
            "codex",
            "--ask-for-approval",
            "never",
            "exec",
            "--model",
            CODEX_ROLE_MODEL,
            "-c",
            f'model_reasoning_effort="{CODEX_ROLE_REASONING_EFFORT}"',
            *codex_mcp_isolation_argv(),
            "--cd",
            str(tmp),
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--output-last-message",
            str(last_message),
        ]
        if CODEX_ROLE_DISABLE_PLUGINS:
            argv.extend(["--disable", "plugins"])
        for feature in CODEX_ROLE_EXTRA_DISABLED_FEATURES:
            argv.extend(["--disable", feature])
        argv.append("请只回答 codex-readiness-ok，不要使用工具。")
        smoke = run_command(argv, cwd=tmp, timeout_seconds=CODEX_CLI_READINESS_TIMEOUT_SECONDS)
        receipt = command_receipt(smoke)
        receipt.update({
            "name": "codex-exec-smoke",
            "last_message_exists": last_message.exists(),
            "last_message_size": last_message.stat().st_size if last_message.exists() else 0,
            "last_message_sha256": sha256_file(last_message) if last_message.exists() else None,
        })
        payload["checks"].append(receipt)
        if smoke.get("ok") is not True or not last_message.exists() or last_message.stat().st_size <= 0:
            payload["ok"] = False
            payload["failures"].append("Codex CLI 非交互执行探针失败，不能启动完整 Loom 角色 E2E")
    return payload


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


def source_workspace_prism_ledger_isolation_probe() -> dict[str, Any]:
    before = source_workspace_snapshot()
    result = run_command([
        str(REDCAP),
        "gate",
        "--task",
        "source workspace prism ledger isolation probe",
        "--risk-level",
        "low",
        "--tag",
        "source-workspace-guard-probe",
    ], timeout_seconds=60)
    guard = compare_source_workspace(before)
    failures: list[str] = []
    if result.get("ok") is not True:
        failures.append("redcap gate isolation probe command failed")
    if guard.get("ok") is not True:
        failures.append(f"redcap gate changed source workspace status: {guard.get('failures')}")
    return {
        "schema_id": "redcap-source-workspace-prism-ledger-isolation-probe",
        "ok": not failures,
        "command": command_receipt(result),
        "source_workspace_guard": guard,
        "failures": failures,
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


def ensure_project_git_repo(project: pathlib.Path, evidence: pathlib.Path | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_id": "redcap-e2e-project-git-baseline",
        "ok": True,
        "project": str(project),
        "already_present": (project / ".git").exists(),
        "command": None,
        "failures": [],
    }
    if not result["already_present"]:
        init = run_command(["git", "init"], cwd=project, timeout_seconds=30)
        result["command"] = command_receipt(init)
        result["ok"] = init["ok"]
        if not init["ok"]:
            result["failures"].append("外部项目 Git 初始化失败，无法可靠验证 Codex 项目级配置和 hook 承载")
    if evidence is not None:
        write_json(evidence / "project-git-baseline.json", result)
    return result


def toml_basic_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\"", "\\\"")


def codex_project_trust_config_arg(project: pathlib.Path) -> str:
    return f'projects."{toml_basic_string(str(project.resolve()))}".trust_level="trusted"'


def codex_project_trust_argv(project: pathlib.Path) -> list[str]:
    return ["-c", codex_project_trust_config_arg(project)]


def source_codex_home() -> pathlib.Path:
    raw_home = os.environ.get("CODEX_HOME")
    return pathlib.Path(raw_home).expanduser() if raw_home else pathlib.Path.home() / ".codex"


def prepare_isolated_codex_home(project: pathlib.Path, evidence: pathlib.Path | None = None) -> dict[str, Any]:
    source_home = source_codex_home()
    isolated_home = project / ".redcap" / "codex-home"
    auth_source = source_home / "auth.json"
    auth_target = isolated_home / "auth.json"
    config_target = isolated_home / "config.toml"
    payload: dict[str, Any] = {
        "schema_id": "redcap-e2e-isolated-codex-home",
        "ok": True,
        "mode": "isolated_home",
        "source_home": str(source_home),
        "isolated_home": str(isolated_home),
        "auth_copied": False,
        "config": str(config_target),
        "failures": [],
    }
    try:
        isolated_home.mkdir(parents=True, exist_ok=True)
        if not auth_source.exists():
            payload["ok"] = False
            payload["failures"].append(f"缺少 Codex 认证文件：{auth_source}")
        else:
            shutil.copy2(auth_source, auth_target)
            auth_target.chmod(0o600)
            payload["auth_copied"] = True
        config_target.write_text(
            "suppress_unstable_features_warning = true\n"
            "[features]\n"
            "hooks = true\n",
            encoding="utf-8",
        )
    except OSError as exc:
        payload["ok"] = False
        payload["failures"].append(f"无法准备隔离 Codex Home：{exc}")
    if evidence is not None:
        write_json(evidence / "isolated-codex-home.json", payload)
    return payload


def codex_child_env(isolated_home: dict[str, Any]) -> dict[str, str]:
    if isolated_home.get("ok") is True and isinstance(isolated_home.get("isolated_home"), str):
        return {"CODEX_HOME": isolated_home["isolated_home"]}
    return {}


def ensure_codex_project_trusted(project: pathlib.Path, evidence: pathlib.Path | None = None) -> dict[str, Any]:
    """Prepare command-scoped trust for a generated E2E project so project-local hooks load."""
    if CODEX_PROJECT_TRUST_MODE == "isolated_home":
        isolated = prepare_isolated_codex_home(project, evidence)
        payload = {
            "schema_id": "redcap-e2e-codex-project-trust",
            "ok": isolated.get("ok") is True,
            "project": str(project.resolve()),
            "config": isolated.get("config"),
            "trust_mode": CODEX_PROJECT_TRUST_MODE,
            "config_override_arg": codex_project_trust_config_arg(project),
            "added_or_updated": False,
            "before_sha256": None,
            "after_sha256": None,
            "isolated_home": isolated,
            "failures": list(isolated.get("failures") or []),
        }
        if evidence is not None:
            write_json(evidence / "codex-project-trust.json", payload)
        return payload
    config_path = source_codex_home() / "config.toml"
    project_path = str(project.resolve())
    header = f'[projects."{toml_basic_string(project_path)}"]'
    payload: dict[str, Any] = {
        "schema_id": "redcap-e2e-codex-project-trust",
        "ok": True,
        "project": project_path,
        "config": str(config_path),
        "trust_mode": CODEX_PROJECT_TRUST_MODE,
        "config_override_arg": codex_project_trust_config_arg(project),
        "added_or_updated": False,
        "before_sha256": None,
        "after_sha256": None,
        "failures": [],
    }
    if CODEX_PROJECT_TRUST_MODE != "persist":
        payload["reason"] = "使用 Codex CLI 单次 -c 覆盖加载项目级 hooks，不写入全局 config.toml。"
        if evidence is not None:
            write_json(evidence / "codex-project-trust.json", payload)
        return payload
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        before = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        payload["before_sha256"] = sha256_text(before) if before else None
        section_pattern = re.compile(
            rf"(?ms)^{re.escape(header)}\n(?P<body>.*?)(?=^\[|\Z)"
        )
        match = section_pattern.search(before)
        after = before
        if match:
            body = match.group("body")
            if 'trust_level = "trusted"' not in body:
                if re.search(r'(?m)^trust_level\s*=', body):
                    new_body = re.sub(r'(?m)^trust_level\s*=.*$', 'trust_level = "trusted"', body, count=1)
                else:
                    new_body = f'trust_level = "trusted"\n{body}'
                after = before[:match.start("body")] + new_body + before[match.end("body"):]
                payload["added_or_updated"] = True
        else:
            separator = "\n" if before.endswith("\n") or not before else "\n\n"
            after = (
                before
                + separator
                + "# Added by RedCap E2E to load project-local hooks for a generated external project.\n"
                + header
                + '\ntrust_level = "trusted"\n'
            )
            payload["added_or_updated"] = True
        if after != before:
            tmp = config_path.with_name(f".{config_path.name}.redcap-e2e-{os.getpid()}.tmp")
            tmp.write_text(after, encoding="utf-8")
            os.replace(tmp, config_path)
        payload["after_sha256"] = sha256_text(after) if after else None
    except OSError as exc:
        payload["ok"] = False
        payload["failures"].append(f"无法写入 Codex 项目信任配置：{exc}")
    if evidence is not None:
        write_json(evidence / "codex-project-trust.json", payload)
    return payload


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
        "runtime/bin/redcap complete-revival-e2e preflight --work-root <external-dir>",
        "runtime/bin/redcap complete-revival-e2e preflight-regression-test --work-root <external-dir>",
        "runtime/bin/redcap complete-revival-e2e carrier-probe --work-root <external-dir>",
        "runtime/bin/redcap complete-revival-e2e run --direction <text> --work-root <external-dir>",
        "runtime/bin/redcap complete-revival-e2e harness-timeout-regression-test --work-root <external-dir>",
        "runtime/bin/redcap complete-revival-e2e runner-negative-probe-regression-test --work-root <external-dir>",
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
        missing_hooks = [event for event in REQUIRED_CONFIGURED_HOOK_EVENTS if event not in hooks]
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
    carrier_preflight = contract.get("codex_cli_hook_carrier_preflight")
    if not isinstance(carrier_preflight, dict):
        failures.append("E2E 合同缺少 codex_cli_hook_carrier_preflight 硬入口")
    else:
        if carrier_preflight.get("status") != "hard_entry_gate":
            failures.append("codex_cli_hook_carrier_preflight.status 必须为 hard_entry_gate")
        preflight_events = carrier_preflight.get("required_events")
        if not isinstance(preflight_events, list):
            failures.append("codex_cli_hook_carrier_preflight.required_events 必须是列表")
        else:
            missing_preflight_events = [event for event in REQUIRED_HOOK_EVENTS if event not in preflight_events]
            if missing_preflight_events:
                failures.append(f"codex_cli_hook_carrier_preflight.required_events 缺少：{missing_preflight_events}")
        must_run_before = str(carrier_preflight.get("must_run_before") or "")
        failure_behavior = str(carrier_preflight.get("failure_behavior") or "")
        if 'env["REDCAP_E2E_WORKER"]' not in must_run_before:
            failures.append("codex_cli_hook_carrier_preflight.must_run_before 必须写明早于 worker 启动")
        for required_fragment in ["blocked_before_project_run=true", "auto_rerun_allowed=false", "禁止启动 Loom 角色"]:
            if required_fragment not in failure_behavior:
                failures.append(f"codex_cli_hook_carrier_preflight.failure_behavior 缺少：{required_fragment}")
    harness_timeout = contract.get("harness_timeout_and_cleanup")
    if not isinstance(harness_timeout, dict):
        failures.append("E2E 合同缺少 harness_timeout_and_cleanup 硬运行门禁")
    else:
        if harness_timeout.get("status") != "hard_runtime_guard":
            failures.append("harness_timeout_and_cleanup.status 必须为 hard_runtime_guard")
        worker_deadline_rule = str(harness_timeout.get("worker_deadline_rule") or "")
        if "timeout_seconds" not in worker_deadline_rule or "不得延长 worker 截止时间" not in worker_deadline_rule:
            failures.append("harness_timeout_and_cleanup.worker_deadline_rule 必须声明 timeout_seconds 是唯一硬截止且观察者不得延长")
        for key, fragment in {
            "interrupt_cleanup_rule": "worker_exit_reason=interrupt",
            "watchdog_rule": "独立看门狗",
            "identity_safety_rule": "身份校验",
            "failure_evidence_rule": "redcap-e2e-harness-summary.json",
        }.items():
            if fragment not in str(harness_timeout.get(key) or ""):
                failures.append(f"harness_timeout_and_cleanup.{key} 缺少关键约束：{fragment}")
        exit_values = harness_timeout.get("exit_reason_values")
        for expected in ["completed", "timeout", "interrupt", "crash"]:
            if not isinstance(exit_values, list) or expected not in exit_values:
                failures.append(f"harness_timeout_and_cleanup.exit_reason_values 缺少：{expected}")
    layered_preflight = contract.get("redcap_layered_preflight")
    if not isinstance(layered_preflight, dict):
        failures.append("E2E 合同缺少 redcap_layered_preflight 硬入口")
    else:
        if layered_preflight.get("status") != "hard_entry_gate":
            failures.append("redcap_layered_preflight.status 必须为 hard_entry_gate")
        required_checks = layered_preflight.get("required_checks")
        expected_checks = [
            "loom-runtime-self-check",
            "self-purification-self-check",
            "knowledge-search-self-purification",
            "knowledge-search-loom",
            "project-install-release-check",
        ]
        if not isinstance(required_checks, list):
            failures.append("redcap_layered_preflight.required_checks 必须是列表")
        else:
            missing_checks = [check for check in expected_checks if check not in required_checks]
            if missing_checks:
                failures.append(f"redcap_layered_preflight.required_checks 缺少：{missing_checks}")
        must_run_before = str(layered_preflight.get("must_run_before") or "")
        for required_fragment in ["carrier-probe", 'env["REDCAP_E2E_WORKER"]', "Loom 角色"]:
            if required_fragment not in must_run_before:
                failures.append(f"redcap_layered_preflight.must_run_before 缺少：{required_fragment}")
        failure_behavior = str(layered_preflight.get("failure_behavior") or "")
        for required_fragment in ["blocked_before_project_run=true", "auto_rerun_allowed=false", "禁止启动 Loom 角色"]:
            if required_fragment not in failure_behavior:
                failures.append(f"redcap_layered_preflight.failure_behavior 缺少：{required_fragment}")
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
        "layered-preflight-failure-cannot-start-project-run",
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
        if max_iterations != E2E_PATROL_MAX_ITERATIONS:
            failures.append(f"iteration_loop.max_iterations_before_cap_escalation 必须等于 {E2E_PATROL_MAX_ITERATIONS}")
        for key in ["failure_ingestion", "next_round_rule", "stop_rule"]:
            value = str(loop.get(key) or "")
            if "failure-backlog" not in value and key != "stop_rule":
                failures.append(f"iteration_loop.{key} 必须绑定 failure-backlog")
        if "ready_for_engineering_use" not in str(loop.get("next_round_rule") or ""):
            failures.append("iteration_loop.next_round_rule 必须读取 ready_for_engineering_use")
        if "auto_rerun_allowed" not in str(loop.get("next_round_rule") or ""):
            failures.append("iteration_loop.next_round_rule 必须读取 convergence-diagnosis.auto_rerun_allowed")
        if "source_signature" not in str(loop.get("next_round_rule") or ""):
            failures.append("iteration_loop.next_round_rule 必须说明源码签名变化后才允许修复后重跑")
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
    trpg_like = any(keyword in normalized for keyword in ["trpg", "跑团", "桌游角色扮演", "tabletop role"])
    if trpg_like or any(keyword in normalized for keyword in ["报名", "意向", "signup", "sign-up", "registration"]):
        contracts.append({
            "id": "signup-intent-data-contract",
            "trigger": "需求方向包含报名、意向或 TRPG 活动组织语境",
            "description": "活动、场次或事件数据必须能独立表达报名意向。",
            "required_data_shape": "每个承载报名意向的活动、场次或事件记录都必须包含自己的非空 signups 数组；兼容非空 signupIntent 字段，但优先使用 signups。",
            "signups_item_hint": "signups 每项建议包含玩家、角色或身份、意向状态、备注中的至少两类信息。",
            "must_be_reflected_by_roles": [
                "product_manager",
                "architect",
                "developer",
                "tester",
                "reviewer"
            ],
            "validation_hint": "验证脚本或负向探针必须证明：把任一活动、场次或事件记录的 signups 置为空数组且 signupIntent 置为空后，验证命令非零退出。"
        })
    if trpg_like or (("角色" in direction and "玩家" in direction) or ("character" in normalized and "player" in normalized)):
        contracts.append({
            "id": "character-player-relation-contract",
            "trigger": "需求方向同时包含角色和玩家，或处于 TRPG 活动组织语境",
            "description": "角色与玩家关系必须在数据和界面中可追踪。",
            "required_data_shape": "角色记录必须能引用或展示对应玩家；若存在 players[] 与 characters[]，character.playerId 或等价字段必须命中同活动、同场次或同文件内真实玩家 id，不能只依赖 playerName 文案兜底。",
            "must_be_reflected_by_roles": [
                "architect",
                "developer",
                "tester",
                "reviewer"
            ],
            "validation_hint": "验证脚本或负向探针必须证明：破坏 character.playerId 或等价引用后验证命令非零退出；浏览器行为验收会在适用时检查角色名和玩家名在 UI 中相邻呈现。"
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
            "项目入口必须支持本地 HTTP 服务访问，也必须支持 file:// 本地文件协议直接打开",
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
            "前端不得只能依赖 fetch 本地 JSON；如果需要读取本地数据，必须提供 file:// 可用的内嵌数据、降级数据或同步加载方案",
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
        "项目入口必须同时支持本地 HTTP 服务访问和 file:// 本地文件协议直接打开",
        "存在 architecture.md，说明结构、边界、风险和测试方式",
        ".redcap/evidence/e2e 中存在实现日志、测试结果、文件清单和验收摘要",
        ".redcap/evidence/e2e/loom-role-session-manifest.json 证明五个 Loom 角色来自独立 Codex CLI 会话",
        ".redcap/evidence/e2e/loom-role-session-manifest-pre-review.json 供 reviewer 审核上游四个角色；最终五角色清单由运行器在 reviewer 退出后生成",
        "默认实现不得依赖联网安装或重型测试栈；如果确需外部依赖，必须在 risk-register.json 中写明理由和降级方案",
        ".redcap/evidence/e2e/self-purification-candidates.json 和 persona-distillation-decision.json 证明自我净化与人格边界已触发",
        ".redcap/evidence/e2e/package-prism-check.json 证明安装包内棱镜自检通过",
        ".redcap/evidence/e2e/final-runner-test-results.json 证明运行器独立重跑了项目验证",
        ".redcap/evidence/e2e/final-marker-validation.json 证明写完成标记前的项目状态再次通过验证",
        ".redcap/evidence/e2e/file-browser-inspection.json 证明项目入口可通过 file:// 本地文件协议打开",
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


def build_role_prompt(
    project: pathlib.Path,
    evidence: pathlib.Path,
    role: str,
    direction: str,
    feedback_packet: pathlib.Path | None = None,
) -> str:
    inputs, outputs = role_handoff(role)
    required_inputs = unique_preserve_order(["requirements.json", "acceptance-criteria.json", *inputs])
    input_records = role_path_records(project, evidence, required_inputs, for_output=False)
    output_records = role_path_records(project, evidence, outputs, for_output=True)
    feedback_section = ""
    if feedback_packet is not None:
        feedback_section = f"""

    额外修复反馈包：
    - 路径：{feedback_packet}
    - 必须先读取该文件，再修改 developer 范围内的项目产物。
    - 反馈包只包含上一轮失败事实、证据文件路径、哈希和失败信号；它不是修复方案，不得把它当作 runner 或 tester 在替你设计实现。
    - 你必须正面修复其中列出的 contract_violation、validation_failure 或 readiness_failure，并重新运行本地验证命令。
    - 禁止通过删除验证、降低错误为 warning、移除领域数据、跳过 file:// 支持或让 tester 放宽标准来“通过”。
        """
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
    - role artifact 至少包含 schema_id、role、status、handoff_inputs、handoff_outputs、evidence_files、notes、upstream_challenges、accepted_upstream_assumptions、rejected_upstream_assumptions。
    - role-artifacts/{role}.json 的 status 必须精确写成 "completed"；不要写 implemented、complete、done、in_progress 或其他近义词。
    - upstream_challenges 必须是数组；除 product_manager 没有真实上游可写空数组外，其他角色至少记录一条对上游输入的质疑、风险复核、验收挑战或明确接受理由。每条建议包含 target、concern、disposition、reason。
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
    - 写完本角色要求的全部文件后，立即用一句中文说明本角色产物已交付并停止，不要继续追加无关分析。
    - 不要在最终回复中写机器完成标记；运行器只用本角色必需文件是否真实写出判断完成。
    {feedback_section}
    """
    role_specific = {
        "product_manager": """
        你的任务：
        1. 阅读 requirements.json 和 acceptance-criteria.json。
        2. 运行 `.redcap/runtime/bin/redcap knowledge-gateway search loom`，把结果写入 knowledge-retrieval-evidence.json。
           该文件必须包含 search_ran=true、query="loom"、command、exit_code、matches；如果 matches 为空，必须写 no_relevant_entry_reason。
        3. 明确问题陈述、范围边界、验收重点；如果存在 domain_contracts，必须把每项契约列为验收重点，并写入 role-artifacts/product_manager.json。
           product_manager 没有真实上游角色，role-artifacts/product_manager.json 的 upstream_challenges 可以是空数组，但 accepted_upstream_assumptions 必须说明它如何接受用户 direction 并收窄成可验收需求。
        """,
        "architect": """
        你的任务：
        1. 阅读产品经理交付和验收标准。
        2. 立即写 architecture.md，必须包含：目标、目录结构、数据模型、交互流程、运行方式、验证方式、风险与回滚。
           如果存在 domain_contracts，architecture.md 的数据模型和验证方式必须逐项承接；例如 signup-intent-data-contract 必须设计每个活动、场次或事件自己的非空 signups 数组或非空 signupIntent 字段，并说明验证脚本如何逐记录检查。
           如果存在 character-player-relation-contract，必须设计 players[] 与 characters[] 的真实引用关系；character.playerId 或等价字段必须命中同活动、同场次或同文件内真实玩家 id，不能只靠 playerName 文案兜底。
        3. 默认选择无外部依赖、无需联网安装、可直接本地验证的方案；除非需求明确要求，不要引入 Vite、Playwright、数据库或服务端框架。
           前端入口必须支持 file:// 直接打开；如果界面需要本地数据，不要只依赖浏览器 fetch 本地 JSON，必须设计内嵌数据、降级数据或其他 file:// 可用方案。
        4. 立即写 risk-register.json，至少包含 risks 数组；每项包含 id、risk、impact、mitigation、owner。
        5. 立即写 role-artifacts/architect.json，status="completed"，并列出读取的输入和写出的文件。
           role-artifacts/architect.json 必须包含 upstream_challenges，至少写一条对产品需求或验收标准的架构风险复核；即使接受上游，也要说明为什么接受。
        6. 不要读取 manifest.json，不要检查 role-workspaces，不要扫描 .redcap 全目录。
        """,
        "developer": """
        你的任务：
        1. 按 architecture.md 实现一个可运行的本地项目。
        2. 优先选择简单、无外部依赖、无需联网安装、可本地验证的技术栈；如果 architecture.md 要求重型依赖但需求并不需要，你应收窄为纯 HTML/CSS/JS + Node 内置模块验证，并在 implementation-log.json 说明原因。
        3. 前端入口必须支持 file:// 直接打开；如果需要展示本地数据，不要只写 fetch("data/xxx.json") 这种在 file:// 下可能失败的路径，必须提供 file:// 可用的数据加载方式，并在 README.md 说明 HTTP 和 file:// 两种打开方式。
           如果验证脚本检查远端依赖，只能把真实 http://、https://、协议相对 URL、CDN 主机或 src/href/import 中的远端资源判为失败；不得把 README 或界面文案里的 file://、普通 JS 注释中的 //、本地路径中的 // 当成远端依赖。
        4. 必须让实现和本地验证命令覆盖 acceptance-criteria.json 的 domain_contracts；例如 signup-intent-data-contract 必须在每个承载报名意向的真实活动、场次或事件记录中提供自己的非空 signups 数组或非空 signupIntent 字段，且验证脚本要逐记录检查该字段，不能只把报名意向放进玩家备注或按钮文案，也不能只检查全局至少有一条报名。
           如果存在 character-player-relation-contract，验证脚本必须检查 character.playerId 或等价字段命中同活动、同场次或同文件内真实 players[]；只要 playerId 被改成不存在的玩家 id，即使 playerName 仍存在，验证命令也必须非零退出。
        5. 页面必须提供真实可观察交互：至少一个 button 或 role=button 控件，点击后必须改变可见文本和稳定 DOM 摘要，例如切换活动、场次或筛选状态；不能只交付静态信息页。
           该交互必须不依赖联网、不依赖安装包，并且点击后仍能看见报名意向和角色-玩家关系。
        6. implementation-log.json 必须逐项说明每个 domain_contracts 的数据结构、界面呈现、真实交互方式和验证脚本检查方式；character-player-relation-contract 不能只写“角色和玩家可见”，必须写明真实引用校验。
        7. 写 implementation-log.json 和 role-artifacts/developer.json；role-artifacts/developer.json 的 status 必须精确是 "completed"，不能写 implemented。
           role-artifacts/developer.json 必须包含 upstream_challenges，至少写一条对架构、风险或验收标准的实现侧挑战；即使接受上游，也要说明为什么接受。
        8. 如果提供验证脚本，机器验证输出必须写 verification-results.json 或其他非角色文件，不能写或覆盖 test-results.json；test-results.json 只属于 tester 角色。
        """,
        "tester": """
        你的任务：
        1. 如果项目根目录存在 blocked-package.json，立即读取它，写 test-results.json、negative-probes.json 和 role-artifacts/tester.json，标记 status="blocked_by_upstream"，passed=false，然后停止；不要等待、不要修复。
        2. 如果没有上游阻塞，先写进行中证据，再运行任何验证：
           - test-results.json：role="tester"，status="in_progress"，passed=false，commands=[]，positive_checks=[]；
           - negative-probes.json：role="tester"，status="in_progress"，passed=false，probes=[]；
           - role-artifacts/tester.json：role="tester"，status="in_progress"，evidence_files 列出上述两个文件。
        3. 只做有限验证：最多一个正向验证命令，最多两个负向或静态探针。优先使用 README、package.json scripts、scripts/validate.mjs、scripts/verify.mjs 或 scripts/verify.sh 中明确给出的本地验证命令；不要为了“更全面”继续追加探索。
           负向或静态探针必须使用 Node 标准库脚本或已经写好的验证脚本；不要用未引用的 shell 通配符、find -name *.xxx、zsh glob 或会被 shell 预展开的命令。
           如果需求包含报名意向，负向或静态探针必须验证 signup-intent-data-contract：每个承载报名意向的活动、场次或事件记录都有自己的非空报名数据；优先接受 signups 数组（每项可以包含玩家、角色、意向或备注），也可以兼容 signupIntent 字段。测试必须证明把任一活动记录的 signups 置为空数组且 signupIntent 置为空时，项目验证命令非零退出；如果验证脚本只检查全局至少有一条报名，test-results.json 和 negative-probes.json 必须标记 failed，不得替开发者修复。
           如果需求同时包含角色和玩家，负向或静态探针必须验证 character-player-relation-contract：当 character.playerId 或等价字段被改成不存在的玩家 id 时，项目验证命令必须非零退出；如果验证脚本没有覆盖该失败路径，test-results.json 和 negative-probes.json 必须标记 failed，不得替开发者修复。
        4. 每执行完一个验证动作，立即更新对应 JSON；验证动作全部结束后，立即把三个文件更新为 completed 或 failed。
        5. test-results.json 必须标记 role="tester"，并记录 commands、positive_checks、passed；negative-probes.json 必须标记 role="tester"，并记录 probes、passed。status 与 passed 必须一致：completed 对应 passed=true，failed 对应 passed=false。
        6. 如果测试失败，必须把失败写清楚，不要替开发者修复。
        7. role-artifacts/tester.json 必须包含 upstream_challenges，至少写一条对开发验证、实现声明或验收标准的测试侧挑战；即使接受上游，也要说明为什么接受。
        """,
        "reviewer": """
        你的任务：
        1. 审阅需求、架构、实现、测试和角色证据。
           注意：loom-role-session-manifest-pre-review.json 只用于审核上游四个角色；reviewer 自己的 session_id 会在你退出后由运行器写入最终 loom-role-session-manifest.json，因此不要因为最终清单在评审前缺少 reviewer 自身而阻塞。
           如果 requirements.json 或 acceptance-criteria.json 包含 domain_contracts，必须逐项审核产品、架构、开发和测试是否承接；任何未承接项必须进入 blocking_findings 和 failure-backlog.open_items。
           对 signup-intent-data-contract 的审核必须包含：开发验证脚本是否逐活动、逐场次或逐事件检查非空报名意向，tester 是否做了清空单个活动 signups 和 signupIntent 后验证命令非零退出的负向或静态探针；只看到全局至少一条报名不算通过。
           对 character-player-relation-contract 的审核必须包含：开发验证脚本是否检查 playerId 命中真实玩家、tester 是否做了破坏 playerId 后验证命令非零退出的负向或静态探针；只看到 playerName 或界面文案不算通过。
           对本地入口的审核必须包含：README、架构和实现是否支持本地 HTTP 服务访问与 file:// 直接打开；如果前端只依赖 fetch 本地 JSON 且没有 file:// 降级方案，必须阻塞。
        2. 写 review-verdict.json；必须包含：
           - "terminal_completion": false；
           - "blocking_findings": [] 或阻塞项数组，禁止用 blocking_failures、open_issues 等近义字段替代；
           - "runner_owned_follow_up": ["completion-marker.json", "iteration-verdict.json", "final-prism-review.json", "final-runner-test-results.json"]，必须是这四个精确文件名字符串，不要写成说明句。
           - "role_opposition_matrix": 非空数组，必须覆盖 product_manager、architect、developer、tester；每项必须精确包含 role、challenge_summary、reviewer_disposition 三个非空字符串字段，分别说明角色名、上游挑战证据摘要、reviewer 是否接受及原因。可以额外写 reason 等补充字段，但不能用 challenged、reviewer_acceptance 等近义字段替代这三个必需字段。
           同时在边界说明中写明 terminal_completion=false 表示 reviewer 只能给阶段评审，不能自证本轮 E2E 终局完成或 RedCap 完整复活。
        3. 写 prism-assisted-review.json；本轮必须记录 used=true，reviews 必须是非空数组，cap_decision 必须非空，skip_reason 必须为 null 或空字符串。
           prism_assistance_request 是整份文件的顶层字段，必须写在 prism-assisted-review.json 顶层，精确形如：
           "prism_assistance_request": {"requested": true, "owner": "e2e-runner", "reason": "reviewer 角色不能直接调度完整棱镜，最终棱镜由运行器统一调度"}。
           禁止只把 prism_assistance_request 写在 reviews[0] 或任何 reviews[] 条目内部；reviews[] 内部不算有效请求，嵌套位置不算有效请求。
           至少在 reviews[0] 中说明一次对需求、架构、代码、测试或文档的棱镜协助或包内棱镜检查如何影响裁决。
        4. 写 self-purification-candidates.json，必须包含至少一个候选和对应 decisions 数组。candidate 可以来自本轮 E2E 暴露的流程缺陷、质量约束、角色协作经验、验证经验或 no-promote 经验；decision 只允许 promote_public、keep_private、no_promote、defer_with_owner；每个 decision 必须包含 reason。即使本轮不晋升，也要用 no_promote 或 defer_with_owner 说明原因，不能只写 no_candidate_reason。
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
        str(message_path),
    ]
    if CODEX_ROLE_DISABLE_PLUGINS:
        argv.extend(["--disable", "plugins"])
    for feature in CODEX_ROLE_EXTRA_DISABLED_FEATURES:
        argv.extend(["--disable", feature])
    for state_dir in provider_state_dirs_for_role(role):
        argv.extend(["--add-dir", str(state_dir)])
    argv.append(prompt)
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
        reviews = assisted.get("reviews")
        if not isinstance(request, dict) or request.get("requested") is not True:
            nested_request_seen = False
            if isinstance(reviews, list):
                nested_request_seen = any(
                    isinstance(item, dict)
                    and isinstance(item.get("prism_assistance_request"), dict)
                    and item["prism_assistance_request"].get("requested") is True
                    for item in reviews
                )
            if nested_request_seen:
                failures.append("reviewer 的 prism_assistance_request 必须写在 prism-assisted-review.json 顶层；只写在 reviews[] 内部不算有效请求")
            else:
                failures.append("reviewer 必须在 prism-assisted-review.json 顶层记录运行器统一调度棱镜的请求")
        if assisted.get("used") is not True:
            failures.append("reviewer 必须把棱镜边界或包内棱镜要求如何影响裁决记录为 used=true")
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
        candidates = purification.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            failures.append("self-purification-candidates.candidates 必须至少包含一个候选，不能用 no_candidate_reason 替代触发")
        decisions = collect_self_purification_decisions(purification)
        if not decisions:
            failures.append("self-purification-candidates 必须至少包含一个处理决定，可写在顶层 decisions 或候选内 decisions")
        for decision in decisions:
            if decision.get("decision") not in SELF_PURIFICATION_ALLOWED_DECISIONS:
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
        opposition = verdict.get("role_opposition_matrix")
        if not isinstance(opposition, list) or not opposition:
            failures.append("review-verdict.role_opposition_matrix 必须是非空数组，证明 reviewer 审核了角色对抗证据")
        else:
            covered_roles = {str(item.get("role")) for item in opposition if isinstance(item, dict)}
            missing_roles = sorted({"product_manager", "architect", "developer", "tester"} - covered_roles)
            if missing_roles:
                failures.append(f"review-verdict.role_opposition_matrix 缺少角色：{missing_roles}")
            for item in opposition:
                if not isinstance(item, dict):
                    failures.append("review-verdict.role_opposition_matrix 条目必须是对象")
                    continue
                for field in ["role", "challenge_summary", "reviewer_disposition"]:
                    if not isinstance(item.get(field), str) or not item[field].strip():
                        failures.append(f"review-verdict.role_opposition_matrix 条目缺少字段：{field}")
    return failures


def validate_tester_outputs(evidence: pathlib.Path) -> list[str]:
    failures: list[str] = []
    test_results = load_optional_json(evidence / "test-results.json")
    if test_results is None:
        failures.append("tester 必须写入可解析的 test-results.json")
    else:
        if test_results.get("role") != "tester":
            failures.append("test-results.json.role 必须是 tester")
        if test_results.get("status") != "completed":
            failures.append("test-results.json.status 必须是 completed，不能停留在 in_progress")
        if test_results.get("passed") is not True:
            failures.append("test-results.json.passed 必须为 true")
        commands = test_results.get("commands")
        if not isinstance(commands, list) or not commands:
            failures.append("test-results.json.commands 必须记录至少一个正向验证命令")
        positive_checks = test_results.get("positive_checks")
        if not isinstance(positive_checks, list) or not positive_checks:
            failures.append("test-results.json.positive_checks 必须记录至少一个正向检查")

    negative_probes = load_optional_json(evidence / "negative-probes.json")
    if negative_probes is None:
        failures.append("tester 必须写入可解析的 negative-probes.json")
    else:
        if negative_probes.get("role") != "tester":
            failures.append("negative-probes.json.role 必须是 tester")
        if negative_probes.get("status") != "completed":
            failures.append("negative-probes.json.status 必须是 completed，不能停留在 in_progress")
        if negative_probes.get("passed") is not True:
            failures.append("negative-probes.json.passed 必须为 true")
        probes = negative_probes.get("probes")
        if not isinstance(probes, list) or not probes:
            failures.append("negative-probes.json.probes 必须记录至少一个负向或静态探针")
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
        if artifact.get("status") != "completed":
            failures.append(f"role-artifacts/{role}.json.status 必须是 completed，不能停留在 {artifact.get('status')!r}")
        for field in ["upstream_challenges", "accepted_upstream_assumptions", "rejected_upstream_assumptions"]:
            if field not in artifact:
                failures.append(f"role-artifacts/{role}.json 缺少角色对抗字段：{field}")
        upstream_challenges = artifact.get("upstream_challenges")
        if not isinstance(upstream_challenges, list):
            failures.append(f"role-artifacts/{role}.json.upstream_challenges 必须是数组")
        elif role != "product_manager" and not upstream_challenges:
            failures.append(f"role-artifacts/{role}.json.upstream_challenges 必须至少包含一条上游挑战或明确接受理由")
        if isinstance(upstream_challenges, list):
            for item in upstream_challenges:
                if not isinstance(item, dict):
                    failures.append(f"role-artifacts/{role}.json.upstream_challenges 条目必须是对象")
                    continue
                for field in ["target", "concern", "disposition", "reason"]:
                    if not isinstance(item.get(field), str) or not item[field].strip():
                        failures.append(f"role-artifacts/{role}.json.upstream_challenges 条目缺少字段：{field}")
        accepted = artifact.get("accepted_upstream_assumptions")
        rejected = artifact.get("rejected_upstream_assumptions")
        if not isinstance(accepted, list):
            failures.append(f"role-artifacts/{role}.json.accepted_upstream_assumptions 必须是数组")
        if not isinstance(rejected, list):
            failures.append(f"role-artifacts/{role}.json.rejected_upstream_assumptions 必须是数组")
    if role == "tester":
        failures.extend(validate_tester_outputs(evidence))
    if role == "reviewer":
        failures.extend(validate_reviewer_outputs(evidence))
    return failures


def domain_contract_ids(evidence: pathlib.Path) -> set[str]:
    ids: set[str] = set()
    for name in ["requirements.json", "acceptance-criteria.json"]:
        payload = load_optional_json(evidence / name)
        if not isinstance(payload, dict):
            continue
        direction = payload.get("direction")
        if isinstance(direction, str) and direction.strip():
            for contract in domain_contracts_for_direction(direction):
                if isinstance(contract, dict) and isinstance(contract.get("id"), str):
                    ids.add(contract["id"])
        contracts = payload.get("domain_contracts")
        if isinstance(contracts, list):
            for item in contracts:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    ids.add(item["id"])
                elif isinstance(item, str):
                    ids.add(item)
        criteria = payload.get("criteria")
        if isinstance(criteria, list):
            for item in criteria:
                if not isinstance(item, str):
                    continue
                if "signup-intent-data-contract" in item:
                    ids.add("signup-intent-data-contract")
                if "character-player-relation-contract" in item:
                    ids.add("character-player-relation-contract")
    return ids


def critical_categories_from_text(text: str) -> set[str]:
    lowered = text.casefold()
    categories: set[str] = set()
    if any(marker in lowered for marker in ["远端依赖", "remote dependency", "remote-dependency", "cdn", "unpkg", "jsdelivr", "https://", "http://"]):
        categories.add("remote-dependency")
    if any(marker in lowered for marker in ["signups", "signupintent", "报名", "意向"]) and any(
        marker in lowered
        for marker in ["warning", "warn", "为空", "空数组", "empty", "缺少", "非空", "hard failure", "failed"]
    ):
        categories.add("signup-empty")
    if any(marker in lowered for marker in ["file://", "本地文件协议"]) or ("fetch" in lowered and any(marker in lowered for marker in ["local", "本地"])):
        categories.add("file-protocol")
    return categories


def append_critical_findings(
    findings: list[dict[str, Any]],
    *,
    source: str,
    severity: str,
    messages: Any,
) -> None:
    if not isinstance(messages, list):
        return
    for index, message in enumerate(messages):
        text = str(message)
        for category in sorted(critical_categories_from_text(text)):
            findings.append({
                "source": source,
                "index": index,
                "severity": severity,
                "category": category,
                "message": text[:1000],
            })


def developer_validation_payload(evidence: pathlib.Path, project: pathlib.Path) -> dict[str, Any] | None:
    for candidate in [
        evidence / "verification-results.json",
        project / "verification-results.json",
        project / "test-results.json",
    ]:
        payload = load_optional_json(candidate)
        if payload is not None:
            payload["_redcap_source_path"] = str(candidate)
            return payload
    return None


def failure_set_from_developer_readiness(gate: dict[str, Any]) -> set[str]:
    failures: set[str] = set()
    for finding in gate.get("critical_findings", []):
        if not isinstance(finding, dict):
            continue
        category = str(finding.get("category") or "unknown")
        severity = str(finding.get("severity") or "unknown")
        failures.add(f"developer-readiness:{category}:{severity}")
    for check in gate.get("checks", []):
        if isinstance(check, dict) and check.get("passed") is not True:
            failures.add(f"developer-readiness:{check.get('name')}")
    for failure in gate.get("failures", []):
        categories = critical_categories_from_text(str(failure))
        if categories:
            for category in categories:
                failures.add(f"developer-readiness:{category}:failure")
        else:
            failures.add(f"developer-readiness:{sha256_text(str(failure))[:12]}")
    return failures


def tester_failure_set(evidence: pathlib.Path, tester_receipt: dict[str, Any]) -> set[str]:
    failures: set[str] = set()
    for failure in tester_receipt.get("failures", []):
        failures.add(f"tester:receipt:{sha256_text(str(failure))[:12]}")
    test_results = load_optional_json(evidence / "test-results.json")
    if isinstance(test_results, dict):
        for check in test_results.get("positive_checks", []):
            if isinstance(check, dict) and check.get("passed") is not True:
                name = str(check.get("name") or "positive")
                categories = critical_categories_from_text(json.dumps(check, ensure_ascii=False))
                if categories:
                    for category in categories:
                        failures.add(f"tester:positive:{name}:{category}")
                else:
                    failures.add(f"tester:positive:{name}")
        if test_results.get("passed") is not True:
            failures.add(f"tester:test-results:{test_results.get('status')}")
    negative_probes = load_optional_json(evidence / "negative-probes.json")
    if isinstance(negative_probes, dict):
        for probe in negative_probes.get("probes", []):
            if isinstance(probe, dict) and probe.get("passed") is not True:
                name = str(probe.get("name") or "probe")
                categories = critical_categories_from_text(json.dumps(probe, ensure_ascii=False))
                if categories:
                    for category in categories:
                        failures.add(f"tester:probe:{name}:{category}")
                else:
                    failures.add(f"tester:probe:{name}")
        if negative_probes.get("passed") is not True:
            failures.add(f"tester:negative-probes:{negative_probes.get('status')}")
    artifact = load_optional_json(role_artifact_path(evidence, "tester"))
    if isinstance(artifact, dict):
        for challenge in artifact.get("upstream_challenges", []):
            if not isinstance(challenge, dict):
                continue
            disposition = str(challenge.get("disposition") or "")
            if "reject" in disposition or "failed" in disposition or "partial" in disposition:
                categories = critical_categories_from_text(json.dumps(challenge, ensure_ascii=False))
                if categories:
                    for category in categories:
                        failures.add(f"tester:challenge:{category}")
                else:
                    failures.add(f"tester:challenge:{sha256_text(json.dumps(challenge, ensure_ascii=False))[:12]}")
    return failures


def developer_repair_decision(
    *,
    source: str,
    failure_set: set[str],
    previous_failure_set: set[str] | None,
    resolved_failures: set[str],
    repair_rounds_used: int,
) -> dict[str, Any]:
    decision = {
        "source": source,
        "failure_set": sorted(failure_set),
        "previous_failure_set": sorted(previous_failure_set or []),
        "resolved_failures": sorted(resolved_failures),
        "repair_rounds_used": repair_rounds_used,
        "max_repair_rounds": LOOM_DEVELOPER_REPAIR_MAX_ROUNDS,
        "schedule_repair": False,
        "reason": "",
        "eliminated_failures": [],
        "regressed_failures": [],
    }
    if not failure_set:
        decision["reason"] = "no_failure"
        return decision
    if repair_rounds_used >= LOOM_DEVELOPER_REPAIR_MAX_ROUNDS:
        decision["reason"] = "repair-loop-exhausted"
        return decision
    if previous_failure_set is not None:
        eliminated = previous_failure_set - failure_set
        regressed = failure_set & resolved_failures
        decision["eliminated_failures"] = sorted(eliminated)
        decision["regressed_failures"] = sorted(regressed)
        if regressed:
            decision["reason"] = "previously-fixed-failure-reappeared"
            return decision
        if not eliminated:
            decision["reason"] = "no-failure-set-progress"
            return decision
    decision["schedule_repair"] = True
    decision["reason"] = "bounded-repair-scheduled"
    return decision


def evidence_hash_record(path: pathlib.Path, *, base: pathlib.Path) -> dict[str, Any]:
    record = evidence_file_record(path, base=base)
    if path.exists():
        record["excerpt"] = read_text_excerpt(path, max_chars=1800)
    return record


def write_developer_repair_feedback(
    evidence: pathlib.Path,
    *,
    repair_round: int,
    source: str,
    failure_set: set[str],
    developer_gate: dict[str, Any] | None,
    tester_receipt: dict[str, Any] | None,
    decision: dict[str, Any],
) -> pathlib.Path:
    feedback_dir = evidence / "developer-repair-feedback"
    feedback_path = feedback_dir / f"round-{repair_round}.json"
    source_artifacts = [
        evidence / "implementation-log.json",
        role_artifact_path(evidence, "developer"),
        evidence / "verification-results.json",
        evidence / "test-results.json",
        evidence / "negative-probes.json",
        role_artifact_path(evidence, "tester"),
    ]
    if developer_gate and developer_gate.get("path"):
        source_artifacts.append(pathlib.Path(str(developer_gate["path"])))
    payload = {
        "schema_id": "redcap-e2e-developer-repair-feedback",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "repair_round": repair_round,
        "source": source,
        "lossless_rule": "This packet carries structured failure facts, file hashes, and excerpts only; it must not prescribe implementation fixes.",
        "contract_violation_signals": sorted(failure_set),
        "decision": decision,
        "developer_readiness_gate": developer_gate,
        "tester_receipt": tester_receipt,
        "source_artifacts": [
            evidence_hash_record(path, base=evidence)
            for path in source_artifacts
            if path.exists()
        ],
        "forbidden_interpretation": [
            "Do not treat this feedback as tester repairing implementation.",
            "Do not lower validation severity from failure to warning.",
            "Do not remove domain data or local file support to bypass the failing checks.",
        ],
    }
    write_json(feedback_path, payload)
    return feedback_path


def snapshot_role_round(evidence: pathlib.Path, role: str, round_name: str) -> None:
    target = evidence / "role-round-snapshots" / round_name / role
    target.mkdir(parents=True, exist_ok=True)
    candidates = [
        role_artifact_path(evidence, role),
        evidence / "role-runs" / f"{role}.json",
        evidence / "role-prompts" / f"{role}.md",
        evidence / "role-messages" / f"{role}.txt",
        evidence / "role-raw" / f"{role}.stdout.txt",
        evidence / "role-raw" / f"{role}.stderr.txt",
        evidence / "test-results.json",
        evidence / "negative-probes.json",
        evidence / "verification-results.json",
    ]
    copied: list[dict[str, Any]] = []
    for source in candidates:
        if not source.exists():
            continue
        destination_name = "__".join(source.relative_to(evidence).parts)
        destination = target / destination_name
        shutil.copyfile(source, destination)
        copied.append(evidence_file_record(destination, base=evidence))
    write_json(target / "snapshot.json", {
        "schema_id": "redcap-e2e-role-round-snapshot",
        "created_at": iso_now(),
        "role": role,
        "round_name": round_name,
        "files": copied,
    })


def run_developer_readiness_gate(project: pathlib.Path, evidence: pathlib.Path, round_index: int) -> dict[str, Any]:
    argv, source = detect_validation_command(project)
    result: dict[str, Any] = {
        "schema_id": "redcap-e2e-developer-readiness-gate",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "round_index": round_index,
        "path": str(evidence / "developer-readiness-gate" / f"round-{round_index}.json"),
        "detected_command": argv,
        "command_source": source,
        "domain_contract_ids": sorted(domain_contract_ids(evidence)),
        "critical_findings": [],
        "checks": [],
        "failures": [],
        "ok": False,
    }
    if argv is None:
        result["failures"].append("developer 未提供可发现的本地验证命令")
        write_json(pathlib.Path(str(result["path"])), result)
        return result
    validation_run = run_command(argv, cwd=project, timeout_seconds=120)
    validation_receipt = command_receipt(validation_run)
    result["validation_command"] = validation_receipt
    validation_passed = validation_run.get("ok") is True
    result["checks"].append({
        "name": "developer_validation_command_passes",
        "passed": validation_passed,
        "command_source": source,
    })
    if not validation_passed:
        combined_tail = f"{validation_receipt.get('stdout_tail') or ''}\n{validation_receipt.get('stderr_tail') or ''}"
        categories = critical_categories_from_text(combined_tail) or {"validation-command-failed"}
        for category in sorted(categories):
            result["critical_findings"].append({
                "source": "validation-command",
                "severity": "error",
                "category": category,
                "message": combined_tail[-1000:],
            })
    payload = developer_validation_payload(evidence, project)
    result["verification_payload_source"] = payload.get("_redcap_source_path") if isinstance(payload, dict) else None
    if isinstance(payload, dict):
        append_critical_findings(result["critical_findings"], source="verification-results.warnings", severity="warning", messages=payload.get("warnings"))
        append_critical_findings(result["critical_findings"], source="verification-results.errors", severity="error", messages=payload.get("errors"))
    contracts = domain_contract_ids(evidence)
    if "signup-intent-data-contract" in contracts:
        signup_probe = run_runner_negative_contract_probe(project, evidence)
        result["signup_negative_probe"] = signup_probe
        result["checks"].append({
            "name": "signup_contract_negative_probe_passes",
            "passed": signup_probe.get("ok") is True,
        })
        if signup_probe.get("ok") is not True:
            result["failures"].append(f"signup-intent-data-contract 未被本地验证命令硬失败覆盖：{signup_probe.get('failures')}")
    if "character-player-relation-contract" in contracts:
        character_probe = run_runner_character_player_contract_probe(project, evidence)
        result["character_player_probe"] = character_probe
        result["checks"].append({
            "name": "character_player_contract_negative_probe_passes",
            "passed": character_probe.get("ok") is True,
        })
        if character_probe.get("ok") is not True:
            result["failures"].append(f"character-player-relation-contract 未被本地验证命令硬失败覆盖：{character_probe.get('failures')}")
    browser_behavior_probe = run_behavioral_browser_verification(project, evidence)
    result["browser_behavior_probe"] = browser_behavior_probe
    result["checks"].append({
        "name": "developer_browser_behavior_probe_passes",
        "passed": browser_behavior_probe.get("ok") is True,
    })
    if browser_behavior_probe.get("ok") is not True:
        result["failures"].append(f"developer 页面行为验收未通过，必须回到开发者修复：{browser_behavior_probe.get('failures')}")
    if result["critical_findings"]:
        result["failures"].append("developer 输出存在关键类别的 warning/error，不能进入 tester 阶段")
    result["ok"] = all(item.get("passed") is True for item in result["checks"]) and not result["critical_findings"] and not result["failures"]
    write_json(pathlib.Path(str(result["path"])), result)
    return result


def role_completion_ready(
    project: pathlib.Path,
    evidence: pathlib.Path,
    role: str,
    *,
    min_role_artifact_mtime: float | None = None,
) -> bool:
    if validate_role_outputs(project, evidence, role):
        return False
    if min_role_artifact_mtime is None:
        return True
    artifact = role_artifact_path(evidence, role)
    try:
        return artifact.stat().st_mtime >= min_role_artifact_mtime
    except OSError:
        return False


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
    repair_history: list[dict[str, Any]] = []
    for dirname in [
        "role-prompts",
        "role-messages",
        "role-runs",
        "role-workspaces",
        "role-artifacts",
        "role-raw",
        "developer-readiness-gate",
        "developer-repair-feedback",
        "developer-repair-decisions",
        "role-round-snapshots",
    ]:
        (evidence / dirname).mkdir(parents=True, exist_ok=True)
    trust_result = ensure_codex_project_trusted(project, evidence)
    mcp_contract = codex_mcp_isolation_contract()
    child_env = codex_child_env(trust_result.get("isolated_home") if isinstance(trust_result.get("isolated_home"), dict) else {})
    if trust_result.get("ok") is not True or mcp_contract.get("ok") is not True:
        aggregate = {
            "schema_id": "redcap-e2e-loom-role-pipeline-run",
            "ok": False,
            "roles": {},
            "codex_project_trust": trust_result,
            "codex_mcp_isolation_contract": mcp_contract,
            "developer_repair_loop": {
                "max_rounds": LOOM_DEVELOPER_REPAIR_MAX_ROUNDS,
                "rounds_used": 0,
                "history": [],
                "resolved_failures": [],
                "final_feedback_packet": None,
            },
            "session_manifest": None,
            "failures": [
                *([] if trust_result.get("ok") is True else ["Loom 角色管线无法准备隔离 Codex Home，禁止启动角色"]),
                *[str(item) for item in mcp_contract.get("failures", [])],
            ],
        }
        write_json(evidence / "codex-run.json", aggregate)
        return aggregate

    def execute_role(role: str, *, feedback_packet: pathlib.Path | None = None, round_name: str | None = None) -> dict[str, Any]:
        role_workspace_path(evidence, role).mkdir(parents=True, exist_ok=True)
        role_clearances[role] = write_role_gate_clearance(evidence, project, role, direction)
        prompt = build_role_prompt(project, evidence, role, direction, feedback_packet=feedback_packet)
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
            min_role_artifact_mtime = time.time() - 0.5
            completion_files = [
                path
                for path in [
                    role_artifact_path(evidence, role),
                    *[
                        role_output_path(project, evidence, output)
                        for output in role_handoff(role)[1]
                    ],
                ]
                if path is not None
            ]
            result = run_command_pty(
                attempt_argv,
                cwd=project,
                timeout_seconds=role_timeout,
                completion_files=completion_files,
                completion_predicate=lambda role=role, min_role_artifact_mtime=min_role_artifact_mtime: role_completion_ready(
                    project,
                    evidence,
                    role,
                    min_role_artifact_mtime=min_role_artifact_mtime,
                ),
                env_overrides=child_env,
            )
            attempt_stdout = evidence / "role-raw" / f"{role}.attempt-{attempt_index}.stdout.txt"
            attempt_stderr = evidence / "role-raw" / f"{role}.attempt-{attempt_index}.stderr.txt"
            attempt_stdout.write_text(str(result.get("stdout") or ""), encoding="utf-8")
            attempt_stderr.write_text(str(result.get("stderr") or ""), encoding="utf-8")
            if not message_path.exists() and str(result.get("stdout") or "").strip():
                message_path.write_text(str(result.get("stdout") or "")[-12000:], encoding="utf-8")
            attempt_receipt = command_receipt(result)
            artifact_exists = role_artifact_path(evidence, role).exists()
            interactive_gate_marker = role_interactive_gate_marker(result)
            actionable_marker = actionable_interactive_gate_marker(result, artifact_exists)
            retry_reason = role_failure_retry_reason(result, artifact_exists)
            attempt_receipt.update({
                "attempt": attempt_index,
                "session_id": extract_codex_session_id(f"{result.get('stdout') or ''}\n{result.get('stderr') or ''}"),
                "raw_stdout": str(attempt_stdout),
                "raw_stderr": str(attempt_stderr),
                "expected_artifact_exists": artifact_exists,
                "last_message_exists": message_path.exists(),
                "interactive_gate_marker_observed": interactive_gate_marker,
                "interactive_gate_marker": actionable_marker,
                "retry_reason": retry_reason,
                "retry_prompt_used": attempt_index > 1,
                "pty": result.get("pty"),
                "completion_reason": result.get("completion_reason"),
                "stop_requested_after_completion": result.get("stop_requested_after_completion"),
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
            "round_name": round_name,
            "feedback_packet": str(feedback_packet) if feedback_packet is not None else None,
            "codex_model": CODEX_ROLE_MODEL,
            "codex_reasoning_effort": CODEX_ROLE_REASONING_EFFORT,
            "codex_plugins_disabled": CODEX_ROLE_DISABLE_PLUGINS,
            "codex_extra_disabled_features": CODEX_ROLE_EXTRA_DISABLED_FEATURES,
            "codex_disabled_mcp_servers": unique_preserve_order(CODEX_DISABLED_MCP_SERVERS),
            "codex_user_config_preserved": CODEX_ROLE_PRESERVE_USER_CONFIG,
            "attempt_count": len(attempts),
            "max_attempts": max(1, CODEX_ROLE_MAX_ATTEMPTS),
            "attempts": attempts,
            "session_id": extract_codex_session_id(f"{result.get('stdout') or ''}\n{result.get('stderr') or ''}"),
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
            "round_name": round_name,
            "recorded_at": iso_now(),
            "ok": receipt["ok"],
        })
        if round_name:
            snapshot_role_round(evidence, role, round_name)
        return receipt

    pipeline_stopped = False

    for role in ["product_manager", "architect"]:
        receipt = execute_role(role, round_name=f"{role}-initial")
        role_results[role] = receipt
        if not receipt["ok"]:
            pipeline_stopped = True
            break

    developer_attempt_total = 0
    tester_attempt_total = 0
    repair_rounds_used = 0
    feedback_packet: pathlib.Path | None = None
    previous_failure_set: set[str] | None = None
    resolved_failures: set[str] = set()

    while not pipeline_stopped and "tester" not in role_results:
        developer_round_name = f"developer-round-{repair_rounds_used + 1}"
        developer_receipt = execute_role("developer", feedback_packet=feedback_packet, round_name=developer_round_name)
        developer_attempt_total += int(developer_receipt.get("attempt_count") or 0)
        developer_receipt["attempt_count"] = developer_attempt_total
        developer_receipt["repair_rounds_used"] = repair_rounds_used
        role_results["developer"] = developer_receipt
        write_json(evidence / "role-runs" / "developer.json", developer_receipt)
        if not developer_receipt["ok"]:
            pipeline_stopped = True
            break

        readiness = run_developer_readiness_gate(project, evidence, repair_rounds_used)
        failure_set = failure_set_from_developer_readiness(readiness)
        if failure_set:
            decision = developer_repair_decision(
                source="developer-readiness",
                failure_set=failure_set,
                previous_failure_set=previous_failure_set,
                resolved_failures=resolved_failures,
                repair_rounds_used=repair_rounds_used,
            )
            write_json(evidence / "developer-repair-decisions" / f"round-{repair_rounds_used}.json", decision)
            repair_history.append({
                "round": repair_rounds_used,
                "source": "developer-readiness",
                "decision": decision,
                "developer_readiness_gate": readiness.get("path"),
            })
            append_jsonl(evidence / "workflow-events.jsonl", {
                "event": "developer_repair_decision",
                "source": "developer-readiness",
                "round": repair_rounds_used,
                "recorded_at": iso_now(),
                "decision": decision,
            })
            if decision["schedule_repair"]:
                if previous_failure_set is not None:
                    resolved_failures.update(previous_failure_set - failure_set)
                repair_rounds_used += 1
                feedback_packet = write_developer_repair_feedback(
                    evidence,
                    repair_round=repair_rounds_used,
                    source="developer-readiness",
                    failure_set=failure_set,
                    developer_gate=readiness,
                    tester_receipt=None,
                    decision=decision,
                )
                previous_failure_set = set(failure_set)
                continue
            developer_receipt["ok"] = False
            developer_receipt["failures"] = [
                *developer_receipt.get("failures", []),
                f"developer-readiness gate failed and repair loop stopped: {decision['reason']}",
            ]
            developer_receipt["developer_readiness_gate"] = readiness
            write_json(evidence / "role-runs" / "developer.json", developer_receipt)
            role_results["developer"] = developer_receipt
            pipeline_stopped = True
            break

        if previous_failure_set is not None:
            resolved_failures.update(previous_failure_set)
            previous_failure_set = None

        tester_round_name = f"tester-round-{repair_rounds_used + 1}"
        tester_receipt = execute_role("tester", round_name=tester_round_name)
        tester_attempt_total += int(tester_receipt.get("attempt_count") or 0)
        tester_receipt["attempt_count"] = tester_attempt_total
        tester_receipt["repair_rounds_used"] = repair_rounds_used
        role_results["tester"] = tester_receipt
        write_json(evidence / "role-runs" / "tester.json", tester_receipt)
        if not tester_receipt["ok"]:
            failure_set = tester_failure_set(evidence, tester_receipt)
            decision = developer_repair_decision(
                source="tester",
                failure_set=failure_set,
                previous_failure_set=previous_failure_set,
                resolved_failures=resolved_failures,
                repair_rounds_used=repair_rounds_used,
            )
            write_json(evidence / "developer-repair-decisions" / f"round-{repair_rounds_used}.tester.json", decision)
            repair_history.append({
                "round": repair_rounds_used,
                "source": "tester",
                "decision": decision,
                "tester_run": "role-runs/tester.json",
            })
            append_jsonl(evidence / "workflow-events.jsonl", {
                "event": "developer_repair_decision",
                "source": "tester",
                "round": repair_rounds_used,
                "recorded_at": iso_now(),
                "decision": decision,
            })
            if decision["schedule_repair"]:
                if previous_failure_set is not None:
                    resolved_failures.update(previous_failure_set - failure_set)
                repair_rounds_used += 1
                feedback_packet = write_developer_repair_feedback(
                    evidence,
                    repair_round=repair_rounds_used,
                    source="tester",
                    failure_set=failure_set,
                    developer_gate=None,
                    tester_receipt=tester_receipt,
                    decision=decision,
                )
                previous_failure_set = set(failure_set)
                role_results.pop("tester", None)
                continue
            pipeline_stopped = True
            break

        if previous_failure_set is not None:
            resolved_failures.update(previous_failure_set)
            previous_failure_set = None
        pre_review_manifest = build_role_session_manifest(project, evidence, role_results, include_pending=True)
        write_json(evidence / "loom-role-session-manifest-pre-review.json", pre_review_manifest)
        break

    if not pipeline_stopped and role_results.get("tester", {}).get("ok") is True:
        reviewer_receipt = execute_role("reviewer", round_name="reviewer-final")
        role_results["reviewer"] = reviewer_receipt
        if not reviewer_receipt["ok"]:
            pipeline_stopped = True

    write_role_gate_clearance_summary(evidence, role_clearances)
    manifest = build_role_session_manifest(project, evidence, role_results)
    write_json(evidence / "loom-role-session-manifest.json", manifest)
    ok = all(role_results.get(role, {}).get("ok") is True for role in LOOM_EXECUTION_ROLES)
    ok = ok and not manifest["session_loss_alarms"]
    aggregate = {
        "schema_id": "redcap-e2e-loom-role-pipeline-run",
        "ok": ok,
        "roles": role_results,
        "codex_project_trust": trust_result,
        "codex_mcp_isolation_contract": mcp_contract,
        "developer_repair_loop": {
            "max_rounds": LOOM_DEVELOPER_REPAIR_MAX_ROUNDS,
            "rounds_used": repair_rounds_used,
            "history": repair_history,
            "resolved_failures": sorted(resolved_failures),
            "final_feedback_packet": str(feedback_packet) if feedback_packet is not None else None,
        },
        "session_manifest": "loom-role-session-manifest.json",
        "failures": [],
    }
    if not ok:
        aggregate["failures"].append("Loom 角色管线失败或会话证据不完整")
    write_json(evidence / "developer-repair-loop.json", aggregate["developer_repair_loop"])
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
    git_result = ensure_project_git_repo(project, evidence)
    if git_result.get("ok") is not True:
        return attach_source_workspace_guard({
            "ok": False,
            "failures": ["外部项目 Git 基线初始化失败"],
            "git": git_result,
            "project": str(project),
        }, guard_before)
    write_external_project_agents(project)
    install_result = package_and_init(project, evidence)
    if not install_result.get("ok"):
        return attach_source_workspace_guard({
            "ok": False,
            "failures": ["项目级 .redcap 安装失败"],
            "git": git_result,
            "install": install_result,
            "project": str(project),
        }, guard_before)
    evidence.mkdir(parents=True, exist_ok=True)
    trust_result = ensure_codex_project_trusted(project, evidence)
    if trust_result.get("ok") is not True:
        return attach_source_workspace_guard({
            "ok": False,
            "failures": ["Codex CLI 项目信任登记失败，项目级 Hook 无法保证加载"],
            "git": git_result,
            "install": install_result,
            "codex_project_trust": trust_result,
            "project": str(project),
        }, guard_before)
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
        "cap_decision": "<required>",
        "prism_assistance_request": {
            "requested": True,
            "owner": "e2e-runner",
            "reason": "reviewer 角色不能直接调度完整棱镜，最终棱镜由运行器统一调度"
        }
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
        "candidates": [
            {
                "id": "<required>",
                "summary": "<process or quality learning from this E2E>",
                "source": "<role evidence or runner evidence path>"
            }
        ],
        "no_candidate_reason": None,
        "allowed_decisions": ["promote_public", "keep_private", "no_promote", "defer_with_owner"],
        "decisions": [
            {
                "candidate_id": "<required>",
                "decision": "no_promote",
                "reason": "<why this candidate should not be promoted in this E2E>"
            }
        ]
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
    write_json(evidence / "final-marker-validation-template.json", {
        "schema_id": "redcap-e2e-final-marker-validation",
        "producer": "e2e-runner",
        "detected_command": "<required>",
        "ok": "<boolean>",
        "failure_policy": "blocking",
        "purpose": "写 completion-marker.json 前再次验证项目状态，避免负向探针或浏览器检查之后数据被破坏。"
    })
    write_json(evidence / "browser-inspection-template.json", {
        "schema_id": "redcap-e2e-browser-inspection",
        "producer": "e2e-runner",
        "target": "index.html",
        "screenshot": "browser-inspection.png",
        "ok": "<boolean>",
        "failure_policy": "blocking"
    })
    write_json(evidence / "file-browser-inspection-template.json", {
        "schema_id": "redcap-e2e-file-browser-inspection",
        "producer": "e2e-runner",
        "target": "index.html",
        "screenshot": "file-browser-inspection.png",
        "launch_mode": "local-file-protocol",
        "ok": "<boolean>",
        "failure_policy": "blocking"
    })
    write_json(evidence / "behavioral-browser-verification-template.json", {
        "schema_id": "redcap-e2e-behavioral-browser-verification",
        "producer": "e2e-runner",
        "target": "index.html",
        "screenshot": "behavioral-browser-verification.png",
        "relation_probe_screenshot": "behavioral-relation-probe.png",
        "relation_container_crop_screenshot": "behavioral-relation-container-crop.png",
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
    (evidence / "behavioral-relation-container-crop.png").write_bytes(PLACEHOLDER_PNG_BYTES)
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
    write_json(evidence / "self-referential-boundary-template.json", {
        "schema_id": "redcap-e2e-self-referential-boundary",
        "producer": "e2e-runner",
        "ok": "<boolean>",
        "failure_policy": "blocking",
        "purpose": "完成标记必须明示本轮验证链路的自引用边界和未覆盖范围。"
    })
    write_json(evidence / "visual-independence-report-template.json", {
        "schema_id": "redcap-e2e-visual-independence-report",
        "producer": "e2e-runner",
        "checks": [
            "所有 E2E 截图证据必须存在于 sources 中并带 sha256，不能漏掉已落盘 PNG",
            "截图 sha256 默认必须互不相同；HTTP 与 file:// 检查必须通过独立视口或独立状态提供可区分截图；只有行为截图与关系探针截图处于同一已选活动状态且像素相同，且记录 relation_event_control、relation_view_control 和 dom_structural_probe 作为新增证明时，才允许解释为可接受重复",
            "所有浏览器证据必须记录 browser_context",
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
    write_json(evidence / "convergence-diagnosis-template.json", {
        "schema_id": "redcap-e2e-convergence-diagnosis",
        "producer": "e2e-runner",
        "auto_rerun_allowed": "<boolean>",
        "diagnosis": [
            {
                "loop_class": "runner_negative_probe_semantics_gap|verification_authority_gap|loom_opposition_gap|behavioral_evidence_alignment_gap|unclassified_final_prism_concern",
                "evidence_gap": "<why the run cannot converge>",
                "required_next_action": "<what must be fixed before rerun>",
                "auto_rerun_allowed": False
            }
        ],
        "failure_policy": "structural gaps must stop blind reruns"
    })
    write_json(evidence / "final-prism-review-template.json", {
        "schema_id": "redcap-e2e-final-prism-review",
        "producer": "e2e-runner",
        "providers_required": ["kimi", "claude-code"],
        "strictest_verdict": "<pass|concern|block>",
        "ok": "<boolean>",
        "failure_policy": "blocking"
    })
    write_json(evidence / "completion-marker-preview-template.json", {
        "schema_id": "redcap-e2e-completion-marker-preview",
        "producer": "e2e-runner",
        "preview_only": True,
        "will_write_only_after_final_prism_pass": True,
        "marker_payload": "<planned completion-marker payload with boundary disclosures copied>"
    })
    write_json(evidence / "completion-marker-preview-validation-template.json", {
        "schema_id": "redcap-e2e-completion-marker-boundary-validation",
        "producer": "e2e-runner",
        "preview": True,
        "ok": "<boolean>",
        "copied_fields": [
            "validation_chain_scope",
            "not_claimed",
            "role_process_completion",
            "observer_boundary",
            "bootstrap_review_boundary"
        ]
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
    write_json(evidence / "completion-marker-boundary-validation-template.json", {
        "schema_id": "redcap-e2e-completion-marker-boundary-validation",
        "producer": "e2e-runner",
        "preview": False,
        "ok": "<boolean>",
        "purpose": "证明正式 completion-marker.json 逐字复制 self-referential-boundary.json 的边界披露"
    })
    (evidence / "implementer-prompt.md").write_text(prompt, encoding="utf-8")
    write_json(evidence / "review-verdict-template.json", {
        "schema_id": "redcap-e2e-review-verdict",
        "status": "pending",
        "terminal_completion": False,
        "boundary": "reviewer 只能给阶段评审；terminal_completion=false 表示不能自证本轮 E2E 终局完成或 RedCap 完整复活",
        "runner_owned_follow_up": REVIEWER_RUNNER_OWNED_FOLLOW_UP,
        "blocking_findings": [],
        "role_opposition_matrix": [],
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
        "codex_project_trust": trust_result,
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
        "final-marker-validation.json",
        "browser-inspection.json",
        "file-browser-inspection.json",
        "behavioral-browser-verification.json",
        "runner-character-player-contract-probe.json",
        "role-execution-risk.json",
        "independent-browser-verification.json",
        "browser-inspection.png",
        "file-browser-inspection.png",
        "behavioral-browser-verification.png",
        "behavioral-relation-probe.png",
        "independent-browser-verification-script.py",
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
        "package-prism-check.json",
        "final-runner-test-results.json",
        "final-marker-validation.json",
        "browser-inspection.json",
        "file-browser-inspection.json",
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
    if isinstance(scripts, dict) and isinstance(scripts.get("test"), str) and scripts["test"].strip() and not command_text_looks_long_running(scripts["test"]):
        return ["npm", "test"], "package.json scripts.test"
    if isinstance(scripts, dict) and isinstance(scripts.get("validate"), str) and scripts["validate"].strip() and not command_text_looks_long_running(scripts["validate"]):
        return ["npm", "run", "validate"], "package.json scripts.validate"
    script_candidates = [
        ("validate.js", ["node", "validate.js"]),
        ("validate.mjs", ["node", "validate.mjs"]),
        ("src/validate.js", ["node", "src/validate.js"]),
        ("src/validate.mjs", ["node", "src/validate.mjs"]),
        ("scripts/validate.js", ["node", "scripts/validate.js"]),
        ("scripts/validate.mjs", ["node", "scripts/validate.mjs"]),
        ("scripts/validate-data.js", ["node", "scripts/validate-data.js"]),
        ("scripts/validate-data.mjs", ["node", "scripts/validate-data.mjs"]),
        ("scripts/verify.mjs", ["node", "scripts/verify.mjs"]),
        ("scripts/verify.js", ["node", "scripts/verify.js"]),
        ("scripts/verify.sh", ["bash", "scripts/verify.sh"]),
        ("tests/validate.mjs", ["node", "tests/validate.mjs"]),
        ("tests/verify.mjs", ["node", "tests/verify.mjs"]),
    ]
    readme = project / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8", errors="replace")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or command_text_looks_long_running(line):
                continue
            try:
                parts = shlex.split(line)
            except ValueError:
                continue
            if len(parts) < 2:
                continue
            runner = parts[0]
            if runner not in {"node", "bash", "python3"}:
                continue
            relative_path = parts[1]
            args = parts[2:]
            if not re.fullmatch(r"(?:validate\.(?:js|mjs)|(?:scripts|tests|src)/[A-Za-z0-9_.\/-]+\.(?:js|mjs|sh|py))", relative_path):
                continue
            if ".." in pathlib.PurePosixPath(relative_path).parts:
                continue
            if not (project / relative_path).exists():
                continue
            if validation_script_path_looks_long_running(relative_path):
                continue
            argv = [runner, relative_path]
            if runner == "bash" and not relative_path.endswith(".sh"):
                continue
            if runner == "node" and not relative_path.endswith((".js", ".mjs")):
                continue
            if runner == "python3" and not relative_path.endswith(".py"):
                continue
            safe_args: list[str] = []
            unsafe_arg = False
            for arg in args:
                if not re.fullmatch(r"[A-Za-z0-9_./:@=+-]+", arg):
                    unsafe_arg = True
                    break
                if arg.startswith(("/", "http://", "https://")):
                    unsafe_arg = True
                    break
                if ".." in pathlib.PurePosixPath(arg).parts:
                    unsafe_arg = True
                    break
                safe_args.append(arg)
            if unsafe_arg:
                continue
            argv = [runner, relative_path, *safe_args]
            return argv, f"README.md command: {' '.join(argv)}"
    for relative_path, argv in script_candidates:
        if (project / relative_path).exists():
            return argv, relative_path
    known_sources = ", ".join(["package.json scripts.test", "package.json scripts.validate", *[item[0] for item in script_candidates]])
    return None, f"没有发现可执行验证命令：{known_sources}"


LONG_RUNNING_COMMAND_HINTS = {"serve", "server", "start", "dev", "watch", "preview", "listen", "http-server"}


def command_text_looks_long_running(command_text: str) -> bool:
    lowered = command_text.lower()
    tokens = re.split(r"[^a-z0-9]+", lowered)
    return any(token in LONG_RUNNING_COMMAND_HINTS for token in tokens)


def validation_script_path_looks_long_running(relative_path: str) -> bool:
    pure = pathlib.PurePosixPath(relative_path)
    tokens: list[str] = []
    for part in pure.parts:
        tokens.extend(re.split(r"[^a-z0-9]+", part.lower()))
    return any(token in LONG_RUNNING_COMMAND_HINTS for token in tokens)


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


def run_final_marker_validation(project: pathlib.Path) -> dict[str, Any]:
    argv, source = detect_validation_command(project)
    if argv is None:
        return {
            "schema_id": "redcap-e2e-final-marker-validation",
            "producer": "e2e-runner",
            "ok": False,
            "detected_command": None,
            "command_source": source,
            "failures": ["写 completion-marker.json 前无法发现可执行验证命令"],
        }
    result = run_command(argv, cwd=project, timeout_seconds=240)
    receipt = command_receipt(result)
    receipt.update({
        "schema_id": "redcap-e2e-final-marker-validation",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "purpose": "写 completion-marker.json 前再次验证项目状态，确保负向探针和浏览器检查之后数据仍可通过项目验证。",
        "detected_command": argv,
        "command_source": source,
        "stdout_sha256_required": True,
        "failures": [] if result["ok"] else ["写 completion-marker.json 前的最终项目验证失败"],
    })
    return receipt


JS_DATA_CANDIDATE_RELATIVE_PATHS = [
    pathlib.Path("app.js"),
    pathlib.Path("app/embedded-data.js"),
    pathlib.Path("app/data.js"),
    pathlib.Path("app/activities.js"),
    pathlib.Path("assets/app.js"),
    pathlib.Path("src/sample-data.js"),
    pathlib.Path("src/app.js"),
    pathlib.Path("src/data.js"),
    pathlib.Path("data.js"),
    pathlib.Path("data/campaigns.js"),
    pathlib.Path("data/events.js"),
    pathlib.Path("data/activities.js"),
    pathlib.Path("src/campaigns.js"),
    pathlib.Path("src/events.js"),
    pathlib.Path("src/activities.js"),
]

SIGNUP_CHILD_LIST_KEYS = ["sessions", "events", "activities", "items"]
SIGNUP_COLLECTION_FIELD_CANDIDATES = [
    "signups",
    "registrations",
    "enrollments",
    "applications",
    "participants",
]
SIGNUP_INTENT_FIELD_CANDIDATES = [
    "signupIntent",
    "registrationIntent",
    "enrollmentIntent",
    "applicationIntent",
    "participationIntent",
]
RELATION_PARENT_LIST_KEYS = [
    "players",
    "participants",
    "attendees",
    "users",
    "members",
]
RELATION_CHILD_LIST_KEYS = [
    "characters",
    "assignments",
    "reservations",
    "submissions",
    "allocations",
]
RELATION_REFERENCE_KEYS = [
    "playerId",
    "player_id",
    "participantId",
    "participant_id",
    "attendeeId",
    "attendee_id",
    "userId",
    "user_id",
    "memberId",
    "member_id",
    "player",
    "playerName",
    "player_name",
    "participant",
    "participantName",
    "participant_name",
]
RELATION_NAME_REFERENCE_KEYS = {
    "player",
    "playerName",
    "player_name",
    "participant",
    "participantName",
    "participant_name",
}
SELF_PURIFICATION_ALLOWED_DECISIONS = {"promote_public", "keep_private", "no_promote", "defer_with_owner"}


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
            nested_decisions = candidate.get("decisions")
            if not isinstance(nested_decisions, list):
                continue
            for decision in nested_decisions:
                if not isinstance(decision, dict):
                    continue
                normalized = copy.deepcopy(decision)
                if candidate_id and "candidate_id" not in normalized and "id" not in normalized:
                    normalized["candidate_id"] = candidate_id
                collected.append(normalized)
    return collected


def structured_data_candidate_paths(project: pathlib.Path) -> list[pathlib.Path]:
    data_dir = project / "data"
    fixed_json = [data_dir / "events.json", data_dir / "activities.json"]
    extra_json = sorted(path for path in data_dir.glob("*.json") if path not in fixed_json)
    fixed_js = [(project / relative) for relative in JS_DATA_CANDIDATE_RELATIVE_PATHS]
    data_like_js: list[pathlib.Path] = []
    for directory in [project, project / "src", project / "app", project / "assets", project / "public", data_dir]:
        if not directory.is_dir():
            continue
        for pattern in ["*data*.js", "*campaign*.js", "*event*.js", "*activit*.js"]:
            data_like_js.extend(sorted(directory.glob(pattern)))
    data_like_js = sorted({path for path in data_like_js})
    extra_data_js = sorted(path for path in data_dir.glob("*.js") if path not in fixed_js)
    fixed_html = [
        project / "index.html",
        project / "app" / "index.html",
        project / "public" / "index.html",
        project / "dist" / "index.html",
        project / "build" / "index.html",
    ]
    candidates = [
        *fixed_json,
        *extra_json,
        *data_like_js,
        *fixed_js,
        *extra_data_js,
        *fixed_html,
    ]
    result: list[pathlib.Path] = []
    seen: set[pathlib.Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            result.append(candidate)
    return result


HTML_JSON_SCRIPT_RE = re.compile(r"(<script\b[^>]*>)([\s\S]*?)(</script>)", re.IGNORECASE)
HTML_JSON_TYPE_RE = re.compile(r"\btype\s*=\s*['\"]application/json['\"]", re.IGNORECASE)
HTML_DATA_HINTS = [
    "trpg",
    "redcap",
    "app",
    "application",
    "project",
    "activity",
    "activities",
    "campaign",
    "event",
    "session",
    "data",
]
STRUCTURED_DATA_KEYS = {
    "activities",
    "events",
    "campaigns",
    "sessions",
    "items",
    "players",
    "participants",
    "attendees",
    "users",
    "members",
    "characters",
    "assignments",
    "reservations",
    "signups",
    "signupIntent",
    "registrations",
    "registrationIntent",
}


def structured_payload_has_domain_keys(payload: Any) -> bool:
    if isinstance(payload, list):
        return any(structured_payload_has_domain_keys(item) for item in payload if isinstance(item, (dict, list)))
    if not isinstance(payload, dict):
        return False
    if any(key in payload for key in STRUCTURED_DATA_KEYS):
        return True
    return any(structured_payload_has_domain_keys(value) for value in payload.values() if isinstance(value, (dict, list)))


def find_html_embedded_json_script(text: str) -> tuple[re.Match[str] | None, dict[str, Any] | list[Any] | None, str | None]:
    fallback: tuple[re.Match[str], dict[str, Any] | list[Any], str] | None = None
    for match in HTML_JSON_SCRIPT_RE.finditer(text):
        open_tag = match.group(1)
        if not HTML_JSON_TYPE_RE.search(open_tag):
            continue
        body = match.group(2).strip()
        if not body:
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, (dict, list)):
            continue
        attr_hint = any(hint in open_tag.lower() for hint in HTML_DATA_HINTS)
        domain_hint = structured_payload_has_domain_keys(payload)
        if attr_hint or domain_hint:
            return match, payload, "script[type=application/json]"
        if fallback is None:
            fallback = (match, payload, "script[type=application/json].fallback")
    if fallback is not None:
        match, payload, source = fallback
        return match, payload, source
    return None, None, None


def load_structured_data_payload(project: pathlib.Path, data_path: pathlib.Path, failures: list[str]) -> dict[str, Any] | list[Any] | None:
    relative = data_path.relative_to(project)
    if data_path.suffix == ".json":
        try:
            return json.loads(data_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            failures.append(f"{relative} 无法解析：{type(exc).__name__}: {exc}")
            return None
    if data_path.suffix == ".js":
        script = (
            "const fs = require('fs');"
            "const vm = require('vm');"
            "const p = process.argv[1];"
            "const source = fs.readFileSync(p, 'utf8');"
            "function structured(v) { return v && typeof v !== 'function' && (Array.isArray(v) || typeof v === 'object'); }"
            "const candidates = [];"
            "const marker = source.match(/\\/\\*\\s*TRPG_DATA_START\\s*\\*\\/\\s*(?:const|let|var)\\s+(?:BOOTSTRAP_DATA|TRPG_DATA|REDCAP_DATA)\\s*=\\s*([\\s\\S]*?);\\s*\\/\\*\\s*TRPG_DATA_END\\s*\\*\\//);"
            "if (marker) {"
            "  try { candidates.push({source: 'marker.TRPG_DATA_START', value: vm.runInNewContext(`(${marker[1]})`, {}, { timeout: 1000 })}); }"
            "  catch (error) { candidates.push({source: 'marker-error', value: undefined, error: String(error && error.message || error)}); }"
            "}"
            "try { candidates.push({source: 'require', value: require(p)}); } catch (error) { candidates.push({source: 'require-error', value: undefined, error: String(error && error.message || error)}); }"
            "const sandbox = { module: { exports: {} }, exports: {}, window: {} };"
            "sandbox.globalThis = sandbox;"
            "vm.createContext(sandbox);"
            "try { vm.runInContext(source, sandbox, { filename: p }); } catch (error) { candidates.push({source: 'vm-error', value: undefined, error: String(error && error.message || error)}); }"
            "candidates.push({source: 'module.exports', value: sandbox.module.exports});"
            "candidates.push({source: 'exports', value: sandbox.exports});"
            "for (const scopeName of ['window', 'globalThis']) {"
            "  const scope = scopeName === 'window' ? sandbox.window : sandbox;"
            "  for (const key of ['TRPG_CAMPAIGNS', 'TRPG_ACTIVITY_DATA', 'TRPG_SAMPLE_DATA', 'TRPG_SEED_DATA', 'TRPG_DATA', 'REDCAP_DATA', 'APP_DATA', 'APPLICATION_DATA', 'PROJECT_DATA', 'DOMAIN_DATA', 'BOOTSTRAP_DATA', 'TRPG_EVENTS', 'TRPG_ACTIVITIES', 'ACTIVITY_DATA', 'SAMPLE_DATA', 'campaigns', 'events', 'activities', 'sessions', 'items']) {"
            "    candidates.push({source: `${scopeName}.${key}`, value: scope[key]});"
            "  }"
            "}"
            "for (const candidate of candidates) {"
            "  if (structured(candidate.value) && !(typeof candidate.value === 'object' && !Array.isArray(candidate.value) && Object.keys(candidate.value).length === 0)) {"
            "    process.stdout.write(JSON.stringify({source: candidate.source, payload: candidate.value}));"
            "    process.exit(0);"
            "  }"
            "}"
            "throw new Error('JS data file did not expose structured data through module exports or known browser globals');"
        )
        completed = subprocess.run(
            ["node", "-e", script, str(data_path.resolve())],
            cwd=str(project),
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            failures.append(f"{relative} 无法作为 JS 数据模块读取：{(completed.stderr or completed.stdout).strip()}")
            return None
        try:
            output = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            failures.append(f"{relative} JS 数据模块输出无法解析：{exc}")
            return None
        payload = output.get("payload") if isinstance(output, dict) and "payload" in output else output
        return payload if isinstance(payload, (dict, list)) else None
    if data_path.suffix == ".html":
        text = data_path.read_text(encoding="utf-8", errors="replace")
        _, payload, _ = find_html_embedded_json_script(text)
        if payload is None:
            failures.append(f"{relative} 未发现可解析的 HTML 内嵌 application/json 数据脚本")
            return None
        return payload
    failures.append(f"{relative} 不是支持的数据文件类型")
    return None


def write_structured_data_probe_payload(data_path: pathlib.Path, payload: dict[str, Any] | list[Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if data_path.suffix == ".json":
        data_path.write_text(serialized + "\n", encoding="utf-8")
        return
    if data_path.suffix == ".js":
        original_text = data_path.read_text(encoding="utf-8", errors="replace") if data_path.exists() else ""
        marker_match = re.search(
            r"(/\*\s*TRPG_DATA_START\s*\*/\s*(?:const|let|var)\s+(?:BOOTSTRAP_DATA|TRPG_DATA|REDCAP_DATA)\s*=\s*)([\s\S]*?)(;\s*/\*\s*TRPG_DATA_END\s*\*/)",
            original_text,
        )
        if marker_match:
            data_path.write_text(
                original_text[:marker_match.start(2)] + serialized + original_text[marker_match.end(2):],
                encoding="utf-8",
            )
            return
        module_text = (
            "const data = "
            + serialized
            + ";\n\n"
            + "if (typeof window !== \"undefined\") {\n"
            + "  window.TRPG_DATA = data;\n"
            + "  window.TRPG_SEED_DATA = data;\n"
            + "  window.REDCAP_DATA = data;\n"
            + "  window.APP_DATA = data;\n"
            + "  window.APPLICATION_DATA = data;\n"
            + "  window.PROJECT_DATA = data;\n"
            + "  window.DOMAIN_DATA = data;\n"
            + "  window.BOOTSTRAP_DATA = data;\n"
            + "  window.TRPG_CAMPAIGNS = Array.isArray(data) ? data : (data.campaigns || data.activities || data.events || data.items || data);\n"
            + "  window.TRPG_ACTIVITY_DATA = data;\n"
            + "  window.TRPG_SAMPLE_DATA = data;\n"
            + "  window.TRPG_ACTIVITIES = Array.isArray(data) ? data : (data.activities || data.campaigns || data.events || data.items || data);\n"
            + "  window.TRPG_EVENTS = Array.isArray(data) ? data : (data.events || data.activities || data.campaigns || data.items || data);\n"
            + "  window.ACTIVITY_DATA = data;\n"
            + "  window.SAMPLE_DATA = data;\n"
            + "  window.activities = Array.isArray(data) ? data : (data.activities || data.events || data.campaigns || data.items || data);\n"
            + "  window.events = Array.isArray(data) ? data : (data.events || data.activities || data.campaigns || data.items || data);\n"
            + "}\n"
            + "if (typeof globalThis !== \"undefined\") {\n"
            + "  globalThis.TRPG_DATA = data;\n"
            + "  globalThis.TRPG_SEED_DATA = data;\n"
            + "  globalThis.REDCAP_DATA = data;\n"
            + "  globalThis.APP_DATA = data;\n"
            + "  globalThis.APPLICATION_DATA = data;\n"
            + "  globalThis.PROJECT_DATA = data;\n"
            + "  globalThis.DOMAIN_DATA = data;\n"
            + "  globalThis.BOOTSTRAP_DATA = data;\n"
            + "  globalThis.TRPG_CAMPAIGNS = Array.isArray(data) ? data : (data.campaigns || data.activities || data.events || data.items || data);\n"
            + "  globalThis.TRPG_ACTIVITY_DATA = data;\n"
            + "  globalThis.TRPG_SAMPLE_DATA = data;\n"
            + "  globalThis.ACTIVITY_DATA = data;\n"
            + "  globalThis.SAMPLE_DATA = data;\n"
            + "}\n"
            + "if (typeof module !== \"undefined\" && module.exports) {\n"
            + "  module.exports = data;\n"
            + "}\n"
        )
        data_path.write_text(module_text, encoding="utf-8")
        return
    if data_path.suffix == ".html":
        original_text = data_path.read_text(encoding="utf-8", errors="replace") if data_path.exists() else ""
        script_match, _, _ = find_html_embedded_json_script(original_text)
        if script_match:
            replacement = "\n" + serialized + "\n"
            data_path.write_text(
                original_text[:script_match.start(2)] + replacement + original_text[script_match.end(2):],
                encoding="utf-8",
            )
            return
        raise ValueError(f"unsupported HTML structured data probe path: {data_path}")
    raise ValueError(f"unsupported structured data probe path: {data_path}")


def summarize_probe_value(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        return {"type": "list", "length": len(value)}
    if isinstance(value, dict):
        return {"type": "object", "keys": sorted(str(key) for key in value.keys())[:12]}
    if isinstance(value, str):
        return {"type": "string", "length": len(value), "sample": value[:80]}
    if value is None:
        return {"type": "null"}
    return {"type": type(value).__name__, "repr": repr(value)[:80]}


def structured_data_probe_syntax_check(project: pathlib.Path, data_path: pathlib.Path) -> dict[str, Any]:
    relative = str(data_path.relative_to(project))
    if data_path.suffix == ".json":
        try:
            json.loads(data_path.read_text(encoding="utf-8"))
            return {"ok": True, "kind": "json-parse", "target": relative}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return {"ok": False, "kind": "json-parse", "target": relative, "error": f"{type(exc).__name__}: {exc}"}
    if data_path.suffix == ".js":
        completed = run_command(["node", "--check", relative], cwd=project, timeout_seconds=30)
        receipt = command_receipt(completed)
        return {
            "ok": completed.get("exit_code") == 0,
            "kind": "node-check",
            "target": relative,
            "receipt": receipt,
        }
    if data_path.suffix == ".html":
        text = data_path.read_text(encoding="utf-8", errors="replace")
        _, payload, source = find_html_embedded_json_script(text)
        return {
            "ok": payload is not None,
            "kind": "html-embedded-json-parse",
            "target": relative,
            "source": source,
        }
    return {"ok": False, "kind": "unsupported", "target": relative, "error": f"unsupported suffix: {data_path.suffix}"}


def write_mutated_probe_snapshot(
    project: pathlib.Path,
    evidence: pathlib.Path,
    data_path: pathlib.Path,
    probe_id: str,
    mutated_sha256: str,
) -> dict[str, Any]:
    suffix = data_path.suffix or ".txt"
    snapshot_dir = evidence / "probe-snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"{probe_id}-{mutated_sha256[:12]}{suffix}"
    shutil.copy2(data_path, snapshot_path)
    return {
        "path": str(snapshot_path.relative_to(project)),
        "sha256": sha256_file(snapshot_path),
        "source_path": str(data_path.relative_to(project)),
    }


def receipt_text(receipt: dict[str, Any] | None) -> str:
    if not isinstance(receipt, dict):
        return ""
    return "\n".join(
        str(receipt.get(key) or "")
        for key in ("stdout_tail", "stderr_tail")
    ).casefold()


def domain_failure_detected(receipt: dict[str, Any] | None, target_contract: str) -> bool:
    text = receipt_text(receipt)
    if not text:
        return False
    return domain_failure_text_matches(text, target_contract)


def domain_failure_text_matches(text: str, target_contract: str) -> bool:
    text = text.casefold()
    setup_error_markers = [
        "trpg_seed_data not set",
        "window.trpg_seed_data",
        "did not set window",
        "js data file did not expose structured data",
        "syntaxerror",
        "unexpected token",
    ]
    if any(marker in text for marker in setup_error_markers):
        return False
    if target_contract == "signup-intent-data-contract":
        markers = [
            "signup-intent-data-contract",
            "signupintent",
            "signups",
            "registrationintent",
            "registrations",
            "enrollmentintent",
            "enrollments",
            "participationintent",
            "participants",
            "报名",
            "注册",
            "参与",
        ]
    elif target_contract == "character-player-relation-contract":
        markers = [
            "character-player-relation-contract",
            "entity-reference-contract",
            "playerid",
            "player id",
            "participantid",
            "participant id",
            "attendeeid",
            "userid",
            "memberid",
            "角色",
            "玩家",
            "参与者",
            "关联",
        ]
    else:
        markers = [target_contract.casefold()]
    return any(marker in text for marker in markers)


def domain_failure_detected_in_payload(payload: dict[str, Any] | None, target_contract: str) -> bool:
    if not isinstance(payload, dict):
        return False
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return domain_failure_text_matches(text, target_contract)


def signup_record_contract_fields(record: dict[str, Any]) -> tuple[str | None, str | None]:
    collection_field = next((field for field in SIGNUP_COLLECTION_FIELD_CANDIDATES if field in record), None)
    intent_field = next((field for field in SIGNUP_INTENT_FIELD_CANDIDATES if field in record), None)
    return collection_field, intent_field


def signup_record_has_contract_fields(record: dict[str, Any]) -> bool:
    collection_field, intent_field = signup_record_contract_fields(record)
    return collection_field is not None or intent_field is not None


def top_level_data_list_candidates(payload: dict[str, Any] | list[Any]) -> list[tuple[str, list[Any]]]:
    list_candidates: list[tuple[str, list[Any]]] = []
    seen: set[str] = set()
    preferred_keys = ["events", "activities", "campaigns", "sessions", "items"]

    def append(path: str, records: list[Any]) -> None:
        if path not in seen:
            seen.add(path)
            list_candidates.append((path, records))

    def visit(value: Any, path: str, depth: int) -> None:
        if depth > 5:
            return
        if isinstance(value, list):
            append(path or "$", value)
            for index, item in enumerate(value):
                if isinstance(item, dict):
                    for child_key in preferred_keys:
                        child_value = item.get(child_key)
                        if isinstance(child_value, list):
                            visit(child_value, f"{path or '$'}.{index}.{child_key}", depth + 1)
                    for child_key, child_value in item.items():
                        if child_key in preferred_keys:
                            continue
                        if isinstance(child_value, (dict, list)):
                            visit(child_value, f"{path or '$'}.{index}.{child_key}", depth + 1)
            return
        if not isinstance(value, dict):
            return
        for key in preferred_keys:
            child = value.get(key)
            if isinstance(child, list):
                visit(child, f"{path}.{key}" if path else key, depth + 1)
        for key, child in value.items():
            if key in preferred_keys:
                continue
            if isinstance(child, (dict, list)):
                visit(child, f"{path}.{key}" if path else str(key), depth + 1)

    visit(payload, "", 0)
    return list_candidates


def iter_signup_probe_candidates(payload: dict[str, Any] | list[Any]) -> list[tuple[str, int, bool]]:
    candidates: list[tuple[str, int, bool]] = []
    for list_key, records in top_level_data_list_candidates(payload):
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            candidates.append((list_key, index, signup_record_has_contract_fields(record)))
            for child_key in SIGNUP_CHILD_LIST_KEYS:
                child_records = record.get(child_key)
                if not isinstance(child_records, list):
                    continue
                nested_list_key = f"{list_key}.{index}.{child_key}"
                for child_index, child_record in enumerate(child_records):
                    if isinstance(child_record, dict):
                        candidates.append((nested_list_key, child_index, signup_record_has_contract_fields(child_record)))
    return candidates


def signup_probe_records_at_list_key(payload: dict[str, Any] | list[Any], list_key: str) -> list[Any] | None:
    if list_key == "$":
        return payload if isinstance(payload, list) else None
    parts = [part for part in list_key.split(".") if part]
    if not parts:
        return None
    current: Any = payload
    for part in parts:
        if part == "$":
            continue
        if isinstance(current, list):
            try:
                item_index = int(part)
            except ValueError:
                return None
            if item_index < 0 or item_index >= len(current):
                return None
            current = current[item_index]
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current if isinstance(current, list) else None


def signup_probe_uses_non_first_path(list_key: str, record_index: int) -> bool:
    if record_index > 0:
        return True
    for part in list_key.split("."):
        try:
            if int(part) > 0:
                return True
        except ValueError:
            continue
    return False


def select_signup_probe_candidate(candidates: list[tuple[str, int, bool]]) -> tuple[str, int] | None:
    if not candidates:
        return None
    explicit = [(list_key, index) for list_key, index, has_fields in candidates if has_fields]
    fallback = [(list_key, index) for list_key, index, has_fields in candidates if not has_fields]
    selectable = explicit or fallback
    return next(
        (
            (list_key, index)
            for list_key, index in selectable
            if signup_probe_uses_non_first_path(list_key, index)
        ),
        selectable[0],
    )


def find_signup_contract_data_target(project: pathlib.Path) -> tuple[pathlib.Path | None, dict[str, Any] | list[Any] | None, str | None, int | None, list[str]]:
    """Locate the structured record that should be mutated for signup contract probing."""
    failures: list[str] = []
    for data_path in structured_data_candidate_paths(project):
        if not data_path.exists():
            continue
        payload = load_structured_data_payload(project, data_path, failures)
        if payload is None:
            continue
        candidate = select_signup_probe_candidate(iter_signup_probe_candidates(payload))
        if candidate is not None:
            list_key, record_index = candidate
            return data_path, payload, list_key, record_index, failures
        failures.append(f"{data_path.relative_to(project)} 未发现可变更的活动列表记录")
    failures.append("未找到包含报名数据或活动列表的 JSON 或 JS 数据文件")
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
    records = signup_probe_records_at_list_key(data, list_key)
    if not isinstance(records, list) or record_index >= len(records) or not isinstance(records[record_index], dict):
        result["failures"].append(f"{data_path.relative_to(project)} 中 {list_key}[{record_index}] 不是可变更对象")
        return result
    eligible_record_indexes = [index for index, record in enumerate(records) if isinstance(record, dict)]
    result["probe_depth"] = {
        "record_count": len(records),
        "eligible_record_indexes": eligible_record_indexes,
        "targeted_non_first_record": record_index > 0,
        "targeted_non_first_path": signup_probe_uses_non_first_path(list_key, record_index),
        "selection_rule": "prefer_non_first_signup_record_then_first_available",
    }
    mutated = json.loads(json.dumps(data, ensure_ascii=False))
    mutated_records = signup_probe_records_at_list_key(mutated, list_key)
    if not isinstance(mutated_records, list):
        result["failures"].append(f"{data_path.relative_to(project)} 中 {list_key} 无法解析为可变更列表")
        return result
    mutated_event = mutated_records[record_index]
    collection_field, intent_field = signup_record_contract_fields(mutated_event)
    if collection_field is None:
        collection_field = "signups"
    if intent_field is None:
        intent_field = "signupIntent"
    before_values = {
        collection_field: copy.deepcopy(mutated_event.get(collection_field)),
        intent_field: copy.deepcopy(mutated_event.get(intent_field)),
    }
    mutated_event[collection_field] = []
    mutated_event[intent_field] = ""
    mutation_summary = {
        "executor": "runner_internal",
        "event_id": mutated_event.get("id"),
        "data_path": str(data_path.relative_to(project)),
        "list_key": list_key,
        "record_index": record_index,
        "target_path": f"{list_key}[{record_index}]",
        "changed_fields": [collection_field, intent_field],
        "contract_fields": {
            "collection_field": collection_field,
            "intent_field": intent_field,
        },
        "before": {key: summarize_probe_value(value) for key, value in before_values.items()},
        "after": {
            collection_field: summarize_probe_value(mutated_event.get(collection_field)),
            intent_field: summarize_probe_value(mutated_event.get(intent_field)),
        },
        "original_sha256": original_sha256,
        "expected_validation_exit": "non_zero",
    }
    result["mutation"] = mutation_summary
    negative_receipt: dict[str, Any] | None = None
    restore_receipt: dict[str, Any] | None = None
    try:
        write_structured_data_probe_payload(data_path, mutated)
        mutated_sha256 = sha256_file(data_path)
        snapshot = write_mutated_probe_snapshot(project, evidence, data_path, str(result["probe_id"]), mutated_sha256)
        syntax_check = structured_data_probe_syntax_check(project, data_path)
        result["mutation"]["mutated_sha256"] = mutated_sha256
        result["mutation"]["mutated_snapshot"] = snapshot
        result["mutation"]["syntax_check"] = syntax_check
        if syntax_check.get("ok") is not True:
            negative_passed = False
            result["checks"].append({
                "name": "probe_setup_keeps_data_file_syntax_valid",
                "passed": False,
                "evidence": syntax_check,
            })
            result["failures"].append("报名负向探针写回后的数据文件语法检查失败，不能把 setup_error 当作领域合同失败")
        else:
            result["checks"].append({
                "name": "probe_setup_keeps_data_file_syntax_valid",
                "passed": True,
                "evidence": syntax_check,
            })
            negative_run = run_command(argv, cwd=project, timeout_seconds=120)
            negative_receipt = command_receipt(negative_run)
            negative_payload = developer_validation_payload(evidence, project)
            result["negative_validation_payload"] = negative_payload
            contract_failure_detected = (
                domain_failure_detected(negative_receipt, "signup-intent-data-contract")
                or domain_failure_detected_in_payload(negative_payload, "signup-intent-data-contract")
            )
            negative_passed = negative_run.get("exit_code") not in (0, None) and contract_failure_detected
            if negative_run.get("exit_code") not in (0, None) and not contract_failure_detected:
                result["failures"].append("报名负向探针触发了非零退出，但输出没有指向报名合同失败，疑似 setup_error 或非目标错误")
        result["contract_failure_detected"] = bool(
            negative_receipt
            and (
                domain_failure_detected(negative_receipt, "signup-intent-data-contract")
                or domain_failure_detected_in_payload(result.get("negative_validation_payload"), "signup-intent-data-contract")
            )
        )
        result["checks"].append({
            "name": "malformed_signup_data_rejected",
            "passed": negative_passed,
            "evidence": {
                "exit_code": negative_receipt.get("exit_code") if isinstance(negative_receipt, dict) else None,
                "stdout_tail": negative_receipt.get("stdout_tail") if isinstance(negative_receipt, dict) else None,
                "stderr_tail": negative_receipt.get("stderr_tail") if isinstance(negative_receipt, dict) else None,
                "domain_failure_detected": result["contract_failure_detected"],
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


CharacterPlayerMatch = tuple[pathlib.Path, Any, str, int, str, int, str, str, list[str]]


def prefer_deeper_character_player_match(matches: list[CharacterPlayerMatch]) -> CharacterPlayerMatch:
    return next(
        (
            match for match in matches
            if match[3] > 0 or match[5] > 0 or signup_probe_uses_non_first_path(match[2], match[3])
        ),
        matches[0],
    )


def relation_parent_ids(container: dict[str, Any], parent_key: str) -> set[str]:
    parents = container.get(parent_key)
    if not isinstance(parents, list):
        return set()
    ids: set[str] = set()
    for parent in parents:
        if not isinstance(parent, dict):
            continue
        for key in ["id", "uid", "name"]:
            value = parent.get(key)
            if value:
                ids.add(str(value))
    return ids


def append_relation_matches(
    matches: list[CharacterPlayerMatch],
    data_path: pathlib.Path,
    payload: dict[str, Any] | list[Any],
    list_key: str,
    event_index: int,
    container: dict[str, Any],
    failures: list[str],
) -> None:
    parent_id_sets = [
        (parent_key, relation_parent_ids(container, parent_key))
        for parent_key in RELATION_PARENT_LIST_KEYS
    ]
    parent_id_sets = [(key, ids) for key, ids in parent_id_sets if ids]
    for child_key in RELATION_CHILD_LIST_KEYS:
        children = container.get(child_key)
        if not isinstance(children, list):
            continue
        for child_index, child in enumerate(children):
            if not isinstance(child, dict):
                continue
            for ref_key in RELATION_REFERENCE_KEYS:
                ref = child.get(ref_key)
                if not isinstance(ref, (str, int, float)) or not str(ref).strip():
                    continue
                ref_value = str(ref)
                if parent_id_sets:
                    for parent_key, parent_ids in parent_id_sets:
                        if ref_value in parent_ids:
                            matches.append((data_path, payload, list_key, event_index, child_key, child_index, ref_key, parent_key, failures))
                elif ref_key in RELATION_NAME_REFERENCE_KEYS:
                    matches.append((data_path, payload, list_key, event_index, child_key, child_index, ref_key, "__name_reference__", failures))


def find_character_player_contract_data_target(project: pathlib.Path) -> tuple[pathlib.Path | None, dict[str, Any] | list[Any] | None, str | None, int | None, str | None, int | None, str | None, str | None, list[str]]:
    failures: list[str] = []
    for data_path in structured_data_candidate_paths(project):
        if not data_path.exists():
            continue
        payload = load_structured_data_payload(project, data_path, failures)
        if payload is None:
            continue
        candidate_matches: list[CharacterPlayerMatch] = []
        if isinstance(payload, dict):
            append_relation_matches(candidate_matches, data_path, payload, "__top_level__", -1, payload, failures)
        list_candidates = top_level_data_list_candidates(payload)
        for list_key, records in list_candidates:
            for event_index, event in enumerate(records):
                if not isinstance(event, dict):
                    continue
                event_records: list[tuple[str, int, dict[str, Any]]] = [(list_key, event_index, event)]
                for child_key in SIGNUP_CHILD_LIST_KEYS:
                    child_records = event.get(child_key)
                    if not isinstance(child_records, list):
                        continue
                    nested_list_key = f"{list_key}.{event_index}.{child_key}"
                    for child_index, child_event in enumerate(child_records):
                        if isinstance(child_event, dict):
                            event_records.append((nested_list_key, child_index, child_event))
                for candidate_list_key, candidate_event_index, candidate_event in event_records:
                    append_relation_matches(candidate_matches, data_path, payload, candidate_list_key, candidate_event_index, candidate_event, failures)
        if candidate_matches:
            return prefer_deeper_character_player_match(candidate_matches)
        failures.append(f"{data_path.relative_to(project)} 未发现可破坏的实体引用关系")
    failures.append("未找到包含父实体列表与子实体引用关系的 JSON 或 JS 数据文件")
    return None, None, None, None, None, None, None, None, failures


def run_runner_character_player_contract_probe(project: pathlib.Path, evidence: pathlib.Path) -> dict[str, Any]:
    argv, source = detect_validation_command(project)
    data_path, data, list_key, event_index, child_key, child_index, ref_key, parent_key, location_failures = find_character_player_contract_data_target(project)
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
        "relation_child_key": child_key,
        "child_index": child_index,
        "parent_key": parent_key,
        "reference_key": ref_key,
        "ok": False,
        "checks": [],
        "failures": [],
    }
    if argv is None:
        result["failures"].append("无法发现验证命令，不能执行角色玩家负向契约探针")
        return result
    if data_path is None or data is None or list_key is None or event_index is None or child_key is None or child_index is None or ref_key is None:
        result["failures"].extend(location_failures)
        return result
    original_bytes = data_path.read_bytes()
    original_sha256 = hashlib.sha256(original_bytes).hexdigest()
    mutated = copy.deepcopy(data)
    if list_key == "__top_level__":
        event = mutated if isinstance(mutated, dict) else None
        children = event.get(child_key) if isinstance(event, dict) else None
        event_count = 1 if isinstance(event, dict) else 0
    else:
        records = signup_probe_records_at_list_key(mutated, list_key)
        if not isinstance(records, list) or event_index is None or event_index >= len(records) or not isinstance(records[event_index], dict):
            result["failures"].append(f"{data_path.relative_to(project)} 中 {list_key}[{event_index}] 不是可变更对象")
            return result
        event = records[event_index]
        children = event.get(child_key)
        event_count = len(records)
    if not isinstance(children, list) or child_index >= len(children) or not isinstance(children[child_index], dict):
        result["failures"].append(f"{data_path.relative_to(project)} 中 {child_key}[{child_index}] 不是可变更对象")
        return result
    result["probe_depth"] = {
        "event_count": event_count,
        "child_count_in_target_event": len(children),
        "targeted_non_first_event": bool(event_index is not None and event_index > 0),
        "targeted_non_first_child": child_index > 0,
        "selection_rule": "prefer_non_first_event_or_child_then_first_available",
    }
    original_ref = children[child_index].get(ref_key)
    broken_ref = "" if ref_key in RELATION_NAME_REFERENCE_KEYS else "__redcap_missing_reference__"
    children[child_index][ref_key] = broken_ref
    result["mutation"] = {
        "executor": "runner_internal",
        "event_id": event.get("id"),
        "child_name": children[child_index].get("name") or children[child_index].get("title"),
        "data_path": str(data_path.relative_to(project)),
        "list_key": list_key,
        "event_index": event_index,
        "relation_child_key": child_key,
        "child_index": child_index,
        "parent_key": parent_key,
        "target_path": f"{list_key}[{event_index}].{child_key}[{child_index}].{ref_key}",
        "changed_field": ref_key,
        "before": summarize_probe_value(original_ref),
        "after": summarize_probe_value(broken_ref),
        "original_sha256": original_sha256,
        "expected_validation_exit": "non_zero",
    }
    negative_receipt: dict[str, Any] | None = None
    try:
        write_structured_data_probe_payload(data_path, mutated)
        mutated_sha256 = sha256_file(data_path)
        snapshot = write_mutated_probe_snapshot(project, evidence, data_path, str(result["probe_id"]), mutated_sha256)
        syntax_check = structured_data_probe_syntax_check(project, data_path)
        result["mutation"]["mutated_sha256"] = mutated_sha256
        result["mutation"]["mutated_snapshot"] = snapshot
        result["mutation"]["syntax_check"] = syntax_check
        if syntax_check.get("ok") is not True:
            negative_passed = False
            result["checks"].append({
                "name": "probe_setup_keeps_data_file_syntax_valid",
                "passed": False,
                "evidence": syntax_check,
            })
            result["failures"].append("角色玩家负向探针写回后的数据文件语法检查失败，不能把 setup_error 当作领域合同失败")
        else:
            result["checks"].append({
                "name": "probe_setup_keeps_data_file_syntax_valid",
                "passed": True,
                "evidence": syntax_check,
            })
            negative_run = run_command(argv, cwd=project, timeout_seconds=120)
            negative_receipt = command_receipt(negative_run)
            negative_payload = developer_validation_payload(evidence, project)
            result["negative_validation_payload"] = negative_payload
            contract_failure_detected = (
                domain_failure_detected(negative_receipt, "character-player-relation-contract")
                or domain_failure_detected_in_payload(negative_payload, "character-player-relation-contract")
            )
            negative_passed = negative_run.get("exit_code") not in (0, None) and contract_failure_detected
            if negative_run.get("exit_code") not in (0, None) and not contract_failure_detected:
                result["failures"].append("角色玩家负向探针触发了非零退出，但输出没有指向角色玩家关系合同失败，疑似 setup_error 或非目标错误")
        result["contract_failure_detected"] = bool(
            negative_receipt
            and (
                domain_failure_detected(negative_receipt, "character-player-relation-contract")
                or domain_failure_detected_in_payload(result.get("negative_validation_payload"), "character-player-relation-contract")
            )
        )
        result["checks"].append({
            "name": "broken_character_player_link_rejected",
            "passed": negative_passed,
            "evidence": {
                "exit_code": negative_receipt.get("exit_code") if isinstance(negative_receipt, dict) else None,
                "stdout_tail": negative_receipt.get("stdout_tail") if isinstance(negative_receipt, dict) else None,
                "stderr_tail": negative_receipt.get("stderr_tail") if isinstance(negative_receipt, dict) else None,
                "domain_failure_detected": result["contract_failure_detected"],
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
    checked: list[str] = []
    for rel in BROWSER_ENTRYPOINT_CANDIDATES:
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


def run_file_browser_inspection(project: pathlib.Path, evidence: pathlib.Path) -> dict[str, Any]:
    target, target_rel, checked_entrypoints = detect_browser_entrypoint(project)
    screenshot = evidence / "file-browser-inspection.png"
    result: dict[str, Any] = {
        "schema_id": "redcap-e2e-file-browser-inspection",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "target": str(target) if target is not None else None,
        "target_relative_path": target_rel,
        "checked_entrypoints": checked_entrypoints,
        "file_url": target.as_uri() if target is not None and target.exists() else None,
        "launch_mode": "local-file-protocol",
        "screenshot": "file-browser-inspection.png",
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
    console_errors: list[str] = []
    page_errors: list[str] = []
    browser_version = None
    title = ""
    body_text = ""
    interactive_count = 0
    element_count = 0
    file_url = target.as_uri()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser_version = browser.version
            page = browser.new_page(viewport=FILE_BROWSER_INSPECTION_VIEWPORT)
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(file_url, wait_until="domcontentloaded", timeout=20_000)
            page.wait_for_timeout(800)
            title = page.title()
            body_text = page.locator("body").inner_text(timeout=5_000)
            interactive_count = page.locator("button, input, select, textarea, a[href]").count()
            element_count = page.locator("body *").count()
            page.screenshot(path=str(screenshot), full_page=True)
            browser.close()
    except Exception as exc:
        result["failures"].append(f"file:// 浏览器检查执行失败：{type(exc).__name__}: {exc}")
        return result
    visible_text = body_text.strip()
    checks = [
        {"name": "file_url_loaded", "passed": True, "evidence": file_url},
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
                "path": "file-browser-inspection.png",
                "sha256": sha256_file(screenshot) if screenshot.exists() else None,
                "size": screenshot.stat().st_size if screenshot.exists() else 0,
            },
        },
    ]
    failures = [f"file:// 浏览器检查失败：{item['name']}" for item in checks if item.get("passed") is not True]
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
            "viewport": FILE_BROWSER_INSPECTION_VIEWPORT,
            "capture_role": "file-browser-inspection",
            "screenshot_phase": "file_protocol_render",
            "protocol": "file",
            "visual_independence_strategy": "different_viewport_from_http_browser_inspection",
        },
        "checks": checks,
        "failures": failures,
    })
    return result


def find_character_player_probe(project: pathlib.Path) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []

    def event_title(value: Any) -> str:
        if not isinstance(value, dict):
            return ""
        for key in ["title", "name", "label"]:
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        return ""

    def person_name(value: Any) -> str:
        if not isinstance(value, dict):
            return ""
        for key in ["name", "displayName", "display_name", "nickname", "label"]:
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        return ""

    def append_event_candidates(
        *,
        data_path: pathlib.Path,
        list_key: str | None,
        event_index: int | None,
        event: dict[str, Any],
        parent_titles: list[str],
        path_indexes: list[int],
    ) -> None:
        characters = event.get("characters")
        if not isinstance(characters, list):
            return
        players = event.get("players")
        player_by_id = {
            str(player.get("id")): person_name(player)
            for player in players
            if isinstance(player, dict) and player.get("id") and person_name(player)
        } if isinstance(players, list) else {}
        activities = event.get("activities")
        activity_title_by_id = {
            str(activity.get("id")): event_title(activity)
            for activity in activities
            if isinstance(activity, dict) and activity.get("id") and event_title(activity)
        } if isinstance(activities, list) else {}
        title = parent_titles[-1] if parent_titles else event_title(event)
        record_title = event_title(event)
        for character_index, character in enumerate(characters):
            if not isinstance(character, dict):
                continue
            character_name = str(character.get("name") or "")
            player_name = player_by_id.get(str(character.get("playerId") or character.get("player_id") or ""))
            if not player_name:
                player_name = str(character.get("player") or character.get("playerName") or character.get("player_name") or "")
            character_activity_title = activity_title_by_id.get(str(character.get("activityId") or character.get("activity_id") or ""))
            candidate_title = title or character_activity_title or record_title
            candidate_record_title = character_activity_title or record_title
            if character_name and player_name:
                candidates.append({
                    "data_file": data_path.relative_to(project).as_posix(),
                    "list_key": list_key,
                    "event_index": event_index,
                    "event_title": candidate_title or data_path.stem,
                    "record_title": candidate_record_title or None,
                    "path_indexes": path_indexes,
                    "character_index": character_index,
                    "character_name": character_name,
                    "player_name": player_name,
                })

    def walk_payload(
        *,
        data_path: pathlib.Path,
        value: Any,
        path: str,
        parent_titles: list[str],
        path_indexes: list[int],
        list_key: str | None = None,
        event_index: int | None = None,
    ) -> None:
        if isinstance(value, dict):
            append_event_candidates(
                data_path=data_path,
                list_key=list_key,
                event_index=event_index,
                event=value,
                parent_titles=parent_titles,
                path_indexes=path_indexes,
            )
            title = event_title(value)
            next_parent_titles = parent_titles + ([title] if title else [])
            for key, child in value.items():
                if isinstance(child, list):
                    child_list_key = f"{path}.{key}" if path and path != "$" else key
                    for child_index, item in enumerate(child):
                        walk_payload(
                            data_path=data_path,
                            value=item,
                            path=f"{child_list_key}.{child_index}",
                            parent_titles=next_parent_titles,
                            path_indexes=path_indexes + [child_index],
                            list_key=child_list_key,
                            event_index=child_index,
                        )
                elif isinstance(child, dict):
                    child_path = f"{path}.{key}" if path and path != "$" else key
                    walk_payload(
                        data_path=data_path,
                        value=child,
                        path=child_path,
                        parent_titles=next_parent_titles,
                        path_indexes=path_indexes,
                        list_key=list_key,
                        event_index=event_index,
                    )
        elif isinstance(value, list):
            child_list_key = path if path and path != "$" else "root-list"
            for child_index, item in enumerate(value):
                walk_payload(
                    data_path=data_path,
                    value=item,
                    path=f"{child_list_key}.{child_index}",
                    parent_titles=parent_titles,
                    path_indexes=path_indexes + [child_index],
                    list_key=child_list_key,
                    event_index=child_index,
                )

    for data_path in structured_data_candidate_paths(project):
        if not data_path.exists():
            continue
        failures: list[str] = []
        payload = load_structured_data_payload(project, data_path, failures)
        if payload is None:
            continue
        walk_payload(
            data_path=data_path,
            value=payload,
            path="$",
            parent_titles=[],
            path_indexes=[],
        )
    if not candidates:
        return None
    # Prefer a non-first path when available so the browser proof must perform
    # a real selection before checking the character-player relation. For nested
    # data, path_indexes catches cases like campaigns[1].sessions[0].
    for candidate in candidates:
        indexes = candidate.get("path_indexes")
        if isinstance(indexes, list) and any(isinstance(index, int) and index > 0 for index in indexes):
            return candidate
    for candidate in candidates:
        if isinstance(candidate.get("event_index"), int) and candidate["event_index"] > 0:
            return candidate
    return candidates[0]


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


def click_matching_browser_control(page: Any, requested_title: str, *, control_kind: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "control_kind": control_kind,
        "requested_title": requested_title,
        "clicked": False,
        "label": None,
        "reason": "no_requested_title" if not requested_title else "no_matching_control_clicked",
    }
    if not requested_title:
        return result
    controls = page.locator("button, [role='button']")
    for control_index in range(min(controls.count(), 24)):
        control = controls.nth(control_index)
        try:
            label = control.inner_text(timeout=2_000).strip()
        except Exception:
            continue
        if not label:
            continue
        title_match = requested_title in label or label in requested_title
        if not title_match:
            continue
        try:
            control.click(timeout=5_000)
            page.wait_for_timeout(500)
            return {
                "control_kind": control_kind,
                "requested_title": requested_title,
                "clicked": True,
                "label": label,
                "index": control_index,
                "reason": f"matched_{control_kind}_title",
            }
        except Exception as exc:
            return {
                "control_kind": control_kind,
                "requested_title": requested_title,
                "clicked": False,
                "label": label,
                "index": control_index,
                "reason": f"matching_control_click_failed:{type(exc).__name__}",
            }
    return result


def click_relation_view_control(page: Any, character_name: str, player_name: str) -> dict[str, Any]:
    """探索可能承载角色和玩家关系的视图入口。"""
    result: dict[str, Any] = {
        "control_kind": "relation_view",
        "clicked": False,
        "label": None,
        "index": None,
        "reason": "no_relation_view_control_clicked",
        "attempts": [],
    }
    try:
        initial_text = page.locator("body").inner_text(timeout=5_000)
    except Exception as exc:
        result["reason"] = f"initial_text_read_failed:{type(exc).__name__}"
        return result
    if character_name in initial_text and player_name in initial_text:
        result["reason"] = "relation_names_already_visible"
        return result

    relation_keywords = [
        "角色",
        "玩家",
        "关系",
        "绑定",
        "资料",
        "名单",
        "成员",
        "队伍",
        "管理",
        "character",
        "characters",
        "player",
        "players",
        "relation",
        "relations",
        "binding",
        "roster",
        "party",
        "profile",
        "profiles",
        "admin",
    ]
    controls = page.locator("button, [role='button'], [role='tab'], a[href], [data-view], [aria-controls]")
    candidates: list[dict[str, Any]] = []
    for control_index in range(min(controls.count(), 64)):
        control = controls.nth(control_index)
        try:
            if not control.is_visible(timeout=1_000):
                continue
        except Exception:
            continue
        try:
            label = control.inner_text(timeout=1_000).strip()
        except Exception:
            label = ""
        attrs: dict[str, str] = {}
        for attr in ["aria-label", "title", "data-view", "data-testid", "href", "role", "class"]:
            try:
                value = control.get_attribute(attr, timeout=1_000)
            except Exception:
                value = None
            if value:
                attrs[attr] = str(value)
        haystack = " ".join([label, *attrs.values()]).lower()
        matched_keywords = [keyword for keyword in relation_keywords if keyword.lower() in haystack]
        if not matched_keywords:
            continue
        score = len(set(matched_keywords))
        if any(keyword in matched_keywords for keyword in ["角色", "character", "characters"]):
            score += 3
        if any(keyword in matched_keywords for keyword in ["玩家", "player", "players"]):
            score += 2
        if any(keyword in matched_keywords for keyword in ["关系", "绑定", "relation", "relations", "binding"]):
            score += 2
        candidates.append({
            "index": control_index,
            "label": label,
            "attributes": attrs,
            "matched_keywords": matched_keywords,
            "score": score,
        })
    candidates.sort(key=lambda item: (-int(item["score"]), int(item["index"])))
    for candidate in candidates[:16]:
        control_index = int(candidate["index"])
        control = controls.nth(control_index)
        attempt = {
            "index": control_index,
            "label": candidate.get("label"),
            "attributes": candidate.get("attributes"),
            "matched_keywords": candidate.get("matched_keywords"),
            "score": candidate.get("score"),
            "clicked": False,
            "character_visible_after_click": False,
            "player_visible_after_click": False,
        }
        try:
            before_snapshot = browser_observable_snapshot(page)
            control.click(timeout=5_000)
            page.wait_for_timeout(500)
            after_snapshot = browser_observable_snapshot(page)
            after_text = after_snapshot["text"]
            character_visible = character_name in after_text
            player_visible = player_name in after_text
            attempt.update({
                "clicked": True,
                "text_changed": before_snapshot["text_hash"] != after_snapshot["text_hash"],
                "dom_summary_changed": before_snapshot["dom_summary_hash"] != after_snapshot["dom_summary_hash"],
                "character_visible_after_click": character_visible,
                "player_visible_after_click": player_visible,
            })
            result["attempts"].append(attempt)
            if character_visible and player_visible:
                result.update({
                    "clicked": True,
                    "label": candidate.get("label"),
                    "index": control_index,
                    "attributes": candidate.get("attributes"),
                    "matched_keywords": candidate.get("matched_keywords"),
                    "reason": "relation_names_visible_after_click",
                })
                return result
        except Exception as exc:
            attempt["error"] = f"{type(exc).__name__}: {exc}"
            result["attempts"].append(attempt)
    if candidates:
        result["reason"] = "candidate_controls_did_not_reveal_both_relation_names"
    else:
        result["reason"] = "no_relation_keyword_control_found"
    return result


def focus_relation_container_for_screenshot(page: Any, character_name: str, player_name: str) -> dict[str, Any]:
    """滚动到真实关系容器，让关系截图截取关系视口。"""
    try:
        result = page.evaluate(
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
                const candidates = [];
                for (const element of Array.from(document.querySelectorAll(selector))) {
                    if (!visible(element)) continue;
                    const text = textOf(element);
                    if (!text.includes(characterName) || !text.includes(playerName)) continue;
                    if (["HTML", "BODY", "MAIN"].includes(element.tagName)) continue;
                    if (text.length > 1600) continue;
                    const rect = element.getBoundingClientRect();
                    candidates.push({ element, text, rect });
                }
                candidates.sort((a, b) => a.text.length - b.text.length);
                if (!candidates.length) {
                    return {
                        applied: false,
                        reason: "no_visible_relation_container",
                        focus_method: "scroll_relation_container_into_view",
                        character_visible: document.body.innerText.includes(characterName),
                        player_visible: document.body.innerText.includes(playerName)
                    };
                }
                const target = candidates[0].element;
                const mutationRecords = [];
                const observer = new MutationObserver((records) => {
                    for (const record of records) {
                        mutationRecords.push({
                            type: record.type,
                            target: record.target && record.target.nodeType === Node.ELEMENT_NODE ? record.target.tagName.toLowerCase() : String(record.target && record.target.nodeName || ""),
                            attributeName: record.attributeName || null
                        });
                    }
                });
                observer.observe(document.documentElement, {
                    attributes: true,
                    childList: true,
                    characterData: true,
                    subtree: true
                });
                const beforeScroll = { x: window.scrollX, y: window.scrollY };
                const beforeRect = target.getBoundingClientRect();
                target.scrollIntoView({ block: "center", inline: "nearest" });
                for (const record of observer.takeRecords()) {
                    mutationRecords.push({
                        type: record.type,
                        target: record.target && record.target.nodeType === Node.ELEMENT_NODE ? record.target.tagName.toLowerCase() : String(record.target && record.target.nodeName || ""),
                        attributeName: record.attributeName || null
                    });
                }
                observer.disconnect();
                const rect = target.getBoundingClientRect();
                const viewport = { width: window.innerWidth, height: window.innerHeight };
                const intersectsViewport = rect.bottom > 0 && rect.top < viewport.height && rect.right > 0 && rect.left < viewport.width;
                const visibleWidth = Math.max(0, Math.min(rect.right, viewport.width) - Math.max(rect.left, 0));
                const visibleHeight = Math.max(0, Math.min(rect.bottom, viewport.height) - Math.max(rect.top, 0));
                const rectArea = Math.max(1, rect.width * rect.height);
                const visibleAreaRatio = (visibleWidth * visibleHeight) / rectArea;
                return {
                    applied: true,
                    reason: "relation_container_scrolled_into_view_for_screenshot",
                    focus_method: "scroll_relation_container_into_view_and_capture_viewport",
                    dom_mutation: mutationRecords.length > 0,
                    mutationRecordCount: mutationRecords.length,
                    mutationRecords: mutationRecords.slice(0, 20),
                    tag: target.tagName.toLowerCase(),
                    id: target.id || null,
                    className: target.className || null,
                    textLength: textOf(target).length,
                    textExcerpt: textOf(target).slice(0, 300),
                    viewport,
                    beforeScroll,
                    afterScroll: { x: window.scrollX, y: window.scrollY },
                    rectBeforeScroll: { x: beforeRect.x, y: beforeRect.y, width: beforeRect.width, height: beforeRect.height },
                    rectAfterScroll: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                    visibleAreaRatio,
                    minimumVisibleAreaRatio: 0.5,
                    targetIntersectsViewport: intersectsViewport
                };
            }""",
            {"characterName": character_name, "playerName": player_name},
        )
    except Exception as exc:
        return {
            "applied": False,
            "reason": f"relation_focus_failed:{type(exc).__name__}",
            "focus_method": "scroll_relation_container_into_view",
            "error": str(exc),
        }
    return result if isinstance(result, dict) else {"applied": False, "reason": "relation_focus_returned_non_object"}


def reset_relation_probe_page_state(page: Any) -> dict[str, Any]:
    """关系探针截图后恢复默认行为验证视口与滚动位置。"""
    try:
        page.set_viewport_size(BEHAVIORAL_BROWSER_VIEWPORT)
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(100)
        result = page.evaluate(
            """() => ({
                viewport: { width: window.innerWidth, height: window.innerHeight },
                scroll: { x: window.scrollX, y: window.scrollY }
            })"""
        )
    except Exception as exc:
        return {
            "applied": False,
            "reason": f"relation_probe_reset_failed:{type(exc).__name__}",
            "error": str(exc),
        }
    viewport = result.get("viewport") if isinstance(result, dict) else None
    scroll = result.get("scroll") if isinstance(result, dict) else None
    return {
        "applied": True,
        "reason": "relation_probe_viewport_and_scroll_reset",
        "viewport": viewport,
        "scroll": scroll,
        "viewport_restored": viewport == BEHAVIORAL_BROWSER_VIEWPORT,
        "scroll_restored": isinstance(scroll, dict) and abs(float(scroll.get("x") or 0)) <= 1 and abs(float(scroll.get("y") or 0)) <= 1,
    }


def relation_container_clip(focus: dict[str, Any]) -> dict[str, float] | None:
    rect = focus.get("rectAfterScroll")
    viewport = focus.get("viewport")
    if not isinstance(rect, dict) or not isinstance(viewport, dict):
        return None
    try:
        viewport_width = float(viewport["width"])
        viewport_height = float(viewport["height"])
        x = max(0.0, float(rect["x"]) - 12.0)
        y = max(0.0, float(rect["y"]) - 12.0)
        width = min(float(rect["width"]) + 24.0, viewport_width - x)
        height = min(float(rect["height"]) + 24.0, viewport_height - y)
    except (KeyError, TypeError, ValueError):
        return None
    if width <= 1 or height <= 1:
        return None
    return {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
    }


def run_behavioral_browser_verification(project: pathlib.Path, evidence: pathlib.Path) -> dict[str, Any]:
    target, target_rel, checked_entrypoints = detect_browser_entrypoint(project)
    screenshot = evidence / "behavioral-browser-verification.png"
    relation_screenshot = evidence / "behavioral-relation-probe.png"
    relation_crop_screenshot = evidence / "behavioral-relation-container-crop.png"
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
    relation_required_payload = load_optional_json(evidence / "runner-character-player-contract-probe.json")
    relation_required = (
        (isinstance(relation_required_payload, dict) and relation_required_payload.get("ok") is True)
        or "character-player-relation-contract" in domain_contract_ids(evidence)
    )
    browser_inspection_screenshot = evidence / "browser-inspection.png"
    screenshot_phase = "not_captured"
    screenshot_phase_reason = "行为级浏览器验证尚未运行到截图阶段"
    relation_probe_browser_context: dict[str, Any] | None = None
    relation_crop_browser_context: dict[str, Any] | None = None
    relation_crop_record: dict[str, Any] | None = None
    relation_probe_reset: dict[str, Any] = {
        "applied": None,
        "reason": "no_relation_probe",
    }
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
            relation_passed = not relation_required
            relation_evidence: dict[str, Any] = {
                "probe_available": False,
                "relation_required": relation_required,
                "reason": (
                    "runner_character_player_contract_probe_passed_but_no_browser_probe_found"
                    if relation_required
                    else "character_player_relation_contract_not_required_for_this_project"
                ),
            }
            relation_visual_focus: dict[str, Any] = {
                "applied": None,
                "reason": "no_relation_probe",
            }
            if relation_probe:
                page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                page.wait_for_timeout(800)
                relation_event_title = str(relation_probe.get("event_title") or "")
                relation_record_title = str(relation_probe.get("record_title") or "")
                relation_event_control = click_matching_browser_control(page, relation_event_title, control_kind="event")
                relation_record_control: dict[str, Any] = {
                    "control_kind": "record",
                    "requested_title": relation_record_title,
                    "clicked": False,
                    "label": None,
                    "reason": "record_title_matches_event_title" if relation_record_title == relation_event_title else "no_requested_title",
                }
                if relation_record_title and relation_record_title != relation_event_title:
                    relation_record_control = click_matching_browser_control(page, relation_record_title, control_kind="record")
                character_name = str(relation_probe["character_name"])
                player_name = str(relation_probe["player_name"])
                relation_view_control = click_relation_view_control(page, character_name, player_name)
                relation_text = page.locator("body").inner_text(timeout=5_000)
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
                page.set_viewport_size(RELATION_PROBE_VIEWPORT)
                relation_visual_focus = focus_relation_container_for_screenshot(page, character_name, player_name)
                page.wait_for_timeout(200)
                page.screenshot(path=str(relation_screenshot), full_page=False)
                relation_clip = relation_container_clip(relation_visual_focus)
                if relation_clip is not None:
                    page.screenshot(path=str(relation_crop_screenshot), clip=relation_clip)
                    relation_crop_record = evidence_file_record(relation_crop_screenshot, base=evidence)
                    relation_crop_browser_context = {
                        "process_pid": os.getpid(),
                        "browser_version": browser_version,
                        "viewport": RELATION_PROBE_VIEWPORT,
                        "server_port": port,
                        "capture_role": "behavioral-relation-container-crop",
                        "screenshot_phase": "relation_container_crop",
                        "visual_independence_strategy": "crop_verified_relation_container_after_scroll",
                        "clip": relation_clip,
                    }
                relation_probe_browser_context = {
                    "process_pid": os.getpid(),
                    "browser_version": browser_version,
                    "viewport": RELATION_PROBE_VIEWPORT,
                    "server_port": port,
                    "capture_role": "behavioral-relation-probe",
                    "screenshot_phase": "relation_container_viewport",
                    "visual_independence_strategy": "scroll_real_relation_container_into_dedicated_viewport",
                    "dom_mutation": relation_visual_focus.get("dom_mutation"),
                }
                relation_probe_reset = reset_relation_probe_page_state(page)
                relation_event_title_visible = bool(relation_event_title and relation_event_title in relation_text)
                relation_record_title_visible = bool(relation_record_title and relation_record_title in relation_text)
                event_state_matched = not relation_event_title or relation_event_control.get("clicked") is True or relation_event_title_visible
                record_state_matched = (
                    not relation_record_title
                    or relation_record_title == relation_event_title
                    or relation_record_control.get("clicked") is True
                    or relation_record_title_visible
                )
                relation_passed = bool(
                    isinstance(dom_relation, dict)
                    and dom_relation.get("same_structural_container") is True
                    and event_state_matched
                    and record_state_matched
                )
                relation_evidence = {
                    "probe_available": True,
                    "relation_required": relation_required,
                    **relation_probe,
                    "relation_event_control": relation_event_control,
                    "relation_record_control": relation_record_control,
                    "relation_view_control": relation_view_control,
                    "relation_visual_focus": relation_visual_focus,
                    "relation_container_crop": {
                        "screenshot": relation_crop_record,
                        "browser_context": relation_crop_browser_context,
                    },
                    "relation_probe_reset": relation_probe_reset,
                    "relation_event_title_visible": relation_event_title_visible,
                    "relation_record_title_visible": relation_record_title_visible,
                    "relation_state_matched": {
                        "event_state_matched": event_state_matched,
                        "record_state_matched": record_state_matched,
                    },
                    "relation_probe_screenshot": evidence_file_record(relation_screenshot, base=evidence),
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
            "name": "relation_visual_focus_applied",
            "passed": (
                not relation_probe
                or (
                    relation_visual_focus.get("applied") is True
                    and relation_visual_focus.get("targetIntersectsViewport") is True
                    and float(relation_visual_focus.get("visibleAreaRatio") or 0) >= RELATION_PROBE_MIN_VISIBLE_RATIO
                    and int((relation_visual_focus.get("viewport") or {}).get("width") or 0) >= RELATION_PROBE_MIN_VIEWPORT["width"]
                    and int((relation_visual_focus.get("viewport") or {}).get("height") or 0) >= RELATION_PROBE_MIN_VIEWPORT["height"]
                    and relation_visual_focus.get("dom_mutation") is False
                )
            ),
            "evidence": relation_visual_focus,
        },
        {
            "name": "relation_probe_state_reset",
            "passed": (
                not relation_probe
                or (
                    relation_probe_reset.get("applied") is True
                    and relation_probe_reset.get("viewport_restored") is True
                    and relation_probe_reset.get("scroll_restored") is True
                )
            ),
            "evidence": relation_probe_reset,
        },
        {
            "name": "relation_container_crop_written",
            "passed": (
                not relation_probe
                or (
                    isinstance(relation_crop_record, dict)
                    and relation_crop_record.get("exists") is True
                    and int(relation_crop_record.get("size") or 0) > 0
                    and bool(relation_crop_record.get("sha256"))
                )
            ),
            "evidence": relation_crop_record or {
                "exists": False,
                "reason": "no_relation_crop_screenshot",
            },
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
        "relation_probe_screenshot_record": evidence_file_record(relation_screenshot, base=evidence),
        "relation_probe_browser_context": relation_probe_browser_context,
        "relation_container_crop_screenshot_record": relation_crop_record,
        "relation_container_crop_browser_context": relation_crop_browser_context,
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
checked_entrypoints = ["index.html", "app/index.html", "public/index.html", "dist/index.html", "build/index.html"]
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
    script_path = evidence / "independent-browser-verification-script.py"
    script_path.write_text(script.lstrip(), encoding="utf-8")
    script_sha256 = sha256_file(script_path)
    completed = subprocess.run(
        ["python3", str(script_path), str(project), str(evidence)],
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
    payload["script"] = {
        "path": script_path.relative_to(evidence).as_posix(),
        "sha256": script_sha256,
        "size": script_path.stat().st_size,
        "purpose": "独立浏览器验证脚本先写入证据目录并记录哈希，再由子进程执行，避免最终复核只能看到匿名内联代码。",
    }
    payload["command"] = command_receipt({
        "argv": ["python3", str(script_path), str(project), str(evidence)],
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
    if not isinstance(bundle_fingerprint, dict) or bundle_fingerprint.get("matches_declared_bundle_sha256") is not True:
        failures.append("independent-observer 必须独立证明 final-evidence-bundle.json 正文哈希等于 bundle_sha256 声明")
    if not isinstance(bundle_fingerprint, dict) or bundle_fingerprint.get("file_sha256_stable_after_cooldown") is not True:
        failures.append("independent-observer 必须证明 final-evidence-bundle.json 冷却后文件哈希保持稳定")
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
        ("file-browser-inspection", "file-browser-inspection.json", "file-browser-inspection.png"),
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
        if source_id == "behavioral-browser-verification":
            relation_record = payload.get("relation_probe_screenshot_record")
            relation_context_for_crop: dict[str, Any] | None = None
            if isinstance(relation_record, dict) and relation_record.get("exists") is True:
                relation_context = payload.get("relation_probe_browser_context")
                if not isinstance(relation_context, dict):
                    relation_context = dict(payload.get("browser_context") or {})
                    relation_context["capture_role"] = "behavioral-relation-probe"
                    relation_context["screenshot_phase"] = "after_relation_event_selection"
                relation_context_for_crop = relation_context
                sources.append({
                    "source_id": "behavioral-relation-probe",
                    "json": json_name,
                    "screenshot": relation_record,
                    "browser_context": relation_context,
                    "ok": payload.get("ok") is True,
                })
            crop_record = payload.get("relation_container_crop_screenshot_record")
            if isinstance(crop_record, dict) and crop_record.get("exists") is True:
                crop_context = payload.get("relation_container_crop_browser_context")
                sources.append({
                    "source_id": "behavioral-relation-container-crop",
                    "json": json_name,
                    "screenshot": crop_record,
                    "browser_context": crop_context if isinstance(crop_context, dict) else relation_context_for_crop,
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
    expected_png_paths: set[str] = set()
    source_by_id = {str(source.get("source_id")): source for source in sources}
    for source in sources:
        record = source.get("screenshot") if isinstance(source.get("screenshot"), dict) else {}
        if record.get("exists") is not True or not record.get("sha256"):
            failures.append(f"{source.get('source_id')} 缺少可哈希的截图证据")
        else:
            screenshot_hashes.append(str(record["sha256"]))
            if record.get("path"):
                expected_png_paths.add(str(record["path"]))
        context = source.get("browser_context")
        if not isinstance(context, dict):
            failures.append(f"{source.get('source_id')} 缺少 browser_context")
        else:
            required_context_keys = ["process_pid", "browser_version", "viewport", "capture_role", "screenshot_phase"]
            required_context_keys.append("protocol" if context.get("protocol") == "file" else "server_port")
            for key in required_context_keys:
                if context.get(key) in (None, "", {}):
                    failures.append(f"{source.get('source_id')} browser_context 缺少 {key}")
    actual_png_paths = sorted(path.name for path in evidence.glob("*.png"))
    unreported_png_paths = [path for path in actual_png_paths if path not in expected_png_paths]
    if unreported_png_paths:
        failures.append(f"视觉三角报告发现未纳入 sources 的截图文件：{unreported_png_paths}")
    distinct_hashes = sorted(set(screenshot_hashes))
    duplicate_hashes = sorted({item for item in screenshot_hashes if screenshot_hashes.count(item) > 1})
    allowed_duplicate_screenshot_hashes: list[dict[str, Any]] = []
    behavioral_source = source_by_id.get("behavioral-browser-verification", {})
    relation_source = source_by_id.get("behavioral-relation-probe", {})
    behavioral_record = behavioral_source.get("screenshot") if isinstance(behavioral_source.get("screenshot"), dict) else {}
    relation_record = relation_source.get("screenshot") if isinstance(relation_source.get("screenshot"), dict) else {}
    behavioral_payload = load_optional_json(evidence / "behavioral-browser-verification.json") or {}
    relation_check = next(
        (
            item for item in behavioral_payload.get("checks", [])
            if isinstance(item, dict) and item.get("name") == "character_player_relation_visible"
        ),
        None,
    )
    relation_evidence = relation_check.get("evidence") if isinstance(relation_check, dict) else None
    relation_event_control = relation_evidence.get("relation_event_control") if isinstance(relation_evidence, dict) else None
    relation_dom_probe = relation_evidence.get("dom_structural_probe") if isinstance(relation_evidence, dict) else None
    if (
        behavioral_record.get("exists") is True
        and relation_record.get("exists") is True
        and behavioral_record.get("sha256")
        and behavioral_record.get("sha256") == relation_record.get("sha256")
        and isinstance(relation_event_control, dict)
        and relation_event_control.get("clicked") is True
        and isinstance(relation_dom_probe, dict)
        and relation_dom_probe.get("same_structural_container") is True
    ):
        allowed_duplicate_screenshot_hashes.append({
            "sha256": behavioral_record.get("sha256"),
            "sources": ["behavioral-browser-verification", "behavioral-relation-probe"],
            "reason": "行为交互截图和关系探针截图处于同一已选活动状态时，像素相同是可接受结果；关系探针的新增证明来自 relation_event_control、relation_view_control 和 dom_structural_probe，而不是依赖像素差异。",
            "relation_event_control": relation_event_control,
            "dom_structural_probe_summary": {
                "same_structural_container": relation_dom_probe.get("same_structural_container"),
                "matched_container_count": relation_dom_probe.get("matched_container_count"),
            },
        })
    allowed_duplicate_hashes = {str(item.get("sha256")) for item in allowed_duplicate_screenshot_hashes if item.get("sha256")}
    unexpected_duplicate_hashes = [item for item in duplicate_hashes if item not in allowed_duplicate_hashes]
    if unexpected_duplicate_hashes:
        failures.append("视觉三角验证要求各截图哈希互不相同，当前存在重复截图哈希")
    observer_payload = load_optional_json(evidence / "independent-observer.json") or {}
    bundle_fingerprint = observer_payload.get("bundle_fingerprint")
    if not isinstance(bundle_fingerprint, dict) or bundle_fingerprint.get("matches_declared_bundle_sha256") is not True:
        failures.append("视觉三角报告要求观察者独立计算的证据包正文哈希与 bundle_sha256 声明一致")
    if not isinstance(bundle_fingerprint, dict) or bundle_fingerprint.get("file_sha256_stable_after_cooldown") is not True:
        failures.append("视觉三角报告要求观察者冷却后复核冻结包文件哈希稳定")
    return {
        "schema_id": "redcap-e2e-visual-independence-report",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "ok": not failures,
        "sources": sources,
        "distinct_screenshot_sha256_count": len(distinct_hashes),
        "screenshot_count": len(screenshot_hashes),
        "actual_png_files": actual_png_paths,
        "reported_png_files": sorted(expected_png_paths),
        "unreported_png_files": unreported_png_paths,
        "duplicate_screenshot_sha256": duplicate_hashes,
        "allowed_duplicate_screenshot_hashes": allowed_duplicate_screenshot_hashes,
        "unexpected_duplicate_screenshot_sha256": unexpected_duplicate_hashes,
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
                "passed": not unexpected_duplicate_hashes and len(screenshot_hashes) == len(sources),
                "evidence": {
                    "distinct": len(distinct_hashes),
                    "total": len(screenshot_hashes),
                    "hashes": screenshot_hashes,
                    "allowed_duplicates": allowed_duplicate_screenshot_hashes,
                    "unexpected_duplicates": unexpected_duplicate_hashes,
                },
            },
            {
                "name": "all_png_files_reported",
                "passed": not unreported_png_paths,
                "evidence": {
                    "actual_png_files": actual_png_paths,
                    "reported_png_files": sorted(expected_png_paths),
                    "unreported_png_files": unreported_png_paths,
                },
            },
            {
                "name": "browser_contexts_recorded",
                "passed": all(isinstance(source.get("browser_context"), dict) for source in sources),
            },
            {
                "name": "observer_bundle_declared_hash_matches",
                "passed": isinstance(bundle_fingerprint, dict) and bundle_fingerprint.get("matches_declared_bundle_sha256") is True,
            },
            {
                "name": "observer_bundle_file_hash_stable_after_cooldown",
                "passed": isinstance(bundle_fingerprint, dict) and bundle_fingerprint.get("file_sha256_stable_after_cooldown") is True,
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


def observer_request_payload_sha256(request: dict[str, Any]) -> str:
    return sha256_text(json.dumps(request, ensure_ascii=False, sort_keys=True))


def observer_request_routing_decision(request_path: pathlib.Path, worker_pid: int) -> dict[str, Any]:
    request = load_optional_json(request_path)
    if request is None:
        return {
            "ok": False,
            "ready": False,
            "reason": "unreadable",
            "request_path": str(request_path),
            "request_sha256": None,
        }
    request_sha256 = observer_request_payload_sha256(request)
    request_runner_pid = request.get("runner_pid")
    if request_runner_pid != worker_pid:
        return {
            "ok": True,
            "ready": False,
            "reason": "stale-runner-pid",
            "request_path": str(request_path),
            "request_sha256": request_sha256,
            "request_runner_pid": request_runner_pid,
            "worker_pid": worker_pid,
        }
    output = pathlib.Path(str(request.get("output") or ""))
    if output.exists():
        return {
            "ok": True,
            "ready": False,
            "reason": "output-already-exists",
            "request_path": str(request_path),
            "request_sha256": request_sha256,
            "request_runner_pid": request_runner_pid,
            "worker_pid": worker_pid,
            "output": str(output),
        }
    return {
        "ok": True,
        "ready": True,
        "reason": "current-worker-request",
        "request_path": str(request_path),
        "request_sha256": request_sha256,
        "request_runner_pid": request_runner_pid,
        "worker_pid": worker_pid,
    }


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


def redcap_source_revision() -> dict[str, Any]:
    relevant_paths = [
        "runtime/core/complete_revival_e2e.py",
        "runtime/core/revival_followthrough.py",
        "runtime/bin/redcap",
        "assets/contracts/complete-revival-e2e-acceptance-design.json",
    ]
    head_result = run_command(["git", "rev-parse", "--verify", "HEAD"], timeout_seconds=15)
    status_result = run_command(["git", "status", "--porcelain=v1", "--", *relevant_paths], timeout_seconds=15)
    diff_result = run_command([
        "git",
        "diff",
        "--",
        *relevant_paths,
    ], timeout_seconds=15)
    head = str(head_result.get("stdout") or "").strip() if head_result.get("ok") else None
    status_text = str(status_result.get("stdout") or "")
    diff_text = str(diff_result.get("stdout") or "")
    signature_material = "\n".join([
        str(head or ""),
        status_text,
        diff_text,
    ])
    return {
        "git_head": head,
        "dirty": bool(status_text.strip() or diff_text.strip()),
        "status_sha256": sha256_text(status_text) if status_text else None,
        "relevant_diff_sha256": sha256_text(diff_text) if diff_text else None,
        "source_signature": sha256_text(signature_material),
        "signature_scope": relevant_paths,
        "commands": {
            "head": command_receipt(head_result),
            "status": command_receipt(status_result),
            "diff": command_receipt(diff_result),
        },
    }


def classify_final_prism_convergence(final_prism: dict[str, Any], failures: list[str]) -> dict[str, Any]:
    reviews = final_prism.get("reviews") if isinstance(final_prism.get("reviews"), list) else []
    review_text = json.dumps(reviews, ensure_ascii=False).casefold()
    merge_text = json.dumps(final_prism.get("merge") if isinstance(final_prism.get("merge"), dict) else {}, ensure_ascii=False).casefold()
    failure_text = json.dumps(failures, ensure_ascii=False).casefold()
    combined = f"{review_text}\n{merge_text}\n{failure_text}"
    classes: list[dict[str, Any]] = []

    def add_class(loop_class: str, evidence_gap: str, required_next_action: str, *, auto_rerun_allowed: bool = False) -> None:
        if any(item.get("loop_class") == loop_class for item in classes):
            return
        classes.append({
            "loop_class": loop_class,
            "evidence_gap": evidence_gap,
            "required_next_action": required_next_action,
            "auto_rerun_allowed": auto_rerun_allowed,
        })

    if final_prism.get("skipped") is True:
        skip_reason = str(final_prism.get("skip_reason") or "")
        skipped_failures = final_prism.get("failures") if isinstance(final_prism.get("failures"), list) else []
        skipped_text = json.dumps([skip_reason, *skipped_failures, *failures], ensure_ascii=False).casefold()
        if any(token in skipped_text for token in [
            "前置客观证据",
            "precondition",
            "objective evidence",
            "runner probe",
            "运行器负向",
            "负向领域契约探针",
            "角色玩家负向",
            "structured data",
            "结构化数据",
        ]):
            add_class(
                "objective_evidence_precondition_gap",
                "最终棱镜复核因前置客观证据未通过而跳过，不能误判为角色制衡或最终评审语义问题。",
                "先修复运行器客观探针、结构化数据发现或项目验证证据，再重新执行 E2E；不要在未修复前盲目重跑。",
            )

    if any(token in combined for token in [
        "runner negative contract",
        "negative contract probe",
        "runner probe",
        "window.trpg_seed_data",
        "trpg_seed_data not set",
        "data/seed-data.js did not set",
        "js parse",
        "syntax-level",
        "syntax error",
        "mutation approach corrupts",
        "mutation_summary",
        "运行器负向",
        "负向合同探针",
        "数据加载失败",
        "语法失败",
        "领域合同",
    ]):
        add_class(
            "runner_negative_probe_semantics_gap",
            "最终评审认为运行器负向合同探针没有证明领域合同失败，而是退化为数据加载、语法或探针设置失败。",
            "先修复运行器内部动态 mutation、语法有效性检查、领域失败分类和 mutation_summary 证据，再重新执行 E2E。",
        )

    if any(token in combined for token in ["self-witness", "self witnessed", "self-referential", "same redcap", "same host", "out-of-band", "external anchor", "self-certification"]):
        add_class(
            "verification_authority_gap",
            "最终评审认为当前验收链仍可能由同一 RedCap 运行器自证，缺少足够清晰的外部锚点或工程试用边界。",
            "先补外部锚点证据、独立脚本哈希、边界降级声明或人工/非运行器验收入口，再重新执行 E2E。",
        )
    if any(token in combined for token in [
        "cross-role",
        "role opposition",
        "role_opposition",
        "opposition matrix",
        "opposition",
        "challenge evidence",
        "upstream challenge",
        "homogeneous loom",
        "same model",
        "角色制衡",
        "角色对抗",
        "上游挑战",
        "互相制衡",
        "同质化 loom",
        "同一模型",
    ]):
        add_class(
            "loom_opposition_gap",
            "最终评审认为 Loom 角色虽然分离，但缺少上游挑战、拒绝、复核或互相制衡的结构化证据。",
            "先让角色产物和 reviewer 产物强制记录 role_opposition_matrix 与 upstream_challenges，再重新执行 E2E。",
        )
    if any(token in combined for token in ["relation probe", "page-state", "probe alignment", "dom", "after a second-event click", "关系探针", "页面状态"]):
        add_class(
            "behavioral_evidence_alignment_gap",
            "最终评审认为浏览器行为截图、点击状态和角色玩家关系探针之间存在解释歧义。",
            "先让行为验证记录关系探针截图、目标活动选择和 DOM 结构证据，再重新执行 E2E。",
        )
    if final_prism.get("strictest_verdict") not in (None, "pass") and not classes:
        add_class(
            "unclassified_final_prism_concern",
            "最终棱镜未通过，但运行器尚未识别出具体可修复类别。",
            "先人工阅读 final-prism-review.json，把新类别写入运行器分类规则，再决定是否重跑。",
        )
    auto_rerun_allowed = bool(classes) and all(item.get("auto_rerun_allowed") is True for item in classes)
    if not classes and final_prism.get("ok") is True:
        auto_rerun_allowed = False
    return {
        "schema_id": "redcap-e2e-convergence-diagnosis",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "redcap_source": redcap_source_revision(),
        "final_prism_ok": final_prism.get("ok") is True,
        "strictest_verdict": final_prism.get("strictest_verdict"),
        "auto_rerun_allowed": auto_rerun_allowed,
        "diagnosis": classes,
        "summary": (
            "最终棱镜已通过，不需要循环重跑。"
            if final_prism.get("ok") is True
            else "最终棱镜未通过；若 diagnosis 中 auto_rerun_allowed=false，禁止继续无意义重跑，必须先修复对应 RedCap 机制。"
        ),
        "source": "final-prism-review.json",
    }


def convergence_diagnosis_from_evidence(evidence: pathlib.Path) -> dict[str, Any]:
    final_prism = load_optional_json(evidence / "final-prism-review.json")
    run_summary = load_optional_json(evidence / "run-summary.json")
    iteration_verdict = load_optional_json(evidence / "iteration-verdict.json")
    failure_backlog = load_optional_json(evidence / "failure-backlog.json")
    failures: list[str] = []
    if isinstance(run_summary, dict):
        failures.extend(str(item) for item in run_summary.get("failures", []) if item)
    if isinstance(iteration_verdict, dict):
        failures.extend(str(item) for item in iteration_verdict.get("remaining_issues", []) if item)
    if isinstance(failure_backlog, dict):
        for item in failure_backlog.get("open_items", []):
            if isinstance(item, dict):
                failures.append(str(item.get("summary") or item))
            else:
                failures.append(str(item))
    if not isinstance(final_prism, dict):
        final_prism = {
            "schema_id": "redcap-e2e-final-prism-review",
            "producer": "e2e-runner",
            "ok": False,
            "strictest_verdict": None,
            "reviews": [],
            "failures": ["缺少 final-prism-review.json，无法证明最终评审通过。"],
        }
        failures.append("缺少 final-prism-review.json，无法证明最终评审通过。")
    diagnosis = classify_final_prism_convergence(final_prism, failures)
    diagnosis["replay"] = {
        "source_evidence_root": str(evidence),
        "used_files": [
            rel for rel in [
                "final-prism-review.json",
                "run-summary.json",
                "iteration-verdict.json",
                "failure-backlog.json",
            ] if (evidence / rel).exists()
        ],
        "failure_count": len(failures),
    }
    return diagnosis


def find_latest_structural_convergence(work_root: pathlib.Path) -> dict[str, Any] | None:
    resolved = work_root.resolve()
    search_roots = [resolved]
    if resolved.parent.name == DEFAULT_PERSISTENT_WORK_ROOT.name:
        search_roots.append(resolved.parent)
    elif resolved == DEFAULT_PERSISTENT_WORK_ROOT:
        search_roots.append(DEFAULT_PERSISTENT_WORK_ROOT)
    candidates: list[tuple[float, pathlib.Path, dict[str, Any]]] = []
    for root in unique_preserve_order([str(path) for path in search_roots]):
        root_path = pathlib.Path(root)
        if not root_path.exists():
            continue
        for path in root_path.glob("**/.redcap/evidence/e2e/convergence-diagnosis.json"):
            payload = load_optional_json(path)
            if not isinstance(payload, dict):
                continue
            if payload.get("final_prism_ok") is True:
                continue
            if payload.get("auto_rerun_allowed") is not False:
                continue
            diagnosis = payload.get("diagnosis")
            if not isinstance(diagnosis, list) or not diagnosis:
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            candidates.append((mtime, path, payload))
    if not candidates:
        return None
    _, path, payload = sorted(candidates, key=lambda item: item[0], reverse=True)[0]
    return {"path": path, "payload": payload}


def convergence_rerun_guard(work_root: pathlib.Path) -> dict[str, Any]:
    latest = find_latest_structural_convergence(work_root)
    current_source = redcap_source_revision()
    if latest is None:
        return {
            "schema_id": "redcap-e2e-convergence-rerun-guard",
            "ok": True,
            "blocked": False,
            "reason": "未发现上一轮结构性收敛阻断诊断。",
            "current_source": current_source,
        }
    payload = latest["payload"]
    recorded_source = payload.get("redcap_source") if isinstance(payload.get("redcap_source"), dict) else {}
    recorded_signature = recorded_source.get("source_signature") if isinstance(recorded_source, dict) else None
    current_signature = current_source.get("source_signature")
    source_changed = bool(recorded_signature and current_signature and recorded_signature != current_signature)
    if source_changed:
        return {
            "schema_id": "redcap-e2e-convergence-rerun-guard",
            "ok": True,
            "blocked": False,
            "reason": "上一轮结构性诊断已被新的 RedCap 源码变更覆盖，允许修复后验证。",
            "previous_diagnosis": str(latest["path"]),
            "recorded_source_signature": recorded_signature,
            "current_source_signature": current_signature,
            "current_source": current_source,
        }
    return {
        "schema_id": "redcap-e2e-convergence-rerun-guard",
        "ok": False,
        "blocked": True,
        "reason": "上一轮 convergence-diagnosis.json 设置 auto_rerun_allowed=false，且 RedCap 源码签名没有变化；禁止继续盲目重跑 E2E。",
        "previous_diagnosis": str(latest["path"]),
        "diagnosis": payload.get("diagnosis"),
        "required_next_action": "先修复 convergence-diagnosis.json 指出的 RedCap 机制缺口，再启动下一轮 E2E。",
        "recorded_source_signature": recorded_signature,
        "current_source_signature": current_signature,
        "current_source": current_source,
    }


def patrol_ledger_path(work_root: pathlib.Path) -> pathlib.Path:
    return work_root / "redcap-e2e-patrol-ledger.jsonl"


def load_patrol_events(work_root: pathlib.Path) -> list[dict[str, Any]]:
    path = patrol_ledger_path(work_root)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def patrol_iteration_guard(work_root: pathlib.Path) -> dict[str, Any]:
    events = load_patrol_events(work_root)
    started = [event for event in events if event.get("event") == "e2e_iteration_started"]
    finished = [event for event in events if event.get("event") == "e2e_iteration_finished"]
    next_iteration = len(started) + 1
    blocked = next_iteration > E2E_PATROL_MAX_ITERATIONS
    return {
        "schema_id": "redcap-e2e-patrol-iteration-guard",
        "ok": not blocked,
        "blocked": blocked,
        "max_iterations": E2E_PATROL_MAX_ITERATIONS,
        "started_iterations": len(started),
        "finished_iterations": len(finished),
        "next_iteration": next_iteration,
        "ledger": str(patrol_ledger_path(work_root)),
        "reason": (
            f"同一 E2E 巡检工作根目录已启动 {len(started)} 轮，达到 {E2E_PATROL_MAX_ITERATIONS} 轮硬上限；第 {next_iteration} 轮必须先由 Cap 仲裁并产出停止或修复决策。"
            if blocked
            else "E2E 巡检轮次未达到硬上限。"
        ),
    }


def long_task_active_run_path(work_root: pathlib.Path) -> pathlib.Path:
    return work_root / "redcap-long-task-active-run.json"


def long_task_active_run_check_path(work_root: pathlib.Path) -> pathlib.Path:
    return work_root / "redcap-long-task-active-run.check.json"


def work_root_evidence_signature(work_root: pathlib.Path) -> str:
    records: list[dict[str, Any]] = []
    for path in [
        patrol_ledger_path(work_root),
        work_root / "redcap-e2e-patrol-iteration-guard.json",
        work_root / "redcap-e2e-convergence-rerun-guard.json",
    ]:
        records.append(evidence_file_record(path))
    latest_summaries: list[dict[str, Any]] = []
    if work_root.exists():
        for path in sorted(work_root.glob("**/.redcap/evidence/e2e/run-summary.json"))[-5:]:
            latest_summaries.append(evidence_file_record(path, base=work_root))
        for path in sorted(work_root.glob("**/.redcap/evidence/e2e/convergence-diagnosis.json"))[-5:]:
            latest_summaries.append(evidence_file_record(path, base=work_root))
    material = json.dumps({
        "records": records,
        "latest_summaries": latest_summaries,
    }, ensure_ascii=False, sort_keys=True)
    return sha256_text(material)


def load_long_task_template() -> dict[str, Any]:
    if LONG_TASK_CONTRACT.exists():
        return load_json(LONG_TASK_CONTRACT)
    return {
        "schema_id": "redcap-long-task-contract",
        "risk_rating_examples": [
            {
                "task": "连续三轮 E2E 暴露同类结构性失败。",
                "expected_mode": "enabled",
                "reason": "达到多轮同类失败阈值，需要父目标、失败账本和防盲重跑。"
            },
            {
                "task": "修改 RedCap 自开发门禁和生命周期规则。",
                "expected_mode": "enabled",
                "reason": "中高风险自开发会改变任务治理能力，必须启用长任务合同。"
            },
            {
                "task": "同时影响发布包、项目 .redcap 运行时和源仓库边界。",
                "expected_mode": "enabled",
                "reason": "涉及两个以上独立边界，必须记录父目标和回滚停止条件。"
            },
            {
                "task": "回答字段含义，不修改文件。",
                "expected_mode": "fast_path",
                "reason": "解释型任务不需要父目标循环。"
            },
            {
                "task": "修复一个低风险错别字。",
                "expected_mode": "fast_path",
                "reason": "一步小修且可局部验证。"
            },
        ],
    }


def build_e2e_long_task_active_run(
    work_root: pathlib.Path,
    *,
    direction: str,
    iteration: int,
    status: str,
    action_evidence: list[str],
    objective_delta: str,
    blocker_signature: str,
    auto_rerun_allowed: bool,
    failures: list[str],
) -> dict[str, Any]:
    template = copy.deepcopy(load_long_task_template())
    source = redcap_source_revision()
    evidence_signature = work_root_evidence_signature(work_root)
    closed_summary = (
        f"第 {iteration} 轮 E2E 入口已产生父任务运行记录：{objective_delta}"
    )
    open_items = [
        {
            "id": f"e2e-round-{iteration}-failure-{index}",
            "summary": str(item)[:400],
        }
        for index, item in enumerate(failures, start=1)
        if str(item).strip()
    ]
    lifecycle_state = "completed" if status == "passed" else ("blocked" if status == "blocked" else "running")
    terminal_boundary = None
    if lifecycle_state != "running":
        terminal_boundary = {
            "outcome": lifecycle_state,
            "completed_at": iso_now(),
            "final_objective_delta": objective_delta,
            "completion_evidence": action_evidence,
            "evidence_quality": [
                {
                    "reference": item,
                    "confidence": "high",
                    "signals": ["e2e-runner", "active_run", "evidence"],
                    "structured": True,
                }
                for item in action_evidence
            ],
            "final_summary": objective_delta,
            "not_claimed": [
                "E2E active_run 只关闭当前巡检轮次，不自动证明 RedCap 完整复活。",
                "E2E active_run 不替代发布级验收或跨机器生产认证。",
            ],
        }
    active_run = {
        **template,
        "schema_id": "redcap-long-task-contract",
        "contract_kind": "active_run",
        "parent_objective": "推进 RedCap 完整复活 E2E 巡检，直到入口、角色、钩子、棱镜、自我净化和完成边界都有真实运行证据支撑。",
        "terminal_acceptance": [
            "每轮 E2E 都有真实动作证据、父目标推进差量和可复核证据签名。",
            "结构性失败不会被盲目重跑吞掉，必须进入失败待办或 Cap 仲裁。",
            "任何阶段收口都只声明本轮 E2E 状态，不声明 RedCap 永久完整复活。"
        ],
        "non_claimed_boundaries": [
            "active_run 只证明本轮长任务入口治理已接入，不证明完整复活已经终局完成。",
            "active_run 不替代 Loom 角色产物、项目级 hook 事件、最终棱镜复核或浏览器验收。",
            "active_run 不自动清除 Codex 外部目标工具的 blocked 状态。"
        ],
        "activation": {
            "mode": "enabled",
            "default_state": "off",
            "risk_level": "medium",
            "triggers": [
                "user_explicit_long_run",
                "redcap_self_development_medium_or_higher",
                "external_e2e_or_release_validation",
                "multi_role_loom_workflow",
                "multi_iteration_failure_repair",
                "cross_workspace_or_runtime_boundary_change",
            ],
            "thresholds": {
                "multi_iteration_failure_repair": {
                    "min_consecutive_failures": 3
                },
                "cross_workspace_or_runtime_boundary_change": {
                    "min_independent_boundaries": 2
                }
            }
        },
        "codex_goal_policy": {
            "blocked_meaning": "Codex 目标 blocked 是外部目标工具状态；它要求 Cap 对自动推进边界做仲裁，但不自动等同于 RedCap 工程失败或成功。",
            "blocked_equals_redcap_failure": False,
            "must_clear_before_new_task": False,
            "blocks_new_redcap_task": False,
            "internal_contract_may_override_external_goal": False,
            "arbitration_required_within_iterations": 1,
        },
        "loop_policy": {
            "max_iterations_before_cap_arbitration": 5,
            "repeated_blocker_threshold": 2,
            "structural_stop_threshold": 2,
            "require_action_evidence": True,
            "require_objective_delta": True,
            "require_failure_backlog": True,
            "no_blind_rerun_without_source_or_evidence_delta": True,
            "blocked_goal_requires_cap_arbitration": True,
            "human_decision_stops_automation": True,
        },
        "stop_conditions": {
            "success": [
                "本轮 E2E 终止验收证据通过，且完成边界声明完整。"
            ],
            "blocked": [
                "同一结构性阻塞连续重复且没有源码或证据变化。",
                "收敛诊断设置 auto_rerun_allowed=false。"
            ],
            "human_decision": [
                "涉及产品范围、外部账号、密钥、正式发布、破坏性操作或用户价值取舍。"
            ],
        },
        "failure_backlog": {
            "open": open_items,
            "closed": [] if open_items else [{"id": f"e2e-round-{iteration}-entry", "summary": closed_summary}],
        },
        "lifecycle_state": lifecycle_state,
        "auto_rerun_allowed": auto_rerun_allowed,
        "completion_boundary": terminal_boundary,
        "iteration_ledger": [
            {
                "iteration_id": f"e2e-round-{iteration}",
                "status": status,
                "action_evidence": action_evidence,
                "objective_delta": objective_delta,
                "blocker_signature": blocker_signature,
                "source_signature": source.get("source_signature"),
                "evidence_signature": evidence_signature,
                "auto_rerun_allowed": auto_rerun_allowed,
            }
        ],
        "capability_coverage": {
            "claim_scope": "只允许声明本轮 E2E 父任务 active_run 已接入并通过合同检查，不允许声明 RedCap 完整复活。",
            "completion_claim_allowed": False,
            "required_layers": [
                "task_entry_decision",
                "contract_validation",
                "active_run_ledger",
                "failure_backlog",
                "completion_boundary_guard",
                "stable_evidence_policy",
                "aggregate_check_integration",
                "prism_review_resolution",
            ],
        },
        "e2e_runtime_context": {
            "work_root": str(work_root),
            "direction_sha256": sha256_text(direction),
            "redcap_source": source,
        },
    }
    return active_run


def write_e2e_long_task_active_run(
    work_root: pathlib.Path,
    *,
    direction: str,
    iteration: int,
    status: str,
    action_evidence: list[str],
    objective_delta: str,
    blocker_signature: str,
    auto_rerun_allowed: bool,
    failures: list[str],
) -> dict[str, Any]:
    packet = build_e2e_long_task_active_run(
        work_root,
        direction=direction,
        iteration=iteration,
        status=status,
        action_evidence=action_evidence,
        objective_delta=objective_delta,
        blocker_signature=blocker_signature,
        auto_rerun_allowed=auto_rerun_allowed,
        failures=failures,
    )
    packet_path = long_task_active_run_path(work_root)
    write_json(packet_path, packet)
    check_result = run_command([
        str(REDCAP),
        "long-task",
        "check",
        "--packet",
        str(packet_path),
    ], timeout_seconds=60)
    check_receipt = command_receipt(check_result)
    check_receipt.update({
        "schema_id": "redcap-e2e-long-task-active-run-check",
        "packet": str(packet_path),
        "packet_sha256": sha256_file(packet_path),
        "iteration": iteration,
        "status": status,
    })
    write_json(long_task_active_run_check_path(work_root), check_receipt)
    try:
        packet_payload = load_json(packet_path)
    except Exception:
        packet_payload = {}
    completion_boundary = packet_payload.get("completion_boundary") if isinstance(packet_payload, dict) else None
    return {
        "schema_id": "redcap-e2e-long-task-active-run-status",
        "ok": check_result.get("ok") is True,
        "packet": str(packet_path),
        "check": str(long_task_active_run_check_path(work_root)),
        "check_receipt": check_receipt,
        "lifecycle_state": packet_payload.get("lifecycle_state") if isinstance(packet_payload, dict) else None,
        "completion_boundary_present": isinstance(completion_boundary, dict),
        "completion_boundary_outcome": completion_boundary.get("outcome") if isinstance(completion_boundary, dict) else None,
    }


def e2e_active_run_boundary_failures(
    active_run_status: dict[str, Any],
    *,
    phase: str,
    parsed_ok: bool | None = None,
    final_status: str | None = None,
    expected_lifecycle_state: str | None = None,
    require_completion_boundary: bool = False,
) -> list[str]:
    failures: list[str] = []
    lifecycle_state = active_run_status.get("lifecycle_state")
    completion_boundary_present = active_run_status.get("completion_boundary_present") is True
    completion_boundary_outcome = active_run_status.get("completion_boundary_outcome")
    if active_run_status.get("ok") is not True:
        if phase == "entry":
            failures.append("E2E 长任务 active_run 入口合同检查失败，不能启动项目执行。")
        elif phase == "final":
            failures.append("E2E 长任务 active_run 收束合同检查失败。")
        else:
            failures.append("E2E 巡检发现 active_run 包，但合同检查失败。")
    if phase == "entry":
        expected_lifecycle_state = "running"
        require_completion_boundary = False
        if lifecycle_state != expected_lifecycle_state:
            failures.append("E2E 长任务 active_run 入口状态必须是 running。")
        if completion_boundary_present:
            failures.append("E2E 长任务 active_run 入口不能带 completion_boundary。")
    elif phase == "final":
        expected_lifecycle_state = "completed" if parsed_ok else ("blocked" if final_status == "blocked" else "running")
        require_completion_boundary = parsed_ok is True
        if lifecycle_state != expected_lifecycle_state:
            failures.append(
                f"E2E 长任务 active_run 收束状态错误：期望 {expected_lifecycle_state}，实际 {lifecycle_state}"
            )
    elif expected_lifecycle_state is not None and lifecycle_state != expected_lifecycle_state:
        failures.append(f"E2E 巡检 active_run 状态不匹配：期望 {expected_lifecycle_state}，实际 {lifecycle_state}")
    if require_completion_boundary and not completion_boundary_present:
        if phase == "final":
            failures.append("E2E 通过时必须写入 active_run completion_boundary。")
        else:
            failures.append("E2E 巡检要求 completion_boundary，但 active_run 未提供。")
    if completion_boundary_present and completion_boundary_outcome != lifecycle_state:
        failures.append(f"E2E completion_boundary.outcome 必须匹配 lifecycle_state：{completion_boundary_outcome} != {lifecycle_state}")
    return failures


def e2e_active_run_entry_failures_via_boundary_check(active_run_status: dict[str, Any]) -> list[str]:
    return e2e_active_run_boundary_failures(active_run_status, phase="entry")


def e2e_active_run_final_failures_via_boundary_check(
    active_run_status: dict[str, Any],
    *,
    parsed_ok: bool,
    final_status: str,
) -> list[str]:
    return e2e_active_run_boundary_failures(
        active_run_status,
        phase="final",
        parsed_ok=parsed_ok,
        final_status=final_status,
    )


def discover_e2e_long_task_active_run(
    work_root: pathlib.Path,
    *,
    expected_lifecycle_state: str | None = None,
    require_completion_boundary: bool = False,
) -> dict[str, Any]:
    packet_path = long_task_active_run_path(work_root)
    failures: list[str] = []
    if not packet_path.exists():
        failures.append("E2E 巡检没有发现 active_run 包。")
        result = {
            "schema_id": "redcap-e2e-long-task-active-run-discovery",
            "ok": False,
            "event": "discover_active_run",
            "packet": str(packet_path),
            "failures": failures,
        }
        write_json(work_root / "redcap-e2e-long-task-active-run-discovery.json", result)
        append_jsonl(patrol_ledger_path(work_root), {
            "event": "e2e_active_run_discovered",
            "recorded_at": iso_now(),
            "ok": False,
            "packet": str(packet_path),
            "failures": failures,
        })
        return result

    check_result = run_command([
        str(REDCAP),
        "long-task",
        "check",
        "--packet",
        str(packet_path),
    ], timeout_seconds=60)
    check_receipt = command_receipt(check_result)
    try:
        packet_payload = load_json(packet_path)
    except Exception as exc:
        packet_payload = {}
        failures.append(f"无法读取 active_run 包：{exc}")
    completion_boundary = packet_payload.get("completion_boundary") if isinstance(packet_payload, dict) else None
    lifecycle_state = packet_payload.get("lifecycle_state") if isinstance(packet_payload, dict) else None
    completion_boundary_present = isinstance(completion_boundary, dict)
    completion_boundary_outcome = completion_boundary.get("outcome") if isinstance(completion_boundary, dict) else None
    failures.extend(e2e_active_run_boundary_failures(
        {
            "ok": check_result.get("ok") is True,
            "lifecycle_state": lifecycle_state,
            "completion_boundary_present": completion_boundary_present,
            "completion_boundary_outcome": completion_boundary_outcome,
        },
        phase="discover",
        expected_lifecycle_state=expected_lifecycle_state,
        require_completion_boundary=require_completion_boundary,
    ))
    result = {
        "schema_id": "redcap-e2e-long-task-active-run-discovery",
        "ok": not failures,
        "event": "discover_active_run",
        "packet": str(packet_path),
        "packet_sha256": sha256_file(packet_path),
        "check_receipt": check_receipt,
        "lifecycle_state": lifecycle_state,
        "completion_boundary_present": completion_boundary_present,
        "completion_boundary_outcome": completion_boundary_outcome,
        "expected_lifecycle_state": expected_lifecycle_state,
        "require_completion_boundary": require_completion_boundary,
        "failures": failures,
    }
    write_json(work_root / "redcap-e2e-long-task-active-run-discovery.json", result)
    append_jsonl(patrol_ledger_path(work_root), {
        "event": "e2e_active_run_discovered",
        "recorded_at": iso_now(),
        "ok": result["ok"],
        "packet": str(packet_path),
        "lifecycle_state": lifecycle_state,
        "completion_boundary_present": completion_boundary_present,
        "completion_boundary_outcome": completion_boundary_outcome,
        "failures": failures,
    })
    return result


def e2e_status_from_packet(packet_path: pathlib.Path, check_result: dict[str, Any]) -> dict[str, Any]:
    try:
        packet_payload = load_json(packet_path)
    except Exception:
        packet_payload = {}
    completion_boundary = packet_payload.get("completion_boundary") if isinstance(packet_payload, dict) else None
    return {
        "schema_id": "redcap-e2e-long-task-active-run-status",
        "ok": check_result.get("ok") is True,
        "packet": str(packet_path),
        "check_receipt": command_receipt(check_result),
        "lifecycle_state": packet_payload.get("lifecycle_state") if isinstance(packet_payload, dict) else None,
        "completion_boundary_present": isinstance(completion_boundary, dict),
        "completion_boundary_outcome": completion_boundary.get("outcome") if isinstance(completion_boundary, dict) else None,
    }


def run_e2e_active_run_runtime_boundary_probe(work_root: pathlib.Path) -> dict[str, Any]:
    probe_root = work_root / "active-run-runtime-boundary-probe"
    probe_root.mkdir(parents=True, exist_ok=True)
    direction = "运行时边界探针：确认 E2E 运行器真实拒绝非法 active_run 状态。"
    valid_root = probe_root / "valid-entry"
    valid_status = write_e2e_long_task_active_run(
        valid_root,
        direction=direction,
        iteration=1,
        status="running",
        action_evidence=["runtime/bin/redcap complete-revival-e2e runtime-boundary-probe"],
        objective_delta="运行时边界探针创建合法 running 入口包。",
        blocker_signature="none",
        auto_rerun_allowed=True,
        failures=[],
    )
    valid_entry_failures = e2e_active_run_entry_failures_via_boundary_check(valid_status)
    cases: list[dict[str, Any]] = []

    def run_case(name: str, mutation: dict[str, Any], *, expected_lifecycle_state: str | None, require_completion_boundary: bool) -> None:
        case_root = probe_root / name
        packet = build_e2e_long_task_active_run(
            case_root,
            direction=direction,
            iteration=1,
            status="running",
            action_evidence=["runtime/bin/redcap complete-revival-e2e runtime-boundary-probe"],
            objective_delta=f"运行时边界探针构造非法包：{name}",
            blocker_signature="runtime-boundary-probe",
            auto_rerun_allowed=False,
            failures=[],
        )
        for key, value in mutation.items():
            packet[key] = value
        packet_path = long_task_active_run_path(case_root)
        write_json(packet_path, packet)
        check_result = run_command([
            str(REDCAP),
            "long-task",
            "check",
            "--packet",
            str(packet_path),
        ], timeout_seconds=60)
        status = e2e_status_from_packet(packet_path, check_result)
        entry_failures = e2e_active_run_entry_failures_via_boundary_check(status)
        final_failures = e2e_active_run_final_failures_via_boundary_check(status, parsed_ok=True, final_status="passed")
        discovery = discover_e2e_long_task_active_run(
            case_root,
            expected_lifecycle_state=expected_lifecycle_state,
            require_completion_boundary=require_completion_boundary,
        )
        rejected = (
            check_result.get("ok") is not True
            and bool(entry_failures or final_failures)
            and discovery.get("ok") is not True
        )
        cases.append({
            "name": name,
            "rejected": rejected,
            "status": status,
            "entry_failures": entry_failures,
            "final_failures": final_failures,
            "discovery": discovery,
        })

    run_case(
        "illegal-lifecycle-state",
        {"lifecycle_state": "paused", "completion_boundary": None},
        expected_lifecycle_state="running",
        require_completion_boundary=False,
    )
    run_case(
        "running-with-completion-boundary",
        {
            "lifecycle_state": "running",
            "completion_boundary": {
                "outcome": "running",
                "completed_at": iso_now(),
                "final_objective_delta": "非法 running 包携带完成边界。",
                "completion_evidence": ["runtime/bin/redcap complete-revival-e2e runtime-boundary-probe"],
                "evidence_quality": [{"reference": "runtime/bin/redcap complete-revival-e2e runtime-boundary-probe", "confidence": "high"}],
                "final_summary": "非法 running 包携带完成边界。",
            },
        },
        expected_lifecycle_state="running",
        require_completion_boundary=False,
    )
    run_case(
        "completed-without-completion-boundary",
        {"lifecycle_state": "completed", "completion_boundary": None},
        expected_lifecycle_state="completed",
        require_completion_boundary=True,
    )
    run_case(
        "completion-boundary-outcome-mismatch",
        {
            "lifecycle_state": "completed",
            "completion_boundary": {
                "outcome": "blocked",
                "completed_at": iso_now(),
                "final_objective_delta": "非法完成边界 outcome 与 lifecycle_state 不一致。",
                "completion_evidence": ["runtime/bin/redcap complete-revival-e2e runtime-boundary-probe"],
                "evidence_quality": [{"reference": "runtime/bin/redcap complete-revival-e2e runtime-boundary-probe", "confidence": "high"}],
                "final_summary": "非法完成边界 outcome 与 lifecycle_state 不一致。",
            },
        },
        expected_lifecycle_state="completed",
        require_completion_boundary=True,
    )
    failures: list[str] = []
    if valid_status.get("ok") is not True or valid_entry_failures:
        failures.append(f"合法 running 入口包被运行时边界误拒：{valid_entry_failures}")
    for case in cases:
        if case.get("rejected") is not True:
            failures.append(f"非法 active_run 未被运行时边界拒绝：{case.get('name')}")
    result = {
        "schema_id": "redcap-e2e-active-run-runtime-boundary-probe",
        "ok": not failures,
        "work_root": str(work_root),
        "valid_entry": valid_status,
        "valid_entry_failures": valid_entry_failures,
        "cases": cases,
        "failures": failures,
    }
    write_json(probe_root / "runtime-boundary-probe.json", result)
    return result


def run_long_task_e2e_integration_dry_run(work_root: pathlib.Path) -> dict[str, Any]:
    integration_root = work_root / "long-task-e2e-integration-dry-run"
    integration_root.mkdir(parents=True, exist_ok=True)
    action_evidence = integration_root / "integration-action-evidence.json"
    progress_evidence = integration_root / "integration-progress-evidence.json"
    completion_evidence = integration_root / "integration-completion-evidence.json"
    write_json(action_evidence, {
        "schema_id": "redcap-long-task-integration-action-evidence",
        "ok": True,
        "purpose": "长任务集成干跑入口证据，证明 start 命令真实创建 active_run。",
        "command": "runtime/bin/redcap long-task start",
    })
    start = run_command([
        str(REDCAP),
        "long-task",
        "start",
        "--task",
        "RedCap 长任务集成干跑：验证 start、record、complete 与 E2E 巡检发现完成边界的完整链路。",
        "--risk-level",
        "medium",
        "--run-dir",
        str(integration_root),
        "--consecutive-failures",
        "3",
        "--boundary-count",
        "2",
        "--action-evidence",
        str(action_evidence),
    ], timeout_seconds=60)
    start_payload = parse_leading_json(str(start.get("stdout") or "")) or {}
    active_run_raw = start_payload.get("active_run") if isinstance(start_payload, dict) else None
    active_run_path = pathlib.Path(str(active_run_raw)).resolve() if isinstance(active_run_raw, str) else integration_root / "redcap-long-task-active-run.json"
    write_json(progress_evidence, {
        "schema_id": "redcap-long-task-integration-progress-evidence",
        "ok": True,
        "purpose": "长任务集成干跑 record 证据，证明父目标有真实推进差量。",
        "active_run": str(active_run_path),
    })
    record = run_command([
        str(REDCAP),
        "long-task",
        "record",
        "--packet",
        str(active_run_path),
        "--status",
        "running",
        "--objective-delta",
        "集成干跑已完成 start 并进入 record，父目标出现可核验推进差量。",
        "--action-evidence",
        str(progress_evidence),
        "--blocker-signature",
        "none",
    ], timeout_seconds=60)
    write_json(completion_evidence, {
        "schema_id": "redcap-long-task-integration-completion-evidence",
        "ok": True,
        "purpose": "长任务集成干跑 complete 证据，包含 active_run、completion_boundary、E2E discover 所需语义。",
        "active_run": str(active_run_path),
        "expected_lifecycle_state": "completed",
    })
    complete = run_command([
        str(REDCAP),
        "long-task",
        "complete",
        "--packet",
        str(active_run_path),
        "--outcome",
        "completed",
        "--final-objective-delta",
        "集成干跑已完成 start、record、complete，等待 E2E 巡检发现 completion_boundary。",
        "--completion-evidence",
        str(completion_evidence),
        "--final-summary",
        "长任务集成干跑完成，active_run 应进入 completed 并写入 completion_boundary。",
        "--blocker-signature",
        "none",
    ], timeout_seconds=60)
    if active_run_path.exists():
        shutil.copy2(active_run_path, long_task_active_run_path(work_root))
    discovery = discover_e2e_long_task_active_run(
        work_root,
        expected_lifecycle_state="completed",
        require_completion_boundary=True,
    )
    commands = {
        "start": command_receipt(start),
        "record": command_receipt(record),
        "complete": command_receipt(complete),
    }
    failures: list[str] = []
    for name, receipt in commands.items():
        if receipt.get("ok") is not True:
            failures.append(f"{name} 命令失败")
    if discovery.get("ok") is not True:
        failures.append("E2E 巡检发现 active_run 完成边界失败")
    result = {
        "schema_id": "redcap-long-task-e2e-integration-dry-run",
        "ok": not failures,
        "work_root": str(work_root),
        "integration_root": str(integration_root),
        "commands": commands,
        "active_run": str(active_run_path),
        "e2e_active_run_packet": str(long_task_active_run_path(work_root)),
        "discovery": discovery,
        "failures": failures,
    }
    write_json(integration_root / "long-task-e2e-integration-dry-run.json", result)
    return result


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
    if "file://" in criterion or "本地文件协议" in criterion:
        return context.get("file_browser_ok") is True, "file-browser-inspection.json"
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
    file_browser_passed, file_browser_evidence = criterion_pass("file:// 本地文件协议打开检查", project, evidence, context)
    results.append({
        "id": "AC-file-browser",
        "criterion": "运行器使用真实浏览器通过 file:// 本地文件协议打开项目入口，确认无需本地服务也能呈现核心内容。",
        "passed": file_browser_passed,
        "evidence": file_browser_evidence,
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
        "disable_plugins": CODEX_INTERACTIVE_DISABLE_PLUGINS,
        "extra_disabled_features": CODEX_INTERACTIVE_EXTRA_DISABLED_FEATURES,
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


def write_self_referential_boundary(
    evidence: pathlib.Path,
    project: pathlib.Path,
    independent_observer_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    observer_process = independent_observer_payload.get("process") if isinstance(independent_observer_payload, dict) else None
    payload = {
        "schema_id": "redcap-e2e-self-referential-boundary",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "ok": True,
        "project": str(project),
        "validation_chain_scope": {
            "same_host": True,
            "same_redcap_package": True,
            "harness_coordinates_runner_and_observer": True,
            "observer_parent_is_harness": bool(isinstance(observer_process, dict) and observer_process.get("parent_is_harness") is True),
            "observer_parent_is_not_runner": bool(isinstance(observer_process, dict) and observer_process.get("parent_is_not_runner") is True),
            "harness_pid": observer_process.get("harness_pid") if isinstance(observer_process, dict) else None,
            "runner_pid": observer_process.get("runner_pid") if isinstance(observer_process, dict) else None,
            "observer_pid": observer_process.get("pid") if isinstance(observer_process, dict) else None,
        },
        "not_claimed": [
            "未声称跨机器验收",
            "未声称人工浏览器验收",
            "未声称生产级真实用户流量验收",
            "未声称所有 Loom 角色进程都是自然零退出；角色完成依据是产物内容、会话标识和运行器验证",
            "未声称最终棱镜复核是外部第三方认证；它仍属于本轮自举工程验收链的一部分",
            "未声称本轮结果可自动代表其他主机、模型版本、时序条件或真实生产负载",
            "未声称 RedCap 永久完整复活",
        ],
        "role_process_completion": {
            "role_processes_may_exit_non_zero_after_intentional_stop": True,
            "completion_basis": "artifact_content_session_identity_and_runner_validators",
            "not_claimed": "not natural terminal exit success for every role process",
            "reason": (
                "运行器在角色产物达到完成谓词后会停止交互式 Codex CLI 进程，"
                "因此原始进程退出码可能反映停止动作，而不是角色产物失败。"
            ),
            "required_mitigations": [
                "每个 Loom 角色必须保留 session_id",
                "角色产物必须通过内容结构校验",
                "运行器必须执行最终项目验证、负向契约探针、浏览器行为验证和最终棱镜复核",
            ],
        },
        "observer_boundary": {
            "observer_is_same_host_harness_sibling": True,
            "not_external_human_or_cross_machine_observer": True,
            "accepted_scope": "single-run engineering-trial observer",
        },
        "bootstrap_review_boundary": {
            "final_prism_review_is_part_of_same_bootstrapped_chain": True,
            "not_externally_certified": True,
            "accepted_scope": "single-run engineering-trial",
            "reason": "最终棱镜复核用于阻断明显缺陷和过度声明，不等同于独立第三方生产认证。",
        },
        "mitigations": [
            "Loom 角色通过独立 Codex CLI 会话运行",
            "Kimi 与 Claude Code 进行最终棱镜复核",
            "独立观察者由 harness 以 runner 兄弟进程启动",
            "运行器执行 HTTP 浏览器检查、file:// 浏览器检查、行为浏览器验证和独立子进程浏览器验证",
            "运行器执行正向验证、负向契约探针、角色玩家负向契约探针和写完成标记前最终验证",
        ],
        "completion_marker_disclosure": {
            "must_copy_this_boundary": True,
            "completion_scope": "single-e2e-run",
            "ready_for_engineering_use_means": "本轮 E2E 证据足以支持工程试用判断，不等同于跨机器、人工或永久生产验收。",
            "must_copy_role_process_completion": True,
            "must_copy_observer_boundary": True,
            "must_copy_bootstrap_review_boundary": True,
            "boundary_file": "self-referential-boundary.json",
            "final_marker_validation": "final-marker-validation.json",
            "file_browser_inspection": "file-browser-inspection.json",
        },
        "failures": [],
    }
    if not payload["validation_chain_scope"]["observer_parent_is_harness"]:
        payload["ok"] = False
        payload["failures"].append("self-referential-boundary 无法确认 observer_parent_is_harness")
    if not payload["validation_chain_scope"]["observer_parent_is_not_runner"]:
        payload["ok"] = False
        payload["failures"].append("self-referential-boundary 无法确认 observer_parent_is_not_runner")
    write_json(evidence / "self-referential-boundary.json", payload)
    return payload


def build_completion_marker_payload(
    evidence: pathlib.Path,
    project: pathlib.Path,
    bundle: dict[str, Any],
    final_prism: dict[str, Any],
    self_referential_boundary: dict[str, Any] | None = None,
    final_marker_validation: dict[str, Any] | None = None,
    file_browser_inspection: dict[str, Any] | None = None,
    convergence_diagnosis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_id": "redcap-e2e-completion-marker",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "project": str(project),
        "ready_for_engineering_use": True,
        "completion_scope": "single-e2e-run",
        "final_evidence_bundle_sha256": bundle.get("bundle_sha256"),
        "final_prism_strictest_verdict": final_prism.get("strictest_verdict"),
        "final_prism_review": "final-prism-review.json",
        "self_referential_boundary": "self-referential-boundary.json",
        "validation_chain_scope": self_referential_boundary.get("validation_chain_scope") if isinstance(self_referential_boundary, dict) else None,
        "not_claimed": self_referential_boundary.get("not_claimed") if isinstance(self_referential_boundary, dict) else [],
        "role_process_completion": self_referential_boundary.get("role_process_completion") if isinstance(self_referential_boundary, dict) else None,
        "observer_boundary": self_referential_boundary.get("observer_boundary") if isinstance(self_referential_boundary, dict) else None,
        "bootstrap_review_boundary": self_referential_boundary.get("bootstrap_review_boundary") if isinstance(self_referential_boundary, dict) else None,
        "ready_for_engineering_use_means": (
            "本轮 E2E 证据足以支持工程试用判断，不等同于跨机器、人工或永久生产验收。"
        ),
        "final_marker_validation": {
            "path": "final-marker-validation.json",
            "ok": final_marker_validation.get("ok") if isinstance(final_marker_validation, dict) else None,
            "stdout_sha256": final_marker_validation.get("stdout_sha256") if isinstance(final_marker_validation, dict) else None,
            "exit_code": final_marker_validation.get("exit_code") if isinstance(final_marker_validation, dict) else None,
        },
        "file_browser_inspection": {
            "path": "file-browser-inspection.json",
            "ok": file_browser_inspection.get("ok") if isinstance(file_browser_inspection, dict) else None,
            "screenshot": "file-browser-inspection.png",
        },
        "convergence_diagnosis": {
            "path": "convergence-diagnosis.json",
            "auto_rerun_allowed": convergence_diagnosis.get("auto_rerun_allowed") if isinstance(convergence_diagnosis, dict) else None,
            "strictest_verdict": convergence_diagnosis.get("strictest_verdict") if isinstance(convergence_diagnosis, dict) else None,
        },
        "browser_inspection": "browser-inspection.json",
        "behavioral_browser_verification": "behavioral-browser-verification.json",
        "iteration_verdict": "iteration-verdict.json",
        "no_open_failure_backlog": True,
    }


def completion_marker_boundary_validation(
    payload: dict[str, Any],
    self_referential_boundary: dict[str, Any] | None,
    *,
    preview: bool,
) -> dict[str, Any]:
    failures: list[str] = []
    boundary = self_referential_boundary if isinstance(self_referential_boundary, dict) else {}
    copied_fields = [
        "validation_chain_scope",
        "not_claimed",
        "role_process_completion",
        "observer_boundary",
        "bootstrap_review_boundary",
    ]
    for field in copied_fields:
        if payload.get(field) != boundary.get(field):
            failures.append(f"completion-marker {field} 未逐字复制 self-referential-boundary")
    if payload.get("completion_scope") != "single-e2e-run":
        failures.append("completion-marker completion_scope 必须是 single-e2e-run")
    meaning = str(payload.get("ready_for_engineering_use_means") or "")
    for required_text in ["工程试用", "不等同于跨机器", "人工", "永久生产验收"]:
        if required_text not in meaning:
            failures.append(f"completion-marker 工程试用边界说明缺少：{required_text}")
    return {
        "schema_id": "redcap-e2e-completion-marker-boundary-validation",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "preview": preview,
        "ok": not failures,
        "copied_fields": copied_fields,
        "boundary_file": "self-referential-boundary.json",
        "payload_sha256": sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True)),
        "boundary_sha256": sha256_text(json.dumps(boundary, ensure_ascii=False, sort_keys=True)) if boundary else None,
        "failures": failures,
    }


def write_completion_marker_preview(
    evidence: pathlib.Path,
    project: pathlib.Path,
    bundle: dict[str, Any],
    self_referential_boundary: dict[str, Any] | None = None,
    final_marker_validation: dict[str, Any] | None = None,
    file_browser_inspection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    preview_final_prism = {
        "strictest_verdict": "pending-final-prism-pass-required",
    }
    preview_convergence = {
        "auto_rerun_allowed": None,
        "strictest_verdict": "pending-final-prism-pass-required",
    }
    marker_payload = build_completion_marker_payload(
        evidence,
        project,
        bundle,
        preview_final_prism,
        self_referential_boundary=self_referential_boundary,
        final_marker_validation=final_marker_validation,
        file_browser_inspection=file_browser_inspection,
        convergence_diagnosis=preview_convergence,
    )
    preview_payload = {
        "schema_id": "redcap-e2e-completion-marker-preview",
        "producer": "e2e-runner",
        "created_at": iso_now(),
        "preview_only": True,
        "completion_marker_target": "completion-marker.json",
        "will_write_only_after_final_prism_pass": True,
        "payload_builder_shared_with_final_marker": True,
        "preview_final_prism_placeholder": "pending-final-prism-pass-required",
        "marker_payload": marker_payload,
    }
    validation = completion_marker_boundary_validation(marker_payload, self_referential_boundary, preview=True)
    preview_payload["boundary_validation"] = {
        "path": "completion-marker-preview-validation.json",
        "ok": validation.get("ok") is True,
        "payload_sha256": validation.get("payload_sha256"),
    }
    write_json(evidence / "completion-marker-preview.json", preview_payload)
    write_json(evidence / "completion-marker-preview-validation.json", validation)
    return preview_payload


def write_completion_marker(
    evidence: pathlib.Path,
    project: pathlib.Path,
    bundle: dict[str, Any],
    final_prism: dict[str, Any],
    self_referential_boundary: dict[str, Any] | None = None,
    final_marker_validation: dict[str, Any] | None = None,
    file_browser_inspection: dict[str, Any] | None = None,
    convergence_diagnosis: dict[str, Any] | None = None,
) -> None:
    payload = build_completion_marker_payload(
        evidence,
        project,
        bundle,
        final_prism,
        self_referential_boundary=self_referential_boundary,
        final_marker_validation=final_marker_validation,
        file_browser_inspection=file_browser_inspection,
        convergence_diagnosis=convergence_diagnosis,
    )
    validation = completion_marker_boundary_validation(payload, self_referential_boundary, preview=False)
    write_json(evidence / "completion-marker-boundary-validation.json", validation)
    if validation.get("ok") is not True:
        raise RuntimeError(f"completion marker boundary validation failed: {validation.get('failures')}")
    write_json(evidence / "completion-marker.json", payload)


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
    decisions = collect_self_purification_decisions(purification)
    candidates = purification.get("candidates")
    if not isinstance(candidates, list):
        candidates = []
    resolutions: list[dict[str, Any]] = []
    failures: list[str] = []
    if not candidates:
        failures.append("本轮 E2E 必须至少产生一个自我净化候选")
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
        "task": "Review whether this RedCap E2E run may write an engineering-trial completion marker with explicit scope boundaries.",
        "user_intent": "Norven wants RedCap to prove it can drive a real project through role-separated Loom workflow, hooks, evidence, self-purification, persona boundary, and failure feedback before claiming production usefulness.",
        "main_claim": "The E2E runner may write completion-marker.json only as a single-run engineering-trial evidence marker, because role, hook, test, evidence, boundary-disclosure, convergence-diagnosis, and failure-loop requirements passed after reviewer exit. This is not a claim that RedCap is permanently fully revived or externally production-certified.",
        "changed_reality": [
            "An external project was created outside the RedCap source workspace.",
            "Five Loom roles were launched as independent Codex CLI sessions with project-level Hook evidence; the runner accepts role completion by session_id, role artifact content, and downstream validators, and role PTYs may be intentionally stopped after their completion predicate is satisfied.",
            "The runner independently reran project validation and bundled evidence hashes before deciding completion.",
            "The runner reran the detected project validation command again as final-marker-validation.json before asking for completion-marker.json, recording exit code, stdout hash, and stderr hash.",
            "The runner performed mutation-based negative contract probes: it prefers non-first eligible records when available, temporarily writes bad signup and character-player data, requires the validation command to fail, restores the original data, and requires validation to pass again.",
            "The runner requires Loom roles to record upstream_challenges and reviewer to summarize role_opposition_matrix so the workflow has explicit role challenge evidence instead of a smooth same-context narrative.",
            "The runner opened the deliverable in a real headless browser, captured a screenshot, and checked visible rendered content before requesting completion.",
            "The runner also opened the same browser entrypoint through the file:// local file protocol and wrote file-browser-inspection.json plus file-browser-inspection.png before final provider review.",
            "The runner performed a separate behavioral browser verification with a real click interaction, captured behavioral-browser-verification.png immediately after the verified interaction, captured behavioral-relation-probe.png at the exact relation-probe state when character-player data exists, explored relation-bearing view controls, compared screenshot hashes, and checked that the relation rendered in the same DOM structural container rather than relying on flattened text distance.",
            "The runner also wrote independent-browser-verification-script.py, recorded its SHA-256, launched it as a separate Python process, and wrote independent-browser-verification.json before final provider review; browser-inspection, behavioral verification, independent browser verification, and independent observer use recorded browser_context metadata and are summarized by visual-independence-report.json.",
            "The outer E2E harness launched an independent observer as a sibling process of the runner-worker; the observer read the frozen final-evidence-bundle.json, independently recomputed its declared bundle_sha256, rechecked the file hash after a cooldown window, and wrote read-only sealed independent-observer.json.",
            "self-referential-boundary.json explicitly discloses that the runner, observer, browser checks, and final reviews are coordinated on the same host and same RedCap package, and states what is not claimed.",
            "self-referential-boundary.json also discloses that role process exit codes may reflect intentional PTY stop after artifact completion, that independent observer is a same-host harness sibling rather than a human or cross-machine observer, and that final Prism review is part of the same bootstrapped engineering-trial chain.",
            "pre-final-readiness.json separates evidence_checked from pending_final_evidence, so completion-marker.json, final-prism-review.json, and the final iteration-verdict.json are not claimed as pre-final checked evidence.",
            "completion-marker-preview.json previews the exact boundary-copying payload shape that will become completion-marker.json only if final Prism passes; completion-marker-preview-validation.json proves it copies self-referential-boundary.json disclosures before providers review.",
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
                "kind": "final-marker-validation-full",
                "reference": "final-marker-validation.json",
                "summary": supplemental_evidence.get("final_marker_validation"),
            },
            {
                "kind": "file-browser-inspection-full",
                "reference": "file-browser-inspection.json",
                "summary": supplemental_evidence.get("file_browser_inspection"),
            },
            {
                "kind": "self-referential-boundary-full",
                "reference": "self-referential-boundary.json",
                "summary": supplemental_evidence.get("self_referential_boundary"),
            },
            {
                "kind": "pre-final-readiness",
                "reference": "pre-final-readiness.json",
                "summary": supplemental_evidence.get("pre_final_readiness"),
            },
            {
                "kind": "completion-marker-preview",
                "reference": "completion-marker-preview.json",
                "summary": supplemental_evidence.get("completion_marker_preview"),
            },
            {
                "kind": "completion-marker-preview-validation",
                "reference": "completion-marker-preview-validation.json",
                "summary": supplemental_evidence.get("completion_marker_preview_validation"),
            },
            {
                "kind": "failure-backlog-full",
                "reference": "failure-backlog.json",
                "summary": supplemental_evidence.get("failure_backlog"),
            },
            {
                "kind": "independent-observer-full",
                "reference": "independent-observer.json",
                "summary": supplemental_evidence.get("independent_observer"),
            },
            {
                "kind": "package-prism-check-full",
                "reference": "package-prism-check.json",
                "summary": supplemental_evidence.get("package_prism_check"),
            },
            {
                "kind": "convergence-diagnosis-policy",
                "reference": "convergence-diagnosis.json",
                "summary": supplemental_evidence.get("convergence_diagnosis_policy"),
            }
        ],
        "review_mode": "completion_review",
        "risk_level": "high",
        "requested_providers": ["kimi", "claude-code"],
        "known_constraints": [
            "Reviewer must not self-certify completion.",
            "Open failure-backlog items block completion.",
            "Completion marker scope is only this E2E run, not permanent RedCap full revival.",
            "Completion marker is an engineering-trial evidence marker with explicit validation_chain_scope and not_claimed boundaries; do not evaluate it as a cross-machine, human, or permanent production certification.",
            "Role process completion must be evaluated by role session_id continuity, structured artifacts, runner validators, negative probes, browser checks, and final review; a non-zero raw role process exit after intentional stop is not by itself a role artifact failure.",
            "The independent observer is intentionally a same-host harness sibling that validates frozen evidence read-only; it is not an external human, cross-machine, or production traffic observer.",
            "The final Prism review is itself part of this bootstrapped RedCap engineering-trial chain; if this is the only remaining concern, it should be treated as a disclosed scope boundary rather than a blocker to a single-run engineering-trial completion marker.",
            "iteration-verdict.json is intentionally not finalized before this provider review; pre-final-readiness.json is generated after final-evidence-bundle.json and is only an objective pre-final summary, not a completion claim.",
            "If this provider review passes, the runner must regenerate iteration-verdict.json with final_prism_pending=false before writing completion-marker.json.",
            "pre-final-readiness.json must not list completion-marker.json, final-prism-review.json, or iteration-verdict.json in evidence_checked; those belong in pending_final_evidence until this review passes.",
            "completion-marker-preview.json is not a completion claim; it is a pre-final payload preview. Providers should evaluate whether its marker_payload copies boundary disclosures, while completion-marker.json remains forbidden until final Prism passes.",
            "Loom role session_id is the role isolation evidence; turn_id may reflect host hook grouping and is not used as the role identity boundary.",
            "independent-observer.json must verify parent_is_harness=true, parent_is_not_runner=true, observer_seal hash match, read-only file mode, deliverable hashes, browser observation, declared bundle hash match, and cooldown file hash stability.",
            "final-evidence-bundle.json is a frozen review bundle observed by the independent observer; post-bundle observer files, visual-independence-report.json, completion-marker-preview.json, completion-marker-preview-validation.json, final-prism-review.json, failure-backlog.json, iteration-verdict.json, completion-marker-boundary-validation.json, and completion-marker.json are supplied separately or generated later to avoid self-referential bundle hashes.",
            "visual-independence-report.json must include every PNG screenshot in the evidence directory, including file-browser-inspection.png, behavioral-relation-probe.png, and behavioral-relation-container-crop.png. Duplicate hashes are forbidden unless the report explicitly records an allowed duplicate explanation; relation evidence must not rely on duplicate hashes, because behavioral-relation-container-crop.png must be a real crop of the verified relation container. HTTP browser-inspection.png and file-browser-inspection.png must be visually distinguishable through independent viewport or state.",
            "completion-marker.json is forbidden before final provider review; if this review passes, the runner must copy self-referential-boundary.json disclosures into completion-marker.json and cite final-marker-validation.json and file-browser-inspection.json.",
            "If this provider review passes, completion-marker.json must copy role_process_completion, observer_boundary, and bootstrap_review_boundary from self-referential-boundary.json.",
            "If the remaining concern is that any same-host automated E2E can never be externally production-certified, treat that as compatible with an engineering-trial marker only when self-referential-boundary.json and completion-marker.json explicitly disclose that limitation.",
        ],
        "role_execution_profile": {
            "model": CODEX_ROLE_MODEL,
            "reasoning_effort": CODEX_ROLE_REASONING_EFFORT,
            "disable_plugins": CODEX_INTERACTIVE_DISABLE_PLUGINS,
            "extra_disabled_features": CODEX_INTERACTIVE_EXTRA_DISABLED_FEATURES,
            "preserve_user_config": CODEX_ROLE_PRESERVE_USER_CONFIG,
            "interactive_gate_markers": CODEX_ROLE_INTERACTIVE_GATE_MARKERS,
            "quality_controls": [
                "structured role handoff files",
                "runner-owned final validation",
                "final-marker-validation.json",
                "browser-inspection.json",
                "file-browser-inspection.json",
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
    file_browser_inspection = run_file_browser_inspection(project, evidence)
    write_json(evidence / "file-browser-inspection.json", file_browser_inspection)
    behavioral_verification = run_behavioral_browser_verification(project, evidence)
    write_json(evidence / "behavioral-browser-verification.json", behavioral_verification)
    independent_browser = run_independent_browser_verification_process(project, evidence)
    write_json(evidence / "independent-browser-verification.json", independent_browser)
    final_marker_validation = run_final_marker_validation(project)
    write_json(evidence / "final-marker-validation.json", final_marker_validation)
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
    if file_browser_inspection.get("ok") is not True:
        failures.append("运行器 file:// 浏览器检查未通过")
    if behavioral_verification.get("ok") is not True:
        failures.append("运行器行为级浏览器验证未通过")
    if independent_browser.get("ok") is not True:
        failures.append("独立子进程浏览器验证未通过")
    if final_marker_validation.get("ok") is not True:
        failures.append("写完成标记前最终项目验证未通过")
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
        "file_browser_ok": file_browser_inspection.get("ok") is True,
        "behavior_ok": behavioral_verification.get("ok") is True,
        "independent_browser_ok": independent_browser.get("ok") is True,
        "final_marker_validation_ok": final_marker_validation.get("ok") is True,
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
    self_referential_boundary = write_self_referential_boundary(
        evidence,
        project,
        independent_observer_payload if isinstance(independent_observer_payload, dict) else None,
    )
    if self_referential_boundary.get("ok") is not True:
        failures.append(f"自引用边界披露未通过：{self_referential_boundary.get('failures')}")
    visual_independence = build_visual_independence_report(evidence)
    write_json(evidence / "visual-independence-report.json", visual_independence)
    if visual_independence.get("ok") is not True:
        failures.append(f"视觉三角独立性验证未通过：{visual_independence.get('failures')}")
    pre_final_context["independent_observer_ok"] = independent_observer_verification.get("ok") is True
    pre_final_readiness = write_pre_final_readiness(project, evidence, failures, pre_final_context)
    completion_marker_preview = write_completion_marker_preview(
        evidence,
        project,
        bundle,
        self_referential_boundary=self_referential_boundary,
        final_marker_validation=final_marker_validation,
        file_browser_inspection=file_browser_inspection,
    )
    completion_marker_preview_validation = load_optional_json(evidence / "completion-marker-preview-validation.json")
    if not isinstance(completion_marker_preview_validation, dict) or completion_marker_preview_validation.get("ok") is not True:
        failures.append(
            f"completion-marker 预览边界校验未通过："
            f"{completion_marker_preview_validation.get('failures') if isinstance(completion_marker_preview_validation, dict) else 'missing validation'}"
        )
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
            "completion_marker_preview": completion_marker_preview,
            "completion_marker_preview_validation": completion_marker_preview_validation,
            "final_marker_validation": load_optional_json(evidence / "final-marker-validation.json"),
            "file_browser_inspection": load_optional_json(evidence / "file-browser-inspection.json"),
            "self_referential_boundary": load_optional_json(evidence / "self-referential-boundary.json"),
            "failure_backlog": load_optional_json(evidence / "failure-backlog.json"),
            "independent_observer": load_optional_json(evidence / "independent-observer.json"),
            "package_prism_check": load_optional_json(evidence / "package-prism-check.json"),
            "convergence_diagnosis_policy": {
                "will_write": "convergence-diagnosis.json",
                "rule": "如果最终棱镜未通过，运行器必须归类 loop_class，并在结构性缺口存在时设置 auto_rerun_allowed=false，禁止继续无意义重跑。",
            },
        })
        write_runner_prism_assistance(evidence, final_prism)
        convergence = classify_final_prism_convergence(final_prism, failures)
        write_json(evidence / "convergence-diagnosis.json", convergence)
        if final_prism.get("ok") is not True:
            failures.append(f"最终棱镜复核未通过：{final_prism.get('failures')}")
            if convergence.get("auto_rerun_allowed") is not True:
                failures.append("E2E 收敛诊断禁止自动盲目重跑；必须先处理 convergence-diagnosis.json 中的结构性缺口")
    if failures:
        if "final_prism" in locals():
            if not (evidence / "convergence-diagnosis.json").exists():
                convergence = classify_final_prism_convergence(final_prism, failures)
                write_json(evidence / "convergence-diagnosis.json", convergence)
            write_runner_prism_assistance(evidence, final_prism)
        write_failure_backlog_with_runner_items(evidence, failures)
        write_final_iteration_verdict(project, evidence, False, failures, {
            **pre_final_context,
            "final_prism_ok": final_prism.get("ok") is True if "final_prism" in locals() else False,
        })
    else:
        convergence = classify_final_prism_convergence(final_prism, failures)
        write_json(evidence / "convergence-diagnosis.json", convergence)
        write_final_iteration_verdict(project, evidence, True, [], {
            **pre_final_context,
            "final_prism_ok": final_prism.get("ok") is True,
        })
        write_completion_marker(
            evidence,
            project,
            bundle,
            final_prism,
            self_referential_boundary=self_referential_boundary,
            final_marker_validation=final_marker_validation,
            file_browser_inspection=file_browser_inspection,
            convergence_diagnosis=convergence,
        )
    return {
        "schema_id": "redcap-e2e-finalization-result",
        "ok": not failures,
        "runner_tests_ok": runner_tests.get("ok") is True,
        "final_marker_validation_ok": final_marker_validation.get("ok") is True,
        "file_browser_ok": file_browser_inspection.get("ok") is True,
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
            seen_sessions: set[str] = set()
            for role in roles:
                if not isinstance(role, dict):
                    failures.append("loom-role-session-manifest.roles 条目必须是对象")
                    continue
                role_name = str(role.get("role") or "")
                if not role_name:
                    failures.append("Loom 角色条目缺少 role")
                    continue
                session_id = str(role.get("session_id") or "")
                if not session_id:
                    failures.append(f"Loom 角色缺少 session_id：{role_name}")
                elif not re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", session_id):
                    failures.append(f"Loom 角色 session_id 格式非法：{role_name}")
                elif session_id in seen_sessions:
                    failures.append(f"Loom 角色 session_id 不能复用：{role_name}")
                else:
                    seen_sessions.add(session_id)
                if role.get("context_state") == "degraded" and not role.get("alarm"):
                    failures.append(f"Loom 角色上下文降级但缺少 alarm：{role_name}")
            for required_role in LOOM_EXECUTION_ROLES:
                for rel in [
                    f"role-artifacts/{required_role}.json",
                    f"role-runs/{required_role}.json",
                    f"role-prompts/{required_role}.md",
                    f"role-messages/{required_role}.txt",
                ]:
                    path = evidence / rel
                    if not path.exists() or path.stat().st_size <= 0:
                        failures.append(f"Loom 角色证据必须存在且非空：{rel}")
                raw_stdout = evidence / "role-raw" / f"{required_role}.stdout.txt"
                raw_stderr = evidence / "role-raw" / f"{required_role}.stderr.txt"
                if not raw_stdout.exists() and not raw_stderr.exists():
                    failures.append(f"Loom 角色缺少 role-raw 原始输出证据：{required_role}")
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
            else:
                for index, review in enumerate(reviews, start=1):
                    if isinstance(review, dict) and str(review.get("verdict") or "").casefold() == "block":
                        failures.append(f"prism-assisted-review.reviews[{index}] 不能是 block")
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
    if purification is not None:
        candidates = purification.get("candidates")
        decisions = collect_self_purification_decisions(purification)
        if not isinstance(candidates, list) or not candidates:
            failures.append("self-purification-candidates 必须至少记录一个候选")
        if not decisions:
            failures.append("self-purification-candidates 必须至少记录一个处理决定")
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
    final_marker_validation = load_optional_json(evidence / "final-marker-validation.json")
    if final_marker_validation is not None:
        if final_marker_validation.get("ok") is not True:
            failures.append("final-marker-validation 必须证明写完成标记前最终项目验证通过")
        if not final_marker_validation.get("stdout_sha256"):
            failures.append("final-marker-validation 必须记录 stdout_sha256")
    browser_inspection = load_optional_json(evidence / "browser-inspection.json")
    if browser_inspection is not None and browser_inspection.get("ok") is not True:
        failures.append("browser-inspection 必须证明运行器独立浏览器检查通过")
    file_browser_inspection = load_optional_json(evidence / "file-browser-inspection.json")
    if file_browser_inspection is not None:
        if file_browser_inspection.get("ok") is not True:
            failures.append("file-browser-inspection 必须证明项目入口可通过 file:// 本地文件协议打开")
        if file_browser_inspection.get("launch_mode") != "local-file-protocol":
            failures.append("file-browser-inspection.launch_mode 必须是 local-file-protocol")
        if not file_browser_inspection.get("screenshot"):
            failures.append("file-browser-inspection 必须记录截图证据")
        file_context = file_browser_inspection.get("browser_context")
        if not isinstance(file_context, dict) or file_context.get("viewport") != FILE_BROWSER_INSPECTION_VIEWPORT:
            failures.append("file-browser-inspection 必须使用独立视口，避免与 HTTP 浏览器截图像素完全相同")
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
        relation_probe = behavioral_verification.get("relation_probe")
        if isinstance(relation_probe, dict):
            relation_record = behavioral_verification.get("relation_probe_screenshot_record")
            if not isinstance(relation_record, dict) or relation_record.get("exists") is not True or not relation_record.get("sha256"):
                failures.append("behavioral-browser-verification 有角色玩家关系探针时，必须记录 behavioral-relation-probe.png 截图哈希")
            relation_check = next(
                (
                    item for item in behavioral_verification.get("checks", [])
                    if isinstance(item, dict) and item.get("name") == "character_player_relation_visible"
                ),
                None,
            )
            relation_evidence = relation_check.get("evidence") if isinstance(relation_check, dict) else None
            if not isinstance(relation_evidence, dict) or not isinstance(relation_evidence.get("relation_event_control"), dict):
                failures.append("behavioral-browser-verification 关系探针必须记录 relation_event_control，说明验证的是哪个交互状态")
            if not isinstance(relation_evidence, dict) or not isinstance(relation_evidence.get("relation_record_control"), dict):
                failures.append("behavioral-browser-verification 关系探针必须记录 relation_record_control，说明嵌套场次或记录状态")
            if not isinstance(relation_evidence, dict) or not isinstance(relation_evidence.get("relation_view_control"), dict):
                failures.append("behavioral-browser-verification 关系探针必须记录 relation_view_control，说明是否探索了角色、玩家或关系视图入口")
            relation_state = relation_evidence.get("relation_state_matched") if isinstance(relation_evidence, dict) else None
            if not isinstance(relation_state, dict) or relation_state.get("event_state_matched") is not True or relation_state.get("record_state_matched") is not True:
                failures.append("behavioral-browser-verification 关系探针必须证明外层活动和内层记录状态都已匹配")
            if isinstance(relation_evidence, dict) and relation_evidence.get("event_title") and relation_evidence.get("relation_event_title_visible") is not True:
                failures.append("behavioral-browser-verification 关系探针必须证明被验证活动标题在关系探针页面状态中可见")
            if isinstance(relation_evidence, dict) and relation_evidence.get("record_title") and relation_evidence.get("relation_record_title_visible") is not True:
                failures.append("behavioral-browser-verification 关系探针必须证明被验证嵌套记录标题在关系探针页面状态中可见")
    visual_report = load_optional_json(evidence / "visual-independence-report.json")
    if visual_report is not None:
        if visual_report.get("ok") is not True:
            failures.append(f"visual-independence-report 必须通过：{visual_report.get('failures')}")
        unexpected_duplicates = visual_report.get("unexpected_duplicate_screenshot_sha256")
        if unexpected_duplicates:
            failures.append(f"visual-independence-report 存在未解释的重复截图哈希：{unexpected_duplicates}")
        if visual_report.get("unreported_png_files"):
            failures.append(f"visual-independence-report 存在未纳入报告的截图文件：{visual_report.get('unreported_png_files')}")
    independent_browser = load_optional_json(evidence / "independent-browser-verification.json")
    if independent_browser is not None:
        if independent_browser.get("ok") is not True:
            failures.append("independent-browser-verification 必须通过")
        script = independent_browser.get("script")
        if not isinstance(script, dict) or script.get("path") != "independent-browser-verification-script.py" or not script.get("sha256"):
            failures.append("independent-browser-verification 必须记录独立脚本文件路径和 sha256")
        elif not (evidence / "independent-browser-verification-script.py").exists():
            failures.append("independent-browser-verification-script.py 必须真实存在于证据目录")
    independent_observer = load_optional_json(evidence / "independent-observer.json")
    if independent_observer is not None:
        verification = verify_independent_observer_output(evidence / "independent-observer.json")
        if verification.get("ok") is not True:
            failures.append(f"independent-observer 必须证明 harness 兄弟进程外部观察通过：{verification.get('failures')}")
    self_referential_boundary = load_optional_json(evidence / "self-referential-boundary.json")
    if self_referential_boundary is not None:
        if self_referential_boundary.get("ok") is not True:
            failures.append(f"self-referential-boundary 必须通过：{self_referential_boundary.get('failures')}")
        scope = self_referential_boundary.get("validation_chain_scope")
        if not isinstance(scope, dict) or scope.get("same_host") is not True or scope.get("same_redcap_package") is not True:
            failures.append("self-referential-boundary 必须明示 same_host 和 same_redcap_package")
        disclosure = self_referential_boundary.get("completion_marker_disclosure")
        if not isinstance(disclosure, dict) or disclosure.get("must_copy_this_boundary") is not True:
            failures.append("self-referential-boundary 必须要求 completion-marker 复制边界披露")
    completion_marker_preview = load_optional_json(evidence / "completion-marker-preview.json")
    completion_marker_preview_validation = load_optional_json(evidence / "completion-marker-preview-validation.json")
    if completion_marker_preview is not None:
        if completion_marker_preview.get("preview_only") is not True:
            failures.append("completion-marker-preview 必须声明 preview_only=true")
        if completion_marker_preview.get("will_write_only_after_final_prism_pass") is not True:
            failures.append("completion-marker-preview 必须声明只有最终棱镜通过后才写正式 completion-marker")
        marker_payload = completion_marker_preview.get("marker_payload")
        if not isinstance(marker_payload, dict):
            failures.append("completion-marker-preview 必须包含 marker_payload")
    if completion_marker_preview_validation is not None and completion_marker_preview_validation.get("ok") is not True:
        failures.append(f"completion-marker-preview-validation 必须通过：{completion_marker_preview_validation.get('failures')}")
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
                "convergence-diagnosis.json",
                "final-prism-review.json",
                "failure-backlog.json",
                "iteration-verdict.json",
                "completion-marker-boundary-validation.json",
                "completion-marker.json",
                "completion-marker-preview.json",
                "completion-marker-preview-validation.json",
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
        if not isinstance(completion_marker.get("validation_chain_scope"), dict):
            failures.append("completion-marker 必须包含 validation_chain_scope 边界披露")
        if not isinstance(completion_marker.get("not_claimed"), list) or not completion_marker.get("not_claimed"):
            failures.append("completion-marker 必须包含 not_claimed 边界声明")
        marker_validation = completion_marker.get("final_marker_validation")
        if not isinstance(marker_validation, dict) or marker_validation.get("ok") is not True:
            failures.append("completion-marker 必须引用通过的 final-marker-validation")
        file_browser = completion_marker.get("file_browser_inspection")
        if not isinstance(file_browser, dict) or file_browser.get("ok") is not True:
            failures.append("completion-marker 必须引用通过的 file-browser-inspection")
        if self_referential_boundary is not None:
            marker_boundary_validation = completion_marker_boundary_validation(
                completion_marker,
                self_referential_boundary,
                preview=False,
            )
            if marker_boundary_validation.get("ok") is not True:
                failures.append(f"completion-marker 必须逐字复制边界披露：{marker_boundary_validation.get('failures')}")
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
    user_codex_before = user_codex_home_state()
    failures = ensure_external_path(work_root)
    if failures:
        return attach_source_workspace_guard({"ok": False, "failures": failures}, guard_before)
    work_root.mkdir(parents=True, exist_ok=True)
    project = (work_root / "redcap-e2e-carrier-probe").resolve()
    if project.exists():
        shutil.rmtree(project)
    (project / ".codex").mkdir(parents=True)
    (project / ".redcap" / "evidence" / "e2e").mkdir(parents=True)
    (project / ".codex" / "config.toml").write_text("[features]\nhooks = true\n", encoding="utf-8")
    git_result = ensure_project_git_repo(project, project / ".redcap" / "evidence" / "e2e")
    if git_result.get("ok") is not True:
        return attach_source_workspace_guard({
            "schema_id": "redcap-ai-e2e-carrier-probe",
            "ok": False,
            "project": str(project),
            "events_path": str(project / ".redcap" / "evidence" / "e2e" / "carrier-hook-events.jsonl"),
            "git": git_result,
            "failures": ["承载探针 Git 基线初始化失败"],
        }, guard_before)
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
            "command": f"/usr/bin/python3 \"{hook_script}\" --event {event}",
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
    trust_result = ensure_codex_project_trusted(project, project / ".redcap" / "evidence" / "e2e")
    mcp_contract = codex_mcp_isolation_contract()
    child_env = codex_child_env(trust_result.get("isolated_home") if isinstance(trust_result.get("isolated_home"), dict) else {})
    if trust_result.get("ok") is not True or mcp_contract.get("ok") is not True:
        probe = {
            "schema_id": "redcap-ai-e2e-carrier-probe",
            "ok": False,
            "project": str(project),
            "events_path": str(events_path),
            "codex_project_trust": trust_result,
            "codex_mcp_isolation_contract": mcp_contract,
            "user_codex_home_guard": compare_user_codex_home_state(user_codex_before),
            "failures": [
                *([] if trust_result.get("ok") is True else ["Codex CLI 项目信任准备失败"]),
                *[str(item) for item in mcp_contract.get("failures", [])],
            ],
        }
        write_json(project / ".redcap" / "evidence" / "e2e" / "carrier-probe.json", probe)
        return attach_source_workspace_guard(probe, guard_before)
    attempts: list[dict[str, Any]] = []
    result: dict[str, Any] = {}
    events: list[str] = []
    missing: list[str] = list(REQUIRED_HOOK_EVENTS)
    last_message = project / ".redcap" / "evidence" / "e2e" / "carrier-last-message.txt"
    marker_path = project / "carrier-shell-marker.txt"
    marker_text: str | None = None
    marker_sha256: str | None = None
    marker_removed = False
    marker_cleanup_error: str | None = None

    def cleanup_marker() -> None:
        nonlocal marker_removed, marker_cleanup_error
        if not marker_path.exists():
            return
        if TEST_INJECT_CARRIER_MARKER_CLEANUP_FAILURE:
            marker_cleanup_error = "injected marker cleanup failure"
            return
        try:
            marker_path.unlink()
            marker_removed = True
        except OSError as exc:
            marker_cleanup_error = str(exc)

    try:
        for attempt in range(1, max(1, CARRIER_PROBE_MAX_ATTEMPTS) + 1):
            if events_path.exists():
                events_path.unlink()
            cleanup_marker()
            last_message = project / ".redcap" / "evidence" / "e2e" / f"carrier-last-message.attempt-{attempt}.txt"
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
            argv.append(
                "请必须使用 shell 工具运行一个本地命令，在当前目录创建 carrier-shell-marker.txt，"
                "内容写 carrier-shell-ok；然后最终只回答三个英文词，并用英文连字符连接：carrier、probe、ok。不要只口头说明。"
            )
            result = run_command_pty(
                argv,
                cwd=project,
                timeout_seconds=timeout_seconds,
                completion_markers=["carrier-probe-ok"],
                completion_files=[marker_path],
                settle_seconds=10.0,
                env_overrides=child_env,
            )
            if str(result.get("stdout") or "").strip():
                last_message.write_text(str(result.get("stdout") or "")[-12000:], encoding="utf-8")
            events = parse_hook_events(events_path)
            missing = [event for event in REQUIRED_HOOK_EVENTS if event not in events]
            marker_exists = marker_path.exists() and marker_path.is_file()
            marker_text = marker_path.read_text(encoding="utf-8", errors="replace") if marker_exists else None
            marker_sha256 = sha256_file(marker_path) if marker_exists else None
            attempt_decision = carrier_probe_attempt_decision(
                command_ok=bool(result["ok"]),
                marker_exists=marker_exists,
                marker_text=marker_text,
                missing_events=missing,
            )
            attempts.append({
                "attempt": attempt,
                "ok": attempt_decision["ok"],
                "command": command_receipt(result),
                "events": events,
                "missing_events": missing,
                "failure_reasons": attempt_decision["failure_reasons"],
                "marker_path": str(marker_path),
                "marker_exists": marker_exists,
                "marker_text": marker_text,
                "marker_sha256": marker_sha256,
                "last_message": str(last_message),
            })
            if attempt_decision["ok"]:
                break
    finally:
        cleanup_marker()
    final_decision = carrier_probe_final_decision(
        command_ok=bool(result.get("ok")),
        marker_exists=marker_text is not None,
        marker_text=marker_text,
        missing_events=missing,
        marker_cleanup_error=marker_cleanup_error,
    )
    probe = {
        "schema_id": "redcap-ai-e2e-carrier-probe",
        "ok": final_decision["ok"],
        "project": str(project),
        "events_path": str(events_path),
        "events": events,
        "missing_events": missing,
        "command": command_receipt(result),
        "attempts": attempts,
        "max_attempts": max(1, CARRIER_PROBE_MAX_ATTEMPTS),
        "codex_model": CODEX_ROLE_MODEL,
        "codex_reasoning_effort": CODEX_ROLE_REASONING_EFFORT,
        "codex_plugins_disabled": CODEX_INTERACTIVE_DISABLE_PLUGINS,
        "codex_extra_disabled_features": CODEX_INTERACTIVE_EXTRA_DISABLED_FEATURES,
        "codex_disabled_mcp_servers": unique_preserve_order(CODEX_DISABLED_MCP_SERVERS),
        "codex_user_config_preserved": CODEX_ROLE_PRESERVE_USER_CONFIG,
        "marker_path": str(marker_path),
        "marker_text": marker_text,
        "marker_sha256": marker_sha256,
        "marker_removed_after_probe": marker_removed,
        "marker_cleanup_error": marker_cleanup_error,
        "git": git_result,
        "codex_project_trust": trust_result,
        "codex_mcp_isolation_contract": mcp_contract,
        "user_codex_home_guard": compare_user_codex_home_state(user_codex_before),
        "last_message": str(last_message),
        "failures": [],
    }
    if trust_result.get("ok") is not True:
        probe["failures"].append("Codex CLI 项目信任登记失败，项目级 hook 无法加载")
        probe["ok"] = False
    if not result["ok"]:
        probe["failures"].append("Codex CLI 承载探针命令失败")
    if not final_decision["marker_ok"]:
        probe["failures"].append("Codex CLI 承载探针没有通过 shell 创建正确的标记文件")
    if missing:
        probe["failures"].append(f"Codex CLI 没有触发全部项目级 hook：{missing}")
    if marker_cleanup_error:
        probe["failures"].append(f"Codex CLI 承载探针 marker 清理失败：{marker_cleanup_error}")
    user_guard = probe.get("user_codex_home_guard") if isinstance(probe.get("user_codex_home_guard"), dict) else {}
    if user_guard.get("ok") is not True:
        probe["ok"] = False
        probe["failures"].append(f"用户真实 Codex Home 保护失败：{user_guard.get('failures')}")
    probe = attach_source_workspace_guard(probe, guard_before)
    write_json(project / ".redcap" / "evidence" / "e2e" / "carrier-probe.json", probe)
    return probe


def run_layered_preflight(work_root: pathlib.Path | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    commands = [
        {
            "id": "loom-runtime-self-check",
            "purpose": "确认 Loom 角色会话运行机可校验项目级角色身份、会话接续和上下文完整性。",
            "argv": [str(REDCAP), "loom-runtime", "self-check"],
        },
        {
            "id": "self-purification-self-check",
            "purpose": "确认自我净化闭环具备任务后候选识别、晋升判断、公共/私有边界和证据输出能力。",
            "argv": [str(REDCAP), "self-purification", "self-check"],
        },
        {
            "id": "knowledge-search-self-purification",
            "purpose": "确认 E2E 前能主动召回自我净化相关沉淀，避免能力尘封。",
            "argv": [str(REDCAP), "knowledge-gateway", "search", "self-purification", "--require-hit"],
        },
        {
            "id": "knowledge-search-loom",
            "purpose": "确认 E2E 前能主动召回 Loom 角色工作流相关沉淀。",
            "argv": [str(REDCAP), "knowledge-gateway", "search", "loom", "--require-hit"],
        },
        {
            "id": "project-install-release-check",
            "purpose": "确认发布包能解压到外部项目并完成项目级 .redcap 初始化。",
            "argv": [str(REDCAP), "project-install", "release-check"],
        },
    ]
    for spec in commands:
        injected_failure = (
            os.environ.get(TEST_MODE_ENV) == "1"
            and os.environ.get(TEST_INJECT_LAYERED_PREFLIGHT_FAILURE_ENV) == spec["id"]
        )
        if injected_failure:
            result = {
                "argv": spec["argv"],
                "cwd": str(REPO_ROOT),
                "exit_code": 97,
                "ok": False,
                "timed_out": False,
                "timeout_seconds": 240,
                "started_at": iso_now(),
                "finished_at": iso_now(),
                "stdout": "",
                "stderr": f"injected layered preflight failure: {spec['id']}",
            }
        else:
            result = run_command(spec["argv"], timeout_seconds=240)
        checks.append({
            "id": spec["id"],
            "purpose": spec["purpose"],
            "ok": result.get("ok") is True,
            "test_injection": injected_failure,
            "command": command_receipt(result),
        })
    failures = [
        f"{check['id']} 未通过"
        for check in checks
        if check.get("ok") is not True
    ]
    result = {
        "schema_id": "redcap-ai-e2e-layered-preflight",
        "ok": not failures,
        "checked_at": iso_now(),
        "must_run_before": "Codex CLI carrier-probe、REDCAP_E2E_WORKER worker 启动、任一 Loom 角色执行之前。",
        "blocked_before_project_run": bool(failures),
        "auto_rerun_allowed": False if failures else True,
        "checks": checks,
        "failures": failures,
    }
    if work_root is not None:
        work_root.mkdir(parents=True, exist_ok=True)
        write_json(work_root / "redcap-e2e-layered-preflight.json", result)
    return result


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
    patrol_guard = patrol_iteration_guard(work_root)
    next_iteration = int(patrol_guard.get("next_iteration") or 1)
    if timeout_seconds > E2E_SINGLE_RUN_TIMEOUT_HARD_CAP_SECONDS:
        active_run = write_e2e_long_task_active_run(
            work_root,
            direction=direction,
            iteration=next_iteration,
            status="blocked",
            action_evidence=["runtime/bin/redcap complete-revival-e2e run blocked by timeout hard cap"],
            objective_delta="单轮 E2E 超时预算超过硬上限，入口在项目执行前阻断，避免把不可控长跑误判为推进。",
            blocker_signature=f"timeout-hard-cap:{timeout_seconds}>{E2E_SINGLE_RUN_TIMEOUT_HARD_CAP_SECONDS}",
            auto_rerun_allowed=False,
            failures=[
                f"单轮 E2E timeout-seconds={timeout_seconds} 超过硬上限 {E2E_SINGLE_RUN_TIMEOUT_HARD_CAP_SECONDS} 秒"
            ],
        )
        return {
            "schema_id": "redcap-ai-e2e-run-result",
            "ok": False,
            "ready_for_engineering_use": False,
            "blocked_before_project_run": True,
            "long_task_active_run": active_run,
            "failures": [
                f"单轮 E2E timeout-seconds={timeout_seconds} 超过硬上限 {E2E_SINGLE_RUN_TIMEOUT_HARD_CAP_SECONDS} 秒"
            ],
        }
    write_json(work_root / "redcap-e2e-patrol-iteration-guard.json", patrol_guard)
    if patrol_guard.get("blocked") is True:
        active_run = write_e2e_long_task_active_run(
            work_root,
            direction=direction,
            iteration=next_iteration,
            status="blocked",
            action_evidence=["runtime/bin/redcap complete-revival-e2e run blocked by patrol iteration guard"],
            objective_delta="E2E 巡检轮次达到硬上限，入口在项目执行前阻断并要求 Cap 仲裁。",
            blocker_signature=f"patrol-hard-cap:{patrol_guard.get('started_iterations')}>= {patrol_guard.get('max_iterations')}",
            auto_rerun_allowed=False,
            failures=[str(patrol_guard.get("reason"))],
        )
        append_jsonl(patrol_ledger_path(work_root), {
            "event": "e2e_iteration_blocked",
            "recorded_at": iso_now(),
            "reason": patrol_guard.get("reason"),
            "guard": patrol_guard,
            "long_task_active_run": active_run,
        })
        return {
            "schema_id": "redcap-ai-e2e-run-result",
            "ok": False,
            "ready_for_engineering_use": False,
            "blocked_before_project_run": True,
            "patrol_iteration_guard": patrol_guard,
            "long_task_active_run": active_run,
            "failures": [str(patrol_guard.get("reason"))],
        }
    rerun_guard = convergence_rerun_guard(work_root)
    write_json(work_root / "redcap-e2e-convergence-rerun-guard.json", rerun_guard)
    if rerun_guard.get("blocked") is True:
        active_run = write_e2e_long_task_active_run(
            work_root,
            direction=direction,
            iteration=next_iteration,
            status="blocked",
            action_evidence=["runtime/bin/redcap complete-revival-e2e run blocked by convergence rerun guard"],
            objective_delta="上一轮结构性收敛诊断未被源码或证据变化覆盖，入口阻断盲目重跑。",
            blocker_signature=str(rerun_guard.get("recorded_source_signature") or "convergence-structural-stop"),
            auto_rerun_allowed=False,
            failures=[str(rerun_guard.get("reason"))],
        )
        return {
            "schema_id": "redcap-ai-e2e-run-result",
            "ok": False,
            "ready_for_engineering_use": False,
            "blocked_before_project_run": True,
            "convergence_rerun_guard": rerun_guard,
            "long_task_active_run": active_run,
            "failures": [str(rerun_guard.get("reason"))],
        }
    layered_preflight = run_layered_preflight(work_root)
    if layered_preflight.get("ok") is not True:
        active_run = write_e2e_long_task_active_run(
            work_root,
            direction=direction,
            iteration=next_iteration,
            status="blocked",
            action_evidence=[
                "runtime/bin/redcap complete-revival-e2e preflight",
                str(work_root / "redcap-e2e-layered-preflight.json"),
            ],
            objective_delta="E2E 在启动 Codex CLI 承载探针和 Loom 角色前验证 RedCap 自身的 Loom、自我净化、知识召回和项目级发布安装能力；当前分层前置检查失败，继续执行会把目标项目产物误当成 RedCap 能力成熟。",
            blocker_signature="layered-preflight:" + ",".join(str(item) for item in layered_preflight.get("failures", [])),
            auto_rerun_allowed=False,
            failures=[str(item) for item in layered_preflight.get("failures", [])],
        )
        append_jsonl(patrol_ledger_path(work_root), {
            "event": "e2e_iteration_blocked",
            "recorded_at": iso_now(),
            "reason": "RedCap E2E 分层前置检查失败",
            "layered_preflight": layered_preflight,
            "long_task_active_run": active_run,
        })
        return {
            "schema_id": "redcap-ai-e2e-run-result",
            "ok": False,
            "ready_for_engineering_use": False,
            "blocked_before_project_run": True,
            "layered_preflight": layered_preflight,
            "long_task_active_run": active_run,
            "failures": ["RedCap E2E 分层前置检查失败，不能启动 Loom 角色执行。", *layered_preflight.get("failures", [])],
        }
    carrier = carrier_probe(work_root / "carrier-preflight", min(max(timeout_seconds, 120), 240))
    write_json(work_root / "redcap-e2e-carrier-preflight.json", carrier)
    if carrier.get("ok") is not True:
        active_run = write_e2e_long_task_active_run(
            work_root,
            direction=direction,
            iteration=next_iteration,
            status="blocked",
            action_evidence=[
                "runtime/bin/redcap complete-revival-e2e carrier-probe",
                str(work_root / "redcap-e2e-carrier-preflight.json"),
            ],
            objective_delta="E2E 在启动 Loom 角色前验证 Codex CLI 项目级 hook 承载；当前承载探针失败，禁止继续执行会突破 hook 保障的角色流程。",
            blocker_signature=f"codex-cli-hook-carrier:{','.join(carrier.get('missing_events') or []) or 'command-failed'}",
            auto_rerun_allowed=False,
            failures=[str(item) for item in carrier.get("failures", [])],
        )
        append_jsonl(patrol_ledger_path(work_root), {
            "event": "e2e_iteration_blocked",
            "recorded_at": iso_now(),
            "reason": "Codex CLI 项目级 hook 承载探针失败",
            "carrier_probe": carrier,
            "long_task_active_run": active_run,
        })
        return {
            "schema_id": "redcap-ai-e2e-run-result",
            "ok": False,
            "ready_for_engineering_use": False,
            "blocked_before_project_run": True,
            "carrier_probe": carrier,
            "long_task_active_run": active_run,
            "failures": ["Codex CLI 项目级 hook 承载探针失败，不能启动 Loom 角色执行。", *carrier.get("failures", [])],
        }
    append_jsonl(patrol_ledger_path(work_root), {
        "event": "e2e_iteration_started",
        "recorded_at": iso_now(),
        "iteration": patrol_guard.get("next_iteration"),
        "direction_sha256": sha256_text(direction),
        "timeout_seconds": timeout_seconds,
    })
    active_run_start = write_e2e_long_task_active_run(
        work_root,
        direction=direction,
        iteration=next_iteration,
        status="running",
        action_evidence=[
            "runtime/bin/redcap complete-revival-e2e run",
            str(patrol_ledger_path(work_root)),
            str(work_root / "redcap-e2e-patrol-iteration-guard.json"),
            str(work_root / "redcap-e2e-convergence-rerun-guard.json"),
            str(work_root / "redcap-e2e-layered-preflight.json"),
            str(work_root / "redcap-e2e-carrier-preflight.json"),
        ],
        objective_delta="E2E 巡检入口已进入真实运行，父目标循环、轮次守卫、收敛守卫、RedCap 分层前置检查和 Codex CLI hook 承载预检均已产生可校验证据。",
        blocker_signature="none-before-worker-start",
        auto_rerun_allowed=True,
        failures=[],
    )
    entry_failures = e2e_active_run_entry_failures_via_boundary_check(active_run_start)
    if entry_failures:
        return {
            "schema_id": "redcap-ai-e2e-run-result",
            "ok": False,
            "ready_for_engineering_use": False,
            "blocked_before_project_run": True,
            "long_task_active_run": active_run_start,
            "failures": entry_failures,
        }
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
    stale_watchdog_cleanup = cleanup_stale_harness_watchdogs(work_root)
    started = iso_now()
    worker_deadline_monotonic = time.monotonic() + timeout_seconds
    worker_deadline_epoch = time.time() + timeout_seconds
    worker = subprocess.Popen(
        argv,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env=env,
    )
    worker_substrings = worker_command_substrings(argv, work_root)
    worker_identity = process_identity(worker.pid, worker_substrings)
    watchdog_record = start_harness_watchdog(
        work_root,
        argv,
        timeout_seconds,
        worker,
        worker_identity,
        worker_deadline_epoch,
    )
    observer_requests: set[str] = set()
    observer_commands: list[dict[str, Any]] = []
    skipped_observer_requests: list[dict[str, Any]] = []
    skipped_observer_request_keys: set[str] = set()
    timed_out = False
    interrupted = False
    interrupt_reason: str | None = None
    process_group_killed = False
    exit_reason = "completed"
    old_signal_handlers: dict[int, Any] = {}

    def harness_signal_handler(signum: int, _frame: Any) -> None:
        try:
            signal_name = signal.Signals(signum).name
        except ValueError:
            signal_name = f"signal-{signum}"
        raise HarnessInterrupted(signal_name)

    for handled_signal in (signal.SIGTERM, signal.SIGHUP):
        try:
            old_signal_handlers[int(handled_signal)] = signal.getsignal(handled_signal)
            signal.signal(handled_signal, harness_signal_handler)
        except (OSError, ValueError):
            pass
    try:
        while worker.poll() is None:
            for request_path in sorted(work_root.glob("**/.redcap/evidence/e2e/observer-request.json")):
                resolved = request_path.resolve()
                decision = observer_request_routing_decision(resolved, worker.pid)
                request_key = f"{resolved}:{decision.get('request_sha256')}"
                if request_key in observer_requests:
                    continue
                if decision.get("ready") is not True:
                    if decision.get("reason") != "unreadable":
                        observer_requests.add(request_key)
                    skipped_key = f"{resolved}:{decision.get('reason')}:{decision.get('request_sha256')}"
                    if skipped_key not in skipped_observer_request_keys:
                        skipped_observer_request_keys.add(skipped_key)
                        skipped_observer_requests.append(decision)
                    continue
                observer_requests.add(request_key)
                observer_commands.append(run_observer_request_as_harness(resolved, runner_pid=worker.pid, harness_pid=os.getpid()))
            if time.monotonic() > worker_deadline_monotonic:
                timed_out = True
                exit_reason = "timeout"
                process_group_killed = kill_process_group(
                    worker,
                    grace_seconds=2.0,
                    expected_identity=worker_identity,
                    command_substrings=worker_substrings,
                ) or process_group_killed
                break
            time.sleep(0.5)
    except HarnessInterrupted as exc:
        interrupted = True
        interrupt_reason = exc.signal_name
        exit_reason = "interrupt"
        process_group_killed = kill_process_group(
            worker,
            grace_seconds=2.0,
            expected_identity=worker_identity,
            command_substrings=worker_substrings,
        ) or process_group_killed
    except KeyboardInterrupt:
        interrupted = True
        interrupt_reason = "KeyboardInterrupt"
        exit_reason = "interrupt"
        process_group_killed = kill_process_group(
            worker,
            grace_seconds=2.0,
            expected_identity=worker_identity,
            command_substrings=worker_substrings,
        ) or process_group_killed
    finally:
        for signum, previous_handler in old_signal_handlers.items():
            try:
                signal.signal(signum, previous_handler)
            except (OSError, ValueError):
                pass
        if (timed_out or interrupted) and worker.poll() is None:
            process_group_killed = kill_process_group(
                worker,
                grace_seconds=2.0,
                expected_identity=worker_identity,
                command_substrings=worker_substrings,
            ) or process_group_killed
    stdout, stderr, communicate_timed_out = communicate_worker_after_stop(worker, HARNESS_WORKER_COMMUNICATE_TIMEOUT_SECONDS)
    watchdog_cleanup = cleanup_harness_watchdog_record(pathlib.Path(str(watchdog_record.get("record_path"))))
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
        harness_failures.append(f"E2E harness worker 达到硬超时 {timeout_seconds} 秒；观察者超时没有延长 worker 截止时间")
    if interrupted:
        harness_failures.append(f"E2E harness 被中断：{interrupt_reason or 'unknown'}，已请求清理 worker 进程组")
    if communicate_timed_out:
        harness_failures.append("E2E worker 停止后收集输出超时")
    if worker.returncode != 0 and parsed.get("ok") is True:
        harness_failures.append(f"E2E worker 退出码非 0：{worker.returncode}")
    if not observer_commands:
        harness_failures.append("E2E worker 没有发出 observer-request.json")
    if any(command.get("ok") is not True for command in observer_commands):
        harness_failures.append("至少一个独立观察者命令失败")
    if exit_reason == "completed" and (worker.returncode is not None and worker.returncode < 0):
        exit_reason = "crash"
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
        "worker_pgid": worker_identity.get("pgid"),
        "worker_exit_code": worker.returncode,
        "worker_exit_reason": exit_reason,
        "worker_timed_out": timed_out,
        "interrupted": interrupted,
        "interrupt_reason": interrupt_reason,
        "process_group_killed": process_group_killed,
        "communicate_timed_out": communicate_timed_out,
        "timeout_seconds": timeout_seconds,
        "worker_deadline_policy": {
            "type": "hard_timeout_seconds",
            "worker_deadline_epoch": worker_deadline_epoch,
            "observer_timeout_extends_worker_deadline": False,
            "observer_timeout_seconds": OBSERVER_TIMEOUT_SECONDS,
        },
        "worker_identity": worker_identity,
        "watchdog_record": watchdog_record,
        "watchdog_cleanup": watchdog_cleanup,
        "stale_watchdog_cleanup": stale_watchdog_cleanup,
        "observer_request_count": len(observer_requests),
        "observer_commands": observer_commands,
        "skipped_observer_requests": skipped_observer_requests[-80:],
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-4000:],
    }
    try:
        write_json(work_root / "redcap-e2e-harness-summary.json", parsed["harness"])
        write_json(work_root / "redcap-e2e-run-summary.json", parsed)
    except Exception:
        pass
    evidence_root = parsed.get("evidence_root")
    if isinstance(evidence_root, str):
        try:
            write_json(pathlib.Path(evidence_root) / "harness-summary.json", parsed["harness"])
            write_json(pathlib.Path(evidence_root) / "run-summary.json", parsed)
        except Exception:
            pass
    append_jsonl(patrol_ledger_path(work_root), {
        "event": "e2e_iteration_finished",
        "recorded_at": iso_now(),
        "iteration": patrol_guard.get("next_iteration"),
        "ok": parsed.get("ok") is True,
        "ready_for_engineering_use": parsed.get("ready_for_engineering_use") is True,
        "evidence_root": evidence_root,
        "failure_count": len(parsed.get("failures", []) if isinstance(parsed.get("failures"), list) else []),
    })
    parsed_failures = [
        str(item)
        for item in parsed.get("failures", [])
        if isinstance(parsed.get("failures"), list) and str(item).strip()
    ]
    final_status = "passed" if parsed.get("ok") is True else ("blocked" if parsed.get("blocked_before_project_run") is True else "failed")
    final_delta = (
        "本轮 E2E 通过运行器、观察者和最终证据检查，父目标获得正向推进。"
        if parsed.get("ok") is True
        else "本轮 E2E 暴露了仍需修复的机制或交付缺口，失败已进入父任务运行包。"
    )
    active_run_final = write_e2e_long_task_active_run(
        work_root,
        direction=direction,
        iteration=next_iteration,
        status=final_status,
        action_evidence=[
            "runtime/bin/redcap complete-revival-e2e run",
            str(work_root / "redcap-e2e-patrol-ledger.jsonl"),
            str(evidence_root or "no-evidence-root"),
            str(pathlib.Path(str(evidence_root)) / "run-summary.json") if isinstance(evidence_root, str) else "run-summary-unavailable",
        ],
        objective_delta=final_delta,
        blocker_signature=sha256_text("\n".join(parsed_failures)) if parsed_failures else "none",
        auto_rerun_allowed=parsed.get("ok") is not True and final_status != "blocked",
        failures=parsed_failures,
    )
    parsed["long_task_active_run"] = active_run_final
    expected_lifecycle_state = "completed" if parsed.get("ok") is True else ("blocked" if final_status == "blocked" else "running")
    discovery = discover_e2e_long_task_active_run(
        work_root,
        expected_lifecycle_state=expected_lifecycle_state,
        require_completion_boundary=parsed.get("ok") is True,
    )
    parsed["long_task_active_run_discovery"] = discovery
    final_failures = e2e_active_run_final_failures_via_boundary_check(
        active_run_final,
        parsed_ok=parsed.get("ok") is True,
        final_status=final_status,
    )
    if discovery.get("ok") is not True:
        final_failures.append("E2E 巡检未能正确发现或读取 active_run 完成边界。")
    if final_failures:
        parsed["ok"] = False
        parsed["ready_for_engineering_use"] = False
        parsed.setdefault("failures", [])
        if isinstance(parsed["failures"], list):
            parsed["failures"].extend(final_failures)
    if isinstance(evidence_root, str):
        try:
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


def cmd_preflight(args: argparse.Namespace) -> int:
    result = run_layered_preflight(resolve_work_root(args.work_root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok"):
        print("REDCAP_AI_E2E_PREFLIGHT_OK")
        return 0
    return 1


def cmd_convergence_check(args: argparse.Namespace) -> int:
    evidence = pathlib.Path(args.evidence_root).expanduser().resolve()
    result = convergence_diagnosis_from_evidence(evidence)
    if args.out:
        write_json(pathlib.Path(args.out).expanduser().resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("final_prism_ok") is True:
        print("REDCAP_AI_E2E_CONVERGENCE_PASS")
        return 0
    if result.get("auto_rerun_allowed") is False and result.get("diagnosis"):
        print("REDCAP_AI_E2E_CONVERGENCE_STRUCTURAL_STOP")
        if args.expect_structural_stop:
            return 0
        return 2
    return 1


def cmd_convergence_guard_check(args: argparse.Namespace) -> int:
    result = convergence_rerun_guard(resolve_work_root(args.work_root))
    if args.out:
        write_json(pathlib.Path(args.out).expanduser().resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.expect_blocked:
        if result.get("blocked") is True:
            print("REDCAP_AI_E2E_CONVERGENCE_GUARD_BLOCKED_OK")
            return 0
        return 1
    if result.get("ok") is True:
        print("REDCAP_AI_E2E_CONVERGENCE_GUARD_OK")
        return 0
    return 1


def cmd_runtime_boundary_probe(args: argparse.Namespace) -> int:
    result = run_e2e_active_run_runtime_boundary_probe(resolve_work_root(args.work_root))
    if args.out:
        write_json(pathlib.Path(args.out).expanduser().resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok") is True:
        print("REDCAP_AI_E2E_RUNTIME_BOUNDARY_PROBE_OK")
        return 0
    return 1


def cmd_long_task_integration_dry_run(args: argparse.Namespace) -> int:
    result = run_long_task_e2e_integration_dry_run(resolve_work_root(args.work_root))
    if args.out:
        write_json(pathlib.Path(args.out).expanduser().resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok") is True:
        print("REDCAP_AI_E2E_LONG_TASK_INTEGRATION_DRY_RUN_OK")
        return 0
    return 1


def cmd_harness_timeout_regression_test(args: argparse.Namespace) -> int:
    result = run_harness_timeout_regression_test(resolve_work_root(args.work_root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok") is True:
        print("REDCAP_AI_E2E_HARNESS_TIMEOUT_REGRESSION_OK")
        return 0
    return 1


def write_runner_negative_probe_regression_project(project: pathlib.Path, global_name: str, data_filename: str) -> pathlib.Path:
    (project / "data").mkdir(parents=True, exist_ok=True)
    (project / "scripts").mkdir(parents=True, exist_ok=True)
    payload = {
        "activities": [
            {
                "id": f"{global_name.lower()}-activity-1",
                "title": f"{global_name} 自检活动一",
                "players": [{"id": f"{global_name.lower()}-player-1", "name": "自检玩家一"}],
                "characters": [{"id": f"{global_name.lower()}-character-1", "name": "自检角色一", "playerId": f"{global_name.lower()}-player-1"}],
                "signupIntent": "第一场需要报名者",
                "signups": [{"id": f"{global_name.lower()}-signup-1", "playerId": f"{global_name.lower()}-player-1"}],
            },
            {
                "id": f"{global_name.lower()}-activity-2",
                "title": f"{global_name} 自检活动二",
                "players": [{"id": f"{global_name.lower()}-player-2", "name": "自检玩家二"}],
                "characters": [{"id": f"{global_name.lower()}-character-2", "name": "自检角色二", "playerId": f"{global_name.lower()}-player-2"}],
                "signupIntent": "第二场也需要报名者",
                "signups": [{"id": f"{global_name.lower()}-signup-2", "playerId": f"{global_name.lower()}-player-2"}],
            },
        ]
    }
    data_path = project / "data" / data_filename
    data_path.write_text(
        f"window.{global_name} = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    (project / "README.md").write_text("## 验证\n\n```sh\nnode scripts/validate-data.js\n```\n", encoding="utf-8")
    (project / "scripts" / "validate-data.js").write_text(
        "const fs = require('fs');\n"
        "const vm = require('vm');\n"
        f"const source = fs.readFileSync('data/{data_filename}', 'utf8');\n"
        "const sandbox = { window: {} };\n"
        "sandbox.globalThis = sandbox.window;\n"
        "vm.createContext(sandbox);\n"
        f"vm.runInContext(source, sandbox, {{ filename: 'data/{data_filename}' }});\n"
        f"const data = sandbox.window.{global_name};\n"
        f"if (!data || !Array.isArray(data.activities)) {{ console.error('{global_name} data not set'); process.exit(10); }}\n"
        "for (const [index, activity] of data.activities.entries()) {\n"
        "  if (!activity.signupIntent || !Array.isArray(activity.signups) || activity.signups.length === 0) {\n"
        "    console.error(`signup-intent-data-contract failed at ${index}`);\n"
        "    process.exit(2);\n"
        "  }\n"
        "  const playerIds = new Set((activity.players || []).map((player) => player.id));\n"
        "  if (!Array.isArray(activity.characters) || activity.characters.some((character) => !playerIds.has(character.playerId))) {\n"
        "    console.error(`character-player-relation-contract failed at ${index}`);\n"
        "    process.exit(3);\n"
        "  }\n"
        "}\n"
        f"console.log(JSON.stringify({{ok: true, source: '{global_name}'}}));\n",
        encoding="utf-8",
    )
    return data_path


def write_generic_runner_negative_probe_regression_project(project: pathlib.Path) -> pathlib.Path:
    (project / "data").mkdir(parents=True, exist_ok=True)
    (project / "scripts").mkdir(parents=True, exist_ok=True)
    payload = {
        "sessions": [
            {
                "id": "workshop-session-1",
                "title": "工作坊报名与分组自检一",
                "participants": [{"id": "participant-1", "name": "参与者一"}],
                "assignments": [{"id": "assignment-1", "name": "任务分配一", "participantId": "participant-1"}],
                "registrationIntent": "第一场需要注册者",
                "registrations": [{"id": "registration-1", "participantId": "participant-1"}],
            },
            {
                "id": "workshop-session-2",
                "title": "工作坊报名与分组自检二",
                "participants": [{"id": "participant-2", "name": "参与者二"}],
                "assignments": [{"id": "assignment-2", "name": "任务分配二", "participantId": "participant-2"}],
                "registrationIntent": "第二场也需要注册者",
                "registrations": [{"id": "registration-2", "participantId": "participant-2"}],
            },
        ]
    }
    data_path = project / "data" / "domain-data.js"
    data_path.write_text(
        "window.APP_DATA = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    (project / "README.md").write_text("## 验证\n\n```sh\nnode scripts/validate-data.js\n```\n", encoding="utf-8")
    (project / "scripts" / "validate-data.js").write_text(
        "const fs = require('fs');\n"
        "const vm = require('vm');\n"
        "const source = fs.readFileSync('data/domain-data.js', 'utf8');\n"
        "const sandbox = { window: {} };\n"
        "sandbox.globalThis = sandbox.window;\n"
        "vm.createContext(sandbox);\n"
        "vm.runInContext(source, sandbox, { filename: 'data/domain-data.js' });\n"
        "const data = sandbox.window.APP_DATA;\n"
        "if (!data || !Array.isArray(data.sessions)) { console.error('APP_DATA data not set'); process.exit(10); }\n"
        "for (const [index, session] of data.sessions.entries()) {\n"
        "  if (!session.registrationIntent || !Array.isArray(session.registrations) || session.registrations.length === 0) {\n"
        "    console.error(`signup-intent-data-contract failed at ${index}: registrations missing`);\n"
        "    process.exit(2);\n"
        "  }\n"
        "  const participantIds = new Set((session.participants || []).map((participant) => participant.id));\n"
        "  if (!Array.isArray(session.assignments) || session.assignments.some((assignment) => !participantIds.has(assignment.participantId))) {\n"
        "    console.error(`character-player-relation-contract failed at ${index}: participant assignment reference missing`);\n"
        "    process.exit(3);\n"
        "  }\n"
        "}\n"
        "console.log(JSON.stringify({ok: true, source: 'APP_DATA'}));\n",
        encoding="utf-8",
    )
    return data_path


def run_runner_negative_probe_setup_error_control(work_root: pathlib.Path) -> dict[str, Any]:
    project = work_root / "setup-error-syntax-control"
    data_path = write_runner_negative_probe_regression_project(project, "TRPG_SEED_DATA", "seed-data.js")
    argv = ["node", "scripts/validate-data.js"]
    positive_run = run_command(argv, cwd=project, timeout_seconds=60)
    original_bytes = data_path.read_bytes()
    original_sha256 = hashlib.sha256(original_bytes).hexdigest()
    syntax_check: dict[str, Any] = {}
    negative_receipt: dict[str, Any] | None = None
    restore_receipt: dict[str, Any] | None = None
    try:
        data_path.write_text("window.TRPG_SEED_DATA = ;\n", encoding="utf-8")
        syntax_check = structured_data_probe_syntax_check(project, data_path)
        negative_run = run_command(argv, cwd=project, timeout_seconds=60)
        negative_receipt = command_receipt(negative_run)
    finally:
        data_path.write_bytes(original_bytes)
        restore_run = run_command(argv, cwd=project, timeout_seconds=60)
        restore_receipt = command_receipt(restore_run)
    signup_detected = domain_failure_detected(negative_receipt, "signup-intent-data-contract")
    relation_detected = domain_failure_detected(negative_receipt, "character-player-relation-contract")
    output_text = receipt_text(negative_receipt)
    setup_marker_detected = any(
        marker in output_text
        for marker in [
            "syntaxerror",
            "unexpected token",
            "did not set window",
            "data not set",
        ]
    )
    checks = [
        {
            "name": "positive_validation_passes_before_control",
            "passed": positive_run.get("ok") is True,
            "evidence": command_receipt(positive_run),
        },
        {
            "name": "control_setup_error_is_syntax_invalid",
            "passed": syntax_check.get("ok") is False,
            "evidence": syntax_check,
        },
        {
            "name": "setup_error_validation_exits_nonzero",
            "passed": isinstance(negative_receipt, dict) and negative_receipt.get("exit_code") not in (0, None),
            "evidence": negative_receipt,
        },
        {
            "name": "setup_error_not_classified_as_domain_failure",
            "passed": signup_detected is False and relation_detected is False,
            "evidence": {
                "signup_domain_failure_detected": signup_detected,
                "relation_domain_failure_detected": relation_detected,
                "setup_marker_detected": setup_marker_detected,
            },
        },
        {
            "name": "original_data_restored_after_setup_error_control",
            "passed": isinstance(restore_receipt, dict)
            and restore_receipt.get("exit_code") == 0
            and sha256_file(data_path) == original_sha256,
            "evidence": restore_receipt,
        },
    ]
    failures = [item["name"] for item in checks if item.get("passed") is not True]
    return {
        "schema_id": "redcap-e2e-runner-negative-probe-setup-error-control",
        "case_id": "setup-error-syntax-control",
        "data_path": str(data_path.relative_to(project)),
        "original_sha256": original_sha256,
        "positive_validation": command_receipt(positive_run),
        "syntax_check": syntax_check,
        "negative_command": negative_receipt,
        "restore_command": restore_receipt,
        "signup_domain_failure_detected": signup_detected,
        "relation_domain_failure_detected": relation_detected,
        "setup_marker_detected": setup_marker_detected,
        "checks": checks,
        "ok": not failures,
        "failures": failures,
    }


def runner_negative_probe_audit(cases: list[dict[str, Any]]) -> dict[str, Any]:
    function_names = [
        "write_structured_data_probe_payload",
        "write_mutated_probe_snapshot",
        "domain_failure_detected",
        "signup_record_contract_fields",
        "append_relation_matches",
        "run_runner_negative_contract_probe",
        "run_runner_character_player_contract_probe",
    ]
    function_sources: dict[str, dict[str, Any]] = {}
    for name in function_names:
        fn = globals().get(name)
        if fn is None:
            continue
        source = inspect.getsource(fn)
        function_sources[name] = {
            "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "source": source,
        }
    probe_summaries: list[dict[str, Any]] = []
    for case in cases:
        for probe_key in ["signup_probe", "character_probe"]:
            probe = case.get(probe_key)
            if not isinstance(probe, dict):
                continue
            probe_summaries.append({
                "case_id": case.get("id"),
                "probe_key": probe_key,
                "target_contract": probe.get("target_contract"),
                "ok": probe.get("ok"),
                "contract_failure_detected": probe.get("contract_failure_detected"),
                "mutation": probe.get("mutation"),
                "negative_command": probe.get("negative_command"),
                "restore_command": probe.get("restore_command"),
            })
    return {
        "schema_id": "redcap-e2e-runner-negative-probe-independent-audit",
        "created_at": iso_now(),
        "source_file": str(pathlib.Path(__file__).resolve().relative_to(REPO_ROOT)),
        "source_file_sha256": sha256_file(pathlib.Path(__file__).resolve()),
        "alias_constants": {
            "SIGNUP_COLLECTION_FIELD_CANDIDATES": SIGNUP_COLLECTION_FIELD_CANDIDATES,
            "SIGNUP_INTENT_FIELD_CANDIDATES": SIGNUP_INTENT_FIELD_CANDIDATES,
            "RELATION_PARENT_LIST_KEYS": RELATION_PARENT_LIST_KEYS,
            "RELATION_CHILD_LIST_KEYS": RELATION_CHILD_LIST_KEYS,
            "RELATION_REFERENCE_KEYS": RELATION_REFERENCE_KEYS,
            "RELATION_NAME_REFERENCE_KEYS": sorted(RELATION_NAME_REFERENCE_KEYS),
        },
        "function_sources": function_sources,
        "probe_summaries": probe_summaries,
    }


def runner_negative_probe_case_failures(case: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for probe_key, expected_contract in [
        ("signup_probe", "signup-intent-data-contract"),
        ("character_probe", "character-player-relation-contract"),
    ]:
        probe = case.get(probe_key)
        if not isinstance(probe, dict):
            failures.append(f"{probe_key} 缺失")
            continue
        if probe.get("ok") is not True:
            failures.append(f"{probe_key} 未通过：{probe.get('failures')}")
        if probe.get("contract_failure_detected") is not True:
            failures.append(f"{probe_key} 没有检测到 {expected_contract} 领域失败")
        mutation = probe.get("mutation")
        if not isinstance(mutation, dict):
            failures.append(f"{probe_key} 缺少 mutation 摘要")
            continue
        if mutation.get("executor") != "runner_internal":
            failures.append(f"{probe_key} mutation.executor 不是 runner_internal")
        syntax_check = mutation.get("syntax_check")
        if not isinstance(syntax_check, dict) or syntax_check.get("ok") is not True:
            failures.append(f"{probe_key} 写回后的语法检查未通过")
        if not mutation.get("mutated_sha256") or mutation.get("mutated_sha256") == mutation.get("original_sha256"):
            failures.append(f"{probe_key} 没有记录有效的变更前后哈希")
        output_text = receipt_text(probe.get("negative_command") if isinstance(probe.get("negative_command"), dict) else None)
        if "trpg_seed_data not set" in output_text or "data not set" in output_text:
            failures.append(f"{probe_key} 仍然退化成数据加载失败：{output_text[-160:]}")
    return failures


def run_runner_negative_probe_regression_test(work_root: pathlib.Path) -> dict[str, Any]:
    work_root.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    cases: list[dict[str, Any]] = []
    configured_cases = [
        ("trpg-seed-data", "TRPG_SEED_DATA", "seed-data.js", "trpg-compatible"),
        ("redcap-data", "REDCAP_DATA", "redcap-data.js", "redcap-compatible"),
        ("project-data", "PROJECT_DATA", "project-data.js", "project-compatible"),
        ("activity-data", "ACTIVITY_DATA", "activity-data.js", "activity-compatible"),
        ("sample-data", "SAMPLE_DATA", "sample-data.js", "sample-compatible"),
        ("generic-workshop-app-data", "APP_DATA", "domain-data.js", "generic-workshop"),
    ]
    for case_id, global_name, filename, case_kind in configured_cases:
        project = work_root / case_id
        evidence = project / ".redcap" / "evidence" / "e2e"
        evidence.mkdir(parents=True, exist_ok=True)
        if case_kind == "generic-workshop":
            data_path = write_generic_runner_negative_probe_regression_project(project)
        else:
            data_path = write_runner_negative_probe_regression_project(project, global_name, filename)
        positive = run_command(["node", "scripts/validate-data.js"], cwd=project, timeout_seconds=60)
        signup_probe = run_runner_negative_contract_probe(project, evidence)
        character_probe = run_runner_character_player_contract_probe(project, evidence)
        case = {
            "id": case_id,
            "case_kind": case_kind,
            "global_name": global_name,
            "data_path": str(data_path.relative_to(project)),
            "positive_validation": command_receipt(positive),
            "signup_probe": signup_probe,
            "character_probe": character_probe,
        }
        case_failures = runner_negative_probe_case_failures(case)
        if positive.get("ok") is not True:
            case_failures.append(f"{case_id} 原始验证命令未通过")
        case["ok"] = not case_failures
        case["failures"] = case_failures
        failures.extend(f"{case_id}: {item}" for item in case_failures)
        cases.append(case)
    setup_error_control = run_runner_negative_probe_setup_error_control(work_root)
    if setup_error_control.get("ok") is not True:
        failures.extend(f"setup-error-syntax-control: {item}" for item in setup_error_control.get("failures", []))
    audit = runner_negative_probe_audit(cases)
    audit_path = work_root / "redcap-e2e-runner-negative-probe-independent-audit.json"
    write_json(audit_path, audit)
    result = {
        "schema_id": "redcap-e2e-runner-negative-probe-regression-test",
        "ok": not failures,
        "work_root": str(work_root),
        "audit_path": str(audit_path),
        "audit_sha256": sha256_file(audit_path),
        "cases": cases,
        "setup_error_control": setup_error_control,
        "failures": failures,
    }
    write_json(work_root / "redcap-e2e-runner-negative-probe-regression-test.json", result)
    return result


def cmd_runner_negative_probe_regression_test(args: argparse.Namespace) -> int:
    result = run_runner_negative_probe_regression_test(resolve_work_root(args.work_root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok") is True:
        print("REDCAP_AI_E2E_RUNNER_NEGATIVE_PROBE_REGRESSION_OK")
        return 0
    return 1


def cmd_harness_watchdog(args: argparse.Namespace) -> int:
    result = run_harness_watchdog(pathlib.Path(args.record).expanduser().resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") is True else 1


def cmd_run(args: argparse.Namespace) -> int:
    result = run_e2e_harness(direction_from_args(args), resolve_work_root(args.work_root), args.timeout_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok"):
        print("REDCAP_AI_E2E_RUN_OK")
        return 0
    return 1


def layered_preflight_block_failures(result: dict[str, Any], work_root: pathlib.Path) -> list[str]:
    failures: list[str] = []
    if result.get("ok") is True:
        failures.append("分层前置负向运行不应通过")
    if result.get("blocked_before_project_run") is not True:
        failures.append("分层前置负向运行没有返回 blocked_before_project_run=true")
    active_packet = load_optional_json(pathlib.Path(str(result.get("long_task_active_run", {}).get("packet") or "")))
    if not isinstance(active_packet, dict):
        failures.append("分层前置负向运行没有写入 active_run 包")
    else:
        if active_packet.get("lifecycle_state") != "blocked":
            failures.append("分层前置负向运行 active_run.lifecycle_state 不是 blocked")
        if active_packet.get("auto_rerun_allowed") is not False:
            failures.append("分层前置负向运行 active_run.auto_rerun_allowed 不是 false")
    if (work_root / "redcap-e2e-carrier-preflight.json").exists():
        failures.append("分层前置失败后仍启动了 Codex CLI 承载探针")
    if list(work_root.glob("**/role-artifacts/*.json")):
        failures.append("分层前置失败后仍出现 Loom 角色产物")
    return failures


def run_layered_preflight_regression_test(work_root: pathlib.Path) -> dict[str, Any]:
    work_root.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    normal = run_layered_preflight(work_root / "normal-pass")
    cases.append({"id": "normal-pass", "ok": normal.get("ok") is True, "result": normal})
    if normal.get("ok") is not True:
        failures.append(f"正常分层前置检查未通过：{normal.get('failures')}")

    saved_test_mode = os.environ.get(TEST_MODE_ENV)
    saved_injection = os.environ.get(TEST_INJECT_LAYERED_PREFLIGHT_FAILURE_ENV)
    try:
        os.environ[TEST_MODE_ENV] = "1"
        for injected_check in ["knowledge-search-loom", "self-purification-self-check"]:
            case_root = work_root / f"negative-{injected_check}"
            os.environ[TEST_INJECT_LAYERED_PREFLIGHT_FAILURE_ENV] = injected_check
            result = run_e2e_harness(
                f"自检方向：验证 {injected_check} 失败会阻断完整 E2E",
                case_root,
                timeout_seconds=240,
            )
            case_failures = layered_preflight_block_failures(result, case_root)
            cases.append({
                "id": f"negative-{injected_check}",
                "ok": not case_failures,
                "injected_check": injected_check,
                "failures": case_failures,
                "blocked_before_project_run": result.get("blocked_before_project_run"),
                "carrier_preflight_exists": (case_root / "redcap-e2e-carrier-preflight.json").exists(),
                "role_artifact_count": len(list(case_root.glob("**/role-artifacts/*.json"))),
                "active_run": result.get("long_task_active_run"),
            })
            failures.extend(f"{injected_check}: {item}" for item in case_failures)
    finally:
        if saved_test_mode is None:
            os.environ.pop(TEST_MODE_ENV, None)
        else:
            os.environ[TEST_MODE_ENV] = saved_test_mode
        if saved_injection is None:
            os.environ.pop(TEST_INJECT_LAYERED_PREFLIGHT_FAILURE_ENV, None)
        else:
            os.environ[TEST_INJECT_LAYERED_PREFLIGHT_FAILURE_ENV] = saved_injection

    result = {
        "schema_id": "redcap-e2e-layered-preflight-regression-test",
        "ok": not failures,
        "work_root": str(work_root),
        "cases": cases,
        "failures": failures,
    }
    write_json(work_root / "redcap-e2e-layered-preflight-regression-test.json", result)
    return result


def cmd_preflight_regression_test(args: argparse.Namespace) -> int:
    result = run_layered_preflight_regression_test(resolve_work_root(args.work_root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok"):
        print("REDCAP_AI_E2E_PREFLIGHT_REGRESSION_TEST_OK")
        return 0
    return 1


def cmd_self_check(args: argparse.Namespace) -> int:
    failures: list[str] = []
    if validate_contract(load_json(CONTRACT)):
        failures.append("通用 E2E 合同检查失败")
    with tempfile.TemporaryDirectory(prefix="redcap-ai-e2e-self-check-") as raw:
        work_root = pathlib.Path(raw).resolve()
        layered_preflight = run_layered_preflight(work_root / "layered-preflight-self-check")
        if layered_preflight.get("ok") is not True:
            failures.append(f"E2E 分层前置检查失败：{layered_preflight.get('failures')}")
        preflight_regression = run_layered_preflight_regression_test(work_root / "layered-preflight-regression")
        if preflight_regression.get("ok") is not True:
            failures.append(f"E2E 分层前置回归测试失败：{preflight_regression.get('failures')}")
        harness_timeout_regression = run_harness_timeout_regression_test(work_root / "harness-timeout-regression")
        if harness_timeout_regression.get("ok") is not True:
            failures.append(f"E2E harness 硬超时回归测试失败：{harness_timeout_regression.get('failures')}")
        runner_negative_probe_regression = run_runner_negative_probe_regression_test(work_root / "runner-negative-probe-regression")
        if runner_negative_probe_regression.get("ok") is not True:
            failures.append(f"E2E 运行器负向合同探针回归测试失败：{runner_negative_probe_regression.get('failures')}")
        regression_dir = work_root / "runner-negative-probe-regression"
        external_audit_out = regression_dir / "redcap-e2e-negative-probe-external-audit.json"
        external_audit = run_command([
            sys.executable,
            "runtime/audit/e2e_negative_probe_external_audit.py",
            "--regression-result",
            str(regression_dir / "redcap-e2e-runner-negative-probe-regression-test.json"),
            "--focused-audit",
            str(regression_dir / "redcap-e2e-runner-negative-probe-independent-audit.json"),
            "--contract",
            str(CONTRACT),
            "--out",
            str(external_audit_out),
        ], cwd=REPO_ROOT, timeout_seconds=60)
        if external_audit.get("ok") is not True:
            failures.append(f"E2E 运行器负向合同探针独立审计失败：{command_receipt(external_audit)}")
        missing_direction = prepare_project("", work_root / "missing")
        if missing_direction.get("ok") is True:
            failures.append("缺失 direction 的 prepare 没有失败")
        prepared = prepare_project("自检方向：交付一个本地可验证的小型工具", work_root / "prepare")
        if prepared.get("ok") is not True:
            failures.append(f"prepare 正向探针失败：{prepared.get('failures')}")
        else:
            runtime_boundary_probe = run_e2e_active_run_runtime_boundary_probe(work_root / "runtime-boundary-self-check")
            if runtime_boundary_probe.get("ok") is not True:
                failures.append(f"E2E active_run 运行时边界探针失败：{runtime_boundary_probe.get('failures')}")
            integration_dry_run = run_long_task_e2e_integration_dry_run(work_root / "long-task-integration-self-check")
            if integration_dry_run.get("ok") is not True:
                failures.append(f"长任务到 E2E 巡检集成干跑失败：{integration_dry_run.get('failures')}")
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
            if "exec" not in developer_argv:
                failures.append("developer Codex CLI argv 必须使用 codex exec 非交互入口，避免交互界面长驻导致角色证据缺失")
            if "--no-alt-screen" in developer_argv:
                failures.append("developer Codex CLI argv 不得在 exec 模式携带 --no-alt-screen")
            if "--enable" not in developer_argv or "hooks" not in developer_argv:
                failures.append("developer Codex CLI argv 必须显式启用 hooks，确保项目级 Hook 能参与角色执行")
            if "--output-last-message" not in developer_argv:
                failures.append("developer Codex CLI argv 必须写 output-last-message，确保角色消息证据可回收")
            else:
                message_index = developer_argv.index("--output-last-message")
                if message_index + 1 >= len(developer_argv) or developer_argv[message_index + 1] != str(evidence / "role-messages" / "developer.txt"):
                    failures.append("developer Codex CLI argv 的 output-last-message 目标不是角色消息证据文件")
            trust_config_arg = codex_project_trust_config_arg(project)
            if trust_config_arg not in developer_argv:
                failures.append("developer Codex CLI argv 必须携带项目级 trust 覆盖，否则外部 E2E 项目的 hooks 会被 Codex 禁用")
            role_prompt_source = inspect.getsource(build_role_prompt)
            role_pipeline_source = inspect.getsource(run_loom_role_pipeline)
            if "REDCAP_LOOM_ROLE_DONE" in role_prompt_source:
                failures.append("Loom 角色提示词不得包含机器完成标记，否则会被终端回显误判为完成")
            if "completion_markers=[" in role_pipeline_source and "REDCAP_LOOM_ROLE_DONE" in role_pipeline_source:
                failures.append("Loom 角色运行器不得用终端完成标记判断完成，必须以必需产物文件为准")
            if "completion_files=completion_files" not in role_pipeline_source:
                failures.append("Loom 角色运行器必须以必需产物文件作为收口依据")
            (evidence / "role-artifacts").mkdir(parents=True, exist_ok=True)
            write_json(evidence / "test-results.json", {
                "schema_id": "redcap-e2e-test-results",
                "role": "tester",
                "status": "in_progress",
                "passed": False,
                "commands": [],
                "positive_checks": [],
            })
            write_json(evidence / "negative-probes.json", {
                "schema_id": "redcap-e2e-negative-probes",
                "role": "tester",
                "status": "in_progress",
                "passed": False,
                "probes": [],
            })
            write_json(evidence / "role-artifacts" / "tester.json", {
                "schema_id": "redcap-e2e-role-artifact",
                "role": "tester",
                "status": "in_progress",
                "handoff_inputs": [],
                "handoff_outputs": [],
                "evidence_files": [],
                "notes": [],
                "upstream_challenges": [{"target": "fixture", "concern": "pending", "disposition": "pending", "reason": "fixture"}],
                "accepted_upstream_assumptions": [],
                "rejected_upstream_assumptions": [],
            })
            if role_completion_ready(project, evidence, "tester"):
                failures.append("tester 只写 in_progress 初始化文件时不得被判定为角色完成")
            write_json(evidence / "test-results.json", {
                "schema_id": "redcap-e2e-test-results",
                "role": "tester",
                "status": "completed",
                "passed": True,
                "commands": [{"command": "node scripts/validate.mjs", "exit_code": 0}],
                "positive_checks": [{"name": "validate", "passed": True}],
            })
            write_json(evidence / "negative-probes.json", {
                "schema_id": "redcap-e2e-negative-probes",
                "role": "tester",
                "status": "completed",
                "passed": True,
                "probes": [{"name": "signup-negative", "passed": True}],
            })
            write_json(evidence / "role-artifacts" / "tester.json", {
                "schema_id": "redcap-e2e-role-artifact",
                "role": "tester",
                "status": "completed",
                "handoff_inputs": ["implementation-log.json"],
                "handoff_outputs": ["test-results.json", "negative-probes.json", "role-artifacts/tester.json"],
                "evidence_files": ["test-results.json", "negative-probes.json"],
                "notes": ["fixture"],
                "upstream_challenges": [{"target": "fixture", "concern": "checked", "disposition": "accepted", "reason": "fixture"}],
                "accepted_upstream_assumptions": [],
                "rejected_upstream_assumptions": [],
            })
            if not role_completion_ready(project, evidence, "tester"):
                failures.append("tester completed 夹具没有被判定为角色完成")
            if role_completion_ready(project, evidence, "tester", min_role_artifact_mtime=time.time() + 60):
                failures.append("角色完成谓词不应允许旧 role-artifact 短路新一轮角色执行")
            current_source = pathlib.Path(__file__).read_text(encoding="utf-8")
            if CODEX_PROJECT_TRUST_MODE == "persist":
                failures.append("项目级 trust 默认不得持久写入 Codex config；必须优先使用单次 -c 覆盖，避免 E2E 污染用户全局配置")
            if "prepare_isolated_codex_home" not in current_source or "CODEX_HOME" not in current_source:
                failures.append("E2E 必须准备隔离 Codex Home，复制认证但不污染用户全局 config")
            isolated_mcp_contract = codex_mcp_isolation_contract("isolated_home")
            if isolated_mcp_contract.get("ok") is not True or isolated_mcp_contract.get("argv"):
                failures.append("isolated_home 模式下 codex_mcp_isolation_argv 必须返回空列表，不能向干净 Codex config 注入 MCP 覆盖")
            non_isolated_mcp_contract = codex_mcp_isolation_contract("command_override")
            if CODEX_DISABLED_MCP_SERVERS and not non_isolated_mcp_contract.get("argv"):
                failures.append("非 isolated_home 模式必须保留 MCP 禁用覆盖，避免用户全局 MCP 噪音影响验收")
            isolated_home_source = inspect.getsource(prepare_isolated_codex_home)
            if "mcp_servers" in isolated_home_source:
                failures.append("隔离 Codex Home 最小 config 模板不得包含 mcp_servers 条目")
            carrier_probe_source = inspect.getsource(carrier_probe)
            role_pipeline_source = inspect.getsource(run_loom_role_pipeline)
            if "*codex_project_trust_argv(project)" not in carrier_probe_source:
                failures.append("carrier_probe 必须携带项目级 trust 覆盖，否则探针不能证明项目级 hooks 真实可用")
            if "env_overrides=child_env" not in carrier_probe_source:
                failures.append("carrier_probe 必须在隔离 Codex Home 中运行子 Codex，避免污染用户全局配置")
            if "env_overrides=child_env" not in role_pipeline_source:
                failures.append("Loom 角色管线必须在隔离 Codex Home 中运行子 Codex，避免污染用户全局配置")
            if "codex_mcp_isolation_contract" not in carrier_probe_source:
                failures.append("carrier_probe 必须运行时检查 MCP 隔离契约，防止隔离模式重新注入 MCP 覆盖")
            if "codex_mcp_isolation_contract" not in role_pipeline_source:
                failures.append("Loom 角色管线必须运行时检查 MCP 隔离契约，防止角色执行复发配置错误")
            if "user_codex_home_guard" not in carrier_probe_source or "compare_user_codex_home_state" not in carrier_probe_source:
                failures.append("carrier_probe 必须记录用户真实 Codex Home 的 config/auth/logs 前后状态，证明不污染全局配置")
            if '"exec"' not in carrier_probe_source:
                failures.append("carrier_probe 必须使用 codex exec 非交互入口，贴合 Loom 角色真实执行方式")
            if "--no-alt-screen" in carrier_probe_source:
                failures.append("carrier_probe 使用 codex exec 时不得携带 --no-alt-screen")
            if "--output-last-message" not in carrier_probe_source:
                failures.append("carrier_probe 必须写 output-last-message，确保承载探针消息证据可回收")
            if '".codex" / "config.toml"' not in carrier_probe_source or "hooks = true" not in carrier_probe_source:
                failures.append("carrier_probe 必须生成最小 .codex/config.toml 项目配置层，否则 Codex CLI 可能不加载项目级 hooks")
            if "carrier-shell-marker.txt" not in carrier_probe_source or "completion_files=[marker_path]" not in carrier_probe_source:
                failures.append("carrier_probe 必须要求子 Codex 产生真实文件副作用，不能只凭口头 carrier-probe-ok 判断通过")
            if "最终只回答 carrier-probe-ok" in carrier_probe_source:
                failures.append("carrier_probe 提示词不得直接包含完成标记，否则会被终端回显误判为完成")
            if "finally:" not in carrier_probe_source or "cleanup_marker()" not in carrier_probe_source or "marker_cleanup_error" not in carrier_probe_source:
                failures.append("carrier_probe 必须用 finally 清理 marker，并把清理失败写入结果")
            if "TEST_INJECT_CARRIER_MARKER_CLEANUP_FAILURE" not in carrier_probe_source or "injected marker cleanup failure" not in carrier_probe_source:
                failures.append("carrier_probe 必须保留 marker 清理失败注入路径，用于真实负向验收")
            if 'if result["ok"]:\n            break' in carrier_probe_source:
                failures.append("carrier_probe 不得在命令 ok 但 Hook 缺失时提前停止重试")
            carrier_decision_source = inspect.getsource(carrier_probe_attempt_decision)
            if "marker_content_mismatch" not in carrier_decision_source or "hook_events_missing" not in carrier_decision_source:
                failures.append("carrier_probe 必须区分 marker 缺失/内容错误和 Hook 缺失等失败原因")
            carrier_final_decision_source = inspect.getsource(carrier_probe_final_decision)
            if "marker_cleanup_failed" not in carrier_final_decision_source or "marker_cleanup_error is None" not in carrier_final_decision_source:
                failures.append("carrier_probe 最终判定必须把 marker_cleanup_error 纳入 ok 计算")
            if "*codex_mcp_isolation_argv()" not in carrier_probe_source:
                failures.append("carrier_probe 必须隔离用户全局 MCP 噪音，避免外部登录态影响项目级 Hook 验收")
            carrier_negative_cases = [
                ("命令成功但没有标记文件", True, False, None, [], "marker_missing"),
                ("命令成功但标记内容错误", True, True, "口头成功", [], "marker_content_mismatch"),
                ("命令成功且标记正确但 Hook 缺失", True, True, "carrier-shell-ok", ["PreToolUse"], "hook_events_missing"),
                ("命令成功且标记正确但 Hook 缺失输入为 None", True, True, "carrier-shell-ok", None, "hook_events_missing"),
                ("命令失败但标记和 Hook 看似正常", False, True, "carrier-shell-ok", [], "command_failed"),
            ]
            for case_name, command_ok, marker_exists, probe_marker_text, probe_missing, expected_reason in carrier_negative_cases:
                decision = carrier_probe_attempt_decision(
                    command_ok=command_ok,
                    marker_exists=marker_exists,
                    marker_text=probe_marker_text,
                    missing_events=probe_missing,
                )
                if decision["ok"] or expected_reason not in decision["failure_reasons"]:
                    failures.append(f"carrier_probe 负向判定失效：{case_name}")
            positive_decision = carrier_probe_attempt_decision(
                command_ok=True,
                marker_exists=True,
                marker_text="carrier-shell-ok",
                missing_events=[],
            )
            if not positive_decision["ok"] or positive_decision["failure_reasons"]:
                failures.append("carrier_probe 正向判定失效：命令成功、标记正确、Hook 完整时应通过")
            positive_newline_decision = carrier_probe_attempt_decision(
                command_ok=True,
                marker_exists=True,
                marker_text="carrier-shell-ok\n",
                missing_events=[],
            )
            if not positive_newline_decision["ok"] or positive_newline_decision["failure_reasons"]:
                failures.append("carrier_probe 正向判定失效：标记文件只有行尾换行时应通过")
            cleanup_failed_decision = carrier_probe_final_decision(
                command_ok=True,
                marker_exists=True,
                marker_text="carrier-shell-ok",
                missing_events=[],
                marker_cleanup_error="injected marker cleanup failure",
            )
            if cleanup_failed_decision["ok"] or "marker_cleanup_failed" not in cleanup_failed_decision["failure_reasons"]:
                failures.append("carrier_probe 最终判定没有在 marker 清理失败时翻转为失败")
            runner_source = inspect.getsource(run_command_pty)
            for required_marker in ["trust_prompt_confirmed", "terminal_query_responses", "keyboard_protocol", "TERM", "xterm-256color"]:
                if required_marker not in runner_source:
                    failures.append(f"PTY 承载器缺少 {required_marker} 防护，可能复发交互式 Codex 卡死")
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
            for required_feature in CODEX_ROLE_EXTRA_DISABLED_FEATURES:
                if ["--disable", required_feature] not in [
                    developer_argv[index:index + 2]
                    for index in range(0, len(developer_argv) - 1)
                ]:
                    failures.append(f"developer Codex CLI argv 没有禁用 {required_feature}")
            for mcp_arg in codex_mcp_isolation_argv():
                if mcp_arg not in developer_argv:
                    failures.append(f"developer Codex CLI argv 缺少 MCP 隔离参数：{mcp_arg}")
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
            trpg_only_contracts = build_requirements("基于旧 trpg-server 与 trpg-web 项目的方向，推演一个简化版 TRPG 活动组织平台").get("domain_contracts")
            if not isinstance(trpg_only_contracts, list) or not any(item.get("id") == "signup-intent-data-contract" for item in trpg_only_contracts if isinstance(item, dict)):
                failures.append("TRPG 项目方向没有自动触发报名意向契约")
            if not isinstance(trpg_only_contracts, list) or not any(item.get("id") == "character-player-relation-contract" for item in trpg_only_contracts if isinstance(item, dict)):
                failures.append("TRPG 项目方向没有自动触发角色玩家关系契约")
            if not isinstance(signup_contracts, list) or not any(item.get("id") == "signup-intent-data-contract" for item in signup_contracts if isinstance(item, dict)):
                failures.append("包含报名意向的需求没有生成 signup-intent-data-contract")
            if not isinstance(signup_contracts, list) or not any(item.get("id") == "character-player-relation-contract" for item in signup_contracts if isinstance(item, dict)):
                failures.append("同时包含角色和玩家的需求没有生成 character-player-relation-contract")
            if "domain_contracts" not in signup_acceptance or not any("signup-intent-data-contract" in item for item in signup_acceptance.get("criteria", []) if isinstance(item, str)):
                failures.append("包含报名意向的验收标准没有承接 signup-intent-data-contract")
            if "domain_contracts" not in signup_acceptance or not any("character-player-relation-contract" in item and "非零退出" in item for item in signup_acceptance.get("criteria", []) if isinstance(item, str)):
                failures.append("角色玩家关系验收标准没有要求破坏 playerId 后验证命令非零退出")
            architect_prompt = build_role_prompt(project, evidence, "architect", signup_direction)
            signup_developer_prompt = build_role_prompt(project, evidence, "developer", signup_direction)
            signup_tester_prompt = build_role_prompt(project, evidence, "tester", signup_direction)
            signup_reviewer_prompt = build_role_prompt(project, evidence, "reviewer", signup_direction)
            if "signup-intent-data-contract" not in architect_prompt or "数据模型" not in architect_prompt:
                failures.append("architect 提示词没有要求把报名意向契约落入数据模型")
            if "character-player-relation-contract" not in architect_prompt or "真实引用关系" not in architect_prompt or "不能只靠 playerName" not in architect_prompt:
                failures.append("architect 提示词没有要求角色玩家契约落入真实引用数据模型")
            if "signup-intent-data-contract" not in signup_developer_prompt or "逐记录检查" not in signup_developer_prompt or "不能只检查全局至少有一条报名" not in signup_developer_prompt:
                failures.append("developer 提示词没有要求逐记录实现并验证报名意向契约")
            if "character-player-relation-contract" not in signup_developer_prompt or "playerId 被改成不存在的玩家 id" not in signup_developer_prompt or "验证命令也必须非零退出" not in signup_developer_prompt:
                failures.append("developer 提示词没有要求验证脚本拒绝损坏的角色玩家引用")
            if "不得把 README 或界面文案里的 file://" not in signup_developer_prompt or "普通 JS 注释中的 //" not in signup_developer_prompt:
                failures.append("developer 提示词没有禁止远端依赖检查误伤 file:// 或普通 // 文本")
            if "signups 数组" not in signup_tester_prompt or "signupIntent 字段" not in signup_tester_prompt or "项目验证命令非零退出" not in signup_tester_prompt or "只检查全局至少有一条报名" not in signup_tester_prompt:
                failures.append("tester 提示词没有要求逐记录验证报名意向契约")
            if "character-player-relation-contract" not in signup_tester_prompt or "不存在的玩家 id" not in signup_tester_prompt or "test-results.json 和 negative-probes.json 必须标记 failed" not in signup_tester_prompt:
                failures.append("tester 提示词没有要求角色玩家负向探针失败时标记测试失败")
            if "domain_contracts" not in signup_reviewer_prompt or "blocking_findings" not in signup_reviewer_prompt:
                failures.append("reviewer 提示词没有要求审核领域数据契约")
            if "逐活动、逐场次或逐事件检查非空报名意向" not in signup_reviewer_prompt or "清空单个活动 signups 和 signupIntent" not in signup_reviewer_prompt:
                failures.append("reviewer 提示词没有要求审核报名意向逐记录负向验证证据")
            if "开发验证脚本是否检查 playerId 命中真实玩家" not in signup_reviewer_prompt or "tester 是否做了破坏 playerId" not in signup_reviewer_prompt:
                failures.append("reviewer 提示词没有要求审核角色玩家负向验证证据")
            retry_developer_prompt = role_retry_prompt(developer_prompt, 2)
            if "【重试约束】" not in retry_developer_prompt or "不要读取或执行需要人工批准的技能流程" not in retry_developer_prompt:
                failures.append("developer 重试提示没有压制交互式设计技能误触发")
            feedback_fixture = evidence / "developer-repair-feedback" / "fixture.json"
            feedback_prompt = build_role_prompt(project, evidence, "developer", "自检方向", feedback_packet=feedback_fixture)
            if "额外修复反馈包" not in feedback_prompt or "降低错误为 warning" not in feedback_prompt:
                failures.append("developer 修复反馈提示没有禁止降低验收严重度")
            if "signup-empty" not in critical_categories_from_text("session signups 为空；warning only"):
                failures.append("关键 warning 分类没有识别 signups 空数组")
            if "remote-dependency" not in critical_categories_from_text("入口包含 https://cdn.example/asset.js 远端依赖"):
                failures.append("关键 warning 分类没有识别远端依赖")
            first_repair = developer_repair_decision(
                source="tester",
                failure_set={"tester:probe:signup:signup-empty"},
                previous_failure_set=None,
                resolved_failures=set(),
                repair_rounds_used=0,
            )
            if first_repair.get("schedule_repair") is not True:
                failures.append("首次 tester 失败没有安排有界 developer 修复回流")
            no_progress_repair = developer_repair_decision(
                source="tester",
                failure_set={"tester:probe:signup:signup-empty"},
                previous_failure_set={"tester:probe:signup:signup-empty"},
                resolved_failures=set(),
                repair_rounds_used=1,
            )
            if no_progress_repair.get("schedule_repair") is True or no_progress_repair.get("reason") != "no-failure-set-progress":
                failures.append("developer 修复回流没有在失败集无进展时停止")
            regression_repair = developer_repair_decision(
                source="developer-readiness",
                failure_set={"developer-readiness:remote-dependency:error"},
                previous_failure_set={"tester:probe:signup:signup-empty"},
                resolved_failures={"developer-readiness:remote-dependency:error"},
                repair_rounds_used=1,
            )
            if regression_repair.get("schedule_repair") is True or regression_repair.get("reason") != "previously-fixed-failure-reappeared":
                failures.append("developer 修复回流没有在已解决失败复发时停止")
            loop_exhausted = developer_repair_decision(
                source="tester",
                failure_set={"tester:positive:validate"},
                previous_failure_set=None,
                resolved_failures=set(),
                repair_rounds_used=LOOM_DEVELOPER_REPAIR_MAX_ROUNDS,
            )
            if loop_exhausted.get("schedule_repair") is True or loop_exhausted.get("reason") != "repair-loop-exhausted":
                failures.append("developer 修复回流没有在轮次耗尽时停止")
            feedback_path = write_developer_repair_feedback(
                evidence,
                repair_round=99,
                source="tester",
                failure_set={"tester:probe:signup:signup-empty"},
                developer_gate=None,
                tester_receipt={"ok": False, "failures": ["fixture failure"]},
                decision=first_repair,
            )
            feedback_payload = load_optional_json(feedback_path)
            if not feedback_payload or feedback_payload.get("lossless_rule") is None:
                failures.append("developer 修复反馈包缺少 lossless_rule")
            if "suggested_fix" in json.dumps(feedback_payload, ensure_ascii=False):
                failures.append("developer 修复反馈包不得包含 suggested_fix，避免 tester 间接修复")
            role_pipeline_source = inspect.getsource(run_loom_role_pipeline)
            for required_marker in [
                "run_developer_readiness_gate",
                "write_developer_repair_feedback",
                "developer_repair_decision",
                "role_results.pop(\"tester\", None)",
                "developer-repair-loop.json",
            ]:
                if required_marker not in role_pipeline_source:
                    failures.append(f"Loom 修复回流缺少硬护栏：{required_marker}")
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
            if "最多一个正向验证命令" not in tester_prompt or "最多两个负向或静态探针" not in tester_prompt:
                failures.append("tester 提示词没有限制验证动作数量，容易因过度探索超时")
            if "每执行完一个验证动作，立即更新对应 JSON" not in tester_prompt:
                failures.append("tester 提示词没有要求验证后立即更新结构化证据")
            if "Node 标准库脚本" not in tester_prompt or "未引用的 shell 通配符" not in tester_prompt:
                failures.append("tester 提示词没有禁止危险 shell 通配符负向探针")
            if "signups 数组" not in tester_prompt or "signupIntent 字段" not in tester_prompt or "signups" not in tester_prompt or "只检查全局至少有一条报名" not in tester_prompt:
                failures.append("tester 提示词没有明确报名意向的非空结构化探针规则")
            if "character-player-relation-contract" not in tester_prompt or "character.playerId" not in tester_prompt or "不存在的玩家 id" not in tester_prompt:
                failures.append("tester 提示词没有明确角色玩家关系负向探针规则")
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
            readme_path = project / "README.md"
            validate_data_js = project / "scripts" / "validate-data.js"
            validate_data_js.write_text("process.exit(0)\n", encoding="utf-8")
            readme_path.write_text("## 验证\n\n```sh\nnode scripts/validate-data.js\n```\n", encoding="utf-8")
            detected_argv, detected_source = detect_validation_command(project)
            if detected_argv != ["node", "scripts/validate-data.js"] or detected_source != "README.md command: node scripts/validate-data.js":
                failures.append("运行器没有识别 README 中明确给出的本地验证命令")
            readme_path.unlink()
            validate_data_js.unlink()
            root_validate = project / "validate.js"
            root_validate.write_text("console.log('root validate ok')\n", encoding="utf-8")
            detected_argv, detected_source = detect_validation_command(project)
            if detected_argv != ["node", "validate.js"] or detected_source != "validate.js":
                failures.append("运行器没有识别根目录 validate.js 作为本地验证命令")
            root_validate.unlink()
            src_detect_dir = project / "src"
            src_detect_dir.mkdir(exist_ok=True)
            src_detect_validate = src_detect_dir / "validate.js"
            src_detect_validate.write_text("console.log('src validate ok')\n", encoding="utf-8")
            detected_argv, detected_source = detect_validation_command(project)
            if detected_argv != ["node", "src/validate.js"] or detected_source != "src/validate.js":
                failures.append("运行器没有识别 src/validate.js 作为本地验证命令")
            src_detect_validate.unlink()
            validate_data_js.write_text("process.exit(0)\n", encoding="utf-8")
            readme_path.write_text("## 验证\n\n```sh\nnode scripts/validate-data.js data/sample-data.json\n```\n", encoding="utf-8")
            detected_argv, detected_source = detect_validation_command(project)
            if detected_argv != ["node", "scripts/validate-data.js", "data/sample-data.json"] or detected_source != "README.md command: node scripts/validate-data.js data/sample-data.json":
                failures.append("运行器没有保留 README 验证命令中的安全本地参数")
            readme_path.unlink()
            validate_data_js.unlink()
            serve_js = project / "scripts" / "serve.js"
            serve_js.write_text("setInterval(() => {}, 1000)\n", encoding="utf-8")
            readme_path.write_text("## 启动\n\n```sh\nnode scripts/serve.js\n```\n", encoding="utf-8")
            detected_argv, detected_source = detect_validation_command(project)
            if detected_argv is not None:
                failures.append("运行器不应把 README 中的长驻 serve 命令识别为验证命令")
            serve_js.unlink()
            readme_path.write_text("## 验证\n\n```sh\nnode scripts/validate-data.js\n```\n", encoding="utf-8")
            app_entrypoint = project / "app" / "index.html"
            app_entrypoint.parent.mkdir(exist_ok=True)
            app_entrypoint.write_text("<!doctype html><main>自检入口</main>\n", encoding="utf-8")
            detected_entrypoint, detected_entrypoint_rel, checked_entrypoints = detect_browser_entrypoint(project)
            if detected_entrypoint != app_entrypoint or detected_entrypoint_rel != "app/index.html":
                failures.append(f"运行器没有识别 app/index.html 作为合法浏览器入口：{checked_entrypoints}")
            app_entrypoint.unlink()
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
                    },
                    {
                        "id": "self-check-activity-2",
                        "title": "自检活动二",
                        "players": [
                            {
                                "id": "player-2",
                                "name": "测试玩家二"
                            }
                        ],
                        "characters": [
                            {
                                "id": "character-2",
                                "name": "测试角色二",
                                "playerId": "player-2"
                            }
                        ],
                        "signupIntent": "第二条活动也需要报名者",
                        "signups": [
                            {
                                "playerName": "测试玩家二",
                                "characterName": "测试角色二",
                                "status": "confirmed"
                            }
                        ]
                    }
                ]
            })
            validate_data_js.write_text(
                "const fs = require('fs');\n"
                "const data = JSON.parse(fs.readFileSync('data/activities.json', 'utf8'));\n"
                "for (const [index, activity] of data.activities.entries()) {\n"
                "  if (!activity.signupIntent || !Array.isArray(activity.signups) || activity.signups.length === 0) {\n"
                "    console.error(`signup-intent-data-contract failed at ${index}`);\n"
                "    process.exit(2);\n"
                "  }\n"
                "  const playerIds = new Set((activity.players || []).map((player) => player.id));\n"
                "  if (!Array.isArray(activity.characters) || activity.characters.some((character) => !playerIds.has(character.playerId))) {\n"
                "    console.error(`character-player-relation-contract failed at ${index}`);\n"
                "    process.exit(3);\n"
                "  }\n"
                "}\n"
                "console.log(JSON.stringify({ok: true}));\n",
                encoding="utf-8",
            )
            negative_probe = run_runner_negative_contract_probe(project, evidence)
            if negative_probe.get("ok") is not True:
                failures.append(f"运行器负向契约探针不能处理 data/activities.json：{negative_probe.get('failures')}")
            if negative_probe.get("data_path") != "data/activities.json" or negative_probe.get("list_key") != "activities":
                failures.append("运行器负向契约探针没有记录真实 activities 数据路径和列表字段")
            if not isinstance(negative_probe.get("probe_depth"), dict) or negative_probe["probe_depth"].get("targeted_non_first_record") is not True:
                failures.append("运行器报名负向契约探针没有优先命中非首条活动记录")
            character_probe = run_runner_character_player_contract_probe(project, evidence)
            if character_probe.get("ok") is not True:
                failures.append(f"运行器角色玩家负向契约探针不能处理 data/activities.json：{character_probe.get('failures')}")
            if character_probe.get("data_path") != "data/activities.json" or character_probe.get("list_key") != "activities":
                failures.append("运行器角色玩家负向契约探针没有记录真实 activities 数据路径和列表字段")
            if not isinstance(character_probe.get("probe_depth"), dict) or character_probe["probe_depth"].get("targeted_non_first_event") is not True:
                failures.append("运行器角色玩家负向契约探针没有优先命中非首条活动记录")
            (data_dir / "activities.json").unlink()
            src_dir = project / "src"
            src_dir.mkdir(exist_ok=True)
            src_data_js = src_dir / "data.js"
            js_payload = {
                "activities": [
                    {
                        "id": "self-check-js-activity",
                        "title": "JS 自检活动",
                        "players": [{"id": "player-js-1", "name": "JS 测试玩家"}],
                        "characters": [{"id": "character-js-1", "name": "JS 测试角色", "playerId": "player-js-1"}],
                        "signupIntent": "JS 活动需要报名者",
                        "signups": [{"playerName": "JS 测试玩家", "characterName": "JS 测试角色", "status": "confirmed"}],
                    },
                    {
                        "id": "self-check-js-activity-2",
                        "title": "JS 自检活动二",
                        "players": [{"id": "player-js-2", "name": "JS 测试玩家二"}],
                        "characters": [{"id": "character-js-2", "name": "JS 测试角色二", "playerId": "player-js-2"}],
                        "signupIntent": "JS 第二条活动也需要报名者",
                        "signups": [{"playerName": "JS 测试玩家二", "characterName": "JS 测试角色二", "status": "confirmed"}],
                    },
                ]
            }
            write_structured_data_probe_payload(src_data_js, js_payload)
            validate_data_js.write_text(
                "const data = require('../src/data.js');\n"
                "for (const [index, activity] of data.activities.entries()) {\n"
                "  if (!activity.signupIntent || !Array.isArray(activity.signups) || activity.signups.length === 0) {\n"
                "    console.error(`signup-intent-data-contract failed at ${index}`);\n"
                "    process.exit(2);\n"
                "  }\n"
                "  const playerIds = new Set((activity.players || []).map((player) => player.id));\n"
                "  if (!Array.isArray(activity.characters) || activity.characters.some((character) => !playerIds.has(character.playerId))) {\n"
                "    console.error(`character-player-relation-contract failed at ${index}`);\n"
                "    process.exit(3);\n"
                "  }\n"
                "}\n"
                "console.log(JSON.stringify({ok: true, source: 'src/data.js'}));\n",
                encoding="utf-8",
            )
            js_negative_probe = run_runner_negative_contract_probe(project, evidence)
            if js_negative_probe.get("ok") is not True:
                failures.append(f"运行器报名负向契约探针不能处理 src/data.js：{js_negative_probe.get('failures')}")
            if js_negative_probe.get("data_path") != "src/data.js" or js_negative_probe.get("list_key") != "activities":
                failures.append("运行器报名负向契约探针没有记录 JS 数据模块路径和列表字段")
            if not isinstance(js_negative_probe.get("probe_depth"), dict) or js_negative_probe["probe_depth"].get("targeted_non_first_record") is not True:
                failures.append("运行器报名负向契约探针没有在 JS 数据模块中优先命中非首条活动记录")
            js_character_probe = run_runner_character_player_contract_probe(project, evidence)
            if js_character_probe.get("ok") is not True:
                failures.append(f"运行器角色玩家负向契约探针不能处理 src/data.js：{js_character_probe.get('failures')}")
            if js_character_probe.get("data_path") != "src/data.js" or js_character_probe.get("list_key") != "activities":
                failures.append("运行器角色玩家负向契约探针没有记录 JS 数据模块路径和列表字段")
            if not isinstance(js_character_probe.get("probe_depth"), dict) or js_character_probe["probe_depth"].get("targeted_non_first_event") is not True:
                failures.append("运行器角色玩家负向契约探针没有在 JS 数据模块中优先命中非首条活动记录")
            src_data_js.unlink()
            app_js = project / "app.js"
            app_js.write_text(
                "(function (root) {\n"
                "  const TRPG_ACTIVITY_DATA = "
                + json.dumps(js_payload, ensure_ascii=False, indent=2)
                + ";\n"
                "  if (typeof module !== 'undefined' && module.exports) {\n"
                "    module.exports = { TRPG_ACTIVITY_DATA };\n"
                "  }\n"
                "  root.__redcapSelfCheckData = TRPG_ACTIVITY_DATA;\n"
                "})(typeof window !== 'undefined' ? window : globalThis);\n",
                encoding="utf-8",
            )
            validate_data_js.write_text(
                "const { TRPG_ACTIVITY_DATA } = require('../app.js');\n"
                "const data = TRPG_ACTIVITY_DATA;\n"
                "for (const [index, activity] of data.activities.entries()) {\n"
                "  if (!activity.signupIntent || !Array.isArray(activity.signups) || activity.signups.length === 0) {\n"
                "    console.error(`signup-intent-data-contract failed at ${index}`);\n"
                "    process.exit(2);\n"
                "  }\n"
                "  const playerIds = new Set((activity.players || []).map((player) => player.id));\n"
                "  if (!Array.isArray(activity.characters) || activity.characters.some((character) => !playerIds.has(character.playerId))) {\n"
                "    console.error(`character-player-relation-contract failed at ${index}`);\n"
                "    process.exit(3);\n"
                "  }\n"
                "}\n"
                "console.log(JSON.stringify({ok: true, source: 'app.js wrapped module export'}));\n",
                encoding="utf-8",
            )
            wrapped_negative_probe = run_runner_negative_contract_probe(project, evidence)
            if wrapped_negative_probe.get("ok") is not True:
                failures.append(f"运行器报名负向契约探针不能处理 app.js 包装层模块导出：{wrapped_negative_probe.get('failures')}")
            if wrapped_negative_probe.get("data_path") != "app.js" or wrapped_negative_probe.get("list_key") != "TRPG_ACTIVITY_DATA.activities":
                failures.append(f"运行器报名负向契约探针没有记录 app.js 包装层数据路径：{wrapped_negative_probe}")
            wrapped_character_probe = run_runner_character_player_contract_probe(project, evidence)
            if wrapped_character_probe.get("ok") is not True:
                failures.append(f"运行器角色玩家负向契约探针不能处理 app.js 包装层模块导出：{wrapped_character_probe.get('failures')}")
            if wrapped_character_probe.get("data_path") != "app.js" or wrapped_character_probe.get("list_key") != "TRPG_ACTIVITY_DATA.activities":
                failures.append(f"运行器角色玩家负向契约探针没有记录 app.js 包装层数据路径：{wrapped_character_probe}")
            app_js.unlink()
            src_sample_data_js = src_dir / "sample-data.js"
            write_structured_data_probe_payload(src_sample_data_js, js_payload)
            validate_data_js.write_text(
                "const data = require('../src/sample-data.js');\n"
                "for (const [index, activity] of data.activities.entries()) {\n"
                "  if (!activity.signupIntent || !Array.isArray(activity.signups) || activity.signups.length === 0) {\n"
                "    console.error(`signup-intent-data-contract failed at ${index}`);\n"
                "    process.exit(2);\n"
                "  }\n"
                "  const playerIds = new Set((activity.players || []).map((player) => player.id));\n"
                "  if (!Array.isArray(activity.characters) || activity.characters.some((character) => !playerIds.has(character.playerId))) {\n"
                "    console.error(`character-player-relation-contract failed at ${index}`);\n"
                "    process.exit(3);\n"
                "  }\n"
                "}\n"
                "console.log(JSON.stringify({ok: true, source: 'src/sample-data.js'}));\n",
                encoding="utf-8",
            )
            sample_js_negative_probe = run_runner_negative_contract_probe(project, evidence)
            if sample_js_negative_probe.get("ok") is not True:
                failures.append(f"运行器报名负向契约探针不能处理 src/sample-data.js：{sample_js_negative_probe.get('failures')}")
            if sample_js_negative_probe.get("data_path") != "src/sample-data.js" or sample_js_negative_probe.get("list_key") != "activities":
                failures.append("运行器报名负向契约探针没有记录 src/sample-data.js 数据路径和列表字段")
            sample_js_character_probe = run_runner_character_player_contract_probe(project, evidence)
            if sample_js_character_probe.get("ok") is not True:
                failures.append(f"运行器角色玩家负向契约探针不能处理 src/sample-data.js：{sample_js_character_probe.get('failures')}")
            if sample_js_character_probe.get("data_path") != "src/sample-data.js" or sample_js_character_probe.get("list_key") != "activities":
                failures.append("运行器角色玩家负向契约探针没有记录 src/sample-data.js 数据路径和列表字段")
            src_sample_data_js.unlink()
            app_dir = project / "app"
            app_dir.mkdir(exist_ok=True)
            embedded_data_js = app_dir / "embedded-data.js"
            embedded_payload = {
                "activities": [
                    {
                        "id": "self-check-app-activity",
                        "title": "App 自检活动",
                        "sessions": [
                            {
                                "id": "session-app-1",
                                "title": "App 自检场次一",
                                "players": [{"id": "player-app-1", "name": "App 测试玩家"}],
                                "characters": [{"id": "character-app-1", "name": "App 测试角色", "playerId": "player-app-1"}],
                                "signupIntent": "App 场次需要报名者",
                                "signups": [{"playerName": "App 测试玩家", "characterName": "App 测试角色", "status": "confirmed"}],
                            }
                        ],
                    },
                    {
                        "id": "self-check-app-activity-2",
                        "title": "App 自检活动二",
                        "sessions": [
                            {
                                "id": "session-app-2",
                                "title": "App 自检场次二",
                                "players": [{"id": "player-app-2", "name": "App 测试玩家二"}],
                                "characters": [{"id": "character-app-2", "name": "App 测试角色二", "playerId": "player-app-2"}],
                                "signupIntent": "App 第二条场次也需要报名者",
                                "signups": [{"playerName": "App 测试玩家二", "characterName": "App 测试角色二", "status": "confirmed"}],
                            }
                        ],
                    },
                ]
            }
            write_structured_data_probe_payload(embedded_data_js, embedded_payload)
            validate_data_js.write_text(
                "const data = require('../app/embedded-data.js');\n"
                "for (const [activityIndex, activity] of data.activities.entries()) {\n"
                "  const sessions = activity.sessions || [];\n"
                "  for (const [sessionIndex, session] of sessions.entries()) {\n"
                "    if (!session.signupIntent || !Array.isArray(session.signups) || session.signups.length === 0) {\n"
                "      console.error(`signup-intent-data-contract failed at ${activityIndex}.${sessionIndex}`);\n"
                "      process.exit(2);\n"
                "    }\n"
                "    const playerIds = new Set((session.players || []).map((player) => player.id));\n"
                "    if (!Array.isArray(session.characters) || session.characters.some((character) => !playerIds.has(character.playerId))) {\n"
                "      console.error(`character-player-relation-contract failed at ${activityIndex}.${sessionIndex}`);\n"
                "      process.exit(3);\n"
                "    }\n"
                "  }\n"
                "}\n"
                "console.log(JSON.stringify({ok: true, source: 'app/embedded-data.js'}));\n",
                encoding="utf-8",
            )
            embedded_negative_probe = run_runner_negative_contract_probe(project, evidence)
            if embedded_negative_probe.get("ok") is not True:
                failures.append(f"运行器报名负向契约探针不能处理 app/embedded-data.js 嵌套场次数据：{embedded_negative_probe.get('failures')}")
            if embedded_negative_probe.get("data_path") != "app/embedded-data.js" or ".sessions" not in str(embedded_negative_probe.get("list_key")):
                failures.append(f"运行器报名负向契约探针没有记录 app/embedded-data.js 的嵌套场次路径：{embedded_negative_probe}")
            if not isinstance(embedded_negative_probe.get("probe_depth"), dict) or embedded_negative_probe["probe_depth"].get("targeted_non_first_path") is not True:
                failures.append("运行器报名负向契约探针没有在 app/embedded-data.js 中优先命中非首条嵌套路径")
            embedded_character_probe = run_runner_character_player_contract_probe(project, evidence)
            if embedded_character_probe.get("ok") is not True:
                failures.append(f"运行器角色玩家负向契约探针不能处理 app/embedded-data.js：{embedded_character_probe.get('failures')}")
            if embedded_character_probe.get("data_path") != "app/embedded-data.js" or ".sessions" not in str(embedded_character_probe.get("list_key")):
                failures.append(f"运行器角色玩家负向契约探针没有记录 app/embedded-data.js 的嵌套场次数据路径：{embedded_character_probe}")
            embedded_data_js.unlink()
            html_index = project / "index.html"
            html_payload = copy.deepcopy(embedded_payload)
            html_index.write_text(
                "<!doctype html>\n"
                "<html lang=\"zh-CN\">\n"
                "<head><meta charset=\"utf-8\"><title>HTML 内嵌数据自检</title></head>\n"
                "<body>\n"
                "<main id=\"app\"></main>\n"
                "<script id=\"trpg-activity-data\" type=\"application/json\">\n"
                + json.dumps(html_payload, ensure_ascii=False, indent=2)
                + "\n</script>\n"
                "</body>\n"
                "</html>\n",
                encoding="utf-8",
            )
            validate_data_js.write_text(
                "const fs = require('fs');\n"
                "const html = fs.readFileSync('index.html', 'utf8');\n"
                "const match = html.match(/<script\\s+id=\"trpg-activity-data\"\\s+type=\"application\\/json\">\\s*([\\s\\S]*?)\\s*<\\/script>/);\n"
                "if (!match) process.exit(10);\n"
                "const data = JSON.parse(match[1]);\n"
                "for (const [activityIndex, activity] of data.activities.entries()) {\n"
                "  const sessions = activity.sessions || [];\n"
                "  for (const [sessionIndex, session] of sessions.entries()) {\n"
                "    if (!session.signupIntent || !Array.isArray(session.signups) || session.signups.length === 0) {\n"
                "      console.error(`signup-intent-data-contract failed at ${activityIndex}.${sessionIndex}`);\n"
                "      process.exit(2);\n"
                "    }\n"
                "    const playerIds = new Set((session.players || []).map((player) => player.id));\n"
                "    if (!Array.isArray(session.characters) || session.characters.some((character) => !playerIds.has(character.playerId))) {\n"
                "      console.error(`character-player-relation-contract failed at ${activityIndex}.${sessionIndex}`);\n"
                "      process.exit(3);\n"
                "    }\n"
                "  }\n"
                "}\n"
                "console.log(JSON.stringify({ok: true, source: 'index.html'}));\n",
                encoding="utf-8",
            )
            html_negative_probe = run_runner_negative_contract_probe(project, evidence)
            if html_negative_probe.get("ok") is not True:
                failures.append(f"运行器报名负向契约探针不能处理 index.html 内嵌 JSON 数据：{html_negative_probe.get('failures')}")
            if html_negative_probe.get("data_path") != "index.html" or ".sessions" not in str(html_negative_probe.get("list_key")):
                failures.append(f"运行器报名负向契约探针没有记录 index.html 的嵌套场次路径：{html_negative_probe}")
            if not isinstance(html_negative_probe.get("probe_depth"), dict) or html_negative_probe["probe_depth"].get("targeted_non_first_path") is not True:
                failures.append("运行器报名负向契约探针没有在 index.html 内嵌数据中优先命中非首条嵌套路径")
            html_character_probe = run_runner_character_player_contract_probe(project, evidence)
            if html_character_probe.get("ok") is not True:
                failures.append(f"运行器角色玩家负向契约探针不能处理 index.html 内嵌 JSON 数据：{html_character_probe.get('failures')}")
            if html_character_probe.get("data_path") != "index.html" or ".sessions" not in str(html_character_probe.get("list_key")):
                failures.append(f"运行器角色玩家负向契约探针没有记录 index.html 的嵌套场次数据路径：{html_character_probe}")
            html_index.unlink()
            browser_global_js = data_dir / "campaigns.js"
            browser_global_js.write_text(
                "(function () { window.TRPG_CAMPAIGNS = "
                + json.dumps(js_payload["activities"], ensure_ascii=False, indent=2)
                + "; })();\n",
                encoding="utf-8",
            )
            validate_data_js.write_text(
                "const fs = require('fs');\n"
                "const vm = require('vm');\n"
                "const source = fs.readFileSync('data/campaigns.js', 'utf8');\n"
                "const sandbox = { window: {} };\n"
                "vm.createContext(sandbox);\n"
                "vm.runInContext(source, sandbox, { filename: 'data/campaigns.js' });\n"
                "const activities = sandbox.window.TRPG_CAMPAIGNS;\n"
                "if (!Array.isArray(activities)) process.exit(10);\n"
                "for (const [index, activity] of activities.entries()) {\n"
                "  if (!activity.signupIntent || !Array.isArray(activity.signups) || activity.signups.length === 0) {\n"
                "    console.error(`signup-intent-data-contract failed at ${index}`);\n"
                "    process.exit(2);\n"
                "  }\n"
                "  const playerIds = new Set((activity.players || []).map((player) => player.id));\n"
                "  if (!Array.isArray(activity.characters) || activity.characters.some((character) => !playerIds.has(character.playerId))) {\n"
                "    console.error(`character-player-relation-contract failed at ${index}`);\n"
                "    process.exit(3);\n"
                "  }\n"
                "}\n"
                "console.log(JSON.stringify({ok: true, source: 'data/campaigns.js'}));\n",
                encoding="utf-8",
            )
            global_negative_probe = run_runner_negative_contract_probe(project, evidence)
            if global_negative_probe.get("ok") is not True:
                failures.append(f"运行器报名负向契约探针不能处理 data/campaigns.js 浏览器全局数据：{global_negative_probe.get('failures')}")
            if global_negative_probe.get("data_path") != "data/campaigns.js" or global_negative_probe.get("list_key") != "$":
                failures.append("运行器报名负向契约探针没有记录浏览器全局数据路径和顶层数组字段")
            global_character_probe = run_runner_character_player_contract_probe(project, evidence)
            if global_character_probe.get("ok") is not True:
                failures.append(f"运行器角色玩家负向契约探针不能处理 data/campaigns.js 浏览器全局数据：{global_character_probe.get('failures')}")
            if global_character_probe.get("data_path") != "data/campaigns.js" or global_character_probe.get("list_key") != "$":
                failures.append("运行器角色玩家负向契约探针没有记录浏览器全局数据路径和顶层数组字段")
            browser_global_js.unlink()
            activity_global_js = data_dir / "sample-data.js"
            activity_global_js.write_text(
                "window.TRPG_ACTIVITY_DATA = "
                + json.dumps(js_payload, ensure_ascii=False, indent=2)
                + ";\n",
                encoding="utf-8",
            )
            validate_data_js.write_text(
                "const fs = require('fs');\n"
                "const vm = require('vm');\n"
                "const source = fs.readFileSync('data/sample-data.js', 'utf8');\n"
                "const sandbox = { window: {} };\n"
                "vm.createContext(sandbox);\n"
                "vm.runInContext(source, sandbox, { filename: 'data/sample-data.js' });\n"
                "const data = sandbox.window.TRPG_ACTIVITY_DATA;\n"
                "if (!data || !Array.isArray(data.activities)) process.exit(10);\n"
                "for (const [index, activity] of data.activities.entries()) {\n"
                "  if (!activity.signupIntent || !Array.isArray(activity.signups) || activity.signups.length === 0) {\n"
                "    console.error(`signup-intent-data-contract failed at ${index}`);\n"
                "    process.exit(2);\n"
                "  }\n"
                "  const playerIds = new Set((activity.players || []).map((player) => player.id));\n"
                "  if (!Array.isArray(activity.characters) || activity.characters.some((character) => !playerIds.has(character.playerId))) {\n"
                "    console.error(`character-player-relation-contract failed at ${index}`);\n"
                "    process.exit(3);\n"
                "  }\n"
                "}\n"
                "console.log(JSON.stringify({ok: true, source: 'data/sample-data.js'}));\n",
                encoding="utf-8",
            )
            activity_negative_probe = run_runner_negative_contract_probe(project, evidence)
            if activity_negative_probe.get("ok") is not True:
                failures.append(f"运行器报名负向契约探针不能处理 data/sample-data.js 浏览器全局对象：{activity_negative_probe.get('failures')}")
            if activity_negative_probe.get("data_path") != "data/sample-data.js" or activity_negative_probe.get("list_key") != "activities":
                failures.append("运行器报名负向契约探针没有记录 data/*.js 浏览器全局对象路径和列表字段")
            activity_character_probe = run_runner_character_player_contract_probe(project, evidence)
            if activity_character_probe.get("ok") is not True:
                failures.append(f"运行器角色玩家负向契约探针不能处理 data/sample-data.js 浏览器全局对象：{activity_character_probe.get('failures')}")
            if activity_character_probe.get("data_path") != "data/sample-data.js" or activity_character_probe.get("list_key") != "activities":
                failures.append("运行器角色玩家负向契约探针没有记录 data/*.js 浏览器全局对象路径和列表字段")
            sample_data_global_js = data_dir / "sample-data-global.js"
            sample_data_global_js.write_text(
                "window.TRPG_SAMPLE_DATA = "
                + json.dumps(js_payload, ensure_ascii=False, indent=2)
                + ";\n",
                encoding="utf-8",
            )
            validate_data_js.write_text(
                "const fs = require('fs');\n"
                "const vm = require('vm');\n"
                "const source = fs.readFileSync('data/sample-data-global.js', 'utf8');\n"
                "const sandbox = { window: {} };\n"
                "vm.createContext(sandbox);\n"
                "vm.runInContext(source, sandbox, { filename: 'data/sample-data-global.js' });\n"
                "const data = sandbox.window.TRPG_SAMPLE_DATA;\n"
                "if (!data || !Array.isArray(data.activities)) process.exit(10);\n"
                "for (const [index, activity] of data.activities.entries()) {\n"
                "  if (!activity.signupIntent || !Array.isArray(activity.signups) || activity.signups.length === 0) {\n"
                "    console.error(`signup-intent-data-contract failed at ${index}`);\n"
                "    process.exit(2);\n"
                "  }\n"
                "  const playerIds = new Set((activity.players || []).map((player) => player.id));\n"
                "  if (!Array.isArray(activity.characters) || activity.characters.some((character) => !playerIds.has(character.playerId))) {\n"
                "    console.error(`character-player-relation-contract failed at ${index}`);\n"
                "    process.exit(3);\n"
                "  }\n"
                "}\n"
                "console.log(JSON.stringify({ok: true, source: 'data/sample-data-global.js'}));\n",
                encoding="utf-8",
            )
            sample_global_negative_probe = run_runner_negative_contract_probe(project, evidence)
            if sample_global_negative_probe.get("ok") is not True:
                failures.append(f"运行器报名负向契约探针不能处理 TRPG_SAMPLE_DATA 浏览器全局对象：{sample_global_negative_probe.get('failures')}")
            if sample_global_negative_probe.get("data_path") != "data/sample-data-global.js" or sample_global_negative_probe.get("list_key") != "activities":
                failures.append("运行器报名负向契约探针没有记录 TRPG_SAMPLE_DATA 数据路径和列表字段")
            sample_global_character_probe = run_runner_character_player_contract_probe(project, evidence)
            if sample_global_character_probe.get("ok") is not True:
                failures.append(f"运行器角色玩家负向契约探针不能处理 TRPG_SAMPLE_DATA 浏览器全局对象：{sample_global_character_probe.get('failures')}")
            sample_data_global_js.unlink()
            activity_relation_probe = find_character_player_probe(project)
            if not isinstance(activity_relation_probe, dict):
                failures.append("行为关系探针没有从 data/sample-data.js 浏览器全局对象中找到角色玩家关系")
            elif activity_relation_probe.get("data_file") != "data/sample-data.js" or activity_relation_probe.get("event_index") != 1 or activity_relation_probe.get("character_index") != 0:
                failures.append(f"行为关系探针没有返回 data/*.js 的稳定事件和角色下标：{activity_relation_probe}")
            activity_global_js.unlink()
            sample_data = data_dir / "sample-data.json"
            sample_data.write_text(json.dumps({
                "events": [
                    {
                        "id": "probe-event-1",
                        "title": "关系探针活动一",
                        "players": [{"id": "probe-player-1", "name": "探针玩家一"}],
                        "characters": [{"id": "probe-character-1", "name": "探针角色一", "playerId": "probe-player-1"}],
                    },
                    {
                        "id": "probe-event-2",
                        "title": "关系探针活动二",
                        "players": [{"id": "probe-player-2", "name": "探针玩家二"}],
                        "characters": [{"id": "probe-character-2", "name": "探针角色二", "playerId": "probe-player-2"}],
                    },
                ]
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            relation_probe = find_character_player_probe(project)
            if not isinstance(relation_probe, dict):
                failures.append("行为关系探针没有从 events 列表数据中找到角色玩家关系")
            elif relation_probe.get("data_file") != "data/sample-data.json" or relation_probe.get("event_index") != 1 or relation_probe.get("character_index") != 0:
                failures.append(f"行为关系探针没有返回稳定的事件和角色下标：{relation_probe}")
            sample_data.unlink()
            nested_campaign_js = src_dir / "sample-data.js"
            nested_campaign_js.write_text(
                "window.TRPG_SEED_DATA = "
                + json.dumps({
                    "campaigns": [
                        {
                            "id": "campaign-nested-1",
                            "title": "嵌套活动一",
                            "sessions": [
                                {
                                    "id": "session-nested-1",
                                    "title": "嵌套场次一",
                                    "players": [{"id": "nested-player-1", "name": "嵌套玩家一"}],
                                    "characters": [{"id": "nested-character-1", "name": "嵌套角色一", "playerId": "nested-player-1"}],
                                    "signups": [{"id": "nested-signup-1", "playerId": "nested-player-1", "intentStatus": "confirmed"}],
                                }
                            ],
                        },
                        {
                            "id": "campaign-nested-2",
                            "title": "嵌套活动二",
                            "sessions": [
                                {
                                    "id": "session-nested-2",
                                    "title": "嵌套场次二",
                                    "players": [{"id": "nested-player-2", "name": "嵌套玩家二"}],
                                    "characters": [{"id": "nested-character-2", "name": "嵌套角色二", "playerId": "nested-player-2"}],
                                    "signups": [{"id": "nested-signup-2", "playerId": "nested-player-2", "intentStatus": "confirmed"}],
                                }
                            ],
                        },
                    ]
                }, ensure_ascii=False, indent=2)
                + ";\n",
                encoding="utf-8",
            )
            nested_relation_probe = find_character_player_probe(project)
            if not isinstance(nested_relation_probe, dict):
                failures.append("行为关系探针没有从 campaigns[].sessions[] 嵌套数据中找到角色玩家关系")
            elif (
                nested_relation_probe.get("data_file") != "src/sample-data.js"
                or nested_relation_probe.get("list_key") != "campaigns.1.sessions"
                or nested_relation_probe.get("event_title") != "嵌套活动二"
                or nested_relation_probe.get("record_title") != "嵌套场次二"
                or nested_relation_probe.get("character_index") != 0
            ):
                failures.append(f"行为关系探针没有返回嵌套活动的父级可点击标题和场次关系：{nested_relation_probe}")
            (project / "index.html").write_text(
                "<!doctype html>\n"
                "<html lang=\"zh-CN\">\n"
                "<head><meta charset=\"utf-8\"><title>关系视图自检</title></head>\n"
                "<body>\n"
                "<main>\n"
                "  <section id=\"activities\"></section>\n"
                "  <section aria-live=\"polite\">\n"
                "    <h1 id=\"activeTitle\"></h1>\n"
                "    <nav>\n"
                "      <button type=\"button\" data-view=\"signups\">报名意向</button>\n"
                "      <button type=\"button\" data-view=\"characters\">角色资料</button>\n"
                "    </nav>\n"
                "    <div id=\"view\"></div>\n"
                "  </section>\n"
                "</main>\n"
                "<script src=\"src/sample-data.js\"></script>\n"
                "<script src=\"src/relation-view-app.js\"></script>\n"
                "</body>\n"
                "</html>\n",
                encoding="utf-8",
            )
            (src_dir / "relation-view-app.js").write_text(
                "(function () {\n"
                "  const campaigns = window.TRPG_SEED_DATA.campaigns;\n"
                "  const sessions = campaigns.flatMap((campaign) => campaign.sessions.map((session) => ({ campaign, session })));\n"
                "  let activeId = sessions[0].session.id;\n"
                "  let activeView = 'signups';\n"
                "  const activities = document.getElementById('activities');\n"
                "  const activeTitle = document.getElementById('activeTitle');\n"
                "  const view = document.getElementById('view');\n"
                "  function active() { return sessions.find((item) => item.session.id === activeId) || sessions[0]; }\n"
                "  function render() {\n"
                "    const current = active();\n"
                "    activities.innerHTML = sessions.map((item) => `<button type=\"button\" data-session=\"${item.session.id}\">${item.campaign.title}<br>${item.session.title}</button>`).join('');\n"
                "    activities.querySelectorAll('button').forEach((button) => button.addEventListener('click', () => { activeId = button.dataset.session; render(); }));\n"
                "    activeTitle.textContent = `${current.campaign.title} / ${current.session.title}`;\n"
                "    if (activeView === 'characters') {\n"
                "      const players = new Map(current.session.players.map((player) => [player.id, player]));\n"
                "      view.innerHTML = current.session.characters.map((character) => `<article class=\"relation-card\"><h2>${character.name}</h2><p>玩家：${players.get(character.playerId).name}</p></article>`).join('');\n"
                "    } else {\n"
                "      view.innerHTML = current.session.signups.map((signup) => `<article><p>${signup.intentStatus}</p></article>`).join('');\n"
                "    }\n"
                "  }\n"
                "  document.querySelectorAll('[data-view]').forEach((button) => button.addEventListener('click', () => { activeView = button.dataset.view; render(); }));\n"
                "  render();\n"
                "}());\n",
                encoding="utf-8",
            )
            relation_view_behavior = run_behavioral_browser_verification(project, evidence)
            if relation_view_behavior.get("ok") is not True:
                failures.append(f"行为浏览器关系视图探索夹具未通过：{relation_view_behavior.get('failures')}")
            relation_view_check = next(
                (
                    item for item in relation_view_behavior.get("checks", [])
                    if isinstance(item, dict) and item.get("name") == "character_player_relation_visible"
                ),
                None,
            )
            relation_view_evidence = relation_view_check.get("evidence") if isinstance(relation_view_check, dict) else None
            relation_view_control = relation_view_evidence.get("relation_view_control") if isinstance(relation_view_evidence, dict) else None
            if not isinstance(relation_view_control, dict) or relation_view_control.get("clicked") is not True:
                failures.append(f"行为关系探针没有点击承载关系的视图入口：{relation_view_control}")
            elif "角色资料" not in str(relation_view_control.get("label") or ""):
                failures.append(f"行为关系探针点击的关系视图入口不是预期的角色资料标签：{relation_view_control}")
            nested_campaign_js.unlink()
            (src_dir / "relation-view-app.js").unlink(missing_ok=True)
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
            if "challenge_summary" not in reviewer_prompt or "reviewer_disposition" not in reviewer_prompt or "不能用 challenged、reviewer_acceptance" not in reviewer_prompt:
                failures.append("reviewer 提示词没有精确声明 role_opposition_matrix 必需字段")
            if '"prism_assistance_request": {"requested": true' not in reviewer_prompt or "顶层字段" not in reviewer_prompt or "reviews[] 内部不算有效请求" not in reviewer_prompt:
                failures.append("reviewer 提示词没有明确 prism_assistance_request 必须写在顶层")
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
            if "role_opposition_matrix" not in verdict_template:
                failures.append("review-verdict-template.json 没有预置 role_opposition_matrix")
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
                "candidates": [
                    {
                        "id": "self-check-candidate-1",
                        "summary": "自检夹具确认 E2E 收口经验必须进入候选处理流程。",
                        "source": "self-check fixture"
                    }
                ],
                "decisions": [
                    {
                        "candidate_id": "self-check-candidate-1",
                        "decision": "no_promote",
                        "reason": "自检夹具只验证流程触发，不晋升公共知识。"
                    }
                ],
                "no_candidate_reason": None
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
                "runner_owned_follow_up": REVIEWER_RUNNER_OWNED_FOLLOW_UP,
                "role_opposition_matrix": [
                    {
                        "role": "product_manager",
                        "challenge_summary": "产品经理接受方向并收窄范围。",
                        "reviewer_disposition": "accepted"
                    },
                    {
                        "role": "architect",
                        "challenge_summary": "架构师复核产品需求风险。",
                        "reviewer_disposition": "accepted"
                    },
                    {
                        "role": "developer",
                        "challenge_summary": "开发者复核架构与验收可实现性。",
                        "reviewer_disposition": "accepted"
                    },
                    {
                        "role": "tester",
                        "challenge_summary": "测试者用负向探针挑战开发声明。",
                        "reviewer_disposition": "accepted"
                    }
                ]
            })
            reviewer_failures = validate_reviewer_outputs(evidence)
            if reviewer_failures:
                failures.append(f"reviewer 终局边界自检失败：{reviewer_failures}")
            assisted_positive = load_json(evidence / "prism-assisted-review.json")
            assisted_nested_only = dict(assisted_positive)
            assisted_nested_only.pop("prism_assistance_request", None)
            assisted_nested_only["reviews"] = [
                {
                    "scope": "runner-prism-boundary",
                    "finding": "自检夹具模拟错误嵌套请求。",
                    "effect_on_verdict": "该结构必须失败。",
                    "prism_assistance_request": {"requested": True}
                }
            ]
            write_json(evidence / "prism-assisted-review.json", assisted_nested_only)
            nested_failures = validate_reviewer_outputs(evidence)
            if not any("reviews[] 内部不算有效请求" in item for item in nested_failures):
                failures.append(f"reviewer 嵌套 prism_assistance_request 负向自检未失败：{nested_failures}")
            assisted_missing = dict(assisted_positive)
            assisted_missing.pop("prism_assistance_request", None)
            write_json(evidence / "prism-assisted-review.json", assisted_missing)
            missing_request_failures = validate_reviewer_outputs(evidence)
            if not any("顶层记录运行器统一调度棱镜的请求" in item for item in missing_request_failures):
                failures.append(f"reviewer 缺少顶层 prism_assistance_request 负向自检未失败：{missing_request_failures}")
            write_json(evidence / "prism-assisted-review.json", assisted_positive)
            structural_final_prism = {
                "schema_id": "redcap-e2e-final-prism-review",
                "producer": "e2e-runner",
                "ok": False,
                "strictest_verdict": "concern",
                "reviews": [],
                "merge": {
                    "strictest_verdict": "concern",
                    "main_concerns": [
                        {
                            "provider": "kimi",
                            "concern": "The completion claim is self-witnessed and self-referential; the same RedCap harness lacks an external anchor and the relation probe has page-state ambiguity."
                        },
                        {
                            "provider": "claude-code",
                            "concern": "The independent browser verification uses an inline script instead of a hash-verifiable file, and cross-role challenge evidence is too weak."
                        }
                    ],
                    "minimum_fixes": [
                        {
                            "provider": "kimi",
                            "minimum_fix": "Add an external anchor or downgrade to engineering-trial scope; record relation probe state."
                        }
                    ]
                },
                "failures": ["最终棱镜 strictest_verdict 不是 pass：concern"],
            }
            structural_convergence = classify_final_prism_convergence(structural_final_prism, structural_final_prism["failures"])
            structural_classes = {item.get("loop_class") for item in structural_convergence.get("diagnosis", [])}
            expected_structural_classes = {
                "verification_authority_gap",
                "loom_opposition_gap",
                "behavioral_evidence_alignment_gap",
            }
            if structural_convergence.get("auto_rerun_allowed") is not False:
                failures.append("结构性最终棱镜 concern 没有禁止自动盲目重跑")
            if not expected_structural_classes.issubset(structural_classes):
                failures.append(f"结构性收敛诊断缺少类别：{sorted(expected_structural_classes - structural_classes)}")
            runner_probe_final_prism = {
                "schema_id": "redcap-e2e-final-prism-review",
                "producer": "e2e-runner",
                "ok": False,
                "strictest_verdict": "concern",
                "reviews": [],
                "merge": {
                    "strictest_verdict": "concern",
                    "main_concerns": [
                        {
                            "provider": "claude-code",
                            "concern": "Runner negative contract probes trigger data/seed-data.js did not set window.TRPG_SEED_DATA, a syntax-level setup failure rather than domain contract validation."
                        }
                    ],
                },
                "failures": ["最终棱镜 strictest_verdict 不是 pass：concern"],
            }
            runner_probe_convergence = classify_final_prism_convergence(runner_probe_final_prism, runner_probe_final_prism["failures"])
            runner_probe_classes = {item.get("loop_class") for item in runner_probe_convergence.get("diagnosis", [])}
            if "runner_negative_probe_semantics_gap" not in runner_probe_classes:
                failures.append(f"负向探针语义缺口没有被收敛诊断识别：{runner_probe_convergence}")
            skipped_final_prism = {
                "schema_id": "redcap-e2e-final-prism-review",
                "producer": "e2e-runner",
                "ok": False,
                "skipped": True,
                "skip_reason": "前置客观证据未通过，跳过最终 provider 复核",
                "strictest_verdict": None,
                "failures": [
                    "运行器负向领域契约探针未通过",
                    "运行器角色玩家负向领域契约探针未通过",
                ],
            }
            skipped_convergence = classify_final_prism_convergence(skipped_final_prism, skipped_final_prism["failures"])
            skipped_classes = {item.get("loop_class") for item in skipped_convergence.get("diagnosis", [])}
            if "objective_evidence_precondition_gap" not in skipped_classes:
                failures.append("前置客观证据失败导致最终棱镜跳过时，收敛诊断没有归类为 objective_evidence_precondition_gap")
            if "loom_opposition_gap" in skipped_classes:
                failures.append("前置客观证据失败导致最终棱镜跳过时，收敛诊断误判为 loom_opposition_gap")
            if skipped_convergence.get("auto_rerun_allowed") is not False:
                failures.append("前置客观证据失败导致最终棱镜跳过时，收敛诊断没有禁止自动盲目重跑")
            visual_evidence = work_root / "visual-report-self-check" / ".redcap" / "evidence" / "e2e"
            visual_evidence.mkdir(parents=True, exist_ok=True)

            def write_visual_probe(name: str, payload: bytes) -> dict[str, Any]:
                path = visual_evidence / name
                path.write_bytes(payload)
                return evidence_file_record(path, base=visual_evidence)

            browser_record = write_visual_probe("browser-inspection.png", b"http-static-render")
            file_record = write_visual_probe("file-browser-inspection.png", b"file-static-render")
            behavioral_record = write_visual_probe("behavioral-browser-verification.png", b"behavioral-render")
            relation_record = write_visual_probe("behavioral-relation-probe.png", b"behavioral-render")
            independent_record = write_visual_probe("independent-browser-verification.png", b"independent-render")
            observer_record = write_visual_probe("independent-observer.png", b"observer-render")
            common_viewport = {"width": 1280, "height": 900}
            write_json(visual_evidence / "browser-inspection.json", {
                "ok": True,
                "screenshot_record": browser_record,
                "browser_context": {
                    "process_pid": 1,
                    "browser_version": "self-check",
                    "viewport": common_viewport,
                    "server_port": 1111,
                    "capture_role": "browser-inspection",
                    "screenshot_phase": "initial_render",
                },
            })
            write_json(visual_evidence / "file-browser-inspection.json", {
                "ok": True,
                "screenshot_record": file_record,
                "browser_context": {
                    "process_pid": 2,
                    "browser_version": "self-check",
                    "viewport": FILE_BROWSER_INSPECTION_VIEWPORT,
                    "server_port": 0,
                    "capture_role": "file-browser-inspection",
                    "screenshot_phase": "file_protocol_render",
                    "protocol": "file",
                    "visual_independence_strategy": "different_viewport_from_http_browser_inspection",
                },
            })
            write_json(visual_evidence / "behavioral-browser-verification.json", {
                "ok": True,
                "screenshot_record": behavioral_record,
                "relation_probe_screenshot_record": relation_record,
                "checks": [
                    {
                        "name": "character_player_relation_visible",
                        "passed": True,
                        "evidence": {
                            "relation_event_control": {"clicked": True, "reason": "matched_event_title"},
                            "dom_structural_probe": {
                                "same_structural_container": True,
                                "matched_container_count": 1,
                            },
                        },
                    }
                ],
                "browser_context": {
                    "process_pid": 3,
                    "browser_version": "self-check",
                    "viewport": {"width": 1280, "height": 900},
                    "server_port": 1112,
                    "capture_role": "behavioral-interaction",
                    "screenshot_phase": "after_interaction",
                },
            })
            write_json(visual_evidence / "independent-browser-verification.json", {
                "ok": True,
                "screenshot_record": independent_record,
                "browser_context": {
                    "process_pid": 4,
                    "browser_version": "self-check",
                    "viewport": {"width": 1176, "height": 820},
                    "server_port": 1113,
                    "capture_role": "independent-browser-process",
                    "screenshot_phase": "after_interaction",
                },
            })
            write_json(visual_evidence / "independent-observer.json", {
                "ok": True,
                "bundle_fingerprint": {
                    "matches_declared_bundle_sha256": True,
                    "file_sha256_stable_after_cooldown": True,
                },
                "browser_observation": {
                    "screenshot_record": observer_record,
                    "browser_context": {
                        "process_pid": 5,
                        "browser_version": "self-check",
                        "viewport": {"width": 1032, "height": 760},
                        "server_port": 1114,
                        "capture_role": "independent-observer",
                        "screenshot_phase": "after_interaction",
                    },
                },
            })
            visual_report = build_visual_independence_report(visual_evidence)
            if visual_report.get("ok") is not True:
                failures.append(f"视觉独立报告不能通过已区分 HTTP/file 截图的夹具：{visual_report.get('failures')}")
            visual_source_ids = {item.get("source_id") for item in visual_report.get("sources", []) if isinstance(item, dict)}
            if "file-browser-inspection" not in visual_source_ids:
                failures.append("视觉独立报告没有纳入 file-browser-inspection 截图来源")
            allowed_duplicate_sources = {
                tuple(item.get("sources") or [])
                for item in visual_report.get("allowed_duplicate_screenshot_hashes", [])
                if isinstance(item, dict)
            }
            if ("browser-inspection", "file-browser-inspection") in allowed_duplicate_sources:
                failures.append("视觉独立报告不应再允许 HTTP/file 截图同像素作为常规通过路径")
            if ("behavioral-browser-verification", "behavioral-relation-probe") not in allowed_duplicate_sources:
                failures.append("视觉独立报告没有记录行为截图与关系探针同状态截图的允许重复说明")
            if visual_report.get("unreported_png_files"):
                failures.append(f"视觉独立报告误判存在未报告截图：{visual_report.get('unreported_png_files')}")
            (visual_evidence / "unreported-extra.png").write_bytes(b"unreported")
            visual_report_with_extra = build_visual_independence_report(visual_evidence)
            if visual_report_with_extra.get("ok") is True or "unreported-extra.png" not in visual_report_with_extra.get("unreported_png_files", []):
                failures.append("视觉独立报告没有拦截未纳入 sources 的额外 PNG 截图")
            browser_relation_duplicate_evidence = work_root / "visual-browser-relation-duplicate-self-check" / ".redcap" / "evidence" / "e2e"
            browser_relation_duplicate_evidence.mkdir(parents=True, exist_ok=True)

            def write_browser_relation_duplicate_probe(name: str, payload: bytes) -> dict[str, Any]:
                path = browser_relation_duplicate_evidence / name
                path.write_bytes(payload)
                return evidence_file_record(path, base=browser_relation_duplicate_evidence)

            duplicate_browser_record = write_browser_relation_duplicate_probe("browser-inspection.png", b"same-initial-and-relation-render")
            duplicate_file_record = write_browser_relation_duplicate_probe("file-browser-inspection.png", b"duplicate-file-render")
            duplicate_behavioral_record = write_browser_relation_duplicate_probe("behavioral-browser-verification.png", b"duplicate-behavior-render")
            duplicate_relation_record = write_browser_relation_duplicate_probe("behavioral-relation-probe.png", b"same-initial-and-relation-render")
            duplicate_independent_record = write_browser_relation_duplicate_probe("independent-browser-verification.png", b"duplicate-independent-render")
            duplicate_observer_record = write_browser_relation_duplicate_probe("independent-observer.png", b"duplicate-observer-render")
            write_json(browser_relation_duplicate_evidence / "browser-inspection.json", {
                "ok": True,
                "screenshot_record": duplicate_browser_record,
                "browser_context": {
                    "process_pid": 11,
                    "browser_version": "self-check",
                    "viewport": common_viewport,
                    "server_port": 2111,
                    "capture_role": "browser-inspection",
                    "screenshot_phase": "initial_render",
                },
            })
            write_json(browser_relation_duplicate_evidence / "file-browser-inspection.json", {
                "ok": True,
                "screenshot_record": duplicate_file_record,
                "browser_context": {
                    "process_pid": 12,
                    "browser_version": "self-check",
                    "viewport": FILE_BROWSER_INSPECTION_VIEWPORT,
                    "server_port": 0,
                    "capture_role": "file-browser-inspection",
                    "screenshot_phase": "file_protocol_render",
                    "protocol": "file",
                },
            })
            write_json(browser_relation_duplicate_evidence / "behavioral-browser-verification.json", {
                "ok": True,
                "screenshot_record": duplicate_behavioral_record,
                "relation_probe_screenshot_record": duplicate_relation_record,
                "checks": [
                    {
                        "name": "character_player_relation_visible",
                        "passed": True,
                        "evidence": {
                            "relation_event_control": {"clicked": False, "reason": "initial_page_already_visible"},
                            "relation_visual_focus": {"applied": False, "reason": "self_check_bad_case_no_focus"},
                            "dom_structural_probe": {
                                "same_structural_container": True,
                                "matched_container_count": 1,
                            },
                        },
                    }
                ],
                "browser_context": {
                    "process_pid": 13,
                    "browser_version": "self-check",
                    "viewport": common_viewport,
                    "server_port": 2112,
                    "capture_role": "behavioral-interaction",
                    "screenshot_phase": "after_interaction",
                },
            })
            write_json(browser_relation_duplicate_evidence / "independent-browser-verification.json", {
                "ok": True,
                "screenshot_record": duplicate_independent_record,
                "browser_context": {
                    "process_pid": 14,
                    "browser_version": "self-check",
                    "viewport": {"width": 1176, "height": 820},
                    "server_port": 2113,
                    "capture_role": "independent-browser-process",
                    "screenshot_phase": "after_interaction",
                },
            })
            write_json(browser_relation_duplicate_evidence / "independent-observer.json", {
                "ok": True,
                "bundle_fingerprint": {
                    "matches_declared_bundle_sha256": True,
                    "file_sha256_stable_after_cooldown": True,
                },
                "browser_observation": {
                    "screenshot_record": duplicate_observer_record,
                    "browser_context": {
                        "process_pid": 15,
                        "browser_version": "self-check",
                        "viewport": {"width": 1032, "height": 760},
                        "server_port": 2114,
                        "capture_role": "independent-observer",
                        "screenshot_phase": "after_interaction",
                    },
                },
            })
            browser_relation_duplicate_report = build_visual_independence_report(browser_relation_duplicate_evidence)
            if browser_relation_duplicate_report.get("ok") is True:
                failures.append("视觉独立报告误放行 browser-inspection 与 behavioral-relation-probe 同像素截图")
            if not browser_relation_duplicate_report.get("unexpected_duplicate_screenshot_sha256"):
                failures.append("视觉独立报告没有把 browser/relation 同像素识别为未解释重复")
            replay_evidence = work_root / "convergence-replay" / ".redcap" / "evidence" / "e2e"
            write_json(replay_evidence / "final-prism-review.json", structural_final_prism)
            write_json(replay_evidence / "run-summary.json", {
                "schema_id": "redcap-ai-e2e-run-result",
                "ok": False,
                "failures": ["最终棱镜复核未通过"],
            })
            replay_convergence = convergence_diagnosis_from_evidence(replay_evidence)
            replay_classes = {item.get("loop_class") for item in replay_convergence.get("diagnosis", [])}
            if not expected_structural_classes.issubset(replay_classes):
                failures.append(f"收敛回放没有复现结构性类别：{sorted(expected_structural_classes - replay_classes)}")
            loop_root = work_root / "loop-guard"
            previous_evidence = loop_root / "previous" / ".redcap" / "evidence" / "e2e"
            write_json(previous_evidence / "convergence-diagnosis.json", replay_convergence)
            blocked_guard = convergence_rerun_guard(loop_root)
            if blocked_guard.get("blocked") is not True:
                failures.append("上一轮 auto_rerun_allowed=false 且源码未变时，E2E 重跑守卫没有阻断")
            changed_convergence = copy.deepcopy(replay_convergence)
            changed_convergence.setdefault("redcap_source", {})["source_signature"] = "old-source-signature"
            write_json(previous_evidence / "convergence-diagnosis.json", changed_convergence)
            allowed_guard = convergence_rerun_guard(loop_root)
            if allowed_guard.get("blocked") is True:
                failures.append("源码签名变化后，E2E 重跑守卫没有允许修复后验证")
            patrol_root = work_root / "patrol-guard"
            patrol_root.mkdir(parents=True, exist_ok=True)
            for index in range(E2E_PATROL_MAX_ITERATIONS):
                append_jsonl(patrol_ledger_path(patrol_root), {
                    "event": "e2e_iteration_started",
                    "iteration": index + 1,
                    "recorded_at": iso_now(),
                })
            patrol_guard = patrol_iteration_guard(patrol_root)
            if patrol_guard.get("blocked") is not True or patrol_guard.get("next_iteration") != E2E_PATROL_MAX_ITERATIONS + 1:
                failures.append("E2E 巡检轮次硬上限没有在第 4 轮前阻断")
            current_source = pathlib.Path(__file__).read_text(encoding="utf-8")
            legacy_full_auto_flag = "--full" + "-auto"
            if legacy_full_auto_flag in current_source:
                failures.append("E2E 角色调用不得继续使用当前 Codex CLI 不支持的旧全自动参数")
            if "patrol_iteration_guard" not in current_source or "redcap-e2e-patrol-ledger.jsonl" not in current_source:
                failures.append("E2E 自检没有覆盖巡检轮次硬上限守卫")
            if "codex_cli_readiness_check" not in current_source or "codex-exec-smoke" not in current_source:
                failures.append("E2E 自检没有覆盖 Codex CLI 可用性探针")
            if '"python3", "-m", "http.server"' not in current_source or "http://127.0.0.1:" not in current_source:
                failures.append("浏览器验收没有通过本地 HTTP 服务打开项目，可能退化为 file:// 误判")
            if "process_group_killed" not in current_source or "exit_code_after_cleanup" not in current_source:
                failures.append("浏览器验收没有记录本地 HTTP 服务清理证据")
            if "behavioral-browser-verification.json" not in current_source or "interactive_state_change" not in current_source:
                failures.append("E2E 自检没有覆盖行为级浏览器验证证据")
            observer_source = (REPO_ROOT / "runtime" / "core" / "e2e_independent_observer.py").read_text(encoding="utf-8")
            if '"app/index.html"' not in current_source or '"app/index.html"' not in observer_source:
                failures.append("浏览器入口候选没有同时覆盖运行器和独立观察者的 app/index.html")
            if "independent-browser-verification.json" not in current_source or "e2e-independent-browser-process" not in current_source:
                failures.append("E2E 自检没有覆盖独立子进程浏览器复核证据")
            if "independent-browser-verification-script.py" not in current_source or "script_sha256" not in current_source:
                failures.append("E2E 自检没有覆盖独立浏览器验证脚本哈希证据")
            if "role_opposition_matrix" not in current_source or "upstream_challenges" not in current_source:
                failures.append("E2E 自检没有覆盖 Loom 角色对抗证据")
            if 'role-artifacts/{role}.json 的 status 必须精确写成 "completed"' not in current_source:
                failures.append("E2E 自检没有覆盖角色产物 status 精确完成约束")
            if 'role-artifacts/developer.json 的 status 必须精确是 "completed"' not in current_source:
                failures.append("E2E 自检没有覆盖 developer 角色 status 精确完成约束")
            if "convergence-diagnosis.json" not in current_source or "classify_final_prism_convergence" not in current_source:
                failures.append("E2E 自检没有覆盖防无限循环的收敛诊断证据")
            if "convergence_rerun_guard" not in current_source or "redcap-e2e-convergence-rerun-guard.json" not in current_source:
                failures.append("E2E 自检没有覆盖 auto_rerun_allowed=false 的下一轮重跑阻断")
            if "convergence_diagnosis_from_evidence" not in current_source or "convergence-check" not in current_source:
                failures.append("E2E 自检没有覆盖旧轮次收敛诊断回放入口")
            if "convergence-guard-check" not in current_source or "expect_blocked" not in current_source:
                failures.append("E2E 自检没有覆盖重跑守卫检查入口")
            if "runtime-boundary-probe" not in current_source or "run_e2e_active_run_runtime_boundary_probe" not in current_source:
                failures.append("E2E 自检没有覆盖 active_run 运行时边界探针")
            if "long-task-integration-dry-run" not in current_source or "run_long_task_e2e_integration_dry_run" not in current_source:
                failures.append("E2E 自检没有覆盖长任务到巡检的集成干跑")
            if len(re.findall(r"^def e2e_active_run_boundary_failures\(", current_source, re.MULTILINE)) != 1:
                failures.append("E2E active_run 边界检查底层实现必须只有一个，避免入口、收束和发现逻辑漂移")
            if "e2e_active_run_entry_failures_via_boundary_check" not in current_source or "e2e_active_run_final_failures_via_boundary_check" not in current_source:
                failures.append("E2E active_run 入口和收束检查必须显式委托给统一边界检查")
            if "behavioral-relation-probe.png" not in current_source or "relation_event_control" not in current_source or "relation_record_control" not in current_source:
                failures.append("E2E 自检没有覆盖行为关系探针截图和事件状态证据")
            for required_token in [
                "RELATION_PROBE_VIEWPORT",
                "RELATION_PROBE_MIN_VIEWPORT",
                "RELATION_PROBE_MIN_VISIBLE_RATIO",
                "relation_probe_browser_context",
                "reset_relation_probe_page_state",
                "relation_probe_state_reset",
                "behavioral-relation-container-crop.png",
                "relation_container_clip",
                "relation_container_crop_written",
                "visibleAreaRatio",
                "full_page=False",
                "dom_mutation",
            ]:
                if required_token not in current_source:
                    failures.append(f"E2E 自检没有覆盖关系探针专用视口截图防线：{required_token}")
            if "independent-observer.json" not in current_source or "e2e_independent_observer.py" not in current_source:
                failures.append("E2E 自检没有覆盖独立外部观察者证据")
            if "run_e2e_harness" not in current_source or "REDCAP_E2E_WORKER" not in current_source:
                failures.append("E2E 自检没有覆盖 harness/worker 兄弟进程运行结构")
            harness_source = inspect.getsource(run_e2e_harness)
            for required_token in [
                "observer_request_routing_decision",
                "request_runner_pid != worker_pid",
                "stale-runner-pid",
                "unreadable",
                "skipped_observer_requests",
                "observer_commands",
            ]:
                if required_token not in harness_source and required_token not in current_source:
                    failures.append(f"E2E harness 观察者请求路由缺少本轮隔离防线：{required_token}")
            legacy_deadline_pattern = "timeout_seconds" + " + OBSERVER_TIMEOUT_SECONDS + 600"
            if legacy_deadline_pattern in current_source:
                failures.append("E2E harness 不能继续把用户硬超时叠加观察者超时和隐藏余量")
            if "worker_deadline_monotonic = time.monotonic() + timeout_seconds" not in harness_source:
                failures.append("E2E harness 没有把 timeout_seconds 作为 worker 唯一硬截止时间")
            for required_token in [
                "HarnessInterrupted",
                "signal.SIGTERM",
                "signal.SIGHUP",
                "start_harness_watchdog",
                "worker_exit_reason",
                "observer_timeout_extends_worker_deadline",
                "communicate_worker_after_stop",
            ]:
                if required_token not in harness_source and required_token not in current_source:
                    failures.append(f"E2E harness 硬超时与中断清理缺少：{required_token}")
            for required_token in ["process_matches_identity", "kill_recorded_process_group", "run_harness_timeout_regression_test", "harness-timeout-regression-test"]:
                if required_token not in current_source:
                    failures.append(f"E2E harness 清理安全自检缺少：{required_token}")
            if "run_layered_preflight(work_root)" not in harness_source:
                failures.append("E2E harness 必须在 Codex CLI 承载探针和 Loom 角色启动前运行 RedCap 分层前置检查")
            if "carrier_probe(work_root / \"carrier-preflight\"" not in harness_source:
                failures.append("E2E harness 必须在 Loom 角色启动前运行 Codex CLI hook 承载探针")
            layered_index = harness_source.find("run_layered_preflight(")
            carrier_index = harness_source.find("carrier_probe(")
            worker_index = harness_source.find('env["REDCAP_E2E_WORKER"]')
            if carrier_index < 0 or worker_index < 0 or carrier_index > worker_index:
                failures.append("Codex CLI hook 承载探针必须早于 REDCAP_E2E_WORKER worker 启动")
            if layered_index < 0 or carrier_index < 0 or worker_index < 0 or not (layered_index < carrier_index < worker_index):
                failures.append("RedCap 分层前置检查必须早于 Codex CLI 承载探针和 REDCAP_E2E_WORKER worker 启动")
            preflight_source = inspect.getsource(run_layered_preflight)
            for required_token in [
                "loom-runtime",
                "self-purification",
                "knowledge-gateway",
                "project-install",
                "release-check",
                "blocked_before_project_run",
                "TEST_INJECT_LAYERED_PREFLIGHT_FAILURE_ENV",
                "TEST_MODE_ENV",
            ]:
                if required_token not in preflight_source:
                    failures.append(f"RedCap 分层前置检查缺少关键能力：{required_token}")
            regression_source = inspect.getsource(run_layered_preflight_regression_test)
            for required_token in ["normal-pass", "knowledge-search-loom", "self-purification-self-check", "layered_preflight_block_failures"]:
                if required_token not in regression_source:
                    failures.append(f"RedCap 分层前置回归测试缺少覆盖：{required_token}")
            if "observer_seal" not in current_source or "parent_is_not_runner" not in current_source:
                failures.append("E2E 自检没有覆盖观察者 seal 与非 runner 父进程约束")
            if "runner-negative-contract-probe.json" not in current_source or "empty-signups-and-empty-signupIntent-must-fail" not in current_source:
                failures.append("E2E 自检没有覆盖运行器坏数据负向契约探针证据")
            if "runner-character-player-contract-probe.json" not in current_source or "broken-character-player-link-must-fail" not in current_source:
                failures.append("E2E 自检没有覆盖运行器角色玩家负向契约探针证据")
            if "probe_depth" not in current_source or "targeted_non_first_record" not in current_source or "targeted_non_first_event" not in current_source:
                failures.append("E2E 自检没有覆盖负向探针优先命中非首条记录的深度证据")
            if "HTML_JSON_SCRIPT_RE" not in current_source or "trpg-activity-data" not in current_source or "index.html 内嵌 JSON 数据" not in current_source:
                failures.append("E2E 自检没有覆盖 HTML 内嵌 JSON 数据探针")
            if '"__".join(source.relative_to(evidence).parts)' not in current_source:
                failures.append("角色轮次快照没有按来源相对路径命名，可能覆盖同名证据文件")
            if "runner-self-purification-resolution.json" not in current_source or "write_runner_self_purification_resolution" not in current_source:
                failures.append("E2E 自检没有覆盖运行器自我净化裁决证据")
            if "same_structural_container" not in current_source or "text_distance_is_informational_only" not in current_source:
                failures.append("行为级浏览器关系验证没有升级为 DOM 结构级探针")
            if "pending_final_evidence" not in current_source or "completion-marker.json\", \"final-prism-review.json\", \"iteration-verdict.json" not in current_source:
                failures.append("pre-final-readiness 没有把最终文件移出已检查证据清单")
            if "failure-backlog-full" not in current_source or "independent-observer-full" not in current_source or "package-prism-check-full" not in current_source:
                failures.append("最终棱镜复核请求没有包含 failure-backlog、independent-observer 和 package-prism-check 的完整证据项")
            if "final-marker-validation-full" not in current_source or "file-browser-inspection-full" not in current_source or "self-referential-boundary-full" not in current_source:
                failures.append("最终棱镜复核请求没有包含最终标记前验证、file 协议浏览器检查和自引用边界披露")
            if "\"failure_backlog\": load_optional_json" not in current_source or "\"independent_observer\": load_optional_json" not in current_source or "\"package_prism_check\": load_optional_json" not in current_source:
                failures.append("最终棱镜复核没有从证据目录读取完整关键 JSON 后再提交给评审方")
            if "\"final_marker_validation\": load_optional_json" not in current_source or "\"file_browser_inspection\": load_optional_json" not in current_source or "\"self_referential_boundary\": load_optional_json" not in current_source:
                failures.append("最终棱镜复核没有读取新增关键 JSON 后再提交给评审方")
            if "text_hash" not in current_source or "dom_summary_hash" not in current_source or "observable_criteria" not in current_source:
                failures.append("行为级浏览器验证没有使用文本哈希和稳定 DOM 摘要哈希作为可度量交互标准")
            if "screenshot_phase" not in current_source or "after_interaction" not in current_source or "behavioral_visual_independence" not in current_source:
                failures.append("行为级浏览器验证没有固化交互后截图阶段与视觉独立性检查")
            if "visual_independence" not in current_source or "hashes_differ" not in current_source or "browser-inspection.png" not in current_source:
                failures.append("行为级浏览器验证没有比较普通浏览器截图和行为截图哈希")
            if "visual-independence-report.json" not in current_source or "build_visual_independence_report" not in current_source:
                failures.append("E2E 自检没有覆盖视觉三角独立性报告")
            if "file-browser-inspection.json" not in current_source or "local-file-protocol" not in current_source or "run_file_browser_inspection" not in current_source:
                failures.append("E2E 自检没有覆盖 file:// 本地文件协议浏览器检查")
            if "final-marker-validation.json" not in current_source or "run_final_marker_validation" not in current_source or "stdout_sha256_required" not in current_source:
                failures.append("E2E 自检没有覆盖写 completion-marker 前的最终项目验证")
            if "self-referential-boundary.json" not in current_source or "not_claimed" not in current_source or "validation_chain_scope" not in current_source:
                failures.append("E2E 自检没有覆盖自引用边界披露")
            if "role_process_completion" not in current_source or "role_processes_may_exit_non_zero_after_intentional_stop" not in current_source:
                failures.append("E2E 自检没有覆盖 Loom 角色进程完成边界披露")
            if "observer_boundary" not in current_source or "bootstrap_review_boundary" not in current_source:
                failures.append("E2E 自检没有覆盖观察者边界和自举复核边界披露")
            if "must_copy_role_process_completion" not in current_source or "must_copy_bootstrap_review_boundary" not in current_source:
                failures.append("completion-marker 披露约束没有要求复制角色完成边界和自举复核边界")
            if "matches_declared_bundle_sha256" not in current_source or "file_sha256_stable_after_cooldown" not in current_source or "cooldown_seconds" not in current_source:
                failures.append("E2E 自检没有覆盖独立观察者声明哈希核对与冷却后文件哈希复核")
            if "data-redcap-volatile" not in current_source or ".spinner" not in current_source or ".loading" not in current_source:
                failures.append("行为级浏览器验证没有排除时间戳和加载器等常见噪音节点")
            if "interactive_gate_marker_observed" not in current_source or "actionable_interactive_gate_marker" not in current_source:
                failures.append("角色交互式门禁证据没有区分观测噪音与行动标记")
            if current_source.count("\n    write_json(evidence / \"final-evidence-bundle.json\", bundle)\n") != 1:
                failures.append("final-evidence-bundle.json 必须只写入一次，避免观察者核对后再次改写冻结包")
        guard_probe = source_workspace_guard_negative_probe()
        if guard_probe.get("ok") is not True:
            failures.append(f"源工作区保护负向探针失败：{guard_probe.get('failures')}")
        prism_ledger_isolation_probe = source_workspace_prism_ledger_isolation_probe()
        if prism_ledger_isolation_probe.get("ok") is not True:
            failures.append(f"棱镜流水隔离探针失败：{prism_ledger_isolation_probe.get('failures')}")
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
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--work-root")
    preflight.set_defaults(func=cmd_preflight)
    preflight_regression = sub.add_parser("preflight-regression-test")
    preflight_regression.add_argument("--work-root")
    preflight_regression.set_defaults(func=cmd_preflight_regression_test)
    convergence = sub.add_parser("convergence-check")
    convergence.add_argument("--evidence-root", required=True)
    convergence.add_argument("--out")
    convergence.add_argument("--expect-structural-stop", action="store_true")
    convergence.set_defaults(func=cmd_convergence_check)
    guard_check = sub.add_parser("convergence-guard-check")
    guard_check.add_argument("--work-root")
    guard_check.add_argument("--out")
    guard_check.add_argument("--expect-blocked", action="store_true")
    guard_check.set_defaults(func=cmd_convergence_guard_check)
    runtime_probe = sub.add_parser("runtime-boundary-probe")
    runtime_probe.add_argument("--work-root")
    runtime_probe.add_argument("--out")
    runtime_probe.set_defaults(func=cmd_runtime_boundary_probe)
    integration_dry_run = sub.add_parser("long-task-integration-dry-run")
    integration_dry_run.add_argument("--work-root")
    integration_dry_run.add_argument("--out")
    integration_dry_run.set_defaults(func=cmd_long_task_integration_dry_run)
    harness_timeout_regression = sub.add_parser("harness-timeout-regression-test")
    harness_timeout_regression.add_argument("--work-root")
    harness_timeout_regression.set_defaults(func=cmd_harness_timeout_regression_test)
    runner_negative_probe_regression = sub.add_parser("runner-negative-probe-regression-test")
    runner_negative_probe_regression.add_argument("--work-root")
    runner_negative_probe_regression.set_defaults(func=cmd_runner_negative_probe_regression_test)
    watchdog = sub.add_parser("harness-watchdog", help=argparse.SUPPRESS)
    watchdog.add_argument("--record", required=True)
    watchdog.set_defaults(func=cmd_harness_watchdog)
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

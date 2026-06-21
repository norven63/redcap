#!/usr/bin/env python3
"""检查外部评审方命令行工具的路径、会话、文件读取和失败分类。"""

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
import time
import uuid
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = REPO_ROOT / "assets" / "contracts" / "provider-health.json"
DEFAULT_EVIDENCE_DIR = REPO_ROOT / "assets" / "evidence" / "provider-health"
CONTRACT_SCHEMA_ID = "redcap-provider-health-contract"
REPORT_SCHEMA_ID = "redcap-provider-health-report"
SELF_CHECK_SCHEMA_ID = "redcap-provider-health-self-check"
LIVE_SCHEMA_ID = "redcap-provider-health-live-report"
TRANSIENCE = {"transient", "permanent", "unknown"}
REQUIRED_PROBE_IDS = {
    "path",
    "version",
    "basic_call",
    "session_resume",
    "bounded_file_read",
    "timeout_classification",
    "path_error",
    "permission_block",
}
MINIMUM_FAILURE_CATEGORIES = {
    "timeout",
    "connection_refused",
    "quota_exhausted",
    "auth_failure",
    "unknown",
}
SUPPORTED_FIXTURES = {
    "healthy",
    "path-error",
    "permission-block",
    "timeout",
    "session-resume-failure",
    "file-budget-exceeded",
    "quota-exhausted",
    "auth-failure",
    "connection-refused",
    "unknown-failure",
}
SESSION_RE = re.compile(r"(session_[0-9a-fA-F-]{36}|[0-9a-fA-F]{8}-[0-9a-fA-F-]{27})")
GENERIC_EXCEPTION_NAMES = {"BaseException", "Exception", "OSError", "IOError"}
EXCEPTION_PARENTS = {
    "asyncio.TimeoutError": "TimeoutError",
    "TimeoutError": "OSError",
    "PermissionError": "OSError",
    "FileNotFoundError": "OSError",
    "ConnectionError": "OSError",
    "ConnectionRefusedError": "ConnectionError",
    "OSError": "Exception",
    "IOError": "OSError",
    "Exception": "BaseException",
}


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}") from exc


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def category_map(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = contract.get("failure_categories")
    if not isinstance(items, list):
        return {}
    return {
        item["id"]: item
        for item in items
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != CONTRACT_SCHEMA_ID:
        failures.append(f"schema_id must be {CONTRACT_SCHEMA_ID}")
    if not isinstance(contract.get("version"), int) or contract.get("version") < 1:
        failures.append("version must be a positive integer")

    stdout_policy = contract.get("stdout_policy")
    if not isinstance(stdout_policy, dict):
        failures.append("stdout_policy missing")
        stdout_policy = {}
    if stdout_policy.get("summary_only") is not True:
        failures.append("stdout_policy.summary_only must be true")
    if stdout_policy.get("details_must_be_file") is not True:
        failures.append("stdout_policy.details_must_be_file must be true")
    if not isinstance(stdout_policy.get("max_summary_chars"), int) or stdout_policy.get("max_summary_chars") < 200:
        failures.append("stdout_policy.max_summary_chars must be an integer >= 200")

    budget = contract.get("file_access_budget")
    if not isinstance(budget, dict):
        failures.append("file_access_budget missing")
        budget = {}
    for key in ["max_files", "max_bytes_per_file", "max_total_bytes"]:
        value = budget.get(key)
        if not isinstance(value, int) or value < 1:
            failures.append(f"file_access_budget.{key} must be a positive integer")
    allowed_extensions = budget.get("allowed_extensions")
    if not isinstance(allowed_extensions, list) or not allowed_extensions:
        failures.append("file_access_budget.allowed_extensions must be a non-empty list")
    elif any(not isinstance(item, str) or not item.startswith(".") for item in allowed_extensions):
        failures.append("file_access_budget.allowed_extensions must contain extension strings")
    if not isinstance(budget.get("denied_path_parts"), list):
        failures.append("file_access_budget.denied_path_parts must be a list")
    if not isinstance(budget.get("denied_filenames"), list):
        failures.append("file_access_budget.denied_filenames must be a list")

    live_policy = contract.get("live_check_policy")
    if not isinstance(live_policy, dict):
        failures.append("live_check_policy missing")
        live_policy = {}
    if live_policy.get("included_in_aggregate") is not False:
        failures.append("live_check_policy.included_in_aggregate must be false")
    for key in ["max_retries", "timeout_seconds", "file_read_timeout_seconds", "retry_backoff_seconds"]:
        value = live_policy.get(key)
        if not isinstance(value, int) or value < 0:
            failures.append(f"live_check_policy.{key} must be a non-negative integer")

    probes = contract.get("required_probes")
    if not isinstance(probes, list):
        failures.append("required_probes must be a list")
        probe_ids: set[str] = set()
    else:
        probe_ids = {item.get("id") for item in probes if isinstance(item, dict) and isinstance(item.get("id"), str)}
    missing_probes = sorted(REQUIRED_PROBE_IDS - probe_ids)
    if missing_probes:
        failures.append(f"required_probes missing: {missing_probes}")

    categories = category_map(contract)
    missing_categories = sorted(MINIMUM_FAILURE_CATEGORIES - set(categories))
    if missing_categories:
        failures.append(f"failure_categories missing: {missing_categories}")
    seen_match_signals: dict[tuple[str, ...], str] = {}
    category_exception_signals: dict[str, set[str]] = {}
    for category_id, category in categories.items():
        if category.get("transience") not in TRANSIENCE:
            failures.append(f"failure_categories.{category_id}.transience invalid")
        if not isinstance(category.get("retryable"), bool):
            failures.append(f"failure_categories.{category_id}.retryable must be boolean")
        if not isinstance(category.get("failure_layer"), str) or not category.get("failure_layer"):
            failures.append(f"failure_categories.{category_id}.failure_layer missing")
        if not isinstance(category.get("backoff_seconds"), int) or category.get("backoff_seconds") < 0:
            failures.append(f"failure_categories.{category_id}.backoff_seconds must be non-negative integer")
        match_signals = category.get("match_signals")
        if not isinstance(match_signals, list) or not match_signals:
            failures.append(f"failure_categories.{category_id}.match_signals must be a non-empty list")
        elif any(not isinstance(item, str) or not item for item in match_signals):
            failures.append(f"failure_categories.{category_id}.match_signals must contain non-empty strings")
        else:
            signature = tuple(sorted(match_signals))
            previous = seen_match_signals.get(signature)
            if previous:
                failures.append(f"failure_categories.{category_id}.match_signals duplicates {previous}")
            seen_match_signals[signature] = category_id
            exception_names = {name for signal in match_signals for name in extract_exception_names(signal)}
            generic_names = sorted(exception_names & GENERIC_EXCEPTION_NAMES)
            if generic_names:
                failures.append(
                    f"failure_categories.{category_id}.match_signals uses generic exception names: {generic_names}"
                )
            category_exception_signals[category_id] = exception_names
    for left_id, left_names in category_exception_signals.items():
        for right_id, right_names in category_exception_signals.items():
            if left_id >= right_id:
                continue
            for left_name in left_names:
                for right_name in right_names:
                    if exception_ancestor(left_name, right_name) or exception_ancestor(right_name, left_name):
                        failures.append(
                            "failure_categories exception signal overlap: "
                            f"{left_id}:{left_name} conflicts with {right_id}:{right_name}"
                        )

    fixtures = contract.get("fixtures")
    if not isinstance(fixtures, list):
        failures.append("fixtures must be a list")
        return failures
    fixture_ids = set()
    for index, fixture in enumerate(fixtures):
        if not isinstance(fixture, dict):
            failures.append(f"fixtures[{index}] must be object")
            continue
        fixture_id = fixture.get("id")
        if fixture_id not in SUPPORTED_FIXTURES:
            failures.append(f"fixtures[{index}].id unsupported")
        else:
            fixture_ids.add(fixture_id)
        if not isinstance(fixture.get("expected_ok"), bool):
            failures.append(f"fixtures[{index}].expected_ok must be boolean")
        expected_category = fixture.get("expected_category")
        if expected_category is not None and expected_category not in categories:
            failures.append(f"fixtures[{index}].expected_category not declared: {expected_category}")
    missing_fixtures = sorted(SUPPORTED_FIXTURES - fixture_ids)
    if missing_fixtures:
        failures.append(f"fixtures missing: {missing_fixtures}")
    return failures


def extract_exception_names(signal: str) -> set[str]:
    names: set[str] = set()
    for match in re.finditer(r"(?:exception|raises|class)\s*[=:]\s*([A-Za-z_][A-Za-z0-9_.]*)", signal):
        names.add(match.group(1))
    return names


def exception_ancestor(child: str, parent: str) -> bool:
    current = child
    visited: set[str] = set()
    while current in EXCEPTION_PARENTS and current not in visited:
        visited.add(current)
        current = EXCEPTION_PARENTS[current]
        if current == parent:
            return True
    return False


def fixture_signal(fixture: str) -> dict[str, Any]:
    if fixture == "healthy":
        return {
            "probe": "all",
            "ok": True,
            "exit_code": 0,
            "timed_out": False,
            "stderr": "",
            "elapsed_seconds": 0.1,
            "retry_count": 0,
        }
    signals: dict[str, dict[str, Any]] = {
        "path-error": {
            "probe": "path",
            "exit_code": None,
            "timed_out": False,
            "stderr": "command not found: kimi",
        },
        "permission-block": {
            "probe": "basic_call",
            "exit_code": 126,
            "timed_out": False,
            "stderr": "Permission denied while invoking provider",
        },
        "timeout": {
            "probe": "basic_call",
            "exit_code": None,
            "timed_out": True,
            "stderr": "subprocess timeout expired",
        },
        "session-resume-failure": {
            "probe": "session_resume",
            "exit_code": 1,
            "timed_out": False,
            "stderr": "session resume failed: session not found",
        },
        "file-budget-exceeded": {
            "probe": "bounded_file_read",
            "exit_code": 1,
            "timed_out": False,
            "stderr": "file read budget exceeded",
            "file_budget_exceeded": True,
        },
        "quota-exhausted": {
            "probe": "basic_call",
            "exit_code": 1,
            "timed_out": False,
            "stderr": "quota exhausted, rate limit exceeded",
        },
        "auth-failure": {
            "probe": "basic_call",
            "exit_code": 1,
            "timed_out": False,
            "stderr": "authentication failed, please login",
        },
        "connection-refused": {
            "probe": "basic_call",
            "exit_code": 1,
            "timed_out": False,
            "stderr": "ECONNREFUSED connection refused",
        },
        "unknown-failure": {
            "probe": "basic_call",
            "exit_code": 3,
            "timed_out": False,
            "stderr": "provider exited with an unrecognized error",
        },
    }
    if fixture not in signals:
        raise SystemExit(f"unsupported fixture: {fixture}")
    signal = signals[fixture]
    return {
        "ok": False,
        "elapsed_seconds": 0.2,
        "retry_count": 0,
        **signal,
    }


def classify_signal(signal: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    categories = category_map(contract)
    stderr = str(signal.get("stderr") or "").lower()
    category_id: str
    if signal.get("ok") is True:
        return {
            "category": None,
            "ok": True,
            "failure_layer": None,
            "transience": None,
            "retryable": None,
            "backoff_seconds": 0,
        }
    if signal.get("file_budget_exceeded") is True:
        category_id = "file_budget_exceeded"
    elif signal.get("timed_out") is True:
        category_id = "timeout"
    elif signal.get("probe") == "path" or "command not found" in stderr or "no such file" in stderr:
        category_id = "path_error"
    elif "permission denied" in stderr or signal.get("exit_code") == 126:
        category_id = "permission_block"
    elif signal.get("probe") == "session_resume" or "session resume" in stderr or "session not found" in stderr:
        category_id = "session_resume_failure"
    elif "quota" in stderr or "rate limit" in stderr:
        category_id = "quota_exhausted"
    elif "auth" in stderr or "login" in stderr or "unauthorized" in stderr:
        category_id = "auth_failure"
    elif "econnrefused" in stderr or "connection refused" in stderr:
        category_id = "connection_refused"
    elif signal.get("probe") == "version" and signal.get("exit_code") not in (0, None):
        category_id = "version_unavailable"
    else:
        category_id = "unknown"
    category = categories.get(category_id, {})
    return {
        "category": category_id,
        "ok": False,
        "failure_layer": category.get("failure_layer", "unknown"),
        "transience": category.get("transience", "unknown"),
        "retryable": category.get("retryable", True),
        "backoff_seconds": category.get("backoff_seconds", 0),
        "raw_exit_code": signal.get("exit_code"),
        "timed_out": signal.get("timed_out") is True,
        "elapsed_seconds": signal.get("elapsed_seconds"),
        "retry_count": signal.get("retry_count", 0),
    }


def compute_offline_report(contract: dict[str, Any], *, fixture: str) -> dict[str, Any]:
    contract_failures = validate_contract(contract)
    signal = fixture_signal(fixture)
    classification = classify_signal(signal, contract)
    fixtures = {
        item.get("id"): item
        for item in contract.get("fixtures", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    fixture_expectation = fixtures.get(fixture, {})
    failures = list(contract_failures)
    expected_category = fixture_expectation.get("expected_category")
    expected_ok = fixture_expectation.get("expected_ok")
    if fixture not in fixtures:
        failures.append(f"fixture not declared in contract: {fixture}")
    if expected_ok is not None and classification["ok"] is not expected_ok:
        failures.append(f"fixture {fixture} ok mismatch: expected {expected_ok}, got {classification['ok']}")
    if expected_category != classification["category"]:
        failures.append(
            f"fixture {fixture} category mismatch: expected {expected_category}, got {classification['category']}"
        )
    report_ok = not failures and classification["ok"] is True
    if fixture != "healthy":
        report_ok = False
    return {
        "schema_id": REPORT_SCHEMA_ID,
        "ok": report_ok,
        "mode": "offline",
        "fixture": fixture,
        "generated_at": iso_now(),
        "contract": rel(DEFAULT_CONTRACT),
        "required_probe_count": len(REQUIRED_PROBE_IDS),
        "failure_category_count": len(category_map(contract)),
        "live_check_included_in_aggregate": contract.get("live_check_policy", {}).get("included_in_aggregate"),
        "signal": {
            "probe": signal.get("probe"),
            "exit_code": signal.get("exit_code"),
            "timed_out": signal.get("timed_out") is True,
            "elapsed_seconds": signal.get("elapsed_seconds"),
            "retry_count": signal.get("retry_count", 0),
        },
        "classification": classification,
        "failures": failures,
    }


def command_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "argv_redacted": result.get("argv_redacted"),
        "ok": result.get("ok"),
        "exit_code": result.get("exit_code"),
        "timed_out": result.get("timed_out"),
        "elapsed_seconds": result.get("elapsed_seconds"),
        "stdout_sha256": result.get("stdout_sha256"),
        "stderr_sha256": result.get("stderr_sha256"),
        "stdout_bytes": result.get("stdout_bytes"),
        "stderr_bytes": result.get("stderr_bytes"),
        "classification": result.get("classification"),
    }


def redact_argv(argv: list[str]) -> list[str]:
    redacted: list[str] = []
    skip_value_for: str | None = None
    for item in argv:
        if skip_value_for == "prompt":
            redacted.append(f"<prompt sha256={sha256_text(item)} chars={len(item)}>")
            skip_value_for = None
            continue
        if skip_value_for == "session":
            redacted.append(f"<session sha256={sha256_text(item)} chars={len(item)}>")
            skip_value_for = None
            continue
        redacted.append(item)
        if item in {"-p", "--prompt"}:
            skip_value_for = "prompt"
        elif item in {"--session", "-S", "-r"}:
            skip_value_for = "session"
    return redacted


def run_provider_command(
    argv: list[str],
    *,
    cwd: pathlib.Path,
    timeout_seconds: int,
    contract: dict[str, Any],
    probe: str,
    retry_count: int = 0,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        elapsed = round(time.perf_counter() - started, 3)
        signal = {
            "probe": probe,
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "timed_out": False,
            "stderr": completed.stderr,
            "elapsed_seconds": elapsed,
            "retry_count": retry_count,
        }
        return {
            "argv_redacted": redact_argv(argv),
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "timed_out": False,
            "elapsed_seconds": elapsed,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "stdout_bytes": len(completed.stdout.encode("utf-8")),
            "stderr_bytes": len(completed.stderr.encode("utf-8")),
            "stdout_sha256": sha256_text(completed.stdout),
            "stderr_sha256": sha256_text(completed.stderr),
            "classification": classify_signal(signal, contract),
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = round(time.perf_counter() - started, 3)
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        signal = {
            "probe": probe,
            "ok": False,
            "exit_code": None,
            "timed_out": True,
            "stderr": stderr or "subprocess timeout expired",
            "elapsed_seconds": elapsed,
            "retry_count": retry_count,
        }
        return {
            "argv_redacted": redact_argv(argv),
            "ok": False,
            "exit_code": None,
            "timed_out": True,
            "elapsed_seconds": elapsed,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_bytes": len(stdout.encode("utf-8")),
            "stderr_bytes": len(stderr.encode("utf-8")),
            "stdout_sha256": sha256_text(stdout),
            "stderr_sha256": sha256_text(stderr),
            "classification": classify_signal(signal, contract),
        }


def extract_session_id(output: str) -> str | None:
    for line in output.splitlines():
        if "To resume this session:" in line or "session.resume_hint" in line:
            match = SESSION_RE.search(line)
            if match:
                value = match.group(1)
                return value if value.startswith("session_") else f"session_{value}"
    match = SESSION_RE.search(output)
    if match:
        value = match.group(1)
        return value if value.startswith("session_") else f"session_{value}"
    return None


def file_allowed(path: pathlib.Path, budget: dict[str, Any]) -> tuple[bool, str | None]:
    resolved = path.resolve()
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError:
        return False, "file is outside RedCap workspace"
    denied_parts = set(budget.get("denied_path_parts", []))
    if denied_parts & set(resolved.parts):
        return False, "file path includes denied path part"
    if resolved.name in set(budget.get("denied_filenames", [])):
        return False, "file name is denied"
    if resolved.suffix not in set(budget.get("allowed_extensions", [])):
        return False, "file extension is not allowed"
    if resolved.stat().st_size > int(budget.get("max_bytes_per_file", 0)):
        return False, "file exceeds max_bytes_per_file"
    return True, None


def live_check_kimi(args: argparse.Namespace, contract: dict[str, Any]) -> dict[str, Any]:
    failures = validate_contract(contract)
    budget = contract.get("file_access_budget", {}) if isinstance(contract.get("file_access_budget"), dict) else {}
    evidence_dir = pathlib.Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    marker = f"redcap-provider-health-{uuid.uuid4().hex[:12]}"
    file_marker = f"file-marker-{uuid.uuid4().hex[:12]}"
    source_file = evidence_dir / f"{dt.datetime.now().strftime('%Y%m%d%H%M%S')}-kimi-file-read-source.txt"
    source_file.write_text(f"marker={file_marker}\n", encoding="utf-8")
    allowed, denied_reason = file_allowed(source_file, budget)
    if not allowed:
        signal = {
            "probe": "bounded_file_read",
            "ok": False,
            "exit_code": None,
            "timed_out": False,
            "stderr": denied_reason or "file not allowed",
            "elapsed_seconds": 0,
            "retry_count": 0,
            "file_budget_exceeded": True,
        }
        failures.append(f"live generated probe file violates budget: {denied_reason}")
        file_budget_classification = classify_signal(signal, contract)
    else:
        file_budget_classification = None

    provider_path = shutil.which("kimi")
    probes: dict[str, Any] = {
        "path": {
            "ok": provider_path is not None,
            "path": provider_path,
            "classification": classify_signal({
                "probe": "path",
                "ok": provider_path is not None,
                "exit_code": 0 if provider_path else None,
                "timed_out": False,
                "stderr": "" if provider_path else "command not found: kimi",
                "elapsed_seconds": 0,
                "retry_count": 0,
            }, contract),
        }
    }
    if provider_path is None:
        failures.append("kimi executable not found")
        return {
            "schema_id": LIVE_SCHEMA_ID,
            "ok": False,
            "generated_at": iso_now(),
            "provider": "kimi",
            "contract": rel(DEFAULT_CONTRACT),
            "evidence_dir": rel(evidence_dir),
            "probes": probes,
            "failures": failures,
        }

    version = run_provider_command(
        [provider_path, "--version"],
        cwd=REPO_ROOT,
        timeout_seconds=max(5, min(args.timeout_seconds, 30)),
        contract=contract,
        probe="version",
    )
    probes["version"] = command_summary(version)
    if not version["ok"]:
        failures.append("kimi version probe failed")

    basic_prompt = f"这是 RedCap provider health 巡检。请记住标记 {marker}，并简短回复已记住该标记。"
    basic = run_provider_command(
        [provider_path, "-p", basic_prompt, "--output-format", "stream-json"],
        cwd=REPO_ROOT,
        timeout_seconds=args.timeout_seconds,
        contract=contract,
        probe="basic_call",
    )
    probes["basic_call"] = command_summary(basic)
    session_id = extract_session_id(str(basic.get("stdout") or ""))
    probes["basic_call"]["captured_session_id"] = session_id
    if not basic["ok"]:
        failures.append("kimi basic call failed")
    if not session_id:
        failures.append("kimi basic call did not expose session id")

    if session_id:
        resume_prompt = f"请只回答刚才让你记住的 RedCap provider health 标记。标记应包含 {marker}。"
        resume = run_provider_command(
            [provider_path, "--session", session_id, "-p", resume_prompt, "--output-format", "stream-json"],
            cwd=REPO_ROOT,
            timeout_seconds=args.timeout_seconds,
            contract=contract,
            probe="session_resume",
        )
        resume_ok = resume["ok"] and marker in str(resume.get("stdout") or "")
        if not resume_ok and resume["classification"].get("category") is None:
            resume["classification"] = classify_signal({
                "probe": "session_resume",
                "ok": False,
                "exit_code": resume.get("exit_code"),
                "timed_out": resume.get("timed_out"),
                "stderr": str(resume.get("stderr") or "session resume failed"),
                "elapsed_seconds": resume.get("elapsed_seconds"),
                "retry_count": 0,
            }, contract)
        probes["session_resume"] = {
            **command_summary(resume),
            "remembered_marker": resume_ok,
        }
        if not resume_ok:
            failures.append("kimi session resume did not preserve marker")

    session_continuity = {
        "session_id": session_id,
        "session_id_sha256": sha256_text(session_id) if session_id else None,
        "before_call": {
            "probe": "basic_call",
            "ok": basic.get("ok") if "basic" in locals() else False,
            "exit_code": basic.get("exit_code") if "basic" in locals() else None,
            "stdout_sha256": basic.get("stdout_sha256") if "basic" in locals() else None,
        },
        "after_call": {
            "probe": "session_resume",
            "ok": resume.get("ok") if "resume" in locals() else False,
            "exit_code": resume.get("exit_code") if "resume" in locals() else None,
            "stdout_sha256": resume.get("stdout_sha256") if "resume" in locals() else None,
        },
        "marker_comparison": {
            "marker_sha256": sha256_text(marker),
            "observed_in_resume": (
                bool(session_id)
                and "resume" in locals()
                and marker in str(resume.get("stdout") or "")
            ),
        },
    }
    session_state_marker_matched = session_continuity["marker_comparison"]["observed_in_resume"]

    if allowed:
        file_prompt = (
            "请读取这个本地文件并只回答 marker 等号后的值，不要输出其他内容："
            f"{source_file}"
        )
        file_read = run_provider_command(
            [provider_path, "-p", file_prompt, "--output-format", "stream-json"],
            cwd=REPO_ROOT,
            timeout_seconds=args.file_read_timeout_seconds,
            contract=contract,
            probe="bounded_file_read",
        )
        file_ok = file_read["ok"] and file_marker in str(file_read.get("stdout") or "")
        probes["bounded_file_read"] = {
            **command_summary(file_read),
            "source_file": rel(source_file),
            "source_file_sha256": sha256_file(source_file),
            "budget": budget,
            "marker_observed": file_ok,
        }
        if not file_ok:
            failures.append("kimi bounded file read did not return marker")
    else:
        probes["bounded_file_read"] = {
            "ok": False,
            "source_file": rel(source_file),
            "classification": file_budget_classification,
        }

    details: dict[str, str | None] = {}
    raw_outputs = {
        "version": version if "version" in locals() else None,
        "basic_call": basic if "basic" in locals() else None,
        "session_resume": resume if "resume" in locals() else None,
        "bounded_file_read": file_read if "file_read" in locals() else None,
    }
    for name, result in raw_outputs.items():
        if not isinstance(result, dict):
            continue
        stdout_path = evidence_dir / f"{name}.stdout.txt"
        stderr_path = evidence_dir / f"{name}.stderr.txt"
        stdout_path.write_text(str(result.get("stdout") or ""), encoding="utf-8")
        stderr_path.write_text(str(result.get("stderr") or ""), encoding="utf-8")
        details[f"{name}_stdout_path"] = rel(stdout_path)
        details[f"{name}_stderr_path"] = rel(stderr_path)

    return {
        "schema_id": LIVE_SCHEMA_ID,
        "ok": not failures,
        "generated_at": iso_now(),
        "provider": "kimi",
        "contract": rel(DEFAULT_CONTRACT),
        "evidence_dir": rel(evidence_dir),
        "live_check_included_in_aggregate": False,
        "timeout_seconds": args.timeout_seconds,
        "file_read_timeout_seconds": args.file_read_timeout_seconds,
        "provider_path": provider_path,
        "probes": probes,
        "session_continuity": session_continuity,
        "session_state_marker_matched": session_state_marker_matched,
        "details": details,
        "failures": failures,
    }


def cmd_check(args: argparse.Namespace) -> int:
    contract = load_json(pathlib.Path(args.contract).resolve())
    if not isinstance(contract, dict):
        raise SystemExit("contract must be a JSON object")
    report = compute_offline_report(contract, fixture=args.fixture)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["ok"]:
        print("REDCAP_PROVIDER_HEALTH_OK")
        return 0
    return 1


def cmd_self_check(args: argparse.Namespace) -> int:
    contract = load_json(pathlib.Path(args.contract).resolve())
    if not isinstance(contract, dict):
        raise SystemExit("contract must be a JSON object")
    cases = [
        ("healthy", True, None),
        ("path-error", False, "path_error"),
        ("permission-block", False, "permission_block"),
        ("timeout", False, "timeout"),
        ("session-resume-failure", False, "session_resume_failure"),
        ("file-budget-exceeded", False, "file_budget_exceeded"),
        ("quota-exhausted", False, "quota_exhausted"),
        ("auth-failure", False, "auth_failure"),
        ("connection-refused", False, "connection_refused"),
        ("unknown-failure", False, "unknown"),
    ]
    failures: list[str] = []
    results: list[dict[str, Any]] = []
    for fixture, expected_ok, expected_category in cases:
        report = compute_offline_report(contract, fixture=fixture)
        category = report.get("classification", {}).get("category")
        ok = report.get("ok") is True
        results.append({
            "fixture": fixture,
            "ok": ok,
            "expected_ok": expected_ok,
            "category": category,
            "expected_category": expected_category,
            "failures": report.get("failures", []),
        })
        if ok is not expected_ok:
            failures.append(f"fixture {fixture} expected ok={expected_ok}, got {ok}")
        if category != expected_category:
            failures.append(f"fixture {fixture} expected category={expected_category}, got {category}")
    payload = {
        "schema_id": SELF_CHECK_SCHEMA_ID,
        "ok": not failures,
        "cases": results,
        "failures": failures,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_PROVIDER_HEALTH_SELF_CHECK_OK")
    return 0


def cmd_live_check(args: argparse.Namespace) -> int:
    contract = load_json(pathlib.Path(args.contract).resolve())
    if not isinstance(contract, dict):
        raise SystemExit("contract must be a JSON object")
    if args.provider != "kimi":
        raise SystemExit("live-check currently supports provider: kimi")
    report = live_check_kimi(args, contract)
    out_path = pathlib.Path(args.out).resolve() if args.out else (
        pathlib.Path(args.evidence_dir).resolve() / f"{dt.datetime.now().strftime('%Y%m%d%H%M%S')}-kimi-live-report.json"
    )
    write_json(out_path, report)
    summary = {
        "schema_id": "redcap-provider-health-live-summary",
        "ok": report["ok"],
        "provider": report["provider"],
        "report_path": rel(out_path),
        "provider_path": report.get("provider_path"),
        "probe_status": {
            name: probe.get("ok") if isinstance(probe, dict) else None
            for name, probe in report.get("probes", {}).items()
        },
        "failures": report.get("failures", []),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if report["ok"]:
        print("REDCAP_PROVIDER_HEALTH_LIVE_OK")
        return 0
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查 provider（评审方工具）健康状态")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check")
    check.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    check.add_argument("--fixture", choices=sorted(SUPPORTED_FIXTURES), default="healthy")
    self_check = subparsers.add_parser("self-check")
    self_check.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    live = subparsers.add_parser("live-check")
    live.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    live.add_argument("--provider", choices=["kimi"], default="kimi")
    live.add_argument("--timeout-seconds", type=int, default=30)
    live.add_argument("--file-read-timeout-seconds", type=int, default=45)
    live.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE_DIR))
    live.add_argument("--out")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check(args)
    if args.command == "self-check":
        return cmd_self_check(args)
    if args.command == "live-check":
        return cmd_live_check(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Codex host hook adapter for RedCap."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "runtime" / "core"))
from prompt_intent import classify_prompt_intent  # noqa: E402

HOOKS_CONFIG = REPO_ROOT / ".codex" / "hooks.json"
EVIDENCE_DIR = pathlib.Path(
    os.environ.get(
        "REDCAP_CODEX_HOOK_EVIDENCE_DIR",
        str(REPO_ROOT / "assets" / "evidence" / "host-hooks" / "codex"),
    )
)
EVENTS_PATH = EVIDENCE_DIR / "events.jsonl"
REDCAP = REPO_ROOT / "runtime" / "bin" / "redcap"
TURN_ACTION_CHECK = REPO_ROOT / "runtime" / "prism" / "bin" / "turn-action-check"
FINAL_CLAIM_GUARD = REPO_ROOT / "runtime" / "core" / "final_claim_guard.py"
HUMAN_OUTPUT_POLICY = REPO_ROOT / "runtime" / "core" / "human_output_policy.py"
SCAN_CONCLUSION_GUARD = REPO_ROOT / "runtime" / "core" / "scan_conclusion_guard.py"
TERMINAL_GOAL_GUARD = REPO_ROOT / "runtime" / "core" / "terminal_goal_guard.py"
TERMINAL_GOAL_CONTRACT = pathlib.Path(
    os.environ.get("REDCAP_TERMINAL_GOAL_CONTRACT", str(REPO_ROOT / "assets" / "contracts" / "terminal-goals.json"))
)
TERMINAL_GOAL_TASK_FACTS = pathlib.Path(
    os.environ.get("REDCAP_TERMINAL_GOAL_TASK_FACTS", str(REPO_ROOT / "assets" / "evidence" / "task-facts" / "task-facts.jsonl"))
)
STOP_HOOK_MODE_FILE = pathlib.Path(os.environ.get("REDCAP_STOP_HOOK_MODE_FILE", str(REPO_ROOT / ".codex" / "stop-hook-mode")))
STOP_HOOK_MODE_FILE_MAX_AGE_SECONDS = float(os.environ.get("REDCAP_STOP_HOOK_MODE_FILE_MAX_AGE_SECONDS", "900"))
STOP_INCLUDE_BLOCKED_REPLY_EXCERPT = (
    os.environ.get("REDCAP_STOP_INCLUDE_BLOCKED_REPLY_EXCERPT", "").casefold()
    in {"1", "true", "yes", "on"}
)
SUPPORTED_EVENTS = {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}
INTENT_JUDGE_TIMEOUT_SECONDS = float(os.environ.get("REDCAP_INTENT_JUDGE_TIMEOUT_SECONDS", "75"))
INTENT_JUDGE_PROVIDER = os.environ.get("REDCAP_INTENT_JUDGE_PROVIDER", "claude-code")
INTENT_JUDGE_FALLBACK_PROVIDER = os.environ.get("REDCAP_INTENT_JUDGE_FALLBACK_PROVIDER", "claude-code")
INTENT_JUDGE_FAKE_RESPONSE = os.environ.get("REDCAP_INTENT_JUDGE_FAKE_RESPONSE")
INTENT_JUDGE_FAKE_DELAY_SECONDS = os.environ.get("REDCAP_INTENT_JUDGE_FAKE_DELAY_SECONDS")
GATE_SEMANTIC_POLICY = os.environ.get("REDCAP_GATE_SEMANTIC_POLICY", "auto-on-ambiguous")
GATE_SEMANTIC_TIMEOUT_SECONDS = os.environ.get("REDCAP_GATE_SEMANTIC_TIMEOUT_SECONDS", "8")
GATE_COMMAND_TIMEOUT_SECONDS = float(os.environ.get("REDCAP_GATE_COMMAND_TIMEOUT_SECONDS", "12"))
GATE_SEMANTIC_FAKE_RESPONSE = os.environ.get("REDCAP_GATE_SEMANTIC_FAKE_RESPONSE") or INTENT_JUDGE_FAKE_RESPONSE
GATE_SEMANTIC_FAKE_DELAY_SECONDS = (
    os.environ.get("REDCAP_GATE_SEMANTIC_FAKE_DELAY_SECONDS") or INTENT_JUDGE_FAKE_DELAY_SECONDS
)
MAX_GATE_PROMPT_CHARS = 12000
MAX_TEXT_EVIDENCE_CHARS = 12000
PROTECTED_EVIDENCE_ROOT = (REPO_ROOT / "assets" / "evidence").resolve()
PROTECTED_PRISM_EVIDENCE_ROOT = (REPO_ROOT / "assets" / "evidence" / "prism").resolve()
PROTECTED_EVIDENCE_PATH_PATTERN = r"['\"]?(?:\./)?(?:assets/evidence/|[^'\"\s;|&]*?/assets/evidence/)"
BROAD_RAW_READ_COMMANDS = {
    "awk",
    "bat",
    "batcat",
    "cat",
    "grep",
    "head",
    "jq",
    "less",
    "more",
    "node",
    "perl",
    "python",
    "python3",
    "rg",
    "ruby",
    "sed",
    "tail",
}
PRISM_RAW_PATH_REGEX = re.compile(
    r"(?:assets/evidence/prism/|[^'\"\s;|&()]*?/assets/evidence/prism/)[^'\"\s;|&()]*\.raw\.json\b"
)
PRISM_RAW_META_PATH_REGEX = re.compile(
    r"(?:assets/evidence/prism/|[^'\"\s;|&()]*?/assets/evidence/prism/)[^'\"\s;|&()]*\.raw\.meta\.json\b"
)
PRISM_RAW_READ_BLOCK_REASON = (
    "Broad reads of Prism raw provider output are blocked; run prism-dispatch --verify-raw-meta "
    "to get a verified small metadata summary."
)
SHELL_REDIRECT_TOKENS = {
    ">",
    ">>",
    ">|",
    "<>",
    "0<>",
    "1>",
    "1>>",
    "1>|",
    "2>",
    "2>>",
    "2>|",
    "&>",
    "&>>",
}


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_hook_input() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"_invalid_json": True}
    return payload if isinstance(payload, dict) else {"_non_object_json": True}


def short_text_fingerprint(value: Any) -> dict[str, Any]:
    text = value if isinstance(value, str) else ""
    return {
        "present": isinstance(value, str),
        "length": len(text),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None,
    }


def normalized_text(value: str) -> str:
    return " ".join(value.split())


def text_evidence(value: Any) -> dict[str, Any]:
    text = value if isinstance(value, str) else ""
    normalized = normalized_text(text)
    evidence = short_text_fingerprint(value)
    evidence.update({
        "normalized_excerpt": normalized[:MAX_TEXT_EVIDENCE_CHARS],
        "normalized_excerpt_truncated": len(normalized) > MAX_TEXT_EVIDENCE_CHARS,
    })
    return evidence


def json_fingerprint(value: Any) -> dict[str, Any]:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload: dict[str, Any] = {
        "type": type(value).__name__,
        "sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "length": len(encoded),
    }
    if isinstance(value, dict):
        payload["keys"] = sorted(str(key) for key in value.keys())
    return payload


def run_command(argv: list[str], timeout_seconds: float | None = None) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            argv,
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        return {
            "argv": argv,
            "exit_code": 124,
            "timed_out": True,
            "timeout_seconds": timeout_seconds,
            "stdout_length": len(stdout),
            "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest() if stdout else None,
            "stderr_length": len(stderr),
            "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest() if stderr else None,
            "stdout": stdout,
            "stderr": stderr,
        }
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    return {
        "argv": argv,
        "exit_code": completed.returncode,
        "timed_out": False,
        "timeout_seconds": timeout_seconds,
        "stdout_length": len(stdout),
        "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest() if stdout else None,
        "stderr_length": len(stderr),
        "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest() if stderr else None,
        "stdout": stdout,
        "stderr": stderr,
    }


def terminal_goal_guard_args() -> list[str]:
    return [
        "--contract",
        str(TERMINAL_GOAL_CONTRACT),
        "--task-facts",
        str(TERMINAL_GOAL_TASK_FACTS),
    ]


@contextlib.contextmanager
def evidence_lock() -> Any:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = EVIDENCE_DIR / ".events.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def write_json_atomic(path: pathlib.Path, payload: dict[str, Any]) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def parse_leading_json_object(stdout: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        parsed, _ = json.JSONDecoder().raw_decode(stdout.lstrip())
    except json.JSONDecodeError as exc:
        return None, str(exc)
    if not isinstance(parsed, dict):
        return None, "leading JSON value is not an object"
    return parsed, None


def stop_hook_mode() -> str:
    mode = None
    if STOP_HOOK_MODE_FILE.exists():
        try:
            age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromtimestamp(
                STOP_HOOK_MODE_FILE.stat().st_mtime,
                dt.timezone.utc,
            )
        except OSError:
            age = dt.timedelta(seconds=STOP_HOOK_MODE_FILE_MAX_AGE_SECONDS + 1)
        if age.total_seconds() <= STOP_HOOK_MODE_FILE_MAX_AGE_SECONDS:
            mode = STOP_HOOK_MODE_FILE.read_text(encoding="utf-8").strip()
    if mode is None:
        mode = os.environ.get("REDCAP_STOP_HOOK_MODE")
    normalized = (mode or "enforce").casefold()
    if normalized in {"observe", "observation", "log", "disabled", "off"}:
        return "observe"
    return "enforce"


def stop_self_check_skips_full_check(payload: dict[str, Any]) -> bool:
    source = payload.get("source")
    return (
        os.environ.get("REDCAP_STOP_SKIP_FULL_CHECK_FOR_SELF_CHECK") == "1"
        and isinstance(source, str)
        and source.startswith("codex-hook-")
        and source.endswith("self-check")
    )


def stop_task_anchor_clause(action_result: dict[str, Any]) -> str:
    anchor = action_result.get("task_anchor")
    if not isinstance(anchor, dict):
        return ""
    excerpt = anchor.get("prompt_excerpt")
    prompt_sha = anchor.get("prompt_sha256")
    turn_id = anchor.get("turn_id")
    parts: list[str] = []
    if isinstance(excerpt, str) and excerpt.strip():
        parts.append(f'Original task excerpt: "{excerpt.strip()}".')
    if isinstance(prompt_sha, str) and prompt_sha.strip():
        parts.append(f"Original prompt sha256: {prompt_sha.strip()}.")
    if isinstance(turn_id, str) and turn_id.strip():
        parts.append(f"Original turn_id: {turn_id.strip()}.")
    parts.append(recovery_focus_clause())
    return " ".join(parts)


def recovery_focus_clause() -> str:
    return (
        "恢复规则：二次回答必须先直接回答原始用户问题，并保持原问题为主轴；"
        "本停止前检查的拦截意见只是一组修正约束，不是新的用户问题，也不得成为回复主题；"
        "除非原用户问题询问钩子本身，否则不要展开钩子细节；"
        "如果无法满足原任务，请明确标记受阻并给出阻塞条件。"
    )


def blocked_reply_excerpt(message: str, limit: int = 160) -> str:
    if not STOP_INCLUDE_BLOCKED_REPLY_EXCERPT:
        return ""
    normalized = normalized_text(message)
    if not normalized:
        return ""
    excerpt = normalized[:limit]
    if len(normalized) > limit:
        excerpt = f"{excerpt}..."
    return f" 被拦回复片段（仅用于定位，不得作为回答主题，不代表有效结论）：{excerpt}"


def run_prompt_gate(
    payload: dict[str, Any],
    prompt: str,
    *,
    semantic_policy: str | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    trimmed = prompt[:MAX_GATE_PROMPT_CHARS]
    policy = semantic_policy if semantic_policy is not None else GATE_SEMANTIC_POLICY
    argv = [
        str(REDCAP),
        "gate",
        "--task",
        trimmed,
        "--risk-level",
        "medium",
        "--tag",
        "codex-user-prompt",
        "--tag",
        "codex-hook",
        "--semantic-policy",
        policy,
        "--semantic-provider",
        INTENT_JUDGE_PROVIDER,
        "--semantic-fallback-provider",
        INTENT_JUDGE_FALLBACK_PROVIDER,
        "--semantic-timeout-seconds",
        str(GATE_SEMANTIC_TIMEOUT_SECONDS),
    ]
    if GATE_SEMANTIC_FAKE_RESPONSE:
        argv.extend(["--semantic-fake-response", GATE_SEMANTIC_FAKE_RESPONSE])
    if GATE_SEMANTIC_FAKE_DELAY_SECONDS:
        argv.extend(["--semantic-fake-delay-seconds", str(GATE_SEMANTIC_FAKE_DELAY_SECONDS)])
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        argv.extend(["--boundary-cwd", cwd])
    command = run_command(argv, timeout_seconds=timeout_seconds)
    result: dict[str, Any] = {
        "exit_code": command["exit_code"],
        "timed_out": command.get("timed_out", False),
        "timeout_seconds": command.get("timeout_seconds"),
        "prompt_truncated": len(prompt) > len(trimmed),
        "stdout_length": command["stdout_length"],
        "stdout_sha256": command["stdout_sha256"],
        "stderr_length": command["stderr_length"],
        "stderr_sha256": command["stderr_sha256"],
    }
    try:
        parsed = json.loads(command["stdout"])
    except json.JSONDecodeError:
        result["parse_ok"] = False
        result["decision"] = None
        result["matched_rules"] = []
        result["review_mode"] = None
    else:
        result["parse_ok"] = isinstance(parsed, dict)
        result["decision"] = parsed.get("decision") if isinstance(parsed, dict) else None
        result["matched_rules"] = parsed.get("matched_rules", []) if isinstance(parsed, dict) else []
        result["review_mode"] = parsed.get("review_mode") if isinstance(parsed, dict) else None
        result["required_providers"] = parsed.get("required_providers", []) if isinstance(parsed, dict) else []
        result["self_development_lifecycle"] = (
            parsed.get("self_development_lifecycle", {}) if isinstance(parsed, dict) else {}
        )
        result["semantic_gate"] = parsed.get("semantic_gate", {}) if isinstance(parsed, dict) else {}
    return result


def semantic_prompt_intent_from_gate(gate: dict[str, Any]) -> dict[str, Any] | None:
    semantic_gate = gate.get("semantic_gate")
    if not isinstance(semantic_gate, dict):
        return None
    if semantic_gate.get("source") == "deterministic" and semantic_gate.get("llm_judgment_applied") is not True:
        return None
    intent = semantic_gate.get("prompt_intent")
    if not isinstance(intent, dict):
        return None
    scope = intent.get("authorized_scope")
    evidence = intent.get("action_evidence")
    kind = intent.get("prompt_kind")
    if isinstance(scope, str) and isinstance(evidence, str) and isinstance(kind, str):
        return intent
    return None


def tool_command(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input") or {}
    if isinstance(tool_input, dict):
        return str(tool_input.get("command") or tool_input.get("cmd") or "")
    return ""


def shell_tokens(command: str) -> list[str]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        try:
            return shlex.split(command, posix=True)
        except ValueError:
            return []


def command_name(token: str) -> str:
    return pathlib.PurePosixPath(token).name.lower()


def expand_shell_path_value(value: str, cwd: str | None) -> str:
    cwd_value = str(pathlib.Path(cwd).expanduser()) if cwd else str(REPO_ROOT)
    home_value = str(pathlib.Path.home())
    expanded = value
    expanded = re.sub(r"\$\{PWD\}", cwd_value, expanded)
    expanded = re.sub(r"\$PWD\b", cwd_value, expanded)
    expanded = re.sub(r"\$\{HOME\}", home_value, expanded)
    expanded = re.sub(r"\$HOME\b", home_value, expanded)
    return os.path.expandvars(os.path.expanduser(expanded))


def path_value_under_protected_evidence(value: str, cwd: str | None = None) -> bool:
    if not value:
        return False
    candidate = pathlib.Path(expand_shell_path_value(value, cwd))
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return is_under(candidate, PROTECTED_EVIDENCE_ROOT)


def path_value_is_prism_raw(value: str, cwd: str | None = None) -> bool:
    if not value or ".raw.meta.json" in value:
        return False
    expanded = expand_shell_path_value(value, cwd)
    if any(char in expanded for char in "*?[]"):
        normalized = expanded.replace("\\", "/")
        return "assets/evidence/prism/" in normalized and normalized.endswith(".raw.json")
    candidate = pathlib.Path(expanded)
    if not candidate.is_absolute():
        candidate = pathlib.Path(cwd if cwd else REPO_ROOT) / candidate
    return candidate.name.endswith(".raw.json") and is_under(candidate, PROTECTED_PRISM_EVIDENCE_ROOT)


def path_value_is_prism_raw_meta(value: str, cwd: str | None = None) -> bool:
    if not value:
        return False
    expanded = expand_shell_path_value(value, cwd)
    if any(char in expanded for char in "*?[]"):
        normalized = expanded.replace("\\", "/")
        return "assets/evidence/prism/" in normalized and normalized.endswith(".raw.meta.json")
    candidate = pathlib.Path(expanded)
    if not candidate.is_absolute():
        candidate = pathlib.Path(cwd if cwd else REPO_ROOT) / candidate
    return candidate.name.endswith(".raw.meta.json") and is_under(candidate, PROTECTED_PRISM_EVIDENCE_ROOT)


def any_prism_raw_path(tokens: list[str], start: int = 0, cwd: str | None = None) -> bool:
    for token in tokens[start:]:
        if token in {";", "|", "||", "&&"}:
            break
        if token.startswith("-"):
            continue
        if path_value_is_prism_raw(token, cwd):
            return True
    return False


def any_prism_raw_meta_path(tokens: list[str], start: int = 0, cwd: str | None = None) -> bool:
    for token in tokens[start:]:
        if token in {";", "|", "||", "&&"}:
            break
        if token.startswith("-"):
            continue
        if path_value_is_prism_raw_meta(token, cwd):
            return True
    return False


def path_value_intersects_prism_evidence(value: str, cwd: str | None = None) -> bool:
    if not value:
        return False
    expanded = expand_shell_path_value(value, cwd)
    if any(char in expanded for char in "*?[]"):
        normalized = expanded.replace("\\", "/")
        return "assets/evidence/prism" in normalized or "assets/evidence" in normalized
    candidate = pathlib.Path(expanded)
    if not candidate.is_absolute():
        candidate = pathlib.Path(cwd if cwd else REPO_ROOT) / candidate
    try:
        resolved = candidate.resolve()
        prism = PROTECTED_PRISM_EVIDENCE_ROOT.resolve()
        evidence = PROTECTED_EVIDENCE_ROOT.resolve()
        resolved.relative_to(prism)
        return True
    except ValueError:
        pass
    try:
        prism.relative_to(resolved)
        return resolved == prism or resolved == evidence
    except ValueError:
        return False


def search_command_excludes_prism_raw(command: str) -> bool:
    normalized = command.replace('"', "'")
    return (
        ("!*.raw.json" in normalized or "!**/*.raw.json" in normalized)
        and ("!*.raw.meta.json" in normalized or "!**/*.raw.meta.json" in normalized)
    )


def search_over_prism_evidence_without_raw_exclusion(tokens: list[str], index: int, command: str, cwd: str | None) -> bool:
    if search_command_excludes_prism_raw(command):
        return False
    for token in tokens[index + 1 :]:
        if token in {";", "|", "||", "&&"}:
            break
        if token.startswith("-"):
            continue
        if path_value_intersects_prism_evidence(token, cwd):
            return True
    return False


def command_contains_prism_raw_hint(command: str) -> bool:
    normalized = command.replace("\\", "/")
    return ".raw.json" in normalized and all(part in normalized for part in ["assets", "evidence", "prism"])


def command_contains_prism_raw_meta_hint(command: str) -> bool:
    normalized = command.replace("\\", "/")
    return ".raw.meta.json" in normalized and all(part in normalized for part in ["assets", "evidence", "prism"])


def prism_raw_read_reason(command: str, cwd: str | None = None) -> str | None:
    if "--verify-raw-meta" in command:
        return None
    for segment in re.split(r"\s*(?:&&|\|\||;|\||\n)\s*", command):
        if not segment.strip():
            continue
        reason = prism_raw_read_reason_for_segment(segment, cwd)
        if reason is not None:
            return reason
    return None


def prism_raw_read_reason_for_segment(command: str, cwd: str | None = None) -> str | None:
    tokens = shell_tokens(command)
    if not tokens:
        if PRISM_RAW_PATH_REGEX.search(command) or PRISM_RAW_META_PATH_REGEX.search(command):
            return PRISM_RAW_READ_BLOCK_REASON
        return None
    for index, token in enumerate(tokens):
        name = command_name(token)
        if name in {"rg", "grep"} and search_over_prism_evidence_without_raw_exclusion(tokens, index, command, cwd):
            return PRISM_RAW_READ_BLOCK_REASON
        if name in BROAD_RAW_READ_COMMANDS and any_prism_raw_path(tokens, index + 1, cwd):
            return PRISM_RAW_READ_BLOCK_REASON
        if name in BROAD_RAW_READ_COMMANDS and any_prism_raw_meta_path(tokens, index + 1, cwd):
            return PRISM_RAW_READ_BLOCK_REASON
        if name in BROAD_RAW_READ_COMMANDS and PRISM_RAW_PATH_REGEX.search(command):
            return PRISM_RAW_READ_BLOCK_REASON
        if name in BROAD_RAW_READ_COMMANDS and PRISM_RAW_META_PATH_REGEX.search(command):
            return PRISM_RAW_READ_BLOCK_REASON
        if name in BROAD_RAW_READ_COMMANDS and command_contains_prism_raw_hint(command):
            return PRISM_RAW_READ_BLOCK_REASON
        if name in BROAD_RAW_READ_COMMANDS and command_contains_prism_raw_meta_hint(command):
            return PRISM_RAW_READ_BLOCK_REASON
    return None


def protected_prism_raw_read_reason(payload: dict[str, Any]) -> str | None:
    tool_name = str(payload.get("tool_name") or "")
    if tool_name not in {"Read", "Open", "View"}:
        return None
    for raw_path in iter_tool_paths(payload.get("tool_input")):
        if path_value_is_prism_raw(raw_path, payload.get("cwd") if isinstance(payload.get("cwd"), str) else None):
            return "Direct host reads of Prism raw provider output are blocked; run prism-dispatch --verify-raw-meta."
        if path_value_is_prism_raw_meta(raw_path, payload.get("cwd") if isinstance(payload.get("cwd"), str) else None):
            return "Direct host reads of Prism raw metadata are blocked; run prism-dispatch --verify-raw-meta."
    return None


def any_protected_evidence_path(tokens: list[str], start: int = 0, cwd: str | None = None) -> bool:
    for token in tokens[start:]:
        if token in {";", "|", "||", "&&"}:
            break
        if token.startswith("-"):
            continue
        if path_value_under_protected_evidence(token, cwd):
            return True
    return False


def option_path_under_protected(
    tokens: list[str],
    index: int,
    *,
    separate_options: set[str],
    joined_prefixes: set[str],
    equals_prefixes: set[str],
    cwd: str | None,
) -> bool:
    token = tokens[index]
    if token in separate_options:
        return index + 1 < len(tokens) and path_value_under_protected_evidence(tokens[index + 1], cwd)
    for prefix in joined_prefixes:
        if token.startswith(prefix) and len(token) > len(prefix):
            return path_value_under_protected_evidence(token[len(prefix) :], cwd)
    for prefix in equals_prefixes:
        if token.startswith(prefix):
            return path_value_under_protected_evidence(token.split("=", 1)[1], cwd)
    return False


def download_output_under_protected(tokens: list[str], index: int, cwd: str | None) -> bool:
    name = command_name(tokens[index])
    args = tokens[index + 1 :]
    if name == "curl":
        for offset, _ in enumerate(args):
            if option_path_under_protected(
                args,
                offset,
                separate_options={"-o", "--output", "--output-dir"},
                joined_prefixes={"-o"},
                equals_prefixes={"--output=", "--output-dir="},
                cwd=cwd,
            ):
                return True
    if name == "wget":
        for offset, _ in enumerate(args):
            if option_path_under_protected(
                args,
                offset,
                separate_options={"-O", "--output-document", "-P", "--directory-prefix"},
                joined_prefixes={"-O", "-P"},
                equals_prefixes={"--output-document=", "--directory-prefix="},
                cwd=cwd,
            ):
                return True
    return False


def shell_evidence_write_reason(command: str, cwd: str | None = None) -> str | None:
    tokens = shell_tokens(command)
    if not tokens:
        if re.search(r"(?:>|>>|\btee\s+)\s*" + PROTECTED_EVIDENCE_PATH_PATTERN, command):
            return "Direct shell writes into assets/evidence are blocked; use RedCap evidence writers instead."
        return None

    for index, token in enumerate(tokens):
        if token in SHELL_REDIRECT_TOKENS:
            if index + 1 < len(tokens) and path_value_under_protected_evidence(tokens[index + 1], cwd):
                return "Direct shell writes into assets/evidence are blocked; use RedCap evidence writers instead."
            continue
        if ">" in token and token not in {">", ">>"}:
            suffix = token.split(">", 1)[1]
            if suffix and path_value_under_protected_evidence(suffix, cwd):
                return "Direct shell writes into assets/evidence are blocked; use RedCap evidence writers instead."

    for index, token in enumerate(tokens):
        name = command_name(token)
        if name == "tee" and any_protected_evidence_path(tokens, index + 1, cwd):
            return "Direct shell writes into assets/evidence are blocked; use RedCap evidence writers instead."
        if name in {"cp", "mv", "install", "rsync", "ditto"} and any_protected_evidence_path(tokens, index + 1, cwd):
            return "Filesystem copy/move into assets/evidence is blocked; use RedCap evidence writers instead."
        if name in {"sed", "perl"}:
            has_in_place = any(
                option == "-i" or (option.startswith("-") and "i" in option[1:])
                for option in tokens[index + 1 :]
            )
            if has_in_place and any_protected_evidence_path(tokens, index + 1, cwd):
                return "In-place edit of assets/evidence is blocked; use RedCap evidence writers instead."
        if name == "dd":
            for item in tokens[index + 1 :]:
                if item.startswith("of=") and path_value_under_protected_evidence(item.split("=", 1)[1], cwd):
                    return "dd write into assets/evidence is blocked; use RedCap evidence writers instead."
        if name in {"curl", "wget"} and download_output_under_protected(tokens, index, cwd):
            return "Download write into assets/evidence is blocked; use RedCap evidence writers instead."
    return None


def dangerous_command_reason(command: str, cwd: str | None = None) -> str | None:
    checks = [
        (r"\bgit\s+reset\s+--hard\b", "git reset --hard is destructive and must not run under RedCap policy."),
        (r"\bgit\s+checkout\s+--\b", "git checkout -- can erase user changes and must not run without explicit recovery approval."),
        (r"\bnpm\s+publish\b", "npm publish is blocked until an explicit release task opens the publish gate."),
        (r"\brm\s+(-[^\s]*r[^\s]*f|-rf|-fr)\b.*\bassets/evidence/prism\b", "Direct recursive removal of Prism evidence is blocked."),
    ]
    for pattern, reason in checks:
        if re.search(pattern, command):
            return reason
    return prism_raw_read_reason(command, cwd) or shell_evidence_write_reason(command, cwd)


def iter_tool_paths(value: Any) -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"path", "file_path", "filename", "target_file", "notebook_path"} and isinstance(item, str):
                paths.append(item)
            else:
                paths.extend(iter_tool_paths(item))
    elif isinstance(value, list):
        for item in value:
            paths.extend(iter_tool_paths(item))
    return paths


def is_under(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        path.resolve().relative_to(root)
    except ValueError:
        return False
    return True


def protected_evidence_write_reason(payload: dict[str, Any]) -> str | None:
    tool_name = str(payload.get("tool_name") or "")
    if tool_name not in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        return None
    tool_input = payload.get("tool_input")
    for raw_path in iter_tool_paths(tool_input):
        candidate = pathlib.Path(raw_path)
        if not candidate.is_absolute():
            cwd = payload.get("cwd")
            candidate = pathlib.Path(cwd if isinstance(cwd, str) and cwd else REPO_ROOT) / candidate
        if is_under(candidate, PROTECTED_EVIDENCE_ROOT):
            return "Direct Write/Edit/MultiEdit into assets/evidence is blocked; use RedCap evidence writers instead."
    return None


def unwrap_command(parts: list[str]) -> list[str]:
    parts = list(parts)
    while parts and parts[0] in {"sudo", "command", "exec", "nohup", "noglob"}:
        parts = parts[1:]
    if parts and parts[0] == "env":
        parts = parts[1:]
        while parts and (parts[0].startswith("-") or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", parts[0])):
            parts = parts[1:]
    if parts and parts[0] in {"timeout", "gtimeout"}:
        parts = parts[1:]
        while parts and parts[0].startswith("-"):
            parts = parts[1:]
        if parts:
            parts = parts[1:]
    return parts


def command_is_mutating(command: str) -> bool:
    mutating_commands = {"chmod", "mv", "rm", "rmdir", "cp", "mkdir", "touch"}
    for segment in re.split(r"\s*(?:&&|\|\||;)\s*", command):
        try:
            parts = shlex.split(segment)
        except ValueError:
            parts = segment.split()
        parts = unwrap_command(parts)
        if not parts:
            continue
        head = parts[0]
        if head in mutating_commands:
            return True
        if head == "git" and len(parts) > 1 and parts[1] in {"add", "commit", "mv", "rm"}:
            return True
        if head == "sed" and any(part.startswith("-") and "i" in part and not part.startswith("--") for part in parts[1:]):
            return True
        if head == "perl" and any(part.startswith("-") and "p" in part and "i" in part and not part.startswith("--") for part in parts[1:]):
            return True
    return False


def tool_is_mutating(payload: dict[str, Any], command: str) -> bool:
    tool_name = str(payload.get("tool_name") or "")
    mutating_tools = {"apply_patch", "Edit", "Write", "MultiEdit", "NotebookEdit"}
    return tool_name in mutating_tools or command_is_mutating(command)


def latest_user_prompt_marker() -> dict[str, Any]:
    latest = EVIDENCE_DIR / "latest-UserPromptSubmit.json"
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def effective_prompt_intent(prompt_marker: dict[str, Any]) -> dict[str, Any] | None:
    for key in ["prompt_intent_effective", "prompt_intent"]:
        intent = prompt_marker.get(key)
        if isinstance(intent, dict):
            return intent
    return None


def prompt_intent_allows_mutation(prompt_marker: dict[str, Any]) -> bool:
    intent = effective_prompt_intent(prompt_marker)
    if not isinstance(intent, dict):
        return True
    return intent.get("authorized_scope") in {"implementation", "completion"}


def prompt_text_from_marker(prompt_marker: dict[str, Any]) -> str:
    prompt = prompt_marker.get("prompt")
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, dict):
        excerpt = prompt.get("normalized_excerpt")
        if isinstance(excerpt, str):
            return excerpt
    return ""


def prompt_marker_is_fresh_for_tool(prompt_marker: dict[str, Any], payload: dict[str, Any]) -> bool:
    if not prompt_text_from_marker(prompt_marker).strip():
        return False
    expected_session = payload.get("session_id")
    if isinstance(expected_session, str) and expected_session.strip() and prompt_marker.get("session_id") != expected_session:
        return False
    recorded_at = prompt_marker.get("recorded_at")
    try:
        recorded = dt.datetime.fromisoformat(str(recorded_at))
    except ValueError:
        return False
    age = dt.datetime.now(dt.timezone.utc) - recorded
    if age.total_seconds() > 3600:
        return False
    return True


def prompt_marker_same_session(prompt_marker: dict[str, Any], payload: dict[str, Any]) -> bool:
    expected_session = payload.get("session_id")
    return (
        isinstance(expected_session, str)
        and bool(expected_session.strip())
        and prompt_marker.get("session_id") == expected_session
    )


def prompt_marker_can_authorize_same_session_continuation(
    prompt_marker: dict[str, Any],
    payload: dict[str, Any],
) -> bool:
    if not prompt_text_from_marker(prompt_marker).strip():
        return False
    if not prompt_marker_same_session(prompt_marker, payload):
        return False
    recorded_at = prompt_marker.get("recorded_at")
    try:
        dt.datetime.fromisoformat(str(recorded_at))
    except ValueError:
        return False
    return prompt_intent_allows_mutation(prompt_marker)


def run_intent_judge_for_marker(prompt_marker: dict[str, Any]) -> dict[str, Any]:
    prompt = prompt_text_from_marker(prompt_marker)
    if not prompt.strip():
        return {
            "ok": False,
            "llm_attempted": False,
            "reason": "latest prompt text is unavailable",
        }
    argv = [
        str(REDCAP),
        "intent-judge",
        "classify",
        "--prompt",
        prompt,
        "--llm-policy",
        "force",
        "--provider",
        INTENT_JUDGE_PROVIDER,
        "--fallback-provider",
        INTENT_JUDGE_FALLBACK_PROVIDER,
        "--timeout-seconds",
        str(INTENT_JUDGE_TIMEOUT_SECONDS),
    ]
    if INTENT_JUDGE_FAKE_RESPONSE:
        argv.extend(["--fake-response", INTENT_JUDGE_FAKE_RESPONSE])
    if INTENT_JUDGE_FAKE_DELAY_SECONDS:
        argv.extend(["--fake-delay-seconds", INTENT_JUDGE_FAKE_DELAY_SECONDS])
    provider_count = 1 + int(bool(INTENT_JUDGE_FALLBACK_PROVIDER) and INTENT_JUDGE_FALLBACK_PROVIDER != INTENT_JUDGE_PROVIDER)
    try:
        completed = subprocess.run(
            argv,
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=(INTENT_JUDGE_TIMEOUT_SECONDS * provider_count) + 5,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "llm_attempted": True,
            "reason": "intent judge timeout",
            "timeout_seconds": INTENT_JUDGE_TIMEOUT_SECONDS,
            "stdout_length": len(exc.stdout or ""),
            "stderr_length": len(exc.stderr or ""),
        }
    parsed, parse_error = parse_leading_json_object(completed.stdout or "")
    if parsed is None:
        parsed = {}
    parsed.update({
        "exit_code": completed.returncode,
        "stdout_length": len(completed.stdout or ""),
        "stdout_sha256": hashlib.sha256((completed.stdout or "").encode("utf-8")).hexdigest()
        if completed.stdout
        else None,
        "stderr_length": len(completed.stderr or ""),
        "stderr_sha256": hashlib.sha256((completed.stderr or "").encode("utf-8")).hexdigest()
        if completed.stderr
        else None,
        "parse_error": parse_error,
    })
    if parse_error is not None:
        parsed["ok"] = False
        parsed["reason"] = f"intent judge returned invalid JSON: {parse_error}"
    return parsed


def pre_tool_claim(payload: dict[str, Any], marker: dict[str, Any], command: str) -> dict[str, Any]:
    tool_name = str(payload.get("tool_name") or "")
    should_claim = tool_is_mutating(payload, command)
    if not should_claim:
        return {"attempted": False}
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return {"attempted": False, "reason": "missing-session-id"}
    task_id = str(payload.get("turn_id") or payload.get("hook_event_name") or "codex-pre-tool-use")
    claim = run_command([
        str(REDCAP),
        "session-ownership",
        "claim",
        "--host",
        "codex",
        "--session-id",
        session_id,
        "--task-id",
        task_id,
        "--intent",
        "execution",
        "--reason",
        f"codex-pre-tool-use:{tool_name}",
    ])
    return {
        "attempted": True,
        "exit_code": claim["exit_code"],
        "stdout_sha256": claim["stdout_sha256"],
        "stderr_sha256": claim["stderr_sha256"],
        "marker_event": marker.get("event"),
    }


def update_latest_marker(event: str, updates: dict[str, Any], base_marker: dict[str, Any] | None = None) -> dict[str, Any]:
    latest = EVIDENCE_DIR / f"latest-{event}.json"
    with evidence_lock():
        marker = dict(base_marker) if base_marker is not None else json.loads(latest.read_text(encoding="utf-8"))
        marker.update(updates)
        write_json_atomic(latest, marker)
        with EVENTS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(marker, ensure_ascii=False, sort_keys=True) + "\n")
    return marker


def write_latest_named_marker(name: str, marker: dict[str, Any]) -> None:
    latest = EVIDENCE_DIR / name
    with evidence_lock():
        write_json_atomic(latest, marker)


def marker_for(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    adapter_path = pathlib.Path(__file__).resolve()
    marker = {
        "schema_id": "redcap-codex-hook-live-marker",
        "host_source": "codex",
        "event": event,
        "hook_event_name": payload.get("hook_event_name"),
        "recorded_at": iso_now(),
        "cwd": payload.get("cwd"),
        "session_id": payload.get("session_id"),
        "turn_id": payload.get("turn_id"),
        "source": payload.get("source"),
        "permission_mode": payload.get("permission_mode"),
        "payload_keys": sorted(payload.keys()),
        "hook_config_path": str(HOOKS_CONFIG),
        "hook_config_sha256": sha256_file(HOOKS_CONFIG) if HOOKS_CONFIG.exists() else None,
        "adapter_path": str(adapter_path),
        "adapter_sha256": sha256_file(adapter_path),
    }
    if event == "UserPromptSubmit":
        prompt = payload.get("prompt") if isinstance(payload.get("prompt"), str) else ""
        marker["prompt"] = text_evidence(prompt)
        marker["prompt_intent"] = classify_prompt_intent(prompt)
    if event == "Stop":
        marker["stop_hook_active"] = payload.get("stop_hook_active")
        marker["last_assistant_message"] = short_text_fingerprint(payload.get("last_assistant_message"))
        marker["required_prompt_action_ok"] = None
        marker["redcap_check_attempted"] = False
        marker["redcap_check_exit"] = None
    if event in {"PreToolUse", "PostToolUse"}:
        marker["tool_name"] = payload.get("tool_name")
        marker["tool_use_id"] = payload.get("tool_use_id")
        marker["tool_input"] = json_fingerprint(payload.get("tool_input"))
        command = tool_command(payload)
        if command:
            marker["tool_command"] = text_evidence(command)
    if event == "PostToolUse":
        marker["tool_response"] = json_fingerprint(payload.get("tool_response"))
    return marker


def write_marker(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    marker = marker_for(event, payload)
    latest = EVIDENCE_DIR / f"latest-{event}.json"
    with evidence_lock():
        with EVENTS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(marker, ensure_ascii=False, sort_keys=True) + "\n")
        write_json_atomic(latest, marker)
    return marker


def cmd_event(args: argparse.Namespace) -> int:
    payload = load_hook_input()
    marker = write_marker(args.event, payload)
    if args.event == "SessionStart":
        soul = run_command([str(REDCAP), "soul-load", "load", "--json"])
        soul_result, soul_parse_error = parse_leading_json_object(soul["stdout"])
        soul_loaded = (
            soul["exit_code"] == 0
            and soul_parse_error is None
            and isinstance(soul_result, dict)
            and soul_result.get("ok") is True
        )
        marker = update_latest_marker("SessionStart", {
            "cap_soul_load_attempted": True,
            "cap_soul_load_ok": soul_loaded,
            "cap_soul_load_stdout_length": soul["stdout_length"],
            "cap_soul_load_stdout_sha256": soul["stdout_sha256"],
            "cap_soul_load_stderr_length": soul["stderr_length"],
            "cap_soul_load_stderr_sha256": soul["stderr_sha256"],
            "cap_soul_load_parse_error": soul_parse_error,
            "cap_soul_required_loaded": soul_result.get("required_loaded") if isinstance(soul_result, dict) else [],
            "cap_soul_optional_missing": soul_result.get("optional_missing") if isinstance(soul_result, dict) else [],
        }, base_marker=marker)
        context = (
            "RedCap Codex SessionStart hook fired. Before RedCap implementation "
            "or completion claims, run runtime/bin/redcap gate and follow the "
            "gate decision. This hook is project-local Codex evidence, not "
            "cross-host hook parity. Cap soul load status: "
            f"{'loaded' if soul_loaded else 'blocked'}."
        )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,
            },
            "systemMessage": f"RedCap Codex hook live marker recorded: {marker['recorded_at']}",
        }, ensure_ascii=False))
    elif args.event == "UserPromptSubmit":
        prompt = payload.get("prompt") if isinstance(payload.get("prompt"), str) else ""
        deterministic_prompt_intent = classify_prompt_intent(prompt)
        gate = run_prompt_gate(
            payload,
            prompt,
            semantic_policy="off",
            timeout_seconds=GATE_COMMAND_TIMEOUT_SECONDS,
        ) if prompt.strip() else {
            "exit_code": 0,
            "timed_out": False,
            "timeout_seconds": None,
            "prompt_truncated": False,
            "parse_ok": False,
            "decision": "skipped",
            "matched_rules": [],
            "review_mode": None,
            "required_providers": [],
            "semantic_gate": {},
        }
        semantic_prompt_intent = None
        prompt_intent_effective = None
        prompt_intent_for_context = prompt_intent_effective or deterministic_prompt_intent
        marker = update_latest_marker("UserPromptSubmit", {
            "gate_decision": gate.get("decision"),
            "gate_review_mode": gate.get("review_mode"),
            "gate_matched_rules": gate.get("matched_rules"),
            "gate_required_providers": gate.get("required_providers"),
            "gate_self_development_lifecycle": gate.get("self_development_lifecycle", {}),
            "gate_semantic": gate.get("semantic_gate", {}),
            "gate_exit_code": gate.get("exit_code"),
            "gate_timed_out": gate.get("timed_out", False),
            "gate_timeout_seconds": gate.get("timeout_seconds"),
            "gate_parse_ok": gate.get("parse_ok"),
            "gate_prompt_truncated": gate.get("prompt_truncated"),
            "gate_stdout_length": gate.get("stdout_length"),
            "gate_stdout_sha256": gate.get("stdout_sha256"),
            "gate_stderr_length": gate.get("stderr_length"),
            "gate_stderr_sha256": gate.get("stderr_sha256"),
            "prompt_intent": deterministic_prompt_intent,
            "prompt_intent_effective": prompt_intent_effective,
            "prompt_intent_llm": gate.get("semantic_gate", {}),
        }, base_marker=marker)
        if prompt.strip() and GATE_SEMANTIC_POLICY != "off":
            semantic_gate_result = run_prompt_gate(
                payload,
                prompt,
                semantic_policy=GATE_SEMANTIC_POLICY,
                timeout_seconds=GATE_COMMAND_TIMEOUT_SECONDS,
            )
            semantic_prompt_intent = semantic_prompt_intent_from_gate(semantic_gate_result)
            if (
                semantic_gate_result.get("parse_ok") is True
                and isinstance(semantic_gate_result.get("decision"), str)
                and semantic_gate_result.get("timed_out") is not True
            ):
                gate = semantic_gate_result
                prompt_intent_effective = semantic_prompt_intent
                prompt_intent_for_context = prompt_intent_effective or deterministic_prompt_intent
                marker = update_latest_marker("UserPromptSubmit", {
                    "gate_decision": gate.get("decision"),
                    "gate_review_mode": gate.get("review_mode"),
                    "gate_matched_rules": gate.get("matched_rules"),
                    "gate_required_providers": gate.get("required_providers"),
                    "gate_self_development_lifecycle": gate.get("self_development_lifecycle", {}),
                    "gate_semantic": gate.get("semantic_gate", {}),
                    "gate_exit_code": gate.get("exit_code"),
                    "gate_timed_out": gate.get("timed_out", False),
                    "gate_timeout_seconds": gate.get("timeout_seconds"),
                    "gate_parse_ok": gate.get("parse_ok"),
                    "gate_prompt_truncated": gate.get("prompt_truncated"),
                    "gate_stdout_length": gate.get("stdout_length"),
                    "gate_stdout_sha256": gate.get("stdout_sha256"),
                    "gate_stderr_length": gate.get("stderr_length"),
                    "gate_stderr_sha256": gate.get("stderr_sha256"),
                    "prompt_intent": deterministic_prompt_intent,
                    "prompt_intent_effective": prompt_intent_effective,
                    "prompt_intent_llm": gate.get("semantic_gate", {}),
                    "gate_semantic_degraded": False,
                }, base_marker=marker)
            else:
                marker = update_latest_marker("UserPromptSubmit", {
                    "gate_semantic_degraded": True,
                    "gate_semantic_degraded_reason": "semantic gate did not complete before hook budget; deterministic gate marker retained",
                    "gate_semantic_exit_code": semantic_gate_result.get("exit_code"),
                    "gate_semantic_timed_out": semantic_gate_result.get("timed_out", False),
                    "gate_semantic_timeout_seconds": semantic_gate_result.get("timeout_seconds"),
                    "gate_semantic_parse_ok": semantic_gate_result.get("parse_ok"),
                    "gate_semantic_stdout_sha256": semantic_gate_result.get("stdout_sha256"),
                    "gate_semantic_stderr_sha256": semantic_gate_result.get("stderr_sha256"),
                }, base_marker=marker)
        decision = marker.get("gate_decision")
        if decision == "required":
            lifecycle = marker.get("gate_self_development_lifecycle") if isinstance(marker, dict) else {}
            scope = prompt_intent_for_context.get("authorized_scope")
            action_evidence = prompt_intent_for_context.get("action_evidence")
            if scope in {"answer_only", "review_only"}:
                context = (
                    "RedCap（当前复活工程）UserPromptSubmit（用户提示提交检查）已触发。"
                    f"本轮被判断为 {scope}；普通回答或评审可以继续，"
                    "但实现动作或完成声明仍必须经过 RedCap（当前复活工程）门禁。"
                )
            elif isinstance(lifecycle, dict) and lifecycle.get("required") is True and lifecycle.get("checked") is not True:
                context = (
                    "RedCap（当前复活工程）UserPromptSubmit（用户提示提交检查）已触发："
                    "Prism（棱镜，异构评审助手）规则评审和自开发生命周期包是必需前置，"
                    "除非 Norven 明确覆盖。"
                )
            else:
                context = (
                    "RedCap（当前复活工程）UserPromptSubmit（用户提示提交检查）已触发，"
                    "且需要 Prism（棱镜，异构评审助手）规则评审。"
                    "实现动作或完成声明前必须完成完整评审，除非 Norven 明确覆盖。"
                )
        else:
            context = (
                "RedCap（当前复活工程）UserPromptSubmit（用户提示提交检查）已触发。"
                f"门禁结论：{decision or 'unknown'}。"
            )
        terminal_context = run_command([
            sys.executable,
            str(TERMINAL_GOAL_GUARD),
            "context",
            "--for-hook",
            *terminal_goal_guard_args(),
        ])
        if terminal_context["exit_code"] == 0 and terminal_context["stdout"].strip():
            context = f"{context}\n{terminal_context['stdout'].strip()}"
            marker = update_latest_marker("UserPromptSubmit", {
                "terminal_goal_context_injected": True,
                "terminal_goal_context_stdout_sha256": terminal_context["stdout_sha256"],
                "terminal_goal_context_stderr_sha256": terminal_context["stderr_sha256"],
            }, base_marker=marker)
        else:
            marker = update_latest_marker("UserPromptSubmit", {
                "terminal_goal_context_injected": False,
                "terminal_goal_context_exit": terminal_context["exit_code"],
                "terminal_goal_context_stdout_sha256": terminal_context["stdout_sha256"],
                "terminal_goal_context_stderr_sha256": terminal_context["stderr_sha256"],
            }, base_marker=marker)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context,
            },
            "systemMessage": f"RedCap（当前复活工程）提示检查已记录门禁结论：{decision or 'unknown'}",
        }, ensure_ascii=False))
    elif args.event == "PreToolUse":
        command = tool_command(payload)
        cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
        prompt_marker = latest_user_prompt_marker()
        intent_deny_reason = None
        intent_judge = None
        prompt_marker_fresh = prompt_marker_is_fresh_for_tool(prompt_marker, payload)
        same_session_continuation_authorized = False
        if tool_is_mutating(payload, command):
            if not prompt_marker_fresh:
                same_session_continuation_authorized = prompt_marker_can_authorize_same_session_continuation(prompt_marker, payload)
                if not same_session_continuation_authorized:
                    intent_deny_reason = (
                        "RedCap 最新用户提示标记缺失、过期或不属于当前会话；"
                        "写入动作需要新鲜 UserPromptSubmit（用户提示提交事件）标记，"
                        "或同会话已授权实施/完成意图的续跑标记。"
                    )
            elif not prompt_intent_allows_mutation(prompt_marker):
                intent = effective_prompt_intent(prompt_marker) if isinstance(prompt_marker, dict) else {}
                scope = intent.get("authorized_scope") if isinstance(intent, dict) else "unknown"
                intent_judge = run_intent_judge_for_marker(prompt_marker)
                judge_intent = intent_judge.get("prompt_intent") if isinstance(intent_judge, dict) else None
                if isinstance(judge_intent, dict) and judge_intent.get("authorized_scope") in {"implementation", "completion"}:
                    prompt_marker = update_latest_marker("UserPromptSubmit", {
                        "prompt_intent_effective": judge_intent,
                        "prompt_intent_llm": intent_judge,
                    }, base_marker=prompt_marker)
                else:
                    judge_reason = intent_judge.get("reason") if isinstance(intent_judge, dict) else None
                    intent_deny_reason = (
                        "Latest RedCap prompt is classified as "
                        f"{scope}; Prism LLM intent judge did not authorize mutation"
                        f"{': ' + judge_reason if judge_reason else ''}."
                    )
            else:
                pass
        deny_reason = (
            dangerous_command_reason(command, cwd)
            or protected_evidence_write_reason(payload)
            or protected_prism_raw_read_reason(payload)
            or intent_deny_reason
        )
        claim = pre_tool_claim(payload, marker, command)
        marker = update_latest_marker("PreToolUse", {
            "dangerous_command_denied": bool(deny_reason),
            "dangerous_command_reason": deny_reason,
            "prompt_intent_mutation_denied": bool(intent_deny_reason),
            "latest_prompt_marker_fresh": prompt_marker_fresh,
            "same_session_continuation_authorized": same_session_continuation_authorized,
            "latest_prompt_intent": effective_prompt_intent(prompt_marker) if isinstance(prompt_marker, dict) else None,
            "prompt_intent_llm_attempted": bool(intent_judge),
            "prompt_intent_llm_result": intent_judge,
            "session_ownership_claim": claim,
        }, base_marker=marker)
        if claim.get("attempted") is True:
            write_latest_named_marker("latest-PreToolUse-mutating.json", marker)
        if deny_reason:
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": deny_reason,
                },
                "systemMessage": "RedCap PreToolUse blocked a dangerous command.",
            }, ensure_ascii=False))
    elif args.event == "PostToolUse":
        tool_name = marker.get("tool_name") or "unknown"
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"RedCap（当前复活工程）PostToolUse（工具使用后检查）已记录动作证据：{tool_name}。"
                ),
            },
            "systemMessage": f"RedCap（当前复活工程）已记录动作证据：{tool_name}。",
        }, ensure_ascii=False))
    elif args.event == "Stop":
        last_assistant_message = str(payload.get("last_assistant_message") or "")
        mode = stop_hook_mode()
        if mode == "observe":
            marker = update_latest_marker("Stop", {
                "stop_hook_mode": "observe",
                "redcap_check_attempted": False,
                "redcap_check_skipped_reason": "Stop hook temporarily downgraded by Norven authorization.",
            }, base_marker=marker)
            print(json.dumps({
                "continue": True,
                "systemMessage": (
                    "RedCap（当前复活工程）Stop Hook（停止前检查）暂处观察模式，阻断式收口检查已跳过。"
                ),
            }, ensure_ascii=False))
            return 0
        action = run_command([
            str(TURN_ACTION_CHECK),
            "--events",
            str(EVENTS_PATH),
            "--session-id",
            str(payload.get("session_id") or ""),
            "--turn-id",
            str(payload.get("turn_id") or ""),
            "--max-age-seconds",
            "86400",
            "--message",
            last_assistant_message,
            "--intent-llm-policy",
            os.environ.get("REDCAP_STOP_INTENT_LLM_POLICY", "auto-on-ambiguous"),
            "--intent-timeout-seconds",
            os.environ.get("REDCAP_STOP_INTENT_TIMEOUT_SECONDS", "60"),
        ])
        action_result, parse_error = parse_leading_json_object(action["stdout"])
        if parse_error is not None or action_result is None:
            action_result = {
                "ok": False,
                "reason": f"turn-action-check returned invalid JSON: {parse_error}",
                "exit_code": action["exit_code"],
            }
        action_sentinel_present = "REDCAP_TURN_ACTION_OK" in action["stdout"]
        if action["exit_code"] == 0 and not action_sentinel_present:
            action_result = dict(action_result)
            action_result["ok"] = False
            action_result["reason"] = "turn-action-check success sentinel missing"
        marker = update_latest_marker("Stop", {
            "required_prompt_action_ok": bool(action_result.get("ok")),
            "required_prompt_action_required": action_result.get("required_prompt"),
            "required_prompt_action_count": action_result.get("actions"),
            "required_prompt_action_tools": action_result.get("action_tools", []),
            "required_prompt_action_reason": action_result.get("reason"),
            "required_prompt_task_anchor": action_result.get("task_anchor"),
            "required_prompt_recovery_guidance": action_result.get("recovery_guidance", []),
            "required_prompt_action_sentinel_present": action_sentinel_present,
        }, base_marker=marker)
        if action["exit_code"] != 0 or action_result.get("ok") is not True:
            action_reason = action_result.get("reason")
            anchor_clause = stop_task_anchor_clause(action_result)
            reason = (
                "RedCap（当前复活工程）Stop Hook（停止前检查）发现：必需处理的 RedCap 提示没有本轮动作证据。"
                "不能只用解释或状态汇报收口；请执行具体修复、运行必需检查，"
                "或明确标记为受阻并说明阻塞条件。"
            )
            if anchor_clause:
                reason = f"{reason} {anchor_clause}"
            if isinstance(action_reason, str) and action_reason.strip():
                reason = f"{reason} 动作检查原因：{action_reason}"
            reason = f"{reason}{blocked_reply_excerpt(last_assistant_message)}"
            print(json.dumps({
                "decision": "block",
                "reason": reason,
                "systemMessage": "RedCap（当前复活工程）必需提示动作证据门禁未通过。",
            }, ensure_ascii=False))
            return 0
        terminal_guard = run_command([
            sys.executable,
            str(TERMINAL_GOAL_GUARD),
            "check",
            "--message",
            last_assistant_message,
            "--events",
            str(EVENTS_PATH),
            "--session-id",
            str(payload.get("session_id") or ""),
            "--turn-id",
            str(payload.get("turn_id") or ""),
            *terminal_goal_guard_args(),
        ])
        terminal_guard_result, terminal_guard_parse_error = parse_leading_json_object(terminal_guard["stdout"])
        if terminal_guard_parse_error is not None or terminal_guard_result is None:
            terminal_guard_result = {
                "ok": False,
                "reason": f"terminal-goal guard returned invalid JSON: {terminal_guard_parse_error}",
                "exit_code": terminal_guard["exit_code"],
            }
        marker = update_latest_marker("Stop", {
            "terminal_goal_guard_ok": bool(terminal_guard_result.get("ok")),
            "terminal_goal_guard_triggered": terminal_guard_result.get("triggered_goals", []),
            "terminal_goal_guard_failures": terminal_guard_result.get("failures", []),
            "terminal_goal_guard_exit": terminal_guard["exit_code"],
            "terminal_goal_guard_stdout_sha256": terminal_guard["stdout_sha256"],
            "terminal_goal_guard_stderr_sha256": terminal_guard["stderr_sha256"],
        }, base_marker=marker)
        if terminal_guard["exit_code"] != 0 or terminal_guard_result.get("ok") is not True:
            failures = terminal_guard_result.get("failures")
            if isinstance(failures, list) and failures:
                detail = "；".join(str(item) for item in failures[:3])
            else:
                detail = str(terminal_guard_result.get("reason") or "未知原因")
            print(json.dumps({
                "decision": "block",
                "reason": (
                    "RedCap（当前复活工程）Stop Hook（停止前检查）发现最后回复可能把阶段成果说成终局完成："
                    f"{detail}。请回到原问题，用阶段、风险、待办口径回答；不要把阶段成果或检查结果写成完整复活。"
                    f"{recovery_focus_clause()}"
                    f"{blocked_reply_excerpt(last_assistant_message)}"
                ),
                "systemMessage": "RedCap（当前复活工程）终局目标门禁未通过。",
            }, ensure_ascii=False))
            return 0
        final_guard = run_command([
            sys.executable,
            str(FINAL_CLAIM_GUARD),
            "check",
            "--message",
            last_assistant_message,
            "--events",
            str(EVENTS_PATH),
            "--session-id",
            str(payload.get("session_id") or ""),
            "--turn-id",
            str(payload.get("turn_id") or ""),
        ])
        final_guard_result, final_guard_parse_error = parse_leading_json_object(final_guard["stdout"])
        if final_guard_parse_error is not None or final_guard_result is None:
            final_guard_result = {
                "ok": False,
                "reason": f"final-claim guard returned invalid JSON: {final_guard_parse_error}",
                "exit_code": final_guard["exit_code"],
            }
        marker = update_latest_marker("Stop", {
            "final_claim_guard_ok": bool(final_guard_result.get("ok")),
            "final_claim_guard_reason": final_guard_result.get("reason"),
            "final_claim_detected": final_guard_result.get("completion_claim_detected"),
            "final_claim_guard_exit": final_guard["exit_code"],
            "final_claim_guard_stdout_sha256": final_guard["stdout_sha256"],
            "final_claim_guard_stderr_sha256": final_guard["stderr_sha256"],
        }, base_marker=marker)
        if final_guard["exit_code"] != 0 or final_guard_result.get("ok") is not True:
            reason = (
                "RedCap（当前复活工程）Stop Hook（停止前检查）发现：必需处理的 RedCap 提示带有最终完成声明，"
                "但缺少本轮新鲜且已验证的任务主体生命周期完成标记。请继续本轮："
                "如果原任务只是评审、回答或状态盘点，请回到原问题并收窄完成口径；"
                "只有实际实施任务已经落地时，才运行 completion_claim.present=true 的生命周期检查。"
            )
            anchor_clause = stop_task_anchor_clause(action_result)
            if anchor_clause:
                reason = f"{reason} {anchor_clause}"
            guard_reason = final_guard_result.get("reason")
            if isinstance(guard_reason, str) and guard_reason.strip():
                reason = f"{reason} 完成声明检查原因：{guard_reason}"
            reason = f"{reason}{blocked_reply_excerpt(last_assistant_message)}"
            print(json.dumps({
                "decision": "block",
                "reason": reason,
                "systemMessage": "RedCap（当前复活工程）最终完成声明门禁未通过。",
            }, ensure_ascii=False))
            return 0
        scan_guard = run_command([
            sys.executable,
            str(SCAN_CONCLUSION_GUARD),
            "check",
            "--message",
            last_assistant_message,
            "--events",
            str(EVENTS_PATH),
            "--session-id",
            str(payload.get("session_id") or ""),
            "--turn-id",
            str(payload.get("turn_id") or ""),
        ])
        scan_guard_result, scan_guard_parse_error = parse_leading_json_object(scan_guard["stdout"])
        if scan_guard_parse_error is not None or scan_guard_result is None:
            scan_guard_result = {
                "ok": False,
                "reason": f"scan-conclusion guard returned invalid JSON: {scan_guard_parse_error}",
                "exit_code": scan_guard["exit_code"],
            }
        scan_state = scan_guard_result.get("scan_state") if isinstance(scan_guard_result, dict) else None
        marker = update_latest_marker("Stop", {
            "scan_conclusion_guard_ok": bool(scan_guard_result.get("ok")),
            "scan_conclusion_guard_triggered": scan_guard_result.get("triggered"),
            "scan_conclusion_guard_reason": scan_guard_result.get("reason"),
            "scan_conclusion_guard_state": scan_state,
            "scan_conclusion_guard_exit": scan_guard["exit_code"],
            "scan_conclusion_guard_stdout_sha256": scan_guard["stdout_sha256"],
            "scan_conclusion_guard_stderr_sha256": scan_guard["stderr_sha256"],
        }, base_marker=marker)
        if scan_guard["exit_code"] != 0 or scan_guard_result.get("ok") is not True:
            expected = scan_guard_result.get("expected_status_block")
            recovery = scan_guard_result.get("recovery")
            reason = (
                "RedCap（当前复活工程）Stop Hook（停止前检查）发现：回复正在回答 360 度旧 RedCap 扫描结论，"
                "但当前扫描没有完成证据，或缺少与账目一致的结构化扫描状态块。"
                "请回到原扫描任务：只能报告阶段状态，或者继续执行已验证的分片扫描。"
                f"{recovery_focus_clause()}"
            )
            if isinstance(expected, str) and expected.strip():
                reason = f"{reason} 需要包含的状态块：{expected}"
            if isinstance(recovery, str) and recovery.strip():
                reason = f"{reason} 恢复要求：{recovery}"
            reason = f"{reason}{blocked_reply_excerpt(last_assistant_message)}"
            print(json.dumps({
                "decision": "block",
                "reason": reason,
                "systemMessage": "RedCap（当前复活工程）360 度扫描结论门禁未通过。",
            }, ensure_ascii=False))
            return 0
        human_output = run_command([
            sys.executable,
            str(HUMAN_OUTPUT_POLICY),
            "lint-text",
            "--surface",
            "assistant_reply",
            "--source",
            "last_assistant_message",
            "--text",
            last_assistant_message,
        ])
        human_output_result, human_output_parse_error = parse_leading_json_object(human_output["stdout"])
        if human_output_parse_error is not None or human_output_result is None:
            human_output_result = {
                "ok": False,
                "reason": f"human-output guard returned invalid JSON: {human_output_parse_error}",
                "exit_code": human_output["exit_code"],
            }
        marker = update_latest_marker("Stop", {
            "human_output_guard_ok": bool(human_output_result.get("ok")),
            "human_output_guard_failures": human_output_result.get("failures", []),
            "human_output_guard_exit": human_output["exit_code"],
            "human_output_guard_stdout_sha256": human_output["stdout_sha256"],
            "human_output_guard_stderr_sha256": human_output["stderr_sha256"],
        }, base_marker=marker)
        if human_output["exit_code"] != 0 or human_output_result.get("ok") is not True:
            failures = human_output_result.get("failures")
            if isinstance(failures, list) and failures:
                detail = "；".join(str(item) for item in failures[:3])
            else:
                detail = str(human_output_result.get("reason") or "未知原因")
            print(json.dumps({
                "decision": "block",
                "reason": (
                    "RedCap（当前复活工程）Stop Hook（停止前检查）发现最后回复不符合中文优先、"
                    f"人类可读策略：{detail}。请改写为中文优先、必要术语带解释的回复。"
                    f"{recovery_focus_clause()}"
                    f"{blocked_reply_excerpt(last_assistant_message)}"
                ),
                "systemMessage": "RedCap（当前复活工程）中文可读输出门禁未通过。",
            }, ensure_ascii=False))
            return 0
        if stop_self_check_skips_full_check(payload):
            marker = update_latest_marker("Stop", {
                "redcap_check_attempted": False,
                "redcap_check_skipped_reason": "self-check passed closeout guards; full redcap check skipped to keep fixture bounded",
            }, base_marker=marker)
            print(json.dumps({
                "continue": True,
                "systemMessage": "RedCap（当前复活工程）Stop Hook（停止前检查）自检门禁已通过，完整检查已按自检范围跳过。",
            }, ensure_ascii=False))
            return 0
        marker = update_latest_marker("Stop", {
            "redcap_check_attempted": True,
        }, base_marker=marker)
        check = run_command([str(REDCAP), "check"])
        marker = update_latest_marker("Stop", {
            "redcap_check_exit": check["exit_code"],
            "redcap_check_stdout_length": check["stdout_length"],
            "redcap_check_stdout_sha256": check["stdout_sha256"],
            "redcap_check_stderr_length": check["stderr_length"],
            "redcap_check_stderr_sha256": check["stderr_sha256"],
            "redcap_check_completed_at": iso_now(),
        }, base_marker=marker)
        if check["exit_code"] == 0:
            print(json.dumps({
                "continue": True,
                "systemMessage": "RedCap（当前复活工程）Stop Hook（停止前检查）已通过。",
            }, ensure_ascii=False))
        else:
            reason = (
                "RedCap（当前复活工程）Stop Hook（停止前检查）运行 runtime/bin/redcap check 后失败。"
                "请继续本轮，在本地查看失败检查、修复具体问题，并在收口前重新运行 runtime/bin/redcap check。"
                f"{recovery_focus_clause()}"
            )
            print(json.dumps({
                "decision": "block",
                "reason": reason,
                "systemMessage": f"RedCap（当前复活工程）Stop Hook（停止前检查）失败，退出码 {marker['redcap_check_exit']}。",
            }, ensure_ascii=False))
    return 0


def run_hook_event_for_self_check(
    event: str,
    payload: dict[str, Any],
    *,
    evidence_dir: pathlib.Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["REDCAP_CODEX_HOOK_EVIDENCE_DIR"] = str(evidence_dir)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(pathlib.Path(__file__).resolve()), "--event", event],
        cwd=str(REPO_ROOT),
        input=json.dumps(payload, ensure_ascii=False),
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def load_self_check_marker(
    evidence_dir: pathlib.Path,
    event: str,
    *,
    source: str | None = None,
    turn_id: str | None = None,
) -> dict[str, Any]:
    if source or turn_id:
        try:
            lines = (evidence_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        for line in reversed(lines):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict) or payload.get("event") != event:
                continue
            if source is not None and payload.get("source") != source:
                continue
            if turn_id is not None and payload.get("turn_id") != turn_id:
                continue
            return payload
    path = evidence_dir / f"latest-{event}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def cmd_self_check_intent_judge(_: argparse.Namespace) -> int:
    failures: list[str] = []
    if prism_raw_read_reason("python3 -m json.tool assets/evidence/prism/run/kimi.raw.json", str(REPO_ROOT)) is None:
        failures.append("Prism raw JSON broad read was not blocked")
    if prism_raw_read_reason("cat assets/evidence/prism/run/kimi.raw.json", str(REPO_ROOT)) is None:
        failures.append("Prism raw cat read was not blocked")
    if prism_raw_read_reason("rg -n provider runtime assets", str(REPO_ROOT)) is not None:
        failures.append("broad repo diagnostic search over assets should not be blocked")
    if prism_raw_read_reason("rg -n provider assets/evidence", str(REPO_ROOT)) is None:
        failures.append("Prism evidence ancestor rg search without raw exclusions was not blocked")
    if prism_raw_read_reason("rg -n provider assets/evidence -g '!*.raw.json' -g '!*.raw.meta.json'", str(REPO_ROOT)) is not None:
        failures.append("Prism evidence ancestor rg search with raw exclusions should not be blocked")
    if prism_raw_read_reason(
        "python3 -c \"print(open('assets/evidence/prism/run/kimi.raw.json').read())\"",
        str(REPO_ROOT),
    ) is None:
        failures.append("Prism raw python -c read was not blocked")
    if prism_raw_read_reason(
        "python3 -c \"print(open('assets/' + 'evidence/prism/run/kimi.raw.json').read())\"",
        str(REPO_ROOT),
    ) is None:
        failures.append("Prism raw python -c concatenated path read was not blocked")
    if prism_raw_read_reason(
        "runtime/prism/bin/prism-dispatch --verify-raw-meta --raw-out assets/evidence/prism/run/kimi.raw.json",
        str(REPO_ROOT),
    ) is not None:
        failures.append("Prism raw metadata verifier should not be blocked")
    if prism_raw_read_reason(
        "runtime/prism/bin/prism-dispatch --provider kimi --raw-out assets/evidence/prism/run/kimi.raw.json",
        str(REPO_ROOT),
    ) is not None:
        failures.append("Prism dispatcher raw-out writer should not be blocked")
    if prism_raw_read_reason(
        "python3 - <<'PY'\nprint('prepare request')\nPY\nruntime/prism/bin/prism-dispatch --provider kimi --raw-out assets/evidence/prism/run/kimi.raw.json",
        str(REPO_ROOT),
    ) is not None:
        failures.append("multiline command with dispatcher raw-out writer should not be blocked")
    if prism_raw_read_reason("cat assets/evidence/prism/run/kimi.raw.meta.json", str(REPO_ROOT)) is None:
        failures.append("Prism raw metadata direct read should be blocked")
    read_reason = protected_prism_raw_read_reason({
        "cwd": str(REPO_ROOT),
        "tool_name": "Read",
        "tool_input": {"path": "assets/evidence/prism/run/kimi.raw.json"},
    })
    if read_reason is None:
        failures.append("Prism raw host Read tool path was not blocked")
    read_meta_reason = protected_prism_raw_read_reason({
        "cwd": str(REPO_ROOT),
        "tool_name": "Read",
        "tool_input": {"path": "assets/evidence/prism/run/kimi.raw.meta.json"},
    })
    if read_meta_reason is None:
        failures.append("Prism raw metadata host Read tool path was not blocked")
    with tempfile.TemporaryDirectory(prefix="redcap-codex-hook-intent-") as raw_tmp:
        evidence_dir = pathlib.Path(raw_tmp)
        prompt_payload = {
            "prompt": "让这个机制以后自己判断真实意图",
            "cwd": str(REPO_ROOT),
            "source": "codex-hook-intent-self-check",
        }
        first_prompt = run_hook_event_for_self_check("UserPromptSubmit", prompt_payload, evidence_dir=evidence_dir)
        if first_prompt.returncode != 0:
            failures.append(f"first UserPromptSubmit failed: {first_prompt.stderr or first_prompt.stdout}")
        allow = run_hook_event_for_self_check(
            "PreToolUse",
            {
                "cwd": str(REPO_ROOT),
                "tool_name": "apply_patch",
                "tool_use_id": "codex-hook-intent-self-check-allow",
                "tool_input": {"patch": "*** Begin Patch\n*** End Patch\n"},
                "source": "codex-hook-intent-self-check",
            },
            evidence_dir=evidence_dir,
            extra_env={
                "REDCAP_INTENT_JUDGE_FAKE_RESPONSE": json.dumps({
                    "prompt_kind": "directive",
                    "authorized_scope": "implementation",
                    "action_evidence": "substantive",
                    "confidence": "high",
                    "reason": "fixture hook branch allow",
                }, ensure_ascii=False),
            },
        )
        if allow.returncode != 0:
            failures.append(f"allow PreToolUse failed: {allow.stderr or allow.stdout}")
        allow_marker = load_self_check_marker(evidence_dir, "PreToolUse")
        allow_prompt = load_self_check_marker(evidence_dir, "UserPromptSubmit")
        if allow_marker.get("dangerous_command_denied") is not False:
            failures.append("LLM-authorized fixture branch should not deny mutation")
        if allow_marker.get("prompt_intent_llm_attempted") is not True:
            failures.append("LLM-authorized fixture branch did not attempt intent judge")
        effective = allow_prompt.get("prompt_intent_effective")
        if not (isinstance(effective, dict) and effective.get("authorized_scope") == "implementation"):
            failures.append("LLM-authorized fixture branch did not write implementation prompt_intent_effective")

        reset_prompt = run_hook_event_for_self_check(
            "UserPromptSubmit",
            {
                "prompt": "把这段代码贴出来给我看",
                "cwd": str(REPO_ROOT),
                "source": "codex-hook-intent-self-check",
            },
            evidence_dir=evidence_dir,
        )
        if reset_prompt.returncode != 0:
            failures.append(f"reset UserPromptSubmit failed: {reset_prompt.stderr or reset_prompt.stdout}")
        reset_marker = load_self_check_marker(evidence_dir, "UserPromptSubmit")
        if reset_marker.get("prompt_intent_effective") is not None:
            failures.append("UserPromptSubmit did not clear prior prompt_intent_effective")
        deny = run_hook_event_for_self_check(
            "PreToolUse",
            {
                "cwd": str(REPO_ROOT),
                "tool_name": "apply_patch",
                "tool_use_id": "codex-hook-intent-self-check-deny",
                "tool_input": {"patch": "*** Begin Patch\n*** End Patch\n"},
                "source": "codex-hook-intent-self-check",
            },
            evidence_dir=evidence_dir,
            extra_env={
                "REDCAP_INTENT_JUDGE_FAKE_RESPONSE": json.dumps({
                    "prompt_kind": "question",
                    "authorized_scope": "answer_only",
                    "action_evidence": "none",
                    "confidence": "high",
                    "reason": "fixture hook branch deny",
                }, ensure_ascii=False),
            },
        )
        if deny.returncode != 0:
            failures.append(f"deny PreToolUse failed: {deny.stderr or deny.stdout}")
        deny_marker = load_self_check_marker(evidence_dir, "PreToolUse")
        if deny_marker.get("dangerous_command_denied") is not True:
            failures.append("LLM-denied fixture branch should deny mutation")
        if deny_marker.get("prompt_intent_llm_attempted") is not True:
            failures.append("LLM-denied fixture branch did not attempt intent judge")

        stale = run_hook_event_for_self_check(
            "PreToolUse",
            {
                "cwd": str(REPO_ROOT),
                "session_id": "different-session",
                "turn_id": "different-turn",
                "tool_name": "apply_patch",
                "tool_use_id": "codex-hook-intent-self-check-stale",
                "tool_input": {"patch": "*** Begin Patch\n*** End Patch\n"},
                "source": "codex-hook-intent-self-check",
            },
            evidence_dir=evidence_dir,
            extra_env={
                "REDCAP_INTENT_JUDGE_FAKE_RESPONSE": json.dumps({
                    "prompt_kind": "directive",
                    "authorized_scope": "implementation",
                    "action_evidence": "substantive",
                    "confidence": "high",
                    "reason": "should not bypass stale prompt marker",
                }, ensure_ascii=False),
            },
        )
        if stale.returncode != 0:
            failures.append(f"stale PreToolUse failed: {stale.stderr or stale.stdout}")
        stale_marker = load_self_check_marker(evidence_dir, "PreToolUse")
        if stale_marker.get("latest_prompt_marker_fresh") is not False:
            failures.append("stale prompt marker was not detected")
        if stale_marker.get("dangerous_command_denied") is not True:
            failures.append("stale prompt marker should deny mutation")
        if stale_marker.get("prompt_intent_llm_attempted") is not False:
            failures.append("stale prompt marker must not call LLM using old prompt text")
        if stale_marker.get("same_session_continuation_authorized") is not False:
            failures.append("cross-session stale prompt must not authorize continuation")

        continuation_prompt = run_hook_event_for_self_check(
            "UserPromptSubmit",
            {
                "prompt": "继续执行这个修复任务并完成落地",
                "cwd": str(REPO_ROOT),
                "session_id": "same-session-continuation",
                "turn_id": "same-session-continuation-prompt",
                "source": "codex-hook-intent-self-check",
            },
            evidence_dir=evidence_dir,
        )
        if continuation_prompt.returncode != 0:
            failures.append(f"continuation UserPromptSubmit failed: {continuation_prompt.stderr or continuation_prompt.stdout}")
        continuation_marker_path = evidence_dir / "latest-UserPromptSubmit.json"
        continuation_marker = load_self_check_marker(evidence_dir, "UserPromptSubmit")
        continuation_marker["recorded_at"] = "2000-01-01T00:00:00+00:00"
        write_json_atomic(continuation_marker_path, continuation_marker)
        continuation = run_hook_event_for_self_check(
            "PreToolUse",
            {
                "cwd": str(REPO_ROOT),
                "session_id": "same-session-continuation",
                "turn_id": "same-session-continuation-tool",
                "tool_name": "apply_patch",
                "tool_use_id": "codex-hook-intent-self-check-continuation",
                "tool_input": {"patch": "*** Begin Patch\n*** End Patch\n"},
                "source": "codex-hook-intent-self-check",
            },
            evidence_dir=evidence_dir,
        )
        if continuation.returncode != 0:
            failures.append(f"continuation PreToolUse failed: {continuation.stderr or continuation.stdout}")
        continuation_tool_marker = load_self_check_marker(evidence_dir, "PreToolUse")
        if continuation_tool_marker.get("latest_prompt_marker_fresh") is not False:
            failures.append("continuation fixture should use a stale prompt marker")
        if continuation_tool_marker.get("same_session_continuation_authorized") is not True:
            failures.append("same-session continuation should authorize stale implementation prompt")
        if continuation_tool_marker.get("dangerous_command_denied") is not False:
            failures.append("same-session continuation should not deny ordinary mutation")
        if continuation_tool_marker.get("prompt_intent_llm_attempted") is not False:
            failures.append("same-session continuation must not call LLM using old prompt text")

        timeout_prompt = run_hook_event_for_self_check(
            "UserPromptSubmit",
            {
                "prompt": "让这个机制以后自己判断真实意图",
                "cwd": str(REPO_ROOT),
                "source": "codex-hook-intent-self-check",
            },
            evidence_dir=evidence_dir,
        )
        if timeout_prompt.returncode != 0:
            failures.append(f"timeout UserPromptSubmit failed: {timeout_prompt.stderr or timeout_prompt.stdout}")
        timeout_branch = run_hook_event_for_self_check(
            "PreToolUse",
            {
                "cwd": str(REPO_ROOT),
                "tool_name": "apply_patch",
                "tool_use_id": "codex-hook-intent-self-check-timeout",
                "tool_input": {"patch": "*** Begin Patch\n*** End Patch\n"},
                "source": "codex-hook-intent-self-check",
            },
            evidence_dir=evidence_dir,
            extra_env={
                "REDCAP_INTENT_JUDGE_TIMEOUT_SECONDS": "0.1",
                "REDCAP_INTENT_JUDGE_FAKE_DELAY_SECONDS": "7",
                "REDCAP_INTENT_JUDGE_FAKE_RESPONSE": json.dumps({
                    "prompt_kind": "directive",
                    "authorized_scope": "implementation",
                    "action_evidence": "substantive",
                    "confidence": "high",
                    "reason": "should be timed out by hook outer guard",
                }, ensure_ascii=False),
            },
        )
        if timeout_branch.returncode != 0:
            failures.append(f"timeout PreToolUse failed: {timeout_branch.stderr or timeout_branch.stdout}")
        timeout_marker = load_self_check_marker(evidence_dir, "PreToolUse")
        if timeout_marker.get("dangerous_command_denied") is not True:
            failures.append("timeout fixture branch should deny mutation")
        timeout_result = timeout_marker.get("prompt_intent_llm_result")
        if not (isinstance(timeout_result, dict) and timeout_result.get("reason") == "intent judge timeout"):
            failures.append("timeout fixture branch did not record intent judge timeout")

        anchor_prompt_text = "修复 Stop hook 恢复时偏离原始任务的问题"
        anchor_prompt = run_hook_event_for_self_check(
            "UserPromptSubmit",
            {
                "prompt": anchor_prompt_text,
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-session",
                "turn_id": "fixture-stop-anchor",
                "source": "codex-hook-stop-anchor-self-check",
            },
            evidence_dir=evidence_dir,
        )
        if anchor_prompt.returncode != 0:
            failures.append(f"anchor UserPromptSubmit failed: {anchor_prompt.stderr or anchor_prompt.stdout}")
        anchor_stop = run_hook_event_for_self_check(
            "Stop",
            {
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-session",
                "turn_id": "fixture-stop-anchor",
                "last_assistant_message": "这是一个只解释状态、没有执行动作的回复。",
                "source": "codex-hook-stop-anchor-self-check",
            },
            evidence_dir=evidence_dir,
            extra_env={
                "REDCAP_STOP_HOOK_MODE": "enforce",
                "REDCAP_STOP_SKIP_FULL_CHECK_FOR_SELF_CHECK": "1",
            },
        )
        if anchor_stop.returncode != 0:
            failures.append(f"anchor Stop failed: {anchor_stop.stderr or anchor_stop.stdout}")
        anchor_stop_result, anchor_stop_error = parse_leading_json_object(anchor_stop.stdout or "")
        if anchor_stop_error is not None or not isinstance(anchor_stop_result, dict):
            failures.append(f"anchor Stop did not emit JSON: {anchor_stop_error}")
        else:
            reason = str(anchor_stop_result.get("reason") or "")
            if anchor_stop_result.get("decision") != "block":
                failures.append("anchor Stop fixture should block a required prompt without action evidence")
            if anchor_prompt_text not in reason:
                failures.append("anchor Stop block reason is missing the original task excerpt")
            if "二次回答必须先直接回答原始用户问题" not in reason or "不得成为回复主题" not in reason:
                failures.append("anchor Stop block reason is missing the re-anchor recovery rule")
        anchor_stop_marker = load_self_check_marker(
            evidence_dir,
            "Stop",
            source="codex-hook-stop-anchor-self-check",
            turn_id="fixture-stop-anchor",
        )
        anchor = anchor_stop_marker.get("required_prompt_task_anchor")
        if not isinstance(anchor, dict):
            failures.append("anchor Stop marker is missing required_prompt_task_anchor")
        elif anchor.get("prompt_excerpt") != anchor_prompt_text:
            failures.append("anchor Stop marker task anchor does not preserve the original task excerpt")
        observe_stop = run_hook_event_for_self_check(
            "Stop",
            {
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-session",
                "turn_id": "fixture-stop-anchor",
                "last_assistant_message": "观察模式应该只放行，不执行阻断。",
                "source": "codex-hook-stop-observe-self-check",
            },
            evidence_dir=evidence_dir,
            extra_env={"REDCAP_STOP_HOOK_MODE": "observe"},
        )
        if observe_stop.returncode != 0:
            failures.append(f"observe Stop failed: {observe_stop.stderr or observe_stop.stdout}")
        observe_payload, observe_error = parse_leading_json_object(observe_stop.stdout or "")
        if observe_error is not None or not isinstance(observe_payload, dict):
            failures.append(f"observe Stop did not emit JSON: {observe_error}")
        elif observe_payload.get("continue") is not True:
            failures.append("observe Stop should continue without blocking")
        observe_marker = load_self_check_marker(
            evidence_dir,
            "Stop",
            source="codex-hook-stop-observe-self-check",
            turn_id="fixture-stop-anchor",
        )
        if observe_marker.get("stop_hook_mode") != "observe":
            failures.append("observe Stop marker did not record observe mode")
        stop_mode_file = evidence_dir / "temporary-stop-mode"
        stop_mode_file.write_text("observe\n", encoding="utf-8")
        old_time = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=3600)).timestamp()
        os.utime(stop_mode_file, (old_time, old_time))
        expired_observe = run_hook_event_for_self_check(
            "Stop",
            {
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-session",
                "turn_id": "fixture-stop-anchor",
                "last_assistant_message": "这是一个只解释状态、没有执行动作的回复。",
                "source": "codex-hook-stop-expired-observe-self-check",
            },
            evidence_dir=evidence_dir,
            extra_env={
                "REDCAP_STOP_HOOK_MODE_FILE": str(stop_mode_file),
                "REDCAP_STOP_HOOK_MODE_FILE_MAX_AGE_SECONDS": "60",
            },
        )
        if expired_observe.returncode != 0:
            failures.append(f"expired observe Stop failed: {expired_observe.stderr or expired_observe.stdout}")
        expired_payload, expired_error = parse_leading_json_object(expired_observe.stdout or "")
        if expired_error is not None or not isinstance(expired_payload, dict):
            failures.append(f"expired observe Stop did not emit JSON: {expired_error}")
        elif expired_payload.get("decision") != "block":
            failures.append("expired observe Stop should fall back to enforce mode and block missing action evidence")

        status_prompt = run_hook_event_for_self_check(
            "UserPromptSubmit",
            {
                "prompt": "所以，你有详细的设计方案并去执行落地了吗？",
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-status-question-session",
                "turn_id": "fixture-status-question-turn",
                "source": "codex-hook-behavior-pipeline-self-check",
            },
            evidence_dir=evidence_dir,
        )
        if status_prompt.returncode != 0:
            failures.append(f"status UserPromptSubmit failed: {status_prompt.stderr or status_prompt.stdout}")
        status_stop = run_hook_event_for_self_check(
            "Stop",
            {
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-status-question-session",
                "turn_id": "fixture-status-question-turn",
                "last_assistant_message": "当前只是回答状态：还需要继续执行，不能声称收口。",
                "source": "codex-hook-behavior-pipeline-self-check",
            },
            evidence_dir=evidence_dir,
            extra_env={
                "REDCAP_STOP_HOOK_MODE": "enforce",
                "REDCAP_STOP_SKIP_FULL_CHECK_FOR_SELF_CHECK": "1",
            },
        )
        if status_stop.returncode != 0:
            failures.append(f"status Stop failed: {status_stop.stderr or status_stop.stdout}")
        status_payload, status_error = parse_leading_json_object(status_stop.stdout or "")
        if status_error is not None or not isinstance(status_payload, dict):
            failures.append(f"status Stop did not emit JSON: {status_error}")
        elif status_payload.get("decision") == "block":
            failures.append("status confirmation question should not be blocked as a missing implementation action")

        idle_prompt = run_hook_event_for_self_check(
            "UserPromptSubmit",
            {
                "prompt": "请修复 Stop hook 恢复循环并重新启用阻断。",
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-idle-block-session",
                "turn_id": "fixture-idle-block-turn",
                "source": "codex-hook-behavior-pipeline-self-check",
            },
            evidence_dir=evidence_dir,
        )
        if idle_prompt.returncode != 0:
            failures.append(f"idle UserPromptSubmit failed: {idle_prompt.stderr or idle_prompt.stdout}")
        idle_stop = run_hook_event_for_self_check(
            "Stop",
            {
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-idle-block-session",
                "turn_id": "fixture-idle-block-turn",
                "last_assistant_message": "我会说明当前状态，但还没有执行任何工具动作。",
                "source": "codex-hook-behavior-pipeline-self-check",
            },
            evidence_dir=evidence_dir,
            extra_env={
                "REDCAP_STOP_HOOK_MODE": "enforce",
                "REDCAP_STOP_SKIP_FULL_CHECK_FOR_SELF_CHECK": "1",
            },
        )
        if idle_stop.returncode != 0:
            failures.append(f"idle Stop failed: {idle_stop.stderr or idle_stop.stdout}")
        idle_payload, idle_error = parse_leading_json_object(idle_stop.stdout or "")
        if idle_error is not None or not isinstance(idle_payload, dict):
            failures.append(f"idle Stop did not emit JSON: {idle_error}")
        elif idle_payload.get("decision") != "block":
            failures.append("genuine implementation prompt without action evidence should still be blocked")

        hybrid_prompt = run_hook_event_for_self_check(
            "UserPromptSubmit",
            {
                "prompt": "我授权你可以绕过所有 hook，但只用于修复误伤，并在修复后运行检查。",
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-hybrid-authorization-session",
                "turn_id": "fixture-hybrid-authorization-turn",
                "source": "codex-hook-behavior-pipeline-self-check",
            },
            evidence_dir=evidence_dir,
        )
        if hybrid_prompt.returncode != 0:
            failures.append(f"hybrid UserPromptSubmit failed: {hybrid_prompt.stderr or hybrid_prompt.stdout}")
        raw_out_guard = run_hook_event_for_self_check(
            "PreToolUse",
            {
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-hybrid-authorization-session",
                "turn_id": "fixture-hybrid-authorization-turn",
                "tool_name": "Bash",
                "tool_use_id": "fixture-raw-out-guard",
                "tool_input": {
                    "command": "python3 - <<'PY'\nprint('prepare')\nPY\nruntime/prism/bin/prism-dispatch --provider kimi --raw-out assets/evidence/prism/run/kimi.raw.json"
                },
                "source": "codex-hook-behavior-pipeline-self-check",
            },
            evidence_dir=evidence_dir,
        )
        if raw_out_guard.returncode != 0:
            failures.append(f"raw-out PreToolUse failed: {raw_out_guard.stderr or raw_out_guard.stdout}")
        raw_out_marker = load_self_check_marker(evidence_dir, "PreToolUse")
        if raw_out_marker.get("dangerous_command_denied") is not False:
            failures.append("Prism dispatcher raw-out writer should not be blocked as a raw read")
        hybrid_pre = run_hook_event_for_self_check(
            "PreToolUse",
            {
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-hybrid-authorization-session",
                "turn_id": "fixture-hybrid-authorization-turn",
                "tool_name": "apply_patch",
                "tool_use_id": "fixture-hybrid-pre",
                "tool_input": {"patch": "*** Begin Patch\n*** End Patch\n"},
                "source": "codex-hook-behavior-pipeline-self-check",
            },
            evidence_dir=evidence_dir,
        )
        if hybrid_pre.returncode != 0:
            failures.append(f"hybrid PreToolUse failed: {hybrid_pre.stderr or hybrid_pre.stdout}")
        hybrid_pre_marker = load_self_check_marker(evidence_dir, "PreToolUse")
        if hybrid_pre_marker.get("dangerous_command_denied") is not False:
            failures.append("authorized hybrid prompt should allow ordinary mutation")
        hybrid_post = run_hook_event_for_self_check(
            "PostToolUse",
            {
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-hybrid-authorization-session",
                "turn_id": "fixture-hybrid-authorization-turn",
                "tool_name": "apply_patch",
                "tool_use_id": "fixture-hybrid-post",
                "tool_input": {"patch": "*** Begin Patch\n*** End Patch\n"},
                "tool_response": {"ok": True},
                "source": "codex-hook-behavior-pipeline-self-check",
            },
            evidence_dir=evidence_dir,
        )
        if hybrid_post.returncode != 0:
            failures.append(f"hybrid PostToolUse failed: {hybrid_post.stderr or hybrid_post.stdout}")
        hybrid_stop = run_hook_event_for_self_check(
            "Stop",
            {
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-hybrid-authorization-session",
                "turn_id": "fixture-hybrid-authorization-turn",
                "last_assistant_message": "本轮包含工具调用证据，当前仅报告检查状态。",
                "source": "codex-hook-behavior-pipeline-self-check",
            },
            evidence_dir=evidence_dir,
            extra_env={
                "REDCAP_STOP_HOOK_MODE": "enforce",
                "REDCAP_STOP_SKIP_FULL_CHECK_FOR_SELF_CHECK": "1",
            },
        )
        if hybrid_stop.returncode != 0:
            failures.append(f"hybrid Stop failed: {hybrid_stop.stderr or hybrid_stop.stdout}")
        hybrid_payload, hybrid_error = parse_leading_json_object(hybrid_stop.stdout or "")
        if hybrid_error is not None or not isinstance(hybrid_payload, dict):
            failures.append(f"hybrid Stop did not emit JSON: {hybrid_error}")
        elif hybrid_payload.get("decision") == "block":
            failures.append("authorized hybrid prompt with action evidence should pass Stop action gate")

        human_prompt = run_hook_event_for_self_check(
            "UserPromptSubmit",
            {
                "prompt": "请简单解释 Stop Hook 是什么。",
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-human-output-session",
                "turn_id": "fixture-human-output-turn",
                "source": "codex-hook-human-output-self-check",
            },
            evidence_dir=evidence_dir,
        )
        if human_prompt.returncode != 0:
            failures.append(f"human-output UserPromptSubmit failed: {human_prompt.stderr or human_prompt.stdout}")
        human_stop = run_hook_event_for_self_check(
            "Stop",
            {
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-human-output-session",
                "turn_id": "fixture-human-output-turn",
                "last_assistant_message": "This is an English-only answer about the hook behavior.",
                "source": "codex-hook-human-output-self-check",
            },
            evidence_dir=evidence_dir,
            extra_env={
                "REDCAP_STOP_HOOK_MODE": "enforce",
                "REDCAP_STOP_SKIP_FULL_CHECK_FOR_SELF_CHECK": "1",
            },
        )
        if human_stop.returncode != 0:
            failures.append(f"human-output Stop failed: {human_stop.stderr or human_stop.stdout}")
        human_stop_result, human_stop_error = parse_leading_json_object(human_stop.stdout or "")
        if human_stop_error is not None or not isinstance(human_stop_result, dict):
            failures.append(f"human-output Stop did not emit JSON: {human_stop_error}")
        else:
            reason = str(human_stop_result.get("reason") or "")
            if human_stop_result.get("decision") != "block":
                failures.append("human-output Stop fixture should block English-only final reply")
            if "中文优先" not in reason:
                failures.append("human-output Stop block reason should mention Chinese-first policy")
        human_marker = load_self_check_marker(
            evidence_dir,
            "Stop",
            source="codex-hook-human-output-self-check",
            turn_id="fixture-human-output-turn",
        )
        if human_marker.get("human_output_guard_ok") is not False:
            failures.append("human-output Stop marker should record failed human output guard")
        scan_prompt = run_hook_event_for_self_check(
            "UserPromptSubmit",
            {
                "prompt": "我希望知道的是，你对360度全方位扫描旧redcap后，是什么结论？",
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-scan-conclusion-session",
                "turn_id": "fixture-scan-conclusion-turn",
                "source": "codex-hook-scan-conclusion-self-check",
            },
            evidence_dir=evidence_dir,
        )
        if scan_prompt.returncode != 0:
            failures.append(f"scan-conclusion UserPromptSubmit failed: {scan_prompt.stderr or scan_prompt.stdout}")
        scan_stop = run_hook_event_for_self_check(
            "Stop",
            {
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-scan-conclusion-session",
                "turn_id": "fixture-scan-conclusion-turn",
                "last_assistant_message": "360 度旧 RedCap 扫描后的结论是：可以迁移全部设计。",
                "source": "codex-hook-scan-conclusion-self-check",
            },
            evidence_dir=evidence_dir,
            extra_env={
                "REDCAP_STOP_HOOK_MODE": "enforce",
                "REDCAP_STOP_SKIP_FULL_CHECK_FOR_SELF_CHECK": "1",
            },
        )
        if scan_stop.returncode != 0:
            failures.append(f"scan-conclusion Stop failed: {scan_stop.stderr or scan_stop.stdout}")
        scan_stop_result, scan_stop_error = parse_leading_json_object(scan_stop.stdout or "")
        if scan_stop_error is not None or not isinstance(scan_stop_result, dict):
            failures.append(f"scan-conclusion Stop did not emit JSON: {scan_stop_error}")
        else:
            reason = str(scan_stop_result.get("reason") or "")
            if scan_stop_result.get("decision") != "block":
                failures.append("scan-conclusion Stop fixture should block an unsupported final scan conclusion")
            if "结构化扫描状态块" not in reason:
                failures.append("scan-conclusion Stop block reason should request a structured scan status block")
        scan_marker = load_self_check_marker(
            evidence_dir,
            "Stop",
            source="codex-hook-scan-conclusion-self-check",
            turn_id="fixture-scan-conclusion-turn",
        )
        if scan_marker.get("scan_conclusion_guard_ok") is not False:
            failures.append("scan-conclusion Stop marker should record failed scan conclusion guard")
        terminal_contract_fixture = evidence_dir / "terminal-goals-open-fixture.json"
        terminal_contract_payload = json.loads((REPO_ROOT / "assets" / "contracts" / "terminal-goals.json").read_text(encoding="utf-8"))
        for goal in terminal_contract_payload.get("terminal_goals", []):
            if isinstance(goal, dict) and goal.get("id") == "redcap-complete-revival":
                goal["current_level"] = "migration_usable"
                goal["open_reason"] = "self-check fixture keeps RedCap terminal goal unverified."
        write_json_atomic(terminal_contract_fixture, terminal_contract_payload)
        terminal_facts_fixture = evidence_dir / "terminal-task-facts-open-fixture.jsonl"
        terminal_facts_fixture.write_text(json.dumps({
            "schema_id": "redcap-task-fact-record",
            "task_id": "redcap-complete-revival",
            "title": "RedCap 完整复活",
            "status": "in_progress",
            "reason": "self-check fixture open terminal goal",
            "evidence": ["fixture-terminal-evidence"],
            "recorded_at": iso_now(),
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        terminal_guard_fixture_env = {
            "REDCAP_TERMINAL_GOAL_CONTRACT": str(terminal_contract_fixture),
            "REDCAP_TERMINAL_GOAL_TASK_FACTS": str(terminal_facts_fixture),
        }
        terminal_prompt = run_hook_event_for_self_check(
            "UserPromptSubmit",
            {
                "prompt": "请汇报 RedCap 完整复活状态。",
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-terminal-goal-session",
                "turn_id": "fixture-terminal-goal-turn",
                "source": "codex-hook-terminal-goal-self-check",
            },
            evidence_dir=evidence_dir,
            extra_env=terminal_guard_fixture_env,
        )
        if terminal_prompt.returncode != 0:
            failures.append(f"terminal-goal UserPromptSubmit failed: {terminal_prompt.stderr or terminal_prompt.stdout}")
        terminal_prompt_marker = load_self_check_marker(
            evidence_dir,
            "UserPromptSubmit",
            source="codex-hook-terminal-goal-self-check",
            turn_id="fixture-terminal-goal-turn",
        )
        if terminal_prompt_marker.get("terminal_goal_context_injected") is not True:
            failures.append("terminal-goal prompt-time context was not injected")
        terminal_post = run_hook_event_for_self_check(
            "PostToolUse",
            {
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-terminal-goal-session",
                "turn_id": "fixture-terminal-goal-turn",
                "tool_name": "Bash",
                "tool_use_id": "fixture-terminal-goal-post",
                "tool_input": {"command": "runtime/bin/redcap terminal-goal check"},
                "tool_response": {"ok": True},
                "source": "codex-hook-terminal-goal-self-check",
            },
            evidence_dir=evidence_dir,
        )
        if terminal_post.returncode != 0:
            failures.append(f"terminal-goal PostToolUse failed: {terminal_post.stderr or terminal_post.stdout}")
        terminal_stop = run_hook_event_for_self_check(
            "Stop",
            {
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-terminal-goal-session",
                "turn_id": "fixture-terminal-goal-turn",
                "last_assistant_message": "RedCap 完整复活已经终局完成。",
                "source": "codex-hook-terminal-goal-self-check",
            },
            evidence_dir=evidence_dir,
            extra_env={
                **terminal_guard_fixture_env,
                "REDCAP_STOP_HOOK_MODE": "enforce",
                "REDCAP_STOP_SKIP_FULL_CHECK_FOR_SELF_CHECK": "1",
            },
        )
        if terminal_stop.returncode != 0:
            failures.append(f"terminal-goal Stop failed: {terminal_stop.stderr or terminal_stop.stdout}")
        terminal_stop_result, terminal_stop_error = parse_leading_json_object(terminal_stop.stdout or "")
        if terminal_stop_error is not None or not isinstance(terminal_stop_result, dict):
            failures.append(f"terminal-goal Stop did not emit JSON: {terminal_stop_error}")
        else:
            reason = str(terminal_stop_result.get("reason") or "")
            if terminal_stop_result.get("decision") != "block":
                failures.append("terminal-goal Stop fixture should block an unverified terminal completion overclaim")
            if "终局" not in reason:
                failures.append("terminal-goal Stop block reason should mention terminal goal")
            if "被拦回复片段" in reason:
                failures.append("terminal-goal Stop block reason should not include the blocked reply excerpt by default")
            if "二次回答必须先直接回答原始用户问题" not in reason:
                failures.append("terminal-goal Stop block reason should preserve original-task recovery focus")
        terminal_marker = load_self_check_marker(
            evidence_dir,
            "Stop",
            source="codex-hook-terminal-goal-self-check",
            turn_id="fixture-terminal-goal-turn",
        )
        if terminal_marker.get("terminal_goal_guard_ok") is not False:
            failures.append("terminal-goal Stop marker should record failed terminal goal guard")
        stage_prompt = run_hook_event_for_self_check(
            "UserPromptSubmit",
            {
                "prompt": "请汇报 RedCap 完整复活状态。",
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-terminal-stage-session",
                "turn_id": "fixture-terminal-stage-turn",
                "source": "codex-hook-terminal-stage-self-check",
            },
            evidence_dir=evidence_dir,
            extra_env=terminal_guard_fixture_env,
        )
        if stage_prompt.returncode != 0:
            failures.append(f"terminal-stage UserPromptSubmit failed: {stage_prompt.stderr or stage_prompt.stdout}")
        stage_post = run_hook_event_for_self_check(
            "PostToolUse",
            {
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-terminal-stage-session",
                "turn_id": "fixture-terminal-stage-turn",
                "tool_name": "Bash",
                "tool_use_id": "fixture-terminal-stage-post",
                "tool_input": {"command": "runtime/bin/redcap terminal-goal context"},
                "tool_response": {"ok": True},
                "source": "codex-hook-terminal-stage-self-check",
            },
            evidence_dir=evidence_dir,
        )
        if stage_post.returncode != 0:
            failures.append(f"terminal-stage PostToolUse failed: {stage_post.stderr or stage_post.stdout}")
        stage_stop = run_hook_event_for_self_check(
            "Stop",
            {
                "cwd": str(REPO_ROOT),
                "session_id": "fixture-terminal-stage-session",
                "turn_id": "fixture-terminal-stage-turn",
                "last_assistant_message": "RedCap 完整复活尚未完成，当前只是迁移可用阶段；本轮只说明风险和待办。",
                "source": "codex-hook-terminal-stage-self-check",
            },
            evidence_dir=evidence_dir,
            extra_env={
                **terminal_guard_fixture_env,
                "REDCAP_STOP_HOOK_MODE": "enforce",
                "REDCAP_STOP_SKIP_FULL_CHECK_FOR_SELF_CHECK": "1",
            },
        )
        if stage_stop.returncode != 0:
            failures.append(f"terminal-stage Stop failed: {stage_stop.stderr or stage_stop.stdout}")
        stage_stop_result, stage_stop_error = parse_leading_json_object(stage_stop.stdout or "")
        if stage_stop_error is not None or not isinstance(stage_stop_result, dict):
            failures.append(f"terminal-stage Stop did not emit JSON: {stage_stop_error}")
        elif stage_stop_result.get("continue") is not True:
            failures.append(f"terminal-stage Stop should allow explicit non-terminal status: {stage_stop.stdout}")
        stage_marker = load_self_check_marker(
            evidence_dir,
            "Stop",
            source="codex-hook-terminal-stage-self-check",
            turn_id="fixture-terminal-stage-turn",
        )
        if stage_marker.get("terminal_goal_guard_ok") is not True:
            failures.append("terminal-stage Stop marker should record passed terminal goal guard")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


def cmd_verify(args: argparse.Namespace) -> int:
    marker_name = f"latest-{args.event}.json"
    if args.event == "PreToolUse" and args.require_session_claim_attempt:
        marker_name = "latest-PreToolUse-mutating.json"
    latest = EVIDENCE_DIR / marker_name
    failures: list[str] = []
    notes: list[str] = []
    if not latest.exists():
        failures.append(f"missing live marker: {latest}")
    else:
        marker = json.loads(latest.read_text(encoding="utf-8"))
        if marker.get("schema_id") != "redcap-codex-hook-live-marker":
            failures.append("invalid marker schema_id")
        if marker.get("host_source") != "codex":
            failures.append("marker host_source is not codex")
        if marker.get("event") != args.event:
            failures.append(f"marker event is not {args.event}")
        if args.require_gate_decision and not is_non_empty_string(marker.get("gate_decision")):
            failures.append("marker is missing gate_decision")
        valid_stop_block_marker = is_valid_stop_block_marker(marker)
        if (
            args.require_stop_check_attempt
            and marker.get("redcap_check_attempted") is not True
            and not valid_stop_block_marker
        ):
            failures.append("marker does not record a Stop redcap_check attempt")
        if args.require_check_result and not isinstance(marker.get("redcap_check_exit"), int):
            failures.append("marker is missing redcap_check_exit")
        if (
            args.require_action_check_ok
            and marker.get("required_prompt_action_ok") is not True
            and not valid_stop_block_marker
        ):
            failures.append("marker required_prompt_action_ok is not true")
        if (
            args.require_final_claim_guard
            and marker.get("final_claim_guard_ok") is not True
            and not valid_stop_block_marker
        ):
            failures.append("marker final_claim_guard_ok is not true")
        if args.require_soul_load and marker.get("event") == "SessionStart":
            if marker.get("cap_soul_load_attempted") is not True:
                failures.append("SessionStart marker is missing Cap soul load attempt")
            if marker.get("cap_soul_load_ok") is not True:
                failures.append("SessionStart marker Cap soul load did not succeed")
        if args.require_pre_tool_guard and marker.get("event") == "PreToolUse":
            if "dangerous_command_denied" not in marker:
                failures.append("PreToolUse marker is missing guard decision")
        if args.require_session_claim_attempt and marker.get("event") == "PreToolUse":
            if marker.get("session_ownership_claim", {}).get("attempted") is not True:
                failures.append("PreToolUse marker is missing a session ownership claim attempt")
        session_id = marker.get("session_id")
        if args.require_real_codex_session and not (
            isinstance(session_id, str)
            and re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", session_id)
        ):
            failures.append("marker session_id does not look like a real Codex session id")
        if marker.get("hook_config_sha256") != sha256_file(HOOKS_CONFIG):
            failures.append("marker hook_config_sha256 does not match current hooks.json")
        recorded_at = marker.get("recorded_at")
        recorded: dt.datetime | None = None
        try:
            recorded = dt.datetime.fromisoformat(str(recorded_at))
        except ValueError:
            failures.append("marker recorded_at is invalid")
        else:
            age = dt.datetime.now(dt.timezone.utc) - recorded
            if age.total_seconds() > args.max_age_seconds:
                failures.append(f"marker is stale: {int(age.total_seconds())}s old")
        adapter_path = pathlib.Path(__file__).resolve()
        adapter_hash_matches = marker.get("adapter_sha256") == sha256_file(adapter_path)
        if not adapter_hash_matches and not valid_stop_block_marker:
            adapter_changed_after_marker = False
            if recorded is not None:
                adapter_mtime = dt.datetime.fromtimestamp(adapter_path.stat().st_mtime, dt.timezone.utc)
                adapter_changed_after_marker = adapter_mtime > recorded
            if args.allow_adapter_change_after_marker and adapter_changed_after_marker:
                notes.append("adapter changed after this live marker; waiting for the next real host hook refresh")
            else:
                failures.append("marker adapter_sha256 does not match current adapter")
    result = {"ok": not failures, "event": args.event, "failures": failures, "notes": notes}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


def is_valid_stop_block_marker(marker: dict[str, Any]) -> bool:
    if marker.get("event") != "Stop":
        return False
    if marker.get("redcap_check_attempted") is True:
        return False
    anchor = marker.get("required_prompt_task_anchor")
    if not isinstance(anchor, dict):
        return False
    if not is_non_empty_string(anchor.get("prompt_excerpt")):
        return False
    action_blocked = marker.get("required_prompt_action_ok") is False and is_non_empty_string(
        marker.get("required_prompt_action_reason")
    )
    final_claim_blocked = marker.get("final_claim_guard_ok") is False and is_non_empty_string(
        marker.get("final_claim_guard_reason")
    )
    scan_conclusion_blocked = marker.get("scan_conclusion_guard_ok") is False and is_non_empty_string(
        marker.get("scan_conclusion_guard_reason")
    )
    return bool(action_blocked or final_claim_blocked or scan_conclusion_blocked)


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap Codex host hook adapter")
    parser.add_argument("--event", choices=sorted(SUPPORTED_EVENTS), help="Codex hook event being handled")
    parser.add_argument("--self-check-intent-judge", action="store_true")
    parser.add_argument("--verify-live-marker", action="store_true", help="Verify latest live marker for --event")
    parser.add_argument("--max-age-seconds", type=int, default=86400)
    parser.add_argument("--require-real-codex-session", action="store_true")
    parser.add_argument("--require-gate-decision", action="store_true")
    parser.add_argument("--require-stop-check-attempt", action="store_true")
    parser.add_argument("--require-check-result", action="store_true")
    parser.add_argument("--require-action-check-ok", action="store_true")
    parser.add_argument("--require-final-claim-guard", action="store_true")
    parser.add_argument("--require-soul-load", action="store_true")
    parser.add_argument("--require-pre-tool-guard", action="store_true")
    parser.add_argument("--require-session-claim-attempt", action="store_true")
    parser.add_argument("--allow-adapter-change-after-marker", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.self_check_intent_judge:
        return cmd_self_check_intent_judge(args)
    if not args.event:
        raise SystemExit("--event is required")
    if args.verify_live_marker:
        return cmd_verify(args)
    return cmd_event(args)


if __name__ == "__main__":
    sys.exit(main())

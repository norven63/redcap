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
SUPPORTED_EVENTS = {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}
INTENT_JUDGE_TIMEOUT_SECONDS = float(os.environ.get("REDCAP_INTENT_JUDGE_TIMEOUT_SECONDS", "75"))
INTENT_JUDGE_PROVIDER = os.environ.get("REDCAP_INTENT_JUDGE_PROVIDER", "claude-code")
INTENT_JUDGE_FALLBACK_PROVIDER = os.environ.get("REDCAP_INTENT_JUDGE_FALLBACK_PROVIDER", "claude-code")
INTENT_JUDGE_FAKE_RESPONSE = os.environ.get("REDCAP_INTENT_JUDGE_FAKE_RESPONSE")
INTENT_JUDGE_FAKE_DELAY_SECONDS = os.environ.get("REDCAP_INTENT_JUDGE_FAKE_DELAY_SECONDS")
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


def run_command(argv: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        argv,
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    return {
        "argv": argv,
        "exit_code": completed.returncode,
        "stdout_length": len(stdout),
        "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest() if stdout else None,
        "stderr_length": len(stderr),
        "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest() if stderr else None,
        "stdout": stdout,
        "stderr": stderr,
    }


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
    parts.append(
        "Recovery rule: return to that original task first, then report same-turn actions/checks or a concrete blocker; "
        "mention this Stop hook only as recovery context."
    )
    return " ".join(parts)


def run_prompt_gate(payload: dict[str, Any], prompt: str) -> dict[str, Any]:
    trimmed = prompt[:MAX_GATE_PROMPT_CHARS]
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
    ]
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        argv.extend(["--boundary-cwd", cwd])
    command = run_command(argv)
    result: dict[str, Any] = {
        "exit_code": command["exit_code"],
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
    return result


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
        return "assets/evidence/prism" in normalized or "assets/evidence" in normalized or normalized.endswith("assets")
    candidate = pathlib.Path(expanded)
    if not candidate.is_absolute():
        candidate = pathlib.Path(cwd if cwd else REPO_ROOT) / candidate
    try:
        resolved = candidate.resolve()
        prism = PROTECTED_PRISM_EVIDENCE_ROOT.resolve()
        resolved.relative_to(prism)
        return True
    except ValueError:
        pass
    try:
        prism.relative_to(resolved)
        return True
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
    for key in ["session_id", "turn_id"]:
        expected = payload.get(key)
        if isinstance(expected, str) and expected.strip() and prompt_marker.get(key) != expected:
            return False
    return True


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
        prompt_intent = classify_prompt_intent(prompt)
        gate = run_prompt_gate(payload, prompt) if prompt.strip() else {
            "exit_code": 0,
            "prompt_truncated": False,
            "parse_ok": False,
            "decision": "skipped",
            "matched_rules": [],
            "review_mode": None,
            "required_providers": [],
        }
        marker = update_latest_marker("UserPromptSubmit", {
            "gate_decision": gate.get("decision"),
            "gate_review_mode": gate.get("review_mode"),
            "gate_matched_rules": gate.get("matched_rules"),
            "gate_required_providers": gate.get("required_providers"),
            "gate_self_development_lifecycle": gate.get("self_development_lifecycle", {}),
            "gate_exit_code": gate.get("exit_code"),
            "gate_parse_ok": gate.get("parse_ok"),
            "gate_prompt_truncated": gate.get("prompt_truncated"),
            "gate_stdout_length": gate.get("stdout_length"),
            "gate_stdout_sha256": gate.get("stdout_sha256"),
            "gate_stderr_length": gate.get("stderr_length"),
            "gate_stderr_sha256": gate.get("stderr_sha256"),
            "prompt_intent": prompt_intent,
            "prompt_intent_effective": None,
            "prompt_intent_llm": None,
        }, base_marker=marker)
        decision = marker.get("gate_decision")
        if decision == "required":
            lifecycle = marker.get("gate_self_development_lifecycle") if isinstance(marker, dict) else {}
            scope = prompt_intent.get("authorized_scope")
            action_evidence = prompt_intent.get("action_evidence")
            if scope in {"answer_only", "review_only"}:
                context = (
                    "RedCap UserPromptSubmit hook fired. This prompt is classified as "
                    f"{scope}; normal answer/review may proceed without task-body action, "
                    "but implementation or completion claims still require the RedCap gates."
                )
            elif isinstance(lifecycle, dict) and lifecycle.get("required") is True and lifecycle.get("checked") is not True:
                context = (
                    "RedCap UserPromptSubmit hook fired: Prism rule review and a self-development lifecycle packet "
                    "are required before implementation or completion claims unless Norven explicitly overrides."
                )
            else:
                context = (
                    "RedCap UserPromptSubmit hook fired and Prism rule review is required. "
                    "Run full Prism before implementation or completion claims unless Norven explicitly overrides."
                )
        else:
            context = (
                "RedCap UserPromptSubmit hook fired. Gate decision: "
                f"{decision or 'unknown'}."
            )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context,
            },
            "systemMessage": f"RedCap prompt hook recorded gate decision: {decision or 'unknown'}",
        }, ensure_ascii=False))
    elif args.event == "PreToolUse":
        command = tool_command(payload)
        cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
        prompt_marker = latest_user_prompt_marker()
        intent_deny_reason = None
        intent_judge = None
        prompt_marker_fresh = prompt_marker_is_fresh_for_tool(prompt_marker, payload)
        if tool_is_mutating(payload, command):
            if not prompt_marker_fresh:
                intent_deny_reason = (
                    "Latest RedCap prompt marker is missing or stale for this tool event; "
                    "mutation requires a fresh UserPromptSubmit marker."
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
                "additionalContext": f"RedCap PostToolUse action evidence recorded for {tool_name}.",
            },
            "systemMessage": f"RedCap action evidence recorded for {tool_name}.",
        }, ensure_ascii=False))
    elif args.event == "Stop":
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
                "RedCap Stop hook found a required RedCap prompt with no same-turn action evidence. "
                "Do not close with explanation/status only; perform the concrete remediation, run the required checks, "
                "or explicitly mark the task blocked with the blocking condition."
            )
            if anchor_clause:
                reason = f"{reason} {anchor_clause}"
            if isinstance(action_reason, str) and action_reason.strip():
                reason = f"{reason} Action check reason: {action_reason}"
            print(json.dumps({
                "decision": "block",
                "reason": reason,
                "systemMessage": "RedCap required-prompt action evidence gate failed.",
            }, ensure_ascii=False))
            return 0
        final_guard = run_command([
            sys.executable,
            str(FINAL_CLAIM_GUARD),
            "check",
            "--message",
            str(payload.get("last_assistant_message") or ""),
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
                "RedCap Stop hook detected a final completion claim for a required RedCap prompt "
                "without a fresh verified task-body lifecycle completion marker. Continue the turn: "
                "either perform the task body and run lifecycle check with completion_claim.present=true, "
                "or remove/narrow the completion claim."
            )
            anchor_clause = stop_task_anchor_clause(action_result)
            if anchor_clause:
                reason = f"{reason} {anchor_clause}"
            guard_reason = final_guard_result.get("reason")
            if isinstance(guard_reason, str) and guard_reason.strip():
                reason = f"{reason} Guard reason: {guard_reason}"
            print(json.dumps({
                "decision": "block",
                "reason": reason,
                "systemMessage": "RedCap final completion claim guard failed.",
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
                "systemMessage": "RedCap Stop hook check passed.",
            }, ensure_ascii=False))
        else:
            reason = (
                "RedCap Stop hook ran runtime/bin/redcap check and it failed. "
                "Continue the turn, inspect the failing check output locally, fix the concrete issue, "
                "then rerun runtime/bin/redcap check before completion."
            )
            print(json.dumps({
                "decision": "block",
                "reason": reason,
                "systemMessage": f"RedCap Stop hook check failed with exit {marker['redcap_check_exit']}.",
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
        timeout=30,
    )


def load_self_check_marker(evidence_dir: pathlib.Path, event: str) -> dict[str, Any]:
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
    if prism_raw_read_reason("rg -n provider runtime assets", str(REPO_ROOT)) is None:
        failures.append("Prism evidence ancestor rg search without raw exclusions was not blocked")
    if prism_raw_read_reason("rg -n provider runtime assets -g '!*.raw.json' -g '!*.raw.meta.json'", str(REPO_ROOT)) is not None:
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
            if "return to that original task first" not in reason:
                failures.append("anchor Stop block reason is missing the re-anchor recovery rule")
        anchor_stop_marker = load_self_check_marker(evidence_dir, "Stop")
        anchor = anchor_stop_marker.get("required_prompt_task_anchor")
        if not isinstance(anchor, dict):
            failures.append("anchor Stop marker is missing required_prompt_task_anchor")
        elif anchor.get("prompt_excerpt") != anchor_prompt_text:
            failures.append("anchor Stop marker task anchor does not preserve the original task excerpt")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


def cmd_verify(args: argparse.Namespace) -> int:
    marker_name = f"latest-{args.event}.json"
    if args.event == "PreToolUse" and args.require_session_claim_attempt:
        marker_name = "latest-PreToolUse-mutating.json"
    latest = EVIDENCE_DIR / marker_name
    failures: list[str] = []
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
        if args.require_stop_check_attempt and marker.get("redcap_check_attempted") is not True:
            failures.append("marker does not record a Stop redcap_check attempt")
        if args.require_check_result and not isinstance(marker.get("redcap_check_exit"), int):
            failures.append("marker is missing redcap_check_exit")
        if args.require_action_check_ok and marker.get("required_prompt_action_ok") is not True:
            failures.append("marker required_prompt_action_ok is not true")
        if args.require_final_claim_guard and marker.get("final_claim_guard_ok") is not True:
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
        if marker.get("adapter_sha256") != sha256_file(pathlib.Path(__file__).resolve()):
            failures.append("marker adapter_sha256 does not match current adapter")
        recorded_at = marker.get("recorded_at")
        try:
            recorded = dt.datetime.fromisoformat(str(recorded_at))
        except ValueError:
            failures.append("marker recorded_at is invalid")
        else:
            age = dt.datetime.now(dt.timezone.utc) - recorded
            if age.total_seconds() > args.max_age_seconds:
                failures.append(f"marker is stale: {int(age.total_seconds())}s old")
    result = {"ok": not failures, "event": args.event, "failures": failures}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


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

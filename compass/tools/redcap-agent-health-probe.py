#!/usr/bin/env python3
# 用途：棱镜与 Agent 路由脚本；详细职责见文件查阅字典。

"""Probe local Agent CLI health without violating provider freeze windows.

Dictionary: references/file-lookup-dictionary.md#prism-and-providers
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


AGENTS: dict[str, dict[str, object]] = {
    "kimi": {
        "binary": "kimi",
        "command": ["kimi", "-y", "-p", "respond only: ok"],
        "live_supported": True,
    },
    "gemini": {
        "binary": "gemini",
        "command": ["gemini", "-p", "respond only: ok", "--yolo"],
        "live_supported": True,
    },
    "copilot": {
        "binary": "copilot",
        "command": ["copilot", "-p", "respond only: ok"],
        "live_supported": True,
    },
    "claude-code": {
        "binary": "claude",
        "command": ["claude", "-p", "respond only: ok"],
        "live_supported": True,
        "min_timeout_s": 60,
    },
    "codex": {
        "binary": "codex",
        "command": ["codex", "exec", "respond only: ok"],
        "live_supported": True,
        "requires_env": "REDCAP_ALLOW_CODEX_LIVE_PROBE",
        "reason": "Codex CLI live probe can create nested agent sessions; it is allowed only as explicit last-resort fallback.",
    },
}

DEFAULT_PROVIDER_POLICY = "references/prism-provider-policy.json"
PROTECTED_FALLBACK_TIERS = {"protected-fallback", "protected_fallback", "fallback-after-required-unavailable"}
PROVIDER_ALIASES = {
    "claude": "claude-code",
    "claude-code": "claude-code",
    "copilot": "copilot",
    "codex": "codex",
    "gemini": "gemini",
    "kimi": "kimi",
}


def normalize_agent_name(name: str) -> str:
    return PROVIDER_ALIASES.get(name.strip().lower(), name.strip().lower())


def load_dotenv(root: Path, env: dict[str, str]) -> None:
    path = root / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in env:
            env[key] = value


def parse_policy_time(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def load_provider_policy(root: Path, policy_arg: str) -> dict[str, object]:
    policy_path = Path(policy_arg)
    if not policy_path.is_absolute():
        policy_path = root / policy_path
    if not policy_path.is_file():
        return {"_policy_unavailable": True, "_policy_unavailable_reason": f"provider policy file missing: {policy_path}"}
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"_policy_unavailable": True, "_policy_unavailable_reason": f"provider policy unavailable or invalid: {policy_path}"}
    return payload if isinstance(payload, dict) else {}


def active_freeze(policy: dict[str, object], agent: str, scope: str) -> dict[str, object] | None:
    now = datetime.now(timezone.utc)
    for item in policy.get("freeze_windows", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("agent") != agent:
            continue
        scopes = item.get("scope", [])
        if isinstance(scopes, list) and scope not in scopes and "all" not in scopes:
            continue
        starts_at = parse_policy_time(item.get("starts_at"))
        until = parse_policy_time(item.get("until"))
        if starts_at is not None and now < starts_at.astimezone(timezone.utc):
            continue
        if until is not None and now >= until.astimezone(timezone.utc):
            continue
        return item
    return None


def scopes_include(raw: object, scope: str) -> bool:
    if raw is None:
        return True
    if isinstance(raw, str):
        return raw in {scope, "all"}
    if isinstance(raw, list):
        return scope in raw or "all" in raw
    return False


def routing_override_for(policy: dict[str, object], agent: str, scope: str) -> dict[str, object] | None:
    canonical = normalize_agent_name(agent)
    for item in policy.get("routing_overrides", []) or []:
        if not isinstance(item, dict):
            continue
        if normalize_agent_name(str(item.get("agent", ""))) != canonical:
            continue
        if not scopes_include(item.get("scope"), scope):
            continue
        return item
    return None


def normalize_routing_tier(raw: object) -> str:
    tier = str(raw or "normal").strip().lower().replace("_", "-")
    if tier in PROTECTED_FALLBACK_TIERS:
        return "protected-fallback"
    return tier or "normal"


def protected_fallback_required(policy: dict[str, object], agent: str, scope: str) -> list[str]:
    override = routing_override_for(policy, agent, scope)
    if not override:
        return []
    if normalize_routing_tier(override.get("priority_tier") or override.get("mode")) != "protected-fallback":
        return []
    raw_required = override.get("allowed_when_all_unavailable")
    if not isinstance(raw_required, list):
        return []
    result: list[str] = []
    for item in raw_required:
        if isinstance(item, str) and item.strip():
            result.append(normalize_agent_name(item))
    return result


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def direct_child_pids(pid: int) -> list[int]:
    try:
        result = subprocess.run(
            ["pgrep", "-P", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return []
    children: list[int] = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if line.isdigit():
            children.append(int(line))
    return children


def descendant_pids(pid: int) -> list[int]:
    seen: set[int] = set()
    stack = [pid]
    descendants: list[int] = []
    while stack:
        current = stack.pop()
        for child in direct_child_pids(current):
            if child in seen:
                continue
            seen.add(child)
            descendants.append(child)
            stack.append(child)
    return descendants


def signal_process_group(pid: int, sig: int) -> None:
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass


def signal_process_tree(pid: int, sig: int) -> None:
    for child in reversed(descendant_pids(pid)):
        try:
            os.kill(child, sig)
        except ProcessLookupError:
            pass
    signal_process_group(pid, sig)


def process_tree_alive(pid: int) -> bool:
    return pid_alive(pid) or any(pid_alive(child) for child in descendant_pids(pid))


def wait_process_tree_gone(pid: int, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not process_tree_alive(pid):
            return True
        time.sleep(0.05)
    return not process_tree_alive(pid)


def run_probe_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_s: int,
) -> tuple[str, str, int | None, bool]:
    proc = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        return stdout or "", stderr or "", proc.returncode, False
    except subprocess.TimeoutExpired:
        signal_process_tree(proc.pid, signal.SIGTERM)
        if not wait_process_tree_gone(proc.pid, 2):
            signal_process_tree(proc.pid, signal.SIGKILL)
            wait_process_tree_gone(proc.pid, 2)
        try:
            stdout, stderr = proc.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            signal_process_tree(proc.pid, signal.SIGKILL)
            wait_process_tree_gone(proc.pid, 2)
            stdout, stderr = proc.communicate()
        return stdout or "", stderr or "", None, True


def probe_agent(root: Path, name: str, live: bool, timeout_s: int, provider_policy: dict[str, object]) -> dict[str, object]:
    spec = AGENTS[name]
    binary = str(spec["binary"])
    path = shutil.which(binary)
    row: dict[str, object] = {
        "agent": name,
        "binary": binary,
        "installed": bool(path),
        "path": path or "",
        "live_probe_requested": live,
    }
    if not path:
        row.update({"live_status": "unavailable", "reason": "CLI not installed"})
        return row
    if not live:
        row.update({"live_status": "skipped", "reason": "live probe not requested"})
        return row
    if name == "copilot" and provider_policy.get("_policy_unavailable"):
        row.update(
            {
                "live_status": "policy-unavailable",
                "reason": provider_policy.get("_policy_unavailable_reason", "provider policy unavailable"),
            }
        )
        return row
    freeze = active_freeze(provider_policy, name, "live-health")
    if freeze is not None:
        row.update(
            {
                "live_status": "frozen",
                "reason": freeze.get("reason", "provider frozen by policy"),
                "frozen_until": freeze.get("until", ""),
            }
        )
        return row
    env = os.environ.copy()
    load_dotenv(root, env)
    required_env = str(spec.get("requires_env") or "")
    if required_env and env.get(required_env, "").strip().lower() not in {"1", "true", "yes"}:
        row.update({"live_status": "unsupported", "reason": spec.get("reason", f"live probe requires {required_env}")})
        return row
    if not bool(spec.get("live_supported", False)):
        row.update({"live_status": "unsupported", "reason": spec.get("reason", "live probe unsupported")})
        return row

    effective_timeout_s = max(timeout_s, int(spec.get("min_timeout_s", timeout_s)))
    command = [str(part) for part in spec["command"]]
    try:
        stdout, stderr, returncode, timed_out = run_probe_command(
            command,
            cwd=root,
            env=env,
            timeout_s=effective_timeout_s,
        )
    except Exception as exc:
        row.update({"live_status": "error", "reason": str(exc)})
        return row
    if timed_out:
        row.update({"live_status": "timeout", "timeout_s": effective_timeout_s})
        return row
    if returncode is None:
        row.update({"live_status": "error", "reason": "probe exited without return code"})
        return row

    output = (stdout + "\n" + stderr).strip()
    row.update(
        {
            "live_status": "pass" if returncode == 0 else "fail",
            "returncode": returncode,
            "output_excerpt": output[:500],
        }
    )
    return row


def policy_suppressed_probe_row(
    name: str,
    path: str,
    required: list[str],
    required_available: list[str],
) -> dict[str, object]:
    spec = AGENTS[name]
    return {
        "agent": name,
        "binary": str(spec["binary"]),
        "installed": bool(path),
        "path": path or "",
        "live_probe_requested": True,
        "live_status": "policy-suppressed",
        "reason": "protected fallback suppressed because required primary providers are available: "
        + ",".join(required_available),
        "fallback_after_unavailable": required,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("--agent", action="append", choices=sorted(AGENTS), help="Probe only this agent; may be repeated.")
    parser.add_argument("--live", action="store_true", help="Run bounded live CLI calls instead of install/config detection only.")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--stdout", action="store_true", help="Print JSON to stdout instead of writing the cache file.")
    parser.add_argument("--output", default="compass/.workflow/agent-health.json")
    parser.add_argument("--provider-policy", default=DEFAULT_PROVIDER_POLICY)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    names = args.agent or sorted(AGENTS)
    provider_policy = load_provider_policy(root, args.provider_policy)
    rows_by_agent: dict[str, dict[str, object]] = {}
    rows: list[dict[str, object]] = []
    deferred: list[tuple[str, list[str]]] = []
    for name in names:
        required = protected_fallback_required(provider_policy, name, "live-health")
        if bool(args.live) and required:
            deferred.append((name, required))
            continue
        row = probe_agent(root, name, bool(args.live), int(args.timeout), provider_policy)
        rows.append(row)
        rows_by_agent[normalize_agent_name(name)] = row

    for name, required in deferred:
        for required_name in required:
            if required_name in AGENTS and required_name not in rows_by_agent:
                row = probe_agent(root, required_name, bool(args.live), int(args.timeout), provider_policy)
                rows.append(row)
                rows_by_agent[required_name] = row
        required_available = sorted(
            provider
            for provider in required
            if rows_by_agent.get(provider, {}).get("live_status") == "pass"
        )
        if required_available:
            path = shutil.which(str(AGENTS[name]["binary"])) or ""
            row = policy_suppressed_probe_row(name, path, required, required_available)
        else:
            row = probe_agent(root, name, bool(args.live), int(args.timeout), provider_policy)
        rows.append(row)
        rows_by_agent[normalize_agent_name(name)] = row

    payload = {
        "version": 1,
        "detected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "live": bool(args.live),
        "timeout_s": args.timeout,
        "provider_policy": args.provider_policy,
        "agents": rows,
    }

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.stdout:
        print(text)
    else:
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
        print(f"AGENT_HEALTH_PROBE_OK {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

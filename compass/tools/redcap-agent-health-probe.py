#!/usr/bin/env python3
"""Probe local Agent CLI health without violating provider freeze windows.

Dictionary: references/file-lookup-dictionary.md#prism-and-providers
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
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
        completed = subprocess.run(
            command,
            cwd=root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=effective_timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        row.update({"live_status": "timeout", "timeout_s": effective_timeout_s})
        return row
    except Exception as exc:
        row.update({"live_status": "error", "reason": str(exc)})
        return row

    output = (completed.stdout + "\n" + completed.stderr).strip()
    row.update(
        {
            "live_status": "pass" if completed.returncode == 0 else "fail",
            "returncode": completed.returncode,
            "output_excerpt": output[:500],
        }
    )
    return row


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
    payload = {
        "version": 1,
        "detected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "live": bool(args.live),
        "timeout_s": args.timeout,
        "provider_policy": args.provider_policy,
        "agents": [probe_agent(root, name, bool(args.live), int(args.timeout), provider_policy) for name in names],
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

#!/usr/bin/env python3
"""Audit host hook coverage and provider-call interception boundaries."""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
HOOKS_CONFIG = REPO_ROOT / ".codex" / "hooks.json"
CODEX_ADAPTER = "runtime/host-adapters/codex/codex-hook.py"
REQUIRED_CODEX_EVENTS = {
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Stop",
}
AUDITED_UNSUPPORTED_EVENTS = {
    "PermissionRequest": "No verified Codex project hook event or provider CLI lifecycle equivalent is available in this workspace.",
    "PreCompact": "No verified Codex project hook event or provider CLI lifecycle equivalent is available in this workspace.",
    "PostCompact": "No verified Codex project hook event or provider CLI lifecycle equivalent is available in this workspace.",
}


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"expected object json: {path}")
    return payload


def hook_commands(config: dict[str, Any], event: str) -> list[str]:
    commands: list[str] = []
    for group in config.get("hooks", {}).get(event, []) or []:
        if not isinstance(group, dict):
            continue
        for hook in group.get("hooks", []) or []:
            if isinstance(hook, dict) and hook.get("type") == "command" and isinstance(hook.get("command"), str):
                commands.append(hook["command"])
    return commands


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=str(REPO_ROOT), check=False, capture_output=True, text=True)


def main() -> int:
    failures: list[str] = []
    config = load_json(HOOKS_CONFIG)
    deployed: dict[str, bool] = {}
    for event in sorted(REQUIRED_CODEX_EVENTS):
        commands = hook_commands(config, event)
        ok = any(CODEX_ADAPTER in command and f"--event {event}" in command for command in commands)
        deployed[event] = ok
        if not ok:
            failures.append(f"Codex hook event is not deployed through adapter: {event}")

    provider_cli = {
        "kimi": shutil.which("kimi"),
        "claude-code": shutil.which("claude"),
    }
    for provider, path in provider_cli.items():
        if not path:
            failures.append(f"provider CLI missing: {provider}")

    dispatcher = run(["runtime/prism/bin/prism-dispatch", "--self-check"])
    if dispatcher.returncode != 0 or "PRISM_DISPATCH_SELF_CHECK_OK" not in dispatcher.stdout:
        failures.append("provider dispatcher self-check failed")

    result = {
        "ok": not failures,
        "codex_hooks": deployed,
        "provider_call_interception": {
            "mode": "dispatcher-enforced",
            "providers": sorted(provider_cli),
            "dispatcher_self_check": dispatcher.returncode == 0,
        },
        "unsupported_events": AUDITED_UNSUPPORTED_EVENTS,
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_HOST_HOOK_AUDIT_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

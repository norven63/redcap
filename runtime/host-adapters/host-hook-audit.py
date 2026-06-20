#!/usr/bin/env python3
"""Audit host hook coverage and provider-call interception boundaries."""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import argparse
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PROJECT_ROOT = REPO_ROOT.parent if REPO_ROOT.name == ".redcap" else REPO_ROOT
HOOKS_CONFIG = PROJECT_ROOT / ".codex" / "hooks.json"
HOOKS_TEMPLATE = REPO_ROOT / "assets" / "contracts" / "codex-hooks.template.json"
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


def normalize_hook_config(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): normalize_hook_config(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [normalize_hook_config(item) for item in value]
    if isinstance(value, str):
        return value.replace(str(REPO_ROOT), "{REPO_ROOT}")
    return value


def run(argv: list[str], *, timeout_seconds: int = 180) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            argv,
            124,
            stdout=exc.stdout or "",
            stderr=f"命令超时：{timeout_seconds} 秒",
        )


def run_with_retry(argv: list[str], *, attempts: int = 2) -> list[subprocess.CompletedProcess[str]]:
    results = []
    for _ in range(max(1, attempts)):
        completed = run(argv)
        results.append(completed)
        if completed.returncode == 0:
            break
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit RedCap host hook coverage and provider-call interception boundaries")
    parser.add_argument(
        "--skip-codex-hook-self-check",
        action="store_true",
        help="Skip the expensive Codex hook behavioral self-check when another required probe has already executed it in the same verification matrix.",
    )
    args = parser.parse_args()
    failures: list[str] = []
    config = load_json(HOOKS_CONFIG)
    template = load_json(HOOKS_TEMPLATE)
    live_normalized = normalize_hook_config(config)
    template_normalized = normalize_hook_config(template)
    if live_normalized != template_normalized:
        failures.append("live .codex/hooks.json does not match tracked assets/contracts/codex-hooks.template.json")
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
    codex_hook_attempts: list[subprocess.CompletedProcess[str]] = []
    codex_hook: subprocess.CompletedProcess[str] | None = None
    if not args.skip_codex_hook_self_check:
        codex_hook_attempts = run_with_retry([sys.executable, CODEX_ADAPTER, "--self-check-intent-judge"])
        codex_hook = codex_hook_attempts[-1]
        if codex_hook.returncode != 0:
            failures.append("codex hook self-check failed")

    result = {
        "ok": not failures,
        "codex_hooks": deployed,
        "codex_hook_template": {
            "template_path": str(HOOKS_TEMPLATE.relative_to(REPO_ROOT)),
            "live_path": str(HOOKS_CONFIG.relative_to(PROJECT_ROOT)),
            "matches": live_normalized == template_normalized,
        },
        "provider_call_interception": {
            "mode": "dispatcher-enforced",
            "providers": sorted(provider_cli),
            "dispatcher_self_check": dispatcher.returncode == 0,
        },
        "codex_hook_self_check": None if args.skip_codex_hook_self_check else codex_hook is not None and codex_hook.returncode == 0,
        "codex_hook_self_check_skipped": args.skip_codex_hook_self_check,
        "codex_hook_self_check_skip_reason": (
            "Skipped only because enforcement-matrix runs the Codex Stop advisory self-check as a separate required probe."
            if args.skip_codex_hook_self_check else None
        ),
        "codex_hook_self_check_attempts": len(codex_hook_attempts),
        "codex_hook_self_check_stdout_tail": ((codex_hook.stdout or "")[-1200:] if codex_hook is not None else ""),
        "codex_hook_self_check_stderr_tail": ((codex_hook.stderr or "")[-1200:] if codex_hook is not None else ""),
        "unsupported_events": AUDITED_UNSUPPORTED_EVENTS,
        "retired_events": {},
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_HOST_HOOK_AUDIT_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

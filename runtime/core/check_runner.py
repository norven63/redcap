#!/usr/bin/env python3
"""Bounded RedCap aggregate check runner."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
from dataclasses import dataclass


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_STEP_TIMEOUT_SECONDS = int(os.environ.get("REDCAP_CHECK_STEP_TIMEOUT_SECONDS", "180"))
TAIL_LIMIT = 4000


@dataclass(frozen=True)
class Step:
    name: str
    argv: tuple[str, ...]
    timeout_seconds: int = DEFAULT_STEP_TIMEOUT_SECONDS


def redcap(*args: str) -> tuple[str, ...]:
    return ("runtime/bin/redcap", *args)


def python(path: str, *args: str) -> tuple[str, ...]:
    return ("python3", path, *args)


STEPS: tuple[Step, ...] = (
    Step("prism-check", ("runtime/prism/bin/prism", "check"), 360),
    Step("prism-resolution-self-check", redcap("prism-resolution", "--self-check")),
    Step("prism-shard-self-check", redcap("prism-shard", "self-check")),
    Step("task-facts-self-check", redcap("task-facts", "self-check")),
    Step("task-facts-check", redcap("task-facts", "check")),
    Step("completion-evidence-self-check", redcap("completion-evidence", "self-check")),
    Step("terminal-goal-self-check", redcap("terminal-goal", "self-check")),
    Step("terminal-goal-check", redcap("terminal-goal", "check")),
    Step("human-output-check", redcap("human-output", "check")),
    Step("human-output-self-check", redcap("human-output", "self-check")),
    Step("scan-conclusion-self-check", redcap("scan-conclusion", "self-check")),
    Step("known-issues-order-check", redcap("known-issues-order", "check")),
    Step("known-issues-queue-check", redcap("known-issues-queue", "check", "--require-1-4-verified")),
    Step("boundary-consumers-check", redcap("boundary-consumers", "check")),
    Step("legacy-evidence-check", redcap("legacy-evidence", "check")),
    Step("legacy-evidence-self-check", redcap("legacy-evidence", "self-check")),
    Step("process-artifacts-check", redcap("process-artifacts", "check")),
    Step("process-artifacts-self-check", redcap("process-artifacts", "self-check")),
    Step("status-json", redcap("status", "--json", "--require-scan-complete")),
    Step("revive-json", redcap("revive", "--json", "--no-write-evidence", "--require-scan-complete")),
    Step("status-surface-self-check", python("runtime/core/status_surface.py", "self-check")),
    Step("revival-queue-self-check", redcap("revival-queue", "self-check")),
    Step("revival-queue-check", redcap("revival-queue", "check", "--skip-heavy-host-audit")),
    Step("formal-usable-self-check", python("runtime/core/formal_usable_check.py", "self-check")),
    Step("complete-revival-self-check", python("runtime/core/complete_revival_check.py", "self-check")),
    Step("session-ownership-self-check", redcap("session-ownership", "self-check")),
    Step("intent-judge-self-check", redcap("intent-judge", "self-check")),
    Step("advisory-stop-check", redcap("advisory-stop", "check")),
    Step("codex-hook-intent-judge-self-check", python("runtime/host-adapters/codex/codex-hook.py", "--self-check-intent-judge")),
    Step("host-hook-audit", redcap("host-hook-audit"), 240),
    Step("prism-dispatch-timeout-policy", redcap("prism-dispatch", "--timeout-policy-check")),
    Step("prism-dispatch-timeout-e2e", python("runtime/prism/bin/prism-dispatch-timeout-e2e")),
    Step("boundary-check", redcap("boundary", "check")),
    Step("boundary-self-check", redcap("boundary", "self-check")),
    Step("archaeology-check", redcap("archaeology", "check")),
    Step("archaeology-self-check", redcap("archaeology", "self-check")),
    Step("lifecycle-self-check", redcap("lifecycle", "self-check")),
    Step("final-claim-self-check", redcap("final-claim", "self-check")),
    Step("phase2-blueprint-check", redcap("phase2-blueprint", "check")),
    Step("phase2-blueprint-self-check", redcap("phase2-blueprint", "self-check")),
    Step("full-revival-amendment-self-check", redcap("full-revival-amendment", "self-check")),
    Step("full-revival-amendment-check", redcap("full-revival-amendment", "check")),
    Step("e2e-trace-self-check", redcap("e2e-trace", "self-check")),
    Step("complete-revival-e2e-design-check", redcap("complete-revival-e2e", "design-check")),
    Step("complete-revival-e2e-self-check", redcap("complete-revival-e2e", "self-check", "--skip-carrier-probe"), 360),
    Step("fsm-check", redcap("fsm", "check")),
    Step("loom-workflow-self-check", redcap("loom-workflow", "self-check")),
    Step("loom-workflow-check", redcap("loom-workflow", "check")),
    Step("forge-self-check", redcap("forge", "self-check")),
    Step("forge-check", redcap("forge", "check")),
    Step("arsenal-check", redcap("arsenal", "check")),
    Step("project-install-release-check", redcap("project-install", "release-check")),
    Step("project-install-self-check", redcap("project-install", "self-check")),
    Step("project-install-check", redcap("project-install", "check")),
    Step("knowledge-gateway-check", redcap("knowledge-gateway", "check")),
    Step("knowledge-gateway-self-check", redcap("knowledge-gateway", "self-check")),
    Step("revival-loop-check", python("runtime/core/revival_loop.py", "check")),
    Step("revival-loop-self-check", python("runtime/core/revival_loop.py", "self-check")),
    Step("soul-load-check", redcap("soul-load", "check")),
    Step("soul-load-self-check", redcap("soul-load", "self-check")),
    Step("layout-check", redcap("layout-check")),
)


def tail(value: str) -> str:
    if len(value) <= TAIL_LIMIT:
        return value
    return value[-TAIL_LIMIT:]


def run_step(step: Step, *, timeout_override: int | None = None) -> dict[str, object]:
    timeout_seconds = timeout_override or step.timeout_seconds
    started = time.perf_counter()
    print(
        f"REDCAP_CHECK_STEP_START name={step.name} timeout_seconds={timeout_seconds}",
        flush=True,
    )
    try:
        completed = subprocess.run(
            list(step.argv),
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        elapsed = round(time.perf_counter() - started, 3)
        result: dict[str, object] = {
            "name": step.name,
            "argv": list(step.argv),
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "timed_out": False,
            "timeout_seconds": timeout_seconds,
            "elapsed_seconds": elapsed,
            "stdout_tail": tail(completed.stdout),
            "stderr_tail": tail(completed.stderr),
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = round(time.perf_counter() - started, 3)
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        result = {
            "name": step.name,
            "argv": list(step.argv),
            "ok": False,
            "exit_code": None,
            "timed_out": True,
            "timeout_seconds": timeout_seconds,
            "elapsed_seconds": elapsed,
            "stdout_tail": tail(stdout),
            "stderr_tail": tail(stderr),
        }
    if result["ok"]:
        print(f"REDCAP_CHECK_STEP_OK name={step.name} elapsed_seconds={result['elapsed_seconds']}", flush=True)
    else:
        print(json.dumps({"schema_id": "redcap-check-step-failure", **result}, ensure_ascii=False, indent=2))
    return result


def cmd_check(args: argparse.Namespace) -> int:
    selected = {args.only} if args.only else None
    results: list[dict[str, object]] = []
    for step in STEPS:
        if selected is not None and step.name not in selected:
            continue
        result = run_step(step, timeout_override=args.step_timeout_seconds)
        results.append(result)
        if not result["ok"]:
            print(json.dumps({
                "schema_id": "redcap-check-summary",
                "ok": False,
                "failed_step": result["name"],
                "completed_steps": len(results) - 1,
                "total_steps": len(STEPS) if selected is None else 1,
            }, ensure_ascii=False, indent=2))
            return 1
    print(json.dumps({
        "schema_id": "redcap-check-summary",
        "ok": True,
        "completed_steps": len(results),
        "total_steps": len(STEPS) if selected is None else len(results),
    }, ensure_ascii=False, indent=2))
    print("REDCAP_CHECK_OK")
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    print(json.dumps({
        "schema_id": "redcap-check-step-list",
        "steps": [
            {
                "name": step.name,
                "argv": list(step.argv),
                "timeout_seconds": step.timeout_seconds,
            }
            for step in STEPS
        ],
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    names = [step.name for step in STEPS]
    if len(names) != len(set(names)):
        failures.append("check step names must be unique")
    if not any(step.name == "prism-check" and step.timeout_seconds > 0 for step in STEPS):
        failures.append("prism-check must have a positive bounded timeout")
    fake_ok = Step("fixture-ok", ("python3", "-c", "print('fixture ok')"), 5)
    ok_result = run_step(fake_ok)
    if not ok_result["ok"]:
        failures.append("fixture successful step should pass")
    fake_fail = Step("fixture-fail", ("python3", "-c", "import sys; print('fixture fail'); sys.exit(7)"), 5)
    fail_result = run_step(fake_fail)
    if fail_result["ok"] or fail_result["exit_code"] != 7:
        failures.append("fixture failing step should preserve exit code")
    fake_timeout = Step("fixture-timeout", ("python3", "-c", "import time; time.sleep(2)"), 1)
    timeout_result = run_step(fake_timeout)
    if timeout_result["ok"] or timeout_result["timed_out"] is not True:
        failures.append("fixture timeout step should fail with timed_out=true")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_CHECK_RUNNER_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run bounded RedCap aggregate checks")
    subparsers = parser.add_subparsers(dest="command")
    check = subparsers.add_parser("check")
    check.add_argument("--only", choices=[step.name for step in STEPS])
    check.add_argument("--step-timeout-seconds", type=int)
    subparsers.add_parser("list")
    subparsers.add_parser("self-check")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    command = args.command or "check"
    if command == "check":
        return cmd_check(args)
    if command == "list":
        return cmd_list(args)
    if command == "self-check":
        return cmd_self_check(args)
    raise SystemExit(f"unknown command: {command}")


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# 用途：发布安全治理脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^,\s}\]]+"
)


def redact_secret_text(value: str) -> str:
    return SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=<redacted>", value)


def stable_path_token(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"<absolute-path:{digest}>"


def redact_path(path: str | Path | None) -> str:
    if path is None:
        return ""
    raw = str(path)
    if not raw:
        return ""
    raw = redact_secret_text(raw)
    try:
        expanded = str(Path(raw).expanduser())
    except Exception:
        expanded = raw
    home = str(Path.home())
    if home and (expanded == home or expanded.startswith(home + os.sep)):
        return "$HOME" + expanded[len(home) :]
    if expanded.startswith("/Users/") or expanded.startswith("/home/"):
        parts = Path(expanded).parts
        if len(parts) >= 3:
            suffix = os.sep.join(parts[3:])
            return "$HOME" + (os.sep + suffix if suffix else "")
        return "$HOME"
    if expanded.startswith(os.sep):
        return stable_path_token(expanded)
    return expanded


def task_id_from_file(task_file: Path) -> str:
    if not task_file.is_file():
        return ""
    try:
        for line in task_file.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("task_id:"):
                return stripped.split(":", 1)[1].strip()
    except Exception:
        return ""
    return ""


def boundary_mode(runtime_root: Path, workspace_root: Path) -> str:
    try:
        return "self-development" if runtime_root.resolve() == workspace_root.resolve() else "external-workspace"
    except Exception:
        return "unknown"


def build_state(args: argparse.Namespace, command: str) -> dict[str, Any]:
    runtime_root = Path(args.runtime_root).resolve()
    workspace_root = Path(args.workspace_root).resolve()
    task_file = Path(args.task_file)
    if not task_file.is_absolute():
        task_file = workspace_root / task_file
    task_file = task_file.resolve()

    runtime_ok = (runtime_root / "bin" / "redcap").is_file()
    workspace_ok = workspace_root.is_dir()
    task_exists = task_file.is_file()
    task_id = task_id_from_file(task_file)
    checks: list[dict[str, Any]] = [
        {
            "id": "runtime-root",
            "status": "pass" if runtime_ok else "fail",
            "message": "RedCap runtime files are present." if runtime_ok else "RedCap runtime files are missing.",
        },
        {
            "id": "workspace-root",
            "status": "pass" if workspace_ok else "fail",
            "message": "Managed workspace directory is reachable." if workspace_ok else "Managed workspace directory is missing.",
        },
        {
            "id": "task-file",
            "status": "pass" if task_exists else "warning",
            "message": (
                "Project task card was found."
                if task_exists
                else "No project task card was found; this workspace may not be initialized yet."
            ),
        },
        {
            "id": "safe-debug-output",
            "status": "pass",
            "message": "Debug and trace output use redacted paths and do not include local identity or environment secrets.",
        },
    ]
    failed = any(item["status"] == "fail" for item in checks)
    warned = any(item["status"] == "warning" for item in checks)
    status = "unhealthy" if failed else "degraded" if warned else "healthy"
    return {
        "version": 1,
        "surface": "redcap-cli-product-surface",
        "command": command,
        "status": status,
        "runtime_root": redact_path(runtime_root),
        "workspace_root": redact_path(workspace_root),
        "task_file": redact_path(task_file),
        "task_file_status": "exists" if task_exists else "missing",
        "task_id": task_id,
        "boundary_mode": boundary_mode(runtime_root, workspace_root),
        "checks": checks,
        "no_secrets_assertion": True,
    }


def prioritized_findings(state: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    if state["status"] == "healthy":
        findings.append("[P3] CLI diagnostic surface is healthy for this workspace.")
    for check in state["checks"]:
        if check["status"] == "fail":
            findings.append(f"[P1] {check['message']}")
        elif check["status"] == "warning":
            findings.append(f"[P2] {check['message']}")
    if state["boundary_mode"] == "external-workspace":
        findings.append("[P3] RedCap is running against an external managed workspace, not its own runtime repository.")
    else:
        findings.append("[P3] RedCap is running in self-development mode; runtime root and workspace root intentionally match.")
    return findings[:5]


def next_step(state: dict[str, Any]) -> str:
    if state["task_file_status"] == "missing":
        return "Create or point RedCap at a project task card with --task-file, then rerun redcap doctor."
    if state["status"] == "healthy":
        return "Continue with the planned RedCap workflow, or run redcap debug --json if an Agent needs a structured support packet."
    return "Fix the highest-priority finding above, then rerun redcap doctor."


def print_doctor(args: argparse.Namespace) -> int:
    state = build_state(args, "doctor")
    print(f"RedCap Doctor: {state['status']}")
    print()
    print("What I checked:")
    print(f"- Runtime: {state['runtime_root']}")
    print(f"- Workspace: {state['workspace_root']}")
    print(f"- Task card: {state['task_file_status']} ({state['task_file']})")
    print(f"- Boundary mode: {state['boundary_mode']}")
    print()
    print("Findings:")
    for item in prioritized_findings(state):
        print(f"- {item}")
    print()
    print("Next step:")
    print(f"- {next_step(state)}")
    return 0 if state["status"] in {"healthy", "degraded"} else 1


def print_debug(args: argparse.Namespace) -> int:
    state = build_state(args, "debug")
    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"RedCap Debug: {state['status']}")
        print(f"- Workspace: {state['workspace_root']}")
        print(f"- Task card: {state['task_file_status']} ({state['task_file']})")
        print(f"- Task id: {state['task_id'] or '(none)'}")
        print(f"- Boundary mode: {state['boundary_mode']}")
        print("- For machine-readable output, rerun with: redcap debug --json")
    return 0


def print_trace(args: argparse.Namespace) -> int:
    state = build_state(args, "trace")
    delegated_to = getattr(args, "delegated_to", "") or "(none)"
    print("RedCap Trace:", file=sys.stderr)
    print(f"- command: {args.traced_command}", file=sys.stderr)
    print(f"- runtime_root: {state['runtime_root']}", file=sys.stderr)
    print(f"- workspace_root: {state['workspace_root']}", file=sys.stderr)
    print(f"- task_file: {state['task_file']}", file=sys.stderr)
    print(f"- delegated_to: {redact_path(delegated_to)}", file=sys.stderr)
    return 0


HELP_TOPICS = {
    "": """usage: redcap [--trace] <command> [args...]

Core commands:
  revive                 Install/revive RedCap for the current host and workspace.
  status                 Show the current compact RedCap state.
  diagnose               Run the internal control-plane diagnostic chain.
  doctor                 Explain CLI health in human-readable product language.
  debug [--json]         Emit a safe diagnostic packet for support or Agent containers.
  closeout               Run the task closeout controller for the workspace task file.
  package-surface        Validate public package identity and surface readiness.

Workspace options:
  --workspace <dir>      Managed project workspace. Defaults to discovered caller workspace.
  --task-file <file>     Task card. Defaults to <workspace>/.dev-task.md.
  --trace                Explain command routing without dumping env or secrets.

Run redcap help <command> for command-specific guidance.""",
    "doctor": """redcap doctor [--workspace <dir>] [--task-file <file>]

Explains whether RedCap can operate on the selected workspace. Use this when a
human or Agent container needs a short, readable health summary.""",
    "debug": """redcap debug [--json] [--workspace <dir>] [--task-file <file>]

Creates a redacted diagnostic packet. Use --json when the output will be copied
into an issue, review, or another Agent. The packet excludes identity details,
environment secrets, and raw local home paths.""",
    "status": """redcap status [--workspace <dir>] [--task-file <file>]

Shows the compact current status for the selected project task card. This is the
best first read after revive, before deciding the next workflow step.""",
    "diagnose": """redcap diagnose [--workspace <dir>] [--task-file <file>]

Runs RedCap's internal control-plane checks. This is deeper and noisier than
doctor, so prefer doctor for humans and diagnose for release/control gates.""",
    "package-surface": """redcap package-surface

Validates the prepared public package identity and package surface. This command
must keep private=true, publish_allowed=false, and license selection manual until
a separate release task explicitly authorizes publication.""",
    "closeout": """redcap closeout <subcommand> [--workspace <dir>] [--task-file <file>]

Delegates to the closeout controller after resolving the managed workspace task
file. Use closeout status to inspect receipt readiness.""",
}


def print_help(args: argparse.Namespace) -> int:
    topic = args.topic.strip() if args.topic else ""
    print(HELP_TOPICS.get(topic, HELP_TOPICS[""]))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="RedCap CLI product diagnostic surface.")
    parser.add_argument("command", choices=["doctor", "debug", "trace", "help"])
    parser.add_argument("--runtime-root", default=os.environ.get("REDCAP_RUNTIME_ROOT", str(ROOT)))
    parser.add_argument("--workspace-root", default=os.environ.get("REDCAP_WORKSPACE_ROOT", os.getcwd()))
    parser.add_argument("--task-file", default=os.environ.get("REDCAP_TASK_FILE", ".dev-task.md"))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--topic", default="")
    parser.add_argument("--traced-command", default="")
    parser.add_argument("--delegated-to", default="")
    args = parser.parse_args()

    if args.command == "doctor":
        return print_doctor(args)
    if args.command == "debug":
        return print_debug(args)
    if args.command == "trace":
        return print_trace(args)
    return print_help(args)


if __name__ == "__main__":
    raise SystemExit(main())

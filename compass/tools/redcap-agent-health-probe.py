#!/usr/bin/env python3
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
    },
    "codex": {
        "binary": "codex",
        "command": ["codex", "exec", "respond only: ok"],
        "live_supported": False,
        "reason": "Codex CLI live probe can create nested agent sessions; keep it opt-in until a stable non-interactive health contract is defined.",
    },
}


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


def probe_agent(root: Path, name: str, live: bool, timeout_s: int) -> dict[str, object]:
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
    if not bool(spec.get("live_supported", False)):
        row.update({"live_status": "unsupported", "reason": spec.get("reason", "live probe unsupported")})
        return row

    env = os.environ.copy()
    load_dotenv(root, env)
    command = [str(part) for part in spec["command"]]
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        row.update({"live_status": "timeout", "timeout_s": timeout_s})
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
    args = parser.parse_args()

    root = Path(args.root).resolve()
    names = args.agent or sorted(AGENTS)
    payload = {
        "version": 1,
        "detected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "live": bool(args.live),
        "timeout_s": args.timeout,
        "agents": [probe_agent(root, name, bool(args.live), int(args.timeout)) for name in names],
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

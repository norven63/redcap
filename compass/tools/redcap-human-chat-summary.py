#!/usr/bin/env python3
# 用途：生成聊天汇报用的人类可读任务摘要；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#runtime-and-closeout

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROGRESS = ROOT / "compass/tools/redcap-progress-meter.sh"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-human-chat-summary] {message}")


def run_progress(task_file: Path) -> dict[str, Any]:
    if not PROGRESS.is_file():
        fail("missing progress meter renderer")
    completed = subprocess.run(
        ["bash", str(PROGRESS), "--task-file", str(task_file), "--json"],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        fail("progress meter failed: " + completed.stdout[:1200])
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        fail(f"progress meter returned invalid JSON: {exc}")
    if not isinstance(payload, dict):
        fail("progress meter payload must be an object")
    return payload


def text(value: Any, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def compact(value: str) -> str:
    return " ".join(value.replace("\n", " ").split())


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a human-readable RedCap chat summary.")
    parser.add_argument("--task-file", default=str(ROOT / ".dev-task.md"))
    args = parser.parse_args()

    task_file = Path(args.task_file)
    if not task_file.is_absolute():
        task_file = ROOT / task_file
    payload = run_progress(task_file)
    human = payload.get("human") if isinstance(payload.get("human"), dict) else {}

    done = compact(text(human.get("当前已完成"), "当前任务已有进展，但还没有形成可读报告摘要。"))
    panorama = compact(text(human.get("整体任务全景图"), "当前任务正在 RedCap 主线中推进。"))
    effect = compact(text(human.get("带来的效果"), text(human.get("当前位置"), "效果尚未形成摘要。")))
    next_step = compact(text(human.get("下一步计划做的是"), "继续推进当前任务。"))
    intervention = compact(text(human.get("需要人工介入"), "不需要。"))

    print("这次完成了什么")
    print(f"- {done}")
    print()
    print("带来的效果")
    print(f"- {effect}")
    print()
    print("当前任务全景")
    print(f"- {panorama}")
    print()
    print("接下来做什么")
    print(f"- {next_step}")
    print()
    print("需要你做什么")
    print(f"- {intervention}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

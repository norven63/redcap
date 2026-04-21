#!/usr/bin/env bash
# Surface the health of RedCap tracking assets: .dev-task, task report, and explore-notes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$SCRIPT_DIR/redcap-dev-task.sh"

TASK_FILE=$(redcap_dev_task_resolve_file "${1:-}")

python3 - "$REDCAP_ROOT" "$TASK_FILE" <<'PY'
from __future__ import annotations

import pathlib
import re
import sys

repo = pathlib.Path(sys.argv[1])
task_file = pathlib.Path(sys.argv[2])
explore_notes = repo / "compass/knowledge/explore-notes.md"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-tracking-health] {message}")


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def metadata(text: str) -> dict[str, str]:
    capture = False
    result: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("## "):
            if capture:
                break
            if line.startswith("## 控制面元数据") or line.startswith("## Canonical Metadata"):
                capture = True
                continue
        if not capture:
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def count_explore_entries(text: str) -> tuple[int, int]:
    active = 0
    archived = 0
    in_entry = False
    archived_current = False
    for line in text.splitlines():
        if line.startswith("### "):
            if in_entry:
                if archived_current:
                    archived += 1
                else:
                    active += 1
            in_entry = True
            archived_current = False
            continue
        if in_entry and "[ARCHIVED]" in line:
            archived_current = True
    if in_entry:
        if archived_current:
            archived += 1
        else:
            active += 1
    return active, archived


print("REDCAP_TRACKING_HEALTH")

if not explore_notes.is_file():
    fail("missing compass/knowledge/explore-notes.md")

active_entries, archived_entries = count_explore_entries(read(explore_notes))

if task_file.is_file():
    text = read(task_file)
    meta = metadata(text)
    missing = [key for key in ("task_id", "active_slice", "task_report") if not meta.get(key)]
    if missing:
        fail(f"{task_file} missing required metadata: {', '.join(missing)}")

    if "## 原始输入" not in text:
        fail(f"{task_file} missing 原始输入 section")

    report_path = pathlib.Path(meta["task_report"])
    if not report_path.is_absolute():
        report_path = repo / report_path
    if not report_path.is_file():
        fail(f"task report missing: {report_path}")

    print(f"task_anchor=present task_id={meta['task_id']} active_slice={meta['active_slice']}")
    print(f"task_report=present path={report_path.relative_to(repo).as_posix()}")
    print("original_input=present")
else:
    print("task_anchor=absent")
    print("task_report=unbound")
    print("original_input=absent")

print(f"explore_notes=active:{active_entries} archived:{archived_entries}")
if active_entries > 0:
    print("note=存在未归档探讨条目；PM Gate 前应沉淀到 .dev-task.md 或归档 explore-notes")
else:
    print("note=书记官账面已归档或当前无活跃探讨条目")

print("TRACKING_OK")
PY

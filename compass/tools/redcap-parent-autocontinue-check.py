#!/usr/bin/env python3
# 用途：检查父任务线在子任务收口后是否应自动续跑，避免把机械“继续”上抛给用户。
# Dictionary: references/file-lookup-dictionary.md#runtime-and-closeout

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


DONE_STATUSES = {"done", "completed", "closed"}
ACTIVE_NEXT_STATUSES = {"pending", "in_progress"}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-parent-autocontinue-check] {message}")


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def section(text: str, heading_prefix: str) -> str:
    capture = False
    buffer: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            if capture:
                break
            if heading.startswith(heading_prefix):
                capture = True
                continue
        if capture:
            buffer.append(line)
    return "\n".join(buffer).strip()


def metadata(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    meta = section(text, "控制面元数据") or section(text, "Canonical Metadata")
    for line in meta.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$", line)
        if match:
            result[match.group(1)] = match.group(2).strip()
    return result


def load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid backlog json: {path} ({exc})")
    if not isinstance(payload, dict):
        fail(f"backlog must be a JSON object: {path}")
    return payload


def collect_items(backlog: dict) -> dict[str, dict]:
    items: dict[str, dict] = {}
    for group in backlog.get("groups") or []:
        if not isinstance(group, dict):
            continue
        for item in group.get("items") or []:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            if isinstance(item_id, str) and item_id.strip():
                items[item_id.strip()] = item
    return items


def main() -> int:
    if len(sys.argv) != 3:
        fail("usage: redcap-parent-autocontinue-check.py <redcap_root> <task_file>")

    repo = Path(sys.argv[1]).resolve()
    task_file = Path(sys.argv[2])
    if not task_file.is_absolute():
        task_file = (Path.cwd() / task_file).resolve()
    task_text = read(task_file)
    meta = metadata(task_text)

    backlog_source = meta.get("backlog_source", "")
    backlog_item = meta.get("backlog_item", "")
    if not backlog_source or not backlog_item:
        print("PARENT_AUTOCONTINUE_OK state=no-backlog-bound-task")
        return 0

    backlog_path = Path(backlog_source)
    if not backlog_path.is_absolute():
        backlog_path = repo / backlog_source
    if backlog_path.suffix.lower() != ".json":
        print("PARENT_AUTOCONTINUE_OK state=non-json-backlog")
        return 0

    backlog = load_json(backlog_path)
    items = collect_items(backlog)
    current = items.get(backlog_item)
    if current is None:
        fail(f"task backlog_item not found in backlog: {backlog_item}")

    current_status = str(current.get("status", "unknown")).strip()
    focus = backlog.get("current_focus") or {}
    if not isinstance(focus, dict):
        fail("backlog.current_focus must be an object")
    focus_id = str(focus.get("item_id", "")).strip()
    focus_item = items.get(focus_id)
    if focus_id and focus_item is None:
        print(
            "PARENT_AUTOCONTINUE_FAIL "
            f"state=focus-item-missing completed={backlog_item} focus={focus_id}"
        )
        return 1
    focus_status = str((focus_item or {}).get("status", "unknown")).strip()

    if current_status not in DONE_STATUSES:
        print(
            "PARENT_AUTOCONTINUE_OK "
            f"state=current-task-active current={backlog_item} status={current_status}"
        )
        return 0

    if focus_id and focus_id != backlog_item and focus_status in ACTIVE_NEXT_STATUSES:
        print(
            "PARENT_AUTOCONTINUE_OK "
            f"state=auto-continue-required completed={backlog_item} next={focus_id} next_status={focus_status}"
        )
        return 0

    if focus_id == backlog_item:
        if all(str(item.get("status", "unknown")).strip() in DONE_STATUSES for item in items.values()):
            print(
                "PARENT_AUTOCONTINUE_OK "
                f"state=all-children-closed completed={backlog_item} focus={focus_id} focus_status={focus_status}"
            )
            return 0
        print(
            "PARENT_AUTOCONTINUE_FAIL "
            f"state=current-focus-still-on-completed-child completed={backlog_item} focus_status={focus_status}"
        )
        return 1

    print(
        "PARENT_AUTOCONTINUE_OK "
        f"state=no-active-next-child completed={backlog_item} focus={focus_id or 'none'} focus_status={focus_status}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

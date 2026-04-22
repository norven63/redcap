#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pathlib
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class ExploreEntry:
    title: str
    archived: bool
    entry_date: date | None


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


def parse_entry_date(title: str) -> date | None:
    match = re.match(r"^\[(\d{4}-\d{2}-\d{2})(?:\s+\d{2}:\d{2})?\]", title)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_explore_entries(text: str) -> list[ExploreEntry]:
    entries: list[ExploreEntry] = []
    current_title = ""
    current_archived = False
    in_entry = False
    for line in text.splitlines():
        if line.startswith("### "):
            if in_entry:
                entries.append(
                    ExploreEntry(
                        title=current_title,
                        archived=current_archived,
                        entry_date=parse_entry_date(current_title),
                    )
                )
            current_title = line[4:].strip()
            current_archived = False
            in_entry = True
            continue
        if in_entry and "[ARCHIVED" in line:
            current_archived = True
    if in_entry:
        entries.append(
            ExploreEntry(
                title=current_title,
                archived=current_archived,
                entry_date=parse_entry_date(current_title),
            )
        )
    return entries


def run(repo: pathlib.Path, task_file: pathlib.Path, stale_days: int) -> int:
    explore_notes = repo / "compass/knowledge/explore-notes.md"
    errors: list[str] = []
    lines = ["REDCAP_TRACKING_HEALTH"]

    if not explore_notes.is_file():
        errors.append("missing compass/knowledge/explore-notes.md")
    else:
        entries = parse_explore_entries(read(explore_notes))
        active_entries = [entry for entry in entries if not entry.archived]
        archived_entries = [entry for entry in entries if entry.archived]
        lines.append(f"explore_notes=active:{len(active_entries)} archived:{len(archived_entries)}")
        if active_entries:
            today = date.today()
            stale_active = [
                entry
                for entry in active_entries
                if entry.entry_date and (today - entry.entry_date).days >= stale_days
            ]
            lines.append(
                f"explore_notes_stale_threshold_days={stale_days} stale_active={len(stale_active)}"
            )
            if stale_active:
                preview = ", ".join(entry.title for entry in stale_active[:3])
                errors.append(
                    "stale explore-notes entries need archival or task sink: " + preview
                )
            else:
                lines.append("note=存在活跃探讨条目，但仍在新鲜阈值内")
        else:
            lines.append("note=书记官账面已归档或当前无活跃探讨条目")

    if task_file.is_file():
        text = read(task_file)
        meta = metadata(text)
        missing = [key for key in ("task_id", "active_slice", "task_report") if not meta.get(key)]
        if missing:
            errors.append(f"{task_file} missing required metadata: {', '.join(missing)}")
        else:
            lines.append(f"task_anchor=present task_id={meta['task_id']} active_slice={meta['active_slice']}")
            report_path = pathlib.Path(meta["task_report"])
            if not report_path.is_absolute():
                report_path = repo / report_path
            if not report_path.is_file():
                errors.append(f"task report missing: {report_path}")
            else:
                lines.append(f"task_report=present path={report_path.relative_to(repo).as_posix()}")

        if "## 原始输入" not in text:
            errors.append(f"{task_file} missing 原始输入 section")
        else:
            lines.append("original_input=present")
    else:
        lines.extend(
            [
                "task_anchor=absent",
                "task_report=unbound",
                "original_input=absent",
            ]
        )

    for line in lines:
        print(line)
    if errors:
        for error in errors:
            print(f"[redcap-tracking-health] {error}")
        return 1
    print("TRACKING_OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo")
    parser.add_argument("task_file")
    parser.add_argument("--stale-days", type=int, default=3)
    args = parser.parse_args()
    return run(pathlib.Path(args.repo), pathlib.Path(args.task_file), args.stale_days)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import sys


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-mechanism-vitality-check] {message}")


def read(root: pathlib.Path, rel: str) -> str:
    path = root / rel
    if not path.is_file():
        fail(f"missing file: {rel}")
    return path.read_text(encoding="utf-8", errors="replace")


def require_text(root: pathlib.Path, rel: str, phrases: list[str]) -> None:
    text = read(root, rel)
    for phrase in phrases:
        if phrase not in text:
            fail(f"{rel} missing phrase: {phrase}")


def require_json_ids(root: pathlib.Path, rel: str, ids: list[str]) -> None:
    path = root / rel
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid json {rel}: {exc}")
    seen = {entry.get("id") for entry in payload.get("guarantees", []) if isinstance(entry, dict)}
    missing = [item for item in ids if item not in seen]
    if missing:
        fail(f"{rel} missing guarantee ids: {', '.join(missing)}")


def main() -> int:
    root = pathlib.Path(sys.argv[1])

    require_text(
        root,
        "compass/CONTRIBUTING.md",
        [
            "书记协议",
            "PM Gate",
            "PLANNING",
            "PLANNING_REVIEW",
            "explore-notes.md 作为 PM Gate Phase 1 的原始资料直接消费",
        ],
    )
    require_text(
        root,
        "references/runtime-memory-architecture.md",
        [
            "PLANNING",
            "PLANNING_REVIEW",
            "canonical task ledger",
            "closeout-receipt",
        ],
    )
    require_text(
        root,
        "compass/tools/redcap-tracking-health.py",
        [
            "explore_notes=active",
            "stale explore-notes entries need archival or task sink",
        ],
    )
    require_text(
        root,
        "compass/tools/redcap-drift-check.sh",
        [
            "ALLOW_REANCHOR",
            "ls-files --others --exclude-standard",
            "changed files exceed current active_slice scope",
        ],
    )
    require_text(
        root,
        "references/task-report-template.md",
        [
            "新增 Lesson",
            "完成等级",
            "closeout receipt",
        ],
    )
    require_text(
        root,
        "compass/tools/redcap-task-report-check.sh",
        [
            "redcap-human-output-quality-check.sh",
            "human output quality audit failed",
        ],
    )
    require_text(
        root,
        "compass/tools/redcap-human-output-quality-check.py",
        [
            "HUMAN_OUTPUT_QUALITY_OK",
            "formal completion is yes but next-step summary still says closeout/receipt remains to be done",
        ],
    )
    require_text(
        root,
        "compass/docs/research/2026-04-24-redcap-workflow-panorama.md",
        [
            "RedCap 工作流全景图",
            "PLANNING_REVIEW",
            "三表对账",
            "老旧资产治理",
        ],
    )
    require_text(
        root,
        "compass/docs/research/2026-04-24-redcap-workflow-panorama.html",
        [
            "RedCap 工作流全景图",
            "PLANNING_REVIEW",
            "三表对账",
        ],
    )
    require_json_ids(
        root,
        "references/execution-guarantees.json",
        [
            "scribe-runtime-vitality",
            "planning-review-gate",
            "workflow-panorama-surface",
            "task-card-reanchor-scope",
        ],
    )
    print("MECHANISM_VITALITY_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

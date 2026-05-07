#!/usr/bin/env python3
# 用途：知识沉淀与自进化脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import json


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-evolution-harvest-check] {message}")


def read(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def parse_fields(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in text.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$", raw)
        if match:
            result[match.group(1)] = match.group(2).strip()
    return result


def section(text: str, heading: str) -> str:
    capture = False
    level = 0
    buffer: list[str] = []
    for raw in text.splitlines():
        match = re.match(r"^(#+)\s*(.*?)\s*$", raw)
        if match:
            current_level = len(match.group(1))
            current_heading = match.group(2).strip()
            if capture and current_level <= level:
                break
            if current_heading == heading:
                capture = True
                level = current_level
                continue
        if capture:
            buffer.append(raw)
    return "\n".join(buffer).strip()


def run_strict_candidates(root: pathlib.Path) -> None:
    script = root / "compass/tools/redcap-evolution-candidate-check.sh"
    if not script.is_file():
        fail(f"missing candidate checker: {script}")
    completed = subprocess.run(
        ["bash", str(script), "--strict"],
        cwd=str(root),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stdout + completed.stderr).strip()
        fail("strict candidate check failed: " + detail)


def known_candidate_ids(root: pathlib.Path) -> set[str]:
    pool_path = root / "compass/evolution/candidates.json"
    try:
        pool = json.loads(pool_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"unable to read candidate pool: {exc}")
    candidates = pool.get("candidates")
    if not isinstance(candidates, list):
        fail("candidate pool candidates must be a list")
    ids: set[str] = set()
    for candidate in candidates:
        if isinstance(candidate, dict) and isinstance(candidate.get("id"), str):
            ids.add(candidate["id"])
    return ids


def main() -> None:
    if len(sys.argv) != 3:
        fail("usage: redcap-evolution-harvest-check.py <redcap_root> <task_file>")

    root = pathlib.Path(sys.argv[1]).resolve()
    task_file_arg = pathlib.Path(sys.argv[2])
    task_file = task_file_arg if task_file_arg.is_absolute() else root / task_file_arg
    task_text = read(task_file)
    if not task_text:
        fail(f"task file missing or unreadable: {task_file}")
    meta = parse_fields(task_text)
    governance = meta.get("governance_tranche", "").lower() == "true"
    if not governance:
        print("EVOLUTION_HARVEST")
        print("status=skipped reason=not-governance-tranche")
        print("EVOLUTION_HARVEST_OK")
        return

    report_rel = meta.get("task_report", "")
    if not report_rel:
        fail("governance tranche must declare task_report")
    report_path = pathlib.Path(report_rel)
    if not report_path.is_absolute():
        report_path = root / report_path
        if not report_path.exists():
            report_path = task_file.parent / report_rel
    report_text = read(report_path)
    if not report_text:
        fail(f"governance task report missing or unreadable: {report_rel}")

    body = section(report_text, "7.3 Evolution Factory 候选处理")
    if not body:
        fail("governance task report missing section: 7.3 Evolution Factory 候选处理")
    referenced_ids = set(re.findall(r"\bEVO-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{3}\b", body))
    if not referenced_ids and not re.search(r"无新增候选|no-promote", body):
        fail("Evolution candidate handling must reference candidate ids, no-promote, or 无新增候选")
    missing_ids = sorted(referenced_ids - known_candidate_ids(root))
    if missing_ids:
        fail("Evolution candidate handling references unknown candidate ids: " + ", ".join(missing_ids))

    run_strict_candidates(root)

    print("EVOLUTION_HARVEST")
    print(f"task_report={report_rel}")
    print("strict_candidates=pass")
    print("EVOLUTION_HARVEST_OK")


if __name__ == "__main__":
    main()

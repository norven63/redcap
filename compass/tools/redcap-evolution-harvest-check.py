#!/usr/bin/env python3
# 用途：知识沉淀与自进化脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import json
from typing import Any


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


def load_signal_policy(root: pathlib.Path) -> dict[str, Any]:
    policy_path = root / "references/evolution-harvest-signal-policy.json"
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"unable to read evolution harvest signal policy: {exc}")
    if not isinstance(policy, dict):
        fail("evolution harvest signal policy must be an object")
    if policy.get("version") != 1:
        fail("evolution harvest signal policy version must be 1")
    if policy.get("policy_id") != "redcap-evolution-harvest-signal-policy":
        fail("evolution harvest signal policy id mismatch")
    for key in ["always_require_task_flags", "task_field_keywords", "signal_groups", "required_report_section"]:
        if key not in policy:
            fail(f"evolution harvest signal policy missing {key}")
    if not isinstance(policy["always_require_task_flags"], list) or not policy["always_require_task_flags"]:
        fail("evolution harvest signal policy always_require_task_flags must be non-empty")
    if not isinstance(policy["task_field_keywords"], dict):
        fail("evolution harvest signal policy task_field_keywords must be an object")
    if not isinstance(policy["signal_groups"], list) or not policy["signal_groups"]:
        fail("evolution harvest signal policy signal_groups must be non-empty")
    return policy


def truthy(value: str) -> bool:
    return value.strip().lower() in {"true", "yes", "1", "y"}


def lower_blob(*parts: str) -> str:
    return "\n".join(part for part in parts if part).lower()


def term_matches(text: str, term: str) -> bool:
    needle = term.lower()
    if re.fullmatch(r"[a-z0-9_-]+", needle):
        return re.search(rf"(?<![a-z0-9_-]){re.escape(needle)}(?![a-z0-9_-])", text) is not None
    return needle in text


def matched_harvest_reasons(meta: dict[str, str], task_text: str, report_text: str, policy: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for flag in policy["always_require_task_flags"]:
        if isinstance(flag, str) and truthy(meta.get(flag, "")):
            reasons.append(f"task-flag:{flag}")

    for field, terms in policy["task_field_keywords"].items():
        if not isinstance(field, str) or not isinstance(terms, list):
            fail("evolution harvest signal policy task_field_keywords entries must be string -> list")
        field_value = meta.get(field, "").lower()
        for term in terms:
            if isinstance(term, str) and term_matches(field_value, term):
                reasons.append(f"task-field:{field}:{term}")

    combined = lower_blob(task_text, report_text)
    for group in policy["signal_groups"]:
        if not isinstance(group, dict):
            fail("evolution harvest signal policy signal_groups entries must be objects")
        group_id = group.get("id")
        terms = group.get("terms")
        if not isinstance(group_id, str) or not isinstance(terms, list) or not terms:
            fail("evolution harvest signal policy signal group must have id and terms")
        for term in terms:
            if isinstance(term, str) and term_matches(combined, term):
                reasons.append(f"signal:{group_id}:{term}")
                break
    return sorted(set(reasons))


def validate_deferred_with_owner(body: str) -> None:
    if "deferred-with-owner" not in body:
        return
    if not re.search(r"\bowner\s*[:=]", body, flags=re.IGNORECASE):
        fail("deferred-with-owner outcome must include owner=<owner>")
    if not re.search(r"\b(next\s+trigger|trigger)\s*[:=]", body, flags=re.IGNORECASE):
        fail("deferred-with-owner outcome must include trigger=<next trigger>")


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
    policy = load_signal_policy(root)
    report_rel = meta.get("task_report", "")
    report_text = ""
    if report_rel:
        report_path = pathlib.Path(report_rel)
        if not report_path.is_absolute():
            report_path = root / report_path
            if not report_path.exists():
                report_path = task_file.parent / report_rel
        report_text = read(report_path)
    reasons = matched_harvest_reasons(meta, task_text, report_text, policy)
    if not reasons:
        print("EVOLUTION_HARVEST")
        print("status=skipped reason=no-high-value-signals")
        print("EVOLUTION_HARVEST_OK")
        return
    if not report_rel:
        fail("high-value evolution harvest signals require task_report; reasons=" + ",".join(reasons))
    if not report_text:
        fail(f"high-value evolution harvest task report missing or unreadable: {report_rel}")

    required_section = str(policy["required_report_section"])
    body = section(report_text, required_section)
    if not body:
        fail(f"high-value task report missing section: {required_section}; reasons=" + ",".join(reasons))
    referenced_ids = set(re.findall(r"\bEVO-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{3}\b", body))
    if not referenced_ids and not re.search(r"无新增候选|no-promote|deferred-with-owner", body):
        fail("Evolution candidate handling must reference candidate ids, no-promote, deferred-with-owner, or 无新增候选")
    validate_deferred_with_owner(body)
    missing_ids = sorted(referenced_ids - known_candidate_ids(root))
    if missing_ids:
        fail("Evolution candidate handling references unknown candidate ids: " + ", ".join(missing_ids))

    run_strict_candidates(root)

    print("EVOLUTION_HARVEST")
    print(f"task_report={report_rel}")
    print("required=true")
    print("reasons=" + ",".join(reasons))
    print("strict_candidates=pass")
    print("EVOLUTION_HARVEST_OK")


if __name__ == "__main__":
    main()

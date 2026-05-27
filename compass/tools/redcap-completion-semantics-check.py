#!/usr/bin/env python3
# 用途：校验 RedCap 完成语义，防止把证明、保留、延期或人工决策边界冒充为完成。
# Dictionary: references/file-lookup-dictionary.md#control-plane-assurance
"""Validate that RedCap completion claims cannot be satisfied by defer/proof states."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "references/completion-semantics-policy.json"
DEFAULT_BACKLOG = ROOT / "references/backlogs/redcap-architecture-smell-governance.json"
DEFAULT_CORE = ROOT / "compass/CONTRIBUTING.core.md"
DEFAULT_TASK_FILE = ROOT / ".dev-task.md"


def fail(message: str) -> None:
    print(f"[redcap-completion-semantics-check] {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"{label} missing: {path.relative_to(ROOT) if path.is_absolute() else path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be a JSON object")
    return payload


def require_list(payload: dict[str, Any], key: str, minimum: int = 1) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or len(value) < minimum:
        fail(f"{key} must be a list with at least {minimum} item(s)")
    return value


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
            result[match.group(1)] = match.group(2)
    return result


def text_has_any(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term and term in text]


def validate_policy(policy: dict[str, Any]) -> tuple[list[str], list[str]]:
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "completion-semantics-policy":
        fail("policy_id mismatch")
    if policy.get("status") != "active":
        fail("policy status must be active")
    states = policy.get("completion_states")
    if not isinstance(states, dict):
        fail("completion_states must be an object")
    for required in ["done", "preserve-with-proof", "deferred", "blocked-by-human-destructive-decision"]:
        if required not in states:
            fail(f"completion_states missing {required}")
    for state, payload in states.items():
        if not isinstance(payload, dict):
            fail(f"completion state must be an object: {state}")
        if "meaning" not in payload or "can_count_as_complete" not in payload:
            fail(f"completion state missing meaning/can_count_as_complete: {state}")
    escape_terms = [str(item) for item in require_list(policy, "forbidden_escape_terms", minimum=8)]
    claim_terms = [str(item) for item in require_list(policy, "completion_claim_terms", minimum=4)]
    labels = set(str(item) for item in require_list(policy, "allowed_non_completion_labels", minimum=3))
    if "blocked-awaiting-human-decision" not in labels or "not-complete" not in labels:
        fail("allowed_non_completion_labels must include blocked-awaiting-human-decision and not-complete")
    audits = require_list(policy, "historical_corrective_audits", minimum=1)
    for audit in audits:
        if not isinstance(audit, dict):
            fail("historical_corrective_audits entries must be objects")
        for field in ["task_id", "report_path", "required_marker", "reason"]:
            if not isinstance(audit.get(field), str) or not audit[field].strip():
                fail(f"historical audit missing {field}")
    return escape_terms, claim_terms


def validate_task_file(task_file: Path, escape_terms: list[str]) -> tuple[str, int]:
    if not task_file.is_file():
        return "missing", 0
    text = task_file.read_text(encoding="utf-8", errors="replace")
    task_id = metadata(text).get("task_id", "unknown")
    if task_id.startswith("acceptance-") or "fixture" in task_id:
        return task_id, 0
    completion = section(text, "完成标准")
    if not completion:
        fail(f"{task_file}: missing ## 完成标准")
    bad_lines: list[str] = []
    checked_count = 0
    for raw in completion.splitlines():
        line = raw.strip()
        if not re.match(r"^-\s+\[[xX]\]\s+", line):
            continue
        checked_count += 1
        hits = text_has_any(line, escape_terms)
        has_or_escape = "或" in line and any(term in line for term in ["人工", "延期", "边界", "证明", "另立", "授权"])
        if hits or has_or_escape:
            bad_lines.append(line)
    if bad_lines:
        fail("checked completion standards contain non-completion escape clauses: " + " | ".join(bad_lines[:3]))
    return task_id, checked_count


def validate_historical_audits(policy: dict[str, Any], escape_terms: list[str], claim_terms: list[str]) -> int:
    audits = policy["historical_corrective_audits"]
    checked = 0
    for audit in audits:
        report = ROOT / audit["report_path"]
        if not report.is_file():
            fail(f"historical report missing: {audit['report_path']}")
        text = report.read_text(encoding="utf-8", errors="replace")
        escape_hits = text_has_any(text, escape_terms)
        claim_hits = text_has_any(text, claim_terms)
        marker = audit["required_marker"]
        if escape_hits and claim_hits and marker not in text:
            fail(
                f"{audit['task_id']}: report has completion claim plus escape states but lacks corrective marker "
                f"{marker!r}"
            )
        if marker not in text:
            fail(f"{audit['task_id']}: historical corrective marker missing")
        if "不能作为全部完成证据" not in text:
            fail(f"{audit['task_id']}: report must explicitly say it cannot be used as full-completion evidence")
        checked += 1
    return checked


def validate_backlog(backlog: dict[str, Any], policy: dict[str, Any]) -> str:
    requirements = backlog.get("requirements")
    if not isinstance(requirements, list):
        fail("backlog requirements must be a list")
    rasg026 = next((item for item in requirements if isinstance(item, dict) and item.get("id") == "RASG-026"), None)
    if not isinstance(rasg026, dict):
        fail("RASG-026 must be registered in architecture smell backlog")
    if rasg026.get("status") not in {"in_progress", "done"}:
        fail("RASG-026 status must be in_progress or done")
    evidence = rasg026.get("evidence")
    if not isinstance(evidence, list):
        fail("RASG-026 evidence must be a list")
    for required in policy["enforcement_surfaces"][:4]:
        if required not in evidence:
            fail(f"RASG-026 evidence missing {required}")
    return str(rasg026.get("status"))


def validate_core_contract(core: Path) -> None:
    text = core.read_text(encoding="utf-8", errors="replace")
    for phrase in ["完成语义", "preserve-with-proof", "不能计入完成"]:
        if phrase not in text:
            fail(f"core contract missing completion semantics phrase: {phrase}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap completion semantics.")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--task-file", default=str(DEFAULT_TASK_FILE))
    parser.add_argument("--skip-task-file", action="store_true")
    args = parser.parse_args()

    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = ROOT / policy_path
    task_file = Path(args.task_file)
    if not task_file.is_absolute():
        task_file = ROOT / task_file

    policy = load_json(policy_path, "completion semantics policy")
    escape_terms, claim_terms = validate_policy(policy)
    backlog_status = validate_backlog(load_json(DEFAULT_BACKLOG, "architecture smell backlog"), policy)
    validate_core_contract(DEFAULT_CORE)
    task_id, checked_count = ("skipped", 0)
    if not args.skip_task_file:
        task_id, checked_count = validate_task_file(task_file, escape_terms)
    historical_count = validate_historical_audits(policy, escape_terms, claim_terms)

    print("COMPLETION_SEMANTICS_OK")
    print(f"task_id={task_id} checked_completion_items={checked_count}")
    print(f"historical_corrective_audits={historical_count} rasg026={backlog_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REDCAP_ROOT = Path(__file__).resolve().parent.parent.parent
POLICY_PATH = REDCAP_ROOT / "references/layerb-change-intake-policy.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-change-intake-check] {message}")


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing policy: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid policy json: {exc}")


def section(text: str, heading_prefix: str) -> str:
    capture = False
    buffer: list[str] = []
    for raw in text.splitlines():
        if raw.startswith("## "):
            heading = raw[3:].strip()
            if capture:
                break
            if heading.startswith(heading_prefix):
                capture = True
                continue
        if capture:
            buffer.append(raw)
    return "\n".join(buffer).strip()


def metadata(text: str) -> dict[str, str]:
    meta = section(text, "控制面元数据") or section(text, "Canonical Metadata")
    result: dict[str, str] = {}
    for raw in meta.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$", raw)
        if match:
            result[match.group(1)] = match.group(2).strip()
    return result


def split_md_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def parse_ledger_table(ledger: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    headers: list[str] = []
    for raw in ledger.splitlines():
        cells = split_md_row(raw)
        if not cells:
            continue
        if is_separator(cells):
            continue
        if not headers:
            headers = cells
            continue
        if len(cells) != len(headers):
            fail(f"ledger table row has {len(cells)} cells but header has {len(headers)}: {raw}")
        rows.append(dict(zip(headers, cells)))
    return rows


def bool_required(value: str, field: str, row_id: str) -> None:
    if value != "yes":
        fail(f"{row_id}: {field} must be yes for this disposition")


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("version") != 1:
        fail("policy version must be 1")
    for key in [
        "required_columns",
        "allowed_types",
        "allowed_priorities",
        "allowed_blocking_values",
        "allowed_update_values",
        "allowed_dispositions",
        "allowed_statuses",
        "resolved_statuses",
        "open_statuses",
        "terminal_active_slices",
        "disposition_rules",
        "parent_completion_claim_values",
    ]:
        if key not in policy:
            fail(f"policy missing key: {key}")


def ledger_required(text: str, meta: dict[str, str], ledger: str, policy: dict[str, Any]) -> bool:
    original = section(text, "原始输入")
    if ledger:
        return True
    if re.search(r"^###\s+U\d+\b", original, flags=re.MULTILINE):
        return True
    if meta.get("active_slice", "") in {"change-intake", "replan-review"}:
        return True
    return False


def validate_rows(rows: list[dict[str, str]], meta: dict[str, str], policy: dict[str, Any], mode: str) -> None:
    required_columns = policy["required_columns"]
    allowed_types = set(policy["allowed_types"])
    allowed_priorities = set(policy["allowed_priorities"])
    allowed_blocking = set(policy["allowed_blocking_values"])
    allowed_updates = set(policy["allowed_update_values"])
    allowed_dispositions = set(policy["allowed_dispositions"])
    allowed_statuses = set(policy["allowed_statuses"])
    resolved_statuses = set(policy["resolved_statuses"])
    open_statuses = set(policy["open_statuses"])
    terminal_slices = set(policy["terminal_active_slices"])
    disposition_rules: dict[str, dict[str, Any]] = policy["disposition_rules"]

    if not rows:
        fail("ledger section exists but contains no markdown table rows")

    seen: set[str] = set()
    active_slice = meta.get("active_slice", "")
    terminal_mode = mode == "closeout" or active_slice in terminal_slices

    for row in rows:
        for column in required_columns:
            if column not in row:
                fail(f"ledger table missing required column: {column}")
            if not row[column].strip():
                fail(f"ledger row has empty required column {column}: {row}")

        row_id = row["id"].strip()
        if not re.fullmatch(r"U\d+", row_id):
            fail(f"ledger id must look like U<n>: {row_id}")
        if row_id in seen:
            fail(f"duplicate ledger id: {row_id}")
        seen.add(row_id)

        change_type = row["类型"].strip()
        blocking = row["阻塞当前任务"].strip()
        priority = row["优先级"].strip()
        disposition = row["处理方式"].strip()
        confirmed_update = row["确认需求更新"].strip()
        plan_update = row["计划更新"].strip()
        acceptance_update = row["验收更新"].strip()
        status = row["状态"].strip()
        evidence = row["证据"].strip()

        if change_type not in allowed_types:
            fail(f"{row_id}: unsupported 类型: {change_type}")
        if blocking not in allowed_blocking:
            fail(f"{row_id}: 阻塞当前任务 must be yes/no")
        if priority not in allowed_priorities:
            fail(f"{row_id}: unsupported 优先级: {priority}")
        if disposition not in allowed_dispositions:
            fail(f"{row_id}: unsupported 处理方式: {disposition}")
        if status not in allowed_statuses:
            fail(f"{row_id}: unsupported 状态: {status}")
        for label, value in [
            ("确认需求更新", confirmed_update),
            ("计划更新", plan_update),
            ("验收更新", acceptance_update),
        ]:
            if value not in allowed_updates:
                fail(f"{row_id}: {label} must be one of {sorted(allowed_updates)}")

        if terminal_mode and status in open_statuses:
            fail(f"{row_id}: terminal task cannot have unresolved change-intake status: {status}")

        rule = disposition_rules.get(disposition, {})
        expected_status = rule.get("terminal_status")
        if status in resolved_statuses and expected_status and status != expected_status:
            fail(f"{row_id}: disposition {disposition} must close with status {expected_status}, got {status}")
        if rule.get("requires_confirmed_update"):
            bool_required(confirmed_update, "确认需求更新", row_id)
        if rule.get("requires_plan_update"):
            bool_required(plan_update, "计划更新", row_id)
        if rule.get("requires_acceptance_update"):
            bool_required(acceptance_update, "验收更新", row_id)
        if rule.get("requires_child_evidence"):
            if not re.search(r"(child:|subtask|task_id|子任务)", evidence, flags=re.IGNORECASE):
                fail(f"{row_id}: split-child disposition must cite child task evidence")
        if blocking == "yes" and status == "deferred" and terminal_mode:
            fail(f"{row_id}: blocking inserted requirement cannot be deferred at terminal closeout")


def validate_parent_completion(meta: dict[str, str], policy: dict[str, Any], mode: str) -> None:
    subtask_of = meta.get("subtask_of", "").strip()
    active_slice = meta.get("active_slice", "").strip()
    terminal_slices = set(policy["terminal_active_slices"])
    if not subtask_of or active_slice not in terminal_slices and mode != "closeout":
        return

    claim = meta.get("parent_completion_claim", "").strip()
    allowed_claims = set(policy["parent_completion_claim_values"])
    if not claim:
        fail("subtask terminal closeout must declare parent_completion_claim: child-only|none|parent-complete")
    if claim not in allowed_claims:
        fail(f"unsupported parent_completion_claim: {claim}")
    if claim == "parent-complete":
        fail("parent_completion_claim=parent-complete is not allowed without a dedicated parent receipt gate")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Layer B change-intake ledger and replan gate.")
    parser.add_argument("task_file", nargs="?", default=str(REDCAP_ROOT / ".dev-task.md"))
    parser.add_argument("--mode", choices=["normal", "closeout"], default="normal")
    args = parser.parse_args()

    task_file = Path(args.task_file)
    if not task_file.is_absolute():
        task_file = (Path.cwd() / task_file).resolve()
    if not task_file.is_file():
        fail(f"task file missing: {task_file}")

    policy = read_json(POLICY_PATH)
    validate_policy(policy)

    text = task_file.read_text(encoding="utf-8", errors="replace")
    meta = metadata(text)
    ledger = section(text, str(policy.get("ledger_section", "中插需求账本")))
    required = ledger_required(text, meta, ledger, policy)
    if required and not ledger:
        fail("missing section: ## 中插需求账本")

    if ledger:
        rows = parse_ledger_table(ledger)
        validate_rows(rows, meta, policy, args.mode)

    validate_parent_completion(meta, policy, args.mode)
    print("CHANGE_INTAKE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

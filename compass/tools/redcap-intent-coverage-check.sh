#!/usr/bin/env bash
# 用途：控制面保障脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#control-plane-assurance

# Validate that Layer B task cards preserve the user's original intent instead of only proving a narrowed plan.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/redcap-dev-task.sh"

TASK_FILE=$(redcap_dev_task_resolve_file "${1:-}")

python3 - "$TASK_FILE" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path


task_file = Path(sys.argv[1])


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-intent-coverage-check] {message}")


def section(text: str, heading_prefix: str) -> str:
    capture = False
    buffer: list[str] = []
    for raw_line in text.splitlines():
        if raw_line.startswith("## "):
            heading = raw_line[3:].strip()
            if capture:
                break
            if heading.startswith(heading_prefix):
                capture = True
                continue
        if capture:
            buffer.append(raw_line)
    return "\n".join(buffer).strip()


def metadata(text: str) -> dict[str, str]:
    meta = section(text, "控制面元数据") or section(text, "Canonical Metadata")
    result: dict[str, str] = {}
    for line in meta.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


if not task_file.is_file():
    fail(f"missing task file: {task_file}")

text = task_file.read_text(encoding="utf-8", errors="replace")
meta = metadata(text)
task_id = meta.get("task_id", "")

# Acceptance fixtures intentionally keep tiny task cards; the production gate is for real Layer B work.
if task_id.startswith("acceptance-") or "acceptance" in task_id or "fixture" in task_id:
    print(f"INTENT_COVERAGE_SKIPPED fixture task_id={task_id or 'unknown'}")
    raise SystemExit(0)

original = section(text, "原始输入")
confirmed = section(text, "已确认需求")
completion = section(text, "完成标准")
coverage = section(text, "原始意图覆盖审计")

if not original:
    fail("missing section: ## 原始输入")
if not confirmed:
    fail("missing section: ## 已确认需求")
if not completion:
    fail("missing section: ## 完成标准")
if not coverage:
    fail("missing section: ## 原始意图覆盖审计")

status_match = re.search(r"^scope_status:\s*([A-Za-z0-9._-]+)\s*$", coverage, flags=re.MULTILINE)
if not status_match:
    fail("原始意图覆盖审计 missing scope_status")

scope_status = status_match.group(1)
allowed = {"full-implementation", "route-only", "partial-with-explicit-defer", "not-applicable"}
if scope_status not in allowed:
    fail(f"invalid scope_status: {scope_status}")

for phrase in ["原始意图", "已覆盖"]:
    if phrase not in coverage:
        fail(f"原始意图覆盖审计 missing phrase: {phrase}")

if scope_status != "full-implementation":
    if not any(phrase in coverage for phrase in ["未覆盖", "降级", "延期", "不在本轮"]):
        fail("non-full scope_status must explicitly name uncovered/deferred scope")
    if not any(phrase in coverage for phrase in ["后续", "另立", "下轮", "迁移任务"]):
        fail("non-full scope_status must name a follow-up path")

high_risk_keywords = [
    "全部",
    "所有",
    "彻底",
    "完整",
    "目录结构",
    "物理",
    "重构",
    "迁移",
    "独立",
    "CLI",
    "runtime",
    "Runtime",
]
hits = [word for word in high_risk_keywords if word in original]
if hits and not any(word in coverage for word in hits):
    fail("原始输入包含高风险范围词，但覆盖审计未显式回应: " + ",".join(hits))

if scope_status in {"route-only", "partial-with-explicit-defer"} and not any(
    phrase in coverage for phrase in ["不能冒充", "不宣称", "不是已完成", "用户可见边界"]
):
    fail("partial/route-only coverage must include a human-visible boundary statement")

print(f"INTENT_COVERAGE_OK scope_status={scope_status}")
PY

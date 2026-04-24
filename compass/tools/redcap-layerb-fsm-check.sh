#!/usr/bin/env bash
# shellcheck shell=bash
# Validate that Layer B FSM workmode, acceptance gate, and closeout runtime stay wired together.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 - "$REDCAP_ROOT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-layerb-fsm-check] {message}")


def read(rel: str) -> str:
    path = root / rel
    if not path.is_file():
        fail(f"missing file: {rel}")
    return path.read_text(encoding="utf-8", errors="replace")


runtime_arch = read("references/runtime-memory-architecture.md")
current_status = read("compass/tools/redcap-current-status.py")
closeout_runtime = read("compass/tools/redcap-layerb-closeout-runtime.py")
diagnose = read("compass/tools/redcap-diagnose.sh")
contributing = read("compass/CONTRIBUTING.md")
core = read("compass/CONTRIBUTING.core.md")
task_report_template = read("references/task-report-template.md")
guarantees = read("references/execution-guarantees.json")

for required_state in ["REANCHORED", "TASK_LOCKED", "PLANNING", "PLANNING_REVIEW", "EXECUTING", "REVIEW_PENDING", "CLOSEOUT_PENDING", "CLOSED", "BLOCKED"]:
    if required_state not in runtime_arch:
        fail(f"runtime-memory-architecture missing state: {required_state}")

for phrase in [
    "棱镜",
    "receipt",
    "pending closure",
    "closeout runtime",
]:
    if phrase not in runtime_arch:
        fail(f"runtime-memory-architecture missing FSM concept: {phrase}")

for required_file in [
    "compass/tools/redcap-layerb-fsm.sh",
    "compass/tools/redcap-prism-acceptance-check.sh",
    "compass/tools/redcap-prism-acceptance-bind.sh",
    "compass/tools/redcap-layerb-closeout-runtime.sh",
    "closeout-cap.sh",
]:
    if not (root / required_file).is_file():
        fail(f"missing FSM file: {required_file}")

if "layerb_fsm_summary" not in current_status:
    fail("current-status must surface Layer B FSM summary")
if "independent-acceptance:" not in current_status:
    fail("current-status must report independent acceptance status")
if "lifecycle-state:" not in current_status:
    fail("current-status must report lifecycle-state")

if "prism_acceptance(identity)" not in closeout_runtime:
    fail("closeout runtime must consume prism acceptance gate")
if "prism-acceptance,closeout-runtime" not in closeout_runtime:
    fail("closeout runtime must block on missing Prism acceptance")
if "acceptance_status" not in closeout_runtime:
    fail("receipt must carry acceptance status")
if 'redline_mode: str = "merge"' not in closeout_runtime:
    fail("closeout runtime pending writes must preserve existing blockers")

if "redcap-layerb-fsm-check.sh" not in diagnose:
    fail("diagnose must execute redcap-layerb-fsm-check.sh")

for phrase in [
    "棱镜已成为 completed 的默认独立验收前置门",
    "receipt 是唯一正式完工凭证",
    "作者不能单独完成 closeout",
]:
    if phrase not in task_report_template:
        fail(f"task-report template missing completion honesty phrase: {phrase}")

for phrase in [
    "棱镜验收",
    "receipt",
    "不得宣称 completed",
]:
    if phrase not in contributing and phrase not in core:
        fail(f"CONTRIBUTING surfaces missing phrase: {phrase}")

for required_id in [
    '"id": "layerb-closeout-runtime"',
    '"id": "layerb-completion-truth"',
]:
    if required_id not in guarantees:
        fail(f"execution-guarantees missing entry: {required_id}")

layerb_fsm = read("compass/tools/redcap-layerb-fsm.py")
for required_phrase in [
    "PLANNING",
    "PLANNING_REVIEW",
    "planning_slices",
    "planning_review_slices",
]:
    if required_phrase not in layerb_fsm:
        fail(f"layerb fsm state surface missing planning phrase: {required_phrase}")

print("LAYERB_FSM_OK")
PY

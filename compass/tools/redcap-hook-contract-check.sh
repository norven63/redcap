#!/usr/bin/env bash
# 用途：宿主适配与分发脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#skill-and-host-distribution

# Validate that hook/validator/runtime contract hardening has executable coverage.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 - "$REDCAP_ROOT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-hook-contract-check] {message}")


def read(rel: str) -> str:
    path = root / rel
    if not path.is_file():
        fail(f"missing file: {rel}")
    return path.read_text(encoding="utf-8", errors="replace")


hook_standards = read("references/hook-standards.md")
for phrase in [
    "Layer B 变更须独立评审",
    "复活与执行保障不可遗漏",
    "token 风险审计",
    "docs 读取必须渐进披露",
    "Hook 唯一信源不可分叉",
    "Codex Hook 升级必须有 live marker",
]:
    if phrase not in hook_standards:
        fail(f"hook standards missing invariant: {phrase}")

host_readiness = read("compass/tools/redcap-host-hook-readiness.sh")
for phrase in [
    "redcap-codex-live-marker-e2e.sh",
    "codex-live-marker-e2e.json",
    "Codex.app interactive surface remains degraded",
]:
    if phrase not in host_readiness:
        fail(f"host readiness missing hook single-source/live-marker boundary: {phrase}")

codex_live_marker = read("compass/tools/redcap-codex-live-marker-e2e.sh")
for phrase in [
    "codex exec",
    "REDCAP_CODEX_HOOK_E2E_PROBE",
    "Codex.app interactive hook behavior must not be claimed",
]:
    if phrase not in codex_live_marker:
        fail(f"Codex live marker E2E script missing boundary phrase: {phrase}")

validator = read("compass/tools/redcap-validator-chain.sh")
for mode in ["stop-review", "on-complete", "session-end"]:
    if mode not in validator:
        fail(f"validator chain missing mode: {mode}")
for gate in [
    "redcap-pm-gate-check.sh",
    "redcap-drift-check.sh",
    "redcap-spec-check.sh",
    "redcap-task-report-check.sh",
    "redcap-artifact-lifecycle-check.sh",
]:
    if gate not in validator:
        fail(f"validator chain missing gate: {gate}")

stop_review = read("compass/tools/redcap-on-stop-review.sh")
if "references/review-tracks.json" not in stop_review:
    fail("stop-review must consume review tracks")
if "redcap-validator-chain.sh" not in stop_review:
    fail("stop-review must call validator chain before reviewer CLI")

session_end = read("compass/tools/redcap-layerB-session-end.sh")
if "redcap-validator-chain.sh" not in session_end:
    fail("session-end must consume validator chain")
if "redcap_interop_write_pending_closure" not in session_end:
    fail("session-end must persist pending closure fail-closed state")

task_complete = read("compass/tools/redcap-layerB-task-complete-guard.sh")
if "redcap_runtime_attach_current_or_claim" not in task_complete:
    fail("task-complete guard must use shared runtime attach helper")
if "redcap-layerb-closeout-runtime.sh" not in task_complete:
    fail("task-complete guard must call unified closeout runtime")
if "redcap-task-report-register.sh" not in task_complete:
    fail("task-complete guard must still register task reports before closeout")

runtime_state = read("compass/tools/redcap-runtime-state.sh")
for helper in [
    "redcap_runtime_attach_current_or_claim",
    "redcap_runtime_attach_current_or_claim_for_host",
]:
    if helper not in runtime_state:
        fail(f"runtime state missing convergence helper: {helper}")

closeout_runtime = read("compass/tools/redcap-layerb-closeout-runtime.py")
for phrase in [
    "promise-ledger",
    "redcap-prism-acceptance-check.sh",
    "audit-open",
    "redcap-on-complete.sh",
    "redcap-layerB-session-end.sh",
]:
    if phrase not in closeout_runtime:
        fail(f"closeout runtime missing required binding: {phrase}")

current_status = read("compass/tools/redcap-current-status.py")
for phrase in [
    "layerb_fsm_summary",
    "independent-acceptance:",
    "lifecycle-state:",
]:
    if phrase not in current_status:
        fail(f"current-status missing FSM honesty phrase: {phrase}")

print("HOOK_CONTRACT_OK")
PY

#!/usr/bin/env bash
# Validate runtime helper convergence: common attach flow must live in redcap-runtime-state.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 - "$REDCAP_ROOT" <<'PY'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-runtime-helper-check] {message}")


runtime = (root / "compass/tools/redcap-runtime-state.sh").read_text(encoding="utf-8", errors="replace")
for helper in [
    "redcap_runtime_attach_current_or_claim()",
    "redcap_runtime_attach_current_or_claim_for_host()",
]:
    if helper not in runtime:
        fail(f"runtime helper missing: {helper}")

managed_scripts = [
    "compass/tools/redcap-drift-check.sh",
    "compass/tools/redcap-pm-gate-check.sh",
    "compass/tools/redcap-pending-closure-reconcile.sh",
    "compass/tools/redcap-layerB-task-complete-guard.sh",
    "compass/tools/redcap-task-report-check.sh",
]
for rel in managed_scripts:
    text = (root / rel).read_text(encoding="utf-8", errors="replace")
    if "redcap_runtime_attach_current_or_claim" not in text:
        fail(f"{rel} must use shared runtime attach helper")
    if re.search(r"^attach_runtime_if_possible\(\)", text, flags=re.MULTILINE):
        fail(f"{rel} still defines local attach_runtime_if_possible")

print("RUNTIME_HELPER_OK")
PY

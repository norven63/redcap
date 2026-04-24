#!/usr/bin/env bash
# RedCap Layer B diagnostic overview.
# Note: current implementation requires a writable temp directory; read-only sandboxes are degraded/manual-only.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TASK_FILE="${1:-$REDCAP_ROOT/.dev-task.md}"

run_check() {
    local name="$1"
    shift
    local output status

    set +e
    output="$("$@" 2>&1)"
    status=$?
    set -e
    if [[ "$status" -eq 0 ]]; then
        printf '[ok] %s\n' "$name"
    else
        printf '[fail] %s status=%s\n' "$name" "$status"
        printf '%s\n' "$output" | sed -n '1,20p'
    fi
    return "$status"
}

run_closeout_rescue_audit() {
    local runtime_script="$SCRIPT_DIR/redcap-layerb-closeout-runtime.sh"
    local status_output status rescue_candidate

    if [[ ! -x "$runtime_script" ]]; then
        echo "[warn] closeout-rescue-audit skipped (runtime missing)"
        return 0
    fi

    set +e
    status_output="$(bash "$runtime_script" status --task-file "$TASK_FILE" 2>/dev/null)"
    status=$?
    set -e

    if [[ "$status" -ne 0 || -z "$status_output" ]]; then
        echo "[warn] closeout-rescue-audit skipped (runtime status unavailable)"
        return 0
    fi

    rescue_candidate="$(python3 - "$status_output" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
receipt_exists = bool(payload.get("receipt_exists"))
active_slice = payload.get("active_slice", "")
state = payload.get("state") or {}
runtime_status = state.get("status", "")

terminal_slices = {"task-complete", "closeout-complete"}
terminal_states = {"closeout-pending", "completed", "blocked"}

if receipt_exists:
    print("skip:receipt-present")
elif runtime_status in terminal_states or active_slice in terminal_slices:
    print("run")
else:
    print(f"skip:status={runtime_status or 'none'} active_slice={active_slice or 'none'}")
PY
)"

    if [[ "$rescue_candidate" != "run" ]]; then
        echo "[ok] closeout-rescue-audit ${rescue_candidate}"
        return 0
    fi

    run_check \
        "closeout-rescue-audit" \
        bash "$runtime_script" audit-open --task-file "$TASK_FILE" --host "${REDCAP_DIAGNOSE_RESCUE_HOST:-diagnose}" --mode diagnose
}

echo "REDCAP_DIAGNOSE"
echo "cwd=$REDCAP_ROOT"
echo

if [[ -x "$SCRIPT_DIR/redcap-current-status.sh" ]]; then
    bash "$SCRIPT_DIR/redcap-current-status.sh" "$TASK_FILE"
else
    echo "[warn] missing redcap-current-status.sh"
fi

echo
echo "## 诊断门禁"
overall=0
run_closeout_rescue_audit || overall=1
run_check "docs-catalog" bash "$SCRIPT_DIR/redcap-docs-catalog.sh" check || overall=1
run_check "docs-retention" bash "$SCRIPT_DIR/redcap-docs-catalog.sh" retention-check || overall=1
run_check "knowledge-index" bash "$SCRIPT_DIR/redcap-knowledge-index-check.sh" || overall=1
run_check "overlay-governance" bash "$SCRIPT_DIR/redcap-overlay-governance-check.sh" || overall=1
run_check "state-machine-contract" bash "$SCRIPT_DIR/redcap-state-machine-check.sh" || overall=1
run_check "layerb-lifecycle-contract" bash "$SCRIPT_DIR/redcap-layerb-lifecycle-check.sh" || overall=1
run_check "layerb-fsm" bash "$SCRIPT_DIR/redcap-layerb-fsm-check.sh" || overall=1
run_check "layerb-closeout-runtime" bash "$SCRIPT_DIR/redcap-layerb-closeout-runtime-check.sh" "$TASK_FILE" || overall=1
run_check "token-risk-audit" bash "$SCRIPT_DIR/redcap-token-risk-audit.sh" || overall=1
run_check "tracking-health" bash "$SCRIPT_DIR/redcap-tracking-health.sh" "$TASK_FILE" || overall=1
run_check "mechanism-vitality" bash "$SCRIPT_DIR/redcap-mechanism-vitality-check.sh" || overall=1
run_check "contributing-ia" bash "$SCRIPT_DIR/redcap-contributing-ia-check.sh" || overall=1
run_check "review-tracks" bash "$SCRIPT_DIR/redcap-review-tracks-check.sh" || overall=1
run_check "prism-evidence" bash "$REDCAP_ROOT/prism/tools/prism-evidence-check.sh" || overall=1
run_check "prism-runs-lifecycle" bash "$REDCAP_ROOT/prism/tools/prism-runs-lifecycle.sh" check || overall=1
run_check "hook-contract" bash "$SCRIPT_DIR/redcap-hook-contract-check.sh" || overall=1
run_check "runtime-helper" bash "$SCRIPT_DIR/redcap-runtime-helper-check.sh" || overall=1
run_check "cli-console-mirror" bash "$SCRIPT_DIR/redcap-cli-console-mirror-check.sh" || overall=1
run_check "execution-guarantees" bash "$SCRIPT_DIR/redcap-execution-guarantee-check.sh" || overall=1
run_check "revival-protocol" bash "$SCRIPT_DIR/redcap-revival-check.sh" "$REDCAP_ROOT" || overall=1
run_check "spec-check" bash "$SCRIPT_DIR/redcap-spec-check.sh" "$REDCAP_ROOT" || overall=1

if [[ "$overall" -eq 0 ]]; then
    echo "DIAGNOSE_OK"
else
    echo "DIAGNOSE_FAIL"
fi
exit "$overall"

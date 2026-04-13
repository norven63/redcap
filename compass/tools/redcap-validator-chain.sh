#!/usr/bin/env bash
# shellcheck shell=bash
# Unified validator chain for Layer B control-plane checks.

set -uo pipefail

MODE="${1:-stop-review}"
HOST="${2:-}"
TASK_FILE="${3:-}"
BASELINE="${4:-}"
CURRENT_HEAD="${5:-}"
OUTPUT_FORMAT="${6:-yaml}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROJECT_DIR="${REDCAP_VALIDATOR_PROJECT_DIR:-$REDCAP_ROOT}"

STEPS=()
STATUSES=()
DETAILS=()

run_step() {
    local name="$1"
    shift
    local output=""
    if output=$("$@" 2>&1); then
        STEPS+=("$name")
        STATUSES+=("pass")
        DETAILS+=("$output")
        return 0
    fi

    STEPS+=("$name")
    STATUSES+=("fail")
    DETAILS+=("$output")
    return 1
}

emit_yaml() {
    local overall="$1"
    python3 - "$overall" <<'PY'
import os
import sys

overall = sys.argv[1]
steps = os.environ.get("REDCAP_VALIDATOR_STEPS", "").split("\n") if os.environ.get("REDCAP_VALIDATOR_STEPS") else []
statuses = os.environ.get("REDCAP_VALIDATOR_STATUSES", "").split("\n") if os.environ.get("REDCAP_VALIDATOR_STATUSES") else []
details = os.environ.get("REDCAP_VALIDATOR_DETAILS", "\x1e").split("\x1e") if os.environ.get("REDCAP_VALIDATOR_DETAILS") else []

print(f"mode: {os.environ.get('REDCAP_VALIDATOR_MODE', 'unknown')}")
print(f"overall_status: {overall}")
print("steps:")
for name, status, detail in zip(steps, statuses, details):
    print(f"  - name: {name}")
    print(f"    status: {status}")
    if detail.strip():
        print("    detail: |-")
        for line in detail.rstrip().splitlines():
            print(f"      {line}")
PY
}

emit_text() {
    local overall="$1"
    local i
    echo "[redcap-validator-chain] mode=$MODE overall=$overall"
    for ((i = 0; i < ${#STEPS[@]}; i++)); do
        echo "[$((i + 1))] ${STEPS[$i]} :: ${STATUSES[$i]}"
        if [[ -n "${DETAILS[$i]}" ]]; then
            printf '%s\n' "${DETAILS[$i]}"
        fi
    done
}

emit() {
    local overall="$1"
    export REDCAP_VALIDATOR_MODE="$MODE"
    export REDCAP_VALIDATOR_STEPS
    export REDCAP_VALIDATOR_STATUSES
    export REDCAP_VALIDATOR_DETAILS

    REDCAP_VALIDATOR_STEPS=$(printf '%s\n' "${STEPS[@]}")
    REDCAP_VALIDATOR_STATUSES=$(printf '%s\n' "${STATUSES[@]}")
    REDCAP_VALIDATOR_DETAILS=$(printf '%s\x1e' "${DETAILS[@]}")

    case "$OUTPUT_FORMAT" in
        text)
            emit_text "$overall"
            ;;
        yaml|*)
            emit_yaml "$overall"
            ;;
    esac
}

overall_status="pass"

case "$MODE" in
    session-start)
        run_step "pm-gate" bash "$SCRIPT_DIR/redcap-pm-gate-check.sh" session-start "$HOST" "$TASK_FILE" || overall_status="fail"
        ;;
    stop-review)
        run_step "pm-gate" bash "$SCRIPT_DIR/redcap-pm-gate-check.sh" stop-review "$HOST" "$TASK_FILE" || overall_status="fail"
        run_step "drift-check" bash "$SCRIPT_DIR/redcap-drift-check.sh" stop-review "$HOST" "$TASK_FILE" "$BASELINE" "$CURRENT_HEAD" || overall_status="fail"
        run_step "artifact-lifecycle-check" bash "$SCRIPT_DIR/redcap-artifact-lifecycle-check.sh" "$REDCAP_ROOT" "$BASELINE" "$CURRENT_HEAD" redcap-self || overall_status="fail"
        ;;
    obligation-reconcile)
        run_step "review-proof-check" bash "$SCRIPT_DIR/redcap-review-proof-check.sh" "${REDCAP_SESSION_END_REVIEW_REQUIRED:-0}" "${REDCAP_SESSION_END_REVIEW_STATUS:-}" || overall_status="fail"
        run_step "reanchor-check" bash "$SCRIPT_DIR/redcap-closure-reanchor-check.sh" "${REDCAP_SESSION_END_PENDING_HEAD_MISMATCH:-0}" "${REDCAP_SESSION_END_PENDING_AUDITED_HEAD:-}" "$CURRENT_HEAD" || overall_status="fail"
        run_step "pm-gate" bash "$SCRIPT_DIR/redcap-pm-gate-check.sh" strict "$HOST" "$TASK_FILE" || overall_status="fail"
        run_step "drift-check" bash "$SCRIPT_DIR/redcap-drift-check.sh" obligation-reconcile "$HOST" "$TASK_FILE" "$BASELINE" "$CURRENT_HEAD" || overall_status="fail"
        run_step "task-report-check" bash "$SCRIPT_DIR/redcap-task-report-check.sh" "$PROJECT_DIR" "$BASELINE" "$CURRENT_HEAD" "$HOST" || overall_status="fail"
        run_step "artifact-lifecycle-check" bash "$SCRIPT_DIR/redcap-artifact-lifecycle-check.sh" "$PROJECT_DIR" "$BASELINE" "$CURRENT_HEAD" redcap-self || overall_status="fail"
        ;;
    session-end)
        run_step "review-proof-check" bash "$SCRIPT_DIR/redcap-review-proof-check.sh" "${REDCAP_SESSION_END_REVIEW_REQUIRED:-0}" "${REDCAP_SESSION_END_REVIEW_STATUS:-}" || overall_status="fail"
        run_step "reanchor-check" bash "$SCRIPT_DIR/redcap-closure-reanchor-check.sh" "${REDCAP_SESSION_END_PENDING_HEAD_MISMATCH:-0}" "${REDCAP_SESSION_END_PENDING_AUDITED_HEAD:-}" "$CURRENT_HEAD" || overall_status="fail"
        run_step "pm-gate" bash "$SCRIPT_DIR/redcap-pm-gate-check.sh" session-end "$HOST" "$TASK_FILE" || overall_status="fail"
        run_step "drift-check" bash "$SCRIPT_DIR/redcap-drift-check.sh" session-end "$HOST" "$TASK_FILE" "$BASELINE" "$CURRENT_HEAD" || overall_status="fail"
        run_step "task-report-check" bash "$SCRIPT_DIR/redcap-task-report-check.sh" "$PROJECT_DIR" "$BASELINE" "$CURRENT_HEAD" "$HOST" || overall_status="fail"
        run_step "artifact-lifecycle-check" bash "$SCRIPT_DIR/redcap-artifact-lifecycle-check.sh" "$PROJECT_DIR" "$BASELINE" "$CURRENT_HEAD" redcap-self || overall_status="fail"
        ;;
    on-complete)
        run_step "commit-proof-check" bash "$SCRIPT_DIR/redcap-commit-proof-check.sh" "$PROJECT_DIR" "$BASELINE" "$CURRENT_HEAD" || overall_status="fail"
        if [[ "$PROJECT_DIR" == "$REDCAP_ROOT" && -f "$TASK_FILE" ]]; then
            run_step "pm-gate" bash "$SCRIPT_DIR/redcap-pm-gate-check.sh" strict "$HOST" "$TASK_FILE" || overall_status="fail"
            run_step "drift-check" bash "$SCRIPT_DIR/redcap-drift-check.sh" on-complete "$HOST" "$TASK_FILE" "$BASELINE" "$CURRENT_HEAD" || overall_status="fail"
            run_step "task-report-check" bash "$SCRIPT_DIR/redcap-task-report-check.sh" "$PROJECT_DIR" "$BASELINE" "$CURRENT_HEAD" || overall_status="fail"
            run_step "artifact-lifecycle-check" bash "$SCRIPT_DIR/redcap-artifact-lifecycle-check.sh" "$PROJECT_DIR" "$BASELINE" "$CURRENT_HEAD" redcap-self || overall_status="fail"
        fi
        ;;
    *)
        echo "[redcap-validator-chain] unsupported mode: $MODE" >&2
        exit 1
        ;;
esac

emit "$overall_status"

if [[ "$overall_status" != "pass" ]]; then
    exit 1
fi

exit 0

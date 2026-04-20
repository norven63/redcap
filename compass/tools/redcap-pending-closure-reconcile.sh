#!/usr/bin/env bash
# shellcheck shell=bash
# Advisory auto-reconcile for outstanding pending closure obligations.

set -u

HOST="${1:-}"

if [[ -z "$HOST" ]]; then
    echo "[redcap-pending-closure-reconcile] ERROR: host is required" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/redcap-runtime-state.sh"
source "$SCRIPT_DIR/redcap-interop-governance.sh"
source "$SCRIPT_DIR/redcap-validator-output.sh"

VALIDATOR_CHAIN="${REDCAP_VALIDATOR_CHAIN_SCRIPT:-$SCRIPT_DIR/redcap-validator-chain.sh}"
TASK_FILE="$REDCAP_ROOT/.dev-task.md"
CURRENT_HEAD=$(git -C "$REDCAP_ROOT" rev-parse HEAD 2>/dev/null || true)
[[ -n "$CURRENT_HEAD" ]] || exit 0

append_required_redline() {
    local item="$1"
    local normalized=""

    normalized=$(printf '%s' "$item" | tr -d '[:space:]')
    [[ -n "$normalized" ]] || return 0
    case ",$REQUIRED_REDLINES," in
        *,"$normalized",*) return 0 ;;
    esac
    if [[ -z "$REQUIRED_REDLINES" ]]; then
        REQUIRED_REDLINES="$normalized"
    else
        REQUIRED_REDLINES="${REQUIRED_REDLINES},$normalized"
    fi
}

append_unmanaged_redlines() {
    local item=""

    for item in ${OLD_REQUIRED_REDLINES//,/ }; do
        item=$(printf '%s' "$item" | tr -d '[:space:]')
        [[ -n "$item" ]] || continue
        case "$item" in
            review|pending-closure|pm-gate|drift|backlog|spec|task-report|artifact-lifecycle|validator-chain) ;;
            *)
                append_required_redline "$item"
                ;;
        esac
    done
}

record_reconcile_event() {
    local outcome="$1"
    local detail="$2"

    redcap_interop_record_reanchor_event \
        "$REDCAP_ROOT" \
        "pending-closure-reconcile-on-session-start" \
        "host=$HOST outcome=$outcome $detail" \
        >/dev/null 2>&1 || true
}

if ! redcap_runtime_attach_current_or_claim "$HOST"; then
    redcap_runtime_record_degraded_mode \
        "$REDCAP_ROOT" \
        "pending-closure-reconcile-missing-claim" \
        "host=$HOST current_head=$CURRENT_HEAD" \
        >/dev/null 2>&1 || true
    exit 0
fi

PENDING_STATE=$(redcap_interop_pending_closure_existing_file "$REDCAP_ROOT" "$TASK_FILE" 2>/dev/null || true)
if [[ -z "$PENDING_STATE" || ! -f "$PENDING_STATE" ]]; then
    exit 0
fi

CURRENT_TASK_ID=$(redcap_dev_task_extract_kv "$TASK_FILE" "task_id" 2>/dev/null || true)
CURRENT_CONFIRMED_HASH=$(redcap_dev_task_confirmed_hash "$TASK_FILE" 2>/dev/null || true)
PENDING_TASK_ID=$(redcap_interop_read_state_field "$PENDING_STATE" "task_id" 2>/dev/null || true)
PENDING_CONFIRMED_HASH=$(redcap_interop_read_state_field "$PENDING_STATE" "confirmed_hash" 2>/dev/null || true)
OLD_REQUIRED_REDLINES=$(redcap_interop_read_state_field "$PENDING_STATE" "required_redlines" 2>/dev/null || true)
PENDING_BASELINE_HEAD=$(redcap_interop_read_state_field "$PENDING_STATE" "baseline_head" 2>/dev/null || true)
PENDING_AUDITED_HEAD=$(redcap_interop_read_state_field "$PENDING_STATE" "audited_head" 2>/dev/null || true)
PENDING_UPDATED_AT=$(redcap_interop_read_state_field "$PENDING_STATE" "updated_at" 2>/dev/null || true)
PENDING_ARTIFACT_PATH=$(redcap_interop_read_state_field "$PENDING_STATE" "artifact_path" 2>/dev/null || true)
IDENTITY_MISMATCH=0

if [[ -n "$PENDING_TASK_ID" && -n "$CURRENT_TASK_ID" && "$PENDING_TASK_ID" != "$CURRENT_TASK_ID" ]]; then
    record_reconcile_event \
        "identity-mismatch" \
        "pending_task_id=$PENDING_TASK_ID current_task_id=$CURRENT_TASK_ID required_redlines=$OLD_REQUIRED_REDLINES"
    exit 0
fi

if [[ -n "$PENDING_CONFIRMED_HASH" && -n "$CURRENT_CONFIRMED_HASH" && "$PENDING_CONFIRMED_HASH" != "$CURRENT_CONFIRMED_HASH" ]]; then
    IDENTITY_MISMATCH=1
fi

BASELINE="$CURRENT_HEAD"
PENDING_HEAD_MISMATCH=0
if [[ -n "$PENDING_BASELINE_HEAD" ]] && git -C "$REDCAP_ROOT" rev-parse "${PENDING_BASELINE_HEAD}^{commit}" >/dev/null 2>&1; then
    if [[ -z "$PENDING_AUDITED_HEAD" || "$PENDING_AUDITED_HEAD" == "$CURRENT_HEAD" ]] || \
        git -C "$REDCAP_ROOT" merge-base --is-ancestor "$PENDING_AUDITED_HEAD" "$CURRENT_HEAD" >/dev/null 2>&1; then
        BASELINE="$PENDING_BASELINE_HEAD"
    else
        PENDING_HEAD_MISMATCH=1
    fi
fi

REVIEW_REQUIRED=0
case ",$OLD_REQUIRED_REDLINES," in
    *,review,*) REVIEW_REQUIRED=1 ;;
esac

REVIEW_STATUS=""
REVIEW_RESULT_FILE=$(redcap_runtime_path "review/review-result" 2>/dev/null || true)
if [[ -n "$REVIEW_RESULT_FILE" && -f "$REVIEW_RESULT_FILE" ]]; then
    REVIEW_STATUS=$(cat "$REVIEW_RESULT_FILE" 2>/dev/null || true)
fi

VALIDATOR_OUTPUT=""
VALIDATOR_INFRA_FAILURE=0
if [[ ! -x "$VALIDATOR_CHAIN" ]]; then
    VALIDATOR_INFRA_FAILURE=1
    VALIDATOR_OUTPUT="[redcap-validator-chain] obligation-reconcile validator missing"
else
    VALIDATOR_OUTPUT=$(
        REDCAP_VALIDATOR_PROJECT_DIR="$REDCAP_ROOT" \
        REDCAP_RUNTIME_SESSION_ID="${REDCAP_RUNTIME_SESSION_ID:-}" \
        REDCAP_RUNTIME_CAPABILITY="${REDCAP_RUNTIME_CAPABILITY:-}" \
        REDCAP_HOST_PROCESS_PID="${REDCAP_HOST_PROCESS_PID:-$PPID}" \
        REDCAP_SESSION_END_REVIEW_REQUIRED="$REVIEW_REQUIRED" \
        REDCAP_SESSION_END_REVIEW_STATUS="$REVIEW_STATUS" \
        REDCAP_SESSION_END_PENDING_HEAD_MISMATCH="$PENDING_HEAD_MISMATCH" \
        REDCAP_SESSION_END_PENDING_AUDITED_HEAD="${PENDING_AUDITED_HEAD:-}" \
        bash "$VALIDATOR_CHAIN" obligation-reconcile "$HOST" "$TASK_FILE" "$BASELINE" "$CURRENT_HEAD" text 2>&1
    ) || true
    if ! redcap_validator_output_has_recordable_step \
        "$VALIDATOR_OUTPUT" \
        review-proof-check \
        reanchor-check \
        pm-gate \
        drift-check \
        backlog-check \
        spec-check \
        task-report-check \
        artifact-lifecycle-check; then
        VALIDATOR_INFRA_FAILURE=1
    fi
fi

REQUIRED_REDLINES=""
if [[ "$VALIDATOR_INFRA_FAILURE" -eq 1 ]]; then
    REQUIRED_REDLINES="$OLD_REQUIRED_REDLINES"
    append_required_redline "validator-chain"
else
    append_unmanaged_redlines
    if [[ "$REVIEW_REQUIRED" -eq 1 && "$(redcap_validator_step_status "$VALIDATOR_OUTPUT" "review-proof-check")" != "pass" ]]; then
        append_required_redline "review"
    fi
    if [[ "$(redcap_validator_step_status "$VALIDATOR_OUTPUT" "reanchor-check")" != "pass" ]]; then
        append_required_redline "pending-closure"
    fi
    if [[ "$(redcap_validator_step_status "$VALIDATOR_OUTPUT" "pm-gate")" != "pass" ]]; then
        append_required_redline "pm-gate"
    fi
    if [[ "$(redcap_validator_step_status "$VALIDATOR_OUTPUT" "drift-check")" != "pass" ]]; then
        append_required_redline "drift"
    fi
    if [[ "$(redcap_validator_step_status "$VALIDATOR_OUTPUT" "backlog-check")" != "pass" ]]; then
        append_required_redline "backlog"
    fi
    if [[ "$(redcap_validator_step_status "$VALIDATOR_OUTPUT" "spec-check")" != "pass" ]]; then
        append_required_redline "spec"
    fi
    if [[ "$(redcap_validator_step_status "$VALIDATOR_OUTPUT" "task-report-check")" != "pass" ]]; then
        append_required_redline "task-report"
    fi
    if [[ "$(redcap_validator_step_status "$VALIDATOR_OUTPUT" "artifact-lifecycle-check")" != "pass" ]]; then
        append_required_redline "artifact-lifecycle"
    fi
fi

DETAIL="old_required_redlines=$OLD_REQUIRED_REDLINES new_required_redlines=${REQUIRED_REDLINES:-none} validator_infra_failure=$VALIDATOR_INFRA_FAILURE baseline=$BASELINE current_head=$CURRENT_HEAD identity_mismatch=$IDENTITY_MISMATCH"

if [[ -z "$REQUIRED_REDLINES" ]]; then
    if redcap_interop_clear_pending_closure \
        "$REDCAP_ROOT" \
        "$TASK_FILE" \
        "session-start-auto-cleared" \
        "$DETAIL" \
        "$PENDING_UPDATED_AT" \
        >/dev/null 2>&1; then
        record_reconcile_event "cleared" "$DETAIL"
    else
        redcap_runtime_record_degraded_mode \
            "$REDCAP_ROOT" \
            "pending-closure-reconcile-clear-failed" \
            "host=$HOST current_head=$CURRENT_HEAD detail=$DETAIL" \
            >/dev/null 2>&1 || true
        record_reconcile_event "clear-failed" "$DETAIL"
    fi
    exit 0
fi

if [[ "$IDENTITY_MISMATCH" -eq 1 || "$REQUIRED_REDLINES" != "$OLD_REQUIRED_REDLINES" ]]; then
    if redcap_interop_write_pending_closure \
        "$REDCAP_ROOT" \
        "$TASK_FILE" \
        "$HOST" \
        "session-start-auto-reconcile" \
        "$REQUIRED_REDLINES" \
        "$DETAIL" \
        "$PENDING_ARTIFACT_PATH" \
        "$PENDING_BASELINE_HEAD" \
        "$PENDING_AUDITED_HEAD" \
        replace \
        "$PENDING_UPDATED_AT" \
        >/dev/null 2>&1; then
        if [[ "$IDENTITY_MISMATCH" -eq 1 && "$REQUIRED_REDLINES" == "$OLD_REQUIRED_REDLINES" ]]; then
            record_reconcile_event "reanchored" "$DETAIL"
        else
            record_reconcile_event "rewritten" "$DETAIL"
        fi
    else
        redcap_runtime_record_degraded_mode \
            "$REDCAP_ROOT" \
            "pending-closure-reconcile-write-failed" \
            "host=$HOST current_head=$CURRENT_HEAD detail=$DETAIL" \
            >/dev/null 2>&1 || true
        record_reconcile_event "rewrite-failed" "$DETAIL"
    fi
    exit 0
fi

record_reconcile_event "blocked" "$DETAIL"
exit 0

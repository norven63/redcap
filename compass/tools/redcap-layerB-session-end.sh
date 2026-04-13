#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap 框架 — Layer B SessionEnd 统一收尾入口
#
# 负责：
#   1. 非 Claude 宿主补跑独立架构评审
#   2. 检查本次 commit 区间是否产出模板化任务报告
#   3. 发送 Layer B 飞书完成/告警通知
#   4. 维护去重标记，避免重复提醒
# ─────────────────────────────────────────────────────────

set -u

HOST="${1:-}"

if [[ -z "$HOST" ]]; then
    echo "[redcap-layerB-session-end] ERROR: host is required" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/redcap-runtime-state.sh"
source "$SCRIPT_DIR/redcap-interop-governance.sh"
source "$SCRIPT_DIR/redcap-notify-format.sh"
source "$SCRIPT_DIR/redcap-validator-output.sh"

VALIDATOR_CHAIN="$SCRIPT_DIR/redcap-validator-chain.sh"

HOOK_CWD="${REDCAP_HOOK_CWD:-$REDCAP_ROOT}"
HOST_SESSION_ID="${REDCAP_HOST_SESSION_ID:-}"
BINDING_KEY="${REDCAP_SESSION_BINDING_KEY:-}"
HOST_PROCESS_PID="${REDCAP_HOST_PROCESS_PID:-$PPID}"

if [[ -z "$BINDING_KEY" && -n "$HOST_SESSION_ID" ]]; then
    BINDING_KEY=$(redcap_runtime_binding_key_from_host_session "$HOST" "$HOST_SESSION_ID")
fi

HEAD_FILE=""
NOTIFIED_FILE=""
ALERTED_FILE=""
REVIEW_RESULT_FILE=""
REVIEW_LOG_FILE=""
LEGACY_CLAUDE_HEAD_FILE="/tmp/redcap-claude-initial-head"
RUNTIME_ATTACHED=0
USED_LEGACY_CLAUDE_HEAD=0

if [[ -n "$BINDING_KEY" ]] && redcap_runtime_load_from_binding "$HOST" "$HOOK_CWD" "$BINDING_KEY"; then
    HEAD_FILE=$(redcap_runtime_path "layerB/initial-head")
    NOTIFIED_FILE=$(redcap_runtime_path "layerB/notified-head")
    ALERTED_FILE=$(redcap_runtime_path "layerB/alerted-head")
    REVIEW_RESULT_FILE=$(redcap_runtime_path "review/review-result")
    REVIEW_LOG_FILE=$(redcap_runtime_path "review/review-log.md")
    RUNTIME_ATTACHED=1
else
    redcap_runtime_record_degraded_mode "$HOOK_CWD" "layerB-session-end-safe-degraded" "host=$HOST binding_key=${BINDING_KEY:-missing}" || true
fi

CURRENT_HEAD=$(git -C "$REDCAP_ROOT" rev-parse HEAD 2>/dev/null) || exit 0

EXPLORE_NOTES_CHECK="$SCRIPT_DIR/redcap-explore-notes-check.sh"
if [[ -x "$EXPLORE_NOTES_CHECK" ]]; then
    REDCAP_SKIP_FEISHU="${REDCAP_SKIP_FEISHU:-0}" bash "$EXPLORE_NOTES_CHECK" 2>&1 || true
fi

if [[ "$RUNTIME_ATTACHED" != "1" ]]; then
    MISSING_RUNTIME_REDLINES="review,pm-gate,drift,artifact-lifecycle,task-report,notify"
    if redcap_interop_pending_closure_exists "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md"; then
        MISSING_RUNTIME_REDLINES="pending-closure,$MISSING_RUNTIME_REDLINES"
    fi
    redcap_interop_write_pending_closure \
        "$REDCAP_ROOT" \
        "$REDCAP_ROOT/.dev-task.md" \
        "$HOST" \
        "layerB-session-end-missing-runtime-claim" \
        "$MISSING_RUNTIME_REDLINES" \
        "missing-runtime-claim" \
        >/dev/null 2>&1 || true
    redcap_runtime_clear_process_claim "$HOST" "$HOST_PROCESS_PID" || true
    exit 0
fi

BASELINE=""
if [[ -f "$NOTIFIED_FILE" ]]; then
    BASELINE=$(cat "$NOTIFIED_FILE")
elif [[ -f "$HEAD_FILE" ]]; then
    BASELINE=$(cat "$HEAD_FILE")
elif [[ "$HOST" == "claude" && -f "$LEGACY_CLAUDE_HEAD_FILE" ]]; then
    BASELINE=$(cat "$LEGACY_CLAUDE_HEAD_FILE")
    redcap_runtime_record_legacy_hit "$HOOK_CWD" "layerB-session-end-legacy-claude-head" "host=$HOST" || true
    USED_LEGACY_CLAUDE_HEAD=1
fi

PENDING_CLOSURE_STATE=$(redcap_interop_pending_closure_file "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" 2>/dev/null || true)
PENDING_CLOSURE_EXISTS=0
PENDING_REQUIRED_REDLINES=""
PENDING_BASELINE_HEAD=""
PENDING_AUDITED_HEAD=""
PENDING_UPDATED_AT=""
PENDING_REVIEW_REQUIRED=0
PENDING_CLOSURE_HEAD_MISMATCH=0
if [[ -n "$PENDING_CLOSURE_STATE" && -f "$PENDING_CLOSURE_STATE" ]]; then
    PENDING_CLOSURE_EXISTS=1
    PENDING_REQUIRED_REDLINES=$(redcap_interop_read_state_field "$PENDING_CLOSURE_STATE" "required_redlines" 2>/dev/null || true)
    PENDING_BASELINE_HEAD=$(redcap_interop_read_state_field "$PENDING_CLOSURE_STATE" "baseline_head" 2>/dev/null || true)
    PENDING_AUDITED_HEAD=$(redcap_interop_read_state_field "$PENDING_CLOSURE_STATE" "audited_head" 2>/dev/null || true)
    PENDING_UPDATED_AT=$(redcap_interop_read_state_field "$PENDING_CLOSURE_STATE" "updated_at" 2>/dev/null || true)
    case ",$PENDING_REQUIRED_REDLINES," in
        *,review,*) PENDING_REVIEW_REQUIRED=1 ;;
    esac
fi

cleanup_session_files() {
    rm -f "$HEAD_FILE" 2>/dev/null || true
    redcap_runtime_remove_path "layerB/current-report-path" || true
    if [[ "$HOST" == "claude" && "$USED_LEGACY_CLAUDE_HEAD" == "1" && -f "$LEGACY_CLAUDE_HEAD_FILE" ]]; then
        if redcap_runtime_quarantine_legacy_path "$HOOK_CWD" "$LEGACY_CLAUDE_HEAD_FILE" "layerB-session-end-legacy-quarantine" "host=$HOST"; then
            echo "[redcap-layerB-session-end] quarantined legacy Claude head marker: $LEGACY_CLAUDE_HEAD_FILE" >&2
        else
            rm -f "$LEGACY_CLAUDE_HEAD_FILE" 2>/dev/null || true
        fi
    fi
    redcap_runtime_clear_process_claim "$HOST" "$HOST_PROCESS_PID" || true
}

clear_review_artifacts() {
    rm -f "$REVIEW_RESULT_FILE" "$REVIEW_LOG_FILE" 2>/dev/null || true
}

run_session_end_validator_chain() {
    SESSION_END_VALIDATOR_OUTPUT=""

    if [[ ! -x "$VALIDATOR_CHAIN" ]]; then
        SESSION_END_VALIDATOR_OUTPUT="[redcap-validator-chain] mode=session-end overall=fail
[session-end] validator chain 缺失，无法继续统一校验"
        return 1
    fi

    SESSION_END_VALIDATOR_OUTPUT=$(REDCAP_VALIDATOR_PROJECT_DIR="$REDCAP_ROOT" \
        REDCAP_RUNTIME_SESSION_ID="${REDCAP_RUNTIME_SESSION_ID:-}" \
        REDCAP_RUNTIME_CAPABILITY="${REDCAP_RUNTIME_CAPABILITY:-}" \
        REDCAP_HOST_PROCESS_PID="$HOST_PROCESS_PID" \
        REDCAP_SESSION_END_REVIEW_REQUIRED="$REVIEW_REQUIRED" \
        REDCAP_SESSION_END_REVIEW_STATUS="${REVIEW_STATUS:-}" \
        REDCAP_SESSION_END_PENDING_HEAD_MISMATCH="$PENDING_CLOSURE_HEAD_MISMATCH" \
        REDCAP_SESSION_END_PENDING_AUDITED_HEAD="${PENDING_AUDITED_HEAD:-}" \
        bash "$VALIDATOR_CHAIN" session-end "$HOST" "$REDCAP_ROOT/.dev-task.md" "$BASELINE" "$CURRENT_HEAD" text 2>&1) || return 1

    return 0
}

record_session_end_phase() {
    local phase="$1"
    local status="$2"
    local detail="${3:-}"
    local artifact_path="${4:-}"

    redcap_interop_append_closure_ledger \
        "$REDCAP_ROOT" \
        "$REDCAP_ROOT/.dev-task.md" \
        "$phase" \
        "$status" \
        "$detail" \
        "$HOST" \
        "session-end" \
        "$BASELINE" \
        "$CURRENT_HEAD" \
        "$artifact_path" \
        >/dev/null 2>&1
}

record_session_end_validator_steps() {
    local output="$1"
    local artifact_path="${2:-}"
    local persist_status=0
    local status=""

    status=$(redcap_validator_step_status "$output" "review-proof-check")
    case "$status" in
        pass) record_session_end_phase "review" "pass" "validator-chain step passed" "$artifact_path" || persist_status=1 ;;
        fail) record_session_end_phase "review" "fail" "validator-chain step failed" "$artifact_path" || persist_status=1 ;;
    esac

    status=$(redcap_validator_step_status "$output" "reanchor-check")
    case "$status" in
        pass) record_session_end_phase "reanchor" "pass" "validator-chain step passed" "$artifact_path" || persist_status=1 ;;
        fail) record_session_end_phase "reanchor" "fail" "validator-chain step failed" "$artifact_path" || persist_status=1 ;;
    esac

    status=$(redcap_validator_step_status "$output" "pm-gate")
    case "$status" in
        pass) record_session_end_phase "pm-gate" "pass" "validator-chain step passed" "$artifact_path" || persist_status=1 ;;
        fail) record_session_end_phase "pm-gate" "fail" "validator-chain step failed" "$artifact_path" || persist_status=1 ;;
    esac

    status=$(redcap_validator_step_status "$output" "drift-check")
    case "$status" in
        pass) record_session_end_phase "drift" "pass" "validator-chain step passed" "$artifact_path" || persist_status=1 ;;
        fail) record_session_end_phase "drift" "fail" "validator-chain step failed" "$artifact_path" || persist_status=1 ;;
    esac

    status=$(redcap_validator_step_status "$output" "task-report-check")
    case "$status" in
        pass) record_session_end_phase "task-report" "pass" "validator-chain step passed" "$artifact_path" || persist_status=1 ;;
        fail) record_session_end_phase "task-report" "fail" "validator-chain step failed" "$artifact_path" || persist_status=1 ;;
    esac

    status=$(redcap_validator_step_status "$output" "artifact-lifecycle-check")
    case "$status" in
        pass) record_session_end_phase "artifact-lifecycle" "pass" "validator-chain step passed" "$artifact_path" || persist_status=1 ;;
        fail) record_session_end_phase "artifact-lifecycle" "fail" "validator-chain step failed" "$artifact_path" || persist_status=1 ;;
    esac

    return "$persist_status"
}

if [[ -z "$BASELINE" ]]; then
    if [[ "$PENDING_CLOSURE_EXISTS" != "1" ]]; then
        clear_review_artifacts
        cleanup_session_files
        exit 0
    fi
    BASELINE="$CURRENT_HEAD"
fi

if [[ "$PENDING_CLOSURE_EXISTS" == "1" && -n "$PENDING_BASELINE_HEAD" ]]; then
    if git -C "$REDCAP_ROOT" rev-parse "${PENDING_BASELINE_HEAD}^{commit}" >/dev/null 2>&1; then
        if [[ -z "$PENDING_AUDITED_HEAD" || "$PENDING_AUDITED_HEAD" == "$CURRENT_HEAD" ]] || \
           git -C "$REDCAP_ROOT" merge-base --is-ancestor "$PENDING_AUDITED_HEAD" "$CURRENT_HEAD" >/dev/null 2>&1; then
            BASELINE="$PENDING_BASELINE_HEAD"
        else
            PENDING_CLOSURE_HEAD_MISMATCH=1
        fi
    fi
fi

if [[ "$BASELINE" == "$CURRENT_HEAD" && "$PENDING_CLOSURE_EXISTS" != "1" ]]; then
    clear_review_artifacts
    cleanup_session_files
    exit 0
fi

SKIP_REVIEW="${REDCAP_SKIP_INDEPENDENT_REVIEW:-0}"
INITIAL_REVIEW_STATUS=""
if [[ -f "$REVIEW_RESULT_FILE" ]]; then
    INITIAL_REVIEW_STATUS=$(cat "$REVIEW_RESULT_FILE" 2>/dev/null || true)
fi

SHOULD_RUN_REVIEW=0
if [[ "$SKIP_REVIEW" != "1" ]]; then
    if [[ "$HOST" != "claude" && "$BASELINE" != "$CURRENT_HEAD" ]]; then
        SHOULD_RUN_REVIEW=1
    elif [[ "$HOST" == "claude" && "$PENDING_REVIEW_REQUIRED" -eq 1 && "$INITIAL_REVIEW_STATUS" != "PASS" ]]; then
        SHOULD_RUN_REVIEW=1
    fi
fi

if [[ "$SHOULD_RUN_REVIEW" -eq 1 ]]; then
    echo "$BASELINE" > "$HEAD_FILE"
    REDCAP_BASELINE_HEAD_FILE="$HEAD_FILE" \
    REDCAP_REVIEW_RESULT_FILE="${REVIEW_RESULT_FILE:-}" \
    REDCAP_REVIEW_LOG_FILE="${REVIEW_LOG_FILE:-}" \
    REDCAP_RUNTIME_SESSION_ID="${REDCAP_RUNTIME_SESSION_ID:-}" \
    REDCAP_RUNTIME_CAPABILITY="${REDCAP_RUNTIME_CAPABILITY:-}" \
    REDCAP_HOST_PROCESS_PID="$HOST_PROCESS_PID" \
    bash "$SCRIPT_DIR/redcap-on-stop-review.sh" <<'EOF' 2>&1 || true
{}
EOF
fi

COMMIT_LOG=$(git -C "$REDCAP_ROOT" --no-pager log --oneline "$BASELINE..$CURRENT_HEAD" 2>/dev/null || echo "(无法获取)")
NOTIFIER="$SCRIPT_DIR/feishu-notifier.py"
SKIP_FEISHU="${REDCAP_SKIP_FEISHU:-0}"
REVIEW_STATUS=""
REQUIRED_REDLINES=""
NOTIFY_STATUS=1

if [[ -f "$REVIEW_RESULT_FILE" ]]; then
    REVIEW_STATUS=$(cat "$REVIEW_RESULT_FILE" 2>/dev/null || true)
fi

if [[ "$HOST" == "claude" && "$BASELINE" != "$CURRENT_HEAD" && -n "$REVIEW_LOG_FILE" && ! -f "$REVIEW_LOG_FILE" && -z "$REVIEW_STATUS" ]]; then
    REVIEW_STATUS="MISSING"
fi

append_required_redline() {
    local item="$1"
    if [[ -z "$item" ]]; then
        return 0
    fi
    if [[ -z "$REQUIRED_REDLINES" ]]; then
        REQUIRED_REDLINES="$item"
    else
        REQUIRED_REDLINES="${REQUIRED_REDLINES},$item"
    fi
}

send_notification() {
    local message="$1"

    if [[ "$SKIP_FEISHU" == "1" ]]; then
        return 0
    fi

    if [[ ! -f "$NOTIFIER" ]]; then
        return 1
    fi

    python3 "$NOTIFIER" notify "$message" --project "redcap" 2>/dev/null
}

REVIEW_REQUIRED=0
if [[ "$SKIP_REVIEW" != "1" && ( "$BASELINE" != "$CURRENT_HEAD" || "$PENDING_REVIEW_REQUIRED" -eq 1 ) ]]; then
    REVIEW_REQUIRED=1
fi

PM_GATE_OUTPUT=""
PM_GATE_STATUS=0
DRIFT_OUTPUT=""
DRIFT_STATUS=0
ARTIFACT_OUTPUT=""
ARTIFACT_STATUS=0
REPORT_OUTPUT=""
REPORT_STATUS=0
REVIEW_PASSED=0
REVIEW_PROOF_OUTPUT=""
REANCHOR_OUTPUT=""
REANCHOR_STATUS=0
VALIDATOR_INFRA_FAILURE=0
SESSION_END_VALIDATOR_OUTPUT=""

if ! run_session_end_validator_chain; then
    if ! redcap_validator_output_has_recordable_step "$SESSION_END_VALIDATOR_OUTPUT" review-proof-check reanchor-check pm-gate drift-check task-report-check artifact-lifecycle-check; then
        VALIDATOR_INFRA_FAILURE=1
    fi
elif ! redcap_validator_output_has_recordable_step "$SESSION_END_VALIDATOR_OUTPUT" review-proof-check reanchor-check pm-gate drift-check task-report-check artifact-lifecycle-check; then
    VALIDATOR_INFRA_FAILURE=1
fi

if [[ "$VALIDATOR_INFRA_FAILURE" -ne 1 ]]; then
    REVIEW_PROOF_OUTPUT=$(redcap_validator_step_detail "$SESSION_END_VALIDATOR_OUTPUT" "review-proof-check")
    REANCHOR_OUTPUT=$(redcap_validator_step_detail "$SESSION_END_VALIDATOR_OUTPUT" "reanchor-check")
    PM_GATE_OUTPUT=$(redcap_validator_step_detail "$SESSION_END_VALIDATOR_OUTPUT" "pm-gate")
    DRIFT_OUTPUT=$(redcap_validator_step_detail "$SESSION_END_VALIDATOR_OUTPUT" "drift-check")
    REPORT_OUTPUT=$(redcap_validator_step_detail "$SESSION_END_VALIDATOR_OUTPUT" "task-report-check")
    ARTIFACT_OUTPUT=$(redcap_validator_step_detail "$SESSION_END_VALIDATOR_OUTPUT" "artifact-lifecycle-check")

    [[ "$(redcap_validator_step_status "$SESSION_END_VALIDATOR_OUTPUT" "review-proof-check")" == "pass" ]] && REVIEW_PASSED=1
    [[ "$(redcap_validator_step_status "$SESSION_END_VALIDATOR_OUTPUT" "reanchor-check")" == "pass" ]] && REANCHOR_STATUS=1
    [[ "$(redcap_validator_step_status "$SESSION_END_VALIDATOR_OUTPUT" "pm-gate")" == "pass" ]] && PM_GATE_STATUS=1
    [[ "$(redcap_validator_step_status "$SESSION_END_VALIDATOR_OUTPUT" "drift-check")" == "pass" ]] && DRIFT_STATUS=1
    [[ "$(redcap_validator_step_status "$SESSION_END_VALIDATOR_OUTPUT" "task-report-check")" == "pass" ]] && REPORT_STATUS=1
    [[ "$(redcap_validator_step_status "$SESSION_END_VALIDATOR_OUTPUT" "artifact-lifecycle-check")" == "pass" ]] && ARTIFACT_STATUS=1

    if ! record_session_end_validator_steps "$SESSION_END_VALIDATOR_OUTPUT" "$REPORT_OUTPUT"; then
        redcap_runtime_record_degraded_mode \
            "$REDCAP_ROOT" \
            "session-end-validator-ledger-write-failed" \
            "host=$HOST current_head=$CURRENT_HEAD" \
            >/dev/null 2>&1 || true
    fi
else
    if ! record_session_end_phase "validator-chain" "fail" "validator chain failed before recordable step output: ${SESSION_END_VALIDATOR_OUTPUT:-none}" "$REPORT_OUTPUT"; then
        redcap_runtime_record_degraded_mode \
            "$REDCAP_ROOT" \
            "session-end-validator-ledger-write-failed" \
            "host=$HOST current_head=$CURRENT_HEAD phase=validator-chain" \
            >/dev/null 2>&1 || true
    fi
fi

if [[ "$VALIDATOR_INFRA_FAILURE" -ne 1 && "$REPORT_STATUS" -eq 1 && "$PM_GATE_STATUS" -eq 1 && "$DRIFT_STATUS" -eq 1 && "$ARTIFACT_STATUS" -eq 1 && "$REVIEW_PASSED" -eq 1 && "$REANCHOR_STATUS" -eq 1 ]]; then
    PENDING_CLEAR_STATUS=1
    CURRENT_PENDING_EXISTS=0
    if [[ "$PENDING_CLOSURE_EXISTS" == "1" ]]; then
        CURRENT_PENDING_EXISTS=1
        if ! redcap_interop_acquire_pending_closure_lock "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md"; then
            PENDING_CLEAR_STATUS=0
        else
            LOCKED_PENDING_STATE=$(redcap_interop_pending_closure_existing_file "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" 2>/dev/null || true)
            if [[ -z "$LOCKED_PENDING_STATE" || ! -f "$LOCKED_PENDING_STATE" ]]; then
                PENDING_CLEAR_STATUS=0
            else
                LOCKED_PENDING_UPDATED_AT=$(redcap_interop_read_state_field "$LOCKED_PENDING_STATE" "updated_at" 2>/dev/null || true)
                LOCKED_PENDING_HOST=$(redcap_interop_read_state_field "$LOCKED_PENDING_STATE" "host" 2>/dev/null || true)
                LOCKED_PENDING_TRIGGER=$(redcap_interop_read_state_field "$LOCKED_PENDING_STATE" "trigger" 2>/dev/null || true)
                LOCKED_PENDING_BASELINE=$(redcap_interop_read_state_field "$LOCKED_PENDING_STATE" "baseline_head" 2>/dev/null || true)
                LOCKED_PENDING_AUDITED=$(redcap_interop_read_state_field "$LOCKED_PENDING_STATE" "audited_head" 2>/dev/null || true)
                LOCKED_PENDING_ARTIFACT=$(redcap_interop_read_state_field "$LOCKED_PENDING_STATE" "artifact_path" 2>/dev/null || true)
                LOCKED_PENDING_TASK_ID=$(redcap_interop_read_state_field "$LOCKED_PENDING_STATE" "task_id" 2>/dev/null || true)
                LOCKED_PENDING_CONFIRMED_HASH=$(redcap_interop_read_state_field "$LOCKED_PENDING_STATE" "confirmed_hash" 2>/dev/null || true)
                LOCKED_PENDING_ACTIVE_SLICE=$(redcap_interop_read_state_field "$LOCKED_PENDING_STATE" "active_slice" 2>/dev/null || true)
                if [[ -z "$PENDING_UPDATED_AT" || "$LOCKED_PENDING_UPDATED_AT" != "$PENDING_UPDATED_AT" ]]; then
                    PENDING_CLEAR_STATUS=0
                elif send_notification "$(redcap_build_completion_message \
                    "RedCap Layer B 收尾完成" \
                    "redcap" \
                    "$COMMIT_LOG" \
                    "${HOST} SessionEnd 兜底收尾" \
                    "$REPORT_OUTPUT" \
                    "$REDCAP_ROOT")"; then
                    if ! rm -f "$LOCKED_PENDING_STATE" 2>/dev/null; then
                        PENDING_CLEAR_STATUS=0
                        redcap_runtime_record_degraded_mode "$REDCAP_ROOT" "session-end-clear-after-notify-failed" "host=$HOST current_head=$CURRENT_HEAD" || true
                    else
                        redcap_interop_record_closure_event \
                            "$REDCAP_ROOT" \
                            "pending-closure-cleared" \
                            "task=$(basename "$LOCKED_PENDING_STATE") outcome=session-end-cleared detail=host=$HOST current_head=$CURRENT_HEAD" \
                            >/dev/null 2>&1 || true
                        if ! redcap_interop_append_closure_ledger_identity \
                            "$REDCAP_ROOT" \
                            "$LOCKED_PENDING_TASK_ID" \
                            "$LOCKED_PENDING_CONFIRMED_HASH" \
                            "$LOCKED_PENDING_ACTIVE_SLICE" \
                            "obligation" \
                            "cleared" \
                            "outcome=session-end-cleared detail=host=$HOST current_head=$CURRENT_HEAD" \
                            "$LOCKED_PENDING_HOST" \
                            "$LOCKED_PENDING_TRIGGER" \
                            "$LOCKED_PENDING_BASELINE" \
                            "$LOCKED_PENDING_AUDITED" \
                            "$LOCKED_PENDING_ARTIFACT" \
                            >/dev/null 2>&1; then
                            if ! redcap_interop_append_closure_ledger \
                                "$REDCAP_ROOT" \
                                "$REDCAP_ROOT/.dev-task.md" \
                                "obligation" \
                                "cleared" \
                                "outcome=session-end-cleared detail=host=$HOST current_head=$CURRENT_HEAD" \
                                "$LOCKED_PENDING_HOST" \
                                "$LOCKED_PENDING_TRIGGER" \
                                "$LOCKED_PENDING_BASELINE" \
                                "$LOCKED_PENDING_AUDITED" \
                                "$LOCKED_PENDING_ARTIFACT" \
                                >/dev/null 2>&1; then
                                redcap_runtime_record_degraded_mode \
                                    "$REDCAP_ROOT" \
                                    "session-end-obligation-cleared-ledger-failed" \
                                    "host=$HOST current_head=$CURRENT_HEAD task_id=$LOCKED_PENDING_TASK_ID" \
                                    >/dev/null 2>&1 || true
                            fi
                        fi
                        echo "$CURRENT_HEAD" > "$NOTIFIED_FILE"
                        rm -f "$ALERTED_FILE" 2>/dev/null || true
                        clear_review_artifacts
                    fi
                else
                    NOTIFY_STATUS=0
                    append_required_redline "notify"
                fi
            fi

            redcap_interop_release_pending_closure_lock "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" >/dev/null 2>&1 || true
        fi
    else
        if send_notification "$(redcap_build_completion_message \
            "RedCap Layer B 收尾完成" \
            "redcap" \
            "$COMMIT_LOG" \
            "${HOST} SessionEnd 兜底收尾" \
            "$REPORT_OUTPUT" \
            "$REDCAP_ROOT")"; then
            echo "$CURRENT_HEAD" > "$NOTIFIED_FILE"
            rm -f "$ALERTED_FILE" 2>/dev/null || true
            clear_review_artifacts
        else
            NOTIFY_STATUS=0
            append_required_redline "notify"
        fi
    fi

    if [[ "$CURRENT_PENDING_EXISTS" -eq 1 && "$PENDING_CLEAR_STATUS" -ne 1 ]]; then
        append_required_redline "pending-closure"
    fi

    if [[ -z "$REQUIRED_REDLINES" ]]; then
        redcap_interop_append_closure_ledger \
            "$REDCAP_ROOT" \
            "$REDCAP_ROOT/.dev-task.md" \
            "session-end" \
            "pass" \
            "review_status=${REVIEW_STATUS:-none} review_passed=$REVIEW_PASSED reanchor_status=$REANCHOR_STATUS validator_infra_failure=$VALIDATOR_INFRA_FAILURE pm_gate_status=$PM_GATE_STATUS drift_status=$DRIFT_STATUS artifact_status=$ARTIFACT_STATUS report_status=$REPORT_STATUS notify_status=$NOTIFY_STATUS" \
            "$HOST" \
            "session-end" \
            "$BASELINE" \
            "$CURRENT_HEAD" \
            "$REPORT_OUTPUT" \
            >/dev/null 2>&1 || true
    fi
else
    if [[ "$VALIDATOR_INFRA_FAILURE" -eq 1 ]]; then
        append_required_redline "validator-chain"
    else
        if [[ "$REVIEW_REQUIRED" -eq 1 && "$REVIEW_PASSED" -ne 1 ]]; then
            append_required_redline "review"
        fi
        if [[ "$REANCHOR_STATUS" -ne 1 ]]; then
            append_required_redline "pending-closure"
        fi
        if [[ "$PM_GATE_STATUS" -ne 1 ]]; then
            append_required_redline "pm-gate"
        fi
        if [[ "$DRIFT_STATUS" -ne 1 ]]; then
            append_required_redline "drift"
        fi
        if [[ "$ARTIFACT_STATUS" -ne 1 ]]; then
            append_required_redline "artifact-lifecycle"
        fi
        if [[ "$REPORT_STATUS" -ne 1 ]]; then
            append_required_redline "task-report"
        fi
    fi

    LAST_ALERTED=""
    if [[ -f "$ALERTED_FILE" ]]; then
        LAST_ALERTED=$(cat "$ALERTED_FILE")
    fi

    if [[ "$LAST_ALERTED" != "$CURRENT_HEAD" ]]; then
        ALERT_BODY="⚠️ RedCap Layer B 收尾审计发现缺口（${HOST} SessionEnd）"
        if [[ "$VALIDATOR_INFRA_FAILURE" -eq 1 ]]; then
            ALERT_BODY="${ALERT_BODY}\n\n问题：session-end validator chain 未产出可判定 step\n\n输出:\n$SESSION_END_VALIDATOR_OUTPUT"
        else
            if [[ "$REVIEW_REQUIRED" -eq 1 && "$REVIEW_PASSED" -ne 1 ]]; then
                if [[ "$REVIEW_STATUS" == "FAIL" ]]; then
                    ALERT_BODY="${ALERT_BODY}\n\n问题：独立 stop-review / 控制面审计未通过"
                elif [[ "$REVIEW_STATUS" == "MISSING" ]]; then
                    ALERT_BODY="${ALERT_BODY}\n\n问题：存在变更，但未找到 Claude stop-review 的评审证据"
                elif [[ "$REVIEW_STATUS" == "INCONCLUSIVE" ]]; then
                    ALERT_BODY="${ALERT_BODY}\n\n问题：独立 stop-review 结果为 INCONCLUSIVE，不能视为评审通过"
                else
                    ALERT_BODY="${ALERT_BODY}\n\n问题：存在变更，但未拿到可判定的独立评审结果"
                fi
                if [[ -n "$REVIEW_PROOF_OUTPUT" ]]; then
                    ALERT_BODY="${ALERT_BODY}\n\n审计输出:\n$REVIEW_PROOF_OUTPUT"
                fi
            fi
            if [[ "$REANCHOR_STATUS" -ne 1 ]]; then
                ALERT_BODY="${ALERT_BODY}\n\n问题：待清理 closure 绑定的 audited head 与当前 HEAD 不可证明衔接，不能清除历史义务"
                if [[ -n "$REANCHOR_OUTPUT" ]]; then
                    ALERT_BODY="${ALERT_BODY}\n\n审计输出:\n$REANCHOR_OUTPUT"
                fi
            fi
            if [[ "$PM_GATE_STATUS" -ne 1 ]]; then
                ALERT_BODY="${ALERT_BODY}\n\n问题：.dev-task / PM Gate 守门失败\n\n输出:\n$PM_GATE_OUTPUT"
            fi
            if [[ "$DRIFT_STATUS" -ne 1 ]]; then
                ALERT_BODY="${ALERT_BODY}\n\n问题：active_slice / scope drift 审计失败\n\n输出:\n$DRIFT_OUTPUT"
            fi
            if [[ "$ARTIFACT_STATUS" -ne 1 ]]; then
                ALERT_BODY="${ALERT_BODY}\n\n问题：artifact lifecycle 审计失败\n\n输出:\n$ARTIFACT_OUTPUT"
            fi
            if [[ "$REPORT_STATUS" -ne 1 ]]; then
                ALERT_BODY="${ALERT_BODY}\n\n问题：缺少按模板归档的任务完成报告\n\n审计输出:\n$REPORT_OUTPUT"
            fi
        fi
        ALERT_BODY="${ALERT_BODY}\n\nCommits:\n$COMMIT_LOG"
        if send_notification "$ALERT_BODY"; then
            echo "$CURRENT_HEAD" > "$ALERTED_FILE"
        else
            NOTIFY_STATUS=0
            append_required_redline "notify"
        fi
    fi
fi

if [[ -n "$REQUIRED_REDLINES" ]]; then
    redcap_interop_write_pending_closure \
        "$REDCAP_ROOT" \
        "$REDCAP_ROOT/.dev-task.md" \
        "$HOST" \
        "layerB-session-end-audit-gap" \
        "$REQUIRED_REDLINES" \
        "baseline=$BASELINE current_head=$CURRENT_HEAD review_status=${REVIEW_STATUS:-none} review_passed=$REVIEW_PASSED reanchor_status=$REANCHOR_STATUS validator_infra_failure=$VALIDATOR_INFRA_FAILURE pm_gate_status=$PM_GATE_STATUS drift_status=$DRIFT_STATUS artifact_status=$ARTIFACT_STATUS report_status=$REPORT_STATUS notify_status=$NOTIFY_STATUS" \
        "" \
        "$BASELINE" \
        "$CURRENT_HEAD" \
        >/dev/null 2>&1 || true
    redcap_interop_append_closure_ledger \
        "$REDCAP_ROOT" \
        "$REDCAP_ROOT/.dev-task.md" \
        "session-end" \
        "blocked" \
        "required_redlines=$REQUIRED_REDLINES review_status=${REVIEW_STATUS:-none} review_passed=$REVIEW_PASSED reanchor_status=$REANCHOR_STATUS validator_infra_failure=$VALIDATOR_INFRA_FAILURE pm_gate_status=$PM_GATE_STATUS drift_status=$DRIFT_STATUS artifact_status=$ARTIFACT_STATUS report_status=$REPORT_STATUS notify_status=$NOTIFY_STATUS" \
        "$HOST" \
        "session-end" \
        "$BASELINE" \
        "$CURRENT_HEAD" \
        "$REPORT_OUTPUT" \
        >/dev/null 2>&1 || true
fi

cleanup_session_files
redcap_runtime_clear_process_claim "$HOST" "$HOST_PROCESS_PID" || true
exit 0

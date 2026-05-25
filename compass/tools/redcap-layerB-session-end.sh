#!/usr/bin/env bash
# 用途：运行时与收尾脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#runtime-and-closeout

# ─────────────────────────────────────────────────────────
# RedCap 框架 — Layer B SessionEnd 统一收尾入口
#
# 负责：
#   1. 非 Claude 宿主补跑独立架构评审
#   2. 检查本次 commit 区间是否产出模板化任务报告
#   3. 只在节点汇报或真实人工介入时发送飞书；内部 audit gap 默认落账不通知
#   4. 维护去重标记，避免重复提醒
# ─────────────────────────────────────────────────────────

set -u

HOST="${1:-}"

if [[ -z "$HOST" ]]; then
    echo "[redcap-layerB-session-end] ERROR: host is required" >&2
    exit 2
fi

if [[ "${REDCAP_SUPPRESS_LIFECYCLE_HOOKS:-0}" == "1" || "${REDCAP_INTERNAL_HEALTH_PROBE:-0}" == "1" ]]; then
    echo "[redcap-layerB-session-end] suppressed for internal health probe host=$HOST" >&2
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TASK_FILE="${REDCAP_TASK_FILE:-$REDCAP_ROOT/.dev-task.md}"
source "$SCRIPT_DIR/redcap-runtime-state.sh"
source "$SCRIPT_DIR/redcap-interop-governance.sh"
source "$SCRIPT_DIR/redcap-notify-format.sh"
source "$SCRIPT_DIR/redcap-validator-output.sh"

VALIDATOR_CHAIN="${REDCAP_VALIDATOR_CHAIN_SCRIPT:-$SCRIPT_DIR/redcap-validator-chain.sh}"

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
WARNED_FILE=""
REVIEW_RESULT_FILE=""
REVIEW_LOG_FILE=""
LEGACY_CLAUDE_HEAD_FILE="/tmp/redcap-claude-initial-head"
RUNTIME_ATTACHED=0
USED_LEGACY_CLAUDE_HEAD=0

session_end_missing_runtime_can_exit_cleanly() {
    local status_json acceptance_status

    if [[ ! -f "$TASK_FILE" ]]; then
        return 1
    fi
    status_json=$(bash "$SCRIPT_DIR/redcap-layerb-closeout-runtime.sh" status --task-file "$TASK_FILE" 2>/dev/null) || return 1
    acceptance_status=$(printf '%s' "$status_json" | python3 -c 'import json,sys
try:
    payload=json.load(sys.stdin)
except Exception:
    raise SystemExit(2)
acceptance=(payload.get("acceptance") or {}).get("status", "")
receipt=payload.get("receipt_exists") is True
pending=int(payload.get("promise_pending") or 0)
print(acceptance)
raise SystemExit(0 if receipt and pending == 0 and acceptance in {"pass", "not-required", "resource-limited-pass"} else 1)
' 2>/dev/null) || return 1
    [[ -n "$acceptance_status" ]]
}

if [[ -n "$BINDING_KEY" ]] && redcap_runtime_load_from_binding "$HOST" "$HOOK_CWD" "$BINDING_KEY"; then
    HEAD_FILE=$(redcap_runtime_path "layerB/initial-head")
    NOTIFIED_FILE=$(redcap_runtime_path "layerB/notified-head")
    ALERTED_FILE=$(redcap_runtime_path "layerB/alerted-head")
    WARNED_FILE=$(redcap_runtime_path "layerB/warned-head")
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
    if session_end_missing_runtime_can_exit_cleanly; then
        CLEAN_EXIT_STATUS="pass"
        CLEAN_EXIT_DETAIL="missing-runtime-claim ignored because closeout receipt is present and promises are complete"
        if redcap_interop_pending_closure_exists "$REDCAP_ROOT" "$TASK_FILE"; then
            PENDING_STATE_FILE=$(redcap_interop_pending_closure_existing_file "$REDCAP_ROOT" "$TASK_FILE" 2>/dev/null || true)
            PENDING_TRIGGER=""
            if [[ -n "$PENDING_STATE_FILE" && -f "$PENDING_STATE_FILE" ]]; then
                PENDING_TRIGGER=$(redcap_interop_read_state_field "$PENDING_STATE_FILE" "trigger" 2>/dev/null || true)
            fi
            if [[ "$PENDING_TRIGGER" == "layerB-session-end-missing-runtime-claim" ]]; then
                if redcap_interop_clear_pending_closure \
                    "$REDCAP_ROOT" \
                    "$TASK_FILE" \
                    "session-end-receipt-present" \
                    "host=$HOST stale missing runtime claim ignored because closeout receipt is present" \
                    >/dev/null 2>&1; then
                    CLEAN_EXIT_DETAIL="stale missing-runtime pending closure cleared because closeout receipt is present and promises are complete"
                else
                    CLEAN_EXIT_STATUS="warn"
                    CLEAN_EXIT_DETAIL="closeout receipt is present, but stale missing-runtime pending closure cleanup failed; pending closure remains visible"
                fi
            else
                CLEAN_EXIT_STATUS="warn"
                CLEAN_EXIT_DETAIL="closeout receipt is present; non-missing-runtime pending closure trigger=${PENDING_TRIGGER:-unknown} preserved and no new missing-runtime closure written"
            fi
        fi
        redcap_interop_append_closure_ledger \
            "$REDCAP_ROOT" \
            "$TASK_FILE" \
            "session-end" \
            "$CLEAN_EXIT_STATUS" \
            "$CLEAN_EXIT_DETAIL" \
            "$HOST" \
            "layerB-session-end-missing-runtime-claim" \
            "" \
            "$CURRENT_HEAD" \
            "" \
            >/dev/null 2>&1 || true
        redcap_runtime_clear_process_claim "$HOST" "$HOST_PROCESS_PID" || true
        exit 0
    fi
    MISSING_RUNTIME_REDLINES="review,pm-gate,drift,artifact-lifecycle,task-report,notify"
    if redcap_interop_pending_closure_exists "$REDCAP_ROOT" "$TASK_FILE"; then
        MISSING_RUNTIME_REDLINES="pending-closure,$MISSING_RUNTIME_REDLINES"
    fi
    redcap_interop_write_pending_closure \
        "$REDCAP_ROOT" \
        "$TASK_FILE" \
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

PENDING_CLOSURE_STATE=$(redcap_interop_pending_closure_file "$REDCAP_ROOT" "$TASK_FILE" 2>/dev/null || true)
PENDING_CLOSURE_EXISTS=0
PENDING_REQUIRED_REDLINES=""
PENDING_ARTIFACT_PATH=""
PENDING_BASELINE_HEAD=""
PENDING_AUDITED_HEAD=""
PENDING_UPDATED_AT=""
PENDING_REVIEW_REQUIRED=0
PENDING_CLOSURE_HEAD_MISMATCH=0
if [[ -n "$PENDING_CLOSURE_STATE" && -f "$PENDING_CLOSURE_STATE" ]]; then
    PENDING_CLOSURE_EXISTS=1
    PENDING_REQUIRED_REDLINES=$(redcap_interop_read_state_field "$PENDING_CLOSURE_STATE" "required_redlines" 2>/dev/null || true)
    PENDING_ARTIFACT_PATH=$(redcap_interop_read_state_field "$PENDING_CLOSURE_STATE" "artifact_path" 2>/dev/null || true)
    PENDING_BASELINE_HEAD=$(redcap_interop_read_state_field "$PENDING_CLOSURE_STATE" "baseline_head" 2>/dev/null || true)
    PENDING_AUDITED_HEAD=$(redcap_interop_read_state_field "$PENDING_CLOSURE_STATE" "audited_head" 2>/dev/null || true)
    PENDING_UPDATED_AT=$(redcap_interop_read_state_field "$PENDING_CLOSURE_STATE" "updated_at" 2>/dev/null || true)
    case ",$PENDING_REQUIRED_REDLINES," in
        *,review,*) PENDING_REVIEW_REQUIRED=1 ;;
    esac
fi

cleanup_session_files() {
    rm -f "$HEAD_FILE" 2>/dev/null || true
    redcap_interop_clear_current_report_marker || true
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

SESSION_END_PERSISTENCE_FAILURE=0
SESSION_END_PERSISTENCE_DETAIL=""

mark_session_end_persistence_failure() {
    local reason="$1"
    local detail="${2:-}"

    SESSION_END_PERSISTENCE_FAILURE=1
    case ",$SESSION_END_PERSISTENCE_DETAIL," in
        *,"$reason",*) ;;
        *)
            if [[ -z "$SESSION_END_PERSISTENCE_DETAIL" ]]; then
                SESSION_END_PERSISTENCE_DETAIL="$reason"
            else
                SESSION_END_PERSISTENCE_DETAIL="${SESSION_END_PERSISTENCE_DETAIL},$reason"
            fi
            ;;
    esac

    redcap_runtime_record_degraded_mode \
        "$REDCAP_ROOT" \
        "$reason" \
        "host=$HOST current_head=$CURRENT_HEAD detail=$detail" \
        >/dev/null 2>&1 || true
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
        bash "$VALIDATOR_CHAIN" session-end "$HOST" "$TASK_FILE" "$BASELINE" "$CURRENT_HEAD" text 2>&1) || return 1

    return 0
}

record_session_end_phase() {
    local phase="$1"
    local status="$2"
    local detail="${3:-}"
    local artifact_path="${4:-}"

    redcap_interop_append_closure_ledger \
        "$REDCAP_ROOT" \
        "$TASK_FILE" \
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

    status=$(redcap_validator_step_status "$output" "backlog-check")
    case "$status" in
        pass) record_session_end_phase "backlog" "pass" "validator-chain step passed" "$artifact_path" || persist_status=1 ;;
        fail) record_session_end_phase "backlog" "fail" "validator-chain step failed" "$artifact_path" || persist_status=1 ;;
    esac

    status=$(redcap_validator_step_status "$output" "spec-check")
    case "$status" in
        pass) record_session_end_phase "spec" "pass" "validator-chain step passed" "$artifact_path" || persist_status=1 ;;
        fail) record_session_end_phase "spec" "fail" "validator-chain step failed" "$artifact_path" || persist_status=1 ;;
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
PRISM_ACCEPTANCE_PASSED=0
if bash "$SCRIPT_DIR/redcap-prism-acceptance-check.sh" --task-file "$TASK_FILE" >/dev/null 2>&1; then
    PRISM_ACCEPTANCE_PASSED=1
    if [[ -z "$INITIAL_REVIEW_STATUS" ]]; then
        INITIAL_REVIEW_STATUS="PRISM_PASS"
    fi
fi

SHOULD_RUN_REVIEW=0
if [[ "$SKIP_REVIEW" != "1" ]]; then
    if [[ "$PRISM_ACCEPTANCE_PASSED" -eq 1 ]]; then
        SHOULD_RUN_REVIEW=0
    elif [[ "$HOST" != "claude" && "$BASELINE" != "$CURRENT_HEAD" ]]; then
        SHOULD_RUN_REVIEW=1
    elif [[ "$HOST" == "claude" && "$PENDING_REVIEW_REQUIRED" -eq 1 && "$INITIAL_REVIEW_STATUS" != "PASS" ]]; then
        SHOULD_RUN_REVIEW=1
    fi
fi

if [[ "$SHOULD_RUN_REVIEW" -eq 1 ]]; then
    echo "$BASELINE" > "$HEAD_FILE"
    REDCAP_STOP_REVIEW_HOST="$HOST" \
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
NOTIFIER="${REDCAP_FEISHU_NOTIFIER:-$SCRIPT_DIR/feishu-notifier.py}"
SKIP_FEISHU="${REDCAP_SKIP_FEISHU:-0}"
SKIP_SUCCESS_NOTIFY="${REDCAP_SKIP_SESSION_END_SUCCESS_NOTIFY:-1}"
AUDIT_GAP_NOTIFY="${REDCAP_SESSION_END_NOTIFY_AUDIT_GAP:-0}"
NOTIFY_TIMEOUT_SECONDS="${REDCAP_FEISHU_NOTIFY_TIMEOUT_SECONDS:-5}"
REVIEW_STATUS=""
REQUIRED_REDLINES=""
NOTIFY_STATUS=1
SUCCESS_GUARD_LOCK_HELD=0

if [[ -f "$REVIEW_RESULT_FILE" ]]; then
    REVIEW_STATUS=$(cat "$REVIEW_RESULT_FILE" 2>/dev/null || true)
fi

review_result_is_superseded_control_plane_failure() {
    [[ "$REVIEW_STATUS" == "FAIL" && "$PRISM_ACCEPTANCE_PASSED" -eq 1 ]] || return 1
    [[ -n "$REVIEW_LOG_FILE" && -f "$REVIEW_LOG_FILE" ]] || return 1
    grep -q "validator chain 检查失败" "$REVIEW_LOG_FILE" || return 1
    grep -q "mode: stop-review" "$REVIEW_LOG_FILE" || return 1
    return 0
}

if [[ "$PRISM_ACCEPTANCE_PASSED" -eq 1 ]]; then
    if [[ -z "$REVIEW_STATUS" ]]; then
        REVIEW_STATUS="PRISM_PASS"
    elif review_result_is_superseded_control_plane_failure; then
        # A previous stop-review may have failed only because the control-plane
        # gates were stale. Once current Prism acceptance is bound and passes,
        # that stale control-plane FAIL must not poison the final SessionEnd.
        REVIEW_STATUS="PRISM_PASS"
        clear_review_artifacts
    fi
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

pending_write_baseline_head() {
    if [[ "$REANCHOR_STATUS" -ne 1 && "$PENDING_CLOSURE_EXISTS" == "1" && -n "$PENDING_BASELINE_HEAD" ]]; then
        printf '%s\n' "$PENDING_BASELINE_HEAD"
        return 0
    fi
    printf '%s\n' "$BASELINE"
}

pending_write_audited_head() {
    if [[ "$REANCHOR_STATUS" -ne 1 && "$PENDING_CLOSURE_EXISTS" == "1" && -n "$PENDING_AUDITED_HEAD" ]]; then
        printf '%s\n' "$PENDING_AUDITED_HEAD"
        return 0
    fi
    printf '%s\n' "$CURRENT_HEAD"
}

session_end_redlines_clearable_after_success() {
    local normalized item
    local -a items=()

    normalized=$(redcap_interop_normalize_redlines "${1:-}")
    [[ -n "$normalized" ]] || return 0

    IFS=',' read -r -a items <<< "$normalized"
    for item in "${items[@]:-}"; do
        case "$item" in
            review|commit-proof|pending-closure|pm-gate|drift|backlog|spec|artifact-lifecycle|task-report|notify|closeout-runtime|promise-ledger|prism-acceptance|validator-chain|closure-ledger)
                ;;
            *)
                return 1
                ;;
        esac
    done

    return 0
}

session_end_pending_commit_covered_by_success_window() {
    local commit="$1"

    [[ -n "$commit" ]] || return 0
    git -C "$REDCAP_ROOT" rev-parse "${commit}^{commit}" >/dev/null 2>&1 || return 1
    git -C "$REDCAP_ROOT" merge-base --is-ancestor "$commit" "$CURRENT_HEAD" >/dev/null 2>&1 || return 1

    return 0
}

session_end_pending_baseline_covered_by_success_window() {
    local baseline="$1"

    [[ -n "$baseline" ]] || return 0
    git -C "$REDCAP_ROOT" rev-parse "${baseline}^{commit}" >/dev/null 2>&1 || return 1
    git -C "$REDCAP_ROOT" merge-base --is-ancestor "$BASELINE" "$baseline" >/dev/null 2>&1 || return 1
    git -C "$REDCAP_ROOT" merge-base --is-ancestor "$baseline" "$CURRENT_HEAD" >/dev/null 2>&1 || return 1

    return 0
}

session_end_pending_state_safe_to_clear_after_success() {
    local state_file="$1"
    local current_confirmed_hash state_confirmed_hash state_baseline state_audited state_redlines

    [[ -n "$state_file" && -f "$state_file" ]] || return 1

    current_confirmed_hash=$(redcap_dev_task_confirmed_hash "$TASK_FILE" 2>/dev/null || true)
    state_confirmed_hash=$(redcap_interop_read_state_field "$state_file" "confirmed_hash" 2>/dev/null || true)
    if [[ -n "$state_confirmed_hash" && -n "$current_confirmed_hash" && "$state_confirmed_hash" != "$current_confirmed_hash" ]]; then
        return 1
    fi

    state_redlines=$(redcap_interop_read_state_field "$state_file" "required_redlines" 2>/dev/null || true)
    session_end_redlines_clearable_after_success "$state_redlines" || return 1

    state_baseline=$(redcap_interop_read_state_field "$state_file" "baseline_head" 2>/dev/null || true)
    session_end_pending_baseline_covered_by_success_window "$state_baseline" || return 1

    state_audited=$(redcap_interop_read_state_field "$state_file" "audited_head" 2>/dev/null || true)
    session_end_pending_commit_covered_by_success_window "$state_audited" || return 1

    return 0
}

session_end_pending_clear_expected_updated_at() {
    local state_file updated_at

    state_file=$(redcap_interop_pending_closure_existing_file "$REDCAP_ROOT" "$TASK_FILE" 2>/dev/null || true)
    [[ -n "$state_file" && -f "$state_file" ]] || return 1

    updated_at=$(redcap_interop_read_state_field "$state_file" "updated_at" 2>/dev/null || true)
    [[ -n "$updated_at" ]] || return 1

    if [[ -n "$PENDING_UPDATED_AT" && "$updated_at" == "$PENDING_UPDATED_AT" ]]; then
        printf '%s\n' "$updated_at"
        return 0
    fi

    session_end_pending_state_safe_to_clear_after_success "$state_file" || return 1
    printf '%s\n' "$updated_at"
}

notification_state_key() {
    printf '%s\n' "$CURRENT_HEAD|$REQUIRED_REDLINES|${SESSION_END_PERSISTENCE_DETAIL:-none}"
}

session_end_report_rel_path() {
    local rel_path="${1:-}"

    [[ -n "$rel_path" ]] || return 1
    redcap_interop_resolve_report_rel_path "$REDCAP_ROOT" "$rel_path" 2>/dev/null
}

session_end_report_artifact_path() {
    local marker_rel=""
    local resolved_rel=""

    resolved_rel=$(session_end_report_rel_path "$REPORT_OUTPUT" || true)
    if [[ -n "$resolved_rel" ]]; then
        printf '%s\n' "$resolved_rel"
        return 0
    fi

    marker_rel=$(redcap_interop_current_report_marker_rel "$REDCAP_ROOT" "$TASK_FILE" 2>/dev/null || true)
    resolved_rel=$(session_end_report_rel_path "$marker_rel" || true)
    if [[ -n "$resolved_rel" ]]; then
        printf '%s\n' "$resolved_rel"
        return 0
    fi

    resolved_rel=$(session_end_report_rel_path "$PENDING_ARTIFACT_PATH" || true)
    if [[ -n "$resolved_rel" ]]; then
        printf '%s\n' "$resolved_rel"
        return 0
    fi

    return 1
}

send_notification() {
    local message="$1"
    local window_type="${2:-manual-intervention}"

    if [[ "$SKIP_FEISHU" == "1" ]]; then
        return 0
    fi

    if [[ ! -f "$NOTIFIER" ]]; then
        return 1
    fi

    if [[ "$NOTIFY_TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] && [[ "$NOTIFY_TIMEOUT_SECONDS" -gt 0 ]]; then
        REDCAP_NOTIFY_MESSAGE="$message" \
        REDCAP_NOTIFY_WINDOW_TYPE="$window_type" \
        REDCAP_NOTIFY_TIMEOUT_SECONDS="$NOTIFY_TIMEOUT_SECONDS" \
            python3 - "$NOTIFIER" <<'PY' 2>/dev/null
import os
import subprocess
import sys

notifier = sys.argv[1]
message = os.environ["REDCAP_NOTIFY_MESSAGE"]
window_type = os.environ["REDCAP_NOTIFY_WINDOW_TYPE"]
timeout_seconds = int(os.environ["REDCAP_NOTIFY_TIMEOUT_SECONDS"])

try:
    result = subprocess.run(
        [
            "python3",
            notifier,
            "notify",
            message,
            "--project",
            "redcap",
            "--window-type",
            window_type,
            "--no-background-watch",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=timeout_seconds,
    )
except subprocess.TimeoutExpired:
    sys.exit(124)

sys.exit(result.returncode)
PY
        return $?
    fi

    python3 "$NOTIFIER" notify \
        "$message" \
        --project "redcap" \
        --window-type "$window_type" \
        --no-background-watch \
        2>/dev/null
}

session_end_success_notify_enabled() {
    [[ "$SKIP_SUCCESS_NOTIFY" != "1" ]]
}

session_end_audit_gap_notify_enabled() {
    # internal audit gap is ledger-only by default; Feishu is reserved for
    # node-report or true manual-intervention interrupts.
    [[ "$AUDIT_GAP_NOTIFY" == "1" ]]
}

acquire_success_guard_lock() {
    if redcap_interop_acquire_pending_closure_lock "$REDCAP_ROOT" "$TASK_FILE"; then
        SUCCESS_GUARD_LOCK_HELD=1
        return 0
    fi
    return 1
}

release_success_guard_lock() {
    if [[ "$SUCCESS_GUARD_LOCK_HELD" -eq 1 ]]; then
        redcap_interop_release_pending_closure_lock "$REDCAP_ROOT" "$TASK_FILE" >/dev/null 2>&1 || true
        SUCCESS_GUARD_LOCK_HELD=0
    fi
}

trap 'release_success_guard_lock' EXIT

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
BACKLOG_OUTPUT=""
BACKLOG_STATUS=0
SPEC_OUTPUT=""
SPEC_STATUS=0
REPORT_OUTPUT=""
REPORT_ARTIFACT_PATH=""
REPORT_STATUS=0
REVIEW_PASSED=0
REVIEW_PROOF_OUTPUT=""
REANCHOR_OUTPUT=""
REANCHOR_STATUS=0
VALIDATOR_INFRA_FAILURE=0
SESSION_END_VALIDATOR_OUTPUT=""
SUCCESS_NOTIFY_SENT=0
BLOCKER_ALERT_SENT=0
BLOCKER_ALERT_KEY=""
COMPENSATION_WARNING_SENT=0
COMPENSATION_WARNING_KEY=""
ALERT_BODY=""

if ! run_session_end_validator_chain; then
    if ! redcap_validator_output_has_recordable_step "$SESSION_END_VALIDATOR_OUTPUT" review-proof-check reanchor-check pm-gate drift-check backlog-check spec-check task-report-check artifact-lifecycle-check; then
        VALIDATOR_INFRA_FAILURE=1
    fi
elif ! redcap_validator_output_has_recordable_step "$SESSION_END_VALIDATOR_OUTPUT" review-proof-check reanchor-check pm-gate drift-check backlog-check spec-check task-report-check artifact-lifecycle-check; then
    VALIDATOR_INFRA_FAILURE=1
fi

if [[ "$VALIDATOR_INFRA_FAILURE" -ne 1 ]]; then
    REVIEW_PROOF_OUTPUT=$(redcap_validator_step_detail "$SESSION_END_VALIDATOR_OUTPUT" "review-proof-check")
    REANCHOR_OUTPUT=$(redcap_validator_step_detail "$SESSION_END_VALIDATOR_OUTPUT" "reanchor-check")
    PM_GATE_OUTPUT=$(redcap_validator_step_detail "$SESSION_END_VALIDATOR_OUTPUT" "pm-gate")
    DRIFT_OUTPUT=$(redcap_validator_step_detail "$SESSION_END_VALIDATOR_OUTPUT" "drift-check")
    BACKLOG_OUTPUT=$(redcap_validator_step_detail "$SESSION_END_VALIDATOR_OUTPUT" "backlog-check")
    SPEC_OUTPUT=$(redcap_validator_step_detail "$SESSION_END_VALIDATOR_OUTPUT" "spec-check")
    REPORT_OUTPUT=$(redcap_validator_step_detail "$SESSION_END_VALIDATOR_OUTPUT" "task-report-check")
    ARTIFACT_OUTPUT=$(redcap_validator_step_detail "$SESSION_END_VALIDATOR_OUTPUT" "artifact-lifecycle-check")

    [[ "$(redcap_validator_step_status "$SESSION_END_VALIDATOR_OUTPUT" "review-proof-check")" == "pass" ]] && REVIEW_PASSED=1
    [[ "$(redcap_validator_step_status "$SESSION_END_VALIDATOR_OUTPUT" "reanchor-check")" == "pass" ]] && REANCHOR_STATUS=1
    [[ "$(redcap_validator_step_status "$SESSION_END_VALIDATOR_OUTPUT" "pm-gate")" == "pass" ]] && PM_GATE_STATUS=1
    [[ "$(redcap_validator_step_status "$SESSION_END_VALIDATOR_OUTPUT" "drift-check")" == "pass" ]] && DRIFT_STATUS=1
    [[ "$(redcap_validator_step_status "$SESSION_END_VALIDATOR_OUTPUT" "backlog-check")" == "pass" ]] && BACKLOG_STATUS=1
    [[ "$(redcap_validator_step_status "$SESSION_END_VALIDATOR_OUTPUT" "spec-check")" == "pass" ]] && SPEC_STATUS=1
    [[ "$(redcap_validator_step_status "$SESSION_END_VALIDATOR_OUTPUT" "task-report-check")" == "pass" ]] && REPORT_STATUS=1
    [[ "$(redcap_validator_step_status "$SESSION_END_VALIDATOR_OUTPUT" "artifact-lifecycle-check")" == "pass" ]] && ARTIFACT_STATUS=1
    REPORT_ARTIFACT_PATH=$(session_end_report_artifact_path 2>/dev/null || true)

    if ! record_session_end_validator_steps "$SESSION_END_VALIDATOR_OUTPUT" "$REPORT_ARTIFACT_PATH"; then
        mark_session_end_persistence_failure \
            "session-end-validator-ledger-write-failed" \
            "phase=validator-steps"
    fi
else
    REPORT_ARTIFACT_PATH=$(session_end_report_artifact_path 2>/dev/null || true)
    if ! record_session_end_phase "validator-chain" "fail" "validator chain failed before recordable step output: ${SESSION_END_VALIDATOR_OUTPUT:-none}" "$REPORT_ARTIFACT_PATH"; then
        mark_session_end_persistence_failure \
            "session-end-validator-ledger-write-failed" \
            "phase=validator-chain"
    fi
fi

if [[ "$VALIDATOR_INFRA_FAILURE" -ne 1 && "$REPORT_STATUS" -eq 1 && "$PM_GATE_STATUS" -eq 1 && "$DRIFT_STATUS" -eq 1 && "$BACKLOG_STATUS" -eq 1 && "$SPEC_STATUS" -eq 1 && "$ARTIFACT_STATUS" -eq 1 && "$REVIEW_PASSED" -eq 1 && "$REANCHOR_STATUS" -eq 1 ]]; then
    PENDING_CLEAR_STATUS=1
    CURRENT_PENDING_EXISTS=0
    if [[ "$PENDING_CLOSURE_EXISTS" == "1" ]]; then
        PENDING_CLEAR_EXPECTED_AT=$(session_end_pending_clear_expected_updated_at 2>/dev/null || true)
        if [[ -n "$PENDING_CLEAR_EXPECTED_AT" ]]; then
            CURRENT_PENDING_EXISTS=1
            if ! redcap_interop_clear_pending_closure \
                "$REDCAP_ROOT" \
                "$TASK_FILE" \
                "session-end-cleared" \
                "host=$HOST current_head=$CURRENT_HEAD" \
                "$PENDING_CLEAR_EXPECTED_AT" \
                "locked" \
                >/dev/null 2>&1; then
                PENDING_CLEAR_STATUS=0
                redcap_runtime_record_degraded_mode \
                    "$REDCAP_ROOT" \
                    "session-end-clear-before-notify-failed" \
                    "host=$HOST current_head=$CURRENT_HEAD pending_updated_at=${PENDING_CLEAR_EXPECTED_AT:-missing}" \
                    || true
            fi
        elif redcap_interop_pending_closure_exists "$REDCAP_ROOT" "$TASK_FILE"; then
            CURRENT_PENDING_EXISTS=1
            PENDING_CLEAR_STATUS=0
            redcap_runtime_record_degraded_mode \
                "$REDCAP_ROOT" \
                "session-end-clear-before-notify-unsafe-refresh" \
                "host=$HOST current_head=$CURRENT_HEAD pending_updated_at=${PENDING_UPDATED_AT:-missing}" \
                || true
        fi
    fi

    if [[ "$CURRENT_PENDING_EXISTS" -eq 1 && "$PENDING_CLEAR_STATUS" -ne 1 ]]; then
        append_required_redline "pending-closure"
    fi

    if [[ -z "$REQUIRED_REDLINES" ]]; then
        if ! acquire_success_guard_lock; then
            append_required_redline "pending-closure"
            redcap_runtime_record_degraded_mode \
                "$REDCAP_ROOT" \
                "session-end-success-lock-failed" \
                "host=$HOST current_head=$CURRENT_HEAD" \
                >/dev/null 2>&1 || true
        elif redcap_interop_pending_closure_exists "$REDCAP_ROOT" "$TASK_FILE"; then
            append_required_redline "pending-closure"
        elif ! redcap_interop_append_closure_ledger \
            "$REDCAP_ROOT" \
            "$TASK_FILE" \
                "session-end" \
                "pass" \
                "review_status=${REVIEW_STATUS:-none} review_passed=$REVIEW_PASSED reanchor_status=$REANCHOR_STATUS validator_infra_failure=$VALIDATOR_INFRA_FAILURE pm_gate_status=$PM_GATE_STATUS drift_status=$DRIFT_STATUS backlog_status=$BACKLOG_STATUS spec_status=$SPEC_STATUS artifact_status=$ARTIFACT_STATUS report_status=$REPORT_STATUS notify_status=$NOTIFY_STATUS" \
                "$HOST" \
                "session-end" \
                "$BASELINE" \
            "$CURRENT_HEAD" \
            "$REPORT_ARTIFACT_PATH" \
            >/dev/null 2>&1; then
            mark_session_end_persistence_failure \
                "session-end-pass-ledger-write-failed" \
                "report=${REPORT_ARTIFACT_PATH:-none}"
        elif ! session_end_success_notify_enabled; then
            # In unified closeout runtime, on-complete owns the human-visible success notification.
            # SessionEnd still reconciles evidence and may send blocker alerts, but does not duplicate success notifications.
            echo "$CURRENT_HEAD" > "$NOTIFIED_FILE"
            rm -f "$ALERTED_FILE" 2>/dev/null || true
            rm -f "$WARNED_FILE" 2>/dev/null || true
            clear_review_artifacts
        elif send_notification "$(redcap_build_completion_message \
            "RedCap Layer B 收尾完成" \
            "redcap" \
            "$COMMIT_LOG" \
            "${HOST} SessionEnd 兜底收尾" \
            "$REPORT_ARTIFACT_PATH" \
            "$REDCAP_ROOT")" "node-report"; then
            SUCCESS_NOTIFY_SENT=1
            echo "$CURRENT_HEAD" > "$NOTIFIED_FILE"
            rm -f "$ALERTED_FILE" 2>/dev/null || true
            rm -f "$WARNED_FILE" 2>/dev/null || true
            clear_review_artifacts
        else
            NOTIFY_STATUS=0
            append_required_redline "notify"
        fi
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
        if [[ "$BACKLOG_STATUS" -ne 1 ]]; then
            append_required_redline "backlog"
        fi
        if [[ "$SPEC_STATUS" -ne 1 ]]; then
            append_required_redline "spec"
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

    PRE_ALERT_KEY=""
    PRE_ALERT_KEY=$(notification_state_key)
    if [[ "$LAST_ALERTED" != "$PRE_ALERT_KEY" ]]; then
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
            if [[ "$BACKLOG_STATUS" -ne 1 ]]; then
                ALERT_BODY="${ALERT_BODY}\n\n问题：长期路线 backlog 审计失败\n\n输出:\n$BACKLOG_OUTPUT"
            fi
            if [[ "$SPEC_STATUS" -ne 1 ]]; then
                ALERT_BODY="${ALERT_BODY}\n\n问题：spec 生命周期 / registry 审计失败\n\n输出:\n$SPEC_OUTPUT"
            fi
            if [[ "$ARTIFACT_STATUS" -ne 1 ]]; then
                ALERT_BODY="${ALERT_BODY}\n\n问题：artifact lifecycle 审计失败\n\n输出:\n$ARTIFACT_OUTPUT"
            fi
            if [[ "$REPORT_STATUS" -ne 1 ]]; then
                ALERT_BODY="${ALERT_BODY}\n\n问题：缺少按模板归档的任务完成报告\n\n审计输出:\n$REPORT_OUTPUT"
            fi
        fi
        if [[ "$SESSION_END_PERSISTENCE_FAILURE" -eq 1 ]]; then
            ALERT_BODY="${ALERT_BODY}\n\n问题：session-end blocker 无法完整写入 closure 证据层，不能视为闭环完成"
            ALERT_BODY="${ALERT_BODY}\n\n持久化缺口:\n${SESSION_END_PERSISTENCE_DETAIL:-unknown}"
        fi
        ALERT_BODY="${ALERT_BODY}\n\nCommits:\n$COMMIT_LOG"
        if session_end_audit_gap_notify_enabled; then
            if send_notification "$ALERT_BODY" "manual-intervention"; then
                BLOCKER_ALERT_SENT=1
                BLOCKER_ALERT_KEY="$PRE_ALERT_KEY"
            else
                NOTIFY_STATUS=0
                append_required_redline "notify"
            fi
        fi
    fi
fi

if [[ "$SESSION_END_PERSISTENCE_FAILURE" -eq 1 ]]; then
    append_required_redline "closure-ledger"
fi

release_success_guard_lock

if [[ "$SUCCESS_NOTIFY_SENT" -eq 1 && -n "$REQUIRED_REDLINES" ]] && session_end_audit_gap_notify_enabled; then
    PRE_WARN_KEY=$(notification_state_key)
    LAST_WARNED=""
    if [[ -f "$WARNED_FILE" ]]; then
        LAST_WARNED=$(cat "$WARNED_FILE")
    fi
    if [[ "$LAST_WARNED" != "$PRE_WARN_KEY" ]]; then
            if send_notification "⚠️ RedCap Layer B 收尾补偿失败（${HOST} SessionEnd）\n\n成功通知已发出，但后续 closure 持久化未完成，当前仍保留 blocker。\n\nrequired_redlines=$REQUIRED_REDLINES\npersistence_detail=${SESSION_END_PERSISTENCE_DETAIL:-none}\n\nCommits:\n$COMMIT_LOG" "manual-intervention"; then
            COMPENSATION_WARNING_SENT=1
            COMPENSATION_WARNING_KEY="$PRE_WARN_KEY"
        else
            NOTIFY_STATUS=0
            append_required_redline "notify"
        fi
    fi
fi

if [[ -n "$REQUIRED_REDLINES" ]]; then
    PENDING_WRITE_BASELINE=$(pending_write_baseline_head)
    PENDING_WRITE_AUDITED=$(pending_write_audited_head)
    if ! redcap_interop_write_pending_closure \
        "$REDCAP_ROOT" \
        "$TASK_FILE" \
        "$HOST" \
        "layerB-session-end-audit-gap" \
        "$REQUIRED_REDLINES" \
        "baseline=$BASELINE current_head=$CURRENT_HEAD review_status=${REVIEW_STATUS:-none} review_passed=$REVIEW_PASSED reanchor_status=$REANCHOR_STATUS validator_infra_failure=$VALIDATOR_INFRA_FAILURE pm_gate_status=$PM_GATE_STATUS drift_status=$DRIFT_STATUS backlog_status=$BACKLOG_STATUS spec_status=$SPEC_STATUS artifact_status=$ARTIFACT_STATUS report_status=$REPORT_STATUS notify_status=$NOTIFY_STATUS persistence_failure=$SESSION_END_PERSISTENCE_FAILURE persistence_detail=${SESSION_END_PERSISTENCE_DETAIL:-none}" \
        "$REPORT_ARTIFACT_PATH" \
        "$PENDING_WRITE_BASELINE" \
        "$PENDING_WRITE_AUDITED" \
        "replace" \
        >/dev/null 2>&1; then
        mark_session_end_persistence_failure \
            "session-end-pending-closure-write-failed" \
            "required_redlines=$REQUIRED_REDLINES"
        redcap_runtime_clear_process_claim "$HOST" "$HOST_PROCESS_PID" || true
        exit 1
    fi
    if ! redcap_interop_append_closure_ledger \
        "$REDCAP_ROOT" \
        "$TASK_FILE" \
        "session-end" \
        "blocked" \
        "required_redlines=$REQUIRED_REDLINES review_status=${REVIEW_STATUS:-none} review_passed=$REVIEW_PASSED reanchor_status=$REANCHOR_STATUS validator_infra_failure=$VALIDATOR_INFRA_FAILURE pm_gate_status=$PM_GATE_STATUS drift_status=$DRIFT_STATUS backlog_status=$BACKLOG_STATUS spec_status=$SPEC_STATUS artifact_status=$ARTIFACT_STATUS report_status=$REPORT_STATUS notify_status=$NOTIFY_STATUS persistence_failure=$SESSION_END_PERSISTENCE_FAILURE persistence_detail=${SESSION_END_PERSISTENCE_DETAIL:-none}" \
        "$HOST" \
        "session-end" \
        "$BASELINE" \
        "$CURRENT_HEAD" \
        "$REPORT_ARTIFACT_PATH" \
        >/dev/null 2>&1; then
        mark_session_end_persistence_failure \
            "session-end-blocked-ledger-write-failed" \
            "required_redlines=$REQUIRED_REDLINES"
        append_required_redline "closure-ledger"
        if ! redcap_interop_write_pending_closure \
            "$REDCAP_ROOT" \
            "$TASK_FILE" \
            "$HOST" \
            "layerB-session-end-audit-gap" \
            "$REQUIRED_REDLINES" \
            "baseline=$BASELINE current_head=$CURRENT_HEAD review_status=${REVIEW_STATUS:-none} review_passed=$REVIEW_PASSED reanchor_status=$REANCHOR_STATUS validator_infra_failure=$VALIDATOR_INFRA_FAILURE pm_gate_status=$PM_GATE_STATUS drift_status=$DRIFT_STATUS backlog_status=$BACKLOG_STATUS spec_status=$SPEC_STATUS artifact_status=$ARTIFACT_STATUS report_status=$REPORT_STATUS notify_status=$NOTIFY_STATUS persistence_failure=$SESSION_END_PERSISTENCE_FAILURE persistence_detail=${SESSION_END_PERSISTENCE_DETAIL:-none}" \
            "$REPORT_ARTIFACT_PATH" \
            "$PENDING_WRITE_BASELINE" \
            "$PENDING_WRITE_AUDITED" \
            "replace" \
            >/dev/null 2>&1; then
            mark_session_end_persistence_failure \
                "session-end-pending-closure-rewrite-failed" \
                "required_redlines=$REQUIRED_REDLINES"
        fi
        redcap_runtime_clear_process_claim "$HOST" "$HOST_PROCESS_PID" || true
        exit 1
    fi
    FINAL_NOTIFICATION_KEY=$(notification_state_key)
    if [[ "$SUCCESS_NOTIFY_SENT" -eq 1 ]]; then
        LAST_WARNED=""
        if [[ -f "$WARNED_FILE" ]]; then
            LAST_WARNED=$(cat "$WARNED_FILE")
        fi
        if [[ "$COMPENSATION_WARNING_SENT" -eq 1 && "$COMPENSATION_WARNING_KEY" == "$FINAL_NOTIFICATION_KEY" ]]; then
            echo "$FINAL_NOTIFICATION_KEY" > "$WARNED_FILE"
        elif session_end_audit_gap_notify_enabled && [[ "$LAST_WARNED" != "$FINAL_NOTIFICATION_KEY" ]]; then
            if send_notification "⚠️ RedCap Layer B 收尾补偿最终状态（${HOST} SessionEnd）\n\n最终 blocker 已确认并落盘。\n\nrequired_redlines=$REQUIRED_REDLINES\npersistence_detail=${SESSION_END_PERSISTENCE_DETAIL:-none}\n\nCommits:\n$COMMIT_LOG" "manual-intervention"; then
                echo "$FINAL_NOTIFICATION_KEY" > "$WARNED_FILE"
            fi
        fi
    else
        LAST_ALERTED=""
        if [[ -f "$ALERTED_FILE" ]]; then
            LAST_ALERTED=$(cat "$ALERTED_FILE")
        fi
        if [[ "$BLOCKER_ALERT_SENT" -eq 1 && "$BLOCKER_ALERT_KEY" == "$FINAL_NOTIFICATION_KEY" ]]; then
            echo "$FINAL_NOTIFICATION_KEY" > "$ALERTED_FILE"
        elif session_end_audit_gap_notify_enabled && [[ "$LAST_ALERTED" != "$FINAL_NOTIFICATION_KEY" ]]; then
            FINAL_ALERT_BODY="$ALERT_BODY"
            if [[ "$BLOCKER_ALERT_KEY" != "$FINAL_NOTIFICATION_KEY" ]]; then
                FINAL_ALERT_BODY="${FINAL_ALERT_BODY}\n\n最终 blocker 集已更新：required_redlines=$REQUIRED_REDLINES\npersistence_detail=${SESSION_END_PERSISTENCE_DETAIL:-none}"
            fi
            if send_notification "$FINAL_ALERT_BODY" "manual-intervention"; then
                echo "$FINAL_NOTIFICATION_KEY" > "$ALERTED_FILE"
            fi
        elif ! session_end_audit_gap_notify_enabled; then
            # Audit-gap Feishu noise is muted by default, but the local runtime
            # still needs a terminal marker so concurrent sessions can prove the
            # SessionEnd path reached a stable blocked state.
            echo "$FINAL_NOTIFICATION_KEY" > "$ALERTED_FILE"
        fi
    fi
    if [[ "$SESSION_END_PERSISTENCE_FAILURE" -eq 1 ]]; then
        redcap_runtime_clear_process_claim "$HOST" "$HOST_PROCESS_PID" || true
        exit 1
    fi
fi

cleanup_session_files
redcap_runtime_clear_process_claim "$HOST" "$HOST_PROCESS_PID" || true
exit 0

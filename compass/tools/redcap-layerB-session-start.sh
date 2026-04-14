#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap 框架 — Layer B SessionStart 统一入口
#
# 供 Claude InstructionsLoaded / Gemini SessionStart / Copilot sessionStart
# 复用。职责是：先过 session resume gate，再决定 full / degraded /
# unsupported 隔离模式，并完成会话起始同步。
# ─────────────────────────────────────────────────────────

set -euo pipefail

HOST="${1:-}"

if [[ -z "$HOST" ]]; then
    echo "[redcap-layerB-session-start] ERROR: host is required" >&2
    exit 2
fi

INPUT=$(cat)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/redcap-runtime-state.sh"
source "$SCRIPT_DIR/redcap-dev-task.sh"
source "$SCRIPT_DIR/redcap-interop-governance.sh"

HOOK_CWD="${REDCAP_HOOK_CWD:-$(redcap_runtime_json_field "$INPUT" "cwd")}"
if [[ -z "$HOOK_CWD" ]]; then
    HOOK_CWD="$REDCAP_ROOT"
fi

HOST_SESSION_ID="${REDCAP_HOST_SESSION_ID:-$(redcap_runtime_json_field "$INPUT" "session_id")}"
BINDING_KEY="${REDCAP_SESSION_BINDING_KEY:-}"

REDCAP_SESSION_ISOLATION_MODE="${REDCAP_SESSION_ISOLATION_MODE:-}"
REDCAP_SESSION_RESUME_REASON="${REDCAP_SESSION_RESUME_REASON:-}"
REDCAP_SESSION_RESUME_PROFILE="${REDCAP_SESSION_RESUME_PROFILE:-}"
REDCAP_SESSION_RESUME_EVIDENCE="${REDCAP_SESSION_RESUME_EVIDENCE:-}"
REDCAP_SESSION_RESUME_IDENTITY_SOURCE="${REDCAP_SESSION_RESUME_IDENTITY_SOURCE:-}"
REDCAP_SESSION_RESUME_RECOVERY_PATH="${REDCAP_SESSION_RESUME_RECOVERY_PATH:-}"
REDCAP_SESSION_RESUME_ALLOW_DISK_RECOVERY="${REDCAP_SESSION_RESUME_ALLOW_DISK_RECOVERY:-0}"
REDCAP_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY="${REDCAP_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY:-0}"
SESSION_RESUME_GATE_AVAILABLE=0

load_session_resume_gate() {
    local gate_script="$SCRIPT_DIR/redcap-session-resume-gate.sh"
    local key value

    [[ -x "$gate_script" ]] || return 1

    while IFS='=' read -r key value; do
        case "$key" in
            REDCAP_SESSION_ISOLATION_MODE) REDCAP_SESSION_ISOLATION_MODE="$value" ;;
            REDCAP_SESSION_RESUME_REASON) REDCAP_SESSION_RESUME_REASON="$value" ;;
            REDCAP_SESSION_RESUME_PROFILE) REDCAP_SESSION_RESUME_PROFILE="$value" ;;
            REDCAP_SESSION_RESUME_EVIDENCE) REDCAP_SESSION_RESUME_EVIDENCE="$value" ;;
            REDCAP_SESSION_RESUME_IDENTITY_SOURCE) REDCAP_SESSION_RESUME_IDENTITY_SOURCE="$value" ;;
            REDCAP_SESSION_RESUME_RECOVERY_PATH) REDCAP_SESSION_RESUME_RECOVERY_PATH="$value" ;;
            REDCAP_SESSION_RESUME_ALLOW_DISK_RECOVERY) REDCAP_SESSION_RESUME_ALLOW_DISK_RECOVERY="$value" ;;
            REDCAP_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY) REDCAP_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY="$value" ;;
            REDCAP_SESSION_BINDING_KEY) REDCAP_SESSION_BINDING_KEY="$value" ;;
            REDCAP_HOST_SESSION_ID) REDCAP_HOST_SESSION_ID="$value" ;;
        esac
    done < <(printf '%s' "$INPUT" | bash "$gate_script" "$HOST")
}

session_resume_gate_complete() {
    [[ -n "${REDCAP_SESSION_ISOLATION_MODE:-}" ]] &&
        [[ -n "${REDCAP_SESSION_RESUME_REASON:-}" ]] &&
        [[ -n "${REDCAP_SESSION_RESUME_PROFILE:-}" ]] &&
        [[ -n "${REDCAP_SESSION_RESUME_EVIDENCE:-}" ]] &&
        [[ -n "${REDCAP_SESSION_RESUME_RECOVERY_PATH:-}" ]] &&
        [[ "${REDCAP_SESSION_RESUME_ALLOW_DISK_RECOVERY:-}" =~ ^[01]$ ]] &&
        [[ "${REDCAP_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY:-}" =~ ^[01]$ ]]
}

ensure_repo_git_hooks() {
    local ensure_script="$SCRIPT_DIR/redcap-ensure-git-hooks.sh"

    [[ -x "$ensure_script" ]] || return 0

    if ! bash "$ensure_script" "$REDCAP_ROOT" >/dev/null 2>&1; then
        echo "[redcap-layerB-session-start] WARNING: failed to ensure repo-owned git hooks" >&2
    fi
}

if [[ -x "$SCRIPT_DIR/redcap-session-resume-gate.sh" ]]; then
    SESSION_RESUME_GATE_AVAILABLE=1
    if ! load_session_resume_gate || ! session_resume_gate_complete; then
        REDCAP_SESSION_ISOLATION_MODE="unsupported"
        REDCAP_SESSION_RESUME_REASON="resume-gate-error"
        REDCAP_SESSION_RESUME_PROFILE="resume-gate-error"
        REDCAP_SESSION_RESUME_EVIDENCE="capability-matrix,gate-execution-failed"
        REDCAP_SESSION_RESUME_IDENTITY_SOURCE="none"
        REDCAP_SESSION_RESUME_RECOVERY_PATH="unsupported"
        REDCAP_SESSION_RESUME_ALLOW_DISK_RECOVERY="0"
        REDCAP_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY="0"
    fi
fi

HOST_SESSION_ID="${REDCAP_HOST_SESSION_ID:-$HOST_SESSION_ID}"
BINDING_KEY="${REDCAP_SESSION_BINDING_KEY:-$BINDING_KEY}"

if [[ "$SESSION_RESUME_GATE_AVAILABLE" != "1" && -z "$REDCAP_SESSION_ISOLATION_MODE" ]]; then
    if [[ -n "$BINDING_KEY" ]]; then
        REDCAP_SESSION_ISOLATION_MODE="full"
        REDCAP_SESSION_RESUME_REASON="legacy-binding-key-fallback"
        REDCAP_SESSION_RESUME_PROFILE="legacy-fallback"
        REDCAP_SESSION_RESUME_EVIDENCE="binding-key"
        REDCAP_SESSION_RESUME_IDENTITY_SOURCE="binding-key"
        REDCAP_SESSION_RESUME_RECOVERY_PATH="runtime-binding-attach-or-create"
        REDCAP_SESSION_RESUME_ALLOW_DISK_RECOVERY="1"
        REDCAP_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY="1"
    else
        REDCAP_SESSION_ISOLATION_MODE="degraded"
        REDCAP_SESSION_RESUME_REASON="legacy-missing-binding-key"
        REDCAP_SESSION_RESUME_PROFILE="legacy-fallback"
        REDCAP_SESSION_RESUME_EVIDENCE="none"
        REDCAP_SESSION_RESUME_IDENTITY_SOURCE="none"
        REDCAP_SESSION_RESUME_RECOVERY_PATH="safe-degraded"
        REDCAP_SESSION_RESUME_ALLOW_DISK_RECOVERY="0"
        REDCAP_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY="0"
    fi
fi

if [[ "$REDCAP_SESSION_ISOLATION_MODE" == "full" && -z "$BINDING_KEY" ]]; then
    REDCAP_SESSION_ISOLATION_MODE="degraded"
    REDCAP_SESSION_RESUME_REASON="missing-binding-key-after-full-gate"
    REDCAP_SESSION_RESUME_RECOVERY_PATH="safe-degraded"
    REDCAP_SESSION_RESUME_ALLOW_DISK_RECOVERY="0"
    REDCAP_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY="0"
fi

run_control_plane_start_sync() {
    local sync_runtime_session_id=""
    local sync_runtime_capability=""
    local sync_runtime_binding_key="${REDCAP_SESSION_BINDING_KEY:-}"
    local sync_runtime_host="$HOST"

    if [[ "${REDCAP_SESSION_ISOLATION_MODE:-}" == "full" ]] && [[ -n "${REDCAP_RUNTIME_SESSION_ID:-}" ]] && redcap_runtime_assert_capability; then
        sync_runtime_session_id="${REDCAP_RUNTIME_SESSION_ID:-}"
        sync_runtime_capability="${REDCAP_RUNTIME_CAPABILITY:-}"
        sync_runtime_binding_key="${REDCAP_RUNTIME_BINDING_KEY:-${REDCAP_SESSION_BINDING_KEY:-}}"
        sync_runtime_host="${REDCAP_RUNTIME_HOST:-$HOST}"
    fi

    VALIDATOR_CHAIN="$SCRIPT_DIR/redcap-validator-chain.sh"
    PM_GATE_CHECK="$SCRIPT_DIR/redcap-pm-gate-check.sh"
    if [[ -x "$VALIDATOR_CHAIN" ]]; then
        REDCAP_RUNTIME_SESSION_ID="$sync_runtime_session_id" \
        REDCAP_RUNTIME_CAPABILITY="$sync_runtime_capability" \
        REDCAP_HOST_PROCESS_PID="${REDCAP_HOST_PROCESS_PID:-$PPID}" \
        bash "$VALIDATOR_CHAIN" session-start "$HOST" "$REDCAP_ROOT/.dev-task.md" "" "" text >/dev/null || true
    elif [[ -x "$PM_GATE_CHECK" ]]; then
        REDCAP_RUNTIME_SESSION_ID="$sync_runtime_session_id" \
        REDCAP_RUNTIME_CAPABILITY="$sync_runtime_capability" \
        REDCAP_HOST_PROCESS_PID="${REDCAP_HOST_PROCESS_PID:-$PPID}" \
        bash "$PM_GATE_CHECK" session-start "$HOST" "$REDCAP_ROOT/.dev-task.md" >/dev/null || true
    fi

    HOST_WORKBOARD_SYNC="$SCRIPT_DIR/redcap-host-workboard-sync.sh"
    if [[ -x "$HOST_WORKBOARD_SYNC" && -n "${REDCAP_HOST_WORKBOARD_PATH:-}" ]]; then
        bash "$HOST_WORKBOARD_SYNC" sync "$REDCAP_HOST_WORKBOARD_PATH" "$REDCAP_ROOT/.dev-task.md" 2>&1 || true
    fi

    SESSION_CONTINUITY="$SCRIPT_DIR/redcap-session-continuity.sh"
    if [[ -x "$SESSION_CONTINUITY" && -n "${REDCAP_HOST_WORKBOARD_PATH:-}" ]]; then
        REDCAP_RUNTIME_SESSION_ID="$sync_runtime_session_id" \
        REDCAP_RUNTIME_CAPABILITY="$sync_runtime_capability" \
        REDCAP_RUNTIME_BINDING_KEY="$sync_runtime_binding_key" \
        REDCAP_RUNTIME_HOST="$sync_runtime_host" \
        REDCAP_HOST_SESSION_ID="${REDCAP_HOST_SESSION_ID:-}" \
        REDCAP_SESSION_ISOLATION_MODE="${REDCAP_SESSION_ISOLATION_MODE:-}" \
        REDCAP_SESSION_RESUME_REASON="${REDCAP_SESSION_RESUME_REASON:-}" \
        REDCAP_SESSION_RESUME_PROFILE="${REDCAP_SESSION_RESUME_PROFILE:-}" \
        REDCAP_SESSION_RESUME_EVIDENCE="${REDCAP_SESSION_RESUME_EVIDENCE:-}" \
        bash "$SESSION_CONTINUITY" sync "$REDCAP_HOST_WORKBOARD_PATH" "$REDCAP_ROOT/.dev-task.md" 2>&1 || true
    fi
}

run_pending_closure_reconcile() {
    local reconcile_script="$SCRIPT_DIR/redcap-pending-closure-reconcile.sh"
    local reconcile_runtime_session_id=""
    local reconcile_runtime_capability=""

    if [[ ! -x "$reconcile_script" ]]; then
        return 0
    fi

    if [[ "${REDCAP_SESSION_ISOLATION_MODE:-}" == "full" ]] && [[ -n "${REDCAP_RUNTIME_SESSION_ID:-}" ]] && redcap_runtime_assert_capability; then
        reconcile_runtime_session_id="${REDCAP_RUNTIME_SESSION_ID:-}"
        reconcile_runtime_capability="${REDCAP_RUNTIME_CAPABILITY:-}"
    fi

    REDCAP_RUNTIME_SESSION_ID="$reconcile_runtime_session_id" \
    REDCAP_RUNTIME_CAPABILITY="$reconcile_runtime_capability" \
    REDCAP_HOST_PROCESS_PID="${REDCAP_HOST_PROCESS_PID:-$PPID}" \
        bash "$reconcile_script" "$HOST" >/dev/null 2>&1 || true
}

PRE_INIT_SESSION_ISOLATION_MODE="${REDCAP_SESSION_ISOLATION_MODE:-}"
PRE_INIT_SESSION_RESUME_REASON="${REDCAP_SESSION_RESUME_REASON:-}"
PRE_INIT_SESSION_RESUME_PROFILE="${REDCAP_SESSION_RESUME_PROFILE:-}"
PRE_INIT_SESSION_RESUME_EVIDENCE="${REDCAP_SESSION_RESUME_EVIDENCE:-}"
PRE_INIT_SESSION_RESUME_ALLOW_DISK_RECOVERY="${REDCAP_SESSION_RESUME_ALLOW_DISK_RECOVERY:-}"
PRE_INIT_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY="${REDCAP_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY:-}"

if [[ "$REDCAP_SESSION_ISOLATION_MODE" == "full" ]] && [[ -n "$BINDING_KEY" ]] && \
    REDCAP_RUNTIME_ALLOW_DISK_RECOVERY="$REDCAP_SESSION_RESUME_ALLOW_DISK_RECOVERY" \
    REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY="$REDCAP_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY" \
    redcap_runtime_init_from_binding "$HOST" "$HOOK_CWD" "$BINDING_KEY"; then
    PENDING_CLOSURE_EXISTS=0
    if redcap_interop_pending_closure_exists "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md"; then
        PENDING_CLOSURE_EXISTS=1
        redcap_interop_record_reanchor_event \
            "$REDCAP_ROOT" \
            "pending-closure-detected-on-session-start" \
            "host=$HOST binding_key=${BINDING_KEY:-missing} runtime_created=${REDCAP_RUNTIME_CREATED:-0}" \
            >/dev/null 2>&1 || true
    fi

    redcap_runtime_remove_path "layerB/current-report-path" || true

    if [[ "${REDCAP_RUNTIME_CREATED:-0}" == "1" ]]; then
        CURRENT_HEAD=$(git -C "$REDCAP_ROOT" rev-parse HEAD 2>/dev/null || true)
        if [[ -n "$CURRENT_HEAD" ]]; then
            redcap_runtime_write_text "layerB/initial-head" "$CURRENT_HEAD" || true
        fi
    fi
    if [[ "$PENDING_CLOSURE_EXISTS" == "1" ]]; then
        run_pending_closure_reconcile
    fi
    run_control_plane_start_sync
    exit 0
fi

REDCAP_SESSION_ISOLATION_MODE="${REDCAP_SESSION_ISOLATION_MODE:-$PRE_INIT_SESSION_ISOLATION_MODE}"
REDCAP_SESSION_RESUME_REASON="${REDCAP_SESSION_RESUME_REASON:-$PRE_INIT_SESSION_RESUME_REASON}"
REDCAP_SESSION_RESUME_PROFILE="${REDCAP_SESSION_RESUME_PROFILE:-$PRE_INIT_SESSION_RESUME_PROFILE}"
REDCAP_SESSION_RESUME_EVIDENCE="${REDCAP_SESSION_RESUME_EVIDENCE:-$PRE_INIT_SESSION_RESUME_EVIDENCE}"
REDCAP_SESSION_RESUME_ALLOW_DISK_RECOVERY="${REDCAP_SESSION_RESUME_ALLOW_DISK_RECOVERY:-$PRE_INIT_SESSION_RESUME_ALLOW_DISK_RECOVERY}"
REDCAP_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY="${REDCAP_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY:-$PRE_INIT_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY}"

if [[ "${REDCAP_SESSION_ISOLATION_MODE:-}" == "full" ]]; then
    REDCAP_SESSION_ISOLATION_MODE="degraded"
    REDCAP_SESSION_RESUME_REASON="runtime-init-failed"
    REDCAP_SESSION_RESUME_RECOVERY_PATH="safe-degraded"
    REDCAP_SESSION_RESUME_ALLOW_DISK_RECOVERY="0"
    REDCAP_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY="0"
fi

case "${REDCAP_SESSION_ISOLATION_MODE:-}" in
    degraded)
        redcap_runtime_record_degraded_mode \
            "$HOOK_CWD" \
            "layerB-session-start-safe-degraded" \
            "host=$HOST binding_key=${BINDING_KEY:-missing} gate_reason=${REDCAP_SESSION_RESUME_REASON:-unknown} gate_profile=${REDCAP_SESSION_RESUME_PROFILE:-unknown}" || true
        ;;
    unsupported)
        redcap_runtime_record_unsupported_mode \
            "$HOOK_CWD" \
            "layerB-session-start-unsupported" \
            "host=$HOST binding_key=${BINDING_KEY:-missing} gate_reason=${REDCAP_SESSION_RESUME_REASON:-unknown} gate_profile=${REDCAP_SESSION_RESUME_PROFILE:-unknown}" || true
        ;;
    *)
        RAW_ISOLATION_MODE="$REDCAP_SESSION_ISOLATION_MODE"
        REDCAP_SESSION_ISOLATION_MODE="degraded"
        REDCAP_SESSION_RESUME_REASON="unknown-isolation-mode"
        REDCAP_SESSION_RESUME_RECOVERY_PATH="safe-degraded"
        redcap_runtime_record_degraded_mode \
            "$HOOK_CWD" \
            "layerB-session-start-unknown-isolation-mode" \
            "host=$HOST raw_mode=${RAW_ISOLATION_MODE:-missing}" || true
        ;;
esac

ensure_repo_git_hooks
run_control_plane_start_sync

exit 0

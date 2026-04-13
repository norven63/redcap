#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap 框架 — Layer B SessionStart 统一入口
#
# 供 Claude InstructionsLoaded / Gemini SessionStart / Copilot sessionStart
# 复用。职责只有一个：捕获当前 HEAD，作为本次会话的基线。
# ─────────────────────────────────────────────────────────

set -u

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

if [[ -z "$BINDING_KEY" && -n "$HOST_SESSION_ID" ]]; then
    BINDING_KEY=$(redcap_runtime_binding_key_from_host_session "$HOST" "$HOST_SESSION_ID")
fi

run_control_plane_start_sync() {
    VALIDATOR_CHAIN="$SCRIPT_DIR/redcap-validator-chain.sh"
    PM_GATE_CHECK="$SCRIPT_DIR/redcap-pm-gate-check.sh"
    if [[ -x "$VALIDATOR_CHAIN" ]]; then
        REDCAP_RUNTIME_SESSION_ID="${REDCAP_RUNTIME_SESSION_ID:-}" \
        REDCAP_RUNTIME_CAPABILITY="${REDCAP_RUNTIME_CAPABILITY:-}" \
        REDCAP_HOST_PROCESS_PID="${REDCAP_HOST_PROCESS_PID:-$PPID}" \
        bash "$VALIDATOR_CHAIN" session-start "$HOST" "$REDCAP_ROOT/.dev-task.md" "" "" text >/dev/null || true
    elif [[ -x "$PM_GATE_CHECK" ]]; then
        REDCAP_RUNTIME_SESSION_ID="${REDCAP_RUNTIME_SESSION_ID:-}" \
        REDCAP_RUNTIME_CAPABILITY="${REDCAP_RUNTIME_CAPABILITY:-}" \
        REDCAP_HOST_PROCESS_PID="${REDCAP_HOST_PROCESS_PID:-$PPID}" \
        bash "$PM_GATE_CHECK" session-start "$HOST" "$REDCAP_ROOT/.dev-task.md" >/dev/null || true
    fi

    HOST_WORKBOARD_SYNC="$SCRIPT_DIR/redcap-host-workboard-sync.sh"
    if [[ -x "$HOST_WORKBOARD_SYNC" && -n "${REDCAP_HOST_WORKBOARD_PATH:-}" ]]; then
        bash "$HOST_WORKBOARD_SYNC" sync "$REDCAP_HOST_WORKBOARD_PATH" "$REDCAP_ROOT/.dev-task.md" 2>&1 || true
    fi

    SESSION_CONTINUITY="$SCRIPT_DIR/redcap-session-continuity.sh"
    if [[ -x "$SESSION_CONTINUITY" && -n "${REDCAP_HOST_WORKBOARD_PATH:-}" ]]; then
        bash "$SESSION_CONTINUITY" sync "$REDCAP_HOST_WORKBOARD_PATH" "$REDCAP_ROOT/.dev-task.md" 2>&1 || true
    fi
}

if [[ -n "$BINDING_KEY" ]] && REDCAP_RUNTIME_ALLOW_DISK_RECOVERY=1 REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY=1 redcap_runtime_init_from_binding "$HOST" "$HOOK_CWD" "$BINDING_KEY"; then
    if redcap_interop_pending_closure_exists "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md"; then
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
    run_control_plane_start_sync
    exit 0
fi

redcap_runtime_record_degraded_mode "$HOOK_CWD" "layerB-session-start-safe-degraded" "host=$HOST binding_key=${BINDING_KEY:-missing}" || true
run_control_plane_start_sync

exit 0

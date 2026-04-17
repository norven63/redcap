#!/usr/bin/env bash

set -u

SCRIPT_SOURCE="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REDCAP_ROOT/compass/tools/redcap-runtime-state.sh"

redcap_copilot_session_state_root() {
    printf '%s\n' "${REDCAP_COPILOT_SESSION_STATE_ROOT:-$HOME/.copilot/session-state}"
}

redcap_copilot_parent_pid() {
    local pid="${1:-}"

    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    ps -o ppid= -p "$pid" 2>/dev/null | tr -d '[:space:]'
}

redcap_copilot_candidate_pids() {
    local pid="${REDCAP_HOST_PROCESS_PID:-$PPID}"
    local depth=0
    local seen=""

    while [[ -n "$pid" && "$pid" =~ ^[0-9]+$ && "$pid" -gt 1 && "$depth" -lt 12 ]]; do
        case " $seen " in
            *" $pid "*) ;;
            *)
                printf '%s\n' "$pid"
                seen="$seen $pid"
                ;;
        esac
        pid="$(redcap_copilot_parent_pid "$pid")"
        depth=$((depth + 1))
    done

    if [[ -n "${COPILOT_LOADER_PID:-}" && "${COPILOT_LOADER_PID:-}" =~ ^[0-9]+$ ]]; then
        case " $seen " in
            *" ${COPILOT_LOADER_PID} "*) ;;
            *) printf '%s\n' "$COPILOT_LOADER_PID" ;;
        esac
    fi
}

redcap_copilot_find_session_context() {
    local session_root
    local pid=""
    local lock_path=""
    local session_dir=""
    local session_handle=""
    local plan_path=""
    local recorded_pid=""
    local matched_context=""
    local matched_count=0

    session_root="$(redcap_copilot_session_state_root)"
    [[ -d "$session_root" ]] || return 1

    while IFS= read -r pid; do
        local candidates=()

        [[ "$pid" =~ ^[0-9]+$ ]] || continue
        kill -0 "$pid" 2>/dev/null || continue
        matched_context=""
        matched_count=0

        shopt -s nullglob
        candidates=("$session_root"/*/inuse."$pid".lock)
        shopt -u nullglob

        [[ "${#candidates[@]}" -gt 0 ]] || continue

        for lock_path in "${candidates[@]}"; do
            recorded_pid="$(tr -d '[:space:]' <"$lock_path" 2>/dev/null || true)"
            [[ "$recorded_pid" == "$pid" ]] || continue

            session_dir="$(dirname "$lock_path")"
            session_handle="$(basename "$session_dir")"
            plan_path="$session_dir/plan.md"
            matched_context=$(printf '%s\t%s\t%s\t%s' "$pid" "$session_handle" "$session_dir" "$plan_path")
            matched_count=$((matched_count + 1))
        done

        if [[ "$matched_count" -gt 1 ]]; then
            return 2
        fi
        if [[ "$matched_count" -eq 1 ]]; then
            printf '%s\n' "$matched_context"
            return 0
        fi
    done < <(redcap_copilot_candidate_pids)

    return 1
}

redcap_copilot_apply_session_context() {
    local context=""
    local matched_pid=""
    local session_handle=""
    local session_dir=""
    local plan_path=""
    local binding_key=""

    context="$(redcap_copilot_find_session_context)" || return 1
    IFS=$'\t' read -r matched_pid session_handle session_dir plan_path <<EOF
$context
EOF

    [[ -n "$session_handle" ]] || return 1
    binding_key="$(redcap_runtime_binding_key_from_host_session copilot "$session_handle")" || return 1

    export REDCAP_HOST_PROCESS_PID="$matched_pid"
    export REDCAP_COPILOT_SESSION_HANDLE="$session_handle"
    export REDCAP_COPILOT_SESSION_SOURCE="session-state-inuse-lock"

    if [[ -z "${REDCAP_HOST_SESSION_ID:-}" ]]; then
        export REDCAP_HOST_SESSION_ID="$session_handle"
    fi

    if [[ -z "${REDCAP_SESSION_BINDING_KEY:-}" ]]; then
        export REDCAP_SESSION_BINDING_KEY="$binding_key"
    fi

    if [[ -z "${REDCAP_HOST_WORKBOARD_PATH:-}" && -f "$plan_path" ]]; then
        export REDCAP_HOST_WORKBOARD_PATH="$plan_path"
    fi

    return 0
}

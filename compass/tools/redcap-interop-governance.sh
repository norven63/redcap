#!/usr/bin/env bash
# shellcheck shell=bash
#
# Shared governance helpers for host/native interop.
# This layer does not replace .dev-task.md as canonical truth. It only:
# 1. records evidence-only interop/closure audit events under project-shared state
# 2. stores derived closure obligations keyed by canonical task identity
# 3. provides common fail-closed checks that later entrypoints can reuse

if [[ "${_REDCAP_INTEROP_GOVERNANCE_SH:-0}" == "1" ]]; then
    return 0 2>/dev/null || exit 0
fi
_REDCAP_INTEROP_GOVERNANCE_SH=1

_redcap_interop_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$_redcap_interop_script_dir/redcap-runtime-state.sh"
source "$_redcap_interop_script_dir/redcap-dev-task.sh"

redcap_interop_governance_dir_for_root() {
    local project_root="$1"

    project_root=$(redcap_runtime_project_root "$project_root")
    printf '%s\n' "$(redcap_runtime_project_path_for_root "$project_root" "governance")"
}

redcap_interop_audit_dir_for_root() {
    local project_root="$1"

    printf '%s\n' "$(redcap_interop_governance_dir_for_root "$project_root")/audit"
}

redcap_interop_pending_closure_dir_for_root() {
    local project_root="$1"

    printf '%s\n' "$(redcap_interop_governance_dir_for_root "$project_root")/pending-closure"
}

redcap_interop_closure_ledger_dir_for_root() {
    local project_root="$1"

    printf '%s\n' "$(redcap_interop_governance_dir_for_root "$project_root")/closure-ledger"
}

redcap_interop_closure_ledger_file_for_identity() {
    local project_root="$1"
    local task_id="$2"
    local confirmed_hash="$3"

    if ! redcap_dev_task_validate_path_component "$task_id"; then
        return 1
    fi

    if [[ -z "$confirmed_hash" ]]; then
        return 1
    fi

    printf '%s/%s-%s.log\n' "$(redcap_interop_closure_ledger_dir_for_root "$project_root")" "$task_id" "$confirmed_hash"
}

redcap_interop_closure_ledger_file() {
    local project_root="$1"
    local task_file="${2:-}"
    local task_id confirmed_hash

    task_file=$(redcap_dev_task_resolve_file "$task_file")
    task_id=$(redcap_dev_task_extract_kv "$task_file" "task_id" 2>/dev/null || true)
    confirmed_hash=$(redcap_dev_task_confirmed_hash "$task_file" 2>/dev/null || true)

    redcap_interop_closure_ledger_file_for_identity "$project_root" "$task_id" "$confirmed_hash"
}

redcap_interop_append_closure_ledger_identity() {
    local project_root="$1"
    local task_id="$2"
    local confirmed_hash="$3"
    local active_slice="$4"
    local phase="$5"
    local status="$6"
    local detail="${7:-}"
    local host="${8:-}"
    local trigger="${9:-}"
    local baseline_head="${10:-}"
    local current_head="${11:-}"
    local artifact_path="${12:-}"
    local ledger_file ledger_dir now

    if [[ -z "$project_root" || -z "$task_id" || -z "$confirmed_hash" || -z "$phase" || -z "$status" ]]; then
        return 1
    fi

    project_root=$(redcap_runtime_project_root "$project_root")
    ledger_file=$(redcap_interop_closure_ledger_file_for_identity "$project_root" "$task_id" "$confirmed_hash") || return 1
    ledger_dir=$(dirname "$ledger_file")
    now=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    mkdir -p "$ledger_dir" || return 1

    detail=$(printf '%s' "$detail" | tr '\n' ' ')
    host=$(printf '%s' "$host" | tr '\n' ' ')
    trigger=$(printf '%s' "$trigger" | tr '\n' ' ')
    baseline_head=$(printf '%s' "$baseline_head" | tr '\n' ' ')
    current_head=$(printf '%s' "$current_head" | tr '\n' ' ')
    artifact_path=$(printf '%s' "$artifact_path" | tr '\n' ' ')

    if [[ ! -f "$ledger_file" ]]; then
        cat > "$ledger_file" <<EOF
# RedCap Closure Ledger
task_id: $task_id
confirmed_hash: $confirmed_hash
EOF
    fi

    cat >> "$ledger_file" <<EOF
---
timestamp: $now
phase: $phase
status: $status
task_id: $task_id
confirmed_hash: $confirmed_hash
active_slice: $active_slice
host: $host
trigger: $trigger
baseline_head: $baseline_head
current_head: $current_head
artifact_path: $artifact_path
detail: $detail
EOF
}

redcap_interop_append_closure_ledger() {
    local project_root="$1"
    local task_file="$2"
    local phase="$3"
    local status="$4"
    local detail="${5:-}"
    local host="${6:-}"
    local trigger="${7:-}"
    local baseline_head="${8:-}"
    local current_head="${9:-}"
    local artifact_path="${10:-}"
    local task_id confirmed_hash active_slice

    if [[ -z "$project_root" || -z "$task_file" || -z "$phase" || -z "$status" ]]; then
        return 1
    fi

    task_file=$(redcap_dev_task_resolve_file "$task_file")
    task_id=$(redcap_dev_task_extract_kv "$task_file" "task_id" 2>/dev/null || true)
    confirmed_hash=$(redcap_dev_task_confirmed_hash "$task_file" 2>/dev/null || true)
    active_slice=$(redcap_dev_task_extract_kv "$task_file" "active_slice" 2>/dev/null || true)

    redcap_interop_append_closure_ledger_identity \
        "$project_root" \
        "$task_id" \
        "$confirmed_hash" \
        "$active_slice" \
        "$phase" \
        "$status" \
        "$detail" \
        "$host" \
        "$trigger" \
        "$baseline_head" \
        "$current_head" \
        "$artifact_path"
}

redcap_interop_record_audit_event() {
    local project_root="$1"
    local category="$2"
    local event="$3"
    local detail="${4:-}"
    local audit_dir

    if [[ -z "$project_root" || -z "$category" || -z "$event" ]]; then
        return 1
    fi

    project_root=$(redcap_runtime_project_root "$project_root")
    audit_dir=$(redcap_interop_audit_dir_for_root "$project_root")
    mkdir -p "$audit_dir" || return 1

    redcap_runtime_increment_counter_file "$audit_dir/${category}.count"
    redcap_runtime_append_event_log "$audit_dir/${category}.log" "$event" "$detail"
}

redcap_interop_record_boundary_violation() {
    redcap_interop_record_audit_event "$1" "interop-violation" "$2" "${3:-}"
}

redcap_interop_record_reanchor_event() {
    redcap_interop_record_audit_event "$1" "reanchor" "$2" "${3:-}"
}

redcap_interop_record_closure_event() {
    redcap_interop_record_audit_event "$1" "closure" "$2" "${3:-}"
}

redcap_interop_task_key() {
    local task_file="${1:-}"
    local task_id confirmed_hash

    task_file=$(redcap_dev_task_resolve_file "$task_file")
    task_id=$(redcap_dev_task_extract_kv "$task_file" "task_id" 2>/dev/null || true)
    confirmed_hash=$(redcap_dev_task_confirmed_hash "$task_file" 2>/dev/null || true)

    if ! redcap_dev_task_validate_path_component "$task_id"; then
        return 1
    fi

    if [[ -z "$task_id" || -z "$confirmed_hash" ]]; then
        return 1
    fi

    printf '%s-%s\n' "$task_id" "$confirmed_hash"
}

redcap_interop_pending_closure_current_file() {
    local project_root="$1"
    local task_file="${2:-}"
    local task_key

    task_key=$(redcap_interop_task_key "$task_file") || return 1
    printf '%s/%s.state\n' "$(redcap_interop_pending_closure_dir_for_root "$project_root")" "$task_key"
}

redcap_interop_pending_closure_existing_file() {
    local project_root="$1"
    local task_file="${2:-}"
    local task_id pending_dir oldest_match=""
    local matches=()

    task_file=$(redcap_dev_task_resolve_file "$task_file")
    task_id=$(redcap_dev_task_extract_kv "$task_file" "task_id" 2>/dev/null || true)
    if ! redcap_dev_task_validate_path_component "$task_id"; then
        return 1
    fi

    pending_dir=$(redcap_interop_pending_closure_dir_for_root "$project_root")
    shopt -s nullglob
    matches=("$pending_dir/$task_id"-*.state)
    shopt -u nullglob

    if [[ ${#matches[@]} -eq 0 ]]; then
        return 1
    fi

    oldest_match=$(ls -1tr "${matches[@]}" 2>/dev/null | head -1)
    [[ -n "$oldest_match" ]] || return 1
    printf '%s\n' "$oldest_match"
}

redcap_interop_pending_closure_file() {
    local project_root="$1"
    local task_file="${2:-}"
    local existing_file

    existing_file=$(redcap_interop_pending_closure_existing_file "$project_root" "$task_file" 2>/dev/null || true)
    if [[ -n "$existing_file" ]]; then
        printf '%s\n' "$existing_file"
        return 0
    fi

    redcap_interop_pending_closure_current_file "$project_root" "$task_file"
}

redcap_interop_pending_closure_lock_path() {
    local project_root="$1"
    local task_file="${2:-}"
    local task_id

    task_file=$(redcap_dev_task_resolve_file "$task_file")
    task_id=$(redcap_dev_task_extract_kv "$task_file" "task_id" 2>/dev/null || true)
    if ! redcap_dev_task_validate_path_component "$task_id"; then
        return 1
    fi

    printf '%s/.locks/%s.lock\n' "$(redcap_interop_governance_dir_for_root "$project_root")" "$task_id"
}

redcap_interop_pending_closure_lock_owner_pid() {
    local lock_path="$1"

    awk -F '\t' 'NR == 1 { print $1 }' "$lock_path" 2>/dev/null
}

redcap_interop_release_pending_closure_lock_path() {
    local lock_path="$1"

    rm -f "$lock_path" 2>/dev/null || return 1
}

redcap_interop_prune_stale_pending_closure_lock() {
    local lock_path="$1"
    local owner_pid=""

    if [[ ! -f "$lock_path" ]]; then
        return 0
    fi

    owner_pid=$(redcap_interop_pending_closure_lock_owner_pid "$lock_path" 2>/dev/null || true)
    if [[ -n "$owner_pid" ]] && kill -0 "$owner_pid" 2>/dev/null; then
        return 1
    fi

    redcap_interop_release_pending_closure_lock_path "$lock_path"
}

redcap_interop_acquire_pending_closure_lock() {
    local project_root="$1"
    local task_file="${2:-}"
    local lock_path lock_tmp lock_dir attempts=0 created_at

    lock_path=$(redcap_interop_pending_closure_lock_path "$project_root" "$task_file") || return 1
    lock_dir=$(dirname "$lock_path")
    lock_tmp="$lock_path.$$.$RANDOM.tmp"
    created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    mkdir -p "$lock_dir" || return 1
    chmod 700 "$lock_dir" 2>/dev/null || return 1
    printf '%s\t%s\n' "$$" "$created_at" > "$lock_tmp" || return 1
    chmod 600 "$lock_tmp" 2>/dev/null || {
        rm -f "$lock_tmp" 2>/dev/null || true
        return 1
    }

    while ! ln "$lock_tmp" "$lock_path" 2>/dev/null; do
        redcap_interop_prune_stale_pending_closure_lock "$lock_path" || true
        attempts=$((attempts + 1))
        if [[ "$attempts" -ge 200 ]]; then
            rm -f "$lock_tmp" 2>/dev/null || true
            return 1
        fi
        sleep 0.05
    done

    rm -f "$lock_tmp" 2>/dev/null || true
}

redcap_interop_release_pending_closure_lock() {
    local project_root="$1"
    local task_file="${2:-}"
    local lock_path

    lock_path=$(redcap_interop_pending_closure_lock_path "$project_root" "$task_file") || return 1
    redcap_interop_release_pending_closure_lock_path "$lock_path"
}

redcap_interop_read_state_field() {
    local state_file="$1"
    local key="$2"

    python3 - "$state_file" "$key" <<'PY'
import pathlib
import re
import sys

state_file = pathlib.Path(sys.argv[1])
key = sys.argv[2]
if not state_file.is_file():
    sys.exit(1)

text = state_file.read_text(encoding="utf-8")
match = re.search(rf"^{re.escape(key)}:\s*(.*?)\s*$", text, re.MULTILINE)
if match:
    print(match.group(1))
PY
}

redcap_interop_pending_closure_exists() {
    local project_root="$1"
    local task_file="${2:-}"
    local state_file

    state_file=$(redcap_interop_pending_closure_existing_file "$project_root" "$task_file" 2>/dev/null || true)
    [[ -n "$state_file" && -f "$state_file" ]]
}

redcap_interop_write_pending_closure() {
    local project_root="$1"
    local task_file="$2"
    local host="$3"
    local trigger="$4"
    local required_redlines="${5:-}"
    local detail="${6:-}"
    local artifact_path="${7:-}"
    local baseline_head="${8:-}"
    local audited_head="${9:-}"
    local task_id top_goal active_slice confirmed_hash state_file state_dir now created_at existing_artifact_path
    local existing_required_redlines existing_baseline_head existing_audited_head existing_confirmed_hash existing_active_slice existing_top_goal item merged_required_redlines=""

    if [[ -z "$project_root" || -z "$task_file" || -z "$host" || -z "$trigger" ]]; then
        return 1
    fi

    project_root=$(redcap_runtime_project_root "$project_root")
    task_file=$(redcap_dev_task_resolve_file "$task_file")
    redcap_interop_acquire_pending_closure_lock "$project_root" "$task_file" || return 1
    (
        trap 'redcap_interop_release_pending_closure_lock "'"$project_root"'" "'"$task_file"'" >/dev/null 2>&1 || true' EXIT
        task_id=$(redcap_dev_task_extract_kv "$task_file" "task_id" 2>/dev/null || true)
        top_goal=$(redcap_dev_task_extract_kv "$task_file" "top_goal" 2>/dev/null || true)
        active_slice=$(redcap_dev_task_extract_kv "$task_file" "active_slice" 2>/dev/null || true)
        confirmed_hash=$(redcap_dev_task_confirmed_hash "$task_file" 2>/dev/null || true)

        if [[ -z "$task_id" || -z "$top_goal" || -z "$active_slice" || -z "$confirmed_hash" ]]; then
            exit 1
        fi

        detail=$(printf '%s' "$detail" | tr '\n' ' ')
        required_redlines=$(printf '%s' "$required_redlines" | tr '\n' ' ')
        artifact_path=$(printf '%s' "$artifact_path" | tr '\n' ' ')
        baseline_head=$(printf '%s' "$baseline_head" | tr '\n' ' ')
        audited_head=$(printf '%s' "$audited_head" | tr '\n' ' ')
        now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
        state_file=$(redcap_interop_pending_closure_existing_file "$project_root" "$task_file" 2>/dev/null || true)
        if [[ -z "$state_file" ]]; then
            state_file=$(redcap_interop_pending_closure_current_file "$project_root" "$task_file")
        fi
        state_dir=$(dirname "$state_file")
        mkdir -p "$state_dir" || exit 1

        created_at=$(redcap_interop_read_state_field "$state_file" "created_at" 2>/dev/null || true)
        [[ -n "$created_at" ]] || created_at="$now"
        existing_required_redlines=$(redcap_interop_read_state_field "$state_file" "required_redlines" 2>/dev/null || true)
        existing_confirmed_hash=$(redcap_interop_read_state_field "$state_file" "confirmed_hash" 2>/dev/null || true)
        existing_active_slice=$(redcap_interop_read_state_field "$state_file" "active_slice" 2>/dev/null || true)
        existing_top_goal=$(redcap_interop_read_state_field "$state_file" "top_goal" 2>/dev/null || true)
        for item in ${existing_required_redlines//,/ } ${required_redlines//,/ }; do
            item=$(printf '%s' "$item" | tr -d '[:space:]')
            [[ -n "$item" ]] || continue
            case ",$merged_required_redlines," in
                *,"$item",*) ;;
                *)
                    if [[ -z "$merged_required_redlines" ]]; then
                        merged_required_redlines="$item"
                    else
                        merged_required_redlines="${merged_required_redlines},$item"
                    fi
                    ;;
            esac
        done
        required_redlines="$merged_required_redlines"
        if [[ -n "$existing_confirmed_hash" ]]; then
            confirmed_hash="$existing_confirmed_hash"
        fi
        if [[ -n "$existing_active_slice" ]]; then
            active_slice="$existing_active_slice"
        fi
        if [[ -n "$existing_top_goal" ]]; then
            top_goal="$existing_top_goal"
        fi
        if [[ -z "$artifact_path" ]]; then
            existing_artifact_path=$(redcap_interop_read_state_field "$state_file" "artifact_path" 2>/dev/null || true)
            artifact_path="$existing_artifact_path"
        fi
        existing_baseline_head=$(redcap_interop_read_state_field "$state_file" "baseline_head" 2>/dev/null || true)
        existing_audited_head=$(redcap_interop_read_state_field "$state_file" "audited_head" 2>/dev/null || true)
        if [[ -n "$existing_baseline_head" ]]; then
            baseline_head="$existing_baseline_head"
        fi
        if [[ -n "$existing_audited_head" ]]; then
            audited_head="$existing_audited_head"
        fi

        cat > "$state_file" <<EOF
task_id: $task_id
confirmed_hash: $confirmed_hash
top_goal: $top_goal
active_slice: $active_slice
host: $host
trigger: $trigger
required_redlines: $required_redlines
artifact_path: $artifact_path
baseline_head: $baseline_head
audited_head: $audited_head
detail: $detail
status: pending
created_at: $created_at
updated_at: $now
EOF

        redcap_interop_record_closure_event \
            "$project_root" \
            "pending-closure-created" \
            "task_id=$task_id host=$host trigger=$trigger confirmed_hash=$confirmed_hash required_redlines=$required_redlines artifact_path=$artifact_path baseline_head=$baseline_head audited_head=$audited_head detail=$detail"
        redcap_interop_append_closure_ledger_identity \
            "$project_root" \
            "$task_id" \
            "$confirmed_hash" \
            "$active_slice" \
            "obligation" \
            "pending" \
            "required_redlines=$required_redlines detail=$detail" \
            "$host" \
            "$trigger" \
            "$baseline_head" \
            "$audited_head" \
            "$artifact_path" \
            >/dev/null 2>&1 || true

        printf '%s\n' "$state_file"
    )
}

redcap_interop_clear_pending_closure() {
    local project_root="$1"
    local task_file="$2"
    local outcome="${3:-done}"
    local detail="${4:-}"
    local expected_updated_at="${5:-}"
    local state_file host trigger baseline_head audited_head artifact_path task_id confirmed_hash active_slice

    if [[ -z "$project_root" || -z "$task_file" ]]; then
        return 1
    fi

    project_root=$(redcap_runtime_project_root "$project_root")
    task_file=$(redcap_dev_task_resolve_file "$task_file")
    redcap_interop_acquire_pending_closure_lock "$project_root" "$task_file" || return 1
    (
        local current_updated_at=""
        trap 'redcap_interop_release_pending_closure_lock "'"$project_root"'" "'"$task_file"'" >/dev/null 2>&1 || true' EXIT
        state_file=$(redcap_interop_pending_closure_existing_file "$project_root" "$task_file" 2>/dev/null || true)
        if [[ -z "$state_file" || ! -f "$state_file" ]]; then
            exit 1
        fi

        current_updated_at=$(redcap_interop_read_state_field "$state_file" "updated_at" 2>/dev/null || true)
        if [[ -n "$expected_updated_at" && "$current_updated_at" != "$expected_updated_at" ]]; then
            exit 1
        fi

        host=$(redcap_interop_read_state_field "$state_file" "host" 2>/dev/null || true)
        trigger=$(redcap_interop_read_state_field "$state_file" "trigger" 2>/dev/null || true)
        baseline_head=$(redcap_interop_read_state_field "$state_file" "baseline_head" 2>/dev/null || true)
        audited_head=$(redcap_interop_read_state_field "$state_file" "audited_head" 2>/dev/null || true)
        artifact_path=$(redcap_interop_read_state_field "$state_file" "artifact_path" 2>/dev/null || true)
        task_id=$(redcap_interop_read_state_field "$state_file" "task_id" 2>/dev/null || true)
        confirmed_hash=$(redcap_interop_read_state_field "$state_file" "confirmed_hash" 2>/dev/null || true)
        active_slice=$(redcap_interop_read_state_field "$state_file" "active_slice" 2>/dev/null || true)
        detail=$(printf '%s' "$detail" | tr '\n' ' ')
        rm -f "$state_file" || exit 1

        redcap_interop_record_closure_event \
            "$project_root" \
            "pending-closure-cleared" \
            "task=$(basename "$state_file") outcome=$outcome detail=$detail"
        redcap_interop_append_closure_ledger_identity \
            "$project_root" \
            "$task_id" \
            "$confirmed_hash" \
            "$active_slice" \
            "obligation" \
            "cleared" \
            "outcome=$outcome detail=$detail" \
            "$host" \
            "$trigger" \
            "$baseline_head" \
            "$audited_head" \
            "$artifact_path" \
            >/dev/null 2>&1 || redcap_interop_append_closure_ledger \
            "$project_root" \
            "$task_file" \
            "obligation" \
            "cleared" \
            "outcome=$outcome detail=$detail" \
            "$host" \
            "$trigger" \
            "$baseline_head" \
            "$audited_head" \
            "$artifact_path" \
            >/dev/null 2>&1 || true
    )
}

redcap_interop_require_no_pending_closure() {
    local project_root="$1"
    local task_file="$2"
    local host="$3"
    local trigger="$4"
    local detail="${5:-}"
    local state_file pending_host pending_trigger required_redlines pending_task_id pending_confirmed_hash pending_active_slice

    if [[ -z "$project_root" || -z "$task_file" || -z "$host" || -z "$trigger" ]]; then
        return 1
    fi

    project_root=$(redcap_runtime_project_root "$project_root")
    state_file=$(redcap_interop_pending_closure_existing_file "$project_root" "$task_file" 2>/dev/null || true)
    if [[ -z "$state_file" || ! -f "$state_file" ]]; then
        redcap_interop_record_reanchor_event \
            "$project_root" \
            "no-pending-closure" \
            "host=$host trigger=$trigger detail=$detail" \
            >/dev/null 2>&1 || true
        return 0
    fi

    pending_host=$(redcap_interop_read_state_field "$state_file" "host" 2>/dev/null || true)
    pending_trigger=$(redcap_interop_read_state_field "$state_file" "trigger" 2>/dev/null || true)
    required_redlines=$(redcap_interop_read_state_field "$state_file" "required_redlines" 2>/dev/null || true)
    pending_task_id=$(redcap_interop_read_state_field "$state_file" "task_id" 2>/dev/null || true)
    pending_confirmed_hash=$(redcap_interop_read_state_field "$state_file" "confirmed_hash" 2>/dev/null || true)
    pending_active_slice=$(redcap_interop_read_state_field "$state_file" "active_slice" 2>/dev/null || true)

    redcap_interop_record_closure_event \
        "$project_root" \
        "pending-closure-blocked" \
        "host=$host trigger=$trigger pending_host=$pending_host pending_trigger=$pending_trigger required_redlines=$required_redlines detail=$detail" \
        >/dev/null 2>&1 || true
    redcap_interop_append_closure_ledger_identity \
        "$project_root" \
        "$pending_task_id" \
        "$pending_confirmed_hash" \
        "$pending_active_slice" \
        "obligation" \
        "blocked" \
        "pending_host=$pending_host pending_trigger=$pending_trigger required_redlines=$required_redlines detail=$detail" \
        "$host" \
        "$trigger" \
        "" \
        "" \
        "" \
        >/dev/null 2>&1 || redcap_interop_append_closure_ledger \
        "$project_root" \
        "$task_file" \
        "obligation" \
        "blocked" \
        "pending_host=$pending_host pending_trigger=$pending_trigger required_redlines=$required_redlines detail=$detail" \
        "$host" \
        "$trigger" \
        "" \
        "" \
        "" \
        >/dev/null 2>&1 || true

    echo "[redcap-interop-governance] unresolved pending closure blocks RedCap-owned state" >&2
    echo "  pending_host: ${pending_host:-unknown}" >&2
    echo "  pending_trigger: ${pending_trigger:-unknown}" >&2
    echo "  required_redlines: ${required_redlines:-unknown}" >&2
    return 1
}

redcap_interop_fail_closed() {
    local project_root="$1"
    local category="$2"
    local event="$3"
    local message="$4"
    local detail="${5:-}"

    case "$category" in
        boundary)
            redcap_interop_record_boundary_violation "$project_root" "$event" "$detail" >/dev/null 2>&1 || true
            ;;
        closure)
            redcap_interop_record_closure_event "$project_root" "$event" "$detail" >/dev/null 2>&1 || true
            ;;
        reanchor)
            redcap_interop_record_reanchor_event "$project_root" "$event" "$detail" >/dev/null 2>&1 || true
            ;;
        *)
            redcap_interop_record_audit_event "$project_root" "$category" "$event" "$detail" >/dev/null 2>&1 || true
            ;;
    esac

    echo "[redcap-interop-governance] $message" >&2
    return 1
}

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

redcap_interop_pending_closure_matching_files() {
    local project_root="$1"
    local task_file="${2:-}"
    local task_id pending_dir
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

    [[ ${#matches[@]} -gt 0 ]] || return 1
    printf '%s\n' "${matches[@]}"
}

redcap_interop_normalize_redlines() {
    local raw="${1:-}"
    local item normalized=""

    for item in ${raw//,/ }; do
        item=$(printf '%s' "$item" | tr -d '[:space:]')
        [[ -n "$item" ]] || continue
        case ",$normalized," in
            *,"$item",*) ;;
            *)
                if [[ -z "$normalized" ]]; then
                    normalized="$item"
                else
                    normalized="${normalized},$item"
                fi
                ;;
        esac
    done

    printf '%s\n' "$normalized"
}

redcap_interop_pending_closure_existing_file() {
    local project_root="$1"
    local task_file="${2:-}"
    local current_file=""
    local task_id pending_dir newest_match=""
    local matches=()

    current_file=$(redcap_interop_pending_closure_current_file "$project_root" "$task_file" 2>/dev/null || true)
    if [[ -n "$current_file" && -f "$current_file" ]]; then
        printf '%s\n' "$current_file"
        return 0
    fi

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

    newest_match=$(ls -1t "${matches[@]}" 2>/dev/null | head -1)
    [[ -n "$newest_match" ]] || return 1
    printf '%s\n' "$newest_match"
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

redcap_interop_resolve_report_abs_path() {
    local project_root="$1"
    local input_path="$2"

    python3 - "$project_root" "$input_path" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
raw = sys.argv[2]
report_roots_raw = [
    root / "assets/docs/task-reports",
    root / "compass/docs/task-reports",
]
report_roots = []
for report_root in report_roots_raw:
    if report_root.is_dir():
        resolved = report_root.resolve()
        if root == resolved or resolved.is_relative_to(root):
            report_roots.append(resolved)
if not report_roots:
    raise SystemExit(1)

candidate_raw = Path(raw)
if not candidate_raw.is_absolute():
    candidate_raw = root / candidate_raw
if candidate_raw.is_symlink():
    raise SystemExit(1)

candidate = candidate_raw.resolve()

if not any(_root == candidate or candidate.is_relative_to(_root) for _root in report_roots):
    raise SystemExit(1)

if candidate.suffix != ".md" or not candidate.is_file():
    raise SystemExit(1)

print(candidate)
PY
}

redcap_interop_resolve_report_rel_path() {
    local project_root="$1"
    local input_path="$2"
    local abs_path=""

    abs_path=$(redcap_interop_resolve_report_abs_path "$project_root" "$input_path") || return 1
    python3 - "$project_root" "$abs_path" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
abs_path = Path(sys.argv[2]).resolve()
print(abs_path.relative_to(root).as_posix())
PY
}

redcap_interop_current_report_marker_path() {
    redcap_runtime_path "layerB/current-report-path" 2>/dev/null
}

redcap_interop_current_report_identity_path() {
    redcap_runtime_path "layerB/current-report-identity" 2>/dev/null
}

redcap_interop_write_current_report_marker() {
    local report_path="$1"
    local task_file="${2:-}"
    local identity_path task_id confirmed_hash active_slice now
    local project_root report_rel

    [[ -n "$report_path" ]] || return 1

    task_file=$(redcap_dev_task_resolve_file "$task_file")
    project_root=$(redcap_runtime_project_root "$(dirname "$task_file")")
    report_rel=$(redcap_interop_resolve_report_rel_path "$project_root" "$report_path") || return 1
    task_id=$(redcap_dev_task_extract_kv "$task_file" "task_id" 2>/dev/null || true)
    confirmed_hash=$(redcap_dev_task_confirmed_hash "$task_file" 2>/dev/null || true)
    active_slice=$(redcap_dev_task_extract_kv "$task_file" "active_slice" 2>/dev/null || true)
    [[ -n "$task_id" && -n "$confirmed_hash" && -n "$active_slice" ]] || return 1

    redcap_runtime_write_text "layerB/current-report-path" "$report_rel" || return 1
    identity_path=$(redcap_interop_current_report_identity_path) || return 1
    [[ -n "$identity_path" ]] || return 1
    now=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    cat > "$identity_path" <<EOF
report_path: $report_rel
task_id: $task_id
confirmed_hash: $confirmed_hash
active_slice: $active_slice
updated_at: $now
EOF
}

redcap_interop_clear_current_report_marker() {
    redcap_runtime_remove_path "layerB/current-report-path" >/dev/null 2>&1 || true
    redcap_runtime_remove_path "layerB/current-report-identity" >/dev/null 2>&1 || true
}

redcap_interop_current_report_marker_rel() {
    local project_root="$1"
    local task_file="${2:-}"
    local marker_path="" marker_rel="" identity_path=""
    local current_task_id="" current_confirmed_hash="" current_active_slice=""
    local identity_report_path="" identity_task_id="" identity_confirmed_hash="" identity_active_slice=""
    local pending_state="" pending_report_path="" pending_task_id="" pending_confirmed_hash=""

    project_root=$(redcap_runtime_project_root "$project_root")
    task_file=$(redcap_dev_task_resolve_file "$task_file")
    marker_path=$(redcap_interop_current_report_marker_path 2>/dev/null || true)
    [[ -n "$marker_path" && -f "$marker_path" ]] || return 1
    marker_rel=$(cat "$marker_path" 2>/dev/null || true)
    marker_rel=$(redcap_interop_resolve_report_rel_path "$project_root" "$marker_rel" 2>/dev/null || true)
    [[ -n "$marker_rel" ]] || return 1

    current_task_id=$(redcap_dev_task_extract_kv "$task_file" "task_id" 2>/dev/null || true)
    current_confirmed_hash=$(redcap_dev_task_confirmed_hash "$task_file" 2>/dev/null || true)
    current_active_slice=$(redcap_dev_task_extract_kv "$task_file" "active_slice" 2>/dev/null || true)
    [[ -n "$current_task_id" && -n "$current_confirmed_hash" ]] || return 1

    identity_path=$(redcap_interop_current_report_identity_path 2>/dev/null || true)
    if [[ -n "$identity_path" && -f "$identity_path" ]]; then
        identity_report_path=$(redcap_interop_read_state_field "$identity_path" "report_path" 2>/dev/null || true)
        identity_task_id=$(redcap_interop_read_state_field "$identity_path" "task_id" 2>/dev/null || true)
        identity_confirmed_hash=$(redcap_interop_read_state_field "$identity_path" "confirmed_hash" 2>/dev/null || true)
        identity_active_slice=$(redcap_interop_read_state_field "$identity_path" "active_slice" 2>/dev/null || true)
        if [[ "$identity_report_path" == "$marker_rel" && \
              "$identity_task_id" == "$current_task_id" && \
              "$identity_confirmed_hash" == "$current_confirmed_hash" ]]; then
            if [[ -z "$identity_active_slice" || -z "$current_active_slice" || "$identity_active_slice" == "$current_active_slice" ]]; then
                printf '%s\n' "$marker_rel"
                return 0
            fi
        fi
    fi

    pending_state=$(redcap_interop_pending_closure_existing_file "$project_root" "$task_file" 2>/dev/null || true)
    if [[ -n "$pending_state" && -f "$pending_state" ]]; then
        pending_report_path=$(redcap_interop_read_state_field "$pending_state" "artifact_path" 2>/dev/null || true)
        pending_report_path=$(redcap_interop_resolve_report_rel_path "$project_root" "$pending_report_path" 2>/dev/null || true)
        pending_task_id=$(redcap_interop_read_state_field "$pending_state" "task_id" 2>/dev/null || true)
        pending_confirmed_hash=$(redcap_interop_read_state_field "$pending_state" "confirmed_hash" 2>/dev/null || true)
        if [[ "$pending_report_path" == "$marker_rel" && \
              "$pending_task_id" == "$current_task_id" && \
              "$pending_confirmed_hash" == "$current_confirmed_hash" ]]; then
            printf '%s\n' "$marker_rel"
            return 0
        fi
    fi

    return 1
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

redcap_interop_lock_owner_started_at() {
    local lock_path="$1"

    awk -F '\t' 'NR == 1 { print $2 }' "$lock_path" 2>/dev/null
}

redcap_interop_lock_field_is_legacy_created_at() {
    local value="${1:-}"

    [[ "$value" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

redcap_interop_legacy_lock_grace_seconds() {
    printf '%s\n' "${REDCAP_LEGACY_LOCK_GRACE_SECONDS:-600}"
}

redcap_interop_legacy_lock_within_grace() {
    local created_at="${1:-}"
    local grace_seconds=""

    grace_seconds=$(redcap_interop_legacy_lock_grace_seconds)
    python3 - "$created_at" "$grace_seconds" <<'PY'
from datetime import datetime, timezone
import sys

created_at = sys.argv[1]
grace_seconds = int(sys.argv[2])

try:
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
except ValueError:
    raise SystemExit(1)

age = (datetime.now(timezone.utc) - created).total_seconds()
raise SystemExit(0 if age <= grace_seconds else 1)
PY
}

redcap_interop_process_started_before_timestamp() {
    local process_started_at="${1:-}"
    local created_at="${2:-}"

    python3 - "$process_started_at" "$created_at" <<'PY'
from datetime import datetime
import sys

process_started_at = sys.argv[1]
created_at = sys.argv[2]

try:
    started = datetime.strptime(process_started_at, "%a %b %d %H:%M:%S %Y")
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
except ValueError:
    raise SystemExit(2)

raise SystemExit(0 if started <= created else 1)
PY
}

redcap_interop_lock_process_matches() {
    local owner_pid="${1:-}"
    local owner_started_at="${2:-}"
    local live_started_at=""
    local legacy_match_status=0

    [[ -n "$owner_pid" ]] || return 1
    if ! kill -0 "$owner_pid" 2>/dev/null; then
        return 1
    fi

    if [[ -z "$owner_started_at" ]]; then
        return 0
    fi
    if redcap_interop_lock_field_is_legacy_created_at "$owner_started_at"; then
        live_started_at=$(redcap_runtime_process_started_at "$owner_pid" 2>/dev/null || true)
        if [[ -n "$live_started_at" ]]; then
            set +e
            redcap_interop_process_started_before_timestamp "$live_started_at" "$owner_started_at"
            legacy_match_status=$?
            set -e
            if [[ "$legacy_match_status" -ne 2 ]]; then
                return "$legacy_match_status"
            fi
        fi
        redcap_interop_legacy_lock_within_grace "$owner_started_at"
        return $?
    fi

    live_started_at=$(redcap_runtime_process_started_at "$owner_pid" 2>/dev/null || true)
    [[ -n "$live_started_at" && "$live_started_at" == "$owner_started_at" ]]
}

redcap_interop_release_pending_closure_lock_path() {
    local lock_path="$1"

    rm -f "$lock_path" 2>/dev/null || return 1
}

redcap_interop_prune_stale_pending_closure_lock() {
    local lock_path="$1"
    local owner_pid=""
    local owner_started_at=""

    if [[ ! -f "$lock_path" ]]; then
        return 0
    fi

    owner_pid=$(redcap_interop_pending_closure_lock_owner_pid "$lock_path" 2>/dev/null || true)
    owner_started_at=$(redcap_interop_lock_owner_started_at "$lock_path" 2>/dev/null || true)
    if redcap_interop_lock_process_matches "$owner_pid" "$owner_started_at"; then
        return 1
    fi

    redcap_interop_release_pending_closure_lock_path "$lock_path"
}

redcap_interop_acquire_pending_closure_lock() {
    local project_root="$1"
    local task_file="${2:-}"
    local lock_path lock_tmp lock_dir attempts=0 created_at owner_started_at

    lock_path=$(redcap_interop_pending_closure_lock_path "$project_root" "$task_file") || return 1
    lock_dir=$(dirname "$lock_path")
    lock_tmp="$lock_path.$$.$RANDOM.tmp"
    created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    owner_started_at=$(redcap_runtime_process_started_at "$$" 2>/dev/null || true)
    [[ -n "$owner_started_at" ]] || return 1

    mkdir -p "$lock_dir" || return 1
    chmod 700 "$lock_dir" 2>/dev/null || return 1
    printf '%s\t%s\t%s\n' "$$" "$owner_started_at" "$created_at" > "$lock_tmp" || return 1
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
match = re.search(rf"^{re.escape(key)}:[ \t]*(.*?)[ \t]*$", text, re.MULTILINE)
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
    local redline_mode="${10:-merge}"
    local expected_updated_at="${11:-}"
    local task_id top_goal active_slice confirmed_hash state_file current_state_file original_state_file state_dir now created_at existing_artifact_path
    local existing_required_redlines existing_baseline_head existing_audited_head existing_confirmed_hash existing_active_slice existing_top_goal existing_updated_at
    local reanchor_from_confirmed_hash="" reanchor_from_active_slice="" reanchor_from_artifact_path="" reanchor_from_baseline_head="" reanchor_from_audited_head=""
    local stale_removed=0
    local matching_state_files=()
    local stale_state_file=""

    if [[ -z "$project_root" || -z "$task_file" || -z "$host" || -z "$trigger" ]]; then
        return 1
    fi
    if [[ "$redline_mode" != "merge" && "$redline_mode" != "replace" ]]; then
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
        current_state_file=$(redcap_interop_pending_closure_current_file "$project_root" "$task_file")
        state_file=$(redcap_interop_pending_closure_existing_file "$project_root" "$task_file" 2>/dev/null || true)
        if [[ -z "$state_file" ]]; then
            state_file="$current_state_file"
        fi
        original_state_file="$state_file"
        state_dir=$(dirname "$state_file")
        mkdir -p "$state_dir" || exit 1

        created_at=$(redcap_interop_read_state_field "$state_file" "created_at" 2>/dev/null || true)
        [[ -n "$created_at" ]] || created_at="$now"
        existing_updated_at=$(redcap_interop_read_state_field "$state_file" "updated_at" 2>/dev/null || true)
        if [[ -n "$expected_updated_at" && "$existing_updated_at" != "$expected_updated_at" ]]; then
            exit 1
        fi
        existing_required_redlines=$(redcap_interop_read_state_field "$state_file" "required_redlines" 2>/dev/null || true)
        existing_confirmed_hash=$(redcap_interop_read_state_field "$state_file" "confirmed_hash" 2>/dev/null || true)
        existing_active_slice=$(redcap_interop_read_state_field "$state_file" "active_slice" 2>/dev/null || true)
        existing_top_goal=$(redcap_interop_read_state_field "$state_file" "top_goal" 2>/dev/null || true)
        existing_artifact_path=$(redcap_interop_read_state_field "$state_file" "artifact_path" 2>/dev/null || true)
        existing_artifact_path=$(redcap_interop_resolve_report_rel_path "$project_root" "$existing_artifact_path" 2>/dev/null || true)
        existing_baseline_head=$(redcap_interop_read_state_field "$state_file" "baseline_head" 2>/dev/null || true)
        existing_audited_head=$(redcap_interop_read_state_field "$state_file" "audited_head" 2>/dev/null || true)

        if [[ -n "$existing_confirmed_hash" && "$existing_confirmed_hash" != "$confirmed_hash" ]]; then
            reanchor_from_confirmed_hash="$existing_confirmed_hash"
            reanchor_from_active_slice="$existing_active_slice"
            reanchor_from_artifact_path="$existing_artifact_path"
            reanchor_from_baseline_head="$existing_baseline_head"
            reanchor_from_audited_head="$existing_audited_head"
            state_file="$current_state_file"
            state_dir=$(dirname "$state_file")
            mkdir -p "$state_dir" || exit 1
        fi

        if [[ "$redline_mode" == "merge" ]]; then
            required_redlines="${existing_required_redlines} ${required_redlines}"
        fi

        required_redlines=$(redcap_interop_normalize_redlines "$required_redlines")
        if [[ -n "$existing_confirmed_hash" && -z "$reanchor_from_confirmed_hash" ]]; then
            confirmed_hash="$existing_confirmed_hash"
        fi
        if [[ -n "$existing_active_slice" && -z "$reanchor_from_confirmed_hash" ]]; then
            active_slice="$existing_active_slice"
        fi
        if [[ -n "$existing_top_goal" && -z "$reanchor_from_confirmed_hash" ]]; then
            top_goal="$existing_top_goal"
        fi
        if [[ -z "$artifact_path" ]]; then
            artifact_path="$existing_artifact_path"
        fi
        artifact_path=$(redcap_interop_resolve_report_rel_path "$project_root" "$artifact_path" 2>/dev/null || true)
        if [[ "$redline_mode" == "merge" && -n "$existing_baseline_head" ]]; then
            baseline_head="$existing_baseline_head"
        elif [[ -z "$baseline_head" && -n "$existing_baseline_head" ]]; then
            baseline_head="$existing_baseline_head"
        fi
        if [[ "$redline_mode" == "merge" && -n "$existing_audited_head" ]]; then
            audited_head="$existing_audited_head"
        elif [[ -z "$audited_head" && -n "$existing_audited_head" ]]; then
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

        matching_state_files=()
        while IFS= read -r stale_state_file; do
            matching_state_files+=("$stale_state_file")
        done < <(redcap_interop_pending_closure_matching_files "$project_root" "$task_file" 2>/dev/null || true)
        for stale_state_file in "${matching_state_files[@]}"; do
            [[ -n "$stale_state_file" && "$stale_state_file" != "$state_file" ]] || continue
            if rm -f "$stale_state_file" 2>/dev/null; then
                stale_removed=$((stale_removed + 1))
            fi
        done

        if [[ -n "$reanchor_from_confirmed_hash" ]]; then
            redcap_interop_record_reanchor_event \
                "$project_root" \
                "pending-closure-reanchored" \
                "task_id=$task_id old_confirmed_hash=$reanchor_from_confirmed_hash new_confirmed_hash=$confirmed_hash trigger=$trigger host=$host stale_removed=$stale_removed"
            redcap_interop_append_closure_ledger_identity \
                "$project_root" \
                "$task_id" \
                "$reanchor_from_confirmed_hash" \
                "${reanchor_from_active_slice:-unknown}" \
                "obligation" \
                "reanchored" \
                "new_confirmed_hash=$confirmed_hash trigger=$trigger host=$host stale_removed=$stale_removed" \
                "$host" \
                "$trigger" \
                "$reanchor_from_baseline_head" \
                "$reanchor_from_audited_head" \
                "${reanchor_from_artifact_path:-$artifact_path}" \
                >/dev/null 2>&1 || true
        elif [[ "$stale_removed" -gt 0 ]]; then
            redcap_interop_record_reanchor_event \
                "$project_root" \
                "pending-closure-pruned-stale" \
                "task_id=$task_id confirmed_hash=$confirmed_hash trigger=$trigger host=$host stale_removed=$stale_removed"
        fi

        redcap_interop_record_closure_event \
            "$project_root" \
            "pending-closure-created" \
            "task_id=$task_id host=$host trigger=$trigger confirmed_hash=$confirmed_hash required_redlines=$required_redlines artifact_path=$artifact_path baseline_head=$baseline_head audited_head=$audited_head redline_mode=$redline_mode stale_removed=$stale_removed detail=$detail"
        redcap_interop_append_closure_ledger_identity \
            "$project_root" \
            "$task_id" \
            "$confirmed_hash" \
            "$active_slice" \
            "obligation" \
            "pending" \
            "required_redlines=$required_redlines redline_mode=$redline_mode detail=$detail" \
            "$host" \
            "$trigger" \
            "$baseline_head" \
            "$audited_head" \
            "$artifact_path" \
            >/dev/null 2>&1 || true

        printf '%s\n' "$state_file"
    )
}

redcap_interop_clear_pending_closure_locked() {
    local project_root="$1"
    local task_file="$2"
    local outcome="${3:-done}"
    local detail="${4:-}"
    local expected_updated_at="${5:-}"
    local state_file host trigger baseline_head audited_head artifact_path task_id confirmed_hash active_slice
    local cleared_files=0
    local matching_state_files=()
    local stale_state_file=""

    if [[ -z "$project_root" || -z "$task_file" ]]; then
        return 1
    fi

    project_root=$(redcap_runtime_project_root "$project_root")
    task_file=$(redcap_dev_task_resolve_file "$task_file")
    (
        local current_updated_at="" state_dir="" backup_dir="" moved_file="" ledger_written=0
        local moved_files=()
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
        state_dir=$(dirname "$state_file")
        backup_dir=$(mktemp -d "$state_dir/.pending-clear-backup.XXXXXX") || exit 1

        matching_state_files=()
        while IFS= read -r stale_state_file; do
            matching_state_files+=("$stale_state_file")
        done < <(redcap_interop_pending_closure_matching_files "$project_root" "$task_file" 2>/dev/null || true)
        for stale_state_file in "${matching_state_files[@]}"; do
            [[ -n "$stale_state_file" ]] || continue
            moved_file="$backup_dir/$(basename "$stale_state_file")"
            if mv "$stale_state_file" "$moved_file" 2>/dev/null; then
                moved_files+=("$moved_file")
                cleared_files=$((cleared_files + 1))
            else
                for moved_file in "${moved_files[@]:-}"; do
                    mv "$moved_file" "$state_dir/$(basename "$moved_file")" 2>/dev/null || true
                done
                rm -rf "$backup_dir" 2>/dev/null || true
                exit 1
            fi
        done
        if [[ "$cleared_files" -eq 0 ]]; then
            rm -rf "$backup_dir" 2>/dev/null || true
            exit 1
        fi

        redcap_interop_record_closure_event \
            "$project_root" \
            "pending-closure-cleared" \
            "task=$(basename "$state_file") outcome=$outcome cleared_files=$cleared_files detail=$detail"
        if redcap_interop_append_closure_ledger_identity \
            "$project_root" \
            "$task_id" \
            "$confirmed_hash" \
            "$active_slice" \
            "obligation" \
            "cleared" \
            "outcome=$outcome cleared_files=$cleared_files detail=$detail" \
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
            "outcome=$outcome cleared_files=$cleared_files detail=$detail" \
            "$host" \
            "$trigger" \
            "$baseline_head" \
            "$audited_head" \
            "$artifact_path" \
            >/dev/null 2>&1; then
            ledger_written=1
        fi

        if [[ "$ledger_written" -ne 1 ]]; then
            for moved_file in "${moved_files[@]:-}"; do
                mv "$moved_file" "$state_dir/$(basename "$moved_file")" 2>/dev/null || true
            done
            rm -rf "$backup_dir" 2>/dev/null || true
            exit 1
        fi

        rm -rf "$backup_dir" 2>/dev/null || true
    )
}

redcap_interop_clear_pending_closure() {
    local project_root="$1"
    local task_file="$2"
    local outcome="${3:-done}"
    local detail="${4:-}"
    local expected_updated_at="${5:-}"
    local lock_mode="${6:-acquire}"

    if [[ -z "$project_root" || -z "$task_file" ]]; then
        return 1
    fi

    project_root=$(redcap_runtime_project_root "$project_root")
    task_file=$(redcap_dev_task_resolve_file "$task_file")

    if [[ "$lock_mode" == "locked" ]]; then
        redcap_interop_clear_pending_closure_locked "$project_root" "$task_file" "$outcome" "$detail" "$expected_updated_at"
        return $?
    fi

    redcap_interop_acquire_pending_closure_lock "$project_root" "$task_file" || return 1
    (
        trap 'redcap_interop_release_pending_closure_lock "'"$project_root"'" "'"$task_file"'" >/dev/null 2>&1 || true' EXIT
        redcap_interop_clear_pending_closure_locked "$project_root" "$task_file" "$outcome" "$detail" "$expected_updated_at"
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

#!/usr/bin/env bash
# shellcheck shell=bash
# RedCap runtime session helpers

if [[ "${_REDCAP_RUNTIME_STATE_SH:-0}" == "1" ]]; then
    return 0 2>/dev/null || exit 0
fi
_REDCAP_RUNTIME_STATE_SH=1

redcap_runtime_json_field() {
    local input="$1"
    local field="$2"
    local value=""

    value=$(printf '%s' "$input" |
        grep -o "\"$field\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" |
        head -1 |
        sed "s/.*\"$field\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/" || true)

    printf '%s\n' "$value"
}

redcap_runtime_project_hash() {
    local path="$1"
    local hash=""

    hash=$(printf '%s' "$path" | md5 2>/dev/null) || true
    if [[ -z "$hash" ]]; then
        hash=$(printf '%s' "$path" | md5sum 2>/dev/null | awk '{print $1}') || true
    fi
    if [[ -z "$hash" ]]; then
        hash=$(redcap_runtime_sha256 "$path")
    fi

    printf '%s\n' "$hash"
}

redcap_runtime_normalize_path() {
    local path="$1"

    if [[ -d "$path" ]]; then
        (
            cd "$path" 2>/dev/null &&
            pwd -P
        )
        return 0
    fi

    printf '%s\n' "$path"
}

redcap_runtime_git_root() {
    local path="$1"
    local normalized root=""

    normalized=$(redcap_runtime_normalize_path "$path")
    root=$(git -C "$normalized" rev-parse --show-toplevel 2>/dev/null) || true
    if [[ -n "$root" ]]; then
        redcap_runtime_normalize_path "$root"
        return 0
    fi

    return 1
}

redcap_runtime_project_root() {
    local path="$1"
    local normalized root=""

    normalized=$(redcap_runtime_normalize_path "$path")
    root=$(redcap_runtime_git_root "$normalized") || true
    if [[ -n "$root" ]]; then
        printf '%s\n' "$root"
        return 0
    fi

    printf '%s\n' "$normalized"
}

redcap_runtime_project_name() {
    local path="$1"
    local explicit_name="${2:-}"
    local project_root="" project_name=""

    if [[ -n "$explicit_name" ]]; then
        printf '%s\n' "$explicit_name"
        return 0
    fi

    project_root=$(redcap_runtime_git_root "$path") || true
    project_name=$(basename "$project_root")
    if [[ -n "$project_name" && "$project_name" != "." && "$project_name" != "/" ]]; then
        printf '%s\n' "$project_name"
        return 0
    fi

    printf 'redcap\n'
}

redcap_runtime_sha256() {
    python3 - "$1" <<'PY'
import hashlib
import sys

print(hashlib.sha256(sys.argv[1].encode("utf-8")).hexdigest())
PY
}

redcap_runtime_uuid() {
    python3 - <<'PY'
import uuid

print(uuid.uuid4().hex)
PY
}

redcap_runtime_token() {
    python3 - <<'PY'
import secrets

print(secrets.token_hex(24))
PY
}

redcap_runtime_base_dir() {
    printf '%s\n' "${REDCAP_RUNTIME_BASE_DIR:-/tmp/redcap/runtime}"
}

redcap_runtime_index_dir() {
    printf '%s\n' "${REDCAP_RUNTIME_INDEX_DIR:-/tmp/redcap/runtime-index}"
}

redcap_runtime_project_base_dir() {
    printf '%s\n' "${REDCAP_RUNTIME_PROJECT_BASE_DIR:-/tmp/redcap/project}"
}

redcap_runtime_process_claim_base_dir() {
    printf '%s\n' "${REDCAP_RUNTIME_PROCESS_CLAIM_DIR:-/tmp/redcap/process-claims}"
}

redcap_runtime_claim_owner_pid() {
    printf '%s\n' "${REDCAP_HOST_PROCESS_PID:-$PPID}"
}

redcap_runtime_claim_search_pid() {
    printf '%s\n' "${REDCAP_HOST_PROCESS_PID:-$$}"
}

redcap_runtime_session_dir_for_id() {
    printf '%s/%s\n' "$(redcap_runtime_base_dir)" "$1"
}

redcap_runtime_owner_file_for_id() {
    printf '%s/owner.json\n' "$(redcap_runtime_session_dir_for_id "$1")"
}

redcap_runtime_capability_file_for_id() {
    printf '%s/capability.token\n' "$(redcap_runtime_session_dir_for_id "$1")"
}

redcap_runtime_project_dir_for_root() {
    local project_root="$1"
    local normalized_root project_hash

    normalized_root=$(redcap_runtime_project_root "$project_root")
    project_hash=$(redcap_runtime_project_hash "$normalized_root")
    printf '%s/%s\n' "$(redcap_runtime_project_base_dir)" "$project_hash"
}

redcap_runtime_project_path_for_root() {
    local project_root="$1"
    local rel_path="$2"

    printf '%s/%s\n' "$(redcap_runtime_project_dir_for_root "$project_root")" "$rel_path"
}

redcap_runtime_compat_dir_for_root() {
    local project_root="$1"

    printf '%s\n' "$(redcap_runtime_project_path_for_root "$project_root" "compat")"
}

redcap_runtime_compat_path_for_root() {
    local project_root="$1"
    local rel_path="$2"

    printf '%s/%s\n' "$(redcap_runtime_compat_dir_for_root "$project_root")" "$rel_path"
}

redcap_runtime_legacy_quarantine_dir_for_root() {
    local project_root="$1"

    printf '%s\n' "$(redcap_runtime_compat_path_for_root "$project_root" "legacy-quarantine")"
}

redcap_runtime_quarantine_legacy_path() {
    local project_root="$1"
    local source_path="$2"
    local event="$3"
    local detail="${4:-}"
    local quarantine_dir timestamp base_name dest_path

    if [[ -z "$project_root" || -z "$source_path" || -z "$event" || ! -e "$source_path" ]]; then
        return 1
    fi

    project_root=$(redcap_runtime_project_root "$project_root")
    quarantine_dir=$(redcap_runtime_legacy_quarantine_dir_for_root "$project_root")
    mkdir -p "$quarantine_dir" || return 1

    timestamp=$(date -u +%Y%m%dT%H%M%SZ)
    base_name=$(basename "$source_path")
    dest_path="$quarantine_dir/${timestamp}-$$-${base_name}"

    mv "$source_path" "$dest_path" 2>/dev/null || {
        if [[ -f "$source_path" ]]; then
            cp -p "$source_path" "$dest_path" 2>/dev/null || return 1
            rm -f "$source_path" 2>/dev/null || return 1
        else
            return 1
        fi
    }

    redcap_runtime_increment_counter_file "$quarantine_dir/quarantined.count"
    redcap_runtime_append_event_log "$quarantine_dir/quarantine.log" "$event" "source=$source_path dest=$dest_path ${detail}"
    printf '%s\n' "$dest_path"
}

redcap_runtime_claim_text_owner() {
    local owner_file="$1"
    local owner_id="$2"
    local current_owner=""

    if [[ -z "$owner_file" || -z "$owner_id" ]]; then
        return 1
    fi

    mkdir -p "$(dirname "$owner_file")"
    if (set -C; printf '%s\n' "$owner_id" > "$owner_file") 2>/dev/null; then
        return 0
    fi

    if [[ -f "$owner_file" ]]; then
        current_owner=$(cat "$owner_file" 2>/dev/null || true)
        [[ "$current_owner" == "$owner_id" ]]
        return
    fi

    return 1
}

redcap_runtime_release_text_owner() {
    local owner_file="$1"
    local owner_id="$2"
    local current_owner=""

    if [[ -z "$owner_file" || ! -f "$owner_file" ]]; then
        return 1
    fi

    current_owner=$(cat "$owner_file" 2>/dev/null || true)
    if [[ -n "$owner_id" && "$current_owner" != "$owner_id" ]]; then
        return 1
    fi

    rm -f "$owner_file" 2>/dev/null || true
}

redcap_runtime_process_claim_file() {
    local host="$1"
    local host_process_pid="$2"

    printf '%s/%s/%s.json\n' "$(redcap_runtime_process_claim_base_dir)" "$host" "$host_process_pid"
}

redcap_runtime_find_process_claim_file() {
    local host="$1"
    local start_pid="${2:-$(redcap_runtime_claim_search_pid)}"
    local pid="$start_pid"
    local claim_file parent_pid

    while [[ -n "$pid" && "$pid" != "0" && "$pid" != "1" ]]; do
        claim_file=$(redcap_runtime_process_claim_file "$host" "$pid")
        if [[ -f "$claim_file" ]]; then
            printf '%s\n' "$claim_file"
            return 0
        fi

        parent_pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d '[:space:]')
        if [[ -z "$parent_pid" || "$parent_pid" == "$pid" ]]; then
            break
        fi
        pid="$parent_pid"
    done

    return 1
}

redcap_runtime_process_started_at() {
    local host_process_pid="$1"

    if [[ -z "$host_process_pid" ]]; then
        return 1
    fi

    ps -o lstart= -p "$host_process_pid" 2>/dev/null | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' | head -n 1
}

redcap_runtime_verify_process_claim_file() {
    local claim_file="$1"
    local host_process_pid="$2"
    local claimed_pid claimed_probe_pid claimed_started_at live_started_at

    if [[ -z "$claim_file" || -z "$host_process_pid" || ! -f "$claim_file" ]]; then
        return 1
    fi

    claimed_pid=$(redcap_runtime_read_process_claim_field "$claim_file" "host_process_pid" 2>/dev/null || true)
    claimed_probe_pid=$(redcap_runtime_read_process_claim_field "$claim_file" "host_process_probe_pid" 2>/dev/null || true)
    claimed_started_at=$(redcap_runtime_read_process_claim_field "$claim_file" "host_process_started_at" 2>/dev/null || true)
    if [[ -z "$claimed_probe_pid" ]]; then
        claimed_probe_pid="$claimed_pid"
    fi
    live_started_at=$(redcap_runtime_process_started_at "$claimed_probe_pid" 2>/dev/null || true)

    [[ -n "$claimed_pid" && "$claimed_pid" == "$host_process_pid" && -n "$claimed_started_at" && -n "$live_started_at" && "$claimed_started_at" == "$live_started_at" ]]
}

redcap_runtime_binding_key_from_host_session() {
    local host="$1"
    local session_id="$2"

    if [[ -z "$host" || -z "$session_id" ]]; then
        return 1
    fi

    printf 'host/%s/session/%s\n' "$host" "$session_id"
}

redcap_runtime_binding_file() {
    local project_hash="$1"
    local binding_key="$2"
    local binding_hash

    binding_hash=$(redcap_runtime_sha256 "$binding_key")
    printf '%s/%s/%s.binding\n' "$(redcap_runtime_index_dir)" "$project_hash" "$binding_hash"
}

redcap_runtime_mint_session_id() {
    local host="$1"
    local project_hash="$2"
    local rand

    rand=$(redcap_runtime_uuid)
    printf 'rs-%s-%s-%s\n' "$host" "$project_hash" "$rand"
}

redcap_runtime_write_owner_file() {
    local owner_file="$1"
    local runtime_session_id="$2"
    local session_binding_key="$3"
    local project_hash="$4"
    local project_root="$5"
    local host="$6"
    local cwd="$7"
    local created_at="$8"

    mkdir -p "$(dirname "$owner_file")" || return 1

    python3 - "$owner_file" \
        "$runtime_session_id" \
        "$session_binding_key" \
        "$project_hash" \
        "$project_root" \
        "$host" \
        "$cwd" \
        "$created_at" <<'PY'
import json
import sys

path = sys.argv[1]
data = {
    "runtime_session_id": sys.argv[2],
    "session_binding_key": sys.argv[3],
    "project_hash": sys.argv[4],
    "project_root": sys.argv[5],
    "host": sys.argv[6],
    "cwd": sys.argv[7],
    "created_at": sys.argv[8],
}

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
PY
    chmod 600 "$owner_file" 2>/dev/null || return 1
}

redcap_runtime_read_owner_field() {
    local owner_file="$1"
    local field="$2"

    python3 - "$owner_file" "$field" <<'PY'
import json
import sys

path = sys.argv[1]
field = sys.argv[2]

with open(path, encoding="utf-8") as f:
    data = json.load(f)

value = data.get(field, "")
if isinstance(value, str):
    print(value)
PY
}

redcap_runtime_write_process_claim() {
    local claim_file="$1"
    local runtime_session_id="$2"
    local runtime_session_capability="$3"
    local session_binding_key="$4"
    local project_hash="$5"
    local host="$6"
    local host_process_pid="$7"
    local host_process_probe_pid="$8"
    local host_process_started_at="$9"
    local claim_dir claim_base_dir

    claim_dir="$(dirname "$claim_file")"
    claim_base_dir="$(dirname "$claim_dir")"
    mkdir -p "$claim_dir" || return 1
    chmod 700 "$claim_base_dir" "$claim_dir" 2>/dev/null || return 1

    python3 - "$claim_file" \
        "$runtime_session_id" \
        "$runtime_session_capability" \
        "$session_binding_key" \
        "$project_hash" \
        "$host" \
        "$host_process_pid" \
        "$host_process_probe_pid" \
        "$host_process_started_at" <<'PY'
import json
import sys

path = sys.argv[1]
data = {
    "runtime_session_id": sys.argv[2],
    "runtime_session_capability": sys.argv[3],
    "session_binding_key": sys.argv[4],
    "project_hash": sys.argv[5],
    "host": sys.argv[6],
    "host_process_pid": sys.argv[7],
    "host_process_probe_pid": sys.argv[8],
    "host_process_started_at": sys.argv[9],
}

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
PY
    chmod 600 "$claim_file" 2>/dev/null || return 1
}

redcap_runtime_read_process_claim_field() {
    local claim_file="$1"
    local field="$2"

    python3 - "$claim_file" "$field" <<'PY'
import json
import sys

path = sys.argv[1]
field = sys.argv[2]

with open(path, encoding="utf-8") as f:
    data = json.load(f)

value = data.get(field, "")
if isinstance(value, str):
    print(value)
PY
}

redcap_runtime_write_capability_file() {
    local capability_file="$1"
    local capability="$2"

    printf '%s\n' "$capability" > "$capability_file" || return 1
    chmod 600 "$capability_file" 2>/dev/null || return 1
}

redcap_runtime_read_capability_file() {
    local capability_file="$1"

    if [[ -f "$capability_file" ]]; then
        cat "$capability_file"
        return 0
    fi

    return 1
}

redcap_runtime_increment_counter_file() {
    local counter_file="$1"
    local current=0

    mkdir -p "$(dirname "$counter_file")"
    if [[ -f "$counter_file" ]]; then
        current=$(cat "$counter_file" 2>/dev/null || true)
        if [[ ! "$current" =~ ^[0-9]+$ ]]; then
            current=0
        fi
    fi

    current=$((current + 1))
    printf '%s\n' "$current" > "$counter_file"
}

redcap_runtime_append_event_log() {
    local log_file="$1"
    local event="$2"
    local detail="${3:-}"

    mkdir -p "$(dirname "$log_file")"
    printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$event" "$detail" >> "$log_file"
}

redcap_runtime_record_legacy_hit() {
    local project_root="$1"
    local event="$2"
    local detail="${3:-}"
    local compat_dir

    project_root=$(redcap_runtime_project_root "$project_root")
    compat_dir=$(redcap_runtime_compat_dir_for_root "$project_root")

    redcap_runtime_increment_counter_file "$compat_dir/legacy-hit.count"
    redcap_runtime_append_event_log "$compat_dir/legacy-hit.log" "$event" "$detail"
}

redcap_runtime_record_degraded_mode() {
    local project_root="$1"
    local event="$2"
    local detail="${3:-}"
    local compat_dir

    project_root=$(redcap_runtime_project_root "$project_root")
    compat_dir=$(redcap_runtime_compat_dir_for_root "$project_root")

    redcap_runtime_increment_counter_file "$compat_dir/degraded-mode.count"
    redcap_runtime_append_event_log "$compat_dir/degraded-mode.log" "$event" "$detail"
}

redcap_runtime_record_unsupported_mode() {
    local project_root="$1"
    local event="$2"
    local detail="${3:-}"
    local compat_dir

    project_root=$(redcap_runtime_project_root "$project_root")
    compat_dir=$(redcap_runtime_compat_dir_for_root "$project_root")

    redcap_runtime_increment_counter_file "$compat_dir/unsupported-mode.count"
    redcap_runtime_append_event_log "$compat_dir/unsupported-mode.log" "$event" "$detail"
}

redcap_runtime_clear_context() {
    unset REDCAP_HOST_PROCESS_PID
    unset REDCAP_ISOLATION_MODE
    unset REDCAP_RESUME_GATE_REASON
    unset REDCAP_RESUME_GATE_PROFILE
    unset REDCAP_RESUME_GATE_EVIDENCE
    unset REDCAP_SESSION_ISOLATION_MODE
    unset REDCAP_SESSION_RESUME_REASON
    unset REDCAP_SESSION_RESUME_PROFILE
    unset REDCAP_SESSION_RESUME_EVIDENCE
    unset REDCAP_RUNTIME_HOST
    unset REDCAP_RUNTIME_CWD
    unset REDCAP_RUNTIME_PROJECT_ROOT
    unset REDCAP_RUNTIME_PROJECT_HASH
    unset REDCAP_RUNTIME_BINDING_KEY
    unset REDCAP_RUNTIME_SESSION_ID
    unset REDCAP_RUNTIME_CAPABILITY
    unset REDCAP_RUNTIME_SESSION_DIR
    unset REDCAP_RUNTIME_OWNER_FILE
    unset REDCAP_RUNTIME_CREATED
}

redcap_runtime_register_process_claim() {
    local host="$1"
    local runtime_session_id="$2"
    local runtime_session_capability="$3"
    local session_binding_key="$4"
    local project_hash="$5"
    local host_process_pid="${6:-$(redcap_runtime_claim_owner_pid)}"
    local host_process_probe_pid="${REDCAP_HOST_PROCESS_PROBE_PID:-$host_process_pid}"
    local host_process_started_at claim_file

    if [[ -z "$host" || -z "$runtime_session_id" || -z "$runtime_session_capability" || -z "$host_process_pid" ]]; then
        return 1
    fi

    host_process_started_at=$(redcap_runtime_process_started_at "$host_process_probe_pid" 2>/dev/null || true)
    if [[ -z "$host_process_started_at" ]]; then
        return 1
    fi

    claim_file=$(redcap_runtime_process_claim_file "$host" "$host_process_pid")
    if ! redcap_runtime_write_process_claim \
        "$claim_file" \
        "$runtime_session_id" \
        "$runtime_session_capability" \
        "$session_binding_key" \
        "$project_hash" \
        "$host" \
        "$host_process_pid" \
        "$host_process_probe_pid" \
        "$host_process_started_at"; then
        rm -f "$claim_file" 2>/dev/null || true
        return 1
    fi

    return 0
}

redcap_runtime_load_claimed_capability() {
    local host="$1"
    local runtime_session_id="$2"
    local host_process_pid="${3:-$(redcap_runtime_claim_search_pid)}"
    local claim_file claimed_session_id capability

    if [[ -z "$host" || -z "$runtime_session_id" || -z "$host_process_pid" ]]; then
        return 1
    fi

    claim_file=$(redcap_runtime_find_process_claim_file "$host" "$host_process_pid" 2>/dev/null || true)
    if [[ ! -f "$claim_file" ]]; then
        return 1
    fi
    if ! redcap_runtime_verify_process_claim_file "$claim_file" "$host_process_pid"; then
        return 1
    fi

    claimed_session_id=$(redcap_runtime_read_process_claim_field "$claim_file" "runtime_session_id" 2>/dev/null || true)
    if [[ "$claimed_session_id" != "$runtime_session_id" ]]; then
        return 1
    fi

    capability=$(redcap_runtime_read_process_claim_field "$claim_file" "runtime_session_capability" 2>/dev/null || true)
    if [[ -n "$capability" ]]; then
        printf '%s\n' "$capability"
        return 0
    fi

    return 1
}

redcap_runtime_attach_from_process_claim() {
    local host="$1"
    local host_process_pid="${2:-$(redcap_runtime_claim_search_pid)}"
    local claim_file runtime_session_id capability

    if [[ -z "$host" || -z "$host_process_pid" ]]; then
        return 1
    fi

    claim_file=$(redcap_runtime_find_process_claim_file "$host" "$host_process_pid" 2>/dev/null || true)
    if [[ ! -f "$claim_file" ]]; then
        return 1
    fi
    if ! redcap_runtime_verify_process_claim_file "$claim_file" "$host_process_pid"; then
        return 1
    fi

    runtime_session_id=$(redcap_runtime_read_process_claim_field "$claim_file" "runtime_session_id" 2>/dev/null || true)
    capability=$(redcap_runtime_read_process_claim_field "$claim_file" "runtime_session_capability" 2>/dev/null || true)
    if [[ -z "$runtime_session_id" || -z "$capability" ]]; then
        return 1
    fi

    redcap_runtime_attach_existing "$runtime_session_id" "$capability"
}

redcap_runtime_clear_process_claim() {
    local host="$1"
    local host_process_pid="${2:-$(redcap_runtime_claim_owner_pid)}"
    local claim_file

    if [[ -z "$host" || -z "$host_process_pid" ]]; then
        return 1
    fi

    claim_file=$(redcap_runtime_process_claim_file "$host" "$host_process_pid")
    rm -f "$claim_file" 2>/dev/null || true
}

redcap_runtime_assert_capability() {
    local expected=""
    local capability_file=""

    if [[ -z "${REDCAP_RUNTIME_SESSION_ID:-}" || -z "${REDCAP_RUNTIME_CAPABILITY:-}" ]]; then
        return 1
    fi

    capability_file=$(redcap_runtime_capability_file_for_id "$REDCAP_RUNTIME_SESSION_ID")
    expected=$(redcap_runtime_read_capability_file "$capability_file" 2>/dev/null || true)
    if [[ -z "$expected" && -n "${REDCAP_RUNTIME_OWNER_FILE:-}" ]]; then
        expected=$(redcap_runtime_read_owner_field "$REDCAP_RUNTIME_OWNER_FILE" "runtime_session_capability" 2>/dev/null || true)
    fi

    [[ -n "$expected" && "$expected" == "$REDCAP_RUNTIME_CAPABILITY" ]]
}

redcap_runtime_attach_existing() {
    local runtime_session_id="$1"
    local owner_file provided_capability expected capability_file
    local binding_key project_hash cwd project_root host session_dir

    if [[ -z "$runtime_session_id" ]]; then
        return 1
    fi

    provided_capability="${2:-${REDCAP_RUNTIME_CAPABILITY:-}}"
    if [[ -z "$provided_capability" ]]; then
        return 1
    fi

    owner_file=$(redcap_runtime_owner_file_for_id "$runtime_session_id")
    if [[ ! -f "$owner_file" ]]; then
        return 1
    fi

    capability_file=$(redcap_runtime_capability_file_for_id "$runtime_session_id")
    expected=$(redcap_runtime_read_capability_file "$capability_file" 2>/dev/null || true)
    if [[ -z "$expected" ]]; then
        expected=$(redcap_runtime_read_owner_field "$owner_file" "runtime_session_capability" 2>/dev/null || true)
    fi
    if [[ -z "$expected" || "$expected" != "$provided_capability" ]]; then
        return 1
    fi

    binding_key=$(redcap_runtime_read_owner_field "$owner_file" "session_binding_key")
    project_hash=$(redcap_runtime_read_owner_field "$owner_file" "project_hash")
    cwd=$(redcap_runtime_read_owner_field "$owner_file" "cwd")
    project_root=$(redcap_runtime_read_owner_field "$owner_file" "project_root")
    host=$(redcap_runtime_read_owner_field "$owner_file" "host")
    session_dir=$(redcap_runtime_session_dir_for_id "$runtime_session_id")

    REDCAP_RUNTIME_SESSION_ID="$runtime_session_id"
    REDCAP_RUNTIME_CAPABILITY="$provided_capability"
    REDCAP_RUNTIME_BINDING_KEY="$binding_key"
    REDCAP_RUNTIME_PROJECT_HASH="$project_hash"
    REDCAP_RUNTIME_CWD="$cwd"
    REDCAP_RUNTIME_PROJECT_ROOT="$project_root"
    REDCAP_RUNTIME_HOST="$host"
    REDCAP_RUNTIME_SESSION_DIR="$session_dir"
    REDCAP_RUNTIME_OWNER_FILE="$owner_file"

    return 0
}

redcap_runtime_load_from_binding() {
    local host="$1"
    local cwd="$2"
    local binding_key="$3"
    local project_root project_hash binding_file runtime_session_id owner_file capability_file capability

    if [[ -z "$host" || -z "$cwd" || -z "$binding_key" ]]; then
        return 1
    fi

    project_root=$(redcap_runtime_project_root "$cwd")
    project_hash=$(redcap_runtime_project_hash "$project_root")
    binding_file=$(redcap_runtime_binding_file "$project_hash" "$binding_key")

    if [[ ! -f "$binding_file" ]]; then
        return 1
    fi

    runtime_session_id=$(cat "$binding_file" 2>/dev/null)
    if [[ -z "$runtime_session_id" ]]; then
        return 1
    fi

    owner_file=$(redcap_runtime_owner_file_for_id "$runtime_session_id")
    if [[ ! -f "$owner_file" ]]; then
        return 1
    fi

    capability="${REDCAP_RUNTIME_CAPABILITY:-}"
    if [[ -z "$capability" ]]; then
        capability=$(redcap_runtime_load_claimed_capability "$host" "$runtime_session_id" 2>/dev/null || true)
    fi
    if [[ -z "$capability" && "${REDCAP_RUNTIME_ALLOW_DISK_RECOVERY:-0}" == "1" && "${REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY:-0}" == "1" ]]; then
        capability_file=$(redcap_runtime_capability_file_for_id "$runtime_session_id")
        capability=$(redcap_runtime_read_capability_file "$capability_file" 2>/dev/null || true)
    fi
    if [[ -z "$capability" ]]; then
        return 1
    fi

    REDCAP_RUNTIME_HOST="$host"
    REDCAP_RUNTIME_CWD="$cwd"
    REDCAP_RUNTIME_PROJECT_ROOT="$project_root"
    REDCAP_RUNTIME_PROJECT_HASH="$project_hash"
    REDCAP_RUNTIME_BINDING_KEY="$binding_key"
    REDCAP_RUNTIME_SESSION_ID="$runtime_session_id"
    REDCAP_RUNTIME_CAPABILITY="$capability"
    REDCAP_RUNTIME_SESSION_DIR=$(redcap_runtime_session_dir_for_id "$runtime_session_id")
    REDCAP_RUNTIME_OWNER_FILE="$owner_file"

    redcap_runtime_assert_capability || return 1
    if ! redcap_runtime_register_process_claim \
        "$host" \
        "$runtime_session_id" \
        "$REDCAP_RUNTIME_CAPABILITY" \
        "$binding_key" \
        "$project_hash"; then
        redcap_runtime_clear_process_claim "$host" "$(redcap_runtime_claim_owner_pid)" || true
        redcap_runtime_clear_context
        return 1
    fi

    return 0
}

redcap_runtime_init_from_binding() {
    local host="$1"
    local cwd="$2"
    local binding_key="$3"
    local project_root project_hash binding_file runtime_session_id owner_file capability_file created_at session_dir

    if [[ -z "$host" || -z "$cwd" || -z "$binding_key" ]]; then
        return 1
    fi

    project_root=$(redcap_runtime_project_root "$cwd")
    if redcap_runtime_load_from_binding "$host" "$project_root" "$binding_key"; then
        REDCAP_RUNTIME_CREATED=0
        return 0
    fi

    project_hash=$(redcap_runtime_project_hash "$project_root")
    binding_file=$(redcap_runtime_binding_file "$project_hash" "$binding_key")
    runtime_session_id=$(redcap_runtime_mint_session_id "$host" "$project_hash")
    session_dir=$(redcap_runtime_session_dir_for_id "$runtime_session_id")
    owner_file=$(redcap_runtime_owner_file_for_id "$runtime_session_id")
    capability_file=$(redcap_runtime_capability_file_for_id "$runtime_session_id")
    created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    mkdir -p "$(dirname "$binding_file")"
    mkdir -p "$session_dir"
    chmod 700 "$session_dir" 2>/dev/null || true

    REDCAP_RUNTIME_HOST="$host"
    REDCAP_RUNTIME_CWD="$cwd"
    REDCAP_RUNTIME_PROJECT_ROOT="$project_root"
    REDCAP_RUNTIME_PROJECT_HASH="$project_hash"
    REDCAP_RUNTIME_BINDING_KEY="$binding_key"
    REDCAP_RUNTIME_SESSION_ID="$runtime_session_id"
    REDCAP_RUNTIME_CAPABILITY=$(redcap_runtime_token)
    REDCAP_RUNTIME_SESSION_DIR=$(redcap_runtime_session_dir_for_id "$runtime_session_id")
    REDCAP_RUNTIME_OWNER_FILE="$owner_file"
    REDCAP_RUNTIME_CREATED=1

    redcap_runtime_write_owner_file \
        "$owner_file" \
        "$runtime_session_id" \
        "$binding_key" \
        "$project_hash" \
        "$project_root" \
        "$host" \
        "$cwd" \
        "$created_at" || {
        rm -rf "$session_dir" 2>/dev/null || true
        redcap_runtime_clear_context
        return 1
    }
    redcap_runtime_write_capability_file "$capability_file" "$REDCAP_RUNTIME_CAPABILITY" || {
        rm -rf "$session_dir" 2>/dev/null || true
        redcap_runtime_clear_context
        return 1
    }

    if ! (set -C; printf '%s\n' "$runtime_session_id" > "$binding_file") 2>/dev/null; then
        rm -rf "$session_dir" 2>/dev/null || true
        redcap_runtime_clear_context
        if REDCAP_RUNTIME_ALLOW_DISK_RECOVERY=1 REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY=1 redcap_runtime_load_from_binding "$host" "$project_root" "$binding_key"; then
            REDCAP_RUNTIME_CREATED=0
            return 0
        fi
        return 1
    fi

    chmod 600 "$binding_file" 2>/dev/null || {
        rm -f "$binding_file" 2>/dev/null || true
        rm -rf "$session_dir" 2>/dev/null || true
        redcap_runtime_clear_context
        return 1
    }
    redcap_runtime_register_process_claim \
        "$host" \
        "$runtime_session_id" \
        "$REDCAP_RUNTIME_CAPABILITY" \
        "$binding_key" \
        "$project_hash" || {
        redcap_runtime_clear_process_claim "$host" "$(redcap_runtime_claim_owner_pid)" || true
        rm -f "$binding_file" 2>/dev/null || true
        rm -rf "$session_dir" 2>/dev/null || true
        redcap_runtime_clear_context
        return 1
    }

    return 0
}

redcap_runtime_path() {
    if [[ -z "${REDCAP_RUNTIME_SESSION_DIR:-}" ]]; then
        return 1
    fi
    redcap_runtime_assert_capability || return 1

    printf '%s/%s\n' "$REDCAP_RUNTIME_SESSION_DIR" "$1"
}

redcap_runtime_write_text() {
    local rel_path="$1"
    local content="$2"
    local abs_path

    abs_path=$(redcap_runtime_path "$rel_path") || return 1
    mkdir -p "$(dirname "$abs_path")"
    printf '%s\n' "$content" > "$abs_path"
}

redcap_runtime_read_text() {
    local rel_path="$1"
    local abs_path

    abs_path=$(redcap_runtime_path "$rel_path") || return 1
    if [[ -f "$abs_path" ]]; then
        cat "$abs_path"
        return 0
    fi

    return 1
}

redcap_runtime_remove_path() {
    local rel_path="$1"
    local abs_path

    abs_path=$(redcap_runtime_path "$rel_path") || return 1
    rm -f "$abs_path" 2>/dev/null || true
}

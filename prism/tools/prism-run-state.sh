#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REDCAP_ROOT/compass/tools/redcap-runtime-state.sh"

PRISM_RESOLVED_RUN_ID=""
PRISM_RESOLVED_REGISTRY_FILE=""
PRISM_RESOLVED_REGISTRY_SOURCE=""

prism_validate_run_id() {
    local run_id="$1"

    [[ -n "$run_id" && "$run_id" =~ ^[A-Za-z0-9._-]+$ && ! "$run_id" =~ ^\.+$ ]]
}

prism_validate_role() {
    local role="$1"

    [[ -n "$role" && "$role" =~ ^[A-Za-z0-9_-]+$ ]]
}

prism_runs_dir() {
    printf '%s/prism/runs\n' "$REDCAP_ROOT"
}

prism_run_locks_dir() {
    printf '%s/.locks\n' "$(prism_runs_dir)"
}

prism_legacy_registry_file() {
    printf '%s/prism/reports/.session-registry.yaml\n' "$REDCAP_ROOT"
}

prism_run_dir() {
    local run_id="$1"

    if ! prism_validate_run_id "$run_id"; then
        return 1
    fi

    printf '%s/%s\n' "$(prism_runs_dir)" "$run_id"
}

prism_run_registry_file() {
    local run_id="$1"
    local run_dir

    run_dir=$(prism_run_dir "$run_id") || return 1
    printf '%s/session-registry.yaml\n' "$run_dir"
}

prism_run_owner_file() {
    local run_id="$1"
    local run_dir

    run_dir=$(prism_run_dir "$run_id") || return 1
    printf '%s/owner.json\n' "$run_dir"
}

prism_run_collect_dir() {
    local run_id="$1"
    local run_dir

    run_dir=$(prism_run_dir "$run_id") || return 1
    printf '%s/collect\n' "$run_dir"
}

prism_run_collect_role_dir() {
    local run_id="$1"
    local role="$2"
    local collect_dir

    prism_validate_role "$role" || return 1
    collect_dir=$(prism_run_collect_dir "$run_id") || return 1
    printf '%s/%s\n' "$collect_dir" "$role"
}

prism_run_lock_dir() {
    local run_id="$1"

    if ! prism_validate_run_id "$run_id"; then
        return 1
    fi

    printf '%s/%s.lock\n' "$(prism_run_locks_dir)" "$run_id"
}

prism_run_lock_owner_pid() {
    local lock_path="$1"

    awk -F '\t' 'NR == 1 { print $1 }' "$lock_path" 2>/dev/null
}

prism_release_run_lock_dir() {
    local lock_path="$1"

    rm -f "$lock_path" 2>/dev/null || return 1
}

prism_prune_stale_run_lock() {
    local lock_path="$1"
    local owner_pid=""

    if [[ ! -f "$lock_path" ]]; then
        return 0
    fi

    owner_pid=$(prism_run_lock_owner_pid "$lock_path" 2>/dev/null || true)
    if [[ -n "$owner_pid" ]] && kill -0 "$owner_pid" 2>/dev/null; then
        return 1
    fi

    prism_release_run_lock_dir "$lock_path"
}

prism_acquire_run_lock() {
    local run_id="$1"
    local lock_path lock_tmp lock_dir attempts=0
    local created_at

    lock_path=$(prism_run_lock_dir "$run_id") || return 1
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
        prism_prune_stale_run_lock "$lock_path" || true
        attempts=$((attempts + 1))
        if [[ "$attempts" -ge 200 ]]; then
            rm -f "$lock_tmp" 2>/dev/null || true
            return 1
        fi
        sleep 0.05
    done

    rm -f "$lock_tmp" 2>/dev/null || true
}

prism_release_run_lock() {
    local run_id="$1"
    local lock_path

    lock_path=$(prism_run_lock_dir "$run_id") || return 1
    prism_release_run_lock_dir "$lock_path"
}

prism_with_run_lock() {
    local run_id="$1"
    local status=0
    shift

    prism_acquire_run_lock "$run_id" || return 1
    (
        trap 'prism_release_run_lock "'"$run_id"'" >/dev/null 2>&1 || true' EXIT
        "$@" || exit $?
    ) || status=$?
    return "$status"
}

prism_registry_field() {
    local registry_file="$1"
    local field="$2"

    python3 - "$registry_file" "$field" <<'PY'
import re
import sys

path = sys.argv[1]
field = sys.argv[2]
pattern = re.compile(rf"^{re.escape(field)}:\s*(.+)$")

with open(path, encoding="utf-8") as f:
    for raw in f:
        match = pattern.match(raw.rstrip("\n"))
        if match:
            print(match.group(1).strip().strip('"'))
            break
PY
}

prism_registry_run_id() {
    prism_registry_field "$1" "run_id"
}

prism_registry_mode() {
    prism_registry_field "$1" "mode"
}

prism_export_registry_agent_for_role() {
    local run_id="$1"
    local role="$2"
    local registry_file

    prism_validate_run_id "$run_id" || return 1
    prism_validate_role "$role" || return 1
    registry_file=$(prism_run_registry_file "$run_id") || return 1
    [[ -f "$registry_file" ]] || return 1

    python3 - "$registry_file" "$role" <<'PY'
import re
import shlex
import sys

path = sys.argv[1]
role = sys.argv[2]

def strip_value(value: str) -> str:
    return value.strip().strip('"')

agents = []
current = None
with open(path, encoding="utf-8") as f:
    for raw in f:
        line = raw.rstrip("\n")
        match = re.match(r"^\s*-\s+handle_type:\s*(.+)$", line)
        if match:
            if current is not None:
                agents.append(current)
            current = {"handle_type": strip_value(match.group(1))}
            continue
        match = re.match(r"^\s+([A-Za-z_]+):\s*(.*)$", line)
        if match and current is not None:
            current[match.group(1)] = strip_value(match.group(2))
    if current is not None:
        agents.append(current)

target = None
for agent in agents:
    if agent.get("role") == role:
        target = agent
        break

if target is None:
    raise SystemExit(1)

fields = {
    "PRISM_AGENT_HANDLE_TYPE": target.get("handle_type", ""),
    "PRISM_AGENT_HANDLE": target.get("handle", ""),
    "PRISM_AGENT_ROLE": target.get("role", ""),
    "PRISM_AGENT_MODEL": target.get("model", ""),
    "PRISM_AGENT_FAMILY": target.get("family", ""),
    "PRISM_AGENT_INJECTION_MODE": target.get("injection_mode", ""),
    "PRISM_AGENT_STATUS": target.get("status", ""),
    "PRISM_AGENT_SCHEMA_OK": target.get("schema_ok", ""),
}

for key, value in fields.items():
    print(f"{key}={shlex.quote(value)}")
PY
}

prism_extract_report_run_id() {
    local report_file="$1"

    python3 - "$report_file" <<'PY'
import re
import sys

path = sys.argv[1]
pattern = re.compile(r"\*\*运行 ID\*\*：\s*([A-Za-z0-9._-]+)")

with open(path, encoding="utf-8") as f:
    for line in f:
        match = pattern.search(line)
        if match:
            print(match.group(1))
            break
PY
}

prism_ensure_run_layout() {
    local run_id="$1"
    local run_dir

    run_dir=$(prism_run_dir "$run_id") || return 1
    mkdir -p \
        "$run_dir/collect" \
        "$run_dir/synthesize" \
        "$run_dir/audit" \
        "$run_dir/artifacts" || return 1
    chmod 700 \
        "$run_dir" \
        "$run_dir/collect" \
        "$run_dir/synthesize" \
        "$run_dir/audit" \
        "$run_dir/artifacts" 2>/dev/null || return 1
}

prism_init_registry_unlocked() {
    local run_id="$1"
    local mode="$2"
    local registry_file existing_run_id existing_mode

    if [[ -z "$run_id" || -z "$mode" ]]; then
        return 1
    fi

    prism_ensure_run_layout "$run_id" || return 1
    registry_file=$(prism_run_registry_file "$run_id") || return 1

    if [[ -f "$registry_file" ]]; then
        existing_run_id=$(prism_registry_run_id "$registry_file" 2>/dev/null || true)
        existing_mode=$(prism_registry_mode "$registry_file" 2>/dev/null || true)
        if [[ "$existing_run_id" != "$run_id" ]]; then
            return 1
        fi
        if [[ -n "$existing_mode" && "$existing_mode" != "$mode" ]]; then
            return 1
        fi
        return 0
    fi

    {
        printf 'run_id: "%s"\n' "$run_id"
        printf 'mode: "%s"\n' "$mode"
        printf 'agents: []\n'
    } > "$registry_file" || return 1
    chmod 600 "$registry_file" 2>/dev/null || return 1
}

prism_init_registry() {
    local run_id="$1"
    local mode="$2"

    prism_with_run_lock "$run_id" prism_init_registry_unlocked "$run_id" "$mode"
}

prism_run_owner_matches_runtime() {
    local owner_file="$1"
    local owner_session_id owner_binding_key owner_project_hash owner_host

    if [[ -z "${REDCAP_RUNTIME_SESSION_ID:-}" || -z "${REDCAP_RUNTIME_BINDING_KEY:-}" || -z "${REDCAP_RUNTIME_PROJECT_HASH:-}" || -z "${REDCAP_RUNTIME_HOST:-}" ]]; then
        return 1
    fi

    owner_session_id=$(redcap_runtime_read_owner_field "$owner_file" "runtime_session_id" 2>/dev/null || true)
    owner_binding_key=$(redcap_runtime_read_owner_field "$owner_file" "session_binding_key" 2>/dev/null || true)
    owner_project_hash=$(redcap_runtime_read_owner_field "$owner_file" "project_hash" 2>/dev/null || true)
    owner_host=$(redcap_runtime_read_owner_field "$owner_file" "host" 2>/dev/null || true)

    [[ "$owner_session_id" == "${REDCAP_RUNTIME_SESSION_ID:-}" ]] &&
        [[ "$owner_binding_key" == "${REDCAP_RUNTIME_BINDING_KEY:-}" ]] &&
        [[ "$owner_project_hash" == "${REDCAP_RUNTIME_PROJECT_HASH:-}" ]] &&
        [[ "$owner_host" == "${REDCAP_RUNTIME_HOST:-}" ]]
}

prism_write_run_owner_file_unlocked() {
    local run_id="$1"
    local owner_file registry_file created_at
    local runtime_session_id session_binding_key project_hash host

    runtime_session_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    session_binding_key="${REDCAP_RUNTIME_BINDING_KEY:-}"
    project_hash="${REDCAP_RUNTIME_PROJECT_HASH:-}"
    host="${REDCAP_RUNTIME_HOST:-}"
    created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    if [[ -z "$run_id" || -z "$runtime_session_id" || -z "$session_binding_key" || -z "$project_hash" || -z "$host" ]]; then
        return 1
    fi

    prism_ensure_run_layout "$run_id" || return 1
    registry_file=$(prism_run_registry_file "$run_id") || return 1
    [[ -f "$registry_file" ]] || return 1
    owner_file=$(prism_run_owner_file "$run_id") || return 1
    if [[ -f "$owner_file" ]] && ! prism_run_owner_matches_runtime "$owner_file"; then
        return 1
    fi

    python3 - "$owner_file" \
        "$run_id" \
        "$runtime_session_id" \
        "$session_binding_key" \
        "$project_hash" \
        "$host" \
        "$created_at" <<'PY'
import json
import sys

path = sys.argv[1]
data = {
    "run_id": sys.argv[2],
    "runtime_session_id": sys.argv[3],
    "session_binding_key": sys.argv[4],
    "project_hash": sys.argv[5],
    "host": sys.argv[6],
    "created_at": sys.argv[7],
}

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
PY
    chmod 600 "$owner_file" 2>/dev/null || return 1
}

prism_write_run_owner_file() {
    local run_id="$1"

    prism_with_run_lock "$run_id" prism_write_run_owner_file_unlocked "$run_id"
}

prism_validate_registry_agent_args() {
    local role="$1"
    local handle_type="$2"
    local injection_mode="$3"
    local status="$4"
    local schema_ok="$5"

    prism_validate_role "$role" || return 1

    case "$handle_type" in
        task_agent|cli_session|shell) ;;
        *) return 1 ;;
    esac

    case "$injection_mode" in
        native|prefixed) ;;
        *) return 1 ;;
    esac

    case "$status" in
        dispatched|responded|absent|followed_up) ;;
        *) return 1 ;;
    esac

    case "$schema_ok" in
        null|true|false) ;;
        *) return 1 ;;
    esac
}

prism_validate_collect_result_args() {
    local status="$1"
    local schema_ok="$2"

    case "$status" in
        responded|followed_up)
            [[ "$schema_ok" == "true" ]]
            ;;
        absent)
            [[ "$schema_ok" == "false" ]]
            ;;
        *)
            return 1
            ;;
    esac
}

prism_collect_transition_allowed() {
    local mode="$1"
    local round="$2"
    local current_status="$3"
    local next_status="$4"

    case "${current_status}:${next_status}" in
        dispatched:responded|dispatched:followed_up|dispatched:absent) return 0 ;;
        responded:responded|followed_up:followed_up|absent:absent) return 0 ;;
        responded:followed_up|responded:absent|followed_up:absent)
            [[ "$mode" == "council" ]] && [[ "$round" =~ ^[2-9][0-9]*$ ]]
            ;;
        *) return 1 ;;
    esac
}

prism_upsert_registry_agent_unlocked() {
    local run_id="$1"
    local mode="$2"
    local role="$3"
    local handle_type="$4"
    local handle="$5"
    local model="$6"
    local family="$7"
    local injection_mode="$8"
    local status="$9"
    local schema_ok="${10:-null}"
    local registry_file

    if [[ -z "$run_id" || -z "$mode" || -z "$role" || -z "$handle_type" || -z "$handle" || -z "$model" || -z "$family" || -z "$injection_mode" || -z "$status" ]]; then
        return 1
    fi

    prism_validate_registry_agent_args "$role" "$handle_type" "$injection_mode" "$status" "$schema_ok" || return 1
    prism_init_registry_unlocked "$run_id" "$mode" || return 1
    registry_file=$(prism_run_registry_file "$run_id") || return 1

    python3 - "$registry_file" \
        "$run_id" \
        "$mode" \
        "$role" \
        "$handle_type" \
        "$handle" \
        "$model" \
        "$family" \
        "$injection_mode" \
        "$status" \
        "$schema_ok" <<'PY'
import os
import re
import sys

path, run_id, mode, role, handle_type, handle, model, family, injection_mode, status, schema_ok = sys.argv[1:]

ALLOWED_HANDLE_TYPES = {"task_agent", "cli_session", "shell"}
ALLOWED_INJECTION_MODES = {"native", "prefixed"}
ALLOWED_STATUSES = {"dispatched", "responded", "absent", "followed_up"}
ALLOWED_SCHEMA = {"null", "true", "false"}

if handle_type not in ALLOWED_HANDLE_TYPES:
    raise SystemExit(1)
if injection_mode not in ALLOWED_INJECTION_MODES:
    raise SystemExit(1)
if status not in ALLOWED_STATUSES:
    raise SystemExit(1)
if schema_ok not in ALLOWED_SCHEMA:
    raise SystemExit(1)

def strip_value(value: str) -> str:
    return value.strip().strip('"')

def parse_registry(registry_path: str):
    data = {"run_id": "", "mode": "", "agents": []}
    if not os.path.exists(registry_path):
        return data

    current = None
    with open(registry_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line == "agents: []":
                data["agents"] = []
                continue
            match = re.match(r"^run_id:\s*(.+)$", line)
            if match:
                data["run_id"] = strip_value(match.group(1))
                continue
            match = re.match(r"^mode:\s*(.+)$", line)
            if match:
                data["mode"] = strip_value(match.group(1))
                continue
            match = re.match(r"^\s*-\s+handle_type:\s*(.+)$", line)
            if match:
                if current is not None:
                    data["agents"].append(current)
                current = {"handle_type": strip_value(match.group(1))}
                continue
            match = re.match(r"^\s+([A-Za-z_]+):\s*(.*)$", line)
            if match and current is not None:
                current[match.group(1)] = strip_value(match.group(2))
        if current is not None:
            data["agents"].append(current)
    return data

def yaml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'

def write_registry(registry_path: str, data):
    agents = data.get("agents", [])
    with open(registry_path, "w", encoding="utf-8") as f:
        f.write(f'run_id: {yaml_string(data["run_id"])}\n')
        f.write(f'mode: {yaml_string(data["mode"])}\n')
        if not agents:
            f.write("agents: []\n")
            return
        f.write("agents:\n")
        for agent in agents:
            f.write(f'  - handle_type: {yaml_string(agent.get("handle_type", ""))}\n')
            f.write(f'    handle: {yaml_string(agent.get("handle", ""))}\n')
            f.write(f'    role: {yaml_string(agent.get("role", ""))}\n')
            f.write(f'    model: {yaml_string(agent.get("model", ""))}\n')
            f.write(f'    family: {yaml_string(agent.get("family", ""))}\n')
            f.write(f'    injection_mode: {yaml_string(agent.get("injection_mode", ""))}\n')
            f.write(f'    status: {yaml_string(agent.get("status", ""))}\n')
            schema_value = agent.get("schema_ok", "null")
            if schema_value not in ALLOWED_SCHEMA:
                schema_value = "null"
            f.write(f'    schema_ok: {schema_value}\n')

data = parse_registry(path)
if data["run_id"] and data["run_id"] != run_id:
    raise SystemExit(1)
if data["mode"] and data["mode"] != mode:
    raise SystemExit(1)
data["run_id"] = run_id
data["mode"] = mode

agent = {
    "handle_type": handle_type,
    "handle": handle,
    "role": role,
    "model": model,
    "family": family,
    "injection_mode": injection_mode,
    "status": status,
    "schema_ok": schema_ok,
}

for index, existing in enumerate(data["agents"]):
    if existing.get("role") == role:
        data["agents"][index] = agent
        break
else:
    data["agents"].append(agent)

write_registry(path, data)
PY
    chmod 600 "$registry_file" 2>/dev/null || return 1
}

prism_record_collect_result_unlocked() {
    local run_id="$1"
    local mode="$2"
    local role="$3"
    local status="$4"
    local schema_ok="$5"
    local round="${6:-1}"
    local agent_exports=""

    if [[ -z "$run_id" || -z "$mode" || -z "$role" || -z "$status" || -z "$schema_ok" || -z "$round" ]]; then
        return 1
    fi

    prism_validate_role "$role" || return 1
    prism_validate_collect_result_args "$status" "$schema_ok" || return 1
    [[ "$round" =~ ^[1-9][0-9]*$ ]] || return 1
    agent_exports=$(prism_export_registry_agent_for_role "$run_id" "$role") || return 1
    eval "$agent_exports"

    if [[ -z "${PRISM_AGENT_HANDLE_TYPE:-}" || -z "${PRISM_AGENT_HANDLE:-}" || -z "${PRISM_AGENT_MODEL:-}" || -z "${PRISM_AGENT_FAMILY:-}" || -z "${PRISM_AGENT_INJECTION_MODE:-}" ]]; then
        return 1
    fi

    if ! prism_collect_transition_allowed "$mode" "$round" "${PRISM_AGENT_STATUS:-}" "$status"; then
        return 1
    fi

    prism_upsert_registry_agent_unlocked \
        "$run_id" \
        "$mode" \
        "$role" \
        "$PRISM_AGENT_HANDLE_TYPE" \
        "$PRISM_AGENT_HANDLE" \
        "$PRISM_AGENT_MODEL" \
        "$PRISM_AGENT_FAMILY" \
        "$PRISM_AGENT_INJECTION_MODE" \
        "$status" \
        "$schema_ok"
}

prism_record_collect_result() {
    local run_id="$1"
    local mode="$2"
    local role="$3"
    local status="$4"
    local schema_ok="$5"
    local round="${6:-1}"

    prism_with_run_lock \
        "$run_id" \
        prism_record_collect_result_unlocked \
        "$run_id" \
        "$mode" \
        "$role" \
        "$status" \
        "$schema_ok" \
        "$round"
}

prism_upsert_registry_agent() {
    local run_id="$1"
    local mode="$2"
    local role="$3"
    local handle_type="$4"
    local handle="$5"
    local model="$6"
    local family="$7"
    local injection_mode="$8"
    local status="$9"
    local schema_ok="${10:-null}"

    if [[ -z "$run_id" || -z "$mode" || -z "$role" || -z "$handle_type" || -z "$handle" || -z "$model" || -z "$family" || -z "$injection_mode" || -z "$status" ]]; then
        return 1
    fi

    prism_validate_registry_agent_args "$role" "$handle_type" "$injection_mode" "$status" "$schema_ok" || return 1
    prism_with_run_lock \
        "$run_id" \
        prism_upsert_registry_agent_unlocked \
        "$run_id" \
        "$mode" \
        "$role" \
        "$handle_type" \
        "$handle" \
        "$model" \
        "$family" \
        "$injection_mode" \
        "$status" \
        "$schema_ok"
}

prism_resolve_registry_file_for_run_id() {
    local run_id="$1"
    local detail="${2:-}"
    local registry_file legacy_file legacy_run_id

    PRISM_RESOLVED_RUN_ID=""
    PRISM_RESOLVED_REGISTRY_FILE=""
    PRISM_RESOLVED_REGISTRY_SOURCE=""

    if [[ -z "$run_id" ]]; then
        return 1
    fi

    registry_file=$(prism_run_registry_file "$run_id") || return 1
    if [[ -f "$registry_file" ]]; then
        PRISM_RESOLVED_RUN_ID="$run_id"
        PRISM_RESOLVED_REGISTRY_FILE="$registry_file"
        PRISM_RESOLVED_REGISTRY_SOURCE="run-scoped"
        printf '%s\n' "$registry_file"
        return 0
    fi

    legacy_file=$(prism_legacy_registry_file)
    if [[ -f "$legacy_file" ]]; then
        legacy_run_id=$(prism_registry_run_id "$legacy_file" 2>/dev/null || true)
        if [[ "$legacy_run_id" == "$run_id" ]]; then
            redcap_runtime_record_legacy_hit "$REDCAP_ROOT" "prism-run-registry-legacy-bridge" "$detail" || true
            PRISM_RESOLVED_RUN_ID="$run_id"
            PRISM_RESOLVED_REGISTRY_FILE="$legacy_file"
            PRISM_RESOLVED_REGISTRY_SOURCE="legacy-bridge"
            printf '%s\n' "$legacy_file"
            return 0
        fi
    fi

    return 1
}

prism_resolve_registry_file_for_report() {
    local report_file="$1"
    local report_run_id detail

    report_run_id=$(prism_extract_report_run_id "$report_file" 2>/dev/null || true)
    if [[ -z "$report_run_id" ]]; then
        return 1
    fi

    detail="run_id=$report_run_id report=$(basename "$report_file")"
    prism_resolve_registry_file_for_run_id "$report_run_id" "$detail"
}

prism_run_state_main() {
    local command="${1:-}"

    case "$command" in
        run-dir)
            [[ $# -eq 2 ]] || return 1
            prism_run_dir "$2"
            ;;
        registry-file)
            [[ $# -eq 2 ]] || return 1
            prism_run_registry_file "$2"
            ;;
        init-registry)
            shift
            local run_id=""
            local mode=""
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --run-id)
                        [[ $# -ge 2 ]] || return 1
                        run_id="$2"
                        shift 2
                        ;;
                    --mode)
                        [[ $# -ge 2 ]] || return 1
                        mode="$2"
                        shift 2
                        ;;
                    *) echo "Unknown arg: $1" >&2; return 1 ;;
                esac
            done
            prism_init_registry "$run_id" "$mode"
            ;;
        upsert-agent)
            shift
            local run_id=""
            local mode=""
            local role=""
            local handle_type=""
            local handle=""
            local model=""
            local family=""
            local injection_mode=""
            local status=""
            local schema_ok="null"
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --run-id)
                        [[ $# -ge 2 ]] || return 1
                        run_id="$2"
                        shift 2
                        ;;
                    --mode)
                        [[ $# -ge 2 ]] || return 1
                        mode="$2"
                        shift 2
                        ;;
                    --role)
                        [[ $# -ge 2 ]] || return 1
                        role="$2"
                        shift 2
                        ;;
                    --handle-type)
                        [[ $# -ge 2 ]] || return 1
                        handle_type="$2"
                        shift 2
                        ;;
                    --handle)
                        [[ $# -ge 2 ]] || return 1
                        handle="$2"
                        shift 2
                        ;;
                    --model)
                        [[ $# -ge 2 ]] || return 1
                        model="$2"
                        shift 2
                        ;;
                    --family)
                        [[ $# -ge 2 ]] || return 1
                        family="$2"
                        shift 2
                        ;;
                    --injection-mode)
                        [[ $# -ge 2 ]] || return 1
                        injection_mode="$2"
                        shift 2
                        ;;
                    --status)
                        [[ $# -ge 2 ]] || return 1
                        status="$2"
                        shift 2
                        ;;
                    --schema-ok)
                        [[ $# -ge 2 ]] || return 1
                        schema_ok="$2"
                        shift 2
                        ;;
                    *) echo "Unknown arg: $1" >&2; return 1 ;;
                esac
            done
            prism_upsert_registry_agent \
                "$run_id" \
                "$mode" \
                "$role" \
                "$handle_type" \
                "$handle" \
                "$model" \
                "$family" \
                "$injection_mode" \
                "$status" \
                "$schema_ok"
            ;;
        write-owner)
            shift
            local run_id=""
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --run-id)
                        [[ $# -ge 2 ]] || return 1
                        run_id="$2"
                        shift 2
                        ;;
                    *) echo "Unknown arg: $1" >&2; return 1 ;;
                esac
            done
            prism_write_run_owner_file "$run_id"
            ;;
        resolve-registry)
            shift
            local run_id=""
            local report_file=""
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --run-id)
                        [[ $# -ge 2 ]] || return 1
                        run_id="$2"
                        shift 2
                        ;;
                    --report)
                        [[ $# -ge 2 ]] || return 1
                        report_file="$2"
                        shift 2
                        ;;
                    *) echo "Unknown arg: $1" >&2; return 1 ;;
                esac
            done
            if [[ -n "$report_file" ]]; then
                prism_resolve_registry_file_for_report "$report_file"
            else
                prism_resolve_registry_file_for_run_id "$run_id"
            fi
            ;;
        *)
            echo "usage: $0 <run-dir|registry-file|init-registry|upsert-agent|write-owner|resolve-registry> ..." >&2
            return 1
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    prism_run_state_main "$@"
fi

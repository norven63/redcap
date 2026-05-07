#!/usr/bin/env bash
# 用途：棱镜与 Agent 路由脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#prism-and-providers

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/prism-run-state.sh"

prism_coordinator_usage() {
    cat <<'EOF' >&2
usage:
  bash prism/tools/prism-coordinator.sh start-run --mode <mode> --run-id <run_id>
  bash prism/tools/prism-coordinator.sh register-agent --run-id <run_id> --mode <mode> --role <role> --handle-type <type> --handle <handle> --model <model> --family <family> --injection-mode <mode>
  bash prism/tools/prism-coordinator.sh record-collect --run-id <run_id> --mode <mode> --role <role> --status <status> --schema-ok <true|false> [--round <n>] [--raw-file <path>] [--parsed-file <path>] [--meta-file <path>]
  bash prism/tools/prism-coordinator.sh resolve-handle --run-id <run_id> --role <role>
EOF
}

prism_coordinator_try_env_attach() {
    if [[ -z "${REDCAP_RUNTIME_SESSION_ID:-}" || -z "${REDCAP_RUNTIME_CAPABILITY:-}" ]]; then
        return 1
    fi

    redcap_runtime_attach_existing "$REDCAP_RUNTIME_SESSION_ID" "$REDCAP_RUNTIME_CAPABILITY" >/dev/null 2>&1
}

prism_coordinator_attach_from_process_claim_chain() {
    local claim_base_dir claim_dir host
    local preserved_host_pid="${REDCAP_HOST_PROCESS_PID:-}"
    local preserved_host_probe_pid="${REDCAP_HOST_PROCESS_PROBE_PID:-}"

    claim_base_dir=$(redcap_runtime_process_claim_base_dir)
    if [[ ! -d "$claim_base_dir" ]]; then
        return 1
    fi

    for claim_dir in "$claim_base_dir"/*; do
        if [[ ! -d "$claim_dir" ]]; then
            continue
        fi

        host=$(basename "$claim_dir")
        if redcap_runtime_attach_from_process_claim "$host" >/dev/null 2>&1; then
            return 0
        fi
        redcap_runtime_clear_context
        if [[ -n "$preserved_host_pid" ]]; then
            export REDCAP_HOST_PROCESS_PID="$preserved_host_pid"
        fi
        if [[ -n "$preserved_host_probe_pid" ]]; then
            export REDCAP_HOST_PROCESS_PROBE_PID="$preserved_host_probe_pid"
        fi
    done

    return 1
}

prism_coordinator_attach_runtime_context() {
    local preserved_host_pid="${REDCAP_HOST_PROCESS_PID:-}"
    local preserved_host_probe_pid="${REDCAP_HOST_PROCESS_PROBE_PID:-}"

    if prism_coordinator_try_env_attach; then
        return 0
    fi

    redcap_runtime_clear_context
    if [[ -n "$preserved_host_pid" ]]; then
        export REDCAP_HOST_PROCESS_PID="$preserved_host_pid"
    fi
    if [[ -n "$preserved_host_probe_pid" ]]; then
        export REDCAP_HOST_PROCESS_PROBE_PID="$preserved_host_probe_pid"
    fi
    prism_coordinator_attach_from_process_claim_chain
}

prism_coordinator_run_owner_matches_runtime() {
    local run_id="$1"
    local owner_file

    owner_file=$(prism_run_owner_file "$run_id") || return 1
    [[ -f "$owner_file" ]] || return 1
    prism_run_owner_matches_runtime "$owner_file"
}

prism_coordinator_require_run_owner() {
    local run_id="$1"
    local owner_file

    prism_coordinator_attach_runtime_context || return 1
    owner_file=$(prism_run_owner_file "$run_id") || return 1

    [[ -f "$owner_file" ]] || return 1
    prism_coordinator_run_owner_matches_runtime "$run_id"
}

prism_coordinator_emit_start_run() {
    local run_id="$1"
    local registry_file="$2"
    local owner_written="$3"

    printf 'RUN_ID=%s\n' "$run_id"
    printf 'REGISTRY_FILE=%s\n' "$registry_file"
    printf 'OWNER_WRITTEN=%s\n' "$owner_written"
    if [[ "$owner_written" == "1" ]]; then
        printf 'OWNER_FILE=%s\n' "$(prism_run_owner_file "$run_id")"
    fi
}

prism_coordinator_start_run_locked() {
    local run_id="$1"
    local mode="$2"
    local registry_file owner_file owner_written="0"

    if [[ -z "$run_id" || -z "$mode" ]]; then
        return 1
    fi

    prism_init_registry_unlocked "$run_id" "$mode"
    if prism_coordinator_attach_runtime_context; then
        owner_file=$(prism_run_owner_file "$run_id") || return 1
        if [[ -f "$owner_file" ]]; then
            prism_coordinator_run_owner_matches_runtime "$run_id" || return 1
        else
            prism_write_run_owner_file_unlocked "$run_id"
            owner_written="1"
        fi
    fi

    registry_file=$(prism_run_registry_file "$run_id")
    prism_coordinator_emit_start_run "$run_id" "$registry_file" "$owner_written"
}

prism_coordinator_start_run() {
    local run_id="$1"
    local mode="$2"

    prism_with_run_lock "$run_id" prism_coordinator_start_run_locked "$run_id" "$mode"
}

prism_coordinator_require_existing_run() {
    local run_id="$1"
    local registry_file

    registry_file=$(prism_run_registry_file "$run_id") || return 1
    [[ -f "$registry_file" ]]
}

prism_coordinator_register_agent_locked() {
    local run_id="$1"
    local mode="$2"
    local role="$3"
    local handle_type="$4"
    local handle="$5"
    local model="$6"
    local family="$7"
    local injection_mode="$8"

    if [[ -z "$run_id" || -z "$mode" || -z "$role" || -z "$handle_type" || -z "$handle" || -z "$model" || -z "$family" || -z "$injection_mode" ]]; then
        return 1
    fi

    prism_coordinator_require_existing_run "$run_id" || return 1
    prism_coordinator_require_run_owner "$run_id" || return 1
    prism_upsert_registry_agent_unlocked \
        "$run_id" \
        "$mode" \
        "$role" \
        "$handle_type" \
        "$handle" \
        "$model" \
        "$family" \
        "$injection_mode" \
        "dispatched" \
        "null"
}

prism_coordinator_register_agent() {
    local run_id="$1"
    local mode="$2"
    local role="$3"
    local handle_type="$4"
    local handle="$5"
    local model="$6"
    local family="$7"
    local injection_mode="$8"
    local registry_file

    prism_with_run_lock \
        "$run_id" \
        prism_coordinator_register_agent_locked \
        "$run_id" \
        "$mode" \
        "$role" \
        "$handle_type" \
        "$handle" \
        "$model" \
        "$family" \
        "$injection_mode" || return 1

    registry_file=$(prism_run_registry_file "$run_id")
    printf 'RUN_ID=%s\n' "$run_id"
    printf 'ROLE=%s\n' "$role"
    printf 'STATUS=dispatched\n'
    printf 'REGISTRY_FILE=%s\n' "$registry_file"
}

prism_coordinator_validate_json_file() {
    local path="$1"
    local kind="${2:-any}"

    python3 - "$path" "$kind" <<'PY'
import json
import sys

path = sys.argv[1]
kind = sys.argv[2]

with open(path, encoding="utf-8") as f:
    data = json.load(f)

if kind == "object" and not isinstance(data, dict):
    raise SystemExit(1)
PY
}

prism_coordinator_validate_positive_integer() {
    local value="$1"

    [[ "$value" =~ ^[1-9][0-9]*$ ]]
}

prism_coordinator_copy_collect_file() {
    local source_file="$1"
    local target_file="$2"
    local json_kind="${3:-}"
    local target_dir tmp_file

    [[ -n "$source_file" ]] || return 0
    [[ -f "$source_file" ]] || return 1

    if [[ -n "$json_kind" ]]; then
        prism_coordinator_validate_json_file "$source_file" "$json_kind" || return 1
    fi

    target_dir=$(dirname "$target_file")
    mkdir -p "$target_dir" || return 1
    chmod 700 "$target_dir" 2>/dev/null || return 1

    tmp_file="$target_file.tmp.$$"
    cp "$source_file" "$tmp_file" || {
        rm -f "$tmp_file" 2>/dev/null || true
        return 1
    }
    chmod 600 "$tmp_file" 2>/dev/null || {
        rm -f "$tmp_file" 2>/dev/null || true
        return 1
    }
    mv -f "$tmp_file" "$target_file" || {
        rm -f "$tmp_file" 2>/dev/null || true
        return 1
    }
}

prism_coordinator_write_collect_meta() {
    local target_file="$1"
    local meta_file="${2:-}"
    local run_id="$3"
    local role="$4"
    local status="$5"
    local schema_ok="$6"
    local round="$7"
    local collected_at="$8"
    local target_dir tmp_file

    target_dir=$(dirname "$target_file")
    mkdir -p "$target_dir" || return 1
    chmod 700 "$target_dir" 2>/dev/null || return 1
    tmp_file="$target_file.tmp.$$"

    python3 - "$tmp_file" \
        "$meta_file" \
        "$run_id" \
        "$role" \
        "$status" \
        "$schema_ok" \
        "$round" \
        "$collected_at" \
        "${PRISM_AGENT_HANDLE:-}" \
        "${PRISM_AGENT_HANDLE_TYPE:-}" \
        "${PRISM_AGENT_MODEL:-}" \
        "${PRISM_AGENT_FAMILY:-}" \
        "${PRISM_AGENT_INJECTION_MODE:-}" <<'PY'
import json
import os
import sys

target, meta_file, run_id, role, status, schema_ok, round_value, collected_at, handle, handle_type, model, family, injection_mode = sys.argv[1:]

payload = {}
if meta_file:
    with open(meta_file, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise SystemExit(1)

payload.update({
    "run_id": run_id,
    "role": role,
    "status": status,
    "schema_ok": schema_ok == "true",
    "round": int(round_value),
    "collected_at": collected_at,
    "source_handle": handle,
    "source_handle_type": handle_type,
    "source_model": model,
    "source_family": family,
    "injection_mode": injection_mode,
})

with open(target, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
PY
    chmod 600 "$tmp_file" 2>/dev/null || {
        rm -f "$tmp_file" 2>/dev/null || true
        return 1
    }
    mv -f "$tmp_file" "$target_file" || {
        rm -f "$tmp_file" 2>/dev/null || true
        return 1
    }
}

prism_coordinator_restore_collect_dir() {
    local collect_dir="$1"
    local backup_dir="$2"

    rm -rf "$collect_dir" 2>/dev/null || true
    if [[ -d "$backup_dir" ]]; then
        mv "$backup_dir" "$collect_dir" || return 1
    fi
}

prism_coordinator_record_collect_locked() {
    local run_id="$1"
    local mode="$2"
    local role="$3"
    local status="$4"
    local schema_ok="$5"
    local raw_file="${6:-}"
    local parsed_file="${7:-}"
    local meta_file="${8:-}"
    local round="${9:-1}"
    local collect_dir collect_parent staged_dir backup_dir collected_at agent_exports="" temp_suffix=""

    if [[ -z "$run_id" || -z "$mode" || -z "$role" || -z "$status" || -z "$schema_ok" ]]; then
        return 1
    fi

    prism_coordinator_require_existing_run "$run_id" || return 1
    prism_coordinator_require_run_owner "$run_id" || return 1
    prism_validate_collect_result_args "$status" "$schema_ok" || return 1
    prism_coordinator_validate_positive_integer "$round" || return 1

    case "$status" in
        responded|followed_up)
            [[ -n "$parsed_file" ]] || return 1
            ;;
    esac

    agent_exports=$(prism_export_registry_agent_for_role "$run_id" "$role") || return 1
    eval "$agent_exports"

    collect_dir=$(prism_run_collect_role_dir "$run_id" "$role") || return 1
    collect_parent=$(dirname "$collect_dir")
    mkdir -p "$collect_parent" || return 1
    chmod 700 "$collect_parent" 2>/dev/null || return 1

    temp_suffix=".$$.$RANDOM"
    staged_dir="${collect_dir}.staged${temp_suffix}"
    backup_dir="${collect_dir}.backup${temp_suffix}"
    mkdir -p "$staged_dir" || return 1
    chmod 700 "$staged_dir" 2>/dev/null || {
        rm -rf "$staged_dir" 2>/dev/null || true
        return 1
    }

    if [[ -n "$raw_file" ]]; then
        prism_coordinator_copy_collect_file "$raw_file" "$staged_dir/raw.txt" || {
            rm -rf "$staged_dir" 2>/dev/null || true
            return 1
        }
    fi
    if [[ -n "$parsed_file" ]]; then
        prism_coordinator_copy_collect_file "$parsed_file" "$staged_dir/parsed.json" "any" || {
            rm -rf "$staged_dir" 2>/dev/null || true
            return 1
        }
    fi

    collected_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    prism_coordinator_write_collect_meta \
        "$staged_dir/meta.json" \
        "$meta_file" \
        "$run_id" \
        "$role" \
        "$status" \
        "$schema_ok" \
        "$round" \
        "$collected_at" || {
        rm -rf "$staged_dir" 2>/dev/null || true
        return 1
    }

    if [[ -d "$collect_dir" ]]; then
        mv "$collect_dir" "$backup_dir" || {
            rm -rf "$staged_dir" 2>/dev/null || true
            return 1
        }
    fi
    mv "$staged_dir" "$collect_dir" || {
        rm -rf "$staged_dir" 2>/dev/null || true
        if [[ -d "$backup_dir" ]]; then
            mv "$backup_dir" "$collect_dir" || return 1
        fi
        return 1
    }

    prism_record_collect_result_unlocked "$run_id" "$mode" "$role" "$status" "$schema_ok" "$round" || {
        prism_coordinator_restore_collect_dir "$collect_dir" "$backup_dir" || return 1
        return 1
    }

    rm -rf "$backup_dir" 2>/dev/null || true
}

prism_coordinator_record_collect() {
    local run_id="$1"
    local mode="$2"
    local role="$3"
    local status="$4"
    local schema_ok="$5"
    local raw_file="${6:-}"
    local parsed_file="${7:-}"
    local meta_file="${8:-}"
    local round="${9:-1}"
    local collect_dir registry_file

    prism_with_run_lock \
        "$run_id" \
        prism_coordinator_record_collect_locked \
        "$run_id" \
        "$mode" \
        "$role" \
        "$status" \
        "$schema_ok" \
        "$raw_file" \
        "$parsed_file" \
        "$meta_file" \
        "$round" || return 1

    collect_dir=$(prism_run_collect_role_dir "$run_id" "$role") || return 1
    registry_file=$(prism_run_registry_file "$run_id") || return 1
    printf 'RUN_ID=%s\n' "$run_id"
    printf 'ROLE=%s\n' "$role"
    printf 'STATUS=%s\n' "$status"
    printf 'SCHEMA_OK=%s\n' "$schema_ok"
    printf 'ROUND=%s\n' "$round"
    printf 'COLLECT_DIR=%s\n' "$collect_dir"
    printf 'REGISTRY_FILE=%s\n' "$registry_file"
}

prism_coordinator_resolve_handle_locked() {
    local run_id="$1"
    local role="$2"
    local agent_exports=""

    if [[ -z "$run_id" || -z "$role" ]]; then
        return 1
    fi

    prism_coordinator_require_existing_run "$run_id" || return 1
    prism_coordinator_require_run_owner "$run_id" || return 1
    agent_exports=$(prism_export_registry_agent_for_role "$run_id" "$role") || return 1
    eval "$agent_exports"

    [[ -n "${PRISM_AGENT_HANDLE_TYPE:-}" && -n "${PRISM_AGENT_HANDLE:-}" ]] || return 1
    case "${PRISM_AGENT_STATUS:-}" in
        responded|followed_up) ;;
        *) return 1 ;;
    esac
    [[ "${PRISM_AGENT_SCHEMA_OK:-}" == "true" ]] || return 1

    printf 'RUN_ID=%s\n' "$run_id"
    printf 'ROLE=%s\n' "$role"
    printf 'HANDLE_TYPE=%s\n' "${PRISM_AGENT_HANDLE_TYPE:-}"
    printf 'HANDLE=%s\n' "${PRISM_AGENT_HANDLE:-}"
    printf 'MODEL=%s\n' "${PRISM_AGENT_MODEL:-}"
    printf 'FAMILY=%s\n' "${PRISM_AGENT_FAMILY:-}"
    printf 'INJECTION_MODE=%s\n' "${PRISM_AGENT_INJECTION_MODE:-}"
    printf 'STATUS=%s\n' "${PRISM_AGENT_STATUS:-}"
    printf 'SCHEMA_OK=%s\n' "${PRISM_AGENT_SCHEMA_OK:-}"
}

prism_coordinator_resolve_handle() {
    local run_id="$1"
    local role="$2"

    prism_with_run_lock \
        "$run_id" \
        prism_coordinator_resolve_handle_locked \
        "$run_id" \
        "$role"
}

prism_coordinator_main() {
    local command="${1:-}"

    case "$command" in
        start-run)
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
                    *) echo "Unknown arg: $1" >&2; prism_coordinator_usage; return 1 ;;
                esac
            done
            prism_coordinator_start_run "$run_id" "$mode"
            ;;
        register-agent)
            shift
            local run_id=""
            local mode=""
            local role=""
            local handle_type=""
            local handle=""
            local model=""
            local family=""
            local injection_mode=""
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
                    *) echo "Unknown arg: $1" >&2; prism_coordinator_usage; return 1 ;;
                esac
            done
            prism_coordinator_register_agent \
                "$run_id" \
                "$mode" \
                "$role" \
                "$handle_type" \
                "$handle" \
                "$model" \
                "$family" \
                "$injection_mode"
            ;;
        record-collect)
            shift
            local run_id=""
            local mode=""
            local role=""
            local status=""
            local schema_ok=""
            local round="1"
            local raw_file=""
            local parsed_file=""
            local meta_file=""
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
                    --round)
                        [[ $# -ge 2 ]] || return 1
                        round="$2"
                        shift 2
                        ;;
                    --raw-file)
                        [[ $# -ge 2 ]] || return 1
                        raw_file="$2"
                        shift 2
                        ;;
                    --parsed-file)
                        [[ $# -ge 2 ]] || return 1
                        parsed_file="$2"
                        shift 2
                        ;;
                    --meta-file)
                        [[ $# -ge 2 ]] || return 1
                        meta_file="$2"
                        shift 2
                        ;;
                    *) echo "Unknown arg: $1" >&2; prism_coordinator_usage; return 1 ;;
                esac
            done
            prism_coordinator_record_collect \
                "$run_id" \
                "$mode" \
                "$role" \
                "$status" \
                "$schema_ok" \
                "$raw_file" \
                "$parsed_file" \
                "$meta_file" \
                "$round"
            ;;
        resolve-handle)
            shift
            local run_id=""
            local role=""
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --run-id)
                        [[ $# -ge 2 ]] || return 1
                        run_id="$2"
                        shift 2
                        ;;
                    --role)
                        [[ $# -ge 2 ]] || return 1
                        role="$2"
                        shift 2
                        ;;
                    *) echo "Unknown arg: $1" >&2; prism_coordinator_usage; return 1 ;;
                esac
            done
            prism_coordinator_resolve_handle "$run_id" "$role"
            ;;
        *)
            prism_coordinator_usage
            return 1
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    prism_coordinator_main "$@"
fi

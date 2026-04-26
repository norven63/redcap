#!/usr/bin/env bash
# shellcheck shell=bash
# Validate .dev-task.md and stamp canonical task metadata into runtime state.

set -uo pipefail

MODE="${1:-session-start}"
HOST="${2:-}"
TASK_FILE="${3:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/redcap-runtime-state.sh"
source "$SCRIPT_DIR/redcap-dev-task.sh"

TASK_FILE=$(redcap_dev_task_resolve_file "$TASK_FILE")

STRICT=1
case "$MODE" in
    session-start)
        STRICT=0
        ;;
    reread|stop-review|session-end|strict)
        STRICT=1
        ;;
    *)
        echo "usage: $0 <session-start|reread|stop-review|session-end|strict> [host] [task_file]" >&2
        exit 2
        ;;
esac

TASK_ID=""
TOP_GOAL=""
ACTIVE_SLICE=""
SUBTASK_OF=""
SOURCE_OF_TRUTH=""
HOST_SURFACE_POLICY=""
DELEGATION_BOUNDARY=""
BACKLOG_SOURCE=""
BACKLOG_ID=""
BACKLOG_ITEM=""
CONFIRMED_HASH=""
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ERRORS=()

record_error() {
    ERRORS+=("$1")
}

task_exists() {
    [[ -f "$TASK_FILE" ]]
}

if ! task_exists; then
    record_error "missing canonical task ledger: $TASK_FILE"
else
    [[ -n "$(redcap_dev_task_extract_section "$TASK_FILE" "原始输入" 2>/dev/null || true)" ]] || record_error "missing section: ## 原始输入"
    [[ -n "$(redcap_dev_task_extract_section "$TASK_FILE" "已确认需求" 2>/dev/null || true)" ]] || record_error "missing section: ## 已确认需求"
    [[ -n "$(redcap_dev_task_metadata_section "$TASK_FILE" 2>/dev/null || true)" ]] || record_error "missing section: ## 控制面元数据"
    [[ -n "$(redcap_dev_task_extract_section "$TASK_FILE" "漂移哨兵" 2>/dev/null || true)" ]] || record_error "missing section: ## 漂移哨兵"
    [[ -n "$(redcap_dev_task_extract_section "$TASK_FILE" "允许修改范围" 2>/dev/null || true)" ]] || record_error "missing section: ## 允许修改范围"

    TASK_ID=$(redcap_dev_task_extract_kv "$TASK_FILE" "task_id" 2>/dev/null || true)
    TOP_GOAL=$(redcap_dev_task_extract_kv "$TASK_FILE" "top_goal" 2>/dev/null || true)
    ACTIVE_SLICE=$(redcap_dev_task_extract_kv "$TASK_FILE" "active_slice" 2>/dev/null || true)
    SUBTASK_OF=$(redcap_dev_task_extract_kv "$TASK_FILE" "subtask_of" 2>/dev/null || true)
    SOURCE_OF_TRUTH=$(redcap_dev_task_extract_kv "$TASK_FILE" "source_of_truth" 2>/dev/null || true)
    HOST_SURFACE_POLICY=$(redcap_dev_task_extract_kv "$TASK_FILE" "host_surface_policy" 2>/dev/null || true)
    DELEGATION_BOUNDARY=$(redcap_dev_task_extract_kv "$TASK_FILE" "delegation_boundary" 2>/dev/null || true)
    BACKLOG_SOURCE=$(redcap_dev_task_extract_kv "$TASK_FILE" "backlog_source" 2>/dev/null || true)
    BACKLOG_ID=$(redcap_dev_task_extract_kv "$TASK_FILE" "backlog_id" 2>/dev/null || true)
    BACKLOG_ITEM=$(redcap_dev_task_extract_kv "$TASK_FILE" "backlog_item" 2>/dev/null || true)
    CONFIRMED_HASH=$(redcap_dev_task_confirmed_hash "$TASK_FILE" 2>/dev/null || true)

    [[ -n "$TASK_ID" ]] || record_error "missing metadata key: task_id"
    [[ -n "$TOP_GOAL" ]] || record_error "missing metadata key: top_goal"
    [[ -n "$ACTIVE_SLICE" ]] || record_error "missing metadata key: active_slice"
    [[ -n "$SOURCE_OF_TRUTH" ]] || record_error "missing metadata key: source_of_truth"
    [[ -n "$HOST_SURFACE_POLICY" ]] || record_error "missing metadata key: host_surface_policy"
    [[ -n "$DELEGATION_BOUNDARY" ]] || record_error "missing metadata key: delegation_boundary"
    [[ -n "$CONFIRMED_HASH" ]] || record_error "failed to hash ## 已确认需求"

    if [[ -n "$SOURCE_OF_TRUTH" && "$SOURCE_OF_TRUTH" != ".dev-task.md" ]]; then
        record_error "source_of_truth must remain .dev-task.md (got: $SOURCE_OF_TRUTH)"
    fi
    if [[ -n "$HOST_SURFACE_POLICY" && "$HOST_SURFACE_POLICY" != "mirror_only" ]]; then
        record_error "host_surface_policy must be mirror_only (got: $HOST_SURFACE_POLICY)"
    fi
    if [[ -n "$TOP_GOAL" && -n "$ACTIVE_SLICE" && "$TOP_GOAL" != "$ACTIVE_SLICE" && -z "$SUBTASK_OF" ]]; then
        record_error "subtask_of is required when active_slice differs from top_goal"
    fi
    if [[ -n "$BACKLOG_SOURCE" || -n "$BACKLOG_ID" || -n "$BACKLOG_ITEM" ]]; then
        [[ -n "$BACKLOG_SOURCE" ]] || record_error "missing metadata key: backlog_source"
        [[ -n "$BACKLOG_ID" ]] || record_error "missing metadata key: backlog_id"
        [[ -n "$BACKLOG_ITEM" ]] || record_error "missing metadata key: backlog_item"
        if [[ -n "$BACKLOG_SOURCE" && -n "$BACKLOG_ID" && -n "$BACKLOG_ITEM" ]]; then
            BACKLOG_CHECK_OUTPUT=$(bash "$SCRIPT_DIR/redcap-backlog-check.sh" anchor "$TASK_FILE" 2>&1) || record_error "$BACKLOG_CHECK_OUTPUT"
        fi
    fi

    if [[ -x "$SCRIPT_DIR/redcap-intent-coverage-check.sh" ]]; then
        INTENT_COVERAGE_OUTPUT=$(bash "$SCRIPT_DIR/redcap-intent-coverage-check.sh" "$TASK_FILE" 2>&1) || record_error "$INTENT_COVERAGE_OUTPUT"
    else
        record_error "missing intent coverage gate: compass/tools/redcap-intent-coverage-check.sh"
    fi

    if [[ -f "$SCRIPT_DIR/redcap-change-intake-check.sh" ]]; then
        CHANGE_INTAKE_OUTPUT=$(bash "$SCRIPT_DIR/redcap-change-intake-check.sh" "$TASK_FILE" 2>&1) || record_error "$CHANGE_INTAKE_OUTPUT"
    else
        record_error "missing change-intake gate: compass/tools/redcap-change-intake-check.sh"
    fi
fi

if [[ ${#ERRORS[@]} -gt 0 ]]; then
    {
        echo "[redcap-pm-gate-check] ${MODE}: invalid Layer B canonical task ledger"
        for item in "${ERRORS[@]}"; do
            echo "  - $item"
        done
    } >&2

    if [[ "$STRICT" == "1" ]]; then
        exit 1
    fi
    exit 0
fi

if redcap_runtime_attach_current_or_claim "$HOST"; then
    redcap_runtime_write_text "layerB/control-plane/task-id" "$TASK_ID" || true
    redcap_runtime_write_text "layerB/control-plane/task-file" "$TASK_FILE" || true
    redcap_runtime_write_text "layerB/control-plane/top-goal" "$TOP_GOAL" || true
    redcap_runtime_write_text "layerB/control-plane/active-slice" "$ACTIVE_SLICE" || true
    redcap_runtime_write_text "layerB/control-plane/subtask-of" "$SUBTASK_OF" || true
    redcap_runtime_write_text "layerB/control-plane/source-of-truth" "$SOURCE_OF_TRUTH" || true
    redcap_runtime_write_text "layerB/control-plane/host-surface-policy" "$HOST_SURFACE_POLICY" || true
    redcap_runtime_write_text "layerB/control-plane/delegation-boundary" "$DELEGATION_BOUNDARY" || true
    redcap_runtime_write_text "layerB/control-plane/backlog-source" "$BACKLOG_SOURCE" || true
    redcap_runtime_write_text "layerB/control-plane/backlog-id" "$BACKLOG_ID" || true
    redcap_runtime_write_text "layerB/control-plane/backlog-item" "$BACKLOG_ITEM" || true
    redcap_runtime_write_text "layerB/control-plane/confirmed.hash" "$CONFIRMED_HASH" || true
    redcap_runtime_write_text "layerB/control-plane/last-reread-at" "$TIMESTAMP" || true
    redcap_runtime_write_text "layerB/control-plane/last-reread-mode" "$MODE" || true
fi

printf '%s\n' "$CONFIRMED_HASH"
exit 0

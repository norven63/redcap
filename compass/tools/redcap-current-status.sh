#!/usr/bin/env bash
# Print a compact RedCap Layer B status overview for handoff, Feishu, and user-facing updates.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$SCRIPT_DIR/redcap-dev-task.sh"
source "$SCRIPT_DIR/redcap-interop-governance.sh"

TASK_FILE=$(redcap_dev_task_resolve_file "${1:-}")
TASK_DIR="$(cd "$(dirname "$TASK_FILE")" 2>/dev/null && pwd || dirname "$TASK_FILE")"
PENDING_STATE=$(redcap_interop_pending_closure_existing_file "$REDCAP_ROOT" "$TASK_FILE" 2>/dev/null || true)
CURRENT_CONFIRMED_HASH=$(redcap_dev_task_confirmed_hash "$TASK_FILE" 2>/dev/null || true)
AGENT_REGISTRY_REFRESH_STATUS="cached"
DETECT_AGENTS_SCRIPT="$SCRIPT_DIR/redcap-detect-agents.sh"
AGENT_REGISTRY_FILE="$REDCAP_ROOT/compass/.workflow/agent-registry.yaml"

if [[ "${REDCAP_CURRENT_STATUS_REFRESH_AGENT_REGISTRY:-1}" == "1" && -x "$DETECT_AGENTS_SCRIPT" ]]; then
    if bash "$DETECT_AGENTS_SCRIPT" "$AGENT_REGISTRY_FILE" >/dev/null 2>&1; then
        AGENT_REGISTRY_REFRESH_STATUS="light-refreshed"
    else
        AGENT_REGISTRY_REFRESH_STATUS="refresh-failed"
    fi
fi

export REDCAP_RUNTIME_ROOT="${REDCAP_RUNTIME_ROOT:-$REDCAP_ROOT}"
export REDCAP_WORKSPACE_ROOT="${REDCAP_WORKSPACE_ROOT:-$TASK_DIR}"
export REDCAP_TASK_FILE="${REDCAP_TASK_FILE:-$TASK_FILE}"
export REDCAP_CURRENT_STATUS_AGENT_REGISTRY_REFRESH_STATUS="$AGENT_REGISTRY_REFRESH_STATUS"
python3 "$SCRIPT_DIR/redcap-current-status.py" "$REDCAP_ROOT" "$TASK_FILE" "$PENDING_STATE" "$CURRENT_CONFIRMED_HASH"

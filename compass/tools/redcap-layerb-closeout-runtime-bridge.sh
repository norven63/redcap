#!/usr/bin/env bash
# shellcheck shell=bash
# Thin bridge so the Python closeout runtime can reuse existing interop governance helpers.

set -euo pipefail

SUBCOMMAND="${1:-}"
if [[ -z "$SUBCOMMAND" ]]; then
    echo "usage: $0 <write-pending|append-ledger|ensure-runtime-binding>" >&2
    exit 2
fi
shift || true

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/redcap-runtime-state.sh"
source "$SCRIPT_DIR/redcap-dev-task.sh"
source "$SCRIPT_DIR/redcap-interop-governance.sh"

case "$SUBCOMMAND" in
    write-pending)
        if [[ $# -lt 6 || $# -gt 10 ]]; then
            echo "usage: $0 write-pending <project_root> <task_file> <host> <trigger> <required_redlines> <detail> [artifact_path] [baseline_head] [audited_head] [redline_mode]" >&2
            exit 2
        fi
        PROJECT_ROOT="$1"
        TASK_FILE="$2"
        HOST="$3"
        TRIGGER="$4"
        REQUIRED_REDLINES="$5"
        DETAIL="$6"
        ARTIFACT_PATH="${7:-}"
        BASELINE_HEAD="${8:-}"
        AUDITED_HEAD="${9:-}"
        REDLINE_MODE="${10:-replace}"
        redcap_interop_write_pending_closure \
            "$PROJECT_ROOT" \
            "$TASK_FILE" \
            "$HOST" \
            "$TRIGGER" \
            "$REQUIRED_REDLINES" \
            "$DETAIL" \
            "$ARTIFACT_PATH" \
            "$BASELINE_HEAD" \
            "$AUDITED_HEAD" \
            "$REDLINE_MODE"
        ;;
    append-ledger)
        if [[ $# -lt 5 || $# -gt 10 ]]; then
            echo "usage: $0 append-ledger <project_root> <task_file> <phase> <status> <detail> [host] [trigger] [baseline_head] [current_head] [artifact_path]" >&2
            exit 2
        fi
        PROJECT_ROOT="$1"
        TASK_FILE="$2"
        PHASE="$3"
        STATUS="$4"
        DETAIL="$5"
        HOST="${6:-}"
        TRIGGER="${7:-}"
        BASELINE_HEAD="${8:-}"
        CURRENT_HEAD="${9:-}"
        ARTIFACT_PATH="${10:-}"
        redcap_interop_append_closure_ledger \
            "$PROJECT_ROOT" \
            "$TASK_FILE" \
            "$PHASE" \
            "$STATUS" \
            "$DETAIL" \
            "$HOST" \
            "$TRIGGER" \
            "$BASELINE_HEAD" \
            "$CURRENT_HEAD" \
            "$ARTIFACT_PATH"
        ;;
    ensure-runtime-binding)
        if [[ $# -lt 3 || $# -gt 4 ]]; then
            echo "usage: $0 ensure-runtime-binding <project_root> <host> <binding_key> [initial_head]" >&2
            exit 2
        fi
        PROJECT_ROOT="$1"
        HOST="$2"
        BINDING_KEY="$3"
        INITIAL_HEAD="${4:-}"
        REDCAP_RUNTIME_ALLOW_DISK_RECOVERY=1 \
        REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY=1 \
            redcap_runtime_init_from_binding "$HOST" "$PROJECT_ROOT" "$BINDING_KEY"
        if [[ -n "$INITIAL_HEAD" ]]; then
            redcap_runtime_write_text "layerB/initial-head" "$INITIAL_HEAD"
        fi
        ;;
    *)
        echo "unsupported subcommand: $SUBCOMMAND" >&2
        exit 2
        ;;
esac

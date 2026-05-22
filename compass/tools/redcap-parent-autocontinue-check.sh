#!/usr/bin/env bash
# 用途：检查父任务线在子任务收口后是否应自动续跑，避免把机械“继续”上抛给用户。
# Dictionary: references/file-lookup-dictionary.md#runtime-and-closeout

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TASK_FILE="${1:-${REDCAP_TASK_FILE:-$REDCAP_ROOT/.dev-task.md}}"

python3 "$SCRIPT_DIR/redcap-parent-autocontinue-check.py" "$REDCAP_ROOT" "$TASK_FILE"

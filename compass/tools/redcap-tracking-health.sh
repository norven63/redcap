#!/usr/bin/env bash
# 用途：运行时与收尾脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#runtime-and-closeout

# Surface the health of RedCap tracking assets: .dev-task, task report, and explore-notes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$SCRIPT_DIR/redcap-dev-task.sh"

TASK_FILE=$(redcap_dev_task_resolve_file "${1:-}")
python3 "$SCRIPT_DIR/redcap-tracking-health.py" "$REDCAP_ROOT" "$TASK_FILE"

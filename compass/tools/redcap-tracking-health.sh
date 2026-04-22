#!/usr/bin/env bash
# Surface the health of RedCap tracking assets: .dev-task, task report, and explore-notes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$SCRIPT_DIR/redcap-dev-task.sh"

TASK_FILE=$(redcap_dev_task_resolve_file "${1:-}")
python3 "$SCRIPT_DIR/redcap-tracking-health.py" "$REDCAP_ROOT" "$TASK_FILE"

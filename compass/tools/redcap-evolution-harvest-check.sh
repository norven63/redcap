#!/usr/bin/env bash
# Validate that governance tasks explicitly handle Evolution Factory candidates.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TASK_FILE="${1:-$REDCAP_ROOT/.dev-task.md}"

python3 "$SCRIPT_DIR/redcap-evolution-harvest-check.py" "$REDCAP_ROOT" "$TASK_FILE"

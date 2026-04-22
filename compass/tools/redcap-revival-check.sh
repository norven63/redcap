#!/usr/bin/env bash
# Validate that revival/re-anchor rules have not drifted out of host entry files,
# reload rules, and the execution-guarantee registry.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="${1:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

python3 "$SCRIPT_DIR/redcap-revival-check.py" "$REDCAP_ROOT"

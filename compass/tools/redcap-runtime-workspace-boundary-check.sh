#!/usr/bin/env bash
# Validate RedCap runtime/project/user boundary and CLI workspace task resolution.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/redcap-runtime-workspace-boundary-check.py" "$@"

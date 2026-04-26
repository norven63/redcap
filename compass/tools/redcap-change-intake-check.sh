#!/usr/bin/env bash
# shellcheck shell=bash
# Validate Layer B mid-task change intake ledger and replan gate.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 "$SCRIPT_DIR/redcap-change-intake-check.py" "$@"

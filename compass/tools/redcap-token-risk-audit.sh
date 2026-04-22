#!/usr/bin/env bash
# Audit for repository areas that can accidentally flood agent context.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
python3 "$SCRIPT_DIR/redcap-token-risk-audit.py" "$REDCAP_ROOT"

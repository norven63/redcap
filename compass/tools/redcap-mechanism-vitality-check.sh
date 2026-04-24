#!/usr/bin/env bash
# shellcheck shell=bash
# Check whether RedCap's non-code governance mechanisms still have visible runtime surfaces.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 "$SCRIPT_DIR/redcap-mechanism-vitality-check.py" "$REDCAP_ROOT"

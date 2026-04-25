#!/usr/bin/env bash
# Validate the human-facing quality shape of RedCap task reports.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/redcap-human-output-quality-check.py" "$@"

#!/usr/bin/env bash
# shellcheck shell=bash
# Thin shell entry for the Layer B closeout runtime.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-layerb-closeout-runtime.py" "$@"

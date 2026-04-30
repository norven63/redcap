#!/usr/bin/env bash
# shellcheck shell=bash
# Apply RedCap legacy asset copy-first targets in the main tree.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 "$SCRIPT_DIR/redcap-legacy-asset-main-tree-apply.py" --root "$REDCAP_ROOT" "$@"

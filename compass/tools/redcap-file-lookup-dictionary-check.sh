#!/usr/bin/env bash
# Dictionary: references/file-lookup-dictionary.md#product-shape-and-retrieval
# Validate that the human file lookup dictionary covers critical RedCap files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 "$SCRIPT_DIR/redcap-file-lookup-dictionary-check.py" "$REDCAP_ROOT" "$@"

#!/usr/bin/env bash
# Dictionary: references/file-lookup-dictionary.md#shared-knowledge-layer
# Manage the local template for the future append-only shared knowledge repo.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 "$SCRIPT_DIR/redcap-shared-knowledge.py" "$REDCAP_ROOT" "$@"

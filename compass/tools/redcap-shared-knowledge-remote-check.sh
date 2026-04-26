#!/usr/bin/env bash
# Dictionary: references/file-lookup-dictionary.md#shared-knowledge-layer
# Validate the shared-knowledge public remote binding without loading historical docs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

exec python3 "$SCRIPT_DIR/redcap-shared-knowledge-remote-check.py" --root "$REDCAP_ROOT" "$@"

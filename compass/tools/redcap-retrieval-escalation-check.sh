#!/usr/bin/env bash
# Dictionary: references/file-lookup-dictionary.md#product-shape-and-retrieval
# Validate retrieval escalation policy without loading corpus bodies.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

exec python3 "$SCRIPT_DIR/redcap-retrieval-escalation-check.py" --root "$REDCAP_ROOT" "$@"

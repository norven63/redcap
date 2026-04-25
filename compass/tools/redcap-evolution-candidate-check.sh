#!/usr/bin/env bash
# Validate RedCap Evolution Factory candidates.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

STRICT=false
POOL_PATH="compass/evolution/candidates.json"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --strict) STRICT=true; shift ;;
        --pool) POOL_PATH="$2"; shift 2 ;;
        *)
            POOL_PATH="$1"; shift
            ;;
    esac
done

python3 "$SCRIPT_DIR/redcap-evolution-candidate-check.py" "$REDCAP_ROOT" "$POOL_PATH" "$STRICT"

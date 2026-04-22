#!/usr/bin/env bash
# Validate the registry of rules that must be backed by revival, hook, validator,
# or explicit manual-review safeguards.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REGISTRY_PATH="${1:-$REDCAP_ROOT/references/execution-guarantees.json}"

python3 "$SCRIPT_DIR/redcap-execution-guarantee-check.py" "$REDCAP_ROOT" "$REGISTRY_PATH"

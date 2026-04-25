#!/usr/bin/env bash
# Validate the R0 Evolution-grade baseline registry.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REGISTRY_PATH="${1:-references/evolution-grade-baseline.json}"

python3 "$SCRIPT_DIR/redcap-evolution-grade-check.py" "$REDCAP_ROOT" "$REGISTRY_PATH"

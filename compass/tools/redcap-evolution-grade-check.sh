#!/usr/bin/env bash
# Dictionary: references/file-lookup-dictionary.md#control-plane-assurance
# Validate the control-plane assurance registry.
# Compatibility: the default file is still references/evolution-grade-baseline.json,
# but the registry now covers all RedCap guarantee surfaces, not only self-evolution.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REGISTRY_PATH="${1:-references/evolution-grade-baseline.json}"

python3 "$SCRIPT_DIR/redcap-evolution-grade-check.py" "$REDCAP_ROOT" "$REGISTRY_PATH"

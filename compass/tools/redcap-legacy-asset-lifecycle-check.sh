#!/usr/bin/env bash
# Validate RedCap legacy asset lifecycle policy and runtime residue guardrails.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
POLICY_PATH="${1:-references/legacy-asset-lifecycle.json}"

python3 "$SCRIPT_DIR/redcap-legacy-asset-lifecycle-check.py" "$REDCAP_ROOT" "$POLICY_PATH"

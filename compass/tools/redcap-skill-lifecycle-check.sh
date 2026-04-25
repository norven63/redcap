#!/usr/bin/env bash
# Validate RedCap skill lifecycle and host-export single-source policy.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
POLICY_PATH="${1:-references/skill-lifecycle-policy.json}"

python3 "$SCRIPT_DIR/redcap-skill-lifecycle-check.py" "$REDCAP_ROOT" "$POLICY_PATH"

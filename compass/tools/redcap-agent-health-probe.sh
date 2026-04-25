#!/usr/bin/env bash
# Probe local Agent CLI health. Default mode is installation/config only; --live runs bounded real calls.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 "$SCRIPT_DIR/redcap-agent-health-probe.py" "$REDCAP_ROOT" "$@"

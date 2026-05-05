#!/usr/bin/env bash
# Validate public redcap-arsenal content-state and claim boundaries.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-public-arsenal-claim-boundary.py" "$@"

#!/usr/bin/env bash

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

exec bash "$REDCAP_ROOT/compass/tools/redcap-layerB-session-start.sh" copilot

#!/usr/bin/env bash

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

source "$SCRIPT_DIR/redcap-copilot-session-context.sh"
redcap_copilot_apply_session_context >/dev/null 2>&1 || true

exec bash "$REDCAP_ROOT/compass/tools/redcap-layerB-session-start.sh" copilot

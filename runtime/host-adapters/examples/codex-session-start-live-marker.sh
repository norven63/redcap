#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--probe" && "${2:-}" == "codex" && "${3:-}" == "SessionStart" ]]; then
  echo "REDCAP_HOOK_LIVE_MARKER_OK codex SessionStart"
  exit 0
fi

echo "usage: codex-session-start-live-marker.sh --probe codex SessionStart" >&2
exit 2

#!/usr/bin/env bash
# prism-runs-lifecycle.sh — classify prism/runs evidence and prune only the safe acceptance set.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

COMMAND="${1:-summary}"
shift || true

APPLY=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=true; shift ;;
    *)
      echo "[prism-runs-lifecycle] unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

python3 "$SCRIPT_DIR/prism-runs-lifecycle.py" "$REDCAP_ROOT" "$COMMAND" "$APPLY"

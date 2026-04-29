#!/usr/bin/env bash
# shellcheck shell=bash
# Run the true git-worktree rehearsal for RedCap historical asset copy-first migration.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 "$SCRIPT_DIR/redcap-legacy-asset-migration-worktree-rehearsal.py" --root "$REDCAP_ROOT" "$@"

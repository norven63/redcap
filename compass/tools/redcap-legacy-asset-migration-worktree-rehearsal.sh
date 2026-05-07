#!/usr/bin/env bash
# shellcheck shell=bash
# 用途：控制面保障脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#control-plane-assurance

# Run the true git-worktree rehearsal for RedCap historical asset copy-first migration.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 "$SCRIPT_DIR/redcap-legacy-asset-migration-worktree-rehearsal.py" --root "$REDCAP_ROOT" "$@"

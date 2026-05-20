#!/usr/bin/env bash
# 用途：runtime Prism 兼容外壳；实际实现仍委托 prism/tools 权威脚本。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TARGET="$REDCAP_ROOT/prism/tools/prism-coordinator.sh"

if [[ ! -f "$TARGET" ]]; then
    echo "[redcap-runtime-prism-facade] missing delegated Prism tool: $TARGET" >&2
    exit 1
fi

exec bash "$TARGET" "$@"


#!/usr/bin/env bash
# 用途：internal-control-plane copy-first 兼容外壳；真实实现仍委托 compass/tools 权威脚本。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TARGET="$REDCAP_ROOT/compass/tools/redcap-drift-check.sh"

if [[ ! -f "$TARGET" ]]; then
    echo "[redcap-internal-control-plane-facade] missing delegated tool: $TARGET" >&2
    exit 1
fi

exec bash "$TARGET" "$@"

#!/usr/bin/env bash
# 用途：runtime 公开入口兼容外壳；实际实现仍委托 compass/tools 权威脚本。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TARGET="$REDCAP_ROOT/compass/tools/redcap-docs-catalog.sh"

if [[ ! -f "$TARGET" ]]; then
    echo "[redcap-runtime-facade] missing delegated RedCap tool: $TARGET" >&2
    exit 1
fi

exec bash "$TARGET" "$@"

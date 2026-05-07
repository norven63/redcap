#!/usr/bin/env bash
# shellcheck shell=bash
# 用途：控制面保障脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#control-plane-assurance

# Preflight RedCap legacy asset delete-last / canonical-switch safety.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 "$SCRIPT_DIR/redcap-legacy-asset-delete-last-preflight.py" --root "$REDCAP_ROOT" "$@"

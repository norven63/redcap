#!/usr/bin/env bash
# shellcheck shell=bash
# 用途：控制面保障脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#control-plane-assurance

# Check whether RedCap's non-code governance mechanisms still have visible runtime surfaces.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 "$SCRIPT_DIR/redcap-mechanism-vitality-check.py" "$REDCAP_ROOT"

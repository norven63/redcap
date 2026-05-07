#!/usr/bin/env bash
# 用途：棱镜与 Agent 路由脚本；详细职责见文件查阅字典。

# Dictionary: references/file-lookup-dictionary.md#prism-and-providers
# Keep a 1-hour Prism agent availability cache and validate rosters before launch.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 "$SCRIPT_DIR/prism-availability.py" "$REDCAP_ROOT" "$@"

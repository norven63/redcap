#!/usr/bin/env bash
# 用途：运行时与收尾脚本；检查飞书回复收件箱，确保回复只进入安全待处理入口，不直接执行。
# Dictionary: references/file-lookup-dictionary.md#runtime-and-closeout

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-feishu-inbox.py" "$@"

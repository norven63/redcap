#!/usr/bin/env bash
# 用途：正式发布 R1 延期根目录处置预检脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-formal-release-r1-root-group-disposition-check.py" "$@"

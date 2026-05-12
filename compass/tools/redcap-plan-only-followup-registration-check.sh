#!/usr/bin/env bash
# 用途：棱镜与结论保障脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#prism-and-providers

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-plan-only-followup-registration-check.py" "$@"

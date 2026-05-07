#!/usr/bin/env bash
# shellcheck shell=bash
# 用途：运行时与收尾脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#runtime-and-closeout

# Thin shell entry for the Layer B closeout runtime.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-layerb-closeout-runtime.py" "$@"

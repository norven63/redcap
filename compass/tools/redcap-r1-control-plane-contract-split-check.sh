#!/usr/bin/env bash
# 用途：运行 R1 控制面契约拆分预检；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/redcap-r1-control-plane-contract-split-check.py" "$@"

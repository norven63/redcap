#!/usr/bin/env bash
# 用途：校验 P4-20 发布准备下一安全切片选择；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-r1-next-safe-slice-after-old-anchor-preflight-check.py" "$@"

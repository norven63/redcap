#!/usr/bin/env bash
# 用途：校验 P4-26 只做 P4-25 后下一安全切片路线选择；详细职责见文件查阅字典。

# Dictionary: references/file-lookup-dictionary.md#package-publish-safety
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/redcap-r1-next-safe-slice-after-control-plane-contract-mirror-preflight-check.py" "$@"

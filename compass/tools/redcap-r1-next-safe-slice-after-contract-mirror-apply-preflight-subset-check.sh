#!/usr/bin/env bash
# 用途：运行 P4-28 下一安全切片路线选择校验；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-r1-next-safe-slice-after-contract-mirror-apply-preflight-subset-check.py" "$@"

#!/usr/bin/env bash
# 用途：R1 合同镜像小范围 apply 预检校验入口；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/redcap-r1-contract-mirror-apply-preflight-subset-check.py" "$@"

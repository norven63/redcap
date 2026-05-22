#!/usr/bin/env bash
# 用途：正式发布 R1 控制面 public/internal contract mirror 预检验收入口。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/redcap-r1-control-plane-public-internal-contract-mirror-preflight-check.py" "$@"

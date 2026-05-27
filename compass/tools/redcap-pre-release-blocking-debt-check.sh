#!/usr/bin/env bash
# 用途：发布前阻塞债务脚本；校验资产历史债务与 full LLM-wiki 补全已形成可验收状态。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-pre-release-blocking-debt-check.py" "$@"

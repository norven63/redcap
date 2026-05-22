#!/usr/bin/env bash
# 用途：校验 P4-19 旧 Prism 报告锚点退休预检，确保它没有越界成真实删除或发布动作。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-r1-prism-report-archive-old-anchor-delete-last-preflight-check.py" "$@"

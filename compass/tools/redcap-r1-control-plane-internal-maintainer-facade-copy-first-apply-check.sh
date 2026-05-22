#!/usr/bin/env bash
# 用途：正式发布 R1 内部控制面维护工具 facade 小批次验收入口；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-r1-control-plane-internal-maintainer-facade-copy-first-apply-check.py" "$@"

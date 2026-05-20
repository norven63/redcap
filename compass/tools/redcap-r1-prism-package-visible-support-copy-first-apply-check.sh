#!/usr/bin/env bash
# 用途：正式发布 R1 Prism package-visible support copy-first 验收；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

exec python3 "$SCRIPT_DIR/redcap-r1-prism-package-visible-support-copy-first-apply-check.py" "$@"


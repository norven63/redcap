#!/usr/bin/env bash
# shellcheck shell=bash
# 用途：正式发布 R1 Prism 证据保留拆分预检；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-r1-prism-evidence-retention-split-check.py" "$@"

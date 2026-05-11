#!/usr/bin/env bash
# 用途：检查 RedCap 面向人类的 CLI、状态和通知输出是否先讲人话；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#product-shape-and-retrieval

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-human-product-surface-check.py" "$@"

#!/usr/bin/env bash
# 用途：产品形态与检索治理脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#product-shape-and-retrieval

# Audit for repository areas that can accidentally flood agent context.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
python3 "$SCRIPT_DIR/redcap-token-risk-audit.py" "$REDCAP_ROOT"

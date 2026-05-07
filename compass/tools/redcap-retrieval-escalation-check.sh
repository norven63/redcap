#!/usr/bin/env bash
# 用途：产品形态与检索治理脚本；详细职责见文件查阅字典。

# Dictionary: references/file-lookup-dictionary.md#product-shape-and-retrieval
# Validate retrieval escalation policy without loading corpus bodies.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

exec python3 "$SCRIPT_DIR/redcap-retrieval-escalation-check.py" --root "$REDCAP_ROOT" "$@"

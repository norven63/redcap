#!/usr/bin/env bash
# 用途：知识沉淀与自进化脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

# Validate the active Evolution Factory harvest ledger.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LEDGER_PATH="${1:-compass/evolution/harvest-ledger.json}"

python3 "$SCRIPT_DIR/redcap-evolution-harvest-ledger-check.py" "$REDCAP_ROOT" "$LEDGER_PATH"

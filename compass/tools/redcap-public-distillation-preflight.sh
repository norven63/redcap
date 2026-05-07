#!/usr/bin/env bash
# 用途：知识沉淀与自进化脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-public-distillation-preflight.py" "$@"

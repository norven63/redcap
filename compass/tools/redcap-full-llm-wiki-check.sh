#!/usr/bin/env bash
# 用途：长期记忆路线图脚本；校验 full LLM-wiki 产品骨架、队列、索引、receipt 与 source anchor。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-full-llm-wiki-check.py" "$@"

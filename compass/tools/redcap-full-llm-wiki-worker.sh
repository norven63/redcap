#!/usr/bin/env bash
# 用途：长期记忆路线图脚本；生成 full LLM-wiki 候选条目和候选 receipt，默认只提案不晋升。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-full-llm-wiki-worker.py" "$@"

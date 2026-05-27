#!/usr/bin/env bash
# 用途：长期记忆路线图脚本；校验 RAG/GraphRAG 受控适配层保持 disabled-by-default。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-rag-graphrag-boundary-check.py" "$@"

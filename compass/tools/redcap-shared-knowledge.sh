#!/usr/bin/env bash
# 用途：公共知识库治理脚本；详细职责见文件查阅字典。

# Dictionary: references/file-lookup-dictionary.md#shared-knowledge-layer
# Manage the local template for the future append-only shared knowledge repo.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 "$SCRIPT_DIR/redcap-shared-knowledge.py" "$REDCAP_ROOT" "$@"

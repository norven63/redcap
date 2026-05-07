#!/usr/bin/env bash
# 用途：公共知识库治理脚本；详细职责见文件查阅字典。

# Dictionary: references/file-lookup-dictionary.md#shared-knowledge-layer
# Validate the shared-knowledge public remote binding without loading historical docs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

exec python3 "$SCRIPT_DIR/redcap-shared-knowledge-remote-check.py" --root "$REDCAP_ROOT" "$@"

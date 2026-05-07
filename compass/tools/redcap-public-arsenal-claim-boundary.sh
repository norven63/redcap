#!/usr/bin/env bash
# 用途：公共知识库治理脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#shared-knowledge-layer

# Validate public redcap-arsenal content-state and claim boundaries.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-public-arsenal-claim-boundary.py" "$@"

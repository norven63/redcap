#!/usr/bin/env bash
# 用途：中途架构与任务树一致性审计入口；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#product-shape-and-retrieval

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

exec python3 "$SCRIPT_DIR/redcap-midcourse-architecture-check.py" "$REDCAP_ROOT" "$@"

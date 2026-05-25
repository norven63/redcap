#!/usr/bin/env bash
# 用途：棱镜与 Agent 路由策略检查；确保 provider 调度约束不是口头约定。
# Dictionary: references/file-lookup-dictionary.md#prism-and-providers

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-prism-provider-policy-check.py" "$@"

#!/usr/bin/env bash
# 用途：控制面保障脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#control-plane-assurance

# Validate the registry of rules that must be backed by revival, hook, validator,
# or explicit manual-review safeguards.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REGISTRY_PATH="${1:-$REDCAP_ROOT/references/execution-guarantees.json}"

python3 "$SCRIPT_DIR/redcap-execution-guarantee-check.py" "$REDCAP_ROOT" "$REGISTRY_PATH"

#!/usr/bin/env bash
# 用途：产品形态与检索治理脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#product-shape-and-retrieval

# Validate RedCap legacy asset lifecycle policy and runtime residue guardrails.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
POLICY_PATH="${1:-references/legacy-asset-lifecycle.json}"

python3 "$SCRIPT_DIR/redcap-legacy-asset-lifecycle-check.py" "$REDCAP_ROOT" "$POLICY_PATH"

#!/usr/bin/env bash
# 用途：棱镜与 Agent 路由脚本；详细职责见文件查阅字典。

# Dictionary: references/file-lookup-dictionary.md#prism-and-providers
# Probe local Agent CLI health. Default mode is installation/config only; --live runs bounded real calls.
# Provider freezes/protected fallbacks from references/prism-provider-policy.json are reported without executing protected CLIs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 "$SCRIPT_DIR/redcap-agent-health-probe.py" "$REDCAP_ROOT" "$@"

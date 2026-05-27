#!/usr/bin/env bash
# 用途：校验 RedCap 完成语义，防止把证明、保留、延期或人工决策边界冒充为完成。
# Dictionary: references/file-lookup-dictionary.md#control-plane-assurance

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-completion-semantics-check.py" "$@"

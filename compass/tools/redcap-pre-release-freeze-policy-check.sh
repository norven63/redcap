#!/usr/bin/env bash
# 用途：校验首次发布收敛期的冻结边界，防止治理任务因为正常证据产出而自我增殖。
# Dictionary: references/file-lookup-dictionary.md
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-pre-release-freeze-policy-check.py" "$@"

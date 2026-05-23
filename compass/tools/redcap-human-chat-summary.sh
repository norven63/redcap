#!/usr/bin/env bash
# 用途：生成聊天汇报用的人类可读任务摘要；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#runtime-and-closeout

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/redcap-human-chat-summary.py" "$@"

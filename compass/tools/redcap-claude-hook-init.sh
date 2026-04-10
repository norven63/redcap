#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap 框架 — Claude Code InstructionsLoaded Hook
#
# 在 CLAUDE.md 加载时触发（等价于 session start）。
# 捕获当前 HEAD 作为基准，供 Stop hook 比较。
# ─────────────────────────────────────────────────────────

cat > /dev/null  # 消费 stdin

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HEAD_FILE="/tmp/redcap-claude-initial-head"

git -C "$REDCAP_ROOT" rev-parse HEAD 2>/dev/null > "$HEAD_FILE" || true
exit 0

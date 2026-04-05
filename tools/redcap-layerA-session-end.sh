#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap Layer A — SessionEnd Hook（用户级）
#
# 部署位置：~/.claude/settings.json（用户级，所有项目生效）
# 触发时机：Claude Code 会话结束
#
# 职责：
#   清理本 session 的临时标记文件
#
# 通信协议（Claude Code Hooks Reference）：
#   stdin — JSON（含 session_id, reason 等）
#   exit 0 — 成功（SessionEnd 不支持阻止）
#   默认超时 1.5s（可通过 CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS 调大）
# ─────────────────────────────────────────────────────────

set -u

INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

if [[ -z "$SESSION_ID" ]]; then
    echo "[redcap-layerA-session-end] WARN: failed to parse session_id from stdin" >&2
    exit 0
fi

# 清理本 session 的标记文件
rm -f "/tmp/redcap-layerA-head-${SESSION_ID}" 2>/dev/null || true
rm -f "/tmp/redcap-layerA-notified-${SESSION_ID}" 2>/dev/null || true

exit 0

#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap Layer A — Stop Hook（用户级）
#
# 部署位置：~/.claude/settings.json（用户级，所有项目生效）
# 触发时机：每次 Claude Code Agent turn 结束
#
# 职责：
#   检测 RedCap 工作流是否到达 ALL_DONE → 执行 on_ALL_DONE 收尾
#
# 检测逻辑（三重过滤，避免误触发）：
#   1. 开发手册/.workflow/state.yaml 存在（RedCap 项目标识）
#   2. current_state == ALL_DONE（流程完毕）
#   3. 本 session 未通知过（session_id 去重）
#
# 通信协议（Claude Code Hooks Reference）：
#   stdin — JSON（含 session_id, cwd, stop_hook_active 等）
#   exit 0 — 允许停止（本脚本只做旁路通知，不阻塞）
# ─────────────────────────────────────────────────────────

set -u

INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
CWD=$(echo "$INPUT" | grep -o '"cwd"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

if [[ -z "$SESSION_ID" || -z "$CWD" ]]; then
    exit 0
fi

# ── 过滤 1: RedCap 工作流存在性 ──────────────────────────

STATE_FILE="$CWD/开发手册/.workflow/state.yaml"
if [[ ! -f "$STATE_FILE" ]]; then
    exit 0
fi

# ── 过滤 2: 状态检查 ─────────────────────────────────────

CURRENT_STATE=$(grep -E '^current_state:' "$STATE_FILE" 2>/dev/null | head -1 | sed 's/^current_state:[[:space:]]*//' | tr -d '"' | tr -d "'")
if [[ "$CURRENT_STATE" != "ALL_DONE" ]]; then
    exit 0
fi

# ── 过滤 3: Session 去重 ─────────────────────────────────

NOTIFIED_FILE="/tmp/redcap-layerA-notified-${SESSION_ID}"
if [[ -f "$NOTIFIED_FILE" ]]; then
    exit 0
fi

# ── 执行 on_ALL_DONE 收尾 ────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 读取初始 HEAD（SessionStart 捕获）
INITIAL_HEAD=""
HEAD_FILE="/tmp/redcap-layerA-head-${SESSION_ID}"
if [[ -f "$HEAD_FILE" ]]; then
    INITIAL_HEAD=$(cat "$HEAD_FILE")
fi

PROJECT_NAME=$(basename "$CWD")

# 调用 on-complete 收尾脚本
ON_COMPLETE="$REDCAP_DIR/tools/redcap-on-complete.sh"
if [[ -f "$ON_COMPLETE" ]]; then
    bash "$ON_COMPLETE" "$CWD" "$INITIAL_HEAD" "$PROJECT_NAME" 2>/dev/null || true
fi

# 标记已通知
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$NOTIFIED_FILE"

exit 0

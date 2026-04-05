#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap Layer A — SessionStart Hook（用户级）
#
# 部署位置：~/.claude/settings.json（用户级，所有项目生效）
# 触发时机：每次 Claude Code 会话启动或恢复
#
# 职责：
#   1. 清理超过 24h 的僵尸标记文件（Lazy 清理）
#   2. 捕获当前 HEAD 供 Stop hook 比较
#
# Layer A 上下文：RedCap 作为 Skill 开发用户项目时，
#   cwd 在目标项目中，但 RedCap 脚本在 RedCap 自身 repo。
#   此脚本通过 state.yaml 存在性判断是否为 RedCap 工作流。
#
# 通信协议（Claude Code Hooks Reference）：
#   stdin — JSON（含 session_id, cwd 等 common fields）
#   exit 0 — 成功
# ─────────────────────────────────────────────────────────

set -u

# 读取 stdin JSON
INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
CWD=$(echo "$INPUT" | grep -o '"cwd"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

if [[ -z "$SESSION_ID" || -z "$CWD" ]]; then
    exit 0
fi

# ── 1. 僵尸标记清理（Lazy，24h 过期） ────────────────────

find /tmp -maxdepth 1 -name "redcap-layerA-*" -mtime +1 -delete 2>/dev/null || true

# ── 2. 捕获初始 HEAD ─────────────────────────────────────

# 无论是否 RedCap 项目都捕获（SessionEnd 会清理）
HEAD=$(git -C "$CWD" rev-parse HEAD 2>/dev/null) || exit 0
echo "$HEAD" > "/tmp/redcap-layerA-head-${SESSION_ID}"

exit 0

#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap 框架 — Claude Code InstructionsLoaded Hook
#
# 在 CLAUDE.md 加载时触发（等价于 session start）。
# 委托到统一的 Layer B SessionStart 入口，保证 Claude/Gemini/Copilot
# 使用同一套初始 HEAD 捕获协议。
# ─────────────────────────────────────────────────────────

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

exec bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" claude

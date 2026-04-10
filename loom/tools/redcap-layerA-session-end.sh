#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap 通用 Hook 分发代理 (SessionEnd / Stop Hook)
#
# 符合《references/hook-standards.md》契约。
#
# 职责：
#   1. 接收宿主 (Claude/Gemini/Kimi) 传入的 JSON 上下文。
#   2. 识别 Layer A (用户项目) 或 Layer B (RedCap 自身)。
#   3. 分发审计逻辑 (Audit)。
#   4. 执行原子清理 (Cleanup)。
#
# 部署：
#   - Claude Code: .claude/settings.json -> Stop hook
#   - Gemini CLI: .gemini/settings.json -> SessionEnd
#   - Kimi CLI: dispatcher -> Stop event
# ─────────────────────────────────────────────────────────

set -u

# ── 1. 接收并解析上下文 ──────────────────────────────────

INPUT=$(cat)
# 简单的正则解析（不依赖 jq 以保证环境兼容性）
SESSION_ID=$(echo "$INPUT" | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
CWD=$(echo "$INPUT" | grep -o '"cwd"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

if [[ -z "$SESSION_ID" || -z "$CWD" ]]; then
    # Gemini CLI 的 SessionEnd 协议可能在不同版本有差异，若解析失败记录警告并继续清理
    echo "[redcap-hook-proxy] WARN: failed to parse session_id or cwd from stdin" >&2
    # 尝试降级获取 CWD
    CWD=${CWD:-$(pwd)}
fi

# ── 2. 识别层级并执行审计逻辑 (Audit) ─────────────────────

# 使用 readlink 解析真实路径（兼容符号链接）
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")" )" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 路径归一化（移除末尾斜杠）
CWD_NORM=$(echo "$CWD" | sed 's:/*$::')
REDCAP_DIR_NORM=$(echo "$REDCAP_ROOT" | sed 's:/*$::')

# 检查是否为 RedCap 自身开发 (Layer B)
if [[ "$CWD_NORM" == "$REDCAP_DIR_NORM" ]]; then
    echo "[redcap-hook-proxy] 检测到 Layer B (RedCap 自身) 任务，启动框架审计..." >&2
    # 调用框架评审脚本
    B_REVIEW_SCRIPT="$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh"
    if [[ -x "$B_REVIEW_SCRIPT" ]]; then
        # 注意：Layer B 脚本内部也需要消费 stdin，我们已经消费过了，
        # 所以通过 echo 重新传进去（虽然目前的脚本只是 cat > /dev/null）
        echo "$INPUT" | bash "$B_REVIEW_SCRIPT" 2>&1 || true
    fi
else
    # 检查是否为 RedCap 开发的用户项目 (Layer A)
    # 依据：是否存在 开发手册/.workflow/state.yaml
    if [[ -f "$CWD/开发手册/.workflow/state.yaml" ]]; then
        echo "[redcap-hook-proxy] 检测到 Layer A (用户项目) 任务，启动项目审计..." >&2
        A_STOP_SCRIPT="$REDCAP_ROOT/loom/tools/redcap-layerA-stop.sh"
        if [[ -x "$A_STOP_SCRIPT" ]]; then
            echo "$INPUT" | bash "$A_STOP_SCRIPT" 2>&1 || true
        fi
    fi
fi

# ── 3. 执行原子清理 (Cleanup) ─────────────────────────────

echo "[redcap-hook-proxy] 执行原子清理 (Session: $SESSION_ID)..." >&2

# 清理本 session 的标记文件
rm -f "/tmp/redcap-layerA-head-${SESSION_ID}" 2>/dev/null || true
rm -f "/tmp/redcap-layerA-notified-${SESSION_ID}" 2>/dev/null || true
rm -f "/tmp/redcap-layerA-workflow-session-${SESSION_ID}" 2>/dev/null || true # 以前可能叫这名

# 清理历史过期的标记文件（24小时以上）
find /tmp -name "redcap-layerA-head-*" -mtime +1 -delete 2>/dev/null || true
find /tmp -name "redcap-layerA-notified-*" -mtime +1 -delete 2>/dev/null || true

# ── 4. 退出 ───────────────────────────────────────────────

# Gemini CLI Hook 必须返回合法 JSON
# 但 SessionEnd 是 "fire and forget"，输出主要用于调试，不影响决策
echo '{"decision": "allow"}'

exit 0

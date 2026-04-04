#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap 框架 — Kimi CLI Hook 处理器
#
# 由全局 dispatcher (~/.kimi/hooks/dispatcher.sh) 在 cwd 匹配
# */redcap 时路由到本脚本。
#
# 功能：
#   - SessionStart: 捕获当前 HEAD 到临时文件
#   - Stop/SessionEnd: 检测新 commit → 飞书通知（CONTRIBUTING.md §4）
#
# 通信协议：
#   $1    — 事件名（SessionStart / Stop / SessionEnd / ...）
#   stdin — Kimi CLI 传递的 JSON 上下文
#
# 退出码：0=允许继续, 2=阻止（本脚本始终返回 0）
# ─────────────────────────────────────────────────────────

set -u

EVENT="${1:-}"
JSON=$(cat)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HEAD_FILE="/tmp/redcap-kimi-initial-head"

# ── SessionStart: 捕获初始 HEAD ──────────────────────────

handle_session_start() {
    local head
    head=$(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null) || return 0
    echo "$head" > "$HEAD_FILE"
}

# ── Stop / SessionEnd: 检测新 commit → 飞书通知 ──────────

handle_session_end() {
    # 读取初始 HEAD
    if [[ ! -f "$HEAD_FILE" ]]; then
        return 0
    fi
    local initial_head
    initial_head=$(cat "$HEAD_FILE")

    # 检查是否有新 commit
    local current_head
    current_head=$(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null) || return 0

    if [[ "$initial_head" == "$current_head" ]]; then
        # 无变更，无需通知
        return 0
    fi

    # 有新 commit → 飞书通知
    local notifier="$SCRIPT_DIR/feishu-notifier.py"
    if [[ ! -f "$notifier" ]]; then
        return 0
    fi

    local commit_log
    commit_log=$(git -C "$PROJECT_DIR" --no-pager log --oneline "$initial_head..HEAD" 2>/dev/null || echo "(无法获取)")

    python3 "$notifier" notify \
        "RedCap 框架变更完成 (Kimi Hook 自动通知)\n\nCommits:\n$commit_log" \
        --project "redcap" 2>/dev/null || true

    # 清理临时文件（仅在 SessionEnd 时，Stop 不清理以便 SessionEnd 兜底）
    if [[ "$EVENT" == "SessionEnd" ]]; then
        rm -f "$HEAD_FILE" 2>/dev/null || true
    fi
}

# ── 路由 ─────────────────────────────────────────────────

case "$EVENT" in
    SessionStart)
        handle_session_start
        ;;
    Stop|SessionEnd)
        handle_session_end
        ;;
    *)
        # 其他事件不处理
        ;;
esac

exit 0

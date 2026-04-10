#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap 框架 — Claude Code Stop Hook
#
# 由 .claude/settings.json 的 Stop hook 触发（每次 Agent turn 结束）。
# 检测自上次通知/会话开始以来是否有新 commit → 有则发飞书通知。
#
# 配合 redcap-claude-hook-init.sh（InstructionsLoaded）使用：
#   init 捕获初始 HEAD → Stop 比较并通知 → 更新已通知 HEAD
#
# Claude Code Stop hook 协议：
#   stdin — JSON
#   退出码 — 0=成功, 非0=失败（不阻塞 Agent）
# ─────────────────────────────────────────────────────────

set -u

cat > /dev/null  # 消费 stdin

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HEAD_FILE="/tmp/redcap-claude-initial-head"
NOTIFIED_FILE="/tmp/redcap-claude-last-notified-head"

# 确定比较基准：优先用"已通知 HEAD"，否则用"初始 HEAD"
BASELINE=""
if [[ -f "$NOTIFIED_FILE" ]]; then
    BASELINE=$(cat "$NOTIFIED_FILE")
elif [[ -f "$HEAD_FILE" ]]; then
    BASELINE=$(cat "$HEAD_FILE")
else
    # 无基准信息，跳过
    exit 0
fi

CURRENT_HEAD=$(git -C "$REDCAP_ROOT" rev-parse HEAD 2>/dev/null) || exit 0

if [[ "$BASELINE" == "$CURRENT_HEAD" ]]; then
    exit 0
fi

# 有新 commit → 飞书通知
NOTIFIER="$SCRIPT_DIR/feishu-notifier.py"
if [[ ! -f "$NOTIFIER" ]]; then
    exit 0
fi

COMMIT_LOG=$(git -C "$REDCAP_ROOT" --no-pager log --oneline "$BASELINE..HEAD" 2>/dev/null || echo "(无法获取)")

python3 "$NOTIFIER" notify \
    "RedCap 框架变更完成 (Claude Hook 自动通知)\n\nCommits:\n$COMMIT_LOG" \
    --project "redcap" 2>/dev/null || true

# 记录已通知的 HEAD，防止下次 Stop 重复通知
echo "$CURRENT_HEAD" > "$NOTIFIED_FILE"

exit 0

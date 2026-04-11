#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap 框架 — Layer B SessionEnd 统一收尾入口
#
# 负责：
#   1. 非 Claude 宿主补跑独立架构评审
#   2. 检查本次 commit 区间是否产出模板化任务报告
#   3. 发送 Layer B 飞书完成/告警通知
#   4. 维护去重标记，避免重复提醒
# ─────────────────────────────────────────────────────────

set -u

HOST="${1:-}"

if [[ -z "$HOST" ]]; then
    echo "[redcap-layerB-session-end] ERROR: host is required" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HEAD_FILE="/tmp/redcap-layerB-${HOST}-initial-head"
NOTIFIED_FILE="/tmp/redcap-layerB-${HOST}-last-notified-head"
ALERTED_FILE="/tmp/redcap-layerB-${HOST}-last-alerted-head"
LEGACY_CLAUDE_HEAD_FILE="/tmp/redcap-claude-initial-head"
REPORT_MARKER="/tmp/redcap-layerB-${HOST}-current-report-path"

CURRENT_HEAD=$(git -C "$REDCAP_ROOT" rev-parse HEAD 2>/dev/null) || exit 0

EXPLORE_NOTES_CHECK="$SCRIPT_DIR/redcap-explore-notes-check.sh"
if [[ -x "$EXPLORE_NOTES_CHECK" ]]; then
    REDCAP_SKIP_FEISHU="${REDCAP_SKIP_FEISHU:-0}" bash "$EXPLORE_NOTES_CHECK" 2>&1 || true
fi

BASELINE=""
if [[ -f "$NOTIFIED_FILE" ]]; then
    BASELINE=$(cat "$NOTIFIED_FILE")
elif [[ -f "$HEAD_FILE" ]]; then
    BASELINE=$(cat "$HEAD_FILE")
elif [[ "$HOST" == "claude" && -f "$LEGACY_CLAUDE_HEAD_FILE" ]]; then
    BASELINE=$(cat "$LEGACY_CLAUDE_HEAD_FILE")
fi

cleanup_session_files() {
    rm -f "$HEAD_FILE" 2>/dev/null || true
    rm -f "$REPORT_MARKER" 2>/dev/null || true
    if [[ "$HOST" == "claude" ]]; then
        rm -f "$LEGACY_CLAUDE_HEAD_FILE" 2>/dev/null || true
    fi
}

if [[ -z "$BASELINE" ]]; then
    echo "$CURRENT_HEAD" > "$NOTIFIED_FILE"
    cleanup_session_files
    exit 0
fi

if [[ "$BASELINE" == "$CURRENT_HEAD" ]]; then
    cleanup_session_files
    exit 0
fi

SKIP_REVIEW="${REDCAP_SKIP_INDEPENDENT_REVIEW:-0}"

if [[ "$HOST" != "claude" && "$SKIP_REVIEW" != "1" ]]; then
    echo "$BASELINE" > "$HEAD_FILE"
    REDCAP_BASELINE_HEAD_FILE="$HEAD_FILE" bash "$SCRIPT_DIR/redcap-on-stop-review.sh" <<'EOF' 2>&1 || true
{}
EOF
fi

REPORT_CHECK_SCRIPT="$SCRIPT_DIR/redcap-task-report-check.sh"
REPORT_OUTPUT=""
REPORT_STATUS=0

if REPORT_OUTPUT=$("$REPORT_CHECK_SCRIPT" "$REDCAP_ROOT" "$BASELINE" "$CURRENT_HEAD" "$HOST" 2>&1); then
    REPORT_STATUS=1
fi

COMMIT_LOG=$(git -C "$REDCAP_ROOT" --no-pager log --oneline "$BASELINE..$CURRENT_HEAD" 2>/dev/null || echo "(无法获取)")
NOTIFIER="$SCRIPT_DIR/feishu-notifier.py"
SKIP_FEISHU="${REDCAP_SKIP_FEISHU:-0}"

send_notification() {
    local message="$1"

    if [[ "$SKIP_FEISHU" == "1" || ! -f "$NOTIFIER" ]]; then
        return 0
    fi

    python3 "$NOTIFIER" notify "$message" --project "redcap" 2>/dev/null || true
}

if [[ "$REPORT_STATUS" -eq 1 ]]; then
    send_notification "RedCap 任务完成（${HOST} SessionEnd 收尾）\n\n任务报告:\n$REPORT_OUTPUT\n\nCommits:\n$COMMIT_LOG"
    echo "$CURRENT_HEAD" > "$NOTIFIED_FILE"
    rm -f "$ALERTED_FILE" 2>/dev/null || true
else
    LAST_ALERTED=""
    if [[ -f "$ALERTED_FILE" ]]; then
        LAST_ALERTED=$(cat "$ALERTED_FILE")
    fi

    if [[ "$LAST_ALERTED" != "$CURRENT_HEAD" ]]; then
        send_notification "⚠️ RedCap Layer B 收尾审计发现缺口（${HOST} SessionEnd）\n\n问题：缺少按模板归档的任务完成报告\n\n审计输出:\n$REPORT_OUTPUT\n\nCommits:\n$COMMIT_LOG"
        echo "$CURRENT_HEAD" > "$ALERTED_FILE"
    fi
fi

cleanup_session_files
exit 0

#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap 框架 — explore-notes 未归档提醒
#
# Layer B 书记协议的非阻塞提醒脚本。可被 Stop / SessionEnd 链复用。
# ─────────────────────────────────────────────────────────

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
EXPLORE_NOTES="$REDCAP_ROOT/compass/knowledge/explore-notes.md"
NOTIFIER="$SCRIPT_DIR/feishu-notifier.py"
ALERT_MARKER="/tmp/redcap-explore-notes-last-alert.sig"

if [[ ! -f "$EXPLORE_NOTES" ]]; then
    exit 0
fi

UNARCHIVED_COUNT=$(awk '
    /^## \[/ {
        if (in_entry && !archived) {
            count++
        }
        in_entry=1
        archived=0
    }
    in_entry && /\[ARCHIVED/ { archived=1 }
    END {
        if (in_entry && !archived) {
            count++
        }
        print count+0
    }
' "$EXPLORE_NOTES")

if [[ "$UNARCHIVED_COUNT" -le 0 ]]; then
    rm -f "$ALERT_MARKER" 2>/dev/null || true
    exit 0
fi

if [[ "${REDCAP_SKIP_FEISHU:-0}" == "1" || ! -f "$NOTIFIER" ]]; then
    exit 0
fi

CURRENT_SIGNATURE=$(shasum "$EXPLORE_NOTES" 2>/dev/null | awk '{print $1}')
LAST_SIGNATURE=""
if [[ -f "$ALERT_MARKER" ]]; then
    LAST_SIGNATURE=$(cat "$ALERT_MARKER")
fi

if [[ -n "$CURRENT_SIGNATURE" && "$CURRENT_SIGNATURE" == "$LAST_SIGNATURE" ]]; then
    exit 0
fi

python3 "$NOTIFIER" notify \
    "⚠️ 探索笔记提醒\n\n存在 ${UNARCHIVED_COUNT} 个未归档的探讨条目，请在 PM Gate 前归档或沉淀到 .dev-task.md\n\n文件：compass/knowledge/explore-notes.md" \
    --project "redcap" 2>/dev/null || true

if [[ -n "$CURRENT_SIGNATURE" ]]; then
    echo "$CURRENT_SIGNATURE" > "$ALERT_MARKER"
fi

exit 0

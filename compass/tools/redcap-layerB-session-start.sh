#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap 框架 — Layer B SessionStart 统一入口
#
# 供 Claude InstructionsLoaded / Gemini SessionStart / Copilot sessionStart
# 复用。职责只有一个：捕获当前 HEAD，作为本次会话的基线。
# ─────────────────────────────────────────────────────────

set -u

HOST="${1:-}"

if [[ -z "$HOST" ]]; then
    echo "[redcap-layerB-session-start] ERROR: host is required" >&2
    exit 2
fi

cat > /dev/null || true  # 消费 stdin，兼容所有宿主

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HEAD_FILE="/tmp/redcap-layerB-${HOST}-initial-head"
REPORT_MARKER="/tmp/redcap-layerB-${HOST}-current-report-path"

rm -f "$REPORT_MARKER" 2>/dev/null || true

git -C "$REDCAP_ROOT" rev-parse HEAD 2>/dev/null > "$HEAD_FILE" || true

# Claude 旧链路兼容：保留历史文件名，避免仍在使用旧 Stop hook 的环境失效。
if [[ "$HOST" == "claude" ]]; then
    cp "$HEAD_FILE" /tmp/redcap-claude-initial-head 2>/dev/null || true
fi

exit 0

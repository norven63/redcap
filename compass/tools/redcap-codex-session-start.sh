#!/usr/bin/env bash
# 用途：Codex 生命周期 Hook 适配脚本；在 SessionStart 时接入 RedCap 复活与状态恢复。
# Dictionary: references/file-lookup-dictionary.md#skill-and-host-distribution

set -u

INPUT="$(cat)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

json_field() {
    local field="$1"
    REDCAP_CODEX_HOOK_INPUT="$INPUT" python3 - "$field" <<'PY'
import json
import os
import sys

field = sys.argv[1]
try:
    payload = json.loads(os.environ.get("REDCAP_CODEX_HOOK_INPUT", "{}"))
except Exception:
    payload = {}
value = payload.get(field, "")
print(value if isinstance(value, str) else "")
PY
}

HOOK_CWD="$(json_field cwd)"
HOST_SESSION_ID="$(json_field session_id)"

if [[ -z "$HOOK_CWD" ]]; then
    HOOK_CWD="$REDCAP_ROOT"
fi

set +e
REDCAP_HOOK_CWD="$HOOK_CWD" \
REDCAP_HOST_SESSION_ID="$HOST_SESSION_ID" \
REDCAP_SKIP_FEISHU="${REDCAP_SKIP_FEISHU:-1}" \
    bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" codex <<<"$INPUT"
status=$?
set -e

if [[ -n "${REDCAP_CODEX_HOOK_MARKER_DIR:-}" ]]; then
    mkdir -p "$REDCAP_CODEX_HOOK_MARKER_DIR" 2>/dev/null || true
    printf '{"event":"SessionStart","status":%s,"host":"codex"}\n' "$status" >"$REDCAP_CODEX_HOOK_MARKER_DIR/session-start.json" 2>/dev/null || true
fi

if [[ "$status" -ne 0 ]]; then
    python3 - <<'PY'
import json

print(json.dumps({
    "continue": True,
    "systemMessage": "RedCap Codex SessionStart hook ran but degraded; run ./revive-cap.sh if the workspace status looks stale.",
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "RedCap SessionStart degraded. Prefer ./revive-cap.sh before editing if status is unclear."
    }
}, ensure_ascii=False))
PY
fi

exit 0

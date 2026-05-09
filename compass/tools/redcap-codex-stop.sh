#!/usr/bin/env bash
# 用途：Codex 生命周期 Hook 收尾适配；在 Stop 时接入 Layer B 收口检查并避免循环续写。
# Dictionary: references/file-lookup-dictionary.md#skill-and-host-distribution

set -u

INPUT="$(cat)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/redcap-interop-governance.sh"

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
if isinstance(value, bool):
    print("true" if value else "false")
elif isinstance(value, str):
    print(value)
else:
    print("")
PY
}

HOOK_CWD="$(json_field cwd)"
HOST_SESSION_ID="$(json_field session_id)"
STOP_HOOK_ACTIVE="$(json_field stop_hook_active)"

if [[ "$STOP_HOOK_ACTIVE" == "true" ]]; then
    printf '{"continue":true}\n'
    exit 0
fi

if [[ -z "$HOOK_CWD" ]]; then
    HOOK_CWD="$REDCAP_ROOT"
fi

write_marker() {
    local status="$1"

    if [[ -n "${REDCAP_CODEX_HOOK_MARKER_DIR:-}" ]]; then
        mkdir -p "$REDCAP_CODEX_HOOK_MARKER_DIR" 2>/dev/null || true
        printf '{"event":"Stop","status":%s,"host":"codex"}\n' "$status" >"$REDCAP_CODEX_HOOK_MARKER_DIR/stop.json" 2>/dev/null || true
    fi
}

if [[ "${REDCAP_CODEX_HOOK_E2E_PROBE:-0}" == "1" ]]; then
    write_marker 0
    printf '{"continue":true}\n'
    exit 0
fi

log_dir="${REDCAP_RUNTIME_BASE_DIR:-${TMPDIR:-/tmp}/redcap-runtime}/codex-hooks"
mkdir -p "$log_dir" 2>/dev/null || true
log_file="$log_dir/stop.log"

set +e
REDCAP_HOOK_CWD="$HOOK_CWD" \
REDCAP_HOST_SESSION_ID="$HOST_SESSION_ID" \
REDCAP_SKIP_FEISHU="${REDCAP_SKIP_FEISHU:-1}" \
    bash "$SCRIPT_DIR/redcap-layerB-session-end.sh" codex >"$log_file" 2>&1
status=$?
set -e

write_marker "$status"

if [[ "$status" -ne 0 ]]; then
    python3 - <<'PY'
import json

print(json.dumps({
    "decision": "block",
    "reason": "RedCap Codex Stop hook detected a closeout error. Continue one more pass: inspect the hook log, repair the pending closeout, then rerun the targeted checks."
}, ensure_ascii=False))
PY
    exit 0
fi

if redcap_interop_pending_closure_exists "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md"; then
    python3 - <<'PY'
import json

print(json.dumps({
    "decision": "block",
    "reason": "RedCap still has pending closeout work. Continue one more pass: resolve the pending closure or explicitly record why it remains blocked."
}, ensure_ascii=False))
PY
    exit 0
fi

printf '{"continue":true}\n'

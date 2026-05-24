#!/usr/bin/env bash
# 用途：Codex Stop hook 会话归属门；防止一个会话接管另一个会话的未完成收尾。
# Dictionary: references/file-lookup-dictionary.md#skill-and-host-distribution

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/redcap-runtime-state.sh"
source "$SCRIPT_DIR/redcap-dev-task.sh"

COMMAND="${1:-}"
shift || true

ROOT="$REDCAP_ROOT"
TASK_FILE="$REDCAP_ROOT/.dev-task.md"
HOST="codex"
SESSION_ID=""
INTENT="execution"
REASON=""

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --root)
            ROOT="$2"
            shift 2
            ;;
        --task-file)
            TASK_FILE="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --session-id)
            SESSION_ID="$2"
            shift 2
            ;;
        --intent)
            INTENT="$2"
            shift 2
            ;;
        --reason)
            REASON="$2"
            shift 2
            ;;
        *)
            echo "[redcap-codex-session-ownership] unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

session_hash() {
    python3 - "$1" <<'PY'
import hashlib
import sys

print(hashlib.sha256(sys.argv[1].encode("utf-8")).hexdigest())
PY
}

ownership_dir() {
    printf '%s/codex-session-ownership\n' "$(redcap_runtime_project_path_for_root "$ROOT" "governance")"
}

ownership_file() {
    local sid_hash
    sid_hash="$(session_hash "$SESSION_ID")"
    printf '%s/%s-%s.json\n' "$(ownership_dir)" "$HOST" "$sid_hash"
}

task_identity_json() {
    local task_id confirmed active_slice
    task_id="$(redcap_dev_task_extract_kv "$TASK_FILE" "task_id" 2>/dev/null || true)"
    confirmed="$(redcap_dev_task_confirmed_hash "$TASK_FILE" 2>/dev/null || true)"
    active_slice="$(redcap_dev_task_extract_kv "$TASK_FILE" "active_slice" 2>/dev/null || true)"
    python3 - "$task_id" "$confirmed" "$active_slice" <<'PY'
import json
import sys

print(json.dumps({
    "task_id": sys.argv[1],
    "confirmed_hash": sys.argv[2],
    "active_slice": sys.argv[3],
}, ensure_ascii=False))
PY
}

claim() {
    local dir file identity now
    if [[ -z "$SESSION_ID" ]]; then
        echo "SESSION_OWNERSHIP_OK state=advisory-only reason=missing-session-id"
        return 0
    fi
    identity="$(task_identity_json)"
    now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    dir="$(ownership_dir)"
    file="$(ownership_file)"
    mkdir -p "$dir"
    chmod 700 "$dir" 2>/dev/null || true
    python3 - "$file" "$HOST" "$(session_hash "$SESSION_ID")" "$INTENT" "$REASON" "$now" "$identity" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
identity = json.loads(sys.argv[7])
payload = {
    "version": 1,
    "host": sys.argv[2],
    "session_id_sha256": sys.argv[3],
    "owner_state": "claimed",
    "intent": sys.argv[4],
    "reason": sys.argv[5],
    "updated_at": sys.argv[6],
    **identity,
}
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
    echo "SESSION_OWNERSHIP_OK state=claimed file=$file"
}

check() {
    local file identity
    if [[ -z "$SESSION_ID" ]]; then
        echo "SESSION_OWNERSHIP_OK state=advisory-only reason=missing-session-id"
        return 0
    fi
    file="$(ownership_file)"
    if [[ ! -f "$file" ]]; then
        echo "SESSION_OWNERSHIP_OK state=advisory-only reason=unclaimed"
        return 0
    fi
    identity="$(task_identity_json)"
    python3 - "$file" "$identity" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
current = json.loads(sys.argv[2])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print("SESSION_OWNERSHIP_OK state=advisory-only reason=invalid-claim")
    raise SystemExit(0)

allowed_intents = {"execution", "closeout", "rescue"}
matches = (
    payload.get("owner_state") == "claimed"
    and payload.get("intent") in allowed_intents
    and payload.get("task_id") == current.get("task_id")
    and payload.get("confirmed_hash") == current.get("confirmed_hash")
    and (not payload.get("active_slice") or payload.get("active_slice") == current.get("active_slice"))
)
if matches:
    print("SESSION_OWNERSHIP_OK state=owned reason=matched-task")
else:
    print("SESSION_OWNERSHIP_OK state=advisory-only reason=task-mismatch")
PY
}

case "$COMMAND" in
    claim)
        claim
        ;;
    check)
        check
        ;;
    *)
        echo "[redcap-codex-session-ownership] usage: $0 claim|check [--root ROOT] [--task-file FILE] [--host HOST] [--session-id ID]" >&2
        exit 2
        ;;
esac

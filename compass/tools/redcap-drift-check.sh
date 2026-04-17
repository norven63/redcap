#!/usr/bin/env bash
# shellcheck shell=bash
# Check whether current work still matches the canonical Layer B task ledger.

set -uo pipefail

MODE="${1:-workspace}"
HOST="${2:-}"
TASK_FILE="${3:-}"
BASELINE="${4:-}"
CURRENT_HEAD="${5:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/redcap-runtime-state.sh"
source "$SCRIPT_DIR/redcap-dev-task.sh"

TASK_FILE=$(redcap_dev_task_resolve_file "$TASK_FILE")

if ! REDCAP_RUNTIME_SESSION_ID="${REDCAP_RUNTIME_SESSION_ID:-}" \
    REDCAP_RUNTIME_CAPABILITY="${REDCAP_RUNTIME_CAPABILITY:-}" \
    REDCAP_HOST_PROCESS_PID="${REDCAP_HOST_PROCESS_PID:-$PPID}" \
    bash "$SCRIPT_DIR/redcap-pm-gate-check.sh" strict "$HOST" "$TASK_FILE" >/tmp/redcap-pm-gate-hash.$$ 2>/tmp/redcap-drift-check-pm.$$; then
    cat /tmp/redcap-drift-check-pm.$$ >&2 || true
    rm -f /tmp/redcap-pm-gate-hash.$$ /tmp/redcap-drift-check-pm.$$ 2>/dev/null || true
    exit 1
fi

CONFIRMED_HASH=$(cat /tmp/redcap-pm-gate-hash.$$ 2>/dev/null || true)
rm -f /tmp/redcap-pm-gate-hash.$$ /tmp/redcap-drift-check-pm.$$ 2>/dev/null || true

TOP_GOAL=$(redcap_dev_task_extract_kv "$TASK_FILE" "top_goal" 2>/dev/null || true)
ACTIVE_SLICE=$(redcap_dev_task_extract_kv "$TASK_FILE" "active_slice" 2>/dev/null || true)
BACKLOG_SOURCE=$(redcap_dev_task_extract_kv "$TASK_FILE" "backlog_source" 2>/dev/null || true)
BACKLOG_ID=$(redcap_dev_task_extract_kv "$TASK_FILE" "backlog_id" 2>/dev/null || true)
BACKLOG_ITEM=$(redcap_dev_task_extract_kv "$TASK_FILE" "backlog_item" 2>/dev/null || true)
ALLOWED_GLOBS=()
while IFS= read -r line; do
    if [[ -n "$line" ]]; then
        ALLOWED_GLOBS+=("$line")
    fi
done < <(redcap_dev_task_list_bullets "$TASK_FILE" "允许修改范围" 2>/dev/null)

if [[ ${#ALLOWED_GLOBS[@]} -eq 0 ]]; then
    echo "[redcap-drift-check] no allowed file globs declared in $TASK_FILE" >&2
    exit 1
fi

attach_runtime_if_possible() {
    if [[ -n "${REDCAP_RUNTIME_SESSION_ID:-}" && -n "${REDCAP_RUNTIME_CAPABILITY:-}" ]]; then
        redcap_runtime_attach_existing "$REDCAP_RUNTIME_SESSION_ID" "$REDCAP_RUNTIME_CAPABILITY" 2>/dev/null
        return
    fi

    if [[ -n "$HOST" ]]; then
        redcap_runtime_attach_from_process_claim "$HOST" 2>/dev/null
    fi
}

STAMPED_HASH=""
STAMPED_SLICE=""
STAMPED_BACKLOG_SOURCE=""
STAMPED_BACKLOG_ID=""
STAMPED_BACKLOG_ITEM=""
if attach_runtime_if_possible; then
    STAMPED_HASH=$(redcap_runtime_read_text "layerB/control-plane/confirmed.hash" 2>/dev/null || true)
    STAMPED_SLICE=$(redcap_runtime_read_text "layerB/control-plane/active-slice" 2>/dev/null || true)
    STAMPED_BACKLOG_SOURCE=$(redcap_runtime_read_text "layerB/control-plane/backlog-source" 2>/dev/null || true)
    STAMPED_BACKLOG_ID=$(redcap_runtime_read_text "layerB/control-plane/backlog-id" 2>/dev/null || true)
    STAMPED_BACKLOG_ITEM=$(redcap_runtime_read_text "layerB/control-plane/backlog-item" 2>/dev/null || true)

    if [[ -n "$STAMPED_HASH" && "$STAMPED_HASH" != "$CONFIRMED_HASH" ]]; then
        echo "[redcap-drift-check] confirmed requirement hash changed without re-anchor" >&2
        echo "  stamped: $STAMPED_HASH" >&2
        echo "  current: $CONFIRMED_HASH" >&2
        exit 1
    fi
    if [[ -n "$STAMPED_SLICE" && "$STAMPED_SLICE" != "$ACTIVE_SLICE" ]]; then
        echo "[redcap-drift-check] active_slice drift detected" >&2
        echo "  stamped: $STAMPED_SLICE" >&2
        echo "  current: $ACTIVE_SLICE" >&2
        exit 1
    fi
    if [[ -n "$STAMPED_BACKLOG_SOURCE" && "$STAMPED_BACKLOG_SOURCE" != "$BACKLOG_SOURCE" ]]; then
        echo "[redcap-drift-check] backlog_source drift detected" >&2
        echo "  stamped: $STAMPED_BACKLOG_SOURCE" >&2
        echo "  current: $BACKLOG_SOURCE" >&2
        exit 1
    fi
    if [[ -n "$STAMPED_BACKLOG_ID" && "$STAMPED_BACKLOG_ID" != "$BACKLOG_ID" ]]; then
        echo "[redcap-drift-check] backlog_id drift detected" >&2
        echo "  stamped: $STAMPED_BACKLOG_ID" >&2
        echo "  current: $BACKLOG_ID" >&2
        exit 1
    fi
    if [[ -n "$STAMPED_BACKLOG_ITEM" && "$STAMPED_BACKLOG_ITEM" != "$BACKLOG_ITEM" ]]; then
        echo "[redcap-drift-check] backlog_item drift detected" >&2
        echo "  stamped: $STAMPED_BACKLOG_ITEM" >&2
        echo "  current: $BACKLOG_ITEM" >&2
        exit 1
    fi

    redcap_runtime_write_text "layerB/control-plane/confirmed.hash" "$CONFIRMED_HASH" || true
    redcap_runtime_write_text "layerB/control-plane/active-slice" "$ACTIVE_SLICE" || true
    redcap_runtime_write_text "layerB/control-plane/top-goal" "$TOP_GOAL" || true
    redcap_runtime_write_text "layerB/control-plane/backlog-source" "$BACKLOG_SOURCE" || true
    redcap_runtime_write_text "layerB/control-plane/backlog-id" "$BACKLOG_ID" || true
    redcap_runtime_write_text "layerB/control-plane/backlog-item" "$BACKLOG_ITEM" || true
    redcap_runtime_write_text "layerB/control-plane/last-drift-check-at" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" || true
    redcap_runtime_write_text "layerB/control-plane/last-drift-check-mode" "$MODE" || true
elif [[ -n "$HOST" ]]; then
    COMPAT_PREFIX=$(redcap_runtime_compat_path_for_root "$REDCAP_ROOT" "legacy-fallback/layerB-${HOST}")
    STAMPED_HASH=$(cat "${COMPAT_PREFIX}-confirmed.hash" 2>/dev/null || true)
    STAMPED_SLICE=$(cat "${COMPAT_PREFIX}-active-slice" 2>/dev/null || true)
    STAMPED_BACKLOG_SOURCE=$(cat "${COMPAT_PREFIX}-backlog-source" 2>/dev/null || true)
    STAMPED_BACKLOG_ID=$(cat "${COMPAT_PREFIX}-backlog-id" 2>/dev/null || true)
    STAMPED_BACKLOG_ITEM=$(cat "${COMPAT_PREFIX}-backlog-item" 2>/dev/null || true)

    if [[ -n "$STAMPED_HASH" && "$STAMPED_HASH" != "$CONFIRMED_HASH" ]]; then
        echo "[redcap-drift-check] compat fallback confirmed hash changed without re-anchor" >&2
        echo "  stamped: $STAMPED_HASH" >&2
        echo "  current: $CONFIRMED_HASH" >&2
        exit 1
    fi
    if [[ -n "$STAMPED_SLICE" && "$STAMPED_SLICE" != "$ACTIVE_SLICE" ]]; then
        echo "[redcap-drift-check] compat fallback active_slice drift detected" >&2
        echo "  stamped: $STAMPED_SLICE" >&2
        echo "  current: $ACTIVE_SLICE" >&2
        exit 1
    fi
    if [[ -n "$STAMPED_BACKLOG_SOURCE" && "$STAMPED_BACKLOG_SOURCE" != "$BACKLOG_SOURCE" ]]; then
        echo "[redcap-drift-check] compat fallback backlog_source drift detected" >&2
        echo "  stamped: $STAMPED_BACKLOG_SOURCE" >&2
        echo "  current: $BACKLOG_SOURCE" >&2
        exit 1
    fi
    if [[ -n "$STAMPED_BACKLOG_ID" && "$STAMPED_BACKLOG_ID" != "$BACKLOG_ID" ]]; then
        echo "[redcap-drift-check] compat fallback backlog_id drift detected" >&2
        echo "  stamped: $STAMPED_BACKLOG_ID" >&2
        echo "  current: $BACKLOG_ID" >&2
        exit 1
    fi
    if [[ -n "$STAMPED_BACKLOG_ITEM" && "$STAMPED_BACKLOG_ITEM" != "$BACKLOG_ITEM" ]]; then
        echo "[redcap-drift-check] compat fallback backlog_item drift detected" >&2
        echo "  stamped: $STAMPED_BACKLOG_ITEM" >&2
        echo "  current: $BACKLOG_ITEM" >&2
        exit 1
    fi

    mkdir -p "$(dirname "${COMPAT_PREFIX}-confirmed.hash")" 2>/dev/null || true
    printf '%s\n' "$CONFIRMED_HASH" > "${COMPAT_PREFIX}-confirmed.hash"
    printf '%s\n' "$ACTIVE_SLICE" > "${COMPAT_PREFIX}-active-slice"
    printf '%s\n' "$TOP_GOAL" > "${COMPAT_PREFIX}-top-goal"
    printf '%s\n' "$BACKLOG_SOURCE" > "${COMPAT_PREFIX}-backlog-source"
    printf '%s\n' "$BACKLOG_ID" > "${COMPAT_PREFIX}-backlog-id"
    printf '%s\n' "$BACKLOG_ITEM" > "${COMPAT_PREFIX}-backlog-item"
fi

TMP_FILES=$(mktemp)
TMP_GLOBS=$(mktemp)
cleanup() {
    rm -f "$TMP_FILES" "$TMP_GLOBS" 2>/dev/null || true
}
trap cleanup EXIT

if [[ -n "$BASELINE" && -n "$CURRENT_HEAD" ]]; then
    git -C "$REDCAP_ROOT" --no-pager diff --name-only "$BASELINE..$CURRENT_HEAD" 2>/dev/null | sed '/^[[:space:]]*$/d' | sort -u > "$TMP_FILES"
else
    {
        git -C "$REDCAP_ROOT" --no-pager diff --name-only 2>/dev/null
        git -C "$REDCAP_ROOT" --no-pager diff --cached --name-only 2>/dev/null
    } | sed '/^[[:space:]]*$/d' | sort -u > "$TMP_FILES"
fi

printf '%s\n' "${ALLOWED_GLOBS[@]}" > "$TMP_GLOBS"

python3 - "$TMP_FILES" "$TMP_GLOBS" <<'PY'
import fnmatch
import pathlib
import sys

files_path = pathlib.Path(sys.argv[1])
globs_path = pathlib.Path(sys.argv[2])
files = [line.strip() for line in files_path.read_text(encoding="utf-8").splitlines() if line.strip()]
globs = [line.strip() for line in globs_path.read_text(encoding="utf-8").splitlines() if line.strip()]

violations = []
for path in files:
    if not any(fnmatch.fnmatch(path, pattern) for pattern in globs):
        violations.append(path)

if violations:
    print("[redcap-drift-check] changed files exceed current active_slice scope", file=sys.stderr)
    for item in violations:
        print(f"  - {item}", file=sys.stderr)
    sys.exit(1)
PY

PYTHON_STATUS=$?
if [[ $PYTHON_STATUS -ne 0 ]]; then
    exit "$PYTHON_STATUS"
fi

exit 0

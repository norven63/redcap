#!/usr/bin/env bash
# shellcheck shell=bash
# Keep a host workboard as a mirror-only view of RedCap canonical task metadata.

set -uo pipefail

MODE="${1:-sync}"
WORKBOARD_FILE="${2:-}"
TASK_FILE="${3:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/redcap-dev-task.sh"

if [[ -z "$WORKBOARD_FILE" ]]; then
    echo "usage: $0 <sync|check> <workboard_file> [task_file]" >&2
    exit 2
fi

TASK_FILE=$(redcap_dev_task_resolve_file "$TASK_FILE")
if ! bash "$SCRIPT_DIR/redcap-pm-gate-check.sh" strict "" "$TASK_FILE" >/tmp/redcap-host-workboard-hash.$$ 2>/dev/null; then
    rm -f /tmp/redcap-host-workboard-hash.$$ 2>/dev/null || true
    echo "[redcap-host-workboard-sync] canonical task ledger is invalid: $TASK_FILE" >&2
    exit 1
fi

CONFIRMED_HASH=$(cat /tmp/redcap-host-workboard-hash.$$ 2>/dev/null || true)
rm -f /tmp/redcap-host-workboard-hash.$$ 2>/dev/null || true

TASK_ID=$(redcap_dev_task_extract_kv "$TASK_FILE" "task_id" 2>/dev/null || true)
TOP_GOAL=$(redcap_dev_task_extract_kv "$TASK_FILE" "top_goal" 2>/dev/null || true)
ACTIVE_SLICE=$(redcap_dev_task_extract_kv "$TASK_FILE" "active_slice" 2>/dev/null || true)
SUBTASK_OF=$(redcap_dev_task_extract_kv "$TASK_FILE" "subtask_of" 2>/dev/null || true)
HOST_SURFACE_POLICY=$(redcap_dev_task_extract_kv "$TASK_FILE" "host_surface_policy" 2>/dev/null || true)
BACKLOG_SOURCE=$(redcap_dev_task_extract_kv "$TASK_FILE" "backlog_source" 2>/dev/null || true)
BACKLOG_ID=$(redcap_dev_task_extract_kv "$TASK_FILE" "backlog_id" 2>/dev/null || true)
BACKLOG_ITEM=$(redcap_dev_task_extract_kv "$TASK_FILE" "backlog_item" 2>/dev/null || true)

if [[ ! -f "$WORKBOARD_FILE" ]]; then
    echo "[redcap-host-workboard-sync] workboard not found: $WORKBOARD_FILE" >&2
    exit 1
fi

MARKER_START="<!-- redcap:canonical-pointer:start -->"
MARKER_END="<!-- redcap:canonical-pointer:end -->"
POINTER_BLOCK=$(cat <<EOF
$MARKER_START
## RedCap Canonical Pointer
- task_id: $TASK_ID
- canonical_path: $TASK_FILE
- source_of_truth: .dev-task.md
- top_goal: $TOP_GOAL
- active_slice: $ACTIVE_SLICE
- subtask_of: $SUBTASK_OF
- confirmed_hash: $CONFIRMED_HASH
- host_surface_policy: $HOST_SURFACE_POLICY
- backlog_source: $BACKLOG_SOURCE
- backlog_id: $BACKLOG_ID
- backlog_item: $BACKLOG_ITEM
$MARKER_END
EOF
)

case "$MODE" in
    sync)
        if ! python3 - "$WORKBOARD_FILE" "$MARKER_START" "$MARKER_END" "$POINTER_BLOCK" <<'PY'
import pathlib
import sys

workboard = pathlib.Path(sys.argv[1])
marker_start = sys.argv[2]
marker_end = sys.argv[3]
pointer_block = sys.argv[4]
text = workboard.read_text(encoding="utf-8")

start = text.find(marker_start)
end = text.find(marker_end)
if start != -1 and end != -1 and end >= start:
    end += len(marker_end)
    new_text = text[:start].rstrip() + "\n\n" + pointer_block + "\n" + text[end:].lstrip("\n")
else:
    suffix = "" if text.endswith("\n") else "\n"
    new_text = text + suffix + "\n" + pointer_block + "\n"

workboard.write_text(new_text, encoding="utf-8")
PY
        then
            exit 1
        fi
        ;;
    check)
        if ! python3 - "$WORKBOARD_FILE" "$MARKER_START" "$MARKER_END" "$TASK_ID" "$TASK_FILE" "$TOP_GOAL" "$ACTIVE_SLICE" "$SUBTASK_OF" "$CONFIRMED_HASH" "$HOST_SURFACE_POLICY" "$BACKLOG_SOURCE" "$BACKLOG_ID" "$BACKLOG_ITEM" <<'PY'
import pathlib
import sys

workboard = pathlib.Path(sys.argv[1])
marker_start = sys.argv[2]
marker_end = sys.argv[3]
task_id = sys.argv[4]
task_file = sys.argv[5]
top_goal = sys.argv[6]
active_slice = sys.argv[7]
subtask_of = sys.argv[8]
confirmed_hash = sys.argv[9]
host_surface_policy = sys.argv[10]
backlog_source = sys.argv[11]
backlog_id = sys.argv[12]
backlog_item = sys.argv[13]
text = workboard.read_text(encoding="utf-8")
start = text.find(marker_start)
end = text.find(marker_end)
if start == -1 or end == -1 or end < start:
    print("[redcap-host-workboard-sync] canonical pointer block missing", file=sys.stderr)
    sys.exit(1)
block = text[start:end + len(marker_end)]
required = [
    f"- task_id: {task_id}",
    f"- canonical_path: {task_file}",
    "- source_of_truth: .dev-task.md",
    f"- top_goal: {top_goal}",
    f"- active_slice: {active_slice}",
    f"- subtask_of: {subtask_of}",
    f"- confirmed_hash: {confirmed_hash}",
    f"- host_surface_policy: {host_surface_policy}",
    f"- backlog_source: {backlog_source}",
    f"- backlog_id: {backlog_id}",
    f"- backlog_item: {backlog_item}",
]
missing = [item for item in required if item not in block]
if missing:
    print("[redcap-host-workboard-sync] host workboard pointer drift detected", file=sys.stderr)
    for item in missing:
        print(f"  - missing: {item}", file=sys.stderr)
    sys.exit(1)
PY
        then
            exit 1
        fi
        ;;
    *)
        echo "usage: $0 <sync|check> <workboard_file> [task_file]" >&2
        exit 2
        ;;
esac

exit 0

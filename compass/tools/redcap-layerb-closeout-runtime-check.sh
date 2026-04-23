#!/usr/bin/env bash
# shellcheck shell=bash
# Sanity check for the Layer B unified closeout runtime contract.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TASK_FILE="${1:-$REDCAP_ROOT/.dev-task.md}"
RUNTIME_SCRIPT="$SCRIPT_DIR/redcap-layerb-closeout-runtime.sh"
ROOT_ENTRY="$REDCAP_ROOT/closeout-cap.sh"
PRISM_ACCEPTANCE_SCRIPT="$SCRIPT_DIR/redcap-prism-acceptance-check.sh"
PRISM_ACCEPTANCE_BIND_SCRIPT="$SCRIPT_DIR/redcap-prism-acceptance-bind.sh"

[[ -x "$RUNTIME_SCRIPT" ]] || {
    echo "[redcap-layerb-closeout-runtime-check] missing runtime script: $RUNTIME_SCRIPT" >&2
    exit 1
}

[[ -x "$ROOT_ENTRY" ]] || {
    echo "[redcap-layerb-closeout-runtime-check] missing root entry: $ROOT_ENTRY" >&2
    exit 1
}

[[ -x "$PRISM_ACCEPTANCE_SCRIPT" ]] || {
    echo "[redcap-layerb-closeout-runtime-check] missing prism acceptance script: $PRISM_ACCEPTANCE_SCRIPT" >&2
    exit 1
}

[[ -x "$PRISM_ACCEPTANCE_BIND_SCRIPT" ]] || {
    echo "[redcap-layerb-closeout-runtime-check] missing prism acceptance bind script: $PRISM_ACCEPTANCE_BIND_SCRIPT" >&2
    exit 1
}

python3 - "$TASK_FILE" <<'PY'
import pathlib
import sys

text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
if "## 执行承诺账本" not in text:
    raise SystemExit("[redcap-layerb-closeout-runtime-check] .dev-task.md missing '## 执行承诺账本' section")
PY

bash "$RUNTIME_SCRIPT" sync-promises --task-file "$TASK_FILE" >/dev/null
bash "$RUNTIME_SCRIPT" status --task-file "$TASK_FILE" >/dev/null
bash "$PRISM_ACCEPTANCE_SCRIPT" --task-file "$TASK_FILE" >/dev/null || true

ACTIVE_SLICE="$(python3 - "$TASK_FILE" <<'PY'
import pathlib
import re
import sys

text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
meta = False
for line in text.splitlines():
    if line.startswith("## "):
        heading = line[3:].strip()
        if meta and not heading.startswith("控制面元数据"):
            break
        meta = heading.startswith("控制面元数据")
        continue
    if meta:
        match = re.match(r"^active_slice:\s*(.*?)\s*$", line)
        if match:
            print(match.group(1))
            break
PY
)"

case "$ACTIVE_SLICE" in
    task-complete|closeout-complete)
        bash "$RUNTIME_SCRIPT" audit-open --task-file "$TASK_FILE" --mode diagnose >/dev/null
        ;;
esac

echo "LAYERB_CLOSEOUT_RUNTIME_OK"

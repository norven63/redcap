#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap 框架 — 注册当前任务报告路径
#
# 作用：为 SessionEnd 收尾链显式声明“这份报告属于当前任务”。
# 未提交但已暂存的报告，必须先登记路径，审计才会接受。
# ─────────────────────────────────────────────────────────

set -u

if [[ $# -ne 2 ]]; then
    echo "usage: $0 <host> <report_path>" >&2
    exit 2
fi

HOST="$1"
INPUT_PATH="$2"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MARKER_FILE="/tmp/redcap-layerB-${HOST}-current-report-path"

if [[ "$INPUT_PATH" = /* ]]; then
    ABS_PATH="$INPUT_PATH"
else
    ABS_PATH="$PWD/$INPUT_PATH"
fi

case "$ABS_PATH" in
    "$REDCAP_ROOT"/compass/docs/task-reports/*.md) ;;
    *)
        echo "[redcap-task-report-register] report must live under compass/docs/task-reports/" >&2
        exit 1
        ;;
esac

if [[ ! -f "$ABS_PATH" ]]; then
    echo "[redcap-task-report-register] report file not found: $ABS_PATH" >&2
    exit 1
fi

REL_PATH="${ABS_PATH#$REDCAP_ROOT/}"
echo "$REL_PATH" > "$MARKER_FILE"
echo "$REL_PATH"
exit 0

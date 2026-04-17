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
source "$SCRIPT_DIR/redcap-runtime-state.sh"
source "$SCRIPT_DIR/redcap-interop-governance.sh"

if [[ "$INPUT_PATH" = /* ]]; then
    ABS_PATH="$INPUT_PATH"
else
    ABS_PATH="$PWD/$INPUT_PATH"
fi

ABS_PATH=$(redcap_interop_resolve_report_abs_path "$REDCAP_ROOT" "$ABS_PATH" 2>/dev/null || true)
if [[ -z "$ABS_PATH" ]]; then
    echo "[redcap-task-report-register] report must resolve under compass/docs/task-reports/" >&2
    exit 1
fi

if [[ ! -f "$ABS_PATH" ]]; then
    echo "[redcap-task-report-register] report file not found: $ABS_PATH" >&2
    exit 1
fi

REL_PATH="${ABS_PATH#$REDCAP_ROOT/}"
if redcap_runtime_attach_from_process_claim "$HOST" 2>/dev/null; then
    INITIAL_HEAD_FILE=$(redcap_runtime_path "layerB/initial-head")
    REGISTER_BASELINE=""
    REGISTER_HEAD=$(git -C "$REDCAP_ROOT" rev-parse HEAD 2>/dev/null || true)
    if [[ -f "$INITIAL_HEAD_FILE" ]]; then
        REGISTER_BASELINE=$(cat "$INITIAL_HEAD_FILE" 2>/dev/null || true)
    fi

    if redcap_interop_pending_closure_exists "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md"; then
        PENDING_STATE_FILE=$(redcap_interop_pending_closure_file "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" 2>/dev/null || true)
        PENDING_ARTIFACT_PATH=$(redcap_interop_read_state_field "$PENDING_STATE_FILE" "artifact_path" 2>/dev/null || true)
        if [[ -n "$PENDING_ARTIFACT_PATH" && "$PENDING_ARTIFACT_PATH" != "$REL_PATH" ]]; then
            redcap_interop_record_closure_event \
                "$REDCAP_ROOT" \
                "task-report-register-replaced-artifact" \
                "host=$HOST existing_artifact=$PENDING_ARTIFACT_PATH new_artifact=$REL_PATH" \
                >/dev/null 2>&1 || true
        fi
    fi

    if ! redcap_interop_write_pending_closure \
        "$REDCAP_ROOT" \
        "$REDCAP_ROOT/.dev-task.md" \
        "$HOST" \
        "task-report-register" \
        "task-report,review,notify" \
        "report-registered" \
        "$REL_PATH" \
        "$REGISTER_BASELINE" \
        "$REGISTER_HEAD" \
        >/dev/null; then
        echo "[redcap-task-report-register] failed to persist pending closure state" >&2
        exit 1
    fi

    if ! redcap_interop_write_current_report_marker "$REL_PATH" "$REDCAP_ROOT/.dev-task.md"; then
        echo "[redcap-task-report-register] failed to persist current report marker: $REL_PATH" >&2
        exit 1
    fi

    redcap_interop_append_closure_ledger \
        "$REDCAP_ROOT" \
        "$REDCAP_ROOT/.dev-task.md" \
        "task-report-register" \
        "pass" \
        "report-registered" \
        "$HOST" \
        "task-report-register" \
        "$REGISTER_BASELINE" \
        "$REGISTER_HEAD" \
        "$REL_PATH" \
        >/dev/null 2>&1 || true
else
    redcap_runtime_record_degraded_mode "$REDCAP_ROOT" "layerB-report-register-missing-claim" "host=$HOST" || true
    echo "[redcap-task-report-register] no runtime process claim available for host=$HOST" >&2
    exit 1
fi
echo "$REL_PATH"
exit 0

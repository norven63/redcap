#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap 框架 — Layer B 任务报告模板审计
#
# 目标：把“最终汇报必须按模板”从对话约束升级为可机器检查的不变量。
# 审计范围：本次 commit 区间内新增/修改的 `compass/docs/task-reports/*.md`
# ─────────────────────────────────────────────────────────

set -u

if [[ $# -lt 2 || $# -gt 4 ]]; then
    echo "usage: $0 <redcap_root> <baseline_head> [current_head] [host]" >&2
    exit 2
fi

REDCAP_ROOT="$1"
BASELINE="$2"
CURRENT_HEAD="${3:-}"
HOST="${4:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/redcap-runtime-state.sh"
source "$SCRIPT_DIR/redcap-interop-governance.sh"

if [[ -z "$CURRENT_HEAD" ]]; then
    CURRENT_HEAD=$(git -C "$REDCAP_ROOT" rev-parse HEAD 2>/dev/null) || exit 1
fi

REPORT_GLOB='compass/docs/task-reports/*.md'
REPORT_MARKER=""
PENDING_CLOSURE_STATE=""
TMP_CHANGED_REPORT_LIST=$(mktemp)

if [[ -n "${REDCAP_RUNTIME_SESSION_ID:-}" && -n "${REDCAP_RUNTIME_CAPABILITY:-}" ]]; then
    if redcap_runtime_attach_existing "$REDCAP_RUNTIME_SESSION_ID" "$REDCAP_RUNTIME_CAPABILITY"; then
        REPORT_MARKER=$(redcap_runtime_path "layerB/current-report-path")
    fi
elif [[ -n "$HOST" ]]; then
    if redcap_runtime_attach_from_process_claim "$HOST" 2>/dev/null; then
        REPORT_MARKER=$(redcap_runtime_path "layerB/current-report-path")
    else
        redcap_runtime_record_degraded_mode "$REDCAP_ROOT" "layerB-report-check-missing-claim" "host=$HOST" || true
    fi
fi

if PENDING_CLOSURE_STATE=$(redcap_interop_pending_closure_file "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" 2>/dev/null); then
    :
else
    PENDING_CLOSURE_STATE=""
fi

TMP_REPORT_LIST=$(mktemp)

git -C "$REDCAP_ROOT" --no-pager diff --diff-filter=ACMR --name-only "$BASELINE..$CURRENT_HEAD" -- "$REPORT_GLOB" 2>/dev/null >> "$TMP_REPORT_LIST" || true
git -C "$REDCAP_ROOT" --no-pager diff --diff-filter=ACMR --name-only "$BASELINE..$CURRENT_HEAD" -- "$REPORT_GLOB" 2>/dev/null >> "$TMP_CHANGED_REPORT_LIST" || true

if [[ -n "$REPORT_MARKER" && -f "$REPORT_MARKER" ]]; then
    MARKED_REPORT=$(cat "$REPORT_MARKER" 2>/dev/null)
    if [[ -n "$MARKED_REPORT" ]]; then
        git -C "$REDCAP_ROOT" --no-pager diff --cached --diff-filter=ACMR --name-only -- "$MARKED_REPORT" 2>/dev/null >> "$TMP_REPORT_LIST" || true
        git -C "$REDCAP_ROOT" --no-pager diff --cached --diff-filter=ACMR --name-only -- "$MARKED_REPORT" 2>/dev/null >> "$TMP_CHANGED_REPORT_LIST" || true
    fi
fi

if [[ -n "$PENDING_CLOSURE_STATE" && -f "$PENDING_CLOSURE_STATE" ]]; then
    PENDING_ARTIFACT_PATH=$(redcap_interop_read_state_field "$PENDING_CLOSURE_STATE" "artifact_path" 2>/dev/null || true)
    if [[ -n "$PENDING_ARTIFACT_PATH" ]]; then
        printf '%s\n' "$PENDING_ARTIFACT_PATH" >> "$TMP_REPORT_LIST"
    fi
fi

REPORT_FILES=()
while IFS= read -r REPORT_FILE; do
    if [[ -n "$REPORT_FILE" ]]; then
        REPORT_FILES+=("$REPORT_FILE")
    fi
done < <(sort -u "$TMP_REPORT_LIST" | sed '/^[[:space:]]*$/d')

CHANGED_REPORTS=()
while IFS= read -r REPORT_FILE; do
    if [[ -n "$REPORT_FILE" ]]; then
        CHANGED_REPORTS+=("$REPORT_FILE")
    fi
done < <(sort -u "$TMP_CHANGED_REPORT_LIST" | sed '/^[[:space:]]*$/d')

rm -f "$TMP_REPORT_LIST" "$TMP_CHANGED_REPORT_LIST"

if [[ ${#REPORT_FILES[@]} -eq 0 ]]; then
    echo "[redcap-task-report-check] missing task report under compass/docs/task-reports/" >&2
    exit 1
fi

REQUIRED_BASE_SECTIONS=(
    "# 任务完成报告："
    "## 一、需求背景"
    "## 二、方案讨论"
    "## 三、落地结果"
    "## 四、人工审核要点"
    "## 五、验证结果"
    "## 六、遗留问题与下一步"
    "## 七、经验沉淀"
    "## 八、附录"
)

REQUIRED_SUMMARY_SECTIONS=(
    "## 零、收尾摘要"
    "### 0.1 需你确认"
    "### 0.2 人工验证"
    "### 0.3 后续动作"
)

VALID_REPORTS=()
INVALID_CHANGED_REPORTS=()

for REL_PATH in "${REPORT_FILES[@]}"; do
    ABS_PATH="$REDCAP_ROOT/$REL_PATH"
    REQUIRE_SUMMARY=0

    for CHANGED in "${CHANGED_REPORTS[@]}"; do
        if [[ "$CHANGED" == "$REL_PATH" ]]; then
            REQUIRE_SUMMARY=1
            break
        fi
    done

    if [[ ! -f "$ABS_PATH" ]]; then
        if [[ "$REQUIRE_SUMMARY" -eq 1 ]]; then
            INVALID_CHANGED_REPORTS+=("$REL_PATH")
            echo "[redcap-task-report-check] changed report missing on disk: $REL_PATH" >&2
        fi
        continue
    fi

    MISSING_SECTION=0
    for REQUIRED in "${REQUIRED_BASE_SECTIONS[@]}"; do
        if ! grep -Fq "$REQUIRED" "$ABS_PATH"; then
            MISSING_SECTION=1
            echo "[redcap-task-report-check] incomplete template: $REL_PATH (missing: $REQUIRED)" >&2
            break
        fi
    done

    if [[ "$MISSING_SECTION" -eq 0 && "$REQUIRE_SUMMARY" -eq 1 ]]; then
        for REQUIRED in "${REQUIRED_SUMMARY_SECTIONS[@]}"; do
            if ! grep -Fq "$REQUIRED" "$ABS_PATH"; then
                MISSING_SECTION=1
                echo "[redcap-task-report-check] incomplete summary template: $REL_PATH (missing: $REQUIRED)" >&2
                break
            fi
        done
    fi

    if [[ "$MISSING_SECTION" -eq 0 ]]; then
        VALID_REPORTS+=("$REL_PATH")
    elif [[ "$REQUIRE_SUMMARY" -eq 1 ]]; then
        INVALID_CHANGED_REPORTS+=("$REL_PATH")
    fi
done

if [[ ${#INVALID_CHANGED_REPORTS[@]} -gt 0 ]]; then
    echo "[redcap-task-report-check] changed reports failed template audit:" >&2
    printf '  - %s\n' "${INVALID_CHANGED_REPORTS[@]}" | sort -u >&2
    exit 1
fi

if [[ ${#VALID_REPORTS[@]} -eq 0 ]]; then
    echo "[redcap-task-report-check] no template-complete task report found" >&2
    exit 1
fi

printf '%s\n' "${VALID_REPORTS[@]}" | sort -u
exit 0

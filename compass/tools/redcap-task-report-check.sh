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

if [[ -z "$CURRENT_HEAD" ]]; then
    CURRENT_HEAD=$(git -C "$REDCAP_ROOT" rev-parse HEAD 2>/dev/null) || exit 1
fi

REPORT_GLOB='compass/docs/task-reports/*.md'
REPORT_MARKER=""

if [[ -n "$HOST" ]]; then
    REPORT_MARKER="/tmp/redcap-layerB-${HOST}-current-report-path"
fi

TMP_REPORT_LIST=$(mktemp)

git -C "$REDCAP_ROOT" --no-pager diff --name-only "$BASELINE..$CURRENT_HEAD" -- "$REPORT_GLOB" 2>/dev/null >> "$TMP_REPORT_LIST" || true

if [[ -n "$REPORT_MARKER" && -f "$REPORT_MARKER" ]]; then
    MARKED_REPORT=$(cat "$REPORT_MARKER" 2>/dev/null)
    if [[ -n "$MARKED_REPORT" ]]; then
        git -C "$REDCAP_ROOT" --no-pager diff --cached --name-only -- "$MARKED_REPORT" 2>/dev/null >> "$TMP_REPORT_LIST" || true
    fi
fi

REPORT_FILES=()
while IFS= read -r REPORT_FILE; do
    if [[ -n "$REPORT_FILE" ]]; then
        REPORT_FILES+=("$REPORT_FILE")
    fi
done < <(sort -u "$TMP_REPORT_LIST" | sed '/^[[:space:]]*$/d')

rm -f "$TMP_REPORT_LIST"

if [[ ${#REPORT_FILES[@]} -eq 0 ]]; then
    echo "[redcap-task-report-check] missing task report under compass/docs/task-reports/" >&2
    exit 1
fi

REQUIRED_SECTIONS=(
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

VALID_REPORTS=()

for REL_PATH in "${REPORT_FILES[@]}"; do
    ABS_PATH="$REDCAP_ROOT/$REL_PATH"

    if [[ ! -f "$ABS_PATH" ]]; then
        continue
    fi

    MISSING_SECTION=0
    for REQUIRED in "${REQUIRED_SECTIONS[@]}"; do
        if ! grep -Fq "$REQUIRED" "$ABS_PATH"; then
            MISSING_SECTION=1
            echo "[redcap-task-report-check] incomplete template: $REL_PATH (missing: $REQUIRED)" >&2
            break
        fi
    done

    if [[ "$MISSING_SECTION" -eq 0 ]]; then
        VALID_REPORTS+=("$REL_PATH")
    fi
done

if [[ ${#VALID_REPORTS[@]} -eq 0 ]]; then
    echo "[redcap-task-report-check] no template-complete task report found" >&2
    exit 1
fi

printf '%s\n' "${VALID_REPORTS[@]}" | sort -u
exit 0

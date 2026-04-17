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
PENDING_CLOSURE_STATE=""
TMP_CHANGED_REPORT_LIST=$(mktemp)
ANCHORED_REPORT=""
ANCHOR_MISMATCH=0
ANCHOR_SOURCE=""

report_anchor_rel_path() {
    local rel_path="${1:-}"

    [[ -n "$rel_path" ]] || return 1
    redcap_interop_resolve_report_rel_path "$REDCAP_ROOT" "$rel_path" 2>/dev/null
}

if [[ -n "${REDCAP_RUNTIME_SESSION_ID:-}" && -n "${REDCAP_RUNTIME_CAPABILITY:-}" ]]; then
    if redcap_runtime_attach_existing "$REDCAP_RUNTIME_SESSION_ID" "$REDCAP_RUNTIME_CAPABILITY"; then
        :
    fi
elif [[ -n "$HOST" ]]; then
    if redcap_runtime_attach_from_process_claim "$HOST" 2>/dev/null; then
        :
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
git -C "$REDCAP_ROOT" --no-pager diff --cached --diff-filter=ACMR --name-only -- "$REPORT_GLOB" 2>/dev/null >> "$TMP_REPORT_LIST" || true
git -C "$REDCAP_ROOT" --no-pager diff --cached --diff-filter=ACMR --name-only -- "$REPORT_GLOB" 2>/dev/null >> "$TMP_CHANGED_REPORT_LIST" || true
git -C "$REDCAP_ROOT" --no-pager diff --diff-filter=ACMR --name-only -- "$REPORT_GLOB" 2>/dev/null >> "$TMP_REPORT_LIST" || true
git -C "$REDCAP_ROOT" --no-pager diff --diff-filter=ACMR --name-only -- "$REPORT_GLOB" 2>/dev/null >> "$TMP_CHANGED_REPORT_LIST" || true
git -C "$REDCAP_ROOT" --no-pager ls-files --others --exclude-standard -- "$REPORT_GLOB" 2>/dev/null >> "$TMP_REPORT_LIST" || true
git -C "$REDCAP_ROOT" --no-pager ls-files --others --exclude-standard -- "$REPORT_GLOB" 2>/dev/null >> "$TMP_CHANGED_REPORT_LIST" || true

MARKED_REPORT=$(redcap_interop_current_report_marker_rel "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" 2>/dev/null || true)
if [[ -n "$MARKED_REPORT" ]]; then
    printf '%s\n' "$MARKED_REPORT" >> "$TMP_REPORT_LIST"
    ANCHORED_REPORT="$MARKED_REPORT"
    ANCHOR_SOURCE="marker"
fi

if [[ -n "$PENDING_CLOSURE_STATE" && -f "$PENDING_CLOSURE_STATE" ]]; then
    PENDING_ARTIFACT_PATH=$(redcap_interop_read_state_field "$PENDING_CLOSURE_STATE" "artifact_path" 2>/dev/null || true)
    PENDING_ARTIFACT_PATH=$(report_anchor_rel_path "$PENDING_ARTIFACT_PATH" || true)
    if [[ -n "$PENDING_ARTIFACT_PATH" ]]; then
        printf '%s\n' "$PENDING_ARTIFACT_PATH" >> "$TMP_REPORT_LIST"
        if [[ -n "$ANCHORED_REPORT" && "$ANCHORED_REPORT" != "$PENDING_ARTIFACT_PATH" ]]; then
            ANCHOR_MISMATCH=1
        elif [[ -z "$ANCHORED_REPORT" ]]; then
            ANCHORED_REPORT="$PENDING_ARTIFACT_PATH"
            ANCHOR_SOURCE="pending"
        fi
    fi
fi

INVALID_CHANGED_REPORTS=()
TMP_CANON_REPORT_LIST=$(mktemp)
TMP_CANON_CHANGED_REPORT_LIST=$(mktemp)

while IFS= read -r REPORT_FILE; do
    local_rel=$(report_anchor_rel_path "$REPORT_FILE" || true)
    if [[ -n "$local_rel" ]]; then
        printf '%s\n' "$local_rel" >> "$TMP_CANON_REPORT_LIST"
    fi
done < <(sort -u "$TMP_REPORT_LIST" | sed '/^[[:space:]]*$/d')

while IFS= read -r REPORT_FILE; do
    local_rel=$(report_anchor_rel_path "$REPORT_FILE" || true)
    if [[ -n "$local_rel" ]]; then
        printf '%s\n' "$local_rel" >> "$TMP_CANON_CHANGED_REPORT_LIST"
    elif [[ -n "$REPORT_FILE" ]]; then
        INVALID_CHANGED_REPORTS+=("$REPORT_FILE")
        echo "[redcap-task-report-check] changed report escapes task-reports root: $REPORT_FILE" >&2
    fi
done < <(sort -u "$TMP_CHANGED_REPORT_LIST" | sed '/^[[:space:]]*$/d')

REPORT_FILES=()
while IFS= read -r REPORT_FILE; do
    if [[ -n "$REPORT_FILE" ]]; then
        REPORT_FILES+=("$REPORT_FILE")
    fi
done < <(sort -u "$TMP_CANON_REPORT_LIST" | sed '/^[[:space:]]*$/d')

CHANGED_REPORTS=()
while IFS= read -r REPORT_FILE; do
    if [[ -n "$REPORT_FILE" ]]; then
        CHANGED_REPORTS+=("$REPORT_FILE")
    fi
done < <(sort -u "$TMP_CANON_CHANGED_REPORT_LIST" | sed '/^[[:space:]]*$/d')

rm -f "$TMP_REPORT_LIST" "$TMP_CHANGED_REPORT_LIST" "$TMP_CANON_REPORT_LIST" "$TMP_CANON_CHANGED_REPORT_LIST"

pending_anchor_is_uniquely_latest_changed_report() {
    local anchor="$1"

    [[ -n "$anchor" && ${#CHANGED_REPORTS[@]} -gt 0 ]] || return 1

    python3 - "$REDCAP_ROOT" "$BASELINE" "$CURRENT_HEAD" "$anchor" "${CHANGED_REPORTS[@]}" <<'PY'
from __future__ import annotations

import subprocess
import sys


def git_lines(root: str, *args: str) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", root, "--no-pager", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


root = sys.argv[1]
baseline = sys.argv[2]
current = sys.argv[3]
anchor = sys.argv[4]
changed = sys.argv[5:]

worktree_changed = set(git_lines(root, "diff", "--name-only"))
worktree_changed.update(git_lines(root, "diff", "--cached", "--name-only"))
worktree_changed.update(git_lines(root, "ls-files", "--others", "--exclude-standard"))

commit_order = git_lines(root, "rev-list", "--reverse", f"{baseline}..{current}")
commit_index = {commit: idx for idx, commit in enumerate(commit_order)}

ranks: dict[str, tuple[int, int]] = {}
for path in changed:
    if path in worktree_changed:
        ranks[path] = (2, 0)
        continue

    commits = git_lines(root, "rev-list", "--reverse", f"{baseline}..{current}", "--", path)
    if commits:
        ranks[path] = (1, commit_index.get(commits[-1], -1))
    else:
        ranks[path] = (0, -1)

anchor_rank = ranks.get(anchor)
if anchor_rank is None:
    print("0")
    raise SystemExit(0)

best_rank = max(ranks.values())
if anchor_rank != best_rank:
    print("0")
    raise SystemExit(0)

is_unique = sum(1 for rank in ranks.values() if rank == best_rank) == 1
print("1" if is_unique else "0")
PY
}

if [[ "$ANCHOR_MISMATCH" -eq 1 ]]; then
    echo "[redcap-task-report-check] report marker and pending closure artifact disagree" >&2
    exit 1
fi

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
    "## 零、先看懂当前局面"
    "### 0.1 当前已完成"
    "### 0.2 上一步完成的是"
    "### 0.3 下一步计划做的是"
    "### 0.4 整体计划脉络图与当前位置"
)

REQUIRED_CHANGED_ONLY_SECTIONS=(
    "### 3.2.1 术语对照（按文件/功能解释）"
)

VALID_REPORTS=()
ANCHOR_IS_CHANGED=0
ANCHOR_IS_UNIQUE_LATEST_CHANGED=0

if [[ -n "$ANCHORED_REPORT" && ${#CHANGED_REPORTS[@]} -gt 0 ]]; then
    for CHANGED in "${CHANGED_REPORTS[@]}"; do
        if [[ "$CHANGED" == "$ANCHORED_REPORT" ]]; then
            ANCHOR_IS_CHANGED=1
            break
        fi
    done
    if [[ "$ANCHOR_IS_CHANGED" -eq 1 ]]; then
        if [[ "$(pending_anchor_is_uniquely_latest_changed_report "$ANCHORED_REPORT")" == "1" ]]; then
            ANCHOR_IS_UNIQUE_LATEST_CHANGED=1
        fi
    fi
fi

for REL_PATH in "${REPORT_FILES[@]}"; do
    ABS_PATH="$REDCAP_ROOT/$REL_PATH"
    REQUIRE_SUMMARY=0

    if [[ ${#CHANGED_REPORTS[@]} -gt 0 ]]; then
        for CHANGED in "${CHANGED_REPORTS[@]}"; do
            if [[ "$CHANGED" == "$REL_PATH" ]]; then
                REQUIRE_SUMMARY=1
                if [[ "$ANCHOR_SOURCE" == "marker" && "$ANCHOR_IS_CHANGED" -eq 1 && "$REL_PATH" != "$ANCHORED_REPORT" ]]; then
                    REQUIRE_SUMMARY=0
                fi
                break
            fi
        done
    fi

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

    if [[ "$MISSING_SECTION" -eq 0 && "$REQUIRE_SUMMARY" -eq 1 ]]; then
        for REQUIRED in "${REQUIRED_CHANGED_ONLY_SECTIONS[@]}"; do
            if ! grep -Fq "$REQUIRED" "$ABS_PATH"; then
                MISSING_SECTION=1
                echo "[redcap-task-report-check] incomplete changed-report template: $REL_PATH (missing: $REQUIRED)" >&2
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

if [[ -n "$ANCHORED_REPORT" ]]; then
    CONFLICTING_CHANGED_REPORTS=()
    if [[ ${#CHANGED_REPORTS[@]} -gt 0 ]]; then
        for CHANGED in "${CHANGED_REPORTS[@]}"; do
            [[ "$CHANGED" == "$ANCHORED_REPORT" ]] && continue
            CONFLICTING_CHANGED_REPORTS+=("$CHANGED")
        done
    fi
    if [[ "$ANCHOR_SOURCE" == "pending" && ${#CONFLICTING_CHANGED_REPORTS[@]} -gt 0 ]]; then
        if [[ "$ANCHOR_IS_UNIQUE_LATEST_CHANGED" -ne 1 ]]; then
            echo "[redcap-task-report-check] stale pending report anchor conflicts with newer changed task reports:" >&2
            printf '  - %s\n' "${CONFLICTING_CHANGED_REPORTS[@]}" | sort -u >&2
            exit 1
        fi
    fi
    if [[ "$ANCHOR_SOURCE" == "marker" && "$ANCHOR_IS_CHANGED" -ne 1 && ${#CONFLICTING_CHANGED_REPORTS[@]} -gt 0 ]]; then
        echo "[redcap-task-report-check] stale marker anchor conflicts with newer changed task reports:" >&2
        printf '  - %s\n' "${CONFLICTING_CHANGED_REPORTS[@]}" | sort -u >&2
        exit 1
    fi
    for VALID in "${VALID_REPORTS[@]}"; do
        if [[ "$VALID" == "$ANCHORED_REPORT" ]]; then
            printf '%s\n' "$ANCHORED_REPORT"
            exit 0
        fi
    done
    echo "[redcap-task-report-check] anchored task report is not template-complete: $ANCHORED_REPORT" >&2
    exit 1
fi

if [[ ${#VALID_REPORTS[@]} -gt 1 ]]; then
    echo "[redcap-task-report-check] multiple valid task reports found without explicit anchor:" >&2
    printf '  - %s\n' "${VALID_REPORTS[@]}" | sort -u >&2
    exit 1
fi

printf '%s\n' "${VALID_REPORTS[0]}"
exit 0

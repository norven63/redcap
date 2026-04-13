#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap on_ALL_DONE 收尾脚本
#
# 将 on_ALL_DONE hook 的 3 个副作用封装为单一脚本，
# 降低 LLM 记忆负担（记 1 个脚本调用 vs 记 3 个步骤细节）。
#
# 用法：
#   bash compass/tools/redcap-on-complete.sh <project_dir> [initial_head] [project_name]
#
# 参数：
#   project_dir   — 项目根目录绝对路径（必须）
#   initial_head  — 本次会话开始时的 HEAD commit（可选，用于 git log）
#   project_name  — 项目名称（可选，飞书通知 --project 参数）
#
# 动作（按序执行，任一失败不阻塞后续）：
#   1. 清除 .workflow/ 临时文件（§5.9）
#   2. 输出最终交付摘要到 stdout
#   3. 飞书通知（§5.11，附带 commit 记录）
# ─────────────────────────────────────────────────────────

set -u  # 未定义变量报错

PROJECT_DIR="${1:?用法: bash compass/tools/redcap-on-complete.sh <project_dir> [initial_head] [project_name]}"
INITIAL_HEAD="${2:-}"
PROJECT_NAME_ARG="${3:-}"
SKIP_FEISHU="${REDCAP_SKIP_FEISHU:-0}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/redcap-runtime-state.sh"
source "$SCRIPT_DIR/redcap-interop-governance.sh"
source "$SCRIPT_DIR/redcap-notify-format.sh"
WORKFLOW_DIR="$PROJECT_DIR/开发手册/.workflow"
PROJECT_NAME=$(redcap_runtime_project_name "$PROJECT_DIR" "$PROJECT_NAME_ARG")
TASK_REPORT_CHECK="$SCRIPT_DIR/redcap-task-report-check.sh"
ARTIFACT_LIFECYCLE_CHECK="$SCRIPT_DIR/redcap-artifact-lifecycle-check.sh"

verify_commit_closure() {
  local current_head worktree_status=""

  current_head=$(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null || true)
  if [[ -z "$current_head" ]]; then
    echo "[on_complete] 无法解析当前 HEAD，拒绝标记完成" >&2
    return 1
  fi

  if [[ -z "$INITIAL_HEAD" ]]; then
    echo "[on_complete] 未提供初始 HEAD，无法证明本轮已有新 commit，拒绝标记完成" >&2
    return 1
  fi

  if ! git -C "$PROJECT_DIR" rev-parse "${INITIAL_HEAD}^{commit}" >/dev/null 2>&1; then
    echo "[on_complete] 初始 HEAD 不可解析：$INITIAL_HEAD" >&2
    return 1
  fi

  worktree_status=$(git -C "$PROJECT_DIR" status --porcelain 2>/dev/null || true)
  if [[ -n "$worktree_status" ]]; then
    echo "[on_complete] worktree 仍有未提交变更，拒绝标记完成" >&2
    return 1
  fi

  if [[ "$current_head" == "$INITIAL_HEAD" ]]; then
    echo "[on_complete] 未检测到本轮新 commit，拒绝标记完成" >&2
    return 1
  fi

  return 0
}

verify_artifact_lifecycle() {
  local current_head

  if [[ "$PROJECT_DIR" != "$REDCAP_ROOT" ]]; then
    return 0
  fi

  current_head=$(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null || true)
  if [[ -z "$current_head" ]]; then
    echo "[on_complete] 无法解析当前 HEAD，拒绝执行 artifact lifecycle 校验" >&2
    return 1
  fi

  if [[ ! -x "$ARTIFACT_LIFECYCLE_CHECK" ]]; then
    echo "[on_complete] artifact lifecycle 检查脚本不存在，拒绝标记完成" >&2
    return 1
  fi

  if ! bash "$ARTIFACT_LIFECYCLE_CHECK" "$PROJECT_DIR" "$INITIAL_HEAD" "$current_head" redcap-self; then
    echo "[on_complete] artifact lifecycle 检查失败，拒绝标记完成" >&2
    return 1
  fi

  return 0
}

self_dev_closure_enabled() {
  [[ "$PROJECT_DIR" == "$REDCAP_ROOT" && -f "$PROJECT_DIR/.dev-task.md" ]]
}

current_project_head() {
  git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null || true
}

record_closure_phase() {
  local phase="$1"
  local status="$2"
  local detail="${3:-}"
  local artifact_path="${4:-}"
  local current_head

  if ! self_dev_closure_enabled; then
    return 0
  fi

  current_head=$(current_project_head)
  if ! redcap_interop_append_closure_ledger \
    "$PROJECT_DIR" \
    "$PROJECT_DIR/.dev-task.md" \
    "$phase" \
    "$status" \
    "$detail" \
    "redcap" \
    "on-complete" \
    "$INITIAL_HEAD" \
    "$current_head" \
    "$artifact_path" \
    >/dev/null 2>&1; then
    echo "[on_complete] failed to append closure ledger (phase=$phase status=$status)" >&2
    return 1
  fi

  return 0
}

write_pending_closure_redline() {
  local redlines="$1"
  local detail="${2:-}"
  local artifact_path="${3:-}"
  local current_head

  if ! self_dev_closure_enabled; then
    return 0
  fi

  current_head=$(current_project_head)
  if ! redcap_interop_write_pending_closure \
    "$PROJECT_DIR" \
    "$PROJECT_DIR/.dev-task.md" \
    "redcap" \
    "on-complete" \
    "$redlines" \
    "$detail" \
    "$artifact_path" \
    "$INITIAL_HEAD" \
    "$current_head" \
    >/dev/null 2>&1; then
    echo "[on_complete] failed to persist pending closure redline: $redlines" >&2
    return 1
  fi

  return 0
}

persist_failure_evidence() {
  local phase="$1"
  local redlines="$2"
  local detail="${3:-}"
  local artifact_path="${4:-}"
  local persist_status=0

  record_closure_phase "$phase" "fail" "$detail" "$artifact_path" || persist_status=1
  if [[ -n "$redlines" ]]; then
    write_pending_closure_redline "$redlines" "$detail" "$artifact_path" || persist_status=1
  fi

  return "$persist_status"
}

record_evidence_system_failure() {
  local phase="$1"
  local detail="${2:-}"

  redcap_runtime_record_degraded_mode \
    "$PROJECT_DIR" \
    "closure-evidence-write-failure" \
    "phase=$phase detail=$detail" \
    >/dev/null 2>&1 || true
  echo "[on_complete] FATAL: cannot persist closure evidence for $phase" >&2
}

verify_task_report_closure() {
  local current_head report_output=""

  if ! self_dev_closure_enabled; then
    return 0
  fi

  current_head=$(current_project_head)
  if [[ -z "$current_head" ]]; then
    echo "[on_complete] 无法解析当前 HEAD，拒绝执行 task report 校验" >&2
    return 1
  fi

  if [[ ! -x "$TASK_REPORT_CHECK" ]]; then
    echo "[on_complete] task report 检查脚本不存在，拒绝标记完成" >&2
    return 1
  fi

  if ! report_output=$("$TASK_REPORT_CHECK" "$PROJECT_DIR" "$INITIAL_HEAD" "$current_head" 2>&1); then
    echo "$report_output" >&2
    echo "[on_complete] task report 审计失败，拒绝标记完成" >&2
    return 1
  fi

  return 0
}

# ── 动作 1: 清除 .workflow/ 临时文件（§5.9） ──────────────

cleanup_workflow() {
  if [[ ! -d "$WORKFLOW_DIR" ]]; then
    echo "[on_complete] .workflow/ 不存在，跳过清理"
    return 0
  fi

  echo "[on_complete] 清理 .workflow/ 临时文件..."

  # 删除 prompt 文件和运行脚本
  find "$WORKFLOW_DIR" -maxdepth 1 \( \
    -name '*-prompt-*.md' -o \
    -name '*-prompt-*.txt' -o \
    -name '*-system-prompt.txt' -o \
    -name 'run-*.sh' \
  \) -delete 2>/dev/null || true

  # 清除项目根目录的错位文件
  rm -f "$PROJECT_DIR/last-result.json" 2>/dev/null || true
  rm -rf "$PROJECT_DIR/__redcap_status" 2>/dev/null || true

  # 清除 Shell 特殊字符命名的异常目录/文件
  find "$PROJECT_DIR" -maxdepth 1 -name '[><|]' -exec rm -rf {} + 2>/dev/null || true

  echo "[on_complete] 清理完成"
}

# ── 动作 2: 输出最终交付摘要 ─────────────────────────────

output_summary() {
  local report_ref message
  report_ref=$(resolve_report_reference)
  message="$(redcap_build_completion_message \
    "RedCap Layer B 收尾完成" \
    "$PROJECT_NAME" \
    "$(current_commit_log)" \
    "on_ALL_DONE 主路径收尾" \
    "$report_ref" \
    "$PROJECT_DIR")"

  echo ""
  echo "═══════════════════════════════════════════"
  echo "  RedCap 流程完成"
  echo "═══════════════════════════════════════════"
  printf '%s\n' "$message"
  echo "═══════════════════════════════════════════"
  echo ""
}

current_commit_log() {
  if [[ -n "$INITIAL_HEAD" ]]; then
    git -C "$PROJECT_DIR" --no-pager log --oneline "$INITIAL_HEAD..HEAD" 2>/dev/null || echo "(无法获取)"
  else
    echo "(无法获取)"
  fi
}

resolve_report_reference() {
  local current_head

  if [[ ! -f "$TASK_REPORT_CHECK" || ! -f "$PROJECT_DIR/.dev-task.md" || -z "$INITIAL_HEAD" ]]; then
    return 0
  fi

  current_head=$(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null || true)
  if [[ -z "$current_head" ]]; then
    return 0
  fi

  "$TASK_REPORT_CHECK" "$PROJECT_DIR" "$INITIAL_HEAD" "$current_head" 2>/dev/null | awk 'NF {print; exit}'
}

# ── 动作 3: 飞书通知（§5.11） ────────────────────────────

feishu_notify() {
  local notifier="$SCRIPT_DIR/feishu-notifier.py"
  local message report_ref

  if [[ "$SKIP_FEISHU" == "1" ]]; then
    echo "[on_complete] REDCAP_SKIP_FEISHU=1，跳过飞书通知"
    return 0
  fi

  if [[ ! -f "$notifier" ]]; then
    echo "[on_complete] feishu-notifier.py 不存在，无法完成飞书通知" >&2
    return 1
  fi

  local commit_log=""
  commit_log=$(current_commit_log)
  report_ref=$(resolve_report_reference)

  message="$(redcap_build_completion_message \
    "RedCap Layer B 收尾完成" \
    "$PROJECT_NAME" \
    "$commit_log" \
    "on_ALL_DONE 主路径收尾" \
    "$report_ref" \
    "$PROJECT_DIR")"

  echo "[on_complete] 发送飞书通知..."
  python3 "$notifier" notify "$message" --project "$PROJECT_NAME" 2>/dev/null || {
    echo "[on_complete] ⚠ 飞书通知失败（可能未配置 feishu-config.json）" >&2
    return 1
  }
}

# ── 执行 ─────────────────────────────────────────────────

echo "[on_complete] 开始执行 on_ALL_DONE 收尾动作..."
record_closure_phase "on-complete" "started" "project=$PROJECT_NAME" || exit 1

if ! verify_commit_closure; then
  if ! record_closure_phase "commit-proof" "fail" "commit proof unmet"; then
    record_evidence_system_failure "commit-proof" "commit proof unmet"
    exit 2
  fi
  echo "[on_complete] ⚠ commit proof 未满足，保留重试机会" >&2
  exit 1
fi
record_closure_phase "commit-proof" "pass" "commit proof verified" || exit 1

if ! verify_task_report_closure; then
  if ! persist_failure_evidence "task-report" "task-report" "task-report-check failed during on-complete" "$(resolve_report_reference)"; then
    record_evidence_system_failure "task-report" "task-report-check failed during on-complete"
    exit 2
  fi
  echo "[on_complete] ⚠ task report proof 未满足，保留重试机会" >&2
  exit 1
fi
record_closure_phase "task-report" "pass" "task report audit passed" "$(resolve_report_reference)" || exit 1

if ! verify_artifact_lifecycle; then
  if ! persist_failure_evidence "artifact-lifecycle" "artifact-lifecycle" "artifact-lifecycle-check failed during on-complete"; then
    record_evidence_system_failure "artifact-lifecycle" "artifact-lifecycle-check failed during on-complete"
    exit 2
  fi
  echo "[on_complete] ⚠ artifact lifecycle proof 未满足，保留重试机会" >&2
  exit 1
fi
record_closure_phase "artifact-lifecycle" "pass" "artifact lifecycle audit passed" || exit 1

ON_COMPLETE_STATUS=0

cleanup_workflow  || {
  echo "[on_complete] ⚠ 清理步骤出错，继续执行" >&2
  ON_COMPLETE_STATUS=1
}
output_summary    || echo "[on_complete] ⚠ 摘要输出出错，继续执行" >&2
feishu_notify     || {
  if ! persist_failure_evidence "notify" "notify" "feishu notify failed during on-complete" "$(resolve_report_reference)"; then
    record_evidence_system_failure "notify" "feishu notify failed during on-complete"
    ON_COMPLETE_STATUS=2
  else
    ON_COMPLETE_STATUS=1
  fi
  echo "[on_complete] ⚠ 飞书通知未完成，保留重试机会" >&2
}

if [[ "$ON_COMPLETE_STATUS" -eq 0 ]]; then
  record_closure_phase "notify" "pass" "on-complete notify succeeded" "$(resolve_report_reference)" || {
    record_evidence_system_failure "notify-pass" "on-complete notify succeeded but pass evidence failed"
    ON_COMPLETE_STATUS=2
  }
  record_closure_phase "on-complete" "pass" "closure main path finished" "$(resolve_report_reference)" || {
    record_evidence_system_failure "on-complete-pass" "closure main path finished but pass evidence failed"
    ON_COMPLETE_STATUS=2
  }
else
  record_closure_phase "on-complete" "incomplete" "main path ended with retry-needed status" "$(resolve_report_reference)" || {
    record_evidence_system_failure "on-complete-incomplete" "retry-needed status but incomplete evidence failed"
    ON_COMPLETE_STATUS=2
  }
fi

echo "[on_complete] on_ALL_DONE 收尾动作全部完成"
exit "$ON_COMPLETE_STATUS"

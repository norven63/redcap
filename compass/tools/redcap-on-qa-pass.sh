#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap on_QA_PASS 提交脚本
#
# 将 on_QA_PASS hook 的副作用封装为单一脚本，
# 降低 LLM 记忆负担（记 1 个脚本调用 vs 记 commit 格式细节）。
#
# 用法：
#   bash compass/tools/redcap-on-qa-pass.sh <project_dir> <commit_type> <commit_scope> <commit_message> [commit_body]
#
# 参数：
#   project_dir     — 项目根目录绝对路径（必须）
#   commit_type     — Commit 类型：feat/fix/refactor/docs/test/chore/style（必须）
#   commit_scope    — Commit 范围（必须）
#   commit_message  — Commit 简要描述，≤72 字符（必须）
#   commit_body     — Commit 正文，说明动机（可选）
#
# 动作（按序执行）：
#   0. state.yaml 一致性校验；若发现不一致则阻断 on_QA_PASS
#   1. git add -A && git commit（按 references/commit-standards.md 格式）
#   2. 检查 lesson 字段 → 提示 Dispatcher 写入经验（§5.8）
#
# 退出码：
#   0 — 成功
#   1 — 参数错误
#   2 — git 操作失败（已输出警告，不阻塞）
#   3 — state.yaml 一致性校验未通过，阻断 on_QA_PASS
# ─────────────────────────────────────────────────────────

set -u

PROJECT_DIR="${1:?用法: bash compass/tools/redcap-on-qa-pass.sh <project_dir> <type> <scope> <message> [body]}"
COMMIT_TYPE="${2:?缺少 commit_type 参数（feat/fix/refactor/docs/test/chore/style）}"
COMMIT_SCOPE="${3:?缺少 commit_scope 参数}"
COMMIT_MESSAGE="${4:?缺少 commit_message 参数}"
COMMIT_BODY="${5:-}"
AUTHOR_MARKER="作者:redcap"

# ── 校验 commit_type ─────────────────────────────────────

VALID_TYPES="feat fix refactor docs test chore style"
if ! echo "$VALID_TYPES" | grep -qw "$COMMIT_TYPE"; then
  echo "[on_qa_pass] ⚠ 无效的 commit_type: $COMMIT_TYPE（允许: $VALID_TYPES）"
  exit 1
fi

# ── 校验 subject line 长度 ───────────────────────────────

SUBJECT_LINE="$COMMIT_TYPE($COMMIT_SCOPE): $COMMIT_MESSAGE"
if [[ ${#SUBJECT_LINE} -gt 72 ]]; then
  echo "[on_qa_pass] ⚠ subject line 超过 72 字符（${#SUBJECT_LINE} 字符）: $SUBJECT_LINE"
  echo "[on_qa_pass] 继续执行，但建议缩短描述"
fi

compose_commit_body() {
  local body="$COMMIT_BODY"

  if [[ -z "$body" ]]; then
    body="原因：沉淀当前步骤已通过 QA 的结果，保持代码、状态机与交付节奏一致。"
  fi

  if [[ "$body" != *"$AUTHOR_MARKER"* ]]; then
    body="${body}"$'\n\n'"$AUTHOR_MARKER"
  fi

  printf '%s' "$body"
}

# ── 动作 1: git add -A && git commit ─────────────────────

git_commit() {
  echo "[on_qa_pass] 执行 git commit..."

  cd "$PROJECT_DIR" || {
    echo "[on_qa_pass] ⚠ 无法进入项目目录: $PROJECT_DIR"
    return 2
  }

  # 检查是否有变更
  if git diff --quiet HEAD 2>/dev/null && git diff --cached --quiet 2>/dev/null; then
    # 检查是否有 untracked 文件
    if [[ -z "$(git ls-files --others --exclude-standard)" ]]; then
      echo "[on_qa_pass] 无变更需要提交，跳过"
      return 0
    fi
  fi

  git add -A || {
    echo "[on_qa_pass] ⚠ git add 失败"
    return 2
  }

  local full_body
  full_body="$(compose_commit_body)"
  git commit -m "$SUBJECT_LINE" -m "$full_body" || {
    echo "[on_qa_pass] ⚠ git commit 失败"
    return 2
  }

  echo "[on_qa_pass] ✓ 已提交: $SUBJECT_LINE"
}

# ── 动作 2: 检查 lesson（提示 Dispatcher） ───────────────

check_lesson() {
  local last_result="$PROJECT_DIR/.workflow/last-result.json"

  if [[ ! -f "$last_result" ]]; then
    return 0
  fi

  # 检查 last-result.json 中是否有 lesson 字段
  if command -v python3 &>/dev/null; then
    local has_lesson
    has_lesson=$(python3 -c "
import json, sys
try:
    data = json.load(open('$last_result'))
    lesson = data.get('lesson', '')
    if lesson and lesson.strip():
        print(lesson.strip())
except:
    pass
" 2>/dev/null)

    if [[ -n "$has_lesson" ]]; then
      echo ""
      echo "[on_qa_pass] ⚠ 检测到 lesson 需要归档:"
      echo "  $has_lesson"
      echo "[on_qa_pass] → Dispatcher 应执行 §5.8 经验沉淀流程"
      echo ""
    fi
  fi
}

# ── 执行 ─────────────────────────────────────────────────

echo "[on_qa_pass] 开始执行 on_QA_PASS 动作..."

# 动作 0: state.yaml 一致性校验（L-19 防护）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEV_MANUAL="$PROJECT_DIR/开发手册"
if [[ -d "$DEV_MANUAL" ]]; then
  state_check_output="$(bash "$SCRIPT_DIR/redcap-check-state.sh" "$DEV_MANUAL" 2>&1)"
  state_check_status=$?
  if [[ -n "$state_check_output" ]]; then
    printf '%s\n' "$state_check_output"
  fi
  if [[ "$state_check_status" -eq 2 ]]; then
    echo "[on_qa_pass] ❌ state.yaml 一致性校验未通过，阻断 on_QA_PASS"
    exit 3
  fi
  if [[ "$state_check_status" -ne 0 ]]; then
    echo "[on_qa_pass] ❌ state.yaml 一致性校验脚本执行失败（exit=$state_check_status），阻断 on_QA_PASS"
    exit "$state_check_status"
  fi
fi

git_commit   || echo "[on_qa_pass] ⚠ git 操作出错，继续执行"
check_lesson || echo "[on_qa_pass] ⚠ lesson 检查出错，继续执行"

echo "[on_qa_pass] on_QA_PASS 动作完成"

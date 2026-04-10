#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap on_ALL_DONE 收尾脚本
#
# 将 on_ALL_DONE hook 的 3 个副作用封装为单一脚本，
# 降低 LLM 记忆负担（记 1 个脚本调用 vs 记 3 个步骤细节）。
#
# 用法：
#   bash tools/redcap-on-complete.sh <project_dir> [initial_head] [project_name]
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

PROJECT_DIR="${1:?用法: bash tools/redcap-on-complete.sh <project_dir> [initial_head] [project_name]}"
INITIAL_HEAD="${2:-}"
PROJECT_NAME="${3:-$(basename "$PROJECT_DIR")}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKFLOW_DIR="$PROJECT_DIR/开发手册/.workflow"

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
  echo ""
  echo "═══════════════════════════════════════════"
  echo "  RedCap 流程完成"
  echo "═══════════════════════════════════════════"

  if [[ -n "$INITIAL_HEAD" ]]; then
    local commit_count
    commit_count=$(git -C "$PROJECT_DIR" rev-list --count "$INITIAL_HEAD..HEAD" 2>/dev/null || echo "0")
    echo "  项目: $PROJECT_NAME"
    echo "  本次 commit 数: $commit_count"
    echo ""
    echo "  Commits:"
    git -C "$PROJECT_DIR" --no-pager log --oneline "$INITIAL_HEAD..HEAD" 2>/dev/null || echo "  (无法获取 commit 记录)"
  else
    echo "  项目: $PROJECT_NAME"
    echo "  (未提供初始 HEAD，无法展示增量 commits)"
  fi

  echo "═══════════════════════════════════════════"
  echo ""
}

# ── 动作 3: 飞书通知（§5.11） ────────────────────────────

feishu_notify() {
  local notifier="$SCRIPT_DIR/feishu-notifier.py"

  if [[ ! -f "$notifier" ]]; then
    echo "[on_complete] feishu-notifier.py 不存在，跳过飞书通知"
    return 0
  fi

  local commit_log=""
  if [[ -n "$INITIAL_HEAD" ]]; then
    commit_log=$(git -C "$PROJECT_DIR" --no-pager log --oneline "$INITIAL_HEAD..HEAD" 2>/dev/null || echo "(无法获取)")
  fi

  local message="RedCap 流程完成: $PROJECT_NAME"
  if [[ -n "$commit_log" ]]; then
    message="$message\n\nCommits:\n$commit_log"
  fi

  echo "[on_complete] 发送飞书通知..."
  python3 "$notifier" notify "$message" --project "$PROJECT_NAME" 2>/dev/null || {
    echo "[on_complete] ⚠ 飞书通知失败（可能未配置 feishu-config.json），不阻塞流程"
  }
}

# ── 执行 ─────────────────────────────────────────────────

echo "[on_complete] 开始执行 on_ALL_DONE 收尾动作..."

cleanup_workflow  || echo "[on_complete] ⚠ 清理步骤出错，继续执行"
output_summary    || echo "[on_complete] ⚠ 摘要输出出错，继续执行"
feishu_notify     || echo "[on_complete] ⚠ 飞书通知出错，继续执行"

echo "[on_complete] on_ALL_DONE 收尾动作全部完成"

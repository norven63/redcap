#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap Layer A — Review 兜底脚本
#
# 由 redcap-layerA-stop.sh 在检测到 ALL_DONE 但缺少 REVIEW_PASS
# 历史记录时调用。拉起新 Agent 执行项目级 Code Review。
#
# 参数：
#   $1 — 项目目录（CWD）
#   $2 — 项目名称
#
# 设计原理：
#   状态机驱动的 REVIEW_WORKING 节点受 LLM attention 衰减影响
#   （长对话 20+ 轮遵从率降至 70-80%），可能被跳过直接进入 ALL_DONE。
#   本脚本作为 Layer 0 兜底：Hook 100% 触发 + 新 Agent 100% 认知能力。
# ─────────────────────────────────────────────────────────

set -u

PROJECT_DIR="${1:?用法: $0 <项目目录> <项目名称>}"
PROJECT_NAME="${2:?用法: $0 <项目目录> <项目名称>}"

# ── 收集 Review 上下文 ───────────────────────────────────

REQUIREMENT_FILE="$PROJECT_DIR/开发手册/pm/需求文档.md"
ARCH_FILE="$PROJECT_DIR/开发手册/architect/技术框架设计.md"
PROGRESS_FILE="$PROJECT_DIR/开发手册/shared/开发进度日志.md"
LESSONS_FILE="$PROJECT_DIR/开发手册/shared/lessons-learned.md"

# 收集项目源代码文件列表（排除开发手册、node_modules、.git 等）
CODE_TREE=$(cd "$PROJECT_DIR" && find . -type f \
    -not -path './开发手册/*' \
    -not -path './.git/*' \
    -not -path './node_modules/*' \
    -not -path './.next/*' \
    -not -path './dist/*' \
    -not -path './build/*' \
    -not -path './__pycache__/*' \
    -not -path './.venv/*' \
    2>/dev/null | head -200)

# 收集 git diff（最近 commit 的变更）
GIT_DIFF=$(cd "$PROJECT_DIR" && git diff HEAD~5..HEAD --stat 2>/dev/null | head -50)

# 读取关键文档（截断防止 prompt 过长）
REQ_CONTENT=""
if [[ -f "$REQUIREMENT_FILE" ]]; then
    REQ_CONTENT=$(head -200 "$REQUIREMENT_FILE")
fi

ARCH_CONTENT=""
if [[ -f "$ARCH_FILE" ]]; then
    ARCH_CONTENT=$(head -200 "$ARCH_FILE")
fi

# ── 构造 Review Prompt ───────────────────────────────────

REVIEW_PROMPT="你是一个独立的项目级 Code Reviewer。这是一个 **兜底 Review**——正常流程中的 Review 步骤可能被跳过了。

## 项目：${PROJECT_NAME}

## 审查维度（按优先级）

1. **安全合规（P0）**：密钥泄露、SQL注入、XSS、CSRF、.gitignore 完备性
2. **架构一致性（P0）**：实际代码是否符合架构设计文档
3. **需求覆盖率（P1）**：对照需求文档逐项检查功能是否遗漏
4. **代码质量（P1）**：命名一致性、重复代码、错误处理统一性
5. **性能模式（P2）**：N+1查询、分页/流式、缓存策略
6. **可维护性（P2）**：README准确性、API文档一致性、废弃代码

## 需求文档
\`\`\`
${REQ_CONTENT:-（未找到需求文档）}
\`\`\`

## 架构设计
\`\`\`
${ARCH_CONTENT:-（未找到架构设计文档）}
\`\`\`

## 项目文件结构
\`\`\`
${CODE_TREE:-（无法获取）}
\`\`\`

## 最近变更统计
\`\`\`
${GIT_DIFF:-（无 git 变更记录）}
\`\`\`

## 输出要求

请直接审查项目目录 ${PROJECT_DIR} 中的代码文件，输出：

1. **问题清单**（表格：编号 | 问题描述 | 优先级P0/P1/P2 | 涉及文件 | 修复建议）
2. **结论**：PASS（无P0问题）或 FAIL（含P0问题）
3. 最后一行必须输出：\`REVIEW_RESULT: PASS\` 或 \`REVIEW_RESULT: FAIL\`"

# ── 拉起新 Agent 执行 Review ─────────────────────────────

RESULT_FILE="/tmp/redcap-layerA-review-fallback-result"
LOG_FILE="/tmp/redcap-layerA-review-fallback-log.md"

rm -f "$RESULT_FILE" "$LOG_FILE"

REVIEW_OUTPUT=""

# 优先使用 kimi（轻量），其次 claude
if command -v kimi &>/dev/null; then
    REVIEW_OUTPUT=$(echo "$REVIEW_PROMPT" | kimi -p 2>/dev/null) || true
elif command -v claude &>/dev/null; then
    REVIEW_OUTPUT=$(echo "$REVIEW_PROMPT" | claude -p --permission-mode bypassPermissions 2>/dev/null) || true
else
    echo "[redcap-layerA-review-fallback] WARN: 无可用 Agent CLI (kimi/claude)，跳过兜底 Review" >&2
    exit 0
fi

# 保存 Review 日志
echo "$REVIEW_OUTPUT" > "$LOG_FILE"

# ── 解析结果 ─────────────────────────────────────────────

if echo "$REVIEW_OUTPUT" | grep -q "REVIEW_RESULT: FAIL"; then
    echo "FAIL" > "$RESULT_FILE"
    echo "[redcap-layerA-review-fallback] Review FAIL — 发现 P0 问题，详见 $LOG_FILE" >&2

    # 飞书告警（如果 feishu-notifier 可用）
    SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")" && pwd)"
    REDCAP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
    NOTIFIER="$REDCAP_DIR/tools/feishu-notifier.py"
    if [[ -f "$NOTIFIER" ]]; then
        python3 "$NOTIFIER" notify "⚠️ RedCap Layer A Review 兜底 FAIL\n项目: ${PROJECT_NAME}\n\n兜底 Review 发现 P0 问题，正常 Review 步骤可能被跳过。\n详见: ${LOG_FILE}" --project "$PROJECT_NAME" 2>/dev/null || true
    fi
elif echo "$REVIEW_OUTPUT" | grep -q "REVIEW_RESULT: PASS"; then
    echo "PASS" > "$RESULT_FILE"
    echo "[redcap-layerA-review-fallback] Review PASS" >&2
else
    echo "INCONCLUSIVE" > "$RESULT_FILE"
    echo "[redcap-layerA-review-fallback] WARN: 无法解析 Review 结果，详见 $LOG_FILE" >&2
fi

exit 0

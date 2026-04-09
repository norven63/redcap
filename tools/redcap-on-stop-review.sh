#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap 框架 — Stop Hook 独立架构评审
#
# Layer B（开发 RedCap 自身）的 Layer 0 防线。
# 在开发 Agent 退出时，拉起一个全新的、无历史包袱的 Agent
# 对本次变更进行独立的架构/规范 Diff 审查。
#
# 设计原理：
#   - 开发 Agent 在长对话末期注意力衰减，可能遗漏规范
#   - 独立 Agent 拥有 100% 注意力 + 零上下文污染
#   - 物理 Hook 触发 = Layer 0 保障，不依赖 LLM 自觉性
#
# Claude Code Stop hook 协议：
#   stdin — JSON（必须消费）
#   退出码 — 0=通过, 非0=有问题（Claude Code 不阻塞，但会写标记文件 + 飞书告警）
#
# 依赖：kimi CLI 或 claude CLI（至少一个）
# ─────────────────────────────────────────────────────────

set -u

cat > /dev/null  # 消费 stdin

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HEAD_FILE="/tmp/redcap-claude-initial-head"
REVIEW_RESULT_FILE="/tmp/redcap-stop-review-result"
REVIEW_LOG_FILE="/tmp/redcap-stop-review-log.md"

# ── 前置检查：有无新变更 ──

BASELINE=""
if [[ -f "$HEAD_FILE" ]]; then
    BASELINE=$(cat "$HEAD_FILE")
else
    exit 0
fi

CURRENT_HEAD=$(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null) || exit 0

# ── E2E Session Gate 检查 ──
# 如果 e2e-session.yaml 存在，说明有未完成的 E2E 后置处理
# 无论是否有 git 变更，都必须执行 postcheck

E2E_SESSION_FILE="$PROJECT_DIR/test-reports/e2e-session.yaml"
if [[ -f "$E2E_SESSION_FILE" ]]; then
    echo "[redcap-on-stop-review] ⚠ 检测到未完成的 E2E session，执行后置完整性审计..." >&2
    POSTCHECK_SCRIPT="$PROJECT_DIR/tools/redcap-e2e-postcheck.sh"
    if [[ -x "$POSTCHECK_SCRIPT" ]]; then
        bash "$POSTCHECK_SCRIPT" >&2
        POSTCHECK_EXIT=$?
        if [[ $POSTCHECK_EXIT -ne 0 ]]; then
            NOTIFIER_E2E="$PROJECT_DIR/tools/feishu-notifier.py"
            if [[ -f "$NOTIFIER_E2E" ]]; then
                python3 "$NOTIFIER_E2E" notify \
                    "⚠️ RedCap E2E 后置处理未完成！\ntest-reports/e2e-session.yaml 仍存在，请补齐后置处理步骤。" \
                    --project "redcap" 2>/dev/null || true
            fi
        fi
    else
        echo "[redcap-on-stop-review] WARNING: redcap-e2e-postcheck.sh 不可执行" >&2
    fi
fi

if [[ "$BASELINE" == "$CURRENT_HEAD" ]]; then
    # 无变更，无需评审
    rm -f "$REVIEW_RESULT_FILE" "$REVIEW_LOG_FILE" 2>/dev/null
    exit 0
fi

# ── 提取 Diff ──

DIFF=$(git -C "$PROJECT_DIR" --no-pager diff "$BASELINE..HEAD" 2>/dev/null)
COMMIT_LOG=$(git -C "$PROJECT_DIR" --no-pager log --oneline "$BASELINE..HEAD" 2>/dev/null)
FILE_LIST=$(git -C "$PROJECT_DIR" --no-pager diff --name-only "$BASELINE..HEAD" 2>/dev/null)

if [[ -z "$DIFF" ]]; then
    exit 0
fi

# ── 截断 Diff（防止超出 Agent 上下文）──

MAX_DIFF_CHARS=20000
if [[ ${#DIFF} -gt $MAX_DIFF_CHARS ]]; then
    DIFF="${DIFF:0:$MAX_DIFF_CHARS}

... [Diff 截断，共 ${#DIFF} 字符，仅显示前 $MAX_DIFF_CHARS 字符]"
fi

# ── 读取 CONTRIBUTING.md 作为评审基准 ──

CONTRIBUTING=""
if [[ -f "$PROJECT_DIR/CONTRIBUTING.md" ]]; then
    CONTRIBUTING=$(cat "$PROJECT_DIR/CONTRIBUTING.md")
fi

# ── 组装评审 Prompt ──

REVIEW_PROMPT="你是一位独立的代码架构评审员。你与开发者无关，你的唯一任务是客观审查以下变更。

## 评审基准

$CONTRIBUTING

## 本次变更摘要

Commits:
$COMMIT_LOG

变更文件:
$FILE_LIST

## Diff 内容

\`\`\`diff
$DIFF
\`\`\`

## 评审要求

请严格对照以下维度逐一检查：

1. **Commit 规范**：是否符合中文 Conventional Commit 格式（type(scope): 描述）？
2. **经验回顾**：变更是否涉及 lessons.md 中的已知陷阱（如 L-4 路由深度、L-7 headless 挂起、L-8 先测再改）？是否有遗漏的检查？
3. **文件联动**：对照 CONTRIBUTING.md §5 影响范围表，本次变更涉及的文件是否有需要同步更新但遗漏的文件？
4. **内容质量**：
   - 文档变更：是否有 Markdown 格式错误（代码块未闭合、标题层级混乱、链接断裂）？
   - 代码变更：是否有安全问题、硬编码、路径错误？
5. **经验沉淀**：本次变更是否发现了新的失败模式或验证了错误假设，但未归档为 Lesson？
6. **E2E 完整性**：如果变更涉及 E2E 验证，检查 test-reports/e2e-session.yaml 是否已处理、报告是否写入 test-reports/latest-e2e-report.md（而非其他路径）、pending-validations 是否已消费。

## 输出格式

严格按以下 JSON 输出，不要输出其他内容：

\`\`\`json
{
  \"result\": \"PASS\" 或 \"FAIL\",
  \"issues\": [
    {
      \"severity\": \"P0\" 或 \"P1\" 或 \"P2\",
      \"dimension\": \"维度名\",
      \"description\": \"问题描述\",
      \"suggestion\": \"修复建议\"
    }
  ],
  \"summary\": \"一句话总结\"
}
\`\`\`

规则：有任何 P0 问题 → result=FAIL；仅有 P1/P2 → result=PASS（附建议）。"

# ── 选择 Agent CLI ──

AGENT_CMD=""
if command -v kimi &>/dev/null; then
    AGENT_CMD="kimi"
elif command -v claude &>/dev/null; then
    AGENT_CMD="claude"
else
    # 无可用 Agent CLI，记录警告后退出
    echo "[redcap-on-stop-review] WARNING: 无可用 Agent CLI (kimi/claude)，跳过独立评审" >&2
    exit 0
fi

# ── 执行独立评审 ──

REVIEW_OUTPUT=""
if [[ "$AGENT_CMD" == "kimi" ]]; then
    REVIEW_OUTPUT=$(echo "$REVIEW_PROMPT" | kimi -p -y 2>/dev/null) || true
elif [[ "$AGENT_CMD" == "claude" ]]; then
    REVIEW_OUTPUT=$(echo "$REVIEW_PROMPT" | claude -p --output-format text 2>/dev/null) || true
fi

if [[ -z "$REVIEW_OUTPUT" ]]; then
    echo "[redcap-on-stop-review] WARNING: Agent 评审无输出" >&2
    exit 0
fi

# ── 保存评审日志 ──

cat > "$REVIEW_LOG_FILE" << LOGEOF
# RedCap Stop Hook 独立评审报告

- **时间**: $(date '+%Y-%m-%d %H:%M:%S')
- **评审 Agent**: $AGENT_CMD
- **基准 commit**: $BASELINE
- **当前 HEAD**: $CURRENT_HEAD
- **Commits**: $COMMIT_LOG

## 评审输出

$REVIEW_OUTPUT
LOGEOF

# ── 解析结果 ──

# 提取 JSON 中的 result 字段
RESULT=$(echo "$REVIEW_OUTPUT" | python3 -c "
import sys, json, re
text = sys.stdin.read()
# 尝试从 markdown code block 中提取 JSON
m = re.search(r'\`\`\`json?\s*\n(.*?)\n\`\`\`', text, re.DOTALL)
if m:
    text = m.group(1)
# 尝试直接解析
try:
    data = json.loads(text.strip())
    print(data.get('result', 'UNKNOWN'))
except:
    # 尝试从文本中找 PASS/FAIL
    if 'FAIL' in text.upper():
        print('FAIL')
    elif 'PASS' in text.upper():
        print('PASS')
    else:
        print('UNKNOWN')
" 2>/dev/null || echo "UNKNOWN")

echo "$RESULT" > "$REVIEW_RESULT_FILE"

# ── 结果处理 ──

NOTIFIER="$PROJECT_DIR/tools/feishu-notifier.py"

if [[ "$RESULT" == "FAIL" ]]; then
    echo "[redcap-on-stop-review] ⚠ 独立评审发现 P0 问题！详情: $REVIEW_LOG_FILE" >&2

    # 飞书告警
    if [[ -f "$NOTIFIER" ]]; then
        SUMMARY=$(echo "$REVIEW_OUTPUT" | python3 -c "
import sys, json, re
text = sys.stdin.read()
m = re.search(r'\`\`\`json?\s*\n(.*?)\n\`\`\`', text, re.DOTALL)
if m: text = m.group(1)
try:
    data = json.loads(text.strip())
    print(data.get('summary', '评审未通过'))
except:
    print('评审未通过（解析失败）')
" 2>/dev/null || echo "评审未通过")

        python3 "$NOTIFIER" notify \
            "⚠️ RedCap 独立评审未通过\n\nCommits:\n$COMMIT_LOG\n\n原因: $SUMMARY\n\n详情: $REVIEW_LOG_FILE" \
            --project "redcap" 2>/dev/null || true
    fi

    exit 1  # 非零退出（Claude Code 不阻塞，但标记失败）

elif [[ "$RESULT" == "PASS" ]]; then
    echo "[redcap-on-stop-review] ✓ 独立评审通过" >&2
    rm -f "$REVIEW_RESULT_FILE" 2>/dev/null
    exit 0

else
    echo "[redcap-on-stop-review] WARNING: 评审结果无法解析 ($RESULT)" >&2
    exit 0
fi

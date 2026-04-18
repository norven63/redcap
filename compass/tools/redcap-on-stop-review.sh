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
# 依赖：至少一个可用的独立评审 CLI（优先 gemini，必要时 fallback 到 codex / copilot / claude / kimi）
# ─────────────────────────────────────────────────────────

set -u

INPUT=$(cat)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/redcap-runtime-state.sh"
source "$SCRIPT_DIR/redcap-interop-governance.sh"

HOST_SESSION_ID="${REDCAP_HOST_SESSION_ID:-$(redcap_runtime_json_field "$INPUT" "session_id")}"
HOOK_CWD="${REDCAP_HOOK_CWD:-$REDCAP_ROOT}"
REVIEW_HOST="${REDCAP_STOP_REVIEW_HOST:-claude}"
REVIEW_AGENT_ORDER="${REDCAP_STOP_REVIEW_AGENT_ORDER:-gemini,codex,copilot,claude,kimi}"
BINDING_KEY=""
if [[ -n "$HOST_SESSION_ID" ]]; then
    BINDING_KEY=$(redcap_runtime_binding_key_from_host_session "$REVIEW_HOST" "$HOST_SESSION_ID")
fi

if [[ -n "${REDCAP_RUNTIME_SESSION_ID:-}" && -n "${REDCAP_RUNTIME_CAPABILITY:-}" ]]; then
    redcap_runtime_attach_existing "$REDCAP_RUNTIME_SESSION_ID" "$REDCAP_RUNTIME_CAPABILITY" || true
fi

if [[ -z "${REDCAP_RUNTIME_SESSION_DIR:-}" && -n "$BINDING_KEY" ]]; then
    redcap_runtime_load_from_binding "$REVIEW_HOST" "$HOOK_CWD" "$BINDING_KEY" || true
fi

HEAD_FILE="${REDCAP_BASELINE_HEAD_FILE:-/tmp/redcap-claude-initial-head}"
REVIEW_RESULT_FILE="${REDCAP_REVIEW_RESULT_FILE:-/tmp/redcap-stop-review-result}"
REVIEW_LOG_FILE="${REDCAP_REVIEW_LOG_FILE:-/tmp/redcap-stop-review-log.md}"
NOTIFIER="$SCRIPT_DIR/feishu-notifier.py"
SKIP_FEISHU="${REDCAP_SKIP_FEISHU:-0}"

if [[ -n "${REDCAP_RUNTIME_SESSION_DIR:-}" ]]; then
    HEAD_FILE="${REDCAP_BASELINE_HEAD_FILE:-$(redcap_runtime_path "layerB/initial-head")}"
    REVIEW_RESULT_FILE="${REDCAP_REVIEW_RESULT_FILE:-$(redcap_runtime_path "review/review-result")}"
    REVIEW_LOG_FILE="${REDCAP_REVIEW_LOG_FILE:-$(redcap_runtime_path "review/review-log.md")}"
fi

mkdir -p "$(dirname "$REVIEW_RESULT_FILE")" "$(dirname "$REVIEW_LOG_FILE")" 2>/dev/null || true

write_control_plane_failure() {
    local title="$1"
    local details="$2"

    cat > "$REVIEW_LOG_FILE" <<LOGEOF
# RedCap Stop Hook 控制面审计失败

- **时间**: $(date '+%Y-%m-%d %H:%M:%S')
- **宿主**: $REVIEW_HOST
- **基准 commit**: ${BASELINE:-unknown}
- **当前 HEAD**: ${CURRENT_HEAD:-unknown}
- **失败原因**: $title

## 详情

$details
LOGEOF

    echo "FAIL" > "$REVIEW_RESULT_FILE"

    if [[ "$SKIP_FEISHU" != "1" && -f "$NOTIFIER" ]]; then
        python3 "$NOTIFIER" notify \
            "⚠️ RedCap Layer B 控制面审计失败\n\n$title\n\n详情:\n$details\n\n日志: $REVIEW_LOG_FILE" \
            --project "redcap" 2>/dev/null || true
    fi
}

record_review_gap() {
    local title="$1"
    local details="${2:-}"

    echo "FAIL" > "$REVIEW_RESULT_FILE"
    redcap_interop_write_pending_closure \
        "$REDCAP_ROOT" \
        "$REDCAP_ROOT/.dev-task.md" \
        "$REVIEW_HOST" \
        "stop-review-gap" \
        "review" \
        "$title ${details}" \
        "" \
        "${BASELINE:-}" \
        "${CURRENT_HEAD:-}" \
        >/dev/null 2>&1 || true
}

review_agent_timeout() {
    local agent="$1"

    case "$agent" in
        gemini)
            printf '%s\n' "${REDCAP_REVIEW_AGENT_TIMEOUT_GEMINI_SEC:-${REDCAP_REVIEW_AGENT_TIMEOUT_SEC:-30}}"
            ;;
        copilot)
            printf '%s\n' "${REDCAP_REVIEW_AGENT_TIMEOUT_COPILOT_SEC:-${REDCAP_REVIEW_AGENT_TIMEOUT_SEC:-180}}"
            ;;
        codex)
            printf '%s\n' "${REDCAP_REVIEW_AGENT_TIMEOUT_CODEX_SEC:-${REDCAP_REVIEW_AGENT_TIMEOUT_SEC:-180}}"
            ;;
        claude)
            printf '%s\n' "${REDCAP_REVIEW_AGENT_TIMEOUT_CLAUDE_SEC:-${REDCAP_REVIEW_AGENT_TIMEOUT_SEC:-45}}"
            ;;
        kimi)
            printf '%s\n' "${REDCAP_REVIEW_AGENT_TIMEOUT_KIMI_SEC:-${REDCAP_REVIEW_AGENT_TIMEOUT_SEC:-30}}"
            ;;
        *)
            printf '%s\n' "${REDCAP_REVIEW_AGENT_TIMEOUT_SEC:-60}"
            ;;
    esac
}

review_cli_failure_reason() {
    local output="$1"
    local mode="${2:-any-line}"

    printf '%s' "$output" | python3 -c "
import re
import sys

mode = sys.argv[1]
text = sys.stdin.read()
lines = [line.strip().lower() for line in text.splitlines() if line.strip()]
patterns = (
    ('authentication-failure', (
        r'^(?:error:\s*)?authorization failed(?:,\s*please check your login status)?[.!]?$',
        r'^(?:error:\s*)?please check your login status[.!]?$',
        r'^(?:error:\s*)?not logged in[.!]?$',
        r'^(?:error:\s*)?authentication failed[.!]?$',
        r'^(?:error:\s*)?please login[.!]?$',
        r'^(?:error:\s*)?invalid api key[.!]?$',
        r'^(?:error:\s*)?api key is invalid[.!]?$',
    )),
    ('rate-limited', (
        r'^(?:error:\s*)?rate limit exceeded[.!]?$',
        r'^(?:error:\s*)?too many requests[.!]?$',
        r'^(?:error:\s*)?quota exceeded[.!]?$',
    )),
)
hint_patterns = (
    r'^(?:hint|note|tip|info)[:\-]\s*.+$',
)

def line_reason(line):
    for reason, regexes in patterns:
        if any(re.match(regex, line) for regex in regexes):
            return reason
    return None

def line_kind(line):
    reason = line_reason(line)
    if reason:
        return ('reason', reason)
    if any(re.match(regex, line) for regex in hint_patterns):
        return ('hint', None)
    return ('other', None)

line_info = [line_kind(line) for line in lines]
line_reasons = [reason for kind, reason in line_info if kind == 'reason']

if mode == 'failure-block':
    if lines and line_info[0][0] == 'reason' and line_reasons and len(set(line_reasons)) == 1 and all(kind in ('reason', 'hint') for kind, _ in line_info):
        print(line_reasons[0])
        raise SystemExit(0)
elif mode == 'all-lines':
    if lines and len(line_reasons) == len(lines) and len(set(line_reasons)) == 1:
        print(line_reasons[0])
        raise SystemExit(0)
else:
    if line_reasons:
        print(line_reasons[0])
        raise SystemExit(0)

raise SystemExit(1)
" "$mode" 2>/dev/null
}

review_output_json_payload() {
    local output="$1"

    printf '%s' "$output" | python3 -c "
import sys, json, re
text = sys.stdin.read()
pattern = re.compile(r'\`\`\`([^\n]*)\n(.*?)\n\`\`\`', re.DOTALL)
candidates = []
for match in pattern.finditer(text):
    info = match.group(1).strip().lower()
    body = match.group(2)
    if info not in ('', 'json'):
        continue
    try:
        json.loads(body.strip())
    except:
        continue
    priority = 0 if info == 'json' else 1
    candidates.append((priority, match.start(), body))
if candidates:
    candidates.sort(key=lambda item: (item[0], item[1]))
    print(candidates[0][2])
    raise SystemExit(0)
try:
    json.loads(text.strip())
    print(text.strip())
except:
    print('')
" 2>/dev/null
}

review_output_residual_text() {
    local output="$1"

    printf '%s' "$output" | python3 -c "
import sys, json, re
text = sys.stdin.read()
pattern = re.compile(r'\`\`\`([^\n]*)\n(.*?)\n\`\`\`', re.DOTALL)
candidates = []
for match in pattern.finditer(text):
    info = match.group(1).strip().lower()
    body = match.group(2)
    if info not in ('', 'json'):
        continue
    try:
        json.loads(body.strip())
    except:
        continue
    priority = 0 if info == 'json' else 1
    candidates.append((priority, match.start(), match.end()))
if candidates:
    print(pattern.sub('', text).strip())
    raise SystemExit(0)
try:
    json.loads(text.strip())
    print('')
except:
    print(text.strip())
" 2>/dev/null || echo "$output"
}

review_output_json_result() {
    local output="$1"
    local payload

    payload="$(review_output_json_payload "$output")"
    if [[ -z "$payload" ]]; then
        echo "UNKNOWN"
        return 0
    fi

    printf '%s' "$payload" | python3 -c "
import sys, json
text = sys.stdin.read()
try:
    data = json.loads(text.strip())
except:
    print('UNKNOWN')
    raise SystemExit(0)
result = data.get('result', 'UNKNOWN')
if isinstance(result, str):
    result = result.strip().upper()
else:
    result = 'UNKNOWN'
if result in ('PASS', 'FAIL'):
    print(result)
else:
    print('UNKNOWN')
" 2>/dev/null || echo "UNKNOWN"
}

review_output_text_result() {
    local output="$1"

    printf '%s' "$output" | python3 -c "
import sys, re
text = sys.stdin.read()
for line in text.splitlines():
    m = re.match(r'^\s*(?:result\s*[:=]\s*)?(PASS|FAIL)\s*$', line, re.IGNORECASE)
    if m:
        print(m.group(1).upper())
        raise SystemExit(0)
print('UNKNOWN')
" 2>/dev/null || echo "UNKNOWN"
}

review_output_result() {
    local output="$1"
    local structured_result

    structured_result="$(review_output_json_result "$output")"
    case "$structured_result" in
        PASS|FAIL)
            printf '%s\n' "$structured_result"
            return 0
            ;;
    esac

    review_output_text_result "$output"
}

run_review_command_with_timeout() {
    local timeout="$1"
    local stdout_file="$2"
    local stderr_file="$3"
    shift 3

    python3 - "$timeout" "$stdout_file" "$stderr_file" "$@" <<'PY'
import subprocess
import sys
from pathlib import Path

timeout = int(sys.argv[1])
stdout_path = Path(sys.argv[2])
stderr_path = Path(sys.argv[3])
cmd = sys.argv[4:]

def write_text(path, text):
    path.write_text(text or "", encoding="utf-8", errors="replace")

try:
    completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    write_text(stdout_path, completed.stdout or "")
    write_text(stderr_path, completed.stderr or "")
    sys.exit(completed.returncode)
except subprocess.TimeoutExpired as exc:
    stdout = exc.stdout or ""
    stderr = exc.stderr or ""
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", "replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", "replace")
    write_text(stdout_path, stdout)
    write_text(stderr_path, stderr)
    sys.exit(124)
PY
}

run_review_with_agent() {
    local agent="$1"
    local timeout status
    local output=""
    local stderr_output=""
    local residual_output=""
    local failure_reason=""
    local parsed_result="UNKNOWN"
    local structured_result="UNKNOWN"
    local stderr_failure_mode="any-line"
    local residual_failure_mode="all-lines"
    local stdout_file=""
    local stderr_file=""
    local message_file=""

    timeout="$(review_agent_timeout "$agent")"
    stdout_file="$(mktemp)"
    stderr_file="$(mktemp)"

    case "$agent" in
        gemini)
            run_review_command_with_timeout "$timeout" "$stdout_file" "$stderr_file" gemini -p "$REVIEW_PROMPT" --sandbox false --yolo || status=$?
            ;;
        copilot)
            run_review_command_with_timeout "$timeout" "$stdout_file" "$stderr_file" copilot -p "$REVIEW_PROMPT" --allow-all --autopilot || status=$?
            ;;
        codex)
            message_file="$(mktemp)"
            run_review_command_with_timeout "$timeout" "$stdout_file" "$stderr_file" codex exec -C "$REDCAP_ROOT" --sandbox read-only --ephemeral --output-last-message "$message_file" --color never "$REVIEW_PROMPT" || status=$?
            ;;
        claude)
            run_review_command_with_timeout "$timeout" "$stdout_file" "$stderr_file" claude -p "$REVIEW_PROMPT" --output-format text || status=$?
            ;;
        kimi)
            run_review_command_with_timeout "$timeout" "$stdout_file" "$stderr_file" kimi -p "$REVIEW_PROMPT" -y || status=$?
            ;;
        *)
            rm -f "$stdout_file" "$stderr_file"
            REVIEW_ATTEMPT_FAILURES+=("$agent:unsupported-agent")
            return 1
            ;;
    esac
    status=${status:-0}
    output="$(cat "$stdout_file")"
    stderr_output="$(cat "$stderr_file")"
    if [[ -n "$message_file" && -s "$message_file" ]]; then
        output="$(cat "$message_file")"
    fi
    rm -f "$stdout_file" "$stderr_file" "$message_file"

    if [[ -z "${output//[[:space:]]/}" ]]; then
        output="$stderr_output"
        stderr_output=""
    fi

    if [[ "$status" -eq 124 ]]; then
        REVIEW_ATTEMPT_FAILURES+=("$agent:timeout")
        return 1
    fi

    if [[ -z "${output//[[:space:]]/}" ]]; then
        REVIEW_ATTEMPT_FAILURES+=("$agent:empty-output")
        return 1
    fi

    structured_result="$(review_output_json_result "$output")"
    if [[ "$status" -eq 0 ]]; then
        case "$structured_result" in
            PASS|FAIL)
                stderr_failure_mode="failure-block"
                ;;
        esac
    fi

    if failure_reason="$(review_cli_failure_reason "$stderr_output" "$stderr_failure_mode")"; then
        REVIEW_ATTEMPT_FAILURES+=("$agent:$failure_reason")
        return 1
    fi

    residual_output="$(review_output_residual_text "$output")"
    if failure_reason="$(review_cli_failure_reason "$residual_output" "$residual_failure_mode")"; then
        REVIEW_ATTEMPT_FAILURES+=("$agent:$failure_reason")
        return 1
    fi

    if [[ "$status" -eq 0 ]]; then
        case "$structured_result" in
            PASS|FAIL)
                AGENT_CMD="$agent"
                REVIEW_OUTPUT="$output"
                return 0
                ;;
        esac
    fi

    if [[ "$status" -ne 0 ]]; then
        REVIEW_ATTEMPT_FAILURES+=("$agent:exit-$status")
        return 1
    fi

    parsed_result="$(review_output_result "$output")"
    case "$parsed_result" in
        PASS|FAIL)
            AGENT_CMD="$agent"
            REVIEW_OUTPUT="$output"
            return 0
            ;;
    esac

    REVIEW_ATTEMPT_FAILURES+=("$agent:unparseable-output")
    return 1
}

# ── 前置检查：有无新变更 ──

BASELINE=""
if [[ -f "$HEAD_FILE" ]]; then
    BASELINE=$(cat "$HEAD_FILE")
else
    write_control_plane_failure "missing baseline head" "$HEAD_FILE 不存在，stop-review 无法计算本轮评审范围。"
    exit 1
fi

CURRENT_HEAD=$(git -C "$REDCAP_ROOT" rev-parse HEAD 2>/dev/null) || exit 0

# ── E2E Session Gate 检查 ──
# 如果 e2e-session.yaml 存在，说明有未完成的 E2E 后置处理
# 无论是否有 git 变更，都必须执行 postcheck

E2E_SESSION_FILE="$REDCAP_ROOT/loom/test-reports/e2e-session.yaml"
if [[ -f "$E2E_SESSION_FILE" ]]; then
    echo "[redcap-on-stop-review] ⚠ 检测到未完成的 E2E session，执行后置完整性审计..." >&2
    POSTCHECK_SCRIPT="$REDCAP_ROOT/loom/tools/redcap-e2e-postcheck.sh"
    if [[ -x "$POSTCHECK_SCRIPT" ]]; then
        bash "$POSTCHECK_SCRIPT" >&2
        POSTCHECK_EXIT=$?
        if [[ $POSTCHECK_EXIT -ne 0 ]]; then
            NOTIFIER_E2E="$SCRIPT_DIR/feishu-notifier.py"
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

EXPLORE_NOTES_CHECK="$SCRIPT_DIR/redcap-explore-notes-check.sh"
if [[ -x "$EXPLORE_NOTES_CHECK" ]]; then
    bash "$EXPLORE_NOTES_CHECK" 2>&1 || true
fi

if [[ "$BASELINE" == "$CURRENT_HEAD" ]]; then
    # 无变更，无需评审
    rm -f "$REVIEW_RESULT_FILE" "$REVIEW_LOG_FILE" 2>/dev/null
exit 0
fi

VALIDATOR_CHAIN="$SCRIPT_DIR/redcap-validator-chain.sh"
if [[ ! -x "$VALIDATOR_CHAIN" ]]; then
    write_control_plane_failure "validator chain 缺失" "$VALIDATOR_CHAIN 不存在或不可执行，stop-review 不能静默降级。"
    exit 1
fi

VALIDATOR_OUTPUT=$(REDCAP_RUNTIME_SESSION_ID="${REDCAP_RUNTIME_SESSION_ID:-}" \
    REDCAP_RUNTIME_CAPABILITY="${REDCAP_RUNTIME_CAPABILITY:-}" \
    REDCAP_HOST_PROCESS_PID="${REDCAP_HOST_PROCESS_PID:-$PPID}" \
    bash "$VALIDATOR_CHAIN" stop-review "$REVIEW_HOST" "$REDCAP_ROOT/.dev-task.md" "$BASELINE" "$CURRENT_HEAD" yaml 2>&1) || {
    write_control_plane_failure "validator chain 检查失败" "$VALIDATOR_OUTPUT"
    exit 1
}

# ── 提取 Diff ──

DIFF=$(git -C "$REDCAP_ROOT" --no-pager diff "$BASELINE..HEAD" 2>/dev/null)
COMMIT_LOG=$(git -C "$REDCAP_ROOT" --no-pager log --oneline "$BASELINE..HEAD" 2>/dev/null)
FILE_LIST=$(git -C "$REDCAP_ROOT" --no-pager diff --name-only "$BASELINE..HEAD" 2>/dev/null)

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
if [[ -f "$REDCAP_ROOT/compass/CONTRIBUTING.md" ]]; then
    CONTRIBUTING=$(cat "$REDCAP_ROOT/compass/CONTRIBUTING.md")
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
6. **E2E 完整性**：如果变更涉及 E2E 验证，检查 loom/test-reports/e2e-session.yaml 是否已处理、报告是否写入 loom/test-reports/latest-e2e-report.md（而非其他路径）、loom/test-reports/pending-validations.md 是否已消费。
7. **目录与生命周期边界**：本次变更是否把 session-isolated / local-only / temporary 文件错误放进 git？docs/specs/research/traces/task-reports 的落点是否正确？是否仍残留旧路径或宿主默认输出路径耦合？

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

# ── 选择并执行 Agent CLI ──

AGENT_CMD=""
REVIEW_OUTPUT=""
REVIEW_ATTEMPT_FAILURES=()
IFS=',' read -r -a REVIEW_AGENT_CANDIDATES <<< "$REVIEW_AGENT_ORDER"

for candidate in "${REVIEW_AGENT_CANDIDATES[@]}"; do
    [[ -n "$candidate" ]] || continue
    if ! command -v "$candidate" >/dev/null 2>&1; then
        REVIEW_ATTEMPT_FAILURES+=("$candidate:missing")
        continue
    fi

    if run_review_with_agent "$candidate"; then
        break
    fi
done

if [[ -z "$REVIEW_OUTPUT" ]]; then
    local_failure_summary="all-review-clis-unavailable"
    if [[ "${#REVIEW_ATTEMPT_FAILURES[@]}" -gt 0 ]]; then
        local_failure_summary="$(IFS='; '; printf '%s' "${REVIEW_ATTEMPT_FAILURES[*]}")"
    fi
    echo "[redcap-on-stop-review] WARNING: 所有 Agent 评审都不可用: $local_failure_summary" >&2
    record_review_gap "独立评审不可用" "$local_failure_summary"
    exit 1
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
RESULT="$(review_output_result "$REVIEW_OUTPUT")"

echo "$RESULT" > "$REVIEW_RESULT_FILE"

# ── 结果处理 ──

if [[ "$RESULT" == "FAIL" ]]; then
    echo "[redcap-on-stop-review] ⚠ 独立评审发现 P0 问题！详情: $REVIEW_LOG_FILE" >&2
    record_review_gap "独立评审未通过" "$REVIEW_LOG_FILE"

    # 飞书告警
    if [[ -f "$NOTIFIER" ]]; then
        SUMMARY_PAYLOAD="$(review_output_json_payload "$REVIEW_OUTPUT")"
        SUMMARY=$(printf '%s' "$SUMMARY_PAYLOAD" | python3 -c "
import sys, json
text = sys.stdin.read()
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
    exit 0

else
    echo "[redcap-on-stop-review] WARNING: 评审结果无法解析 ($RESULT)" >&2
    record_review_gap "评审结果无法解析" "$RESULT"
    exit 1
fi

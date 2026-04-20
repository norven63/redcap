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
# 依赖：至少一个可用的独立评审 CLI（优先 codex，必要时 fallback 到 gemini / copilot / claude / kimi）
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
if [[ -n "${REDCAP_STOP_REVIEW_AGENT_ORDER:-}" ]]; then
    REVIEW_AGENT_ORDER="$REDCAP_STOP_REVIEW_AGENT_ORDER"
elif [[ "$REVIEW_HOST" == "codex" ]]; then
    REVIEW_AGENT_ORDER="gemini,copilot,claude,kimi,codex"
else
    REVIEW_AGENT_ORDER="codex,gemini,copilot,claude,kimi"
fi
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

    {
        printf '# RedCap Stop Hook 控制面审计失败\n\n'
        printf -- '- **时间**: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')"
        printf -- '- **宿主**: %s\n' "$REVIEW_HOST"
        printf -- '- **基准 commit**: %s\n' "${BASELINE:-unknown}"
        printf -- '- **当前 HEAD**: %s\n' "${CURRENT_HEAD:-unknown}"
        printf -- '- **失败原因**: %s\n\n' "$title"
        printf '## 详情\n\n%s\n' "$details"
    } > "$REVIEW_LOG_FILE"

    echo "FAIL" > "$REVIEW_RESULT_FILE"

    if [[ "$SKIP_FEISHU" != "1" && -f "$NOTIFIER" ]]; then
        python3 "$NOTIFIER" notify \
            "⚠️ RedCap Layer B 控制面审计失败\n\n$title\n\n详情:\n$details\n\n日志: $REVIEW_LOG_FILE" \
            --project "redcap" 2>/dev/null || true
    fi
}

write_review_unavailable_log() {
    local details="$1"

    {
        printf '# RedCap Stop Hook 独立评审不可用\n\n'
        printf -- '- **时间**: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')"
        printf -- '- **宿主**: %s\n' "$REVIEW_HOST"
        printf -- '- **基准 commit**: %s\n' "${BASELINE:-unknown}"
        printf -- '- **当前 HEAD**: %s\n' "${CURRENT_HEAD:-unknown}"
        printf -- '- **候选顺序**: %s\n\n' "${REVIEW_AGENT_ORDER:-unknown}"
        printf '## 失败摘要\n\n%s\n\n' "$details"
        printf '## 结论\n\n'
        printf '%s\n' '本日志只说明 reviewer CLI 传输层不可用或超时；它不是对代码变更内容的独立评审 verdict。RedCap 必须保持 `review` 红线 pending，直到任一独立 reviewer 产出可解析的 PASS/FAIL。'
    } > "$REVIEW_LOG_FILE"

    echo "FAIL" > "$REVIEW_RESULT_FILE"
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
        r'^sorry,\s*you.?ve hit a rate limit that restricts .+$',
        r'^please try again in \d+\s+(?:second|seconds|minute|minutes|hour|hours|day|days)[.!]?$',
        r'^.*please try again in \d+\s+(?:second|seconds|minute|minutes|hour|hours|day|days).*$',
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

review_output_tracks_valid() {
    local output="$1"
    local payload

    payload="$(review_output_json_payload "$output")"
    if [[ -z "$payload" ]]; then
        return 1
    fi

    printf '%s' "$payload" | python3 -c "
import json
import sys

required = {'architecture', 'governance', 'contracts'}

try:
    data = json.loads(sys.stdin.read().strip())
except Exception:
    raise SystemExit(1)

track_verdicts = data.get('track_verdicts')
if not isinstance(track_verdicts, dict):
    raise SystemExit(1)
if set(track_verdicts.keys()) != required:
    raise SystemExit(1)
for key in required:
    value = track_verdicts.get(key)
    if not isinstance(value, str) or value.strip().upper() not in {'PASS', 'FAIL'}:
        raise SystemExit(1)

issues = data.get('issues')
if not isinstance(issues, list):
    raise SystemExit(1)
for issue in issues:
    if not isinstance(issue, dict):
        raise SystemExit(1)
    track = issue.get('track')
    if not isinstance(track, str) or track not in required:
        raise SystemExit(1)
    severity = issue.get('severity')
    if severity is not None and (not isinstance(severity, str) or severity not in {'P0', 'P1', 'P2'}):
        raise SystemExit(1)

result = data.get('result', '')
if not isinstance(result, str):
    raise SystemExit(1)
if result.strip().upper() == 'PASS':
    for issue in issues:
        if issue.get('severity') == 'P0':
            raise SystemExit(1)
" >/dev/null 2>&1
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

review_text_is_blank() {
    local output="$1"

    printf '%s' "$output" | python3 -c "
import sys
raise SystemExit(0 if not sys.stdin.read().strip() else 1)
" 2>/dev/null
}

run_review_command_with_timeout() {
    local timeout="$1"
    local stdout_file="$2"
    local stderr_file="$3"
    local stdin_file="${REDCAP_REVIEW_COMMAND_STDIN_FILE:-}"
    local prompt_arg_file="${REDCAP_REVIEW_COMMAND_PROMPT_ARG_FILE:-}"
    shift 3

    python3 - "$timeout" "$stdout_file" "$stderr_file" "$stdin_file" "$prompt_arg_file" "$@" <<'PY'
import os
import signal
import subprocess
import sys
from pathlib import Path

timeout = int(sys.argv[1])
stdout_path = Path(sys.argv[2])
stderr_path = Path(sys.argv[3])
stdin_file = sys.argv[4]
prompt_arg_file = sys.argv[5]
cmd = sys.argv[6:]
stdin_text = None

if stdin_file:
    stdin_text = Path(stdin_file).read_text(encoding="utf-8", errors="replace")
if prompt_arg_file:
    prompt_arg = Path(prompt_arg_file).read_text(encoding="utf-8", errors="replace")
    cmd = [prompt_arg if arg == "__REDCAP_REVIEW_PROMPT__" else arg for arg in cmd]

def write_text(path, text):
    path.write_text(text or "", encoding="utf-8", errors="replace")

proc = subprocess.Popen(
    cmd,
    stdin=subprocess.PIPE if stdin_text is not None else None,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    start_new_session=True,
)

try:
    stdout, stderr = proc.communicate(input=stdin_text, timeout=timeout)
    write_text(stdout_path, stdout or "")
    write_text(stderr_path, stderr or "")
    sys.exit(proc.returncode)
except subprocess.TimeoutExpired:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        stdout, stderr = proc.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = proc.communicate()
    write_text(stdout_path, stdout or "")
    write_text(stderr_path, stderr or "")
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
            REDCAP_REVIEW_COMMAND_PROMPT_ARG_FILE="$REVIEW_PROMPT_FILE" \
                run_review_command_with_timeout "$timeout" "$stdout_file" "$stderr_file" gemini -p "__REDCAP_REVIEW_PROMPT__" --sandbox false --yolo || status=$?
            ;;
        copilot)
            REDCAP_REVIEW_COMMAND_PROMPT_ARG_FILE="$REVIEW_PROMPT_FILE" \
                run_review_command_with_timeout "$timeout" "$stdout_file" "$stderr_file" copilot -p "__REDCAP_REVIEW_PROMPT__" --allow-all --autopilot || status=$?
            ;;
        codex)
            message_file="$(mktemp)"
            REDCAP_REVIEW_COMMAND_STDIN_FILE="$REVIEW_PROMPT_FILE" \
                run_review_command_with_timeout "$timeout" "$stdout_file" "$stderr_file" codex exec -C "$REDCAP_ROOT" --sandbox read-only --ephemeral --output-last-message "$message_file" --color never - || status=$?
            ;;
        claude)
            REDCAP_REVIEW_COMMAND_PROMPT_ARG_FILE="$REVIEW_PROMPT_FILE" \
                run_review_command_with_timeout "$timeout" "$stdout_file" "$stderr_file" claude -p "__REDCAP_REVIEW_PROMPT__" --output-format text || status=$?
            ;;
        kimi)
            REDCAP_REVIEW_COMMAND_PROMPT_ARG_FILE="$REVIEW_PROMPT_FILE" \
                run_review_command_with_timeout "$timeout" "$stdout_file" "$stderr_file" kimi -p "__REDCAP_REVIEW_PROMPT__" -y || status=$?
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

    if review_text_is_blank "$output"; then
        output="$stderr_output"
        stderr_output=""
    fi

    if [[ "$status" -eq 124 ]]; then
        REVIEW_ATTEMPT_FAILURES+=("$agent:timeout")
        return 1
    fi

    if review_text_is_blank "$output"; then
        REVIEW_ATTEMPT_FAILURES+=("$agent:empty-output")
        return 1
    fi

    structured_result="$(review_output_json_result "$output")"
    if [[ "$status" -eq 0 ]]; then
        case "$structured_result" in
            PASS|FAIL)
                if ! review_output_tracks_valid "$output"; then
                    REVIEW_ATTEMPT_FAILURES+=("$agent:invalid-track-structure")
                    return 1
                fi
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

# ── 提取 Diff 并组装评审 Prompt ──

DIFF_FILE="$(mktemp)"
COMMIT_LOG_FILE="$(mktemp)"
FILE_LIST_FILE="$(mktemp)"
REVIEW_PROMPT_FILE="$(mktemp)"

git -C "$REDCAP_ROOT" --no-pager diff "$BASELINE..HEAD" >"$DIFF_FILE" 2>/dev/null
git -C "$REDCAP_ROOT" --no-pager log --oneline "$BASELINE..HEAD" >"$COMMIT_LOG_FILE" 2>/dev/null
git -C "$REDCAP_ROOT" --no-pager diff --name-only "$BASELINE..HEAD" >"$FILE_LIST_FILE" 2>/dev/null

if [[ ! -s "$DIFF_FILE" ]]; then
    rm -f "$DIFF_FILE" "$COMMIT_LOG_FILE" "$FILE_LIST_FILE" "$REVIEW_PROMPT_FILE"
    exit 0
fi

if ! python3 - \
    "$REDCAP_ROOT/compass/CONTRIBUTING.core.md" \
    "$REDCAP_ROOT/compass/CONTRIBUTING.md" \
    "$REDCAP_ROOT/references/review-tracks.json" \
    "$DIFF_FILE" \
    "$COMMIT_LOG_FILE" \
    "$FILE_LIST_FILE" \
    "$REVIEW_PROMPT_FILE" <<'PY'
from pathlib import Path
import sys

core_path = Path(sys.argv[1])
contributing_path = Path(sys.argv[2])
review_tracks_path = Path(sys.argv[3])
diff_path = Path(sys.argv[4])
commit_log_path = Path(sys.argv[5])
file_list_path = Path(sys.argv[6])
prompt_path = Path(sys.argv[7])

def read_text(path):
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")

core_contract = read_text(core_path)
contributing_full = read_text(contributing_path)
review_tracks = read_text(review_tracks_path)
diff = read_text(diff_path)
commit_log = read_text(commit_log_path)
file_list = read_text(file_list_path)


def contributing_sections(text):
    sections = []
    current = []
    current_title = "preamble"
    for line in text.splitlines():
        if line.startswith("## "):
            if current:
                sections.append((current_title, "\n".join(current).strip()))
            current_title = line.strip()
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append((current_title, "\n".join(current).strip()))
    return sections


changed_files = [line.strip() for line in file_list.splitlines() if line.strip()]
wanted_prefixes = {
    "## 2. Commit 规范",
    "## 3. 变更后：经验沉淀检查",
    "## 4. 独立架构评审",
    "## 6. 文件变更影响范围提示",
    "## 7. Layer B 大型任务断点续传",
    "## 10. Layer B 需求确认门",
    "## §13 任务级完成强制复盘协议",
}
if any(path.startswith("compass/docs/") or path.startswith("compass/knowledge/") for path in changed_files):
    wanted_prefixes.add("## 7. Layer B 大型任务断点续传")
if any(path.startswith("compass/tools/") or path.startswith("loom/tools/") for path in changed_files):
    wanted_prefixes.update({"## 4. 独立架构评审", "## 7. Layer B 大型任务断点续传"})
if any(path in {"SKILL.md", "compass/CONTRIBUTING.md", "compass/CONTRIBUTING.core.md", "prism/protocol.md"} for path in changed_files):
    wanted_prefixes.update({
        "## 1. 变更前：经验回顾",
        "## 8. Layer B 长任务并行裂变协议",
        "## 9. Layer B Red Teaming 协议",
        "## §11 棱镜（Prism）",
    })

selected_chunks = []
for title, body in contributing_sections(contributing_full):
    if any(title.startswith(prefix) for prefix in wanted_prefixes):
        selected_chunks.append(body)

selected_guidance = "\n\n---\n\n".join(selected_chunks)
max_guidance_chars = 12000
if len(selected_guidance) > max_guidance_chars:
    selected_guidance = selected_guidance[:max_guidance_chars] + f"\n\n... [CONTRIBUTING 精选章节截断至 {max_guidance_chars} 字符]"

max_diff_chars = 20000
diff_len = len(diff)
if diff_len > max_diff_chars:
    diff = (
        diff[:max_diff_chars]
        + f"\n\n... [Diff 截断，共 {diff_len} 字符，仅显示前 {max_diff_chars} 字符]"
    )

prompt = f"""你是一位独立的代码架构评审员。你与开发者无关，你的唯一任务是客观审查以下变更。

## 评审基准

### 启动核心契约

{core_contract}

### 三轨评审定义

{review_tracks}

### CONTRIBUTING 精选章节

{selected_guidance}

## 本次变更摘要

Commits:
{commit_log}

变更文件:
{file_list}

## Diff 内容

```diff
{diff}
```

## 评审要求

请严格对照以下维度逐一检查，并且把发现按三轨归类：

1. **Commit 规范**：是否符合中文 Conventional Commit 格式（type(scope): 描述）？
2. **经验回顾**：变更是否涉及 lessons.md 中的已知陷阱（如 L-4 路由深度、L-7 headless 挂起、L-8 先测再改）？是否有遗漏的检查？
3. **文件联动**：对照 CONTRIBUTING.md 的影响范围表与本次精选章节，本次变更涉及的文件是否有需要同步更新但遗漏的文件？
4. **内容质量**：
   - 文档变更：是否有 Markdown 格式错误（代码块未闭合、标题层级混乱、链接断裂）？
   - 代码变更：是否有安全问题、硬编码、路径错误？
5. **经验沉淀**：本次变更是否发现了新的失败模式或验证了错误假设，但未归档为 Lesson？
6. **E2E 完整性**：如果变更涉及 E2E 验证，检查 loom/test-reports/e2e-session.yaml 是否已处理、报告是否写入 loom/test-reports/latest-e2e-report.md（而非其他路径）、loom/test-reports/pending-validations.md 是否已消费。
7. **目录与生命周期边界**：本次变更是否把 session-isolated / local-only / temporary 文件错误放进 git？docs/specs/research/traces/task-reports 的落点是否正确？是否仍残留旧路径或宿主默认输出路径耦合？

三轨归类要求：
- `architecture`：架构边界、状态机、角色职责、宿主/运行时真相源边界。
- `governance`：规范是否进入执行保障、backlog/debt/lessons/task report 是否同步、是否存在伪完成。
- `contracts`：hook、validator、runtime helper、artifact lifecycle、输入输出契约、fail-closed 边界。
- 每条 issue 必须落到其中一轨；若某轨没有问题，也必须给出明确 verdict。

## 输出格式

严格按以下 JSON 输出，不要输出其他内容：

```json
{{
  \"result\": \"PASS\" 或 \"FAIL\",
  \"track_verdicts\": {{
    \"architecture\": \"PASS\" 或 \"FAIL\",
    \"governance\": \"PASS\" 或 \"FAIL\",
    \"contracts\": \"PASS\" 或 \"FAIL\"
  }},
  \"issues\": [
    {{
      \"severity\": \"P0\" 或 \"P1\" 或 \"P2\",
      \"track\": \"architecture\" 或 \"governance\" 或 \"contracts\",
      \"dimension\": \"维度名\",
      \"description\": \"问题描述\",
      \"suggestion\": \"修复建议\"
    }}
  ],
  \"summary\": \"一句话总结\"
}}
```

规则：有任何 P0 问题 → result=FAIL；仅有 P1/P2 → result=PASS（附建议）。"""

prompt_path.write_text(prompt, encoding="utf-8")
PY
then
    rm -f "$DIFF_FILE" "$COMMIT_LOG_FILE" "$FILE_LIST_FILE" "$REVIEW_PROMPT_FILE"
    write_control_plane_failure "review prompt 构造失败" "无法生成 stop-review 独立评审 prompt。"
    exit 1
fi

COMMIT_LOG="$(cat "$COMMIT_LOG_FILE")"
rm -f "$DIFF_FILE" "$COMMIT_LOG_FILE" "$FILE_LIST_FILE"

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
    rm -f "$REVIEW_PROMPT_FILE"
    local_failure_summary="all-review-clis-unavailable"
    if [[ "${#REVIEW_ATTEMPT_FAILURES[@]}" -gt 0 ]]; then
        local_failure_summary="$(IFS='; '; printf '%s' "${REVIEW_ATTEMPT_FAILURES[*]}")"
    fi
    echo "[redcap-on-stop-review] WARNING: 所有 Agent 评审都不可用: $local_failure_summary" >&2
    write_review_unavailable_log "$local_failure_summary"
    record_review_gap "独立评审不可用" "$local_failure_summary"
    exit 1
fi

rm -f "$REVIEW_PROMPT_FILE"

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

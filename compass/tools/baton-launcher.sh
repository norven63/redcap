#!/usr/bin/env bash
# 用途：棱镜与 Agent 路由脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#prism-and-providers

# baton-launcher.sh — 通用 Agent 启动器（指挥棒核心原语）
#
# 用法:
#   baton-launcher.sh \
#     --cli <claude|gemini|kimi|copilot|codex> \
#     --prompt-file <path>       # prompt 内容文件（避免 ARG_MAX 限制）
#     --output-file <path>       # 供 baton-collect 消费的最终消息写入此文件
#     [--model <model_id>]       # 可选，覆盖默认模型
#     [--session-id <id>]        # 可选，首次调用时指定 session UUID（claude/kimi）
#     [--resume <id>]            # 可选，续接已有 session（优先于 --session-id）
#     [--skill-path <dir>]       # 可选，Skill 外包：在 prompt 前注入"加载此 skill"指令
#     [--work-dir <dir>]         # Agent 工作目录，默认 $PWD
#     [--timeout <seconds>]      # 超时秒数，默认 300
#
# 退出码:
#   0   成功（CLI 正常退出）
#   124 超时
#   其他 CLI 非零退出码透传

set -uo pipefail

# ──────────────────────────────────────────────
# 参数解析
# ──────────────────────────────────────────────
CLI=""
PROMPT_FILE=""
OUTPUT_FILE=""
MODEL=""
SESSION_ID=""
RESUME_ID=""
SKILL_PATH=""
WORK_DIR="${PWD}"
TIMEOUT=300

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cli)         CLI="$2";         shift 2 ;;
    --prompt-file) PROMPT_FILE="$2"; shift 2 ;;
    --output-file) OUTPUT_FILE="$2"; shift 2 ;;
    --model)       MODEL="$2";       shift 2 ;;
    --session-id)  SESSION_ID="$2";  shift 2 ;;
    --resume)      RESUME_ID="$2";   shift 2 ;;
    --skill-path)  SKILL_PATH="$2";  shift 2 ;;
    --work-dir)    WORK_DIR="$2";    shift 2 ;;
    --timeout)     TIMEOUT="$2";     shift 2 ;;
    *)             echo "[baton-launcher] 未知参数: $1" >&2; exit 1 ;;
  esac
done

# ──────────────────────────────────────────────
# 参数校验
# ──────────────────────────────────────────────
if [[ -z "$CLI" ]]; then
  echo "[baton-launcher] 错误: --cli 必须指定（claude|gemini|kimi|copilot|codex）" >&2
  exit 1
fi
if [[ -z "$PROMPT_FILE" ]]; then
  echo "[baton-launcher] 错误: --prompt-file 必须指定" >&2
  exit 1
fi
if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "[baton-launcher] 错误: --prompt-file 文件不存在: $PROMPT_FILE" >&2
  exit 1
fi
if [[ -z "$OUTPUT_FILE" ]]; then
  echo "[baton-launcher] 错误: --output-file 必须指定" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROVIDER_POLICY="$SCRIPT_DIR/redcap-provider-policy.sh"
if [[ ! -x "$PROVIDER_POLICY" && "$CLI" == "copilot" ]]; then
  echo "[baton-launcher] 错误: provider policy gate missing; refusing frozen-sensitive CLI: $CLI" >&2
  exit 1
fi
if [[ -x "$PROVIDER_POLICY" ]]; then
  PROVIDER_POLICY_OUTPUT=""
  if ! PROVIDER_POLICY_OUTPUT="$("$PROVIDER_POLICY" assert-not-frozen "$CLI" baton-delegate 2>&1)"; then
    printf '%s\n' "$PROVIDER_POLICY_OUTPUT" >&2
    exit 1
  fi
fi

# ──────────────────────────────────────────────
# Prompt 大小检查（ARG_MAX 防护）
# 超过 200KB 的 prompt 有触发 OS ARG_MAX 的风险
# ──────────────────────────────────────────────
PROMPT_SIZE=$(wc -c < "$PROMPT_FILE")
if [[ "$PROMPT_SIZE" -gt 524288 ]]; then  # > 512KB：硬拒绝
  echo "[baton-launcher] 错误: prompt 文件过大（${PROMPT_SIZE} bytes > 512KB），有触发 ARG_MAX 的风险，请拆分任务" >&2
  exit 1
elif [[ "$PROMPT_SIZE" -gt 204800 ]]; then  # > 200KB：警告
  echo "[baton-launcher] 警告: prompt 文件较大（${PROMPT_SIZE} bytes > 200KB），建议精简以避免潜在 ARG_MAX 问题" >&2
fi

# ──────────────────────────────────────────────
# Skill 外包：在 prompt 前注入加载指令
# ──────────────────────────────────────────────
EFFECTIVE_PROMPT_FILE="$PROMPT_FILE"

if [[ -n "$SKILL_PATH" ]]; then
  SKILL_MD="${SKILL_PATH}/SKILL.md"
  if [[ ! -f "$SKILL_MD" ]]; then
    echo "[baton-launcher] 错误: --skill-path 下未找到 SKILL.md: $SKILL_MD" >&2
    exit 1
  fi
  # 创建注入了 skill 加载指令的临时 prompt 文件
  INJECTED_PROMPT_FILE="$(mktemp /tmp/baton-prompt-XXXXXX.txt)"
  # shellcheck disable=SC2064
  trap "rm -f '$INJECTED_PROMPT_FILE'" EXIT
  {
    echo "在执行以下任务之前，请先读取并完整理解以下 Skill 的工作规范："
    echo "Skill 路径：${SKILL_PATH}"
    echo "Skill 主文件：${SKILL_MD}"
    echo "---"
    cat "$PROMPT_FILE"
  } > "$INJECTED_PROMPT_FILE"
  EFFECTIVE_PROMPT_FILE="$INJECTED_PROMPT_FILE"
fi

# ──────────────────────────────────────────────
# 组装并执行 CLI 命令
# ──────────────────────────────────────────────
EXIT_CODE=0

run_with_timeout() {
  if timeout "$TIMEOUT" "$@" > "$OUTPUT_FILE" 2>&1; then
    EXIT_CODE=0
  else
    EXIT_CODE=$?
    # timeout 命令在超时时返回 124
  fi
}

case "$CLI" in
  claude)
    # Claude Code CLI：prompt 通过 $(cat ...) 避免 ARG_MAX
    # --permission-mode bypassPermissions：避免 headless 模式权限弹窗
    # --resume 优先（续接）；--session-id 用于首次调用指定 UUID
    CMD=(claude -p "$(cat "$EFFECTIVE_PROMPT_FILE")"
      --output-format json
      --add-dir "$WORK_DIR"
      --permission-mode bypassPermissions)
    if [[ -n "$RESUME_ID" ]]; then
      CMD+=(--resume "$RESUME_ID")
    elif [[ -n "$SESSION_ID" ]]; then
      CMD+=(--session-id "$SESSION_ID")
    fi
    if [[ -n "$MODEL" ]]; then
      CMD+=(--model "$MODEL")
    fi
    run_with_timeout "${CMD[@]}"
    ;;

  gemini)
    CMD=(gemini -p "$(cat "$EFFECTIVE_PROMPT_FILE")"
      --output-format json
      --sandbox false
      --yolo
      --include-directories "$WORK_DIR")
    # Gemini：首次调用不需要 session 参数；--resume 用于续接
    if [[ -n "$RESUME_ID" ]]; then
      CMD+=(--resume "$RESUME_ID")
    fi
    if [[ -n "$MODEL" ]]; then
      CMD+=(--model "$MODEL")
    fi
    run_with_timeout "${CMD[@]}"
    ;;

  kimi)
    # Kimi：使用 --output-format text（不用 stream-json，避免 JSON 流解析复杂性）
    # --print 模式隐含 --yolo；-p 传入 prompt 避免 ARG_MAX
    # Kimi --session 对首次/续接通用，RESUME_ID 优先于 SESSION_ID
    CMD=(kimi --print
      -p "$(cat "$EFFECTIVE_PROMPT_FILE")"
      --output-format text
      --work-dir "$WORK_DIR"
      --yolo
      --max-steps-per-turn 50)
    if [[ -n "$RESUME_ID" ]]; then
      CMD+=(--session "$RESUME_ID")
    elif [[ -n "$SESSION_ID" ]]; then
      CMD+=(--session "$SESSION_ID")
    fi
    if [[ -n "$MODEL" ]]; then
      CMD+=(--model "$MODEL")
    fi
    run_with_timeout "${CMD[@]}"
    ;;

  copilot)
    # Copilot CLI：纯文本输出；session ID 由 sessionStart Hook 自动捕获
    COPILOT_SESSION_FILE="${WORK_DIR}/.workflow/.copilot-session-id"
    CMD=(copilot -p "$(cat "$EFFECTIVE_PROMPT_FILE")"
      --allow-all
      --autopilot)
    if [[ -f "$COPILOT_SESSION_FILE" ]] && [[ -s "$COPILOT_SESSION_FILE" ]]; then
      STORED_SESSION="$(cat "$COPILOT_SESSION_FILE")"
      CMD+=(--resume="$STORED_SESSION")
    fi
    if [[ -n "$MODEL" ]]; then
      CMD+=(--model "$MODEL")
    fi
    run_with_timeout "${CMD[@]}"
    ;;

  codex)
    # Codex CLI：程序化消费必须优先读取 --output-last-message，stdout/stderr 只作 transport noise
    RAW_OUTPUT_FILE="$(mktemp /tmp/baton-codex-raw-XXXXXX.txt)"
    MESSAGE_FILE="$(mktemp /tmp/baton-codex-message-XXXXXX.txt)"
    trap 'rm -f "${RAW_OUTPUT_FILE:-}" "${MESSAGE_FILE:-}" "${INJECTED_PROMPT_FILE:-}"' EXIT

    CMD=(codex exec
      -C "$WORK_DIR"
      --sandbox read-only
      --ephemeral
      --output-last-message "$MESSAGE_FILE"
      --color never
      -)
    if [[ -n "$MODEL" ]]; then
      CMD+=(--model "$MODEL")
    fi

    if timeout "$TIMEOUT" "${CMD[@]}" < "$EFFECTIVE_PROMPT_FILE" > "$RAW_OUTPUT_FILE" 2>&1; then
      EXIT_CODE=0
    else
      EXIT_CODE=$?
    fi

    if [[ -s "$MESSAGE_FILE" ]]; then
      cp "$MESSAGE_FILE" "$OUTPUT_FILE"
    else
      cp "$RAW_OUTPUT_FILE" "$OUTPUT_FILE"
    fi
    ;;

  *)
    echo "[baton-launcher] 错误: 不支持的 CLI: $CLI（支持: claude|gemini|kimi|copilot|codex）" >&2
    exit 1
    ;;
esac

if [[ $EXIT_CODE -eq 124 ]]; then
  echo "[baton-launcher] 超时（${TIMEOUT}s）：$CLI" >&2
fi

exit "$EXIT_CODE"

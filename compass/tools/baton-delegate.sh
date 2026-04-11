#!/usr/bin/env bash
# baton-delegate.sh — Skill 外包高层包装（指挥棒外包原语）
#
# 将子任务委托给指定 Agent（可选加载 skill），收集结果并路由：
#   DONE     → exit 0
#   BLOCKED  → exit 2（blocked 文件已写入 .workflow/）
#   TIMEOUT  → exit 124
#   ERROR    → exit 1（CLI 失败、解析错误等）
#
# 用法:
#   baton-delegate.sh \
#     --cli <claude|gemini|kimi|copilot> \
#     --prompt-file <path>       # 任务 prompt 文件
#     --role <name>              # 任务角色名（用于 blocked 文件命名）
#     [--skill-path <dir>]       # 可选，Skill 外包：加载指定 skill
#     [--model <model_id>]       # 可选，覆盖默认模型
#     [--session-id <id>]        # 可选，续接 session
#     [--work-dir <dir>]         # Agent 工作目录，默认 $PWD
#     [--output-file <path>]     # 可选，Agent 原始输出保存路径（便于调试）
#     [--timeout <seconds>]      # 超时秒数，默认 300
#     [--workflow-dir <dir>]     # blocked 文件写入目录，默认 $PWD/.workflow
#
# 退出码:
#   0    DONE（任务完成）
#   1    ERROR（CLI 失败、解析错误、无完成信号）
#   2    BLOCKED（需要人工决策，blocked 文件已写入）
#   124  TIMEOUT（超时）

set -uo pipefail

# ──────────────────────────────────────────────
# 参数解析
# ──────────────────────────────────────────────
CLI=""
PROMPT_FILE=""
ROLE="agent"
SKILL_PATH=""
MODEL=""
SESSION_ID=""
WORK_DIR="${PWD}"
OUTPUT_FILE=""
TIMEOUT=300
WORKFLOW_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cli)          CLI="$2";          shift 2 ;;
    --prompt-file)  PROMPT_FILE="$2";  shift 2 ;;
    --role)         ROLE="$2";         shift 2 ;;
    --skill-path)   SKILL_PATH="$2";   shift 2 ;;
    --model)        MODEL="$2";        shift 2 ;;
    --session-id)   SESSION_ID="$2";   shift 2 ;;
    --work-dir)     WORK_DIR="$2";     shift 2 ;;
    --output-file)  OUTPUT_FILE="$2";  shift 2 ;;
    --timeout)      TIMEOUT="$2";      shift 2 ;;
    --workflow-dir) WORKFLOW_DIR="$2"; shift 2 ;;
    *)              echo "[baton-delegate] 未知参数: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$CLI" ]]; then
  echo "[baton-delegate] 错误: --cli 必须指定" >&2; exit 1
fi
if [[ -z "$PROMPT_FILE" ]]; then
  echo "[baton-delegate] 错误: --prompt-file 必须指定" >&2; exit 1
fi
if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "[baton-delegate] 错误: --prompt-file 不存在: $PROMPT_FILE" >&2; exit 1
fi

WORKFLOW_DIR="${WORKFLOW_DIR:-${WORK_DIR}/.workflow}"
mkdir -p "$WORKFLOW_DIR"

# ──────────────────────────────────────────────
# 确定输出文件（临时 or 调用方指定）
# ──────────────────────────────────────────────
CLEANUP_OUTPUT=false
if [[ -z "$OUTPUT_FILE" ]]; then
  OUTPUT_FILE="$(mktemp /tmp/baton-output-XXXXXX.txt)"
  CLEANUP_OUTPUT=true
fi

cleanup() {
  if [[ "$CLEANUP_OUTPUT" == true ]] && [[ -f "$OUTPUT_FILE" ]]; then
    rm -f "$OUTPUT_FILE"
  fi
}
trap cleanup EXIT

# ──────────────────────────────────────────────
# 定位脚本目录（baton-launcher/collect 与本脚本同目录）
# ──────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCHER="${SCRIPT_DIR}/baton-launcher.sh"
COLLECT="${SCRIPT_DIR}/baton-collect.sh"

for dep in "$LAUNCHER" "$COLLECT"; do
  if [[ ! -x "$dep" ]]; then
    echo "[baton-delegate] 错误: 依赖脚本不可执行: $dep" >&2
    exit 1
  fi
done

# ──────────────────────────────────────────────
# 组装 launcher 参数
# ──────────────────────────────────────────────
LAUNCHER_ARGS=(
  --cli        "$CLI"
  --prompt-file "$PROMPT_FILE"
  --output-file "$OUTPUT_FILE"
  --work-dir   "$WORK_DIR"
  --timeout    "$TIMEOUT"
)
[[ -n "$SKILL_PATH"  ]] && LAUNCHER_ARGS+=(--skill-path  "$SKILL_PATH")
[[ -n "$MODEL"       ]] && LAUNCHER_ARGS+=(--model       "$MODEL")
[[ -n "$SESSION_ID"  ]] && LAUNCHER_ARGS+=(--session-id  "$SESSION_ID")

# ──────────────────────────────────────────────
# 步骤 1：启动 Agent
# ──────────────────────────────────────────────
echo "[baton-delegate] 启动 Agent: cli=${CLI} role=${ROLE} timeout=${TIMEOUT}s" >&2

LAUNCHER_EXIT=0
bash "$LAUNCHER" "${LAUNCHER_ARGS[@]}" || LAUNCHER_EXIT=$?

if [[ $LAUNCHER_EXIT -eq 124 ]]; then
  echo "[baton-delegate] TIMEOUT（${TIMEOUT}s 超限）：${CLI}" >&2
  exit 124
fi

if [[ $LAUNCHER_EXIT -ne 0 ]]; then
  echo "[baton-delegate] ERROR：Agent 启动失败（exit ${LAUNCHER_EXIT}）" >&2
  exit 1
fi

# ──────────────────────────────────────────────
# 步骤 2：收集结果并解析信号
# ──────────────────────────────────────────────
COLLECT_ARGS=(
  --output-file  "$OUTPUT_FILE"
  --role         "$ROLE"
  --workflow-dir "$WORKFLOW_DIR"
)

COLLECT_EXIT=0
bash "$COLLECT" "${COLLECT_ARGS[@]}" || COLLECT_EXIT=$?

case $COLLECT_EXIT in
  0)
    echo "[baton-delegate] ✅ DONE: ${ROLE}（${CLI}）" >&2
    exit 0
    ;;
  1)
    echo "[baton-delegate] ❌ 未完成（无 ##DONE## 信号）: ${ROLE}（${CLI}）" >&2
    exit 1
    ;;
  2)
    echo "[baton-delegate] 🚧 BLOCKED: ${ROLE}（${CLI}）→ 查看 ${WORKFLOW_DIR}/blocked-${ROLE}-*.md" >&2
    exit 2
    ;;
  3)
    echo "[baton-delegate] ⚠️ 工具层错误（空输出/解析失败）: ${ROLE}（${CLI}）" >&2
    exit 1
    ;;
  *)
    echo "[baton-delegate] ⚠️ 未知收集退出码 ${COLLECT_EXIT}: ${ROLE}（${CLI}）" >&2
    exit 1
    ;;
esac

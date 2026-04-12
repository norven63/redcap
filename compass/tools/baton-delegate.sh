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
#     [--session-id <id>]        # 可选，首次调用指定 session UUID
#     [--resume <id>]            # 可选，续接已有 session（优先于 --session-id）
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

resolve_existing_path() {
  python3 - "$1" <<'PY'
import pathlib
import sys

try:
    print(pathlib.Path(sys.argv[1]).resolve(strict=True))
except Exception:
    sys.exit(1)
PY
}

resolve_path_allow_missing_leaf() {
  python3 - "$1" <<'PY'
import os
import pathlib
import sys

p = pathlib.Path(sys.argv[1])
try:
    if os.path.lexists(p):
        print(p.resolve(strict=True))
    else:
        print((p.parent.resolve(strict=True) / p.name))
except Exception:
    sys.exit(1)
PY
}

# ──────────────────────────────────────────────
# 参数解析
# ──────────────────────────────────────────────
CLI=""
PROMPT_FILE=""
ROLE="agent"
SKILL_PATH=""
MODEL=""
SESSION_ID=""
RESUME_ID=""
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
    --resume)       RESUME_ID="$2";    shift 2 ;;
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
WORKFLOW_DIR_ABS=$(cd "$WORKFLOW_DIR" 2>/dev/null && pwd -P) || {
  echo "[baton-delegate] 错误: 无法解析 workflow-dir: $WORKFLOW_DIR" >&2
  exit 1
}

SKILL_DELEGATION_MODE=false
if [[ -n "$SKILL_PATH" ]]; then
  SKILL_DELEGATION_MODE=true
  PROMPT_PATH=$(resolve_existing_path "$PROMPT_FILE") || {
    echo "[baton-delegate] 错误: 无法解析 Skill 外包请求文件真实路径: $PROMPT_FILE" >&2
    exit 1
  }
  PROMPT_BASENAME="$(basename "$PROMPT_FILE")"
  case "$PROMPT_PATH" in
    "$WORKFLOW_DIR_ABS"/skill-delegation-*.md) ;;
    *)
      echo "[baton-delegate] 错误: Skill 外包请求文件必须位于 ${WORKFLOW_DIR}/skill-delegation-*.md" >&2
      exit 1
      ;;
  esac
  case "$PROMPT_BASENAME" in
    skill-delegation-*.md) ;;
    *)
      echo "[baton-delegate] 错误: Skill 外包请求文件名必须匹配 skill-delegation-{task_id}.md" >&2
      exit 1
      ;;
  esac
fi

# ──────────────────────────────────────────────
# 确定输出文件（临时 or 调用方指定）
# ──────────────────────────────────────────────
CLEANUP_OUTPUT=false
if [[ -z "$OUTPUT_FILE" ]]; then
  if [[ "$SKILL_DELEGATION_MODE" == true ]]; then
    OUTPUT_FILE="${WORKFLOW_DIR}/${PROMPT_BASENAME%.md}-result.md"
  else
    OUTPUT_FILE="$(mktemp /tmp/baton-output-XXXXXX.txt)"
    CLEANUP_OUTPUT=true
  fi
fi

if [[ "$SKILL_DELEGATION_MODE" == true ]]; then
  OUTPUT_PATH=$(resolve_path_allow_missing_leaf "$OUTPUT_FILE") || {
    echo "[baton-delegate] 错误: 无法解析 Skill 外包结果文件真实路径: $OUTPUT_FILE" >&2
    exit 1
  }
  OUTPUT_BASENAME="$(basename "$OUTPUT_FILE")"
  case "$OUTPUT_PATH" in
    "$WORKFLOW_DIR_ABS"/skill-delegation-*-result.md) ;;
    *)
      echo "[baton-delegate] 错误: Skill 外包结果文件必须位于 ${WORKFLOW_DIR}/skill-delegation-*-result.md" >&2
      exit 1
      ;;
  esac
  case "$OUTPUT_BASENAME" in
    skill-delegation-*-result.md) ;;
    *)
      echo "[baton-delegate] 错误: Skill 外包结果文件名必须匹配 skill-delegation-{task_id}-result.md" >&2
      exit 1
      ;;
  esac

  PROMPT_TASK_ID="${PROMPT_BASENAME#skill-delegation-}"
  PROMPT_TASK_ID="${PROMPT_TASK_ID%.md}"
  RESULT_TASK_ID="${OUTPUT_BASENAME#skill-delegation-}"
  RESULT_TASK_ID="${RESULT_TASK_ID%-result.md}"
  if [[ "$PROMPT_TASK_ID" != "$RESULT_TASK_ID" ]]; then
    echo "[baton-delegate] 错误: Skill 外包请求/结果 task_id 必须一致（${PROMPT_TASK_ID} != ${RESULT_TASK_ID}）" >&2
    exit 1
  fi

  PROMPT_FILE="$PROMPT_PATH"
  OUTPUT_FILE="$OUTPUT_PATH"
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
[[ -n "$RESUME_ID"   ]] && LAUNCHER_ARGS+=(--resume      "$RESUME_ID")

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

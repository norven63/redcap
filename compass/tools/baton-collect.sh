#!/usr/bin/env bash
# baton-collect.sh — Agent 结果收集与信号解析
#
# 读取 baton-launcher.sh 写入的 output-file，解析信号并路由：
#   - ##DONE##           → exit 0（成功完成）
#   - ##BLOCKED: <q>##   → 写 blocked 文件 → exit 2（需人工决策）
#   - 无信号              → exit 1（未完成/未知状态，不假设成功）
#   - 解析失败/空文件      → exit 3（工具层错误）
#
# 用法:
#   baton-collect.sh \
#     --output-file <path>     # baton-launcher 写入的 CLI 输出文件
#     --role <name>            # 发起角色名（用于 blocked 文件命名）
#     [--workflow-dir <dir>]   # blocked 文件写入目录，默认 $PWD/.workflow
#
# stdout: 提取的 response 文本
# 退出码:
#   0  DONE
#   1  无信号（未完成状态）
#   2  BLOCKED（blocked 文件已写入）
#   3  工具层错误（空文件/解析失败）

set -uo pipefail

# ──────────────────────────────────────────────
# 参数解析
# ──────────────────────────────────────────────
OUTPUT_FILE=""
ROLE="unknown"
WORKFLOW_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-file)  OUTPUT_FILE="$2";  shift 2 ;;
    --role)         ROLE="$2";         shift 2 ;;
    --workflow-dir) WORKFLOW_DIR="$2"; shift 2 ;;
    *)              echo "[baton-collect] 未知参数: $1" >&2; exit 3 ;;
  esac
done

if [[ -z "$OUTPUT_FILE" ]]; then
  echo "[baton-collect] 错误: --output-file 必须指定" >&2
  exit 3
fi
if [[ ! -f "$OUTPUT_FILE" ]]; then
  echo "[baton-collect] 错误: output-file 不存在: $OUTPUT_FILE" >&2
  exit 3
fi
if [[ ! -s "$OUTPUT_FILE" ]]; then
  echo "[baton-collect] 错误: output-file 为空: $OUTPUT_FILE" >&2
  exit 3
fi

WORKFLOW_DIR="${WORKFLOW_DIR:-${PWD}/.workflow}"
mkdir -p "$WORKFLOW_DIR"

# ──────────────────────────────────────────────
# 提取 response 文本
# 支持 JSON wrapper（claude/gemini）和纯文本（kimi/copilot）
# ──────────────────────────────────────────────
RESPONSE_TEXT=""

# 尝试 JSON 解析：claude 用 .result，gemini 用 .response
RESPONSE_TEXT="$(python3 - "$OUTPUT_FILE" <<'PY'
import json, sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # claude-code: result 字段；gemini: response 字段
    text = data.get("result") or data.get("response") or ""
    print(text, end="")
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
)" || true

# JSON 解析失败时，降级为纯文本（kimi/copilot 输出）
if [[ -z "$RESPONSE_TEXT" ]]; then
  RESPONSE_TEXT="$(cat "$OUTPUT_FILE")"
fi

if [[ -z "$RESPONSE_TEXT" ]]; then
  echo "[baton-collect] 错误: 无法从 output-file 中提取任何文本" >&2
  exit 3
fi

# 输出 response 文本到 stdout
echo "$RESPONSE_TEXT"

# ──────────────────────────────────────────────
# 信号检测
# ──────────────────────────────────────────────

# 检测 ##BLOCKED: <question>##
# 格式：##BLOCKED: 阻塞问题描述##
if echo "$RESPONSE_TEXT" | grep -qE '##BLOCKED:[^#]+##'; then
  BLOCKED_QUESTION="$(echo "$RESPONSE_TEXT" | grep -oE '##BLOCKED:[^#]+##' | head -1 | sed 's/^##BLOCKED: *//' | sed 's/##$//')"
  TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  BLOCKED_FILE="${WORKFLOW_DIR}/blocked-${ROLE}-${TIMESTAMP}.md"

  cat > "$BLOCKED_FILE" <<EOF
# BLOCKED: ${BLOCKED_QUESTION}

**阻塞方**：${ROLE}
**时间戳**：$(date -u +%Y-%m-%dT%H:%M:%SZ)
**上下文**：由 baton-collect.sh 从 Agent 输出中自动提取
**阻塞问题**：
> ${BLOCKED_QUESTION}

**Agent 原始输出**：
$(echo "$RESPONSE_TEXT" | head -50)

**状态**：PENDING
EOF

  echo "[baton-collect] BLOCKED → ${BLOCKED_FILE}" >&2
  exit 2
fi

# 检测 ##DONE##
if echo "$RESPONSE_TEXT" | grep -q '##DONE##'; then
  echo "[baton-collect] DONE" >&2
  exit 0
fi

# 无信号：不假设成功
echo "[baton-collect] 警告: 未检测到 ##DONE## 或 ##BLOCKED## 信号，视为未完成" >&2
exit 1

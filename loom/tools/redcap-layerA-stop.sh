#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap Layer A — Stop Hook（用户级）
#
# 部署位置：~/.claude/settings.json（用户级，所有项目生效）
# 触发时机：每次 Claude Code Agent turn 结束
#
# 职责：
#   检测 RedCap 工作流是否到达 ALL_DONE → 执行 on_ALL_DONE 收尾
#
# 检测逻辑（四重过滤，避免误触发）：
#   1. 开发手册/.workflow/state.yaml 存在（RedCap 项目标识）
#   2. current_state == ALL_DONE（流程完毕）
#   3. Session 归属校验（发起工作流的 session 才能触发）
#   4. 本 session 未通知过（session_id 去重）
#
# 通信协议（Claude Code Hooks Reference）：
#   stdin — JSON（含 session_id, cwd, stop_hook_active 等）
#   exit 0 — 允许停止（本脚本只做旁路通知，不阻塞）
# ─────────────────────────────────────────────────────────

set -u

INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
CWD=$(echo "$INPUT" | grep -o '"cwd"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

if [[ -z "$SESSION_ID" || -z "$CWD" ]]; then
    echo "[redcap-layerA-stop] WARN: failed to parse session_id or cwd from stdin" >&2
    exit 0
fi

# ── 过滤 1: RedCap 工作流存在性 ──────────────────────────

STATE_FILE="$CWD/开发手册/.workflow/state.yaml"
if [[ ! -f "$STATE_FILE" ]]; then
    exit 0
fi

# ── 过滤 2: 状态检查 ─────────────────────────────────────

CURRENT_STATE=$(grep -E '^current_state:' "$STATE_FILE" 2>/dev/null | head -1 | sed 's/^current_state:[[:space:]]*//' | tr -d '"' | tr -d "'")
if [[ "$CURRENT_STATE" != "ALL_DONE" ]]; then
    exit 0
fi

# ── 过滤 3: Session 归属校验 ──────────────────────────────
# 只有发起工作流的 session 才应触发收尾，防止其他 session 在同一
# 项目目录下打开时误触发（state.yaml 仍为 ALL_DONE 但非本 session 产生）

PROJECT_HASH=$(echo -n "$CWD" | md5 2>/dev/null || echo -n "$CWD" | md5sum 2>/dev/null | cut -d' ' -f1)
WORKFLOW_SESSION_FILE="/tmp/redcap-layerA-workflow-session-${PROJECT_HASH}"
if [[ -f "$WORKFLOW_SESSION_FILE" ]]; then
    WORKFLOW_SESSION=$(cat "$WORKFLOW_SESSION_FILE")
    if [[ "$WORKFLOW_SESSION" != "$SESSION_ID" ]]; then
        exit 0
    fi
else
    # Graceful degradation：无归属记录（旧项目/resume session/24h 清理后），
    # 降级为三重过滤继续执行，不阻塞收尾
    echo "[redcap-layerA-stop] WARN: workflow-session file not found for project hash ${PROJECT_HASH}, skipping ownership check (graceful degradation)" >&2
fi

# ── 过滤 4: Session 去重 ─────────────────────────────────

NOTIFIED_FILE="/tmp/redcap-layerA-notified-${SESSION_ID}"
if [[ -f "$NOTIFIED_FILE" ]]; then
    exit 0
fi

# ── 执行 on_ALL_DONE 收尾 ────────────────────────────────

# 使用 readlink 解析真实路径（兼容符号链接）
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")" )" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 读取初始 HEAD（SessionStart 捕获）
INITIAL_HEAD=""
HEAD_FILE="/tmp/redcap-layerA-head-${SESSION_ID}"
if [[ -f "$HEAD_FILE" ]]; then
    INITIAL_HEAD=$(cat "$HEAD_FILE")
fi

PROJECT_NAME=$(basename "$CWD")

# ── Review 兜底检查 ──────────────────────────────────────
# 状态机的 REVIEW_WORKING 节点受 LLM attention 衰减影响可能被跳过。
# 如果 state.yaml history 中没有 reviewer 完成记录，拉起新 Agent 补 Review。

REVIEW_FALLBACK="$REDCAP_ROOT/loom/tools/redcap-layerA-review-fallback.sh"
if [[ -f "$REVIEW_FALLBACK" ]]; then
    # 检查 history 中是否存在 reviewer 角色的 completed 记录
    # state.yaml history 格式: - role: "reviewer" ... status: "completed"
    # -A10 覆盖 history 条目最大字段数（role/agent/session_id/status/finished_at 等约 6-8 字段）
    HAS_REVIEW=$(grep -A10 'role:.*reviewer' "$STATE_FILE" 2>/dev/null | grep -c 'status:.*completed' || true)
    if [[ "$HAS_REVIEW" -eq 0 ]]; then
        echo "[redcap-layerA-stop] Review 未执行，启动兜底 Review..." >&2
        bash "$REVIEW_FALLBACK" "$CWD" "$PROJECT_NAME" 2>&1 || echo "[redcap-layerA-stop] WARN: review-fallback exited with $?" >&2
    fi
fi

# 调用 on-complete 收尾脚本
ON_COMPLETE="$REDCAP_ROOT/compass/tools/redcap-on-complete.sh"
if [[ -f "$ON_COMPLETE" ]]; then
    bash "$ON_COMPLETE" "$CWD" "$INITIAL_HEAD" "$PROJECT_NAME" 2>&1 || echo "[redcap-layerA-stop] WARN: on-complete.sh exited with $?" >&2
else
    echo "[redcap-layerA-stop] WARN: on-complete.sh not found at $ON_COMPLETE" >&2
fi

# 标记已通知
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$NOTIFIED_FILE"

exit 0

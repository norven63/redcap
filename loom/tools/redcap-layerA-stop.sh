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

if [[ "${REDCAP_SUPPRESS_LIFECYCLE_HOOKS:-0}" == "1" || "${REDCAP_INTERNAL_HEALTH_PROBE:-0}" == "1" ]]; then
    cat >/dev/null 2>&1 || true
    exit 0
fi

INPUT=$(cat)
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")" )" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REDCAP_ROOT/compass/tools/redcap-runtime-state.sh"

HOST="${REDCAP_HOST:-claude}"
HOST_PROCESS_PID="${REDCAP_HOST_PROCESS_PID:-$PPID}"
RUNTIME_ATTACHED=0
RUNTIME_CLEANUP_REQUIRED=0
WORKFLOW_SESSION_FILE=""
RELEASE_WORKFLOW_OWNER_ON_EXIT=0

cleanup_runtime_attachment() {
    if [[ "$RELEASE_WORKFLOW_OWNER_ON_EXIT" == "1" && -n "$WORKFLOW_SESSION_FILE" ]]; then
        redcap_runtime_release_text_owner "$WORKFLOW_SESSION_FILE" "${REDCAP_RUNTIME_SESSION_ID:-}" || true
    fi

    if [[ "$RUNTIME_ATTACHED" != "1" ]]; then
        return 0
    fi

    redcap_runtime_clear_process_claim "$HOST" "$HOST_PROCESS_PID" || true
    if [[ "$RUNTIME_CLEANUP_REQUIRED" == "1" ]]; then
        redcap_runtime_remove_path "layerA/ownership-check" || true
    fi
}

trap cleanup_runtime_attachment EXIT

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

BINDING_KEY=$(redcap_runtime_binding_key_from_host_session "$HOST" "$SESSION_ID")
if redcap_runtime_load_from_binding "$HOST" "$CWD" "$BINDING_KEY"; then
    RUNTIME_ATTACHED=1
    RUNTIME_CLEANUP_REQUIRED=1
    PROJECT_ROOT="${REDCAP_RUNTIME_PROJECT_ROOT:-$(redcap_runtime_project_root "$CWD")}"
    WORKFLOW_SESSION_FILE=$(redcap_runtime_project_path_for_root "$PROJECT_ROOT" "layerA/workflow-owner-session")
    OWNERSHIP_CHECK_FILE=$(redcap_runtime_path "layerA/ownership-check")
    if [[ ! -f "$OWNERSHIP_CHECK_FILE" ]]; then
        if [[ -f "$WORKFLOW_SESSION_FILE" ]]; then
            WORKFLOW_SESSION=$(cat "$WORKFLOW_SESSION_FILE")
            if [[ "$WORKFLOW_SESSION" != "${REDCAP_RUNTIME_SESSION_ID:-}" ]]; then
                exit 0
            fi
            RELEASE_WORKFLOW_OWNER_ON_EXIT=1
            redcap_runtime_write_text "layerA/ownership-check" "${REDCAP_RUNTIME_SESSION_ID:-}" || true
        else
            echo "[redcap-layerA-stop] WARN: workflow owner file not found for project root ${PROJECT_ROOT}, entering safe degraded mode" >&2
            redcap_runtime_record_degraded_mode "$CWD" "layerA-stop-missing-owner-claim" "session_id=$SESSION_ID" || true
            exit 0
        fi
    elif [[ -f "$WORKFLOW_SESSION_FILE" ]]; then
        WORKFLOW_SESSION=$(cat "$WORKFLOW_SESSION_FILE")
        if [[ -n "$WORKFLOW_SESSION" && "$WORKFLOW_SESSION" != "${REDCAP_RUNTIME_SESSION_ID:-}" ]]; then
            exit 0
        fi
        RELEASE_WORKFLOW_OWNER_ON_EXIT=1
    fi
else
    redcap_runtime_record_degraded_mode "$CWD" "layerA-stop-safe-degraded" "session_id=$SESSION_ID" || true
    exit 0
fi

# ── 过滤 4: Session 去重 ─────────────────────────────────

NOTIFIED_FILE="/tmp/redcap-layerA-notified-${SESSION_ID}"
if [[ -n "${REDCAP_RUNTIME_SESSION_DIR:-}" ]]; then
    NOTIFIED_FILE=$(redcap_runtime_path "layerA/notified")
fi
if [[ -f "$NOTIFIED_FILE" ]]; then
    exit 0
fi

# ── 执行 on_ALL_DONE 收尾 ────────────────────────────────

# 读取初始 HEAD（SessionStart 捕获）
INITIAL_HEAD=""
HEAD_FILE="/tmp/redcap-layerA-head-${SESSION_ID}"
if [[ -n "${REDCAP_RUNTIME_SESSION_DIR:-}" ]]; then
    HEAD_FILE=$(redcap_runtime_path "layerA/head")
fi
if [[ -f "$HEAD_FILE" ]]; then
    INITIAL_HEAD=$(cat "$HEAD_FILE")
fi

PROJECT_NAME=$(redcap_runtime_project_name "$CWD")

# ── Review 兜底检查 ──────────────────────────────────────
# 状态机的 REVIEW_WORKING 节点受 LLM attention 衰减影响可能被跳过。
# 如果 state.yaml history 中没有 reviewer 完成记录，拉起新 Agent 补 Review。

REVIEW_FALLBACK="$REDCAP_ROOT/loom/tools/redcap-layerA-review-fallback.sh"
REVIEW_FALLBACK_STATUS=0
HAS_REVIEW=$(grep -A10 'role:.*reviewer' "$STATE_FILE" 2>/dev/null | grep -c 'status:.*completed' || true)
if [[ "$HAS_REVIEW" -eq 0 ]]; then
    if [[ -f "$REVIEW_FALLBACK" ]]; then
        echo "[redcap-layerA-stop] Review 未执行，启动兜底 Review..." >&2
        if REDCAP_RUNTIME_SESSION_ID="${REDCAP_RUNTIME_SESSION_ID:-}" \
            REDCAP_RUNTIME_CAPABILITY="${REDCAP_RUNTIME_CAPABILITY:-}" \
            REDCAP_HOST_PROCESS_PID="$HOST_PROCESS_PID" \
            bash "$REVIEW_FALLBACK" "$CWD" "$PROJECT_NAME" 2>&1; then
            REVIEW_FALLBACK_STATUS=0
        else
            REVIEW_FALLBACK_STATUS=$?
            echo "[redcap-layerA-stop] WARN: review-fallback exited with $REVIEW_FALLBACK_STATUS" >&2
        fi
    else
        REVIEW_FALLBACK_STATUS=1
        echo "[redcap-layerA-stop] WARN: review-fallback script missing: $REVIEW_FALLBACK" >&2
    fi
fi

if [[ "$REVIEW_FALLBACK_STATUS" -ne 0 ]]; then
    redcap_runtime_record_degraded_mode "$CWD" "layerA-stop-review-fallback-incomplete" "status=$REVIEW_FALLBACK_STATUS session_id=$SESSION_ID" || true
    exit 0
fi

# 调用 on-complete 收尾脚本
ON_COMPLETE="$REDCAP_ROOT/compass/tools/redcap-on-complete.sh"
ON_COMPLETE_STATUS=1
if [[ -f "$ON_COMPLETE" ]]; then
    if bash "$ON_COMPLETE" "$CWD" "$INITIAL_HEAD" "$PROJECT_NAME" 2>&1; then
        ON_COMPLETE_STATUS=0
    else
        ON_COMPLETE_STATUS=$?
        echo "[redcap-layerA-stop] WARN: on-complete.sh exited with $ON_COMPLETE_STATUS" >&2
    fi
else
    echo "[redcap-layerA-stop] WARN: on-complete.sh not found at $ON_COMPLETE" >&2
fi

if [[ "$ON_COMPLETE_STATUS" -eq 0 ]]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$NOTIFIED_FILE"
else
    redcap_runtime_record_degraded_mode "$CWD" "layerA-stop-on-complete-incomplete" "status=$ON_COMPLETE_STATUS session_id=$SESSION_ID" || true
fi

exit 0

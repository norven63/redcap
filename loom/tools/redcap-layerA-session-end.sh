#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap 通用 Hook 分发代理 (SessionEnd / Stop Hook)
#
# 符合《references/hook-standards.md》契约。
#
# 职责：
#   1. 接收宿主 (Claude/Gemini/Kimi) 传入的 JSON 上下文。
#   2. 识别 Layer A (用户项目) 或 Layer B (RedCap 自身)。
#   3. 分发审计逻辑 (Audit)。
#   4. 执行原子清理 (Cleanup)。
#
# 部署：
#   - Claude Code: .claude/settings.json -> SessionEnd
#   - Gemini CLI: .gemini/settings.json -> SessionEnd
#   - Copilot CLI: .github/hooks/*.json -> sessionEnd
#   - Kimi CLI: dispatcher -> Stop / SessionEnd event
# ─────────────────────────────────────────────────────────

set -u

HOST="${1:-unknown}"
LAYER_B_SESSION_END_STATUS=0

# ── 1. 接收并解析上下文 ──────────────────────────────────

INPUT=$(cat)
# 简单的正则解析（不依赖 jq 以保证环境兼容性）
SESSION_ID=$(echo "$INPUT" | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
CWD=$(echo "$INPUT" | grep -o '"cwd"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

if [[ -z "$CWD" ]]; then
    echo "[redcap-hook-proxy] WARN: failed to parse cwd from stdin" >&2
    CWD=$(pwd)
fi

if [[ -z "$SESSION_ID" ]]; then
    echo "[redcap-hook-proxy] INFO: session_id unavailable for host=$HOST, continue with host-level cleanup only" >&2
fi

# ── 2. 识别层级并执行审计逻辑 (Audit) ─────────────────────

# 使用 readlink 解析真实路径（兼容符号链接）
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")" )" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REDCAP_ROOT/compass/tools/redcap-runtime-state.sh"

# 路径归一化（统一到真实路径，兼容 macOS 的 /tmp -> /private/tmp）
if ! CWD_NORM=$(redcap_runtime_normalize_path "$CWD" 2>/dev/null); then
    CWD_NORM=$(echo "$CWD" | sed 's:/*$::')
fi
if ! REDCAP_DIR_NORM=$(redcap_runtime_normalize_path "$REDCAP_ROOT" 2>/dev/null); then
    REDCAP_DIR_NORM=$(echo "$REDCAP_ROOT" | sed 's:/*$::')
fi

# 检查是否为 RedCap 自身开发 (Layer B)
if [[ "$CWD_NORM" == "$REDCAP_DIR_NORM" || "$CWD_NORM" == "$REDCAP_DIR_NORM/"* ]]; then
    echo "[redcap-hook-proxy] 检测到 Layer B (RedCap 自身) 任务，启动框架审计..." >&2
    B_SESSION_END_SCRIPT="$REDCAP_ROOT/compass/tools/redcap-layerB-session-end.sh"
    if [[ -x "$B_SESSION_END_SCRIPT" ]]; then
        REDCAP_HOST_SESSION_ID="$SESSION_ID" REDCAP_HOOK_CWD="$CWD" REDCAP_HOST_PROCESS_PID="${REDCAP_HOST_PROCESS_PID:-$PPID}" bash "$B_SESSION_END_SCRIPT" "$HOST" 2>&1
        LAYER_B_SESSION_END_STATUS=$?
    fi
else
    # 检查是否为 RedCap 开发的用户项目 (Layer A)
    # 依据：是否存在 开发手册/.workflow/state.yaml
    if [[ -f "$CWD/开发手册/.workflow/state.yaml" ]]; then
        echo "[redcap-hook-proxy] 检测到 Layer A (用户项目) 任务，启动项目审计..." >&2
        A_STOP_SCRIPT="$REDCAP_ROOT/loom/tools/redcap-layerA-stop.sh"
        if [[ -x "$A_STOP_SCRIPT" ]]; then
            echo "$INPUT" | REDCAP_HOST="$HOST" REDCAP_HOST_PROCESS_PID="$PPID" bash "$A_STOP_SCRIPT" 2>&1 || true
        fi
    fi
fi

# ── 3. 执行原子清理 (Cleanup) ─────────────────────────────

echo "[redcap-hook-proxy] 执行原子清理 (Session: ${SESSION_ID:-n/a})..." >&2

# 清理本 session 的标记文件
if [[ -n "$SESSION_ID" ]]; then
    BINDING_KEY=$(redcap_runtime_binding_key_from_host_session "$HOST" "$SESSION_ID")
    if REDCAP_RUNTIME_ALLOW_DISK_RECOVERY=1 REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY=1 redcap_runtime_load_from_binding "$HOST" "$CWD" "$BINDING_KEY"; then
        redcap_runtime_remove_path "layerA/head" || true
        redcap_runtime_remove_path "layerA/notified" || true
        redcap_runtime_remove_path "layerA/ownership-check" || true
    else
        PROJECT_HASH=$(redcap_runtime_project_hash "$CWD")
        redcap_runtime_record_legacy_hit "$CWD" "layerA-session-end-legacy-cleanup" "host=$HOST session_id=$SESSION_ID" || true
        for LEGACY_PATH in \
            "/tmp/redcap-layerA-head-${SESSION_ID}" \
            "/tmp/redcap-layerA-notified-${SESSION_ID}" \
            "/tmp/redcap-layerA-workflow-session-${SESSION_ID}" \
            "/tmp/redcap-layerA-workflow-session-${PROJECT_HASH}"; do
            if [[ -e "$LEGACY_PATH" ]]; then
                if redcap_runtime_quarantine_legacy_path "$CWD" "$LEGACY_PATH" "layerA-session-end-legacy-quarantine" "host=$HOST session_id=$SESSION_ID"; then
                    echo "[redcap-hook-proxy] quarantined legacy Layer A marker: $LEGACY_PATH" >&2
                else
                    rm -f "$LEGACY_PATH" 2>/dev/null || true
                fi
            fi
        done
    fi
fi

redcap_runtime_clear_process_claim "$HOST" "${REDCAP_HOST_PROCESS_PID:-$PPID}" || true

# ── 4. 退出 ───────────────────────────────────────────────

if [[ "$LAYER_B_SESSION_END_STATUS" -ne 0 ]]; then
    if [[ "$HOST" == "gemini" ]]; then
        echo '{"decision": "allow"}'
        exit 2
    fi
    exit "$LAYER_B_SESSION_END_STATUS"
fi

# Hook 返回协议是宿主相关的：Gemini SessionEnd 需要合法 JSON，
# Claude / Copilot 生命周期 Hook 则应保持静默或返回各自宿主可接受的结构。
if [[ "$HOST" == "gemini" ]]; then
    echo '{"decision": "allow"}'
fi

exit 0

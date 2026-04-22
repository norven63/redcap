#!/usr/bin/env bash
# Thin root entry for "Cap revival + RedCap workflow import".

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALLER="$SCRIPT_DIR/compass/tools/redcap-install.sh"

usage() {
    cat <<'EOF'
Usage: ./revive-cap.sh [--host <name>] [--task-file <path>] [--init-identity] [--full-diagnose]

This is a short root-level wrapper around compass/tools/redcap-install.sh.
If --host is omitted, the wrapper will try a lightweight host guess from the current environment.
EOF
}

has_flag() {
    local needle="$1"
    shift || true
    local arg=""
    for arg in "$@"; do
        if [[ "$arg" == "$needle" ]]; then
            return 0
        fi
    done
    return 1
}

detect_host() {
    if [[ -n "${REDCAP_HOST:-}" ]]; then
        printf '%s\n' "$REDCAP_HOST"
        return
    fi
    if [[ -n "${CODEX_THREAD_ID:-}" || -n "${CODEX_INTERNAL_ORIGINATOR_OVERRIDE:-}" || -n "${CODEX_CI:-}" ]]; then
        printf '%s\n' "codex"
        return
    fi
    if [[ -n "${CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC:-}" || -n "${CLAUDECODE:-}" || -n "${CLAUDE_CODE_ENTRYPOINT:-}" ]]; then
        printf '%s\n' "claude"
        return
    fi
    if [[ -n "${GEMINI_CLI:-}" || -n "${GEMINI_SESSION_ID:-}" || -n "${GOOGLE_GENAI_USE_VERTEXAI:-}" ]]; then
        printf '%s\n' "gemini"
        return
    fi
    if [[ -n "${GITHUB_COPILOT_AGENT_SESSION:-}" || -n "${COPILOT_AGENT_SESSION:-}" ]]; then
        printf '%s\n' "copilot"
        return
    fi
    if [[ -n "${KIMI_SESSION_ID:-}" || -n "${MOONSHOT_SESSION_ID:-}" ]]; then
        printf '%s\n' "kimi"
        return
    fi
    printf '%s\n' "unknown"
}

if has_flag "-h" "$@" || has_flag "--help" "$@"; then
    usage
    exec bash "$INSTALLER" "$@"
fi

args=()
if ! has_flag "--host" "$@"; then
    args+=(--host "$(detect_host)")
fi
if ! has_flag "--task-file" "$@" && [[ -f "$SCRIPT_DIR/.dev-task.md" ]]; then
    args+=(--task-file "$SCRIPT_DIR/.dev-task.md")
fi
args+=("$@")

exec bash "$INSTALLER" "${args[@]}"

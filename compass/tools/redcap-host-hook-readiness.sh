#!/usr/bin/env bash
# 用途：宿主适配与分发脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#skill-and-host-distribution

# Report whether the current host's hook surface is repo-owned-ready,
# host-limited, or requires manual home-scope setup.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="${2:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
HOST="${1:-auto}"

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

require_file() {
    local rel="$1"
    [[ -f "$REDCAP_ROOT/$rel" ]] || {
        echo "[redcap-host-hook-readiness] missing file: $rel" >&2
        return 1
    }
}

require_contains() {
    local rel="$1"
    shift
    local text=""
    text="$(cat "$REDCAP_ROOT/$rel")"
    local token=""
    for token in "$@"; do
        if [[ "$text" != *"$token"* ]]; then
            echo "[redcap-host-hook-readiness] $rel missing token: $token" >&2
            return 1
        fi
    done
}

check_claude() {
    local rel=".claude/settings.json"
    require_file "$rel"
    require_contains "$rel" \
        '"InstructionsLoaded"' \
        'redcap-claude-hook-init.sh' \
        '"Stop"' \
        'redcap-on-stop-review.sh' \
        '"SessionEnd"' \
        'loom/tools/redcap-layerA-session-end.sh claude'
    echo "host=claude"
    echo "hook_scope=repo-owned"
    echo "hook_status=ready"
    echo "note=project-level .claude/settings.json already carries Layer B hook registration"
}

check_gemini() {
    local rel=".gemini/settings.json"
    require_file "$rel"
    require_contains "$rel" \
        '"SessionStart"' \
        'redcap-layerB-session-start.sh gemini' \
        '"SessionEnd"' \
        'redcap-layerA-session-end.sh gemini'
    echo "host=gemini"
    echo "hook_scope=repo-owned"
    echo "hook_status=ready"
    echo "note=project-level .gemini/settings.json already carries Layer B hook registration"
}

check_copilot() {
    local rel=".github/hooks/redcap-layerB.json"
    require_file "$rel"
    require_file ".github/hooks/scripts/redcap-layerB-session-start.sh"
    require_file ".github/hooks/scripts/redcap-layerB-session-end.sh"
    require_file ".github/hooks/scripts/redcap-layerB-post-tool.sh"
    require_contains "$rel" \
        '"sessionStart"' \
        'redcap-layerB-session-start.sh' \
        '"sessionEnd"' \
        'redcap-layerB-session-end.sh' \
        '"postToolUse"' \
        'redcap-layerB-post-tool.sh'
    echo "host=copilot"
    echo "hook_scope=repo-owned"
    echo "hook_status=ready"
    echo "note=.github/hooks/*.json and wrapper scripts already provide Layer B hook registration"
}

check_codex() {
    local config_rel=".codex/config.toml"
    local hooks_rel=".codex/hooks.json"
    local marker_result_rel="references/codex-live-marker-e2e.json"
    local marker_status="pending"

    require_file "$config_rel"
    require_file "$hooks_rel"
    require_file "compass/tools/redcap-codex-session-start.sh"
    require_file "compass/tools/redcap-codex-pre-tool-use.sh"
    require_file "compass/tools/redcap-codex-stop.sh"
    require_file "compass/tools/redcap-codex-live-marker-e2e.sh"
    require_contains "$config_rel" \
        "codex_hooks = true"
    require_contains "$hooks_rel" \
        '"SessionStart"' \
        'redcap-codex-session-start.sh' \
        '"PreToolUse"' \
        'redcap-codex-pre-tool-use.sh' \
        '"Stop"' \
        'redcap-codex-stop.sh'
    if [[ -f "$REDCAP_ROOT/$marker_result_rel" ]] && grep -Fq '"codex_cli_live_marker_e2e_passed": true' "$REDCAP_ROOT/$marker_result_rel"; then
        marker_status="codex-cli-live-marker-pass"
    fi
    echo "host=codex"
    echo "hook_scope=repo-owned-candidate"
    if [[ "$marker_status" == "codex-cli-live-marker-pass" ]]; then
        echo "hook_status=partial-ready"
        echo "note=Codex CLI live marker E2E passed via $marker_result_rel; Codex.app interactive surface remains degraded unless separately observed; no full reply-veto claim"
    else
        echo "hook_status=degraded"
        echo "note=Codex official lifecycle hooks are configured in .codex/hooks.json, but remain degraded until project trust, feature flag loading, and live marker E2E verify physical SessionStart/Stop firing; run redcap-codex-live-marker-e2e.sh --run to create $marker_result_rel; no full reply-veto claim"
    fi
}

check_kimi() {
    echo "host=kimi"
    echo "hook_scope=manual-home-scope"
    echo "hook_status=manual"
    echo "note=Kimi hook deployment lives under ~/.kimi and should not be silently installed from a repo-local revival script"
}

if [[ "$HOST" == "auto" || "$HOST" == "unknown" || -z "$HOST" ]]; then
    HOST="$(detect_host)"
fi

case "$HOST" in
    claude) check_claude ;;
    gemini) check_gemini ;;
    copilot) check_copilot ;;
    codex) check_codex ;;
    kimi) check_kimi ;;
    *)
        echo "host=$HOST"
        echo "hook_scope=unknown"
        echo "hook_status=manual"
        echo "note=unknown host; no repo-owned hook bootstrap available"
        ;;
esac

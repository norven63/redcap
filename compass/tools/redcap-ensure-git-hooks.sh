#!/usr/bin/env bash
# shellcheck shell=bash
# Ensure RedCap's repo-owned git hooks are active for this repository.

set -euo pipefail

REPO_ROOT="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -z "$REPO_ROOT" ]]; then
    REPO_ROOT="$DEFAULT_REDCAP_ROOT"
fi

HOOKS_PATH=".githooks"
HOOK_FILE="$REPO_ROOT/$HOOKS_PATH/pre-commit"

resolve_hook_dir() {
    local repo_root="$1"
    local hook_dir="$2"

    if [[ -z "$hook_dir" ]]; then
        return 1
    fi

    if [[ "$hook_dir" != /* ]]; then
        hook_dir="$repo_root/$hook_dir"
    fi

    if [[ -d "$hook_dir" ]]; then
        (cd "$hook_dir" && pwd)
        return 0
    fi

    printf '%s\n' "$hook_dir"
}

git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1 || {
    echo "[redcap-ensure-git-hooks] not a git repository: $REPO_ROOT" >&2
    exit 1
}

if [[ ! -x "$HOOK_FILE" ]]; then
    echo "[redcap-ensure-git-hooks] missing repo-owned pre-commit hook: $HOOK_FILE" >&2
    exit 1
fi

CURRENT_HOOKS_PATH="$(git -C "$REPO_ROOT" config --local --get core.hooksPath || true)"
DESIRED_ABS="$(resolve_hook_dir "$REPO_ROOT" "$HOOKS_PATH")"
CURRENT_ABS="$(resolve_hook_dir "$REPO_ROOT" "$CURRENT_HOOKS_PATH" || true)"

if [[ -n "$CURRENT_ABS" && "$CURRENT_ABS" == "$DESIRED_ABS" ]]; then
    if [[ "$CURRENT_HOOKS_PATH" != "$HOOKS_PATH" ]]; then
        git -C "$REPO_ROOT" config --local core.hooksPath "$HOOKS_PATH"
    fi
    exit 0
fi

if [[ -n "$CURRENT_HOOKS_PATH" ]]; then
    git -C "$REPO_ROOT" config --local redcap.previousHooksPath "$CURRENT_HOOKS_PATH"
else
    git -C "$REPO_ROOT" config --local --unset redcap.previousHooksPath >/dev/null 2>&1 || true
fi

git -C "$REPO_ROOT" config --local core.hooksPath "$HOOKS_PATH"

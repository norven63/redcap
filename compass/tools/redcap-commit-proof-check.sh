#!/usr/bin/env bash
# shellcheck shell=bash
# Validate that the current session produced at least one clean commit.

set -uo pipefail

PROJECT_DIR="${1:-}"
INITIAL_HEAD="${2:-}"
CURRENT_HEAD="${3:-}"

if [[ -z "$PROJECT_DIR" || -z "$INITIAL_HEAD" ]]; then
    echo "usage: $0 <project_dir> <initial_head> [current_head]" >&2
    exit 2
fi

if [[ -z "$CURRENT_HEAD" ]]; then
    CURRENT_HEAD=$(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null || true)
fi

if [[ -z "$CURRENT_HEAD" ]]; then
    echo "[redcap-commit-proof-check] 无法解析当前 HEAD" >&2
    exit 1
fi

if ! git -C "$PROJECT_DIR" rev-parse "${INITIAL_HEAD}^{commit}" >/dev/null 2>&1; then
    echo "[redcap-commit-proof-check] 初始 HEAD 不可解析：$INITIAL_HEAD" >&2
    exit 1
fi

WORKTREE_STATUS=$(git -C "$PROJECT_DIR" status --porcelain 2>/dev/null || true)
if [[ -n "$WORKTREE_STATUS" ]]; then
    echo "[redcap-commit-proof-check] worktree 仍有未提交变更" >&2
    exit 1
fi

if [[ "$CURRENT_HEAD" == "$INITIAL_HEAD" ]]; then
    echo "[redcap-commit-proof-check] 未检测到本轮新 commit" >&2
    exit 1
fi

exit 0

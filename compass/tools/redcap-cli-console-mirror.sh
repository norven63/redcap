#!/usr/bin/env bash
# shellcheck shell=bash
# Maintain cli_console.md as an overwrite-only display mirror.

set -euo pipefail

MODE="${1:-write}"
SOURCE_FILE="${2:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TARGET_PATH="${REDCAP_CLI_CONSOLE_PATH:-$REDCAP_ROOT/cli_console.md}"

usage() {
    echo "usage: $0 <write|clear|path> [source_file]" >&2
}

case "$MODE" in
    write)
        mkdir -p "$(dirname "$TARGET_PATH")"
        if [[ -n "$SOURCE_FILE" ]]; then
            if [[ ! -f "$SOURCE_FILE" ]]; then
                echo "[redcap-cli-console-mirror] source file not found: $SOURCE_FILE" >&2
                exit 1
            fi
            cat "$SOURCE_FILE" >"$TARGET_PATH"
        else
            cat >"$TARGET_PATH"
        fi
        ;;
    clear)
        mkdir -p "$(dirname "$TARGET_PATH")"
        : >"$TARGET_PATH"
        ;;
    path)
        printf '%s\n' "$TARGET_PATH"
        ;;
    *)
        usage
        exit 2
        ;;
esac

#!/usr/bin/env bash
# shellcheck shell=bash
# Validate that a pending closure can still be reconciled against the current head.

set -uo pipefail

HEAD_MISMATCH="${1:-}"
PENDING_AUDITED_HEAD="${2:-}"
CURRENT_HEAD="${3:-}"

if [[ "$HEAD_MISMATCH" != "0" && "$HEAD_MISMATCH" != "1" ]]; then
    echo "usage: $0 <head_mismatch:0|1> [pending_audited_head] [current_head]" >&2
    exit 2
fi

if [[ "$HEAD_MISMATCH" == "0" ]]; then
    exit 0
fi

echo "[redcap-closure-reanchor-check] pending closure audited head cannot be proven to reach current HEAD" >&2
if [[ -n "$PENDING_AUDITED_HEAD" ]]; then
    echo "  audited_head: $PENDING_AUDITED_HEAD" >&2
fi
if [[ -n "$CURRENT_HEAD" ]]; then
    echo "  current_head: $CURRENT_HEAD" >&2
fi

exit 1

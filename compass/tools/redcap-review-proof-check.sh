#!/usr/bin/env bash
# shellcheck shell=bash
# Validate that session-end has a usable independent review proof.

set -uo pipefail

REVIEW_REQUIRED="${1:-}"
REVIEW_STATUS="${2:-}"
TASK_FILE="${3:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ "$REVIEW_REQUIRED" != "0" && "$REVIEW_REQUIRED" != "1" ]]; then
    echo "usage: $0 <review_required:0|1> [review_status] [task_file]" >&2
    exit 2
fi

if [[ "$REVIEW_REQUIRED" == "0" ]]; then
    exit 0
fi

prism_acceptance_status() {
    local task_file="$1"
    local output=""

    [[ -n "$task_file" && -f "$task_file" ]] || return 1
    output="$(bash "$SCRIPT_DIR/redcap-prism-acceptance-check.sh" --task-file "$task_file" 2>/dev/null)" || return 1
    python3 - <<'PY' "$output"
import json
import sys

payload = json.loads(sys.argv[1])
print(str(payload.get("status", "")).strip())
PY
}

case "$REVIEW_STATUS" in
    PASS|PRISM_PASS)
        exit 0
        ;;
    "")
        if [[ -n "$TASK_FILE" ]]; then
            if [[ "$(prism_acceptance_status "$TASK_FILE" 2>/dev/null || true)" == "pass" ]]; then
                echo "[redcap-review-proof-check] satisfied via bound Prism acceptance"
                exit 0
            fi
        fi
        echo "[redcap-review-proof-check] review is required but no review result is available" >&2
        ;;
    FAIL)
        echo "[redcap-review-proof-check] stop-review result is FAIL" >&2
        ;;
    MISSING)
        echo "[redcap-review-proof-check] missing independent review proof for session-end" >&2
        ;;
    INCONCLUSIVE)
        echo "[redcap-review-proof-check] stop-review result is INCONCLUSIVE" >&2
        ;;
    *)
        echo "[redcap-review-proof-check] unsupported review result: $REVIEW_STATUS" >&2
        ;;
esac

exit 1

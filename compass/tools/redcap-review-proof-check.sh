#!/usr/bin/env bash
# shellcheck shell=bash
# Validate that session-end has a usable independent review proof.

set -uo pipefail

REVIEW_REQUIRED="${1:-}"
REVIEW_STATUS="${2:-}"

if [[ "$REVIEW_REQUIRED" != "0" && "$REVIEW_REQUIRED" != "1" ]]; then
    echo "usage: $0 <review_required:0|1> [review_status]" >&2
    exit 2
fi

if [[ "$REVIEW_REQUIRED" == "0" ]]; then
    exit 0
fi

case "$REVIEW_STATUS" in
    PASS)
        exit 0
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
    "")
        echo "[redcap-review-proof-check] review is required but no review result is available" >&2
        ;;
    *)
        echo "[redcap-review-proof-check] unsupported review result: $REVIEW_STATUS" >&2
        ;;
esac

exit 1

#!/usr/bin/env bash
# shellcheck shell=bash

if [[ "${_REDCAP_VALIDATOR_OUTPUT_SH:-0}" == "1" ]]; then
    return 0 2>/dev/null || exit 0
fi
_REDCAP_VALIDATOR_OUTPUT_SH=1

redcap_validator_step_status() {
    local output="$1"
    local step="$2"

    printf '%s\n' "$output" | awk -v step="$step" 'index($0, "] " step " :: ") {split($0, parts, " :: "); print parts[2]; exit}'
}

redcap_validator_step_detail() {
    local output="$1"
    local step="$2"

    printf '%s\n' "$output" | awk -v step="$step" '
        /^\[[0-9]+\] / {
            if (capture) {
                exit
            }
            if (index($0, "] " step " :: ")) {
                capture = 1
                next
            }
        }
        capture {
            print
        }
    '
}

redcap_validator_output_has_recordable_step() {
    local output="$1"
    shift
    local step=""

    for step in "$@"; do
        if [[ -n "$(redcap_validator_step_status "$output" "$step")" ]]; then
            return 0
        fi
    done

    return 1
}

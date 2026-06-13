#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../.."
tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/redcap-codex-pretool-fixture.XXXXXX")"
trap 'rm -rf "$tmp_dir"' EXIT
printf '%s' '{"hook_event_name":"PreToolUse","session_id":"00000000-0000-0000-0000-000000000000","turn_id":"fixture-turn","tool_name":"Bash","tool_input":{"command":"git reset --hard"}}' \
  | REDCAP_CODEX_HOOK_EVIDENCE_DIR="$tmp_dir" python3 runtime/host-adapters/codex/codex-hook.py --event PreToolUse

#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../.."
tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/redcap-codex-pretool-evidence.XXXXXX")"
trap 'rm -rf "$tmp_dir"' EXIT
printf '%s' '{"hook_event_name":"PreToolUse","cwd":"/Users/norven/workspace/AI Era/redcap","session_id":"00000000-0000-0000-0000-000000000000","turn_id":"fixture-turn","tool_name":"Write","tool_input":{"file_path":"assets/evidence/manual-forgery.json","content":"{}"}}' \
  | REDCAP_CODEX_HOOK_EVIDENCE_DIR="$tmp_dir" runtime/host-adapters/codex/codex-hook.py --event PreToolUse
printf '\n'
printf '%s' '{"hook_event_name":"PreToolUse","cwd":"/Users/norven/workspace/AI Era/redcap","session_id":"00000000-0000-0000-0000-000000000000","turn_id":"fixture-turn","tool_name":"NotebookEdit","tool_input":{"notebook_path":"assets/evidence/manual-forgery.ipynb","edits":[]}}' \
  | REDCAP_CODEX_HOOK_EVIDENCE_DIR="$tmp_dir" runtime/host-adapters/codex/codex-hook.py --event PreToolUse

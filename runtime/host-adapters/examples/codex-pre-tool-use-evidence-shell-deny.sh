#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../.."
tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/redcap-codex-pretool-evidence-shell.XXXXXX")"
trap 'rm -rf "$tmp_dir"' EXIT

run_probe() {
  local command="$1"
  local output
  output="$(
    python3 - "$command" <<'PY' | PWDDIR="$PWD" HOMEBREW="$PWD" REDCAP_CODEX_HOOK_EVIDENCE_DIR="$tmp_dir" python3 runtime/host-adapters/codex/codex-hook.py --event PreToolUse
import json
import sys

print(json.dumps({
    "hook_event_name": "PreToolUse",
    "cwd": "/Users/norven/workspace/AI Era/redcap",
    "session_id": "00000000-0000-0000-0000-000000000000",
    "turn_id": "fixture-turn",
    "tool_name": "Bash",
    "tool_input": {"command": sys.argv[1]},
}))
PY
  )"
  printf '%s\n' "$output"
  if [[ "$output" != *'"permissionDecision": "deny"'* ]]; then
    printf 'expected command to be denied: %s\n' "$command" >&2
    return 1
  fi
  printf '\n'
}

run_probe "cp /tmp/fake.json assets/evidence/manual-forgery.json"
run_probe "sed -i '' s/a/b/ assets/evidence/manual-forgery.json"
run_probe "dd if=/tmp/fake.json of=assets/evidence/manual-forgery.json"
run_probe "install /tmp/fake.json assets/evidence/manual-forgery.json"
run_probe "rsync /tmp/fake.json assets/evidence/manual-forgery.json"
run_probe "ditto /tmp/fake.json assets/evidence/manual-forgery.json"
run_probe "perl -pi -e s/a/b/ assets/evidence/manual-forgery.json"
absolute_target="$(printf '%q' "$PWD/assets/evidence/manual-forgery.json")"
run_probe "echo forged > $absolute_target"
run_probe "echo forged >> assets/evidence/manual-forgery.json"
run_probe "printf forged | tee $absolute_target"
run_probe "printf forged | tee -a assets/evidence/manual-forgery.json"
run_probe "echo forged <> assets/evidence/manual-forgery.json"
run_probe 'echo forged >| $PWD/assets/evidence/manual-forgery.json'
run_probe 'echo forged <> $PWD/assets/evidence/manual-forgery.json'
run_probe 'printf forged | tee $PWD/assets/evidence/manual-forgery.json'
run_probe 'dd if=/tmp/fake.json of=$PWD/assets/evidence/manual-forgery.json'
run_probe 'echo forged > ~/workspace/AI\ Era/redcap/assets/evidence/manual-forgery.json'
run_probe 'curl -o $PWD/assets/evidence/manual-forgery.json https://example.invalid/fake.json'
run_probe 'curl --output $PWD/assets/evidence/manual-forgery.json https://example.invalid/fake.json'
run_probe 'curl --output-dir $PWD/assets/evidence -O https://example.invalid/fake.json'
run_probe 'wget -O $PWD/assets/evidence/manual-forgery.json https://example.invalid/fake.json'
run_probe 'wget --output-document=$PWD/assets/evidence/manual-forgery.json https://example.invalid/fake.json'
run_probe 'wget -P $PWD/assets/evidence https://example.invalid/fake.json'
run_probe 'echo forged > $PWDDIR/assets/evidence/manual-forgery.json'
run_probe 'echo forged > $HOMEBREW/assets/evidence/manual-forgery.json'

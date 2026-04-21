#!/usr/bin/env bash
# redcap-e2e-session.sh — manage the repo-owned e2e-session ledger.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SESSION_FILE="$REDCAP_ROOT/loom/test-reports/e2e-session.yaml"

usage() {
  cat <<'EOF'
Usage:
  bash loom/tools/redcap-e2e-session.sh start --preset <name> --instruction <text>
  bash loom/tools/redcap-e2e-session.sh start --instruction <text> --switch <name> [--switch <name> ...]
  bash loom/tools/redcap-e2e-session.sh mark <switch> [<switch> ...]
  bash loom/tools/redcap-e2e-session.sh status
  bash loom/tools/redcap-e2e-session.sh clear

Presets:
  smoke       happy_path + deliverable_check
  rollback    happy_path + qa_fail_code + qa_fail_design + review_fail + deliverable_check
  escalation  happy_path + escalate_l1 + escalate_l2 + paused_resume + deliverable_check
  infra       happy_path + agent_fallback + all_agent_fail + iteration_scan + deliverable_check
  full        all benchmark switches
EOF
}

preset_switches() {
  case "$1" in
    smoke)
      printf '%s\n' happy_path deliverable_check
      ;;
    rollback)
      printf '%s\n' happy_path qa_fail_code qa_fail_design review_fail deliverable_check
      ;;
    escalation)
      printf '%s\n' happy_path escalate_l1 escalate_l2 paused_resume deliverable_check
      ;;
    infra)
      printf '%s\n' happy_path agent_fallback all_agent_fail iteration_scan deliverable_check
      ;;
    full)
      printf '%s\n' \
        happy_path \
        multi_step \
        qa_fail_code \
        qa_fail_design \
        review_fail \
        escalate_l1 \
        escalate_l2 \
        paused_resume \
        agent_fallback \
        all_agent_fail \
        qa_max_retry \
        iteration_scan \
        deliverable_check
      ;;
    *)
      echo "[redcap-e2e-session] unknown preset: $1" >&2
      exit 1
      ;;
  esac
}

write_session_file() {
  local preset="$1"
  local instruction="$2"
  shift 2
  python3 - "$SESSION_FILE" "$preset" "$instruction" "$@" <<'PY'
import datetime as dt
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
preset = sys.argv[2]
instruction = sys.argv[3]
switches = list(dict.fromkeys(sys.argv[4:]))

def render_list(items):
    if not items:
        return "[]"
    return "[" + ", ".join(json.dumps(item, ensure_ascii=False) for item in items) + "]"

body = (
    f'created_at: "{dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")}"\n'
    f'preset: {json.dumps(preset, ensure_ascii=False)}\n'
    f'switches_on: {render_list(switches)}\n'
    'switches_completed: []\n'
    f'user_instruction: {json.dumps(instruction, ensure_ascii=False)}\n'
)
path.write_text(body, encoding="utf-8")
PY
}

mark_switches() {
  python3 - "$SESSION_FILE" "$@" <<'PY'
import json
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
if not path.exists():
    raise SystemExit("[redcap-e2e-session] session file does not exist")

text = path.read_text(encoding="utf-8")
targets = [item for item in sys.argv[2:] if item]
if not targets:
    raise SystemExit("[redcap-e2e-session] at least one switch is required")

def parse_inline_list(key: str):
    match = re.search(rf"^{key}:\s*\[(.*)\]\s*$", text, re.MULTILINE)
    if not match:
        return []
    raw = match.group(1).strip()
    if not raw:
        return []
    return json.loads("[" + raw + "]")

def replace_inline_list(source: str, key: str, items):
    rendered = "[" + ", ".join(json.dumps(item, ensure_ascii=False) for item in items) + "]"
    return re.sub(rf"^{key}:\s*\[.*\]\s*$", f"{key}: {rendered}", source, flags=re.MULTILINE)

switches_on = parse_inline_list("switches_on")
switches_completed = parse_inline_list("switches_completed")
known = set(switches_on)
completed = list(switches_completed)

for item in targets:
    if known and item not in known:
        raise SystemExit(f"[redcap-e2e-session] switch not declared in switches_on: {item}")
    if item not in completed:
        completed.append(item)

updated = replace_inline_list(text, "switches_completed", completed)
path.write_text(updated, encoding="utf-8")
print("E2E_SESSION_MARK_OK")
print("completed=" + ",".join(completed))
PY
}

show_status() {
  python3 - "$SESSION_FILE" <<'PY'
import json
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
if not path.exists():
    print("E2E_SESSION_STATUS")
    print("exists=false")
    raise SystemExit(0)

text = path.read_text(encoding="utf-8")

def parse_scalar(key: str):
    match = re.search(rf"^{key}:\s*(.+)\s*$", text, re.MULTILINE)
    if not match:
        return ""
    raw = match.group(1).strip()
    try:
        return json.loads(raw)
    except Exception:
        return raw.strip('"')

def parse_inline_list(key: str):
    match = re.search(rf"^{key}:\s*\[(.*)\]\s*$", text, re.MULTILINE)
    if not match:
        return []
    raw = match.group(1).strip()
    if not raw:
        return []
    return json.loads("[" + raw + "]")

switches_on = parse_inline_list("switches_on")
switches_completed = parse_inline_list("switches_completed")
missing = [item for item in switches_on if item not in switches_completed]

print("E2E_SESSION_STATUS")
print("exists=true")
print("path=" + str(path))
print("created_at=" + str(parse_scalar("created_at")))
print("preset=" + str(parse_scalar("preset")))
print("instruction=" + str(parse_scalar("user_instruction")))
print("switches_on=" + ",".join(switches_on))
print("switches_completed=" + ",".join(switches_completed))
print("switches_missing=" + ",".join(missing))
PY
}

COMMAND="${1:-status}"
case "$COMMAND" in
  start)
    shift
    PRESET=""
    INSTRUCTION=""
    declare -a SWITCHES=()
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --preset)
          PRESET="${2:-}"
          shift 2
          ;;
        --instruction)
          INSTRUCTION="${2:-}"
          shift 2
          ;;
        --switch)
          SWITCHES+=("${2:-}")
          shift 2
          ;;
        --help|-h)
          usage
          exit 0
          ;;
        *)
          echo "[redcap-e2e-session] unknown argument: $1" >&2
          usage
          exit 1
          ;;
      esac
    done

    if [[ -n "$PRESET" ]]; then
      while IFS= read -r item; do
        [[ -n "$item" ]] && SWITCHES+=("$item")
      done < <(preset_switches "$PRESET")
    fi

    if [[ ${#SWITCHES[@]} -eq 0 ]]; then
      echo "[redcap-e2e-session] start requires --preset or at least one --switch" >&2
      exit 1
    fi

    if [[ -z "$INSTRUCTION" ]]; then
      echo "[redcap-e2e-session] start requires --instruction" >&2
      exit 1
    fi

    write_session_file "${PRESET:-manual}" "$INSTRUCTION" "${SWITCHES[@]}"
    echo "E2E_SESSION_START_OK"
    show_status
    ;;
  mark)
    shift
    mark_switches "$@"
    show_status
    ;;
  status)
    show_status
    ;;
  clear)
    rm -f "$SESSION_FILE"
    echo "E2E_SESSION_CLEAR_OK"
    ;;
  --help|-h|help)
    usage
    ;;
  *)
    echo "[redcap-e2e-session] unknown command: $COMMAND" >&2
    usage
    exit 1
    ;;
esac

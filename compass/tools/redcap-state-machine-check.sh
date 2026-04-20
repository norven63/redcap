#!/usr/bin/env bash
# Validate that documented FSM states are accepted by state.yaml checks.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 - "$REDCAP_ROOT" <<'PY'
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
state_machine = root / "loom/dispatcher/state-machine.md"
check_state = root / "compass/tools/redcap-check-state.sh"
protocol = root / "references/communication-protocol.md"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-state-machine-check] {message}")


for path in (state_machine, check_state, protocol):
    if not path.is_file():
        fail(f"missing file: {path.relative_to(root)}")

state_text = state_machine.read_text(encoding="utf-8", errors="replace")
check_text = check_state.read_text(encoding="utf-8", errors="replace")
protocol_text = protocol.read_text(encoding="utf-8", errors="replace")

documented_states = set()
in_state_table = False
for line in state_text.splitlines():
    if line.startswith("## 1. 状态枚举"):
        in_state_table = True
        continue
    if in_state_table and line.startswith("## 2. "):
        break
    match = re.match(r"^\|\s*`([A-Z0-9_]+)`\s*\|", line)
    if match:
        documented_states.add(match.group(1))

if not documented_states:
    fail("no documented FSM states found")

valid_block = re.search(r"VALID_STATES\s*=\s*\{(.*?)\}", check_text, flags=re.S)
if not valid_block:
    fail("redcap-check-state.sh missing VALID_STATES set")
script_states = set(re.findall(r"'([A-Z0-9_]+)'", valid_block.group(1)))

missing = sorted(documented_states - script_states)
if missing:
    fail("documented states missing from redcap-check-state.sh: " + ", ".join(missing))

required_statuses = {"completed", "failed", "blocked", "need_user", "need_revision"}
missing_statuses = sorted(status for status in required_statuses if f"`{status}`" not in protocol_text)
if missing_statuses:
    fail("communication protocol missing status values: " + ", ".join(missing_statuses))

if "reload_config.on_session_revival" not in state_text:
    fail("state-machine event loop missing on_session_revival reload checkpoint")

print("STATE_MACHINE_CONTRACT_OK")
PY

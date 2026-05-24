#!/usr/bin/env bash
# 用途：Codex 生命周期 Hook 安全护栏；在高危工具调用前阻止明显破坏性动作。
# Dictionary: references/file-lookup-dictionary.md#skill-and-host-distribution

set -euo pipefail

INPUT="$(cat)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

json_field() {
    local field="$1"
    REDCAP_CODEX_HOOK_INPUT="$INPUT" python3 - "$field" <<'PY'
import json
import os
import sys

field = sys.argv[1]
try:
    payload = json.loads(os.environ.get("REDCAP_CODEX_HOOK_INPUT", "{}"))
except Exception:
    payload = {}
value = payload.get(field, "")
print(value if isinstance(value, str) else "")
PY
}

json_tool_command() {
    REDCAP_CODEX_HOOK_INPUT="$INPUT" python3 - <<'PY'
import json
import os

try:
    payload = json.loads(os.environ.get("REDCAP_CODEX_HOOK_INPUT", "{}"))
except Exception:
    payload = {}
tool_input = payload.get("tool_input") or {}
if isinstance(tool_input, dict):
    print(str(tool_input.get("command") or tool_input.get("cmd") or ""))
else:
    print("")
PY
}

DENY_REASON="$(
REDCAP_CODEX_HOOK_INPUT="$INPUT" python3 - <<'PY'
import json
import os
import re
import sys

try:
    payload = json.loads(os.environ.get("REDCAP_CODEX_HOOK_INPUT", "{}"))
except Exception:
    payload = {}

tool_name = str(payload.get("tool_name") or "")
tool_input = payload.get("tool_input") or {}
command = ""
if isinstance(tool_input, dict):
    command = str(tool_input.get("command") or tool_input.get("cmd") or "")

checks = [
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard is destructive and must not run under RedCap policy."),
    (r"\bgit\s+checkout\s+--\b", "git checkout -- can erase user changes and must not run without explicit recovery approval."),
    (r"\bprism-runs-lifecycle\.sh\b.*\bprune-local\b.*\b--apply\b", "Physical deletion of prism/runs evidence requires a separate explicit approval task."),
    (r"\brm\s+(-[^\s]*r[^\s]*f|-rf|-fr)\b.*\bprism/runs\b", "Direct removal of prism/runs evidence is blocked; use the reviewed lifecycle tool and approval flow."),
    (r"\bnpm\s+publish\b", "npm publish is blocked until the release task explicitly opens the publish gate."),
]

reason = ""
for pattern, message in checks:
    if re.search(pattern, command):
        reason = message
        break

if not reason:
    sys.exit(0)

print(reason)
PY
)"

if [[ -n "$DENY_REASON" ]]; then
    REDCAP_DENY_REASON="$DENY_REASON" python3 - <<'PY'
import json
import os

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": os.environ["REDCAP_DENY_REASON"],
    }
}, ensure_ascii=False))
PY
    exit 0
fi

TOOL_NAME="$(json_field tool_name)"
HOOK_CWD="$(json_field cwd)"
HOST_SESSION_ID="$(json_field session_id)"
COMMAND="$(json_tool_command)"

if [[ -z "$HOOK_CWD" ]]; then
    HOOK_CWD="$REDCAP_ROOT"
fi

SHOULD_CLAIM="$(
    REDCAP_TOOL_NAME="$TOOL_NAME" REDCAP_TOOL_COMMAND="$COMMAND" python3 - <<'PY'
import os
import re
import shlex

tool = os.environ.get("REDCAP_TOOL_NAME", "")
command = os.environ.get("REDCAP_TOOL_COMMAND", "")
mutating_tools = {"apply_patch", "Edit", "Write"}
mutating_commands = {"chmod", "mv", "rm", "rmdir", "cp", "mkdir", "touch"}
mutating_bash = False

def unwrap(parts):
    parts = list(parts)
    while parts and parts[0] in {"sudo", "command", "exec", "nohup", "noglob"}:
        parts = parts[1:]
    if parts and parts[0] == "env":
        parts = parts[1:]
        while parts and (parts[0].startswith("-") or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", parts[0])):
            parts = parts[1:]
    if parts and parts[0] in {"timeout", "gtimeout"}:
        parts = parts[1:]
        while parts and parts[0].startswith("-"):
            parts = parts[1:]
        if parts:
            parts = parts[1:]
    return parts

for segment in re.split(r"\s*(?:&&|\|\||;)\s*", command):
    try:
        parts = shlex.split(segment)
    except ValueError:
        parts = segment.split()
    parts = unwrap(parts)
    if not parts:
        continue
    head = parts[0]
    if head in mutating_commands:
        mutating_bash = True
        break
    if head == "git" and len(parts) > 1 and parts[1] in {"add", "commit", "mv", "rm"}:
        mutating_bash = True
        break
    if head == "sed" and any(part.startswith("-") and "i" in part and not part.startswith("--") for part in parts[1:]):
        mutating_bash = True
        break
    if head == "perl" and any(part.startswith("-") and "p" in part and "i" in part and not part.startswith("--") for part in parts[1:]):
        mutating_bash = True
        break
print("1" if tool in mutating_tools or mutating_bash else "0")
PY
)"

if [[ "$SHOULD_CLAIM" == "1" && -n "$HOST_SESSION_ID" ]]; then
    bash "$SCRIPT_DIR/redcap-codex-session-ownership.sh" claim \
        --root "$REDCAP_ROOT" \
        --task-file "$REDCAP_ROOT/.dev-task.md" \
        --host codex \
        --session-id "$HOST_SESSION_ID" \
        --intent execution \
        --reason "codex-pre-tool-use-mutating-tool:$TOOL_NAME" >/dev/null 2>&1 || true
fi

#!/usr/bin/env bash
# 用途：Codex 生命周期 Hook 安全护栏；在高危工具调用前阻止明显破坏性动作。
# Dictionary: references/file-lookup-dictionary.md#skill-and-host-distribution

set -euo pipefail

INPUT="$(cat)"

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

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }
}, ensure_ascii=False))
PY

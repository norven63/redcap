#!/usr/bin/env bash
# 用途：棱镜与 Agent 路由脚本；详细职责见文件查阅字典。

# Dictionary: references/file-lookup-dictionary.md#prism-and-providers
# Evaluate provider freeze windows before RedCap-owned CLI launchers start an Agent.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
POLICY_PATH="${REDCAP_PROVIDER_POLICY_FILE:-$REDCAP_ROOT/references/prism-provider-policy.json}"

usage() {
    cat <<'EOF' >&2
usage:
  redcap-provider-policy.sh is-frozen <agent> [scope]
  redcap-provider-policy.sh assert-not-frozen <agent> [scope]
EOF
}

command="${1:-}"
agent="${2:-}"
scope="${3:-direct-cli}"

if [[ -z "$command" || -z "$agent" ]]; then
    usage
    exit 2
fi

python3 - "$POLICY_PATH" "$command" "$agent" "$scope" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

policy_path, command, agent, scope = sys.argv[1:5]
path = Path(policy_path)

def fail(message, code=1):
    print(message, file=sys.stderr)
    raise SystemExit(code)

def parse_time(raw):
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        value = datetime.fromisoformat(text)
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

policy_unavailable = False
policy_unavailable_reason = ""
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except FileNotFoundError:
    payload = {}
    policy_unavailable = True
    policy_unavailable_reason = f"provider policy file missing: {path}"
except json.JSONDecodeError as exc:
    payload = {}
    policy_unavailable = True
    policy_unavailable_reason = f"invalid provider policy json: {exc}"

freeze_sensitive_agents = {"copilot"}
if policy_unavailable and agent in freeze_sensitive_agents:
    if command == "is-frozen":
        print(json.dumps({
            "agent": agent,
            "scope": scope,
            "status": "policy-unavailable",
            "reason": policy_unavailable_reason,
            "until": "",
        }, ensure_ascii=False))
        raise SystemExit(0)
    if command == "assert-not-frozen":
        fail(f"[redcap-provider-policy] {policy_unavailable_reason}; refusing frozen-sensitive provider: {agent}", 18)

now = datetime.now(timezone.utc)
matched = None
for item in payload.get("freeze_windows", []) or []:
    if not isinstance(item, dict) or item.get("agent") != agent:
        continue
    scopes = item.get("scope", [])
    if isinstance(scopes, list) and scope not in scopes and "all" not in scopes:
        continue
    starts_at = parse_time(item.get("starts_at"))
    until = parse_time(item.get("until"))
    if starts_at is not None and now < starts_at:
        continue
    if until is not None and now >= until:
        continue
    matched = item
    break

if command == "is-frozen":
    if matched is None:
        raise SystemExit(1)
    print(json.dumps({
        "agent": agent,
        "scope": scope,
        "status": "frozen",
        "reason": matched.get("reason", "provider frozen by policy"),
        "until": matched.get("until", ""),
    }, ensure_ascii=False))
    raise SystemExit(0)

if command == "assert-not-frozen":
    if matched is None:
        print("PROVIDER_ALLOWED")
        raise SystemExit(0)
    fail(
        f"[redcap-provider-policy] provider frozen: agent={agent} scope={scope} "
        f"until={matched.get('until', '')} reason={matched.get('reason', 'provider frozen by policy')}",
        17,
    )

fail(f"[redcap-provider-policy] unsupported command: {command}", 2)
PY

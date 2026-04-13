#!/usr/bin/env bash
# shellcheck shell=bash
# Decide Layer B isolation mode from host capability matrix.

set -euo pipefail

HOST="${1:-}"

if [[ -z "$HOST" ]]; then
    echo "[redcap-session-resume-gate] ERROR: host is required" >&2
    exit 2
fi

INPUT=$(cat)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/redcap-runtime-state.sh"

HOST_SESSION_ID="${REDCAP_HOST_SESSION_ID:-$(redcap_runtime_json_field "$INPUT" "session_id")}"
EXPLICIT_BINDING_KEY="${REDCAP_SESSION_BINDING_KEY:-}"
MATRIX_PATH="${REDCAP_HOST_SESSION_CAPABILITY_MATRIX_PATH:-$REDCAP_ROOT/references/host-session-capability-matrix.json}"

python3 - "$HOST" "$HOST_SESSION_ID" "$EXPLICIT_BINDING_KEY" "$MATRIX_PATH" <<'PY'
import json
import sys
from pathlib import Path

host = sys.argv[1].strip()
host_session_id = sys.argv[2].strip()
explicit_binding_key = sys.argv[3].strip()
matrix_path = Path(sys.argv[4]).resolve()

try:
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
except FileNotFoundError as exc:
    raise SystemExit(f"[redcap-session-resume-gate] matrix not found: {matrix_path}") from exc
except json.JSONDecodeError as exc:
    raise SystemExit(f"[redcap-session-resume-gate] invalid matrix json: {matrix_path}") from exc
default = dict(matrix.get("default", {}))
profile = dict(default)
profile.update(matrix.get("hosts", {}).get(host, {}))

support_status = profile.get("support_status", "unsupported")
allow_safe_degraded = bool(profile.get("allow_safe_degraded", False))
allow_explicit_binding_key = bool(profile.get("allow_explicit_binding_key", False))
allow_host_session_id_binding = bool(profile.get("allow_host_session_id_binding", False))
missing_identity_mode = profile.get("missing_identity_mode", "unsupported")
profile_name = profile.get("profile", "unsupported-host")

mode = "unsupported"
reason = "unsupported-host"
identity_source = "none"
recovery_path = "unsupported"
binding_key = ""
allow_disk_recovery = "0"
allow_capability_file_recovery = "0"
evidence = ["capability-matrix"]

if support_status == "supported":
    if explicit_binding_key:
        if allow_explicit_binding_key:
            mode = "full"
            reason = "explicit-binding-key"
            identity_source = "explicit-binding-key"
            recovery_path = "runtime-binding-attach-or-create"
            binding_key = explicit_binding_key
            allow_disk_recovery = "1"
            allow_capability_file_recovery = "1"
            evidence.append("explicit-binding-key")
        elif allow_safe_degraded:
            mode = "degraded"
            reason = "explicit-binding-key-not-supported"
            identity_source = "explicit-binding-key"
            recovery_path = "safe-degraded"
            evidence.append("explicit-binding-key")
        else:
            reason = "explicit-binding-key-not-supported"
            identity_source = "explicit-binding-key"
            evidence.append("explicit-binding-key")
    elif host_session_id:
        if allow_host_session_id_binding:
            mode = "full"
            reason = "host-session-id-derived-binding"
            identity_source = "host-session-id"
            recovery_path = "runtime-binding-attach-or-create"
            binding_key = f"host/{host}/session/{host_session_id}"
            allow_disk_recovery = "1"
            allow_capability_file_recovery = "1"
            evidence.append("host-session-id")
        elif allow_safe_degraded:
            mode = missing_identity_mode
            reason = "host-session-id-not-usable-on-sessionstart"
            identity_source = "host-session-id"
            recovery_path = "safe-degraded"
            evidence.append("host-session-id")
        else:
            reason = "host-session-id-not-usable-on-sessionstart"
            identity_source = "host-session-id"
            evidence.append("host-session-id")
    elif allow_safe_degraded:
        mode = missing_identity_mode
        reason = "missing-host-session-id"
        recovery_path = "safe-degraded"
    else:
        reason = "missing-host-session-id"

payload = {
    "REDCAP_SESSION_ISOLATION_MODE": mode,
    "REDCAP_SESSION_RESUME_REASON": reason,
    "REDCAP_SESSION_RESUME_PROFILE": profile_name,
    "REDCAP_SESSION_RESUME_EVIDENCE": ",".join(evidence),
    "REDCAP_SESSION_RESUME_IDENTITY_SOURCE": identity_source,
    "REDCAP_SESSION_RESUME_RECOVERY_PATH": recovery_path,
    "REDCAP_SESSION_RESUME_ALLOW_DISK_RECOVERY": allow_disk_recovery,
    "REDCAP_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY": allow_capability_file_recovery,
    "REDCAP_SESSION_BINDING_KEY": binding_key,
    "REDCAP_HOST_SESSION_ID": host_session_id,
    "REDCAP_SESSION_CAPABILITY_SUPPORT": support_status,
}

for key, value in payload.items():
    print(f"{key}={value}")
PY

#!/usr/bin/env bash
# 用途：Codex 生命周期 Hook 真实触发探针；用安全 marker 证明本机 Codex CLI 是否物理执行 SessionStart/Stop。
# Dictionary: references/file-lookup-dictionary.md#skill-and-host-distribution

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESULT_PATH="${REDCAP_CODEX_LIVE_MARKER_E2E_RESULT:-$REDCAP_ROOT/references/codex-live-marker-e2e.json}"

usage() {
    cat <<'EOF'
usage:
  bash compass/tools/redcap-codex-live-marker-e2e.sh --run
  bash compass/tools/redcap-codex-live-marker-e2e.sh --check-result
  bash compass/tools/redcap-codex-live-marker-e2e.sh --self-test

--run          Launch a minimal local `codex exec` probe and write sanitized result evidence.
--check-result Validate references/codex-live-marker-e2e.json when it exists.
--self-test    Validate checker behavior with temporary pass/fail fixtures; does not call Codex.
EOF
}

json_write_result() {
    local output_path="$1"
    local passed="$2"
    local reason="$3"
    local command_exit_code="$4"
    local codex_path="$5"
    local codex_version="$6"
    local feature_state="$7"
    local source_head="$8"
    local session_start_marker="$9"
    local stop_marker="${10}"

    REDCAP_RESULT_PATH="$output_path" \
    REDCAP_E2E_PASSED="$passed" \
    REDCAP_E2E_REASON="$reason" \
    REDCAP_E2E_COMMAND_EXIT_CODE="$command_exit_code" \
    REDCAP_E2E_CODEX_PATH="$codex_path" \
    REDCAP_E2E_CODEX_VERSION="$codex_version" \
    REDCAP_E2E_FEATURE_STATE="$feature_state" \
    REDCAP_E2E_SOURCE_HEAD="$source_head" \
    REDCAP_E2E_SESSION_START_MARKER="$session_start_marker" \
    REDCAP_E2E_STOP_MARKER="$stop_marker" \
        python3 - <<'PY'
import json
import os
import pathlib
from datetime import datetime, timezone

def as_bool(value: str) -> bool:
    return value.lower() == "true"

def load_marker(raw: str) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}

path = pathlib.Path(os.environ["REDCAP_RESULT_PATH"])
path.parent.mkdir(parents=True, exist_ok=True)
data = {
    "version": 1,
    "manifest_id": "redcap-codex-live-marker-e2e",
    "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "host": "codex",
    "surface": "codex-cli-exec",
    "scope": "local-machine-evidence",
    "codex_cli_live_marker_e2e_passed": as_bool(os.environ.get("REDCAP_E2E_PASSED", "false")),
    "reason": os.environ.get("REDCAP_E2E_REASON", ""),
    "command_exit_code": int(os.environ.get("REDCAP_E2E_COMMAND_EXIT_CODE", "0") or "0"),
    "codex_binary_observed": bool(os.environ.get("REDCAP_E2E_CODEX_PATH", "")),
    "codex_version": os.environ.get("REDCAP_E2E_CODEX_VERSION", ""),
    "codex_hooks_feature": os.environ.get("REDCAP_E2E_FEATURE_STATE", ""),
    "source_head": os.environ.get("REDCAP_E2E_SOURCE_HEAD", ""),
    "markers": {
        "session_start": load_marker(os.environ.get("REDCAP_E2E_SESSION_START_MARKER", "")),
        "stop": load_marker(os.environ.get("REDCAP_E2E_STOP_MARKER", "")),
    },
    "privacy": {
        "local_paths_redacted": True,
        "prompt_content_recorded": False,
        "model_output_recorded": False
    },
    "boundary": "This proves local Codex CLI lifecycle hook firing only; Codex.app interactive hook behavior must not be claimed unless separately observed."
}
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

check_result_file() {
    local result_path="${1:-$RESULT_PATH}"

    python3 - "$result_path" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
if not path.exists():
    print("CODEX_LIVE_MARKER_E2E_RESULT_ABSENT")
    raise SystemExit(0)

try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception as exc:
    raise SystemExit(f"[redcap-codex-live-marker-e2e] invalid result json: {exc}")

def fail(message: str) -> None:
    raise SystemExit(f"[redcap-codex-live-marker-e2e] {message}")

if data.get("version") != 1:
    fail("result version must be 1")
if data.get("manifest_id") != "redcap-codex-live-marker-e2e":
    fail("unexpected manifest_id")
if data.get("host") != "codex":
    fail("host must be codex")
if data.get("surface") != "codex-cli-exec":
    fail("surface must be codex-cli-exec")
if data.get("codex_cli_live_marker_e2e_passed") is not True:
    fail("last live marker E2E did not pass")

markers = data.get("markers")
if not isinstance(markers, dict):
    fail("markers must be an object")
session_start = markers.get("session_start")
stop = markers.get("stop")
if not isinstance(session_start, dict) or session_start.get("event") != "SessionStart":
    fail("missing SessionStart marker")
if not isinstance(stop, dict) or stop.get("event") != "Stop":
    fail("missing Stop marker")
for label, marker in [("SessionStart", session_start), ("Stop", stop)]:
    if marker.get("host") != "codex":
        fail(f"{label} marker host must be codex")
    if marker.get("status") != 0:
        fail(f"{label} marker status must be 0")

privacy = data.get("privacy")
if not isinstance(privacy, dict) or privacy.get("local_paths_redacted") is not True:
    fail("result must declare local path redaction")
if "/" in json.dumps(data.get("markers", {}), ensure_ascii=False):
    fail("marker evidence must not embed local filesystem paths")

print("CODEX_LIVE_MARKER_E2E_RESULT_OK")
PY
}

run_live_probe() {
    local codex_path=""
    local codex_version=""
    local feature_output=""
    local feature_state="unknown"
    local source_head=""
    local marker_dir=""
    local last_message=""
    local stdout_log=""
    local status=0
    local passed="false"
    local reason=""
    local session_start_marker=""
    local stop_marker=""

    codex_path="$(command -v codex || true)"
    if [[ -z "$codex_path" ]]; then
        json_write_result "$RESULT_PATH" false "codex binary not found" 127 "" "" "missing" "" "" ""
        echo "CODEX_LIVE_MARKER_E2E_FAIL result=$RESULT_PATH reason=codex-binary-not-found"
        exit 1
    fi

    codex_version="$(codex --version 2>/dev/null | tr '\n' ' ' | sed 's/[[:space:]]*$//' || true)"
    feature_output="$(codex features list 2>/dev/null || true)"
    if printf '%s\n' "$feature_output" | grep -Eq '^codex_hooks[[:space:]]+[^[:space:]]+[[:space:]]+true$'; then
        feature_state="true"
    elif printf '%s\n' "$feature_output" | grep -q '^codex_hooks'; then
        feature_state="false"
    fi

    source_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD 2>/dev/null || true)"
    marker_dir="$(mktemp -d "${TMPDIR:-/tmp}/redcap-codex-live-marker.XXXXXX")"
    last_message="$(mktemp "${TMPDIR:-/tmp}/redcap-codex-live-marker-message.XXXXXX")"
    stdout_log="$(mktemp "${TMPDIR:-/tmp}/redcap-codex-live-marker-stdout.XXXXXX")"

    set +e
    REDCAP_CODEX_HOOK_MARKER_DIR="$marker_dir" \
    REDCAP_CODEX_HOOK_E2E_PROBE=1 \
    REDCAP_SKIP_FEISHU=1 \
        codex exec \
            -C "$REDCAP_ROOT" \
            --sandbox read-only \
            --ephemeral \
            --enable codex_hooks \
            -o "$last_message" \
            "Reply exactly REDCAP_CODEX_LIVE_MARKER_E2E_OK. Do not run tools." \
            >"$stdout_log" 2>&1
    status=$?
    set -e

    if [[ -f "$marker_dir/session-start.json" ]]; then
        session_start_marker="$(tr -d '\n' <"$marker_dir/session-start.json")"
    fi
    if [[ -f "$marker_dir/stop.json" ]]; then
        stop_marker="$(tr -d '\n' <"$marker_dir/stop.json")"
    fi

    if [[ "$status" -eq 0 && -n "$session_start_marker" && -n "$stop_marker" ]]; then
        passed="true"
        reason="local Codex CLI invoked SessionStart and Stop hooks and both wrappers wrote marker evidence"
    else
        reason="Codex CLI probe did not produce both lifecycle markers"
    fi

    json_write_result "$RESULT_PATH" "$passed" "$reason" "$status" "$codex_path" "$codex_version" "$feature_state" "$source_head" "$session_start_marker" "$stop_marker"
    rm -rf "$marker_dir" "$last_message" "$stdout_log" 2>/dev/null || true

    if [[ "$passed" == "true" ]]; then
        echo "CODEX_LIVE_MARKER_E2E_OK result=$RESULT_PATH"
    else
        echo "CODEX_LIVE_MARKER_E2E_FAIL result=$RESULT_PATH"
        exit 1
    fi
}

self_test() {
    local temp_dir pass_file fail_file

    temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/redcap-codex-live-marker-selftest.XXXXXX")"
    pass_file="$temp_dir/pass.json"
    fail_file="$temp_dir/fail.json"

    json_write_result "$pass_file" true "self-test pass" 0 "/tmp/codex" "codex-cli self-test" "true" "HEAD" '{"event":"SessionStart","status":0,"host":"codex"}' '{"event":"Stop","status":0,"host":"codex"}'
    check_result_file "$pass_file" >/dev/null

    json_write_result "$fail_file" false "self-test fail" 1 "/tmp/codex" "codex-cli self-test" "true" "HEAD" '{"event":"SessionStart","status":0,"host":"codex"}' ''
    if check_result_file "$fail_file" >/dev/null 2>&1; then
        rm -rf "$temp_dir"
        echo "[redcap-codex-live-marker-e2e] failing fixture unexpectedly passed" >&2
        exit 1
    fi

    rm -rf "$temp_dir"
    echo "CODEX_LIVE_MARKER_E2E_SELF_TEST_OK"
}

case "${1:-}" in
    --run)
        run_live_probe
        ;;
    --check-result)
        check_result_file "$RESULT_PATH"
        ;;
    --self-test)
        self_test
        ;;
    -h|--help|"")
        usage
        ;;
    *)
        echo "[redcap-codex-live-marker-e2e] unknown argument: $1" >&2
        usage >&2
        exit 2
        ;;
esac

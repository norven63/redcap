#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/redcap-runtime-state.sh"
source "$SCRIPT_DIR/redcap-interop-governance.sh"
source "$SCRIPT_DIR/redcap-dev-task.sh"
redcap_runtime_clear_context
unset REDCAP_RUNTIME_ALLOW_DISK_RECOVERY REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY REDCAP_RUNTIME_CAPABILITY 2>/dev/null || true

ACCEPT_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/redcap-acceptance.XXXXXX")"
export REDCAP_RUNTIME_BASE_DIR="$ACCEPT_ROOT/runtime"
export REDCAP_RUNTIME_INDEX_DIR="$ACCEPT_ROOT/runtime-index"
export REDCAP_RUNTIME_PROJECT_BASE_DIR="$ACCEPT_ROOT/project"
export REDCAP_RUNTIME_PROCESS_CLAIM_DIR="$ACCEPT_ROOT/process-claims"
CONTINUITY_CORE_DIR="$ACCEPT_ROOT/continuity-core"

LEGACY_REGISTRY_FILE="$REDCAP_ROOT/prism/reports/.session-registry.yaml"
LEGACY_REGISTRY_BACKUP=""
TEMP_PROJECTS=()
LEGACY_TMP_FILES=()
HOST_PROCESS_PROBES=()

cleanup() {
    local path

    for path in "${LEGACY_TMP_FILES[@]:-}"; do
        rm -f "$path" 2>/dev/null || true
    done

    if [[ -n "$LEGACY_REGISTRY_BACKUP" && -f "$LEGACY_REGISTRY_BACKUP" ]]; then
        mv -f "$LEGACY_REGISTRY_BACKUP" "$LEGACY_REGISTRY_FILE" 2>/dev/null || true
    else
        rm -f "$LEGACY_REGISTRY_FILE" 2>/dev/null || true
    fi

    for path in "${TEMP_PROJECTS[@]:-}"; do
        rm -rf "$path" 2>/dev/null || true
    done

    for path in "${HOST_PROCESS_PROBES[@]:-}"; do
        kill "$path" 2>/dev/null || true
        wait "$path" 2>/dev/null || true
    done

    rm -rf "$ACCEPT_ROOT" 2>/dev/null || true
}

trap cleanup EXIT

usage() {
    cat <<'EOF' >&2
usage:
  bash compass/tools/redcap-multi-session-acceptance.sh all
  bash compass/tools/redcap-multi-session-acceptance.sh binding-recovery-gate
  bash compass/tools/redcap-multi-session-acceptance.sh layerb-concurrency
  bash compass/tools/redcap-multi-session-acceptance.sh copilot-safe-degraded
  bash compass/tools/redcap-multi-session-acceptance.sh cross-layer-visibility
  bash compass/tools/redcap-multi-session-acceptance.sh layera-legacy-quarantine
  bash compass/tools/redcap-multi-session-acceptance.sh prism-concurrency
  bash compass/tools/redcap-multi-session-acceptance.sh prism-legacy-bridge
  bash compass/tools/redcap-multi-session-acceptance.sh report-register-requires-claim
  bash compass/tools/redcap-multi-session-acceptance.sh sessionstart-auto-reconcile-rewrite
  bash compass/tools/redcap-multi-session-acceptance.sh sessionstart-auto-reconcile-clear
  bash compass/tools/redcap-multi-session-acceptance.sh sessionstart-auto-reconcile-hash-mismatch
  bash compass/tools/redcap-multi-session-acceptance.sh sessionstart-runtime-init-failed-degrades
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-manifest-sync
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-runtime-required
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-runtime-claim-requires-live-process
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-manifest-only-discovery
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-discovery-requires-source-metadata
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-manifest-import
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-cross-host-import
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-manifest-mismatch
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-stale-import
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-stale-import-requires-source-metadata
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-rejects-stale-source-manifest
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-import-requires-source-manifest
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-import-requires-source-metadata
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-import-requires-target-manifest
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-import-rejects-foreign-runtime
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-import-rejects-target-runtime-mismatch
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-import-rejects-relay-source
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-import-rejects-imported-own-record-source
  bash compass/tools/redcap-multi-session-acceptance.sh continuity-import-resolves-live-manifest
  bash compass/tools/redcap-multi-session-acceptance.sh session-resume-gate-claude-full
  bash compass/tools/redcap-multi-session-acceptance.sh session-resume-gate-gemini-full
  bash compass/tools/redcap-multi-session-acceptance.sh session-resume-gate-copilot-full
  bash compass/tools/redcap-multi-session-acceptance.sh session-resume-gate-error-safe-fail
  bash compass/tools/redcap-multi-session-acceptance.sh session-resume-gate-unsupported-host
EOF
}

log() {
    printf '[redcap-multi-session-acceptance] %s\n' "$1" >&2
}

fail() {
    printf '[redcap-multi-session-acceptance] ERROR: %s\n' "$1" >&2
    exit 1
}

assert_exists() {
    [[ -e "$1" ]] || fail "expected path to exist: $1"
}

assert_not_exists() {
    [[ ! -e "$1" ]] || fail "expected path to be absent: $1"
}

assert_eq() {
    [[ "$1" == "$2" ]] || fail "expected '$1' == '$2'"
}

assert_contains() {
    grep -Fq -- "$2" "$1" || fail "expected '$1' to contain '$2'"
}

assert_string_contains() {
    [[ "$1" == *"$2"* ]] || fail "expected '$1' to contain '$2'"
}

assert_ne() {
    [[ "$1" != "$2" ]] || fail "expected '$1' != '$2'"
}

assert_num_eq() {
    [[ "$1" =~ ^[0-9]+$ ]] || fail "expected numeric value, got: $1"
    [[ "$2" =~ ^[0-9]+$ ]] || fail "expected numeric value, got: $2"
    [[ "$1" -eq "$2" ]] || fail "expected $1 -eq $2"
}

normalize_csv() {
    local value="${1:-}"

    printf '%s' "$value" | tr ',' '\n' | sed '/^[[:space:]]*$/d' | sort | paste -sd',' -
}

counter_value() {
    local path="$1"
    if [[ -f "$path" ]]; then
        cat "$path"
    else
        printf '0\n'
    fi
}

attach_binding_with_capability_recovery() {
    local host="$1"
    local project_root="$2"
    local binding_key="$3"
    local host_process_pid="$4"
    local host_process_probe_pid="${5:-}"
    local status=0

    set +e
    REDCAP_HOST_PROCESS_PID="$host_process_pid" \
    REDCAP_HOST_PROCESS_PROBE_PID="$host_process_probe_pid" \
    REDCAP_RUNTIME_ALLOW_DISK_RECOVERY=1 \
    REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY=1 \
    redcap_runtime_load_from_binding "$host" "$project_root" "$binding_key"
    status=$?
    set -e
    unset REDCAP_HOST_PROCESS_PID REDCAP_HOST_PROCESS_PROBE_PID REDCAP_RUNTIME_ALLOW_DISK_RECOVERY REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY
    return "$status"
}

read_file_text() {
    local path="$1"
    [[ -f "$path" ]] || fail "expected file to exist: $path"
    cat "$path"
}

manifest_value() {
    local path="$1"
    local key="$2"

    python3 - "$path" "$key" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
key = sys.argv[2]
for raw in path.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or ":" not in line:
        continue
    current_key, value = line.split(":", 1)
    if current_key.strip() != key:
        continue
    value = value.strip()
    try:
        parsed = json.loads(value)
    except Exception:
        parsed = value
    print(parsed if isinstance(parsed, str) else json.dumps(parsed, ensure_ascii=False))
    break
PY
}

workboard_value() {
    local path="$1"
    local key="$2"

    python3 - "$path" "$key" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
key = sys.argv[2]
text = path.read_text(encoding="utf-8")
match = re.search(
    r"<!-- redcap:session-mirror:start -->(.*?)<!-- redcap:session-mirror:end -->",
    text,
    re.S,
)
if not match:
    raise SystemExit(0)
for raw in match.group(1).splitlines():
    line = raw.strip()
    if line.startswith(f"- {key}: "):
        print(line.split(": ", 1)[1].strip())
        break
PY
}

extract_output_value() {
    local output="$1"
    local key="$2"

    printf '%s\n' "$output" | sed -n "s/^${key}=//p" | head -1
}

git_previous_head() {
    git -C "$REDCAP_ROOT" rev-parse HEAD~1 2>/dev/null || git -C "$REDCAP_ROOT" rev-parse HEAD
}

repo_has_tracked_drift() {
    [[ -n "$(git -C "$REDCAP_ROOT" status --short --untracked-files=no)" ]]
}

make_temp_project() {
    local dir
    dir="$(mktemp -d "${TMPDIR:-/tmp}/redcap-layera-project.XXXXXX")"
    TEMP_PROJECTS+=("$dir")
    printf '%s\n' "$dir"
}

write_workboard_fixture() {
    local path="$1"
    local task_file="$2"
    local task_id="$3"
    local top_goal="$4"
    local active_slice="$5"
    local confirmed_hash="$6"

    mkdir -p "$(dirname "$path")"
    cat >"$path" <<EOF
# Continuity fixture

<!-- redcap:canonical-pointer:start -->
## RedCap Canonical Pointer
- task_id: $task_id
- canonical_path: $task_file
- source_of_truth: .dev-task.md
- top_goal: $top_goal
- active_slice: $active_slice
- subtask_of: $task_id
- confirmed_hash: $confirmed_hash
- host_surface_policy: mirror_only
<!-- redcap:canonical-pointer:end -->
EOF
}

spawn_host_probe() {
    local probe_pid

    sleep 600 >/dev/null 2>&1 &
    probe_pid=$!
    HOST_PROCESS_PROBES+=("$probe_pid")
    printf '%s\n' "$probe_pid"
}

init_bound_runtime() {
    local host="$1"
    local binding_key="$2"
    local host_process_pid="$3"
    local probe_pid

    probe_pid="$(spawn_host_probe)"

    REDCAP_HOST_PROCESS_PID="$host_process_pid" REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid" redcap_runtime_init_from_binding "$host" "$REDCAP_ROOT" "$binding_key" >/dev/null \
        || fail "failed to initialize runtime binding for $host"
    REDCAP_HOST_PROCESS_PID="$host_process_pid"
    REDCAP_SESSION_ISOLATION_MODE="full"
    export REDCAP_HOST_PROCESS_PID REDCAP_SESSION_ISOLATION_MODE REDCAP_RUNTIME_SESSION_ID REDCAP_RUNTIME_BINDING_KEY REDCAP_RUNTIME_HOST REDCAP_RUNTIME_CAPABILITY
    unset REDCAP_HOST_PROCESS_PROBE_PID
}

run_host_session_resume_full_case() {
    local host="$1"
    local profile="$2"
    local case_name="$3"
    local case_root case_core workboard confirmed_hash
    local session_id runtime_id manifest binding_key

    log "case: $case_name"

    case_root="$ACCEPT_ROOT/$case_name"
    case_core="$CONTINUITY_CORE_DIR/$case_name"
    workboard="$case_root/plan.md"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"

    write_workboard_fixture \
        "$workboard" \
        "$REDCAP_ROOT/.dev-task.md" \
        "framework-upgrade-backlog-review" \
        "acceptance session resume gate" \
        "tranche-1-session-resume-gate-capability-matrix" \
        "$confirmed_hash"

    session_id="acceptance-${host}-session-${RANDOM}-$$"
    printf '{"session_id":"%s","cwd":"%s"}\n' "$session_id" "$REDCAP_ROOT" | \
        REDCAP_HOOK_CWD="$REDCAP_ROOT" \
        REDCAP_HOST_WORKBOARD_PATH="$workboard" \
        REDCAP_CONTINUITY_ROOT_DIR="$case_core" \
        REDCAP_HOST_PROCESS_PID="$$" \
        bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$host" >/dev/null

    assert_eq "$(workboard_value "$workboard" "isolation_mode")" "full"
    assert_eq "$(workboard_value "$workboard" "resume_gate_reason")" "host-session-id-derived-binding"
    assert_eq "$(workboard_value "$workboard" "resume_gate_profile")" "$profile"
    assert_eq "$(workboard_value "$workboard" "resume_gate_evidence")" "capability-matrix,host-session-id"
    assert_eq "$(workboard_value "$workboard" "continuity_state")" "fresh-session"

    binding_key="$(workboard_value "$workboard" "session_binding_key")"
    assert_eq "$binding_key" "$(redcap_runtime_binding_key_from_host_session "$host" "$session_id")"

    runtime_id="$(workboard_value "$workboard" "runtime_session_id")"
    [[ -n "$runtime_id" && "$runtime_id" != "unknown" ]] || fail "expected runtime session id for $case_name"

    manifest="$case_core/sessions/$runtime_id/manifest.yaml"
    assert_exists "$manifest"
    assert_eq "$(manifest_value "$manifest" "isolation_mode")" "full"
    assert_eq "$(manifest_value "$manifest" "resume_gate_reason")" "host-session-id-derived-binding"
    assert_eq "$(manifest_value "$manifest" "resume_gate_profile")" "$profile"
    assert_eq "$(manifest_value "$manifest" "resume_gate_evidence")" "capability-matrix,host-session-id"
}

run_session_resume_gate_claude_full_case() {
    run_host_session_resume_full_case "claude" "claude-sessionstart-host-session" "session-resume-gate-claude-full"
}

run_session_resume_gate_gemini_full_case() {
    run_host_session_resume_full_case "gemini" "gemini-sessionstart-host-session" "session-resume-gate-gemini-full"
}

run_session_resume_gate_copilot_full_case() {
    local host="copilot"
    local case_name="session-resume-gate-copilot-full"
    local case_root case_core workboard confirmed_hash
    local binding_key runtime_id manifest

    log "case: $case_name"

    case_root="$ACCEPT_ROOT/$case_name"
    case_core="$CONTINUITY_CORE_DIR/$case_name"
    workboard="$case_root/plan.md"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    binding_key="acceptance-copilot-full-${RANDOM}-$$"

    write_workboard_fixture \
        "$workboard" \
        "$REDCAP_ROOT/.dev-task.md" \
        "framework-upgrade-backlog-review" \
        "acceptance session resume gate" \
        "tranche-1-session-resume-gate-capability-matrix" \
        "$confirmed_hash"

    printf '{}' | \
        REDCAP_HOOK_CWD="$REDCAP_ROOT" \
        REDCAP_HOST_WORKBOARD_PATH="$workboard" \
        REDCAP_CONTINUITY_ROOT_DIR="$case_core" \
        REDCAP_HOST_PROCESS_PID="$$" \
        REDCAP_SESSION_BINDING_KEY="$binding_key" \
        bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$host" >/dev/null

    assert_eq "$(workboard_value "$workboard" "isolation_mode")" "full"
    assert_eq "$(workboard_value "$workboard" "resume_gate_reason")" "explicit-binding-key"
    assert_eq "$(workboard_value "$workboard" "resume_gate_profile")" "copilot-sessionstart-wrapper-required"
    assert_eq "$(workboard_value "$workboard" "resume_gate_evidence")" "capability-matrix,explicit-binding-key"
    assert_eq "$(workboard_value "$workboard" "session_binding_key")" "$binding_key"

    runtime_id="$(workboard_value "$workboard" "runtime_session_id")"
    [[ -n "$runtime_id" && "$runtime_id" != "unknown" ]] || fail "expected runtime session id for $case_name"

    manifest="$case_core/sessions/$runtime_id/manifest.yaml"
    assert_exists "$manifest"
    assert_eq "$(manifest_value "$manifest" "isolation_mode")" "full"
    assert_eq "$(manifest_value "$manifest" "resume_gate_reason")" "explicit-binding-key"
    assert_eq "$(manifest_value "$manifest" "resume_gate_profile")" "copilot-sessionstart-wrapper-required"
    assert_eq "$(manifest_value "$manifest" "resume_gate_evidence")" "capability-matrix,explicit-binding-key"
}

run_session_resume_gate_unsupported_host_case() {
    local host="unsupported-host"
    local case_name="session-resume-gate-unsupported-host"
    local case_root case_core workboard confirmed_hash
    local unsupported_file before after

    log "case: $case_name"

    case_root="$ACCEPT_ROOT/$case_name"
    case_core="$CONTINUITY_CORE_DIR/$case_name"
    workboard="$case_root/plan.md"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    unsupported_file="$(redcap_runtime_compat_path_for_root "$REDCAP_ROOT" "unsupported-mode.count")"
    before="$(counter_value "$unsupported_file")"

    write_workboard_fixture \
        "$workboard" \
        "$REDCAP_ROOT/.dev-task.md" \
        "framework-upgrade-backlog-review" \
        "acceptance session resume gate" \
        "tranche-1-session-resume-gate-capability-matrix" \
        "$confirmed_hash"

    printf '{}' | \
        REDCAP_HOOK_CWD="$REDCAP_ROOT" \
        REDCAP_HOST_WORKBOARD_PATH="$workboard" \
        REDCAP_CONTINUITY_ROOT_DIR="$case_core" \
        REDCAP_HOST_PROCESS_PID="$$" \
        bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$host" >/dev/null

    after="$(counter_value "$unsupported_file")"
    assert_num_eq "$after" $((before + 1))
    assert_eq "$(workboard_value "$workboard" "isolation_mode")" "unsupported"
    assert_eq "$(workboard_value "$workboard" "resume_gate_reason")" "unsupported-host"
    assert_eq "$(workboard_value "$workboard" "resume_gate_profile")" "unsupported-host"
    assert_eq "$(workboard_value "$workboard" "resume_gate_evidence")" "capability-matrix"
    assert_eq "$(workboard_value "$workboard" "runtime_session_id")" "unknown"
    assert_eq "$(workboard_value "$workboard" "continuity_state")" "fresh-session"
    assert_eq "$(workboard_value "$workboard" "continuity_authority")" "degraded-no-runtime-manifest"
    assert_not_exists "$case_core/sessions"
}

run_session_resume_gate_error_safe_fail_case() {
    local host="copilot"
    local case_name="session-resume-gate-error-safe-fail"
    local case_root case_core workboard confirmed_hash
    local binding_key unsupported_file before after

    log "case: $case_name"

    case_root="$ACCEPT_ROOT/$case_name"
    case_core="$CONTINUITY_CORE_DIR/$case_name"
    workboard="$case_root/plan.md"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    binding_key="acceptance-gate-error-${RANDOM}-$$"
    unsupported_file="$(redcap_runtime_compat_path_for_root "$REDCAP_ROOT" "unsupported-mode.count")"
    before="$(counter_value "$unsupported_file")"

    write_workboard_fixture \
        "$workboard" \
        "$REDCAP_ROOT/.dev-task.md" \
        "framework-upgrade-backlog-review" \
        "acceptance session resume gate" \
        "tranche-1-session-resume-gate-capability-matrix" \
        "$confirmed_hash"

    printf '{}' | \
        REDCAP_HOOK_CWD="$REDCAP_ROOT" \
        REDCAP_HOST_WORKBOARD_PATH="$workboard" \
        REDCAP_CONTINUITY_ROOT_DIR="$case_core" \
        REDCAP_HOST_PROCESS_PID="$$" \
        REDCAP_SESSION_BINDING_KEY="$binding_key" \
        REDCAP_HOST_SESSION_CAPABILITY_MATRIX_PATH="$case_root/missing-matrix.json" \
        bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$host" >/dev/null

    after="$(counter_value "$unsupported_file")"
    assert_num_eq "$after" $((before + 1))
    assert_eq "$(workboard_value "$workboard" "isolation_mode")" "unsupported"
    assert_eq "$(workboard_value "$workboard" "resume_gate_reason")" "resume-gate-error"
    assert_eq "$(workboard_value "$workboard" "resume_gate_profile")" "resume-gate-error"
    assert_eq "$(workboard_value "$workboard" "runtime_session_id")" "unknown"
    assert_eq "$(workboard_value "$workboard" "session_binding_key")" "$binding_key"
    assert_eq "$(workboard_value "$workboard" "continuity_authority")" "degraded-no-runtime-manifest"
    assert_not_exists "$case_core/sessions"
}

run_binding_recovery_gate_case() {
    local host="claude"
    local binding_key="acceptance-binding-${RANDOM}-$$"
    local created_session_id

    log "case: binding-recovery-gate"

    printf '{}' | REDCAP_SESSION_BINDING_KEY="$binding_key" REDCAP_HOST_PROCESS_PID="$$" bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$host" >/dev/null

    attach_binding_with_capability_recovery "$host" "$REDCAP_ROOT" "$binding_key" "$$" || fail "failed to attach binding with explicit capability recovery"
    created_session_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    [[ -n "$created_session_id" ]] || fail "runtime session id missing after attach"

    redcap_runtime_clear_process_claim "$host" "$$" || true
    redcap_runtime_clear_context

    if redcap_runtime_load_from_binding "$host" "$REDCAP_ROOT" "$binding_key" >/dev/null 2>&1; then
        fail "binding-only attach unexpectedly restored write capability"
    fi

    if REDCAP_HOST_PROCESS_PID="$$" REDCAP_RUNTIME_ALLOW_DISK_RECOVERY=1 redcap_runtime_load_from_binding "$host" "$REDCAP_ROOT" "$binding_key" >/dev/null 2>&1; then
        fail "disk recovery without explicit capability gate unexpectedly succeeded"
    fi
    unset REDCAP_HOST_PROCESS_PID REDCAP_RUNTIME_ALLOW_DISK_RECOVERY

    attach_binding_with_capability_recovery "$host" "$REDCAP_ROOT" "$binding_key" "$$" || fail "explicit capability recovery should succeed"
    assert_eq "${REDCAP_RUNTIME_SESSION_ID:-}" "$created_session_id"
    redcap_runtime_clear_context
}

run_layerb_concurrency_case() {
    local host baseline current_head
    local binding_a binding_b pid_a pid_b probe_a probe_b
    local session_a session_b report_marker_a report_marker_b alerted_a alerted_b

    log "case: layerb-concurrency"

    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    baseline="$(git_previous_head)"
    [[ -n "$baseline" ]] || fail "failed to resolve baseline head for Layer B concurrency case"
    [[ "$baseline" != "$current_head" ]] || fail "layerB concurrency case requires repository history beyond HEAD"

    for host in claude gemini copilot; do
        binding_a="acceptance-${host}-a-${RANDOM}-$$"
        binding_b="acceptance-${host}-b-${RANDOM}-$$"
        pid_a="$((10000 + RANDOM))"
        pid_b="$((20000 + RANDOM))"
        probe_a="$(spawn_host_probe)"
        probe_b="$(spawn_host_probe)"

        printf '{}' | REDCAP_SESSION_BINDING_KEY="$binding_a" REDCAP_HOST_PROCESS_PID="$pid_a" REDCAP_HOST_PROCESS_PROBE_PID="$probe_a" bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$host" >/dev/null
        printf '{}' | REDCAP_SESSION_BINDING_KEY="$binding_b" REDCAP_HOST_PROCESS_PID="$pid_b" REDCAP_HOST_PROCESS_PROBE_PID="$probe_b" bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$host" >/dev/null

        attach_binding_with_capability_recovery "$host" "$REDCAP_ROOT" "$binding_a" "$pid_a" "$probe_a" || fail "failed to attach first $host session"
        session_a="${REDCAP_RUNTIME_SESSION_ID:-}"
        report_marker_a="$(redcap_runtime_path "layerB/current-report-path")"
        redcap_runtime_write_text "layerB/current-report-path" "acceptance/${host}/a.md" || fail "failed to write first report marker"
        redcap_runtime_write_text "layerB/initial-head" "$baseline" || fail "failed to write first baseline"
        redcap_runtime_clear_context

        attach_binding_with_capability_recovery "$host" "$REDCAP_ROOT" "$binding_b" "$pid_b" "$probe_b" || fail "failed to attach second $host session"
        session_b="${REDCAP_RUNTIME_SESSION_ID:-}"
        report_marker_b="$(redcap_runtime_path "layerB/current-report-path")"
        redcap_runtime_write_text "layerB/current-report-path" "acceptance/${host}/b.md" || fail "failed to write second report marker"
        redcap_runtime_write_text "layerB/initial-head" "$baseline" || fail "failed to write second baseline"
        assert_ne "$session_a" "$session_b"
        assert_ne "$report_marker_a" "$report_marker_b"
        assert_eq "$(read_file_text "$report_marker_b")" "acceptance/${host}/b.md"
        redcap_runtime_clear_context

        attach_binding_with_capability_recovery "$host" "$REDCAP_ROOT" "$binding_a" "$pid_a" "$probe_a" || fail "failed to reattach first $host session"
        assert_eq "$(read_file_text "$report_marker_a")" "acceptance/${host}/a.md"
        redcap_runtime_clear_context

        REDCAP_SESSION_BINDING_KEY="$binding_a" REDCAP_HOST_PROCESS_PID="$pid_a" REDCAP_HOST_PROCESS_PROBE_PID="$probe_a" REDCAP_SKIP_FEISHU=1 REDCAP_SKIP_INDEPENDENT_REVIEW=1 bash "$SCRIPT_DIR/redcap-layerB-session-end.sh" "$host" >/dev/null
        REDCAP_SESSION_BINDING_KEY="$binding_b" REDCAP_HOST_PROCESS_PID="$pid_b" REDCAP_HOST_PROCESS_PROBE_PID="$probe_b" REDCAP_SKIP_FEISHU=1 REDCAP_SKIP_INDEPENDENT_REVIEW=1 bash "$SCRIPT_DIR/redcap-layerB-session-end.sh" "$host" >/dev/null

        attach_binding_with_capability_recovery "$host" "$REDCAP_ROOT" "$binding_a" "$pid_a" "$probe_a" || fail "failed to reattach first $host session after session-end"
        alerted_a="$(redcap_runtime_path "layerB/alerted-head")"
        case "$(read_file_text "$alerted_a")" in
            "$current_head|"*) ;;
            *) fail "unexpected alerted marker for first $host session" ;;
        esac
        redcap_runtime_clear_context

        attach_binding_with_capability_recovery "$host" "$REDCAP_ROOT" "$binding_b" "$pid_b" "$probe_b" || fail "failed to reattach second $host session after session-end"
        alerted_b="$(redcap_runtime_path "layerB/alerted-head")"
        case "$(read_file_text "$alerted_b")" in
            "$current_head|"*) ;;
            *) fail "unexpected alerted marker for second $host session" ;;
        esac
        redcap_runtime_clear_context
    done
}

run_copilot_safe_degraded_case() {
    local compat_prefix degraded_file before after expected
    local case_root case_core workboard confirmed_hash
    local suffix stale_runtime_id

    log "case: copilot-safe-degraded"

    compat_prefix="$(redcap_runtime_compat_path_for_root "$REDCAP_ROOT" "legacy-fallback/layerB-copilot")"
    degraded_file="$(redcap_runtime_compat_path_for_root "$REDCAP_ROOT" "degraded-mode.count")"
    before="$(counter_value "$degraded_file")"
    case_root="$ACCEPT_ROOT/copilot-safe-degraded"
    case_core="$CONTINUITY_CORE_DIR/copilot-safe-degraded"
    workboard="$case_root/plan.md"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    stale_runtime_id="stale-runtime-id"

    write_workboard_fixture \
        "$workboard" \
        "$REDCAP_ROOT/.dev-task.md" \
        "framework-upgrade-backlog-review" \
        "acceptance session resume gate" \
        "tranche-1-session-resume-gate-capability-matrix" \
        "$confirmed_hash"

    printf '{}' | REDCAP_HOOK_CWD="$REDCAP_ROOT" REDCAP_HOST_WORKBOARD_PATH="$workboard" REDCAP_CONTINUITY_ROOT_DIR="$case_core" REDCAP_HOST_PROCESS_PID="$$" REDCAP_RUNTIME_SESSION_ID="$stale_runtime_id" bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" copilot >/dev/null
    assert_eq "$(workboard_value "$workboard" "isolation_mode")" "degraded"
    assert_eq "$(workboard_value "$workboard" "resume_gate_reason")" "missing-host-session-id"
    assert_eq "$(workboard_value "$workboard" "resume_gate_profile")" "copilot-sessionstart-wrapper-required"
    assert_eq "$(workboard_value "$workboard" "resume_gate_evidence")" "capability-matrix"
    assert_eq "$(workboard_value "$workboard" "runtime_session_id")" "unknown"
    assert_eq "$(workboard_value "$workboard" "continuity_authority")" "degraded-no-runtime-manifest"
    assert_not_exists "$case_core/sessions/$stale_runtime_id/manifest.yaml"
    assert_not_exists "$case_core/sessions/$stale_runtime_id/provenance.yaml"
    REDCAP_HOOK_CWD="$REDCAP_ROOT" REDCAP_HOST_PROCESS_PID="$$" REDCAP_SKIP_FEISHU=1 REDCAP_SKIP_INDEPENDENT_REVIEW=1 bash "$SCRIPT_DIR/redcap-layerB-session-end.sh" copilot >/dev/null

    for suffix in \
        initial-head \
        confirmed.hash \
        active-slice \
        top-goal \
        last-notified-head \
        last-alerted-head \
        review-result \
        review-log.md; do
        assert_not_exists "$compat_prefix-$suffix"
    done

    after="$(counter_value "$degraded_file")"
    expected=$((before + 2))
    assert_num_eq "$after" "$expected"
}

run_cross_layer_visibility_case() {
    local project_dir state_dir layera_session_id layera_binding
    local layera_pid layerb_pid layerb_binding layera_probe layerb_probe
    local layera_owner_file layera_head_file layera_check_file layerb_head_file
    local layera_session_runtime layerb_session_runtime

    log "case: cross-layer-visibility"

    project_dir="$(make_temp_project)"
    state_dir="$project_dir/开发手册/.workflow"
    mkdir -p "$state_dir"
    printf 'current_state: DEV_WORKING\n' > "$state_dir/state.yaml"
    git -C "$project_dir" init -q
    git -C "$project_dir" config user.name redcap-acceptance
    git -C "$project_dir" config user.email redcap-acceptance@example.com
    printf 'acceptance\n' > "$project_dir/README.txt"
    git -C "$project_dir" add README.txt
    git -C "$project_dir" commit -qm "init"

    layera_session_id="acceptance-cross-layer-a-${RANDOM}-$$"
    layera_binding="$(redcap_runtime_binding_key_from_host_session "claude" "$layera_session_id")"
    layerb_binding="acceptance-cross-layer-b-${RANDOM}-$$"
    layera_pid="$((40000 + RANDOM))"
    layerb_pid="$((50000 + RANDOM))"
    layera_probe="$(spawn_host_probe)"
    layerb_probe="$(spawn_host_probe)"

    printf '{"session_id":"%s","cwd":"%s"}\n' "$layera_session_id" "$project_dir" | REDCAP_HOST_PROCESS_PID="$layera_pid" REDCAP_HOST_PROCESS_PROBE_PID="$layera_probe" bash "$REDCAP_ROOT/loom/tools/redcap-layerA-session-start.sh" >/dev/null
    printf '{}' | REDCAP_SESSION_BINDING_KEY="$layerb_binding" REDCAP_HOST_PROCESS_PID="$layerb_pid" REDCAP_HOST_PROCESS_PROBE_PID="$layerb_probe" bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" claude >/dev/null

    attach_binding_with_capability_recovery "claude" "$project_dir" "$layera_binding" "$layera_pid" "$layera_probe" || fail "failed to attach Layer A runtime"
    layera_session_runtime="${REDCAP_RUNTIME_SESSION_DIR:-}"
    layera_owner_file="$(redcap_runtime_project_path_for_root "$project_dir" "layerA/workflow-owner-session")"
    layera_head_file="$(redcap_runtime_path "layerA/head")"
    layera_check_file="$(redcap_runtime_path "layerA/ownership-check")"
    assert_exists "$layera_owner_file"
    assert_exists "$layera_head_file"
    assert_exists "$layera_check_file"
    redcap_runtime_clear_context

    attach_binding_with_capability_recovery "claude" "$REDCAP_ROOT" "$layerb_binding" "$layerb_pid" "$layerb_probe" || fail "failed to attach Layer B runtime"
    layerb_session_runtime="${REDCAP_RUNTIME_SESSION_DIR:-}"
    layerb_head_file="$(redcap_runtime_path "layerB/initial-head")"
    assert_exists "$layerb_head_file"
    assert_ne "$layera_session_runtime" "$layerb_session_runtime"
    assert_not_exists "$layerb_session_runtime/layerA/head"
    assert_not_exists "$layerb_session_runtime/layerA/ownership-check"
    redcap_runtime_clear_context

    if attach_binding_with_capability_recovery "claude" "$REDCAP_ROOT" "$layera_binding" "$layera_pid" "$layera_probe" >/dev/null 2>&1; then
        fail "Layer A binding unexpectedly reattached under Layer B project root"
    fi
    if attach_binding_with_capability_recovery "claude" "$project_dir" "$layerb_binding" "$layerb_pid" "$layerb_probe" >/dev/null 2>&1; then
        fail "Layer B binding unexpectedly reattached under Layer A project root"
    fi
}

run_layera_legacy_quarantine_case() {
    local project_dir state_dir session_id project_hash
    local legacy_head legacy_notified legacy_owner_session legacy_owner_project
    local legacy_hit_file quarantine_dir quarantine_count_file
    local before_hit before_quarantine after_hit after_quarantine expected_quarantine

    log "case: layera-legacy-quarantine"

    project_dir="$(make_temp_project)"
    state_dir="$project_dir/开发手册/.workflow"
    mkdir -p "$state_dir"
    printf 'current_state: DEV_WORKING\n' > "$state_dir/state.yaml"

    session_id="acceptance-layera-${RANDOM}-$$"
    project_hash="$(redcap_runtime_project_hash "$project_dir")"

    legacy_head="/tmp/redcap-layerA-head-${session_id}"
    legacy_notified="/tmp/redcap-layerA-notified-${session_id}"
    legacy_owner_session="/tmp/redcap-layerA-workflow-session-${session_id}"
    legacy_owner_project="/tmp/redcap-layerA-workflow-session-${project_hash}"
    LEGACY_TMP_FILES+=("$legacy_head" "$legacy_notified" "$legacy_owner_session" "$legacy_owner_project")

    printf 'legacy-head\n' > "$legacy_head"
    printf 'legacy-notified\n' > "$legacy_notified"
    printf 'legacy-owner-session\n' > "$legacy_owner_session"
    printf 'legacy-owner-project\n' > "$legacy_owner_project"

    legacy_hit_file="$(redcap_runtime_compat_path_for_root "$project_dir" "legacy-hit.count")"
    quarantine_dir="$(redcap_runtime_legacy_quarantine_dir_for_root "$project_dir")"
    quarantine_count_file="$quarantine_dir/quarantined.count"
    before_hit="$(counter_value "$legacy_hit_file")"
    before_quarantine="$(counter_value "$quarantine_count_file")"

    printf '{"session_id":"%s","cwd":"%s"}\n' "$session_id" "$project_dir" | REDCAP_HOST_PROCESS_PID="$$" bash "$REDCAP_ROOT/loom/tools/redcap-layerA-session-end.sh" claude >/dev/null

    assert_not_exists "$legacy_head"
    assert_not_exists "$legacy_notified"
    assert_not_exists "$legacy_owner_session"
    assert_not_exists "$legacy_owner_project"

    after_hit="$(counter_value "$legacy_hit_file")"
    after_quarantine="$(counter_value "$quarantine_count_file")"
    assert_num_eq "$after_hit" $((before_hit + 1))
    expected_quarantine=$((before_quarantine + 4))
    assert_num_eq "$after_quarantine" "$expected_quarantine"
    assert_exists "$quarantine_dir/quarantine.log"
    grep -q "$(basename "$legacy_head")" "$quarantine_dir/quarantine.log" || fail "legacy head was not quarantined"
    grep -q "$(basename "$legacy_notified")" "$quarantine_dir/quarantine.log" || fail "legacy notified marker was not quarantined"
    grep -q "$(basename "$legacy_owner_session")" "$quarantine_dir/quarantine.log" || fail "legacy session owner marker was not quarantined"
    grep -q "$(basename "$legacy_owner_project")" "$quarantine_dir/quarantine.log" || fail "legacy project owner marker was not quarantined"
}

run_prism_legacy_bridge_case() {
    local match_run mismatch_run legacy_hit_file before_hit after_hit resolved

    log "case: prism-legacy-bridge"

    mkdir -p "$(dirname "$LEGACY_REGISTRY_FILE")"
    if [[ -f "$LEGACY_REGISTRY_FILE" ]]; then
        LEGACY_REGISTRY_BACKUP="$ACCEPT_ROOT/session-registry.backup"
        cp "$LEGACY_REGISTRY_FILE" "$LEGACY_REGISTRY_BACKUP"
    fi

    match_run="acceptance-prism-match-${RANDOM}-$$"
    mismatch_run="acceptance-prism-mismatch-${RANDOM}-$$"
    cat > "$LEGACY_REGISTRY_FILE" <<EOF
run_id: $match_run
mode: redteam
agents: []
EOF

    legacy_hit_file="$(redcap_runtime_compat_path_for_root "$REDCAP_ROOT" "legacy-hit.count")"
    before_hit="$(counter_value "$legacy_hit_file")"

    resolved="$(bash "$REDCAP_ROOT/prism/tools/prism-run-state.sh" resolve-registry --run-id "$match_run")"
    assert_eq "$resolved" "$LEGACY_REGISTRY_FILE"

    after_hit="$(counter_value "$legacy_hit_file")"
    assert_num_eq "$after_hit" $((before_hit + 1))

    if bash "$REDCAP_ROOT/prism/tools/prism-run-state.sh" resolve-registry --run-id "$mismatch_run" >/dev/null 2>&1; then
        fail "legacy registry unexpectedly resolved mismatched run_id"
    fi
}

run_prism_concurrency_case() {
    local host="claude"
    local host_pid host_probe binding_key run_a run_b
    local raw_a parsed_a raw_b parsed_b
    local output collect_a collect_b handle_a handle_b

    log "case: prism-concurrency"

    host_pid="$((30000 + RANDOM))"
    host_probe="$(spawn_host_probe)"
    binding_key="acceptance-prism-owner-${RANDOM}-$$"
    run_a="acceptance-prism-a-${RANDOM}-$$"
    run_b="acceptance-prism-b-${RANDOM}-$$"
    raw_a="$ACCEPT_ROOT/prism-a.raw.txt"
    parsed_a="$ACCEPT_ROOT/prism-a.parsed.json"
    raw_b="$ACCEPT_ROOT/prism-b.raw.txt"
    parsed_b="$ACCEPT_ROOT/prism-b.parsed.json"

    printf 'raw-a\n' > "$raw_a"
    printf '{"case":"a"}\n' > "$parsed_a"
    printf 'raw-b\n' > "$raw_b"
    printf '{"case":"b"}\n' > "$parsed_b"

    printf '{}' | REDCAP_SESSION_BINDING_KEY="$binding_key" REDCAP_HOST_PROCESS_PID="$host_pid" REDCAP_HOST_PROCESS_PROBE_PID="$host_probe" bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$host" >/dev/null

    REDCAP_HOST_PROCESS_PID="$host_pid" bash "$REDCAP_ROOT/prism/tools/prism-coordinator.sh" start-run --mode redteam --run-id "$run_a" >/dev/null
    REDCAP_HOST_PROCESS_PID="$host_pid" bash "$REDCAP_ROOT/prism/tools/prism-coordinator.sh" start-run --mode redteam --run-id "$run_b" >/dev/null

    REDCAP_HOST_PROCESS_PID="$host_pid" bash "$REDCAP_ROOT/prism/tools/prism-coordinator.sh" register-agent --run-id "$run_a" --mode redteam --role challenger --handle-type cli_session --handle session-a --model test-model-a --family test-family --injection-mode native >/dev/null
    REDCAP_HOST_PROCESS_PID="$host_pid" bash "$REDCAP_ROOT/prism/tools/prism-coordinator.sh" register-agent --run-id "$run_b" --mode redteam --role challenger --handle-type cli_session --handle session-b --model test-model-b --family test-family --injection-mode native >/dev/null

    output="$(REDCAP_HOST_PROCESS_PID="$host_pid" bash "$REDCAP_ROOT/prism/tools/prism-coordinator.sh" record-collect --run-id "$run_a" --mode redteam --role challenger --status responded --schema-ok true --raw-file "$raw_a" --parsed-file "$parsed_a")"
    collect_a="$(extract_output_value "$output" "COLLECT_DIR")"
    output="$(REDCAP_HOST_PROCESS_PID="$host_pid" bash "$REDCAP_ROOT/prism/tools/prism-coordinator.sh" record-collect --run-id "$run_b" --mode redteam --role challenger --status responded --schema-ok true --raw-file "$raw_b" --parsed-file "$parsed_b")"
    collect_b="$(extract_output_value "$output" "COLLECT_DIR")"

    [[ -n "$collect_a" && -n "$collect_b" ]] || fail "failed to resolve Prism collect directories"
    assert_ne "$collect_a" "$collect_b"
    assert_eq "$(read_file_text "$collect_a/raw.txt")" "raw-a"
    assert_eq "$(read_file_text "$collect_b/raw.txt")" "raw-b"
    assert_eq "$(read_file_text "$collect_a/parsed.json")" '{"case":"a"}'
    assert_eq "$(read_file_text "$collect_b/parsed.json")" '{"case":"b"}'

    output="$(REDCAP_HOST_PROCESS_PID="$host_pid" bash "$REDCAP_ROOT/prism/tools/prism-coordinator.sh" resolve-handle --run-id "$run_a" --role challenger)"
    handle_a="$(extract_output_value "$output" "HANDLE")"
    output="$(REDCAP_HOST_PROCESS_PID="$host_pid" bash "$REDCAP_ROOT/prism/tools/prism-coordinator.sh" resolve-handle --run-id "$run_b" --role challenger)"
    handle_b="$(extract_output_value "$output" "HANDLE")"

    assert_eq "$handle_a" "session-a"
    assert_eq "$handle_b" "session-b"
}

run_report_register_requires_claim_case() {
    local report_path degraded_file before after

    log "case: report-register-requires-claim"

    report_path="$REDCAP_ROOT/compass/docs/task-reports/2026-04-11-multi-session-isolation-foundation.md"
    degraded_file="$(redcap_runtime_compat_path_for_root "$REDCAP_ROOT" "degraded-mode.count")"
    before="$(counter_value "$degraded_file")"

    if bash "$REDCAP_ROOT/compass/tools/redcap-task-report-register.sh" claude "$report_path" >/dev/null 2>&1; then
        fail "task report registration unexpectedly succeeded without a process claim"
    fi

    after="$(counter_value "$degraded_file")"
    assert_num_eq "$after" $((before + 1))
}

run_sessionstart_auto_reconcile_rewrite_case() {
    local host="claude"
    local binding_a binding_b pid_a pid_b probe_a probe_b
    local report_path pending_state required_redlines expected_seed expected_reconciled

    log "case: sessionstart-auto-reconcile-rewrite"

    report_path="$REDCAP_ROOT/compass/docs/task-reports/2026-04-11-multi-session-isolation-foundation.md"
    binding_a="acceptance-reconcile-a-${RANDOM}-$$"
    binding_b="acceptance-reconcile-b-${RANDOM}-$$"
    pid_a="$((61000 + RANDOM))"
    pid_b="$((62000 + RANDOM))"
    probe_a="$(spawn_host_probe)"
    probe_b="$(spawn_host_probe)"

    printf '{}' | REDCAP_SESSION_BINDING_KEY="$binding_a" REDCAP_HOST_PROCESS_PID="$pid_a" REDCAP_HOST_PROCESS_PROBE_PID="$probe_a" bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$host" >/dev/null
    REDCAP_HOST_PROCESS_PID="$pid_a" bash "$REDCAP_ROOT/compass/tools/redcap-task-report-register.sh" "$host" "$report_path" >/dev/null

    pending_state=$(redcap_interop_pending_closure_file "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md")
    required_redlines=$(redcap_interop_read_state_field "$pending_state" "required_redlines" 2>/dev/null || true)
    expected_seed="task-report,review,notify"
    assert_eq "$(normalize_csv "$required_redlines")" "$(normalize_csv "$expected_seed")"

    printf '{}' | REDCAP_SESSION_BINDING_KEY="$binding_b" REDCAP_HOST_PROCESS_PID="$pid_b" REDCAP_HOST_PROCESS_PROBE_PID="$probe_b" bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$host" >/dev/null

    required_redlines=$(redcap_interop_read_state_field "$pending_state" "required_redlines" 2>/dev/null || true)
    expected_reconciled="review,notify"
    assert_eq "$(normalize_csv "$required_redlines")" "$(normalize_csv "$expected_reconciled")"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-cleanup" "sessionstart-auto-reconcile-rewrite" >/dev/null
    redcap_runtime_clear_process_claim "$host" "$pid_a" >/dev/null 2>&1 || true
    redcap_runtime_clear_process_claim "$host" "$pid_b" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_sessionstart_auto_reconcile_clear_case() {
    local host="claude"
    local binding_key pid probe_pid
    local report_path pending_state current_head required_redlines

    log "case: sessionstart-auto-reconcile-clear"

    report_path="compass/docs/task-reports/2026-04-11-multi-session-isolation-foundation.md"
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    redcap_interop_write_pending_closure \
        "$REDCAP_ROOT" \
        "$REDCAP_ROOT/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "task-report" \
        "sessionstart-auto-reconcile-clear" \
        "$report_path" \
        "$current_head" \
        "$current_head" \
        >/dev/null
    pending_state=$(redcap_interop_pending_closure_file "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md")
    assert_exists "$pending_state"

    binding_key="acceptance-reconcile-clear-${RANDOM}-$$"
    pid="$((63000 + RANDOM))"
    probe_pid="$(spawn_host_probe)"
    printf '{}' | REDCAP_SESSION_BINDING_KEY="$binding_key" REDCAP_HOST_PROCESS_PID="$pid" REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid" bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$host" >/dev/null

    if [[ -f "$pending_state" ]]; then
        required_redlines=$(redcap_interop_read_state_field "$pending_state" "required_redlines" 2>/dev/null || true)
        assert_eq "$(normalize_csv "$required_redlines")" "$(normalize_csv "drift")"
        redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-cleanup" "sessionstart-auto-reconcile-clear" >/dev/null
    else
        assert_not_exists "$pending_state"
    fi
    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_sessionstart_auto_reconcile_hash_mismatch_case() {
    local host="claude"
    local binding_key pid probe_pid
    local report_path pending_state required_redlines
    local current_hash mismatch_hash

    log "case: sessionstart-auto-reconcile-hash-mismatch"

    report_path="compass/docs/task-reports/2026-04-11-multi-session-isolation-foundation.md"
    current_hash=$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")
    mismatch_hash="deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    [[ "$current_hash" != "$mismatch_hash" ]] || fail "hash mismatch fixture collided with current confirmed hash"

    redcap_interop_write_pending_closure \
        "$REDCAP_ROOT" \
        "$REDCAP_ROOT/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "task-report" \
        "sessionstart-auto-reconcile-hash-mismatch" \
        "$report_path" \
        "$current_hash" \
        "$current_hash" \
        >/dev/null
    pending_state=$(redcap_interop_pending_closure_file "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md")
    python3 - "$pending_state" "$mismatch_hash" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
replacement = sys.argv[2]
text = path.read_text(encoding="utf-8")
updated = re.sub(r"^confirmed_hash:\s*.*$", f"confirmed_hash: {replacement}", text, count=1, flags=re.MULTILINE)
path.write_text(updated, encoding="utf-8")
PY

    binding_key="acceptance-reconcile-hash-mismatch-${RANDOM}-$$"
    pid="$((64000 + RANDOM))"
    probe_pid="$(spawn_host_probe)"
    printf '{}' | REDCAP_SESSION_BINDING_KEY="$binding_key" REDCAP_HOST_PROCESS_PID="$pid" REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid" bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$host" >/dev/null

    assert_exists "$pending_state"
    required_redlines=$(redcap_interop_read_state_field "$pending_state" "required_redlines" 2>/dev/null || true)
    assert_eq "$(normalize_csv "$required_redlines")" "$(normalize_csv "task-report")"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-cleanup" "sessionstart-auto-reconcile-hash-mismatch" >/dev/null
    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_sessionstart_runtime_init_failed_degrades_case() {
    local case_root case_core workboard
    local task_id top_goal active_slice confirmed_hash

    log "case: sessionstart-runtime-init-failed-degrades"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/sessionstart-runtime-init-failed-degrades"
    case_core="$CONTINUITY_CORE_DIR/sessionstart-runtime-init-failed-degrades"
    workboard="$case_root/plan.md"

    write_workboard_fixture "$workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    printf '{}' | \
        REDCAP_HOOK_CWD="$REDCAP_ROOT" \
        REDCAP_HOST_WORKBOARD_PATH="$workboard" \
        REDCAP_CONTINUITY_ROOT_DIR="$case_core" \
        REDCAP_SESSION_BINDING_KEY="acceptance-invalid-binding" \
        REDCAP_SESSION_ISOLATION_MODE="full" \
        REDCAP_SESSION_RESUME_REASON="acceptance-forced-full" \
        REDCAP_SESSION_RESUME_ALLOW_DISK_RECOVERY="0" \
        REDCAP_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY="0" \
        REDCAP_HOST_PROCESS_PID=999999 \
        bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "claude" >/dev/null

    assert_eq "$(workboard_value "$workboard" "isolation_mode")" "degraded"
    assert_eq "$(workboard_value "$workboard" "resume_gate_reason")" "runtime-init-failed"
    assert_eq "$(workboard_value "$workboard" "continuity_authority")" "degraded-no-runtime-manifest"
    assert_eq "$(workboard_value "$workboard" "import_protocol")" "runtime-session-unavailable"
    assert_eq "$(workboard_value "$workboard" "import_ready_signal")" "blocked-no-runtime"
}

run_continuity_manifest_sync_case() {
    local host="claude"
    local binding_key pid runtime_id
    local case_root case_core session_dir workboard manifest provenance
    local task_id top_goal active_slice confirmed_hash

    log "case: continuity-manifest-sync"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/continuity-sync"
    case_core="$CONTINUITY_CORE_DIR/continuity-sync"
    session_dir="$case_root/host-a/session-sync"
    workboard="$session_dir/plan.md"
    write_workboard_fixture "$workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$session_dir/files"
    printf 'own record\n' >"$session_dir/files/note.txt"

    binding_key="acceptance-continuity-sync-${RANDOM}-$$"
    pid="$((65000 + RANDOM))"
    init_bound_runtime "$host" "$binding_key" "$pid"
    runtime_id="${REDCAP_RUNTIME_SESSION_ID:-}"

    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null

    manifest="$case_core/sessions/$runtime_id/manifest.yaml"
    provenance="$case_core/sessions/$runtime_id/provenance.yaml"
    assert_exists "$manifest"
    assert_exists "$provenance"
    assert_eq "$(manifest_value "$manifest" "runtime_session_id")" "$runtime_id"
    assert_eq "$(manifest_value "$manifest" "continuity_state")" "self-recorded"
    assert_eq "$(manifest_value "$manifest" "import_protocol")" "not-needed-current-session-has-own-record"
    assert_eq "$(manifest_value "$manifest" "import_ready_signal")" "not-needed-own-record"
    assert_eq "$(workboard_value "$workboard" "continuity_authority")" "redcap-owned-manifest"
    assert_eq "$(workboard_value "$workboard" "continuity_state")" "self-recorded"
    assert_eq "$(workboard_value "$workboard" "import_protocol")" "not-needed-current-session-has-own-record"
    assert_eq "$(workboard_value "$workboard" "import_ready_signal")" "not-needed-own-record"
    assert_string_contains "$(workboard_value "$workboard" "import_ready_summary")" "own continuity assets"

    python3 - "$workboard" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = re.sub(r"^- continuity_state:\s*.*$", "- continuity_state: imported", text, count=1, flags=re.MULTILINE)
text = re.sub(r"^- continuity_authority:\s*.*$", "- continuity_authority: tampered", text, count=1, flags=re.MULTILINE)
path.write_text(text, encoding="utf-8")
PY

    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    assert_eq "$(workboard_value "$workboard" "continuity_authority")" "redcap-owned-manifest"
    assert_eq "$(workboard_value "$workboard" "continuity_state")" "self-recorded"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_continuity_runtime_required_case() {
    local host="claude"
    local binding_key pid runtime_id
    local case_root case_core session_dir workboard manifest
    local task_id top_goal active_slice confirmed_hash

    log "case: continuity-runtime-required"

    redcap_runtime_clear_context
    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/continuity-runtime-required"
    case_core="$CONTINUITY_CORE_DIR/continuity-runtime-required"
    session_dir="$case_root/host-a/session-runtime-missing"
    workboard="$session_dir/plan.md"
    write_workboard_fixture "$workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$session_dir/files"
    printf 'own record\n' >"$session_dir/files/note.txt"

    binding_key="acceptance-continuity-runtime-required-${RANDOM}-$$"
    pid="$((69000 + RANDOM))"
    init_bound_runtime "$host" "$binding_key" "$pid"
    runtime_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    manifest="$case_core/sessions/$runtime_id/manifest.yaml"
    assert_exists "$manifest"
    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true

    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null

    assert_eq "$(workboard_value "$workboard" "continuity_authority")" "degraded-no-runtime-manifest"
    assert_eq "$(workboard_value "$workboard" "continuity_state")" "fresh-session"
    assert_eq "$(workboard_value "$workboard" "import_protocol")" "runtime-session-unavailable"
    assert_eq "$(workboard_value "$workboard" "import_ready_signal")" "blocked-no-runtime"
    assert_string_contains "$(workboard_value "$workboard" "import_ready_summary")" "verified runtime binding"
    redcap_runtime_clear_context
}

run_continuity_manifest_only_discovery_case() {
    local host="claude"
    local binding_key pid
    local case_root case_core source_dir target_dir source_workboard target_workboard
    local task_id top_goal active_slice confirmed_hash

    log "case: continuity-manifest-only-discovery"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/continuity-manifest-only-discovery"
    case_core="$CONTINUITY_CORE_DIR/continuity-manifest-only-discovery"
    source_dir="$case_root/shared-base/source-session"
    target_dir="$case_root/shared-base/target-session"
    source_workboard="$source_dir/plan.md"
    target_workboard="$target_dir/plan.md"

    write_workboard_fixture "$source_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$source_dir/files"
    printf 'source own record\n' >"$source_dir/files/note.txt"
    write_workboard_fixture "$target_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"

    binding_key="acceptance-continuity-discovery-${RANDOM}-$$"
    pid="$((66000 + RANDOM))"
    init_bound_runtime "$host" "$binding_key" "$pid"

    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null

    assert_eq "$(workboard_value "$target_workboard" "continuity_state")" "fresh-session"
    assert_eq "$(workboard_value "$target_workboard" "import_protocol")" "no-compatible-source-detected"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_continuity_runtime_claim_requires_live_process_case() {
    local host="claude"
    local binding_key pid
    local case_root case_core workboard manifest claim_file runtime_id
    local task_id top_goal active_slice confirmed_hash

    log "case: continuity-runtime-claim-requires-live-process"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/continuity-runtime-claim-requires-live-process"
    case_core="$CONTINUITY_CORE_DIR/continuity-runtime-claim-requires-live-process"
    workboard="$case_root/host-a/session-live-claim/plan.md"

    write_workboard_fixture "$workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"

    binding_key="acceptance-continuity-live-claim-${RANDOM}-$$"
    pid="$((65500 + RANDOM))"
    init_bound_runtime "$host" "$binding_key" "$pid"
    runtime_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    manifest="$case_core/sessions/$runtime_id/manifest.yaml"
    assert_exists "$manifest"

    claim_file="$(redcap_runtime_process_claim_file "$host" "$pid")"
    python3 - "$claim_file" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
data["host_process_started_at"] = "Mon Jan  1 00:00:00 1990"
path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
PY

    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    assert_eq "$(workboard_value "$workboard" "continuity_authority")" "degraded-no-runtime-manifest"
    assert_eq "$(workboard_value "$workboard" "import_protocol")" "runtime-session-unavailable"
    assert_eq "$(workboard_value "$workboard" "import_ready_signal")" "blocked-no-runtime"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_continuity_discovery_requires_source_metadata_case() {
    local host="claude"
    local source_binding target_binding source_pid target_pid
    local source_runtime_id
    local case_root case_core
    local source_dir target_dir source_workboard target_workboard source_manifest
    local task_id top_goal active_slice confirmed_hash

    log "case: continuity-discovery-requires-source-metadata"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/continuity-discovery-requires-source-metadata"
    case_core="$CONTINUITY_CORE_DIR/continuity-discovery-requires-source-metadata"
    source_dir="$case_root/shared-base/source-session"
    target_dir="$case_root/shared-base/target-session"
    source_workboard="$source_dir/plan.md"
    target_workboard="$target_dir/plan.md"

    write_workboard_fixture "$source_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$source_dir/files"
    printf 'source own record\n' >"$source_dir/files/note.txt"
    source_binding="acceptance-discovery-source-${RANDOM}-$$"
    source_pid="$((66500 + RANDOM))"
    init_bound_runtime "$host" "$source_binding" "$source_pid"
    source_runtime_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$source_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    source_manifest="$case_core/sessions/$source_runtime_id/manifest.yaml"
    python3 - "$source_manifest" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
for key in ("task_id", "confirmed_hash"):
    text = re.sub(rf'^{key}:\s*.*\n?', '', text, flags=re.MULTILINE)
path.write_text(text, encoding="utf-8")
PY
    redcap_runtime_clear_process_claim "$host" "$source_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context

    write_workboard_fixture "$target_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    target_binding="acceptance-discovery-target-${RANDOM}-$$"
    target_pid="$((66600 + RANDOM))"
    init_bound_runtime "$host" "$target_binding" "$target_pid"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null

    assert_eq "$(workboard_value "$target_workboard" "continuity_state")" "fresh-session"
    assert_eq "$(workboard_value "$target_workboard" "import_protocol")" "no-compatible-source-detected"
    assert_eq "$(workboard_value "$target_workboard" "import_ready_signal")" "not-ready-no-compatible-source"
    assert_eq "$(workboard_value "$target_workboard" "suggested_source_session_handle")" ""

    redcap_runtime_clear_process_claim "$host" "$target_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_continuity_manifest_import_case() {
    local host="claude"
    local source_binding target_binding source_pid target_pid
    local source_runtime_id target_runtime_id
    local case_root case_core
    local source_dir target_dir source_workboard target_workboard
    local source_manifest target_manifest target_provenance import_registry audit_log metadata_path
    local task_id top_goal active_slice confirmed_hash import_output

    log "case: continuity-manifest-import"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/continuity-manifest-import"
    case_core="$CONTINUITY_CORE_DIR/continuity-manifest-import"
    source_dir="$case_root/source-host/source-session"
    target_dir="$case_root/target-host/target-session"
    source_workboard="$source_dir/plan.md"
    target_workboard="$target_dir/plan.md"

    write_workboard_fixture "$source_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$source_dir/files"
    printf 'source own record\n' >"$source_dir/files/note.txt"

    source_binding="acceptance-continuity-import-source-${RANDOM}-$$"
    source_pid="$((67000 + RANDOM))"
    init_bound_runtime "$host" "$source_binding" "$source_pid"
    source_runtime_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$source_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    source_manifest="$case_core/sessions/$source_runtime_id/manifest.yaml"
    assert_exists "$source_manifest"
    redcap_runtime_clear_process_claim "$host" "$source_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context

    write_workboard_fixture "$target_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    target_binding="acceptance-continuity-import-target-${RANDOM}-$$"
    target_pid="$((68000 + RANDOM))"
    init_bound_runtime "$host" "$target_binding" "$target_pid"
    target_runtime_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null

    assert_eq "$(workboard_value "$target_workboard" "continuity_state")" "import-suggested"
    assert_eq "$(workboard_value "$target_workboard" "suggested_source_session_handle")" "source-session"
    assert_eq "$(workboard_value "$target_workboard" "import_protocol")" "explicit-only"
    assert_eq "$(workboard_value "$target_workboard" "import_ready_signal")" "ready"
    assert_string_contains "$(workboard_value "$target_workboard" "import_ready_summary")" "source-session"

    import_output="$(REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" import "$source_workboard" "$target_workboard" "$REDCAP_ROOT/.dev-task.md")"

    target_manifest="$case_core/sessions/$target_runtime_id/manifest.yaml"
    target_provenance="$case_core/sessions/$target_runtime_id/provenance.yaml"
    import_registry="$case_core/continuity/import-registry.jsonl"
    audit_log="$case_core/continuity/audit-log.jsonl"
    metadata_path="$target_dir/files/imported-sessions/source-session/metadata.json"
    assert_exists "$target_manifest"
    assert_exists "$target_provenance"
    assert_exists "$import_registry"
    assert_exists "$audit_log"
    assert_string_contains "$import_output" "\"status\": \"imported\""
    assert_string_contains "$import_output" "\"import_action\": \"copied\""
    assert_string_contains "$import_output" "\"import_root\": \"files/imported-sessions/source-session\""
    assert_string_contains "$import_output" "\"imported_match_strength\": \"exact\""
    assert_string_contains "$import_output" "\"source_session_handle\": \"source-session\""
    assert_string_contains "$import_output" "\"target_runtime_session_id\": \"$target_runtime_id\""
    assert_eq "$(manifest_value "$target_manifest" "source_session_handle")" "source-session"
    assert_eq "$(manifest_value "$target_manifest" "import_protocol")" "explicit-copy-preserve-source"
    assert_eq "$(manifest_value "$target_manifest" "import_ready_signal")" "completed"
    assert_string_contains "$(manifest_value "$target_manifest" "import_success_summary")" "source-session"
    assert_string_contains "$(manifest_value "$target_manifest" "import_success_summary")" "mode=copied"
    assert_eq "$(workboard_value "$target_workboard" "continuity_state")" "imported"
    assert_eq "$(workboard_value "$target_workboard" "continuity_authority")" "redcap-owned-manifest"
    assert_eq "$(workboard_value "$target_workboard" "import_protocol")" "explicit-copy-preserve-source"
    assert_eq "$(workboard_value "$target_workboard" "import_ready_signal")" "completed"
    assert_string_contains "$(workboard_value "$target_workboard" "import_success_summary")" "source-session"
    assert_string_contains "$(workboard_value "$target_workboard" "import_success_summary")" "mode=copied"
    assert_contains "$import_registry" "\"target_runtime_session_id\": \"$target_runtime_id\""
    assert_contains "$audit_log" "\"event\": \"import\""

    rm -f "$metadata_path"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    assert_eq "$(workboard_value "$target_workboard" "continuity_state")" "imported"

    redcap_runtime_clear_process_claim "$host" "$target_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
    if REDCAP_CONTINUITY_ROOT_DIR="$case_core" REDCAP_RUNTIME_SESSION_ID="$target_runtime_id" REDCAP_RUNTIME_HOST="$host" \
        bash "$SCRIPT_DIR/redcap-session-continuity.sh" import "$source_workboard" "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null 2>&1; then
        fail "import unexpectedly succeeded without verified runtime capability"
    fi

    redcap_runtime_clear_context
}

run_continuity_cross_host_import_case() {
    local source_host="claude"
    local target_host="copilot"
    local source_session_id source_pid source_probe target_binding target_pid target_probe
    local source_runtime_id target_runtime_id
    local case_root case_core
    local source_dir target_dir source_workboard target_workboard
    local source_manifest target_manifest import_output
    local task_id top_goal active_slice confirmed_hash

    log "case: continuity-cross-host-import"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/continuity-cross-host-import"
    case_core="$CONTINUITY_CORE_DIR/continuity-cross-host-import"
    source_dir="$case_root/source-host/source-session"
    target_dir="$case_root/target-host/target-session"
    source_workboard="$source_dir/plan.md"
    target_workboard="$target_dir/plan.md"

    write_workboard_fixture "$source_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$source_dir/files"
    printf 'source own record\n' >"$source_dir/files/note.txt"

    source_session_id="acceptance-cross-host-source-${RANDOM}-$$"
    source_pid="$((69000 + RANDOM))"
    source_probe="$(spawn_host_probe)"
    printf '{"session_id":"%s","cwd":"%s"}\n' "$source_session_id" "$REDCAP_ROOT" | \
        REDCAP_HOOK_CWD="$REDCAP_ROOT" \
        REDCAP_HOST_WORKBOARD_PATH="$source_workboard" \
        REDCAP_CONTINUITY_ROOT_DIR="$case_core" \
        REDCAP_HOST_PROCESS_PID="$source_pid" \
        REDCAP_HOST_PROCESS_PROBE_PID="$source_probe" \
        bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$source_host" >/dev/null

    source_runtime_id="$(workboard_value "$source_workboard" "runtime_session_id")"
    source_manifest="$case_core/sessions/$source_runtime_id/manifest.yaml"
    assert_eq "$(workboard_value "$source_workboard" "isolation_mode")" "full"
    assert_eq "$(workboard_value "$source_workboard" "continuity_state")" "self-recorded"
    assert_exists "$source_manifest"

    write_workboard_fixture "$target_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    target_binding="acceptance-cross-host-target-${RANDOM}-$$"
    target_pid="$((70000 + RANDOM))"
    target_probe="$(spawn_host_probe)"
    printf '{}' | \
        REDCAP_HOOK_CWD="$REDCAP_ROOT" \
        REDCAP_HOST_WORKBOARD_PATH="$target_workboard" \
        REDCAP_CONTINUITY_ROOT_DIR="$case_core" \
        REDCAP_HOST_PROCESS_PID="$target_pid" \
        REDCAP_HOST_PROCESS_PROBE_PID="$target_probe" \
        REDCAP_SESSION_BINDING_KEY="$target_binding" \
        bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$target_host" >/dev/null

    assert_eq "$(workboard_value "$target_workboard" "isolation_mode")" "full"
    assert_eq "$(workboard_value "$target_workboard" "continuity_state")" "import-suggested"
    assert_eq "$(workboard_value "$target_workboard" "suggested_source_session_handle")" "source-session"
    assert_eq "$(workboard_value "$target_workboard" "import_protocol")" "explicit-only"
    assert_eq "$(workboard_value "$target_workboard" "import_ready_signal")" "ready"

    init_bound_runtime "$target_host" "$target_binding" "$target_pid"
    target_runtime_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    import_output="$(REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" import "$source_workboard" "$target_workboard" "$REDCAP_ROOT/.dev-task.md")"

    target_manifest="$case_core/sessions/$target_runtime_id/manifest.yaml"
    assert_exists "$target_manifest"
    assert_eq "$(manifest_value "$target_manifest" "import_protocol")" "explicit-copy-preserve-source"
    assert_eq "$(manifest_value "$target_manifest" "import_ready_signal")" "completed"
    assert_eq "$(workboard_value "$target_workboard" "continuity_state")" "imported"
    assert_eq "$(workboard_value "$target_workboard" "continuity_authority")" "redcap-owned-manifest"
    assert_eq "$(workboard_value "$target_workboard" "import_protocol")" "explicit-copy-preserve-source"
    assert_eq "$(workboard_value "$target_workboard" "import_ready_signal")" "completed"
    assert_string_contains "$import_output" "\"import_action\": \"copied\""
    assert_string_contains "$import_output" "\"source_session_handle\": \"source-session\""
    assert_string_contains "$import_output" "\"target_session_handle\": \"target-session\""
    assert_string_contains "$(manifest_value "$target_manifest" "import_success_summary")" "source-session"
    assert_string_contains "$(manifest_value "$target_manifest" "import_success_summary")" "mode=copied"
    assert_string_contains "$(workboard_value "$target_workboard" "import_success_summary")" "source-session"
    assert_string_contains "$(workboard_value "$target_workboard" "import_success_summary")" "mode=copied"

    redcap_runtime_clear_process_claim "$source_host" "$source_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_process_claim "$target_host" "$target_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_continuity_manifest_mismatch_case() {
    local host="claude"
    local source_session_id source_pid source_probe target_session_id target_pid target_probe
    local case_root case_core
    local source_dir target_dir source_workboard target_workboard
    local source_runtime_id source_manifest
    local task_id top_goal active_slice confirmed_hash mismatch_hash mismatch_goal

    log "case: continuity-manifest-mismatch"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    mismatch_hash="deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    mismatch_goal="mismatch continuity goal"
    case_root="$ACCEPT_ROOT/continuity-manifest-mismatch"
    case_core="$CONTINUITY_CORE_DIR/continuity-manifest-mismatch"
    source_dir="$case_root/source-host/source-session"
    target_dir="$case_root/target-host/target-session"
    source_workboard="$source_dir/plan.md"
    target_workboard="$target_dir/plan.md"

    write_workboard_fixture "$source_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$source_dir/files"
    printf 'source own record\n' >"$source_dir/files/note.txt"

    source_session_id="acceptance-mismatch-source-${RANDOM}-$$"
    source_pid="$((71000 + RANDOM))"
    source_probe="$(spawn_host_probe)"
    printf '{"session_id":"%s","cwd":"%s"}\n' "$source_session_id" "$REDCAP_ROOT" | \
        REDCAP_HOOK_CWD="$REDCAP_ROOT" \
        REDCAP_HOST_WORKBOARD_PATH="$source_workboard" \
        REDCAP_CONTINUITY_ROOT_DIR="$case_core" \
        REDCAP_HOST_PROCESS_PID="$source_pid" \
        REDCAP_HOST_PROCESS_PROBE_PID="$source_probe" \
        bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$host" >/dev/null
    source_runtime_id="$(workboard_value "$source_workboard" "runtime_session_id")"
    assert_exists "$case_core/sessions/$source_runtime_id/manifest.yaml"

    source_manifest="$case_core/sessions/$source_runtime_id/manifest.yaml"
    assert_exists "$source_manifest"
    python3 - "$source_manifest" "$mismatch_goal" "$mismatch_hash" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
goal = sys.argv[2]
confirmed_hash = sys.argv[3]
text = path.read_text(encoding="utf-8")
text = re.sub(r'^top_goal:\s*.*$', f'top_goal: "{goal}"', text, flags=re.MULTILINE)
text = re.sub(r'^confirmed_hash:\s*.*$', f'confirmed_hash: "{confirmed_hash}"', text, flags=re.MULTILINE)
path.write_text(text, encoding="utf-8")
PY

    write_workboard_fixture "$target_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    target_session_id="acceptance-mismatch-target-${RANDOM}-$$"
    target_pid="$((72000 + RANDOM))"
    target_probe="$(spawn_host_probe)"
    printf '{"session_id":"%s","cwd":"%s"}\n' "$target_session_id" "$REDCAP_ROOT" | \
        REDCAP_HOOK_CWD="$REDCAP_ROOT" \
        REDCAP_HOST_WORKBOARD_PATH="$target_workboard" \
        REDCAP_CONTINUITY_ROOT_DIR="$case_core" \
        REDCAP_HOST_PROCESS_PID="$target_pid" \
        REDCAP_HOST_PROCESS_PROBE_PID="$target_probe" \
        bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$host" >/dev/null

    assert_eq "$(workboard_value "$target_workboard" "continuity_state")" "fresh-session"
    assert_eq "$(workboard_value "$target_workboard" "import_ready_signal")" "not-ready-no-compatible-source"
    assert_eq "$(workboard_value "$target_workboard" "import_protocol")" "no-compatible-source-detected"
    assert_eq "$(workboard_value "$target_workboard" "suggested_source_session_handle")" ""

    init_bound_runtime "$host" "$(workboard_value "$target_workboard" "session_binding_key")" "$target_pid"
    if REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" import "$source_workboard" "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null 2>&1; then
        fail "mismatched source unexpectedly imported"
    fi

    redcap_runtime_clear_process_claim "$host" "$source_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_process_claim "$host" "$target_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_continuity_stale_import_case() {
    local host="claude"
    local source_binding target_binding source_pid target_pid
    local source_runtime_id target_runtime_id
    local case_root case_core
    local source_dir target_dir source_workboard target_workboard
    local source_manifest target_manifest mismatch_goal mismatch_hash
    local task_id top_goal active_slice confirmed_hash

    log "case: continuity-stale-import"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    mismatch_goal="stale import mismatch goal"
    mismatch_hash="feedfacefeedfacefeedfacefeedfacefeedfacefeedfacefeedfacefeedface"
    case_root="$ACCEPT_ROOT/continuity-stale-import"
    case_core="$CONTINUITY_CORE_DIR/continuity-stale-import"
    source_dir="$case_root/source-host/source-session"
    target_dir="$case_root/target-host/target-session"
    source_workboard="$source_dir/plan.md"
    target_workboard="$target_dir/plan.md"

    write_workboard_fixture "$source_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$source_dir/files"
    printf 'source own record\n' >"$source_dir/files/note.txt"

    source_binding="acceptance-stale-import-source-${RANDOM}-$$"
    source_pid="$((73000 + RANDOM))"
    init_bound_runtime "$host" "$source_binding" "$source_pid"
    source_runtime_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$source_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    source_manifest="$case_core/sessions/$source_runtime_id/manifest.yaml"
    assert_exists "$source_manifest"
    redcap_runtime_clear_process_claim "$host" "$source_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context

    write_workboard_fixture "$target_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    target_binding="acceptance-stale-import-target-${RANDOM}-$$"
    target_pid="$((74000 + RANDOM))"
    init_bound_runtime "$host" "$target_binding" "$target_pid"
    target_runtime_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" import "$source_workboard" "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null

    target_manifest="$case_core/sessions/$target_runtime_id/manifest.yaml"
    assert_exists "$target_manifest"
    rm -f "$source_manifest"
    python3 - "$target_manifest" "$mismatch_goal" "$mismatch_hash" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
goal = sys.argv[2]
confirmed_hash = sys.argv[3]
text = path.read_text(encoding="utf-8")
text = re.sub(r'^source_top_goal:\s*.*$', f'source_top_goal: "{goal}"', text, flags=re.MULTILINE)
text = re.sub(r'^source_confirmed_hash:\s*.*$', f'source_confirmed_hash: "{confirmed_hash}"', text, flags=re.MULTILINE)
path.write_text(text, encoding="utf-8")
PY

    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    assert_eq "$(workboard_value "$target_workboard" "continuity_state")" "fresh-session"
    assert_eq "$(workboard_value "$target_workboard" "stale_import_session_handle")" "source-session"
    assert_eq "$(workboard_value "$target_workboard" "stale_import_reason")" "task-metadata-mismatch"
    assert_eq "$(workboard_value "$target_workboard" "import_protocol")" "no-compatible-source-detected"
    assert_eq "$(workboard_value "$target_workboard" "import_ready_signal")" "not-ready-no-compatible-source"
    assert_eq "$(workboard_value "$target_workboard" "suggested_source_session_handle")" ""

    redcap_runtime_clear_process_claim "$host" "$target_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_continuity_stale_import_requires_source_metadata_case() {
    local host="claude"
    local source_binding target_binding source_pid target_pid
    local target_runtime_id
    local case_root case_core
    local source_dir target_dir source_workboard target_workboard target_manifest
    local task_id top_goal active_slice confirmed_hash

    log "case: continuity-stale-import-requires-source-metadata"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/continuity-stale-import-requires-source-metadata"
    case_core="$CONTINUITY_CORE_DIR/continuity-stale-import-requires-source-metadata"
    source_dir="$case_root/source-host/source-session"
    target_dir="$case_root/target-host/target-session"
    source_workboard="$source_dir/plan.md"
    target_workboard="$target_dir/plan.md"

    write_workboard_fixture "$source_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$source_dir/files"
    printf 'source own record\n' >"$source_dir/files/note.txt"

    source_binding="acceptance-stale-metadata-source-${RANDOM}-$$"
    source_pid="$((73500 + RANDOM))"
    init_bound_runtime "$host" "$source_binding" "$source_pid"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$source_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    redcap_runtime_clear_process_claim "$host" "$source_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context

    write_workboard_fixture "$target_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    target_binding="acceptance-stale-metadata-target-${RANDOM}-$$"
    target_pid="$((74500 + RANDOM))"
    init_bound_runtime "$host" "$target_binding" "$target_pid"
    target_runtime_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" import "$source_workboard" "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null

    target_manifest="$case_core/sessions/$target_runtime_id/manifest.yaml"
    python3 - "$target_manifest" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
for key in ("source_task_id", "source_confirmed_hash"):
    text = re.sub(rf'^{key}:\s*.*\n?', '', text, flags=re.MULTILINE)
path.write_text(text, encoding="utf-8")
PY

    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    assert_eq "$(workboard_value "$target_workboard" "continuity_state")" "import-suggested"
    assert_eq "$(workboard_value "$target_workboard" "stale_import_session_handle")" "source-session"
    assert_eq "$(workboard_value "$target_workboard" "stale_import_reason")" "task-metadata-mismatch"
    assert_eq "$(workboard_value "$target_workboard" "import_protocol")" "explicit-only"
    assert_eq "$(workboard_value "$target_workboard" "import_ready_signal")" "ready"
    assert_eq "$(workboard_value "$target_workboard" "suggested_source_session_handle")" "source-session"

    redcap_runtime_clear_process_claim "$host" "$target_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_continuity_rejects_stale_source_manifest_case() {
    local source_host="claude"
    local degraded_host="unsupported-host"
    local target_host="copilot"
    local source_binding target_binding source_pid target_pid
    local case_root case_core
    local source_dir target_dir source_workboard target_workboard
    local task_id top_goal active_slice confirmed_hash

    log "case: continuity-rejects-stale-source-manifest"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/continuity-rejects-stale-source-manifest"
    case_core="$CONTINUITY_CORE_DIR/continuity-rejects-stale-source-manifest"
    source_dir="$case_root/source-host/source-session"
    target_dir="$case_root/target-host/target-session"
    source_workboard="$source_dir/plan.md"
    target_workboard="$target_dir/plan.md"

    write_workboard_fixture "$source_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$source_dir/files"
    printf 'source own record\n' >"$source_dir/files/note.txt"
    source_binding="acceptance-stale-source-${RANDOM}-$$"
    source_pid="$((81500 + RANDOM))"
    init_bound_runtime "$source_host" "$source_binding" "$source_pid"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$source_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    redcap_runtime_clear_process_claim "$source_host" "$source_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context

    printf '{}' | \
        REDCAP_HOOK_CWD="$REDCAP_ROOT" \
        REDCAP_HOST_WORKBOARD_PATH="$source_workboard" \
        REDCAP_CONTINUITY_ROOT_DIR="$case_core" \
        bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$degraded_host" >/dev/null
    assert_eq "$(workboard_value "$source_workboard" "continuity_authority")" "degraded-no-runtime-manifest"
    assert_eq "$(workboard_value "$source_workboard" "import_ready_signal")" "blocked-no-runtime"

    write_workboard_fixture "$target_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    target_binding="acceptance-stale-source-target-${RANDOM}-$$"
    target_pid="$((82500 + RANDOM))"
    init_bound_runtime "$target_host" "$target_binding" "$target_pid"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null

    assert_eq "$(workboard_value "$target_workboard" "continuity_state")" "fresh-session"
    assert_eq "$(workboard_value "$target_workboard" "import_protocol")" "no-compatible-source-detected"
    assert_eq "$(workboard_value "$target_workboard" "import_ready_signal")" "not-ready-no-compatible-source"
    assert_eq "$(workboard_value "$target_workboard" "suggested_source_session_handle")" ""

    if REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" import "$source_workboard" "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null 2>&1; then
        fail "stale source manifest unexpectedly imported"
    fi

    redcap_runtime_clear_process_claim "$target_host" "$target_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_continuity_import_requires_source_manifest_case() {
    local host="claude"
    local target_binding target_pid
    local case_root case_core
    local source_dir target_dir source_workboard target_workboard
    local task_id top_goal active_slice confirmed_hash

    log "case: continuity-import-requires-source-manifest"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/continuity-import-requires-source-manifest"
    case_core="$CONTINUITY_CORE_DIR/continuity-import-requires-source-manifest"
    source_dir="$case_root/source-host/source-session"
    target_dir="$case_root/target-host/target-session"
    source_workboard="$source_dir/plan.md"
    target_workboard="$target_dir/plan.md"

    write_workboard_fixture "$source_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$source_dir/files"
    printf 'source own record\n' >"$source_dir/files/note.txt"

    write_workboard_fixture "$target_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    target_binding="acceptance-source-manifest-target-${RANDOM}-$$"
    target_pid="$((75000 + RANDOM))"
    init_bound_runtime "$host" "$target_binding" "$target_pid"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null

    if REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" import "$source_workboard" "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null 2>&1; then
        fail "source without manifest unexpectedly imported"
    fi

    redcap_runtime_clear_process_claim "$host" "$target_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_continuity_import_requires_source_metadata_case() {
    local host="claude"
    local source_binding source_pid target_binding target_pid
    local source_runtime_id source_manifest
    local case_root case_core
    local source_dir target_dir source_workboard target_workboard
    local task_id top_goal active_slice confirmed_hash

    log "case: continuity-import-requires-source-metadata"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/continuity-import-requires-source-metadata"
    case_core="$CONTINUITY_CORE_DIR/continuity-import-requires-source-metadata"
    source_dir="$case_root/source-host/source-session"
    target_dir="$case_root/target-host/target-session"
    source_workboard="$source_dir/plan.md"
    target_workboard="$target_dir/plan.md"

    write_workboard_fixture "$source_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$source_dir/files"
    printf 'source own record\n' >"$source_dir/files/note.txt"
    source_binding="acceptance-source-metadata-source-${RANDOM}-$$"
    source_pid="$((79000 + RANDOM))"
    init_bound_runtime "$host" "$source_binding" "$source_pid"
    source_runtime_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$source_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    source_manifest="$case_core/sessions/$source_runtime_id/manifest.yaml"
    python3 - "$source_manifest" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
for key in ("task_id", "top_goal", "confirmed_hash"):
    text = re.sub(rf'^{key}:\s*.*\n?', '', text, flags=re.MULTILINE)
path.write_text(text, encoding="utf-8")
PY
    redcap_runtime_clear_process_claim "$host" "$source_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context

    write_workboard_fixture "$target_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    target_binding="acceptance-source-metadata-target-${RANDOM}-$$"
    target_pid="$((80000 + RANDOM))"
    init_bound_runtime "$host" "$target_binding" "$target_pid"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null

    if REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" import "$source_workboard" "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null 2>&1; then
        fail "source with missing manifest metadata unexpectedly imported"
    fi

    redcap_runtime_clear_process_claim "$host" "$target_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_continuity_import_requires_target_manifest_case() {
    local host="claude"
    local source_binding source_pid target_binding target_pid
    local target_runtime_id target_manifest
    local case_root case_core
    local source_dir target_dir source_workboard target_workboard
    local task_id top_goal active_slice confirmed_hash

    log "case: continuity-import-requires-target-manifest"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/continuity-import-requires-target-manifest"
    case_core="$CONTINUITY_CORE_DIR/continuity-import-requires-target-manifest"
    source_dir="$case_root/source-host/source-session"
    target_dir="$case_root/target-host/target-session"
    source_workboard="$source_dir/plan.md"
    target_workboard="$target_dir/plan.md"

    write_workboard_fixture "$source_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$source_dir/files"
    printf 'source own record\n' >"$source_dir/files/note.txt"
    source_binding="acceptance-target-manifest-source-${RANDOM}-$$"
    source_pid="$((77000 + RANDOM))"
    init_bound_runtime "$host" "$source_binding" "$source_pid"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$source_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    redcap_runtime_clear_process_claim "$host" "$source_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context

    write_workboard_fixture "$target_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    target_binding="acceptance-target-manifest-target-${RANDOM}-$$"
    target_pid="$((78000 + RANDOM))"
    init_bound_runtime "$host" "$target_binding" "$target_pid"
    target_runtime_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    target_manifest="$case_core/sessions/$target_runtime_id/manifest.yaml"
    rm -f "$target_manifest"

    if REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" import "$source_workboard" "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null 2>&1; then
        fail "target without manifest unexpectedly imported"
    fi

    redcap_runtime_clear_process_claim "$host" "$target_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_continuity_import_rejects_foreign_runtime_case() {
    local source_host="claude"
    local target_host="copilot"
    local source_binding source_pid
    local case_root case_core
    local source_dir target_dir source_workboard target_workboard
    local task_id top_goal active_slice confirmed_hash

    log "case: continuity-import-rejects-foreign-runtime"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/continuity-import-rejects-foreign-runtime"
    case_core="$CONTINUITY_CORE_DIR/continuity-import-rejects-foreign-runtime"
    source_dir="$case_root/source-host/source-session"
    target_dir="$case_root/target-host/target-session"
    source_workboard="$source_dir/plan.md"
    target_workboard="$target_dir/plan.md"

    write_workboard_fixture "$source_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$source_dir/files"
    printf 'source own record\n' >"$source_dir/files/note.txt"
    source_binding="acceptance-foreign-runtime-source-${RANDOM}-$$"
    source_pid="$((76000 + RANDOM))"
    init_bound_runtime "$source_host" "$source_binding" "$source_pid"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$source_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null

    write_workboard_fixture "$target_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    printf '{}' | \
        REDCAP_HOOK_CWD="$REDCAP_ROOT" \
        REDCAP_HOST_WORKBOARD_PATH="$target_workboard" \
        REDCAP_CONTINUITY_ROOT_DIR="$case_core" \
        REDCAP_HOST_PROCESS_PID="$$" \
        bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$target_host" >/dev/null

    assert_eq "$(workboard_value "$target_workboard" "continuity_authority")" "degraded-no-runtime-manifest"
    assert_eq "$(workboard_value "$target_workboard" "runtime_session_id")" "unknown"
    if REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" import "$source_workboard" "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null 2>&1; then
        fail "foreign runtime unexpectedly imported into degraded target"
    fi

    redcap_runtime_clear_process_claim "$source_host" "$source_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_continuity_import_rejects_target_runtime_mismatch_case() {
    local host="claude"
    local source_binding target_binding foreign_binding
    local source_pid target_pid foreign_pid
    local case_root case_core
    local source_dir target_dir source_workboard target_workboard
    local task_id top_goal active_slice confirmed_hash
    local target_runtime_id target_manifest import_stderr

    log "case: continuity-import-rejects-target-runtime-mismatch"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/continuity-import-rejects-target-runtime-mismatch"
    case_core="$CONTINUITY_CORE_DIR/continuity-import-rejects-target-runtime-mismatch"
    source_dir="$case_root/source-host/source-session"
    target_dir="$case_root/target-host/target-session"
    source_workboard="$source_dir/plan.md"
    target_workboard="$target_dir/plan.md"
    import_stderr="$case_root/import.err"

    write_workboard_fixture "$source_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$source_dir/files"
    printf 'source own record\n' >"$source_dir/files/note.txt"
    source_binding="acceptance-target-runtime-mismatch-source-${RANDOM}-$$"
    source_pid="$((79000 + RANDOM))"
    init_bound_runtime "$host" "$source_binding" "$source_pid"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$source_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null

    write_workboard_fixture "$target_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    target_binding="acceptance-target-runtime-mismatch-target-${RANDOM}-$$"
    target_pid="$((79500 + RANDOM))"
    init_bound_runtime "$host" "$target_binding" "$target_pid"
    target_runtime_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null

    target_manifest="$case_core/sessions/$target_runtime_id/manifest.yaml"
    assert_exists "$target_manifest"
    assert_eq "$(workboard_value "$target_workboard" "runtime_session_id")" "$target_runtime_id"
    assert_eq "$(workboard_value "$target_workboard" "continuity_state")" "import-suggested"
    assert_eq "$(workboard_value "$target_workboard" "import_ready_signal")" "ready"

    foreign_binding="acceptance-target-runtime-mismatch-foreign-${RANDOM}-$$"
    foreign_pid="$((79900 + RANDOM))"
    init_bound_runtime "$host" "$foreign_binding" "$foreign_pid"

    if REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" import "$source_workboard" "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null 2>"$import_stderr"; then
        fail "foreign full runtime unexpectedly imported into mismatched target session"
    fi

    assert_string_contains "$(cat "$import_stderr")" "target workboard runtime mismatch"
    assert_eq "$(workboard_value "$target_workboard" "runtime_session_id")" "$target_runtime_id"
    assert_eq "$(workboard_value "$target_workboard" "continuity_state")" "import-suggested"
    assert_eq "$(manifest_value "$target_manifest" "runtime_session_id")" "$target_runtime_id"
    assert_eq "$(manifest_value "$target_manifest" "import_ready_signal")" "ready"

    redcap_runtime_clear_process_claim "$host" "$source_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_process_claim "$host" "$target_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_process_claim "$host" "$foreign_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_continuity_import_rejects_relay_source_case() {
    local host="claude"
    local source_binding relay_binding target_binding
    local source_pid relay_pid target_pid
    local case_root case_core
    local source_dir relay_dir target_dir source_workboard relay_workboard target_workboard
    local task_id top_goal active_slice confirmed_hash

    log "case: continuity-import-rejects-relay-source"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/continuity-import-rejects-relay-source"
    case_core="$CONTINUITY_CORE_DIR/continuity-import-rejects-relay-source"
    source_dir="$case_root/source-host/source-session"
    relay_dir="$case_root/relay-host/relay-session"
    target_dir="$case_root/target-host/target-session"
    source_workboard="$source_dir/plan.md"
    relay_workboard="$relay_dir/plan.md"
    target_workboard="$target_dir/plan.md"

    write_workboard_fixture "$source_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$source_dir/files"
    printf 'source own record\n' >"$source_dir/files/note.txt"
    source_binding="acceptance-relay-source-${RANDOM}-$$"
    source_pid="$((81000 + RANDOM))"
    init_bound_runtime "$host" "$source_binding" "$source_pid"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$source_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    redcap_runtime_clear_process_claim "$host" "$source_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context

    write_workboard_fixture "$relay_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    relay_binding="acceptance-relay-middle-${RANDOM}-$$"
    relay_pid="$((82000 + RANDOM))"
    init_bound_runtime "$host" "$relay_binding" "$relay_pid"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$relay_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" import "$source_workboard" "$relay_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    assert_eq "$(workboard_value "$relay_workboard" "continuity_state")" "imported"
    redcap_runtime_clear_process_claim "$host" "$relay_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context

    write_workboard_fixture "$target_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    target_binding="acceptance-relay-target-${RANDOM}-$$"
    target_pid="$((83000 + RANDOM))"
    init_bound_runtime "$host" "$target_binding" "$target_pid"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null

    if REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" import "$relay_workboard" "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null 2>&1; then
        fail "relay-imported source unexpectedly re-exported"
    fi

    redcap_runtime_clear_process_claim "$host" "$target_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_continuity_import_rejects_imported_own_record_source_case() {
    local host="claude"
    local source_binding relay_binding target_binding
    local source_pid relay_pid target_pid
    local relay_runtime_id source_runtime_id
    local case_root case_core
    local source_dir relay_dir target_dir source_workboard relay_workboard target_workboard source_manifest
    local task_id top_goal active_slice confirmed_hash

    log "case: continuity-import-rejects-imported-own-record-source"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/continuity-import-rejects-imported-own-record-source"
    case_core="$CONTINUITY_CORE_DIR/continuity-import-rejects-imported-own-record-source"
    source_dir="$case_root/source-host/source-session"
    relay_dir="$case_root/relay-host/relay-session"
    target_dir="$case_root/target-host/target-session"
    source_workboard="$source_dir/plan.md"
    relay_workboard="$relay_dir/plan.md"
    target_workboard="$target_dir/plan.md"

    write_workboard_fixture "$source_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$source_dir/files"
    printf 'source own record\n' >"$source_dir/files/note.txt"
    source_binding="acceptance-hybrid-source-${RANDOM}-$$"
    source_pid="$((83500 + RANDOM))"
    init_bound_runtime "$host" "$source_binding" "$source_pid"
    source_runtime_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$source_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    source_manifest="$case_core/sessions/$source_runtime_id/manifest.yaml"
    redcap_runtime_clear_process_claim "$host" "$source_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context

    write_workboard_fixture "$relay_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    relay_binding="acceptance-hybrid-relay-${RANDOM}-$$"
    relay_pid="$((84500 + RANDOM))"
    init_bound_runtime "$host" "$relay_binding" "$relay_pid"
    relay_runtime_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$relay_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" import "$source_workboard" "$relay_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    mkdir -p "$relay_dir/files/local"
    printf 'relay own record\n' >"$relay_dir/files/local/note.txt"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$relay_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    assert_eq "$(workboard_value "$relay_workboard" "continuity_state")" "imported"
    assert_eq "$(manifest_value "$case_core/sessions/$relay_runtime_id/manifest.yaml" "own_record_present")" "1"
    rm -f "$source_manifest"
    redcap_runtime_clear_process_claim "$host" "$relay_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context

    write_workboard_fixture "$target_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    target_binding="acceptance-hybrid-target-${RANDOM}-$$"
    target_pid="$((85500 + RANDOM))"
    init_bound_runtime "$host" "$target_binding" "$target_pid"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    assert_eq "$(workboard_value "$target_workboard" "continuity_state")" "fresh-session"
    assert_eq "$(workboard_value "$target_workboard" "suggested_source_session_handle")" ""

    if REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" import "$relay_workboard" "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null 2>&1; then
        fail "imported source with own record unexpectedly re-exported"
    fi

    redcap_runtime_clear_process_claim "$host" "$target_pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_continuity_import_resolves_live_manifest_case() {
    local host="claude"
    local source_binding_one source_binding_two target_binding_one target_binding_two
    local source_pid_one source_pid_two target_pid_one target_pid_two
    local source_runtime_one source_runtime_two target_runtime_two
    local case_root case_core
    local source_dir target_dir source_workboard target_workboard target_manifest import_output
    local task_id top_goal active_slice confirmed_hash

    log "case: continuity-import-resolves-live-manifest"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/continuity-import-resolves-live-manifest"
    case_core="$CONTINUITY_CORE_DIR/continuity-import-resolves-live-manifest"
    source_dir="$case_root/source-host/source-session"
    target_dir="$case_root/target-host/target-session"
    source_workboard="$source_dir/plan.md"
    target_workboard="$target_dir/plan.md"

    write_workboard_fixture "$source_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    mkdir -p "$source_dir/files"
    printf 'source own record\n' >"$source_dir/files/note.txt"
    source_binding_one="acceptance-live-source-one-${RANDOM}-$$"
    source_pid_one="$((86500 + RANDOM))"
    init_bound_runtime "$host" "$source_binding_one" "$source_pid_one"
    source_runtime_one="${REDCAP_RUNTIME_SESSION_ID:-}"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$source_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    redcap_runtime_clear_process_claim "$host" "$source_pid_one" >/dev/null 2>&1 || true
    redcap_runtime_clear_context

    source_binding_two="acceptance-live-source-two-${RANDOM}-$$"
    source_pid_two="$((87500 + RANDOM))"
    init_bound_runtime "$host" "$source_binding_two" "$source_pid_two"
    source_runtime_two="${REDCAP_RUNTIME_SESSION_ID:-}"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$source_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    assert_exists "$case_core/sessions/$source_runtime_one/manifest.yaml"
    redcap_runtime_clear_process_claim "$host" "$source_pid_two" >/dev/null 2>&1 || true
    redcap_runtime_clear_context

    write_workboard_fixture "$target_workboard" "$REDCAP_ROOT/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"
    target_binding_one="acceptance-live-target-one-${RANDOM}-$$"
    target_pid_one="$((88500 + RANDOM))"
    init_bound_runtime "$host" "$target_binding_one" "$target_pid_one"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null
    redcap_runtime_clear_process_claim "$host" "$target_pid_one" >/dev/null 2>&1 || true
    redcap_runtime_clear_context

    target_binding_two="acceptance-live-target-two-${RANDOM}-$$"
    target_pid_two="$((89500 + RANDOM))"
    init_bound_runtime "$host" "$target_binding_two" "$target_pid_two"
    target_runtime_two="${REDCAP_RUNTIME_SESSION_ID:-}"
    REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" sync "$target_workboard" "$REDCAP_ROOT/.dev-task.md" >/dev/null

    import_output="$(REDCAP_CONTINUITY_ROOT_DIR="$case_core" bash "$SCRIPT_DIR/redcap-session-continuity.sh" import "$source_workboard" "$target_workboard" "$REDCAP_ROOT/.dev-task.md")"
    target_manifest="$case_core/sessions/$target_runtime_two/manifest.yaml"
    assert_eq "$(manifest_value "$target_manifest" "runtime_session_id")" "$target_runtime_two"
    assert_eq "$(manifest_value "$target_manifest" "source_runtime_session_id")" "$source_runtime_two"
    assert_string_contains "$import_output" "\"target_runtime_session_id\": \"$target_runtime_two\""

    redcap_runtime_clear_process_claim "$host" "$target_pid_two" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_all_cases() {
    run_binding_recovery_gate_case
    run_layerb_concurrency_case
    run_copilot_safe_degraded_case
    run_session_resume_gate_claude_full_case
    run_session_resume_gate_gemini_full_case
    run_session_resume_gate_copilot_full_case
    run_session_resume_gate_error_safe_fail_case
    run_session_resume_gate_unsupported_host_case
    run_cross_layer_visibility_case
    run_layera_legacy_quarantine_case
    run_prism_concurrency_case
    run_prism_legacy_bridge_case
    run_report_register_requires_claim_case
    run_sessionstart_auto_reconcile_rewrite_case
    run_sessionstart_auto_reconcile_clear_case
    run_sessionstart_auto_reconcile_hash_mismatch_case
    run_sessionstart_runtime_init_failed_degrades_case
    run_continuity_manifest_sync_case
    run_continuity_runtime_required_case
    run_continuity_runtime_claim_requires_live_process_case
    run_continuity_manifest_only_discovery_case
    run_continuity_discovery_requires_source_metadata_case
    run_continuity_manifest_import_case
    run_continuity_cross_host_import_case
    run_continuity_manifest_mismatch_case
    run_continuity_stale_import_case
    run_continuity_stale_import_requires_source_metadata_case
    run_continuity_rejects_stale_source_manifest_case
    run_continuity_import_requires_source_manifest_case
    run_continuity_import_requires_source_metadata_case
    run_continuity_import_requires_target_manifest_case
    run_continuity_import_rejects_foreign_runtime_case
    run_continuity_import_rejects_target_runtime_mismatch_case
    run_continuity_import_rejects_relay_source_case
    run_continuity_import_rejects_imported_own_record_source_case
    run_continuity_import_resolves_live_manifest_case
}

COMMAND="${1:-all}"

case "$COMMAND" in
    all)
        run_all_cases
        ;;
    binding-recovery-gate)
        run_binding_recovery_gate_case
        ;;
    layerb-concurrency)
        run_layerb_concurrency_case
        ;;
    copilot-safe-degraded)
        run_copilot_safe_degraded_case
        ;;
    cross-layer-visibility)
        run_cross_layer_visibility_case
        ;;
    layera-legacy-quarantine)
        run_layera_legacy_quarantine_case
        ;;
    prism-concurrency)
        run_prism_concurrency_case
        ;;
    prism-legacy-bridge)
        run_prism_legacy_bridge_case
        ;;
    report-register-requires-claim)
        run_report_register_requires_claim_case
        ;;
    sessionstart-auto-reconcile-rewrite)
        run_sessionstart_auto_reconcile_rewrite_case
        ;;
    sessionstart-auto-reconcile-clear)
        run_sessionstart_auto_reconcile_clear_case
        ;;
    sessionstart-auto-reconcile-hash-mismatch)
        run_sessionstart_auto_reconcile_hash_mismatch_case
        ;;
    sessionstart-runtime-init-failed-degrades)
        run_sessionstart_runtime_init_failed_degrades_case
        ;;
    continuity-manifest-sync)
        run_continuity_manifest_sync_case
        ;;
    continuity-runtime-required)
        run_continuity_runtime_required_case
        ;;
    continuity-runtime-claim-requires-live-process)
        run_continuity_runtime_claim_requires_live_process_case
        ;;
    continuity-manifest-only-discovery)
        run_continuity_manifest_only_discovery_case
        ;;
    continuity-discovery-requires-source-metadata)
        run_continuity_discovery_requires_source_metadata_case
        ;;
    continuity-manifest-import)
        run_continuity_manifest_import_case
        ;;
    continuity-cross-host-import)
        run_continuity_cross_host_import_case
        ;;
    continuity-manifest-mismatch)
        run_continuity_manifest_mismatch_case
        ;;
    continuity-stale-import)
        run_continuity_stale_import_case
        ;;
    continuity-stale-import-requires-source-metadata)
        run_continuity_stale_import_requires_source_metadata_case
        ;;
    continuity-rejects-stale-source-manifest)
        run_continuity_rejects_stale_source_manifest_case
        ;;
    continuity-import-requires-source-manifest)
        run_continuity_import_requires_source_manifest_case
        ;;
    continuity-import-requires-source-metadata)
        run_continuity_import_requires_source_metadata_case
        ;;
    continuity-import-requires-target-manifest)
        run_continuity_import_requires_target_manifest_case
        ;;
    continuity-import-rejects-foreign-runtime)
        run_continuity_import_rejects_foreign_runtime_case
        ;;
    continuity-import-rejects-target-runtime-mismatch)
        run_continuity_import_rejects_target_runtime_mismatch_case
        ;;
    continuity-import-rejects-relay-source)
        run_continuity_import_rejects_relay_source_case
        ;;
    continuity-import-rejects-imported-own-record-source)
        run_continuity_import_rejects_imported_own_record_source_case
        ;;
    continuity-import-resolves-live-manifest)
        run_continuity_import_resolves_live_manifest_case
        ;;
    session-resume-gate-claude-full)
        run_session_resume_gate_claude_full_case
        ;;
    session-resume-gate-gemini-full)
        run_session_resume_gate_gemini_full_case
        ;;
    session-resume-gate-copilot-full)
        run_session_resume_gate_copilot_full_case
        ;;
    session-resume-gate-error-safe-fail)
        run_session_resume_gate_error_safe_fail_case
        ;;
    session-resume-gate-unsupported-host)
        run_session_resume_gate_unsupported_host_case
        ;;
    *)
        usage
        exit 2
        ;;
esac

echo "ACCEPTANCE_OK"

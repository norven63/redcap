#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/redcap-runtime-state.sh"
redcap_runtime_clear_context
unset REDCAP_RUNTIME_ALLOW_DISK_RECOVERY REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY REDCAP_RUNTIME_CAPABILITY 2>/dev/null || true

ACCEPT_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/redcap-acceptance.XXXXXX")"
export REDCAP_RUNTIME_BASE_DIR="$ACCEPT_ROOT/runtime"
export REDCAP_RUNTIME_INDEX_DIR="$ACCEPT_ROOT/runtime-index"
export REDCAP_RUNTIME_PROJECT_BASE_DIR="$ACCEPT_ROOT/project"
export REDCAP_RUNTIME_PROCESS_CLAIM_DIR="$ACCEPT_ROOT/process-claims"

LEGACY_REGISTRY_FILE="$REDCAP_ROOT/prism/reports/.session-registry.yaml"
LEGACY_REGISTRY_BACKUP=""
TEMP_PROJECTS=()
LEGACY_TMP_FILES=()

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

assert_ne() {
    [[ "$1" != "$2" ]] || fail "expected '$1' != '$2'"
}

assert_num_eq() {
    [[ "$1" =~ ^[0-9]+$ ]] || fail "expected numeric value, got: $1"
    [[ "$2" =~ ^[0-9]+$ ]] || fail "expected numeric value, got: $2"
    [[ "$1" -eq "$2" ]] || fail "expected $1 -eq $2"
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
    local status=0

    set +e
    REDCAP_HOST_PROCESS_PID="$host_process_pid" \
    REDCAP_RUNTIME_ALLOW_DISK_RECOVERY=1 \
    REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY=1 \
    redcap_runtime_load_from_binding "$host" "$project_root" "$binding_key"
    status=$?
    set -e
    unset REDCAP_HOST_PROCESS_PID REDCAP_RUNTIME_ALLOW_DISK_RECOVERY REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY
    return "$status"
}

read_file_text() {
    local path="$1"
    [[ -f "$path" ]] || fail "expected file to exist: $path"
    cat "$path"
}

extract_output_value() {
    local output="$1"
    local key="$2"

    printf '%s\n' "$output" | sed -n "s/^${key}=//p" | head -1
}

git_previous_head() {
    git -C "$REDCAP_ROOT" rev-parse HEAD~1 2>/dev/null || git -C "$REDCAP_ROOT" rev-parse HEAD
}

make_temp_project() {
    local dir
    dir="$(mktemp -d "${TMPDIR:-/tmp}/redcap-layera-project.XXXXXX")"
    TEMP_PROJECTS+=("$dir")
    printf '%s\n' "$dir"
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
    local binding_a binding_b pid_a pid_b
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

        printf '{}' | REDCAP_SESSION_BINDING_KEY="$binding_a" REDCAP_HOST_PROCESS_PID="$pid_a" bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$host" >/dev/null
        printf '{}' | REDCAP_SESSION_BINDING_KEY="$binding_b" REDCAP_HOST_PROCESS_PID="$pid_b" bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$host" >/dev/null

        attach_binding_with_capability_recovery "$host" "$REDCAP_ROOT" "$binding_a" "$pid_a" || fail "failed to attach first $host session"
        session_a="${REDCAP_RUNTIME_SESSION_ID:-}"
        report_marker_a="$(redcap_runtime_path "layerB/current-report-path")"
        redcap_runtime_write_text "layerB/current-report-path" "acceptance/${host}/a.md" || fail "failed to write first report marker"
        redcap_runtime_write_text "layerB/initial-head" "$baseline" || fail "failed to write first baseline"
        redcap_runtime_clear_context

        attach_binding_with_capability_recovery "$host" "$REDCAP_ROOT" "$binding_b" "$pid_b" || fail "failed to attach second $host session"
        session_b="${REDCAP_RUNTIME_SESSION_ID:-}"
        report_marker_b="$(redcap_runtime_path "layerB/current-report-path")"
        redcap_runtime_write_text "layerB/current-report-path" "acceptance/${host}/b.md" || fail "failed to write second report marker"
        redcap_runtime_write_text "layerB/initial-head" "$baseline" || fail "failed to write second baseline"
        assert_ne "$session_a" "$session_b"
        assert_ne "$report_marker_a" "$report_marker_b"
        assert_eq "$(read_file_text "$report_marker_b")" "acceptance/${host}/b.md"
        redcap_runtime_clear_context

        attach_binding_with_capability_recovery "$host" "$REDCAP_ROOT" "$binding_a" "$pid_a" || fail "failed to reattach first $host session"
        assert_eq "$(read_file_text "$report_marker_a")" "acceptance/${host}/a.md"
        redcap_runtime_clear_context

        REDCAP_SESSION_BINDING_KEY="$binding_a" REDCAP_HOST_PROCESS_PID="$pid_a" REDCAP_SKIP_FEISHU=1 REDCAP_SKIP_INDEPENDENT_REVIEW=1 bash "$SCRIPT_DIR/redcap-layerB-session-end.sh" "$host" >/dev/null
        REDCAP_SESSION_BINDING_KEY="$binding_b" REDCAP_HOST_PROCESS_PID="$pid_b" REDCAP_SKIP_FEISHU=1 REDCAP_SKIP_INDEPENDENT_REVIEW=1 bash "$SCRIPT_DIR/redcap-layerB-session-end.sh" "$host" >/dev/null

        attach_binding_with_capability_recovery "$host" "$REDCAP_ROOT" "$binding_a" "$pid_a" || fail "failed to reattach first $host session after session-end"
        alerted_a="$(redcap_runtime_path "layerB/alerted-head")"
        assert_eq "$(read_file_text "$alerted_a")" "$current_head"
        redcap_runtime_clear_context

        attach_binding_with_capability_recovery "$host" "$REDCAP_ROOT" "$binding_b" "$pid_b" || fail "failed to reattach second $host session after session-end"
        alerted_b="$(redcap_runtime_path "layerB/alerted-head")"
        assert_eq "$(read_file_text "$alerted_b")" "$current_head"
        redcap_runtime_clear_context
    done
}

run_copilot_safe_degraded_case() {
    local compat_prefix degraded_file before after expected
    local suffix

    log "case: copilot-safe-degraded"

    compat_prefix="$(redcap_runtime_compat_path_for_root "$REDCAP_ROOT" "legacy-fallback/layerB-copilot")"
    degraded_file="$(redcap_runtime_compat_path_for_root "$REDCAP_ROOT" "degraded-mode.count")"
    before="$(counter_value "$degraded_file")"

    printf '{}' | REDCAP_HOOK_CWD="$REDCAP_ROOT" REDCAP_HOST_PROCESS_PID="$$" bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" copilot >/dev/null
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
    local layera_pid layerb_pid layerb_binding
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

    printf '{"session_id":"%s","cwd":"%s"}\n' "$layera_session_id" "$project_dir" | REDCAP_HOST_PROCESS_PID="$layera_pid" bash "$REDCAP_ROOT/loom/tools/redcap-layerA-session-start.sh" >/dev/null
    printf '{}' | REDCAP_SESSION_BINDING_KEY="$layerb_binding" REDCAP_HOST_PROCESS_PID="$layerb_pid" bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" claude >/dev/null

    attach_binding_with_capability_recovery "claude" "$project_dir" "$layera_binding" "$layera_pid" || fail "failed to attach Layer A runtime"
    layera_session_runtime="${REDCAP_RUNTIME_SESSION_DIR:-}"
    layera_owner_file="$(redcap_runtime_project_path_for_root "$project_dir" "layerA/workflow-owner-session")"
    layera_head_file="$(redcap_runtime_path "layerA/head")"
    layera_check_file="$(redcap_runtime_path "layerA/ownership-check")"
    assert_exists "$layera_owner_file"
    assert_exists "$layera_head_file"
    assert_exists "$layera_check_file"
    redcap_runtime_clear_context

    attach_binding_with_capability_recovery "claude" "$REDCAP_ROOT" "$layerb_binding" "$layerb_pid" || fail "failed to attach Layer B runtime"
    layerb_session_runtime="${REDCAP_RUNTIME_SESSION_DIR:-}"
    layerb_head_file="$(redcap_runtime_path "layerB/initial-head")"
    assert_exists "$layerb_head_file"
    assert_ne "$layera_session_runtime" "$layerb_session_runtime"
    assert_not_exists "$layerb_session_runtime/layerA/head"
    assert_not_exists "$layerb_session_runtime/layerA/ownership-check"
    redcap_runtime_clear_context

    if attach_binding_with_capability_recovery "claude" "$REDCAP_ROOT" "$layera_binding" "$layera_pid" >/dev/null 2>&1; then
        fail "Layer A binding unexpectedly reattached under Layer B project root"
    fi
    if attach_binding_with_capability_recovery "claude" "$project_dir" "$layerb_binding" "$layerb_pid" >/dev/null 2>&1; then
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
    local host_pid binding_key run_a run_b
    local raw_a parsed_a raw_b parsed_b
    local output collect_a collect_b handle_a handle_b

    log "case: prism-concurrency"

    host_pid="$((30000 + RANDOM))"
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

    printf '{}' | REDCAP_SESSION_BINDING_KEY="$binding_key" REDCAP_HOST_PROCESS_PID="$host_pid" bash "$SCRIPT_DIR/redcap-layerB-session-start.sh" "$host" >/dev/null

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

run_all_cases() {
    run_binding_recovery_gate_case
    run_layerb_concurrency_case
    run_copilot_safe_degraded_case
    run_cross_layer_visibility_case
    run_layera_legacy_quarantine_case
    run_prism_concurrency_case
    run_prism_legacy_bridge_case
    run_report_register_requires_claim_case
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
    *)
        usage
        exit 2
        ;;
esac

echo "ACCEPTANCE_OK"

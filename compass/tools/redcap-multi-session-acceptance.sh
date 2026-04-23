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
  bash compass/tools/redcap-multi-session-acceptance.sh copilot-wrapper-identity-anchor
  bash compass/tools/redcap-multi-session-acceptance.sh copilot-session-context-rejects-ambiguous-locks
  bash compass/tools/redcap-multi-session-acceptance.sh cross-layer-visibility
  bash compass/tools/redcap-multi-session-acceptance.sh layera-legacy-quarantine
  bash compass/tools/redcap-multi-session-acceptance.sh prism-concurrency
  bash compass/tools/redcap-multi-session-acceptance.sh prism-legacy-bridge
  bash compass/tools/redcap-multi-session-acceptance.sh report-register-requires-claim
  bash compass/tools/redcap-multi-session-acceptance.sh report-register-accepts-explicit-runtime-env
  bash compass/tools/redcap-multi-session-acceptance.sh report-register-rejects-ambiguous-explicit-runtime
  bash compass/tools/redcap-multi-session-acceptance.sh report-register-prefers-live-claim-over-stale-explicit-runtime
  bash compass/tools/redcap-multi-session-acceptance.sh report-register-rejects-foreign-explicit-runtime
  bash compass/tools/redcap-multi-session-acceptance.sh report-register-replaces-pending-artifact
  bash compass/tools/redcap-multi-session-acceptance.sh report-register-rejects-traversal-artifact
  bash compass/tools/redcap-multi-session-acceptance.sh report-register-rejects-symlinked-report-root
  bash compass/tools/redcap-multi-session-acceptance.sh sessionstart-auto-reconcile-rewrite
  bash compass/tools/redcap-multi-session-acceptance.sh sessionstart-auto-reconcile-normalizes-absolute-artifact
  bash compass/tools/redcap-multi-session-acceptance.sh sessionstart-auto-reconcile-clear
  bash compass/tools/redcap-multi-session-acceptance.sh sessionstart-auto-reconcile-hash-mismatch
  bash compass/tools/redcap-multi-session-acceptance.sh sessionstart-auto-reconcile-backlog-spec
  bash compass/tools/redcap-multi-session-acceptance.sh task-complete-guard-triggers-closeout-runtime
  bash compass/tools/redcap-multi-session-acceptance.sh layerb-closeout-runtime-promise-ledger-blocks
  bash compass/tools/redcap-multi-session-acceptance.sh prism-acceptance-binding-required
  bash compass/tools/redcap-multi-session-acceptance.sh layerb-closeout-runtime-complete-writes-receipt
  bash compass/tools/redcap-multi-session-acceptance.sh layerb-closeout-runtime-session-end-failure-writes-pending
  bash compass/tools/redcap-multi-session-acceptance.sh layerb-closeout-runtime-audit-open-repairs-receipt
  bash compass/tools/redcap-multi-session-acceptance.sh layerb-closeout-runtime-audit-open-blocks-unresolved
  bash compass/tools/redcap-multi-session-acceptance.sh layerb-closeout-runtime-audit-open-preserves-existing-blockers
  bash compass/tools/redcap-multi-session-acceptance.sh diagnose-auto-repairs-closeout-receipt
  bash compass/tools/redcap-multi-session-acceptance.sh closeout-cap-root-entry-basic-commands
  bash compass/tools/redcap-multi-session-acceptance.sh task-complete-guard-avoids-ambiguous-reports
  bash compass/tools/redcap-multi-session-acceptance.sh task-complete-guard-skips-stale-pending-artifact
  bash compass/tools/redcap-multi-session-acceptance.sh task-complete-guard-normalizes-absolute-pending-anchor
  bash compass/tools/redcap-multi-session-acceptance.sh on-complete-records-backlog-spec-redlines
  bash compass/tools/redcap-multi-session-acceptance.sh pending-closure-clear-restores-on-ledger-failure
  bash compass/tools/redcap-multi-session-acceptance.sh session-end-clears-all-matching-pending-states
  bash compass/tools/redcap-multi-session-acceptance.sh session-end-clears-compatible-pending-refresh
  bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-prefers-anchor
  bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-allows-marker-anchor-when-uniquely-latest
  bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-allows-pending-anchor-when-uniquely-latest
  bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-rejects-stale-pending-anchor-conflict
  bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-requires-summary-for-untracked-anchor
  bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-accepts-legacy-pending-anchor
  bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-rejects-stale-marker-conflict
  bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-rejects-zero-diff-stale-marker
  bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-ignores-invalid-pending-artifact
  bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-ignores-traversal-anchor
  bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-normalizes-absolute-pending-anchor
  bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-rejects-symlink-report-escape
  bash compass/tools/redcap-multi-session-acceptance.sh task-complete-guard-replaces-stale-marker-with-unique-report
  bash compass/tools/redcap-multi-session-acceptance.sh task-complete-guard-serializes-on-complete
  bash compass/tools/redcap-multi-session-acceptance.sh task-complete-guard-prunes-stale-lock
  bash compass/tools/redcap-multi-session-acceptance.sh task-complete-guard-keeps-live-legacy-lock
  bash compass/tools/redcap-multi-session-acceptance.sh task-complete-guard-prunes-reused-pid-lock
  bash compass/tools/redcap-multi-session-acceptance.sh task-complete-guard-retries-after-report-change
  bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-falls-back-to-codex-after-unavailable-reviewers
  bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-prefers-codex-for-codex-host
  bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-records-unavailable-rate-limit
  bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-rejects-invalid-track-structure
  bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-skips-prompt-only-reviewer-when-repo-inspection-required
  bash compass/tools/redcap-multi-session-acceptance.sh session-end-success-notify-after-clear
  bash compass/tools/redcap-multi-session-acceptance.sh session-end-notify-timeout-releases-lock
  bash compass/tools/redcap-multi-session-acceptance.sh session-end-blocked-rewrite-keeps-report-anchor
  bash compass/tools/redcap-multi-session-acceptance.sh session-end-blocked-rewrite-normalizes-absolute-report-anchor
  bash compass/tools/redcap-multi-session-acceptance.sh pending-closure-lock-keeps-live-legacy-lock
  bash compass/tools/redcap-multi-session-acceptance.sh pending-closure-lock-prunes-reused-pid
  bash compass/tools/redcap-multi-session-acceptance.sh sessionstart-runtime-init-failed-degrades
  bash compass/tools/redcap-multi-session-acceptance.sh sessionstart-control-gate-failure-degrades
  bash compass/tools/redcap-multi-session-acceptance.sh runtime-clear-context-clears-probe-pid
  bash compass/tools/redcap-multi-session-acceptance.sh runtime-claim-parent-fallback
  bash compass/tools/redcap-multi-session-acceptance.sh artifact-lifecycle-classifier
  bash compass/tools/redcap-multi-session-acceptance.sh artifact-lifecycle-hook-install
  bash compass/tools/redcap-multi-session-acceptance.sh artifact-lifecycle-pre-commit-block
  bash compass/tools/redcap-multi-session-acceptance.sh artifact-lifecycle-pre-commit-allow
  bash compass/tools/redcap-multi-session-acceptance.sh artifact-lifecycle-rejects-tabbed-path
  bash compass/tools/redcap-multi-session-acceptance.sh docs-catalog-check
  bash compass/tools/redcap-multi-session-acceptance.sh docs-catalog-progressive-disclosure
  bash compass/tools/redcap-multi-session-acceptance.sh docs-retention-check
  bash compass/tools/redcap-multi-session-acceptance.sh backlog-check-strict
  bash compass/tools/redcap-multi-session-acceptance.sh current-status-overview
  bash compass/tools/redcap-multi-session-acceptance.sh tracking-health-overview
  bash compass/tools/redcap-multi-session-acceptance.sh install-overview
  bash compass/tools/redcap-multi-session-acceptance.sh execution-guarantees-check
  bash compass/tools/redcap-multi-session-acceptance.sh knowledge-index-check
  bash compass/tools/redcap-multi-session-acceptance.sh acceptance-index-check
  bash compass/tools/redcap-multi-session-acceptance.sh token-risk-audit
  bash compass/tools/redcap-multi-session-acceptance.sh contributing-ia-check
  bash compass/tools/redcap-multi-session-acceptance.sh review-tracks-check
  bash compass/tools/redcap-multi-session-acceptance.sh hook-contract-check
  bash compass/tools/redcap-multi-session-acceptance.sh runtime-helper-check
  bash compass/tools/redcap-multi-session-acceptance.sh cli-console-mirror-check
  bash compass/tools/redcap-multi-session-acceptance.sh revival-protocol-check
  bash compass/tools/redcap-multi-session-acceptance.sh diagnose-overview
  bash compass/tools/redcap-multi-session-acceptance.sh state-machine-contract-check
  bash compass/tools/redcap-multi-session-acceptance.sh on-qa-pass-blocks-inconsistent-state
  bash compass/tools/redcap-multi-session-acceptance.sh spec-registry-validates-repo
  bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures
  bash compass/tools/redcap-multi-session-acceptance.sh spec-check-rejects-superseded-outside-archive
  bash compass/tools/redcap-multi-session-acceptance.sh spec-check-requires-replaced-by
  bash compass/tools/redcap-multi-session-acceptance.sh spec-check-rejects-invalid-role
  bash compass/tools/redcap-multi-session-acceptance.sh spec-check-rejects-replacement-cycle
  bash compass/tools/redcap-multi-session-acceptance.sh spec-check-accepts-archived-superseded
  bash compass/tools/redcap-multi-session-acceptance.sh host-workboard-backlog-anchor
  bash compass/tools/redcap-multi-session-acceptance.sh cli-console-mirror-overwrites
  bash compass/tools/redcap-multi-session-acceptance.sh feishu-duplex-window-queue
  bash compass/tools/redcap-multi-session-acceptance.sh overlay-skill-handoff-stays-native
  bash compass/tools/redcap-multi-session-acceptance.sh overlay-governance-check
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
    local previous_host_process_pid="${REDCAP_HOST_PROCESS_PID:-}"
    local previous_host_process_probe_pid="${REDCAP_HOST_PROCESS_PROBE_PID:-}"
    local previous_allow_disk_recovery="${REDCAP_RUNTIME_ALLOW_DISK_RECOVERY:-}"
    local previous_allow_capability_recovery="${REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY:-}"
    local status=0

    export REDCAP_HOST_PROCESS_PID="$host_process_pid"
    if [[ -n "$host_process_probe_pid" ]]; then
        export REDCAP_HOST_PROCESS_PROBE_PID="$host_process_probe_pid"
    else
        unset REDCAP_HOST_PROCESS_PROBE_PID
    fi
    export REDCAP_RUNTIME_ALLOW_DISK_RECOVERY=1
    export REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY=1

    set +e
    redcap_runtime_load_from_binding "$host" "$project_root" "$binding_key"
    status=$?
    set -e

    if [[ -n "$previous_host_process_pid" ]]; then
        export REDCAP_HOST_PROCESS_PID="$previous_host_process_pid"
    else
        unset REDCAP_HOST_PROCESS_PID
    fi
    if [[ -n "$previous_host_process_probe_pid" ]]; then
        export REDCAP_HOST_PROCESS_PROBE_PID="$previous_host_process_probe_pid"
    else
        unset REDCAP_HOST_PROCESS_PROBE_PID
    fi
    if [[ -n "$previous_allow_disk_recovery" ]]; then
        export REDCAP_RUNTIME_ALLOW_DISK_RECOVERY="$previous_allow_disk_recovery"
    else
        unset REDCAP_RUNTIME_ALLOW_DISK_RECOVERY
    fi
    if [[ -n "$previous_allow_capability_recovery" ]]; then
        export REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY="$previous_allow_capability_recovery"
    else
        unset REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY
    fi

    return "$status"
}

read_file_text() {
    local path="$1"
    [[ -f "$path" ]] || fail "expected file to exist: $path"
    cat "$path"
}

assert_session_end_terminal_marker() {
    local current_head="$1"
    local label="${2:-session}"
    local marker_path marker_value

    marker_path="$(redcap_runtime_path "layerB/notified-head")"
    if [[ -f "$marker_path" ]]; then
        marker_value="$(read_file_text "$marker_path")"
        case "$marker_value" in
            "$current_head"|"$current_head|"*) return 0 ;;
            *) fail "unexpected notified marker for $label" ;;
        esac
    fi

    marker_path="$(redcap_runtime_path "layerB/alerted-head")"
    if [[ -f "$marker_path" ]]; then
        marker_value="$(read_file_text "$marker_path")"
        case "$marker_value" in
            "$current_head"|"$current_head|"*) return 0 ;;
            *) fail "unexpected alerted marker for $label" ;;
        esac
    fi

    fail "expected session-end terminal marker for $label"
}

write_current_report_marker_fixture() {
    local report_rel="$1"
    local task_file="${2:-$REDCAP_ROOT/.dev-task.md}"

    redcap_interop_write_current_report_marker "$report_rel" "$task_file" >/dev/null \
        || fail "failed to write current report marker: $report_rel"
}

write_current_report_marker_with_hash_fixture() {
    local report_rel="$1"
    local confirmed_hash="$2"
    local task_file="${3:-$REDCAP_ROOT/.dev-task.md}"
    local identity_path task_id active_slice

    task_file=$(redcap_dev_task_resolve_file "$task_file")
    task_id=$(redcap_dev_task_extract_kv "$task_file" "task_id" 2>/dev/null || true)
    active_slice=$(redcap_dev_task_extract_kv "$task_file" "active_slice" 2>/dev/null || true)
    [[ -n "$task_id" && -n "$active_slice" ]] || fail "failed to resolve current task metadata for marker fixture"

    redcap_runtime_write_text "layerB/current-report-path" "$report_rel" >/dev/null \
        || fail "failed to write raw current report marker: $report_rel"
    identity_path="$(redcap_runtime_path "layerB/current-report-identity")"
    [[ -n "$identity_path" ]] || fail "failed to resolve current report identity path"
    cat >"$identity_path" <<EOF
report_path: $report_rel
task_id: $task_id
confirmed_hash: $confirmed_hash
active_slice: $active_slice
updated_at: 2026-04-16T00:00:00Z
EOF
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

init_temp_git_repo() {
    local repo="$1"

    git -C "$repo" init --quiet
    git -C "$repo" config user.name "RedCap Acceptance"
    git -C "$repo" config user.email "redcap-acceptance@example.com"
}

seed_temp_git_repo() {
    local repo="$1"

    printf '# acceptance fixture\n' >"$repo/README.md"
    git -C "$repo" add README.md
    git -C "$repo" commit --quiet -m "init"
}

create_task_report_fixture_repo() {
    local repo="$1"

    mkdir -p "$repo"
    init_temp_git_repo "$repo"
    mkdir -p "$repo/compass/tools" "$repo/compass/docs/task-reports" "$repo/references"
    cp "$REDCAP_ROOT/.dev-task.md" "$repo/.dev-task.md"
    cp "$REDCAP_ROOT/compass/tools/redcap-task-report-check.sh" "$repo/compass/tools/redcap-task-report-check.sh"
    cp "$REDCAP_ROOT/compass/tools/redcap-task-report-register.sh" "$repo/compass/tools/redcap-task-report-register.sh"
    cp "$REDCAP_ROOT/compass/tools/redcap-layerB-task-complete-guard.sh" "$repo/compass/tools/redcap-layerB-task-complete-guard.sh"
    cp "$REDCAP_ROOT/compass/tools/redcap-pending-closure-reconcile.sh" "$repo/compass/tools/redcap-pending-closure-reconcile.sh"
    cp "$REDCAP_ROOT/compass/tools/redcap-runtime-state.sh" "$repo/compass/tools/redcap-runtime-state.sh"
    cp "$REDCAP_ROOT/compass/tools/redcap-interop-governance.sh" "$repo/compass/tools/redcap-interop-governance.sh"
    cp "$REDCAP_ROOT/compass/tools/redcap-dev-task.sh" "$repo/compass/tools/redcap-dev-task.sh"
    cp "$REDCAP_ROOT/compass/tools/redcap-validator-output.sh" "$repo/compass/tools/redcap-validator-output.sh"
    cp "$REDCAP_ROOT/references/task-report-template.md" "$repo/references/task-report-template.md"
    chmod +x \
        "$repo/compass/tools/redcap-task-report-check.sh" \
        "$repo/compass/tools/redcap-task-report-register.sh" \
        "$repo/compass/tools/redcap-layerB-task-complete-guard.sh" \
        "$repo/compass/tools/redcap-pending-closure-reconcile.sh"
    git -C "$repo" add .dev-task.md compass/tools
    git -C "$repo" commit --quiet -m "task-report fixture"
}

install_artifact_hook_fixture() {
    local repo="$1"

    mkdir -p "$repo/.githooks" "$repo/compass/tools" "$repo/compass/docs"
    cp "$REDCAP_ROOT/.githooks/pre-commit" "$repo/.githooks/pre-commit"
    cp "$REDCAP_ROOT/compass/tools/redcap-artifact-classifier.sh" "$repo/compass/tools/redcap-artifact-classifier.sh"
    cp "$REDCAP_ROOT/compass/tools/redcap-artifact-lifecycle-check.sh" "$repo/compass/tools/redcap-artifact-lifecycle-check.sh"
    cp "$REDCAP_ROOT/compass/tools/redcap-ensure-git-hooks.sh" "$repo/compass/tools/redcap-ensure-git-hooks.sh"
    cp "$REDCAP_ROOT/compass/docs/index.yaml" "$repo/compass/docs/index.yaml"
    chmod +x \
        "$repo/.githooks/pre-commit" \
        "$repo/compass/tools/redcap-artifact-classifier.sh" \
        "$repo/compass/tools/redcap-artifact-lifecycle-check.sh" \
        "$repo/compass/tools/redcap-ensure-git-hooks.sh"
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
    local outvar="${1:-}"
    local spawned_probe_pid

    sleep 600 >/dev/null 2>&1 &
    spawned_probe_pid=$!
    HOST_PROCESS_PROBES+=("$spawned_probe_pid")
    if [[ -n "$outvar" ]]; then
        printf -v "$outvar" '%s' "$spawned_probe_pid"
    else
        printf '%s\n' "$spawned_probe_pid"
    fi
}

init_bound_runtime() {
    local host="$1"
    local binding_key="$2"
    local host_process_pid="$3"
    local probe_pid

    spawn_host_probe probe_pid

    export REDCAP_HOST_PROCESS_PID="$host_process_pid"
    export REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid"
    redcap_runtime_init_from_binding "$host" "$REDCAP_ROOT" "$binding_key" >/dev/null \
        || fail "failed to initialize runtime binding for $host"
    REDCAP_SESSION_ISOLATION_MODE="full"
    export REDCAP_HOST_PROCESS_PID REDCAP_SESSION_ISOLATION_MODE REDCAP_RUNTIME_SESSION_ID REDCAP_RUNTIME_BINDING_KEY REDCAP_RUNTIME_HOST REDCAP_RUNTIME_CAPABILITY
    unset REDCAP_HOST_PROCESS_PROBE_PID
}

init_bound_runtime_for_repo() {
    local host="$1"
    local repo="$2"
    local binding_key="$3"
    local host_process_pid="$4"
    local probe_pid

    spawn_host_probe probe_pid

    export REDCAP_HOST_PROCESS_PID="$host_process_pid"
    export REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid"
    redcap_runtime_init_from_binding "$host" "$repo" "$binding_key" >/dev/null \
        || fail "failed to initialize runtime binding for $host fixture repo"
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

    export REDCAP_HOST_PROCESS_PID="$$"
    export REDCAP_RUNTIME_ALLOW_DISK_RECOVERY=1
    if redcap_runtime_load_from_binding "$host" "$REDCAP_ROOT" "$binding_key" >/dev/null 2>&1; then
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
    local session_a session_b report_marker_a report_marker_b

    log "case: layerb-concurrency"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "layerb-concurrency" >/dev/null 2>&1 || true

    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    baseline="$(git_previous_head)"
    [[ -n "$baseline" ]] || fail "failed to resolve baseline head for Layer B concurrency case"
    [[ "$baseline" != "$current_head" ]] || fail "layerB concurrency case requires repository history beyond HEAD"

    for host in claude gemini copilot; do
        binding_a="acceptance-${host}-a-${RANDOM}-$$"
        binding_b="acceptance-${host}-b-${RANDOM}-$$"
        pid_a="$((10000 + RANDOM))"
        pid_b="$((20000 + RANDOM))"
        spawn_host_probe probe_a
        spawn_host_probe probe_b

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
        assert_session_end_terminal_marker "$current_head" "first $host session"
        redcap_runtime_clear_context

        attach_binding_with_capability_recovery "$host" "$REDCAP_ROOT" "$binding_b" "$pid_b" "$probe_b" || fail "failed to reattach second $host session after session-end"
        assert_session_end_terminal_marker "$current_head" "second $host session"
        redcap_runtime_clear_context

        redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-cleanup" "layerb-concurrency" >/dev/null 2>&1 || true
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

run_copilot_wrapper_identity_anchor_case() {
    local case_name="copilot-wrapper-identity-anchor"
    local case_root case_core session_state_root session_handle session_dir workboard confirmed_hash
    local probe_pid binding_key runtime_id manifest degraded_file before after initial_head

    log "case: $case_name"

    case_root="$ACCEPT_ROOT/$case_name"
    case_core="$CONTINUITY_CORE_DIR/$case_name"
    session_state_root="$case_root/session-state"
    session_handle="acceptance-copilot-handle-${RANDOM}-$$"
    session_dir="$session_state_root/$session_handle"
    workboard="$session_dir/plan.md"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    degraded_file="$(redcap_runtime_compat_path_for_root "$REDCAP_ROOT" "degraded-mode.count")"
    before="$(counter_value "$degraded_file")"

    spawn_host_probe probe_pid
    mkdir -p "$session_dir"
    printf '%s\n' "$probe_pid" >"$session_dir/inuse.$probe_pid.lock"

    write_workboard_fixture \
        "$workboard" \
        "$REDCAP_ROOT/.dev-task.md" \
        "framework-upgrade-backlog-review" \
        "acceptance copilot wrapper identity anchor" \
        "copilot-session-anchor" \
        "$confirmed_hash"

    printf '{"cwd":"%s"}\n' "$REDCAP_ROOT" | \
        REDCAP_COPILOT_SESSION_STATE_ROOT="$session_state_root" \
        REDCAP_CONTINUITY_ROOT_DIR="$case_core" \
        REDCAP_HOOK_CWD="$REDCAP_ROOT" \
        REDCAP_HOST_PROCESS_PID="$probe_pid" \
        bash "$REDCAP_ROOT/.github/hooks/scripts/redcap-layerB-session-start.sh" >/dev/null

    binding_key="$(redcap_runtime_binding_key_from_host_session copilot "$session_handle")"
    assert_eq "$(workboard_value "$workboard" "isolation_mode")" "full"
    assert_eq "$(workboard_value "$workboard" "resume_gate_reason")" "explicit-binding-key"
    assert_eq "$(workboard_value "$workboard" "resume_gate_profile")" "copilot-sessionstart-wrapper-required"
    assert_eq "$(workboard_value "$workboard" "resume_gate_evidence")" "capability-matrix,explicit-binding-key"
    assert_eq "$(workboard_value "$workboard" "session_binding_key")" "$binding_key"
    assert_eq "$(workboard_value "$workboard" "continuity_authority")" "redcap-owned-manifest"
    assert_eq "$(workboard_value "$workboard" "continuity_state")" "fresh-session"

    runtime_id="$(workboard_value "$workboard" "runtime_session_id")"
    [[ -n "$runtime_id" && "$runtime_id" != "unknown" ]] || fail "expected runtime session id for $case_name"

    manifest="$case_core/sessions/$runtime_id/manifest.yaml"
    assert_exists "$manifest"
    assert_eq "$(manifest_value "$manifest" "isolation_mode")" "full"
    assert_eq "$(manifest_value "$manifest" "resume_gate_reason")" "explicit-binding-key"

    printf '{"cwd":"%s"}\n' "$REDCAP_ROOT" | \
        REDCAP_COPILOT_SESSION_STATE_ROOT="$session_state_root" \
        REDCAP_CONTINUITY_ROOT_DIR="$case_core" \
        REDCAP_HOOK_CWD="$REDCAP_ROOT" \
        REDCAP_HOST_PROCESS_PID="$probe_pid" \
        REDCAP_SKIP_FEISHU=1 \
        REDCAP_SKIP_INDEPENDENT_REVIEW=1 \
        bash "$REDCAP_ROOT/.github/hooks/scripts/redcap-layerB-session-end.sh" >/dev/null

    after="$(counter_value "$degraded_file")"
    assert_num_eq "$after" "$before"

    attach_binding_with_capability_recovery "copilot" "$REDCAP_ROOT" "$binding_key" "$probe_pid" "$probe_pid" \
        || fail "failed to reattach runtime for $case_name"
    initial_head="$(redcap_runtime_path "layerB/initial-head")"
    assert_not_exists "$initial_head"
    redcap_runtime_clear_context
}

run_copilot_session_context_rejects_ambiguous_locks_case() {
    local case_name="copilot-session-context-rejects-ambiguous-locks"
    local case_root session_state_root session_dir_a session_dir_b probe_pid output session binding workboard

    log "case: $case_name"

    case_root="$ACCEPT_ROOT/$case_name"
    session_state_root="$case_root/session-state"
    session_dir_a="$session_state_root/acceptance-copilot-a-${RANDOM}-$$"
    session_dir_b="$session_state_root/acceptance-copilot-b-${RANDOM}-$$"

    spawn_host_probe probe_pid
    mkdir -p "$session_dir_a" "$session_dir_b"
    printf '%s\n' "$probe_pid" >"$session_dir_a/inuse.$probe_pid.lock"
    printf '%s\n' "$probe_pid" >"$session_dir_b/inuse.$probe_pid.lock"
    printf '# a\n' >"$session_dir_a/plan.md"
    printf '# b\n' >"$session_dir_b/plan.md"

    output="$(
        REDCAP_ROOT_ENV="$REDCAP_ROOT" \
        REDCAP_COPILOT_SESSION_STATE_ROOT="$session_state_root" \
        REDCAP_HOST_PROCESS_PID="$probe_pid" \
            bash -lc '
set -u
cd "$REDCAP_ROOT_ENV"
source .github/hooks/scripts/redcap-copilot-session-context.sh
echo "loaded=1"
unset REDCAP_HOST_SESSION_ID REDCAP_SESSION_BINDING_KEY REDCAP_HOST_WORKBOARD_PATH REDCAP_COPILOT_SESSION_SOURCE
if redcap_copilot_apply_session_context >/dev/null 2>&1; then
    echo "applied=1"
else
    echo "applied=0"
fi
echo "session=${REDCAP_HOST_SESSION_ID:-}"
echo "binding=${REDCAP_SESSION_BINDING_KEY:-}"
echo "workboard=${REDCAP_HOST_WORKBOARD_PATH:-}"
'
    )"

    session="$(printf '%s\n' "$output" | awk -F= '/^session=/{print $2}')"
    binding="$(printf '%s\n' "$output" | awk -F= '/^binding=/{print $2}')"
    workboard="$(printf '%s\n' "$output" | awk -F= '/^workboard=/{print $2}')"
    assert_string_contains "$output" "loaded=1"
    assert_string_contains "$output" "applied=0"
    assert_eq "$session" ""
    assert_eq "$binding" ""
    assert_eq "$workboard" ""
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
    spawn_host_probe layera_probe
    spawn_host_probe layerb_probe

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
    spawn_host_probe host_probe
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

    redcap_runtime_clear_context
    unset REDCAP_RUNTIME_ALLOW_DISK_RECOVERY REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY REDCAP_RUNTIME_CAPABILITY 2>/dev/null || true

    report_path="$REDCAP_ROOT/compass/docs/task-reports/2026-04-16-completion-hook-hardening.md"
    degraded_file="$(redcap_runtime_compat_path_for_root "$REDCAP_ROOT" "degraded-mode.count")"
    before="$(counter_value "$degraded_file")"

    if bash "$REDCAP_ROOT/compass/tools/redcap-task-report-register.sh" claude "$report_path" >/dev/null 2>&1; then
        fail "task report registration unexpectedly succeeded without a process claim"
    fi

    after="$(counter_value "$degraded_file")"
    assert_num_eq "$after" $((before + 1))
}

run_report_register_accepts_explicit_runtime_env_case() {
    local host="copilot"
    local binding_key pid current_head pending_state marker_path
    local report_path rel_path

    log "case: report-register-accepts-explicit-runtime-env"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "report-register-accepts-explicit-runtime-env" >/dev/null 2>&1 || true

    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-explicit-runtime-${RANDOM}-$$.md"
    rel_path="${report_path#$REDCAP_ROOT/}"
    printf '# acceptance explicit runtime report\n' >"$report_path"
    LEGACY_TMP_FILES+=("$report_path")

    binding_key="acceptance-report-register-explicit-${RANDOM}-$$"
    pid="$((64900 + RANDOM))"
    init_bound_runtime "$host" "$binding_key" "$pid"
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to write initial head for explicit runtime report register case"
    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true

    REDCAP_RUNTIME_SESSION_ID="$REDCAP_RUNTIME_SESSION_ID" \
    REDCAP_RUNTIME_CAPABILITY="$REDCAP_RUNTIME_CAPABILITY" \
    REDCAP_SESSION_BINDING_KEY="$binding_key" \
        bash "$REDCAP_ROOT/compass/tools/redcap-task-report-register.sh" "$host" "$report_path" >/dev/null \
        || fail "task report registration should accept explicit runtime env"

    pending_state=$(redcap_interop_pending_closure_file "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md")
    assert_eq "$(redcap_interop_read_state_field "$pending_state" "artifact_path")" "$rel_path"

    marker_path="$(redcap_runtime_path "layerB/current-report-path")"
    assert_exists "$marker_path"
    assert_eq "$(read_file_text "$marker_path")" "$rel_path"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-cleanup" "report-register-accepts-explicit-runtime-env" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_report_register_rejects_ambiguous_explicit_runtime_case() {
    local host="copilot"
    local binding_key pid runtime_id runtime_capability
    local report_path output status pending_state

    log "case: report-register-rejects-ambiguous-explicit-runtime"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "report-register-rejects-ambiguous-explicit-runtime" >/dev/null 2>&1 || true

    binding_key="acceptance-report-register-ambiguous-${RANDOM}-$$"
    pid="$((64780 + RANDOM))"
    init_bound_runtime "$host" "$binding_key" "$pid"
    runtime_id="$REDCAP_RUNTIME_SESSION_ID"
    runtime_capability="$REDCAP_RUNTIME_CAPABILITY"
    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true

    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-ambiguous-explicit-${RANDOM}-$$.md"
    printf '# acceptance ambiguous explicit runtime report\n' >"$report_path"
    LEGACY_TMP_FILES+=("$report_path")

    set +e
    output="$(
        REDCAP_RUNTIME_SESSION_ID="$runtime_id" \
        REDCAP_RUNTIME_CAPABILITY="$runtime_capability" \
            bash "$REDCAP_ROOT/compass/tools/redcap-task-report-register.sh" "$host" "$report_path" 2>&1
    )"
    status=$?
    set -e
    [[ "$status" -ne 0 ]] || fail "task report registration unexpectedly accepted ambiguous explicit runtime"
    assert_string_contains "$output" "no matching runtime context available"

    pending_state=$(redcap_interop_pending_closure_existing_file "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" 2>/dev/null || true)
    [[ -z "$pending_state" ]] || fail "ambiguous explicit runtime unexpectedly created pending closure"

    redcap_runtime_clear_context
}

run_report_register_prefers_live_claim_over_stale_explicit_runtime_case() {
    local host="copilot"
    local binding_a binding_b pid_a pid_b
    local runtime_a capability_a report_path rel_path
    local marker_a marker_b

    log "case: report-register-prefers-live-claim-over-stale-explicit-runtime"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "report-register-prefers-live-claim-over-stale-explicit-runtime" >/dev/null 2>&1 || true

    binding_a="acceptance-report-register-priority-a-${RANDOM}-$$"
    binding_b="acceptance-report-register-priority-b-${RANDOM}-$$"
    pid_a="$((64800 + RANDOM))"
    pid_b="$((64810 + RANDOM))"

    init_bound_runtime "$host" "$binding_a" "$pid_a"
    runtime_a="$REDCAP_RUNTIME_SESSION_ID"
    capability_a="$REDCAP_RUNTIME_CAPABILITY"

    init_bound_runtime "$host" "$binding_b" "$pid_b"

    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-review-runtime-priority-${RANDOM}-$$.md"
    rel_path="${report_path#$REDCAP_ROOT/}"
    printf '# acceptance runtime priority report\n' >"$report_path"
    LEGACY_TMP_FILES+=("$report_path")

    REDCAP_RUNTIME_SESSION_ID="$runtime_a" \
    REDCAP_RUNTIME_CAPABILITY="$capability_a" \
    REDCAP_HOST_PROCESS_PID="$pid_b" \
        bash "$REDCAP_ROOT/compass/tools/redcap-task-report-register.sh" "$host" "$report_path" >/dev/null \
        || fail "task report registration should prefer live claim over stale explicit runtime"

    redcap_runtime_attach_existing "$runtime_a" "$capability_a" >/dev/null || fail "failed to reattach runtime A"
    marker_a="$(redcap_runtime_path "layerB/current-report-path")"
    if [[ -f "$marker_a" ]]; then
        assert_ne "$(read_file_text "$marker_a")" "$rel_path"
    fi

    REDCAP_HOST_PROCESS_PID="$pid_b" redcap_runtime_attach_from_process_claim "$host" >/dev/null || fail "failed to reattach runtime B"
    marker_b="$(redcap_runtime_path "layerB/current-report-path")"
    assert_exists "$marker_b"
    assert_eq "$(read_file_text "$marker_b")" "$rel_path"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-cleanup" "report-register-prefers-live-claim-over-stale-explicit-runtime" >/dev/null 2>&1 || true
    redcap_runtime_clear_process_claim "$host" "$pid_a" >/dev/null 2>&1 || true
    redcap_runtime_clear_process_claim "$host" "$pid_b" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_report_register_rejects_foreign_explicit_runtime_case() {
    local host="copilot"
    local repo_a repo_b
    local binding_key pid runtime_id runtime_capability
    local report_path output status pending_state

    log "case: report-register-rejects-foreign-explicit-runtime"

    redcap_runtime_clear_context
    repo_a="$ACCEPT_ROOT/report-register-foreign-runtime-a/repo"
    repo_b="$ACCEPT_ROOT/report-register-foreign-runtime-b/repo"
    create_task_report_fixture_repo "$repo_a"
    create_task_report_fixture_repo "$repo_b"

    binding_key="acceptance-report-register-foreign-${RANDOM}-$$"
    pid="$((64850 + RANDOM))"
    init_bound_runtime_for_repo "$host" "$repo_a" "$binding_key" "$pid"
    runtime_id="$REDCAP_RUNTIME_SESSION_ID"
    runtime_capability="$REDCAP_RUNTIME_CAPABILITY"
    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true

    report_path="$repo_b/compass/docs/task-reports/zz-acceptance-foreign-runtime-${RANDOM}-$$.md"
    cp "$repo_b/references/task-report-template.md" "$report_path"

    set +e
    output="$(
        REDCAP_RUNTIME_SESSION_ID="$runtime_id" \
        REDCAP_RUNTIME_CAPABILITY="$runtime_capability" \
        REDCAP_SESSION_BINDING_KEY="$binding_key" \
            bash "$repo_b/compass/tools/redcap-task-report-register.sh" "$host" "$report_path" 2>&1
    )"
    status=$?
    set -e
    [[ "$status" -ne 0 ]] || fail "task report registration unexpectedly accepted foreign explicit runtime"
    assert_string_contains "$output" "no matching runtime context available"

    pending_state=$(redcap_interop_pending_closure_existing_file "$repo_b" "$repo_b/.dev-task.md" 2>/dev/null || true)
    [[ -z "$pending_state" ]] || fail "foreign explicit runtime unexpectedly created pending closure in target repo"
    redcap_runtime_clear_context
}

run_report_register_replaces_pending_artifact_case() {
    local host="claude"
    local binding_key pid
    local current_head pending_state marker_path
    local report_a report_b rel_a rel_b

    log "case: report-register-replaces-pending-artifact"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "report-register-replaces-pending-artifact" >/dev/null 2>&1 || true

    report_a="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-report-a-${RANDOM}-$$.md"
    report_b="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-report-b-${RANDOM}-$$.md"
    rel_a="${report_a#$REDCAP_ROOT/}"
    rel_b="${report_b#$REDCAP_ROOT/}"
    printf '# acceptance report a\n' >"$report_a"
    printf '# acceptance report b\n' >"$report_b"
    LEGACY_TMP_FILES+=("$report_a" "$report_b")

    binding_key="acceptance-report-register-replace-${RANDOM}-$$"
    pid="$((65000 + RANDOM))"
    init_bound_runtime "$host" "$binding_key" "$pid"
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to write initial head for report register replace case"

    REDCAP_HOST_PROCESS_PID="$pid" bash "$REDCAP_ROOT/compass/tools/redcap-task-report-register.sh" "$host" "$report_a" >/dev/null \
        || fail "failed to register first report artifact"
    pending_state=$(redcap_interop_pending_closure_file "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md")
    assert_eq "$(redcap_interop_read_state_field "$pending_state" "artifact_path")" "$rel_a"

    REDCAP_HOST_PROCESS_PID="$pid" bash "$REDCAP_ROOT/compass/tools/redcap-task-report-register.sh" "$host" "$report_b" >/dev/null \
        || fail "failed to replace pending report artifact"
    pending_state=$(redcap_interop_pending_closure_file "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md")
    assert_eq "$(redcap_interop_read_state_field "$pending_state" "artifact_path")" "$rel_b"

    marker_path="$(redcap_runtime_path "layerB/current-report-path")"
    assert_exists "$marker_path"
    assert_eq "$(read_file_text "$marker_path")" "$rel_b"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-cleanup" "report-register-replaces-pending-artifact" >/dev/null 2>&1 || true
    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_report_register_rejects_traversal_artifact_case() {
    local host="claude"
    local repo binding_key pid current_head traversal_path output status pending_state

    log "case: report-register-rejects-traversal-artifact"

    redcap_runtime_clear_context
    repo="$ACCEPT_ROOT/report-register-rejects-traversal/repo"
    create_task_report_fixture_repo "$repo"
    binding_key="acceptance-report-register-traversal-${RANDOM}-$$"
    pid="$((65100 + RANDOM))"
    init_bound_runtime_for_repo "$host" "$repo" "$binding_key" "$pid"
    current_head="$(git -C "$repo" rev-parse HEAD)"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to write initial head for traversal register case"
    traversal_path="$repo/compass/docs/task-reports/../../../references/task-report-template.md"

    set +e
    output="$(REDCAP_HOST_PROCESS_PID="$pid" bash "$repo/compass/tools/redcap-task-report-register.sh" "$host" "$traversal_path" 2>&1)"
    status=$?
    set -e
    [[ "$status" -ne 0 ]] || fail "task-report-register unexpectedly accepted traversal report path"
    assert_string_contains "$output" "report must resolve under compass/docs/task-reports/"

    pending_state=$(redcap_interop_pending_closure_existing_file "$repo" "$repo/.dev-task.md" 2>/dev/null || true)
    [[ -z "$pending_state" ]] || fail "task-report-register unexpectedly created pending closure for traversal path"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_report_register_rejects_symlinked_report_root_case() {
    local host="claude"
    local repo case_root external_reports report_path binding_key pid current_head output status pending_state

    log "case: report-register-rejects-symlinked-report-root"

    redcap_runtime_clear_context
    case_root="$ACCEPT_ROOT/report-register-symlink-root"
    repo="$case_root/repo"
    external_reports="$case_root/external-reports"
    create_task_report_fixture_repo "$repo"
    mkdir -p "$external_reports"
    cp "$repo/references/task-report-template.md" "$external_reports/escape.md"
    rm -rf "$repo/compass/docs/task-reports"
    ln -s "$external_reports" "$repo/compass/docs/task-reports"
    report_path="$repo/compass/docs/task-reports/escape.md"

    binding_key="acceptance-report-register-symlink-root-${RANDOM}-$$"
    pid="$((65110 + RANDOM))"
    init_bound_runtime_for_repo "$host" "$repo" "$binding_key" "$pid"
    current_head="$(git -C "$repo" rev-parse HEAD)"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to write initial head for symlinked root case"

    set +e
    output="$(REDCAP_HOST_PROCESS_PID="$pid" bash "$repo/compass/tools/redcap-task-report-register.sh" "$host" "$report_path" 2>&1)"
    status=$?
    set -e
    [[ "$status" -ne 0 ]] || fail "task-report-register unexpectedly accepted symlinked task-report root"
    assert_string_contains "$output" "report must resolve under compass/docs/task-reports/"

    pending_state=$(redcap_interop_pending_closure_existing_file "$repo" "$repo/.dev-task.md" 2>/dev/null || true)
    [[ -z "$pending_state" ]] || fail "task-report-register unexpectedly created pending closure for symlinked task-report root"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_sessionstart_auto_reconcile_rewrite_case() {
    local host="claude"
    local binding_a binding_b pid_a pid_b
    local report_path report_rel pending_state required_redlines expected_seed expected_reconciled
    local current_head repo case_dir validator_stub

    log "case: sessionstart-auto-reconcile-rewrite"

    repo="$ACCEPT_ROOT/sessionstart-auto-reconcile-rewrite/repo"
    create_task_report_fixture_repo "$repo"
    report_rel="compass/docs/task-reports/zz-acceptance-reconcile-rewrite-${RANDOM}-$$.md"
    report_path="$repo/$report_rel"
    cp "$repo/references/task-report-template.md" "$report_path"
    binding_a="acceptance-reconcile-a-${RANDOM}-$$"
    binding_b="acceptance-reconcile-b-${RANDOM}-$$"
    pid_a="$((61000 + RANDOM))"
    pid_b="$((62000 + RANDOM))"
    redcap_interop_clear_pending_closure "$repo" "$repo/.dev-task.md" "acceptance-reset" "sessionstart-auto-reconcile-rewrite" >/dev/null 2>&1 || true

    init_bound_runtime_for_repo "$host" "$repo" "$binding_a" "$pid_a"
    current_head="$(git -C "$repo" rev-parse HEAD)"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for reconcile rewrite case"
    REDCAP_HOST_PROCESS_PID="$pid_a" bash "$repo/compass/tools/redcap-task-report-register.sh" "$host" "$report_path" >/dev/null

    pending_state=$(redcap_interop_pending_closure_file "$repo" "$repo/.dev-task.md")
    required_redlines=$(redcap_interop_read_state_field "$pending_state" "required_redlines" 2>/dev/null || true)
    expected_seed="task-report,review,notify"
    assert_eq "$(normalize_csv "$required_redlines")" "$(normalize_csv "$expected_seed")"

    init_bound_runtime_for_repo "$host" "$repo" "$binding_b" "$pid_b"
    write_current_report_marker_fixture "$report_rel" "$repo/.dev-task.md"
    case_dir="$(mktemp -d "$ACCEPT_ROOT/sessionstart-reconcile-rewrite.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    validator_stub="$case_dir/validator-stub.sh"
    cat >"$validator_stub" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
[redcap-validator-chain] mode=obligation-reconcile overall=fail
[1] review-proof-check :: fail
review required
[2] reanchor-check :: pass
reanchor ok
[3] pm-gate :: pass
pm-gate ok
[4] drift-check :: pass
drift ok
[5] backlog-check :: pass
backlog ok
[6] spec-check :: pass
spec ok
[7] task-report-check :: pass
task-report ok
[8] artifact-lifecycle-check :: pass
artifact ok
OUT
exit 1
EOF
    chmod +x "$validator_stub"
    REDCAP_VALIDATOR_CHAIN_SCRIPT="$validator_stub" \
    REDCAP_HOST_PROCESS_PID="$pid_b" \
        bash "$repo/compass/tools/redcap-pending-closure-reconcile.sh" "$host" >/dev/null \
        || fail "pending closure reconcile rewrite case failed"

    pending_state=$(redcap_interop_pending_closure_file "$repo" "$repo/.dev-task.md")
    required_redlines=$(redcap_interop_read_state_field "$pending_state" "required_redlines" 2>/dev/null || true)
    expected_reconciled="review,notify"
    assert_eq "$(normalize_csv "$required_redlines")" "$(normalize_csv "$expected_reconciled")"

    redcap_interop_clear_pending_closure "$repo" "$repo/.dev-task.md" "acceptance-cleanup" "sessionstart-auto-reconcile-rewrite" >/dev/null
    redcap_runtime_clear_process_claim "$host" "$pid_a" >/dev/null 2>&1 || true
    redcap_runtime_clear_process_claim "$host" "$pid_b" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_sessionstart_auto_reconcile_normalizes_absolute_artifact_case() {
    local host="claude"
    local binding_a binding_b pid_a pid_b
    local report_path report_rel report_abs pending_state current_head repo case_dir validator_stub

    log "case: sessionstart-auto-reconcile-normalizes-absolute-artifact"

    repo="$ACCEPT_ROOT/sessionstart-auto-reconcile-normalizes-absolute/repo"
    create_task_report_fixture_repo "$repo"
    report_rel="compass/docs/task-reports/zz-acceptance-reconcile-absolute-${RANDOM}-$$.md"
    report_path="$repo/$report_rel"
    cp "$repo/references/task-report-template.md" "$report_path"
    report_abs="$report_path"
    binding_a="acceptance-reconcile-abs-a-${RANDOM}-$$"
    binding_b="acceptance-reconcile-abs-b-${RANDOM}-$$"
    pid_a="$((61010 + RANDOM))"
    pid_b="$((62010 + RANDOM))"
    redcap_interop_clear_pending_closure "$repo" "$repo/.dev-task.md" "acceptance-reset" "sessionstart-auto-reconcile-normalizes-absolute-artifact" >/dev/null 2>&1 || true

    init_bound_runtime_for_repo "$host" "$repo" "$binding_a" "$pid_a"
    current_head="$(git -C "$repo" rev-parse HEAD)"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for absolute reconcile case"
    redcap_interop_write_pending_closure \
        "$repo" \
        "$repo/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "task-report,review,notify" \
        "sessionstart-auto-reconcile-normalizes-absolute-artifact" \
        "$report_abs" \
        "$current_head" \
        "$current_head" \
        >/dev/null || fail "failed to seed absolute pending artifact"
    pending_state=$(redcap_interop_pending_closure_file "$repo" "$repo/.dev-task.md")
    python3 - "$pending_state" "$report_abs" <<'PY'
import pathlib
import re
import sys

state_file = pathlib.Path(sys.argv[1])
artifact_path = sys.argv[2]
text = state_file.read_text(encoding="utf-8")
text, count = re.subn(r"^artifact_path:.*$", f"artifact_path: {artifact_path}", text, count=1, flags=re.MULTILINE)
if count != 1:
    raise SystemExit(1)
state_file.write_text(text, encoding="utf-8")
PY

    init_bound_runtime_for_repo "$host" "$repo" "$binding_b" "$pid_b"
    write_current_report_marker_fixture "$report_rel" "$repo/.dev-task.md"
    case_dir="$(mktemp -d "$ACCEPT_ROOT/sessionstart-reconcile-absolute.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    validator_stub="$case_dir/validator-stub.sh"
    cat >"$validator_stub" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
[redcap-validator-chain] mode=obligation-reconcile overall=fail
[1] review-proof-check :: fail
review required
[2] reanchor-check :: pass
reanchor ok
[3] pm-gate :: pass
pm-gate ok
[4] drift-check :: pass
drift ok
[5] backlog-check :: pass
backlog ok
[6] spec-check :: pass
spec ok
[7] task-report-check :: pass
task-report ok
[8] artifact-lifecycle-check :: pass
artifact ok
OUT
exit 1
EOF
    chmod +x "$validator_stub"
    REDCAP_VALIDATOR_CHAIN_SCRIPT="$validator_stub" \
    REDCAP_HOST_PROCESS_PID="$pid_b" \
        bash "$repo/compass/tools/redcap-pending-closure-reconcile.sh" "$host" >/dev/null \
        || fail "pending closure reconcile absolute artifact case failed"

    pending_state=$(redcap_interop_pending_closure_file "$repo" "$repo/.dev-task.md")
    assert_eq "$(redcap_interop_read_state_field "$pending_state" "artifact_path" 2>/dev/null || true)" "$report_rel"

    redcap_interop_clear_pending_closure "$repo" "$repo/.dev-task.md" "acceptance-cleanup" "sessionstart-auto-reconcile-normalizes-absolute-artifact" >/dev/null
    redcap_runtime_clear_process_claim "$host" "$pid_a" >/dev/null 2>&1 || true
    redcap_runtime_clear_process_claim "$host" "$pid_b" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_complete_guard_triggers_closeout_runtime_case() {
    local host="copilot"
    local binding_key pid current_head
    local report_path report_rel marker_path
    local case_dir register_log runtime_log register_stub runtime_stub
    local runtime_count register_count
    local task_complete_slice

    log "case: task-complete-guard-triggers-closeout-runtime"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "task-complete-guard-triggers-closeout-runtime" >/dev/null 2>&1 || true

    binding_key="acceptance-task-complete-guard-${RANDOM}-$$"
    pid="$((66000 + RANDOM))"
    init_bound_runtime "$host" "$binding_key" "$pid"
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for task complete guard case"

    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-task-complete-guard-${RANDOM}-$$.md"
    report_rel="${report_path#$REDCAP_ROOT/}"
    printf '# acceptance guard report\n' >"$report_path"
    LEGACY_TMP_FILES+=("$report_path")
    redcap_interop_write_pending_closure \
        "$REDCAP_ROOT" \
        "$REDCAP_ROOT/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "task-report,review,notify" \
        "task-complete-guard-triggers-closeout-runtime" \
        "$report_rel" \
        "$current_head" \
        "$current_head" \
        >/dev/null || fail "failed to seed pending closure for task complete guard case"
    write_current_report_marker_fixture "$report_rel"
    task_complete_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/task-complete-guard.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    register_log="$case_dir/register.log"
    runtime_log="$case_dir/closeout-runtime.log"
    register_stub="$case_dir/register-stub.sh"
    runtime_stub="$case_dir/closeout-runtime-stub.sh"

    cat >"$register_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
HOST="\${1:?}"
REPORT="\${2:?}"
source "$REDCAP_ROOT/compass/tools/redcap-runtime-state.sh"
source "$REDCAP_ROOT/compass/tools/redcap-interop-governance.sh"
redcap_runtime_attach_existing "\${REDCAP_RUNTIME_SESSION_ID:?}" "\${REDCAP_RUNTIME_CAPABILITY:?}" >/dev/null
printf '%s\n' "\$REPORT" >>"$register_log"
redcap_interop_write_current_report_marker "\${REPORT#$REDCAP_ROOT/}" "$REDCAP_ROOT/.dev-task.md" >/dev/null
EOF
    cat >"$runtime_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf '%s\t%s\n' "\${1:-complete}" "\${REDCAP_HOST_PROCESS_PID:-missing}" >>"$runtime_log"
EOF
    chmod +x "$register_stub" "$runtime_stub"

    REDCAP_TASK_COMPLETE_SLICE="$task_complete_slice" \
    REDCAP_TASK_REPORT_REGISTER_SCRIPT="$register_stub" \
    REDCAP_LAYERB_CLOSEOUT_RUNTIME_SCRIPT="$runtime_stub" \
    REDCAP_HOST_PROCESS_PID="$pid" \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-task-complete-guard.sh" "$host" >/dev/null \
        || fail "task complete guard first run failed"

    marker_path="$(redcap_runtime_path "layerB/current-report-path")"
    assert_exists "$marker_path"
    assert_eq "$(read_file_text "$marker_path")" "$report_rel"

    register_count="0"
    [[ -f "$register_log" ]] && register_count="$(wc -l < "$register_log" | tr -d '[:space:]')"
    runtime_count="$(wc -l < "$runtime_log" | tr -d '[:space:]')"
    assert_num_eq "$register_count" 0
    assert_num_eq "$runtime_count" 1
    assert_string_contains "$(cat "$runtime_log")" $'complete\t'

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-cleanup" "task-complete-guard-triggers-closeout-runtime" >/dev/null 2>&1 || true
    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

write_layerb_closeout_task_fixture() {
    local task_file="$1"
    local report_rel="$2"
    local promise_block="$3"
    local task_id

    task_id="$(basename "$task_file")"
    task_id="${task_id%.md}"
    task_id="${task_id#.}"
    task_id="${task_id//[^A-Za-z0-9._-]/-}"
    case "$task_id" in
        acceptance-*) ;;
        *) task_id="acceptance-${task_id}" ;;
    esac

    cat >"$task_file" <<EOF
# 当前任务：Layer B closeout runtime acceptance

## 控制面元数据（机器校验）
task_id: $task_id
source_of_truth: .dev-task.md
top_goal: 验证 Layer B closeout runtime
active_slice: closeout-runtime-acceptance
host_surface_policy: mirror_only
delegation_boundary: redcap-native-first
task_report: $report_rel
acceptance_policy: not-required
prism_acceptance_run: none

## 原始输入（用户原文）
验证统一 closeout runtime

## 已确认需求（执行依据）
统一 closeout runtime 必须核对 promise ledger、receipt 与 rescue audit。

## 漂移哨兵
- 只验证 closeout runtime acceptance

## 允许修改范围
- compass/tools/**
- compass/docs/task-reports/**

## 完成标准
- [ ] closeout runtime acceptance

## 执行承诺账本（Agent 自追加承诺，closeout 必核对）
$promise_block

## 断点备注
acceptance fixture
EOF
}

run_layerb_closeout_runtime_promise_ledger_blocks_case() {
    local host="copilot"
    local current_head task_file report_path report_rel case_dir
    local on_complete_stub session_end_stub output status pending_state audit_path

    log "case: layerb-closeout-runtime-promise-ledger-blocks"

    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    task_file="$REDCAP_ROOT/.acceptance-closeout-runtime-pending-${RANDOM}-$$.md"
    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-closeout-runtime-pending-${RANDOM}-$$.md"
    report_rel="${report_path#$REDCAP_ROOT/}"
    LEGACY_TMP_FILES+=("$task_file" "$report_path")
    cat >"$report_path" <<'EOF'
# 任务完成报告：acceptance closeout runtime

## 零、先看懂当前局面
### 0.1 当前已完成
- 当前已完成：closeout runtime acceptance fixture
### 0.3 下一步计划做的是
- 下一步计划做的是：无
EOF
    write_layerb_closeout_task_fixture "$task_file" "$report_rel" "- [ ] 统一 runtime 还未真正收尾"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/closeout-runtime-blocked.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    on_complete_stub="$case_dir/on-complete-stub.sh"
    session_end_stub="$case_dir/session-end-stub.sh"
    printf '#!/usr/bin/env bash\nexit 99\n' >"$on_complete_stub"
    printf '#!/usr/bin/env bash\nexit 99\n' >"$session_end_stub"
    chmod +x "$on_complete_stub" "$session_end_stub"

    set +e
    output="$(REDCAP_ON_COMPLETE_SCRIPT="$on_complete_stub" REDCAP_LAYERB_SESSION_END_SCRIPT="$session_end_stub" bash "$REDCAP_ROOT/compass/tools/redcap-layerb-closeout-runtime.sh" complete --task-file "$task_file" --host "$host" --baseline-head "$current_head" 2>&1)"
    status=$?
    set -e
    [[ "$status" -ne 0 ]] || fail "promise-ledger blocked case unexpectedly succeeded"
    assert_string_contains "$output" "promise ledger contains unresolved commitments"

    pending_state="$(redcap_interop_pending_closure_file "$REDCAP_ROOT" "$task_file")"
    assert_exists "$pending_state"
    assert_eq "$(redcap_interop_read_state_field "$pending_state" "required_redlines" 2>/dev/null || true)" "promise-ledger,closeout-runtime"

    audit_path="$(python3 - <<'PY' "$output"
import json, sys
text = sys.argv[1]
start = text.find('{')
payload = json.loads(text[start:])
print(payload["audit_path"])
PY
)"
    assert_exists "$audit_path"
    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$task_file" "acceptance-cleanup" "layerb-closeout-runtime-promise-ledger-blocks" >/dev/null 2>&1 || true
}

run_layerb_closeout_runtime_prism_acceptance_blocks_case() {
    local host="copilot"
    local current_head task_file report_path report_rel case_dir
    local on_complete_stub session_end_stub output status pending_state audit_path

    log "case: layerb-closeout-runtime-prism-acceptance-blocks"

    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    case_dir="$(mktemp -d "$ACCEPT_ROOT/layerb-prism-acceptance.XXXXXX")"
    task_file="$case_dir/.dev-task.md"
    report_path="$case_dir/report.md"
    report_rel="$report_path"
    cat >"$report_path" <<EOF
# report

### 0.1 当前已完成
- 当前已完成：FSM 验收门已接线
EOF
    write_layerb_closeout_task_fixture "$task_file" "$report_rel" "- [x] 统一 runtime 已真正收尾"
    python3 - "$task_file" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace("acceptance_policy: not-required", "acceptance_policy: prism-required")
text = text.replace("prism_acceptance_run: none", "prism_acceptance_run: pending")
path.write_text(text, encoding="utf-8")
PY

    on_complete_stub="$case_dir/on-complete.sh"
    session_end_stub="$case_dir/session-end.sh"
    cat >"$on_complete_stub" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
    cat >"$session_end_stub" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
    chmod +x "$on_complete_stub" "$session_end_stub"

    set +e
    output="$(REDCAP_ON_COMPLETE_SCRIPT="$on_complete_stub" REDCAP_LAYERB_SESSION_END_SCRIPT="$session_end_stub" bash "$REDCAP_ROOT/compass/tools/redcap-layerb-closeout-runtime.sh" complete --task-file "$task_file" --host "$host" --baseline-head "$current_head" 2>&1)"
    status=$?
    set -e
    [[ "$status" -ne 0 ]] || fail "prism-acceptance blocked case unexpectedly succeeded"
    assert_string_contains "$output" "independent acceptance missing or failed"
    pending_state="$(redcap_interop_pending_closure_file "$case_dir" "$task_file")"
    assert_exists "$pending_state"
    assert_eq "$(redcap_interop_read_state_field "$pending_state" "required_redlines" 2>/dev/null || true)" "prism-acceptance,closeout-runtime"
    audit_path="$(python3 - <<'PY' "$output"
import json
import sys
payload = json.loads(sys.argv[1])
print(payload["audit_path"])
PY
)"
    assert_exists "$audit_path"
}

run_prism_acceptance_binding_required_case() {
    local case_dir task_file report_path report_rel run_id output status
    local parsed_a parsed_b registry

    log "case: prism-acceptance-binding-required"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/prism-acceptance-binding.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    task_file="$case_dir/.dev-task.md"
    report_path="$case_dir/report.md"
    report_rel="$report_path"
    printf '# report\n' >"$report_path"
    write_layerb_closeout_task_fixture "$task_file" "$report_rel" "- [x] 棱镜验收证据已准备"
    python3 - "$task_file" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace("acceptance_policy: not-required", "acceptance_policy: prism-required")
text = text.replace("prism_acceptance_run: none", "prism_acceptance_run: acceptance-binding-run")
path.write_text(text, encoding="utf-8")
PY

    run_id="acceptance-binding-run"
    registry="$case_dir/prism/runs/$run_id/session-registry.yaml"
    parsed_a="$case_dir/prism/runs/$run_id/collect/a_review/parsed.json"
    parsed_b="$case_dir/prism/runs/$run_id/collect/b_review/parsed.json"
    mkdir -p "$(dirname "$registry")" "$(dirname "$parsed_a")" "$(dirname "$parsed_b")"
    cat >"$registry" <<'EOF'
run_id: "acceptance-binding-run"
mode: "test"
agents:
  - handle_type: "shell"
    handle: "a"
    role: "a_review"
    model: "kimi-for-coding"
    family: "kimi"
    injection_mode: "native"
    status: "responded"
    schema_ok: true
  - handle_type: "task_agent"
    handle: "b"
    role: "b_review"
    model: "gpt-5.4"
    family: "gpt"
    injection_mode: "native"
    status: "responded"
    schema_ok: true
EOF
    printf '{"agent":"a","role":"independent-reviewer","conclusion":"ok","confidence":"high","blockers":[],"actions":[],"blind_spots":null}\n' >"$parsed_a"
    printf '{"agent":"b","role":"independent-reviewer","conclusion":"ok","confidence":"high","blockers":[],"actions":[],"blind_spots":null}\n' >"$parsed_b"

    set +e
    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-prism-acceptance-check.sh" --task-file "$task_file" 2>&1)"
    status=$?
    set -e
    [[ "$status" -ne 0 ]] || fail "prism acceptance unexpectedly passed without binding"
    assert_string_contains "$output" "binding missing"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-prism-acceptance-bind.sh" --run-id "$run_id" --task-file "$task_file")"
    assert_string_contains "$output" "\"status\": \"ok\""

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-prism-acceptance-check.sh" --task-file "$task_file")"
    assert_string_contains "$output" "\"status\": \"pass\""
}

run_review_proof_check_accepts_prism_acceptance_case() {
    local case_dir task_file report_path report_rel run_id output
    local parsed_a parsed_b registry

    log "case: review-proof-check-accepts-prism-acceptance"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/review-proof-prism.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    task_file="$case_dir/.dev-task.md"
    report_path="$case_dir/report.md"
    report_rel="$report_path"
    printf '# report\n' >"$report_path"
    write_layerb_closeout_task_fixture "$task_file" "$report_rel" "- [x] 棱镜验收可替代 stop-review 证明"
    python3 - "$task_file" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace("acceptance_policy: not-required", "acceptance_policy: prism-required")
text = text.replace("prism_acceptance_run: none", "prism_acceptance_run: review-proof-prism-run")
path.write_text(text, encoding="utf-8")
PY

    run_id="review-proof-prism-run"
    registry="$case_dir/prism/runs/$run_id/session-registry.yaml"
    parsed_a="$case_dir/prism/runs/$run_id/collect/a_review/parsed.json"
    parsed_b="$case_dir/prism/runs/$run_id/collect/b_review/parsed.json"
    mkdir -p "$(dirname "$registry")" "$(dirname "$parsed_a")" "$(dirname "$parsed_b")"
    cat >"$registry" <<'EOF'
run_id: "review-proof-prism-run"
mode: "test"
agents:
  - handle_type: "shell"
    handle: "a"
    role: "a_review"
    model: "kimi-for-coding"
    family: "kimi"
    injection_mode: "native"
    status: "responded"
    schema_ok: true
  - handle_type: "task_agent"
    handle: "b"
    role: "b_review"
    model: "gpt-5.4"
    family: "gpt"
    injection_mode: "native"
    status: "responded"
    schema_ok: true
EOF
    printf '{"agent":"a","role":"independent-reviewer","conclusion":"ok","confidence":"high","blockers":[],"actions":[],"blind_spots":null}\n' >"$parsed_a"
    printf '{"agent":"b","role":"independent-reviewer","conclusion":"ok","confidence":"high","blockers":[],"actions":[],"blind_spots":null}\n' >"$parsed_b"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-prism-acceptance-bind.sh" --run-id "$run_id" --task-file "$task_file")"
    assert_string_contains "$output" "\"status\": \"ok\""

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-review-proof-check.sh" 1 "" "$task_file")"
    assert_string_contains "$output" "bound Prism acceptance"
}

run_layerb_closeout_runtime_complete_writes_receipt_case() {
    local host="copilot"
    local current_head task_file report_path report_rel case_dir
    local on_complete_stub session_end_stub on_complete_log session_end_log output receipt_path summary_path state_path

    log "case: layerb-closeout-runtime-complete-writes-receipt"

    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    task_file="$REDCAP_ROOT/.acceptance-closeout-runtime-complete-${RANDOM}-$$.md"
    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-closeout-runtime-complete-${RANDOM}-$$.md"
    report_rel="${report_path#$REDCAP_ROOT/}"
    LEGACY_TMP_FILES+=("$task_file" "$report_path")
    cat >"$report_path" <<'EOF'
# 任务完成报告：acceptance closeout runtime

## 零、先看懂当前局面
### 0.1 当前已完成
- 当前已完成：统一 closeout runtime 已完成收尾
### 0.3 下一步计划做的是
- 下一步计划做的是：无
EOF
    write_layerb_closeout_task_fixture "$task_file" "$report_rel" "- [x] 统一 runtime 已真正收尾"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/closeout-runtime-complete.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    on_complete_stub="$case_dir/on-complete-stub.sh"
    session_end_stub="$case_dir/session-end-stub.sh"
    on_complete_log="$case_dir/on-complete.log"
    session_end_log="$case_dir/session-end.log"
    cat >"$on_complete_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "on-complete" >>"$on_complete_log"
EOF
    cat >"$session_end_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "session-end" >>"$session_end_log"
EOF
    chmod +x "$on_complete_stub" "$session_end_stub"

    output="$(REDCAP_ON_COMPLETE_SCRIPT="$on_complete_stub" REDCAP_LAYERB_SESSION_END_SCRIPT="$session_end_stub" bash "$REDCAP_ROOT/compass/tools/redcap-layerb-closeout-runtime.sh" complete --task-file "$task_file" --host "$host" --baseline-head "$current_head")"
    receipt_path="$(python3 - <<'PY' "$output"
import json, sys
payload = json.loads(sys.argv[1])
print(payload["receipt_path"])
PY
)"
    summary_path="$(python3 - <<'PY' "$output"
import json, sys
payload = json.loads(sys.argv[1])
print(payload["summary_path"])
PY
)"
    state_path="$(python3 - <<'PY' "$output"
import json, sys
payload = json.loads(sys.argv[1])
print(payload["state"]["receipt_path"])
PY
)"
    assert_exists "$receipt_path"
    assert_exists "$summary_path"
    assert_eq "$receipt_path" "$state_path"
    assert_string_contains "$(cat "$summary_path")" "统一 closeout runtime 已完成收尾"
    assert_num_eq "$(wc -l < "$on_complete_log" | tr -d '[:space:]')" 1
    assert_num_eq "$(wc -l < "$session_end_log" | tr -d '[:space:]')" 1
}

run_layerb_closeout_runtime_session_end_failure_writes_pending_case() {
    local host="copilot"
    local current_head task_file report_path report_rel case_dir
    local on_complete_stub session_end_stub output status pending_state audit_path

    log "case: layerb-closeout-runtime-session-end-failure-writes-pending"

    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    task_file="$REDCAP_ROOT/.acceptance-closeout-runtime-session-end-fail-${RANDOM}-$$.md"
    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-closeout-runtime-session-end-fail-${RANDOM}-$$.md"
    report_rel="${report_path#$REDCAP_ROOT/}"
    LEGACY_TMP_FILES+=("$task_file" "$report_path")
    cat >"$report_path" <<'EOF'
# 任务完成报告：acceptance closeout runtime session-end failure

## 零、先看懂当前局面
### 0.1 当前已完成
- 当前已完成：session-end 失败时必须写回 pending closure
### 0.3 下一步计划做的是
- 下一步计划做的是：无
EOF
    write_layerb_closeout_task_fixture "$task_file" "$report_rel" "- [x] 统一 runtime 已走到 session-end"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/closeout-runtime-session-end-fail.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    on_complete_stub="$case_dir/on-complete-stub.sh"
    session_end_stub="$case_dir/session-end-stub.sh"
    cat >"$on_complete_stub" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF
    cat >"$session_end_stub" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 1
EOF
    chmod +x "$on_complete_stub" "$session_end_stub"

    set +e
    output="$(REDCAP_ON_COMPLETE_SCRIPT="$on_complete_stub" REDCAP_LAYERB_SESSION_END_SCRIPT="$session_end_stub" bash "$REDCAP_ROOT/compass/tools/redcap-layerb-closeout-runtime.sh" complete --task-file "$task_file" --host "$host" --baseline-head "$current_head" 2>&1)"
    status=$?
    set -e
    [[ "$status" -ne 0 ]] || fail "session-end failure case unexpectedly succeeded"
    pending_state="$(redcap_interop_pending_closure_file "$REDCAP_ROOT" "$task_file")"
    assert_exists "$pending_state"
    assert_string_contains "$(cat "$pending_state")" "closeout-runtime"
    audit_path="$(python3 - <<'PY' "$output"
import json, sys
text = sys.argv[1]
start = text.find('{')
payload = json.loads(text[start:])
print(payload["audit_path"])
PY
)"
    assert_exists "$audit_path"
    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$task_file" "acceptance-cleanup" "layerb-closeout-runtime-session-end-failure-writes-pending" >/dev/null 2>&1 || true
}

run_layerb_closeout_runtime_audit_open_repairs_receipt_case() {
    local host="copilot"
    local current_head task_file report_path report_rel case_dir
    local on_complete_stub session_end_stub output receipt_path audit_path

    log "case: layerb-closeout-runtime-audit-open-repairs-receipt"

    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    task_file="$REDCAP_ROOT/.acceptance-closeout-runtime-repair-${RANDOM}-$$.md"
    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-closeout-runtime-repair-${RANDOM}-$$.md"
    report_rel="${report_path#$REDCAP_ROOT/}"
    LEGACY_TMP_FILES+=("$task_file" "$report_path")
    cat >"$report_path" <<'EOF'
# 任务完成报告：acceptance closeout runtime

## 零、先看懂当前局面
### 0.1 当前已完成
- 当前已完成：receipt 可由 rescue audit 补写
### 0.3 下一步计划做的是
- 下一步计划做的是：无
EOF
    write_layerb_closeout_task_fixture "$task_file" "$report_rel" "- [x] 收尾已完成，仅缺 receipt"
    case_dir="$(mktemp -d "$ACCEPT_ROOT/closeout-runtime-audit-repair.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    on_complete_stub="$case_dir/on-complete-stub.sh"
    session_end_stub="$case_dir/session-end-stub.sh"
    cat >"$on_complete_stub" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF
    cat >"$session_end_stub" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF
    chmod +x "$on_complete_stub" "$session_end_stub"

    output="$(REDCAP_ON_COMPLETE_SCRIPT="$on_complete_stub" REDCAP_LAYERB_SESSION_END_SCRIPT="$session_end_stub" bash "$REDCAP_ROOT/compass/tools/redcap-layerb-closeout-runtime.sh" complete --task-file "$task_file" --host "$host" --baseline-head "$current_head")"
    receipt_path="$(python3 - <<'PY' "$output"
import json, sys
payload = json.loads(sys.argv[1])
print(payload["receipt_path"])
PY
)"
    assert_exists "$receipt_path"
    rm -f "$receipt_path"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-layerb-closeout-runtime.sh" audit-open --task-file "$task_file" --host "$host" --baseline-head "$current_head" --mode diagnose)"
    receipt_path="$(python3 - <<'PY' "$output"
import json, sys
payload = json.loads(sys.argv[1])
print(payload["receipt_path"])
PY
)"
    audit_path="$(python3 - <<'PY' "$output"
import json, sys
payload = json.loads(sys.argv[1])
print(payload["audit_path"])
PY
)"
    assert_exists "$receipt_path"
    assert_exists "$audit_path"
    assert_string_contains "$(cat "$audit_path")" "repair-receipt"
}

run_layerb_closeout_runtime_audit_open_blocks_unresolved_case() {
    local host="copilot"
    local current_head task_file report_path report_rel output status audit_path pending_state

    log "case: layerb-closeout-runtime-audit-open-blocks-unresolved"

    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    task_file="$REDCAP_ROOT/.acceptance-closeout-runtime-audit-block-${RANDOM}-$$.md"
    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-closeout-runtime-audit-block-${RANDOM}-$$.md"
    report_rel="${report_path#$REDCAP_ROOT/}"
    LEGACY_TMP_FILES+=("$task_file" "$report_path")
    printf '# acceptance report\n' >"$report_path"
    write_layerb_closeout_task_fixture "$task_file" "$report_rel" "- [x] 代码已改完，但 blocker 还没清"

    redcap_interop_write_pending_closure \
        "$REDCAP_ROOT" \
        "$task_file" \
        "$host" \
        "acceptance-seed" \
        "closeout-runtime" \
        "audit-open unresolved fixture" \
        "$report_rel" \
        "$current_head" \
        "$current_head" \
        >/dev/null || fail "failed to seed pending closure for audit-open blocked case"

    set +e
    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-layerb-closeout-runtime.sh" audit-open --task-file "$task_file" --host "$host" --baseline-head "$current_head" --mode diagnose 2>&1)"
    status=$?
    set -e
    [[ "$status" -ne 0 ]] || fail "audit-open unresolved case unexpectedly succeeded"
    assert_string_contains "$output" "could not repair receipt"
    audit_path="$(python3 - <<'PY' "$output"
import json, sys
text = sys.argv[1]
start = text.find('{')
payload = json.loads(text[start:])
print(payload["audit_path"])
PY
)"
    assert_exists "$audit_path"
    pending_state="$(redcap_interop_pending_closure_file "$REDCAP_ROOT" "$task_file")"
    assert_exists "$pending_state"
    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$task_file" "acceptance-cleanup" "layerb-closeout-runtime-audit-open-blocks-unresolved" >/dev/null 2>&1 || true
}

run_layerb_closeout_runtime_audit_open_preserves_existing_blockers_case() {
    local host="copilot"
    local current_head task_file report_path report_rel output status pending_state

    log "case: layerb-closeout-runtime-audit-open-preserves-existing-blockers"

    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    task_file="$REDCAP_ROOT/.acceptance-closeout-runtime-audit-merge-${RANDOM}-$$.md"
    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-closeout-runtime-audit-merge-${RANDOM}-$$.md"
    report_rel="${report_path#$REDCAP_ROOT/}"
    LEGACY_TMP_FILES+=("$task_file" "$report_path")
    printf '# acceptance report\n' >"$report_path"
    write_layerb_closeout_task_fixture "$task_file" "$report_rel" "- [x] closeout 之外的 blocker 仍存在"

    redcap_interop_write_pending_closure \
        "$REDCAP_ROOT" \
        "$task_file" \
        "$host" \
        "acceptance-seed" \
        "review,task-report" \
        "pre-existing blockers" \
        "$report_rel" \
        "$current_head" \
        "$current_head" \
        >/dev/null || fail "failed to seed pending closure for merge-preserve case"

    set +e
    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-layerb-closeout-runtime.sh" audit-open --task-file "$task_file" --host "$host" --baseline-head "$current_head" --mode diagnose 2>&1)"
    status=$?
    set -e
    [[ "$status" -ne 0 ]] || fail "audit-open preserve-blockers case unexpectedly succeeded"
    pending_state="$(redcap_interop_pending_closure_file "$REDCAP_ROOT" "$task_file")"
    assert_exists "$pending_state"
    assert_eq "$(redcap_interop_read_state_field "$pending_state" "required_redlines" 2>/dev/null || true)" "review,task-report,closeout-runtime"
    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$task_file" "acceptance-cleanup" "layerb-closeout-runtime-audit-open-preserves-existing-blockers" >/dev/null 2>&1 || true
}

run_diagnose_auto_repairs_closeout_receipt_case() {
    local host="copilot"
    local current_head task_file report_path report_rel case_dir
    local on_complete_stub session_end_stub receipt_path output complete_output

    log "case: diagnose-auto-repairs-closeout-receipt"

    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    task_file="$REDCAP_ROOT/.acceptance-diagnose-closeout-repair-${RANDOM}-$$.md"
    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-diagnose-closeout-repair-${RANDOM}-$$.md"
    report_rel="${report_path#$REDCAP_ROOT/}"
    LEGACY_TMP_FILES+=("$task_file" "$report_path")
    cat >"$report_path" <<'EOF'
# 任务完成报告：acceptance diagnose rescue audit

## 零、先看懂当前局面
### 0.1 当前已完成
- 当前已完成：session-end 已闭环，但 receipt 丢失
### 0.3 下一步计划做的是
- 下一步计划做的是：无
EOF
    write_layerb_closeout_task_fixture "$task_file" "$report_rel" "- [x] receipt 之外的收尾都已完成"
    bash "$REDCAP_ROOT/compass/tools/redcap-docs-catalog.sh" generate >/dev/null

    case_dir="$(mktemp -d "$ACCEPT_ROOT/diagnose-closeout-repair.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    on_complete_stub="$case_dir/on-complete-stub.sh"
    session_end_stub="$case_dir/session-end-stub.sh"
    cat >"$on_complete_stub" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF
    cat >"$session_end_stub" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF
    chmod +x "$on_complete_stub" "$session_end_stub"

    complete_output="$(REDCAP_ON_COMPLETE_SCRIPT="$on_complete_stub" REDCAP_LAYERB_SESSION_END_SCRIPT="$session_end_stub" bash "$REDCAP_ROOT/compass/tools/redcap-layerb-closeout-runtime.sh" complete --task-file "$task_file" --host "$host" --baseline-head "$current_head")"
    receipt_path="$(python3 - <<'PY' "$complete_output"
import json, sys
payload = json.loads(sys.argv[1])
print(payload["receipt_path"])
PY
)"
    assert_exists "$receipt_path"
    rm -f "$receipt_path"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-diagnose.sh" "$task_file")"
    assert_string_contains "$output" "[ok] closeout-rescue-audit"
    assert_exists "$receipt_path"
}

run_closeout_cap_root_entry_basic_commands_case() {
    local task_file report_path report_rel output

    log "case: closeout-cap-root-entry-basic-commands"

    task_file="$REDCAP_ROOT/.acceptance-closeout-cap-root-${RANDOM}-$$.md"
    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-closeout-cap-root-${RANDOM}-$$.md"
    report_rel="${report_path#$REDCAP_ROOT/}"
    LEGACY_TMP_FILES+=("$task_file" "$report_path")
    cat >"$report_path" <<'EOF'
# 任务完成报告：acceptance closeout cap root entry

## 零、先看懂当前局面
### 0.1 当前已完成
- 当前已完成：根入口基础命令可用
### 0.3 下一步计划做的是
- 下一步计划做的是：无
EOF
    write_layerb_closeout_task_fixture "$task_file" "$report_rel" "- [x] closeout cap 根入口可用"
    bash "$REDCAP_ROOT/compass/tools/redcap-docs-catalog.sh" generate >/dev/null

    output="$(bash "$REDCAP_ROOT/closeout-cap.sh" sync-promises --task-file "$task_file")"
    assert_string_contains "$output" "\"status\": \"ok\""

    output="$(bash "$REDCAP_ROOT/closeout-cap.sh" status --task-file "$task_file")"
    assert_string_contains "$output" "\"promise_total\": 1"
    assert_string_contains "$output" "\"receipt_exists\": false"
}

run_task_complete_guard_passes_host_to_on_complete_case() {
    local host="copilot"
    local binding_key pid current_head report_path report_rel marker_path
    local task_complete_slice case_dir register_log complete_log register_stub complete_stub register_count

    log "case: task-complete-guard-passes-host-to-on-complete"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "task-complete-guard-passes-host-to-on-complete" >/dev/null 2>&1 || true

    binding_key="acceptance-task-complete-host-${RANDOM}-$$"
    pid="$((68000 + RANDOM))"
    init_bound_runtime "$host" "$binding_key" "$pid"
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for host passthrough case"

    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-task-complete-host-${RANDOM}-$$.md"
    report_rel="${report_path#$REDCAP_ROOT/}"
    printf '# acceptance guard host report\n' >"$report_path"
    LEGACY_TMP_FILES+=("$report_path")
    redcap_interop_write_pending_closure \
        "$REDCAP_ROOT" \
        "$REDCAP_ROOT/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "task-report,review,notify" \
        "task-complete-guard-passes-host-to-on-complete" \
        "$report_rel" \
        "$current_head" \
        "$current_head" \
        >/dev/null || fail "failed to seed pending closure for host passthrough case"
    write_current_report_marker_fixture "$report_rel"
    task_complete_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/task-complete-host.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    register_log="$case_dir/register.log"
    complete_log="$case_dir/on-complete-host.log"
    register_stub="$case_dir/register-stub.sh"
    complete_stub="$case_dir/on-complete-stub.sh"

    cat >"$register_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
REPORT="\${2:?}"
source "$REDCAP_ROOT/compass/tools/redcap-runtime-state.sh"
source "$REDCAP_ROOT/compass/tools/redcap-interop-governance.sh"
redcap_runtime_attach_existing "\${REDCAP_RUNTIME_SESSION_ID:?}" "\${REDCAP_RUNTIME_CAPABILITY:?}" >/dev/null
printf '%s\n' "\$REPORT" >>"$register_log"
redcap_interop_write_current_report_marker "\${REPORT#$REDCAP_ROOT/}" "$REDCAP_ROOT/.dev-task.md" >/dev/null
EOF
    cat >"$complete_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "\${REDCAP_ON_COMPLETE_HOST:-missing}" >>"$complete_log"
EOF
    chmod +x "$register_stub" "$complete_stub"

    REDCAP_ON_COMPLETE_HOST="claude" \
    REDCAP_TASK_COMPLETE_SLICE="$task_complete_slice" \
    REDCAP_TASK_REPORT_REGISTER_SCRIPT="$register_stub" \
    REDCAP_ON_COMPLETE_SCRIPT="$complete_stub" \
    REDCAP_HOST_PROCESS_PID="$pid" \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-task-complete-guard.sh" "$host" >/dev/null \
        || fail "task complete guard host passthrough case failed"

    marker_path="$(redcap_runtime_path "layerB/current-report-path")"
    assert_exists "$marker_path"
    assert_eq "$(read_file_text "$marker_path")" "$report_rel"
    assert_eq "$(read_file_text "$complete_log")" "$host"
    register_count="0"
    [[ -f "$register_log" ]] && register_count="$(wc -l < "$register_log" | tr -d '[:space:]')"
    assert_num_eq "$register_count" 0

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-cleanup" "task-complete-guard-passes-host-to-on-complete" >/dev/null 2>&1 || true
    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_complete_guard_avoids_ambiguous_reports_case() {
    local host="copilot"
    local binding_key pid current_head marker_path status_path
    local report_a report_b case_dir register_log complete_log register_stub complete_stub
    local task_complete_slice

    log "case: task-complete-guard-avoids-ambiguous-reports"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "task-complete-guard-avoids-ambiguous-reports" >/dev/null 2>&1 || true

    binding_key="acceptance-task-complete-ambiguous-${RANDOM}-$$"
    pid="$((66100 + RANDOM))"
    init_bound_runtime "$host" "$binding_key" "$pid"
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for ambiguous report case"

    report_a="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-task-complete-ambiguous-a-${RANDOM}-$$.md"
    report_b="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-task-complete-ambiguous-b-${RANDOM}-$$.md"
    printf '# acceptance ambiguous report a\n' >"$report_a"
    printf '# acceptance ambiguous report b\n' >"$report_b"
    LEGACY_TMP_FILES+=("$report_a" "$report_b")

    task_complete_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    case_dir="$(mktemp -d "$ACCEPT_ROOT/task-complete-ambiguous.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    register_log="$case_dir/register.log"
    complete_log="$case_dir/on-complete.log"
    register_stub="$case_dir/register-stub.sh"
    complete_stub="$case_dir/on-complete-stub.sh"

    cat >"$register_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
HOST="\${1:?}"
REPORT="\${2:?}"
printf '%s\n' "\$HOST:\$REPORT" >>"$register_log"
EOF
    cat >"$complete_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
source "$REDCAP_ROOT/compass/tools/redcap-runtime-state.sh"
redcap_runtime_attach_existing "\${REDCAP_RUNTIME_SESSION_ID:?}" "\${REDCAP_RUNTIME_CAPABILITY:?}" >/dev/null
marker="\$(redcap_runtime_path "layerB/current-report-path" 2>/dev/null || true)"
[[ -n "\$marker" && -f "\$marker" ]] || exit 1
printf '%s\n' "on-complete" >>"$complete_log"
EOF
    chmod +x "$register_stub" "$complete_stub"

    REDCAP_TASK_COMPLETE_SLICE="$task_complete_slice" \
    REDCAP_TASK_REPORT_REGISTER_SCRIPT="$register_stub" \
    REDCAP_ON_COMPLETE_SCRIPT="$complete_stub" \
    REDCAP_HOST_PROCESS_PID="$pid" \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-task-complete-guard.sh" "$host" >/dev/null \
        || fail "task complete guard ambiguous report run failed"

    marker_path="$(redcap_runtime_path "layerB/current-report-path")"
    assert_not_exists "$marker_path"
    assert_not_exists "$register_log"
    assert_not_exists "$complete_log"
    status_path="$(redcap_runtime_path "layerB/task-complete-guard/last-status")"
    assert_exists "$status_path"
    assert_eq "$(read_file_text "$status_path")" "retry-needed"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_complete_guard_skips_stale_pending_artifact_case() {
    local host="copilot"
    local binding_key pid current_head marker_path status_path
    local report_old report_new report_old_rel case_dir register_log complete_log register_stub complete_stub
    local task_complete_slice

    log "case: task-complete-guard-skips-stale-pending-artifact"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "task-complete-guard-skips-stale-pending-artifact" >/dev/null 2>&1 || true

    binding_key="acceptance-task-complete-stale-pending-${RANDOM}-$$"
    pid="$((66150 + RANDOM))"
    init_bound_runtime "$host" "$binding_key" "$pid"
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for stale pending case"

    report_old="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-task-complete-stale-old-${RANDOM}-$$.md"
    report_new="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-task-complete-stale-new-${RANDOM}-$$.md"
    report_old_rel="${report_old#$REDCAP_ROOT/}"
    printf '# acceptance stale old report\n' >"$report_old"
    printf '# acceptance stale new report\n' >"$report_new"
    LEGACY_TMP_FILES+=("$report_old" "$report_new")
    redcap_interop_write_pending_closure \
        "$REDCAP_ROOT" \
        "$REDCAP_ROOT/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "task-report,review,notify" \
        "task-complete-guard-skips-stale-pending-artifact" \
        "$report_old_rel" \
        "$current_head" \
        "$current_head" \
        >/dev/null || fail "failed to seed stale pending artifact"

    task_complete_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    case_dir="$(mktemp -d "$ACCEPT_ROOT/task-complete-stale-pending.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    register_log="$case_dir/register.log"
    complete_log="$case_dir/on-complete.log"
    register_stub="$case_dir/register-stub.sh"
    complete_stub="$case_dir/on-complete-stub.sh"

    cat >"$register_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
HOST="\${1:?}"
REPORT="\${2:?}"
printf '%s\n' "\$HOST:\$REPORT" >>"$register_log"
EOF
    cat >"$complete_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
source "$REDCAP_ROOT/compass/tools/redcap-runtime-state.sh"
redcap_runtime_attach_existing "\${REDCAP_RUNTIME_SESSION_ID:?}" "\${REDCAP_RUNTIME_CAPABILITY:?}" >/dev/null
marker="\$(redcap_runtime_path "layerB/current-report-path" 2>/dev/null || true)"
[[ -n "\$marker" && -f "\$marker" ]] || exit 1
printf '%s\n' "on-complete" >>"$complete_log"
EOF
    chmod +x "$register_stub" "$complete_stub"

    REDCAP_TASK_COMPLETE_SLICE="$task_complete_slice" \
    REDCAP_TASK_REPORT_REGISTER_SCRIPT="$register_stub" \
    REDCAP_ON_COMPLETE_SCRIPT="$complete_stub" \
    REDCAP_HOST_PROCESS_PID="$pid" \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-task-complete-guard.sh" "$host" >/dev/null \
        || fail "task complete guard stale pending run failed"

    marker_path="$(redcap_runtime_path "layerB/current-report-path")"
    assert_not_exists "$marker_path"
    assert_not_exists "$register_log"
    assert_not_exists "$complete_log"
    status_path="$(redcap_runtime_path "layerB/task-complete-guard/last-status")"
    assert_exists "$status_path"
    assert_eq "$(read_file_text "$status_path")" "retry-needed"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-cleanup" "task-complete-guard-skips-stale-pending-artifact" >/dev/null 2>&1 || true
    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_complete_guard_normalizes_absolute_pending_anchor_case() {
    local host="copilot"
    local repo binding_key pid current_head marker_path pending_state
    local report_path report_rel case_dir complete_log complete_stub task_complete_slice

    log "case: task-complete-guard-normalizes-absolute-pending-anchor"

    redcap_runtime_clear_context
    repo="$ACCEPT_ROOT/task-complete-absolute-pending-repo/repo"
    create_task_report_fixture_repo "$repo"
    binding_key="acceptance-task-complete-absolute-pending-${RANDOM}-$$"
    pid="$((66160 + RANDOM))"
    init_bound_runtime_for_repo "$host" "$repo" "$binding_key" "$pid"
    current_head="$(git -C "$repo" rev-parse HEAD)"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for absolute pending case"

    report_path="$repo/compass/docs/task-reports/zz-acceptance-task-complete-absolute-${RANDOM}-$$.md"
    report_rel="${report_path#$repo/}"
    cp "$repo/references/task-report-template.md" "$report_path"
    redcap_interop_write_pending_closure \
        "$repo" \
        "$repo/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "task-report,review,notify" \
        "task-complete-guard-normalizes-absolute-pending-anchor" \
        "$report_path" \
        "$current_head" \
        "$current_head" \
        >/dev/null || fail "failed to seed absolute pending anchor"
    pending_state="$(redcap_interop_pending_closure_file "$repo" "$repo/.dev-task.md")"
    python3 - "$pending_state" "$report_path" <<'PY'
import pathlib
import re
import sys

state_file = pathlib.Path(sys.argv[1])
artifact_path = sys.argv[2]
text = state_file.read_text(encoding="utf-8")
text, count = re.subn(r"^artifact_path:.*$", f"artifact_path: {artifact_path}", text, count=1, flags=re.MULTILINE)
if count != 1:
    raise SystemExit(1)
state_file.write_text(text, encoding="utf-8")
PY

    task_complete_slice="$(redcap_dev_task_extract_kv "$repo/.dev-task.md" "active_slice")"
    case_dir="$(mktemp -d "$ACCEPT_ROOT/task-complete-absolute-pending.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    complete_log="$case_dir/on-complete.log"
    complete_stub="$case_dir/on-complete-stub.sh"

    cat >"$complete_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
source "$repo/compass/tools/redcap-runtime-state.sh"
redcap_runtime_attach_existing "\${REDCAP_RUNTIME_SESSION_ID:?}" "\${REDCAP_RUNTIME_CAPABILITY:?}" >/dev/null
marker="\$(redcap_runtime_path "layerB/current-report-path" 2>/dev/null || true)"
[[ -n "\$marker" && -f "\$marker" ]] || exit 1
printf '%s\n' "on-complete" >>"$complete_log"
EOF
    chmod +x "$complete_stub"

    REDCAP_TASK_COMPLETE_SLICE="$task_complete_slice" \
    REDCAP_ON_COMPLETE_SCRIPT="$complete_stub" \
    REDCAP_HOST_PROCESS_PID="$pid" \
        bash "$repo/compass/tools/redcap-layerB-task-complete-guard.sh" "$host" >/dev/null \
        || fail "task complete guard absolute pending anchor case failed"

    marker_path="$(redcap_runtime_path "layerB/current-report-path")"
    pending_state="$(redcap_interop_pending_closure_existing_file "$repo" "$repo/.dev-task.md" 2>/dev/null || true)"
    assert_exists "$marker_path"
    assert_exists "$pending_state"
    assert_eq "$(read_file_text "$marker_path")" "$report_rel"
    assert_eq "$(redcap_interop_read_state_field "$pending_state" "artifact_path" 2>/dev/null || true)" "$report_rel"
    assert_exists "$complete_log"

    redcap_interop_clear_pending_closure "$repo" "$repo/.dev-task.md" "acceptance-cleanup" "task-complete-guard-normalizes-absolute-pending-anchor" >/dev/null 2>&1 || true
    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_on_complete_records_backlog_spec_redlines_case() {
    local case_dir validator_stub current_head pending_state required_redlines

    log "case: on-complete-records-backlog-spec-redlines"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "on-complete-records-backlog-spec-redlines" >/dev/null 2>&1 || true
    case_dir="$(mktemp -d "$ACCEPT_ROOT/on-complete-backlog-spec.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    validator_stub="$case_dir/validator-stub.sh"

    cat >"$validator_stub" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
[redcap-validator-chain] mode=on-complete overall=fail
[1] commit-proof-check :: pass
commit-proof ok
[2] pm-gate :: pass
pm-gate ok
[3] drift-check :: pass
drift ok
[4] backlog-check :: fail
backlog failed
[5] spec-check :: fail
spec failed
[6] task-report-check :: pass
task-report ok
[7] artifact-lifecycle-check :: pass
artifact ok
OUT
exit 1
EOF
    chmod +x "$validator_stub"

    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    if REDCAP_SKIP_FEISHU=1 REDCAP_VALIDATOR_CHAIN_SCRIPT="$validator_stub" \
        bash "$REDCAP_ROOT/compass/tools/redcap-on-complete.sh" "$REDCAP_ROOT" "$current_head" redcap >/dev/null 2>&1; then
        fail "on-complete unexpectedly succeeded with backlog/spec failures"
    fi

    pending_state="$(redcap_interop_pending_closure_file "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md")"
    assert_exists "$pending_state"
    required_redlines="$(redcap_interop_read_state_field "$pending_state" "required_redlines" 2>/dev/null || true)"
    assert_eq "$(normalize_csv "$required_redlines")" "$(normalize_csv "backlog,spec")"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-cleanup" "on-complete-records-backlog-spec-redlines" >/dev/null 2>&1 || true
}

run_on_complete_uses_explicit_validator_host_case() {
    local case_dir validator_stub host_log current_head

    log "case: on-complete-uses-explicit-validator-host"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/on-complete-host.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    host_log="$case_dir/validator-host.log"
    validator_stub="$case_dir/validator-stub.sh"

    cat >"$validator_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf '%s|%s\n' "\${2:-missing}" "\${REDCAP_RUNTIME_HOST:-missing}" >"$host_log"
cat <<'OUT'
[redcap-validator-chain] mode=on-complete overall=pass
[1] commit-proof-check :: pass
commit-proof ok
[2] pm-gate :: pass
pm-gate ok
[3] drift-check :: pass
drift ok
[4] backlog-check :: pass
backlog ok
[5] spec-check :: pass
spec ok
[6] task-report-check :: pass
task-report ok
[7] artifact-lifecycle-check :: pass
artifact ok
OUT
EOF
    chmod +x "$validator_stub"

    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    REDCAP_SKIP_FEISHU=1 \
    REDCAP_ON_COMPLETE_HOST="copilot" \
    REDCAP_RUNTIME_HOST="claude" \
    REDCAP_VALIDATOR_CHAIN_SCRIPT="$validator_stub" \
        bash "$REDCAP_ROOT/compass/tools/redcap-on-complete.sh" "$REDCAP_ROOT" "$current_head" redcap >/dev/null 2>&1 \
        || fail "on-complete should accept explicit validator host"

    assert_eq "$(read_file_text "$host_log")" "copilot|copilot"
}

run_on_complete_prefers_binding_host_over_stale_runtime_host_case() {
    local case_dir validator_stub host_log current_head

    log "case: on-complete-prefers-binding-host-over-stale-runtime-host"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/on-complete-binding-host.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    host_log="$case_dir/validator-host.log"
    validator_stub="$case_dir/validator-stub.sh"

    cat >"$validator_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf '%s|%s\n' "\${2:-missing}" "\${REDCAP_RUNTIME_HOST:-missing}" >"$host_log"
cat <<'OUT'
[redcap-validator-chain] mode=on-complete overall=pass
[1] commit-proof-check :: pass
commit-proof ok
[2] pm-gate :: pass
pm-gate ok
[3] drift-check :: pass
drift ok
[4] backlog-check :: pass
backlog ok
[5] spec-check :: pass
spec ok
[6] task-report-check :: pass
task-report ok
[7] artifact-lifecycle-check :: pass
artifact ok
OUT
EOF
    chmod +x "$validator_stub"

    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    REDCAP_SKIP_FEISHU=1 \
    REDCAP_SESSION_BINDING_KEY="host/copilot/session/acceptance-binding-host" \
    REDCAP_RUNTIME_HOST="claude" \
    REDCAP_VALIDATOR_CHAIN_SCRIPT="$validator_stub" \
        bash "$REDCAP_ROOT/compass/tools/redcap-on-complete.sh" "$REDCAP_ROOT" "$current_head" redcap >/dev/null 2>&1 \
        || fail "on-complete should prefer binding host over stale runtime host"

    assert_eq "$(read_file_text "$host_log")" "copilot|copilot"
}

run_pending_closure_clear_restores_on_ledger_failure_case() {
    local current_head report_path state_file clear_result

    log "case: pending-closure-clear-restores-on-ledger-failure"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "pending-closure-clear-restores-on-ledger-failure" >/dev/null 2>&1 || true

    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    report_path="compass/docs/task-reports/2026-04-16-completion-hook-hardening.md"
    state_file="$(
        redcap_interop_write_pending_closure \
            "$REDCAP_ROOT" \
            "$REDCAP_ROOT/.dev-task.md" \
            "copilot" \
            "acceptance-seed" \
            "review,notify" \
            "pending-closure-clear-restores-on-ledger-failure" \
            "$report_path" \
            "$current_head" \
            "$current_head"
    )" || fail "failed to seed pending closure for ledger failure rollback case"

    clear_result="$(
        PROJECT_ROOT="$REDCAP_ROOT" \
        TASK_FILE="$REDCAP_ROOT/.dev-task.md" \
        EXPECTED_UPDATED_AT="$(redcap_interop_read_state_field "$state_file" "updated_at" 2>/dev/null || true)" \
        bash -lc '
            set -euo pipefail
            source "$PROJECT_ROOT/compass/tools/redcap-runtime-state.sh"
            source "$PROJECT_ROOT/compass/tools/redcap-dev-task.sh"
            source "$PROJECT_ROOT/compass/tools/redcap-interop-governance.sh"
            redcap_interop_append_closure_ledger_identity() { return 1; }
            redcap_interop_append_closure_ledger() { return 1; }
            if redcap_interop_clear_pending_closure "$PROJECT_ROOT" "$TASK_FILE" "acceptance-ledger-failure" "forced-ledger-failure" "$EXPECTED_UPDATED_AT"; then
                printf "success\n"
            else
                printf "failed\n"
            fi
        '
    )"
    assert_eq "$clear_result" "failed"
    assert_exists "$state_file"
    assert_eq "$(redcap_interop_read_state_field "$state_file" "artifact_path" 2>/dev/null || true)" "$report_path"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-cleanup" "pending-closure-clear-restores-on-ledger-failure" >/dev/null 2>&1 || true
}

run_session_end_clears_all_matching_pending_states_case() {
    local host="copilot"
    local binding_key pid probe_pid current_head report_path state_file stale_state case_dir validator_stub

    log "case: session-end-clears-all-matching-pending-states"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "session-end-clears-all-matching-pending-states" >/dev/null 2>&1 || true

    binding_key="acceptance-session-end-clear-${RANDOM}-$$"
    pid="$((66250 + RANDOM))"
    spawn_host_probe probe_pid
    export REDCAP_HOST_PROCESS_PID="$pid"
    export REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid"
    redcap_runtime_init_from_binding "$host" "$REDCAP_ROOT" "$binding_key" >/dev/null \
        || fail "failed to initialize runtime binding for session-end clear case"
    REDCAP_SESSION_ISOLATION_MODE="full"
    export REDCAP_HOST_PROCESS_PID REDCAP_SESSION_ISOLATION_MODE REDCAP_RUNTIME_SESSION_ID REDCAP_RUNTIME_BINDING_KEY REDCAP_RUNTIME_HOST REDCAP_RUNTIME_CAPABILITY
    unset REDCAP_HOST_PROCESS_PROBE_PID
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    report_path="compass/docs/task-reports/2026-04-16-completion-hook-hardening.md"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for session-end clear case"
    write_current_report_marker_fixture "$report_path"

    state_file="$(
        redcap_interop_write_pending_closure \
            "$REDCAP_ROOT" \
            "$REDCAP_ROOT/.dev-task.md" \
            "$host" \
            "acceptance-seed" \
            "review,notify" \
            "session-end-clears-all-matching-pending-states" \
            "$report_path" \
            "$current_head" \
            "$current_head"
    )" || fail "failed to seed pending closure for session-end clear case"
    stale_state="$(dirname "$state_file")/$(basename "$state_file" .state)-stale.state"
    cp "$state_file" "$stale_state" || fail "failed to clone stale pending state for session-end clear case"
    LEGACY_TMP_FILES+=("$stale_state")

    case_dir="$(mktemp -d "$ACCEPT_ROOT/session-end-clear.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    validator_stub="$case_dir/validator-pass.sh"
    cat >"$validator_stub" <<EOF
#!/usr/bin/env bash
cat <<'OUT'
[1] review-proof-check :: pass
review clean
[2] reanchor-check :: pass
reanchor clean
[3] pm-gate :: pass
pm gate clean
[4] drift-check :: pass
drift clean
[5] backlog-check :: pass
backlog clean
[6] spec-check :: pass
spec clean
[7] task-report-check :: pass
$report_path
[8] artifact-lifecycle-check :: pass
artifact clean
OUT
EOF
    chmod +x "$validator_stub"

    REDCAP_VALIDATOR_CHAIN_SCRIPT="$validator_stub" \
    REDCAP_SESSION_BINDING_KEY="$binding_key" \
    REDCAP_HOST_PROCESS_PID="$pid" \
    REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid" \
    REDCAP_SKIP_FEISHU=1 \
    REDCAP_SKIP_INDEPENDENT_REVIEW=1 \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-session-end.sh" "$host" >/dev/null \
        || fail "session-end clear all matching states case failed"

    assert_not_exists "$state_file"
    assert_not_exists "$stale_state"
    if redcap_interop_pending_closure_exists "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md"; then
        fail "pending closure still exists after session-end clear all matching states case"
    fi

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_session_end_clears_compatible_pending_refresh_case() {
    local host="copilot"
    local binding_key pid probe_pid current_head report_path state_file case_dir validator_stub

    log "case: session-end-clears-compatible-pending-refresh"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "session-end-clears-compatible-pending-refresh" >/dev/null 2>&1 || true

    binding_key="acceptance-session-end-refresh-${RANDOM}-$$"
    pid="$((66250 + RANDOM))"
    spawn_host_probe probe_pid
    export REDCAP_HOST_PROCESS_PID="$pid"
    export REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid"
    redcap_runtime_init_from_binding "$host" "$REDCAP_ROOT" "$binding_key" >/dev/null \
        || fail "failed to initialize runtime binding for session-end refresh case"
    REDCAP_SESSION_ISOLATION_MODE="full"
    export REDCAP_HOST_PROCESS_PID REDCAP_SESSION_ISOLATION_MODE REDCAP_RUNTIME_SESSION_ID REDCAP_RUNTIME_BINDING_KEY REDCAP_RUNTIME_HOST REDCAP_RUNTIME_CAPABILITY
    unset REDCAP_HOST_PROCESS_PROBE_PID
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    report_path="compass/docs/task-reports/2026-04-16-completion-hook-hardening.md"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for session-end refresh case"
    write_current_report_marker_fixture "$report_path"

    state_file="$(
        redcap_interop_write_pending_closure \
            "$REDCAP_ROOT" \
            "$REDCAP_ROOT/.dev-task.md" \
            "$host" \
            "acceptance-seed" \
            "review,notify" \
            "session-end-clears-compatible-pending-refresh" \
            "$report_path" \
            "$current_head" \
            "$current_head"
    )" || fail "failed to seed pending closure for session-end refresh case"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/session-end-refresh.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    validator_stub="$case_dir/validator-refresh-pass.sh"
    cat >"$validator_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
sleep 1
source "$REDCAP_ROOT/compass/tools/redcap-runtime-state.sh"
source "$REDCAP_ROOT/compass/tools/redcap-dev-task.sh"
source "$REDCAP_ROOT/compass/tools/redcap-interop-governance.sh"
redcap_interop_write_pending_closure \\
    "$REDCAP_ROOT" \\
    "$REDCAP_ROOT/.dev-task.md" \\
    "$host" \\
    "acceptance-compatible-refresh" \\
    "pending-closure" \\
    "compatible-refresh" \\
    "$report_path" \\
    "$current_head" \\
    "$current_head" \\
    "replace" \\
    >/dev/null
cat <<'OUT'
[1] review-proof-check :: pass
review clean
[2] reanchor-check :: pass
reanchor clean
[3] pm-gate :: pass
pm gate clean
[4] drift-check :: pass
drift clean
[5] backlog-check :: pass
backlog clean
[6] spec-check :: pass
spec clean
[7] task-report-check :: pass
$report_path
[8] artifact-lifecycle-check :: pass
artifact clean
OUT
EOF
    chmod +x "$validator_stub"

    REDCAP_VALIDATOR_CHAIN_SCRIPT="$validator_stub" \
    REDCAP_SESSION_BINDING_KEY="$binding_key" \
    REDCAP_HOST_PROCESS_PID="$pid" \
    REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid" \
    REDCAP_SKIP_FEISHU=1 \
    REDCAP_SKIP_INDEPENDENT_REVIEW=1 \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-session-end.sh" "$host" >/dev/null \
        || fail "session-end compatible pending refresh case failed"

    assert_not_exists "$state_file"
    if redcap_interop_pending_closure_exists "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md"; then
        fail "pending closure still exists after compatible refresh clear case"
    fi

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_session_end_clears_closeout_runtime_pending_case() {
    local host="copilot"
    local binding_key pid probe_pid current_head report_path state_file case_dir validator_stub

    log "case: session-end-clears-closeout-runtime-pending"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "session-end-clears-closeout-runtime-pending" >/dev/null 2>&1 || true

    binding_key="acceptance-session-end-closeout-${RANDOM}-$$"
    pid="$((66250 + RANDOM))"
    spawn_host_probe probe_pid
    export REDCAP_HOST_PROCESS_PID="$pid"
    export REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid"
    redcap_runtime_init_from_binding "$host" "$REDCAP_ROOT" "$binding_key" >/dev/null \
        || fail "failed to initialize runtime binding for session-end closeout clear case"
    REDCAP_SESSION_ISOLATION_MODE="full"
    export REDCAP_HOST_PROCESS_PID REDCAP_SESSION_ISOLATION_MODE REDCAP_RUNTIME_SESSION_ID REDCAP_RUNTIME_BINDING_KEY REDCAP_RUNTIME_HOST REDCAP_RUNTIME_CAPABILITY
    unset REDCAP_HOST_PROCESS_PROBE_PID
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    report_path="compass/docs/task-reports/2026-04-23-layerb-fsm-workmode-hardening.md"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for session-end closeout clear case"
    write_current_report_marker_fixture "$report_path"

    state_file="$(
        redcap_interop_write_pending_closure \
            "$REDCAP_ROOT" \
            "$REDCAP_ROOT/.dev-task.md" \
            "$host" \
            "acceptance-seed" \
            "review,task-report,pending-closure,pm-gate,drift,artifact-lifecycle,notify,closeout-runtime" \
            "session-end-clears-closeout-runtime-pending" \
            "$report_path" \
            "1d6b320909c53d479ec1f29e4430a1113ea49134" \
            "1d6b320909c53d479ec1f29e4430a1113ea49134"
    )" || fail "failed to seed closeout-runtime pending closure"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/session-end-closeout-clear.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    validator_stub="$case_dir/validator-pass.sh"
    cat >"$validator_stub" <<EOF
#!/usr/bin/env bash
cat <<'OUT'
[1] review-proof-check :: pass
review clean
[2] reanchor-check :: pass
reanchor clean
[3] pm-gate :: pass
pm gate clean
[4] drift-check :: pass
drift clean
[5] backlog-check :: pass
backlog clean
[6] spec-check :: pass
spec clean
[7] task-report-check :: pass
$report_path
[8] artifact-lifecycle-check :: pass
artifact clean
OUT
EOF
    chmod +x "$validator_stub"

    REDCAP_VALIDATOR_CHAIN_SCRIPT="$validator_stub" \
    REDCAP_SESSION_BINDING_KEY="$binding_key" \
    REDCAP_HOST_PROCESS_PID="$pid" \
    REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid" \
    REDCAP_SKIP_FEISHU=1 \
    REDCAP_SKIP_INDEPENDENT_REVIEW=1 \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-session-end.sh" "$host" >/dev/null \
        || fail "session-end closeout-runtime clear case failed"

    assert_not_exists "$state_file"
    if redcap_interop_pending_closure_exists "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md"; then
        fail "pending closure still exists after clearing closeout-runtime-compatible blocker set"
    fi

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_report_check_prefers_anchor_case() {
    local host="claude"
    local repo baseline_head current_head binding_key pid output
    local report_a report_b rel_a rel_b

    log "case: task-report-check-prefers-anchor"

    redcap_runtime_clear_context
    repo="$ACCEPT_ROOT/task-report-prefers-anchor/repo"
    create_task_report_fixture_repo "$repo"
    baseline_head="$(git -C "$repo" rev-parse HEAD)"

    rel_a="compass/docs/task-reports/zz-acceptance-task-report-anchor-a-${RANDOM}-$$.md"
    rel_b="compass/docs/task-reports/zz-acceptance-task-report-anchor-b-${RANDOM}-$$.md"
    report_a="$repo/$rel_a"
    report_b="$repo/$rel_b"
    cp "$repo/references/task-report-template.md" "$report_a"
    git -C "$repo" add "$rel_a"
    git -C "$repo" commit --quiet -m "add older anchor report"

    cp "$repo/references/task-report-template.md" "$report_b"
    git -C "$repo" add "$rel_b"
    git -C "$repo" commit --quiet -m "add latest anchor report"

    binding_key="acceptance-task-report-anchor-${RANDOM}-$$"
    pid="$((66200 + RANDOM))"
    init_bound_runtime_for_repo "$host" "$repo" "$binding_key" "$pid"
    write_current_report_marker_fixture "$rel_b" "$repo/.dev-task.md"
    current_head="$(git -C "$repo" rev-parse HEAD)"
    redcap_interop_write_pending_closure \
        "$repo" \
        "$repo/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "task-report,review,notify" \
        "task-report-check-prefers-anchor" \
        "$rel_b" \
        "$baseline_head" \
        "$current_head" \
        >/dev/null || fail "failed to seed pending closure for task-report-check anchor case"

    output="$(REDCAP_HOST_PROCESS_PID="$pid" bash "$repo/compass/tools/redcap-task-report-check.sh" "$repo" "$baseline_head" "$current_head" "$host")"
    assert_eq "$output" "$rel_b"

    redcap_interop_clear_pending_closure "$repo" "$repo/.dev-task.md" "acceptance-cleanup" "task-report-check-prefers-anchor" >/dev/null 2>&1 || true
    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_report_check_allows_marker_anchor_when_uniquely_latest_case() {
    local host="copilot"
    local repo baseline_head current_head binding_key pid output
    local older_rel older_report marker_rel marker_report

    log "case: task-report-check-allows-marker-anchor-when-uniquely-latest"

    redcap_runtime_clear_context
    repo="$ACCEPT_ROOT/task-report-marker-unique-latest/repo"
    create_task_report_fixture_repo "$repo"
    baseline_head="$(git -C "$repo" rev-parse HEAD)"

    older_rel="compass/docs/task-reports/zz-acceptance-marker-older-${RANDOM}-$$.md"
    older_report="$repo/$older_rel"
    cp "$repo/references/task-report-template.md" "$older_report"
    git -C "$repo" add "$older_rel"
    git -C "$repo" commit --quiet -m "add older marker report"

    marker_rel="compass/docs/task-reports/zz-acceptance-marker-latest-${RANDOM}-$$.md"
    marker_report="$repo/$marker_rel"
    cp "$repo/references/task-report-template.md" "$marker_report"
    git -C "$repo" add "$marker_rel"
    git -C "$repo" commit --quiet -m "add latest marker report"
    current_head="$(git -C "$repo" rev-parse HEAD)"

    binding_key="acceptance-task-report-marker-latest-${RANDOM}-$$"
    pid="$((66320 + RANDOM))"
    init_bound_runtime_for_repo "$host" "$repo" "$binding_key" "$pid"
    write_current_report_marker_fixture "$marker_rel" "$repo/.dev-task.md"

    output="$(REDCAP_HOST_PROCESS_PID="$pid" bash "$repo/compass/tools/redcap-task-report-check.sh" "$repo" "$baseline_head" "$current_head" "$host")"
    assert_eq "$output" "$marker_rel"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_report_check_allows_pending_anchor_when_uniquely_latest_case() {
    local host="copilot"
    local repo baseline_head current_head
    local older_rel latest_rel output

    log "case: task-report-check-allows-pending-anchor-when-uniquely-latest"

    redcap_runtime_clear_context
    repo="$ACCEPT_ROOT/task-report-pending-anchor-latest/repo"
    create_task_report_fixture_repo "$repo"
    baseline_head="$(git -C "$repo" rev-parse HEAD)"
    older_rel="compass/docs/task-reports/zz-acceptance-pending-older-${RANDOM}-$$.md"
    latest_rel="compass/docs/task-reports/zz-acceptance-pending-latest-${RANDOM}-$$.md"
    cp "$repo/references/task-report-template.md" "$repo/$older_rel"
    git -C "$repo" add "$older_rel"
    git -C "$repo" commit --quiet -m "add older report"
    cp "$repo/references/task-report-template.md" "$repo/$latest_rel"
    git -C "$repo" add "$latest_rel"
    git -C "$repo" commit --quiet -m "add latest report"
    current_head="$(git -C "$repo" rev-parse HEAD)"

    redcap_interop_write_pending_closure \
        "$repo" \
        "$repo/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "task-report,review,notify" \
        "task-report-check-allows-pending-anchor-when-uniquely-latest" \
        "$latest_rel" \
        "$baseline_head" \
        "$current_head" \
        >/dev/null || fail "failed to seed pending closure for latest pending anchor case"

    output="$(bash "$repo/compass/tools/redcap-task-report-check.sh" "$repo" "$baseline_head" "$current_head" "$host")" \
        || fail "task-report-check should allow uniquely latest pending anchor"
    assert_eq "$output" "$latest_rel"

    redcap_interop_clear_pending_closure "$repo" "$repo/.dev-task.md" "acceptance-cleanup" "task-report-check-allows-pending-anchor-when-uniquely-latest" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_report_check_rejects_stale_pending_anchor_conflict_case() {
    local host="copilot"
    local repo baseline_head current_head
    local stale_rel newer_rel output status

    log "case: task-report-check-rejects-stale-pending-anchor-conflict"

    redcap_runtime_clear_context
    repo="$ACCEPT_ROOT/task-report-stale-pending-anchor/repo"
    create_task_report_fixture_repo "$repo"
    baseline_head="$(git -C "$repo" rev-parse HEAD)"
    stale_rel="compass/docs/task-reports/zz-acceptance-pending-stale-${RANDOM}-$$.md"
    newer_rel="compass/docs/task-reports/zz-acceptance-pending-newer-${RANDOM}-$$.md"
    cp "$repo/references/task-report-template.md" "$repo/$stale_rel"
    git -C "$repo" add "$stale_rel"
    git -C "$repo" commit --quiet -m "add stale report"
    cp "$repo/references/task-report-template.md" "$repo/$newer_rel"
    git -C "$repo" add "$newer_rel"
    git -C "$repo" commit --quiet -m "add newer report"
    current_head="$(git -C "$repo" rev-parse HEAD)"

    redcap_interop_write_pending_closure \
        "$repo" \
        "$repo/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "task-report,review,notify" \
        "task-report-check-rejects-stale-pending-anchor-conflict" \
        "$stale_rel" \
        "$baseline_head" \
        "$current_head" \
        >/dev/null || fail "failed to seed pending closure for stale pending anchor case"

    set +e
    output="$(bash "$repo/compass/tools/redcap-task-report-check.sh" "$repo" "$baseline_head" "$current_head" "$host" 2>&1)"
    status=$?
    set -e
    [[ "$status" -ne 0 ]] || fail "task-report-check unexpectedly accepted stale pending anchor conflict"
    assert_string_contains "$output" "stale pending report anchor conflicts with newer changed task reports"

    redcap_interop_clear_pending_closure "$repo" "$repo/.dev-task.md" "acceptance-cleanup" "task-report-check-rejects-stale-pending-anchor-conflict" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_report_check_requires_summary_for_untracked_anchor_case() {
    local host="claude"
    local binding_key pid current_head rel_path output report_path

    log "case: task-report-check-requires-summary-for-untracked-anchor"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "task-report-check-requires-summary-for-untracked-anchor" >/dev/null 2>&1 || true

    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-task-report-incomplete-${RANDOM}-$$.md"
    rel_path="${report_path#$REDCAP_ROOT/}"
    cat >"$report_path" <<'EOF'
# 任务完成报告：Acceptance Incomplete Report

**报告日期**：2026-04-16
**执行者**：Cap（Acceptance）
**报告版本**：v1.0

---

## 一、需求背景
fixture

## 二、方案讨论
fixture

## 三、落地结果
fixture

## 四、人工审核要点
fixture

## 五、验证结果
fixture

## 六、遗留问题与下一步
fixture

## 七、经验沉淀
fixture

## 八、附录
fixture
EOF
    LEGACY_TMP_FILES+=("$report_path")

    binding_key="acceptance-task-report-incomplete-${RANDOM}-$$"
    pid="$((66300 + RANDOM))"
    init_bound_runtime "$host" "$binding_key" "$pid"
    write_current_report_marker_fixture "$rel_path"
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    redcap_interop_write_pending_closure \
        "$REDCAP_ROOT" \
        "$REDCAP_ROOT/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "task-report,review,notify" \
        "task-report-check-requires-summary-for-untracked-anchor" \
        "$rel_path" \
        "$current_head" \
        "$current_head" \
        >/dev/null || fail "failed to seed pending closure for incomplete report case"

    if output="$(REDCAP_HOST_PROCESS_PID="$pid" bash "$REDCAP_ROOT/compass/tools/redcap-task-report-check.sh" "$REDCAP_ROOT" "$current_head" "$current_head" "$host" 2>&1)"; then
        fail "task-report-check unexpectedly accepted incomplete anchored report"
    fi
    case "$output" in
        *"incomplete summary template"*|*"anchored task report is not template-complete"*) ;;
        *)
            fail "task-report-check incomplete anchor output did not mention summary/template failure"
            ;;
    esac

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-cleanup" "task-report-check-requires-summary-for-untracked-anchor" >/dev/null 2>&1 || true
    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_report_check_accepts_legacy_pending_anchor_case() {
    local repo legacy_rel current_head output

    log "case: task-report-check-accepts-legacy-pending-anchor"

    redcap_runtime_clear_context
    repo="$ACCEPT_ROOT/task-report-legacy-pending-anchor/repo"
    create_task_report_fixture_repo "$repo"
    legacy_rel="compass/docs/task-reports/2026-04-12-continuity-governance-session-adoption.md"
    mkdir -p "$(dirname "$repo/$legacy_rel")"
    cp "$REDCAP_ROOT/$legacy_rel" "$repo/$legacy_rel"
    git -C "$repo" add "$legacy_rel"
    git -C "$repo" commit --quiet -m "add legacy report anchor"
    current_head="$(git -C "$repo" rev-parse HEAD)"

    redcap_interop_write_pending_closure \
        "$repo" \
        "$repo/.dev-task.md" \
        "copilot" \
        "acceptance-seed" \
        "task-report,review,notify" \
        "task-report-check-accepts-legacy-pending-anchor" \
        "$legacy_rel" \
        "$current_head" \
        "$current_head" \
        >/dev/null || fail "failed to seed legacy pending anchor"

    output="$(bash "$repo/compass/tools/redcap-task-report-check.sh" "$repo" "$current_head" "$current_head")"
    assert_eq "$output" "$legacy_rel"

    redcap_interop_clear_pending_closure "$repo" "$repo/.dev-task.md" "acceptance-cleanup" "task-report-check-accepts-legacy-pending-anchor" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_report_check_rejects_stale_marker_conflict_case() {
    local host="copilot"
    local repo legacy_rel baseline_head current_head binding_key pid new_report output

    log "case: task-report-check-rejects-stale-marker-conflict"

    redcap_runtime_clear_context
    repo="$ACCEPT_ROOT/task-report-stale-marker-conflict/repo"
    create_task_report_fixture_repo "$repo"
    baseline_head="$(git -C "$repo" rev-parse HEAD)"
    legacy_rel="compass/docs/task-reports/zz-acceptance-stale-marker-old-${RANDOM}-$$.md"
    cp "$repo/references/task-report-template.md" "$repo/$legacy_rel"
    git -C "$repo" add "$legacy_rel"
    git -C "$repo" commit --quiet -m "add legacy marker report"
    current_head="$(git -C "$repo" rev-parse HEAD)"

    binding_key="acceptance-task-report-stale-marker-${RANDOM}-$$"
    pid="$((66350 + RANDOM))"
    init_bound_runtime_for_repo "$host" "$repo" "$binding_key" "$pid"
    write_current_report_marker_fixture "$legacy_rel" "$repo/.dev-task.md"

    new_report="$repo/compass/docs/task-reports/zz-acceptance-stale-marker-new-${RANDOM}-$$.md"
    cp "$repo/references/task-report-template.md" "$new_report"

    set +e
    output="$(REDCAP_HOST_PROCESS_PID="$pid" bash "$repo/compass/tools/redcap-task-report-check.sh" "$repo" "$baseline_head" "$current_head" "$host" 2>&1)"
    status=$?
    set -e
    [[ "$status" -ne 0 ]] || fail "task-report-check unexpectedly accepted stale marker conflict"
    assert_string_contains "$output" "stale marker anchor conflicts with newer changed task reports"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_complete_guard_replaces_stale_marker_with_unique_report_case() {
    local host="copilot"
    local repo legacy_rel current_head binding_key pid case_dir register_log complete_log register_stub complete_stub marker_path task_complete_slice
    local new_report new_rel register_count complete_count

    log "case: task-complete-guard-replaces-stale-marker-with-unique-report"

    redcap_runtime_clear_context
    repo="$ACCEPT_ROOT/task-complete-stale-marker/repo"
    create_task_report_fixture_repo "$repo"
    legacy_rel="compass/docs/task-reports/2026-04-12-continuity-governance-session-adoption.md"
    mkdir -p "$(dirname "$repo/$legacy_rel")"
    cp "$REDCAP_ROOT/$legacy_rel" "$repo/$legacy_rel"
    git -C "$repo" add "$legacy_rel"
    git -C "$repo" commit --quiet -m "add legacy stale marker report"
    current_head="$(git -C "$repo" rev-parse HEAD)"

    binding_key="acceptance-task-complete-stale-marker-${RANDOM}-$$"
    pid="$((66400 + RANDOM))"
    init_bound_runtime_for_repo "$host" "$repo" "$binding_key" "$pid"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for stale marker guard case"
    write_current_report_marker_fixture "$legacy_rel" "$repo/.dev-task.md"
    task_complete_slice="$(redcap_dev_task_extract_kv "$repo/.dev-task.md" "active_slice")"

    new_report="$repo/compass/docs/task-reports/zz-acceptance-stale-marker-new-${RANDOM}-$$.md"
    new_rel="${new_report#$repo/}"
    cat >"$new_report" <<'EOF'
# 任务完成报告：Acceptance Guard Stale Marker New

**报告日期**：2026-04-16
**执行者**：Cap（Acceptance）
**报告版本**：v1.0

---

## 零、先看懂当前局面
### 0.1 当前已完成
- 当前已完成：fixture
- 详情：fixture
### 0.2 上一步完成的是
- 上一步完成的是：fixture
### 0.3 下一步计划做的是
- 下一步计划做的是：fixture
### 0.4 整体计划脉络图与当前位置
- 整体计划脉络图是：fixture
- 当前所在位置：fixture

---

## 一、需求背景
fixture

## 二、方案讨论
fixture

## 三、落地结果
fixture

### 3.2.1 术语对照（按文件/功能解释）
| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| fixture | fixture | fixture |

## 四、人工审核要点
fixture

## 五、验证结果
fixture

## 六、遗留问题与下一步
fixture

## 七、经验沉淀
fixture

## 八、附录
fixture
EOF
    LEGACY_TMP_FILES+=("$new_report")

    case_dir="$(mktemp -d "$ACCEPT_ROOT/task-complete-stale-marker.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    register_log="$case_dir/register.log"
    complete_log="$case_dir/on-complete.log"
    register_stub="$case_dir/register-stub.sh"
    complete_stub="$case_dir/on-complete-stub.sh"

    cat >"$register_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
HOST="\${1:?}"
REPORT="\${2:?}"
REL="\$(python3 - <<'PY' "\$REPORT" "$repo"
import os
import sys
print(os.path.relpath(sys.argv[1], sys.argv[2]))
PY
)"
source "$repo/compass/tools/redcap-runtime-state.sh"
source "$repo/compass/tools/redcap-interop-governance.sh"
redcap_runtime_attach_existing "\${REDCAP_RUNTIME_SESSION_ID:?}" "\${REDCAP_RUNTIME_CAPABILITY:?}" >/dev/null
printf '%s\n' "\$REPORT" >>"$register_log"
redcap_interop_write_current_report_marker "\$REL" "$repo/.dev-task.md" >/dev/null
EOF
    cat >"$complete_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "on-complete" >>"$complete_log"
EOF
    chmod +x "$register_stub" "$complete_stub"

    REDCAP_TASK_COMPLETE_SLICE="$task_complete_slice" \
    REDCAP_TASK_REPORT_REGISTER_SCRIPT="$register_stub" \
    REDCAP_ON_COMPLETE_SCRIPT="$complete_stub" \
    REDCAP_HOST_PROCESS_PID="$pid" \
        bash "$repo/compass/tools/redcap-layerB-task-complete-guard.sh" "$host" >/dev/null \
        || fail "task complete guard stale marker replacement case failed"

    marker_path="$(redcap_runtime_path "layerB/current-report-path")"
    assert_exists "$marker_path"
    assert_eq "$(read_file_text "$marker_path")" "$new_rel"
    register_count="$(wc -l < "$register_log" | tr -d '[:space:]')"
    complete_count="$(wc -l < "$complete_log" | tr -d '[:space:]')"
    assert_num_eq "$register_count" 1
    assert_num_eq "$complete_count" 1

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_report_check_rejects_zero_diff_stale_marker_case() {
    local host="copilot"
    local repo legacy_rel current_head binding_key pid output status stale_hash

    log "case: task-report-check-rejects-zero-diff-stale-marker"

    redcap_runtime_clear_context
    repo="$ACCEPT_ROOT/task-report-zero-diff-stale-marker/repo"
    create_task_report_fixture_repo "$repo"
    legacy_rel="compass/docs/task-reports/2026-04-12-continuity-governance-session-adoption.md"
    mkdir -p "$(dirname "$repo/$legacy_rel")"
    cp "$REDCAP_ROOT/$legacy_rel" "$repo/$legacy_rel"
    git -C "$repo" add "$legacy_rel"
    git -C "$repo" commit --quiet -m "add zero diff stale marker report"
    current_head="$(git -C "$repo" rev-parse HEAD)"
    stale_hash="deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"

    binding_key="acceptance-task-report-zero-diff-stale-${RANDOM}-$$"
    pid="$((66420 + RANDOM))"
    init_bound_runtime_for_repo "$host" "$repo" "$binding_key" "$pid"
    write_current_report_marker_with_hash_fixture "$legacy_rel" "$stale_hash" "$repo/.dev-task.md"

    set +e
    output="$(bash "$repo/compass/tools/redcap-task-report-check.sh" "$repo" "$current_head" "$current_head" "$host" 2>&1)"
    status=$?
    set -e
    [[ "$status" -ne 0 ]] || fail "task-report-check unexpectedly accepted zero diff stale marker"
    assert_string_contains "$output" "missing task report under compass/docs/task-reports/"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_report_check_ignores_invalid_pending_artifact_case() {
    local host="copilot"
    local repo current_head report_rel pending_state output

    log "case: task-report-check-ignores-invalid-pending-artifact"

    redcap_runtime_clear_context
    repo="$ACCEPT_ROOT/task-report-invalid-pending-artifact/repo"
    create_task_report_fixture_repo "$repo"
    current_head="$(git -C "$repo" rev-parse HEAD)"
    report_rel="compass/docs/task-reports/zz-acceptance-valid-report-${RANDOM}-$$.md"
    printf '# 任务完成报告：acceptance\n\n## 零、先看懂当前局面\n\n### 0.1 当前已完成\n\n- 当前已完成：acceptance\n- 详情：acceptance\n\n### 0.2 上一步完成的是\n\n- 上一步完成的是：acceptance\n\n### 0.3 下一步计划做的是\n\n- 下一步计划做的是：无\n\n### 0.4 整体计划脉络图与当前位置\n\n- 整体计划脉络图是：acceptance\n- 当前所在位置：acceptance\n\n## 一、需求背景\n\n## 二、方案讨论\n\n## 三、落地结果\n\n### 3.2.1 术语对照（按文件/功能解释）\n\n## 四、人工审核要点\n\n## 五、验证结果\n\n## 六、遗留问题与下一步\n\n## 七、经验沉淀\n\n## 八、附录\n' >"$repo/$report_rel"
    pending_state="$(
        REDCAP_CONTINUITY_ROOT_DIR="$ACCEPT_ROOT/task-report-invalid-pending-artifact/core" \
            bash -lc 'set -euo pipefail; cd "'"$repo"'"; source compass/tools/redcap-interop-governance.sh; redcap_interop_write_pending_closure "'"$repo"'" "'"$repo"'/.dev-task.md" "'"$host"'" acceptance-seed task-report "missing task report under compass/docs/task-reports/" "'"$current_head"'" "'"$current_head"'"'
    )" || fail "failed to seed invalid pending artifact"
    assert_exists "$pending_state"

    output="$(bash "$repo/compass/tools/redcap-task-report-check.sh" "$repo" "$current_head" "$current_head" "$host")" \
        || fail "task-report-check should ignore invalid pending artifact"
    assert_eq "$output" "$report_rel"
}

run_task_report_check_ignores_traversal_anchor_case() {
    local host="copilot"
    local repo current_head report_rel traversal_rel output
    local binding_key pid confirmed_hash pending_state

    log "case: task-report-check-ignores-traversal-anchor"

    redcap_runtime_clear_context
    repo="$ACCEPT_ROOT/task-report-traversal-anchor/repo"
    create_task_report_fixture_repo "$repo"
    current_head="$(git -C "$repo" rev-parse HEAD)"
    report_rel="compass/docs/task-reports/zz-acceptance-valid-report-${RANDOM}-$$.md"
    printf '# 任务完成报告：acceptance\n\n## 零、先看懂当前局面\n\n### 0.1 当前已完成\n\n- 当前已完成：acceptance\n- 详情：acceptance\n\n### 0.2 上一步完成的是\n\n- 上一步完成的是：acceptance\n\n### 0.3 下一步计划做的是\n\n- 下一步计划做的是：无\n\n### 0.4 整体计划脉络图与当前位置\n\n- 整体计划脉络图是：acceptance\n- 当前所在位置：acceptance\n\n## 一、需求背景\n\n## 二、方案讨论\n\n## 三、落地结果\n\n### 3.2.1 术语对照（按文件/功能解释）\n\n## 四、人工审核要点\n\n## 五、验证结果\n\n## 六、遗留问题与下一步\n\n## 七、经验沉淀\n\n## 八、附录\n' >"$repo/$report_rel"
    binding_key="acceptance-task-report-traversal-${RANDOM}-$$"
    pid="$((66600 + RANDOM))"
    init_bound_runtime_for_repo "$host" "$repo" "$binding_key" "$pid"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$repo/.dev-task.md")"
    traversal_rel="compass/docs/task-reports/../../../references/task-report-template.md"
    write_current_report_marker_with_hash_fixture "$traversal_rel" "$confirmed_hash" "$repo/.dev-task.md"
    pending_state=$(redcap_interop_write_pending_closure \
        "$repo" \
        "$repo/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "task-report" \
        "traversal-anchor" \
        "$traversal_rel" \
        "$current_head" \
        "$current_head") || fail "failed to seed traversal pending artifact"
    assert_exists "$pending_state"

    output="$(bash "$repo/compass/tools/redcap-task-report-check.sh" "$repo" "$current_head" "$current_head" "$host")" \
        || fail "task-report-check should ignore traversal anchor"
    assert_eq "$output" "$report_rel"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_report_check_normalizes_absolute_pending_anchor_case() {
    local host="copilot"
    local repo current_head report_rel report_abs output
    local binding_key pid pending_state

    log "case: task-report-check-normalizes-absolute-pending-anchor"

    redcap_runtime_clear_context
    repo="$ACCEPT_ROOT/task-report-absolute-anchor/repo"
    create_task_report_fixture_repo "$repo"
    current_head="$(git -C "$repo" rev-parse HEAD)"
    report_rel="compass/docs/task-reports/zz-acceptance-absolute-anchor-${RANDOM}-$$.md"
    cp "$repo/references/task-report-template.md" "$repo/$report_rel"
    report_abs="$repo/$report_rel"
    binding_key="acceptance-task-report-absolute-anchor-${RANDOM}-$$"
    pid="$((66620 + RANDOM))"
    init_bound_runtime_for_repo "$host" "$repo" "$binding_key" "$pid"
    write_current_report_marker_fixture "$report_rel" "$repo/.dev-task.md"
    pending_state=$(redcap_interop_write_pending_closure \
        "$repo" \
        "$repo/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "task-report" \
        "absolute-anchor" \
        "$report_abs" \
        "$current_head" \
        "$current_head") || fail "failed to seed absolute pending anchor"
    assert_exists "$pending_state"

    output="$(bash "$repo/compass/tools/redcap-task-report-check.sh" "$repo" "$current_head" "$current_head" "$host")" \
        || fail "task-report-check should normalize absolute pending anchor"
    assert_eq "$output" "$report_rel"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_report_check_rejects_symlink_report_escape_case() {
    local host="copilot"
    local repo current_head report_rel output status

    log "case: task-report-check-rejects-symlink-report-escape"

    redcap_runtime_clear_context
    repo="$ACCEPT_ROOT/task-report-symlink-escape/repo"
    create_task_report_fixture_repo "$repo"
    current_head="$(git -C "$repo" rev-parse HEAD)"
    report_rel="compass/docs/task-reports/zz-acceptance-symlink-escape-${RANDOM}-$$.md"
    ln -s ../../../references/task-report-template.md "$repo/$report_rel"
    git -C "$repo" add "$report_rel"

    set +e
    output="$(bash "$repo/compass/tools/redcap-task-report-check.sh" "$repo" "$current_head" "$current_head" "$host" 2>&1)"
    status=$?
    set -e
    [[ "$status" -ne 0 ]] || fail "task-report-check unexpectedly accepted symlink report escape"
    assert_string_contains "$output" "changed report escapes task-reports root"
}

run_task_complete_guard_serializes_on_complete_case() {
    local host="copilot"
    local binding_key pid current_head report_path report_rel case_dir complete_log complete_stub task_complete_slice

    log "case: task-complete-guard-serializes-on-complete"

    redcap_runtime_clear_context
    binding_key="acceptance-task-complete-serialize-${RANDOM}-$$"
    pid="$((66430 + RANDOM))"
    init_bound_runtime "$host" "$binding_key" "$pid"
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for serialize case"
    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-task-complete-serialize-${RANDOM}-$$.md"
    report_rel="${report_path#$REDCAP_ROOT/}"
    printf '# acceptance serialize report\n' >"$report_path"
    LEGACY_TMP_FILES+=("$report_path")
    write_current_report_marker_fixture "$report_rel"
    task_complete_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/task-complete-serialize.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    complete_log="$case_dir/on-complete.log"
    complete_stub="$case_dir/on-complete-stub.sh"
    cat >"$complete_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "on-complete" >>"$complete_log"
sleep 1
EOF
    chmod +x "$complete_stub"

    REDCAP_TASK_COMPLETE_SLICE="$task_complete_slice" \
    REDCAP_ON_COMPLETE_SCRIPT="$complete_stub" \
    REDCAP_HOST_PROCESS_PID="$pid" \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-task-complete-guard.sh" "$host" >/dev/null &
    guard_a=$!
    REDCAP_TASK_COMPLETE_SLICE="$task_complete_slice" \
    REDCAP_ON_COMPLETE_SCRIPT="$complete_stub" \
    REDCAP_HOST_PROCESS_PID="$pid" \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-task-complete-guard.sh" "$host" >/dev/null &
    guard_b=$!
    wait "$guard_a"
    wait "$guard_b"

    assert_exists "$complete_log"
    assert_num_eq "$(wc -l < "$complete_log" | tr -d '[:space:]')" 1

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_complete_guard_prunes_stale_lock_case() {
    local host="copilot"
    local binding_key pid current_head report_path report_rel case_dir complete_log complete_stub task_complete_slice lock_path

    log "case: task-complete-guard-prunes-stale-lock"

    redcap_runtime_clear_context
    binding_key="acceptance-task-complete-stale-lock-${RANDOM}-$$"
    pid="$((66435 + RANDOM))"
    init_bound_runtime "$host" "$binding_key" "$pid"
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for stale lock case"
    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-task-complete-stale-lock-${RANDOM}-$$.md"
    report_rel="${report_path#$REDCAP_ROOT/}"
    printf '# acceptance stale lock report\n' >"$report_path"
    LEGACY_TMP_FILES+=("$report_path")
    write_current_report_marker_fixture "$report_rel"
    task_complete_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    lock_path="$(redcap_runtime_path "layerB/task-complete-guard.lock")"
    mkdir -p "$(dirname "$lock_path")"
    printf 'dead-pid\t1970-01-01T00:00:00Z\n' >"$lock_path"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/task-complete-stale-lock.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    complete_log="$case_dir/on-complete.log"
    complete_stub="$case_dir/on-complete-stub.sh"
    cat >"$complete_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "on-complete" >>"$complete_log"
EOF
    chmod +x "$complete_stub"

    REDCAP_TASK_COMPLETE_SLICE="$task_complete_slice" \
    REDCAP_ON_COMPLETE_SCRIPT="$complete_stub" \
    REDCAP_HOST_PROCESS_PID="$pid" \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-task-complete-guard.sh" "$host" >/dev/null \
        || fail "task complete guard stale lock case failed"

    assert_exists "$complete_log"
    assert_num_eq "$(wc -l < "$complete_log" | tr -d '[:space:]')" 1
    assert_not_exists "$lock_path"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_complete_guard_keeps_live_legacy_lock_case() {
    local host="copilot"
    local binding_key pid current_head report_path report_rel case_dir complete_log complete_stub task_complete_slice lock_path legacy_owner_pid legacy_created_at

    log "case: task-complete-guard-keeps-live-legacy-lock"

    redcap_runtime_clear_context
    binding_key="acceptance-task-complete-live-legacy-lock-${RANDOM}-$$"
    pid="$((66436 + RANDOM))"
    init_bound_runtime "$host" "$binding_key" "$pid"
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for live legacy lock case"
    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-task-complete-live-legacy-${RANDOM}-$$.md"
    report_rel="${report_path#$REDCAP_ROOT/}"
    printf '# acceptance live legacy lock report\n' >"$report_path"
    LEGACY_TMP_FILES+=("$report_path")
    write_current_report_marker_fixture "$report_rel"
    task_complete_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    lock_path="$(redcap_runtime_path "layerB/task-complete-guard.lock")"
    mkdir -p "$(dirname "$lock_path")"
    spawn_host_probe legacy_owner_pid
    legacy_created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf '%s\t%s\n' "$legacy_owner_pid" "$legacy_created_at" >"$lock_path"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/task-complete-live-legacy-lock.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    complete_log="$case_dir/on-complete.log"
    complete_stub="$case_dir/on-complete-stub.sh"
    cat >"$complete_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "on-complete" >>"$complete_log"
EOF
    chmod +x "$complete_stub"

    REDCAP_TASK_COMPLETE_SLICE="$task_complete_slice" \
    REDCAP_ON_COMPLETE_SCRIPT="$complete_stub" \
    REDCAP_HOST_PROCESS_PID="$pid" \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-task-complete-guard.sh" "$host" >/dev/null \
        || fail "task complete guard live legacy lock case failed"

    assert_not_exists "$complete_log"
    assert_exists "$lock_path"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_task_complete_guard_retries_after_report_change_case() {
    local host="copilot"
    local binding_key pid current_head report_path report_rel case_dir complete_log complete_stub task_complete_slice status_path

    log "case: task-complete-guard-retries-after-report-change"

    redcap_runtime_clear_context
    binding_key="acceptance-task-complete-retry-${RANDOM}-$$"
    pid="$((66440 + RANDOM))"
    init_bound_runtime "$host" "$binding_key" "$pid"
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for retry case"
    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-task-complete-retry-${RANDOM}-$$.md"
    report_rel="${report_path#$REDCAP_ROOT/}"
    printf '# acceptance retry report\n' >"$report_path"
    LEGACY_TMP_FILES+=("$report_path")
    write_current_report_marker_fixture "$report_rel"
    task_complete_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/task-complete-retry.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    complete_log="$case_dir/on-complete.log"
    complete_stub="$case_dir/on-complete-stub.sh"
    cat >"$complete_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "on-complete" >>"$complete_log"
exit 1
EOF
    chmod +x "$complete_stub"

    REDCAP_TASK_COMPLETE_SLICE="$task_complete_slice" \
    REDCAP_ON_COMPLETE_SCRIPT="$complete_stub" \
    REDCAP_HOST_PROCESS_PID="$pid" \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-task-complete-guard.sh" "$host" >/dev/null \
        || fail "task complete guard retry case first run failed"

    assert_num_eq "$(wc -l < "$complete_log" | tr -d '[:space:]')" 1
    status_path="$(redcap_runtime_path "layerB/task-complete-guard/last-status")"
    assert_exists "$status_path"
    assert_eq "$(read_file_text "$status_path")" "retry-needed"

    printf '\nmore content\n' >>"$report_path"

    REDCAP_TASK_COMPLETE_SLICE="$task_complete_slice" \
    REDCAP_ON_COMPLETE_SCRIPT="$complete_stub" \
    REDCAP_HOST_PROCESS_PID="$pid" \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-task-complete-guard.sh" "$host" >/dev/null \
        || fail "task complete guard retry case second run failed"

    assert_num_eq "$(wc -l < "$complete_log" | tr -d '[:space:]')" 2

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_on_stop_review_copilot_fallback_case() {
    local case_name="$1"
    local gemini_mode="$2"
    local case_dir fake_bin head_file review_result review_log baseline output status child_pid_file child_pid attempt copilot_guard_flag

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    case "$gemini_mode" in
        timeout)
            child_pid_file="$case_dir/gemini-child.pid"
            cat >"$fake_bin/gemini" <<EOF
#!/usr/bin/env bash
(sleep 30) &
printf '%s\n' "\$!" > "$child_pid_file"
sleep 30
EOF
            ;;
        auth-failure)
            cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
echo "Authorization failed, please check your login status"
exit 1
EOF
            ;;
        auth-failure-with-result-token)
            cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
Authorization failed, please check your login status
result: PASS
OUT
exit 1
EOF
            ;;
        unparseable-success-output)
            cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
echo "review completed without structured result"
EOF
            ;;
        structured-pass-with-auth-error-line)
            cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
```json
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"ok"}
```
Authorization failed, please check your login status
OUT
EOF
            ;;
        *)
            fail "unsupported gemini fallback mode: $gemini_mode"
            ;;
    esac
    chmod +x "$fake_bin/gemini"

    copilot_guard_flag="$case_dir/copilot-guard-flag.txt"
    cat >"$fake_bin/copilot" <<'EOF'
#!/usr/bin/env bash
: "${REDCAP_FAKE_COPILOT_GUARD_FLAG:?}"
printf '%s\n' "${REDCAP_SUPPRESS_TASK_COMPLETE_GUARD:-}" >"$REDCAP_FAKE_COPILOT_GUARD_FLAG"
cat <<'OUT'
```json
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"copilot fallback ok"}
```
OUT
EOF
    chmod +x "$fake_bin/copilot"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_FAKE_COPILOT_GUARD_FLAG="$copilot_guard_flag" \
            REDCAP_RUNTIME_SESSION_ID="" \
            REDCAP_RUNTIME_CAPABILITY="" \
            REDCAP_RUNTIME_SESSION_DIR="" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="gemini,copilot" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=5 \
            REDCAP_REVIEW_REQUIRE_REPO_INSPECTION_THRESHOLD=9999999 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    if [[ "$status" -ne 0 ]]; then
        fail "on-stop-review fallback case failed: status=$status output=$output result=$(counter_value "$review_result") log=$(counter_value "$review_log")"
    fi
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "PASS"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "**评审 Agent**: copilot"
    assert_string_contains "$(read_file_text "$review_log")" "copilot fallback ok"
    assert_exists "$copilot_guard_flag"
    assert_eq "$(read_file_text "$copilot_guard_flag")" "1"

    if [[ -n "${child_pid_file:-}" ]]; then
        assert_exists "$child_pid_file"
        child_pid="$(read_file_text "$child_pid_file")"
        for attempt in {1..20}; do
            if ! kill -0 "$child_pid" 2>/dev/null; then
                break
            fi
            sleep 0.1
        done
        if kill -0 "$child_pid" 2>/dev/null; then
            kill "$child_pid" 2>/dev/null || true
            fail "timed-out reviewer descendant process still alive: $child_pid"
        fi
    fi
}

run_on_stop_review_falls_back_after_timeout_case() {
    run_on_stop_review_copilot_fallback_case "on-stop-review-falls-back-after-timeout" "timeout"
}

run_on_stop_review_falls_back_after_auth_failure_case() {
    run_on_stop_review_copilot_fallback_case "on-stop-review-falls-back-after-auth-failure" "auth-failure"
}

run_on_stop_review_falls_back_after_auth_failure_with_result_token_case() {
    run_on_stop_review_copilot_fallback_case "on-stop-review-falls-back-after-auth-failure-with-result-token" "auth-failure-with-result-token"
}

run_on_stop_review_falls_back_after_unparseable_success_output_case() {
    run_on_stop_review_copilot_fallback_case "on-stop-review-falls-back-after-unparseable-success-output" "unparseable-success-output"
}

run_on_stop_review_falls_back_after_structured_pass_with_auth_error_line_case() {
    run_on_stop_review_copilot_fallback_case "on-stop-review-falls-back-after-structured-pass-with-auth-error-line" "structured-pass-with-auth-error-line"
}

run_on_stop_review_falls_back_to_codex_after_unavailable_reviewers_case() {
    local case_name="on-stop-review-falls-back-to-codex-after-unavailable-reviewers"
    local case_dir fake_bin head_file review_result review_log baseline output status codex_argv codex_stdin fake_task

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' 'Rate limit exceeded.' >&2
exit 1
EOF
    chmod +x "$fake_bin/gemini"

    codex_argv="$case_dir/codex-argv.txt"
    codex_stdin="$case_dir/codex-stdin.txt"
    cat >"$fake_bin/codex" <<'EOF'
#!/usr/bin/env bash
: "${REDCAP_FAKE_CODEX_ARGV:?}"
: "${REDCAP_FAKE_CODEX_STDIN:?}"
message_file=""
stdin_requested=""
printf '%s\n' "$@" >"$REDCAP_FAKE_CODEX_ARGV"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-last-message)
            message_file="$2"
            shift 2
            ;;
        -)
            stdin_requested=1
            shift
            ;;
        *)
            shift
            ;;
    esac
done
cat >"$REDCAP_FAKE_CODEX_STDIN"

if [[ -z "$stdin_requested" ]]; then
    printf '%s\n' 'codex prompt was not requested via stdin' >&2
    exit 2
fi
if ! grep -q '你是一位独立的代码架构评审员' "$REDCAP_FAKE_CODEX_STDIN"; then
    printf '%s\n' 'codex stdin did not contain the review prompt' >&2
    exit 2
fi

printf '%s\n' 'Codex CLI banner that must not become the review payload.'
printf '%s\n' 'Reading additional input from stdin...' >&2
printf '%s\n' 'WARN codex plugin prewarm failed; continuing.' >&2

if [[ -n "$message_file" ]]; then
    cat >"$message_file" <<'OUT'
```json
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"codex fallback ok"}
```
OUT
else
    cat <<'OUT'
```json
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"codex fallback ok"}
```
OUT
fi
EOF
    chmod +x "$fake_bin/codex"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    fake_task="$case_dir/.dev-task.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"
    cat >"$fake_task" <<'EOF'
# 当前任务：stop-review acceptance fixture

## 控制面元数据（机器校验）
task_id: stop-review-acceptance
source_of_truth: .dev-task.md
top_goal: 隔离验证 stop-review 行为，不让真实仓库当前任务账面干扰 acceptance。
active_slice: stop-review-acceptance-fixture
subtask_of: stop-review-acceptance
host_surface_policy: mirror_only
delegation_boundary: redcap-native-first
human_escalation_policy: ai-uncomputable-only
overlay_skill_policy: advisory_only
task_report: compass/docs/task-reports/2026-04-21-reviewer-routing-rebalance-and-ledger-fix.md

## 原始输入（用户原文，禁止改写）
### Q1
验证 stop-review fallback。

## 已确认需求（执行依据）
### Q1: stop-review acceptance fixture
验证 stop-review 在受控 fake CLI 环境下的行为。
> 执行摘要：仅用于 acceptance。

## 漂移哨兵
- 本文件只用于 acceptance。

## 允许修改范围
- *

## 完成标准
- [ ] acceptance fixture

## 断点备注
- none
EOF

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_TASK_FILE="$fake_task" \
            REDCAP_FAKE_CODEX_ARGV="$codex_argv" \
            REDCAP_FAKE_CODEX_STDIN="$codex_stdin" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_VALIDATOR_HOST="acceptance-fixture" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="gemini,codex" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=10 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -eq 0 ]] || fail "codex fallback case failed: $output"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "PASS"
    assert_exists "$codex_argv"
    assert_exists "$codex_stdin"
    assert_string_contains "$(read_file_text "$codex_argv")" "-"
    assert_string_contains "$(read_file_text "$codex_stdin")" "你是一位独立的代码架构评审员"
    assert_string_contains "$(read_file_text "$codex_stdin")" "repo-inspection"
    assert_string_contains "$(read_file_text "$codex_stdin")" "你必须直接检查仓库中的完整证据"
    [[ "$(read_file_text "$codex_stdin")" != *"Diff 截断"* ]] || fail "codex prompt still contains diff truncation marker"
    [[ "$(read_file_text "$codex_stdin")" != *"CONTRIBUTING 精选章节截断"* ]] || fail "codex prompt still contains guidance truncation marker"
    if [[ "$(read_file_text "$codex_argv")" == *"你是一位独立的代码架构评审员"* ]]; then
        fail "codex review prompt leaked into argv"
    fi
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "**评审 Agent**: codex"
    assert_string_contains "$(read_file_text "$review_log")" "codex fallback ok"
    if [[ "$(read_file_text "$review_log")" == *"Codex CLI banner that must not become the review payload."* ]]; then
        fail "codex fallback leaked stdout banner into review payload"
    fi
}

run_on_stop_review_prefers_codex_when_best_ranked_case() {
    local case_name="on-stop-review-prefers-codex-when-best-ranked"
    local case_dir fake_bin head_file review_result review_log baseline output status fake_registry fake_task
    local gemini_marker kimi_marker codex_argv codex_stdin

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    gemini_marker="$case_dir/gemini-called.txt"
    cat >"$fake_bin/gemini" <<EOF
#!/usr/bin/env bash
printf '%s\n' called > "$gemini_marker"
exit 97
EOF
    chmod +x "$fake_bin/gemini"

    kimi_marker="$case_dir/kimi-called.txt"
    cat >"$fake_bin/kimi" <<EOF
#!/usr/bin/env bash
printf '%s\n' called > "$kimi_marker"
exit 98
EOF
    chmod +x "$fake_bin/kimi"

    codex_argv="$case_dir/codex-argv.txt"
    codex_stdin="$case_dir/codex-stdin.txt"
    cat >"$fake_bin/codex" <<'EOF'
#!/usr/bin/env bash
: "${REDCAP_FAKE_CODEX_ARGV:?}"
: "${REDCAP_FAKE_CODEX_STDIN:?}"
message_file=""
stdin_requested=""
printf '%s\n' "$@" >"$REDCAP_FAKE_CODEX_ARGV"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-last-message)
            message_file="$2"
            shift 2
            ;;
        -)
            stdin_requested=1
            shift
            ;;
        *)
            shift
            ;;
    esac
done
cat >"$REDCAP_FAKE_CODEX_STDIN"

if [[ -z "$stdin_requested" ]]; then
    printf '%s\n' 'codex prompt was not requested via stdin' >&2
    exit 2
fi

cat >"$message_file" <<'OUT'
```json
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"codex preferred ok"}
```
OUT
EOF
    chmod +x "$fake_bin/codex"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    fake_registry="$case_dir/agent-registry.yaml"
    fake_task="$case_dir/.dev-task.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"
    cat >"$fake_task" <<'EOF'
# 当前任务：stop-review acceptance fixture

## 控制面元数据（机器校验）
task_id: stop-review-acceptance
source_of_truth: .dev-task.md
top_goal: 隔离验证 stop-review 动态 reviewer 排序。
active_slice: stop-review-acceptance-fixture
subtask_of: stop-review-acceptance
host_surface_policy: mirror_only
delegation_boundary: redcap-native-first
human_escalation_policy: ai-uncomputable-only
overlay_skill_policy: advisory_only
task_report: compass/docs/task-reports/2026-04-21-reviewer-routing-rebalance-and-ledger-fix.md

## 原始输入（用户原文，禁止改写）
### Q1
验证 stop-review 动态排序。

## 已确认需求（执行依据）
### Q1: stop-review acceptance fixture
验证 stop-review 在受控 fake CLI 环境下的 reviewer 排序。
> 执行摘要：仅用于 acceptance。

## 漂移哨兵
- 本文件只用于 acceptance。

## 允许修改范围
- *

## 完成标准
- [ ] acceptance fixture

## 断点备注
- none
EOF
    cat >"$fake_registry" <<'EOF'
detected_at: "2026-04-21T02:00:00Z"
probe_mode: false
agents:
  gemini:
    available: true
    actual_model: "gemini-3-flash"
    supports_model_switch: true
    model_switch_flag: "--model"
    known_issues:
      - "L-7: headless 必须 --yolo"
  kimi:
    available: true
    actual_model: "kimi-for-coding"
    supports_model_switch: false
  codex:
    available: true
    actual_model: "gpt-5.4"
    supports_model_switch: true
    model_switch_flag: "--model"
EOF

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_TASK_FILE="$fake_task" \
            REDCAP_FAKE_CODEX_ARGV="$codex_argv" \
            REDCAP_FAKE_CODEX_STDIN="$codex_stdin" \
            REDCAP_REVIEW_AGENT_REGISTRY_FILE="$fake_registry" \
            REDCAP_STOP_REVIEW_HOST="claude" \
            REDCAP_STOP_REVIEW_VALIDATOR_HOST="acceptance-fixture" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=10 \
            REDCAP_REVIEW_REQUIRE_REPO_INSPECTION_THRESHOLD=9999999 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -eq 0 ]] || fail "codex best-ranked case failed: $output"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "PASS"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "**评审 Agent**: codex@gpt-5.4"
    assert_string_contains "$(read_file_text "$review_log")" "codex preferred ok"
    assert_exists "$codex_argv"
    assert_exists "$codex_stdin"
    assert_not_exists "$gemini_marker"
    assert_not_exists "$kimi_marker"
}

run_on_stop_review_prefers_copilot_premium_model_over_lighter_clis_case() {
    local case_name="on-stop-review-prefers-copilot-premium-model-over-lighter-clis"
    local case_dir fake_bin head_file review_result review_log baseline output status fake_registry fake_task
    local gemini_marker kimi_marker copilot_argv

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    gemini_marker="$case_dir/gemini-called.txt"
    cat >"$fake_bin/gemini" <<EOF
#!/usr/bin/env bash
printf '%s\n' called > "$gemini_marker"
exit 97
EOF
    chmod +x "$fake_bin/gemini"

    kimi_marker="$case_dir/kimi-called.txt"
    cat >"$fake_bin/kimi" <<EOF
#!/usr/bin/env bash
printf '%s\n' called > "$kimi_marker"
exit 98
EOF
    chmod +x "$fake_bin/kimi"

    copilot_argv="$case_dir/copilot-argv.txt"
    cat >"$fake_bin/copilot" <<'EOF'
#!/usr/bin/env bash
: "${REDCAP_FAKE_COPILOT_ARGV:?}"
printf '%s\n' "$@" >"$REDCAP_FAKE_COPILOT_ARGV"
cat <<'OUT'
```json
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"copilot preferred ok"}
```
OUT
EOF
    chmod +x "$fake_bin/copilot"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    fake_registry="$case_dir/agent-registry.yaml"
    fake_task="$case_dir/.dev-task.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"
    cat >"$fake_task" <<'EOF'
# 当前任务：stop-review acceptance fixture

## 控制面元数据（机器校验）
task_id: stop-review-acceptance
source_of_truth: .dev-task.md
top_goal: 隔离验证 stop-review 动态 reviewer 排序。
active_slice: stop-review-acceptance-fixture
subtask_of: stop-review-acceptance
host_surface_policy: mirror_only
delegation_boundary: redcap-native-first
human_escalation_policy: ai-uncomputable-only
overlay_skill_policy: advisory_only
task_report: compass/docs/task-reports/2026-04-21-reviewer-routing-rebalance-and-ledger-fix.md

## 原始输入（用户原文，禁止改写）
### Q1
验证 stop-review 动态排序。

## 已确认需求（执行依据）
### Q1: stop-review acceptance fixture
验证 stop-review 在受控 fake CLI 环境下的 reviewer 排序。
> 执行摘要：仅用于 acceptance。

## 漂移哨兵
- 本文件只用于 acceptance。

## 允许修改范围
- *

## 完成标准
- [ ] acceptance fixture

## 断点备注
- none
EOF
    cat >"$fake_registry" <<'EOF'
detected_at: "2026-04-21T02:00:00Z"
probe_mode: false
agents:
  gemini:
    available: true
    actual_model: "gemini-3-flash"
    supports_model_switch: true
    model_switch_flag: "--model"
    known_issues:
      - "L-7: headless 必须 --yolo"
  kimi:
    available: true
    actual_model: "kimi-for-coding"
    supports_model_switch: false
  copilot:
    available: true
    actual_model: "claude-opus-4.6"
    supports_model_switch: true
    model_switch_flag: "--model"
    switchable_models:
      - "claude-opus-4.6"
EOF

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_FAKE_COPILOT_ARGV="$copilot_argv" \
            REDCAP_TASK_FILE="$fake_task" \
            REDCAP_REVIEW_AGENT_REGISTRY_FILE="$fake_registry" \
            REDCAP_STOP_REVIEW_HOST="claude" \
            REDCAP_STOP_REVIEW_VALIDATOR_HOST="acceptance-fixture" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=10 \
            REDCAP_REVIEW_REQUIRE_REPO_INSPECTION_THRESHOLD=9999999 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -eq 0 ]] || fail "copilot premium ranking case failed: $output"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "PASS"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "**评审 Agent**: copilot@claude-opus-4.6"
    assert_string_contains "$(read_file_text "$review_log")" "copilot preferred ok"
    assert_exists "$copilot_argv"
    assert_string_contains "$(read_file_text "$copilot_argv")" "--model"
    assert_string_contains "$(read_file_text "$copilot_argv")" "claude-opus-4.6"
    assert_not_exists "$gemini_marker"
    assert_not_exists "$kimi_marker"
}

run_on_stop_review_records_unavailable_rate_limit_case() {
    local case_name="on-stop-review-records-unavailable-rate-limit"
    local case_dir fake_bin head_file review_result review_log baseline output status

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    cat >"$fake_bin/copilot" <<'EOF'
#!/usr/bin/env bash
cat >&2 <<'OUT'
Sorry, you've hit a rate limit that restricts the number of Copilot model requests you can make within a specific time period. Please try again in 44 hours.
OUT
exit 1
EOF
    chmod +x "$fake_bin/copilot"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="copilot" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=10 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -ne 0 ]] || fail "unavailable rate-limit case unexpectedly passed"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "FAIL"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "独立评审不可用"
    assert_string_contains "$(read_file_text "$review_log")" "copilot:rate-limited"
    assert_string_contains "$(read_file_text "$review_log")" '`review` 红线 pending'
    assert_string_contains "$output" "copilot:rate-limited"
    [[ "$output" != *"command not found"* ]] || fail "unavailable rate-limit case leaked shell expansion error: $output"
}

run_on_stop_review_rejects_invalid_track_structure_case() {
    local case_name="on-stop-review-rejects-invalid-track-structure"
    local case_dir fake_bin head_file review_result review_log baseline output status

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
```json
{"result":"PASS","issues":[],"summary":"legacy schema must be rejected"}
```
OUT
EOF
    chmod +x "$fake_bin/gemini"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="gemini" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=1 \
            REDCAP_REVIEW_REQUIRE_REPO_INSPECTION_THRESHOLD=9999999 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -ne 0 ]] || fail "invalid track structure case unexpectedly passed"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "FAIL"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "独立评审不可用"
    assert_string_contains "$(read_file_text "$review_log")" "gemini:invalid-track-structure"
    assert_string_contains "$output" "gemini:invalid-track-structure"
}

run_on_stop_review_skips_prompt_only_reviewer_when_repo_inspection_required_case() {
    local case_name="on-stop-review-skips-prompt-only-reviewer-when-repo-inspection-required"
    local case_dir fake_bin head_file review_result review_log baseline output status

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' 'gemini should not be invoked for oversized repo-inspection review' >&2
exit 99
EOF
    chmod +x "$fake_bin/gemini"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    baseline="7cb8cca0d66f1ebfc95d115be5c71ec1ac9f17e3"
    printf '%s\n' "$baseline" >"$head_file"

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="gemini" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=5 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -ne 0 ]] || fail "prompt-only oversized review case unexpectedly passed"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "FAIL"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "gemini:insufficient-evidence"
    assert_string_contains "$output" "gemini:insufficient-evidence"
    [[ "$output" != *"gemini should not be invoked"* ]] || fail "prompt-only reviewer was invoked despite insufficient evidence gate"
}

run_on_stop_review_accepts_structured_review_with_auth_terms_case() {
    local case_name="on-stop-review-accepts-structured-review-with-auth-terms"
    local case_dir fake_bin head_file review_result review_log baseline output status

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
```json
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"unauthorized path is covered and remains fail-closed"}
```
OUT
EOF
    chmod +x "$fake_bin/gemini"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="gemini" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=5 \
            REDCAP_REVIEW_REQUIRE_REPO_INSPECTION_THRESHOLD=9999999 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -eq 0 ]] || fail "structured auth-term review case failed: $output"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "PASS"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "**评审 Agent**: gemini"
    assert_string_contains "$(read_file_text "$review_log")" "unauthorized path is covered"
}

run_on_stop_review_accepts_structured_review_with_auth_prose_outside_fence_case() {
    local case_name="on-stop-review-accepts-structured-review-with-auth-prose-outside-fence"
    local case_dir fake_bin head_file review_result review_log baseline output status

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
The authentication failed path remains fail-closed.
```json
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"ok"}
```
OUT
EOF
    chmod +x "$fake_bin/gemini"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="gemini" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=5 \
            REDCAP_REVIEW_REQUIRE_REPO_INSPECTION_THRESHOLD=9999999 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -eq 0 ]] || fail "structured auth prose outside fence case failed: $output"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "PASS"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "**评审 Agent**: gemini"
    assert_string_contains "$(read_file_text "$review_log")" "The authentication failed path remains fail-closed."
}

run_on_stop_review_accepts_structured_review_with_quoted_cli_error_in_stdout_prose_case() {
    local case_name="on-stop-review-accepts-structured-review-with-quoted-cli-error-in-stdout-prose"
    local case_dir fake_bin head_file review_result review_log baseline output status

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
Observed failing path:
Authorization failed, please check your login status
```json
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"ok"}
```
OUT
EOF
    chmod +x "$fake_bin/gemini"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="gemini" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=5 \
            REDCAP_REVIEW_REQUIRE_REPO_INSPECTION_THRESHOLD=9999999 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -eq 0 ]] || fail "quoted cli error in stdout prose case failed: $output"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "PASS"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "**评审 Agent**: gemini"
    assert_string_contains "$(read_file_text "$review_log")" "{\"result\":\"PASS\""
}

run_on_stop_review_accepts_structured_review_with_quoted_cli_error_block_in_stdout_residual_case() {
    local case_name="on-stop-review-accepts-structured-review-with-quoted-cli-error-block-in-stdout-residual"
    local case_dir fake_bin head_file review_result review_log baseline output status

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
```json
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"ok"}
```
Authorization failed, please check your login status
Hint: run login again
OUT
EOF
    chmod +x "$fake_bin/gemini"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="gemini" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=5 \
            REDCAP_REVIEW_REQUIRE_REPO_INSPECTION_THRESHOLD=9999999 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -eq 0 ]] || fail "quoted cli error block in stdout residual case failed: $output"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "PASS"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "**评审 Agent**: gemini"
    assert_string_contains "$(read_file_text "$review_log")" "{\"result\":\"PASS\""
}

run_on_stop_review_accepts_lowercase_structured_result_case() {
    local case_name="on-stop-review-accepts-lowercase-structured-result"
    local case_dir fake_bin head_file review_result review_log baseline output status

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
```json
{"result":"pass","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"ok"}
```
OUT
EOF
    chmod +x "$fake_bin/gemini"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="gemini" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=5 \
            REDCAP_REVIEW_REQUIRE_REPO_INSPECTION_THRESHOLD=9999999 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -eq 0 ]] || fail "lowercase structured review case failed: $output"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "PASS"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "**评审 Agent**: gemini"
    assert_string_contains "$(read_file_text "$review_log")" "\"result\":\"pass\""
}

run_on_stop_review_accepts_raw_json_with_stderr_auth_terms_case() {
    local case_name="on-stop-review-accepts-raw-json-with-stderr-auth-terms"
    local case_dir fake_bin head_file review_result review_log baseline output status

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' '{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"ok"}'
printf '%s\n' 'unauthorized path remains fail-closed' >&2
EOF
    chmod +x "$fake_bin/gemini"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="gemini" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=5 \
            REDCAP_REVIEW_REQUIRE_REPO_INSPECTION_THRESHOLD=9999999 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -eq 0 ]] || fail "raw json with stderr auth terms case failed: $output"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "PASS"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "**评审 Agent**: gemini"
    assert_string_contains "$(read_file_text "$review_log")" "{\"result\":\"PASS\""
}

run_on_stop_review_falls_back_after_structured_pass_with_stderr_auth_error_line_case() {
    local case_name="on-stop-review-falls-back-after-structured-pass-with-stderr-auth-error-line"
    local case_dir fake_bin head_file review_result review_log baseline output status

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
```json
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"ok"}
```
OUT
printf '%s\n' 'Authorization failed, please check your login status' >&2
EOF
    chmod +x "$fake_bin/gemini"

    cat >"$fake_bin/copilot" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
```json
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"copilot fallback ok"}
```
OUT
EOF
    chmod +x "$fake_bin/copilot"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="gemini,copilot" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=5 \
            REDCAP_REVIEW_REQUIRE_REPO_INSPECTION_THRESHOLD=9999999 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -eq 0 ]] || fail "structured pass with stderr auth error line case failed: $output"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "PASS"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "**评审 Agent**: copilot"
    assert_string_contains "$(read_file_text "$review_log")" "copilot fallback ok"
}

run_on_stop_review_falls_back_after_structured_pass_with_stderr_auth_error_and_hint_case() {
    local case_name="on-stop-review-falls-back-after-structured-pass-with-stderr-auth-error-and-hint"
    local case_dir fake_bin head_file review_result review_log baseline output status

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
```json
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"ok"}
```
OUT
cat >&2 <<'ERR'
Authorization failed, please check your login status
Hint: run login again
ERR
EOF
    chmod +x "$fake_bin/gemini"

    cat >"$fake_bin/copilot" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
```json
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"copilot fallback ok"}
```
OUT
EOF
    chmod +x "$fake_bin/copilot"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="gemini,copilot" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=5 \
            REDCAP_REVIEW_REQUIRE_REPO_INSPECTION_THRESHOLD=9999999 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -eq 0 ]] || fail "structured pass with stderr auth error and hint case failed: $output"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "PASS"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "**评审 Agent**: copilot"
    assert_string_contains "$(read_file_text "$review_log")" "copilot fallback ok"
}

run_on_stop_review_accepts_structured_review_with_quoted_cli_error_in_stderr_prose_case() {
    local case_name="on-stop-review-accepts-structured-review-with-quoted-cli-error-in-stderr-prose"
    local case_dir fake_bin head_file review_result review_log baseline output status

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
```json
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"ok"}
```
OUT
cat >&2 <<'ERR'
Observed failing path:
Authorization failed, please check your login status
ERR
EOF
    chmod +x "$fake_bin/gemini"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="gemini" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=5 \
            REDCAP_REVIEW_REQUIRE_REPO_INSPECTION_THRESHOLD=9999999 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -eq 0 ]] || fail "quoted cli error in stderr prose case failed: $output"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "PASS"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "**评审 Agent**: gemini"
    assert_string_contains "$(read_file_text "$review_log")" "{\"result\":\"PASS\""
}

run_on_stop_review_accepts_plain_text_pass_with_fail_closed_case() {
    local case_name="on-stop-review-accepts-plain-text-pass-with-fail-closed"
    local case_dir fake_bin head_file review_result review_log baseline output status

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
PASS
The failure path remains fail-closed.
OUT
EOF
    chmod +x "$fake_bin/gemini"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="gemini" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=5 \
            REDCAP_REVIEW_REQUIRE_REPO_INSPECTION_THRESHOLD=9999999 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -eq 0 ]] || fail "plain text pass with fail-closed case failed: $output"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "PASS"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "**评审 Agent**: gemini"
    assert_string_contains "$(read_file_text "$review_log")" "The failure path remains fail-closed."
}

run_on_stop_review_accepts_uppercase_fenced_json_case() {
    local case_name="on-stop-review-accepts-uppercase-fenced-json"
    local case_dir fake_bin head_file review_result review_log baseline output status

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
```JSON
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"ok"}
```
OUT
EOF
    chmod +x "$fake_bin/gemini"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="gemini" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=5 \
            REDCAP_REVIEW_REQUIRE_REPO_INSPECTION_THRESHOLD=9999999 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -eq 0 ]] || fail "uppercase fenced json case failed: $output"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "PASS"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "**评审 Agent**: gemini"
    assert_string_contains "$(read_file_text "$review_log")" '```JSON'
}

run_on_stop_review_accepts_bare_fenced_json_case() {
    local case_name="on-stop-review-accepts-bare-fenced-json"
    local case_dir fake_bin head_file review_result review_log baseline output status

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
```
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"ok"}
```
OUT
EOF
    chmod +x "$fake_bin/gemini"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="gemini" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=5 \
            REDCAP_REVIEW_REQUIRE_REPO_INSPECTION_THRESHOLD=9999999 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -eq 0 ]] || fail "bare fenced json case failed: $output"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "PASS"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "**评审 Agent**: gemini"
    assert_string_contains "$(read_file_text "$review_log")" '```'
}

run_on_stop_review_accepts_json_fence_after_nonjson_bare_fence_case() {
    local case_name="on-stop-review-accepts-json-fence-after-nonjson-bare-fence"
    local case_dir fake_bin head_file review_result review_log baseline output status

    log "case: $case_name"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/$case_name.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    fake_bin="$case_dir/bin"
    mkdir -p "$fake_bin"

    cat >"$fake_bin/gemini" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
这里先给一个示例：
```
Authorization failed, please check your login status
```

```json
{"result":"PASS","track_verdicts":{"architecture":"PASS","governance":"PASS","contracts":"PASS"},"issues":[],"summary":"ok"}
```
OUT
EOF
    chmod +x "$fake_bin/gemini"

    head_file="$case_dir/baseline.head"
    review_result="$case_dir/review-result"
    review_log="$case_dir/review-log.md"
    baseline="$(git -C "$REDCAP_ROOT" rev-parse HEAD~1)"
    printf '%s\n' "$baseline" >"$head_file"

    set +e
    output="$(
        printf '{}' | \
            PATH="$fake_bin:/usr/bin:/bin" \
            REDCAP_STOP_REVIEW_HOST="copilot" \
            REDCAP_STOP_REVIEW_AGENT_ORDER="gemini" \
            REDCAP_BASELINE_HEAD_FILE="$head_file" \
            REDCAP_REVIEW_RESULT_FILE="$review_result" \
            REDCAP_REVIEW_LOG_FILE="$review_log" \
            REDCAP_REVIEW_AGENT_TIMEOUT_SEC=5 \
            REDCAP_REVIEW_REQUIRE_REPO_INSPECTION_THRESHOLD=9999999 \
            REDCAP_SKIP_FEISHU=1 \
            bash "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" 2>&1
    )"
    status=$?
    set -e

    [[ "$status" -eq 0 ]] || fail "json fence after nonjson bare fence case failed: $output"
    assert_exists "$review_result"
    assert_eq "$(read_file_text "$review_result")" "PASS"
    assert_exists "$review_log"
    assert_string_contains "$(read_file_text "$review_log")" "**评审 Agent**: gemini"
    assert_string_contains "$(read_file_text "$review_log")" "Authorization failed, please check your login status"
    assert_string_contains "$(read_file_text "$review_log")" '```json'
}

run_session_end_success_notify_after_clear_case() {
    local host="copilot"
    local binding_key pid probe_pid current_head report_path case_dir validator_stub notifier_stub notify_log pending_state

    log "case: session-end-success-notify-after-clear"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "session-end-success-notify-after-clear" >/dev/null 2>&1 || true

    binding_key="acceptance-session-end-notify-order-${RANDOM}-$$"
    pid="$((66450 + RANDOM))"
    spawn_host_probe probe_pid
    export REDCAP_HOST_PROCESS_PID="$pid"
    export REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid"
    redcap_runtime_init_from_binding "$host" "$REDCAP_ROOT" "$binding_key" >/dev/null \
        || fail "failed to initialize runtime binding for notify order case"
    REDCAP_SESSION_ISOLATION_MODE="full"
    export REDCAP_HOST_PROCESS_PID REDCAP_SESSION_ISOLATION_MODE REDCAP_RUNTIME_SESSION_ID REDCAP_RUNTIME_BINDING_KEY REDCAP_RUNTIME_HOST REDCAP_RUNTIME_CAPABILITY
    unset REDCAP_HOST_PROCESS_PROBE_PID
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    report_path="compass/docs/task-reports/2026-04-16-completion-hook-hardening.md"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for notify order case"
    write_current_report_marker_fixture "$report_path"
    pending_state="$(
        redcap_interop_write_pending_closure \
            "$REDCAP_ROOT" \
            "$REDCAP_ROOT/.dev-task.md" \
            "$host" \
            "acceptance-seed" \
            "review,notify" \
            "session-end-success-notify-after-clear" \
            "$report_path" \
            "$current_head" \
            "$current_head"
    )" || fail "failed to seed pending closure for notify order case"
    assert_exists "$pending_state"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/session-end-notify-order.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    validator_stub="$case_dir/validator-pass.sh"
    notifier_stub="$case_dir/notifier.py"
    notify_log="$case_dir/notify.log"
    cat >"$validator_stub" <<EOF
#!/usr/bin/env bash
cat <<'OUT'
[1] review-proof-check :: pass
review clean
[2] reanchor-check :: pass
reanchor clean
[3] pm-gate :: pass
pm gate clean
[4] drift-check :: pass
drift clean
[5] backlog-check :: pass
backlog clean
[6] spec-check :: pass
spec clean
[7] task-report-check :: pass
$report_path
[8] artifact-lifecycle-check :: pass
artifact clean
OUT
EOF
    cat >"$notifier_stub" <<'PYEOF'
#!/usr/bin/env python3
import os
import pathlib
import sys

log_path = pathlib.Path(os.environ["FAKE_NOTIFY_LOG"])
pending_state = pathlib.Path(os.environ["FAKE_PENDING_STATE"])
log_path.write_text(f"pending_exists={'1' if pending_state.exists() else '0'}\n", encoding="utf-8")
sys.exit(0)
PYEOF
    chmod +x "$validator_stub" "$notifier_stub"

    FAKE_NOTIFY_LOG="$notify_log" \
    FAKE_PENDING_STATE="$pending_state" \
    REDCAP_FEISHU_NOTIFIER="$notifier_stub" \
    REDCAP_VALIDATOR_CHAIN_SCRIPT="$validator_stub" \
    REDCAP_SESSION_BINDING_KEY="$binding_key" \
    REDCAP_HOST_PROCESS_PID="$pid" \
    REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid" \
    REDCAP_SKIP_INDEPENDENT_REVIEW=1 \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-session-end.sh" "$host" >/dev/null \
        || fail "session-end success notify after clear case failed"

    assert_exists "$notify_log"
    assert_string_contains "$(cat "$notify_log")" "pending_exists=0"
    assert_not_exists "$pending_state"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_session_end_notify_timeout_releases_lock_case() {
    local host="copilot"
    local binding_key pid probe_pid current_head report_path case_dir validator_stub notifier_stub lock_probe notifier_started pending_state

    log "case: session-end-notify-timeout-releases-lock"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "session-end-notify-timeout-releases-lock" >/dev/null 2>&1 || true

    binding_key="acceptance-session-end-notify-timeout-${RANDOM}-$$"
    pid="$((66460 + RANDOM))"
    spawn_host_probe probe_pid
    export REDCAP_HOST_PROCESS_PID="$pid"
    export REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid"
    redcap_runtime_init_from_binding "$host" "$REDCAP_ROOT" "$binding_key" >/dev/null \
        || fail "failed to initialize runtime binding for notify timeout case"
    REDCAP_SESSION_ISOLATION_MODE="full"
    export REDCAP_HOST_PROCESS_PID REDCAP_SESSION_ISOLATION_MODE REDCAP_RUNTIME_SESSION_ID REDCAP_RUNTIME_BINDING_KEY REDCAP_RUNTIME_HOST REDCAP_RUNTIME_CAPABILITY
    unset REDCAP_HOST_PROCESS_PROBE_PID
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    report_path="compass/docs/task-reports/2026-04-16-completion-hook-hardening.md"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for notify timeout case"
    write_current_report_marker_fixture "$report_path"
    pending_state="$(
        redcap_interop_write_pending_closure \
            "$REDCAP_ROOT" \
            "$REDCAP_ROOT/.dev-task.md" \
            "$host" \
            "acceptance-seed" \
            "review,notify" \
            "session-end-notify-timeout-releases-lock" \
            "$report_path" \
            "$current_head" \
            "$current_head"
    )" || fail "failed to seed pending closure for notify timeout case"
    assert_exists "$pending_state"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/session-end-notify-timeout.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    validator_stub="$case_dir/validator-pass.sh"
    notifier_stub="$case_dir/notifier.py"
    lock_probe="$case_dir/lock-probe.log"
    notifier_started="$case_dir/notifier.started"
    cat >"$validator_stub" <<EOF
#!/usr/bin/env bash
cat <<'OUT'
[1] review-proof-check :: pass
review clean
[2] reanchor-check :: pass
reanchor clean
[3] pm-gate :: pass
pm gate clean
[4] drift-check :: pass
drift clean
[5] backlog-check :: pass
backlog clean
[6] spec-check :: pass
spec clean
[7] task-report-check :: pass
$report_path
[8] artifact-lifecycle-check :: pass
artifact clean
OUT
EOF
    cat >"$notifier_stub" <<'PYEOF'
#!/usr/bin/env python3
import os
import pathlib
import time

pathlib.Path(os.environ["FAKE_NOTIFY_STARTED"]).write_text("started\n", encoding="utf-8")
time.sleep(5)
PYEOF
    chmod +x "$validator_stub" "$notifier_stub"

    (
        local attempts=0
        while [[ ! -f "$notifier_started" ]]; do
            attempts=$((attempts + 1))
            if [[ "$attempts" -ge 400 ]]; then
                echo "start-timeout" >"$lock_probe"
                exit 1
            fi
            sleep 0.05
        done
        if redcap_interop_acquire_pending_closure_lock "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md"; then
            echo "acquired" >"$lock_probe"
            redcap_interop_release_pending_closure_lock "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" >/dev/null 2>&1 || true
        else
            echo "failed" >"$lock_probe"
            exit 1
        fi
    ) &
    lock_probe_pid=$!

    FAKE_NOTIFY_STARTED="$notifier_started" \
    REDCAP_FEISHU_NOTIFIER="$notifier_stub" \
    REDCAP_FEISHU_NOTIFY_TIMEOUT_SECONDS=2 \
    REDCAP_VALIDATOR_CHAIN_SCRIPT="$validator_stub" \
    REDCAP_SESSION_BINDING_KEY="$binding_key" \
    REDCAP_HOST_PROCESS_PID="$pid" \
    REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid" \
    REDCAP_SKIP_INDEPENDENT_REVIEW=1 \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-session-end.sh" "$host" >/dev/null \
        || fail "session-end notify timeout case failed"

    wait "$lock_probe_pid" || fail "pending closure lock probe did not complete: $(counter_value "$lock_probe")"
    assert_exists "$lock_probe"
    assert_string_contains "$(cat "$lock_probe")" "acquired"
    redcap_interop_pending_closure_exists "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" \
        || fail "expected pending closure to remain after notify timeout"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_session_end_blocked_rewrite_keeps_report_anchor_case() {
    local host="copilot"
    local binding_key pid probe_pid current_head report_path case_dir validator_stub pending_state rewritten_artifact required_redlines

    log "case: session-end-blocked-rewrite-keeps-report-anchor"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "session-end-blocked-rewrite-keeps-report-anchor" >/dev/null 2>&1 || true

    binding_key="acceptance-session-end-report-anchor-${RANDOM}-$$"
    pid="$((66470 + RANDOM))"
    spawn_host_probe probe_pid
    export REDCAP_HOST_PROCESS_PID="$pid"
    export REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid"
    redcap_runtime_init_from_binding "$host" "$REDCAP_ROOT" "$binding_key" >/dev/null \
        || fail "failed to initialize runtime binding for report anchor case"
    REDCAP_SESSION_ISOLATION_MODE="full"
    export REDCAP_HOST_PROCESS_PID REDCAP_SESSION_ISOLATION_MODE REDCAP_RUNTIME_SESSION_ID REDCAP_RUNTIME_BINDING_KEY REDCAP_RUNTIME_HOST REDCAP_RUNTIME_CAPABILITY
    unset REDCAP_HOST_PROCESS_PROBE_PID
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    report_path="compass/docs/task-reports/2026-04-16-completion-hook-hardening.md"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for report anchor case"
    write_current_report_marker_fixture "$report_path"
    redcap_interop_write_pending_closure \
        "$REDCAP_ROOT" \
        "$REDCAP_ROOT/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "task-report,notify" \
        "session-end-blocked-rewrite-keeps-report-anchor" \
        "$report_path" \
        "$current_head" \
        "$current_head" \
        >/dev/null || fail "failed to seed pending closure for report anchor case"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/session-end-report-anchor.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    validator_stub="$case_dir/validator-report-fail.sh"
    cat >"$validator_stub" <<EOF
#!/usr/bin/env bash
cat <<'OUT'
[1] review-proof-check :: pass
review clean
[2] reanchor-check :: pass
reanchor clean
[3] pm-gate :: pass
pm gate clean
[4] drift-check :: pass
drift clean
[5] backlog-check :: pass
backlog clean
[6] spec-check :: pass
spec clean
[7] task-report-check :: fail
missing task report under compass/docs/task-reports/
[8] artifact-lifecycle-check :: pass
artifact clean
OUT
EOF
    chmod +x "$validator_stub"

    REDCAP_SKIP_FEISHU=1 \
    REDCAP_VALIDATOR_CHAIN_SCRIPT="$validator_stub" \
    REDCAP_SESSION_BINDING_KEY="$binding_key" \
    REDCAP_HOST_PROCESS_PID="$pid" \
    REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid" \
    REDCAP_SKIP_INDEPENDENT_REVIEW=1 \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-session-end.sh" "$host" >/dev/null \
        || fail "session-end blocked rewrite case failed"

    pending_state="$(redcap_interop_pending_closure_existing_file "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" 2>/dev/null || true)"
    assert_exists "$pending_state"
    rewritten_artifact="$(redcap_interop_read_state_field "$pending_state" "artifact_path" 2>/dev/null || true)"
    required_redlines="$(redcap_interop_read_state_field "$pending_state" "required_redlines" 2>/dev/null || true)"
    assert_eq "$rewritten_artifact" "$report_path"
    assert_string_contains "$required_redlines" "task-report"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_session_end_blocked_rewrite_normalizes_absolute_report_anchor_case() {
    local host="copilot"
    local binding_key pid probe_pid current_head report_rel report_abs case_dir validator_stub pending_state rewritten_artifact

    log "case: session-end-blocked-rewrite-normalizes-absolute-report-anchor"

    redcap_interop_clear_pending_closure "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" "acceptance-reset" "session-end-blocked-rewrite-normalizes-absolute-report-anchor" >/dev/null 2>&1 || true

    binding_key="acceptance-session-end-absolute-anchor-${RANDOM}-$$"
    pid="$((66480 + RANDOM))"
    spawn_host_probe probe_pid
    export REDCAP_HOST_PROCESS_PID="$pid"
    export REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid"
    redcap_runtime_init_from_binding "$host" "$REDCAP_ROOT" "$binding_key" >/dev/null \
        || fail "failed to initialize runtime binding for absolute report anchor case"
    REDCAP_SESSION_ISOLATION_MODE="full"
    export REDCAP_HOST_PROCESS_PID REDCAP_SESSION_ISOLATION_MODE REDCAP_RUNTIME_SESSION_ID REDCAP_RUNTIME_BINDING_KEY REDCAP_RUNTIME_HOST REDCAP_RUNTIME_CAPABILITY
    unset REDCAP_HOST_PROCESS_PROBE_PID
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    report_rel="compass/docs/task-reports/2026-04-16-completion-hook-hardening.md"
    report_abs="$REDCAP_ROOT/$report_rel"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for absolute report anchor case"
    redcap_interop_write_pending_closure \
        "$REDCAP_ROOT" \
        "$REDCAP_ROOT/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "task-report,notify" \
        "session-end-blocked-rewrite-normalizes-absolute-report-anchor" \
        "$report_abs" \
        "$current_head" \
        "$current_head" \
        >/dev/null || fail "failed to seed absolute pending closure for report anchor case"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/session-end-absolute-report-anchor.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    validator_stub="$case_dir/validator-report-fail.sh"
    cat >"$validator_stub" <<EOF
#!/usr/bin/env bash
cat <<'OUT'
[1] review-proof-check :: pass
review clean
[2] reanchor-check :: pass
reanchor clean
[3] pm-gate :: pass
pm gate clean
[4] drift-check :: pass
drift clean
[5] backlog-check :: pass
backlog clean
[6] spec-check :: pass
spec clean
[7] task-report-check :: fail
missing task report under compass/docs/task-reports/
[8] artifact-lifecycle-check :: pass
artifact clean
OUT
EOF
    chmod +x "$validator_stub"

    REDCAP_SKIP_FEISHU=1 \
    REDCAP_VALIDATOR_CHAIN_SCRIPT="$validator_stub" \
    REDCAP_SESSION_BINDING_KEY="$binding_key" \
    REDCAP_HOST_PROCESS_PID="$pid" \
    REDCAP_HOST_PROCESS_PROBE_PID="$probe_pid" \
    REDCAP_SKIP_INDEPENDENT_REVIEW=1 \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-session-end.sh" "$host" >/dev/null \
        || fail "session-end absolute report anchor case failed"

    pending_state="$(redcap_interop_pending_closure_existing_file "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" 2>/dev/null || true)"
    assert_exists "$pending_state"
    rewritten_artifact="$(redcap_interop_read_state_field "$pending_state" "artifact_path" 2>/dev/null || true)"
    assert_eq "$rewritten_artifact" "$report_rel"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_pending_closure_lock_keeps_live_legacy_lock_case() {
    local lock_path legacy_owner_pid legacy_created_at

    log "case: pending-closure-lock-keeps-live-legacy-lock"

    lock_path="$(redcap_interop_pending_closure_lock_path "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md")"
    mkdir -p "$(dirname "$lock_path")"
    spawn_host_probe legacy_owner_pid
    legacy_created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf '%s\t%s\n' "$legacy_owner_pid" "$legacy_created_at" >"$lock_path"

    if redcap_interop_prune_stale_pending_closure_lock "$lock_path"; then
        fail "pending closure lock unexpectedly pruned live legacy lock"
    fi
    assert_exists "$lock_path"

    redcap_interop_release_pending_closure_lock_path "$lock_path" >/dev/null 2>&1 || true
}

run_pending_closure_lock_prunes_reused_pid_case() {
    local lock_path owner_started_at owner_pid

    log "case: pending-closure-lock-prunes-reused-pid"

    lock_path="$(redcap_interop_pending_closure_lock_path "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md")"
    mkdir -p "$(dirname "$lock_path")"
    printf '%s\t%s\t%s\n' "$$" "Mon Jan  1 00:00:00 1990" "1970-01-01T00:00:00Z" >"$lock_path"

    redcap_interop_acquire_pending_closure_lock "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" \
        || fail "pending closure lock should prune reused pid lock"

    owner_pid="$(redcap_interop_pending_closure_lock_owner_pid "$lock_path" 2>/dev/null || true)"
    owner_started_at="$(redcap_interop_lock_owner_started_at "$lock_path" 2>/dev/null || true)"
    assert_eq "$owner_pid" "$$"
    assert_eq "$owner_started_at" "$(redcap_runtime_process_started_at "$$")"
    redcap_interop_release_pending_closure_lock "$REDCAP_ROOT" "$REDCAP_ROOT/.dev-task.md" >/dev/null 2>&1 || true
}

run_task_complete_guard_prunes_reused_pid_lock_case() {
    local host="copilot"
    local binding_key pid current_head report_path report_rel case_dir complete_log complete_stub task_complete_slice lock_path

    log "case: task-complete-guard-prunes-reused-pid-lock"

    redcap_runtime_clear_context
    binding_key="acceptance-task-complete-reused-pid-${RANDOM}-$$"
    pid="$((66480 + RANDOM))"
    init_bound_runtime "$host" "$binding_key" "$pid"
    current_head="$(git -C "$REDCAP_ROOT" rev-parse HEAD)"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for reused pid lock case"
    report_path="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-task-complete-reused-pid-${RANDOM}-$$.md"
    report_rel="${report_path#$REDCAP_ROOT/}"
    printf '# acceptance reused pid report\n' >"$report_path"
    LEGACY_TMP_FILES+=("$report_path")
    write_current_report_marker_fixture "$report_rel"
    task_complete_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    lock_path="$(redcap_runtime_path "layerB/task-complete-guard.lock")"
    mkdir -p "$(dirname "$lock_path")"
    printf '%s\t%s\t%s\n' "$$" "Mon Jan  1 00:00:00 1990" "1970-01-01T00:00:00Z" >"$lock_path"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/task-complete-reused-pid.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    complete_log="$case_dir/on-complete.log"
    complete_stub="$case_dir/on-complete-stub.sh"
    cat >"$complete_stub" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "on-complete" >>"$complete_log"
EOF
    chmod +x "$complete_stub"

    REDCAP_TASK_COMPLETE_SLICE="$task_complete_slice" \
    REDCAP_ON_COMPLETE_SCRIPT="$complete_stub" \
    REDCAP_HOST_PROCESS_PID="$pid" \
        bash "$REDCAP_ROOT/compass/tools/redcap-layerB-task-complete-guard.sh" "$host" >/dev/null \
        || fail "task complete guard should prune reused pid lock"

    assert_exists "$complete_log"
    assert_num_eq "$(wc -l < "$complete_log" | tr -d '[:space:]')" 1
    assert_not_exists "$lock_path"

    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_runtime_claim_parent_fallback_case() {
    local host="claude"
    local binding_key runtime_session_id capability child_capability child_runtime_id

    log "case: runtime-claim-parent-fallback"

    binding_key="acceptance-parent-claim-${RANDOM}-$$"
    export REDCAP_HOST_PROCESS_PID="$$"
    export REDCAP_HOST_PROCESS_PROBE_PID="$$"
    redcap_runtime_init_from_binding "$host" "$REDCAP_ROOT" "$binding_key" >/dev/null || fail "failed to initialize parent claim runtime"
    runtime_session_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    capability="${REDCAP_RUNTIME_CAPABILITY:-}"
    [[ -n "$runtime_session_id" ]] || fail "runtime session id missing for parent fallback case"
    [[ -n "$capability" ]] || fail "runtime capability missing for parent fallback case"

    redcap_runtime_clear_context
    unset REDCAP_HOST_PROCESS_PID REDCAP_HOST_PROCESS_PROBE_PID

    child_capability="$(bash -lc 'set -euo pipefail; cd "'"$REDCAP_ROOT"'"; source compass/tools/redcap-runtime-state.sh; redcap_runtime_load_claimed_capability "'"$host"'" "'"$runtime_session_id"'"')"
    assert_eq "$child_capability" "$capability"

    child_runtime_id="$(bash -lc 'set -euo pipefail; cd "'"$REDCAP_ROOT"'"; source compass/tools/redcap-runtime-state.sh; redcap_runtime_attach_from_process_claim "'"$host"'" >/dev/null; printf "%s\n" "${REDCAP_RUNTIME_SESSION_ID:-}"')"
    assert_eq "$child_runtime_id" "$runtime_session_id"

    redcap_runtime_clear_process_claim "$host" "$$" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_runtime_clear_context_clears_probe_pid_case() {
    log "case: runtime-clear-context-clears-probe-pid"

    export REDCAP_HOST_PROCESS_PID="12345"
    export REDCAP_HOST_PROCESS_PROBE_PID="23456"
    export REDCAP_SESSION_ISOLATION_MODE="full"
    export REDCAP_SESSION_RESUME_REASON="acceptance"

    redcap_runtime_clear_context

    assert_eq "${REDCAP_HOST_PROCESS_PID:-}" ""
    assert_eq "${REDCAP_HOST_PROCESS_PROBE_PID:-}" ""
    assert_eq "${REDCAP_SESSION_ISOLATION_MODE:-}" ""
    assert_eq "${REDCAP_SESSION_RESUME_REASON:-}" ""
}

run_sessionstart_auto_reconcile_clear_case() {
    local host="claude"
    local binding_key pid
    local report_path report_rel pending_state current_head required_redlines repo case_dir validator_stub

    log "case: sessionstart-auto-reconcile-clear"

    repo="$ACCEPT_ROOT/sessionstart-auto-reconcile-clear/repo"
    create_task_report_fixture_repo "$repo"
    report_rel="compass/docs/task-reports/zz-acceptance-reconcile-clear-${RANDOM}-$$.md"
    report_path="$repo/$report_rel"
    cp "$repo/references/task-report-template.md" "$report_path"
    current_head="$(git -C "$repo" rev-parse HEAD)"
    redcap_interop_write_pending_closure \
        "$repo" \
        "$repo/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "task-report" \
        "sessionstart-auto-reconcile-clear" \
        "$report_rel" \
        "$current_head" \
        "$current_head" \
        >/dev/null
    pending_state=$(redcap_interop_pending_closure_file "$repo" "$repo/.dev-task.md")
    assert_exists "$pending_state"

    binding_key="acceptance-reconcile-clear-${RANDOM}-$$"
    pid="$((63000 + RANDOM))"
    init_bound_runtime_for_repo "$host" "$repo" "$binding_key" "$pid"
    write_current_report_marker_fixture "$report_rel" "$repo/.dev-task.md"
    case_dir="$(mktemp -d "$ACCEPT_ROOT/sessionstart-reconcile-clear.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    validator_stub="$case_dir/validator-stub.sh"
    cat >"$validator_stub" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
[redcap-validator-chain] mode=obligation-reconcile overall=fail
[1] review-proof-check :: pass
review ok
[2] reanchor-check :: pass
reanchor ok
[3] pm-gate :: pass
pm-gate ok
[4] drift-check :: fail
drift failed
[5] backlog-check :: pass
backlog ok
[6] spec-check :: pass
spec ok
[7] task-report-check :: pass
task-report ok
[8] artifact-lifecycle-check :: pass
artifact ok
OUT
exit 1
EOF
    chmod +x "$validator_stub"
    REDCAP_VALIDATOR_CHAIN_SCRIPT="$validator_stub" \
    REDCAP_HOST_PROCESS_PID="$pid" \
        bash "$repo/compass/tools/redcap-pending-closure-reconcile.sh" "$host" >/dev/null \
        || fail "pending closure reconcile clear case failed"

    if [[ -f "$pending_state" ]]; then
        required_redlines=$(redcap_interop_read_state_field "$pending_state" "required_redlines" 2>/dev/null || true)
        assert_eq "$(normalize_csv "$required_redlines")" "$(normalize_csv "drift")"
        redcap_interop_clear_pending_closure "$repo" "$repo/.dev-task.md" "acceptance-cleanup" "sessionstart-auto-reconcile-clear" >/dev/null
    else
        assert_not_exists "$pending_state"
    fi
    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_sessionstart_auto_reconcile_hash_mismatch_case() {
    local host="claude"
    local binding_key pid
    local report_path report_rel pending_state mismatch_state reanchored_state required_redlines
    local current_hash mismatch_hash current_head repo case_dir validator_stub

    log "case: sessionstart-auto-reconcile-hash-mismatch"

    repo="$ACCEPT_ROOT/sessionstart-auto-reconcile-hash-mismatch/repo"
    create_task_report_fixture_repo "$repo"
    report_rel="compass/docs/task-reports/zz-acceptance-reconcile-hash-${RANDOM}-$$.md"
    report_path="$repo/$report_rel"
    cp "$repo/references/task-report-template.md" "$report_path"
    current_hash=$(redcap_dev_task_confirmed_hash "$repo/.dev-task.md")
    current_head="$(git -C "$repo" rev-parse HEAD)"
    mismatch_hash="deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    [[ "$current_hash" != "$mismatch_hash" ]] || fail "hash mismatch fixture collided with current confirmed hash"

    redcap_interop_write_pending_closure \
        "$repo" \
        "$repo/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "task-report,notify" \
        "sessionstart-auto-reconcile-hash-mismatch" \
        "$report_rel" \
        "$current_hash" \
        "$current_hash" \
        >/dev/null
    pending_state=$(redcap_interop_pending_closure_file "$repo" "$repo/.dev-task.md")
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
    mismatch_state="${pending_state/$current_hash/$mismatch_hash}"
    mv "$pending_state" "$mismatch_state"
    pending_state="$mismatch_state"

    binding_key="acceptance-reconcile-hash-mismatch-${RANDOM}-$$"
    pid="$((64000 + RANDOM))"
    init_bound_runtime_for_repo "$host" "$repo" "$binding_key" "$pid"
    write_current_report_marker_fixture "$report_rel" "$repo/.dev-task.md"
    redcap_runtime_write_text "layerB/initial-head" "$current_head" || fail "failed to seed initial head for hash mismatch case"
    case_dir="$(mktemp -d "$ACCEPT_ROOT/sessionstart-reconcile-hash-mismatch.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    validator_stub="$case_dir/validator-stub.sh"
    cat >"$validator_stub" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
[redcap-validator-chain] mode=obligation-reconcile overall=pass
[1] review-proof-check :: pass
review ok
[2] reanchor-check :: pass
reanchor ok
[3] pm-gate :: pass
pm-gate ok
[4] drift-check :: pass
drift ok
[5] backlog-check :: pass
backlog ok
[6] spec-check :: pass
spec ok
[7] task-report-check :: pass
task-report ok
[8] artifact-lifecycle-check :: pass
artifact ok
OUT
exit 0
EOF
    chmod +x "$validator_stub"
    REDCAP_VALIDATOR_CHAIN_SCRIPT="$validator_stub" \
    REDCAP_HOST_PROCESS_PID="$pid" \
        bash "$repo/compass/tools/redcap-pending-closure-reconcile.sh" "$host" >/dev/null \
        || fail "pending closure reconcile hash mismatch case failed"

    assert_not_exists "$pending_state"
    reanchored_state=$(redcap_interop_pending_closure_file "$repo" "$repo/.dev-task.md")
    assert_exists "$reanchored_state"
    assert_eq "$(redcap_interop_read_state_field "$reanchored_state" "confirmed_hash" 2>/dev/null || true)" "$current_hash"
    required_redlines=$(redcap_interop_read_state_field "$reanchored_state" "required_redlines" 2>/dev/null || true)
    assert_eq "$(normalize_csv "$required_redlines")" "$(normalize_csv "notify")"

    redcap_interop_clear_pending_closure "$repo" "$repo/.dev-task.md" "acceptance-cleanup" "sessionstart-auto-reconcile-hash-mismatch" >/dev/null
    redcap_runtime_clear_process_claim "$host" "$pid" >/dev/null 2>&1 || true
    redcap_runtime_clear_context
}

run_sessionstart_auto_reconcile_backlog_spec_case() {
    local host="claude"
    local binding_key pid current_head
    local report_path report_rel pending_state required_redlines
    local case_dir validator_stub repo

    log "case: sessionstart-auto-reconcile-backlog-spec"

    repo="$ACCEPT_ROOT/sessionstart-auto-reconcile-backlog-spec/repo"
    create_task_report_fixture_repo "$repo"
    redcap_interop_clear_pending_closure "$repo" "$repo/.dev-task.md" "acceptance-reset" "sessionstart-auto-reconcile-backlog-spec" >/dev/null 2>&1 || true

    report_rel="compass/docs/task-reports/zz-acceptance-reconcile-backlog-spec-${RANDOM}-$$.md"
    report_path="$repo/$report_rel"
    cp "$repo/references/task-report-template.md" "$report_path"
    current_head="$(git -C "$repo" rev-parse HEAD)"
    redcap_interop_write_pending_closure \
        "$repo" \
        "$repo/.dev-task.md" \
        "$host" \
        "acceptance-seed" \
        "review,task-report,notify" \
        "sessionstart-auto-reconcile-backlog-spec" \
        "$report_rel" \
        "$current_head" \
        "$current_head" \
        >/dev/null

    binding_key="acceptance-reconcile-backlog-spec-${RANDOM}-$$"
    pid="$((64100 + RANDOM))"
    init_bound_runtime_for_repo "$host" "$repo" "$binding_key" "$pid"
    write_current_report_marker_fixture "$report_rel" "$repo/.dev-task.md"

    case_dir="$(mktemp -d "$ACCEPT_ROOT/sessionstart-reconcile-backlog-spec.XXXXXX")"
    TEMP_PROJECTS+=("$case_dir")
    validator_stub="$case_dir/validator-stub.sh"
    cat >"$validator_stub" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
[redcap-validator-chain] mode=obligation-reconcile overall=fail
[1] review-proof-check :: pass
review ok
[2] reanchor-check :: pass
reanchor ok
[3] pm-gate :: pass
pm-gate ok
[4] drift-check :: pass
drift ok
[5] backlog-check :: fail
backlog failed
[6] spec-check :: fail
spec failed
[7] task-report-check :: pass
task-report ok
[8] artifact-lifecycle-check :: pass
artifact ok
OUT
exit 1
EOF
    chmod +x "$validator_stub"

    REDCAP_VALIDATOR_CHAIN_SCRIPT="$validator_stub" \
    REDCAP_HOST_PROCESS_PID="$pid" \
        bash "$repo/compass/tools/redcap-pending-closure-reconcile.sh" "$host" >/dev/null \
        || fail "pending closure reconcile backlog/spec case failed"

    pending_state="$(redcap_interop_pending_closure_file "$repo" "$repo/.dev-task.md")"
    assert_exists "$pending_state"
    required_redlines="$(redcap_interop_read_state_field "$pending_state" "required_redlines" 2>/dev/null || true)"
    assert_eq "$(normalize_csv "$required_redlines")" "$(normalize_csv "notify,backlog,spec")"

    redcap_interop_clear_pending_closure "$repo" "$repo/.dev-task.md" "acceptance-cleanup" "sessionstart-auto-reconcile-backlog-spec" >/dev/null 2>&1 || true
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

run_sessionstart_control_gate_failure_degrades_case() {
    local case_root case_core fixture_root workboard compat_dir degraded_log output
    local task_id top_goal active_slice confirmed_hash

    log "case: sessionstart-control-gate-failure-degrades"

    task_id="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "task_id")"
    top_goal="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "top_goal")"
    active_slice="$(redcap_dev_task_extract_kv "$REDCAP_ROOT/.dev-task.md" "active_slice")"
    confirmed_hash="$(redcap_dev_task_confirmed_hash "$REDCAP_ROOT/.dev-task.md")"
    case_root="$ACCEPT_ROOT/sessionstart-control-gate-failure-degrades"
    case_core="$CONTINUITY_CORE_DIR/sessionstart-control-gate-failure-degrades"
    fixture_root="$case_root/repo"
    workboard="$case_root/plan.md"

    mkdir -p "$fixture_root/compass"
    cp -R "$REDCAP_ROOT/compass/tools" "$fixture_root/compass/"
    cp "$REDCAP_ROOT/.dev-task.md" "$fixture_root/.dev-task.md"
    chmod +x "$fixture_root/compass/tools/"*.sh

    cat >"$fixture_root/compass/tools/redcap-validator-chain.sh" <<'EOF'
#!/usr/bin/env bash
echo "fixture validator failure" >&2
exit 37
EOF
    chmod +x "$fixture_root/compass/tools/redcap-validator-chain.sh"

    write_workboard_fixture "$workboard" "$fixture_root/.dev-task.md" "$task_id" "$top_goal" "$active_slice" "$confirmed_hash"

    output="$(
        printf '{}' | \
            REDCAP_HOOK_CWD="$fixture_root" \
            REDCAP_HOST_WORKBOARD_PATH="$workboard" \
            REDCAP_CONTINUITY_ROOT_DIR="$case_core" \
            REDCAP_SKIP_FEISHU=1 \
            REDCAP_SESSION_ISOLATION_MODE="degraded" \
            REDCAP_SESSION_RESUME_REASON="acceptance-control-gate" \
            REDCAP_SESSION_RESUME_PROFILE="safe-degraded" \
            REDCAP_SESSION_RESUME_EVIDENCE="acceptance-fixture" \
            REDCAP_SESSION_RESUME_RECOVERY_PATH="safe-degraded" \
            REDCAP_SESSION_RESUME_ALLOW_DISK_RECOVERY="0" \
            REDCAP_SESSION_RESUME_ALLOW_CAPABILITY_FILE_RECOVERY="0" \
            REDCAP_HOST_PROCESS_PID="$$" \
            bash "$fixture_root/compass/tools/redcap-layerB-session-start.sh" "claude" 2>&1
    )"

    assert_string_contains "$output" "fixture validator failure"
    compat_dir="$(redcap_runtime_compat_dir_for_root "$fixture_root")"
    degraded_log="$compat_dir/degraded-mode.log"
    assert_exists "$degraded_log"
    assert_contains "$degraded_log" "layerB-session-start-control-gate-failed"
    assert_contains "$degraded_log" "check=validator-chain status=37"
    assert_eq "$(workboard_value "$workboard" "isolation_mode")" "degraded"
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
    spawn_host_probe source_probe
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
    spawn_host_probe target_probe
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
    spawn_host_probe source_probe
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
    spawn_host_probe target_probe
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

run_artifact_lifecycle_classifier_case() {
    local repo output

    log "case: artifact-lifecycle-classifier"

    repo="$(make_temp_project)"
    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-artifact-classifier.sh" "$repo" \
        ".dev-task.md" \
        "compass/docs/catalog.json" \
        "compass/docs/catalog.json/evil.md" \
        "compass/docs/specs/ok.md" \
        "compass/docs/random.md" \
        "compass/.workflow/local.txt" \
        "docs-scratch/note.md")"

    assert_string_contains "$output" $'.dev-task.md\tsession-isolated\tsession-isolated-process-state\t'
    assert_string_contains "$output" $'compass/docs/catalog.json\trepo-tracked\trepo-tracked-evidence\tcompass/docs approved collection'
    assert_string_contains "$output" $'compass/docs/catalog.json/evil.md\tlocal-only\tdocs-root-policy-violation\tviolates compass/docs root policy'
    assert_string_contains "$output" $'compass/docs/specs/ok.md\trepo-tracked\trepo-tracked-evidence\tcompass/docs approved collection'
    assert_string_contains "$output" $'compass/docs/random.md\tlocal-only\tdocs-root-policy-violation\tviolates compass/docs root policy'
    assert_string_contains "$output" $'compass/.workflow/local.txt\tlocal-only\tlocal-only-host-asset\t'
    assert_string_contains "$output" $'docs-scratch/note.md\ttemporary\ttemporary-reading-space-root\t'
}

run_artifact_lifecycle_hook_install_case() {
    local repo

    log "case: artifact-lifecycle-hook-install"

    repo="$(make_temp_project)"
    init_temp_git_repo "$repo"
    mkdir -p "$repo/custom-hooks"
    install_artifact_hook_fixture "$repo"

    git -C "$repo" config --local core.hooksPath custom-hooks
    bash "$repo/compass/tools/redcap-ensure-git-hooks.sh" "$repo"

    assert_eq "$(git -C "$repo" config --local --get core.hooksPath)" ".githooks"
    assert_eq "$(git -C "$repo" config --local --get redcap.previousHooksPath)" "custom-hooks"
}

run_artifact_lifecycle_pre_commit_block_case() {
    local repo output status

    log "case: artifact-lifecycle-pre-commit-block"

    repo="$(make_temp_project)"
    init_temp_git_repo "$repo"
    seed_temp_git_repo "$repo"
    install_artifact_hook_fixture "$repo"
    git -C "$repo" config --local core.hooksPath .githooks

    printf 'tracked update\n' >>"$repo/README.md"
    printf 'session state\n' >"$repo/.dev-task.md"
    git -C "$repo" add README.md .dev-task.md

    set +e
    output="$(git -C "$repo" commit -m "mixed lifecycle" 2>&1)"
    status=$?
    set -e

    [[ "$status" -ne 0 ]] || fail "mixed lifecycle commit unexpectedly succeeded"
    assert_string_contains "$output" "disallowed artifacts detected"
    assert_string_contains "$output" ".dev-task.md"
    assert_string_contains "$output" "mixed-lifecycle staged commit detected"
}

run_artifact_lifecycle_pre_commit_allow_case() {
    local repo

    log "case: artifact-lifecycle-pre-commit-allow"

    repo="$(make_temp_project)"
    init_temp_git_repo "$repo"
    seed_temp_git_repo "$repo"
    install_artifact_hook_fixture "$repo"
    git -C "$repo" config --local core.hooksPath .githooks

    printf 'tracked update\n' >>"$repo/README.md"
    git -C "$repo" add README.md
    git -C "$repo" commit --quiet -m "tracked only"

    assert_eq "$(git -C "$repo" rev-list --count HEAD)" "2"
}

run_artifact_lifecycle_rejects_tabbed_path_case() {
    local repo output status bad_name

    log "case: artifact-lifecycle-rejects-tabbed-path"

    repo="$(make_temp_project)"
    init_temp_git_repo "$repo"
    seed_temp_git_repo "$repo"
    install_artifact_hook_fixture "$repo"
    git -C "$repo" config --local core.hooksPath .githooks

    bad_name=$'notes\twith-tab.md'
    printf 'bad path\n' >"$repo/$bad_name"
    git -C "$repo" add "$bad_name"

    set +e
    output="$(git -C "$repo" commit -m "tabbed path" 2>&1)"
    status=$?
    set -e

    [[ "$status" -ne 0 ]] || fail "tabbed filename unexpectedly bypassed lifecycle gate"
    assert_string_contains "$output" "unsupported filename contains tab/newline"
}

run_docs_catalog_check_case() {
    local output summary temp_catalog stale_output stale_status zz_report

    log "case: docs-catalog-check"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-docs-catalog.sh" check)"
    assert_string_contains "$output" "DOCS_CATALOG_OK"
    assert_contains "$REDCAP_ROOT/compass/docs/catalog.json" '"path": "compass/docs/task-reports/2026-04-17-live-closeout-final-blockers.md"'
    assert_contains "$REDCAP_ROOT/compass/docs/catalog.json" '"read_policy": "read-catalog-summary-first-then-open-if-current-anchor"'
    assert_contains "$REDCAP_ROOT/compass/docs/catalog.json" '"status_basis": "filename_recency_only"'
    assert_contains "$REDCAP_ROOT/compass/docs/catalog.json" '"path": "compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md"'

    summary="$(bash "$REDCAP_ROOT/compass/tools/redcap-docs-catalog.sh" summary)"
    assert_string_contains "$summary" "DOCS_CATALOG_SUMMARY"
    assert_string_contains "$summary" "rough_token_pressure="
    assert_string_contains "$summary" "task-reports:"

    zz_report="$REDCAP_ROOT/compass/docs/task-reports/zz-acceptance-docs-catalog-ignore-${RANDOM}-$$.md"
    LEGACY_TMP_FILES+=("$zz_report")
    printf '# acceptance-only report fixture\n' >"$zz_report"
    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-docs-catalog.sh" check)"
    assert_string_contains "$output" "DOCS_CATALOG_OK"

    temp_catalog="$ACCEPT_ROOT/docs-catalog-fixture.json"
    bash "$REDCAP_ROOT/compass/tools/redcap-docs-catalog.sh" generate "$temp_catalog"
    REDCAP_DOCS_CATALOG_PATH="$temp_catalog" bash "$REDCAP_ROOT/compass/tools/redcap-docs-catalog.sh" check >/dev/null
    printf '\n' >>"$temp_catalog"
    set +e
    stale_output="$(REDCAP_DOCS_CATALOG_PATH="$temp_catalog" bash "$REDCAP_ROOT/compass/tools/redcap-docs-catalog.sh" check 2>&1)"
    stale_status=$?
    set -e
    [[ "$stale_status" -ne 0 ]] || fail "stale docs catalog unexpectedly passed"
    assert_string_contains "$stale_output" "catalog is out of date"
}

run_docs_catalog_progressive_disclosure_case() {
    local plan_output budget_output blocked_output blocked_status bulk_output bulk_status

    log "case: docs-catalog-progressive-disclosure"

    plan_output="$(bash "$REDCAP_ROOT/compass/tools/redcap-docs-catalog.sh" plan "当前 pending closure task report" 5)"
    assert_string_contains "$plan_output" "DOCS_ACCESS_PLAN"
    assert_string_contains "$plan_output" "rule=Open only the exact paths needed; run budget before opening source files."
    assert_string_contains "$plan_output" "compass/docs/task-reports/2026-04-17-live-closeout-final-blockers.md"

    budget_output="$(bash "$REDCAP_ROOT/compass/tools/redcap-docs-catalog.sh" budget "compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md")"
    assert_string_contains "$budget_output" "DOCS_ACCESS_BUDGET_OK"
    assert_string_contains "$budget_output" "files=1"

    set +e
    blocked_output="$(REDCAP_DOCS_BUDGET_MAX_HIGH_TOKENS=1000 bash "$REDCAP_ROOT/compass/tools/redcap-docs-catalog.sh" budget "compass/docs/task-reports/2026-04-17-live-closeout-final-blockers.md" 2>&1)"
    blocked_status=$?
    set -e
    [[ "$blocked_status" -ne 0 ]] || fail "oversized docs read budget unexpectedly passed"
    assert_string_contains "$blocked_output" "rough token budget exceeded"

    set +e
    bulk_output="$(bash "$REDCAP_ROOT/compass/tools/redcap-docs-catalog.sh" budget "compass/docs/" 2>&1)"
    bulk_status=$?
    set -e
    [[ "$bulk_status" -ne 0 ]] || fail "docs directory budget unexpectedly passed"
    assert_string_contains "$bulk_output" "directory reads are not allowed"
}

run_docs_retention_check_case() {
    local output fixture stale_output stale_status

    log "case: docs-retention-check"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-docs-catalog.sh" retention-check)"
    assert_string_contains "$output" "DOCS_RETENTION_CHECK_OK"
    assert_string_contains "$output" "archive_candidates_check_only="

    fixture="$ACCEPT_ROOT/docs-retention-fixture"
    mkdir -p "$fixture/compass/docs/archive" "$fixture/compass/tools"
    cp "$REDCAP_ROOT/compass/tools/redcap-docs-catalog.sh" "$fixture/compass/tools/redcap-docs-catalog.sh"
    cp -R "$REDCAP_ROOT/compass/docs/specs" "$fixture/compass/docs/specs"
    cp -R "$REDCAP_ROOT/compass/docs/task-reports" "$fixture/compass/docs/task-reports"
    cp -R "$REDCAP_ROOT/compass/docs/research" "$fixture/compass/docs/research"
    cp -R "$REDCAP_ROOT/compass/docs/traces" "$fixture/compass/docs/traces"
    chmod +x "$fixture/compass/tools/redcap-docs-catalog.sh"
    printf '# bad retention log\n' >"$fixture/compass/docs/archive/retention-log.md"

    set +e
    stale_output="$(bash "$fixture/compass/tools/redcap-docs-catalog.sh" retention-check 2>&1)"
    stale_status=$?
    set -e
    [[ "$stale_status" -ne 0 ]] || fail "bad docs retention log unexpectedly passed"
    assert_string_contains "$stale_output" "retention log missing required phrase"
}

run_backlog_check_strict_case() {
    log "case: backlog-check-strict"

    bash "$REDCAP_ROOT/compass/tools/redcap-backlog-check.sh" strict "$REDCAP_ROOT/.dev-task.md" >/dev/null
}

run_current_status_overview_case() {
    local output

    log "case: current-status-overview"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-current-status.sh" "$REDCAP_ROOT/.dev-task.md")"
    assert_string_contains "$output" "当前已完成："
    assert_string_contains "$output" "## 收尾红线"
    assert_string_contains "$output" "## 长期 backlog"
    assert_string_contains "$output" "## CLI 工具族"
    assert_string_contains "$output" "## 棱镜 / 独立评审"
    assert_string_contains "$output" "## docs 考古入口"
    assert_string_contains "$output" "## token 风险入口"
    assert_string_contains "$output" "## 追踪连续性"
    assert_string_contains "$output" "## Layer B FSM"
    assert_string_contains "$output" "lifecycle-state:"
    assert_string_contains "$output" "independent-acceptance:"
    assert_string_contains "$output" "token-risk-audit:"
    assert_string_contains "$output" "tracking-health:"
    assert_string_contains "$output" "## 待验证登记"
    assert_string_contains "$output" "## closeout runtime"
    assert_string_contains "$output" "promise-ledger:"
    assert_string_contains "$output" "closeout-receipt:"
    assert_string_contains "$output" "active_slice:"
}

run_tracking_health_overview_case() {
    local output

    log "case: tracking-health-overview"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-tracking-health.sh" "$REDCAP_ROOT/.dev-task.md")"
    assert_string_contains "$output" "REDCAP_TRACKING_HEALTH"
    assert_string_contains "$output" "task_anchor=present"
    assert_string_contains "$output" "task_report=present"
    assert_string_contains "$output" "explore_notes=active:"
    assert_string_contains "$output" "TRACKING_OK"
}

run_install_overview_case() {
    local output home_root

    log "case: install-overview"

    home_root="$ACCEPT_ROOT/install-home"
    rm -rf "$home_root"
    mkdir -p "$home_root"

    output="$(
        HOME="$home_root" \
        bash "$REDCAP_ROOT/compass/tools/redcap-install.sh" \
            --host acceptance \
            --task-file "$REDCAP_ROOT/.dev-task.md" \
            --init-identity
    )"
    assert_string_contains "$output" "REDCAP_INSTALL"
    assert_string_contains "$output" "identity=initialized:"
    assert_string_contains "$output" "[ok] current-status"
    assert_string_contains "$output" "[ok] tracking-health"
    assert_string_contains "$output" "[ok] execution-guarantees"
    assert_string_contains "$output" "[ok] revival-protocol"
    assert_string_contains "$output" "REDCAP_INSTALL_OK"
}

run_execution_guarantees_check_case() {
    local output temp_registry stale_output stale_status

    log "case: execution-guarantees-check"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-execution-guarantee-check.sh")"
    assert_string_contains "$output" "EXECUTION_GUARANTEES_OK"

    temp_registry="$ACCEPT_ROOT/execution-guarantees-stale.json"
    cp "$REDCAP_ROOT/references/execution-guarantees.json" "$temp_registry"
    python3 - "$temp_registry" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
for entry in data["guarantees"]:
    if entry["id"] == "revival-current-status":
        entry["auto_enforceable"] = True
        entry["guarantee_paths"] = []
        entry.pop("non_automation_reason", None)
        break
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

    set +e
    stale_output="$(bash "$REDCAP_ROOT/compass/tools/redcap-execution-guarantee-check.sh" "$temp_registry" 2>&1)"
    stale_status=$?
    set -e
    [[ "$stale_status" -ne 0 ]] || fail "stale execution-guarantee registry unexpectedly passed"
    assert_string_contains "$stale_output" "revival-current-status"
}

run_knowledge_index_check_case() {
    local output fixture stale_output stale_status

    log "case: knowledge-index-check"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-knowledge-index-check.sh")"
    assert_string_contains "$output" "KNOWLEDGE_INDEX_OK"

    fixture="$ACCEPT_ROOT/knowledge-index-fixture"
    mkdir -p "$fixture/compass/knowledge" "$fixture/compass/tools"
    cp "$REDCAP_ROOT/compass/tools/redcap-knowledge-index-check.sh" "$fixture/compass/tools/redcap-knowledge-index-check.sh"
    cp "$REDCAP_ROOT/compass/knowledge/lessons.md" "$fixture/compass/knowledge/lessons.md"
    cp "$REDCAP_ROOT/compass/knowledge/design-principles.md" "$fixture/compass/knowledge/design-principles.md"
    printf '# bad index\n\n首读导航\n不要默认 bulk-read\nredcap-knowledge-index-check.sh\ncompass/knowledge/lessons.md\n' >"$fixture/compass/knowledge/index.md"
    chmod +x "$fixture/compass/tools/redcap-knowledge-index-check.sh"

    set +e
    stale_output="$(bash "$fixture/compass/tools/redcap-knowledge-index-check.sh" 2>&1)"
    stale_status=$?
    set -e
    [[ "$stale_status" -ne 0 ]] || fail "bad knowledge index unexpectedly passed"
    assert_string_contains "$stale_output" "index missing required phrase: 热点主题速览"
}

run_revival_protocol_check_case() {
    local fixture output stale_output stale_status

    log "case: revival-protocol-check"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-revival-check.sh" "$REDCAP_ROOT")"
    assert_string_contains "$output" "REVIVAL_PROTOCOL_OK"

    fixture="$ACCEPT_ROOT/revival-protocol-fixture"
    mkdir -p "$fixture/compass" "$fixture/compass/docs" "$fixture/compass/knowledge" "$fixture/loom/dispatcher" "$fixture/references" "$fixture/.github"
    cp "$REDCAP_ROOT/compass/soul.md" "$fixture/compass/soul.md"
    cp "$REDCAP_ROOT/compass/knowledge/index.md" "$fixture/compass/knowledge/index.md"
    if [[ -f "$REDCAP_ROOT/AGENTS.md" ]]; then
        cp "$REDCAP_ROOT/AGENTS.md" "$fixture/AGENTS.md"
    fi
    cp "$REDCAP_ROOT/CLAUDE.md" "$fixture/CLAUDE.md"
    cp "$REDCAP_ROOT/GEMINI.md" "$fixture/GEMINI.md"
    cp "$REDCAP_ROOT/.github/copilot-instructions.md" "$fixture/.github/copilot-instructions.md"
    cp "$REDCAP_ROOT/loom/dispatcher/reload-rules.yaml" "$fixture/loom/dispatcher/reload-rules.yaml"
    cp "$REDCAP_ROOT/references/hook-standards.md" "$fixture/references/hook-standards.md"
    cp "$REDCAP_ROOT/references/execution-guarantees.json" "$fixture/references/execution-guarantees.json"

    python3 - "$fixture/compass/soul.md" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace("redcap-execution-guarantee-check.sh", "redcap-execution-guarantee-missing.sh")
path.write_text(text, encoding="utf-8")
PY

    set +e
    stale_output="$(bash "$REDCAP_ROOT/compass/tools/redcap-revival-check.sh" "$fixture" 2>&1)"
    stale_status=$?
    set -e
    [[ "$stale_status" -ne 0 ]] || fail "stale revival protocol fixture unexpectedly passed"
    assert_string_contains "$stale_output" "redcap-execution-guarantee-check.sh"
}

run_diagnose_overview_case() {
    local output

    log "case: diagnose-overview"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-diagnose.sh" "$REDCAP_ROOT/.dev-task.md")"
    assert_string_contains "$output" "REDCAP_DIAGNOSE"
    assert_string_contains "$output" "## 诊断门禁"
    assert_string_contains "$output" "[ok] closeout-rescue-audit"
    assert_string_contains "$output" "[ok] docs-catalog"
    assert_string_contains "$output" "[ok] knowledge-index"
    assert_string_contains "$output" "[ok] overlay-governance"
    assert_string_contains "$output" "[ok] state-machine-contract"
    assert_string_contains "$output" "[ok] token-risk-audit"
    assert_string_contains "$output" "[ok] tracking-health"
    assert_string_contains "$output" "[ok] layerb-lifecycle-contract"
    assert_string_contains "$output" "[ok] layerb-closeout-runtime"
    assert_string_contains "$output" "[ok] contributing-ia"
    assert_string_contains "$output" "[ok] review-tracks"
    assert_string_contains "$output" "[ok] hook-contract"
    assert_string_contains "$output" "[ok] runtime-helper"
    assert_string_contains "$output" "[ok] cli-console-mirror"
    assert_string_contains "$output" "DIAGNOSE_OK"
}

run_acceptance_index_check_case() {
    local output find_output

    log "case: acceptance-index-check"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-acceptance-index.sh" check)"
    assert_string_contains "$output" "ACCEPTANCE_INDEX_OK"
    assert_string_contains "$output" "do not bulk-read"

    find_output="$(bash "$REDCAP_ROOT/compass/tools/redcap-acceptance-index.sh" find docs-catalog)"
    assert_string_contains "$find_output" "ACCEPTANCE_INDEX_FIND"
    assert_string_contains "$find_output" "docs-catalog-check"
}

run_token_risk_audit_case() {
    local output fixture stale_output stale_status

    log "case: token-risk-audit"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-token-risk-audit.sh")"
    assert_string_contains "$output" "TOKEN_RISK_AUDIT_OK"
    assert_string_contains "$output" "entry_auto_import_large_files=none"
    assert_string_contains "$output" "redcap-multi-session-acceptance.sh"

    fixture="$ACCEPT_ROOT/token-risk-fixture"
    mkdir -p "$fixture"
    init_temp_git_repo "$fixture"
    cp -R "$REDCAP_ROOT/CLAUDE.md" "$fixture/CLAUDE.md"
    cp -R "$REDCAP_ROOT/GEMINI.md" "$fixture/GEMINI.md"
    mkdir -p "$fixture/.github" "$fixture/compass/tools" "$fixture/compass/docs" "$fixture/compass/knowledge"
    cp "$REDCAP_ROOT/.github/copilot-instructions.md" "$fixture/.github/copilot-instructions.md"
    cp "$REDCAP_ROOT/.gitignore" "$fixture/.gitignore"
    cp "$REDCAP_ROOT/compass/tools/redcap-token-risk-audit.sh" "$fixture/compass/tools/redcap-token-risk-audit.sh"
    cp "$REDCAP_ROOT/compass/tools/redcap-docs-catalog.sh" "$fixture/compass/tools/redcap-docs-catalog.sh"
    cp "$REDCAP_ROOT/compass/tools/redcap-knowledge-index-check.sh" "$fixture/compass/tools/redcap-knowledge-index-check.sh"
    cp "$REDCAP_ROOT/compass/tools/redcap-acceptance-index.sh" "$fixture/compass/tools/redcap-acceptance-index.sh"
    cp "$REDCAP_ROOT/compass/tools/redcap-contributing-ia-check.sh" "$fixture/compass/tools/redcap-contributing-ia-check.sh"
    cp "$REDCAP_ROOT/compass/CONTRIBUTING.core.md" "$fixture/compass/CONTRIBUTING.core.md"
    chmod +x "$fixture/compass/tools/redcap-token-risk-audit.sh"
    git -C "$fixture" add . >/dev/null
    git -C "$fixture" commit --quiet -m "token risk fixture"
    printf '\n@compass/CONTRIBUTING.md\n' >>"$fixture/CLAUDE.md"

    set +e
    stale_output="$(bash "$fixture/compass/tools/redcap-token-risk-audit.sh" 2>&1)"
    stale_status=$?
    set -e
    [[ "$stale_status" -ne 0 ]] || fail "bad token-risk fixture unexpectedly passed"
    assert_string_contains "$stale_output" "auto-imports large file"
}

run_contributing_ia_check_case() {
    local output fixture stale_output stale_status

    log "case: contributing-ia-check"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-contributing-ia-check.sh")"
    assert_string_contains "$output" "CONTRIBUTING_IA_OK"

    fixture="$ACCEPT_ROOT/contributing-ia-fixture"
    mkdir -p "$fixture/.github" "$fixture/compass/tools" "$fixture/references" "$fixture/compass"
    cp "$REDCAP_ROOT/CLAUDE.md" "$fixture/CLAUDE.md"
    cp "$REDCAP_ROOT/GEMINI.md" "$fixture/GEMINI.md"
    cp "$REDCAP_ROOT/.github/copilot-instructions.md" "$fixture/.github/copilot-instructions.md"
    cp "$REDCAP_ROOT/compass/CONTRIBUTING.md" "$fixture/compass/CONTRIBUTING.md"
    cp "$REDCAP_ROOT/compass/CONTRIBUTING.core.md" "$fixture/compass/CONTRIBUTING.core.md"
    cp "$REDCAP_ROOT/compass/tools/redcap-on-stop-review.sh" "$fixture/compass/tools/redcap-on-stop-review.sh"
    cp "$REDCAP_ROOT/compass/tools/redcap-token-risk-audit.sh" "$fixture/compass/tools/redcap-token-risk-audit.sh"
    cp "$REDCAP_ROOT/compass/tools/redcap-contributing-ia-check.sh" "$fixture/compass/tools/redcap-contributing-ia-check.sh"
    cp "$REDCAP_ROOT/references/review-tracks.json" "$fixture/references/review-tracks.json"
    printf '\n@compass/CONTRIBUTING.md\n' >>"$fixture/CLAUDE.md"
    set +e
    stale_output="$(bash "$fixture/compass/tools/redcap-contributing-ia-check.sh" 2>&1)"
    stale_status=$?
    set -e
    [[ "$stale_status" -ne 0 ]] || fail "bad contributing IA fixture unexpectedly passed"
    assert_string_contains "$stale_output" "must not auto-import large file"
}

run_review_tracks_check_case() {
    local output

    log "case: review-tracks-check"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-review-tracks-check.sh")"
    assert_string_contains "$output" "REVIEW_TRACKS_OK"
}

run_hook_contract_check_case() {
    local output

    log "case: hook-contract-check"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-hook-contract-check.sh")"
    assert_string_contains "$output" "HOOK_CONTRACT_OK"
}

run_runtime_helper_check_case() {
    local output

    log "case: runtime-helper-check"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-runtime-helper-check.sh")"
    assert_string_contains "$output" "RUNTIME_HELPER_OK"
}

run_cli_console_mirror_check_case() {
    local output

    log "case: cli-console-mirror-check"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-cli-console-mirror-check.sh")"
    assert_string_contains "$output" "CLI_CONSOLE_MIRROR_OK"
}

run_state_machine_contract_check_case() {
    local output fixture stale_output stale_status

    log "case: state-machine-contract-check"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-state-machine-check.sh")"
    assert_string_contains "$output" "STATE_MACHINE_CONTRACT_OK"

    fixture="$ACCEPT_ROOT/state-machine-contract-fixture"
    mkdir -p "$fixture/compass/tools" "$fixture/loom/dispatcher" "$fixture/references"
    cp "$REDCAP_ROOT/compass/tools/redcap-state-machine-check.sh" "$fixture/compass/tools/redcap-state-machine-check.sh"
    cp "$REDCAP_ROOT/compass/tools/redcap-check-state.sh" "$fixture/compass/tools/redcap-check-state.sh"
    cp "$REDCAP_ROOT/loom/dispatcher/state-machine.md" "$fixture/loom/dispatcher/state-machine.md"
    cp "$REDCAP_ROOT/references/communication-protocol.md" "$fixture/references/communication-protocol.md"
    chmod +x "$fixture/compass/tools/redcap-state-machine-check.sh"
    python3 - "$fixture/compass/tools/redcap-check-state.sh" <<'PY'
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace("    'DEGRADED',\n", "")
path.write_text(text, encoding="utf-8")
PY

    set +e
    stale_output="$(bash "$fixture/compass/tools/redcap-state-machine-check.sh" 2>&1)"
    stale_status=$?
    set -e
    [[ "$stale_status" -ne 0 ]] || fail "bad state-machine contract fixture unexpectedly passed"
    assert_string_contains "$stale_output" "documented states missing"
}

run_on_qa_pass_blocks_inconsistent_state_case() {
    local fixture output status

    log "case: on-qa-pass-blocks-inconsistent-state"

    fixture="$ACCEPT_ROOT/on-qa-pass-state-fixture"
    mkdir -p "$fixture/compass/tools" "$fixture/开发手册/.workflow"
    cp "$REDCAP_ROOT/compass/tools/redcap-check-state.sh" "$fixture/compass/tools/redcap-check-state.sh"
    cp "$REDCAP_ROOT/compass/tools/redcap-on-qa-pass.sh" "$fixture/compass/tools/redcap-on-qa-pass.sh"
    chmod +x "$fixture/compass/tools/redcap-check-state.sh" "$fixture/compass/tools/redcap-on-qa-pass.sh"

    cat >"$fixture/开发手册/.workflow/state.yaml" <<'EOF'
project: "fixture-project"
current_state: "QA_PASS"
iteration: 1
current_step: 2
current_step_name: "功能完整"
total_steps: 2
current_role:
  name: "qa"
  agent: "dispatcher-degraded"
  session_id: null
  started_at: "2026-04-21T00:00:00Z"
  retry_count: 0
history:
  - role: "product-manager"
    agent: "dispatcher-degraded"
    session_id: null
    status: "completed"
    step: 1
    finished_at: "2026-04-21T00:00:00Z"
degraded_mode: false
EOF

    set +e
    output="$(bash "$fixture/compass/tools/redcap-check-state.sh" "$fixture/开发手册" 2>&1)"
    status=$?
    set -e
    [[ "$status" -eq 2 ]] || fail "invalid state fixture should return 2 from redcap-check-state.sh"
    assert_string_contains "$output" "缺少 purpose 字段"

    set +e
    output="$(bash "$fixture/compass/tools/redcap-on-qa-pass.sh" "$fixture" test fixture "blocked by invalid state" 2>&1)"
    status=$?
    set -e
    [[ "$status" -eq 3 ]] || fail "on-qa-pass should block on invalid state fixture"
    assert_string_contains "$output" "state.yaml 一致性校验未通过"
}

run_spec_registry_validates_repo_case() {
    log "case: spec-registry-validates-repo"

    bash "$REDCAP_ROOT/compass/tools/redcap-spec-check.sh" "$REDCAP_ROOT" >/dev/null
}

run_spec_check_propagates_control_gate_failures_case() {
    local repo output status failing_gate expected_message

    log "case: spec-check-propagates-control-gate-failures"

    for failing_gate in docs-catalog docs-retention execution-guarantee knowledge-index overlay-governance state-machine token-risk contributing-ia review-tracks hook-contract runtime-helper cli-console revival; do
        repo="$ACCEPT_ROOT/spec-check-control-gate-fixture-$failing_gate"
        create_spec_registry_fixture "$repo"
        mkdir -p "$repo/compass/tools" "$repo/compass/docs"
        cp "$REDCAP_ROOT/compass/tools/redcap-spec-check.sh" "$repo/compass/tools/redcap-spec-check.sh"

cat >"$repo/compass/tools/redcap-docs-catalog.sh" <<EOF
#!/usr/bin/env bash
if [[ "$failing_gate" == "docs-catalog" && "\${1:-}" == "check" ]]; then
    echo "fixture docs catalog failure" >&2
    exit 37
fi
if [[ "$failing_gate" == "docs-retention" && "\${1:-}" == "retention-check" ]]; then
    echo "fixture docs retention failure" >&2
    exit 37
fi
exit 0
EOF

        cat >"$repo/compass/tools/redcap-execution-guarantee-check.sh" <<EOF
#!/usr/bin/env bash
if [[ "$failing_gate" == "execution-guarantee" ]]; then
    echo "fixture execution guarantee failure" >&2
    exit 37
fi
exit 0
EOF

        cat >"$repo/compass/tools/redcap-revival-check.sh" <<EOF
#!/usr/bin/env bash
if [[ "$failing_gate" == "revival" ]]; then
    echo "fixture revival failure" >&2
    exit 37
fi
exit 0
EOF

        cat >"$repo/compass/tools/redcap-knowledge-index-check.sh" <<EOF
#!/usr/bin/env bash
if [[ "$failing_gate" == "knowledge-index" ]]; then
    echo "fixture knowledge index failure" >&2
    exit 37
fi
exit 0
EOF

        cat >"$repo/compass/tools/redcap-overlay-governance-check.sh" <<EOF
#!/usr/bin/env bash
if [[ "$failing_gate" == "overlay-governance" ]]; then
    echo "fixture overlay governance failure" >&2
    exit 37
fi
exit 0
EOF

        cat >"$repo/compass/tools/redcap-state-machine-check.sh" <<EOF
#!/usr/bin/env bash
if [[ "$failing_gate" == "state-machine" ]]; then
    echo "fixture state machine failure" >&2
    exit 37
fi
exit 0
EOF

        cat >"$repo/compass/tools/redcap-token-risk-audit.sh" <<EOF
#!/usr/bin/env bash
if [[ "$failing_gate" == "token-risk" ]]; then
    echo "fixture token risk failure" >&2
    exit 37
fi
exit 0
EOF

        cat >"$repo/compass/tools/redcap-contributing-ia-check.sh" <<EOF
#!/usr/bin/env bash
if [[ "$failing_gate" == "contributing-ia" ]]; then
    echo "fixture contributing IA failure" >&2
    exit 37
fi
exit 0
EOF

        cat >"$repo/compass/tools/redcap-review-tracks-check.sh" <<EOF
#!/usr/bin/env bash
if [[ "$failing_gate" == "review-tracks" ]]; then
    echo "fixture review tracks failure" >&2
    exit 37
fi
exit 0
EOF

        cat >"$repo/compass/tools/redcap-hook-contract-check.sh" <<EOF
#!/usr/bin/env bash
if [[ "$failing_gate" == "hook-contract" ]]; then
    echo "fixture hook contract failure" >&2
    exit 37
fi
exit 0
EOF

        cat >"$repo/compass/tools/redcap-runtime-helper-check.sh" <<EOF
#!/usr/bin/env bash
if [[ "$failing_gate" == "runtime-helper" ]]; then
    echo "fixture runtime helper failure" >&2
    exit 37
fi
exit 0
EOF

        cat >"$repo/compass/tools/redcap-cli-console-mirror-check.sh" <<EOF
#!/usr/bin/env bash
if [[ "$failing_gate" == "cli-console" ]]; then
    echo "fixture cli console failure" >&2
    exit 37
fi
exit 0
EOF

        chmod +x "$repo/compass/tools/redcap-spec-check.sh" \
            "$repo/compass/tools/redcap-docs-catalog.sh" \
            "$repo/compass/tools/redcap-execution-guarantee-check.sh" \
            "$repo/compass/tools/redcap-knowledge-index-check.sh" \
            "$repo/compass/tools/redcap-overlay-governance-check.sh" \
            "$repo/compass/tools/redcap-state-machine-check.sh" \
            "$repo/compass/tools/redcap-token-risk-audit.sh" \
            "$repo/compass/tools/redcap-contributing-ia-check.sh" \
            "$repo/compass/tools/redcap-review-tracks-check.sh" \
            "$repo/compass/tools/redcap-hook-contract-check.sh" \
            "$repo/compass/tools/redcap-runtime-helper-check.sh" \
            "$repo/compass/tools/redcap-cli-console-mirror-check.sh" \
            "$repo/compass/tools/redcap-revival-check.sh"

        case "$failing_gate" in
            docs-catalog) expected_message="docs catalog check failed" ;;
            docs-retention) expected_message="docs retention check failed" ;;
            execution-guarantee) expected_message="execution guarantee check failed" ;;
            knowledge-index) expected_message="knowledge index check failed" ;;
            overlay-governance) expected_message="overlay governance check failed" ;;
            state-machine) expected_message="state machine contract check failed" ;;
            token-risk) expected_message="token risk audit failed" ;;
            contributing-ia) expected_message="contributing IA check failed" ;;
            review-tracks) expected_message="review tracks check failed" ;;
            hook-contract) expected_message="hook contract check failed" ;;
            runtime-helper) expected_message="runtime helper check failed" ;;
            cli-console) expected_message="cli console mirror check failed" ;;
            revival) expected_message="revival check failed" ;;
        esac

        set +e
        output="$(bash "$repo/compass/tools/redcap-spec-check.sh" "$repo" 2>&1)"
        status=$?
        set -e
        [[ "$status" -ne 0 ]] || fail "spec-check did not propagate $failing_gate failure"
        assert_string_contains "$output" "$expected_message"
    done
}

create_spec_registry_fixture() {
    local fixture_root="$1"

    python3 - "$REDCAP_ROOT" "$fixture_root" <<'PY'
import json
import pathlib
import shutil
import sys

src = pathlib.Path(sys.argv[1])
dst = pathlib.Path(sys.argv[2])
dst.mkdir(parents=True, exist_ok=True)

registry = json.loads((src / "references/spec-registry.json").read_text(encoding="utf-8"))
files = {
    "references/spec-registry.json",
    "references/spec-lifecycle-policy.json",
    "references/spec-contribution-standard.md",
    "compass/docs/index.yaml",
}

for entry in registry["specs"]:
    files.add(entry["path"])
    for control_path in entry.get("paired_control_paths", []):
        files.add(control_path)

for rel in sorted(files):
    src_path = src / rel
    dst_path = dst / rel
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    if src_path.is_file():
        shutil.copy2(src_path, dst_path)
    else:
        dst_path.write_text("# fixture\n", encoding="utf-8")
PY
}

run_spec_check_rejects_superseded_outside_archive_case() {
    local repo output status

    log "case: spec-check-rejects-superseded-outside-archive"

    repo="$ACCEPT_ROOT/spec-check-rejects-superseded-outside-archive/repo"
    create_spec_registry_fixture "$repo"

    python3 - "$repo" <<'PY'
import json
import pathlib
import sys

repo = pathlib.Path(sys.argv[1])
registry_path = repo / "references/spec-registry.json"
registry = json.loads(registry_path.read_text(encoding="utf-8"))
registry["specs"][0]["status"] = "superseded"
registry["specs"][0]["replaced_by"] = registry["specs"][1]["path"]
registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

    set +e
    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-spec-check.sh" "$repo" 2>&1)"
    status=$?
    set -e

    [[ "$status" -ne 0 ]] || fail "superseded spec unexpectedly remained valid outside archive"
    assert_string_contains "$output" "spec status superseded cannot live under active root"
}

run_spec_check_requires_replaced_by_case() {
    local repo output status

    log "case: spec-check-requires-replaced-by"

    repo="$ACCEPT_ROOT/spec-check-requires-replaced-by/repo"
    create_spec_registry_fixture "$repo"

    python3 - "$repo" <<'PY'
import json
import pathlib
import shutil
import sys

repo = pathlib.Path(sys.argv[1])
registry_path = repo / "references/spec-registry.json"
registry = json.loads(registry_path.read_text(encoding="utf-8"))
entry = registry["specs"][0]
old_rel = entry["path"]
new_rel = "compass/docs/archive/specs/" + pathlib.PurePosixPath(old_rel).name
old_path = repo / old_rel
new_path = repo / new_rel
new_path.parent.mkdir(parents=True, exist_ok=True)
shutil.move(str(old_path), str(new_path))
entry["path"] = new_rel
entry["status"] = "superseded"
entry.pop("replaced_by", None)
registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

    set +e
    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-spec-check.sh" "$repo" 2>&1)"
    status=$?
    set -e

    [[ "$status" -ne 0 ]] || fail "superseded spec unexpectedly passed without replaced_by"
    assert_string_contains "$output" "superseded spec missing replaced_by"
}

run_spec_check_rejects_invalid_role_case() {
    local repo output status

    log "case: spec-check-rejects-invalid-role"

    repo="$ACCEPT_ROOT/spec-check-rejects-invalid-role/repo"
    create_spec_registry_fixture "$repo"

    python3 - "$repo" <<'PY'
import json
import pathlib
import sys

repo = pathlib.Path(sys.argv[1])
registry_path = repo / "references/spec-registry.json"
registry = json.loads(registry_path.read_text(encoding="utf-8"))
registry["specs"][0]["role"] = "invalid-role"
registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

    set +e
    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-spec-check.sh" "$repo" 2>&1)"
    status=$?
    set -e

    [[ "$status" -ne 0 ]] || fail "invalid spec role unexpectedly passed"
    assert_string_contains "$output" "spec registry entry uses unsupported role"
}

run_spec_check_rejects_replacement_cycle_case() {
    local repo output status

    log "case: spec-check-rejects-replacement-cycle"

    repo="$ACCEPT_ROOT/spec-check-rejects-replacement-cycle/repo"
    create_spec_registry_fixture "$repo"

    python3 - "$repo" <<'PY'
import json
import pathlib
import sys

repo = pathlib.Path(sys.argv[1])
registry_path = repo / "references/spec-registry.json"
registry = json.loads(registry_path.read_text(encoding="utf-8"))
registry["specs"][0]["replaced_by"] = registry["specs"][1]["path"]
registry["specs"][1]["replaced_by"] = registry["specs"][0]["path"]
registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

    set +e
    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-spec-check.sh" "$repo" 2>&1)"
    status=$?
    set -e

    [[ "$status" -ne 0 ]] || fail "replacement cycle unexpectedly passed"
    assert_string_contains "$output" "spec replacement chain contains cycle"
}

run_spec_check_accepts_archived_superseded_case() {
    local repo

    log "case: spec-check-accepts-archived-superseded"

    repo="$ACCEPT_ROOT/spec-check-accepts-archived-superseded/repo"
    create_spec_registry_fixture "$repo"

    python3 - "$repo" <<'PY'
import json
import pathlib
import shutil
import sys

repo = pathlib.Path(sys.argv[1])
registry_path = repo / "references/spec-registry.json"
registry = json.loads(registry_path.read_text(encoding="utf-8"))
entry = registry["specs"][0]
replacement = registry["specs"][1]["path"]
old_rel = entry["path"]
new_rel = "compass/docs/archive/specs/" + pathlib.PurePosixPath(old_rel).name
old_path = repo / old_rel
new_path = repo / new_rel
new_path.parent.mkdir(parents=True, exist_ok=True)
shutil.move(str(old_path), str(new_path))
entry["path"] = new_rel
entry["status"] = "superseded"
entry["replaced_by"] = replacement
registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

    bash "$REDCAP_ROOT/compass/tools/redcap-spec-check.sh" "$repo" >/dev/null
}

run_host_workboard_backlog_anchor_case() {
    local workboard expected_backlog_item

    log "case: host-workboard-backlog-anchor"

    workboard="$ACCEPT_ROOT/host-workboard-backlog-anchor/plan.md"
    mkdir -p "$(dirname "$workboard")"
    printf '# backlog anchor fixture\n' >"$workboard"
    expected_backlog_item=$(awk -F': ' '/^backlog_item:/ {print $2; exit}' "$REDCAP_ROOT/.dev-task.md")

    bash "$REDCAP_ROOT/compass/tools/redcap-host-workboard-sync.sh" sync "$workboard" "$REDCAP_ROOT/.dev-task.md"

    assert_contains "$workboard" "- backlog_source: references/backlogs/framework-upgrade.json"
    assert_contains "$workboard" "- backlog_id: framework-upgrade"
    assert_contains "$workboard" "- backlog_item: $expected_backlog_item"
}

run_cli_console_mirror_overwrites_case() {
    local temp_console temp_source

    log "case: cli-console-mirror-overwrites"

    temp_console="$ACCEPT_ROOT/cli-console-mirror/cli_console.md"
    temp_source="$ACCEPT_ROOT/cli-console-mirror/source.txt"
    mkdir -p "$(dirname "$temp_console")"

    printf 'old content\n' >"$temp_console"
    printf 'new mirrored content\nsecond line\n' >"$temp_source"

    REDCAP_CLI_CONSOLE_PATH="$temp_console" bash "$REDCAP_ROOT/compass/tools/redcap-cli-console-mirror.sh" write "$temp_source"

    assert_eq "$(cat "$temp_console")" "$(cat "$temp_source")"
}

run_feishu_duplex_window_queue_case() {
    local fixture_root fake_bin fake_state config_path state_dir output window_id pending_id scan_count pending_count sent_count

    log "case: feishu-duplex-window-queue"

    fixture_root="$ACCEPT_ROOT/feishu-duplex-window-queue"
    fake_bin="$fixture_root/bin/lark-cli"
    fake_state="$fixture_root/fake-lark-state.json"
    config_path="$fixture_root/feishu-config.json"
    state_dir="$fixture_root/runtime-state"

    mkdir -p "$(dirname "$fake_bin")" "$state_dir"

    cat >"$fake_bin" <<'PYEOF'
#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

state_path = Path(os.environ["FAKE_LARK_STATE"])
if state_path.exists():
    state = json.loads(state_path.read_text(encoding="utf-8"))
else:
    state = {"next_id": 1, "messages": []}


def save_state():
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def next_message_id(prefix="om_fake"):
    value = f"{prefix}_{state['next_id']}"
    state["next_id"] += 1
    return value


def arg_value(flag: str, default: str = "") -> str:
    if flag not in args:
        return default
    index = args.index(flag)
    if index + 1 >= len(args):
        return default
    return args[index + 1]


args = sys.argv[1:]
if args and args[0] == "--profile" and len(args) >= 2:
    args = args[2:]

if args[:2] == ["im", "+messages-send"]:
    dry_run = "--dry-run" in args
    chat_id = arg_value("--chat-id", "oc_test")
    text = arg_value("--text")
    message_id = next_message_id()
    if not dry_run:
        state["messages"].append(
            {
                "content": text,
                "create_time": f"2026-04-16 00:{state['next_id']:02d}",
                "deleted": False,
                "message_id": message_id,
                "msg_type": "text",
                "sender": {
                    "id": "cli_test",
                    "id_type": "app_id",
                    "sender_type": "app",
                    "tenant_key": "tenant_test",
                },
                "updated": False,
            }
        )
        save_state()
    print(json.dumps({"ok": True, "identity": "bot", "data": {"chat_id": chat_id, "create_time": "2026-04-16 00:00:00", "message_id": message_id}}, ensure_ascii=False))
    sys.exit(0)

if args[:2] == ["im", "+messages-reply"]:
    text = arg_value("--text")
    message_id = next_message_id("om_reply")
    state["messages"].append(
        {
            "content": text,
            "create_time": f"2026-04-16 00:{state['next_id']:02d}",
            "deleted": False,
            "message_id": message_id,
            "msg_type": "text",
            "sender": {
                "id": "cli_test",
                "id_type": "app_id",
                "sender_type": "app",
                "tenant_key": "tenant_test",
            },
            "updated": False,
        }
    )
    save_state()
    print(json.dumps({"ok": True, "identity": "bot", "data": {"message_id": message_id}}, ensure_ascii=False))
    sys.exit(0)

if args[:2] == ["im", "+chat-messages-list"]:
    page_size = int(arg_value("--page-size", "50"))
    messages = list(reversed(state["messages"]))[:page_size]
    print(json.dumps({"ok": True, "identity": "bot", "data": {"has_more": False, "messages": messages, "page_token": "", "total": len(messages)}}, ensure_ascii=False))
    sys.exit(0)

print(json.dumps({"ok": False, "error": {"message": "unsupported fake lark-cli args", "args": args}}, ensure_ascii=False))
sys.exit(1)
PYEOF
    chmod +x "$fake_bin"

    cat >"$config_path" <<EOF
{
  "notify_enabled": true,
  "transport": "lark_cli_dm",
  "lark_cli_bin": "$fake_bin",
  "lark_cli_profile": "test-profile",
  "lark_chat_id": "oc_test_chat",
  "lark_identity": "bot",
  "fast_poll_seconds": 1,
  "fast_poll_window_seconds": 1,
  "slow_poll_seconds": 1,
  "followup_timeout_seconds": 30,
  "notify_dedup_seconds": 300,
  "history_limit": 50,
  "known_id_limit": 50
}
EOF

    output="$(
        FAKE_LARK_STATE="$fake_state" \
        REDCAP_FEISHU_CONFIG_PATH="$config_path" \
        REDCAP_FEISHU_STATE_DIR="$state_dir" \
        python3 "$REDCAP_ROOT/compass/tools/feishu-notifier.py" notify "任务完成" --project redcap --window-type followup --no-background-watch 2>&1
    )"
    window_id=$(printf '%s\n' "$output" | sed -n 's/^FEISHU_WINDOW_ID=//p' | tail -n 1)
    [[ -n "$window_id" ]] || fail "notify followup did not emit window id"
    assert_exists "$state_dir/active-window.json"

    output="$(
        FAKE_LARK_STATE="$fake_state" \
        REDCAP_FEISHU_CONFIG_PATH="$config_path" \
        REDCAP_FEISHU_STATE_DIR="$state_dir" \
        python3 "$REDCAP_ROOT/compass/tools/feishu-notifier.py" notify "任务完成" --project redcap --window-type followup --no-background-watch 2>&1
    )"
    assert_string_contains "$output" "FEISHU_DEDUPED_WINDOW_ID=$window_id"
    sent_count="$(python3 - "$fake_state" <<'PY'
import json
import pathlib
import sys
state = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
print(sum(1 for message in state["messages"] if message.get("sender", {}).get("sender_type") == "app"))
PY
)"
    assert_eq "$sent_count" "1"

    python3 - "$fake_state" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
state = json.loads(path.read_text(encoding="utf-8"))
state["messages"].append(
    {
        "content": "继续下一步",
        "create_time": "2026-04-16 00:30",
        "deleted": False,
        "message_id": "om_user_1",
        "msg_type": "text",
        "sender": {
            "id": "user_test",
            "id_type": "open_id",
            "sender_type": "user",
            "tenant_key": "tenant_test",
        },
        "updated": False,
    }
)
path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
PY

    output="$(
        FAKE_LARK_STATE="$fake_state" \
        REDCAP_FEISHU_CONFIG_PATH="$config_path" \
        REDCAP_FEISHU_STATE_DIR="$state_dir" \
        python3 "$REDCAP_ROOT/compass/tools/feishu-notifier.py" watch-window "$window_id" 2>&1
    )"
    assert_string_contains "$output" "继续下一步"
    assert_not_exists "$state_dir/active-window.json"

    pending_count="$(
        FAKE_LARK_STATE="$fake_state" \
        REDCAP_FEISHU_CONFIG_PATH="$config_path" \
        REDCAP_FEISHU_STATE_DIR="$state_dir" \
        python3 "$REDCAP_ROOT/compass/tools/feishu-notifier.py" pending-count
    )"
    assert_eq "$pending_count" "1"

    pending_id="$(python3 - "$state_dir/pending-items.json" <<'PY'
import json
import pathlib
import sys

items = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
print(items[0]["id"])
PY
)"
    [[ -n "$pending_id" ]] || fail "pending item id missing"

    FAKE_LARK_STATE="$fake_state" \
    REDCAP_FEISHU_CONFIG_PATH="$config_path" \
    REDCAP_FEISHU_STATE_DIR="$state_dir" \
    python3 "$REDCAP_ROOT/compass/tools/feishu-notifier.py" pending-promote "$pending_id" >/dev/null

    pending_count="$(
        FAKE_LARK_STATE="$fake_state" \
        REDCAP_FEISHU_CONFIG_PATH="$config_path" \
        REDCAP_FEISHU_STATE_DIR="$state_dir" \
        python3 "$REDCAP_ROOT/compass/tools/feishu-notifier.py" pending-count
    )"
    assert_eq "$pending_count" "0"

    python3 - "$fake_state" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
state = json.loads(path.read_text(encoding="utf-8"))
state["messages"].append(
    {
        "content": "窗口外消息",
        "create_time": "2026-04-16 00:31",
        "deleted": False,
        "message_id": "om_user_2",
        "msg_type": "text",
        "sender": {
            "id": "user_test",
            "id_type": "open_id",
            "sender_type": "user",
            "tenant_key": "tenant_test",
        },
        "updated": False,
    }
)
path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
PY

    scan_count="$(
        FAKE_LARK_STATE="$fake_state" \
        REDCAP_FEISHU_CONFIG_PATH="$config_path" \
        REDCAP_FEISHU_STATE_DIR="$state_dir" \
        python3 "$REDCAP_ROOT/compass/tools/feishu-notifier.py" pending-scan
    )"
    assert_eq "$scan_count" "1"

    pending_count="$(
        FAKE_LARK_STATE="$fake_state" \
        REDCAP_FEISHU_CONFIG_PATH="$config_path" \
        REDCAP_FEISHU_STATE_DIR="$state_dir" \
        python3 "$REDCAP_ROOT/compass/tools/feishu-notifier.py" pending-count
    )"
    assert_eq "$pending_count" "1"
}

run_overlay_skill_handoff_stays_native_case() {
    log "case: overlay-skill-handoff-stays-native"

    assert_contains "$REDCAP_ROOT/SKILL.md" "缺少宿主下游 skill 不是合法 blocker"
    assert_contains "$REDCAP_ROOT/compass/CONTRIBUTING.md" "缺少这类宿主下游 skill 不是合法 blocker"
    assert_contains "$REDCAP_ROOT/ARCHITECTURE.md" "其自带的下游 handoff（如 writing-plans）也不能反向接管 RedCap-native 主流程"
    assert_contains "$REDCAP_ROOT/references/agent-constraints.md" "下游 skill 当成 blocker"
}

run_overlay_governance_check_case() {
    local output fixture stale_output stale_status

    log "case: overlay-governance-check"

    output="$(bash "$REDCAP_ROOT/compass/tools/redcap-overlay-governance-check.sh")"
    assert_string_contains "$output" "OVERLAY_GOVERNANCE_OK"

    fixture="$ACCEPT_ROOT/overlay-governance-fixture"
    mkdir -p "$fixture/compass" "$fixture/references" "$fixture/compass/docs/specs" "$fixture/compass/tools"
    cp "$REDCAP_ROOT/compass/tools/redcap-overlay-governance-check.sh" "$fixture/compass/tools/redcap-overlay-governance-check.sh"
    cp "$REDCAP_ROOT/SKILL.md" "$fixture/SKILL.md"
    cp "$REDCAP_ROOT/compass/CONTRIBUTING.md" "$fixture/compass/CONTRIBUTING.md"
    cp "$REDCAP_ROOT/references/agent-constraints.md" "$fixture/references/agent-constraints.md"
    cp "$REDCAP_ROOT/compass/docs/specs/2026-04-12-host-skill-overlay-governance-design.md" "$fixture/compass/docs/specs/2026-04-12-host-skill-overlay-governance-design.md"
    chmod +x "$fixture/compass/tools/redcap-overlay-governance-check.sh"
    python3 - "$fixture/references/agent-constraints.md" <<'PY'
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace("brainstorming/澄清习惯", "随便澄清")
path.write_text(text, encoding="utf-8")
PY

    set +e
    stale_output="$(bash "$fixture/compass/tools/redcap-overlay-governance-check.sh" 2>&1)"
    stale_status=$?
    set -e
    [[ "$stale_status" -ne 0 ]] || fail "bad overlay governance fixture unexpectedly passed"
    assert_string_contains "$stale_output" "references/agent-constraints.md missing required pattern"
}

run_all_cases() {
    run_binding_recovery_gate_case
    run_layerb_concurrency_case
    run_copilot_safe_degraded_case
    run_copilot_wrapper_identity_anchor_case
    run_copilot_session_context_rejects_ambiguous_locks_case
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
    run_report_register_replaces_pending_artifact_case
    run_report_register_rejects_traversal_artifact_case
    run_report_register_rejects_symlinked_report_root_case
    run_sessionstart_auto_reconcile_rewrite_case
    run_sessionstart_auto_reconcile_normalizes_absolute_artifact_case
    run_sessionstart_auto_reconcile_clear_case
    run_sessionstart_auto_reconcile_hash_mismatch_case
    run_sessionstart_auto_reconcile_backlog_spec_case
    run_task_complete_guard_triggers_on_complete_case
    run_task_complete_guard_passes_host_to_on_complete_case
    run_task_complete_guard_avoids_ambiguous_reports_case
    run_task_complete_guard_skips_stale_pending_artifact_case
    run_task_complete_guard_normalizes_absolute_pending_anchor_case
    run_on_complete_records_backlog_spec_redlines_case
    run_on_complete_uses_explicit_validator_host_case
    run_on_complete_prefers_binding_host_over_stale_runtime_host_case
    run_pending_closure_clear_restores_on_ledger_failure_case
    run_session_end_clears_all_matching_pending_states_case
    run_session_end_clears_compatible_pending_refresh_case
    run_task_report_check_prefers_anchor_case
    run_task_report_check_allows_marker_anchor_when_uniquely_latest_case
    run_task_report_check_requires_summary_for_untracked_anchor_case
    run_task_report_check_accepts_legacy_pending_anchor_case
    run_task_report_check_rejects_stale_marker_conflict_case
    run_task_report_check_rejects_zero_diff_stale_marker_case
    run_task_report_check_ignores_invalid_pending_artifact_case
    run_task_report_check_ignores_traversal_anchor_case
    run_task_report_check_normalizes_absolute_pending_anchor_case
    run_task_report_check_rejects_symlink_report_escape_case
    run_task_complete_guard_replaces_stale_marker_with_unique_report_case
    run_task_complete_guard_serializes_on_complete_case
    run_task_complete_guard_prunes_stale_lock_case
    run_task_complete_guard_keeps_live_legacy_lock_case
    run_task_complete_guard_prunes_reused_pid_lock_case
    run_task_complete_guard_retries_after_report_change_case
    run_on_stop_review_falls_back_after_timeout_case
    run_on_stop_review_falls_back_after_auth_failure_case
    run_on_stop_review_falls_back_after_auth_failure_with_result_token_case
    run_on_stop_review_falls_back_after_unparseable_success_output_case
    run_on_stop_review_falls_back_after_structured_pass_with_auth_error_line_case
    run_on_stop_review_falls_back_to_codex_after_unavailable_reviewers_case
    run_on_stop_review_prefers_codex_when_best_ranked_case
    run_on_stop_review_prefers_copilot_premium_model_over_lighter_clis_case
    run_on_stop_review_records_unavailable_rate_limit_case
    run_on_stop_review_rejects_invalid_track_structure_case
    run_on_stop_review_skips_prompt_only_reviewer_when_repo_inspection_required_case
    run_on_stop_review_accepts_structured_review_with_auth_terms_case
    run_on_stop_review_accepts_structured_review_with_auth_prose_outside_fence_case
    run_on_stop_review_accepts_structured_review_with_quoted_cli_error_in_stdout_prose_case
    run_on_stop_review_accepts_structured_review_with_quoted_cli_error_block_in_stdout_residual_case
    run_on_stop_review_accepts_lowercase_structured_result_case
    run_on_stop_review_accepts_raw_json_with_stderr_auth_terms_case
    run_on_stop_review_falls_back_after_structured_pass_with_stderr_auth_error_line_case
    run_on_stop_review_falls_back_after_structured_pass_with_stderr_auth_error_and_hint_case
    run_on_stop_review_accepts_structured_review_with_quoted_cli_error_in_stderr_prose_case
    run_on_stop_review_accepts_plain_text_pass_with_fail_closed_case
    run_on_stop_review_accepts_uppercase_fenced_json_case
    run_on_stop_review_accepts_bare_fenced_json_case
    run_on_stop_review_accepts_json_fence_after_nonjson_bare_fence_case
    run_session_end_success_notify_after_clear_case
    run_session_end_notify_timeout_releases_lock_case
    run_session_end_blocked_rewrite_keeps_report_anchor_case
    run_session_end_blocked_rewrite_normalizes_absolute_report_anchor_case
    run_pending_closure_lock_keeps_live_legacy_lock_case
    run_pending_closure_lock_prunes_reused_pid_case
    run_sessionstart_runtime_init_failed_degrades_case
    run_sessionstart_control_gate_failure_degrades_case
    run_runtime_clear_context_clears_probe_pid_case
    run_runtime_claim_parent_fallback_case
    run_artifact_lifecycle_classifier_case
    run_artifact_lifecycle_hook_install_case
    run_artifact_lifecycle_pre_commit_block_case
    run_artifact_lifecycle_pre_commit_allow_case
    run_artifact_lifecycle_rejects_tabbed_path_case
    run_docs_catalog_check_case
    run_docs_catalog_progressive_disclosure_case
    run_docs_retention_check_case
    run_backlog_check_strict_case
    run_current_status_overview_case
    run_tracking_health_overview_case
    run_install_overview_case
    run_execution_guarantees_check_case
    run_knowledge_index_check_case
    run_acceptance_index_check_case
    run_token_risk_audit_case
    run_contributing_ia_check_case
    run_review_tracks_check_case
    run_hook_contract_check_case
    run_runtime_helper_check_case
    run_cli_console_mirror_check_case
    run_revival_protocol_check_case
    run_diagnose_overview_case
    run_state_machine_contract_check_case
    run_on_qa_pass_blocks_inconsistent_state_case
    run_spec_registry_validates_repo_case
    run_spec_check_propagates_control_gate_failures_case
    run_spec_check_rejects_superseded_outside_archive_case
    run_spec_check_requires_replaced_by_case
    run_spec_check_rejects_invalid_role_case
    run_spec_check_rejects_replacement_cycle_case
    run_spec_check_accepts_archived_superseded_case
    run_host_workboard_backlog_anchor_case
    run_cli_console_mirror_overwrites_case
    run_feishu_duplex_window_queue_case
    run_overlay_skill_handoff_stays_native_case
    run_overlay_governance_check_case
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
    copilot-wrapper-identity-anchor)
        run_copilot_wrapper_identity_anchor_case
        ;;
    copilot-session-context-rejects-ambiguous-locks)
        run_copilot_session_context_rejects_ambiguous_locks_case
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
    report-register-accepts-explicit-runtime-env)
        run_report_register_accepts_explicit_runtime_env_case
        ;;
    report-register-rejects-ambiguous-explicit-runtime)
        run_report_register_rejects_ambiguous_explicit_runtime_case
        ;;
    report-register-prefers-live-claim-over-stale-explicit-runtime)
        run_report_register_prefers_live_claim_over_stale_explicit_runtime_case
        ;;
    report-register-rejects-foreign-explicit-runtime)
        run_report_register_rejects_foreign_explicit_runtime_case
        ;;
    report-register-replaces-pending-artifact)
        run_report_register_replaces_pending_artifact_case
        ;;
    report-register-rejects-traversal-artifact)
        run_report_register_rejects_traversal_artifact_case
        ;;
    report-register-rejects-symlinked-report-root)
        run_report_register_rejects_symlinked_report_root_case
        ;;
    sessionstart-auto-reconcile-rewrite)
        run_sessionstart_auto_reconcile_rewrite_case
        ;;
    sessionstart-auto-reconcile-normalizes-absolute-artifact)
        run_sessionstart_auto_reconcile_normalizes_absolute_artifact_case
        ;;
    sessionstart-auto-reconcile-clear)
        run_sessionstart_auto_reconcile_clear_case
        ;;
    sessionstart-auto-reconcile-hash-mismatch)
        run_sessionstart_auto_reconcile_hash_mismatch_case
        ;;
    sessionstart-auto-reconcile-backlog-spec)
        run_sessionstart_auto_reconcile_backlog_spec_case
        ;;
    task-complete-guard-triggers-on-complete|task-complete-guard-triggers-closeout-runtime)
        run_task_complete_guard_triggers_closeout_runtime_case
        ;;
    layerb-closeout-runtime-promise-ledger-blocks)
        run_layerb_closeout_runtime_promise_ledger_blocks_case
        ;;
    layerb-closeout-runtime-prism-acceptance-blocks)
        run_layerb_closeout_runtime_prism_acceptance_blocks_case
        ;;
    prism-acceptance-binding-required)
        run_prism_acceptance_binding_required_case
        ;;
    review-proof-check-accepts-prism-acceptance)
        run_review_proof_check_accepts_prism_acceptance_case
        ;;
    layerb-closeout-runtime-complete-writes-receipt)
        run_layerb_closeout_runtime_complete_writes_receipt_case
        ;;
    layerb-closeout-runtime-session-end-failure-writes-pending)
        run_layerb_closeout_runtime_session_end_failure_writes_pending_case
        ;;
    layerb-closeout-runtime-audit-open-repairs-receipt)
        run_layerb_closeout_runtime_audit_open_repairs_receipt_case
        ;;
    layerb-closeout-runtime-audit-open-blocks-unresolved)
        run_layerb_closeout_runtime_audit_open_blocks_unresolved_case
        ;;
    layerb-closeout-runtime-audit-open-preserves-existing-blockers)
        run_layerb_closeout_runtime_audit_open_preserves_existing_blockers_case
        ;;
    diagnose-auto-repairs-closeout-receipt)
        run_diagnose_auto_repairs_closeout_receipt_case
        ;;
    closeout-cap-root-entry-basic-commands)
        run_closeout_cap_root_entry_basic_commands_case
        ;;
    task-complete-guard-passes-host-to-on-complete)
        run_task_complete_guard_passes_host_to_on_complete_case
        ;;
    task-complete-guard-avoids-ambiguous-reports)
        run_task_complete_guard_avoids_ambiguous_reports_case
        ;;
    task-complete-guard-skips-stale-pending-artifact)
        run_task_complete_guard_skips_stale_pending_artifact_case
        ;;
    task-complete-guard-normalizes-absolute-pending-anchor)
        run_task_complete_guard_normalizes_absolute_pending_anchor_case
        ;;
    on-complete-records-backlog-spec-redlines)
        run_on_complete_records_backlog_spec_redlines_case
        ;;
    on-complete-uses-explicit-validator-host)
        run_on_complete_uses_explicit_validator_host_case
        ;;
    on-complete-prefers-binding-host-over-stale-runtime-host)
        run_on_complete_prefers_binding_host_over_stale_runtime_host_case
        ;;
    pending-closure-clear-restores-on-ledger-failure)
        run_pending_closure_clear_restores_on_ledger_failure_case
        ;;
    session-end-clears-all-matching-pending-states)
        run_session_end_clears_all_matching_pending_states_case
        ;;
    session-end-clears-compatible-pending-refresh)
        run_session_end_clears_compatible_pending_refresh_case
        ;;
    session-end-clears-closeout-runtime-pending)
        run_session_end_clears_closeout_runtime_pending_case
        ;;
    task-report-check-prefers-anchor)
        run_task_report_check_prefers_anchor_case
        ;;
    task-report-check-allows-marker-anchor-when-uniquely-latest)
        run_task_report_check_allows_marker_anchor_when_uniquely_latest_case
        ;;
    task-report-check-allows-pending-anchor-when-uniquely-latest)
        run_task_report_check_allows_pending_anchor_when_uniquely_latest_case
        ;;
    task-report-check-rejects-stale-pending-anchor-conflict)
        run_task_report_check_rejects_stale_pending_anchor_conflict_case
        ;;
    task-report-check-requires-summary-for-untracked-anchor)
        run_task_report_check_requires_summary_for_untracked_anchor_case
        ;;
    task-report-check-accepts-legacy-pending-anchor)
        run_task_report_check_accepts_legacy_pending_anchor_case
        ;;
    task-report-check-rejects-stale-marker-conflict)
        run_task_report_check_rejects_stale_marker_conflict_case
        ;;
    task-report-check-rejects-zero-diff-stale-marker)
        run_task_report_check_rejects_zero_diff_stale_marker_case
        ;;
    task-report-check-ignores-invalid-pending-artifact)
        run_task_report_check_ignores_invalid_pending_artifact_case
        ;;
    task-report-check-ignores-traversal-anchor)
        run_task_report_check_ignores_traversal_anchor_case
        ;;
    task-report-check-normalizes-absolute-pending-anchor)
        run_task_report_check_normalizes_absolute_pending_anchor_case
        ;;
    task-report-check-rejects-symlink-report-escape)
        run_task_report_check_rejects_symlink_report_escape_case
        ;;
    task-complete-guard-replaces-stale-marker-with-unique-report)
        run_task_complete_guard_replaces_stale_marker_with_unique_report_case
        ;;
    task-complete-guard-serializes-on-complete)
        run_task_complete_guard_serializes_on_complete_case
        ;;
    task-complete-guard-prunes-stale-lock)
        run_task_complete_guard_prunes_stale_lock_case
        ;;
    task-complete-guard-keeps-live-legacy-lock)
        run_task_complete_guard_keeps_live_legacy_lock_case
        ;;
    task-complete-guard-prunes-reused-pid-lock)
        run_task_complete_guard_prunes_reused_pid_lock_case
        ;;
    task-complete-guard-retries-after-report-change)
        run_task_complete_guard_retries_after_report_change_case
        ;;
    on-stop-review-falls-back-after-timeout)
        run_on_stop_review_falls_back_after_timeout_case
        ;;
    on-stop-review-falls-back-after-auth-failure)
        run_on_stop_review_falls_back_after_auth_failure_case
        ;;
    on-stop-review-falls-back-after-auth-failure-with-result-token)
        run_on_stop_review_falls_back_after_auth_failure_with_result_token_case
        ;;
    on-stop-review-falls-back-after-unparseable-success-output)
        run_on_stop_review_falls_back_after_unparseable_success_output_case
        ;;
    on-stop-review-falls-back-after-structured-pass-with-auth-error-line)
        run_on_stop_review_falls_back_after_structured_pass_with_auth_error_line_case
        ;;
    on-stop-review-falls-back-to-codex-after-unavailable-reviewers)
        run_on_stop_review_falls_back_to_codex_after_unavailable_reviewers_case
        ;;
    on-stop-review-prefers-codex-when-best-ranked)
        run_on_stop_review_prefers_codex_when_best_ranked_case
        ;;
    on-stop-review-prefers-copilot-premium-model-over-lighter-clis)
        run_on_stop_review_prefers_copilot_premium_model_over_lighter_clis_case
        ;;
    on-stop-review-records-unavailable-rate-limit)
        run_on_stop_review_records_unavailable_rate_limit_case
        ;;
    on-stop-review-rejects-invalid-track-structure)
        run_on_stop_review_rejects_invalid_track_structure_case
        ;;
    on-stop-review-skips-prompt-only-reviewer-when-repo-inspection-required)
        run_on_stop_review_skips_prompt_only_reviewer_when_repo_inspection_required_case
        ;;
    on-stop-review-accepts-structured-review-with-auth-terms)
        run_on_stop_review_accepts_structured_review_with_auth_terms_case
        ;;
    on-stop-review-accepts-structured-review-with-auth-prose-outside-fence)
        run_on_stop_review_accepts_structured_review_with_auth_prose_outside_fence_case
        ;;
    on-stop-review-accepts-structured-review-with-quoted-cli-error-in-stdout-prose)
        run_on_stop_review_accepts_structured_review_with_quoted_cli_error_in_stdout_prose_case
        ;;
    on-stop-review-accepts-structured-review-with-quoted-cli-error-block-in-stdout-residual)
        run_on_stop_review_accepts_structured_review_with_quoted_cli_error_block_in_stdout_residual_case
        ;;
    on-stop-review-accepts-lowercase-structured-result)
        run_on_stop_review_accepts_lowercase_structured_result_case
        ;;
    on-stop-review-accepts-raw-json-with-stderr-auth-terms)
        run_on_stop_review_accepts_raw_json_with_stderr_auth_terms_case
        ;;
    on-stop-review-falls-back-after-structured-pass-with-stderr-auth-error-line)
        run_on_stop_review_falls_back_after_structured_pass_with_stderr_auth_error_line_case
        ;;
    on-stop-review-falls-back-after-structured-pass-with-stderr-auth-error-and-hint)
        run_on_stop_review_falls_back_after_structured_pass_with_stderr_auth_error_and_hint_case
        ;;
    on-stop-review-accepts-structured-review-with-quoted-cli-error-in-stderr-prose)
        run_on_stop_review_accepts_structured_review_with_quoted_cli_error_in_stderr_prose_case
        ;;
    on-stop-review-accepts-plain-text-pass-with-fail-closed)
        run_on_stop_review_accepts_plain_text_pass_with_fail_closed_case
        ;;
    on-stop-review-accepts-uppercase-fenced-json)
        run_on_stop_review_accepts_uppercase_fenced_json_case
        ;;
    on-stop-review-accepts-bare-fenced-json)
        run_on_stop_review_accepts_bare_fenced_json_case
        ;;
    on-stop-review-accepts-json-fence-after-nonjson-bare-fence)
        run_on_stop_review_accepts_json_fence_after_nonjson_bare_fence_case
        ;;
    session-end-success-notify-after-clear)
        run_session_end_success_notify_after_clear_case
        ;;
    session-end-notify-timeout-releases-lock)
        run_session_end_notify_timeout_releases_lock_case
        ;;
    session-end-blocked-rewrite-keeps-report-anchor)
        run_session_end_blocked_rewrite_keeps_report_anchor_case
        ;;
    session-end-blocked-rewrite-normalizes-absolute-report-anchor)
        run_session_end_blocked_rewrite_normalizes_absolute_report_anchor_case
        ;;
    pending-closure-lock-keeps-live-legacy-lock)
        run_pending_closure_lock_keeps_live_legacy_lock_case
        ;;
    pending-closure-lock-prunes-reused-pid)
        run_pending_closure_lock_prunes_reused_pid_case
        ;;
    sessionstart-runtime-init-failed-degrades)
        run_sessionstart_runtime_init_failed_degrades_case
        ;;
    sessionstart-control-gate-failure-degrades)
        run_sessionstart_control_gate_failure_degrades_case
        ;;
    runtime-clear-context-clears-probe-pid)
        run_runtime_clear_context_clears_probe_pid_case
        ;;
    runtime-claim-parent-fallback)
        run_runtime_claim_parent_fallback_case
        ;;
    artifact-lifecycle-classifier)
        run_artifact_lifecycle_classifier_case
        ;;
    artifact-lifecycle-hook-install)
        run_artifact_lifecycle_hook_install_case
        ;;
    artifact-lifecycle-pre-commit-block)
        run_artifact_lifecycle_pre_commit_block_case
        ;;
    artifact-lifecycle-pre-commit-allow)
        run_artifact_lifecycle_pre_commit_allow_case
        ;;
    artifact-lifecycle-rejects-tabbed-path)
        run_artifact_lifecycle_rejects_tabbed_path_case
        ;;
    docs-catalog-check)
        run_docs_catalog_check_case
        ;;
    docs-catalog-progressive-disclosure)
        run_docs_catalog_progressive_disclosure_case
        ;;
    docs-retention-check)
        run_docs_retention_check_case
        ;;
    backlog-check-strict)
        run_backlog_check_strict_case
        ;;
    current-status-overview)
        run_current_status_overview_case
        ;;
    tracking-health-overview)
        run_tracking_health_overview_case
        ;;
    install-overview)
        run_install_overview_case
        ;;
    execution-guarantees-check)
        run_execution_guarantees_check_case
        ;;
    knowledge-index-check)
        run_knowledge_index_check_case
        ;;
    acceptance-index-check)
        run_acceptance_index_check_case
        ;;
    token-risk-audit)
        run_token_risk_audit_case
        ;;
    contributing-ia-check)
        run_contributing_ia_check_case
        ;;
    review-tracks-check)
        run_review_tracks_check_case
        ;;
    hook-contract-check)
        run_hook_contract_check_case
        ;;
    runtime-helper-check)
        run_runtime_helper_check_case
        ;;
    cli-console-mirror-check)
        run_cli_console_mirror_check_case
        ;;
    revival-protocol-check)
        run_revival_protocol_check_case
        ;;
    diagnose-overview)
        run_diagnose_overview_case
        ;;
    state-machine-contract-check)
        run_state_machine_contract_check_case
        ;;
    on-qa-pass-blocks-inconsistent-state)
        run_on_qa_pass_blocks_inconsistent_state_case
        ;;
    spec-registry-validates-repo)
        run_spec_registry_validates_repo_case
        ;;
    spec-check-propagates-control-gate-failures)
        run_spec_check_propagates_control_gate_failures_case
        ;;
    spec-check-rejects-superseded-outside-archive)
        run_spec_check_rejects_superseded_outside_archive_case
        ;;
    spec-check-requires-replaced-by)
        run_spec_check_requires_replaced_by_case
        ;;
    spec-check-rejects-invalid-role)
        run_spec_check_rejects_invalid_role_case
        ;;
    spec-check-rejects-replacement-cycle)
        run_spec_check_rejects_replacement_cycle_case
        ;;
    spec-check-accepts-archived-superseded)
        run_spec_check_accepts_archived_superseded_case
        ;;
    host-workboard-backlog-anchor)
        run_host_workboard_backlog_anchor_case
        ;;
    cli-console-mirror-overwrites)
        run_cli_console_mirror_overwrites_case
        ;;
    feishu-duplex-window-queue)
        run_feishu_duplex_window_queue_case
        ;;
    overlay-skill-handoff-stays-native)
        run_overlay_skill_handoff_stays_native_case
        ;;
    overlay-governance-check)
        run_overlay_governance_check_case
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

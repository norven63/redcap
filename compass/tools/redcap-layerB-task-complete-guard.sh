#!/usr/bin/env bash
#
# Repo-owned task-complete guard for Copilot postToolUse.
# When .dev-task.md enters task-complete, this guard auto-attempts:
# 1. task report registration (best effort, prefer existing pending artifact; otherwise only a unique git-visible candidate)
# 2. unified Layer B closeout runtime

set -u

HOST="${1:-}"

if [[ -z "$HOST" ]]; then
    echo "[redcap-layerB-task-complete-guard] ERROR: host is required" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TASK_FILE="$REDCAP_ROOT/.dev-task.md"
CLOSEOUT_RUNTIME_SCRIPT="${REDCAP_LAYERB_CLOSEOUT_RUNTIME_SCRIPT:-$SCRIPT_DIR/redcap-layerb-closeout-runtime.sh}"
REPORT_REGISTER_SCRIPT="${REDCAP_TASK_REPORT_REGISTER_SCRIPT:-$SCRIPT_DIR/redcap-task-report-register.sh}"
TASK_COMPLETE_SLICE="${REDCAP_TASK_COMPLETE_SLICE:-task-complete}"
SKIP_AUTOREGISTER="${REDCAP_TASK_COMPLETE_GUARD_SKIP_AUTOREGISTER:-0}"
FORCE_RUN="${REDCAP_TASK_COMPLETE_GUARD_FORCE:-0}"

if [[ "${REDCAP_SUPPRESS_TASK_COMPLETE_GUARD:-0}" == "1" ]]; then
    echo "[redcap-layerB-task-complete-guard] suppressed by REDCAP_SUPPRESS_TASK_COMPLETE_GUARD=1" >&2
    exit 0
fi

source "$SCRIPT_DIR/redcap-runtime-state.sh"
source "$SCRIPT_DIR/redcap-dev-task.sh"
source "$SCRIPT_DIR/redcap-interop-governance.sh"

guard_lock_owner_pid() {
    local lock_path="$1"

    awk -F '\t' 'NR == 1 { print $1 }' "$lock_path" 2>/dev/null
}

prune_stale_guard_lock() {
    local lock_path="$1"
    local owner_pid=""
    local owner_started_at=""

    if [[ ! -f "$lock_path" ]]; then
        return 0
    fi

    owner_pid=$(guard_lock_owner_pid "$lock_path" 2>/dev/null || true)
    owner_started_at=$(redcap_interop_lock_owner_started_at "$lock_path" 2>/dev/null || true)
    if redcap_interop_lock_process_matches "$owner_pid" "$owner_started_at"; then
        return 1
    fi

    rm -f "$lock_path" 2>/dev/null || return 1
}

acquire_guard_lock() {
    local lock_path lock_tmp attempts=0 created_at owner_started_at

    lock_path=$(redcap_runtime_path "layerB/task-complete-guard.lock" 2>/dev/null || true)
    [[ -n "$lock_path" ]] || return 1
    mkdir -p "$(dirname "$lock_path")" || return 1
    lock_tmp="$lock_path.$$.$RANDOM.tmp"
    created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    owner_started_at=$(redcap_runtime_process_started_at "$$" 2>/dev/null || true)
    [[ -n "$owner_started_at" ]] || return 1
    printf '%s\t%s\t%s\n' "$$" "$owner_started_at" "$created_at" > "$lock_tmp" || return 1
    chmod 600 "$lock_tmp" 2>/dev/null || {
        rm -f "$lock_tmp" 2>/dev/null || true
        return 1
    }

    while ! ln "$lock_tmp" "$lock_path" 2>/dev/null; do
        prune_stale_guard_lock "$lock_path" || true
        attempts=$((attempts + 1))
        if [[ "$attempts" -ge 200 ]]; then
            rm -f "$lock_tmp" 2>/dev/null || true
            return 1
        fi
        sleep 0.05
    done

    rm -f "$lock_tmp" 2>/dev/null || true
    GUARD_LOCK_PATH="$lock_path"
    return 0
}

release_guard_lock() {
    if [[ -n "${GUARD_LOCK_PATH:-}" ]]; then
        rm -f "$GUARD_LOCK_PATH" 2>/dev/null || true
        GUARD_LOCK_PATH=""
    fi
}

write_guard_marker() {
    local key="$1"
    local value="$2"

    redcap_runtime_write_text "layerB/task-complete-guard/$key" "$value" >/dev/null 2>&1
}

read_guard_marker() {
    local key="$1"
    local path

    path=$(redcap_runtime_path "layerB/task-complete-guard/$key" 2>/dev/null || true)
    [[ -n "$path" && -f "$path" ]] || return 1
    cat "$path" 2>/dev/null
}

record_guard_state() {
    local fingerprint="$1"
    local status="$2"
    local detail="${3:-}"

    write_guard_marker "last-attempt-fingerprint" "$fingerprint" || true
    write_guard_marker "last-status" "$status" || true
    write_guard_marker "last-detail" "$detail" || true
    write_guard_marker "last-attempted-head" "$CURRENT_HEAD" || true
    write_guard_marker "last-attempted-at" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" || true
}

list_git_visible_report_candidates() {
    local initial_head_file="$1"

    python3 - "$REDCAP_ROOT" "$initial_head_file" <<'PY'
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1])
initial_head_file = Path(sys.argv[2])
report_dir = root / "compass/docs/task-reports"
if not report_dir.is_dir():
    raise SystemExit(0)

initial_head = ""
if initial_head_file.is_file():
    initial_head = initial_head_file.read_text(encoding="utf-8").strip()

def git_lines(*args: str) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]

paths: set[str] = set()
if initial_head:
    paths.update(git_lines("diff", "--name-only", "--diff-filter=AMRT", initial_head, "--", "compass/docs/task-reports"))
paths.update(git_lines("diff", "--cached", "--name-only", "--diff-filter=AMRT", "--", "compass/docs/task-reports"))
paths.update(git_lines("diff", "--name-only", "--diff-filter=AMRT", "--", "compass/docs/task-reports"))
paths.update(git_lines("ls-files", "--others", "--exclude-standard", "--", "compass/docs/task-reports"))

for rel in sorted(paths):
    if not rel.endswith(".md"):
        continue
    path = root / rel
    if path.is_file():
        print(rel)
PY
}

current_report_path() {
    local initial_head_file="$1"
    local rel
    rel=$(redcap_interop_current_report_marker_rel "$REDCAP_ROOT" "$TASK_FILE" 2>/dev/null || true)
    [[ -n "$rel" && -f "$REDCAP_ROOT/$rel" ]] || return 1

    local candidates=()
    while IFS= read -r candidate; do
        [[ -n "$candidate" ]] || continue
        candidates+=("$candidate")
    done < <(list_git_visible_report_candidates "$initial_head_file")

    if [[ ${#candidates[@]} -eq 0 ]]; then
        printf '%s\n' "$rel"
        return 0
    fi
    if [[ ${#candidates[@]} -eq 1 && "${candidates[0]}" == "$rel" ]]; then
        printf '%s\n' "$rel"
        return 0
    fi
    return 1
}

discover_report_candidate() {
    local initial_head_file="$1"
    local pending_state=""
    local pending_rel=""
    local candidates=()

    pending_state=$(redcap_interop_pending_closure_file "$REDCAP_ROOT" "$TASK_FILE" 2>/dev/null || true)
    if [[ -n "$pending_state" && -f "$pending_state" ]]; then
        pending_rel=$(redcap_interop_read_state_field "$pending_state" "artifact_path" 2>/dev/null || true)
        pending_rel=$(redcap_interop_resolve_report_rel_path "$REDCAP_ROOT" "$pending_rel" 2>/dev/null || true)
    fi

    while IFS= read -r candidate; do
        [[ -n "$candidate" ]] || continue
        candidates+=("$candidate")
    done < <(list_git_visible_report_candidates "$initial_head_file")

    if [[ -n "$pending_rel" && -f "$REDCAP_ROOT/$pending_rel" ]]; then
        if [[ ${#candidates[@]} -eq 0 ]]; then
            printf '%s\n' "$REDCAP_ROOT/$pending_rel"
            return 0
        fi
        if [[ ${#candidates[@]} -eq 1 && "${candidates[0]}" == "$pending_rel" ]]; then
            printf '%s\n' "$REDCAP_ROOT/$pending_rel"
            return 0
        fi
        return 0
    fi

    if [[ ${#candidates[@]} -ne 1 ]]; then
        return 0
    fi

    printf '%s\n' "$REDCAP_ROOT/${candidates[0]}"
}

build_guard_fingerprint() {
    local report_ref="$1"
    local confirmed_hash
    local worktree_signature

    confirmed_hash=$(redcap_dev_task_confirmed_hash "$TASK_FILE" 2>/dev/null || true)
    worktree_signature=$(python3 - "$REDCAP_ROOT" <<'PY'
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1])

def git_bytes(*args: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if proc.returncode != 0:
        return b""
    return proc.stdout

sig = sha256()
sig.update(b"cached\0")
sig.update(git_bytes("diff", "--cached", "--binary", "--no-ext-diff", "HEAD", "--"))
sig.update(b"worktree\0")
sig.update(git_bytes("diff", "--binary", "--no-ext-diff", "--"))
untracked = git_bytes("ls-files", "--others", "--exclude-standard", "-z")
sig.update(b"untracked\0")
sig.update(untracked)
for raw in sorted(entry for entry in untracked.split(b"\0") if entry):
    path = root / raw.decode()
    sig.update(raw)
    if path.is_file():
        sig.update(sha256(path.read_bytes()).digest())
print(sig.hexdigest())
PY
)
    printf '%s|%s|%s|%s\n' \
        "${confirmed_hash:-unknown}" \
        "${CURRENT_HEAD:-unknown}" \
        "${report_ref:-none}" \
        "${worktree_signature:-none}"
}

ACTIVE_SLICE=$(redcap_dev_task_extract_kv "$TASK_FILE" "active_slice" 2>/dev/null || true)
if [[ "$ACTIVE_SLICE" != "$TASK_COMPLETE_SLICE" ]]; then
    exit 0
fi

if ! redcap_runtime_attach_current_or_claim "$HOST"; then
    redcap_runtime_record_degraded_mode \
        "$REDCAP_ROOT" \
        "task-complete-guard-missing-runtime-claim" \
        "host=$HOST active_slice=$ACTIVE_SLICE" \
        >/dev/null 2>&1 || true
    exit 0
fi

CURRENT_HEAD=$(git -C "$REDCAP_ROOT" rev-parse HEAD 2>/dev/null || true)
[[ -n "$CURRENT_HEAD" ]] || exit 0

INITIAL_HEAD_FILE=$(redcap_runtime_path "layerB/initial-head" 2>/dev/null || true)
if [[ -z "$INITIAL_HEAD_FILE" || ! -f "$INITIAL_HEAD_FILE" ]]; then
    redcap_runtime_record_degraded_mode \
        "$REDCAP_ROOT" \
        "task-complete-guard-missing-initial-head" \
        "host=$HOST current_head=$CURRENT_HEAD" \
        >/dev/null 2>&1 || true
    exit 0
fi

if ! acquire_guard_lock; then
    exit 0
fi
trap 'release_guard_lock' EXIT

CURRENT_REPORT_REL=$(current_report_path "$INITIAL_HEAD_FILE" 2>/dev/null || true)
if [[ -z "$CURRENT_REPORT_REL" && "$SKIP_AUTOREGISTER" != "1" && -x "$REPORT_REGISTER_SCRIPT" ]]; then
    REPORT_CANDIDATE=$(discover_report_candidate "$INITIAL_HEAD_FILE" 2>/dev/null || true)
    if [[ -n "$REPORT_CANDIDATE" ]]; then
        if REDCAP_HOST_PROCESS_PID="${REDCAP_HOST_PROCESS_PID:-$PPID}" \
            REDCAP_RUNTIME_SESSION_ID="${REDCAP_RUNTIME_SESSION_ID:-}" \
            REDCAP_RUNTIME_CAPABILITY="${REDCAP_RUNTIME_CAPABILITY:-}" \
            bash "$REPORT_REGISTER_SCRIPT" "$HOST" "$REPORT_CANDIDATE" >/dev/null 2>&1; then
            CURRENT_REPORT_REL="${REPORT_CANDIDATE#$REDCAP_ROOT/}"
            write_guard_marker "auto-registered-report" "$CURRENT_REPORT_REL" || true
        fi
    fi
fi

FINGERPRINT=$(build_guard_fingerprint "$CURRENT_REPORT_REL")
LAST_FINGERPRINT=$(read_guard_marker "last-attempt-fingerprint" 2>/dev/null || true)
LAST_STATUS=$(read_guard_marker "last-status" 2>/dev/null || true)
SUCCESS_FINGERPRINT=$(read_guard_marker "success-fingerprint" 2>/dev/null || true)

if [[ "$FORCE_RUN" != "1" && -n "$SUCCESS_FINGERPRINT" && "$SUCCESS_FINGERPRINT" == "$FINGERPRINT" ]]; then
    exit 0
fi
if [[ "$FORCE_RUN" != "1" && -n "$LAST_FINGERPRINT" && "$LAST_FINGERPRINT" == "$FINGERPRINT" && "$LAST_STATUS" != "success" ]]; then
    exit 0
fi

INITIAL_HEAD=$(cat "$INITIAL_HEAD_FILE" 2>/dev/null || true)
[[ -n "$INITIAL_HEAD" ]] || exit 0

if [[ ! -x "$CLOSEOUT_RUNTIME_SCRIPT" ]]; then
    record_guard_state "$FINGERPRINT" "missing-closeout-runtime" "script=$CLOSEOUT_RUNTIME_SCRIPT"
    exit 0
fi

set +e
REDCAP_HOST_PROCESS_PID="${REDCAP_HOST_PROCESS_PID:-$PPID}" \
REDCAP_ON_COMPLETE_HOST="$HOST" \
REDCAP_RUNTIME_SESSION_ID="${REDCAP_RUNTIME_SESSION_ID:-}" \
REDCAP_RUNTIME_CAPABILITY="${REDCAP_RUNTIME_CAPABILITY:-}" \
bash "$CLOSEOUT_RUNTIME_SCRIPT" complete \
    --host "$HOST" \
    --task-file "$TASK_FILE" \
    --baseline-head "$INITIAL_HEAD" >/dev/null 2>&1
STATUS=$?
set -e

case "$STATUS" in
    0)
        record_guard_state "$FINGERPRINT" "success" "closeout-runtime-finished"
        write_guard_marker "success-fingerprint" "$FINGERPRINT" || true
        ;;
    1)
        record_guard_state "$FINGERPRINT" "retry-needed" "closeout-runtime-retry-needed"
        redcap_runtime_remove_path "layerB/task-complete-guard/success-fingerprint" >/dev/null 2>&1 || true
        ;;
    *)
        record_guard_state "$FINGERPRINT" "error" "closeout-runtime-exit=$STATUS"
        redcap_runtime_remove_path "layerB/task-complete-guard/success-fingerprint" >/dev/null 2>&1 || true
        redcap_runtime_record_degraded_mode \
            "$REDCAP_ROOT" \
            "task-complete-guard-closeout-runtime-error" \
            "host=$HOST current_head=$CURRENT_HEAD status=$STATUS" \
            >/dev/null 2>&1 || true
        ;;
esac

exit 0

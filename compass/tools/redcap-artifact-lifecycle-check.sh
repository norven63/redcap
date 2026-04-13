#!/usr/bin/env bash
# shellcheck shell=bash
# Reject tracked or to-be-tracked artifacts that violate RedCap lifecycle policy.

set -uo pipefail

REPO_ROOT="${1:-}"
BASELINE="${2:-}"
CURRENT_HEAD="${3:-}"
POLICY_MODE="${4:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
if [[ -z "$REPO_ROOT" ]]; then
    REPO_ROOT="$DEFAULT_REDCAP_ROOT"
fi

if [[ -z "$POLICY_MODE" ]]; then
    if [[ "$(cd "$REPO_ROOT" 2>/dev/null && pwd)" == "$DEFAULT_REDCAP_ROOT" ]]; then
        POLICY_MODE="redcap-self"
    else
        POLICY_MODE="noop"
    fi
fi

if [[ "$POLICY_MODE" != "redcap-self" ]]; then
    exit 0
fi

TMP_FILES=$(mktemp)
cleanup() {
    rm -f "$TMP_FILES" 2>/dev/null || true
}
trap cleanup EXIT

collect_changed_files() {
    if [[ -n "$BASELINE" && -n "$CURRENT_HEAD" ]]; then
        git -C "$REPO_ROOT" --no-pager log --format='' --name-only "$BASELINE..$CURRENT_HEAD" 2>/dev/null
        return
    fi

    {
        git -C "$REPO_ROOT" --no-pager diff --name-only 2>/dev/null
        git -C "$REPO_ROOT" --no-pager diff --cached --name-only 2>/dev/null
    }
}

collect_changed_files | sed '/^[[:space:]]*$/d' | sort -u > "$TMP_FILES"

python3 - "$TMP_FILES" <<'PY'
import pathlib
import sys
from fnmatch import fnmatch

files_path = pathlib.Path(sys.argv[1])
files = [line.strip() for line in files_path.read_text(encoding="utf-8").splitlines() if line.strip()]

disallowed_exact = {
    ".dev-task.md": "session-isolated process state",
    ".env.local": "local-only host asset",
    "cli_console.md": "local-only display mirror",
    "compass/tools/feishu-config.json": "local-only host asset",
    "prism/reports/.session-registry.yaml": "local-only runtime registry",
}

disallowed_globs = [
    ("compass/.workflow/**", "local-only host assets"),
    ("prism/runs/**", "session-isolated process state"),
    ("round-table/**", "local-only workspace"),
    ("__pycache__/**", "temporary runtime outputs"),
    ("*.pyc", "temporary runtime outputs"),
    ("docs*", "temporary reading-space root"),
    ("docs*/**", "temporary reading-space root"),
]

allowed_docs_root = {"index.yaml", "specs", "research", "traces", "task-reports"}
violations = []

for path in files:
    reason = None
    if path in disallowed_exact:
        reason = disallowed_exact[path]
    else:
        for pattern, category in disallowed_globs:
            if fnmatch(path, pattern):
                reason = category
                break

    if reason is None and path.startswith("compass/docs/"):
        rel = path[len("compass/docs/"):]
        root = rel.split("/", 1)[0]
        if root not in allowed_docs_root:
            reason = "violates compass/docs root policy"
        elif root == "index.yaml" and rel != "index.yaml":
            reason = "violates compass/docs root policy"

    if reason is not None:
        violations.append((path, reason))

if violations:
    print("[redcap-artifact-lifecycle-check] disallowed artifacts detected", file=sys.stderr)
    for path, reason in violations:
        print(f"  - {path} :: {reason}", file=sys.stderr)
    sys.exit(1)
PY

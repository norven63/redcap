#!/usr/bin/env bash
# shellcheck shell=bash
# Classify artifact paths by lifecycle so gates can block non-repo-tracked outputs.

set -euo pipefail

REPO_ROOT="${1:-}"

if [[ -z "$REPO_ROOT" ]]; then
    echo "[redcap-artifact-classifier] usage: bash compass/tools/redcap-artifact-classifier.sh <repo-root> [path ...]" >&2
    exit 2
fi

shift || true

if [[ $# -eq 0 ]]; then
    exit 0
fi

python3 - "$REPO_ROOT/compass/docs/index.yaml" "$@" <<'PY'
import pathlib
import re
import sys
from fnmatch import fnmatch


def normalize(path: str) -> str:
    value = path.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value


def read_allowed_docs_root(index_path: pathlib.Path) -> set[str]:
    default = {"index.yaml", "specs", "research", "traces", "task-reports"}
    if not index_path.exists():
        return default

    allowed: list[str] = []
    in_root_policy = False
    in_allowed_entries = False

    for raw_line in index_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if not raw_line.startswith((" ", "\t")):
            in_root_policy = stripped == "root_policy:"
            in_allowed_entries = False
            continue

        if not in_root_policy:
            continue

        if re.match(r"^\s{2}allowed_entries:\s*$", raw_line):
            in_allowed_entries = True
            continue

        if re.match(r"^\s{2}\S", raw_line):
            in_allowed_entries = False

        if in_allowed_entries:
            match = re.match(r"^\s*-\s*(.+?)\s*$", raw_line)
            if match:
                allowed.append(match.group(1))

    return set(allowed) or default


allowed_docs_root = read_allowed_docs_root(pathlib.Path(sys.argv[1]))
paths = [normalize(path) for path in sys.argv[2:]]

disallowed_exact = {
    ".dev-task.md": ("session-isolated", "session-isolated-process-state", "session-isolated process state"),
    ".env.local": ("local-only", "local-only-host-asset", "local-only host asset"),
    "cli_console.md": ("local-only", "local-only-display-mirror", "local-only display mirror"),
    "compass/tools/feishu-config.json": ("local-only", "local-only-host-asset", "local-only host asset"),
    "prism/reports/.session-registry.yaml": ("local-only", "local-only-runtime-registry", "local-only runtime registry"),
}

disallowed_globs = [
    ("compass/.workflow/**", "local-only", "local-only-host-asset", "local-only host assets"),
    ("prism/runs/**", "session-isolated", "session-isolated-process-state", "session-isolated process state"),
    ("round-table/**", "local-only", "local-only-workspace", "local-only workspace"),
    ("__pycache__/**", "temporary", "temporary-runtime-output", "temporary runtime outputs"),
    ("*.pyc", "temporary", "temporary-runtime-output", "temporary runtime outputs"),
    ("docs*", "temporary", "temporary-reading-space-root", "temporary reading-space root"),
    ("docs*/**", "temporary", "temporary-reading-space-root", "temporary reading-space root"),
]


def classify(path: str) -> tuple[str, str, str]:
    if path in disallowed_exact:
        return disallowed_exact[path]

    for pattern, lifecycle, category, reason in disallowed_globs:
        if fnmatch(path, pattern):
            return lifecycle, category, reason

    if path.startswith("compass/docs/"):
        rel = path[len("compass/docs/") :]
        root = rel.split("/", 1)[0]
        if root not in allowed_docs_root or (root == "index.yaml" and rel != "index.yaml"):
            return "local-only", "docs-root-policy-violation", "violates compass/docs root policy"
        return "repo-tracked", "repo-tracked-evidence", "compass/docs approved collection"

    return "repo-tracked", "repo-tracked-canonical", "repo-tracked canonical/evidence"


for path in paths:
    if not path:
        continue
    if "\t" in path or "\n" in path:
        print("[redcap-artifact-classifier] unsupported path contains tab/newline", file=sys.stderr)
        print(f"  - {path!r}", file=sys.stderr)
        sys.exit(1)
    lifecycle, category, reason = classify(path)
    print(f"{path}\t{lifecycle}\t{category}\t{reason}")
PY

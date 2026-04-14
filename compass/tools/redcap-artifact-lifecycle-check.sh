#!/usr/bin/env bash
# shellcheck shell=bash
# Reject tracked or to-be-tracked artifacts that violate RedCap lifecycle policy.

set -euo pipefail

REPO_ROOT="${1:-}"
BASELINE="${2:-}"
CURRENT_HEAD="${3:-}"
POLICY_MODE="${4:-}"
CHECK_MODE="${5:-history}"

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
TMP_RAW_FILES=$(mktemp)
cleanup() {
    rm -f "$TMP_FILES" 2>/dev/null || true
    rm -f "$TMP_RAW_FILES" 2>/dev/null || true
}
trap cleanup EXIT

collect_changed_files() {
    case "$CHECK_MODE" in
        pre-commit)
            git -C "$REPO_ROOT" --no-pager diff --cached --diff-filter=ACMR --name-only -z
            ;;
        history)
            if [[ -n "$BASELINE" && -n "$CURRENT_HEAD" ]]; then
                git -C "$REPO_ROOT" --no-pager log --diff-filter=ACMR --format='' --name-only -z "$BASELINE..$CURRENT_HEAD"
                return
            fi

            {
                git -C "$REPO_ROOT" --no-pager diff --diff-filter=ACMR --name-only -z
                git -C "$REPO_ROOT" --no-pager diff --cached --diff-filter=ACMR --name-only -z
            }
            ;;
        *)
            echo "[redcap-artifact-lifecycle-check] unsupported check mode: $CHECK_MODE" >&2
            exit 2
            ;;
    esac
}

CLASSIFIER="$SCRIPT_DIR/redcap-artifact-classifier.sh"
if [[ ! -x "$CLASSIFIER" ]]; then
    echo "[redcap-artifact-lifecycle-check] missing classifier: $CLASSIFIER" >&2
    exit 1
fi

collect_changed_files > "$TMP_RAW_FILES"
python3 - "$TMP_RAW_FILES" "$TMP_FILES" <<'PY'
import pathlib
import sys

input_path = pathlib.Path(sys.argv[1])
output_path = pathlib.Path(sys.argv[2])
seen = set()
paths = []
invalid = []

for item in input_path.read_bytes().split(b"\0"):
    if not item:
        continue
    path = item.decode("utf-8", "surrogateescape")
    if "\t" in path or "\n" in path:
        invalid.append(path)
        continue
    if path not in seen:
        seen.add(path)
        paths.append(path)

if invalid:
    print("[redcap-artifact-lifecycle-check] unsupported filename contains tab/newline", file=sys.stderr)
    for path in invalid:
        print(f"  - {path!r}", file=sys.stderr)
    sys.exit(1)

normalized = "\n".join(sorted(paths))
if normalized:
    normalized += "\n"
output_path.write_text(normalized, encoding="utf-8")
PY

CHANGED_FILES=()
while IFS= read -r changed_path; do
    [[ -n "$changed_path" ]] || continue
    CHANGED_FILES+=("$changed_path")
done < "$TMP_FILES"

if [[ ${#CHANGED_FILES[@]} -eq 0 ]]; then
    exit 0
fi

CLASSIFICATION_OUTPUT="$(bash "$CLASSIFIER" "$REPO_ROOT" "${CHANGED_FILES[@]}")"
ALLOWED_COUNT=0
DISALLOWED_COUNT=0
VIOLATIONS=()

while IFS=$'\t' read -r path lifecycle category reason; do
    [[ -n "$path" ]] || continue
    if [[ "$lifecycle" == "repo-tracked" ]]; then
        ALLOWED_COUNT=$((ALLOWED_COUNT + 1))
        continue
    fi

    DISALLOWED_COUNT=$((DISALLOWED_COUNT + 1))
    VIOLATIONS+=("$path"$'\t'"$lifecycle"$'\t'"$category"$'\t'"$reason")
done <<< "$CLASSIFICATION_OUTPUT"

if [[ "$DISALLOWED_COUNT" == "0" ]]; then
    exit 0
fi

echo "[redcap-artifact-lifecycle-check] disallowed artifacts detected" >&2
for violation in "${VIOLATIONS[@]}"; do
    IFS=$'\t' read -r path lifecycle category reason <<< "$violation"
    echo "  - $path :: $lifecycle :: $category :: $reason" >&2
done

if [[ "$CHECK_MODE" == "pre-commit" && "$ALLOWED_COUNT" -gt 0 ]]; then
    echo "[redcap-artifact-lifecycle-check] mixed-lifecycle staged commit detected: repo-tracked artifacts cannot be committed together with session/local/temp artifacts" >&2
fi

exit 1

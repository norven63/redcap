#!/usr/bin/env bash
# shellcheck shell=bash
# 用途：知识沉淀与自进化脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

# Build a small first-read catalog for compass/docs so agents avoid bulk-reading historical evidence.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CATALOG_PATH="${REDCAP_DOCS_CATALOG_PATH:-$REDCAP_ROOT/compass/docs/catalog.json}"

usage() {
    cat <<'EOF' >&2
usage:
  bash compass/tools/redcap-docs-catalog.sh generate [output-path]
  bash compass/tools/redcap-docs-catalog.sh check
  bash compass/tools/redcap-docs-catalog.sh summary
  bash compass/tools/redcap-docs-catalog.sh plan <query> [limit]
  bash compass/tools/redcap-docs-catalog.sh budget <repo-relative-doc-path>...
  bash compass/tools/redcap-docs-catalog.sh retention-check
EOF
}

generate_catalog() {
    local output_path="$1"

    python3 "$SCRIPT_DIR/redcap-docs-catalog.py" generate "$REDCAP_ROOT" "$output_path"
}

print_summary() {
    python3 "$SCRIPT_DIR/redcap-docs-catalog.py" summary "$REDCAP_ROOT" "$CATALOG_PATH"
}

print_plan() {
    local query="$1"
    local limit="${2:-8}"

    if [[ -z "$query" ]]; then
        usage
        return 2
    fi

    python3 "$SCRIPT_DIR/redcap-docs-catalog.py" plan "$REDCAP_ROOT" "$CATALOG_PATH" "$query" "$limit"
}

check_budget() {
    if [[ "$#" -eq 0 ]]; then
        usage
        return 2
    fi

    python3 "$SCRIPT_DIR/redcap-docs-catalog.py" budget "$REDCAP_ROOT" "$CATALOG_PATH" "$@"
}

check_retention() {
    python3 "$SCRIPT_DIR/redcap-docs-catalog.py" retention-check "$REDCAP_ROOT" "$CATALOG_PATH"
}

check_catalog() {
    python3 "$SCRIPT_DIR/redcap-docs-catalog.py" check "$REDCAP_ROOT" "$CATALOG_PATH"
}

COMMAND="${1:-summary}"
case "$COMMAND" in
    generate)
        generate_catalog "${2:-$CATALOG_PATH}"
        ;;
    check)
        check_catalog
        ;;
    summary)
        print_summary
        ;;
    plan)
        print_plan "${2:-}" "${3:-8}"
        ;;
    budget)
        shift
        check_budget "$@"
        ;;
    retention-check)
        check_retention
        ;;
    *)
        usage
        exit 2
        ;;
esac

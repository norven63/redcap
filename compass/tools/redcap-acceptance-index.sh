#!/usr/bin/env bash
# Build a small first-read index for the large acceptance suite.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ACCEPTANCE_PATH="$REDCAP_ROOT/compass/tools/redcap-multi-session-acceptance.sh"

usage() {
    cat <<'EOF' >&2
usage:
  bash compass/tools/redcap-acceptance-index.sh summary
  bash compass/tools/redcap-acceptance-index.sh find <case-substring>
  bash compass/tools/redcap-acceptance-index.sh check
EOF
}

command="${1:-summary}"
case_query="${2:-}"
python3 "$SCRIPT_DIR/redcap-acceptance-index.py" "$REDCAP_ROOT" "$ACCEPTANCE_PATH" "$command" "$case_query"

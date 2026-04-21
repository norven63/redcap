#!/usr/bin/env bash
# redcap-e2e-benchmark-carrier.sh — scaffold the repo-owned md-table-tool benchmark carrier.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FIXTURE_ROOT="$REDCAP_ROOT/loom/fixtures/md-table-tool-benchmark"
SEED_DIR="$FIXTURE_ROOT/seed"

usage() {
  cat <<'EOF'
Usage:
  bash loom/tools/redcap-e2e-benchmark-carrier.sh check
  bash loom/tools/redcap-e2e-benchmark-carrier.sh summary
  bash loom/tools/redcap-e2e-benchmark-carrier.sh init <dest-dir>
EOF
}

ensure_seed() {
  [[ -d "$SEED_DIR" ]] || {
    echo "[redcap-e2e-benchmark-carrier] missing seed dir: $SEED_DIR" >&2
    exit 1
  }
  [[ -f "$FIXTURE_ROOT/carrier.json" ]] || {
    echo "[redcap-e2e-benchmark-carrier] missing carrier metadata: $FIXTURE_ROOT/carrier.json" >&2
    exit 1
  }
}

COMMAND="${1:-summary}"
case "$COMMAND" in
  check)
    ensure_seed
    echo "E2E_BENCHMARK_CARRIER_OK"
    ;;
  summary)
    ensure_seed
    echo "E2E_BENCHMARK_CARRIER"
    echo "fixture_root=$FIXTURE_ROOT"
    echo "seed_dir=$SEED_DIR"
    echo "files=$(find "$SEED_DIR" -type f | wc -l | tr -d ' ')"
    echo "request=$SEED_DIR/REQUEST.md"
    echo "sample_input=$SEED_DIR/samples/input.md"
    ;;
  init)
    ensure_seed
    DEST="${2:-}"
    if [[ -z "$DEST" ]]; then
      echo "[redcap-e2e-benchmark-carrier] init requires <dest-dir>" >&2
      usage
      exit 1
    fi
    mkdir -p "$DEST"
    cp -R "$SEED_DIR"/. "$DEST"/
    cp "$FIXTURE_ROOT/carrier.json" "$DEST"/.redcap-e2e-benchmark-carrier.json
    echo "E2E_BENCHMARK_CARRIER_INIT_OK"
    echo "dest=$(cd "$DEST" && pwd -P)"
    ;;
  *)
    usage
    exit 1
    ;;
esac

#!/usr/bin/env bash
# Dictionary: references/file-lookup-dictionary.md#shared-knowledge-layer
# Validate the shared knowledge repository template and append-only contracts.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

bash "$SCRIPT_DIR/redcap-shared-knowledge.sh" check --root "$REDCAP_ROOT/templates/shared-knowledge"

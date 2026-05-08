#!/usr/bin/env bash
# 用途：运行时与收尾脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#runtime-and-closeout

# One-click install/revival entry for Cap identity + RedCap workflow import.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$SCRIPT_DIR/redcap-dev-task.sh"

HOST="unknown"
TASK_FILE_ARG=""
INIT_IDENTITY=0
FULL_DIAGNOSE=0

usage() {
    cat <<'EOF'
Usage: bash compass/tools/redcap-install.sh [--host <name>] [--task-file <path>] [--init-identity] [--full-diagnose]

  --host <name>         Host label for reporting only (e.g. codex / claude / gemini / copilot)
  --task-file <path>    Task anchor path; defaults to .dev-task.md when present
  --init-identity       If ~/.cap/identity.md is missing, create it from the template in compass/soul.md
  --full-diagnose       Run redcap-diagnose.sh after the lightweight install/revival chain
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)
            HOST="${2:-}"
            shift 2
            ;;
        --task-file)
            TASK_FILE_ARG="${2:-}"
            shift 2
            ;;
        --init-identity)
            INIT_IDENTITY=1
            shift
            ;;
        --full-diagnose)
            FULL_DIAGNOSE=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "[redcap-install] unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

TASK_FILE=$(redcap_dev_task_resolve_file "$TASK_FILE_ARG")
IDENTITY_FILE="${REDCAP_IDENTITY_FILE:-$HOME/.cap/identity.md}"
INSTALL_OK=1

extract_identity_template() {
    python3 - "$REDCAP_ROOT/compass/soul.md" <<'PY'
import pathlib
import re
import sys

text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
match = re.search(r"## 七、identity\.md 模板.*?```markdown\n(.*?)\n```", text, re.S)
if not match:
    raise SystemExit("failed to extract identity template from compass/soul.md")
print(match.group(1))
PY
}

run_check() {
    local label="$1"
    shift
    local output=""
    local status=0

    set +e
    output="$("$@" 2>&1)"
    status=$?
    set -e

    if [[ "$status" -eq 0 ]]; then
        printf '[ok] %s\n' "$label"
        if [[ "$label" == "current-status" ]]; then
            printf '%s\n' "$output" | sed -n '1,4p' | sed 's/^/  /'
        elif [[ "$label" == "tracking-health" ]]; then
            printf '%s\n' "$output" | sed '/^REDCAP_TRACKING_HEALTH$/d;/^TRACKING_OK$/d' | sed 's/^/  /'
        elif [[ "$label" == "feishu-inbox" ]]; then
            printf '%s\n' "$output" | sed 's/^/  /'
        elif [[ "$label" == "host-hook-readiness" ]]; then
            printf '%s\n' "$output" | sed 's/^/  /'
        fi
    else
        printf '[fail] %s status=%s\n' "$label" "$status"
        printf '%s\n' "$output" | sed -n '1,20p' | sed 's/^/  /'
        INSTALL_OK=0
    fi
}

echo "REDCAP_INSTALL"
echo "host=$HOST"
echo "repo=$REDCAP_ROOT"

if [[ -f "$IDENTITY_FILE" ]]; then
    echo "identity=present:$IDENTITY_FILE"
elif [[ "$INIT_IDENTITY" -eq 1 ]]; then
    mkdir -p "$(dirname "$IDENTITY_FILE")"
    extract_identity_template >"$IDENTITY_FILE"
    echo "identity=initialized:$IDENTITY_FILE"
else
    echo "identity=missing:$IDENTITY_FILE"
    echo "hint=run again with --init-identity to create the template before revival"
    INSTALL_OK=0
fi

run_check "user-agent-identity" bash "$SCRIPT_DIR/redcap-user-agent-identity.sh" init --host "$HOST"
run_check "feishu-notification-policy" bash "$SCRIPT_DIR/redcap-feishu-notification-policy-check.sh"
run_check "feishu-inbox" bash "$SCRIPT_DIR/redcap-feishu-inbox.sh" scan --soft
run_check "current-status" bash "$SCRIPT_DIR/redcap-current-status.sh" "$TASK_FILE"
run_check "tracking-health" bash "$SCRIPT_DIR/redcap-tracking-health.sh" "$TASK_FILE"
run_check "host-hook-readiness" bash "$SCRIPT_DIR/redcap-host-hook-readiness.sh" "$HOST" "$REDCAP_ROOT"
run_check "execution-guarantees" bash "$SCRIPT_DIR/redcap-execution-guarantee-check.sh"
run_check "revival-protocol" bash "$SCRIPT_DIR/redcap-revival-check.sh" "$REDCAP_ROOT"

if [[ "$FULL_DIAGNOSE" -eq 1 ]]; then
    run_check "diagnose" bash "$SCRIPT_DIR/redcap-diagnose.sh" "$TASK_FILE"
fi

if [[ "$INSTALL_OK" -eq 1 ]]; then
    echo "REDCAP_INSTALL_OK"
else
    echo "REDCAP_INSTALL_FAIL"
    exit 1
fi

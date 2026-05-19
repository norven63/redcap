#!/usr/bin/env bash
# 用途：运行时与收尾脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#runtime-and-closeout

# RedCap Layer B diagnostic overview.
# Note: current implementation requires a writable temp directory; read-only sandboxes are degraded/manual-only.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TASK_FILE="${1:-${REDCAP_TASK_FILE:-$REDCAP_ROOT/.dev-task.md}}"
REDCAP_RUNTIME_ROOT="${REDCAP_RUNTIME_ROOT:-$REDCAP_ROOT}"
REDCAP_WORKSPACE_ROOT="${REDCAP_WORKSPACE_ROOT:-$(cd "$(dirname "$TASK_FILE")" 2>/dev/null && pwd || dirname "$TASK_FILE")}"
REDCAP_DIAGNOSE_PROFILE="${REDCAP_DIAGNOSE_PROFILE:-source}"
export REDCAP_RUNTIME_ROOT REDCAP_WORKSPACE_ROOT REDCAP_TASK_FILE="$TASK_FILE"

case "$REDCAP_DIAGNOSE_PROFILE" in
    source|runtime)
        ;;
    *)
        printf '[redcap-diagnose] unsupported REDCAP_DIAGNOSE_PROFILE=%s\n' "$REDCAP_DIAGNOSE_PROFILE" >&2
        exit 2
        ;;
esac

run_check() {
    local name="$1"
    shift
    local output status

    if [[ "${1:-}" == "bash" && -n "${2:-}" && ! -e "$2" ]]; then
        printf '[skip] %s reason=script-not-packaged\n' "$name"
        return 0
    fi

    set +e
    output="$("$@" 2>&1)"
    status=$?
    set -e
    if [[ "$status" -eq 0 ]]; then
        printf '[ok] %s\n' "$name"
    else
        printf '[fail] %s status=%s\n' "$name" "$status"
        printf '%s\n' "$output" | sed -n '1,20p'
    fi
    return "$status"
}

run_source_check() {
    local name="$1"
    if [[ "$REDCAP_DIAGNOSE_PROFILE" == "runtime" ]]; then
        printf '[skip] %s reason=source-maintenance-check\n' "$name"
        return 0
    fi
    run_check "$@"
}

run_closeout_rescue_audit() {
    local runtime_script="$SCRIPT_DIR/redcap-layerb-closeout-runtime.sh"
    local status_output status rescue_candidate

    if [[ ! -x "$runtime_script" ]]; then
        echo "[warn] closeout-rescue-audit skipped (runtime missing)"
        return 0
    fi

    set +e
    status_output="$(bash "$runtime_script" status --task-file "$TASK_FILE" 2>/dev/null)"
    status=$?
    set -e

    if [[ "$status" -ne 0 || -z "$status_output" ]]; then
        echo "[warn] closeout-rescue-audit skipped (runtime status unavailable)"
        return 0
    fi

    rescue_candidate="$(python3 - "$status_output" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
receipt_exists = bool(payload.get("receipt_exists"))
active_slice = payload.get("active_slice", "")
state = payload.get("state") or {}
runtime_status = state.get("status", "")

terminal_slices = {"task-complete", "closeout-complete"}
terminal_states = {"closeout-pending", "completed", "blocked"}

if receipt_exists:
    print("skip:receipt-present")
elif runtime_status in terminal_states or active_slice in terminal_slices:
    print("run")
else:
    print(f"skip:status={runtime_status or 'none'} active_slice={active_slice or 'none'}")
PY
)"

    if [[ "$rescue_candidate" != "run" ]]; then
        echo "[ok] closeout-rescue-audit ${rescue_candidate}"
        return 0
    fi

    run_check \
        "closeout-rescue-audit" \
        bash "$runtime_script" audit-open --task-file "$TASK_FILE" --host "${REDCAP_DIAGNOSE_RESCUE_HOST:-diagnose}" --mode diagnose
}

echo "RedCap 深入体检：正在检查当前工作区能否安全继续推进"
echo "- 先展示人类可读的任务状态，再列出内部检查结果。"
echo "- 如果只需要快速判断能否继续，请运行 redcap doctor。"
echo
echo "REDCAP_DIAGNOSE"
echo "runtime_root=$REDCAP_RUNTIME_ROOT"
echo "workspace_root=$REDCAP_WORKSPACE_ROOT"
echo "task_file=$TASK_FILE"
echo "diagnose_profile=$REDCAP_DIAGNOSE_PROFILE"
echo

if [[ -x "$SCRIPT_DIR/redcap-current-status.sh" ]]; then
    bash "$SCRIPT_DIR/redcap-current-status.sh" "$TASK_FILE"
else
    echo "[warn] missing redcap-current-status.sh"
fi

echo
echo "## 诊断门禁"
overall=0
run_closeout_rescue_audit || overall=1
run_source_check "docs-catalog" bash "$SCRIPT_DIR/redcap-docs-catalog.sh" check || overall=1
run_source_check "docs-retention" bash "$SCRIPT_DIR/redcap-docs-catalog.sh" retention-check || overall=1
run_source_check "knowledge-index" bash "$SCRIPT_DIR/redcap-knowledge-index-check.sh" || overall=1
run_source_check "overlay-governance" bash "$SCRIPT_DIR/redcap-overlay-governance-check.sh" || overall=1
run_source_check "state-machine-contract" bash "$SCRIPT_DIR/redcap-state-machine-check.sh" || overall=1
run_source_check "layerb-lifecycle-contract" bash "$SCRIPT_DIR/redcap-layerb-lifecycle-check.sh" || overall=1
run_source_check "layerb-fsm" bash "$SCRIPT_DIR/redcap-layerb-fsm-check.sh" || overall=1
run_check "layerb-closeout-runtime" bash "$SCRIPT_DIR/redcap-layerb-closeout-runtime-check.sh" "$TASK_FILE" || overall=1
run_source_check "token-risk-audit" bash "$SCRIPT_DIR/redcap-token-risk-audit.sh" || overall=1
run_source_check "architecture-smell-governance" bash "$SCRIPT_DIR/redcap-architecture-smell-governance-check.sh" || overall=1
run_source_check "plan-only-followup-registration" bash "$SCRIPT_DIR/redcap-plan-only-followup-registration-check.sh" || overall=1
run_source_check "progress-meter" bash "$SCRIPT_DIR/redcap-progress-meter-check.sh" || overall=1
run_source_check "reference-asset-lifecycle" bash "$SCRIPT_DIR/redcap-reference-asset-lifecycle.sh" check || overall=1
run_source_check "layer-boundary" bash "$SCRIPT_DIR/redcap-layer-boundary-check.sh" || overall=1
run_check "tracking-health" bash "$SCRIPT_DIR/redcap-tracking-health.sh" "$TASK_FILE" || overall=1
run_check "intent-coverage" bash "$SCRIPT_DIR/redcap-intent-coverage-check.sh" "$TASK_FILE" || overall=1
run_check "change-intake" bash "$SCRIPT_DIR/redcap-change-intake-check.sh" "$TASK_FILE" --mode closeout || overall=1
run_source_check "mechanism-vitality" bash "$SCRIPT_DIR/redcap-mechanism-vitality-check.sh" || overall=1
run_source_check "evolution-grade-baseline" bash "$SCRIPT_DIR/redcap-evolution-grade-check.sh" || overall=1
run_source_check "evolution-candidates" bash "$SCRIPT_DIR/redcap-evolution-candidate-check.sh" || overall=1
run_check "evolution-harvest" bash "$SCRIPT_DIR/redcap-evolution-harvest-check.sh" "$TASK_FILE" || overall=1
run_source_check "skill-lifecycle" bash "$SCRIPT_DIR/redcap-skill-lifecycle-check.sh" || overall=1
run_source_check "legacy-asset-lifecycle" bash "$SCRIPT_DIR/redcap-legacy-asset-lifecycle-check.sh" || overall=1
run_source_check "human-output-quality" bash "$SCRIPT_DIR/redcap-human-output-quality-check.sh" --task-file "$TASK_FILE" || overall=1
run_source_check "contributing-ia" bash "$SCRIPT_DIR/redcap-contributing-ia-check.sh" || overall=1
run_source_check "review-tracks" bash "$SCRIPT_DIR/redcap-review-tracks-check.sh" || overall=1
run_source_check "conclusion-prism" bash "$SCRIPT_DIR/redcap-conclusion-prism-check.sh" || overall=1
run_source_check "prism-degradation" bash "$SCRIPT_DIR/redcap-prism-degradation-check.sh" --task-file "$TASK_FILE" --fail-on-action-required || overall=1
run_source_check "prism-evidence" bash "$REDCAP_ROOT/prism/tools/prism-evidence-check.sh" || overall=1
run_source_check "prism-runs-lifecycle" bash "$REDCAP_ROOT/prism/tools/prism-runs-lifecycle.sh" check || overall=1
run_check "prism-availability" bash "$REDCAP_ROOT/prism/tools/prism-availability.sh" status || overall=1
run_source_check "file-lookup-dictionary" bash "$SCRIPT_DIR/redcap-file-lookup-dictionary-check.sh" || overall=1
run_source_check "r0-r22-registry" bash "$SCRIPT_DIR/redcap-r0-r22-registry-check.sh" || overall=1
run_source_check "execution-layer-split-dry-run" bash "$SCRIPT_DIR/redcap-execution-layer-split-check.sh" || overall=1
run_source_check "legacy-asset-migration-dry-run" bash "$SCRIPT_DIR/redcap-legacy-asset-migration-check.sh" || overall=1
run_source_check "legacy-asset-migration-apply-preflight" bash "$SCRIPT_DIR/redcap-legacy-asset-migration-apply-plan.sh" || overall=1
legacy_rehearsal_mode="--check-result"
legacy_worktree_rehearsal_mode="--check-result"
if [[ -f "$REDCAP_ROOT/references/legacy-asset-migration-main-tree-apply.json" ]]; then
    legacy_rehearsal_mode="--check-stored-result-only"
    legacy_worktree_rehearsal_mode="--check-stored-result-only"
fi
run_source_check "legacy-asset-migration-rehearsal" bash "$SCRIPT_DIR/redcap-legacy-asset-migration-rehearsal.sh" "$legacy_rehearsal_mode" || overall=1
run_source_check "legacy-asset-migration-worktree-rehearsal" bash "$SCRIPT_DIR/redcap-legacy-asset-migration-worktree-rehearsal.sh" "$legacy_worktree_rehearsal_mode" || overall=1
run_source_check "legacy-asset-alias-resolver" bash "$SCRIPT_DIR/redcap-legacy-asset-alias-resolver.sh" --check-result || overall=1
run_source_check "legacy-asset-main-tree-apply" bash "$SCRIPT_DIR/redcap-legacy-asset-main-tree-apply.sh" --check-result || overall=1
run_source_check "legacy-asset-delete-last-preflight" bash "$SCRIPT_DIR/redcap-legacy-asset-delete-last-preflight.sh" --check-result || overall=1
if [[ -f "$REDCAP_ROOT/references/legacy-asset-delete-last-apply.json" ]]; then
    run_source_check "legacy-asset-delete-last-apply" bash "$SCRIPT_DIR/redcap-legacy-asset-delete-last-apply.sh" --check-result || overall=1
fi
run_source_check "parent-receipt-aggregation" bash "$SCRIPT_DIR/redcap-parent-receipt-aggregation-check.sh" || overall=1
run_source_check "shared-knowledge" bash "$SCRIPT_DIR/redcap-shared-knowledge-check.sh" || overall=1
run_source_check "shared-knowledge-remote-binding" bash "$SCRIPT_DIR/redcap-shared-knowledge-remote-check.sh" || overall=1
run_source_check "arsenal-version-binding" bash "$SCRIPT_DIR/redcap-arsenal-version-binding-check.sh" || overall=1
run_source_check "information-architecture" bash "$SCRIPT_DIR/redcap-information-architecture-check.sh" || overall=1
run_source_check "root-information-architecture" bash "$SCRIPT_DIR/redcap-root-information-architecture-check.sh" || overall=1
run_source_check "root-ia-deferral" bash "$SCRIPT_DIR/redcap-root-ia-deferral-check.sh" || overall=1
run_source_check "redcap-forge" bash "$SCRIPT_DIR/redcap-forge-check.sh" || overall=1
run_source_check "public-arsenal-claim-boundary" bash "$SCRIPT_DIR/redcap-public-arsenal-claim-boundary.sh" || overall=1
run_source_check "public-distillation-preflight" bash "$SCRIPT_DIR/redcap-public-distillation-preflight.sh" || overall=1
run_source_check "agent-reading-absorption" bash "$SCRIPT_DIR/redcap-agent-reading-absorption-check.sh" || overall=1
run_source_check "llm-wiki-asset-stratification" bash "$SCRIPT_DIR/redcap-llm-wiki-asset-stratification-check.sh" || overall=1
run_source_check "llm-wiki-lite" bash "$SCRIPT_DIR/redcap-llm-wiki-lite-check.sh" || overall=1
run_source_check "knowledge-gateway" bash "$SCRIPT_DIR/redcap-knowledge-gateway.sh" check || overall=1
run_source_check "cold-archive-inventory" bash "$SCRIPT_DIR/redcap-cold-archive-inventory.sh" check || overall=1
run_source_check "full-llm-wiki-roadmap" bash "$SCRIPT_DIR/redcap-full-llm-wiki-roadmap-check.sh" || overall=1
run_source_check "retrieval-escalation" bash "$SCRIPT_DIR/redcap-retrieval-escalation-check.sh" || overall=1
run_check "user-agent-identity" bash "$SCRIPT_DIR/redcap-user-agent-identity.sh" check --local || overall=1
run_source_check "feishu-inbox" bash "$SCRIPT_DIR/redcap-feishu-inbox.sh" check || overall=1
run_source_check "feishu-notification-policy" bash "$SCRIPT_DIR/redcap-feishu-notification-policy-check.sh" || overall=1
run_check "human-communication" bash "$SCRIPT_DIR/redcap-human-communication-check.sh" || overall=1
if [[ "${REDCAP_DIAGNOSE_SKIP_HUMAN_PRODUCT_SURFACE:-0}" == "1" ]]; then
    echo "[skip] human-product-surface reason=called-from-human-product-surface-check"
else
    run_check "human-product-surface" bash "$SCRIPT_DIR/redcap-human-product-surface-check.sh" || overall=1
fi
run_check "package-publish-safety" bash "$SCRIPT_DIR/redcap-package-publish-safety-check.sh" || overall=1
run_check "runtime-package-manifest" bash "$SCRIPT_DIR/redcap-runtime-package-manifest.sh" --check || overall=1
run_check "public-package-surface" bash "$SCRIPT_DIR/redcap-public-package-surface.sh" || overall=1
run_source_check "runtime-contract-surface" bash "$SCRIPT_DIR/redcap-runtime-contract-surface-check.sh" || overall=1
run_check "release-e2e-matrix" bash "$SCRIPT_DIR/redcap-release-e2e-matrix-check.sh" || overall=1
run_check "formal-release-r1-root-group-disposition" bash "$SCRIPT_DIR/redcap-formal-release-r1-root-group-disposition-check.sh" || overall=1
run_check "r1-control-plane-contract-split" bash "$SCRIPT_DIR/redcap-r1-control-plane-contract-split-check.sh" || overall=1
run_check "r1-prism-evidence-retention-split" bash "$SCRIPT_DIR/redcap-r1-prism-evidence-retention-split-check.sh" || overall=1
run_check "r1-layera-product-boundary" bash "$SCRIPT_DIR/redcap-r1-layera-product-boundary-check.sh" || overall=1
run_check "formal-release-readiness-plan" bash "$SCRIPT_DIR/redcap-formal-release-readiness-plan-check.sh" || overall=1
run_check "pre-release-product-architecture" bash "$SCRIPT_DIR/redcap-pre-release-product-architecture-check.sh" || overall=1
run_check "pre-release-structure-task-tree" bash "$SCRIPT_DIR/redcap-pre-release-structure-task-tree-check.sh" || overall=1
run_check "runtime-workspace-boundary" bash "$SCRIPT_DIR/redcap-runtime-workspace-boundary-check.sh" || overall=1
run_check "cli-product-surface" bash "$SCRIPT_DIR/redcap-cli-product-surface-check.sh" || overall=1
if [[ -f "$REDCAP_ROOT/references/clean-workspace-install-e2e.json" ]]; then
    run_source_check "clean-workspace-e2e" bash "$SCRIPT_DIR/redcap-clean-workspace-e2e.sh" --check-result || overall=1
fi
run_source_check "hook-contract" bash "$SCRIPT_DIR/redcap-hook-contract-check.sh" || overall=1
run_source_check "codex-hooks-candidate" bash "$SCRIPT_DIR/redcap-codex-hooks-check.sh" || overall=1
run_source_check "runtime-helper" bash "$SCRIPT_DIR/redcap-runtime-helper-check.sh" || overall=1
run_source_check "cli-console-mirror" bash "$SCRIPT_DIR/redcap-cli-console-mirror-check.sh" || overall=1
run_check "execution-guarantees" bash "$SCRIPT_DIR/redcap-execution-guarantee-check.sh" || overall=1
run_check "revival-protocol" bash "$SCRIPT_DIR/redcap-revival-check.sh" "$REDCAP_ROOT" || overall=1
run_source_check "spec-check" bash "$SCRIPT_DIR/redcap-spec-check.sh" "$REDCAP_ROOT" || overall=1

if [[ "$overall" -eq 0 ]]; then
    echo "DIAGNOSE_OK"
else
    echo "DIAGNOSE_FAIL"
fi
exit "$overall"

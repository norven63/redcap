#!/usr/bin/env bash
# shellcheck shell=bash
# Validate spec registry coverage, lifecycle policy, and changed spec entries.

set -uo pipefail

if [[ $# -lt 1 || $# -gt 3 ]]; then
    echo "usage: $0 <redcap_root> [baseline_head] [current_head]" >&2
    exit 2
fi

REDCAP_ROOT="$1"
BASELINE="${2:-}"
CURRENT_HEAD="${3:-}"
REGISTRY_PATH="$REDCAP_ROOT/references/spec-registry.json"
POLICY_PATH="$REDCAP_ROOT/references/spec-lifecycle-policy.json"
TMP_CHANGED_SPECS=$(mktemp)

cleanup() {
    rm -f "$TMP_CHANGED_SPECS" 2>/dev/null || true
}
trap cleanup EXIT

if [[ -n "$BASELINE" && -n "$CURRENT_HEAD" ]]; then
    git -C "$REDCAP_ROOT" --no-pager diff --diff-filter=ACMR --name-only "$BASELINE..$CURRENT_HEAD" -- \
        'compass/docs/specs/*.md' 'compass/docs/archive/specs/*.md' 2>/dev/null \
        | sed '/^[[:space:]]*$/d' | sort -u >"$TMP_CHANGED_SPECS"
else
    {
        git -C "$REDCAP_ROOT" --no-pager diff --name-only -- 'compass/docs/specs/*.md' 'compass/docs/archive/specs/*.md' 2>/dev/null
        git -C "$REDCAP_ROOT" --no-pager diff --cached --name-only -- 'compass/docs/specs/*.md' 'compass/docs/archive/specs/*.md' 2>/dev/null
    } | sed '/^[[:space:]]*$/d' | sort -u >"$TMP_CHANGED_SPECS"
fi

python3 - "$REDCAP_ROOT" "$REGISTRY_PATH" "$POLICY_PATH" "$TMP_CHANGED_SPECS" <<'PY'
import json
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(sys.argv[1])
REGISTRY_PATH = pathlib.Path(sys.argv[2])
POLICY_PATH = pathlib.Path(sys.argv[3])
CHANGED_PATH = pathlib.Path(sys.argv[4])


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-spec-check] {message}")


def load_json(path: pathlib.Path, label: str) -> dict:
    if not path.is_file():
        fail(f"{label} missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label} json: {exc}")


registry = load_json(REGISTRY_PATH, "spec registry")
policy = load_json(POLICY_PATH, "spec lifecycle policy")

if registry.get("version") != 1:
    fail("spec registry version must be 1")
if policy.get("version") != 1:
    fail("spec lifecycle policy version must be 1")

entries = registry.get("specs")
if not isinstance(entries, list) or not entries:
    fail("spec registry must define a non-empty specs array")

roots = policy.get("roots")
if not isinstance(roots, dict):
    fail("spec lifecycle policy must define roots")
active_root = roots.get("active")
archive_root = roots.get("archive")
if not isinstance(active_root, str) or not active_root.strip():
    fail("spec lifecycle policy missing roots.active")
if not isinstance(archive_root, str) or not archive_root.strip():
    fail("spec lifecycle policy missing roots.archive")
active_root = active_root.strip()
archive_root = archive_root.strip()

allowed_statuses = policy.get("allowed_statuses")
if not isinstance(allowed_statuses, list) or not allowed_statuses:
    fail("spec lifecycle policy must define allowed_statuses")
allowed_statuses = {status for status in allowed_statuses if isinstance(status, str) and status.strip()}
if not allowed_statuses:
    fail("spec lifecycle policy has no valid allowed_statuses")

allowed_roles = policy.get("allowed_roles")
if not isinstance(allowed_roles, list) or not allowed_roles:
    fail("spec lifecycle policy must define allowed_roles")
allowed_roles = {role for role in allowed_roles if isinstance(role, str) and role.strip()}
if not allowed_roles:
    fail("spec lifecycle policy has no valid allowed_roles")

filename_pattern = policy.get("filename_pattern")
if not isinstance(filename_pattern, str) or not filename_pattern.strip():
    fail("spec lifecycle policy missing filename_pattern")
try:
    filename_re = re.compile(filename_pattern)
except re.error as exc:
    fail(f"invalid spec lifecycle filename_pattern: {exc}")

summary_rule = policy.get("summary", {})
if not isinstance(summary_rule, dict):
    fail("spec lifecycle policy summary rule must be an object")
summary_min = int(summary_rule.get("min_length", 1))
summary_max = int(summary_rule.get("max_length", 1000))
if summary_min < 1 or summary_max < summary_min:
    fail("spec lifecycle policy summary length bounds are invalid")

status_rules = policy.get("status_rules")
if not isinstance(status_rules, dict) or not status_rules:
    fail("spec lifecycle policy must define status_rules")
for status in allowed_statuses:
    if status not in status_rules:
        fail(f"spec lifecycle policy missing status rule for {status}")


def collect_specs(rel_root: str) -> set[str]:
    root = REPO_ROOT / rel_root
    if not root.exists():
        return set()
    return {
        path.relative_to(REPO_ROOT).as_posix()
        for path in sorted(root.glob("*.md"))
        if path.is_file()
    }


repo_specs = collect_specs(active_root) | collect_specs(archive_root)


def classify_root(path: str) -> str:
    if path.startswith(active_root + "/"):
        return "active"
    if path.startswith(archive_root + "/"):
        return "archive"
    fail(f"spec must live under {active_root}/ or {archive_root}/: {path}")


registry_map: dict[str, dict] = {}
for entry in entries:
    if not isinstance(entry, dict):
        fail("spec registry entries must be objects")
    path = entry.get("path")
    if not isinstance(path, str) or not path.strip():
        fail("spec registry entry missing path")
    path = path.strip()
    if path in registry_map:
        fail(f"duplicate spec registry path: {path}")
    filename = pathlib.PurePosixPath(path).name
    if not filename_re.fullmatch(filename):
        fail(f"spec filename violates lifecycle policy: {path}")

    title = entry.get("title")
    if not isinstance(title, str) or not title.strip():
        fail(f"spec registry entry missing title: {path}")

    role = entry.get("role")
    if role not in allowed_roles:
        fail(f"spec registry entry uses unsupported role ({role}): {path}")

    status = entry.get("status")
    if status not in allowed_statuses:
        fail(f"spec registry entry uses unsupported status ({status}): {path}")

    root_alias = classify_root(path)
    status_rule = status_rules.get(status)
    if not isinstance(status_rule, dict):
        fail(f"spec lifecycle policy status rule must be an object: {status}")
    allowed_roots = status_rule.get("allowed_roots", [])
    if not isinstance(allowed_roots, list) or not allowed_roots:
        fail(f"spec lifecycle policy missing allowed_roots for status {status}")
    if root_alias not in allowed_roots:
        fail(f"spec status {status} cannot live under {root_alias} root: {path}")

    if entry.get("runtime_authority") is not False:
        fail(f"spec registry entry must declare runtime_authority=false: {path}")

    summary = entry.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        fail(f"spec registry entry missing summary: {path}")
    normalized_summary = " ".join(summary.split())
    if not (summary_min <= len(normalized_summary) <= summary_max):
        fail(f"spec registry entry summary length violates policy: {path}")

    control_paths = entry.get("paired_control_paths", [])
    debt_ids = entry.get("paired_debt_ids", [])
    if not isinstance(control_paths, list) or not isinstance(debt_ids, list):
        fail(f"spec registry entry has invalid paired paths/debts: {path}")
    if not control_paths and not debt_ids:
        fail(f"spec registry entry must declare paired_control_paths or paired_debt_ids: {path}")
    for control_path in control_paths:
        if not isinstance(control_path, str) or not control_path.strip():
            fail(f"spec registry entry has invalid paired_control_path: {path}")
        abs_control_path = REPO_ROOT / control_path
        if not abs_control_path.exists():
            fail(f"spec registry entry points to missing control path: {control_path}")
    for debt_id in debt_ids:
        if not isinstance(debt_id, str) or not debt_id.strip():
            fail(f"spec registry entry has invalid paired_debt_id: {path}")

    replaced_by = entry.get("replaced_by")
    requires_replacement = bool(status_rule.get("require_replaced_by"))
    if requires_replacement:
        if not isinstance(replaced_by, str) or not replaced_by.strip():
            fail(f"superseded spec missing replaced_by: {path}")
        replaced_by = replaced_by.strip()
        entry["replaced_by"] = replaced_by
    elif replaced_by is not None:
        if not isinstance(replaced_by, str) or not replaced_by.strip():
            fail(f"spec registry entry has invalid replaced_by: {path}")
        entry["replaced_by"] = replaced_by.strip()

    registry_map[path] = entry

missing_from_registry = sorted(repo_specs - set(registry_map.keys()))
if missing_from_registry:
    fail("specs missing from registry: " + ", ".join(missing_from_registry))

extra_registry_entries = sorted(set(registry_map.keys()) - repo_specs)
if extra_registry_entries:
    fail("spec registry references missing specs: " + ", ".join(extra_registry_entries))

for path, entry in registry_map.items():
    replaced_by = entry.get("replaced_by")
    if replaced_by is None:
        continue
    if replaced_by == path:
        fail(f"spec replaced_by cannot point to itself: {path}")
    if replaced_by not in registry_map:
        fail(f"spec replaced_by target missing from registry: {path} -> {replaced_by}")
    seen = {path}
    cursor = replaced_by
    while cursor in registry_map:
        if cursor in seen:
            fail(f"spec replacement chain contains cycle: {path} -> {cursor}")
        seen.add(cursor)
        cursor = registry_map[cursor].get("replaced_by")
        if cursor is None:
            break

changed_specs = [
    line.strip()
    for line in CHANGED_PATH.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
for spec_path in changed_specs:
    if spec_path not in registry_map:
        fail(f"changed spec missing from registry: {spec_path}")

if changed_specs:
    print("\n".join(changed_specs))
PY
SPEC_CHECK_STATUS=$?
if [[ "$SPEC_CHECK_STATUS" -ne 0 ]]; then
    exit "$SPEC_CHECK_STATUS"
fi

DOCS_CATALOG_CHECK="$REDCAP_ROOT/compass/tools/redcap-docs-catalog.sh"
if [[ -x "$DOCS_CATALOG_CHECK" ]]; then
    if ! REDCAP_DOCS_CATALOG_PATH="$REDCAP_ROOT/compass/docs/catalog.json" bash "$DOCS_CATALOG_CHECK" check >/dev/null; then
        echo "[redcap-spec-check] docs catalog check failed" >&2
        exit 1
    fi
    if ! REDCAP_DOCS_CATALOG_PATH="$REDCAP_ROOT/compass/docs/catalog.json" bash "$DOCS_CATALOG_CHECK" retention-check >/dev/null; then
        echo "[redcap-spec-check] docs retention check failed" >&2
        exit 1
    fi
fi

EXECUTION_GUARANTEE_CHECK="$REDCAP_ROOT/compass/tools/redcap-execution-guarantee-check.sh"
if [[ -x "$EXECUTION_GUARANTEE_CHECK" ]]; then
    if ! bash "$EXECUTION_GUARANTEE_CHECK" >/dev/null; then
        echo "[redcap-spec-check] execution guarantee check failed" >&2
        exit 1
    fi
fi

KNOWLEDGE_INDEX_CHECK="$REDCAP_ROOT/compass/tools/redcap-knowledge-index-check.sh"
if [[ -x "$KNOWLEDGE_INDEX_CHECK" ]]; then
    if ! bash "$KNOWLEDGE_INDEX_CHECK" >/dev/null; then
        echo "[redcap-spec-check] knowledge index check failed" >&2
        exit 1
    fi
fi

OVERLAY_GOVERNANCE_CHECK="$REDCAP_ROOT/compass/tools/redcap-overlay-governance-check.sh"
if [[ -x "$OVERLAY_GOVERNANCE_CHECK" ]]; then
    if ! bash "$OVERLAY_GOVERNANCE_CHECK" >/dev/null; then
        echo "[redcap-spec-check] overlay governance check failed" >&2
        exit 1
    fi
fi

STATE_MACHINE_CHECK="$REDCAP_ROOT/compass/tools/redcap-state-machine-check.sh"
if [[ -x "$STATE_MACHINE_CHECK" ]]; then
    if ! bash "$STATE_MACHINE_CHECK" >/dev/null; then
        echo "[redcap-spec-check] state machine contract check failed" >&2
        exit 1
    fi
fi

LAYERB_LIFECYCLE_CHECK="$REDCAP_ROOT/compass/tools/redcap-layerb-lifecycle-check.sh"
if [[ -x "$LAYERB_LIFECYCLE_CHECK" ]]; then
    if ! bash "$LAYERB_LIFECYCLE_CHECK" >/dev/null; then
        echo "[redcap-spec-check] layerb lifecycle contract check failed" >&2
        exit 1
    fi
fi

TOKEN_RISK_AUDIT="$REDCAP_ROOT/compass/tools/redcap-token-risk-audit.sh"
if [[ -x "$TOKEN_RISK_AUDIT" ]]; then
    if ! bash "$TOKEN_RISK_AUDIT" >/dev/null; then
        echo "[redcap-spec-check] token risk audit failed" >&2
        exit 1
    fi
fi

CONTRIBUTING_IA_CHECK="$REDCAP_ROOT/compass/tools/redcap-contributing-ia-check.sh"
if [[ -x "$CONTRIBUTING_IA_CHECK" ]]; then
    if ! bash "$CONTRIBUTING_IA_CHECK" >/dev/null; then
        echo "[redcap-spec-check] contributing IA check failed" >&2
        exit 1
    fi
fi

REVIEW_TRACKS_CHECK="$REDCAP_ROOT/compass/tools/redcap-review-tracks-check.sh"
if [[ -x "$REVIEW_TRACKS_CHECK" ]]; then
    if ! bash "$REVIEW_TRACKS_CHECK" >/dev/null; then
        echo "[redcap-spec-check] review tracks check failed" >&2
        exit 1
    fi
fi

HOOK_CONTRACT_CHECK="$REDCAP_ROOT/compass/tools/redcap-hook-contract-check.sh"
if [[ -x "$HOOK_CONTRACT_CHECK" ]]; then
    if ! bash "$HOOK_CONTRACT_CHECK" >/dev/null; then
        echo "[redcap-spec-check] hook contract check failed" >&2
        exit 1
    fi
fi

LAYERB_FSM_CHECK="$REDCAP_ROOT/compass/tools/redcap-layerb-fsm-check.sh"
if [[ -x "$LAYERB_FSM_CHECK" ]]; then
    if ! bash "$LAYERB_FSM_CHECK" >/dev/null; then
        echo "[redcap-spec-check] layerb fsm check failed" >&2
        exit 1
    fi
fi

RUNTIME_HELPER_CHECK="$REDCAP_ROOT/compass/tools/redcap-runtime-helper-check.sh"
if [[ -x "$RUNTIME_HELPER_CHECK" ]]; then
    if ! bash "$RUNTIME_HELPER_CHECK" >/dev/null; then
        echo "[redcap-spec-check] runtime helper check failed" >&2
        exit 1
    fi
fi

CLI_CONSOLE_CHECK="$REDCAP_ROOT/compass/tools/redcap-cli-console-mirror-check.sh"
if [[ -x "$CLI_CONSOLE_CHECK" ]]; then
    if ! bash "$CLI_CONSOLE_CHECK" >/dev/null; then
        echo "[redcap-spec-check] cli console mirror check failed" >&2
        exit 1
    fi
fi

REVIVAL_CHECK="$REDCAP_ROOT/compass/tools/redcap-revival-check.sh"
if [[ -x "$REVIVAL_CHECK" ]]; then
    if ! bash "$REVIVAL_CHECK" >/dev/null; then
        echo "[redcap-spec-check] revival check failed" >&2
        exit 1
    fi
fi

MECHANISM_VITALITY_CHECK="$REDCAP_ROOT/compass/tools/redcap-mechanism-vitality-check.sh"
if [[ -x "$MECHANISM_VITALITY_CHECK" ]]; then
    if ! bash "$MECHANISM_VITALITY_CHECK" >/dev/null; then
        echo "[redcap-spec-check] mechanism vitality check failed" >&2
        exit 1
    fi
fi

EVOLUTION_GRADE_CHECK="$REDCAP_ROOT/compass/tools/redcap-evolution-grade-check.sh"
if [[ -x "$EVOLUTION_GRADE_CHECK" ]]; then
    if ! bash "$EVOLUTION_GRADE_CHECK" >/dev/null; then
        echo "[redcap-spec-check] evolution grade baseline check failed" >&2
        exit 1
    fi
fi

EVOLUTION_CANDIDATE_CHECK="$REDCAP_ROOT/compass/tools/redcap-evolution-candidate-check.sh"
if [[ -x "$EVOLUTION_CANDIDATE_CHECK" ]]; then
    if ! bash "$EVOLUTION_CANDIDATE_CHECK" >/dev/null; then
        echo "[redcap-spec-check] evolution candidate check failed" >&2
        exit 1
    fi
fi

SKILL_LIFECYCLE_CHECK="$REDCAP_ROOT/compass/tools/redcap-skill-lifecycle-check.sh"
if [[ -x "$SKILL_LIFECYCLE_CHECK" ]]; then
    if ! bash "$SKILL_LIFECYCLE_CHECK" >/dev/null; then
        echo "[redcap-spec-check] skill lifecycle check failed" >&2
        exit 1
    fi
fi

LEGACY_ASSET_LIFECYCLE_CHECK="$REDCAP_ROOT/compass/tools/redcap-legacy-asset-lifecycle-check.sh"
if [[ -x "$LEGACY_ASSET_LIFECYCLE_CHECK" ]]; then
    if ! bash "$LEGACY_ASSET_LIFECYCLE_CHECK" >/dev/null; then
        echo "[redcap-spec-check] legacy asset lifecycle check failed" >&2
        exit 1
    fi
fi

FILE_LOOKUP_DICTIONARY_CHECK="$REDCAP_ROOT/compass/tools/redcap-file-lookup-dictionary-check.sh"
if [[ -x "$FILE_LOOKUP_DICTIONARY_CHECK" ]]; then
    if ! bash "$FILE_LOOKUP_DICTIONARY_CHECK" >/dev/null; then
        echo "[redcap-spec-check] file lookup dictionary check failed" >&2
        exit 1
    fi
fi

R0_R22_REGISTRY_CHECK="$REDCAP_ROOT/compass/tools/redcap-r0-r22-registry-check.sh"
if [[ -x "$R0_R22_REGISTRY_CHECK" ]]; then
    if ! bash "$R0_R22_REGISTRY_CHECK" >/dev/null; then
        echo "[redcap-spec-check] R0-R22 registry check failed" >&2
        exit 1
    fi
fi

EXECUTION_LAYER_SPLIT_CHECK="$REDCAP_ROOT/compass/tools/redcap-execution-layer-split-check.sh"
if [[ -x "$EXECUTION_LAYER_SPLIT_CHECK" ]]; then
    if ! bash "$EXECUTION_LAYER_SPLIT_CHECK" >/dev/null; then
        echo "[redcap-spec-check] execution layer split dry-run check failed" >&2
        exit 1
    fi
fi

LEGACY_ASSET_MIGRATION_CHECK="$REDCAP_ROOT/compass/tools/redcap-legacy-asset-migration-check.sh"
if [[ -x "$LEGACY_ASSET_MIGRATION_CHECK" ]]; then
    if ! bash "$LEGACY_ASSET_MIGRATION_CHECK" >/dev/null; then
        echo "[redcap-spec-check] legacy asset migration dry-run check failed" >&2
        exit 1
    fi
fi

LEGACY_ASSET_APPLY_PREFLIGHT_CHECK="$REDCAP_ROOT/compass/tools/redcap-legacy-asset-migration-apply-plan.sh"
if [[ -x "$LEGACY_ASSET_APPLY_PREFLIGHT_CHECK" ]]; then
    if ! bash "$LEGACY_ASSET_APPLY_PREFLIGHT_CHECK" >/dev/null; then
        echo "[redcap-spec-check] legacy asset migration apply preflight check failed" >&2
        exit 1
    fi
fi

LEGACY_ASSET_REHEARSAL_CHECK="$REDCAP_ROOT/compass/tools/redcap-legacy-asset-migration-rehearsal.sh"
if [[ -x "$LEGACY_ASSET_REHEARSAL_CHECK" ]]; then
    LEGACY_ASSET_REHEARSAL_MODE="--check-result"
    if [[ -f "$REDCAP_ROOT/references/legacy-asset-migration-main-tree-apply.json" ]]; then
        LEGACY_ASSET_REHEARSAL_MODE="--check-stored-result-only"
    fi
    if ! bash "$LEGACY_ASSET_REHEARSAL_CHECK" "$LEGACY_ASSET_REHEARSAL_MODE" >/dev/null; then
        echo "[redcap-spec-check] legacy asset migration rehearsal check failed" >&2
        exit 1
    fi
fi

LEGACY_ASSET_WORKTREE_REHEARSAL_CHECK="$REDCAP_ROOT/compass/tools/redcap-legacy-asset-migration-worktree-rehearsal.sh"
if [[ -x "$LEGACY_ASSET_WORKTREE_REHEARSAL_CHECK" ]]; then
    LEGACY_ASSET_WORKTREE_REHEARSAL_MODE="--check-result"
    if [[ -f "$REDCAP_ROOT/references/legacy-asset-migration-main-tree-apply.json" ]]; then
        LEGACY_ASSET_WORKTREE_REHEARSAL_MODE="--check-stored-result-only"
    fi
    if ! bash "$LEGACY_ASSET_WORKTREE_REHEARSAL_CHECK" "$LEGACY_ASSET_WORKTREE_REHEARSAL_MODE" >/dev/null; then
        echo "[redcap-spec-check] legacy asset migration worktree rehearsal check failed" >&2
        exit 1
    fi
fi

LEGACY_ASSET_ALIAS_RESOLVER_CHECK="$REDCAP_ROOT/compass/tools/redcap-legacy-asset-alias-resolver.sh"
if [[ -x "$LEGACY_ASSET_ALIAS_RESOLVER_CHECK" ]]; then
    if ! bash "$LEGACY_ASSET_ALIAS_RESOLVER_CHECK" --check-result >/dev/null; then
        echo "[redcap-spec-check] legacy asset alias resolver check failed" >&2
        exit 1
    fi
fi

LEGACY_ASSET_MAIN_TREE_APPLY_CHECK="$REDCAP_ROOT/compass/tools/redcap-legacy-asset-main-tree-apply.sh"
if [[ -x "$LEGACY_ASSET_MAIN_TREE_APPLY_CHECK" ]]; then
    if ! bash "$LEGACY_ASSET_MAIN_TREE_APPLY_CHECK" --check-result >/dev/null; then
        echo "[redcap-spec-check] legacy asset main-tree apply check failed" >&2
        exit 1
    fi
fi

LEGACY_ASSET_DELETE_LAST_PREFLIGHT_CHECK="$REDCAP_ROOT/compass/tools/redcap-legacy-asset-delete-last-preflight.sh"
if [[ -x "$LEGACY_ASSET_DELETE_LAST_PREFLIGHT_CHECK" ]]; then
    if ! bash "$LEGACY_ASSET_DELETE_LAST_PREFLIGHT_CHECK" --check-result >/dev/null; then
        echo "[redcap-spec-check] legacy asset delete-last preflight check failed" >&2
        exit 1
    fi
fi

LEGACY_ASSET_DELETE_LAST_APPLY_CHECK="$REDCAP_ROOT/compass/tools/redcap-legacy-asset-delete-last-apply.sh"
if [[ -x "$LEGACY_ASSET_DELETE_LAST_APPLY_CHECK" && -f "$REDCAP_ROOT/references/legacy-asset-delete-last-apply.json" ]]; then
    if ! bash "$LEGACY_ASSET_DELETE_LAST_APPLY_CHECK" --check-result >/dev/null; then
        echo "[redcap-spec-check] legacy asset delete-last apply check failed" >&2
        exit 1
    fi
fi

PARENT_RECEIPT_AGGREGATION_CHECK="$REDCAP_ROOT/compass/tools/redcap-parent-receipt-aggregation-check.sh"
if [[ -x "$PARENT_RECEIPT_AGGREGATION_CHECK" ]]; then
    if ! bash "$PARENT_RECEIPT_AGGREGATION_CHECK" >/dev/null; then
        echo "[redcap-spec-check] parent receipt aggregation check failed" >&2
        exit 1
    fi
fi

SHARED_KNOWLEDGE_CHECK="$REDCAP_ROOT/compass/tools/redcap-shared-knowledge-check.sh"
if [[ -x "$SHARED_KNOWLEDGE_CHECK" ]]; then
    if ! bash "$SHARED_KNOWLEDGE_CHECK" >/dev/null; then
        echo "[redcap-spec-check] shared knowledge check failed" >&2
        exit 1
    fi
fi

SHARED_KNOWLEDGE_REMOTE_CHECK="$REDCAP_ROOT/compass/tools/redcap-shared-knowledge-remote-check.sh"
if [[ -x "$SHARED_KNOWLEDGE_REMOTE_CHECK" ]]; then
    if ! bash "$SHARED_KNOWLEDGE_REMOTE_CHECK" >/dev/null; then
        echo "[redcap-spec-check] shared knowledge remote binding check failed" >&2
        exit 1
    fi
fi

INFORMATION_ARCHITECTURE_CHECK="$REDCAP_ROOT/compass/tools/redcap-information-architecture-check.sh"
if [[ -x "$INFORMATION_ARCHITECTURE_CHECK" ]]; then
    if ! bash "$INFORMATION_ARCHITECTURE_CHECK" >/dev/null; then
        echo "[redcap-spec-check] information architecture check failed" >&2
        exit 1
    fi
fi

REDCAP_FORGE_CHECK="$REDCAP_ROOT/compass/tools/redcap-forge-check.sh"
if [[ -x "$REDCAP_FORGE_CHECK" ]]; then
    if ! bash "$REDCAP_FORGE_CHECK" >/dev/null; then
        echo "[redcap-spec-check] RedCap Forge check failed" >&2
        exit 1
    fi
fi

RETRIEVAL_ESCALATION_CHECK="$REDCAP_ROOT/compass/tools/redcap-retrieval-escalation-check.sh"
if [[ -x "$RETRIEVAL_ESCALATION_CHECK" ]]; then
    if ! bash "$RETRIEVAL_ESCALATION_CHECK" >/dev/null; then
        echo "[redcap-spec-check] retrieval escalation check failed" >&2
        exit 1
    fi
fi

USER_AGENT_IDENTITY_CHECK="$REDCAP_ROOT/compass/tools/redcap-user-agent-identity.sh"
if [[ ! -f "$USER_AGENT_IDENTITY_CHECK" ]]; then
    echo "[redcap-spec-check] user/agent identity check missing" >&2
    exit 1
fi
if ! bash "$USER_AGENT_IDENTITY_CHECK" check >/dev/null; then
    echo "[redcap-spec-check] user/agent identity policy check failed" >&2
    exit 1
fi

FEISHU_NOTIFICATION_POLICY_CHECK="$REDCAP_ROOT/compass/tools/redcap-feishu-notification-policy-check.sh"
if [[ ! -f "$FEISHU_NOTIFICATION_POLICY_CHECK" ]]; then
    echo "[redcap-spec-check] Feishu notification policy check missing" >&2
    exit 1
fi
if ! bash "$FEISHU_NOTIFICATION_POLICY_CHECK" >/dev/null; then
    echo "[redcap-spec-check] Feishu notification policy check failed" >&2
    exit 1
fi

HUMAN_COMMUNICATION_CHECK="$REDCAP_ROOT/compass/tools/redcap-human-communication-check.sh"
if [[ ! -f "$HUMAN_COMMUNICATION_CHECK" ]]; then
    echo "[redcap-spec-check] human communication check missing" >&2
    exit 1
fi
if ! bash "$HUMAN_COMMUNICATION_CHECK" >/dev/null; then
    echo "[redcap-spec-check] human communication check failed" >&2
    exit 1
fi

PACKAGE_PUBLISH_SAFETY_CHECK="$REDCAP_ROOT/compass/tools/redcap-package-publish-safety-check.sh"
if [[ ! -f "$PACKAGE_PUBLISH_SAFETY_CHECK" ]]; then
    echo "[redcap-spec-check] package publish safety check missing" >&2
    exit 1
fi
if ! bash "$PACKAGE_PUBLISH_SAFETY_CHECK" >/dev/null; then
    echo "[redcap-spec-check] package publish safety check failed" >&2
    exit 1
fi

RUNTIME_PACKAGE_MANIFEST_CHECK="$REDCAP_ROOT/compass/tools/redcap-runtime-package-manifest.sh"
if [[ ! -f "$RUNTIME_PACKAGE_MANIFEST_CHECK" ]]; then
    echo "[redcap-spec-check] runtime package manifest check missing" >&2
    exit 1
fi
if ! bash "$RUNTIME_PACKAGE_MANIFEST_CHECK" --check >/dev/null; then
    echo "[redcap-spec-check] runtime package manifest check failed" >&2
    exit 1
fi

PUBLIC_PACKAGE_SURFACE_CHECK="$REDCAP_ROOT/compass/tools/redcap-public-package-surface.sh"
if [[ ! -f "$PUBLIC_PACKAGE_SURFACE_CHECK" ]]; then
    echo "[redcap-spec-check] public package surface check missing" >&2
    exit 1
fi
if ! bash "$PUBLIC_PACKAGE_SURFACE_CHECK" >/dev/null; then
    echo "[redcap-spec-check] public package surface check failed" >&2
    exit 1
fi

PRE_RELEASE_PRODUCT_ARCHITECTURE_CHECK="$REDCAP_ROOT/compass/tools/redcap-pre-release-product-architecture-check.sh"
if [[ ! -f "$PRE_RELEASE_PRODUCT_ARCHITECTURE_CHECK" ]]; then
    echo "[redcap-spec-check] pre-release product architecture check missing" >&2
    exit 1
fi
if ! bash "$PRE_RELEASE_PRODUCT_ARCHITECTURE_CHECK" >/dev/null; then
    echo "[redcap-spec-check] pre-release product architecture check failed" >&2
    exit 1
fi

PRE_RELEASE_STRUCTURE_TASK_TREE_CHECK="$REDCAP_ROOT/compass/tools/redcap-pre-release-structure-task-tree-check.sh"
if [[ ! -f "$PRE_RELEASE_STRUCTURE_TASK_TREE_CHECK" ]]; then
    echo "[redcap-spec-check] pre-release structure task tree check missing" >&2
    exit 1
fi
if ! bash "$PRE_RELEASE_STRUCTURE_TASK_TREE_CHECK" >/dev/null; then
    echo "[redcap-spec-check] pre-release structure task tree check failed" >&2
    exit 1
fi

RUNTIME_WORKSPACE_BOUNDARY_CHECK="$REDCAP_ROOT/compass/tools/redcap-runtime-workspace-boundary-check.sh"
if [[ ! -f "$RUNTIME_WORKSPACE_BOUNDARY_CHECK" ]]; then
    echo "[redcap-spec-check] runtime workspace boundary check missing" >&2
    exit 1
fi
if ! bash "$RUNTIME_WORKSPACE_BOUNDARY_CHECK" >/dev/null; then
    echo "[redcap-spec-check] runtime workspace boundary check failed" >&2
    exit 1
fi

CLI_PRODUCT_SURFACE_CHECK="$REDCAP_ROOT/compass/tools/redcap-cli-product-surface-check.sh"
if [[ ! -f "$CLI_PRODUCT_SURFACE_CHECK" ]]; then
    echo "[redcap-spec-check] CLI product surface check missing" >&2
    exit 1
fi
if ! bash "$CLI_PRODUCT_SURFACE_CHECK" >/dev/null; then
    echo "[redcap-spec-check] CLI product surface check failed" >&2
    exit 1
fi

CLEAN_WORKSPACE_E2E_CHECK="$REDCAP_ROOT/compass/tools/redcap-clean-workspace-e2e.sh"
if [[ -f "$REDCAP_ROOT/references/clean-workspace-install-e2e.json" ]]; then
    if [[ ! -f "$CLEAN_WORKSPACE_E2E_CHECK" ]]; then
        echo "[redcap-spec-check] clean workspace E2E check missing" >&2
        exit 1
    fi
    if ! bash "$CLEAN_WORKSPACE_E2E_CHECK" --check-result >/dev/null; then
        echo "[redcap-spec-check] clean workspace E2E result check failed" >&2
        exit 1
    fi
fi

CHANGE_INTAKE_CHECK="$REDCAP_ROOT/compass/tools/redcap-change-intake-check.sh"
if [[ ! -f "$CHANGE_INTAKE_CHECK" ]]; then
    echo "[redcap-spec-check] change intake check missing" >&2
    exit 1
fi
if [[ -f "$REDCAP_ROOT/.dev-task.md" ]]; then
    if ! bash "$CHANGE_INTAKE_CHECK" "$REDCAP_ROOT/.dev-task.md" >/dev/null; then
        echo "[redcap-spec-check] change intake check failed" >&2
        exit 1
    fi
fi

PRISM_AVAILABILITY_CHECK="$REDCAP_ROOT/prism/tools/prism-availability.sh"
if [[ -x "$PRISM_AVAILABILITY_CHECK" ]]; then
    if ! bash "$PRISM_AVAILABILITY_CHECK" status >/dev/null; then
        echo "[redcap-spec-check] prism availability check failed" >&2
        exit 1
    fi
fi

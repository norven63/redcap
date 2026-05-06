#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "references/llm-wiki-asset-stratification-policy.json"
TASK_TREE = ROOT / "references/pre-release-structure-refactor-task-tree.json"
PARENT_LEDGER = ROOT / "references/redcap-parent-task-ledger.md"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-llm-wiki-asset-stratification] {message}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing json: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid json {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{path} must be a JSON object")
    return payload


def require_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        fail(f"{key} must be a non-empty list")
    return value


def ids(items: list[Any]) -> set[str]:
    return {str(item.get("id", "")) for item in items if isinstance(item, dict)}


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("version") != 1:
        fail("version must be 1")
    if policy.get("policy_id") != "llm-wiki-asset-stratification":
        fail("policy_id must be llm-wiki-asset-stratification")
    if policy.get("parent_child_id") != "P4-2h-2":
        fail("parent_child_id must be P4-2h-2")
    if policy.get("status") != "assessment-completed-requirement-registered":
        fail("status must be assessment-completed-requirement-registered")

    role = policy.get("llm_wiki_role")
    if not isinstance(role, dict):
        fail("llm_wiki_role must be an object")
    if role.get("classification") != "private-semantic-memory-cache":
        fail("LLM-wiki must remain a private semantic memory cache")
    if role.get("authority") != "non-authoritative-derived-context":
        fail("LLM-wiki must be non-authoritative derived context")
    if role.get("public_by_default") is not False:
        fail("LLM-wiki must not be public by default")

    asset_layers = require_list(policy, "asset_layers")
    required_assets = {
        "current-task-truth",
        "entry-host-surfaces",
        "control-policies-references",
        "tools-runtime",
        "active-docs-inbox",
        "active-private-knowledge",
        "private-knowledge-archive",
        "prism-formal-reports",
        "prism-runtime-runs",
        "evolution-factory",
        "shared-knowledge-template",
        "external-redcap-arsenal",
        "indexes-and-dictionaries",
        "package-surface",
    }
    missing = sorted(required_assets - ids(asset_layers))
    if missing:
        fail(f"asset_layers missing: {', '.join(missing)}")

    dispositions = {
        str(item.get("id")): str(item.get("llm_wiki_disposition", ""))
        for item in asset_layers
        if isinstance(item, dict)
    }
    forbidden_or_anchor = {
        "current-task-truth": "forbidden",
        "prism-runtime-runs": "forbidden-raw-source-only",
        "indexes-and-dictionaries": "forbidden",
    }
    for asset_id, expected in forbidden_or_anchor.items():
        if dispositions.get(asset_id) != expected:
            fail(f"{asset_id} disposition must be {expected}")
    if dispositions.get("control-policies-references") != "derived-summary-only":
        fail("control policies must be derived-summary-only, not wiki authority")
    if dispositions.get("entry-host-surfaces") != "metadata-only":
        fail("entry host surfaces must be metadata-only")

    candidate_types = require_list(policy, "llm_wiki_candidate_types")
    candidate_ids = ids(candidate_types)
    for required in [
        "stable-concept",
        "design-philosophy",
        "glossary",
        "user-preference-derived-summary",
        "repeated-failure-pattern",
        "decision-framework",
        "task-specific-state",
        "raw-private-transcript",
        "executable-code",
    ]:
        if required not in candidate_ids:
            fail(f"candidate type missing: {required}")
    by_id = {str(item.get("id")): item for item in candidate_types if isinstance(item, dict)}
    for forbidden in ["task-specific-state", "raw-private-transcript", "executable-code"]:
        if by_id[forbidden].get("allowed") is not False:
            fail(f"{forbidden} must be forbidden")

    source_anchor = policy.get("source_anchor_contract")
    if not isinstance(source_anchor, dict):
        fail("source_anchor_contract must be an object")
    if source_anchor.get("required") is not True:
        fail("source anchors must be required")
    for field in ["source_path", "source_kind", "commit_sha_or_digest", "last_reviewed_at", "privacy_classification"]:
        if field not in require_list(source_anchor, "minimum_fields"):
            fail(f"source anchor minimum field missing: {field}")
    if "Do not inline raw private" not in str(source_anchor.get("raw_excerpt_rule", "")):
        fail("raw excerpt rule must forbid inlining raw private passages")
    if "stale" not in str(source_anchor.get("staleness_rule", "")).lower():
        fail("staleness rule must be explicit")

    privacy = policy.get("privacy_and_publication")
    if not isinstance(privacy, dict):
        fail("privacy_and_publication must be an object")
    if privacy.get("default_wiki_visibility") != "private":
        fail("default wiki visibility must be private")
    if privacy.get("public_export") != "forbidden-without-forge-promotion":
        fail("public export must require Forge promotion")

    retrieval = policy.get("retrieval_boundary")
    if not isinstance(retrieval, dict):
        fail("retrieval_boundary must be an object")
    if retrieval.get("current_default") != "catalog-rg-metadata":
        fail("retrieval default must remain catalog-rg-metadata")
    if retrieval.get("rag_or_graphrag") != "deferred-to-retrieval-escalation-policy":
        fail("RAG/GraphRAG must remain deferred to retrieval escalation policy")

    followup = policy.get("registered_followup_requirement")
    if not isinstance(followup, dict):
        fail("registered_followup_requirement must be an object")
    if followup.get("id") != "P4-2h-3":
        fail("follow-up requirement must be P4-2h-3")
    followup_status = followup.get("status")
    if followup_status not in {"planned", "completed"}:
        fail("P4-2h-3 status must be planned or completed")
    if followup_status == "completed":
        evidence = followup.get("implementation_evidence")
        if not isinstance(evidence, list) or not evidence:
            fail("completed P4-2h-3 must declare implementation_evidence")
        for path in evidence:
            if not isinstance(path, str) or not path.strip():
                fail("completed P4-2h-3 implementation_evidence entries must be strings")
            if not (ROOT / path).exists():
                fail(f"completed P4-2h-3 implementation_evidence missing: {path}")
    if followup.get("release_blocker") is not False:
        fail("P4-2h-3 must not be a public release blocker by default")

    claims = [str(item) for item in require_list(policy, "must_not_claim")]
    for phrase in ["complete LLM-wiki", "source of truth", "raw private", "catalog + rg + metadata", "RAG or GraphRAG"]:
        if not any(phrase in claim for claim in claims):
            fail(f"must_not_claim missing phrase: {phrase}")


def validate_task_tree(policy: dict[str, Any]) -> None:
    tree = load_json(TASK_TREE)
    nodes = tree.get("nodes")
    if not isinstance(nodes, list):
        fail("task tree nodes must be a list")
    by_id = {str(node.get("id")): node for node in nodes if isinstance(node, dict)}
    for required in ["P4-2h-2", "P4-2h-3"]:
        if required not in by_id:
            fail(f"task tree missing {required}")
    if by_id["P4-2h-2"].get("status") != "completed":
        fail("P4-2h-2 must be completed after this assessment")
    expected_status = policy["registered_followup_requirement"].get("status")
    if by_id["P4-2h-3"].get("status") != expected_status:
        fail(f"P4-2h-3 task tree status must match policy follow-up status: {expected_status}")
    if by_id["P4-2h-3"].get("release_blocker") is not False:
        fail("P4-2h-3 must not be a release blocker by default")
    if "P4-2h-2" not in by_id["P4-2h-3"].get("depends_on", []):
        fail("P4-2h-3 must depend on P4-2h-2")

    followup = policy["registered_followup_requirement"]
    if by_id["P4-2h-3"].get("title") != followup.get("title"):
        fail("P4-2h-3 title must match policy follow-up requirement")


def validate_parent_ledger() -> None:
    text = PARENT_LEDGER.read_text(encoding="utf-8")
    for required in ["P4-2h-2", "P4-2h-3", "LLM-wiki-lite", "语义记忆"]:
        if required not in text:
            fail(f"parent ledger missing {required}")


def validate_cross_policies() -> None:
    retrieval = load_json(ROOT / "references/retrieval-escalation-policy.json")
    routes = retrieval.get("routes")
    if not isinstance(routes, list):
        fail("retrieval routes missing")
    by_id = {str(item.get("id")): item for item in routes if isinstance(item, dict)}
    for route in ["rag", "graphrag"]:
        if by_id.get(route, {}).get("allowed_now") is not False:
            fail(f"{route} must remain disabled")

    forge = load_json(ROOT / "references/redcap-forge-policy.json")
    if "privacy-safety" not in {str(item.get("id")) for item in forge.get("responsibilities", []) if isinstance(item, dict)}:
        fail("RedCap Forge privacy-safety responsibility missing")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap LLM-wiki asset stratification and follow-up requirement registration.")
    parser.add_argument("--policy", default=str(POLICY))
    args = parser.parse_args()

    policy = load_json(Path(args.policy).resolve())
    validate_policy(policy)
    validate_task_tree(policy)
    validate_parent_ledger()
    validate_cross_policies()
    print("LLM_WIKI_ASSET_STRATIFICATION_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

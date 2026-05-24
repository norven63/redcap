#!/usr/bin/env python3
# 用途：知识沉淀与自进化脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

from __future__ import annotations

import json
import argparse
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "references/agent-reading-absorption-policy.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-agent-reading-absorption] {message}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing policy: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid json: {exc}")
    if not isinstance(payload, dict):
        fail("policy must be a JSON object")
    return payload


def require_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        fail(f"{key} must be a non-empty list")
    return value


def require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{key} must be a non-empty string")
    return value.strip()


def repo_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def require_surface(path: str) -> None:
    if "*" in path or "<" in path:
        return
    if not repo_path(path).exists():
        fail(f"required surface missing: {path}")


def validate_source_docs(policy: dict[str, Any]) -> None:
    docs = require_list(policy, "source_docs")
    dispositions = {str(item.get("disposition", "")) for item in docs if isinstance(item, dict)}
    for required in [
        "read-as-guide-not-authority",
        "absorb-core-principles",
        "absorb-pattern-with-redcap-boundaries",
        "defer-until-learning-skill-scope",
    ]:
        if required not in dispositions:
            fail(f"source_docs missing disposition: {required}")

    paths = {str(item.get("path", "")) for item in docs if isinstance(item, dict)}
    for required in ["agent-reading-guide.md", "ai-engineer.md", "llm-wiki.md", "ai-professor-mode.md"]:
        if not any(path.endswith(required) for path in paths):
            fail(f"source_docs missing {required}")


def validate_engineering(policy: dict[str, Any]) -> None:
    principles = require_list(policy, "absorbed_engineering_principles")
    ids = {str(item.get("id", "")) for item in principles if isinstance(item, dict)}
    for required in ["explicit-assumptions", "simplicity-first", "surgical-changes", "verifiable-goal-loop"]:
        if required not in ids:
            fail(f"missing absorbed engineering principle: {required}")


def validate_memory_mapping(policy: dict[str, Any]) -> None:
    mapping = policy.get("long_term_memory_mapping")
    if not isinstance(mapping, dict):
        fail("long_term_memory_mapping must be an object")

    raw = mapping.get("raw_sources")
    if not isinstance(raw, dict):
        fail("raw_sources mapping missing")
    if raw.get("raw_public_export") != "forbidden":
        fail("raw_sources.raw_public_export must remain forbidden")
    raw_paths = [str(item) for item in require_list(raw, "redcap_paths")]
    for required in ["assets/docs/task-reports", "assets/private-archive/redcap-knowledge/task-reports", "prism/runs"]:
        if required not in raw_paths:
            fail(f"raw_sources missing {required}")

    synthesis = mapping.get("wiki_or_synthesis_layer")
    if not isinstance(synthesis, dict):
        fail("wiki_or_synthesis_layer mapping missing")
    if synthesis.get("llm_full_ownership") is not False:
        fail("llm_full_ownership must remain false")
    synthesis_paths = [str(item) for item in require_list(synthesis, "redcap_paths")]
    for required in ["assets/knowledge/index.md", "assets/knowledge/log.md", "compass/evolution/candidates.json"]:
        if required not in synthesis_paths:
            fail(f"synthesis layer missing {required}")

    schema = mapping.get("schema_layer")
    if not isinstance(schema, dict):
        fail("schema_layer mapping missing")
    if schema.get("separate_schema_root_now") is not False:
        fail("schema separate root must remain deferred")


def validate_operations(policy: dict[str, Any]) -> None:
    operations = require_list(policy, "operations")
    by_id = {str(item.get("id", "")): item for item in operations if isinstance(item, dict)}
    for required in ["ingest", "query", "lint"]:
        if required not in by_id:
            fail(f"operation missing: {required}")
    if by_id["ingest"].get("direct_public_write_allowed") is not False:
        fail("ingest.direct_public_write_allowed must remain false")
    if by_id["query"].get("good_answer_writeback") != "candidate-only":
        fail("query.good_answer_writeback must be candidate-only")


def validate_decisions(policy: dict[str, Any]) -> None:
    decisions = require_list(policy, "immediate_decisions")
    by_id = {str(item.get("id", "")): item for item in decisions if isinstance(item, dict)}
    expected = {
        "no-new-llm-owned-wiki-layer": "defer",
        "query-answer-writeback": "candidate-only",
        "rag-or-graphrag": "keep-existing-threshold-policy",
        "schema-root": "defer",
        "ai-professor-mode": "defer",
    }
    for key, value in expected.items():
        if key not in by_id:
            fail(f"decision missing: {key}")
        if by_id[key].get("decision") != value:
            fail(f"{key} decision must be {value}")


def validate_surfaces(policy: dict[str, Any]) -> None:
    for path in [str(item) for item in require_list(policy, "required_surfaces")]:
        require_surface(path)

    index = (ROOT / "assets/knowledge/index.md").read_text(encoding="utf-8")
    if "assets/knowledge/log.md" not in index:
        fail("knowledge index must mention assets/knowledge/log.md")

    log_path = ROOT / "assets/knowledge/log.md"
    log = log_path.read_text(encoding="utf-8")
    if "agent-reading-absorption" not in log:
        fail("knowledge log must record agent-reading-absorption")
    if not re.search(r"^## \[20\d\d-\d\d-\d\d\] ", log, flags=re.MULTILINE):
        fail("knowledge log must use append-only dated headings")

    retrieval = load_json(ROOT / "references/retrieval-escalation-policy.json")
    routes = retrieval.get("routes")
    if not isinstance(routes, list):
        fail("retrieval escalation routes missing")
    heavy = {str(item.get("id")): item.get("allowed_now") for item in routes if isinstance(item, dict)}
    for route in ["rag", "graphrag"]:
        if heavy.get(route) is not False:
            fail(f"{route} must remain disabled until threshold review")


def validate_must_not_claim(policy: dict[str, Any]) -> None:
    claims = [str(item) for item in require_list(policy, "must_not_claim")]
    for phrase in ["complete LLM Wiki", "directly write public", "RAG", "ai-professor-mode", "raw private reports"]:
        if not any(phrase in claim for claim in claims):
            fail(f"must_not_claim missing phrase: {phrase}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate RedCap's controlled absorption of external agent-reading guidance."
    )
    parser.add_argument(
        "--policy",
        default=str(POLICY),
        help="Policy JSON to validate. Defaults to references/agent-reading-absorption-policy.json.",
    )
    args = parser.parse_args()

    policy = load_json(Path(args.policy).resolve())
    if policy.get("version") != 1:
        fail("version must be 1")
    if policy.get("policy_id") != "agent-reading-absorption":
        fail("policy_id must be agent-reading-absorption")
    if policy.get("parent_child_id") != "P4-2h-1":
        fail("parent_child_id must be P4-2h-1")
    if policy.get("status") != "implemented-contract-only":
        fail("status must be implemented-contract-only")
    require_text(policy, "purpose")

    validate_source_docs(policy)
    validate_engineering(policy)
    validate_memory_mapping(policy)
    validate_operations(policy)
    validate_decisions(policy)
    validate_surfaces(policy)
    validate_must_not_claim(policy)
    print("AGENT_READING_ABSORPTION_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

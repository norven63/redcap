#!/usr/bin/env python3
# 用途：长期记忆路线图脚本；校验 RAG/GraphRAG 受控适配层保持 disabled-by-default。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "assets/references/rag-graphrag-boundary-policy.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-rag-graphrag-boundary] {message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid policy json: {exc}")
    if not isinstance(payload, dict):
        fail("policy must be object")
    return payload


def require_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        fail(f"{key} must be non-empty list")
    return value


def main() -> int:
    policy = load_json(POLICY)
    if policy.get("version") != 1 or policy.get("policy_id") != "rag-graphrag-controlled-boundary":
        fail("policy identity mismatch")
    if policy.get("status") != "implemented-disabled-by-default":
        fail("status must be implemented-disabled-by-default")
    backend = policy.get("backend_state")
    if not isinstance(backend, dict):
        fail("backend_state must be object")
    for key in ["rag_enabled", "graphrag_enabled", "vector_store_enabled", "background_indexer_enabled"]:
        if backend.get(key) is not False:
            fail(f"{key} must remain false")
    gate = policy.get("activation_gate")
    if not isinstance(gate, dict):
        fail("activation_gate must be object")
    for key in ["requires_explicit_task", "requires_prism_review", "requires_privacy_review", "requires_dependency_review", "requires_rollback_plan", "requires_clean_workspace_e2e"]:
        if gate.get(key) is not True:
            fail(f"{key} must be true")
    if "No environment variable" not in str(gate.get("forbidden_soft_switch", "")):
        fail("activation gate must forbid soft switches")
    adapter = policy.get("adapter_contract")
    if not isinstance(adapter, dict):
        fail("adapter_contract must be object")
    if not (ROOT / str(adapter.get("entrypoint_check", ""))).is_file():
        fail("entrypoint_check must exist")
    forbidden = " ".join(str(item) for item in require_list(adapter, "forbidden_operations_now"))
    for phrase in ["build vector index", "call external retrieval service", "replace source files as truth"]:
        if phrase not in forbidden:
            fail(f"forbidden operations missing phrase: {phrase}")
    claims = " ".join(str(item) for item in require_list(policy, "must_not_claim"))
    for phrase in ["RAG is enabled", "GraphRAG is enabled", "vector search is enabled", "semantic retrieval"]:
        if phrase not in claims:
            fail(f"must_not_claim missing phrase: {phrase}")
    print("RAG_GRAPHRAG_BOUNDARY_OK")
    print("status=disabled-by-default")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# 用途：长期记忆路线图脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "references/full-llm-wiki-roadmap.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-full-llm-wiki-roadmap-check] {message}")


def main() -> int:
    try:
        payload = json.loads(POLICY.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid roadmap json: {exc}")
    if payload.get("version") != 1 or payload.get("roadmap_id") != "full-llm-wiki-roadmap":
        fail("roadmap identity mismatch")
    if payload.get("current_capability") != "full-llm-wiki-controlled-local":
        fail("current capability must be full-llm-wiki-controlled-local after the explicit implementation task")
    phases = {item.get("id"): item.get("status") for item in payload.get("phases", []) if isinstance(item, dict)}
    for required in ["lite", "full-wiki-product", "background-distillation-worker", "fts-rag-graphrag"]:
        if required not in phases:
            fail(f"missing phase: {required}")
    if phases["lite"] != "implemented":
        fail("lite phase must stay implemented")
    expected = {
        "full-wiki-product": "implemented-controlled-local",
        "background-distillation-worker": "implemented-proposal-only",
        "fts-rag-graphrag": "controlled-boundary-disabled-by-default",
    }
    for required, status in expected.items():
        if phases[required] != status:
            fail(f"{required} status mismatch: expected {status}, got {phases[required]}")
    must_not = " ".join(str(item) for item in payload.get("must_not_claim", []))
    for phrase in ["not a source of truth", "proposal-only", "No live vector store", "never replace source policies"]:
        if phrase not in must_not:
            fail(f"must_not_claim missing phrase: {phrase}")
    retrieval = (ROOT / "references/retrieval-escalation-policy.json").read_text(encoding="utf-8", errors="replace")
    if "semantic_retrieval_miss_observations_30d" not in retrieval:
        fail("retrieval escalation policy must expose observation metrics")
    for required_surface in [
        "assets/references/full-llm-wiki-policy.json",
        "assets/references/rag-graphrag-boundary-policy.json",
        "compass/tools/redcap-full-llm-wiki-check.sh",
        "compass/tools/redcap-full-llm-wiki-worker.sh",
    ]:
        if not (ROOT / required_surface).exists():
            fail(f"full implementation surface missing: {required_surface}")
    print("FULL_LLM_WIKI_ROADMAP_OK")
    print(f"status={payload['status']} current={payload['current_capability']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

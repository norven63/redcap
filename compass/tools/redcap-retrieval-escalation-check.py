#!/usr/bin/env python3
# 用途：产品形态与检索治理脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#product-shape-and-retrieval

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_POLICY = "references/retrieval-escalation-policy.json"
VALID_ROUTES = {"index-rg-metadata", "fts", "rag", "graphrag"}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-retrieval-escalation-check] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label} json: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be a json object")
    return payload


def resolve(root: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return (root / path).resolve()


def count_entries(root: Path, entry_glob: str) -> tuple[int, int]:
    if not root.exists():
        return 0, 0
    count = 0
    total_bytes = 0
    for path in root.glob(entry_glob):
        if not path.is_file():
            continue
        count += 1
        total_bytes += path.stat().st_size
    return count, total_bytes


def threshold_crossed(metrics: dict[str, int], thresholds: dict[str, Any]) -> list[str]:
    crossed: list[str] = []
    for key, raw_limit in thresholds.items():
        if not isinstance(raw_limit, int) or raw_limit < 0:
            fail(f"invalid escalation threshold: {key}")
        metric_key = key.removesuffix("_gte")
        value = metrics.get(metric_key)
        if value is None:
            fail(f"threshold references unknown metric: {key}")
        if value >= raw_limit:
            crossed.append(f"{metric_key}={value} >= {raw_limit}")
    return crossed


def threshold_group(thresholds: dict[str, Any], key: str) -> dict[str, Any]:
    group = thresholds.get(key)
    if not isinstance(group, dict):
        fail(f"escalation_thresholds.{key} must be an object")
    return group


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate RedCap retrieval escalation policy.")
    parser.add_argument("--root", default=".", help="RedCap repository root")
    parser.add_argument("--policy", default=DEFAULT_POLICY, help="Policy path relative to root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy_path = resolve(root, args.policy)
    policy = load_json(policy_path, "retrieval escalation policy")

    if policy.get("version") != 1:
        fail("version must be 1")
    if policy.get("policy_id") != "redcap-retrieval-escalation":
        fail("policy_id must be redcap-retrieval-escalation")

    active_route = policy.get("active_route")
    if active_route not in VALID_ROUTES:
        fail(f"active_route must be one of {sorted(VALID_ROUTES)}")

    read_rule = policy.get("default_read_rule")
    if not isinstance(read_rule, dict):
        fail("default_read_rule must be an object")
    for key in ("catalog_first", "metadata_first", "body_read_requires_precise_path", "forbid_default_full_corpus_load"):
        if read_rule.get(key) is not True:
            fail(f"default_read_rule.{key} must be true")

    forbidden = policy.get("forbidden_defaults")
    if not isinstance(forbidden, dict):
        fail("forbidden_defaults must be an object")
    for key in (
        "load_full_corpus_by_default",
        "enable_vector_store_without_threshold",
        "enable_graphrag_without_threshold",
        "treat_rag_as_source_of_truth",
    ):
        if forbidden.get(key) is not False:
            fail(f"forbidden_defaults.{key} must be false")

    roots = policy.get("roots")
    if not isinstance(roots, dict):
        fail("roots must be an object")
    docs_catalog_path = resolve(root, str(roots.get("docs_catalog", "")))
    template_root = resolve(root, str(roots.get("shared_knowledge_template", "")))
    worktree_root = resolve(root, str(roots.get("shared_knowledge_worktree", "")))
    docs_catalog = load_json(docs_catalog_path, "docs catalog")

    summary = docs_catalog.get("summary")
    if not isinstance(summary, dict):
        fail("docs catalog summary missing")

    entry_glob = policy.get("shared_knowledge_entry_glob")
    if entry_glob != "users/*/*.md":
        fail("shared_knowledge_entry_glob must be users/*/*.md")

    template_entries, template_bytes = count_entries(template_root, entry_glob)
    worktree_entries, worktree_bytes = count_entries(worktree_root, entry_glob)
    shared_entries = template_entries + worktree_entries
    shared_bytes = template_bytes + worktree_bytes

    observations = policy.get("current_observations")
    if not isinstance(observations, dict):
        fail("current_observations must be an object")
    update_rule = policy.get("observation_update_rule")
    if not isinstance(update_rule, dict):
        fail("observation_update_rule must be an object")
    for key in ("write_target", "evidence_sources", "required_update_points"):
        if not update_rule.get(key):
            fail(f"observation_update_rule.{key} must be set")
    if update_rule.get("write_target") != "current_observations":
        fail("observation_update_rule.write_target must be current_observations")

    metrics = {
        "docs_catalog_file_count": int(summary.get("file_count", 0)),
        "docs_catalog_lines": int(summary.get("lines", 0)),
        "shared_knowledge_entry_count": shared_entries,
        "shared_knowledge_size_bytes": shared_bytes,
        "semantic_retrieval_miss_observations_30d": int(observations.get("semantic_retrieval_miss_observations_30d", 0)),
        "relationship_query_observations_30d": int(observations.get("relationship_query_observations_30d", 0)),
        "cross_entity_trace_failures_30d": int(observations.get("cross_entity_trace_failures_30d", 0)),
    }

    thresholds = policy.get("escalation_thresholds")
    if not isinstance(thresholds, dict):
        fail("escalation_thresholds must be an object")

    fts_crossed = threshold_crossed(metrics, threshold_group(thresholds, "fts_review_required_when_any"))
    rag_crossed = threshold_crossed(metrics, threshold_group(thresholds, "rag_review_required_when_any"))
    graphrag_crossed = threshold_crossed(metrics, threshold_group(thresholds, "graphrag_review_required_when_any"))

    routes = policy.get("routes")
    if not isinstance(routes, list) or not routes:
        fail("routes must be a non-empty list")
    route_map: dict[str, dict[str, Any]] = {}
    for route in routes:
        if not isinstance(route, dict):
            fail("routes entries must be objects")
        rid = route.get("id")
        if rid not in VALID_ROUTES:
            fail(f"route has invalid id: {rid}")
        if rid in route_map:
            fail(f"duplicate route id: {rid}")
        route_map[rid] = route
    missing_routes = VALID_ROUTES - set(route_map)
    if missing_routes:
        fail("routes missing: " + ", ".join(sorted(missing_routes)))

    if active_route == "index-rg-metadata":
        crossed = fts_crossed + rag_crossed + graphrag_crossed
        if crossed:
            fail("index-rg-metadata route is stale; escalation review threshold crossed: " + "; ".join(crossed))
    elif active_route == "fts":
        if not fts_crossed:
            fail("fts route enabled before FTS review threshold crossed")
        if rag_crossed or graphrag_crossed:
            fail("fts route is stale; heavier retrieval review threshold crossed")
    elif active_route == "rag":
        if not rag_crossed:
            fail("rag route enabled before RAG review threshold crossed")
        if graphrag_crossed:
            fail("rag route is stale; GraphRAG review threshold crossed")
    elif active_route == "graphrag" and not graphrag_crossed:
        fail("graphrag route enabled before GraphRAG review threshold crossed")

    if active_route in {"rag", "graphrag"} and forbidden.get("treat_rag_as_source_of_truth") is not False:
        fail("RAG/GraphRAG must not replace source-of-truth files")

    print(
        "RETRIEVAL_ESCALATION_OK "
        f"active_route={active_route} "
        f"docs_files={metrics['docs_catalog_file_count']} "
        f"docs_lines={metrics['docs_catalog_lines']} "
        f"shared_entries={shared_entries} "
        f"shared_bytes={shared_bytes}"
    )


if __name__ == "__main__":
    main()

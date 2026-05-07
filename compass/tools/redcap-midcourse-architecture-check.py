#!/usr/bin/env python3
# 用途：校验 RedCap 中途架构审计是否覆盖任务树、文件头、LLM-wiki 与棱镜边界；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#product-shape-and-retrieval

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_DIMENSIONS = {
    "completed-requirements",
    "recent-inserted-requirements",
    "planned-open-tasks",
    "script-header-and-dictionary-governance",
    "llm-wiki-lite-boundary",
    "runtime-artifact-and-directory-governance",
    "prism-provider-governance",
}

REQUIRED_DEFERRED = {"P4-2h", "P4-2", "full-llm-wiki-product"}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-midcourse-architecture-check] {message}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing review json: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid json: {exc}")
    if not isinstance(payload, dict):
        fail("review json must be an object")
    return payload


def ensure_paths_exist(root: Path, paths: list[str], field: str) -> None:
    for rel in paths:
        path = root / rel
        if not path.exists():
            fail(f"{field} path does not exist: {rel}")


def validate_review(root: Path, payload: dict[str, Any]) -> None:
    if payload.get("version") != 1:
        fail("version must be 1")
    if payload.get("status") != "completed":
        fail("status must be completed")

    dimensions = payload.get("dimensions")
    if not isinstance(dimensions, list):
        fail("dimensions must be a list")
    seen: set[str] = set()
    for item in dimensions:
        if not isinstance(item, dict):
            fail("dimension entries must be objects")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            fail("dimension missing id")
        seen.add(item_id)
        if item.get("status") not in {"aligned", "bounded", "remediated", "visible", "guarded"}:
            fail(f"{item_id}: unsupported status {item.get('status')!r}")
        decision = item.get("decision")
        if not isinstance(decision, str) or len(decision.strip()) < 20:
            fail(f"{item_id}: decision must be a meaningful sentence")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            fail(f"{item_id}: evidence must be a non-empty list")
        ensure_paths_exist(root, [str(path) for path in evidence], f"{item_id}.evidence")

    missing_dimensions = REQUIRED_DIMENSIONS - seen
    if missing_dimensions:
        fail("missing required dimensions: " + ", ".join(sorted(missing_dimensions)))

    deferred = payload.get("deferred_items")
    if not isinstance(deferred, list):
        fail("deferred_items must be a list")
    deferred_ids = {str(item.get("id")) for item in deferred if isinstance(item, dict)}
    missing_deferred = REQUIRED_DEFERRED - deferred_ids
    if missing_deferred:
        fail("missing deferred items: " + ", ".join(sorted(missing_deferred)))

    claims = payload.get("must_not_claim")
    if not isinstance(claims, list) or len(claims) < 4:
        fail("must_not_claim must contain at least four guardrails")

    checks = payload.get("checks")
    if not isinstance(checks, list) or len(checks) < 3:
        fail("checks must list the review and supporting gates")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--review", default="references/midcourse-architecture-task-tree-review.json")
    args = parser.parse_args()

    root = args.root.resolve()
    review = root / args.review
    validate_review(root, load_json(review))
    print("MIDCOURSE_ARCHITECTURE_REVIEW_OK dimensions=7 deferred=3")
    return 0


if __name__ == "__main__":
    sys.exit(main())

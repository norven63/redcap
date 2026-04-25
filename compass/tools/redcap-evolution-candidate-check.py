#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-evolution-candidate-check] {message}")


def load_json(path: pathlib.Path, label: str) -> dict:
    if not path.is_file():
        fail(f"missing {label}: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label}: {exc}")


def exists(root: pathlib.Path, rel_path: str) -> bool:
    if not rel_path:
        return False
    path = pathlib.Path(rel_path).expanduser()
    if path.is_absolute():
        return path.exists()
    return (root / path).exists()


def require_meaningful(candidate: dict, cid: str, field: str, min_len: int = 30) -> None:
    value = candidate.get(field)
    if not isinstance(value, str) or len(value.strip()) < min_len:
        fail(f"{cid}: {field} must be meaningful")


def main() -> None:
    if len(sys.argv) != 4:
        fail("usage: redcap-evolution-candidate-check.py <root> <pool_path> <strict>")

    root = pathlib.Path(sys.argv[1]).resolve()
    pool_arg = pathlib.Path(sys.argv[2])
    pool_path = pool_arg if pool_arg.is_absolute() else root / pool_arg
    strict = sys.argv[3].lower() == "true"

    schema = load_json(root / "references/evolution-candidate-schema.json", "candidate schema")
    pool = load_json(pool_path, "candidate pool")

    if schema.get("version") != 1:
        fail("candidate schema version must be 1")
    if pool.get("version") != 1:
        fail("candidate pool version must be 1")

    required_fields = schema.get("required_fields")
    if not isinstance(required_fields, list) or not required_fields:
        fail("candidate schema required_fields must be non-empty")
    allowed_source_kinds = set(schema.get("allowed_source_kinds") or [])
    allowed_targets = set(schema.get("allowed_promotion_targets") or [])
    allowed_statuses = set(schema.get("allowed_statuses") or [])
    if not allowed_source_kinds or not allowed_targets or not allowed_statuses:
        fail("candidate schema allowed lists must be non-empty")

    candidates = pool.get("candidates")
    if not isinstance(candidates, list):
        fail("candidate pool candidates must be a list")

    seen: set[str] = set()
    counts: Counter[str] = Counter()
    unresolved: list[str] = []

    for candidate in candidates:
        if not isinstance(candidate, dict):
            fail("candidate entries must be objects")
        cid = candidate.get("id")
        if not isinstance(cid, str) or not cid.strip():
            fail("candidate missing id")
        if cid in seen:
            fail(f"duplicate candidate id: {cid}")
        seen.add(cid)

        for field in required_fields:
            if field not in candidate:
                fail(f"{cid}: missing required field: {field}")

        source_kind = candidate.get("source_kind")
        if source_kind not in allowed_source_kinds:
            fail(f"{cid}: invalid source_kind: {source_kind}")
        target = candidate.get("promotion_target")
        if target not in allowed_targets:
            fail(f"{cid}: invalid promotion_target: {target}")
        status = candidate.get("status")
        if status not in allowed_statuses:
            fail(f"{cid}: invalid status: {status}")
        counts[status] += 1

        require_meaningful(candidate, cid, "problem_source")
        require_meaningful(candidate, cid, "solution")
        require_meaningful(candidate, cid, "final_effect")

        evidence_paths = candidate.get("evidence_paths")
        if not isinstance(evidence_paths, list) or not evidence_paths:
            fail(f"{cid}: evidence_paths must be non-empty")
        for path in evidence_paths:
            if not isinstance(path, str) or not path.strip():
                fail(f"{cid}: invalid evidence path")
            if not exists(root, path):
                fail(f"{cid}: evidence path does not exist: {path}")

        review_paths = candidate.get("review_paths", [])
        if review_paths is not None:
            if not isinstance(review_paths, list):
                fail(f"{cid}: review_paths must be a list")
            for path in review_paths:
                if not isinstance(path, str) or not path.strip():
                    fail(f"{cid}: invalid review path")
                if not exists(root, path):
                    fail(f"{cid}: review path does not exist: {path}")

        if status in {"candidate", "reviewing"}:
            unresolved.append(cid)
        if status == "promoted":
            promotion_paths = candidate.get("promotion_paths")
            if not isinstance(promotion_paths, list) or not promotion_paths:
                fail(f"{cid}: promoted candidate must declare promotion_paths")
            for path in promotion_paths:
                if not isinstance(path, str) or not path.strip() or not exists(root, path):
                    fail(f"{cid}: invalid promotion path: {path}")
        if status == "no-promote":
            reason = candidate.get("no_promote_reason")
            if not isinstance(reason, str) or len(reason.strip()) < 20:
                fail(f"{cid}: no-promote candidate must explain no_promote_reason")

    if strict and unresolved:
        fail("unresolved evolution candidates: " + ", ".join(unresolved))

    print("EVOLUTION_CANDIDATES")
    print(f"candidates={len(candidates)} strict={str(strict).lower()}")
    print("statuses=" + ",".join(f"{key}={counts.get(key, 0)}" for key in sorted(allowed_statuses)))
    if unresolved:
        print("unresolved=" + ",".join(unresolved))
    print("EVOLUTION_CANDIDATES_OK")


if __name__ == "__main__":
    main()

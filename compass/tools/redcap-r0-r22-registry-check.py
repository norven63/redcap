#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "references/redcap-r0-r22-registry.json"
ALLOWED_STATUS = {"completed", "completed-with-defer", "deferred", "blocked-or-deferred"}
ALLOWED_SOURCE_TYPE = {"recovered", "reconstructed"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r0-r22-registry-check] {message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid json {path}: {exc}")
    if not isinstance(payload, dict):
        fail("registry must be a JSON object")
    return payload


def require_text(item: dict[str, Any], key: str, item_id: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{item_id}: missing non-empty {key}")
    return value.strip()


def require_existing_path(repo_root: Path, rel_path: str, item_id: str, key: str) -> None:
    if rel_path.startswith("/") or ".." in Path(rel_path).parts:
        fail(f"{item_id}: {key} must be a safe repo-relative path: {rel_path}")
    path = repo_root / rel_path
    if not path.exists():
        fail(f"{item_id}: evidence path missing: {rel_path}")


def require_existing_commit(repo_root: Path, commit: str, item_id: str) -> None:
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", commit):
        fail(f"{item_id}: source_commit must be a git hex prefix or full sha")
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-e", f"{commit}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode != 0:
        fail(f"{item_id}: source_commit does not resolve to a commit: {commit}")


def expected_ids() -> list[str]:
    return [f"R{index}" for index in range(23)]


def check_registry(path: Path) -> None:
    repo_root = path.resolve().parents[1] if path.name == "redcap-r0-r22-registry.json" else ROOT
    payload = load_json(path)
    if payload.get("version") != 1:
        fail("version must be 1")
    if payload.get("registry_id") != "redcap-r0-r22":
        fail("registry_id must be redcap-r0-r22")
    policy = payload.get("reconstruction_policy")
    if not isinstance(policy, dict) or "Do not invent lost original titles" not in str(policy.get("rule", "")):
        fail("reconstruction_policy must forbid inventing lost original titles")

    items = payload.get("items")
    if not isinstance(items, list):
        fail("items must be a list")
    ids = [item.get("id") for item in items if isinstance(item, dict)]
    expected = expected_ids()
    if ids != expected:
        fail(f"items must be exactly {', '.join(expected)}")

    reconstructed_low_or_medium = 0
    for item in items:
        if not isinstance(item, dict):
            fail("item must be an object")
        item_id = require_text(item, "id", "unknown")
        if not re.fullmatch(r"R(?:[0-9]|1[0-9]|2[0-2])", item_id):
            fail(f"invalid id: {item_id}")
        require_text(item, "title", item_id)
        status = require_text(item, "status", item_id)
        source_type = require_text(item, "source_type", item_id)
        confidence = require_text(item, "confidence", item_id)
        source_report = require_text(item, "source_report", item_id)
        require_text(item, "completion_boundary", item_id)
        require_text(item, "deferred_boundary", item_id)

        if status not in ALLOWED_STATUS:
            fail(f"{item_id}: unsupported status: {status}")
        if source_type not in ALLOWED_SOURCE_TYPE:
            fail(f"{item_id}: unsupported source_type: {source_type}")
        if confidence not in ALLOWED_CONFIDENCE:
            fail(f"{item_id}: unsupported confidence: {confidence}")
        if source_type == "reconstructed" and confidence == "high":
            fail(f"{item_id}: reconstructed items must not be high-confidence")
        if source_type == "reconstructed" and confidence in {"medium", "low"}:
            reconstructed_low_or_medium += 1

        require_existing_path(repo_root, source_report, item_id, "source_report")
        source_commit = item.get("source_commit")
        if source_commit is not None:
            if not isinstance(source_commit, str) or not source_commit.strip():
                fail(f"{item_id}: source_commit must be a non-empty string when present")
            require_existing_commit(repo_root, source_commit.strip(), item_id)
        evidence_paths = item.get("evidence_paths")
        if not isinstance(evidence_paths, list) or not evidence_paths:
            fail(f"{item_id}: evidence_paths must be a non-empty list")
        for evidence in evidence_paths:
            if not isinstance(evidence, str) or not evidence.strip():
                fail(f"{item_id}: evidence path must be a non-empty string")
            require_existing_path(repo_root, evidence.strip(), item_id, "evidence_paths")

    if reconstructed_low_or_medium == 0:
        fail("registry must explicitly mark reconstructed lower-confidence items")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap R0-R22 parent-task registry.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    args = parser.parse_args()
    path = Path(args.registry)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.is_file():
        fail(f"missing registry: {path}")
    check_registry(path)
    print(f"R0_R22_REGISTRY_OK {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

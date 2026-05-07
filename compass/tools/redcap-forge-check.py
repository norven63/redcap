#!/usr/bin/env python3
# 用途：知识沉淀与自进化脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "references/redcap-forge-policy.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-forge-check] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"{label} missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label} json: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be a JSON object")
    return payload


def require_text(payload: dict[str, Any], key: str, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{label}: missing non-empty {key}")
    return value.strip()


def require_list(payload: dict[str, Any], key: str, label: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        fail(f"{label}: {key} must be a non-empty list")
    return value


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "redcap-forge":
        fail("unexpected policy_id")

    names = policy.get("canonical_names")
    if not isinstance(names, dict):
        fail("canonical_names must be an object")
    if names.get("umbrella_system") != "RedCap Evolution Factory":
        fail("umbrella_system must remain RedCap Evolution Factory")
    if names.get("execution_pipeline") != "RedCap Forge":
        fail("execution_pipeline must be RedCap Forge")
    if names.get("public_repository") != "redcap-arsenal":
        fail("public_repository must be redcap-arsenal")

    responsibilities = require_list(policy, "responsibilities", "policy")
    required = {"capture", "distill", "privacy-safety", "dedupe", "structure", "index", "promote"}
    seen = set()
    for item in responsibilities:
        if not isinstance(item, dict):
            fail("responsibilities entries must be objects")
        item_id = require_text(item, "id", "responsibility")
        require_text(item, "meaning", item_id)
        seen.add(item_id)
    missing = sorted(required - seen)
    if missing:
        fail("missing Forge responsibilities: " + ", ".join(missing))

    forbidden = require_list(policy, "forbidden_public_raw_sources", "policy")
    for required_forbidden in ["compass/docs/task-reports/**", "redcap-knowledge/**", "compass/knowledge/**", "prism/runs/**", ".env"]:
        if required_forbidden not in forbidden:
            fail(f"missing forbidden public raw source: {required_forbidden}")

    public_targets = [
        item for item in require_list(policy, "promotion_targets", "policy")
        if isinstance(item, dict) and item.get("public") is True
    ]
    if not public_targets:
        fail("Forge policy must define at least one public promotion target")
    if not any("../redcap-arsenal" in str(item.get("path", "")) for item in public_targets):
        fail("public promotion target must point to external redcap-arsenal")

    gates = require_list(policy, "public_promotion_gates", "policy")
    for phrase in ["redcap-shared-knowledge dedupe", "redcap-shared-knowledge check", "redcap-shared-knowledge-remote-check", "Prism review"]:
        if not any(phrase in str(gate) for gate in gates):
            fail(f"public_promotion_gates missing phrase: {phrase}")

    for phrase in ["raw reports", "redcap-arsenal is populated", "active identity"]:
        if not any(phrase in str(item) for item in require_list(policy, "must_not_claim", "policy")):
            fail(f"must_not_claim missing phrase: {phrase}")


def validate_docs(root: Path) -> None:
    evolution_readme = (root / "compass/evolution/README.md").read_text(encoding="utf-8", errors="replace")
    for phrase in ["RedCap Forge", "redcap-arsenal", "Evolution Factory"]:
        if phrase not in evolution_readme:
            fail(f"Evolution README missing phrase: {phrase}")
    shared_readme = (root / "shared-knowledge/README.md").read_text(encoding="utf-8", errors="replace")
    if "RedCap Forge" not in shared_readme:
        fail("shared-knowledge README must mention RedCap Forge")


def validate_shared_policy(root: Path) -> None:
    shared = load_json(root / "references/shared-knowledge-policy.json", "shared knowledge policy")
    remote = load_json(root / "references/shared-knowledge-remote-binding.json", "shared knowledge remote binding")
    for phrase in ["RedCap Forge", "append-only", "dedupe"]:
        if phrase not in json.dumps(shared, ensure_ascii=False):
            fail(f"shared knowledge policy missing phrase: {phrase}")
    if remote.get("publish_mode") == "template-only":
        notes = "\n".join(str(item) for item in remote.get("notes", []))
        if "RedCap Forge" not in notes:
            fail("template-only remote binding notes must explain RedCap Forge boundary")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = root / policy_path
    policy = load_json(policy_path, "RedCap Forge policy")

    validate_policy(policy)
    validate_docs(root)
    validate_shared_policy(root)

    print("REDCAP_FORGE")
    print("pipeline=RedCap Forge")
    print("umbrella=RedCap Evolution Factory")
    print("public_repository=redcap-arsenal")
    print("REDCAP_FORGE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

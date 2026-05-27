#!/usr/bin/env python3
# 用途：知识检索入口脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "references/knowledge-gateway-policy.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-knowledge-gateway] {message}")


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


def resolve(root: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return (root / path).resolve()


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


def validate_policy(root: Path, policy: dict[str, Any]) -> list[dict[str, Any]]:
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "redcap-knowledge-gateway":
        fail("policy_id must be redcap-knowledge-gateway")
    if policy.get("status") != "active":
        fail("policy status must be active")
    for phrase in [
        "not a RAG system",
        "source files as truth sources",
        "must not bulk-read",
        "must not export private raw reports",
    ]:
        if phrase not in " ".join(str(item) for item in require_list(policy, "must_not_claim", "policy")):
            fail(f"must_not_claim missing phrase: {phrase}")

    routes = require_list(policy, "route_order", "policy")
    expected = [
        "active-private-index",
        "llm-wiki-lite",
        "llm-wiki-full",
        "public-arsenal-catalog",
        "private-cold-archive",
        "raw-evidence",
    ]
    actual: list[str] = []
    for item in routes:
        if not isinstance(item, dict):
            fail("route_order entries must be objects")
        route_id = require_text(item, "id", "route")
        actual.append(route_id)
        root_path = resolve(root, require_text(item, "root", route_id))
        first_read = require_text(item, "first_read", route_id)
        require_text(item, "body_read_rule", route_id)
        if not isinstance(item.get("allowed_default"), bool):
            fail(f"{route_id}: allowed_default must be boolean")
        if route_id != "public-arsenal-catalog" and not root_path.exists():
            fail(f"{route_id}: root does not exist: {item['root']}")
        if route_id != "raw-evidence":
            first_path = resolve(root, first_read)
            if not first_path.exists():
                fail(f"{route_id}: first_read does not exist: {first_read}")
    if actual != expected:
        fail("route_order must remain active -> wiki-lite -> full wiki -> public catalog -> cold archive -> raw evidence")
    if sum(1 for item in routes if item.get("allowed_default") is True) != 1:
        fail("only the active private index may be default-readable")
    if routes[0].get("allowed_default") is not True:
        fail("active-private-index must be the default first read")
    return routes


def print_summary(routes: list[dict[str, Any]]) -> None:
    print("REDCAP_KNOWLEDGE_GATEWAY")
    for index, route in enumerate(routes, start=1):
        default = "default" if route.get("allowed_default") else "on-demand"
        print(f"{index}. {route['id']} [{default}]")
        print(f"   first_read={route['first_read']}")
        print(f"   rule={route['body_read_rule']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and print RedCap knowledge lookup route.")
    parser.add_argument("command", nargs="?", choices=("check", "summary"), default="summary")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = root / policy_path
    routes = validate_policy(root, load_json(policy_path, "knowledge gateway policy"))
    if args.command == "summary":
        print_summary(routes)
    else:
        print("KNOWLEDGE_GATEWAY_OK")
        print(f"routes={len(routes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

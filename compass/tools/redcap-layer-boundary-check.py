#!/usr/bin/env python3
# 用途：Layer A/B 边界治理脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#product-shape-and-retrieval

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "references/layera-layerb-boundary-policy.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-layer-boundary-check] {message}")


def load_policy() -> dict[str, Any]:
    try:
        payload = json.loads(POLICY.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid policy json: {exc}")
    if not isinstance(payload, dict):
        fail("policy must be a JSON object")
    return payload


def require_text(payload: dict[str, Any], key: str, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{label}: missing {key}")
    return value.strip()


def require_layer(policy: dict[str, Any], key: str) -> dict[str, Any]:
    layer = policy.get(key)
    if not isinstance(layer, dict):
        fail(f"{key} must be an object")
    for field in ("name", "owner", "state_surface", "must_not_claim"):
        require_text(layer, field, key)
    assets = layer.get("primary_assets")
    if not isinstance(assets, list) or not assets:
        fail(f"{key}.primary_assets must be non-empty")
    return layer


def main() -> int:
    policy = load_policy()
    if policy.get("version") != 1 or policy.get("policy_id") != "redcap-layera-layerb-boundary":
        fail("policy identity mismatch")
    layer_a = require_layer(policy, "layer_a")
    layer_b = require_layer(policy, "layer_b")
    if layer_a["state_surface"] == layer_b["state_surface"]:
        fail("Layer A and Layer B must not share the same state surface")
    for rel in policy.get("required_surfaces", []):
        path = ROOT / str(rel)
        if not path.exists():
            fail(f"required surface missing: {rel}")

    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    for phrase in ["Layer A / 外部用户项目", "Layer B / RedCap 自身开发", ".dev-task.md + 承诺账本 + closeout runtime + Prism acceptance + receipt"]:
        if phrase not in skill:
            fail(f"SKILL.md missing Layer boundary phrase: {phrase}")

    system_layers = (ROOT / "references/redcap-system-layers.md").read_text(encoding="utf-8", errors="replace")
    for phrase in ["Runtime Layer", "Host Adapter Layer", "当前仓库仍是 skill-root 形态"]:
        if phrase not in system_layers:
            fail(f"redcap-system-layers missing phrase: {phrase}")

    dictionary = (ROOT / "references/file-lookup-dictionary.md").read_text(encoding="utf-8", errors="replace")
    for phrase in ["Layer A/B boundary", "references/layera-layerb-boundary-policy.json"]:
        if phrase not in dictionary:
            fail(f"file lookup dictionary missing boundary phrase: {phrase}")

    print("LAYER_BOUNDARY_OK")
    print(f"layer_a={layer_a['name']} layer_b={layer_b['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

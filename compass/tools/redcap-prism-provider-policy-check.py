#!/usr/bin/env python3
# 用途：棱镜与 Agent 路由策略检查；确保 provider 调度约束不是口头约定。
# Dictionary: references/file-lookup-dictionary.md#prism-and-providers

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "references/prism-provider-policy.json"
CORE_PATH = ROOT / "compass/CONTRIBUTING.core.md"
README_PATH = ROOT / "README.md"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-prism-provider-policy-check] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"{label} missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be a JSON object")
    return payload


def read(path: Path, label: str) -> str:
    if not path.is_file():
        fail(f"{label} missing: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def require_phrase(text: str, phrase: str, label: str) -> None:
    if phrase not in text:
        fail(f"{label} missing phrase: {phrase}")


def validate_routing_overrides(policy: dict[str, Any]) -> None:
    overrides = policy.get("routing_overrides")
    if not isinstance(overrides, list):
        fail("routing_overrides must be a list")

    by_agent: dict[str, dict[str, Any]] = {}
    for item in overrides:
        if not isinstance(item, dict):
            fail("routing_overrides entries must be objects")
        agent = str(item.get("agent") or "")
        if agent:
            by_agent[agent] = item

    copilot = by_agent.get("copilot")
    if not copilot:
        fail("copilot protected fallback override missing")
    if copilot.get("priority_tier") != "protected-fallback":
        fail("copilot must remain protected-fallback")
    required = copilot.get("allowed_when_all_unavailable")
    if required != ["claude-code", "kimi"]:
        fail("copilot fallback must require both claude-code and kimi unavailable")

    codex = by_agent.get("codex")
    if not codex:
        fail("codex last-resort override missing")
    if codex.get("priority_tier") != "last-resort":
        fail("codex must remain last-resort")


def validate_workload_distribution(policy: dict[str, Any]) -> None:
    distribution = policy.get("workload_distribution")
    if not isinstance(distribution, dict):
        fail("workload_distribution missing")
    if distribution.get("version") != 1:
        fail("workload_distribution.version must be 1")

    target = distribution.get("target_ratio")
    if not isinstance(target, dict):
        fail("workload_distribution.target_ratio must be an object")

    kimi = target.get("kimi")
    claude = target.get("claude-code")
    if not isinstance(kimi, dict) or not isinstance(claude, dict):
        fail("workload_distribution must define kimi and claude-code target ratios")

    kimi_min = float(kimi.get("share_min", -1))
    kimi_max = float(kimi.get("share_max", -1))
    claude_min = float(claude.get("share_min", -1))
    claude_max = float(claude.get("share_max", -1))
    if not (0.6 <= kimi_min <= kimi_max <= 0.7):
        fail("kimi share must stay within 60-70%")
    if not (0.3 <= claude_min <= claude_max <= 0.4):
        fail("claude-code share must stay within 30-40%")

    kimi_roles = kimi.get("default_roles")
    if not isinstance(kimi_roles, list):
        fail("kimi.default_roles must be a list")
    for role in [
        "long-form-analysis",
        "historical-archaeology",
        "task-tree-review",
        "large-document-synthesis",
    ]:
        if role not in kimi_roles:
            fail(f"kimi default_roles missing {role}")

    selection_policy = "\n".join(str(item) for item in distribution.get("selection_policy", []))
    for phrase in [
        "long-form",
        "archaeology",
        "Kimi + Claude Code",
        "60-70%",
        "resource-limited",
    ]:
        require_phrase(selection_policy, phrase, "workload_distribution.selection_policy")


def main() -> int:
    policy = load_json(POLICY_PATH, "provider policy")
    if policy.get("version") != 1:
        fail("provider policy version must be 1")

    text = json.dumps(policy, ensure_ascii=False)
    for phrase in [
        "Rank providers by model capability profile plus local CLI stability evidence.",
        "prefer Kimi",
        "Claude Code",
        "Copilot CLI is a protected fallback only",
        "Codex CLI is a last-resort fallback only",
    ]:
        require_phrase(text, phrase, "provider policy")

    validate_routing_overrides(policy)
    validate_workload_distribution(policy)

    core = read(CORE_PATH, "CONTRIBUTING core")
    for phrase in [
        "Prism 先看可用性清单",
        "Kimi",
        "Claude Code",
    ]:
        require_phrase(core, phrase, "CONTRIBUTING core")

    readme = read(README_PATH, "README")
    for phrase in [
        "Kimi",
        "Claude Code",
        "Copilot",
    ]:
        require_phrase(readme, phrase, "README")

    print("PRISM_PROVIDER_POLICY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

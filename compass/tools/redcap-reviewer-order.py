#!/usr/bin/env python3
# 用途：棱镜与 Agent 路由脚本；详细职责见文件查阅字典。

"""Compute stop-review reviewer targets from the capability matrix, local registry, and provider policy.

This parser intentionally supports only the small YAML subset used by
`compass/knowledge/model-capability-matrix.yaml` and
`compass/.workflow/agent-registry.yaml` so it can run without PyYAML.

Dictionary: references/file-lookup-dictionary.md#prism-and-providers
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


AGENT_NAME_MAP = {
    # reviewer-order outputs executable CLI names. The registry provider is
    # `claude-code`, but baton/on-stop-review invoke the local CLI as `claude`.
    # prism-availability keeps `claude-code` canonical and adds `claude` alias;
    # this asymmetry is intentional and covered by availability acceptance.
    "claude-code": "claude",
    "claude": "claude",
    "gemini": "gemini",
    "kimi": "kimi",
    "copilot": "copilot",
    "codex": "codex",
}

SPECIALIZED_CLI = {"claude", "gemini", "kimi", "codex"}
LAST_RESORT_TIERS = {"last-resort", "last_resort", "fallback-only", "fallback_only"}
PROTECTED_FALLBACK_TIERS = {"protected-fallback", "protected_fallback", "fallback-after-required-unavailable"}


def strip_inline_comment(text: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    for idx, ch in enumerate(text):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            continue
        if ch == "#" and not in_single and not in_double:
            return text[:idx].rstrip()
    return text.rstrip()


def parse_scalar(text: str):
    value = strip_inline_comment(text.strip())
    if value == "":
        return ""
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        return value[1:-1]
    if value.startswith("'") and value.endswith("'") and len(value) >= 2:
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def split_key_value(text: str) -> tuple[str, str]:
    key, _, value = text.partition(":")
    return key.strip(), value.strip()


def parse_matrix(path: Path) -> dict:
    data = {
        "role_requirements": {},
        "role_minimum_thresholds": {},
        "models": {},
        "reviewer_cli_profiles": {},
    }
    section = None
    current = None
    current_list = None
    current_role = None

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0:
            if line.endswith(":"):
                name = line[:-1]
                section = name if name in data else None
            else:
                section = None
            current = None
            current_list = None
            current_role = None
            continue

        if section in {"role_requirements", "role_minimum_thresholds"}:
            if indent == 2 and line.endswith(":"):
                current_role = line[:-1]
                data[section][current_role] = {}
            elif indent == 4 and current_role and ":" in line:
                key, value = split_key_value(line)
                data[section][current_role][key] = parse_scalar(value)
            continue

        if section in {"models", "reviewer_cli_profiles"}:
            if indent == 2 and line.endswith(":"):
                current = line[:-1]
                current_list = None
                data[section][current] = {}
            elif indent == 4 and current:
                if line.endswith(":"):
                    current_list = line[:-1]
                    data[section][current][current_list] = []
                elif ":" in line:
                    key, value = split_key_value(line)
                    data[section][current][key] = parse_scalar(value)
                    current_list = None
            elif indent == 6 and current and current_list and line.startswith("- "):
                data[section][current][current_list].append(parse_scalar(line[2:]))
            continue

    return data


def parse_registry(path: Path) -> dict:
    data = {"agents": {}}
    section = None
    current = None
    current_list = None

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0:
            section = "agents" if line == "agents:" else None
            current = None
            current_list = None
            continue

        if section != "agents":
            continue

        if indent == 2 and line.endswith(":"):
            current = line[:-1]
            current_list = None
            data["agents"][current] = {}
        elif indent == 4 and current:
            if line.endswith(":"):
                current_list = line[:-1]
                data["agents"][current][current_list] = []
            elif ":" in line:
                key, value = split_key_value(line)
                data["agents"][current][key] = parse_scalar(value)
                current_list = None
        elif indent == 6 and current and current_list and line.startswith("- "):
            data["agents"][current][current_list].append(parse_scalar(line[2:]))

    return data


def normalize_token(text: str) -> str:
    lowered = text.strip().lower()
    lowered = lowered.replace("_", "-")
    lowered = lowered.replace("/", "-")
    lowered = lowered.replace(" ", "")
    lowered = lowered.replace(".0", "")
    return lowered


def build_model_alias_map(models: dict) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for canonical, meta in models.items():
        candidates = [canonical] + list(meta.get("aliases", []) or [])
        for candidate in candidates:
            alias_map[candidate] = canonical
            alias_map[candidate.lower()] = canonical
            alias_map[normalize_token(candidate)] = canonical
    return alias_map


def canonical_model(raw_model: str, alias_map: dict[str, str]) -> str:
    if not raw_model:
        return "unknown"
    if raw_model in alias_map:
        return alias_map[raw_model]
    lowered = raw_model.lower()
    if lowered in alias_map:
        return alias_map[lowered]
    normalized = normalize_token(raw_model)
    return alias_map.get(normalized, raw_model)


def parse_manual_order(order: str) -> list[tuple[str, str | None]]:
    items: list[tuple[str, str | None]] = []
    for raw_item in order.split(","):
        item = raw_item.strip()
        if not item:
            continue
        agent = item
        model = None
        for separator in ("@", "&", ":"):
            if separator in item:
                agent, model = item.split(separator, 1)
                agent = agent.strip()
                model = model.strip() or None
                break
        items.append((AGENT_NAME_MAP.get(agent, agent), model))
    return items


def parse_policy_time(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def load_provider_policy(path: str | None) -> dict:
    if not path:
        return {}
    policy_path = Path(path)
    if not policy_path.is_file():
        return {}
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def policy_agent_name(agent: str) -> str:
    return "claude-code" if agent == "claude" else agent


def provider_frozen(policy: dict, agent: str, scope: str) -> bool:
    canonical_agent = policy_agent_name(agent)
    now = datetime.now(timezone.utc)
    for item in policy.get("freeze_windows", []) or []:
        if not isinstance(item, dict) or item.get("agent") != canonical_agent:
            continue
        scopes = item.get("scope", [])
        if isinstance(scopes, list) and scope not in scopes and "all" not in scopes:
            continue
        starts_at = parse_policy_time(item.get("starts_at"))
        until = parse_policy_time(item.get("until"))
        if starts_at is not None and now < starts_at.astimezone(timezone.utc):
            continue
        if until is not None and now >= until.astimezone(timezone.utc):
            continue
        return True
    return False


def scopes_include(raw: object, scope: str) -> bool:
    if raw is None:
        return True
    if isinstance(raw, str):
        return raw in {scope, "all"}
    if isinstance(raw, list):
        return scope in raw or "all" in raw
    return False


def provider_routing_tier(policy: dict, agent: str, scope: str) -> str:
    canonical_agent = policy_agent_name(agent)
    for item in policy.get("routing_overrides", []) or []:
        if not isinstance(item, dict) or item.get("agent") != canonical_agent:
            continue
        if not scopes_include(item.get("scope"), scope):
            continue
        raw = str(item.get("priority_tier") or item.get("mode") or "normal").strip().lower()
        if raw in LAST_RESORT_TIERS:
            return "last-resort"
        if raw in PROTECTED_FALLBACK_TIERS:
            return "protected-fallback"
        return raw or "normal"
    return "normal"


def provider_required_unavailable(policy: dict, agent: str, scope: str) -> list[str]:
    canonical_agent = policy_agent_name(agent)
    for item in policy.get("routing_overrides", []) or []:
        if not isinstance(item, dict) or item.get("agent") != canonical_agent:
            continue
        if not scopes_include(item.get("scope"), scope):
            continue
        raw = str(item.get("priority_tier") or item.get("mode") or "normal").strip().lower()
        if raw not in PROTECTED_FALLBACK_TIERS:
            return []
        required = item.get("allowed_when_all_unavailable")
        if not isinstance(required, list):
            return []
        return [policy_agent_name(str(value).strip()) for value in required if isinstance(value, str) and value.strip()]
    return []


def registry_meta_for_agent(registry: dict, agent: str) -> dict:
    candidates = [agent, policy_agent_name(agent)]
    for registry_name, mapped in AGENT_NAME_MAP.items():
        if mapped == agent or policy_agent_name(mapped) == policy_agent_name(agent):
            candidates.append(registry_name)
    for candidate in candidates:
        meta = registry.get("agents", {}).get(candidate)
        if isinstance(meta, dict):
            return meta
    return {}


def registry_agent_available(registry: dict, agent: str) -> bool:
    return bool(registry_meta_for_agent(registry, agent).get("available", False))


def model_profile_for(model_name: str, models: dict) -> dict:
    default = {
        "family": "unknown",
        "reasoning": 3,
        "coding": 3,
        "instruction_following": 3,
        "tool_use": 3,
        "cost_efficiency": 3,
        "known_issues": [],
    }
    profile = dict(default)
    profile.update(models.get(model_name, {}))
    return profile


def candidate_rows(
    matrix: dict,
    registry: dict,
    manual_order: str | None,
    requires_repo_inspection: bool,
    provider_policy: dict | None = None,
) -> list[dict]:
    models = matrix["models"]
    alias_map = build_model_alias_map(models)
    cli_profiles = matrix.get("reviewer_cli_profiles", {})
    reviewer_req = matrix["role_requirements"].get("reviewer", {})
    reviewer_min = matrix["role_minimum_thresholds"].get("reviewer", {})
    primary = reviewer_req.get("primary", "reasoning")
    secondary = reviewer_req.get("secondary", "coding")

    if manual_order:
        seeds: list[tuple[str, str | None]] = parse_manual_order(manual_order)
    else:
        seeds = []
        for registry_agent, meta in registry.get("agents", {}).items():
            if not meta.get("available", False):
                continue
            agent = AGENT_NAME_MAP.get(registry_agent, registry_agent)
            expanded_models = []
            switchable = meta.get("switchable_models", []) or []
            if switchable:
                expanded_models.extend(switchable)
            actual_model = meta.get("actual_model")
            if actual_model:
                expanded_models.append(actual_model)
            if not expanded_models:
                expanded_models.append("unknown")
            for raw_model in expanded_models:
                seeds.append((agent, raw_model))

    seen = set()
    rows = []
    provider_policy = provider_policy or {}
    for position, (agent, raw_model) in enumerate(seeds):
        if provider_frozen(provider_policy, agent, "stop-review"):
            continue
        routing_tier = provider_routing_tier(provider_policy, agent, "stop-review")
        required_unavailable = provider_required_unavailable(provider_policy, agent, "stop-review")
        if routing_tier == "protected-fallback" and any(registry_agent_available(registry, required) for required in required_unavailable):
            continue
        registry_meta = registry_meta_for_agent(registry, agent)
        if not manual_order and not registry_meta.get("available", False):
            continue
        canonical = canonical_model(raw_model or registry_meta.get("actual_model", ""), alias_map)
        key = (agent, canonical)
        if key in seen:
            continue
        seen.add(key)

        cli_profile = cli_profiles.get(agent, {})
        if requires_repo_inspection and not cli_profile.get("repo_inspection", False):
            continue

        model_profile = model_profile_for(canonical, models)
        if any(model_profile.get(capability, 0) < minimum for capability, minimum in reviewer_min.items()):
            continue

        capability_score = int(model_profile.get(primary, 3)) * 2 + int(model_profile.get(secondary, 3))
        local_stability = int(cli_profile.get("reviewer_local_stability", 3))
        issue_penalty = min(
            len(registry_meta.get("known_issues", []) or []) + len(model_profile.get("known_issues", []) or []),
            3,
        )
        final_score = capability_score * 10 + local_stability * 3 - issue_penalty * 4
        specialized_rank = 1 if agent in SPECIALIZED_CLI else 0
        rows.append(
            {
                "agent": agent,
                "model": canonical,
                "capability_score": capability_score,
                "local_stability": local_stability,
                "cost_efficiency": int(model_profile.get("cost_efficiency", 3)),
                "issue_penalty": issue_penalty,
                "final_score": final_score,
                "specialized_rank": specialized_rank,
                "position": position,
                "routing_tier": routing_tier,
            }
        )

    # Protected fallbacks have their own provider-specific gate above. Once
    # they pass that gate, they should behave like normal non-last-resort
    # providers and still suppress Codex-style last-resort reviewers.
    if any(row.get("routing_tier") != "last-resort" for row in rows):
        rows = [row for row in rows if row.get("routing_tier") != "last-resort"]

    if manual_order:
        rows.sort(key=lambda row: row["position"])
    else:
        rows.sort(
            key=lambda row: (
                -row["final_score"],
                -row["capability_score"],
                -row["local_stability"],
                -row["cost_efficiency"],
                -row["specialized_rank"],
                row["agent"],
                row["model"],
            )
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--manual-order")
    parser.add_argument("--requires-repo-inspection", action="store_true")
    parser.add_argument("--provider-policy")
    args = parser.parse_args()

    matrix = parse_matrix(Path(args.matrix))
    registry = parse_registry(Path(args.registry))
    provider_policy = load_provider_policy(args.provider_policy)
    rows = candidate_rows(
        matrix=matrix,
        registry=registry,
        manual_order=args.manual_order,
        requires_repo_inspection=args.requires_repo_inspection,
        provider_policy=provider_policy,
    )
    for row in rows:
        print(
            "\t".join(
                [
                    row["agent"],
                    row["model"],
                    str(row["final_score"]),
                    str(row["capability_score"]),
                    str(row["local_stability"]),
                ]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

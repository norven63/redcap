#!/usr/bin/env python3
"""Load the single authoritative Prism provider policy."""

from __future__ import annotations

import json
import pathlib
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT_RELATIVE_PATH = pathlib.Path("assets/contracts/prism-provider-policy.json")
KNOWN_PROVIDERS = {"claude-code", "kimi"}


def validate_provider_policy(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if payload.get("schema_id") != "redcap-prism-provider-policy":
        failures.append("provider policy schema_id must be redcap-prism-provider-policy")
    if payload.get("schema_version") != 1:
        failures.append("provider policy schema_version must be 1")
    if payload.get("status") != "active":
        failures.append("provider policy status must be active")
    if payload.get("live_dispatch_frozen") is not True:
        failures.append("provider policy must freeze retired-provider live dispatch")
    if not isinstance(payload.get("frozen_at"), str) or not payload["frozen_at"].strip():
        failures.append("provider policy frozen_at must be non-empty")
    required = payload.get("required_providers")
    active = payload.get("active_dispatch_providers")
    historical = payload.get("historical_read_compatibility")
    for label, providers in [
        ("required_providers", required),
        ("active_dispatch_providers", active),
        ("historical_read_compatibility", historical),
    ]:
        if not isinstance(providers, list) or not all(isinstance(item, str) and item for item in providers):
            failures.append(f"provider policy {label} must be a string list")
            continue
        if len(providers) != len(set(providers)):
            failures.append(f"provider policy {label} must not contain duplicates")
        unknown = sorted(set(providers) - KNOWN_PROVIDERS)
        if unknown:
            failures.append(f"provider policy {label} contains unknown providers: {unknown}")
    if isinstance(required, list) and isinstance(active, list) and required != active:
        failures.append("provider policy required_providers must equal active_dispatch_providers")
    if required != ["claude-code"]:
        failures.append("current provider policy must require only claude-code")
    if isinstance(active, list) and isinstance(historical, list) and set(active) & set(historical):
        failures.append("active and historical providers must be disjoint")
    claims = payload.get("claims")
    if not isinstance(claims, dict):
        failures.append("provider policy claims must be an object")
    else:
        if claims.get("heterogeneous_redteam_equivalent") is not False:
            failures.append("single-provider policy must not claim heterogeneous redteam equivalence")
        if claims.get("multi_provider_consensus_allowed") is not False:
            failures.append("single-provider policy must not claim multi-provider consensus")
    resolution = payload.get("concern_resolution")
    if not isinstance(resolution, dict):
        failures.append("provider policy concern_resolution must be an object")
    else:
        if resolution.get("same_provider_pass_closes_prior_concern") is not False:
            failures.append("same-provider pass must not automatically close a prior concern")
        if resolution.get("cap_resolution_required") is not True:
            failures.append("single-provider concern handling must require Cap resolution")
        fields = resolution.get("required_trace_fields")
        expected = {
            "task_id",
            "provider_review_refs",
            "decision",
            "rationale",
            "source_code_refs",
            "contract_refs",
            "test_run_refs",
            "norven_decision_ref",
        }
        if not isinstance(fields, list) or set(fields) != expected:
            failures.append("provider policy concern resolution trace fields are incomplete")
    if not isinstance(payload.get("user_decision_ref"), str) or not payload["user_decision_ref"].strip():
        failures.append("provider policy must preserve the user decision reference")
    return failures


def load_provider_policy(repo_root: pathlib.Path | None = None) -> dict[str, Any]:
    root = pathlib.Path(repo_root).resolve() if repo_root is not None else REPO_ROOT
    path = root / CONTRACT_RELATIVE_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot load Prism provider policy {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Prism provider policy must be a JSON object: {path}")
    failures = validate_provider_policy(payload)
    if failures:
        raise RuntimeError("invalid Prism provider policy: " + "; ".join(failures))
    return payload


def required_providers(repo_root: pathlib.Path | None = None) -> list[str]:
    return list(load_provider_policy(repo_root)["required_providers"])


def active_dispatch_providers(repo_root: pathlib.Path | None = None) -> list[str]:
    return list(load_provider_policy(repo_root)["active_dispatch_providers"])


def historical_read_compatibility(repo_root: pathlib.Path | None = None) -> list[str]:
    return list(load_provider_policy(repo_root)["historical_read_compatibility"])


def all_known_policy_providers(repo_root: pathlib.Path | None = None) -> set[str]:
    policy = load_provider_policy(repo_root)
    return set(policy["active_dispatch_providers"]) | set(policy["historical_read_compatibility"])


def validate_cap_resolution_trace(payload: dict[str, Any], repo_root: pathlib.Path | None = None) -> list[str]:
    policy = load_provider_policy(repo_root)
    resolution = policy["concern_resolution"]
    failures: list[str] = []
    if payload.get("schema_id") != "redcap-cap-review-resolution":
        failures.append("Cap resolution trace schema_id must be redcap-cap-review-resolution")
    for field in resolution["required_trace_fields"]:
        if field not in payload:
            failures.append(f"Cap resolution trace missing {field}")
    for field, minimum in resolution["minimum_independent_evidence"].items():
        value = payload.get(field)
        if not isinstance(value, list) or len([item for item in value if isinstance(item, str) and item.strip()]) < minimum:
            failures.append(f"Cap resolution trace {field} requires at least {minimum} reference(s)")
    provider_refs = payload.get("provider_review_refs")
    if not isinstance(provider_refs, list) or not provider_refs:
        failures.append("Cap resolution trace provider_review_refs must be non-empty")
    if payload.get("decision") not in {"accept", "reject", "escalate"}:
        failures.append("Cap resolution trace decision must be accept, reject or escalate")
    if not isinstance(payload.get("rationale"), str) or not payload["rationale"].strip():
        failures.append("Cap resolution trace rationale must be non-empty")
    if not isinstance(payload.get("norven_decision_ref"), str) or not payload["norven_decision_ref"].strip():
        failures.append("Cap resolution trace must preserve a Norven decision reference")
    return failures

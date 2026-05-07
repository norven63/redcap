#!/usr/bin/env python3
# 用途：公共知识库治理脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#shared-knowledge-layer

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "references/public-arsenal-claim-boundary-policy.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-public-arsenal-claim-boundary] {message}")


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


def repo_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def resolve_worktree(binding: dict[str, Any]) -> Path | None:
    raw = binding.get("preferred_local_worktree")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return repo_path(raw.strip())


def substantive_entries(worktree: Path | None) -> int:
    return len(substantive_entry_paths(worktree))


def substantive_entry_paths(worktree: Path | None) -> list[Path]:
    if worktree is None or not worktree.is_dir():
        return []
    users_root = worktree / "users"
    if not users_root.is_dir():
        return []
    entries: list[Path] = []
    for path in users_root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(worktree).as_posix()
        if path.name == ".gitkeep":
            continue
        parts = rel.split("/")
        if len(parts) < 3 or parts[0] != "users" or not parts[1]:
            fail(f"substantive entry must live under users/<user>/: {rel}")
        if not rel.endswith(".md"):
            fail(f"substantive public entry must be markdown: {rel}")
        entries.append(path)
    return sorted(entries)


def finding_by_id(review: dict[str, Any], finding_id: str) -> dict[str, Any] | None:
    findings = review.get("findings")
    if not isinstance(findings, list):
        fail("pre-release review findings must be a list")
    for item in findings:
        if isinstance(item, dict) and item.get("id") == finding_id:
            return item
    return None


def validate_readme(path: Path, policy: dict[str, Any], label: str, contract_key: str = "readme_contract") -> None:
    if not path.is_file():
        fail(f"{label} README missing: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    contract = policy.get(contract_key)
    if not isinstance(contract, dict):
        fail(f"policy {contract_key} must be an object")
    for phrase in require_list(contract, "required_phrases", contract_key):
        if not isinstance(phrase, str) or phrase not in text:
            fail(f"{label} README missing required phrase: {phrase}")
    for phrase in require_list(contract, "forbidden_phrases", contract_key):
        if isinstance(phrase, str) and phrase and phrase in text:
            fail(f"{label} README contains forbidden phrase: {phrase}")


def validate_public_entries(worktree: Path | None, policy: dict[str, Any]) -> None:
    state = policy["current_state"]
    content_state = state["content_state"]
    entries = substantive_entry_paths(worktree)
    if content_state == "template-only":
        return
    requirements = policy.get("reviewed_substantive_entry_contract")
    if not isinstance(requirements, dict):
        fail("reviewed-substantive state requires reviewed_substantive_entry_contract")
    required_sections = [str(item).strip() for item in require_list(requirements, "required_sections", "reviewed_substantive_entry_contract")]
    forbidden_patterns = [str(item).strip() for item in require_list(requirements, "forbidden_patterns", "reviewed_substantive_entry_contract")]
    minimum_entries = requirements.get("minimum_entries")
    if not isinstance(minimum_entries, int) or minimum_entries < 1:
        fail("reviewed_substantive_entry_contract.minimum_entries must be a positive integer")
    if len(entries) < minimum_entries:
        fail(f"reviewed-substantive state requires at least {minimum_entries} entries")
    heading_re = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
    for path in entries:
        rel = path.relative_to(worktree).as_posix() if worktree else str(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        headings = {match.group(1).strip() for match in heading_re.finditer(text)}
        missing = sorted(section for section in required_sections if section not in headings)
        if missing:
            fail(f"public entry missing required sections {missing}: {rel}")
        for pattern in forbidden_patterns:
            if re.search(pattern, text):
                fail(f"public entry contains forbidden pattern {pattern}: {rel}")


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "public-arsenal-claim-boundary":
        fail("policy_id must be public-arsenal-claim-boundary")
    if policy.get("status") not in {"template-only-claim-boundary", "reviewed-substantive-claim-boundary"}:
        fail("policy status must be template-only-claim-boundary or reviewed-substantive-claim-boundary")
    if require_text(policy, "public_repository_name", "policy") != "redcap-arsenal":
        fail("public_repository_name must be redcap-arsenal")
    state = policy.get("current_state")
    if not isinstance(state, dict):
        fail("policy current_state must be an object")
    content_state = state.get("content_state")
    if content_state not in {"template-only", "reviewed-substantive"}:
        fail("policy current_state.content_state must be template-only or reviewed-substantive")
    entries = state.get("substantive_entries")
    if not isinstance(entries, int) or entries < 0:
        fail("policy current_state.substantive_entries must be a non-negative integer")
    if content_state == "template-only" and entries != 0:
        fail("template-only state must report zero substantive entries")
    if content_state == "reviewed-substantive" and entries <= 0:
        fail("reviewed-substantive state must report at least one substantive entry")
    for key in ["template_only_allowed_claims", "template_only_forbidden_claims", "must_not_claim"]:
        values = require_list(policy, key, "policy")
        if len(values) < 4:
            fail(f"policy {key} must contain at least 4 concrete claims")
    if content_state == "reviewed-substantive":
        values = require_list(policy, "reviewed_substantive_allowed_claims", "policy")
        if len(values) < 4:
            fail("policy reviewed_substantive_allowed_claims must contain at least 4 concrete claims")
    thresholds = policy.get("promotion_thresholds")
    if not isinstance(thresholds, dict):
        fail("policy promotion_thresholds must be an object")
    if thresholds.get("populated_claim_requires_substantive_entries") is not True:
        fail("populated claim must require substantive entries")
    if thresholds.get("substantive_entries_must_live_under") != "users/<user>/":
        fail("substantive_entries_must_live_under must be users/<user>/")
    required_steps = {
        "RedCap Forge promotion decision",
        "privacy and secret scan",
        "duplicate check",
        "append-only entry schema validation",
        "metadata/index refresh",
        "shared-knowledge remote binding safety check",
    }
    raw_steps = [str(item).strip() for item in require_list(thresholds, "required_before_populated_claim", "promotion_thresholds")]
    actual_steps = set(raw_steps)
    if len(raw_steps) != len(actual_steps):
        fail("promotion thresholds contain duplicate required steps")
    missing_steps = sorted(required_steps - actual_steps)
    if missing_steps:
        fail("promotion thresholds missing required steps: " + ", ".join(missing_steps))
    extra_steps = sorted(actual_steps - required_steps)
    if extra_steps:
        fail("promotion thresholds contain unsupported extra steps: " + ", ".join(extra_steps))
    relation = policy.get("release_relation")
    if not isinstance(relation, dict):
        fail("policy release_relation must be an object")
    if relation.get("p4_2e_blocks_broad_marketing_claims") is not True:
        fail("P4-2e must block broad marketing claims")
    if relation.get("p4_2e_blocks_default_cli_release") is not False:
        fail("P4-2e must not be a default CLI release blocker")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate public redcap-arsenal claim boundary.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy = load_json(Path(args.policy), "public arsenal claim boundary policy")
    validate_policy(policy)

    shared = load_json(root / policy["shared_knowledge_policy_path"], "shared knowledge policy")
    binding = load_json(root / policy["remote_binding_path"], "shared knowledge remote binding")
    forge = load_json(root / policy["forge_policy_path"], "RedCap Forge policy")
    review = load_json(root / policy["pre_release_review_path"], "pre-release product architecture review")

    if shared.get("public_repository_name") != "redcap-arsenal":
        fail("shared knowledge policy public_repository_name mismatch")
    if "RedCap Forge" not in str(shared.get("forge_pipeline", "")):
        fail("shared knowledge policy must route public entries through RedCap Forge")
    if binding.get("remote_repo") != "redcap-arsenal":
        fail("remote binding remote_repo mismatch")
    expected_mode = "template-only" if policy["current_state"]["content_state"] == "template-only" else "forge-append-only"
    if binding.get("publish_mode") != expected_mode:
        fail(f"remote binding publish_mode must be {expected_mode}")
    if forge.get("canonical_names", {}).get("public_repository") != "redcap-arsenal":
        fail("RedCap Forge policy public repository mismatch")
    forge_must_not_claim = " ".join(map(str, forge.get("must_not_claim", [])))
    for phrase in ["raw reports", "active identity"]:
        if phrase not in forge_must_not_claim:
            fail(f"RedCap Forge must_not_claim missing phrase: {phrase}")

    worktree = resolve_worktree(binding)
    actual_entries = substantive_entries(worktree)
    expected_entries = policy["current_state"]["substantive_entries"]
    if actual_entries != expected_entries:
        fail(f"substantive entry count mismatch: policy={expected_entries} actual={actual_entries}")
    validate_public_entries(worktree, policy)

    facts = review.get("observed_facts")
    if not isinstance(facts, dict):
        fail("pre-release review observed_facts must be an object")
    if facts.get("redcap_arsenal_content_state") != policy["current_state"]["content_state"]:
        fail("pre-release review redcap_arsenal_content_state mismatch")
    if facts.get("redcap_arsenal_substantive_entries") != actual_entries:
        fail("pre-release review redcap_arsenal_substantive_entries mismatch")

    expected_finding = "public-arsenal-template-only" if policy["current_state"]["content_state"] == "template-only" else "public-arsenal-reviewed-substantive-minimum"
    finding = finding_by_id(review, expected_finding)
    if finding is None:
        fail(f"pre-release review missing {expected_finding} finding")
    if finding.get("severity") not in {"should-fix", "pass"}:
        fail(f"{expected_finding} finding severity must be should-fix or pass")
    if policy["current_state"]["content_state"] == "template-only" and "must not be marketed" not in str(finding.get("claim", "")):
        fail("public-arsenal-template-only finding must explicitly forbid marketing as populated")
    if policy["current_state"]["content_state"] == "reviewed-substantive" and "does not make redcap-arsenal mature" not in str(finding.get("claim", "")):
        fail("reviewed substantive finding must explicitly keep maturity claims bounded")

    must_not_claim = " ".join(map(str, review.get("must_not_claim", [])))
    forbidden_claim_phrase = (
        "redcap-arsenal contains substantive migrated knowledge"
        if policy["current_state"]["content_state"] == "template-only"
        else "redcap-arsenal is mature or complete"
    )
    for phrase in [
        forbidden_claim_phrase,
        "public-release-ready",
    ]:
        if phrase not in must_not_claim:
            fail(f"pre-release review must_not_claim missing: {phrase}")

    shared_contract = "template_readme_contract" if policy["current_state"]["content_state"] == "reviewed-substantive" else "readme_contract"
    validate_readme(root / "shared-knowledge/README.md", policy, "shared-knowledge template", shared_contract)
    if worktree is not None and worktree.is_dir():
        validate_readme(worktree / "README.md", policy, "public worktree")

    print(
        "PUBLIC_ARSENAL_CLAIM_BOUNDARY_OK "
        f"state={policy['current_state']['content_state']} "
        f"substantive_entries={actual_entries} "
        f"worktree={'present' if worktree and worktree.is_dir() else 'absent'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

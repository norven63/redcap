#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "references/llm-wiki-lite-policy.json"
SCHEMA = ROOT / "references/llm-wiki-lite-entry.schema.json"
ASSET_POLICY = ROOT / "references/llm-wiki-asset-stratification-policy.json"
FORGE_POLICY = ROOT / "references/redcap-forge-policy.json"
RETRIEVAL_POLICY = ROOT / "references/retrieval-escalation-policy.json"
INDEX = ROOT / "compass/knowledge/llm-wiki/index.json"
ENTRY_ROOT = ROOT / "compass/knowledge/llm-wiki/entries"

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,80}$")
STATIC_SECRET_PATTERNS = [
    "GEMINI_API_KEY",
    "KIMI_API_KEY",
    "FEISHU",
    "Uer56",
    "BEGIN PRIVATE KEY",
    "sk-",
]
PRIVACY_LEVEL = {
    "public": 0,
    "internal": 1,
    "private": 2,
    "sensitive": 3,
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-llm-wiki-lite] {message}")


def load_json(path: Path, label: str = "json") -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be a JSON object")
    return payload


def require_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        fail(f"{key} must be a non-empty list")
    return value


def require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        fail(f"{key} must be an object")
    return value


def require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{key} must be a non-empty string")
    return value.strip()


def repo_rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        fail(f"path escapes RedCap repo: {path}")


def resolve_repo_path(root: Path, raw: str) -> Path:
    if not raw or raw.startswith("~"):
        fail(f"invalid repo path: {raw}")
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        fail(f"repo path must be relative and non-traversal: {raw}")
    return root / path


def sha256_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def validate_iso_utc(raw: str, field: str) -> None:
    if not isinstance(raw, str) or not raw.endswith("Z"):
        fail(f"{field} must be ISO-8601 UTC with Z suffix")
    try:
        parsed = datetime.fromisoformat(raw[:-1] + "+00:00")
    except ValueError:
        fail(f"{field} must be valid ISO-8601 UTC")
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        fail(f"{field} must be UTC")


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def validate_schema(schema: dict[str, Any], policy: dict[str, Any]) -> None:
    if schema.get("version") != 1:
        fail("entry schema version must be 1")
    if schema.get("schema_id") != "llm-wiki-lite-entry":
        fail("entry schema_id must be llm-wiki-lite-entry")
    if schema.get("type") != "object":
        fail("entry schema type must be object")
    if schema.get("additionalProperties") is not False:
        fail("entry schema must reject additionalProperties")

    required = require_list(schema, "required")
    policy_required = require_list(require_dict(policy, "entry_contract"), "required_fields")
    missing = sorted(set(policy_required) - {str(item) for item in required})
    if missing:
        fail("entry schema missing required fields from policy: " + ", ".join(missing))

    properties = require_dict(schema, "properties")
    for field in policy_required:
        if field not in properties:
            fail(f"entry schema missing property: {field}")


def validate_policy(policy: dict[str, Any], root: Path) -> None:
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "llm-wiki-lite-lifecycle":
        fail("policy_id must be llm-wiki-lite-lifecycle")
    if policy.get("parent_child_id") != "P4-2h-3":
        fail("parent_child_id must be P4-2h-3")
    if policy.get("status") != "implemented-minimum-lifecycle":
        fail("policy status must be implemented-minimum-lifecycle")

    storage = require_dict(policy, "storage")
    if storage.get("visibility") != "private":
        fail("LLM-wiki-lite storage must stay private")
    if storage.get("authority") != "non-authoritative-derived-context":
        fail("LLM-wiki-lite storage must stay non-authoritative")

    required_surfaces = require_list(policy, "required_surfaces")
    for raw in required_surfaces:
        if not isinstance(raw, str) or not raw.strip():
            fail("required_surfaces entries must be strings")
        if not resolve_repo_path(root, raw).exists():
            fail(f"required surface missing: {raw}")

    source_anchor = require_dict(policy, "source_anchor_contract")
    if source_anchor.get("required") is not True:
        fail("source anchors must be required")
    minimum_fields = {str(item) for item in require_list(source_anchor, "minimum_fields")}
    for field in ["source_path", "source_kind", "commit_sha_or_digest", "last_reviewed_at", "privacy_classification"]:
        if field not in minimum_fields:
            fail(f"source anchor minimum field missing: {field}")
    if source_anchor.get("digest_prefix") != "sha256:":
        fail("source anchor digest_prefix must be sha256:")
    if "must not inline raw private" not in str(source_anchor.get("raw_excerpt_rule", "")).lower():
        fail("raw excerpt rule must forbid raw private content")

    forge = require_dict(policy, "forge_promotion_boundary")
    if forge.get("public_write_allowed_from_wiki") is not False:
        fail("public_write_allowed_from_wiki must remain false")
    if forge.get("requires_redcap_forge") is not True:
        fail("requires_redcap_forge must remain true")
    for target in ["redcap-arsenal", "shared-knowledge", "public wiki pages"]:
        if target not in {str(item) for item in require_list(forge, "must_not_write_directly")}:
            fail(f"forge boundary must forbid direct write to {target}")

    disabled = require_dict(policy, "disabled_capabilities")
    for key in ["full_wiki_product", "background_generator", "rag", "graphrag", "vector_store", "automatic_public_writeback"]:
        if disabled.get(key) is not False:
            fail(f"disabled capability must remain false: {key}")

    claims = [str(item) for item in require_list(policy, "must_not_claim")]
    for phrase in ["complete LLM-wiki", "source of truth", "RAG", "GraphRAG", "private reports", "RedCap Forge", "npm/public release"]:
        if not any(phrase in claim for claim in claims):
            fail(f"must_not_claim missing phrase: {phrase}")


def candidate_sets(asset_policy: dict[str, Any]) -> tuple[set[str], set[str]]:
    candidates = require_list(asset_policy, "llm_wiki_candidate_types")
    allowed: set[str] = set()
    denied: set[str] = set()
    for item in candidates:
        if not isinstance(item, dict):
            fail("llm_wiki_candidate_types entries must be objects")
        candidate_id = require_text(item, "id")
        marker = item.get("allowed")
        if marker is True or marker == "guarded":
            allowed.add(candidate_id)
        elif marker is False:
            denied.add(candidate_id)
        else:
            fail(f"candidate type has invalid allowed marker: {candidate_id}")
    return allowed, denied


def validate_cross_policies(policy: dict[str, Any], asset_policy: dict[str, Any]) -> tuple[set[str], set[str], list[str]]:
    if asset_policy.get("policy_id") != "llm-wiki-asset-stratification":
        fail("asset stratification policy_id mismatch")
    allowed, denied = candidate_sets(asset_policy)

    denied_from_policy = {str(item) for item in require_list(require_dict(policy, "entry_contract"), "deny_candidate_types")}
    if not denied_from_policy <= denied:
        fail("LLM-wiki-lite deny_candidate_types must be inherited from asset stratification denylist")

    retrieval = load_json(RETRIEVAL_POLICY, "retrieval escalation policy")
    routes = require_list(retrieval, "routes")
    by_route = {str(item.get("id")): item for item in routes if isinstance(item, dict)}
    for route in ["rag", "graphrag"]:
        if by_route.get(route, {}).get("allowed_now") is not False:
            fail(f"{route} must remain disabled in retrieval escalation policy")

    forge = load_json(FORGE_POLICY, "RedCap Forge policy")
    responsibilities = {str(item.get("id")) for item in require_list(forge, "responsibilities") if isinstance(item, dict)}
    for required in ["privacy-safety", "dedupe", "promote"]:
        if required not in responsibilities:
            fail(f"RedCap Forge responsibility missing: {required}")

    denied_paths = [str(item) for item in require_list(require_dict(policy, "candidate_selection"), "denied_source_paths")]
    return allowed, denied, denied_paths


def secret_patterns(root: Path) -> list[str]:
    patterns = list(STATIC_SECRET_PATTERNS)
    home = Path.home().as_posix()
    if home and home != "/":
        patterns.append(home)
    feishu_policy = root / "references/feishu-notification-policy.json"
    if feishu_policy.is_file():
        try:
            profile = load_json(feishu_policy, "Feishu policy").get("required_lark_cli_profile")
        except SystemExit:
            profile = None
        if isinstance(profile, str) and profile.strip():
            patterns.append(profile.strip())
    return patterns


def validate_index(root: Path, index_path: Path, entry_root: Path) -> dict[str, dict[str, Any]]:
    index = load_json(index_path, "LLM-wiki-lite index")
    if index.get("version") != 1:
        fail("index version must be 1")
    if index.get("store_id") != "redcap-private-llm-wiki-lite":
        fail("index store_id must be redcap-private-llm-wiki-lite")
    if index.get("visibility") != "private":
        fail("index visibility must be private")
    if index.get("authority") != "non-authoritative-derived-context":
        fail("index authority must be non-authoritative")

    entries = require_list(index, "entries")
    by_id: dict[str, dict[str, Any]] = {}
    for item in entries:
        if not isinstance(item, dict):
            fail("index entries must be objects")
        entry_id = require_text(item, "id")
        if entry_id in by_id:
            fail(f"duplicate index entry id: {entry_id}")
        path_text = require_text(item, "path")
        path = resolve_repo_path(root, path_text)
        if not path.is_file():
            fail(f"index entry file missing: {path_text}")
        if repo_rel(root, path.parent) != repo_rel(root, entry_root):
            fail(f"index entry must live under entry root: {path_text}")
        if path.name != f"{entry_id}.json":
            fail(f"index entry path must match id: {entry_id}")
        by_id[entry_id] = item

    indexed_files = {require_text(item, "path") for item in entries if isinstance(item, dict)}
    actual_files = {
        repo_rel(root, path)
        for path in sorted(entry_root.glob("*.json"))
        if path.is_file()
    }
    extra = sorted(actual_files - indexed_files)
    if extra:
        fail("LLM-wiki-lite entries missing from index: " + ", ".join(extra))
    return by_id


def validate_entry(
    root: Path,
    entry_path: Path,
    index_row: dict[str, Any],
    required_fields: set[str],
    allowed_candidates: set[str],
    denied_candidates: set[str],
    denied_paths: list[str],
) -> None:
    entry = load_json(entry_path, f"entry {entry_path.name}")
    extra = sorted(set(entry.keys()) - required_fields)
    if extra:
        fail(f"{entry_path.name} has unexpected fields: " + ", ".join(extra))
    missing = sorted(required_fields - set(entry.keys()))
    if missing:
        fail(f"{entry_path.name} missing fields: " + ", ".join(missing))

    entry_id = require_text(entry, "id")
    if not SLUG_RE.fullmatch(entry_id):
        fail(f"entry id must be slug-like: {entry_id}")
    if entry_path.name != f"{entry_id}.json":
        fail(f"entry path must match id: {entry_id}")
    if entry.get("version") != 1:
        fail(f"{entry_id}.version must be 1")
    if entry.get("visibility") != "private":
        fail(f"{entry_id}.visibility must be private")
    if entry.get("authority") != "non-authoritative-derived-context":
        fail(f"{entry_id}.authority must be non-authoritative-derived-context")
    if entry.get("status") not in {"active", "stale", "retired"}:
        fail(f"{entry_id}.status is unsupported")
    if index_row.get("status") != entry.get("status"):
        fail(f"index status differs from entry: {entry_id}")

    candidate_type = require_text(entry, "candidate_type")
    if candidate_type in denied_candidates:
        fail(f"entry candidate_type is denied by asset stratification: {candidate_type}")
    if candidate_type not in allowed_candidates:
        fail(f"entry candidate_type is not allowed by asset stratification: {candidate_type}")
    if index_row.get("candidate_type") != candidate_type:
        fail(f"index candidate_type differs from entry: {entry_id}")

    privacy = require_text(entry, "privacy_classification")
    if privacy not in PRIVACY_LEVEL:
        fail(f"{entry_id}.privacy_classification is unsupported")

    body = str(entry.get("body", ""))
    summary = str(entry.get("summary", ""))
    for needle in secret_patterns(root):
        if needle in body or needle in summary:
            fail(f"{entry_id} appears to contain private or secret material: {needle}")
    if len(summary.strip()) < 10 or len(body.strip()) < 20:
        fail(f"{entry_id} summary/body are too short")

    forge = require_dict(entry, "forge_promotion")
    if forge.get("requires_forge") is not True:
        fail(f"{entry_id}.forge_promotion.requires_forge must be true")
    if forge.get("public_write_allowed") is not False:
        fail(f"{entry_id}.forge_promotion.public_write_allowed must be false")

    anchors = require_list(entry, "source_anchors")
    for idx, anchor in enumerate(anchors, start=1):
        if not isinstance(anchor, dict):
            fail(f"{entry_id}.source_anchors[{idx}] must be an object")
        source_path = require_text(anchor, "source_path")
        if matches_any(source_path, denied_paths):
            fail(f"{entry_id} source path belongs to denied layer: {source_path}")
        source_file = resolve_repo_path(root, source_path)
        if not source_file.is_file():
            fail(f"{entry_id} source anchor does not resolve: {source_path}")
        digest = require_text(anchor, "commit_sha_or_digest")
        if not digest.startswith("sha256:"):
            fail(f"{entry_id} source anchor must use sha256 digest: {source_path}")
        current = sha256_digest(source_file)
        if current != digest:
            fail(f"{entry_id} source anchor stale digest for {source_path}")
        source_privacy = require_text(anchor, "privacy_classification")
        if source_privacy not in PRIVACY_LEVEL:
            fail(f"{entry_id} source privacy classification unsupported: {source_privacy}")
        if PRIVACY_LEVEL[privacy] < PRIVACY_LEVEL[source_privacy]:
            fail(f"{entry_id} privacy classification is weaker than source: {source_path}")
        validate_iso_utc(require_text(anchor, "last_reviewed_at"), f"{entry_id}.source_anchors[{idx}].last_reviewed_at")
        require_text(anchor, "source_kind")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap's private LLM-wiki-lite lifecycle.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--policy", type=Path, default=POLICY)
    parser.add_argument("--schema", type=Path, default=SCHEMA)
    parser.add_argument("--asset-policy", type=Path, default=ASSET_POLICY)
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--entry-root", type=Path, default=ENTRY_ROOT)
    args = parser.parse_args()

    root = args.root.resolve()
    policy = load_json(args.policy if args.policy.is_absolute() else root / args.policy, "LLM-wiki-lite policy")
    schema = load_json(args.schema if args.schema.is_absolute() else root / args.schema, "LLM-wiki-lite entry schema")
    asset_policy = load_json(args.asset_policy if args.asset_policy.is_absolute() else root / args.asset_policy, "LLM-wiki asset stratification policy")
    index_path = args.index if args.index.is_absolute() else root / args.index
    entry_root = args.entry_root if args.entry_root.is_absolute() else root / args.entry_root

    validate_policy(policy, root)
    validate_schema(schema, policy)
    allowed_candidates, denied_candidates, denied_paths = validate_cross_policies(policy, asset_policy)
    index_rows = validate_index(root, index_path, entry_root)
    required_fields = {str(item) for item in require_list(require_dict(policy, "entry_contract"), "required_fields")}

    for entry_id, row in sorted(index_rows.items()):
        entry_path = resolve_repo_path(root, require_text(row, "path"))
        validate_entry(root, entry_path, row, required_fields, allowed_candidates, denied_candidates, denied_paths)

    print(f"LLM_WIKI_LITE_OK entries={len(index_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

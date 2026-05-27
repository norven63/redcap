#!/usr/bin/env python3
# 用途：长期记忆路线图脚本；校验 full LLM-wiki 产品骨架、队列、索引、receipt 与 source anchor。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "assets/references/full-llm-wiki-policy.json"
ENTRY_SCHEMA = ROOT / "assets/references/full-llm-wiki-entry.schema.json"
CANDIDATE_SCHEMA = ROOT / "assets/references/full-llm-wiki-candidate.schema.json"
RAG_POLICY = ROOT / "assets/references/rag-graphrag-boundary-policy.json"
ROADMAP = ROOT / "assets/references/full-llm-wiki-roadmap.json"
INDEX = ROOT / "assets/knowledge/llm-wiki-full/index.json"
QUEUE_INDEX = ROOT / "assets/knowledge/llm-wiki-full/queue/index.json"
RECEIPT_INDEX = ROOT / "assets/knowledge/llm-wiki-full/receipts/index.json"

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,80}$")
SECRET_PATTERNS = [
    "GEMINI_API_KEY",
    "KIMI_API_KEY",
    "FEISHU",
    "BEGIN PRIVATE KEY",
    "Uer56",
]
SECRET_REGEXES = [
    re.compile(r"sk-[A-Za-z0-9_\\-]{16,}"),
]


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-full-llm-wiki] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be an object")
    return payload


def require_text(payload: dict[str, Any], key: str, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{label}: missing non-empty {key}")
    return value.strip()


def require_list(payload: dict[str, Any], key: str, label: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        fail(f"{label}: {key} must be a list")
    return value


def require_non_empty_list(payload: dict[str, Any], key: str, label: str) -> list[Any]:
    value = require_list(payload, key, label)
    if not value:
        fail(f"{label}: {key} must be non-empty")
    return value


def resolve_repo_path(raw: str) -> Path:
    if not raw or raw.startswith("~"):
        fail(f"invalid repo path: {raw}")
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        fail(f"repo path must be relative and non-traversal: {raw}")
    return ROOT / path


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        fail(f"path escapes repo: {path}")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def validate_iso(raw: str, field: str) -> None:
    if not isinstance(raw, str) or not raw.endswith("Z"):
        fail(f"{field} must be ISO-8601 UTC with Z suffix")
    try:
        datetime.fromisoformat(raw[:-1] + "+00:00")
    except ValueError:
        fail(f"{field} must be valid ISO-8601 UTC")


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def scan_for_secrets(text: str, label: str) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern in text:
            fail(f"{label} contains forbidden secret marker: {pattern}")
    for pattern in SECRET_REGEXES:
        if pattern.search(text):
            fail(f"{label} contains forbidden secret marker: {pattern.pattern}")


def validate_schema_identity(schema: dict[str, Any], expected_id: str, label: str) -> None:
    if schema.get("version") != 1 or schema.get("schema_id") != expected_id:
        fail(f"{label} identity mismatch")
    if schema.get("type") != "object":
        fail(f"{label} must be object schema")
    if schema.get("additionalProperties") is not False:
        fail(f"{label} must reject additionalProperties")
    required = require_non_empty_list(schema, "required", label)
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        fail(f"{label} properties must be object")
    missing = [str(item) for item in required if str(item) not in properties]
    if missing:
        fail(f"{label} missing properties: {', '.join(missing)}")


def validate_policy(policy: dict[str, Any]) -> list[str]:
    if policy.get("version") != 1 or policy.get("policy_id") != "full-llm-wiki-product":
        fail("policy identity mismatch")
    if policy.get("status") != "implemented-controlled-local-product":
        fail("policy status must be implemented-controlled-local-product")
    storage = policy.get("storage")
    if not isinstance(storage, dict):
        fail("policy storage must be object")
    if storage.get("visibility") != "private":
        fail("full LLM-wiki must remain private")
    if storage.get("authority") != "non-authoritative-derived-context":
        fail("full LLM-wiki must remain non-authoritative")
    worker = policy.get("worker_contract")
    if not isinstance(worker, dict):
        fail("worker_contract must be object")
    if worker.get("automatic_source_mutation_allowed") is not False:
        fail("worker must not mutate source automatically")
    if worker.get("automatic_public_writeback_allowed") is not False:
        fail("worker must not public-write automatically")
    rag = policy.get("rag_boundary")
    if not isinstance(rag, dict) or rag.get("real_backend_enabled") is not False:
        fail("full wiki must keep real RAG backend disabled")
    for phrase in ["source of truth", "RAG", "GraphRAG", "public arsenal"]:
        if phrase not in " ".join(str(item) for item in require_non_empty_list(policy, "must_not_claim", "policy")):
            fail(f"must_not_claim missing phrase: {phrase}")
    required = [str(item) for item in require_non_empty_list(policy, "required_surfaces", "policy")]
    for raw in required:
        if not resolve_repo_path(raw).exists():
            fail(f"required surface missing: {raw}")
    denied = policy.get("source_boundaries", {}).get("denied_source_paths")
    if not isinstance(denied, list):
        fail("source_boundaries.denied_source_paths must be list")
    return [str(item) for item in denied]


def validate_entry(entry: dict[str, Any], index_row: dict[str, Any], denied_paths: list[str]) -> None:
    entry_id = require_text(entry, "id", "entry")
    if not SLUG_RE.match(entry_id):
        fail(f"entry id invalid: {entry_id}")
    if entry_id != require_text(index_row, "id", "index row"):
        fail(f"entry id mismatch: {entry_id}")
    if entry.get("version") != 1:
        fail(f"{entry_id}: version must be 1")
    if entry.get("visibility") != "private":
        fail(f"{entry_id}: visibility must be private")
    if entry.get("authority") != "non-authoritative-derived-context":
        fail(f"{entry_id}: authority mismatch")
    if entry.get("status") not in {"active", "stale", "retired"}:
        fail(f"{entry_id}: invalid status")
    if entry.get("privacy_classification") not in {"public", "internal", "private", "sensitive"}:
        fail(f"{entry_id}: invalid privacy_classification")
    scan_for_secrets(str(entry.get("summary", "")) + "\n" + str(entry.get("body", "")), entry_id)

    anchors = require_non_empty_list(entry, "source_anchors", entry_id)
    for anchor in anchors:
        if not isinstance(anchor, dict):
            fail(f"{entry_id}: source anchor must be object")
        source_path = require_text(anchor, "source_path", entry_id)
        if matches_any(source_path, denied_paths):
            fail(f"{entry_id}: denied source path: {source_path}")
        path = resolve_repo_path(source_path)
        if not path.is_file():
            fail(f"{entry_id}: source path missing: {source_path}")
        expected = require_text(anchor, "commit_sha_or_digest", entry_id)
        if not expected.startswith("sha256:"):
            fail(f"{entry_id}: source digest must use sha256 prefix")
        if digest(path) != expected:
            fail(f"{entry_id}: stale source digest for {source_path}")
        validate_iso(require_text(anchor, "last_reviewed_at", entry_id), f"{entry_id}.last_reviewed_at")

    review = entry.get("review_state")
    if not isinstance(review, dict) or review.get("state") not in {"candidate", "reviewing", "accepted", "rejected", "retired"}:
        fail(f"{entry_id}: review_state invalid")
    validate_iso(require_text(review, "reviewed_at", entry_id), f"{entry_id}.reviewed_at")
    receipt = resolve_repo_path(require_text(review, "receipt", entry_id))
    if not receipt.exists():
        fail(f"{entry_id}: review receipt missing")

    staleness = entry.get("staleness")
    if not isinstance(staleness, dict) or staleness.get("source_digest_match") is not True:
        fail(f"{entry_id}: staleness must show source_digest_match=true")
    validate_iso(require_text(staleness, "last_checked_at", entry_id), f"{entry_id}.staleness.last_checked_at")

    forge = entry.get("forge_promotion")
    if not isinstance(forge, dict):
        fail(f"{entry_id}: forge_promotion must be object")
    if forge.get("requires_forge") is not True or forge.get("public_write_allowed") is not False:
        fail(f"{entry_id}: forge boundary invalid")


def validate_index(index: dict[str, Any], denied_paths: list[str]) -> None:
    if index.get("store_id") != "redcap-private-full-llm-wiki":
        fail("full index store_id mismatch")
    if index.get("status") != "implemented-controlled-local-product":
        fail("full index status mismatch")
    if index.get("visibility") != "private":
        fail("full index visibility must be private")
    validate_iso(require_text(index, "generated_at", "index"), "index.generated_at")
    entries = require_non_empty_list(index, "entries", "index")
    seen: set[str] = set()
    for row in entries:
        if not isinstance(row, dict):
            fail("index entries must be objects")
        entry_id = require_text(row, "id", "index row")
        if entry_id in seen:
            fail(f"duplicate full wiki entry id: {entry_id}")
        seen.add(entry_id)
        path = resolve_repo_path(require_text(row, "path", entry_id))
        if not path.is_file():
            fail(f"entry file missing: {path}")
        if rel(path.parent) != "assets/knowledge/llm-wiki-full/entries":
            fail(f"entry must live under full wiki entries: {path}")
        validate_entry(load_json(path, f"entry {entry_id}"), row, denied_paths)

    actual = {path.stem for path in (ROOT / "assets/knowledge/llm-wiki-full/entries").glob("*.json")}
    if actual != seen:
        fail("full wiki index does not match entry files")


def validate_queue_and_receipts() -> None:
    queue = load_json(QUEUE_INDEX, "queue index")
    if queue.get("queue_id") != "redcap-full-llm-wiki-ingest-queue":
        fail("queue id mismatch")
    if queue.get("status") != "active":
        fail("queue must be active")
    if not isinstance(queue.get("candidates"), list):
        fail("queue candidates must be list")
    for row in queue.get("candidates", []):
        if not isinstance(row, dict):
            fail("queue candidate rows must be objects")
        candidate_path = resolve_repo_path(require_text(row, "path", "queue candidate"))
        if not candidate_path.is_file():
            fail(f"queue candidate missing: {candidate_path}")
        candidate = load_json(candidate_path, "queue candidate")
        if candidate.get("status") != "candidate":
            fail(f"queue candidate status mismatch: {candidate_path}")
        privacy = candidate.get("privacy_scan")
        if not isinstance(privacy, dict) or privacy.get("status") != "pass":
            fail(f"queue candidate privacy scan must pass: {candidate_path}")
        receipt_path = resolve_repo_path(require_text(row, "receipt", "queue candidate"))
        if not receipt_path.is_file():
            fail(f"queue candidate receipt missing: {receipt_path}")
    validate_iso(require_text(queue, "generated_at", "queue"), "queue.generated_at")

    receipts = load_json(RECEIPT_INDEX, "receipt index")
    if receipts.get("receipt_index_id") != "redcap-full-llm-wiki-receipts":
        fail("receipt index id mismatch")
    if receipts.get("status") != "active":
        fail("receipt index must be active")
    if not isinstance(receipts.get("receipts"), list):
        fail("receipt index receipts must be list")
    for row in receipts.get("receipts", []):
        if not isinstance(row, dict):
            fail("receipt rows must be objects")
        path = resolve_repo_path(require_text(row, "path", "receipt row"))
        if not path.is_file():
            fail(f"receipt path missing: {path}")
        payload = load_json(path, "candidate receipt")
        if payload.get("status") != row.get("status"):
            fail(f"receipt status mismatch: {path}")
    validate_iso(require_text(receipts, "generated_at", "receipt index"), "receipt_index.generated_at")


def validate_roadmap() -> None:
    roadmap = load_json(ROADMAP, "full LLM-wiki roadmap")
    if roadmap.get("roadmap_id") != "full-llm-wiki-roadmap":
        fail("roadmap id mismatch")
    if roadmap.get("status") != "implemented-controlled-local-product":
        fail("roadmap status must be implemented-controlled-local-product")
    if roadmap.get("current_capability") != "full-llm-wiki-controlled-local":
        fail("roadmap current_capability mismatch")
    phases = {item.get("id"): item.get("status") for item in roadmap.get("phases", []) if isinstance(item, dict)}
    expected = {
        "lite": "implemented",
        "full-wiki-product": "implemented-controlled-local",
        "background-distillation-worker": "implemented-proposal-only",
        "fts-rag-graphrag": "controlled-boundary-disabled-by-default",
    }
    for phase, status in expected.items():
        if phases.get(phase) != status:
            fail(f"roadmap phase {phase} status mismatch: {phases.get(phase)}")


def main() -> int:
    policy = load_json(POLICY, "full LLM-wiki policy")
    denied_paths = validate_policy(policy)
    validate_schema_identity(load_json(ENTRY_SCHEMA, "entry schema"), "full-llm-wiki-entry", "entry schema")
    validate_schema_identity(load_json(CANDIDATE_SCHEMA, "candidate schema"), "full-llm-wiki-candidate", "candidate schema")
    validate_index(load_json(INDEX, "full wiki index"), denied_paths)
    validate_queue_and_receipts()
    validate_roadmap()
    rag = load_json(RAG_POLICY, "RAG/GraphRAG boundary policy")
    if rag.get("status") != "implemented-disabled-by-default":
        fail("RAG boundary status mismatch")
    print("FULL_LLM_WIKI_OK")
    print("status=implemented-controlled-local-product entries=1 worker=proposal-only rag=disabled-by-default")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

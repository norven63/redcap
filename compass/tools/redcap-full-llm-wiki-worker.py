#!/usr/bin/env python3
# 用途：长期记忆路线图脚本；生成 full LLM-wiki 候选条目和候选 receipt，默认只提案不晋升。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "assets/references/full-llm-wiki-policy.json"
QUEUE_DIR = ROOT / "assets/knowledge/llm-wiki-full/queue"
RECEIPT_DIR = ROOT / "assets/knowledge/llm-wiki-full/receipts"
ENTRY_DIR = ROOT / "assets/knowledge/llm-wiki-full/entries"
QUEUE_INDEX = QUEUE_DIR / "index.json"
RECEIPT_INDEX = RECEIPT_DIR / "index.json"

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
SLUG_RE = re.compile(r"[^a-z0-9]+")


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-full-llm-wiki-worker] {message}")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        fail(f"path escapes repo: {path}")


def resolve_repo_path(raw: str) -> Path:
    if not raw or raw.startswith("~"):
        fail(f"invalid source path: {raw}")
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        fail(f"source path must be repo-relative: {raw}")
    return ROOT / path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def slugify(raw: str) -> str:
    text = SLUG_RE.sub("-", raw.lower()).strip("-")
    text = re.sub(r"-+", "-", text)
    if len(text) < 3:
        text = "wiki-candidate-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
    return text[:80]


def scan_text(text: str) -> dict[str, Any]:
    matches = [pattern for pattern in SECRET_PATTERNS if pattern in text]
    matches.extend(pattern.pattern for pattern in SECRET_REGEXES if pattern.search(text))
    return {
        "status": "pass" if not matches else "fail",
        "patterns_checked": SECRET_PATTERNS,
        "matches": matches,
    }


def denied_paths(policy: dict[str, Any]) -> list[str]:
    boundaries = policy.get("source_boundaries")
    if not isinstance(boundaries, dict):
        fail("policy.source_boundaries missing")
    raw = boundaries.get("denied_source_paths")
    if not isinstance(raw, list):
        fail("policy.source_boundaries.denied_source_paths must be list")
    return [str(item) for item in raw]


def matches_any(path: str, patterns: list[str]) -> bool:
    import fnmatch

    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def existing_dedupe_keys() -> set[str]:
    keys: set[str] = set()
    for path in sorted(QUEUE_DIR.glob("*.json")):
        if path.name == "index.json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("dedupe_key"), str):
            keys.add(payload["dedupe_key"])
    for path in sorted(ENTRY_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        anchors = payload.get("source_anchors") if isinstance(payload, dict) else None
        if isinstance(anchors, list):
            for anchor in anchors:
                if isinstance(anchor, dict) and isinstance(anchor.get("commit_sha_or_digest"), str):
                    keys.add(anchor["commit_sha_or_digest"])
    return keys


def build_candidate(args: argparse.Namespace, policy: dict[str, Any]) -> dict[str, Any]:
    source = resolve_repo_path(args.source)
    if not source.is_file():
        fail(f"source file missing: {args.source}")
    rel_source = repo_rel(source)
    if matches_any(rel_source, denied_paths(policy)):
        fail(f"source path denied by policy: {rel_source}")
    source_text = source.read_text(encoding="utf-8", errors="replace")
    proposed_text = "\n".join([args.title, args.summary, args.body])
    privacy_scan = scan_text(source_text + "\n" + proposed_text)
    if privacy_scan["status"] != "pass":
        fail("privacy scan failed: " + ",".join(privacy_scan["matches"]))

    source_digest = sha256_file(source)
    dedupe_key = source_digest + ":" + slugify(args.title)
    if dedupe_key in existing_dedupe_keys():
        fail("duplicate candidate/source detected")

    candidate_id = slugify(args.candidate_id or args.title)
    created_at = now_iso()
    return {
        "version": 1,
        "candidate_id": candidate_id,
        "status": "candidate",
        "candidate_type": args.candidate_type,
        "source_anchors": [
            {
                "source_path": rel_source,
                "source_kind": args.source_kind,
                "commit_sha_or_digest": source_digest,
                "last_reviewed_at": created_at,
                "privacy_classification": args.privacy_classification,
            }
        ],
        "dedupe_key": dedupe_key,
        "privacy_scan": privacy_scan,
        "proposed_entry": {
            "version": 1,
            "id": candidate_id,
            "title": args.title,
            "status": "active",
            "visibility": "private",
            "authority": "non-authoritative-derived-context",
            "candidate_type": args.candidate_type,
            "privacy_classification": args.privacy_classification,
            "source_anchors": [
                {
                    "source_path": rel_source,
                    "source_kind": args.source_kind,
                    "commit_sha_or_digest": source_digest,
                    "last_reviewed_at": created_at,
                    "privacy_classification": args.privacy_classification,
                }
            ],
            "summary": args.summary,
            "body": args.body,
            "review_state": {
                "state": "candidate",
                "reviewed_by": "redcap-full-llm-wiki-worker",
                "reviewed_at": created_at,
                "receipt": f"assets/knowledge/llm-wiki-full/receipts/{candidate_id}.json",
            },
            "staleness": {
                "mode": "source-digest",
                "last_checked_at": created_at,
                "source_digest_match": True,
            },
            "forge_promotion": {
                "status": "requires-forge-review",
                "requires_forge": True,
                "public_write_allowed": False,
            },
        },
    }


def check_worker() -> int:
    policy = load_json(POLICY_PATH, "full LLM-wiki policy")
    worker = policy.get("worker_contract")
    if not isinstance(worker, dict):
        fail("worker_contract missing")
    if worker.get("entrypoint") != "compass/tools/redcap-full-llm-wiki-worker.sh":
        fail("worker entrypoint mismatch")
    if worker.get("automatic_source_mutation_allowed") is not False:
        fail("worker may not mutate source truth")
    for path in [QUEUE_INDEX, RECEIPT_INDEX]:
        if not path.is_file():
            fail(f"missing worker surface: {path}")
    print("FULL_LLM_WIKI_WORKER_OK")
    print("mode=proposal-only")
    return 0


def write_candidate(candidate: dict[str, Any]) -> None:
    candidate_id = str(candidate["candidate_id"])
    candidate_path = QUEUE_DIR / f"{candidate_id}.json"
    receipt_path = RECEIPT_DIR / f"{candidate_id}.json"
    if candidate_path.exists() or receipt_path.exists():
        fail(f"candidate already exists: {candidate_id}")
    receipt = {
        "version": 1,
        "receipt_id": candidate_id,
        "status": "candidate-generated",
        "created_at": now_iso(),
        "candidate_path": repo_rel(candidate_path),
        "source_anchors": candidate["source_anchors"],
        "privacy_scan": candidate["privacy_scan"],
        "promotion_boundary": "candidate only; requires review before entry promotion and RedCap Forge before public arsenal promotion",
    }
    write_json(candidate_path, candidate)
    write_json(receipt_path, receipt)
    queue_index = load_json(QUEUE_INDEX, "queue index")
    queue_rows = queue_index.setdefault("candidates", [])
    if not isinstance(queue_rows, list):
        fail("queue index candidates must be list")
    queue_rows.append(
        {
            "candidate_id": candidate_id,
            "path": repo_rel(candidate_path),
            "status": "candidate",
            "candidate_type": candidate.get("candidate_type"),
            "receipt": repo_rel(receipt_path),
        }
    )
    queue_index["generated_at"] = now_iso()
    write_json(QUEUE_INDEX, queue_index)

    receipt_index = load_json(RECEIPT_INDEX, "receipt index")
    receipt_rows = receipt_index.setdefault("receipts", [])
    if not isinstance(receipt_rows, list):
        fail("receipt index receipts must be list")
    receipt_rows.append(
        {
            "receipt_id": candidate_id,
            "path": repo_rel(receipt_path),
            "status": "candidate-generated",
            "candidate_path": repo_rel(candidate_path),
        }
    )
    receipt_index["generated_at"] = now_iso()
    write_json(RECEIPT_INDEX, receipt_index)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate full LLM-wiki proposal-only candidates.")
    parser.add_argument("--check", action="store_true", help="validate worker surfaces without generating a candidate")
    parser.add_argument("--write", action="store_true", help="write candidate and receipt; default is dry-run JSON output")
    parser.add_argument("--source", default="assets/references/llm-wiki-asset-stratification-policy.json")
    parser.add_argument("--source-kind", default="policy")
    parser.add_argument("--candidate-id", default="")
    parser.add_argument("--candidate-type", default="decision-framework")
    parser.add_argument("--privacy-classification", default="internal")
    parser.add_argument("--title", default="Full LLM-wiki 候选生成链路")
    parser.add_argument("--summary", default="Full LLM-wiki worker 会生成带 source anchor、隐私扫描和去重键的候选，而不是直接改写权威源。")
    parser.add_argument("--body", default="该候选说明 worker 的正确边界：只写入 queue 和 receipt，等待 review 后才可能晋升为 entry；公开 arsenal 晋升还必须通过 RedCap Forge。")
    args = parser.parse_args()

    if args.check:
        return check_worker()

    policy = load_json(POLICY_PATH, "full LLM-wiki policy")
    candidate = build_candidate(args, policy)
    if args.write:
        write_candidate(candidate)
        print("FULL_LLM_WIKI_CANDIDATE_WRITTEN")
        print(f"candidate_id={candidate['candidate_id']}")
    else:
        print(json.dumps(candidate, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Minimal index-first RedCap knowledge gateway."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unicodedata
from typing import Any

import knowledge_quality as kq


REPO_ROOT = pathlib.Path(os.environ.get("REDCAP_KNOWLEDGE_ROOT", pathlib.Path(__file__).resolve().parents[2])).resolve()
DEFAULT_INDEX = REPO_ROOT / "assets" / "knowledge" / "index.json"
DEFAULT_QUALITY = REPO_ROOT / "assets" / "knowledge" / "quality.json"
DEFAULT_IMPACT_CONTRACT = REPO_ROOT / "assets" / "contracts" / "knowledge-impact-trace.json"
DEFAULT_IMPACT_EVIDENCE = REPO_ROOT / ".redcap" / "evidence" / "rsp" / "rsp-08-knowledge-impact-trace.json"
DEFAULT_IMPACT_ARTIFACTS = REPO_ROOT / ".redcap" / "evidence" / "rsp" / "rsp-08-knowledge-impact-artifacts"
CURRENT_RSP_07_08_TASK_ID = "20260621-rsp-07-08-self-purification-knowledge"
DEFAULT_RSP_07_08_START_MARKER = (
    REPO_ROOT / "assets" / "evidence" / "prism" / CURRENT_RSP_07_08_TASK_ID / "request.json"
)
DEFAULT_LIFECYCLE_REGRESSION_SAMPLES = [
    REPO_ROOT / "assets" / "evidence" / "lifecycle" / "20260621-rsp-10-long-task-loop-boundary.json",
    REPO_ROOT / "assets" / "evidence" / "lifecycle" / "20260621-rsp-19-cli-surface-compat.json",
]
DEFAULT_DRAFTS = REPO_ROOT / "assets" / "evidence" / "knowledge" / "drafts"
DEFAULT_REVIEWS = REPO_ROOT / "assets" / "evidence" / "knowledge" / "reviews"
DEFAULT_ENTRIES = REPO_ROOT / "assets" / "knowledge" / "entries"
ENTRY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")
ALLOWED_ROUTES = {
    "active-local-index",
    "revival-doc",
    "controlled-archaeology",
    "old-redcap-reference",
}
RAW_EVIDENCE_BOUNDARY_ID = "raw-evidence-access-boundary"
RAW_EVIDENCE_REQUIRED_TAGS = {
    "raw",
    "evidence",
    "archive",
    "package",
    "cleanup",
    "lifecycle",
    "release",
}
RAW_EVIDENCE_REQUIRED_TERMS = {
    "default context",
    "package candidate",
    "physical cleanup",
    "cleanup apply",
    "minimum run count",
    "release blocker",
}
ASCII_TOKEN_RE = re.compile(r"[a-z0-9]+")
CJK_SEQUENCE_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")
SEARCH_MINIMUM_SCORE = 6
SEARCH_MINIMUM_COVERAGE = 0.18
SEARCH_STOP_TOKENS = {"id"}
SEARCH_ALIAS_GROUPS = [
    {"loom", "角色化", "角色工作流", "角色化工作流"},
    {"session", "sessions", "sessionid", "session_id", "会话"},
    {"continuity", "continuous", "resume", "续接", "连续", "连续性"},
    {"self", "purification", "selfpurification", "自我净化"},
    {"e2e", "端到端", "端到端验收"},
    {"layered", "acceptance", "preflight", "分层", "分层验收", "验收"},
    {"candidate", "harvest", "promotion", "promote", "候选", "晋升", "沉淀"},
    {"raw", "evidence", "archive", "package", "cleanup", "release", "原始", "证据", "归档", "清理", "发布"},
]
ROUTE_SEARCH_PRIORITY = {
    "active-local-index": 0,
    "revival-doc": 1,
    "controlled-archaeology": 2,
    "old-redcap-reference": 3,
}
SEARCH_ALIAS_MAP: dict[str, set[str]] = {}
for group in SEARCH_ALIAS_GROUPS:
    expanded: set[str] = set()
    for value in group:
        expanded.update([])  # keep mypy/simple linters happy for the in-place build below
        expanded.update(re.findall(r"[a-z0-9]+|[\u3400-\u4dbf\u4e00-\u9fff]+", unicodedata.normalize("NFKC", value).casefold()))
        expanded.add(unicodedata.normalize("NFKC", value).casefold().replace("_", ""))
    expanded = {item for item in expanded if item}
    for token in expanded:
        SEARCH_ALIAS_MAP[token] = expanded


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def resolve_path(path: str | pathlib.Path) -> pathlib.Path:
    candidate = pathlib.Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def rel_path(path: pathlib.Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def utc_from_timestamp(value: float) -> dt.datetime:
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).replace(microsecond=0)


def file_time_summary(path: pathlib.Path) -> dict[str, Any]:
    stat = path.stat()
    created_at = getattr(stat, "st_birthtime", stat.st_ctime)
    return {
        "created_at_utc": utc_from_timestamp(created_at).isoformat(),
        "modified_at_utc": utc_from_timestamp(stat.st_mtime).isoformat(),
        "modified_timestamp": stat.st_mtime,
    }


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"knowledge index missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid knowledge index json: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("knowledge index must be a JSON object")
    return payload


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_text(path: pathlib.Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(body, encoding="utf-8")
    os.replace(tmp, path)


def rel_exists(rel_path: str) -> bool:
    return (REPO_ROOT / rel_path).exists()


def validate_index(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if payload.get("schema_id") != "redcap-knowledge-index":
        failures.append("schema_id must be redcap-knowledge-index")
    if payload.get("default_read") != "index-only":
        failures.append("default_read must be index-only")
    if payload.get("raw_archive_default") != "forbidden":
        failures.append("raw_archive_default must be forbidden")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        failures.append("entries must be a non-empty list")
        return failures
    seen: set[str] = set()
    raw_boundary_entry: dict[str, Any] | None = None
    for index, entry in enumerate(entries, start=1):
        label = f"entries[{index}]"
        if not isinstance(entry, dict):
            failures.append(f"{label} must be an object")
            continue
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id.strip():
            failures.append(f"{label}.id must be non-empty")
        elif entry_id in seen:
            failures.append(f"duplicate entry id: {entry_id}")
        else:
            seen.add(entry_id)
        route = entry.get("route")
        if route not in ALLOWED_ROUTES:
            failures.append(f"{label}.route invalid: {route}")
        path = entry.get("path")
        if route != "old-redcap-reference":
            if not isinstance(path, str) or not rel_exists(path):
                failures.append(f"{label}.path missing: {path}")
        tags = entry.get("tags")
        if not isinstance(tags, list) or not all(isinstance(tag, str) and tag.strip() for tag in tags):
            failures.append(f"{label}.tags must be a non-empty string list")
        summary = entry.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            failures.append(f"{label}.summary must be non-empty")
        first_read = entry.get("first_read")
        if route != "old-redcap-reference" and (not isinstance(first_read, str) or not rel_exists(first_read)):
            failures.append(f"{label}.first_read missing: {first_read}")
        if entry.get("body_read_rule") not in {"index-first", "explicit-only"}:
            failures.append(f"{label}.body_read_rule must be index-first or explicit-only")
        if entry.get("id") == RAW_EVIDENCE_BOUNDARY_ID:
            raw_boundary_entry = entry
    failures.extend(validate_raw_evidence_boundary_entry(raw_boundary_entry))
    return failures


def validate_raw_evidence_boundary_entry(entry: dict[str, Any] | None) -> list[str]:
    if entry is None:
        return [f"raw evidence boundary entry missing: {RAW_EVIDENCE_BOUNDARY_ID}"]
    failures: list[str] = []
    tags = {str(tag).casefold() for tag in entry.get("tags", []) if isinstance(tag, str)}
    missing_tags = sorted(RAW_EVIDENCE_REQUIRED_TAGS - tags)
    if missing_tags:
        failures.append(f"{RAW_EVIDENCE_BOUNDARY_ID}.tags missing: {', '.join(missing_tags)}")
    searchable = " ".join([
        str(entry.get("title", "")),
        str(entry.get("summary", "")),
        " ".join(sorted(tags)),
    ]).casefold()
    for term in ["raw", "evidence"]:
        if term not in searchable:
            failures.append(f"{RAW_EVIDENCE_BOUNDARY_ID} must be searchable by {term}")
    path_value = entry.get("path")
    if not isinstance(path_value, str) or not rel_exists(path_value):
        failures.append(f"{RAW_EVIDENCE_BOUNDARY_ID}.path missing: {path_value}")
        return failures
    body = (REPO_ROOT / path_value).read_text(encoding="utf-8", errors="replace").casefold()
    summary = str(entry.get("summary", "")).casefold()
    combined = f"{summary}\n{body}"
    missing_terms = sorted(term for term in RAW_EVIDENCE_REQUIRED_TERMS if term not in combined)
    if missing_terms:
        failures.append(f"{RAW_EVIDENCE_BOUNDARY_ID} missing boundary terms: {', '.join(missing_terms)}")
    return failures


def normalize_search_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[_\-/]+", " ", normalized)
    normalized = re.sub(r"[^\w\u3400-\u4dbf\u4e00-\u9fff]+", " ", normalized, flags=re.UNICODE)
    return re.sub(r"\s+", " ", normalized).strip()


def cjk_windows(sequence: str) -> set[str]:
    if len(sequence) <= 2:
        return {sequence}
    windows = {sequence}
    windows.update(sequence[index : index + 2] for index in range(0, len(sequence) - 1))
    return windows


def search_tokens(value: str) -> set[str]:
    normalized = normalize_search_text(value)
    tokens = set(ASCII_TOKEN_RE.findall(normalized)) - SEARCH_STOP_TOKENS
    for sequence in CJK_SEQUENCE_RE.findall(normalized):
        tokens.update(cjk_windows(sequence))
    expanded = set(tokens)
    for token in list(tokens):
        compact = token.replace("_", "")
        if compact in SEARCH_ALIAS_MAP:
            expanded.update(SEARCH_ALIAS_MAP[compact])
    return {token for token in expanded if token and token not in SEARCH_STOP_TOKENS}


def entry_search_fields(entry: dict[str, Any]) -> dict[str, set[str]]:
    tags = " ".join(str(tag) for tag in entry.get("tags", []) if isinstance(tag, str))
    return {
        "id": search_tokens(str(entry.get("id", ""))),
        "title": search_tokens(str(entry.get("title", ""))),
        "summary": search_tokens(str(entry.get("summary", ""))),
        "tags": search_tokens(tags),
    }


def entry_search_score(entry: dict[str, Any], query_tokens: set[str]) -> tuple[int, float, int]:
    fields = entry_search_fields(entry)
    weighted_score = 0
    matched_tokens: set[str] = set()
    for field, weight in {"id": 3, "title": 3, "tags": 3, "summary": 1}.items():
        field_matches = query_tokens & fields[field]
        if field_matches:
            weighted_score += len(field_matches) * weight
            matched_tokens.update(field_matches)
    coverage = len(matched_tokens) / max(len(query_tokens), 1)
    return weighted_score, coverage, len(matched_tokens)


def search_entries(payload: dict[str, Any], query: str) -> list[dict[str, Any]]:
    query_tokens = search_tokens(query)
    entries = payload.get("entries", [])
    scored_matches: list[tuple[int, float, int, str, dict[str, Any]]] = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        score, coverage, matched_count = entry_search_score(entry, query_tokens)
        if not query_tokens or (
            score >= SEARCH_MINIMUM_SCORE
            and (coverage >= SEARCH_MINIMUM_COVERAGE or matched_count >= 2)
        ):
            route_priority = ROUTE_SEARCH_PRIORITY.get(str(entry.get("route", "")), 9)
            scored_matches.append((score, coverage, route_priority, str(entry.get("id", "")), {
                "id": entry.get("id"),
                "title": entry.get("title"),
                "route": entry.get("route"),
                "summary": entry.get("summary"),
                "first_read": entry.get("first_read"),
                "body_read_rule": entry.get("body_read_rule"),
            }))
    scored_matches.sort(key=lambda item: (item[2], -item[0], -item[1], item[3]))
    return [item[4] for item in scored_matches]


def parse_tags(value: str) -> list[str]:
    tags = [tag.strip() for tag in value.split(",") if tag.strip()]
    if not tags:
        raise SystemExit("--tags must contain at least one tag")
    return tags


def require_entry_id(entry_id: str) -> None:
    if not ENTRY_ID_RE.fullmatch(entry_id):
        raise SystemExit("entry id must be lowercase kebab-case, 3-64 chars")


def index_has_id(payload: dict[str, Any], entry_id: str) -> bool:
    entries = payload.get("entries", [])
    return any(isinstance(entry, dict) and entry.get("id") == entry_id for entry in entries if isinstance(entries, list))


def read_body_arg(args: argparse.Namespace) -> str:
    if args.body_file:
        body = resolve_path(args.body_file).read_text(encoding="utf-8")
    else:
        body = args.body or ""
    if not body.strip():
        raise SystemExit("knowledge draft body must be non-empty")
    return body


def cmd_draft(args: argparse.Namespace) -> int:
    entry_id = args.id
    require_entry_id(entry_id)
    index = load_json(resolve_path(args.index))
    failures = validate_index(index)
    if failures:
        raise SystemExit("; ".join(failures))
    if index_has_id(index, entry_id):
        raise SystemExit(f"knowledge entry already exists: {entry_id}")
    body = read_body_arg(args)
    draft = {
        "schema_id": "redcap-knowledge-draft",
        "id": entry_id,
        "title": args.title,
        "summary": args.summary,
        "tags": parse_tags(args.tags),
        "body": body,
        "source_path": args.source_path,
        "created_at": iso_now(),
        "status": "draft",
    }
    for key in ["title", "summary"]:
        if not isinstance(draft[key], str) or not draft[key].strip():
            raise SystemExit(f"--{key.replace('_', '-')} must be non-empty")
    output = resolve_path(args.output) if args.output else DEFAULT_DRAFTS / f"{entry_id}.json"
    write_json(output, draft)
    print(json.dumps({"ok": True, "draft": rel_path(output), "id": entry_id}, ensure_ascii=False, indent=2))
    print("REDCAP_KNOWLEDGE_DRAFT_OK")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    draft_path = resolve_path(args.draft)
    draft = load_json(draft_path)
    if draft.get("schema_id") != "redcap-knowledge-draft":
        raise SystemExit("review input is not a redcap knowledge draft")
    decision = args.decision
    if decision == "approve" and not args.reason.strip():
        raise SystemExit("--reason is required for approved knowledge")
    review = {
        "schema_id": "redcap-knowledge-review",
        "id": draft.get("id"),
        "decision": decision,
        "reviewer": args.reviewer,
        "reason": args.reason,
        "reviewed_at": iso_now(),
        "draft_path": rel_path(draft_path),
        "draft": draft,
    }
    output = resolve_path(args.output) if args.output else DEFAULT_REVIEWS / f"{draft['id']}.review.json"
    write_json(output, review)
    print(json.dumps({"ok": True, "review": rel_path(output), "id": draft.get("id"), "decision": decision}, ensure_ascii=False, indent=2))
    print("REDCAP_KNOWLEDGE_REVIEW_OK")
    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    index_path = resolve_path(args.index)
    index = load_json(index_path)
    failures = validate_index(index)
    if failures:
        raise SystemExit("; ".join(failures))
    review_path = resolve_path(args.review)
    review = load_json(review_path)
    if review.get("schema_id") != "redcap-knowledge-review":
        raise SystemExit("promote input is not a redcap knowledge review")
    if review.get("decision") != "approve":
        raise SystemExit("only approved knowledge reviews can be promoted")
    draft = review.get("draft")
    if not isinstance(draft, dict) or draft.get("schema_id") != "redcap-knowledge-draft":
        raise SystemExit("knowledge review is missing its draft payload")
    entry_id = str(draft.get("id") or "")
    require_entry_id(entry_id)
    if index_has_id(index, entry_id):
        raise SystemExit(f"knowledge entry already exists: {entry_id}")
    body_path = DEFAULT_ENTRIES / f"{entry_id}.md"
    body = (
        f"# {draft['title']}\n\n"
        f"{draft['body'].rstrip()}\n\n"
        "## Review\n\n"
        f"- reviewer: {review.get('reviewer')}\n"
        f"- reviewed_at: {review.get('reviewed_at')}\n"
        f"- reason: {review.get('reason')}\n"
    )
    write_text(body_path, body)
    entry = {
        "id": entry_id,
        "title": draft["title"],
        "route": "active-local-index",
        "path": rel_path(body_path),
        "first_read": rel_path(body_path),
        "body_read_rule": "index-first",
        "tags": draft["tags"],
        "summary": draft["summary"],
    }
    index["entries"].append(entry)
    write_json(index_path, index)
    sync_quality_for_promoted_entry(entry, review)
    print(json.dumps({"ok": True, "entry": entry, "review": rel_path(review_path)}, ensure_ascii=False, indent=2))
    print("REDCAP_KNOWLEDGE_PROMOTE_OK")
    return 0


def sync_quality_for_promoted_entry(entry: dict[str, Any], review: dict[str, Any]) -> None:
    if not DEFAULT_QUALITY.exists():
        return
    quality = load_json(DEFAULT_QUALITY)
    entries = quality.setdefault("entries", {})
    if not isinstance(entries, dict):
        raise SystemExit("knowledge quality entries must be an object")
    entry_id = str(entry.get("id") or "")
    reviewed_at = str(review.get("reviewed_at") or iso_now())[:10]
    try:
        valid_until = (dt.date.fromisoformat(reviewed_at) + dt.timedelta(days=92)).isoformat()
    except ValueError:
        valid_until = (dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=92)).isoformat()
    entries[entry_id] = {
        "applicability": "新晋升的 RedCap 活跃知识；首次使用前仍需结合当前任务事实验证。",
        "confidence": "medium",
        "expiry_condition": "来源草稿、评审理由、适用边界或关联运行时行为变化时必须重新复核。",
        "index_path": entry.get("path"),
        "index_route": entry.get("route"),
        "reviewed_at": reviewed_at,
        "source_refs": [
            str(entry.get("path")),
            str(review.get("draft_path")),
        ],
        "status": "active",
        "usage_policy": "review_required",
        "valid_until": valid_until,
    }
    write_json(DEFAULT_QUALITY, quality)


def cmd_self_check(args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="redcap-knowledge-self-check-") as root:
        root_path = pathlib.Path(root)
        index_path = root_path / "assets" / "knowledge" / "index.json"
        write_json(index_path, {
            "schema_id": "redcap-knowledge-index",
            "version": 1,
            "default_read": "index-only",
            "raw_archive_default": "forbidden",
            "entries": [
                {
                    "id": "seed",
                    "title": "Seed",
                    "route": "active-local-index",
                    "path": "assets/knowledge/entries/seed.md",
                    "first_read": "assets/knowledge/entries/seed.md",
                    "body_read_rule": "index-first",
                    "tags": ["seed"],
                    "summary": "Seed entry for gateway self-check.",
                },
                {
                    "id": RAW_EVIDENCE_BOUNDARY_ID,
                    "title": "Raw Evidence Access Boundary",
                    "route": "active-local-index",
                    "path": "assets/knowledge/entries/raw-evidence-access-boundary.md",
                    "first_read": "assets/knowledge/entries/raw-evidence-access-boundary.md",
                    "body_read_rule": "index-first",
                    "tags": ["raw", "evidence", "archive", "package", "cleanup", "lifecycle", "release"],
                    "summary": "Raw evidence is explicit-access only: not default context, not a package candidate, not physically cleaned, no cleanup apply, protected by minimum run count and release blocker rules.",
                }
            ],
        })
        write_text(root_path / "assets" / "knowledge" / "entries" / "seed.md", "# Seed\n")
        write_text(
            root_path / "assets" / "knowledge" / "entries" / "raw-evidence-access-boundary.md",
            "\n".join([
                "# Raw Evidence Access Boundary",
                "",
                "- raw evidence is never default context",
                "- prism/runs is not a package candidate",
                "- physical cleanup requires explicit approval",
                "- cleanup apply stays disabled by default",
                "- minimum run count integrity is preserved",
                "- release blocker linkage remains until evidence retention is resolved",
            ]),
        )
        env = os.environ.copy()
        env["REDCAP_KNOWLEDGE_ROOT"] = str(root_path)
        script = pathlib.Path(__file__).resolve()
        commands = [
            [sys.executable, str(script), "draft", "--id", "fixture-entry", "--title", "Fixture Entry", "--summary", "Fixture knowledge entry.", "--tags", "fixture,self-check", "--body", "A reviewed knowledge fixture."],
            [sys.executable, str(script), "review", "--draft", "assets/evidence/knowledge/drafts/fixture-entry.json", "--decision", "approve", "--reviewer", "self-check", "--reason", "fixture approved"],
            [sys.executable, str(script), "promote", "--review", "assets/evidence/knowledge/reviews/fixture-entry.review.json"],
            [sys.executable, str(script), "check"],
            [sys.executable, str(script), "search", "fixture", "--require-match"],
            [sys.executable, str(script), "search", "seed fixture unrelated", "--require-match"],
        ]
        failures: list[str] = []
        for command in commands:
            completed = __import__("subprocess").run(command, cwd=str(root_path), env=env, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                failures.append(f"{' '.join(command[2:])}: exit {completed.returncode}: {completed.stderr or completed.stdout}")
        positive_index = {
            "schema_id": "redcap-knowledge-index",
            "version": 1,
            "default_read": "index-only",
            "raw_archive_default": "forbidden",
            "entries": [
                {
                    "id": "self-purification-runtime-loop",
                    "title": "自我净化运行闭环",
                    "route": "active-local-index",
                    "path": "assets/knowledge/entries/seed.md",
                    "first_read": "assets/knowledge/entries/seed.md",
                    "body_read_rule": "index-first",
                    "tags": ["self-purification", "runtime", "knowledge", "anti-loop"],
                    "summary": "自我净化必须把任务前检索、任务后候选、评审决策和后续召回串成闭环，不能停留在合同检查。",
                },
                {
                    "id": "loom-runtime-session-continuity",
                    "title": "Loom 角色会话连续性",
                    "route": "active-local-index",
                    "path": "assets/knowledge/entries/seed.md",
                    "first_read": "assets/knowledge/entries/seed.md",
                    "body_read_rule": "index-first",
                    "tags": ["loom", "runtime", "session", "codex-cli"],
                    "summary": "Loom 必须在普通项目中记录角色会话、续接关系、丢失报警和上下游交付证据，不能由共享上下文冒充多角色。",
                },
                {
                    "id": RAW_EVIDENCE_BOUNDARY_ID,
                    "title": "Raw Evidence Access Boundary",
                    "route": "active-local-index",
                    "path": "assets/knowledge/entries/raw-evidence-access-boundary.md",
                    "first_read": "assets/knowledge/entries/raw-evidence-access-boundary.md",
                    "body_read_rule": "index-first",
                    "tags": ["raw", "evidence", "archive", "package", "cleanup", "lifecycle", "release"],
                    "summary": "Raw evidence is explicit-access only: not default context, not a package candidate, not physically cleaned, no cleanup apply, protected by minimum run count and release blocker rules.",
                },
            ],
        }
        expected_cases = [
            ("loom session continuity self-purification E2E layered acceptance", {"loom-runtime-session-continuity", "self-purification-runtime-loop"}),
            ("Loom 角色 会话 连续 自我净化 E2E 分层验收", {"loom-runtime-session-continuity", "self-purification-runtime-loop"}),
            ("任务后候选 晋升 no promote 自我净化", {"self-purification-runtime-loop"}),
            ("角色化工作流 session_id 丢失报警", {"loom-runtime-session-continuity"}),
            ("raw evidence package cleanup release blocker", {RAW_EVIDENCE_BOUNDARY_ID}),
        ]
        for query, expected_ids in expected_cases:
            found = {str(item.get("id")) for item in search_entries(positive_index, query)}
            if not found & expected_ids:
                failures.append(f"search fixture failed for {query!r}: found {sorted(found)}, expected one of {sorted(expected_ids)}")
        for query in ["banana invoice mineral unrelated", "天气 菜谱 星座 完全无关"]:
            found = search_entries(positive_index, query)
            if found:
                failures.append(f"negative search fixture should not match {query!r}: {found}")
        result = {"ok": not failures, "failures": failures}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if failures:
            return 1
        print("REDCAP_KNOWLEDGE_WRITE_REVIEW_OK")
        return 0


def cmd_check(args: argparse.Namespace) -> int:
    payload = load_json(pathlib.Path(args.index).resolve())
    failures = validate_index(payload)
    result = {
        "ok": not failures,
        "entries": len(payload.get("entries", [])) if isinstance(payload.get("entries"), list) else 0,
        "default_read": payload.get("default_read"),
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_KNOWLEDGE_GATEWAY_OK")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    payload = load_json(pathlib.Path(args.index).resolve())
    failures = validate_index(payload)
    if failures:
        raise SystemExit("; ".join(failures))
    matches = search_entries(payload, args.query)
    quality = load_json(pathlib.Path(args.quality).resolve()) if pathlib.Path(args.quality).exists() else None
    enriched_matches: list[dict[str, Any]] = []
    for match in matches:
        enriched = dict(match)
        enriched["quality"] = kq.quality_decision_for_entry(enriched, quality)
        enriched_matches.append(enriched)
    if args.direct_driver_only:
        enriched_matches = [
            match for match in enriched_matches
            if isinstance(match.get("quality"), dict) and match["quality"].get("direct_driver_allowed") is True
        ]
    ok = bool(enriched_matches) or not args.require_match
    if args.direct_driver_only and not enriched_matches:
        ok = False
    result = {
        "query": args.query,
        "matches": enriched_matches,
        "ok": ok,
        "read_policy": "index-first; read first_read before body; raw archives require explicit task need",
        "quality_policy": "quality metadata is loaded when present; missing quality defaults to review_required; direct-driver filtering uses quality.direct_driver_allowed",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not ok:
        print("REDCAP_KNOWLEDGE_GATEWAY_NO_MATCH")
        return 1
    return 0


def impact_trace_for_query(*, query: str, index_path: pathlib.Path, quality_path: pathlib.Path) -> dict[str, Any]:
    payload = load_json(index_path)
    failures = validate_index(payload)
    if failures:
        raise SystemExit("; ".join(failures))
    quality = load_json(quality_path) if quality_path.exists() else None
    matches: list[dict[str, Any]] = []
    for match in search_entries(payload, query):
        enriched = dict(match)
        enriched["quality"] = kq.quality_decision_for_entry(enriched, quality)
        matches.append(enriched)
    direct_matches = [
        match for match in matches
        if isinstance(match.get("quality"), dict) and match["quality"].get("direct_driver_allowed") is True
    ]
    adopted = direct_matches[:1]
    adopted_ids = [str(item.get("id")) for item in adopted]
    if adopted:
        adopted_id = adopted_ids[0]
        without_knowledge_path = {
            "mode": "without_adopted_knowledge",
            "planning_decision": "run generic implementation checks only",
            "implementation_decision": "do not add knowledge impact trace",
            "verification_decision": "accept command-level checks without knowledge impact evidence",
        }
        with_knowledge_path = {
            "mode": "with_adopted_knowledge",
            "planning_decision": "require pre-task knowledge retrieval and visible adopted entry",
            "implementation_decision": "add knowledge impact trace and self-purification loop checks",
            "verification_decision": "require RSP-08 evidence and negative probes before claim",
        }
        decision_impacts = {
            "planning": f"采用知识条目 {adopted_id} 作为计划约束：任务前必须先检索并记录命中知识。",
            "implementation": f"采用知识条目 {adopted_id} 作为实现约束：实现必须产生可运行入口和结构化证据，而不是只写文档。",
            "verification": f"采用知识条目 {adopted_id} 作为验收约束：验收必须证明知识命中如何影响计划、实现或检查结果。",
        }
        counterfactual_analysis = {
            "mode": "counterfactual_analysis",
            "independent_runtime_executions": False,
            "execution_boundary": "同一任务的双路径决策分析，不伪装成两个真实独立运行的任务。",
            "reason": "RedCap 正常任务流只有一条真实执行路径；这里用于证明知识命中改变决策边界，而不是声称执行了两次项目交付。",
            "without_adopted_knowledge": "只能执行通用实现检查，无法要求自我净化候选和知识影响证据进入验收。",
            "with_adopted_knowledge": "必须执行自我净化候选、no-promote 决策、知识影响字段和负向探针验收。",
            "analysis_paths": [
                without_knowledge_path,
                with_knowledge_path,
            ],
            "changed_decisions": [
                f"planning_decision: {without_knowledge_path['planning_decision']} -> {with_knowledge_path['planning_decision']}",
                f"implementation_decision: {without_knowledge_path['implementation_decision']} -> {with_knowledge_path['implementation_decision']}",
                f"verification_decision: {without_knowledge_path['verification_decision']} -> {with_knowledge_path['verification_decision']}",
            ],
        }
    else:
        decision_impacts = {}
        counterfactual_analysis = {
            "mode": "counterfactual_analysis",
            "independent_runtime_executions": False,
            "without_adopted_knowledge": "没有可采用知识。",
            "with_adopted_knowledge": "没有可采用知识。",
            "analysis_paths": [],
            "changed_decisions": [],
        }
    return {
        "schema_id": "redcap-knowledge-impact-trace",
        "query": query,
        "matches": matches,
        "adopted_entries": adopted_ids,
        "result_handling": "use_relevant_entry" if adopted else "record_no_relevant_entry",
        "decision_impacts": decision_impacts,
        "counterfactual_analysis": counterfactual_analysis,
        "no_relevant_entry_reason": None if adopted else "没有可作为 direct_driver 的知识命中；不能声称知识已影响决策。",
        "quality_policy": "direct-driver impact requires quality.direct_driver_allowed=true",
    }


def scan_lifecycle_knowledge_usage(
    lifecycle_root: pathlib.Path,
    *,
    minimum_count: int,
    task_start_marker: pathlib.Path,
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    skipped_newer_samples: list[dict[str, Any]] = []
    failures = []
    if not task_start_marker.exists():
        failures.append(f"task start marker is missing: {rel_path(task_start_marker)}")
        task_start_timestamp = None
        task_start_summary = None
    else:
        task_start_summary = file_time_summary(task_start_marker)
        task_start_timestamp = task_start_summary["modified_timestamp"]
    for path in sorted(lifecycle_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            payload = load_json(path)
        except SystemExit:
            continue
        binding = payload.get("self_purification")
        if payload.get("task_id") == CURRENT_RSP_07_08_TASK_ID:
            continue
        if not isinstance(binding, dict):
            continue
        evidence_path = binding.get("knowledge_retrieval_evidence")
        if not isinstance(evidence_path, str) or not evidence_path.strip():
            continue
        try:
            evidence_file = resolve_path(evidence_path)
            evidence = load_json(evidence_file)
        except SystemExit:
            continue
        effects = evidence.get("task_decision_effects")
        used = evidence.get("used_knowledge")
        impacts = evidence.get("decision_impacts")
        has_effect = (
            isinstance(effects, list) and bool(effects)
            or isinstance(used, list) and bool(used)
            or isinstance(impacts, dict) and bool(impacts)
        )
        if has_effect:
            lifecycle_times = file_time_summary(path)
            evidence_times = file_time_summary(evidence_file)
            lifecycle_before_task = (
                task_start_timestamp is not None
                and lifecycle_times["modified_timestamp"] < task_start_timestamp
            )
            evidence_before_task = (
                task_start_timestamp is not None
                and evidence_times["modified_timestamp"] < task_start_timestamp
            )
            if not lifecycle_before_task or not evidence_before_task:
                skipped_newer_samples.append({
                    "lifecycle": rel_path(path),
                    "task_id": payload.get("task_id"),
                    "modified_at_utc": lifecycle_times["modified_at_utc"],
                    "knowledge_retrieval_evidence": evidence_path,
                    "knowledge_evidence_modified_at_utc": evidence_times["modified_at_utc"],
                    "reason": "晚于当前 RSP-07/08 任务起点；不作为历史独立性样本。",
                })
                continue
            samples.append({
                "lifecycle": rel_path(path),
                "task_id": payload.get("task_id"),
                "created_at_utc": lifecycle_times["created_at_utc"],
                "modified_at_utc": lifecycle_times["modified_at_utc"],
                "knowledge_retrieval_evidence": evidence_path,
                "knowledge_evidence_created_at_utc": evidence_times["created_at_utc"],
                "knowledge_evidence_modified_at_utc": evidence_times["modified_at_utc"],
                "lifecycle_before_current_task": lifecycle_before_task,
                "knowledge_evidence_before_current_task": evidence_before_task,
            })
        if len(samples) >= minimum_count:
            break
    if len(samples) < minimum_count:
        failures.append(f"knowledge impact lifecycle usage requires at least {minimum_count} samples")
    return {
        "ok": not failures,
        "minimum_count": minimum_count,
        "excludes_current_task_id": CURRENT_RSP_07_08_TASK_ID,
        "task_start_marker": rel_path(task_start_marker) if task_start_marker.exists() else str(task_start_marker),
        "task_started_at_utc": task_start_summary["modified_at_utc"] if task_start_summary else None,
        "sample_count": len(samples),
        "samples": samples,
        "skipped_newer_samples": skipped_newer_samples,
        "failures": failures,
    }


def validate_impact_trace(trace: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    adopted = trace.get("adopted_entries")
    if not isinstance(adopted, list) or not adopted:
        failures.append("knowledge impact requires at least one adopted entry")
    matches = trace.get("matches")
    if not isinstance(matches, list) or not matches:
        failures.append("knowledge impact requires at least one match")
    else:
        adopted_set = {str(item) for item in adopted if isinstance(item, str)} if isinstance(adopted, list) else set()
        direct_ids = {
            str(match.get("id"))
            for match in matches
            if isinstance(match, dict)
            and isinstance(match.get("quality"), dict)
            and match["quality"].get("direct_driver_allowed") is True
        }
        if not (adopted_set & direct_ids):
            failures.append("adopted entries must be allowed direct drivers by quality metadata")
    impacts = trace.get("decision_impacts")
    if not isinstance(impacts, dict):
        failures.append("knowledge impact requires decision_impacts object")
        impacts = {}
    for key in ["planning", "implementation", "verification"]:
        value = impacts.get(key)
        if not isinstance(value, str) or len(value.strip()) < 20:
            failures.append(f"knowledge impact missing substantive {key} effect")
    counterfactual = trace.get("counterfactual_analysis")
    if not isinstance(counterfactual, dict):
        failures.append("knowledge impact requires counterfactual_analysis object")
    else:
        if counterfactual.get("mode") != "counterfactual_analysis":
            failures.append("knowledge impact counterfactual must be explicitly marked as analysis")
        if counterfactual.get("independent_runtime_executions") is not False:
            failures.append("knowledge impact counterfactual must not claim independent runtime executions")
        changed = counterfactual.get("changed_decisions")
        if not isinstance(changed, list) or not changed:
            failures.append("knowledge impact counterfactual requires changed_decisions")
        paths = counterfactual.get("analysis_paths")
        if not isinstance(paths, list) or len(paths) < 2:
            failures.append("knowledge impact counterfactual requires two analysis paths")
    return failures


def run_impact_negative_probes(trace: dict[str, Any], *, index_path: pathlib.Path, quality_path: pathlib.Path) -> list[dict[str, Any]]:
    probes: list[dict[str, Any]] = []
    no_effect = json.loads(json.dumps(trace, ensure_ascii=False))
    no_effect["decision_impacts"] = {}
    failures = validate_impact_trace(no_effect)
    probes.append({
        "name": "missing_decision_impacts",
        "expected_failure": True,
        "failed_as_expected": bool(failures),
        "failures": failures,
    })

    no_adopted = json.loads(json.dumps(trace, ensure_ascii=False))
    no_adopted["adopted_entries"] = []
    failures = validate_impact_trace(no_adopted)
    probes.append({
        "name": "missing_adopted_entries",
        "expected_failure": True,
        "failed_as_expected": bool(failures),
        "failures": failures,
    })

    unrelated = impact_trace_for_query(
        query="banana invoice mineral horoscope unrelated",
        index_path=index_path,
        quality_path=quality_path,
    )
    failures = validate_impact_trace(unrelated)
    probes.append({
        "name": "irrelevant_query_without_reasoned_impact",
        "expected_failure": True,
        "failed_as_expected": bool(failures),
        "failures": failures,
    })
    no_counterfactual = json.loads(json.dumps(trace, ensure_ascii=False))
    no_counterfactual["counterfactual_analysis"] = {"changed_decisions": []}
    failures = validate_impact_trace(no_counterfactual)
    probes.append({
        "name": "missing_counterfactual_difference",
        "expected_failure": True,
        "failed_as_expected": bool(failures),
        "failures": failures,
    })
    return probes


def write_lifecycle_prompt_events(events_path: pathlib.Path, packet: dict[str, Any]) -> None:
    prompt_context = packet.get("prompt_context") if isinstance(packet.get("prompt_context"), dict) else {}
    excerpt = str(prompt_context.get("source_prompt_excerpt") or "").strip()
    prompt_kind = str(prompt_context.get("prompt_kind") or "directive").strip()
    authorized_scope = str(prompt_context.get("authorized_scope") or "implementation").strip()
    if not excerpt:
        raise ValueError("lifecycle regression sample missing prompt_context.source_prompt_excerpt")
    event = {
        "event": "UserPromptSubmit",
        "recorded_at": "fixture",
        "schema_id": "redcap-lifecycle-regression-prompt-event",
        "session_id": "knowledge-gateway-impact-regression",
        "turn_id": f"fixture-{packet.get('task_id') or events_path.stem}",
        "source": "knowledge-gateway-impact-check",
        "prompt": {
            "present": True,
            "normalized_excerpt": excerpt,
            "normalized_excerpt_truncated": False,
            "length": len(excerpt),
        },
        "prompt_intent": {
            "prompt_kind": prompt_kind if prompt_kind in {"question", "directive", "mixed"} else "directive",
            "authorized_scope": (
                authorized_scope
                if authorized_scope in {"answer_only", "review_only", "implementation", "completion"}
                else "implementation"
            ),
            "action_evidence": "substantive",
            "reason": "historical lifecycle regression fixture bound to the sample prompt, not the current live host prompt",
        },
    }
    events_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = events_path.with_name(f".{events_path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, events_path)


def run_lifecycle_regression_probes(artifact_root: pathlib.Path) -> dict[str, Any]:
    probes: list[dict[str, Any]] = []
    for sample in DEFAULT_LIFECYCLE_REGRESSION_SAMPLES:
        sample_packet = load_json(sample)
        sample_events_path = artifact_root / f"{sample.stem}-events.jsonl"
        write_lifecycle_prompt_events(sample_events_path, sample_packet)
        completed = subprocess.run(
            [
                "runtime/bin/redcap",
                "lifecycle",
                "check",
                "--packet",
                str(sample.relative_to(REPO_ROOT)),
                "--events",
                rel_path(sample_events_path),
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        probes.append({
            "name": f"positive_{sample.stem}",
            "packet": str(sample.relative_to(REPO_ROOT)),
            "events": rel_path(sample_events_path),
            "expected_exit_code": 0,
            "exit_code": completed.returncode,
            "ok": completed.returncode == 0,
            "stdout_tail": completed.stdout[-1000:],
            "stderr_tail": completed.stderr[-1000:],
        })

    base_packet = load_json(DEFAULT_LIFECYCLE_REGRESSION_SAMPLES[-1])
    bad_knowledge = {
        "schema_id": "redcap-self-purification-knowledge-retrieval",
        "result_handling": "use_relevant_entry",
        "adopted_entries": ["self-purification-runtime-loop"],
        "matches": [{"id": "self-purification-runtime-loop"}],
        "task_decision_effects": []
    }
    bad_knowledge_path = artifact_root / "negative-lifecycle-bad-knowledge.json"
    bad_packet_path = artifact_root / "negative-lifecycle-missing-knowledge-impact.json"
    write_json(bad_knowledge_path, bad_knowledge)
    base_packet["self_purification"]["knowledge_retrieval_evidence"] = rel_path(bad_knowledge_path)
    write_json(bad_packet_path, base_packet)
    negative_events_path = artifact_root / "negative-lifecycle-events.jsonl"
    write_lifecycle_prompt_events(negative_events_path, base_packet)
    completed = subprocess.run(
        [
            "runtime/bin/redcap",
            "lifecycle",
            "check",
            "--packet",
            rel_path(bad_packet_path),
            "--events",
            rel_path(negative_events_path),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    probes.append({
        "name": "negative_lifecycle_missing_knowledge_impact",
        "packet": rel_path(bad_packet_path),
        "events": rel_path(negative_events_path),
        "expected_exit_code": 1,
        "exit_code": completed.returncode,
        "ok": completed.returncode != 0 and "decision effects" in completed.stdout,
        "stdout_tail": completed.stdout[-1000:],
        "stderr_tail": completed.stderr[-1000:],
    })

    ordinary_packet = json.loads(json.dumps(base_packet, ensure_ascii=False))
    ordinary_packet["task_id"] = "ordinary-knowledge-impact-hard-fail-probe"
    if isinstance(ordinary_packet.get("requirement_review"), dict):
        ordinary_packet["requirement_review"]["user_intent"] = "普通 RedCap 任务也必须在采用知识时记录决策影响。"
        ordinary_packet["requirement_review"]["target_reality"] = "生命周期检查必须阻止缺少知识影响证据的普通任务收口。"
        ordinary_packet["requirement_review"]["non_goals"] = ["不复用 RSP-07/08 专项任务作为证明。"]
    if isinstance(ordinary_packet.get("task_body"), dict):
        ordinary_packet["task_body"]["requested_outcome"] = "普通任务知识影响硬失败探针。"
        ordinary_packet["task_body"]["primary_deliverable"] = "生命周期检查失败输出。"
        ordinary_packet["task_body"]["acceptance_criteria"] = [
            "采用知识但没有决策影响记录时必须失败。",
        ]
    ordinary_packet["self_purification"]["knowledge_retrieval_evidence"] = rel_path(bad_knowledge_path)
    ordinary_packet_path = artifact_root / "ordinary-lifecycle-missing-knowledge-impact.json"
    write_json(ordinary_packet_path, ordinary_packet)
    completed = subprocess.run(
        [
            "runtime/bin/redcap",
            "lifecycle",
            "check",
            "--packet",
            rel_path(ordinary_packet_path),
            "--events",
            rel_path(negative_events_path),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    probes.append({
        "name": "ordinary_task_negative_lifecycle_missing_knowledge_impact",
        "packet": rel_path(ordinary_packet_path),
        "events": rel_path(negative_events_path),
        "expected_exit_code": 1,
        "exit_code": completed.returncode,
        "ok": completed.returncode != 0 and "decision effects" in completed.stdout,
        "stdout_tail": completed.stdout[-1000:],
        "stderr_tail": completed.stderr[-1000:],
    })
    failures = [probe for probe in probes if not probe["ok"]]
    return {
        "ok": not failures,
        "probes": probes,
        "failures": failures,
    }


def cmd_impact_check(args: argparse.Namespace) -> int:
    index_path = pathlib.Path(args.index).resolve()
    quality_path = pathlib.Path(args.quality).resolve()
    out_path = pathlib.Path(args.out).resolve()
    artifact_root = pathlib.Path(args.artifact_root).resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)

    trace = impact_trace_for_query(query=args.query, index_path=index_path, quality_path=quality_path)
    positive_failures = validate_impact_trace(trace)
    lifecycle_usage = scan_lifecycle_knowledge_usage(
        pathlib.Path(args.lifecycle_root).resolve(),
        minimum_count=args.minimum_lifecycle_usage_count,
        task_start_marker=pathlib.Path(args.task_start_marker).resolve(),
    )
    positive_failures.extend(lifecycle_usage["failures"])
    lifecycle_regression = run_lifecycle_regression_probes(artifact_root)
    if not lifecycle_regression["ok"]:
        positive_failures.append("lifecycle regression probes failed")
    negative_probes = run_impact_negative_probes(trace, index_path=index_path, quality_path=quality_path)
    negative_ok = all(probe["failed_as_expected"] for probe in negative_probes)

    retrieval_path = artifact_root / "knowledge-retrieval-evidence.json"
    write_json(retrieval_path, trace)
    evidence = {
        "schema_id": "redcap-rsp-08-knowledge-impact-evidence",
        "rsp": "RSP-08",
        "ok": not positive_failures and negative_ok,
        "contract_path": rel_path(pathlib.Path(args.contract).resolve()),
        "acceptance": {
            "positive": {
                "status": "pass" if not positive_failures else "fail",
                "checks": [
                    "knowledge search produced at least one direct-driver adopted entry",
                    "planning, implementation, and verification all record how the knowledge changed decisions",
                    "quality metadata participates in the direct-driver decision",
                    "lifecycle history shows knowledge retrieval evidence was used in real tasks",
                    "historical lifecycle samples and their knowledge evidence are older than the current RSP-07/08 task start marker",
                    "lifecycle regression proves positive samples still pass and missing knowledge impact hard-fails",
                    "counterfactual analysis records changed decisions without pretending to be independent runtime execution",
                ],
                "failures": positive_failures,
            },
            "negative": {
                "status": "pass" if negative_ok else "fail",
                "checks": negative_probes,
            },
        },
        "changed_reality": [
            "知识召回现在有 RSP-08 专项验收：命中知识必须显式影响计划、实现和验收。",
            "impact-check 会扫描真实 lifecycle 历史，确认知识影响证据不是只在本检查器内生成。",
            "历史样本必须早于当前 RSP-07/08 任务起点，避免本轮自举证据冒充自然触发。",
            "无关命中、缺少 adopted entry 或缺少 decision_impacts 不能通过验收。",
            "反事实记录明确为分析路径，不声称执行了两条独立项目交付路径。",
            "质量元数据必须参与 direct-driver 决策，避免错误知识直接驱动实现。",
        ],
        "artifacts": [
            "runtime/core/knowledge_gateway.py",
            "assets/contracts/knowledge-impact-trace.json",
            rel_path(retrieval_path),
        ],
        "trace": trace,
        "counterfactual_analysis": trace.get("counterfactual_analysis"),
        "historical_samples": lifecycle_usage,
        "lifecycle_usage": lifecycle_usage,
        "lifecycle_regression": lifecycle_regression,
    }
    write_json(out_path, evidence)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    if evidence["ok"]:
        print("REDCAP_KNOWLEDGE_IMPACT_TRACE_OK")
        return 0
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap knowledge gateway")
    parser.add_argument("--index", default=str(DEFAULT_INDEX))
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check")
    check.set_defaults(func=cmd_check)
    search = subparsers.add_parser("search")
    search.add_argument("query")
    search.add_argument("--require-match", "--require-hit", dest="require_match", action="store_true")
    search.add_argument("--quality", default=str(DEFAULT_QUALITY))
    search.add_argument("--direct-driver-only", action="store_true")
    search.set_defaults(func=cmd_search)
    impact = subparsers.add_parser("impact-check")
    impact.add_argument("--query", default="self purification knowledge retrieval task candidate promotion no promote")
    impact.add_argument("--quality", default=str(DEFAULT_QUALITY))
    impact.add_argument("--contract", default=str(DEFAULT_IMPACT_CONTRACT))
    impact.add_argument("--artifact-root", default=str(DEFAULT_IMPACT_ARTIFACTS))
    impact.add_argument("--lifecycle-root", default=str(REPO_ROOT / "assets" / "evidence" / "lifecycle"))
    impact.add_argument("--task-start-marker", default=str(DEFAULT_RSP_07_08_START_MARKER))
    impact.add_argument("--minimum-lifecycle-usage-count", type=int, default=2)
    impact.add_argument("--out", default=str(DEFAULT_IMPACT_EVIDENCE))
    impact.set_defaults(func=cmd_impact_check)
    draft = subparsers.add_parser("draft")
    draft.add_argument("--id", required=True)
    draft.add_argument("--title", required=True)
    draft.add_argument("--summary", required=True)
    draft.add_argument("--tags", required=True, help="Comma-separated tag list")
    draft.add_argument("--body")
    draft.add_argument("--body-file")
    draft.add_argument("--source-path")
    draft.add_argument("--output")
    draft.set_defaults(func=cmd_draft)
    review = subparsers.add_parser("review")
    review.add_argument("--draft", required=True)
    review.add_argument("--decision", choices=["approve", "reject"], required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--reason", required=True)
    review.add_argument("--output")
    review.set_defaults(func=cmd_review)
    promote = subparsers.add_parser("promote")
    promote.add_argument("--review", required=True)
    promote.set_defaults(func=cmd_promote)
    self_check = subparsers.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

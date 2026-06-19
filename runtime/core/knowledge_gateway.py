#!/usr/bin/env python3
"""Minimal index-first RedCap knowledge gateway."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(os.environ.get("REDCAP_KNOWLEDGE_ROOT", pathlib.Path(__file__).resolve().parents[2])).resolve()
DEFAULT_INDEX = REPO_ROOT / "assets" / "knowledge" / "index.json"
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


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def resolve_path(path: str | pathlib.Path) -> pathlib.Path:
    candidate = pathlib.Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def rel_path(path: pathlib.Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


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


def search_entries(payload: dict[str, Any], query: str) -> list[dict[str, Any]]:
    terms = [term.casefold() for term in query.split() if term.strip()]
    entries = payload.get("entries", [])
    matches: list[dict[str, Any]] = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        haystack = " ".join([
            str(entry.get("id", "")),
            str(entry.get("title", "")),
            str(entry.get("summary", "")),
            " ".join(str(tag) for tag in entry.get("tags", []) if isinstance(tag, str)),
        ]).casefold()
        if not terms or all(term in haystack for term in terms):
            matches.append({
                "id": entry.get("id"),
                "title": entry.get("title"),
                "route": entry.get("route"),
                "summary": entry.get("summary"),
                "first_read": entry.get("first_read"),
                "body_read_rule": entry.get("body_read_rule"),
            })
    return matches


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
    print(json.dumps({"ok": True, "entry": entry, "review": rel_path(review_path)}, ensure_ascii=False, indent=2))
    print("REDCAP_KNOWLEDGE_PROMOTE_OK")
    return 0


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
        ]
        failures: list[str] = []
        for command in commands:
            completed = __import__("subprocess").run(command, cwd=str(root_path), env=env, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                failures.append(f"{' '.join(command[2:])}: exit {completed.returncode}: {completed.stderr or completed.stdout}")
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
    result = {
        "query": args.query,
        "matches": matches,
        "ok": bool(matches) or not args.require_match,
        "read_policy": "index-first; read first_read before body; raw archives require explicit task need",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.require_match and not matches:
        print("REDCAP_KNOWLEDGE_GATEWAY_NO_MATCH")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap knowledge gateway")
    parser.add_argument("--index", default=str(DEFAULT_INDEX))
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check")
    check.set_defaults(func=cmd_check)
    search = subparsers.add_parser("search")
    search.add_argument("query")
    search.add_argument("--require-match", "--require-hit", dest="require_match", action="store_true")
    search.set_defaults(func=cmd_search)
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

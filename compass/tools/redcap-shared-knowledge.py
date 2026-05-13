#!/usr/bin/env python3
# 用途：公共知识库治理脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#shared-knowledge-layer

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ROOT = "templates/shared-knowledge"
ALLOWED_KINDS = {
    "lesson",
    "identity-signal",
    "skill-candidate",
    "governance-rule",
    "methodology",
    "case-study",
    "source-note",
}
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def fail(message: str, code: int = 1) -> None:
    print(f"[redcap-shared-knowledge] {message}", file=sys.stderr)
    raise SystemExit(code)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def timestamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = lowered.strip("-")
    return lowered[:64] or "entry"


def user_namespace(value: str) -> str:
    """Preserve human-facing user names while keeping path segments safe."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    cleaned = cleaned.strip(".-_")
    return cleaned[:64] or "user"


def normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def fingerprint(kind: str, title: str, body: str) -> str:
    normalized = "\n".join([normalize_text(kind), normalize_text(title), normalize_text(body)])
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def resolve_root(repo_root: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return repo_root / path


def parse_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def ensure_structure(root: Path) -> None:
    (root / "users").mkdir(parents=True, exist_ok=True)
    (root / "indexes").mkdir(parents=True, exist_ok=True)
    (root / "schemas").mkdir(parents=True, exist_ok=True)


def template_root(repo_root: Path) -> Path:
    canonical = repo_root / "templates" / "shared-knowledge"
    legacy = repo_root / "shared-knowledge"
    return canonical if canonical.is_dir() else legacy


def copy_template(repo_root: Path, root: Path) -> None:
    source_root = template_root(repo_root)
    template_readme = source_root / "README.md"
    template_gitignore = source_root / ".gitignore"
    template_schema = source_root / "schemas" / "entry.schema.json"
    if template_readme.is_file() and not (root / "README.md").exists():
        shutil.copyfile(template_readme, root / "README.md")
    if template_gitignore.is_file() and not (root / ".gitignore").exists():
        shutil.copyfile(template_gitignore, root / ".gitignore")
    if template_schema.is_file() and not (root / "schemas" / "entry.schema.json").exists():
        shutil.copyfile(template_schema, root / "schemas" / "entry.schema.json")
    for placeholder in (root / "users" / ".gitkeep", root / "indexes" / ".gitkeep"):
        if not placeholder.exists():
            placeholder.write_text("", encoding="utf-8")


def iter_entries(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    users_root = root / "users"
    if not users_root.exists():
        return entries
    for path in sorted(users_root.glob("*/*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        meta = parse_frontmatter(text)
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "user": meta.get("user", path.parent.name),
                "kind": meta.get("kind", ""),
                "title": meta.get("title", ""),
                "created_at": meta.get("created_at", ""),
                "fingerprint": meta.get("fingerprint", ""),
            }
        )
    return entries


def validate_root(root: Path) -> None:
    if not (root / "README.md").is_file():
        fail(f"missing shared knowledge README: {root / 'README.md'}")
    if not (root / "schemas" / "entry.schema.json").is_file():
        fail(f"missing entry schema: {root / 'schemas' / 'entry.schema.json'}")
    for entry in iter_entries(root):
        rel = entry["path"]
        name = Path(rel).name
        if not re.match(r"^\d{8}T\d{6}Z-[a-z0-9-]+-.+\.md$", name):
            fail(f"entry filename violates append-only timestamp rule: {rel}")
        for field in ("title", "kind", "user", "created_at", "fingerprint"):
            if not entry.get(field):
                fail(f"entry missing frontmatter {field}: {rel}")
        if entry.get("kind") not in ALLOWED_KINDS:
            fail(f"entry uses invalid kind: {rel}")


def build_index(root: Path) -> dict[str, Any]:
    entries = iter_entries(root)
    return {
        "version": 1,
        "generated_at": iso(utc_now()),
        "entry_count": len(entries),
        "entries": entries,
    }


def command_init(args: argparse.Namespace, repo_root: Path) -> int:
    root = resolve_root(repo_root, args.root)
    ensure_structure(root)
    copy_template(repo_root, root)
    print(f"SHARED_KNOWLEDGE_INIT_OK {root}")
    return 0


def read_body(args: argparse.Namespace) -> str:
    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8")
    if args.body:
        return args.body
    fail("append/dedupe requires --body-file or --body")
    return ""


def find_duplicate(root: Path, fp: str) -> dict[str, Any] | None:
    for entry in iter_entries(root):
        if entry.get("fingerprint") == fp:
            return entry
    return None


def command_append(args: argparse.Namespace, repo_root: Path) -> int:
    root = resolve_root(repo_root, args.root)
    ensure_structure(root)
    copy_template(repo_root, root)
    if args.kind not in ALLOWED_KINDS:
        fail(f"invalid kind: {args.kind}")
    user = user_namespace(args.user)
    body = read_body(args)
    fp = fingerprint(args.kind, args.title, body)
    duplicate = find_duplicate(root, fp)
    if duplicate is not None:
        print(f"SHARED_KNOWLEDGE_DUPLICATE path={duplicate['path']} fingerprint={fp}")
        return 3

    now = utc_now()
    user_dir = root / "users" / user
    user_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{timestamp(now)}-{args.kind}-{slugify(args.title)}.md"
    path = user_dir / filename
    if path.exists():
        fail(f"refusing to overwrite existing append-only entry: {path}")
    source_lines = "\n".join(f"- {source}" for source in args.source)
    text = (
        "---\n"
        f'title: "{args.title}"\n'
        f"kind: {args.kind}\n"
        f"user: {user}\n"
        f"created_at: {iso(now)}\n"
        f"fingerprint: {fp}\n"
        "---\n\n"
        f"# {args.title}\n\n"
        f"{body.strip()}\n"
    )
    if source_lines:
        text += "\n## Sources\n\n" + source_lines + "\n"
    path.write_text(text, encoding="utf-8")
    print(f"SHARED_KNOWLEDGE_APPEND_OK path={path.relative_to(root).as_posix()} fingerprint={fp}")
    return 0


def command_index(args: argparse.Namespace, repo_root: Path) -> int:
    root = resolve_root(repo_root, args.root)
    ensure_structure(root)
    payload = build_index(root)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
        print(f"SHARED_KNOWLEDGE_INDEX_OK {output}")
    elif args.snapshot:
        output = root / "indexes" / f"{timestamp(utc_now())}-catalog.json"
        output.write_text(text + "\n", encoding="utf-8")
        print(f"SHARED_KNOWLEDGE_INDEX_OK {output}")
    else:
        print(text)
    return 0


def command_dedupe(args: argparse.Namespace, repo_root: Path) -> int:
    root = resolve_root(repo_root, args.root)
    body = read_body(args)
    fp = fingerprint(args.kind, args.title, body)
    duplicate = find_duplicate(root, fp)
    payload = {"duplicate": duplicate is not None, "fingerprint": fp, "existing": duplicate}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if duplicate is None else 3


def command_check(args: argparse.Namespace, repo_root: Path) -> int:
    root = resolve_root(repo_root, args.root)
    validate_root(root)
    index = build_index(root)
    fingerprints = [entry.get("fingerprint") for entry in index["entries"] if entry.get("fingerprint")]
    duplicates = sorted({fp for fp in fingerprints if fingerprints.count(fp) > 1})
    if duplicates:
        fail("duplicate fingerprints found: " + ", ".join(duplicates))
    print(f"SHARED_KNOWLEDGE_OK root={root} entries={index['entry_count']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_root(p: argparse.ArgumentParser) -> None:
        p.add_argument("--root", default=DEFAULT_ROOT)

    init = sub.add_parser("init")
    add_root(init)

    check = sub.add_parser("check")
    add_root(check)

    index = sub.add_parser("index")
    add_root(index)
    index.add_argument("--output")
    index.add_argument("--snapshot", action="store_true")

    append = sub.add_parser("append")
    add_root(append)
    append.add_argument("--user", required=True)
    append.add_argument("--kind", required=True)
    append.add_argument("--title", required=True)
    append.add_argument("--body-file")
    append.add_argument("--body")
    append.add_argument("--source", action="append", default=[])

    dedupe = sub.add_parser("dedupe")
    add_root(dedupe)
    dedupe.add_argument("--kind", required=True)
    dedupe.add_argument("--title", required=True)
    dedupe.add_argument("--body-file")
    dedupe.add_argument("--body")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = args.repo_root.resolve()
    if args.command == "init":
        return command_init(args, repo_root)
    if args.command == "check":
        return command_check(args, repo_root)
    if args.command == "index":
        return command_index(args, repo_root)
    if args.command == "append":
        return command_append(args, repo_root)
    if args.command == "dedupe":
        return command_dedupe(args, repo_root)
    fail(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())

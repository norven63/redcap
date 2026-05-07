#!/usr/bin/env python3
# 用途：产品形态与检索治理脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#product-shape-and-retrieval

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote


LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-file-lookup-dictionary-check] {message}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing policy: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid policy json: {exc}")
    if not isinstance(payload, dict):
        fail("policy must be a json object")
    return payload


def strip_anchor(raw: str) -> str:
    return raw.split("#", 1)[0].strip()


def resolve_repo_path(root: Path, raw: str) -> Path:
    path = Path(strip_anchor(raw)).expanduser()
    if path.is_absolute():
        return path
    return root / path


def normalize_rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def dictionary_mentions_path(text: str, rel_path: str) -> bool:
    if rel_path in text:
        return True
    encoded = rel_path.replace(" ", "%20")
    return encoded in text


def validate_links(root: Path, dictionary_path: Path, text: str) -> list[str]:
    broken: list[str] = []
    base = dictionary_path.parent
    for match in LINK_RE.finditer(text):
        target = match.group(1).strip()
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        target = unquote(strip_anchor(target))
        if not target:
            continue
        candidate = Path(target)
        if not candidate.is_absolute():
            candidate = (base / candidate).resolve()
        if not candidate.exists():
            broken.append(target)
        elif root not in [candidate, *candidate.parents]:
            broken.append(target)
    return broken


def is_script_header_required(rel_path: str, row: dict[str, Any], policy: dict[str, Any]) -> bool:
    header_policy = policy.get("script_header_policy")
    if not isinstance(header_policy, dict) or not header_policy.get("enabled"):
        return False
    if row.get("header_required") is False:
        return False
    prefixes = header_policy.get("path_prefixes", [])
    extensions = header_policy.get("extensions", [])
    if not isinstance(prefixes, list) or not isinstance(extensions, list):
        fail("script_header_policy path_prefixes/extensions must be lists")
    path = Path(rel_path)
    suffix = path.suffix
    return any(rel_path.startswith(str(prefix)) for prefix in prefixes) and suffix in set(str(item) for item in extensions)


def validate_script_header(path: Path, rel_path: str, policy: dict[str, Any]) -> list[str]:
    header_policy = policy.get("script_header_policy", {})
    max_scan_lines = int(header_policy.get("max_scan_lines", 20))
    purpose_markers = header_policy.get("required_purpose_markers", ["用途：", "作用："])
    dictionary_marker = str(header_policy.get("required_dictionary_marker", "Dictionary:"))
    if not isinstance(purpose_markers, list) or not purpose_markers:
        fail("script_header_policy required_purpose_markers must be a non-empty list")

    try:
        head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:max_scan_lines])
    except UnicodeDecodeError as exc:
        return [f"{rel_path}: header is not utf-8 readable: {exc}"]

    missing: list[str] = []
    purpose_re = re.compile(
        r"^\s*(#|//|/\*|\*)\s*("
        + "|".join(re.escape(str(marker)) for marker in purpose_markers)
        + ")",
        flags=re.MULTILINE,
    )
    if not purpose_re.search(head):
        missing.append("Chinese purpose marker")
    if dictionary_marker not in head:
        missing.append("Dictionary backlink")
    if missing:
        return [f"{rel_path}: missing {', '.join(missing)}"]
    return []


def load_required_paths(policy: dict[str, Any]) -> list[dict[str, Any]]:
    required = policy.get("required_paths")
    if not isinstance(required, list) or not required:
        fail("policy required_paths must be a non-empty list")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in required:
        if isinstance(item, str):
            row = {"path": item}
        elif isinstance(item, dict):
            row = item
        else:
            fail("required_paths entries must be strings or objects")
        raw_path = row.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            fail("required path entry missing path")
        rel_path = strip_anchor(raw_path)
        if rel_path in seen:
            fail(f"duplicate required path: {rel_path}")
        seen.add(rel_path)
        rows.append({**row, "path": rel_path})
    return rows


def plan_rows(rows: list[dict[str, Any]]) -> str:
    output = [
        "| 文件 | 定位 | 含义 | owner | check |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        rel = row["path"]
        link = f"[`{rel}`](../{rel})"
        output.append(
            "| "
            + " | ".join(
                [
                    link,
                    str(row.get("section") or "Unclassified"),
                    str(row.get("meaning") or "Needs dictionary meaning"),
                    str(row.get("owner") or "TBD"),
                    f"`{row.get('check') or 'TBD'}`",
                ]
            )
            + " |"
        )
    return "\n".join(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--policy", default="references/file-lookup-dictionary-policy.json")
    parser.add_argument("--plan", action="store_true", help="Print markdown rows for missing entries instead of only failing.")
    args = parser.parse_args()

    root = args.root.resolve()
    policy_path = resolve_repo_path(root, args.policy)
    policy = load_json(policy_path)
    if policy.get("version") != 1:
        fail("policy version must be 1")
    dictionary_rel = policy.get("dictionary_path")
    if not isinstance(dictionary_rel, str) or not dictionary_rel.strip():
        fail("policy missing dictionary_path")
    dictionary_path = resolve_repo_path(root, dictionary_rel)
    if not dictionary_path.is_file():
        fail(f"missing dictionary: {dictionary_path}")
    text = dictionary_path.read_text(encoding="utf-8")

    missing_files: list[str] = []
    missing_entries: list[dict[str, Any]] = []
    missing_headers: list[str] = []
    for row in load_required_paths(policy):
        rel = row["path"]
        optional = bool(row.get("optional"))
        repo_path = resolve_repo_path(root, rel)
        if not repo_path.exists() and not optional:
            missing_files.append(rel)
            continue
        if not dictionary_mentions_path(text, rel):
            missing_entries.append(row)
        if repo_path.exists() and is_script_header_required(rel, row, policy):
            missing_headers.extend(validate_script_header(repo_path, rel, policy))

    broken_links = validate_links(root, dictionary_path, text)
    if args.plan and missing_entries:
        print(plan_rows(missing_entries))

    if missing_files:
        fail("required files missing from repo: " + ", ".join(sorted(missing_files)))
    if missing_entries:
        fail("required files missing from dictionary: " + ", ".join(row["path"] for row in missing_entries))
    if broken_links:
        fail("dictionary contains broken local links: " + ", ".join(sorted(set(broken_links))))
    if missing_headers:
        fail("script headers missing required short purpose/backlink: " + "; ".join(missing_headers))

    print(f"FILE_LOOKUP_DICTIONARY_OK required_paths={len(load_required_paths(policy))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

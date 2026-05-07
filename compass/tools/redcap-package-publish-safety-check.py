#!/usr/bin/env python3
# 用途：发布安全治理脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import fnmatch
import json
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Iterable


DEFAULT_POLICY = "references/package-publish-safety-policy.json"


@dataclass(frozen=True)
class Finding:
    kind: str
    path: str
    detail: str


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-package-publish-safety-check] {message}")


def rel_to_root(root: pathlib.Path, path: pathlib.Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        fail(f"candidate path escapes repository root: {path}")


def load_policy(path: pathlib.Path) -> dict:
    if not path.is_file():
        fail(f"missing policy: {path}")
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid policy json: {exc}")
    if policy.get("version") != 1:
        fail("policy version must be 1")
    for key in ("default_package_globs", "deny_path_globs", "secret_patterns"):
        if not isinstance(policy.get(key), list):
            fail(f"policy field must be a list: {key}")
    if not isinstance(policy.get("default_exclude_globs", []), list):
        fail("policy field must be a list: default_exclude_globs")
    return policy


def excluded(rel: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(rel, pattern) for pattern in patterns)


def expand_globs(root: pathlib.Path, patterns: Iterable[str], exclude_patterns: Iterable[str]) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    seen: set[pathlib.Path] = set()
    for pattern in patterns:
        if not isinstance(pattern, str) or not pattern.strip():
            fail("empty package glob in policy")
        matches = sorted(root.glob(pattern))
        if not matches:
            fail(f"default package glob matched no files: {pattern}")
        for match in matches:
            if match.is_dir():
                for child in sorted(p for p in match.rglob("*") if p.is_file()):
                    if excluded(rel_to_root(root, child), exclude_patterns):
                        continue
                    resolved = child.resolve()
                    if resolved not in seen:
                        files.append(child)
                        seen.add(resolved)
            elif match.is_file():
                if excluded(rel_to_root(root, match), exclude_patterns):
                    continue
                resolved = match.resolve()
                if resolved not in seen:
                    files.append(match)
                    seen.add(resolved)
    if not files:
        fail("default package globs produced no files after exclusions")
    return files


def explicit_paths(root: pathlib.Path, values: Iterable[str]) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    seen: set[pathlib.Path] = set()
    for value in values:
        candidate = pathlib.Path(value)
        if not candidate.is_absolute():
            candidate = root / candidate
        if not candidate.exists():
            fail(f"candidate path does not exist: {value}")
        rel_to_root(root, candidate)
        if candidate.is_dir():
            children = sorted(p for p in candidate.rglob("*") if p.is_file())
        else:
            children = [candidate]
        for child in children:
            resolved = child.resolve()
            if resolved not in seen:
                files.append(child)
                seen.add(resolved)
    return files


def read_candidate_list(root: pathlib.Path, path: pathlib.Path) -> list[pathlib.Path]:
    if not path.is_file():
        fail(f"missing candidate list: {path}")
    values = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return explicit_paths(root, values)


def deny_path_findings(root: pathlib.Path, files: list[pathlib.Path], deny_globs: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for file_path in files:
        rel = rel_to_root(root, file_path)
        for pattern in deny_globs:
            if fnmatch.fnmatch(rel, pattern):
                findings.append(Finding("denied-path", rel, pattern))
                break
    return findings


def compile_secret_patterns(policy: dict) -> list[tuple[str, re.Pattern[str]]]:
    compiled: list[tuple[str, re.Pattern[str]]] = []
    for entry in policy["secret_patterns"]:
        if not isinstance(entry, dict):
            fail("secret pattern entries must be objects")
        pattern_id = entry.get("id")
        pattern = entry.get("pattern")
        if not isinstance(pattern_id, str) or not pattern_id.strip():
            fail("secret pattern missing id")
        if not isinstance(pattern, str) or not pattern.strip():
            fail(f"secret pattern missing regex: {pattern_id}")
        try:
            compiled.append((pattern_id, re.compile(pattern)))
        except re.error as exc:
            fail(f"invalid secret regex {pattern_id}: {exc}")
    return compiled


def secret_findings(root: pathlib.Path, files: list[pathlib.Path], patterns: list[tuple[str, re.Pattern[str]]], max_bytes: int) -> list[Finding]:
    findings: list[Finding] = []
    for file_path in files:
        rel = rel_to_root(root, file_path)
        size = file_path.stat().st_size
        if size > max_bytes:
            findings.append(Finding("oversized-file", rel, f"{size} bytes exceeds max_text_scan_bytes={max_bytes}"))
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern_id, pattern in patterns:
                if pattern.search(line):
                    findings.append(Finding("secret-pattern", rel, f"{pattern_id}:line={line_number}"))
                    break
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Fail-closed publish/package safety check for RedCap release candidates.")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--policy", default=DEFAULT_POLICY, help="policy JSON path")
    parser.add_argument("--candidate-list", help="newline-delimited package candidate file list")
    parser.add_argument("--path", action="append", default=[], help="explicit candidate path; can be repeated")
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()
    policy_path = pathlib.Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = root / policy_path
    policy = load_policy(policy_path)

    if args.candidate_list:
        list_path = pathlib.Path(args.candidate_list)
        if not list_path.is_absolute():
            list_path = root / list_path
        files = read_candidate_list(root, list_path)
        source = f"candidate-list:{rel_to_root(root, list_path) if list_path.resolve().is_relative_to(root) else list_path}"
    elif args.path:
        files = explicit_paths(root, args.path)
        source = "explicit-paths"
    else:
        files = expand_globs(root, policy["default_package_globs"], policy.get("default_exclude_globs", []))
        source = "default-package-globs"

    deny_findings = deny_path_findings(root, files, policy["deny_path_globs"])
    max_bytes = policy.get("max_text_scan_bytes", 2 * 1024 * 1024)
    if not isinstance(max_bytes, int) or max_bytes <= 0:
        fail("max_text_scan_bytes must be a positive integer")
    content_findings = secret_findings(root, files, compile_secret_patterns(policy), max_bytes)
    findings = deny_findings + content_findings

    if findings:
        print("PACKAGE_PUBLISH_SAFETY_FAIL")
        for finding in findings[:50]:
            print(f"{finding.kind}\t{finding.path}\t{finding.detail}")
        if len(findings) > 50:
            print(f"... {len(findings) - 50} more findings")
        raise SystemExit(1)

    print("PACKAGE_PUBLISH_SAFETY_OK")
    print(f"source={source}")
    print(f"files_scanned={len(files)}")


if __name__ == "__main__":
    main()

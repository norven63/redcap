#!/usr/bin/env python3
"""Restore bounded generated evidence through a RedCap-owned writer."""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import stat
import sys
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = (REPO_ROOT / "assets" / "evidence").resolve()
ALLOWED_SUFFIXES = {".json", ".jsonl", ".lock", ".md", ".txt"}


def rel(path: pathlib.Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def is_relative_to(path: pathlib.Path, parent: pathlib.Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def executable_bit_set(path: pathlib.Path) -> bool:
    mode = path.stat().st_mode
    return bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


def validate_source_tree(source: pathlib.Path) -> list[str]:
    failures: list[str] = []
    if not source.exists():
        return [f"source does not exist: {source}"]
    if not source.is_dir():
        return [f"source must be a directory: {source}"]
    files = [path for path in source.rglob("*") if path.is_file()]
    if not files:
        failures.append(f"source has no files: {source}")
    for path in files:
        if path.suffix not in ALLOWED_SUFFIXES:
            failures.append(f"source file extension is not allowed: {path}")
        if executable_bit_set(path):
            failures.append(f"source file is executable: {path}")
    return failures


def copy_tree(source: pathlib.Path, dest: pathlib.Path, replace: bool) -> None:
    if dest.exists():
        if not replace:
            raise SystemExit(f"destination already exists: {dest}")
        if not dest.is_dir():
            raise SystemExit(f"destination exists but is not a directory: {dest}")
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)


def result_payload(source: pathlib.Path, dest: pathlib.Path, failures: list[str]) -> dict[str, Any]:
    files = []
    if dest.exists():
        files = sorted(rel(path) for path in dest.rglob("*") if path.is_file())
    return {
        "ok": not failures,
        "source": str(source),
        "destination": rel(dest) if is_relative_to(dest, REPO_ROOT) else str(dest),
        "files": files,
        "failures": failures,
    }


def cmd_restore(args: argparse.Namespace) -> int:
    source = pathlib.Path(args.source).expanduser().resolve()
    dest = (REPO_ROOT / args.dest).resolve()
    failures: list[str] = []
    if not is_relative_to(dest, EVIDENCE_ROOT):
        failures.append(f"destination must be under {rel(EVIDENCE_ROOT)}")
    failures.extend(validate_source_tree(source))
    if failures:
        print(json.dumps(result_payload(source, dest, failures), ensure_ascii=False, indent=2))
        return 1
    copy_tree(source, dest, args.replace)
    print(json.dumps(result_payload(source, dest, []), ensure_ascii=False, indent=2))
    print("REDCAP_EVIDENCE_RESTORE_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Restore bounded RedCap generated evidence")
    sub = parser.add_subparsers(dest="command", required=True)

    restore = sub.add_parser("restore")
    restore.add_argument("--source", required=True)
    restore.add_argument("--dest", required=True)
    restore.add_argument("--replace", action="store_true")
    restore.set_defaults(func=cmd_restore)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

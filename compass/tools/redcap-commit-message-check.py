#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import re
import sys


TYPE_RE = re.compile(r"^(feat|fix|refactor|docs|test|chore|style|perf)(\([^()]+\))?: .+$")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
AUTHOR_MARKER = "作者:redcap"


def load_message(path: pathlib.Path) -> list[str]:
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.startswith("# ------------------------ >8"):
            break
        if raw.startswith("#"):
            continue
        lines.append(raw.rstrip())
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def fail(message: str) -> int:
    print(f"[redcap-commit-msg] {message}", file=sys.stderr)
    return 1


def main() -> int:
    if len(sys.argv) != 2:
        return fail("usage: redcap-commit-message-check.py <commit-msg-file>")

    path = pathlib.Path(sys.argv[1])
    if not path.is_file():
        return fail(f"missing commit message file: {path}")

    lines = load_message(path)
    if not lines:
        return fail("empty commit message")

    subject = lines[0].strip()
    if subject.startswith(("Merge ", "Revert ", "fixup! ", "squash! ")):
        return 0
    if not TYPE_RE.match(subject):
        return fail("subject must match type(scope): 简要描述 or type: 简要描述")
    if len(subject) > 72:
        return fail(f"subject exceeds 72 characters: {len(subject)}")
    if subject.endswith((".", "。")):
        return fail("subject must not end with punctuation")
    if not CJK_RE.search(subject):
        return fail("subject should use Chinese as the primary language")

    body_lines = [line for line in lines[1:] if line.strip()]
    if not body_lines:
        return fail("commit body is required and must briefly explain why")
    if body_lines[-1].strip() != AUTHOR_MARKER:
        return fail(f"last non-empty line must be {AUTHOR_MARKER}")

    explanation_lines = [line.strip() for line in body_lines[:-1] if line.strip()]
    if not explanation_lines:
        return fail("commit body must include at least one explanation line before 作者:redcap")
    if not any(len(line) >= 6 for line in explanation_lines):
        return fail("commit explanation is too short")

    return 0


if __name__ == "__main__":
    sys.exit(main())

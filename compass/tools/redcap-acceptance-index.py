#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pathlib
import re
import sys


def fail(message: str) -> int:
    print(f"[redcap-acceptance-index] {message}", file=sys.stderr)
    return 1


def load_cases(path: pathlib.Path) -> tuple[list[dict[str, object]], int]:
    lines = path.read_text(encoding="utf-8").splitlines()
    cases: list[dict[str, object]] = []
    function_lines: dict[str, int] = {}
    case_to_function: dict[str, str] = {}

    for idx, line in enumerate(lines, start=1):
        match = re.match(r"^run_([a-zA-Z0-9_]+)_case\(\)\s*\{", line)
        if match:
            function_lines[match.group(1).replace("_", "-")] = idx
            continue
        match = re.match(r"^\s*([a-z0-9][a-z0-9-]+)\)\s*$", line)
        if match:
            case_name = match.group(1)
            if case_name == "all":
                continue
            for follow_idx in range(idx, min(idx + 6, len(lines))):
                call = re.search(r"\brun_([a-zA-Z0-9_]+)_case\b", lines[follow_idx])
                if call:
                    case_to_function[case_name] = call.group(1).replace("_", "-")
                    break

    for case_name, function_name in sorted(case_to_function.items()):
        cases.append(
            {
                "case": case_name,
                "function": "run_" + function_name.replace("-", "_") + "_case",
                "line": function_lines.get(function_name),
            }
        )
    return cases, len(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo")
    parser.add_argument("acceptance_path")
    parser.add_argument("command", choices=("summary", "find", "check"))
    parser.add_argument("query", nargs="?", default="")
    args = parser.parse_args()

    root = pathlib.Path(args.repo)
    path = pathlib.Path(args.acceptance_path)
    query = args.query.strip().lower()

    if args.command == "find" and not query:
        return fail("find requires a case substring")
    if not path.is_file():
        return fail("acceptance script missing")

    cases, total_lines = load_cases(path)
    if args.command == "check":
        if len(cases) < 50:
            return fail(f"too few indexed cases: {len(cases)}")
        missing = [str(item["case"]) for item in cases if item["line"] is None]
        if missing:
            return fail("cases missing function definitions: " + ", ".join(missing[:10]))
        print("ACCEPTANCE_INDEX_OK")
        print(f"cases={len(cases)}")
        print("rule=Use find <case-substring> or rg for specific cases; do not bulk-read redcap-multi-session-acceptance.sh.")
        return 0

    if args.command == "summary":
        print("ACCEPTANCE_INDEX_SUMMARY")
        print(f"path={path.relative_to(root).as_posix()}")
        print(f"lines={total_lines} cases={len(cases)}")
        print("rule=Use find <case-substring> before opening the large acceptance script.")
        for item in cases[:40]:
            print(f"case={item['case']}\tline={item['line']}")
        if len(cases) > 40:
            print(f"... {len(cases) - 40} more cases; use find <substring> for targeted lookup.")
        return 0

    matches = [
        item
        for item in cases
        if query in str(item["case"]).lower() or query in str(item["function"]).lower()
    ]
    print("ACCEPTANCE_INDEX_FIND")
    print(f"query={query}")
    print("rule=Open only the returned line ranges needed for the target case.")
    for item in matches[:30]:
        print(f"case={item['case']}\tfunction={item['function']}\tline={item['line']}")
    if len(matches) > 30:
        print(f"... {len(matches) - 30} more matches")
    return 0 if matches else 1


if __name__ == "__main__":
    sys.exit(main())

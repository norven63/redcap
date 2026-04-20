#!/usr/bin/env bash
# Build a small first-read index for the large acceptance suite.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ACCEPTANCE_PATH="$REDCAP_ROOT/compass/tools/redcap-multi-session-acceptance.sh"

usage() {
    cat <<'EOF' >&2
usage:
  bash compass/tools/redcap-acceptance-index.sh summary
  bash compass/tools/redcap-acceptance-index.sh find <case-substring>
  bash compass/tools/redcap-acceptance-index.sh check
EOF
}

command="${1:-summary}"
case_query="${2:-}"

python3 - "$REDCAP_ROOT" "$ACCEPTANCE_PATH" "$command" "$case_query" <<'PY'
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
path = pathlib.Path(sys.argv[2])
command = sys.argv[3]
query = sys.argv[4].strip().lower()


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-acceptance-index] {message}")


if command not in {"summary", "find", "check"}:
    fail("unsupported command")
if command == "find" and not query:
    fail("find requires a case substring")
if not path.is_file():
    fail("acceptance script missing")

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
        if case_name in {"all"}:
            continue
        for follow_idx in range(idx, min(idx + 6, len(lines))):
            call = re.search(r"\brun_([a-zA-Z0-9_]+)_case\b", lines[follow_idx])
            if call:
                case_to_function[case_name] = call.group(1).replace("_", "-")
                break

for case_name, function_name in sorted(case_to_function.items()):
    line_no = function_lines.get(function_name)
    cases.append(
        {
            "case": case_name,
            "function": "run_" + function_name.replace("-", "_") + "_case",
            "line": line_no,
        }
    )

if command == "check":
    if len(cases) < 50:
        fail(f"too few indexed cases: {len(cases)}")
    missing = [item["case"] for item in cases if item["line"] is None]
    if missing:
        fail("cases missing function definitions: " + ", ".join(missing[:10]))
    print("ACCEPTANCE_INDEX_OK")
    print(f"cases={len(cases)}")
    print("rule=Use find <case-substring> or rg for specific cases; do not bulk-read redcap-multi-session-acceptance.sh.")
    raise SystemExit(0)

if command == "summary":
    print("ACCEPTANCE_INDEX_SUMMARY")
    print(f"path={path.relative_to(root).as_posix()}")
    print(f"lines={len(lines)} cases={len(cases)}")
    print("rule=Use find <case-substring> before opening the large acceptance script.")
    for item in cases[:40]:
        print(f"case={item['case']}\tline={item['line']}")
    if len(cases) > 40:
        print(f"... {len(cases) - 40} more cases; use find <substring> for targeted lookup.")
    raise SystemExit(0)

matches = [
    item for item in cases
    if query in str(item["case"]).lower() or query in str(item["function"]).lower()
]
print("ACCEPTANCE_INDEX_FIND")
print(f"query={query}")
print("rule=Open only the returned line ranges needed for the target case.")
for item in matches[:30]:
    print(f"case={item['case']}\tfunction={item['function']}\tline={item['line']}")
if len(matches) > 30:
    print(f"... {len(matches) - 30} more matches")
if not matches:
    raise SystemExit(1)
PY

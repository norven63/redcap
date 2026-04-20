#!/usr/bin/env bash
# shellcheck shell=bash
# Build a small first-read catalog for compass/docs so agents avoid bulk-reading historical evidence.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CATALOG_PATH="${REDCAP_DOCS_CATALOG_PATH:-$REDCAP_ROOT/compass/docs/catalog.json}"

usage() {
    cat <<'EOF' >&2
usage:
  bash compass/tools/redcap-docs-catalog.sh generate [output-path]
  bash compass/tools/redcap-docs-catalog.sh check
  bash compass/tools/redcap-docs-catalog.sh summary
  bash compass/tools/redcap-docs-catalog.sh plan <query> [limit]
  bash compass/tools/redcap-docs-catalog.sh budget <repo-relative-doc-path>...
  bash compass/tools/redcap-docs-catalog.sh retention-check
EOF
}

generate_catalog() {
    local output_path="$1"

    mkdir -p "$(dirname "$output_path")"
    python3 - "$REDCAP_ROOT" "$output_path" <<'PY'
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

root = pathlib.Path(sys.argv[1])
output_path = pathlib.Path(sys.argv[2])
docs_root = root / "compass/docs"
registry_path = root / "references/spec-registry.json"


def repo_path(path: pathlib.Path) -> str:
    return path.relative_to(root).as_posix()


def normalize_text(value: str, max_len: int = 240) -> str:
    value = " ".join(value.split())
    if len(value) <= max_len:
        return value
    return value[: max_len - 1].rstrip() + "…"


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def first_heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return normalize_text(match.group(1), 160)
    return fallback


def section_lines(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    capture = False
    captured: list[str] = []
    heading_re = re.compile(r"^###\s+" + re.escape(heading) + r"\s*$")
    for line in lines:
        if heading_re.match(line):
            capture = True
            continue
        if capture and re.match(r"^#{1,3}\s+", line):
            break
        if capture:
            captured.append(line)
    return captured


def bullets_from_section(text: str, heading: str, limit: int = 2) -> list[str]:
    bullets: list[str] = []
    for line in section_lines(text, heading):
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(normalize_text(stripped[2:], 260))
        if len(bullets) >= limit:
            break
    return bullets


def first_paragraph(text: str) -> str:
    paragraph: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("---"):
            if paragraph:
                break
            continue
        if stripped.startswith("|"):
            continue
        paragraph.append(stripped)
        if len(" ".join(paragraph)) >= 160:
            break
    return normalize_text(" ".join(paragraph), 240)


def collection_for(path: pathlib.Path) -> str:
    rel = path.relative_to(docs_root).as_posix()
    if "/" not in rel:
        return "root"
    return rel.split("/", 1)[0]


def is_cataloged_doc(path: pathlib.Path) -> bool:
    if not path.is_file() or path.name == ".gitkeep" or path.name == "catalog.json":
        return False
    rel = repo_path(path)
    if rel.startswith("compass/docs/task-reports/"):
        name = path.name
        if name.startswith(("zz-acceptance-", "zz-review-")):
            return False
    return True


def load_spec_registry() -> dict[str, dict]:
    if not registry_path.is_file():
        return {}
    registry = json.loads(read_text(registry_path))
    specs = registry.get("specs", [])
    if not isinstance(specs, list):
        return {}
    result: dict[str, dict] = {}
    for entry in specs:
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            result[entry["path"]] = entry
    return result


def task_report_status(index: int, total: int) -> str:
    if index >= max(total - 3, 0):
        return "hot"
    if index >= max(total - 8, 0):
        return "warm"
    return "cold-candidate"


def read_policy(collection: str, status: str, spec_status=None) -> str:
    if collection == "specs":
        if spec_status in {"active", "reference"}:
            return "read-registry-summary-first"
        return "read-on-demand"
    if collection == "task-reports":
        if status == "hot":
            return "read-catalog-summary-first-then-open-if-current-anchor"
        return "read-catalog-summary-by-default"
    if collection in {"research", "traces"}:
        return "read-on-demand-after-catalog"
    return "read-on-demand"


all_docs = [
    path
    for path in sorted(docs_root.rglob("*"))
    if path != output_path and is_cataloged_doc(path)
]

spec_registry = load_spec_registry()
task_reports = [path for path in all_docs if collection_for(path) == "task-reports"]
task_report_order = {repo_path(path): idx for idx, path in enumerate(sorted(task_reports))}
entries: list[dict] = []
summary_by_collection: dict[str, dict] = {}
collection_counter: Counter[str] = Counter()
collection_bytes: Counter[str] = Counter()
collection_lines: Counter[str] = Counter()
collection_chars: Counter[str] = Counter()

for path in all_docs:
    rel = repo_path(path)
    collection = collection_for(path)
    text = read_text(path)
    stat = path.stat()
    lines = len(text.splitlines())
    chars = len(text)

    collection_counter[collection] += 1
    collection_bytes[collection] += stat.st_size
    collection_lines[collection] += lines
    collection_chars[collection] += chars

    title = first_heading(text, path.stem)
    status = "reference"
    role = "docs-evidence"
    spec_status = None
    summary = first_paragraph(text)
    summary_points: dict[str, list[str]] = {}

    if collection == "specs":
        spec = spec_registry.get(rel, {})
        title = spec.get("title") or title
        role = spec.get("role") or "design-snapshot"
        spec_status = spec.get("status") if isinstance(spec.get("status"), str) else None
        status = spec_status or "unregistered"
        summary = spec.get("summary") or summary
    elif collection == "task-reports":
        order = task_report_order[rel]
        status = task_report_status(order, len(task_report_order))
        role = "closure-evidence"
        extracted_points = {
            "current_done": bullets_from_section(text, "0.1 当前已完成"),
            "previous_step": bullets_from_section(text, "0.2 上一步完成的是", 1),
            "next_step": bullets_from_section(text, "0.3 下一步计划做的是", 1),
            "position": bullets_from_section(text, "0.4 整体计划脉络图与当前位置", 2),
        }
        flat_points = [item for values in extracted_points.values() for item in values]
        if flat_points:
            summary = normalize_text(" / ".join(flat_points[:2]), 320)
        if status == "hot":
            summary_points = extracted_points
    elif collection == "research":
        role = "research-evidence"
    elif collection == "traces":
        role = "trace-evidence"
    elif collection == "archive":
        role = "archived-evidence"
        status = "archived"

    entry = {
        "path": rel,
        "collection": collection,
        "title": title,
        "role": role,
        "status": status,
        "read_policy": read_policy(collection, status, spec_status),
        "size_bytes": stat.st_size,
        "lines": lines,
        "chars": chars,
        "summary": normalize_text(summary, 360),
    }
    if collection == "task-reports":
        entry["status_basis"] = "filename_recency_only"
    if collection == "specs":
        spec = spec_registry.get(rel, {})
        entry["runtime_authority"] = bool(spec.get("runtime_authority"))
        entry["paired_control_paths"] = spec.get("paired_control_paths", [])
        entry["paired_debt_ids"] = spec.get("paired_debt_ids", [])
    if summary_points:
        entry["summary_points"] = summary_points
    entries.append(entry)

for collection in sorted(collection_counter):
    summary_by_collection[collection] = {
        "file_count": collection_counter[collection],
        "size_bytes": collection_bytes[collection],
        "lines": collection_lines[collection],
        "chars": collection_chars[collection],
        "rough_token_pressure": {
            "low": collection_chars[collection] // 4,
            "high": collection_chars[collection] // 2,
        },
    }

largest = sorted(entries, key=lambda item: (-item["chars"], item["path"]))[:8]
payload = {
    "version": 1,
    "generated_by": "compass/tools/redcap-docs-catalog.sh",
    "purpose": "First-read index for compass/docs. Read this catalog before opening historical specs, traces, research, or task reports.",
    "rules": [
        "Do not bulk-read compass/docs/** by default.",
        "Use summary/read_policy first, then open only the specific source document needed for the current question.",
        "Use plan <query> to select candidate evidence without opening source documents.",
        "Use budget <paths...> before opening source documents; directories, uncataloged paths, too many files, or oversized read sets fail closed.",
        "Regenerate with: bash compass/tools/redcap-docs-catalog.sh generate",
    ],
    "summary": {
        "file_count": len(entries),
        "size_bytes": sum(item["size_bytes"] for item in entries),
        "lines": sum(item["lines"] for item in entries),
        "chars": sum(item["chars"] for item in entries),
        "rough_token_pressure": {
            "low": sum(item["chars"] for item in entries) // 4,
            "high": sum(item["chars"] for item in entries) // 2,
        },
        "collections": summary_by_collection,
        "largest_entries": [
            {
                "path": item["path"],
                "chars": item["chars"],
                "lines": item["lines"],
                "read_policy": item["read_policy"],
            }
            for item in largest
        ],
    },
    "entries": sorted(entries, key=lambda item: item["path"]),
}

output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")
PY
}

print_summary() {
    local tmp_path

    tmp_path="$(mktemp)"
    trap 'rm -f "$tmp_path" 2>/dev/null || true' RETURN
    generate_catalog "$tmp_path"
    python3 - "$tmp_path" <<'PY'
import json
import sys

catalog = json.loads(open(sys.argv[1], encoding="utf-8").read())
summary = catalog["summary"]
print("DOCS_CATALOG_SUMMARY")
print(f"files={summary['file_count']} bytes={summary['size_bytes']} lines={summary['lines']} chars={summary['chars']}")
pressure = summary["rough_token_pressure"]
print(f"rough_token_pressure={pressure['low']}..{pressure['high']}")
print("collections:")
for name, item in sorted(summary["collections"].items()):
    pressure = item["rough_token_pressure"]
    print(f"  - {name}: files={item['file_count']} lines={item['lines']} chars={item['chars']} rough_tokens={pressure['low']}..{pressure['high']}")
print("largest_entries:")
for item in summary["largest_entries"]:
    print(f"  - {item['path']} lines={item['lines']} chars={item['chars']} policy={item['read_policy']}")
PY
}

print_plan() {
    local query="$1"
    local limit="${2:-8}"
    local tmp_path

    if [[ -z "$query" ]]; then
        usage
        return 2
    fi

    tmp_path="$(mktemp)"
    trap 'rm -f "$tmp_path" 2>/dev/null || true' RETURN
    generate_catalog "$tmp_path"
    python3 - "$tmp_path" "$query" "$limit" "$REDCAP_ROOT" <<'PY'
import json
import pathlib
import re
import sys

catalog = json.loads(open(sys.argv[1], encoding="utf-8").read())
query = sys.argv[2]
try:
    limit = max(1, int(sys.argv[3]))
except Exception:
    limit = 8

terms = [term.casefold() for term in re.findall(r"[\w\u4e00-\u9fff-]+", query) if term.strip()]
if not terms:
    raise SystemExit("[redcap-docs-catalog] query has no searchable terms")

repo_root = pathlib.Path(sys.argv[4])
current_report = ""
task_file = repo_root / ".dev-task.md"
if task_file.is_file():
    for line in task_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("task_report:"):
            current_report = line.split(":", 1)[1].strip()
            break
current_terms = {"current", "latest", "active", "pending", "当前", "最新", "活跃", "收尾"}


def haystack(entry):
    parts = [
        entry.get("path", ""),
        entry.get("title", ""),
        entry.get("role", ""),
        entry.get("status", ""),
        entry.get("summary", ""),
    ]
    for values in (entry.get("summary_points") or {}).values():
        if isinstance(values, list):
            parts.extend(str(item) for item in values)
    return " ".join(parts).casefold()


ranked = []
for entry in catalog.get("entries", []):
    text = haystack(entry)
    score = sum(text.count(term) for term in terms)
    if score <= 0:
        continue
    if entry.get("status") == "hot":
        score += 3
    if current_report and entry.get("path") == current_report and any(term in current_terms for term in terms):
        score += 20
    if entry.get("status") in {"active", "reference"}:
        score += 2
    if entry.get("read_policy", "").startswith("read-catalog"):
        score += 1
    ranked.append((score, entry.get("chars", 0), entry))

ranked.sort(key=lambda item: (-item[0], item[1], item[2].get("path", "")))

print("DOCS_ACCESS_PLAN")
print(f"query={query}")
print("rule=Open only the exact paths needed; run budget before opening source files.")
if not ranked:
    print("candidates=0")
    raise SystemExit(0)
for score, _chars, entry in ranked[:limit]:
    pressure = entry.get("chars", 0)
    print(
        "\t".join(
            [
                f"score={score}",
                f"path={entry.get('path', '')}",
                f"policy={entry.get('read_policy', '')}",
                f"status={entry.get('status', '')}",
                f"rough_tokens={pressure // 4}..{pressure // 2}",
                f"summary={entry.get('summary', '')}",
            ]
        )
    )
PY
}

check_budget() {
    if [[ "$#" -eq 0 ]]; then
        usage
        return 2
    fi

    python3 - "$REDCAP_ROOT" "$CATALOG_PATH" "$@" <<'PY'
import json
import os
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
catalog_path = pathlib.Path(sys.argv[2])
raw_paths = sys.argv[3:]
max_files = int(os.environ.get("REDCAP_DOCS_BUDGET_MAX_FILES", "3"))
max_high_tokens = int(os.environ.get("REDCAP_DOCS_BUDGET_MAX_HIGH_TOKENS", "20000"))


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-docs-catalog] access budget failed: {message}")


if not catalog_path.is_file():
    fail("catalog missing; run generate/check first")

catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
entries = {entry["path"]: entry for entry in catalog.get("entries", []) if isinstance(entry, dict) and entry.get("path")}

normalized: list[str] = []
for raw in raw_paths:
    if not raw.strip():
        continue
    path = pathlib.Path(raw)
    if path.is_absolute():
        try:
            rel = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            fail(f"path escapes repo: {raw}")
    else:
        rel = path.as_posix().lstrip("./")

    if rel in {"compass/docs", "compass/docs/"} or rel.endswith("/"):
        fail(f"directory reads are not allowed by default: {raw}")
    if "*" in rel or "?" in rel or "[" in rel:
        fail(f"glob reads are not allowed by default: {raw}")
    if rel not in entries:
        fail(f"path is not cataloged docs evidence: {raw}")
    normalized.append(rel)

seen = []
for rel in normalized:
    if rel not in seen:
        seen.append(rel)

if not seen:
    fail("no docs paths supplied")
if len(seen) > max_files:
    fail(f"too many docs files requested: {len(seen)} > {max_files}")

total_chars = sum(int(entries[rel].get("chars", 0)) for rel in seen)
high_tokens = total_chars // 2
if high_tokens > max_high_tokens:
    fail(f"rough token budget exceeded: {high_tokens} > {max_high_tokens}")

print("DOCS_ACCESS_BUDGET_OK")
print(f"files={len(seen)} rough_tokens={total_chars // 4}..{high_tokens} max_high_tokens={max_high_tokens}")
for rel in seen:
    entry = entries[rel]
    print(
        "\t".join(
            [
                f"path={rel}",
                f"policy={entry.get('read_policy', '')}",
                f"status={entry.get('status', '')}",
                f"rough_tokens={int(entry.get('chars', 0)) // 4}..{int(entry.get('chars', 0)) // 2}",
            ]
        )
    )
PY
}

check_retention() {
    local tmp_path

    tmp_path="$(mktemp)"
    trap 'rm -f "$tmp_path" 2>/dev/null || true' RETURN
    generate_catalog "$tmp_path"
    python3 - "$REDCAP_ROOT" "$tmp_path" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
catalog = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
log_path = root / "compass/docs/archive/retention-log.md"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-docs-catalog] retention check failed: {message}")


if not log_path.is_file():
    fail("missing compass/docs/archive/retention-log.md")
log_text = log_path.read_text(encoding="utf-8", errors="replace")
for required in ("redcap:docs-retention-log", "不删除 closure evidence", "catalog + plan + budget"):
    if required not in log_text:
        fail(f"retention log missing required phrase: {required}")

entries = catalog.get("entries", [])
task_reports = [entry for entry in entries if entry.get("collection") == "task-reports"]
cold = [entry for entry in task_reports if entry.get("status") == "cold-candidate"]
hot = [entry for entry in task_reports if entry.get("status") == "hot"]
largest = catalog.get("summary", {}).get("largest_entries", [])
summary = catalog.get("summary", {})
pressure = summary.get("rough_token_pressure", {})

print("DOCS_RETENTION_CHECK_OK")
print(f"files={summary.get('file_count', 'unknown')} rough_tokens={pressure.get('low', '?')}..{pressure.get('high', '?')}")
print(f"task_reports={len(task_reports)} hot={len(hot)} cold_candidates={len(cold)}")
if cold:
    print("archive_candidates_check_only=" + ",".join(entry.get("path", "") for entry in cold[:8]))
if largest:
    print("largest_check_only=" + ",".join(item.get("path", "") for item in largest[:5]))
PY
}

check_catalog() {
    local tmp_path status

    tmp_path="$(mktemp)"
    trap 'rm -f "$tmp_path" 2>/dev/null || true' RETURN
    generate_catalog "$tmp_path"

    if [[ ! -f "$CATALOG_PATH" ]]; then
        echo "[redcap-docs-catalog] catalog missing: compass/docs/catalog.json" >&2
        echo "[redcap-docs-catalog] run: bash compass/tools/redcap-docs-catalog.sh generate" >&2
        return 1
    fi

    if cmp -s "$tmp_path" "$CATALOG_PATH"; then
        echo "DOCS_CATALOG_OK"
        return 0
    fi

    echo "[redcap-docs-catalog] catalog is out of date; regenerate it:" >&2
    echo "  bash compass/tools/redcap-docs-catalog.sh generate" >&2
    status=1
    if command -v diff >/dev/null 2>&1; then
        diff -u "$CATALOG_PATH" "$tmp_path" | sed -n '1,120p' >&2 || true
    fi
    return "$status"
}

COMMAND="${1:-summary}"
case "$COMMAND" in
    generate)
        generate_catalog "${2:-$CATALOG_PATH}"
        ;;
    check)
        check_catalog
        ;;
    summary)
        print_summary
        ;;
    plan)
        print_plan "${2:-}" "${3:-8}"
        ;;
    budget)
        shift
        check_budget "$@"
        ;;
    retention-check)
        check_retention
        ;;
    *)
        usage
        exit 2
        ;;
esac

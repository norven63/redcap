#!/usr/bin/env python3
# 用途：知识沉淀与自进化脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
from collections import Counter


CATALOGED_DOC_SUFFIXES = {".html", ".htm", ".json", ".md", ".markdown", ".yaml", ".yml"}


def normalize_text(value: str, max_len: int = 240) -> str:
    value = " ".join(value.split())
    if len(value) <= max_len:
        return value
    return value[: max_len - 1].rstrip() + "…"


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def repo_path(root: pathlib.Path, path: pathlib.Path) -> str:
    return path.relative_to(root).as_posix()


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


def collection_for(docs_root: pathlib.Path, path: pathlib.Path) -> str:
    rel = path.relative_to(docs_root).as_posix()
    if "/" not in rel:
        return "root"
    return rel.split("/", 1)[0]


def is_cataloged_doc(root: pathlib.Path, output_path: pathlib.Path, path: pathlib.Path) -> bool:
    if not path.is_file() or path.name == ".gitkeep" or path == output_path or path.name == "catalog.json":
        return False
    docs_root = root / "compass/docs"
    rel_to_docs = path.relative_to(docs_root)
    if any(part.startswith(".") for part in rel_to_docs.parts):
        return False
    if path.suffix.lower() not in CATALOGED_DOC_SUFFIXES:
        return False
    rel = repo_path(root, path)
    if rel.startswith("compass/docs/task-reports/"):
        name = path.name
        if name.startswith(("zz-acceptance-", "zz-review-")):
            return False
    return True


def load_spec_registry(root: pathlib.Path) -> dict[str, dict]:
    registry_path = root / "references/spec-registry.json"
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


def load_alias_resolver_summary(root: pathlib.Path) -> dict:
    resolver_path = root / "references/legacy-asset-migration-alias-resolver.json"
    pointer = resolver_path.relative_to(root).as_posix()
    base = {
        "path": pointer,
        "read_policy": "read-summary-first-then-use-redcap-legacy-asset-alias-resolver",
        "resolver_command": "bash compass/tools/redcap-legacy-asset-alias-resolver.sh --resolve <path>",
    }
    if not resolver_path.is_file():
        return {
            **base,
            "status": "missing",
            "meaning": "No durable legacy alias resolver is present yet.",
        }
    try:
        payload = json.loads(read_text(resolver_path))
    except json.JSONDecodeError:
        return {
            **base,
            "status": "invalid-json",
            "meaning": "Alias resolver exists but cannot be parsed; run its checker.",
        }
    summary_block = payload.get("summary") if isinstance(payload, dict) else {}
    if not isinstance(summary_block, dict):
        summary_block = {}
    return {
        **base,
        "status": "present",
        "manifest_id": payload.get("manifest_id") if isinstance(payload, dict) else None,
        "task_id": payload.get("task_id") if isinstance(payload, dict) else None,
        "source_result": payload.get("source_result") if isinstance(payload, dict) else None,
        "source_result_sha256": payload.get("source_result_sha256") if isinstance(payload, dict) else None,
        "alias_entries": summary_block.get("alias_entries", 0),
        "old_catalog_anchors_present": summary_block.get("old_catalog_anchors_present", 0),
        "retired_old_anchors": summary_block.get("retired_old_anchors", 0),
        "planned_targets": summary_block.get("planned_targets", 0),
        "applied_targets": summary_block.get("applied_targets", 0),
        "meaning": (
            "Old compass/docs paths are retired for migrated assets; use the resolver to map them to redcap-knowledge canonical paths."
            if isinstance(payload.get("resolution_policy"), dict)
            and payload.get("resolution_policy", {}).get("delete_last_applied") is True
            else "Old compass/docs paths remain authoritative; redcap-knowledge paths are private copy targets that may be planned or applied, but they are not canonical anchors."
        ),
    }


def task_report_status(index: int, total: int) -> str:
    if index >= max(total - 3, 0):
        return "hot"
    if index >= max(total - 8, 0):
        return "warm"
    return "cold-candidate"


def read_policy(collection: str, status: str, spec_status: str | None = None) -> str:
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


def build_catalog(root: pathlib.Path, output_path: pathlib.Path) -> dict:
    docs_root = root / "compass/docs"
    all_docs = [
        path
        for path in sorted(docs_root.rglob("*"))
        if is_cataloged_doc(root, output_path, path)
    ]
    spec_registry = load_spec_registry(root)
    task_reports = [path for path in all_docs if collection_for(docs_root, path) == "task-reports"]
    task_report_order = {repo_path(root, path): idx for idx, path in enumerate(sorted(task_reports))}

    entries: list[dict] = []
    summary_by_collection: dict[str, dict] = {}
    collection_counter: Counter[str] = Counter()
    collection_bytes: Counter[str] = Counter()
    collection_lines: Counter[str] = Counter()
    collection_chars: Counter[str] = Counter()

    for path in all_docs:
        rel = repo_path(root, path)
        collection = collection_for(docs_root, path)
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
    return {
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
        "legacy_alias_resolver": load_alias_resolver_summary(root),
        "entries": sorted(entries, key=lambda item: item["path"]),
    }


def dump_catalog(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def summary(catalog: dict) -> int:
    summary_block = catalog["summary"]
    print("DOCS_CATALOG_SUMMARY")
    print(
        f"files={summary_block['file_count']} bytes={summary_block['size_bytes']} lines={summary_block['lines']} chars={summary_block['chars']}"
    )
    pressure = summary_block["rough_token_pressure"]
    print(f"rough_token_pressure={pressure['low']}..{pressure['high']}")
    print("collections:")
    for name, item in sorted(summary_block["collections"].items()):
        item_pressure = item["rough_token_pressure"]
        print(
            f"  - {name}: files={item['file_count']} lines={item['lines']} chars={item['chars']} rough_tokens={item_pressure['low']}..{item_pressure['high']}"
        )
    print("largest_entries:")
    for item in summary_block["largest_entries"]:
        print(
            f"  - {item['path']} lines={item['lines']} chars={item['chars']} policy={item['read_policy']}"
        )
    return 0


def plan(root: pathlib.Path, catalog: dict, query: str, limit: int) -> int:
    terms = [term.casefold() for term in re.findall(r"[\w\u4e00-\u9fff-]+", query) if term.strip()]
    if not terms:
        print("[redcap-docs-catalog] query has no searchable terms", file=sys.stderr)
        return 1

    current_report = ""
    task_file = root / ".dev-task.md"
    if task_file.is_file():
        for line in task_file.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("task_report:"):
                current_report = line.split(":", 1)[1].strip()
                break
    current_terms = {"current", "latest", "active", "pending", "当前", "最新", "活跃", "收尾"}

    def haystack(entry: dict) -> str:
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

    ranked: list[tuple[int, int, dict]] = []
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
        if str(entry.get("read_policy", "")).startswith("read-catalog"):
            score += 1
        ranked.append((score, int(entry.get("chars", 0)), entry))

    ranked.sort(key=lambda item: (-item[0], item[1], item[2].get("path", "")))
    print("DOCS_ACCESS_PLAN")
    print(f"query={query}")
    print("rule=Open only the exact paths needed; run budget before opening source files.")
    if not ranked:
        print("candidates=0")
        return 0
    for score, _chars, entry in ranked[:limit]:
        pressure = int(entry.get("chars", 0))
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
    return 0


def budget(root: pathlib.Path, catalog_path: pathlib.Path, raw_paths: list[str]) -> int:
    max_files = int(os.environ.get("REDCAP_DOCS_BUDGET_MAX_FILES", "3"))
    max_high_tokens = int(os.environ.get("REDCAP_DOCS_BUDGET_MAX_HIGH_TOKENS", "20000"))

    if not catalog_path.is_file():
        print("[redcap-docs-catalog] access budget failed: catalog missing; run generate/check first", file=sys.stderr)
        return 1
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    entries = {
        entry["path"]: entry
        for entry in catalog.get("entries", [])
        if isinstance(entry, dict) and entry.get("path")
    }

    normalized: list[str] = []
    for raw in raw_paths:
        if not raw.strip():
            continue
        path = pathlib.Path(raw)
        if path.is_absolute():
            try:
                rel = path.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                print(f"[redcap-docs-catalog] access budget failed: path escapes repo: {raw}", file=sys.stderr)
                return 1
        else:
            rel = path.as_posix().lstrip("./")
        if rel in {"compass/docs", "compass/docs/"} or rel.endswith("/"):
            print(f"[redcap-docs-catalog] access budget failed: directory reads are not allowed by default: {raw}", file=sys.stderr)
            return 1
        if any(char in rel for char in "*?["):
            print(f"[redcap-docs-catalog] access budget failed: glob reads are not allowed by default: {raw}", file=sys.stderr)
            return 1
        if rel not in entries:
            print(f"[redcap-docs-catalog] access budget failed: path is not cataloged docs evidence: {raw}", file=sys.stderr)
            return 1
        normalized.append(rel)

    seen: list[str] = []
    for rel in normalized:
        if rel not in seen:
            seen.append(rel)
    if not seen:
        print("[redcap-docs-catalog] access budget failed: no docs paths supplied", file=sys.stderr)
        return 1
    if len(seen) > max_files:
        print(f"[redcap-docs-catalog] access budget failed: too many docs files requested: {len(seen)} > {max_files}", file=sys.stderr)
        return 1
    total_chars = sum(int(entries[rel].get("chars", 0)) for rel in seen)
    high_tokens = total_chars // 2
    if high_tokens > max_high_tokens:
        print(f"[redcap-docs-catalog] access budget failed: rough token budget exceeded: {high_tokens} > {max_high_tokens}", file=sys.stderr)
        return 1

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
    return 0


def retention_check(root: pathlib.Path, catalog: dict) -> int:
    log_path = root / "compass/docs/archive/retention-log.md"
    if not log_path.is_file():
        print("[redcap-docs-catalog] retention check failed: missing compass/docs/archive/retention-log.md", file=sys.stderr)
        return 1
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    for required in ("redcap:docs-retention-log", "不删除 closure evidence", "catalog + plan + budget"):
        if required not in log_text:
            print(f"[redcap-docs-catalog] retention check failed: retention log missing required phrase: {required}", file=sys.stderr)
            return 1
    entries = catalog.get("entries", [])
    task_reports = [entry for entry in entries if entry.get("collection") == "task-reports"]
    cold = [entry for entry in task_reports if entry.get("status") == "cold-candidate"]
    hot = [entry for entry in task_reports if entry.get("status") == "hot"]
    largest = catalog.get("summary", {}).get("largest_entries", [])
    summary_block = catalog.get("summary", {})
    pressure = summary_block.get("rough_token_pressure", {})
    print("DOCS_RETENTION_CHECK_OK")
    print(f"files={summary_block.get('file_count', 'unknown')} rough_tokens={pressure.get('low', '?')}..{pressure.get('high', '?')}")
    print(f"task_reports={len(task_reports)} hot={len(hot)} cold_candidates={len(cold)}")
    if cold:
        print("archive_candidates_check_only=" + ",".join(entry.get("path", "") for entry in cold[:8]))
    if largest:
        print("largest_check_only=" + ",".join(item.get("path", "") for item in largest[:5]))
    return 0


def check(root: pathlib.Path, catalog_path: pathlib.Path, catalog: dict) -> int:
    if not catalog_path.is_file():
        print("[redcap-docs-catalog] catalog missing: compass/docs/catalog.json", file=sys.stderr)
        print("[redcap-docs-catalog] run: bash compass/tools/redcap-docs-catalog.sh generate", file=sys.stderr)
        return 1
    expected = dump_catalog(catalog)
    actual = catalog_path.read_text(encoding="utf-8")
    if actual == expected:
        print("DOCS_CATALOG_OK")
        return 0
    print("[redcap-docs-catalog] catalog is out of date; regenerate it:", file=sys.stderr)
    print("  bash compass/tools/redcap-docs-catalog.sh generate", file=sys.stderr)
    return 1


def main() -> int:
    command = sys.argv[1]
    root = pathlib.Path(sys.argv[2]).resolve()
    catalog_path = pathlib.Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else root / "compass/docs/catalog.json"
    catalog = None

    if command == "generate":
        output_path = pathlib.Path(sys.argv[3]).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        catalog = build_catalog(root, output_path)
        output_path.write_text(dump_catalog(catalog), encoding="utf-8")
        return 0

    if command in {"summary", "check", "plan", "retention-check"}:
        catalog = build_catalog(root, catalog_path)

    if command == "summary":
        return summary(catalog)
    if command == "plan":
        if len(sys.argv) < 5 or not sys.argv[4].strip():
            print("[redcap-docs-catalog] query is required", file=sys.stderr)
            return 2
        limit = 8
        if len(sys.argv) > 5:
            try:
                limit = max(1, int(sys.argv[5]))
            except ValueError:
                limit = 8
        return plan(root, catalog, sys.argv[4], limit)
    if command == "budget":
        if len(sys.argv) < 5:
            print("[redcap-docs-catalog] budget requires at least one docs path", file=sys.stderr)
            return 2
        return budget(root, catalog_path, sys.argv[4:])
    if command == "retention-check":
        return retention_check(root, catalog)
    if command == "check":
        return check(root, catalog_path, catalog)

    print(f"[redcap-docs-catalog] unsupported command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())

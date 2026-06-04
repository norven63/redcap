#!/usr/bin/env python3
"""Load RedCap identity sources without leaking their private contents."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE_DIR = REPO_ROOT / "assets" / "evidence" / "soul"
DEFAULT_SOURCES = [
    {
        "id": "legacy_soul",
        "path": "~/.codex/skills/redcap/soul.md",
        "required": False,
        "role": "legacy RedCap soul anchor referenced by AGENTS.md",
    },
    {
        "id": "cap_identity",
        "path": "/Users/norven/.cap/identity.md",
        "required": True,
        "role": "private Cap identity source",
    },
]

SECRET_LINE = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|credential|private[_-]?key)\b|^[A-Z0-9_]{8,}\s*="
)


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def resolve_path(raw_path: str) -> pathlib.Path:
    return pathlib.Path(os.path.expandvars(os.path.expanduser(raw_path))).resolve()


def markdown_title(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or None
    return None


def redact_line(line: str) -> str:
    if SECRET_LINE.search(line):
        return "[REDACTED secret-like line]"
    return line


def summarize_source(source: dict[str, Any]) -> dict[str, Any]:
    path = resolve_path(str(source["path"]))
    result: dict[str, Any] = {
        "id": source["id"],
        "role": source.get("role"),
        "configured_path": source["path"],
        "resolved_path": str(path),
        "required": bool(source.get("required")),
        "exists": path.exists(),
        "readable": False,
        "sha256": None,
        "line_count": 0,
        "char_count": 0,
        "title": None,
        "redacted_line_count": 0,
        "error": None,
    }
    if not path.exists():
        if result["required"]:
            result["error"] = "required source is missing"
        return result
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        result["error"] = f"could not read source: {exc}"
        return result
    redacted_lines = [redact_line(line) for line in text.splitlines()]
    result.update(
        {
            "readable": True,
            "sha256": sha256_text(text),
            "line_count": len(text.splitlines()),
            "char_count": len(text),
            "title": markdown_title(text),
            "redacted_line_count": sum(
                1 for original, redacted in zip(text.splitlines(), redacted_lines)
                if original != redacted
            ),
        }
    )
    return result


def build_packet(sources: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    sources = sources or DEFAULT_SOURCES
    summaries = [summarize_source(source) for source in sources]
    failures = [
        f"{item['id']}: {item['error']}"
        for item in summaries
        if item.get("required") and item.get("error")
    ]
    required_loaded = [
        item["id"]
        for item in summaries
        if item.get("required") and item.get("exists") and item.get("readable")
    ]
    optional_missing = [
        item["id"]
        for item in summaries
        if not item.get("required") and not item.get("exists")
    ]
    packet = {
        "schema_id": "redcap-cap-soul-load",
        "loaded_at": iso_now(),
        "loader": "runtime/core/soul_loader.py",
        "container": {
            "host": "codex",
            "repo_root": str(REPO_ROOT),
            "pid": os.getpid(),
        },
        "ok": not failures,
        "required_loaded": required_loaded,
        "optional_missing": optional_missing,
        "sources": summaries,
        "content_policy": {
            "private_body_written_to_evidence": False,
            "evidence_contains": ["source status", "hashes", "counts", "titles", "redaction counts"],
        },
        "activation": {
            "identity": "Cap",
            "state": "loaded" if not failures else "blocked",
            "message": (
                "Cap identity source is loaded into this RedCap session container."
                if not failures
                else "Cap identity source could not be loaded."
            ),
        },
        "failures": failures,
    }
    return packet


def write_json_atomic(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def write_evidence(packet: dict[str, Any], evidence_dir: pathlib.Path) -> dict[str, str]:
    latest = evidence_dir / "latest-load.json"
    ledger = evidence_dir / "load-ledger.jsonl"
    write_json_atomic(latest, packet)
    append_jsonl(ledger, packet)
    return {"latest": str(latest), "ledger": str(ledger)}


def cmd_check(_: argparse.Namespace) -> int:
    packet = build_packet()
    result = {
        "ok": packet["ok"],
        "required_loaded": packet["required_loaded"],
        "optional_missing": packet["optional_missing"],
        "failures": packet["failures"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if packet["ok"]:
        print("REDCAP_SOUL_SOURCE_OK")
        return 0
    return 1


def cmd_load(args: argparse.Namespace) -> int:
    packet = build_packet()
    evidence = write_evidence(packet, pathlib.Path(args.evidence_dir).resolve())
    output = {
        "ok": packet["ok"],
        "activation": packet["activation"],
        "required_loaded": packet["required_loaded"],
        "optional_missing": packet["optional_missing"],
        "evidence": evidence,
        "failures": packet["failures"],
    }
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print("CAP_SOUL_LOADED" if packet["ok"] else "CAP_SOUL_LOAD_BLOCKED")
        print(packet["activation"]["message"])
        print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if packet["ok"] else 1


def cmd_self_check(_: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="redcap-soul-loader-") as tmp_raw:
        tmp = pathlib.Path(tmp_raw)
        identity = tmp / "identity.md"
        identity.write_text(
            "# I am Cap\n\n"
            "This fixture contains identity material.\n"
            "TEST_SECRET=fixture-value-that-must-redact\n",
            encoding="utf-8",
        )
        packet = build_packet([
            {
                "id": "optional_missing_fixture",
                "path": str(tmp / "missing-soul.md"),
                "required": False,
                "role": "fixture optional",
            },
            {
                "id": "identity_fixture",
                "path": str(identity),
                "required": True,
                "role": "fixture identity",
            },
        ])
        evidence = write_evidence(packet, tmp / "evidence")
        latest = json.loads(pathlib.Path(evidence["latest"]).read_text(encoding="utf-8"))
        failures: list[str] = []
        if not packet["ok"]:
            failures.append("fixture packet did not load")
        if latest["sources"][1]["sha256"] != sha256_text(identity.read_text(encoding="utf-8")):
            failures.append("fixture sha mismatch")
        if latest["sources"][1]["redacted_line_count"] != 1:
            failures.append("secret-like line was not counted for redaction")
        if "fixture-value" in json.dumps(latest, ensure_ascii=False):
            failures.append("evidence leaked fixture secret")
        result = {"ok": not failures, "failures": failures}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if failures:
            return 1
        print("REDCAP_SOUL_LOADER_OK")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap Cap soul loader")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="verify real configured soul sources")
    check.set_defaults(func=cmd_check)

    load = sub.add_parser("load", help="load Cap identity sources and write evidence")
    load.add_argument("--json", action="store_true", help="print structured output only")
    load.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE_DIR))
    load.set_defaults(func=cmd_load)

    self_check = sub.add_parser("self-check", help="run isolated loader self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

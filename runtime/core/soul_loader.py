#!/usr/bin/env python3
"""加载 RedCap 身份源，同时避免泄露私密正文。"""

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
CAP_HOME_ENV = "CAP_HOME"


def cap_home_path() -> tuple[pathlib.Path, str, str]:
    raw = os.environ.get(CAP_HOME_ENV)
    if isinstance(raw, str) and raw.strip():
        return resolve_path(raw), "$CAP_HOME", "env"
    return resolve_path("~/.cap"), "~/.cap", "default"


def default_sources() -> list[dict[str, Any]]:
    cap_home, configured_home, source_kind = cap_home_path()
    return [
        {
            "id": "legacy_soul",
            "path": "~/.codex/skills/redcap/soul.md",
            "required": False,
            "role": "AGENTS.md 引用的旧 RedCap 灵魂锚点",
        },
        {
            "id": "cap_identity",
            "path": str(cap_home / "identity.md"),
            "configured_path": f"{configured_home}/identity.md",
            "required": True,
            "role": "Cap 私有身份源",
            "cap_home_source": source_kind,
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
        "configured_path": source.get("configured_path", source["path"]),
        "resolved_path": str(path),
        "required": bool(source.get("required")),
        "cap_home_source": source.get("cap_home_source"),
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
    if not path.is_file():
        result["error"] = "source is not a regular file"
        return result
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        result["error"] = f"could not read source: {exc}"
        return result
    if result["required"] and not text.strip():
        result["error"] = "required source is empty"
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
    sources = sources or default_sources()
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
            "evidence_contains": ["来源状态", "哈希", "计数", "标题", "脱敏计数"],
        },
        "activation": {
            "identity": "Cap",
            "state": "loaded" if not failures else "blocked",
            "message": (
                "Cap 身份源已加载到当前 RedCap 会话容器。"
                if not failures
                else "Cap 身份源未能加载。"
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
        old_cap_home = os.environ.get(CAP_HOME_ENV)
        old_home = os.environ.get("HOME")
        try:
            env_home = tmp / "env-cap-home"
            env_home.mkdir()
            (env_home / "identity.md").write_text("# Env Cap\n\nfixture\n", encoding="utf-8")
            os.environ[CAP_HOME_ENV] = str(env_home)
            env_packet = build_packet()
            env_identity = next((item for item in env_packet["sources"] if item["id"] == "cap_identity"), {})
            if env_packet.get("ok") is not True or env_identity.get("configured_path") != "$CAP_HOME/identity.md":
                failures.append("CAP_HOME identity source did not load through portable configured path")

            os.environ.pop(CAP_HOME_ENV, None)
            fallback_home = tmp / "fallback-home"
            fallback_identity = fallback_home / ".cap" / "identity.md"
            fallback_identity.parent.mkdir(parents=True)
            fallback_identity.write_text("# Fallback Cap\n\nfixture\n", encoding="utf-8")
            os.environ["HOME"] = str(fallback_home)
            fallback_packet = build_packet()
            fallback_identity_summary = next((item for item in fallback_packet["sources"] if item["id"] == "cap_identity"), {})
            if fallback_packet.get("ok") is not True or fallback_identity_summary.get("configured_path") != "~/.cap/identity.md":
                failures.append("default ~/.cap identity source did not load when CAP_HOME is absent")

            os.environ[CAP_HOME_ENV] = str(tmp / "missing-cap-home")
            missing_dir_packet = build_packet()
            if missing_dir_packet.get("ok") is True or not missing_dir_packet.get("failures"):
                failures.append("missing CAP_HOME directory should block required identity loading")

            missing_identity_home = tmp / "missing-identity-home"
            missing_identity_home.mkdir()
            os.environ[CAP_HOME_ENV] = str(missing_identity_home)
            missing_identity_packet = build_packet()
            if missing_identity_packet.get("ok") is True or not missing_identity_packet.get("failures"):
                failures.append("CAP_HOME without identity.md should block required identity loading")

            empty_identity_home = tmp / "empty-identity-home"
            empty_identity_home.mkdir()
            (empty_identity_home / "identity.md").write_text("", encoding="utf-8")
            os.environ[CAP_HOME_ENV] = str(empty_identity_home)
            empty_identity_packet = build_packet()
            if empty_identity_packet.get("ok") is True or not any("empty" in item for item in empty_identity_packet.get("failures", [])):
                failures.append("empty CAP_HOME identity.md should block required identity loading")

            non_directory_home = tmp / "cap-home-is-file"
            non_directory_home.write_text("not a directory\n", encoding="utf-8")
            os.environ[CAP_HOME_ENV] = str(non_directory_home)
            non_directory_packet = build_packet()
            if non_directory_packet.get("ok") is True or not non_directory_packet.get("failures"):
                failures.append("CAP_HOME pointing to a file should block required identity loading")

            unreadable_identity_home = tmp / "unreadable-identity-home"
            unreadable_identity_home.mkdir()
            unreadable_identity = unreadable_identity_home / "identity.md"
            unreadable_identity.write_text("# Unreadable Cap\n\nfixture\n", encoding="utf-8")
            unreadable_identity.chmod(0)
            try:
                os.environ[CAP_HOME_ENV] = str(unreadable_identity_home)
                unreadable_packet = build_packet()
                if unreadable_packet.get("ok") is True or not unreadable_packet.get("failures"):
                    failures.append("unreadable CAP_HOME identity.md should block required identity loading")
            finally:
                unreadable_identity.chmod(0o600)
        finally:
            if old_cap_home is None:
                os.environ.pop(CAP_HOME_ENV, None)
            else:
                os.environ[CAP_HOME_ENV] = old_cap_home
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home
        result = {"ok": not failures, "failures": failures}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if failures:
            return 1
        print("REDCAP_SOUL_LOADER_OK")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap Cap 身份加载器")
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

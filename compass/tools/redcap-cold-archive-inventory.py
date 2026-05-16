#!/usr/bin/env python3
# 用途：知识冷归档清单脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_ROOT_REL = "private-archive/redcap-knowledge"
ARCHIVE_ROOT = ROOT / ARCHIVE_ROOT_REL
DEFAULT_OUTPUT = ROOT / "references/redcap-knowledge-cold-archive-inventory.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-cold-archive-inventory] {message}")


def rel(path: Path, root: Path = ROOT) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify(path: Path) -> str:
    parts = path.relative_to(ARCHIVE_ROOT).parts
    if parts[0] == "task-reports":
        return "private-task-report-archive"
    if parts[0] == "research":
        return "private-research-archive"
    if parts[0] == "traces":
        return "private-trace-archive"
    return "private-cold-archive"


def build_inventory() -> dict[str, Any]:
    if not ARCHIVE_ROOT.is_dir():
        fail(f"{ARCHIVE_ROOT_REL} archive root missing")
    files: list[dict[str, Any]] = []
    for path in sorted(ARCHIVE_ROOT.rglob("*")):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        files.append(
            {
                "path": rel(path),
                "class": classify(path),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "read_policy": "exact-read-only-after-gateway",
                "public_export": "forbidden-raw",
            }
        )
    by_class: dict[str, int] = {}
    for item in files:
        by_class[item["class"]] = by_class.get(item["class"], 0) + 1
    return {
        "version": 1,
        "inventory_id": "redcap-knowledge-cold-archive",
        "root": ARCHIVE_ROOT_REL,
        "purpose": "Machine-readable private cold archive inventory for progressive retrieval and no-raw-public-export governance.",
        "file_count": len(files),
        "bytes_total": sum(int(item["bytes"]) for item in files),
        "by_class": by_class,
        "must_not_claim": [
            "This inventory is not a public knowledge export.",
            "Raw private reports remain private cold archive evidence.",
            "Use the knowledge gateway before opening exact archive bodies."
        ],
        "files": files,
    }


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"inventory missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid inventory json: {exc}")
    if not isinstance(payload, dict):
        fail("inventory must be a JSON object")
    return payload


def compare(expected: dict[str, Any], actual: dict[str, Any]) -> None:
    expected_compact = json.dumps(expected, ensure_ascii=False, sort_keys=True)
    actual_compact = json.dumps(actual, ensure_ascii=False, sort_keys=True)
    if expected_compact != actual_compact:
        fail("inventory is stale; run redcap-cold-archive-inventory.sh update")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or validate redcap-knowledge cold archive inventory.")
    parser.add_argument("command", choices=("check", "update", "summary"), nargs="?", default="check")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    inventory = build_inventory()
    if args.command == "update":
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"COLD_ARCHIVE_INVENTORY_UPDATED path={rel(output)} files={inventory['file_count']}")
        return 0
    if args.command == "summary":
        print("COLD_ARCHIVE_INVENTORY")
        print(f"files={inventory['file_count']} bytes={inventory['bytes_total']}")
        for key, value in sorted(inventory["by_class"].items()):
            print(f"{key}={value}")
        return 0
    compare(inventory, load_json(output))
    print("COLD_ARCHIVE_INVENTORY_OK")
    print(f"files={inventory['file_count']} bytes={inventory['bytes_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

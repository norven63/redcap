#!/usr/bin/env python3
# 用途：治理资产生命周期脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#product-shape-and-retrieval

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "references/reference-asset-lifecycle.json"
THRESHOLD_BYTES = 20_000


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-reference-asset-lifecycle] {message}")


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def classify(path: Path) -> tuple[str, str, str]:
    name = path.name
    raw = rel(path)
    if raw.startswith("references/backlogs/"):
        return "backlog", "active-until-parent-closed-then-private-archive", "bash compass/tools/redcap-architecture-smell-governance-check.sh"
    if name.startswith("legacy-asset-"):
        return "legacy-migration-ledger", "retain-as-private-migration-evidence", "bash compass/tools/redcap-legacy-asset-migration-check.sh"
    if name.startswith("file-lookup-dictionary"):
        return "lookup-index", "active-machine-and-human-index", "bash compass/tools/redcap-file-lookup-dictionary-check.sh"
    if name == "execution-guarantees.json":
        return "control-plane-registry", "active-validator-registry", "bash compass/tools/redcap-execution-guarantee-check.sh"
    if name == "redcap-parent-task-ledger.md":
        return "parent-task-ledger", "active-parent-state-ledger", "bash compass/tools/redcap-parent-receipt-aggregation-check.sh"
    if name == "redcap-knowledge-cold-archive-inventory.json":
        return "cold-archive-inventory", "generated-private-archive-index", "bash compass/tools/redcap-cold-archive-inventory.sh check"
    if name == "runtime-memory-architecture.md":
        return "human-explainer", "active-human-reference", "bash compass/tools/redcap-file-lookup-dictionary-check.sh"
    return "reference-asset", "index-first-active-reference", "bash compass/tools/redcap-file-lookup-dictionary-check.sh"


def large_reference_files() -> list[Path]:
    allowed = {".json", ".md", ".yaml", ".yml"}
    return [
        path
        for path in sorted((ROOT / "references").rglob("*"))
        if path.is_file() and path.suffix in allowed and path.stat().st_size >= THRESHOLD_BYTES
    ]


def build_inventory() -> dict[str, Any]:
    entries = []
    for path in large_reference_files():
        asset_class, lifecycle, consumer = classify(path)
        entries.append(
            {
                "path": rel(path),
                "bytes": path.stat().st_size,
                "asset_class": asset_class,
                "lifecycle": lifecycle,
                "consumer_check": consumer,
                "read_policy": "index-or-checker-first",
                "public_export": "forbidden-unless-explicit-template-or-release-allowlist",
            }
        )
    return {
        "version": 1,
        "registry_id": "reference-asset-lifecycle",
        "threshold_bytes": THRESHOLD_BYTES,
        "purpose": "Classify large/high-impact references so policies, ledgers, evidence and backlogs do not become an unowned pile.",
        "entries": entries,
    }


def load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"registry missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid registry json: {exc}")
    if not isinstance(payload, dict):
        fail("registry must be a JSON object")
    return payload


def validate(payload: dict[str, Any]) -> None:
    expected = build_inventory()
    if json.dumps(payload, ensure_ascii=False, sort_keys=True) != json.dumps(expected, ensure_ascii=False, sort_keys=True):
        fail("registry is stale; run redcap-reference-asset-lifecycle.sh update")
    paths = set()
    for entry in payload.get("entries", []):
        if not isinstance(entry, dict):
            fail("entries must be objects")
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            fail("entry missing path")
        if path in paths:
            fail(f"duplicate entry: {path}")
        paths.add(path)
        for key in ("asset_class", "lifecycle", "consumer_check", "read_policy", "public_export"):
            if not isinstance(entry.get(key), str) or not entry[key].strip():
                fail(f"{path}: missing {key}")
        command = shlex.split(entry["consumer_check"])
        if len(command) >= 2 and command[0] == "bash":
            script = ROOT / command[1]
            if not script.is_file():
                fail(f"{path}: consumer_check script missing: {command[1]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or validate lifecycle classifications for large references.")
    parser.add_argument("command", nargs="?", choices=("check", "update", "summary"), default="check")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    inventory = build_inventory()
    if args.command == "update":
        output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"REFERENCE_ASSET_LIFECYCLE_UPDATED path={rel(output)} entries={len(inventory['entries'])}")
        return 0
    if args.command == "summary":
        print("REFERENCE_ASSET_LIFECYCLE")
        print(f"threshold_bytes={THRESHOLD_BYTES} entries={len(inventory['entries'])}")
        for entry in inventory["entries"]:
            print(f"{entry['path']}\t{entry['asset_class']}\t{entry['lifecycle']}")
        return 0
    validate(load(output))
    print("REFERENCE_ASSET_LIFECYCLE_OK")
    print(f"entries={len(inventory['entries'])} threshold_bytes={THRESHOLD_BYTES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

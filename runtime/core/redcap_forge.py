#!/usr/bin/env python3
"""RedCap Forge and redcap-arsenal checker."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tempfile
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FORGE_CONTRACT = REPO_ROOT / "assets" / "contracts" / "redcap-forge.json"
ARSENAL_INDEX = REPO_ROOT / "assets" / "knowledge" / "arsenal" / "index.json"
FORBIDDEN_PRIVATE_MARKERS = [
    "/Users/norven/.cap",
    ".cap/identity",
    "assets/evidence/prism/",
    ".raw.json",
    "raw provider",
    "secret",
    "token",
]


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取 JSON：{path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON 必须是对象：{path}")
    return payload


def rel_exists(path: str) -> bool:
    return (REPO_ROOT / path).is_file()


def text_has_private_marker(value: str) -> bool:
    lowered = value.casefold()
    return any(marker.casefold() in lowered for marker in FORBIDDEN_PRIVATE_MARKERS)


def validate_forge(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-forge-contract":
        failures.append("Forge 合同 schema_id 错误")
    if contract.get("target_index") != "assets/knowledge/arsenal/index.json":
        failures.append("Forge 合同必须指向 redcap-arsenal 索引")
    stage_ids = [stage.get("id") for stage in contract.get("stages", []) if isinstance(stage, dict)]
    for required in ["candidate", "private_review", "dedupe", "promote_to_arsenal"]:
        if required not in stage_ids:
            failures.append(f"Forge 阶段缺失：{required}")
    promotion_requires = set(contract.get("promotion_requires", []))
    for required in ["reviewed_source", "privacy_checked", "deduplicated", "human_readable", "index_first", "source_refs_exist"]:
        if required not in promotion_requires:
            failures.append(f"Forge 提升条件缺失：{required}")
    forbidden = "\n".join(str(item) for item in contract.get("forbidden_inputs", []))
    for required in ["用户私有身份", "原始供应方", "凭据"]:
        if required not in forbidden:
            failures.append(f"Forge 禁止输入没有覆盖：{required}")
    return failures


def validate_arsenal(index: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if index.get("schema_id") != "redcap-arsenal-index":
        failures.append("arsenal 索引 schema_id 错误")
    if index.get("visibility") != "public-reusable":
        failures.append("arsenal 必须标记为 public-reusable")
    if index.get("default_read") != "index-first":
        failures.append("arsenal 默认读取必须是 index-first")
    if index.get("privacy_boundary") != "no-private-identity-no-raw-provider-output":
        failures.append("arsenal 隐私边界缺失")
    entries = index.get("entries")
    if not isinstance(entries, list) or not entries:
        failures.append("arsenal entries 必须是非空列表")
        return failures
    seen: set[str] = set()
    for idx, entry in enumerate(entries, start=1):
        label = f"entries[{idx}]"
        if not isinstance(entry, dict):
            failures.append(f"{label} 必须是对象")
            continue
        entry_id = str(entry.get("id") or "")
        if not entry_id:
            failures.append(f"{label}.id 不能为空")
        elif entry_id in seen:
            failures.append(f"arsenal 条目重复：{entry_id}")
        seen.add(entry_id)
        if entry.get("status") != "promoted":
            failures.append(f"{label}.status 必须是 promoted")
        for key in ["title", "summary", "body"]:
            if not isinstance(entry.get(key), str) or not entry.get(key, "").strip():
                failures.append(f"{label}.{key} 不能为空")
        if not rel_exists(str(entry.get("body") or "")):
            failures.append(f"{label}.body 文件不存在：{entry.get('body')}")
        tags = entry.get("tags")
        if not isinstance(tags, list) or not all(isinstance(tag, str) and tag for tag in tags):
            failures.append(f"{label}.tags 必须是非空字符串列表")
        refs = entry.get("source_refs")
        if not isinstance(refs, list) or not refs:
            failures.append(f"{label}.source_refs 必须是非空列表")
        else:
            for ref in refs:
                if not isinstance(ref, str) or not ref:
                    failures.append(f"{label}.source_refs 包含空值")
                elif text_has_private_marker(ref):
                    failures.append(f"{label}.source_refs 含私密或原始输出路径：{ref}")
                elif not (REPO_ROOT / ref).exists():
                    failures.append(f"{label}.source_refs 不存在：{ref}")
        searchable = json.dumps(entry, ensure_ascii=False)
        if text_has_private_marker(searchable):
            failures.append(f"{label} 含私密或原始输出标记")
    return failures


def check() -> dict[str, Any]:
    forge = load_json(FORGE_CONTRACT)
    arsenal = load_json(ARSENAL_INDEX)
    failures = validate_forge(forge) + validate_arsenal(arsenal)
    return {
        "schema_id": "redcap-forge-check",
        "ok": not failures,
        "forge_contract": str(FORGE_CONTRACT),
        "arsenal_index": str(ARSENAL_INDEX),
        "arsenal_entries": len(arsenal.get("entries", [])) if isinstance(arsenal.get("entries"), list) else 0,
        "failures": failures,
    }


def cmd_check(_: argparse.Namespace) -> int:
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_FORGE_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="redcap-forge-") as raw_tmp:
        tmp = pathlib.Path(raw_tmp)
        body = tmp / "entry.md"
        body.write_text("可复用经验。", encoding="utf-8")
        good_index = {
            "schema_id": "redcap-arsenal-index",
            "visibility": "public-reusable",
            "default_read": "index-first",
            "privacy_boundary": "no-private-identity-no-raw-provider-output",
            "entries": [
                {
                    "id": "fixture",
                    "title": "Fixture",
                    "status": "promoted",
                    "summary": "可复用条目。",
                    "tags": ["fixture"],
                    "body": str(body.relative_to(REPO_ROOT)) if body.is_relative_to(REPO_ROOT) else "assets/knowledge/arsenal/anti-empty-completion.md",
                    "source_refs": ["runtime/core/redcap_forge.py"],
                    "target_consumers": ["tests"],
                }
            ],
        }
        good_failures = validate_arsenal(good_index)
        if good_failures:
            failures.append(f"合法 arsenal 样例不应失败：{good_failures}")
        bad_index = dict(good_index)
        bad_entry = dict(good_index["entries"][0])
        bad_entry["source_refs"] = ["/Users/norven/.cap/identity.md"]
        bad_index["entries"] = [bad_entry]
        if not any("私密" in item for item in validate_arsenal(bad_index)):
            failures.append("私密路径样例没有被拒绝")
        bad_contract = load_json(FORGE_CONTRACT)
        bad_contract["promotion_requires"] = []
        if not validate_forge(bad_contract):
            failures.append("缺少提升条件的 Forge 合同没有失败")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_FORGE_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap Forge 与 redcap-arsenal 检查器")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("self-check").set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

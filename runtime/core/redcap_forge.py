#!/usr/bin/env python3
"""RedCap Forge and redcap-arsenal boundary checker."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FORGE_CONTRACT = REPO_ROOT / "assets" / "contracts" / "redcap-forge.json"
BOUNDARY_CONTRACT = REPO_ROOT / "assets" / "contracts" / "forge-private-boundary.json"
ARSENAL_DIR = REPO_ROOT / "assets" / "knowledge" / "arsenal"
ARSENAL_INDEX = ARSENAL_DIR / "index.json"
PROMOTION_LEDGER = ARSENAL_DIR / "promotion-ledger.jsonl"
LEDGER_SCHEMA_ID = "redcap-arsenal-promotion-ledger-entry"
BOUNDARY_REPORT_SCHEMA_ID = "redcap-forge-private-boundary-check"

LEGACY_FORBIDDEN_PRIVATE_MARKERS = [
    "/.cap",
    ".cap/identity",
    "assets/evidence/prism/",
    ".raw.json",
    "raw provider",
    "secret",
    "token",
]


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取 JSON：{path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON 必须是对象：{path}")
    return payload


def load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise SystemExit(f"无法读取 JSONL：{path}: {exc}") from exc
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"JSONL 第 {index} 行无法解析：{path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise SystemExit(f"JSONL 第 {index} 行必须是对象：{path}")
        rows.append(payload)
    return rows


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: pathlib.Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def rel_exists(path: str) -> bool:
    return (REPO_ROOT / path).exists()


def path_under(path: pathlib.Path, parent: pathlib.Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def text_has_legacy_private_marker(value: str) -> bool:
    lowered = value.casefold()
    return any(marker.casefold() in lowered for marker in LEGACY_FORBIDDEN_PRIVATE_MARKERS)


def private_patterns(contract: dict[str, Any]) -> list[dict[str, str]]:
    patterns = contract.get("private_patterns")
    if not isinstance(patterns, list):
        return []
    result: list[dict[str, str]] = []
    for pattern in patterns:
        if not isinstance(pattern, dict):
            continue
        pattern_id = pattern.get("id")
        regex = pattern.get("regex")
        if isinstance(pattern_id, str) and pattern_id and isinstance(regex, str) and regex:
            result.append({"id": pattern_id, "regex": regex})
    return result


def private_pattern_hits(text: str, patterns: list[dict[str, str]]) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        try:
            if re.search(pattern["regex"], text, flags=re.IGNORECASE | re.MULTILINE):
                hits.append(pattern["id"])
        except re.error:
            hits.append(f"{pattern['id']}:invalid-regex")
    return hits


def load_contracts() -> tuple[dict[str, Any], dict[str, Any]]:
    return load_json(FORGE_CONTRACT), load_json(BOUNDARY_CONTRACT)


def validate_boundary_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-forge-private-boundary-contract":
        failures.append("Forge 边界合同 schema_id 错误")
    if contract.get("ledger") != "assets/knowledge/arsenal/promotion-ledger.jsonl":
        failures.append("Forge 边界合同必须指向 promotion-ledger.jsonl")
    if contract.get("boundary_check_command") != "runtime/bin/redcap forge boundary-check":
        failures.append("Forge 边界合同必须定义 boundary-check 命令")
    patterns = private_patterns(contract)
    if len(patterns) < 5:
        failures.append("Forge 边界合同 private_patterns 覆盖不足")
    invalid = [pattern["id"] for pattern in patterns if private_pattern_hits("", [pattern]) and "invalid-regex" in private_pattern_hits("", [pattern])[0]]
    if invalid:
        failures.append(f"Forge 边界合同含非法 regex：{invalid}")
    required = set(contract.get("promotion_requires", []))
    for item in ["content_sha256", "index_entry_sha256", "hash_chain", "privacy_scan_passed", "dedupe_key", "review_artifact"]:
        if item not in required:
            failures.append(f"Forge 边界合同 promotion_requires 缺失：{item}")
    return failures


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


def validate_entry_body(entry: dict[str, Any], label: str, patterns: list[dict[str, str]]) -> list[str]:
    failures: list[str] = []
    body = entry.get("body")
    if not isinstance(body, str) or not body.strip():
        return [f"{label}.body 不能为空"]
    body_path = (REPO_ROOT / body).resolve()
    if pathlib.Path(body).is_absolute() or not path_under(body_path, ARSENAL_DIR):
        failures.append(f"{label}.body 必须位于 assets/knowledge/arsenal/：{body}")
        return failures
    if not body_path.is_file():
        failures.append(f"{label}.body 文件不存在：{body}")
        return failures
    try:
        text = body_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        failures.append(f"{label}.body 无法读取为 UTF-8 文本：{body}: {exc}")
        return failures
    if len(text.strip()) < 20:
        failures.append(f"{label}.body 可读内容过短")
    hits = private_pattern_hits(text, patterns)
    if hits:
        failures.append(f"{label}.body 命中私密模式：{hits}")
    return failures


def validate_arsenal(index: dict[str, Any], boundary: dict[str, Any] | None = None) -> list[str]:
    failures: list[str] = []
    patterns = private_patterns(boundary or {})
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
    seen_ids: set[str] = set()
    seen_dedupe: set[str] = set()
    for idx, entry in enumerate(entries, start=1):
        label = f"entries[{idx}]"
        if not isinstance(entry, dict):
            failures.append(f"{label} 必须是对象")
            continue
        entry_id = str(entry.get("id") or "")
        if not entry_id:
            failures.append(f"{label}.id 不能为空")
        elif entry_id in seen_ids:
            failures.append(f"arsenal 条目重复：{entry_id}")
        seen_ids.add(entry_id)
        if entry.get("status") != "promoted":
            failures.append(f"{label}.status 必须是 promoted")
        for key in ["title", "summary", "body"]:
            if not isinstance(entry.get(key), str) or not entry.get(key, "").strip():
                failures.append(f"{label}.{key} 不能为空")
        dedupe_key = sha256_text("|".join([
            str(entry.get("title") or "").casefold().strip(),
            str(entry.get("summary") or "").casefold().strip(),
            ",".join(sorted(str(tag).casefold() for tag in entry.get("tags", []) if isinstance(tag, str))),
        ]))
        if dedupe_key in seen_dedupe:
            failures.append(f"{label} 与其他条目疑似重复")
        seen_dedupe.add(dedupe_key)
        failures.extend(validate_entry_body(entry, label, patterns))
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
                elif text_has_legacy_private_marker(ref) or private_pattern_hits(ref, patterns):
                    failures.append(f"{label}.source_refs 含私密、凭据或原始输出路径：{ref}")
                elif not rel_exists(ref):
                    failures.append(f"{label}.source_refs 不存在：{ref}")
        searchable = canonical_json(entry)
        if text_has_legacy_private_marker(searchable):
            failures.append(f"{label} 含私密或原始输出标记")
        hits = private_pattern_hits(searchable, patterns)
        if hits:
            failures.append(f"{label} 元数据命中私密模式：{hits}")
    return failures


def ledger_entry_hash(entry: dict[str, Any]) -> str:
    payload = dict(entry)
    payload.pop("entry_hash", None)
    return sha256_text(canonical_json(payload))


def validate_ledger(index: dict[str, Any], boundary: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    patterns = private_patterns(boundary)
    if not PROMOTION_LEDGER.is_file():
        return ["promotion-ledger.jsonl 不存在"]
    rows = load_jsonl(PROMOTION_LEDGER)
    if not rows:
        return ["promotion-ledger.jsonl 不能为空"]
    entries = index.get("entries") if isinstance(index.get("entries"), list) else []
    index_by_id = {entry.get("id"): entry for entry in entries if isinstance(entry, dict)}
    ledger_by_id: dict[str, dict[str, Any]] = {}
    previous_hash: str | None = None
    for line_no, row in enumerate(rows, start=1):
        label = f"ledger[{line_no}]"
        if row.get("schema_id") != LEDGER_SCHEMA_ID:
            failures.append(f"{label}.schema_id 错误")
        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id:
            failures.append(f"{label}.id 不能为空")
            continue
        if row_id in ledger_by_id:
            failures.append(f"{label}.id 重复：{row_id}")
        ledger_by_id[row_id] = row
        if row.get("promotion_decision") != "promoted":
            failures.append(f"{label}.promotion_decision 必须为 promoted")
        if row.get("privacy_review") != "checked":
            failures.append(f"{label}.privacy_review 必须为 checked")
        if row.get("previous_entry_hash") != previous_hash:
            failures.append(f"{label}.previous_entry_hash 不匹配")
        expected_entry_hash = ledger_entry_hash(row)
        if row.get("entry_hash") != expected_entry_hash:
            failures.append(f"{label}.entry_hash 不匹配")
        previous_hash = str(row.get("entry_hash") or "")
        serialized = canonical_json(row)
        if text_has_legacy_private_marker(serialized):
            failures.append(f"{label} 含私密或原始输出标记")
        hits = private_pattern_hits(serialized, patterns)
        if hits:
            failures.append(f"{label} 命中私密模式：{hits}")
        entry = index_by_id.get(row_id)
        if not isinstance(entry, dict):
            failures.append(f"{label}.id 未出现在 arsenal index：{row_id}")
            continue
        body = entry.get("body")
        if not isinstance(body, str):
            failures.append(f"{label} 对应 entry.body 无效")
            continue
        body_path = (REPO_ROOT / body).resolve()
        if body_path.is_file() and row.get("body_sha256") != sha256_file(body_path):
            failures.append(f"{label}.body_sha256 与正文文件不一致")
        if row.get("index_entry_sha256") != sha256_text(canonical_json(entry)):
            failures.append(f"{label}.index_entry_sha256 与索引条目不一致")
        if row.get("body") != body:
            failures.append(f"{label}.body 与索引条目不一致")
        review_artifact = row.get("review_artifact")
        if not isinstance(review_artifact, str) or not review_artifact or not rel_exists(review_artifact):
            failures.append(f"{label}.review_artifact 必须指向存在的评审或合同依据")
    missing = sorted(str(entry_id) for entry_id in index_by_id if entry_id not in ledger_by_id)
    if missing:
        failures.append(f"promotion ledger 缺少条目：{missing}")
    return failures


def git_recent_message_scan(patterns: list[dict[str, str]]) -> dict[str, Any]:
    import subprocess

    completed = subprocess.run(
        ["git", "log", "-n", "50", "--format=%B", "--", "assets/knowledge/arsenal"],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    text = completed.stdout if completed.returncode == 0 else ""
    hits = private_pattern_hits(text, patterns)
    return {
        "ok": completed.returncode == 0 and not hits,
        "exit_code": completed.returncode,
        "scanned_recent_commit_messages": completed.returncode == 0,
        "scope": "last 50 commit messages touching assets/knowledge/arsenal",
        "hit_pattern_ids": hits,
        "stderr_tail": completed.stderr[-1000:],
    }


def check_boundary() -> dict[str, Any]:
    forge, boundary = load_contracts()
    index = load_json(ARSENAL_INDEX)
    patterns = private_patterns(boundary)
    failures: list[str] = []
    failures.extend(validate_forge(forge))
    failures.extend(validate_boundary_contract(boundary))
    failures.extend(validate_arsenal(index, boundary))
    failures.extend(validate_ledger(index, boundary))
    git_scan = git_recent_message_scan(patterns)
    if not git_scan["ok"]:
        failures.append("arsenal 近 50 条相关提交信息扫描未通过")
    entries = index.get("entries") if isinstance(index.get("entries"), list) else []
    positive_ok = (
        not validate_forge(forge)
        and not validate_boundary_contract(boundary)
        and not validate_arsenal(index, boundary)
        and not validate_ledger(index, boundary)
        and git_scan["ok"]
    )
    negative_probes = self_check_negative_probes(boundary, index)
    negative_ok = negative_probes["ok"]
    return {
        "schema_id": BOUNDARY_REPORT_SCHEMA_ID,
        "rsp": "RSP-15",
        "ok": not failures,
        "changed_reality": [
            "Forge 边界检查从索引元数据检查升级为正文内容、来源引用、晋升账本和提交信息共同检查。",
            "redcap-arsenal promoted 条目必须具备 promotion ledger 记录，且 ledger 绑定正文哈希、索引条目哈希和哈希链。",
            "runtime/bin/redcap forge boundary-check 已成为可执行边界检查入口，并接入聚合检查。"
        ],
        "acceptance": {
            "positive": {
                "status": "pass" if positive_ok else "fail",
                "checks": [
                    "Forge 合同、边界合同、arsenal index、正文文件、promotion ledger 和最近相关提交信息均通过检查。",
                    "每个 promoted 条目都有 ledger 记录，且 body_sha256、index_entry_sha256、entry_hash 与当前内容一致。"
                ]
            },
            "negative": {
                "status": "pass" if negative_ok else "fail",
                "checks": negative_probes["checks"],
                "failures": negative_probes["failures"]
            }
        },
        "artifacts": [
            "assets/contracts/forge-private-boundary.json",
            "assets/knowledge/arsenal/promotion-ledger.jsonl",
            "runtime/core/redcap_forge.py",
            "runtime/bin/redcap forge boundary-check",
            "runtime/core/check_runner.py"
        ],
        "forge_contract": rel(FORGE_CONTRACT),
        "boundary_contract": rel(BOUNDARY_CONTRACT),
        "arsenal_index": rel(ARSENAL_INDEX),
        "promotion_ledger": rel(PROMOTION_LEDGER),
        "arsenal_entries": len(entries),
        "private_pattern_ids": [pattern["id"] for pattern in patterns],
        "git_recent_message_scan": git_scan,
        "failures": failures,
    }


def check() -> dict[str, Any]:
    return check_boundary()


def self_check_negative_probes(boundary: dict[str, Any], index: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    checks: list[str] = []
    entries = index.get("entries") if isinstance(index.get("entries"), list) else []
    if not entries:
        return {"ok": False, "checks": checks, "failures": ["缺少 arsenal 条目，无法执行负向样本"]}
    body_outside = json.loads(json.dumps(index, ensure_ascii=False))
    body_outside["entries"][0]["body"] = "assets/docs/residual-todo-final-solution-plan.md"
    checks.append("正文位于 arsenal 外必须失败")
    if not any(".body 必须位于" in item for item in validate_arsenal(body_outside, boundary)):
        failures.append("正文位于 arsenal 外的负向样本没有失败")
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        suffix=".md",
        prefix=".redcap-forge-self-check-",
        dir=ARSENAL_DIR,
        delete=False,
    ) as handle:
        temp_path = pathlib.Path(handle.name)
        handle.write("私有身份样例\npassword = should-not-promote\n")
    try:
        private_body = json.loads(json.dumps(index, ensure_ascii=False))
        private_body["entries"][0]["body"] = rel(temp_path)
        checks.append("正文含凭据模式必须失败")
        if not any("命中私密模式" in item for item in validate_arsenal(private_body, boundary)):
            failures.append("正文含凭据的负向样本没有失败")
    finally:
        temp_path.unlink(missing_ok=True)
    tampered_rows = load_jsonl(PROMOTION_LEDGER)
    if tampered_rows:
        tampered_rows[0]["body_sha256"] = "0" * 64
        original_loader = globals()["load_jsonl"]
        try:
            globals()["load_jsonl"] = lambda _: tampered_rows
            checks.append("ledger 哈希篡改必须失败")
            if not any("body_sha256" in item for item in validate_ledger(index, boundary)):
                failures.append("ledger 哈希篡改负向样本没有失败")
        finally:
            globals()["load_jsonl"] = original_loader
    return {"ok": not failures, "checks": checks, "failures": failures}


def cmd_check(args: argparse.Namespace) -> int:
    result = check_boundary()
    if args.out:
        write_json(pathlib.Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if result["ok"]:
        print("REDCAP_FORGE_BOUNDARY_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    result = check_boundary()
    if not result["ok"]:
        failures.append(f"真实 Forge 边界检查不应失败：{result['failures']}")
    _, boundary = load_contracts()
    index = load_json(ARSENAL_INDEX)
    negative = self_check_negative_probes(boundary, index)
    failures.extend(negative["failures"])
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2, sort_keys=True))
    if failures:
        return 1
    print("REDCAP_FORGE_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap Forge 与 redcap-arsenal 检查器")
    sub = parser.add_subparsers(dest="command", required=True)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--out")
    check_parser.set_defaults(func=cmd_check)
    boundary_parser = sub.add_parser("boundary-check")
    boundary_parser.add_argument("--out")
    boundary_parser.set_defaults(func=cmd_check)
    sub.add_parser("self-check").set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

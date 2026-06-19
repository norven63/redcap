#!/usr/bin/env python3
"""独立复核 E2E 负向合同探针回归证据。"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
import sys
from typing import Any


REQUIRED_GLOBALS = {
    "TRPG_SEED_DATA",
    "REDCAP_DATA",
    "PROJECT_DATA",
    "ACTIVITY_DATA",
    "SAMPLE_DATA",
    "APP_DATA",
}

SETUP_ERROR_MARKERS = [
    "data not set",
    "did not set window",
    "syntaxerror",
    "unexpected token",
    "js data file did not expose structured data",
]

EXPECTED_CONTRACTS = {
    "signup_probe": "signup-intent-data-contract",
    "character_probe": "character-player-relation-contract",
}

DEFAULT_REQUIRED_ALIAS_COVERAGE = {
    "SIGNUP_COLLECTION_FIELD_CANDIDATES": [
        "signups",
        "registrations",
        "enrollments",
        "applications",
        "participants",
    ],
    "SIGNUP_INTENT_FIELD_CANDIDATES": [
        "signupIntent",
        "registrationIntent",
        "enrollmentIntent",
        "applicationIntent",
        "participationIntent",
    ],
    "RELATION_PARENT_LIST_KEYS": [
        "players",
        "participants",
        "attendees",
        "users",
        "members",
    ],
    "RELATION_CHILD_LIST_KEYS": [
        "characters",
        "assignments",
        "reservations",
        "submissions",
        "allocations",
    ],
    "RELATION_REFERENCE_KEYS": [
        "playerId",
        "player_id",
        "participantId",
        "participant_id",
        "attendeeId",
        "attendee_id",
        "userId",
        "user_id",
        "memberId",
        "member_id",
    ],
}

PATH_PART_RE = re.compile(r"^([^\[\]]+)?(?:\[(-?\d+)\])?$")


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command_text(receipt: dict[str, Any]) -> str:
    return "\n".join(str(receipt.get(key) or "") for key in ("stdout_tail", "stderr_tail")).casefold()


def text_points_to_contract(text: str, expected_contract: str) -> bool:
    folded = text.casefold()
    if not folded or any(marker in folded for marker in SETUP_ERROR_MARKERS):
        return False
    return expected_contract.casefold() in folded


def summarize_value(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return {"type": "string", "length": len(value), "sample": value[:80]}
    if isinstance(value, list):
        return {"type": "list", "length": len(value)}
    if isinstance(value, dict):
        return {"type": "dict", "keys": sorted(str(key) for key in value.keys())[:12]}
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, (int, float)):
        return {"type": "number", "value": value}
    return {"type": type(value).__name__, "sample": str(value)[:80]}


def summary_matches(actual: dict[str, Any], expected: Any) -> bool:
    if not isinstance(expected, dict):
        return True
    for key in ["type", "length", "sample", "value"]:
        if key in expected and actual.get(key) != expected.get(key):
            return False
    return True


def load_structured_payload(path: pathlib.Path, expected_global: str | None = None) -> Any:
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix != ".js":
        raise ValueError(f"不支持的数据文件类型：{path.suffix}")
    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const file = process.argv[1];
const expected = process.argv[2] || "";
const code = fs.readFileSync(file, 'utf8');
const sandbox = { window: {}, self: null, globalThis: null, console: { log() {} } };
sandbox.self = sandbox.window;
sandbox.globalThis = sandbox.window;
vm.createContext(sandbox);
vm.runInContext(code, sandbox, { filename: file, timeout: 1000 });
const keys = Object.keys(sandbox.window);
const key = expected && Object.prototype.hasOwnProperty.call(sandbox.window, expected)
  ? expected
  : keys[0];
if (!key) {
  console.error("no window data global found");
  process.exit(2);
}
process.stdout.write(JSON.stringify({ global_name: key, payload: sandbox.window[key] }));
"""
    completed = subprocess.run(
        ["node", "-e", node_script, str(path), expected_global or ""],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        raise ValueError((completed.stderr or completed.stdout or "node 读取 JS 数据失败").strip())
    decoded = json.loads(completed.stdout)
    return decoded["payload"]


def write_structured_payload(path: pathlib.Path, payload: Any, global_name: str | None = None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if path.suffix == ".json":
        path.write_text(text + "\n", encoding="utf-8")
        return
    if path.suffix == ".js":
        name = global_name or "APP_DATA"
        path.write_text(f"window.{name} = {text};\n", encoding="utf-8")
        return
    raise ValueError(f"不支持写回的数据文件类型：{path.suffix}")


def run_receipt(argv: list[str], cwd: pathlib.Path, timeout: int = 120) -> dict[str, Any]:
    completed = subprocess.run(
        argv,
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "argv": argv,
        "cwd": str(cwd),
        "exit_code": completed.returncode,
        "stdout_tail": (completed.stdout or "")[-1000:],
        "stderr_tail": (completed.stderr or "")[-1000:],
        "ok": completed.returncode == 0,
    }


def path_tokens(target_path: str) -> list[tuple[str, str | int]]:
    if target_path == "__top_level__":
        return []
    tokens: list[tuple[str, str | int]] = []
    for raw_part in target_path.split("."):
        if raw_part in ("", "__top_level__"):
            continue
        if raw_part.lstrip("-").isdigit():
            tokens.append(("index", int(raw_part)))
            continue
        match = PATH_PART_RE.match(raw_part)
        if not match:
            raise ValueError(f"无法解析 target_path 片段：{raw_part}")
        key, index = match.groups()
        if key and key != "$":
            tokens.append(("key", key))
        if index is not None:
            tokens.append(("index", int(index)))
    return tokens


def resolve_tokens(payload: Any, tokens: list[tuple[str, str | int]]) -> tuple[bool, Any]:
    current = payload
    for kind, value in tokens:
        if kind == "key":
            if not isinstance(current, dict) or value not in current:
                return False, None
            current = current[value]
        elif kind == "index":
            if not isinstance(current, list) or not isinstance(value, int) or value < 0 or value >= len(current):
                return False, None
            current = current[value]
    return True, current


def target_path_check(work_root: pathlib.Path, case: dict[str, Any], probe_key: str, probe: dict[str, Any]) -> dict[str, Any]:
    case_id = str(case.get("id") or "<missing-case-id>")
    mutation = probe.get("mutation") if isinstance(probe, dict) else None
    if not isinstance(mutation, dict):
        return {"case_id": case_id, "probe_key": probe_key, "ok": False, "error": "mutation missing"}
    data_path_value = case.get("data_path") or mutation.get("data_path")
    target_path = mutation.get("target_path")
    if not isinstance(data_path_value, str) or not isinstance(target_path, str):
        return {"case_id": case_id, "probe_key": probe_key, "ok": False, "error": "data_path or target_path missing"}
    project = work_root / case_id
    data_path = project / data_path_value
    summary: dict[str, Any] = {
        "case_id": case_id,
        "probe_key": probe_key,
        "data_path": data_path_value,
        "target_path": target_path,
    }
    try:
        original_payload = load_structured_payload(data_path, str(case.get("global_name") or ""))
        tokens = path_tokens(target_path)
        exists, original_value = resolve_tokens(original_payload, tokens)
        summary["original_target_exists"] = exists
        if not exists:
            summary["ok"] = False
            return summary
        failures: list[str] = []
        if probe_key == "signup_probe":
            changed_fields = mutation.get("changed_fields")
            before = mutation.get("before")
            if not isinstance(original_value, dict):
                failures.append("报名探针 target_path 未指向对象")
            elif not isinstance(changed_fields, list) or not changed_fields:
                failures.append("报名探针缺少 changed_fields")
            else:
                field_checks = []
                for field in changed_fields:
                    field_name = str(field)
                    field_exists = field_name in original_value
                    field_summary = summarize_value(original_value.get(field_name)) if field_exists else None
                    field_ok = field_exists and summary_matches(field_summary or {}, before.get(field_name) if isinstance(before, dict) else None)
                    field_checks.append({
                        "field": field_name,
                        "exists_in_original": field_exists,
                        "before_summary_matches": field_ok,
                        "original_summary": field_summary,
                    })
                    if not field_ok:
                        failures.append(f"报名探针原始字段校验失败：{field_name}")
                summary["field_checks"] = field_checks
        else:
            before_summary = summarize_value(original_value)
            summary["original_value_summary"] = before_summary
            if not summary_matches(before_summary, mutation.get("before")):
                failures.append("关系探针原始 target_path 值与 before 摘要不一致")
        snapshot = mutation.get("mutated_snapshot")
        if isinstance(snapshot, dict) and isinstance(snapshot.get("path"), str):
            snapshot_payload = load_structured_payload(project / str(snapshot["path"]), str(case.get("global_name") or ""))
            snapshot_exists, snapshot_value = resolve_tokens(snapshot_payload, tokens)
            summary["snapshot_target_exists"] = snapshot_exists
            if not snapshot_exists:
                failures.append("mutation 快照缺少 target_path")
            elif probe_key == "signup_probe":
                after = mutation.get("after")
                snapshot_field_checks = []
                if isinstance(snapshot_value, dict) and isinstance(after, dict):
                    for field, expected_summary in after.items():
                        field_exists = field in snapshot_value
                        field_summary = summarize_value(snapshot_value.get(field)) if field_exists else None
                        field_ok = field_exists and summary_matches(field_summary or {}, expected_summary)
                        snapshot_field_checks.append({
                            "field": field,
                            "exists_in_snapshot": field_exists,
                            "after_summary_matches": field_ok,
                            "snapshot_summary": field_summary,
                        })
                        if not field_ok:
                            failures.append(f"报名探针快照字段校验失败：{field}")
                else:
                    failures.append("报名探针快照 target_path 未指向对象或缺少 after 摘要")
                summary["snapshot_field_checks"] = snapshot_field_checks
            else:
                snapshot_summary = summarize_value(snapshot_value)
                summary["snapshot_value_summary"] = snapshot_summary
                if not summary_matches(snapshot_summary, mutation.get("after")):
                    failures.append("关系探针快照 target_path 值与 after 摘要不一致")
        else:
            failures.append("缺少 mutation 快照，不能检查变更后目标路径")
        summary["failures"] = failures
        summary["ok"] = not failures
        return summary
    except Exception as exc:
        summary["ok"] = False
        summary["error"] = str(exc)
        return summary


def required_alias_coverage(contract: dict[str, Any] | None) -> dict[str, list[str]]:
    if isinstance(contract, dict):
        section = contract.get("negative_probe_alias_coverage")
        if isinstance(section, dict):
            aliases = section.get("required_aliases")
            if isinstance(aliases, dict):
                return {
                    str(key): [str(item) for item in value]
                    for key, value in aliases.items()
                    if isinstance(value, list)
                }
    return DEFAULT_REQUIRED_ALIAS_COVERAGE


def alias_coverage_check(alias_constants: dict[str, Any], contract: dict[str, Any] | None) -> dict[str, Any]:
    required = required_alias_coverage(contract)
    checks: dict[str, Any] = {}
    failures: list[str] = []
    for key, required_values in required.items():
        actual_values = alias_constants.get(key)
        actual_set = {str(item) for item in actual_values} if isinstance(actual_values, list) else set()
        missing = sorted(set(required_values) - actual_set)
        checks[key] = {
            "required": required_values,
            "actual": sorted(actual_set),
            "missing": missing,
            "ok": not missing,
        }
        if missing:
            failures.append(f"{key} 缺少合同要求别名：{missing}")
    return {"ok": not failures, "checks": checks, "failures": failures}


def setup_error_control_check(regression: dict[str, Any]) -> dict[str, Any]:
    control = regression.get("setup_error_control")
    if not isinstance(control, dict):
        return {"ok": False, "failures": ["回归结果缺少 setup_error_control"]}
    failures: list[str] = []
    negative = control.get("negative_command")
    if control.get("ok") is not True:
        failures.append("setup_error_control.ok 不是 true")
    syntax_check = control.get("syntax_check")
    if not isinstance(syntax_check, dict) or syntax_check.get("ok") is not False:
        failures.append("setup_error_control 未证明语法检查失败")
    if not isinstance(negative, dict) or negative.get("exit_code") in (0, None):
        failures.append("setup_error_control 未产生非零验证退出")
    else:
        text = command_text(negative)
        if text_points_to_contract(text, "signup-intent-data-contract"):
            failures.append("setup_error_control 被误判为报名合同失败")
        if text_points_to_contract(text, "character-player-relation-contract"):
            failures.append("setup_error_control 被误判为实体引用合同失败")
        if not any(marker in text for marker in SETUP_ERROR_MARKERS):
            failures.append("setup_error_control 输出未包含可识别 setup_error 标记")
    if control.get("signup_domain_failure_detected") is not False:
        failures.append("signup_domain_failure_detected 应为 false")
    if control.get("relation_domain_failure_detected") is not False:
        failures.append("relation_domain_failure_detected 应为 false")
    restore = control.get("restore_command")
    if not isinstance(restore, dict) or restore.get("exit_code") != 0:
        failures.append("setup_error_control 恢复原数据后验证未通过")
    return {
        "ok": not failures,
        "case_id": control.get("case_id"),
        "syntax_exit_code": syntax_check.get("receipt", {}).get("exit_code") if isinstance(syntax_check, dict) else None,
        "negative_exit_code": negative.get("exit_code") if isinstance(negative, dict) else None,
        "restore_exit_code": restore.get("exit_code") if isinstance(restore, dict) else None,
        "signup_domain_failure_detected": control.get("signup_domain_failure_detected"),
        "relation_domain_failure_detected": control.get("relation_domain_failure_detected"),
        "setup_marker_detected": control.get("setup_marker_detected"),
        "failures": failures,
    }


def list_candidates(payload: Any) -> list[tuple[str, list[Any]]]:
    if isinstance(payload, list):
        return [("$", payload)]
    if not isinstance(payload, dict):
        return []
    preferred = ["events", "activities", "campaigns", "sessions", "items"]
    candidates: list[tuple[str, list[Any]]] = []
    seen: set[str] = set()
    for key in preferred:
        value = payload.get(key)
        if isinstance(value, list):
            candidates.append((key, value))
            seen.add(key)
    for key, value in payload.items():
        if key not in seen and isinstance(value, list):
            candidates.append((str(key), value))
    return candidates


def independent_signup_candidate(payload: Any, aliases: dict[str, list[str]]) -> tuple[str, int, str, str] | None:
    collection_aliases = aliases["SIGNUP_COLLECTION_FIELD_CANDIDATES"]
    intent_aliases = aliases["SIGNUP_INTENT_FIELD_CANDIDATES"]
    matches: list[tuple[str, int, str, str]] = []
    for list_key, records in list_candidates(payload):
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            collection = next((field for field in collection_aliases if field in record), None)
            intent = next((field for field in intent_aliases if field in record), None)
            if collection and intent:
                matches.append((list_key, index, collection, intent))
    if not matches:
        return None
    return next((match for match in matches if match[1] > 0), matches[0])


def independent_relation_candidate(payload: Any, aliases: dict[str, list[str]]) -> tuple[str, int, str, int, str, str] | None:
    parent_aliases = aliases["RELATION_PARENT_LIST_KEYS"]
    child_aliases = aliases["RELATION_CHILD_LIST_KEYS"]
    ref_aliases = aliases["RELATION_REFERENCE_KEYS"]
    matches: list[tuple[str, int, str, int, str, str]] = []
    for list_key, records in list_candidates(payload):
        for event_index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            parent_sets: list[tuple[str, set[str]]] = []
            for parent_key in parent_aliases:
                parents = record.get(parent_key)
                if not isinstance(parents, list):
                    continue
                ids = {
                    str(parent.get(id_key))
                    for parent in parents
                    if isinstance(parent, dict)
                    for id_key in ["id", "uid", "name"]
                    if parent.get(id_key)
                }
                if ids:
                    parent_sets.append((parent_key, ids))
            if not parent_sets:
                continue
            for child_key in child_aliases:
                children = record.get(child_key)
                if not isinstance(children, list):
                    continue
                for child_index, child in enumerate(children):
                    if not isinstance(child, dict):
                        continue
                    for ref_key in ref_aliases:
                        ref_value = child.get(ref_key)
                        if not isinstance(ref_value, (str, int, float)) or not str(ref_value).strip():
                            continue
                        for parent_key, parent_ids in parent_sets:
                            if str(ref_value) in parent_ids:
                                matches.append((list_key, event_index, child_key, child_index, ref_key, parent_key))
    if not matches:
        return None
    return next((match for match in matches if match[1] > 0 or match[3] > 0), matches[0])


def mutate_at_path(payload: Any, target_path: str, mutator: Any) -> None:
    tokens = path_tokens(target_path)
    if not tokens:
        mutator(payload)
        return
    parent_tokens = tokens[:-1]
    leaf_kind, leaf_value = tokens[-1]
    exists, parent = resolve_tokens(payload, parent_tokens)
    if not exists:
        raise ValueError(f"无法解析父路径：{target_path}")
    if leaf_kind == "key":
        if not isinstance(parent, dict) or leaf_value not in parent:
            raise ValueError(f"无法解析字段：{target_path}")
        mutator(parent, leaf_value)
    elif leaf_kind == "index":
        if not isinstance(parent, list) or not isinstance(leaf_value, int) or leaf_value >= len(parent):
            raise ValueError(f"无法解析索引：{target_path}")
        mutator(parent, leaf_value)


def independent_reconstruction_check(work_root: pathlib.Path, case: dict[str, Any], contract: dict[str, Any] | None) -> list[dict[str, Any]]:
    case_id = str(case.get("id") or "<missing-case-id>")
    project = work_root / case_id
    data_path_value = str(case.get("data_path") or "")
    data_path = project / data_path_value
    global_name = str(case.get("global_name") or "")
    argv = case.get("positive_validation", {}).get("argv") if isinstance(case.get("positive_validation"), dict) else None
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        return [{
            "case_id": case_id,
            "probe_key": "independent_reconstruction",
            "ok": False,
            "error": "positive_validation.argv missing",
        }]
    aliases = required_alias_coverage(contract)
    checks: list[dict[str, Any]] = []
    original_bytes = data_path.read_bytes()

    def restore() -> None:
        data_path.write_bytes(original_bytes)

    try:
        payload = load_structured_payload(data_path, global_name)
        signup = independent_signup_candidate(payload, aliases)
        signup_summary: dict[str, Any] = {"case_id": case_id, "probe_key": "signup_probe"}
        if signup is None:
            signup_summary.update({"ok": False, "error": "未找到合同别名匹配的报名字段"})
        else:
            list_key, index, collection_field, intent_field = signup
            target_path = f"{list_key}[{index}]"
            def mutate_signup(parent: Any, leaf: Any) -> None:
                record = parent[leaf] if isinstance(parent, list) else parent
                record[collection_field] = []
                record[intent_field] = ""
            mutate_at_path(payload, target_path, mutate_signup)
            write_structured_payload(data_path, payload, global_name)
            syntax = run_receipt(["node", "--check", data_path_value], project, 30) if data_path.suffix == ".js" else {"exit_code": 0, "ok": True}
            negative = run_receipt([str(item) for item in argv], project)
            restore()
            positive = run_receipt([str(item) for item in argv], project)
            text = command_text(negative)
            signup_summary.update({
                "target_path": target_path,
                "changed_fields": [collection_field, intent_field],
                "syntax_exit_code": syntax.get("exit_code"),
                "negative_exit_code": negative.get("exit_code"),
                "restore_exit_code": positive.get("exit_code"),
                "contract_output_detected": text_points_to_contract(text, "signup-intent-data-contract"),
                "ok": syntax.get("exit_code") == 0
                    and negative.get("exit_code") not in (0, None)
                    and text_points_to_contract(text, "signup-intent-data-contract")
                    and positive.get("exit_code") == 0,
            })
        checks.append(signup_summary)
    except Exception as exc:
        restore()
        checks.append({"case_id": case_id, "probe_key": "signup_probe", "ok": False, "error": str(exc)})

    try:
        payload = load_structured_payload(data_path, global_name)
        relation = independent_relation_candidate(payload, aliases)
        relation_summary: dict[str, Any] = {"case_id": case_id, "probe_key": "character_probe"}
        if relation is None:
            relation_summary.update({"ok": False, "error": "未找到合同别名匹配的实体引用关系"})
        else:
            list_key, event_index, child_key, child_index, ref_key, parent_key = relation
            target_path = f"{list_key}[{event_index}].{child_key}[{child_index}].{ref_key}"
            def mutate_relation(parent: Any, leaf: Any) -> None:
                parent[leaf] = "__redcap_missing_reference__"
            mutate_at_path(payload, target_path, mutate_relation)
            write_structured_payload(data_path, payload, global_name)
            syntax = run_receipt(["node", "--check", data_path_value], project, 30) if data_path.suffix == ".js" else {"exit_code": 0, "ok": True}
            negative = run_receipt([str(item) for item in argv], project)
            restore()
            positive = run_receipt([str(item) for item in argv], project)
            text = command_text(negative)
            relation_summary.update({
                "target_path": target_path,
                "parent_key": parent_key,
                "relation_child_key": child_key,
                "reference_key": ref_key,
                "syntax_exit_code": syntax.get("exit_code"),
                "negative_exit_code": negative.get("exit_code"),
                "restore_exit_code": positive.get("exit_code"),
                "contract_output_detected": text_points_to_contract(text, "character-player-relation-contract"),
                "ok": syntax.get("exit_code") == 0
                    and negative.get("exit_code") not in (0, None)
                    and text_points_to_contract(text, "character-player-relation-contract")
                    and positive.get("exit_code") == 0,
            })
        checks.append(relation_summary)
    except Exception as exc:
        restore()
        checks.append({"case_id": case_id, "probe_key": "character_probe", "ok": False, "error": str(exc)})
    finally:
        restore()
    return checks


def mutation_has_required_shape(mutation: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if mutation.get("executor") != "runner_internal":
        failures.append("mutation.executor 不是 runner_internal")
    for key in ["target_path", "original_sha256", "mutated_sha256", "before", "after", "syntax_check"]:
        if key not in mutation:
            failures.append(f"mutation 缺少 {key}")
    snapshot = mutation.get("mutated_snapshot")
    if not isinstance(snapshot, dict) or not snapshot.get("path") or not snapshot.get("sha256"):
        failures.append("mutation 缺少 mutated_snapshot.path 或 mutated_snapshot.sha256")
    if mutation.get("original_sha256") == mutation.get("mutated_sha256"):
        failures.append("mutation 原始哈希与变更后哈希相同")
    syntax_check = mutation.get("syntax_check")
    if not isinstance(syntax_check, dict) or syntax_check.get("ok") is not True:
        failures.append("mutation.syntax_check 未通过")
    return failures


def validate_snapshot(project: pathlib.Path, mutation: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    snapshot = mutation.get("mutated_snapshot")
    if not isinstance(snapshot, dict):
        return ["mutation 缺少 mutated_snapshot"]
    raw_path = snapshot.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        return ["mutated_snapshot.path 缺失"]
    snapshot_path = (project / raw_path).resolve()
    try:
        snapshot_path.relative_to(project.resolve())
    except ValueError:
        return [f"mutated_snapshot.path 越过项目目录：{raw_path}"]
    if not snapshot_path.is_file():
        return [f"mutated_snapshot 文件不存在：{raw_path}"]
    actual_sha = sha256_file(snapshot_path)
    if actual_sha != snapshot.get("sha256") or actual_sha != mutation.get("mutated_sha256"):
        failures.append("mutated_snapshot 哈希与 mutation.mutated_sha256 不一致")
    if snapshot_path.suffix == ".js":
        completed = subprocess.run(
            ["node", "--check", str(snapshot_path)],
            cwd=str(project),
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            failures.append(f"mutated_snapshot node --check 失败：{(completed.stderr or completed.stdout).strip()}")
    elif snapshot_path.suffix == ".json":
        try:
            json.loads(snapshot_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"mutated_snapshot JSON 解析失败：{exc}")
    return failures


def snapshot_check_summary(project: pathlib.Path, mutation: dict[str, Any]) -> dict[str, Any]:
    snapshot = mutation.get("mutated_snapshot") if isinstance(mutation, dict) else None
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("path"), str):
        return {"ok": False, "error": "mutated_snapshot missing"}
    snapshot_path = (project / str(snapshot["path"])).resolve()
    summary: dict[str, Any] = {
        "path": str(snapshot.get("path")),
        "expected_sha256": snapshot.get("sha256"),
        "mutation_sha256": mutation.get("mutated_sha256"),
        "exists": snapshot_path.is_file(),
    }
    if not snapshot_path.is_file():
        summary["ok"] = False
        return summary
    actual_sha = sha256_file(snapshot_path)
    summary["actual_sha256"] = actual_sha
    summary["sha256_match"] = actual_sha == snapshot.get("sha256") == mutation.get("mutated_sha256")
    if snapshot_path.suffix == ".js":
        completed = subprocess.run(
            ["node", "--check", str(snapshot_path)],
            cwd=str(project),
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        summary["syntax_kind"] = "node-check"
        summary["syntax_exit_code"] = completed.returncode
        summary["syntax_stderr_tail"] = (completed.stderr or "")[-240:]
        summary["syntax_stdout_tail"] = (completed.stdout or "")[-240:]
        summary["syntax_ok"] = completed.returncode == 0
    elif snapshot_path.suffix == ".json":
        summary["syntax_kind"] = "json-parse"
        try:
            json.loads(snapshot_path.read_text(encoding="utf-8"))
            summary["syntax_ok"] = True
        except json.JSONDecodeError as exc:
            summary["syntax_ok"] = False
            summary["syntax_error"] = str(exc)
    summary["ok"] = bool(summary.get("sha256_match") and summary.get("syntax_ok", True))
    return summary


def probe_failures(work_root: pathlib.Path, case: dict[str, Any], probe_key: str, probe: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    case_id = str(case.get("id") or "<missing-case-id>")
    expected_contract = EXPECTED_CONTRACTS[probe_key]
    if probe.get("ok") is not True:
        failures.append(f"{case_id}.{probe_key} ok 不是 true")
    if probe.get("target_contract") != expected_contract:
        failures.append(f"{case_id}.{probe_key} target_contract 不是 {expected_contract}")
    if probe.get("contract_failure_detected") is not True:
        failures.append(f"{case_id}.{probe_key} 未记录领域合同失败")
    mutation = probe.get("mutation")
    if not isinstance(mutation, dict):
        failures.append(f"{case_id}.{probe_key} 缺少 mutation")
    else:
        failures.extend(f"{case_id}.{probe_key}: {item}" for item in mutation_has_required_shape(mutation))
        failures.extend(f"{case_id}.{probe_key}: {item}" for item in validate_snapshot(work_root / case_id, mutation))
    negative = probe.get("negative_command")
    if not isinstance(negative, dict):
        failures.append(f"{case_id}.{probe_key} 缺少 negative_command")
    else:
        if negative.get("exit_code") in (0, None):
            failures.append(f"{case_id}.{probe_key} negative_command 没有非零退出")
        text = command_text(negative)
        if expected_contract not in text:
            failures.append(f"{case_id}.{probe_key} 输出没有指向 {expected_contract}")
        if any(marker in text for marker in SETUP_ERROR_MARKERS):
            failures.append(f"{case_id}.{probe_key} 输出疑似 setup_error：{text[-180:]}")
    restore = probe.get("restore_command")
    if not isinstance(restore, dict) or restore.get("exit_code") != 0:
        failures.append(f"{case_id}.{probe_key} 恢复原数据后验证未通过")
    return failures


def audit_regression(
    work_root: pathlib.Path,
    regression: dict[str, Any],
    focused_audit: dict[str, Any],
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failures: list[str] = []
    snapshot_checks: list[dict[str, Any]] = []
    target_path_checks: list[dict[str, Any]] = []
    independent_reconstruction_checks: list[dict[str, Any]] = []
    setup_error_control = setup_error_control_check(regression)
    if setup_error_control.get("ok") is not True:
        failures.extend(setup_error_control.get("failures") or ["setup_error_control 未通过"])
    cases = regression.get("cases")
    if not isinstance(cases, list) or not cases:
        failures.append("回归结果缺少 cases")
        cases = []
    globals_seen = {str(case.get("global_name")) for case in cases if isinstance(case, dict)}
    missing_globals = sorted(REQUIRED_GLOBALS - globals_seen)
    if missing_globals:
        failures.append(f"全局名覆盖缺失：{missing_globals}")
    for case in cases:
        if not isinstance(case, dict):
            failures.append("case 不是 JSON 对象")
            continue
        case_id = str(case.get("id") or "<missing-case-id>")
        positive = case.get("positive_validation")
        if not isinstance(positive, dict) or positive.get("exit_code") != 0:
            failures.append(f"{case_id} 正向验证未通过")
        reconstruction = independent_reconstruction_check(work_root, case, contract)
        independent_reconstruction_checks.extend(reconstruction)
        for item in reconstruction:
            if item.get("ok") is not True:
                failures.append(f"{case_id}.{item.get('probe_key')} 独立重构负向探针失败：{item.get('error') or item}")
        for probe_key in EXPECTED_CONTRACTS:
            probe = case.get(probe_key)
            if not isinstance(probe, dict):
                failures.append(f"{case_id} 缺少 {probe_key}")
                continue
            failures.extend(probe_failures(work_root, case, probe_key, probe))
            target_check = target_path_check(work_root, case, probe_key, probe)
            target_path_checks.append(target_check)
            if target_check.get("ok") is not True:
                failures.append(f"{case_id}.{probe_key} target_path 独立校验失败：{target_check.get('failures') or target_check.get('error')}")
            mutation = probe.get("mutation")
            if isinstance(mutation, dict):
                summary = snapshot_check_summary(work_root / case_id, mutation)
                summary["case_id"] = case_id
                summary["probe_key"] = probe_key
                snapshot_checks.append(summary)
    alias_constants = focused_audit.get("alias_constants")
    if not isinstance(alias_constants, dict):
        failures.append("聚焦审计缺少 alias_constants")
        alias_coverage = {"ok": False, "checks": {}, "failures": ["聚焦审计缺少 alias_constants"]}
    else:
        for key in [
            "SIGNUP_COLLECTION_FIELD_CANDIDATES",
            "SIGNUP_INTENT_FIELD_CANDIDATES",
            "RELATION_PARENT_LIST_KEYS",
            "RELATION_CHILD_LIST_KEYS",
            "RELATION_REFERENCE_KEYS",
        ]:
            value = alias_constants.get(key)
            if not isinstance(value, list) or not value:
                failures.append(f"alias_constants.{key} 缺失或为空")
        alias_coverage = alias_coverage_check(alias_constants, contract)
        failures.extend(alias_coverage["failures"])
    function_sources = focused_audit.get("function_sources")
    if not isinstance(function_sources, dict):
        failures.append("聚焦审计缺少 function_sources")
    else:
        for key in [
            "domain_failure_detected",
            "run_runner_negative_contract_probe",
            "run_runner_character_player_contract_probe",
            "append_relation_matches",
        ]:
            item = function_sources.get(key)
            if not isinstance(item, dict) or not item.get("sha256") or not item.get("source"):
                failures.append(f"function_sources.{key} 缺少源码片段或哈希")
    return {
        "schema_id": "redcap-e2e-negative-probe-external-audit",
        "created_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "ok": not failures,
        "required_globals": sorted(REQUIRED_GLOBALS),
        "globals_seen": sorted(globals_seen),
        "case_count": len(cases),
        "snapshot_check_count": len(snapshot_checks),
        "snapshot_checks": snapshot_checks,
        "target_path_check_count": len(target_path_checks),
        "target_path_checks": target_path_checks,
        "independent_reconstruction_check_count": len(independent_reconstruction_checks),
        "independent_reconstruction_checks": independent_reconstruction_checks,
        "setup_error_control": setup_error_control,
        "alias_coverage": alias_coverage,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="独立复核 E2E 负向合同探针回归证据")
    parser.add_argument("--regression-result", required=True)
    parser.add_argument("--focused-audit", required=True)
    parser.add_argument("--contract")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    regression_path = pathlib.Path(args.regression_result).expanduser().resolve()
    focused_audit_path = pathlib.Path(args.focused_audit).expanduser().resolve()
    out_path = pathlib.Path(args.out).expanduser().resolve()
    regression = load_json(regression_path)
    focused_audit = load_json(focused_audit_path)
    contract = load_json(pathlib.Path(args.contract).expanduser().resolve()) if args.contract else None
    work_root_value = regression.get("work_root") if isinstance(regression, dict) else None
    work_root = pathlib.Path(str(work_root_value)).expanduser().resolve() if work_root_value else regression_path.parent
    result = audit_regression(work_root, regression, focused_audit, contract)
    result["inputs"] = {
        "regression_result": str(regression_path),
        "regression_result_sha256": sha256_file(regression_path),
        "focused_audit": str(focused_audit_path),
        "focused_audit_sha256": sha256_file(focused_audit_path),
        "contract": str(pathlib.Path(args.contract).expanduser().resolve()) if args.contract else None,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok") is True:
        print("REDCAP_E2E_NEGATIVE_PROBE_EXTERNAL_AUDIT_OK")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

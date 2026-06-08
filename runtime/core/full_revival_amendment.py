#!/usr/bin/env python3
"""完整复活口径修正检查器。"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = REPO_ROOT / "assets" / "contracts" / "full-revival-amendment.json"
DEFAULT_MERGE = REPO_ROOT / "assets" / "archaeology" / "shards" / "old-redcap-360-scan-merge.json"


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def portable_ids(payload: dict[str, Any]) -> set[str]:
    return {
        str(item.get("id"))
        for item in payload.get("portable_designs", [])
        if isinstance(item, dict) and item.get("id")
    }


def validate_contract(contract: dict[str, Any], scan_merge: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-full-revival-amendment":
        failures.append("完整复活修正合同 schema_id 错误")
    if contract.get("posture") != "complete_workflow_machine_required":
        failures.append("完整复活姿态必须要求完整工作流机器")
    if contract.get("minimum_kernel_completion_allowed") is not False:
        failures.append("最小内核不能被允许作为完整复活完成依据")
    rules = contract.get("rules")
    if not isinstance(rules, list) or len(rules) < 4:
        failures.append("完整复活修正合同缺少足够规则")
    required_designs = contract.get("required_designs")
    if not isinstance(required_designs, list) or not required_designs:
        failures.append("完整复活修正合同缺少机器可枚举设计清单")
        required_designs = []
    contract_ids = {
        str(item.get("id"))
        for item in required_designs
        if isinstance(item, dict) and item.get("id")
    }
    scan_ids = portable_ids(scan_merge)
    missing = sorted(scan_ids - contract_ids)
    extra = sorted(contract_ids - scan_ids)
    if missing:
        failures.append(f"完整复活清单缺少扫描出的优秀设计：{missing}")
    if extra:
        failures.append(f"完整复活清单包含未在扫描中确认的设计：{extra}")
    for item in required_designs:
        if not isinstance(item, dict):
            failures.append("完整复活设计条目必须是对象")
            continue
        if item.get("full_revival_required") is not True:
            failures.append(f"{item.get('id')}: full_revival_required 必须为 true")
        for key in ["id", "name", "required_as"]:
            if not (isinstance(item.get(key), str) and item[key].strip()):
                failures.append(f"{item.get('id')}: {key} 必须是非空字符串")
    reopened = contract.get("reopened_design_decisions")
    if not isinstance(reopened, list) or not any(
        isinstance(item, dict)
        and item.get("id") == "LTCD-R01"
        and item.get("new_decision") == "重新设计并复活完整角色化工程工作流"
        for item in reopened
    ):
        failures.append("旧 Loom / Layer B 完整形态的旧决定必须被重新解释为重设计复活")
    terminal = contract.get("terminal_goal_effect")
    if not isinstance(terminal, dict):
        failures.append("完整复活修正合同缺少终局目标影响")
    else:
        if terminal.get("redcap_complete_revival_must_reopen") is not True:
            failures.append("完整复活父任务必须重新打开")
        forbidden = terminal.get("forbidden_completion_basis")
        if not isinstance(forbidden, list) or "最小执行内核" not in forbidden:
            failures.append("终局目标必须禁止用最小执行内核作为完成依据")
    return failures


def check(contract_path: pathlib.Path, merge_path: pathlib.Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    scan_merge = load_json(merge_path)
    failures = validate_contract(contract, scan_merge)
    return {
        "schema_id": "redcap-full-revival-amendment-check",
        "ok": not failures,
        "contract": str(contract_path),
        "scan_merge": str(merge_path),
        "required_design_count": len(contract.get("required_designs", [])) if isinstance(contract.get("required_designs"), list) else 0,
        "scan_portable_count": len(portable_ids(scan_merge)),
        "failures": failures,
    }


def cmd_check(args: argparse.Namespace) -> int:
    result = check(pathlib.Path(args.contract).resolve(), pathlib.Path(args.scan_merge).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_FULL_REVIVAL_AMENDMENT_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    scan = {"portable_designs": [{"id": "A"}, {"id": "B"}]}
    good = {
        "schema_id": "redcap-full-revival-amendment",
        "posture": "complete_workflow_machine_required",
        "minimum_kernel_completion_allowed": False,
        "rules": [{"id": f"R{i}", "rule": "x"} for i in range(4)],
        "required_designs": [
            {"id": "A", "name": "a", "required_as": "runtime", "full_revival_required": True},
            {"id": "B", "name": "b", "required_as": "workflow", "full_revival_required": True},
        ],
        "reopened_design_decisions": [
            {"id": "LTCD-R01", "new_decision": "重新设计并复活完整角色化工程工作流"}
        ],
        "terminal_goal_effect": {
            "redcap_complete_revival_must_reopen": True,
            "forbidden_completion_basis": ["最小执行内核"],
        },
    }
    failures: list[str] = []
    if validate_contract(good, scan):
        failures.append("完整复活修正样例不应失败")
    bad = dict(good)
    bad["minimum_kernel_completion_allowed"] = True
    if not any("最小内核" in item for item in validate_contract(bad, scan)):
        failures.append("允许最小内核完成的样例没有失败")
    missing = dict(good)
    missing["required_designs"] = good["required_designs"][:1]
    if not any("缺少扫描出的优秀设计" in item for item in validate_contract(missing, scan)):
        failures.append("缺少设计清单项的样例没有失败")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_FULL_REVIVAL_AMENDMENT_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap 完整复活口径修正检查器")
    sub = parser.add_subparsers(dest="command", required=True)
    check_cmd = sub.add_parser("check")
    check_cmd.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    check_cmd.add_argument("--scan-merge", default=str(DEFAULT_MERGE))
    check_cmd.set_defaults(func=cmd_check)
    self_check = sub.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

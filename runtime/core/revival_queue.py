#!/usr/bin/env python3
"""从已验证扫描结果生成可执行的 RedCap 复活队列。"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MERGE_PATH = REPO_ROOT / "assets" / "archaeology" / "shards" / "old-redcap-360-scan-merge.json"


def run_command(argv: list[str], *, timeout: int = 120) -> dict[str, Any]:
    completed = subprocess.run(
        argv,
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "argv": argv,
        "exit_code": completed.returncode,
        "stdout_tail": completed.stdout[-1200:],
        "stderr_tail": completed.stderr[-1200:],
        "ok": completed.returncode == 0,
    }


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def merge_coverage(merge_path: pathlib.Path) -> dict[str, Any]:
    payload = load_json(merge_path)
    portable_ids = {
        str(item.get("id"))
        for item in payload.get("portable_designs", [])
        if isinstance(item, dict) and item.get("id")
    }
    risk_ids = {
        str(item.get("id"))
        for item in payload.get("risk_designs", [])
        if isinstance(item, dict) and item.get("id")
    }
    return {
        "ok": payload.get("schema_id") == "prism-shard-merge"
        and payload.get("verified_count", 0) >= 3
        and payload.get("no_promote_count", 0) >= 4
        and len(portable_ids) >= 10
        and len(risk_ids) >= 8,
        "portable_ids": sorted(portable_ids),
        "risk_ids": sorted(risk_ids),
        "verified_count": payload.get("verified_count"),
        "no_promote_count": payload.get("no_promote_count"),
    }


def item(
    item_id: str,
    title: str,
    reality_change: str,
    scan_refs: list[str],
    commands: list[list[str]],
    *,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "title": title,
        "reality_change": reality_change,
        "scan_refs": scan_refs,
        "commands": commands,
        "required_for_formal_use": required,
    }


def queue_items() -> list[dict[str, Any]]:
    return [
        item(
            "RQ-01",
            "360 扫描合并结果",
            "旧 RedCap 设计已经完成分片扫描、合并，并能被检查器验证。",
            ["boundary-layer-separation", "DLR-P01", "LTCD-P03"],
            [["runtime/bin/redcap", "scan-conclusion", "check"]],
        ),
        item(
            "RQ-02",
            "运行边界",
            "运行时、项目工作区、用户私有状态三层边界由运行时代码检查。",
            ["boundary-layer-separation", "boundary-self-development-exception", "boundary-user-private-state"],
            [["runtime/bin/redcap", "boundary", "check"], ["runtime/bin/redcap", "boundary", "self-check"]],
        ),
        item(
            "RQ-03",
            "生命周期与完成声明",
            "原始意图、评审轨、完成等级和最终声明由生命周期与最终声明检查器约束。",
            ["DLR-P01", "DLR-P02", "DLR-P03", "DLR-R03"],
            [["runtime/bin/redcap", "lifecycle", "self-check"], ["runtime/bin/redcap", "final-claim", "self-check"]],
        ),
        item(
            "RQ-04",
            "长任务分片治理",
            "长任务通过分片账目、上下文预算、Cap 验收与合并条件约束。",
            ["LTCD-P01", "LTCD-P03", "LTCD-P04", "LTCD-P05"],
            [["runtime/bin/redcap", "prism-shard", "self-check"], ["runtime/bin/redcap", "prism-ledger", "summary"]],
        ),
        item(
            "RQ-05",
            "索引优先知识入口",
            "知识、证据和大材料默认先走索引，原始证据不默认进入上下文。",
            ["LTCD-P02", "LTCD-R02"],
            [["runtime/bin/redcap", "knowledge-gateway", "check"]],
        ),
        item(
            "RQ-06",
            "宿主边界诚实审计",
            "RedCap 只声明已验证的项目钩子和调度器边界，不包装成未知宿主能力。",
            ["LTCD-P06", "LTCD-R04"],
            [["runtime/bin/redcap", "host-hook-audit"]],
        ),
        item(
            "RQ-07",
            "用户状态命令",
            "用户可直接运行 redcap status 查看项目状态、扫描状态和下一步。",
            ["boundary-shared-command-resolution", "DLR-P05"],
            [["runtime/bin/redcap", "status", "--json"]],
        ),
        item(
            "RQ-08",
            "Cap 复活命令",
            "用户可直接运行 redcap revive 重新加载 Cap 身份并得到状态面，不泄露私密正文。",
            ["LTCD-P01", "boundary-user-private-state"],
            [["runtime/bin/redcap", "revive", "--json", "--no-write-evidence"]],
        ),
        item(
            "RQ-09",
            "旧病禁止提升",
            "报告即进度、回执即完成、收尾递归和原始证据默认加载都保留为禁止提升决策。",
            ["DLR-R01", "DLR-R03", "LTCD-R02", "LTCD-R03"],
            [["runtime/bin/redcap", "phase2-blueprint", "check"]],
        ),
    ]


def evaluate_queue(*, merge_path: pathlib.Path = MERGE_PATH, run_checks: bool = True) -> dict[str, Any]:
    coverage = merge_coverage(merge_path)
    entries = []
    for spec in queue_items():
        command_results = [run_command(argv) for argv in spec["commands"]] if run_checks else []
        commands_ok = all(result.get("ok") for result in command_results) if run_checks else True
        scan_refs_present = all(ref in coverage["portable_ids"] or ref in coverage["risk_ids"] for ref in spec["scan_refs"])
        status = "verified" if coverage["ok"] and commands_ok and scan_refs_present else "pending"
        entries.append({
            **spec,
            "status": status,
            "scan_refs_present": scan_refs_present,
            "command_results": command_results,
        })
    required_open = [
        entry["id"] for entry in entries
        if entry["required_for_formal_use"] and entry["status"] != "verified"
    ]
    return {
        "schema_id": "redcap-revival-execution-queue",
        "ok": not required_open,
        "merge_coverage": coverage,
        "required_open": required_open,
        "entries": entries,
    }


def cmd_check(args: argparse.Namespace) -> int:
    result = evaluate_queue(merge_path=pathlib.Path(args.merge).resolve(), run_checks=not args.no_run_checks)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_REVIVAL_QUEUE_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="redcap-revival-queue-") as raw_tmp:
        tmp = pathlib.Path(raw_tmp)
        merge = tmp / "merge.json"
        merge.write_text(json.dumps({
            "schema_id": "prism-shard-merge",
            "verified_count": 3,
            "no_promote_count": 4,
            "portable_designs": (
                [{"id": ref} for entry in queue_items() for ref in entry["scan_refs"] if not ref.startswith("DLR-R") and not ref.startswith("LTCD-R")]
                + [{"id": f"fixture-portable-{index}"} for index in range(10)]
            ),
            "risk_designs": (
                [{"id": ref} for entry in queue_items() for ref in entry["scan_refs"] if ref.startswith("DLR-R") or ref.startswith("LTCD-R")]
                + [{"id": f"fixture-risk-{index}"} for index in range(8)]
            ),
        }, ensure_ascii=False), encoding="utf-8")
        good = evaluate_queue(merge_path=merge, run_checks=False)
        if not good["ok"]:
            failures.append(f"完整覆盖队列应通过：{good['required_open']}")
        bad_payload = load_json(merge)
        bad_payload["portable_designs"] = []
        bad = tmp / "bad-merge.json"
        bad.write_text(json.dumps(bad_payload, ensure_ascii=False), encoding="utf-8")
        bad_result = evaluate_queue(merge_path=bad, run_checks=False)
        if bad_result["ok"] or not bad_result["required_open"]:
            failures.append("缺少扫描引用时队列没有标记未完成")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_REVIVAL_QUEUE_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="可执行的 RedCap 复活队列")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--merge", default=str(MERGE_PATH))
    check.add_argument("--no-run-checks", action="store_true")
    check.set_defaults(func=cmd_check)
    self_check = sub.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

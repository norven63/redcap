#!/usr/bin/env python3
"""检查会写运行产物的命令是否使用项目级 .redcap 边界。"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def run(argv: list[str], *, cwd: pathlib.Path = REPO_ROOT, timeout: int = 120) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "argv": argv,
            "exit_code": 124,
            "ok": False,
            "stdout": exc.stdout or "",
            "stderr": f"命令超时：{timeout} 秒",
        }
    return {
        "argv": argv,
        "exit_code": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def leading_json(stdout: str) -> dict[str, Any]:
    try:
        parsed, _ = json.JSONDecoder().raw_decode(stdout.lstrip())
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def assert_under(path: pathlib.Path, parent: pathlib.Path, label: str, failures: list[str]) -> None:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        failures.append(f"{label} 未落在项目级 .redcap 内：{path}")


def external_project_probe() -> dict[str, Any]:
    failures: list[str] = []
    command_results: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="redcap-boundary-consumers-") as raw_tmp:
        tmp = pathlib.Path(raw_tmp)
        project = tmp / "managed-project"
        nested = project / "src" / "pkg"
        nested.mkdir(parents=True)
        (project / ".dev-task.md").write_text("task_id: boundary-consumer-fixture\n", encoding="utf-8")
        private = tmp / "private"
        private.mkdir()
        redcap_dir = project / ".redcap"

        boundary_init = run([
            "runtime/bin/redcap",
            "boundary",
            "init",
            "--cwd",
            str(nested),
            "--user-private-root",
            str(private),
            "--require-task-file",
        ])
        command_results["boundary_init"] = boundary_init
        if not boundary_init["ok"]:
            failures.append("boundary init 失败")

        record = run([
            "runtime/bin/redcap",
            "task-facts",
            "record",
            "--cwd",
            str(nested),
            "--user-private-root",
            str(private),
            "--task-id",
            "external-boundary-consumer-fixture",
            "--title",
            "外部项目运行产物探针",
            "--status",
            "in_progress",
            "--reason",
            "验证 task-facts 默认写入项目级 .redcap。",
            "--source",
            "runtime-boundary-consumers-self-check",
            "--evidence",
            "runtime/core/runtime_boundary_consumers.py",
        ])
        command_results["task_facts_record"] = record
        record_payload = leading_json(record["stdout"])
        if not record["ok"]:
            failures.append("task-facts record 失败")
        ledger = pathlib.Path(record_payload.get("store_paths", {}).get("ledger") or "")
        if ledger:
            assert_under(ledger, redcap_dir, "task-facts ledger", failures)
        else:
            failures.append("task-facts record 没有返回 ledger 路径")

        summary = run([
            "runtime/bin/redcap",
            "task-facts",
            "summary",
            "--cwd",
            str(nested),
            "--user-private-root",
            str(private),
        ])
        command_results["task_facts_summary"] = summary
        summary_payload = leading_json(summary["stdout"])
        if not summary["ok"]:
            failures.append("task-facts summary 失败")
        if summary_payload.get("open_count") != 1:
            failures.append("外部项目 task-facts summary 没有读取项目级账本")
        summary_ledger = pathlib.Path(summary_payload.get("store_paths", {}).get("ledger") or "")
        if summary_ledger:
            assert_under(summary_ledger, redcap_dir, "task-facts summary ledger", failures)

        status = run([
            "runtime/bin/redcap",
            "status",
            "--json",
            "--cwd",
            str(nested),
            "--user-private-root",
            str(private),
        ])
        command_results["status"] = status
        status_payload = leading_json(status["stdout"])
        if not status["ok"]:
            failures.append("status 命令在外部项目失败")
        task_facts_path = pathlib.Path(status_payload.get("task_facts_path") or "")
        if task_facts_path:
            assert_under(task_facts_path, redcap_dir, "status task_facts_path", failures)
        else:
            failures.append("status 没有暴露 task_facts_path")
        if status_payload.get("task_summary", {}).get("open_count") != 1:
            failures.append("status 没有读取外部项目 task-facts 账本")

        if not (redcap_dir / ".gitignore").is_file():
            failures.append("外部项目 .redcap 缺少 .gitignore 保护")
        if (REPO_ROOT / ".redcap").exists():
            failures.append("探针不应在 RedCap 仓库根目录创建 .redcap")

        return {
            "schema_id": "redcap-runtime-boundary-consumer-check",
            "ok": not failures,
            "project_workspace": str(project),
            "project_runtime_root": str(redcap_dir),
            "commands_checked": sorted(command_results),
            "command_results": {
                name: {
                    "argv": result["argv"],
                    "exit_code": result["exit_code"],
                    "ok": result["ok"],
                    "stdout_tail": result["stdout"][-1200:],
                    "stderr_tail": result["stderr"][-1200:],
                }
                for name, result in command_results.items()
            },
            "failures": failures,
        }


def cmd_check(_: argparse.Namespace) -> int:
    result = external_project_probe()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_RUNTIME_BOUNDARY_CONSUMERS_OK")
        return 0
    return 1


def cmd_self_check(args: argparse.Namespace) -> int:
    return cmd_check(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查 RedCap 运行边界消费者")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
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

#!/usr/bin/env python3
"""独立复核 E2E 运行目录保留策略的外部验证器。"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys
from typing import Any


FORBIDDEN_RUNTIME_IMPORT_MODULES = [
    "runtime.core.complete_revival_e2e",
    "complete_revival_e2e",
    "runtime.core.soul_loader",
    "soul_loader",
]


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def ps_snapshot(pid: int) -> dict[str, Any]:
    if pid <= 0:
        return {"ok": False, "reason": "pid-missing"}
    completed = subprocess.run(
        ["ps", "-p", str(pid), "-o", "pid=,ppid=,pgid=,stat=,command="],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    output = (completed.stdout or "").strip()
    return {
        "ok": completed.returncode == 0 and bool(output),
        "exit_code": completed.returncode,
        "stdout": output,
        "stderr": (completed.stderr or "").strip(),
    }


def runtime_isolation_snapshot() -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "executable": sys.executable,
        "argv": sys.argv,
        "cwd": str(pathlib.Path.cwd()),
        "python_version": sys.version.split()[0],
        "process_snapshot": ps_snapshot(os.getpid()),
        "parent_snapshot": ps_snapshot(os.getppid()),
        "invocation_kind": "standalone-python-process",
    }


def normalize_deleted(paths: Any) -> list[str]:
    if not isinstance(paths, list):
        return []
    return [str(item) for item in paths]


def path_matches(path: pathlib.Path, candidates: list[str]) -> bool:
    resolved = str(path.resolve())
    return any(str(pathlib.Path(item).resolve()) == resolved for item in candidates if item)


def forbidden_import_hits(source: str, forbidden_modules: list[str]) -> list[str]:
    hits: list[str] = []
    tree = ast.parse(source)
    forbidden = set(forbidden_modules)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name in forbidden:
                    hits.append(name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in forbidden:
                hits.append(module)
    return sorted(set(hits))


def validate(args: argparse.Namespace) -> dict[str, Any]:
    root = pathlib.Path(args.root).expanduser().resolve() if args.root else None
    prune_result = pathlib.Path(args.prune_result).expanduser().resolve()
    live_dir = pathlib.Path(args.live_dir).expanduser().resolve()
    stale_dir = pathlib.Path(args.stale_dir).expanduser().resolve()
    out_path = pathlib.Path(args.out).expanduser().resolve() if args.out else None
    sleep_pid = int(args.sleep_pid)
    script_path = pathlib.Path(__file__).resolve()
    script_source = script_path.read_text(encoding="utf-8")

    failures: list[str] = []
    prune = load_json(prune_result)
    plan = prune.get("plan") if isinstance(prune.get("plan"), dict) else {}
    execution = prune.get("execution") if isinstance(prune.get("execution"), dict) else {}
    deleted = normalize_deleted(execution.get("deleted"))
    ps_after = ps_snapshot(sleep_pid)

    if prune.get("ok") is not True:
        failures.append("prune 结果不是 ok=true")
    if prune.get("executed") is not True:
        failures.append("prune 结果没有 executed=true，不能证明执行过清理")
    if plan.get("ok") is not True:
        failures.append("prune 计划不是 ok=true")
    if execution.get("ok") is not True:
        failures.append("prune 执行不是 ok=true")
    if live_dir.exists() is not True:
        failures.append("真实存活 active 目录被删除或不存在")
    if stale_dir.exists() is not False:
        failures.append("陈旧 active 目录没有被删除")
    if process_alive(sleep_pid) is not True:
        failures.append("真实 sleep 进程在清理后不存在")
    if ps_after.get("ok") is not True or "sleep" not in str(ps_after.get("stdout", "")).lower():
        failures.append("ps 快照没有证明 sleep 进程仍存活")
    if not path_matches(stale_dir, deleted):
        failures.append("prune 执行记录没有包含陈旧 active 目录删除")
    if path_matches(live_dir, deleted):
        failures.append("prune 执行记录错误包含真实存活 active 目录")
    if plan.get("safety_warnings"):
        failures.append("prune 计划仍有 safety_warnings")
    if execution.get("failures"):
        failures.append("prune 执行存在 failures")
    import_hits = forbidden_import_hits(script_source, FORBIDDEN_RUNTIME_IMPORT_MODULES)
    if import_hits:
        failures.append("外部验证器源码包含被测运行器或 soul_loader 导入标记")
    if root and root in stale_dir.parents and root in live_dir.parents:
        root_check = "same_root"
    elif root:
        root_check = "root_mismatch"
        failures.append("live/stale 目录不都位于声明的 root 下")
    else:
        root_check = "not_provided"

    result = {
        "schema_id": "redcap-e2e-retention-external-validation",
        "created_at": iso_now(),
        "ok": not failures,
        "root": str(root) if root else None,
        "root_check": root_check,
        "inputs": {
            "prune_result": str(prune_result),
            "live_dir": str(live_dir),
            "stale_dir": str(stale_dir),
            "sleep_pid": sleep_pid,
        },
        "validator": {
            "path": "runtime/audit/e2e_retention_external_validation.py",
            "absolute_path": str(script_path),
            "sha256": sha256_file(script_path),
            "runtime_isolation": runtime_isolation_snapshot(),
            "forbidden_runtime_import_modules": FORBIDDEN_RUNTIME_IMPORT_MODULES,
            "forbidden_import_hits": import_hits,
        },
        "observations": {
            "sleep_alive_after": process_alive(sleep_pid),
            "ps_after": ps_after,
            "live_dir_exists_after": live_dir.exists(),
            "stale_dir_exists_after": stale_dir.exists(),
            "deleted": deleted,
            "plan_delete_candidates": plan.get("delete_candidates", []),
        },
        "failures": failures,
    }
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="独立复核 E2E 运行目录保留策略")
    parser.add_argument("--root")
    parser.add_argument("--prune-result", required=True)
    parser.add_argument("--live-dir", required=True)
    parser.add_argument("--stale-dir", required=True)
    parser.add_argument("--sleep-pid", required=True)
    parser.add_argument("--out")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = validate(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok") is True:
        print("REDCAP_E2E_RETENTION_EXTERNAL_VALIDATION_OK")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

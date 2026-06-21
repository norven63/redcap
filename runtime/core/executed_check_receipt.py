#!/usr/bin/env python3
"""生成 RedCap 可复查的命令执行回执。"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_ID = "redcap-executed-check-receipt"


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_bytes(path: pathlib.Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(raw)
    os.replace(tmp, path)


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def resolve_output(raw: str) -> pathlib.Path:
    path = pathlib.Path(raw)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def run_command(args: argparse.Namespace) -> dict[str, Any]:
    if not args.argv:
        raise SystemExit("缺少要执行的命令；请在 -- 后传入 argv")
    out = resolve_output(args.out)
    stdout_path = resolve_output(args.stdout_path) if args.stdout_path else out.with_suffix(".stdout.txt")
    stderr_path = resolve_output(args.stderr_path) if args.stderr_path else out.with_suffix(".stderr.txt")
    started = time.monotonic()
    completed = subprocess.run(
        args.argv,
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        timeout=args.timeout_seconds,
    )
    elapsed = round(time.monotonic() - started, 3)
    write_bytes(stdout_path, completed.stdout)
    write_bytes(stderr_path, completed.stderr)
    ok = completed.returncode == args.expected_exit_code
    payload = {
        "schema_id": SCHEMA_ID,
        "name": args.name,
        "command": " ".join(args.argv),
        "argv": args.argv,
        "cwd": str(REPO_ROOT),
        "exit_code": completed.returncode,
        "expected_exit_code": args.expected_exit_code,
        "expected_exit_codes": [args.expected_exit_code],
        "ok": ok,
        "elapsed_seconds": elapsed,
        "stdout_path": str(stdout_path.relative_to(REPO_ROOT) if stdout_path.is_relative_to(REPO_ROOT) else stdout_path),
        "stderr_path": str(stderr_path.relative_to(REPO_ROOT) if stderr_path.is_relative_to(REPO_ROOT) else stderr_path),
        "stdout_sha256": sha256_bytes(completed.stdout),
        "stderr_sha256": sha256_bytes(completed.stderr),
        "stdout_length": len(completed.stdout),
        "stderr_length": len(completed.stderr),
        "executed_at": iso_now(),
        "executor": "cap",
    }
    write_json(out, payload)
    return payload


def cmd_run(args: argparse.Namespace) -> int:
    try:
        payload = run_command(args)
    except subprocess.TimeoutExpired as exc:
        out = resolve_output(args.out)
        stdout_path = resolve_output(args.stdout_path) if args.stdout_path else out.with_suffix(".stdout.txt")
        stderr_path = resolve_output(args.stderr_path) if args.stderr_path else out.with_suffix(".stderr.txt")
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        if isinstance(stdout, str):
            stdout = stdout.encode("utf-8")
        if isinstance(stderr, str):
            stderr = stderr.encode("utf-8")
        write_bytes(stdout_path, stdout)
        write_bytes(stderr_path, stderr)
        payload = {
            "schema_id": SCHEMA_ID,
            "name": args.name,
            "command": " ".join(args.argv),
            "argv": args.argv,
            "cwd": str(REPO_ROOT),
            "exit_code": 124,
            "expected_exit_code": args.expected_exit_code,
            "expected_exit_codes": [args.expected_exit_code],
            "ok": False,
            "timed_out": True,
            "timeout_seconds": args.timeout_seconds,
            "elapsed_seconds": args.timeout_seconds,
            "stdout_path": str(stdout_path.relative_to(REPO_ROOT) if stdout_path.is_relative_to(REPO_ROOT) else stdout_path),
            "stderr_path": str(stderr_path.relative_to(REPO_ROOT) if stderr_path.is_relative_to(REPO_ROOT) else stderr_path),
            "stdout_sha256": sha256_bytes(stdout),
            "stderr_sha256": sha256_bytes(stderr),
            "stdout_length": len(stdout),
            "stderr_length": len(stderr),
            "executed_at": iso_now(),
            "executor": "cap",
        }
        write_json(out, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") is True else 1


def cmd_self_check(_: argparse.Namespace) -> int:
    with subprocess.Popen(
        [sys.executable, __file__, "run", "--name", "executed-check-self-check", "--out", "/tmp/redcap-executed-check-self-check.json", "--", sys.executable, "-c", "print('ok')"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as proc:
        stdout, stderr = proc.communicate(timeout=30)
    payload_path = pathlib.Path("/tmp/redcap-executed-check-self-check.json")
    failures: list[str] = []
    if proc.returncode != 0:
        failures.append(f"self-check 子命令失败：stdout={stdout.decode(errors='replace')} stderr={stderr.decode(errors='replace')}")
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        payload = {}
        failures.append(f"self-check 回执不可读：{exc}")
    if payload.get("schema_id") != SCHEMA_ID:
        failures.append("self-check 回执 schema_id 错误")
    if payload.get("ok") is not True:
        failures.append("self-check 回执 ok 不为 true")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_EXECUTED_CHECK_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 RedCap 命令执行回执")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--name", required=True)
    run.add_argument("--out", required=True)
    run.add_argument("--stdout-path")
    run.add_argument("--stderr-path")
    run.add_argument("--expected-exit-code", type=int, default=0)
    run.add_argument("--timeout-seconds", type=float, default=180)
    run.add_argument("argv", nargs=argparse.REMAINDER)
    run.set_defaults(func=cmd_run)
    sub.add_parser("self-check").set_defaults(func=cmd_self_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "argv", None) and args.argv[0] == "--":
        args.argv = args.argv[1:]
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Reversible divergence probe for RSP-24 runtime health checks."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import subprocess
import time
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_TARGET = REPO_ROOT / "runtime" / "core" / "loom_runtime.py"
DEFAULT_OUT = REPO_ROOT / "assets" / "evidence" / "rsp" / "rsp-24-divergence-test.json"
DEFAULT_MAIN_REPORT = REPO_ROOT / "assets" / "evidence" / "rsp" / "rsp-24-divergence-main.json"
DEFAULT_PROBE_REPORT = REPO_ROOT / "assets" / "evidence" / "rsp" / "rsp-24-divergence-independent.json"
SCHEMA_ID = "redcap-rsp-24-divergence-test"


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def rel(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def run_step(name: str, argv: list[str], expected_exit_code: int | None, steps: list[dict[str, Any]]) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(argv, cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    result = {
        "name": name,
        "argv": argv,
        "exit_code": completed.returncode,
        "expected_exit_code": expected_exit_code,
        "ok": completed.returncode == expected_exit_code if expected_exit_code is not None else completed.returncode == 0,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }
    steps.append(result)
    return result


def find_entrypoint(payload: dict[str, Any], key: str, entrypoint_id: str) -> dict[str, Any]:
    items = payload.get(key)
    if not isinstance(items, list):
        return {}
    for item in items:
        if isinstance(item, dict) and item.get("id") == entrypoint_id:
            return item
    return {}


def expected_category_for_mode(mode: str) -> str:
    if mode == "hide":
        return "command_missing"
    if mode == "permission-deny":
        return "permission_error"
    raise SystemExit(f"unsupported mode: {mode}")


def apply_mutation(target: pathlib.Path, hidden: pathlib.Path, mode: str) -> dict[str, Any]:
    if mode == "hide":
        target.rename(hidden)
        return {"original_mode": None}
    if mode == "permission-deny":
        original_mode = target.stat().st_mode & 0o777
        target.chmod(0)
        return {"original_mode": original_mode}
    raise SystemExit(f"unsupported mode: {mode}")


def restore_mutation(target: pathlib.Path, hidden: pathlib.Path, mode: str, mutation_state: dict[str, Any]) -> bool:
    if mode == "hide":
        if hidden.exists():
            hidden.rename(target)
            return True
        return target.exists()
    if mode == "permission-deny":
        original_mode = mutation_state.get("original_mode")
        if isinstance(original_mode, int):
            target.chmod(original_mode)
            return True
        return False
    raise SystemExit(f"unsupported mode: {mode}")


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    target = pathlib.Path(args.target).resolve()
    hidden = target.with_name(f".{target.name}.rsp24-divergence-hidden")
    out = pathlib.Path(args.out).resolve()
    main_report = pathlib.Path(args.main_report).resolve()
    probe_report = pathlib.Path(args.probe_report).resolve()
    steps: list[dict[str, Any]] = []
    restored = False
    mutation_state: dict[str, Any] = {}
    expected_category = expected_category_for_mode(args.mode)

    try:
        target.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise SystemExit("target must be inside RedCap workspace") from exc
    try:
        if not target.exists():
            raise SystemExit(f"target missing before divergence probe: {target}")
        if hidden.exists():
            raise SystemExit(f"hidden path already exists: {hidden}")
        mutation_state = apply_mutation(target, hidden, args.mode)
        run_step(
            f"main-check-with-{args.mode}",
            ["runtime/bin/redcap", "runtime-health", "check", "--out", rel(main_report)],
            1,
            steps,
        )
        run_step(
            f"independent-probe-with-{args.mode}",
            [
                "runtime/bin/redcap",
                "runtime-health",
                "independent-probe",
                "--report",
                rel(main_report),
                "--out",
                rel(probe_report),
            ],
            0,
            steps,
        )
    finally:
        restored = restore_mutation(target, hidden, args.mode, mutation_state)
        run_step("target-restored-self-check", ["runtime/bin/redcap", "loom-runtime", "self-check"], 0, steps)

    main_payload = load_json(main_report)
    probe_payload = load_json(probe_report)
    main_loom = find_entrypoint(main_payload, "entrypoints", "loom_runtime")
    probe_loom = find_entrypoint(probe_payload, "entrypoints_observed", "loom_runtime")
    payload = {
        "schema_id": SCHEMA_ID,
        "ok": restored
        and main_payload.get("ok") is False
        and main_payload.get("status") == "blocked"
        and main_loom.get("category") == expected_category
        and probe_payload.get("ok") is True
        and probe_loom.get("ok") is False,
        "generated_at": iso_now(),
        "mutation": {
            "type": args.mode,
            "target": rel(target),
            "hidden_path": rel(hidden),
            "original_mode": mutation_state.get("original_mode"),
            "restored": restored,
        },
        "main_checker_result": {
            "path": rel(main_report),
            "ok": main_payload.get("ok"),
            "status": main_payload.get("status"),
            "loom_runtime": main_loom,
        },
        "independent_probe_result": {
            "path": rel(probe_report),
            "ok": probe_payload.get("ok"),
            "loom_runtime": probe_loom,
            "failures": probe_payload.get("failures"),
        },
        "expected_category": expected_category,
        "steps": steps,
    }
    write_json(out, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 RSP-24 可回滚发散探针")
    parser.add_argument("--target", default=str(DEFAULT_TARGET))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--main-report", default=str(DEFAULT_MAIN_REPORT))
    parser.add_argument("--probe-report", default=str(DEFAULT_PROBE_REPORT))
    parser.add_argument("--mode", choices=["hide", "permission-deny"], default="hide")
    args = parser.parse_args()
    payload = run_probe(args)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload["ok"]:
        print("REDCAP_CAP_RUNTIME_HEALTH_DIVERGENCE_PROBE_OK")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Independent probe for RSP-24 runtime health evidence.

This script intentionally does not import cap_runtime_health.py. It observes the
same contract and current report through a separate code path.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import time
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = REPO_ROOT / "assets" / "contracts" / "cap-runtime-health.json"
DEFAULT_REPORT = REPO_ROOT / "assets" / "evidence" / "rsp" / "rsp-24-cap-runtime-health.json"
DEFAULT_OUT = REPO_ROOT / "assets" / "evidence" / "rsp" / "rsp-24-independent-runtime-health.json"
REPORT_SCHEMA_ID = "redcap-cap-runtime-health-independent-probe"
REQUIRED_ENTRYPOINTS = {
    "gate",
    "prism_dispatch",
    "loom_runtime",
    "self_purification",
    "knowledge_gateway",
    "project_install",
    "e2e_report",
}
FAILURE_CATEGORIES = {
    "command_missing": "blocked",
    "config_error": "blocked",
    "permission_error": "blocked",
    "provider_unavailable": "degraded",
    "evidence_missing": "blocked",
}


def classify_observation(*, ok: bool, exit_code: int | None, timed_out: bool, stderr: str) -> tuple[str | None, str | None]:
    if ok:
        return None, None
    text = stderr.casefold()
    if "permission denied" in text or "operation not permitted" in text or exit_code == 126:
        return "permission_error", "blocked"
    if "no such file or directory" in text or "can't open file" in text or "command not found" in text:
        return "command_missing", "blocked"
    if timed_out or "provider timeout" in text or "rate limit" in text or "quota" in text or "connection refused" in text:
        return "provider_unavailable", "degraded"
    if "evidence missing" in text or "receipt missing" in text or "missing evidence" in text:
        return "evidence_missing", "blocked"
    return "config_error", "blocked"


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取 JSON：{path}: {exc}") from exc


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def rel(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def entrypoints_from_contract(contract: dict[str, Any]) -> list[dict[str, Any]]:
    items = contract.get("entrypoints")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)]


def run_entrypoint(entrypoint: dict[str, Any]) -> dict[str, Any]:
    argv = entrypoint.get("command")
    if not isinstance(argv, list) or any(not isinstance(item, str) for item in argv):
        category, status = classify_observation(
            ok=False,
            exit_code=None,
            timed_out=False,
            stderr="invalid command shape",
        )
        return {
            "id": entrypoint.get("id"),
            "ok": False,
            "category": category,
            "status": status,
            "exit_code": None,
            "timed_out": False,
            "elapsed_seconds": 0,
            "observer_failure": "invalid command shape",
        }
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            argv,
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=int(entrypoint.get("timeout_seconds", 60)),
        )
        elapsed = round(time.perf_counter() - started, 3)
        ok = completed.returncode == 0
        category, status = classify_observation(
            ok=ok,
            exit_code=completed.returncode,
            timed_out=False,
            stderr=completed.stderr,
        )
        return {
            "id": entrypoint.get("id"),
            "ok": ok,
            "category": category,
            "status": "healthy" if ok else status,
            "exit_code": completed.returncode,
            "timed_out": False,
            "elapsed_seconds": elapsed,
            "stdout_tail": completed.stdout[-800:],
            "stderr_tail": completed.stderr[-800:],
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = round(time.perf_counter() - started, 3)
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        category, status = classify_observation(
            ok=False,
            exit_code=None,
            timed_out=True,
            stderr=stderr or "independent probe timeout",
        )
        return {
            "id": entrypoint.get("id"),
            "ok": False,
            "category": category,
            "status": status,
            "exit_code": None,
            "timed_out": True,
            "elapsed_seconds": elapsed,
            "stdout_tail": stdout[-800:],
            "stderr_tail": stderr[-800:] or "independent probe timeout",
        }


def independent_aggregate(statuses: list[str]) -> str:
    if "blocked" in statuses:
        return "blocked"
    if "degraded" in statuses:
        return "degraded"
    return "healthy"


def injected_matrix(entrypoint_ids: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entrypoint_id in entrypoint_ids:
        for category, severity in FAILURE_CATEGORIES.items():
            other_statuses = ["healthy" for _ in entrypoint_ids if _ != entrypoint_id]
            aggregate = independent_aggregate([severity, *other_statuses])
            rows.append({
                "entrypoint": entrypoint_id,
                "injected_category": category,
                "expected_entrypoint_status": severity,
                "aggregate_status": aggregate,
                "probe_passed": aggregate != "healthy" and (aggregate == severity if severity == "degraded" else aggregate == "blocked"),
            })
    return rows


def compare_with_runtime_report(observed: list[dict[str, Any]], report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    report_entrypoints = report.get("entrypoints")
    if not isinstance(report_entrypoints, list):
        return ["runtime report entrypoints missing"]
    report_by_id = {
        item.get("id"): item
        for item in report_entrypoints
        if isinstance(item, dict)
    }
    for item in observed:
        entrypoint_id = item.get("id")
        current = report_by_id.get(entrypoint_id)
        if not isinstance(current, dict):
            failures.append(f"runtime report missing entrypoint: {entrypoint_id}")
            continue
        if current.get("ok") is not item.get("ok"):
            failures.append(f"runtime report ok mismatch for {entrypoint_id}")
        if current.get("timed_out") is not item.get("timed_out"):
            failures.append(f"runtime report timeout mismatch for {entrypoint_id}")
        if item.get("ok") is False and current.get("category") != item.get("category"):
            failures.append(
                f"runtime report category mismatch for {entrypoint_id}: "
                f"runtime={current.get('category')} probe={item.get('category')}"
            )
    return failures


def build_probe(contract: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    entrypoints = entrypoints_from_contract(contract)
    entrypoint_ids = [str(entrypoint.get("id")) for entrypoint in entrypoints]
    missing = sorted(REQUIRED_ENTRYPOINTS - set(entrypoint_ids))
    if missing:
        failures.append(f"contract missing entrypoints: {missing}")
    observed = [run_entrypoint(entrypoint) for entrypoint in entrypoints]
    failures.extend(compare_with_runtime_report(observed, report))
    matrix = injected_matrix(entrypoint_ids)
    failed_matrix = [row for row in matrix if row.get("probe_passed") is not True]
    if failed_matrix:
        failures.append("injected failure matrix has failed rows")
    provider_rows = [row for row in matrix if row.get("injected_category") == "provider_unavailable"]
    if not provider_rows or any(row.get("aggregate_status") != "degraded" for row in provider_rows):
        failures.append("provider_unavailable rows must aggregate to degraded")
    if any(row.get("aggregate_status") == "healthy" for row in matrix):
        failures.append("injected failure rows must never aggregate to healthy")
    if report.get("status") == "healthy" and any(item.get("ok") is not True for item in observed):
        failures.append("runtime report says healthy while independent observation saw a failed entrypoint")

    return {
        "schema_id": REPORT_SCHEMA_ID,
        "ok": not failures,
        "generated_at": iso_now(),
        "contract": rel(DEFAULT_CONTRACT),
        "runtime_report": rel(DEFAULT_REPORT),
        "observer": "independent subprocess runner; does not import cap_runtime_health.py",
        "entrypoint_count": len(observed),
        "entrypoints_observed": observed,
        "matrix_size": len(matrix),
        "matrix_expected_size": len(REQUIRED_ENTRYPOINTS) * len(FAILURE_CATEGORIES),
        "matrix_passed": len(matrix) == len(REQUIRED_ENTRYPOINTS) * len(FAILURE_CATEGORIES) and not failed_matrix,
        "provider_unavailable_policy": "degraded",
        "injected_failure_matrix": matrix,
        "failures": failures,
    }


def cmd_check(args: argparse.Namespace) -> int:
    contract = load_json(pathlib.Path(args.contract).resolve())
    report = load_json(pathlib.Path(args.report).resolve())
    if not isinstance(contract, dict):
        raise SystemExit("contract must be object")
    if not isinstance(report, dict):
        raise SystemExit("report must be object")
    payload = build_probe(contract, report)
    if args.out:
        write_json(pathlib.Path(args.out).resolve(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload["ok"]:
        print("REDCAP_CAP_RUNTIME_HEALTH_INDEPENDENT_PROBE_OK")
        return 0
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="独立验证 Cap 运行时健康巡检")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    return cmd_check(args)


if __name__ == "__main__":
    raise SystemExit(main())

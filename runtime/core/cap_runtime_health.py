#!/usr/bin/env python3
"""Cap runtime health check for critical RedCap entrypoints."""

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
DEFAULT_OUT = REPO_ROOT / "assets" / "evidence" / "rsp" / "rsp-24-cap-runtime-health.json"
DEFAULT_INDEPENDENT_PROBE = REPO_ROOT / "assets" / "evidence" / "rsp" / "rsp-24-independent-runtime-health.json"
DEFAULT_DIVERGENCE_TEST = REPO_ROOT / "assets" / "evidence" / "rsp" / "rsp-24-divergence-test.json"
DEFAULT_DIVERGENCE_PERMISSION_TEST = REPO_ROOT / "assets" / "evidence" / "rsp" / "rsp-24-divergence-permission-test.json"
CONTRACT_SCHEMA_ID = "redcap-cap-runtime-health-contract"
REPORT_SCHEMA_ID = "redcap-cap-runtime-health-report"
SELF_CHECK_SCHEMA_ID = "redcap-cap-runtime-health-self-check"
MARKER = "REDCAP_CAP_RUNTIME_HEALTH_OK"
SELF_CHECK_MARKER = "REDCAP_CAP_RUNTIME_HEALTH_SELF_CHECK_OK"
REQUIRED_ENTRYPOINTS = {
    "gate",
    "prism_dispatch",
    "loom_runtime",
    "self_purification",
    "knowledge_gateway",
    "project_install",
    "e2e_report",
}
REQUIRED_FAILURE_CATEGORIES = {
    "command_missing",
    "config_error",
    "permission_error",
    "provider_unavailable",
    "evidence_missing",
}
SUPPORTED_FIXTURES = {
    "healthy",
    "command-missing",
    "config-error",
    "permission-error",
    "provider-unavailable",
    "evidence-missing",
}


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


def load_contract(path: pathlib.Path) -> dict[str, Any]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise SystemExit("合同必须是 JSON 对象")
    return payload


def optional_json_object(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def category_map(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    categories = contract.get("failure_categories")
    if not isinstance(categories, list):
        return {}
    return {
        item["id"]: item
        for item in categories
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def fixture_map(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fixtures = contract.get("fixtures")
    if not isinstance(fixtures, list):
        return {}
    return {
        item["id"]: item
        for item in fixtures
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != CONTRACT_SCHEMA_ID:
        failures.append(f"schema_id 必须是 {CONTRACT_SCHEMA_ID}")
    if contract.get("rsp") != "RSP-24":
        failures.append("合同必须绑定 RSP-24")
    policy = contract.get("aggregate_policy")
    if not isinstance(policy, dict):
        failures.append("aggregate_policy 缺失")
        policy = {}
    for key in [
        "all_entrypoints_required",
        "any_blocked_fails_health",
        "provider_unavailable_is_degraded",
        "e2e_success_cannot_override_entrypoint_failure",
        "independent_cross_validation_required",
    ]:
        if policy.get(key) is not True:
            failures.append(f"aggregate_policy.{key} 必须为 true")
    if policy.get("forbidden_overall_status_when_any_entry_failed") != "healthy":
        failures.append("aggregate_policy 必须禁止入口失败时整体 healthy")

    entrypoints = contract.get("entrypoints")
    if not isinstance(entrypoints, list):
        failures.append("entrypoints 必须是数组")
        entrypoints = []
    entrypoint_ids: set[str] = set()
    for index, entrypoint in enumerate(entrypoints):
        if not isinstance(entrypoint, dict):
            failures.append(f"entrypoints[{index}] 必须是对象")
            continue
        entrypoint_id = entrypoint.get("id")
        if not isinstance(entrypoint_id, str) or not entrypoint_id:
            failures.append(f"entrypoints[{index}].id 缺失")
        elif entrypoint_id in entrypoint_ids:
            failures.append(f"entrypoints id 重复：{entrypoint_id}")
        else:
            entrypoint_ids.add(entrypoint_id)
        if entrypoint.get("required") is not True:
            failures.append(f"entrypoints[{index}].required 必须为 true")
        command = entrypoint.get("command")
        if not isinstance(command, list) or not command or any(not isinstance(item, str) for item in command):
            failures.append(f"entrypoints[{index}].command 必须是非空字符串数组")
        timeout = entrypoint.get("timeout_seconds")
        if not isinstance(timeout, int) or timeout <= 0:
            failures.append(f"entrypoints[{index}].timeout_seconds 必须是正整数")
    missing_entrypoints = sorted(REQUIRED_ENTRYPOINTS - entrypoint_ids)
    if missing_entrypoints:
        failures.append(f"缺少运行入口：{missing_entrypoints}")

    categories = category_map(contract)
    missing_categories = sorted(REQUIRED_FAILURE_CATEGORIES - set(categories))
    if missing_categories:
        failures.append(f"缺少故障分类：{missing_categories}")
    for category_id, category in categories.items():
        if category.get("severity") not in {"blocked", "degraded"}:
            failures.append(f"failure_categories.{category_id}.severity 无效")
        signals = category.get("match_signals")
        if not isinstance(signals, list) or not signals:
            failures.append(f"failure_categories.{category_id}.match_signals 必须是非空数组")

    fixtures = fixture_map(contract)
    missing_fixtures = sorted(SUPPORTED_FIXTURES - set(fixtures))
    if missing_fixtures:
        failures.append(f"缺少夹具：{missing_fixtures}")
    for fixture_id, fixture in fixtures.items():
        if fixture.get("expected_ok") not in {True, False}:
            failures.append(f"fixtures.{fixture_id}.expected_ok 必须是布尔值")
        if fixture.get("expected_status") not in {"healthy", "degraded", "blocked"}:
            failures.append(f"fixtures.{fixture_id}.expected_status 无效")
        category = fixture.get("expected_category")
        if category is not None and category not in categories:
            failures.append(f"fixtures.{fixture_id}.expected_category 未声明：{category}")

    fields = contract.get("required_report_fields")
    if not isinstance(fields, list) or not fields:
        failures.append("required_report_fields 必须是非空数组")
    return failures


def command_exists(argv: list[str]) -> bool:
    if not argv:
        return False
    command_path = pathlib.Path(argv[0])
    if command_path.is_absolute():
        return command_path.exists()
    return (REPO_ROOT / command_path).exists()


def classify_failure(*, stdout: str, stderr: str, exit_code: int | None, timed_out: bool, missing_command: bool) -> str:
    text = f"{stdout}\n{stderr}".casefold()
    if missing_command:
        return "command_missing"
    if timed_out:
        return "provider_unavailable" if "provider" in text or "prism" in text else "config_error"
    if "permission denied" in text or "operation not permitted" in text or exit_code == 126:
        return "permission_error"
    if any(signal in text for signal in ["provider timeout", "provider unavailable", "rate limit", "quota", "connection refused", "econnrefused"]):
        return "provider_unavailable"
    if any(signal in text for signal in ["evidence missing", "receipt missing", "no evidence", "missing evidence"]):
        return "evidence_missing"
    if any(signal in text for signal in ["invalid json", "schema_id", "config", "contract", "missing required", "must be", "必须"]):
        return "config_error"
    if any(signal in text for signal in ["command not found", "no such file or directory", "missing command"]):
        return "command_missing"
    return "config_error"


def category_severity(contract: dict[str, Any], category_id: str | None) -> str | None:
    if category_id is None:
        return None
    return category_map(contract).get(category_id, {}).get("severity", "blocked")


def run_entrypoint(entrypoint: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    argv = [str(item) for item in entrypoint["command"]]
    missing_command = not command_exists(argv)
    started = time.perf_counter()
    stdout = ""
    stderr = ""
    exit_code: int | None = None
    timed_out = False
    if missing_command:
        stderr = f"entrypoint file missing: {argv[0]}"
    else:
        try:
            completed = subprocess.run(
                argv,
                cwd=str(REPO_ROOT),
                check=False,
                capture_output=True,
                text=True,
                timeout=int(entrypoint["timeout_seconds"]),
            )
            stdout = completed.stdout
            stderr = completed.stderr
            exit_code = completed.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else "runtime health command timed out"
            timed_out = True
    elapsed = round(time.perf_counter() - started, 3)
    ok = (exit_code == 0) and not timed_out and not missing_command
    category = None if ok else classify_failure(
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        timed_out=timed_out,
        missing_command=missing_command,
    )
    severity = category_severity(contract, category)
    return {
        "id": entrypoint["id"],
        "label": entrypoint.get("label"),
        "ok": ok,
        "status": "healthy" if ok else severity,
        "category": category,
        "severity": severity,
        "argv": argv,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "timeout_seconds": entrypoint["timeout_seconds"],
        "elapsed_seconds": elapsed,
        "stdout_tail": stdout[-1200:],
        "stderr_tail": stderr[-1200:],
    }


def fixture_entrypoints(contract: dict[str, Any], fixture: str) -> list[dict[str, Any]]:
    entrypoints = contract.get("entrypoints")
    if not isinstance(entrypoints, list):
        return []
    results: list[dict[str, Any]] = []
    injected = {
        "command-missing": ("gate", "command_missing", "blocked", "entrypoint file missing"),
        "config-error": ("prism_dispatch", "config_error", "blocked", "contract schema_id invalid"),
        "permission-error": ("loom_runtime", "permission_error", "blocked", "permission denied"),
        "provider-unavailable": ("prism_dispatch", "provider_unavailable", "degraded", "provider timeout"),
        "evidence-missing": ("e2e_report", "evidence_missing", "blocked", "evidence missing"),
    }.get(fixture)
    for entrypoint in entrypoints:
        entrypoint_id = entrypoint.get("id")
        if injected and entrypoint_id == injected[0]:
            _, category, status, stderr = injected
            results.append({
                "id": entrypoint_id,
                "label": entrypoint.get("label"),
                "ok": False,
                "status": status,
                "category": category,
                "severity": status,
                "argv": entrypoint.get("command"),
                "exit_code": None if category in {"command_missing", "provider_unavailable"} else 1,
                "timed_out": category == "provider_unavailable",
                "timeout_seconds": entrypoint.get("timeout_seconds"),
                "elapsed_seconds": 0.01,
                "stdout_tail": "",
                "stderr_tail": stderr,
            })
        else:
            results.append({
                "id": entrypoint_id,
                "label": entrypoint.get("label"),
                "ok": True,
                "status": "healthy",
                "category": None,
                "severity": None,
                "argv": entrypoint.get("command"),
                "exit_code": 0,
                "timed_out": False,
                "timeout_seconds": entrypoint.get("timeout_seconds"),
                "elapsed_seconds": 0.01,
                "stdout_tail": "",
                "stderr_tail": "",
            })
    return results


def aggregate_status(entrypoints: list[dict[str, Any]]) -> str:
    if any(entrypoint.get("severity") == "blocked" for entrypoint in entrypoints):
        return "blocked"
    if any(entrypoint.get("severity") == "degraded" for entrypoint in entrypoints):
        return "degraded"
    return "healthy"


def build_report(
    contract: dict[str, Any],
    *,
    fixture: str | None = None,
    run_live: bool = True,
    include_acceptance: bool = True,
) -> dict[str, Any]:
    contract_failures = validate_contract(contract)
    if fixture:
        entrypoints = fixture_entrypoints(contract, fixture)
    elif run_live:
        raw_entrypoints = contract.get("entrypoints") if isinstance(contract.get("entrypoints"), list) else []
        entrypoints = [
            run_entrypoint(entrypoint, contract)
            for entrypoint in raw_entrypoints
            if isinstance(entrypoint, dict) and isinstance(entrypoint.get("command"), list)
        ]
    else:
        entrypoints = fixture_entrypoints(contract, "healthy")

    failures = list(contract_failures)
    entrypoint_ids = {str(entrypoint.get("id")) for entrypoint in entrypoints}
    missing_entrypoints = sorted(REQUIRED_ENTRYPOINTS - entrypoint_ids)
    if missing_entrypoints:
        failures.append(f"报告缺少运行入口：{missing_entrypoints}")

    status = aggregate_status(entrypoints)
    ok = not failures and status == "healthy"
    failed_entrypoints = [entrypoint for entrypoint in entrypoints if entrypoint.get("ok") is not True]
    if failed_entrypoints and status == "healthy":
        failures.append("入口失败时整体状态不能是 healthy")
        ok = False
    if any(entrypoint.get("category") == "provider_unavailable" and entrypoint.get("severity") != "degraded" for entrypoint in entrypoints):
        failures.append("provider_unavailable 必须分类为 degraded")
        ok = False

    if fixture:
        expectation = fixture_map(contract).get(fixture, {})
        if ok is not expectation.get("expected_ok"):
            failures.append(f"夹具 {fixture} ok 不符合预期：expected={expectation.get('expected_ok')} actual={ok}")
        if status != expectation.get("expected_status"):
            failures.append(f"夹具 {fixture} status 不符合预期：expected={expectation.get('expected_status')} actual={status}")
        expected_category = expectation.get("expected_category")
        actual_categories = {entrypoint.get("category") for entrypoint in failed_entrypoints}
        if expected_category not in actual_categories and expected_category is not None:
            failures.append(f"夹具 {fixture} category 不符合预期：expected={expected_category} actual={sorted(str(item) for item in actual_categories)}")

    failure_summary: dict[str, int] = {}
    for entrypoint in failed_entrypoints:
        category = str(entrypoint.get("category"))
        failure_summary[category] = failure_summary.get(category, 0) + 1

    acceptance = build_acceptance(contract, ok=ok and not failures, status=status, fixture=fixture) if include_acceptance else None
    report = {
        "schema_id": REPORT_SCHEMA_ID,
        "rsp": "RSP-24",
        "ok": ok and not failures,
        "status": status if not failures else ("blocked" if any("合同" in item or "缺少" in item for item in failures) else status),
        "mode": "fixture" if fixture else "live",
        "fixture": fixture,
        "generated_at": iso_now(),
        "contract": rel(DEFAULT_CONTRACT),
        "entrypoint_count": len(entrypoints),
        "required_entrypoints": sorted(REQUIRED_ENTRYPOINTS),
        "entrypoints": entrypoints,
        "failure_summary": failure_summary,
        "changed_reality": [
            "新增 Cap 运行时健康合同：assets/contracts/cap-runtime-health.json",
            "新增可执行入口：runtime/bin/redcap runtime-health check",
            "七类关键入口可被统一枚举和巡检",
            "五类故障可被分类，且 provider_unavailable 保持 degraded",
            "总检查器可通过 runtime-health-check 运行该能力",
            "独立探针可通过不导入主检查器的代码路径交叉验证七入口和 7×5 故障矩阵",
            "真实发散测试可临时隐藏一个入口文件并确认主检查器和独立探针都捕获损坏",
            "真实权限发散测试可临时移除入口文件读取权限并确认 permission_error 分类",
            "发散测试已固化为 runtime/bin/redcap runtime-health divergence-probe",
        ],
        "artifacts": [
            "assets/contracts/cap-runtime-health.json",
            "runtime/core/cap_runtime_health.py",
            "runtime/core/cap_runtime_health_external_probe.py",
            "runtime/core/cap_runtime_health_divergence_probe.py",
            "runtime/bin/redcap",
            "runtime/core/check_runner.py",
            "assets/evidence/rsp/rsp-24-cap-runtime-health.json",
            "assets/evidence/rsp/rsp-24-independent-runtime-health.json",
            "assets/evidence/rsp/rsp-24-divergence-test.json",
            "assets/evidence/rsp/rsp-24-divergence-permission-test.json",
        ],
        "failures": failures,
    }
    if acceptance is not None:
        report["acceptance"] = acceptance
    if fixture is None:
        independent_probe = optional_json_object(DEFAULT_INDEPENDENT_PROBE)
        if independent_probe is not None:
            report["independent_cross_validation"] = {
                "path": rel(DEFAULT_INDEPENDENT_PROBE),
                "ok": independent_probe.get("ok"),
                "observer": independent_probe.get("observer"),
                "entrypoint_count": independent_probe.get("entrypoint_count"),
                "matrix_size": independent_probe.get("matrix_size"),
                "matrix_passed": independent_probe.get("matrix_passed"),
                "provider_unavailable_policy": independent_probe.get("provider_unavailable_policy"),
                "failures": independent_probe.get("failures"),
            }
        divergence_test = optional_json_object(DEFAULT_DIVERGENCE_TEST)
        if divergence_test is not None:
            report["divergence_test"] = {
                "path": rel(DEFAULT_DIVERGENCE_TEST),
                "ok": divergence_test.get("ok"),
                "mutation": divergence_test.get("mutation"),
                "main_checker_result": divergence_test.get("main_checker_result"),
                "independent_probe_result": divergence_test.get("independent_probe_result"),
            }
        permission_divergence_test = optional_json_object(DEFAULT_DIVERGENCE_PERMISSION_TEST)
        if permission_divergence_test is not None:
            report["permission_divergence_test"] = {
                "path": rel(DEFAULT_DIVERGENCE_PERMISSION_TEST),
                "ok": permission_divergence_test.get("ok"),
                "mutation": permission_divergence_test.get("mutation"),
                "main_checker_result": permission_divergence_test.get("main_checker_result"),
                "independent_probe_result": permission_divergence_test.get("independent_probe_result"),
            }
    return report


def build_acceptance(contract: dict[str, Any], *, ok: bool, status: str, fixture: str | None) -> dict[str, Any]:
    positive_status = "pass" if ok and status == "healthy" and fixture is None else ("not_applicable" if fixture else "fail")
    negative_results: list[dict[str, Any]] = []
    if fixture is None:
        for negative_fixture in sorted(SUPPORTED_FIXTURES - {"healthy"}):
            probe = build_report(contract, fixture=negative_fixture, run_live=False, include_acceptance=False)
            expected = fixture_map(contract).get(negative_fixture, {})
            negative_results.append({
                "fixture": negative_fixture,
                "ok": probe["ok"],
                "status": probe["status"],
                "expected_ok": expected.get("expected_ok"),
                "expected_status": expected.get("expected_status"),
                "failure_summary": probe["failure_summary"],
                "probe_passed": probe["ok"] is expected.get("expected_ok")
                and probe["status"] == expected.get("expected_status")
                and not probe["failures"],
            })
    negative_status = "pass" if negative_results and all(item["probe_passed"] for item in negative_results) else (
        "not_applicable" if fixture else "fail"
    )
    return {
        "positive": {
            "status": positive_status,
            "checks": [
                "七类关键入口均已巡检",
                "入口失败不能被整体标为 healthy",
                "provider_unavailable 保持 degraded",
            ],
        },
        "negative": {
            "status": negative_status,
            "checks": [
                "command-missing",
                "config-error",
                "permission-error",
                "provider-unavailable",
                "evidence-missing",
            ],
            "probes": negative_results,
        },
    }


def cmd_check(args: argparse.Namespace) -> int:
    contract = load_contract(pathlib.Path(args.contract).resolve())
    report = build_report(contract, fixture=args.fixture)
    if args.out:
        write_json(pathlib.Path(args.out).resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["ok"]:
        print(MARKER)
        return 0
    return 1


def cmd_self_check(args: argparse.Namespace) -> int:
    contract = load_contract(pathlib.Path(args.contract).resolve())
    cases = [
        ("healthy", True, "healthy"),
        ("command-missing", False, "blocked"),
        ("config-error", False, "blocked"),
        ("permission-error", False, "blocked"),
        ("provider-unavailable", False, "degraded"),
        ("evidence-missing", False, "blocked"),
    ]
    failures: list[str] = []
    results: list[dict[str, Any]] = []
    for fixture, expected_ok, expected_status in cases:
        report = build_report(contract, fixture=fixture)
        result = {
            "fixture": fixture,
            "ok": report["ok"],
            "status": report["status"],
            "expected_ok": expected_ok,
            "expected_status": expected_status,
            "failure_summary": report["failure_summary"],
            "failures": report["failures"],
        }
        results.append(result)
        if report["ok"] is not expected_ok:
            failures.append(f"{fixture} ok expected={expected_ok} actual={report['ok']}")
        if report["status"] != expected_status:
            failures.append(f"{fixture} status expected={expected_status} actual={report['status']}")
        if len(report["entrypoints"]) != len(REQUIRED_ENTRYPOINTS):
            failures.append(f"{fixture} entrypoint count mismatch")
        if fixture == "provider-unavailable":
            failed = [entrypoint for entrypoint in report["entrypoints"] if entrypoint.get("category") == "provider_unavailable"]
            if not failed or failed[0].get("severity") != "degraded":
                failures.append("provider-unavailable 必须保留为 degraded，不能升级为 blocked 或核心损坏")
        if fixture != "healthy" and report["status"] == "healthy":
            failures.append(f"{fixture} 失败夹具不能得到 healthy")
    payload = {
        "schema_id": SELF_CHECK_SCHEMA_ID,
        "ok": not failures,
        "cases": results,
        "failures": failures,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print(SELF_CHECK_MARKER)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查 Cap 关键运行入口健康状态")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check")
    check.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    check.add_argument("--out")
    check.add_argument("--fixture", choices=sorted(SUPPORTED_FIXTURES))

    self_check = subparsers.add_parser("self-check")
    self_check.add_argument("--contract", default=str(DEFAULT_CONTRACT))

    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check(args)
    if args.command == "self-check":
        return cmd_self_check(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())

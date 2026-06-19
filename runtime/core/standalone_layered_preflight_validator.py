#!/usr/bin/env python3
"""Standalone validator for the RedCap complete-revival E2E layered preflight.

This script is intentionally kept outside runtime/core and outside
runtime/bin/redcap check. It directly imports the implementation under review
and verifies behavior without relying on RedCap's aggregate check runner.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from unittest import mock


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "runtime" / "core" / "complete_revival_e2e.py"
sys.path.insert(0, str(REPO_ROOT / "runtime" / "core"))


def load_module():
    spec = importlib.util.spec_from_file_location("complete_revival_e2e_standalone", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_true(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def source_order_probe(source: str) -> dict[str, object]:
    failures: list[str] = []
    layered = source.find("layered_preflight = run_layered_preflight(work_root)")
    carrier = source.find("carrier = carrier_probe(")
    worker = source.find('env["REDCAP_E2E_WORKER"] = "1"')
    assert_true(layered >= 0, "source missing run_layered_preflight call", failures)
    assert_true(carrier >= 0, "source missing carrier_probe call", failures)
    assert_true(worker >= 0, "source missing REDCAP_E2E_WORKER assignment", failures)
    if layered >= 0 and carrier >= 0:
        assert_true(layered < carrier, "run_layered_preflight is not before carrier_probe", failures)
    if carrier >= 0 and worker >= 0:
        assert_true(carrier < worker, "carrier_probe is not before REDCAP_E2E_WORKER assignment", failures)
    return {
        "ok": not failures,
        "positions": {"layered_preflight": layered, "carrier_probe": carrier, "worker_env": worker},
        "failures": failures,
    }


def direct_harness_block_probe(module) -> dict[str, object]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="redcap-standalone-harness-") as raw:
        work_root = pathlib.Path(raw)
        preflight = {
            "schema_id": "redcap-ai-e2e-layered-preflight",
            "ok": False,
            "blocked_before_project_run": True,
            "auto_rerun_allowed": False,
            "failures": ["standalone-preflight-failure"],
            "checks": [],
        }
        with mock.patch.object(module, "run_layered_preflight", return_value=preflight), mock.patch.object(module, "carrier_probe") as carrier:
            carrier.side_effect = AssertionError("carrier_probe must not be called after layered preflight failure")
            result = module.run_e2e_harness("standalone layered preflight block probe", work_root, timeout_seconds=240)
        active_run_path = work_root / "redcap-long-task-active-run.json"
        active_run = json.loads(active_run_path.read_text(encoding="utf-8")) if active_run_path.exists() else {}
        assert_true(result.get("ok") is False, "blocked harness result unexpectedly ok", failures)
        assert_true(result.get("blocked_before_project_run") is True, "blocked_before_project_run was not true", failures)
        assert_true(carrier.call_count == 0, "carrier_probe was called despite preflight failure", failures)
        assert_true(not (work_root / "redcap-e2e-carrier-preflight.json").exists(), "carrier preflight file was created", failures)
        completion_markers = list(work_root.glob("**/completion-marker.json"))
        assert_true(not completion_markers, f"completion marker was created: {completion_markers}", failures)
        assert_true(active_run.get("lifecycle_state") == "blocked", "active_run lifecycle_state is not blocked", failures)
        assert_true(active_run.get("auto_rerun_allowed") is False, "active_run auto_rerun_allowed is not false", failures)
    return {
        "ok": not failures,
        "failures": failures,
        "carrier_probe_call_count": carrier.call_count,
        "completion_marker_count": len(completion_markers),
        "active_run_lifecycle_state": active_run.get("lifecycle_state"),
        "active_run_auto_rerun_allowed": active_run.get("auto_rerun_allowed"),
    }


def project_install_failure_without_test_mode_probe(module) -> dict[str, object]:
    failures: list[str] = []

    def fake_run_command(argv, **_kwargs):
        argv_list = [str(item) for item in argv]
        is_project_install = argv_list[-2:] == ["project-install", "release-check"]
        return {
            "argv": argv_list,
            "cwd": str(REPO_ROOT),
            "exit_code": 31 if is_project_install else 0,
            "ok": not is_project_install,
            "timed_out": False,
            "timeout_seconds": 240,
            "stdout": "",
            "stderr": "simulated project-install release-check failure" if is_project_install else "",
        }

    old_test_mode = os.environ.pop(module.TEST_MODE_ENV, None)
    old_inject = os.environ.pop(module.TEST_INJECT_LAYERED_PREFLIGHT_FAILURE_ENV, None)
    try:
        with tempfile.TemporaryDirectory(prefix="redcap-standalone-project-install-") as raw:
            work_root = pathlib.Path(raw)
            with mock.patch.object(module, "run_command", side_effect=fake_run_command):
                result = module.run_layered_preflight(work_root)
            checks = {item["id"]: item for item in result.get("checks", [])}
            project_check = checks.get("project-install-release-check", {})
            assert_true(result.get("ok") is False, "project-install failure did not fail preflight", failures)
            assert_true(result.get("blocked_before_project_run") is True, "project-install failure did not block before project run", failures)
            assert_true(project_check.get("ok") is False, "project-install check was not marked failed", failures)
            assert_true(project_check.get("test_injection") is False, "project-install failure was incorrectly marked as test injection", failures)
            assert_true((work_root / "redcap-e2e-layered-preflight.json").exists(), "preflight evidence file was not written", failures)
    finally:
        if old_test_mode is not None:
            os.environ[module.TEST_MODE_ENV] = old_test_mode
        if old_inject is not None:
            os.environ[module.TEST_INJECT_LAYERED_PREFLIGHT_FAILURE_ENV] = old_inject
    return {
        "ok": not failures,
        "failures": failures,
        "blocked_before_project_run": result.get("blocked_before_project_run"),
        "project_install_test_injection": project_check.get("test_injection"),
    }


def injection_does_not_apply_without_test_mode() -> dict[str, object]:
    failures: list[str] = []
    env = os.environ.copy()
    env.pop("REDCAP_TEST_MODE", None)
    env["REDCAP_TEST_INJECT_LAYERED_PREFLIGHT_FAILURE"] = "knowledge-search-loom"
    with tempfile.TemporaryDirectory(prefix="redcap-standalone-no-test-mode-") as raw:
        cmd = [
            str(REPO_ROOT / "runtime" / "bin" / "redcap"),
            "complete-revival-e2e",
            "preflight",
            "--work-root",
            raw,
        ]
        proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, text=True, capture_output=True, timeout=300)
        try:
            payload, _ = json.JSONDecoder().raw_decode(proc.stdout.lstrip())
        except json.JSONDecodeError:
            payload = {}
            failures.append("preflight stdout did not start with JSON")
        assert_true(proc.returncode == 0, f"preflight without REDCAP_TEST_MODE failed: {proc.returncode}", failures)
        assert_true(payload.get("ok") is True, "preflight without REDCAP_TEST_MODE was not ok", failures)
        injected = [check for check in payload.get("checks", []) if check.get("test_injection")]
        assert_true(not injected, "test injection applied without REDCAP_TEST_MODE", failures)
    return {
        "ok": not failures,
        "failures": failures,
        "exit_code": proc.returncode,
        "test_injection_count": len(injected) if isinstance(payload, dict) else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    module = load_module()
    source = MODULE_PATH.read_text(encoding="utf-8")
    cases = [
        {"id": "source-order", **source_order_probe(source)},
        {"id": "direct-harness-block", **direct_harness_block_probe(module)},
        {"id": "project-install-failure-without-test-mode", **project_install_failure_without_test_mode_probe(module)},
        {"id": "injection-does-not-apply-without-test-mode", **injection_does_not_apply_without_test_mode()},
    ]
    failures = [f"{case['id']}: {item}" for case in cases for item in case.get("failures", [])]
    payload = {
        "schema_id": "redcap-standalone-layered-preflight-validation",
        "ok": not failures,
        "module": str(MODULE_PATH),
        "cases": cases,
        "failures": failures,
    }
    output = pathlib.Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

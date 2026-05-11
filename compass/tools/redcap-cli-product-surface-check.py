#!/usr/bin/env python3
# 用途：发布安全治理脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "references/cli-product-surface-policy.json"
CLI = ROOT / "bin/redcap"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-cli-product-surface-check] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"{label} missing: {path.relative_to(ROOT)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be an object")
    return payload


def run(args: list[str], cwd: Path, env: dict[str, str] | None = None, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    for key in [
        "REDCAP_TASK_FILE",
        "REDCAP_WORKSPACE",
        "REDCAP_WORKSPACE_ROOT",
        "REDCAP_RUNTIME_HOST",
    ]:
        merged.pop(key, None)
    if env:
        merged.update(env)
    return subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        env=merged,
        timeout=timeout,
    )


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        fail(f"{label} missing {needle!r}:\n{text[:2000]}")


def assert_not_contains(text: str, needle: str, label: str) -> None:
    if needle and needle in text:
        fail(f"{label} leaked forbidden text {needle!r}:\n{text[:2000]}")


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "redcap-cli-product-surface":
        fail("policy_id mismatch")
    required = set(policy.get("required_commands", []))
    for command in {"doctor", "debug", "help", "--trace"}:
        if command not in required:
            fail(f"policy missing required command: {command}")
    if policy.get("debug_contract", {}).get("no_secrets_assertion") is not True:
        fail("debug contract must require no_secrets_assertion=true")
    if policy.get("error_contract", {}).get("exit_code_for_usage_errors") != 2:
        fail("usage error exit code must be 2")
    if policy.get("trace_contract", {}).get("must_not_use") is None:
        fail("trace contract must declare forbidden trace mechanisms")


def inspect_cli() -> None:
    text = CLI.read_text(encoding="utf-8")
    for needle in [
        "doctor)",
        "debug)",
        "help|-h|--help)",
        "--trace",
        "redcap_error()",
        "原因(cause):",
        "影响(impact):",
        "建议动作(suggested_action):",
        "redcap-cli-product-surface.sh",
    ]:
        if needle not in text:
            fail(f"bin/redcap missing CLI product surface contract: {needle}")
    if "set -x" in text:
        fail("bin/redcap must not implement trace with set -x")


def load_debug_json(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        fail(f"debug --json did not emit valid JSON: {exc}\n{text[:2000]}")
    if not isinstance(payload, dict):
        fail("debug --json must emit a JSON object")
    return payload


def forbidden_output_checks(text: str, label: str, workspace: Path | None = None, task_file: Path | None = None) -> None:
    home = str(Path.home())
    for forbidden in [
        "/Users/",
        "/home/",
        home,
        ".cap",
        "identity_file",
        "agent_name",
        "API_KEY",
        "TOKEN",
        "SECRET",
        "PASSWORD",
    ]:
        assert_not_contains(text, forbidden, label)
    if workspace is not None:
        assert_not_contains(text, str(workspace), label)
    if task_file is not None:
        assert_not_contains(text, str(task_file), label)


def validate_debug_payload(payload: dict[str, Any], task_id: str, expected_mode: str, expected_task_status: str) -> None:
    required = [
        "version",
        "surface",
        "status",
        "runtime_root",
        "workspace_root",
        "task_file",
        "task_file_status",
        "task_id",
        "boundary_mode",
        "checks",
        "no_secrets_assertion",
    ]
    for key in required:
        if key not in payload:
            fail(f"debug json missing required field: {key}")
    if payload["no_secrets_assertion"] is not True:
        fail("debug json no_secrets_assertion must be true")
    if payload["task_id"] != task_id:
        fail(f"debug json task_id mismatch: {payload['task_id']} != {task_id}")
    if payload["boundary_mode"] != expected_mode:
        fail(f"debug json boundary_mode mismatch: {payload['boundary_mode']} != {expected_mode}")
    if payload["task_file_status"] != expected_task_status:
        fail(f"debug json task_file_status mismatch: {payload['task_file_status']} != {expected_task_status}")
    if not isinstance(payload["checks"], list) or not payload["checks"]:
        fail("debug json checks must be a non-empty list")
    for forbidden_key in ["identity_file", "agent_name"]:
        if forbidden_key in payload:
            fail(f"debug json must not include {forbidden_key}")


def run_external_workspace_smoke() -> None:
    with tempfile.TemporaryDirectory(prefix="redcap-cli-product-surface-") as tmp:
        workspace = Path(tmp).resolve()
        task_file = workspace / ".dev-task.md"
        task_file.write_text(
            """# 当前任务：cli product fixture

## 控制面元数据（机器校验）
task_id: fixture-cli-product-surface
active_slice: cli-product-surface-fixture
task_report: compass/docs/task-reports/fixture.md
""",
            encoding="utf-8",
        )

        doctor = run([str(CLI), "doctor"], cwd=workspace)
        if doctor.returncode != 0:
            fail("doctor external workspace smoke failed:\n" + doctor.stdout[:2000])
        assert_contains(doctor.stdout, "RedCap 体检：可继续", "doctor output")
        assert_contains(doctor.stdout, "运行方式：外部项目工作区", "doctor output")
        assert_contains(doctor.stdout, "下一步：", "doctor output")
        assert_not_contains(doctor.stdout, "[ok]", "doctor output")
        assert_not_contains(doctor.stdout, "[fail]", "doctor output")

        debug = run([str(CLI), "debug", "--json"], cwd=workspace)
        if debug.returncode != 0:
            fail("debug external workspace smoke failed:\n" + debug.stdout[:2000])
        forbidden_output_checks(debug.stdout, "debug json", workspace, task_file)
        payload = load_debug_json(debug.stdout)
        validate_debug_payload(payload, "fixture-cli-product-surface", "external-workspace", "exists")

        trace = run([str(CLI), "--trace", "doctor"], cwd=workspace)
        if trace.returncode != 0:
            fail("trace doctor external workspace smoke failed:\n" + trace.stdout[:2000])
        assert_contains(trace.stdout, "RedCap 路由追踪", "trace output")
        assert_contains(trace.stdout, "command: doctor", "trace output")
        forbidden_output_checks(trace.stdout, "trace output", workspace, task_file)
        assert_not_contains(trace.stdout, "PATH=", "trace output")
        assert_not_contains(trace.stdout, "HOME=", "trace output")

        for topic in ["status", "diagnose", "doctor", "debug"]:
            help_output = run([str(CLI), "help", topic], cwd=workspace)
            if help_output.returncode != 0:
                fail(f"help {topic} failed:\n" + help_output.stdout[:2000])
            assert_contains(help_output.stdout, f"redcap {topic}", f"help {topic} output")

        typo = run([str(CLI), "docter"], cwd=workspace)
        if typo.returncode != 2:
            fail(f"unknown command should exit 2, got {typo.returncode}:\n{typo.stdout[:2000]}")
        for needle in ["原因(cause):", "影响(impact):", "建议动作(suggested_action):", "redcap doctor"]:
            assert_contains(typo.stdout, needle, "unknown command output")

        missing_workspace = Path(tempfile.mkdtemp(prefix="redcap-cli-product-missing-")).resolve()
        missing = run([str(CLI), "doctor"], cwd=missing_workspace)
        if missing.returncode != 0:
            fail("doctor missing task file should degrade without failing:\n" + missing.stdout[:2000])
        assert_contains(missing.stdout, "RedCap 体检：可继续，但有提醒", "missing task doctor")
        assert_contains(missing.stdout, "没有找到当前任务卡", "missing task doctor")

        missing_debug = run([str(CLI), "debug", "--json"], cwd=missing_workspace)
        if missing_debug.returncode != 0:
            fail("debug missing task file should not fail:\n" + missing_debug.stdout[:2000])
        missing_payload = load_debug_json(missing_debug.stdout)
        validate_debug_payload(missing_payload, "", "external-workspace", "missing")

        env_debug = run(
            [str(CLI), "debug", "--json"],
            cwd=missing_workspace,
            env={"REDCAP_WORKSPACE": str(workspace)},
        )
        if env_debug.returncode != 0:
            fail("debug with REDCAP_WORKSPACE env failed:\n" + env_debug.stdout[:2000])
        env_payload = load_debug_json(env_debug.stdout)
        validate_debug_payload(env_payload, "fixture-cli-product-surface", "external-workspace", "exists")

        no_args = run([str(CLI)], cwd=workspace)
        if no_args.returncode != 2:
            fail(f"no-args usage should exit 2, got {no_args.returncode}:\n{no_args.stdout[:2000]}")
        for needle in ["doctor", "debug", "原因(cause):", "影响(impact):", "建议动作(suggested_action):"]:
            assert_contains(no_args.stdout, needle, "no-args output")


def run_self_development_smoke() -> None:
    doctor = run([str(CLI), "doctor", "--workspace", str(ROOT)], cwd=ROOT)
    if doctor.returncode != 0:
        fail("doctor self-development smoke failed:\n" + doctor.stdout[:2000])
    assert_contains(doctor.stdout, "运行方式：开发 RedCap 自身", "doctor self-development")

    debug = run([str(CLI), "debug", "--json", "--workspace", str(ROOT)], cwd=ROOT)
    if debug.returncode != 0:
        fail("debug self-development smoke failed:\n" + debug.stdout[:2000])
    forbidden_output_checks(debug.stdout, "self-development debug json")
    payload = load_debug_json(debug.stdout)
    if payload.get("boundary_mode") != "self-development":
        fail("self-development debug json must report self-development mode")


def main() -> None:
    policy = load_json(POLICY, "CLI product surface policy")
    validate_policy(policy)
    inspect_cli()
    run_external_workspace_smoke()
    run_self_development_smoke()
    print("CLI_PRODUCT_SURFACE_OK")


if __name__ == "__main__":
    main()

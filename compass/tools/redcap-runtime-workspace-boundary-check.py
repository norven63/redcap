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
POLICY = ROOT / "references/runtime-workspace-boundary-policy.json"
CLI = ROOT / "bin/redcap"
PRE_RELEASE_REVIEW = ROOT / "references/pre-release-product-architecture-review.json"
FIXTURE_TASK_ID = "fixture-external-workspace"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-runtime-workspace-boundary-check] {message}")


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


def command_branch(script: str, command: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(command)}\)\n(?P<body>.*?)(?=^\s*;;\n)", re.M | re.S)
    match = pattern.search(script)
    if not match:
        fail(f"CLI command branch missing: {command}")
    return match.group("body")


def task_id_from(path: Path) -> str:
    if not path.is_file():
        return ""
    match = re.search(r"^task_id:\s*(\S+)\s*$", path.read_text(encoding="utf-8", errors="replace"), re.M)
    return match.group(1).strip() if match else ""


def assert_fixture_output(output: str, label: str) -> None:
    if (
        f"task_id: {FIXTURE_TASK_ID}" not in output
        and f"task_id={FIXTURE_TASK_ID}" not in output
        and FIXTURE_TASK_ID not in output
        and "Fixture external workspace boundary top goal." not in output
    ):
        fail(f"{label} must receive the external workspace task file")


def assert_no_runtime_task_leak(output: str, runtime_task_id: str, label: str) -> None:
    if not runtime_task_id or runtime_task_id == FIXTURE_TASK_ID:
        return
    leak_needles = [
        f"task_id: {runtime_task_id}",
        f"task_id={runtime_task_id}",
    ]
    for needle in leak_needles:
        if needle in output:
            fail(f"{label} leaked the RedCap package-root task card: {runtime_task_id}")


def require_policy(policy: dict[str, Any]) -> None:
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "redcap-runtime-workspace-boundary":
        fail("policy_id mismatch")
    project = policy.get("project_layer")
    runtime = policy.get("runtime_layer")
    user = policy.get("user_layer")
    if not isinstance(project, dict) or not isinstance(runtime, dict) or not isinstance(user, dict):
        fail("policy must define runtime_layer, project_layer and user_layer")
    expected_project = {
        "workspace_default": "$PWD",
        "workspace_option": "--workspace",
        "workspace_env": "REDCAP_WORKSPACE",
        "task_file_default": "<workspace>/.dev-task.md",
        "task_file_option": "--task-file",
        "task_file_env": "REDCAP_TASK_FILE",
        "env": "REDCAP_WORKSPACE_ROOT",
    }
    for key, expected in expected_project.items():
        if project.get(key) != expected:
            fail(f"project_layer.{key} must be {expected}")
    if runtime.get("env") != "REDCAP_RUNTIME_ROOT":
        fail("runtime_layer.env must be REDCAP_RUNTIME_ROOT")
    if user.get("identity_anchor") != "~/.cap/identity.md":
        fail("user_layer.identity_anchor must remain outside the repository")
    commands = policy.get("workspace_oriented_commands")
    if commands != ["revive", "summary", "status", "diagnose", "change-intake", "closeout"]:
        fail("workspace_oriented_commands must be revive/summary/status/diagnose/change-intake/closeout")
    diagnostic_commands = policy.get("diagnostic_product_commands")
    if diagnostic_commands != ["doctor", "debug"]:
        fail("diagnostic_product_commands must be doctor/debug")
    guarantees = policy.get("required_guarantees")
    if not isinstance(guarantees, list) or len(guarantees) < 5:
        fail("required_guarantees must document the boundary contract")


def inspect_cli() -> None:
    if not CLI.is_file():
        fail("bin/redcap missing")
    script = CLI.read_text(encoding="utf-8")
    for needle in [
        "resolve_workspace_task_args()",
        "--workspace",
        "--task-file",
        "REDCAP_RUNTIME_ROOT",
        "REDCAP_WORKSPACE_ROOT",
        "REDCAP_CMD_TASK_FILE",
    ]:
        if needle not in script:
            fail(f"bin/redcap missing workspace contract: {needle}")

    for command in ["revive", "summary", "status", "diagnose", "change-intake", "doctor", "debug"]:
        body = command_branch(script, command)
        if "$REDCAP_ROOT/.dev-task.md" in body:
            fail(f"{command} still defaults to package-root .dev-task.md")
        if "resolve_workspace_task_args" not in body:
            fail(f"{command} must call resolve_workspace_task_args")
        if "REDCAP_CMD_TASK_FILE" not in body:
            fail(f"{command} must pass the resolved workspace task file")
    closeout_body = command_branch(script, "closeout")
    if "$REDCAP_ROOT/.dev-task.md" in closeout_body:
        fail("closeout still defaults to package-root .dev-task.md")
    if "resolve_workspace_options_only" not in closeout_body:
        fail("closeout must resolve workspace options before delegating")
    if "closeout-cap.sh" not in closeout_body:
        fail("closeout must continue delegating to closeout-cap.sh")


def run_external_workspace_smoke() -> None:
    with tempfile.TemporaryDirectory(prefix="redcap-workspace-boundary-") as tmp:
        workspace = Path(tmp).resolve()
        fixture = workspace / ".dev-task.md"
        runtime_task_id = task_id_from(ROOT / ".dev-task.md")
        fixture.write_text(
            """# 当前任务：workspace boundary fixture

## 控制面元数据（机器校验）
task_id: fixture-external-workspace
active_slice: runtime-workspace-boundary-fixture
top_goal: Fixture external workspace boundary top goal.
task_report: assets/docs/task-reports/2026-05-27-completion-semantics-hard-gate.md

## 原始输入（用户原文，禁止改写）

"Fixture external workspace boundary smoke."

## 已确认需求
- This fixture proves bin/redcap workspace-aware commands read the caller workspace task file.
""",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env.pop("REDCAP_TASK_FILE", None)
        env.pop("REDCAP_WORKSPACE", None)
        env.pop("REDCAP_WORKSPACE_ROOT", None)
        env["REDCAP_CURRENT_STATUS_REFRESH_AGENT_REGISTRY"] = "0"
        completed = subprocess.run(
            [str(CLI), "status"],
            cwd=workspace,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=60,
            check=False,
        )
        output = completed.stdout
        if completed.returncode != 0:
            fail("external workspace status smoke failed:\n" + output[:2000])
        required = [
            "task_id: fixture-external-workspace",
            f"runtime root: {ROOT}",
            f"workspace root: {workspace}",
            f"task file: {fixture} (exists)",
            "boundary mode: external-workspace",
        ]
        for needle in required:
            if needle not in output:
                fail(f"external workspace status missing: {needle}")
        assert_no_runtime_task_leak(output, runtime_task_id, "external workspace status")

        subdir = workspace / "src" / "module"
        subdir.mkdir(parents=True)
        completed = subprocess.run(
            [str(CLI), "status"],
            cwd=subdir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=60,
            check=False,
        )
        output = completed.stdout
        if completed.returncode != 0:
            fail("external workspace subdir status smoke failed:\n" + output[:2000])
        if f"workspace root: {workspace}" not in output or f"task_id: {FIXTURE_TASK_ID}" not in output:
            fail("subdirectory invocation must walk up to the workspace task file")
        assert_no_runtime_task_leak(output, runtime_task_id, "external workspace subdir status")

        def run_redcap(args: list[str], label: str, cwd: Path = workspace, extra_env: dict[str, str] | None = None) -> str:
            run_env = env.copy()
            if extra_env:
                run_env.update(extra_env)
            completed = subprocess.run(
                [str(CLI), *args],
                cwd=cwd,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=run_env,
                timeout=60,
                check=False,
            )
            output = completed.stdout
            if completed.returncode != 0:
                fail(f"{label} smoke failed:\n" + output[:2000])
            assert_no_runtime_task_leak(output, runtime_task_id, label)
            return output

        def assert_revive_uses_fixture(args: list[str], label: str, cwd: Path = workspace, extra_env: dict[str, str] | None = None) -> None:
            output = run_redcap(["revive", *args], f"external workspace revive ({label})", cwd=cwd, extra_env=extra_env)
            assert_fixture_output(output, f"revive ({label})")

        def assert_summary_uses_fixture(args: list[str], label: str, cwd: Path = workspace, extra_env: dict[str, str] | None = None) -> None:
            output = run_redcap(["summary", *args], f"summary workspace ({label})", cwd=cwd, extra_env=extra_env)
            assert_fixture_output(output, f"summary ({label})")

        assert_revive_uses_fixture([], "default")
        assert_revive_uses_fixture(["--workspace", str(workspace)], "workspace-option", cwd=ROOT)
        assert_revive_uses_fixture(["--task-file", str(fixture)], "task-file-option", cwd=ROOT)
        assert_revive_uses_fixture([], "workspace-env", cwd=ROOT, extra_env={"REDCAP_WORKSPACE": str(workspace)})
        assert_revive_uses_fixture([], "task-file-env", cwd=ROOT, extra_env={"REDCAP_TASK_FILE": str(fixture)})

        assert_summary_uses_fixture([], "default")
        assert_summary_uses_fixture(["--workspace", str(workspace)], "workspace-option", cwd=ROOT)
        assert_summary_uses_fixture(["--task-file", str(fixture)], "task-file-option", cwd=ROOT)
        assert_summary_uses_fixture([], "workspace-env", cwd=ROOT, extra_env={"REDCAP_WORKSPACE": str(workspace)})
        assert_summary_uses_fixture([], "task-file-env", cwd=ROOT, extra_env={"REDCAP_TASK_FILE": str(fixture)})

        completed = subprocess.run(
            [str(CLI), "closeout", "status"],
            cwd=workspace,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=60,
            check=False,
        )
        output = completed.stdout
        if completed.returncode != 0:
            fail("closeout status workspace smoke failed:\n" + output[:2000])
        if "fixture-external-workspace" not in output or str(fixture) not in output:
            fail("closeout status must receive the workspace task file")

        completed = subprocess.run(
            [str(CLI), "doctor"],
            cwd=workspace,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=60,
            check=False,
        )
        output = completed.stdout
        if completed.returncode != 0:
            fail("doctor workspace smoke failed:\n" + output[:2000])
        if "运行方式：外部项目工作区" not in output or "当前任务卡：exists" not in output:
            fail("doctor must use the caller workspace task file")

        completed = subprocess.run(
            [str(CLI), "debug", "--json"],
            cwd=workspace,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=60,
            check=False,
        )
        output = completed.stdout
        if completed.returncode != 0:
            fail("debug workspace smoke failed:\n" + output[:2000])
        try:
            debug_payload = json.loads(output)
        except json.JSONDecodeError as exc:
            fail(f"debug workspace smoke did not emit valid json: {exc}")
        if debug_payload.get("task_id") != "fixture-external-workspace":
            fail("debug must report the external workspace task_id")
        if debug_payload.get("boundary_mode") != "external-workspace":
            fail("debug must report external-workspace mode")


def inspect_pre_release_review() -> None:
    review = load_json(PRE_RELEASE_REVIEW, "pre-release product architecture review")
    facts = review.get("observed_facts")
    if not isinstance(facts, dict):
        fail("pre-release review observed_facts must be an object")
    if facts.get("cli_defaults_to_package_task_file") is not False:
        fail("pre-release review must record cli_defaults_to_package_task_file=false after P4-2b fix")
    findings = review.get("findings")
    if not isinstance(findings, list):
        fail("pre-release review findings must be a list")
    workspace_finding = next(
        (item for item in findings if isinstance(item, dict) and item.get("id") == "cli-workspace-context-not-separated"),
        None,
    )
    if not workspace_finding:
        fail("pre-release review missing cli-workspace-context-not-separated finding history")
    if workspace_finding.get("severity") != "pass":
        fail("cli-workspace-context-not-separated finding must be marked pass after this fix")
    if workspace_finding.get("required_before_public_release") is not False:
        fail("fixed workspace context finding must no longer be required_before_public_release")


def main() -> None:
    policy = load_json(POLICY, "runtime workspace boundary policy")
    require_policy(policy)
    inspect_cli()
    run_external_workspace_smoke()
    inspect_pre_release_review()
    print("RUNTIME_WORKSPACE_BOUNDARY_OK")


if __name__ == "__main__":
    main()

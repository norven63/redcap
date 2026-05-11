#!/usr/bin/env python3
# 用途：用真实命令样例验证 RedCap 人类可读产品表面；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#product-shape-and-retrieval

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "references/human-product-surface-policy.json"
CLI = ROOT / "bin/redcap"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-human-product-surface-check] {message}")


def load_policy() -> dict[str, Any]:
    if not POLICY.is_file():
        fail("missing human product surface policy")
    try:
        payload = json.loads(POLICY.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid policy json: {exc}")
    if not isinstance(payload, dict):
        fail("policy must be a JSON object")
    if payload.get("version") != 1:
        fail("policy version must be 1")
    if payload.get("policy_id") != "redcap-human-product-surface":
        fail("unexpected policy_id")
    return payload


def run(args: list[str], cwd: Path, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in [
        "REDCAP_TASK_FILE",
        "REDCAP_WORKSPACE",
        "REDCAP_WORKSPACE_ROOT",
        "REDCAP_CURRENT_STATUS_REFRESH_AGENT_REGISTRY",
    ]:
        env.pop(key, None)
    env["REDCAP_CURRENT_STATUS_REFRESH_AGENT_REGISTRY"] = "0"
    return subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        env=env,
        timeout=timeout,
    )


def run_partial(args: list[str], cwd: Path, timeout: int = 12) -> str:
    try:
        return run(args, cwd=cwd, timeout=timeout).stdout
    except subprocess.TimeoutExpired as exc:
        output = exc.output or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return str(output)


def require_phrases(text: str, phrases: list[str], label: str) -> None:
    missing = [phrase for phrase in phrases if phrase not in text]
    if missing:
        fail(f"{label} missing human-readable phrase(s): {', '.join(missing)}\n{text[:2000]}")


def forbid_terms(text: str, terms: list[str], label: str) -> None:
    leaked = [term for term in terms if term and term in text]
    if leaked:
        fail(f"{label} leaked internal term(s) in primary surface: {', '.join(leaked)}\n{text[:2000]}")


def before_marker(text: str, marker: str) -> str:
    if marker in text:
        return text.split(marker, 1)[0]
    return text


def create_fixture_workspace() -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
    tmp = tempfile.TemporaryDirectory(prefix="redcap-human-product-surface-")
    workspace = Path(tmp.name).resolve()
    report = workspace / "report.md"
    report.write_text(
        """# RASG-019 样例报告

## 0.1 当前已完成
- 已完成 CLI、状态和通知首屏的人类可读样例检查。

## 0.2 上一步完成的是
- 已完成任务卡重锚和输出样例审计。

## 0.3 下一步计划做的是
- 继续运行独立评审和回归验收。

## 0.4 整体计划脉络图与当前位置
- 历史债务治理 -> 当前发布前产品表面治理 -> 后续发布准备；当前位于输出表面加固阶段。

## 0.5 是否需要 Norven 人工介入
- 不需要。
""",
        encoding="utf-8",
    )
    task = workspace / ".dev-task.md"
    task.write_text(
        f"""# 当前任务：human product surface fixture

## 控制面元数据（机器校验）
task_id: fixture-human-product-surface
active_slice: fixture-human-readable-surface
task_report: {report}

## 原始输入（用户原文，禁止改写）
“fixture”

## 已确认需求（执行依据）

### R1: fixture
- 用于检查人类可读输出。

## 中插需求账本

| id | 触发 | 类型 | 阻塞当前任务 | 优先级 | 处理方式 | 确认需求更新 | 计划更新 | 验收更新 | 状态 | 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| U1 | fixture | authorization | yes | P1 | merge-current | yes | yes | yes | integrated | fixture |
""",
        encoding="utf-8",
    )
    return tmp, workspace, task


def validate_policy(policy: dict[str, Any]) -> None:
    required_keys = [
        "primary_human_surfaces",
        "required_primary_story_fields",
        "main_narrative_rule",
        "secondary_evidence_rule",
        "internal_terms",
        "primary_surface_forbidden_terms",
        "required_cli_phrases",
        "checker",
    ]
    for key in required_keys:
        if key not in policy:
            fail(f"policy missing key: {key}")
    for item in policy.get("internal_terms") or []:
        if not isinstance(item, dict) or not item.get("term") or not item.get("plain_language"):
            fail("internal_terms entries must define term and plain_language")
    if policy.get("checker") != "compass/tools/redcap-human-product-surface-check.sh":
        fail("policy checker path mismatch")
    if "new human-facing CLI command" not in str(policy.get("new_surface_update_rule", "")):
        fail("policy must define the update rule for newly added human-facing surfaces")


def validate_cli_surfaces(policy: dict[str, Any]) -> None:
    phrases = policy["required_cli_phrases"]
    forbidden = list(policy["primary_surface_forbidden_terms"])

    help_output = run([str(CLI), "help"], cwd=ROOT)
    if help_output.returncode != 0:
        fail("redcap help failed:\n" + help_output.stdout[:2000])
    require_phrases(help_output.stdout, phrases["help"], "redcap help")
    forbid_terms(help_output.stdout, forbidden, "redcap help")

    doctor = run([str(CLI), "doctor", "--workspace", str(ROOT)], cwd=ROOT)
    if doctor.returncode != 0:
        fail("redcap doctor failed:\n" + doctor.stdout[:2000])
    require_phrases(doctor.stdout, phrases["doctor"], "redcap doctor")
    forbid_terms(doctor.stdout, forbidden, "redcap doctor")

    fixture_tmp, workspace, task = create_fixture_workspace()
    try:
        status = run([str(CLI), "status", "--workspace", str(workspace), "--task-file", str(task)], cwd=workspace)
        if status.returncode != 0:
            fail("redcap status fixture failed:\n" + status.stdout[:2000])
        first_screen = before_marker(status.stdout, "## 当前任务锚点")
        require_phrases(first_screen, phrases["status_first_screen"], "redcap status first-screen")
        forbid_terms(first_screen, forbidden, "redcap status first-screen")

        diagnose_output = run_partial(
            [str(CLI), "diagnose", "--workspace", str(workspace), "--task-file", str(task)],
            cwd=workspace,
        )
        intro = before_marker(diagnose_output, "REDCAP_DIAGNOSE")
        require_phrases(intro, phrases["diagnose_intro"], "redcap diagnose introduction")
        forbid_terms(intro, forbidden, "redcap diagnose introduction")
    finally:
        fixture_tmp.cleanup()

    with tempfile.TemporaryDirectory(prefix="redcap-human-product-surface-missing-") as tmp:
        missing_workspace = Path(tmp).resolve()
        degraded = run([str(CLI), "doctor"], cwd=missing_workspace)
        if degraded.returncode != 0:
            fail("redcap doctor degraded fixture failed:\n" + degraded.stdout[:2000])
        require_phrases(degraded.stdout, phrases["doctor"], "redcap doctor degraded")
        require_phrases(degraded.stdout, ["没有找到当前任务卡"], "redcap doctor degraded")
        forbid_terms(degraded.stdout, forbidden, "redcap doctor degraded")

        missing_report_task = missing_workspace / ".dev-task.md"
        missing_report_task.write_text(
            """# 当前任务：missing report fixture

## 控制面元数据（机器校验）
task_id: fixture-missing-report
active_slice: fixture-missing-report-surface
task_report: /tmp/redcap-human-product-surface-report-does-not-exist.md

## 已确认需求
- 用于检查任务报告缺失时的首屏 fallback。
""",
            encoding="utf-8",
        )
        missing_status = run(
            [str(CLI), "status", "--workspace", str(missing_workspace), "--task-file", str(missing_report_task)],
            cwd=missing_workspace,
        )
        if missing_status.returncode != 0:
            fail("redcap status missing-report fixture failed:\n" + missing_status.stdout[:2000])
        missing_first_screen = before_marker(missing_status.stdout, "## 当前任务锚点")
        require_phrases(missing_first_screen, phrases["status_first_screen"], "redcap status missing-report first-screen")
        require_phrases(missing_first_screen, ["本轮任务报告尚未生成"], "redcap status missing-report first-screen")
        forbid_terms(missing_first_screen, forbidden, "redcap status missing-report first-screen")


def validate_feishu_surface(policy: dict[str, Any]) -> None:
    script = r'''
source compass/tools/redcap-notify-format.sh
redcap_build_completion_message \
  "RedCap 节点汇报" \
  "redcap" \
  "abc1234 feat(example): sample" \
  "acceptance" \
  "" \
  "$PWD"
'''
    result = subprocess.run(
        ["bash", "-lc", script],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=60,
    )
    if result.returncode != 0:
        fail("Feishu formatter sample failed:\n" + result.stdout[:2000])
    phrases = policy["required_cli_phrases"]["feishu"]
    require_phrases(result.stdout, phrases, "Feishu node-report")
    forbid_terms(result.stdout, list(policy["primary_surface_forbidden_terms"]), "Feishu node-report")


def main() -> None:
    policy = load_policy()
    validate_policy(policy)
    validate_cli_surfaces(policy)
    validate_feishu_surface(policy)
    print("HUMAN_PRODUCT_SURFACE_OK")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""RedCap 通用 E2E（端到端验收）运行器。"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REDCAP = REPO_ROOT / "runtime" / "bin" / "redcap"
CONTRACT = REPO_ROOT / "assets" / "contracts" / "complete-revival-e2e-acceptance-design.json"
REQUIRED_HOOK_EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"]
OLD_REDCAP_ROOT = pathlib.Path("/Users/norven/workspace/redcap")
GIT_IN_PROGRESS_MARKERS = [
    "MERGE_HEAD",
    "CHERRY_PICK_HEAD",
    "REVERT_HEAD",
    "BISECT_LOG",
    "rebase-merge",
    "rebase-apply",
]


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取 JSON：{path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON 必须是对象：{path}")
    return payload


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slugify(value: str) -> str:
    lowered = value.casefold()
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", lowered, flags=re.UNICODE).strip("-")
    if not slug:
        slug = "direction"
    return slug[:36].strip("-") or "direction"


def run_command(
    argv: list[str],
    *,
    cwd: pathlib.Path = REPO_ROOT,
    timeout_seconds: int = 180,
    stdin: str | None = None,
) -> dict[str, Any]:
    started = dt.datetime.now(dt.timezone.utc)
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
        return {
            "argv": argv,
            "cwd": str(cwd),
            "exit_code": completed.returncode,
            "ok": completed.returncode == 0,
            "timed_out": False,
            "timeout_seconds": timeout_seconds,
            "started_at": started.replace(microsecond=0).isoformat(),
            "finished_at": iso_now(),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "argv": argv,
            "cwd": str(cwd),
            "exit_code": 124,
            "ok": False,
            "timed_out": True,
            "timeout_seconds": timeout_seconds,
            "started_at": started.replace(microsecond=0).isoformat(),
            "finished_at": iso_now(),
            "stdout": stdout,
            "stderr": stderr,
        }


def command_receipt(result: dict[str, Any]) -> dict[str, Any]:
    stdout = str(result.get("stdout") or "")
    stderr = str(result.get("stderr") or "")
    return {
        "argv": result.get("argv"),
        "cwd": result.get("cwd"),
        "exit_code": result.get("exit_code"),
        "ok": result.get("ok"),
        "timed_out": result.get("timed_out"),
        "timeout_seconds": result.get("timeout_seconds"),
        "stdout_length": len(stdout),
        "stdout_sha256": sha256_text(stdout) if stdout else None,
        "stderr_length": len(stderr),
        "stderr_sha256": sha256_text(stderr) if stderr else None,
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
    }


def git_text(args: list[str]) -> tuple[bool, str, str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0, completed.stdout, completed.stderr


def git_path(name: str) -> pathlib.Path | None:
    ok, stdout, _ = git_text(["rev-parse", "--git-path", name])
    if not ok:
        return None
    return (REPO_ROOT / stdout.strip()).resolve()


def compact_status(status: str) -> dict[str, Any]:
    return {
        "length": len(status),
        "sha256": sha256_text(status),
        "tail": status[-2000:],
    }


def source_workspace_snapshot() -> dict[str, Any]:
    failures: list[str] = []
    branch_ok, branch, branch_err = git_text(["branch", "--show-current"])
    head_ok, head, head_err = git_text(["rev-parse", "HEAD"])
    status_ok, status, status_err = git_text(["status", "--porcelain=v1", "--untracked-files=all"])
    if not branch_ok:
        failures.append(f"无法读取当前分支：{branch_err.strip()}")
    if not head_ok:
        failures.append(f"无法读取当前提交：{head_err.strip()}")
    if not status_ok:
        failures.append(f"无法读取工作区状态：{status_err.strip()}")
    in_progress: list[str] = []
    for marker in GIT_IN_PROGRESS_MARKERS:
        path = git_path(marker)
        if path is not None and path.exists():
            in_progress.append(marker)
    return {
        "schema_id": "redcap-source-workspace-snapshot",
        "ok": not failures,
        "root": str(REPO_ROOT),
        "branch": branch.strip(),
        "head": head.strip(),
        "status": compact_status(status),
        "in_progress": sorted(in_progress),
        "failures": failures,
    }


def compare_source_workspace(before: dict[str, Any]) -> dict[str, Any]:
    after = source_workspace_snapshot()
    failures: list[str] = []
    if not before.get("ok"):
        failures.append(f"执行前无法建立源工作区基线：{before.get('failures')}")
    if not after.get("ok"):
        failures.append(f"执行后无法读取源工作区状态：{after.get('failures')}")
    for field in ["branch", "head", "in_progress"]:
        if before.get(field) != after.get(field):
            failures.append(f"源工作区 {field} 发生变化")
    before_status = before.get("status") if isinstance(before.get("status"), dict) else {}
    after_status = after.get("status") if isinstance(after.get("status"), dict) else {}
    if before_status.get("sha256") != after_status.get("sha256"):
        failures.append("源工作区文件状态发生变化")
    return {
        "schema_id": "redcap-source-workspace-guard",
        "ok": not failures,
        "before": {
            "branch": before.get("branch"),
            "head": before.get("head"),
            "status": before_status,
            "in_progress": before.get("in_progress"),
        },
        "after": {
            "branch": after.get("branch"),
            "head": after.get("head"),
            "status": after_status,
            "in_progress": after.get("in_progress"),
        },
        "failures": failures,
    }


def attach_source_workspace_guard(result: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    guard = compare_source_workspace(before)
    result["source_workspace_guard"] = guard
    if not guard["ok"]:
        result["ok"] = False
        failures = result.setdefault("failures", [])
        if isinstance(failures, list):
            failures.append(f"RedCap 源工作区保护失败：{guard['failures']}")
    return result


def source_workspace_guard_negative_probe() -> dict[str, Any]:
    before = source_workspace_snapshot()
    fixture = REPO_ROOT / ".redcap-e2e-source-guard-fixture"
    detected = {"ok": False, "failures": ["负向探针未执行"]}
    restored = {"ok": False, "failures": ["负向探针未清理"]}
    try:
        fixture.write_text("redcap source workspace guard fixture\n", encoding="utf-8")
        detected = compare_source_workspace(before)
    finally:
        if fixture.exists():
            fixture.unlink()
        restored = compare_source_workspace(before)
    return {
        "schema_id": "redcap-source-workspace-guard-negative-probe",
        "ok": detected.get("ok") is False and restored.get("ok") is True,
        "detected_mutation": detected,
        "restored_baseline": restored,
        "failures": [] if detected.get("ok") is False and restored.get("ok") is True else ["源工作区污染负向探针未按预期工作或未恢复基线"],
    }


def resolve_work_root(raw: str | None) -> pathlib.Path:
    if raw:
        return pathlib.Path(raw).expanduser().resolve()
    return pathlib.Path(tempfile.mkdtemp(prefix="redcap-ai-e2e-")).resolve()


def ensure_external_path(path: pathlib.Path) -> list[str]:
    failures: list[str] = []
    resolved = path.resolve()
    try:
        resolved.relative_to(REPO_ROOT)
        failures.append(f"工作目录不能位于 RedCap 源仓库内部：{resolved}")
    except ValueError:
        pass
    if OLD_REDCAP_ROOT.exists():
        try:
            resolved.relative_to(OLD_REDCAP_ROOT.resolve())
            failures.append(f"工作目录不能位于旧 RedCap 仓库内部：{resolved}")
        except ValueError:
            pass
    return failures


def direction_from_args(args: argparse.Namespace) -> str:
    direction = getattr(args, "direction", None)
    direction_file = getattr(args, "direction_file", None)
    if direction_file:
        direction = pathlib.Path(direction_file).expanduser().read_text(encoding="utf-8")
    return (direction or "").strip()


def filesystem_manifest(root: pathlib.Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(root).as_posix()
        if ".git/" in rel:
            continue
        records.append({
            "path": rel,
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return records


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-complete-revival-e2e-acceptance-design":
        failures.append("E2E 合同 schema_id 错误")
    if contract.get("status") != "executable_generic_methodology":
        failures.append("E2E 合同必须声明 executable_generic_methodology")
    if "fixed_sandbox_task" in contract:
        failures.append("E2E 合同不得包含 fixed_sandbox_task")
    text = json.dumps(contract, ensure_ascii=False)
    forbidden_fixed_terms = ["external-task-ledger-cli", "task-ledger", "任务账本命令行工具"]
    leaked = [term for term in forbidden_fixed_terms if term in text]
    if leaked:
        failures.append(f"E2E 合同仍包含固定场景词：{leaked}")
    commands = {item.get("name") for item in contract.get("commands", []) if isinstance(item, dict)}
    for required in [
        "runtime/bin/redcap complete-revival-e2e design-check",
        "runtime/bin/redcap complete-revival-e2e prepare --direction <text> --work-root <external-dir>",
        "runtime/bin/redcap complete-revival-e2e carrier-probe --work-root <external-dir>",
        "runtime/bin/redcap complete-revival-e2e run --direction <text> --work-root <external-dir>",
        "runtime/bin/redcap complete-revival-e2e self-check",
    ]:
        if required not in commands:
            failures.append(f"E2E 合同缺少命令定义：{required}")
    roles = contract.get("roles")
    if not isinstance(roles, dict):
        failures.append("E2E 合同缺少 roles")
    else:
        for role in ["cap_requester", "codex_cli_implementer", "cap_acceptor"]:
            if role not in roles:
                failures.append(f"E2E 合同缺少角色：{role}")
        hooks = roles.get("codex_cli_implementer", {}).get("required_hooks") if isinstance(roles.get("codex_cli_implementer"), dict) else []
        missing_hooks = [event for event in REQUIRED_HOOK_EVENTS if event not in hooks]
        if missing_hooks:
            failures.append(f"Codex CLI 承接方缺少 hook 要求：{missing_hooks}")
    phases = [item.get("phase") for item in contract.get("workflow_template", []) if isinstance(item, dict)]
    for phase in ["direction_intake", "architecture_design", "implementation", "quality_assurance", "review_and_acceptance"]:
        if phase not in phases:
            failures.append(f"E2E 工作流缺少阶段：{phase}")
    probes = {item.get("id") for item in contract.get("negative_probes", []) if isinstance(item, dict)}
    for required_probe in [
        "missing-direction-cannot-run",
        "fixed-scenario-cannot-pass-design-check",
        "redcap-root-pollution-cannot-pass",
        "source-workspace-mutation-cannot-pass",
        "hook-carrier-missing-cannot-pass",
        "report-only-cannot-pass",
    ]:
        if required_probe not in probes:
            failures.append(f"E2E 合同缺少负向探针：{required_probe}")
    return failures


def package_and_init(project: pathlib.Path, evidence: pathlib.Path) -> dict[str, Any]:
    package_path = evidence / "redcap-package.zip"
    package_result = run_command([str(REDCAP), "project-install", "package", "--out", str(package_path)], timeout_seconds=180)
    if not package_result["ok"]:
        return {"ok": False, "step": "package", "command": command_receipt(package_result)}
    audit_result = run_command([str(REDCAP), "project-install", "audit-package", "--package", str(package_path)], timeout_seconds=180)
    if not audit_result["ok"]:
        return {
            "ok": False,
            "step": "audit-package",
            "package": str(package_path),
            "package_command": command_receipt(package_result),
            "audit_command": command_receipt(audit_result),
        }
    with zipfile.ZipFile(package_path) as archive:
        archive.extractall(project)
    runtime_bin = project / ".redcap" / "runtime" / "bin" / "redcap"
    init_result = run_command([
        "bash",
        str(runtime_bin),
        "project-install",
        "init",
        "--project",
        str(project),
    ], cwd=project, timeout_seconds=180)
    return {
        "ok": init_result["ok"],
        "step": "init",
        "package": str(package_path),
        "package_command": command_receipt(package_result),
        "audit_command": command_receipt(audit_result),
        "init_command": command_receipt(init_result),
    }


def build_requirements(direction: str) -> dict[str, Any]:
    return {
        "schema_id": "redcap-e2e-requirements",
        "created_at": iso_now(),
        "direction": direction,
        "cap_expanded_need": f"围绕“{direction}”交付一个可在本地运行、可检查、可维护的小型工程成果。",
        "scope": [
            "实现真实可运行产物，不只写文档",
            "提供清晰启动方式",
            "提供自动或半自动验证命令",
            "把 RedCap 运行证据保存在项目 .redcap 内"
        ],
        "non_goals": [
            "外网部署",
            "真实账号或私密凭据接入",
            "不可回滚的系统级修改"
        ],
        "quality_bar": [
            "实现方必须先读 .redcap/evidence/e2e/requirements.json",
            "实现方必须生成 architecture.md 和 test-results.json",
            "实现方必须在完成前运行验证命令并记录结果",
            "实现方不能把无法完成的事项标为完成"
        ]
    }


def build_acceptance(direction: str) -> dict[str, Any]:
    return {
        "schema_id": "redcap-e2e-acceptance-criteria",
        "direction_sha256": sha256_text(direction),
        "criteria": [
            "外部项目根目录包含真实交付文件",
            "存在可执行或可打开的入口说明",
            "存在 architecture.md，说明结构、边界、风险和测试方式",
            ".redcap/evidence/e2e 中存在实现日志、测试结果、文件清单和验收摘要",
            "如果实现方遇到阻塞，必须写 blocked-package.json，而不是写 completion-marker.json"
        ],
        "completion_marker_rule": "只有客观证据全部通过时，才允许写 .redcap/evidence/e2e/completion-marker.json。"
    }


def build_implementer_prompt(project: pathlib.Path, direction: str) -> str:
    return textwrap.dedent(f"""
    你是独立实现方，正在接受 RedCap E2E（端到端验收）测试。

    需求方向：
    {direction}

    工作目录：
    {project}

    必须遵守：
    1. 先阅读 .redcap/evidence/e2e/requirements.json 和 .redcap/evidence/e2e/acceptance-criteria.json。
    2. 在外部项目根目录内实现真实交付物，不要修改 RedCap 源仓库。
    3. 产出 architecture.md，说明方案、目录结构、运行方式、验证方式和风险。
    4. 运行你认为合适的验证命令，并把结果写入 .redcap/evidence/e2e/test-results.json。
    5. 写入 .redcap/evidence/e2e/implementation-log.json，记录你做了什么。
    6. 如果因为权限、网络、账号、环境缺失无法完成，写 .redcap/evidence/e2e/blocked-package.json，并说明阻塞条件。
    7. 只有真实交付和验证都完成时，才写 .redcap/evidence/e2e/completion-marker.json。

    最后请用中文简要说明：完成了什么、验证命令是什么、证据文件在哪里。
    """).strip() + "\n"


def prepare_project(direction: str, work_root: pathlib.Path, project_name: str | None = None) -> dict[str, Any]:
    guard_before = source_workspace_snapshot()
    failures = ensure_external_path(work_root)
    if not direction.strip():
        failures.append("缺少 direction：真实 E2E 必须由一个大致需求方向驱动")
    if failures:
        return attach_source_workspace_guard({"ok": False, "failures": failures}, guard_before)
    work_root.mkdir(parents=True, exist_ok=True)
    project = (work_root / (project_name or f"redcap-e2e-{slugify(direction)}")).resolve()
    if project.exists():
        shutil.rmtree(project)
    project.mkdir(parents=True)
    evidence = project / ".redcap" / "evidence" / "e2e"
    evidence.mkdir(parents=True, exist_ok=True)
    install_result = package_and_init(project, evidence)
    if not install_result.get("ok"):
        return attach_source_workspace_guard({
            "ok": False,
            "failures": ["项目级 .redcap 安装失败"],
            "install": install_result,
            "project": str(project),
        }, guard_before)
    evidence.mkdir(parents=True, exist_ok=True)
    requirements = build_requirements(direction)
    acceptance = build_acceptance(direction)
    prompt = build_implementer_prompt(project, direction)
    write_json(evidence / "requirements.json", requirements)
    write_json(evidence / "acceptance-criteria.json", acceptance)
    (evidence / "architecture-template.md").write_text(
        "# 架构设计\n\n## 目标\n\n## 目录结构\n\n## 运行方式\n\n## 验证方式\n\n## 风险与回滚\n",
        encoding="utf-8",
    )
    (evidence / "implementer-prompt.md").write_text(prompt, encoding="utf-8")
    write_json(evidence / "review-verdict-template.json", {
        "schema_id": "redcap-e2e-review-verdict",
        "status": "pending",
        "must_check": [
            "requirements_covered",
            "deliverables_exist",
            "verification_ran",
            "hook_events_present",
            "runtime_artifacts_inside_project_redcap"
        ]
    })
    append_jsonl(evidence / "workflow-events.jsonl", {
        "event": "direction_intake",
        "recorded_at": iso_now(),
        "direction_sha256": sha256_text(direction),
        "project": str(project),
    })
    manifest = {
        "schema_id": "redcap-ai-e2e-manifest",
        "created_at": iso_now(),
        "project": str(project),
        "work_root": str(work_root),
        "direction_sha256": sha256_text(direction),
        "redcap_package_installed": True,
        "hook_config": str(project / ".codex" / "hooks.json"),
        "evidence_root": str(evidence),
        "required_after_prepare": load_json(CONTRACT)["raw_evidence_package"]["required_files_after_prepare"],
        "install": install_result,
    }
    write_json(evidence / "manifest.json", manifest)
    write_json(evidence / "filesystem-before.json", {"files": filesystem_manifest(project)})
    result = {
        "ok": True,
        "schema_id": "redcap-ai-e2e-prepare-result",
        "project": str(project),
        "evidence_root": str(evidence),
        "implementer_prompt": str(evidence / "implementer-prompt.md"),
        "manifest": str(evidence / "manifest.json"),
        "failures": [],
    }
    result = attach_source_workspace_guard(result, guard_before)
    write_json(evidence / "source-workspace-guard.json", result["source_workspace_guard"])
    return result


def parse_hook_events(path: pathlib.Path) -> list[str]:
    if not path.exists():
        return []
    events: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("event"), str):
            events.append(payload["event"])
    return events


def carrier_probe(work_root: pathlib.Path, timeout_seconds: int = 240) -> dict[str, Any]:
    guard_before = source_workspace_snapshot()
    failures = ensure_external_path(work_root)
    if failures:
        return attach_source_workspace_guard({"ok": False, "failures": failures}, guard_before)
    work_root.mkdir(parents=True, exist_ok=True)
    project = (work_root / "redcap-e2e-carrier-probe").resolve()
    if project.exists():
        shutil.rmtree(project)
    (project / ".codex").mkdir(parents=True)
    (project / ".redcap" / "evidence" / "e2e").mkdir(parents=True)
    hook_script = project / ".redcap" / "hook_probe.py"
    events_path = project / ".redcap" / "evidence" / "e2e" / "carrier-hook-events.jsonl"
    hook_script.write_text(textwrap.dedent(f"""\
        #!/usr/bin/env python3
        import argparse, datetime as dt, hashlib, json, pathlib, sys
        parser = argparse.ArgumentParser()
        parser.add_argument('--event', required=True)
        args = parser.parse_args()
        raw = sys.stdin.read()
        path = pathlib.Path({str(events_path)!r})
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps({{
                'event': args.event,
                'recorded_at': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
                'stdin_length': len(raw),
                'stdin_sha256': hashlib.sha256(raw.encode('utf-8')).hexdigest() if raw else None
            }}, ensure_ascii=False, sort_keys=True) + '\\n')
        print(json.dumps({{'continue': True}}, ensure_ascii=False))
        """), encoding="utf-8")
    hook_script.chmod(0o755)
    def hook(event: str) -> dict[str, Any]:
        return {
            "type": "command",
            "command": f"/usr/bin/python3 {str(hook_script)!r} --event {event}",
            "timeout": 10,
            "statusMessage": f"RedCap E2E carrier probe {event}",
        }
    (project / ".codex" / "hooks.json").write_text(json.dumps({
        "hooks": {
            "SessionStart": [{"matcher": "startup|resume|clear|compact", "hooks": [hook("SessionStart")]}],
            "UserPromptSubmit": [{"hooks": [hook("UserPromptSubmit")]}],
            "PreToolUse": [{"matcher": "Bash|apply_patch|Edit|Write", "hooks": [hook("PreToolUse")]}],
            "PostToolUse": [{"matcher": ".*", "hooks": [hook("PostToolUse")]}],
            "Stop": [{"hooks": [hook("Stop")]}],
        }
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    last_message = project / ".redcap" / "evidence" / "e2e" / "carrier-last-message.txt"
    result = run_command([
        "codex",
        "exec",
        "--cd",
        str(project),
        "--skip-git-repo-check",
        "--sandbox",
        "workspace-write",
        "--full-auto",
        "--output-last-message",
        str(last_message),
        "请使用 shell 执行 pwd，然后最终只回答 carrier-probe-ok。",
    ], cwd=project, timeout_seconds=timeout_seconds)
    events = parse_hook_events(events_path)
    missing = [event for event in REQUIRED_HOOK_EVENTS if event not in events]
    probe = {
        "schema_id": "redcap-ai-e2e-carrier-probe",
        "ok": result["ok"] and not missing,
        "project": str(project),
        "events_path": str(events_path),
        "events": events,
        "missing_events": missing,
        "command": command_receipt(result),
        "last_message": str(last_message),
        "failures": [],
    }
    if not result["ok"]:
        probe["failures"].append("Codex CLI 承载探针命令失败")
    if missing:
        probe["failures"].append(f"Codex CLI 没有触发全部项目级 hook：{missing}")
    probe = attach_source_workspace_guard(probe, guard_before)
    write_json(project / ".redcap" / "evidence" / "e2e" / "carrier-probe.json", probe)
    return probe


def run_e2e(direction: str, work_root: pathlib.Path, timeout_seconds: int = 900) -> dict[str, Any]:
    prepared = prepare_project(direction, work_root)
    if not prepared.get("ok"):
        return prepared
    project = pathlib.Path(str(prepared["project"]))
    evidence = pathlib.Path(str(prepared["evidence_root"]))
    guard_before = source_workspace_snapshot()
    prompt_path = evidence / "implementer-prompt.md"
    last_message = evidence / "codex-last-message.txt"
    result = run_command([
        "codex",
        "exec",
        "--cd",
        str(project),
        "--skip-git-repo-check",
        "--sandbox",
        "workspace-write",
        "--full-auto",
        "--output-last-message",
        str(last_message),
        prompt_path.read_text(encoding="utf-8"),
    ], cwd=project, timeout_seconds=timeout_seconds)
    write_json(evidence / "codex-run.json", command_receipt(result))
    write_json(evidence / "filesystem-after.json", {"files": filesystem_manifest(project)})
    hook_events = parse_hook_events(project / ".redcap" / "assets" / "evidence" / "host-hooks" / "codex" / "events.jsonl")
    missing_hooks = [event for event in REQUIRED_HOOK_EVENTS if event not in hook_events]
    write_json(evidence / "hook-events-summary.json", {
        "schema_id": "redcap-e2e-hook-events-summary",
        "events": hook_events,
        "missing_events": missing_hooks,
    })
    completion_marker = evidence / "completion-marker.json"
    summary = {
        "schema_id": "redcap-ai-e2e-run-result",
        "ok": result["ok"] and not missing_hooks and completion_marker.exists(),
        "project": str(project),
        "evidence_root": str(evidence),
        "codex_cli_ok": result["ok"],
        "hook_events_ok": not missing_hooks,
        "completion_marker_present": completion_marker.exists(),
        "failures": [],
    }
    if not result["ok"]:
        summary["failures"].append("Codex CLI 独立承接方执行失败")
    if missing_hooks:
        summary["failures"].append(f"缺少项目级 hook 事件：{missing_hooks}")
    if not completion_marker.exists():
        summary["failures"].append("实现方没有写入 completion-marker.json；这可能表示任务未完成或被阻塞")
    summary = attach_source_workspace_guard(summary, guard_before)
    (evidence / "e2e-acceptance-summary.md").write_text(
        "# RedCap E2E 验收摘要\n\n"
        f"- 项目：{project}\n"
        f"- Codex CLI 执行：{'通过' if result['ok'] else '失败'}\n"
        f"- Hook 事件：{'通过' if not missing_hooks else '缺失 ' + ', '.join(missing_hooks)}\n"
        f"- 完成标记：{'存在' if completion_marker.exists() else '不存在'}\n",
        encoding="utf-8",
    )
    write_json(evidence / "source-workspace-guard-run.json", summary["source_workspace_guard"])
    write_json(evidence / "run-summary.json", summary)
    return summary


def cmd_design_check(_: argparse.Namespace) -> int:
    result = {
        "schema_id": "redcap-ai-e2e-design-check",
        "ok": True,
        "contract": str(CONTRACT),
        "failures": validate_contract(load_json(CONTRACT)),
    }
    result["ok"] = not result["failures"]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_AI_E2E_DESIGN_OK")
        return 0
    return 1


def cmd_prepare(args: argparse.Namespace) -> int:
    result = prepare_project(direction_from_args(args), resolve_work_root(args.work_root), args.project_name)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok"):
        print("REDCAP_AI_E2E_PREPARE_OK")
        return 0
    return 1


def cmd_carrier_probe(args: argparse.Namespace) -> int:
    result = carrier_probe(resolve_work_root(args.work_root), args.timeout_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok"):
        print("REDCAP_AI_E2E_CARRIER_PROBE_OK")
        return 0
    return 1


def cmd_run(args: argparse.Namespace) -> int:
    result = run_e2e(direction_from_args(args), resolve_work_root(args.work_root), args.timeout_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok"):
        print("REDCAP_AI_E2E_RUN_OK")
        return 0
    return 1


def cmd_self_check(args: argparse.Namespace) -> int:
    failures: list[str] = []
    if validate_contract(load_json(CONTRACT)):
        failures.append("通用 E2E 合同检查失败")
    with tempfile.TemporaryDirectory(prefix="redcap-ai-e2e-self-check-") as raw:
        work_root = pathlib.Path(raw).resolve()
        missing_direction = prepare_project("", work_root / "missing")
        if missing_direction.get("ok") is True:
            failures.append("缺失 direction 的 prepare 没有失败")
        prepared = prepare_project("自检方向：交付一个本地可验证的小型工具", work_root / "prepare")
        if prepared.get("ok") is not True:
            failures.append(f"prepare 正向探针失败：{prepared.get('failures')}")
        else:
            evidence = pathlib.Path(str(prepared["evidence_root"]))
            for rel in load_json(CONTRACT)["raw_evidence_package"]["required_files_after_prepare"]:
                if not (evidence / rel).exists():
                    failures.append(f"prepare 后缺少证据文件：{rel}")
        guard_probe = source_workspace_guard_negative_probe()
        if guard_probe.get("ok") is not True:
            failures.append(f"源工作区保护负向探针失败：{guard_probe.get('failures')}")
        if not args.skip_carrier_probe:
            probe = carrier_probe(work_root / "carrier", args.timeout_seconds)
            if probe.get("ok") is not True:
                failures.append(f"Codex CLI 承载探针失败：{probe.get('failures')}")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_AI_E2E_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap 通用纯 AI E2E 运行器")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("design-check").set_defaults(func=cmd_design_check)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--direction")
    prepare.add_argument("--direction-file")
    prepare.add_argument("--work-root")
    prepare.add_argument("--project-name")
    prepare.set_defaults(func=cmd_prepare)
    carrier = sub.add_parser("carrier-probe")
    carrier.add_argument("--work-root")
    carrier.add_argument("--timeout-seconds", type=int, default=240)
    carrier.set_defaults(func=cmd_carrier_probe)
    run = sub.add_parser("run")
    run.add_argument("--direction")
    run.add_argument("--direction-file")
    run.add_argument("--work-root")
    run.add_argument("--timeout-seconds", type=int, default=900)
    run.set_defaults(func=cmd_run)
    self_check = sub.add_parser("self-check")
    self_check.add_argument("--skip-carrier-probe", action="store_true")
    self_check.add_argument("--timeout-seconds", type=int, default=240)
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

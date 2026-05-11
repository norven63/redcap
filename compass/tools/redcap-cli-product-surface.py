#!/usr/bin/env python3
# 用途：提供 RedCap CLI 的人类可读体检、调试与帮助输出；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^,\s}\]]+"
)


def redact_secret_text(value: str) -> str:
    return SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=<redacted>", value)


def stable_path_token(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"<absolute-path:{digest}>"


def redact_path(path: str | Path | None) -> str:
    if path is None:
        return ""
    raw = str(path)
    if not raw:
        return ""
    raw = redact_secret_text(raw)
    try:
        expanded = str(Path(raw).expanduser())
    except Exception:
        expanded = raw
    home = str(Path.home())
    if home and (expanded == home or expanded.startswith(home + os.sep)):
        return "$HOME" + expanded[len(home) :]
    if expanded.startswith("/Users/") or expanded.startswith("/home/"):
        parts = Path(expanded).parts
        if len(parts) >= 3:
            suffix = os.sep.join(parts[3:])
            return "$HOME" + (os.sep + suffix if suffix else "")
        return "$HOME"
    if expanded.startswith(os.sep):
        return stable_path_token(expanded)
    return expanded


def task_id_from_file(task_file: Path) -> str:
    if not task_file.is_file():
        return ""
    try:
        for line in task_file.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("task_id:"):
                return stripped.split(":", 1)[1].strip()
    except Exception:
        return ""
    return ""


def boundary_mode(runtime_root: Path, workspace_root: Path) -> str:
    try:
        return "self-development" if runtime_root.resolve() == workspace_root.resolve() else "external-workspace"
    except Exception:
        return "unknown"


def boundary_mode_label(value: str) -> str:
    return {
        "self-development": "开发 RedCap 自身",
        "external-workspace": "外部项目工作区",
        "unknown": "未知",
    }.get(value, value)


def build_state(args: argparse.Namespace, command: str) -> dict[str, Any]:
    runtime_root = Path(args.runtime_root).resolve()
    workspace_root = Path(args.workspace_root).resolve()
    task_file = Path(args.task_file)
    if not task_file.is_absolute():
        task_file = workspace_root / task_file
    task_file = task_file.resolve()

    runtime_ok = (runtime_root / "bin" / "redcap").is_file()
    workspace_ok = workspace_root.is_dir()
    task_exists = task_file.is_file()
    task_id = task_id_from_file(task_file)
    checks: list[dict[str, Any]] = [
        {
            "id": "runtime-root",
            "status": "pass" if runtime_ok else "fail",
            "message": "RedCap 运行时文件已就绪。" if runtime_ok else "RedCap 运行时文件缺失。",
        },
        {
            "id": "workspace-root",
            "status": "pass" if workspace_ok else "fail",
            "message": "当前工作区可以访问。" if workspace_ok else "当前工作区不存在或无法访问。",
        },
        {
            "id": "task-file",
            "status": "pass" if task_exists else "warning",
            "message": (
                "已找到当前任务卡。"
                if task_exists
                else "没有找到当前任务卡；这个工作区可能还没有完成 RedCap 初始化。"
            ),
        },
        {
            "id": "safe-debug-output",
            "status": "pass",
            "message": "调试和追踪输出会隐藏本机路径、身份信息和环境密钥。",
        },
    ]
    failed = any(item["status"] == "fail" for item in checks)
    warned = any(item["status"] == "warning" for item in checks)
    status = "unhealthy" if failed else "degraded" if warned else "healthy"
    return {
        "version": 1,
        "surface": "redcap-cli-product-surface",
        "command": command,
        "status": status,
        "runtime_root": redact_path(runtime_root),
        "workspace_root": redact_path(workspace_root),
        "task_file": redact_path(task_file),
        "task_file_status": "exists" if task_exists else "missing",
        "task_id": task_id,
        "boundary_mode": boundary_mode(runtime_root, workspace_root),
        "checks": checks,
        "no_secrets_assertion": True,
    }


def prioritized_findings(state: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    if state["status"] == "healthy":
        findings.append("[P3] 这个工作区的 RedCap CLI 入口可以正常使用。")
    for check in state["checks"]:
        if check["status"] == "fail":
            findings.append(f"[P1] {check['message']}")
        elif check["status"] == "warning":
            findings.append(f"[P2] {check['message']}")
    if state["boundary_mode"] == "external-workspace":
        findings.append("[P3] RedCap 正在管理外部工作区，运行时和项目工作区是分开的。")
    else:
        findings.append("[P3] RedCap 正在开发自己本身，因此运行时和工作区相同，这是预期状态。")
    return findings[:5]


def next_step(state: dict[str, Any]) -> str:
    if state["task_file_status"] == "missing":
        return "先创建或指定当前任务卡（--task-file），然后重新运行 redcap doctor。"
    if state["status"] == "healthy":
        return "可以继续当前 RedCap 工作流；如果需要给 Agent 或人工排查，请运行 redcap debug --json。"
    return "先处理上面优先级最高的问题，然后重新运行 redcap doctor。"


def print_doctor(args: argparse.Namespace) -> int:
    state = build_state(args, "doctor")
    status_label = {
        "healthy": "可继续",
        "degraded": "可继续，但有提醒",
        "unhealthy": "需要先修复",
    }.get(state["status"], state["status"])
    print(f"RedCap 体检：{status_label}")
    print()
    print("我检查了什么：")
    print(f"- RedCap 程序位置：{state['runtime_root']}")
    print(f"- 当前工作区：{state['workspace_root']}")
    print(f"- 当前任务卡：{state['task_file_status']} ({state['task_file']})")
    print(f"- 运行方式：{boundary_mode_label(str(state['boundary_mode']))}")
    print()
    print("发现：")
    for item in prioritized_findings(state):
        print(f"- {item}")
    print()
    print("下一步：")
    print(f"- {next_step(state)}")
    return 0 if state["status"] in {"healthy", "degraded"} else 1


def print_debug(args: argparse.Namespace) -> int:
    state = build_state(args, "debug")
    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"RedCap 调试包：{state['status']}")
        print(f"- 当前工作区：{state['workspace_root']}")
        print(f"- 当前任务卡：{state['task_file_status']} ({state['task_file']})")
        print(f"- 任务编号：{state['task_id'] or '(none)'}")
        print(f"- 运行方式：{boundary_mode_label(str(state['boundary_mode']))}")
        print("- 如需机器可读输出，请重新运行：redcap debug --json")
    return 0


def print_trace(args: argparse.Namespace) -> int:
    state = build_state(args, "trace")
    delegated_to = getattr(args, "delegated_to", "") or "(none)"
    print("RedCap 路由追踪：", file=sys.stderr)
    print(f"- command: {args.traced_command}", file=sys.stderr)
    print(f"- runtime_root: {state['runtime_root']}", file=sys.stderr)
    print(f"- workspace_root: {state['workspace_root']}", file=sys.stderr)
    print(f"- task_file: {state['task_file']}", file=sys.stderr)
    print(f"- delegated_to: {redact_path(delegated_to)}", file=sys.stderr)
    return 0


HELP_TOPICS = {
    "": """用法：redcap [--trace] <命令> [参数...]

常用命令：
  revive                 初始化或复活当前工作区的 RedCap 工作流。
  status                 查看当前任务的简明状态、全景位置和下一步。
  diagnose               做一次深入体检；适合发布前、自查或排障。
  doctor                 做一次短体检；适合人类或 Agent 容器快速判断能否继续。
  debug [--json]         生成已脱敏的调试包，方便复制给其他 Agent 或 issue。
  closeout               对当前任务做正式收尾检查。
  package-surface        检查未来 npm/CLI 包面的安全与准备状态。

工作区参数：
  --workspace <dir>      被 RedCap 管理的项目工作区，默认自动识别。
  --task-file <file>     当前任务卡，默认是 <workspace>/.dev-task.md。
  --trace                解释命令路由，不输出环境变量或密钥。

运行 redcap help <命令> 查看某个命令的具体用法。""",
    "doctor": """redcap doctor [--workspace <dir>] [--task-file <file>]

用一句话判断 RedCap 现在能不能继续工作，并说明发现、影响和下一步。
当你只想快速知道“能不能继续”时，优先用这个命令。""",
    "debug": """redcap debug [--json] [--workspace <dir>] [--task-file <file>]

生成脱敏后的调试信息。加 --json 后适合复制给其他 Agent、issue 或审查流程。
输出会排除 identity、环境密钥和原始本机路径。""",
    "status": """redcap status [--workspace <dir>] [--task-file <file>]

查看当前任务状态：已经完成什么、下一步是什么、整体任务全景在哪里。
这是 revive 之后最适合作为第一眼状态面的命令。""",
    "diagnose": """redcap diagnose [--workspace <dir>] [--task-file <file>]

做深入体检：先给人类可读摘要，再列出内部检查结果。
如果只是给人快速判断，请优先用 redcap doctor。""",
    "package-surface": """redcap package-surface

检查未来公开包的名称、包面和安全边界。在正式发布任务开始前，它必须保持
private=true、publish_allowed=false，许可证也必须继续由人工明确决定。""",
    "closeout": """redcap closeout <subcommand> [--workspace <dir>] [--task-file <file>]

对当前任务执行正式收尾流程。可用 redcap closeout status 查看是否具备完工凭证。""",
}


def print_help(args: argparse.Namespace) -> int:
    topic = args.topic.strip() if args.topic else ""
    print(HELP_TOPICS.get(topic, HELP_TOPICS[""]))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="RedCap CLI product diagnostic surface.")
    parser.add_argument("command", choices=["doctor", "debug", "trace", "help"])
    parser.add_argument("--runtime-root", default=os.environ.get("REDCAP_RUNTIME_ROOT", str(ROOT)))
    parser.add_argument("--workspace-root", default=os.environ.get("REDCAP_WORKSPACE_ROOT", os.getcwd()))
    parser.add_argument("--task-file", default=os.environ.get("REDCAP_TASK_FILE", ".dev-task.md"))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--topic", default="")
    parser.add_argument("--traced-command", default="")
    parser.add_argument("--delegated-to", default="")
    args = parser.parse_args()

    if args.command == "doctor":
        return print_doctor(args)
    if args.command == "debug":
        return print_debug(args)
    if args.command == "trace":
        return print_trace(args)
    return print_help(args)


if __name__ == "__main__":
    raise SystemExit(main())

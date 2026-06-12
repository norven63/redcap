#!/usr/bin/env python3
"""旧 RedCap 外部证据目录的兼容、计划和恢复工具。"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import stat
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "runtime" / "core"))
import runtime_boundary  # noqa: E402

DEFAULT_POLICY = REPO_ROOT / "assets" / "contracts" / "legacy-evidence-policy.json"
ALLOWED_SUFFIXES = {".json", ".jsonl", ".lock", ".md", ".txt"}


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(json.dumps({"ok": False, "failures": [f"无法读取旧证据策略：{exc}"]}, ensure_ascii=False, indent=2)) from exc
    if not isinstance(payload, dict):
        raise SystemExit(json.dumps({"ok": False, "failures": ["旧证据策略必须是 JSON 对象"]}, ensure_ascii=False, indent=2))
    return payload


def boundary_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        runtime_root=args.runtime_root,
        project_workspace=args.project_workspace,
        cwd=args.cwd,
        task_file=args.task_file,
        task_id="",
        user_private_root=args.user_private_root,
        project_runtime_root=args.project_runtime_root,
        state_root=args.state_root,
        evidence_root=args.evidence_root,
        require_task_file=False,
    )


def is_relative_to(path: pathlib.Path, parent: pathlib.Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def executable_bit_set(path: pathlib.Path) -> bool:
    mode = path.stat().st_mode
    return bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


def validate_policy(policy: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if policy.get("schema_id") != "redcap-legacy-evidence-policy":
        failures.append("schema_id 不匹配")
    if policy.get("default_mode") != "read_only_compatibility":
        failures.append("default_mode 必须是 read_only_compatibility")
    rules = policy.get("rules")
    if not isinstance(rules, list) or not rules:
        failures.append("rules 必须是非空列表")
    rule_text = "\n".join(str(item) for item in rules or [])
    for required in ["不自动迁移旧证据", "legacy-evidence restore", ".redcap/evidence/legacy-import", "拒绝可执行文件"]:
        if required not in rule_text:
            failures.append(f"rules 缺少关键约束：{required}")
    return failures


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    policy = load_json(pathlib.Path(args.policy).resolve())
    context = runtime_boundary.build_context(boundary_args(args))
    failures = runtime_boundary.validate_context(context, require_task_file=False)
    failures.extend(validate_policy(policy))
    source = pathlib.Path(context["legacy_external_evidence_root"]).resolve()
    destination = pathlib.Path(context["evidence_root"]).resolve() / "legacy-import"
    if context.get("boundary_mode") == "external-workspace" and not is_relative_to(destination, pathlib.Path(context["project_runtime_root"]).resolve()):
        failures.append("旧证据恢复目标必须位于项目级 .redcap 内")
    return {
        "schema_id": "redcap-legacy-evidence-plan",
        "ok": not failures,
        "mode": policy.get("default_mode"),
        "boundary_mode": context.get("boundary_mode"),
        "project_workspace": context.get("project_workspace"),
        "source": str(source),
        "source_exists": source.exists(),
        "destination": str(destination),
        "automatic_migration": False,
        "restore_command_required": True,
        "failures": failures,
    }


def validate_source(source: pathlib.Path) -> list[str]:
    if not source.exists():
        return [f"旧证据源不存在：{source}"]
    if not source.is_dir():
        return [f"旧证据源必须是目录：{source}"]
    failures: list[str] = []
    files = [path for path in source.rglob("*") if path.is_file()]
    if not files:
        failures.append(f"旧证据源没有文件：{source}")
    for path in files:
        if path.suffix not in ALLOWED_SUFFIXES:
            failures.append(f"旧证据文件后缀不允许：{path}")
        if executable_bit_set(path):
            failures.append(f"旧证据文件不能带可执行位：{path}")
    return failures


def copy_tree(source: pathlib.Path, destination: pathlib.Path, *, replace: bool) -> None:
    if destination.exists():
        if not replace:
            raise SystemExit(json.dumps({"ok": False, "failures": [f"恢复目标已存在：{destination}"]}, ensure_ascii=False, indent=2))
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def cmd_check(args: argparse.Namespace) -> int:
    policy = load_json(pathlib.Path(args.policy).resolve())
    failures = validate_policy(policy)
    result = {"schema_id": "redcap-legacy-evidence-policy-check", "ok": not failures, "policy": str(pathlib.Path(args.policy).resolve()), "failures": failures}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_LEGACY_EVIDENCE_POLICY_OK")
        return 0
    return 1


def cmd_plan(args: argparse.Namespace) -> int:
    result = build_plan(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_LEGACY_EVIDENCE_PLAN_OK")
        return 0
    return 1


def cmd_restore(args: argparse.Namespace) -> int:
    plan = build_plan(args)
    source = pathlib.Path(plan["source"]).resolve()
    destination = pathlib.Path(plan["destination"]).resolve()
    failures = list(plan["failures"])
    failures.extend(validate_source(source))
    if failures:
        print(json.dumps({**plan, "ok": False, "failures": failures}, ensure_ascii=False, indent=2))
        return 1
    context_args = boundary_args(args)
    context = runtime_boundary.build_context(context_args)
    if context.get("boundary_mode") == "external-workspace":
        runtime_boundary.initialize_runtime_dirs(context)
    copy_tree(source, destination, replace=args.replace)
    files = sorted(str(path.relative_to(destination)) for path in destination.rglob("*") if path.is_file())
    result = {**plan, "ok": True, "restored_files": files, "failures": []}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("REDCAP_LEGACY_EVIDENCE_RESTORE_OK")
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="redcap-legacy-evidence-") as raw_tmp:
        tmp = pathlib.Path(raw_tmp)
        runtime_root = tmp / "runtime"
        runtime_root.mkdir()
        project = tmp / "project"
        project.mkdir()
        (project / ".dev-task.md").write_text("task_id: legacy-evidence-fixture\n", encoding="utf-8")
        private = tmp / "private"
        private.mkdir()
        project_hash = runtime_boundary.project_hash(project)
        source = private / "redcap-runtime" / "evidence" / project_hash
        source.mkdir(parents=True)
        (source / "review.json").write_text('{"ok": true}\n', encoding="utf-8")
        args = argparse.Namespace(
            policy=str(DEFAULT_POLICY),
            runtime_root=str(runtime_root),
            project_workspace=str(project),
            cwd=str(project),
            task_file=None,
            user_private_root=str(private),
            project_runtime_root=None,
            state_root=None,
            evidence_root=None,
            replace=True,
        )
        plan = build_plan(args)
        if not plan["ok"] or plan["source_exists"] is not True:
            failures.append("旧证据计划没有识别 fixture 源")
        restore_code = cmd_restore(args)
        restored = pathlib.Path(plan["destination"]) / "review.json"
        if restore_code != 0 or not restored.is_file():
            failures.append("旧证据恢复没有写入项目级 .redcap")
        if not is_relative_to(restored, project / ".redcap"):
            failures.append("旧证据恢复目标不在项目级 .redcap")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_LEGACY_EVIDENCE_SELF_CHECK_OK")
    return 0


def add_boundary_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--runtime-root")
    parser.add_argument("--project-workspace")
    parser.add_argument("--cwd")
    parser.add_argument("--task-file")
    parser.add_argument("--user-private-root")
    parser.add_argument("--project-runtime-root")
    parser.add_argument("--state-root")
    parser.add_argument("--evidence-root")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="旧 RedCap 外部证据目录策略")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check")
    check.add_argument("--policy", default=str(DEFAULT_POLICY))
    check.set_defaults(func=cmd_check)

    plan = sub.add_parser("plan")
    add_boundary_args(plan)
    plan.set_defaults(func=cmd_plan)

    restore = sub.add_parser("restore")
    add_boundary_args(restore)
    restore.add_argument("--replace", action="store_true")
    restore.set_defaults(func=cmd_restore)

    self_check = sub.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""RedCap runtime/project/user boundary kernel."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_USER_PRIVATE_ROOT = pathlib.Path(os.path.expanduser("~/.cap"))
DEFAULT_PROJECT_RUNTIME_DIR_NAME = ".redcap"
TASK_ID_RE = re.compile(r"^task_id:\s*(\S+)\s*$", re.M)


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def digest_file(path: pathlib.Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def is_relative_to(path: pathlib.Path, parent: pathlib.Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def resolve_path(raw: str | pathlib.Path) -> pathlib.Path:
    return pathlib.Path(os.path.expandvars(os.path.expanduser(str(raw)))).resolve()


def find_workspace_from_cwd(cwd: pathlib.Path, runtime_root: pathlib.Path) -> pathlib.Path:
    cwd = cwd.resolve()
    if is_relative_to(cwd, runtime_root):
        return runtime_root.resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / ".dev-task.md").is_file():
            return candidate.resolve()
    return cwd


def task_id_from(path: pathlib.Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    match = TASK_ID_RE.search(path.read_text(encoding="utf-8", errors="replace"))
    return match.group(1).strip() if match else ""


def legacy_external_state_root(user_private_root: pathlib.Path) -> pathlib.Path:
    return resolve_path(os.environ.get("REDCAP_RUNTIME_BASE_DIR") or user_private_root / "redcap-runtime")


def default_project_runtime_root(project_workspace: pathlib.Path) -> pathlib.Path:
    return (project_workspace / DEFAULT_PROJECT_RUNTIME_DIR_NAME).resolve()


def project_hash(project_workspace: pathlib.Path) -> str:
    return digest_text(str(project_workspace.resolve()))[:16]


def legacy_external_evidence_root(user_private_root: pathlib.Path, project_workspace: pathlib.Path) -> pathlib.Path:
    return legacy_external_state_root(user_private_root) / "evidence" / project_hash(project_workspace)


def gitignore_protects_project_runtime(project_runtime_root: pathlib.Path) -> bool:
    ignore_file = project_runtime_root / ".gitignore"
    if not ignore_file.is_file():
        return False
    content = ignore_file.read_text(encoding="utf-8", errors="replace").splitlines()
    return "*" in {line.strip() for line in content}


def project_runtime_dirs(project_runtime_root: pathlib.Path) -> dict[str, pathlib.Path]:
    return {
        "state": project_runtime_root / "state",
        "evidence": project_runtime_root / "evidence",
        "logs": project_runtime_root / "logs",
        "tmp": project_runtime_root / "tmp",
    }


def initialize_runtime_dirs(context: dict[str, Any]) -> list[str]:
    """Create runtime directories for a resolved boundary context."""
    project_runtime_root = resolve_path(context["project_runtime_root"])
    runtime_dirs = project_runtime_dirs(project_runtime_root)
    boundary_mode = context.get("boundary_mode")
    created_paths: list[str] = []
    for path in [project_runtime_root, *runtime_dirs.values()]:
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        if not existed:
            created_paths.append(str(path))
    if boundary_mode == "external-workspace":
        ignore_file = project_runtime_root / ".gitignore"
        desired = "*\n!.gitignore\n"
        if not ignore_file.is_file() or ignore_file.read_text(encoding="utf-8", errors="replace") != desired:
            ignore_file.write_text(desired, encoding="utf-8")
            created_paths.append(str(ignore_file))
    return created_paths


def build_context(args: argparse.Namespace) -> dict[str, Any]:
    runtime_root = resolve_path(args.runtime_root or os.environ.get("REDCAP_RUNTIME_ROOT") or REPO_ROOT)
    cwd = resolve_path(args.cwd or os.getcwd())
    raw_workspace = args.project_workspace or os.environ.get("REDCAP_WORKSPACE") or os.environ.get("REDCAP_WORKSPACE_ROOT")
    project_workspace = resolve_path(raw_workspace) if raw_workspace else find_workspace_from_cwd(cwd, runtime_root)
    raw_task_file = args.task_file or os.environ.get("REDCAP_TASK_FILE")
    task_file = resolve_path(raw_task_file) if raw_task_file else (project_workspace / ".dev-task.md").resolve()
    user_private_root = resolve_path(args.user_private_root or os.environ.get("REDCAP_USER_PRIVATE_ROOT") or DEFAULT_USER_PRIVATE_ROOT)
    boundary_mode = "self-development" if project_workspace == runtime_root else "external-workspace"
    raw_project_runtime_root = args.project_runtime_root or os.environ.get("REDCAP_PROJECT_RUNTIME_ROOT")
    if raw_project_runtime_root:
        project_runtime_root = resolve_path(raw_project_runtime_root)
    elif boundary_mode == "self-development":
        project_runtime_root = (runtime_root / "assets" / "evidence").resolve()
    else:
        project_runtime_root = default_project_runtime_root(project_workspace)

    if args.state_root:
        state_root = resolve_path(args.state_root)
    elif boundary_mode == "self-development":
        state_root = legacy_external_state_root(user_private_root)
    else:
        state_root = (project_runtime_root / "state").resolve()

    if args.evidence_root:
        evidence_root = resolve_path(args.evidence_root)
    elif boundary_mode == "self-development":
        evidence_root = runtime_root / "assets" / "evidence"
    else:
        evidence_root = project_runtime_root / "evidence"
    runtime_dirs = project_runtime_dirs(project_runtime_root)
    return {
        "schema_id": "redcap-runtime-boundary-context",
        "version": 2,
        "resolved_at": iso_now(),
        "boundary_mode": boundary_mode,
        "cwd": str(cwd),
        "runtime_root": str(runtime_root),
        "project_workspace": str(project_workspace),
        "project_runtime_root": str(project_runtime_root.resolve()),
        "task_file": str(task_file),
        "task_file_exists": task_file.is_file(),
        "task_id": args.task_id or task_id_from(task_file),
        "task_hash": digest_file(task_file),
        "user_private_root": str(user_private_root),
        "state_root": str(state_root),
        "evidence_root": str(evidence_root.resolve()),
        "logs_root": str(runtime_dirs["logs"].resolve()),
        "tmp_root": str(runtime_dirs["tmp"].resolve()),
        "project_runtime_gitignore": str((project_runtime_root / ".gitignore").resolve()),
        "project_runtime_gitignore_ok": gitignore_protects_project_runtime(project_runtime_root),
        "legacy_external_evidence_root": str(legacy_external_evidence_root(user_private_root, project_workspace).resolve()),
        "source_policy": "old-redcap-runtime-workspace-boundary-extraction-v1",
    }


def validate_context(context: dict[str, Any], *, require_task_file: bool = False) -> list[str]:
    failures: list[str] = []
    runtime_root = resolve_path(context["runtime_root"])
    project_workspace = resolve_path(context["project_workspace"])
    cwd = resolve_path(context["cwd"])
    task_file = resolve_path(context["task_file"])
    project_runtime_root = resolve_path(context["project_runtime_root"])
    user_private_root = resolve_path(context["user_private_root"])
    state_root = resolve_path(context["state_root"])
    evidence_root = resolve_path(context["evidence_root"])
    logs_root = resolve_path(context["logs_root"])
    tmp_root = resolve_path(context["tmp_root"])
    boundary_mode = context.get("boundary_mode")

    if not runtime_root.is_dir():
        failures.append(f"runtime_root missing: {runtime_root}")
    if not project_workspace.is_dir():
        failures.append(f"project_workspace missing: {project_workspace}")
    if boundary_mode not in {"self-development", "external-workspace"}:
        failures.append(f"invalid boundary_mode: {boundary_mode}")
    if project_workspace == runtime_root and not is_relative_to(cwd, runtime_root):
        failures.append("project_workspace may equal runtime_root only for self-development calls from inside runtime_root")
    if project_workspace != runtime_root and is_relative_to(project_workspace, runtime_root):
        failures.append("external project_workspace must not be inside runtime_root")
    if require_task_file and not task_file.is_file():
        failures.append(f"task_file missing: {task_file}")
    if task_file.is_file() and not is_relative_to(task_file, project_workspace):
        failures.append("task_file must live inside project_workspace")
    if is_relative_to(task_file, project_runtime_root):
        failures.append("task_file must not live inside project_runtime_root")
    if is_relative_to(user_private_root, runtime_root):
        failures.append("user_private_root must not live inside runtime_root")
    if is_relative_to(user_private_root, project_workspace):
        failures.append("user_private_root must not live inside project_workspace")
    if is_relative_to(user_private_root, project_runtime_root):
        failures.append("user_private_root must not live inside project_runtime_root")
    if boundary_mode == "external-workspace":
        expected_project_runtime_root = default_project_runtime_root(project_workspace)
        if project_runtime_root != expected_project_runtime_root:
            failures.append("external project_runtime_root must be <project_workspace>/.redcap")
        if not is_relative_to(project_runtime_root, project_workspace):
            failures.append("external project_runtime_root must live inside project_workspace")
        for label, path in {
            "state_root": state_root,
            "evidence_root": evidence_root,
            "logs_root": logs_root,
            "tmp_root": tmp_root,
        }.items():
            if not is_relative_to(path, project_runtime_root):
                failures.append(f"external project {label} must live inside project_runtime_root")
            if is_relative_to(path, runtime_root):
                failures.append(f"external project {label} must not live inside RedCap runtime_root")
        if project_runtime_root.exists() and not context.get("project_runtime_gitignore_ok"):
            failures.append("project_runtime_root exists but is not protected by .redcap/.gitignore")
    elif not is_relative_to(evidence_root, runtime_root):
        failures.append("self-development evidence_root must live inside RedCap runtime_root")
    return failures


def cmd_resolve(args: argparse.Namespace) -> int:
    context = build_context(args)
    print(json.dumps(context, ensure_ascii=False, indent=2))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    context = build_context(args)
    failures = validate_context(context, require_task_file=args.require_task_file)
    result = {"ok": not failures, "context": context, "failures": failures}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_RUNTIME_BOUNDARY_OK")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    context = build_context(args)
    failures = validate_context(context, require_task_file=args.require_task_file)
    created_paths: list[str] = []
    if not failures:
        created_paths = initialize_runtime_dirs(context)
        context = build_context(args)
        failures = validate_context(context, require_task_file=args.require_task_file)
    result = {"ok": not failures, "context": context, "created_paths": created_paths, "failures": failures}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_RUNTIME_BOUNDARY_INIT_OK")
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="redcap-boundary-") as tmp_raw:
        tmp = pathlib.Path(tmp_raw)
        runtime_root = tmp / "runtime-root"
        runtime_root.mkdir()
        external = tmp / "external-project"
        nested = external / "src" / "pkg"
        nested.mkdir(parents=True)
        task = external / ".dev-task.md"
        task.write_text("task_id: boundary-fixture\n", encoding="utf-8")
        private = tmp / "user-private"
        private.mkdir()

        external_args = argparse.Namespace(
            runtime_root=str(runtime_root),
            cwd=str(nested),
            project_workspace=None,
            task_file=None,
            user_private_root=str(private),
            project_runtime_root=None,
            state_root=None,
            evidence_root=None,
            task_id="",
            require_task_file=True,
        )
        external_context = build_context(external_args)
        external_failures = validate_context(external_context, require_task_file=True)
        if external_failures:
            failures.append(f"external workspace should pass: {external_failures}")
        if external_context["project_workspace"] != str(external.resolve()):
            failures.append("external workspace discovery did not walk up to .dev-task.md")
        if external_context["boundary_mode"] != "external-workspace":
            failures.append("external workspace mode not detected")
        expected_runtime_root = external / ".redcap"
        if external_context["project_runtime_root"] != str(expected_runtime_root.resolve()):
            failures.append("external project runtime root did not default to <project_workspace>/.redcap")
        for key in ["state_root", "evidence_root", "logs_root", "tmp_root"]:
            if not is_relative_to(resolve_path(external_context[key]), expected_runtime_root):
                failures.append(f"{key} did not default inside external .redcap")

        init_args = argparse.Namespace(**{**external_args.__dict__})
        init_result = build_context(init_args)
        for path in [resolve_path(init_result["project_runtime_root"]), resolve_path(init_result["state_root"]), resolve_path(init_result["evidence_root"]), resolve_path(init_result["logs_root"]), resolve_path(init_result["tmp_root"])]:
            path.mkdir(parents=True, exist_ok=True)
        (resolve_path(init_result["project_runtime_root"]) / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")
        init_failures = validate_context(build_context(init_args), require_task_file=True)
        if init_failures:
            failures.append(f"initialized external .redcap should pass: {init_failures}")
        (expected_runtime_root / ".gitignore").unlink()
        unprotected_failures = validate_context(build_context(init_args), require_task_file=True)
        if not any("project_runtime_root exists but is not protected" in item for item in unprotected_failures):
            failures.append("external .redcap without protection was not rejected")

        self_args = argparse.Namespace(
            runtime_root=str(runtime_root),
            cwd=str(runtime_root),
            project_workspace=None,
            task_file=None,
            user_private_root=str(private),
            project_runtime_root=None,
            state_root=None,
            evidence_root=None,
            task_id="",
            require_task_file=False,
        )
        self_context = build_context(self_args)
        self_failures = validate_context(self_context, require_task_file=False)
        if self_failures:
            failures.append(f"self-development should pass: {self_failures}")
        if self_context["boundary_mode"] != "self-development":
            failures.append("self-development mode not detected")

        leak_args = argparse.Namespace(
            runtime_root=str(runtime_root),
            cwd=str(external),
            project_workspace=str(runtime_root),
            task_file=None,
            user_private_root=str(private),
            project_runtime_root=None,
            state_root=None,
            evidence_root=None,
            task_id="",
            require_task_file=False,
        )
        leak_failures = validate_context(build_context(leak_args), require_task_file=False)
        if not any("project_workspace may equal runtime_root" in item for item in leak_failures):
            failures.append("runtime root selected as external workspace was not rejected")

        private_leak_args = argparse.Namespace(
            runtime_root=str(runtime_root),
            cwd=str(external),
            project_workspace=str(external),
            task_file=None,
            user_private_root=str(external / ".cap"),
            project_runtime_root=None,
            state_root=None,
            evidence_root=None,
            task_id="",
            require_task_file=False,
        )
        private_failures = validate_context(build_context(private_leak_args), require_task_file=False)
        if not any("user_private_root" in item for item in private_failures):
            failures.append("user-private state inside project was not rejected")

        wrong_runtime_args = argparse.Namespace(
            runtime_root=str(runtime_root),
            cwd=str(external),
            project_workspace=str(external),
            task_file=None,
            user_private_root=str(private),
            project_runtime_root=str(private / "wrong-runtime"),
            state_root=None,
            evidence_root=None,
            task_id="",
            require_task_file=False,
        )
        wrong_runtime_failures = validate_context(build_context(wrong_runtime_args), require_task_file=False)
        if not any("project_runtime_root" in item for item in wrong_runtime_failures):
            failures.append("external project_runtime_root override outside .redcap was not rejected")

    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_RUNTIME_BOUNDARY_SELF_CHECK_OK")
    return 0


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--runtime-root")
    parser.add_argument("--project-workspace")
    parser.add_argument("--cwd")
    parser.add_argument("--task-file")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--user-private-root")
    parser.add_argument("--project-runtime-root")
    parser.add_argument("--state-root")
    parser.add_argument("--evidence-root")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap runtime/project/user boundary")
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve")
    add_common(resolve)
    resolve.set_defaults(func=cmd_resolve)

    check = sub.add_parser("check")
    add_common(check)
    check.add_argument("--require-task-file", action="store_true")
    check.set_defaults(func=cmd_check)

    init = sub.add_parser("init")
    add_common(init)
    init.add_argument("--require-task-file", action="store_true")
    init.set_defaults(func=cmd_init)

    self_check = sub.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

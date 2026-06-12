#!/usr/bin/env python3
"""Project-level RedCap package and init installer."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import shutil
import stat
import sys
import tempfile
import zipfile
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "assets" / "contracts" / "project-installation.json"
HOOK_TEMPLATE = REPO_ROOT / "assets" / "contracts" / "codex-hooks.template.json"
PACKAGE_ROOT = ".redcap"
EXCLUDED_PARTS = {".git", "__pycache__", "assets/evidence"}


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


def should_exclude(path: pathlib.Path) -> bool:
    rel = path.relative_to(REPO_ROOT).as_posix()
    if rel == "assets/evidence" or rel.startswith("assets/evidence/"):
        return True
    return any(part in EXCLUDED_PARTS for part in path.parts)


def iter_package_files(contract: dict[str, Any]) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for raw in contract.get("required_package_roots", []):
        root = REPO_ROOT / str(raw)
        if not root.exists():
            continue
        if root.is_file():
            if not should_exclude(root):
                files.append(root)
            continue
        for path in root.rglob("*"):
            if path.is_file() and not should_exclude(path):
                files.append(path)
    return sorted(set(files))


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-project-installation-contract":
        failures.append("项目安装合同 schema_id 错误")
    if contract.get("package_root_name") != PACKAGE_ROOT:
        failures.append("压缩包根目录必须是 .redcap")
    if ".redcap/runtime/bin/redcap project-install init" not in str(contract.get("init_command", "")):
        failures.append("项目安装合同缺少 init 命令")
    for raw in contract.get("required_package_roots", []):
        if not (REPO_ROOT / str(raw)).exists():
            failures.append(f"打包必需路径不存在：{raw}")
    safety = "\n".join(str(item) for item in contract.get("safety_rules", []))
    for required in ["assets/evidence", "项目级", "hooks"]:
        if required not in safety:
            failures.append(f"安装安全规则缺少：{required}")
    return failures


def render_hook_config(package_root: pathlib.Path) -> str:
    template = HOOK_TEMPLATE.read_text(encoding="utf-8")
    return template.replace("{REPO_ROOT}", str(package_root.resolve()))


def package_to(output: pathlib.Path) -> dict[str, Any]:
    contract = load_json(CONTRACT)
    failures = validate_contract(contract)
    if failures:
        return {"ok": False, "failures": failures}
    output.parent.mkdir(parents=True, exist_ok=True)
    files = iter_package_files(contract)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            rel = path.relative_to(REPO_ROOT).as_posix()
            archive.write(path, f"{PACKAGE_ROOT}/{rel}")
        install_manifest = {
            "schema_id": "redcap-package-manifest",
            "created_at": iso_now(),
            "package_root": PACKAGE_ROOT,
            "file_count": len(files),
            "init_command": contract.get("init_command"),
        }
        archive.writestr(f"{PACKAGE_ROOT}/install-manifest.json", json.dumps(install_manifest, ensure_ascii=False, indent=2) + "\n")
    return {
        "schema_id": "redcap-project-package",
        "ok": True,
        "out": str(output.resolve()),
        "package_root": PACKAGE_ROOT,
        "file_count": len(files),
        "failures": [],
    }


def init_project(project: pathlib.Path, package_root: pathlib.Path) -> dict[str, Any]:
    project = project.resolve()
    package_root = package_root.resolve()
    failures: list[str] = []
    if not project.is_dir():
        failures.append(f"项目目录不存在：{project}")
    if not package_root.is_dir():
        failures.append(f".redcap 包目录不存在：{package_root}")
    if package_root != project / PACKAGE_ROOT:
        failures.append("package_root 必须是 <project>/.redcap")
    runtime_bin = package_root / "runtime" / "bin" / "redcap"
    if not runtime_bin.is_file():
        failures.append("包内缺少 runtime/bin/redcap")
    if failures:
        return {"ok": False, "failures": failures}
    created: list[str] = []
    for path in [package_root / "state", package_root / "evidence", package_root / "logs", package_root / "tmp", project / ".codex"]:
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        if not existed:
            created.append(str(path))
    gitignore = package_root / ".gitignore"
    desired_ignore = "*\n!.gitignore\n"
    if not gitignore.exists() or gitignore.read_text(encoding="utf-8", errors="replace") != desired_ignore:
        gitignore.write_text(desired_ignore, encoding="utf-8")
        created.append(str(gitignore))
    hook_file = project / ".codex" / "hooks.json"
    hook_file.write_text(render_hook_config(package_root), encoding="utf-8")
    created.append(str(hook_file))
    install_json = package_root / "install.json"
    install_json.write_text(json.dumps({
        "schema_id": "redcap-project-installation",
        "installed_at": iso_now(),
        "project": str(project),
        "package_root": str(package_root),
        "hook_config": str(hook_file),
        "runtime_bin": str(runtime_bin),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    created.append(str(install_json))
    mode = runtime_bin.stat().st_mode
    runtime_bin.chmod(mode | stat.S_IXUSR)
    return {
        "schema_id": "redcap-project-installation",
        "ok": True,
        "project": str(project),
        "package_root": str(package_root),
        "created": created,
        "failures": [],
    }


def check() -> dict[str, Any]:
    contract = load_json(CONTRACT)
    failures = validate_contract(contract)
    package_files = iter_package_files(contract)
    if any("assets/evidence/" in path.relative_to(REPO_ROOT).as_posix() for path in package_files):
        failures.append("打包清单不得包含 assets/evidence")
    return {
        "schema_id": "redcap-project-installation-check",
        "ok": not failures,
        "contract": str(CONTRACT),
        "package_root": PACKAGE_ROOT,
        "package_file_count": len(package_files),
        "failures": failures,
    }


def cmd_check(_: argparse.Namespace) -> int:
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_PROJECT_INSTALL_OK")
        return 0
    return 1


def cmd_package(args: argparse.Namespace) -> int:
    result = package_to(pathlib.Path(args.out))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_PROJECT_PACKAGE_OK")
        return 0
    return 1


def cmd_init(args: argparse.Namespace) -> int:
    project = pathlib.Path(args.project)
    package_root = pathlib.Path(args.package_root) if args.package_root else project / PACKAGE_ROOT
    result = init_project(project, package_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_PROJECT_INIT_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="redcap-project-install-") as raw_tmp:
        tmp = pathlib.Path(raw_tmp)
        package_path = tmp / "redcap.zip"
        package_result = package_to(package_path)
        if not package_result.get("ok"):
            failures.append(f"打包自检失败：{package_result.get('failures')}")
        project = tmp / "project"
        project.mkdir()
        with zipfile.ZipFile(package_path) as archive:
            archive.extractall(project)
        package_root = project / PACKAGE_ROOT
        init_result = init_project(project, package_root)
        if not init_result.get("ok"):
            failures.append(f"初始化自检失败：{init_result.get('failures')}")
        for required in [
            package_root / "runtime" / "bin" / "redcap",
            package_root / "install.json",
            package_root / "evidence",
            package_root / "logs",
            package_root / "tmp",
            project / ".codex" / "hooks.json",
        ]:
            if not required.exists():
                failures.append(f"安装后缺少路径：{required}")
        hook_text = (project / ".codex" / "hooks.json").read_text(encoding="utf-8", errors="replace")
        if str(package_root) not in hook_text:
            failures.append("项目 hooks 没有指向项目 .redcap")
        if (package_root / "assets" / "evidence").exists():
            failures.append("包内不应包含 assets/evidence")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_PROJECT_INSTALL_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap 项目级安装与打包")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check").set_defaults(func=cmd_check)
    package = sub.add_parser("package")
    package.add_argument("--out", required=True)
    package.set_defaults(func=cmd_package)
    init = sub.add_parser("init")
    init.add_argument("--project", required=True)
    init.add_argument("--package-root")
    init.set_defaults(func=cmd_init)
    sub.add_parser("self-check").set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

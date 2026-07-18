#!/usr/bin/env python3
"""Project-level RedCap package and init installer."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "assets" / "contracts" / "project-installation.json"
PRODUCTION_READINESS_CONTRACT = REPO_ROOT / "assets" / "contracts" / "project-install-production-readiness.json"
HOOK_TEMPLATE = REPO_ROOT / "assets" / "contracts" / "codex-hooks.template.json"
PACKAGE_ROOT = ".redcap"
EXCLUDED_PARTS = {".git", "__pycache__", "assets/evidence"}
EXCLUDED_PREFIXES = {
    "runtime/bootstrap",
}
FORBIDDEN_ZIP_PARTS = {".git", "__pycache__", "assets/evidence"}
FORBIDDEN_ZIP_NAMES = {"AGENTS.md", ".DS_Store"}
ALLOWED_RAW_META_ZIP_PREFIXES = (
    f"{PACKAGE_ROOT}/assets/fixtures/prism/real-provider-evidence/",
)
TRANSIENT_SELF_CHECK_PREFIXES = (
    ".redcap-forge-self-check-",
)
TEXT_SCAN_SUFFIXES = {".json", ".md", ".py", ".sh", ".txt", ".toml", ".yaml", ".yml"}
TEXT_SCAN_PATH_PREFIXES = (
    f"{PACKAGE_ROOT}/runtime/bin/",
    f"{PACKAGE_ROOT}/runtime/prism/bin/",
    f"{PACKAGE_ROOT}/runtime/host-adapters/examples/",
)


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


def should_exclude(path: pathlib.Path) -> bool:
    rel = path.relative_to(REPO_ROOT).as_posix()
    if rel == "assets/evidence" or rel.startswith("assets/evidence/"):
        return True
    if any(rel == prefix or rel.startswith(f"{prefix}/") for prefix in EXCLUDED_PREFIXES):
        return True
    return any(part in EXCLUDED_PARTS for part in path.parts)


def is_transient_self_check_file(path: pathlib.Path) -> bool:
    return any(path.name.startswith(prefix) for prefix in TRANSIENT_SELF_CHECK_PREFIXES)


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def executable_bit_set(path: pathlib.Path) -> bool:
    return bool(path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


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
            if path.is_file() and not should_exclude(path) and not is_transient_self_check_file(path):
                files.append(path)
    return sorted(set(files))


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-project-installation-contract":
        failures.append("项目安装合同 schema_id 错误")
    if contract.get("package_root_name") != PACKAGE_ROOT:
        failures.append("压缩包根目录必须是 .redcap")
    init_command = str(contract.get("init_command", ""))
    if ".redcap/runtime/bin/redcap" not in init_command or "project-install init" not in init_command:
        failures.append("项目安装合同缺少 init 命令")
    for raw in contract.get("required_package_roots", []):
        if not (REPO_ROOT / str(raw)).exists():
            failures.append(f"打包必需路径不存在：{raw}")
    safety = "\n".join(str(item) for item in contract.get("safety_rules", []))
    for required in ["assets/evidence", "项目级", "hooks", "longrun-observer"]:
        if required not in safety:
            failures.append(f"安装安全规则缺少：{required}")
    if "longrun-observer" not in str(contract.get("longrun_observer_command", "")):
        failures.append("项目安装合同缺少长期观察器初始化命令")
    return failures


def render_hook_config(package_root: pathlib.Path) -> str:
    template = HOOK_TEMPLATE.read_text(encoding="utf-8")
    return template.replace("{REPO_ROOT}", str(package_root.resolve()))


def restore_executable_bits(package_root: pathlib.Path) -> list[str]:
    changed: list[str] = []
    for command_dir in [
        package_root / "runtime" / "bin",
        package_root / "runtime" / "host-adapters" / "examples",
        package_root / "runtime" / "prism" / "bin",
    ]:
        if not command_dir.is_dir():
            continue
        for path in command_dir.iterdir():
            if not path.is_file():
                continue
            mode = path.stat().st_mode
            desired = mode | stat.S_IXUSR
            if desired != mode:
                path.chmod(desired)
                changed.append(str(path))
    return changed


def existing_install_compatibility_guard(install_json: pathlib.Path) -> dict[str, Any]:
    if not install_json.exists():
        return {"ok": True, "created": [], "status": "absent", "failures": []}
    try:
        from config_contract_compat import classify_file, migrate_file  # noqa: PLC0415
        classification = classify_file(install_json, expected_type="project_installation_record")
    except BaseException as exc:  # noqa: BLE001
        return {
            "ok": False,
            "created": [],
            "status": "guard_error",
            "failures": [f"现有 install.json 兼容性检查失败：{exc}"],
        }
    if classification.get("status") == "direct_read":
        return {
            "ok": True,
            "created": [],
            "status": "direct_read",
            "classification": classification,
            "failures": [],
        }
    if classification.get("status") != "needs_migration":
        return {
            "ok": False,
            "created": [],
            "status": "rejected",
            "classification": classification,
            "failures": classification.get("failures", ["现有 install.json 被拒绝"]),
        }
    migration = migrate_file(install_json, apply=True)
    created = [
        str(migration.get("backup_path")),
        str(migration.get("receipt_path")),
    ]
    return {
        "ok": migration.get("ok") is True,
        "created": [item for item in created if item and item != "None"],
        "status": "migrated",
        "classification": classification,
        "migration": migration,
        "failures": migration.get("failures", []),
    }


def package_to(output: pathlib.Path) -> dict[str, Any]:
    contract = load_json(CONTRACT)
    failures = validate_contract(contract)
    if failures:
        return {"ok": False, "failures": failures}
    output.parent.mkdir(parents=True, exist_ok=True)
    files = iter_package_files(contract)
    manifest_files: list[dict[str, Any]] = []
    failures: list[str] = []
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            rel = path.relative_to(REPO_ROOT).as_posix()
            try:
                size = path.stat().st_size
                digest = sha256_file(path)
                archive.write(path, f"{PACKAGE_ROOT}/{rel}")
            except FileNotFoundError:
                if is_transient_self_check_file(path):
                    continue
                failures.append(f"打包过程中源文件消失：{rel}")
                continue
            manifest_files.append({
                "path": f"{PACKAGE_ROOT}/{rel}",
                "size": size,
                "sha256": digest,
            })
        if failures:
            return {
                "schema_id": "redcap-project-package",
                "ok": False,
                "out": str(output.resolve()),
                "package_root": PACKAGE_ROOT,
                "file_count": len(manifest_files),
                "failures": failures,
            }
        install_manifest = {
            "schema_id": "redcap-package-manifest",
            "schema_version": 1,
            "created_at": iso_now(),
            "package_root": PACKAGE_ROOT,
            "file_count": len(manifest_files),
            "files": manifest_files,
            "init_command": contract.get("init_command"),
        }
        archive.writestr(f"{PACKAGE_ROOT}/install-manifest.json", json.dumps(install_manifest, ensure_ascii=False, indent=2) + "\n")
    return {
        "schema_id": "redcap-project-package",
        "ok": True,
        "out": str(output.resolve()),
        "package_root": PACKAGE_ROOT,
        "file_count": len(manifest_files),
        "failures": [],
    }


def transient_self_check_exclusion_probe() -> dict[str, Any]:
    arsenal_dir = REPO_ROOT / "assets" / "knowledge" / "arsenal"
    transient = arsenal_dir / f"{TRANSIENT_SELF_CHECK_PREFIXES[0]}package-probe-{os.getpid()}.md"
    transient.write_text("RedCap transient package exclusion probe.\n", encoding="utf-8")
    try:
        with tempfile.TemporaryDirectory(prefix="redcap-project-transient-package-") as raw_tmp:
            package_path = pathlib.Path(raw_tmp) / "redcap.zip"
            package_result = package_to(package_path)
            if package_result.get("ok") is not True:
                return {
                    "ok": False,
                    "failures": [f"临时自检文件排除探针打包失败：{package_result.get('failures')}"],
                }
            with zipfile.ZipFile(package_path) as archive:
                names = set(archive.namelist())
            packaged_name = f"{PACKAGE_ROOT}/{transient.relative_to(REPO_ROOT).as_posix()}"
            if packaged_name in names:
                return {
                    "ok": False,
                    "failures": [f"临时自检文件不应进入发布包：{packaged_name}"],
                }
            return {"ok": True, "failures": []}
    finally:
        transient.unlink(missing_ok=True)


def entry_has_forbidden_part(name: str) -> str | None:
    parts = pathlib.PurePosixPath(name).parts
    if not parts or parts[0] != PACKAGE_ROOT:
        return "压缩包条目必须位于 .redcap 根目录下"
    if name.startswith("/") or ".." in parts:
        return "压缩包条目不得是绝对路径或包含 .."
    for forbidden in FORBIDDEN_ZIP_PARTS:
        forbidden_parts = pathlib.PurePosixPath(forbidden).parts
        for index in range(0, len(parts) - len(forbidden_parts) + 1):
            if parts[index:index + len(forbidden_parts)] == forbidden_parts:
                return f"压缩包不得包含 {forbidden}"
    if parts[-1] in FORBIDDEN_ZIP_NAMES:
        return f"压缩包不得包含 {parts[-1]}"
    stable_fixture_raw_meta = (
        parts[-1].endswith(".raw.meta.json")
        and any(name.startswith(prefix) for prefix in ALLOWED_RAW_META_ZIP_PREFIXES)
    )
    if parts[-1].endswith(".raw.json") or (parts[-1].endswith(".raw.meta.json") and not stable_fixture_raw_meta):
        return "压缩包不得包含供应方 raw 输出"
    return None


def audit_package(package_path: pathlib.Path) -> dict[str, Any]:
    failures: list[str] = []
    if not package_path.is_file():
        return {"schema_id": "redcap-project-package-audit", "ok": False, "package": str(package_path), "failures": ["压缩包不存在"]}
    try:
        with zipfile.ZipFile(package_path) as archive:
            names = archive.namelist()
            for name in names:
                reason = entry_has_forbidden_part(name)
                if reason:
                    failures.append(f"{name}: {reason}")
            required = [
                f"{PACKAGE_ROOT}/runtime/bin/redcap",
                f"{PACKAGE_ROOT}/runtime/core/longrun_observer.py",
                f"{PACKAGE_ROOT}/assets/contracts/codex-hooks.template.json",
                f"{PACKAGE_ROOT}/assets/contracts/longrun-observer.json",
                f"{PACKAGE_ROOT}/install-manifest.json",
                f"{PACKAGE_ROOT}/README.md",
            ]
            for name in required:
                if name not in names:
                    failures.append(f"压缩包缺少必需条目：{name}")
            manifest_payload: dict[str, Any] = {}
            if f"{PACKAGE_ROOT}/install-manifest.json" in names:
                try:
                    manifest_payload = json.loads(archive.read(f"{PACKAGE_ROOT}/install-manifest.json").decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    failures.append(f"install-manifest.json 无法读取：{exc}")
                if manifest_payload.get("schema_id") != "redcap-package-manifest":
                    failures.append("install-manifest.json schema_id 错误")
                if manifest_payload.get("schema_version") != 1:
                    failures.append("install-manifest.json schema_version 必须为 1")
                if not isinstance(manifest_payload.get("files"), list) or not manifest_payload.get("files"):
                    failures.append("install-manifest.json 必须包含 files 清单")
            current_root = str(REPO_ROOT)
            leaked_current_root: list[str] = []
            for info in archive.infolist():
                suffix = pathlib.PurePosixPath(info.filename).suffix
                scan_text = suffix in TEXT_SCAN_SUFFIXES or any(info.filename.startswith(prefix) for prefix in TEXT_SCAN_PATH_PREFIXES)
                if not scan_text or info.file_size > 2_000_000:
                    continue
                try:
                    text = archive.read(info).decode("utf-8")
                except UnicodeDecodeError:
                    continue
                if current_root in text:
                    leaked_current_root.append(info.filename)
            if leaked_current_root:
                failures.append(f"压缩包文本包含当前源仓库绝对路径：{leaked_current_root[:8]}")
    except zipfile.BadZipFile as exc:
        failures.append(f"压缩包格式错误：{exc}")
        names = []
    return {
        "schema_id": "redcap-project-package-audit",
        "ok": not failures,
        "package": str(package_path.resolve()),
        "entry_count": len(names),
        "failures": failures,
    }


def release_check() -> dict[str, Any]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="redcap-project-release-") as raw_tmp:
        tmp = pathlib.Path(raw_tmp)
        package_path = tmp / "redcap.zip"
        package_result = package_to(package_path)
        if not package_result.get("ok"):
            failures.append(f"打包失败：{package_result.get('failures')}")
            audit_result = {"ok": False, "failures": ["打包失败，无法审计"]}
            init_result = {"ok": False, "failures": ["打包失败，无法安装"]}
        else:
            audit_result = audit_package(package_path)
            if not audit_result.get("ok"):
                failures.append(f"发布包审计失败：{audit_result.get('failures')}")
            project = tmp / "project"
            project.mkdir()
            with zipfile.ZipFile(package_path) as archive:
                archive.extractall(project)
            runtime_bin = project / PACKAGE_ROOT / "runtime" / "bin" / "redcap"
            init_result = run_release_init(project, runtime_bin)
            if not init_result.get("ok"):
                failures.append("真实解压安装命令失败")
            for required in [
                project / PACKAGE_ROOT / "runtime" / "bin" / "redcap",
                project / PACKAGE_ROOT / "runtime" / "core" / "longrun_observer.py",
                project / PACKAGE_ROOT / "assets" / "contracts" / "longrun-observer.json",
                project / PACKAGE_ROOT / "runtime" / "prism" / "bin" / "prism",
                project / PACKAGE_ROOT / "install.json",
                project / PACKAGE_ROOT / "evidence",
                project / PACKAGE_ROOT / "logs",
                project / PACKAGE_ROOT / "tmp",
                project / ".codex" / "hooks.json",
                project / ".codex" / "config.toml",
            ]:
                if not required.exists():
                    failures.append(f"发布安装后缺少路径：{required}")
            hook_file = project / ".codex" / "hooks.json"
            if hook_file.exists() and str((project / PACKAGE_ROOT).resolve()) not in hook_file.read_text(encoding="utf-8", errors="replace"):
                failures.append("项目 hooks 没有指向解压后的项目 .redcap")
            for executable in [
                project / PACKAGE_ROOT / "runtime" / "bin" / "redcap",
                project / PACKAGE_ROOT / "runtime" / "prism" / "bin" / "prism",
            ]:
                if executable.exists() and not executable_bit_set(executable):
                    failures.append(f"发布安装后命令不可执行：{executable}")
    return {
        "schema_id": "redcap-project-release-check",
        "ok": not failures,
        "package": package_result,
        "audit": audit_result,
        "init": init_result,
        "failures": failures,
    }


def run_release_init(project: pathlib.Path, runtime_bin: pathlib.Path) -> dict[str, Any]:
    completed = subprocess.run(
        ["bash", str(runtime_bin), "project-install", "init", "--project", str(project)],
        cwd=str(project),
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "argv": ["bash", str(runtime_bin), "project-install", "init", "--project", str(project)],
        "exit_code": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def run_smoke_command(argv: list[str], cwd: pathlib.Path, timeout_seconds: int = 60) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return {
            "argv": argv,
            "cwd": str(cwd),
            "timeout_seconds": timeout_seconds,
            "exit_code": completed.returncode,
            "ok": completed.returncode == 0,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "argv": argv,
            "cwd": str(cwd),
            "timeout_seconds": timeout_seconds,
            "exit_code": None,
            "ok": False,
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            "failures": ["命令超时"],
        }


def installed_runtime_smoke_check() -> dict[str, Any]:
    failures: list[str] = []
    commands: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="redcap-project-runtime-smoke-") as raw_tmp:
        tmp = pathlib.Path(raw_tmp)
        package_path = tmp / "redcap.zip"
        package_result = package_to(package_path)
        audit_result = audit_package(package_path) if package_result.get("ok") is True else {"ok": False, "failures": ["打包失败"]}
        project = tmp / "external-project"
        project.mkdir()
        if package_result.get("ok") is not True:
            failures.append(f"打包失败：{package_result.get('failures')}")
        elif audit_result.get("ok") is not True:
            failures.append(f"包审计失败：{audit_result.get('failures')}")
        else:
            with zipfile.ZipFile(package_path) as archive:
                archive.extractall(project)
            package_root = project / PACKAGE_ROOT
            init_result = init_project(project, package_root)
            if init_result.get("ok") is not True:
                failures.append(f"外部项目初始化失败：{init_result.get('failures')}")
            runtime_bin = package_root / "runtime" / "bin" / "redcap"
            for argv in [
                ["bash", str(runtime_bin), "project-install", "check"],
                ["bash", str(runtime_bin), "cli-surface", "check"],
                ["bash", str(runtime_bin), "longrun-observer", "self-check"],
                ["bash", str(runtime_bin), "longrun-observer", "scenario-test"],
                ["bash", str(runtime_bin), "longrun-observer", "auto-collect-scenario-test"],
                ["bash", str(runtime_bin), "gate", "--task", "外部项目安装后 runtime smoke", "--risk-level", "low"],
            ]:
                command = run_smoke_command(argv, project)
                commands.append(command)
                if command.get("ok") is not True:
                    failures.append(f"安装后运行时冒烟命令失败：{' '.join(argv[:4])}")
            hook_text = (project / ".codex" / "hooks.json").read_text(encoding="utf-8", errors="replace") if (project / ".codex" / "hooks.json").exists() else ""
            install_text = (package_root / "install.json").read_text(encoding="utf-8", errors="replace") if (package_root / "install.json").exists() else ""
            if str(package_root) not in hook_text:
                failures.append("安装后 hooks 未指向项目级 .redcap")
            if str(REPO_ROOT) in hook_text or str(REPO_ROOT) in install_text:
                failures.append("安装后项目配置泄漏 RedCap 源仓库绝对路径")
            gitignore = package_root / ".gitignore"
            if not gitignore.exists() or gitignore.read_text(encoding="utf-8", errors="replace") != "*\n!.gitignore\n":
                failures.append(".redcap/.gitignore 不符合运行时产物隔离规则")
    return {
        "schema_id": "redcap-installed-runtime-smoke-check",
        "ok": not failures,
        "commands": commands,
        "failures": failures,
    }


def source_path_leak_negative_probe() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="redcap-project-bad-package-") as raw_tmp:
        bad_package = pathlib.Path(raw_tmp) / "bad-source-leak.zip"
        with zipfile.ZipFile(bad_package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"{PACKAGE_ROOT}/runtime/bin/redcap", f"#!/usr/bin/env bash\n# leak {REPO_ROOT}\n")
            archive.writestr(f"{PACKAGE_ROOT}/assets/contracts/codex-hooks.template.json", "{}\n")
            archive.writestr(f"{PACKAGE_ROOT}/install-manifest.json", json.dumps({
                "schema_id": "redcap-package-manifest",
                "schema_version": 1,
                "files": [{"path": f"{PACKAGE_ROOT}/runtime/bin/redcap"}],
            }, ensure_ascii=False))
            archive.writestr(f"{PACKAGE_ROOT}/README.md", "fixture\n")
        audit = audit_package(bad_package)
    detected = audit.get("ok") is False and any("绝对路径" in item for item in audit.get("failures", []))
    return {
        "schema_id": "redcap-source-path-leak-negative-probe",
        "ok": detected,
        "audit": audit,
        "failures": [] if detected else ["包含源仓库绝对路径的坏发布包没有被 audit-package 拒绝"],
    }


def validate_production_readiness_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-project-install-production-readiness-contract":
        failures.append("项目安装生产就绪合同 schema_id 错误")
    command = str(contract.get("command", ""))
    if "project-install production-readiness-check" not in command:
        failures.append("项目安装生产就绪合同缺少命令声明")
    required = "\n".join(str(item) for item in contract.get("technical_acceptance", []))
    for marker in ["release-check", "matrix-check", "安装后运行时冒烟", "scenario-test", "源仓库绝对路径"]:
        if marker not in required:
            failures.append(f"项目安装生产就绪合同缺少验收点：{marker}")
    boundary = str(contract.get("completion_boundary", ""))
    if "不等同于公开发布授权" not in boundary:
        failures.append("项目安装生产就绪合同必须声明不等同于公开发布授权")
    return failures


def production_readiness_check(out: pathlib.Path | None = None) -> dict[str, Any]:
    failures: list[str] = []
    contract = load_json(PRODUCTION_READINESS_CONTRACT)
    contract_failures = validate_production_readiness_contract(contract)
    failures.extend(contract_failures)
    install_check = check()
    release_result = release_check()
    matrix_result = project_install_matrix_check()
    smoke_result = installed_runtime_smoke_check()
    leak_probe = source_path_leak_negative_probe()
    checks = [
        {"id": "contract", "ok": not contract_failures, "failures": contract_failures},
        {"id": "project-install-check", "ok": install_check.get("ok") is True, "result": install_check},
        {"id": "release-check", "ok": release_result.get("ok") is True, "result": release_result},
        {"id": "matrix-check", "ok": matrix_result.get("ok") is True, "result": matrix_result},
        {"id": "installed-runtime-smoke", "ok": smoke_result.get("ok") is True, "result": smoke_result},
        {"id": "source-path-leak-negative-probe", "ok": leak_probe.get("ok") is True, "result": leak_probe},
    ]
    for check_item in checks:
        if check_item.get("ok") is not True:
            failures.append(f"{check_item.get('id')} 未通过")
    result = {
        "schema_id": "redcap-project-install-production-readiness-check",
        "ok": not failures,
        "state": "technical_ready_for_human_release_review" if not failures else "failed",
        "contract": str(PRODUCTION_READINESS_CONTRACT.relative_to(REPO_ROOT)),
        "checks": checks,
        "human_release_authorization_required": True,
        "completion_boundary": contract.get("completion_boundary"),
        "failures": failures,
    }
    if out is not None:
        write_json(out, result)
    return result


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
    install_json = package_root / "install.json"
    compatibility = existing_install_compatibility_guard(install_json)
    if compatibility.get("ok") is not True:
        return {
            "schema_id": "redcap-project-installation",
            "schema_version": 1,
            "ok": False,
            "project": str(project),
            "package_root": str(package_root),
            "created": [],
            "compatibility": compatibility,
            "failures": compatibility.get("failures", ["install.json 兼容性检查失败"]),
        }
    created: list[str] = list(compatibility.get("created", []))
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
    codex_config = project / ".codex" / "config.toml"
    config_text = "[features]\nhooks = true\n"
    if not codex_config.exists() or codex_config.read_text(encoding="utf-8", errors="replace") != config_text:
        codex_config.write_text(config_text, encoding="utf-8")
        created.append(str(codex_config))
    install_json.write_text(json.dumps({
        "schema_id": "redcap-project-installation",
        "schema_version": 1,
        "installed_at": iso_now(),
        "project": str(project),
        "package_root": str(package_root),
        "hook_config": str(hook_file),
        "codex_config": str(codex_config),
        "runtime_bin": str(runtime_bin),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    created.append(str(install_json))
    created.extend(restore_executable_bits(package_root))
    return {
        "schema_id": "redcap-project-installation",
        "schema_version": 1,
        "ok": True,
        "project": str(project),
        "package_root": str(package_root),
        "created": created,
        "compatibility": compatibility,
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


def cmd_audit_package(args: argparse.Namespace) -> int:
    result = audit_package(pathlib.Path(args.package).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_PROJECT_PACKAGE_AUDIT_OK")
        return 0
    return 1


def cmd_release_check(_: argparse.Namespace) -> int:
    result = release_check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_PROJECT_RELEASE_CHECK_OK")
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


def git_status_short() -> dict[str, Any]:
    completed = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "sha256": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
    }


def source_workspace_unchanged(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return before.get("exit_code") == 0 and after.get("exit_code") == 0 and before.get("stdout") == after.get("stdout")


def project_install_matrix_check(out: pathlib.Path | None = None) -> dict[str, Any]:
    failures: list[str] = []
    checks: list[dict[str, Any]] = []
    before_status = git_status_short()
    with tempfile.TemporaryDirectory(prefix="redcap-project-install-matrix-") as raw_tmp:
        tmp = pathlib.Path(raw_tmp)
        package_path = tmp / "redcap-package.zip"
        package_result = package_to(package_path)
        audit_result = audit_package(package_path) if package_result.get("ok") is True else {"ok": False, "failures": ["package failed"]}
        checks.append({"id": "package", "ok": package_result.get("ok") is True, "result": package_result})
        checks.append({"id": "audit-package", "ok": audit_result.get("ok") is True, "result": audit_result})
        if package_result.get("ok") is not True:
            failures.append(f"打包失败：{package_result.get('failures')}")
        if audit_result.get("ok") is not True:
            failures.append(f"包审计失败：{audit_result.get('failures')}")

        projects = [
            tmp / "external-project-a",
            tmp / "外部 项目 b",
        ]
        for index, project in enumerate(projects, start=1):
            project.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(package_path) as archive:
                archive.extractall(project)
            package_root = project / PACKAGE_ROOT
            init_result = init_project(project, package_root)
            required_paths = [
                package_root / "runtime" / "bin" / "redcap",
                package_root / "install.json",
                package_root / "evidence",
                package_root / "logs",
                package_root / "tmp",
                project / ".codex" / "hooks.json",
                project / ".codex" / "config.toml",
            ]
            hooks_text = (project / ".codex" / "hooks.json").read_text(encoding="utf-8", errors="replace") if (project / ".codex" / "hooks.json").exists() else ""
            ok = (
                init_result.get("ok") is True
                and all(path.exists() for path in required_paths)
                and str(package_root) in hooks_text
                and not (package_root / "assets" / "evidence").exists()
            )
            checks.append({
                "id": f"init-project-{index}",
                "ok": ok,
                "project": str(project),
                "required_paths_present": all(path.exists() for path in required_paths),
                "hooks_point_to_project_redcap": str(package_root) in hooks_text,
                "package_excludes_source_evidence": not (package_root / "assets" / "evidence").exists(),
                "result": init_result,
            })
            if not ok:
                failures.append(f"外部项目 {index} 初始化矩阵失败")

        reinit_result = init_project(projects[0], projects[0] / PACKAGE_ROOT)
        checks.append({"id": "reinit-idempotent", "ok": reinit_result.get("ok") is True, "result": reinit_result})
        if reinit_result.get("ok") is not True:
            failures.append(f"重复初始化失败：{reinit_result.get('failures')}")

        shutil.rmtree(projects[1] / PACKAGE_ROOT)
        uninstall_removed = not (projects[1] / PACKAGE_ROOT).exists()
        with zipfile.ZipFile(package_path) as archive:
            archive.extractall(projects[1])
        reinstall_result = init_project(projects[1], projects[1] / PACKAGE_ROOT)
        checks.append({
            "id": "uninstall-reinstall",
            "ok": uninstall_removed and reinstall_result.get("ok") is True,
            "uninstall_removed_package_root": uninstall_removed,
            "result": reinstall_result,
        })
        if not uninstall_removed or reinstall_result.get("ok") is not True:
            failures.append("卸载后重装验证失败")

    after_status = git_status_short()
    source_clean = source_workspace_unchanged(before_status, after_status)
    pollution_negative_before = dict(before_status)
    pollution_negative_after = dict(after_status)
    pollution_negative_after["stdout"] = str(after_status.get("stdout") or "") + "?? assets/evidence/rsp/pollution-probe.tmp\n"
    negative_probe_detected = not source_workspace_unchanged(pollution_negative_before, pollution_negative_after)
    checks.append({
        "id": "source-workspace-unchanged",
        "ok": source_clean,
        "before_sha256": before_status.get("sha256"),
        "after_sha256": after_status.get("sha256"),
    })
    checks.append({
        "id": "negative-source-pollution-detected",
        "ok": negative_probe_detected,
        "simulated_pollution": "?? assets/evidence/rsp/pollution-probe.tmp",
    })
    if not source_clean:
        failures.append("项目级安装矩阵改变了 RedCap 源工作区 git 状态")
    if not negative_probe_detected:
        failures.append("源工作区污染负向探针没有失败")

    evidence = {
        "rsp": "RSP-09",
        "schema_id": "redcap-rsp-09-project-install-matrix",
        "ok": not failures,
        "acceptance": {
            "positive": {
                "status": "pass" if not failures else "fail",
                "checks": [
                    "外部项目安装通过",
                    "重复初始化通过",
                    "卸载后重装通过",
                    "源仓库 git 状态未被安装流程改变"
                ],
            },
            "negative": {
                "status": "pass" if negative_probe_detected else "fail",
                "checks": ["模拟源仓库污染必须被矩阵检查识别为失败"],
            },
        },
        "changed_reality": [
            "runtime/core/project_install.py 新增 project-install matrix-check 命令，真实执行 package、audit-package、init、reinit、uninstall/reinstall 和源工作区隔离检查。"
        ],
        "artifacts": [
            "runtime/bin/redcap project-install matrix-check",
            "runtime/core/project_install.py",
            "assets/contracts/project-install-matrix.json"
        ],
        "checks": checks,
        "source_status": {
            "before_sha256": before_status.get("sha256"),
            "after_sha256": after_status.get("sha256"),
            "unchanged": source_clean,
        },
        "failures": failures,
    }
    if out is not None:
        write_json(out, evidence)
    return evidence


def cmd_matrix_check(args: argparse.Namespace) -> int:
    out = pathlib.Path(args.out).resolve() if args.out else REPO_ROOT / ".redcap" / "evidence" / "rsp" / "rsp-09-project-install-matrix.json"
    result = project_install_matrix_check(out)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok") is True:
        print("REDCAP_PROJECT_INSTALL_MATRIX_OK")
        return 0
    return 1


def cmd_production_readiness_check(args: argparse.Namespace) -> int:
    out = pathlib.Path(args.out).resolve() if args.out else None
    result = production_readiness_check(out)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok") is True:
        print("REDCAP_PROJECT_INSTALL_PRODUCTION_READINESS_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    transient_probe = transient_self_check_exclusion_probe()
    if transient_probe.get("ok") is not True:
        failures.extend(transient_probe.get("failures") or ["临时自检文件排除探针失败"])
    release_result = release_check()
    if not release_result.get("ok"):
        failures.append(f"发布链路自检失败：{release_result.get('failures')}")
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
            package_root / "runtime" / "core" / "longrun_observer.py",
            package_root / "assets" / "contracts" / "longrun-observer.json",
            package_root / "assets" / "fixtures" / "prism" / "real-provider-evidence" / "20260624-e2e-structural-fix" / "session.json",
            package_root / "install.json",
            package_root / "evidence",
            package_root / "logs",
            package_root / "tmp",
            project / ".codex" / "hooks.json",
            project / ".codex" / "config.toml",
        ]:
            if not required.exists():
                failures.append(f"安装后缺少路径：{required}")
        hook_text = (project / ".codex" / "hooks.json").read_text(encoding="utf-8", errors="replace")
        if str(package_root) not in hook_text:
            failures.append("项目 hooks 没有指向项目 .redcap")
        if (package_root / "assets" / "evidence").exists():
            failures.append("包内不应包含 assets/evidence")
        if not (package_root / "assets" / "fixtures").exists():
            failures.append("包内必须包含 assets/fixtures 稳定自检夹具")
        bad_package = tmp / "bad-redcap.zip"
        with zipfile.ZipFile(bad_package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"{PACKAGE_ROOT}/assets/evidence/forbidden.json", "{}\n")
            archive.writestr(f"{PACKAGE_ROOT}/runtime/bin/redcap", "#!/usr/bin/env bash\n")
            archive.writestr(f"{PACKAGE_ROOT}/assets/contracts/codex-hooks.template.json", "{}\n")
            archive.writestr(f"{PACKAGE_ROOT}/install-manifest.json", json.dumps({
                "schema_id": "redcap-package-manifest",
                "schema_version": 1,
                "files": [{"path": f"{PACKAGE_ROOT}/assets/evidence/forbidden.json"}],
            }))
            archive.writestr(f"{PACKAGE_ROOT}/README.md", "fixture\n")
        bad_audit = audit_package(bad_package)
        if bad_audit.get("ok") is True or not any("assets/evidence" in item for item in bad_audit.get("failures", [])):
            failures.append("包含 assets/evidence 的坏发布包没有被 audit-package 拒绝")
        legacy_project = tmp / "legacy-project"
        legacy_project.mkdir()
        legacy_root = legacy_project / PACKAGE_ROOT
        shutil.copytree(package_root, legacy_root)
        legacy_install = legacy_root / "install.json"
        legacy_install.write_text(json.dumps({
            "schema_id": "redcap-project-installation",
            "installed_at": "2026-06-20T00:00:00+00:00",
            "project": str(legacy_project),
            "package_root": str(legacy_root),
            "hook_config": str(legacy_project / ".codex" / "hooks.json"),
            "codex_config": str(legacy_project / ".codex" / "config.toml"),
            "runtime_bin": str(legacy_root / "runtime" / "bin" / "redcap"),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        legacy_init = init_project(legacy_project, legacy_root)
        if legacy_init.get("ok") is not True:
            failures.append(f"旧 install.json 自动迁移初始化失败：{legacy_init.get('failures')}")
        compatibility = legacy_init.get("compatibility") if isinstance(legacy_init.get("compatibility"), dict) else {}
        if compatibility.get("status") != "migrated":
            failures.append("旧 install.json 初始化前没有触发迁移")
        if not any(str(item).endswith(".migration-receipt.json") for item in legacy_init.get("created", [])):
            failures.append("旧 install.json 迁移没有生成回执")
        rejected_project = tmp / "rejected-project"
        rejected_project.mkdir()
        rejected_root = rejected_project / PACKAGE_ROOT
        shutil.copytree(package_root, rejected_root)
        rejected_install = rejected_root / "install.json"
        rejected_install.write_text(json.dumps({
            "schema_id": "redcap-project-installation",
            "schema_version": 999,
            "installed_at": "2026-06-20T00:00:00+00:00",
            "project": str(rejected_project),
            "package_root": str(rejected_root),
            "hook_config": str(rejected_project / ".codex" / "hooks.json"),
            "codex_config": str(rejected_project / ".codex" / "config.toml"),
            "runtime_bin": str(rejected_root / "runtime" / "bin" / "redcap"),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rejected_init = init_project(rejected_project, rejected_root)
        if rejected_init.get("ok") is True:
            failures.append("未知 schema_version 的 install.json 没有阻断 init")
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
    audit = sub.add_parser("audit-package")
    audit.add_argument("--package", required=True)
    audit.set_defaults(func=cmd_audit_package)
    sub.add_parser("release-check").set_defaults(func=cmd_release_check)
    init = sub.add_parser("init")
    init.add_argument("--project", required=True)
    init.add_argument("--package-root")
    init.set_defaults(func=cmd_init)
    matrix = sub.add_parser("matrix-check")
    matrix.add_argument("--out")
    matrix.set_defaults(func=cmd_matrix_check)
    production = sub.add_parser("production-readiness-check")
    production.add_argument("--out")
    production.set_defaults(func=cmd_production_readiness_check)
    sub.add_parser("self-check").set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Independent filesystem probe for RSP-27 config compatibility."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys
import tempfile
import zipfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNTIME_BIN = REPO_ROOT / "runtime" / "bin" / "redcap"
PACKAGE_ROOT = ".redcap"
TAIL_LIMIT = 4000


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def tail(value: str) -> str:
    if len(value) <= TAIL_LIMIT:
        return value
    return value[-TAIL_LIMIT:]


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON 必须是对象：{path}")
    return payload


def run(argv: list[str], *, cwd: pathlib.Path) -> dict[str, Any]:
    completed = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, check=False)
    return {
        "argv": argv,
        "exit_code": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout_tail": tail(completed.stdout or ""),
        "stderr_tail": tail(completed.stderr or ""),
    }


def init_command(project: pathlib.Path) -> list[str]:
    runtime_bin = project / PACKAGE_ROOT / "runtime" / "bin" / "redcap"
    return ["bash", str(runtime_bin), "project-install", "init", "--project", str(project)]


def package_project(root: pathlib.Path) -> tuple[pathlib.Path, dict[str, Any]]:
    package_path = root / "redcap.zip"
    result = run([str(RUNTIME_BIN), "project-install", "package", "--out", str(package_path)], cwd=REPO_ROOT)
    return package_path, result


def extract_package(package_path: pathlib.Path, project: pathlib.Path) -> pathlib.Path:
    project.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package_path) as archive:
        archive.extractall(project)
    return project / PACKAGE_ROOT


def install_record(project: pathlib.Path, package_root: pathlib.Path, *, schema_version: int | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_id": "redcap-project-installation",
        "installed_at": "2026-06-20T00:00:00+00:00",
        "project": str(project.resolve()),
        "package_root": str(package_root.resolve()),
        "hook_config": str((project / ".codex" / "hooks.json").resolve()),
        "codex_config": str((project / ".codex" / "config.toml").resolve()),
        "runtime_bin": str((package_root / "runtime" / "bin" / "redcap").resolve()),
    }
    if schema_version is not None:
        payload["schema_version"] = schema_version
    return payload


def write_install_record(path: pathlib.Path, payload: dict[str, Any]) -> bytes:
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    path.write_bytes(data)
    return data


def make_bad_manifest_package(source_package: pathlib.Path, bad_package: pathlib.Path) -> None:
    manifest_name = f"{PACKAGE_ROOT}/install-manifest.json"
    with zipfile.ZipFile(source_package) as source, zipfile.ZipFile(bad_package, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == manifest_name:
                manifest = json.loads(data.decode("utf-8"))
                manifest["schema_version"] = 999
                data = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
            target.writestr(info, data)


def probe() -> dict[str, Any]:
    failures: list[str] = []
    steps: dict[str, Any] = {}
    assertions: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="redcap-config-external-probe-") as raw:
        root = pathlib.Path(raw)
        package_path, package_result = package_project(root)
        steps["package"] = package_result
        if package_result["exit_code"] != 0 or not package_path.exists():
            failures.append("project-install package failed")
            return build_report(False, steps, assertions, failures)

        legacy_project = root / "legacy-project"
        legacy_root = extract_package(package_path, legacy_project)
        legacy_install = legacy_root / "install.json"
        legacy_before_payload = install_record(legacy_project, legacy_root, schema_version=None)
        legacy_before_bytes = write_install_record(legacy_install, legacy_before_payload)
        legacy_init = run(init_command(legacy_project), cwd=legacy_project)
        steps["legacy_init"] = legacy_init
        legacy_after_payload = load_json(legacy_install)
        backups = sorted(legacy_root.glob("install.json.backup-*"))
        receipts = sorted(legacy_root.glob("install.json.migration-receipt.json"))
        backup_bytes = backups[0].read_bytes() if backups else b""
        assertions["legacy_init_exit_zero"] = legacy_init["exit_code"] == 0
        assertions["legacy_backup_exists"] = bool(backups)
        assertions["legacy_backup_matches_original_bytes"] = backup_bytes == legacy_before_bytes
        assertions["legacy_receipt_exists"] = bool(receipts)
        assertions["legacy_after_schema_version_1"] = legacy_after_payload.get("schema_version") == 1
        assertions["legacy_hook_config_preserved"] = legacy_after_payload.get("hook_config") == legacy_before_payload.get("hook_config")
        assertions["legacy_codex_config_preserved"] = legacy_after_payload.get("codex_config") == legacy_before_payload.get("codex_config")
        assertions["legacy_runtime_bin_preserved"] = legacy_after_payload.get("runtime_bin") == legacy_before_payload.get("runtime_bin")

        rejected_project = root / "rejected-project"
        rejected_root = extract_package(package_path, rejected_project)
        rejected_install = rejected_root / "install.json"
        rejected_before_payload = install_record(rejected_project, rejected_root, schema_version=999)
        rejected_before_bytes = write_install_record(rejected_install, rejected_before_payload)
        rejected_init = run(init_command(rejected_project), cwd=rejected_project)
        steps["unknown_version_init"] = rejected_init
        rejected_after_bytes = rejected_install.read_bytes()
        assertions["unknown_version_nonzero_exit"] = rejected_init["exit_code"] != 0
        assertions["unknown_version_install_json_unchanged"] = rejected_after_bytes == rejected_before_bytes
        assertions["unknown_version_no_codex_created"] = not (rejected_project / ".codex").exists()

        bad_package = root / "bad-manifest.zip"
        make_bad_manifest_package(package_path, bad_package)
        bad_audit = run([str(RUNTIME_BIN), "project-install", "audit-package", "--package", str(bad_package)], cwd=REPO_ROOT)
        steps["bad_manifest_audit"] = bad_audit
        assertions["bad_manifest_rejected"] = bad_audit["exit_code"] != 0

    for name, ok in assertions.items():
        if not ok:
            failures.append(f"assertion failed: {name}")
    return build_report(not failures, steps, assertions, failures)


def build_report(ok: bool, steps: dict[str, Any], assertions: dict[str, bool], failures: list[str]) -> dict[str, Any]:
    return {
        "schema_id": "redcap-config-contract-compat-external-probe",
        "rsp": "RSP-27",
        "created_at": iso_now(),
        "ok": ok,
        "probe_type": "independent_filesystem_cli_probe",
        "steps": steps,
        "assertions": assertions,
        "failures": failures,
    }


def cmd_check(args: argparse.Namespace) -> int:
    report = probe()
    if args.out:
        write_json(pathlib.Path(args.out), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["ok"]:
        print("REDCAP_CONFIG_CONTRACT_COMPAT_EXTERNAL_PROBE_OK")
        return 0
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap 配置兼容独立外部探针")
    parser.add_argument("--out")
    return parser


def main() -> int:
    return cmd_check(build_parser().parse_args())


if __name__ == "__main__":
    sys.exit(main())

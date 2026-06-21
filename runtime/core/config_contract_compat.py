#!/usr/bin/env python3
"""RedCap configuration contract compatibility checker."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import shutil
import sys
import tempfile
import zipfile
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "assets" / "contracts" / "config-contract-compat.json"
PROJECT_INSTALL_CONTRACT = REPO_ROOT / "assets" / "contracts" / "project-installation.json"
PACKAGE_ROOT = ".redcap"

CURRENT_SCHEMA_VERSION = 1

ALLOWED_FIELDS = {
    "project_installation_contract": {
        "schema_id",
        "schema_version",
        "purpose",
        "package_root_name",
        "init_command",
        "package_command",
        "audit_command",
        "release_check_command",
        "runtime_boundary",
        "required_package_roots",
        "init_outputs",
        "safety_rules",
    },
    "project_installation_record": {
        "schema_id",
        "schema_version",
        "installed_at",
        "project",
        "package_root",
        "hook_config",
        "codex_config",
        "runtime_bin",
    },
    "package_manifest": {
        "schema_id",
        "schema_version",
        "created_at",
        "package_root",
        "file_count",
        "files",
        "init_command",
    },
}

SCHEMA_TO_TYPE = {
    "redcap-project-installation-contract": "project_installation_contract",
    "redcap-project-installation": "project_installation_record",
    "redcap-package-manifest": "package_manifest",
}


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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT)


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-config-contract-compat":
        failures.append("配置兼容合同 schema_id 错误")
    if contract.get("schema_version") != CURRENT_SCHEMA_VERSION:
        failures.append("配置兼容合同 schema_version 必须为 1")
    matrix = contract.get("compatibility_matrix")
    if not isinstance(matrix, list) or not matrix:
        failures.append("配置兼容合同必须包含 compatibility_matrix")
        return failures
    seen = set()
    for item in matrix:
        if not isinstance(item, dict):
            failures.append("compatibility_matrix 条目必须是对象")
            continue
        config_type = item.get("config_type")
        schema_id = item.get("schema_id")
        if config_type not in ALLOWED_FIELDS:
            failures.append(f"未知 config_type：{config_type}")
        if schema_id not in SCHEMA_TO_TYPE:
            failures.append(f"未知 schema_id：{schema_id}")
        if SCHEMA_TO_TYPE.get(str(schema_id)) != config_type:
            failures.append(f"schema_id 与 config_type 不匹配：{schema_id}/{config_type}")
        if config_type in seen:
            failures.append(f"重复 config_type：{config_type}")
        seen.add(config_type)
        if item.get("current_schema_version") != CURRENT_SCHEMA_VERSION:
            failures.append(f"{config_type} current_schema_version 必须为 1")
        supported = item.get("supported_versions")
        if not isinstance(supported, list) or not supported:
            failures.append(f"{config_type} 缺少 supported_versions")
            continue
        actions = {entry.get("action") for entry in supported if isinstance(entry, dict)}
        if "direct_read" not in actions:
            failures.append(f"{config_type} 必须支持 direct_read")
        if item.get("unknown_version_action") != "reject":
            failures.append(f"{config_type} unknown_version_action 必须为 reject")
    if contract.get("strict_unknown_fields") is not True:
        failures.append("strict_unknown_fields 必须为 true")
    migration = contract.get("migration_rules")
    if not isinstance(migration, dict):
        failures.append("migration_rules 必须是对象")
    else:
        if migration.get("dry_run_required") is not True:
            failures.append("migration_rules.dry_run_required 必须为 true")
        if migration.get("apply_requires_backup") is not True:
            failures.append("migration_rules.apply_requires_backup 必须为 true")
        if migration.get("apply_requires_receipt") is not True:
            failures.append("migration_rules.apply_requires_receipt 必须为 true")
        if migration.get("manual_internal_edit_required") is not False:
            failures.append("migration_rules.manual_internal_edit_required 必须为 false")
    return failures


def matrix_by_type(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("config_type")): item
        for item in contract.get("compatibility_matrix", [])
        if isinstance(item, dict)
    }


def supported_action(matrix_item: dict[str, Any], version: int) -> dict[str, Any] | None:
    for item in matrix_item.get("supported_versions", []):
        if isinstance(item, dict) and item.get("schema_version") == version:
            return item
    return None


def classify_payload(payload: dict[str, Any], *, expected_type: str | None = None) -> dict[str, Any]:
    contract = load_contract()
    failures = validate_contract(contract)
    schema_id = payload.get("schema_id")
    config_type = SCHEMA_TO_TYPE.get(str(schema_id))
    if expected_type and config_type != expected_type:
        failures.append(f"配置类型不匹配：expected={expected_type}, actual={config_type}")
    if config_type is None:
        failures.append(f"未知 schema_id：{schema_id}")
        return {
            "ok": False,
            "status": "rejected",
            "reason": "unknown_schema_id",
            "failures": failures,
        }
    version_raw = payload.get("schema_version")
    version_missing = version_raw is None
    version = 0 if version_missing else version_raw
    if not isinstance(version, int):
        failures.append("schema_version 必须是整数")
        version = -1
    matrix_item = matrix_by_type(contract).get(config_type)
    if matrix_item is None:
        failures.append(f"兼容矩阵缺少配置类型：{config_type}")
        action_item = None
    else:
        action_item = supported_action(matrix_item, version)
    allowed = ALLOWED_FIELDS[config_type]
    unknown_fields = sorted(set(payload) - allowed)
    if unknown_fields:
        failures.append(f"存在未知字段：{unknown_fields}")
    missing_required = ["schema_id"]
    if version != 0:
        missing_required.append("schema_version")
    for key in missing_required:
        if key not in payload:
            failures.append(f"缺少必需字段：{key}")
    if failures:
        return {
            "ok": False,
            "status": "rejected",
            "config_type": config_type,
            "schema_id": schema_id,
            "schema_version": version,
            "version_missing": version_missing,
            "reason": "validation_failed",
            "failures": failures,
        }
    if action_item is None:
        return {
            "ok": False,
            "status": "rejected",
            "config_type": config_type,
            "schema_id": schema_id,
            "schema_version": version,
            "version_missing": version_missing,
            "reason": "unsupported_schema_version",
            "failures": [f"不支持的 schema_version：{version}"],
        }
    action = str(action_item.get("action"))
    status = "direct_read" if action == "direct_read" else "needs_migration"
    return {
        "ok": action == "direct_read",
        "status": status,
        "config_type": config_type,
        "schema_id": schema_id,
        "schema_version": version,
        "version_missing": version_missing,
        "migration": action_item.get("migration"),
        "target_schema_version": matrix_item.get("current_schema_version"),
        "failures": [],
    }


def classify_file(path: pathlib.Path, *, expected_type: str | None = None) -> dict[str, Any]:
    payload = load_json(path)
    result = classify_payload(payload, expected_type=expected_type)
    result["path"] = str(path)
    return result


def migrated_payload(payload: dict[str, Any], classification: dict[str, Any]) -> dict[str, Any]:
    if classification.get("status") != "needs_migration":
        return dict(payload)
    if classification.get("migration") != "add_schema_version_1":
        raise SystemExit(f"未知迁移规则：{classification.get('migration')}")
    next_payload = dict(payload)
    next_payload["schema_version"] = CURRENT_SCHEMA_VERSION
    return next_payload


def unique_backup_path(path: pathlib.Path) -> pathlib.Path:
    base = path.with_name(f"{path.name}.backup-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    if not base.exists():
        return base
    for index in range(1, 100):
        candidate = path.with_name(f"{base.name}-{index}")
        if not candidate.exists():
            return candidate
    raise SystemExit(f"无法生成唯一备份路径：{path}")


def migrate_file(path: pathlib.Path, *, apply: bool) -> dict[str, Any]:
    payload = load_json(path)
    classification = classify_payload(payload)
    if classification.get("status") == "rejected":
        return {
            "schema_id": "redcap-config-migration-result",
            "ok": False,
            "path": str(path),
            "status": "rejected",
            "classification": classification,
            "failures": classification.get("failures", []),
        }
    if classification.get("status") == "direct_read":
        return {
            "schema_id": "redcap-config-migration-result",
            "ok": True,
            "path": str(path),
            "status": "already_current",
            "classification": classification,
            "failures": [],
        }
    next_payload = migrated_payload(payload, classification)
    backup_path = unique_backup_path(path)
    receipt_path = path.with_name(f"{path.name}.migration-receipt.json")
    result = {
        "schema_id": "redcap-config-migration-result",
        "ok": True,
        "path": str(path),
        "status": "dry_run" if not apply else "applied",
        "classification": classification,
        "target_schema_version": CURRENT_SCHEMA_VERSION,
        "backup_path": str(backup_path),
        "receipt_path": str(receipt_path),
        "migrated_payload": next_payload if not apply else None,
        "failures": [],
    }
    if not apply:
        return result
    shutil.copy2(path, backup_path)
    write_json(path, next_payload)
    receipt = {
        "schema_id": "redcap-config-migration-receipt",
        "created_at": iso_now(),
        "source_path": str(path),
        "backup_path": str(backup_path),
        "from_schema_version": classification.get("schema_version"),
        "to_schema_version": CURRENT_SCHEMA_VERSION,
        "migration": classification.get("migration"),
    }
    write_json(receipt_path, receipt)
    after = classify_file(path)
    result["post_migration_classification"] = after
    if after.get("status") != "direct_read":
        result["ok"] = False
        result["failures"].append("迁移后配置仍不能 direct_read")
    if not backup_path.exists():
        result["ok"] = False
        result["failures"].append("迁移未生成备份")
    if not receipt_path.exists():
        result["ok"] = False
        result["failures"].append("迁移未生成回执")
    return result


def current_generation_checks() -> list[dict[str, Any]]:
    from project_install import init_project, package_to  # noqa: PLC0415

    checks: list[dict[str, Any]] = []
    checks.append({"id": "project-installation-contract", **classify_file(PROJECT_INSTALL_CONTRACT)})
    with tempfile.TemporaryDirectory(prefix="redcap-config-compat-") as raw:
        root = pathlib.Path(raw)
        package = root / "redcap.zip"
        package_result = package_to(package)
        checks.append({
            "id": "package-command",
            "ok": bool(package_result.get("ok")),
            "status": "direct_read" if package_result.get("ok") else "rejected",
            "failures": package_result.get("failures", []),
        })
        if package_result.get("ok"):
            with zipfile.ZipFile(package) as archive:
                manifest = json.loads(archive.read(f"{PACKAGE_ROOT}/install-manifest.json").decode("utf-8"))
            checks.append({"id": "package-manifest", **classify_payload(manifest, expected_type="package_manifest")})
            project = root / "project"
            project.mkdir()
            with zipfile.ZipFile(package) as archive:
                archive.extractall(project)
            init_result = init_project(project, project / PACKAGE_ROOT)
            checks.append({
                "id": "project-init",
                "ok": bool(init_result.get("ok")),
                "status": "direct_read" if init_result.get("ok") else "rejected",
                "failures": init_result.get("failures", []),
            })
            install_json = project / PACKAGE_ROOT / "install.json"
            checks.append({"id": "project-install-record", **classify_file(install_json, expected_type="project_installation_record")})
            legacy_project = root / "legacy-project"
            legacy_project.mkdir()
            legacy_root = legacy_project / PACKAGE_ROOT
            shutil.copytree(project / PACKAGE_ROOT, legacy_root)
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
            legacy_compat = legacy_init.get("compatibility") if isinstance(legacy_init.get("compatibility"), dict) else {}
            checks.append({
                "id": "project-init-legacy-install-migration",
                "ok": legacy_init.get("ok") is True
                and legacy_compat.get("status") == "migrated"
                and any(str(item).endswith(".migration-receipt.json") for item in legacy_init.get("created", [])),
                "status": legacy_compat.get("status"),
                "init": legacy_init,
                "failures": legacy_init.get("failures", []),
            })
            rejected_project = root / "rejected-project"
            rejected_project.mkdir()
            rejected_root = rejected_project / PACKAGE_ROOT
            shutil.copytree(project / PACKAGE_ROOT, rejected_root)
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
            before_unknown_payload = load_json(rejected_install)
            rejected_init = init_project(rejected_project, rejected_root)
            after_unknown_payload = load_json(rejected_install)
            checks.append({
                "id": "project-init-unknown-version-rejected",
                "ok": rejected_init.get("ok") is False and before_unknown_payload == after_unknown_payload,
                "status": "rejected",
                "init": rejected_init,
                "install_json_unchanged": before_unknown_payload == after_unknown_payload,
                "failures": [] if rejected_init.get("ok") is False else ["未知版本未被 init 阻断"],
            })
    return checks


def project_install_integration_probe() -> dict[str, Any]:
    from project_install import init_project, package_to  # noqa: PLC0415

    with tempfile.TemporaryDirectory(prefix="redcap-config-probe-") as raw:
        root = pathlib.Path(raw)
        package = root / "redcap.zip"
        package_result = package_to(package)
        if package_result.get("ok") is not True:
            return {
                "ok": False,
                "stage": "package",
                "failures": package_result.get("failures", ["package failed"]),
            }
        project = root / "project"
        project.mkdir()
        with zipfile.ZipFile(package) as archive:
            archive.extractall(project)
        package_root = project / PACKAGE_ROOT
        baseline_init = init_project(project, package_root)
        if baseline_init.get("ok") is not True:
            return {
                "ok": False,
                "stage": "baseline-init",
                "failures": baseline_init.get("failures", ["baseline init failed"]),
            }
        legacy_project = root / "legacy-project"
        legacy_project.mkdir()
        legacy_root = legacy_project / PACKAGE_ROOT
        shutil.copytree(package_root, legacy_root)
        legacy_install = legacy_root / "install.json"
        legacy_before = {
            "schema_id": "redcap-project-installation",
            "installed_at": "2026-06-20T00:00:00+00:00",
            "project": str(legacy_project),
            "package_root": str(legacy_root),
            "hook_config": str(legacy_project / ".codex" / "hooks.json"),
            "codex_config": str(legacy_project / ".codex" / "config.toml"),
            "runtime_bin": str(legacy_root / "runtime" / "bin" / "redcap"),
        }
        write_json(legacy_install, legacy_before)
        legacy_init = init_project(legacy_project, legacy_root)
        legacy_after = load_json(legacy_install)
        legacy_created = [str(item) for item in legacy_init.get("created", [])]
        legacy_receipt = next((item for item in legacy_created if item.endswith(".migration-receipt.json")), None)
        legacy_backup = next((item for item in legacy_created if ".backup-" in item), None)

        rejected_project = root / "rejected-project"
        rejected_project.mkdir()
        rejected_root = rejected_project / PACKAGE_ROOT
        shutil.copytree(package_root, rejected_root)
        rejected_install = rejected_root / "install.json"
        rejected_before = {
            "schema_id": "redcap-project-installation",
            "schema_version": 999,
            "installed_at": "2026-06-20T00:00:00+00:00",
            "project": str(rejected_project),
            "package_root": str(rejected_root),
            "hook_config": str(rejected_project / ".codex" / "hooks.json"),
            "codex_config": str(rejected_project / ".codex" / "config.toml"),
            "runtime_bin": str(rejected_root / "runtime" / "bin" / "redcap"),
        }
        write_json(rejected_install, rejected_before)
        rejected_init = init_project(rejected_project, rejected_root)
        rejected_after = load_json(rejected_install)
        rejected_codex_created = (rejected_project / ".codex").exists()

    def same_path_value(left: Any, right: Any) -> bool:
        if left == right:
            return True
        if not isinstance(left, str) or not isinstance(right, str):
            return False
        try:
            return pathlib.Path(left).resolve() == pathlib.Path(right).resolve()
        except OSError:
            return False

    preserved_fields = all(
        same_path_value(legacy_before.get(key), legacy_after.get(key))
        for key in ["hook_config", "codex_config", "runtime_bin"]
    )
    legacy_ok = (
        legacy_init.get("ok") is True
        and legacy_after.get("schema_version") == CURRENT_SCHEMA_VERSION
        and preserved_fields
        and bool(legacy_receipt)
        and bool(legacy_backup)
    )
    rejected_ok = (
        rejected_init.get("ok") is False
        and rejected_after == rejected_before
        and not rejected_codex_created
    )
    return {
        "schema_id": "redcap-config-project-install-integration-probe",
        "ok": legacy_ok and rejected_ok,
        "legacy_missing_version": {
            "before_schema_version": legacy_before.get("schema_version"),
            "after_schema_version": legacy_after.get("schema_version"),
            "init_ok": legacy_init.get("ok"),
            "compatibility_status": (legacy_init.get("compatibility") or {}).get("status") if isinstance(legacy_init.get("compatibility"), dict) else None,
            "backup_created": bool(legacy_backup),
            "receipt_created": bool(legacy_receipt),
            "host_config_fields_semantically_preserved": preserved_fields,
            "host_config_fields_note": "init 会将临时目录路径规范化；迁移本身的字面字段保留由 migration-preserves-host-config-fields 负向探针覆盖。",
        },
        "unknown_version": {
            "before_schema_version": rejected_before.get("schema_version"),
            "after_schema_version": rejected_after.get("schema_version"),
            "init_ok": rejected_init.get("ok"),
            "install_json_unchanged": rejected_after == rejected_before,
            "codex_config_created": rejected_codex_created,
        },
        "failures": [] if legacy_ok and rejected_ok else ["project-install integration probe failed"],
    }


def fixture_negative_checks() -> list[dict[str, Any]]:
    legacy = {
        "schema_id": "redcap-project-installation",
        "installed_at": "2026-06-20T00:00:00+00:00",
        "project": "/tmp/project",
        "package_root": "/tmp/project/.redcap",
        "hook_config": "/tmp/project/.codex/hooks.json",
        "codex_config": "/tmp/project/.codex/config.toml",
        "runtime_bin": "/tmp/project/.redcap/runtime/bin/redcap",
    }
    unknown_version = {**legacy, "schema_version": 999}
    unknown_field = {**legacy, "schema_version": 1, "surprise": True}
    legacy_result = classify_payload(legacy, expected_type="project_installation_record")
    unknown_version_result = classify_payload(unknown_version, expected_type="project_installation_record")
    unknown_field_result = classify_payload(unknown_field, expected_type="project_installation_record")
    with tempfile.TemporaryDirectory(prefix="redcap-config-migrate-") as raw:
        path = pathlib.Path(raw) / "install.json"
        write_json(path, legacy)
        dry_run = migrate_file(path, apply=False)
        unchanged_after_dry_run = load_json(path).get("schema_version") is None
        before_apply = load_json(path)
        apply_result = migrate_file(path, apply=True)
        after_apply = load_json(path)
        preserved_codex_fields = (
            before_apply.get("hook_config") == after_apply.get("hook_config")
            and before_apply.get("codex_config") == after_apply.get("codex_config")
            and before_apply.get("runtime_bin") == after_apply.get("runtime_bin")
        )
    return [
        {
            "id": "legacy-missing-version-needs-migration",
            "ok": legacy_result.get("status") == "needs_migration",
            "classification": legacy_result,
        },
        {
            "id": "unknown-version-rejected",
            "ok": unknown_version_result.get("status") == "rejected",
            "classification": unknown_version_result,
        },
        {
            "id": "unknown-field-rejected",
            "ok": unknown_field_result.get("status") == "rejected",
            "classification": unknown_field_result,
        },
        {
            "id": "migration-dry-run-no-write",
            "ok": dry_run.get("ok") is True and dry_run.get("status") == "dry_run" and unchanged_after_dry_run,
            "migration": dry_run,
            "unchanged_after_dry_run": unchanged_after_dry_run,
        },
        {
            "id": "migration-apply-backup-and-receipt",
            "ok": apply_result.get("ok") is True and apply_result.get("status") == "applied",
            "migration": apply_result,
        },
        {
            "id": "migration-preserves-host-config-fields",
            "ok": preserved_codex_fields,
            "preserved_fields": ["hook_config", "codex_config", "runtime_bin"],
        },
    ]


def full_report() -> dict[str, Any]:
    contract = load_contract()
    contract_failures = validate_contract(contract)
    positive = current_generation_checks()
    negative = fixture_negative_checks()
    integration_probe = project_install_integration_probe()
    failures = list(contract_failures)
    for item in positive + negative:
        if item.get("ok") is not True:
            failures.append(f"{item.get('id')} failed")
    if integration_probe.get("ok") is not True:
        failures.append("project-install integration probe failed")
    positive_ids = [str(item.get("id")) for item in positive]
    negative_ids = [str(item.get("id")) for item in negative]
    report = {
        "schema_id": "redcap-config-contract-compat-report",
        "rsp": "RSP-27",
        "ok": not failures,
        "contract": str(CONTRACT),
        "positive_checks": positive,
        "negative_probes": negative,
        "integration_probe_log": integration_probe,
        "acceptance": {
            "positive": {
                "status": "pass" if all(item.get("ok") is True for item in positive) else "fail",
                "checks": positive_ids,
            },
            "negative": {
                "status": "pass" if all(item.get("ok") is True for item in negative) else "fail",
                "checks": negative_ids,
            },
        },
        "changed_reality": [
            "RedCap 自有项目级安装记录和发布清单写入 schema_version。",
            "配置兼容检查区分 direct_read、needs_migration、rejected。",
            "旧 install.json 可 dry-run 预览并 apply 迁移，apply 保留备份和迁移回执。",
            "未知版本和未知字段被拒绝，不能静默通过。",
            "宿主配置不被强行写入 RedCap 私有字段，改由版本化模板和安装合同约束。"
        ],
        "artifacts": [
            "assets/contracts/config-contract-compat.json",
            "runtime/core/config_contract_compat.py",
            "runtime/core/project_install.py",
            "runtime/bin/redcap",
            "runtime/core/check_runner.py"
        ],
        "failures": failures,
    }
    return report


def cmd_check(args: argparse.Namespace) -> int:
    if args.file:
        result = classify_file(pathlib.Path(args.file), expected_type=args.config_type)
        if args.out:
            write_json(pathlib.Path(args.out), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("status") == "direct_read":
            print("REDCAP_CONFIG_COMPAT_DIRECT_READ")
            return 0
        if result.get("status") == "needs_migration":
            print("REDCAP_CONFIG_COMPAT_NEEDS_MIGRATION")
            return 2
        return 1
    report = full_report()
    if args.out:
        write_json(pathlib.Path(args.out), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["ok"]:
        print("REDCAP_CONFIG_CONTRACT_COMPAT_OK")
        return 0
    return 1


def cmd_migrate(args: argparse.Namespace) -> int:
    result = migrate_file(pathlib.Path(args.file), apply=args.apply)
    if args.out:
        write_json(pathlib.Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok"):
        print("REDCAP_CONFIG_MIGRATION_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    report = full_report()
    failures = list(report.get("failures", []))
    statuses = {item.get("id"): item.get("ok") for item in report.get("positive_checks", []) + report.get("negative_probes", [])}
    for required in [
        "project-installation-contract",
        "package-manifest",
        "project-install-record",
        "project-init-legacy-install-migration",
        "project-init-unknown-version-rejected",
        "legacy-missing-version-needs-migration",
        "unknown-version-rejected",
        "unknown-field-rejected",
        "migration-dry-run-no-write",
        "migration-apply-backup-and-receipt",
        "migration-preserves-host-config-fields",
    ]:
        if statuses.get(required) is not True:
            failures.append(f"self-check missing or failed: {required}")
    print(json.dumps({"ok": not failures, "failures": failures, "report": report}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_CONFIG_CONTRACT_COMPAT_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap 配置契约版本兼容性检查")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("compat-check")
    check.add_argument("--file")
    check.add_argument("--config-type")
    check.add_argument("--out")
    check.set_defaults(func=cmd_check)
    migrate = sub.add_parser("migrate")
    migrate.add_argument("--file", required=True)
    mode = migrate.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    migrate.add_argument("--out")
    migrate.set_defaults(func=cmd_migrate)
    sub.add_parser("self-check").set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

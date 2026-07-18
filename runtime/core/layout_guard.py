#!/usr/bin/env python3
"""Executable directory structure guard for RedCap."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import stat
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_POLICY = REPO_ROOT / "assets" / "contracts" / "directory-structure.json"
EXPECTED_POLICY_SHA256 = "f3c261e60736fd35e0518fe54d8f83beb93a2f03172efd9b65bd40e6bdd56662"


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}") from exc


def rel(path: pathlib.Path, root: pathlib.Path) -> str:
    return path.relative_to(root).as_posix()


def load_policy(path: pathlib.Path) -> dict[str, Any]:
    policy = load_json(path)
    if not isinstance(policy, dict):
        raise SystemExit("directory policy must be a JSON object")
    if policy.get("schema_id") != "redcap-directory-structure-policy":
        raise SystemExit("directory policy schema_id must be redcap-directory-structure-policy")
    required_keys = [
        "root_allowed_entries",
        "direct_children_allowed",
        "required_paths",
        "functional_directories",
        "file_placement_rules",
        "ignored_names",
        "forbidden_names",
        "asset_unit",
        "future_expansion_policy",
    ]
    missing = [key for key in required_keys if key not in policy]
    if missing:
        raise SystemExit(f"directory policy missing keys: {', '.join(missing)}")
    if not isinstance(policy["root_allowed_entries"], dict) or not policy["root_allowed_entries"]:
        raise SystemExit("directory policy root_allowed_entries must be a non-empty object")
    for list_key in ["required_paths", "ignored_names", "forbidden_names"]:
        values = policy[list_key]
        if not isinstance(values, list) or not all(isinstance(value, str) and value for value in values):
            raise SystemExit(f"directory policy {list_key} must be a string list")
    if not isinstance(policy["functional_directories"], dict) or not policy["functional_directories"]:
        raise SystemExit("directory policy functional_directories must be a non-empty object")
    placement_rules = policy["file_placement_rules"]
    if not isinstance(placement_rules, list) or not placement_rules:
        raise SystemExit("directory policy file_placement_rules must be a non-empty list")
    seen_rule_paths: set[str] = set()
    for rule in placement_rules:
        if not isinstance(rule, dict):
            raise SystemExit("directory policy file_placement_rules entries must be objects")
        for key in ["path", "role", "recursive"]:
            if key not in rule:
                raise SystemExit(f"file placement rule missing {key}")
        if not isinstance(rule["path"], str) or not rule["path"]:
            raise SystemExit("file placement rule path must be a non-empty string")
        if not isinstance(rule["role"], str) or not rule["role"]:
            raise SystemExit("file placement rule role must be a non-empty string")
        if not isinstance(rule["recursive"], bool):
            raise SystemExit("file placement rule recursive must be boolean")
        if "allowed_names" not in rule and "allowed_extensions" not in rule:
            raise SystemExit(f"file placement rule must define allowed_names or allowed_extensions: {rule['path']}")
        if rule["path"] in seen_rule_paths:
            raise SystemExit(f"duplicate file placement rule path: {rule['path']}")
        seen_rule_paths.add(rule["path"])
    return policy


def policy_integrity_failures(path: pathlib.Path) -> list[str]:
    if not EXPECTED_POLICY_SHA256:
        return ["directory policy hash lock is not configured"]
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != EXPECTED_POLICY_SHA256:
        return [
            "directory policy hash mismatch: "
            f"{path} has {actual}, expected {EXPECTED_POLICY_SHA256}. "
            "Policy changes must update the layout guard through the reviewed runtime path."
        ]
    return []


def ignored(path: pathlib.Path, ignored_names: set[str]) -> bool:
    return any(part in ignored_names for part in path.parts)


def check_required_paths(root: pathlib.Path, policy: dict[str, Any], failures: list[str]) -> None:
    for required in policy["required_paths"]:
        if not (root / required).exists():
            failures.append(f"missing required layout path: {required}")


def check_root_entries(root: pathlib.Path, policy: dict[str, Any], failures: list[str]) -> None:
    allowed = set(policy["root_allowed_entries"].keys())
    ignored_names = set(policy["ignored_names"])
    for child in root.iterdir():
        if child.name in ignored_names:
            continue
        if child.name not in allowed:
            failures.append(f"root entry not classified by directory policy: {child.name}")


def check_direct_children(root: pathlib.Path, policy: dict[str, Any], failures: list[str]) -> None:
    ignored_names = set(policy["ignored_names"])
    direct = policy["direct_children_allowed"]
    if not isinstance(direct, dict):
        failures.append("directory policy direct_children_allowed must be an object")
        return
    for parent_rel, allowed_children in direct.items():
        if not isinstance(allowed_children, list) or not all(isinstance(item, str) for item in allowed_children):
            failures.append(f"direct_children_allowed for {parent_rel} must be a string list")
            continue
        parent = root / parent_rel
        if not parent.exists():
            failures.append(f"direct-child policy parent is missing: {parent_rel}")
            continue
        allowed = set(allowed_children)
        for child in parent.iterdir():
            if child.name in ignored_names:
                continue
            if child.name not in allowed:
                failures.append(f"{parent_rel} child not classified by directory policy: {rel(child, root)}")


def check_forbidden_names(root: pathlib.Path, policy: dict[str, Any], failures: list[str]) -> None:
    forbidden = {name.lower() for name in policy["forbidden_names"]}
    ignored_names = set(policy["ignored_names"])
    for path in root.rglob("*"):
        if ignored(path.relative_to(root), ignored_names):
            continue
        if path.name.lower() in forbidden:
            failures.append(f"forbidden sprawl name present: {rel(path, root)}")


def executable_bit_set(path: pathlib.Path) -> bool:
    mode = path.stat().st_mode
    return bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


def check_asset_unit(root: pathlib.Path, policy: dict[str, Any], failures: list[str]) -> None:
    asset_policy = policy["asset_unit"]
    if not isinstance(asset_policy, dict):
        failures.append("directory policy asset_unit must be an object")
        return
    asset_root = root / str(asset_policy.get("path") or "assets")
    ignored_names = set(policy["ignored_names"])
    exceptions = set(asset_policy.get("exceptions") or [])
    denied_exts = set(asset_policy.get("deny_executable_extensions") or [])
    if not asset_root.exists():
        failures.append(f"asset unit path is missing: {rel(asset_root, root)}")
        return
    for path in asset_root.rglob("*"):
        if not path.is_file():
            continue
        relative = rel(path, root)
        if relative in exceptions or ignored(path.relative_to(root), ignored_names):
            continue
        if path.suffix in denied_exts:
            failures.append(f"asset unit contains executable/source-like file extension: {relative}")
        if asset_policy.get("deny_executable_bits") is True and executable_bit_set(path):
            failures.append(f"asset unit file has executable bit set: {relative}")


def check_functional_directory_coverage(policy: dict[str, Any], failures: list[str]) -> None:
    rules_by_path = {
        rule["path"]: rule for rule in policy["file_placement_rules"]
        if isinstance(rule, dict) and isinstance(rule.get("path"), str)
    }
    functional_paths_by_role: dict[str, set[str]] = {}
    for role, record in policy["functional_directories"].items():
        if not isinstance(record, dict):
            failures.append(f"functional directory record must be object: {role}")
            continue
        paths = record.get("paths")
        if not isinstance(paths, list) or not all(isinstance(path, str) and path for path in paths):
            failures.append(f"functional directory paths must be a string list: {role}")
            continue
        functional_paths_by_role[role] = set(paths)
        for directory in paths:
            rule = rules_by_path.get(directory)
            if rule is None:
                failures.append(f"functional directory has no file placement rule: role={role} path={directory}")
                continue
            if rule.get("role") != role:
                failures.append(
                    "functional directory role does not match file placement rule: "
                    f"path={directory} functional_role={role} placement_role={rule.get('role')}"
                )
    functional_roles = set(functional_paths_by_role)
    for rule in policy["file_placement_rules"]:
        role = rule.get("role")
        path = rule.get("path")
        if role in functional_roles and path not in functional_paths_by_role[role]:
            failures.append(
                "file placement rule claims functional role outside functional directory map: "
                f"path={path} role={role}"
            )


def rule_matches(path: pathlib.Path, root: pathlib.Path, rule: dict[str, Any]) -> bool:
    rule_root = root / rule["path"]
    if path.parent == rule_root:
        return True
    if not rule.get("recursive"):
        return False
    try:
        path.relative_to(rule_root)
    except ValueError:
        return False
    return True


def matching_placement_rule(path: pathlib.Path, root: pathlib.Path, policy: dict[str, Any]) -> dict[str, Any] | None:
    rules = [
        rule for rule in policy["file_placement_rules"]
        if rule_matches(path, root, rule)
    ]
    if not rules:
        return None
    return max(rules, key=lambda rule: len(pathlib.PurePosixPath(rule["path"]).parts))


def check_file_placement(root: pathlib.Path, policy: dict[str, Any], failures: list[str]) -> None:
    ignored_names = set(policy["ignored_names"])
    root_allowed = policy["root_allowed_entries"]
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = rel(path, root)
        if ignored(path.relative_to(root), ignored_names):
            continue
        if path.parent == root and path.name in root_allowed:
            continue
        rule = matching_placement_rule(path, root, policy)
        if rule is None:
            failures.append(f"file has no functional placement rule: {relative}")
            continue
        allowed = False
        allowed_names = rule.get("allowed_names") or []
        allowed_extensions = rule.get("allowed_extensions") or []
        if path.name in allowed_names:
            allowed = True
        if path.suffix in allowed_extensions:
            allowed = True
        if not allowed:
            failures.append(
                "file placement rule disallows path: "
                f"{relative} role={rule['role']} allowed_names={allowed_names} "
                f"allowed_extensions={allowed_extensions}"
            )
        if rule.get("deny_executable_bits") is True and executable_bit_set(path):
            failures.append(f"file placement rule denies executable bit: {relative} role={rule['role']}")


def check_layout(root: pathlib.Path, policy: dict[str, Any]) -> list[str]:
    if root.name == ".redcap" and (root / "install.json").exists():
        return check_installed_package_layout(root)
    failures: list[str] = []
    if not root.exists() or not root.is_dir():
        return [f"root is not a directory: {root}"]
    check_functional_directory_coverage(policy, failures)
    check_required_paths(root, policy, failures)
    check_root_entries(root, policy, failures)
    check_direct_children(root, policy, failures)
    check_forbidden_names(root, policy, failures)
    check_file_placement(root, policy, failures)
    check_asset_unit(root, policy, failures)
    return failures


def check_installed_package_layout(root: pathlib.Path) -> list[str]:
    failures: list[str] = []
    project_root = root.parent
    required = [
        "README.md",
        ".gitignore",
        "runtime/bin/redcap",
        "assets/contracts/codex-hooks.template.json",
        "assets/contracts/directory-structure.json",
        "assets/contracts/project-installation.json",
        "assets/docs/README.md",
        "assets/knowledge/README.md",
        "assets/archaeology/README.md",
        "install-manifest.json",
        "install.json",
        "evidence",
        "logs",
        "state",
        "tmp",
    ]
    for item in required:
        if not (root / item).exists():
            failures.append(f"installed package missing path: {item}")
    if not (project_root / ".codex" / "hooks.json").exists():
        failures.append("installed project missing path: .codex/hooks.json")
    forbidden = [".git", "node_modules"]
    for name in forbidden:
        if (root / name).exists():
            failures.append(f"installed package contains forbidden path: {name}")
    return failures


def write_fixture_file(path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("fixture\n", encoding="utf-8")


def create_valid_fixture(root: pathlib.Path, policy: dict[str, Any]) -> None:
    for entry in policy["root_allowed_entries"]:
        target = root / entry
        if pathlib.PurePosixPath(entry).suffix:
            write_fixture_file(target)
        else:
            target.mkdir(parents=True, exist_ok=True)
    for parent_rel, children in policy["direct_children_allowed"].items():
        parent = root / parent_rel
        parent.mkdir(parents=True, exist_ok=True)
        for child in children:
            target = parent / child
            if pathlib.PurePosixPath(child).suffix:
                write_fixture_file(target)
            else:
                target.mkdir(parents=True, exist_ok=True)
    for required in policy["required_paths"]:
        write_fixture_file(root / required)


def fixture_failures(policy: dict[str, Any], mutate: Any) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="redcap-layout-guard-") as tmp_raw:
        root = pathlib.Path(tmp_raw)
        create_valid_fixture(root, policy)
        mutate(root)
        return check_layout(root, policy)


def cmd_check(args: argparse.Namespace) -> int:
    policy_path = pathlib.Path(args.policy).resolve()
    policy = load_policy(policy_path)
    root = pathlib.Path(args.root).resolve()
    failures = policy_integrity_failures(policy_path)
    failures.extend(check_layout(root, policy))
    result = {
        "ok": not failures,
        "root": str(root),
        "policy": str(policy_path),
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_LAYOUT_OK")
    return 0


def cmd_self_check(args: argparse.Namespace) -> int:
    policy_path = pathlib.Path(args.policy).resolve()
    policy = load_policy(policy_path)
    failures: list[str] = []
    failures.extend(policy_integrity_failures(policy_path))

    valid = fixture_failures(policy, lambda _root: None)
    if valid:
        failures.append(f"valid fixture failed: {valid}")

    cases = [
        (
            "root-sprawl",
            lambda root: (root / "scratch").mkdir(),
            "root entry not classified",
        ),
        (
            "runtime-child-sprawl",
            lambda root: (root / "runtime" / "misc").mkdir(),
            "runtime child not classified",
        ),
        (
            "asset-executable-extension",
            lambda root: write_fixture_file(root / "assets" / "docs" / "tool.py"),
            "asset unit contains executable/source-like file extension",
        ),
        (
            "asset-executable-bit",
            lambda root: (write_fixture_file(root / "assets" / "docs" / "runbook.md"), os.chmod(root / "assets" / "docs" / "runbook.md", 0o755)),
            "asset unit file has executable bit set",
        ),
        (
            "host-entry-sprawl",
            lambda root: write_fixture_file(root / ".codex" / "notes.md"),
            ".codex child not classified",
        ),
        (
            "missing-required-path",
            lambda root: (root / "runtime" / "bin" / "redcap").unlink(),
            "missing required layout path",
        ),
        (
            "case-insensitive-forbidden-name",
            lambda root: (root / "assets" / "evidence" / "Temp").mkdir(parents=True),
            "forbidden sprawl name present",
        ),
        (
            "placement-rule-executable-bit-drift",
            lambda root: (write_fixture_file(root / "assets" / "contracts" / "executable.json"), os.chmod(root / "assets" / "contracts" / "executable.json", 0o755)),
            "file placement rule denies executable bit",
        ),
        (
            "runtime-asset-source-drift",
            lambda root: write_fixture_file(root / "runtime" / "prism" / "prompts" / "tool.py"),
            "file placement rule disallows path",
        ),
        (
            "source-logic-runtime-asset-drift",
            lambda root: write_fixture_file(root / "runtime" / "core" / "prompt.md"),
            "file placement rule disallows path",
        ),
        (
            "contract-in-docs-drift",
            lambda root: write_fixture_file(root / "assets" / "docs" / "schema.json"),
            "file placement rule disallows path",
        ),
        (
            "archaeology-source-drift",
            lambda root: write_fixture_file(root / "assets" / "archaeology" / "extract.py"),
            "file placement rule disallows path",
        ),
        (
            "prism-root-file-drift",
            lambda root: write_fixture_file(root / "runtime" / "prism" / "notes.md"),
            "file placement rule disallows path",
        ),
    ]
    for name, mutate, expected in cases:
        case_failures = fixture_failures(policy, mutate)
        if not any(expected in failure for failure in case_failures):
            failures.append(f"{name}: expected failure containing {expected!r}, got {case_failures}")

    with tempfile.TemporaryDirectory(prefix="redcap-layout-policy-") as tmp_raw:
        eroded_policy = pathlib.Path(tmp_raw) / "directory-structure.json"
        payload = dict(policy)
        root_allowed = dict(payload["root_allowed_entries"])
        root_allowed["scratch"] = {
            "kind": "asset-unit",
            "reason": "fixture erosion"
        }
        payload["root_allowed_entries"] = root_allowed
        eroded_policy.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        erosion_failures = policy_integrity_failures(eroded_policy)
        if not any("directory policy hash mismatch" in failure for failure in erosion_failures):
            failures.append(f"policy-erosion: expected hash mismatch, got {erosion_failures}")

    coverage_policy = json.loads(json.dumps(policy))
    coverage_policy["functional_directories"]["runtime_assets"]["paths"].append("runtime/prism/missing-assets")
    with tempfile.TemporaryDirectory(prefix="redcap-layout-functional-") as tmp_raw:
        root = pathlib.Path(tmp_raw)
        create_valid_fixture(root, coverage_policy)
        coverage_failures = check_layout(root, coverage_policy)
        if not any("functional directory has no file placement rule" in failure for failure in coverage_failures):
            failures.append(f"functional-directory-without-placement-rule: expected coverage failure, got {coverage_failures}")

    reverse_coverage_policy = json.loads(json.dumps(policy))
    reverse_coverage_policy["file_placement_rules"].append({
        "path": "runtime/prism/rogue-assets",
        "role": "runtime_assets",
        "recursive": True,
        "allowed_extensions": [".md"],
        "deny_executable_bits": True,
    })
    with tempfile.TemporaryDirectory(prefix="redcap-layout-functional-reverse-") as tmp_raw:
        root = pathlib.Path(tmp_raw)
        create_valid_fixture(root, reverse_coverage_policy)
        reverse_failures = check_layout(root, reverse_coverage_policy)
        if not any("file placement rule claims functional role outside functional directory map" in failure for failure in reverse_failures):
            failures.append(f"placement-rule-functional-role-outside-map: expected reverse coverage failure, got {reverse_failures}")

    duplicate_policy = json.loads(json.dumps(policy))
    duplicate_policy["file_placement_rules"].append(dict(duplicate_policy["file_placement_rules"][0]))
    try:
        duplicate_path = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        try:
            json.dump(duplicate_policy, duplicate_path)
            duplicate_path.close()
            try:
                load_policy(pathlib.Path(duplicate_path.name))
            except SystemExit as exc:
                duplicate_error = str(exc)
            else:
                duplicate_error = ""
        finally:
            pathlib.Path(duplicate_path.name).unlink(missing_ok=True)
    except Exception as exc:
        duplicate_error = str(exc)
    if "duplicate file placement rule path" not in duplicate_error:
        failures.append(f"duplicate-placement-rule-path: expected duplicate path failure, got {duplicate_error!r}")

    result = {
        "ok": not failures,
        "policy": str(policy_path),
        "negative_cases": [name for name, _mutate, _expected in cases] + [
            "policy-erosion",
            "functional-directory-without-placement-rule",
            "placement-rule-functional-role-outside-map",
            "duplicate-placement-rule-path",
        ],
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_LAYOUT_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify RedCap directory structure policy")
    parser.add_argument("--root", default=str(REPO_ROOT))
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("check")
    subparsers.add_parser("self-check")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    command = args.command or "check"
    if command == "check":
        return cmd_check(args)
    if command == "self-check":
        return cmd_self_check(args)
    raise SystemExit(f"unknown command: {command}")


if __name__ == "__main__":
    sys.exit(main())

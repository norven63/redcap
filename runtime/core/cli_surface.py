#!/usr/bin/env python3
"""Verify the public RedCap command surface against a compatibility contract."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CLI = REPO_ROOT / "runtime/bin/redcap"
DEFAULT_CONTRACT = REPO_ROOT / "assets/contracts/cli-surface-compat.json"

CASE_LABEL_RE = re.compile(r"^\s{2}([A-Za-z0-9_.|*-]+)\)")
USAGE_RE = re.compile(r"^\s*runtime/bin/redcap\s+([A-Za-z0-9_.-]+)\b(.*)$")
COMMAND_DESC_RE = re.compile(r"^\s{2}([A-Za-z0-9_.-]+)\s{2,}.+$")
IGNORED_CASE_LABELS = {"-h", "--help", "help", "*"}


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"json root must be object: {path}")
    return value


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sorted_unique(values: list[str]) -> list[str]:
    return sorted(set(values))


def extract_surface(cli_text: str) -> dict[str, Any]:
    usage_commands: dict[str, list[str]] = {}
    command_descriptions: list[str] = []
    case_routes: list[str] = []

    for line in cli_text.splitlines():
        usage_match = USAGE_RE.match(line)
        if usage_match:
            command = usage_match.group(1)
            usage_commands.setdefault(command, []).append(line.strip())

        desc_match = COMMAND_DESC_RE.match(line)
        if desc_match:
            command_descriptions.append(desc_match.group(1))

        case_match = CASE_LABEL_RE.match(line)
        if case_match:
            labels = case_match.group(1).split("|")
            for label in labels:
                if label in IGNORED_CASE_LABELS or label.startswith("-"):
                    continue
                case_routes.append(label)

    return {
        "case_routes": sorted_unique(case_routes),
        "command_descriptions": sorted_unique(command_descriptions),
        "help_usage_commands": sorted(usage_commands),
        "usage_lines": {key: usage_commands[key] for key in sorted(usage_commands)},
    }


def command_text(surface: dict[str, Any], command: str) -> str:
    lines = surface.get("usage_lines", {}).get(command, [])
    if not isinstance(lines, list):
        return ""
    return "\n".join(str(line) for line in lines)


def list_from_contract(contract: dict[str, Any], section: str, key: str) -> list[str]:
    value = contract.get(section, {}).get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SystemExit(f"contract.{section}.{key} must be a string list")
    return value


def required_usage_markers(contract: dict[str, Any]) -> list[dict[str, Any]]:
    value = contract.get("compatibility_promises", {}).get("required_usage_markers", [])
    if not isinstance(value, list):
        raise SystemExit("contract.compatibility_promises.required_usage_markers must be a list")
    for item in value:
        if not isinstance(item, dict):
            raise SystemExit("each required_usage_markers item must be an object")
        if not isinstance(item.get("command"), str) or not item["command"].strip():
            raise SystemExit("required_usage_markers item command must be a non-empty string")
        markers = item.get("markers")
        if not isinstance(markers, list) or not all(isinstance(marker, str) for marker in markers):
            raise SystemExit("required_usage_markers item markers must be a string list")
    return value


def validate_surface(contract: dict[str, Any], cli_text: str) -> dict[str, Any]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-cli-surface-compat":
        failures.append("contract schema_id must be redcap-cli-surface-compat")

    surface = extract_surface(cli_text)
    observed = contract.get("observed_baseline", {})
    if not isinstance(observed, dict):
        failures.append("contract observed_baseline must be an object")
        observed = {}

    baseline_case_routes = set(list_from_contract(contract, "observed_baseline", "case_routes"))
    baseline_help_commands = set(list_from_contract(contract, "observed_baseline", "help_usage_commands"))
    baseline_top_level = set(list_from_contract(contract, "observed_baseline", "top_level_commands"))
    current_case_routes = set(surface["case_routes"])
    current_help_commands = set(surface["help_usage_commands"])

    missing_case_routes = sorted(baseline_case_routes - current_case_routes)
    if missing_case_routes:
        failures.append(f"baseline case routes missing from runtime/bin/redcap: {missing_case_routes}")

    unregistered_case_routes = sorted(current_case_routes - baseline_case_routes)
    if unregistered_case_routes:
        failures.append(f"new case routes are not registered in cli-surface contract: {unregistered_case_routes}")

    missing_help_commands = sorted(baseline_help_commands - current_help_commands)
    if missing_help_commands:
        failures.append(f"baseline help commands missing from runtime/bin/redcap usage: {missing_help_commands}")

    unregistered_help_commands = sorted(current_help_commands - baseline_help_commands)
    if unregistered_help_commands:
        failures.append(f"new help commands are not registered in cli-surface contract: {unregistered_help_commands}")

    help_without_route = sorted((current_help_commands & baseline_top_level) - current_case_routes)
    if help_without_route:
        failures.append(f"help advertises commands without case routes: {help_without_route}")

    route_without_help = sorted((current_case_routes & baseline_top_level) - current_help_commands)
    if route_without_help:
        failures.append(f"case routes are not advertised in help usage: {route_without_help}")

    required_commands = list_from_contract(contract, "compatibility_promises", "required_top_level_commands")
    for command in required_commands:
        if command not in current_case_routes:
            failures.append(f"required command missing from case routes: {command}")
        if command not in current_help_commands:
            failures.append(f"required command missing from help usage: {command}")

    required_aliases = list_from_contract(contract, "compatibility_promises", "required_aliases")
    for alias in required_aliases:
        if alias not in current_case_routes:
            failures.append(f"required compatibility alias missing from case routes: {alias}")
        if alias not in current_help_commands:
            failures.append(f"required compatibility alias missing from help usage: {alias}")

    for item in required_usage_markers(contract):
        command = item["command"]
        text = command_text(surface, command)
        if not text:
            failures.append(f"required usage marker command has no usage line: {command}")
            continue
        for marker in item["markers"]:
            if marker not in text:
                failures.append(f"required usage marker missing for {command}: {marker}")

    return {
        "ok": not failures,
        "failures": failures,
        "extracted_surface": surface,
    }


def mutate_without_loom_route(text: str) -> str:
    return text.replace("  loom)\n", "  loom-disabled)\n", 1)


def mutate_without_gate_risk_level(text: str) -> str:
    return text.replace(
        "runtime/bin/redcap gate [--task TEXT|--request FILE] [--risk-level LEVEL]",
        "runtime/bin/redcap gate [--task TEXT|--request FILE] [--risk LEVEL]",
        1,
    )


def mutate_with_unregistered_route(text: str) -> str:
    marker = "  -h|--help|help)\n"
    injected = "  shadow-command)\n    exec echo shadow\n    ;;\n"
    return text.replace(marker, injected + marker, 1)


def mutate_long_task_help_drift(text: str) -> str:
    return text.replace(
        "runtime/bin/redcap long-task check|decide|start|record|complete|boundary-check|self-check [...]",
        "runtime/bin/redcap long-task check|decide|start|record|complete|boundary-pass|self-check [...]",
        1,
    )


def run_negative_probes(contract: dict[str, Any], cli_text: str) -> list[dict[str, Any]]:
    probes = [
        ("missing_loom_alias_route", mutate_without_loom_route),
        ("missing_gate_risk_level_marker", mutate_without_gate_risk_level),
        ("unregistered_shadow_command", mutate_with_unregistered_route),
        ("long_task_help_semantic_drift", mutate_long_task_help_drift),
    ]
    results: list[dict[str, Any]] = []
    for name, mutate in probes:
        mutated_text = mutate(cli_text)
        validation = validate_surface(contract, mutated_text)
        results.append(
            {
                "name": name,
                "expected_failure": True,
                "failed_as_expected": validation["ok"] is False,
                "failures": validation["failures"],
            }
        )
    return results


def evidence_payload(
    *,
    contract_path: pathlib.Path,
    cli_path: pathlib.Path,
    validation: dict[str, Any],
    negative_probes: list[dict[str, Any]],
) -> dict[str, Any]:
    negative_ok = all(item["failed_as_expected"] for item in negative_probes)
    return {
        "schema_id": "redcap-cli-surface-compat-evidence",
        "rsp": "RSP-19",
        "ok": bool(validation["ok"] and negative_ok),
        "contract_path": str(contract_path.relative_to(REPO_ROOT)),
        "cli_path": str(cli_path.relative_to(REPO_ROOT)),
        "acceptance": {
            "positive": {
                "status": "pass" if validation["ok"] else "fail",
                "checks": [
                    "baseline case routes match runtime/bin/redcap",
                    "help usage commands match runtime/bin/redcap",
                    "required compatibility aliases are routed and advertised",
                    "required parameter and subcommand markers are present",
                ],
            },
            "negative": {
                "status": "pass" if negative_ok else "fail",
                "checks": negative_probes,
            },
        },
        "changed_reality": [
            "RedCap 命令面现在有可运行的兼容合同检查。",
            "新增命令、删除旧别名、破坏参数标记、帮助文本语义漂移都会被本地探针发现。",
            "合同区分机械提取的当前基线和必须保留的兼容承诺。",
        ],
        "artifacts": [
            "assets/contracts/cli-surface-compat.json",
            "runtime/core/cli_surface.py",
            "runtime/bin/redcap",
            "runtime/core/check_runner.py",
        ],
        "validation": validation,
        "negative_probes": negative_probes,
    }


def cmd_extract(args: argparse.Namespace) -> int:
    cli_path = pathlib.Path(args.cli)
    surface = extract_surface(cli_path.read_text(encoding="utf-8"))
    payload = {"schema_id": "redcap-cli-surface-extract", "cli_path": str(cli_path), "surface": surface}
    if args.out:
        write_json(pathlib.Path(args.out), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    contract_path = pathlib.Path(args.contract)
    cli_path = pathlib.Path(args.cli)
    contract = load_json(contract_path)
    cli_text = cli_path.read_text(encoding="utf-8")
    validation = validate_surface(contract, cli_text)
    negative_probes = [] if args.skip_negative_probes else run_negative_probes(contract, cli_text)
    payload = evidence_payload(
        contract_path=contract_path,
        cli_path=cli_path,
        validation=validation,
        negative_probes=negative_probes,
    )
    if args.out:
        write_json(pathlib.Path(args.out), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload["ok"]:
        print("REDCAP_CLI_SURFACE_COMPAT_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    contract = load_json(DEFAULT_CONTRACT)
    cli_text = DEFAULT_CLI.read_text(encoding="utf-8")
    validation = validate_surface(contract, cli_text)
    negative_probes = run_negative_probes(contract, cli_text)
    failures: list[str] = []
    if not validation["ok"]:
        failures.extend(validation["failures"])
    for probe in negative_probes:
        if not probe["failed_as_expected"]:
            failures.append(f"negative probe unexpectedly passed: {probe['name']}")
    result = {
        "schema_id": "redcap-cli-surface-self-check",
        "ok": not failures,
        "failures": failures,
        "negative_probes": negative_probes,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_CLI_SURFACE_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify RedCap CLI compatibility surface")
    subparsers = parser.add_subparsers(dest="command")

    extract = subparsers.add_parser("extract")
    extract.add_argument("--cli", default=str(DEFAULT_CLI))
    extract.add_argument("--out")

    check = subparsers.add_parser("check")
    check.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    check.add_argument("--cli", default=str(DEFAULT_CLI))
    check.add_argument("--out")
    check.add_argument("--skip-negative-probes", action="store_true")

    subparsers.add_parser("self-check")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    command = args.command or "check"
    if command == "extract":
        return cmd_extract(args)
    if command == "check":
        return cmd_check(args)
    if command == "self-check":
        return cmd_self_check(args)
    raise SystemExit(f"unknown command: {command}")


if __name__ == "__main__":
    sys.exit(main())

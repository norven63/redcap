#!/usr/bin/env python3
"""Validate that completion claims are backed by multiple evidence classes."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REQUIRED_EVIDENCE_CLASSES = {
    "task_fact",
    "source_logic",
    "contract_logic",
    "negative_check",
    "runtime_check",
}


def load_json(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"completion evidence packet must be a JSON object: {path}")
    return payload


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def reference_exists(reference: str) -> bool:
    if reference.startswith("runtime/bin/redcap ") or reference.startswith("python3 "):
        return True
    path = pathlib.Path(reference)
    if path.is_absolute():
        return path.exists()
    return (REPO_ROOT / path).exists()


def validate_packet(packet: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if packet.get("schema_id") != "redcap-completion-evidence-packet":
        failures.append("schema_id must be redcap-completion-evidence-packet")
    if not non_empty_string(packet.get("task_id")):
        failures.append("task_id is required")
    if packet.get("standalone_completion_certificate") is not False:
        failures.append("completion evidence packet must declare standalone_completion_certificate=false")
    evidence = packet.get("evidence")
    if not isinstance(evidence, dict):
        failures.append("evidence must be an object")
        return failures
    missing = sorted(REQUIRED_EVIDENCE_CLASSES - set(evidence))
    if missing:
        failures.append(f"evidence missing classes: {', '.join(missing)}")
    for class_id in sorted(REQUIRED_EVIDENCE_CLASSES):
        entries = evidence.get(class_id)
        if not non_empty_list(entries):
            failures.append(f"evidence.{class_id} must be a non-empty list")
            continue
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                failures.append(f"evidence.{class_id}[{index}] must be an object")
                continue
            reference = entry.get("reference")
            summary = entry.get("summary")
            if not non_empty_string(reference):
                failures.append(f"evidence.{class_id}[{index}].reference is required")
            elif not reference_exists(reference):
                failures.append(f"evidence.{class_id}[{index}].reference does not exist or is not a known command: {reference}")
            if not non_empty_string(summary):
                failures.append(f"evidence.{class_id}[{index}].summary is required")
    ledger_only = set(evidence) <= {"task_fact"}
    if ledger_only:
        failures.append("task fact or ledger evidence alone cannot support a completion judgment")
    lifecycle = packet.get("lifecycle")
    if isinstance(lifecycle, dict):
        for key in ["packet", "prism_resolution"]:
            value = lifecycle.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                failures.append(f"lifecycle.{key} must be a non-empty string when present")
    return failures


def cmd_check(args: argparse.Namespace) -> int:
    packet = load_json(pathlib.Path(args.packet).resolve())
    failures = validate_packet(packet)
    result = {
        "schema_id": "redcap-completion-evidence-check-result",
        "ok": not failures,
        "packet": str(pathlib.Path(args.packet).resolve()),
        "failures": failures,
        "note": "This check is advisory input to lifecycle review, not a standalone completion certificate.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_COMPLETION_EVIDENCE_OK")
    return 0


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def valid_fixture() -> dict[str, Any]:
    return {
        "schema_id": "redcap-completion-evidence-packet",
        "task_id": "completion-evidence-fixture",
        "standalone_completion_certificate": False,
        "evidence": {
            "task_fact": [
                {
                    "reference": "runtime/bin/redcap task-facts summary",
                    "summary": "任务事实只作为索引，不单独证明完成。",
                }
            ],
            "source_logic": [
                {
                    "reference": "runtime/core/completion_evidence.py",
                    "summary": "源码逻辑会检查证据类别是否齐全。",
                }
            ],
            "contract_logic": [
                {
                    "reference": "assets/contracts/process-artifact-placement.json",
                    "summary": "合同或策略文件提供稳定规则来源。",
                }
            ],
            "negative_check": [
                {
                    "reference": "runtime/bin/redcap completion-evidence self-check",
                    "summary": "自检包含账本独证失败、缺少负例失败等场景。",
                }
            ],
            "runtime_check": [
                {
                    "reference": "runtime/bin/redcap completion-evidence check",
                    "summary": "运行命令必须能重复验证证据包。",
                }
            ],
        },
        "lifecycle": {
            "packet": "assets/evidence/lifecycle/placeholder.json",
            "prism_resolution": "assets/evidence/prism/placeholder/resolution.json",
        },
    }


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    valid = valid_fixture()
    valid_failures = validate_packet(valid)
    if valid_failures:
        failures.append(f"valid fixture should pass: {valid_failures}")
    ledger_only = {
        "schema_id": "redcap-completion-evidence-packet",
        "task_id": "ledger-only",
        "standalone_completion_certificate": False,
        "evidence": {
            "task_fact": [
                {
                    "reference": "runtime/bin/redcap task-facts summary",
                    "summary": "账本状态。",
                }
            ],
        },
    }
    ledger_failures = validate_packet(ledger_only)
    if not any("evidence missing classes" in item for item in ledger_failures):
        failures.append(f"ledger-only fixture should fail for missing evidence classes: {ledger_failures}")
    standalone = valid_fixture()
    standalone["standalone_completion_certificate"] = True
    standalone_failures = validate_packet(standalone)
    if not any("standalone_completion_certificate=false" in item for item in standalone_failures):
        failures.append(f"standalone completion certificate should fail: {standalone_failures}")
    missing_reference = valid_fixture()
    missing_reference["evidence"]["source_logic"][0]["reference"] = "runtime/core/not-real.py"
    missing_reference_failures = validate_packet(missing_reference)
    if not any("does not exist" in item for item in missing_reference_failures):
        failures.append(f"missing source reference should fail: {missing_reference_failures}")
    with tempfile.TemporaryDirectory(prefix="redcap-completion-evidence-") as tmp_raw:
        packet_path = pathlib.Path(tmp_raw) / "packet.json"
        write_json(packet_path, valid)
        loaded = load_json(packet_path)
        if validate_packet(loaded):
            failures.append("written valid fixture should load and pass")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_COMPLETION_EVIDENCE_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify completion judgment evidence depth")
    subparsers = parser.add_subparsers(dest="command")
    check = subparsers.add_parser("check")
    check.add_argument("--packet", required=True)
    subparsers.add_parser("self-check")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    command = args.command or "self-check"
    if command == "check":
        return cmd_check(args)
    if command == "self-check":
        return cmd_self_check(args)
    raise SystemExit(f"unknown command: {command}")


if __name__ == "__main__":
    sys.exit(main())

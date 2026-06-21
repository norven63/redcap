#!/usr/bin/env python3
"""Run the residual RSP batch as one integration check."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile
import time
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "assets" / "evidence" / "rsp" / "rsp-09-13-14-17-18-22-batch-integration.json"
PLAN = "assets/docs/residual-todo-final-solution-plan.md"
TAIL_LIMIT = 4000


RSP_CHECKS: tuple[dict[str, Any], ...] = (
    {
        "rsp": "RSP-09",
        "name": "project-install-matrix-check",
        "argv": ["runtime/bin/redcap", "project-install", "matrix-check", "--out", "{out}"],
        "negative": {
            "description": "source workspace pollution must be detected",
            "kind": "check-id-ok",
            "check_id": "negative-source-pollution-detected",
        },
        "claim": "assets/evidence/rsp/rsp-09-claim.json",
        "evidence": "assets/evidence/rsp/rsp-09-project-install-matrix.json",
    },
    {
        "rsp": "RSP-13",
        "name": "e2e-cache-prune-check",
        "argv": ["runtime/bin/redcap", "complete-revival-e2e", "prune-check", "--out", "{out}"],
        "negative": {
            "description": "RedCap source workspace must be rejected as prune root",
            "kind": "field-ok-false-with-failures",
            "field": "source_workspace_negative_probe",
        },
        "claim": "assets/evidence/rsp/rsp-13-claim.json",
        "evidence": "assets/evidence/rsp/rsp-13-e2e-cache-prune.json",
    },
    {
        "rsp": "RSP-14",
        "name": "e2e-human-report-check",
        "argv": ["runtime/bin/redcap", "complete-revival-e2e", "report-check", "--out", "{out}"],
        "negative": {
            "description": "toy page-access-only report must be rejected",
            "kind": "field-ok-false-with-failures",
            "field": "negative_report",
        },
        "claim": "assets/evidence/rsp/rsp-14-claim.json",
        "evidence": "assets/evidence/rsp/rsp-14-e2e-human-report.json",
    },
    {
        "rsp": "RSP-17",
        "name": "design-maturity-matrix-check",
        "argv": ["runtime/bin/redcap", "full-revival-amendment", "maturity-check", "--out", "{out}"],
        "negative": {
            "description": "contract coverage alone must not be accepted as long-term maturity",
            "kind": "acceptance-negative-pass",
        },
        "claim": "assets/evidence/rsp/rsp-17-claim.json",
        "evidence": "assets/evidence/rsp/rsp-17-design-maturity-matrix.json",
    },
    {
        "rsp": "RSP-18",
        "name": "fixture-external-project-samples-check",
        "argv": ["runtime/bin/redcap", "complete-revival-e2e", "external-sample-check", "--out", "{out}"],
        "negative": {
            "description": "target-only sample without RedCap capability evidence must be rejected",
            "kind": "empty-capability-improvement",
            "field": "negative_sample",
        },
        "claim": "assets/evidence/rsp/rsp-18-claim.json",
        "evidence": "assets/evidence/rsp/rsp-18-fixture-external-project-samples.json",
    },
    {
        "rsp": "RSP-22",
        "name": "e2e-contract-mapping-check",
        "argv": ["runtime/bin/redcap", "complete-revival-e2e", "contract-map-check", "--out", "{out}"],
        "negative": {
            "description": "missing E2E contract mapping must be detected",
            "kind": "detected-missing",
            "field": "negative_probe",
        },
        "claim": "assets/evidence/rsp/rsp-22-claim.json",
        "evidence": "assets/evidence/rsp/rsp-22-e2e-contract-mapping.json",
    },
)


REMOVED_RSP18_PATHS = [
    "assets/contracts/external-project-long-samples.json",
    "assets/evidence/rsp/rsp-18-external-project-long-samples.json",
    "assets/evidence/check-receipts/20260621-rsp-09-13-14-17-18-22-residual-batch/rsp-18-external-project-long-samples-check.receipt.json",
    "assets/evidence/check-receipts/20260621-rsp-09-13-14-17-18-22-residual-batch/rsp-contract-rsp-18.receipt.json",
]


def item_by_rsp(rsp_id: str) -> dict[str, Any]:
    for item in RSP_CHECKS:
        if item["rsp"] == rsp_id:
            return item
    raise KeyError(rsp_id)


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return payload


def tail(value: str) -> str:
    if len(value) <= TAIL_LIMIT:
        return value
    return value[-TAIL_LIMIT:]


def run(argv: list[str], *, timeout_seconds: int = 240) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        argv,
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    return {
        "argv": argv,
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "stdout_tail": tail(completed.stdout),
        "stderr_tail": tail(completed.stderr),
    }


def check_id_ok(payload: dict[str, Any], check_id: str) -> bool:
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return False
    for item in checks:
        if isinstance(item, dict) and item.get("id") == check_id:
            return item.get("ok") is True
    return False


def acceptance_negative_pass(payload: dict[str, Any]) -> bool:
    acceptance = payload.get("acceptance")
    if not isinstance(acceptance, dict):
        return False
    negative = acceptance.get("negative")
    return isinstance(negative, dict) and negative.get("status") == "pass"


def field_ok_false_with_failures(payload: dict[str, Any], field: str) -> bool:
    value = payload.get(field)
    return isinstance(value, dict) and value.get("ok") is False and bool(value.get("failures"))


def empty_capability_improvement(payload: dict[str, Any], field: str) -> bool:
    value = payload.get(field)
    return isinstance(value, dict) and value.get("redcap_capability_improvements") == []


def detected_missing(payload: dict[str, Any], field: str) -> bool:
    value = payload.get(field)
    return isinstance(value, dict) and value.get("detected") is True and bool(value.get("missing"))


def mutate_negative_probe_payload(payload: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    mutated = json.loads(json.dumps(payload, ensure_ascii=False))
    kind = spec["kind"]
    if kind == "check-id-ok":
        checks = mutated.get("checks")
        if isinstance(checks, list):
            for item in checks:
                if isinstance(item, dict) and item.get("id") == spec["check_id"]:
                    item["ok"] = False
                    item["mutation_reason"] = "故障注入：污染探针未检测到"
                    break
    elif kind == "field-ok-false-with-failures":
        mutated[spec["field"]] = {
            "ok": True,
            "failures": [],
            "mutation_reason": "故障注入：本应失败的负向样本被错误接受"
        }
    elif kind == "acceptance-negative-pass":
        acceptance = mutated.setdefault("acceptance", {})
        if isinstance(acceptance, dict):
            acceptance["negative"] = {
                "status": "fail",
                "checks": ["故障注入：合同覆盖冒充长期成熟没有被拦住"]
            }
    elif kind == "empty-capability-improvement":
        value = mutated.get(spec["field"])
        if not isinstance(value, dict):
            value = {}
            mutated[spec["field"]] = value
        value["redcap_capability_improvements"] = ["mutated-false-positive"]
    elif kind == "detected-missing":
        mutated[spec["field"]] = {
            "detected": False,
            "missing": [],
            "mutation_reason": "故障注入：缺失映射没有被检测到"
        }
    return mutated


def evaluate_negative_probe(payload: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    kind = spec["kind"]
    if kind == "check-id-ok":
        detected = check_id_ok(payload, spec["check_id"])
    elif kind == "field-ok-false-with-failures":
        detected = field_ok_false_with_failures(payload, spec["field"])
    elif kind == "acceptance-negative-pass":
        detected = acceptance_negative_pass(payload)
    elif kind == "empty-capability-improvement":
        detected = empty_capability_improvement(payload, spec["field"])
    elif kind == "detected-missing":
        detected = detected_missing(payload, spec["field"])
    else:
        detected = False
    return {
        "description": spec["description"],
        "kind": kind,
        "detected": detected,
    }


def report_row_ids(payload: dict[str, Any]) -> set[str]:
    report = payload.get("report")
    if not isinstance(report, dict):
        return set()
    rows = report.get("rows")
    if not isinstance(rows, list):
        return set()
    return {
        str(item.get("id"))
        for item in rows
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id")
    }


def contract_mapping_ids(payload: dict[str, Any]) -> set[str]:
    mapping = payload.get("mapping")
    if not isinstance(mapping, list):
        return set()
    return {
        str(item.get("contract_item_id"))
        for item in mapping
        if isinstance(item, dict) and isinstance(item.get("contract_item_id"), str) and item.get("contract_item_id")
    }


def contract_check(item: dict[str, Any]) -> dict[str, Any]:
    argv = [
        "runtime/bin/redcap",
        "rsp-contract",
        "check",
        "--plan",
        PLAN,
        "--rsp",
        item["rsp"],
        "--claim-file",
        item["claim"],
        "--evidence-file",
        item["evidence"],
    ]
    return run(argv, timeout_seconds=180)


def residual_batch_check(out: pathlib.Path | None = None) -> dict[str, Any]:
    failures: list[str] = []
    steps: list[dict[str, Any]] = []
    negative_probes: list[dict[str, Any]] = []
    contract_checks: list[dict[str, Any]] = []
    payloads: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="redcap-rsp-batch-integration-") as raw_tmp:
        tmp = pathlib.Path(raw_tmp)
        for item in RSP_CHECKS:
            evidence_out = tmp / f"{item['rsp'].lower()}-{item['name']}.json"
            argv = [part.format(out=str(evidence_out)) for part in item["argv"]]
            result = run(argv, timeout_seconds=300)
            step = {
                "rsp": item["rsp"],
                "name": item["name"],
                "evidence_out": str(evidence_out),
                **result,
            }
            steps.append(step)
            if not result["ok"]:
                failures.append(f"{item['rsp']} 集成检查命令失败：{item['name']}")
                continue
            try:
                payload = load_json(evidence_out)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                failures.append(f"{item['rsp']} 集成证据无法读取：{exc}")
                continue
            if payload.get("ok") is not True:
                failures.append(f"{item['rsp']} 集成证据 ok 必须为 true")
            payloads[item["rsp"]] = payload
            probe = {
                "rsp": item["rsp"],
                **evaluate_negative_probe(payload, item["negative"]),
            }
            negative_probes.append(probe)
            if probe["detected"] is not True:
                failures.append(f"{item['rsp']} 负向探针未检测到目标失败：{probe['description']}")

            contract = contract_check(item)
            contract_checks.append({
                "rsp": item["rsp"],
                **contract,
            })
            if contract["ok"] is not True:
                failures.append(f"{item['rsp']} RSP 合同绑定检查失败")

    cross_check_assertions: list[dict[str, Any]] = []
    rsp14_rows = report_row_ids(payloads.get("RSP-14", {}))
    rsp22_mapping = contract_mapping_ids(payloads.get("RSP-22", {}))
    missing_report_mappings = sorted(rsp14_rows - rsp22_mapping)
    cross_check_assertions.append({
        "id": "rsp-14-report-rows-covered-by-rsp-22-contract-mapping",
        "description": "RSP-14 人类报告中的能力项必须被 RSP-22 合同映射覆盖",
        "ok": not missing_report_mappings and bool(rsp14_rows) and bool(rsp22_mapping),
        "report_row_ids": sorted(rsp14_rows),
        "mapping_ids_sample": sorted(rsp22_mapping),
        "missing_report_mappings": missing_report_mappings,
    })
    for assertion in cross_check_assertions:
        if assertion["ok"] is not True:
            failures.append(f"跨检查断言失败：{assertion['id']}")

    removed_path_checks = []
    for raw_path in REMOVED_RSP18_PATHS:
        path = REPO_ROOT / raw_path
        absent = not path.exists()
        removed_path_checks.append({
            "path": raw_path,
            "absent": absent,
        })
        if not absent:
            failures.append(f"废弃 RSP-18 路径仍然存在：{raw_path}")

    result = {
        "schema_id": "redcap-rsp-residual-batch-integration-check",
        "ok": not failures,
        "rsp_items": [item["rsp"] for item in RSP_CHECKS],
        "steps": steps,
        "negative_probes": negative_probes,
        "cross_check_assertions": cross_check_assertions,
        "contract_checks": contract_checks,
        "removed_path_checks": removed_path_checks,
        "failures": failures,
    }
    if out is not None:
        write_json(out, result)
    return result


def residual_batch_mutation_check(out: pathlib.Path | None = None) -> dict[str, Any]:
    failures: list[str] = []
    mutations: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="redcap-rsp-batch-mutation-") as raw_tmp:
        tmp = pathlib.Path(raw_tmp)
        for item in RSP_CHECKS:
            evidence_out = tmp / f"{item['rsp'].lower()}-{item['name']}.json"
            argv = [part.format(out=str(evidence_out)) for part in item["argv"]]
            command_result = run(argv, timeout_seconds=300)
            mutation: dict[str, Any] = {
                "rsp": item["rsp"],
                "name": item["name"],
                "command_ok": command_result["ok"],
                "target_failure": item["negative"]["description"],
            }
            if command_result["ok"] is not True:
                mutation["ok"] = False
                mutation["failure"] = "baseline command failed before mutation"
                failures.append(f"{item['rsp']} mutation baseline command failed")
                mutations.append(mutation)
                continue
            try:
                payload = load_json(evidence_out)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                mutation["ok"] = False
                mutation["failure"] = f"baseline evidence unreadable: {exc}"
                failures.append(f"{item['rsp']} mutation baseline evidence unreadable")
                mutations.append(mutation)
                continue
            baseline = evaluate_negative_probe(payload, item["negative"])
            mutated_payload = mutate_negative_probe_payload(payload, item["negative"])
            mutated_probe = evaluate_negative_probe(mutated_payload, item["negative"])
            mutation.update({
                "baseline_detected": baseline["detected"],
                "mutated_detected": mutated_probe["detected"],
                "ok": baseline["detected"] is True and mutated_probe["detected"] is False,
            })
            if mutation["ok"] is not True:
                failures.append(f"{item['rsp']} 负向探针故障注入没有被 residual-batch 检出")
            mutations.append(mutation)
    result = {
        "schema_id": "redcap-rsp-residual-batch-mutation-check",
        "ok": not failures,
        "mutations": mutations,
        "failures": failures,
    }
    if out is not None:
        write_json(out, result)
    return result


def cmd_check(args: argparse.Namespace) -> int:
    out = pathlib.Path(args.out) if args.out else DEFAULT_OUT
    result = residual_batch_check(out)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if result["ok"]:
        print("REDCAP_RSP_RESIDUAL_BATCH_INTEGRATION_OK")
        return 0
    return 1


def cmd_mutation_check(args: argparse.Namespace) -> int:
    out = pathlib.Path(args.out) if args.out else REPO_ROOT / "assets" / "evidence" / "rsp" / "rsp-09-13-14-17-18-22-batch-mutation.json"
    result = residual_batch_mutation_check(out)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if result["ok"]:
        print("REDCAP_RSP_RESIDUAL_BATCH_MUTATION_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="redcap-rsp-batch-self-check-") as raw_tmp:
        result = residual_batch_check(pathlib.Path(raw_tmp) / "batch.json")
        mutation = residual_batch_mutation_check(pathlib.Path(raw_tmp) / "mutation.json")
    if not result["ok"]:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    if not mutation["ok"]:
        print(json.dumps(mutation, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    if len(result.get("negative_probes", [])) != len(RSP_CHECKS):
        print("residual batch self-check missing negative probes")
        return 1
    print("REDCAP_RSP_RESIDUAL_BATCH_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run residual RSP batch integration checks")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--out")
    check.set_defaults(func=cmd_check)
    mutation_check = sub.add_parser("mutation-check")
    mutation_check.add_argument("--out")
    mutation_check.set_defaults(func=cmd_mutation_check)
    self_check = sub.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

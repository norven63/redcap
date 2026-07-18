#!/usr/bin/env python3
"""Validate the RedCap revival 1.0 loop contract."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = REPO_ROOT / "assets" / "contracts" / "redcap-1.0-loop.json"
from prism_provider_policy import required_providers as policy_required_providers

REQUIRED_TRIAGE = {
    "blocks-this-item",
    "blocks-1.0",
    "valid-observation-recorded",
    "needs-norven-decision",
}

REQUIRED_KERNELS = {
    "runtime-boundary",
    "session-ownership",
    "fsm",
    "hook-adapter",
    "completion-semantics",
    "knowledge-gateway",
    "prism-integration",
}

REQUIRED_PATHOLOGY_SHARDS = {
    "pathology-report-as-progress",
    "pathology-receipt-as-completion",
    "pathology-closeout-recursion",
    "pathology-raw-evidence-default",
}

COMPLETION_STATUSES = {"verified", "done", "completed"}
TERMINAL_NON_COMPLETION_STATUSES = {"no-promote", "out-of-scope"}
CONTRACT_STATUSES = {"active", "completed"}

REPORT_ONLY_MARKERS = {
    "report",
    "reports",
    "task-report",
    "extraction",
    "extractions",
    "prism",
    "review",
    "reviews",
    "ledger",
    "receipt",
    "summary",
    "closeout",
    "close out",
    "close-out",
    "closure",
    "closing",
}

CONSUMPTION_PREFIXES = (
    "runtime/",
    "assets/contracts/",
    "assets/knowledge/",
)


def load_json(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def non_empty_strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def evidence_is_report_only(raw: str) -> bool:
    normalized = raw.strip().lower()
    if normalized.startswith("runtime/bin/redcap "):
        return False
    parts = [part for part in normalized.replace("\\", "/").replace(".", "/").replace("-", "/").split("/") if part]
    return any(part in REPORT_ONLY_MARKERS for part in parts)


def evidence_consumes_extraction(raw: str) -> bool:
    normalized = raw.strip()
    return normalized.startswith(CONSUMPTION_PREFIXES) or normalized.startswith("runtime/bin/redcap ")


def evidence_entry_exists(raw: str) -> bool:
    normalized = raw.strip()
    if normalized.startswith("runtime/bin/redcap "):
        return True
    path = pathlib.Path(normalized)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.exists()


def validate_contract(path: pathlib.Path) -> list[str]:
    failures: list[str] = []
    if not path.is_file():
        return [f"missing loop contract: {path}"]
    try:
        payload = load_json(path)
    except Exception as exc:
        return [f"invalid loop contract JSON: {exc}"]

    if payload.get("schema_id") != "redcap-revival-1-loop":
        failures.append("schema_id must be redcap-revival-1-loop")
    contract_status = payload.get("status")
    if contract_status not in CONTRACT_STATUSES:
        failures.append("status must be active or completed")
    driver = payload.get("driver")
    if not isinstance(driver, dict):
        failures.append("driver must be an object")
    else:
        if driver.get("no_new_cli_command") is not True:
            failures.append("driver.no_new_cli_command must be true")
        if driver.get("command_surface") != "existing-redcap-check-and-lifecycle":
            failures.append("driver.command_surface must use existing redcap check and lifecycle")

    budget = payload.get("cycle_budget")
    if not isinstance(budget, dict):
        failures.append("cycle_budget must be an object")
    else:
        if not isinstance(budget.get("max_cycles_before_human_review"), int) or budget["max_cycles_before_human_review"] > 12:
            failures.append("max_cycles_before_human_review must be an integer <= 12")
        if budget.get("max_consecutive_non_runtime_change_cycles") != 1:
            failures.append("max_consecutive_non_runtime_change_cycles must be 1")
        if not isinstance(budget.get("max_attempts_per_item_before_skip_or_escalate"), int) or budget[
            "max_attempts_per_item_before_skip_or_escalate"
        ] > 2:
            failures.append("max_attempts_per_item_before_skip_or_escalate must be an integer <= 2")
        hard_stop = str(budget.get("hard_stop", "")).lower()
        if "documents" not in hard_stop or "extraction summaries" not in hard_stop or "escalate" not in hard_stop:
            failures.append("cycle_budget.hard_stop must stop document/extraction-only loops")

    prism = payload.get("prism")
    if not isinstance(prism, dict):
        failures.append("prism must be an object")
    else:
        if prism.get("providers") != policy_required_providers(REPO_ROOT):
            failures.append("prism.providers must match the authoritative provider policy")
        triage = prism.get("concern_triage")
        if set(triage or []) != REQUIRED_TRIAGE:
            failures.append("prism.concern_triage must define the required four labels")
        if not non_empty_strings(prism.get("triage_rules")):
            failures.append("prism.triage_rules must be non-empty strings")

    phases = payload.get("cycle_phases")
    if not non_empty_strings(phases):
        failures.append("cycle_phases must be non-empty strings")
    else:
        joined = " ".join(phases).lower()
        for phrase in ["select exactly one", "changed reality", "resolve every concern"]:
            if phrase not in joined:
                failures.append(f"cycle_phases must mention {phrase}")

    queue = payload.get("queue")
    if not isinstance(queue, list) or not queue:
        failures.append("queue must be a non-empty list")
        queue = []
    ids: set[str] = set()
    current_count = 0
    extract_shards: set[str] = set()
    kernels: set[str] = set()
    final_claim_seen = False
    final_claim_status: str | None = None
    nonterminal_non_final_items: list[str] = []
    for index, item in enumerate(queue):
        if not isinstance(item, dict):
            failures.append(f"queue[{index}] must be an object")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            failures.append(f"queue[{index}].id must be non-empty")
        elif item_id in ids:
            failures.append(f"duplicate queue id: {item_id}")
        else:
            ids.add(item_id)
        if item.get("status") == "current":
            current_count += 1
        item_status = item.get("status")
        item_type = item.get("type")
        if item_type == "extract-only":
            failures.append(f"{item_id}: extract-only items are forbidden")
        if item_type == "extract-and-consume":
            shard_id = item.get("shard_id")
            if isinstance(shard_id, str):
                extract_shards.add(shard_id)
            changed = str(item.get("changed_reality", "")).lower()
            if not any(term in changed for term in ["guardrail", "contract rule", "checker", "no-promote"]):
                failures.append(f"{item_id}: extract-and-consume changed_reality must consume extraction")
            forbidden = " ".join(item.get("forbidden_completion_evidence", [])).lower()
            if "extraction json alone" not in forbidden or "summary document alone" not in forbidden:
                failures.append(f"{item_id}: must forbid extraction and summary as completion")
            if item.get("status") in COMPLETION_STATUSES:
                consumption_evidence = item.get("consumption_evidence")
                if not non_empty_strings(consumption_evidence):
                    failures.append(f"{item_id}: verified extract-and-consume items require consumption_evidence")
                else:
                    report_only = [entry for entry in consumption_evidence if evidence_is_report_only(entry)]
                    consuming = [entry for entry in consumption_evidence if evidence_consumes_extraction(entry)]
                    if len(report_only) == len(consumption_evidence):
                        failures.append(
                            f"{item_id}: consumption_evidence cannot be only reports, extractions, Prism reviews, "
                            "ledgers, receipts, summaries, closeouts, or closures"
                        )
                    if not consuming:
                        failures.append(f"{item_id}: consumption_evidence must include runtime, contract, knowledge, or redcap command evidence")
            if item.get("status") in TERMINAL_NON_COMPLETION_STATUSES:
                decision_path = item.get("no_promote_decision") or item.get("out_of_scope_decision")
                if not isinstance(decision_path, str) or not decision_path.strip():
                    failures.append(f"{item_id}: {item.get('status')} extract-and-consume items require a decision path")
                elif not evidence_entry_exists(decision_path):
                    failures.append(f"{item_id}: decision path does not exist: {decision_path}")
                decision_evidence = item.get("decision_evidence")
                if not non_empty_strings(decision_evidence):
                    failures.append(f"{item_id}: {item.get('status')} items require decision_evidence")
                elif not any(evidence_consumes_extraction(entry) for entry in decision_evidence):
                    failures.append(f"{item_id}: decision_evidence must include runtime, contract, knowledge, or redcap command evidence")
        if item_type == "kernel-verification":
            kernel = item.get("kernel")
            if isinstance(kernel, str):
                kernels.add(kernel)
            if not non_empty_strings(item.get("verification")):
                failures.append(f"{item_id}: kernel verification must have executable probes")
        if item_type == "final-claim":
            final_claim_seen = True
            final_claim_status = item_status if isinstance(item_status, str) else None
        elif item_status not in COMPLETION_STATUSES and item_status not in TERMINAL_NON_COMPLETION_STATUSES:
            nonterminal_non_final_items.append(str(item_id))
        if not isinstance(item.get("prism_required"), bool):
            failures.append(f"{item_id}: prism_required must be boolean")
        if not isinstance(item.get("changed_reality"), str) or not item["changed_reality"].strip():
            failures.append(f"{item_id}: changed_reality must be non-empty")

    if contract_status == "active" and current_count != 1:
        failures.append("queue must have exactly one current item")
    if contract_status == "completed":
        if current_count != 0:
            failures.append("completed contract must have zero current items")
        if final_claim_status not in COMPLETION_STATUSES:
            failures.append("completed contract requires redcap-1.0-final-claim in a completion status")
        if nonterminal_non_final_items:
            failures.append(
                "completed contract requires all non-final queue items to be terminal: "
                + ", ".join(nonterminal_non_final_items)
            )
    missing_shards = sorted(REQUIRED_PATHOLOGY_SHARDS - extract_shards)
    if missing_shards:
        failures.append(f"missing pathology extract-and-consume shards: {missing_shards}")
    missing_kernels = sorted(REQUIRED_KERNELS - kernels)
    if missing_kernels:
        failures.append(f"missing kernel verification items: {missing_kernels}")
    if not final_claim_seen:
        failures.append("queue must include a final-claim item")

    exit_criteria = payload.get("exit_criteria")
    if not non_empty_strings(exit_criteria):
        failures.append("exit_criteria must be non-empty strings")
    else:
        joined = " ".join(exit_criteria).lower()
        for phrase in ["end-to-end trace", "seven 1.0 kernel", "temporary-usable-check", "redcap check", "prism concerns"]:
            if phrase not in joined:
                failures.append(f"exit_criteria must mention {phrase}")

    return failures


def cmd_check(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.contract).resolve()
    failures = validate_contract(path)
    print(json.dumps({"ok": not failures, "contract": str(path), "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_REVIVAL_1_LOOP_OK")
    return 0


def cmd_self_check(args: argparse.Namespace) -> int:
    valid_failures = validate_contract(DEFAULT_CONTRACT)
    invalid = load_json(DEFAULT_CONTRACT)
    invalid["queue"] = [
        {
            "id": "bad-extract",
            "status": "current",
            "type": "extract-only",
            "changed_reality": "Writes an extraction only.",
            "prism_required": True,
        }
    ]
    tmp = pathlib.Path(args.tmp_dir) if args.tmp_dir else pathlib.Path("/tmp")
    fixture = tmp / "redcap-revival-loop-invalid.json"
    fixture.write_text(json.dumps(invalid, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    invalid_failures = validate_contract(fixture)
    report_only = load_json(DEFAULT_CONTRACT)
    report_only["queue"] = [
        {
            "id": "bad-report-only-consumption",
            "status": "verified",
            "type": "extract-and-consume",
            "shard_id": "pathology-report-as-progress",
            "changed_reality": "Claims a report pathology extraction was consumed into a guardrail.",
            "forbidden_completion_evidence": [
                "extraction JSON alone",
                "summary document alone",
            ],
            "consumption_evidence": [
                "assets/archaeology/extractions/pathology-report-as-progress-v1.json",
                "assets/docs/task-reports/report.md",
                "assets/evidence/prism/review.json",
            ],
            "prism_required": True,
        },
        {
            "id": "kernel-runtime-boundary-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "runtime-boundary",
            "changed_reality": "Runtime boundary kernel has an executable probe and passes it.",
            "verification": ["runtime/bin/redcap boundary check"],
            "prism_required": False,
        },
        {
            "id": "kernel-session-ownership-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "session-ownership",
            "changed_reality": "Session ownership kernel has an executable probe and passes it.",
            "verification": ["runtime/bin/redcap session-ownership self-check"],
            "prism_required": False,
        },
        {
            "id": "kernel-fsm-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "fsm",
            "changed_reality": "Minimal FSM kernel has executable transition probes and passes them.",
            "verification": ["runtime/bin/redcap fsm check"],
            "prism_required": False,
        },
        {
            "id": "kernel-hook-adapter-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "hook-adapter",
            "changed_reality": "Codex hook adapter contract has probes and passes them.",
            "verification": ["runtime/bin/redcap host-hook-audit"],
            "prism_required": False,
        },
        {
            "id": "kernel-completion-semantics-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "completion-semantics",
            "changed_reality": "Completion semantics guard rejects proof-only claims.",
            "verification": ["runtime/bin/redcap final-claim self-check"],
            "prism_required": False,
        },
        {
            "id": "kernel-knowledge-gateway-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "knowledge-gateway",
            "changed_reality": "Knowledge gateway probes pass.",
            "verification": ["runtime/bin/redcap knowledge-gateway check"],
            "prism_required": False,
        },
        {
            "id": "kernel-prism-integration-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "prism-integration",
            "changed_reality": "Prism integration probes pass.",
            "verification": ["runtime/prism/bin/prism check"],
            "prism_required": False,
        },
        {
            "id": "redcap-1.0-final-claim",
            "status": "pending",
            "type": "final-claim",
            "changed_reality": "All 1.0 exit criteria are proven.",
            "verification": ["runtime/bin/redcap check"],
            "prism_required": True,
        },
    ]
    report_only_fixture = tmp / "redcap-revival-loop-report-only.json"
    report_only_fixture.write_text(json.dumps(report_only, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_only_failures = validate_contract(report_only_fixture)
    receipt_only = load_json(DEFAULT_CONTRACT)
    receipt_only["queue"] = [
        {
            "id": "bad-receipt-only-consumption",
            "status": "verified",
            "type": "extract-and-consume",
            "shard_id": "pathology-receipt-as-completion",
            "changed_reality": "Claims receipt pathology was consumed into a guardrail.",
            "forbidden_completion_evidence": [
                "extraction JSON alone",
                "summary document alone",
            ],
            "consumption_evidence": [
                "assets/evidence/receipts/receipt.json",
            ],
            "prism_required": True,
        },
        {
            "id": "kernel-runtime-boundary-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "runtime-boundary",
            "changed_reality": "Runtime boundary kernel has an executable probe and passes it.",
            "verification": ["runtime/bin/redcap boundary check"],
            "prism_required": False,
        },
        {
            "id": "kernel-session-ownership-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "session-ownership",
            "changed_reality": "Session ownership kernel has an executable probe and passes it.",
            "verification": ["runtime/bin/redcap session-ownership self-check"],
            "prism_required": False,
        },
        {
            "id": "kernel-fsm-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "fsm",
            "changed_reality": "Minimal FSM kernel has executable transition probes and passes them.",
            "verification": ["runtime/bin/redcap fsm check"],
            "prism_required": False,
        },
        {
            "id": "kernel-hook-adapter-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "hook-adapter",
            "changed_reality": "Codex hook adapter contract has probes and passes them.",
            "verification": ["runtime/bin/redcap host-hook-audit"],
            "prism_required": False,
        },
        {
            "id": "kernel-completion-semantics-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "completion-semantics",
            "changed_reality": "Completion semantics guard rejects proof-only claims.",
            "verification": ["runtime/bin/redcap final-claim self-check"],
            "prism_required": False,
        },
        {
            "id": "kernel-knowledge-gateway-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "knowledge-gateway",
            "changed_reality": "Knowledge gateway probes pass.",
            "verification": ["runtime/bin/redcap knowledge-gateway check"],
            "prism_required": False,
        },
        {
            "id": "kernel-prism-integration-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "prism-integration",
            "changed_reality": "Prism integration probes pass.",
            "verification": ["runtime/prism/bin/prism check"],
            "prism_required": False,
        },
        {
            "id": "redcap-1.0-final-claim",
            "status": "pending",
            "type": "final-claim",
            "changed_reality": "All 1.0 exit criteria are proven.",
            "verification": ["runtime/bin/redcap check"],
            "prism_required": True,
        },
    ]
    receipt_only_fixture = tmp / "redcap-revival-loop-receipt-only.json"
    receipt_only_fixture.write_text(json.dumps(receipt_only, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipt_only_failures = validate_contract(receipt_only_fixture)
    closeout_only = load_json(DEFAULT_CONTRACT)
    closeout_only["queue"] = [
        {
            "id": "bad-closeout-only-consumption",
            "status": "verified",
            "type": "extract-and-consume",
            "shard_id": "pathology-closeout-recursion",
            "changed_reality": "Claims closeout pathology was consumed into a guardrail.",
            "forbidden_completion_evidence": [
                "extraction JSON alone",
                "summary document alone",
            ],
            "consumption_evidence": [
                "assets/evidence/closeout-runtime/closeout-summary.md",
                "assets/evidence/pending-closure/state.json",
                "assets/evidence/closure-ledger/closure.log",
            ],
            "prism_required": True,
        },
        {
            "id": "kernel-runtime-boundary-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "runtime-boundary",
            "changed_reality": "Runtime boundary kernel has an executable probe and passes it.",
            "verification": ["runtime/bin/redcap boundary check"],
            "prism_required": False,
        },
        {
            "id": "kernel-session-ownership-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "session-ownership",
            "changed_reality": "Session ownership kernel has an executable probe and passes it.",
            "verification": ["runtime/bin/redcap session-ownership self-check"],
            "prism_required": False,
        },
        {
            "id": "kernel-fsm-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "fsm",
            "changed_reality": "Minimal FSM kernel has executable transition probes and passes them.",
            "verification": ["runtime/bin/redcap fsm check"],
            "prism_required": False,
        },
        {
            "id": "kernel-hook-adapter-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "hook-adapter",
            "changed_reality": "Codex hook adapter contract has probes and passes them.",
            "verification": ["runtime/bin/redcap host-hook-audit"],
            "prism_required": False,
        },
        {
            "id": "kernel-completion-semantics-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "completion-semantics",
            "changed_reality": "Completion semantics guard rejects proof-only claims.",
            "verification": ["runtime/bin/redcap final-claim self-check"],
            "prism_required": False,
        },
        {
            "id": "kernel-knowledge-gateway-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "knowledge-gateway",
            "changed_reality": "Knowledge gateway probes pass.",
            "verification": ["runtime/bin/redcap knowledge-gateway check"],
            "prism_required": False,
        },
        {
            "id": "kernel-prism-integration-verified",
            "status": "pending",
            "type": "kernel-verification",
            "kernel": "prism-integration",
            "changed_reality": "Prism integration probes pass.",
            "verification": ["runtime/prism/bin/prism check"],
            "prism_required": False,
        },
        {
            "id": "redcap-1.0-final-claim",
            "status": "pending",
            "type": "final-claim",
            "changed_reality": "All 1.0 exit criteria are proven.",
            "verification": ["runtime/bin/redcap check"],
            "prism_required": True,
        },
    ]
    closeout_only_fixture = tmp / "redcap-revival-loop-closeout-only.json"
    closeout_only_fixture.write_text(json.dumps(closeout_only, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    closeout_only_failures = validate_contract(closeout_only_fixture)
    no_promote_without_decision = load_json(DEFAULT_CONTRACT)
    no_promote_without_decision["queue"][1]["status"] = "no-promote"
    no_promote_without_decision["queue"][1].pop("no_promote_decision", None)
    no_promote_without_decision["queue"][1].pop("decision_evidence", None)
    no_promote_fixture = tmp / "redcap-revival-loop-no-promote-missing-evidence.json"
    no_promote_fixture.write_text(json.dumps(no_promote_without_decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    no_promote_failures = validate_contract(no_promote_fixture)

    completed_valid = load_json(DEFAULT_CONTRACT)
    completed_valid["status"] = "completed"
    for item in completed_valid["queue"]:
        if item.get("id") == "redcap-1.0-final-claim":
            item["status"] = "verified"
    completed_valid_fixture = tmp / "redcap-revival-loop-completed-valid.json"
    completed_valid_fixture.write_text(json.dumps(completed_valid, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    completed_valid_failures = validate_contract(completed_valid_fixture)

    completed_with_current = load_json(completed_valid_fixture)
    for item in completed_with_current["queue"]:
        if item.get("id") == "kernel-fsm-verified":
            item["status"] = "current"
            break
    completed_with_current_fixture = tmp / "redcap-revival-loop-completed-with-current.json"
    completed_with_current_fixture.write_text(json.dumps(completed_with_current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    completed_with_current_failures = validate_contract(completed_with_current_fixture)

    completed_pending_final = load_json(completed_valid_fixture)
    for item in completed_pending_final["queue"]:
        if item.get("id") == "redcap-1.0-final-claim":
            item["status"] = "pending"
            break
    completed_pending_final_fixture = tmp / "redcap-revival-loop-completed-pending-final.json"
    completed_pending_final_fixture.write_text(json.dumps(completed_pending_final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    completed_pending_final_failures = validate_contract(completed_pending_final_fixture)

    failures: list[str] = []
    if valid_failures:
        failures.append(f"valid contract failed: {valid_failures}")
    if not any("extract-only items are forbidden" in item for item in invalid_failures):
        failures.append("invalid extract-only fixture did not fail")
    if not any("consumption_evidence cannot be only reports" in item for item in report_only_failures):
        failures.append("report/extraction/prism-only consumption fixture did not fail")
    if not any("receipts" in item for item in receipt_only_failures):
        failures.append("receipt-only consumption fixture did not fail with receipt-specific message")
    if not any("closeouts" in item or "closures" in item for item in closeout_only_failures):
        failures.append("closeout-only consumption fixture did not fail with closeout-specific message")
    if not any("no-promote extract-and-consume items require a decision path" in item for item in no_promote_failures):
        failures.append("no-promote without decision fixture did not fail")
    if completed_valid_failures:
        failures.append(f"valid completed contract failed: {completed_valid_failures}")
    if not any("current" in item or "terminal" in item for item in completed_with_current_failures):
        failures.append("completed contract with current item fixture did not fail")
    if not any("final-claim" in item or "completion" in item for item in completed_pending_final_failures):
        failures.append("completed contract with pending final-claim fixture did not fail")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_REVIVAL_1_LOOP_SELF_CHECK_OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap revival 1.0 loop contract")
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check")
    check.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    check.set_defaults(func=cmd_check)
    self_check = sub.add_parser("self-check")
    self_check.add_argument("--tmp-dir")
    self_check.set_defaults(func=cmd_self_check)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

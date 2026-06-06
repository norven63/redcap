#!/usr/bin/env python3
"""Validate the RedCap 1.1 Phase 2 blueprint contract."""

from __future__ import annotations

import argparse
import copy
import json
import os
import pathlib
import shlex
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
AUTHORITATIVE_CONTRACT = REPO_ROOT / "assets" / "contracts" / "redcap-1.1-phase2-blueprint.json"
EXPECTED_SCHEMA_ID = "redcap-1.1-phase2-blueprint-contract"
ACTIVE_STATUS = "active"
DRAFT_STATUS = "draft_for_prism_review_only"
OLD_REDCAP_ROOT = "/Users/norven/workspace/redcap"
REQUIRED_GUARANTEE_REFS = {"G04", "G05", "G06", "G07", "G08", "G09"}
PROOF_ONLY_MARKERS = {
    "doc",
    "document",
    "report",
    "review",
    "ledger",
    "receipt",
    "summary",
    "closeout",
    "closure",
}
REALITY_EVIDENCE_MARKERS = {
    "runtime/bin/redcap",
    "runtime/core/",
    "assets/contracts/",
    "assets/knowledge/",
    "assets/archaeology/extractions/",
    "assets/archaeology/no-promote/",
}


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"contract not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid contract json: {path}: {exc}") from exc


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(is_nonempty_string(item) for item in value)


def object_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, dict) for item in value)


def rel_or_raw(path: pathlib.Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_reference(raw: str, base_dir: pathlib.Path) -> pathlib.Path:
    path = pathlib.Path(raw)
    if path.is_absolute():
        return path
    first = (base_dir / path).resolve()
    if first.exists():
        return first
    return (REPO_ROOT / path).resolve()


def looks_like_directory_source(raw: str) -> bool:
    if not raw.startswith(OLD_REDCAP_ROOT + "/"):
        return True
    if any(token in raw for token in ["*", "?", "[", "]"]):
        return True
    if raw.endswith("/"):
        return True
    name = pathlib.PurePosixPath(raw).name
    if not name or name in {"redcap", "assets", "runtime", "compass", "tools", "references", "knowledge"}:
        return True
    return False


def source_violates_disabled_limits(raw: str, limits: dict[str, Any]) -> str | None:
    lowered = raw.casefold()
    if limits.get("private_archives_allowed") is False:
        private_markers = ["/archives/", "/archive/", "/receipts/", "/private/", "/task-bodies/", "/task_bodies/"]
        if any(marker in lowered for marker in private_markers):
            return "private archive or task-body source is disabled by source_limits"
    if limits.get("raw_prism_runs_allowed_by_default") is False:
        raw_markers = ["/prism/runs/", "/raw-prism-runs/", "/raw_evidence/", "/raw-evidence/", "/evidence/archive/"]
        if any(marker in lowered for marker in raw_markers):
            return "raw Prism run or raw evidence source is disabled by source_limits"
    return None


def source_file_failure(raw: str) -> str | None:
    old_root = pathlib.Path(OLD_REDCAP_ROOT)
    if not old_root.exists():
        return None
    path = pathlib.Path(raw)
    if not path.exists():
        return "old source does not exist"
    if not path.is_file():
        return "old source is not a file"
    if not os.access(path, os.R_OK):
        return "old source is not readable"
    return None


def route_points_to_existing_local_target(route: str) -> bool:
    try:
        parts = shlex.split(route)
    except ValueError:
        return False
    if not parts:
        return False
    first = parts[0]
    if first.startswith("runtime/") or first.startswith("assets/"):
        return (REPO_ROOT / first).exists()
    if first in {"python3", "python"} and len(parts) > 1 and (parts[1].startswith("runtime/") or parts[1].startswith("assets/")):
        return (REPO_ROOT / parts[1]).exists()
    return True


def has_reality_evidence(values: list[str]) -> bool:
    lowered_values = [value.casefold() for value in values]
    if any(any(marker in value for marker in REALITY_EVIDENCE_MARKERS) for value in lowered_values):
        return True
    return any(not any(marker in value for marker in PROOF_ONLY_MARKERS) for value in lowered_values)


def validate_activation_boundary(contract: dict[str, Any], path: pathlib.Path, allow_draft: bool, failures: list[str]) -> None:
    status = contract.get("status")
    if path.resolve() == AUTHORITATIVE_CONTRACT.resolve():
        if status != ACTIVE_STATUS:
            failures.append("authoritative contract must have status active")
    elif status == ACTIVE_STATUS:
        failures.append("non-authoritative contract path cannot have status active")
    elif status == DRAFT_STATUS and not allow_draft:
        failures.append("draft contract requires --allow-draft")
    elif status != DRAFT_STATUS:
        failures.append(f"contract status invalid: {status}")

    boundary = contract.get("activation_boundary")
    if not isinstance(boundary, dict):
        failures.append("activation_boundary must be an object")
        return
    for key in ["authoritative_path_when_accepted", "not_authoritative_until", "forbidden_uses"]:
        if key not in boundary:
            failures.append(f"activation_boundary missing {key}")
    if boundary.get("authoritative_path_when_accepted") != "assets/contracts/redcap-1.1-phase2-blueprint.json":
        failures.append("activation_boundary must name the authoritative contract path")
    for key in ["not_authoritative_until", "forbidden_uses"]:
        if key in boundary and not string_list(boundary[key]):
            failures.append(f"activation_boundary.{key} must be a non-empty string list")


def validate_taxonomies(contract: dict[str, Any], failures: list[str]) -> tuple[set[str], set[str], set[str], set[str], set[str]]:
    taxonomy = contract.get("classification_taxonomy")
    destinations = contract.get("destination_boundaries")
    queue_shape = contract.get("queue_entry_shape")
    idea_shape = contract.get("idea_record_shape")
    if not isinstance(taxonomy, dict):
        failures.append("classification_taxonomy must be an object")
        allowed_classes: set[str] = set()
    else:
        allowed_classes = set(taxonomy.get("allowed_values") or [])
        required = {"keep", "redesign", "discard", "pathology", "no_promote"}
        if not required.issubset(allowed_classes):
            failures.append(f"classification_taxonomy.allowed_values missing: {sorted(required - allowed_classes)}")
    if not isinstance(destinations, dict):
        failures.append("destination_boundaries must be an object")
        allowed_destinations: set[str] = set()
    else:
        allowed_destinations = set(destinations.get("allowed_values") or [])
        if "no_destination" not in allowed_destinations:
            failures.append("destination_boundaries.allowed_values must include no_destination")
    if not isinstance(queue_shape, dict):
        failures.append("queue_entry_shape must be an object")
        allowed_status: set[str] = set()
        queue_required: set[str] = set()
    else:
        allowed_status = set(queue_shape.get("allowed_status") or [])
        queue_required = set(queue_shape.get("required_fields") or [])
        minimum = {
            "id",
            "phase",
            "question",
            "exact_old_sources",
            "stop_condition",
            "acceptance_criteria",
            "risk_level",
            "requires_prism",
            "expected_output",
            "status",
        }
        if not minimum.issubset(queue_required):
            failures.append(f"queue_entry_shape.required_fields missing: {sorted(minimum - queue_required)}")
    if not isinstance(idea_shape, dict):
        failures.append("idea_record_shape must be an object")
        actions: set[str] = set()
        hooks: set[str] = set()
    else:
        actions = set(idea_shape.get("migration_action_values") or [])
        hooks = set(idea_shape.get("hook_or_gate_values") or [])
        for required in ["redesign", "record_no_promote", "defer"]:
            if required not in actions:
                failures.append(f"idea_record_shape.migration_action_values missing {required}")
        for required in ["deterministic_gate", "lifecycle_validator", "final_claim_guard"]:
            if required not in hooks:
                failures.append(f"idea_record_shape.hook_or_gate_values missing {required}")
    return allowed_classes, allowed_destinations, allowed_status, actions, hooks


def validate_authority_inheritance(contract: dict[str, Any], base_dir: pathlib.Path, failures: list[str]) -> None:
    inheritance = contract.get("authority_inheritance")
    if not isinstance(inheritance, dict):
        failures.append("authority_inheritance must be an object")
        return
    for key in ["source_contract", "binding_rule", "reopen_rule", "non_override_rule", "handoff_records"]:
        if key not in inheritance:
            failures.append(f"authority_inheritance missing {key}")
    for key in ["binding_rule", "reopen_rule", "non_override_rule"]:
        if key in inheritance and not is_nonempty_string(inheritance[key]):
            failures.append(f"authority_inheritance.{key} must be a non-empty string")
    source_contract = inheritance.get("source_contract")
    if isinstance(source_contract, str):
        if not resolve_reference(source_contract, base_dir).exists():
            failures.append(f"authority_inheritance.source_contract does not exist: {source_contract}")
    if not string_list(inheritance.get("handoff_records")):
        failures.append("authority_inheritance.handoff_records must be a non-empty string list")
    else:
        for raw in inheritance["handoff_records"]:
            if not resolve_reference(raw, base_dir).exists():
                failures.append(f"authority handoff record does not exist: {raw}")


def validate_queue_amendment_protocol(contract: dict[str, Any], failures: list[str]) -> None:
    protocol = contract.get("queue_amendment_protocol")
    if not isinstance(protocol, dict):
        failures.append("queue_amendment_protocol must be an object")
        return
    for key in ["allowed_actors", "required_steps", "fresh_prism_required_when", "forbidden_amendments"]:
        if not string_list(protocol.get(key)):
            failures.append(f"queue_amendment_protocol.{key} must be a non-empty string list")
    joined_steps = "\n".join(protocol.get("required_steps") or []).casefold()
    joined_fresh = "\n".join(protocol.get("fresh_prism_required_when") or []).casefold()
    joined_forbidden = "\n".join(protocol.get("forbidden_amendments") or []).casefold()
    for fragment in ["gate", "exact old source", "stop condition", "redcap check"]:
        if fragment not in joined_steps:
            failures.append(f"queue_amendment_protocol.required_steps missing fragment: {fragment}")
    if "prism" not in joined_steps + joined_fresh:
        failures.append("queue_amendment_protocol must require Prism for risky amendments")
    if "bulk-read" not in joined_forbidden and "bulk read" not in joined_forbidden:
        failures.append("queue_amendment_protocol.forbidden_amendments must forbid bulk reads")


def validate_queue(
    contract: dict[str, Any],
    allowed_status: set[str],
    failures: list[str],
) -> set[str]:
    queue = contract.get("initial_queue")
    if not object_list(queue):
        failures.append("initial_queue must be a non-empty object list")
        return set()
    queue_ids: set[str] = set()
    queued_count = 0
    verified_count = 0
    max_files = 7
    limits: dict[str, Any] = {}
    shape = contract.get("queue_entry_shape")
    if isinstance(shape, dict):
        limits = shape.get("source_limits")
        if isinstance(limits, dict) and isinstance(limits.get("default_max_files_per_shard"), int):
            max_files = limits["default_max_files_per_shard"]
        if not isinstance(limits, dict):
            limits = {}
    for index, item in enumerate(queue):
        prefix = f"initial_queue[{index}]"
        item_id = item.get("id")
        if not is_nonempty_string(item_id):
            failures.append(f"{prefix}.id must be a non-empty string")
            continue
        if item_id in queue_ids:
            failures.append(f"duplicate queue id: {item_id}")
        queue_ids.add(item_id)
        if item.get("status") == "queued":
            queued_count += 1
        if item.get("status") == "verified":
            verified_count += 1
        if item.get("status") not in allowed_status:
            failures.append(f"{prefix}.status invalid: {item.get('status')}")
        if item.get("status") == "no_promote":
            failures.append(f"{prefix} must not contain no_promote status; use prior_decisions")
        if not string_list(item.get("exact_old_sources")):
            failures.append(f"{prefix}.exact_old_sources must be a non-empty string list")
        else:
            if len(item["exact_old_sources"]) > max_files:
                failures.append(f"{prefix}.exact_old_sources exceeds default max files")
            for raw in item["exact_old_sources"]:
                if looks_like_directory_source(raw):
                    failures.append(f"{prefix}.exact_old_sources contains non-exact or out-of-bound source: {raw}")
                limit_failure = source_violates_disabled_limits(raw, limits)
                if limit_failure:
                    failures.append(f"{prefix}.exact_old_sources violates source_limits: {raw}: {limit_failure}")
                file_failure = source_file_failure(raw)
                if file_failure:
                    failures.append(f"{prefix}.exact_old_sources invalid: {raw}: {file_failure}")
        for key in ["question", "stop_condition", "expected_output", "risk_level"]:
            if not is_nonempty_string(item.get(key)):
                failures.append(f"{prefix}.{key} must be a non-empty string")
        if not string_list(item.get("acceptance_criteria")):
            failures.append(f"{prefix}.acceptance_criteria must be a non-empty string list")
        if item.get("requires_prism") is not True:
            failures.append(f"{prefix}.requires_prism must be true")
        if item.get("status") == "verified":
            evidence = item.get("verification_evidence")
            if not string_list(evidence):
                failures.append(f"{prefix}.verification_evidence is required when status is verified")
            elif not has_reality_evidence(evidence):
                failures.append(f"{prefix}.verification_evidence cannot be proof-only")
    if queued_count < 1 and verified_count < 1:
        failures.append("initial_queue must include at least one queued or verified extraction item")
    return queue_ids


def validate_prior_decisions(contract: dict[str, Any], queue_ids: set[str], base_dir: pathlib.Path, failures: list[str]) -> set[str]:
    decisions = contract.get("prior_decisions")
    if not object_list(decisions):
        failures.append("prior_decisions must be a non-empty object list")
        return set()
    decision_ids: set[str] = set()
    required = {
        "pathology-report-as-progress",
        "pathology-receipt-as-completion",
        "pathology-closeout-recursion",
        "pathology-raw-evidence-default",
    }
    for index, item in enumerate(decisions):
        prefix = f"prior_decisions[{index}]"
        item_id = item.get("id")
        if not is_nonempty_string(item_id):
            failures.append(f"{prefix}.id must be a non-empty string")
            continue
        if item_id in queue_ids:
            failures.append(f"{prefix}.id overlaps with initial_queue: {item_id}")
        decision_ids.add(item_id)
        if item.get("decision") != "no_promote":
            failures.append(f"{prefix}.decision must be no_promote")
        for key in ["source", "binding_effect", "reopen_requires"]:
            if not is_nonempty_string(item.get(key)):
                failures.append(f"{prefix}.{key} must be a non-empty string")
        source = item.get("source")
        if isinstance(source, str) and not resolve_reference(source, base_dir).exists():
            failures.append(f"{prefix}.source does not exist: {source}")
    missing = sorted(required - decision_ids)
    if missing:
        failures.append(f"prior_decisions missing required 1.0 no-promote decisions: {missing}")
    return decision_ids


def validate_idea_records(
    contract: dict[str, Any],
    queue_ids: set[str],
    decision_ids: set[str],
    allowed_classes: set[str],
    allowed_destinations: set[str],
    actions: set[str],
    hooks: set[str],
    failures: list[str],
) -> None:
    records = contract.get("initial_idea_records")
    if not object_list(records):
        failures.append("initial_idea_records must be a non-empty object list")
        return
    seen: set[str] = set()
    has_redesign = False
    has_pathology_or_no_promote = False
    guarantee_refs: set[str] = set()
    allowed_shards = queue_ids | decision_ids
    for index, item in enumerate(records):
        prefix = f"initial_idea_records[{index}]"
        item_id = item.get("id")
        if not is_nonempty_string(item_id):
            failures.append(f"{prefix}.id must be a non-empty string")
            continue
        if item_id in seen:
            failures.append(f"duplicate idea record id: {item_id}")
        seen.add(item_id)
        source_shard = item.get("source_shard")
        if source_shard not in allowed_shards:
            failures.append(f"{prefix}.source_shard does not reference a queue or prior decision id: {source_shard}")
        classification = item.get("classification")
        if classification not in allowed_classes:
            failures.append(f"{prefix}.classification invalid: {classification}")
        if classification == "redesign":
            has_redesign = True
        if classification in {"pathology", "no_promote"}:
            has_pathology_or_no_promote = True
        if item.get("destination_boundary") not in allowed_destinations:
            failures.append(f"{prefix}.destination_boundary invalid: {item.get('destination_boundary')}")
        if item.get("migration_action") not in actions:
            failures.append(f"{prefix}.migration_action invalid: {item.get('migration_action')}")
        if item.get("hook_or_gate_assessment") not in hooks:
            failures.append(f"{prefix}.hook_or_gate_assessment invalid: {item.get('hook_or_gate_assessment')}")
        for key in ["summary"]:
            if not is_nonempty_string(item.get(key)):
                failures.append(f"{prefix}.{key} must be a non-empty string")
        if not string_list(item.get("source_refs")):
            failures.append(f"{prefix}.source_refs must be a non-empty string list")
        else:
            for raw_ref in item["source_refs"]:
                for guarantee in REQUIRED_GUARANTEE_REFS:
                    if f"#{guarantee}" in raw_ref:
                        guarantee_refs.add(guarantee)
        if classification in {"keep", "redesign"} and not string_list(item.get("verification_route")):
            failures.append(f"{prefix}.verification_route is required for keep/redesign")
        elif string_list(item.get("verification_route")):
            for route in item["verification_route"]:
                if not route_points_to_existing_local_target(route):
                    failures.append(f"{prefix}.verification_route target does not exist: {route}")
        if classification in {"pathology", "no_promote", "discard"} and item.get("hook_or_gate_assessment") == "no_hook_needed":
            failures.append(f"{prefix}.hook_or_gate_assessment cannot be no_hook_needed for pathology/no_promote/discard")
    if not has_redesign:
        failures.append("initial_idea_records must include at least one redesign example")
    if not has_pathology_or_no_promote:
        failures.append("initial_idea_records must include at least one pathology or no_promote example")
    missing_guarantees = sorted(REQUIRED_GUARANTEE_REFS - guarantee_refs)
    if missing_guarantees:
        failures.append(f"initial_idea_records missing G04-G09 coverage: {missing_guarantees}")


def validate_required_checker(contract: dict[str, Any], failures: list[str]) -> None:
    checker = contract.get("required_checker")
    if not isinstance(checker, dict):
        failures.append("required_checker must be an object")
        return
    if checker.get("proposed_command") != "runtime/bin/redcap phase2-blueprint check --contract assets/contracts/redcap-1.1-phase2-blueprint.json":
        failures.append("required_checker.proposed_command must name the phase2-blueprint check command")
    assertions = checker.get("minimum_assertions")
    if not string_list(assertions):
        failures.append("required_checker.minimum_assertions must be a non-empty string list")
        return
    required_fragments = [
        "all queue entries contain exact_old_sources",
        "all idea records use constrained classification",
        "runtime/bin/redcap check delegates or includes this checker",
    ]
    for fragment in required_fragments:
        if not any(fragment in item for item in assertions):
            failures.append(f"required_checker.minimum_assertions missing fragment: {fragment}")


def validate_exit_criteria(contract: dict[str, Any], failures: list[str]) -> None:
    criteria = contract.get("phase2_exit_criteria")
    if not string_list(criteria):
        failures.append("phase2_exit_criteria must be a non-empty string list")
        return
    joined = "\n".join(criteria).casefold()
    for fragment in [
        "authoritative contract exists",
        "checker exists",
        "reaches verified",
        "no concrete old module migration",
    ]:
        if fragment not in joined:
            failures.append(f"phase2_exit_criteria missing fragment: {fragment}")
    if "currently queued" not in joined and "queue item" not in joined:
        failures.append("phase2_exit_criteria must describe which queue item reaches verified")


def validate_contract(contract: dict[str, Any], path: pathlib.Path, allow_draft: bool) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != EXPECTED_SCHEMA_ID:
        failures.append(f"schema_id must be {EXPECTED_SCHEMA_ID}")
    if not isinstance(contract.get("version"), int) or contract["version"] < 1:
        failures.append("version must be a positive integer")
    for key in ["purpose", "human_intervention_rules"]:
        if key == "purpose" and not is_nonempty_string(contract.get(key)):
            failures.append("purpose must be a non-empty string")
        if key == "human_intervention_rules" and not string_list(contract.get(key)):
            failures.append("human_intervention_rules must be a non-empty string list")

    base_dir = path.parent
    validate_activation_boundary(contract, path, allow_draft, failures)
    validate_authority_inheritance(contract, base_dir, failures)
    validate_queue_amendment_protocol(contract, failures)
    allowed_classes, allowed_destinations, allowed_status, actions, hooks = validate_taxonomies(contract, failures)
    queue_ids = validate_queue(contract, allowed_status, failures)
    decision_ids = validate_prior_decisions(contract, queue_ids, base_dir, failures)
    validate_idea_records(contract, queue_ids, decision_ids, allowed_classes, allowed_destinations, actions, hooks, failures)
    validate_required_checker(contract, failures)
    validate_exit_criteria(contract, failures)
    return failures


def command_check(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.contract).resolve() if args.contract else AUTHORITATIVE_CONTRACT
    if not args.contract and not path.exists():
        payload = {
            "ok": True,
            "authoritative_contract_present": False,
            "contract": rel_or_raw(path),
            "note": "Phase 2 blueprint contract is not active yet.",
            "failures": [],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("REDCAP_PHASE2_BLUEPRINT_OK")
        return 0
    contract = load_json(path)
    if not isinstance(contract, dict):
        raise SystemExit("contract must be a JSON object")
    failures = validate_contract(contract, path, args.allow_draft)
    payload = {
        "ok": not failures,
        "contract": rel_or_raw(path),
        "allow_draft": bool(args.allow_draft),
        "failures": failures,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_PHASE2_BLUEPRINT_OK")
    return 0


def self_check_fixture() -> dict[str, Any]:
    return {
        "schema_id": EXPECTED_SCHEMA_ID,
        "version": 1,
        "status": DRAFT_STATUS,
        "activation_boundary": {
            "authoritative_path_when_accepted": "assets/contracts/redcap-1.1-phase2-blueprint.json",
            "not_authoritative_until": [
                "Prism reviews this proposed-contract.json, not only the request summary",
                "Cap decides on Prism concerns with accept, reject-with-bounded-followup, or escalate",
                "A contract-specific checker exists and accepts the authoritative contract",
                "runtime/bin/redcap check includes or delegates that checker",
            ],
            "forbidden_uses": [
                "claim Phase 2 governance exists",
                "bulk-read the old RedCap repository",
            ],
        },
        "purpose": "Fixture for Phase 2 blueprint checker.",
        "authority_inheritance": {
            "source_contract": "assets/contracts/redcap-1.0-loop.json",
            "binding_rule": "1.0 decisions are binding.",
            "reopen_rule": "Reopen only with bounded evidence.",
            "non_override_rule": "Phase 2 does not override 1.0.",
            "handoff_records": [
                "assets/contracts/redcap-1.0-loop.json",
                "assets/archaeology/no-promote/pathology-report-as-progress-v1.json",
                "assets/archaeology/no-promote/pathology-receipt-as-completion-v1.json",
                "assets/archaeology/no-promote/pathology-closeout-recursion-v1.json",
                "assets/archaeology/no-promote/pathology-raw-evidence-default-v1.json",
            ],
        },
        "classification_taxonomy": {
            "allowed_values": ["keep", "redesign", "discard", "pathology", "no_promote"],
            "definitions": {},
        },
        "destination_boundaries": {
            "allowed_values": ["runtime", "assets_archaeology", "no_destination"],
            "directory_contract_sources": ["assets/contracts/directory-structure.json"],
        },
        "queue_entry_shape": {
            "required_fields": [
                "id",
                "phase",
                "question",
                "exact_old_sources",
                "stop_condition",
                "acceptance_criteria",
                "risk_level",
                "requires_prism",
                "expected_output",
                "status",
            ],
            "allowed_status": ["queued", "classified", "verified", "blocked"],
            "source_limits": {
                "default_max_files_per_shard": 7,
                "private_archives_allowed": False,
                "raw_prism_runs_allowed_by_default": False,
            },
        },
        "queue_amendment_protocol": {
            "allowed_actors": ["Cap", "Norven"],
            "required_steps": [
                "Run gate",
                "Name exact old source files",
                "Provide stop condition",
                "Run redcap check",
            ],
            "fresh_prism_required_when": ["High-risk Prism amendment"],
            "forbidden_amendments": ["bulk-read old RedCap"],
        },
        "idea_record_shape": {
            "required_fields": [
                "id",
                "source_shard",
                "source_refs",
                "summary",
                "classification",
                "destination_boundary",
                "migration_action",
                "hook_or_gate_assessment",
                "verification_route",
            ],
            "migration_action_values": ["copy", "redesign", "record_no_promote", "defer"],
            "hook_or_gate_values": ["deterministic_gate", "lifecycle_validator", "final_claim_guard"],
        },
        "phases": [{"id": "P2-B", "name": "Bounded Extraction"}],
        "initial_queue": [
            {
                "id": "runtime-workspace-boundary",
                "phase": "P2-B",
                "question": "Fixture question.",
                "exact_old_sources": [
                    "/Users/norven/workspace/redcap/assets/references/runtime-workspace-boundary-policy.json"
                ],
                "stop_condition": "Stop after fixture.",
                "acceptance_criteria": ["Bounded source exists."],
                "risk_level": "high",
                "requires_prism": True,
                "expected_output": "fixture-output.json",
                "status": "queued",
            }
        ],
        "prior_decisions": [
            {
                "id": "pathology-report-as-progress",
                "decision": "no_promote",
                "source": "assets/archaeology/no-promote/pathology-report-as-progress-v1.json",
                "binding_effect": "Support-only reports.",
                "reopen_requires": "bounded evidence",
            },
            {
                "id": "pathology-receipt-as-completion",
                "decision": "no_promote",
                "source": "assets/archaeology/no-promote/pathology-receipt-as-completion-v1.json",
                "binding_effect": "Support-only receipts.",
                "reopen_requires": "bounded evidence",
            },
            {
                "id": "pathology-closeout-recursion",
                "decision": "no_promote",
                "source": "assets/archaeology/no-promote/pathology-closeout-recursion-v1.json",
                "binding_effect": "Support-only closeout.",
                "reopen_requires": "bounded evidence",
            },
            {
                "id": "pathology-raw-evidence-default",
                "decision": "no_promote",
                "source": "assets/archaeology/no-promote/pathology-raw-evidence-default-v1.json",
                "binding_effect": "Explicit raw evidence access.",
                "reopen_requires": "bounded evidence",
            },
        ],
        "initial_idea_records": [
            {
                "id": "fixture-redesign",
                "source_shard": "runtime-workspace-boundary",
                "source_refs": [
                    "fixture#G04",
                    "fixture#G05",
                    "fixture#G06",
                    "fixture#G07",
                    "fixture#G08",
                    "fixture#G09",
                ],
                "summary": "Fixture redesign.",
                "classification": "redesign",
                "destination_boundary": "runtime",
                "migration_action": "redesign",
                "hook_or_gate_assessment": "deterministic_gate",
                "verification_route": ["runtime/bin/redcap check"],
            },
            {
                "id": "fixture-pathology",
                "source_shard": "pathology-report-as-progress",
                "source_refs": ["assets/archaeology/no-promote/pathology-report-as-progress-v1.json"],
                "summary": "Fixture pathology.",
                "classification": "pathology",
                "destination_boundary": "assets_archaeology",
                "migration_action": "record_no_promote",
                "hook_or_gate_assessment": "final_claim_guard",
                "verification_route": ["runtime/bin/redcap check"],
            },
        ],
        "required_checker": {
            "proposed_command": "runtime/bin/redcap phase2-blueprint check --contract assets/contracts/redcap-1.1-phase2-blueprint.json",
            "minimum_assertions": [
                "all queue entries contain exact_old_sources and no directory paths",
                "all idea records use constrained classification and destination values",
                "runtime/bin/redcap check delegates or includes this checker",
            ],
        },
        "human_intervention_rules": ["Ask Norven before private reads."],
        "phase2_exit_criteria": [
            "The authoritative contract exists under assets/contracts.",
            "The contract-specific checker exists.",
            "At least one currently queued item reaches verified.",
            "No concrete old module migration starts before active contract.",
        ],
    }


def command_self_check() -> int:
    failures: list[str] = []
    fixture = self_check_fixture()
    with tempfile.TemporaryDirectory(prefix="redcap-phase2-blueprint-") as tmp:
        path = pathlib.Path(tmp) / "contract.json"
        path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        valid_failures = validate_contract(load_json(path), path, allow_draft=True)
        if valid_failures:
            failures.append(f"valid fixture rejected: {valid_failures}")

        missing_inheritance = copy.deepcopy(fixture)
        missing_inheritance.pop("authority_inheritance")
        if not any("authority_inheritance" in item for item in validate_contract(missing_inheritance, path, allow_draft=True)):
            failures.append("missing authority_inheritance was not rejected")

        directory_source = copy.deepcopy(fixture)
        directory_source["initial_queue"][0]["exact_old_sources"] = [OLD_REDCAP_ROOT + "/assets/references"]
        if not any("non-exact" in item for item in validate_contract(directory_source, path, allow_draft=True)):
            failures.append("directory source was not rejected")

        all_verified = copy.deepcopy(fixture)
        all_verified["initial_queue"][0]["status"] = "verified"
        all_verified["initial_queue"][0]["verification_evidence"] = [
            "runtime/core/phase2_blueprint.py",
            "runtime/bin/redcap phase2-blueprint check",
        ]
        all_verified_failures = validate_contract(all_verified, path, allow_draft=True)
        if all_verified_failures:
            failures.append(f"all-verified queue fixture was rejected: {all_verified_failures}")

        no_redesign = copy.deepcopy(fixture)
        no_redesign["initial_idea_records"][0]["classification"] = "keep"
        no_redesign["initial_idea_records"][0]["migration_action"] = "copy"
        if not any("redesign example" in item for item in validate_contract(no_redesign, path, allow_draft=True)):
            failures.append("missing redesign example was not rejected")

        prior_in_queue = copy.deepcopy(fixture)
        prior_in_queue["initial_queue"].append(
            {
                "id": "pathology-report-as-progress",
                "phase": "P2-C",
                "question": "Bad.",
                "exact_old_sources": [OLD_REDCAP_ROOT + "/assets/references/task-report-template.md"],
                "stop_condition": "Bad.",
                "acceptance_criteria": ["Bad."],
                "risk_level": "high",
                "requires_prism": True,
                "expected_output": "bad.json",
                "status": "no_promote",
            }
        )
        prior_failures = validate_contract(prior_in_queue, path, allow_draft=True)
        if not any("no_promote status" in item for item in prior_failures):
            failures.append("no_promote queue item was not rejected")

        verified_proof_only = copy.deepcopy(fixture)
        verified_proof_only["initial_queue"][0]["status"] = "verified"
        verified_proof_only["initial_queue"][0]["verification_evidence"] = [
            "review document",
            "receipt ledger summary",
        ]
        verified_failures = validate_contract(verified_proof_only, path, allow_draft=True)
        if not any("proof-only" in item for item in verified_failures):
            failures.append("proof-only verified queue evidence was not rejected")

        missing_amendment = copy.deepcopy(fixture)
        missing_amendment.pop("queue_amendment_protocol")
        if not any("queue_amendment_protocol" in item for item in validate_contract(missing_amendment, path, allow_draft=True)):
            failures.append("missing queue_amendment_protocol was not rejected")

    payload = {"ok": not failures, "failures": failures}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_PHASE2_BLUEPRINT_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--contract", help="Contract JSON to validate. Defaults to the authoritative contract.")
    check.add_argument("--allow-draft", action="store_true", help="Allow a draft contract outside assets/contracts.")
    sub.add_parser("self-check")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "check":
        return command_check(args)
    if args.command == "self-check":
        return command_self_check()
    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())

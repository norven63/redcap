#!/usr/bin/env python3
"""Minimal RedCap workflow FSM kernel."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


STATES = {
    "INTAKE",
    "PRISM_REVIEW",
    "IMPLEMENTING",
    "VERIFYING",
    "TEMPORARY_USABLE",
    "BLOCKED",
}

TRANSITIONS = {
    "INTAKE": {"PRISM_REVIEW", "BLOCKED"},
    "PRISM_REVIEW": {"IMPLEMENTING", "BLOCKED"},
    "IMPLEMENTING": {"VERIFYING", "BLOCKED"},
    "VERIFYING": {"TEMPORARY_USABLE", "IMPLEMENTING", "BLOCKED"},
    "TEMPORARY_USABLE": {"IMPLEMENTING"},
    "BLOCKED": {"INTAKE", "PRISM_REVIEW"},
}

REQUIRED_EVIDENCE = {
    ("INTAKE", "PRISM_REVIEW"): {"gate_required_or_optional"},
    ("PRISM_REVIEW", "IMPLEMENTING"): {"prism_review_or_explicit_skip"},
    ("IMPLEMENTING", "VERIFYING"): {"runtime_change"},
    ("VERIFYING", "TEMPORARY_USABLE"): {"redcap_check_passed"},
    ("VERIFYING", "IMPLEMENTING"): {"verification_failed"},
    ("INTAKE", "BLOCKED"): {"blocking_condition"},
    ("PRISM_REVIEW", "BLOCKED"): {"blocking_condition"},
    ("IMPLEMENTING", "BLOCKED"): {"blocking_condition"},
    ("VERIFYING", "BLOCKED"): {"blocking_condition"},
    ("TEMPORARY_USABLE", "IMPLEMENTING"): {"new_requirement"},
    ("BLOCKED", "INTAKE"): {"user_resume"},
    ("BLOCKED", "PRISM_REVIEW"): {"blocker_resolved"},
}


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"state file must be a JSON object: {path}")
    return payload


def transition_allowed(source: str, target: str, evidence: set[str]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if source not in STATES:
        failures.append(f"unknown source state: {source}")
    if target not in STATES:
        failures.append(f"unknown target state: {target}")
    if failures:
        return False, failures
    if target not in TRANSITIONS[source]:
        failures.append(f"transition not allowed: {source}->{target}")
    required = REQUIRED_EVIDENCE.get((source, target), set())
    missing = sorted(required - evidence)
    if missing:
        failures.append(f"missing transition evidence: {', '.join(missing)}")
    return not failures, failures


def state_payload(state: str, *, evidence: list[str] | None = None) -> dict[str, Any]:
    if state not in STATES:
        raise SystemExit(f"unknown state: {state}")
    return {
        "schema_id": "redcap-workflow-fsm",
        "state": state,
        "allowed_next": sorted(TRANSITIONS[state]),
        "evidence": sorted(evidence or []),
    }


def check_kernel() -> dict[str, Any]:
    failures: list[str] = []
    for state, targets in TRANSITIONS.items():
        if state not in STATES:
            failures.append(f"transition table includes unknown state: {state}")
        for target in targets:
            if target not in STATES:
                failures.append(f"{state}: transition to unknown state {target}")
            required = REQUIRED_EVIDENCE.get((state, target))
            if not required:
                failures.append(f"{state}->{target}: transition has no required evidence")
    ok, illegal_failures = transition_allowed("INTAKE", "TEMPORARY_USABLE", {"redcap_check_passed"})
    if ok:
        failures.append("INTAKE->TEMPORARY_USABLE must not be allowed directly")
    elif not any("transition not allowed" in item for item in illegal_failures):
        failures.append("illegal transition probe failed for the wrong reason")
    ok, allowed_failures = transition_allowed(
        "VERIFYING",
        "TEMPORARY_USABLE",
        {"redcap_check_passed"},
    )
    if not ok:
        failures.append(f"VERIFYING->TEMPORARY_USABLE probe failed: {'; '.join(allowed_failures)}")
    return {
        "ok": not failures,
        "states": sorted(STATES),
        "transitions": sum(len(targets) for targets in TRANSITIONS.values()),
        "failures": failures,
    }


def cmd_status(args: argparse.Namespace) -> int:
    if args.state_file:
        payload = load_json(pathlib.Path(args.state_file).resolve())
        state = str(payload.get("state") or "")
        evidence = payload.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = []
    else:
        state = args.state
        evidence = args.evidence
    print(json.dumps(state_payload(state, evidence=evidence), ensure_ascii=False, indent=2))
    return 0


def cmd_transition(args: argparse.Namespace) -> int:
    ok, failures = transition_allowed(args.source, args.target, set(args.evidence))
    result = {
        "ok": ok,
        "source": args.source,
        "target": args.target,
        "evidence": sorted(args.evidence),
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def cmd_check(_: argparse.Namespace) -> int:
    result = check_kernel()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        return 1
    print("REDCAP_FSM_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap workflow FSM")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status")
    status.add_argument("--state", default="INTAKE", choices=sorted(STATES))
    status.add_argument("--state-file")
    status.add_argument("--evidence", action="append", default=[])
    status.set_defaults(func=cmd_status)

    transition = subparsers.add_parser("transition")
    transition.add_argument("--from", dest="source", required=True, choices=sorted(STATES))
    transition.add_argument("--to", dest="target", required=True, choices=sorted(STATES))
    transition.add_argument("--evidence", action="append", default=[])
    transition.set_defaults(func=cmd_transition)

    check = subparsers.add_parser("check")
    check.set_defaults(func=cmd_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

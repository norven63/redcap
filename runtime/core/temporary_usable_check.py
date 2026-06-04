#!/usr/bin/env python3
"""Check whether the current scaffold is temporarily usable for RedCap revival."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

ALLOWED_ENFORCEMENT_WARNINGS: set[str] = set()

ALLOWED_HOOK_WARNINGS: set[str] = set()


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=str(REPO_ROOT), check=False, capture_output=True, text=True)


def leading_json(stdout: str) -> dict[str, Any]:
    parsed, _ = json.JSONDecoder().raw_decode(stdout.lstrip())
    if not isinstance(parsed, dict):
        raise ValueError("leading JSON is not an object")
    return parsed


def check_command(name: str, argv: list[str], sentinel: str | None, failures: list[str]) -> None:
    completed = run(argv)
    if completed.returncode != 0:
        failures.append(f"{name}: exit {completed.returncode}")
        return
    if sentinel and sentinel not in completed.stdout:
        failures.append(f"{name}: missing sentinel {sentinel}")


def main() -> int:
    failures: list[str] = []

    enforcement = run(["runtime/bin/redcap", "enforcement-check"])
    if enforcement.returncode != 0:
        failures.append("enforcement-check failed")
    else:
        try:
            payload = leading_json(enforcement.stdout)
        except Exception as exc:
            failures.append(f"enforcement-check invalid JSON: {exc}")
        else:
            warnings = set(payload.get("warnings", []))
            unexpected = sorted(warnings - ALLOWED_ENFORCEMENT_WARNINGS)
            missing_probes = [
                probe for probe in [
                    "session-ownership-kernel:session ownership self-check distinguishes owned from mismatch",
                    "provider-dispatcher:provider dispatcher self-check enforces sessions, retries timeouts, and extracts nested reviews",
                    "provider-dispatcher:provider dispatcher verifies persisted real provider evidence",
                    "host-level-hook-interception:host hook audit verifies Codex hooks and dispatcher boundary",
                    "fsm-workflow-gates:FSM kernel validates transition table",
                    "knowledge-gateway:knowledge gateway validates index-first policy",
                    "knowledge-gateway:knowledge gateway writes, reviews, promotes, and searches a fixture",
                    "layout-check:directory policy rejects sprawl fixtures",
                    "cap-soul-loader:Cap identity source is loadable",
                    "cap-soul-loader:Cap soul loader redacts private fixture evidence",
                    "prism-task-execution-ledger:Prism task ledger records and summarizes fixture execution",
                    "prism-task-execution-ledger:Prism gate evaluations append to the ledger",
                    "prism-task-execution-ledger:Prism task ledger summary is queryable",
                    "runtime-boundary-kernel:runtime boundary accepts current self-development context",
                    "runtime-boundary-kernel:runtime boundary self-check rejects cross-boundary leaks",
                    "old-redcap-archaeology-shards:old RedCap boundary rules are extracted from bounded sources",
                    "old-redcap-archaeology-shards:archaeology shards reject missing extraction and wildcard sources",
                    "development-lifecycle-evidence-gate:development lifecycle rejects documentation-only completion",
                    "development-lifecycle-evidence-gate:self-development lifecycle packet is required by intake",
                    "development-lifecycle-evidence-gate:self-development lifecycle packet is checked by gate",
                    "development-lifecycle-evidence-gate:external workspace architecture does not require self-development packet",
                    "final-claim-guard:final claim guard blocks completion without task-body marker",
                ]
                if probe not in payload.get("probes_run", [])
            ]
            if unexpected:
                failures.append(f"unexpected enforcement warnings: {unexpected}")
            if missing_probes:
                failures.append(f"missing temporary usable probes: {missing_probes}")

    hook = run(["runtime/bin/redcap", "hook-coverage-check"])
    if hook.returncode != 0:
        failures.append("hook-coverage-check failed")
    else:
        try:
            payload = leading_json(hook.stdout)
        except Exception as exc:
            failures.append(f"hook-coverage-check invalid JSON: {exc}")
        else:
            warnings = set(payload.get("warnings", []))
            unexpected = sorted(warnings - ALLOWED_HOOK_WARNINGS)
            required_now = set(payload.get("required_now_entries", []))
            for entry in [
                "session-ownership-kernel",
                "provider-dispatcher",
                "prism-task-execution-ledger",
                "cap-soul-loader",
                "host-level-hook-interception",
                "fsm-workflow-gates",
                "knowledge-gateway",
                "runtime-boundary-kernel",
                "old-redcap-archaeology-shards",
                "development-lifecycle-evidence-gate",
                "final-claim-guard",
            ]:
                if entry not in required_now:
                    failures.append(f"{entry}: not hook-covered as required_now")
            if unexpected:
                failures.append(f"unexpected hook warnings: {unexpected}")

    check_command("prism-check", ["runtime/prism/bin/prism", "check"], "PRISM_CHECK_OK", failures)
    check_command("provider-dispatcher", ["runtime/prism/bin/prism-dispatch", "--self-check"], "PRISM_DISPATCH_SELF_CHECK_OK", failures)
    check_command("host-hook-audit", ["runtime/bin/redcap", "host-hook-audit"], "REDCAP_HOST_HOOK_AUDIT_OK", failures)
    check_command("session-ownership", ["runtime/bin/redcap", "session-ownership", "self-check"], "REDCAP_SESSION_OWNERSHIP_OK", failures)
    check_command("fsm", ["runtime/bin/redcap", "fsm", "check"], "REDCAP_FSM_OK", failures)
    check_command("knowledge-gateway", ["runtime/bin/redcap", "knowledge-gateway", "check"], "REDCAP_KNOWLEDGE_GATEWAY_OK", failures)
    check_command("knowledge-write-review", ["runtime/bin/redcap", "knowledge-gateway", "self-check"], "REDCAP_KNOWLEDGE_WRITE_REVIEW_OK", failures)
    check_command("cap-soul-source", ["runtime/bin/redcap", "soul-load", "check"], "REDCAP_SOUL_SOURCE_OK", failures)
    check_command("cap-soul-loader", ["runtime/bin/redcap", "soul-load", "self-check"], "REDCAP_SOUL_LOADER_OK", failures)
    check_command("prism-ledger", ["runtime/bin/redcap", "prism-ledger", "self-check"], "PRISM_LEDGER_SELF_CHECK_OK", failures)
    check_command("prism-ledger-summary", ["runtime/bin/redcap", "prism-ledger", "summary"], "PRISM_LEDGER_SUMMARY_OK", failures)
    check_command("boundary", ["runtime/bin/redcap", "boundary", "check"], "REDCAP_RUNTIME_BOUNDARY_OK", failures)
    check_command(
        "boundary-self-check",
        ["runtime/bin/redcap", "boundary", "self-check"],
        "REDCAP_RUNTIME_BOUNDARY_SELF_CHECK_OK",
        failures,
    )
    check_command("archaeology", ["runtime/bin/redcap", "archaeology", "check"], "REDCAP_ARCHAEOLOGY_SHARDS_OK", failures)
    check_command(
        "archaeology-self-check",
        ["runtime/bin/redcap", "archaeology", "self-check"],
        "REDCAP_ARCHAEOLOGY_SHARDS_SELF_CHECK_OK",
        failures,
    )
    check_command(
        "lifecycle",
        ["runtime/bin/redcap", "lifecycle", "self-check"],
        "REDCAP_DEVELOPMENT_LIFECYCLE_SELF_CHECK_OK",
        failures,
    )
    check_command(
        "final-claim-guard",
        ["runtime/bin/redcap", "final-claim", "self-check"],
        "REDCAP_FINAL_CLAIM_GUARD_SELF_CHECK_OK",
        failures,
    )
    check_command("layout", ["runtime/bin/redcap", "layout-check"], "REDCAP_LAYOUT_OK", failures)
    check_command("layout-self-check", ["runtime/bin/redcap", "layout-check", "self-check"], "REDCAP_LAYOUT_SELF_CHECK_OK", failures)
    check_command(
        "temporary-usable-transition",
        [
            "runtime/bin/redcap",
            "fsm",
            "transition",
            "--from",
            "VERIFYING",
            "--to",
            "TEMPORARY_USABLE",
            "--evidence",
            "redcap_check_passed",
        ],
        '"ok": true',
        failures,
    )

    result = {
        "ok": not failures,
        "allowed_rough_edges": sorted(ALLOWED_ENFORCEMENT_WARNINGS),
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_TEMPORARY_USABLE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

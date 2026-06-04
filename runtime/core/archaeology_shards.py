#!/usr/bin/env python3
"""Bounded old-RedCap archaeology shard extraction."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_OLD_ROOT = pathlib.Path("/Users/norven/workspace/redcap")
DEFAULT_OUTPUT = REPO_ROOT / "assets" / "archaeology" / "extractions" / "runtime-workspace-boundary-v1.json"
TASKS_PATH = REPO_ROOT / "assets" / "archaeology" / "shards" / "index.json"


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"json object expected: {path}")
    return payload


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def classify_guarantee(text: str) -> str:
    lowered = text.lower()
    if "public release" in lowered:
        return "defer_release"
    if "redcap runtime repository" in lowered or "redcap repository" in lowered:
        return "portable_with_self_development_exception"
    return "portable"


def extract_boundary(old_root: pathlib.Path, output: pathlib.Path) -> dict[str, Any]:
    policy_path = old_root / "assets" / "references" / "runtime-workspace-boundary-policy.json"
    facade_path = old_root / "runtime" / "redcap-core" / "tools" / "redcap-runtime-workspace-boundary-check.py"
    delegated_path = old_root / "compass" / "tools" / "redcap-runtime-workspace-boundary-check.py"
    for path in [policy_path, facade_path, delegated_path]:
        if not path.is_file():
            raise SystemExit(f"required bounded source missing: {path}")
    policy = read_json(policy_path)
    delegated_text = delegated_path.read_text(encoding="utf-8", errors="replace")
    guarantees = policy.get("required_guarantees")
    if not isinstance(guarantees, list) or len(guarantees) < 9:
        raise SystemExit("old boundary policy must contain at least 9 guarantees")
    extracted = {
        "schema_id": "old-redcap-boundary-extraction",
        "version": 1,
        "extracted_at": iso_now(),
        "old_root": str(old_root.resolve()),
        "bounded_sources": [
            {
                "path": str(policy_path),
                "role": "source-policy",
                "sha256": sha256_file(policy_path),
                "line_count": len(policy_path.read_text(encoding="utf-8").splitlines()),
            },
            {
                "path": str(facade_path),
                "role": "runtime-facade",
                "sha256": sha256_file(facade_path),
                "line_count": len(facade_path.read_text(encoding="utf-8").splitlines()),
            },
            {
                "path": str(delegated_path),
                "role": "authoritative-checker",
                "sha256": sha256_file(delegated_path),
                "line_count": len(delegated_text.splitlines()),
            },
        ],
        "read_policy": {
            "mode": "bounded-exact-files",
            "bulk_read": False,
            "source_count": 3,
            "stop_condition": "extract runtime/project/user boundary guarantees only",
        },
        "layers": {
            "runtime": policy.get("runtime_layer", {}),
            "project": policy.get("project_layer", {}),
            "user": policy.get("user_layer", {}),
        },
        "guarantees": [
            {
                "id": f"G{index:02d}",
                "text": str(item),
                "classification": classify_guarantee(str(item)),
            }
            for index, item in enumerate(guarantees, start=1)
        ],
        "checker_behaviors": {
            "validates_policy_shape": "require_policy(" in delegated_text,
            "runs_external_workspace_smoke": "run_external_workspace_smoke(" in delegated_text,
            "walks_up_to_task_file": "subdirectory invocation must walk up" in delegated_text,
            "rejects_runtime_task_leak": "assert_no_runtime_task_leak" in delegated_text,
            "checks_doctor_debug": "doctor workspace smoke" in delegated_text and "debug workspace smoke" in delegated_text,
        },
        "portable_rules_for_new_redcap": [
            "workspace-oriented commands must resolve project_workspace from caller context, not from RedCap runtime root",
            "task_file defaults to <project_workspace>/.dev-task.md unless explicit task file is supplied",
            "self-development is the only case where project_workspace may equal runtime_root",
            "status/diagnose/debug-style outputs must expose runtime_root, project_workspace, task_file, and user_private_root",
            "user identity and private local state stay outside runtime_root and project_workspace",
            "external project evidence and runtime state must not default into RedCap runtime_root or the managed project workspace",
        ],
        "discard_or_defer": [
            "old release-readiness review coupling is deferred; the new kernel should first enforce boundary resolution",
            "old command-specific shell branch inspection is not copied wholesale; new commands should expose one shared boundary resolver",
        ],
    }
    write_json(output, extracted)
    return extracted


def cmd_extract_boundary(args: argparse.Namespace) -> int:
    extracted = extract_boundary(pathlib.Path(args.old_root).resolve(), pathlib.Path(args.output).resolve())
    print(json.dumps({"ok": True, "output": args.output, "guarantees": len(extracted["guarantees"])}, ensure_ascii=False, indent=2))
    print("REDCAP_ARCHAEOLOGY_BOUNDARY_EXTRACT_OK")
    return 0


def validate_extraction(path: pathlib.Path) -> list[str]:
    failures: list[str] = []
    if not path.is_file():
        return [f"missing boundary extraction: {path}"]
    payload = read_json(path)
    if payload.get("schema_id") != "old-redcap-boundary-extraction":
        failures.append("invalid extraction schema_id")
    sources = payload.get("bounded_sources")
    if not isinstance(sources, list) or len(sources) != 3:
        failures.append("boundary extraction must cite exactly three bounded sources")
    guarantees = payload.get("guarantees")
    if not isinstance(guarantees, list) or len(guarantees) < 9:
        failures.append("boundary extraction must preserve at least nine guarantees")
    else:
        for item in guarantees:
            if not isinstance(item, dict) or not item.get("id") or not item.get("text") or not item.get("classification"):
                failures.append("each guarantee needs id, text, and classification")
                break
    read_policy = payload.get("read_policy", {})
    if read_policy.get("bulk_read") is not False:
        failures.append("extraction must record bulk_read=false")
    portable = payload.get("portable_rules_for_new_redcap")
    if not isinstance(portable, list) or len(portable) < 4:
        failures.append("extraction must produce portable rules")
    return failures


def shard_index_payload() -> dict[str, Any]:
    return {
        "schema_id": "redcap-archaeology-shard-index",
        "version": 1,
        "updated_at": iso_now(),
        "read_policy": "exact-files-before-shard; no directory bulk-read",
        "shards": [
            {
                "id": "runtime-workspace-boundary",
                "status": "extracted",
                "question": "Which old RedCap rules separate runtime root, project workspace, and user-private state?",
                "candidate_sources": [
                    "/Users/norven/workspace/redcap/assets/references/runtime-workspace-boundary-policy.json",
                    "/Users/norven/workspace/redcap/runtime/redcap-core/tools/redcap-runtime-workspace-boundary-check.py",
                    "/Users/norven/workspace/redcap/compass/tools/redcap-runtime-workspace-boundary-check.py",
                ],
                "output": "assets/archaeology/extractions/runtime-workspace-boundary-v1.json",
                "acceptance": "Boundary extraction exists, has exactly bounded sources, and preserves required guarantees.",
            },
            {
                "id": "development-lifecycle-review",
                "status": "planned",
                "question": "Which old review tracks are portable without duplicating the new FSM?",
                "candidate_sources": [
                    "/Users/norven/workspace/redcap/assets/references/review-tracks.json",
                    "/Users/norven/workspace/redcap/assets/references/task-report-template.md",
                ],
                "output": None,
                "acceptance": "Produces lifecycle evidence rules mapped to existing FSM transitions, not a second state machine.",
            },
            {
                "id": "long-task-context-defense",
                "status": "planned",
                "question": "Which old long-task defenses should become Prism shard ledger rules?",
                "candidate_sources": [
                    "/Users/norven/workspace/redcap/assets/knowledge/long-task-context-defense.md"
                ],
                "output": None,
                "acceptance": "Produces shard split/acceptance rules and explicit anti-bulk-read limits.",
            },
            {
                "id": "pathology-report-as-progress",
                "status": "planned",
                "question": "Which old report rules helped verification, and which report mechanics let written reports substitute for changed reality?",
                "candidate_sources": [
                    "/Users/norven/workspace/redcap/assets/references/task-report-template.md",
                    "/Users/norven/workspace/redcap/runtime/redcap-core/tools/redcap-task-report-check.sh",
                    "/Users/norven/workspace/redcap/compass/tools/redcap-task-report-check.sh",
                ],
                "output": None,
                "acceptance": "Produces anti-pattern rules that distinguish useful reports from report-as-progress pathology, with no task-report body migration.",
                "stop_condition": "extract only report/progress semantics and guardrail candidates; do not read historical task-report bodies",
            },
            {
                "id": "pathology-receipt-as-completion",
                "status": "planned",
                "question": "Which old receipt rules are useful proof chains, and which allowed receipts or aggregation to masquerade as completion?",
                "candidate_sources": [
                    "/Users/norven/workspace/redcap/assets/references/parent-receipt-aggregation-policy.json",
                    "/Users/norven/workspace/redcap/compass/tools/redcap-parent-receipt-aggregation-check.py",
                    "/Users/norven/workspace/redcap/compass/tools/redcap-parent-receipt-aggregation-check.sh",
                ],
                "output": None,
                "acceptance": "Produces receipt semantics that keep receipts as proof after reality changes, never as completion itself.",
                "stop_condition": "extract receipt/completion boundary only; do not inspect receipt archives or private task bodies",
            },
            {
                "id": "pathology-closeout-recursion",
                "status": "planned",
                "question": "Which old closeout mechanics are needed for safe recovery, and which created closeout work before implementation reality changed?",
                "candidate_sources": [
                    "/Users/norven/workspace/redcap/runtime/redcap-core/closeout-cap.sh",
                    "/Users/norven/workspace/redcap/runtime/redcap-core/tools/redcap-layerb-closeout-runtime.py",
                    "/Users/norven/workspace/redcap/compass/tools/redcap-layerb-closeout-runtime.py",
                    "/Users/norven/workspace/redcap/assets/docs/specs/2026-04-22-layerb-closeout-runtime-and-promise-ledger-design.md",
                ],
                "output": None,
                "acceptance": "Produces closeout recursion limits and cut lines between closeout, implementation, and verification.",
                "stop_condition": "extract closeout recursion and ownership limits only; do not execute old closeout scripts",
            },
            {
                "id": "pathology-raw-evidence-default",
                "status": "planned",
                "question": "Which old evidence retention rules preserve proof, and which made raw evidence the default context surface?",
                "candidate_sources": [
                    "/Users/norven/workspace/redcap/prism/tools/prism-evidence-check.sh",
                    "/Users/norven/workspace/redcap/runtime/redcap-core/prism-tools/prism-evidence-check.sh",
                    "/Users/norven/workspace/redcap/compass/tools/redcap-r1-prism-evidence-retention-split-check.py",
                    "/Users/norven/workspace/redcap/assets/references/r1-prism-evidence-retention-split-preflight.json",
                ],
                "output": None,
                "acceptance": "Produces raw-evidence access limits that keep evidence queryable without making raw dumps default context.",
                "stop_condition": "extract evidence-retention and context-default rules only; do not read raw prism runs or evidence archives",
            },
        ],
    }


def cmd_seed(args: argparse.Namespace) -> int:
    output = pathlib.Path(args.output).resolve()
    write_json(output, shard_index_payload())
    print(json.dumps({"ok": True, "index": str(output)}, ensure_ascii=False, indent=2))
    print("REDCAP_ARCHAEOLOGY_SHARDS_SEEDED")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    extraction = pathlib.Path(args.extraction).resolve()
    index = pathlib.Path(args.index).resolve()
    failures = validate_extraction(extraction)
    if not index.is_file():
        failures.append(f"missing shard index: {index}")
    else:
        payload = read_json(index)
        if payload.get("schema_id") != "redcap-archaeology-shard-index":
            failures.append("invalid shard index schema_id")
        for shard in payload.get("shards", []):
            sources = shard.get("candidate_sources") if isinstance(shard, dict) else None
            if not isinstance(sources, list) or not sources:
                failures.append("each shard must have bounded candidate_sources")
                break
            if any(str(source).endswith("/") or "*" in str(source) for source in sources):
                failures.append("shard candidate_sources must be exact files, not directories or globs")
                break
            missing = [str(source) for source in sources if not pathlib.Path(str(source)).is_file()]
            if missing:
                failures.append(f"shard candidate_sources must exist: {missing[:3]}")
                break
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_ARCHAEOLOGY_SHARDS_OK")
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="redcap-archaeology-") as tmp_raw:
        tmp = pathlib.Path(tmp_raw)
        bad_index = tmp / "bad-index.json"
        write_json(bad_index, {
            "schema_id": "redcap-archaeology-shard-index",
            "shards": [{"id": "bad", "candidate_sources": ["/tmp/old-redcap/*"]}],
        })
        extraction = tmp / "missing.json"
        result = validate_extraction(extraction)
        if not result:
            failures.append("missing extraction was not rejected")
        payload = read_json(bad_index)
        if "*" not in payload["shards"][0]["candidate_sources"][0]:
            failures.append("fixture error")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_ARCHAEOLOGY_SHARDS_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap bounded archaeology shards")
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract-boundary")
    extract.add_argument("--old-root", default=str(DEFAULT_OLD_ROOT))
    extract.add_argument("--output", default=str(DEFAULT_OUTPUT))
    extract.set_defaults(func=cmd_extract_boundary)

    seed = sub.add_parser("seed")
    seed.add_argument("--output", default=str(TASKS_PATH))
    seed.set_defaults(func=cmd_seed)

    check = sub.add_parser("check")
    check.add_argument("--extraction", default=str(DEFAULT_OUTPUT))
    check.add_argument("--index", default=str(TASKS_PATH))
    check.set_defaults(func=cmd_check)

    self_check = sub.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

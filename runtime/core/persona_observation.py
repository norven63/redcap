#!/usr/bin/env python3
"""RedCap Cap 人格沉淀观察升级检查器。"""

from __future__ import annotations

import argparse
import json
import pathlib
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = REPO_ROOT / "assets" / "contracts" / "persona-observation.json"
DEFAULT_EVIDENCE_ROOT = REPO_ROOT / "assets" / "evidence" / "self-purification"
PROBLEM = "problem"
WARNING = "warning"
HEALTHY = "healthy"
PRIVATE_PRIVACY_CLASSES = {"private", "cap-private"}
PERSONA_DECISIONS = {
    "private_boundary_only",
    "keep_private",
    "no_promote_persona",
    "not_persona",
    "no_persona_update",
}
FORBIDDEN_PERSONA_FIELDS = {
    "private_identity_body",
    "raw_persona_body",
    "secret",
    "token",
    "credential",
}


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}") from exc


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def repo_rel(path: pathlib.Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def text_value(value: Any) -> str:
    return str(value or "").strip()


def candidate_needs_persona_decision(candidate: dict[str, Any]) -> bool:
    privacy_class = text_value(candidate.get("privacy_class")).lower()
    trigger = text_value(candidate.get("trigger")).lower()
    kind = text_value(candidate.get("kind")).lower()
    candidate_id = text_value(candidate.get("id")).lower()
    return (
        privacy_class in PRIVATE_PRIVACY_CLASSES
        or trigger == "persona_signal"
        or "persona" in kind
        or "人格" in kind
        or "persona" in candidate_id
    )


def forbidden_field_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            current = f"{prefix}.{key}" if prefix else str(key)
            if str(key) in FORBIDDEN_PERSONA_FIELDS:
                paths.append(current)
            paths.extend(forbidden_field_paths(child, current))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(forbidden_field_paths(child, f"{prefix}[{index}]"))
    return paths


def validate_persona_decision(path: pathlib.Path) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    warnings: list[str] = []
    payload = load_json(path)
    if not isinstance(payload, dict):
        return [f"{repo_rel(path)} must be object"], warnings
    decision = text_value(payload.get("decision"))
    if decision not in PERSONA_DECISIONS:
        warnings.append(f"{repo_rel(path)} decision is not a recognized persona boundary decision: {decision}")
    if "private_body_written" in payload and payload.get("private_body_written") is not False:
        problems.append(f"{repo_rel(path)} private_body_written must be false")
    elif "private_body_written" not in payload:
        warnings.append(f"{repo_rel(path)} does not record private_body_written=false; legacy evidence kept as observation")
    if payload.get("public_body_written") is True and decision != "not_persona":
        problems.append(f"{repo_rel(path)} writes public body for a persona boundary decision")
    forbidden = forbidden_field_paths(payload)
    if forbidden:
        problems.append(f"{repo_rel(path)} contains forbidden persona evidence fields: {forbidden}")
    return problems, warnings


def directory_record(path: pathlib.Path) -> dict[str, Any]:
    candidates_path = path / "self-purification-candidates.json"
    persona_path = path / "persona-distillation-decision.json"
    resolution_path = path / "runner-self-purification-resolution.json"
    record: dict[str, Any] = {
        "path": repo_rel(path),
        "candidates": repo_rel(candidates_path) if candidates_path.exists() else None,
        "persona_boundary": repo_rel(persona_path) if persona_path.exists() else None,
        "resolution": repo_rel(resolution_path) if resolution_path.exists() else None,
        "candidate_count": 0,
        "private_or_persona_candidate_count": 0,
        "observations": [],
    }
    if not candidates_path.exists():
        return record
    candidates_payload = load_json(candidates_path)
    candidates = as_list(as_dict(candidates_payload).get("candidates"))
    record["candidate_count"] = len(candidates)
    private_candidates = [item for item in candidates if isinstance(item, dict) and candidate_needs_persona_decision(item)]
    record["private_or_persona_candidate_count"] = len(private_candidates)
    if private_candidates and not persona_path.exists():
        record["observations"].append({
            "severity": PROBLEM,
            "rule": "private-candidate-missing-persona-decision",
            "message": "私人人格或 persona_signal 候选缺少 persona-distillation-decision.json。",
        })
    elif candidates and not persona_path.exists():
        record["observations"].append({
            "severity": WARNING,
            "rule": "public-candidate-missing-boundary",
            "message": "公共候选缺少 persona 边界记录；保留观察，不阻断检查。",
        })
    if candidates and not resolution_path.exists():
        record["observations"].append({
            "severity": WARNING,
            "rule": "missing-runner-resolution",
            "message": "候选存在但缺少 runner-self-purification-resolution.json；保留观察。",
        })
    if persona_path.exists():
        problems, warnings = validate_persona_decision(persona_path)
        for message in problems:
            record["observations"].append({"severity": PROBLEM, "rule": "persona-boundary-invalid", "message": message})
        for message in warnings:
            record["observations"].append({"severity": WARNING, "rule": "persona-boundary-warning", "message": message})
    return record


def public_leak_scan_summary() -> dict[str, Any]:
    from cap_revival_portability import PUBLIC_SCAN_ROOTS, forbidden_public_fragments, text_leak_scan

    result = text_leak_scan(PUBLIC_SCAN_ROOTS, forbidden_public_fragments())
    return {
        "ok": result.get("ok") is True,
        "hit_count": result.get("hit_count"),
        "hits": result.get("hits", [])[:20],
    }


def check(
    *,
    evidence_root: pathlib.Path = DEFAULT_EVIDENCE_ROOT,
    contract_path: pathlib.Path = DEFAULT_CONTRACT,
    include_public_leak_scan: bool = True,
) -> dict[str, Any]:
    contract = load_json(contract_path)
    contract_failures: list[str] = []
    if not isinstance(contract, dict) or contract.get("schema_id") != "redcap-persona-observation-contract":
        contract_failures.append("persona observation contract schema_id invalid")
    if as_dict(contract).get("scope", {}).get("does_not_read_private_identity_body") is not True:
        contract_failures.append("contract must forbid reading private identity body")
    records: list[dict[str, Any]] = []
    if evidence_root.exists():
        for candidates_path in sorted(evidence_root.rglob("self-purification-candidates.json")):
            records.append(directory_record(candidates_path.parent))
    leak_summary = public_leak_scan_summary() if include_public_leak_scan else {"ok": True, "hit_count": None, "hits": []}
    observations = [
        observation
        for record in records
        for observation in as_list(record.get("observations"))
        if isinstance(observation, dict)
    ]
    if contract_failures:
        observations.extend({"severity": PROBLEM, "rule": "contract-invalid", "message": item} for item in contract_failures)
    if leak_summary.get("ok") is not True:
        observations.append({
            "severity": PROBLEM,
            "rule": "public-leak-scan-hit",
            "message": "公共泄漏扫描发现私有身份或凭据命中。",
        })
    problem_count = sum(1 for item in observations if item.get("severity") == PROBLEM)
    warning_count = sum(1 for item in observations if item.get("severity") == WARNING)
    state = PROBLEM if problem_count else WARNING if warning_count else HEALTHY
    return {
        "schema_id": "redcap-persona-observation-check",
        "ok": problem_count == 0,
        "state": state,
        "contract": repo_rel(contract_path),
        "evidence_root": repo_rel(evidence_root),
        "gap_map": as_dict(contract).get("gap_map", {}),
        "records_scanned": len(records),
        "problem_count": problem_count,
        "warning_count": warning_count,
        "observations": observations,
        "directories": records,
        "public_leak_scan": leak_summary,
        "completion_boundary": "本检查只把 LS-005 从人工保留观察升级为可执行观察与升级机制；warning 不关闭真实能力缺口，problem 必须修复后才能通过。",
    }


def should_fail(state: str, fail_on: str) -> bool:
    if fail_on == "never":
        return False
    if fail_on == "warning":
        return state in {WARNING, PROBLEM}
    return state == PROBLEM


def cmd_check(args: argparse.Namespace) -> int:
    result = check(
        evidence_root=pathlib.Path(args.evidence_root).resolve(),
        contract_path=pathlib.Path(args.contract).resolve(),
        include_public_leak_scan=not args.skip_public_leak_scan,
    )
    if args.out:
        write_json(pathlib.Path(args.out).resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if should_fail(result["state"], args.fail_on):
        return 1
    print("REDCAP_PERSONA_OBSERVATION_OK")
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="redcap-persona-observation-") as raw:
        root = pathlib.Path(raw)
        public_dir = root / "public"
        public_dir.mkdir()
        write_json(public_dir / "self-purification-candidates.json", {
            "schema_id": "redcap-self-purification-candidates",
            "candidates": [{"id": "public-candidate", "privacy_class": "public", "trigger": "workflow_drift"}],
            "decisions": [{"candidate_id": "public-candidate", "decision": "no_promote", "reason": "fixture reason"}],
        })
        public_result = check(evidence_root=root, include_public_leak_scan=False)
        if public_result["state"] != WARNING:
            failures.append("公共候选缺少边界记录应为 warning")

        private_dir = root / "private-missing"
        private_dir.mkdir()
        write_json(private_dir / "self-purification-candidates.json", {
            "schema_id": "redcap-self-purification-candidates",
            "candidates": [{"id": "cap-private-candidate", "privacy_class": "cap-private", "trigger": "persona_signal"}],
            "decisions": [{"candidate_id": "cap-private-candidate", "decision": "keep_private", "reason": "fixture reason"}],
        })
        private_missing = check(evidence_root=root, include_public_leak_scan=False)
        if private_missing["state"] != PROBLEM:
            failures.append("私人人格候选缺少边界记录应为 problem")

        good_dir = root / "private-good"
        good_dir.mkdir()
        write_json(good_dir / "self-purification-candidates.json", {
            "schema_id": "redcap-self-purification-candidates",
            "candidates": [{"id": "cap-private-good", "privacy_class": "cap-private", "trigger": "persona_signal"}],
            "decisions": [{"candidate_id": "cap-private-good", "decision": "keep_private", "reason": "fixture reason"}],
        })
        write_json(good_dir / "persona-distillation-decision.json", {
            "schema_id": "redcap-cap-persona-boundary-decision",
            "candidate_id": "cap-private-good",
            "decision": "private_boundary_only",
            "reason": "fixture keeps private boundary",
            "hash": "fixture",
            "counts": {"lesson_chars": 7},
            "private_body_written": False,
            "public_body_written": False,
        })
        write_json(good_dir / "runner-self-purification-resolution.json", {
            "schema_id": "redcap-self-purification-resolution",
            "ok": True,
            "decision": "keep_private",
        })
        good_only = check(evidence_root=good_dir, include_public_leak_scan=False)
        if good_only["state"] != HEALTHY:
            failures.append(f"完整私人人格边界样例应为 healthy，实际为 {good_only['state']}")

        leak_dir = root / "private-leak"
        leak_dir.mkdir()
        write_json(leak_dir / "self-purification-candidates.json", {
            "schema_id": "redcap-self-purification-candidates",
            "candidates": [{"id": "cap-private-leak", "privacy_class": "cap-private", "trigger": "persona_signal"}],
            "decisions": [{"candidate_id": "cap-private-leak", "decision": "keep_private", "reason": "fixture reason"}],
        })
        write_json(leak_dir / "persona-distillation-decision.json", {
            "schema_id": "redcap-cap-persona-boundary-decision",
            "candidate_id": "cap-private-leak",
            "decision": "private_boundary_only",
            "private_body_written": True,
        })
        leak_result = check(evidence_root=leak_dir, include_public_leak_scan=False)
        if leak_result["state"] != PROBLEM:
            failures.append("私人人格正文写入样例应为 problem")
    result = {"ok": not failures, "failures": failures}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_PERSONA_OBSERVATION_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap Cap 人格沉淀观察升级检查器")
    sub = parser.add_subparsers(dest="command", required=True)
    check_cmd = sub.add_parser("check")
    check_cmd.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    check_cmd.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT))
    check_cmd.add_argument("--out")
    check_cmd.add_argument("--fail-on", choices=["problem", "warning", "never"], default="problem")
    check_cmd.add_argument("--skip-public-leak-scan", action="store_true")
    check_cmd.set_defaults(func=cmd_check)
    self_check = sub.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

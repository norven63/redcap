#!/usr/bin/env python3
"""Check that process artifacts stay out of stable contract directories."""

from __future__ import annotations

import argparse
import fnmatch
import json
import pathlib
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_POLICY = REPO_ROOT / "assets" / "contracts" / "process-artifact-placement.json"


def rel(path: pathlib.Path, root: pathlib.Path) -> str:
    return path.relative_to(root).as_posix()


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}") from exc


def normalize_path(value: str) -> str:
    return pathlib.PurePosixPath(value).as_posix()


def load_policy(path: pathlib.Path) -> dict[str, Any]:
    policy = load_json(path)
    if not isinstance(policy, dict):
        raise SystemExit("process artifact policy must be a JSON object")
    if policy.get("schema_id") != "redcap-process-artifact-placement-policy":
        raise SystemExit("process artifact policy schema_id must be redcap-process-artifact-placement-policy")
    required = [
        "forbidden_roots",
        "process_artifact_patterns",
        "allowed_roots",
        "artifact_identities",
        "migration_policy",
    ]
    missing = [key for key in required if key not in policy]
    if missing:
        raise SystemExit(f"process artifact policy missing keys: {', '.join(missing)}")
    for key in ["forbidden_roots", "process_artifact_patterns"]:
        values = policy[key]
        if not isinstance(values, list) or not all(isinstance(item, str) and item for item in values):
            raise SystemExit(f"process artifact policy {key} must be a non-empty string list")
    if not isinstance(policy["allowed_roots"], dict) or not policy["allowed_roots"]:
        raise SystemExit("process artifact policy allowed_roots must be a non-empty object")
    identities = policy["artifact_identities"]
    if not isinstance(identities, dict) or not identities:
        raise SystemExit("process artifact policy artifact_identities must be a non-empty object")
    migration_policy = policy["migration_policy"]
    if not isinstance(migration_policy, dict):
        raise SystemExit("process artifact policy migration_policy must be an object")
    if migration_policy.get("legacy_allowlist_allowed") is not False:
        raise SystemExit("process artifact policy must not allow legacy allowlists")
    if "legacy_allowlist" in policy:
        raise SystemExit("process artifact policy must not define legacy_allowlist")
    return policy


def matches_process_artifact(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def semantic_process_artifact_reason(path: pathlib.Path, policy: dict[str, Any]) -> str | None:
    if path.suffix != ".json":
        return None
    indicators = policy.get("semantic_indicators")
    if not isinstance(indicators, dict):
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    identities = policy.get("artifact_identities")
    identities = identities if isinstance(identities, dict) else {}
    schema_identities = indicators.get("schema_identities")
    if isinstance(schema_identities, dict):
        schema_identity = schema_identities.get(payload.get("schema_id"))
        if isinstance(schema_identity, str):
            identity = identities.get(schema_identity)
            if isinstance(identity, dict) and identity.get("not_contract") is True:
                return f"schema_id:{payload.get('schema_id')}"
    identity_fields = indicators.get("identity_fields")
    if isinstance(identity_fields, list):
        for field in identity_fields:
            if not isinstance(field, str):
                continue
            raw_identity = payload.get(field)
            if not isinstance(raw_identity, str):
                continue
            identity = identities.get(raw_identity)
            if isinstance(identity, dict) and identity.get("not_contract") is True:
                return f"{field}:{raw_identity}"
    process_flags = indicators.get("process_flags")
    if isinstance(process_flags, list):
        for flag in process_flags:
            if isinstance(flag, str) and payload.get(flag) is True:
                return f"{flag}:true"
    return None


def scan_process_artifacts(root: pathlib.Path, policy: dict[str, Any]) -> list[str]:
    patterns = policy["process_artifact_patterns"]
    found: list[str] = []
    for forbidden_root in policy["forbidden_roots"]:
        directory = root / forbidden_root
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            reason = None
            if matches_process_artifact(path.name, patterns):
                reason = "filename-pattern"
            semantic_reason = semantic_process_artifact_reason(path, policy)
            if semantic_reason is not None:
                reason = semantic_reason
            if reason is not None:
                found.append(f"{rel(path, root)} ({reason})")
    return sorted(found)


def validate_allowed_roots(root: pathlib.Path, policy: dict[str, Any], failures: list[str]) -> None:
    for kind, roots in policy["allowed_roots"].items():
        if not isinstance(roots, list) or not all(isinstance(item, str) and item for item in roots):
            failures.append(f"allowed_roots.{kind} must be a non-empty string list")
            continue
        for root_rel in roots:
            if not (root / root_rel).exists():
                failures.append(f"allowed process artifact root is missing: {root_rel}")


def check_placement(root: pathlib.Path, policy: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    validate_allowed_roots(root, policy, failures)
    found = scan_process_artifacts(root, policy)
    if found:
        failures.append(
            "process artifacts are forbidden in stable contract roots: "
            + ", ".join(found)
        )
    return {
        "ok": not failures,
        "root": str(root),
        "policy": str(DEFAULT_POLICY),
        "found_in_forbidden_roots": found,
        "failures": failures,
    }


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fixture_policy() -> dict[str, Any]:
    return {
        "schema_id": "redcap-process-artifact-placement-policy",
        "version": 2,
        "artifact_identities": {
            "lifecycle_packet": {
                "meaning": "fixture lifecycle evidence",
                "default_home": "assets/evidence/lifecycle",
                "not_contract": True,
            },
            "prism_request": {
                "meaning": "fixture Prism request",
                "default_home": "assets/evidence/prism/<task-id>/",
                "not_contract": True,
            },
        },
        "forbidden_roots": ["assets/contracts"],
        "process_artifact_patterns": ["*-lifecycle.json", "*-prism-request.json"],
        "semantic_indicators": {
            "schema_identities": {
                "redcap-development-lifecycle-packet": "lifecycle_packet",
                "prism-session-manifest": "prism_request",
                "redcap-executed-check-receipt": "self_development_runtime_artifact",
                "redcap-completion-evidence-packet": "self_development_runtime_artifact",
            },
            "identity_fields": ["artifact_identity", "artifact_kind"],
            "process_flags": ["not_contract", "process_artifact"],
            "scope": "top_level_json_object_only",
        },
        "allowed_roots": {
            "lifecycle_packet": ["assets/evidence/lifecycle"],
            "prism_request": ["assets/evidence/prism"],
            "migration_evidence": ["assets/evidence/migrations"],
        },
        "migration_policy": {
            "legacy_allowlist_allowed": False,
            "reason": "fixture forbids legacy allowlists",
            "completed_migration_map": "assets/evidence/migrations/fixture-map.json",
        },
    }


def create_fixture(root: pathlib.Path) -> None:
    for directory in [
        root / "assets" / "contracts",
        root / "assets" / "evidence" / "lifecycle",
        root / "assets" / "evidence" / "prism",
        root / "assets" / "evidence" / "migrations",
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def cmd_check(args: argparse.Namespace) -> int:
    root = pathlib.Path(args.root).resolve()
    policy_path = pathlib.Path(args.policy).resolve()
    policy = load_policy(policy_path)
    result = check_placement(root, policy)
    result["policy"] = str(policy_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_PROCESS_ARTIFACT_PLACEMENT_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="redcap-process-artifacts-") as tmp_raw:
        root = pathlib.Path(tmp_raw)
        create_fixture(root)
        policy = fixture_policy()
        valid = check_placement(root, policy)
        if not valid["ok"]:
            failures.append(f"empty stable contracts fixture should pass: {valid['failures']}")
        bad_file = root / "assets" / "contracts" / "new-task-lifecycle.json"
        bad_file.write_text("{}", encoding="utf-8")
        bad = check_placement(root, policy)
        if bad["ok"] or not any(item.startswith("assets/contracts/new-task-lifecycle.json") for item in bad["found_in_forbidden_roots"]):
            failures.append(f"new misplaced artifact should fail: {bad}")
        semantic_bad = root / "assets" / "contracts" / "review-packet.json"
        semantic_bad.write_text(json.dumps({
            "schema_id": "redcap-development-lifecycle-packet",
            "task_id": "fixture",
        }), encoding="utf-8")
        semantic = check_placement(root, policy)
        if semantic["ok"] or not any(item.startswith("assets/contracts/review-packet.json") for item in semantic["found_in_forbidden_roots"]):
            failures.append(f"semantic process artifact should fail even without a process filename: {semantic}")
        stable_contract = root / "assets" / "contracts" / "stable-contract.json"
        stable_contract.write_text(json.dumps({
            "artifact_identity": "stable_contract",
            "not_contract": False,
        }), encoding="utf-8")
        semantic_bad.unlink()
        stable = check_placement(root, policy)
        if stable["ok"]:
            failures.append("stable contract fixture should still fail while filename-pattern artifact remains")
        good_file = root / "assets" / "evidence" / "lifecycle" / "new-task-lifecycle.json"
        good_file.write_text("{}", encoding="utf-8")
        good_prism = root / "assets" / "evidence" / "prism" / "fixture-task" / "fixture-prism-request.json"
        good_prism.parent.mkdir(parents=True, exist_ok=True)
        good_prism.write_text("{}", encoding="utf-8")
        bad_file.unlink()
        good = check_placement(root, policy)
        if not good["ok"]:
            failures.append(f"process artifacts in evidence roots should pass: {good['failures']}")
        eroded = dict(policy)
        eroded["legacy_allowlist"] = {"tracked": ["assets/contracts/legacy-lifecycle.json"], "untracked": []}
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
                json.dump(eroded, handle)
                eroded_path = pathlib.Path(handle.name)
            try:
                load_policy(eroded_path)
            except SystemExit as exc:
                if "legacy_allowlist" not in str(exc):
                    failures.append(f"legacy allowlist erosion returned wrong error: {exc}")
            else:
                failures.append("legacy allowlist erosion should fail")
        finally:
            eroded_path.unlink(missing_ok=True)
    result = {
        "ok": not failures,
        "negative_cases": [
            "new process artifact in assets/contracts fails",
            "semantic process artifact in assets/contracts fails even when the filename is contract-like",
            "stable contract identity is not treated as a process artifact",
            "same artifact in assets/evidence/lifecycle passes",
            "same artifact in assets/evidence/prism/<task-id> passes",
            "legacy_allowlist policy erosion fails",
        ],
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_PROCESS_ARTIFACT_PLACEMENT_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify RedCap process artifact placement")
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

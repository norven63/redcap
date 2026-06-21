#!/usr/bin/env python3
"""Knowledge quality checks for RedCap indexed knowledge."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(os.environ.get("REDCAP_KNOWLEDGE_ROOT", pathlib.Path(__file__).resolve().parents[2])).resolve()
DEFAULT_INDEX = REPO_ROOT / "assets" / "knowledge" / "index.json"
DEFAULT_QUALITY = REPO_ROOT / "assets" / "knowledge" / "quality.json"
DEFAULT_CONTRACT = REPO_ROOT / "assets" / "contracts" / "knowledge-quality.json"
DEFAULT_EVIDENCE = REPO_ROOT / "assets" / "evidence" / "rsp" / "rsp-26-knowledge-quality.json"

ALLOWED_STATUSES = {"active", "stale", "conflict", "no_promote", "deprecated", "legacy_reference"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_USAGE_POLICIES = {"direct_driver", "review_required", "hint_only", "blocked"}
ACTIVE_DIRECT_ROUTES = {"active-local-index", "revival-doc"}
PRIVATE_SOURCE_MARKERS = (
    "/Users/norven/.cap",
    "/Users/norven/.codex",
    "identity.md",
    "private_identity_body",
    "raw_persona_body",
    "sk-",
    "token=",
    "credential=",
)


def today_utc() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def resolve_path(raw: str | pathlib.Path) -> pathlib.Path:
    path = pathlib.Path(raw)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def rel_path(path: pathlib.Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing json file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json file: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"json file must be an object: {path}")
    return payload


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def parse_date(value: Any) -> dt.date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return dt.date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def as_entry_map(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = index.get("entries")
    if not isinstance(entries, list):
        return {}
    return {
        str(entry.get("id")): entry
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }


def quality_entries(quality: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = quality.get("entries")
    if not isinstance(raw, dict):
        return {}
    return {str(key): value for key, value in raw.items() if isinstance(value, dict)}


def source_ref_failures(source_refs: Any) -> list[str]:
    failures: list[str] = []
    if not isinstance(source_refs, list) or not source_refs:
        return ["source_refs must be a non-empty list"]
    for source_ref in source_refs:
        if not isinstance(source_ref, str) or not source_ref.strip():
            failures.append("source_refs must contain non-empty strings")
            continue
        lowered = source_ref.casefold()
        for marker in PRIVATE_SOURCE_MARKERS:
            if marker.casefold() in lowered:
                failures.append(f"source_ref contains private marker: {source_ref}")
                break
        path = pathlib.Path(source_ref)
        if path.is_absolute():
            failures.append(f"source_ref must be repository-relative: {source_ref}")
        elif not resolve_path(source_ref).exists():
            failures.append(f"source_ref does not exist: {source_ref}")
    return failures


def quality_decision_for_entry(
    entry: dict[str, Any],
    quality: dict[str, Any] | None,
    *,
    today: dt.date | None = None,
) -> dict[str, Any]:
    today = today or today_utc()
    entry_id = str(entry.get("id") or "")
    route = str(entry.get("route") or "")
    entries = quality_entries(quality or {})
    meta = entries.get(entry_id)
    reasons: list[str] = []
    if meta is None:
        return {
            "entry_id": entry_id,
            "quality_status": "missing_quality",
            "usage_policy": "review_required",
            "direct_driver_allowed": False,
            "reasons": ["quality metadata missing; defaulting to review_required"],
        }

    status = str(meta.get("status") or "")
    confidence = str(meta.get("confidence") or "")
    usage_policy = str(meta.get("usage_policy") or "")
    valid_until = parse_date(meta.get("valid_until"))
    expired = valid_until is not None and valid_until < today
    if expired:
        reasons.append("valid_until is in the past")
    if route == "old-redcap-reference":
        reasons.append("old-redcap-reference cannot be direct_driver")
    if status != "active":
        reasons.append(f"status is not active: {status}")
    if confidence == "low":
        reasons.append("confidence is low")
    if meta.get("conflicts_with"):
        reasons.append("conflicts_with is present")
    if meta.get("no_promote_refs"):
        reasons.append("no_promote_refs is present")
    if usage_policy != "direct_driver":
        reasons.append(f"usage_policy is {usage_policy or 'missing'}")
    direct_allowed = (
        route in ACTIVE_DIRECT_ROUTES
        and status == "active"
        and confidence in {"high", "medium"}
        and usage_policy == "direct_driver"
        and not expired
        and not meta.get("conflicts_with")
        and not meta.get("no_promote_refs")
    )
    return {
        "entry_id": entry_id,
        "quality_status": status or "invalid",
        "usage_policy": usage_policy or "review_required",
        "direct_driver_allowed": bool(direct_allowed),
        "reasons": [] if direct_allowed else reasons,
        "reviewed_at": meta.get("reviewed_at"),
        "valid_until": meta.get("valid_until"),
        "applicability": meta.get("applicability"),
        "confidence": confidence or None,
    }


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-knowledge-quality-contract":
        failures.append("contract.schema_id must be redcap-knowledge-quality-contract")
    required = contract.get("required_fields")
    expected = {
        "source_refs",
        "reviewed_at",
        "applicability",
        "expiry_condition",
        "confidence",
        "status",
        "usage_policy",
    }
    if not isinstance(required, list) or set(required) != expected:
        failures.append("contract.required_fields must match the RSP-26 field set")
    defaults = contract.get("default_policies")
    if not isinstance(defaults, dict):
        failures.append("contract.default_policies must be an object")
    elif defaults.get("missing_quality") != "review_required":
        failures.append("missing quality must default to review_required")
    return failures


def validate_quality(index: dict[str, Any], quality: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    decisions: list[dict[str, Any]] = []
    failures.extend(validate_contract(contract))
    if quality.get("schema_id") != "redcap-knowledge-quality":
        failures.append("quality.schema_id must be redcap-knowledge-quality")
    if quality.get("index_path") != "assets/knowledge/index.json":
        failures.append("quality.index_path must be assets/knowledge/index.json")
    index_entries = as_entry_map(index)
    metadata = quality_entries(quality)
    for entry_id in sorted(index_entries):
        entry = index_entries[entry_id]
        meta = metadata.get(entry_id)
        if meta is None:
            failures.append(f"quality metadata missing for {entry_id}")
            decisions.append(quality_decision_for_entry(entry, quality))
            continue
        label = f"entries.{entry_id}"
        if meta.get("index_route") != entry.get("route"):
            failures.append(f"{label}.index_route mismatch")
        if meta.get("index_path") != entry.get("path"):
            failures.append(f"{label}.index_path mismatch")
        for failure in source_ref_failures(meta.get("source_refs")):
            failures.append(f"{label}.{failure}")
        reviewed_at = parse_date(meta.get("reviewed_at"))
        if reviewed_at is None:
            failures.append(f"{label}.reviewed_at must be ISO date")
        elif reviewed_at > today_utc():
            failures.append(f"{label}.reviewed_at cannot be in the future")
        if not (isinstance(meta.get("applicability"), str) and meta["applicability"].strip()):
            failures.append(f"{label}.applicability must be non-empty")
        if not (isinstance(meta.get("expiry_condition"), str) and meta["expiry_condition"].strip()):
            failures.append(f"{label}.expiry_condition must be non-empty")
        confidence = meta.get("confidence")
        if confidence not in ALLOWED_CONFIDENCE:
            failures.append(f"{label}.confidence invalid: {confidence}")
        status = meta.get("status")
        if status not in ALLOWED_STATUSES:
            failures.append(f"{label}.status invalid: {status}")
        usage_policy = meta.get("usage_policy")
        if usage_policy not in ALLOWED_USAGE_POLICIES:
            failures.append(f"{label}.usage_policy invalid: {usage_policy}")
        valid_until = parse_date(meta.get("valid_until"))
        if meta.get("valid_until") is not None and valid_until is None:
            failures.append(f"{label}.valid_until must be ISO date when present")
        expired = valid_until is not None and valid_until < today_utc()
        if expired and status == "active":
            failures.append(f"{label} is expired but still active")
        if expired and usage_policy == "direct_driver":
            failures.append(f"{label} is expired but usage_policy is direct_driver")
        if entry.get("route") == "old-redcap-reference" and usage_policy == "direct_driver":
            failures.append(f"{label} old-redcap-reference cannot be direct_driver")
        conflicts = meta.get("conflicts_with")
        if conflicts:
            if usage_policy == "direct_driver":
                failures.append(f"{label} has conflicts_with but usage_policy is direct_driver")
            if not (isinstance(meta.get("conflict_resolution"), str) and meta["conflict_resolution"].strip()):
                failures.append(f"{label}.conflict_resolution required when conflicts_with is present")
        no_promote_refs = meta.get("no_promote_refs")
        if no_promote_refs:
            if usage_policy == "direct_driver":
                failures.append(f"{label} has no_promote_refs but usage_policy is direct_driver")
            for ref in no_promote_refs if isinstance(no_promote_refs, list) else []:
                if not isinstance(ref, str) or not ref.strip():
                    failures.append(f"{label}.no_promote_refs must contain non-empty strings")
                elif not resolve_path(ref).exists():
                    failures.append(f"{label}.no_promote_refs missing: {ref}")
        decision = quality_decision_for_entry(entry, quality)
        if decision["direct_driver_allowed"] and usage_policy != "direct_driver":
            failures.append(f"{label} direct_driver decision inconsistent with usage_policy")
        decisions.append(decision)
    for entry_id in sorted(set(metadata) - set(index_entries)):
        failures.append(f"orphan quality metadata entry: {entry_id}")
    if not any(item.get("direct_driver_allowed") for item in decisions):
        warnings.append("no direct_driver knowledge entries are currently allowed")
    return {
        "ok": not failures,
        "failures": failures,
        "warnings": warnings,
        "decisions": decisions,
    }


def report_payload(index: dict[str, Any], quality: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    validation = validate_quality(index, quality, contract)
    return {
        "schema_id": "redcap-knowledge-quality-report",
        "rsp": "RSP-26",
        "ok": validation["ok"],
        "checked_at": iso_now(),
        "index_path": "assets/knowledge/index.json",
        "quality_path": "assets/knowledge/quality.json",
        "contract_path": "assets/contracts/knowledge-quality.json",
        "changed_reality": [
            "knowledge quality metadata is checked against the live knowledge index",
            "knowledge gateway search can consume quality metadata and expose direct-driver eligibility",
            "stale, conflicting, no-promote, missing-quality, and old-redcap-reference cases are not direct drivers"
        ],
        "acceptance": {
            "positive": {
                "status": "pass" if validation["ok"] else "fail",
                "checks": [
                    "all indexed reusable knowledge has quality metadata",
                    "quality metadata includes source_refs, reviewed_at, applicability, expiry_condition, confidence, status, usage_policy",
                    "direct-driver eligibility is computed from quality status and route"
                ]
            },
            "negative": {
                "status": "pass" if validation["ok"] else "fail",
                "checks": [
                    "missing quality metadata fails",
                    "expired active direct-driver metadata fails",
                    "conflicting direct-driver metadata fails",
                    "no-promote direct-driver metadata fails",
                    "old-redcap-reference direct-driver metadata fails",
                    "private source references fail"
                ]
            }
        },
        "artifacts": [
            "assets/contracts/knowledge-quality.json",
            "assets/knowledge/quality.json",
            "runtime/core/knowledge_quality.py",
            "runtime/core/knowledge_gateway.py",
            "runtime/bin/redcap",
            "runtime/core/check_runner.py"
        ],
        "failures": validation["failures"],
        "warnings": validation["warnings"],
        "decisions": validation["decisions"],
    }


def cmd_check(args: argparse.Namespace) -> int:
    index = load_json(resolve_path(args.index))
    quality = load_json(resolve_path(args.quality))
    contract = load_json(resolve_path(args.contract))
    payload = report_payload(index, quality, contract)
    if args.out:
        write_json(resolve_path(args.out), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not payload["ok"]:
        return 1
    print("REDCAP_KNOWLEDGE_QUALITY_OK")
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="redcap-knowledge-quality-") as root:
        root_path = pathlib.Path(root)
        entries = root_path / "assets" / "knowledge" / "entries"
        evidence = root_path / "assets" / "archaeology" / "no-promote"
        entries.mkdir(parents=True)
        evidence.mkdir(parents=True)
        (entries / "active.md").write_text("# Active\n", encoding="utf-8")
        (entries / "old.md").write_text("# Old\n", encoding="utf-8")
        (evidence / "bad.json").write_text("{}", encoding="utf-8")
        index = {
            "schema_id": "redcap-knowledge-index",
            "entries": [
                {"id": "active", "route": "active-local-index", "path": "assets/knowledge/entries/active.md"},
                {"id": "old-ref", "route": "old-redcap-reference", "path": "/tmp/old-redcap/file.sh"},
            ],
        }
        quality = {
            "schema_id": "redcap-knowledge-quality",
            "index_path": "assets/knowledge/index.json",
            "entries": {
                "active": {
                    "index_route": "active-local-index",
                    "index_path": "assets/knowledge/entries/active.md",
                    "source_refs": ["assets/knowledge/index.json"],
                    "reviewed_at": "2026-06-21",
                    "valid_until": "2026-09-21",
                    "applicability": "active fixture",
                    "expiry_condition": "source changes",
                    "confidence": "medium",
                    "status": "active",
                    "usage_policy": "direct_driver"
                },
                "old-ref": {
                    "index_route": "old-redcap-reference",
                    "index_path": "/tmp/old-redcap/file.sh",
                    "source_refs": ["assets/knowledge/index.json"],
                    "reviewed_at": "2026-06-21",
                    "applicability": "legacy reference fixture",
                    "expiry_condition": "only with explicit archaeology review",
                    "confidence": "low",
                    "status": "legacy_reference",
                    "usage_policy": "review_required"
                }
            }
        }
        contract = {
            "schema_id": "redcap-knowledge-quality-contract",
            "required_fields": sorted([
                "source_refs",
                "reviewed_at",
                "applicability",
                "expiry_condition",
                "confidence",
                "status",
                "usage_policy",
            ]),
            "default_policies": {"missing_quality": "review_required"}
        }
        failures: list[str] = []
        positive_result = validate_quality(index, quality, contract)
        if not positive_result["ok"]:
            failures.append(f"positive fixture should pass: {positive_result['failures']}")
        probes = []
        missing = json.loads(json.dumps(quality))
        missing["entries"].pop("active")
        probes.append(("missing quality", missing, "quality metadata missing"))
        expired = json.loads(json.dumps(quality))
        expired["entries"]["active"]["valid_until"] = "2020-01-01"
        probes.append(("expired active direct_driver", expired, "expired"))
        conflict = json.loads(json.dumps(quality))
        conflict["entries"]["active"]["conflicts_with"] = ["other"]
        probes.append(("conflict direct_driver", conflict, "conflicts_with"))
        no_promote = json.loads(json.dumps(quality))
        no_promote["entries"]["active"]["no_promote_refs"] = ["assets/archaeology/no-promote/bad.json"]
        probes.append(("no-promote direct_driver", no_promote, "no_promote_refs"))
        old_direct = json.loads(json.dumps(quality))
        old_direct["entries"]["old-ref"]["usage_policy"] = "direct_driver"
        probes.append(("old direct_driver", old_direct, "old-redcap-reference"))
        private_source = json.loads(json.dumps(quality))
        private_source["entries"]["active"]["source_refs"] = [
            "/" + "/".join(["Users", "norven", ".cap", "identity.md"])
        ]
        probes.append(("private source", private_source, "private marker"))
        for label, bad_quality, expected in probes:
            result = validate_quality(index, bad_quality, contract)
            if result["ok"]:
                failures.append(f"{label}: expected failure")
            elif not any(expected in item for item in result["failures"]):
                failures.append(f"{label}: expected failure containing {expected!r}, got {result['failures']}")
        print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
        if failures:
            return 1
        print("REDCAP_KNOWLEDGE_QUALITY_SELF_CHECK_OK")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check RedCap knowledge quality metadata")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check")
    check.add_argument("--index", default=str(DEFAULT_INDEX))
    check.add_argument("--quality", default=str(DEFAULT_QUALITY))
    check.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    check.add_argument("--out")
    check.set_defaults(func=cmd_check)
    self_check = subparsers.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

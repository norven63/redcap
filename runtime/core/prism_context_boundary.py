#!/usr/bin/env python3
"""验证 Prism 通信上下文边界，防止 raw 大输出进入 Cap 主上下文。"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import pathlib
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = REPO_ROOT / "assets" / "contracts" / "prism-context-boundary.json"
DEFAULT_MANIFEST = REPO_ROOT / "assets" / "evidence" / "rsp" / "rsp-04-context-consumption.json"
CONTRACT_SCHEMA_ID = "redcap-prism-context-boundary-contract"
MANIFEST_SCHEMA_ID = "redcap-prism-context-consumption"
REPORT_SCHEMA_ID = "redcap-prism-context-boundary-report"
SELF_CHECK_SCHEMA_ID = "redcap-prism-context-boundary-self-check"
CAP_PAYLOAD_SCHEMA_ID = "redcap-cap-context-payload"
CAP_CONSUME_SCHEMA_ID = "redcap-cap-context-consume"
DEFAULT_CAP_INPUT = REPO_ROOT / "assets" / "evidence" / "rsp" / "rsp-04-cap-context" / "cap-loader-output.json"


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}") from exc


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def rel(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def resolve_repo_path(value: str) -> pathlib.Path:
    path = pathlib.Path(value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != CONTRACT_SCHEMA_ID:
        failures.append(f"contract.schema_id must be {CONTRACT_SCHEMA_ID}")
    budget = contract.get("cap_context_budget")
    if not isinstance(budget, dict):
        failures.append("cap_context_budget missing")
        budget = {}
    for key in ["max_total_bytes", "max_structured_review_bytes", "max_brief_excerpt_bytes", "max_manifest_bytes"]:
        value = budget.get(key)
        if not isinstance(value, int) or value < 1:
            failures.append(f"cap_context_budget.{key} must be a positive integer")
    if budget.get("max_total_bytes", 0) > 8192:
        failures.append("cap_context_budget.max_total_bytes must not exceed 8192")
    for key in ["forbidden_cap_path_suffixes", "forbidden_cap_text_markers"]:
        if not isinstance(budget.get(key), list) or not budget.get(key):
            failures.append(f"cap_context_budget.{key} must be a non-empty list")
    required = contract.get("request_file_access_required")
    if not isinstance(required, dict):
        failures.append("request_file_access_required missing")
        required = {}
    if required.get("mode") != "bounded-read":
        failures.append("request_file_access_required.mode must be bounded-read")
    fields = required.get("fields")
    if not isinstance(fields, list) or not fields:
        failures.append("request_file_access_required.fields must be a non-empty list")
    if set(contract.get("provider_artifact_layers", [])) != {"raw", "brief", "structured_review"}:
        failures.append("provider_artifact_layers must be raw, brief, structured_review")
    raw_policy = contract.get("raw_access_policy")
    if not isinstance(raw_policy, dict):
        failures.append("raw_access_policy missing")
        raw_policy = {}
    if raw_policy.get("cap_context") != "forbidden":
        failures.append("raw_access_policy.cap_context must be forbidden")
    if raw_policy.get("checker_access") != "stat-only":
        failures.append("raw_access_policy.checker_access must be stat-only")
    if raw_policy.get("audit_replay") != "path-and-hash-only":
        failures.append("raw_access_policy.audit_replay must be path-and-hash-only")
    required_fixtures = {
        "raw-in-cap",
        "brief-over-limit",
        "raw-in-brief",
        "unbounded-manifest",
        "self-check-recursion",
        "file-access-boundary-mismatch",
        "raw-read-full-content-checker",
        "cap-input-unlisted-file",
        "cap-input-extra-content",
        "cap-input-stale-manifest",
    }
    fixtures = set(contract.get("negative_fixtures", []))
    missing = sorted(required_fixtures - fixtures)
    if missing:
        failures.append(f"negative_fixtures missing: {missing}")
    return failures


def request_file_access_failures(request: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    required = contract.get("request_file_access_required", {})
    file_access = request.get("file_access")
    if not isinstance(file_access, dict):
        return ["request.file_access missing"]
    if file_access.get("mode") != required.get("mode"):
        failures.append("request.file_access.mode must be bounded-read")
    for field in required.get("fields", []):
        if field not in file_access:
            failures.append(f"request.file_access.{field} missing")
    if not isinstance(file_access.get("paths"), list) or not file_access.get("paths"):
        failures.append("request.file_access.paths must be a non-empty list")
    for field in ["max_files", "max_bytes_per_file", "max_total_bytes"]:
        if not isinstance(file_access.get(field), int) or file_access.get(field) < 1:
            failures.append(f"request.file_access.{field} must be a positive integer")
    if not isinstance(file_access.get("purpose"), str) or len(file_access.get("purpose", "")) < 12:
        failures.append("request.file_access.purpose must be substantive")
    return failures


def load_cap_context(manifest: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    budget = contract.get("cap_context_budget", {})
    cap_payload = manifest.get("cap_bound_payload")
    if not isinstance(cap_payload, dict):
        return {"ok": False, "failures": ["cap_bound_payload missing"], "files": []}
    files = cap_payload.get("files")
    if not isinstance(files, list) or not files:
        return {"ok": False, "failures": ["cap_bound_payload.files must be non-empty"], "files": []}
    total_bytes = 0
    loaded: list[dict[str, Any]] = []
    forbidden_suffixes = tuple(budget.get("forbidden_cap_path_suffixes", []))
    forbidden_markers = [str(item) for item in budget.get("forbidden_cap_text_markers", [])]
    manifest_path = manifest.get("manifest_path")
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            failures.append(f"cap_bound_payload.files[{index}] must be object")
            continue
        role = item.get("role")
        value = item.get("path")
        if not isinstance(value, str) or not value:
            failures.append(f"cap_bound_payload.files[{index}].path missing")
            continue
        if manifest_path and value == manifest_path:
            failures.append("cap_bound_payload must not include its own manifest")
        if value.endswith(forbidden_suffixes):
            failures.append(f"cap_bound_payload references forbidden raw path: {value}")
            continue
        path = resolve_repo_path(value)
        if not path.exists():
            failures.append(f"cap_bound_payload file missing: {value}")
            continue
        size = path.stat().st_size
        if role == "structured_review" and size > budget.get("max_structured_review_bytes", 0):
            failures.append(f"structured review exceeds budget: {value}")
        if role in {"brief", "brief_excerpt"} and size > budget.get("max_brief_excerpt_bytes", 0):
            failures.append(f"brief excerpt exceeds budget: {value}")
        total_bytes += size
        text = path.read_text(encoding="utf-8")
        for marker in forbidden_markers:
            if marker and marker in text:
                failures.append(f"cap_bound_payload file contains forbidden marker {marker}: {value}")
        loaded.append({"path": value, "role": role, "bytes": size, "sha256": sha256_file(path)})
    if total_bytes > budget.get("max_total_bytes", 0):
        failures.append(f"cap_bound_payload total bytes exceed budget: {total_bytes}")
    return {"ok": not failures, "failures": failures, "files": loaded, "total_bytes": total_bytes}


def validate_cap_input(
    payload: dict[str, Any],
    *,
    expected_report: dict[str, Any],
    manifest_path: pathlib.Path,
    contract_path: pathlib.Path,
) -> list[str]:
    """校验真正进入 Cap 主上下文的输入包只能来自 cap-load 输出。"""
    failures: list[str] = []
    allowed_top_keys = {
        "schema_id",
        "source_manifest",
        "source_manifest_sha256",
        "contract",
        "contract_sha256",
        "files",
        "total_bytes",
    }
    extra_top_keys = sorted(set(payload) - allowed_top_keys)
    if extra_top_keys:
        failures.append(f"cap input contains unexpected top-level keys: {extra_top_keys}")
    if payload.get("schema_id") != CAP_PAYLOAD_SCHEMA_ID:
        failures.append(f"cap input schema_id must be {CAP_PAYLOAD_SCHEMA_ID}")
    if payload.get("source_manifest") != rel(manifest_path):
        failures.append("cap input source_manifest does not match checked manifest")
    if payload.get("source_manifest_sha256") != sha256_file(manifest_path):
        failures.append("cap input source_manifest_sha256 is stale or missing")
    if payload.get("contract") != rel(contract_path):
        failures.append("cap input contract does not match checked contract")
    if payload.get("contract_sha256") != sha256_file(contract_path):
        failures.append("cap input contract_sha256 is stale or missing")

    expected_files = expected_report.get("cap_context_files")
    if not isinstance(expected_files, list) or not expected_files:
        failures.append("expected report has no cap_context_files")
        expected_files = []
    actual_files = payload.get("files")
    if not isinstance(actual_files, list) or not actual_files:
        failures.append("cap input files must be a non-empty list")
        actual_files = []
    allowed_file_keys = {"path", "role", "bytes", "sha256"}
    for index, item in enumerate(actual_files):
        if not isinstance(item, dict):
            failures.append(f"cap input files[{index}] must be object")
            continue
        extra_keys = sorted(set(item) - allowed_file_keys)
        if extra_keys:
            failures.append(f"cap input files[{index}] contains unexpected keys: {extra_keys}")
    if actual_files != expected_files:
        failures.append("cap input files do not exactly match cap-load manifest output")
    if payload.get("total_bytes") != expected_report.get("cap_context_total_bytes"):
        failures.append("cap input total_bytes does not match checked manifest")
    return failures


def validate_manifest(manifest: dict[str, Any], contract: dict[str, Any], *, manifest_path: pathlib.Path) -> list[str]:
    failures: list[str] = []
    if manifest.get("schema_id") != MANIFEST_SCHEMA_ID:
        failures.append(f"manifest.schema_id must be {MANIFEST_SCHEMA_ID}")
    if manifest_path.stat().st_size > contract.get("cap_context_budget", {}).get("max_manifest_bytes", 0):
        failures.append("manifest file exceeds max_manifest_bytes")
    if manifest.get("checker_raw_access_mode") != "stat-only":
        failures.append("checker_raw_access_mode must be stat-only")
    source_request = manifest.get("source_request")
    if not isinstance(source_request, str):
        failures.append("source_request missing")
    else:
        request_path = resolve_repo_path(source_request)
        if not request_path.exists():
            failures.append("source_request does not exist")
        else:
            request = load_json(request_path)
            if isinstance(request, dict):
                failures.extend(request_file_access_failures(request, contract))
            else:
                failures.append("source_request must be JSON object")
    providers = manifest.get("providers")
    if not isinstance(providers, list) or not providers:
        failures.append("providers must be a non-empty list")
        providers = []
    for index, provider in enumerate(providers):
        if not isinstance(provider, dict):
            failures.append(f"providers[{index}] must be object")
            continue
        for key in ["raw_path", "brief_path", "structured_review_path"]:
            value = provider.get(key)
            if not isinstance(value, str) or not value:
                failures.append(f"providers[{index}].{key} missing")
                continue
            path = resolve_repo_path(value)
            if not path.exists():
                failures.append(f"providers[{index}].{key} missing file: {value}")
        raw_path_value = provider.get("raw_path")
        if isinstance(raw_path_value, str):
            raw_path = resolve_repo_path(raw_path_value)
            if raw_path.exists() and not raw_path_value.endswith((".raw.txt", ".raw.json")):
                failures.append(f"providers[{index}].raw_path must be raw artifact")
            provider["raw_size_bytes_observed_by_stat"] = raw_path.stat().st_size if raw_path.exists() else None
        raw_meta_value = provider.get("raw_meta_path")
        if isinstance(raw_meta_value, str):
            raw_meta = resolve_repo_path(raw_meta_value)
            if not raw_meta.exists():
                failures.append(f"providers[{index}].raw_meta_path missing file: {raw_meta_value}")
            else:
                raw_meta_payload = load_json(raw_meta)
                if isinstance(raw_meta_payload, dict) and raw_meta_payload.get("raw_path"):
                    provider.setdefault("audit_replay_raw_sha256", raw_meta_payload.get("raw_sha256"))
    audit = manifest.get("audit_replay")
    if not isinstance(audit, dict):
        failures.append("audit_replay missing")
    else:
        raw_files = audit.get("raw_files")
        if not isinstance(raw_files, list) or not raw_files:
            failures.append("audit_replay.raw_files must be non-empty")
        else:
            for value in raw_files:
                if not isinstance(value, str):
                    failures.append("audit_replay.raw_files must contain strings")
                    continue
                path = resolve_repo_path(value)
                if not path.exists():
                    failures.append(f"audit_replay raw file missing: {value}")
    cap_context = load_cap_context(manifest, contract)
    failures.extend(cap_context["failures"])
    return failures


def fixture_manifest(base: dict[str, Any], fixture: str) -> dict[str, Any]:
    manifest = copy.deepcopy(base)
    files = manifest.setdefault("cap_bound_payload", {}).setdefault("files", [])
    providers = manifest.get("providers") if isinstance(manifest.get("providers"), list) else []
    raw_path = providers[0].get("raw_path") if providers and isinstance(providers[0], dict) else "fixture.raw.txt"
    if fixture == "healthy":
        return manifest
    if fixture == "raw-in-cap":
        files.append({"role": "raw", "path": raw_path})
        return manifest
    if fixture == "brief-over-limit":
        manifest.setdefault("contract_overrides", {})["max_brief_excerpt_bytes"] = 1
        return manifest
    if fixture == "raw-in-brief":
        files.append({"role": "brief_excerpt", "path": "assets/evidence/rsp/rsp-04-fixtures/raw-in-brief.md"})
        return manifest
    if fixture == "unbounded-manifest":
        manifest.setdefault("contract_overrides", {})["max_manifest_bytes"] = 1
        return manifest
    if fixture == "self-check-recursion":
        files.append({"role": "structured_review", "path": manifest.get("manifest_path", "manifest.json")})
        return manifest
    if fixture == "file-access-boundary-mismatch":
        manifest["source_request"] = "assets/evidence/rsp/rsp-04-fixtures/request-without-file-access.json"
        return manifest
    if fixture == "raw-read-full-content-checker":
        manifest["checker_raw_access_mode"] = "full-read"
        return manifest
    raise SystemExit(f"unsupported fixture: {fixture}")


def fixture_cap_input(base: dict[str, Any], fixture: str) -> dict[str, Any]:
    payload = copy.deepcopy(base)
    if fixture == "healthy":
        return payload
    if fixture == "cap-input-unlisted-file":
        payload.setdefault("files", []).append({
            "role": "structured_review",
            "path": "assets/evidence/rsp/unlisted-context.json",
            "bytes": 1,
            "sha256": "0" * 64,
        })
        return payload
    if fixture == "cap-input-extra-content":
        payload["inline_content"] = "这段正文模拟绕过 cap-load 清单直接塞入 Cap 上下文。"
        return payload
    if fixture == "cap-input-stale-manifest":
        payload["source_manifest_sha256"] = "0" * 64
        return payload
    raise SystemExit(f"unsupported cap input fixture: {fixture}")


def apply_contract_overrides(contract: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(contract)
    overrides = manifest.get("contract_overrides")
    if isinstance(overrides, dict):
        budget = result.setdefault("cap_context_budget", {})
        for key, value in overrides.items():
            if key in budget:
                budget[key] = value
    return result


def compute_report(contract: dict[str, Any], manifest: dict[str, Any], *, manifest_path: pathlib.Path) -> dict[str, Any]:
    effective_contract = apply_contract_overrides(contract, manifest)
    contract_failures = validate_contract(effective_contract)
    manifest_failures = validate_manifest(manifest, effective_contract, manifest_path=manifest_path)
    cap_context = load_cap_context(manifest, effective_contract)
    return {
        "schema_id": REPORT_SCHEMA_ID,
        "ok": not contract_failures and not manifest_failures,
        "contract": rel(DEFAULT_CONTRACT),
        "manifest": rel(manifest_path),
        "cap_context_total_bytes": cap_context.get("total_bytes"),
        "cap_context_files": cap_context.get("files"),
        "raw_access_mode": manifest.get("checker_raw_access_mode"),
        "failures": contract_failures + manifest_failures,
    }


def cmd_check(args: argparse.Namespace) -> int:
    contract = load_json(resolve_repo_path(args.contract))
    manifest_path = resolve_repo_path(args.manifest)
    manifest = load_json(manifest_path)
    if args.fixture != "healthy":
        manifest = fixture_manifest(manifest, args.fixture)
    report = compute_report(contract, manifest, manifest_path=manifest_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["ok"]:
        print("REDCAP_PRISM_CONTEXT_BOUNDARY_OK")
        return 0
    return 1


def cmd_self_check(args: argparse.Namespace) -> int:
    fixtures = [
        ("healthy", True),
        ("raw-in-cap", False),
        ("brief-over-limit", False),
        ("raw-in-brief", False),
        ("unbounded-manifest", False),
        ("self-check-recursion", False),
        ("file-access-boundary-mismatch", False),
        ("raw-read-full-content-checker", False),
    ]
    failures: list[str] = []
    cases: list[dict[str, Any]] = []
    contract = load_json(resolve_repo_path(args.contract))
    manifest_path = resolve_repo_path(args.manifest)
    manifest = load_json(manifest_path)
    for fixture, expected_ok in fixtures:
        report = compute_report(contract, fixture_manifest(manifest, fixture), manifest_path=manifest_path)
        ok = report["ok"]
        cases.append({"fixture": fixture, "ok": ok, "expected_ok": expected_ok, "failures": report["failures"]})
        if ok is not expected_ok:
            failures.append(f"fixture {fixture} expected ok={expected_ok}, got {ok}")
    cap_report = compute_report(contract, manifest, manifest_path=manifest_path)
    if cap_report["ok"]:
        healthy_payload = {
            "schema_id": CAP_PAYLOAD_SCHEMA_ID,
            "source_manifest": rel(manifest_path),
            "source_manifest_sha256": sha256_file(manifest_path),
            "contract": rel(resolve_repo_path(args.contract)),
            "contract_sha256": sha256_file(resolve_repo_path(args.contract)),
            "files": cap_report["cap_context_files"],
            "total_bytes": cap_report["cap_context_total_bytes"],
        }
        for fixture, expected_ok in [
            ("healthy", True),
            ("cap-input-unlisted-file", False),
            ("cap-input-extra-content", False),
            ("cap-input-stale-manifest", False),
        ]:
            payload = fixture_cap_input(healthy_payload, fixture)
            cap_failures = validate_cap_input(
                payload,
                expected_report=cap_report,
                manifest_path=manifest_path,
                contract_path=resolve_repo_path(args.contract),
            )
            ok = not cap_failures
            cases.append({
                "fixture": fixture,
                "surface": "cap-input",
                "ok": ok,
                "expected_ok": expected_ok,
                "failures": cap_failures,
            })
            if ok is not expected_ok:
                failures.append(f"cap input fixture {fixture} expected ok={expected_ok}, got {ok}")
    else:
        failures.append(f"healthy manifest must pass before cap input fixtures: {cap_report['failures']}")
    payload = {"schema_id": SELF_CHECK_SCHEMA_ID, "ok": not failures, "cases": cases, "failures": failures}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_PRISM_CONTEXT_BOUNDARY_SELF_CHECK_OK")
    return 0


def cmd_cap_load(args: argparse.Namespace) -> int:
    contract = load_json(resolve_repo_path(args.contract))
    manifest_path = resolve_repo_path(args.manifest)
    manifest = load_json(manifest_path)
    report = compute_report(contract, manifest, manifest_path=manifest_path)
    if not report["ok"]:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    if args.out:
        out_path = resolve_repo_path(args.out)
        write_json(out_path, {
            "schema_id": CAP_PAYLOAD_SCHEMA_ID,
            "source_manifest": rel(manifest_path),
            "source_manifest_sha256": sha256_file(manifest_path),
            "contract": rel(resolve_repo_path(args.contract)),
            "contract_sha256": sha256_file(resolve_repo_path(args.contract)),
            "files": report["cap_context_files"],
            "total_bytes": report["cap_context_total_bytes"],
        })
        report["payload_path"] = rel(out_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("REDCAP_PRISM_CONTEXT_CAP_LOAD_OK")
    return 0


def cmd_cap_input_check(args: argparse.Namespace) -> int:
    contract = load_json(resolve_repo_path(args.contract))
    manifest_path = resolve_repo_path(args.manifest)
    manifest = load_json(manifest_path)
    report = compute_report(contract, manifest, manifest_path=manifest_path)
    if not report["ok"]:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    input_path = resolve_repo_path(args.input)
    payload = load_json(input_path)
    if not isinstance(payload, dict):
        raise SystemExit(f"cap input must be JSON object: {input_path}")
    if args.fixture != "healthy":
        payload = fixture_cap_input(payload, args.fixture)
    failures = validate_cap_input(
        payload,
        expected_report=report,
        manifest_path=manifest_path,
        contract_path=resolve_repo_path(args.contract),
    )
    result = {
        "schema_id": "redcap-cap-context-input-check",
        "ok": not failures,
        "input": rel(input_path),
        "manifest": rel(manifest_path),
        "cap_context_total_bytes": report["cap_context_total_bytes"],
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_PRISM_CONTEXT_CAP_INPUT_OK")
    return 0


def cmd_cap_consume(args: argparse.Namespace) -> int:
    contract_path = resolve_repo_path(args.contract)
    contract = load_json(contract_path)
    manifest_path = resolve_repo_path(args.manifest)
    manifest = load_json(manifest_path)
    report = compute_report(contract, manifest, manifest_path=manifest_path)
    if not report["ok"]:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    input_path = resolve_repo_path(args.input)
    payload = load_json(input_path)
    if not isinstance(payload, dict):
        raise SystemExit(f"cap input must be JSON object: {input_path}")
    failures = validate_cap_input(
        payload,
        expected_report=report,
        manifest_path=manifest_path,
        contract_path=contract_path,
    )
    result = {
        "schema_id": CAP_CONSUME_SCHEMA_ID,
        "ok": not failures,
        "ordering_contract": "cap-input-check-before-consume",
        "input": rel(input_path),
        "manifest": rel(manifest_path),
        "files": payload.get("files") if not failures else [],
        "total_bytes": payload.get("total_bytes") if not failures else None,
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_PRISM_CONTEXT_CAP_CONSUME_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查 Prism 通信上下文边界")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ["check", "self-check", "cap-load", "cap-input-check", "cap-consume"]:
        sub = subparsers.add_parser(name)
        sub.add_argument("--contract", default=str(DEFAULT_CONTRACT))
        sub.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
        if name == "check":
            sub.add_argument(
                "--fixture",
                choices=[
                    "healthy",
                    "raw-in-cap",
                    "brief-over-limit",
                    "raw-in-brief",
                    "unbounded-manifest",
                    "self-check-recursion",
                    "file-access-boundary-mismatch",
                    "raw-read-full-content-checker",
                ],
                default="healthy",
            )
        if name == "cap-load":
            sub.add_argument("--out")
        if name in {"cap-input-check", "cap-consume"}:
            sub.add_argument("--input", default=str(DEFAULT_CAP_INPUT))
        if name == "cap-input-check":
            sub.add_argument(
                "--fixture",
                choices=[
                    "healthy",
                    "cap-input-unlisted-file",
                    "cap-input-extra-content",
                    "cap-input-stale-manifest",
                ],
                default="healthy",
            )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check(args)
    if args.command == "self-check":
        return cmd_self_check(args)
    if args.command == "cap-load":
        return cmd_cap_load(args)
    if args.command == "cap-input-check":
        return cmd_cap_input_check(args)
    if args.command == "cap-consume":
        return cmd_cap_consume(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# 用途：发布前阻塞债务脚本；校验资产历史债务与 full LLM-wiki 补全已形成可验收状态。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / "assets/references/pre-release-blocking-debt-completion.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-pre-release-blocking-debt] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be object")
    return payload


def require_list(payload: dict[str, Any], key: str, label: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        fail(f"{label}: {key} must be non-empty list")
    return value


def run_check(command: list[str], label: str) -> str:
    completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode != 0:
        fail(f"{label} failed: {(completed.stderr or completed.stdout).strip()[:1000]}")
    return completed.stdout


def validate_claim_boundary(payload: dict[str, Any]) -> None:
    boundary = payload.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be object")
    for key in ["formal_release_performed", "license_or_registry_changed", "secrets_read", "unrecoverable_deletion_performed"]:
        if boundary.get(key) is not False:
            fail(f"claim_boundary.{key} must be false")
    if "不能声明" not in str(boundary.get("allowed_claim", "")):
        fail("claim_boundary.allowed_claim must explain forbidden claims")


def validate_symlinks(asset: dict[str, Any]) -> None:
    shims = require_list(asset, "compatibility_shims", "asset_historical_debt")
    for row in shims:
        if not isinstance(row, dict):
            fail("compatibility shim rows must be objects")
        raw_path = str(row.get("path", ""))
        if not raw_path:
            fail("compatibility shim path missing")
        path = ROOT / raw_path
        if row.get("disposition") != "preserve-with-proof":
            fail(f"{raw_path}: disposition must be preserve-with-proof")
        if row.get("delete_requires_human_decision") is not True:
            fail(f"{raw_path}: delete_requires_human_decision must be true")
        if not path.is_symlink():
            fail(f"{raw_path}: expected compatibility shim symlink")
        target = os.readlink(path)
        if target != row.get("canonical_target"):
            fail(f"{raw_path}: symlink target mismatch: expected {row.get('canonical_target')}, got {target}")


def validate_prism_runs(asset: dict[str, Any]) -> None:
    runs = asset.get("prism_runs")
    if not isinstance(runs, dict):
        fail("prism_runs disposition missing")
    if runs.get("bulk_delete_allowed") is not False:
        fail("prism runs bulk_delete_allowed must be false")
    if runs.get("formal_run_policy") != "preserve":
        fail("formal_run_policy must be preserve")
    output = run_check(["bash", "prism/tools/prism-runs-lifecycle.sh", "summary"], "prism runs lifecycle summary")
    parsed: dict[str, str] = {}
    for line in output.splitlines():
        for chunk in line.split():
            if "=" in chunk:
                key, value = chunk.split("=", 1)
                parsed[key] = value
    if int(parsed.get("formal-run", "0")) <= 0:
        fail("expected formal prism runs to be preserved and counted")
    if parsed.get("purgeable_acceptance") != "0":
        fail("purgeable acceptance fixtures must be zero before completion")
    if parsed.get("pruneable_local") != "0":
        fail("pruneable local evidence must be zero before completion")
    run_check(["bash", "prism/tools/prism-runs-lifecycle.sh", "check"], "prism runs lifecycle check")


def validate_remaining_root_groups(asset: dict[str, Any]) -> None:
    groups = require_list(asset, "remaining_root_groups", "asset_historical_debt")
    ids = {str(row.get("id")) for row in groups if isinstance(row, dict)}
    for required in ["internal-control-plane", "internal-layer-a", "workspace-state"]:
        if required not in ids:
            fail(f"remaining root group missing: {required}")
    for row in groups:
        if not isinstance(row, dict):
            fail("remaining root group rows must be objects")
        disposition = row.get("disposition")
        if disposition not in {"preserve-with-proof", "workspace-local-excluded-nonhistorical", "blocked-by-human-destructive-decision"}:
            fail(f"{row.get('id')}: invalid disposition {disposition}")
        roots = require_list(row, "roots", str(row.get("id")))
        for raw in roots:
            if str(raw) == ".env":
                continue
            if not (ROOT / str(raw)).exists():
                fail(f"{row.get('id')}: root path missing: {raw}")


def validate_long_term_memory(payload: dict[str, Any]) -> None:
    memory = payload.get("long_term_memory_debt")
    if not isinstance(memory, dict):
        fail("long_term_memory_debt missing")
    if memory.get("status") != "implemented-controlled-local-product":
        fail("long_term_memory_debt status mismatch")
    if memory.get("real_rag_backend_enabled") is not False or memory.get("real_graphrag_backend_enabled") is not False:
        fail("real RAG/GraphRAG backends must remain disabled")
    if memory.get("activation_requires_separate_task") is not True:
        fail("backend activation must require separate task")
    for key in ["full_llm_wiki_policy", "full_llm_wiki_index", "worker", "rag_boundary"]:
        raw = str(memory.get(key, ""))
        if not raw or not (ROOT / raw).exists():
            fail(f"long_term_memory_debt surface missing: {key}={raw}")
    run_check(["bash", "compass/tools/redcap-full-llm-wiki-check.sh"], "full LLM-wiki check")
    run_check(["bash", "compass/tools/redcap-full-llm-wiki-worker.sh", "--check"], "full LLM-wiki worker check")
    run_check(["bash", "compass/tools/redcap-rag-graphrag-boundary-check.sh"], "RAG/GraphRAG boundary check")


def validate_prism(payload: dict[str, Any]) -> None:
    prism = payload.get("prism_scope_review")
    if not isinstance(prism, dict):
        fail("prism_scope_review missing")
    run_id = str(prism.get("run_id", ""))
    if not run_id:
        fail("prism run_id missing")
    for role in ["kimi_reviewer", "claude_risk"]:
        parsed = ROOT / "prism/runs" / run_id / "collect" / role / "parsed.json"
        if not parsed.is_file():
            fail(f"Prism parsed verdict missing: {parsed}")
        payload = load_json(parsed, f"Prism {role}")
        blockers = payload.get("blockers")
        if blockers not in ([], None):
            fail(f"Prism {role} still reports blockers")


def main() -> int:
    payload = load_json(RECEIPT, "pre-release blocking debt receipt")
    if payload.get("version") != 1 or payload.get("receipt_id") != "pre-release-blocking-debt-completion":
        fail("receipt identity mismatch")
    if payload.get("status") not in {"in-progress", "completed"}:
        fail("receipt status must be in-progress or completed")
    validate_claim_boundary(payload)
    asset = payload.get("asset_historical_debt")
    if not isinstance(asset, dict):
        fail("asset_historical_debt missing")
    if asset.get("status") != "implemented-with-human-destructive-boundaries":
        fail("asset_historical_debt status mismatch")
    validate_symlinks(asset)
    validate_prism_runs(asset)
    validate_remaining_root_groups(asset)
    validate_long_term_memory(payload)
    validate_prism(payload)
    run_check(["bash", "compass/tools/redcap-runtime-package-manifest.sh", "--check", "--npm-pack-dry-run"], "runtime package manifest")
    run_check(["bash", "compass/tools/redcap-package-publish-safety-check.sh"], "package publish safety")
    run_check(["bash", "compass/tools/redcap-knowledge-gateway.sh", "check"], "knowledge gateway")
    print("PRE_RELEASE_BLOCKING_DEBT_OK")
    print(f"status={payload['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

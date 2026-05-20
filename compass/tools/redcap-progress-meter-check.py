#!/usr/bin/env python3
# 用途：运行时与收尾脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#runtime-and-closeout

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "references/redcap-progress-meter-policy.json"
SCRIPT_PATH = ROOT / "compass/tools/redcap-progress-meter.sh"
EXPECTED_BUCKETS = {
    "historical_debt_smell",
    "current_focused_task_set",
    "long_term_evolution_program",
}
REQUIRED_DEBT_FIELDS = {
    "owner",
    "status",
    "reason",
    "expiry_review_rule",
    "closeout_rule",
    "archive_rule",
}
REQUIRED_HUMAN_FIELDS = {
    "整体任务全景图",
    "当前位置",
    "当前已完成",
    "下一步计划做的是",
    "需要人工介入",
}
REQUIRED_SOURCE_IDS = {
    "dev_task",
    "current_task_report",
    "closeout_runtime",
    "backlog_current_focus",
    "framework_upgrade_backlog",
    "architecture_smell_backlog",
    "legacy_asset_lifecycle",
    "reference_asset_lifecycle",
    "governance_debt_register",
    "evolution_candidates",
    "conclusion_prism_policy",
    "full_llm_wiki_roadmap",
    "public_arsenal_policy",
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-progress-meter-check] {message}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing json: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid json {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"json must be an object: {path}")
    return payload


def safe_repo_path(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        fail(f"unsafe source path: {raw}")
    return ROOT / path


def require_existing_sources(policy: dict[str, Any]) -> None:
    for row in policy.get("source_mappings", []):
        if not isinstance(row, dict):
            fail("source_mappings entries must be objects")
        source_id = row.get("id")
        bucket = row.get("bucket")
        raw_path = row.get("path")
        if not isinstance(source_id, str) or not source_id:
            fail("source mapping missing id")
        if bucket not in EXPECTED_BUCKETS:
            fail(f"{source_id}: unsupported bucket {bucket}")
        if not isinstance(raw_path, str) or not raw_path:
            fail(f"{source_id}: missing path")
        if raw_path == ".dev-task.md":
            continue
        if not safe_repo_path(raw_path).exists():
            fail(f"{source_id}: source path missing: {raw_path}")


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "redcap-progress-meter-policy":
        fail("unexpected policy_id")
    truth = policy.get("truth_source_rule")
    if not isinstance(truth, dict):
        fail("missing truth_source_rule")
    if truth.get("mode") != "aggregate-only":
        fail("truth_source_rule.mode must be aggregate-only")
    if truth.get("allowed_to_store_new_truth") is not False:
        fail("progress meter must not store new truth")
    buckets = policy.get("buckets")
    if not isinstance(buckets, list):
        fail("buckets must be a list")
    bucket_ids = {row.get("id") for row in buckets if isinstance(row, dict)}
    if bucket_ids != EXPECTED_BUCKETS:
        fail(f"bucket ids mismatch: {sorted(bucket_ids)}")
    source_ids = {row.get("id") for row in policy.get("source_mappings", []) if isinstance(row, dict)}
    missing_sources = sorted(REQUIRED_SOURCE_IDS - source_ids)
    if missing_sources:
        fail("required source mappings missing: " + ", ".join(missing_sources))
    fields = set(policy.get("debt_lifecycle_minimum_fields") or [])
    missing_fields = sorted(REQUIRED_DEBT_FIELDS - fields)
    if missing_fields:
        fail("debt lifecycle fields missing: " + ", ".join(missing_fields))
    boundary = policy.get("prism_boundary")
    if not isinstance(boundary, dict):
        fail("missing prism_boundary")
    if boundary.get("real_task_default_timeout_seconds") != 600:
        fail("real Prism task timeout must be 600 seconds")
    if "Availability probes" not in str(boundary.get("availability_probe_timeout_rule", "")):
        fail("availability probe timeout boundary missing")
    if "Copilot" not in str(boundary.get("copilot_fallback_rule", "")):
        fail("copilot fallback boundary missing")
    require_existing_sources(policy)


def validate_output() -> None:
    completed = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        fail("progress meter json render failed: " + (completed.stderr.strip() or completed.stdout.strip()))
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        fail(f"progress meter json is invalid: {exc}")
    if payload.get("truth_source_mode") != "aggregate-only":
        fail("progress meter output must declare aggregate-only truth source mode")
    bucket_ids = {row.get("id") for row in payload.get("buckets", []) if isinstance(row, dict)}
    if bucket_ids != EXPECTED_BUCKETS:
        fail(f"progress meter output bucket ids mismatch: {sorted(bucket_ids)}")
    historical = next((row for row in payload.get("buckets", []) if row.get("id") == "historical_debt_smell"), {})
    counts = historical.get("counts") if isinstance(historical, dict) else {}
    if not isinstance(counts, dict) or "governance_debt" not in counts:
        fail("progress meter output must include governance_debt counts")
    human = payload.get("human")
    if not isinstance(human, dict):
        fail("progress meter output missing human surface")
    missing_human = sorted(REQUIRED_HUMAN_FIELDS - set(human))
    if missing_human:
        fail("progress meter human fields missing: " + ", ".join(missing_human))
    current_position = str(human.get("当前位置", ""))
    if "门禁层级" not in current_position:
        fail("progress meter human current position must expose gate tier")
    if "门禁层级：未声明" in current_position:
        fail("progress meter human current position must not expose an undeclared gate tier")
    current_bucket = next((row for row in payload.get("buckets", []) if row.get("id") == "current_focused_task_set"), {})
    task = current_bucket.get("task") if isinstance(current_bucket, dict) else {}
    gate_tier = task.get("gate_tier") if isinstance(task, dict) else None
    if gate_tier not in {"lightweight", "standard", "release-structural"}:
        fail("progress meter current task gate_tier must be a supported tier")
    boundary = payload.get("prism_boundary")
    if not isinstance(boundary, dict) or boundary.get("real_task_default_timeout_seconds") != 600:
        fail("progress meter output lost prism timeout boundary")


def main() -> int:
    validate_policy(load_json(POLICY_PATH))
    validate_output()
    print("PROGRESS_METER_CHECK_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# 用途：正式发布 R1 Prism 报告归档迁移规划验收；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAN = ROOT / "references/r1-prism-report-archive-copy-first-plan.json"
DEFAULT_CHURN_FREEZE_GUARD = ROOT / "references/r1-prism-report-archive-churn-freeze-guard.json"
DEFAULT_LIVE_APPLY_MANIFEST = ROOT / "references/r1-prism-report-archive-live-copy-first-apply.json"
RUNTIME_MANIFEST = ROOT / "compass/tools/redcap-runtime-package-manifest.sh"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-prism-report-archive-copy-first-plan-check] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing {label}: {path.relative_to(ROOT)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be a JSON object")
    return payload


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{label} must be non-empty text")
    return value.strip()


def require_bool(value: Any, expected: bool, label: str) -> None:
    if value is not expected:
        fail(f"{label} must be {expected}")


def require_list(value: Any, label: str, *, min_len: int = 1) -> list[Any]:
    if not isinstance(value, list) or len(value) < min_len:
        fail(f"{label} must be a list with at least {min_len} item(s)")
    return value


def package_candidates() -> set[str]:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        candidate_path = Path(handle.name)
    try:
        completed = subprocess.run(
            ["bash", str(RUNTIME_MANIFEST), "--output", str(candidate_path)],
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if completed.returncode != 0:
            sys.stdout.write(completed.stdout)
            fail("runtime package manifest generation failed")
        return {
            line.strip()
            for line in candidate_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    finally:
        try:
            candidate_path.unlink()
        except OSError:
            pass


def normalized_report_id(path: Path) -> str:
    stem = path.stem
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})-(.+)$", stem)
    if match:
        return f"{match.group(1)}{match.group(2)}{match.group(3)}-{match.group(4)}"
    return stem


def index_text_and_ids(index_path: Path) -> tuple[str, set[str]]:
    text = index_path.read_text(encoding="utf-8")
    ids = {
        match.group(1).strip()
        for match in re.finditer(r'^\s*-\s+id:\s*"?([^"\n]+)"?\s*$', text, flags=re.MULTILINE)
    }
    if not ids:
        fail("prism report index has no ids")
    return text, ids


def git_tracked(rel: str) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--", rel],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return rel in {line.strip() for line in completed.stdout.splitlines()}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_optional_churn_freeze_guard() -> dict[str, Any] | None:
    if not DEFAULT_CHURN_FREEZE_GUARD.is_file():
        return None
    guard = load_json(DEFAULT_CHURN_FREEZE_GUARD, "Prism report archive churn/freeze guard")
    if guard.get("guard_id") != "redcap-r1-prism-report-archive-churn-freeze-guard":
        fail("churn/freeze guard id mismatch")
    if guard.get("status") != "active-freeze-guard-no-live-report-copy-move-delete-or-cleanup":
        fail("churn/freeze guard status mismatch")
    return guard


def validate_optional_live_apply_copies(copied_reports: list[Path]) -> None:
    if not copied_reports:
        return
    if not DEFAULT_LIVE_APPLY_MANIFEST.is_file():
        fail("private-archive/prism-reports/*.md files require live copy-first apply manifest")
    manifest = load_json(DEFAULT_LIVE_APPLY_MANIFEST, "Prism report archive live copy-first apply manifest")
    if manifest.get("apply_id") != "redcap-r1-prism-report-archive-live-copy-first-apply":
        fail("live copy-first apply manifest id mismatch")
    if manifest.get("status") != "copy-first-archive-apply-old-anchors-retained":
        fail("live copy-first apply manifest status mismatch")
    contract = manifest.get("archive_contract")
    if not isinstance(contract, dict):
        fail("live copy-first apply manifest archive_contract must be an object")
    if contract.get("archive_root") != "private-archive/prism-reports":
        fail("live copy-first apply archive_root mismatch")
    copies = require_list(manifest.get("archive_copies"), "live copy-first apply archive_copies", min_len=len(copied_reports))
    expected = {path.relative_to(ROOT).as_posix() for path in copied_reports}
    actual = {
        require_text(item.get("archive_path"), "live copy-first apply archive_copies.archive_path")
        for item in copies
        if isinstance(item, dict)
    }
    if expected != actual:
        fail("live copy-first apply archive_copies do not match private archive files")
    if contract.get("copied_report_count") != len(copied_reports):
        fail("live copy-first apply copied_report_count is stale")


def validate_churn_freeze_guard(
    guard: dict[str, Any],
    payload: dict[str, Any],
    mappings: list[Any],
    live_source_set: set[str],
    mapped_sources: set[str],
    index_text: str,
    index: set[str],
) -> dict[str, int]:
    source = guard.get("source_truth")
    if not isinstance(source, dict):
        fail("churn/freeze guard source_truth must be an object")
    plan_rel = require_text(source.get("plan_path"), "churn_freeze_guard.source_truth.plan_path")
    if plan_rel != "references/r1-prism-report-archive-copy-first-plan.json":
        fail("churn/freeze guard source_truth.plan_path mismatch")
    expected_plan_hash = require_text(source.get("plan_sha256"), "churn_freeze_guard.source_truth.plan_sha256")
    if sha256(DEFAULT_PLAN) != expected_plan_hash:
        fail("churn/freeze guard source_truth.plan_sha256 is stale")

    policy = guard.get("freeze_policy")
    if not isinstance(policy, dict):
        fail("churn/freeze guard freeze_policy must be an object")
    if policy.get("frozen_source") != "references/r1-prism-report-archive-copy-first-plan.json::archive_plan.mappings":
        fail("churn/freeze guard freeze_policy.frozen_source mismatch")
    if policy.get("frozen_report_count") != len(mappings):
        fail(f"churn/freeze guard frozen_report_count stale: expected {len(mappings)}")
    expected_mapping_hash = require_text(policy.get("frozen_mapping_sha256"), "freeze_policy.frozen_mapping_sha256")
    if canonical_sha256(mappings) != expected_mapping_hash:
        fail("churn/freeze guard frozen_mapping_sha256 is stale")
    for key in [
        "new_report_handling",
        "unlisted_new_report_policy",
        "next_plan_refresh_policy",
    ]:
        require_text(policy.get(key), f"freeze_policy.{key}")

    if not mapped_sources <= live_source_set:
        missing = sorted(mapped_sources - live_source_set)
        fail("frozen mapped reports missing from live anchors: " + ", ".join(missing[:8]))

    post_freeze_entries = guard.get("post_freeze_reports", [])
    if not isinstance(post_freeze_entries, list):
        fail("post_freeze_reports must be a list")
    expected_post_freeze = live_source_set - mapped_sources
    seen_post_freeze: set[str] = set()
    for item in post_freeze_entries:
        if not isinstance(item, dict):
            fail("post_freeze_reports entries must be objects")
        source_rel = require_text(item.get("source_path"), "post_freeze_report.source_path")
        if source_rel in seen_post_freeze:
            fail(f"duplicate post-freeze report: {source_rel}")
        seen_post_freeze.add(source_rel)
        if source_rel not in expected_post_freeze:
            fail(f"post-freeze report is not a live unmapped report: {source_rel}")
        if item.get("include_in_current_archive_plan") is not False:
            fail(f"post-freeze report must not be included in current archive plan: {source_rel}")
        source_path = ROOT / source_rel
        if not git_tracked(source_rel):
            fail(f"post-freeze report must remain git-tracked: {source_rel}")
        if sha256(source_path) != require_text(item.get("source_sha256"), "post_freeze_report.source_sha256"):
            fail(f"post-freeze report hash stale: {source_rel}")
        report_id = require_text(item.get("report_id"), "post_freeze_report.report_id")
        if report_id not in {source_path.stem, normalized_report_id(source_path)}:
            fail(f"post-freeze report id does not match source path: {source_rel}")
        if report_id not in index and source_path.stem not in index and source_rel not in index_text:
            fail(f"prism report index missing post-freeze report id: {report_id}")

    if seen_post_freeze != expected_post_freeze:
        missing = sorted(expected_post_freeze - seen_post_freeze)
        extra = sorted(seen_post_freeze - expected_post_freeze)
        if missing:
            fail("unlisted post-freeze Prism reports: " + ", ".join(missing[:8]))
        if extra:
            fail("stale post-freeze Prism report entries: " + ", ".join(extra[:8]))

    result = guard.get("result")
    if not isinstance(result, dict):
        fail("churn/freeze guard result must be an object")
    if result.get("target_parent") != "prism-layer-and-evidence":
        fail("churn/freeze guard result.target_parent mismatch")
    if "still-blocking" not in require_text(result.get("release_blocker_status"), "result.release_blocker_status"):
        fail("churn/freeze guard must keep release blocker still-blocking")
    require_bool(result.get("this_guard_completed"), True, "result.this_guard_completed")
    for key in [
        "live_physical_archive_completed",
        "old_anchor_retirement_completed",
        "raw_evidence_cleanup_completed",
        "public_release_ready",
    ]:
        require_bool(result.get(key), False, f"result.{key}")

    return {"frozen_reports": len(mappings), "post_freeze_reports": len(seen_post_freeze)}


def validate_source_truth(payload: dict[str, Any]) -> None:
    source = payload.get("source_truth")
    if not isinstance(source, dict):
        fail("source_truth must be an object")
    for path_key, hash_key in [
        ("preflight_path", "preflight_sha256"),
        ("route_decision_path", "route_decision_sha256"),
    ]:
        rel = require_text(source.get(path_key), f"source_truth.{path_key}")
        expected = require_text(source.get(hash_key), f"source_truth.{hash_key}")
        path = ROOT / rel
        if not path.is_file():
            fail(f"source_truth path missing: {rel}")
        if sha256(path) != expected:
            fail(f"source_truth.{hash_key} is stale")
    preflight = load_json(ROOT / source["preflight_path"], "Prism report archive preflight")
    if preflight.get("preflight_id") != "redcap-r1-prism-report-archive-copy-first-preflight":
        fail("source preflight id mismatch")
    if preflight.get("claim_boundary", {}).get("report_archive_physically_migrated") is not False:
        fail("source preflight must not claim physical migration")
    route = load_json(ROOT / source["route_decision_path"], "P4-11 route decision")
    if route.get("selected_next_slice", {}).get("backlog_item_id") != "P4-12":
        fail("source route decision must select P4-12")


def validate_boundaries(payload: dict[str, Any]) -> None:
    boundary = payload.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    require_bool(boundary.get("plan_completed"), True, "claim_boundary.plan_completed")
    for key in [
        "copy_performed_now",
        "alias_switch_performed_now",
        "delete_last_performed_now",
        "old_report_anchors_removed_or_replaced",
        "raw_run_evidence_touched",
        "release_blocker_resolved",
        "public_release_ready",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")
    forbidden_claims = "\n".join(
        str(item) for item in require_list(boundary.get("forbidden_claims"), "claim_boundary.forbidden_claims", min_len=5)
    )
    for phrase in ["physically migrated", "retired or replaced", "raw run evidence", "blocker is closed", "public-release-ready"]:
        if phrase not in forbidden_claims:
            fail(f"claim_boundary.forbidden_claims missing {phrase}")

    policy = payload.get("operation_policy")
    if not isinstance(policy, dict):
        fail("operation_policy must be an object")
    for key in [
        "destructive_operations_allowed",
        "old_anchor_mutation_allowed",
        "raw_evidence_cleanup_allowed",
        "release_operations_allowed",
    ]:
        require_bool(policy.get(key), False, f"operation_policy.{key}")
    forbidden = {
        require_text(item, "operation_policy.forbidden_now item")
        for item in require_list(policy.get("forbidden_now"), "operation_policy.forbidden_now", min_len=10)
    }
    for required in [
        "copy-report",
        "move-report",
        "delete-report",
        "replace-old-report-anchor",
        "delete-run-evidence",
        "cleanup-run-evidence",
        "public-publish",
        "release-switch-change",
    ]:
        if required not in forbidden:
            fail(f"operation_policy.forbidden_now missing {required}")


def validate_archive_plan(payload: dict[str, Any]) -> dict[str, int]:
    plan = payload.get("archive_plan")
    if not isinstance(plan, dict):
        fail("archive_plan must be an object")
    if plan.get("source_root") != "prism/reports":
        fail("archive_plan.source_root must be prism/reports")
    if plan.get("future_archive_root") != "private-archive/prism-reports":
        fail("archive_plan.future_archive_root must be private-archive/prism-reports")
    if plan.get("future_index_path") != "private-archive/prism-reports/index.yaml":
        fail("archive_plan.future_index_path must be private-archive/prism-reports/index.yaml")

    report_files = sorted((ROOT / "prism/reports").glob("*.md"))
    mappings = require_list(plan.get("mappings"), "archive_plan.mappings", min_len=1)

    index_text, index = index_text_and_ids(ROOT / "prism/reports/index.yaml")
    live_source_set = {path.relative_to(ROOT).as_posix() for path in report_files}
    seen_sources: set[str] = set()
    seen_targets: set[str] = set()
    for item in mappings:
        if not isinstance(item, dict):
            fail("archive_plan.mappings entries must be objects")
        source_rel = require_text(item.get("source_path"), "mapping.source_path")
        target_rel = require_text(item.get("future_archive_path"), "mapping.future_archive_path")
        report_id = require_text(item.get("report_id"), "mapping.report_id")
        if source_rel in seen_sources:
            fail(f"duplicate source_path: {source_rel}")
        if target_rel in seen_targets:
            fail(f"duplicate future_archive_path: {target_rel}")
        seen_sources.add(source_rel)
        seen_targets.add(target_rel)
        if source_rel not in live_source_set:
            fail(f"mapping source_path is not a current report anchor: {source_rel}")
        if not target_rel.startswith("private-archive/prism-reports/") or not target_rel.endswith(".md"):
            fail(f"future archive path must stay under private-archive/prism-reports: {target_rel}")
        source_path = ROOT / source_rel
        if not git_tracked(source_rel):
            fail(f"source report must remain git-tracked: {source_rel}")
        if sha256(source_path) != require_text(item.get("source_sha256"), "mapping.source_sha256"):
            fail(f"mapping.source_sha256 stale: {source_rel}")
        if report_id not in {source_path.stem, normalized_report_id(source_path)}:
            fail(f"mapping.report_id does not match source path: {source_rel}")
        if report_id not in index and source_path.stem not in index and source_rel not in index_text:
            fail(f"prism report index missing mapped report id: {report_id}")
        require_bool(item.get("old_anchor_must_remain_resolvable"), True, f"{source_rel}.old_anchor_must_remain_resolvable")
        require_bool(item.get("copy_now"), False, f"{source_rel}.copy_now")
        require_bool(item.get("delete_old_now"), False, f"{source_rel}.delete_old_now")

    guard = load_optional_churn_freeze_guard()
    if guard is None:
        if plan.get("report_count") != len(report_files):
            fail(f"archive_plan.report_count stale: expected {len(report_files)}")
        if len(mappings) != len(report_files):
            fail(f"archive_plan.mappings must cover {len(report_files)} reports")
        missing_sources = sorted(live_source_set - seen_sources)
        if missing_sources:
            fail("archive_plan missing source reports: " + ", ".join(missing_sources[:8]))
        guard_summary = {"frozen_reports": len(report_files), "post_freeze_reports": 0}
    else:
        if plan.get("report_count") != len(mappings):
            fail(f"archive_plan.report_count must equal frozen mapping count: expected {len(mappings)}")
        guard_summary = validate_churn_freeze_guard(
            guard,
            payload,
            mappings,
            live_source_set,
            seen_sources,
            index_text,
            index,
        )

    archive_root = ROOT / "private-archive/prism-reports"
    copied_reports = sorted(archive_root.glob("*.md")) if archive_root.exists() else []
    validate_optional_live_apply_copies(copied_reports)

    candidates = package_candidates()
    for prefix in ["prism/reports/", "prism/runs/", "private-archive/prism-reports/"]:
        if any(path.startswith(prefix) for path in candidates):
            fail(f"{prefix.rstrip('/')} must remain excluded from package candidates")

    tracked_runs = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--", "prism/runs"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    ).stdout.strip()
    if tracked_runs:
        fail("prism/runs raw evidence must remain untracked/local-only")

    return {
        "reports": guard_summary["frozen_reports"],
        "mappings": len(mappings),
        "post_freeze_reports": guard_summary["post_freeze_reports"],
        "candidates": len(candidates),
    }


def validate_future_gates(payload: dict[str, Any]) -> None:
    rollback = payload.get("rollback_plan")
    if not isinstance(rollback, dict):
        fail("rollback_plan must be an object")
    rollback_text = "\n".join(str(item) for item in require_list(rollback.get("required_future_rollback_artifacts"), "rollback_plan.required_future_rollback_artifacts", min_len=4))
    for phrase in ["copy-first apply receipt", "old-anchor alias map", "package surface", "clean workspace E2E"]:
        if phrase not in rollback_text:
            fail(f"rollback_plan missing {phrase}")

    verification = payload.get("verification_plan")
    if not isinstance(verification, dict):
        fail("verification_plan must be an object")
    apply_text = "\n".join(str(item) for item in require_list(verification.get("required_before_future_apply"), "verification_plan.required_before_future_apply", min_len=10))
    for phrase in ["git-tracked", "unique", "index", "alias", "prism/runs", "package surface", "Prism review", "clean workspace E2E", "closeout receipt"]:
        if phrase not in apply_text:
            fail(f"verification_plan.required_before_future_apply missing {phrase}")
    retire_text = "\n".join(str(item) for item in require_list(verification.get("required_before_old_anchor_retirement"), "verification_plan.required_before_old_anchor_retirement", min_len=6))
    for phrase in ["copy-first apply", "alias-first", "archive-check", "package safety", "explicit Norven approval", "delete-last"]:
        if phrase not in retire_text:
            fail(f"verification_plan.required_before_old_anchor_retirement missing {phrase}")

    result = payload.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    if result.get("target_parent") != "prism-layer-and-evidence":
        fail("result.target_parent must be prism-layer-and-evidence")
    if "still-blocking" not in require_text(result.get("release_blocker_status"), "result.release_blocker_status"):
        fail("result.release_blocker_status must stay still-blocking")
    require_bool(result.get("this_plan_completed"), True, "result.this_plan_completed")
    require_bool(result.get("physical_archive_completed"), False, "result.physical_archive_completed")
    require_bool(result.get("raw_evidence_cleanup_completed"), False, "result.raw_evidence_cleanup_completed")


def validate(args: argparse.Namespace) -> dict[str, int]:
    payload = load_json(args.plan, "Prism report archive copy-first plan")
    if payload.get("version") != 1:
        fail("version must be 1")
    if payload.get("plan_id") != "redcap-r1-prism-report-archive-copy-first-plan":
        fail("plan_id mismatch")
    if payload.get("status") != "plan-only-no-report-copied-moved-deleted-or-cleaned":
        fail("status must remain plan-only-no-report-copied-moved-deleted-or-cleaned")
    validate_source_truth(payload)
    validate_boundaries(payload)
    summary = validate_archive_plan(payload)
    validate_future_gates(payload)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap R1 Prism report archive copy-first / alias-first plan.")
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    args = parser.parse_args()
    summary = validate(args)
    print(
        "R1_PRISM_REPORT_ARCHIVE_COPY_FIRST_PLAN_OK "
        f"reports={summary['reports']} mappings={summary['mappings']} "
        f"post_freeze_reports={summary['post_freeze_reports']} candidates={summary['candidates']} "
        "release_blocker_status=still-blocking"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

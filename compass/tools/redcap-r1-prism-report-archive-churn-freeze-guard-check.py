#!/usr/bin/env python3
# 用途：正式发布 R1 Prism 报告归档漂移冻结验收；详细职责见文件查阅字典。
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
DEFAULT_GUARD = ROOT / "references/r1-prism-report-archive-churn-freeze-guard.json"
PLAN_CHECKER = ROOT / "compass/tools/redcap-r1-prism-report-archive-copy-first-plan-check.sh"
READINESS_CHECKER = ROOT / "compass/tools/redcap-r1-prism-report-archive-apply-readiness-check.sh"
RUNTIME_MANIFEST = ROOT / "compass/tools/redcap-runtime-package-manifest.sh"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-prism-report-archive-churn-freeze-guard-check] {message}")


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


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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


def git_tracked(rel: str) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--", rel],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return rel in {line.strip() for line in completed.stdout.splitlines()}


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


def run_required_checker(label: str, checker: Path) -> None:
    completed = subprocess.run(
        ["bash", str(checker)],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        sys.stdout.write(completed.stdout)
        fail(f"{label} must pass before churn/freeze guard can pass")


def validate_source_truth(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    source = payload.get("source_truth")
    if not isinstance(source, dict):
        fail("source_truth must be an object")
    plan_rel = require_text(source.get("plan_path"), "source_truth.plan_path")
    readiness_rel = require_text(source.get("readiness_path"), "source_truth.readiness_path")
    plan_path = ROOT / plan_rel
    readiness_path = ROOT / readiness_rel
    if sha256(plan_path) != require_text(source.get("plan_sha256"), "source_truth.plan_sha256"):
        fail("source_truth.plan_sha256 is stale")
    if sha256(readiness_path) != require_text(source.get("readiness_sha256"), "source_truth.readiness_sha256"):
        fail("source_truth.readiness_sha256 is stale")
    run_required_checker("P4-12 plan checker", PLAN_CHECKER)
    run_required_checker("P4-13 readiness checker", READINESS_CHECKER)
    return (
        load_json(plan_path, "P4-12 Prism report archive plan"),
        load_json(readiness_path, "P4-13 Prism report archive readiness"),
    )


def validate_boundaries(payload: dict[str, Any]) -> None:
    boundary = payload.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    require_bool(boundary.get("freeze_guard_completed"), True, "claim_boundary.freeze_guard_completed")
    for key in [
        "live_apply_performed",
        "live_report_copy_performed",
        "old_anchor_retirement_performed",
        "raw_run_evidence_touched",
        "release_blocker_resolved",
        "public_release_ready",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")
    forbidden_claims = "\n".join(
        str(item) for item in require_list(boundary.get("forbidden_claims"), "claim_boundary.forbidden_claims", min_len=5)
    )
    for phrase in ["physically migrated", "retired or replaced", "raw run evidence", "blocker is not closed", "not public-release-ready"]:
        if phrase not in forbidden_claims:
            fail(f"claim_boundary.forbidden_claims missing {phrase}")

    policy = payload.get("operation_policy")
    if not isinstance(policy, dict):
        fail("operation_policy must be an object")
    for key in [
        "live_apply_allowed",
        "destructive_operations_allowed",
        "old_anchor_mutation_allowed",
        "raw_evidence_cleanup_allowed",
        "release_operations_allowed",
    ]:
        require_bool(policy.get(key), False, f"operation_policy.{key}")
    forbidden_ops = {
        require_text(item, "operation_policy.forbidden_now item")
        for item in require_list(policy.get("forbidden_now"), "operation_policy.forbidden_now", min_len=10)
    }
    for required in [
        "live-copy-report",
        "live-move-report",
        "live-delete-report",
        "replace-old-report-anchor",
        "retire-old-report-anchor",
        "create-private-archive-report-copy",
        "delete-run-evidence",
        "cleanup-run-evidence",
        "public-publish",
        "release-switch-change",
    ]:
        if required not in forbidden_ops:
            fail(f"operation_policy.forbidden_now missing {required}")


def validate_freeze_policy(payload: dict[str, Any], plan: dict[str, Any]) -> list[dict[str, Any]]:
    archive_plan = plan.get("archive_plan")
    if not isinstance(archive_plan, dict):
        fail("source plan archive_plan must be an object")
    mappings = require_list(archive_plan.get("mappings"), "source plan archive_plan.mappings")
    policy = payload.get("freeze_policy")
    if not isinstance(policy, dict):
        fail("freeze_policy must be an object")
    if policy.get("frozen_source") != "references/r1-prism-report-archive-copy-first-plan.json::archive_plan.mappings":
        fail("freeze_policy.frozen_source mismatch")
    if policy.get("frozen_report_count") != len(mappings):
        fail(f"freeze_policy.frozen_report_count stale: expected {len(mappings)}")
    if canonical_sha256(mappings) != require_text(policy.get("frozen_mapping_sha256"), "freeze_policy.frozen_mapping_sha256"):
        fail("freeze_policy.frozen_mapping_sha256 is stale")
    for key in ["new_report_handling", "unlisted_new_report_policy", "next_plan_refresh_policy"]:
        require_text(policy.get(key), f"freeze_policy.{key}")
    return [entry for entry in mappings if isinstance(entry, dict)]


def validate_report_sets(payload: dict[str, Any], mappings: list[dict[str, Any]]) -> dict[str, int]:
    index_text, index = index_text_and_ids(ROOT / "prism/reports/index.yaml")
    live_reports = sorted((ROOT / "prism/reports").glob("*.md"))
    live_source_set = {path.relative_to(ROOT).as_posix() for path in live_reports}
    mapped_sources: set[str] = set()
    for item in mappings:
        source_rel = require_text(item.get("source_path"), "mapping.source_path")
        mapped_sources.add(source_rel)
        source_path = ROOT / source_rel
        if source_rel not in live_source_set:
            fail(f"frozen mapped source missing from live reports: {source_rel}")
        if not git_tracked(source_rel):
            fail(f"frozen mapped source must remain git-tracked: {source_rel}")
        if sha256(source_path) != require_text(item.get("source_sha256"), "mapping.source_sha256"):
            fail(f"frozen mapped source hash stale: {source_rel}")

    expected_post_freeze = live_source_set - mapped_sources
    post_entries = payload.get("post_freeze_reports", [])
    if not isinstance(post_entries, list):
        fail("post_freeze_reports must be a list")
    seen_post: set[str] = set()
    for item in post_entries:
        if not isinstance(item, dict):
            fail("post_freeze_reports entries must be objects")
        source_rel = require_text(item.get("source_path"), "post_freeze_report.source_path")
        seen_post.add(source_rel)
        if source_rel not in expected_post_freeze:
            fail(f"post-freeze report is not an unmapped live report: {source_rel}")
        source_path = ROOT / source_rel
        if not git_tracked(source_rel):
            fail(f"post-freeze report must remain git-tracked: {source_rel}")
        if sha256(source_path) != require_text(item.get("source_sha256"), "post_freeze_report.source_sha256"):
            fail(f"post-freeze report hash stale: {source_rel}")
        if item.get("include_in_current_archive_plan") is not False:
            fail(f"post-freeze report must not be included in current archive plan: {source_rel}")
        report_id = require_text(item.get("report_id"), "post_freeze_report.report_id")
        if report_id not in {source_path.stem, normalized_report_id(source_path)}:
            fail(f"post-freeze report id does not match source path: {source_rel}")
        if report_id not in index and source_path.stem not in index and source_rel not in index_text:
            fail(f"prism report index missing post-freeze report id: {report_id}")

    if seen_post != expected_post_freeze:
        missing = sorted(expected_post_freeze - seen_post)
        stale = sorted(seen_post - expected_post_freeze)
        if missing:
            fail("unlisted post-freeze Prism reports: " + ", ".join(missing[:8]))
        if stale:
            fail("stale post-freeze Prism reports: " + ", ".join(stale[:8]))

    return {"frozen_reports": len(mapped_sources), "post_freeze_reports": len(seen_post)}


def validate_package_surface(payload: dict[str, Any]) -> int:
    policy = payload.get("package_surface_policy")
    if not isinstance(policy, dict):
        fail("package_surface_policy must be an object")
    for key in [
        "prism_reports_must_remain_excluded",
        "prism_runs_must_remain_excluded",
        "private_archive_prism_reports_must_remain_excluded",
    ]:
        require_bool(policy.get(key), True, f"package_surface_policy.{key}")
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
    )
    if tracked_runs.stdout.strip():
        fail("prism/runs raw evidence must remain untracked")
    archive_root = ROOT / "private-archive/prism-reports"
    copied_reports = sorted(archive_root.glob("*.md")) if archive_root.exists() else []
    if copied_reports:
        fail("freeze guard task must not create private-archive/prism-reports/*.md files")
    return len(candidates)


def validate_result(payload: dict[str, Any]) -> None:
    result = payload.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    if result.get("target_parent") != "prism-layer-and-evidence":
        fail("result.target_parent mismatch")
    if "still-blocking" not in require_text(result.get("release_blocker_status"), "result.release_blocker_status"):
        fail("result.release_blocker_status must remain still-blocking")
    require_bool(result.get("this_guard_completed"), True, "result.this_guard_completed")
    for key in [
        "live_physical_archive_completed",
        "old_anchor_retirement_completed",
        "raw_evidence_cleanup_completed",
        "public_release_ready",
    ]:
        require_bool(result.get(key), False, f"result.{key}")


def validate(args: argparse.Namespace) -> dict[str, int]:
    payload = load_json(args.guard, "Prism report archive churn/freeze guard")
    if payload.get("version") != 1:
        fail("version must be 1")
    if payload.get("guard_id") != "redcap-r1-prism-report-archive-churn-freeze-guard":
        fail("guard_id mismatch")
    if payload.get("status") != "active-freeze-guard-no-live-report-copy-move-delete-or-cleanup":
        fail("status mismatch")
    plan, _readiness = validate_source_truth(payload)
    validate_boundaries(payload)
    mappings = validate_freeze_policy(payload, plan)
    summary = validate_report_sets(payload, mappings)
    summary["candidates"] = validate_package_surface(payload)
    validate_result(payload)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap R1 Prism report archive churn/freeze guard.")
    parser.add_argument("--guard", type=Path, default=DEFAULT_GUARD)
    args = parser.parse_args()
    summary = validate(args)
    print(
        "R1_PRISM_REPORT_ARCHIVE_CHURN_FREEZE_GUARD_OK "
        f"frozen_reports={summary['frozen_reports']} post_freeze_reports={summary['post_freeze_reports']} "
        f"candidates={summary['candidates']} release_blocker_status=still-blocking"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

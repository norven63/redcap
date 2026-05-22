#!/usr/bin/env python3
# 用途：正式发布 R1 Prism 报告归档 live copy-first apply 验收；详细职责见文件查阅字典。
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
DEFAULT_MANIFEST = ROOT / "references/r1-prism-report-archive-live-copy-first-apply.json"
PLAN_PATH = ROOT / "references/r1-prism-report-archive-copy-first-plan.json"
READINESS_PATH = ROOT / "references/r1-prism-report-archive-apply-readiness.json"
GUARD_PATH = ROOT / "references/r1-prism-report-archive-churn-freeze-guard.json"
PLAN_CHECKER = ROOT / "compass/tools/redcap-r1-prism-report-archive-copy-first-plan-check.sh"
READINESS_CHECKER = ROOT / "compass/tools/redcap-r1-prism-report-archive-apply-readiness-check.sh"
GUARD_CHECKER = ROOT / "compass/tools/redcap-r1-prism-report-archive-churn-freeze-guard-check.sh"
RUNTIME_MANIFEST = ROOT / "compass/tools/redcap-runtime-package-manifest.sh"
EXPECTED_STATUS = "copy-first-archive-apply-old-anchors-retained"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-prism-report-archive-live-copy-first-apply-check] {message}")


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
        fail(f"{label} must pass before live copy-first apply can pass")


def normalized_report_id(path: Path) -> str:
    stem = path.stem
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})-(.+)$", stem)
    if match:
        return f"{match.group(1)}{match.group(2)}{match.group(3)}-{match.group(4)}"
    return stem


def archive_index_text_and_ids(index_path: Path) -> tuple[str, set[str], set[str]]:
    text = index_path.read_text(encoding="utf-8")
    ids = {
        match.group(1).strip()
        for match in re.finditer(r'^\s*-\s+id:\s*"?([^"\n]+)"?\s*$', text, flags=re.MULTILINE)
    }
    paths = {
        match.group(1).strip()
        for match in re.finditer(r'^\s*archive_path:\s*"?([^"\n]+)"?\s*$', text, flags=re.MULTILINE)
    }
    if not ids:
        fail("archive index has no ids")
    return text, ids, paths


def validate_source_truth(manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source = manifest.get("source_truth")
    if not isinstance(source, dict):
        fail("source_truth must be an object")
    expected = {
        "plan_path": PLAN_PATH,
        "readiness_path": READINESS_PATH,
        "guard_path": GUARD_PATH,
    }
    for key, path in expected.items():
        if source.get(key) != path.relative_to(ROOT).as_posix():
            fail(f"source_truth.{key} mismatch")
        hash_key = key.replace("_path", "_sha256")
        if source.get(hash_key) != sha256(path):
            fail(f"source_truth.{hash_key} is stale")

    run_required_checker("P4-12 plan checker", PLAN_CHECKER)
    run_required_checker("P4-13 readiness checker", READINESS_CHECKER)
    run_required_checker("P4-15 freeze guard checker", GUARD_CHECKER)
    return (
        load_json(PLAN_PATH, "P4-12 Prism report archive plan"),
        load_json(READINESS_PATH, "P4-13 Prism report archive readiness"),
        load_json(GUARD_PATH, "P4-15 Prism report archive freeze guard"),
    )


def validate_boundaries(manifest: dict[str, Any]) -> None:
    boundary = manifest.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    require_bool(boundary.get("live_archive_copies_created"), True, "claim_boundary.live_archive_copies_created")
    require_bool(boundary.get("archive_index_created"), True, "claim_boundary.archive_index_created")
    require_bool(boundary.get("old_anchors_retained"), True, "claim_boundary.old_anchors_retained")
    for key in [
        "old_anchor_retirement_performed",
        "raw_run_evidence_touched",
        "post_freeze_reports_absorbed",
        "release_blocker_resolved",
        "public_release_ready",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")
    forbidden = "\n".join(str(item) for item in require_list(boundary.get("forbidden_claims"), "claim_boundary.forbidden_claims", min_len=5))
    for phrase in ["Old prism/reports anchors", "raw run evidence", "post-freeze reports", "blocker is not closed", "not public-release-ready"]:
        if phrase not in forbidden:
            fail(f"claim_boundary.forbidden_claims missing {phrase}")

    policy = manifest.get("operation_policy")
    if not isinstance(policy, dict):
        fail("operation_policy must be an object")
    if policy.get("allowed_operation") != "copy-first-report-archive-only":
        fail("operation_policy.allowed_operation mismatch")
    require_bool(policy.get("live_copy_first_apply_completed"), True, "operation_policy.live_copy_first_apply_completed")
    for key in [
        "destructive_operations_allowed",
        "old_anchor_mutation_allowed",
        "raw_evidence_cleanup_allowed",
        "release_operations_allowed",
    ]:
        require_bool(policy.get(key), False, f"operation_policy.{key}")
    forbidden_ops = {
        require_text(item, "operation_policy.forbidden_operations item")
        for item in require_list(policy.get("forbidden_operations"), "operation_policy.forbidden_operations", min_len=8)
    }
    for required in [
        "move-old-report",
        "delete-old-report",
        "replace-old-report-anchor",
        "retire-old-report-anchor",
        "absorb-post-freeze-report",
        "delete-run-evidence",
        "cleanup-run-evidence",
        "public-publish",
        "release-switch-change",
    ]:
        if required not in forbidden_ops:
            fail(f"operation_policy.forbidden_operations missing {required}")


def validate_archive_contract(manifest: dict[str, Any], plan: dict[str, Any], guard: dict[str, Any]) -> dict[str, int]:
    archive_plan = plan.get("archive_plan")
    if not isinstance(archive_plan, dict):
        fail("source plan archive_plan must be an object")
    mappings = require_list(archive_plan.get("mappings"), "source plan archive_plan.mappings")
    freeze_policy = guard.get("freeze_policy")
    if not isinstance(freeze_policy, dict):
        fail("guard.freeze_policy must be an object")
    if freeze_policy.get("frozen_report_count") != len(mappings):
        fail("guard frozen_report_count does not match source plan mappings")
    if freeze_policy.get("frozen_mapping_sha256") != canonical_sha256(mappings):
        fail("guard frozen_mapping_sha256 is stale")

    contract = manifest.get("archive_contract")
    if not isinstance(contract, dict):
        fail("archive_contract must be an object")
    if contract.get("source_root") != "prism/reports":
        fail("archive_contract.source_root must be prism/reports")
    if contract.get("archive_root") != "private-archive/prism-reports":
        fail("archive_contract.archive_root must be private-archive/prism-reports")
    if contract.get("archive_index_path") != "private-archive/prism-reports/index.yaml":
        fail("archive_contract.archive_index_path mismatch")
    if contract.get("copied_report_count") != len(mappings):
        fail("archive_contract.copied_report_count is stale")
    require_bool(contract.get("old_anchors_remain_authoritative"), True, "archive_contract.old_anchors_remain_authoritative")
    require_bool(contract.get("post_freeze_reports_excluded"), True, "archive_contract.post_freeze_reports_excluded")

    copies = require_list(manifest.get("archive_copies"), "archive_copies", min_len=len(mappings))
    expected = {
        (require_text(item.get("source_path"), "mapping.source_path"), require_text(item.get("future_archive_path"), "mapping.future_archive_path"))
        for item in mappings
        if isinstance(item, dict)
    }
    actual = {
        (require_text(item.get("source_path"), "archive_copies.source_path"), require_text(item.get("archive_path"), "archive_copies.archive_path"))
        for item in copies
        if isinstance(item, dict)
    }
    if actual != expected:
        fail("archive_copies must exactly match frozen P4-12 mappings")

    index_path = ROOT / "private-archive/prism-reports/index.yaml"
    if not index_path.is_file():
        fail("archive index missing: private-archive/prism-reports/index.yaml")
    index_text, index_ids, index_paths = archive_index_text_and_ids(index_path)

    post_freeze = require_list(guard.get("post_freeze_reports"), "guard.post_freeze_reports", min_len=1)
    post_freeze_sources = {
        require_text(item.get("source_path"), "post_freeze_reports.source_path")
        for item in post_freeze
        if isinstance(item, dict)
    }

    archive_files = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "private-archive/prism-reports").glob("*.md")
    }
    expected_archive_files: set[str] = set()
    for item in copies:
        if not isinstance(item, dict):
            fail("archive_copies entries must be objects")
        source_rel = require_text(item.get("source_path"), "archive_copies.source_path")
        archive_rel = require_text(item.get("archive_path"), "archive_copies.archive_path")
        report_id = require_text(item.get("report_id"), "archive_copies.report_id")
        expected_hash = require_text(item.get("source_sha256"), "archive_copies.source_sha256")
        if source_rel in post_freeze_sources:
            fail(f"post-freeze report was copied into current archive cohort: {source_rel}")
        if not archive_rel.startswith("private-archive/prism-reports/") or not archive_rel.endswith(".md"):
            fail(f"archive copy escapes target root: {archive_rel}")
        source_path = ROOT / source_rel
        archive_path = ROOT / archive_rel
        if not source_path.is_file():
            fail(f"old report anchor missing: {source_rel}")
        if not git_tracked(source_rel):
            fail(f"old report anchor must remain git-tracked: {source_rel}")
        if not archive_path.is_file():
            fail(f"archive copy missing: {archive_rel}")
        if sha256(source_path) != expected_hash:
            fail(f"source hash stale: {source_rel}")
        if sha256(archive_path) != expected_hash:
            fail(f"archive copy hash mismatch: {archive_rel}")
        require_bool(item.get("old_anchor_retained"), True, f"{archive_rel}.old_anchor_retained")
        require_bool(item.get("copied"), True, f"{archive_rel}.copied")
        require_bool(item.get("delete_old_now"), False, f"{archive_rel}.delete_old_now")
        if report_id not in {source_path.stem, normalized_report_id(source_path)}:
            fail(f"archive copy report_id does not match source path: {source_rel}")
        if report_id not in index_ids:
            fail(f"archive index missing report id: {report_id}")
        if archive_rel not in index_paths and archive_rel not in index_text:
            fail(f"archive index missing archive path: {archive_rel}")
        expected_archive_files.add(archive_rel)

    if archive_files != expected_archive_files:
        missing = sorted(expected_archive_files - archive_files)
        extra = sorted(archive_files - expected_archive_files)
        if missing:
            fail("archive files missing: " + ", ".join(missing[:8]))
        if extra:
            fail("unexpected archive files: " + ", ".join(extra[:8]))

    for source_rel in post_freeze_sources:
        if source_rel in index_text:
            fail(f"post-freeze source unexpectedly appears in archive index: {source_rel}")

    return {"copied_reports": len(copies), "post_freeze_reports": len(post_freeze)}


def validate_package_surface(manifest: dict[str, Any]) -> int:
    policy = manifest.get("package_surface_policy")
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
    return len(candidates)


def validate_result(manifest: dict[str, Any]) -> None:
    result = manifest.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    if result.get("target_parent") != "prism-layer-and-evidence":
        fail("result.target_parent mismatch")
    if "still-blocking" not in require_text(result.get("release_blocker_status"), "result.release_blocker_status"):
        fail("result.release_blocker_status must remain still-blocking")
    require_bool(result.get("live_physical_archive_completed"), True, "result.live_physical_archive_completed")
    for key in [
        "old_anchor_retirement_completed",
        "raw_evidence_cleanup_completed",
        "post_freeze_reports_absorbed",
        "public_release_ready",
    ]:
        require_bool(result.get(key), False, f"result.{key}")


def validate(args: argparse.Namespace) -> dict[str, int]:
    manifest = load_json(args.manifest, "P4-16 Prism report archive live copy-first apply")
    if manifest.get("version") != 1:
        fail("version must be 1")
    if manifest.get("apply_id") != "redcap-r1-prism-report-archive-live-copy-first-apply":
        fail("apply_id mismatch")
    if manifest.get("status") != EXPECTED_STATUS:
        fail(f"status must be {EXPECTED_STATUS}")
    plan, _readiness, guard = validate_source_truth(manifest)
    validate_boundaries(manifest)
    summary = validate_archive_contract(manifest, plan, guard)
    summary["candidates"] = validate_package_surface(manifest)
    validate_result(manifest)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap R1 Prism report archive live copy-first apply.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    summary = validate(args)
    print(
        "R1_PRISM_REPORT_ARCHIVE_LIVE_COPY_FIRST_APPLY_OK "
        f"copied_reports={summary['copied_reports']} post_freeze_reports={summary['post_freeze_reports']} "
        f"candidates={summary['candidates']} release_blocker_status=still-blocking"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

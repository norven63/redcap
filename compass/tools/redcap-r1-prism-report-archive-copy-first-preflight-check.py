#!/usr/bin/env python3
# 用途：正式发布 R1 Prism 报告归档预检；详细职责见文件查阅字典。
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
DEFAULT_PREFLIGHT = ROOT / "references/r1-prism-report-archive-copy-first-preflight.json"
RUNTIME_MANIFEST = ROOT / "compass/tools/redcap-runtime-package-manifest.sh"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-prism-report-archive-copy-first-preflight-check] {message}")


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


def read_index(index_path: Path) -> tuple[str, set[str]]:
    text = index_path.read_text(encoding="utf-8")
    ids: set[str] = set()
    for match in re.finditer(r'^\s*-\s+id:\s*"?([^"\n]+)"?\s*$', text, flags=re.MULTILINE):
        ids.add(match.group(1).strip())
    if not ids:
        fail("prism report index has no report ids")
    return text, ids


def normalized_report_id(path: Path) -> str:
    stem = path.stem
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})-(.+)$", stem)
    if match:
        return f"{match.group(1)}{match.group(2)}{match.group(3)}-{match.group(4)}"
    return stem


def git_tracked(rel: str) -> bool:
    candidates = [rel]
    if rel.startswith("prism/reports/"):
        candidates.append("assets/evidence/prism-reports/" + rel[len("prism/reports/") :])
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--", *candidates],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    tracked = {line.strip() for line in completed.stdout.splitlines()}
    return any(candidate in tracked for candidate in candidates)


def validate_source_truth(payload: dict[str, Any]) -> None:
    source = payload.get("source_truth")
    if not isinstance(source, dict):
        fail("source_truth must be an object")
    for path_key, hash_key in [
        ("route_decision_path", "route_decision_sha256"),
        ("apply_preflight_path", "apply_preflight_sha256"),
    ]:
        rel = require_text(source.get(path_key), f"source_truth.{path_key}")
        expected_hash = require_text(source.get(hash_key), f"source_truth.{hash_key}")
        path = ROOT / rel
        if not path.is_file():
            fail(f"source_truth path missing: {rel}")
        actual_hash = sha256(path)
        if actual_hash != expected_hash:
            fail(f"source_truth.{hash_key} is stale")
    if source.get("apply_batch_id") != "batch-2-report-archive-index-migration":
        fail("source_truth.apply_batch_id must point to batch-2-report-archive-index-migration")

    apply_preflight = load_json(ROOT / require_text(source.get("apply_preflight_path"), "source_truth.apply_preflight_path"), "Prism apply preflight")
    batches = apply_preflight.get("apply_preflight_batches")
    if not isinstance(batches, list):
        fail("Prism apply preflight batches must be a list")
    batch = next((item for item in batches if isinstance(item, dict) and item.get("id") == source.get("apply_batch_id")), None)
    if not isinstance(batch, dict):
        fail("Prism apply preflight missing report archive batch")
    if batch.get("target_layers") != ["tracked-report-archive"]:
        fail("report archive batch target_layers must be ['tracked-report-archive']")
    if batch.get("candidate_count") != 1:
        fail("report archive batch candidate_count must stay 1")
    if batch.get("apply_now") is not False:
        fail("report archive batch apply_now must be false")


def validate_boundaries(payload: dict[str, Any]) -> None:
    boundary = payload.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    for key in [
        "report_archive_physically_migrated",
        "old_report_anchors_removed",
        "old_report_anchors_replaced",
        "raw_run_evidence_deleted",
        "raw_run_evidence_cleaned",
        "raw_run_evidence_moved",
        "release_switches_changed",
        "release_blocker_resolved",
        "public_release_ready",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")
    require_bool(boundary.get("report_archive_preflight_completed"), True, "claim_boundary.report_archive_preflight_completed")
    require_list(boundary.get("forbidden_claims"), "claim_boundary.forbidden_claims", min_len=5)

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
    require_bool(policy.get("apply_allowed_now"), False, "operation_policy.apply_allowed_now")
    forbidden = require_list(policy.get("forbidden_operations"), "operation_policy.forbidden_operations", min_len=8)
    for required in ["delete-run-evidence", "cleanup-run-evidence", "replace-old-report-anchor", "public-publish"]:
        if required not in forbidden:
            fail(f"operation_policy.forbidden_operations missing {required}")


def validate_reports_and_runs(payload: dict[str, Any]) -> tuple[int, int, int]:
    report_snapshot = payload.get("tracked_report_archive_snapshot")
    if not isinstance(report_snapshot, dict):
        fail("tracked_report_archive_snapshot must be an object")
    report_root = require_text(report_snapshot.get("report_root"), "tracked_report_archive_snapshot.report_root")
    index_rel = require_text(report_snapshot.get("index_path"), "tracked_report_archive_snapshot.index_path")
    if report_root != "prism/reports":
        fail("tracked_report_archive_snapshot.report_root must be prism/reports")
    if index_rel != "prism/reports/index.yaml":
        fail("tracked_report_archive_snapshot.index_path must be prism/reports/index.yaml")
    require_bool(report_snapshot.get("index_must_cover_current_reports"), True, "tracked_report_archive_snapshot.index_must_cover_current_reports")
    require_bool(report_snapshot.get("package_candidate_count_must_be_zero"), True, "tracked_report_archive_snapshot.package_candidate_count_must_be_zero")
    require_bool(report_snapshot.get("old_paths_must_remain_resolvable"), True, "tracked_report_archive_snapshot.old_paths_must_remain_resolvable")
    minimum_reports = report_snapshot.get("minimum_report_files")
    if not isinstance(minimum_reports, int) or minimum_reports < 1:
        fail("tracked_report_archive_snapshot.minimum_report_files must be positive")

    report_files = sorted((ROOT / report_root).glob("*.md"))
    if len(report_files) < minimum_reports:
        fail(f"tracked report count below minimum: expected>={minimum_reports} actual={len(report_files)}")
    index_text, ids = read_index(ROOT / index_rel)
    missing_ids = [
        path.relative_to(ROOT).as_posix()
        for path in report_files
        if (
            normalized_report_id(path) not in ids
            and path.stem not in ids
            and path.relative_to(ROOT).as_posix() not in index_text
        )
    ]
    if missing_ids:
        fail("prism report index missing report ids: " + ", ".join(missing_ids[:8]))
    if len(ids) != len(report_files):
        fail(f"prism report index count mismatch: index={len(ids)} files={len(report_files)}")
    for path in report_files:
        rel = path.relative_to(ROOT).as_posix()
        if not git_tracked(rel):
            fail(f"Prism report must remain git-tracked: {rel}")

    run_snapshot = payload.get("raw_run_evidence_snapshot")
    if not isinstance(run_snapshot, dict):
        fail("raw_run_evidence_snapshot must be an object")
    run_root = require_text(run_snapshot.get("run_root"), "raw_run_evidence_snapshot.run_root")
    if run_root != "prism/runs":
        fail("raw_run_evidence_snapshot.run_root must be prism/runs")
    require_bool(run_snapshot.get("package_candidate_count_must_be_zero"), True, "raw_run_evidence_snapshot.package_candidate_count_must_be_zero")
    require_bool(run_snapshot.get("tracked_git_files_allowed"), False, "raw_run_evidence_snapshot.tracked_git_files_allowed")
    require_bool(run_snapshot.get("cleanup_apply_allowed_now"), False, "raw_run_evidence_snapshot.cleanup_apply_allowed_now")
    require_bool(run_snapshot.get("prune_local_apply_allowed_now"), False, "raw_run_evidence_snapshot.prune_local_apply_allowed_now")
    minimum_runs = run_snapshot.get("minimum_run_directories")
    if not isinstance(minimum_runs, int) or minimum_runs < 1:
        fail("raw_run_evidence_snapshot.minimum_run_directories must be positive")
    run_dirs = sorted(path for path in (ROOT / run_root).iterdir() if path.is_dir()) if (ROOT / run_root).is_dir() else []
    if len(run_dirs) < minimum_runs:
        fail(f"Prism run evidence directory count below minimum: expected>={minimum_runs} actual={len(run_dirs)}")
    tracked_runs = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--", run_root],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    ).stdout.strip()
    if tracked_runs:
        fail("prism/runs raw evidence must remain untracked/local-only")

    candidates = package_candidates()
    if any(path.startswith("prism/reports/") for path in candidates):
        fail("prism/reports must remain excluded from package candidates")
    if any(path.startswith("prism/runs/") for path in candidates):
        fail("prism/runs must remain excluded from package candidates")
    return len(report_files), len(ids), len(run_dirs)


def validate_migration_preflight(payload: dict[str, Any]) -> None:
    preflight = payload.get("migration_preflight")
    if not isinstance(preflight, dict):
        fail("migration_preflight must be an object")
    if preflight.get("mode") != "copy-first-alias-first-preflight-only":
        fail("migration_preflight.mode must be copy-first-alias-first-preflight-only")
    for key in ["copy_performed_now", "alias_switch_performed_now", "delete_last_performed_now"]:
        require_bool(preflight.get(key), False, f"migration_preflight.{key}")
    required = "\n".join(str(item) for item in require_list(preflight.get("required_before_future_apply"), "migration_preflight.required_before_future_apply"))
    for phrase in ["report index migration proof", "archive-check pass", "old anchor", "package surface", "Prism review", "clean workspace E2E", "closeout receipt"]:
        if phrase not in required:
            fail(f"migration_preflight.required_before_future_apply missing {phrase}")
    cleanup = "\n".join(str(item) for item in require_list(preflight.get("required_before_any_cleanup"), "migration_preflight.required_before_any_cleanup"))
    for phrase in ["copy-first apply receipt", "archive-check pass", "aliases", "explicit Norven approval"]:
        if phrase not in cleanup:
            fail(f"migration_preflight.required_before_any_cleanup missing {phrase}")

    result = payload.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    if result.get("target_parent") != "prism-layer-and-evidence":
        fail("result.target_parent must be prism-layer-and-evidence")
    if "still-blocking" not in require_text(result.get("release_blocker_status"), "result.release_blocker_status"):
        fail("result.release_blocker_status must stay still-blocking")
    for key in ["physical_archive_completed", "raw_evidence_cleanup_completed"]:
        require_bool(result.get(key), False, f"result.{key}")


def validate(args: argparse.Namespace) -> dict[str, int]:
    payload = load_json(args.preflight, "Prism report archive preflight")
    if payload.get("version") != 1:
        fail("version must be 1")
    if payload.get("preflight_id") != "redcap-r1-prism-report-archive-copy-first-preflight":
        fail("preflight_id mismatch")
    if payload.get("status") != "preflight-only-no-report-or-run-evidence-moved-deleted-or-cleaned":
        fail("status must remain preflight-only-no-report-or-run-evidence-moved-deleted-or-cleaned")
    validate_source_truth(payload)
    validate_boundaries(payload)
    report_count, index_count, run_count = validate_reports_and_runs(payload)
    validate_migration_preflight(payload)
    return {"report_count": report_count, "index_count": index_count, "run_count": run_count}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap R1 Prism report archive copy-first preflight.")
    parser.add_argument("--preflight", type=Path, default=DEFAULT_PREFLIGHT)
    args = parser.parse_args()
    summary = validate(args)
    print(
        "R1_PRISM_REPORT_ARCHIVE_COPY_FIRST_PREFLIGHT_OK "
        f"reports={summary['report_count']} index={summary['index_count']} runs={summary['run_count']} "
        "release_blocker_status=still-blocking"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

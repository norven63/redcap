#!/usr/bin/env python3
# 用途：正式发布 R1 Prism 报告归档 apply readiness / rehearsal 验收；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_READINESS = ROOT / "references/r1-prism-report-archive-apply-readiness.json"
DEFAULT_LIVE_APPLY_MANIFEST = ROOT / "references/r1-prism-report-archive-live-copy-first-apply.json"
PLAN_CHECKER = ROOT / "compass/tools/redcap-r1-prism-report-archive-copy-first-plan-check.sh"
RUNTIME_MANIFEST = ROOT / "compass/tools/redcap-runtime-package-manifest.sh"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-prism-report-archive-apply-readiness-check] {message}")


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


def validate_optional_live_apply_files(live_archive_files: list[Path]) -> set[str]:
    if not live_archive_files:
        return set()
    if not DEFAULT_LIVE_APPLY_MANIFEST.is_file():
        fail("live private-archive/prism-reports files require live copy-first apply manifest")
    manifest = load_json(DEFAULT_LIVE_APPLY_MANIFEST, "Prism report archive live copy-first apply manifest")
    if manifest.get("apply_id") != "redcap-r1-prism-report-archive-live-copy-first-apply":
        fail("live copy-first apply manifest id mismatch")
    if manifest.get("status") != "copy-first-archive-apply-old-anchors-retained":
        fail("live copy-first apply manifest status mismatch")
    contract = manifest.get("archive_contract")
    if not isinstance(contract, dict):
        fail("live copy-first apply archive_contract must be an object")
    if contract.get("archive_root") != "private-archive/prism-reports":
        fail("live copy-first apply archive_root mismatch")
    index_rel = require_text(contract.get("archive_index_path"), "live copy-first apply archive_index_path")
    expected_index_path = ROOT / index_rel
    report_files = [path for path in live_archive_files if path.suffix == ".md"]
    non_report_files = {path.relative_to(ROOT).as_posix() for path in live_archive_files if path.suffix != ".md"}
    if non_report_files != {index_rel}:
        fail("live private archive contains unexpected non-report files: " + ", ".join(sorted(non_report_files)[:8]))
    if not expected_index_path.is_file():
        fail("live copy-first apply archive index missing")
    copies = require_list(manifest.get("archive_copies"), "live copy-first apply archive_copies", min_len=len(report_files))
    expected = {path.relative_to(ROOT).as_posix() for path in report_files}
    actual = {
        require_text(item.get("archive_path"), "live copy-first apply archive_copies.archive_path")
        for item in copies
        if isinstance(item, dict)
    }
    if expected != actual:
        fail("live copy-first apply archive_copies do not match live private archive files")
    return expected | {index_rel}


def validate_source_truth(payload: dict[str, Any]) -> dict[str, Any]:
    source = payload.get("source_truth")
    if not isinstance(source, dict):
        fail("source_truth must be an object")
    plan_rel = require_text(source.get("plan_path"), "source_truth.plan_path")
    expected_hash = require_text(source.get("plan_sha256"), "source_truth.plan_sha256")
    plan_path = ROOT / plan_rel
    if sha256(plan_path) != expected_hash:
        fail("source_truth.plan_sha256 is stale")

    completed = subprocess.run(
        ["bash", str(PLAN_CHECKER)],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        sys.stdout.write(completed.stdout)
        fail("P4-12 plan checker must pass before readiness rehearsal")

    plan = load_json(plan_path, "P4-12 Prism report archive plan")
    if plan.get("plan_id") != source.get("plan_id"):
        fail("source_truth.plan_id mismatch")
    return plan


def validate_boundaries(payload: dict[str, Any]) -> None:
    boundary = payload.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    require_bool(boundary.get("readiness_rehearsal_completed"), True, "claim_boundary.readiness_rehearsal_completed")
    require_bool(boundary.get("sandbox_rehearsal_completed"), True, "claim_boundary.sandbox_rehearsal_completed")
    for key in [
        "live_apply_performed",
        "live_report_copy_performed",
        "old_anchor_retirement_performed",
        "raw_run_evidence_touched",
        "release_blocker_resolved",
        "public_release_ready",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")
    forbidden = "\n".join(str(item) for item in require_list(boundary.get("forbidden_claims"), "claim_boundary.forbidden_claims", min_len=5))
    for phrase in ["physically migrated", "retired or replaced", "raw run evidence", "blocker is closed", "public-release-ready"]:
        if phrase not in forbidden:
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
        "delete-run-evidence",
        "cleanup-run-evidence",
        "public-publish",
        "release-switch-change",
    ]:
        if required not in forbidden_ops:
            fail(f"operation_policy.forbidden_now missing {required}")


def validate_rehearsal(payload: dict[str, Any], plan: dict[str, Any]) -> dict[str, int]:
    readiness = payload.get("rehearsal_plan")
    if not isinstance(readiness, dict):
        fail("rehearsal_plan must be an object")
    archive_plan = plan.get("archive_plan")
    if not isinstance(archive_plan, dict):
        fail("source plan archive_plan must be an object")
    mappings = require_list(archive_plan.get("mappings"), "source plan archive_plan.mappings")
    if readiness.get("report_count") != len(mappings):
        fail(f"rehearsal_plan.report_count stale: expected {len(mappings)}")
    if readiness.get("mode") != "temporary-directory-copy-first-rehearsal":
        fail("rehearsal_plan.mode mismatch")
    if readiness.get("source_root") != "prism/reports":
        fail("rehearsal_plan.source_root must be prism/reports")
    if readiness.get("future_archive_root") != "private-archive/prism-reports":
        fail("rehearsal_plan.future_archive_root must be private-archive/prism-reports")
    if readiness.get("future_index_path") != "private-archive/prism-reports/index.yaml":
        fail("rehearsal_plan.future_index_path must be private-archive/prism-reports/index.yaml")

    alias = readiness.get("alias_compatibility_policy")
    if not isinstance(alias, dict):
        fail("rehearsal_plan.alias_compatibility_policy must be an object")
    for key in [
        "old_paths_remain_authoritative",
        "old_paths_must_remain_resolvable_after_rehearsal",
        "future_alias_map_required_before_live_apply",
        "delete_last_forbidden_in_this_task",
    ]:
        require_bool(alias.get(key), True, f"rehearsal_plan.alias_compatibility_policy.{key}")

    live_archive_root = ROOT / "private-archive/prism-reports"
    live_archive_files = sorted(path for path in live_archive_root.rglob("*") if path.is_file()) if live_archive_root.exists() else []
    live_archive_before = validate_optional_live_apply_files(live_archive_files)

    seen_targets: set[str] = set()
    with tempfile.TemporaryDirectory(prefix="redcap-prism-report-archive-rehearsal-") as tmp_name:
        tmp_root = Path(tmp_name)
        index_rows: list[dict[str, str]] = []
        for item in sorted(mappings, key=lambda entry: entry["source_path"]):
            source_rel = require_text(item.get("source_path"), "mapping.source_path")
            target_rel = require_text(item.get("future_archive_path"), "mapping.future_archive_path")
            report_id = require_text(item.get("report_id"), "mapping.report_id")
            expected_hash = require_text(item.get("source_sha256"), "mapping.source_sha256")
            if target_rel in seen_targets:
                fail(f"duplicate future archive target: {target_rel}")
            seen_targets.add(target_rel)
            if not target_rel.startswith("private-archive/prism-reports/") or not target_rel.endswith(".md"):
                fail(f"future archive target escapes archive root: {target_rel}")
            source_path = ROOT / source_rel
            if not source_path.is_file():
                fail(f"source report missing: {source_rel}")
            if not git_tracked(source_rel):
                fail(f"source report must remain git-tracked: {source_rel}")
            if sha256(source_path) != expected_hash:
                fail(f"mapping.source_sha256 stale: {source_rel}")
            require_bool(item.get("old_anchor_must_remain_resolvable"), True, f"{source_rel}.old_anchor_must_remain_resolvable")
            require_bool(item.get("copy_now"), False, f"{source_rel}.copy_now")
            require_bool(item.get("delete_old_now"), False, f"{source_rel}.delete_old_now")

            target_path = tmp_root / target_rel
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            if sha256(target_path) != expected_hash:
                fail(f"temporary archive copy checksum mismatch: {target_rel}")
            if not source_path.exists():
                fail(f"old anchor disappeared during rehearsal: {source_rel}")
            index_rows.append(
                {
                    "report_id": report_id,
                    "source_path": source_rel,
                    "future_archive_path": target_rel,
                    "source_sha256": expected_hash,
                }
            )

        index_path = tmp_root / "private-archive/prism-reports/index.yaml"
        index_path.write_text(
            "reports:\n"
            + "".join(
                f'  - id: "{row["report_id"]}"\n'
                f'    source_path: "{row["source_path"]}"\n'
                f'    archive_path: "{row["future_archive_path"]}"\n'
                f'    sha256: "{row["source_sha256"]}"\n'
                for row in index_rows
            ),
            encoding="utf-8",
        )
        if len(index_rows) != len(mappings):
            fail("temporary archive index row count mismatch")
        if not index_path.is_file():
            fail("temporary archive index was not created")

    live_archive_files_after = sorted(path for path in live_archive_root.rglob("*") if path.is_file()) if live_archive_root.exists() else []
    live_archive_after = validate_optional_live_apply_files(live_archive_files_after)
    if live_archive_after != live_archive_before:
        fail("live private archive changed during rehearsal")

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

    return {"reports": len(mappings), "rehearsed_copies": len(mappings), "candidates": len(candidates)}


def validate_result(payload: dict[str, Any]) -> None:
    result = payload.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    if result.get("target_parent") != "prism-layer-and-evidence":
        fail("result.target_parent mismatch")
    status = require_text(result.get("release_blocker_status"), "result.release_blocker_status")
    if not status.startswith("still-blocking"):
        fail("result.release_blocker_status must remain still-blocking")
    require_bool(result.get("this_readiness_rehearsal_completed"), True, "result.this_readiness_rehearsal_completed")
    for key in [
        "live_physical_archive_completed",
        "old_anchor_retirement_completed",
        "raw_evidence_cleanup_completed",
    ]:
        require_bool(result.get(key), False, f"result.{key}")


def validate(args: argparse.Namespace) -> dict[str, int]:
    payload = load_json(args.readiness, "Prism report archive apply readiness")
    if payload.get("version") != 1:
        fail("version must be 1")
    if payload.get("readiness_id") != "redcap-r1-prism-report-archive-apply-readiness":
        fail("readiness_id mismatch")
    if payload.get("status") != "readiness-rehearsal-only-no-live-report-copy-move-delete-or-cleanup":
        fail("status must remain readiness-rehearsal-only-no-live-report-copy-move-delete-or-cleanup")
    plan = validate_source_truth(payload)
    validate_boundaries(payload)
    summary = validate_rehearsal(payload, plan)
    validate_result(payload)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap R1 Prism report archive apply readiness / rehearsal.")
    parser.add_argument("--readiness", type=Path, default=DEFAULT_READINESS)
    args = parser.parse_args()
    summary = validate(args)
    print(
        "R1_PRISM_REPORT_ARCHIVE_APPLY_READINESS_OK "
        f"reports={summary['reports']} rehearsed_copies={summary['rehearsed_copies']} candidates={summary['candidates']} "
        "release_blocker_status=still-blocking"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

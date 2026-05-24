#!/usr/bin/env python3
# 用途：校验 P4-19 旧 Prism 报告锚点退休预检；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "references/r1-prism-report-archive-old-anchor-delete-last-preflight.json"
LIVE_APPLY = ROOT / "references/r1-prism-report-archive-live-copy-first-apply.json"
CONVERGENCE = ROOT / "references/r1-formal-release-readiness-convergence-assessment.json"
LIVE_APPLY_CHECKER = ROOT / "compass/tools/redcap-r1-prism-report-archive-live-copy-first-apply-check.sh"
RUNTIME_MANIFEST = ROOT / "compass/tools/redcap-runtime-package-manifest.sh"
EXPECTED_STATUS = "preflight-completed-old-anchors-retained-not-ready-for-delete-last-apply"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-prism-report-archive-old-anchor-delete-last-preflight-check] {message}")


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


def require_int(value: Any, expected: int, label: str) -> None:
    if value != expected:
        fail(f"{label} must be {expected}, got {value!r}")


def require_list(value: Any, label: str, *, min_len: int = 1) -> list[Any]:
    if not isinstance(value, list) or len(value) < min_len:
        fail(f"{label} must be a list with at least {min_len} item(s)")
    return value


def run_checker(label: str, checker: Path) -> None:
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
        fail(f"{label} failed")


def package_candidates() -> set[str]:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        output_path = Path(handle.name)
    try:
        completed = subprocess.run(
            ["bash", str(RUNTIME_MANIFEST), "--output", str(output_path)],
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if completed.returncode != 0:
            sys.stdout.write(completed.stdout)
            fail("runtime package manifest generation failed")
        return {line.strip() for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()}
    finally:
        try:
            output_path.unlink()
        except OSError:
            pass


def normalized_report_id(path: str) -> str:
    stem = Path(path).stem
    parts = stem.split("-", 3)
    if len(parts) == 4 and all(part.isdigit() for part in parts[:3]):
        return f"{parts[0]}{parts[1]}{parts[2]}-{parts[3]}"
    return stem


def validate_source_truth(manifest: dict[str, Any]) -> dict[str, Any]:
    source = manifest.get("source_truth")
    if not isinstance(source, dict):
        fail("source_truth must be an object")
    if source.get("live_copy_first_apply_path") != LIVE_APPLY.relative_to(ROOT).as_posix():
        fail("source_truth.live_copy_first_apply_path mismatch")
    if source.get("convergence_assessment_path") != CONVERGENCE.relative_to(ROOT).as_posix():
        fail("source_truth.convergence_assessment_path mismatch")
    if source.get("live_copy_first_apply_sha256") != sha256(LIVE_APPLY):
        fail("source_truth.live_copy_first_apply_sha256 is stale")
    if source.get("convergence_assessment_sha256") != sha256(CONVERGENCE):
        fail("source_truth.convergence_assessment_sha256 is stale")
    run_checker("P4-16 live copy-first apply checker", LIVE_APPLY_CHECKER)
    return load_json(LIVE_APPLY, "P4-16 live copy-first apply manifest")


def validate_claim_boundary(manifest: dict[str, Any]) -> None:
    boundary = manifest.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    for key in [
        "delete_last_preflight_completed",
        "old_anchors_retained",
        "private_archive_copies_verified",
    ]:
        require_bool(boundary.get(key), True, f"claim_boundary.{key}")
    for key in [
        "old_anchor_retirement_performed",
        "old_anchor_files_moved_or_deleted",
        "old_anchor_symlink_or_redirect_created",
        "raw_run_evidence_touched",
        "release_blocker_resolved",
        "public_release_ready",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")
    forbidden = "\n".join(str(item) for item in require_list(boundary.get("forbidden_claims"), "claim_boundary.forbidden_claims", min_len=5))
    for phrase in ["not been retired", "has been deleted", "raw run evidence", "blocker is not closed", "not public-release-ready"]:
        if phrase not in forbidden:
            fail(f"claim_boundary.forbidden_claims missing phrase: {phrase}")


def validate_inventory(manifest: dict[str, Any], live_apply: dict[str, Any]) -> None:
    inventory = manifest.get("old_anchor_inventory")
    if not isinstance(inventory, dict):
        fail("old_anchor_inventory must be an object")

    current_reports = sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / "prism/reports").glob("*.md"))
    copies = require_list(live_apply.get("archive_copies"), "live_apply.archive_copies", min_len=1)
    copied_sources = {require_text(item.get("source_path"), "archive_copies.source_path") for item in copies if isinstance(item, dict)}
    post_freeze = [path for path in current_reports if path not in copied_sources]

    require_int(inventory.get("current_report_markdown_count"), len(current_reports), "old_anchor_inventory.current_report_markdown_count")
    require_int(inventory.get("copied_report_count"), len(copied_sources), "old_anchor_inventory.copied_report_count")
    require_int(inventory.get("post_freeze_report_count"), len(post_freeze), "old_anchor_inventory.post_freeze_report_count")
    require_bool(
        inventory.get("package_surface_includes_old_report_anchors"),
        False,
        "old_anchor_inventory.package_surface_includes_old_report_anchors",
    )
    require_bool(
        inventory.get("package_surface_includes_private_archive_reports"),
        False,
        "old_anchor_inventory.package_surface_includes_private_archive_reports",
    )

    manifest_post = require_list(
        inventory.get("post_freeze_reports_not_in_archive_cohort"),
        "old_anchor_inventory.post_freeze_reports_not_in_archive_cohort",
        min_len=len(post_freeze),
    )
    manifest_post_paths = {require_text(item.get("source_path"), "post_freeze.source_path") for item in manifest_post if isinstance(item, dict)}
    if manifest_post_paths != set(post_freeze):
        fail("post-freeze report list does not match live prism/reports minus P4-16 copied cohort")

    for rel in current_reports:
        if not (ROOT / rel).is_file():
            fail(f"old anchor report missing: {rel}")
    for item in copies:
        if not isinstance(item, dict):
            fail("archive_copies item must be an object")
        source = ROOT / require_text(item.get("source_path"), "archive_copies.source_path")
        archive = ROOT / require_text(item.get("archive_path"), "archive_copies.archive_path")
        expected_hash = require_text(item.get("source_sha256"), "archive_copies.source_sha256")
        if not source.is_file():
            fail(f"copied source old anchor missing: {source.relative_to(ROOT)}")
        if not archive.is_file():
            fail(f"private archive copy missing: {archive.relative_to(ROOT)}")
        if sha256(source) != expected_hash:
            fail(f"source hash mismatch for {source.relative_to(ROOT)}")
        if sha256(archive) != expected_hash:
            fail(f"archive hash mismatch for {archive.relative_to(ROOT)}")

    candidates = package_candidates()
    leaked = sorted(
        item
        for item in candidates
        if item.startswith("prism/reports/") or item.startswith("private-archive/prism-reports/")
    )
    if leaked:
        fail("report anchors must not be package candidates: " + ", ".join(leaked[:5]))


def should_scan(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    if path.is_dir():
        return False
    excluded_prefixes = (
        ".git/",
        "node_modules/",
        "prism/reports/",
        "private-archive/prism-reports/",
        "assets/evidence/prism-reports/",
        "assets/private-archive/prism-reports/",
        "prism/runs/",
        ".redcap-runtime/",
    )
    if rel.startswith(excluded_prefixes):
        return False
    included_roots = (
        "ARCHITECTURE.md",
        "README.md",
        "AGENTS.md",
        "SKILL.md",
        "assets/",
        "compass/",
        "references/",
        "prism/",
        "private-archive/",
    )
    return rel in included_roots or rel.startswith(included_roots)


def reference_counts() -> tuple[int, int]:
    files = 0
    lines = 0
    for path in ROOT.rglob("*"):
        if not should_scan(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        count = text.count("prism/reports/")
        if count:
            files += 1
            lines += sum(1 for line in text.splitlines() if "prism/reports/" in line)
    return files, lines


def validate_reference_scan(manifest: dict[str, Any]) -> None:
    scan = manifest.get("reference_scan")
    if not isinstance(scan, dict):
        fail("reference_scan must be an object")
    files, lines = reference_counts()
    minimum_files = scan.get("minimum_files_with_old_anchor_references_excluding_report_roots")
    minimum_lines = scan.get("minimum_primary_control_surface_reference_lines")
    if not isinstance(minimum_files, int) or files < minimum_files:
        fail(f"old-anchor reference file count below manifest floor: {files} < {minimum_files!r}")
    if not isinstance(minimum_lines, int) or lines < minimum_lines:
        fail(f"old-anchor reference line count below manifest floor: {lines} < {minimum_lines!r}")
    groups = require_list(scan.get("representative_reference_groups"), "reference_scan.representative_reference_groups", min_len=4)
    group_names = {require_text(item.get("group"), "representative_reference_groups.group") for item in groups if isinstance(item, dict)}
    for required in [
        "current-user-facing-prism-index-and-protocol",
        "release-and-package-policy",
        "historical-task-reports-and-private-archive",
        "tools-and-runtime-status",
    ]:
        if required not in group_names:
            fail(f"reference_scan.representative_reference_groups missing {required}")


def validate_readiness(manifest: dict[str, Any]) -> None:
    readiness = manifest.get("retirement_readiness")
    if not isinstance(readiness, dict):
        fail("retirement_readiness must be an object")
    require_bool(readiness.get("safe_to_run_delete_last_apply_now"), False, "retirement_readiness.safe_to_run_delete_last_apply_now")
    if readiness.get("decision") != "not-ready-for-delete-last-apply":
        fail("retirement_readiness.decision mismatch")
    blockers = require_list(readiness.get("blockers"), "retirement_readiness.blockers", min_len=4)
    blocker_ids = {require_text(item.get("id"), "retirement_readiness.blockers.id") for item in blockers if isinstance(item, dict)}
    for required in [
        "post-freeze-reports-not-archived",
        "old-anchor-references-still-canonical",
        "no-delete-last-alias-contract",
        "no-human-destructive-authorization",
    ]:
        if required not in blocker_ids:
            fail(f"retirement_readiness.blockers missing {required}")

    requirements = "\n".join(str(item) for item in require_list(manifest.get("future_apply_requirements"), "future_apply_requirements", min_len=6))
    for phrase in ["post-freeze report", "alias", "references", "dry-run", "authorization", "raw evidence"]:
        if phrase not in requirements:
            fail(f"future_apply_requirements missing {phrase}")

    result = manifest.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    if result.get("release_blocker_status") != "still-blocking-after-delete-last-preflight":
        fail("result.release_blocker_status mismatch")
    require_bool(result.get("old_anchor_retirement_completed"), False, "result.old_anchor_retirement_completed")
    require_bool(result.get("delete_last_apply_ready"), False, "result.delete_last_apply_ready")


def validate_manifest(path: Path) -> None:
    manifest = load_json(path, "P4-19 old-anchor delete-last preflight manifest")
    if manifest.get("version") != 1:
        fail("version must be 1")
    if manifest.get("preflight_id") != "redcap-r1-prism-report-archive-old-anchor-delete-last-preflight":
        fail("preflight_id mismatch")
    if manifest.get("status") != EXPECTED_STATUS:
        fail("status mismatch")
    live_apply = validate_source_truth(manifest)
    validate_claim_boundary(manifest)
    validate_inventory(manifest, live_apply)
    validate_reference_scan(manifest)
    validate_readiness(manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()
    validate_manifest(Path(args.manifest).resolve())
    print("R1_PRISM_REPORT_ARCHIVE_OLD_ANCHOR_DELETE_LAST_PREFLIGHT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

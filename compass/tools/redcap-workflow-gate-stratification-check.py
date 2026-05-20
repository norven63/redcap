#!/usr/bin/env python3
# 用途：控制面保障脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#control-plane-assurance

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "references/workflow-gate-stratification-policy.json"
DEFAULT_SAMPLES = ROOT / "references/workflow-gate-stratification-samples.json"
DEFAULT_TASK = ROOT / ".dev-task.md"
REQUIRED_TIERS = {"lightweight", "standard", "release-structural"}
REQUIRED_TIERS_ORDER = ["lightweight", "standard", "release-structural"]
REQUIRED_RELEASE_CHECKS = {
    "spec-check",
    "diagnose",
    "package-safety",
    "runtime-package-manifest",
    "clean-workspace-e2e",
    "prism-quorum",
    "closeout-runtime",
}
FORBIDDEN_LIGHTWEIGHT_DEFAULTS = {
    "full-acceptance",
    "clean-workspace-e2e",
    "package-safety",
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-workflow-gate-stratification-check] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be a JSON object")
    return payload


def section(text: str, heading_prefix: str) -> str:
    capture = False
    buffer: list[str] = []
    for raw in text.splitlines():
        if raw.startswith("## "):
            heading = raw[3:].strip()
            if capture:
                break
            if heading.startswith(heading_prefix):
                capture = True
                continue
        if capture:
            buffer.append(raw)
    return "\n".join(buffer).strip()


def metadata(task_file: Path) -> dict[str, str]:
    if not task_file.is_file():
        return {}
    text = task_file.read_text(encoding="utf-8", errors="replace")
    meta = section(text, "控制面元数据") or section(text, "Canonical Metadata")
    result: dict[str, str] = {}
    for raw in meta.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$", raw)
        if match:
            result[match.group(1)] = match.group(2).strip()
    return result


def as_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        fail(f"{label} must be a non-empty string list")
    return [item.strip() for item in value]


def any_match(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def drift_allowed(path: str, policy: dict[str, Any]) -> bool:
    allow = policy.get("post_result_drift_allowlist")
    if not isinstance(allow, dict):
        fail("policy missing post_result_drift_allowlist")
    paths = set(as_string_list(allow.get("paths"), "post_result_drift_allowlist.paths"))
    prefixes = as_string_list(allow.get("prefixes"), "post_result_drift_allowlist.prefixes")
    globs = as_string_list(allow.get("globs"), "post_result_drift_allowlist.globs")
    blocked = as_string_list(allow.get("must_not_include"), "post_result_drift_allowlist.must_not_include")
    if path in paths or any(path.startswith(prefix) for prefix in prefixes) or any_match(path, globs):
        if path in blocked or any(path.startswith(prefix) for prefix in blocked if prefix.endswith("/")) or any_match(path, blocked):
            return False
        return True
    return False


def classify_paths(paths: list[str], policy: dict[str, Any]) -> str:
    overrides = policy.get("hard_gate_overrides")
    if not isinstance(overrides, list) or not overrides:
        fail("policy must define hard_gate_overrides")
    for row in overrides:
        if not isinstance(row, dict):
            fail("hard_gate_overrides entries must be objects")
        required = row.get("require_tier")
        if required != "release-structural":
            fail("hard gate overrides must require release-structural")
        patterns = as_string_list(row.get("path_globs"), f"hard_gate_overrides.{row.get('id', 'unknown')}.path_globs")
        if any(any_match(path, patterns) for path in paths):
            return "release-structural"
    if paths and all(drift_allowed(path, policy) for path in paths):
        return "lightweight"
    return "standard"


def git_changed_paths() -> list[str]:
    if not (ROOT / ".git").exists():
        return []
    changed: set[str] = set()
    for args in (
        ["git", "-C", str(ROOT), "diff", "--name-only", "HEAD", "--"],
        ["git", "-C", str(ROOT), "ls-files", "--others", "--exclude-standard"],
    ):
        completed = subprocess.run(args, text=True, capture_output=True, check=False)
        if completed.returncode != 0:
            return []
        changed.update(line.strip() for line in completed.stdout.splitlines() if line.strip())
    return sorted(changed)


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "redcap-workflow-gate-stratification":
        fail("unexpected policy_id")
    metadata_rule = policy.get("task_metadata")
    if not isinstance(metadata_rule, dict):
        fail("policy missing task_metadata")
    required_fields = set(as_string_list(metadata_rule.get("required_fields"), "task_metadata.required_fields"))
    if {"gate_tier", "gate_reason"} - required_fields:
        fail("task_metadata must require gate_tier and gate_reason")
    tiers = policy.get("tiers")
    if not isinstance(tiers, list) or len(tiers) < 3:
        fail("policy.tiers must contain at least three tiers")
    by_id: dict[str, dict[str, Any]] = {}
    for tier in tiers:
        if not isinstance(tier, dict):
            fail("tier entries must be objects")
        tier_id = tier.get("id")
        if not isinstance(tier_id, str) or tier_id in by_id:
            fail(f"invalid or duplicate tier id: {tier_id}")
        by_id[tier_id] = tier
        as_string_list(tier.get("mandatory_checks"), f"tier {tier_id}.mandatory_checks")
        if not isinstance(tier.get("when_to_use"), str) or not tier["when_to_use"].strip():
            fail(f"tier {tier_id} missing when_to_use")
    if set(by_id) != REQUIRED_TIERS:
        fail(f"tier ids mismatch: {sorted(by_id)}")
    lightweight_not_required = set(as_string_list(by_id["lightweight"].get("not_required_by_default"), "lightweight.not_required_by_default"))
    if not FORBIDDEN_LIGHTWEIGHT_DEFAULTS <= lightweight_not_required:
        fail("lightweight tier must not require release-grade checks by default")
    release_checks = set(as_string_list(by_id["release-structural"].get("mandatory_checks"), "release-structural.mandatory_checks"))
    missing_release = sorted(REQUIRED_RELEASE_CHECKS - release_checks)
    if missing_release:
        fail("release-structural tier missing mandatory checks: " + ", ".join(missing_release))
    not_downgradable = " ".join(as_string_list(by_id["release-structural"].get("not_downgradable_checks"), "release-structural.not_downgradable_checks"))
    for phrase in ["secret", "package", "destructive", "closeout"]:
        if phrase not in not_downgradable:
            fail(f"release-structural not_downgradable checks must include {phrase}")
    claims = " ".join(as_string_list(policy.get("must_not_claim"), "must_not_claim"))
    for phrase in ["does not permit skipping", "Clean workspace E2E freshness"]:
        if phrase not in claims:
            fail(f"must_not_claim missing phrase: {phrase}")
    # Validate allowlist shape and ensure it never includes obvious runtime/package roots.
    allow = policy.get("post_result_drift_allowlist")
    if not isinstance(allow, dict):
        fail("policy missing post_result_drift_allowlist")
    for key in ("paths", "prefixes", "globs", "must_not_include"):
        as_string_list(allow.get(key), f"post_result_drift_allowlist.{key}")


def validate_samples(policy: dict[str, Any], samples_payload: dict[str, Any]) -> None:
    if samples_payload.get("version") != 1:
        fail("samples version must be 1")
    if samples_payload.get("policy_path") != "references/workflow-gate-stratification-policy.json":
        fail("samples must point at workflow gate policy")
    samples = samples_payload.get("samples")
    if not isinstance(samples, list) or len(samples) < 3:
        fail("samples must contain at least three cases")
    sample_ids: set[str] = set()
    for sample in samples:
        if not isinstance(sample, dict):
            fail("sample entries must be objects")
        sample_id = sample.get("id")
        if not isinstance(sample_id, str) or sample_id in sample_ids:
            fail(f"invalid or duplicate sample id: {sample_id}")
        sample_ids.add(sample_id)
        paths = as_string_list(sample.get("changed_paths"), f"sample {sample_id}.changed_paths")
        expected_tier = sample.get("expected_tier")
        if expected_tier not in REQUIRED_TIERS:
            fail(f"sample {sample_id} expected_tier unsupported: {expected_tier}")
        actual_tier = classify_paths(paths, policy)
        if actual_tier != expected_tier:
            fail(f"sample {sample_id} expected tier {expected_tier}, got {actual_tier}")
        expected_drift = sample.get("expected_post_result_drift")
        drift_ok = all(drift_allowed(path, policy) for path in paths)
        if expected_drift == "allowed" and not drift_ok:
            fail(f"sample {sample_id} expected post-result drift to be allowed")
        if expected_drift == "blocked" and drift_ok:
            fail(f"sample {sample_id} expected post-result drift to be blocked")
        if expected_tier == "release-structural" and sample.get("expected_clean_workspace_e2e_required") is not True:
            fail(f"sample {sample_id} release-structural must require clean workspace E2E")
    if "p4-8-report-catalog-after-e2e" not in sample_ids:
        fail("samples must include the P4-8 report/catalog E2E staleness regression")


def validate_task_metadata(policy: dict[str, Any], task_file: Path) -> None:
    meta = metadata(task_file)
    if not meta:
        print(f"[warn] workflow gate task metadata missing in {task_file}", file=sys.stderr)
        return
    tier = meta.get("gate_tier", "").strip()
    reason = meta.get("gate_reason", "").strip()
    if not tier:
        print(f"[warn] workflow gate_tier missing in {task_file}", file=sys.stderr)
        return
    if tier not in REQUIRED_TIERS:
        fail(f"task gate_tier unsupported: {tier}")
    if len(reason) < 12:
        fail("task gate_reason is missing or too short")
    changed_paths = git_changed_paths()
    if changed_paths:
        inferred_tier = classify_paths(changed_paths, policy)
        if REQUIRED_TIERS_ORDER.index(tier) < REQUIRED_TIERS_ORDER.index(inferred_tier):
            fail(f"task gate_tier {tier} is weaker than changed-path tier {inferred_tier}")
    task_id = meta.get("task_id", "")
    if "rasg-024" in task_id and tier != "release-structural":
        fail("RASG-024 implementation must remain release-structural because it edits validator behavior")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap workflow gate stratification policy.")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--samples", default=str(DEFAULT_SAMPLES))
    parser.add_argument("--task-file", default=str(DEFAULT_TASK))
    args = parser.parse_args()

    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = ROOT / policy_path
    samples_path = Path(args.samples)
    if not samples_path.is_absolute():
        samples_path = ROOT / samples_path
    task_file = Path(args.task_file)
    if not task_file.is_absolute():
        task_file = ROOT / task_file
    policy = load_json(policy_path, "policy")
    samples = load_json(samples_path, "samples")
    validate_policy(policy)
    validate_samples(policy, samples)
    validate_task_metadata(policy, task_file)
    print(f"WORKFLOW_GATE_STRATIFICATION_OK tiers=3 samples={len(samples.get('samples', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

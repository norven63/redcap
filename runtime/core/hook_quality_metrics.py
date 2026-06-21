#!/usr/bin/env python3
"""度量 Hook（宿主钩子）误伤率、漏检率和样本退化。"""

from __future__ import annotations

import argparse
import datetime as dt
import copy
import hashlib
import json
import pathlib
import sys
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = REPO_ROOT / "assets" / "contracts" / "hook-quality-metrics.json"
REPORT_SCHEMA_ID = "redcap-hook-quality-metrics-report"
CONTRACT_SCHEMA_ID = "redcap-hook-quality-metrics-contract"
SAMPLE_CLASSES = {"false_positive", "false_negative", "true_block", "true_pass"}
OUTCOMES = {"pass", "block"}
SUPPORTED_EVENTS = {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}") from exc


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def parse_time(value: str) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def sample_expected_outcome(sample_class: str) -> str:
    if sample_class in {"false_positive", "true_pass"}:
        return "pass"
    return "block"


def threshold_values(contract: dict[str, Any]) -> dict[str, float]:
    raw = contract.get("thresholds")
    return raw if isinstance(raw, dict) else {}


def baseline_threshold_values(contract: dict[str, Any]) -> dict[str, float]:
    raw = contract.get("baseline_thresholds")
    return raw if isinstance(raw, dict) else {}


def source_event_reality_failures(
    source_event: dict[str, Any],
    *,
    sample_index: int,
    line_cache: dict[pathlib.Path, list[str]],
) -> list[str]:
    failures: list[str] = []
    events_jsonl = source_event.get("events_jsonl")
    line_number = source_event.get("events_jsonl_line")
    expected_hash = source_event.get("events_jsonl_sha256")
    if not isinstance(events_jsonl, str) or not events_jsonl:
        return [f"samples[{sample_index}].source_event.events_jsonl missing"]
    if not isinstance(line_number, int) or line_number < 1:
        return [f"samples[{sample_index}].source_event.events_jsonl_line missing"]
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        return [f"samples[{sample_index}].source_event.events_jsonl_sha256 invalid"]

    path = (REPO_ROOT / events_jsonl).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError:
        return [f"samples[{sample_index}].source_event.events_jsonl outside repo"]
    if not path.exists():
        return [f"samples[{sample_index}].source_event.events_jsonl not found"]

    if path not in line_cache:
        line_cache[path] = path.read_text(encoding="utf-8").splitlines()
    lines = line_cache[path]
    if line_number > len(lines):
        return [f"samples[{sample_index}].source_event.events_jsonl_line out of range"]

    line = lines[line_number - 1]
    actual_hash = hashlib.sha256(line.encode("utf-8")).hexdigest()
    if actual_hash != expected_hash:
        failures.append(f"samples[{sample_index}].source_event.events_jsonl_sha256 mismatch")
    try:
        event_payload = json.loads(line)
    except json.JSONDecodeError:
        failures.append(f"samples[{sample_index}].source_event.events_jsonl_line invalid json")
        return failures
    if event_payload.get("event") != source_event.get("event"):
        failures.append(f"samples[{sample_index}].source_event.event does not match events_jsonl line")
    return failures


def validate_contract(contract: dict[str, Any], *, now: dt.datetime | None = None) -> list[str]:
    failures: list[str] = []
    now = now or dt.datetime.now(dt.timezone.utc)
    if contract.get("schema_id") != CONTRACT_SCHEMA_ID:
        failures.append(f"schema_id must be {CONTRACT_SCHEMA_ID}")
    governance = contract.get("sample_governance")
    if not isinstance(governance, dict):
        failures.append("sample_governance missing")
        governance = {}
    min_per_class = governance.get("min_samples_per_class")
    if not isinstance(min_per_class, int) or min_per_class < 1:
        failures.append("sample_governance.min_samples_per_class must be a positive integer")
        min_per_class = 1
    max_age_days = governance.get("max_sample_age_days")
    if not isinstance(max_age_days, int) or max_age_days < 1:
        failures.append("sample_governance.max_sample_age_days must be a positive integer")
        max_age_days = 1
    if governance.get("independent_label_review_required") is not True:
        failures.append("sample_governance.independent_label_review_required must be true")

    thresholds = threshold_values(contract)
    baseline_thresholds = baseline_threshold_values(contract)
    for key in ["max_false_positive_rate", "max_false_negative_rate"]:
        value = thresholds.get(key)
        if not isinstance(value, (int, float)) or value < 0 or value > 1:
            failures.append(f"thresholds.{key} must be a number from 0 to 1")
        base_value = baseline_thresholds.get(key)
        if not isinstance(base_value, (int, float)) or base_value < 0 or base_value > 1:
            failures.append(f"baseline_thresholds.{key} must be a number from 0 to 1")

    change = contract.get("threshold_change_control")
    if not isinstance(change, dict):
        failures.append("threshold_change_control missing")
        change = {}
    if change.get("prism_review_required") is not True:
        failures.append("threshold_change_control.prism_review_required must be true")
    if thresholds != baseline_thresholds:
        review = change.get("review_evidence")
        if not isinstance(review, list) or not review:
            failures.append("thresholds differ from baseline_thresholds without review_evidence")
        if change.get("review_state") != "approved":
            failures.append("thresholds differ from baseline_thresholds without approved review_state")

    trend = contract.get("trend")
    if not isinstance(trend, dict):
        failures.append("trend missing")
        trend = {}
    if not isinstance(trend.get("window_days"), int) or trend.get("window_days") < 1:
        failures.append("trend.window_days must be a positive integer")
    max_increase = trend.get("max_rate_increase")
    if not isinstance(max_increase, (int, float)) or max_increase < 0 or max_increase > 1:
        failures.append("trend.max_rate_increase must be a number from 0 to 1")
    if not isinstance(trend.get("change_reasons"), list):
        failures.append("trend.change_reasons must be a list")

    samples = contract.get("samples")
    if not isinstance(samples, list):
        failures.append("samples must be a list")
        return failures

    counts = {name: 0 for name in SAMPLE_CLASSES}
    seen_ids: set[str] = set()
    source_event_line_cache: dict[pathlib.Path, list[str]] = {}
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            failures.append(f"samples[{index}] must be an object")
            continue
        sample_id = sample.get("id")
        if not isinstance(sample_id, str) or not sample_id:
            failures.append(f"samples[{index}].id missing")
        elif sample_id in seen_ids:
            failures.append(f"duplicate sample id: {sample_id}")
        else:
            seen_ids.add(sample_id)
        sample_class = sample.get("class")
        if sample_class not in SAMPLE_CLASSES:
            failures.append(f"samples[{index}].class invalid")
            continue
        counts[sample_class] += 1
        expected = sample.get("expected_outcome")
        if expected not in OUTCOMES:
            failures.append(f"samples[{index}].expected_outcome invalid")
        elif expected != sample_expected_outcome(sample_class):
            failures.append(f"samples[{index}].expected_outcome conflicts with class")
        if sample.get("observed_outcome") not in OUTCOMES:
            failures.append(f"samples[{index}].observed_outcome invalid")
        source_event = sample.get("source_event")
        if not isinstance(source_event, dict):
            failures.append(f"samples[{index}].source_event missing")
        else:
            if source_event.get("event") not in SUPPORTED_EVENTS:
                failures.append(f"samples[{index}].source_event.event invalid")
            if source_event.get("source_kind") != "real_hook_event":
                failures.append(f"samples[{index}].source_event.source_kind must be real_hook_event")
            if not isinstance(source_event.get("event_id"), str) or not source_event.get("event_id"):
                failures.append(f"samples[{index}].source_event.event_id missing")
            if not isinstance(source_event.get("events_jsonl_line"), int) or source_event.get("events_jsonl_line") < 1:
                failures.append(f"samples[{index}].source_event.events_jsonl_line missing")
            if not isinstance(source_event.get("events_jsonl_sha256"), str) or not source_event.get("events_jsonl_sha256"):
                failures.append(f"samples[{index}].source_event.events_jsonl_sha256 missing")
            fields = source_event.get("required_fields")
            if not isinstance(fields, list) or not fields:
                failures.append(f"samples[{index}].source_event.required_fields missing")
            failures.extend(
                source_event_reality_failures(
                    source_event,
                    sample_index=index,
                    line_cache=source_event_line_cache,
                )
            )
        label_review = sample.get("label_review")
        if not isinstance(label_review, dict):
            failures.append(f"samples[{index}].label_review missing")
        else:
            if label_review.get("state") != "prism-reviewed":
                failures.append(f"samples[{index}].label_review.state must be prism-reviewed")
            if not isinstance(label_review.get("review_reference"), str) or not label_review.get("review_reference"):
                failures.append(f"samples[{index}].label_review.review_reference missing")
        labeled_at = sample.get("labeled_at")
        parsed = parse_time(labeled_at) if isinstance(labeled_at, str) else None
        if parsed is None:
            failures.append(f"samples[{index}].labeled_at invalid")
        else:
            age_days = (now - parsed).days
            if age_days > max_age_days:
                failures.append(f"samples[{index}] stale: age_days={age_days} > {max_age_days}")

    for sample_class, count in sorted(counts.items()):
        if count < min_per_class:
            failures.append(f"sample class {sample_class} has {count}, expected at least {min_per_class}")
    return failures


def compute_report(contract: dict[str, Any], *, now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.timezone.utc)
    failures = validate_contract(contract, now=now)
    samples = contract.get("samples") if isinstance(contract.get("samples"), list) else []
    counts = {name: 0 for name in SAMPLE_CLASSES}
    source_events: set[str] = set()
    line_hash_bound_count = 0
    false_positive_count = 0
    false_negative_count = 0
    expected_pass_count = 0
    expected_block_count = 0
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        sample_class = sample.get("class")
        if sample_class in counts:
            counts[sample_class] += 1
        source_event = sample.get("source_event")
        if isinstance(source_event, dict) and isinstance(source_event.get("event_id"), str):
            source_events.add(source_event["event_id"])
            if isinstance(source_event.get("events_jsonl_line"), int) and isinstance(
                source_event.get("events_jsonl_sha256"),
                str,
            ):
                line_hash_bound_count += 1
        expected = sample.get("expected_outcome")
        observed = sample.get("observed_outcome")
        if expected == "pass":
            expected_pass_count += 1
            if observed == "block":
                false_positive_count += 1
        if expected == "block":
            expected_block_count += 1
            if observed == "pass":
                false_negative_count += 1

    false_positive_rate = false_positive_count / expected_pass_count if expected_pass_count else 1.0
    false_negative_rate = false_negative_count / expected_block_count if expected_block_count else 1.0
    thresholds = threshold_values(contract)
    if false_positive_rate > float(thresholds.get("max_false_positive_rate", -1)):
        failures.append(f"false_positive_rate {false_positive_rate:.4f} exceeds threshold")
    if false_negative_rate > float(thresholds.get("max_false_negative_rate", -1)):
        failures.append(f"false_negative_rate {false_negative_rate:.4f} exceeds threshold")

    trend = contract.get("trend") if isinstance(contract.get("trend"), dict) else {}
    baseline_fp = trend.get("baseline_false_positive_rate", 0)
    baseline_fn = trend.get("baseline_false_negative_rate", 0)
    max_increase = trend.get("max_rate_increase", 0)
    if isinstance(baseline_fp, (int, float)) and false_positive_rate - baseline_fp > max_increase:
        failures.append("false_positive_rate trend regression exceeds max_rate_increase")
    if isinstance(baseline_fn, (int, float)) and false_negative_rate - baseline_fn > max_increase:
        failures.append("false_negative_rate trend regression exceeds max_rate_increase")

    return {
        "schema_id": REPORT_SCHEMA_ID,
        "ok": not failures,
        "generated_at": iso_now(),
        "contract": str(DEFAULT_CONTRACT.relative_to(REPO_ROOT)),
        "sample_counts": counts,
        "sample_provenance": {
            "unique_source_event_count": len(source_events),
            "source_kind": "real_hook_event",
            "line_hash_bound_sample_count": line_hash_bound_count,
            "line_hash_validation": "required",
        },
        "metrics": {
            "false_positive_count": false_positive_count,
            "false_negative_count": false_negative_count,
            "expected_pass_count": expected_pass_count,
            "expected_block_count": expected_block_count,
            "false_positive_rate": round(false_positive_rate, 6),
            "false_negative_rate": round(false_negative_rate, 6),
        },
        "thresholds": thresholds,
        "trend": {
            "window_days": trend.get("window_days"),
            "baseline_false_positive_rate": baseline_fp,
            "baseline_false_negative_rate": baseline_fn,
            "max_rate_increase": max_increase,
            "change_reasons": trend.get("change_reasons") if isinstance(trend.get("change_reasons"), list) else [],
        },
        "failures": failures,
    }


def fixture_contract(base: dict[str, Any], fixture: str) -> dict[str, Any]:
    contract = copy.deepcopy(base)
    samples = contract.get("samples")
    if not isinstance(samples, list):
        return contract
    if fixture == "healthy":
        return contract
    if fixture == "false-positive-failure":
        for sample in samples:
            if isinstance(sample, dict) and sample.get("class") == "false_positive":
                sample["observed_outcome"] = "block"
                sample["change_reason"] = "negative probe: false positive regression"
                break
        return contract
    if fixture == "false-negative-failure":
        for sample in samples:
            if isinstance(sample, dict) and sample.get("class") == "false_negative":
                sample["observed_outcome"] = "pass"
                sample["change_reason"] = "negative probe: false negative regression"
                break
        return contract
    if fixture == "threshold-relaxed-unreviewed":
        contract.setdefault("thresholds", {})["max_false_positive_rate"] = 1.0
        contract.setdefault("thresholds", {})["max_false_negative_rate"] = 1.0
        contract["threshold_change_control"] = {
            "prism_review_required": True,
            "review_state": "missing",
            "review_evidence": [],
        }
        return contract
    if fixture == "insufficient-coverage":
        contract["samples"] = [
            sample for sample in samples
            if not (isinstance(sample, dict) and sample.get("class") == "true_pass")
        ]
        return contract
    if fixture == "stale-samples":
        for sample in samples:
            if isinstance(sample, dict):
                sample["labeled_at"] = "2020-01-01T00:00:00+00:00"
        return contract
    raise SystemExit(f"unsupported fixture: {fixture}")


def cmd_check(args: argparse.Namespace) -> int:
    contract_path = pathlib.Path(args.contract).resolve()
    contract = load_json(contract_path)
    if not isinstance(contract, dict):
        raise SystemExit("contract must be a JSON object")
    contract = fixture_contract(contract, args.fixture)
    report = compute_report(contract)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["ok"]:
        print("REDCAP_HOOK_QUALITY_METRICS_OK")
        return 0
    return 1


def cmd_self_check(args: argparse.Namespace) -> int:
    base = load_json(pathlib.Path(args.contract).resolve())
    if not isinstance(base, dict):
        raise SystemExit("contract must be a JSON object")
    cases = [
        ("healthy", True),
        ("false-positive-failure", False),
        ("false-negative-failure", False),
        ("threshold-relaxed-unreviewed", False),
        ("insufficient-coverage", False),
        ("stale-samples", False),
    ]
    failures: list[str] = []
    results: list[dict[str, Any]] = []
    for fixture, expected_ok in cases:
        report = compute_report(fixture_contract(base, fixture))
        results.append({"fixture": fixture, "ok": report["ok"], "expected_ok": expected_ok, "failures": report["failures"]})
        if report["ok"] is not expected_ok:
            failures.append(f"fixture {fixture} expected ok={expected_ok}, got {report['ok']}")
    payload = {
        "schema_id": "redcap-hook-quality-metrics-self-check",
        "ok": not failures,
        "cases": results,
        "failures": failures,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_HOOK_QUALITY_METRICS_SELF_CHECK_OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查 Hook（宿主钩子）质量度量")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check")
    check.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    check.add_argument(
        "--fixture",
        choices=[
            "healthy",
            "false-positive-failure",
            "false-negative-failure",
            "threshold-relaxed-unreviewed",
            "insufficient-coverage",
            "stale-samples",
        ],
        default="healthy",
    )
    self_check = subparsers.add_parser("self-check")
    self_check.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check(args)
    if args.command == "self-check":
        return cmd_self_check(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())

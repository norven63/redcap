#!/usr/bin/env python3
"""RedCap evidence retention guard and dry-run cleanup planner."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys
from dataclasses import dataclass
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "assets" / "contracts" / "evidence-retention.json"
DEFAULT_PLAN_OUT = REPO_ROOT / ".redcap" / "evidence" / "retention" / "latest-retention-plan.json"


@dataclass(frozen=True)
class Metric:
    id: str
    path: pathlib.Path
    exists: bool
    bytes: int
    file_count: int
    dir_count: int
    git_policy: str


def load_json(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON 必须是对象：{path}")
    return payload


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def path_label(path: pathlib.Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def git_policy(path: pathlib.Path) -> str:
    if not path.exists():
        return "missing"
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", path_label(path)],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    if tracked.returncode == 0:
        return "tracked"
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", path_label(path)],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    if ignored.returncode == 0:
        return "ignored"
    return "untracked"


def measure_path(metric_id: str, path: pathlib.Path) -> Metric:
    resolved = path if path.is_absolute() else REPO_ROOT / path
    if not resolved.exists():
        return Metric(metric_id, resolved, False, 0, 0, 0, "missing")
    if resolved.is_file():
        return Metric(metric_id, resolved, True, resolved.stat().st_size, 1, 0, git_policy(resolved))
    total = 0
    files = 0
    dirs = 0
    for item in resolved.rglob("*"):
        if item.is_dir():
            dirs += 1
        elif item.is_file():
            files += 1
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return Metric(metric_id, resolved, True, total, files, dirs, git_policy(resolved))


def sha256_file(path: pathlib.Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize_text_file(path: pathlib.Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else REPO_ROOT / path
    summary: dict[str, Any] = {
        "path": path_label(resolved),
        "exists": resolved.exists(),
        "sha256": sha256_file(resolved),
        "line_count": 0,
        "first_line_sha256": None,
        "last_line_sha256": None,
    }
    if not resolved.exists() or not resolved.is_file():
        return summary
    first_line: bytes | None = None
    last_line: bytes | None = None
    line_count = 0
    with resolved.open("rb") as handle:
        for raw_line in handle:
            line_count += 1
            line = raw_line.rstrip(b"\n")
            if first_line is None:
                first_line = line
            last_line = line
    summary["line_count"] = line_count
    if first_line is not None:
        summary["first_line_sha256"] = hashlib.sha256(first_line).hexdigest()
    if last_line is not None:
        summary["last_line_sha256"] = hashlib.sha256(last_line).hexdigest()
    return summary


def classify(value: int, warning: int | None, critical: int | None) -> str:
    if critical is not None and value >= critical:
        return "critical"
    if warning is not None and value >= warning:
        return "warning"
    return "ok"


def metric_payload(metric: Metric, *, warning_bytes: int | None = None, critical_bytes: int | None = None, warning_count: int | None = None, critical_count: int | None = None) -> dict[str, Any]:
    size_state = classify(metric.bytes, warning_bytes, critical_bytes)
    count_state = classify(metric.file_count, warning_count, critical_count)
    state = "critical" if "critical" in {size_state, count_state} else ("warning" if "warning" in {size_state, count_state} else "ok")
    return {
        "id": metric.id,
        "path": path_label(metric.path),
        "exists": metric.exists,
        "bytes": metric.bytes,
        "file_count": metric.file_count,
        "dir_count": metric.dir_count,
        "git_policy": metric.git_policy,
        "state": state,
        "size_state": size_state,
        "file_count_state": count_state,
        "thresholds": {
            "warning_bytes": warning_bytes,
            "critical_bytes": critical_bytes,
            "warning_count": warning_count,
            "critical_count": critical_count,
        },
    }


def dir_size(path: pathlib.Path) -> tuple[int, int]:
    total = 0
    files = 0
    for item in path.rglob("*"):
        if not item.is_file():
            continue
        files += 1
        try:
            total += item.stat().st_size
        except OSError:
            continue
    return total, files


def collect_system_temp_metric(contract: dict[str, Any]) -> dict[str, Any]:
    cfg = contract.get("system_temp_artifacts", {})
    protected = set(cfg.get("protected_names") or [])
    roots: list[pathlib.Path] = []
    for raw_root in cfg.get("roots", []):
        if raw_root == "$TMPDIR":
            raw_root = os.environ.get("TMPDIR") or "/tmp"
        root = pathlib.Path(str(raw_root)).expanduser()
        try:
            root = root.resolve()
        except OSError:
            root = root.absolute()
        if root not in roots:
            roots.append(root)

    candidates: list[dict[str, Any]] = []
    protected_hits: list[dict[str, Any]] = []
    total_bytes = 0
    total_files = 0
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for pattern in cfg.get("include_globs") or ["redcap-*"]:
            for item in sorted(root.glob(str(pattern))):
                if not item.is_dir():
                    continue
                size, files = dir_size(item)
                payload = {
                    "path": str(item),
                    "name": item.name,
                    "bytes": size,
                    "file_count": files,
                }
                if item.name in protected:
                    protected_hits.append(payload)
                    continue
                candidates.append(payload)
                total_bytes += size
                total_files += files

    thresholds = contract.get("thresholds", {}).get("system_temp_redcap_artifacts", {})
    count = len(candidates)
    count_state = classify(count, thresholds.get("warning_count"), thresholds.get("critical_count"))
    state = count_state
    return {
        "id": "system_temp_redcap_artifacts",
        "path": ", ".join(str(root) for root in roots),
        "exists": bool(candidates),
        "bytes": total_bytes,
        "file_count": total_files,
        "dir_count": count,
        "git_policy": "external-temp",
        "state": state,
        "size_state": "ok",
        "file_count_state": count_state,
        "thresholds": {
            "warning_bytes": None,
            "critical_bytes": None,
            "warning_count": thresholds.get("warning_count"),
            "critical_count": thresholds.get("critical_count"),
        },
        "candidates": candidates,
        "protected": protected_hits,
        "rule": cfg.get("rule"),
    }


def collect_metrics(contract: dict[str, Any]) -> list[dict[str, Any]]:
    thresholds = contract.get("thresholds", {})
    metrics: list[dict[str, Any]] = []
    total_cfg = thresholds.get("source_evidence_boundary", {})
    count_cfg = thresholds.get("source_evidence_boundary_file_count", {})
    metrics.append(metric_payload(
        measure_path("source_evidence_boundary", pathlib.Path("assets/evidence")),
        warning_bytes=total_cfg.get("warning_bytes"),
        critical_bytes=total_cfg.get("critical_bytes"),
        warning_count=count_cfg.get("warning_count"),
        critical_count=count_cfg.get("critical_count"),
    ))
    host_cfg = thresholds.get("host_hook_events_jsonl", {})
    metrics.append(metric_payload(
        measure_path("host_hook_events_jsonl", pathlib.Path(".redcap/evidence/host-hooks/codex/events.jsonl")),
        warning_bytes=host_cfg.get("warning_bytes"),
        critical_bytes=host_cfg.get("critical_bytes"),
    ))
    prism_cfg = thresholds.get("tracked_prism_task_ledger", {})
    metrics.append(metric_payload(
        measure_path("tracked_prism_task_ledger", pathlib.Path(".redcap/evidence/prism/task-ledger.jsonl")),
        warning_bytes=prism_cfg.get("warning_bytes"),
        critical_bytes=prism_cfg.get("critical_bytes"),
    ))
    runtime_cfg = thresholds.get("project_runtime_evidence", {})
    metrics.append(metric_payload(
        measure_path("project_runtime_evidence", pathlib.Path(".redcap/evidence")),
        warning_bytes=runtime_cfg.get("warning_bytes"),
        critical_bytes=runtime_cfg.get("critical_bytes"),
    ))
    external_cfg = thresholds.get("external_e2e_cache", {})
    metrics.append(metric_payload(
        measure_path("external_e2e_cache", pathlib.Path("/Users/norven/workspace/redcap-e2e-runs")),
        warning_bytes=external_cfg.get("warning_bytes"),
        critical_bytes=external_cfg.get("critical_bytes"),
        warning_count=external_cfg.get("warning_count"),
        critical_count=external_cfg.get("critical_count"),
    ))
    metrics.append(collect_system_temp_metric(contract))
    return metrics


def build_plan(contract: dict[str, Any], metrics: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {item["id"]: item for item in metrics}
    actions: list[dict[str, Any]] = []
    for rule in contract.get("retention_rules", []):
        if not isinstance(rule, dict):
            continue
        target = str(rule.get("target") or "")
        metric = None
        if target == ".redcap/evidence/host-hooks/codex/events.jsonl":
            metric = by_id.get("host_hook_events_jsonl")
        elif target == ".redcap/evidence/prism/task-ledger.jsonl":
            metric = by_id.get("tracked_prism_task_ledger")
        elif target == "assets/evidence":
            metric = by_id.get("source_evidence_boundary")
        elif target == "/Users/norven/workspace/redcap-e2e-runs":
            metric = by_id.get("external_e2e_cache")
        elif target == "system-temp-redcap-artifacts":
            metric = by_id.get("system_temp_redcap_artifacts")
        action_required = bool(metric and metric.get("state") in {"warning", "critical"})
        actions.append({
            "id": rule.get("id"),
            "target": target,
            "classification": rule.get("classification"),
            "git_policy": rule.get("git_policy"),
            "allowed_plan": rule.get("allowed_plan"),
            "mode": "dry_run_only",
            "action_required": action_required,
            "metric": metric,
            "hard_constraints": rule.get("hard_constraints", []),
            "next_safe_action": (
                "生成摘要索引后再申请受控清理"
                if action_required and rule.get("git_policy") == "tracked"
                else "通过对应受控入口 dry-run 后再决定是否清理"
                if action_required
                else "继续观察"
            ),
        })
    return {
        "schema_id": "redcap-evidence-retention-dry-run-plan",
        "dry_run": True,
        "destructive_cleanup_performed": False,
        "actions": actions,
    }


def build_materialized_plan(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_id": "redcap-evidence-retention-materialized-plan",
        "created_at": iso_now(),
        "dry_run": True,
        "destructive_cleanup_performed": False,
        "human_authorization_required_for_deletion": True,
        "source_report_status": report.get("status"),
        "metrics": report.get("metrics", []),
        "warnings": report.get("warnings", []),
        "failures": report.get("failures", []),
        "dry_run_plan": report.get("dry_run_plan") or {},
        "summary_index": {
            "host_hook_events_jsonl": summarize_text_file(REPO_ROOT / ".redcap" / "evidence" / "host-hooks" / "codex" / "events.jsonl"),
            "tracked_prism_task_ledger": summarize_text_file(REPO_ROOT / ".redcap" / "evidence" / "prism" / "task-ledger.jsonl"),
        },
        "history_window_policy": report.get("history_window_policy", {}),
        "completion_boundary": "本计划只提供膨胀风险治理的可查询 dry-run 依据；未执行删除、轮转或归档。",
    }


def build_report(*, include_plan: bool) -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    metrics = collect_metrics(contract)
    critical = [item for item in metrics if item.get("state") == "critical"]
    warnings = [item for item in metrics if item.get("state") == "warning"]
    report = {
        "schema_id": "redcap-evidence-retention-check",
        "ok": not critical,
        "contract": path_label(CONTRACT_PATH),
        "status": "critical" if critical else ("warning" if warnings else "ok"),
        "critical_count": len(critical),
        "warning_count": len(warnings),
        "metrics": metrics,
        "failures": [f"{item['id']} 达到 critical 阈值" for item in critical],
        "warnings": [f"{item['id']} 达到 warning 阈值，需要 dry-run 清理计划" for item in warnings],
        "history_window_policy": {
            "knowledge_impact_regression_must_survive": True,
            "lifecycle_sample_events_must_not_be_deleted_without_index": True,
            "tracked_ledgers_require_summary_index_before_archive": True,
        },
    }
    if include_plan:
        report["dry_run_plan"] = build_plan(contract, metrics)
    return report


def cmd_check(args: argparse.Namespace) -> int:
    report = build_report(include_plan=args.include_plan)
    if args.out:
        payload = build_materialized_plan(report) if args.materialize_plan else report
        write_json(pathlib.Path(args.out).resolve(), payload)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report["ok"]:
        print("REDCAP_EVIDENCE_RETENTION_OK")
        return 0
    return 1


def cmd_plan(args: argparse.Namespace) -> int:
    report = build_report(include_plan=True)
    payload = build_materialized_plan(report) if args.materialize else report["dry_run_plan"]
    if args.out:
        write_json(pathlib.Path(args.out).resolve(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    print("REDCAP_EVIDENCE_RETENTION_PLAN_OK")
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    if classify(10, 5, 20) != "warning":
        failures.append("warning threshold classification failed")
    if classify(20, 5, 20) != "critical":
        failures.append("critical threshold classification failed")
    contract = load_json(CONTRACT_PATH)
    if contract.get("schema_id") != "redcap-evidence-retention-contract":
        failures.append("contract schema_id invalid")
    if not contract.get("mode", {}).get("cleanup_plan_must_be_dry_run_first"):
        failures.append("contract must require dry-run before cleanup")
    temp_metric = collect_system_temp_metric(contract)
    if temp_metric.get("id") != "system_temp_redcap_artifacts":
        failures.append("system temp metric missing")
    if any(item.get("name") == "redcap-runtime" for item in temp_metric.get("candidates", [])):
        failures.append("redcap-runtime must be protected from system temp cleanup candidates")
    plan = build_plan(contract, [
        {
            "id": "host_hook_events_jsonl",
            "path": ".redcap/evidence/host-hooks/codex/events.jsonl",
            "state": "warning",
            "git_policy": "ignored",
        }
    ])
    if not any(item.get("action_required") for item in plan.get("actions", []) if item.get("id") == "host-hooks-events"):
        failures.append("dry-run plan did not require action for warning host hook log")
    materialized = build_materialized_plan({"status": "warning", "metrics": [], "warnings": [], "failures": [], "dry_run_plan": plan})
    if materialized.get("destructive_cleanup_performed") is not False:
        failures.append("materialized plan must not perform cleanup")
    if materialized.get("human_authorization_required_for_deletion") is not True:
        failures.append("materialized plan must require human authorization for deletion")
    if not isinstance(materialized.get("summary_index"), dict):
        failures.append("materialized plan missing summary_index")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_EVIDENCE_RETENTION_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap 证据保留与膨胀治理检查器")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--include-plan", action="store_true")
    check.add_argument("--out")
    check.add_argument("--materialize-plan", action="store_true")
    check.set_defaults(func=cmd_check)
    plan = sub.add_parser("plan")
    plan.add_argument("--out")
    plan.add_argument("--materialize", action="store_true")
    plan.set_defaults(func=cmd_plan)
    self_check = sub.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

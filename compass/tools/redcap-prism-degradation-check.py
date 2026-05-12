#!/usr/bin/env python3
# 用途：棱镜与结论保障脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#prism-and-providers

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "references/prism-degradation-policy.json"
INDEX_PATH = ROOT / "prism/reports/index.yaml"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-prism-degradation-check] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"{label} missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be a JSON object")
    return payload


def parse_reports_index(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        fail(f"Prism report index missing: {path}")
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        start = re.match(r'\s*-\s+id:\s*"?([^"\n]+)"?\s*$', raw)
        if start:
            if current:
                entries.append(current)
            current = {"id": start.group(1).strip()}
            continue
        if current is None:
            continue
        scalar = re.match(r'\s+(mode|date|topic|verdict):\s*"?([^"\n]+)"?\s*$', raw)
        if scalar:
            current[scalar.group(1)] = scalar.group(2).strip()
            continue
        agents = re.match(r"\s+agents:\s*\[(.*)\]\s*$", raw)
        if agents:
            current["agents"] = [
                item.strip().strip('"').strip("'")
                for item in agents.group(1).split(",")
                if item.strip()
            ]
    if current:
        entries.append(current)
    if not entries:
        fail("Prism report index must contain at least one report entry")
    return entries


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "prism-degradation-frequency-policy":
        fail("unexpected policy_id")
    if policy.get("primary_data_source") != "prism/reports/index.yaml":
        fail("policy must use prism/reports/index.yaml as primary data source")
    if policy.get("default_raw_runs_policy") != "forbidden-for-frequency-summary":
        fail("policy must forbid raw prism/runs as the default frequency source")
    window = policy.get("recent_window")
    thresholds = policy.get("thresholds")
    if not isinstance(window, dict) or not isinstance(thresholds, dict):
        fail("policy must define recent_window and thresholds")
    if int(window.get("report_count", 0)) < int(window.get("minimum_report_count", 0)):
        fail("recent_window.report_count must be >= minimum_report_count")
    warning = float(thresholds.get("warning_resource_limited_rate", -1))
    action = float(thresholds.get("action_required_resource_limited_rate", -1))
    if not (0 <= warning <= action <= 1):
        fail("resource-limited thresholds must satisfy 0 <= warning <= action <= 1")
    text = json.dumps(policy, ensure_ascii=False)
    for phrase in [
        "resource-limited",
        "full-quorum",
        "current_task_acceptance_classification",
        "Copilot remains protected fallback",
        "Codex CLI remains last-resort fallback",
    ]:
        if phrase not in text:
            fail(f"policy missing required phrase: {phrase}")


def classify_report(entry: dict[str, Any]) -> str:
    verdict = str(entry.get("verdict", "")).strip().lower()
    mode = str(entry.get("mode", "")).strip().lower()
    combined = f"{mode} {verdict}"
    if "resource-limited" in combined:
        return "resource-limited"
    if verdict in {"deadlock", "escalate", "blocked", "fail", "failed"}:
        return "blocked"
    if verdict in {"weak-consensus"}:
        return "weak-consensus"
    return "full-or-normal"


def provider_family(agent: str, mapping: dict[str, Any]) -> str:
    normalized = agent.strip().lower()
    for family, aliases in mapping.items():
        if not isinstance(aliases, list):
            continue
        for alias in aliases:
            alias_text = str(alias).strip().lower()
            if alias_text and normalized.startswith(alias_text):
                return family
    return normalized.split("&", 1)[0] or "unknown"


def parse_task_meta(task_file: Path) -> dict[str, str]:
    if not task_file.is_file():
        return {}
    meta: dict[str, str] = {}
    for raw in task_file.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_\-]+):\s*(.+?)\s*$", raw)
        if match:
            meta[match.group(1)] = match.group(2)
    return meta


def classify_current_acceptance(repo: Path, task_file: Path | None) -> dict[str, Any]:
    if task_file is None:
        return {"status": "not-checked", "classification": "not-required"}
    meta = parse_task_meta(task_file)
    policy = meta.get("acceptance_policy", "").strip().lower().replace("_", "-")
    run_id = meta.get("prism_acceptance_run", "").strip()
    if policy not in {"prism-required", "prism-required-when-available"}:
        return {"status": "not-required", "classification": "not-required", "policy": policy or "missing"}
    if not run_id:
        return {"status": "missing", "classification": "missing", "policy": policy, "detail": "prism_acceptance_run is not declared"}
    run_root = repo / "prism/runs" / run_id
    registry = run_root / "session-registry.yaml"
    binding = run_root / "artifacts/acceptance-binding.json"
    resource_limited = run_root / "artifacts/resource-limited.json"
    if resource_limited.is_file():
        return {"status": "present", "classification": "resource-limited", "policy": policy, "run_id": run_id}
    if binding.is_file():
        return {"status": "present", "classification": "full-quorum", "policy": policy, "run_id": run_id}
    if registry.is_file():
        return {"status": "pending", "classification": "pending", "policy": policy, "run_id": run_id}
    return {"status": "pending", "classification": "pending", "policy": policy, "run_id": run_id}


def build_summary(repo: Path, policy: dict[str, Any], task_file: Path | None) -> dict[str, Any]:
    reports = parse_reports_index(repo / str(policy["primary_data_source"]))
    window_cfg = policy["recent_window"]
    report_count = int(window_cfg["report_count"])
    minimum = int(window_cfg["minimum_report_count"])
    window = reports[:report_count]
    classes = Counter(classify_report(entry) for entry in window)
    resource_limited = classes.get("resource-limited", 0)
    blocked = classes.get("blocked", 0)
    total = len(window)
    rate = resource_limited / total if total else 0.0
    thresholds = policy["thresholds"]
    warning_rate = float(thresholds["warning_resource_limited_rate"])
    action_rate = float(thresholds["action_required_resource_limited_rate"])
    action_blocked = int(thresholds["action_required_blocked_reports"])
    if total < minimum:
        status = "insufficient-sample"
        action = "Collect more formal Prism reports before interpreting degradation trend."
    elif rate >= action_rate or blocked >= action_blocked:
        status = "action-required"
        action = policy["visible_actions"]["action_required"]
    elif rate >= warning_rate:
        status = "warning"
        action = policy["visible_actions"]["warning"]
    else:
        status = "healthy"
        action = policy["visible_actions"]["healthy"]
    mapping = policy.get("provider_family_mapping") or {}
    families = sorted(
        {
            provider_family(agent, mapping)
            for entry in window
            for agent in entry.get("agents") or []
            if str(agent).strip()
        }
    )
    resource_families = sorted(
        {
            provider_family(agent, mapping)
            for entry in window
            if classify_report(entry) == "resource-limited"
            for agent in entry.get("agents") or []
            if str(agent).strip()
        }
    )
    return {
        "status": status,
        "action": action,
        "window": {
            "configured_reports": report_count,
            "minimum_reports": minimum,
            "actual_reports": total,
            "latest_report_id": reports[0].get("id") if reports else "",
        },
        "counts": {
            "full_or_normal": classes.get("full-or-normal", 0),
            "resource_limited": resource_limited,
            "weak_consensus": classes.get("weak-consensus", 0),
            "blocked": blocked,
        },
        "rates": {
            "resource_limited": round(rate, 4),
            "warning_threshold": warning_rate,
            "action_required_threshold": action_rate,
        },
        "provider_families": families,
        "resource_limited_provider_families": resource_families,
        "current_task_acceptance": classify_current_acceptance(repo, task_file),
    }


def render_human(payload: dict[str, Any]) -> str:
    counts = payload["counts"]
    rates = payload["rates"]
    window = payload["window"]
    current = payload["current_task_acceptance"]
    percent = rates["resource_limited"] * 100
    lines = [
        "PRISM_DEGRADATION",
        f"status={payload['status']}",
        f"window_reports={window['actual_reports']}/{window['configured_reports']} minimum={window['minimum_reports']}",
        f"counts full_or_normal={counts['full_or_normal']} resource_limited={counts['resource_limited']} weak_consensus={counts['weak_consensus']} blocked={counts['blocked']}",
        f"resource_limited_rate={percent:.1f}% warning={rates['warning_threshold']*100:.0f}% action_required={rates['action_required_threshold']*100:.0f}%",
        "provider_families=" + ",".join(payload["provider_families"]),
        "resource_limited_provider_families=" + (",".join(payload["resource_limited_provider_families"]) or "none"),
        f"current_task_acceptance={current.get('classification', 'unknown')} run_id={current.get('run_id', 'none')}",
        f"action={payload['action']}",
        "PRISM_DEGRADATION_OK" if payload["status"] != "action-required" else "PRISM_DEGRADATION_ACTION_REQUIRED",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track formal Prism resource-limited degradation frequency.")
    parser.add_argument("--repo", default=str(ROOT), help="RedCap repo root")
    parser.add_argument("--task-file", default=None, help="Current .dev-task.md for acceptance classification")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    parser.add_argument("--fail-on-action-required", action="store_true", help="Exit non-zero when action-required threshold is reached")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    policy = load_json(repo / POLICY_PATH.relative_to(ROOT), "Prism degradation policy")
    validate_policy(policy)
    task_file = Path(args.task_file).resolve() if args.task_file else None
    payload = build_summary(repo, policy, task_file)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_human(payload))
    if args.fail_on_action_required and payload["status"] == "action-required":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""长期外部项目观察器。"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import shutil
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "assets" / "contracts" / "longrun-observer.json"
PROJECT_REDCAP = ".redcap"
STATE_REL = pathlib.Path(PROJECT_REDCAP) / "state" / "longrun-observer"
EVIDENCE_REL = pathlib.Path(PROJECT_REDCAP) / "evidence" / "longrun-observer"
CONFIG_NAME = "config.json"
OBSERVATIONS_NAME = "observations.jsonl"
EVALUATION_NAME = "evaluation.json"
OPEN_FAILURE_STATUSES = {"fail", "failed", "open", "blocked"}
OPEN_FAILURE_SEVERITIES = {"P0", "P1"}
FIXTURE_AT_VALUES = [
    "2026-01-01T00:00:00+00:00",
    "2026-01-03T00:00:00+00:00",
    "2026-01-05T00:00:00+00:00",
    "2026-01-07T00:00:00+00:00",
    "2026-01-09T00:00:00+00:00",
    "2026-01-11T00:00:00+00:00",
    "2026-01-13T00:00:00+00:00",
    "2026-01-16T00:00:00+00:00",
]
PASSING_FIXTURE_EVENTS = [
    ("project_initialized", "pass", ["project_install"], 1),
    ("requirement_change", "pass", ["requirement_change"], 1),
    ("role_session_continued", "pass", ["loom_role_session"], 1),
    ("failure_reflux", "pass", ["failure_reflux"], 2),
    ("knowledge_used", "pass", ["knowledge_recall"], 2),
    ("self_purification_decision", "pass", ["self_purification"], 2),
    ("persona_boundary_check", "pass", ["persona_boundary"], 3),
    ("cache_retention_check", "pass", ["cache_retention"], 3),
    ("requirement_change", "pass", ["requirement_change"], 3),
    ("revalidation", "pass", ["e2e_validation"], 1),
    ("revalidation", "pass", ["e2e_validation"], 2),
    ("revalidation", "pass", ["e2e_validation"], 3),
    ("prism_review", "pass", ["prism_review"], 3),
]


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def parse_time(value: str) -> dt.datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    parsed = dt.datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取 JSON：{path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON 必须是对象：{path}")
    return payload


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def project_root(raw: str) -> pathlib.Path:
    path = pathlib.Path(raw).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"项目目录不存在：{path}")
    if not path.is_dir():
        raise SystemExit(f"项目路径不是目录：{path}")
    return path


def state_dir(project: pathlib.Path) -> pathlib.Path:
    return project / STATE_REL


def evidence_dir(project: pathlib.Path) -> pathlib.Path:
    return project / EVIDENCE_REL


def config_path(project: pathlib.Path) -> pathlib.Path:
    return state_dir(project) / CONFIG_NAME


def observations_path(project: pathlib.Path) -> pathlib.Path:
    return state_dir(project) / OBSERVATIONS_NAME


def evaluation_path(project: pathlib.Path) -> pathlib.Path:
    return evidence_dir(project) / EVALUATION_NAME


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT_PATH)


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-longrun-observer-contract":
        failures.append("长期观察合同 schema_id 错误")
    if contract.get("schema_version") != 1:
        failures.append("长期观察合同 schema_version 必须为 1")
    capabilities = contract.get("required_capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        failures.append("长期观察合同缺少 required_capabilities")
    thresholds = contract.get("thresholds")
    if not isinstance(thresholds, dict):
        failures.append("长期观察合同缺少 thresholds")
    else:
        for key in [
            "min_duration_days",
            "min_calendar_days_observed",
            "min_iterations",
            "min_requirement_changes",
            "min_failure_reflux_cycles",
            "min_revalidations",
        ]:
            if not isinstance(thresholds.get(key), int) or thresholds[key] < 0:
                failures.append(f"thresholds.{key} 必须是非负整数")
    return failures


def init_project(project: pathlib.Path, sample_id: str | None = None) -> dict[str, Any]:
    contract = load_contract()
    failures = validate_contract(contract)
    if failures:
        return {"ok": False, "failures": failures}
    (project / PROJECT_REDCAP).mkdir(exist_ok=True)
    state_dir(project).mkdir(parents=True, exist_ok=True)
    evidence_dir(project).mkdir(parents=True, exist_ok=True)
    config = {
        "schema_id": "redcap-longrun-observer-config",
        "schema_version": 1,
        "created_at": iso_now(),
        "project": str(project),
        "sample_id": sample_id or project.name,
        "contract": "assets/contracts/longrun-observer.json",
        "thresholds": contract.get("thresholds", {}),
        "required_capabilities": contract.get("required_capabilities", []),
        "event_types": contract.get("event_types", []),
        "completion_boundary": "该观察器只判断 OL-11 是否具备关闭候选资格，不关闭 RedCap 完整复活终局目标。",
    }
    write_json(config_path(project), config)
    observations = observations_path(project)
    if not observations.exists():
        observations.write_text("", encoding="utf-8")
    return {
        "schema_id": "redcap-longrun-observer-init",
        "ok": True,
        "project": str(project),
        "config": str(config_path(project)),
        "observations": str(observations),
        "evaluation_default": str(evaluation_path(project)),
        "failures": [],
    }


def load_config(project: pathlib.Path) -> dict[str, Any]:
    path = config_path(project)
    if not path.exists():
        raise SystemExit(f"长期观察器尚未初始化：{path}")
    return load_json(path)


def valid_event_types(project: pathlib.Path) -> set[str]:
    config = load_config(project)
    values = config.get("event_types")
    return {str(item) for item in values if isinstance(item, str)} if isinstance(values, list) else set()


def record_event(
    project: pathlib.Path,
    *,
    event_type: str,
    summary: str,
    status: str,
    capabilities: list[str],
    evidence_refs: list[str],
    at: str | None = None,
    severity: str | None = None,
    iteration: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    allowed = valid_event_types(project)
    if event_type not in allowed:
        return {
            "schema_id": "redcap-longrun-observer-record",
            "ok": False,
            "failures": [f"未知观察事件类型：{event_type}"],
        }
    payload = {
        "schema_id": "redcap-longrun-observer-event",
        "schema_version": 1,
        "recorded_at": iso_now(),
        "at": at or iso_now(),
        "event_type": event_type,
        "summary": summary,
        "status": status,
        "severity": severity,
        "iteration": iteration,
        "capabilities": capabilities,
        "evidence_refs": evidence_refs,
        "metadata": metadata or {},
    }
    append_jsonl(observations_path(project), payload)
    return {
        "schema_id": "redcap-longrun-observer-record",
        "ok": True,
        "project": str(project),
        "observation": payload,
        "failures": [],
    }


def load_observations(project: pathlib.Path) -> list[dict[str, Any]]:
    path = observations_path(project)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            events.append({
                "schema_id": "redcap-longrun-observer-event",
                "event_type": "invalid_json",
                "status": "fail",
                "severity": "P0",
                "summary": f"第 {index} 行不是合法 JSON：{exc}",
                "capabilities": [],
                "evidence_refs": [],
                "at": iso_now(),
            })
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def event_time(event: dict[str, Any]) -> dt.datetime | None:
    value = event.get("at") or event.get("recorded_at")
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return parse_time(value)
    except ValueError:
        return None


def count_events(events: list[dict[str, Any]], event_type: str, passing_only: bool = False) -> int:
    total = 0
    for event in events:
        if event.get("event_type") != event_type:
            continue
        if passing_only and event.get("status") != "pass":
            continue
        total += 1
    return total


def capability_coverage(events: list[dict[str, Any]]) -> set[str]:
    covered: set[str] = set()
    for event in events:
        if event.get("status") not in {"pass", "accepted", "resolved"}:
            continue
        capabilities = event.get("capabilities")
        if not isinstance(capabilities, list):
            continue
        covered.update(str(item) for item in capabilities if isinstance(item, str) and item.strip())
    return covered


def open_p0_p1_failures(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for event in events:
        status = str(event.get("status") or "")
        severity = str(event.get("severity") or "")
        if status in OPEN_FAILURE_STATUSES and severity in OPEN_FAILURE_SEVERITIES:
            failures.append(event)
    return failures


def evaluate(project: pathlib.Path) -> dict[str, Any]:
    config = load_config(project)
    thresholds = config.get("thresholds") if isinstance(config.get("thresholds"), dict) else {}
    required_capabilities = [
        str(item)
        for item in config.get("required_capabilities", [])
        if isinstance(item, str) and item.strip()
    ]
    events = load_observations(project)
    times = [value for value in (event_time(event) for event in events) if value is not None]
    duration_days = 0
    calendar_days_observed = 0
    if times:
        duration_days = int((max(times) - min(times)).total_seconds() // 86400)
        calendar_days_observed = len({time.date().isoformat() for time in times})
    iterations = {
        int(event["iteration"])
        for event in events
        if isinstance(event.get("iteration"), int)
    }
    covered = capability_coverage(events)
    missing_capabilities = [capability for capability in required_capabilities if capability not in covered]
    gaps: list[str] = []
    if duration_days < int(thresholds.get("min_duration_days", 0)):
        gaps.append(f"观察跨度不足：{duration_days} 天")
    if calendar_days_observed < int(thresholds.get("min_calendar_days_observed", 0)):
        gaps.append(f"覆盖自然日不足：{calendar_days_observed} 天")
    if len(iterations) < int(thresholds.get("min_iterations", 0)):
        gaps.append(f"迭代轮次不足：{len(iterations)}")
    if count_events(events, "requirement_change", passing_only=True) < int(thresholds.get("min_requirement_changes", 0)):
        gaps.append("需求变更次数不足")
    if count_events(events, "failure_reflux", passing_only=True) < int(thresholds.get("min_failure_reflux_cycles", 0)):
        gaps.append("失败回流次数不足")
    if count_events(events, "revalidation", passing_only=True) < int(thresholds.get("min_revalidations", 0)):
        gaps.append("重新验收次数不足")
    if missing_capabilities:
        gaps.append(f"能力覆盖不足：{missing_capabilities}")
    prism_pass = any(event.get("event_type") == "prism_review" and event.get("status") == "pass" for event in events)
    if thresholds.get("required_final_prism_pass") is True and not prism_pass:
        gaps.append("缺少最终棱镜通过事件")
    open_failures = open_p0_p1_failures(events)
    if open_failures:
        decision = "needs_fix"
    elif gaps:
        decision = "continue_observing"
    else:
        decision = "eligible_to_close_ol11"
    return {
        "schema_id": "redcap-longrun-observer-evaluation",
        "schema_version": 1,
        "ok": decision == "eligible_to_close_ol11",
        "project": str(project),
        "decision": decision,
        "can_close_ol11_candidate": decision == "eligible_to_close_ol11",
        "must_continue": decision == "continue_observing",
        "must_fix": decision == "needs_fix",
        "event_count": len(events),
        "duration_days": duration_days,
        "calendar_days_observed": calendar_days_observed,
        "iterations": sorted(iterations),
        "required_capabilities": required_capabilities,
        "covered_capabilities": sorted(covered),
        "missing_capabilities": missing_capabilities,
        "open_p0_p1_failures": [
            {
                "event_type": event.get("event_type"),
                "summary": event.get("summary"),
                "status": event.get("status"),
                "severity": event.get("severity"),
            }
            for event in open_failures
        ],
        "gaps": gaps,
        "completion_boundary": "该结果只判断 OL-11 关闭候选资格，不直接关闭 RedCap 完整复活终局目标。",
        "failures": [] if decision == "eligible_to_close_ol11" else gaps,
    }


def seed_passing_fixture_events(project: pathlib.Path) -> list[str]:
    failures: list[str] = []
    for index, (event_type, status, capabilities, iteration) in enumerate(PASSING_FIXTURE_EVENTS):
        record = record_event(
            project,
            event_type=event_type,
            summary=f"fixture {event_type}",
            status=status,
            capabilities=capabilities,
            evidence_refs=[f".redcap/evidence/fixture/{event_type}.json"],
            at=FIXTURE_AT_VALUES[min(index, len(FIXTURE_AT_VALUES) - 1)],
            iteration=iteration,
        )
        if record.get("ok") is not True:
            failures.append(f"记录事件失败：{record.get('failures')}")
    return failures


def scenario_result(name: str, expected_decision: str, evaluation: dict[str, Any]) -> dict[str, Any]:
    actual = evaluation.get("decision")
    return {
        "name": name,
        "expected_decision": expected_decision,
        "actual_decision": actual,
        "ok": actual == expected_decision,
        "event_count": evaluation.get("event_count"),
        "gaps": evaluation.get("gaps", []),
        "open_p0_p1_failures": evaluation.get("open_p0_p1_failures", []),
    }


def run_scenario_test() -> dict[str, Any]:
    failures: list[str] = []
    scenarios: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="redcap-longrun-observer-scenarios-") as raw_tmp:
        root = pathlib.Path(raw_tmp)

        continue_project = root / "continue-observing"
        continue_project.mkdir()
        init_project(continue_project, sample_id="scenario-continue-observing")
        record_event(
            continue_project,
            event_type="project_initialized",
            summary="fixture short sample",
            status="pass",
            capabilities=["project_install"],
            evidence_refs=[".redcap/evidence/fixture/project-initialized.json"],
            at="2026-01-01T00:00:00+00:00",
            iteration=1,
        )
        scenarios.append(scenario_result("insufficient-sample-continues", "continue_observing", evaluate(continue_project)))

        eligible_project = root / "eligible"
        eligible_project.mkdir()
        init_project(eligible_project, sample_id="scenario-eligible")
        failures.extend(seed_passing_fixture_events(eligible_project))
        scenarios.append(scenario_result("complete-sample-eligible", "eligible_to_close_ol11", evaluate(eligible_project)))

        timeout_project = root / "timeout-or-open-failure"
        shutil.copytree(eligible_project, timeout_project)
        record_event(
            timeout_project,
            event_type="observer_verdict",
            summary="fixture stalled external sample requiring intervention",
            status="blocked",
            severity="P1",
            capabilities=[],
            evidence_refs=[".redcap/evidence/fixture/stalled-sample.json"],
            at="2026-01-17T00:00:00+00:00",
            iteration=3,
        )
        scenarios.append(scenario_result("open-p1-requires-fix", "needs_fix", evaluate(timeout_project)))

        invalid_project = root / "invalid-json"
        invalid_project.mkdir()
        init_project(invalid_project, sample_id="scenario-invalid-json")
        observations_path(invalid_project).write_text("{not valid json\n", encoding="utf-8")
        scenarios.append(scenario_result("invalid-observation-json-requires-fix", "needs_fix", evaluate(invalid_project)))

        unknown_project = root / "unknown-event"
        unknown_project.mkdir()
        init_project(unknown_project, sample_id="scenario-unknown-event")
        unknown = record_event(
            unknown_project,
            event_type="unknown_event",
            summary="fixture unknown event",
            status="pass",
            capabilities=[],
            evidence_refs=[],
        )
        scenarios.append({
            "name": "unknown-event-rejected",
            "expected_ok": False,
            "actual_ok": unknown.get("ok"),
            "ok": unknown.get("ok") is False,
            "failures": unknown.get("failures", []),
        })

    for item in scenarios:
        if item.get("ok") is not True:
            failures.append(f"场景失败：{item.get('name')}")
    return {
        "schema_id": "redcap-longrun-observer-scenario-test",
        "ok": not failures,
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "external_sample_boundary": "合成场景只验证观察器的判定能力；OL-11 关闭仍必须基于真实长期外部项目样本。",
        "failures": failures,
    }


def parse_metadata(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--metadata-json 不是合法 JSON：{exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("--metadata-json 必须是 JSON 对象")
    return payload


def cmd_init(args: argparse.Namespace) -> int:
    result = init_project(project_root(args.project), sample_id=args.sample_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_LONGRUN_OBSERVER_INIT_OK")
        return 0
    return 1


def cmd_record(args: argparse.Namespace) -> int:
    result = record_event(
        project_root(args.project),
        event_type=args.event_type,
        summary=args.summary,
        status=args.status,
        capabilities=args.capability,
        evidence_refs=args.evidence_ref,
        at=args.at,
        severity=args.severity,
        iteration=args.iteration,
        metadata=parse_metadata(args.metadata_json),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_LONGRUN_OBSERVER_RECORD_OK")
        return 0
    return 1


def cmd_evaluate(args: argparse.Namespace) -> int:
    project = project_root(args.project)
    result = evaluate(project)
    if args.out:
        write_json(pathlib.Path(args.out).expanduser().resolve(), result)
    elif args.write_default:
        write_json(evaluation_path(project), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("decision") == "needs_fix":
        return 2
    if result.get("decision") == "continue_observing":
        return 3
    print("REDCAP_LONGRUN_OBSERVER_EVALUATION_OK")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    project = project_root(args.project)
    failures: list[str] = []
    for path in [config_path(project), observations_path(project)]:
        if not path.exists():
            failures.append(f"缺少长期观察器文件：{path}")
    if not failures:
        try:
            result = evaluate(project)
        except SystemExit as exc:
            failures.append(str(exc))
            result = {}
    else:
        result = {}
    output = {
        "schema_id": "redcap-longrun-observer-check",
        "ok": not failures,
        "project": str(project),
        "evaluation_decision": result.get("decision"),
        "failures": failures,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if output["ok"]:
        print("REDCAP_LONGRUN_OBSERVER_CHECK_OK")
        return 0
    return 1


def self_check() -> dict[str, Any]:
    failures: list[str] = []
    contract_failures = validate_contract(load_contract())
    failures.extend(contract_failures)
    with tempfile.TemporaryDirectory(prefix="redcap-longrun-observer-") as raw_tmp:
        root = pathlib.Path(raw_tmp)
        project = root / "external-project"
        project.mkdir()
        init_result = init_project(project, sample_id="fixture")
        if init_result.get("ok") is not True:
            failures.append(f"初始化失败：{init_result.get('failures')}")
        empty = evaluate(project)
        if empty.get("decision") != "continue_observing":
            failures.append("空观察样本必须判定为 continue_observing")
        failures.extend(seed_passing_fixture_events(project))
        eligible = evaluate(project)
        if eligible.get("decision") != "eligible_to_close_ol11":
            failures.append(f"完整样本应具备关闭候选资格：{eligible.get('gaps')}")
        bad_project = root / "bad-project"
        shutil.copytree(project, bad_project)
        record_event(
            bad_project,
            event_type="observer_verdict",
            summary="fixture open P0",
            status="open",
            severity="P0",
            capabilities=[],
            evidence_refs=[".redcap/evidence/fixture/open-p0.json"],
            at="2026-01-17T00:00:00+00:00",
            iteration=3,
        )
        needs_fix = evaluate(bad_project)
        if needs_fix.get("decision") != "needs_fix":
            failures.append("存在开放 P0 时必须判定为 needs_fix")
    scenario_test = run_scenario_test()
    if scenario_test.get("ok") is not True:
        failures.append(f"合成场景测试失败：{scenario_test.get('failures')}")
    return {
        "schema_id": "redcap-longrun-observer-self-check",
        "ok": not failures,
        "failures": failures,
    }


def cmd_self_check(_: argparse.Namespace) -> int:
    result = self_check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_LONGRUN_OBSERVER_SELF_CHECK_OK")
        return 0
    return 1


def cmd_scenario_test(_: argparse.Namespace) -> int:
    result = run_scenario_test()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_LONGRUN_OBSERVER_SCENARIO_TEST_OK")
        return 0
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap 长期外部项目观察器")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--project", required=True)
    init.add_argument("--sample-id")
    init.set_defaults(func=cmd_init)
    record = sub.add_parser("record")
    record.add_argument("--project", required=True)
    record.add_argument("--event-type", required=True)
    record.add_argument("--summary", required=True)
    record.add_argument("--status", default="pass")
    record.add_argument("--severity")
    record.add_argument("--iteration", type=int)
    record.add_argument("--capability", action="append", default=[])
    record.add_argument("--evidence-ref", action="append", default=[])
    record.add_argument("--at")
    record.add_argument("--metadata-json")
    record.set_defaults(func=cmd_record)
    evaluate_cmd = sub.add_parser("evaluate")
    evaluate_cmd.add_argument("--project", required=True)
    evaluate_cmd.add_argument("--out")
    evaluate_cmd.add_argument("--write-default", action="store_true")
    evaluate_cmd.set_defaults(func=cmd_evaluate)
    check = sub.add_parser("check")
    check.add_argument("--project", required=True)
    check.set_defaults(func=cmd_check)
    sub.add_parser("scenario-test").set_defaults(func=cmd_scenario_test)
    sub.add_parser("self-check").set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

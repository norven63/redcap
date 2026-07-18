#!/usr/bin/env python3
"""长期外部项目观察器。"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import gzip
import hashlib
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
ISSUES_NAME = "issues.jsonl"
SAMPLE_REGISTRY_NAME = "sample-registry.json"
COLLECTOR_STATE_NAME = "collector-state.json"
LATEST_HANDOFF_NAME = "LATEST-HANDOFF.json"
ARCHIVE_DIR_NAME = "archive"
OPEN_FAILURE_STATUSES = {"fail", "failed", "open", "blocked"}
OPEN_FAILURE_SEVERITIES = {"P0", "P1"}
AUTO_COLLECT_EVIDENCE_SPECS = [
    {
        "path": ".redcap/evidence/e2e/requirements.json",
        "event_type": "requirement_change",
        "capabilities": ["requirement_change"],
        "summary": "E2E 需求已结构化记录",
        "iteration": 1,
    },
    {
        "path": ".redcap/evidence/e2e/acceptance-criteria.json",
        "event_type": "requirement_change",
        "capabilities": ["requirement_change"],
        "summary": "E2E 验收标准已结构化记录",
        "iteration": 1,
    },
    {
        "path": ".redcap/evidence/e2e/loom-role-session-manifest.json",
        "event_type": "role_session_continued",
        "capabilities": ["loom_role_session"],
        "summary": "Loom 角色会话证据已记录",
        "iteration": 1,
    },
    {
        "path": ".redcap/evidence/e2e/failure-reflux-audit.json",
        "event_type": "failure_reflux",
        "capabilities": ["failure_reflux"],
        "summary": "失败回流审计证据已记录",
        "iteration": 2,
    },
    {
        "path": ".redcap/evidence/e2e/knowledge-retrieval-evidence.json",
        "event_type": "knowledge_used",
        "capabilities": ["knowledge_recall"],
        "summary": "知识召回影响证据已记录",
        "iteration": 2,
    },
    {
        "path": ".redcap/evidence/e2e/runner-self-purification-resolution.json",
        "event_type": "self_purification_decision",
        "capabilities": ["self_purification"],
        "summary": "自我净化候选处理证据已记录",
        "iteration": 2,
    },
    {
        "path": ".redcap/evidence/e2e/persona-distillation-decision.json",
        "event_type": "persona_boundary_check",
        "capabilities": ["persona_boundary"],
        "summary": "Cap 人格边界证据已记录",
        "iteration": 3,
    },
    {
        "path": ".redcap/evidence/e2e/redcap-e2e-run-retention-after-run.json",
        "event_type": "cache_retention_check",
        "capabilities": ["cache_retention"],
        "summary": "E2E 缓存保留策略证据已记录",
        "iteration": 3,
    },
    {
        "path": ".redcap/evidence/e2e/iteration-02-change-summary.json",
        "event_type": "requirement_change",
        "capabilities": ["requirement_change"],
        "summary": "第二轮需求变更证据已记录",
        "iteration": 3,
    },
    {
        "path": ".redcap/evidence/e2e/final-runner-test-results.json",
        "event_type": "revalidation",
        "capabilities": ["e2e_validation"],
        "summary": "运行器最终测试证据已记录",
        "iteration": 3,
    },
    {
        "path": ".redcap/evidence/e2e/final-marker-validation.json",
        "event_type": "revalidation",
        "capabilities": ["e2e_validation"],
        "summary": "完成标记前验证证据已记录",
        "iteration": 3,
    },
    {
        "path": ".redcap/evidence/e2e/browser-inspection.json",
        "event_type": "revalidation",
        "capabilities": ["e2e_validation"],
        "summary": "浏览器检查证据已记录",
        "iteration": 3,
    },
    {
        "path": ".redcap/evidence/e2e/prism-assisted-review.json",
        "event_type": "prism_review",
        "capabilities": ["prism_review"],
        "summary": "棱镜协助评审证据已记录",
        "iteration": 3,
    },
]
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
    with jsonl_lock(path):
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


def issues_path(project: pathlib.Path) -> pathlib.Path:
    return evidence_dir(project) / ISSUES_NAME


def sample_registry_path(project: pathlib.Path) -> pathlib.Path:
    return state_dir(project) / SAMPLE_REGISTRY_NAME


def collector_state_path(project: pathlib.Path) -> pathlib.Path:
    return state_dir(project) / COLLECTOR_STATE_NAME


def latest_handoff_path(project: pathlib.Path) -> pathlib.Path:
    return evidence_dir(project) / LATEST_HANDOFF_NAME


def archive_dir(project: pathlib.Path) -> pathlib.Path:
    return evidence_dir(project) / ARCHIVE_DIR_NAME


def history_segment_dir(project: pathlib.Path) -> pathlib.Path:
    return archive_dir(project) / "history-segments"


def archive_run_dir(project: pathlib.Path, run_id: str) -> pathlib.Path:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in run_id).strip("-")
    return archive_dir(project) / (safe or "run")


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT_PATH)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: pathlib.Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


@contextlib.contextmanager
def jsonl_lock(path: pathlib.Path):
    lock_path = path.with_name(f".{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_handle, fcntl.LOCK_UN)


def write_bytes_atomic(path: pathlib.Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, path)


def project_relative(project: pathlib.Path, path: pathlib.Path) -> str:
    try:
        return path.resolve().relative_to(project.resolve()).as_posix()
    except ValueError:
        return str(path)


def load_optional_json(path: pathlib.Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "missing"
    except json.JSONDecodeError as exc:
        return None, f"invalid_json: {exc}"
    except OSError as exc:
        return None, f"read_error: {exc}"
    if not isinstance(payload, dict):
        return None, "json_not_object"
    return payload, None


def load_jsonl_objects(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def load_jsonl_objects_strict(path: pathlib.Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], []
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [], [f"无法读取 {path}: {exc}"]
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            failures.append(f"{path} 第 {index} 行不是合法 JSON: {exc}")
            continue
        if not isinstance(payload, dict):
            failures.append(f"{path} 第 {index} 行不是 JSON 对象")
            continue
        records.append(payload)
    return records, failures


def _write_jsonl_objects_unlocked(path: pathlib.Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def write_jsonl_objects(path: pathlib.Path, records: list[dict[str, Any]]) -> None:
    with jsonl_lock(path):
        _write_jsonl_objects_unlocked(path, records)


def history_segment_meta_paths(project: pathlib.Path, stream: str) -> list[pathlib.Path]:
    root = history_segment_dir(project)
    return sorted(root.glob(f"{stream}-*.jsonl.gz.meta.json")) if root.exists() else []


def verify_history_segments(project: pathlib.Path, stream: str) -> dict[str, Any]:
    failures: list[str] = []
    records: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    referenced_data_names: set[str] = set()
    expected_sequence = 1
    for meta_path in history_segment_meta_paths(project, stream):
        meta, error = load_optional_json(meta_path)
        if error or meta is None:
            failures.append(f"历史分段元数据不可读: {meta_path}: {error}")
            continue
        if meta.get("schema_id") != "redcap-longrun-observer-history-segment":
            failures.append(f"历史分段 schema 错误: {meta_path}")
            continue
        if meta.get("stream") != stream:
            failures.append(f"历史分段 stream 错误: {meta_path}")
            continue
        data_name = meta.get("data_file")
        if not isinstance(data_name, str) or pathlib.Path(data_name).name != data_name:
            failures.append(f"历史分段 data_file 非法: {meta_path}")
            continue
        referenced_data_names.add(data_name)
        data_path = meta_path.parent / data_name
        try:
            compressed = data_path.read_bytes()
        except OSError as exc:
            failures.append(f"历史分段数据不可读: {data_path}: {exc}")
            continue
        compressed_sha = hashlib.sha256(compressed).hexdigest()
        if compressed_sha != meta.get("compressed_sha256"):
            failures.append(f"历史分段压缩哈希不匹配: {data_path}")
            continue
        try:
            raw = gzip.decompress(compressed)
        except (OSError, EOFError) as exc:
            failures.append(f"历史分段无法解压: {data_path}: {exc}")
            continue
        if hashlib.sha256(raw).hexdigest() != meta.get("raw_sha256"):
            failures.append(f"历史分段原文哈希不匹配: {data_path}")
            continue
        segment_records: list[dict[str, Any]] = []
        for index, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                failures.append(f"历史分段 {data_path} 第 {index} 行非法: {exc}")
                continue
            if not isinstance(payload, dict):
                failures.append(f"历史分段 {data_path} 第 {index} 行不是对象")
                continue
            segment_records.append(payload)
        start_sequence = meta.get("start_sequence")
        end_sequence = meta.get("end_sequence")
        if start_sequence != expected_sequence:
            failures.append(
                f"历史分段序号不连续: {meta_path}, expected={expected_sequence}, actual={start_sequence}"
            )
        if meta.get("record_count") != len(segment_records):
            failures.append(f"历史分段记录数不匹配: {meta_path}")
        calculated_end = int(start_sequence or 0) + len(segment_records) - 1
        if end_sequence != calculated_end:
            failures.append(f"历史分段结束序号不匹配: {meta_path}")
        expected_sequence = calculated_end + 1
        records.extend(segment_records)
        segments.append({
            "meta": project_relative(project, meta_path),
            "data": project_relative(project, data_path),
            "record_count": len(segment_records),
            "start_sequence": start_sequence,
            "end_sequence": end_sequence,
            "raw_sha256": meta.get("raw_sha256"),
        })
    history_root = history_segment_dir(project)
    if history_root.exists():
        actual_data_names = {
            path.name
            for path in history_root.glob(f"{stream}-*.jsonl.gz")
            if path.is_file()
        }
        for orphan_name in sorted(actual_data_names - referenced_data_names):
            failures.append(f"发现没有元数据引用的历史分段数据: {history_root / orphan_name}")
    return {
        "ok": not failures,
        "stream": stream,
        "record_count": len(records),
        "segment_count": len(segments),
        "segments": segments,
        "records": records,
        "failures": failures,
    }


def write_history_segment(
    project: pathlib.Path,
    *,
    stream: str,
    run_id: str,
    records: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not records:
        return None
    existing = verify_history_segments(project, stream)
    if existing.get("ok") is not True:
        raise RuntimeError("; ".join(str(item) for item in existing.get("failures", [])))
    start_sequence = int(existing.get("record_count") or 0) + 1
    end_sequence = start_sequence + len(records) - 1
    raw = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        for record in records
    ).encode("utf-8")
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    raw_sha = hashlib.sha256(raw).hexdigest()
    compressed_sha = hashlib.sha256(compressed).hexdigest()
    safe_run = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in run_id).strip("-")
    data_name = f"{stream}-{start_sequence:012d}-{end_sequence:012d}-{safe_run or 'run'}-{raw_sha[:12]}.jsonl.gz"
    data_path = history_segment_dir(project) / data_name
    meta_path = data_path.with_suffix(data_path.suffix + ".meta.json")
    if data_path.exists() or meta_path.exists():
        raise RuntimeError(f"历史分段目标已存在，拒绝覆盖: {data_path}")
    write_bytes_atomic(data_path, compressed)
    meta = {
        "schema_id": "redcap-longrun-observer-history-segment",
        "schema_version": 1,
        "stream": stream,
        "run_id": run_id,
        "created_at": iso_now(),
        "data_file": data_name,
        "record_count": len(records),
        "start_sequence": start_sequence,
        "end_sequence": end_sequence,
        "raw_bytes": len(raw),
        "compressed_bytes": len(compressed),
        "raw_sha256": raw_sha,
        "compressed_sha256": compressed_sha,
        "first_recorded_at": records[0].get("recorded_at") or records[0].get("first_seen"),
        "last_recorded_at": records[-1].get("recorded_at") or records[-1].get("last_seen"),
    }
    write_json(meta_path, meta)
    return {
        "meta": project_relative(project, meta_path),
        "data": project_relative(project, data_path),
        **meta,
    }


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
        "auto_collection": contract.get("auto_collection", {}),
        "completion_boundary": "该观察器只判断 OL-11 是否具备关闭候选资格，不关闭 RedCap 完整复活终局目标。",
    }
    write_json(config_path(project), config)
    observations = observations_path(project)
    if not observations.exists():
        observations.write_text("", encoding="utf-8")
    if not issues_path(project).exists():
        issues_path(project).write_text("", encoding="utf-8")
    if not sample_registry_path(project).exists():
        write_json(sample_registry_path(project), {
            "schema_id": "redcap-longrun-observer-sample-registry",
            "schema_version": 1,
            "created_at": iso_now(),
            "samples": [],
        })
    if not collector_state_path(project).exists():
        write_json(collector_state_path(project), {
            "schema_id": "redcap-longrun-observer-collector-state",
            "schema_version": 1,
            "created_at": iso_now(),
            "latest_run_id": None,
            "latest_decision": None,
            "runs": [],
        })
    return {
        "schema_id": "redcap-longrun-observer-init",
        "ok": True,
        "project": str(project),
        "config": str(config_path(project)),
        "observations": str(observations),
        "issues": str(issues_path(project)),
        "latest_handoff": str(latest_handoff_path(project)),
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
    active, active_failures = load_jsonl_objects_strict(path)
    history = verify_history_segments(project, "observations")
    failures = [*history.get("failures", []), *active_failures]
    events = [*history.get("records", []), *active]
    for failure in failures:
        events.append({
            "schema_id": "redcap-longrun-observer-event",
            "event_type": "invalid_json",
            "status": "fail",
            "severity": "P0",
            "summary": f"长期观察历史完整性失败：{failure}",
            "capabilities": [],
            "evidence_refs": [project_relative(project, path)],
            "at": iso_now(),
        })
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


def issue_dedupe_key(
    *,
    run_id: str,
    issue_type: str,
    evidence_ref: str,
    summary: str,
    source_sha256: str | None,
) -> str:
    return sha256_text(stable_json({
        "run_id": run_id,
        "issue_type": issue_type,
        "evidence_ref": evidence_ref,
        "summary": summary,
        "source_sha256": source_sha256,
    }))


def upsert_issue(
    project: pathlib.Path,
    *,
    run_id: str,
    issue_type: str,
    summary: str,
    severity: str,
    decision_effect: str,
    evidence_ref: str,
    source_sha256: str | None = None,
    status: str = "open",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = iso_now()
    key = issue_dedupe_key(
        run_id=run_id,
        issue_type=issue_type,
        evidence_ref=evidence_ref,
        summary=summary,
        source_sha256=source_sha256,
    )
    path = issues_path(project)
    with jsonl_lock(path):
        records, failures = load_jsonl_objects_strict(path)
        if failures:
            raise RuntimeError("; ".join(failures))
        for record in records:
            if record.get("dedupe_key") != key:
                continue
            record["last_seen"] = now
            record["count"] = int(record.get("count") or 1) + 1
            record["status"] = status
            record["severity"] = severity
            record["decision_effect"] = decision_effect
            record["metadata"] = metadata or {}
            _write_jsonl_objects_unlocked(path, records)
            return record
        history_records = latest_issue_records(project)
        historical = history_records.get(key)
        if historical is not None:
            record = dict(historical)
            record["last_seen"] = now
            record["count"] = int(record.get("count") or 1) + 1
            record["status"] = status
            record["severity"] = severity
            record["decision_effect"] = decision_effect
            record["metadata"] = metadata or {}
        else:
            record = {
                "schema_id": "redcap-longrun-observer-issue",
                "schema_version": 1,
                "dedupe_key": key,
                "run_id": run_id,
                "issue_type": issue_type,
                "summary": summary,
                "severity": severity,
                "decision_effect": decision_effect,
                "status": status,
                "evidence_ref": evidence_ref,
                "source_sha256": source_sha256,
                "first_seen": now,
                "last_seen": now,
                "count": 1,
                "metadata": metadata or {},
            }
        records.append(record)
        _write_jsonl_objects_unlocked(path, records)
        return record


def resolve_recovered_evidence_issues(
    project: pathlib.Path,
    *,
    run_id: str,
    phase: str,
    present_refs: set[str],
) -> list[dict[str, Any]]:
    """Close stale missing/invalid evidence issues when the evidence is now present and readable."""
    path = issues_path(project)
    records = list(latest_issue_records(project).values())
    resolved: list[dict[str, Any]] = []
    now = iso_now()
    for record in records:
        if str(record.get("status") or "open") not in OPEN_FAILURE_STATUSES:
            continue
        issue_type = str(record.get("issue_type") or "")
        evidence_ref = str(record.get("evidence_ref") or "")
        if issue_type not in {"missing_evidence", "invalid_evidence_json"}:
            continue
        if evidence_ref not in present_refs:
            continue
        record["status"] = "resolved"
        record["decision_effect"] = "resolved"
        record["last_seen"] = now
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        record["metadata"] = {
            **metadata,
            "resolved_by_run_id": run_id,
            "resolved_phase": phase,
            "resolved_at": now,
            "resolution_reason": "evidence_ref_present_in_latest_auto_collect_scan",
        }
        resolved.append(record)
    if resolved:
        with jsonl_lock(path):
            active, failures = load_jsonl_objects_strict(path)
            if failures:
                raise RuntimeError("; ".join(failures))
            active_by_key = {
                str(record.get("dedupe_key")): index
                for index, record in enumerate(active)
                if isinstance(record.get("dedupe_key"), str)
            }
            for record in resolved:
                key = str(record.get("dedupe_key") or "")
                if key in active_by_key:
                    active[active_by_key[key]] = record
                else:
                    active.append(record)
            _write_jsonl_objects_unlocked(path, active)
    return resolved


def normalize_external_issue(raw: dict[str, Any], *, phase: str) -> dict[str, Any]:
    issue_type = str(raw.get("issue_type") or raw.get("type") or "external_observer_issue").strip()
    summary = str(raw.get("summary") or raw.get("message") or issue_type).strip()
    severity = str(raw.get("severity") or "P1").strip().upper()
    if severity not in {"P0", "P1", "P2", "P3"}:
        severity = "P1"
    default_effect = "needs_fix" if severity in OPEN_FAILURE_SEVERITIES else "continue_observing"
    decision_effect = str(raw.get("decision_effect") or default_effect).strip()
    evidence_ref = str(raw.get("evidence_ref") or raw.get("path") or ".redcap/evidence/longrun-observer/external-issue.json").strip()
    status = str(raw.get("status") or "open").strip()
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    metadata = {
        **metadata,
        "phase": metadata.get("phase") or phase,
        "external_issue_ingested": True,
    }
    return {
        "issue_type": issue_type or "external_observer_issue",
        "summary": summary or "外部观察问题",
        "severity": severity,
        "decision_effect": decision_effect or default_effect,
        "evidence_ref": evidence_ref or ".redcap/evidence/longrun-observer/external-issue.json",
        "source_sha256": raw.get("source_sha256") if isinstance(raw.get("source_sha256"), str) else None,
        "status": status or "open",
        "metadata": metadata,
    }


def external_issue_records_from_payload(payload: Any, *, phase: str) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        raw_issues = payload.get("issues") if isinstance(payload.get("issues"), list) else [payload]
    elif isinstance(payload, list):
        raw_issues = payload
    else:
        return []
    return [
        normalize_external_issue(item, phase=phase)
        for item in raw_issues
        if isinstance(item, dict)
    ]


def load_external_issue_records(paths: list[pathlib.Path], *, phase: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        payload, error = load_optional_json(path)
        if error or payload is None:
            records.append(normalize_external_issue({
                "issue_type": "external_issue_file_unreadable",
                "summary": f"外部问题文件不可读取：{path}: {error}",
                "severity": "P1",
                "decision_effect": "needs_fix",
                "evidence_ref": str(path),
                "source_sha256": sha256_file(path),
                "metadata": {"path": str(path), "read_error": error},
            }, phase=phase))
            continue
        records.extend(external_issue_records_from_payload(payload, phase=phase))
    return records


def ingest_external_issues(
    project: pathlib.Path,
    *,
    run_id: str,
    phase: str,
    external_issues: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    ingested: list[dict[str, Any]] = []
    record_results: list[dict[str, Any]] = []
    for issue in external_issues or []:
        normalized = normalize_external_issue(issue, phase=phase)
        record = upsert_issue(
            project,
            run_id=run_id,
            issue_type=normalized["issue_type"],
            summary=normalized["summary"],
            severity=normalized["severity"],
            decision_effect=normalized["decision_effect"],
            evidence_ref=normalized["evidence_ref"],
            source_sha256=normalized.get("source_sha256"),
            status=normalized["status"],
            metadata=normalized["metadata"],
        )
        ingested.append(record)
        if normalized["severity"] in OPEN_FAILURE_SEVERITIES:
            record_results.append(record_auto_event(
                project,
                run_id=run_id,
                event_type="observer_verdict",
                summary=normalized["summary"],
                status=normalized["status"],
                severity=normalized["severity"],
                capabilities=[],
                evidence_refs=[normalized["evidence_ref"]],
                metadata={"issue": record.get("dedupe_key"), "phase": phase, "external_issue_ingested": True},
            ))
    return {
        "ingested": ingested,
        "record_results": record_results,
    }


def latest_issue_records(project: pathlib.Path) -> dict[str, dict[str, Any]]:
    history = verify_history_segments(project, "issues")
    active, active_failures = load_jsonl_objects_strict(issues_path(project))
    records = [*history.get("records", []), *active]
    latest: dict[str, dict[str, Any]] = {}
    for index, issue in enumerate(records):
        key = str(issue.get("dedupe_key") or f"record-{index}")
        latest[key] = issue
    failures = [*history.get("failures", []), *active_failures]
    for index, failure in enumerate(failures):
        key = f"history-integrity-{index}-{sha256_text(failure)}"
        latest[key] = {
            "schema_id": "redcap-longrun-observer-issue",
            "schema_version": 1,
            "dedupe_key": key,
            "run_id": "history-integrity",
            "issue_type": "history_integrity_failure",
            "summary": f"长期观察问题历史完整性失败：{failure}",
            "severity": "P0",
            "decision_effect": "needs_fix",
            "status": "open",
            "evidence_ref": project_relative(project, history_segment_dir(project)),
            "source_sha256": sha256_text(failure),
            "first_seen": iso_now(),
            "last_seen": iso_now(),
            "count": 1,
            "metadata": {"integrity_failure": True},
        }
    return latest


def open_issue_records(project: pathlib.Path) -> list[dict[str, Any]]:
    return [
        issue
        for issue in latest_issue_records(project).values()
        if str(issue.get("status") or "open") in OPEN_FAILURE_STATUSES
    ]


def open_p0_p1_issues(project: pathlib.Path) -> list[dict[str, Any]]:
    return [
        issue
        for issue in open_issue_records(project)
        if str(issue.get("severity") or "") in OPEN_FAILURE_SEVERITIES
    ]


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
    open_issues = open_issue_records(project)
    open_blocking_issues = open_p0_p1_issues(project)
    if open_failures or open_blocking_issues:
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
        "open_issues": [
            {
                "issue_type": issue.get("issue_type"),
                "summary": issue.get("summary"),
                "status": issue.get("status"),
                "severity": issue.get("severity"),
                "decision_effect": issue.get("decision_effect"),
                "evidence_ref": issue.get("evidence_ref"),
                "dedupe_key": issue.get("dedupe_key"),
            }
            for issue in open_issues
        ],
        "open_p0_p1_issues": [
            {
                "issue_type": issue.get("issue_type"),
                "summary": issue.get("summary"),
                "status": issue.get("status"),
                "severity": issue.get("severity"),
                "decision_effect": issue.get("decision_effect"),
                "evidence_ref": issue.get("evidence_ref"),
                "dedupe_key": issue.get("dedupe_key"),
            }
            for issue in open_blocking_issues
        ],
        "gaps": gaps,
        "completion_boundary": "该结果只判断 OL-11 关闭候选资格，不直接关闭 RedCap 完整复活终局目标。",
        "failures": [] if decision == "eligible_to_close_ol11" else [
            *gaps,
            *[str(issue.get("summary") or issue.get("issue_type")) for issue in open_blocking_issues],
        ],
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


def retention_policy(project: pathlib.Path) -> dict[str, int]:
    config = load_config(project)
    auto_collection = config.get("auto_collection") if isinstance(config.get("auto_collection"), dict) else {}
    retention = auto_collection.get("retention") if isinstance(auto_collection.get("retention"), dict) else {}
    return {
        "max_observations_total": int(retention.get("max_observations_total", 400)),
        "max_issues_total": int(retention.get("max_issues_total", 400)),
        "max_archived_handoffs": int(retention.get("max_archived_handoffs", 20)),
    }


def record_auto_event(
    project: pathlib.Path,
    *,
    run_id: str,
    event_type: str,
    summary: str,
    status: str,
    capabilities: list[str],
    evidence_refs: list[str],
    severity: str | None = None,
    iteration: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dedupe = sha256_text(stable_json({
        "run_id": run_id,
        "event_type": event_type,
        "summary": summary,
        "evidence_refs": evidence_refs,
        "capabilities": capabilities,
        "severity": severity,
        "iteration": iteration,
    }))
    for event in load_observations(project):
        event_meta = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        if event_meta.get("auto_collect_dedupe_key") == dedupe:
            return {
                "schema_id": "redcap-longrun-observer-record",
                "ok": True,
                "deduped": True,
                "project": str(project),
                "observation": event,
                "failures": [],
            }
    merged_metadata = {
        "source": "longrun-observer auto-collect",
        "run_id": run_id,
        "auto_collect_dedupe_key": dedupe,
        **(metadata or {}),
    }
    return record_event(
        project,
        event_type=event_type,
        summary=summary,
        status=status,
        capabilities=capabilities,
        evidence_refs=evidence_refs,
        severity=severity,
        iteration=iteration,
        metadata=merged_metadata,
    )


def auto_collect_scan(project: pathlib.Path, *, run_id: str, phase: str, inject_open_failure: bool) -> dict[str, Any]:
    present: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for spec in AUTO_COLLECT_EVIDENCE_SPECS:
        rel = str(spec["path"])
        path = project / rel
        if not path.exists():
            issue = upsert_issue(
                project,
                run_id=run_id,
                issue_type="missing_evidence",
                summary=f"缺少自动观测证据：{rel}",
                severity="P2",
                decision_effect="continue_observing",
                evidence_ref=rel,
                metadata={"phase": phase, "rule": "missing evidence is observation gap unless it proves a failed completed step"},
            )
            missing.append({"path": rel, "issue": issue.get("dedupe_key")})
            issues.append(issue)
            continue
        digest = sha256_file(path)
        payload, error = load_optional_json(path)
        if error and error != "missing":
            issue = upsert_issue(
                project,
                run_id=run_id,
                issue_type="invalid_evidence_json",
                summary=f"自动观测证据不是合法 JSON：{rel}",
                severity="P1",
                decision_effect="needs_fix",
                evidence_ref=rel,
                source_sha256=digest,
                metadata={"phase": phase, "error": error},
            )
            invalid.append({"path": rel, "error": error, "issue": issue.get("dedupe_key")})
            issues.append(issue)
            records.append(record_auto_event(
                project,
                run_id=run_id,
                event_type="observer_verdict",
                summary=f"自动观测发现坏 JSON：{rel}",
                status="open",
                severity="P1",
                capabilities=[],
                evidence_refs=[rel],
                metadata={"issue": issue.get("dedupe_key"), "phase": phase},
            ))
            continue
        present.append({
            "path": rel,
            "sha256": digest,
            "schema_id": payload.get("schema_id") if isinstance(payload, dict) else None,
        })
        records.append(record_auto_event(
            project,
            run_id=run_id,
            event_type=str(spec["event_type"]),
            summary=str(spec["summary"]),
            status="pass",
            capabilities=[str(item) for item in spec.get("capabilities", [])],
            evidence_refs=[rel],
            iteration=int(spec.get("iteration") or 1),
            metadata={"phase": phase, "source_sha256": digest},
        ))
    if inject_open_failure:
        issue = upsert_issue(
            project,
            run_id=run_id,
            issue_type="injected_p1_fault",
            summary="自动观测故障注入：开放 P1 必须阻断验收",
            severity="P1",
            decision_effect="needs_fix",
            evidence_ref=".redcap/evidence/longrun-observer/injected-p1-fault.json",
            source_sha256=sha256_text(f"{project}:{run_id}:injected_p1_fault"),
            metadata={"phase": phase, "injected": True},
        )
        issues.append(issue)
        records.append(record_auto_event(
            project,
            run_id=run_id,
            event_type="observer_verdict",
            summary="自动观测故障注入：开放 P1 必须阻断验收",
            status="open",
            severity="P1",
            capabilities=[],
            evidence_refs=[".redcap/evidence/longrun-observer/injected-p1-fault.json"],
            metadata={"issue": issue.get("dedupe_key"), "phase": phase, "injected": True},
        ))
    return {
        "present": present,
        "missing": missing,
        "invalid": invalid,
        "issues": issues,
        "record_results": records,
    }


def compact_collector_files(project: pathlib.Path, run_id: str) -> dict[str, Any]:
    policy = retention_policy(project)
    archive = archive_run_dir(project, run_id)
    archive.mkdir(parents=True, exist_ok=True)
    result = {
        "schema_id": "redcap-longrun-observer-compaction",
        "run_id": run_id,
        "compacted_at": iso_now(),
        "observation_compacted": False,
        "issue_compacted": False,
        "history_segments": [],
        "history_integrity": {},
        "archive_pruned": [],
        "failures": [],
    }
    for stream, path, limit_key, result_key in [
        ("observations", observations_path(project), "max_observations_total", "observation_compacted"),
        ("issues", issues_path(project), "max_issues_total", "issue_compacted"),
    ]:
        maximum = max(50, policy[limit_key])
        with jsonl_lock(path):
            records, parse_failures = load_jsonl_objects_strict(path)
            if parse_failures:
                result["failures"].extend(parse_failures)
                continue
            if len(records) <= maximum:
                continue
            overflow = records[:-maximum]
            try:
                segment = write_history_segment(
                    project,
                    stream=stream,
                    run_id=run_id,
                    records=overflow,
                )
            except RuntimeError as exc:
                result["failures"].append(str(exc))
                continue
            if segment is None:
                continue
            _write_jsonl_objects_unlocked(path, records[-maximum:])
            result[result_key] = True
            result["history_segments"].append(segment)
    for stream in ["observations", "issues"]:
        integrity = verify_history_segments(project, stream)
        result["history_integrity"][stream] = {
            key: value
            for key, value in integrity.items()
            if key != "records"
        }
        result["failures"].extend(integrity.get("failures", []))
    max_archives = max(1, policy["max_archived_handoffs"])
    archives = sorted(
        [
            path
            for path in archive_dir(project).glob("*")
            if path.is_dir() and path.name != history_segment_dir(project).name
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if archive_dir(project).exists() else []
    for stale in archives[max_archives:]:
        shutil.rmtree(stale)
        result["archive_pruned"].append(stale.name)
    result["ok"] = not result["failures"]
    return result


def update_sample_registry(project: pathlib.Path, *, sample_id: str, run_id: str, decision: str, handoff: pathlib.Path) -> None:
    registry, error = load_optional_json(sample_registry_path(project))
    if error or registry is None:
        registry = {
            "schema_id": "redcap-longrun-observer-sample-registry",
            "schema_version": 1,
            "created_at": iso_now(),
            "samples": [],
        }
    samples = registry.get("samples") if isinstance(registry.get("samples"), list) else []
    updated = False
    for sample in samples:
        if isinstance(sample, dict) and sample.get("sample_id") == sample_id:
            sample.update({
                "project": str(project),
                "latest_run_id": run_id,
                "latest_decision": decision,
                "latest_handoff": project_relative(project, handoff),
                "updated_at": iso_now(),
            })
            updated = True
            break
    if not updated:
        samples.append({
            "sample_id": sample_id,
            "project": str(project),
            "latest_run_id": run_id,
            "latest_decision": decision,
            "latest_handoff": project_relative(project, handoff),
            "created_at": iso_now(),
            "updated_at": iso_now(),
        })
    registry["samples"] = samples
    registry["latest_sample_id"] = sample_id
    registry["latest_run_id"] = run_id
    registry["latest_decision"] = decision
    write_json(sample_registry_path(project), registry)


def write_handoff(
    project: pathlib.Path,
    *,
    sample_id: str,
    run_id: str,
    phase: str,
    scan: dict[str, Any],
    evaluation: dict[str, Any],
    compaction: dict[str, Any],
) -> dict[str, Any]:
    open_issues = open_issue_records(project)
    blocking_issues = open_p0_p1_issues(project)
    payload = {
        "schema_id": "redcap-longrun-observer-handoff",
        "schema_version": 1,
        "created_at": iso_now(),
        "sample_id": sample_id,
        "run_id": run_id,
        "phase": phase,
        "project": str(project),
        "decision": evaluation.get("decision"),
        "must_fix": evaluation.get("must_fix") is True,
        "must_continue": evaluation.get("must_continue") is True,
        "can_close_ol11_candidate": evaluation.get("can_close_ol11_candidate") is True,
        "issue_summary": {
            "open_count": len(open_issues),
            "blocking_count": len(blocking_issues),
            "blocking_issues": [
                {
                    "issue_type": issue.get("issue_type"),
                    "summary": issue.get("summary"),
                    "severity": issue.get("severity"),
                    "evidence_ref": issue.get("evidence_ref"),
                    "dedupe_key": issue.get("dedupe_key"),
                }
                for issue in blocking_issues
            ],
        },
        "evidence_summary": {
            "present_count": len(scan.get("present", [])),
            "missing_count": len(scan.get("missing", [])),
            "invalid_count": len(scan.get("invalid", [])),
            "present": scan.get("present", []),
            "missing": scan.get("missing", []),
            "invalid": scan.get("invalid", []),
        },
        "paths": {
            "observations": project_relative(project, observations_path(project)),
            "issues": project_relative(project, issues_path(project)),
            "evaluation": project_relative(project, evaluation_path(project)),
            "latest_handoff": project_relative(project, latest_handoff_path(project)),
            "sample_registry": project_relative(project, sample_registry_path(project)),
            "collector_state": project_relative(project, collector_state_path(project)),
        },
        "resume_command": f"runtime/bin/redcap longrun-observer resume --project {project}",
        "next_action": (
            "先修复 blocking_issues，再重新执行自动观测和 E2E。"
            if blocking_issues
            else "继续真实长期样本观察或进入人工触发的验收结果评估。"
        ),
        "compaction": compaction,
        "history_integrity_ok": compaction.get("ok") is True,
        "boundary": "该 handoff 只归档 OL-11 自动观测状态，不声明 RedCap 完整复活终局完成。",
    }
    write_json(latest_handoff_path(project), payload)
    archive = archive_run_dir(project, run_id)
    archive.mkdir(parents=True, exist_ok=True)
    write_json(archive / "handoff.json", payload)
    update_sample_registry(
        project,
        sample_id=sample_id,
        run_id=run_id,
        decision=str(evaluation.get("decision") or ""),
        handoff=latest_handoff_path(project),
    )
    state, error = load_optional_json(collector_state_path(project))
    if error or state is None:
        state = {
            "schema_id": "redcap-longrun-observer-collector-state",
            "schema_version": 1,
            "created_at": iso_now(),
            "runs": [],
        }
    runs = state.get("runs") if isinstance(state.get("runs"), list) else []
    runs.append({
        "run_id": run_id,
        "sample_id": sample_id,
        "phase": phase,
        "decision": evaluation.get("decision"),
        "created_at": payload["created_at"],
        "latest_handoff": project_relative(project, latest_handoff_path(project)),
    })
    state["runs"] = runs[-50:]
    state["latest_run_id"] = run_id
    state["latest_decision"] = evaluation.get("decision")
    state["updated_at"] = iso_now()
    write_json(collector_state_path(project), state)
    return payload


def auto_collect(
    project: pathlib.Path,
    *,
    sample_id: str | None = None,
    run_id: str | None = None,
    phase: str = "e2e-post-condition",
    inject_open_failure: bool = False,
    external_issues: list[dict[str, Any]] | None = None,
    write_default: bool = True,
) -> dict[str, Any]:
    if not config_path(project).exists():
        init_project(project, sample_id=sample_id)
    config = load_config(project)
    actual_sample_id = sample_id or str(config.get("sample_id") or project.name)
    actual_run_id = run_id or f"run-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    scan = auto_collect_scan(project, run_id=actual_run_id, phase=phase, inject_open_failure=inject_open_failure)
    present_refs = {
        str(item.get("path") or "")
        for item in scan.get("present", [])
        if isinstance(item, dict)
    }
    resolved_issues = resolve_recovered_evidence_issues(
        project,
        run_id=actual_run_id,
        phase=phase,
        present_refs=present_refs,
    )
    if resolved_issues:
        scan["resolved_issues"] = [
            {
                "dedupe_key": issue.get("dedupe_key"),
                "issue_type": issue.get("issue_type"),
                "evidence_ref": issue.get("evidence_ref"),
                "status": issue.get("status"),
            }
            for issue in resolved_issues
        ]
    external_issue_result = ingest_external_issues(
        project,
        run_id=actual_run_id,
        phase=phase,
        external_issues=external_issues,
    )
    scan["external_issues"] = external_issue_result["ingested"]
    scan["record_results"] = [
        *scan.get("record_results", []),
        *external_issue_result["record_results"],
    ]
    scan["issues"] = [
        *scan.get("issues", []),
        *external_issue_result["ingested"],
    ]
    compaction = compact_collector_files(project, actual_run_id)
    if compaction.get("ok") is not True:
        integrity_summary = "; ".join(str(item) for item in compaction.get("failures", []))
        issue = upsert_issue(
            project,
            run_id=actual_run_id,
            issue_type="history_integrity_failure",
            summary=f"长期观察历史压缩或完整性校验失败：{integrity_summary}",
            severity="P0",
            decision_effect="needs_fix",
            evidence_ref=project_relative(project, history_segment_dir(project)),
            source_sha256=sha256_text(integrity_summary),
            metadata={"phase": phase, "compaction": compaction},
        )
        scan["issues"].append(issue)
        scan["record_results"].append(record_auto_event(
            project,
            run_id=actual_run_id,
            event_type="observer_verdict",
            summary="长期观察历史完整性失败",
            status="open",
            severity="P0",
            capabilities=[],
            evidence_refs=[project_relative(project, history_segment_dir(project))],
            metadata={"phase": phase, "issue": issue.get("dedupe_key")},
        ))
    evaluation = evaluate(project)
    if write_default:
        write_json(evaluation_path(project), evaluation)
    handoff = write_handoff(
        project,
        sample_id=actual_sample_id,
        run_id=actual_run_id,
        phase=phase,
        scan=scan,
        evaluation=evaluation,
        compaction=compaction,
    )
    result = {
        "schema_id": "redcap-longrun-observer-auto-collect",
        "schema_version": 1,
        "ok": evaluation.get("decision") != "needs_fix",
        "project": str(project),
        "sample_id": actual_sample_id,
        "run_id": actual_run_id,
        "phase": phase,
        "decision": evaluation.get("decision"),
        "must_fix": evaluation.get("must_fix") is True,
        "must_continue": evaluation.get("must_continue") is True,
        "injected_open_failure": inject_open_failure,
        "external_issue_count": len(external_issue_result["ingested"]),
        "scan": scan,
        "evaluation": evaluation,
        "handoff": {
            "latest": str(latest_handoff_path(project)),
            "archive": str(archive_run_dir(project, actual_run_id) / "handoff.json"),
            "payload": handoff,
        },
        "failures": evaluation.get("failures", []) if evaluation.get("decision") == "needs_fix" else [],
    }
    return result


def resume(project: pathlib.Path) -> dict[str, Any]:
    handoff_path = latest_handoff_path(project)
    handoff, handoff_error = load_optional_json(handoff_path)
    registry, registry_error = load_optional_json(sample_registry_path(project))
    state, state_error = load_optional_json(collector_state_path(project))
    failures: list[str] = []
    if handoff_error or handoff is None:
        failures.append(f"缺少可恢复 handoff：{handoff_path}: {handoff_error}")
    if registry_error or registry is None:
        failures.append(f"缺少 sample registry：{sample_registry_path(project)}: {registry_error}")
    if state_error or state is None:
        failures.append(f"缺少 collector state：{collector_state_path(project)}: {state_error}")
    history_integrity = {
        stream: verify_history_segments(project, stream)
        for stream in ["observations", "issues"]
    }
    for stream, integrity in history_integrity.items():
        failures.extend(f"{stream}: {failure}" for failure in integrity.get("failures", []))
    return {
        "schema_id": "redcap-longrun-observer-resume",
        "schema_version": 1,
        "ok": not failures,
        "project": str(project),
        "handoff_path": str(handoff_path),
        "handoff": handoff,
        "sample_registry": registry,
        "collector_state": state,
        "history_integrity": {
            stream: {key: value for key, value in integrity.items() if key != "records"}
            for stream, integrity in history_integrity.items()
        },
        "new_session_instruction": (
            "读取 handoff.issue_summary、evidence_summary 和 next_action；若 must_fix=true，先修复阻断问题并重跑 E2E；"
            "若只有 must_continue=true，则继续真实长期样本观察或由用户触发验收结果评估。"
        ),
        "failures": failures,
    }


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


def write_auto_collect_fixture_evidence(project: pathlib.Path) -> None:
    for spec in AUTO_COLLECT_EVIDENCE_SPECS:
        rel = str(spec["path"])
        path = project / rel
        write_json(path, {
            "schema_id": "redcap-auto-collect-fixture-evidence",
            "path": rel,
            "ok": True,
            "status": "pass",
            "producer": "longrun-observer-scenario-test",
        })


def run_auto_collect_scenario_test() -> dict[str, Any]:
    failures: list[str] = []
    scenarios: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="redcap-longrun-auto-collect-") as raw_tmp:
        root = pathlib.Path(raw_tmp)

        positive = root / "positive"
        positive.mkdir()
        init_project(positive, sample_id="scenario-auto-positive")
        write_auto_collect_fixture_evidence(positive)
        positive_result = auto_collect(
            positive,
            sample_id="scenario-auto-positive",
            run_id="scenario-auto-positive-run",
            phase="scenario-positive",
        )
        positive_resume = resume(positive)
        scenarios.append({
            "name": "auto-collect-positive-handoff-resume",
            "expected_decision": "continue_observing",
            "actual_decision": positive_result.get("decision"),
            "ok": (
                positive_result.get("decision") == "continue_observing"
                and positive_result.get("must_fix") is False
                and latest_handoff_path(positive).exists()
                and (archive_run_dir(positive, "scenario-auto-positive-run") / "handoff.json").exists()
                and positive_resume.get("ok") is True
            ),
            "handoff": str(latest_handoff_path(positive)),
            "resume_ok": positive_resume.get("ok"),
        })

        injected = root / "injected"
        shutil.copytree(positive, injected)
        injected_result = auto_collect(
            injected,
            sample_id="scenario-auto-injected",
            run_id="scenario-auto-injected-run",
            phase="scenario-injected",
            inject_open_failure=True,
        )
        injected_issues = load_jsonl_objects(issues_path(injected))
        scenarios.append({
            "name": "auto-collect-injected-p1-requires-fix",
            "expected_decision": "needs_fix",
            "actual_decision": injected_result.get("decision"),
            "ok": (
                injected_result.get("decision") == "needs_fix"
                and any(issue.get("issue_type") == "injected_p1_fault" for issue in injected_issues)
                and injected_result.get("must_fix") is True
            ),
            "issue_count": len(injected_issues),
        })

        invalid = root / "invalid"
        invalid.mkdir()
        init_project(invalid, sample_id="scenario-auto-invalid")
        write_auto_collect_fixture_evidence(invalid)
        (invalid / AUTO_COLLECT_EVIDENCE_SPECS[0]["path"]).write_text("{bad json\n", encoding="utf-8")
        invalid_result = auto_collect(
            invalid,
            sample_id="scenario-auto-invalid",
            run_id="scenario-auto-invalid-run",
            phase="scenario-invalid-json",
        )
        scenarios.append({
            "name": "auto-collect-invalid-json-requires-fix",
            "expected_decision": "needs_fix",
            "actual_decision": invalid_result.get("decision"),
            "ok": invalid_result.get("decision") == "needs_fix" and invalid_result.get("must_fix") is True,
        })

        missing = root / "missing"
        missing.mkdir()
        init_project(missing, sample_id="scenario-auto-missing")
        missing_result = auto_collect(
            missing,
            sample_id="scenario-auto-missing",
            run_id="scenario-auto-missing-run",
            phase="scenario-missing",
        )
        missing_issues = load_jsonl_objects(issues_path(missing))
        scenarios.append({
            "name": "auto-collect-missing-evidence-continues",
            "expected_decision": "continue_observing",
            "actual_decision": missing_result.get("decision"),
            "ok": (
                missing_result.get("decision") == "continue_observing"
                and missing_result.get("must_fix") is False
                and any(issue.get("issue_type") == "missing_evidence" for issue in missing_issues)
            ),
            "missing_issue_count": sum(1 for issue in missing_issues if issue.get("issue_type") == "missing_evidence"),
        })
        write_auto_collect_fixture_evidence(missing)
        recovered_result = auto_collect(
            missing,
            sample_id="scenario-auto-missing",
            run_id="scenario-auto-recovered-run",
            phase="scenario-recovered",
        )
        recovered_issues = load_jsonl_objects(issues_path(missing))
        unresolved_missing = [
            issue
            for issue in recovered_issues
            if issue.get("issue_type") == "missing_evidence"
            and str(issue.get("status") or "open") in OPEN_FAILURE_STATUSES
        ]
        resolved_missing = [
            issue
            for issue in recovered_issues
            if issue.get("issue_type") == "missing_evidence"
            and issue.get("status") == "resolved"
        ]
        scenarios.append({
            "name": "auto-collect-recovered-evidence-closes-missing-issues",
            "expected_decision": "continue_observing",
            "actual_decision": recovered_result.get("decision"),
            "ok": (
                recovered_result.get("decision") == "continue_observing"
                and not unresolved_missing
                and len(resolved_missing) >= len(AUTO_COLLECT_EVIDENCE_SPECS)
                and bool(recovered_result.get("scan", {}).get("resolved_issues"))
            ),
            "resolved_missing_count": len(resolved_missing),
            "unresolved_missing_count": len(unresolved_missing),
        })

        dedupe = root / "dedupe"
        dedupe.mkdir()
        init_project(dedupe, sample_id="scenario-auto-dedupe")
        write_auto_collect_fixture_evidence(dedupe)
        auto_collect(dedupe, sample_id="scenario-auto-dedupe", run_id="same-run", phase="scenario-dedupe")
        auto_collect(dedupe, sample_id="scenario-auto-dedupe", run_id="same-run", phase="scenario-dedupe")
        observations = load_jsonl_objects(observations_path(dedupe))
        issues = load_jsonl_objects(issues_path(dedupe))
        scenarios.append({
            "name": "auto-collect-idempotent-same-run",
            "ok": len(observations) <= len(AUTO_COLLECT_EVIDENCE_SPECS) + 1 and len(issues) == 0,
            "observation_count": len(observations),
            "issue_count": len(issues),
        })

        external = root / "external"
        external.mkdir()
        init_project(external, sample_id="scenario-auto-external-issue")
        write_auto_collect_fixture_evidence(external)
        external_result = auto_collect(
            external,
            sample_id="scenario-auto-external-issue",
            run_id="scenario-auto-external-issue-run",
            phase="scenario-external-issue",
            external_issues=[{
                "issue_type": "harness_timeout",
                "summary": "外层 E2E harness 超时必须进入长期观察器问题账本",
                "severity": "P1",
                "decision_effect": "needs_fix",
                "evidence_ref": ".redcap/evidence/e2e/harness-summary.json",
                "source_sha256": sha256_text("scenario-auto-external-issue"),
            }],
        )
        external_issues = load_jsonl_objects(issues_path(external))
        scenarios.append({
            "name": "auto-collect-external-p1-issue-requires-fix",
            "expected_decision": "needs_fix",
            "actual_decision": external_result.get("decision"),
            "ok": (
                external_result.get("decision") == "needs_fix"
                and external_result.get("external_issue_count") == 1
                and any(issue.get("issue_type") == "harness_timeout" for issue in external_issues)
                and latest_handoff_path(external).exists()
            ),
            "issue_count": len(external_issues),
        })

    for item in scenarios:
        if item.get("ok") is not True:
            failures.append(f"自动收集场景失败：{item.get('name')}")
    return {
        "schema_id": "redcap-longrun-observer-auto-collect-scenario-test",
        "ok": not failures,
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "external_sample_boundary": "合成场景只验证自动收集、故障感知和恢复能力；真实长期外部样本仍需单独运行。",
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
    history_integrity = {
        stream: verify_history_segments(project, stream)
        for stream in ["observations", "issues"]
    }
    for stream, integrity in history_integrity.items():
        failures.extend(f"{stream}: {failure}" for failure in integrity.get("failures", []))
    output = {
        "schema_id": "redcap-longrun-observer-check",
        "ok": not failures,
        "project": str(project),
        "evaluation_decision": result.get("decision"),
        "history_integrity": {
            stream: {key: value for key, value in integrity.items() if key != "records"}
            for stream, integrity in history_integrity.items()
        },
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
        history_project = root / "history-project"
        history_project.mkdir()
        init_project(history_project, sample_id="history-fixture")
        config = load_config(history_project)
        config["auto_collection"]["retention"] = {
            "max_observations_total": 50,
            "max_issues_total": 50,
            "max_archived_handoffs": 2,
        }
        write_json(config_path(history_project), config)
        for index in range(75):
            record_event(
                history_project,
                event_type="project_initialized",
                summary=f"history event {index}",
                status="pass",
                capabilities=["project_install"],
                evidence_refs=[f".redcap/evidence/fixture/history-{index}.json"],
                iteration=1,
            )
            upsert_issue(
                history_project,
                run_id=f"history-run-{index}",
                issue_type="history_fixture",
                summary=f"history issue {index}",
                severity="P2",
                decision_effect="continue_observing",
                evidence_ref=f".redcap/evidence/fixture/history-issue-{index}.json",
            )
        compaction = compact_collector_files(history_project, "history-compaction")
        observation_history = verify_history_segments(history_project, "observations")
        issue_history = verify_history_segments(history_project, "issues")
        if compaction.get("ok") is not True:
            failures.append(f"历史分段压缩失败：{compaction.get('failures')}")
        if observation_history.get("record_count") != 25 or issue_history.get("record_count") != 25:
            failures.append("历史分段没有保存全部溢出记录")
        if len(load_observations(history_project)) != 75:
            failures.append("历史分段重放后观察记录总数不完整")
        if len(latest_issue_records(history_project)) != 75:
            failures.append("历史分段重放后问题记录总数不完整")
        for run_index in range(4):
            run_archive = archive_run_dir(history_project, f"prune-{run_index}")
            run_archive.mkdir(parents=True, exist_ok=True)
            write_json(run_archive / "handoff.json", {"run": run_index})
        prune_result = compact_collector_files(history_project, "prune-final")
        if not history_segment_dir(history_project).exists() or verify_history_segments(history_project, "observations").get("ok") is not True:
            failures.append("handoff 轮转错误删除了不可变历史分段")
        if len(prune_result.get("archive_pruned", [])) < 2:
            failures.append("handoff 归档轮转没有按上限执行")
        orphan_segment = history_segment_dir(history_project) / "observations-999999999999-999999999999-orphan.jsonl.gz"
        orphan_segment.write_bytes(gzip.compress(b'{}\n', compresslevel=9, mtime=0))
        if verify_history_segments(history_project, "observations").get("ok") is not False:
            failures.append("没有元数据引用的孤儿历史分段未被发现")
        orphan_segment.unlink()
        observation_meta = history_segment_meta_paths(history_project, "observations")[0]
        observation_meta_payload = load_json(observation_meta)
        observation_data = observation_meta.parent / str(observation_meta_payload["data_file"])
        observation_data.write_bytes(observation_data.read_bytes() + b"tamper")
        if verify_history_segments(history_project, "observations").get("ok") is not False:
            failures.append("历史分段篡改没有被完整性校验发现")
    scenario_test = run_scenario_test()
    if scenario_test.get("ok") is not True:
        failures.append(f"合成场景测试失败：{scenario_test.get('failures')}")
    auto_collect_test = run_auto_collect_scenario_test()
    if auto_collect_test.get("ok") is not True:
        failures.append(f"自动收集场景测试失败：{auto_collect_test.get('failures')}")
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


def cmd_auto_collect(args: argparse.Namespace) -> int:
    issue_paths = [
        pathlib.Path(path).expanduser().resolve()
        for path in (args.issue_json or [])
    ]
    result = auto_collect(
        project_root(args.project),
        sample_id=args.sample_id,
        run_id=args.run_id,
        phase=args.phase,
        inject_open_failure=args.inject_open_failure,
        external_issues=load_external_issue_records(issue_paths, phase=args.phase),
        write_default=True,
    )
    if args.out:
        write_json(pathlib.Path(args.out).expanduser().resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("decision") == "needs_fix":
        return 2
    print("REDCAP_LONGRUN_OBSERVER_AUTO_COLLECT_OK")
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    result = resume(project_root(args.project))
    if args.out:
        write_json(pathlib.Path(args.out).expanduser().resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_LONGRUN_OBSERVER_RESUME_OK")
        return 0
    return 1


def cmd_auto_collect_scenario_test(_: argparse.Namespace) -> int:
    result = run_auto_collect_scenario_test()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_LONGRUN_OBSERVER_AUTO_COLLECT_SCENARIO_TEST_OK")
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
    auto_collect_cmd = sub.add_parser("auto-collect")
    auto_collect_cmd.add_argument("--project", required=True)
    auto_collect_cmd.add_argument("--sample-id")
    auto_collect_cmd.add_argument("--run-id")
    auto_collect_cmd.add_argument("--phase", default="e2e-post-condition")
    auto_collect_cmd.add_argument("--inject-open-failure", action="store_true")
    auto_collect_cmd.add_argument("--issue-json", action="append", default=[])
    auto_collect_cmd.add_argument("--out")
    auto_collect_cmd.set_defaults(func=cmd_auto_collect)
    resume_cmd = sub.add_parser("resume")
    resume_cmd.add_argument("--project", required=True)
    resume_cmd.add_argument("--out")
    resume_cmd.set_defaults(func=cmd_resume)
    sub.add_parser("scenario-test").set_defaults(func=cmd_scenario_test)
    sub.add_parser("auto-collect-scenario-test").set_defaults(func=cmd_auto_collect_scenario_test)
    sub.add_parser("self-check").set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

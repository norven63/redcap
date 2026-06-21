#!/usr/bin/env python3
"""RedCap long-task parent-objective governance.

This module decides whether a task should enter heavy long-task mode and
validates the contracts for policy templates and active long-task runs. It does
not execute user project work.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import datetime as dt
import fcntl
import hashlib
import json
import pathlib
import tempfile
import sys
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_ID = "redcap-long-task-contract"
VALID_MODES = {"enabled", "fast_path"}
CONTRACT_KINDS = {"policy_template", "active_run"}
VALID_TRIGGERS = {
    "user_explicit_long_run",
    "redcap_self_development_medium_or_higher",
    "external_e2e_or_release_validation",
    "multi_role_loom_workflow",
    "multi_iteration_failure_repair",
    "cross_workspace_or_runtime_boundary_change",
}
FAST_PATH_SIGNALS = {
    "low_risk",
    "answer_only_or_review_only",
    "single_step_or_small_patch",
    "no_cross_role_no_e2e_no_release_no_self_development",
}
RISK_LEVELS = {"low", "medium", "high", "critical"}
ITERATION_STATUSES = {"planned", "running", "passed", "failed", "blocked", "arbitrated"}
ACTIVE_RUN_STATES = {"running", "completed", "failed", "blocked", "human_decision"}
CAPABILITY_LAYERS = {
    "task_entry_decision",
    "generic_active_run_entry",
    "contract_validation",
    "active_run_ledger",
    "failure_backlog",
    "completion_boundary_guard",
    "stable_evidence_policy",
    "aggregate_check_integration",
    "prism_review_resolution",
}
REQUIRED_CODE_POINTERS = {
    "runtime/bin/redcap": "long-task check|decide|start|record|complete|boundary-check|self-check",
    "runtime/core/check_runner.py": "long-task-contract-self-check",
}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
MIN_ACTION_EVIDENCE_BYTES = 80
MIN_ACTION_EVIDENCE_UNIQUE_CHARS = 8
EVIDENCE_MEANING_MARKERS = {
    "command",
    "stdout",
    "stderr",
    "exit_code",
    "ok",
    "passed",
    "failed",
    "changed",
    "modified",
    "verified",
    "test",
    "check",
    "evidence",
    "result",
    "命令",
    "输出",
    "退出码",
    "通过",
    "失败",
    "检查",
    "验证",
    "证据",
    "变更",
    "修复",
    "产物",
}
COMPLETION_RELEVANCE_MARKERS = {
    "active_run",
    "完成",
    "终止",
    "关闭",
    "收口",
    "验收",
    "回执",
    "证据",
    "测试",
    "检查",
    "通过",
    "失败",
    "产物",
    "源码",
    "变更",
    "修复",
}


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"contract must be a JSON object: {path}")
    return payload


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def non_empty_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(non_empty_string(item) for item in value)


def substantive(value: Any, *, min_len: int = 12) -> bool:
    return non_empty_string(value) and len(str(value).strip()) >= min_len


def list_values(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def risk_at_least(risk_level: str, minimum: str) -> bool:
    return RISK_ORDER.get(risk_level, -1) >= RISK_ORDER[minimum]


def contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.casefold()
    return any(needle.casefold() in lowered for needle in needles)


def request_text_from_file(path: pathlib.Path) -> str:
    content = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return content
    if not isinstance(payload, dict):
        return content
    parts: list[str] = []
    for key in [
        "task",
        "user_intent",
        "main_claim",
        "requested_outcome",
        "source_prompt_excerpt",
    ]:
        value = payload.get(key)
        if isinstance(value, str):
            parts.append(value)
    for key in ["changed_reality", "known_constraints", "questions_for_prism"]:
        value = payload.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value if isinstance(item, str))
    return "\n".join(parts) if parts else content


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@contextlib.contextmanager
def packet_lock(packet_path: pathlib.Path):
    lock_path = packet_path.with_suffix(packet_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_long_task_template() -> dict[str, Any]:
    path = REPO_ROOT / "assets" / "contracts" / "long-task-contract.json"
    if path.exists():
        return load_json(path)
    return valid_enabled_fixture()


def source_signature() -> str:
    records: list[dict[str, str]] = []
    for rel in [
        "runtime/core/long_task_contract.py",
        "runtime/bin/redcap",
        "assets/contracts/long-task-contract.json",
    ]:
        path = REPO_ROOT / rel
        if not path.exists():
            records.append({"path": rel, "sha256": "missing"})
            continue
        records.append({"path": rel, "sha256": sha256_text(path.read_text(encoding="utf-8"))})
    return sha256_text(json.dumps(records, ensure_ascii=False, sort_keys=True))


def entry_evidence_signature(task_text: str, decision: dict[str, Any], run_dir: pathlib.Path) -> str:
    existing_files: list[dict[str, Any]] = []
    if run_dir.exists():
        for path in sorted(run_dir.glob("*")):
            if path.is_file():
                existing_files.append({
                    "name": path.name,
                    "size": path.stat().st_size,
                    "sha256": sha256_text(path.read_text(encoding="utf-8", errors="replace")),
                })
    return sha256_text(json.dumps({
        "task_sha256": sha256_text(task_text),
        "decision": decision,
        "run_dir": str(run_dir),
        "existing_files": existing_files,
    }, ensure_ascii=False, sort_keys=True))


def iteration_evidence_signature(packet_path: pathlib.Path, action_evidence: list[str], objective_delta: str) -> str:
    evidence_records: list[dict[str, Any]] = []
    for item in action_evidence:
        path = resolve_evidence_path(packet_path, item)
        record: dict[str, Any] = {"reference": item}
        if path.exists() and path.is_file():
            record.update({
                "size": path.stat().st_size,
                "sha256": sha256_text(path.read_text(encoding="utf-8", errors="replace")),
            })
        evidence_records.append(record)
    return sha256_text(json.dumps({
        "packet": str(packet_path),
        "objective_delta": objective_delta,
        "action_evidence": evidence_records,
    }, ensure_ascii=False, sort_keys=True))


def resolve_evidence_path(packet_path: pathlib.Path, reference: str) -> pathlib.Path:
    path = pathlib.Path(reference)
    if path.is_absolute():
        return path
    return packet_path.parent / path


def validate_action_evidence_files(packet_path: pathlib.Path, action_evidence: list[str]) -> list[str]:
    failures: list[str] = []
    for index, item in enumerate(action_evidence):
        path = resolve_evidence_path(packet_path, item)
        if not path.exists():
            failures.append(f"action_evidence[{index}] file does not exist: {item}")
            continue
        if not path.is_file():
            failures.append(f"action_evidence[{index}] must be a file: {item}")
            continue
        size = path.stat().st_size
        if size < MIN_ACTION_EVIDENCE_BYTES:
            failures.append(
                f"action_evidence[{index}] file must be at least {MIN_ACTION_EVIDENCE_BYTES} bytes: {item}"
            )
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        visible = "".join(ch for ch in text if not ch.isspace())
        if len(set(visible)) < MIN_ACTION_EVIDENCE_UNIQUE_CHARS:
            failures.append(
                f"action_evidence[{index}] file must contain meaningful varied content: {item}"
            )
    return failures


def evidence_quality_record(packet_path: pathlib.Path, reference: str) -> dict[str, Any]:
    path = resolve_evidence_path(packet_path, reference)
    record: dict[str, Any] = {
        "reference": reference,
        "resolved_path": str(path),
        "exists": path.exists(),
    }
    if not path.exists() or not path.is_file():
        record["confidence"] = "missing"
        record["signals"] = []
        return record
    text = path.read_text(encoding="utf-8", errors="replace")
    lowered = text.casefold()
    signals = sorted(marker for marker in EVIDENCE_MEANING_MARKERS if marker.casefold() in lowered)
    structured = False
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        structured = any(key in parsed for key in ["schema_id", "command", "exit_code", "ok", "stdout", "stderr"])
    if structured or len(signals) >= 2:
        confidence = "high"
    elif signals:
        confidence = "medium"
    else:
        confidence = "low"
    record.update({
        "bytes": path.stat().st_size,
        "sha256": sha256_text(text),
        "confidence": confidence,
        "signals": signals,
        "structured": structured,
    })
    return record


def evidence_quality(packet_path: pathlib.Path, evidence: list[str]) -> list[dict[str, Any]]:
    return [evidence_quality_record(packet_path, item) for item in evidence]


def low_confidence_evidence(quality_records: list[dict[str, Any]]) -> list[str]:
    return [
        str(item.get("reference"))
        for item in quality_records
        if item.get("confidence") in {"low", "missing"}
    ]


def completion_relevance_failures(
    packet_path: pathlib.Path,
    completion_evidence: list[str],
    final_objective_delta: str,
    final_summary: str,
) -> list[str]:
    final_text = f"{final_objective_delta}\n{final_summary}"
    expected_markers = [
        marker
        for marker in sorted(COMPLETION_RELEVANCE_MARKERS)
        if marker.casefold() in final_text.casefold()
    ]
    if not expected_markers:
        expected_markers = ["完成", "证据", "验收", "回执"]
    failures: list[str] = []
    for index, item in enumerate(completion_evidence):
        path = resolve_evidence_path(packet_path, item)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not any(marker.casefold() in text.casefold() for marker in expected_markers):
            failures.append(
                f"completion_evidence[{index}] lacks task-relevant completion markers: {item}"
            )
    return failures


def decide_long_task_mode(
    task_text: str,
    *,
    risk_level: str,
    consecutive_failures: int = 0,
    boundary_count: int = 0,
    external_goal_status: str | None = None,
) -> dict[str, Any]:
    triggers: list[str] = []
    fast_path_signals: list[str] = []
    explicit_long_run = contains_any(task_text, [
        "持续推进",
        "直到完成",
        "直至完成",
        "循环往复",
        "不要停",
        "一气呵成",
        "所有目标",
        "全部完成",
        "长任务",
        "long task",
        "loop",
    ])
    e2e_or_release = contains_any(task_text, [
        "e2e",
        "端到端",
        "发布",
        "验收",
        "release",
        "生产",
        "交付",
    ])
    loom = contains_any(task_text, ["loom", "角色化", "多角色", "角色分工"])
    self_development = contains_any(task_text, [
        "redcap",
        "自开发",
        "门禁",
        "hook",
        "钩子",
        "生命周期",
        "棱镜",
        "任务入口",
        "完成边界",
        "长任务机制",
        "工作流",
    ])
    boundary_change = boundary_count >= 2 or contains_any(task_text, [
        "跨工作区",
        "跨仓库",
        "运行时",
        "runtime",
        ".redcap",
        "项目级",
        "边界",
    ])
    if explicit_long_run:
        triggers.append("user_explicit_long_run")
    if risk_at_least(risk_level, "medium") and self_development:
        triggers.append("redcap_self_development_medium_or_higher")
    if e2e_or_release:
        triggers.append("external_e2e_or_release_validation")
    if loom:
        triggers.append("multi_role_loom_workflow")
    if consecutive_failures >= 3:
        triggers.append("multi_iteration_failure_repair")
    if boundary_change and (boundary_count >= 2 or risk_at_least(risk_level, "medium")):
        triggers.append("cross_workspace_or_runtime_boundary_change")

    answer_only = contains_any(task_text, [
        "什么意思",
        "是什么",
        "解释",
        "讲一下",
        "是否",
        "吗",
        "为什么",
        "review",
        "评审一下",
    ]) and not contains_any(task_text, ["修复", "实现", "执行", "落地", "提交", "push", "部署"])
    if risk_level == "low":
        fast_path_signals.append("low_risk")
    if answer_only:
        fast_path_signals.append("answer_only_or_review_only")
    if not explicit_long_run and not e2e_or_release and consecutive_failures == 0 and boundary_count <= 1:
        fast_path_signals.append("single_step_or_small_patch")
    if not self_development and not e2e_or_release and not loom and not boundary_change:
        fast_path_signals.append("no_cross_role_no_e2e_no_release_no_self_development")

    mode = "enabled" if triggers else "fast_path"
    if mode == "fast_path":
        missing = sorted(FAST_PATH_SIGNALS - set(fast_path_signals))
        if missing and risk_level == "low" and answer_only:
            fast_path_signals.extend(item for item in missing if item not in fast_path_signals)

    requires_cap_arbitration = mode == "enabled" and str(external_goal_status or "").casefold() == "blocked"
    return {
        "schema_id": "redcap-long-task-decision",
        "ok": True,
        "mode": mode,
        "risk_level": risk_level,
        "triggers": triggers,
        "fast_path_signals": sorted(set(fast_path_signals)),
        "requires_lifecycle": mode == "enabled" and risk_at_least(risk_level, "medium"),
        "requires_prism": mode == "enabled" and (
            risk_at_least(risk_level, "medium")
            or "external_e2e_or_release_validation" in triggers
            or "multi_role_loom_workflow" in triggers
        ),
        "requires_cap_arbitration": requires_cap_arbitration,
        "external_goal_status": external_goal_status,
        "reason": (
            "进入长任务模式：命中重型任务触发条件。"
            if mode == "enabled"
            else "走轻量路径：未命中长任务触发条件。"
        ),
    }


def validate_thresholds(thresholds: Any, failures: list[str]) -> None:
    if not isinstance(thresholds, dict):
        failures.append("activation.thresholds must be an object")
        return
    multi = thresholds.get("multi_iteration_failure_repair")
    if not isinstance(multi, dict):
        failures.append("activation.thresholds.multi_iteration_failure_repair must be an object")
    elif multi.get("min_consecutive_failures") != 3:
        failures.append("multi_iteration_failure_repair.min_consecutive_failures must be exactly 3")
    cross = thresholds.get("cross_workspace_or_runtime_boundary_change")
    if not isinstance(cross, dict):
        failures.append("activation.thresholds.cross_workspace_or_runtime_boundary_change must be an object")
    elif cross.get("min_independent_boundaries") != 2:
        failures.append("cross_workspace_or_runtime_boundary_change.min_independent_boundaries must be exactly 2")


def validate_codex_goal_policy(policy: Any, failures: list[str]) -> None:
    if not isinstance(policy, dict):
        failures.append("codex_goal_policy must be an object")
        return
    expected_false = [
        "blocked_equals_redcap_failure",
        "must_clear_before_new_task",
        "blocks_new_redcap_task",
        "internal_contract_may_override_external_goal",
    ]
    for key in expected_false:
        if policy.get(key) is not False:
            failures.append(f"codex_goal_policy.{key} must be false")
    if policy.get("arbitration_required_within_iterations") != 1:
        failures.append("codex_goal_policy.arbitration_required_within_iterations must be 1")
    if not substantive(policy.get("blocked_meaning")):
        failures.append("codex_goal_policy.blocked_meaning must explain the external blocked state")


def validate_loop_policy(policy: Any, failures: list[str]) -> None:
    if not isinstance(policy, dict):
        failures.append("loop_policy must be an object when activation.mode=enabled")
        return
    if policy.get("max_iterations_before_cap_arbitration") != 5:
        failures.append("loop_policy.max_iterations_before_cap_arbitration must default to 5")
    if policy.get("repeated_blocker_threshold") != 2:
        failures.append("loop_policy.repeated_blocker_threshold must be 2")
    if policy.get("structural_stop_threshold") != 2:
        failures.append("loop_policy.structural_stop_threshold must be 2")
    required_true = [
        "require_action_evidence",
        "require_objective_delta",
        "require_failure_backlog",
        "no_blind_rerun_without_source_or_evidence_delta",
        "blocked_goal_requires_cap_arbitration",
        "human_decision_stops_automation",
    ]
    for key in required_true:
        if policy.get(key) is not True:
            failures.append(f"loop_policy.{key} must be true")


def validate_stop_conditions(stop_conditions: Any, failures: list[str]) -> None:
    if not isinstance(stop_conditions, dict):
        failures.append("stop_conditions must be an object when activation.mode=enabled")
        return
    for key in ["success", "blocked", "human_decision"]:
        if not non_empty_string_list(stop_conditions.get(key)):
            failures.append(f"stop_conditions.{key} must be a non-empty string list")


def signature_of(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def validate_contract_kind(contract: dict[str, Any], failures: list[str]) -> str | None:
    kind = contract.get("contract_kind")
    if kind not in CONTRACT_KINDS:
        failures.append("contract_kind must be one of policy_template or active_run")
        return None
    return str(kind)


def validate_failure_backlog(backlog: Any, failures: list[str]) -> None:
    if not isinstance(backlog, dict):
        failures.append("active_run requires failure_backlog object")
        return
    total = 0
    for key in ["open", "closed"]:
        value = backlog.get(key)
        if not isinstance(value, list):
            failures.append(f"failure_backlog.{key} must be a list")
            continue
        total += len(value)
        for index, item in enumerate(value):
            if isinstance(item, str):
                if not substantive(item):
                    failures.append(f"failure_backlog.{key}[{index}] must be substantive")
                continue
            if not isinstance(item, dict):
                failures.append(f"failure_backlog.{key}[{index}] must be a string or object")
                continue
            if not substantive(item.get("summary")):
                failures.append(f"failure_backlog.{key}[{index}].summary must be substantive")
    if total == 0:
        failures.append("failure_backlog must contain at least one open or closed entry")


def validate_iteration_ledger(iterations: Any, failures: list[str], *, active_run: bool = False) -> None:
    if iterations is None:
        if active_run:
            failures.append("active_run requires iteration_ledger")
        return
    if not isinstance(iterations, list):
        failures.append("iteration_ledger must be a list when present")
        return
    if active_run and not iterations:
        failures.append("active_run iteration_ledger must be non-empty")
    empty_delta_streak = 0
    previous: dict[str, Any] | None = None
    repeated_same_root_streak = 1
    for index, item in enumerate(iterations):
        if not isinstance(item, dict):
            failures.append(f"iteration_ledger[{index}] must be an object")
            continue
        status = item.get("status")
        if status not in ITERATION_STATUSES:
            failures.append(f"iteration_ledger[{index}].status invalid: {status}")
        finished = status in {"passed", "failed", "blocked", "arbitrated"}
        active_step = active_run and status != "planned"
        delta = item.get("objective_delta")
        if (finished or active_step) and not substantive(delta):
            failures.append(f"iteration_ledger[{index}] active or finished iterations require substantive objective_delta")
        if (finished or active_step) and not non_empty_string_list(item.get("action_evidence")):
            failures.append(f"iteration_ledger[{index}] active or finished iterations require action_evidence")
        if active_step:
            for key in ["source_signature", "evidence_signature"]:
                if not substantive(item.get(key), min_len=6):
                    failures.append(f"iteration_ledger[{index}].{key} must be substantive for active_run")
        if substantive(delta):
            empty_delta_streak = 0
        else:
            empty_delta_streak += 1
        if empty_delta_streak >= 2:
            failures.append("two consecutive iterations without objective_delta must trigger structural stop")
        if previous is not None:
            same_blocker = signature_of(previous, "blocker_signature") == signature_of(item, "blocker_signature")
            same_source = signature_of(previous, "source_signature") == signature_of(item, "source_signature")
            same_evidence = signature_of(previous, "evidence_signature") == signature_of(item, "evidence_signature")
            if same_blocker and same_source and same_evidence:
                repeated_same_root_streak += 1
            else:
                repeated_same_root_streak = 1
            if same_blocker and same_source and same_evidence and previous.get("auto_rerun_allowed") is False:
                failures.append("blind rerun detected after auto_rerun_allowed=false with unchanged blocker/source/evidence signatures")
            if (
                repeated_same_root_streak > 2
                and status in {"running", "failed", "blocked"}
                and item.get("auto_rerun_allowed") is not False
            ):
                failures.append(
                    "same blocker/source/evidence repeated more than threshold without arbitration or evidence delta"
                )
        previous = item


def derive_capability_layers() -> set[str]:
    layers: set[str] = set()

    def read(rel: str) -> str:
        try:
            return (REPO_ROOT / rel).read_text(encoding="utf-8")
        except OSError:
            return ""

    source = read("runtime/core/long_task_contract.py")
    redcap = read("runtime/bin/redcap")
    runner = read("runtime/core/check_runner.py")
    evidence_gitignore = read("assets/evidence/.gitignore")
    if "def cmd_decide" in source and "long-task check|decide|start|record|complete|boundary-check|self-check" in redcap:
        layers.add("task_entry_decision")
    if (
        "def cmd_start" in source
        and "def start_long_task" in source
        and "def cmd_record" in source
        and "def record_long_task_iteration" in source
        and "def cmd_complete" in source
        and "def complete_long_task" in source
        and "def packet_lock" in source
        and "def validate_action_evidence_files" in source
        and "MIN_ACTION_EVIDENCE_BYTES" in source
        and "MIN_ACTION_EVIDENCE_UNIQUE_CHARS" in source
        and "completion_evidence must not be low confidence" in source
        and "completion_relevance_failures" in source
        and "record requires active_run.lifecycle_state=running" in source
        and "objective_delta must differ from previous iteration" in source
        and "long-task check|decide|start|record|complete|boundary-check|self-check" in redcap
    ):
        layers.add("generic_active_run_entry")
    if "def validate_contract_kind" in source and "contract_kind" in source:
        layers.add("contract_validation")
    if "def validate_active_run_contract" in source and "active_run iteration_ledger must be non-empty" in source:
        layers.add("active_run_ledger")
    if "def validate_failure_backlog" in source and "failure_backlog" in source:
        layers.add("failure_backlog")
    if "def validate_capability_coverage" in source and "completion_claim_allowed" in source:
        layers.add("completion_boundary_guard")
    if "long-task-contract-self-check" in runner and "long-task-contract-check" in runner:
        layers.add("aggregate_check_integration")
    stable_needles = [
        "!prism/*/session.json",
        "!prism/*/request*.json",
        "!prism/*/*.review.json",
        "!prism/*/*.review.brief.md",
        "!prism/*/merge.json",
        "!prism/*/*.merge.json",
        "!prism/*/resolution.json",
        "!check-receipts/*/*.receipt.json",
    ]
    if all(needle in evidence_gitignore for needle in stable_needles):
        layers.add("stable_evidence_policy")
    if has_prism_review_resolution_evidence():
        layers.add("prism_review_resolution")
    return layers


def has_prism_review_resolution_evidence() -> bool:
    prism_root = REPO_ROOT / "assets" / "evidence" / "prism"
    if not prism_root.exists():
        return False
    for run_dir in prism_root.iterdir():
        if not run_dir.is_dir():
            continue
        if not (run_dir / "session.json").exists():
            continue
        merge_files = list(run_dir.glob("merge.json")) + list(run_dir.glob("*.merge.json"))
        if not merge_files:
            continue
        has_kimi = any("kimi" in path.name and path.name.endswith(".review.json") for path in run_dir.glob("*.review.json"))
        has_claude = any("claude-code" in path.name and path.name.endswith(".review.json") for path in run_dir.glob("*.review.json"))
        if not (has_kimi and has_claude):
            continue
        for merge_file in merge_files:
            try:
                merge = load_json(merge_file)
            except SystemExit:
                continue
            if merge.get("strictest_verdict") == "pass":
                return True
            if (run_dir / "resolution.json").exists() or any(path.name.endswith(".resolution.json") for path in run_dir.glob("*.resolution.json")):
                return True
    return False


def validate_capability_coverage(coverage: Any, failures: list[str], *, require_integration: bool = False) -> None:
    if not isinstance(coverage, dict):
        failures.append("capability_coverage must be an object")
        return
    if "completed_layers" in coverage:
        failures.append("capability_coverage.completed_layers must not be supplied by contract; checker derives completed layers")
    required = coverage.get("required_layers")
    if not isinstance(required, list) or not required:
        failures.append("capability_coverage.required_layers must be a non-empty list")
        required = []
    unknown = sorted(str(item) for item in required if item not in CAPABILITY_LAYERS)
    if unknown:
        failures.append(f"capability_coverage.required_layers contains unknown entries: {', '.join(unknown)}")
    if not substantive(coverage.get("claim_scope")):
        failures.append("capability_coverage.claim_scope must explain the allowed claim boundary")
    completion_allowed = coverage.get("completion_claim_allowed")
    if not isinstance(completion_allowed, bool):
        failures.append("capability_coverage.completion_claim_allowed must be boolean")
        completion_allowed = False
    if completion_allowed and require_integration:
        derived = derive_capability_layers()
        missing = sorted(set(required) - derived)
        if missing:
            failures.append(f"completion_claim_allowed requires derived capability layers: {', '.join(missing)}")


def validate_examples(examples: Any, failures: list[str]) -> None:
    if not isinstance(examples, list) or len(examples) < 5:
        failures.append("risk_rating_examples must contain at least 5 examples")
        return
    modes = set()
    for index, item in enumerate(examples):
        if not isinstance(item, dict):
            failures.append(f"risk_rating_examples[{index}] must be an object")
            continue
        mode = item.get("expected_mode")
        modes.add(mode)
        if mode not in VALID_MODES:
            failures.append(f"risk_rating_examples[{index}].expected_mode invalid: {mode}")
        if not substantive(item.get("task")):
            failures.append(f"risk_rating_examples[{index}].task must be substantive")
        if not substantive(item.get("reason")):
            failures.append(f"risk_rating_examples[{index}].reason must be substantive")
    if "enabled" not in modes or "fast_path" not in modes:
        failures.append("risk_rating_examples must include both enabled and fast_path cases")


def validate_activation(contract: dict[str, Any], failures: list[str]) -> None:
    activation = contract.get("activation")
    if not isinstance(activation, dict):
        failures.append("activation must be an object")
        return
    mode = activation.get("mode")
    if mode not in VALID_MODES:
        failures.append(f"activation.mode invalid: {mode}")
        return
    risk_level = activation.get("risk_level")
    if risk_level not in RISK_LEVELS:
        failures.append(f"activation.risk_level invalid: {risk_level}")
    triggers = activation.get("triggers", [])
    if not isinstance(triggers, list):
        failures.append("activation.triggers must be a list")
        triggers = []
    unknown = sorted(str(item) for item in triggers if item not in VALID_TRIGGERS)
    if unknown:
        failures.append(f"activation.triggers contains unknown entries: {', '.join(unknown)}")
    if mode == "fast_path":
        signals = activation.get("fast_path_signals")
        if not isinstance(signals, list):
            failures.append("activation.fast_path_signals must be a list when mode=fast_path")
            signals = []
        missing = sorted(FAST_PATH_SIGNALS - set(signals))
        if missing:
            failures.append(f"fast_path must prove all fast-path signals: {', '.join(missing)}")
        if any(trigger in VALID_TRIGGERS - {"user_explicit_long_run"} for trigger in triggers):
            failures.append("fast_path cannot include heavy long-task triggers")
        if not substantive(activation.get("fast_path_reason")):
            failures.append("activation.fast_path_reason must explain why the heavy loop is skipped")
        return
    if not triggers:
        failures.append("activation.triggers must be non-empty when mode=enabled")
    validate_thresholds(activation.get("thresholds"), failures)
    if risk_level == "low" and "user_explicit_long_run" not in triggers:
        failures.append("low-risk enabled long task requires user_explicit_long_run")
    if activation.get("default_state") != "off":
        failures.append("activation.default_state must be off")


def validate_enabled_contract(contract: dict[str, Any], failures: list[str], *, active_run: bool = False) -> None:
    if not substantive(contract.get("parent_objective")):
        failures.append("parent_objective must be substantive when activation.mode=enabled")
    if not non_empty_string_list(contract.get("terminal_acceptance")):
        failures.append("terminal_acceptance must be a non-empty string list")
    if not non_empty_string_list(contract.get("non_claimed_boundaries")):
        failures.append("non_claimed_boundaries must be a non-empty string list")
    validate_codex_goal_policy(contract.get("codex_goal_policy"), failures)
    validate_loop_policy(contract.get("loop_policy"), failures)
    validate_stop_conditions(contract.get("stop_conditions"), failures)
    validate_iteration_ledger(contract.get("iteration_ledger"), failures, active_run=active_run)
    if active_run:
        validate_active_run_contract(contract, failures)


def validate_active_run_contract(contract: dict[str, Any], failures: list[str]) -> None:
    state = contract.get("lifecycle_state")
    if state not in ACTIVE_RUN_STATES:
        failures.append("active_run.lifecycle_state must be one of running, completed, failed, blocked, human_decision")
        return
    validate_failure_backlog(contract.get("failure_backlog"), failures)
    boundary = contract.get("completion_boundary")
    if state == "running":
        if boundary not in (None, {}):
            failures.append("running active_run must not contain a terminal completion_boundary")
        return
    if not isinstance(boundary, dict):
        failures.append("terminal active_run requires completion_boundary object")
        return
    if boundary.get("outcome") != state:
        failures.append("completion_boundary.outcome must match active_run.lifecycle_state")
    for key in ["completed_at", "final_objective_delta", "final_summary"]:
        if not substantive(boundary.get(key)):
            failures.append(f"completion_boundary.{key} must be substantive")
    if not non_empty_string_list(boundary.get("completion_evidence")):
        failures.append("completion_boundary.completion_evidence must be a non-empty string list")
    quality = boundary.get("evidence_quality")
    if not isinstance(quality, list) or not quality:
        failures.append("completion_boundary.evidence_quality must be a non-empty list")
    else:
        low = [item for item in quality if isinstance(item, dict) and item.get("confidence") in {"low", "missing"}]
        if low:
            failures.append("completion_boundary.evidence_quality must not contain low-confidence evidence")


def validate_repository_integration(failures: list[str]) -> None:
    for rel, needle in REQUIRED_CODE_POINTERS.items():
        path = REPO_ROOT / rel
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            failures.append(f"cannot read integration file {rel}: {exc}")
            continue
        if needle not in content:
            failures.append(f"{rel} is missing long-task contract integration marker: {needle}")


def validate_contract(contract: dict[str, Any], *, require_integration: bool = False) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != SCHEMA_ID:
        failures.append(f"schema_id must be {SCHEMA_ID}")
    contract_kind = validate_contract_kind(contract, failures)
    validate_activation(contract, failures)
    activation = contract.get("activation") if isinstance(contract.get("activation"), dict) else {}
    if activation.get("mode") == "enabled":
        validate_enabled_contract(contract, failures, active_run=contract_kind == "active_run")
    validate_capability_coverage(contract.get("capability_coverage"), failures, require_integration=require_integration)
    validate_examples(contract.get("risk_rating_examples"), failures)
    if require_integration:
        validate_repository_integration(failures)
    return failures


def check_payload(path: pathlib.Path, *, require_integration: bool = False) -> dict[str, Any]:
    payload = load_json(path)
    failures = validate_contract(payload, require_integration=require_integration)
    activation = payload.get("activation") if isinstance(payload.get("activation"), dict) else {}
    coverage = payload.get("capability_coverage") if isinstance(payload.get("capability_coverage"), dict) else {}
    required_layers = set(coverage.get("required_layers", []) if isinstance(coverage.get("required_layers"), list) else [])
    derived_layers = derive_capability_layers() if require_integration else set()
    return {
        "schema_id": "redcap-long-task-contract-check-result",
        "ok": not failures,
        "path": str(path),
        "contract_kind": payload.get("contract_kind"),
        "mode": activation.get("mode"),
        "derived_capability_layers": sorted(derived_layers),
        "missing_capability_layers": sorted(required_layers - derived_layers) if require_integration else [],
        "failures": failures,
    }


def valid_enabled_fixture() -> dict[str, Any]:
    return {
        "schema_id": SCHEMA_ID,
        "contract_kind": "active_run",
        "parent_objective": "持续推进 RedCap 复活后续工程，直到工程试用验收有客观证据支撑。",
        "terminal_acceptance": [
            "所有终止条件均由运行证据、最终评审和边界声明共同支撑"
        ],
        "non_claimed_boundaries": [
            "不声称跨机器生产验收",
            "不声称永久没有后续优化"
        ],
        "activation": {
            "mode": "enabled",
            "default_state": "off",
            "risk_level": "medium",
            "triggers": [
                "user_explicit_long_run",
                "external_e2e_or_release_validation",
                "multi_iteration_failure_repair"
            ],
            "thresholds": {
                "multi_iteration_failure_repair": {
                    "min_consecutive_failures": 3
                },
                "cross_workspace_or_runtime_boundary_change": {
                    "min_independent_boundaries": 2
                }
            }
        },
        "codex_goal_policy": {
            "blocked_meaning": "Codex 目标 blocked 是外部目标工具状态；它提示需要仲裁，但不自动等于 RedCap 工程失败。",
            "blocked_equals_redcap_failure": False,
            "must_clear_before_new_task": False,
            "blocks_new_redcap_task": False,
            "internal_contract_may_override_external_goal": False,
            "arbitration_required_within_iterations": 1
        },
        "loop_policy": {
            "max_iterations_before_cap_arbitration": 5,
            "repeated_blocker_threshold": 2,
            "structural_stop_threshold": 2,
            "require_action_evidence": True,
            "require_objective_delta": True,
            "require_failure_backlog": True,
            "no_blind_rerun_without_source_or_evidence_delta": True,
            "blocked_goal_requires_cap_arbitration": True,
            "human_decision_stops_automation": True
        },
        "stop_conditions": {
            "success": ["终止验收证据通过，且边界声明完整"],
            "blocked": ["同一结构性阻塞重复出现且没有源码或证据变化"],
            "human_decision": ["涉及产品范围、外部账号、密钥、发布或破坏性操作"]
        },
        "failure_backlog": {
            "open": [],
            "closed": [
                {
                    "id": "fixture-gap",
                    "summary": "第一轮发现外部锚点证据缺口，第二轮已补齐并关闭。"
                }
            ]
        },
        "lifecycle_state": "running",
        "completion_boundary": None,
        "iteration_ledger": [
            {
                "iteration_id": "round-1",
                "status": "failed",
                "action_evidence": ["runtime/bin/redcap complete-revival-e2e run"],
                "objective_delta": "发现最终评审要求补充外部锚点证据。",
                "blocker_signature": "external-anchor-gap",
                "source_signature": "source-a",
                "evidence_signature": "evidence-a",
                "auto_rerun_allowed": True
            },
            {
                "iteration_id": "round-2",
                "status": "passed",
                "action_evidence": ["runtime/bin/redcap check"],
                "objective_delta": "补齐外部锚点并通过最终评审。",
                "blocker_signature": "none",
                "source_signature": "source-b",
                "evidence_signature": "evidence-b",
                "auto_rerun_allowed": False
            }
        ],
        "capability_coverage": valid_capability_coverage(completion_claim_allowed=False),
        "risk_rating_examples": risk_examples(),
    }


def valid_fast_path_fixture() -> dict[str, Any]:
    return {
        "schema_id": SCHEMA_ID,
        "contract_kind": "policy_template",
        "activation": {
            "mode": "fast_path",
            "default_state": "off",
            "risk_level": "low",
            "triggers": [],
            "fast_path_signals": sorted(FAST_PATH_SIGNALS),
            "fast_path_reason": "这是低风险回答或一步小修，不涉及跨角色、E2E、发布、自开发中高风险或多轮失败修复。"
        },
        "capability_coverage": valid_capability_coverage(completion_claim_allowed=False),
        "risk_rating_examples": risk_examples(),
    }


def valid_capability_coverage(*, completion_claim_allowed: bool) -> dict[str, Any]:
    return {
        "claim_scope": "只允许声明长任务治理策略或单次 active_run 合同检查结果，不允许单独声明 RedCap 完整复活。",
        "completion_claim_allowed": completion_claim_allowed,
        "required_layers": sorted(CAPABILITY_LAYERS),
    }


def risk_examples() -> list[dict[str, str]]:
    return [
        {
            "task": "回答 Codex 目标 blocked 的语义，不修改文件。",
            "expected_mode": "fast_path",
            "reason": "这是解释型任务，没有跨角色、发布、E2E 或多轮失败修复。"
        },
        {
            "task": "修复一个低风险错别字并运行单个检查。",
            "expected_mode": "fast_path",
            "reason": "一步小修且可局部验证，不需要父目标循环。"
        },
        {
            "task": "连续三轮 E2E 暴露同类结构性失败。",
            "expected_mode": "enabled",
            "reason": "达到多轮同类失败阈值，需要父目标、失败账本和防盲重跑。"
        },
        {
            "task": "修改 RedCap 自开发门禁和生命周期规则。",
            "expected_mode": "enabled",
            "reason": "中高风险自开发会改变任务治理能力，必须启用长任务合同。"
        },
        {
            "task": "同时影响发布包、项目 .redcap 运行时和源仓库边界。",
            "expected_mode": "enabled",
            "reason": "涉及两个以上独立边界，必须记录父目标和回滚停止条件。"
        }
    ]


def write_fixture(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def default_thresholds(template: dict[str, Any]) -> dict[str, Any]:
    activation = template.get("activation") if isinstance(template.get("activation"), dict) else {}
    thresholds = activation.get("thresholds") if isinstance(activation.get("thresholds"), dict) else {}
    return {
        "multi_iteration_failure_repair": {
            "min_consecutive_failures": (
                thresholds.get("multi_iteration_failure_repair", {}).get("min_consecutive_failures", 3)
                if isinstance(thresholds.get("multi_iteration_failure_repair"), dict)
                else 3
            )
        },
        "cross_workspace_or_runtime_boundary_change": {
            "min_independent_boundaries": (
                thresholds.get("cross_workspace_or_runtime_boundary_change", {}).get("min_independent_boundaries", 2)
                if isinstance(thresholds.get("cross_workspace_or_runtime_boundary_change"), dict)
                else 2
            )
        },
    }


def inherited_or_default(template: dict[str, Any], key: str, default: Any) -> Any:
    value = template.get(key)
    if isinstance(default, dict):
        return copy.deepcopy(value) if isinstance(value, dict) else copy.deepcopy(default)
    if isinstance(default, list):
        return copy.deepcopy(value) if isinstance(value, list) and value else copy.deepcopy(default)
    return copy.deepcopy(value) if value is not None else copy.deepcopy(default)


def build_started_active_run(
    task_text: str,
    run_dir: pathlib.Path,
    decision: dict[str, Any],
    *,
    parent_objective: str | None = None,
    action_evidence: list[str] | None = None,
) -> dict[str, Any]:
    template = load_long_task_template()
    now = iso_now()
    objective = parent_objective or f"持续推进任务入口：{task_text.strip()[:160]}"
    evidence = action_evidence or ["runtime/bin/redcap long-task start"]
    return {
        "schema_id": SCHEMA_ID,
        "contract_kind": "active_run",
        "parent_objective": objective,
        "terminal_acceptance": inherited_or_default(template, "terminal_acceptance", [
            "每一轮都有可核验的动作证据和父目标推进差量",
            "成功、受阻、需要人类决策三类停止条件均可机器检查",
        ]),
        "non_claimed_boundaries": inherited_or_default(template, "non_claimed_boundaries", [
            "long-task start 只证明长任务入口已经创建真实运行包，不证明父任务已经完成",
            "long-task start 不替代 E2E、Loom、生命周期包、棱镜复核或最终验收",
        ]),
        "activation": {
            "mode": "enabled",
            "default_state": "off",
            "risk_level": decision["risk_level"],
            "triggers": decision["triggers"],
            "thresholds": default_thresholds(template),
        },
        "codex_goal_policy": inherited_or_default(template, "codex_goal_policy", {
            "blocked_meaning": "Codex 目标 blocked 是外部目标工具状态；它要求 Cap 仲裁，但不自动等于 RedCap 工程失败或完成。",
            "blocked_equals_redcap_failure": False,
            "must_clear_before_new_task": False,
            "blocks_new_redcap_task": False,
            "internal_contract_may_override_external_goal": False,
            "arbitration_required_within_iterations": 1,
        }),
        "loop_policy": inherited_or_default(template, "loop_policy", {
            "max_iterations_before_cap_arbitration": 5,
            "repeated_blocker_threshold": 2,
            "structural_stop_threshold": 2,
            "require_action_evidence": True,
            "require_objective_delta": True,
            "require_failure_backlog": True,
            "no_blind_rerun_without_source_or_evidence_delta": True,
            "blocked_goal_requires_cap_arbitration": True,
            "human_decision_stops_automation": True,
        }),
        "stop_conditions": inherited_or_default(template, "stop_conditions", {
            "success": ["终止验收证据通过，且完成边界声明完整"],
            "blocked": ["同一结构性阻塞连续重复且没有源码或证据变化"],
            "human_decision": ["涉及产品范围、外部账号、密钥、发布或破坏性操作"],
        }),
        "failure_backlog": {
            "open": [],
            "closed": [
                {
                    "id": "long-task-entry-created",
                    "summary": "长任务统一入口已创建第一轮 active_run 运行包；这不是父任务完成声明。",
                }
            ],
        },
        "lifecycle_state": "running",
        "completion_boundary": None,
        "iteration_ledger": [
            {
                "iteration_id": "entry-round-1",
                "status": "running",
                "action_evidence": evidence,
                "objective_delta": "长任务统一入口已根据决策结果创建第一轮 active_run 运行包，父目标进入可追踪状态。",
                "blocker_signature": "none-at-entry",
                "source_signature": source_signature(),
                "evidence_signature": entry_evidence_signature(task_text, decision, run_dir),
                "auto_rerun_allowed": True,
                "started_at": now,
            }
        ],
        "capability_coverage": {
            "claim_scope": "只允许声明长任务统一入口已创建并校验 active_run，不允许声明父任务完成或 RedCap 完整复活。",
            "completion_claim_allowed": False,
            "required_layers": sorted(CAPABILITY_LAYERS),
        },
        "risk_rating_examples": risk_examples(),
        "entry_context": {
            "created_at": now,
            "task_sha256": sha256_text(task_text),
            "decision": decision,
            "run_dir": str(run_dir),
        },
    }


def start_long_task(
    task_text: str,
    *,
    risk_level: str,
    run_dir: pathlib.Path,
    consecutive_failures: int = 0,
    boundary_count: int = 0,
    external_goal_status: str | None = None,
    parent_objective: str | None = None,
    action_evidence: list[str] | None = None,
) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    decision = decide_long_task_mode(
        task_text,
        risk_level=risk_level,
        consecutive_failures=consecutive_failures,
        boundary_count=boundary_count,
        external_goal_status=external_goal_status,
    )
    decision_path = run_dir / "redcap-long-task-decision.json"
    write_json(decision_path, decision)
    if decision["mode"] == "fast_path":
        result = {
            "schema_id": "redcap-long-task-start-result",
            "ok": True,
            "mode": "fast_path",
            "active_run_created": False,
            "decision": str(decision_path),
            "reason": "轻量路径不创建重型 active_run，避免小任务被过度治理。",
        }
        write_json(run_dir / "redcap-long-task-start-result.json", result)
        return result

    packet = build_started_active_run(
        task_text,
        run_dir,
        decision,
        parent_objective=parent_objective,
        action_evidence=action_evidence,
    )
    packet_path = run_dir / "redcap-long-task-active-run.json"
    write_json(packet_path, packet)
    check_result = check_payload(packet_path)
    check_path = run_dir / "redcap-long-task-active-run.check.json"
    write_json(check_path, check_result)
    result = {
        "schema_id": "redcap-long-task-start-result",
        "ok": check_result["ok"],
        "mode": "enabled",
        "active_run_created": True,
        "decision": str(decision_path),
        "active_run": str(packet_path),
        "check": str(check_path),
        "failures": check_result["failures"],
    }
    write_json(run_dir / "redcap-long-task-start-result.json", result)
    return result


def record_long_task_iteration(
    packet_path: pathlib.Path,
    *,
    status: str,
    objective_delta: str,
    action_evidence: list[str],
    blocker_signature: str,
    failure_summary: str | None = None,
    auto_rerun_allowed: bool | None = None,
) -> dict[str, Any]:
    with packet_lock(packet_path):
        return _record_long_task_iteration_unlocked(
            packet_path,
            status=status,
            objective_delta=objective_delta,
            action_evidence=action_evidence,
            blocker_signature=blocker_signature,
            failure_summary=failure_summary,
            auto_rerun_allowed=auto_rerun_allowed,
        )


def _record_long_task_iteration_unlocked(
    packet_path: pathlib.Path,
    *,
    status: str,
    objective_delta: str,
    action_evidence: list[str],
    blocker_signature: str,
    failure_summary: str | None = None,
    auto_rerun_allowed: bool | None = None,
) -> dict[str, Any]:
    packet = load_json(packet_path)
    if packet.get("contract_kind") != "active_run":
        return {
            "schema_id": "redcap-long-task-record-result",
            "ok": False,
            "failures": ["record requires contract_kind=active_run"],
        }
    if packet.get("lifecycle_state") != "running":
        return {
            "schema_id": "redcap-long-task-record-result",
            "ok": False,
            "failures": ["record requires active_run.lifecycle_state=running"],
        }
    if status not in ITERATION_STATUSES - {"planned"}:
        return {
            "schema_id": "redcap-long-task-record-result",
            "ok": False,
            "failures": [f"status must be one of: {', '.join(sorted(ITERATION_STATUSES - {'planned'}))}"],
        }
    if not substantive(objective_delta):
        return {
            "schema_id": "redcap-long-task-record-result",
            "ok": False,
            "failures": ["objective_delta must be substantive"],
        }
    if not non_empty_string_list(action_evidence):
        return {
            "schema_id": "redcap-long-task-record-result",
            "ok": False,
            "failures": ["action_evidence must be non-empty"],
        }
    evidence_failures = validate_action_evidence_files(packet_path, action_evidence)
    if evidence_failures:
        return {
            "schema_id": "redcap-long-task-record-result",
            "ok": False,
            "failures": evidence_failures,
        }
    quality = evidence_quality(packet_path, action_evidence)
    backlog = packet.setdefault("failure_backlog", {"open": [], "closed": []})
    if not isinstance(backlog, dict):
        backlog = {"open": [], "closed": []}
        packet["failure_backlog"] = backlog
    backlog.setdefault("open", [])
    backlog.setdefault("closed", [])
    iterations = packet.setdefault("iteration_ledger", [])
    if not isinstance(iterations, list):
        return {
            "schema_id": "redcap-long-task-record-result",
            "ok": False,
            "failures": ["iteration_ledger must be a list"],
        }
    if iterations:
        previous_delta = iterations[-1].get("objective_delta") if isinstance(iterations[-1], dict) else None
        if isinstance(previous_delta, str) and previous_delta.strip() == objective_delta.strip():
            return {
                "schema_id": "redcap-long-task-record-result",
                "ok": False,
                "failures": ["objective_delta must differ from previous iteration"],
            }
    next_index = len(iterations) + 1
    if auto_rerun_allowed is None:
        auto_rerun_allowed = status in {"running", "failed"}
    iterations.append({
        "iteration_id": f"recorded-round-{next_index}",
        "status": status,
        "action_evidence": action_evidence,
        "objective_delta": objective_delta,
        "blocker_signature": blocker_signature,
        "source_signature": source_signature(),
        "evidence_signature": iteration_evidence_signature(packet_path, action_evidence, objective_delta),
        "evidence_quality": quality,
        "auto_rerun_allowed": auto_rerun_allowed,
        "recorded_at": iso_now(),
    })
    summary = failure_summary or objective_delta
    if status in {"failed", "blocked"}:
        backlog["open"].append({
            "id": f"recorded-round-{next_index}",
            "summary": summary,
        })
    elif status in {"passed", "arbitrated"}:
        backlog["closed"].append({
            "id": f"recorded-round-{next_index}",
            "summary": summary,
        })
    write_json(packet_path, packet)
    check_result = check_payload(packet_path)
    check_path = packet_path.with_suffix(packet_path.suffix + ".check.json")
    write_json(check_path, check_result)
    result = {
        "schema_id": "redcap-long-task-record-result",
        "ok": check_result["ok"],
        "packet": str(packet_path),
        "check": str(check_path),
        "iteration_id": f"recorded-round-{next_index}",
        "status": status,
        "evidence_quality": quality,
        "failures": check_result["failures"],
    }
    write_json(packet_path.with_name("redcap-long-task-record-result.json"), result)
    return result


def complete_long_task(
    packet_path: pathlib.Path,
    *,
    outcome: str,
    final_objective_delta: str,
    completion_evidence: list[str],
    final_summary: str,
    blocker_signature: str,
) -> dict[str, Any]:
    with packet_lock(packet_path):
        return _complete_long_task_unlocked(
            packet_path,
            outcome=outcome,
            final_objective_delta=final_objective_delta,
            completion_evidence=completion_evidence,
            final_summary=final_summary,
            blocker_signature=blocker_signature,
        )


def _complete_long_task_unlocked(
    packet_path: pathlib.Path,
    *,
    outcome: str,
    final_objective_delta: str,
    completion_evidence: list[str],
    final_summary: str,
    blocker_signature: str,
) -> dict[str, Any]:
    if outcome not in {"completed", "failed", "blocked", "human_decision"}:
        return {
            "schema_id": "redcap-long-task-complete-result",
            "ok": False,
            "failures": ["outcome must be one of completed, failed, blocked, human_decision"],
        }
    packet = load_json(packet_path)
    if packet.get("contract_kind") != "active_run":
        return {
            "schema_id": "redcap-long-task-complete-result",
            "ok": False,
            "failures": ["complete requires contract_kind=active_run"],
        }
    if packet.get("lifecycle_state") != "running":
        return {
            "schema_id": "redcap-long-task-complete-result",
            "ok": False,
            "failures": ["complete requires active_run.lifecycle_state=running"],
        }
    if not substantive(final_objective_delta):
        return {
            "schema_id": "redcap-long-task-complete-result",
            "ok": False,
            "failures": ["final_objective_delta must be substantive"],
        }
    if not substantive(final_summary):
        return {
            "schema_id": "redcap-long-task-complete-result",
            "ok": False,
            "failures": ["final_summary must be substantive"],
        }
    if not non_empty_string_list(completion_evidence):
        return {
            "schema_id": "redcap-long-task-complete-result",
            "ok": False,
            "failures": ["completion_evidence must be non-empty"],
        }
    evidence_failures = validate_action_evidence_files(packet_path, completion_evidence)
    if evidence_failures:
        return {
            "schema_id": "redcap-long-task-complete-result",
            "ok": False,
            "failures": evidence_failures,
        }
    quality = evidence_quality(packet_path, completion_evidence)
    low = low_confidence_evidence(quality)
    if low:
        return {
            "schema_id": "redcap-long-task-complete-result",
            "ok": False,
            "failures": [f"completion_evidence must not be low confidence: {', '.join(low)}"],
            "evidence_quality": quality,
        }
    relevance_failures = completion_relevance_failures(
        packet_path,
        completion_evidence,
        final_objective_delta,
        final_summary,
    )
    if relevance_failures:
        return {
            "schema_id": "redcap-long-task-complete-result",
            "ok": False,
            "failures": relevance_failures,
            "evidence_quality": quality,
        }

    iterations = packet.setdefault("iteration_ledger", [])
    if not isinstance(iterations, list):
        return {
            "schema_id": "redcap-long-task-complete-result",
            "ok": False,
            "failures": ["iteration_ledger must be a list"],
        }
    if iterations:
        previous_delta = iterations[-1].get("objective_delta") if isinstance(iterations[-1], dict) else None
        if isinstance(previous_delta, str) and previous_delta.strip() == final_objective_delta.strip():
            return {
                "schema_id": "redcap-long-task-complete-result",
                "ok": False,
                "failures": ["final_objective_delta must differ from previous iteration"],
            }
    status_by_outcome = {
        "completed": "passed",
        "failed": "failed",
        "blocked": "blocked",
        "human_decision": "arbitrated",
    }
    next_index = len(iterations) + 1
    now = iso_now()
    iterations.append({
        "iteration_id": f"completion-round-{next_index}",
        "status": status_by_outcome[outcome],
        "action_evidence": completion_evidence,
        "objective_delta": final_objective_delta,
        "blocker_signature": blocker_signature,
        "source_signature": source_signature(),
        "evidence_signature": iteration_evidence_signature(packet_path, completion_evidence, final_objective_delta),
        "evidence_quality": quality,
        "auto_rerun_allowed": False,
        "terminal": True,
        "recorded_at": now,
    })
    backlog = packet.setdefault("failure_backlog", {"open": [], "closed": []})
    if not isinstance(backlog, dict):
        backlog = {"open": [], "closed": []}
        packet["failure_backlog"] = backlog
    backlog.setdefault("open", [])
    backlog.setdefault("closed", [])
    if outcome == "completed" and backlog["open"]:
        backlog["closed"].extend({
            "id": str(item.get("id", "closed-by-complete")) if isinstance(item, dict) else "closed-by-complete",
            "summary": (
                f"complete closed prior open backlog: {item.get('summary')}"
                if isinstance(item, dict)
                else f"complete closed prior open backlog: {item}"
            ),
        } for item in backlog["open"])
        backlog["open"] = []
    target = "closed" if outcome == "completed" else "open"
    backlog[target].append({
        "id": f"completion-round-{next_index}",
        "summary": final_summary,
    })
    packet["lifecycle_state"] = outcome
    packet["completion_boundary"] = {
        "outcome": outcome,
        "completed_at": now,
        "final_objective_delta": final_objective_delta,
        "completion_evidence": completion_evidence,
        "evidence_quality": quality,
        "final_summary": final_summary,
        "not_claimed": [
            "complete 只关闭当前 active_run，不自动证明 RedCap 完整复活",
            "complete 不替代 E2E、Loom 或发布级验收",
        ],
    }
    write_json(packet_path, packet)
    check_result = check_payload(packet_path)
    check_path = packet_path.with_suffix(packet_path.suffix + ".check.json")
    write_json(check_path, check_result)
    result = {
        "schema_id": "redcap-long-task-complete-result",
        "ok": check_result["ok"],
        "packet": str(packet_path),
        "check": str(check_path),
        "outcome": outcome,
        "iteration_id": f"completion-round-{next_index}",
        "evidence_quality": quality,
        "failures": check_result["failures"],
    }
    write_json(packet_path.with_name("redcap-long-task-complete-result.json"), result)
    return result


def add_boundary_probe(
    checks: list[dict[str, Any]],
    probe_id: str,
    *,
    ok: bool,
    expected: str,
    observed: Any,
    artifacts: list[str] | None = None,
) -> None:
    checks.append({
        "id": probe_id,
        "status": "pass" if ok else "fail",
        "expected": expected,
        "observed": observed,
        "artifacts": artifacts or [],
    })


def run_boundary_probe_suite() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    artifacts: list[str] = [
        "runtime/core/long_task_contract.py",
        "assets/contracts/long-task-contract.json",
        "assets/contracts/long-task-loop-boundary.json",
        "runtime/bin/redcap long-task boundary-check",
    ]
    artifact_root = REPO_ROOT / "assets" / "evidence" / "rsp" / "rsp-10-long-task-loop-boundary-artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    with contextlib.nullcontext(artifact_root) as tmp:

        short_decision = decide_long_task_mode("解释这个字段是什么意思", risk_level="low")
        short_start = start_long_task(
            "解释这个字段是什么意思",
            risk_level="low",
            run_dir=tmp / "short-task",
        )
        add_boundary_probe(
            checks,
            "short_task_misroute",
            ok=short_decision.get("mode") == "fast_path"
            and short_start.get("mode") == "fast_path"
            and short_start.get("active_run_created") is False,
            expected="低风险问答走 fast_path，且不创建 active_run。",
            observed={"decision": short_decision, "start": short_start},
            artifacts=[str(tmp / "short-task" / "redcap-long-task-start-result.json")],
        )

        complex_start = start_long_task(
            "持续推进 RedCap 自开发 E2E 巡检，直到每轮问题都进入失败回流并完成真实修复。",
            risk_level="medium",
            run_dir=tmp / "complex-task",
            action_evidence=["runtime/bin/redcap long-task boundary-check complex start"],
        )
        complex_active_run = pathlib.Path(str(complex_start.get("active_run", tmp / "complex-task" / "missing.json")))
        behavior_artifact = tmp / "complex-task" / "behavior-artifact.json"
        behavior_artifact.write_text(json.dumps({
            "schema_id": "boundary-behavior-artifact",
            "command": "runtime/bin/redcap long-task boundary-check behavior probe",
            "exit_code": 0,
            "ok": False,
            "stdout": "failed probe produced structured evidence and changed failure_backlog",
            "evidence": "本文件证明 boundary-check 真实执行 record，而不是只读取合同。",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        record_result = record_long_task_iteration(
            complex_active_run,
            status="failed",
            objective_delta="边界探针写入真实行为证据，并把失败项加入 failure_backlog。",
            action_evidence=[str(behavior_artifact)],
            blocker_signature="boundary-fixture-first-failure",
            failure_summary="边界探针验证 record 能推进 active_run 并维护失败回流。",
        ) if complex_start.get("ok") else {"ok": False, "failures": ["complex start failed"]}
        final_receipt = tmp / "complex-task" / "final-receipt.json"
        final_receipt.write_text(json.dumps({
            "schema_id": "boundary-final-receipt",
            "command": "runtime/bin/redcap long-task boundary-check final probe",
            "exit_code": 0,
            "ok": True,
            "stdout": "passed completion boundary",
            "evidence": "完成回执证明当前 active_run 已达到终止条件。",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        complete_result = complete_long_task(
            complex_active_run,
            outcome="completed",
            final_objective_delta="结构化完成回执证明当前 active_run 已达到终止条件，允许关闭本轮运行包。",
            completion_evidence=[str(final_receipt)],
            final_summary="RSP-10 边界探针中的复杂任务 active_run 已由完成回执关闭。",
            blocker_signature="none",
        ) if record_result.get("ok") else {"ok": False, "failures": ["record probe failed"]}
        completed_packet = load_json(complex_active_run) if complex_active_run.exists() else {}
        add_boundary_probe(
            checks,
            "complex_task_progress_and_close",
            ok=complex_start.get("active_run_created") is True
            and record_result.get("ok") is True
            and complete_result.get("ok") is True
            and completed_packet.get("lifecycle_state") == "completed"
            and bool(completed_packet.get("completion_boundary")),
            expected="复杂任务通过 decide/start/record/complete 推进，并写入 completion_boundary。",
            observed={
                "start": complex_start,
                "record": record_result,
                "complete": complete_result,
                "lifecycle_state": completed_packet.get("lifecycle_state"),
                "completion_boundary_present": bool(completed_packet.get("completion_boundary")),
            },
            artifacts=[str(behavior_artifact), str(final_receipt), str(complex_active_run)],
        )

        blind_retry = valid_enabled_fixture()
        blind_retry["iteration_ledger"] = [
            {
                "iteration_id": "round-1",
                "status": "failed",
                "action_evidence": ["same command output"],
                "objective_delta": "第一次发现同一结构性阻塞。",
                "blocker_signature": "same-root-cause",
                "source_signature": "same-source",
                "evidence_signature": "same-evidence",
                "auto_rerun_allowed": True,
            },
            {
                "iteration_id": "round-2",
                "status": "failed",
                "action_evidence": ["same command output again"],
                "objective_delta": "第二次仍是同一结构性阻塞，尚未出现源码或证据变化。",
                "blocker_signature": "same-root-cause",
                "source_signature": "same-source",
                "evidence_signature": "same-evidence",
                "auto_rerun_allowed": True,
            },
            {
                "iteration_id": "round-3",
                "status": "failed",
                "action_evidence": ["same command output third time"],
                "objective_delta": "第三次仍是同一结构性阻塞，继续自动重跑必须被拒绝。",
                "blocker_signature": "same-root-cause",
                "source_signature": "same-source",
                "evidence_signature": "same-evidence",
                "auto_rerun_allowed": True,
            },
        ]
        blind_retry_path = tmp / "blind-retry.json"
        write_json(blind_retry_path, blind_retry)
        blind_failures = validate_contract(blind_retry)
        add_boundary_probe(
            checks,
            "blind_retry_loop",
            ok=any("same blocker/source/evidence repeated" in item for item in blind_failures),
            expected="同根因、同源码、同证据重复第三轮且仍允许自动重跑时必须失败。",
            observed=blind_failures,
            artifacts=[str(blind_retry_path)],
        )

        low_quality_start = start_long_task(
            "持续推进 RedCap 自开发 E2E 巡检，验证低质量完成证据不能收口。",
            risk_level="medium",
            run_dir=tmp / "low-quality-completion",
            action_evidence=["runtime/bin/redcap long-task boundary-check low quality"],
        )
        low_quality_artifact = tmp / "low-quality-completion" / "random-filler.txt"
        low_quality_artifact.write_text("qwertyuiopasdfghjklzxcvbnm1234567890" * 3 + "\n", encoding="utf-8")
        low_quality_complete = complete_long_task(
            pathlib.Path(str(low_quality_start.get("active_run", tmp / "low-quality-completion" / "missing.json"))),
            outcome="completed",
            final_objective_delta="这轮故意使用随机填充证据收口，complete 必须拒绝。",
            completion_evidence=[str(low_quality_artifact)],
            final_summary="随机填充证据不应关闭 active_run。",
            blocker_signature="low-quality-completion",
        ) if low_quality_start.get("ok") else {"ok": False, "failures": ["low quality start failed"]}
        add_boundary_probe(
            checks,
            "low_quality_completion",
            ok=low_quality_complete.get("ok") is False
            and any("low confidence" in item for item in low_quality_complete.get("failures", [])),
            expected="低置信完成证据必须被 complete 拒绝。",
            observed=low_quality_complete,
            artifacts=[str(low_quality_artifact)],
        )

        missing_start = start_long_task(
            "持续推进 RedCap 自开发 E2E 巡检，验证缺少动作证据和失败账本时必须失败。",
            risk_level="medium",
            run_dir=tmp / "missing-required-fields",
            action_evidence=["runtime/bin/redcap long-task boundary-check missing fields"],
        )
        missing_packet = pathlib.Path(str(missing_start.get("active_run", tmp / "missing-required-fields" / "missing.json")))
        empty_record = record_long_task_iteration(
            missing_packet,
            status="failed",
            objective_delta="这轮故意缺少动作证据，record 必须拒绝。",
            action_evidence=[],
            blocker_signature="missing-action-evidence",
            failure_summary="缺少动作证据不应进入长任务账本。",
        ) if missing_start.get("ok") else {"ok": False, "failures": ["missing fields start failed"]}
        missing_backlog = valid_enabled_fixture()
        missing_backlog.pop("failure_backlog")
        missing_backlog_failures = validate_contract(missing_backlog)
        missing_delta = valid_enabled_fixture()
        missing_delta["iteration_ledger"][0].pop("objective_delta", None)
        missing_delta_failures = validate_contract(missing_delta)
        add_boundary_probe(
            checks,
            "missing_required_fields",
            ok=empty_record.get("ok") is False
            and any("action_evidence" in item for item in empty_record.get("failures", []))
            and any("failure_backlog" in item for item in missing_backlog_failures)
            and any("objective_delta" in item for item in missing_delta_failures),
            expected="缺少 action_evidence、objective_delta 或 failure_backlog 时必须失败。",
            observed={
                "empty_record": empty_record,
                "missing_backlog_failures": missing_backlog_failures,
                "missing_delta_failures": missing_delta_failures,
            },
            artifacts=[str(missing_packet)],
        )

    failures = [item for item in checks if item["status"] != "pass"]
    return {
        "schema_id": "redcap-rsp-10-long-task-loop-boundary",
        "rsp": "RSP-10",
        "ok": not failures,
        "acceptance": {
            "positive": {
                "status": "pass" if all(
                    item["status"] == "pass"
                    for item in checks
                    if item["id"] in {"short_task_misroute", "complex_task_progress_and_close"}
                ) else "fail",
                "checks": [item for item in checks if item["id"] in {"short_task_misroute", "complex_task_progress_and_close"}],
            },
            "negative": {
                "status": "pass" if all(
                    item["status"] == "pass"
                    for item in checks
                    if item["id"] in {"blind_retry_loop", "low_quality_completion", "missing_required_fields"}
                ) else "fail",
                "checks": [item for item in checks if item["id"] in {"blind_retry_loop", "low_quality_completion", "missing_required_fields"}],
            },
        },
        "changed_reality": [
            "runtime/bin/redcap long-task boundary-check 真实调用 decide/start/record/complete，而不是只检查合同文本。",
            "同根因、同源码、同证据第三轮仍自动重跑会被 validate_iteration_ledger 阻断。",
            "低风险短任务不会创建 active_run，降低过度治理风险。",
            "低置信完成证据、缺失动作证据、缺失目标推进差量和缺失失败账本均会被拒绝。"
        ],
        "artifacts": artifacts,
        "failures": failures,
    }


def cmd_boundary_check(args: argparse.Namespace) -> int:
    result = run_boundary_probe_suite()
    if args.out:
        write_json(pathlib.Path(args.out).resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        return 1
    print("REDCAP_LONG_TASK_BOUNDARY_CHECK_OK")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    result = check_payload(pathlib.Path(args.packet).resolve(), require_integration=args.require_integration)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        return 1
    print("REDCAP_LONG_TASK_CONTRACT_OK")
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    if args.risk_level not in RISK_LEVELS:
        raise SystemExit(f"--risk-level must be one of: {', '.join(sorted(RISK_LEVELS))}")
    if args.task:
        task_text = args.task
    elif args.request:
        task_text = request_text_from_file(pathlib.Path(args.request).resolve())
    else:
        raise SystemExit("one of --task or --request is required")
    result = decide_long_task_mode(
        task_text,
        risk_level=args.risk_level,
        consecutive_failures=args.consecutive_failures,
        boundary_count=args.boundary_count,
        external_goal_status=args.external_goal_status,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("REDCAP_LONG_TASK_DECISION_OK")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    if args.risk_level not in RISK_LEVELS:
        raise SystemExit(f"--risk-level must be one of: {', '.join(sorted(RISK_LEVELS))}")
    if args.task:
        task_text = args.task
    elif args.request:
        task_text = request_text_from_file(pathlib.Path(args.request).resolve())
    else:
        raise SystemExit("one of --task or --request is required")
    result = start_long_task(
        task_text,
        risk_level=args.risk_level,
        run_dir=pathlib.Path(args.run_dir).resolve(),
        consecutive_failures=args.consecutive_failures,
        boundary_count=args.boundary_count,
        external_goal_status=args.external_goal_status,
        parent_objective=args.parent_objective,
        action_evidence=args.action_evidence,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        return 1
    print("REDCAP_LONG_TASK_START_OK")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    result = record_long_task_iteration(
        pathlib.Path(args.packet).resolve(),
        status=args.status,
        objective_delta=args.objective_delta,
        action_evidence=args.action_evidence,
        blocker_signature=args.blocker_signature,
        failure_summary=args.failure_summary,
        auto_rerun_allowed=args.auto_rerun_allowed,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        return 1
    print("REDCAP_LONG_TASK_RECORD_OK")
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    result = complete_long_task(
        pathlib.Path(args.packet).resolve(),
        outcome=args.outcome,
        final_objective_delta=args.final_objective_delta,
        completion_evidence=args.completion_evidence,
        final_summary=args.final_summary,
        blocker_signature=args.blocker_signature,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        return 1
    print("REDCAP_LONG_TASK_COMPLETE_OK")
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="redcap-long-task-contract-") as tmp_raw:
        tmp = pathlib.Path(tmp_raw)
        enabled = tmp / "enabled.json"
        fast = tmp / "fast.json"
        write_fixture(enabled, valid_enabled_fixture())
        write_fixture(fast, valid_fast_path_fixture())
        for path in [enabled, fast]:
            result = check_payload(path)
            if not result["ok"]:
                failures.extend(f"{path.name}: {item}" for item in result["failures"])

        missing_threshold = valid_enabled_fixture()
        missing_threshold["activation"]["thresholds"]["multi_iteration_failure_repair"]["min_consecutive_failures"] = 2
        if not validate_contract(missing_threshold):
            failures.append("invalid multi-iteration threshold was accepted")

        small_overtrigger = valid_fast_path_fixture()
        small_overtrigger["activation"]["triggers"] = ["external_e2e_or_release_validation"]
        if not validate_contract(small_overtrigger):
            failures.append("fast-path contract with heavy trigger was accepted")

        blind_rerun = valid_enabled_fixture()
        blind_rerun["iteration_ledger"] = [
            {
                "iteration_id": "round-1",
                "status": "failed",
                "action_evidence": ["run"],
                "objective_delta": "发现结构性问题。",
                "blocker_signature": "same",
                "source_signature": "same",
                "evidence_signature": "same",
                "auto_rerun_allowed": False
            },
            {
                "iteration_id": "round-2",
                "status": "failed",
                "action_evidence": ["run again"],
                "objective_delta": "重复相同结构性问题。",
                "blocker_signature": "same",
                "source_signature": "same",
                "evidence_signature": "same",
                "auto_rerun_allowed": True
            }
        ]
        if not validate_contract(blind_rerun):
            failures.append("blind rerun after auto_rerun_allowed=false was accepted")

        no_delta = valid_enabled_fixture()
        no_delta["iteration_ledger"] = [
            {
                "iteration_id": "round-1",
                "status": "running",
                "blocker_signature": "a",
                "source_signature": "a",
                "evidence_signature": "a",
                "auto_rerun_allowed": True
            },
            {
                "iteration_id": "round-2",
                "status": "running",
                "blocker_signature": "b",
                "source_signature": "b",
                "evidence_signature": "b",
                "auto_rerun_allowed": True
            }
        ]
        if not validate_contract(no_delta):
            failures.append("two no-delta iterations were accepted")

        active_empty = valid_enabled_fixture()
        active_empty["iteration_ledger"] = []
        empty_failures = validate_contract(active_empty)
        if not any("active_run iteration_ledger must be non-empty" in item for item in empty_failures):
            failures.append("active_run with empty iteration_ledger was accepted")

        missing_backlog = valid_enabled_fixture()
        missing_backlog.pop("failure_backlog")
        backlog_failures = validate_contract(missing_backlog)
        if not any("failure_backlog" in item for item in backlog_failures):
            failures.append("active_run without failure_backlog was accepted")

        self_dev_decision = decide_long_task_mode(
            "修复 RedCap 长任务入口与完成边界误判",
            risk_level="medium",
        )
        if self_dev_decision["mode"] != "enabled" or "redcap_self_development_medium_or_higher" not in self_dev_decision["triggers"]:
            failures.append("self-development medium task did not enter long-task mode")

        answer_decision = decide_long_task_mode("解释这个字段是什么意思", risk_level="low")
        if answer_decision["mode"] != "fast_path":
            failures.append("low-risk answer-only task did not use fast_path")

        blocked_decision = decide_long_task_mode(
            "持续推进 RedCap 自开发直到完成",
            risk_level="medium",
            external_goal_status="blocked",
        )
        if blocked_decision["requires_cap_arbitration"] is not True:
            failures.append("enabled task with external blocked goal did not require Cap arbitration")

        bad_coverage = valid_enabled_fixture()
        bad_coverage["capability_coverage"] = {
            **valid_capability_coverage(completion_claim_allowed=False),
            "completed_layers": ["contract_validation"],
        }
        coverage_failures = validate_contract(bad_coverage)
        if not any("completed_layers must not be supplied" in item for item in coverage_failures):
            failures.append("self-declared capability completed_layers was accepted")

        enabled_start = start_long_task(
            "持续推进 RedCap 自开发 E2E 巡检，直到每轮问题都进入失败回流并完成真实修复。",
            risk_level="medium",
            run_dir=tmp / "enabled-start",
            action_evidence=["runtime/bin/redcap long-task start self-check enabled"],
        )
        if enabled_start.get("ok") is not True or enabled_start.get("active_run_created") is not True:
            failures.append("enabled long-task start did not create a valid active_run")
        else:
            active_run = load_json(pathlib.Path(enabled_start["active_run"]))
            if active_run.get("contract_kind") != "active_run":
                failures.append("enabled long-task start did not write contract_kind=active_run")
            if active_run.get("iteration_ledger", [{}])[0].get("status") != "running":
                failures.append("enabled long-task start did not create a running first iteration")
            behavior_artifact = tmp / "enabled-start" / "controlled-behavior-artifact.txt"
            behavior_artifact.write_text(
                "受控行为迭代产物：本文件由 self-check 在 start 之后写入，"
                "用于证明 record 记录的是后续行为证据，而不是 start 命令自身产物。"
                "内容包含足够长度和多样字符，避免空洞证据绕过。\n",
                encoding="utf-8",
            )
            record_result = record_long_task_iteration(
                pathlib.Path(enabled_start["active_run"]),
                status="failed",
                objective_delta="受控行为迭代写入非 start 产物，并把发现的问题进入失败回流账本。",
                action_evidence=[str(behavior_artifact)],
                blocker_signature="controlled-behavior-gap",
                failure_summary="受控行为迭代证明 record 能推进 active_run，而不只是创建入口文件。",
            )
            if record_result.get("ok") is not True:
                failures.append("long-task record did not keep active_run valid")
            else:
                recorded = load_json(pathlib.Path(enabled_start["active_run"]))
                if len(recorded.get("iteration_ledger", [])) < 2:
                    failures.append("long-task record did not append a behavior iteration")
                open_backlog = recorded.get("failure_backlog", {}).get("open", [])
                if not open_backlog:
                    failures.append("long-task record did not update failure_backlog.open")
            negative_start = start_long_task(
                "持续推进 RedCap 自开发 E2E 巡检，验证 record 负向证据门禁。",
                risk_level="medium",
                run_dir=tmp / "negative-record",
                action_evidence=["runtime/bin/redcap long-task start self-check negative"],
            )
            empty_artifact = tmp / "negative-record" / "empty-artifact.txt"
            empty_artifact.write_text("", encoding="utf-8")
            empty_record = record_long_task_iteration(
                pathlib.Path(negative_start["active_run"]),
                status="failed",
                objective_delta="这轮故意使用空证据文件，record 必须拒绝。",
                action_evidence=[str(empty_artifact)],
                blocker_signature="empty-evidence",
                failure_summary="空证据文件不应进入长任务账本。",
            )
            if empty_record.get("ok") is not False or not any("at least" in item for item in empty_record.get("failures", [])):
                failures.append("long-task record accepted an empty evidence file")
            tiny_artifact = tmp / "negative-record" / "tiny-artifact.txt"
            tiny_artifact.write_text("ok\n", encoding="utf-8")
            tiny_record = record_long_task_iteration(
                pathlib.Path(negative_start["active_run"]),
                status="failed",
                objective_delta="这轮故意使用过短证据文件，record 必须拒绝。",
                action_evidence=[str(tiny_artifact)],
                blocker_signature="tiny-evidence",
                failure_summary="过短证据文件不应进入长任务账本。",
            )
            if tiny_record.get("ok") is not False or not any("at least" in item for item in tiny_record.get("failures", [])):
                failures.append("long-task record accepted a tiny evidence file")
            repeated_artifact = tmp / "negative-record" / "repeated-artifact.txt"
            repeated_artifact.write_text("a" * MIN_ACTION_EVIDENCE_BYTES + "\n", encoding="utf-8")
            repeated_record = record_long_task_iteration(
                pathlib.Path(negative_start["active_run"]),
                status="failed",
                objective_delta="这轮故意使用重复字符证据文件，record 必须拒绝。",
                action_evidence=[str(repeated_artifact)],
                blocker_signature="repeated-evidence",
                failure_summary="重复字符证据文件不应进入长任务账本。",
            )
            if repeated_record.get("ok") is not False or not any("varied content" in item for item in repeated_record.get("failures", [])):
                failures.append("long-task record accepted repeated filler evidence")
            duplicate_artifact = tmp / "enabled-start" / "duplicate-delta-artifact.txt"
            duplicate_artifact.write_text(
                "重复 delta 负向测试产物：本文件足够长且内容多样，"
                "用于确认失败原因来自 objective_delta 重复，而不是证据文件本身不合格。"
                "如果 record 接受相同推进差量，就会重新引入原地踏步式伪迭代。\n",
                encoding="utf-8",
            )
            duplicate_record = record_long_task_iteration(
                pathlib.Path(enabled_start["active_run"]),
                status="failed",
                objective_delta="受控行为迭代写入非 start 产物，并把发现的问题进入失败回流账本。",
                action_evidence=[str(duplicate_artifact)],
                blocker_signature="duplicate-delta",
                failure_summary="重复推进差量不应进入长任务账本。",
            )
            if duplicate_record.get("ok") is not False or not any("differ from previous" in item for item in duplicate_record.get("failures", [])):
                failures.append("long-task record accepted duplicate objective_delta")
            external_artifact_dir = tmp / "external-worker"
            external_artifact_dir.mkdir(parents=True, exist_ok=True)
            external_artifact = external_artifact_dir / "feature-output.js"
            external_artifact.write_text(
                "/* 外部承接方源码变更证据：本文件模拟非 RedCap 自身写入的工程产物。 */\n"
                "export const verificationResult = { ok: true, command: 'npm test', stdout: 'passed' };\n",
                encoding="utf-8",
            )
            external_record = record_long_task_iteration(
                pathlib.Path(enabled_start["active_run"]),
                status="running",
                objective_delta="外部承接方写入源码产物，并由 record 作为真实行为证据入账。",
                action_evidence=[str(external_artifact)],
                blocker_signature="none",
                failure_summary="外部产物已进入长任务运行账本。",
            )
            if external_record.get("ok") is not True:
                failures.append("long-task record did not accept external worker artifact evidence")
            final_receipt = tmp / "enabled-start" / "final-receipt.json"
            final_receipt.write_text(json.dumps({
                "schema_id": "fixture-final-check",
                "command": "runtime/bin/redcap long-task self-check final fixture",
                "exit_code": 0,
                "ok": True,
                "stdout": "passed",
                "stderr": "",
                "evidence": "完成命令使用结构化回执收口当前 active_run。",
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            complete_result = complete_long_task(
                pathlib.Path(enabled_start["active_run"]),
                outcome="completed",
                final_objective_delta="最终结构化回执证明当前 active_run 已达到本轮终止条件，可以关闭。",
                completion_evidence=[str(final_receipt)],
                final_summary="当前 active_run 已用结构化完成证据关闭；这不代表 RedCap 完整复活。",
                blocker_signature="none",
            )
            if complete_result.get("ok") is not True:
                failures.append("long-task complete did not close a valid active_run")
            else:
                completed = load_json(pathlib.Path(enabled_start["active_run"]))
                if completed.get("lifecycle_state") != "completed":
                    failures.append("long-task complete did not set lifecycle_state=completed")
                if completed.get("failure_backlog", {}).get("open"):
                    failures.append("completed active_run still has open failure_backlog entries")
            second_complete = complete_long_task(
                pathlib.Path(enabled_start["active_run"]),
                outcome="completed",
                final_objective_delta="完成后故意再次 complete，必须被状态门禁拒绝。",
                completion_evidence=[str(final_receipt)],
                final_summary="已完成的 active_run 不应被重复关闭。",
                blocker_signature="double-complete",
            )
            if second_complete.get("ok") is not False or not any("lifecycle_state=running" in item for item in second_complete.get("failures", [])):
                failures.append("long-task complete accepted a second terminal transition")
            post_complete_record = record_long_task_iteration(
                pathlib.Path(enabled_start["active_run"]),
                status="running",
                objective_delta="完成后故意尝试继续记录，record 必须拒绝。",
                action_evidence=[str(final_receipt)],
                blocker_signature="post-complete-record",
                failure_summary="完成后的 active_run 不应继续追加普通迭代。",
            )
            if post_complete_record.get("ok") is not False or not any("lifecycle_state=running" in item for item in post_complete_record.get("failures", [])):
                failures.append("long-task record accepted iteration after complete")
            low_confidence_start = start_long_task(
                "持续推进 RedCap 自开发 E2E 巡检，验证低置信完成证据不能收口。",
                risk_level="medium",
                run_dir=tmp / "low-confidence-complete",
                action_evidence=["runtime/bin/redcap long-task start self-check low confidence"],
            )
            random_artifact = tmp / "low-confidence-complete" / "random-filler.txt"
            random_artifact.write_text("qwertyuiopasdfghjklzxcvbnm1234567890" * 3 + "\n", encoding="utf-8")
            low_confidence_complete = complete_long_task(
                pathlib.Path(low_confidence_start["active_run"]),
                outcome="completed",
                final_objective_delta="这轮故意使用随机填充证据收口，complete 必须拒绝。",
                completion_evidence=[str(random_artifact)],
                final_summary="随机填充证据不应关闭 active_run。",
                blocker_signature="low-confidence-evidence",
            )
            if low_confidence_complete.get("ok") is not False or not any("low confidence" in item for item in low_confidence_complete.get("failures", [])):
                failures.append("long-task complete accepted low-confidence filler evidence")
            irrelevant_start = start_long_task(
                "持续推进 RedCap 自开发 E2E 巡检，验证结构合法但语义无关的完成证据不能收口。",
                risk_level="medium",
                run_dir=tmp / "irrelevant-complete",
                action_evidence=["runtime/bin/redcap long-task start self-check irrelevant completion"],
            )
            irrelevant_receipt = tmp / "irrelevant-complete" / "irrelevant-receipt.json"
            irrelevant_receipt.write_text(json.dumps({
                "schema_id": "fixture-unrelated-check",
                "command": "echo banana",
                "exit_code": 0,
                "ok": True,
                "stdout": "passed banana inventory",
                "stderr": "",
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            irrelevant_complete = complete_long_task(
                pathlib.Path(irrelevant_start["active_run"]),
                outcome="completed",
                final_objective_delta="最终完成回执需要证明当前 active_run 已达到终止条件。",
                completion_evidence=[str(irrelevant_receipt)],
                final_summary="当前 active_run 必须由完成回执关闭。",
                blocker_signature="irrelevant-completion-evidence",
            )
            if irrelevant_complete.get("ok") is not False or not any("task-relevant completion markers" in item for item in irrelevant_complete.get("failures", [])):
                failures.append("long-task complete accepted structurally valid but irrelevant evidence")
            failed_start = start_long_task(
                "持续推进 RedCap 自开发 E2E 巡检，验证失败轮次可以终态收口且不会冒充完成。",
                risk_level="medium",
                run_dir=tmp / "failed-complete",
                action_evidence=["runtime/bin/redcap long-task start self-check failed completion"],
            )
            failed_receipt = tmp / "failed-complete" / "failed-receipt.json"
            failed_receipt.write_text(json.dumps({
                "schema_id": "fixture-failed-check",
                "command": "runtime/bin/redcap complete-revival-e2e run",
                "exit_code": 1,
                "ok": False,
                "stdout": "failed with structured evidence",
                "stderr": "",
                "failures": ["E2E harness timeout classification failed before fix"],
                "evidence": "失败命令使用结构化回执收口当前 active_run。",
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            failed_complete = complete_long_task(
                pathlib.Path(failed_start["active_run"]),
                outcome="failed",
                final_objective_delta="最终结构化失败回执证明当前 active_run 已达到失败终止条件，可以关闭并保留未解决问题。",
                completion_evidence=[str(failed_receipt)],
                final_summary="当前 active_run 已用结构化失败证据关闭；这不代表 RedCap 完整复活。",
                blocker_signature="self-check-failed-terminal",
            )
            if failed_complete.get("ok") is not True:
                failures.append("long-task complete did not accept failed terminal outcome")
            else:
                failed_packet = load_json(pathlib.Path(failed_start["active_run"]))
                if failed_packet.get("lifecycle_state") != "failed":
                    failures.append("failed complete did not set lifecycle_state=failed")
                if failed_packet.get("completion_boundary", {}).get("outcome") != "failed":
                    failures.append("failed complete did not set completion_boundary.outcome=failed")
                if not failed_packet.get("failure_backlog", {}).get("open"):
                    failures.append("failed active_run should keep an open failure backlog item")
            tampered_start = start_long_task(
                "持续推进 RedCap 自开发 E2E 巡检，验证直接篡改 lifecycle_state 不能通过合同。",
                risk_level="medium",
                run_dir=tmp / "tampered-state",
                action_evidence=["runtime/bin/redcap long-task start self-check tampered state"],
            )
            tampered_path = pathlib.Path(tampered_start["active_run"])
            tampered = load_json(tampered_path)
            tampered["lifecycle_state"] = "completed"
            tampered["completion_boundary"] = None
            write_json(tampered_path, tampered)
            tampered_check = check_payload(tampered_path)
            if tampered_check.get("ok") is not False or not any("completion_boundary" in item for item in tampered_check.get("failures", [])):
                failures.append("tampered terminal lifecycle_state without completion_boundary was accepted")

        fast_start = start_long_task(
            "解释这个字段是什么意思",
            risk_level="low",
            run_dir=tmp / "fast-start",
        )
        if fast_start.get("ok") is not True or fast_start.get("mode") != "fast_path":
            failures.append("low-risk long-task start did not use fast_path")
        if fast_start.get("active_run_created") is not False:
            failures.append("fast_path long-task start should not create active_run")

    validate_repository_integration(failures)
    print(json.dumps({
        "schema_id": "redcap-long-task-contract-self-check",
        "ok": not failures,
        "failures": failures,
    }, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_LONG_TASK_CONTRACT_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify RedCap long-task parent-objective contracts")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--packet", required=True)
    check.add_argument("--require-integration", action="store_true")
    check.set_defaults(func=cmd_check)
    decide = sub.add_parser("decide")
    decide.add_argument("--task")
    decide.add_argument("--request")
    decide.add_argument("--risk-level", default="low")
    decide.add_argument("--external-goal-status")
    decide.add_argument("--consecutive-failures", type=int, default=0)
    decide.add_argument("--boundary-count", type=int, default=0)
    decide.set_defaults(func=cmd_decide)
    start = sub.add_parser("start")
    start.add_argument("--task")
    start.add_argument("--request")
    start.add_argument("--risk-level", default="low")
    start.add_argument("--run-dir", required=True)
    start.add_argument("--external-goal-status")
    start.add_argument("--consecutive-failures", type=int, default=0)
    start.add_argument("--boundary-count", type=int, default=0)
    start.add_argument("--parent-objective")
    start.add_argument("--action-evidence", action="append")
    start.set_defaults(func=cmd_start)
    record = sub.add_parser("record")
    record.add_argument("--packet", required=True)
    record.add_argument("--status", required=True, choices=sorted(ITERATION_STATUSES - {"planned"}))
    record.add_argument("--objective-delta", required=True)
    record.add_argument("--action-evidence", action="append", required=True)
    record.add_argument("--blocker-signature", default="none")
    record.add_argument("--failure-summary")
    record.add_argument("--auto-rerun-allowed", action=argparse.BooleanOptionalAction, default=None)
    record.set_defaults(func=cmd_record)
    complete = sub.add_parser("complete")
    complete.add_argument("--packet", required=True)
    complete.add_argument("--outcome", required=True, choices=["completed", "failed", "blocked", "human_decision"])
    complete.add_argument("--final-objective-delta", required=True)
    complete.add_argument("--completion-evidence", action="append", required=True)
    complete.add_argument("--final-summary", required=True)
    complete.add_argument("--blocker-signature", default="none")
    complete.set_defaults(func=cmd_complete)
    boundary_check = sub.add_parser("boundary-check")
    boundary_check.add_argument("--out")
    boundary_check.set_defaults(func=cmd_boundary_check)
    self_check = sub.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

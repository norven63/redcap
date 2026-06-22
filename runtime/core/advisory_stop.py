#!/usr/bin/env python3
"""检查建议型 Stop（停止前检查钩子）契约和部署。"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "assets" / "contracts" / "advisory-stop.json"
LIVE_HOOKS = REPO_ROOT / ".codex" / "hooks.json"
TEMPLATE_HOOKS = REPO_ROOT / "assets" / "contracts" / "codex-hooks.template.json"
CODEX_HOOK = REPO_ROOT / "runtime" / "host-adapters" / "codex" / "codex-hook.py"
DEFAULT_EVIDENCE_DIR = REPO_ROOT / ".redcap" / "evidence" / "host-hooks" / "codex"
STOP_OVERRIDE_SCHEMA_ID = "redcap-stop-override-v1"
HEALTH_SCHEMA_ID = "redcap-advisory-stop-health-report"
HEALTH_STATES = {"healthy", "degraded", "blocked"}
HEALTH_REASONS = {
    "semantic_unavailable": "语义评审不可用、超时或返回非法结构",
    "rule_conflict": "确定性规则与语义评审或主轴回放结论冲突",
    "replay_failure": "主轴保持、最大轮次、覆盖标记等回放样本失败",
    "evidence_missing": "Stop 事件、修正轮次、覆盖标记、持续时间或检查来源等必需证据缺失",
}
BLOCKED_DEGRADED_THRESHOLD = 3


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}") from exc


def hook_commands(config: dict[str, Any], event: str) -> list[str]:
    commands: list[str] = []
    for group in config.get("hooks", {}).get(event, []) or []:
        if not isinstance(group, dict):
            continue
        for hook in group.get("hooks", []) or []:
            if isinstance(hook, dict) and hook.get("type") == "command" and isinstance(hook.get("command"), str):
                commands.append(hook["command"])
    return commands


def normalize_hook_config(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): normalize_hook_config(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [normalize_hook_config(item) for item in value]
    if isinstance(value, str):
        return value.replace(str(REPO_ROOT), "{REPO_ROOT}")
    return value


def run(argv: list[str], *, timeout_seconds: int = 150) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(argv, 124, stdout=exc.stdout or "", stderr="命令超时")


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def write_json_atomic(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def override_path(evidence_dir: pathlib.Path, session_id: str, turn_id: str) -> pathlib.Path:
    key = hashlib.sha256(f"{session_id}\n{turn_id}".encode("utf-8")).hexdigest()
    return evidence_dir / "stop-overrides" / f"{key}.json"


def write_override_marker(
    evidence_dir: pathlib.Path,
    *,
    session_id: str,
    turn_id: str,
    reason: str,
    source: str,
    expires_minutes: int,
) -> pathlib.Path:
    created = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    path = override_path(evidence_dir, session_id, turn_id)
    write_json_atomic(path, {
        "schema_id": STOP_OVERRIDE_SCHEMA_ID,
        "session_id": session_id,
        "turn_id": turn_id,
        "reason": reason,
        "source": source,
        "created_at": created.isoformat(),
        "expires_at": (created + dt.timedelta(minutes=expires_minutes)).isoformat(),
    })
    return path


def run_hook_event(
    event: str,
    payload: dict[str, Any],
    *,
    evidence_dir: pathlib.Path,
    extra_env: dict[str, str] | None = None,
    timeout_seconds: int = 120,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["REDCAP_CODEX_HOOK_EVIDENCE_DIR"] = str(evidence_dir)
    env["REDCAP_GATE_SEMANTIC_POLICY"] = "off"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(CODEX_HOOK), "--event", event],
        cwd=str(REPO_ROOT),
        input=json.dumps(payload, ensure_ascii=False),
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout_seconds,
    )


def leading_json(stdout: str) -> dict[str, Any]:
    parsed, _ = json.JSONDecoder().raw_decode(stdout.lstrip())
    if not isinstance(parsed, dict):
        raise ValueError("leading JSON is not an object")
    return parsed


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-advisory-stop-contract":
        failures.append("contract schema_id invalid")
    deployment = contract.get("deployment")
    if not isinstance(deployment, dict):
        failures.append("deployment missing")
    else:
        if deployment.get("hook_event") != "Stop":
            failures.append("deployment.hook_event must be Stop")
        if deployment.get("required_in_codex_hooks") is not True:
            failures.append("deployment.required_in_codex_hooks must be true")
        if deployment.get("hot_path_full_prism") is not False:
            failures.append("deployment.hot_path_full_prism must be false")
    schema = contract.get("advisory_payload_schema")
    if not isinstance(schema, dict):
        failures.append("advisory_payload_schema missing")
    else:
        required = set(schema.get("required_fields", []))
        for field in [
            "advisory_schema_id",
            "original_task_excerpt",
            "correction_constraints",
            "cap_may_override",
            "max_rounds",
            "current_round",
            "recovery_focus_anchor",
            "primary_response_axis",
            "advisory_is_meta_guidance",
            "do_not_answer_the_hook",
        ]:
            if field not in required:
                failures.append(f"advisory payload required field missing: {field}")
    constraints = contract.get("six_hard_constraints")
    if not isinstance(constraints, list) or len(constraints) != 6:
        failures.append("six_hard_constraints must contain exactly 6 items")
    else:
        ids = {item.get("id") for item in constraints if isinstance(item, dict)}
        for required_id in [
            "original-task-anchor",
            "concrete-correction-only",
            "cap-arbitration",
            "no-hook-axis-leakage",
            "max-correction-rounds",
            "health-observation",
        ]:
            if required_id not in ids:
                failures.append(f"six_hard_constraints missing {required_id}")
    health = contract.get("health_signals")
    if not isinstance(health, dict):
        failures.append("health_signals missing")
    else:
        states = set(health.get("states", [])) if isinstance(health.get("states"), list) else set()
        if states != HEALTH_STATES:
            failures.append("health_signals.states must be healthy/degraded/blocked")
        catalog = health.get("reason_catalog")
        if not isinstance(catalog, dict):
            failures.append("health_signals.reason_catalog missing")
        else:
            for reason in HEALTH_REASONS:
                item = catalog.get(reason)
                if not isinstance(item, dict) or not item.get("detect_when"):
                    failures.append(f"health_signals.reason_catalog.{reason}.detect_when missing")
        state_rules = health.get("state_rules")
        if not isinstance(state_rules, dict):
            failures.append("health_signals.state_rules missing")
        else:
            for state in HEALTH_STATES:
                if not isinstance(state_rules.get(state), str) or not state_rules[state].strip():
                    failures.append(f"health_signals.state_rules.{state} missing")
    return failures


def fixture_health_observations(fixture: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if fixture == "healthy":
        return [], {"critical_completion_claim": False, "consecutive_degraded_count": 0}
    if fixture == "degraded":
        return [
            {
                "reason": "semantic_unavailable",
                "severity": "degraded",
                "source": "fixture:semantic-timeout",
                "detail": "semantic review timed out and produced no valid judgment",
            },
            {
                "reason": "rule_conflict",
                "severity": "degraded",
                "source": "fixture:rule-conflict",
                "detail": "deterministic and semantic verdicts disagree",
            },
            {
                "reason": "replay_failure",
                "severity": "degraded",
                "source": "fixture:main-axis-replay",
                "detail": "main axis replay fixture failed",
            },
            {
                "reason": "evidence_missing",
                "severity": "degraded",
                "source": "fixture:marker",
                "detail": "required Stop marker field is absent",
            },
        ], {"critical_completion_claim": False, "consecutive_degraded_count": 1}
    if fixture == "blocked":
        return [
            {
                "reason": "evidence_missing",
                "severity": "degraded",
                "source": "fixture:critical-completion",
                "detail": "critical completion claim lacks required Stop marker evidence",
            }
        ], {"critical_completion_claim": True, "consecutive_degraded_count": BLOCKED_DEGRADED_THRESHOLD}
    raise ValueError(f"unsupported health fixture: {fixture}")


def advisory_health_report(
    observations: list[dict[str, Any]],
    *,
    critical_completion_claim: bool = False,
    consecutive_degraded_count: int = 0,
    source: str = "runtime",
) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    for item in observations:
        reason = item.get("reason")
        severity = item.get("severity") or "degraded"
        if reason not in HEALTH_REASONS:
            reason = "evidence_missing"
        if severity not in {"degraded", "blocked"}:
            severity = "degraded"
        normalized.append({
            "reason": reason,
            "reason_text": HEALTH_REASONS[reason],
            "severity": severity,
            "source": str(item.get("source") or source),
            "detail": str(item.get("detail") or HEALTH_REASONS[reason]),
        })
    reasons = sorted({item["reason"] for item in normalized})
    blocked_reasons = {
        item["reason"]
        for item in normalized
        if item["severity"] == "blocked"
        or (
            critical_completion_claim
            and item["reason"] in {"rule_conflict", "replay_failure", "evidence_missing"}
        )
    }
    escalation_reasons: list[str] = []
    if blocked_reasons:
        escalation_reasons.append("critical_or_blocked_observation")
    if consecutive_degraded_count >= BLOCKED_DEGRADED_THRESHOLD:
        escalation_reasons.append("consecutive_degraded_threshold")
    if blocked_reasons or consecutive_degraded_count >= BLOCKED_DEGRADED_THRESHOLD:
        state = "blocked"
    elif normalized:
        state = "degraded"
    else:
        state = "healthy"
    return {
        "schema_id": HEALTH_SCHEMA_ID,
        "state": state,
        "ok": state == "healthy",
        "source": source,
        "reasons": reasons,
        "observations": normalized,
        "critical_completion_claim": critical_completion_claim,
        "consecutive_degraded_count": consecutive_degraded_count,
        "blocked_threshold": BLOCKED_DEGRADED_THRESHOLD,
        "escalation_reasons": escalation_reasons,
    }


def validate_health_report(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if report.get("schema_id") != HEALTH_SCHEMA_ID:
        failures.append("health report schema_id invalid")
    state = report.get("state")
    if state not in HEALTH_STATES:
        failures.append(f"health report state invalid: {state}")
    observations = report.get("observations")
    if not isinstance(observations, list):
        failures.append("health report observations must be a list")
        observations = []
    reasons = report.get("reasons")
    if not isinstance(reasons, list):
        failures.append("health report reasons must be a list")
        reasons = []
    for index, item in enumerate(observations):
        if not isinstance(item, dict):
            failures.append(f"health observation[{index}] must be an object")
            continue
        if item.get("reason") not in HEALTH_REASONS:
            failures.append(f"health observation[{index}] reason invalid")
        if item.get("severity") not in {"degraded", "blocked"}:
            failures.append(f"health observation[{index}] severity invalid")
        if not isinstance(item.get("source"), str) or not item["source"].strip():
            failures.append(f"health observation[{index}] source missing")
    if state == "healthy" and (observations or reasons):
        failures.append("healthy report must not contain degraded observations or reasons")
    if state in {"degraded", "blocked"} and not observations:
        failures.append(f"{state} report requires observations")
    if state == "degraded" and report.get("ok") is True:
        failures.append("degraded report must not set ok=true")
    if state == "blocked" and not report.get("escalation_reasons"):
        failures.append("blocked report requires escalation_reasons")
    if state == "blocked" and report.get("ok") is True:
        failures.append("blocked report must not set ok=true")
    return failures


def run_health_regression() -> dict[str, Any]:
    failures: list[str] = []
    results: list[dict[str, Any]] = []
    for fixture, expected_state in [
        ("healthy", "healthy"),
        ("degraded", "degraded"),
        ("blocked", "blocked"),
    ]:
        observations, options = fixture_health_observations(fixture)
        report = advisory_health_report(
            observations,
            critical_completion_claim=options["critical_completion_claim"],
            consecutive_degraded_count=options["consecutive_degraded_count"],
            source=f"fixture:{fixture}",
        )
        case_failures = validate_health_report(report)
        if report.get("state") != expected_state:
            case_failures.append(f"expected state {expected_state}, got {report.get('state')}")
        if case_failures:
            failures.append(f"{fixture}: {'; '.join(case_failures)}")
        results.append({"fixture": fixture, "report": report, "failures": case_failures})
    invalid = {
        "schema_id": HEALTH_SCHEMA_ID,
        "state": "healthy",
        "ok": True,
        "source": "fixture:invalid",
        "reasons": ["semantic_unavailable"],
        "observations": [
            {
                "reason": "semantic_unavailable",
                "reason_text": HEALTH_REASONS["semantic_unavailable"],
                "severity": "degraded",
                "source": "fixture:invalid",
                "detail": "degraded signal incorrectly marked healthy",
            }
        ],
        "critical_completion_claim": False,
        "consecutive_degraded_count": 1,
        "blocked_threshold": BLOCKED_DEGRADED_THRESHOLD,
        "escalation_reasons": [],
    }
    invalid_failures = validate_health_report(invalid)
    if not invalid_failures:
        failures.append("invalid degraded-as-healthy sample should fail validation")
    results.append({"fixture": "invalid-degraded-as-healthy", "report": invalid, "failures": invalid_failures})
    return {"ok": not failures, "cases": results, "failures": failures}


def validate_hook_deployment() -> list[str]:
    failures: list[str] = []
    live = load_json(LIVE_HOOKS)
    template = load_json(TEMPLATE_HOOKS)
    if normalize_hook_config(live) != normalize_hook_config(template):
        failures.append("live .codex/hooks.json must match codex-hooks.template.json")
    commands = hook_commands(live, "Stop")
    if not commands:
        failures.append("Stop hook is not deployed in live hooks config")
    if not any("runtime/host-adapters/codex/codex-hook.py" in command and "--event Stop" in command for command in commands):
        failures.append("Stop hook does not call the Codex adapter with --event Stop")
    return failures


HOOK_AXIS_TERMS = ("stop", "hook", "钩子", "停止前检查", "拦截", "修正约束")
STATUS_PROMPT_TERMS = ("状态", "现状", "完成", "未完成", "还有", "哪些", "进度")
STATUS_ANSWER_TERMS = ("已完成", "未完成", "还有", "状态", "现状", "风险", "待办", "阻塞", "没有")


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(term.casefold() in lowered for term in terms)


def main_axis_retention_result(prompt: str, answer: str) -> dict[str, Any]:
    """对历史误伤样本做主轴保持回放，不作为通用自然语言理解器。"""
    stripped = answer.strip()
    first_segment = stripped[:140]
    prompt_asks_hook = contains_any(prompt, ("stop", "hook", "钩子", "停止前检查"))
    hook_index = min(
        [first_segment.casefold().find(term.casefold()) for term in HOOK_AXIS_TERMS if term.casefold() in first_segment.casefold()]
        or [-1]
    )
    status_prompt = contains_any(prompt, STATUS_PROMPT_TERMS)
    status_answer_index = min(
        [first_segment.find(term) for term in STATUS_ANSWER_TERMS if term in first_segment]
        or [-1]
    )
    failures: list[str] = []
    if hook_index == 0 and not prompt_asks_hook:
        failures.append("answer starts from Stop/Hook instead of the original user question")
    if status_prompt and status_answer_index < 0:
        failures.append("status/progress question lacks a direct status answer in the opening segment")
    if status_prompt and hook_index >= 0 and (status_answer_index < 0 or hook_index < status_answer_index):
        failures.append("Stop/Hook discussion appears before the direct status answer")
    return {
        "ok": not failures,
        "prompt": prompt,
        "answer_opening": first_segment,
        "status_prompt": status_prompt,
        "prompt_asks_hook": prompt_asks_hook,
        "failures": failures,
    }


def run_main_axis_replay() -> dict[str, Any]:
    cases = [
        {
            "id": "positive-status-direct-answer",
            "expected_ok": True,
            "prompt": "现在还有哪些任务没完成？",
            "answer": "还有三项未完成：RSP-02、RSP-21、RSP-25。Stop 建议只影响措辞，不改变这个状态结论。",
        },
        {
            "id": "positive-cause-direct-answer",
            "expected_ok": True,
            "prompt": "为什么刚才会偏航？",
            "answer": "原因是二次回答把内部检查当成了主轴。Stop 提示只是修正约束，不能替代原问题。",
        },
        {
            "id": "negative-status-stop-first",
            "expected_ok": False,
            "prompt": "现在还有哪些任务没完成？",
            "answer": "Stop 拦截是因为最后回复缺少动作证据，所以我先解释这个钩子的判断逻辑。",
        },
        {
            "id": "negative-status-no-answer",
            "expected_ok": False,
            "prompt": "当前进度状态是什么？",
            "answer": "这个问题触发了停止前检查，它认为需要重新组织语言并补充证据。",
        },
    ]
    failures: list[str] = []
    results: list[dict[str, Any]] = []
    for case in cases:
        result = main_axis_retention_result(case["prompt"], case["answer"])
        result["id"] = case["id"]
        result["expected_ok"] = case["expected_ok"]
        if result["ok"] is not case["expected_ok"]:
            failures.append(f"{case['id']} expected ok={case['expected_ok']} got {result['ok']}")
        results.append(result)
    return {
        "ok": not failures,
        "cases": results,
        "failures": failures,
    }


def validate_self_check() -> list[str]:
    failures: list[str] = []
    completed = run([sys.executable, str(CODEX_HOOK), "--self-check-intent-judge"])
    if completed.returncode != 0:
        failures.append("Codex hook self-check failed")
        return failures
    try:
        parsed, _ = json.JSONDecoder().raw_decode((completed.stdout or "").lstrip())
    except json.JSONDecodeError as exc:
        failures.append(f"Codex hook self-check returned invalid JSON: {exc}")
        return failures
    if not isinstance(parsed, dict) or parsed.get("ok") is not True:
        failures.append("Codex hook self-check did not return ok=true")
    return failures


def run_e2e_regression() -> dict[str, Any]:
    failures: list[str] = []
    main_axis_replay = run_main_axis_replay()
    if main_axis_replay.get("ok") is not True:
        failures.extend(str(item) for item in main_axis_replay.get("failures", []))
    with tempfile.TemporaryDirectory(prefix="redcap-advisory-stop-e2e-") as tmp:
        evidence_dir = pathlib.Path(tmp) / "evidence"
        session_id = "advisory-stop-e2e-session"
        turn_id = "advisory-stop-e2e-turn"
        prompt_text = "请修复建议型 Stop 的偏航问题，并只围绕这个原始任务收口。"
        prompt = run_hook_event(
            "UserPromptSubmit",
            {
                "prompt": prompt_text,
                "cwd": str(REPO_ROOT),
                "session_id": session_id,
                "turn_id": turn_id,
                "source": "advisory-stop-e2e-regression",
            },
            evidence_dir=evidence_dir,
        )
        if prompt.returncode != 0:
            failures.append(f"UserPromptSubmit failed: {prompt.stderr or prompt.stdout}")

        stop = run_hook_event(
            "Stop",
            {
                "cwd": str(REPO_ROOT),
                "session_id": session_id,
                "turn_id": turn_id,
                "last_assistant_message": "Stop 说需要改写，所以我接下来主要解释 Stop 的建议。",
                "source": "advisory-stop-e2e-regression",
            },
            evidence_dir=evidence_dir,
        )
        if stop.returncode != 0:
            failures.append(f"Stop failed: {stop.stderr or stop.stdout}")
            stop_payload: dict[str, Any] = {}
        else:
            try:
                stop_payload = leading_json(stop.stdout or "")
            except Exception as exc:
                failures.append(f"Stop did not emit JSON: {exc}")
                stop_payload = {}
        reason = str(stop_payload.get("reason") or "")
        if stop_payload.get("decision") != "block":
            failures.append("first Stop should block a closeout without action evidence")
        if prompt_text not in reason:
            failures.append("first Stop reason must preserve the original task excerpt")
        if not reason.startswith("请先直接回应原始用户问题："):
            failures.append("first Stop reason must start from the original user question, not the Stop advisory")
        if "不是新的用户任务" not in reason or "不得成为回复主题" not in reason:
            failures.append("first Stop reason must state that hook feedback is not the reply topic")
        if "被拦回复片段" in reason:
            failures.append("first Stop reason must not include blocked reply excerpts by default")

        marker_path = evidence_dir / "events.jsonl"
        stop_markers: list[dict[str, Any]] = []
        try:
            for line in marker_path.read_text(encoding="utf-8").splitlines():
                item = json.loads(line)
                if isinstance(item, dict) and item.get("event") == "Stop":
                    stop_markers.append(item)
        except OSError as exc:
            failures.append(f"missing Stop events: {exc}")
        first_marker = stop_markers[-1] if stop_markers else {}
        if first_marker.get("advisory_stop_schema_id") != "redcap-stop-advisory-v1":
            failures.append("first Stop marker must record advisory schema")
        if first_marker.get("advisory_stop_is_meta_guidance") is not True:
            failures.append("first Stop marker must record advisory_stop_is_meta_guidance=true")
        if not isinstance(first_marker.get("advisory_stop_primary_response_axis"), str):
            failures.append("first Stop marker must record advisory_stop_primary_response_axis")
        if first_marker.get("advisory_stop_current_round") != 1:
            failures.append("first Stop marker must consume exactly one correction round")
        if not isinstance(first_marker.get("stop_hook_duration_ms"), (int, float)):
            failures.append("first Stop marker must record stop_hook_duration_ms")
        if first_marker.get("redcap_check_attempted") is not False:
            failures.append("first Stop must not run full redcap check in the default hot path")

        fuse_session_id = "advisory-stop-fuse-session"
        fuse_turn_id = "advisory-stop-fuse-turn"
        fuse_prompt = run_hook_event(
            "UserPromptSubmit",
            {
                "prompt": "请修复建议型 Stop 达到最大修正轮次后的重复循环。",
                "cwd": str(REPO_ROOT),
                "session_id": fuse_session_id,
                "turn_id": fuse_turn_id,
                "source": "advisory-stop-e2e-fuse",
            },
            evidence_dir=evidence_dir,
        )
        if fuse_prompt.returncode != 0:
            failures.append(f"fuse UserPromptSubmit failed: {fuse_prompt.stderr or fuse_prompt.stdout}")
        fuse_payloads: list[dict[str, Any]] = []
        for round_index in range(1, 4):
            fuse_stop = run_hook_event(
                "Stop",
                {
                    "cwd": str(REPO_ROOT),
                    "session_id": fuse_session_id,
                    "turn_id": fuse_turn_id,
                    "last_assistant_message": "这是一个只解释状态、没有执行动作的回复。",
                    "source": f"advisory-stop-e2e-fuse-{round_index}",
                },
                evidence_dir=evidence_dir,
            )
            if fuse_stop.returncode != 0:
                failures.append(f"fuse Stop round {round_index} failed: {fuse_stop.stderr or fuse_stop.stdout}")
                continue
            try:
                fuse_payloads.append(leading_json(fuse_stop.stdout or ""))
            except Exception as exc:
                failures.append(f"fuse Stop round {round_index} did not emit JSON: {exc}")
        if len(fuse_payloads) >= 2:
            for round_index, fuse_payload in enumerate(fuse_payloads[:2], 1):
                if fuse_payload.get("decision") != "block":
                    failures.append(f"fuse Stop round {round_index} should block before max rounds are exhausted")
        final_fuse_payload = fuse_payloads[-1] if fuse_payloads else {}
        if final_fuse_payload.get("continue") is not True:
            failures.append("fuse Stop third round must continue after max rounds are exhausted")
        if final_fuse_payload.get("fuse_triggered") is not True:
            failures.append("fuse Stop third round must expose fuse_triggered=true")
        if final_fuse_payload.get("resolution_status") != "released_not_resolved":
            failures.append("fuse Stop third round must expose released_not_resolved status")
        try:
            fuse_markers = [
                item
                for item in (json.loads(line) for line in marker_path.read_text(encoding="utf-8").splitlines())
                if isinstance(item, dict)
                and item.get("event") == "Stop"
                and item.get("turn_id") == fuse_turn_id
            ]
        except OSError:
            fuse_markers = []
        final_fuse_marker = fuse_markers[-1] if fuse_markers else {}
        if final_fuse_marker.get("advisory_stop_fuse_triggered") is not True:
            failures.append("fuse Stop marker must record advisory_stop_fuse_triggered=true")
        if final_fuse_marker.get("advisory_stop_resolution_status") != "released_not_resolved":
            failures.append("fuse Stop marker must record released_not_resolved status")
        if final_fuse_marker.get("stop_hook_outcome") != "pass:max-correction-rounds-fuse":
            failures.append("fuse Stop marker must record pass:max-correction-rounds-fuse outcome")

        override_file = write_override_marker(
            evidence_dir,
            session_id=session_id,
            turn_id=turn_id,
            reason="E2E regression proves Cap can override a false positive while preserving the original task anchor.",
            source="advisory-stop-e2e-regression",
            expires_minutes=30,
        )
        override_stop = run_hook_event(
            "Stop",
            {
                "cwd": str(REPO_ROOT),
                "session_id": session_id,
                "turn_id": turn_id,
                "last_assistant_message": "我已回到原始任务，只说明这次修复的阶段状态。",
                "source": "advisory-stop-e2e-regression-override",
            },
            evidence_dir=evidence_dir,
        )
        if override_stop.returncode != 0:
            failures.append(f"override Stop failed: {override_stop.stderr or override_stop.stdout}")
            override_payload: dict[str, Any] = {}
        else:
            try:
                override_payload = leading_json(override_stop.stdout or "")
            except Exception as exc:
                failures.append(f"override Stop did not emit JSON: {exc}")
                override_payload = {}
        if override_payload.get("continue") is not True:
            failures.append("override Stop must continue after explicit Cap override marker")
        try:
            stop_markers = [
                item
                for item in (json.loads(line) for line in marker_path.read_text(encoding="utf-8").splitlines())
                if isinstance(item, dict) and item.get("event") == "Stop"
            ]
        except OSError:
            stop_markers = []
        override_marker = stop_markers[-1] if stop_markers else {}
        if override_marker.get("advisory_stop_override_used") is not True:
            failures.append("override Stop marker must record advisory_stop_override_used=true")
        if str(override_marker.get("advisory_stop_override_path") or "") != str(override_file):
            failures.append("override Stop marker must record the override marker path")
        if not isinstance(override_marker.get("stop_hook_duration_ms"), (int, float)):
            failures.append("override Stop marker must record stop_hook_duration_ms")
        if override_marker.get("redcap_check_attempted") is not False:
            failures.append("override Stop must not run full redcap check in the default hot path")
        timing_failure_stop = run_hook_event(
            "Stop",
            {
                "cwd": str(REPO_ROOT),
                "session_id": session_id,
                "turn_id": turn_id,
                "last_assistant_message": "我已回到原始任务，只说明这次修复的阶段状态。",
                "source": "advisory-stop-e2e-regression-timing-failure",
            },
            evidence_dir=evidence_dir,
            extra_env={"REDCAP_STOP_TIMING_FAIL_FOR_SELF_CHECK": "1"},
        )
        if timing_failure_stop.returncode != 0:
            failures.append(f"timing failure Stop should not crash: {timing_failure_stop.stderr or timing_failure_stop.stdout}")
            timing_failure_payload: dict[str, Any] = {}
        else:
            try:
                timing_failure_payload = leading_json(timing_failure_stop.stdout or "")
            except Exception as exc:
                failures.append(f"timing failure Stop did not emit JSON: {exc}")
                timing_failure_payload = {}
        if timing_failure_payload.get("continue") is not True:
            failures.append("timing failure Stop must still continue when an explicit Cap override marker is valid")
        return {
            "ok": not failures,
            "scenario": "advisory-stop-answer-drift-regression",
            "evidence_dir": str(evidence_dir),
            "override_file": str(override_file),
            "first_stop_duration_ms": first_marker.get("stop_hook_duration_ms"),
            "override_stop_duration_ms": override_marker.get("stop_hook_duration_ms"),
            "timing_failure_injection_continued": timing_failure_payload.get("continue") is True,
            "main_axis_replay": main_axis_replay,
            "failures": failures,
        }


def cmd_check(_: argparse.Namespace) -> int:
    contract = load_json(CONTRACT)
    failures = validate_contract(contract)
    failures.extend(validate_hook_deployment())
    failures.extend(validate_self_check())
    regression = run_e2e_regression()
    if regression.get("ok") is not True:
        failures.extend(str(item) for item in regression.get("failures", []))
    health_regression = run_health_regression()
    if health_regression.get("ok") is not True:
        failures.extend(str(item) for item in health_regression.get("failures", []))
    result = {
        "ok": not failures,
        "contract": str(CONTRACT.relative_to(REPO_ROOT)),
        "live_hooks": str(LIVE_HOOKS.relative_to(REPO_ROOT)),
        "template_hooks": str(TEMPLATE_HOOKS.relative_to(REPO_ROOT)),
        "e2e_regression": regression,
        "health_regression": health_regression,
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_ADVISORY_STOP_OK")
    return 0


def cmd_health_check(args: argparse.Namespace) -> int:
    if args.fixture == "invalid-degraded-as-healthy":
        report = {
            "schema_id": HEALTH_SCHEMA_ID,
            "state": "healthy",
            "ok": True,
            "source": "fixture:invalid-degraded-as-healthy",
            "reasons": ["semantic_unavailable"],
            "observations": [
                {
                    "reason": "semantic_unavailable",
                    "reason_text": HEALTH_REASONS["semantic_unavailable"],
                    "severity": "degraded",
                    "source": "fixture:invalid",
                    "detail": "degraded signal incorrectly marked healthy",
                }
            ],
            "critical_completion_claim": False,
            "consecutive_degraded_count": 1,
            "blocked_threshold": BLOCKED_DEGRADED_THRESHOLD,
            "escalation_reasons": [],
        }
    else:
        observations, options = fixture_health_observations(args.fixture)
        report = advisory_health_report(
            observations,
            critical_completion_claim=options["critical_completion_claim"],
            consecutive_degraded_count=options["consecutive_degraded_count"],
            source=f"fixture:{args.fixture}",
        )
    failures = validate_health_report(report)
    if args.expect_state and report.get("state") != args.expect_state:
        failures.append(f"expected state {args.expect_state}, got {report.get('state')}")
    result = {
        "ok": not failures and (
            report.get("state") == "healthy"
            or (args.allow_degraded and report.get("state") == "degraded")
            or (args.expect_state is not None and report.get("state") == args.expect_state)
        ),
        "report": report,
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_ADVISORY_STOP_HEALTH_OK")
        return 0
    return 1


def cmd_self_check(args: argparse.Namespace) -> int:
    return cmd_check(args)


def cmd_override(args: argparse.Namespace) -> int:
    evidence_dir = pathlib.Path(args.evidence_dir).resolve() if args.evidence_dir else DEFAULT_EVIDENCE_DIR
    path = write_override_marker(
        evidence_dir,
        session_id=args.session_id,
        turn_id=args.turn_id,
        reason=args.reason,
        source=args.source,
        expires_minutes=args.expires_minutes,
    )
    print(json.dumps({
        "ok": True,
        "override_path": str(path),
        "session_id": args.session_id,
        "turn_id": args.turn_id,
    }, ensure_ascii=False, indent=2))
    print("REDCAP_ADVISORY_STOP_OVERRIDE_OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="检查建议型 Stop（停止前检查钩子）")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("check")
    subparsers.add_parser("self-check")
    health = subparsers.add_parser("health-check")
    health.add_argument("--fixture", choices=["healthy", "degraded", "blocked", "invalid-degraded-as-healthy"], default="healthy")
    health.add_argument("--allow-degraded", action="store_true")
    health.add_argument("--expect-state", choices=sorted(HEALTH_STATES))
    override = subparsers.add_parser("override")
    override.add_argument("--session-id", required=True)
    override.add_argument("--turn-id", required=True)
    override.add_argument("--reason", required=True)
    override.add_argument("--source", default="redcap-advisory-stop-override")
    override.add_argument("--expires-minutes", type=int, default=30)
    override.add_argument("--evidence-dir")
    args = parser.parse_args()
    if args.command == "check":
        return cmd_check(args)
    if args.command == "self-check":
        return cmd_self_check(args)
    if args.command == "health-check":
        return cmd_health_check(args)
    if args.command == "override":
        return cmd_override(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())

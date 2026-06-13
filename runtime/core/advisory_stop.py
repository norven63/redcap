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
DEFAULT_EVIDENCE_DIR = REPO_ROOT / "assets" / "evidence" / "host-hooks" / "codex"
STOP_OVERRIDE_SCHEMA_ID = "redcap-stop-override-v1"


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
    return failures


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
        if first_marker.get("advisory_stop_current_round") != 1:
            failures.append("first Stop marker must consume exactly one correction round")
        if not isinstance(first_marker.get("stop_hook_duration_ms"), (int, float)):
            failures.append("first Stop marker must record stop_hook_duration_ms")
        if first_marker.get("redcap_check_attempted") is not False:
            failures.append("first Stop must not run full redcap check in the default hot path")

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
    result = {
        "ok": not failures,
        "contract": str(CONTRACT.relative_to(REPO_ROOT)),
        "live_hooks": str(LIVE_HOOKS.relative_to(REPO_ROOT)),
        "template_hooks": str(TEMPLATE_HOOKS.relative_to(REPO_ROOT)),
        "e2e_regression": regression,
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_ADVISORY_STOP_OK")
    return 0


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
    if args.command == "override":
        return cmd_override(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())

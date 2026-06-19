#!/usr/bin/env python3
"""Executable RedCap 1.0 trace across hook, ownership, FSM, and completion gates."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REDCAP = REPO_ROOT / "runtime" / "bin" / "redcap"
CODEX_HOOK = REPO_ROOT / "runtime" / "host-adapters" / "codex" / "codex-hook.py"
FINAL_CLAIM_GUARD = REPO_ROOT / "runtime" / "core" / "final_claim_guard.py"
OLD_REDCAP_ROOT = pathlib.Path("/Users/norven/workspace/redcap")


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def clean_env(tmp: pathlib.Path) -> dict[str, str]:
    env = os.environ.copy()
    env["REDCAP_CODEX_HOOK_EVIDENCE_DIR"] = str(tmp / "hook-evidence")
    env["REDCAP_RUNTIME_BASE_DIR"] = str(tmp / "runtime-state")
    env["PYTHONPATH"] = ""
    return env


def run(
    argv: list[str],
    *,
    env: dict[str, str],
    stdin: dict[str, Any] | None = None,
    cwd: pathlib.Path = REPO_ROOT,
) -> dict[str, Any]:
    completed = subprocess.run(
        argv,
        cwd=str(cwd),
        env=env,
        input=json.dumps(stdin, ensure_ascii=False) if stdin is not None else None,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "argv": argv,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def parse_leading_json(stdout: str) -> dict[str, Any]:
    parsed, _ = json.JSONDecoder().raw_decode(stdout.lstrip())
    if not isinstance(parsed, dict):
        raise ValueError("leading JSON is not an object")
    return parsed


def load_json(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object expected: {path}")
    return payload


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def assert_ok(condition: bool, failures: list[str], message: str) -> None:
    if not condition:
        failures.append(message)


def old_path_leaks(commands: list[dict[str, Any]], env: dict[str, str]) -> list[str]:
    old = str(OLD_REDCAP_ROOT)
    leaks: list[str] = []
    for command in commands:
        argv_text = "\n".join(str(item) for item in command.get("argv", []))
        if old in argv_text:
            leaks.append(f"subprocess argv references old RedCap path: {command.get('argv')}")
    if old in os.pathsep.join(sys.path):
        leaks.append("current sys.path references old RedCap path")
    if old in env.get("PYTHONPATH", ""):
        leaks.append("PYTHONPATH references old RedCap path")
    return leaks


def trace(tmp: pathlib.Path) -> dict[str, Any]:
    env = clean_env(tmp)
    failures: list[str] = []
    commands: list[dict[str, Any]] = []
    session_id = "e2e-trace-session"
    task_id = "e2e-trace-task"

    pretool_payload = {
        "cwd": str(REPO_ROOT),
        "hook_event_name": "PreToolUse",
        "permission_mode": "default",
        "session_id": session_id,
        "turn_id": task_id,
        "tool_name": "Bash",
        "tool_input": {"command": f"touch {tmp / 'mutating-marker'}"},
        "tool_use_id": "e2e-trace-tool",
        "transcript_path": str(tmp / "transcript.jsonl"),
    }
    pretool = run([sys.executable, str(CODEX_HOOK), "--event", "PreToolUse"], env=env, stdin=pretool_payload)
    commands.append(pretool)
    assert_ok(pretool["exit_code"] == 0, failures, "PreToolUse hook did not exit cleanly")
    pretool_marker = load_json(tmp / "hook-evidence" / "latest-PreToolUse.json")
    claim = pretool_marker.get("session_ownership_claim") if isinstance(pretool_marker.get("session_ownership_claim"), dict) else {}
    assert_ok(claim.get("attempted") is True, failures, "PreToolUse did not attempt session ownership claim")

    ownership = run([
        str(REDCAP),
        "session-ownership",
        "check",
        "--host",
        "codex",
        "--session-id",
        session_id,
        "--task-id",
        task_id,
    ], env=env)
    commands.append(ownership)
    ownership_payload = parse_leading_json(ownership["stdout"])
    assert_ok(ownership["exit_code"] == 0 and ownership_payload.get("state") == "owned", failures, "session ownership check did not confirm owned state")

    transitions = [
        ("INTAKE", "PRISM_REVIEW", "gate_required_or_optional"),
        ("PRISM_REVIEW", "IMPLEMENTING", "prism_review_or_explicit_skip"),
        ("IMPLEMENTING", "VERIFYING", "runtime_change"),
        ("VERIFYING", "TEMPORARY_USABLE", "redcap_check_passed"),
    ]
    for source, target, evidence in transitions:
        result = run([
            str(REDCAP),
            "fsm",
            "transition",
            "--from",
            source,
            "--to",
            target,
            "--evidence",
            evidence,
        ], env=env)
        commands.append(result)
        payload = parse_leading_json(result["stdout"])
        assert_ok(result["exit_code"] == 0 and payload.get("ok") is True, failures, f"FSM transition failed: {source}->{target}")

    completion_session = "e2e-completion-session"
    completion_turn = "e2e-completion-turn"
    events_path = tmp / "completion-events.jsonl"
    append_jsonl(events_path, {
        "event": "UserPromptSubmit",
        "session_id": completion_session,
        "turn_id": completion_turn,
        "recorded_at": iso_now(),
        "gate_decision": "required",
        "prompt": {"normalized_excerpt": "Please implement the e2e trace fixture."},
    })
    marker_path = tmp / "latest-completion.json"
    blocked = run([
        sys.executable,
        str(FINAL_CLAIM_GUARD),
        "check",
        "--message",
        "已完成。",
        "--events",
        str(events_path),
        "--completion-marker",
        str(marker_path),
        "--session-id",
        completion_session,
        "--turn-id",
        completion_turn,
    ], env=env)
    commands.append(blocked)
    blocked_payload = parse_leading_json(blocked["stdout"])
    assert_ok(blocked["exit_code"] != 0 and blocked_payload.get("ok") is False, failures, "final claim guard did not block missing lifecycle marker")

    purification_dir = tmp / "self-purification"
    knowledge_path = purification_dir / "knowledge-retrieval-evidence.json"
    candidates_path = purification_dir / "self-purification-candidates.json"
    persona_path = purification_dir / "persona-distillation-decision.json"
    write_json(knowledge_path, {
        "schema_id": "redcap-self-purification-knowledge-retrieval",
        "query": "e2e trace fixture completion",
        "matches": [],
        "result_handling": "record_no_relevant_entry",
    })
    write_json(candidates_path, {
        "schema_id": "redcap-self-purification-candidates",
        "task_summary": "e2e trace fixture completion",
        "candidates": [
            {
                "id": "e2e-trace-completion-binding",
                "source_task": "e2e-trace-fixture",
                "trigger": "completion_claim_correction",
                "lesson": "完成态生命周期包必须携带自我净化证据，才能写入完成标记。",
            }
        ],
        "decisions": [
            {
                "candidate_id": "e2e-trace-completion-binding",
                "decision": "no_promote",
                "reason": "fixture 只验证完成态绑定，不晋升公共知识。",
            }
        ],
    })
    write_json(persona_path, {
        "schema_id": "redcap-cap-persona-boundary-decision",
        "candidate_id": "e2e-trace-completion-binding",
        "decision": "not_persona",
        "reason": "fixture 不包含 Cap 私有人格正文。",
        "hash": "fixture",
        "counts": {"lesson_chars": 29},
    })

    completion_packet = {
        "schema_id": "redcap-development-lifecycle-packet",
        "task_id": completion_turn,
        "fsm_state": "TEMPORARY_USABLE",
        "requirement_review": {
            "user_intent": "fixture completion",
            "target_reality": "e2e trace completion marker generated by lifecycle checker",
            "non_goals": ["release"],
            "risk_level": "medium",
        },
        "technical_review": {
            "runtime_boundary_checked": True,
            "prism_gate_decision": "required",
            "rollback_plan": "delete temp fixture",
            "verification_plan": ["runtime/bin/redcap e2e-trace self-check"],
        },
        "prism_review": {
            "merge_path": "runtime/prism/examples/prism-concern-resolution.merge.pass.json",
            "resolution_path": "runtime/prism/examples/prism-concern-resolution.valid-pass-merge.json",
        },
        "prompt_context": {
            "source_prompt_excerpt": "Please implement the e2e trace fixture.",
            "prompt_kind": "directive",
            "authorized_scope": "completion",
        },
        "task_body": {
            "requested_outcome": "fixture completion marker",
            "primary_deliverable": "completion marker",
            "acceptance_criteria": ["marker generated by lifecycle checker"],
            "status": "verified",
            "evidence_kind": "code",
            "evidence": ["runtime/core/e2e_trace.py"],
        },
        "review_tracks": {
            "architecture": {
                "status": "checked",
                "findings": ["The fixture uses the existing development lifecycle checker and final-claim guard."],
                "evidence": ["runtime/core/development_lifecycle.py", "runtime/core/e2e_trace.py"],
            },
            "governance": {
                "status": "checked",
                "findings": ["The completion marker is generated only after task-body evidence is verified."],
                "evidence": ["runtime/core/final_claim_guard.py", "runtime/core/development_lifecycle.py"],
            },
            "contracts": {
                "status": "checked",
                "findings": ["The fixture names concrete implementation and verification evidence."],
                "evidence": ["runtime/bin/redcap e2e-trace self-check"],
            },
        },
        "fsm_transition": {
            "from": "VERIFYING",
            "to": "TEMPORARY_USABLE",
            "evidence": ["redcap_check_passed"],
        },
        "implementation_evidence": ["runtime/core/e2e_trace.py"],
        "verification_evidence": ["runtime/bin/redcap e2e-trace self-check"],
        "completion_claim": {"present": True, "evidence_kind": "code"},
        "self_purification": {
            "knowledge_retrieval_evidence": str(knowledge_path),
            "post_task_harvest": {
                "candidates_path": str(candidates_path),
            },
            "review_decision": {
                "decision": "no_promote",
                "reason": "fixture 只验证完成态绑定，不晋升公共知识。",
            },
            "promotion_or_no_promote_result": {
                "decision": "no_promote",
                "reason": "fixture remains local evidence.",
            },
            "persona_boundary_evidence": str(persona_path),
        },
    }
    packet_path = tmp / "completion-packet.json"
    write_json(packet_path, completion_packet)
    lifecycle = run([
        str(REDCAP),
        "lifecycle",
        "check",
        "--packet",
        str(packet_path),
        "--events",
        str(events_path),
        "--completion-marker",
        str(marker_path),
    ], env=env)
    commands.append(lifecycle)
    lifecycle_payload = parse_leading_json(lifecycle["stdout"])
    assert_ok(lifecycle["exit_code"] == 0 and lifecycle_payload.get("ok") is True, failures, "development lifecycle did not create a valid completion marker")
    assert_ok(marker_path.exists(), failures, "completion marker was not written by development lifecycle")

    allowed = run([
        sys.executable,
        str(FINAL_CLAIM_GUARD),
        "check",
        "--message",
        "已完成。",
        "--events",
        str(events_path),
        "--completion-marker",
        str(marker_path),
        "--session-id",
        completion_session,
        "--turn-id",
        completion_turn,
    ], env=env)
    commands.append(allowed)
    allowed_payload = parse_leading_json(allowed["stdout"])
    assert_ok(
        allowed["exit_code"] == 0
        and allowed_payload.get("ok") is True
        and allowed_payload.get("completion_claim_detected") is True,
        failures,
        "final claim guard did not accept lifecycle-generated completion marker",
    )

    failures.extend(old_path_leaks(commands, env))
    return {
        "ok": not failures,
        "steps": {
            "pretool_claim": claim.get("attempted") is True,
            "ownership_state": ownership_payload.get("state"),
            "fsm_transitions": len(transitions),
            "completion_blocked_without_marker": blocked_payload.get("ok") is False,
            "completion_allowed_with_lifecycle_marker": allowed_payload.get("ok") is True,
            "old_redcap_path": str(OLD_REDCAP_ROOT),
        },
        "commands": [
            {
                "argv": command["argv"],
                "exit_code": command["exit_code"],
            }
            for command in commands
        ],
        "failures": failures,
    }


def cmd_check(args: argparse.Namespace) -> int:
    tmp = pathlib.Path(args.tmp_dir).resolve() if args.tmp_dir else None
    if tmp is not None:
        tmp.mkdir(parents=True, exist_ok=True)
        result = trace(tmp)
    else:
        with tempfile.TemporaryDirectory(prefix="redcap-e2e-trace-") as tmp_raw:
            result = trace(pathlib.Path(tmp_raw))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        return 1
    print("REDCAP_E2E_TRACE_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the RedCap 1.0 end-to-end trace")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--tmp-dir")
    check.set_defaults(func=cmd_check)
    self_check = sub.add_parser("self-check")
    self_check.add_argument("--tmp-dir")
    self_check.set_defaults(func=cmd_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

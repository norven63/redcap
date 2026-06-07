#!/usr/bin/env python3
"""RedCap development lifecycle evidence gate built on the FSM, not beside it."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "runtime" / "core"))
from fsm import STATES, transition_allowed  # noqa: E402
from prompt_intent import (  # noqa: E402
    normalize_prompt_text,
    prompt_has_directive_authority,
    prompt_text_from_event,
)


DEFAULT_EVENTS = REPO_ROOT / "assets" / "evidence" / "host-hooks" / "codex" / "events.jsonl"
REQUIRED_REVIEW_FIELDS = {"user_intent", "target_reality", "non_goals", "risk_level"}
REQUIRED_TECH_FIELDS = {"runtime_boundary_checked", "prism_gate_decision", "rollback_plan", "verification_plan"}
REQUIRED_TASK_BODY_FIELDS = {"requested_outcome", "primary_deliverable", "acceptance_criteria", "status", "evidence_kind", "evidence"}
REQUIRED_PROMPT_CONTEXT_FIELDS = {"source_prompt_excerpt", "prompt_kind", "authorized_scope"}
REQUIRED_REVIEW_TRACK_IDS = {"architecture", "governance", "contracts"}
PRISM_REVIEW_REQUIRED_TARGETS = {"IMPLEMENTING", "VERIFYING", "TEMPORARY_USABLE"}
TASK_BODY_STATUSES = {"planned", "in_progress", "implemented", "verified", "blocked", "deferred"}
PROMPT_KINDS = {"question", "directive", "mixed"}
AUTHORIZED_SCOPES = {"answer_only", "review_only", "implementation", "completion"}
REVIEW_TRACK_STATUSES = {"checked", "not_applicable"}
REVIEW_TRACK_REQUIRED_RISKS = {"medium", "high", "critical"}
GENERIC_REVIEW_TEXT = {
    "done",
    "ok",
    "pass",
    "passed",
    "checked",
    "reviewed",
    "complete",
    "completed",
    "yes",
    "true",
    "已检查",
    "已评审",
    "已审查",
    "通过",
    "完成",
    "无问题",
}
TASK_BODY_EVIDENCE_KINDS = {"code", "code-and-review", "runtime-change", "runtime_change", "test", "migration"}
REVIEW_EVIDENCE_KINDS = {"review-task"}
LEGACY_EVIDENCE_KINDS = {"mixed"}
EVIDENCE_KINDS = TASK_BODY_EVIDENCE_KINDS | REVIEW_EVIDENCE_KINDS | LEGACY_EVIDENCE_KINDS
PROOF_ONLY_COMPLETION_KINDS = {"docs", "documentation", "ledger", "receipt", "report", "governance", "prism-review", "gate-check", "checklist", "metadata", "writeup", "spec"}
COMPLETION_MARKER = REPO_ROOT / "assets" / "evidence" / "lifecycle" / "latest-completion.json"


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"lifecycle packet must be a JSON object: {path}")
    return payload


def load_json_object(path: pathlib.Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} cannot be loaded: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return payload


def resolve_reference_path(raw: str, base_dir: pathlib.Path | None = None) -> pathlib.Path:
    path = pathlib.Path(raw)
    if path.is_absolute():
        return path.resolve()
    if base_dir is not None:
        candidate = (base_dir / path).resolve()
        if candidate.exists():
            return candidate
    return (REPO_ROOT / path).resolve()


def parse_leading_json(stdout: str) -> dict[str, Any] | None:
    try:
        parsed, _ = json.JSONDecoder().raw_decode(stdout.lstrip())
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def collect_string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(collect_string_values(item))
        return items
    if isinstance(value, dict):
        items = []
        for item in value.values():
            items.extend(collect_string_values(item))
        return items
    return []


def non_empty_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def substantive_text(value: str) -> bool:
    compact = re.sub(r"[\W_]+", "", value.casefold(), flags=re.UNICODE)
    if len(compact) < 12:
        return False
    return compact not in GENERIC_REVIEW_TEXT


def has_substantive_text(values: Any) -> bool:
    return isinstance(values, list) and any(isinstance(item, str) and substantive_text(item) for item in values)


def has_reference_like_evidence(values: Any) -> bool:
    if not isinstance(values, list):
        return False
    for item in values:
        if not isinstance(item, str):
            continue
        stripped = item.strip()
        if "/" in stripped or "." in pathlib.PurePosixPath(stripped).name or stripped.startswith("runtime/bin/redcap"):
            return True
    return False


def looks_like_prism_merge_path(value: str) -> bool:
    name = pathlib.Path(value).name.lower()
    return "merge" in name and name.endswith(".json")


def resolution_sibling_for_merge(merge_path: pathlib.Path) -> pathlib.Path | None:
    candidates = [
        merge_path.with_name("resolution.json"),
        merge_path.with_name(merge_path.name.replace("merge", "resolution", 1)),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def run_prism_resolution_check(
    merge_path: pathlib.Path,
    resolution_path: pathlib.Path,
    manifest_path: pathlib.Path | None = None,
) -> tuple[bool, list[str], dict[str, Any] | None]:
    argv = [
        str(REPO_ROOT / "runtime" / "bin" / "redcap"),
        "prism-resolution",
        "--merge",
        str(merge_path),
        "--resolution",
        str(resolution_path),
    ]
    if manifest_path is not None:
        argv.extend(["--manifest", str(manifest_path)])
    completed = subprocess.run(argv, cwd=str(REPO_ROOT), check=False, capture_output=True, text=True)
    parsed = parse_leading_json(completed.stdout)
    if completed.returncode == 0 and parsed is not None and parsed.get("ok") is True:
        return True, [], parsed
    failures: list[str] = []
    if parsed is not None and isinstance(parsed.get("failures"), list):
        failures.extend(str(item) for item in parsed["failures"])
    else:
        failures.append((completed.stdout or completed.stderr or "prism-resolution failed without parseable output").strip())
    return False, failures, parsed


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_events(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def latest_prompt_event(events_path: pathlib.Path) -> dict[str, Any] | None:
    prompts = [event for event in load_events(events_path) if event.get("event") == "UserPromptSubmit"]
    return prompts[-1] if prompts else None


def prompt_excerpt_is_meaningful(excerpt: str, actual_prompt: str) -> bool:
    normalized_excerpt = normalize_prompt_text(excerpt)
    normalized_actual = normalize_prompt_text(actual_prompt)
    if normalized_excerpt not in normalized_actual:
        return False
    if len(normalized_actual) < 16:
        return normalized_excerpt == normalized_actual and len(normalized_excerpt) >= 6
    if len(normalized_excerpt) < 16:
        return False
    return len(normalized_excerpt) / max(len(normalized_actual), 1) >= 0.2


def continuation_authorization_is_valid(
    prompt_context: dict[str, Any],
    prompt_event: dict[str, Any],
    actual_prompt: str,
    authorized_scope: Any,
) -> tuple[bool, str | None]:
    auth = prompt_context.get("continuation_authorization")
    if not isinstance(auth, dict):
        return False, None
    if auth.get("mode") != "same_session_authorized_continuation":
        return False, "prompt_context.continuation_authorization.mode invalid"
    source = auth.get("source")
    if source not in {"codex_goal", "same_session_resume", "automatic_continuation"}:
        return False, "prompt_context.continuation_authorization.source invalid"
    session_id = auth.get("session_id")
    event_session_id = prompt_event.get("session_id")
    if not (isinstance(session_id, str) and session_id.strip()):
        return False, "prompt_context.continuation_authorization.session_id is required"
    if session_id != event_session_id:
        return False, "prompt_context.continuation_authorization.session_id does not match latest UserPromptSubmit session"
    base_excerpt = auth.get("base_prompt_excerpt")
    if not (isinstance(base_excerpt, str) and base_excerpt.strip()):
        return False, "prompt_context.continuation_authorization.base_prompt_excerpt is required"
    if not prompt_excerpt_is_meaningful(base_excerpt, actual_prompt):
        return False, "prompt_context.continuation_authorization.base_prompt_excerpt does not match latest UserPromptSubmit prompt"
    continuation_excerpt = prompt_context.get("source_prompt_excerpt")
    if not (isinstance(continuation_excerpt, str) and substantive_text(continuation_excerpt)):
        return False, "prompt_context.source_prompt_excerpt must describe the continuation task"
    if authorized_scope not in {"implementation", "completion"}:
        return False, "prompt_context.continuation_authorization requires implementation or completion scope"
    if not prompt_has_directive_authority(actual_prompt):
        return False, "prompt_context.continuation_authorization requires a directive base UserPromptSubmit"
    return True, None


def validate_task_body(packet: dict[str, Any], failures: list[str]) -> None:
    task_body = packet.get("task_body")
    if not isinstance(task_body, dict):
        failures.append("task_body must be an object")
        return
    missing = sorted(REQUIRED_TASK_BODY_FIELDS - set(task_body))
    if missing:
        failures.append(f"task_body missing: {', '.join(missing)}")
    for key in ["requested_outcome", "primary_deliverable"]:
        if key in task_body and not (isinstance(task_body.get(key), str) and task_body[key].strip()):
            failures.append(f"task_body.{key} must be a non-empty string")
    criteria = task_body.get("acceptance_criteria")
    if criteria is not None and not (
        isinstance(criteria, list)
        and bool(criteria)
        and all(isinstance(item, str) and item.strip() for item in criteria)
    ):
        failures.append("task_body.acceptance_criteria must be a non-empty string list")
    status = task_body.get("status")
    if status is not None and status not in TASK_BODY_STATUSES:
        failures.append(f"task_body.status invalid: {status}")
    evidence = task_body.get("evidence")
    if evidence is not None and not (
        isinstance(evidence, list)
        and bool(evidence)
        and all(isinstance(item, str) and item.strip() for item in evidence)
    ):
        failures.append("task_body.evidence must be a non-empty string list")
    evidence_kind = task_body.get("evidence_kind")
    if evidence_kind is not None and not (isinstance(evidence_kind, str) and evidence_kind.strip()):
        failures.append("task_body.evidence_kind must be a non-empty string")
    if isinstance(evidence_kind, str) and evidence_kind.strip():
        if evidence_kind not in EVIDENCE_KINDS:
            failures.append("task_body.evidence_kind must be one of the allowed evidence kinds")
    completion_claim = packet.get("completion_claim")
    completion_present = isinstance(completion_claim, dict) and completion_claim.get("present") is True
    transition = packet.get("fsm_transition")
    transition_target = transition.get("to") if isinstance(transition, dict) else None
    prompt_context = packet.get("prompt_context")
    authorized_scope = prompt_context.get("authorized_scope") if isinstance(prompt_context, dict) else None
    if completion_present:
        if status != "verified":
            failures.append("completion_claim requires task_body.status=verified")
        if str(evidence_kind) not in TASK_BODY_EVIDENCE_KINDS:
            failures.append("completion_claim requires task_body.evidence_kind to be one of the allowed task-body evidence kinds")
        if authorized_scope != "completion":
            failures.append("completion_claim requires prompt_context.authorized_scope=completion")
    if (
        not completion_present
        and transition_target in {"IMPLEMENTING", "VERIFYING", "TEMPORARY_USABLE"}
        and str(evidence_kind) not in TASK_BODY_EVIDENCE_KINDS
    ):
        failures.append("FSM transition to IMPLEMENTING or beyond requires task_body.evidence_kind to be one of the allowed task-body evidence kinds")
    if (
        not completion_present
        and transition_target in {"IMPLEMENTING", "VERIFYING", "TEMPORARY_USABLE"}
        and status not in {"implemented", "verified"}
    ):
        failures.append("FSM transition to IMPLEMENTING or beyond requires task_body.status implemented or verified even when completion_claim is not present")
    if transition_target in {"IMPLEMENTING", "VERIFYING", "TEMPORARY_USABLE"} and authorized_scope not in {"implementation", "completion"}:
        failures.append("FSM transition to IMPLEMENTING or beyond requires prompt_context.authorized_scope implementation or completion")
    if transition_target == "VERIFYING" and status not in {"implemented", "verified"}:
        failures.append("IMPLEMENTING->VERIFYING requires task_body.status implemented or verified")
    if transition_target == "TEMPORARY_USABLE" and status != "verified":
        failures.append("VERIFYING->TEMPORARY_USABLE requires task_body.status=verified")


def validate_prompt_context(packet: dict[str, Any], failures: list[str], events_path: pathlib.Path) -> None:
    prompt_context = packet.get("prompt_context")
    if not isinstance(prompt_context, dict):
        failures.append("prompt_context must be an object")
        return
    missing = sorted(REQUIRED_PROMPT_CONTEXT_FIELDS - set(prompt_context))
    if missing:
        failures.append(f"prompt_context missing: {', '.join(missing)}")
    excerpt = prompt_context.get("source_prompt_excerpt")
    if excerpt is not None and not (isinstance(excerpt, str) and excerpt.strip()):
        failures.append("prompt_context.source_prompt_excerpt must be a non-empty string")
    prompt_kind = prompt_context.get("prompt_kind")
    if prompt_kind is not None and prompt_kind not in PROMPT_KINDS:
        failures.append(f"prompt_context.prompt_kind invalid: {prompt_kind}")
    authorized_scope = prompt_context.get("authorized_scope")
    if authorized_scope is not None and authorized_scope not in AUTHORIZED_SCOPES:
        failures.append(f"prompt_context.authorized_scope invalid: {authorized_scope}")
    if prompt_kind == "question" and authorized_scope in {"implementation", "completion"}:
        failures.append("question-only prompt cannot authorize implementation or completion without an explicit directive")
    if isinstance(excerpt, str) and excerpt.strip():
        prompt_event = latest_prompt_event(events_path)
        if prompt_event is None:
            failures.append(f"prompt_context.source_prompt_excerpt cannot be verified: no UserPromptSubmit event in {events_path}")
        else:
            actual_prompt = prompt_text_from_event(prompt_event)
            if actual_prompt is None:
                failures.append("prompt_context.source_prompt_excerpt cannot be verified: latest UserPromptSubmit event has no prompt text excerpt")
            elif not prompt_excerpt_is_meaningful(excerpt, actual_prompt):
                continuation_ok, continuation_failure = continuation_authorization_is_valid(
                    prompt_context,
                    prompt_event,
                    actual_prompt,
                    authorized_scope,
                )
                if not continuation_ok:
                    failures.append(continuation_failure or "prompt_context.source_prompt_excerpt does not match latest UserPromptSubmit prompt")
            elif authorized_scope in {"implementation", "completion"} and not prompt_has_directive_authority(actual_prompt):
                failures.append("prompt_context.authorized_scope requires an actual UserPromptSubmit directive, not a question-only prompt substring")


def validate_prism_review_resolution(packet: dict[str, Any], failures: list[str]) -> None:
    transition = packet.get("fsm_transition")
    transition_target = transition.get("to") if isinstance(transition, dict) else None
    technical_review = packet.get("technical_review")
    prism_gate_decision = technical_review.get("prism_gate_decision") if isinstance(technical_review, dict) else None
    prism_review = packet.get("prism_review")

    if transition_target in PRISM_REVIEW_REQUIRED_TARGETS and prism_gate_decision == "required":
        if not isinstance(prism_review, dict):
            failures.append("technical_review.prism_gate_decision=required requires prism_review before FSM transition to IMPLEMENTING or beyond")
            return
        if not (isinstance(prism_review.get("merge_path"), str) and prism_review["merge_path"].strip()):
            failures.append("prism_review.merge_path is required when Prism gate decision is required")
            return

    explicit_merge_path: pathlib.Path | None = None
    if isinstance(prism_review, dict):
        raw_merge = prism_review.get("merge_path")
        if isinstance(raw_merge, str) and raw_merge.strip():
            explicit_merge_path = resolve_reference_path(raw_merge)
            try:
                merge_payload = load_json_object(explicit_merge_path, "prism_review.merge_path")
            except ValueError as exc:
                failures.append(str(exc))
                merge_payload = {}
            raw_resolution = prism_review.get("resolution_path")
            resolution_path: pathlib.Path | None = None
            if isinstance(raw_resolution, str) and raw_resolution.strip():
                resolution_path = resolve_reference_path(raw_resolution, explicit_merge_path.parent)
            elif explicit_merge_path.exists():
                resolution_path = resolution_sibling_for_merge(explicit_merge_path)
            raw_manifest = prism_review.get("manifest_path")
            manifest_path = resolve_reference_path(raw_manifest, explicit_merge_path.parent) if isinstance(raw_manifest, str) and raw_manifest.strip() else None
            if merge_payload.get("must_respond") is True:
                if resolution_path is None:
                    failures.append("Prism merge with must_respond=true requires prism_review.resolution_path or sibling resolution.json")
                else:
                    ok, resolution_failures, parsed = run_prism_resolution_check(explicit_merge_path, resolution_path, manifest_path)
                    if not ok:
                        failures.extend(f"prism_review resolution failed: {item}" for item in resolution_failures)
                    elif (
                        transition_target in PRISM_REVIEW_REQUIRED_TARGETS
                        and isinstance(parsed, dict)
                        and parsed.get("conclusion_state") == "escalated"
                    ):
                        failures.append("FSM transition to IMPLEMENTING or beyond cannot proceed with escalated Prism concern resolution")
            elif resolution_path is not None:
                ok, resolution_failures, _ = run_prism_resolution_check(explicit_merge_path, resolution_path, manifest_path)
                if not ok:
                    failures.extend(f"prism_review resolution failed: {item}" for item in resolution_failures)

    referenced_merge_paths: set[pathlib.Path] = set()
    for value in collect_string_values(packet):
        if not looks_like_prism_merge_path(value):
            continue
        merge_path = resolve_reference_path(value)
        if explicit_merge_path is not None and merge_path == explicit_merge_path:
            continue
        if not merge_path.exists():
            continue
        try:
            merge_payload = load_json_object(merge_path, "referenced Prism merge")
        except ValueError:
            continue
        if merge_payload.get("must_respond") is True:
            referenced_merge_paths.add(merge_path)
    for merge_path in sorted(referenced_merge_paths):
        sibling_resolution = resolution_sibling_for_merge(merge_path)
        if sibling_resolution is None:
            failures.append(f"referenced Prism merge with must_respond=true requires an executable resolution: {merge_path}")
            continue
        ok, resolution_failures, parsed = run_prism_resolution_check(merge_path, sibling_resolution)
        if not ok:
            failures.extend(f"referenced Prism merge resolution failed: {item}" for item in resolution_failures)
        elif (
            transition_target in PRISM_REVIEW_REQUIRED_TARGETS
            and isinstance(parsed, dict)
            and parsed.get("conclusion_state") == "escalated"
        ):
            failures.append(f"referenced Prism merge is escalated and cannot authorize implementation: {merge_path}")


def validate_review_tracks(packet: dict[str, Any], failures: list[str]) -> None:
    transition = packet.get("fsm_transition")
    transition_target = transition.get("to") if isinstance(transition, dict) else None
    requirement_review = packet.get("requirement_review")
    risk_level = requirement_review.get("risk_level") if isinstance(requirement_review, dict) else None
    if (
        transition_target not in PRISM_REVIEW_REQUIRED_TARGETS
        or not isinstance(risk_level, str)
        or risk_level.casefold() not in REVIEW_TRACK_REQUIRED_RISKS
    ):
        return

    review_tracks = packet.get("review_tracks")
    if not isinstance(review_tracks, dict):
        failures.append("medium-or-higher lifecycle transition requires review_tracks")
        return
    missing = sorted(REQUIRED_REVIEW_TRACK_IDS - set(review_tracks))
    if missing:
        failures.append(f"review_tracks missing: {', '.join(missing)}")
    for track_id in sorted(REQUIRED_REVIEW_TRACK_IDS):
        track = review_tracks.get(track_id)
        if not isinstance(track, dict):
            failures.append(f"review_tracks.{track_id} must be an object")
            continue
        status = track.get("status")
        if status not in REVIEW_TRACK_STATUSES:
            failures.append(f"review_tracks.{track_id}.status invalid: {status}")
            continue
        if status == "checked":
            if not non_empty_string_list(track.get("findings")):
                failures.append(f"review_tracks.{track_id}.findings must be a non-empty string list when checked")
            elif not has_substantive_text(track.get("findings")):
                failures.append(f"review_tracks.{track_id}.findings must include a substantive review finding")
            if not non_empty_string_list(track.get("evidence")):
                failures.append(f"review_tracks.{track_id}.evidence must be a non-empty string list when checked")
            elif not has_reference_like_evidence(track.get("evidence")):
                failures.append(f"review_tracks.{track_id}.evidence must include a file path or command reference")
        if status == "not_applicable":
            if not (isinstance(track.get("reason"), str) and track["reason"].strip()):
                failures.append(f"review_tracks.{track_id}.reason is required when not_applicable")
            elif not substantive_text(track["reason"]):
                failures.append(f"review_tracks.{track_id}.reason must explain why the track is not applicable")


def validate_packet(packet: dict[str, Any], events_path: pathlib.Path = DEFAULT_EVENTS) -> list[str]:
    failures: list[str] = []
    if packet.get("schema_id") != "redcap-development-lifecycle-packet":
        failures.append("schema_id must be redcap-development-lifecycle-packet")
    state = packet.get("fsm_state")
    if state not in STATES:
        failures.append(f"fsm_state invalid: {state}")
    req = packet.get("requirement_review")
    if not isinstance(req, dict):
        failures.append("requirement_review must be an object")
    else:
        missing = sorted(REQUIRED_REVIEW_FIELDS - set(req))
        if missing:
            failures.append(f"requirement_review missing: {', '.join(missing)}")
    tech = packet.get("technical_review")
    if not isinstance(tech, dict):
        failures.append("technical_review must be an object")
    else:
        missing = sorted(REQUIRED_TECH_FIELDS - set(tech))
        if missing:
            failures.append(f"technical_review missing: {', '.join(missing)}")
        if tech.get("runtime_boundary_checked") is not True:
            failures.append("technical_review.runtime_boundary_checked must be true")
    validate_prompt_context(packet, failures, events_path)
    validate_task_body(packet, failures)
    validate_prism_review_resolution(packet, failures)
    validate_review_tracks(packet, failures)
    fsm_transition = packet.get("fsm_transition")
    if isinstance(fsm_transition, dict):
        source = str(fsm_transition.get("from") or "")
        target = str(fsm_transition.get("to") or "")
        evidence = set(fsm_transition.get("evidence", []) if isinstance(fsm_transition.get("evidence"), list) else [])
        ok, transition_failures = transition_allowed(source, target, evidence)
        if not ok:
            failures.extend(f"fsm_transition: {item}" for item in transition_failures)
    completion_claim = packet.get("completion_claim")
    if isinstance(completion_claim, dict) and completion_claim.get("present"):
        implementation_evidence = packet.get("implementation_evidence")
        verification_evidence = packet.get("verification_evidence")
        if not isinstance(implementation_evidence, list) or not implementation_evidence:
            failures.append("completion_claim requires implementation_evidence")
        if not isinstance(verification_evidence, list) or not verification_evidence:
            failures.append("completion_claim requires verification_evidence")
        doc_only = completion_claim.get("evidence_kind") in PROOF_ONLY_COMPLETION_KINDS
        if doc_only:
            failures.append("documentation, ledger, receipt, report, or governance evidence cannot satisfy completion alone")
    return failures


def record_completion_marker(
    packet_path: pathlib.Path,
    packet: dict[str, Any],
    marker_path: pathlib.Path = COMPLETION_MARKER,
    events_path: pathlib.Path = DEFAULT_EVENTS,
) -> None:
    task_body = packet.get("task_body") if isinstance(packet.get("task_body"), dict) else {}
    prompt_event = latest_prompt_event(events_path)
    marker = {
        "schema_id": "redcap-development-lifecycle-completion-marker",
        "checked_at": iso_now(),
        "packet_path": str(packet_path),
        "task_id": packet.get("task_id"),
        "session_id": prompt_event.get("session_id") if isinstance(prompt_event, dict) else None,
        "turn_id": prompt_event.get("turn_id") if isinstance(prompt_event, dict) else None,
        "task_body_status": task_body.get("status"),
        "task_body_evidence_kind": task_body.get("evidence_kind"),
        "requested_outcome": task_body.get("requested_outcome"),
    }
    write_json(marker_path, marker)


def cmd_check(args: argparse.Namespace) -> int:
    packet_path = pathlib.Path(args.packet).resolve()
    packet = load_json(packet_path)
    failures = validate_packet(packet, pathlib.Path(args.events).resolve())
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    completion_claim = packet.get("completion_claim")
    if isinstance(completion_claim, dict) and completion_claim.get("present") is True:
        record_completion_marker(
            packet_path,
            packet,
            pathlib.Path(args.completion_marker).resolve(),
            pathlib.Path(args.events).resolve(),
        )
    print("REDCAP_DEVELOPMENT_LIFECYCLE_OK")
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    valid = {
        "schema_id": "redcap-development-lifecycle-packet",
        "task_id": "fixture",
        "fsm_state": "IMPLEMENTING",
        "requirement_review": {
            "user_intent": "fixture",
            "target_reality": "runtime boundary behavior changes",
            "non_goals": ["release"],
            "risk_level": "medium",
        },
        "technical_review": {
            "runtime_boundary_checked": True,
            "prism_gate_decision": "required",
            "rollback_plan": "delete fixture file",
            "verification_plan": ["self-check"],
        },
        "prism_review": {
            "merge_path": "runtime/prism/examples/prism-concern-resolution.merge.pass.json",
            "resolution_path": "runtime/prism/examples/prism-concern-resolution.valid-pass-merge.json",
        },
        "prompt_context": {
            "source_prompt_excerpt": "Implement the lifecycle validator fixture.",
            "prompt_kind": "directive",
            "authorized_scope": "implementation",
        },
        "task_body": {
            "requested_outcome": "exercise lifecycle validator",
            "primary_deliverable": "validator fixture",
            "acceptance_criteria": ["valid packet passes"],
            "status": "implemented",
            "evidence_kind": "code",
            "evidence": ["runtime/core/development_lifecycle.py"],
        },
        "review_tracks": {
            "architecture": {
                "status": "checked",
                "findings": ["FSM transition uses the existing lifecycle validator instead of a second state machine."],
                "evidence": ["runtime/core/development_lifecycle.py", "runtime/core/fsm.py"],
            },
            "governance": {
                "status": "checked",
                "findings": ["Completion remains tied to task-body evidence, not report or receipt presence."],
                "evidence": ["runtime/core/development_lifecycle.py", "runtime/prism/examples/self-development-lifecycle-packet.json"],
            },
            "contracts": {
                "status": "checked",
                "findings": ["The packet names rollback and verification plans before implementation."],
                "evidence": ["runtime/bin/redcap lifecycle self-check", "runtime/bin/redcap check"],
            },
        },
        "fsm_transition": {
            "from": "PRISM_REVIEW",
            "to": "IMPLEMENTING",
            "evidence": ["prism_review_or_explicit_skip"],
        },
        "implementation_evidence": ["runtime_change"],
        "verification_evidence": ["self-check"],
        "completion_claim": {"present": False},
    }
    invalid = dict(valid)
    invalid["completion_claim"] = {"present": True, "evidence_kind": "docs"}
    invalid["implementation_evidence"] = []
    invalid["prompt_context"] = {
        "source_prompt_excerpt": "Is this necessary?",
        "prompt_kind": "question",
        "authorized_scope": "completion",
    }
    invalid["task_body"] = {
        "requested_outcome": "fixture",
        "primary_deliverable": "governance-only fixture",
        "acceptance_criteria": ["must fail"],
        "status": "implemented",
        "evidence_kind": "governance",
        "evidence": ["assets/evidence/example.json"],
    }
    with tempfile.TemporaryDirectory(prefix="redcap-lifecycle-") as tmp_raw:
        tmp = pathlib.Path(tmp_raw)
        events_path = tmp / "events.jsonl"
        events_path.write_text(json.dumps({
            "event": "UserPromptSubmit",
            "session_id": "fixture-session",
            "prompt": {"normalized_excerpt": "Please implement the lifecycle validator fixture."},
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        if validate_packet(valid, events_path):
            failures.append("valid packet failed")
        invalid_failures = validate_packet(invalid, events_path)
        if not any("cannot satisfy completion" in item for item in invalid_failures):
            failures.append("documentation-only completion was not rejected")
        if not any("task_body.status=verified" in item for item in invalid_failures):
            failures.append("completion without verified task body was not rejected")
        if not any("allowed task-body evidence kinds" in item or "governance/proof-only" in item for item in invalid_failures):
            failures.append("completion with governance-only task body evidence was not rejected")
        mismatch = dict(valid)
        mismatch["prompt_context"] = {
            "source_prompt_excerpt": "Implement a completely different feature.",
            "prompt_kind": "directive",
            "authorized_scope": "implementation",
        }
        mismatch_failures = validate_packet(mismatch, events_path)
        if not any("does not match latest UserPromptSubmit prompt" in item for item in mismatch_failures):
            failures.append("fabricated prompt excerpt was not rejected")
        continuation = copy.deepcopy(valid)
        continuation["prompt_context"] = {
            "source_prompt_excerpt": "Continue the existing lifecycle validator goal after automatic resume.",
            "prompt_kind": "directive",
            "authorized_scope": "implementation",
            "continuation_authorization": {
                "mode": "same_session_authorized_continuation",
                "source": "codex_goal",
                "session_id": "fixture-session",
                "base_prompt_excerpt": "Please implement the lifecycle validator fixture.",
            },
        }
        continuation_failures = validate_packet(continuation, events_path)
        if continuation_failures:
            failures.append(f"same-session continuation should pass lifecycle prompt verification: {'; '.join(continuation_failures)}")
        cross_session = copy.deepcopy(continuation)
        cross_session["prompt_context"]["continuation_authorization"]["session_id"] = "other-session"
        cross_session_failures = validate_packet(cross_session, events_path)
        if not any("session_id does not match" in item for item in cross_session_failures):
            failures.append("cross-session continuation was not rejected")
        missing_event_failures = validate_packet(valid, tmp / "missing-events.jsonl")
        if not any("no UserPromptSubmit event" in item for item in missing_event_failures):
            failures.append("missing UserPromptSubmit event did not fail prompt-context verification")
        question_events_path = tmp / "question-events.jsonl"
        question_events_path.write_text(json.dumps({
            "event": "UserPromptSubmit",
            "prompt": {"normalized_excerpt": "Should we implement the lifecycle validator fixture?"},
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        question_substring = dict(valid)
        question_substring["prompt_context"] = {
            "source_prompt_excerpt": "implement the lifecycle validator fixture",
            "prompt_kind": "directive",
            "authorized_scope": "implementation",
        }
        question_failures = validate_packet(question_substring, question_events_path)
        if not any("question-only prompt substring" in item for item in question_failures):
            failures.append("question prompt substring authorizing implementation was not rejected")
        short_events_path = tmp / "short-events.jsonl"
        short_events_path.write_text(json.dumps({
            "event": "UserPromptSubmit",
            "prompt": {"normalized_excerpt": "可以，请处理这些风险点"},
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        short_prompt = dict(valid)
        short_prompt["prompt_context"] = {
            "source_prompt_excerpt": "可以，请处理这些风险点",
            "prompt_kind": "directive",
            "authorized_scope": "implementation",
        }
        short_failures = validate_packet(short_prompt, short_events_path)
        if short_failures:
            failures.append(f"short directive prompt should pass lifecycle prompt verification: {'; '.join(short_failures)}")
        bypass = dict(valid)
        bypass["prompt_context"] = {
            "source_prompt_excerpt": "Please implement the lifecycle validator fixture.",
            "prompt_kind": "question",
            "authorized_scope": "review_only",
        }
        bypass["task_body"] = {
            "requested_outcome": "governance packet only",
            "primary_deliverable": "report",
            "acceptance_criteria": ["report exists"],
            "status": "planned",
            "evidence_kind": "governance",
            "evidence": ["assets/evidence/report.json"],
        }
        bypass["fsm_transition"] = {
            "from": "PRISM_REVIEW",
            "to": "IMPLEMENTING",
            "evidence": ["prism_review_or_explicit_skip"],
        }
        bypass_failures = validate_packet(bypass, events_path)
        if not any("task_body.status implemented or verified" in item for item in bypass_failures):
            failures.append("present=false governance packet could still advance to IMPLEMENTING")
        if not any("authorized_scope implementation or completion" in item for item in bypass_failures):
            failures.append("review-only prompt could still advance to IMPLEMENTING")
        missing_prism_review = dict(valid)
        missing_prism_review.pop("prism_review", None)
        missing_prism_failures = validate_packet(missing_prism_review, events_path)
        if not any("prism_review" in item and "required" in item for item in missing_prism_failures):
            failures.append("required Prism gate could advance without prism_review")
        unresolved_prism_review = dict(valid)
        unresolved_prism_review["prism_review"] = {
            "merge_path": "runtime/prism/examples/prism-concern-resolution.merge.concern.json",
        }
        unresolved_prism_failures = validate_packet(unresolved_prism_review, events_path)
        if not any("must_respond=true" in item for item in unresolved_prism_failures):
            failures.append("Prism merge with must_respond=true could advance without resolution")
        escalated_prism_review = dict(valid)
        escalated_prism_review["prism_review"] = {
            "merge_path": "runtime/prism/examples/prism-concern-resolution.merge.concern.json",
            "resolution_path": "runtime/prism/examples/prism-concern-resolution.valid-escalate.json",
        }
        escalated_prism_failures = validate_packet(escalated_prism_review, events_path)
        if not any("cannot proceed with escalated Prism concern resolution" in item for item in escalated_prism_failures):
            failures.append("escalated Prism concern could still authorize implementation")
        missing_tracks = copy.deepcopy(valid)
        missing_tracks.pop("review_tracks", None)
        missing_track_failures = validate_packet(missing_tracks, events_path)
        if not any("requires review_tracks" in item for item in missing_track_failures):
            failures.append("medium-risk implementation transition could advance without review_tracks")
        missing_governance = copy.deepcopy(valid)
        missing_governance["review_tracks"].pop("governance", None)
        governance_track_failures = validate_packet(missing_governance, events_path)
        if not any("review_tracks missing" in item and "governance" in item for item in governance_track_failures):
            failures.append("missing governance review track was not rejected")
        no_evidence_track = copy.deepcopy(valid)
        no_evidence_track["review_tracks"]["contracts"]["evidence"] = []
        no_evidence_failures = validate_packet(no_evidence_track, events_path)
        if not any("review_tracks.contracts.evidence" in item for item in no_evidence_failures):
            failures.append("checked review track without evidence was not rejected")
        no_reason_track = copy.deepcopy(valid)
        no_reason_track["review_tracks"]["architecture"] = {"status": "not_applicable"}
        no_reason_failures = validate_packet(no_reason_track, events_path)
        if not any("review_tracks.architecture.reason" in item for item in no_reason_failures):
            failures.append("not_applicable review track without reason was not rejected")
        weak_finding_track = copy.deepcopy(valid)
        weak_finding_track["review_tracks"]["governance"]["findings"] = ["done"]
        weak_finding_failures = validate_packet(weak_finding_track, events_path)
        if not any("review_tracks.governance.findings" in item and "substantive" in item for item in weak_finding_failures):
            failures.append("generic review-track finding was not rejected")
        weak_evidence_track = copy.deepcopy(valid)
        weak_evidence_track["review_tracks"]["contracts"]["evidence"] = ["done"]
        weak_evidence_failures = validate_packet(weak_evidence_track, events_path)
        if not any("review_tracks.contracts.evidence" in item and "file path or command" in item for item in weak_evidence_failures):
            failures.append("generic review-track evidence was not rejected")
        governance_implementation = dict(valid)
        governance_implementation["task_body"] = {
            "requested_outcome": "governance packet only",
            "primary_deliverable": "report",
            "acceptance_criteria": ["must fail"],
            "status": "implemented",
            "evidence_kind": "configuration",
            "evidence": ["assets/evidence/report.json"],
        }
        governance_failures = validate_packet(governance_implementation, events_path)
        if not any("allowed task-body evidence kinds" in item or "allowed evidence kinds" in item for item in governance_failures):
            failures.append("present=false implemented non-whitelisted evidence could still advance to IMPLEMENTING")
        packet_path = tmp / "valid.json"
        packet_path.write_text(json.dumps(valid, ensure_ascii=False), encoding="utf-8")
        if load_json(packet_path).get("task_id") != "fixture":
            failures.append("packet fixture read failed")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_DEVELOPMENT_LIFECYCLE_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap development lifecycle evidence gate")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check")
    check.add_argument("--packet", required=True)
    check.add_argument("--events", default=str(DEFAULT_EVENTS))
    check.add_argument("--completion-marker", default=str(COMPLETION_MARKER))
    check.set_defaults(func=cmd_check)

    self_check = sub.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
import sys
from pathlib import Path
from typing import Any


def section(text: str, heading_prefix: str) -> str:
    capture = False
    buffer: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            if capture:
                break
            if heading.startswith(heading_prefix):
                capture = True
                continue
        if capture:
            buffer.append(line)
    return "\n".join(buffer).strip()


def metadata(text: str) -> dict[str, str]:
    meta = section(text, "控制面元数据") or section(text, "Canonical Metadata")
    result: dict[str, str] = {}
    for line in meta.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def normalize_policy(meta: dict[str, str]) -> str:
    policy = meta.get("acceptance_policy", "").strip().lower().replace("_", "-")
    if policy:
        return policy
    if meta.get("governance_tranche", "").strip().lower() == "true":
        return "prism-required"
    return "not-required"


def confirmed_hash(task_text: str) -> str:
    confirmed = section(task_text, "已确认需求")
    if not confirmed:
        return ""
    import hashlib
    return hashlib.sha256(confirmed.encode("utf-8")).hexdigest()


def parse_registry(path: Path) -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\s*-\s+handle_type:\s*", raw):
            if current:
                agents.append(current)
            value = raw.split(":", 1)[1].strip().strip('"')
            current = {"handle_type": value}
            continue
        if current is None:
            continue
        match = re.match(r"^\s+([A-Za-z0-9_.-]+):\s*(.*?)\s*$", raw)
        if not match:
            continue
        key = match.group(1)
        value = match.group(2).strip().strip('"')
        if value in {"true", "false"}:
            current[key] = value == "true"
        else:
            current[key] = value
    if current:
        agents.append(current)
    return agents


def blockers_empty(payload: dict[str, Any]) -> bool:
    blockers = payload.get("blockers")
    if blockers is None:
        return True
    if isinstance(blockers, str):
        blockers = [blockers]
    if not isinstance(blockers, list):
        return False
    cleaned = [str(item).strip() for item in blockers if str(item).strip()]
    if not cleaned:
        return True
    return all(
        re.fullmatch(r"(无\s*blocker|none|null|无)", item, flags=re.IGNORECASE)
        for item in cleaned
    )


def build_result(*, status: str, policy: str, detail: str, run_id: str = "", responded: int = 0, families: int = 0, blockers: int = 0, roles: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "policy": policy,
        "detail": detail,
        "run_id": run_id,
        "responded": responded,
        "family_count": families,
        "blocker_roles": blockers,
        "roles": roles or [],
    }


def validate_binding(binding_path: Path, *, task_id: str, confirmed: str, run_id: str) -> tuple[bool, str, dict[str, Any]]:
    if not binding_path.is_file():
        return False, f"prism acceptance binding missing: {binding_path}", {}
    try:
        payload = json.loads(binding_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"invalid prism acceptance binding: {exc}", {}

    bound_task_id = str(payload.get("task_id", "")).strip()
    bound_confirmed = str(payload.get("confirmed_hash", "")).strip()
    bound_run_id = str(payload.get("run_id", "")).strip()
    if bound_run_id and bound_run_id != run_id:
        return False, f"prism acceptance binding run mismatch: expected {run_id}, got {bound_run_id}", payload
    if bound_task_id != task_id:
        return False, f"prism acceptance binding task mismatch: expected {task_id}, got {bound_task_id or 'missing'}", payload
    if bound_confirmed != confirmed:
        return False, f"prism acceptance binding confirmed_hash mismatch: expected {confirmed}, got {bound_confirmed or 'missing'}", payload
    return True, "binding ok", payload


def parsed_payload_for_agent(repo_root: Path, run_id: str, agent: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    role = str(agent.get("role", "")).strip()
    parsed = repo_root / "prism/runs" / run_id / "collect" / role / "parsed.json"
    if not parsed.is_file():
        return None, f"parsed reviewer payload missing: {parsed}"
    try:
        payload = json.loads(parsed.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"invalid parsed reviewer payload for {role}: {exc}"
    if not isinstance(payload, dict):
        return None, f"parsed reviewer payload is not an object: {parsed}"
    return payload, ""


def blocker_roles_for_agents(repo_root: Path, run_id: str, agents: list[dict[str, Any]]) -> tuple[list[str], str]:
    blocker_roles: list[str] = []
    for agent in agents:
        role = str(agent.get("role", "")).strip()
        payload, error = parsed_payload_for_agent(repo_root, run_id, agent)
        if error:
            return [], error
        if payload is not None and not blockers_empty(payload):
            blocker_roles.append(role)
    return blocker_roles, ""


def resource_limited_ok(repo_root: Path, run_id: str, binding: dict[str, Any], responded_agents: list[dict[str, Any]]) -> tuple[bool, str, int]:
    if binding.get("resource_limited") is not True:
        return False, "resource-limited Prism is not declared in acceptance binding", 0
    if len(responded_agents) < 1:
        return False, "resource-limited Prism requires at least one responded/schema_ok reviewer", 0

    evidence_path = repo_root / "prism/runs" / run_id / "artifacts" / "resource-limited.json"
    if not evidence_path.is_file():
        return False, f"resource-limited evidence missing: {evidence_path}", 0
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"invalid resource-limited evidence: {exc}", 0
    if not isinstance(evidence, dict) or evidence.get("status") != "resource-limited":
        return False, "resource-limited evidence must declare status=resource-limited", 0

    allowed_statuses = {
        "timeout",
        "cli-timeout",
        "api-timeout",
        "unavailable",
        "auth-failure",
        "dependency-missing",
        "invalid-install",
        "frozen",
        "policy-frozen",
        "policy-unavailable",
    }
    attempts = evidence.get("provider_attempts", [])
    if not isinstance(attempts, list):
        return False, "resource-limited evidence provider_attempts must be a list", 0
    unavailable_families: set[str] = set()
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        status = str(attempt.get("status", "")).strip()
        family = str(attempt.get("family", "")).strip()
        provider = str(attempt.get("provider", "")).strip()
        if not provider or not family or status not in allowed_statuses:
            continue
        unavailable_families.add(family)
    if not unavailable_families:
        return False, "resource-limited Prism requires unavailable/frozen evidence for at least one additional family", 0

    blocker_roles, blocker_error = blocker_roles_for_agents(repo_root, run_id, responded_agents)
    if blocker_error:
        return False, blocker_error, len(unavailable_families)
    if blocker_roles:
        return False, "resource-limited Prism reviewer still reports blockers", len(unavailable_families)
    return True, "resource-limited Prism evidence is present and blocker-free", len(unavailable_families)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Prism acceptance evidence for the current Layer B task.")
    parser.add_argument("--task-file", default=".dev-task.md")
    args = parser.parse_args()

    task_file = Path(args.task_file).resolve()
    if not task_file.is_file():
        print(json.dumps(build_result(status="fail", policy="unknown", detail=f"task file missing: {task_file}"), ensure_ascii=False, indent=2))
        return 1

    task_text = task_file.read_text(encoding="utf-8")
    meta = metadata(task_text)
    task_id = meta.get("task_id", "").strip()
    confirmed = confirmed_hash(task_text)
    policy = normalize_policy(meta)
    if policy in {"none", "not-required", "disabled"}:
        print(json.dumps(build_result(status="not-required", policy=policy, detail="task does not require Prism acceptance"), ensure_ascii=False, indent=2))
        return 0

    run_id = meta.get("prism_acceptance_run", "").strip()
    if not run_id or run_id in {"pending", "none", "missing"}:
        print(json.dumps(build_result(status="fail", policy=policy, detail="prism acceptance run is not declared in .dev-task.md"), ensure_ascii=False, indent=2))
        return 1

    repo_root = task_file.parent
    registry = repo_root / "prism/runs" / run_id / "session-registry.yaml"
    binding_path = repo_root / "prism/runs" / run_id / "artifacts" / "acceptance-binding.json"
    if not registry.is_file():
        print(json.dumps(build_result(status="fail", policy=policy, detail=f"prism acceptance registry missing: {registry}", run_id=run_id), ensure_ascii=False, indent=2))
        return 1
    if not task_id or not confirmed:
        print(json.dumps(build_result(status="fail", policy=policy, detail="task_id or confirmed_hash missing from .dev-task.md", run_id=run_id), ensure_ascii=False, indent=2))
        return 1
    binding_ok, binding_detail, binding_payload = validate_binding(binding_path, task_id=task_id, confirmed=confirmed, run_id=run_id)
    if not binding_ok:
        print(json.dumps(build_result(status="fail", policy=policy, detail=binding_detail, run_id=run_id), ensure_ascii=False, indent=2))
        return 1

    try:
        agents = parse_registry(registry)
    except Exception as exc:
        print(json.dumps(build_result(status="fail", policy=policy, detail=f"unable to parse prism registry: {exc}", run_id=run_id), ensure_ascii=False, indent=2))
        return 1

    responded_agents = [
        agent
        for agent in agents
        if agent.get("status") in {"responded", "followed_up"} and agent.get("schema_ok") is True
    ]
    if len(responded_agents) < 2:
        ok, detail, unavailable_families = resource_limited_ok(repo_root, run_id, binding_payload, responded_agents)
        if ok:
            print(json.dumps(build_result(status="resource-limited-pass", policy=policy, detail=detail, run_id=run_id, responded=len(responded_agents), families=1 + unavailable_families, blockers=0, roles=[str(agent.get("role", "")).strip() for agent in responded_agents]), ensure_ascii=False, indent=2))
            return 0
        print(json.dumps(build_result(status="fail", policy=policy, detail="Prism acceptance requires at least 2 responded/schema_ok agents", run_id=run_id, responded=len(responded_agents)), ensure_ascii=False, indent=2))
        return 1

    families = {str(agent.get("family", "")).strip() for agent in responded_agents if str(agent.get("family", "")).strip()}
    if len(families) < 2:
        ok, detail, unavailable_families = resource_limited_ok(repo_root, run_id, binding_payload, responded_agents)
        if ok:
            print(json.dumps(build_result(status="resource-limited-pass", policy=policy, detail=detail, run_id=run_id, responded=len(responded_agents), families=len(families) + unavailable_families, blockers=0, roles=[str(agent.get("role", "")).strip() for agent in responded_agents]), ensure_ascii=False, indent=2))
            return 0
        print(json.dumps(build_result(status="fail", policy=policy, detail="Prism acceptance requires at least 2 distinct model families", run_id=run_id, responded=len(responded_agents), families=len(families)), ensure_ascii=False, indent=2))
        return 1

    blocker_roles, blocker_error = blocker_roles_for_agents(repo_root, run_id, responded_agents)
    if blocker_error:
        print(json.dumps(build_result(status="fail", policy=policy, detail=blocker_error, run_id=run_id, responded=len(responded_agents), families=len(families)), ensure_ascii=False, indent=2))
        return 1

    if blocker_roles:
        print(json.dumps(build_result(status="fail", policy=policy, detail="Prism acceptance reviewers still report blockers", run_id=run_id, responded=len(responded_agents), families=len(families), blockers=len(blocker_roles), roles=blocker_roles), ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(build_result(status="pass", policy=policy, detail="Prism acceptance evidence is present and blocker-free", run_id=run_id, responded=len(responded_agents), families=len(families), blockers=0, roles=[str(agent.get("role", "")).strip() for agent in responded_agents]), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

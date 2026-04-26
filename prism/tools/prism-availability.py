#!/usr/bin/env python3
"""Maintain the Prism agent availability cache.

The cache is intentionally separate from the lighter agent registry: Prism must
know whether a CLI is truly usable in headless mode before a roster is launched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_CACHE = "compass/.workflow/prism-agent-availability.json"
DEFAULT_TTL_SECONDS = 3600
DEFAULT_TIMEOUT_SECONDS = 15
AVAILABLE_STATUS = "pass"
PROVENANCE_CONTRACT = "prism-availability-provenance-v1"
PROVIDER_ALIASES = {
    "claude": "claude-code",
    "claude-code": "claude-code",
    "copilot": "copilot",
    "codex": "codex",
    "gemini": "gemini",
    "kimi": "kimi",
}


def fail(message: str) -> None:
    raise SystemExit(f"[prism-availability] {message}")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_path(root: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return root / path


def stable_path(path: Path) -> str:
    try:
        return str(path.expanduser().resolve(strict=False))
    except OSError:
        return str(path.expanduser().absolute())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        if not path.is_file():
            return ""
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def build_cache_provenance(root: Path, cache_path: Path, health_probe: Path, provider_policy_path: Path) -> dict[str, str]:
    """Capture the runtime facts that make an availability cache trustworthy."""
    return {
        "contract": PROVENANCE_CONTRACT,
        "root": stable_path(root),
        "cache_path": stable_path(cache_path),
        "health_probe": stable_path(health_probe),
        "health_probe_sha256": sha256_file(health_probe),
        "provider_policy": stable_path(provider_policy_path),
        "provider_policy_sha256": sha256_file(provider_policy_path),
        "path_sha256": sha256_text(os.environ.get("PATH", "")),
    }


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def provenance_matches(cache: dict[str, Any], expected: dict[str, str]) -> bool:
    provenance = cache.get("provenance")
    if not isinstance(provenance, dict):
        return False
    for key, expected_value in expected.items():
        if provenance.get(key) != expected_value:
            return False
    return True


def cache_is_fresh(cache: dict[str, Any], now: datetime, min_timeout_s: int, expected_provenance: dict[str, str]) -> bool:
    if cache.get("version") != 1:
        return False
    if not provenance_matches(cache, expected_provenance):
        return False
    expires_at = parse_time(cache.get("expires_at"))
    if expires_at is None or now >= expires_at:
        return False
    agents = cache.get("agents")
    try:
        cached_timeout = int(cache.get("timeout_s", 0))
    except (TypeError, ValueError):
        cached_timeout = 0
    if cached_timeout < min_timeout_s:
        return False
    return isinstance(agents, dict) and bool(agents)


def normalize_agent_name(name: str) -> str:
    return PROVIDER_ALIASES.get(name.strip().lower(), name.strip().lower())


def normalize_health_payload(payload: dict[str, Any], ttl_seconds: int, source: str, provenance: dict[str, str]) -> dict[str, Any]:
    now = utc_now()
    expires = now + timedelta(seconds=ttl_seconds)
    agents: dict[str, dict[str, Any]] = {}

    for row in payload.get("agents", []) or []:
        if not isinstance(row, dict):
            continue
        raw_agent = row.get("agent")
        if not isinstance(raw_agent, str) or not raw_agent.strip():
            continue
        agent = normalize_agent_name(raw_agent)
        status = str(row.get("live_status") or "unknown")
        reason = str(row.get("reason") or "")
        normalized = {
            "agent": agent,
            "source_agent": raw_agent,
            "available": status == AVAILABLE_STATUS,
            "status": status,
            "installed": bool(row.get("installed")),
            "path": str(row.get("path") or ""),
            "reason": reason,
        }
        if row.get("frozen_until"):
            normalized["frozen_until"] = row.get("frozen_until")
        if row.get("timeout_s"):
            normalized["timeout_s"] = row.get("timeout_s")
        agents[agent] = normalized
        if agent == "claude-code":
            agents["claude"] = {**normalized, "agent": "claude", "canonical_agent": "claude-code"}

    return {
        "version": 1,
        "generated_at": iso(now),
        "expires_at": iso(expires),
        "ttl_seconds": ttl_seconds,
        "timeout_s": payload.get("timeout_s", ""),
        "source": source,
        "provenance": provenance,
        "source_health_detected_at": payload.get("detected_at", ""),
        "agents": agents,
    }


def run_health_probe(root: Path, health_probe: Path, timeout_s: int, provider_policy: str, provenance: dict[str, str]) -> dict[str, Any]:
    if not health_probe.is_file():
        fail(f"missing health probe script: {health_probe}")
    command = [
        "bash",
        str(health_probe),
        "--stdout",
        "--live",
        "--timeout",
        str(timeout_s),
        "--provider-policy",
        provider_policy,
    ]
    completed = subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        fail(f"health probe failed status={completed.returncode}: {(completed.stderr or completed.stdout).strip()[:800]}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        fail(f"health probe returned invalid json: {exc}")
    if not isinstance(payload, dict):
        fail("health probe returned non-object json")
    return normalize_health_payload(
        payload,
        ttl_seconds=int(os.environ.get("PRISM_AVAILABILITY_TTL_SECONDS", DEFAULT_TTL_SECONDS)),
        source=" ".join(command),
        provenance=provenance,
    )


def ensure_cache(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    cache_path = resolve_path(root, args.cache)
    health_probe = resolve_path(root, args.health_probe)
    provider_policy_path = resolve_path(root, args.provider_policy)
    expected_provenance = build_cache_provenance(root, cache_path, health_probe, provider_policy_path)
    now = utc_now()
    existing = load_json(cache_path)
    if not args.refresh and existing is not None and cache_is_fresh(existing, now, args.timeout, expected_provenance):
        if args.verbose:
            print(f"PRISM_AVAILABILITY_CACHE_OK {cache_path}")
        return existing

    payload = run_health_probe(root, health_probe, args.timeout, args.provider_policy, expected_provenance)
    payload["ttl_seconds"] = args.ttl_seconds
    generated = parse_time(payload.get("generated_at")) or now
    payload["expires_at"] = iso(generated + timedelta(seconds=args.ttl_seconds))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.verbose:
        print(f"PRISM_AVAILABILITY_REFRESHED {cache_path}")
    return payload


def extract_provider(model: str) -> str:
    text = model.strip().lower()
    for separator in ("&", "@"):
        if separator in text:
            provider, _, _ = text.partition(separator)
            return normalize_agent_name(provider)
    for prefix in ("claude-code", "claude", "copilot", "codex", "gemini", "kimi"):
        if text.startswith(prefix):
            return normalize_agent_name(prefix)
    return ""


def parse_roster(raw: str) -> list[dict[str, str]]:
    roster = []
    for spec in raw.split(","):
        spec = spec.strip()
        if not spec:
            continue
        if ":" in spec:
            model, role = spec.split(":", 1)
        else:
            model, role = spec, "unknown"
        roster.append({"spec": spec, "model": model.strip(), "role": role.strip(), "provider": extract_provider(model)})
    return roster


def roster_status(cache: dict[str, Any], roster_raw: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    agents = cache.get("agents")
    if not isinstance(agents, dict):
        fail("availability cache has no agents map")
    available: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in parse_roster(roster_raw):
        provider = item["provider"]
        if not provider:
            rejected.append({**item, "status": "provider-unqualified", "reason": "agent spec must be provider-qualified, e.g. kimi&model:role"})
            continue
        row = agents.get(provider)
        if not isinstance(row, dict):
            rejected.append({**item, "status": "missing-from-cache", "reason": "provider absent from availability cache"})
            continue
        merged = {**item, **row}
        if row.get("available") is True:
            available.append(merged)
        else:
            rejected.append(merged)
    return available, rejected


def command_status(args: argparse.Namespace) -> int:
    cache = ensure_cache(args)
    print(json.dumps(cache, ensure_ascii=False, indent=2))
    return 0


def command_check_roster(args: argparse.Namespace) -> int:
    cache = ensure_cache(args)
    available, rejected = roster_status(cache, args.agents)
    if rejected:
        for item in rejected:
            print(
                "PRISM_AGENT_UNAVAILABLE "
                f"spec={item.get('spec')} provider={item.get('provider') or '-'} "
                f"status={item.get('status')} reason={item.get('reason', '')}",
                file=sys.stderr,
            )
        return 1
    print(f"PRISM_AVAILABILITY_ROSTER_OK agents={len(available)}")
    return 0


def command_filter_roster(args: argparse.Namespace) -> int:
    cache = ensure_cache(args)
    available, rejected = roster_status(cache, args.agents)
    if args.report_rejected:
        for item in rejected:
            print(
                f"# rejected spec={item.get('spec')} provider={item.get('provider') or '-'} status={item.get('status')} reason={item.get('reason', '')}",
                file=sys.stderr,
            )
    print(",".join(str(item["spec"]) for item in available))
    return 0 if available else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("command", choices=["ensure", "status", "check-roster", "filter-roster"])
    parser.add_argument("--cache", default=os.environ.get("PRISM_AVAILABILITY_CACHE", DEFAULT_CACHE))
    parser.add_argument("--ttl-seconds", type=int, default=int(os.environ.get("PRISM_AVAILABILITY_TTL_SECONDS", DEFAULT_TTL_SECONDS)))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("PRISM_AVAILABILITY_PROBE_TIMEOUT", DEFAULT_TIMEOUT_SECONDS)))
    parser.add_argument("--health-probe", default=os.environ.get("PRISM_AGENT_HEALTH_PROBE_SCRIPT", "compass/tools/redcap-agent-health-probe.sh"))
    parser.add_argument("--provider-policy", default=os.environ.get("REDCAP_PROVIDER_POLICY_FILE", "references/prism-provider-policy.json"))
    parser.add_argument("--agents", default="")
    parser.add_argument("--report-rejected", action="store_true")
    parser.add_argument("--refresh", action="store_true", default=os.environ.get("PRISM_AVAILABILITY_REFRESH", "").lower() in {"1", "true", "yes"})
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.ttl_seconds <= 0:
        fail("--ttl-seconds must be positive")
    if args.timeout <= 0:
        fail("--timeout must be positive")

    if args.command == "ensure":
        ensure_cache(args)
        return 0
    if args.command == "status":
        return command_status(args)
    if args.command == "check-roster":
        if not args.agents.strip():
            fail("check-roster requires --agents")
        return command_check_roster(args)
    if args.command == "filter-roster":
        if not args.agents.strip():
            fail("filter-roster requires --agents")
        return command_filter_roster(args)
    fail(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())

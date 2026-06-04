#!/usr/bin/env python3
"""Minimal RedCap session ownership kernel."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "runtime" / "prism" / "lib"))
from prism_lock import write_json_atomic  # noqa: E402


ALLOWED_INTENTS = {"execution", "review", "closeout", "rescue"}


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def project_hash() -> str:
    return hashlib.md5(str(REPO_ROOT.resolve()).encode("utf-8")).hexdigest()


def ownership_root() -> pathlib.Path:
    base = os.environ.get("REDCAP_RUNTIME_BASE_DIR") or os.path.join(os.environ.get("TMPDIR", "/tmp"), "redcap-runtime")
    return pathlib.Path(base) / "project" / project_hash() / "session-ownership"


def ownership_file(host: str, session_id: str) -> pathlib.Path:
    return ownership_root() / f"{host}-{digest(session_id)}.json"


def payload_for(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "schema_id": "redcap-session-ownership",
        "version": 1,
        "host": args.host,
        "session_id_sha256": digest(args.session_id),
        "owner_state": "claimed",
        "intent": args.intent,
        "task_id": args.task_id,
        "task_hash": args.task_hash or "",
        "reason": args.reason or "",
        "updated_at": iso_now(),
        "workspace": str(REPO_ROOT),
    }


def load_claim(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def claim_matches(payload: dict[str, Any] | None, args: argparse.Namespace) -> tuple[str, str]:
    if not args.session_id:
        return "advisory-only", "missing-session-id"
    if payload is None:
        return "advisory-only", "unclaimed"
    if not payload:
        return "advisory-only", "invalid-claim"
    if payload.get("schema_id") != "redcap-session-ownership":
        return "advisory-only", "invalid-schema"
    if payload.get("owner_state") != "claimed":
        return "advisory-only", "not-claimed"
    if payload.get("host") != args.host:
        return "advisory-only", "host-mismatch"
    if payload.get("session_id_sha256") != digest(args.session_id):
        return "advisory-only", "session-mismatch"
    if payload.get("intent") not in ALLOWED_INTENTS:
        return "advisory-only", "intent-invalid"
    if args.task_id and payload.get("task_id") != args.task_id:
        return "advisory-only", "task-mismatch"
    if args.task_hash and payload.get("task_hash") not in {"", args.task_hash}:
        return "advisory-only", "task-hash-mismatch"
    return "owned", "matched"


def cmd_claim(args: argparse.Namespace) -> int:
    if not args.session_id:
        print("SESSION_OWNERSHIP_OK state=advisory-only reason=missing-session-id")
        return 0
    path = ownership_file(args.host, args.session_id)
    write_json_atomic(path, payload_for(args))
    print(f"SESSION_OWNERSHIP_OK state=claimed file={path}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    payload = load_claim(ownership_file(args.host, args.session_id)) if args.session_id else None
    state, reason = claim_matches(payload, args)
    result = {
        "ok": True,
        "state": state,
        "reason": reason,
        "host": args.host,
        "task_id": args.task_id,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"SESSION_OWNERSHIP_OK state={state} reason={reason}")
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    session_id = "fixture-session"
    task_id = "fixture-task"
    claim_args = argparse.Namespace(
        host="codex",
        session_id=session_id,
        task_id=task_id,
        task_hash="fixture-hash",
        intent="execution",
        reason="self-check",
    )
    cmd_claim(claim_args)
    owned_args = argparse.Namespace(host="codex", session_id=session_id, task_id=task_id, task_hash="fixture-hash")
    wrong_args = argparse.Namespace(host="codex", session_id=session_id, task_id="other-task", task_hash="")
    owned_state, owned_reason = claim_matches(load_claim(ownership_file("codex", session_id)), owned_args)
    wrong_state, wrong_reason = claim_matches(load_claim(ownership_file("codex", session_id)), wrong_args)
    failures: list[str] = []
    if owned_state != "owned":
        failures.append(f"owned probe failed: {owned_state}/{owned_reason}")
    if wrong_state != "advisory-only" or wrong_reason != "task-mismatch":
        failures.append(f"task mismatch probe failed: {wrong_state}/{wrong_reason}")
    result = {
        "ok": not failures,
        "owned_probe": owned_state,
        "mismatch_probe": wrong_state,
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_SESSION_OWNERSHIP_OK")
    return 0


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default="codex")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--task-hash", default="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap session ownership")
    subparsers = parser.add_subparsers(dest="command", required=True)

    claim = subparsers.add_parser("claim")
    add_common(claim)
    claim.add_argument("--intent", default="execution", choices=sorted(ALLOWED_INTENTS))
    claim.add_argument("--reason", default="")
    claim.set_defaults(func=cmd_claim)

    check = subparsers.add_parser("check")
    add_common(check)
    check.set_defaults(func=cmd_check)

    self_check = subparsers.add_parser("self-check")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

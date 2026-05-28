#!/usr/bin/env python3
# 用途：运行时与收尾脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#runtime-and-closeout

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REDCAP_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REDCAP_ROOT / "references" / "user-agent-identity-policy.json"


def fail(message: str, code: int = 1) -> None:
    print(f"[redcap-user-agent-identity] {message}", file=sys.stderr)
    raise SystemExit(code)


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing policy: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid policy json: {exc}")
    if not isinstance(payload, dict):
        fail("policy must be a json object")
    return payload


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def expand_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return REDCAP_ROOT / path


def safe_namespace(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip(".-_")
    return cleaned[:64] or "user"


def infer_agent_name(identity_file: Path, default: str) -> str:
    if not identity_file.is_file():
        return default
    text = identity_file.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^\s*#\s*我是\s+([^\n#]+?)\s*$", text, flags=re.MULTILINE)
    if match:
        name = re.split(r"\s+[-—–]\s+", match.group(1).strip(), maxsplit=1)[0].strip()
        if name:
            return name[:64]
    return default


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("version") != 1:
        fail("policy version must be 1")
    required = [
        "identity_file",
        "local_state_path",
        "default_user_namespace",
        "default_agent_name",
        "shared_knowledge_template_root",
        "shared_knowledge_preferred_worktree",
        "shared_knowledge_user_path",
        "private_identity_rule",
        "first_start_rule",
        "state_fields",
    ]
    for key in required:
        if key not in policy:
            fail(f"policy missing key: {key}")
    user = safe_namespace(str(policy["default_user_namespace"]))
    expected_user_path = f"users/{user}"
    if policy.get("shared_knowledge_user_path") != expected_user_path:
        fail(f"shared_knowledge_user_path must be {expected_user_path}")


def ensure_user_namespace(root: Path, user: str) -> Path:
    path = root / "users" / user
    path.mkdir(parents=True, exist_ok=True)
    placeholder = path / ".gitkeep"
    if not placeholder.exists():
        placeholder.write_text("", encoding="utf-8")
    return path


def build_state(policy: dict[str, Any], host: str) -> dict[str, Any]:
    identity_file = expand_path(str(policy["identity_file"]))
    user = safe_namespace(str(policy["default_user_namespace"]))
    agent_name = infer_agent_name(identity_file, str(policy["default_agent_name"]))
    template_root = expand_path(str(policy["shared_knowledge_template_root"]))
    preferred_root = expand_path(str(policy["shared_knowledge_preferred_worktree"]))
    template_user_path = template_root / "users" / user
    preferred_user_path = preferred_root / "users" / user

    return {
        "version": 1,
        "generated_at_utc": utc_now(),
        "host": host or "unknown",
        "identity_file": str(identity_file),
        "identity_present": identity_file.is_file(),
        "agent_name": agent_name,
        "user_namespace": user,
        "shared_knowledge_template_user_path": str(template_user_path),
        "shared_knowledge_preferred_worktree_user_path": str(preferred_user_path),
        "preferred_worktree_present": preferred_root.exists(),
        "private_identity_committed": False,
    }


def state_path(policy: dict[str, Any]) -> Path:
    return expand_path(str(policy["local_state_path"]))


def write_state(policy: dict[str, Any], state: dict[str, Any]) -> None:
    path = state_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def command_init(args: argparse.Namespace) -> int:
    policy = read_json(POLICY_PATH)
    validate_policy(policy)
    user = safe_namespace(str(policy["default_user_namespace"]))
    template_root = expand_path(str(policy["shared_knowledge_template_root"]))
    preferred_root = expand_path(str(policy["shared_knowledge_preferred_worktree"]))

    template_user_path = ensure_user_namespace(template_root, user)
    preferred_status = "absent"
    if preferred_root.exists():
        ensure_user_namespace(preferred_root, user)
        preferred_status = "present"

    state = build_state(policy, args.host)
    write_state(policy, state)
    print(f"USER_AGENT_IDENTITY_INIT_OK user={user} agent={state['agent_name']} template={template_user_path} preferred={preferred_status}")
    if not state["identity_present"]:
        print(f"[redcap-user-agent-identity] identity file missing: {state['identity_file']}", file=sys.stderr)
        return 1
    return 0


def command_check(args: argparse.Namespace) -> int:
    policy = read_json(POLICY_PATH)
    validate_policy(policy)
    user = safe_namespace(str(policy["default_user_namespace"]))
    template_root = expand_path(str(policy["shared_knowledge_template_root"]))
    template_user_path = template_root / "users" / user
    if not (template_user_path / ".gitkeep").is_file():
        fail(f"missing template user namespace: {template_user_path}")

    if args.local:
        state_file = state_path(policy)
        if not state_file.is_file():
            fail(f"missing local state: {state_file}")
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(f"invalid local state json: {exc}")
        for field in policy["state_fields"]:
            if field not in state:
                fail(f"local state missing field: {field}")
        if state.get("private_identity_committed") is not False:
            fail("local state must not mark private identity as committed")
        if state.get("user_namespace") != user:
            fail(f"local state user_namespace mismatch: {state.get('user_namespace')} != {user}")

    print(f"USER_AGENT_IDENTITY_OK user={user} local={'yes' if args.local else 'not-required'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize/check RedCap local user and Agent identity state.")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--host", default="unknown")
    check = sub.add_parser("check")
    check.add_argument("--local", action="store_true", help="also require ignored local state generated by installer")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "init":
        return command_init(args)
    if args.command == "check":
        return command_check(args)
    fail(f"unknown command: {args.command}", code=2)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

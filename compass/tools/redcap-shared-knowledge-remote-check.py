#!/usr/bin/env python3
# 用途：公共知识库治理脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#shared-knowledge-layer

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "references/shared-knowledge-remote-binding.json"
HEX_RE = re.compile(r"^[0-9a-f]{40}$")


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-shared-knowledge-remote-check] {message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid json {path}: {exc}")
    if not isinstance(payload, dict):
        fail("policy must be a JSON object")
    return payload


def require_text(item: dict[str, Any], key: str, label: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{label}: missing non-empty {key}")
    return value.strip()


def safe_rel(raw: str, label: str) -> str:
    if raw.startswith("/") or raw.startswith("~"):
        fail(f"{label}: path must be repo-relative: {raw}")
    parts = Path(raw).parts
    if ".." in parts or raw in {"", "."}:
        fail(f"{label}: unsafe path: {raw}")
    return Path(raw).as_posix()


def is_under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def git_output(cwd: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", "-C", str(cwd), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        fail(f"git {' '.join(args)} failed in {cwd}: {completed.stderr.strip() or completed.stdout.strip()}")
    return completed.stdout.strip()


def validate_preferred_worktree(
    payload: dict[str, Any],
    root: Path,
    expected_files: list[tuple[str, str, Path]],
) -> str | None:
    raw = payload.get("preferred_local_worktree")
    if raw is None:
        fail("preferred_local_worktree is required when --require-worktree is used")
    if not isinstance(raw, str) or not raw.strip():
        fail("preferred_local_worktree must be a non-empty string")
    path = Path(raw.strip()).expanduser()
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if payload.get("preferred_worktree_must_be_external") is True and is_under(path, root):
        fail(f"preferred_local_worktree must live outside the RedCap repo: {path}")
    if not path.exists():
        fail(f"preferred_local_worktree missing: {path}")
    if not path.is_dir():
        fail(f"preferred_local_worktree is not a directory: {path}")
    if not (path / ".git").exists():
        fail(f"preferred_local_worktree is not a git worktree: {path}")
    if git_output(path, ["rev-parse", "--is-inside-work-tree"]) != "true":
        fail(f"preferred_local_worktree is not inside a git worktree: {path}")
    origin = git_output(path, ["remote", "get-url", "origin"])
    if origin != require_text(payload, "remote_url", "policy"):
        fail(f"preferred_local_worktree origin mismatch: {origin}")
    status = git_output(path, ["status", "--short"])
    if status:
        fail(f"preferred_local_worktree has uncommitted changes: {status}")
    expected = sorted(remote_rel for _repo_rel, remote_rel, _path in expected_files)
    actual = sorted(line for line in git_output(path, ["ls-files"]).splitlines() if line)
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    if missing or extra:
        fail(f"preferred_local_worktree tree mismatch missing={missing} extra={extra}")
    return str(path)


def check_url(payload: dict[str, Any]) -> None:
    remote_url = require_text(payload, "remote_url", "policy")
    parsed = urlparse(remote_url)
    fixture_mode = payload.get("fixture_mode") is True
    if parsed.username or parsed.password:
        fail("remote_url must not contain embedded credentials")
    if parsed.query or parsed.fragment:
        fail("remote_url must not contain query strings or fragments")
    if fixture_mode:
        if parsed.scheme not in {"https", "file"}:
            fail("fixture remote_url must use https or file scheme")
        return
    if parsed.scheme != "https":
        fail("production remote_url must use https")
    if parsed.hostname != payload.get("remote_host") or parsed.hostname != "gitee.com":
        fail("production remote_url must point to gitee.com and match remote_host")
    expected_path = f"/{require_text(payload, 'remote_owner', 'policy')}/{require_text(payload, 'remote_repo', 'policy')}.git"
    if parsed.path != expected_path:
        fail(f"remote_url path must be {expected_path}")


def load_safety_policy(root: Path, raw: str) -> dict[str, Any]:
    rel = safe_rel(raw, "safety_policy_path")
    path = root / rel
    if not path.is_file():
        fail(f"missing safety policy: {rel}")
    payload = load_json(path)
    patterns = payload.get("secret_patterns")
    if not isinstance(patterns, list):
        fail("safety policy must contain secret_patterns list")
    return payload


def compile_secret_patterns(policy: dict[str, Any]) -> list[tuple[str, re.Pattern[str]]]:
    compiled: list[tuple[str, re.Pattern[str]]] = []
    for entry in policy.get("secret_patterns", []):
        if not isinstance(entry, dict):
            fail("secret pattern entries must be objects")
        pattern_id = require_text(entry, "id", "secret_pattern")
        pattern = require_text(entry, "pattern", pattern_id)
        try:
            compiled.append((pattern_id, re.compile(pattern)))
        except re.error as exc:
            fail(f"invalid secret regex {pattern_id}: {exc}")
    return compiled


def matches_any(value: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(value, pattern) for pattern in patterns)


def candidate_files(payload: dict[str, Any], root: Path) -> list[tuple[str, str, Path]]:
    local_root_rel = safe_rel(require_text(payload, "local_root", "policy"), "local_root")
    local_root = root / local_root_rel
    if not local_root.is_dir():
        fail(f"local_root missing: {local_root_rel}")
    if payload.get("remote_root") != ".":
        fail("remote_root must remain '.' for the initial public shared-knowledge repository")
    candidates = payload.get("allowed_candidates")
    if not isinstance(candidates, list) or not candidates:
        fail("allowed_candidates must be a non-empty list")
    forbidden = payload.get("forbidden_path_globs")
    if not isinstance(forbidden, list) or not all(isinstance(item, str) and item.strip() for item in forbidden):
        fail("forbidden_path_globs must be a list of non-empty strings")

    resolved: list[tuple[str, str, Path]] = []
    seen_remote: set[str] = set()
    for index, item in enumerate(candidates, start=1):
        if not isinstance(item, dict):
            fail("allowed_candidates entries must be objects")
        label = f"candidate[{index}]"
        local_rel = safe_rel(require_text(item, "path", label), f"{label}.path")
        remote_rel = safe_rel(require_text(item, "remote_path", label), f"{label}.remote_path")
        require_text(item, "purpose", label)
        if remote_rel in seen_remote:
            fail(f"duplicate remote_path: {remote_rel}")
        seen_remote.add(remote_rel)
        repo_rel = f"{local_root_rel}/{local_rel}"
        if matches_any(local_rel, forbidden) or matches_any(repo_rel, forbidden) or matches_any(remote_rel, forbidden):
            fail(f"{label}: candidate matches forbidden path glob: {repo_rel} -> {remote_rel}")
        path = local_root / local_rel
        if not path.is_file():
            fail(f"{label}: candidate file missing: {repo_rel}")
        if not is_under(path, local_root):
            fail(f"{label}: candidate escapes local_root: {local_rel}")
        resolved.append((repo_rel, remote_rel, path))
    return resolved


def scan_candidate_content(files: list[tuple[str, str, Path]], safety_policy: dict[str, Any]) -> None:
    max_bytes = safety_policy.get("max_text_scan_bytes", 2 * 1024 * 1024)
    if not isinstance(max_bytes, int) or max_bytes <= 0:
        fail("safety policy max_text_scan_bytes must be a positive integer")
    patterns = compile_secret_patterns(safety_policy)
    for repo_rel, _remote_rel, path in files:
        size = path.stat().st_size
        if size > max_bytes:
            fail(f"candidate too large for text safety scan: {repo_rel}")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            fail(f"candidate must be UTF-8 text: {repo_rel}")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern_id, pattern in patterns:
                if pattern.search(line):
                    fail(f"candidate contains credential-like content: {repo_rel}:{line_number}:{pattern_id}")


def check_last_verified(payload: dict[str, Any]) -> str | None:
    last = payload.get("last_verified")
    if last is None:
        if payload.get("status") == "bound":
            fail("bound policy requires last_verified evidence")
        return None
    if not isinstance(last, dict):
        fail("last_verified must be null or an object")
    head = require_text(last, "remote_head", "last_verified")
    if not HEX_RE.fullmatch(head):
        fail("last_verified.remote_head must be a full 40-character git sha")
    require_text(last, "checked_at_utc", "last_verified")
    expected_ref = f"refs/heads/{require_text(payload, 'default_branch', 'policy')}"
    if last.get("remote_ref") != expected_ref:
        fail(f"last_verified.remote_ref must be {expected_ref}")
    return head


def live_head(payload: dict[str, Any]) -> str:
    branch = require_text(payload, "default_branch", "policy")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", branch) or branch.startswith("-") or ".." in branch:
        fail(f"unsafe default_branch: {branch}")
    ref = f"refs/heads/{branch}"
    remote_url = require_text(payload, "remote_url", "policy")
    completed = subprocess.run(
        ["git", "ls-remote", "--heads", remote_url, ref],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        fail(f"git ls-remote failed: {completed.stderr.strip() or completed.stdout.strip()}")
    line = completed.stdout.strip().splitlines()[0] if completed.stdout.strip() else ""
    if not line:
        fail(f"remote head missing: {ref}")
    head, remote_ref = line.split()[:2]
    if remote_ref != ref or not HEX_RE.fullmatch(head):
        fail(f"unexpected remote head output: {line}")
    return head


def verify_remote_tree(payload: dict[str, Any], expected_files: list[tuple[str, str, Path]]) -> list[str]:
    branch = require_text(payload, "default_branch", "policy")
    remote_url = require_text(payload, "remote_url", "policy")
    expected = sorted(remote_rel for _repo_rel, remote_rel, _path in expected_files)
    temp_dir = Path(tempfile.mkdtemp(prefix="redcap-shared-knowledge-remote-check-"))
    try:
        completed = subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                "--depth",
                "1",
                "--branch",
                branch,
                "--single-branch",
                remote_url,
                str(temp_dir),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            fail(f"git clone for remote tree verification failed: {completed.stderr.strip() or completed.stdout.strip()}")
        listed = subprocess.run(
            ["git", "-C", str(temp_dir), "ls-files"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if listed.returncode != 0:
            fail(f"git ls-files for remote tree verification failed: {listed.stderr.strip() or listed.stdout.strip()}")
        actual = sorted(line.strip() for line in listed.stdout.splitlines() if line.strip())
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        if missing or extra:
            fail(f"remote tree mismatch missing={missing} extra={extra}")
        local_by_remote = {remote_rel: path for _repo_rel, remote_rel, path in expected_files}
        for remote_rel, local_path in local_by_remote.items():
            remote_path = temp_dir / remote_rel
            if remote_path.read_bytes() != local_path.read_bytes():
                fail(f"remote file content mismatch: {remote_rel}")
        return actual
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def check_policy(policy_path: Path, root: Path, live: bool, require_worktree: bool) -> None:
    payload = load_json(policy_path)
    if payload.get("version") != 1:
        fail("version must be 1")
    if payload.get("binding_id") != "redcap-shared-knowledge-gitee-remote-binding":
        fail("binding_id must be redcap-shared-knowledge-gitee-remote-binding")
    if payload.get("status") not in {"prepared", "bound", "blocked-external"}:
        fail("status must be prepared, bound, or blocked-external")
    if payload.get("publish_mode") != "template-only":
        fail("publish_mode must remain template-only")
    check_url(payload)
    safety_policy = load_safety_policy(root, require_text(payload, "safety_policy_path", "policy"))
    files = candidate_files(payload, root)
    scan_candidate_content(files, safety_policy)
    preferred_worktree = validate_preferred_worktree(payload, root, files) if require_worktree else None
    expected_head = check_last_verified(payload)

    live_value = None
    remote_tree: list[str] = []
    if live:
        live_value = live_head(payload)
        if expected_head and live_value != expected_head:
            fail(f"remote head drift: policy={expected_head} live={live_value}")
        remote_tree = verify_remote_tree(payload, files)

    print("SHARED_KNOWLEDGE_REMOTE_BINDING_OK")
    print(f"policy={policy_path}")
    print(f"status={payload.get('status')}")
    print(f"remote_url={payload.get('remote_url')}")
    print(f"default_branch={payload.get('default_branch')}")
    print(f"candidates={len(files)}")
    if preferred_worktree:
        print(f"preferred_local_worktree={preferred_worktree}")
    if live_value:
        print(f"live_head={live_value}")
        print(f"remote_tree_files={len(remote_tree)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedCap shared-knowledge remote binding policy.")
    parser.add_argument("--root", default=str(ROOT), help="RedCap repository root")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY), help="remote binding policy JSON")
    parser.add_argument("--live", action="store_true", help="also verify the remote branch head with git ls-remote")
    parser.add_argument("--require-worktree", action="store_true", help="require the preferred local public-library worktree to exist and be clean")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy = Path(args.policy)
    if not policy.is_absolute():
        policy = (Path.cwd() / policy).resolve()
    if not policy.is_file():
        fail(f"missing policy: {policy}")
    check_policy(policy, root, args.live, args.require_worktree)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# 用途：发布安全治理脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULT = ROOT / "references/clean-workspace-install-e2e.json"
PACKAGE_SAFETY_POLICY = ROOT / "references/package-publish-safety-policy.json"
MANIFEST_ID = "redcap-clean-workspace-install-e2e"
TASK_ID = "redcap-clean-workspace-install-e2e"

ALLOWED_POST_RESULT_DRIFT_PATHS = {
    "compass/tools/redcap-execution-guarantee-check.py",
    "compass/tools/redcap-multi-session-acceptance.sh",
    "compass/tools/redcap-parent-receipt-aggregation-check.py",
    "references/clean-workspace-install-e2e.json",
    "references/execution-guarantees.json",
    "references/file-lookup-dictionary.md",
    "references/file-lookup-dictionary-policy.json",
    "references/parent-receipt-aggregation-policy.json",
    "references/redcap-parent-task-ledger.md",
    "references/redcap-r0-r22-registry.json",
    "references/legacy-asset-migration-dry-run.json",
    "compass/docs/catalog.json",
    "private-archive/redcap-knowledge/task-reports/2026-04-30-historical-asset-migration-main-tree-copy-apply.md",
    "private-archive/redcap-knowledge/task-reports/2026-05-01-redcap-clean-workspace-install-e2e.md",
    "compass/docs/task-reports/2026-05-03-parent-receipt-durability-reconciliation.md",
    "private-archive/redcap-knowledge/task-reports/2026-05-06-agent-reading-absorption.md",
    "private-archive/redcap-knowledge/task-reports/2026-05-06-redcap-public-distillation-preflight.md",
    "compass/knowledge/lessons.md",
}

ALLOWED_POST_RESULT_DRIFT_PREFIXES = (
    "prism/runs/20260501-redcap-clean-workspace-install-e2e/",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-clean-workspace-e2e] {message}")


def run_git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        fail(completed.stderr.strip() or completed.stdout.strip() or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def git_success(root: Path, *args: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    ).returncode == 0


def git_status(root: Path) -> str:
    return run_git(root, "status", "--porcelain=v1", "--untracked-files=all")


def output_excerpt(value: str, limit: int = 1600) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...<truncated>"


def redact_text(value: str, replacements: dict[str, str]) -> str:
    text = value
    for raw, replacement in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        if raw:
            text = text.replace(raw, replacement)
    return text


def redact_payload(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, str):
        return redact_text(value, replacements)
    if isinstance(value, list):
        return [redact_payload(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: redact_payload(item, replacements) for key, item in value.items()}
    return value


def safe_command(command: list[str]) -> list[str]:
    return [str(item) for item in command]


def run_command(label: str, command: list[str], *, cwd: Path, env: dict[str, str], timeout: int) -> dict[str, Any]:
    started = now_iso()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "label": label,
            "command": safe_command(command),
            "cwd": str(cwd),
            "started_at": started,
            "finished_at": now_iso(),
            "exit_code": completed.returncode,
            "stdout_excerpt": output_excerpt(completed.stdout),
            "stderr_excerpt": output_excerpt(completed.stderr),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "label": label,
            "command": safe_command(command),
            "cwd": str(cwd),
            "started_at": started,
            "finished_at": now_iso(),
            "exit_code": 124,
            "stdout_excerpt": output_excerpt(exc.stdout or ""),
            "stderr_excerpt": output_excerpt(exc.stderr or f"timeout after {timeout}s"),
        }


def minimal_env(temp_home: Path, runtime_base: Path, identity_file: Path) -> dict[str, str]:
    keep = ("PATH", "SHELL", "LANG", "LC_ALL", "TMPDIR")
    env = {key: value for key, value in os.environ.items() if key in keep and value}
    env["HOME"] = str(temp_home)
    env["REDCAP_IDENTITY_FILE"] = str(identity_file)
    env["REDCAP_RUNTIME_PROJECT_BASE_DIR"] = str(runtime_base)
    env["REDCAP_HOST"] = "codex"
    env["REDCAP_SKIP_SESSION_END_SUCCESS_NOTIFY"] = "1"
    return env


def load_forbidden_candidate_globs(root: Path) -> list[str]:
    policy_path = root / PACKAGE_SAFETY_POLICY.relative_to(ROOT)
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"unable to load package safety policy: {exc}")
    globs = payload.get("deny_path_globs")
    if not isinstance(globs, list) or not globs:
        fail("package safety policy deny_path_globs must be a non-empty list")
    result = [item for item in globs if isinstance(item, str) and item.strip()]
    if len(result) != len(globs):
        fail("package safety policy deny_path_globs contains invalid entries")
    return result


def forbidden_candidate_matches(candidates: list[str], patterns: list[str]) -> list[str]:
    matches: list[str] = []
    for candidate in candidates:
        if any(fnmatch.fnmatch(candidate, pattern) for pattern in patterns):
            matches.append(candidate)
    return matches


def allowed_post_result_drift(path: str) -> bool:
    return path in ALLOWED_POST_RESULT_DRIFT_PATHS or any(path.startswith(prefix) for prefix in ALLOWED_POST_RESULT_DRIFT_PREFIXES)


def assert_no_private_path_leak(result: dict[str, Any], *, root: Path) -> None:
    encoded = json.dumps(result, ensure_ascii=False)
    source_repo = result.get("source_repo_path")
    if isinstance(source_repo, str) and source_repo.startswith("/"):
        fail("source_repo_path must be redacted, not an absolute path")
    private_patterns = [
        str(root.resolve()),
        str(Path.home()),
        "/Users/",
        "/private/var/folders/",
        "/var/folders/",
    ]
    leaked = [pattern for pattern in private_patterns if pattern and pattern in encoded]
    if leaked:
        fail("result contains private absolute path evidence")


def read_candidates(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def apply_dirty_worktree_snapshot(source_root: Path, target: Path) -> str:
    diff = subprocess.run(
        ["git", "-C", str(source_root), "diff", "--binary", "HEAD", "--"],
        capture_output=True,
        check=False,
    )
    if diff.returncode != 0:
        fail(diff.stderr.decode("utf-8", "replace").strip() or "git diff HEAD failed")
    if diff.stdout:
        applied = subprocess.run(
            ["git", "-C", str(target), "apply", "--whitespace=nowarn", "--binary"],
            input=diff.stdout,
            capture_output=True,
            check=False,
        )
        if applied.returncode != 0:
            fail(applied.stderr.decode("utf-8", "replace").strip() or "failed to apply dirty worktree diff")

    untracked = subprocess.run(
        ["git", "-C", str(source_root), "ls-files", "--others", "--exclude-standard", "-z"],
        capture_output=True,
        check=False,
    )
    if untracked.returncode != 0:
        fail(untracked.stderr.decode("utf-8", "replace").strip() or "git ls-files --others failed")
    for raw in untracked.stdout.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", "surrogateescape")
        source = source_root / rel
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            if dest.exists() or dest.is_symlink():
                dest.unlink()
            os.symlink(os.readlink(source), dest)
        elif source.is_file():
            shutil.copy2(source, dest)

    if git_status(target):
        run_git(target, "add", "-A")
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(target),
                "-c",
                "user.name=RedCap Clean Workspace E2E",
                "-c",
                "user.email=redcap-clean-e2e@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "redcap clean workspace dirty snapshot",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            fail(completed.stderr.strip() or completed.stdout.strip() or "failed to commit dirty worktree snapshot")
    return run_git(target, "rev-parse", "HEAD")


def clone_clean_workspace(source_root: Path, target: Path, head: str, *, include_dirty_snapshot: bool) -> str:
    completed = subprocess.run(
        ["git", "clone", "--no-hardlinks", "--quiet", str(source_root), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        fail(completed.stderr.strip() or completed.stdout.strip() or "git clone failed")
    run_git(target, "checkout", "--quiet", head)
    if include_dirty_snapshot:
        return apply_dirty_worktree_snapshot(source_root, target)
    return run_git(target, "rev-parse", "HEAD")


def run_e2e(root: Path, *, timeout: int, allow_dirty: bool, keep_temp: bool, npm_pack_dry_run: bool) -> dict[str, Any]:
    source_head = run_git(root, "rev-parse", "HEAD")
    source_status = git_status(root)
    if source_status and not allow_dirty:
        fail("source worktree must be clean before clean workspace E2E; commit or pass --allow-dirty for local debugging")

    temp_root = Path(tempfile.mkdtemp(prefix="redcap-clean-workspace-e2e-"))
    clone_root = temp_root / "clean-clone"
    temp_home = temp_root / "home"
    runtime_base = temp_root / "runtime"
    identity_file = temp_home / ".cap" / "identity.md"
    candidate_list = temp_root / "package-candidates.txt"
    commands: list[dict[str, Any]] = []
    cleanup_error = ""

    try:
        temp_home.mkdir(parents=True, exist_ok=True)
        runtime_base.mkdir(parents=True, exist_ok=True)
        tested_head = clone_clean_workspace(root, clone_root, source_head, include_dirty_snapshot=bool(source_status and allow_dirty))
        env = minimal_env(temp_home, runtime_base, identity_file)

        commands.append(
            run_command(
                "revive-cap",
                ["./revive-cap.sh", "--host", "codex", "--init-identity"],
                cwd=clone_root,
                env=env,
                timeout=timeout,
            )
        )
        commands.append(run_command("redcap-status", ["bin/redcap", "status"], cwd=clone_root, env=env, timeout=timeout))
        commands.append(run_command("publish-safety", ["bin/redcap", "publish-safety"], cwd=clone_root, env=env, timeout=timeout))

        package_command = ["bin/redcap", "package-manifest", "--output", str(candidate_list), "--check"]
        if npm_pack_dry_run:
            package_command.append("--npm-pack-dry-run")
        commands.append(run_command("package-manifest", package_command, cwd=clone_root, env=env, timeout=timeout))

        candidates = read_candidates(candidate_list)
        forbidden = forbidden_candidate_matches(candidates, load_forbidden_candidate_globs(root))
        clone_status = git_status(clone_root)
        replacements = {
            str(identity_file): "<temporary-identity-file>",
            str(candidate_list): "<temporary-candidate-list>",
            str(runtime_base): "<temporary-runtime-base>",
            str(temp_home): "<temporary-home>",
            str(clone_root): "<clean-clone>",
            str(temp_root): "<temporary-root>",
            str(root.resolve()): "<source-repo>",
        }
        passed = (
            all(item["exit_code"] == 0 for item in commands)
            and identity_file.is_file()
            and runtime_base.is_dir()
            and not clone_status
            and bool(candidates)
            and not forbidden
        )

        payload = {
            "version": 1,
            "manifest_id": MANIFEST_ID,
            "task_id": TASK_ID,
            "created_at": now_iso(),
            "source_repo_path": "<source-repo>",
            "source_head": source_head,
            "tested_head": tested_head,
            "source_worktree_dirty_allowed": allow_dirty,
            "source_worktree_dirty": bool(source_status),
            "source_worktree_snapshot_applied": bool(source_status and allow_dirty),
            "clean_workspace_e2e_passed": passed,
            "temporary_workspace_removed": not keep_temp,
            "temporary_root": str(temp_root) if keep_temp else "",
            "clean_clone_path": str(clone_root) if keep_temp else "",
            "isolation": {
                "home_path": str(temp_home) if keep_temp else "<temporary>",
                "runtime_project_base": str(runtime_base) if keep_temp else "<temporary>",
                "identity_file": str(identity_file) if keep_temp else "<temporary>",
                "identity_initialized": identity_file.is_file(),
                "runtime_base_exists": runtime_base.is_dir(),
            },
            "package_candidates": {
                "count": len(candidates),
                "forbidden_matches": forbidden,
                "npm_pack_dry_run_checked": npm_pack_dry_run,
            },
            "clean_clone_git_status_clean": clone_status == "",
            "commands": commands,
        }
        return redact_payload(payload, replacements)
    finally:
        if not keep_temp:
            try:
                shutil.rmtree(temp_root)
            except OSError as exc:
                cleanup_error = str(exc)
        if cleanup_error:
            # The payload cannot be mutated after return from finally, so surface
            # cleanup failures as hard failures rather than silently retaining temp data.
            fail(f"failed to remove temporary workspace: {cleanup_error}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid result json {path}: {exc}")
    if not isinstance(payload, dict):
        fail("result must be a JSON object")
    return payload


def validate_result(result: dict[str, Any], *, root: Path, require_current_head: bool) -> None:
    if result.get("version") != 1:
        fail("result version must be 1")
    if result.get("manifest_id") != MANIFEST_ID:
        fail(f"manifest_id must be {MANIFEST_ID}")
    if result.get("task_id") != TASK_ID:
        fail(f"task_id must be {TASK_ID}")
    if result.get("clean_workspace_e2e_passed") is not True:
        fail("clean_workspace_e2e_passed must be true")
    if result.get("clean_clone_git_status_clean") is not True:
        fail("clean clone git status must be clean")
    assert_no_private_path_leak(result, root=root)
    isolation = result.get("isolation")
    if not isinstance(isolation, dict) or isolation.get("identity_initialized") is not True or isolation.get("runtime_base_exists") is not True:
        fail("isolation evidence must show identity and runtime base were created")
    package = result.get("package_candidates")
    if not isinstance(package, dict) or int(package.get("count", 0)) <= 0:
        fail("package candidate evidence must be non-empty")
    if package.get("forbidden_matches"):
        fail("package candidate evidence contains forbidden matches")
    commands = result.get("commands")
    if not isinstance(commands, list) or len(commands) < 4:
        fail("commands must contain revive/status/publish-safety/package-manifest evidence")
    failed = [item for item in commands if not isinstance(item, dict) or item.get("exit_code") != 0]
    if failed:
        fail("all E2E commands must exit 0")
    if require_current_head:
        if result.get("source_worktree_dirty") is True or result.get("source_worktree_snapshot_applied") is True:
            fail("committed result must come from a clean source worktree, not a dirty snapshot")
        current_head = run_git(root, "rev-parse", "HEAD")
        source_head = result.get("source_head")
        if source_head != current_head:
            if not isinstance(source_head, str) or not git_success(root, "merge-base", "--is-ancestor", source_head, current_head):
                fail(f"result source_head is stale: {source_head} != {current_head}")
            drift = [
                line.strip()
                for line in run_git(root, "diff", "--name-only", f"{source_head}..{current_head}").splitlines()
                if line.strip()
            ]
            unsafe_drift = [path for path in drift if not allowed_post_result_drift(path)]
            if unsafe_drift:
                fail(
                    "result source_head is stale across unsafe code/policy drift: "
                    + ", ".join(unsafe_drift)
                )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run RedCap clean workspace / cross-machine style install E2E.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--result", default=str(DEFAULT_RESULT))
    parser.add_argument("--write-result", action="store_true")
    parser.add_argument("--check-result", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true", help="Only for local debugging before committing the E2E tool.")
    parser.add_argument("--keep-temp", action="store_true")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--skip-npm-pack-dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    result_path = Path(args.result)
    if not result_path.is_absolute():
        result_path = root / result_path

    if args.check_result and not args.write_result:
        if not result_path.is_file():
            fail(f"missing result file: {result_path}")
        validate_result(load_json(result_path), root=root, require_current_head=True)
        print(f"CLEAN_WORKSPACE_E2E_OK result={result_path}")
        return 0

    result = run_e2e(
        root,
        timeout=args.timeout,
        allow_dirty=args.allow_dirty,
        keep_temp=args.keep_temp,
        npm_pack_dry_run=not args.skip_npm_pack_dry_run,
    )
    if args.write_result:
        write_json(result_path, result)
    validate_result(result, root=root, require_current_head=False)
    if args.check_result:
        validate_result(load_json(result_path), root=root, require_current_head=False)
    print(
        "CLEAN_WORKSPACE_E2E_OK "
        f"head={result['source_head']} candidates={result['package_candidates']['count']} "
        f"npm_pack_dry_run={str(result['package_candidates']['npm_pack_dry_run_checked']).lower()}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

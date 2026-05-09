#!/usr/bin/env python3
# 用途：公共知识库版本绑定脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#shared-knowledge-layer

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BINDING = ROOT / "references/shared-knowledge-remote-binding.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-arsenal-version-binding-check] {message}")


def git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(cwd), *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode != 0:
        fail(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout.strip()


def main() -> int:
    try:
        payload = json.loads(BINDING.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid binding json: {exc}")
    version_binding = payload.get("version_binding")
    if not isinstance(version_binding, dict):
        fail("shared-knowledge remote binding missing version_binding")
    expected = version_binding.get("validated_local_head")
    if not isinstance(expected, str) or len(expected) != 40:
        fail("version_binding.validated_local_head must be a git sha")
    worktree_raw = payload.get("preferred_local_worktree")
    if not isinstance(worktree_raw, str) or not worktree_raw:
        fail("preferred_local_worktree missing")
    worktree = Path(worktree_raw)
    if not worktree.is_absolute():
        worktree = (ROOT / worktree).resolve()
    if not worktree.is_dir():
        fail(f"preferred worktree missing: {worktree}")
    actual = git(worktree, "rev-parse", "HEAD")
    if actual != expected:
        fail(f"arsenal head drift: binding={expected} actual={actual}")
    if git(worktree, "status", "--short"):
        fail("arsenal worktree must be clean before release-readiness claims")
    print("ARSENAL_VERSION_BINDING_OK")
    print(f"validated_local_head={actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

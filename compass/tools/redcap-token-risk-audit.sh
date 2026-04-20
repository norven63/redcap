#!/usr/bin/env bash
# Audit for repository areas that can accidentally flood agent context.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 - "$REDCAP_ROOT" <<'PY'
from __future__ import annotations

import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])

TRACKED_WARN_BYTES = 50_000
TRACKED_HARD_BYTES = 250_000
IGNORED_WARN_BYTES = 1_000_000
IGNORED_HARD_BYTES = 50_000_000
IGNORED_WARN_FILES = 500

REQUIRED_IGNORED_PATHS = [
    "prism/runs",
    "compass/.runtime",
    "compass/.workflow",
    ".env",
    "prompt.txt",
    "cli_console.md",
]

FORBIDDEN_AUTO_IMPORTS = [
    "compass/CONTRIBUTING.md",
    "compass/knowledge/lessons.md",
]

COPILOT_FORBIDDEN_FULL_READS = [
    "read_file` 读取 `compass/CONTRIBUTING.md`",
    "read_file` 读取 `compass/knowledge/lessons.md`",
]

ENTRY_FILES = [
    "CLAUDE.md",
    "GEMINI.md",
    ".github/copilot-instructions.md",
]

OPTIONAL_LOCAL_ENTRY_FILES = [
    "AGENTS.md",
]


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-token-risk-audit] {message}")


def path_size(path: pathlib.Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def path_file_count(path: pathlib.Path) -> int:
    if path.is_file():
        return 1
    return sum(1 for child in path.rglob("*") if child.is_file())


def git_ignored(rel_path: str) -> bool:
    proc = run_git("check-ignore", "-q", rel_path)
    return proc.returncode == 0


def mitigation_for(rel_path: str, size: int) -> str | None:
    if rel_path.startswith("compass/docs/"):
        return "docs-catalog-plan-budget"
    if rel_path.startswith("compass/knowledge/"):
        return "knowledge-index"
    if rel_path == "compass/tools/redcap-multi-session-acceptance.sh":
        return "acceptance-index"
    if rel_path == "compass/CONTRIBUTING.md":
        return "contributing-core-and-section-routing"
    if rel_path in {"SKILL.md", "compass/soul.md"}:
        return "entry-no-large-auto-import-and-targeted-rg"
    if rel_path.startswith("references/backlogs/"):
        return "current-status-backlog-summary"
    if rel_path.startswith("prism/") and not rel_path.startswith("prism/runs/"):
        return "prism-protocol-targeted-read"
    if size < TRACKED_HARD_BYTES:
        return "below-hard-threshold"
    return None


tracked_proc = run_git("ls-files", "-z")
if tracked_proc.returncode != 0:
    fail("git ls-files failed")

tracked_paths = [p for p in tracked_proc.stdout.split("\0") if p]
large_tracked: list[tuple[int, str, str | None]] = []
for rel in tracked_paths:
    path = root / rel
    if not path.is_file():
        continue
    size = path.stat().st_size
    if size >= TRACKED_WARN_BYTES:
        large_tracked.append((size, rel, mitigation_for(rel, size)))

missing_mitigation = [
    (size, rel) for size, rel, mitigation in large_tracked
    if mitigation is None
]
if missing_mitigation:
    rels = ", ".join(f"{rel}({size})" for size, rel in missing_mitigation[:8])
    fail("large tracked files missing mitigation: " + rels)

entry_failures: list[str] = []
for rel in ENTRY_FILES:
    path = root / rel
    if not path.is_file():
        entry_failures.append(f"missing entry file: {rel}")
        continue
    text = path.read_text(encoding="utf-8")
    for token in FORBIDDEN_AUTO_IMPORTS:
        for raw in text.splitlines():
            if raw.strip() == "@" + token:
                entry_failures.append(f"{rel} still auto-imports large file: @{token}")
    if rel == ".github/copilot-instructions.md":
        for token in COPILOT_FORBIDDEN_FULL_READS:
            if token in text:
                entry_failures.append(f"{rel} still requires full read: {token}")
    for required in [
        "compass/CONTRIBUTING.core.md",
        "redcap-current-status.sh",
        "compass/knowledge/index.md",
        "redcap-docs-catalog.sh",
    ]:
        if required not in text:
            entry_failures.append(f"{rel} missing progressive entry hint: {required}")

if entry_failures:
    fail("; ".join(entry_failures))

for rel in OPTIONAL_LOCAL_ENTRY_FILES:
    path = root / rel
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8")
    for token in FORBIDDEN_AUTO_IMPORTS:
        for raw in text.splitlines():
            if raw.strip() == "@" + token:
                entry_failures.append(f"{rel} still auto-imports large file: @{token}")
    for required in [
        "compass/CONTRIBUTING.core.md",
        "redcap-current-status.sh",
        "compass/knowledge/index.md",
        "redcap-docs-catalog.sh",
    ]:
        if required not in text:
            entry_failures.append(f"{rel} missing progressive entry hint: {required}")

if entry_failures:
    fail("; ".join(entry_failures))

ignored_issues: list[str] = []
ignored_large: list[tuple[int, int, str, str]] = []
for rel in REQUIRED_IGNORED_PATHS:
    if not git_ignored(rel):
        ignored_issues.append(f"{rel} is not ignored")
        continue
    path = root / rel
    if path.exists():
        size = path_size(path)
        files = path_file_count(path)
        if size >= IGNORED_WARN_BYTES or files >= IGNORED_WARN_FILES:
            level = "warn"
            if size >= IGNORED_HARD_BYTES:
                level = "hard"
                ignored_issues.append(f"{rel} ignored but too large for unattended context safety: {size}")
            ignored_large.append((size, files, rel, level))

required_scripts = [
    "compass/tools/redcap-docs-catalog.sh",
    "compass/tools/redcap-knowledge-index-check.sh",
    "compass/tools/redcap-acceptance-index.sh",
    "compass/tools/redcap-contributing-ia-check.sh",
]
for rel in required_scripts:
    if not (root / rel).is_file():
        fail(f"missing mitigation script: {rel}")

print("TOKEN_RISK_AUDIT_OK")
print(f"tracked_large_files={len(large_tracked)} warn_bytes={TRACKED_WARN_BYTES} hard_bytes={TRACKED_HARD_BYTES}")
for size, rel, mitigation in sorted(large_tracked, reverse=True)[:15]:
    print(f"tracked\tbytes={size}\tpath={rel}\tmitigation={mitigation}")
print(f"ignored_large_paths={len(ignored_large)} warn_bytes={IGNORED_WARN_BYTES} hard_bytes={IGNORED_HARD_BYTES} warn_files={IGNORED_WARN_FILES}")
for size, files, rel, level in sorted(ignored_large, reverse=True)[:10]:
    print(f"ignored\tlevel={level}\tbytes={size}\tfiles={files}\tpath={rel}\tpolicy=gitignored-do-not-bulk-read")
print("entry_auto_import_large_files=none")
print("rule=Use current-status, docs catalog plan/budget, knowledge index, and acceptance index before opening large files.")
PY

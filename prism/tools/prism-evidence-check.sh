#!/usr/bin/env bash
# Validate that Prism run evidence, report archive, and cleanup policy stay honest.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 - "$REDCAP_ROOT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])


def fail(message: str) -> None:
    raise SystemExit(f"[prism-evidence-check] {message}")


def read(rel: str) -> str:
    path = root / rel
    if not path.is_file():
        fail(f"missing file: {rel}")
    return path.read_text(encoding="utf-8", errors="replace")


gitignore = read(".gitignore")
if "prism/runs/" not in gitignore:
    fail(".gitignore must keep prism/runs/ out of git")

protocol = read("prism/protocol.md")
for phrase in [
    "run-scoped 本地运行证据",
    "repo-tracked 归档证据",
    "formal Prism 成功次数",
    "获得用户显式批准",
    "archived: true",
    "prism-runs-lifecycle.sh",
    "acceptance-fixture",
]:
    if phrase not in protocol:
        fail(f"prism/protocol.md missing evidence boundary: {phrase}")

status_script = read("compass/tools/redcap-current-status.sh")
for phrase in [
    "formal Prism 报告索引",
    "legacy/non-auditable",
    "当前任务新增的 formal quorum 不能从报告总数或 prism/runs 目录数量反推",
    "prism/runs 分类",
]:
    if phrase not in status_script:
        fail(f"current-status missing Prism honesty phrase: {phrase}")

index_text = read("prism/reports/index.yaml")
entry_count = index_text.count("\n  - id:")
archived_count = index_text.count("\n    archived:")
if entry_count == 0:
    fail("prism/reports/index.yaml must contain at least one report entry")
if archived_count != entry_count:
    fail("every Prism report entry in index.yaml must declare archived")

lifecycle_output = ""
try:
    import subprocess
    lifecycle_output = subprocess.check_output(
        ["bash", str(root / "prism/tools/prism-runs-lifecycle.sh"), "check"],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()
except Exception as exc:
    fail(f"prism-runs-lifecycle check failed: {exc}")
if "PRISM_RUNS_LIFECYCLE_OK" not in lifecycle_output:
    fail("prism-runs-lifecycle check did not return PRISM_RUNS_LIFECYCLE_OK")

print("PRISM_EVIDENCE_OK")
PY

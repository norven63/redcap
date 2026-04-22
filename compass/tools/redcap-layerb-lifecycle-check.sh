#!/usr/bin/env bash
# Validate Layer B lifecycle contract, terminology surface, and entry-point wording.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 - "$REDCAP_ROOT" <<'PY'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
lifecycle = root / "references/runtime-memory-architecture.md"
terms = root / "compass/knowledge/runtime-memory-architecture.md"
architecture = root / "ARCHITECTURE.md"
contributing = root / "compass/CONTRIBUTING.md"
readme = root / "README.md"
knowledge_index = root / "compass/knowledge/index.md"
diagnose = root / "compass/tools/redcap-diagnose.sh"
execution_guarantees = root / "references/execution-guarantees.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-layerb-lifecycle-check] {message}")


for path in (lifecycle, terms, architecture, contributing, readme, knowledge_index, diagnose, execution_guarantees):
    if not path.is_file():
        fail(f"missing file: {path.relative_to(root)}")

lifecycle_text = lifecycle.read_text(encoding="utf-8", errors="replace")
terms_text = terms.read_text(encoding="utf-8", errors="replace")
architecture_text = architecture.read_text(encoding="utf-8", errors="replace")
contributing_text = contributing.read_text(encoding="utf-8", errors="replace")
readme_text = readme.read_text(encoding="utf-8", errors="replace")
index_text = knowledge_index.read_text(encoding="utf-8", errors="replace")
diagnose_text = diagnose.read_text(encoding="utf-8", errors="replace")
execution_guarantees_text = execution_guarantees.read_text(encoding="utf-8", errors="replace")

required_states = {
    "REANCHORED",
    "TASK_LOCKED",
    "EXECUTING",
    "REVIEW_PENDING",
    "CLOSEOUT_PENDING",
    "CLOSED",
    "BLOCKED",
}
documented_states = set(re.findall(r"^\|\s*`([A-Z_]+)`\s*\|", lifecycle_text, flags=re.MULTILINE))
missing_states = sorted(required_states - documented_states)
if missing_states:
    fail("missing Layer B lifecycle states: " + ", ".join(missing_states))

required_bindings = [
    "compass/tools/redcap-install.sh",
    "compass/tools/redcap-layerB-session-start.sh",
    "compass/tools/redcap-pm-gate-check.sh",
    "compass/tools/redcap-drift-check.sh",
    "compass/tools/redcap-on-stop-review.sh",
    "compass/tools/redcap-validator-chain.sh",
    "compass/tools/redcap-task-report-check.sh",
    "compass/tools/redcap-on-complete.sh",
    "compass/tools/redcap-layerB-session-end.sh",
    "compass/tools/redcap-interop-governance.sh",
]
missing_bindings = [path for path in required_bindings if path not in lifecycle_text]
if missing_bindings:
    fail("lifecycle contract missing bound scripts: " + ", ".join(missing_bindings))

missing_binding_files = [path for path in required_bindings if not (root / path).is_file()]
if missing_binding_files:
    fail("lifecycle contract references missing script files: " + ", ".join(missing_binding_files))

required_terms = [
    "真相源",
    "镜像",
    "闭环证据",
    "跨会话考古 / 追踪层",
    "长期知识和项目资产的持续沉淀",
    "分布式控制面状态机",
]
missing_terms = [term for term in required_terms if term not in terms_text]
if missing_terms:
    fail("runtime memory glossary missing terms: " + ", ".join(missing_terms))

if "Layer B 无状态机保护" in contributing_text:
    fail("CONTRIBUTING.md still contains the outdated 'Layer B 无状态机保护' wording")

if "references/runtime-memory-architecture.md" not in architecture_text:
    fail("ARCHITECTURE.md must reference references/runtime-memory-architecture.md")
if "compass/knowledge/runtime-memory-architecture.md" not in architecture_text:
    fail("ARCHITECTURE.md must reference compass/knowledge/runtime-memory-architecture.md")
if "compass/knowledge/runtime-memory-architecture.md" not in readme_text:
    fail("README.md must surface the runtime memory glossary")
if "compass/knowledge/runtime-memory-architecture.md" not in index_text:
    fail("knowledge index must include the runtime memory glossary")
if "redcap-layerb-lifecycle-check.sh" not in diagnose_text:
    fail("redcap-diagnose.sh must execute redcap-layerb-lifecycle-check.sh")
if '"id": "layerb-lifecycle-contract"' not in execution_guarantees_text:
    fail("execution-guarantees.json must register layerb-lifecycle-contract")
for required_path in (
    "compass/tools/redcap-layerb-lifecycle-check.sh",
    "references/runtime-memory-architecture.md",
    "compass/knowledge/runtime-memory-architecture.md",
):
    if required_path not in execution_guarantees_text:
        fail(f"execution-guarantees.json missing guarantee path: {required_path}")

print("LAYERB_LIFECYCLE_CONTRACT_OK")
PY

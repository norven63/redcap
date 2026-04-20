#!/usr/bin/env bash
# Validate that revival/re-anchor rules have not drifted out of host entry files,
# reload rules, and the execution-guarantee registry.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="${1:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

python3 - "$REDCAP_ROOT" <<'PY'
import pathlib
import sys

root = pathlib.Path(sys.argv[1])


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-revival-check] {message}")


def read(rel_path: str) -> str:
    path = root / rel_path
    if not path.is_file():
        fail(f"missing file: {rel_path}")
    return path.read_text(encoding="utf-8")


def require(rel_path: str, patterns: list[str]) -> None:
    text = read(rel_path)
    for pattern in patterns:
        if pattern not in text:
            fail(f"{rel_path} missing required revival pattern: {pattern}")


def forbid(rel_path: str, patterns: list[str]) -> None:
    text = read(rel_path)
    for pattern in patterns:
        if pattern.startswith("@"):
            found = any(raw.strip() == pattern for raw in text.splitlines())
        else:
            found = pattern in text
        if found:
            fail(f"{rel_path} contains forbidden revival pattern: {pattern}")


require(
    "compass/soul.md",
    [
        "~/.cap/identity.md",
        "compass/CONTRIBUTING.core.md",
        "compass/CONTRIBUTING.md",
        "compass/knowledge/lessons.md",
        "compass/knowledge/design-principles.md",
        "compass/knowledge/index.md",
        ".dev-task.md",
        "compass/docs/catalog.json",
        "loom/dispatcher/reload-rules.yaml",
        "references/execution-guarantees.json",
        "redcap-current-status.sh",
        "redcap-docs-catalog.sh",
        "plan",
        "budget",
        "redcap-detect-agents.sh",
        "redcap-execution-guarantee-check.sh",
        "redcap-knowledge-index-check.sh",
        "redcap-overlay-governance-check.sh",
        "redcap-diagnose.sh",
        "redcap-state-machine-check.sh",
        "redcap-acceptance-index.sh",
        "redcap-token-risk-audit.sh",
        "redcap-contributing-ia-check.sh",
        "redcap-review-tracks-check.sh",
        "redcap-hook-contract-check.sh",
        "redcap-runtime-helper-check.sh",
        "当前已完成 / 上一步完成的是 / 下一步计划做的是 / 整体计划脉络图与当前位置",
    ],
)

for rel_path in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
    require(
        rel_path,
        [
            "@compass/soul.md",
            "@compass/CONTRIBUTING.core.md",
            "轻量自动导入",
            "不再默认展开注入上下文",
            "redcap-current-status.sh",
            "redcap-execution-guarantee-check.sh",
            "redcap-docs-catalog.sh budget",
            "compass/knowledge/index.md",
        ],
    )
    forbid(
        rel_path,
        [
            "@compass/CONTRIBUTING.md",
            "@compass/knowledge/lessons.md",
        ],
    )

require(
    ".github/copilot-instructions.md",
    [
        "compass/soul.md",
        "compass/CONTRIBUTING.core.md",
        "compass/CONTRIBUTING.md",
        "compass/knowledge/lessons.md",
        "redcap-current-status.sh",
        "redcap-execution-guarantee-check.sh",
        "redcap-docs-catalog.sh budget",
        "redcap-acceptance-index.sh",
        "不要默认全文读取",
    ],
)
forbid(
    ".github/copilot-instructions.md",
    [
        "read_file` 读取 `compass/CONTRIBUTING.md`",
        "read_file` 读取 `compass/knowledge/lessons.md`",
    ],
)

require(
    "loom/dispatcher/reload-rules.yaml",
    [
        "on_session_revival",
        "compass/soul.md",
        "compass/CONTRIBUTING.md",
        "compass/knowledge/lessons.md",
        "compass/knowledge/index.md",
        "compass/docs/catalog.json",
        "references/execution-guarantees.json",
        "prism/protocol.md",
    ],
)

require(
    "references/hook-standards.md",
    [
        "复活与执行保障不可遗漏",
        "经验沉淀不可遗漏",
        "docs catalog 不可陈旧",
        "docs 读取必须渐进披露",
        "knowledge 读取必须先走导航",
        "token 风险审计",
    ],
)

require(
    "references/execution-guarantees.json",
    [
        "revival-core-files",
        "lessons-closeout",
        "knowledge-index-navigation",
        "overlay-ask-user-boundary",
        "diagnostic-overview",
        "state-machine-contract",
        "soul-identity-update",
        "prism-formal-run",
        "docs-catalog-freshness",
        "docs-progressive-disclosure",
        "acceptance-index-navigation",
        "token-risk-audit",
        "contributing-core-routing",
        "review-tracks-gate",
        "hook-contract-audit",
        "runtime-helper-convergence",
        "cli-console-mirror-contract",
    ],
)

print("REVIVAL_PROTOCOL_OK")
PY

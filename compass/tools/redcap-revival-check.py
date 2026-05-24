#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-revival-check] {message}")


def read(root: pathlib.Path, rel_path: str) -> str:
    path = root / rel_path
    if not path.is_file():
        fail(f"missing file: {rel_path}")
    return path.read_text(encoding="utf-8")


def require(root: pathlib.Path, rel_path: str, patterns: list[str]) -> None:
    text = read(root, rel_path)
    for pattern in patterns:
        if pattern not in text:
            fail(f"{rel_path} missing required revival pattern: {pattern}")


def optional_require(root: pathlib.Path, rel_path: str, patterns: list[str]) -> None:
    path = root / rel_path
    if not path.is_file():
        return
    require(root, rel_path, patterns)


def forbid(root: pathlib.Path, rel_path: str, patterns: list[str]) -> None:
    text = read(root, rel_path)
    for pattern in patterns:
        if pattern.startswith("@"):
            found = any(raw.strip() == pattern for raw in text.splitlines())
        else:
            found = pattern in text
        if found:
            fail(f"{rel_path} contains forbidden revival pattern: {pattern}")


def optional_forbid(root: pathlib.Path, rel_path: str, patterns: list[str]) -> None:
    path = root / rel_path
    if not path.is_file():
        return
    forbid(root, rel_path, patterns)


def main() -> None:
    root = pathlib.Path(sys.argv[1])

    require(
        root,
        "compass/soul.md",
        [
            "~/.cap/identity.md",
            "redcap-install.sh",
            "compass/CONTRIBUTING.core.md",
            "compass/CONTRIBUTING.md",
            "assets/knowledge/lessons.md",
            "assets/knowledge/design-principles.md",
            "assets/knowledge/index.md",
            ".dev-task.md",
            "assets/docs/catalog.json",
            "loom/dispatcher/reload-rules.yaml",
            "assets/references/execution-guarantees.json",
            "redcap-current-status.sh",
            "redcap-docs-catalog.sh",
            "plan",
            "budget",
            "redcap-detect-agents.sh",
            "redcap-execution-guarantee-check.sh",
            "redcap-knowledge-index-check.sh",
            "redcap-tracking-health.sh",
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

    optional_require(
        root,
        "AGENTS.md",
        [
            "~/.cap/identity.md",
            "@compass/soul.md",
            "@compass/CONTRIBUTING.core.md",
            "轻量自动导入",
            "不再默认展开注入上下文",
            "redcap-install.sh",
            "redcap-current-status.sh",
            "redcap-execution-guarantee-check.sh",
            "redcap-docs-catalog.sh budget",
            "assets/knowledge/index.md",
        ],
    )
    optional_forbid(
        root,
        "AGENTS.md",
        [
            "@compass/CONTRIBUTING.md",
            "@compass/knowledge/lessons.md",
        ],
    )

    for rel_path in ("CLAUDE.md", "GEMINI.md"):
        require(
            root,
            rel_path,
            [
                "~/.cap/identity.md",
                "@compass/soul.md",
                "@compass/CONTRIBUTING.core.md",
                "轻量自动导入",
                "不再默认展开注入上下文",
                "redcap-install.sh",
                "redcap-current-status.sh",
                "redcap-execution-guarantee-check.sh",
                "redcap-docs-catalog.sh budget",
                "assets/knowledge/index.md",
            ],
        )
        forbid(
            root,
            rel_path,
            [
                "@compass/CONTRIBUTING.md",
                "@compass/knowledge/lessons.md",
            ],
        )

    require(
        root,
        ".github/copilot-instructions.md",
        [
            "~/.cap/identity.md",
            "compass/soul.md",
            "compass/CONTRIBUTING.core.md",
            "compass/CONTRIBUTING.md",
            "redcap-install.sh",
            "assets/knowledge/lessons.md",
            "redcap-current-status.sh",
            "tracking-health",
            "redcap-execution-guarantee-check.sh",
            "redcap-docs-catalog.sh budget",
            "redcap-acceptance-index.sh",
            "不要默认全文读取",
        ],
    )
    forbid(
        root,
        ".github/copilot-instructions.md",
        [
            "read_file` 读取 `compass/CONTRIBUTING.md`",
            "read_file` 读取 `compass/knowledge/lessons.md`",
        ],
    )

    require(
        root,
        "loom/dispatcher/reload-rules.yaml",
        [
            "on_session_revival",
            "compass/soul.md",
            "compass/CONTRIBUTING.md",
            "assets/knowledge/lessons.md",
            "assets/knowledge/index.md",
            "assets/docs/catalog.json",
            "assets/references/execution-guarantees.json",
            "prism/protocol.md",
        ],
    )

    require(
        root,
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
        root,
        "references/execution-guarantees.json",
        [
            "revival-core-files",
            "lessons-closeout",
            "knowledge-index-navigation",
            "overlay-ask-user-boundary",
            "diagnostic-overview",
            "state-machine-contract",
            "soul-identity-update",
            "install-revival-entry",
            "prism-formal-run",
            "docs-catalog-freshness",
            "docs-progressive-disclosure",
            "acceptance-index-navigation",
            "token-risk-audit",
            "tracking-health-overview",
            "contributing-core-routing",
            "review-tracks-gate",
            "hook-contract-audit",
            "runtime-helper-convergence",
            "cli-console-mirror-contract",
        ],
    )

    print("REVIVAL_PROTOCOL_OK")


if __name__ == "__main__":
    main()

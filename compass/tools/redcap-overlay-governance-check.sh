#!/usr/bin/env bash
# Validate RedCap-owned overlay/ask_user governance rules.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 - "$REDCAP_ROOT" <<'PY'
import pathlib
import sys

root = pathlib.Path(sys.argv[1])


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-overlay-governance-check] {message}")


def require(rel_path: str, patterns: list[str]) -> None:
    path = root / rel_path
    if not path.is_file():
        fail(f"missing file: {rel_path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    for pattern in patterns:
        if pattern not in text:
            fail(f"{rel_path} missing required pattern: {pattern}")


require(
    "SKILL.md",
    [
        "advisory overlay",
        "缺少宿主下游 skill 不是合法 blocker",
        "共享宿主 skill 属于 carrier-owned asset",
        "overlay / host skill 产物不得覆盖 `.dev-task.md`、任务账本、门禁结果、runtime receipt 或 closeout 结论",
    ],
)
require(
    "compass/CONTRIBUTING.md",
    [
        "宿主通用 skill overlay 兼容规则",
        "缺少这类宿主下游 skill 不是合法 blocker",
        "共享宿主 skill 属于宿主资产",
        "prompt-level hard limitation",
        "overlay / host skill 产物不得覆盖 `.dev-task.md`、任务账本、门禁结果、runtime receipt 或 closeout 结论",
    ],
)
require(
    "references/agent-constraints.md",
    [
        "brainstorming/澄清习惯",
        "返回 `need_user`",
        "下游 skill 当成 blocker",
        "缺少 AI 无法推断的外部事实/凭证/偏好",
        "overlay / host skill 产物不得覆盖 `.dev-task.md`、任务账本、门禁结果、runtime receipt 或 closeout 结论",
    ],
)
require(
    "compass/docs/specs/2026-04-12-host-skill-overlay-governance-design.md",
    [
        "advisory overlay",
        "degraded / unsupported overlay",
        "ask_user 属于宿主层工具调用",
        "overlay / host skill 产物不得覆盖 `.dev-task.md`、任务账本、门禁结果、runtime receipt 或 closeout 结论",
    ],
)
require(
    "ARCHITECTURE.md",
    [
        "**advisory-only**，不得覆盖 `.dev-task.md`",
        "task report / acceptance report",
        "runtime project state",
    ],
)

print("OVERLAY_GOVERNANCE_OK")
PY

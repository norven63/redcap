#!/usr/bin/env bash
# Validate CONTRIBUTING information architecture: core contract first, full spec routed by section.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 - "$REDCAP_ROOT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-contributing-ia-check] {message}")


def read(rel: str) -> str:
    path = root / rel
    if not path.is_file():
        fail(f"missing file: {rel}")
    return path.read_text(encoding="utf-8", errors="replace")


core = read("compass/CONTRIBUTING.core.md")
core_lines = core.splitlines()
if len(core_lines) > 120:
    fail(f"core contract too long for first-read use: {len(core_lines)} lines")
for required in [
    "compass/CONTRIBUTING.md 仍是权威规范全文",
    "不得把全文规范当默认上下文",
    "章节路由",
    "必跑入口",
    "redcap-current-status.sh",
    "redcap-diagnose.sh",
    "变更前必须做经验回顾",
]:
    if required not in core:
        fail(f"core contract missing required phrase: {required}")

full = read("compass/CONTRIBUTING.md")
for heading in [
    "## 1. 变更前：经验回顾",
    "## 4. 独立架构评审",
    "## 6. 文件变更影响范围提示",
    "## 7. Layer B 大型任务断点续传",
    "## §11 棱镜（Prism）",
    "## §13 任务级完成强制复盘协议",
]:
    if heading not in full:
        fail(f"CONTRIBUTING missing routed heading: {heading}")

for rel in ("CLAUDE.md", "GEMINI.md"):
    text = read(rel)
    if len(text.splitlines()) > 80:
        fail(f"{rel} must remain a thin host shim, not a second handbook")
    if "@compass/CONTRIBUTING.core.md" not in text:
        fail(f"{rel} must auto-import CONTRIBUTING.core.md")
    if "@compass/soul.md" not in text:
        fail(f"{rel} must auto-import soul.md")
    if "权威规范唯一来源" not in text or "轻量自动导入" not in text:
        fail(f"{rel} must stay in thin-shim form")
    for forbidden in ("@compass/CONTRIBUTING.md", "@compass/knowledge/lessons.md"):
        if any(line.strip() == forbidden for line in text.splitlines()):
            fail(f"{rel} must not auto-import large file: {forbidden}")
    at_lines = [line.strip() for line in text.splitlines() if line.strip().startswith("@")]
    if at_lines != ["@compass/soul.md", "@compass/CONTRIBUTING.core.md"]:
        fail(f"{rel} must only auto-import soul + CONTRIBUTING core")

agents_path = root / "AGENTS.md"
if agents_path.is_file():
    text = read("AGENTS.md")
    if len(text.splitlines()) > 80:
        fail("AGENTS.md must remain a thin local Codex shim, not a second handbook")
    if "@compass/CONTRIBUTING.core.md" not in text or "@compass/soul.md" not in text:
        fail("AGENTS.md must keep soul + CONTRIBUTING core startup imports")
    for forbidden in ("@compass/CONTRIBUTING.md", "@compass/knowledge/lessons.md"):
        if any(line.strip() == forbidden for line in text.splitlines()):
            fail(f"AGENTS.md must not auto-import large file: {forbidden}")

copilot = read(".github/copilot-instructions.md")
if len(copilot.splitlines()) > 80:
    fail("Copilot instructions must remain a thin startup shim")
if "compass/CONTRIBUTING.core.md" not in copilot:
    fail("Copilot instructions must require CONTRIBUTING.core.md")
if "不要默认全文读取 `CONTRIBUTING.md`" not in copilot:
    fail("Copilot instructions must forbid default full CONTRIBUTING read")
if "首要动作" not in copilot:
    fail("Copilot instructions must remain a startup shim, not a full handbook")

stop_review = read("compass/tools/redcap-on-stop-review.sh")
if "CONTRIBUTING.core.md" not in stop_review:
    fail("stop-review prompt must include CONTRIBUTING.core.md")
if "selected_guidance" not in stop_review:
    fail("stop-review prompt must use selected CONTRIBUTING guidance, not raw full text")
if "{contributing}" in stop_review:
    fail("stop-review prompt still embeds full CONTRIBUTING text")

token_audit = read("compass/tools/redcap-token-risk-audit.sh")
if "compass/CONTRIBUTING.core.md" not in token_audit:
    fail("token-risk audit must know the CONTRIBUTING core mitigation")

architecture = read("ARCHITECTURE.md")
for required in [
    "carrier-required shims",
    "不得长成第二份规范正文",
    "首读压缩层",
]:
    if required not in architecture:
        fail(f"ARCHITECTURE missing host/IA boundary: {required}")

print("CONTRIBUTING_IA_OK")
PY

#!/usr/bin/env bash
# 用途：Codex 生命周期 Hook 候选接线检查；验证配置、wrapper 与保守边界没有漂移。
# Dictionary: references/file-lookup-dictionary.md#skill-and-host-distribution

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 - "$REDCAP_ROOT" <<'PY'
from pathlib import Path
import json
import sys

root = Path(sys.argv[1])


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-codex-hooks-check] {message}")


def read(rel: str) -> str:
    path = root / rel
    if not path.is_file():
        fail(f"missing file: {rel}")
    return path.read_text(encoding="utf-8", errors="replace")


config = read(".codex/config.toml")
if "codex_hooks = true" not in config:
    fail(".codex/config.toml must enable codex_hooks feature flag")

try:
    hooks = json.loads(read(".codex/hooks.json"))
except Exception as exc:
    fail(f".codex/hooks.json is not valid JSON: {exc}")

events = hooks.get("hooks") or {}
for event in ["SessionStart", "PreToolUse", "Stop"]:
    if event not in events:
        fail(f"hooks.json missing event: {event}")

hooks_text = json.dumps(hooks, ensure_ascii=False)
if "REDCAP_CODEX_HOOK_E2E_PROBE" in hooks_text:
    fail("hooks.json must not inject REDCAP_CODEX_HOOK_E2E_PROBE; probe mode is only allowed inside the live marker E2E runner")

for token in [
    "redcap-codex-session-start.sh",
    "redcap-codex-pre-tool-use.sh",
    "redcap-codex-stop.sh",
    "startup|resume",
    "Bash|apply_patch|Edit|Write",
]:
    if token not in hooks_text:
        fail(f"hooks.json missing token: {token}")

for rel in [
    "compass/tools/redcap-codex-session-start.sh",
    "compass/tools/redcap-codex-pre-tool-use.sh",
    "compass/tools/redcap-codex-stop.sh",
    "compass/tools/redcap-codex-live-marker-e2e.sh",
]:
    script = root / rel
    if not script.is_file():
        fail(f"missing wrapper: {rel}")
    text = script.read_text(encoding="utf-8", errors="replace")
    if "用途：" not in text.splitlines()[1]:
        fail(f"{rel} must keep a Chinese purpose header")

if "decision" not in read("compass/tools/redcap-codex-stop.sh") or "stop_hook_active" not in read("compass/tools/redcap-codex-stop.sh"):
    fail("Stop wrapper must return Codex-compatible JSON and guard continuation loops")
if "REDCAP_CODEX_HOOK_E2E_PROBE" not in read("compass/tools/redcap-codex-session-start.sh"):
    fail("SessionStart wrapper must support safe live marker E2E probe mode")
if "REDCAP_CODEX_HOOK_E2E_PROBE" not in read("compass/tools/redcap-codex-stop.sh"):
    fail("Stop wrapper must support safe live marker E2E probe mode")
if "codex exec" not in read("compass/tools/redcap-codex-live-marker-e2e.sh") or "--check-result" not in read("compass/tools/redcap-codex-live-marker-e2e.sh"):
    fail("Codex live marker E2E script must provide run and check-result flows")

pre_tool = read("compass/tools/redcap-codex-pre-tool-use.sh")
for blocked in ["git reset --hard", "prune-local", "npm publish"]:
    if blocked not in pre_tool:
        fail(f"PreToolUse wrapper missing dangerous command guard: {blocked}")

codex_doc = read("compass/knowledge/hooks-codex-cli.md")
for phrase in [
    "official lifecycle hooks",
    "feature flag",
    "project trust",
    "live marker E2E",
    "not full host parity",
    "Codex.app interactive",
]:
    if phrase not in codex_doc:
        fail(f"Codex knowledge doc missing boundary phrase: {phrase}")

readiness = read("compass/tools/redcap-host-hook-readiness.sh")
for phrase in [
    "repo-owned-candidate",
    "live marker E2E",
    ".codex/hooks.json",
    "codex-live-marker-e2e.json",
]:
    if phrase not in readiness:
        fail(f"host readiness missing Codex candidate phrase: {phrase}")

print("CODEX_HOOKS_CANDIDATE_OK")
PY

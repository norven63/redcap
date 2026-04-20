#!/usr/bin/env bash
# Validate that cli_console.md remains a local-only overwrite mirror, not a second answer log.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 - "$REDCAP_ROOT" <<'PY'
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1])


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-cli-console-mirror-check] {message}")


gitignore = (root / ".gitignore").read_text(encoding="utf-8", errors="replace")
if "cli_console.md" not in gitignore:
    fail("cli_console.md must be gitignored")

classifier = (root / "compass/tools/redcap-artifact-classifier.sh").read_text(encoding="utf-8", errors="replace")
if '"cli_console.md": ("local-only", "local-only-display-mirror"' not in classifier:
    fail("artifact classifier must mark cli_console.md as local-only display mirror")

helper = (root / "compass/tools/redcap-cli-console-mirror.sh").read_text(encoding="utf-8", errors="replace")
if ">>" in helper:
    fail("cli console mirror helper must not append")
if '>"$TARGET_PATH"' not in helper and ': >"$TARGET_PATH"' not in helper:
    fail("cli console mirror helper must overwrite/truncate target")

allowed_script_refs = {
    "compass/tools/redcap-cli-console-mirror.sh",
    "compass/tools/redcap-cli-console-mirror-check.sh",
    "compass/tools/redcap-multi-session-acceptance.sh",
    "compass/tools/redcap-artifact-classifier.sh",
    "compass/tools/redcap-token-risk-audit.sh",
}
for rel in subprocess.check_output(
    ["git", "-C", str(root), "ls-files"],
    text=True,
).splitlines():
    if rel in allowed_script_refs:
        continue
    if not rel.endswith((".sh", ".py")):
        continue
    path = root / rel
    text = path.read_text(encoding="utf-8", errors="replace")
    if "cli_console.md" in text or "REDCAP_CLI_CONSOLE_PATH" in text:
        fail(f"unexpected script-level cli_console.md writer/reference outside mirror helper: {rel}")

proc = subprocess.run(
    ["git", "-C", str(root), "check-ignore", "-q", "cli_console.md"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    check=False,
)
if proc.returncode != 0:
    fail("git check-ignore does not ignore cli_console.md")

print("CLI_CONSOLE_MIRROR_OK")
PY

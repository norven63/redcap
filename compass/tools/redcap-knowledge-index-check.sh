#!/usr/bin/env bash
# 用途：知识沉淀与自进化脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

# Validate that compass/knowledge has a first-read navigation index.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 - "$REDCAP_ROOT" <<'PY'
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
knowledge = root / "compass/knowledge"
index_path = knowledge / "index.md"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-knowledge-index-check] {message}")


if not index_path.is_file():
    fail("missing compass/knowledge/index.md")

text = index_path.read_text(encoding="utf-8", errors="replace")
for required in ("首读导航", "不要默认 bulk-read", "redcap-knowledge-index-check.sh", "热点主题速览"):
    if required not in text:
        fail(f"index missing required phrase: {required}")

missing: list[str] = []
for path in sorted(knowledge.glob("*.md")):
    if path.name == "index.md":
        continue
    rel = path.relative_to(root).as_posix()
    if rel not in text:
        missing.append(rel)

if missing:
    fail("index missing knowledge files: " + ", ".join(missing))

print("KNOWLEDGE_INDEX_OK")
PY

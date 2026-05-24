#!/usr/bin/env bash
# 用途：知识沉淀与自进化脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#docs-knowledge-and-evolution

# Validate that assets/knowledge has a first-read navigation index.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 - "$REDCAP_ROOT" <<'PY'
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
knowledge = root / "assets/knowledge"
index_path = knowledge / "index.md"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-knowledge-index-check] {message}")


if not index_path.is_file():
    fail("missing assets/knowledge/index.md")

text = index_path.read_text(encoding="utf-8", errors="replace")
for required in ("首读导航", "不要默认 bulk-read", "redcap-knowledge-index-check.sh", "热点主题速览", "assets/knowledge/lessons/<l-id>.md"):
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

lessons_index = knowledge / "lessons.md"
lessons_dir = knowledge / "lessons"
if not lessons_index.is_file():
    fail("missing lessons index")
if not lessons_dir.is_dir():
    fail("missing lessons module directory")
lessons_text = lessons_index.read_text(encoding="utf-8", errors="replace")
if "不承载完整正文" not in lessons_text or "## Lesson 模块索引与旧锚点" not in lessons_text:
    fail("lessons.md must be a lightweight index with legacy redirects")
if "问题源" in lessons_text or "解决方案" in lessons_text or "最后效果" in lessons_text:
    fail("lessons.md appears to contain full lesson bodies; keep bodies in modules")
module_paths = sorted(lessons_dir.glob("l-*.md"))
if len(module_paths) < 100:
    fail("lessons split lost too many modules")
for module in module_paths:
    rel = module.relative_to(root).as_posix()
    module_text = module.read_text(encoding="utf-8", errors="replace")
    if rel not in lessons_text:
        fail(f"lessons index missing module link: {rel}")
    if "Generated from compass/knowledge/lessons.md split" not in module_text:
        fail(f"lesson module missing split provenance: {rel}")

print("KNOWLEDGE_INDEX_OK")
PY

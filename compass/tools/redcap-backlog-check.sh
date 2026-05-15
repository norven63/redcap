#!/usr/bin/env bash
# shellcheck shell=bash
# Validate and sync a repo-tracked backlog authority file with its human-readable guide.

set -uo pipefail

MODE="${1:-strict}"
TASK_FILE="${2:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/redcap-dev-task.sh"

TASK_FILE=$(redcap_dev_task_resolve_file "$TASK_FILE")

BACKLOG_SOURCE_REL=$(redcap_dev_task_extract_kv "$TASK_FILE" "backlog_source" 2>/dev/null || true)
BACKLOG_ID=$(redcap_dev_task_extract_kv "$TASK_FILE" "backlog_id" 2>/dev/null || true)
BACKLOG_ITEM=$(redcap_dev_task_extract_kv "$TASK_FILE" "backlog_item" 2>/dev/null || true)

if [[ -z "$BACKLOG_SOURCE_REL" && -z "$BACKLOG_ID" && -z "$BACKLOG_ITEM" ]]; then
    exit 0
fi

if [[ -z "$BACKLOG_SOURCE_REL" || -z "$BACKLOG_ID" || -z "$BACKLOG_ITEM" ]]; then
    echo "[redcap-backlog-check] backlog metadata must declare backlog_source, backlog_id, backlog_item together" >&2
    exit 1
fi

case "$BACKLOG_SOURCE_REL" in
    /*)
        BACKLOG_SOURCE_ABS="$BACKLOG_SOURCE_REL"
        ;;
    *)
        BACKLOG_SOURCE_ABS="$REDCAP_ROOT/$BACKLOG_SOURCE_REL"
        ;;
esac

python3 - "$MODE" "$REDCAP_ROOT" "$TASK_FILE" "$BACKLOG_SOURCE_ABS" "$BACKLOG_SOURCE_REL" "$BACKLOG_ID" "$BACKLOG_ITEM" <<'PY'
import json
import pathlib
import re
import sys

MODE = sys.argv[1]
REPO_ROOT = pathlib.Path(sys.argv[2])
TASK_FILE = pathlib.Path(sys.argv[3])
BACKLOG_PATH = pathlib.Path(sys.argv[4])
BACKLOG_SOURCE_REL = sys.argv[5]
BACKLOG_ID = sys.argv[6]
BACKLOG_ITEM = sys.argv[7]

ALLOWED_STATUSES = {"done", "in_progress", "pending", "blocked"}
ALLOWED_PRIORITIES = {"P0", "P1", "P2"}
STATUS_LABELS = {
    "done": "已完成",
    "in_progress": "进行中",
    "pending": "待推进",
    "blocked": "阻塞",
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-backlog-check] {message}")


def load_json(path: pathlib.Path):
    if not path.is_file():
        fail(f"backlog source missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid backlog json: {path} ({exc})")


def markdown_field(block: str, key: str) -> str:
    match = re.search(rf"^-\s+\*\*{re.escape(key)}\*\*:\s*`?([^`\n]+)`?\s*$", block, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def validate_governance_debt_markdown() -> None:
    """Governance debt is a markdown register, not a JSON backlog authority."""
    if BACKLOG_SOURCE_REL != "compass/knowledge/governance-debt-register.md":
        fail(f"unsupported markdown backlog source: {BACKLOG_SOURCE_REL}")
    if BACKLOG_ID != "governance-debt-register":
        fail(f"governance debt backlog_id mismatch: {BACKLOG_ID}")
    if not BACKLOG_PATH.is_file():
        fail(f"backlog source missing: {BACKLOG_PATH}")

    text = BACKLOG_PATH.read_text(encoding="utf-8", errors="replace")
    heading = re.search(rf"^###\s+{re.escape(BACKLOG_ITEM)}(?:：|:).*$", text, flags=re.MULTILINE)
    if not heading:
        fail(f"task backlog_item not found in governance debt register: {BACKLOG_ITEM}")
    next_heading = re.search(r"^###\s+", text[heading.end():], flags=re.MULTILINE)
    end = heading.end() + next_heading.start() if next_heading else len(text)
    block = text[heading.start():end]

    design_status = markdown_field(block, "design_status")
    implementation_status = markdown_field(block, "implementation_status")
    if design_status not in {"identified", "design-complete", "not-applicable"}:
        fail(f"{BACKLOG_ITEM}: unsupported design_status: {design_status or 'missing'}")
    if implementation_status not in {"pending", "in-progress", "done", "blocked"}:
        fail(f"{BACKLOG_ITEM}: unsupported implementation_status: {implementation_status or 'missing'}")
    if "**gap**" not in block:
        fail(f"{BACKLOG_ITEM}: missing gap field")
    if MODE in {"anchor", "strict"}:
        return
    if MODE == "render":
        sys.stdout.write(block.rstrip() + "\n")
        return
    if MODE == "sync":
        return
    fail(f"unsupported mode for governance debt markdown: {MODE}")


def require_string(data, key, ctx):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{ctx} missing string field: {key}")
    return value.strip()


def normalize_rel_path(path_str: str) -> str:
    value = pathlib.PurePosixPath(path_str)
    return value.as_posix()


def render_block(data, items_by_id, groups_by_id):
    markers = data["human_contract"]
    start = markers["generated_block_start"]
    end = markers["generated_block_end"]
    current_item = items_by_id[data["current_focus"]["item_id"]]
    human_path = data["human_readable_path"]

    lines = [
        start,
        "## 当前状态总览（自动同步）",
        "",
        "### 这份机制对应哪里",
        f"- 机器权威：`{data['source_of_truth']}`",
        f"- 人类说明：`{human_path}`",
        f"- 当前焦点：`{current_item['id']} {current_item['title']}`",
        f"- 当前焦点说明：{data['current_focus']['summary']}",
        "",
        "### 阶段顺序",
        "| 阶段 | 状态 | 主要条目 | 说明 |",
        "|---|---|---|---|",
    ]
    for phase in data["execution_order"]:
        item_text = " / ".join(phase["item_ids"])
        lines.append(
            f"| {phase['title']} | {STATUS_LABELS[phase['status']]} | {item_text} | {phase['summary']} |"
        )

    lines.extend(
        [
            "",
            "### 条目状态",
            "| 条目 | 所属能力 | 状态 | 优先级 | 一句话说明 |",
            "|---|---|---|---|---|",
        ]
    )
    for group in data["groups"]:
        for item in group["items"]:
            lines.append(
                f"| {item['id']} {item['title']} | {group['title']} | {STATUS_LABELS[item['status']]} | {item['priority']} | {item['summary']} |"
            )

    lines.extend(
        [
            "",
            "### 术语对照",
            "| 术语 | 人话解释 |",
            "|---|---|",
        ]
    )
    for entry in data["glossary"]:
        term = f"{entry['term']}（{entry['label']}）"
        lines.append(f"| {term} | {entry['meaning']} |")

    lines.append(end)
    return "\n".join(lines) + "\n"


if BACKLOG_PATH.suffix.lower() == ".md":
    validate_governance_debt_markdown()
    raise SystemExit(0)

data = load_json(BACKLOG_PATH)

if data.get("version") != 1:
    fail("backlog version must be 1")

source_of_truth = require_string(data, "source_of_truth", "backlog")
if normalize_rel_path(source_of_truth) != normalize_rel_path(BACKLOG_SOURCE_REL):
    fail(
        "backlog source_of_truth mismatch: "
        f"task points to {BACKLOG_SOURCE_REL}, backlog declares {source_of_truth}"
    )

file_backlog_id = require_string(data, "backlog_id", "backlog")
if file_backlog_id != BACKLOG_ID:
    fail(f"backlog_id mismatch: task={BACKLOG_ID}, backlog={file_backlog_id}")

require_string(data, "title", "backlog")
human_path_rel = require_string(data, "human_readable_path", "backlog")
human_path = REPO_ROOT / human_path_rel

authority_boundary = data.get("authority_boundary")
if not isinstance(authority_boundary, dict):
    fail("backlog.authority_boundary must be an object")
for key in (
    "backlog_responsibility",
    "dev_task_responsibility",
    "human_guide_responsibility",
):
    require_string(authority_boundary, key, "backlog.authority_boundary")

human_contract = data.get("human_contract")
if not isinstance(human_contract, dict):
    fail("backlog.human_contract must be an object")

required_headings = human_contract.get("required_headings")
if not isinstance(required_headings, list) or not required_headings:
    fail("backlog.human_contract.required_headings must be a non-empty array")
for heading in required_headings:
    if not isinstance(heading, str) or not heading.strip():
        fail("backlog.human_contract.required_headings contains invalid heading")

for key in ("generated_block_start", "generated_block_end"):
    require_string(human_contract, key, "backlog.human_contract")

glossary = data.get("glossary")
if not isinstance(glossary, list) or not glossary:
    fail("backlog.glossary must be a non-empty array")
for entry in glossary:
    if not isinstance(entry, dict):
        fail("backlog.glossary entries must be objects")
    for key in ("term", "label", "meaning"):
        require_string(entry, key, "backlog.glossary")

groups = data.get("groups")
if not isinstance(groups, list) or not groups:
    fail("backlog.groups must be a non-empty array")

items_by_id = {}
groups_by_id = {}
for group in groups:
    if not isinstance(group, dict):
        fail("backlog.groups entries must be objects")
    group_id = require_string(group, "id", "group")
    group_title = require_string(group, "title", "group")
    items = group.get("items")
    if not isinstance(items, list) or not items:
        fail(f"group {group_id} must define a non-empty items array")
    groups_by_id[group_id] = group_title
    for item in items:
        if not isinstance(item, dict):
            fail(f"group {group_id} has invalid item entry")
        item_id = require_string(item, "id", f"group {group_id} item")
        if item_id in items_by_id:
            fail(f"duplicate backlog item id: {item_id}")
        require_string(item, "title", f"item {item_id}")
        status = require_string(item, "status", f"item {item_id}")
        priority = require_string(item, "priority", f"item {item_id}")
        require_string(item, "phase_id", f"item {item_id}")
        require_string(item, "summary", f"item {item_id}")
        if status not in ALLOWED_STATUSES:
            fail(f"item {item_id} uses unsupported status: {status}")
        if priority not in ALLOWED_PRIORITIES:
            fail(f"item {item_id} uses unsupported priority: {priority}")
        evidence = item.get("evidence_paths", [])
        if not isinstance(evidence, list):
            fail(f"item {item_id} evidence_paths must be an array")
        for evidence_path in evidence:
            if not isinstance(evidence_path, str) or not evidence_path.strip():
                fail(f"item {item_id} has invalid evidence path")
        item["group_id"] = group_id
        items_by_id[item_id] = item

execution_order = data.get("execution_order")
if not isinstance(execution_order, list) or not execution_order:
    fail("backlog.execution_order must be a non-empty array")
phase_ids = set()
for phase in execution_order:
    if not isinstance(phase, dict):
        fail("backlog.execution_order entries must be objects")
    phase_id = require_string(phase, "id", "phase")
    if phase_id in phase_ids:
        fail(f"duplicate phase id: {phase_id}")
    phase_ids.add(phase_id)
    require_string(phase, "title", f"phase {phase_id}")
    phase_status = require_string(phase, "status", f"phase {phase_id}")
    require_string(phase, "summary", f"phase {phase_id}")
    if phase_status not in ALLOWED_STATUSES:
        fail(f"phase {phase_id} uses unsupported status: {phase_status}")
    item_ids = phase.get("item_ids")
    if not isinstance(item_ids, list) or not item_ids:
        fail(f"phase {phase_id} must have a non-empty item_ids array")
    for item_id in item_ids:
        if item_id not in items_by_id:
            fail(f"phase {phase_id} references unknown item: {item_id}")

for item_id, item in items_by_id.items():
    if item["phase_id"] not in phase_ids:
        fail(f"item {item_id} references unknown phase_id: {item['phase_id']}")

current_focus = data.get("current_focus")
if not isinstance(current_focus, dict):
    fail("backlog.current_focus must be an object")
focus_id = require_string(current_focus, "item_id", "backlog.current_focus")
require_string(current_focus, "summary", "backlog.current_focus")
if focus_id not in items_by_id:
    fail(f"current_focus references unknown item: {focus_id}")

if BACKLOG_ITEM not in items_by_id:
    fail(f"task backlog_item not found in backlog: {BACKLOG_ITEM}")

rendered_block = render_block(data, items_by_id, groups_by_id)

if MODE == "anchor":
    raise SystemExit(0)

if MODE == "render":
    sys.stdout.write(rendered_block)
    raise SystemExit(0)

if not human_path.is_file():
    fail(f"human-readable backlog guide missing: {human_path}")

text = human_path.read_text(encoding="utf-8")
for heading in required_headings:
    if heading not in text:
        fail(f"human-readable backlog guide missing required heading: {heading}")

start_marker = human_contract["generated_block_start"]
end_marker = human_contract["generated_block_end"]
start = text.find(start_marker)
end = text.find(end_marker)

if MODE == "sync":
    if start != -1 and end != -1 and end >= start:
        end += len(end_marker)
        new_text = text[:start].rstrip() + "\n\n" + rendered_block + text[end:]
    else:
        suffix = "" if text.endswith("\n") else "\n"
        new_text = text + suffix + "\n" + rendered_block
    human_path.write_text(new_text, encoding="utf-8")
    raise SystemExit(0)

if MODE != "strict":
    fail(f"unsupported mode: {MODE}")

if start == -1 or end == -1 or end < start:
    fail("human-readable backlog guide missing generated block markers")
end += len(end_marker)
current_block = text[start:end]
if current_block.strip() != rendered_block.strip():
    fail("human-readable backlog guide is out of sync with backlog authority; run redcap-backlog-check.sh sync")
PY

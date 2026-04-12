#!/usr/bin/env bash
# shellcheck shell=bash
# Mirror session continuity metadata into host workboards and support explicit imports.

set -uo pipefail

MODE="${1:-}"
ARG1="${2:-}"
ARG2="${3:-}"
ARG3="${4:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/redcap-dev-task.sh"

sync_session_mirror() {
    local workboard_file="$1"
    local task_file="$2"
    local task_id top_goal confirmed_hash runtime_session_id binding_key

    if [[ ! -f "$workboard_file" ]]; then
        echo "[redcap-session-continuity] workboard not found: $workboard_file" >&2
        exit 1
    fi

    task_id=$(redcap_dev_task_extract_kv "$task_file" "task_id" 2>/dev/null || true)
    top_goal=$(redcap_dev_task_extract_kv "$task_file" "top_goal" 2>/dev/null || true)
    confirmed_hash=$(redcap_dev_task_confirmed_hash "$task_file" 2>/dev/null || true)
    runtime_session_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    binding_key="${REDCAP_RUNTIME_BINDING_KEY:-${REDCAP_SESSION_BINDING_KEY:-}}"

    python3 - "$workboard_file" "$task_file" "$task_id" "$top_goal" "$confirmed_hash" "$runtime_session_id" "$binding_key" <<'PY'
import json
import os
import re
import sys
from pathlib import Path

workboard = Path(sys.argv[1]).resolve()
task_file = str(Path(sys.argv[2]).resolve())
task_id = sys.argv[3]
top_goal = sys.argv[4]
confirmed_hash = sys.argv[5]
runtime_session_id = sys.argv[6]
binding_key = sys.argv[7]

session_dir = workboard.parent
session_base = session_dir.parent
session_handle = session_dir.name
files_dir = session_dir / "files"
checkpoints_dir = session_dir / "checkpoints"
imports_dir = files_dir / "imported-sessions"

marker_start = "<!-- redcap:session-mirror:start -->"
marker_end = "<!-- redcap:session-mirror:end -->"


def parse_pointer(plan_path):
    text = plan_path.read_text(encoding="utf-8")
    match = re.search(
        r"<!-- redcap:canonical-pointer:start -->(.*?)<!-- redcap:canonical-pointer:end -->",
        text,
        re.S,
    )
    if not match:
        return {}
    data = {}
    for raw in match.group(1).splitlines():
        line = raw.strip()
        if line.startswith("- ") and ":" in line:
            key, value = line[2:].split(":", 1)
            data[key.strip()] = value.strip()
    return data


def has_own_record() -> bool:
    if files_dir.exists():
        for candidate in files_dir.rglob("*"):
            if not candidate.is_file():
                continue
            if "imported-sessions" in candidate.parts:
                continue
            return True
    if checkpoints_dir.exists():
        for candidate in checkpoints_dir.rglob("*"):
            if candidate.is_file():
                return True
    return False


def latest_import_metadata():
    if not imports_dir.exists():
        return None
    metadata_files = sorted(
        imports_dir.glob("*/metadata.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for metadata_file in metadata_files:
        try:
            return json.loads(metadata_file.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None


def best_candidate():
    best = None
    for plan_path in session_base.glob("*/plan.md"):
        if plan_path.resolve() == workboard:
            continue
        pointer = parse_pointer(plan_path)
        if not pointer:
            continue
        if pointer.get("canonical_path") != task_file:
            continue

        score = 1
        match_strength = "weak"
        if pointer.get("task_id") == task_id and pointer.get("confirmed_hash") == confirmed_hash and confirmed_hash:
            score = 3
            match_strength = "exact"
        elif pointer.get("top_goal") == top_goal and top_goal:
            score = 2
            match_strength = "compatible"

        candidate = {
            "source_session_handle": plan_path.parent.name,
            "source_plan": str(plan_path.resolve()),
            "source_task_id": pointer.get("task_id", ""),
            "source_top_goal": pointer.get("top_goal", ""),
            "source_confirmed_hash": pointer.get("confirmed_hash", ""),
            "suggested_match_strength": match_strength,
            "score": score,
            "mtime": plan_path.stat().st_mtime,
        }

        if best is None or (candidate["score"], candidate["mtime"]) > (best["score"], best["mtime"]):
            best = candidate

    return best


def import_match_strength(imported):
    source_task_id = imported.get("source_task_id", "")
    source_top_goal = imported.get("source_top_goal", "")
    source_confirmed_hash = imported.get("source_confirmed_hash", "")
    if source_task_id == task_id and source_confirmed_hash == confirmed_hash and confirmed_hash:
        return "exact"
    if source_top_goal == top_goal and top_goal:
        return "compatible"
    return ""


state = "fresh-session"
block_lines = [
    marker_start,
    "## RedCap Session Mirror",
    f"- session_handle: {session_handle}",
    f"- runtime_session_id: {runtime_session_id or 'unknown'}",
    f"- session_binding_key: {binding_key or 'unknown'}",
    f"- task_id: {task_id}",
    f"- confirmed_hash: {confirmed_hash}",
]

imported = latest_import_metadata()
stale_import = None
if imported and import_match_strength(imported):
    state = "imported"
    block_lines.extend(
        [
            f"- continuity_state: {state}",
            f"- imported_match_strength: {import_match_strength(imported)}",
            f"- imported_from_session_handle: {imported.get('source_session_handle', '')}",
            f"- imported_from_plan: {imported.get('source_plan', '')}",
            f"- imported_from_task_id: {imported.get('source_task_id', '')}",
            f"- imported_from_confirmed_hash: {imported.get('source_confirmed_hash', '')}",
            f"- imported_at: {imported.get('imported_at', '')}",
            f"- import_root: {imported.get('import_root', '')}",
            "- import_protocol: explicit-copy-preserve-source",
        ]
    )
else:
    if imported:
        stale_import = imported
    if has_own_record():
        state = "self-recorded"
        block_lines.extend(
            [
                f"- continuity_state: {state}",
                "- import_protocol: not-needed-current-session-has-own-record",
            ]
        )
    else:
        candidate = best_candidate()
        if candidate:
            state = "import-suggested"
            next_action = (
                "bash compass/tools/redcap-session-continuity.sh import "
                f"\"{candidate['source_plan']}\" \"{workboard}\" \"{task_file}\""
            )
            block_lines.extend(
                [
                    f"- continuity_state: {state}",
                    f"- suggested_source_session_handle: {candidate['source_session_handle']}",
                    f"- suggested_source_plan: {candidate['source_plan']}",
                    f"- suggested_match_strength: {candidate['suggested_match_strength']}",
                    f"- suggested_source_task_id: {candidate['source_task_id']}",
                    f"- suggested_source_top_goal: {candidate['source_top_goal']}",
                    f"- suggested_source_confirmed_hash: {candidate['source_confirmed_hash']}",
                    "- import_protocol: explicit-only",
                    f"- next_action: {next_action}",
                ]
            )
        else:
            block_lines.extend(
                [
                    f"- continuity_state: {state}",
                    "- import_protocol: no-compatible-source-detected",
                ]
            )

if stale_import:
    block_lines.extend(
        [
            f"- stale_import_session_handle: {stale_import.get('source_session_handle', '')}",
            f"- stale_import_root: {stale_import.get('import_root', '')}",
            "- stale_import_reason: task-metadata-mismatch",
        ]
    )

block_lines.append(marker_end)
block = "\n".join(block_lines)

text = workboard.read_text(encoding="utf-8")
start = text.find(marker_start)
end = text.find(marker_end)
if start != -1 and end != -1 and end >= start:
    end += len(marker_end)
    new_text = text[:start].rstrip() + "\n\n" + block + "\n" + text[end:].lstrip("\n")
else:
    suffix = "" if text.endswith("\n") else "\n"
    new_text = text + suffix + "\n" + block + "\n"

workboard.write_text(new_text, encoding="utf-8")
print(state)
PY
}

import_session_assets() {
    local source_workboard="$1"
    local target_workboard="$2"
    local task_file="$3"

    if [[ ! -f "$source_workboard" ]]; then
        echo "[redcap-session-continuity] source workboard not found: $source_workboard" >&2
        exit 1
    fi
    if [[ ! -f "$target_workboard" ]]; then
        echo "[redcap-session-continuity] target workboard not found: $target_workboard" >&2
        exit 1
    fi

    python3 - "$source_workboard" "$target_workboard" <<'PY'
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

source_workboard = Path(sys.argv[1]).resolve()
target_workboard = Path(sys.argv[2]).resolve()
source_dir = source_workboard.parent
target_dir = target_workboard.parent
source_handle = source_dir.name
target_handle = target_dir.name

if source_dir == target_dir:
    raise SystemExit("[redcap-session-continuity] source and target session must differ")

dest_root = target_dir / "files" / "imported-sessions" / source_handle
if dest_root.exists():
    print(dest_root)
    raise SystemExit(0)

dest_root.mkdir(parents=True, exist_ok=False)
shutil.copy2(source_workboard, dest_root / "plan.md")

source_files = source_dir / "files"
if source_files.exists():
    shutil.copytree(
        source_files,
        dest_root / "files",
        ignore=shutil.ignore_patterns("imported-sessions"),
        dirs_exist_ok=True,
    )

source_checkpoints = source_dir / "checkpoints"
if source_checkpoints.exists():
    shutil.copytree(source_checkpoints, dest_root / "checkpoints", dirs_exist_ok=True)

metadata = {
    "source_session_handle": source_handle,
    "source_plan": str(source_workboard),
    "source_task_id": "",
    "source_top_goal": "",
    "source_confirmed_hash": "",
    "imported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "import_root": str(dest_root.relative_to(target_dir)),
    "target_session_handle": target_handle,
}

text = source_workboard.read_text(encoding="utf-8")
for raw in text.splitlines():
    line = raw.strip()
    if line.startswith("- task_id: "):
        metadata["source_task_id"] = line.split(": ", 1)[1].strip()
    elif line.startswith("- top_goal: "):
        metadata["source_top_goal"] = line.split(": ", 1)[1].strip()
    elif line.startswith("- confirmed_hash: "):
        metadata["source_confirmed_hash"] = line.split(": ", 1)[1].strip()

(dest_root / "metadata.json").write_text(
    json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
    encoding="utf-8",
)
print(dest_root)
PY

    sync_session_mirror "$target_workboard" "$task_file" >/dev/null
}

case "$MODE" in
    sync)
        if [[ -z "$ARG1" ]]; then
            echo "usage: $0 sync <workboard_file> [task_file]" >&2
            exit 2
        fi
        sync_session_mirror "$ARG1" "$(redcap_dev_task_resolve_file "$ARG2")"
        ;;
    import)
        if [[ -z "$ARG1" || -z "$ARG2" ]]; then
            echo "usage: $0 import <source_workboard> <target_workboard> [task_file]" >&2
            exit 2
        fi
        import_session_assets "$ARG1" "$ARG2" "$(redcap_dev_task_resolve_file "$ARG3")"
        ;;
    *)
        echo "usage: $0 <sync|import> ..." >&2
        exit 2
        ;;
esac

exit 0

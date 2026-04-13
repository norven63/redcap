#!/usr/bin/env bash
# shellcheck shell=bash
# Mirror session continuity metadata into host workboards and support explicit imports.

set -euo pipefail

MODE="${1:-}"
ARG1="${2:-}"
ARG2="${3:-}"
ARG3="${4:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/redcap-dev-task.sh"

sync_session_mirror() {
    local workboard_file="$1"
    local task_file="$2"
    local task_id top_goal confirmed_hash active_slice runtime_session_id binding_key runtime_host

    if [[ ! -f "$workboard_file" ]]; then
        echo "[redcap-session-continuity] workboard not found: $workboard_file" >&2
        exit 1
    fi

    task_id=$(redcap_dev_task_extract_kv "$task_file" "task_id" 2>/dev/null || true)
    top_goal=$(redcap_dev_task_extract_kv "$task_file" "top_goal" 2>/dev/null || true)
    confirmed_hash=$(redcap_dev_task_confirmed_hash "$task_file" 2>/dev/null || true)
    active_slice=$(redcap_dev_task_extract_kv "$task_file" "active_slice" 2>/dev/null || true)
    runtime_session_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    binding_key="${REDCAP_RUNTIME_BINDING_KEY:-${REDCAP_SESSION_BINDING_KEY:-}}"
    runtime_host="${REDCAP_RUNTIME_HOST:-}"

    python3 - "$workboard_file" "$task_file" "$task_id" "$top_goal" "$confirmed_hash" "$active_slice" "$runtime_session_id" "$binding_key" "$runtime_host" <<'PY'
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

workboard = Path(sys.argv[1]).resolve()
task_file = str(Path(sys.argv[2]).resolve())
task_id = sys.argv[3]
top_goal = sys.argv[4]
confirmed_hash = sys.argv[5]
active_slice = sys.argv[6]
runtime_session_id = sys.argv[7].strip()
binding_key = sys.argv[8].strip()
runtime_host = sys.argv[9].strip()

repo_root = Path(task_file).resolve().parent
continuity_root = Path(
    os.environ.get("REDCAP_CONTINUITY_ROOT_DIR") or (repo_root / "compass" / ".runtime")
).resolve()
sessions_root = continuity_root / "sessions"
continuity_dir = continuity_root / "continuity"

session_dir = workboard.parent
session_handle = session_dir.name
files_dir = session_dir / "files"
checkpoints_dir = session_dir / "checkpoints"

marker_start = "<!-- redcap:session-mirror:start -->"
marker_end = "<!-- redcap:session-mirror:end -->"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def decode_scalar(raw):
    raw = raw.strip()
    if not raw:
        return ""
    try:
        value = json.loads(raw)
    except Exception:
        return raw
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else str(value)


def parse_scalar_file(path: Path):
    if not path.exists():
        return {}
    data = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = decode_scalar(value)
    return data


def write_scalar_file(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for key, value in data.items():
        normalized = "" if value is None else str(value)
        lines.append(f"{key}: {json.dumps(normalized, ensure_ascii=False)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def parse_marker_block(plan_path: Path, start_marker: str, end_marker: str):
    try:
        text = plan_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    match = re.search(re.escape(start_marker) + r"(.*?)" + re.escape(end_marker), text, re.S)
    if not match:
        return {}
    data = {}
    for raw in match.group(1).splitlines():
        line = raw.strip()
        if line.startswith("- ") and ":" in line:
            key, value = line[2:].split(":", 1)
            data[key.strip()] = value.strip()
    return data


def has_own_record(path: Path) -> bool:
    candidate_files = path / "files"
    candidate_checkpoints = path / "checkpoints"
    if candidate_files.exists():
        for candidate in candidate_files.rglob("*"):
            if not candidate.is_file():
                continue
            if "imported-sessions" in candidate.parts:
                continue
            return True
    if candidate_checkpoints.exists():
        for candidate in candidate_checkpoints.rglob("*"):
            if candidate.is_file():
                return True
    return False


def continuity_session_dir(session_id: str):
    return sessions_root / session_id


def manifest_path_for(session_id: str):
    return continuity_session_dir(session_id) / "manifest.yaml"


def provenance_path_for(session_id: str):
    return continuity_session_dir(session_id) / "provenance.yaml"


def load_manifest_for_runtime(session_id: str):
    if not session_id:
        return {}
    return parse_scalar_file(manifest_path_for(session_id))


def find_manifest_for_workboard(target_workboard: Path):
    for candidate in sessions_root.glob("*/manifest.yaml"):
        data = parse_scalar_file(candidate)
        if data.get("workboard_path") == str(target_workboard):
            return data, candidate
    return {}, None


def score_match(source_task_id: str, source_top_goal: str, source_confirmed_hash: str):
    if source_task_id == task_id and source_confirmed_hash == confirmed_hash and confirmed_hash:
        return 3, "exact"
    if source_top_goal == top_goal and top_goal:
        return 2, "compatible"
    return 0, ""


def best_manifest_candidate(current_runtime_id: str):
    best = None
    for candidate_path in sessions_root.glob("*/manifest.yaml"):
        candidate = parse_scalar_file(candidate_path)
        if not candidate:
            continue
        if candidate.get("workboard_path") == str(workboard):
            continue
        if current_runtime_id and candidate.get("runtime_session_id") == current_runtime_id:
            continue
        if candidate.get("canonical_path") != task_file:
            continue
        if candidate.get("own_record_present") != "1":
            continue
        score, match_strength = score_match(
            candidate.get("task_id", ""),
            candidate.get("top_goal", ""),
            candidate.get("confirmed_hash", ""),
        )
        if score == 0:
            continue
        ranked = {
            "source_session_handle": candidate.get("session_handle", ""),
            "source_runtime_session_id": candidate.get("runtime_session_id", ""),
            "source_workboard_path": candidate.get("workboard_path", ""),
            "source_plan": candidate.get("workboard_path", ""),
            "source_task_id": candidate.get("task_id", ""),
            "source_top_goal": candidate.get("top_goal", ""),
            "source_confirmed_hash": candidate.get("confirmed_hash", ""),
            "suggested_match_strength": match_strength,
            "continuity_authority": "redcap-owned-manifest",
            "score": score,
            "mtime": candidate_path.stat().st_mtime,
        }
        if best is None or (ranked["score"], ranked["mtime"]) > (best["score"], best["mtime"]):
            best = ranked
    return best


def manifest_import_payload(candidate):
    if not candidate:
        return None
    if not candidate.get("source_session_handle") or not candidate.get("import_root"):
        return None
    return {
        "source_session_handle": candidate.get("source_session_handle", ""),
        "source_runtime_session_id": candidate.get("source_runtime_session_id", ""),
        "source_workboard_path": candidate.get("source_workboard_path", ""),
        "source_plan": candidate.get("source_plan", ""),
        "source_task_id": candidate.get("source_task_id", ""),
        "source_top_goal": candidate.get("source_top_goal", ""),
        "source_confirmed_hash": candidate.get("source_confirmed_hash", ""),
        "imported_at": candidate.get("imported_at", ""),
        "import_root": candidate.get("import_root", ""),
    }


def import_match_strength(imported):
    if not imported:
        return ""
    score, match_strength = score_match(
        imported.get("source_task_id", ""),
        imported.get("source_top_goal", ""),
        imported.get("source_confirmed_hash", ""),
    )
    return match_strength if score else ""


existing_manifest = {}
existing_manifest_path = None
if runtime_session_id:
    existing_manifest = load_manifest_for_runtime(runtime_session_id)
    if existing_manifest:
        existing_manifest_path = manifest_path_for(runtime_session_id)
    if not existing_manifest:
        existing_manifest, existing_manifest_path = find_manifest_for_workboard(workboard)
        if existing_manifest and existing_manifest.get("runtime_session_id", "").strip() not in ("", runtime_session_id):
            existing_manifest = {}
            existing_manifest_path = None
    if not binding_key:
        binding_key = existing_manifest.get("session_binding_key", "").strip()
    if not runtime_host:
        runtime_host = existing_manifest.get("runtime_host", "").strip()

manifest_import = manifest_import_payload(existing_manifest)
imported = None
stale_import = None

if manifest_import:
    match_strength = import_match_strength(manifest_import)
    if match_strength:
        imported = dict(manifest_import)
        imported["imported_match_strength"] = match_strength
    else:
        stale_import = dict(manifest_import)
        stale_import["stale_import_reason"] = "task-metadata-mismatch"

own_record_present = has_own_record(session_dir)
candidate = None
continuity_authority = "redcap-owned-manifest"
state = "fresh-session"
next_action = ""
import_protocol = "no-compatible-source-detected"

if not runtime_session_id:
    continuity_authority = "degraded-no-runtime-manifest"
    import_protocol = "runtime-session-unavailable"
elif imported:
    state = "imported"
    import_protocol = "explicit-copy-preserve-source"
elif own_record_present:
    state = "self-recorded"
    import_protocol = "not-needed-current-session-has-own-record"
else:
    candidate = best_manifest_candidate(runtime_session_id)
    if candidate:
        state = "import-suggested"
        next_action = (
            "bash compass/tools/redcap-session-continuity.sh import "
            f"\"{candidate['source_plan']}\" \"{workboard}\" \"{task_file}\""
        )
        import_protocol = "explicit-only"

manifest_data = {
    "manifest_version": "1",
    "runtime_session_id": runtime_session_id,
    "session_handle": session_handle,
    "workboard_path": str(workboard),
    "session_dir": str(session_dir),
    "canonical_path": task_file,
    "task_id": task_id,
    "top_goal": top_goal,
    "confirmed_hash": confirmed_hash,
    "active_slice": active_slice,
    "runtime_host": runtime_host,
    "session_binding_key": binding_key,
    "continuity_state": state,
    "continuity_authority": continuity_authority,
    "own_record_present": "1" if own_record_present else "0",
    "source_session_handle": imported.get("source_session_handle", "") if imported else "",
    "source_runtime_session_id": imported.get("source_runtime_session_id", "") if imported else "",
    "source_workboard_path": imported.get("source_workboard_path", "") if imported else "",
    "source_plan": imported.get("source_plan", "") if imported else "",
    "source_task_id": imported.get("source_task_id", "") if imported else "",
    "source_top_goal": imported.get("source_top_goal", "") if imported else "",
    "source_confirmed_hash": imported.get("source_confirmed_hash", "") if imported else "",
    "imported_match_strength": imported.get("imported_match_strength", "") if imported else "",
    "imported_at": imported.get("imported_at", "") if imported else "",
    "import_root": imported.get("import_root", "") if imported else "",
    "suggested_source_session_handle": candidate.get("source_session_handle", "") if candidate else "",
    "suggested_source_runtime_session_id": candidate.get("source_runtime_session_id", "") if candidate else "",
    "suggested_source_workboard_path": candidate.get("source_workboard_path", "") if candidate else "",
    "suggested_source_plan": candidate.get("source_plan", "") if candidate else "",
    "suggested_source_task_id": candidate.get("source_task_id", "") if candidate else "",
    "suggested_source_top_goal": candidate.get("source_top_goal", "") if candidate else "",
    "suggested_source_confirmed_hash": candidate.get("source_confirmed_hash", "") if candidate else "",
    "suggested_match_strength": candidate.get("suggested_match_strength", "") if candidate else "",
    "stale_import_session_handle": stale_import.get("source_session_handle", "") if stale_import else "",
    "stale_import_root": stale_import.get("import_root", "") if stale_import else "",
    "stale_import_reason": stale_import.get("stale_import_reason", "") if stale_import else "",
    "import_protocol": import_protocol,
    "next_action": next_action,
    "last_synced_at": now_iso(),
}

provenance_import_root = manifest_data.get("import_root", "")
provenance_data = {
    "provenance_version": "1",
    "runtime_session_id": runtime_session_id,
    "session_handle": session_handle,
    "workboard_path": str(workboard),
    "files_dir": str(files_dir),
    "checkpoints_dir": str(checkpoints_dir),
    "import_root": provenance_import_root,
    "import_metadata_path": (
        str((session_dir / provenance_import_root / "metadata.json").resolve())
        if provenance_import_root
        else ""
    ),
    "source_session_handle": manifest_data.get("source_session_handle", ""),
    "source_runtime_session_id": manifest_data.get("source_runtime_session_id", ""),
    "source_workboard_path": manifest_data.get("source_workboard_path", ""),
    "source_plan": manifest_data.get("source_plan", ""),
    "source_task_id": manifest_data.get("source_task_id", ""),
    "source_confirmed_hash": manifest_data.get("source_confirmed_hash", ""),
    "recorded_at": manifest_data["last_synced_at"],
}

if runtime_session_id:
    manifest_path = manifest_path_for(runtime_session_id)
    provenance_path = provenance_path_for(runtime_session_id)
    previous_manifest = parse_scalar_file(manifest_path)
    write_scalar_file(manifest_path, manifest_data)
    write_scalar_file(provenance_path, provenance_data)

    audit_keys = (
        "continuity_state",
        "continuity_authority",
        "own_record_present",
        "source_session_handle",
        "source_runtime_session_id",
        "suggested_source_session_handle",
        "suggested_source_runtime_session_id",
        "stale_import_session_handle",
        "import_root",
    )
    if not previous_manifest or any(previous_manifest.get(key, "") != manifest_data.get(key, "") for key in audit_keys):
        append_jsonl(
            continuity_dir / "audit-log.jsonl",
            {
                "event": "sync",
                "recorded_at": manifest_data["last_synced_at"],
                "runtime_session_id": runtime_session_id,
                "session_handle": session_handle,
                "workboard_path": str(workboard),
                "task_id": task_id,
                "confirmed_hash": confirmed_hash,
                "continuity_state": state,
                "continuity_authority": continuity_authority,
                "source_session_handle": manifest_data.get("source_session_handle", ""),
                "source_runtime_session_id": manifest_data.get("source_runtime_session_id", ""),
                "suggested_source_session_handle": manifest_data.get("suggested_source_session_handle", ""),
                "suggested_source_runtime_session_id": manifest_data.get("suggested_source_runtime_session_id", ""),
                "import_root": manifest_data.get("import_root", ""),
            },
        )

block_lines = [
    marker_start,
    "## RedCap Session Mirror",
    f"- session_handle: {session_handle}",
    f"- runtime_session_id: {runtime_session_id or 'unknown'}",
    f"- session_binding_key: {binding_key or 'unknown'}",
    f"- task_id: {task_id}",
    f"- confirmed_hash: {confirmed_hash}",
    f"- continuity_authority: {continuity_authority}",
]

if state == "imported":
    block_lines.extend(
        [
            f"- continuity_state: {state}",
            f"- imported_match_strength: {manifest_data.get('imported_match_strength', '')}",
            f"- imported_from_session_handle: {manifest_data.get('source_session_handle', '')}",
            f"- imported_from_runtime_session_id: {manifest_data.get('source_runtime_session_id', '')}",
            f"- imported_from_plan: {manifest_data.get('source_plan', '')}",
            f"- imported_from_task_id: {manifest_data.get('source_task_id', '')}",
            f"- imported_from_confirmed_hash: {manifest_data.get('source_confirmed_hash', '')}",
            f"- imported_at: {manifest_data.get('imported_at', '')}",
            f"- import_root: {manifest_data.get('import_root', '')}",
            f"- import_protocol: {import_protocol}",
        ]
    )
elif state == "self-recorded":
    block_lines.extend(
        [
            f"- continuity_state: {state}",
            f"- import_protocol: {import_protocol}",
        ]
    )
elif state == "import-suggested":
    block_lines.extend(
        [
            f"- continuity_state: {state}",
            f"- suggested_source_session_handle: {manifest_data.get('suggested_source_session_handle', '')}",
            f"- suggested_source_runtime_session_id: {manifest_data.get('suggested_source_runtime_session_id', '')}",
            f"- suggested_source_plan: {manifest_data.get('suggested_source_plan', '')}",
            f"- suggested_match_strength: {manifest_data.get('suggested_match_strength', '')}",
            f"- suggested_source_task_id: {manifest_data.get('suggested_source_task_id', '')}",
            f"- suggested_source_top_goal: {manifest_data.get('suggested_source_top_goal', '')}",
            f"- suggested_source_confirmed_hash: {manifest_data.get('suggested_source_confirmed_hash', '')}",
            f"- import_protocol: {import_protocol}",
            f"- next_action: {next_action}",
        ]
    )
else:
    block_lines.extend(
        [
            f"- continuity_state: {state}",
            f"- import_protocol: {import_protocol}",
        ]
    )

if stale_import:
    block_lines.extend(
        [
            f"- stale_import_session_handle: {manifest_data.get('stale_import_session_handle', '')}",
            f"- stale_import_root: {manifest_data.get('stale_import_root', '')}",
            f"- stale_import_reason: {manifest_data.get('stale_import_reason', '')}",
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
    new_text = text + suffix + "\n\n" + block + "\n"

workboard.write_text(new_text, encoding="utf-8")
print(state)
PY
}

import_session_assets() {
    local source_workboard="$1"
    local target_workboard="$2"
    local task_file="$3"
    local runtime_session_id binding_key runtime_host

    if [[ ! -f "$source_workboard" ]]; then
        echo "[redcap-session-continuity] source workboard not found: $source_workboard" >&2
        exit 1
    fi
    if [[ ! -f "$target_workboard" ]]; then
        echo "[redcap-session-continuity] target workboard not found: $target_workboard" >&2
        exit 1
    fi

    runtime_session_id="${REDCAP_RUNTIME_SESSION_ID:-}"
    binding_key="${REDCAP_RUNTIME_BINDING_KEY:-${REDCAP_SESSION_BINDING_KEY:-}}"
    runtime_host="${REDCAP_RUNTIME_HOST:-}"

    python3 - "$source_workboard" "$target_workboard" "$task_file" "$runtime_session_id" "$binding_key" "$runtime_host" <<'PY'
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

source_workboard = Path(sys.argv[1]).resolve()
target_workboard = Path(sys.argv[2]).resolve()
task_file = str(Path(sys.argv[3]).resolve())
target_runtime_session_id = sys.argv[4].strip()
target_binding_key = sys.argv[5].strip()
runtime_host = sys.argv[6].strip()

repo_root = Path(task_file).resolve().parent
continuity_root = Path(
    os.environ.get("REDCAP_CONTINUITY_ROOT_DIR") or (repo_root / "compass" / ".runtime")
).resolve()
sessions_root = continuity_root / "sessions"
continuity_dir = continuity_root / "continuity"

source_dir = source_workboard.parent
target_dir = target_workboard.parent
source_handle = source_dir.name
target_handle = target_dir.name

if source_dir == target_dir:
    raise SystemExit("[redcap-session-continuity] source and target session must differ")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def decode_scalar(raw):
    raw = raw.strip()
    if not raw:
        return ""
    try:
        value = json.loads(raw)
    except Exception:
        return raw
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else str(value)


def parse_scalar_file(path: Path):
    if not path.exists():
        return {}
    data = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = decode_scalar(value)
    return data


def write_scalar_file(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for key, value in data.items():
        normalized = "" if value is None else str(value)
        lines.append(f"{key}: {json.dumps(normalized, ensure_ascii=False)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_marker_block(plan_path: Path, start_marker: str, end_marker: str):
    try:
        text = plan_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    match = re.search(re.escape(start_marker) + r"(.*?)" + re.escape(end_marker), text, re.S)
    if not match:
        return {}
    data = {}
    for raw in match.group(1).splitlines():
        line = raw.strip()
        if line.startswith("- ") and ":" in line:
            key, value = line[2:].split(":", 1)
            data[key.strip()] = value.strip()
    return data


def parse_pointer(plan_path: Path):
    return parse_marker_block(
        plan_path,
        "<!-- redcap:canonical-pointer:start -->",
        "<!-- redcap:canonical-pointer:end -->",
    )


def parse_session_mirror(plan_path: Path):
    return parse_marker_block(
        plan_path,
        "<!-- redcap:session-mirror:start -->",
        "<!-- redcap:session-mirror:end -->",
    )


def find_manifest_for_workboard(target: Path):
    for candidate in sessions_root.glob("*/manifest.yaml"):
        data = parse_scalar_file(candidate)
        if data.get("workboard_path") == str(target):
            return data
    return {}


def has_own_record(path: Path):
    candidate_files = path / "files"
    candidate_checkpoints = path / "checkpoints"
    if candidate_files.exists():
        for candidate in candidate_files.rglob("*"):
            if not candidate.is_file():
                continue
            if "imported-sessions" in candidate.parts:
                continue
            return True
    if candidate_checkpoints.exists():
        for candidate in candidate_checkpoints.rglob("*"):
            if candidate.is_file():
                return True
    return False


def score_match(target_task_id: str, target_top_goal: str, target_confirmed_hash: str):
    if metadata["source_task_id"] == target_task_id and metadata["source_confirmed_hash"] == target_confirmed_hash and target_confirmed_hash:
        return "exact"
    if metadata["source_top_goal"] == target_top_goal and target_top_goal:
        return "compatible"
    return ""


def manifest_path_for(session_id: str):
    return sessions_root / session_id / "manifest.yaml"


def provenance_path_for(session_id: str):
    return sessions_root / session_id / "provenance.yaml"


def append_jsonl(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


source_pointer = parse_pointer(source_workboard)
source_mirror = parse_session_mirror(source_workboard)
source_manifest = find_manifest_for_workboard(source_workboard)
target_manifest = find_manifest_for_workboard(target_workboard)
target_pointer = parse_pointer(target_workboard)
if not target_binding_key:
    target_binding_key = target_manifest.get("session_binding_key", "").strip()
if not runtime_host:
    runtime_host = target_manifest.get("runtime_host", "").strip()
if not target_runtime_session_id:
    raise SystemExit("[redcap-session-continuity] target runtime session missing; run session-start sync before import")
if target_manifest.get("runtime_session_id", "").strip() not in ("", target_runtime_session_id):
    raise SystemExit("[redcap-session-continuity] target runtime session mismatch; refuse import")

dest_root = target_dir / "files" / "imported-sessions" / source_handle
created = False
if not dest_root.exists():
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
    created = True

metadata = {
    "source_session_handle": source_handle,
    "source_runtime_session_id": source_manifest.get("runtime_session_id", source_mirror.get("runtime_session_id", "")),
    "source_workboard_path": str(source_workboard),
    "source_plan": str(source_workboard),
    "source_task_id": source_pointer.get("task_id", ""),
    "source_top_goal": source_pointer.get("top_goal", ""),
    "source_confirmed_hash": source_pointer.get("confirmed_hash", ""),
    "imported_at": now_iso(),
    "import_root": str(dest_root.relative_to(target_dir)),
    "target_session_handle": target_handle,
    "target_runtime_session_id": target_runtime_session_id,
    "target_workboard_path": str(target_workboard),
    "target_binding_key": target_binding_key,
    "runtime_host": runtime_host,
}

metadata_path = dest_root / "metadata.json"
metadata_path.write_text(
    json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
    encoding="utf-8",
)

should_record_registry = created
existing_import_root = target_manifest.get("import_root", "")
if not should_record_registry and existing_import_root != metadata["import_root"]:
    should_record_registry = True

if should_record_registry:
    append_jsonl(
        continuity_dir / "import-registry.jsonl",
        {
            "event": "import" if created else "import-adopt-existing-root",
            "imported_at": metadata["imported_at"],
            "runtime_host": runtime_host,
            "target_runtime_session_id": target_runtime_session_id,
            "target_session_handle": target_handle,
            "target_workboard_path": str(target_workboard),
            "target_binding_key": target_binding_key,
            "source_runtime_session_id": metadata["source_runtime_session_id"],
            "source_session_handle": source_handle,
            "source_workboard_path": str(source_workboard),
            "source_task_id": metadata["source_task_id"],
            "source_top_goal": metadata["source_top_goal"],
            "source_confirmed_hash": metadata["source_confirmed_hash"],
            "import_root": metadata["import_root"],
        },
    )
    append_jsonl(
        continuity_dir / "audit-log.jsonl",
        {
            "event": "import",
            "recorded_at": metadata["imported_at"],
            "runtime_host": runtime_host,
            "target_runtime_session_id": target_runtime_session_id,
            "target_session_handle": target_handle,
            "source_runtime_session_id": metadata["source_runtime_session_id"],
            "source_session_handle": source_handle,
            "import_root": metadata["import_root"],
        },
    )

target_task_id = target_pointer.get("task_id", target_manifest.get("task_id", ""))
target_top_goal = target_pointer.get("top_goal", target_manifest.get("top_goal", ""))
target_confirmed_hash = target_pointer.get("confirmed_hash", target_manifest.get("confirmed_hash", ""))
target_active_slice = target_pointer.get("active_slice", target_manifest.get("active_slice", ""))
target_own_record = has_own_record(target_dir)
imported_match_strength = score_match(target_task_id, target_top_goal, target_confirmed_hash)
recorded_at = metadata["imported_at"]

manifest_data = {
    "manifest_version": "1",
    "runtime_session_id": target_runtime_session_id,
    "session_handle": target_handle,
    "workboard_path": str(target_workboard),
    "session_dir": str(target_dir),
    "canonical_path": task_file,
    "task_id": target_task_id,
    "top_goal": target_top_goal,
    "confirmed_hash": target_confirmed_hash,
    "active_slice": target_active_slice,
    "runtime_host": runtime_host,
    "session_binding_key": target_binding_key,
    "continuity_state": "imported",
    "continuity_authority": "redcap-owned-manifest",
    "own_record_present": "1" if target_own_record else "0",
    "source_session_handle": metadata["source_session_handle"],
    "source_runtime_session_id": metadata["source_runtime_session_id"],
    "source_workboard_path": metadata["source_workboard_path"],
    "source_plan": metadata["source_plan"],
    "source_task_id": metadata["source_task_id"],
    "source_top_goal": metadata["source_top_goal"],
    "source_confirmed_hash": metadata["source_confirmed_hash"],
    "imported_match_strength": imported_match_strength,
    "imported_at": metadata["imported_at"],
    "import_root": metadata["import_root"],
    "suggested_source_session_handle": "",
    "suggested_source_runtime_session_id": "",
    "suggested_source_workboard_path": "",
    "suggested_source_plan": "",
    "suggested_source_task_id": "",
    "suggested_source_top_goal": "",
    "suggested_source_confirmed_hash": "",
    "suggested_match_strength": "",
    "stale_import_session_handle": "",
    "stale_import_root": "",
    "stale_import_reason": "",
    "import_protocol": "explicit-copy-preserve-source",
    "next_action": "",
    "last_synced_at": recorded_at,
}
write_scalar_file(manifest_path_for(target_runtime_session_id), manifest_data)

provenance_data = {
    "provenance_version": "1",
    "runtime_session_id": target_runtime_session_id,
    "session_handle": target_handle,
    "workboard_path": str(target_workboard),
    "files_dir": str(target_dir / "files"),
    "checkpoints_dir": str(target_dir / "checkpoints"),
    "import_root": metadata["import_root"],
    "import_metadata_path": str(metadata_path.resolve()),
    "source_session_handle": metadata["source_session_handle"],
    "source_runtime_session_id": metadata["source_runtime_session_id"],
    "source_workboard_path": metadata["source_workboard_path"],
    "source_plan": metadata["source_plan"],
    "source_task_id": metadata["source_task_id"],
    "source_confirmed_hash": metadata["source_confirmed_hash"],
    "recorded_at": recorded_at,
}
write_scalar_file(provenance_path_for(target_runtime_session_id), provenance_data)

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

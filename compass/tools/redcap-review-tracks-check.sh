#!/usr/bin/env bash
# Validate the architecture/governance/contracts review-track registry and consumers.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REGISTRY_PATH="${1:-$REDCAP_ROOT/references/review-tracks.json}"

python3 - "$REDCAP_ROOT" "$REGISTRY_PATH" <<'PY'
from pathlib import Path
import json
import sys

root = Path(sys.argv[1])
registry_path = Path(sys.argv[2])


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-review-tracks-check] {message}")


def exists(rel: str) -> bool:
    path = Path(rel)
    return path.exists() if path.is_absolute() else (root / path).exists()


if not registry_path.is_file():
    fail(f"missing registry: {registry_path}")
try:
    data = json.loads(registry_path.read_text(encoding="utf-8"))
except json.JSONDecodeError as exc:
    fail(f"invalid review tracks json: {exc}")

if data.get("version") != 1:
    fail("version must be 1")
tracks = data.get("tracks")
if not isinstance(tracks, list) or len(tracks) != 3:
    fail("tracks must contain exactly architecture/governance/contracts")

required = {"architecture", "governance", "contracts"}
seen = set()
for track in tracks:
    if not isinstance(track, dict):
        fail("track entries must be objects")
    tid = track.get("id")
    if tid not in required:
        fail(f"unexpected track id: {tid}")
    if tid in seen:
        fail(f"duplicate track id: {tid}")
    seen.add(tid)
    for key in ("label", "purpose"):
        if not isinstance(track.get(key), str) or len(track[key].strip()) < 4:
            fail(f"{tid}: missing {key}")
    for key in ("must_check", "primary_sources"):
        values = track.get(key)
        if not isinstance(values, list) or len(values) < 3:
            fail(f"{tid}: {key} must contain at least 3 entries")
    for source in track["primary_sources"]:
        if not isinstance(source, str) or not exists(source):
            fail(f"{tid}: missing primary source: {source}")

if seen != required:
    fail("missing required tracks: " + ", ".join(sorted(required - seen)))

stop_review = (root / "compass/tools/redcap-on-stop-review.sh").read_text(encoding="utf-8", errors="replace")
if "references/review-tracks.json" not in stop_review or "三轨评审定义" not in stop_review:
    fail("stop-review prompt must consume review-tracks registry")
for required_phrase in ("track_verdicts", "architecture", "governance", "contracts"):
    if required_phrase not in stop_review:
        fail(f"stop-review prompt must require per-track review output: {required_phrase}")

checklist = (root / "references/governance-review-checklist.md").read_text(encoding="utf-8", errors="replace")
if "references/review-tracks.json" not in checklist:
    fail("governance checklist must point to review-tracks registry")

print("REVIEW_TRACKS_OK")
PY

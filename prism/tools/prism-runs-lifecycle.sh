#!/usr/bin/env bash
# prism-runs-lifecycle.sh — classify prism/runs evidence and prune only the safe acceptance set.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

COMMAND="${1:-summary}"
shift || true

APPLY=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=true; shift ;;
    *)
      echo "[prism-runs-lifecycle] unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

python3 - "$REDCAP_ROOT" "$COMMAND" "$APPLY" <<'PY'
from __future__ import annotations

import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

root = Path(sys.argv[1])
command = sys.argv[2]
apply = sys.argv[3] == "true"
runs_root = root / "prism" / "runs"
reports_root = root / "prism" / "reports"


def fail(message: str) -> None:
    raise SystemExit(f"[prism-runs-lifecycle] {message}")


def report_bound_run_ids() -> set[str]:
    ids: set[str] = set()
    if not reports_root.exists():
        return ids
    pattern = re.compile(r"\*\*运行 ID\*\*：\s*([A-Za-z0-9._-]+)")
    for path in reports_root.glob("*.md"):
        text = path.read_text(encoding="utf-8", errors="replace")
        match = pattern.search(text)
        if match:
            ids.add(match.group(1))
    return ids


def registry_statuses(path: Path) -> list[str]:
    if not path.is_file():
        return []
    statuses: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"^\s+status:\s*\"?([A-Za-z_-]+)\"?\s*$", raw)
        if match:
            statuses.append(match.group(1))
    return statuses


def classify_runs() -> list[dict[str, object]]:
    if not runs_root.exists():
        return []
    bound_ids = report_bound_run_ids()
    rows: list[dict[str, object]] = []
    for path in sorted(p for p in runs_root.iterdir() if p.is_dir()):
        name = path.name
        registry = path / "session-registry.yaml"
        statuses = registry_statuses(registry)
        active = any(status == "dispatched" for status in statuses)
        report_bound = name in bound_ids

        if name == ".locks":
            lifecycle_class = "infra-locks"
            retention = "preserve"
            cleanup_eligible = False
            reason = "internal lock directory"
        elif name.startswith("acceptance-prism-"):
            lifecycle_class = "acceptance-fixture"
            retention = "ephemeral-local"
            cleanup_eligible = not active and not report_bound
            reason = "acceptance fixture run; safe cleanup set only after run is no longer active"
        elif re.match(r"^20\d{6}-", name):
            lifecycle_class = "formal-run"
            retention = "preserve"
            cleanup_eligible = False
            reason = "formal Prism run evidence should be preserved by default"
        else:
            lifecycle_class = "named-local-evidence"
            retention = "preserve"
            cleanup_eligible = False
            reason = "named/debug/manual local evidence; preserve by default"

        rows.append(
            {
                "run_id": name,
                "path": str(path),
                "class": lifecycle_class,
                "retention": retention,
                "cleanup_eligible": cleanup_eligible,
                "active": active,
                "report_bound": report_bound,
                "statuses": statuses,
                "reason": reason,
            }
        )
    return rows


rows = classify_runs()

if command == "json":
    print(json.dumps({"runs": rows}, ensure_ascii=False, indent=2))
    raise SystemExit(0)

if command == "summary":
    counts = Counter(row["class"] for row in rows)
    purgeable = [row for row in rows if row["cleanup_eligible"]]
    print("PRISM_RUNS_LIFECYCLE_SUMMARY")
    print(f"total={len(rows)}")
    print(f"acceptance-fixture={counts.get('acceptance-fixture', 0)}")
    print(f"formal-run={counts.get('formal-run', 0)}")
    print(f"named-local-evidence={counts.get('named-local-evidence', 0)}")
    print(f"infra-locks={counts.get('infra-locks', 0)}")
    print(f"purgeable_acceptance={len(purgeable)}")
    if purgeable:
        preview = ",".join(str(row["run_id"]) for row in purgeable[:5])
        print(f"purge_preview={preview}")
    raise SystemExit(0)

if command == "check":
    if not rows:
        print("PRISM_RUNS_LIFECYCLE_OK")
        raise SystemExit(0)
    for row in rows:
        if row["class"] in {"formal-run", "named-local-evidence", "infra-locks"} and row["cleanup_eligible"]:
            fail(f"non-acceptance run marked purgeable: {row['run_id']}")
    print("PRISM_RUNS_LIFECYCLE_OK")
    raise SystemExit(0)

if command == "prune-acceptance":
    targets = [Path(str(row["path"])) for row in rows if row["cleanup_eligible"]]
    if not apply:
        print("PRISM_RUNS_PRUNE_PLAN")
        print(f"targets={len(targets)}")
        for path in targets:
            print(path)
        raise SystemExit(0)
    removed = 0
    for path in targets:
        shutil.rmtree(path)
        removed += 1
    print("PRISM_RUNS_PRUNE_OK")
    print(f"removed={removed}")
    raise SystemExit(0)

fail(f"unsupported command: {command}")
PY

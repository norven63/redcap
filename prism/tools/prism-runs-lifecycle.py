#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path


LOCAL_RETENTION_DAYS = int(os.environ.get("REDCAP_PRISM_LOCAL_RETENTION_DAYS", "7"))


def fail(message: str) -> int:
    print(f"[prism-runs-lifecycle] {message}", file=sys.stderr)
    return 1


def report_bound_run_ids(reports_root: Path) -> set[str]:
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


def age_days(path: Path) -> int:
    modified = datetime.fromtimestamp(path.stat().st_mtime).date()
    return max(0, (date.today() - modified).days)


def classify_runs(root: Path) -> list[dict[str, object]]:
    runs_root = root / "prism" / "runs"
    reports_root = root / "prism" / "reports"
    if not runs_root.exists():
        return []

    bound_ids = report_bound_run_ids(reports_root)
    rows: list[dict[str, object]] = []
    for path in sorted(p for p in runs_root.iterdir() if p.is_dir()):
        name = path.name
        registry = path / "session-registry.yaml"
        statuses = registry_statuses(registry)
        active = any(status == "dispatched" for status in statuses)
        report_bound = name in bound_ids
        row_age_days = age_days(path)
        cleanup_eligible = False
        local_prune_candidate = False

        if name == ".locks":
            lifecycle_class = "infra-locks"
            retention = "preserve"
            reason = "internal lock directory"
        elif name.startswith("acceptance-prism-"):
            lifecycle_class = "acceptance-fixture"
            retention = "ephemeral-local"
            cleanup_eligible = not active and not report_bound
            reason = "acceptance fixture run; safe cleanup set only after run is no longer active"
        elif re.match(r"^20\d{6}-", name):
            lifecycle_class = "formal-run"
            retention = "preserve"
            reason = "formal Prism run evidence should be preserved by default"
        else:
            lifecycle_class = "named-local-evidence"
            if active:
                retention = "preserve-active"
                reason = "local evidence still marked active"
            elif report_bound:
                retention = "preserve-bound"
                reason = "local evidence is referenced by a formal report"
            elif row_age_days >= LOCAL_RETENTION_DAYS:
                retention = f"review-and-prune>{LOCAL_RETENTION_DAYS}d"
                local_prune_candidate = True
                reason = "named/debug/manual local evidence exceeded retention threshold"
            else:
                retention = f"review-until>{LOCAL_RETENTION_DAYS}d"
                reason = "named/debug/manual local evidence still within retention threshold"

        rows.append(
            {
                "run_id": name,
                "path": str(path),
                "class": lifecycle_class,
                "retention": retention,
                "cleanup_eligible": cleanup_eligible,
                "local_prune_candidate": local_prune_candidate,
                "active": active,
                "report_bound": report_bound,
                "statuses": statuses,
                "age_days": row_age_days,
                "reason": reason,
            }
        )
    return rows


def main() -> int:
    root = Path(sys.argv[1])
    command = sys.argv[2]
    apply = sys.argv[3] == "true"
    rows = classify_runs(root)

    if command == "json":
        print(json.dumps({"runs": rows}, ensure_ascii=False, indent=2))
        return 0

    if command == "summary":
        counts = Counter(row["class"] for row in rows)
        purgeable = [row for row in rows if row["cleanup_eligible"]]
        pruneable_local = [row for row in rows if row["local_prune_candidate"]]
        print("PRISM_RUNS_LIFECYCLE_SUMMARY")
        print(f"total={len(rows)}")
        print(f"acceptance-fixture={counts.get('acceptance-fixture', 0)}")
        print(f"formal-run={counts.get('formal-run', 0)}")
        print(f"named-local-evidence={counts.get('named-local-evidence', 0)}")
        print(f"infra-locks={counts.get('infra-locks', 0)}")
        print(f"purgeable_acceptance={len(purgeable)}")
        print(f"pruneable_local={len(pruneable_local)} retention_days={LOCAL_RETENTION_DAYS}")
        if pruneable_local:
            preview = ",".join(str(row["run_id"]) for row in pruneable_local[:5])
            print(f"local_prune_preview={preview}")
        return 0

    if command == "inventory":
        print("PRISM_RUNS_LIFECYCLE_INVENTORY")
        print(f"retention_days={LOCAL_RETENTION_DAYS}")
        for row in rows:
            print(
                "\t".join(
                    [
                        f"run_id={row['run_id']}",
                        f"class={row['class']}",
                        f"age_days={row['age_days']}",
                        f"retention={row['retention']}",
                        f"active={str(row['active']).lower()}",
                        f"report_bound={str(row['report_bound']).lower()}",
                        f"acceptance_cleanup={str(row['cleanup_eligible']).lower()}",
                        f"local_prune_candidate={str(row['local_prune_candidate']).lower()}",
                    ]
                )
            )
        return 0

    if command == "check":
        for row in rows:
            if row["class"] in {"formal-run", "infra-locks"} and row["cleanup_eligible"]:
                return fail(f"immutable run marked acceptance-purgeable: {row['run_id']}")
            if row["local_prune_candidate"] and row["class"] != "named-local-evidence":
                return fail(f"non-local evidence marked local prune candidate: {row['run_id']}")
            if row["local_prune_candidate"] and row["active"]:
                return fail(f"active local evidence marked prune candidate: {row['run_id']}")
        print("PRISM_RUNS_LIFECYCLE_OK")
        return 0

    if command == "prune-acceptance":
        targets = [Path(str(row["path"])) for row in rows if row["cleanup_eligible"]]
        if not apply:
            print("PRISM_RUNS_PRUNE_PLAN")
            print(f"targets={len(targets)}")
            for path in targets:
                print(path)
            return 0
        for path in targets:
            shutil.rmtree(path)
        print("PRISM_RUNS_PRUNE_OK")
        print(f"removed={len(targets)}")
        return 0

    if command == "prune-local":
        targets = [Path(str(row["path"])) for row in rows if row["local_prune_candidate"]]
        if not apply:
            print("PRISM_RUNS_LOCAL_PRUNE_PLAN")
            print(f"targets={len(targets)} retention_days={LOCAL_RETENTION_DAYS}")
            for path in targets:
                print(path)
            return 0
        for path in targets:
            shutil.rmtree(path)
        print("PRISM_RUNS_LOCAL_PRUNE_OK")
        print(f"removed={len(targets)} retention_days={LOCAL_RETENTION_DAYS}")
        return 0

    return fail(f"unsupported command: {command}")


if __name__ == "__main__":
    sys.exit(main())

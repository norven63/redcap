#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


REDCAP_ROOT = Path(__file__).resolve().parent.parent.parent


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def section(text: str, heading_prefix: str) -> str:
    capture = False
    buffer: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            if capture:
                break
            if heading.startswith(heading_prefix):
                capture = True
                continue
        if capture:
            buffer.append(line)
    return "\n".join(buffer).strip()


def metadata(text: str) -> dict[str, str]:
    meta = section(text, "控制面元数据") or section(text, "Canonical Metadata")
    result: dict[str, str] = {}
    for line in meta.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def confirmed_hash(task_text: str) -> str:
    confirmed = section(task_text, "已确认需求")
    if not confirmed:
        return ""
    return hashlib.sha256(confirmed.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Bind a Prism acceptance run to the current Layer B task.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-file", default=str(REDCAP_ROOT / ".dev-task.md"))
    parser.add_argument("--resource-limited", action="store_true", help="Bind an explicit resource-limited Prism result without pretending it is formal quorum.")
    parser.add_argument("--resource-limited-evidence", help="JSON evidence file copied to artifacts/resource-limited.json when --resource-limited is used.")
    args = parser.parse_args()

    task_file = Path(args.task_file).resolve()
    if not task_file.is_file():
        raise SystemExit(f"task file missing: {task_file}")

    task_text = task_file.read_text(encoding="utf-8")
    meta = metadata(task_text)
    task_id = meta.get("task_id", "").strip()
    active_slice = meta.get("active_slice", "").strip()
    top_goal = meta.get("top_goal", "").strip()
    confirmed = confirmed_hash(task_text)
    if not task_id or not confirmed:
        raise SystemExit("task_id or confirmed_hash missing from .dev-task.md")

    repo_root = task_file.parent
    run_dir = repo_root / "prism" / "runs" / args.run_id
    registry = run_dir / "session-registry.yaml"
    if not registry.is_file():
        raise SystemExit(f"prism run registry missing: {registry}")

    binding_path = run_dir / "artifacts" / "acceptance-binding.json"
    binding_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": args.run_id,
        "task_id": task_id,
        "active_slice": active_slice,
        "top_goal": top_goal,
        "confirmed_hash": confirmed,
        "task_file": str(task_file),
        "source_of_truth": ".dev-task.md",
        "created_at": now_iso(),
    }
    if args.resource_limited:
        payload["resource_limited"] = True
        if not args.resource_limited_evidence:
            raise SystemExit("--resource-limited requires --resource-limited-evidence")
        evidence_source = Path(args.resource_limited_evidence).resolve()
        if not evidence_source.is_file():
            raise SystemExit(f"resource-limited evidence missing: {evidence_source}")
        evidence_target = binding_path.parent / "resource-limited.json"
        shutil.copyfile(evidence_source, evidence_target)
        payload["resource_limited_evidence"] = str(evidence_target)
    binding_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "binding_path": str(binding_path), "run_id": args.run_id, "task_id": task_id, "confirmed_hash": confirmed}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

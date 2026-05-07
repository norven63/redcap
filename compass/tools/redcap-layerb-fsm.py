#!/usr/bin/env python3
# 用途：运行时与收尾脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#runtime-and-closeout

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REDCAP_ROOT = Path(__file__).resolve().parent.parent.parent
PRISM_ACCEPTANCE_SCRIPT = REDCAP_ROOT / "compass/tools/redcap-prism-acceptance-check.sh"


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


def runtime_root(repo_root: Path) -> Path:
    project_hash = hashlib.md5(str(repo_root.resolve()).encode("utf-8")).hexdigest()
    return Path(os.environ.get("REDCAP_RUNTIME_PROJECT_BASE_DIR", "/tmp/redcap/project")) / project_hash / "governance" / "closeout-runtime"


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def acceptance_result(task_file: Path) -> dict[str, Any]:
    if not PRISM_ACCEPTANCE_SCRIPT.is_file():
        return {"status": "fail", "detail": f"missing script: {PRISM_ACCEPTANCE_SCRIPT}"}
    proc = subprocess.run(
        ["bash", str(PRISM_ACCEPTANCE_SCRIPT), "--task-file", str(task_file)],
        cwd=str(task_file.parent),
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except Exception:
        payload = {"status": "fail", "detail": proc.stdout.strip() or proc.stderr.strip() or "invalid acceptance payload"}
    payload.setdefault("status", "fail")
    payload["exit_code"] = proc.returncode
    return payload


def derive_state(active_slice: str, pending_exists: bool, receipt_exists: bool, closeout_status: str, acceptance_status: str) -> tuple[str, str]:
    planning_slices = {"planning", "plan", "work-plan", "design-plan", "proposal"}
    planning_review_slices = {"planning-review", "plan-review", "prism-planning-review", "plan-audit"}
    change_intake_slices = {"change-intake", "user-change-intake", "mid-task-change"}
    replan_review_slices = {"replan-review", "change-replan-review"}
    if pending_exists:
        return "BLOCKED", "pending closure exists"
    if receipt_exists:
        return "CLOSED", "closeout receipt present"
    if closeout_status == "blocked":
        return "BLOCKED", "closeout runtime blocked"
    if active_slice in change_intake_slices:
        return "CHANGE_INTAKE", "active slice indicates mid-task inserted requirement intake"
    if active_slice in replan_review_slices:
        return "REPLAN_REVIEW", "active slice indicates inserted requirement replan review"
    if acceptance_status == "fail":
        return "REVIEW_PENDING", "Prism acceptance missing or failed"
    if closeout_status in {"closeout-pending", "prepared"}:
        return "CLOSEOUT_PENDING", "closeout runtime started but receipt missing"
    if active_slice in {"task-complete", "report-and-closeout", "closeout-complete"}:
        return "CLOSEOUT_PENDING", "active slice indicates terminal closeout stage"
    if active_slice in planning_review_slices:
        return "PLANNING_REVIEW", "active slice indicates planning review gate"
    if active_slice in planning_slices:
        return "PLANNING", "active slice indicates planning stage"
    if active_slice in {"review", "review-pending", "stop-review"}:
        return "REVIEW_PENDING", "active slice indicates review gate"
    if active_slice:
        return "EXECUTING", f"active slice {active_slice}"
    return "TASK_LOCKED", "task exists but no explicit execution slice"


def build_payload(task_file: Path) -> dict[str, Any]:
    task_text = task_file.read_text(encoding="utf-8")
    meta = metadata(task_text)
    task_id = meta.get("task_id", "").strip()
    active_slice = meta.get("active_slice", "").strip()
    conf_hash = confirmed_hash(task_text)
    repo_root = task_file.parent.resolve()

    if not task_id or not conf_hash:
        raise SystemExit("task_id or confirmed_hash missing from .dev-task.md")

    identity = f"{task_id}-{conf_hash}"
    root = runtime_root(repo_root)
    state_payload = read_json(root / "state" / f"{identity}.json")
    promise_payload = read_json(root / "promise-ledger" / f"{identity}.json")
    receipt_exists = (root / "receipts" / f"{identity}.json").is_file()
    pending_exists = (Path(os.environ.get("REDCAP_RUNTIME_PROJECT_BASE_DIR", "/tmp/redcap/project")) / hashlib.md5(str(repo_root.resolve()).encode("utf-8")).hexdigest() / "governance" / "pending-closure" / f"{identity}.state").is_file()

    acceptance = acceptance_result(task_file)
    closeout_status = str(state_payload.get("status", "")).strip()
    lifecycle_state, reason = derive_state(
        active_slice=active_slice,
        pending_exists=pending_exists,
        receipt_exists=receipt_exists,
        closeout_status=closeout_status,
        acceptance_status=str(acceptance.get("status", "fail")).strip(),
    )

    return {
        "task_id": task_id,
        "confirmed_hash": conf_hash,
        "active_slice": active_slice,
        "lifecycle_state": lifecycle_state,
        "reason": reason,
        "acceptance": acceptance,
        "closeout": {
            "state": state_payload,
            "promise_completed": promise_payload.get("completed", 0),
            "promise_total": promise_payload.get("total", 0),
            "promise_pending": promise_payload.get("pending", 0),
            "receipt_exists": receipt_exists,
            "pending_closure_exists": pending_exists,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Show machine-readable Layer B FSM state for the current task.")
    parser.add_argument("--task-file", default=str(REDCAP_ROOT / ".dev-task.md"))
    args = parser.parse_args()

    task_file = Path(args.task_file).resolve()
    if not task_file.is_file():
        raise SystemExit(f"task file missing: {task_file}")

    payload = build_payload(task_file)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

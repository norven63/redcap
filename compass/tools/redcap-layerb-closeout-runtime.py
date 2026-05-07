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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REDCAP_ROOT = SCRIPT_DIR.parent.parent
BRIDGE_SCRIPT = Path(os.environ.get("REDCAP_LAYERB_CLOSEOUT_RUNTIME_BRIDGE", str(SCRIPT_DIR / "redcap-layerb-closeout-runtime-bridge.sh")))
ON_COMPLETE_SCRIPT = Path(os.environ.get("REDCAP_ON_COMPLETE_SCRIPT", str(SCRIPT_DIR / "redcap-on-complete.sh")))
SESSION_END_SCRIPT = Path(os.environ.get("REDCAP_LAYERB_SESSION_END_SCRIPT", str(SCRIPT_DIR / "redcap-layerB-session-end.sh")))
PRISM_ACCEPTANCE_SCRIPT = Path(os.environ.get("REDCAP_PRISM_ACCEPTANCE_SCRIPT", str(SCRIPT_DIR / "redcap-prism-acceptance-check.sh")))
EVOLUTION_CANDIDATE_SCRIPT = Path(
    os.environ.get("REDCAP_EVOLUTION_CANDIDATE_SCRIPT", str(SCRIPT_DIR / "redcap-evolution-candidate-check.sh"))
)
EVOLUTION_HARVEST_SCRIPT = Path(
    os.environ.get("REDCAP_EVOLUTION_HARVEST_SCRIPT", str(SCRIPT_DIR / "redcap-evolution-harvest-check.sh"))
)

RUNTIME_PROJECT_BASE = Path(os.environ.get("REDCAP_RUNTIME_PROJECT_BASE_DIR", "/tmp/redcap/project"))


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def normalize_repo_path(path: Path) -> Path:
    root = run_git(path, "rev-parse", "--show-toplevel")
    return Path(root).resolve() if root else path.resolve()


def project_hash(repo_root: Path) -> str:
    return hashlib.md5(str(repo_root).encode("utf-8")).hexdigest()


def runtime_project_dir(repo_root: Path) -> Path:
    return RUNTIME_PROJECT_BASE / project_hash(repo_root)


def governance_dir(repo_root: Path) -> Path:
    return runtime_project_dir(repo_root) / "governance"


def closeout_runtime_dir(repo_root: Path) -> Path:
    return governance_dir(repo_root) / "closeout-runtime"


def state_dir(repo_root: Path) -> Path:
    return closeout_runtime_dir(repo_root) / "state"


def receipt_dir(repo_root: Path) -> Path:
    return closeout_runtime_dir(repo_root) / "receipts"


def summary_dir(repo_root: Path) -> Path:
    return closeout_runtime_dir(repo_root) / "summaries"


def audit_dir(repo_root: Path) -> Path:
    return closeout_runtime_dir(repo_root) / "audits"


def promise_dir(repo_root: Path) -> Path:
    return closeout_runtime_dir(repo_root) / "promise-ledger"


def pending_dir(repo_root: Path) -> Path:
    return governance_dir(repo_root) / "pending-closure"


def ledger_dir(repo_root: Path) -> Path:
    return governance_dir(repo_root) / "closure-ledger"


def runtime_identity(task_id: str, confirmed_hash: str) -> str:
    safe_task = re.sub(r"[^A-Za-z0-9._-]+", "_", task_id).strip("._-") or "task"
    return f"{safe_task}-{confirmed_hash}"


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


def parse_checkbox_items(task_text: str, heading: str) -> list[dict[str, Any]]:
    body = section(task_text, heading)
    items: list[dict[str, Any]] = []
    for index, raw in enumerate(body.splitlines(), start=1):
        match = re.match(r"^-\s+\[([ xX])\]\s+(.*?)\s*$", raw.strip())
        if not match:
            continue
        items.append(
            {
                "id": f"promise-{index:02d}",
                "text": match.group(2).strip(),
                "done": match.group(1).lower() == "x",
            }
        )
    return items


def capture_report_items(report_path: Path, prefixes: list[str], limit: int = 2) -> list[str]:
    text = read_text(report_path)
    if not text:
        return []
    lines = text.splitlines()
    capture = False
    level = 0
    buffer: list[str] = []
    for line in lines:
        match = re.match(r"^(#+)\s*(.+?)\s*$", line)
        if match:
            heading_level = len(match.group(1))
            heading = match.group(2).strip()
            if capture and heading_level <= level:
                break
            if any(heading.startswith(prefix) for prefix in prefixes):
                capture = True
                level = heading_level
                continue
        if capture:
            buffer.append(line)
    items: list[str] = []
    for raw in buffer:
        line = raw.strip()
        if re.match(r"^[-*]\s+", line):
            item = re.sub(r"^[-*]\s+", "", line)
            item = re.sub(r"`([^`]*)`", r"\1", item)
            item = re.sub(r"\*\*(.*?)\*\*", r"\1", item)
            item = re.sub(r"^\w+\.\d+\s+", "", item)
            item = re.sub(r"\s+", " ", item).strip()
            if item:
                items.append(item)
        if len(items) >= limit:
            break
    return items


def parse_simple_fields(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for line in read_text(path).splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$", line)
        if match:
            data[match.group(1)] = match.group(2)
    return data


def parse_ledger_entries(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    content = read_text(path)
    if not content:
        return []
    parts = [part.strip() for part in content.split("---") if part.strip()]
    entries: list[dict[str, str]] = []
    for part in parts:
        fields = parse_simple_block(part)
        if "phase" in fields:
            entries.append(fields)
    return entries


def parse_simple_block(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


@dataclass
class TaskIdentity:
    repo_root: Path
    task_file: Path
    task_text: str
    meta: dict[str, str]
    task_id: str
    active_slice: str
    top_goal: str
    confirmed_hash: str
    report_path: Path | None
    identity_key: str


def resolve_task_file(raw: str | None) -> Path:
    if raw:
        path = Path(raw)
        return path if path.is_absolute() else (Path.cwd() / path)
    return REDCAP_ROOT / ".dev-task.md"


def load_identity(task_file: Path) -> TaskIdentity:
    task_text = read_text(task_file)
    if not task_text:
        raise SystemExit(f"task file not found or unreadable: {task_file}")
    meta = metadata(task_text)
    task_id = meta.get("task_id", "").strip()
    active_slice = meta.get("active_slice", "").strip()
    top_goal = meta.get("top_goal", "").strip()
    conf_hash = confirmed_hash(task_text)
    if not task_id or not conf_hash:
        raise SystemExit("task_id or confirmed_hash missing from .dev-task.md")
    repo_root = normalize_repo_path(task_file.parent)
    report_path: Path | None = None
    report_rel = meta.get("task_report", "").strip()
    if report_rel:
        candidate = (repo_root / report_rel).resolve()
        report_path = candidate
    identity_key = runtime_identity(task_id, conf_hash)
    return TaskIdentity(
        repo_root=repo_root,
        task_file=task_file.resolve(),
        task_text=task_text,
        meta=meta,
        task_id=task_id,
        active_slice=active_slice,
        top_goal=top_goal,
        confirmed_hash=conf_hash,
        report_path=report_path,
        identity_key=identity_key,
    )


def promise_ledger_path(identity: TaskIdentity) -> Path:
    return promise_dir(identity.repo_root) / f"{identity.identity_key}.json"


def closeout_state_path(identity: TaskIdentity) -> Path:
    return state_dir(identity.repo_root) / f"{identity.identity_key}.json"


def closeout_receipt_path(identity: TaskIdentity) -> Path:
    return receipt_dir(identity.repo_root) / f"{identity.identity_key}.json"


def closeout_summary_path(identity: TaskIdentity) -> Path:
    return summary_dir(identity.repo_root) / f"{identity.identity_key}.md"


def closeout_audit_path(identity: TaskIdentity, action: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_action = re.sub(r"[^A-Za-z0-9._-]+", "-", action).strip("-") or "audit"
    return audit_dir(identity.repo_root) / f"{timestamp}-{identity.identity_key}-{safe_action}.json"


def current_head(identity: TaskIdentity) -> str:
    return run_git(identity.repo_root, "rev-parse", "HEAD")


def initial_head(identity: TaskIdentity) -> str:
    path = runtime_project_dir(identity.repo_root) / "layerB" / "initial-head"
    return read_text(path).strip()


def pending_state_path(identity: TaskIdentity) -> Path:
    exact = pending_dir(identity.repo_root) / f"{identity.identity_key}.state"
    if exact.is_file():
        return exact
    matches = sorted(pending_dir(identity.repo_root).glob(f"{identity.task_id}-*.state"))
    return matches[-1] if matches else exact


def closure_ledger_path(identity: TaskIdentity) -> Path:
    return ledger_dir(identity.repo_root) / f"{identity.identity_key}.log"


def sync_promises(identity: TaskIdentity) -> dict[str, Any]:
    promises = parse_checkbox_items(identity.task_text, "执行承诺账本")
    payload = {
        "task_id": identity.task_id,
        "task_file": str(identity.task_file),
        "repo_root": str(identity.repo_root),
        "confirmed_hash": identity.confirmed_hash,
        "active_slice": identity.active_slice,
        "top_goal": identity.top_goal,
        "updated_at": now_iso(),
        "source": str(identity.task_file),
        "promises": promises,
        "total": len(promises),
        "pending": sum(1 for item in promises if not item["done"]),
        "completed": sum(1 for item in promises if item["done"]),
    }
    write_json(promise_ledger_path(identity), payload)
    return payload


def load_state(identity: TaskIdentity) -> dict[str, Any]:
    path = closeout_state_path(identity)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def update_state(identity: TaskIdentity, **fields: Any) -> dict[str, Any]:
    state = load_state(identity)
    state.update(
        {
            "task_id": identity.task_id,
            "confirmed_hash": identity.confirmed_hash,
            "active_slice": identity.active_slice,
            "repo_path": str(identity.repo_root),
            "task_file": str(identity.task_file),
            "report_path": str(identity.report_path) if identity.report_path else "",
            "updated_at": now_iso(),
        }
    )
    state.update(fields)
    write_json(closeout_state_path(identity), state)
    return state


def append_audit(identity: TaskIdentity, action: str, payload: dict[str, Any]) -> Path:
    path = closeout_audit_path(identity, action)
    base = {
        "action": action,
        "task_id": identity.task_id,
        "confirmed_hash": identity.confirmed_hash,
        "active_slice": identity.active_slice,
        "created_at": now_iso(),
    }
    base.update(payload)
    write_json(path, base)
    return path


def run_shell(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(command, cwd=str(REDCAP_ROOT), capture_output=True, text=True, env=merged_env, check=False)


def closeout_binding_key(identity: TaskIdentity, host: str) -> str:
    explicit = os.environ.get("REDCAP_SESSION_BINDING_KEY", "").strip()
    if explicit:
        return explicit
    runtime_binding = os.environ.get("REDCAP_RUNTIME_BINDING_KEY", "").strip()
    if runtime_binding:
        return runtime_binding
    host_session = os.environ.get("REDCAP_HOST_SESSION_ID", "").strip()
    if host_session:
        return f"host/{host}/session/{host_session}"
    return f"host/{host}/session/closeout/{identity.identity_key}"


def closeout_runtime_env(identity: TaskIdentity, host: str, baseline_head: str) -> tuple[dict[str, str], dict[str, Any]]:
    binding_key = closeout_binding_key(identity, host)
    host_pid = os.environ.get("REDCAP_HOST_PROCESS_PID", "").strip() or str(os.getpid())
    probe_pid = os.environ.get("REDCAP_HOST_PROCESS_PROBE_PID", "").strip() or host_pid
    env = {
        "REDCAP_SESSION_BINDING_KEY": binding_key,
        "REDCAP_HOST_PROCESS_PID": host_pid,
        "REDCAP_HOST_PROCESS_PROBE_PID": probe_pid,
        "REDCAP_ON_COMPLETE_HOST": host,
    }
    init = run_shell(
        [
            "bash",
            str(BRIDGE_SCRIPT),
            "ensure-runtime-binding",
            str(identity.repo_root),
            host,
            binding_key,
            baseline_head,
        ],
        env=env,
    )
    return env, {
        "binding_key": binding_key,
        "host_process_pid": host_pid,
        "host_process_probe_pid": probe_pid,
        "returncode": init.returncode,
        "stdout": init.stdout,
        "stderr": init.stderr,
    }


def prism_acceptance(identity: TaskIdentity) -> dict[str, Any]:
    if not PRISM_ACCEPTANCE_SCRIPT.is_file():
        return {"status": "fail", "detail": f"missing script: {PRISM_ACCEPTANCE_SCRIPT}"}
    completed = run_shell(["bash", str(PRISM_ACCEPTANCE_SCRIPT), "--task-file", str(identity.task_file)])
    try:
        payload = json.loads((completed.stdout or "").strip() or "{}")
    except Exception:
        payload = {"status": "fail", "detail": completed.stdout.strip() or completed.stderr.strip() or "invalid acceptance payload"}
    payload.setdefault("status", "fail")
    payload["exit_code"] = completed.returncode
    return payload


def evolution_candidates_strict(identity: TaskIdentity) -> dict[str, Any]:
    if not EVOLUTION_CANDIDATE_SCRIPT.is_file():
        return {"status": "fail", "detail": f"missing script: {EVOLUTION_CANDIDATE_SCRIPT}", "exit_code": 127}
    completed = run_shell(["bash", str(EVOLUTION_CANDIDATE_SCRIPT), "--strict"])
    detail = completed.stdout.strip() or completed.stderr.strip()
    return {
        "status": "pass" if completed.returncode == 0 else "fail",
        "detail": detail or ("strict evolution candidates passed" if completed.returncode == 0 else "strict evolution candidates failed"),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "exit_code": completed.returncode,
    }


def evolution_harvest(identity: TaskIdentity) -> dict[str, Any]:
    if not EVOLUTION_HARVEST_SCRIPT.is_file():
        return {"status": "fail", "detail": f"missing script: {EVOLUTION_HARVEST_SCRIPT}", "exit_code": 127}
    completed = run_shell(["bash", str(EVOLUTION_HARVEST_SCRIPT), str(identity.task_file)])
    detail = completed.stdout.strip() or completed.stderr.strip()
    return {
        "status": "pass" if completed.returncode == 0 else "fail",
        "detail": detail or ("evolution harvest passed" if completed.returncode == 0 else "evolution harvest failed"),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "exit_code": completed.returncode,
    }


def bridge_write_pending(
    identity: TaskIdentity,
    *,
    host: str,
    trigger: str,
    required_redlines: str,
    detail: str,
    artifact_path: str = "",
    baseline_head: str = "",
    audited_head: str = "",
    redline_mode: str = "merge",
) -> None:
    run_shell(
        [
            "bash",
            str(BRIDGE_SCRIPT),
            "write-pending",
            str(identity.repo_root),
            str(identity.task_file),
            host,
            trigger,
            required_redlines,
            detail,
            artifact_path,
            baseline_head,
            audited_head,
            redline_mode,
        ]
    )


def bridge_append_ledger(
    identity: TaskIdentity,
    *,
    phase: str,
    status: str,
    detail: str,
    host: str = "",
    trigger: str = "",
    baseline_head: str = "",
    current_head: str = "",
    artifact_path: str = "",
) -> None:
    run_shell(
        [
            "bash",
            str(BRIDGE_SCRIPT),
            "append-ledger",
            str(identity.repo_root),
            str(identity.task_file),
            phase,
            status,
            detail,
            host,
            trigger,
            baseline_head,
            current_head,
            artifact_path,
        ]
    )


def can_repair_receipt(
    identity: TaskIdentity,
    promise_info: dict[str, Any],
    harvest: dict[str, Any],
    evolution_candidates: dict[str, Any],
) -> tuple[bool, str]:
    if promise_info.get("pending", 0) > 0:
        return False, "promise-ledger pending"
    if harvest.get("status") == "fail":
        return False, f"evolution harvest unresolved: {harvest.get('detail', 'unknown reason')}"
    if evolution_candidates.get("status") == "fail":
        return False, f"evolution candidates unresolved: {evolution_candidates.get('detail', 'unknown reason')}"
    pending_state = pending_state_path(identity)
    if pending_state.is_file():
        return False, "pending-closure still exists"
    ledger_entries = parse_ledger_entries(closure_ledger_path(identity))
    if not ledger_entries:
        return False, "closure-ledger missing"
    for entry in reversed(ledger_entries):
        phase = entry.get("phase", "")
        status = entry.get("status", "")
        if phase not in {"session-end", "closeout-runtime"}:
            continue
        if status == "pass":
            return True, f"{phase} pass proven and no pending closure"
        return False, f"{phase} {status} blocks receipt repair"
    return False, "session-end/closeout-runtime pass not proven"


def build_summary(identity: TaskIdentity, promise_info: dict[str, Any], status: str, detail: str, acceptance: dict[str, Any] | None = None) -> str:
    report_path = identity.report_path if identity.report_path and identity.report_path.is_file() else None
    completed_items = capture_report_items(report_path, ["0.1 当前已完成"], 3) if report_path else []
    next_items = capture_report_items(report_path, ["0.3 下一步计划做的是"], 2) if report_path else []
    promise_lines: list[str] = []
    for item in promise_info.get("promises", []):
        mark = "x" if item.get("done") else " "
        promise_lines.append(f"- [{mark}] {item.get('text', '')}")
    if not promise_lines:
        promise_lines = ["- 无执行承诺账本条目"]

    lines = [
        f"# Layer B Closeout Summary: {identity.task_id}",
        "",
        f"- 状态：{status}",
        f"- 生成时间：{now_iso()}",
        f"- active_slice：{identity.active_slice or 'unknown'}",
        f"- confirmed_hash：`{identity.confirmed_hash}`",
        f"- 报告路径：{identity.meta.get('task_report', '(未声明)')}",
        f"- 承诺账本：{promise_info.get('completed', 0)}/{promise_info.get('total', 0)} 已完成",
        f"- 独立验收：{(acceptance or {}).get('status', 'unknown')}",
        "",
        "## 当前已完成",
    ]
    if completed_items:
        lines.extend(f"- {item}" for item in completed_items)
    else:
        lines.append("- 未从任务报告摘要中提取到“当前已完成”，请打开报告查看细节")
    lines.extend(
        [
            "",
            "## 执行承诺账本",
            *promise_lines,
            "",
            "## closeout runtime 说明",
            f"- detail：{detail}",
            "",
            "## 下一步",
        ]
    )
    if next_items:
        lines.extend(f"- {item}" for item in next_items)
    elif status == "completed":
        lines.append("- 当前任务已完成 closeout，无额外 runtime blocker")
    else:
        lines.append("- 当前任务仍需继续处理 blocker；详见 pending closure / closeout audit")
    return "\n".join(lines) + "\n"


def write_receipt(identity: TaskIdentity, promise_info: dict[str, Any], *, status: str, detail: str, host: str, baseline_head: str, current: str, repaired: bool = False, acceptance: dict[str, Any] | None = None) -> tuple[Path, Path]:
    summary_content = build_summary(identity, promise_info, status, detail, acceptance=acceptance)
    summary_path = write_text(closeout_summary_path(identity), summary_content)
    receipt_payload = {
        "task_id": identity.task_id,
        "confirmed_hash": identity.confirmed_hash,
        "active_slice": identity.active_slice,
        "repo_path": str(identity.repo_root),
        "task_file": str(identity.task_file),
        "report_path": str(identity.report_path) if identity.report_path else "",
        "status": status,
        "detail": detail,
        "host": host,
        "baseline_head": baseline_head,
        "current_head": current,
        "promise_completed": promise_info.get("completed", 0),
        "promise_total": promise_info.get("total", 0),
        "promise_pending": promise_info.get("pending", 0),
        "acceptance_status": (acceptance or {}).get("status", "unknown"),
        "acceptance_detail": (acceptance or {}).get("detail", ""),
        "acceptance_run": (acceptance or {}).get("run_id", ""),
        "summary_path": str(summary_path),
        "repaired": repaired,
        "created_at": now_iso(),
    }
    receipt_path = write_json(closeout_receipt_path(identity), receipt_payload)
    return summary_path, receipt_path


def command_sync_promises(args: argparse.Namespace) -> int:
    identity = load_identity(resolve_task_file(args.task_file))
    promise_info = sync_promises(identity)
    existing_state = load_state(identity)
    receipt_exists = closeout_receipt_path(identity).is_file()
    current_status = str(existing_state.get("status", "")).strip()
    next_status = current_status or "prepared"
    next_result = str(existing_state.get("last_result", "")).strip()

    # sync-promises only refreshes the derived ledger; it must not silently
    # downgrade a terminal/blocked lifecycle back to "prepared".
    if receipt_exists:
        next_status = "completed"
        if not next_result:
            next_result = "receipt-present"

    state = update_state(
        identity,
        status=next_status,
        last_command="sync-promises",
        last_result=next_result,
        promises_total=promise_info["total"],
        promises_pending=promise_info["pending"],
    )
    emit({"status": "ok", "promise_ledger": promise_info, "state": state})
    return 0


def command_status(args: argparse.Namespace) -> int:
    identity = load_identity(resolve_task_file(args.task_file))
    promise_info = sync_promises(identity)
    acceptance = prism_acceptance(identity)
    harvest = evolution_harvest(identity)
    evolution_candidates = evolution_candidates_strict(identity)
    receipt_path = closeout_receipt_path(identity)
    state = load_state(identity)
    payload = {
        "task_id": identity.task_id,
        "task_file": str(identity.task_file),
        "repo_root": str(identity.repo_root),
        "confirmed_hash": identity.confirmed_hash,
        "active_slice": identity.active_slice,
        "promise_total": promise_info["total"],
        "promise_pending": promise_info["pending"],
        "pending_closure_exists": pending_state_path(identity).is_file(),
        "receipt_exists": receipt_path.is_file(),
        "state": state,
        "acceptance": acceptance,
        "evolution_harvest": harvest,
        "evolution_candidates": evolution_candidates,
    }
    emit(payload)
    return 0


def command_complete(args: argparse.Namespace) -> int:
    identity = load_identity(resolve_task_file(args.task_file))
    promise_info = sync_promises(identity)
    harvest = evolution_harvest(identity)
    evolution_candidates = evolution_candidates_strict(identity)
    acceptance = prism_acceptance(identity)
    host = args.host
    baseline_head = args.baseline_head or initial_head(identity) or current_head(identity)
    current = current_head(identity)
    report_rel = identity.meta.get("task_report", "")

    update_state(
        identity,
        status="closeout-pending",
        last_command="complete",
        promises_total=promise_info["total"],
        promises_pending=promise_info["pending"],
        baseline_head=baseline_head,
        current_head=current,
    )

    if promise_info["pending"] > 0:
        detail = "promise ledger contains unresolved commitments"
        bridge_write_pending(
            identity,
            host=host,
            trigger="layerb-closeout-runtime",
            required_redlines="promise-ledger,closeout-runtime",
            detail=detail,
            artifact_path=report_rel,
            baseline_head=baseline_head,
            audited_head=current,
        )
        bridge_append_ledger(
            identity,
            phase="closeout-runtime",
            status="blocked",
            detail=detail,
            host=host,
            trigger="complete",
            baseline_head=baseline_head,
            current_head=current,
            artifact_path=report_rel,
        )
        audit_path = append_audit(
            identity,
            "promise-ledger-blocked",
            {
                "detail": detail,
                "pending_promises": [item["text"] for item in promise_info["promises"] if not item["done"]],
            },
        )
        state = update_state(identity, status="blocked", last_result="promise-ledger-pending", audit_path=str(audit_path))
        emit({"status": "blocked", "reason": detail, "audit_path": str(audit_path), "state": state})
        return 1

    if harvest.get("status") == "fail":
        detail = f"evolution harvest unresolved: {harvest.get('detail', 'unknown reason')}"
        bridge_write_pending(
            identity,
            host=host,
            trigger="layerb-closeout-runtime-evolution-harvest",
            required_redlines="evolution-harvest,closeout-runtime",
            detail=detail,
            artifact_path=report_rel,
            baseline_head=baseline_head,
            audited_head=current,
        )
        bridge_append_ledger(
            identity,
            phase="closeout-runtime",
            status="blocked",
            detail=detail,
            host=host,
            trigger="complete",
            baseline_head=baseline_head,
            current_head=current,
            artifact_path=report_rel,
        )
        audit_path = append_audit(
            identity,
            "evolution-harvest-blocked",
            {
                "detail": detail,
                "evolution_harvest": harvest,
            },
        )
        state = update_state(identity, status="blocked", last_result="evolution-harvest-unresolved", audit_path=str(audit_path))
        emit(
            {
                "status": "blocked",
                "reason": detail,
                "audit_path": str(audit_path),
                "state": state,
                "evolution_harvest": harvest,
            }
        )
        return 1

    if evolution_candidates.get("status") == "fail":
        detail = f"evolution candidates unresolved: {evolution_candidates.get('detail', 'unknown reason')}"
        bridge_write_pending(
            identity,
            host=host,
            trigger="layerb-closeout-runtime-evolution-candidates",
            required_redlines="evolution-candidates,closeout-runtime",
            detail=detail,
            artifact_path=report_rel,
            baseline_head=baseline_head,
            audited_head=current,
        )
        bridge_append_ledger(
            identity,
            phase="closeout-runtime",
            status="blocked",
            detail=detail,
            host=host,
            trigger="complete",
            baseline_head=baseline_head,
            current_head=current,
            artifact_path=report_rel,
        )
        audit_path = append_audit(
            identity,
            "evolution-candidates-blocked",
            {
                "detail": detail,
                "evolution_candidates": evolution_candidates,
            },
        )
        state = update_state(identity, status="blocked", last_result="evolution-candidates-unresolved", audit_path=str(audit_path))
        emit(
            {
                "status": "blocked",
                "reason": detail,
                "audit_path": str(audit_path),
                "state": state,
                "evolution_candidates": evolution_candidates,
            }
        )
        return 1

    if acceptance.get("status") == "fail":
        detail = f"independent acceptance missing or failed: {acceptance.get('detail', 'unknown reason')}"
        bridge_write_pending(
            identity,
            host=host,
            trigger="layerb-closeout-runtime-prism-acceptance",
            required_redlines="prism-acceptance,closeout-runtime",
            detail=detail,
            artifact_path=report_rel,
            baseline_head=baseline_head,
            audited_head=current,
        )
        bridge_append_ledger(
            identity,
            phase="closeout-runtime",
            status="blocked",
            detail=detail,
            host=host,
            trigger="complete",
            baseline_head=baseline_head,
            current_head=current,
            artifact_path=report_rel,
        )
        audit_path = append_audit(
            identity,
            "prism-acceptance-blocked",
            {
                "detail": detail,
                "acceptance": acceptance,
            },
        )
        state = update_state(identity, status="blocked", last_result="prism-acceptance-missing", audit_path=str(audit_path))
        emit({"status": "blocked", "reason": detail, "audit_path": str(audit_path), "state": state, "acceptance": acceptance})
        return 1

    runtime_env, runtime_binding = closeout_runtime_env(identity, host, baseline_head)
    if runtime_binding["returncode"] != 0:
        detail = f"closeout runtime binding init failed with status={runtime_binding['returncode']}"
        bridge_write_pending(
            identity,
            host=host,
            trigger="layerb-closeout-runtime-binding",
            required_redlines="closeout-runtime",
            detail=detail,
            artifact_path=report_rel,
            baseline_head=baseline_head,
            audited_head=current,
        )
        bridge_append_ledger(
            identity,
            phase="closeout-runtime",
            status="blocked",
            detail=detail,
            host=host,
            trigger="complete",
            baseline_head=baseline_head,
            current_head=current,
            artifact_path=report_rel,
        )
        audit_path = append_audit(
            identity,
            "runtime-binding-failed",
            {
                "detail": detail,
                "runtime_binding": runtime_binding,
            },
        )
        state = update_state(identity, status="blocked", last_result="runtime-binding-failed", audit_path=str(audit_path))
        emit({"status": "blocked", "reason": detail, "audit_path": str(audit_path), "state": state})
        return 1

    on_complete = run_shell(["bash", str(ON_COMPLETE_SCRIPT), str(identity.repo_root), baseline_head, identity.repo_root.name], env=runtime_env)
    current = current_head(identity)
    if on_complete.returncode != 0:
        detail = f"redcap-on-complete failed with status={on_complete.returncode}"
        bridge_write_pending(
            identity,
            host=host,
            trigger="layerb-closeout-runtime-on-complete",
            required_redlines="closeout-runtime",
            detail=detail,
            artifact_path=report_rel,
            baseline_head=baseline_head,
            audited_head=current,
        )
        bridge_append_ledger(
            identity,
            phase="closeout-runtime",
            status="blocked",
            detail=detail,
            host=host,
            trigger="complete",
            baseline_head=baseline_head,
            current_head=current,
            artifact_path=report_rel,
        )
        audit_path = append_audit(
            identity,
            "on-complete-failed",
            {
                "detail": detail,
                "stdout": on_complete.stdout,
                "stderr": on_complete.stderr,
            },
        )
        state = update_state(identity, status="blocked", last_result="on-complete-failed", audit_path=str(audit_path))
        emit({"status": "blocked", "reason": detail, "audit_path": str(audit_path), "state": state})
        return 1

    session_end_env = dict(runtime_env)
    session_end_env["REDCAP_SKIP_SESSION_END_SUCCESS_NOTIFY"] = "1"
    session_end = run_shell(["bash", str(SESSION_END_SCRIPT), host], env=session_end_env)
    current = current_head(identity)
    if session_end.returncode != 0 or pending_state_path(identity).is_file():
        detail = (
            f"session-end unresolved (status={session_end.returncode}, pending_closure={'yes' if pending_state_path(identity).is_file() else 'no'})"
        )
        bridge_write_pending(
            identity,
            host=host,
            trigger="layerb-closeout-runtime-session-end",
            required_redlines="closeout-runtime",
            detail=detail,
            artifact_path=report_rel,
            baseline_head=baseline_head,
            audited_head=current,
        )
        bridge_append_ledger(
            identity,
            phase="closeout-runtime",
            status="blocked",
            detail=detail,
            host=host,
            trigger="complete",
            baseline_head=baseline_head,
            current_head=current,
            artifact_path=report_rel,
        )
        audit_path = append_audit(
            identity,
            "session-end-unresolved",
            {
                "detail": detail,
                "stdout": session_end.stdout,
                "stderr": session_end.stderr,
                "pending_state": str(pending_state_path(identity)) if pending_state_path(identity).is_file() else "",
            },
        )
        state = update_state(identity, status="blocked", last_result="session-end-unresolved", audit_path=str(audit_path))
        emit({"status": "blocked", "reason": detail, "audit_path": str(audit_path), "state": state})
        return 1

    summary_path, receipt_path = write_receipt(
        identity,
        promise_info,
        status="completed",
        detail="closeout runtime completed with on-complete + session-end",
        host=host,
        baseline_head=baseline_head,
        current=current,
        acceptance=acceptance,
    )
    bridge_append_ledger(
        identity,
        phase="closeout-runtime",
        status="pass",
        detail="receipt generated",
        host=host,
        trigger="complete",
        baseline_head=baseline_head,
        current_head=current,
        artifact_path=report_rel,
    )
    state = update_state(
        identity,
        status="completed",
        last_result="completed",
        baseline_head=baseline_head,
        current_head=current,
        receipt_path=str(receipt_path),
        summary_path=str(summary_path),
    )
    emit({"status": "completed", "receipt_path": str(receipt_path), "summary_path": str(summary_path), "state": state, "acceptance": acceptance})
    return 0


def command_audit_open(args: argparse.Namespace) -> int:
    identity = load_identity(resolve_task_file(args.task_file))
    promise_info = sync_promises(identity)
    harvest = evolution_harvest(identity)
    evolution_candidates = evolution_candidates_strict(identity)
    acceptance = prism_acceptance(identity)
    host = args.host
    baseline_head = args.baseline_head or initial_head(identity) or current_head(identity)
    current = current_head(identity)
    receipt_path = closeout_receipt_path(identity)
    report_rel = identity.meta.get("task_report", "")

    if receipt_path.is_file():
        state = update_state(identity, status="completed", last_command="audit-open", last_result="receipt-present")
        emit({"status": "clean", "reason": "receipt already exists", "state": state})
        return 0

    if acceptance.get("status") == "fail":
        repairable, reason = (False, f"independent acceptance missing or failed: {acceptance.get('detail', 'unknown reason')}")
    else:
        repairable, reason = can_repair_receipt(identity, promise_info, harvest, evolution_candidates)
    if repairable:
        summary_path, new_receipt = write_receipt(
            identity,
            promise_info,
            status="completed",
            detail=f"receipt repaired via audit-open ({args.mode})",
            host=host,
            baseline_head=baseline_head,
            current=current,
            repaired=True,
            acceptance=acceptance,
        )
        audit_path = append_audit(
            identity,
            "repair-receipt",
            {"mode": args.mode, "detail": reason, "receipt_path": str(new_receipt)},
        )
        bridge_append_ledger(
            identity,
            phase="closeout-runtime",
            status="pass",
            detail=f"receipt repaired via audit-open ({args.mode})",
            host=host,
            trigger="audit-open",
            baseline_head=baseline_head,
            current_head=current,
            artifact_path=report_rel,
        )
        state = update_state(
            identity,
            status="completed",
            last_command="audit-open",
            last_result="receipt-repaired",
            receipt_path=str(new_receipt),
            summary_path=str(summary_path),
            audit_path=str(audit_path),
        )
        emit({"status": "repaired", "receipt_path": str(new_receipt), "audit_path": str(audit_path), "state": state})
        return 0

    detail = f"audit-open could not repair receipt: {reason}"
    if promise_info["pending"] > 0:
        required_redlines = "promise-ledger,closeout-runtime"
    elif harvest.get("status") == "fail":
        required_redlines = "evolution-harvest,closeout-runtime"
    elif evolution_candidates.get("status") == "fail":
        required_redlines = "evolution-candidates,closeout-runtime"
    else:
        required_redlines = "closeout-runtime"
    bridge_write_pending(
        identity,
        host=host,
        trigger=f"layerb-closeout-runtime-audit-{args.mode}",
        required_redlines=required_redlines,
        detail=detail,
        artifact_path=report_rel,
        baseline_head=baseline_head,
        audited_head=current,
    )
    bridge_append_ledger(
        identity,
        phase="closeout-runtime",
        status="blocked",
        detail=detail,
        host=host,
        trigger="audit-open",
        baseline_head=baseline_head,
        current_head=current,
        artifact_path=report_rel,
    )
    audit_path = append_audit(
        identity,
        "block-and-audit",
        {"mode": args.mode, "detail": detail, "repairable_reason": reason},
    )
    state = update_state(identity, status="blocked", last_command="audit-open", last_result="blocked", audit_path=str(audit_path))
    emit({"status": "attention", "reason": detail, "audit_path": str(audit_path), "state": state})
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Layer B unified closeout runtime.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--task-file", default=str(REDCAP_ROOT / ".dev-task.md"))
        sub.add_argument("--host", default="codex")
        sub.add_argument("--baseline-head", default="")

    sync = subparsers.add_parser("sync-promises", help="Sync the execution promise ledger from .dev-task.md")
    sync.add_argument("--task-file", default=str(REDCAP_ROOT / ".dev-task.md"))
    sync.set_defaults(func=command_sync_promises)

    status = subparsers.add_parser("status", help="Show closeout runtime status")
    status.add_argument("--task-file", default=str(REDCAP_ROOT / ".dev-task.md"))
    status.set_defaults(func=command_status)

    complete = subparsers.add_parser("complete", help="Run unified Layer B closeout runtime")
    add_common(complete)
    complete.set_defaults(func=command_complete)

    audit_open = subparsers.add_parser("audit-open", help="Repair missing receipt or re-surface runtime blocker")
    add_common(audit_open)
    audit_open.add_argument("--mode", choices=("stop", "session-end", "diagnose"), default="diagnose")
    audit_open.set_defaults(func=command_audit_open)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

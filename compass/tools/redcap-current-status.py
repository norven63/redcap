#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import hashlib
from collections import Counter
from datetime import date, datetime
from pathlib import Path


LOCAL_EVIDENCE_RETENTION_DAYS = int(os.environ.get("REDCAP_PRISM_LOCAL_RETENTION_DAYS", "7"))


def run_git(repo: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


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


def closeout_runtime_identity(task_id: str, confirmed_hash: str) -> str:
    safe_task = re.sub(r"[^A-Za-z0-9._-]+", "_", task_id).strip("._-") or "task"
    return f"{safe_task}-{confirmed_hash}"


def metadata(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    meta = section(text, "控制面元数据") or section(text, "Canonical Metadata")
    for line in meta.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def state_fields(path: Path | None) -> dict[str, str]:
    if not path or not path.is_file():
        return {}
    result: dict[str, str] = {}
    for line in read(path).splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def capture_report_items(report_path: Path, prefixes: list[str], limit: int = 2) -> list[str]:
    text = read(report_path)
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
            item = re.sub(r"^(当前已完成|上一步完成的是|下一步计划做的是|整体计划脉络图是|当前所在位置)：", "", item)
            item = re.sub(r"\s+", " ", item).strip()
            if item:
                items.append(item)
        if len(items) >= limit:
            break
    return items


def load_backlog(repo: Path, meta: dict[str, str]) -> tuple[Path | None, dict]:
    rel = meta.get("backlog_source", "")
    if not rel:
        return None, {}
    path = Path(rel)
    if not path.is_absolute():
        path = repo / rel
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return path, {}


def backlog_summary(repo: Path, meta: dict[str, str]) -> list[str]:
    path, data = load_backlog(repo, meta)
    if not data:
        if path:
            return [f"backlog 读取失败：{path}"]
        return ["未绑定长期 backlog"]

    item_id = meta.get("backlog_item", "")
    current_focus = data.get("current_focus") or {}
    counts: Counter[str] = Counter()
    current_item = None
    for group in data.get("groups") or []:
        for item in group.get("items") or []:
            counts[str(item.get("status", "unknown"))] += 1
            if item.get("id") == item_id:
                current_item = item

    labels = {
        "done": "已完成",
        "in_progress": "进行中",
        "pending": "待推进",
        "blocked": "阻塞",
        "unknown": "未知",
    }
    count_text = " / ".join(f"{labels.get(k, k)}={v}" for k, v in sorted(counts.items()))
    lines = [
        f"当前焦点：{current_focus.get('item_id', 'unknown')} — {current_focus.get('summary', '无说明')}",
        f"条目计数：{count_text or '无条目'}",
    ]
    if current_item:
        lines.append(
            f"当前绑定条目：{current_item.get('id')} {current_item.get('title')}（{labels.get(current_item.get('status'), current_item.get('status'))}，{current_item.get('priority')}）"
        )
    elif item_id:
        lines.append(f"当前绑定条目：{item_id}（未在 backlog 中找到）")
    return lines


def progress_meter_summary(repo: Path, task_file: Path) -> list[str]:
    script = repo / "compass/tools/redcap-progress-meter.sh"
    if not script.is_file():
        return ["progress-meter: missing redcap-progress-meter.sh"]
    try:
        proc = subprocess.run(
            ["bash", str(script), "--task-file", str(task_file)],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return [f"progress-meter 无法运行：{exc}"]
    if proc.returncode != 0:
        detail = proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else "unknown error"
        return [f"progress-meter 失败：{detail}"]
    lines: list[str] = []
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if not line or line in {"REDCAP_PROGRESS_METER", "PROGRESS_METER_OK"}:
            continue
        if line.startswith("- "):
            line = line[2:].strip()
        lines.append(line)
    return lines or ["progress-meter: no output"]


def pending_validation_summary(repo: Path) -> str:
    path = repo / "loom/test-reports/pending-validations.md"
    text = read(path)
    active = section(text, "活跃条目")
    if not active:
        return "未找到活跃待验证条目（历史完整用户项目 E2E 队列为空）"
    entries = re.findall(r"^###\s+V-\d+:", active, flags=re.MULTILINE)
    waiting = len(re.findall(r"状态.*待验证", active))
    partial = len(re.findall(r"状态.*部分验证", active))
    return (
        f"活跃待验证 {len(entries)} 项，其中待验证 {waiting} 项、部分验证 {partial} 项；"
        "这是历史完整用户项目 E2E 验证队列，不计入当前 framework-upgrade backlog 完成度"
    )


def runtime_workspace_summary(repo: Path, task_file: Path) -> list[str]:
    runtime_root = os.environ.get("REDCAP_RUNTIME_ROOT") or str(repo)
    workspace_root = os.environ.get("REDCAP_WORKSPACE_ROOT") or str(task_file.parent)
    resolved_task_file = os.environ.get("REDCAP_TASK_FILE") or str(task_file)

    policy_path = repo / "references/user-agent-identity-policy.json"
    local_state = "compass/.workflow/user-agent-identity.json"
    identity_anchor = "~/.cap/identity.md"
    if policy_path.is_file():
        try:
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            local_state = str(policy.get("local_state_path") or local_state)
            identity_anchor = str(policy.get("identity_file") or identity_anchor)
        except Exception:
            pass

    task_exists = Path(resolved_task_file).is_file()
    relation = "same-root" if Path(runtime_root) == Path(workspace_root) else "external-workspace"
    return [
        f"runtime root: {runtime_root}",
        f"workspace root: {workspace_root}",
        f"task file: {resolved_task_file} ({'exists' if task_exists else 'missing'})",
        f"user state: {local_state}; private identity anchor: {identity_anchor}",
        f"boundary mode: {relation}；CLI 默认应以 workspace 为项目状态目录，runtime root 只提供工具实现",
    ]


def agent_registry_summary(repo: Path) -> list[str]:
    path = repo / "compass/.workflow/agent-registry.yaml"
    text = read(path)
    if not text:
        return ["未找到 agent-registry cache；需要时可运行 redcap-detect-agents.sh 做安装/配置嗅探"]

    detected = "unknown"
    match = re.search(r'^detected_at:\s*"?([^"\n]+)"?', text, flags=re.MULTILINE)
    if match:
        detected = match.group(1).strip()

    agents: list[str] = []
    current = ""
    available = ""
    for line in text.splitlines():
        agent_match = re.match(r"^\s{2}([A-Za-z0-9_-]+):\s*$", line)
        if agent_match:
            if current:
                agents.append(f"{current}={available or 'unknown'}")
            current = agent_match.group(1)
            available = ""
            continue
        if current:
            available_match = re.match(r"^\s{4}available:\s*(\S+)", line)
            if available_match:
                available = available_match.group(1)
    if current:
        agents.append(f"{current}={available or 'unknown'}")

    refresh_state = os.environ.get("REDCAP_CURRENT_STATUS_AGENT_REGISTRY_REFRESH_STATUS", "cached")
    refresh_labels = {
        "light-refreshed": "registry 已在本次 current-status 前做轻量刷新",
        "cached": "registry 使用现有 cache（未强制刷新）",
        "refresh-failed": "registry 轻量刷新失败，以下结果回退到已有 cache",
    }
    lines = [
        f"registry cache: detected_at={detected}",
        refresh_labels.get(refresh_state, f"registry 刷新状态：{refresh_state}"),
        "registry 只代表安装/配置嗅探，不等于登录态、限流或 headless 调用健康",
    ]
    if agents:
        lines.append("agents: " + ", ".join(agents))
    health_path = repo / "compass/.workflow/agent-health.json"
    if health_path.is_file():
        try:
            health = json.loads(health_path.read_text(encoding="utf-8"))
        except Exception:
            health = {}
        health_agents = []
        for row in health.get("agents") or []:
            if not isinstance(row, dict):
                continue
            health_agents.append(
                f"{row.get('agent', 'unknown')}={row.get('live_status', 'unknown')}"
            )
        if health_agents:
            mode = "live" if health.get("live") else "install-only"
            lines.append(
                f"agent health cache: detected_at={health.get('detected_at', 'unknown')} mode={mode}"
            )
            lines.append("agent health: " + ", ".join(health_agents))
    else:
        lines.append("agent health cache: missing；需要区分登录态/限流/headless 健康时运行 redcap-agent-health-probe.sh --live")
    return lines


def prism_summary(repo: Path) -> list[str]:
    index_path = repo / "prism/reports/index.yaml"
    text = read(index_path)
    if not text:
        return ["未找到 prism/reports/index.yaml；无法统计 formal Prism 历史报告"]

    formal_reports = len(re.findall(r"^\s*-\s+id:\s*", text, flags=re.MULTILINE))
    archived_reports = len(re.findall(r"^\s+archived:\s*true\s*$", text, flags=re.MULTILINE))
    consensus_reports = len(re.findall(r'^\s+verdict:\s*"?consensus"?\s*$', text, flags=re.MULTILINE))
    weak_reports = len(re.findall(r'^\s+verdict:\s*"?weak-consensus"?\s*$', text, flags=re.MULTILINE))
    blocked_reports = len(re.findall(r'^\s+verdict:\s*"?(deadlock|escalate)"?\s*$', text, flags=re.MULTILINE))
    rows: list[dict] = []
    lifecycle_script = repo / "prism/tools/prism-runs-lifecycle.sh"
    if lifecycle_script.is_file():
        try:
            lifecycle_output = subprocess.check_output(
                ["bash", str(lifecycle_script), "json"],
                cwd=repo,
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
            payload = json.loads(lifecycle_output)
            rows = [row for row in payload.get("runs") or [] if isinstance(row, dict)]
        except Exception:
            rows = []

    if not rows:
        runs_root = repo / "prism/runs"
        if runs_root.exists():
            for path in runs_root.iterdir():
                if not path.is_dir():
                    continue
                name = path.name
                if name == ".locks":
                    lifecycle_class = "infra-locks"
                elif name.startswith("acceptance-prism-"):
                    lifecycle_class = "acceptance-fixture"
                elif re.match(r"^20\d{6}-", name):
                    lifecycle_class = "formal-run"
                else:
                    lifecycle_class = "named-local-evidence"
                rows.append(
                    {
                        "run_id": name,
                        "class": lifecycle_class,
                        "local_prune_candidate": False,
                        "evidence_bound": False,
                    }
                )

    counts = Counter(row.get("class", "unknown") for row in rows)
    active_runs = len(rows)
    acceptance_runs = counts.get("acceptance-fixture", 0)
    formal_runs = counts.get("formal-run", 0)
    named_runs = counts.get("named-local-evidence", 0)
    prune_candidates = sum(1 for row in rows if row.get("local_prune_candidate"))
    bound_local = sum(
        1
        for row in rows
        if row.get("class") == "named-local-evidence" and row.get("evidence_bound")
    )
    lines = [
        f"formal Prism 报告索引：{formal_reports} 份（replay-auditable/archived={archived_reports}，legacy/non-auditable={formal_reports - archived_reports}）",
        f"历史 verdict：consensus={consensus_reports}，weak-consensus={weak_reports}，deadlock/escalate={blocked_reports}",
        "未写入 Prism run registry / reports 的单路审查只能算轻量独立评审，不能冒充 formal Prism quorum",
        "当前任务新增的 formal quorum 不能从报告总数或 prism/runs 目录数量反推，必须看本次 run/report 是否真实归档",
    ]
    if active_runs:
        lines.append(
            f"prism/runs 分类：acceptance-fixture={acceptance_runs}，formal-run={formal_runs}，named-local-evidence={named_runs}"
        )
        if bound_local:
            lines.append(
                f"named-local-evidence 中 {bound_local} 个已被历史报告/知识资产引用，按证据链保留；不得直接物理删除"
            )
        if prune_candidates:
            lines.append(
                f"另有 {prune_candidates} 个未绑定的过期 named-local-evidence；可先运行 `bash prism/tools/prism-runs-lifecycle.sh inventory`（只读）与 `bash prism/tools/prism-runs-lifecycle.sh prune-local`（dry-run）做审查计划"
            )
            lines.append(
                "物理清理需要显式批准：不得在未确认前运行 `bash prism/tools/prism-runs-lifecycle.sh prune-local --apply`"
            )
        lines.append(
            f"本地 prism/runs 目录含 {active_runs} 个运行夹具/残留；这是运行证据，不等于当前任务已成功使用 Prism"
        )
    return lines


def layerb_fsm_summary(repo: Path, task_file: Path) -> list[str]:
    script = repo / "compass/tools/redcap-layerb-fsm.sh"
    if not script.is_file():
        return ["layerb-fsm: missing redcap-layerb-fsm.sh"]
    try:
        proc = subprocess.run(
            ["bash", str(script), "--task-file", str(task_file)],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return [f"layerb-fsm 无法运行：{exc}"]
    if proc.returncode != 0:
        detail = proc.stdout.strip() or "unknown error"
        return [f"layerb-fsm 失败：{detail}"]
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        return ["layerb-fsm 输出不可解析"]

    acceptance = payload.get("acceptance") or {}
    closeout = payload.get("closeout") or {}
    lines = [
        f"lifecycle-state: {payload.get('lifecycle_state', 'unknown')}（{payload.get('reason', 'no reason')}）",
        f"independent-acceptance: {acceptance.get('status', 'unknown')}（{acceptance.get('detail', 'no detail')}）",
        f"formal-completion: receipt={'present' if closeout.get('receipt_exists') else 'missing'} pending_closure={'yes' if closeout.get('pending_closure_exists') else 'no'} promise={closeout.get('promise_completed', 0)}/{closeout.get('promise_total', 0)}",
    ]
    run_id = str(acceptance.get("run_id", "")).strip()
    if run_id:
        lines.append(f"prism-acceptance-run: {run_id}")
    return lines


def change_intake_summary(repo: Path, task_file: Path) -> list[str]:
    script = repo / "compass/tools/redcap-change-intake-check.sh"
    if not script.is_file():
        return ["change-intake gate: missing"]

    task_text = read(task_file)
    ledger = section(task_text, "中插需求账本")
    try:
        proc = subprocess.run(
            ["bash", str(script), str(task_file)],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return [f"change-intake gate 无法运行：{exc}"]

    lines = [f"change-intake gate: {'pass' if proc.returncode == 0 else 'fail'}"]
    if proc.returncode != 0:
        lines.append(proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else "unknown error")
        return lines
    if not ledger:
        lines.append("ledger: none required for current task")
        return lines

    rows = []
    for raw in ledger.splitlines():
        stripped = raw.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    if len(rows) <= 1:
        lines.append("ledger: present but no rows")
        return lines
    headers, data_rows = rows[0], rows[1:]
    try:
        status_index = headers.index("状态")
        disposition_index = headers.index("处理方式")
    except ValueError:
        lines.append(f"ledger rows={len(data_rows)}")
        return lines
    statuses = Counter(row[status_index] for row in data_rows if len(row) > status_index)
    dispositions = Counter(row[disposition_index] for row in data_rows if len(row) > disposition_index)
    lines.append(
        "ledger: rows="
        + str(len(data_rows))
        + " status="
        + ",".join(f"{key}:{value}" for key, value in sorted(statuses.items()))
    )
    lines.append(
        "handling: "
        + ",".join(f"{key}:{value}" for key, value in sorted(dispositions.items()))
    )
    return lines


def feishu_inbox_summary(repo: Path) -> list[str]:
    script = repo / "compass/tools/redcap-feishu-inbox.sh"
    if not script.is_file():
        return ["feishu-inbox: missing redcap-feishu-inbox.sh"]
    try:
        proc = subprocess.run(
            ["bash", str(script), "summary", "--human", "--limit", "3"],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=15,
            check=False,
        )
    except Exception as exc:
        return [f"feishu-inbox 无法读取：{exc}"]
    if proc.returncode != 0:
        detail = proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else "unknown error"
        return [f"feishu-inbox 失败：{detail}"]
    lines = []
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if line:
            lines.append(line)
    return lines or ["feishu-inbox: no output"]


def closeout_runtime_summary(repo: Path, meta: dict[str, str], task_text: str) -> list[str]:
    task_id = meta.get("task_id", "").strip()
    confirmed_section = section(task_text, "已确认需求")
    confirmed = hashlib.sha256(confirmed_section.encode("utf-8")).hexdigest() if confirmed_section else ""
    if not task_id or not confirmed:
        return ["closeout-runtime: task identity incomplete; unable to inspect receipt/promise state"]

    identity = closeout_runtime_identity(task_id, confirmed)
    project_hash = hashlib.md5(str(repo.resolve()).encode("utf-8")).hexdigest()
    runtime_root = Path(os.environ.get("REDCAP_RUNTIME_PROJECT_BASE_DIR", "/tmp/redcap/project")) / project_hash / "governance" / "closeout-runtime"
    state_path = runtime_root / "state" / f"{identity}.json"
    receipt_path = runtime_root / "receipts" / f"{identity}.json"
    promise_path = runtime_root / "promise-ledger" / f"{identity}.json"

    lines: list[str] = []
    try:
        promise_payload = json.loads(promise_path.read_text(encoding="utf-8")) if promise_path.is_file() else {}
    except Exception:
        promise_payload = {}
    if promise_payload:
        lines.append(
            f"promise-ledger: completed={promise_payload.get('completed', 0)} pending={promise_payload.get('pending', 0)} total={promise_payload.get('total', 0)}"
        )
    else:
        lines.append("promise-ledger: missing or not yet synced")

    try:
        state_payload = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    except Exception:
        state_payload = {}
    if state_payload:
        lines.append(
            f"closeout-runtime-state: status={state_payload.get('status', 'unknown')} last_command={state_payload.get('last_command', 'none')} last_result={state_payload.get('last_result', 'none')}"
        )
    else:
        lines.append("closeout-runtime-state: not initialized")

    lines.append(f"closeout-receipt: {'present' if receipt_path.is_file() else 'missing'}")
    return lines


def closeout_runtime_facts(repo: Path, meta: dict[str, str], task_text: str) -> dict[str, object]:
    task_id = meta.get("task_id", "").strip()
    confirmed_section = section(task_text, "已确认需求")
    confirmed = hashlib.sha256(confirmed_section.encode("utf-8")).hexdigest() if confirmed_section else ""
    if not task_id or not confirmed:
        return {"receipt_exists": False, "promise_pending": None, "state_status": ""}

    identity = closeout_runtime_identity(task_id, confirmed)
    project_hash = hashlib.md5(str(repo.resolve()).encode("utf-8")).hexdigest()
    runtime_root = Path(os.environ.get("REDCAP_RUNTIME_PROJECT_BASE_DIR", "/tmp/redcap/project")) / project_hash / "governance" / "closeout-runtime"
    state_path = runtime_root / "state" / f"{identity}.json"
    receipt_path = runtime_root / "receipts" / f"{identity}.json"
    promise_path = runtime_root / "promise-ledger" / f"{identity}.json"

    try:
        promise_payload = json.loads(promise_path.read_text(encoding="utf-8")) if promise_path.is_file() else {}
    except Exception:
        promise_payload = {}
    try:
        state_payload = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    except Exception:
        state_payload = {}

    return {
        "receipt_exists": receipt_path.is_file(),
        "promise_pending": promise_payload.get("pending"),
        "promise_completed": promise_payload.get("completed"),
        "promise_total": promise_payload.get("total"),
        "state_status": str(state_payload.get("status", "")).strip(),
        "last_result": str(state_payload.get("last_result", "")).strip(),
    }


def host_hook_summary(repo: Path) -> list[str]:
    matrix_path = repo / "references/host-session-capability-matrix.json"
    try:
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    except Exception:
        return ["未找到宿主能力矩阵；无法判断 full / degraded / unsupported 边界"]

    hosts = matrix.get("hosts") or {}
    host_lines: list[str] = []
    for name in sorted(hosts):
        profile = hosts.get(name) or {}
        status = profile.get("support_status", "unknown")
        missing_identity_mode = profile.get("missing_identity_mode", "unknown")
        host_lines.append(f"{name}={status}/{missing_identity_mode}")

    claude_settings = read(repo / ".claude/settings.json")
    gemini_settings = read(repo / ".gemini/settings.json")
    deployed: list[str] = []
    if "redcap-claude-hook-init.sh" in claude_settings and "redcap-on-stop-review.sh" in claude_settings and "redcap-layerA-session-end.sh claude" in claude_settings:
        deployed.append("claude=SessionStart/Stop/SessionEnd configured")
    else:
        deployed.append("claude=hook config incomplete-or-unreadable")
    if "redcap-layerB-session-start.sh gemini" in gemini_settings and "redcap-layerA-session-end.sh gemini" in gemini_settings:
        deployed.append("gemini=SessionStart/SessionEnd configured")
    else:
        deployed.append("gemini=hook config incomplete-or-unreadable")
    codex_config = read(repo / ".codex/config.toml")
    codex_hooks = read(repo / ".codex/hooks.json")
    codex_marker_result = repo / "references/codex-live-marker-e2e.json"
    codex_marker_passed = False
    if codex_marker_result.is_file():
        try:
            codex_marker_data = json.loads(codex_marker_result.read_text(encoding="utf-8"))
            codex_marker_passed = codex_marker_data.get("codex_cli_live_marker_e2e_passed") is True
        except Exception:
            codex_marker_passed = False
    if "codex" in hosts:
        if (
            "codex_hooks = true" in codex_config
            and "redcap-codex-session-start.sh" in codex_hooks
            and "redcap-codex-stop.sh" in codex_hooks
        ):
            if codex_marker_passed:
                deployed.append("codex=SessionStart/Stop/PreToolUse configured; Codex CLI live marker E2E passed; Codex.app still separately unproven")
            else:
                deployed.append("codex=SessionStart/Stop/PreToolUse candidate configured; live marker E2E pending")
        else:
            deployed.append("codex=AGENTS startup import only; no repo-owned hook config")

    lines: list[str] = []
    if host_lines:
        lines.append("capability matrix: " + ", ".join(host_lines))
    lines.append("hook configs: " + ", ".join(deployed))
    lines.append("配置存在不等于登录态、限流或真实触发已验证；Codex hooks 需 project trust + feature flag + live marker E2E。CLI marker 通过也不自动证明 Codex.app interactive hook ready")
    return lines


def docs_catalog_summary(repo: Path) -> list[str]:
    path = repo / "compass/docs/catalog.json"
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ["未找到 docs catalog；运行 redcap-docs-catalog.sh generate 后可用首读索引替代全量 docs 考古"]

    summary = catalog.get("summary") or {}
    pressure = summary.get("rough_token_pressure") or {}
    lines = [
        f"docs 首读索引：files={summary.get('file_count', 'unknown')} lines={summary.get('lines', 'unknown')} rough_tokens={pressure.get('low', '?')}..{pressure.get('high', '?')}",
        "考古规则：先用 redcap-docs-catalog.sh summary/plan 定位候选，再用 budget 审计精确路径；不得默认 bulk-read compass/docs/**",
    ]
    task_reports = (summary.get("collections") or {}).get("task-reports") or {}
    if task_reports:
        task_pressure = task_reports.get("rough_token_pressure") or {}
        lines.append(
            f"task-reports 压力：files={task_reports.get('file_count', 'unknown')} lines={task_reports.get('lines', 'unknown')} rough_tokens={task_pressure.get('low', '?')}..{task_pressure.get('high', '?')}"
        )
    return lines


def token_risk_summary(repo: Path) -> list[str]:
    audit_script = repo / "compass/tools/redcap-token-risk-audit.sh"
    acceptance_index = repo / "compass/tools/redcap-acceptance-index.sh"
    lines = [
        "首读规则：current-status → docs catalog/knowledge index/acceptance index → 按需精读；不得默认 bulk-read 大文件或运行残留",
    ]
    if acceptance_index.is_file():
        lines.append("acceptance 巨型套件入口：redcap-acceptance-index.sh summary/find/check")
    else:
        lines.append("acceptance 巨型套件入口缺失：redcap-acceptance-index.sh 不存在")
    if not audit_script.is_file():
        lines.append("token 风险审计缺失：redcap-token-risk-audit.sh 不存在")
        return lines
    try:
        proc = subprocess.run(
            ["bash", str(audit_script)],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        lines.append(f"token 风险审计无法运行：{exc}")
        return lines
    lines.append(f"token-risk-audit: {'pass' if proc.returncode == 0 else 'fail'}")
    for raw in proc.stdout.splitlines():
        if raw.startswith(("tracked_large_files=", "ignored_large_paths=", "entry_auto_import_large_files=")):
            lines.append(raw)
        elif "\tpath=prism/runs" in raw:
            lines.append("prism/runs: ignored warning; do not bulk-read; physical cleanup requires explicit approval")
    return lines


def tracking_summary(repo: Path, task_file: Path) -> list[str]:
    script = repo / "compass/tools/redcap-tracking-health.sh"
    if not script.is_file():
        return ["tracking-health missing: compass/tools/redcap-tracking-health.sh"]
    try:
        proc = subprocess.run(
            ["bash", str(script), str(task_file)],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return [f"tracking-health 无法运行：{exc}"]
    lines = [f"tracking-health: {'pass' if proc.returncode == 0 else 'fail'}"]
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if not line or line in {"REDCAP_TRACKING_HEALTH", "TRACKING_OK"}:
            continue
        if line.startswith("[redcap-tracking-health] "):
            line = line.replace("[redcap-tracking-health] ", "", 1)
        lines.append(line)
    return lines


def main() -> int:
    repo = Path(sys.argv[1])
    task_file = Path(sys.argv[2])
    pending_state = Path(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else None
    current_confirmed_hash = sys.argv[4] if len(sys.argv) > 4 else ""

    task_text = read(task_file)
    meta = metadata(task_text)
    pending = state_fields(pending_state)
    closeout_facts = closeout_runtime_facts(repo, meta, task_text)
    receipt_exists = bool(closeout_facts.get("receipt_exists"))
    pending_hash = pending.get("confirmed_hash", "")
    head = run_git(repo, "rev-parse", "--short", "HEAD") or "unknown"
    dirty = run_git(repo, "status", "--short")
    dirty_label = "有未提交变更" if dirty else "干净"

    report_rel = pending.get("artifact_path") or meta.get("task_report", "")
    report_path = None
    if report_rel:
        candidate = Path(report_rel)
        report_path = candidate if candidate.is_absolute() else repo / report_rel

    done_items = capture_report_items(report_path, ["0.1 当前已完成"], 2) if report_path else []
    previous_items = capture_report_items(report_path, ["0.2 上一步完成的是"], 1) if report_path else []
    next_items = capture_report_items(report_path, ["0.3 下一步计划做的是", "0.3 后续动作"], 1) if report_path else []
    roadmap_items = capture_report_items(report_path, ["0.4 整体计划脉络图与当前位置"], 2) if report_path else []

    done_summary = done_items[0] if done_items else "本轮任务报告尚未生成；我会先依据当前任务卡继续推进。"
    next_summary = next_items[0] if next_items else "继续完成当前任务的实现、评审、验证和正式收口。"
    if pending:
        hash_label = pending_hash[:12] + "..." if pending_hash else "unknown"
        receipt_label = "完工凭证已生成" if receipt_exists else "完工凭证尚未生成"
        done_summary = (
            f"当前需求指纹（{hash_label}）对应的未清收尾项仍未处理，"
            f"{receipt_label}，必须满足的收尾红线：{pending.get('required_redlines', 'unknown')}；"
            "历史报告里更早一次收尾的“已清/已完成”口径不能直接外推到当前工作区。"
        )
        next_summary = (
            "先完成当前未清收尾项与收尾记录的一致性核对，"
            "再宣称当前需求版本已经干净收口。"
        )
        roadmap_items = [
            "当前实时状态：完工凭证与未清收尾项分开判断；未清收尾项存在时，以未清收尾项为准。",
            "下一步是清理或证明当前未清收尾项，而不是重复生成已有凭证。"
        ]
    elif receipt_exists:
        next_summary = "当前任务完工凭证已生成，未发现未清收尾阻塞；可转入后续任务或长期演进专项。"
        if not roadmap_items or any(
            "等待 closeout receipt" in item
            or "等待 receipt" in item
            or "receipt 作为正式完工凭证" in item
            or ("receipt" in item.lower() and ("等待" in item or "待" in item))
            for item in roadmap_items
        ):
            roadmap_items = [
                "当前实时状态：完工凭证已生成，未发现未清收尾阻塞。",
                "报告中的收尾前计划句只保留为历史记录，不再作为当前路线判断。"
            ]

    print("当前已完成：" + done_summary)
    print("上一步完成的是：" + (previous_items[0] if previous_items else "本轮任务刚刚重锚，尚未形成上一步报告摘要"))
    print("下一步计划做的是：" + next_summary)
    print("整体计划脉络图与当前位置：" + ("；".join(roadmap_items) if roadmap_items else "当前处于已授权任务的实现阶段，等待任务报告补齐更完整路线摘要"))
    print()

    print("## 当前任务锚点")
    print(f"- task_id: {meta.get('task_id', 'unknown')}")
    print(f"- active_slice: {meta.get('active_slice', 'unknown')}")
    if current_confirmed_hash:
        print(f"- confirmed_hash: {current_confirmed_hash}")
    print(f"- backlog: {meta.get('backlog_id', 'none')} / {meta.get('backlog_item', 'none')}")
    print(f"- git: {head}（{dirty_label}）")
    if report_rel:
        print(f"- task_report: {report_rel}")
    print()

    print("## runtime / workspace / user 边界")
    for line in runtime_workspace_summary(repo, task_file):
        print(f"- {line}")
    print()

    print("## 收尾红线")
    if pending:
        print(f"- status: {pending.get('status', 'pending')}")
        if pending_hash:
            print(f"- confirmed_hash: {pending_hash}")
        print(f"- required_redlines: {pending.get('required_redlines', 'unknown')}")
        print(f"- host/trigger: {pending.get('host', 'unknown')} / {pending.get('trigger', 'unknown')}")
        print(f"- audited_head: {pending.get('audited_head', 'unknown')}")
        print(f"- updated_at: {pending.get('updated_at', 'unknown')}")
        print(f"- state_file: {pending_state}")
        if current_confirmed_hash and pending_hash == current_confirmed_hash:
            print("- note: 当前 confirmed_hash 仍以 pending closure 为准；历史 report/ledger 的已清事件只适用于更早版本的 confirmed_hash")
    else:
        print("- status: clear（未找到当前 .dev-task 对应的 pending closure）")
    print()

    print("## 长期 backlog")
    for line in backlog_summary(repo, meta):
        print(f"- {line}")
    print()

    print("## RedCap 前进刻度表")
    for line in progress_meter_summary(repo, task_file):
        print(f"- {line}")
    print()

    print("## CLI 工具族")
    for line in agent_registry_summary(repo):
        print(f"- {line}")
    print()

    print("## 宿主 Hook / 适配部署")
    for line in host_hook_summary(repo):
        print(f"- {line}")
    print()

    print("## 棱镜 / 独立评审")
    for line in prism_summary(repo):
        print(f"- {line}")
    print()

    print("## docs 考古入口")
    for line in docs_catalog_summary(repo):
        print(f"- {line}")
    print()

    print("## token 风险入口")
    for line in token_risk_summary(repo):
        print(f"- {line}")
    print()

    print("## 追踪连续性")
    for line in tracking_summary(repo, task_file):
        print(f"- {line}")
    print()

    print("## Layer B FSM")
    for line in layerb_fsm_summary(repo, task_file):
        print(f"- {line}")
    print()

    print("## 中插需求 / 重计划")
    for line in change_intake_summary(repo, task_file):
        print(f"- {line}")
    print()

    print("## 飞书收件箱 / 回复入口")
    for line in feishu_inbox_summary(repo):
        print(f"- {line}")
    print()

    print("## 待验证登记")
    print(f"- {pending_validation_summary(repo)}")
    print()

    print("## closeout runtime")
    for line in closeout_runtime_summary(repo, meta, task_text):
        print(f"- {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

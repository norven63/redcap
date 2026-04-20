#!/usr/bin/env bash
# Print a compact RedCap Layer B status overview for handoff, Feishu, and user-facing updates.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$SCRIPT_DIR/redcap-dev-task.sh"
source "$SCRIPT_DIR/redcap-interop-governance.sh"

TASK_FILE=$(redcap_dev_task_resolve_file "${1:-}")
PENDING_STATE=$(redcap_interop_pending_closure_existing_file "$REDCAP_ROOT" "$TASK_FILE" 2>/dev/null || true)
CURRENT_CONFIRMED_HASH=$(redcap_dev_task_confirmed_hash "$TASK_FILE" 2>/dev/null || true)

python3 - "$REDCAP_ROOT" "$TASK_FILE" "$PENDING_STATE" "$CURRENT_CONFIRMED_HASH" <<'PY'
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

repo = Path(sys.argv[1])
task_file = Path(sys.argv[2])
pending_state = Path(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else None
current_confirmed_hash = sys.argv[4] if len(sys.argv) > 4 else ""


def run_git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.DEVNULL).strip()
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


def metadata(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    meta = section(text, "控制面元数据") or section(text, "Canonical Metadata")
    for line in meta.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def state_fields(path) -> dict[str, str]:
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


def load_backlog(meta: dict[str, str]):
    rel = meta.get("backlog_source", "")
    if not rel:
        return None, {}
    path = Path(rel)
    if not path.is_absolute():
        path = repo / rel
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return path, data
    except Exception:
        return path, {}


def backlog_summary(meta: dict[str, str]) -> list[str]:
    path, data = load_backlog(meta)
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


def pending_validation_summary() -> str:
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


def agent_registry_summary() -> list[str]:
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

    lines = [
        f"registry cache: detected_at={detected}",
        "registry 只代表安装/配置嗅探，不等于登录态、限流或 headless 调用健康",
    ]
    if agents:
        lines.append("agents: " + ", ".join(agents))
    return lines


def prism_summary() -> list[str]:
    index_path = repo / "prism/reports/index.yaml"
    text = read(index_path)
    if not text:
        return ["未找到 prism/reports/index.yaml；无法统计 formal Prism 历史报告"]

    formal_reports = len(re.findall(r"^\s*-\s+id:\s*", text, flags=re.MULTILINE))
    archived_reports = len(re.findall(r"^\s+archived:\s*true\s*$", text, flags=re.MULTILINE))
    consensus_reports = len(re.findall(r'^\s+verdict:\s*"?consensus"?\s*$', text, flags=re.MULTILINE))
    weak_reports = len(re.findall(r'^\s+verdict:\s*"?weak-consensus"?\s*$', text, flags=re.MULTILINE))
    blocked_reports = len(re.findall(r'^\s+verdict:\s*"?(deadlock|escalate)"?\s*$', text, flags=re.MULTILINE))
    active_runs = len([path for path in (repo / "prism/runs").glob("*") if path.is_dir()]) if (repo / "prism/runs").exists() else 0
    lines = [
        f"formal Prism 历史报告：{formal_reports} 份（live-index={formal_reports - archived_reports}，archived={archived_reports}）",
        f"历史 verdict：consensus={consensus_reports}，weak-consensus={weak_reports}，deadlock/escalate={blocked_reports}",
        "未写入 Prism run registry / reports 的单路审查只能算轻量独立评审，不能冒充 formal Prism quorum",
        "当前任务新增的 formal quorum 不能从报告总数或 prism/runs 目录数量反推，必须看本次 run/report 是否真实归档",
    ]
    if active_runs:
        lines.append(f"本地 prism/runs 目录含 {active_runs} 个运行夹具/残留；这是运行证据，不等于当前任务已成功使用 Prism")
    return lines


def host_hook_summary() -> list[str]:
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
    if "codex" in hosts:
        deployed.append("codex=AGENTS startup import only; no repo-owned reply-veto hook")

    lines: list[str] = []
    if host_lines:
        lines.append("capability matrix: " + ", ".join(host_lines))
    lines.append("hook configs: " + ", ".join(deployed))
    lines.append("配置存在不等于登录态、限流或真实触发已验证；弱 Hook / 无 Hook 宿主仍必须走 pending closure、wrapper 或 degraded/unsupported 标记")
    return lines


def docs_catalog_summary() -> list[str]:
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
    collections = summary.get("collections") or {}
    task_reports = collections.get("task-reports") or {}
    if task_reports:
        task_pressure = task_reports.get("rough_token_pressure") or {}
        lines.append(
            f"task-reports 压力：files={task_reports.get('file_count', 'unknown')} lines={task_reports.get('lines', 'unknown')} rough_tokens={task_pressure.get('low', '?')}..{task_pressure.get('high', '?')}"
        )
    return lines


def token_risk_summary() -> list[str]:
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

    status = "pass" if proc.returncode == 0 else "fail"
    lines.append(f"token-risk-audit: {status}")
    for raw in proc.stdout.splitlines():
        if raw.startswith(("tracked_large_files=", "ignored_large_paths=", "entry_auto_import_large_files=")):
            lines.append(raw)
        elif "\tpath=prism/runs" in raw:
            lines.append("prism/runs: ignored warning; do not bulk-read; physical cleanup requires explicit approval")
    return lines


task_text = read(task_file)
meta = metadata(task_text)
pending = state_fields(pending_state)
pending_hash = pending.get("confirmed_hash", "")
head = run_git("rev-parse", "--short", "HEAD") or "unknown"
dirty = run_git("status", "--short")
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

done_summary = done_items[0] if done_items else "未从任务报告抽取到摘要；请查看任务报告或 .dev-task.md"
next_summary = next_items[0] if next_items else "未从任务报告抽取到下一步摘要"
if pending:
    hash_label = pending_hash[:12] + "..." if pending_hash else "unknown"
    done_summary = (
        f"当前 confirmed_hash（{hash_label}）对应的 pending closure 仍未清，"
        f"required_redlines={pending.get('required_redlines', 'unknown')}；"
        "历史报告里更早一次 closeout 的“已清/已完成”口径不能直接外推到当前工作区。"
    )
    next_summary = (
        "先完成当前 pending closure、task report、current-status 与 closure ledger 的一致性收口，"
        "再宣称当前 confirmed_hash 已 clean。"
    )

print("当前已完成：" + done_summary)
print("上一步完成的是：" + (previous_items[0] if previous_items else "未从任务报告抽取到上一步摘要"))
print("下一步计划做的是：" + next_summary)
print("整体计划脉络图与当前位置：" + ("；".join(roadmap_items) if roadmap_items else "未从任务报告抽取到路线摘要"))
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
for line in backlog_summary(meta):
    print(f"- {line}")
print()

print("## CLI 工具族")
for line in agent_registry_summary():
    print(f"- {line}")
print()

print("## 宿主 Hook / 适配部署")
for line in host_hook_summary():
    print(f"- {line}")
print()

print("## 棱镜 / 独立评审")
for line in prism_summary():
    print(f"- {line}")
print()

print("## docs 考古入口")
for line in docs_catalog_summary():
    print(f"- {line}")
print()

print("## token 风险入口")
for line in token_risk_summary():
    print(f"- {line}")
print()

print("## 待验证登记")
print(f"- {pending_validation_summary()}")
PY

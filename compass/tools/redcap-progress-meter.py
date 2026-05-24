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
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "references/redcap-progress-meter-policy.json"


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def section(text: str, heading: str) -> str:
    capture = False
    level = 0
    lines: list[str] = []
    for raw in text.splitlines():
        match = re.match(r"^(#+)\s*(.*?)\s*$", raw)
        if match:
            current_level = len(match.group(1))
            current_heading = match.group(2).strip()
            if capture and current_level <= level:
                break
            if current_heading == heading or current_heading.startswith(heading):
                capture = True
                level = current_level
                continue
        if capture:
            lines.append(raw)
    return "\n".join(lines).strip()


def parse_fields(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in text.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$", raw)
        if match:
            result[match.group(1)] = match.group(2).strip()
    return result


def first_bullet(body: str, default: str) -> str:
    for raw in body.splitlines():
        line = raw.strip()
        if not line.startswith("- "):
            continue
        value = re.sub(r"^-\s+", "", line)
        value = re.sub(r"^(当前已完成|上一步完成的是|下一步计划做的是|整体计划脉络图是|当前所在位置|人工介入|说明)：", "", value)
        value = re.sub(r"`([^`]*)`", r"\1", value)
        value = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
        return re.sub(r"\s+", " ", value).strip() or default
    return default


def humanize_primary_text(value: str) -> str:
    replacements = {
        "正式发布人工授权硬门": "正式发布前的人工决策点",
        "人工授权硬门": "人工决策点",
        "human hard gate": "人工决策点",
        "机械继续": "例行继续",
        "release blocker": "发布前阻塞项",
        "backlog": "任务清单",
        "closeout receipt": "完工证明",
        "receipt": "完工证明",
        "pending closure": "未完成的收尾事项",
        "active_slice": "当前任务段",
        "confirmed_hash": "需求记录",
        "Prism": "棱镜评审",
        "assistant chat reply": "聊天回复",
        "CLI": "命令行工具",
        "FSM": "状态流",
        "Layer B": "RedCap 自身开发",
        "validator": "检查程序",
        "spec-check": "规范检查",
        "门禁": "检查点",
        "硬门": "必须人工决策的边界",
        "工作切片": "当前任务段",
        "需求指纹": "需求记录",
        "收尾红线": "完成前必须满足的要求",
        "收口": "最终完成",
    }
    result = value
    for old, new in replacements.items():
        result = result.replace(old, new)
    result = re.sub(r"\s*(聊天回复|命令行工具)\s*", r"\1", result)
    return result


def human_sentence_fragment(value: str) -> str:
    return humanize_primary_text(value).strip().rstrip("。；; ")


def task_report_path(meta: dict[str, str]) -> Path | None:
    raw = meta.get("task_report", "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else ROOT / raw


def closeout_identity(task_id: str, confirmed_hash: str) -> str:
    safe_task = re.sub(r"[^A-Za-z0-9._-]+", "_", task_id).strip("._-") or "task"
    return f"{safe_task}-{confirmed_hash}"


def confirmed_hash(task_text: str) -> str:
    confirmed = section(task_text, "已确认需求")
    return hashlib.sha256(confirmed.encode("utf-8")).hexdigest() if confirmed else ""


def closeout_state(repo: Path, task_id: str, hash_value: str) -> dict[str, Any]:
    if not task_id or not hash_value:
        return {"receipt": "unknown", "promise": "unknown", "state": "unknown"}
    project_hash = hashlib.md5(str(repo.resolve()).encode("utf-8")).hexdigest()
    project_base = Path(os.environ.get("REDCAP_RUNTIME_PROJECT_BASE_DIR", "/tmp/redcap/project"))
    runtime_root = project_base / project_hash / "governance" / "closeout-runtime"
    identity = closeout_identity(task_id, hash_value)
    receipt = runtime_root / "receipts" / f"{identity}.json"
    promise = runtime_root / "promise-ledger" / f"{identity}.json"
    state = runtime_root / "state" / f"{identity}.json"
    promise_payload = load_json(promise)
    state_payload = load_json(state)
    return {
        "receipt": "present" if receipt.is_file() else "missing",
        "promise_completed": promise_payload.get("completed", 0),
        "promise_total": promise_payload.get("total", 0),
        "promise_pending": promise_payload.get("pending", 0),
        "state": state_payload.get("status", "not-initialized"),
    }


def backlog_status(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    counts: Counter[str] = Counter()
    current_focus = payload.get("current_focus") if isinstance(payload.get("current_focus"), dict) else {}
    open_items: list[str] = []
    seen_ids: set[str] = set()
    for item in payload.get("requirements") or []:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "").strip()
        if item_id:
            seen_ids.add(item_id)
        status = str(item.get("status", "unknown"))
        counts[status] += 1
        if status not in {"done", "archived", "superseded"} and len(open_items) < 3:
            open_items.append(str(item.get("human_label") or f"{item.get('id', 'unknown')} {item.get('title', '')}").strip())
    for group in payload.get("groups") or []:
        if not isinstance(group, dict):
            continue
        for item in group.get("items") or []:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("id") or "").strip()
            if item_id and item_id in seen_ids:
                continue
            status = str(item.get("status", "unknown"))
            counts[status] += 1
            if status not in {"done", "archived", "superseded"} and len(open_items) < 3:
                open_items.append(str(item.get("human_label") or f"{item.get('id', 'unknown')} {item.get('title', '')}").strip())
    return {
        "path": path.relative_to(ROOT).as_posix() if path.exists() else path.as_posix(),
        "current_focus": current_focus,
        "status_counts": dict(sorted(counts.items())),
        "open_examples": open_items,
    }


def parent_autocontinue_status(task_file: Path) -> dict[str, str]:
    script = ROOT / "compass/tools/redcap-parent-autocontinue-check.sh"
    if not script.is_file():
        return {"state": "checker-missing", "raw": "checker missing"}
    try:
        proc = subprocess.run(
            ["bash", str(script), str(task_file)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return {"state": "checker-error", "raw": str(exc)}
    raw = proc.stdout.strip()
    state_match = re.search(r"\bstate=([^ ]+)", raw)
    next_match = re.search(r"\bnext=([^ ]+)", raw)
    return {
        "state": state_match.group(1) if state_match else ("fail" if proc.returncode else "unknown"),
        "next": next_match.group(1) if next_match else "",
        "raw": raw,
    }


def evolution_status(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    counts: Counter[str] = Counter()
    examples: list[str] = []
    active_statuses = {"candidate", "reviewing"}
    for item in payload.get("candidates") or []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "unknown"))
        counts[status] += 1
        if status in active_statuses and len(examples) < 3:
            examples.append(f"{item.get('id', 'unknown')} {item.get('title', '')}".strip())
    return {"status_counts": dict(sorted(counts.items())), "open_examples": examples}


def governance_debt_status(path: Path) -> dict[str, Any]:
    text = read(path)
    counts: Counter[str] = Counter()
    examples: list[str] = []
    current_title = ""
    for raw in text.splitlines():
        heading = re.match(r"^###\s+(GD-[0-9]+[：:].*)$", raw.strip())
        if heading:
            current_title = heading.group(1).strip()
            continue
        status = re.match(r"^-\s+\*\*implementation_status\*\*:\s+`([^`]+)`", raw.strip())
        if not status:
            continue
        value = status.group(1).strip() or "unknown"
        counts[value] += 1
        if value != "done" and current_title and len(examples) < 3:
            examples.append(current_title)
    return {
        "path": path.relative_to(ROOT).as_posix() if path.exists() else path.as_posix(),
        "counts": dict(sorted(counts.items())),
        "open_examples": examples,
    }


def lifecycle_status(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    rows = payload.get("entries") or payload.get("assets") or payload.get("items") or []
    counts: Counter[str] = Counter()
    if isinstance(rows, list):
        for item in rows:
            if isinstance(item, dict):
                counts[
                    str(
                        item.get("lifecycle")
                        or item.get("default_action")
                        or item.get("asset_class")
                        or item.get("lifecycle_class")
                        or item.get("class")
                        or item.get("status")
                        or "unknown"
                    )
                ] += 1
    return {"path": path.relative_to(ROOT).as_posix() if path.exists() else path.as_posix(), "counts": dict(sorted(counts.items()))}


def build_meter(task_file: Path) -> dict[str, Any]:
    policy = load_json(POLICY_PATH)
    task_text = read(task_file)
    meta = parse_fields(section(task_text, "控制面元数据"))
    report = task_report_path(meta)
    report_text = read(report) if report else ""
    hash_value = confirmed_hash(task_text)
    closeout = closeout_state(ROOT, meta.get("task_id", ""), hash_value)
    architecture_backlog = backlog_status(ROOT / "references/backlogs/redcap-architecture-smell-governance.json")
    framework_backlog = backlog_status(ROOT / "references/backlogs/framework-upgrade.json")
    parent_autocontinue = parent_autocontinue_status(task_file)
    evolution = evolution_status(ROOT / "compass/evolution/candidates.json")
    governance_debt = governance_debt_status(ROOT / "compass/knowledge/governance-debt-register.md")
    reference_lifecycle = lifecycle_status(ROOT / "references/reference-asset-lifecycle.json")
    legacy_lifecycle = lifecycle_status(ROOT / "references/legacy-asset-lifecycle.json")
    architecture_open_examples = architecture_backlog.get("open_examples", [])

    done = first_bullet(section(report_text, "0.1 当前已完成"), "当前任务已建立，等待任务报告或完工凭证更新。")
    next_step = first_bullet(section(report_text, "0.3 下一步计划做的是"), "继续推进当前任务的实现、评审与最终完成。")
    intervention = first_bullet(section(report_text, "0.5 是否需要 Norven 人工介入"), "不需要")
    roadmap = first_bullet(section(report_text, "0.4 整体计划脉络图与当前位置"), "历史债务坏味 -> 当前专注任务集 -> 长期演进专项")
    effect = first_bullet(section(report_text, "0.2 上一步完成的是"), "本轮完成后，会让当前任务进展更清晰、可验证。")
    if closeout.get("receipt") == "present":
        if parent_autocontinue.get("state") in {"current-focus-still-on-completed-child", "focus-item-missing"}:
            next_step = "当前子任务完工凭证已生成，但父任务 backlog 焦点没有安全指向下一项；必须先修正 current_focus，再继续父任务线。"
        elif parent_autocontinue.get("state") == "auto-continue-required":
            next_step = (
                f"当前子任务完工凭证已生成，父任务线还有 {parent_autocontinue.get('next') or '下一项'}；"
                "未命中人工硬门时应自动续跑，不应等待 Norven 机械回复。"
            )
        else:
            next_step = "当前任务已经正式完成；可转入后续任务或长期演进专项。"
        if architecture_open_examples:
            next_step = "当前任务完工凭证已生成；发布准备前仍需处理：" + "；".join(architecture_open_examples[:3]) + "。"
        if intervention == "不需要":
            intervention = "不需要，本任务已正式收口。"

    receipt_present = closeout.get("receipt") == "present"
    receipt_label = "已完成" if receipt_present else "尚未完成"
    gate_tier = (meta.get("gate_tier") or "未声明").strip()
    gate_reason = (meta.get("gate_reason") or "").strip()
    promise_total = int(closeout.get("promise_total", 0) or 0)
    promise_completed = int(closeout.get("promise_completed", 0) or 0)
    if receipt_present:
        current_position = f"这段任务{receipt_label}；已兑现 {promise_completed}/{promise_total} 项承诺。"
    elif promise_total > 0:
        current_position = f"这段任务正在执行；已兑现 {promise_completed}/{promise_total} 项承诺。"
    else:
        current_position = "这段任务正在执行；承诺项会在完工核验时统一核对。"
    debt_counts = architecture_backlog.get("status_counts", {})
    governance_counts = governance_debt.get("counts", {})
    evolution_counts = evolution.get("status_counts", {})
    debt_open = sum(v for k, v in debt_counts.items() if k not in {"done", "archived", "superseded"})
    governance_open = sum(v for k, v in governance_counts.items() if k != "done")
    evolution_open = sum(v for k, v in evolution_counts.items() if k in {"candidate", "reviewing"})
    focus = framework_backlog.get("current_focus") if isinstance(framework_backlog.get("current_focus"), dict) else {}
    focus_summary = str(focus.get("summary") or "").strip()
    debt_summary = "历史债务暂无开放项" if debt_open + governance_open == 0 else f"历史债务仍有 {debt_open + governance_open} 项开放"
    evolution_summary = "长期演进暂无待评审候选" if evolution_open == 0 else f"长期演进仍有 {evolution_open} 项待评审候选"
    task_goal = str(meta.get("top_goal") or "").strip()
    current_summary = human_sentence_fragment(task_goal or focus_summary or "当前任务正在推进")
    focus_id = str(focus.get("item_id") or focus.get("id") or "").strip()
    task_id = str(meta.get("task_id") or "").strip()
    bound_backlog = str(meta.get("backlog_source") or "").strip()
    task_uses_framework_backlog = bool(bound_backlog and Path(bound_backlog).name == "framework-upgrade.json")
    if task_uses_framework_backlog and focus_summary and focus_id and focus_id != task_id:
        current_summary += "；主推进任务仍停在：" + human_sentence_fragment(focus_summary)
    panorama = f"{debt_summary}；当前主线：{current_summary}；{evolution_summary}"
    if architecture_open_examples:
        panorama += "；开放历史债务：" + "；".join(architecture_open_examples[:3])

    buckets = [
        {
            "id": "historical_debt_smell",
            "label": "历史债务坏味",
            "summary": "旧机制、旧资产、冗余证据和结构坏味保持可见，但不抢占当前任务。",
            "counts": {
                "architecture_backlog": debt_counts,
                "governance_debt": governance_counts,
                "reference_lifecycle": reference_lifecycle.get("counts", {}),
                "legacy_lifecycle": legacy_lifecycle.get("counts", {}),
            },
            "examples": architecture_open_examples + governance_debt.get("open_examples", []),
            "source_paths": [
                "references/backlogs/redcap-architecture-smell-governance.json",
                "references/reference-asset-lifecycle.json",
                "references/legacy-asset-lifecycle.json",
                "compass/knowledge/governance-debt-register.md",
            ],
        },
        {
            "id": "current_focused_task_set",
            "label": "当前专注任务集",
            "summary": "当前任务由任务卡、任务报告、长期任务焦点和完工凭证共同说明。",
            "task": {
                "task_id": meta.get("task_id", ""),
                "active_slice": meta.get("active_slice", ""),
                "task_report": meta.get("task_report", ""),
                "gate_tier": gate_tier,
                "gate_reason": gate_reason,
                "closeout": closeout,
                "framework_backlog": framework_backlog,
                "parent_autocontinue": parent_autocontinue,
            },
            "source_paths": [".dev-task.md", meta.get("task_report", ""), "closeout-cap.sh", "references/backlogs/framework-upgrade.json"],
        },
        {
            "id": "long_term_evolution_program",
            "label": "长期演进专项",
            "summary": "未来增强通过 Evolution candidates、路线图和 Prism-backed policy 保持可见，晋升前不打断当前任务。",
            "counts": {"evolution_candidates": evolution_counts},
            "examples": evolution.get("open_examples", []),
            "source_paths": [
                "compass/evolution/candidates.json",
                "references/conclusion-prism-policy.json",
                "references/full-llm-wiki-roadmap.json",
                "references/redcap-forge-policy.json",
            ],
        },
    ]

    return {
        "policy_id": policy.get("policy_id", "redcap-progress-meter-policy"),
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "truth_source_mode": (policy.get("truth_source_rule") or {}).get("mode", "aggregate-only"),
        "source_mappings": policy.get("source_mappings", []),
        "prism_boundary": policy.get("prism_boundary", {}),
        "human": {
            "整体任务全景图": panorama,
            "当前位置": current_position,
            "当前已完成": humanize_primary_text(done),
            "带来的效果": humanize_primary_text(effect),
            "下一步计划做的是": humanize_primary_text(next_step),
            "需要人工介入": humanize_primary_text(intervention),
            "路线摘要": humanize_primary_text(roadmap),
        },
        "buckets": buckets,
    }


def print_human(payload: dict[str, Any]) -> None:
    human = payload.get("human", {})
    print("REDCAP_PROGRESS_METER")
    print(f"- 整体任务全景图：{human.get('整体任务全景图', 'unknown')}")
    print(f"- 当前位置：{human.get('当前位置', 'unknown')}")
    print(f"- 当前已完成：{human.get('当前已完成', 'unknown')}")
    print(f"- 下一步计划做的是：{human.get('下一步计划做的是', 'unknown')}")
    print(f"- 需要人工介入：{human.get('需要人工介入', 'unknown')}")
    print("- 说明：以上是给人看的摘要；需要证据时再展开检查记录和报告链接。")
    print("PROGRESS_METER_OK")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render RedCap progress meter from existing truth sources.")
    parser.add_argument("--task-file", default=str(ROOT / ".dev-task.md"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    task_file = Path(args.task_file)
    if not task_file.is_absolute():
        task_file = ROOT / task_file
    payload = build_meter(task_file)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_human(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

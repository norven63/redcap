#!/usr/bin/env python3
# 用途：棱镜与结论保障脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#prism-and-providers

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "references/conclusion-prism-policy.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-conclusion-prism-check] {message}")


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.is_file():
        fail(f"missing file: {rel}")
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    if not path.is_file():
        fail(f"missing json: {rel}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid json {rel}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{rel} must be a json object")
    return payload


def require_phrases(text: str, label: str, phrases: list[str]) -> None:
    missing = [phrase for phrase in phrases if phrase not in text]
    if missing:
        fail(f"{label} missing phrases: {', '.join(missing)}")


def main() -> int:
    policy = load_json("references/conclusion-prism-policy.json")
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "redcap-prism-backed-conclusion-policy":
        fail("policy_id mismatch")

    non_official = str(policy.get("non_official_boundary", ""))
    for phrase in ["single main-agent reply", "proposal", "joint reviewed verdict"]:
        if phrase not in non_official:
            fail(f"non_official_boundary missing phrase: {phrase}")

    host_limited = str(policy.get("host_limited_boundary", ""))
    for phrase in ["tracked official conclusions", "physical pre-send veto", "Codex.app live chat sentence"]:
        if phrase not in host_limited:
            fail(f"host_limited_boundary missing phrase: {phrase}")

    official = str(policy.get("official_conclusion_definition", ""))
    for phrase in ["answer", "report", "release posture", "completion claim", "governance decision"]:
        if phrase not in official:
            fail(f"official_conclusion_definition missing phrase: {phrase}")

    classes = policy.get("conclusion_classes")
    if not isinstance(classes, list) or len(classes) < 5:
        fail("conclusion_classes must cover at least five official conclusion classes")
    required_classes = {"architecture", "governance", "completion", "release-readiness", "long-term-roadmap"}
    seen_classes: set[str] = set()
    for item in classes:
        if not isinstance(item, dict):
            fail("conclusion class entries must be objects")
        cid = item.get("id")
        if cid in seen_classes:
            fail(f"duplicate conclusion class: {cid}")
        seen_classes.add(str(cid))
        if item.get("prism_required") is not True:
            fail(f"{cid}: prism_required must be true")
        examples = item.get("examples")
        if not isinstance(examples, list) or len(examples) < 2:
            fail(f"{cid}: examples must contain at least two items")
    missing = required_classes - seen_classes
    if missing:
        fail("missing conclusion classes: " + ", ".join(sorted(missing)))

    allowed = policy.get("allowed_non_prism_outputs")
    if not isinstance(allowed, list) or len(allowed) < 3:
        fail("allowed_non_prism_outputs must list safe non-Prism boundaries")
    allowed_text = json.dumps(allowed, ensure_ascii=False)
    for phrase in ["source", "proposal", "low-risk"]:
        if phrase not in allowed_text:
            fail(f"allowed_non_prism_outputs missing boundary phrase: {phrase}")

    evidence = policy.get("prism_evidence_requirement")
    if not isinstance(evidence, dict):
        fail("prism_evidence_requirement must be an object")
    evidence_text = json.dumps(evidence, ensure_ascii=False)
    for phrase in ["formal Prism run", "resource-limited-pass", "blocker-free", "skipping Prism"]:
        if phrase not in evidence_text:
            fail(f"prism_evidence_requirement missing phrase: {phrase}")

    guarantee = policy.get("guarantee_first_capability_rule")
    if not isinstance(guarantee, dict):
        fail("guarantee_first_capability_rule must be an object")
    guarantee_text = json.dumps(guarantee, ensure_ascii=False)
    for phrase in ["script", "validator", "hook", "acceptance", "receipt", "diagnose/spec-check", "non-automation reason"]:
        if phrase not in guarantee_text:
            fail(f"guarantee_first_capability_rule missing phrase: {phrase}")

    follow_up = policy.get("plan_only_follow_up_requirement")
    if not isinstance(follow_up, dict):
        fail("plan_only_follow_up_requirement must be an object")
    follow_up_text = json.dumps(follow_up, ensure_ascii=False)
    for phrase in ["design-complete", "plan-complete", "partial-with-explicit-defer", "durably tracked", "revisit trigger", "acceptance boundary", "physical apply complete", "Norven's memory"]:
        if phrase not in follow_up_text:
            fail(f"plan_only_follow_up_requirement missing phrase: {phrase}")

    surfaces = policy.get("enforcement_surfaces")
    if not isinstance(surfaces, list):
        fail("enforcement_surfaces must be a list")
    for rel in surfaces:
        if not isinstance(rel, str) or not rel.strip():
            fail("invalid enforcement surface")
        surface_path = ROOT / rel
        if not surface_path.exists():
            fail(f"enforcement surface missing: {rel}")
        if surface_path.is_file() and surface_path.stat().st_size <= 0:
            fail(f"enforcement surface is empty: {rel}")

    must_not = " ".join(str(item) for item in policy.get("must_not_claim", []))
    for phrase in ["Every live chat sentence", "single Cap answer", "Documented-only", "Resource-limited Prism", "Plan-complete"]:
        if phrase not in must_not:
            fail(f"must_not_claim missing phrase: {phrase}")

    core = read("compass/CONTRIBUTING.core.md")
    require_phrases(
        core,
        "CONTRIBUTING.core.md",
        [
            "结论性输出必须 Prism-backed",
            "未经 Prism 的主 Agent 观点只能叫建议稿",
            "新增能力默认先做固化保障评估",
            "计划型完成不能吞掉后续任务",
        ],
    )

    contributing = read("compass/CONTRIBUTING.md")
    require_phrases(
        contributing,
        "CONTRIBUTING.md",
        [
            "结论性输出 Prism Gate",
            "RedCap 官方结论",
            "新增能力的固化保障优先级",
            "计划型完成与后续任务登记",
        ],
    )

    protocol = read("prism/protocol.md")
    require_phrases(
        protocol,
        "prism/protocol.md",
        [
            "结论性输出 Prism Gate",
            "official conclusion",
            "proposal / first-pass",
            "plan-complete",
        ],
    )

    prism_readme = read("prism/README.md")
    require_phrases(
        prism_readme,
        "prism/README.md",
        [
            "结论性输出",
            "不是单 Agent 自证",
            "resource-limited",
            "计划型完成",
        ],
    )

    guarantees = load_json("references/execution-guarantees.json")
    guarantee_ids = {item.get("id") for item in guarantees.get("guarantees", []) if isinstance(item, dict)}
    for gid in ["prism-backed-conclusion-gate", "guarantee-first-capability-gate", "plan-only-follow-up-registration-gate"]:
        if gid not in guarantee_ids:
            fail(f"execution guarantees missing: {gid}")

    dictionary = read("references/file-lookup-dictionary.md")
    require_phrases(
        dictionary,
        "file lookup dictionary",
        [
            "references/conclusion-prism-policy.json",
            "redcap-conclusion-prism-check",
        ],
    )

    print("CONCLUSION_PRISM_OK")
    print(f"classes={len(classes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

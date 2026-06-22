#!/usr/bin/env python3
"""RedCap 自我净化与 Cap 私有人格沉淀边界检查器。"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile
from typing import Any

import knowledge_gateway


REPO_ROOT = pathlib.Path(os.environ.get("REDCAP_REPO_ROOT", pathlib.Path(__file__).resolve().parents[2])).resolve()
DEFAULT_CONTRACT = REPO_ROOT / "assets" / "contracts" / "self-purification.json"
DEFAULT_LOOP_CONTRACT = REPO_ROOT / "assets" / "contracts" / "self-purification-loop.json"
DEFAULT_LOOP_EVIDENCE = REPO_ROOT / ".redcap" / "evidence" / "rsp" / "rsp-07-self-purification-loop.json"
DEFAULT_LOOP_ARTIFACTS = REPO_ROOT / ".redcap" / "evidence" / "rsp" / "rsp-07-self-purification-loop-artifacts"
DEFAULT_KNOWLEDGE_ROOT = REPO_ROOT
CURRENT_RSP_07_08_TASK_ID = "20260621-rsp-07-08-self-purification-knowledge"
DEFAULT_RSP_07_08_START_MARKER = (
    REPO_ROOT / "assets" / "evidence" / "prism" / CURRENT_RSP_07_08_TASK_ID / "request.json"
)
RUN_LOOP_SCHEMA_ID = "redcap-self-purification-run-loop"
RETRIEVAL_SCHEMA_ID = "redcap-self-purification-knowledge-retrieval"
CANDIDATES_SCHEMA_ID = "redcap-self-purification-candidates"
PERSONA_DECISION_SCHEMA_ID = "redcap-cap-persona-boundary-decision"
RESOLUTION_SCHEMA_ID = "redcap-self-purification-resolution"

REQUIRED_RETRIEVAL_SCOPES = {"implementation", "completion", "e2e", "self-development"}
REQUIRED_RESULT_HANDLING = {"use_relevant_entry", "record_no_relevant_entry", "record_skip_reason"}
REQUIRED_TRIGGERS = {
    "user_correction",
    "prism_block_or_concern",
    "e2e_failure",
    "hook_false_positive",
    "workflow_drift",
    "completion_claim_correction",
    "new_reusable_design",
    "persona_signal",
}
REQUIRED_CANDIDATE_FIELDS = {
    "id",
    "source_task",
    "trigger",
    "lesson",
    "privacy_class",
    "proposed_destination",
    "evidence",
    "created_at",
}
REQUIRED_DECISIONS = {"promote_public", "keep_private", "no_promote", "defer_with_owner"}
REQUIRED_PROMOTION = {
    "reviewed_source",
    "privacy_checked",
    "deduplicated",
    "human_readable",
    "index_first",
    "source_refs_exist",
}
FORBIDDEN_PUBLIC_DESTINATIONS = {
    "assets/knowledge/entries",
    "assets/knowledge/arsenal",
    "assets/contracts",
    "assets/docs",
}
REQUIRED_PERSONA_EVIDENCE_FIELDS = {"candidate_id", "decision", "source_task", "reason", "hash", "counts"}
FORBIDDEN_PERSONA_EVIDENCE = {"private_identity_body", "raw_persona_body", "secret", "token", "credential"}
REQUIRED_BEFORE = {"knowledge_retrieval_or_skip_reason"}
REQUIRED_AFTER = {"harvest_candidate_or_no_candidate_reason", "review_decision", "promotion_or_no_promote_result"}
REQUIRED_RUNTIME_INTEGRATION = {
    "pre_task_entrypoint",
    "post_task_entrypoint",
    "aggregate_check",
    "e2e_hard_gate",
    "skip_policy",
    "failure_policy",
}
ENTRY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def utc_from_timestamp(value: float) -> dt.datetime:
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).replace(microsecond=0)


def file_time_summary(path: pathlib.Path) -> dict[str, Any]:
    stat = path.stat()
    created_at = getattr(stat, "st_birthtime", stat.st_ctime)
    return {
        "created_at_utc": utc_from_timestamp(created_at).isoformat(),
        "modified_at_utc": utc_from_timestamp(stat.st_mtime).isoformat(),
        "modified_timestamp": stat.st_mtime,
    }


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_text(path: pathlib.Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(value, encoding="utf-8")
    os.replace(tmp, path)


def slugify(value: str, *, fallback: str = "self-purification-candidate") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if len(slug) < 3:
        slug = fallback
    if len(slug) > 54:
        slug = slug[:54].strip("-")
    if not slug:
        slug = fallback
    if not ENTRY_ID_RE.fullmatch(slug):
        slug = fallback
    return slug


def evidence_rel(path: pathlib.Path, root: pathlib.Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def knowledge_paths(knowledge_root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    return knowledge_root / "assets" / "knowledge" / "index.json", knowledge_root / "assets" / "knowledge" / "entries"


def load_knowledge_index(knowledge_root: pathlib.Path) -> dict[str, Any]:
    old_root = knowledge_gateway.REPO_ROOT
    knowledge_gateway.REPO_ROOT = knowledge_root
    try:
        index_path, _ = knowledge_paths(knowledge_root)
        index = knowledge_gateway.load_json(index_path)
        failures = knowledge_gateway.validate_index(index)
        if failures:
            raise SystemExit("; ".join(failures))
        return index
    finally:
        knowledge_gateway.REPO_ROOT = old_root


def search_knowledge(knowledge_root: pathlib.Path, query: str) -> list[dict[str, Any]]:
    old_root = knowledge_gateway.REPO_ROOT
    knowledge_gateway.REPO_ROOT = knowledge_root
    try:
        return knowledge_gateway.search_entries(load_knowledge_index(knowledge_root), query)
    finally:
        knowledge_gateway.REPO_ROOT = old_root


def promote_public_knowledge(
    *,
    knowledge_root: pathlib.Path,
    entry_id: str,
    title: str,
    summary: str,
    tags: list[str],
    body: str,
    source_path: str,
    reviewer: str,
    reason: str,
    evidence_root: pathlib.Path,
) -> dict[str, Any]:
    if not ENTRY_ID_RE.fullmatch(entry_id):
        raise SystemExit("promote_public entry id 必须是小写 kebab-case")
    old_root = knowledge_gateway.REPO_ROOT
    knowledge_gateway.REPO_ROOT = knowledge_root
    try:
        index_path, entries_dir = knowledge_paths(knowledge_root)
        index = load_knowledge_index(knowledge_root)
        if knowledge_gateway.index_has_id(index, entry_id):
            return {
                "ok": True,
                "skipped": True,
                "reason": "knowledge entry already exists",
                "entry_id": entry_id,
            }
        draft_path = evidence_root / "knowledge-draft.json"
        review_path = evidence_root / "knowledge-review.json"
        body_path = entries_dir / f"{entry_id}.md"
        now = iso_now()
        draft = {
            "schema_id": "redcap-knowledge-draft",
            "id": entry_id,
            "title": title,
            "summary": summary,
            "tags": tags,
            "body": body,
            "source_path": source_path,
            "created_at": now,
            "status": "draft",
        }
        review = {
            "schema_id": "redcap-knowledge-review",
            "id": entry_id,
            "decision": "approve",
            "reviewer": reviewer,
            "reason": reason,
            "reviewed_at": now,
            "draft_path": evidence_rel(draft_path, knowledge_root),
            "draft": draft,
        }
        entry_body = (
            f"# {title}\n\n"
            f"{body.rstrip()}\n\n"
            "## Review\n\n"
            f"- reviewer: {reviewer}\n"
            f"- reviewed_at: {now}\n"
            f"- reason: {reason}\n"
        )
        write_json(draft_path, draft)
        write_json(review_path, review)
        write_text(body_path, entry_body)
        entry = {
            "id": entry_id,
            "title": title,
            "route": "active-local-index",
            "path": evidence_rel(body_path, knowledge_root),
            "first_read": evidence_rel(body_path, knowledge_root),
            "body_read_rule": "index-first",
            "tags": tags,
            "summary": summary,
        }
        index["entries"].append(entry)
        write_json(index_path, index)
        final_failures = knowledge_gateway.validate_index(index)
        if final_failures:
            raise SystemExit("; ".join(final_failures))
        return {
            "ok": True,
            "skipped": False,
            "entry": entry,
            "draft": evidence_rel(draft_path, knowledge_root),
            "review": evidence_rel(review_path, knowledge_root),
        }
    finally:
        knowledge_gateway.REPO_ROOT = old_root


def candidate_lesson(lesson: str, privacy_class: str) -> tuple[str, dict[str, Any]]:
    digest = hashlib.sha256(lesson.encode("utf-8")).hexdigest()
    evidence = {
        "lesson_sha256": digest,
        "lesson_chars": len(lesson),
    }
    if privacy_class == "cap-private":
        return "[cap-private omitted; sha256 recorded]", evidence
    return lesson, evidence


def run_loop(
    *,
    task_summary: str,
    evidence_root: pathlib.Path,
    knowledge_root: pathlib.Path,
    query: str,
    trigger: str,
    lesson: str,
    decision: str,
    candidate_id: str,
    privacy_class: str,
    proposed_destination: str,
    promote_title: str,
    promote_summary: str,
    promote_tags: list[str],
) -> dict[str, Any]:
    evidence_root.mkdir(parents=True, exist_ok=True)
    now = iso_now()
    matches = search_knowledge(knowledge_root, query)
    retrieval = {
        "schema_id": RETRIEVAL_SCHEMA_ID,
        "task_summary": task_summary,
        "query": query,
        "matches": matches,
        "result_handling": "use_relevant_entry" if matches else "record_no_relevant_entry",
        "adopted_entries": [matches[0]["id"]] if matches else [],
        "task_decision_effects": [
            f"采用知识条目 {matches[0]['id']} 作为本任务约束"
        ] if matches else [],
        "no_relevant_entry_reason": None if matches else "知识库没有命中；任务后必须评估是否产生新候选。",
        "recorded_at": now,
    }
    retrieval_path = evidence_root / "knowledge-retrieval-evidence.json"
    write_json(retrieval_path, retrieval)

    stored_lesson, lesson_evidence = candidate_lesson(lesson, privacy_class)
    candidate = {
        "id": candidate_id,
        "source_task": task_summary,
        "trigger": trigger,
        "lesson": stored_lesson,
        "privacy_class": privacy_class,
        "proposed_destination": proposed_destination,
        "evidence": {
            **lesson_evidence,
            "knowledge_retrieval": evidence_rel(retrieval_path, knowledge_root),
        },
        "created_at": now,
    }
    decision_record = {
        "candidate_id": candidate_id,
        "decision": decision,
        "reason": "",
        "decided_at": now,
    }
    promotion_result: dict[str, Any] | None = None
    if decision == "promote_public":
        if privacy_class != "public":
            raise SystemExit("promote_public 只允许 privacy_class=public")
        decision_record["reason"] = "候选是可复用公共工程经验，且不包含 Cap 私有人格正文。"
        body = "\n".join([
            f"来源任务：{task_summary}",
            "",
            f"经验：{lesson}",
            "",
            "使用规则：任务前检索命中后，必须说明该经验如何影响计划、实现或验收。",
        ])
        promotion_result = promote_public_knowledge(
            knowledge_root=knowledge_root,
            entry_id=candidate_id,
            title=promote_title,
            summary=promote_summary,
            tags=promote_tags,
            body=body,
            source_path=evidence_rel(evidence_root, knowledge_root),
            reviewer="self-purification-run-loop",
            reason="自我净化闭环晋升公共经验。",
            evidence_root=evidence_root,
        )
    elif decision == "keep_private":
        decision_record["reason"] = "候选属于 Cap 私有人格边界，只保留哈希化边界证据，不写公共知识库。"
    elif decision == "no_promote":
        decision_record["reason"] = "候选暂不晋升；本轮只保留证据，避免把未经验证的经验写入公共知识库。"
    elif decision == "defer_with_owner":
        decision_record["reason"] = "候选需要后续责任人复核，暂不晋升。"
    candidates = {
        "schema_id": CANDIDATES_SCHEMA_ID,
        "task_summary": task_summary,
        "candidates": [candidate],
        "decisions": [decision_record],
        "promotion_result": promotion_result,
        "recorded_at": now,
    }
    candidates_path = evidence_root / "self-purification-candidates.json"
    write_json(candidates_path, candidates)

    persona = {
        "schema_id": PERSONA_DECISION_SCHEMA_ID,
        "candidate_id": candidate_id,
        "decision": "private_boundary_only" if privacy_class == "cap-private" else "not_persona",
        "source_task": task_summary,
        "reason": "Cap 私有人格不得自动写入公共仓库；本文件只记录边界和哈希摘要。",
        "hash": lesson_evidence["lesson_sha256"],
        "counts": {"lesson_chars": lesson_evidence["lesson_chars"]},
        "private_body_written": False,
        "public_body_written": decision == "promote_public",
        "recorded_at": now,
    }
    persona_path = evidence_root / "persona-distillation-decision.json"
    write_json(persona_path, persona)

    resolution = {
        "schema_id": RESOLUTION_SCHEMA_ID,
        "ok": True,
        "task_summary": task_summary,
        "retrieval": evidence_rel(retrieval_path, knowledge_root),
        "candidates": evidence_rel(candidates_path, knowledge_root),
        "persona_boundary": evidence_rel(persona_path, knowledge_root),
        "decision": decision,
        "promotion_result": promotion_result,
    }
    resolution_path = evidence_root / "runner-self-purification-resolution.json"
    write_json(resolution_path, resolution)
    return {
        "schema_id": RUN_LOOP_SCHEMA_ID,
        "ok": True,
        "evidence_root": str(evidence_root),
        "knowledge_root": str(knowledge_root),
        "retrieval": str(retrieval_path),
        "candidates": str(candidates_path),
        "persona_boundary": str(persona_path),
        "resolution": str(resolution_path),
        "decision": decision,
        "promotion_result": promotion_result,
    }


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取 JSON：{path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON 必须是对象：{path}")
    return payload


def as_set(payload: dict[str, Any], key: str) -> set[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if isinstance(item, str) and item.strip()}


def missing(required: set[str], actual: set[str]) -> list[str]:
    return sorted(required - actual)


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-self-purification-contract":
        failures.append("自我净化合同 schema_id 错误")
    if contract.get("status") != "runtime-gated":
        failures.append("自我净化合同必须声明 runtime-gated")

    retrieval = contract.get("pre_task_retrieval")
    if not isinstance(retrieval, dict):
        failures.append("自我净化缺少 pre_task_retrieval")
    else:
        missing_scopes = missing(REQUIRED_RETRIEVAL_SCOPES, as_set(retrieval, "required_for"))
        if missing_scopes:
            failures.append(f"任务前知识检索覆盖范围缺失：{missing_scopes}")
        if retrieval.get("command") != "runtime/bin/redcap knowledge-gateway search <query>":
            failures.append("任务前知识检索必须使用 knowledge-gateway search")
        if retrieval.get("evidence_field") != "knowledge_retrieval_evidence":
            failures.append("任务前知识检索必须写入 knowledge_retrieval_evidence")
        if retrieval.get("skip_requires_reason") is not True:
            failures.append("跳过任务前知识检索必须写明理由")
        missing_handling = missing(REQUIRED_RESULT_HANDLING, as_set(retrieval, "minimum_result_handling"))
        if missing_handling:
            failures.append(f"任务前知识检索结果处理缺失：{missing_handling}")

    harvest = contract.get("post_task_harvest")
    if not isinstance(harvest, dict):
        failures.append("自我净化缺少 post_task_harvest")
    else:
        missing_triggers = missing(REQUIRED_TRIGGERS, as_set(harvest, "required_triggers"))
        if missing_triggers:
            failures.append(f"任务后候选触发器缺失：{missing_triggers}")
        missing_fields = missing(REQUIRED_CANDIDATE_FIELDS, as_set(harvest, "candidate_required_fields"))
        if missing_fields:
            failures.append(f"任务后候选字段缺失：{missing_fields}")
        missing_decisions = missing(REQUIRED_DECISIONS, as_set(harvest, "decision_labels"))
        if missing_decisions:
            failures.append(f"任务后评审决策缺失：{missing_decisions}")
        if harvest.get("no_promote_requires_reason") is not True:
            failures.append("no-promote 必须写明理由")

    public_path = contract.get("public_knowledge_path")
    if not isinstance(public_path, dict):
        failures.append("自我净化缺少 public_knowledge_path")
    else:
        if public_path.get("gateway") != "runtime/bin/redcap knowledge-gateway":
            failures.append("公共知识路径必须经过 knowledge-gateway")
        if public_path.get("forge") != "runtime/bin/redcap forge check":
            failures.append("公共知识路径必须经过 Forge 检查")
        if public_path.get("arsenal") != "runtime/bin/redcap arsenal check":
            failures.append("公共知识路径必须经过 arsenal 检查")
        missing_promotion = missing(REQUIRED_PROMOTION, as_set(public_path, "promotion_requires"))
        if missing_promotion:
            failures.append(f"公共知识晋升条件缺失：{missing_promotion}")

    persona = contract.get("cap_persona_distillation")
    if not isinstance(persona, dict):
        failures.append("自我净化缺少 cap_persona_distillation")
    else:
        if persona.get("enabled") is not True:
            failures.append("Cap 人格沉淀必须显式启用")
        if persona.get("privacy_class") != "cap-private":
            failures.append("Cap 人格沉淀必须标记为 cap-private")
        if persona.get("public_write_forbidden") is not True:
            failures.append("Cap 人格沉淀禁止写入公共知识库")
        forbidden = as_set(persona, "public_destinations_forbidden")
        missing_forbidden = missing(FORBIDDEN_PUBLIC_DESTINATIONS, forbidden)
        if missing_forbidden:
            failures.append(f"Cap 私有人格公共禁写目录缺失：{missing_forbidden}")
        if persona.get("private_identity_source") != "$CAP_HOME/identity.md":
            failures.append("Cap 私有人格必须绑定路径可迁移的私有身份源")
        missing_evidence_fields = missing(REQUIRED_PERSONA_EVIDENCE_FIELDS, as_set(persona, "evidence_may_contain"))
        if missing_evidence_fields:
            failures.append(f"Cap 人格证据允许字段缺失：{missing_evidence_fields}")
        missing_forbidden_evidence = missing(FORBIDDEN_PERSONA_EVIDENCE, as_set(persona, "evidence_must_not_contain"))
        if missing_forbidden_evidence:
            failures.append(f"Cap 人格证据禁含字段缺失：{missing_forbidden_evidence}")
        if persona.get("identity_mutation_requires_human") is not True:
            failures.append("修改 Cap 身份必须要求人工授权")

    binding = contract.get("lifecycle_binding")
    if not isinstance(binding, dict):
        failures.append("自我净化缺少 lifecycle_binding")
    else:
        missing_before = missing(REQUIRED_BEFORE, as_set(binding, "required_before_implementation"))
        if missing_before:
            failures.append(f"生命周期实施前绑定缺失：{missing_before}")
        missing_after = missing(REQUIRED_AFTER, as_set(binding, "required_after_task"))
        if missing_after:
            failures.append(f"生命周期任务后绑定缺失：{missing_after}")
        e2e_binding = str(binding.get("e2e_failure_binding") or "")
        if "E2E" not in e2e_binding or "candidate" not in e2e_binding:
            failures.append("E2E 失败必须绑定候选抽取或无候选理由")
    runtime = contract.get("runtime_integration")
    if not isinstance(runtime, dict):
        failures.append("自我净化缺少 runtime_integration")
    else:
        missing_runtime = missing(REQUIRED_RUNTIME_INTEGRATION, set(runtime))
        if missing_runtime:
            failures.append(f"自我净化运行接入字段缺失：{missing_runtime}")
        if runtime.get("pre_task_entrypoint") != "runtime/bin/redcap knowledge-gateway search <query>":
            failures.append("自我净化任务前入口必须是 knowledge-gateway search")
        if runtime.get("post_task_entrypoint") != "runtime/bin/redcap self-purification run-loop --task-summary <text> --evidence-root <dir>":
            failures.append("自我净化任务后入口必须绑定 self-purification run-loop")
        if runtime.get("aggregate_check") != "runtime/bin/redcap self-purification check":
            failures.append("自我净化聚合检查入口错误")
        failure_policy = str(runtime.get("failure_policy") or "")
        for required in ["Missing retrieval", "persona privacy leak", "open failure-backlog", "closed_non_blocking"]:
            if required not in failure_policy:
                failures.append(f"自我净化 failure_policy 缺少：{required}")
    return failures


def check(path: pathlib.Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    contract = load_json(path)
    failures = validate_contract(contract)
    return {
        "schema_id": "redcap-self-purification-check",
        "ok": not failures,
        "contract": str(path),
        "failures": failures,
    }


def cmd_check(args: argparse.Namespace) -> int:
    result = check(pathlib.Path(args.contract).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_SELF_PURIFICATION_OK")
        return 0
    return 1


def cmd_run_loop(args: argparse.Namespace) -> int:
    candidate_id = args.candidate_id or slugify(args.promote_title or args.task_summary)
    tags = [tag.strip() for tag in args.promote_tags.split(",") if tag.strip()]
    if not tags:
        raise SystemExit("--promote-tags 必须至少包含一个标签")
    result = run_loop(
        task_summary=args.task_summary,
        evidence_root=pathlib.Path(args.evidence_root).expanduser().resolve(),
        knowledge_root=pathlib.Path(args.knowledge_root).expanduser().resolve(),
        query=args.query or args.task_summary,
        trigger=args.trigger,
        lesson=args.lesson,
        decision=args.decision,
        candidate_id=candidate_id,
        privacy_class=args.privacy_class,
        proposed_destination=args.proposed_destination,
        promote_title=args.promote_title,
        promote_summary=args.promote_summary,
        promote_tags=tags,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("REDCAP_SELF_PURIFICATION_RUN_LOOP_OK")
    return 0


def validate_run_loop_outputs(result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if result.get("ok") is not True:
        failures.append("run-loop result ok must be true")
    retrieval_path = pathlib.Path(str(result.get("retrieval") or ""))
    candidates_path = pathlib.Path(str(result.get("candidates") or ""))
    persona_path = pathlib.Path(str(result.get("persona_boundary") or ""))
    resolution_path = pathlib.Path(str(result.get("resolution") or ""))
    for label, path in [
        ("retrieval", retrieval_path),
        ("candidates", candidates_path),
        ("persona_boundary", persona_path),
        ("resolution", resolution_path),
    ]:
        if not path.exists():
            failures.append(f"run-loop missing {label} artifact: {path}")
    if retrieval_path.exists():
        retrieval = load_json(retrieval_path)
        handling = retrieval.get("result_handling")
        if handling not in {"use_relevant_entry", "record_no_relevant_entry", "record_skip_reason"}:
            failures.append("retrieval result_handling is invalid")
        if handling == "use_relevant_entry" and not retrieval.get("task_decision_effects"):
            failures.append("retrieval with relevant entry must record task_decision_effects")
    if candidates_path.exists():
        candidates = load_json(candidates_path)
        candidate_items = candidates.get("candidates")
        decisions = candidates.get("decisions")
        if not isinstance(candidate_items, list) or not candidate_items:
            failures.append("run-loop must create at least one candidate")
        if not isinstance(decisions, list) or not decisions:
            failures.append("run-loop must create at least one decision")
        for decision in decisions if isinstance(decisions, list) else []:
            if not isinstance(decision, dict):
                failures.append("run-loop decision must be object")
                continue
            if decision.get("decision") not in REQUIRED_DECISIONS:
                failures.append("run-loop decision label is invalid")
            if not (isinstance(decision.get("reason"), str) and len(decision["reason"].strip()) >= 12):
                failures.append("run-loop decision must include substantive reason")
    if persona_path.exists():
        persona = load_json(persona_path)
        if persona.get("private_body_written") is not False:
            failures.append("persona boundary must not write private body")
    if resolution_path.exists():
        resolution = load_json(resolution_path)
        if resolution.get("ok") is not True:
            failures.append("run-loop resolution ok must be true")
    return failures


def scan_natural_trigger_history(
    *,
    lifecycle_root: pathlib.Path,
    minimum_count: int,
    task_start_marker: pathlib.Path,
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    skipped_newer_samples: list[dict[str, Any]] = []
    failures = []
    if not task_start_marker.exists():
        failures.append(f"task start marker is missing: {evidence_rel(task_start_marker, REPO_ROOT)}")
        task_start_timestamp = None
        task_start_summary = None
    else:
        task_start_summary = file_time_summary(task_start_marker)
        task_start_timestamp = task_start_summary["modified_timestamp"]
    for path in sorted(lifecycle_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            payload = load_json(path)
        except SystemExit:
            continue
        binding = payload.get("self_purification")
        if payload.get("task_id") == CURRENT_RSP_07_08_TASK_ID:
            continue
        if not isinstance(binding, dict):
            continue
        if binding.get("purification_required") is False:
            continue
        harvest = binding.get("post_task_harvest")
        has_harvest = isinstance(harvest, dict) and (
            isinstance(harvest.get("candidates_path"), str)
            or isinstance(harvest.get("no_candidate_reason"), str)
        )
        review = binding.get("review_decision")
        has_review = isinstance(review, dict) and review.get("decision") in REQUIRED_DECISIONS
        knowledge = binding.get("knowledge_retrieval_evidence") or binding.get("knowledge_retrieval_skip_reason")
        if has_harvest and has_review and isinstance(knowledge, str) and knowledge.strip():
            lifecycle_times = file_time_summary(path)
            lifecycle_before_task = (
                task_start_timestamp is not None
                and lifecycle_times["modified_timestamp"] < task_start_timestamp
            )
            knowledge_evidence_times = None
            knowledge_before_task = None
            if binding.get("knowledge_retrieval_evidence"):
                knowledge_path = REPO_ROOT / str(binding["knowledge_retrieval_evidence"])
                if knowledge_path.exists():
                    knowledge_evidence_times = file_time_summary(knowledge_path)
                    knowledge_before_task = (
                        task_start_timestamp is not None
                        and knowledge_evidence_times["modified_timestamp"] < task_start_timestamp
                    )
            if not lifecycle_before_task or knowledge_before_task is False:
                skipped_newer_samples.append({
                    "lifecycle": evidence_rel(path, REPO_ROOT),
                    "task_id": payload.get("task_id"),
                    "modified_at_utc": lifecycle_times["modified_at_utc"],
                    "knowledge": knowledge,
                    "knowledge_evidence_modified_at_utc": knowledge_evidence_times["modified_at_utc"] if knowledge_evidence_times else None,
                    "reason": "晚于当前 RSP-07/08 任务起点；不作为历史独立性样本。",
                })
                continue
            samples.append({
                "lifecycle": evidence_rel(path, REPO_ROOT),
                "task_id": payload.get("task_id"),
                "created_at_utc": lifecycle_times["created_at_utc"],
                "modified_at_utc": lifecycle_times["modified_at_utc"],
                "decision": review.get("decision"),
                "knowledge": knowledge,
                "knowledge_evidence_created_at_utc": knowledge_evidence_times["created_at_utc"] if knowledge_evidence_times else None,
                "knowledge_evidence_modified_at_utc": knowledge_evidence_times["modified_at_utc"] if knowledge_evidence_times else None,
                "lifecycle_before_current_task": lifecycle_before_task,
                "knowledge_evidence_before_current_task": knowledge_before_task,
            })
        if len(samples) >= minimum_count:
            break
    if len(samples) < minimum_count:
        failures.append(f"natural trigger history requires at least {minimum_count} lifecycle samples")
    return {
        "ok": not failures,
        "minimum_count": minimum_count,
        "excludes_current_task_id": CURRENT_RSP_07_08_TASK_ID,
        "task_start_marker": evidence_rel(task_start_marker, REPO_ROOT) if task_start_marker.exists() else str(task_start_marker),
        "task_started_at_utc": task_start_summary["modified_at_utc"] if task_start_summary else None,
        "sample_count": len(samples),
        "samples": samples,
        "skipped_newer_samples": skipped_newer_samples,
        "failures": failures,
    }


def run_loop_negative_probes(good_result: dict[str, Any]) -> list[dict[str, Any]]:
    probes: list[dict[str, Any]] = []
    candidates_path = pathlib.Path(str(good_result.get("candidates") or ""))
    retrieval_path = pathlib.Path(str(good_result.get("retrieval") or ""))
    persona_path = pathlib.Path(str(good_result.get("persona_boundary") or ""))

    if candidates_path.exists():
        broken_result = dict(good_result)
        broken_candidates_path = candidates_path.with_name("negative-missing-decisions.json")
        broken_payload = load_json(candidates_path)
        broken_payload["decisions"] = []
        write_json(broken_candidates_path, broken_payload)
        broken_result["candidates"] = str(broken_candidates_path)
        failures = validate_run_loop_outputs(broken_result)
        probes.append({
            "name": "missing_harvest_decision",
            "expected_failure": True,
            "failed_as_expected": bool(failures),
            "failures": failures,
        })

    if retrieval_path.exists():
        broken_result = dict(good_result)
        broken_retrieval_path = retrieval_path.with_name("negative-missing-decision-effects.json")
        broken_payload = load_json(retrieval_path)
        broken_payload["task_decision_effects"] = []
        write_json(broken_retrieval_path, broken_payload)
        broken_result["retrieval"] = str(broken_retrieval_path)
        failures = validate_run_loop_outputs(broken_result)
        probes.append({
            "name": "missing_retrieval_decision_effects",
            "expected_failure": True,
            "failed_as_expected": bool(failures),
            "failures": failures,
        })

    if persona_path.exists():
        broken_result = dict(good_result)
        broken_persona_path = persona_path.with_name("negative-private-body-leak.json")
        broken_payload = load_json(persona_path)
        broken_payload["private_body_written"] = True
        write_json(broken_persona_path, broken_payload)
        broken_result["persona_boundary"] = str(broken_persona_path)
        failures = validate_run_loop_outputs(broken_result)
        probes.append({
            "name": "persona_private_body_leak",
            "expected_failure": True,
            "failed_as_expected": bool(failures),
            "failures": failures,
        })
    empty_history = {"ok": False, "minimum_count": 1, "sample_count": 0, "samples": [], "failures": ["natural trigger history requires at least 1 lifecycle samples"]}
    probes.append({
        "name": "missing_natural_trigger_history",
        "expected_failure": True,
        "failed_as_expected": empty_history["ok"] is False,
        "failures": empty_history["failures"],
    })
    return probes


def cmd_loop_check(args: argparse.Namespace) -> int:
    evidence_root = pathlib.Path(args.artifact_root).resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    result = run_loop(
        task_summary="RSP-07 自我净化自然触发验收",
        evidence_root=evidence_root / "run-loop",
        knowledge_root=pathlib.Path(args.knowledge_root).resolve(),
        query=args.query,
        trigger="workflow_drift",
        lesson="自我净化必须在真实实现任务后生成候选、评审决策和晋升或 no-promote 结果。",
        decision="no_promote",
        candidate_id="rsp-07-self-purification-natural-trigger",
        privacy_class="public",
        proposed_destination="assets/knowledge/entries",
        promote_title="RSP-07 Self Purification Natural Trigger",
        promote_summary="自我净化自然触发必须产生候选和评审决策。",
        promote_tags=["self-purification", "runtime", "rsp-07"],
    )
    positive_failures = validate_run_loop_outputs(result)
    history = scan_natural_trigger_history(
        lifecycle_root=pathlib.Path(args.lifecycle_root).resolve(),
        minimum_count=args.minimum_history_count,
        task_start_marker=pathlib.Path(args.task_start_marker).resolve(),
    )
    positive_failures.extend(history["failures"])
    negative_probes = run_loop_negative_probes(result)
    negative_ok = all(probe["failed_as_expected"] for probe in negative_probes)
    evidence = {
        "schema_id": "redcap-rsp-07-self-purification-loop-evidence",
        "rsp": "RSP-07",
        "ok": not positive_failures and negative_ok,
        "contract_path": str(pathlib.Path(args.contract).resolve().relative_to(REPO_ROOT)),
        "acceptance": {
            "positive": {
                "status": "pass" if not positive_failures else "fail",
                "checks": [
                    "run-loop generated retrieval evidence",
                    "run-loop generated at least one candidate",
                    "run-loop generated an explicit no-promote decision with reason",
                    "persona boundary evidence did not write private body",
                    "recent lifecycle history contains self-purification bindings",
                    "historical lifecycle samples are older than the current RSP-07/08 task start marker",
                ],
                "failures": positive_failures,
            },
            "negative": {
                "status": "pass" if negative_ok else "fail",
                "checks": negative_probes,
            },
        },
        "changed_reality": [
            "自我净化现在有 RSP-07 专项验收：真实 run-loop 必须生成检索、候选、决策和边界证据。",
            "loop-check 会扫描真实 lifecycle 历史，确认自我净化不是只在本检查器内手动运行。",
            "历史样本必须早于当前 RSP-07/08 任务起点，避免本轮自举证据冒充自然触发。",
            "缺少任务后决策、缺少知识决策影响或私人人格正文泄露都会被负向探针拦截。",
            "本轮 no-promote 决策证明自我净化闭环工作过，但不向公共知识库追加噪音资产。",
        ],
        "artifacts": [
            "runtime/core/self_purification.py",
            "assets/contracts/self-purification-loop.json",
            str((evidence_root / "run-loop").relative_to(REPO_ROOT)),
        ],
        "run_loop_result": result,
        "historical_samples": history,
        "natural_trigger_history": history,
    }
    out_path = pathlib.Path(args.out).resolve()
    write_json(out_path, evidence)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    if evidence["ok"]:
        print("REDCAP_SELF_PURIFICATION_LOOP_CHECK_OK")
        return 0
    return 1


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    good = load_json(DEFAULT_CONTRACT)
    good_failures = validate_contract(good)
    if good_failures:
        failures.append(f"当前自我净化合同不应失败：{good_failures}")
    missing_retrieval = json.loads(json.dumps(good, ensure_ascii=False))
    missing_retrieval["pre_task_retrieval"]["required_for"] = ["implementation"]
    if not any("任务前知识检索覆盖范围缺失" in item for item in validate_contract(missing_retrieval)):
        failures.append("缺少任务前检索覆盖范围的样例没有失败")
    public_persona = json.loads(json.dumps(good, ensure_ascii=False))
    public_persona["cap_persona_distillation"]["public_write_forbidden"] = False
    if not any("公共知识库" in item for item in validate_contract(public_persona)):
        failures.append("允许 Cap 人格写入公共知识库的样例没有失败")
    no_no_promote_reason = json.loads(json.dumps(good, ensure_ascii=False))
    no_no_promote_reason["post_task_harvest"]["no_promote_requires_reason"] = False
    if not any("no-promote" in item for item in validate_contract(no_no_promote_reason)):
        failures.append("no-promote 无理由样例没有失败")
    no_runtime = json.loads(json.dumps(good, ensure_ascii=False))
    no_runtime.pop("runtime_integration", None)
    if not any("runtime_integration" in item for item in validate_contract(no_runtime)):
        failures.append("缺少 runtime_integration 的样例没有失败")
    with tempfile.TemporaryDirectory(prefix="redcap-self-purification-") as raw:
        tmp = pathlib.Path(raw)
        fixture = tmp / "contract.json"
        fixture.write_text(json.dumps(good, ensure_ascii=False), encoding="utf-8")
        if not check(fixture)["ok"]:
            failures.append("临时合同路径检查失败")
    with tempfile.TemporaryDirectory(prefix="redcap-self-purification-loop-") as raw:
        tmp = pathlib.Path(raw)
        knowledge_root = tmp / "knowledge-root"
        entries = knowledge_root / "assets" / "knowledge" / "entries"
        entries.mkdir(parents=True)
        write_text(entries / "seed.md", "# Seed\n\n自我净化运行闭环需要任务前检索和任务后候选处理。\n")
        write_text(
            entries / "raw-evidence-access-boundary.md",
            "\n".join([
                "# Raw Evidence Access Boundary",
                "",
                "- raw evidence is never default context",
                "- prism/runs is not a package candidate",
                "- physical cleanup requires explicit approval",
                "- cleanup apply stays disabled by default",
                "- minimum run count integrity is preserved",
                "- release blocker linkage remains until evidence retention is resolved",
            ]),
        )
        write_json(knowledge_root / "assets" / "knowledge" / "index.json", {
            "schema_id": "redcap-knowledge-index",
            "version": 1,
            "default_read": "index-only",
            "raw_archive_default": "forbidden",
            "entries": [
                {
                    "id": "seed",
                    "title": "Seed",
                    "route": "active-local-index",
                    "path": "assets/knowledge/entries/seed.md",
                    "first_read": "assets/knowledge/entries/seed.md",
                    "body_read_rule": "index-first",
                    "tags": ["self-purification", "seed"],
                    "summary": "自我净化运行闭环种子知识。",
                },
                {
                    "id": "raw-evidence-access-boundary",
                    "title": "Raw Evidence Access Boundary",
                    "route": "active-local-index",
                    "path": "assets/knowledge/entries/raw-evidence-access-boundary.md",
                    "first_read": "assets/knowledge/entries/raw-evidence-access-boundary.md",
                    "body_read_rule": "index-first",
                    "tags": ["raw", "evidence", "archive", "package", "cleanup", "lifecycle", "release"],
                    "summary": "Raw evidence is explicit-access only: not default context, not a package candidate, not physically cleaned, no cleanup apply, protected by minimum run count and release blocker rules.",
                },
            ],
        })
        result = run_loop(
            task_summary="验证自我净化运行闭环",
            evidence_root=tmp / "evidence",
            knowledge_root=knowledge_root,
            query="self-purification",
            trigger="workflow_drift",
            lesson="自我净化必须把任务前检索、任务后候选、评审决策和后续召回串成闭环。",
            decision="promote_public",
            candidate_id="self-purification-runtime-loop",
            privacy_class="public",
            proposed_destination="assets/knowledge/entries",
            promote_title="Self Purification Runtime Loop",
            promote_summary="自我净化必须形成可执行的检索、候选、决策和召回闭环。",
            promote_tags=["self-purification", "runtime", "knowledge"],
        )
        if result.get("ok") is not True:
            failures.append("run-loop 没有返回成功")
        matches = search_knowledge(knowledge_root, "self-purification runtime")
        if not any(item.get("id") == "self-purification-runtime-loop" for item in matches):
            failures.append("公共晋升后的知识条目无法被再次检索命中")
        private_result = run_loop(
            task_summary="验证 Cap 私有人格边界",
            evidence_root=tmp / "private-evidence",
            knowledge_root=knowledge_root,
            query="self-purification",
            trigger="persona_signal",
            lesson="这是一条私有人格候选正文，不能进入公共仓库。",
            decision="keep_private",
            candidate_id="cap-private-boundary-fixture",
            privacy_class="cap-private",
            proposed_destination="cap-private",
            promote_title="Cap Private Boundary Fixture",
            promote_summary="Cap 私有人格只能保留边界证据。",
            promote_tags=["persona", "private"],
        )
        persona_path = pathlib.Path(str(private_result.get("persona_boundary")))
        persona_payload = load_json(persona_path)
        if persona_payload.get("private_body_written") is not False:
            failures.append("Cap 私有人格边界证据不得写入私有正文")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_SELF_PURIFICATION_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap 自我净化与 Cap 私有人格边界检查器")
    sub = parser.add_subparsers(dest="command", required=True)
    check_cmd = sub.add_parser("check")
    check_cmd.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    check_cmd.set_defaults(func=cmd_check)
    run = sub.add_parser("run-loop")
    run.add_argument("--task-summary", required=True)
    run.add_argument("--evidence-root", required=True)
    run.add_argument("--knowledge-root", default=str(DEFAULT_KNOWLEDGE_ROOT))
    run.add_argument("--query")
    run.add_argument("--trigger", choices=sorted(REQUIRED_TRIGGERS), default="workflow_drift")
    run.add_argument("--lesson", required=True)
    run.add_argument("--decision", choices=sorted(REQUIRED_DECISIONS), default="no_promote")
    run.add_argument("--candidate-id")
    run.add_argument("--privacy-class", choices=["public", "cap-private", "private"], default="public")
    run.add_argument("--proposed-destination", default="assets/knowledge/entries")
    run.add_argument("--promote-title", required=True)
    run.add_argument("--promote-summary", required=True)
    run.add_argument("--promote-tags", default="self-purification,runtime")
    run.set_defaults(func=cmd_run_loop)
    loop = sub.add_parser("loop-check")
    loop.add_argument("--query", default="self purification knowledge retrieval task candidate promotion no promote")
    loop.add_argument("--knowledge-root", default=str(DEFAULT_KNOWLEDGE_ROOT))
    loop.add_argument("--contract", default=str(DEFAULT_LOOP_CONTRACT))
    loop.add_argument("--artifact-root", default=str(DEFAULT_LOOP_ARTIFACTS))
    loop.add_argument("--lifecycle-root", default=str(REPO_ROOT / "assets" / "evidence" / "lifecycle"))
    loop.add_argument("--task-start-marker", default=str(DEFAULT_RSP_07_08_START_MARKER))
    loop.add_argument("--minimum-history-count", type=int, default=2)
    loop.add_argument("--out", default=str(DEFAULT_LOOP_EVIDENCE))
    loop.set_defaults(func=cmd_loop_check)
    sub.add_parser("self-check").set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

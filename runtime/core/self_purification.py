#!/usr/bin/env python3
"""RedCap 自我净化与 Cap 私有人格沉淀边界检查器。"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = REPO_ROOT / "assets" / "contracts" / "self-purification.json"

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
        if persona.get("private_identity_source") != "/Users/norven/.cap/identity.md":
            failures.append("Cap 私有人格必须绑定私有身份源")
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
    with tempfile.TemporaryDirectory(prefix="redcap-self-purification-") as raw:
        tmp = pathlib.Path(raw)
        fixture = tmp / "contract.json"
        fixture.write_text(json.dumps(good, ensure_ascii=False), encoding="utf-8")
        if not check(fixture)["ok"]:
            failures.append("临时合同路径检查失败")
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
    sub.add_parser("self-check").set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

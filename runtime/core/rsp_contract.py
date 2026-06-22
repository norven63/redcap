#!/usr/bin/env python3
"""检查 RSP 完成口径合同，防止方案、账本或报告替代实际完成。"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_PLAN = REPO_ROOT / "assets" / "docs" / "residual-todo-final-solution-plan.md"
SCHEMA_ID = "redcap-rsp-contract-check"
RSP_ID_RE = re.compile(r"^RSP-\d{2}$")
EXPECTED_RSP_IDS = [f"RSP-{index:02d}" for index in range(28)]
PLAN_CHANGE_CONTROL = "plan-change-control"
PROOF_ONLY_TERMS = {
    "文档",
    "方案",
    "方案书",
    "账本",
    "报告",
    "摘要",
    "清单",
    "记录",
    "复盘",
    "说明",
    "评审",
    "review",
    "digest",
    "ledger",
    "report",
    "doc",
    "docs",
    "document",
    "plan",
    "checklist",
}
REALITY_CHANGE_TERMS = {
    "runtime/",
    "runtime/bin/redcap",
    "runtime/core/",
    ".redcap/evidence/rsp/",
    "check",
    "self-check",
    "测试",
    "自检",
    "命令",
    "检查器",
    "阻断",
    "拒绝",
    "执行",
    "运行",
    "验证",
    "解析",
    "生成",
    "写入",
    "读取",
    "迁移",
    "隔离",
    "hook",
    "钩子",
    "session",
    "会话",
    "cli",
    "code",
    "source",
    "artifact",
}


def load_json_object(path: pathlib.Path, label: str, failures: list[str]) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"{label} 无法读取：{path}: {exc}")
        return None
    if not isinstance(payload, dict):
        failures.append(f"{label} 必须是 JSON 对象：{path}")
        return None
    return payload


def strip_cell(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`") and len(value) >= 2:
        return value[1:-1].strip()
    return value


def split_table_row(line: str) -> list[str]:
    raw = line.strip()
    if not (raw.startswith("|") and raw.endswith("|")):
        return []
    return [strip_cell(cell) for cell in raw.strip("|").split("|")]


def section_name(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    return stripped


def parse_plan(path: pathlib.Path) -> tuple[dict[str, Any] | None, list[str]]:
    failures: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [f"方案书无法读取：{path}: {exc}"]

    matrix: dict[str, dict[str, str]] = {}
    evidence_paths: dict[str, str] = {}
    current_section: str | None = None
    for line in text.splitlines():
        heading = section_name(line)
        if heading is not None:
            current_section = heading
            continue
        cells = split_table_row(line)
        if not cells or not RSP_ID_RE.fullmatch(cells[0]):
            continue
        rsp_id = cells[0]
        if current_section == "## 2.2 可执行验收矩阵" and len(cells) >= 4:
            matrix[rsp_id] = {
                "positive": cells[1],
                "negative": cells[2],
                "evidence_hint": cells[3],
            }
        elif current_section == "### 2.2.1 完成声明证据路径" and len(cells) >= 2:
            evidence_paths[rsp_id] = cells[1]

    if (
        "RSP-00" in evidence_paths
        and "RSP-00 的最小机器防线" in text
        and "最小通过条件" in text
        and "最小检查语义" in text
    ):
        matrix["RSP-00"] = {
            "positive": "rsp-contract check 能验证方案、claim_file 和 evidence_file",
            "negative": "未知 RSP、证据不匹配、新问题未入队必须失败",
            "evidence_hint": evidence_paths["RSP-00"],
        }

    missing_matrix = [rsp_id for rsp_id in EXPECTED_RSP_IDS if rsp_id not in matrix]
    missing_evidence = [rsp_id for rsp_id in EXPECTED_RSP_IDS if rsp_id not in evidence_paths]
    if missing_matrix:
        failures.append(f"方案书缺少正向/负向验收矩阵：{missing_matrix}")
    if missing_evidence:
        failures.append(f"方案书缺少完成证据路径：{missing_evidence}")

    for rsp_id, item in sorted(matrix.items()):
        if not item["positive"].strip():
            failures.append(f"{rsp_id} 缺少正向验收")
        if not item["negative"].strip():
            failures.append(f"{rsp_id} 缺少负向探针")
    for rsp_id, evidence in sorted(evidence_paths.items()):
        if not evidence.startswith(".redcap/evidence/rsp/"):
            failures.append(f"{rsp_id} 完成证据路径必须位于 .redcap/evidence/rsp/：{evidence}")

    return {
        "path": str(path),
        "matrix": matrix,
        "evidence_paths": evidence_paths,
        "rsp_ids": sorted(set(matrix) | set(evidence_paths)),
    }, failures


def resolve_reference(raw: str, *, base_dir: pathlib.Path) -> pathlib.Path:
    path = pathlib.Path(raw)
    if path.is_absolute():
        return path.resolve()
    return (base_dir / path).resolve()


def same_reference(left: str, right: str, *, base_dir: pathlib.Path) -> bool:
    return resolve_reference(left, base_dir=base_dir) == resolve_reference(right, base_dir=base_dir)


def required_fields(payload: dict[str, Any], fields: list[str], label: str, failures: list[str]) -> None:
    for field in fields:
        if field not in payload:
            failures.append(f"{label} 缺少必填字段：{field}")


def collect_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(collect_strings(item))
        return items
    if isinstance(value, dict):
        items = []
        for item in value.values():
            items.extend(collect_strings(item))
        return items
    return []


def has_runtime_reality_signal(value: Any) -> bool:
    haystack = "\n".join(collect_strings(value)).casefold()
    return any(term.casefold() in haystack for term in REALITY_CHANGE_TERMS)


def looks_proof_only(value: Any) -> bool:
    texts = collect_strings(value)
    if not texts:
        return True
    haystack = "\n".join(texts).casefold()
    has_proof_term = any(term.casefold() in haystack for term in PROOF_ONLY_TERMS)
    return has_proof_term and not has_runtime_reality_signal(value)


def check_claim(
    *,
    rsp_id: str,
    claim_file: pathlib.Path,
    evidence_file_arg: str,
    plan_rsp_ids: set[str],
    failures: list[str],
) -> dict[str, Any] | None:
    claim = load_json_object(claim_file, "claim_file", failures)
    if claim is None:
        return None
    required_fields(claim, ["rsp", "claim_scope", "completion_level", "evidence_file", "new_issues"], "claim_file", failures)
    if claim.get("rsp") != rsp_id:
        failures.append(f"claim_file.rsp 必须等于 {rsp_id}")
    if not (isinstance(claim.get("claim_scope"), str) and claim["claim_scope"].strip()):
        failures.append("claim_file.claim_scope 必须非空")
    if not (isinstance(claim.get("completion_level"), str) and claim["completion_level"].strip()):
        failures.append("claim_file.completion_level 必须非空")
    if not (isinstance(claim.get("evidence_file"), str) and claim["evidence_file"].strip()):
        failures.append("claim_file.evidence_file 必须非空")
    if not isinstance(claim.get("new_issues"), list):
        failures.append("claim_file.new_issues 必须是数组")
        return claim
    for index, issue in enumerate(claim.get("new_issues", []), start=1):
        if not isinstance(issue, dict):
            failures.append(f"claim_file.new_issues[{index}] 必须是对象")
            continue
        target = issue.get("queue_target")
        if target not in plan_rsp_ids and target != PLAN_CHANGE_CONTROL:
            failures.append(f"claim_file.new_issues[{index}].queue_target 必须指向已有 RSP 或 plan-change-control")
    if isinstance(claim.get("evidence_file"), str) and not same_reference(
        claim["evidence_file"],
        evidence_file_arg,
        base_dir=REPO_ROOT,
    ):
        failures.append("completion claim does not reference required evidence file")
    return claim


def acceptance_status(payload: dict[str, Any], *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def check_evidence(
    *,
    rsp_id: str,
    evidence_file: pathlib.Path,
    failures: list[str],
) -> dict[str, Any] | None:
    evidence = load_json_object(evidence_file, "evidence_file", failures)
    if evidence is None:
        return None
    required_fields(evidence, ["rsp", "acceptance", "changed_reality", "artifacts"], "evidence_file", failures)
    if evidence.get("rsp") != rsp_id:
        failures.append(f"evidence_file.rsp 必须等于 {rsp_id}")
    positive = acceptance_status(evidence, "acceptance", "positive")
    negative = acceptance_status(evidence, "acceptance", "negative")
    if acceptance_status(evidence, "acceptance", "positive", "status") != "pass":
        failures.append("evidence_file.acceptance.positive.status 必须是 pass")
    if acceptance_status(evidence, "acceptance", "negative", "status") != "pass":
        failures.append("evidence_file.acceptance.negative.status 必须是 pass")
    if isinstance(positive, dict) and not isinstance(positive.get("checks"), list):
        failures.append("evidence_file.acceptance.positive.checks 必须是数组")
    if isinstance(negative, dict) and not isinstance(negative.get("checks"), list):
        failures.append("evidence_file.acceptance.negative.checks 必须是数组")
    if not isinstance(evidence.get("changed_reality"), list):
        failures.append("evidence_file.changed_reality 必须是数组")
    elif not evidence["changed_reality"]:
        failures.append("evidence_file.changed_reality 必须非空，且必须描述实际行为变化")
    elif looks_proof_only(evidence["changed_reality"]):
        failures.append("evidence_file.changed_reality 不能只有文档、账本、报告或评审描述，必须包含实际行为变化")
    if not isinstance(evidence.get("artifacts"), list):
        failures.append("evidence_file.artifacts 必须是数组")
    elif not evidence["artifacts"]:
        failures.append("evidence_file.artifacts 必须非空，且必须引用实际产物或可重复命令")
    elif looks_proof_only(evidence["artifacts"]):
        failures.append("evidence_file.artifacts 不能只有文档、账本、报告或评审产物，必须引用实际产物或可重复命令")
    return evidence


def build_result(
    *,
    plan_path: pathlib.Path,
    rsp_id: str | None,
    claim_file: pathlib.Path | None,
    evidence_file: pathlib.Path | None,
    checks: dict[str, Any],
    failures: list[str],
) -> dict[str, Any]:
    return {
        "schema_id": SCHEMA_ID,
        "ok": not failures,
        "rsp": rsp_id,
        "plan_path": str(plan_path),
        "claim_file": str(claim_file) if claim_file else None,
        "evidence_file": str(evidence_file) if evidence_file else None,
        "checks": checks,
        "failures": failures,
    }


def run_check(
    *,
    plan_path: pathlib.Path,
    rsp_id: str | None,
    claim_file: pathlib.Path | None,
    evidence_file: pathlib.Path | None,
) -> dict[str, Any]:
    failures: list[str] = []
    plan, plan_failures = parse_plan(plan_path)
    failures.extend(plan_failures)

    matrix = plan.get("matrix", {}) if plan else {}
    evidence_paths = plan.get("evidence_paths", {}) if plan else {}
    plan_rsp_ids = set(plan.get("rsp_ids", [])) if plan else set()

    checks: dict[str, Any] = {
        "plan_has_all_rsp": not [rsp for rsp in EXPECTED_RSP_IDS if rsp not in plan_rsp_ids],
        "all_rsp_have_positive_acceptance": not [rsp for rsp in EXPECTED_RSP_IDS if rsp not in matrix],
        "all_rsp_have_negative_probe": not [rsp for rsp in EXPECTED_RSP_IDS if rsp not in matrix],
        "all_rsp_have_evidence_path": not [rsp for rsp in EXPECTED_RSP_IDS if rsp not in evidence_paths],
        "has_positive_acceptance": None,
        "has_negative_probe": None,
        "claim_references_evidence": None,
        "new_issue_is_queued": None,
    }

    if rsp_id is None:
        if claim_file or evidence_file:
            failures.append("--claim-file 和 --evidence-file 需要同时指定 --rsp")
        return build_result(
            plan_path=plan_path,
            rsp_id=rsp_id,
            claim_file=claim_file,
            evidence_file=evidence_file,
            checks=checks,
            failures=failures,
        )

    if not RSP_ID_RE.fullmatch(rsp_id):
        failures.append(f"--rsp 格式非法：{rsp_id}")
    elif rsp_id not in plan_rsp_ids:
        failures.append(f"未知 RSP：{rsp_id}")

    checks["has_positive_acceptance"] = rsp_id in matrix and bool(matrix.get(rsp_id, {}).get("positive"))
    checks["has_negative_probe"] = rsp_id in matrix and bool(matrix.get(rsp_id, {}).get("negative"))

    if claim_file is None:
        failures.append("--rsp 检查必须提供 --claim-file")
    if evidence_file is None:
        failures.append("--rsp 检查必须提供 --evidence-file")
    if claim_file is None or evidence_file is None:
        return build_result(
            plan_path=plan_path,
            rsp_id=rsp_id,
            claim_file=claim_file,
            evidence_file=evidence_file,
            checks=checks,
            failures=failures,
        )

    claim_failure_start = len(failures)
    claim = check_claim(
        rsp_id=rsp_id,
        claim_file=claim_file,
        evidence_file_arg=str(evidence_file),
        plan_rsp_ids=plan_rsp_ids,
        failures=failures,
    )
    evidence = check_evidence(rsp_id=rsp_id, evidence_file=evidence_file, failures=failures)

    checks["claim_references_evidence"] = bool(
        claim
        and isinstance(claim.get("evidence_file"), str)
        and same_reference(claim["evidence_file"], str(evidence_file), base_dir=REPO_ROOT)
    )
    checks["new_issue_is_queued"] = bool(
        claim
        and isinstance(claim.get("new_issues"), list)
        and all(
            isinstance(issue, dict)
            and (issue.get("queue_target") in plan_rsp_ids or issue.get("queue_target") == PLAN_CHANGE_CONTROL)
            for issue in claim.get("new_issues", [])
        )
    )
    if evidence is not None:
        checks["has_positive_acceptance"] = checks["has_positive_acceptance"] and (
            acceptance_status(evidence, "acceptance", "positive", "status") == "pass"
        )
        checks["has_negative_probe"] = checks["has_negative_probe"] and (
            acceptance_status(evidence, "acceptance", "negative", "status") == "pass"
        )
    if len(failures) == claim_failure_start and not checks["claim_references_evidence"]:
        failures.append("completion claim does not reference required evidence file")

    return build_result(
        plan_path=plan_path,
        rsp_id=rsp_id,
        claim_file=claim_file,
        evidence_file=evidence_file,
        checks=checks,
        failures=failures,
    )


def cmd_check(args: argparse.Namespace) -> int:
    result = run_check(
        plan_path=pathlib.Path(args.plan).resolve(),
        rsp_id=args.rsp,
        claim_file=pathlib.Path(args.claim_file).resolve() if args.claim_file else None,
        evidence_file=pathlib.Path(args.evidence_file).resolve() if args.evidence_file else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["ok"]:
        print("REDCAP_RSP_CONTRACT_OK")
        return 0
    return 1


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    plan_only = run_check(plan_path=DEFAULT_PLAN, rsp_id=None, claim_file=None, evidence_file=None)
    if plan_only["ok"] is not True:
        failures.append(f"方案结构检查应通过：{plan_only['failures']}")

    with tempfile.TemporaryDirectory(prefix="redcap-rsp-contract-") as raw:
        root = pathlib.Path(raw)
        evidence = root / ".redcap" / "evidence" / "rsp" / "rsp-03-provider-health.json"
        claim = root / "claim.json"
        write_json(evidence, {
            "rsp": "RSP-03",
            "acceptance": {
                "positive": {"status": "pass", "checks": ["fixture positive"]},
                "negative": {"status": "pass", "checks": ["fixture negative"]},
            },
            "changed_reality": ["fixture changed runtime behavior"],
            "artifacts": ["runtime/core/rsp_contract.py"],
        })
        write_json(claim, {
            "rsp": "RSP-03",
            "claim_scope": "current-machine-current-version",
            "completion_level": "sample_passed",
            "evidence_file": str(evidence),
            "new_issues": [],
        })
        positive = run_check(plan_path=DEFAULT_PLAN, rsp_id="RSP-03", claim_file=claim, evidence_file=evidence)
        if positive["ok"] is not True:
            failures.append(f"正向 RSP 检查应通过：{positive['failures']}")

        unknown = run_check(plan_path=DEFAULT_PLAN, rsp_id="RSP-99", claim_file=claim, evidence_file=evidence)
        if unknown["ok"] is True or not any("未知 RSP" in failure for failure in unknown["failures"]):
            failures.append("未知 RSP 样例必须失败")

        mismatch_claim = root / "claim-mismatch.json"
        write_json(mismatch_claim, {
            "rsp": "RSP-03",
            "claim_scope": "current-machine-current-version",
            "completion_level": "sample_passed",
            "evidence_file": ".redcap/evidence/rsp/other.json",
            "new_issues": [],
        })
        mismatch = run_check(plan_path=DEFAULT_PLAN, rsp_id="RSP-03", claim_file=mismatch_claim, evidence_file=evidence)
        if mismatch["ok"] is True or not any("does not reference" in failure for failure in mismatch["failures"]):
            failures.append("claim/evidence 不匹配样例必须失败")

        bad_evidence = root / "bad-evidence.json"
        write_json(bad_evidence, {
            "rsp": "RSP-03",
            "acceptance": {
                "positive": {"status": "pass", "checks": []},
                "negative": {"status": "fail", "checks": []},
            },
            "changed_reality": [],
            "artifacts": [],
        })
        bad_evidence_claim = root / "bad-evidence-claim.json"
        write_json(bad_evidence_claim, {
            "rsp": "RSP-03",
            "claim_scope": "current-machine-current-version",
            "completion_level": "sample_passed",
            "evidence_file": str(bad_evidence),
            "new_issues": [],
        })
        negative_fail = run_check(plan_path=DEFAULT_PLAN, rsp_id="RSP-03", claim_file=bad_evidence_claim, evidence_file=bad_evidence)
        if negative_fail["ok"] is True or not any("negative.status" in failure for failure in negative_fail["failures"]):
            failures.append("负向探针未通过样例必须失败")

        proof_only_evidence = root / "proof-only-evidence.json"
        write_json(proof_only_evidence, {
            "rsp": "RSP-12",
            "acceptance": {
                "positive": {"status": "pass", "checks": ["fixture positive"]},
                "negative": {"status": "pass", "checks": ["fixture negative"]},
            },
            "changed_reality": ["已写入方案书和复盘报告。"],
            "artifacts": ["assets/docs/residual-todo-final-solution-plan.md"],
        })
        proof_only_claim = root / "proof-only-claim.json"
        write_json(proof_only_claim, {
            "rsp": "RSP-12",
            "claim_scope": "current-machine-current-version",
            "completion_level": "sample_passed",
            "evidence_file": str(proof_only_evidence),
            "new_issues": [],
        })
        proof_only = run_check(
            plan_path=DEFAULT_PLAN,
            rsp_id="RSP-12",
            claim_file=proof_only_claim,
            evidence_file=proof_only_evidence,
        )
        if proof_only["ok"] is True:
            failures.append("只有文档、账本、报告的 changed_reality 和 artifacts 样例必须失败")
        if not any("不能只有文档" in failure for failure in proof_only["failures"]):
            failures.append(f"文档替代现实变化样例应给出明确失败原因：{proof_only['failures']}")

        unqueued_claim = root / "claim-unqueued.json"
        write_json(unqueued_claim, {
            "rsp": "RSP-03",
            "claim_scope": "current-machine-current-version",
            "completion_level": "sample_passed",
            "evidence_file": str(evidence),
            "new_issues": [{"title": "fixture unqueued issue"}],
        })
        unqueued = run_check(plan_path=DEFAULT_PLAN, rsp_id="RSP-03", claim_file=unqueued_claim, evidence_file=evidence)
        if unqueued["ok"] is True or not any("queue_target" in failure for failure in unqueued["failures"]):
            failures.append("新问题未入队样例必须失败")

    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_RSP_CONTRACT_SELF_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查 RSP 完成口径合同")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--plan", required=True)
    check.add_argument("--rsp")
    check.add_argument("--claim-file")
    check.add_argument("--evidence-file")
    check.set_defaults(func=cmd_check)
    sub.add_parser("self-check").set_defaults(func=cmd_self_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

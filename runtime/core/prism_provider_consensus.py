#!/usr/bin/env python3
"""RSP-23 Prism provider consensus and disagreement hardening check."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PRISM = REPO_ROOT / "runtime" / "prism" / "bin" / "prism"
CONTRACT_PATH = REPO_ROOT / "assets" / "contracts" / "prism-provider-consensus.json"
EXAMPLES = REPO_ROOT / "runtime" / "prism" / "examples"
DEFAULT_OUT = REPO_ROOT / ".redcap" / "evidence" / "rsp" / "rsp-23-prism-provider-consensus.json"
MARKER = "REDCAP_PRISM_PROVIDER_CONSENSUS_OK"
TRACE_MARKER = "REDCAP_PRISM_PROVIDER_TRACE_OK"
SCHEMA_ID = "redcap-prism-provider-consensus-check"
TRACE_SCHEMA_ID = "redcap-prism-provider-consensus-trace"
VERDICT_RANK = {"pass": 0, "concern": 1, "block": 2}


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取 JSON：{path}: {exc}") from exc


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def short_text(value: Any, *, limit: int = 240) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def normalize_material_text(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def run_command(argv: list[str], *, timeout_seconds: int = 60) -> dict[str, Any]:
    completed = subprocess.run(
        argv,
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    return {
        "argv": argv,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "ok": completed.returncode == 0,
    }


def command_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "argv": result["argv"],
        "exit_code": result["exit_code"],
        "ok": result["ok"],
        "stdout_tail": str(result.get("stdout", ""))[-1000:],
        "stderr_tail": str(result.get("stderr", ""))[-1000:],
    }


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def load_review(path: pathlib.Path, failures: list[str]) -> dict[str, Any] | None:
    payload = load_json(path)
    if not isinstance(payload, dict):
        failures.append(f"评审文件必须是 JSON 对象：{path}")
        return None
    provider = payload.get("provider")
    verdict = payload.get("verdict")
    if provider not in {"kimi", "claude-code"}:
        failures.append(f"评审文件 provider 无效：{path}")
    if verdict not in VERDICT_RANK:
        failures.append(f"评审文件 verdict 无效：{path}")
    for key in ["main_concern", "minimum_fix", "missing_evidence"]:
        if key not in payload:
            failures.append(f"评审文件缺少字段 {key}：{path}")
    return payload


def raw_summary(path: pathlib.Path) -> dict[str, Any]:
    data = path.read_text(encoding="utf-8", errors="replace")
    path_text = str(path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path)
    return {
        "path": path_text,
        "bytes": len(data.encode("utf-8")),
        "sha256": hashlib.sha256(data.encode("utf-8")).hexdigest(),
        "tail": data[-1200:],
    }


def build_provider_trace(review_paths: list[pathlib.Path], raw_paths: list[pathlib.Path]) -> dict[str, Any]:
    failures: list[str] = []
    reviews: list[dict[str, Any]] = []
    for path in review_paths:
        review = load_review(path, failures)
        if review is not None:
            reviews.append(review)
    if len(reviews) < 2:
        failures.append("至少需要两份 provider 评审才能形成一致性轨迹")
    providers = [str(review.get("provider")) for review in reviews]
    if len(providers) != len(set(providers)):
        failures.append("provider 评审不能重复")

    verdicts = [
        {
            "provider": review.get("provider"),
            "verdict": review.get("verdict"),
            "confidence": review.get("confidence"),
        }
        for review in reviews
    ]
    strictest = max(reviews, key=lambda item: VERDICT_RANK.get(str(item.get("verdict")), -1), default={})
    concern_texts = {str(review.get("provider")): normalize_material_text(review.get("main_concern")) for review in reviews}
    minimum_fix_texts = {str(review.get("provider")): normalize_material_text(review.get("minimum_fix")) for review in reviews}
    verdict_delta = len({str(item.get("verdict")) for item in reviews}) > 1
    concern_delta = len(set(concern_texts.values())) > 1
    minimum_fix_delta = len(set(minimum_fix_texts.values())) > 1
    any_concern_or_block = any(review.get("verdict") in {"concern", "block"} for review in reviews)
    must_respond = any_concern_or_block or verdict_delta or concern_delta or minimum_fix_delta
    material_delta = verdict_delta or concern_delta or minimum_fix_delta
    raw_outputs = []
    for path in raw_paths:
        if not path.exists():
            failures.append(f"raw provider 输出不存在：{path}")
            continue
        raw_outputs.append(raw_summary(path))
    if raw_paths and len(raw_outputs) < len(reviews):
        failures.append("每份 provider 评审都应有对应 raw provider 输出")

    return {
        "schema_id": TRACE_SCHEMA_ID,
        "ok": not failures,
        "providers": providers,
        "verdicts": verdicts,
        "strictest_provider": strictest.get("provider"),
        "strictest_verdict": strictest.get("verdict"),
        "must_respond": must_respond,
        "refuses_silent_pass": must_respond,
        "bounded_outcome": "requires_resolution" if must_respond else "consensus_pass",
        "allowed_resolution_paths": [
            "accept concern with implementation and verification evidence",
            "reject only after bounded same-provider rebuttal returns pass",
            "escalate unresolved concern to human or Cap arbitration with evidence",
        ] if must_respond else [],
        "material_disagreement": {
            "present": material_delta,
            "verdict_delta": verdict_delta,
            "main_concern_delta": concern_delta,
            "minimum_fix_delta": minimum_fix_delta,
        },
        "review_summaries": [
            {
                "provider": review.get("provider"),
                "verdict": review.get("verdict"),
                "main_concern_excerpt": short_text(review.get("main_concern")),
                "minimum_fix_excerpt": short_text(review.get("minimum_fix")),
                "missing_evidence_count": len(review.get("missing_evidence") or []),
            }
            for review in reviews
        ],
        "raw_provider_outputs": raw_outputs,
        "failures": failures,
    }


def validate_contract(contract: dict[str, Any], failures: list[str]) -> None:
    require(contract.get("schema_id") == "redcap-prism-provider-consensus-contract", "合同 schema_id 错误", failures)
    require(contract.get("rsp") == "RSP-23", "合同必须绑定 RSP-23", failures)
    providers = contract.get("allowed_providers")
    require(providers == ["kimi", "claude-code"], "合同必须限定 Kimi 与 Claude Code 两名评审方", failures)
    dimensions = contract.get("required_dimensions")
    require(isinstance(dimensions, list) and len(dimensions) >= 6, "合同必须列出至少 6 条差异处理维度", failures)
    positive = contract.get("positive_acceptance")
    negative = contract.get("negative_probes")
    require(isinstance(positive, list) and len(positive) >= 4, "合同必须包含正向验收矩阵", failures)
    require(isinstance(negative, list) and len(negative) >= 3, "合同必须包含负向探针矩阵", failures)
    forbidden = "\n".join(str(item) for item in contract.get("forbidden_completion_claims", []))
    require("RedCap 完整复活" in forbidden, "合同必须禁止把 RSP-23 说成 RedCap 完整复活", failures)


def parse_first_json(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def run_merge_check(tmp_dir: pathlib.Path, failures: list[str], checks: list[dict[str, Any]]) -> None:
    concern_merge = tmp_dir / "merge.concern.json"
    concern_result = run_command(
        [
            str(PRISM),
            "merge",
            "--out",
            str(concern_merge),
            str(EXAMPLES / "prism-concern-resolution.claude-pass.json"),
            str(EXAMPLES / "prism-concern-resolution.kimi-concern.json"),
        ]
    )
    checks.append({"id": "merge-concern-keeps-strictest", **command_summary(concern_result)})
    require(concern_result["ok"], "concern 合并命令必须通过", failures)
    if concern_merge.exists():
        merged = load_json(concern_merge)
        require(merged.get("strictest_verdict") == "concern", "concern 合并必须保留最严格 verdict=concern", failures)
        require(merged.get("strictest_provider") == "kimi", "concern 合并必须保留 strictest_provider=kimi", failures)
        require(merged.get("must_respond") is True, "concern 合并必须要求回应 must_respond=true", failures)
    else:
        failures.append("concern 合并没有生成输出文件")

    pass_merge = tmp_dir / "merge.pass.json"
    pass_result = run_command(
        [
            str(PRISM),
            "merge",
            "--out",
            str(pass_merge),
            str(EXAMPLES / "prism-concern-resolution.claude-pass.json"),
            str(EXAMPLES / "prism-concern-resolution.kimi-followup-pass.json"),
        ]
    )
    checks.append({"id": "merge-pass-does-not-force-response", **command_summary(pass_result)})
    require(pass_result["ok"], "pass 合并命令必须通过", failures)
    if pass_merge.exists():
        merged = load_json(pass_merge)
        require(merged.get("strictest_verdict") == "pass", "全 pass 合并必须得到 strictest_verdict=pass", failures)
        require(merged.get("must_respond") is False, "全 pass 合并不能要求回应 must_respond=false", failures)
    else:
        failures.append("pass 合并没有生成输出文件")


def run_resolution_checks(failures: list[str], checks: list[dict[str, Any]]) -> None:
    self_check = run_command([str(PRISM), "resolution-check", "--self-check"], timeout_seconds=90)
    checks.append({"id": "resolution-self-check", **command_summary(self_check)})
    require(self_check["ok"], "prism-resolution 自检必须通过", failures)

    negative_cases = [
        (
            "accept-without-verification-fails",
            "prism-concern-resolution.invalid-accept-missing-verification.json",
            "accept 缺少验证证据必须失败",
        ),
        (
            "reject-without-followup-fails",
            "prism-concern-resolution.invalid-reject-missing-followup.json",
            "reject 缺少同评审方反驳必须失败",
        ),
        (
            "reject-while-followup-still-concern-fails",
            "prism-concern-resolution.invalid-reject-followup-still-concern.json",
            "同评审方反驳仍 concern 时 reject 必须失败",
        ),
    ]
    for check_id, file_name, message in negative_cases:
        result = run_command(
            [
                str(PRISM),
                "resolution-check",
                "--merge",
                str(EXAMPLES / "prism-concern-resolution.merge.concern.json"),
                "--resolution",
                str(EXAMPLES / file_name),
            ]
        )
        summary = command_summary(result)
        summary["expected_failure"] = True
        summary["probe_passed"] = not result["ok"]
        checks.append({"id": check_id, **summary})
        require(not result["ok"], message, failures)


def run_rebuttal_request_check(tmp_dir: pathlib.Path, failures: list[str], checks: list[dict[str, Any]]) -> None:
    out_path = tmp_dir / "kimi.rebuttal-request.json"
    result = run_command(
        [
            str(PRISM),
            "rebuttal-request",
            "--merge",
            str(EXAMPLES / "prism-concern-resolution.merge.concern.json"),
            "--review",
            str(EXAMPLES / "prism-concern-resolution.kimi-concern.json"),
            "--provider",
            "kimi",
            "--main-claim",
            "RSP-23 verifies bounded same-provider rebuttal before rejecting Prism concerns.",
            "--changed-reality",
            "RSP-23 adds an executable consensus check.",
            "--evidence",
            "assets/contracts/prism-provider-consensus.json",
            "--out",
            str(out_path),
        ]
    )
    checks.append({"id": "same-provider-rebuttal", **command_summary(result)})
    require(result["ok"], "同评审方反驳请求生成必须通过", failures)
    if not out_path.exists():
        failures.append("同评审方反驳请求没有生成输出文件")
        return
    payload = load_json(out_path)
    require(payload.get("review_mode") == "rebuttal_review", "反驳请求必须使用 rebuttal_review 模式", failures)
    require(payload.get("requested_providers") == ["kimi"], "反驳请求必须只回到原始 Kimi 评审方", failures)
    require(payload.get("additive_rebuttal_only") is True, "反驳请求必须声明 additive_rebuttal_only=true", failures)
    rebuttal_for = payload.get("rebuttal_for")
    require(isinstance(rebuttal_for, dict) and rebuttal_for.get("provider") == "kimi", "反驳请求必须记录原始评审方", failures)


def run_actual_provider_trace(
    provider_run_dir: pathlib.Path | None,
    trace_out: pathlib.Path | None,
    failures: list[str],
    checks: list[dict[str, Any]],
) -> None:
    if provider_run_dir is None:
        return
    review_paths = [
        provider_run_dir / "kimi.review.json",
        provider_run_dir / "claude-code.review.json",
    ]
    raw_paths = [
        provider_run_dir / "kimi.raw.json",
        provider_run_dir / "claude-code.raw.json",
    ]
    trace = build_provider_trace(review_paths, raw_paths)
    if trace_out is not None:
        write_json(trace_out, trace)
    trace_reference = str(trace_out.relative_to(REPO_ROOT) if trace_out and trace_out.is_relative_to(REPO_ROOT) else trace_out)
    checks.append({
        "id": "actual-provider-disagreement-trace",
        "ok": trace["ok"],
        "trace_out": trace_reference,
        "strictest_verdict": trace.get("strictest_verdict"),
        "must_respond": trace.get("must_respond"),
        "material_disagreement": trace.get("material_disagreement"),
    })
    require(trace["ok"], "真实 provider 差异轨迹必须可生成", failures)
    require(trace.get("must_respond") is True, "真实 provider 轨迹中 concern/block 或材料差异必须阻止静默通过", failures)
    require(trace.get("refuses_silent_pass") is True, "真实 provider 轨迹必须拒绝静默通过", failures)


def run_check(provider_run_dir: pathlib.Path | None = None, trace_out: pathlib.Path | None = None) -> dict[str, Any]:
    failures: list[str] = []
    checks: list[dict[str, Any]] = []
    contract = load_json(CONTRACT_PATH)
    if not isinstance(contract, dict):
        raise SystemExit("合同必须是 JSON 对象")
    validate_contract(contract, failures)
    checks.append({"id": "contract-shape", "ok": not failures, "path": str(CONTRACT_PATH.relative_to(REPO_ROOT))})

    with tempfile.TemporaryDirectory(prefix="redcap-prism-consensus-") as tmp_raw:
        tmp_dir = pathlib.Path(tmp_raw)
        run_merge_check(tmp_dir, failures, checks)
        run_resolution_checks(failures, checks)
        run_rebuttal_request_check(tmp_dir, failures, checks)
        run_actual_provider_trace(provider_run_dir, trace_out, failures, checks)
    positive_checks = [
        "merge-concern-keeps-strictest",
        "merge-pass-does-not-force-response",
        "resolution-self-check",
        "same-provider-rebuttal",
    ]
    if provider_run_dir is not None:
        positive_checks.append("actual-provider-disagreement-trace")

    return {
        "schema_id": SCHEMA_ID,
        "rsp": "RSP-23",
        "ok": not failures,
        "contract": str(CONTRACT_PATH.relative_to(REPO_ROOT)),
        "checks": checks,
        "acceptance": {
            "positive": {
                "status": "pass" if not failures else "fail",
                "checks": positive_checks,
            },
            "negative": {
                "status": "pass" if not failures else "fail",
                "checks": [
                    "accept-without-verification-fails",
                    "reject-without-followup-fails",
                    "reject-while-followup-still-concern-fails",
                ],
            },
        },
        "changed_reality": [
            "RSP-23 拥有独立合同：assets/contracts/prism-provider-consensus.json",
            "RSP-23 拥有可执行检查器：runtime/bin/redcap prism-consensus check",
            "RSP-23 可以读取真实 provider 评审与 raw 输出并生成差异处理轨迹",
            "总检查器可通过 prism-provider-consensus-check 运行该能力",
        ],
        "artifacts": [
            "assets/contracts/prism-provider-consensus.json",
            "runtime/core/prism_provider_consensus.py",
            "runtime/bin/redcap",
            "runtime/core/check_runner.py",
        ],
        "forbidden_parent_claims": contract.get("forbidden_completion_claims", []),
        "failures": failures,
    }


def cmd_check(args: argparse.Namespace) -> int:
    provider_run_dir = pathlib.Path(args.provider_run_dir).resolve() if args.provider_run_dir else None
    trace_out = pathlib.Path(args.trace_out).resolve() if args.trace_out else None
    payload = run_check(provider_run_dir=provider_run_dir, trace_out=trace_out)
    if args.out:
        write_json(pathlib.Path(args.out).resolve(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not payload["ok"]:
        return 1
    print(MARKER)
    return 0


def cmd_self_check(args: argparse.Namespace) -> int:
    return cmd_check(args)


def cmd_trace(args: argparse.Namespace) -> int:
    review_paths = [pathlib.Path(raw).resolve() for raw in args.review]
    raw_paths = [pathlib.Path(raw).resolve() for raw in args.raw]
    payload = build_provider_trace(review_paths, raw_paths)
    if args.out:
        write_json(pathlib.Path(args.out).resolve(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not payload["ok"]:
        return 1
    print(TRACE_MARKER)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RSP-23 Prism provider consensus check")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check")
    check.add_argument("--out", default=None)
    check.add_argument("--provider-run-dir", default=None)
    check.add_argument("--trace-out", default=None)
    check.set_defaults(func=cmd_check)
    self_check = subparsers.add_parser("self-check")
    self_check.add_argument("--out", default=None)
    self_check.add_argument("--provider-run-dir", default=None)
    self_check.add_argument("--trace-out", default=None)
    self_check.set_defaults(func=cmd_self_check)
    trace = subparsers.add_parser("trace")
    trace.add_argument("--review", action="append", required=True)
    trace.add_argument("--raw", action="append", required=True)
    trace.add_argument("--out", default=None)
    trace.set_defaults(func=cmd_trace)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

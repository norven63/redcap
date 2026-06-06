#!/usr/bin/env python3
"""Human-facing output policy checker for RedCap."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = REPO_ROOT / "assets" / "contracts" / "human-output-policy.json"
CJK_RE = re.compile(r"[\u3400-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")
EXPLANATION_RE = re.compile(r"^[（(][^）)]*[\u3400-\u9fff][^）)]*[）)]")
FENCE_RE = re.compile(r"```.*?```", flags=re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"json root must be object: {path}")
    return payload


def strip_code(text: str) -> str:
    without_fences = FENCE_RE.sub(" ", text)
    return INLINE_CODE_RE.sub(" ", without_fences)


def cjk_ratio(text: str) -> float:
    prose = strip_code(text)
    cjk_count = len(CJK_RE.findall(prose))
    latin_count = len(LATIN_RE.findall(prose))
    total = cjk_count + latin_count
    if total == 0:
        return 1.0
    return cjk_count / total


def term_has_explanation(text: str, term: str) -> bool:
    prose = strip_code(text)
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])")
    for match in pattern.finditer(prose):
        suffix = prose[match.end(): match.end() + 80].lstrip()
        if EXPLANATION_RE.match(suffix):
            return True
    return False


def lint_text(text: str, contract: dict[str, Any], *, surface: str, source: str) -> list[str]:
    failures: list[str] = []
    surfaces = contract.get("surfaces")
    if not isinstance(surfaces, dict) or surface not in surfaces:
        failures.append(f"unknown surface: {surface}")
        return failures
    surface_policy = surfaces[surface]
    if not isinstance(surface_policy, dict):
        failures.append(f"surface policy must be object: {surface}")
        return failures
    prose = strip_code(text).strip()
    if not prose:
        return failures
    min_ratio = float(surface_policy.get("minimum_cjk_ratio", contract.get("default_minimum_cjk_ratio", 0.18)))
    if len(prose) >= int(surface_policy.get("minimum_checked_chars", 16)):
        ratio = cjk_ratio(text)
        if ratio < min_ratio:
            failures.append(f"{source}: 中文比例过低，surface={surface}, ratio={ratio:.3f}, minimum={min_ratio:.3f}")
    banned = surface_policy.get("banned_phrases", contract.get("banned_phrases", []))
    if isinstance(banned, list):
        lowered = prose.lower()
        for phrase in banned:
            if isinstance(phrase, str) and phrase and phrase.lower() in lowered:
                failures.append(f"{source}: 出现不适合给人看的机器化表达: {phrase}")
    terms = surface_policy.get("terms_requiring_explanation", contract.get("terms_requiring_explanation", []))
    if isinstance(terms, list):
        for term in terms:
            if not isinstance(term, str) or not term.strip():
                continue
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])", prose) and not term_has_explanation(text, term):
                failures.append(f"{source}: 专有名词首次出现缺少中文解释: {term}")
    return failures


def check_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_id") != "redcap-human-output-policy":
        failures.append("schema_id must be redcap-human-output-policy")
    if not isinstance(contract.get("mechanism"), str) or "确定性启发式" not in contract.get("mechanism", ""):
        failures.append("mechanism must describe the deterministic heuristic checker")
    mixed_rules = contract.get("mixed_language_rules")
    if not isinstance(mixed_rules, dict):
        failures.append("mixed_language_rules must be an object")
    elif not isinstance(mixed_rules.get("minimum_mixed_samples"), int) or mixed_rules.get("minimum_mixed_samples") < 5:
        failures.append("mixed_language_rules.minimum_mixed_samples must be at least 5")
    surfaces = contract.get("surfaces")
    required_surfaces = {"assistant_reply", "document", "hook_message", "generated_report", "code_comment", "commit_message"}
    if not isinstance(surfaces, dict):
        failures.append("surfaces must be an object")
        return failures
    missing = sorted(required_surfaces - set(surfaces))
    if missing:
        failures.append(f"missing required surfaces: {', '.join(missing)}")
    for name, policy in surfaces.items():
        if not isinstance(policy, dict):
            failures.append(f"{name}: surface policy must be object")
            continue
        if not isinstance(policy.get("minimum_cjk_ratio"), (int, float)):
            failures.append(f"{name}: minimum_cjk_ratio must be number")
    samples = contract.get("required_samples")
    if not isinstance(samples, list) or len(samples) < 15:
        failures.append("required_samples must contain at least 15 samples")
    else:
        mixed_count = sum(1 for sample in samples if isinstance(sample, dict) and sample.get("mixed_language") is True)
        if mixed_count < 5:
            failures.append("required_samples must include at least 5 mixed-language samples")
    return failures


def cmd_check(args: argparse.Namespace) -> int:
    contract = load_json(pathlib.Path(args.contract).resolve())
    failures = check_contract(contract)
    for sample in contract.get("required_samples", []):
        if not isinstance(sample, dict):
            failures.append("required_samples entries must be objects")
            continue
        text = str(sample.get("text") or "")
        surface = str(sample.get("surface") or "")
        should_pass = sample.get("should_pass") is True
        sample_failures = lint_text(text, contract, surface=surface, source=str(sample.get("id") or "sample"))
        if should_pass and sample_failures:
            failures.extend(sample_failures)
        if not should_pass and not sample_failures:
            failures.append(f"{sample.get('id')}: negative sample unexpectedly passed")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_HUMAN_OUTPUT_POLICY_OK")
    return 0


def cmd_lint_text(args: argparse.Namespace) -> int:
    contract = load_json(pathlib.Path(args.contract).resolve())
    failures = check_contract(contract)
    failures.extend(lint_text(args.text, contract, surface=args.surface, source=args.source))
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_HUMAN_OUTPUT_TEXT_OK")
    return 0


def cmd_lint_file(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.path).resolve()
    text = path.read_text(encoding="utf-8")
    contract = load_json(pathlib.Path(args.contract).resolve())
    failures = check_contract(contract)
    failures.extend(lint_text(text, contract, surface=args.surface, source=str(path)))
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    print("REDCAP_HUMAN_OUTPUT_FILE_OK")
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="redcap-human-output-") as tmp_raw:
        tmp = pathlib.Path(tmp_raw)
        contract_path = tmp / "policy.json"
        contract_path.write_text(DEFAULT_CONTRACT.read_text(encoding="utf-8"), encoding="utf-8")
        contract = load_json(contract_path)
        good = lint_text(
            "棱镜（异构评审助手）已经返回阻断意见，Cap 会先修行为级问题，再进入下一步。",
            contract,
            surface="assistant_reply",
            source="good",
        )
        english_only = lint_text(
            "The workflow lifecycle packet proves completion and the task is done.",
            contract,
            surface="assistant_reply",
            source="english-only",
        )
        unexplained = lint_text(
            "Prism 已经返回意见，继续处理。",
            contract,
            surface="assistant_reply",
            source="unexplained",
        )
        hook_message = lint_text(
            "运行 RedCap（当前复活工程）收口检查。",
            contract,
            surface="hook_message",
            source="hook-message",
        )
        failures: list[str] = []
        if good:
            failures.append("中文优先样例不应失败")
        if not english_only:
            failures.append("英文机器化样例应失败")
        if not unexplained:
            failures.append("未解释专有名词样例应失败")
        if hook_message:
            failures.append("简短 hook 消息不应失败")
        print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
        if failures:
            return 1
        print("REDCAP_HUMAN_OUTPUT_POLICY_SELF_CHECK_OK")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap human-facing output policy checker")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("self-check")
    lint_text_parser = sub.add_parser("lint-text")
    lint_text_parser.add_argument("--surface", required=True)
    lint_text_parser.add_argument("--source", default="inline-text")
    lint_text_parser.add_argument("--text", required=True)
    lint_file_parser = sub.add_parser("lint-file")
    lint_file_parser.add_argument("--surface", required=True)
    lint_file_parser.add_argument("path")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "check":
        return cmd_check(args)
    if args.command == "self-check":
        return cmd_self_check(args)
    if args.command == "lint-text":
        return cmd_lint_text(args)
    if args.command == "lint-file":
        return cmd_lint_file(args)
    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Prism-backed prompt intent judge.

Deterministic prompt intent remains the fast path. This module gives RedCap
hooks a bounded LLM appeal path when deterministic intent would block a
mutating action that the user may actually have authorized.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import time
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "runtime" / "core"))
from prompt_intent import classify_prompt_intent  # noqa: E402


ALLOWED_SCOPES = {"answer_only", "review_only", "implementation", "completion"}
ALLOWED_EVIDENCE = {"none", "diagnostic", "substantive"}
ALLOWED_KINDS = {"question", "directive", "mixed"}
ALLOWED_CONFIDENCE = {"low", "medium", "high"}
PROVIDERS = {"kimi", "claude-code"}
DEFAULT_PROVIDER = "claude-code"
DEFAULT_FALLBACK_PROVIDER = "claude-code"
DEFAULT_TIMEOUT_SECONDS = 75.0
MAX_JUDGE_PROMPT_CHARS = 4000


def normalize_intent(raw: dict[str, Any], *, source: str) -> dict[str, Any] | None:
    scope = raw.get("authorized_scope")
    evidence = raw.get("action_evidence")
    kind = raw.get("prompt_kind") or raw.get("kind") or "mixed"
    confidence = raw.get("confidence") or "medium"
    if scope not in ALLOWED_SCOPES or evidence not in ALLOWED_EVIDENCE:
        return None
    if kind not in ALLOWED_KINDS:
        kind = "mixed"
    if confidence not in ALLOWED_CONFIDENCE:
        confidence = "medium"
    return {
        "prompt_kind": kind,
        "authorized_scope": scope,
        "action_evidence": evidence,
        "confidence": confidence,
        "reason": str(raw.get("reason") or f"{source} prompt intent judgment"),
        "source": source,
    }


def iter_json_objects(text: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            objects.append(parsed)
            result = parsed.get("result")
            if isinstance(result, str):
                objects.extend(iter_json_objects(result))
    return objects


def extract_judgment(text: str, *, source: str) -> dict[str, Any] | None:
    for obj in iter_json_objects(text):
        direct = normalize_intent(obj, source=source)
        if direct is not None:
            return direct
        for key in ["intent", "prompt_intent", "judgment"]:
            nested = obj.get(key)
            if isinstance(nested, dict):
                normalized = normalize_intent(nested, source=source)
                if normalized is not None:
                    return normalized
    return None


def build_judge_prompt(user_prompt: str, deterministic: dict[str, str]) -> str:
    prompt_truncated = len(user_prompt) > MAX_JUDGE_PROMPT_CHARS
    bounded_prompt = user_prompt[:MAX_JUDGE_PROMPT_CHARS]
    if prompt_truncated:
        bounded_prompt += "\n[TRUNCATED_BY_REDCAP_INTENT_JUDGE]"
    schema = {
        "prompt_kind": "question|directive|mixed",
        "authorized_scope": "answer_only|review_only|implementation|completion",
        "action_evidence": "none|diagnostic|substantive",
        "confidence": "low|medium|high",
        "reason": "short reason",
    }
    payload = {
        "task": "Classify whether the user's prompt authorizes RedCap to mutate files or claim completion.",
        "rules": [
            "answer_only: user asks for explanation, status, or conceptual answer; no tool action required.",
            "review_only: user asks to inspect, diagnose, audit, quote, or show code; read-only diagnostic evidence may be enough.",
            "implementation: user asks to change code, run a remediation, upgrade, build, fix, commit, push, create, move, or otherwise alter state.",
            "completion: user explicitly asks to close out or claim done after verification.",
            "Quoted words like `commit`, `push`, or '执行词' do not authorize execution by themselves.",
            "Hybrid prompts that ask to explain and then fix/commit are implementation.",
            "If uncertain between answer_only and implementation, choose implementation with low confidence.",
        ],
        "deterministic_intent": deterministic,
        "user_prompt": bounded_prompt,
        "user_prompt_truncated": prompt_truncated,
        "required_json_schema": schema,
    }
    return (
        "You are Prism's prompt intent judge. Return exactly one JSON object and no prose.\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def provider_command(provider: str, prompt: str) -> list[str]:
    if provider == "kimi":
        return [
            "kimi",
            "--work-dir",
            str(REPO_ROOT),
            "--plan",
            "--quiet",
            "--max-steps-per-turn",
            "1",
            "-p",
            prompt,
        ]
    if provider == "claude-code":
        return [
            "claude",
            "--print",
            "--output-format",
            "json",
            "--no-session-persistence",
            "--permission-mode",
            "plan",
            "--disallowedTools",
            "Bash,Edit,Write,MultiEdit,Read,Glob,Grep,LS,Task,TodoWrite,NotebookEdit,WebFetch,WebSearch",
            "--",
            prompt,
        ]
    raise ValueError(f"unsupported provider: {provider}")


def run_provider(provider: str, judge_prompt: str, timeout_seconds: float) -> dict[str, Any]:
    if provider not in PROVIDERS:
        return {"ok": False, "provider": provider, "reason": "unsupported provider"}
    binary = "claude" if provider == "claude-code" else provider
    if shutil.which(binary) is None:
        return {"ok": False, "provider": provider, "reason": f"provider binary not found: {binary}"}
    argv = provider_command(provider, judge_prompt)
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            argv,
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "provider": provider,
            "reason": "provider timeout",
            "timeout_seconds": timeout_seconds,
            "stdout_length": len(exc.stdout or ""),
            "stderr_length": len(exc.stderr or ""),
        }
    raw = (completed.stdout or "") + "\n" + (completed.stderr or "")
    judgment = extract_judgment(raw, source=f"llm:{provider}")
    return {
        "ok": completed.returncode == 0 and judgment is not None,
        "provider": provider,
        "exit_code": completed.returncode,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "stdout_length": len(completed.stdout or ""),
        "stderr_length": len(completed.stderr or ""),
        "judgment": judgment,
        "reason": None if judgment is not None else "provider output did not contain valid intent JSON",
    }


def classify_with_policy(
    prompt: str,
    *,
    llm_policy: str,
    provider: str,
    fallback_provider: str | None,
    timeout_seconds: float,
    fake_response: str | None = None,
    fake_delay_seconds: float = 0.0,
) -> dict[str, Any]:
    deterministic = classify_prompt_intent(prompt)
    result: dict[str, Any] = {
        "ok": True,
        "prompt_intent": deterministic,
        "deterministic_intent": deterministic,
        "source": "deterministic",
        "llm_policy": llm_policy,
        "llm_attempted": False,
        "llm_results": [],
    }
    if llm_policy == "off":
        return result
    if llm_policy == "auto" and deterministic.get("authorized_scope") in {"implementation", "completion"}:
        return result
    if fake_response is not None:
        if fake_delay_seconds > 0:
            time.sleep(fake_delay_seconds)
        judgment = extract_judgment(fake_response, source="llm:fixture")
        result["llm_attempted"] = True
        result["llm_results"].append({"ok": judgment is not None, "provider": "fixture", "judgment": judgment})
        if judgment is not None:
            result["prompt_intent"] = judgment
            result["source"] = "llm:fixture"
        return result
    judge_prompt = build_judge_prompt(prompt, deterministic)
    providers = [provider]
    if fallback_provider and fallback_provider != provider:
        providers.append(fallback_provider)
    for candidate in providers:
        provider_result = run_provider(candidate, judge_prompt, timeout_seconds)
        result["llm_attempted"] = True
        result["llm_results"].append(provider_result)
        judgment = provider_result.get("judgment") if isinstance(provider_result, dict) else None
        if provider_result.get("ok") is True and isinstance(judgment, dict):
            result["prompt_intent"] = judgment
            result["source"] = f"llm:{candidate}"
            return result
    result["ok"] = False if llm_policy == "force" else True
    result["reason"] = "LLM intent judge did not return a usable judgment; deterministic fallback retained."
    return result


def cmd_classify(args: argparse.Namespace) -> int:
    prompt = args.prompt if args.prompt is not None else sys.stdin.read()
    result = classify_with_policy(
        prompt,
        llm_policy=args.llm_policy,
        provider=args.provider,
        fallback_provider=args.fallback_provider,
        timeout_seconds=args.timeout_seconds,
        fake_response=args.fake_response,
        fake_delay_seconds=args.fake_delay_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    quoted = classify_with_policy(
        "把 `commit/push` 判断代码贴出来",
        llm_policy="off",
        provider=DEFAULT_PROVIDER,
        fallback_provider=None,
        timeout_seconds=1,
    )
    if quoted["prompt_intent"].get("authorized_scope") != "review_only":
        failures.append("quoted code excerpt request should remain review_only")
    pre_execution = classify_with_policy(
        "我希望你可以一气呵成的完成任务：先完成360度旧RedCap扫描任务，然后根据任务的完成结果制定完整的如何复活Redcap项目计划，再根据计划去执行和落地。关于这个问题，你不要着急先开动，而是先回答我是否可行，并且如果还缺什么缓解，或者说你觉得有更好的“一气呵成任务计划方案”，也可以拿出来和我讨论。",
        llm_policy="off",
        provider=DEFAULT_PROVIDER,
        fallback_provider=None,
        timeout_seconds=1,
    )
    if pre_execution["prompt_intent"].get("authorized_scope") != "answer_only":
        failures.append("pre-execution feasibility discussion should remain answer_only")
    execution_samples = [
        ("请执行这个修复", "direct implementation request should remain implementation"),
        ("直接做这个优化", "direct do-it request should remain implementation"),
        ("先讨论一下可行性，没问题的话就直接做", "mixed discussion plus execution request should remain implementation"),
    ]
    for sample_prompt, failure in execution_samples:
        classified = classify_with_policy(
            sample_prompt,
            llm_policy="off",
            provider=DEFAULT_PROVIDER,
            fallback_provider=None,
            timeout_seconds=1,
        )
        if classified["prompt_intent"].get("authorized_scope") != "implementation":
            failures.append(failure)
    fake = classify_with_policy(
        "把棱镜改造成 LLM intent judge 模式",
        llm_policy="force",
        provider=DEFAULT_PROVIDER,
        fallback_provider=None,
        timeout_seconds=1,
        fake_response=json.dumps({
            "prompt_kind": "directive",
            "authorized_scope": "implementation",
            "action_evidence": "substantive",
            "confidence": "high",
            "reason": "fixture override",
        }, ensure_ascii=False),
    )
    if fake["prompt_intent"].get("authorized_scope") != "implementation" or fake.get("source") != "llm:fixture":
        failures.append("LLM fixture judgment should override deterministic intent")
    auto_clear = classify_with_policy(
        "请升级这个 hook",
        llm_policy="auto",
        provider=DEFAULT_PROVIDER,
        fallback_provider=None,
        timeout_seconds=1,
        fake_response=json.dumps({
            "prompt_kind": "question",
            "authorized_scope": "answer_only",
            "action_evidence": "none",
            "confidence": "high",
            "reason": "should not be used",
        }, ensure_ascii=False),
    )
    if auto_clear.get("source") != "deterministic" or auto_clear.get("llm_attempted") is not False:
        failures.append("auto mode should not call LLM when deterministic intent already authorizes implementation")
    invalid = extract_judgment("not json", source="fixture")
    if invalid is not None:
        failures.append("invalid provider output should not produce a judgment")
    print(json.dumps({"ok": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify RedCap prompt intent with Prism LLM fallback.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    classify = sub.add_parser("classify", help="Classify prompt intent.")
    classify.add_argument("--prompt", help="Prompt text. Reads stdin when omitted.")
    classify.add_argument(
        "--llm-policy",
        choices=["off", "auto", "force"],
        default="auto",
        help="off uses deterministic rules only; force requires an LLM judgment; auto allows LLM fallback.",
    )
    classify.add_argument("--provider", choices=sorted(PROVIDERS), default=DEFAULT_PROVIDER)
    classify.add_argument("--fallback-provider", choices=sorted(PROVIDERS), default=DEFAULT_FALLBACK_PROVIDER)
    classify.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    classify.add_argument("--fake-response", help="Test-only provider response JSON.")
    classify.add_argument("--fake-delay-seconds", type=float, default=0.0, help="Test-only delay before fake response.")
    classify.set_defaults(func=cmd_classify)

    self_check = sub.add_parser("self-check", help="Run local intent judge self-checks.")
    self_check.set_defaults(func=cmd_self_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

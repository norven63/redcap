#!/usr/bin/env python3
"""Deterministic prompt-intent classification shared by RedCap gates."""

from __future__ import annotations

import re
from typing import Any


QUESTION_ONLY_MARKERS = {
    "should we",
    "do we need",
    "is it necessary",
    "can we",
    "could we",
    "why",
    "what is",
    "what are",
    "how should",
    "how does",
    "how do",
    "是否",
    "是不是",
    "要不要",
    "能否",
    "可以吗",
    "对吗",
    "为什么",
    "如何",
    "怎么",
    "什么是",
    "是什么",
}

IMPLEMENTATION_MARKERS = {
    "commit",
    "implement",
    "fix",
    "complete ",
    "push",
    "run ",
    "execute",
    "go ahead",
    "approved",
    "approve",
    "完成",
    "修复",
    "执行",
    "创建",
    "开始",
    "来吧",
    "落地",
    "变成",
    "做成",
    "编成",
    "编程",
    "新分支",
    "修改",
    "改掉",
    "调整",
    "补齐",
    "补上",
    "提交",
    "推送",
    "添加",
    "加入",
    "加上",
    "新加",
    "清理",
    "跑",
    "继续",
    "赞同",
    "同意",
}

REVIEW_MARKERS = {
    "review",
    "audit",
    "diagnose",
    "inspect",
    "analyze",
    "analyse",
    "评估",
    "审核",
    "检查",
    "诊断",
    "排查",
    "分析",
    "复盘",
    "看看",
}

CODE_EXCERPT_REQUEST_MARKERS = {
    "show me the code",
    "paste the code",
    "show the code",
    "paste the script",
    "show the script",
    "贴出来",
    "贴出",
    "列出来",
    "列出",
    "展示",
    "给我看看",
}

CODE_REFERENCE_MARKERS = {
    "code",
    "script",
    "source",
    "代码",
    "脚本",
    "源码",
}

NEGATED_IMPLEMENTATION_PHRASES = {
    "do not change",
    "do not edit",
    "do not modify",
    "don't change",
    "don't edit",
    "don't modify",
    "no changes",
    "without changing",
    "not executing",
    "not actually executing",
    "不要修改",
    "不要改",
    "不要执行",
    "不要提交",
    "不要推送",
    "不要push",
    "不要 push",
    "不要commit",
    "不要 commit",
    "不用修改",
    "不用改",
    "不用执行",
    "不需要执行",
    "无需执行",
    "不用提交",
    "不用推送",
    "不修改",
    "不改",
    "不是实际执行",
    "不是执行",
    "不是任务执行",
    "并非执行",
    "没有执行",
    "不会执行",
    "不提交",
    "不推送",
    "先别改",
    "先别提交",
    "先别推送",
    "别改",
    "别提交",
    "别推送",
}

ANSWER_ONLY_EXECUTION_CONTEXT_PHRASES = {
    "answer only",
    "just answer",
    "only answer",
    "question only",
    "只是回答问题",
    "只是回答",
    "仅回答",
    "只回答",
    "回答问题",
    "不是实际执行任务",
    "不是实际执行",
    "是不是实际执行",
    "是否实际执行",
    "不是执行任务",
    "不是执行",
    "不需要执行",
    "不用执行",
    "无需执行",
    "没有执行",
    "不会执行",
}

MECHANISM_QUESTION_CONTEXT_PHRASES = {
    "trigger execution",
    "execution flow",
    "execution logic",
    "execution mechanism",
    "hook execution",
    "触发执行脚本",
    "触发执行",
    "执行流程",
    "执行逻辑",
    "执行机制",
    "执行判断",
    "执行过程",
    "脚本执行",
    "hook执行",
    "hook 执行",
}

STRONG_IMPLEMENTATION_MARKERS = {
    "go ahead",
    "approved",
    "approve",
    "请",
    "执行",
    "开始",
    "来吧",
    "落地",
    "跑",
    "继续",
    "先把",
    "帮我",
    "do it",
}

CONDITIONAL_IMPLEMENTATION_MARKERS = {
    "if needed",
    "if necessary",
    "as needed",
    "when needed",
    "如果",
    "有的话",
    "没有的话",
    "需要的话",
    "必要的话",
    "发现",
}

META_QUESTION_MARKERS = {
    "why",
    "为什么",
    "是为了什么",
    "拦截",
    "过激",
    "误判",
    "意图",
    "原因",
}


def normalize_prompt_text(value: str) -> str:
    return " ".join(value.casefold().split())


def strip_quoted_spans(value: str) -> str:
    return re.sub(r"`[^`]*`|“[^”]*”|\"[^\"]*\"|'[^']*'|‘[^’]*’", " ", value)


def prompt_requests_code_excerpt(normalized: str) -> bool:
    return (
        any(marker in normalized for marker in CODE_EXCERPT_REQUEST_MARKERS)
        and any(marker in normalized for marker in CODE_REFERENCE_MARKERS)
    )


def prompt_text_from_event(event: dict[str, Any]) -> str | None:
    for key in ["prompt_text", "prompt_excerpt", "source_prompt"]:
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value
    prompt = event.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        return prompt
    if isinstance(prompt, dict):
        for key in ["text", "normalized_excerpt", "excerpt"]:
            value = prompt.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None


def prompt_has_directive_authority(prompt: str) -> bool:
    normalized = normalize_prompt_text(prompt)
    directive_text = strip_quoted_spans(normalized)
    question_context = any(marker in normalized for marker in QUESTION_ONLY_MARKERS) or "?" in prompt or "？" in prompt
    for phrase in NEGATED_IMPLEMENTATION_PHRASES:
        directive_text = directive_text.replace(phrase, " ")
    for phrase in ANSWER_ONLY_EXECUTION_CONTEXT_PHRASES:
        directive_text = directive_text.replace(phrase, " ")
    if question_context:
        for phrase in MECHANISM_QUESTION_CONTEXT_PHRASES:
            directive_text = directive_text.replace(phrase, " ")
    directive = any(marker in directive_text for marker in IMPLEMENTATION_MARKERS)
    strong_directive = any(marker in directive_text for marker in STRONG_IMPLEMENTATION_MARKERS)
    conditional_directive = (
        directive
        and any(marker in directive_text for marker in CONDITIONAL_IMPLEMENTATION_MARKERS)
        and not any(marker in normalized for marker in META_QUESTION_MARKERS)
    )
    if question_context and not (strong_directive or conditional_directive):
        return False
    return directive


def classify_prompt_intent(prompt: str) -> dict[str, str]:
    normalized = normalize_prompt_text(prompt)
    question = any(marker in normalized for marker in QUESTION_ONLY_MARKERS) or "?" in prompt or "？" in prompt
    implementation = prompt_has_directive_authority(prompt)
    review = any(marker in normalized for marker in REVIEW_MARKERS) or prompt_requests_code_excerpt(normalized)

    if implementation:
        return {
            "prompt_kind": "mixed" if question else "directive",
            "authorized_scope": "implementation",
            "action_evidence": "substantive",
            "reason": "implementation directive marker present",
        }
    if review:
        return {
            "prompt_kind": "mixed" if question else "directive",
            "authorized_scope": "review_only",
            "action_evidence": "diagnostic",
            "reason": "review or diagnostic marker present without implementation directive",
        }
    if question:
        return {
            "prompt_kind": "question",
            "authorized_scope": "answer_only",
            "action_evidence": "none",
            "reason": "question marker present without implementation directive",
        }
    return {
        "prompt_kind": "mixed",
        "authorized_scope": "answer_only",
        "action_evidence": "none",
        "reason": "no implementation directive marker present",
    }


def prompt_intent_from_event(event: dict[str, Any]) -> dict[str, str]:
    stored = event.get("prompt_intent")
    if isinstance(stored, dict):
        scope = stored.get("authorized_scope")
        evidence = stored.get("action_evidence")
        kind = stored.get("prompt_kind")
        if isinstance(scope, str) and isinstance(evidence, str) and isinstance(kind, str):
            return {
                "prompt_kind": kind,
                "authorized_scope": scope,
                "action_evidence": evidence,
                "reason": str(stored.get("reason") or "stored prompt_intent"),
            }
    prompt = prompt_text_from_event(event)
    if isinstance(prompt, str) and prompt.strip():
        return classify_prompt_intent(prompt)
    return {
        "prompt_kind": "mixed",
        "authorized_scope": "implementation",
        "action_evidence": "substantive",
        "reason": "legacy marker without prompt text defaults to implementation enforcement",
    }

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
    "有没有",
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
    "直接做",
    "直接",
    "做掉",
    "变成",
    "做成",
    "编成",
    "编程",
    "编写",
    "写入",
    "写好",
    "写完",
    "固化",
    "落盘",
    "沉淀",
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
    "升级",
    "改造",
    "赞同",
    "同意",
    "处理",
    "处置",
    "实施",
    "授权",
    "允许",
    "批准",
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
    "没有授权",
    "未授权",
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
    "直接做",
    "直接",
    "做掉",
    "跑",
    "继续",
    "先把",
    "帮我",
    "do it",
    "授权",
    "允许",
    "批准",
}

STATUS_CONFIRMATION_DIRECTIVE_OVERRIDES = {
    "请",
    "请你",
    "请也要",
    "授权",
    "允许",
    "批准",
    "直接做",
    "开始修复",
    "开始执行",
    "彻底杜绝",
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
    "本质",
    "含义",
    "什么意思",
    "是什么意思",
    "提示词",
    "逻辑发生变化",
    "导致你的任务",
    "机械性",
}

META_CLARIFICATION_MARKERS = {
    "任务需求本质",
    "提问的本质",
    "本质含义",
    "你有分析过",
    "是否分析过",
    "有没有分析过",
    "你只是机械",
    "机械性的执行",
    "这句话是什么意思",
    "这句话是",
    "是什么意思",
    "什么含义",
    "我的提示词导致",
    "提示词导致",
    "导致你的任务",
    "导致你的逻辑",
    "任务或者逻辑发生变化",
    "逻辑发生变化",
}

META_CLARIFICATION_ACTION_OVERRIDES = [
    r"(?:请|立刻|现在|马上|直接|去).{0,8}(?:修复|执行|改|修改|落地|实现)",
    r"(?:开始|继续).{0,8}(?:修复|执行|改|修改|落地|实现)",
    r"(?:修复|执行|改掉|修改|落地|实现).{0,12}(?:这个|该|上述|问题)",
]
META_CLARIFICATION_ACTION_REGEXES = [re.compile(pattern, re.I | re.S) for pattern in META_CLARIFICATION_ACTION_OVERRIDES]

STATUS_CONFIRMATION_PATTERNS = [
    r"(?:你|你们|cap|redcap|棱镜).{0,24}(?:是否|是不是|有没有|有无|是否已经|是不是已经|有没有已经|有).{0,24}(?:完成|修复|解决|处理|执行|落地|实现|做完|搞定)",
    r"(?:是否|是不是|有没有|有无).{0,24}(?:完成|修复|解决|处理|执行|落地|实现|做完|搞定).{0,12}(?:了|了吗|了么|没有|没)",
    r"(?:完成|修复|解决|处理|执行|落地|实现|做完|搞定).{0,12}(?:了吗|了么|了没有|了没|没有|没)",
]
STATUS_CONFIRMATION_REGEXES = [re.compile(pattern, re.I | re.S) for pattern in STATUS_CONFIRMATION_PATTERNS]
PRE_EXECUTION_DISCUSSION_PATTERNS = [
    r"(?:不要|别|先别|不用|不必|不要着急|不要急着).{0,12}(?:开动|开始|执行|落地|实施)",
    r"(?:先|暂时).{0,8}(?:回答|评估|讨论|判断).{0,24}(?:是否可行|可不可行|可行性|方案)",
    r"(?:是否可行|可不可行|可行性).{0,40}(?:讨论|拿出来|方案|缓解|更好)",
]
PRE_EXECUTION_DISCUSSION_REGEXES = [re.compile(pattern, re.I | re.S) for pattern in PRE_EXECUTION_DISCUSSION_PATTERNS]
EXECUTION_AFTER_DISCUSSION_PATTERNS = [
    r"(?:没问题|可行|可以|通过|确认).{0,12}(?:就|则|的话).{0,8}(?:直接)?(?:做|执行|开动|开始|落地|实施|修复)",
    r"(?:顺便|一起|同时).{0,8}(?:做掉|执行|落地|实施|修复)",
    r"(?:讨论|评估|看看|分析).{0,24}(?:后|完|清楚).{0,12}(?:直接)?(?:做|执行|开动|开始|落地|实施|修复)",
    r"(?:先|暂时).{0,12}(?:讨论|评估|看看|分析).{0,32}(?:然后|再).{0,8}(?:做|执行|开动|开始|落地|实施|修复)",
]
EXECUTION_AFTER_DISCUSSION_REGEXES = [re.compile(pattern, re.I | re.S) for pattern in EXECUTION_AFTER_DISCUSSION_PATTERNS]

AWARENESS_CONFIRMATION_PATTERNS = [
    r"(?:你|你们|cap|redcap|棱镜).{0,32}(?:是否|是不是|有没有|有无|能否|可以).{0,32}(?:察觉|意识到|注意到|认可|认同|同意|理解|get到)",
    r"(?:这个|上述|前面|刚才).{0,24}(?:问题|判断|说法|机制|现象).{0,32}(?:你|你们|cap|redcap|棱镜).{0,24}(?:是否|是不是|有没有|有无).{0,24}(?:察觉|意识到|注意到|认可|认同|同意|理解|get到)",
    r"(?:你|你们|cap|redcap|棱镜).{0,24}(?:认可|认同|同意|理解|察觉|意识到|注意到).{0,12}(?:吗|么|？|\?)",
]
AWARENESS_CONFIRMATION_REGEXES = [re.compile(pattern, re.I | re.S) for pattern in AWARENESS_CONFIRMATION_PATTERNS]
AWARENESS_CONFIRMATION_ACTION_PATTERNS = [
    r"(?:认可|认同|同意|理解|察觉|意识到|注意到|get到).{0,16}(?:的话|后|就|则|请|帮我|直接|立刻|马上|顺便|并|然后|再).{0,24}(?:执行|修复|修改|改掉|落地|实现|处理|做|开始|继续|写|提交|推送|运行|跑)",
    r"(?:是否|是不是|有没有|有无|能否|可以|可否).{0,24}(?:帮我|直接|现在|立刻|马上|开始|继续|去|把|并|顺便).{0,24}(?:执行|修复|修改|改掉|落地|实现|处理|做|写|提交|推送|运行|跑)",
    r"(?:如果|若).{0,16}(?:认可|认同|同意|理解|可以|可行|没问题).{0,24}(?:执行|修复|修改|改掉|落地|实现|处理|做|开始|继续|写|提交|推送|运行|跑)",
]
AWARENESS_CONFIRMATION_ACTION_REGEXES = [re.compile(pattern, re.I | re.S) for pattern in AWARENESS_CONFIRMATION_ACTION_PATTERNS]

DOCUMENT_WRITE_AUTHORITY_PATTERNS = [
    r"(?:编写|写入|写好|写完|固化|落盘|沉淀|整理成|设计好).{0,32}(?:方案|文档|合同|工作流|手册|计划|测试方案|需求文档|架构文档)",
    r"(?:方案|文档|合同|工作流|手册|计划|测试方案|需求文档|架构文档).{0,32}(?:写入|固化|落盘|沉淀|编写|写好|写完)",
    r"(?:只需要|仅需要|本次只需要).{0,24}(?:编写|写入|写好|写完|固化|落盘|沉淀).{0,32}(?:方案|文档|合同|工作流|手册|计划)",
]
DOCUMENT_WRITE_AUTHORITY_REGEXES = [re.compile(pattern, re.I | re.S) for pattern in DOCUMENT_WRITE_AUTHORITY_PATTERNS]


def normalize_prompt_text(value: str) -> str:
    return " ".join(value.casefold().split())


def strip_quoted_spans(value: str) -> str:
    return re.sub(r"`[^`]*`|“[^”]*”|\"[^\"]*\"|'[^']*'|‘[^’]*’", " ", value)


def prompt_requests_code_excerpt(normalized: str) -> bool:
    return (
        any(marker in normalized for marker in CODE_EXCERPT_REQUEST_MARKERS)
        and any(marker in normalized for marker in CODE_REFERENCE_MARKERS)
    )


def prompt_is_status_confirmation_question(prompt: str) -> bool:
    directive_text = strip_quoted_spans(normalize_prompt_text(prompt))
    for phrase in NEGATED_IMPLEMENTATION_PHRASES:
        directive_text = directive_text.replace(phrase, " ")
    if any(marker in directive_text for marker in STATUS_CONFIRMATION_DIRECTIVE_OVERRIDES):
        return False
    return ("?" in prompt or "？" in prompt) and any(
        pattern.search(prompt) for pattern in STATUS_CONFIRMATION_REGEXES
    )


def prompt_is_pre_execution_discussion(prompt: str) -> bool:
    if any(pattern.search(prompt) for pattern in EXECUTION_AFTER_DISCUSSION_REGEXES):
        return False
    if prompt_has_document_write_authority(prompt):
        return False
    return any(pattern.search(prompt) for pattern in PRE_EXECUTION_DISCUSSION_REGEXES)


def prompt_has_document_write_authority(prompt: str) -> bool:
    """Return true for explicit requests to write design/doc/contract artifacts.

    This is deliberately narrower than generic "discuss a plan" language: it
    only fires when the user asks for a concrete file-like deliverable. It lets
    "write the plan, but do not run E2E" authorize document edits without
    weakening the guard that keeps pure feasibility questions answer-only.
    """
    normalized = normalize_prompt_text(prompt)
    if any(marker in normalized for marker in ["不要修改", "不要改", "不修改", "不改", "只回答", "仅回答"]):
        return False
    return any(pattern.search(prompt) for pattern in DOCUMENT_WRITE_AUTHORITY_REGEXES)


def prompt_is_meta_clarification_question(prompt: str) -> bool:
    normalized = normalize_prompt_text(prompt)
    question_context = any(marker in normalized for marker in QUESTION_ONLY_MARKERS) or "?" in prompt or "？" in prompt
    if not question_context:
        return False
    if any(pattern.search(prompt) for pattern in META_CLARIFICATION_ACTION_REGEXES):
        return False
    return any(marker in normalized for marker in META_CLARIFICATION_MARKERS)


def prompt_has_explicit_action_question(prompt: str) -> bool:
    return any(pattern.search(prompt) for pattern in AWARENESS_CONFIRMATION_ACTION_REGEXES)


def prompt_is_awareness_confirmation_question(prompt: str) -> bool:
    normalized = normalize_prompt_text(prompt)
    question_context = any(marker in normalized for marker in QUESTION_ONLY_MARKERS) or "?" in prompt or "？" in prompt
    if not question_context:
        return False
    if prompt_has_explicit_action_question(prompt):
        return False
    if any(pattern.search(prompt) for pattern in META_CLARIFICATION_ACTION_REGEXES):
        return False
    return any(pattern.search(prompt) for pattern in AWARENESS_CONFIRMATION_REGEXES)


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
    if prompt_is_pre_execution_discussion(prompt):
        return False
    if prompt_has_document_write_authority(prompt):
        return True
    if prompt_has_explicit_action_question(prompt):
        return True
    if prompt_is_status_confirmation_question(prompt):
        return False
    if prompt_is_meta_clarification_question(prompt):
        return False
    if prompt_is_awareness_confirmation_question(prompt):
        return False
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
    if prompt_is_meta_clarification_question(prompt):
        return {
            "prompt_kind": "question",
            "authorized_scope": "answer_only",
            "action_evidence": "none",
            "reason": "meta clarification question does not authorize implementation",
        }
    if prompt_is_pre_execution_discussion(prompt):
        return {
            "prompt_kind": "question" if question else "mixed",
            "authorized_scope": "answer_only",
            "action_evidence": "none",
            "reason": "pre-execution feasibility discussion explicitly asks not to start implementation",
        }
    if prompt_is_awareness_confirmation_question(prompt):
        return {
            "prompt_kind": "question",
            "authorized_scope": "answer_only",
            "action_evidence": "none",
            "reason": "awareness or agreement confirmation question does not authorize implementation",
        }
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
    for key in ["prompt_intent_effective", "prompt_intent"]:
        stored = event.get(key)
        if not isinstance(stored, dict):
            continue
        scope = stored.get("authorized_scope")
        evidence = stored.get("action_evidence")
        kind = stored.get("prompt_kind")
        if isinstance(scope, str) and isinstance(evidence, str) and isinstance(kind, str):
            return {
                "prompt_kind": kind,
                "authorized_scope": scope,
                "action_evidence": evidence,
                "reason": str(stored.get("reason") or f"stored {key}"),
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

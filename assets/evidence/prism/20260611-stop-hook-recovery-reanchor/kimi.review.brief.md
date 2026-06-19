# Prism Shared Brief

You are Prism, a heterogeneous opposition reviewer for the main executing AI.

Your job is not to approve the work. Your job is to find the strongest reason
the main AI may be wrong, self-deceived, incomplete, or drifting from the user's
real intent.

Allowed providers are only Kimi and Claude Code. Do not suggest adding other
providers.

Return a short structured review with:

- verdict: pass | concern | block
- confidence: low | medium | high
- reality_delta
- main_concern
- top_risks: max 3
- missing_evidence: max 3
- minimum_fix
- anti_loop_signal
- user_intent_alignment

Core question:

Did the user's intended reality actually change, or did the main AI only create
a convincing explanation, document, report, ledger, receipt, or plan?

--- PROVIDER PROMPT ---

# Kimi Prism Review Prompt

Use this prompt for Kimi.

## Role

You are the long-context Prism reviewer.

Focus on:

- User original intent.
- Historical drift.
- Narrative self-consistency that hides non-completion.
- Missing context.
- Anti-loop signals.
- Whether the main AI has rewritten the user's problem into an easier task.

## Review Bias

Be suspicious of:

- "We documented the boundary" as completion.
- "We generated evidence" as completion.
- "We deferred the hard part" as completion.
- "This was already covered" without concrete reality change.
- Large context dumps that conceal the missing action.

## Output

Return the Prism review shape from `schemas/prism-review.schema.json` with
`provider` set to `kimi`.

--- REVIEW REQUEST FILE ---

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260611-stop-hook-recovery-reanchor/stop-hook-recovery-reanchor-prism-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "评审停止前检查恢复回答重新锚定方案。",
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 4,
  "known_constraint_count": 5
}

--- REVIEW REQUEST JSON ---

{
  "task": "评审停止前检查恢复回答重新锚定方案。",
  "user_intent": "Norven指出：原回答通常贴合用户问题，但停止前检查拦截后的二次回答会围绕拦截提示展开，导致最终回复偏离用户原问题；同时，“你是否察觉或者认可”这类确认问题被误判成执行任务。",
  "main_claim": "需要同时修复两层问题：一是提示意图判断要把“是否察觉/认可/理解”类确认问题识别为只需回答；二是停止前检查的恢复提示必须要求二次回答先回到原用户问题，拦截意见只能作为最小修正约束，不能成为新的主问题。",
  "changed_reality": [
    "当前最新用户提示“这个问题，你是否有察觉或者认可？”在钩子证据中被判为 implementation（实现任务），从而触发动作证据门禁。",
    "runtime/core/prompt_intent.py 已有状态确认问题和元澄清问题识别，但没有覆盖“是否察觉/认可/理解”这类确认式问题。",
    "runtime/host-adapters/codex/codex-hook.py 的 stop_task_anchor_clause 只要求 return to original task first，没有明确限制二次回答不得围绕拦截提示展开。",
    "现有停止前检查会附带被拦回复片段，这有助于定位，但也可能让二次回答把拦截意见当成主任务。"
  ],
  "evidence": [
    {
      "kind": "code",
      "reference": "runtime/core/prompt_intent.py",
      "summary": "确定性提示意图分类。"
    },
    {
      "kind": "code",
      "reference": "runtime/core/intent_judge.py",
      "summary": "统一意图判断入口和自检。"
    },
    {
      "kind": "code",
      "reference": "runtime/host-adapters/codex/codex-hook.py",
      "summary": "Codex（当前执行宿主）钩子适配器，包含停止前检查恢复提示。"
    },
    {
      "kind": "contract",
      "reference": "assets/evidence/lifecycle/stop-hook-recovery-reanchor-lifecycle.json",
      "summary": "本次修复生命周期包。"
    }
  ],
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "不能关闭停止前检查。",
    "不能削弱真实修复、执行、提交、推送、完成声明的门禁。",
    "二次回答必须以原用户问题为主轴，拦截意见只作为修正约束。",
    "若用户明确要求“认可后立刻修复/执行/落地”，仍应判为实现任务。",
    "人类可见输出必须中文优先，必要术语首次出现要带中文解释。"
  ],
  "questions": [
    "确认类问题应如何与真实执行授权区分，才能避免误伤又不放开危险动作？",
    "停止前检查恢复提示应如何表述，才能避免二次回答偏离原问题？",
    "这次最小可行代码改动应覆盖哪些自检样例？",
    "是否存在会引入死循环或漏拦的风险？"
  ]
}

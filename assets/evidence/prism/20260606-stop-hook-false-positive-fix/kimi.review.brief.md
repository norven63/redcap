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

/private/tmp/redcap-stop-hook-false-positive-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "修复 Stop hook 终态声明守卫对正常问答、盘点回答、状态词的误伤。",
  "review_mode": "implementation_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 0,
  "known_constraint_count": 0
}

--- REVIEW REQUEST JSON ---

{
  "task": "修复 Stop hook 终态声明守卫对正常问答、盘点回答、状态词的误伤。",
  "user_intent": "Norven 无法正常交流，因为 Stop hook 把回答类内容切成恢复片段。需要保留防空转与防虚假盖章能力，同时减少误伤。",
  "main_claim": "应把 final_claim_guard 从裸子串命中改为更精确的终态声明识别，并对 answer_only/review_only 提示的普通状态盘点放宽。",
  "changed_reality": [
    "runtime/core/final_claim_guard.py 当前对 COMPLETION_TERMS 使用 substring 匹配，英文 unresolved 会因包含 resolved 而误伤。",
    "Stop hook 对 required prompt 无条件运行 final_claim_guard；answer_only 或 review_only 的回答也可能被拦。",
    "修复应增加可执行自检：仍拦截执行任务后的盖章式宣告；允许问答/盘点中列举 completed/resolved/已完成 等状态词。"
  ],
  "review_mode": "implementation_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "candidate_solution": {
    "scope": [
      "仅修改 runtime/core/final_claim_guard.py；必要时补充 self-check fixtures。",
      "不移除 Stop hook，不跳过 required prompt action evidence。",
      "保留有 marker 才能对 implementation/completion prompt 做最终宣告的规则。"
    ],
    "expected_rules": [
      "answer_only/review_only prompt：允许回答中出现状态词，除非文本明显是第一人称执行闭环宣告。",
      "implementation/completion prompt：仍对盖章式宣告强拦截，直到 lifecycle marker 匹配。",
      "英文完成词使用词边界或短语边界，避免 unresolved 命中 resolved、incomplete 命中 complete。",
      "中文词保留短语匹配，但增加问答语境宽限和自检。"
    ]
  },
  "acceptance_criteria": [
    "self-check 包含 answer_only 问答状态盘点不会被 final_claim_guard 拦截。",
    "self-check 包含 review_only 盘点表述不会被 final_claim_guard 拦截。",
    "self-check 包含 implementation required prompt 下的 已执行完/搞定了/all set 仍会被拦截。",
    "self-check 包含 unresolved 不会误触发 resolved。",
    "runtime/bin/redcap final-claim self-check 与 runtime/bin/redcap check 通过。"
  ]
}

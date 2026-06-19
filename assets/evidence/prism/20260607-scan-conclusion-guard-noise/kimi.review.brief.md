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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260607-scan-conclusion-guard-noise/scan-conclusion-guard-noise-prism-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "评审 360 度扫描结论检查的元讨论误伤修复方案",
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 0,
  "known_constraint_count": 4
}

--- REVIEW REQUEST JSON ---

{
  "task": "评审 360 度扫描结论检查的元讨论误伤修复方案",
  "user_intent": "Norven 指出当前停止前检查把“讨论扫描结论检查器是否冗余、为何误伤、如何修复”的回复误判成扫描结论，导致回复中反复出现固定状态块。",
  "main_claim": "RedCap 需要收窄扫描结论检查的触发边界：真实扫描结论仍必须有结构化扫描证据；关于检查器自身的元讨论不应被强制要求扫描状态块。",
  "current_state": {
    "known_failure": "定向探针显示，元讨论提示与机制解释回复仍触发扫描结论检查，并被要求附带结构化扫描状态块。",
    "current_guard": "runtime/core/scan_conclusion_guard.py",
    "current_trigger": "只要提示或回复合并文本同时命中扫描语境和结论语境，就触发检查。"
  },
  "changed_reality": [
    "当前还没有实施修复；已确认现有自检没有覆盖元讨论误伤。",
    "本次计划改变运行时触发边界，而不是只修改汇报措辞或补记录。",
    "修复后应能通过定向探针证明：元讨论不触发扫描状态块，真实扫描结论仍被拦截。"
  ],
  "planned_change": [
    "新增元讨论识别：当语境是在讨论检查、拦截、误伤、冗余、触发条件、修复方案时，默认不视为扫描结论。",
    "新增直接结论请求识别：当用户明确询问扫描结论、归纳结果、完成状态或迁移判断时，仍触发检查。",
    "保留危险结论兜底：只要回复实际给出未完成扫描的最终结论或迁移判断，即使处在元讨论语境中也必须拦截。",
    "扩展自检：覆盖元讨论放行、真实结论拦截、直接结论请求仍受控三类场景。"
  ],
  "requested_review": [
    "判断该方案是否会削弱对真实 360 度扫描结论冒充完成的拦截。",
    "判断元讨论例外是否足够窄，是否会把真实扫描结论误放行。",
    "指出还需要增加哪些测试，才能证明误伤已经修复而不是换一种方式空转。",
    "如果不同意方案，请给出替代触发边界。"
  ],
  "known_constraints": [
    "不得宣称 360 度旧 RedCap 扫描已经完成。",
    "不得批量读取旧 RedCap 仓库。",
    "不得把生命周期包、评审请求或记录当作任务完成。",
    "给人看的内容必须中文优先、可读，不堆机器流程名词。"
  ],
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ]
}

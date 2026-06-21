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

## Runtime Boundary

You are running through Kimi Code CLI in non-interactive prompt mode.

- Default to using only the text included in this prompt.
- Do not inspect files unless this prompt contains an `AUTHORIZED FILE ACCESS`
  section.
- If `AUTHORIZED FILE ACCESS` is present, read only the generated bundle JSON
  named in that section. Do not inspect the original source paths directly.
- Do not run commands.
- Do not call tools.
- Do not ask follow-up questions.
- If evidence is missing from the prompt text or authorized bundle, report it
  as missing evidence instead of fetching more files.

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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-residual-final-solution-plan/request.r7.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "最终复审 RedCap 残留待完善项最终解决方案书第七轮",
  "review_mode": "design_review",
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
  "task": "最终复审 RedCap 残留待完善项最终解决方案书第七轮",
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "user_intent": "只确认第六轮 minimum_fix 是否已经写入方案书；不执行开发实现，不新增 RSP，不继续扩写方案范围。",
  "main_claim": "第七轮方案补齐了 rsp-contract check 的检查语义、claim_file 与 evidence_file 最小 JSON schema、放宽标准例外流程、plan-change-control 示例。方案现在应冻结，后续转入 RSP-00/RSP-11/RSP-12 实施。",
  "changed_reality": [
    "补充 has_positive_acceptance、has_negative_probe、claim_references_evidence、new_issue_is_queued 的通过/失败条件。",
    "补充 claim_file 最小 JSON schema：rsp、claim_scope、completion_level、evidence_file、new_issues。",
    "补充 evidence_file 最小 JSON schema：rsp、acceptance.positive.status、acceptance.negative.status、changed_reality、artifacts。",
    "补充 standard_change=loosen 的例外流程：默认拒绝，必须说明不可执行原因、替代标准、Norven 授权、Prism 复核，并标记 loosen_with_approval。",
    "补充 plan-change-control 标注示例。"
  ],
  "non_goals": [
    "不实现 rsp-contract check。",
    "不关闭任何 RSP。",
    "不新增 RSP。",
    "不声明 RedCap 完整复活。"
  ],
  "reviewable_plan_excerpt": {
    "check_semantics": [
      "has_positive_acceptance 通过条件：方案书对应 RSP 存在正向验收，且 evidence_file.acceptance.positive.status=pass。",
      "has_negative_probe 通过条件：方案书对应 RSP 存在负向探针，且 evidence_file.acceptance.negative.status=pass。",
      "claim_references_evidence 通过条件：claim_file.evidence_file 与 --evidence-file 一致。",
      "new_issue_is_queued 通过条件：claim_file.new_issues 非空时，每个新问题包含 queue_target，且指向已有 RSP 或 plan-change-control。"
    ],
    "schemas": [
      "claim_file 必填字段：rsp、claim_scope、completion_level、evidence_file、new_issues。",
      "evidence_file 必填字段：rsp、acceptance.positive.status、acceptance.negative.status、changed_reality、artifacts。"
    ],
    "loosen_exception": [
      "standard_change=loosen 默认拒绝。",
      "必须说明原标准为何不可执行、会造成什么误伤或死锁。",
      "必须给出替代标准，且替代标准不能低于用户原始目标。",
      "必须经过 Norven 明确授权和 Prism 复核。",
      "通过后只能标记 loosen_with_approval。"
    ],
    "freeze": [
      "方案通过 Prism 后冻结。",
      "后续必须进入 RSP-00/RSP-11/RSP-12 实施，不再继续扩写方案。"
    ]
  },
  "review_questions": [
    "第六轮 Claude Code minimum_fix 是否已经解决？",
    "方案阶段是否还有 blocker，还是应当冻结并进入实施？",
    "若仍有 concern，请区分方案阶段必须修复的问题与实施阶段自然要解决的问题。"
  ],
  "required_response": {
    "format": "json",
    "fields": [
      "verdict",
      "confidence",
      "reality_delta",
      "main_concern",
      "top_risks",
      "missing_evidence",
      "minimum_fix",
      "anti_loop_signal",
      "user_intent_alignment"
    ]
  },
  "language_policy": "中文优先；只输出一个 JSON 对象，不要输出 Markdown，不要输出思考过程。"
}


--- KIMI FILE ACCESS ---
mode: prompt-only
No file reading is authorized for this review.

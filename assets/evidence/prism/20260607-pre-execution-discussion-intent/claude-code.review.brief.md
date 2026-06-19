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

# Claude Code Prism Review Prompt

Use this prompt for Claude Code.

## Role

You are the engineering Prism reviewer.

Focus on:

- Concrete implementation risks.
- Bugs, regressions, and missing tests.
- Unsafe file operations.
- Workspace and runtime boundary leaks.
- Whether the diff actually implements the claim.
- Whether verification matches the risk.

## Review Bias

Be suspicious of:

- Tests that only prove the checker exists.
- Docs-only changes for behavior tasks.
- Broad edits that exceed the task.
- Generated evidence that is not tied to the changed behavior.
- Claims that rely on closeout artifacts instead of implementation facts.

## Output

Return the Prism review shape from `schemas/prism-review.schema.json` with
`provider` set to `claude-code`.

--- REVIEW REQUEST FILE ---

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260607-pre-execution-discussion-intent/pre-execution-discussion-intent-prism-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "评审停止前检查对“先别执行、先回答可行性”提示的误伤修复",
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 0,
  "known_constraint_count": 3
}

--- REVIEW REQUEST JSON ---

{
  "task": "评审停止前检查对“先别执行、先回答可行性”提示的误伤修复",
  "user_intent": "Norven 明确要求先回答一气呵成任务是否可行，不要急着开动；停止前检查仍要求实施动作证据，造成讨论型提示被误判为执行任务。",
  "main_claim": "RedCap 需要把“先别开动、先回答是否可行、拿出来讨论”的提示判为只回答，不要求同轮实施动作证据。",
  "current_state": {
    "known_failure": "提示中描述了未来要完成、执行、落地的任务链，但同时明确说不要着急先开动；现有分类器先命中动作词，导致停止前检查误伤。",
    "affected_files": [
      "runtime/core/prompt_intent.py",
      "runtime/core/intent_judge.py",
      "runtime/prism/bin/turn-action-check"
    ]
  },
  "changed_reality": [
    "新增预执行讨论识别：明确先别执行、先回答可行性、拿出来讨论时，分类为 answer_only。",
    "新增自检样例覆盖真实提示，防止再次误判。",
    "定向动作检查已验证该原始提示能通过停止前动作检查。"
  ],
  "planned_change": [
    "保留真正执行请求的空转拦截。",
    "只放行明确的预执行可行性讨论，不放行没有限制语的执行任务。",
    "通过分类器自检、动作检查和全量检查验证。"
  ],
  "requested_review": [
    "判断该修复是否会让真正的执行任务绕过动作证据要求。",
    "判断预执行讨论识别是否过宽。",
    "指出是否还需要加入对照样例，证明普通“请执行”仍被判为实施。"
  ],
  "known_constraints": [
    "不得削弱真实执行任务的空转拦截。",
    "不得把讨论型回答强制变成实施动作。",
    "给人看的内容必须中文优先、人类可读。"
  ],
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ]
}

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

## Authorized File Access

If the review request JSON contains `file_access.mode = "bounded-read"` and an
`allowed_paths` list, you are authorized and expected to inspect those paths
directly before judging implementation reality.

- Read only the listed paths unless the prompt explicitly expands scope.
- Treat unreadable listed files as missing evidence, not as proof that the main
  claim is false.
- Do not rely only on the request's narrative when code or evidence files are
  authorized.
- When the request also includes generated compact audit evidence, prefer that
  compact evidence over broad source reads if context is tight.

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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260621-rsp-contract-first-batch/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "RSP-00/RSP-11/RSP-12 首批实施与当前总检查自检语义修复",
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 5,
  "known_constraint_count": 5
}

--- REVIEW REQUEST JSON ---

{
  "task": "RSP-00/RSP-11/RSP-12 首批实施与当前总检查自检语义修复",
  "user_intent": "Norven 要求根据 residual-todo-final-solution-plan 逐项实施和落地，测试验证每个问题确切解决；如果没有解决就继续设计、修复、验证，直到没有残留问题或遇到必须人工介入的节点。",
  "main_claim": "本轮准备进入首批实现：先修复 revival-followthrough self-check 与当前 open-loop 队列状态不一致的问题，再实现 runtime/bin/redcap rsp-contract check，作为 RSP-00/RSP-11/RSP-12 的完成口径防线。",
  "changed_reality": [
    "当前 runtime/bin/redcap check 失败在 revival-followthrough self-check，原因是自检把 closeout_allowed=true 当成失败，和当前 P0/P1 已 verified 的队列事实相反。",
    "当前 runtime/bin/redcap rsp-contract check --plan assets/docs/residual-todo-final-solution-plan.md 返回 unknown command，说明 RSP-00 的机器防线尚未落地。",
    "本轮实现必须补正上述两个运行时事实，而不是只更新方案书或状态说明。"
  ],
  "evidence": [
    {
      "kind": "document",
      "reference": "assets/docs/residual-todo-final-solution-plan.md",
      "summary": "方案书要求 RSP-00、RSP-11、RSP-12 作为前三项实施，并定义 rsp-contract check 的最小接口、输出、正向验收和负向探针。"
    },
    {
      "kind": "log",
      "reference": "runtime/bin/redcap check",
      "summary": "本轮运行总检查失败在 revival-followthrough self-check。"
    },
    {
      "kind": "log",
      "reference": "runtime/bin/redcap revival-followthrough open-loop-check",
      "summary": "单独检查显示 open_p0_p1_count=0 且 closeout_allowed=true。"
    },
    {
      "kind": "log",
      "reference": "runtime/bin/redcap rsp-contract check --plan assets/docs/residual-todo-final-solution-plan.md",
      "summary": "当前命令不存在，返回 unknown command。"
    },
    {
      "kind": "other",
      "reference": "runtime/core/revival_followthrough.py",
      "summary": "cmd_self_check 中存在把 current_open_loop.closeout_allowed is True 判为失败的逻辑，需评估是否应改为要求当前已验证队列允许收口。"
    }
  ],
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "不得把 RSP 方案书、评审记录或生命周期包当作完成证据。",
    "不得降低完成口径；修复必须正面解决行为问题，保留原有防空转、防误收口能力。",
    "rsp-contract check 必须至少覆盖 claim_file、evidence_file、正向验收、负向探针、完成声明证据引用、新问题入队和未知 RSP 失败。",
    "revival-followthrough self-check 的修复不能放松 open-loop 队列验证；只允许修正自检夹具或语义反转。",
    "本轮通过只能证明首批 RSP 完成口径防线和当前自检一致性，不得声明 RedCap 完整复活终局完成。"
  ]
}

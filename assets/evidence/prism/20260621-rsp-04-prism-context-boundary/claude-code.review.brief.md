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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260621-rsp-04-prism-context-boundary/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "RSP-04 Prism 通信上下文边界设计评审",
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 0,
  "known_constraint_count": 5
}

--- REVIEW REQUEST JSON ---

{
  "task": "RSP-04 Prism 通信上下文边界设计评审",
  "task_id": "20260621-rsp-04-prism-context-boundary",
  "risk_level": "medium",
  "user_intent": "实施 RSP-04：Prism 需要足够上下文，但 raw 大输出和大文件正文不能直接进入 Cap 主上下文。",
  "main_claim": "计划新增 prism-context 边界检查：请求必须携带 file_access 边界；provider 输出必须落 raw、brief、structured review 三层；Cap consumption manifest 只能列 brief 与 structured review，raw 仅做审计回放。",
  "changed_reality": [
    "准备新增 assets/contracts/prism-context-boundary.json 定义通信边界、行长、stdout、raw 和 consumption 规则。",
    "准备新增 runtime/core/prism_context_boundary.py，提供 check 和 self-check。",
    "准备使用 RSP-03 真实 Prism raw/brief/review 产物作为 RSP-04 大输出样本。",
    "准备新增 assets/evidence/rsp/rsp-04-context-consumption.json 记录 Cap 默认消费哪些文件、哪些 raw 只允许审计回放。",
    "准备把 prism-context-boundary-check 接入 runtime/bin/redcap 和聚合检查。"
  ],
  "review_mode": "design_review",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "file_access": {
    "mode": "bounded-read",
    "paths": [
      "assets/docs/residual-todo-final-solution-plan.md",
      "runtime/prism/bin/prism-dispatch",
      "assets/evidence/prism/20260621-rsp-03-provider-health/request-post-implementation.json",
      "assets/evidence/prism/20260621-rsp-03-provider-health/kimi.post.review.json",
      "assets/evidence/prism/20260621-rsp-03-provider-health/kimi.post.review.brief.md",
      "assets/evidence/prism/20260621-rsp-03-provider-health/kimi.post.raw.meta.json",
      "assets/evidence/lifecycle/20260621-rsp-04-prism-context-boundary.json"
    ],
    "max_files": 9,
    "max_bytes_per_file": 90000,
    "max_total_bytes": 240000,
    "purpose": "评审 RSP-04 通信上下文边界设计是否能防止 raw 大输出进入 Cap 主上下文，同时保留审计回放能力。"
  },
  "known_constraints": [
    "不禁止 Prism 读取必要本地文件。",
    "不把上下文控制变成信息不足。",
    "不把 raw 输出直接灌入 Cap 上下文。",
    "常规检查应验证边界，但不应重新触发 provider live 调用。",
    "本条只关闭 RSP-04 当前通信边界检查范围，不声明 RedCap 完整复活。"
  ],
  "questions_for_prism": [
    "用 consumption manifest 约束 Cap 只读 brief 和 structured review，是否能正面解决上下文膨胀问题？",
    "raw 只做审计回放的设计是否会损失必要信息？",
    "负向夹具应覆盖哪些绕过路径，才能防止 raw 被主上下文消费？",
    "是否需要把该检查接入常规 redcap check？"
  ]
}

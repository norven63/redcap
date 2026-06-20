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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-e2e-failed-retention-followup/claude-code.rebuttal.request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Bounded Prism rebuttal for claude-code concern",
  "review_mode": "rebuttal_review",
  "risk_level": "medium",
  "requested_providers": [
    "claude-code"
  ],
  "evidence_count": 1,
  "known_constraint_count": 3
}

--- REVIEW REQUEST JSON ---

{
  "task": "Bounded Prism rebuttal for claude-code concern",
  "user_intent": "Give the same Prism provider one bounded opportunity to evaluate RedCap's proposed rejection evidence.",
  "main_claim": "Claude Code 的 block 可能基于过期或不完整 diff：failed-run 保留治理实际位于 runtime/core/complete_revival_e2e.py，且 cmd_run 外层入口会调用 attach_e2e_run_retention_result 并持久化带 retention 的运行摘要；OL-10 仍不关闭完整 E2E 证明。",
  "changed_reality": [
    "补充 code-facts.json，列出 complete_revival_e2e.py 中默认阈值、plan_e2e_run_retention、attach_e2e_run_retention_result、cmd_run 调用点、prune-runs 参数传入和旧失败目录行为自检行号。"
  ],
  "review_mode": "rebuttal_review",
  "risk_level": "medium",
  "requested_providers": [
    "claude-code"
  ],
  "evidence": [
    "assets/evidence/prism/20260620-e2e-failed-retention-followup/code-facts.json"
  ],
  "known_constraints": [
    "This is a one-round same-provider rebuttal request.",
    "The provider must return one Prism review JSON and must not open an unbounded discussion loop.",
    "The request preserves the original concern context and adds only rebuttal evidence."
  ],
  "generated_by": "runtime/prism/bin/prism rebuttal-request",
  "rebuttal_for": {
    "provider": "claude-code",
    "original_merge_path": "/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-e2e-failed-retention-followup/merge.json",
    "original_review_path": "/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-e2e-failed-retention-followup/claude-code.review.json"
  },
  "additive_rebuttal_only": true
}

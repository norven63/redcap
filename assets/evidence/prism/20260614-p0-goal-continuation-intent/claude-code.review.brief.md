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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260614-p0-goal-continuation-intent/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Review the P0 fix plan for RedCap goal-continuation intent recognition.",
  "review_mode": "design_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 4,
  "known_constraint_count": 4
}

--- REVIEW REQUEST JSON ---

{
  "task": "Review the P0 fix plan for RedCap goal-continuation intent recognition.",
  "user_intent": "Norven says the previous long-running objective already authorized implementation, but RedCap Hook intent recognition lost that authorization and blocked writes as review_only. This must be treated as P0 and fixed without weakening anti-empty-work gates.",
  "main_claim": "The correct fix is to let the hook and lifecycle validators recognize same-thread long-running goal continuations that carry explicit implementation intent, while still rejecting pure review-only prompts, cross-session continuations, unsupported completion claims, and empty-work closure.",
  "changed_reality": [
    "A lifecycle packet has been added for this P0 investigation.",
    "The current latest real UserPromptSubmit is classified as implementation, proving the user prompt now authorizes mutation.",
    "The previous repeated blocker came from the hook only seeing an older review_only UserPromptSubmit instead of the active goal objective."
  ],
  "evidence": [
    {
      "kind": "code",
      "reference": "runtime/host-adapters/codex/codex-hook.py",
      "summary": "PreToolUse mutation authorization currently depends on latest UserPromptSubmit marker freshness and authorized_scope."
    },
    {
      "kind": "code",
      "reference": "runtime/core/development_lifecycle.py",
      "summary": "Lifecycle validator already contains same_session_authorized_continuation checks."
    },
    {
      "kind": "evidence",
      "reference": "assets/evidence/lifecycle/20260614-p0-goal-continuation-intent-lifecycle.json",
      "summary": "Current P0 lifecycle packet."
    },
    {
      "kind": "evidence",
      "reference": "assets/evidence/host-hooks/codex/latest-UserPromptSubmit.json",
      "summary": "Latest prompt intent marker."
    }
  ],
  "review_mode": "design_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "Do not disable PreToolUse or Stop hook guardrails.",
    "Do not treat every goal continuation as authorized mutation.",
    "Do not require Norven to repeat an authorization that is already present in the active objective.",
    "The fix must include regression tests for review_only prompts and same-session goal continuations."
  ]
}

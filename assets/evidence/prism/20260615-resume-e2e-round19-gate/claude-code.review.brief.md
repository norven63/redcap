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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260615-resume-e2e-round19-gate/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Review whether Cap may resume the interrupted RedCap complete-revival E2E loop from the current clean baseline and run round 19.",
  "review_mode": "implementation_review",
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
  "task": "Review whether Cap may resume the interrupted RedCap complete-revival E2E loop from the current clean baseline and run round 19.",
  "user_intent": "Norven accidentally archived and restored the session, then asked Cap to recover the previous task and continue until all RedCap revival goals are met. The immediate action is to continue the already planned E2E loop, not to claim complete revival.",
  "main_claim": "The repository is at a clean baseline after commit 616a5cb, the lifecycle packet is valid, and Cap can proceed to round 19 E2E while fixing any new failure by evidence.",
  "changed_reality": [
    "Recent commits fixed E2E browser startup, behavior verification, final Prism ordering, reviewer field contracts, tester evidence timing, and related E2E acceptance checks.",
    "git status is currently clean before starting round 19.",
    "The lifecycle packet assets/evidence/lifecycle/20260615-revival-resume-after-archive-lifecycle/packet.json passes lifecycle validation.",
    "Round 19 has not yet been executed after the latest browser behavior and final verdict ordering fixes."
  ],
  "evidence": [
    {
      "kind": "command-output",
      "reference": "git status --short",
      "summary": "Clean output before round 19."
    },
    {
      "kind": "command-output",
      "reference": "git log --oneline -8",
      "summary": "Latest commit is 616a5cb, the E2E behavior and final Prism ordering fix."
    },
    {
      "kind": "lifecycle-packet",
      "reference": "assets/evidence/lifecycle/20260615-revival-resume-after-archive-lifecycle/packet.json",
      "summary": "Self-development lifecycle packet for resuming the interrupted RedCap revival task."
    },
    {
      "kind": "source",
      "reference": "runtime/core/complete_revival_e2e.py",
      "summary": "E2E runner implementation containing browser behavior verification and final Prism ordering."
    },
    {
      "kind": "source",
      "reference": "runtime/core/revival_followthrough.py",
      "summary": "Followthrough checker requiring E2E evidence quality."
    }
  ],
  "review_mode": "implementation_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "Do not claim RedCap complete revival unless terminal checks and E2E evidence pass.",
    "Do not write external E2E project runtime artifacts into the RedCap source repository.",
    "Do not bypass lifecycle, Prism, or formal usability checks.",
    "If round 19 fails, inspect structured evidence and fix the root cause before rerunning.",
    "Stop after an unresolved Prism block or concern only if it cannot be addressed with local evidence."
  ]
}

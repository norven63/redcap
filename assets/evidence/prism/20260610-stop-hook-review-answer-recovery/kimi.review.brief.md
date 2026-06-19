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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260610-stop-hook-review-answer-recovery/stop-hook-review-answer-recovery-prism-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Review the planned Stop Hook false-positive repair for stage-review answers.",
  "review_mode": "design_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 4,
  "known_constraint_count": 6
}

--- REVIEW REQUEST JSON ---

{
  "task": "Review the planned Stop Hook false-positive repair for stage-review answers.",
  "user_intent": "Norven asked why a normal answer about current new RedCap optimization needs was repeatedly distorted by Stop Hook recovery prompts, and required Cap to fix that behavior now.",
  "main_claim": "The Stop Hook should keep blocking unsupported completion claims and RedCap complete-revival overclaims, but it must allow review-only answers that list risks, optimization needs, open issues, or next priorities without claiming terminal completion.",
  "changed_reality": [
    "The current final-claim guard treats broad words such as 已完成, 收口, complete, and status-like replies as completion signals unless status-report context is recognized.",
    "The current lifecycle rules intentionally do not allow review-task evidence to create completion_claim.present=true markers.",
    "The user-facing recovery loop became incoherent because repeated rewrites tried to satisfy completion-marker requirements for a review-only answer instead of suppressing the false positive.",
    "The repair must target intent discrimination and guard wording, not global Stop Hook removal."
  ],
  "evidence": [
    {
      "kind": "code",
      "reference": "runtime/core/final_claim_guard.py",
      "summary": "Detects final completion claims and has status-report exceptions."
    },
    {
      "kind": "code",
      "reference": "runtime/core/terminal_goal_guard.py",
      "summary": "Detects terminal goal overclaims such as RedCap complete revival claims."
    },
    {
      "kind": "code",
      "reference": "runtime/host-adapters/codex/codex-hook.py",
      "summary": "Runs action, terminal-goal, and final-claim checks during Stop Hook."
    },
    {
      "kind": "contract",
      "reference": "assets/evidence/lifecycle/redcap-design-layout-review-lifecycle.json",
      "summary": "The triggering task was review-only and explicitly did not authorize RedCap complete revival closure."
    }
  ],
  "review_mode": "design_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "Do not disable Stop Hook globally.",
    "Do not let a real unsupported implementation completion claim pass.",
    "Do not let RedCap complete revival be claimed as terminally verified unless the terminal goal is actually verified.",
    "Prefer targeted exceptions for review/status/optimization answers over keyword-only broad bypasses.",
    "Keep Chinese-first human-facing recovery reasons readable.",
    "Do not create another documentation-only fix."
  ],
  "questions": [
    "What is the narrowest safe rule that allows an answer listing current RedCap optimization needs without requiring a completion marker?",
    "Which current patterns are most likely causing the false positive loop?",
    "What self-check fixtures should be added so this does not regress?",
    "Is any change needed in codex-hook recovery wording, or is the main repair inside the guard modules?"
  ]
}

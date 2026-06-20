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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-package-prism-timeout-calibration/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Review the RedCap E2E package Prism timeout calibration fix before implementation.",
  "review_mode": "risk_review",
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
  "task": "Review the RedCap E2E package Prism timeout calibration fix before implementation.",
  "user_intent": "Norven wants RedCap to become a reliable project-development workflow machine. E2E must expose real RedCap mechanism failures, but must not fail because a calibrated full package self-check is killed too early.",
  "main_claim": "Third E2E failed because complete_revival_e2e forced REDCAP_PRISM_CHECK_SUBPROCESS_TIMEOUT_SECONDS=45 for package prism check. Direct measurements show package enforcement-check completes successfully in about 59.2 seconds and source enforcement-check completes in about 63.2 seconds. Proposed fix: keep package prism check mandatory, keep outer timeout bounded, keep structured timeout evidence, but raise the child subprocess budget to a calibrated value above observed full-check duration; add self-check coverage so future changes cannot silently reintroduce an unrealistically low package child timeout.",
  "changed_reality": [
    "Third E2E produced a real external project and passed Loom role session, hook event, browser, file protocol, behavioral relation, self-purification, and cache-retention evidence.",
    "Third E2E failed AC-10 because package-prism-check.json records prism check child command timed out at 45 seconds while the outer package check did not time out.",
    "Running the installed package .redcap/runtime/prism/bin/enforcement-check directly completed with exit code 0 in about 59.215 seconds.",
    "Running source runtime/prism/bin/enforcement-check directly completed with exit code 0 in about 63.248 seconds.",
    "The current failure is therefore a false timeout calibration failure, not evidence that the package enforcement matrix is broken."
  ],
  "review_mode": "risk_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "questions": [
    "Does raising the package Prism child timeout preserve strict checking rather than bypassing or weakening it?",
    "What child timeout and outer timeout relationship should be enforced so the check remains bounded but does not false-fail normal runs?",
    "What self-checks should be added so this calibration does not regress?"
  ]
}

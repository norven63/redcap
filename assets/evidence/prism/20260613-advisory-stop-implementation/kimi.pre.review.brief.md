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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260613-advisory-stop-implementation/pre-review-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Pre-review the implementation plan for advisory Stop hook restoration.",
  "review_mode": "pre_implementation_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 0,
  "known_constraint_count": 5
}

--- REVIEW REQUEST JSON ---

{
  "task": "Pre-review the implementation plan for advisory Stop hook restoration.",
  "user_intent": "Norven authorized implementing the advisory Stop plan. The task must first roll back the no-Stop side-channel observer remnants, then restore Stop as a 100% closeout reviewer that only provides bounded suggestions and corrections. Cap must judge the suggestions independently, keep revised replies anchored to the original user task, and complete post-implementation Prism review with all findings resolved.",
  "main_claim": "The implementation should restore Stop deployment while preventing the previous answer-drift pathology. Stop may block to force a revised answer, but its reason must be structured as correction constraints for the original task, not as a new user prompt. The hot path should use deterministic checks for hard rules, bounded LLM only for ambiguous intent classification, and full Prism only for pre/post review rather than every Stop event.",
  "changed_reality": [
    "Current live Codex hook config does not include Stop.",
    "The previous no-Stop side-channel observer direction has an unfinished lifecycle/request remnant and is no longer the target design.",
    "The existing Stop branch still exists in runtime/host-adapters/codex/codex-hook.py as rollback code, but its user-facing block reasons are from the old blocking model.",
    "User explicitly authorized implementation of the advisory Stop plan after the prior answer-only discussion.",
    "The implementation must preserve lifecycle, final-claim, terminal-goal, action-evidence, and human-output checks."
  ],
  "planned_changes": [
    "Remove or supersede the incomplete no-Stop closeout-observer lifecycle/request remnants.",
    "Re-add Stop to .codex/hooks.json and assets/contracts/codex-hooks.template.json.",
    "Replace old Stop block messages with advisory correction payloads anchored to original_task_excerpt.",
    "Add six hard constraints: original-task anchor, concrete correction only, Cap arbitration wording, no hook-axis reply leakage, max correction rounds, health metrics.",
    "Update hook coverage, host-hook audit, enforcement matrix, and docs to describe advisory Stop rather than retired Stop.",
    "Run post-implementation Prism review and resolve all concern/block findings before claiming completion."
  ],
  "review_questions": [
    "Is restoring Stop as advisory reviewer safer than keeping it retired, given the proposed constraints?",
    "Which constraints must be enforced by code rather than wording?",
    "Should Stop invoke full Prism/LLM every time, or only deterministic checks plus bounded ambiguous-intent LLM?",
    "What minimum tests are required to prove the old answer-drift pathology is not reintroduced?",
    "What risks should block implementation unless fixed?"
  ],
  "known_constraints": [
    "Do not make Stop a new task source.",
    "Do not call full Prism on every Stop event.",
    "Do not weaken lifecycle completion markers, final-claim guard, terminal-goal guard, human-output policy, or action-evidence checks.",
    "Do not hide unresolved Prism concerns.",
    "Keep human-facing outputs Chinese-first."
  ],
  "expected_output": "Return strict JSON with provider, verdict, confidence, reality_delta, main_concern, top_risks, missing_evidence, minimum_fix, anti_loop_signal, and user_intent_alignment.",
  "review_mode": "pre_implementation_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ]
}

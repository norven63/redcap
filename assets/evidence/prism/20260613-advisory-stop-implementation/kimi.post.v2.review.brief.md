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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260613-advisory-stop-implementation/post-review-request-v2.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Re-review advisory Stop after resolving post-review concerns.",
  "review_mode": "post_implementation_recheck",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 0,
  "known_constraint_count": 0
}

--- REVIEW REQUEST JSON ---

{
  "task": "Re-review advisory Stop after resolving post-review concerns.",
  "user_intent": "Norven wants Stop restored as a 100% closeout review surface, but without reviving the old pathology where hook feedback becomes the reply topic. Cap must be able to judge Stop suggestions instead of blindly obeying them.",
  "main_claim": "The first post-review concerns have been addressed: Cap override is now an executable marker-based path, not only metadata, and advisory Stop has an independent end-to-end regression scenario that exercises the adapter event path rather than only checking static fields.",
  "changed_reality": [
    "runtime/host-adapters/codex/codex-hook.py now checks a per-session_id plus turn_id override marker before blocking on a Stop advisory.",
    "runtime/bin/redcap advisory-stop override writes bounded override markers with reason, source, and expiry.",
    "runtime/core/advisory_stop.py now runs an advisory-stop-answer-drift-regression scenario that submits UserPromptSubmit, triggers Stop, verifies original-task anchoring, writes an override marker, reruns Stop, and verifies continue=true plus override marker evidence.",
    "The Codex Stop timeout in .codex/hooks.json and assets/contracts/codex-hooks.template.json is now 300 seconds.",
    "assets/contracts/advisory-stop.json documents the override command and updated residual risks.",
    "runtime/bin/redcap check passed after these changes."
  ],
  "implemented_changes": [
    "Added STOP_OVERRIDE_SCHEMA_ID, stop_override_marker_path, load_stop_override, and override recording fields to the Codex hook adapter.",
    "Changed print_advisory_stop to emit continue=true when a valid Cap override marker exists.",
    "Added runtime/bin/redcap advisory-stop override with session id, turn id, reason, source, expiry, and evidence-dir options.",
    "Added e2e regression inside advisory_stop.py and included it in advisory-stop check.",
    "Extended codex-hook self-check to prove first Stop blocks and a second Stop continues after explicit override marker.",
    "Raised Stop hook timeout from 120 seconds to 300 seconds."
  ],
  "verification_performed": [
    "python3 runtime/host-adapters/codex/codex-hook.py --self-check-intent-judge",
    "runtime/bin/redcap advisory-stop check",
    "runtime/bin/redcap hook-coverage-check",
    "runtime/bin/redcap host-hook-audit",
    "runtime/bin/redcap enforcement-check",
    "runtime/bin/redcap temporary-usable-check",
    "runtime/bin/redcap check"
  ],
  "verification_result": "All listed commands passed after the concern fixes.",
  "review_questions": [
    "Does the marker-based override path satisfy the requirement that Cap can actually override a false positive Stop suggestion?",
    "Does the advisory-stop-answer-drift-regression scenario sufficiently exercise the actual adapter event path rather than only static self-check fields?",
    "Are any old Stop answer-drift failure modes still likely to recur?",
    "Is the 300-second Stop timeout acceptable for the current implementation, or should full runtime/bin/redcap check be removed from Stop hot path in a later task?",
    "Is it acceptable that a real host-fired Stop marker can only be proven after Codex reloads the new hook config and a real closeout occurs?"
  ],
  "known_limits": [
    "Full Prism provider review is still intentionally outside the Stop hot path.",
    "A real host-fired Stop event may require Codex restart because the Stop event was newly added to .codex/hooks.json.",
    "The enforcement matrix still uses adapter self-check for Stop deployment proof until a real host-fired Stop marker is available.",
    "The override path is powerful and must be used only with a concrete human-readable reason."
  ],
  "expected_output": "Return strict JSON with provider, verdict, confidence, reality_delta, main_concern, top_risks, missing_evidence, minimum_fix, anti_loop_signal, user_intent_alignment, and whether concerns are blocking.",
  "review_mode": "post_implementation_recheck",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ]
}

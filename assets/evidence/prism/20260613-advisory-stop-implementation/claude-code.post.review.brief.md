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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260613-advisory-stop-implementation/post-review-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Post-review the implemented advisory Stop hook restoration.",
  "review_mode": "post_implementation_review",
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
  "task": "Post-review the implemented advisory Stop hook restoration.",
  "user_intent": "Norven authorized restoring Stop as a 100% closeout reviewer, but only as an advisory correction mechanism that keeps Cap anchored to the original user task and prevents hook feedback from becoming the reply topic.",
  "main_claim": "The implementation restores Stop as a 100% closeout review surface while changing its failure output into structured, original-task-anchored correction constraints. It preserves hard closeout protections, avoids full Prism in the hot path, and records enough health metadata to detect drift or repeated corrections.",
  "changed_reality": [
    "Stop is present again in the live Codex hook config and the tracked hook template.",
    "The adapter Stop branch now builds advisory payloads instead of old recovery prompts.",
    "An executable advisory-stop checker validates the contract, deployment, and adapter self-check.",
    "Hook coverage, host audit, enforcement matrix, and documentation now describe advisory Stop as deployed.",
    "The stale observe-mode file and abandoned closeout-observer lifecycle remnant were removed.",
    "runtime/bin/redcap check passes with the advisory Stop checks included."
  ],
  "implemented_changes": [
    "Added advisory Stop contract at assets/contracts/advisory-stop.json with six hard constraints, decision model, payload schema, hot-path limits, and residual risks.",
    "Added runtime/core/advisory_stop.py and wired runtime/bin/redcap advisory-stop check into runtime/bin/redcap check.",
    "Changed runtime/host-adapters/codex/codex-hook.py Stop handling to produce structured advisory correction constraints, Cap override metadata, max correction rounds, no-hook-axis leakage marker, and health fields.",
    "Removed the stale .codex/stop-hook-mode observe file and removed the abandoned closeout-observer lifecycle remnant.",
    "Restored Stop in .codex/hooks.json and assets/contracts/codex-hooks.template.json.",
    "Updated hook coverage, host hook audit, enforcement matrix, temporary usable check, and host adapter docs to treat Stop as advisory closeout review rather than retired.",
    "Updated provider-dispatcher persisted-evidence probe to use the fresh 20260613 advisory Stop Prism evidence instead of the expired 20260606 evidence."
  ],
  "verification_performed": [
    "python3 runtime/host-adapters/codex/codex-hook.py --self-check-intent-judge",
    "runtime/bin/redcap advisory-stop check",
    "runtime/bin/redcap hook-coverage-check",
    "runtime/bin/redcap host-hook-audit",
    "runtime/bin/redcap enforcement-check",
    "runtime/prism/bin/prism check",
    "runtime/bin/redcap temporary-usable-check",
    "runtime/bin/redcap check"
  ],
  "verification_result": "All listed commands passed after updating the stale provider evidence probe.",
  "pre_review_findings_and_resolution": [
    "Finding: changing only wording is insufficient. Resolution: Stop branch now builds and validates structured advisory payloads and records health markers.",
    "Finding: advisory must not contradict blocking behavior. Resolution: contract defines stop_suggest as host-level closeout block with correction constraints, not a new task source.",
    "Finding: Cap must not blindly obey Stop. Resolution: payload records cap_may_override=true and override_condition.",
    "Finding: max-round guard needed. Resolution: advisory_stop_round counts per session_id plus turn_id and switches to max-correction-rounds constraint after the configured limit.",
    "Finding: old answer drift must be regression tested. Resolution: codex-hook self-check includes original-task anchoring, no blocked reply excerpt by default, human output, scan conclusion, terminal goal, and missing-action fixtures."
  ],
  "review_questions": [
    "Does the implementation genuinely prevent Stop feedback from becoming the new user task?",
    "Are the six hard constraints actually code-backed where they need to be?",
    "Is replacing the live Stop marker probe with the advisory self-check acceptable until Codex is restarted and a real Stop event fires?",
    "Does running runtime/bin/redcap check inside Stop create unacceptable latency or recursion risk?",
    "Are there any remaining stale no-Stop observer remnants or retired-Stop claims?",
    "Are any user-facing strings still likely to trigger the old answer-drift problem?"
  ],
  "known_limits": [
    "The live .codex/hooks.json file is updated, but newly added Stop event activation may require Codex host restart if the host caches hook config.",
    "Full Prism provider review is intentionally not run in the Stop hot path.",
    "The Stop matrix live marker probe currently uses adapter self-check rather than requiring an already-fired real Stop marker, to avoid false failure before host restart or first closeout.",
    "There are pre-existing unrelated workspace modifications in the worktree; review should focus on advisory Stop implementation unless it sees a direct conflict."
  ],
  "expected_output": "Return strict JSON with provider, verdict, confidence, reality_delta, main_concern, top_risks, missing_evidence, minimum_fix, anti_loop_signal, user_intent_alignment, and whether concerns are blocking.",
  "review_mode": "post_implementation_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ]
}

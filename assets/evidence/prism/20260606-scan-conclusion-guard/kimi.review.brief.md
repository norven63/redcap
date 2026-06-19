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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260606-scan-conclusion-guard/scan-conclusion-guard-prism-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Review the planned scan-conclusion guard before implementation.",
  "review_mode": "design_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 4,
  "known_constraint_count": 5
}

--- REVIEW REQUEST JSON ---

{
  "task": "Review the planned scan-conclusion guard before implementation.",
  "user_intent": "Norven challenged that Cap appeared to stop after only creating shard work and then reported as if that were an acceptable stopping point.",
  "main_claim": "RedCap needs a runtime guard that blocks final-sounding 360-degree old RedCap scan conclusions until scan completion evidence exists.",
  "current_state": {
    "scan_account": "assets/archaeology/shards/old-redcap-360-scan-account.json",
    "scan_account_status": "active",
    "task_fact": "full-360-old-redcap-scan is in_progress",
    "known_failure": "Cap created the scan-start account and then answered too close to a scan conclusion without verified shard outputs or a merge."
  },
  "changed_reality": [
    "A lifecycle packet now scopes this task as a guard fix for scan-conclusion overclaiming, not as completion of the old RedCap scan.",
    "The planned guard will inspect the current scan account and task fact ledger before allowing any final-sounding 360-degree scan conclusion.",
    "The planned hook integration will run during final reply closeout so the same mistake is caught before the answer reaches Norven."
  ],
  "planned_change": [
    "Add a RedCap command that checks whether an assistant message is making or answering a 360-degree scan conclusion.",
    "If the message is a final-sounding scan conclusion, require a merged scan account, verified shard outputs, and a verified task fact.",
    "Allow clearly provisional stage-status replies while the scan account is still active.",
    "Wire the checker into runtime/bin/redcap check and the Codex Stop hook path.",
    "Add self-check fixtures that prove the active-scan conclusion claim is blocked and the provisional status answer is allowed."
  ],
  "requested_review": [
    "Challenge whether this guard actually fixes the empty-work recurrence instead of merely documenting it.",
    "Challenge whether the proposed evidence requirements are too weak or too strict.",
    "Identify any missing hook integration point that would let the same mistake recur in final replies.",
    "Confirm whether implementation can proceed without bulk-reading the old RedCap repository."
  ],
  "evidence": [
    {
      "kind": "source",
      "reference": "assets/archaeology/shards/old-redcap-360-scan-account.json",
      "summary": "Current scan account is active, with no verified shard outputs yet."
    },
    {
      "kind": "command",
      "reference": "runtime/bin/redcap task-facts summary",
      "summary": "Current task fact summary reports full-360-old-redcap-scan as in_progress."
    },
    {
      "kind": "source",
      "reference": "runtime/core/final_claim_guard.py",
      "summary": "Existing completion-claim guard is generic and does not distinguish scan start from scan conclusion."
    },
    {
      "kind": "source",
      "reference": "runtime/host-adapters/codex/codex-hook.py",
      "summary": "Stop hook already runs final-claim and human-output checks; the new scan-conclusion guard should join this path."
    }
  ],
  "review_mode": "design_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "Do not bulk-read the old RedCap repository.",
    "Do not claim the 360-degree scan is complete.",
    "Do not treat shard accounts, reviews, lifecycle packets, or receipts as scan conclusions.",
    "Keep provider policy locked to Kimi and Claude Code only.",
    "Cap must evaluate provider feedback and resolve disagreements instead of blindly accepting or vetoing it."
  ]
}

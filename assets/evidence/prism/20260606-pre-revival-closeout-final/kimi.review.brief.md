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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260606-pre-revival-zero-tail-infra-batch/pre-revival-zero-tail-prism-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Review the pre-revival infrastructure closeout plan before implementation continues.",
  "review_mode": "implementation_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 5,
  "known_constraint_count": 5
}

--- REVIEW REQUEST JSON ---

{
  "task": "Review the pre-revival infrastructure closeout plan before implementation continues.",
  "user_intent": "Norven wants every known unfinished pre-revival infrastructure task resolved before RedCap enters the 360-degree old RedCap scan and full revival work.",
  "main_claim": "Cap should finish the remaining pre-revival infrastructure items as a high-risk batch: Prism timeout governance, Chinese-first human-facing output policy, and the parent zero-tail batch. The planned 360-degree scan is the next phase, not something to hide inside pre-work closure.",
  "current_state": {
    "redcap_task_facts_open_count": 4,
    "open_pre_revival_infra_items": [
      "prism-timeout-governance",
      "human-facing-chinese-policy",
      "pre-revival-zero-tail-infra-batch"
    ],
    "next_phase_item_not_prework": "full-360-old-redcap-scan",
    "prism_ledger_health": "one active concern remains for 20260606-pre-revival-zero-tail-infra-batch",
    "redcap_check": "exit 0 in the latest current-state run",
    "prism_check": "exit 0 in the latest current-state run"
  },
  "changed_reality": [
    "The task fact ledger now exists and distinguishes verified, in_progress, planned, superseded, blocked, and escalated states.",
    "PreToolUse and Stop Hook false-positive handling has executable evidence, including legal Stop block markers, live-marker allowance when adapter code changes after a marker, and Goal continuation prompt freshness by session plus age instead of exact tool turn.",
    "Host hook deployment hygiene has a tracked Codex hook template and audit check.",
    "Prism communication guard has verified raw metadata paths and blocks broad raw-provider-output reads.",
    "The dispatcher still lacks whole-task timeout budgeting across provider calls, post-timeout decision policy, and a concise Chinese timeout report.",
    "The Chinese-first human-facing policy is still a requirement without a contract/checker covering docs, reports, hook messages, comments, and commit-message guidance."
  ],
  "requested_review": [
    "Challenge whether the remaining pre-revival list is complete enough to enter implementation.",
    "Challenge the proposed distinction between pre-revival infrastructure and the next 360-degree scan phase.",
    "Identify implementation traps for whole-task timeout budgeting, timeout fallback decisions, and Chinese-readable reports.",
    "Identify how to make the Chinese-first policy checkable without turning it into brittle keyword theater.",
    "Do not approve closure unless the runtime checks can verify changed system behavior, not only records."
  ],
  "evidence": [
    {
      "kind": "command",
      "reference": "runtime/bin/redcap task-facts summary",
      "summary": "Shows open_count 4, with three pre-revival infrastructure items and one next-phase 360 scan item."
    },
    {
      "kind": "command",
      "reference": "runtime/prism/bin/prism-ledger health-check",
      "summary": "Shows the parent zero-tail Prism task still active with strictest verdict concern."
    },
    {
      "kind": "command",
      "reference": "runtime/bin/redcap check",
      "summary": "Latest run exits 0 after live-marker verifier fixes."
    },
    {
      "kind": "command",
      "reference": "runtime/prism/bin/prism check",
      "summary": "Latest run exits 0 after live-marker verifier fixes."
    },
    {
      "kind": "source",
      "reference": "assets/evidence/lifecycle/pre-revival-zero-tail-lifecycle.json",
      "summary": "Lifecycle packet freezes the high-risk batch scope."
    }
  ],
  "review_mode": "implementation_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "Do not bulk-read the old RedCap repository; use archaeology shards and exact paths only.",
    "Do not treat documents, ledgers, lifecycle packets, task facts, or Prism reviews as the task body.",
    "Do not narrow the batch to a single easy fix unless Prism or Norven explicitly identifies a blocker.",
    "Keep all human-facing output Chinese-first, readable, and free of machine-style workflow jargon unless a term is immediately explained.",
    "Cap must evaluate Prism feedback and resolve disagreements; Prism is not a one-vote approval authority."
  ]
}

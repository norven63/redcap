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
  "task": "Follow-up review after implementing pre-revival infrastructure closeout fixes.",
  "review_mode": "implementation_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 9,
  "known_constraint_count": 5
}

--- REVIEW REQUEST JSON ---

{
  "task": "Follow-up review after implementing pre-revival infrastructure closeout fixes.",
  "user_intent": "Norven wants every known unfinished pre-revival infrastructure task resolved before RedCap enters the 360-degree old RedCap scan and full revival work.",
  "main_claim": "Cap implemented behavior-level fixes for the two remaining pre-revival infrastructure items, and now needs Prism to challenge whether the parent zero-tail batch can be resolved or still has blocking risk.",
  "current_state": {
    "redcap_task_facts_open_count": 2,
    "open_pre_revival_infra_items": [
      "pre-revival-zero-tail-infra-batch"
    ],
    "next_phase_item_not_prework": "full-360-old-redcap-scan",
    "prism_ledger_health": "the parent zero-tail batch still needs explicit Prism resolution",
    "redcap_check": "exit 0 after adding timeout governance and human-output policy checks",
    "prism_check": "exit 0 after adding timeout governance and human-output policy checks"
  },
  "changed_reality": [
    "The task fact ledger now exists and distinguishes verified, in_progress, planned, superseded, blocked, and escalated states.",
    "PreToolUse and Stop Hook false-positive handling has executable evidence, including legal Stop block markers, live-marker allowance when adapter code changes after a marker, and Goal continuation prompt freshness by session plus age instead of exact tool turn.",
    "Host hook deployment hygiene has a tracked Codex hook template and audit check.",
    "Prism communication guard has verified raw metadata paths and blocks broad raw-provider-output reads.",
    "The dispatcher now has --task-total-timeout-seconds, computes remaining task budget from session task_started_at before falling back to created_at for older manifests, prevents provider launch when the task budget is exhausted, persists task budget fields in raw metadata, and emits a bounded Chinese timeout report.",
    "The dispatcher self-check now exercises provider-attempt timeout, dispatcher-total timeout, task-total timeout before provider launch, process-group cleanup, raw metadata verification, and Chinese timeout report generation.",
    "The Chinese-first human-facing policy now has a contract and checker covering assistant replies, documents, hook messages, generated reports, code comments, and commit-message guidance.",
    "The human-output checker is wired into runtime/bin/redcap check, enforcement matrix, and hook coverage; its self-check proves Chinese-readable text passes while machine-like English and unexplained technical terms fail.",
    "PreToolUse prompt freshness no longer requires exact tool turn_id match; Goal continuation can mutate when the latest prompt marker is in the same session and recent.",
    "Prism session manifests now write task_started_at, and prism-dispatch uses task_started_at before falling back to created_at for older manifests.",
    "Timeout governance has an explicit contract defining provider-attempt, dispatcher-total, and task-total budgets; per-provider allocation is a shared pool, and timeout follow-up decisions are documented for provider-attempt, dispatcher-total, task-total, and remote-state cases.",
    "A separate runtime/prism/bin/prism-dispatch-timeout-e2e script now tests task-total budget exhaustion outside prism-dispatch --self-check, verifies raw metadata plus Chinese timeout reporting, and checks SIGTERM cleanup for a stubborn child process.",
    "The human-output policy contract now requires at least 15 samples and at least 5 mixed-language samples; the current sample set includes mixed Chinese/English pass and fail cases."
  ],
  "requested_review": [
    "Challenge whether the behavior-level fixes address the prior Kimi concern and Claude Code block.",
    "Challenge the proposed distinction between pre-revival infrastructure and the next 360-degree scan phase.",
    "Identify any remaining required-now gaps before entering the 360-degree scan phase.",
    "Assess whether the parent batch can close with the explicit caveat that parent completion means all known child infrastructure items have behavior-level verification, while any real 360-scan failure can reopen the batch immediately.",
    "Do not approve closure unless the runtime checks now verify changed system behavior, not only records."
  ],
  "evidence": [
    {
      "kind": "command",
      "reference": "runtime/bin/redcap task-facts summary",
      "summary": "Shows open_count 2 after timeout governance and Chinese policy task facts were updated from behavior-level evidence."
    },
    {
      "kind": "command",
      "reference": "runtime/prism/bin/prism-ledger health-check",
      "summary": "The parent batch still needs explicit Prism resolution."
    },
    {
      "kind": "command",
      "reference": "runtime/bin/redcap check",
      "summary": "Latest run exits 0 after adding human-output checks to the full chain."
    },
    {
      "kind": "command",
      "reference": "runtime/prism/bin/prism check",
      "summary": "Latest run exits 0 after adding the human-facing output policy matrix entry."
    },
    {
      "kind": "command",
      "reference": "runtime/prism/bin/prism-dispatch --self-check",
      "summary": "Covers provider-attempt, dispatcher-total, and task-total timeout behavior plus Chinese timeout report output."
    },
    {
      "kind": "command",
      "reference": "runtime/prism/bin/prism-dispatch --timeout-policy-check",
      "summary": "Validates the timeout governance contract, including task_started_at, shared budget pool, and post-timeout decisions."
    },
    {
      "kind": "command",
      "reference": "python3 runtime/prism/bin/prism-dispatch-timeout-e2e",
      "summary": "Independent integration test confirms task-total exhaustion refuses provider launch, emits verified metadata plus Chinese report, and cleans up a child process after dispatcher termination."
    },
    {
      "kind": "command",
      "reference": "runtime/bin/redcap human-output check && runtime/bin/redcap human-output self-check",
      "summary": "Covers the Chinese-first output contract, 15+ samples, mixed-language samples, machine-like English, and unexplained terms."
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

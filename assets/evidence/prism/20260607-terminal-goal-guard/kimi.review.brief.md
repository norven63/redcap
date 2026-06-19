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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260607-terminal-goal-guard/terminal-goal-guard-prism-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Review the terminal-goal guard design before implementation.",
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
  "task": "Review the terminal-goal guard design before implementation.",
  "user_intent": "Norven requires Cap to execute the fix completely and prevent phase work from replacing the terminal task.",
  "main_claim": "RedCap needs a general terminal-goal guard so phase achievements cannot close or imply completion of a larger user goal.",
  "current_state": {
    "observed_failure": "Formal usability and revival queue checks were treated as if they closed the full RedCap revival goal.",
    "task_fact_open_count": "The current task fact summary reports open_count=0 even though full RedCap revival is not truly complete.",
    "local_case": "The RedCap revival task exposed the bug, but the fix must cover any long-running terminal objective."
  },
  "changed_reality": [
    "A lifecycle packet now scopes the fix as a general terminal-goal substitution guard.",
    "The planned implementation will add a contract and runtime checker instead of only rewriting the status wording.",
    "The planned implementation will reopen or keep open a full-revival parent fact until full-revival evidence exists."
  ],
  "planned_change": [
    "Add a terminal-goal contract that defines completion levels and forbidden substitutions.",
    "Add a runtime command that validates terminal-goal facts and checks final replies for overclaims.",
    "Reopen the full RedCap revival parent task as in_progress while only baseline usability evidence exists.",
    "Update status and formal usability surfaces so they say baseline usability, not full revival.",
    "Wire the terminal-goal guard into runtime/bin/redcap check and the Codex Stop hook path.",
    "Add self-check fixtures for blocked overclaim, allowed phase report, and verified-terminal fixture."
  ],
  "requested_review": [
    "Challenge whether this solves the general class of phase-output substitution, not only the RedCap revival wording.",
    "Challenge whether the proposed completion levels are sufficient and not over-fitted.",
    "Identify any missing enforcement path that would still let Cap close a parent goal with phase evidence.",
    "Confirm whether implementation can proceed without bulk-reading the old RedCap repository."
  ],
  "evidence": [
    {
      "kind": "command",
      "reference": "runtime/bin/redcap task-facts summary",
      "summary": "Current summary reports open_count=0, which is incompatible with the full revival goal still being incomplete."
    },
    {
      "kind": "source",
      "reference": "runtime/core/formal_usable_check.py",
      "summary": "Current formal usability check validates command surfaces and queue health, not full revival migration completion."
    },
    {
      "kind": "source",
      "reference": "runtime/core/status_surface.py",
      "summary": "Current status surface can say the state is healthy without preserving the full revival parent goal."
    },
    {
      "kind": "source",
      "reference": "runtime/host-adapters/codex/codex-hook.py",
      "summary": "Stop hook already runs final reply checks and should run the terminal-goal guard there."
    }
  ],
  "review_mode": "design_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "Do not claim full RedCap revival is complete.",
    "Do not treat status reports, lifecycle packets, scan merges, queue checks, or version records as terminal completion by themselves.",
    "Do not bulk-read the old RedCap repository.",
    "Cap must evaluate reviewer feedback and resolve disagreements instead of blindly accepting or vetoing it."
  ]
}

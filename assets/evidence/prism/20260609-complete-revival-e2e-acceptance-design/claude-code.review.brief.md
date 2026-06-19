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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260609-complete-revival-e2e-acceptance-design/complete-revival-e2e-acceptance-design-prism-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Review the proposed RedCap complete-revival end-to-end acceptance design before the design contract is finalized.",
  "review_mode": "architecture_and_completion_review",
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
  "task": "Review the proposed RedCap complete-revival end-to-end acceptance design before the design contract is finalized.",
  "user_intent": "Norven asked Cap to complete the design for a full RedCap end-to-end acceptance test, and asked whether an external sandbox run is merely Cap testing itself or requires Norven to execute or assist.",
  "main_claim": "A valid complete-revival acceptance design must create an external sandbox project and verify the whole RedCap workflow machine through objective evidence, not through Cap self-belief or a report-only proof chain.",
  "changed_reality": [
    "Current complete-revival terminal acceptance is still open and must not be closed by minimum-kernel checks.",
    "Current RedCap has a 1.0 e2e trace, but that trace only covers hook, ownership, FSM, and completion guards; it does not prove a full external project development workflow.",
    "The new design should specify a future acceptance harness that creates an external project workspace outside the RedCap root and drives a realistic engineering task through Loom phases.",
    "The design should state that Norven is not needed for mechanical local execution, but remains the authority for human-gated terminal acceptance or unresolved strategy decisions."
  ],
  "evidence": [
    {
      "kind": "contract",
      "reference": "assets/contracts/loom-workflow.json",
      "summary": "Defines product manager, architect, developer, tester, reviewer, change intake, closeout, and blocked phases."
    },
    {
      "kind": "contract",
      "reference": "assets/contracts/full-revival-amendment.json",
      "summary": "Forbids minimum-kernel completion and requires complete workflow-machine posture."
    },
    {
      "kind": "scan-merge",
      "reference": "assets/archaeology/shards/old-redcap-360-scan-merge.json",
      "summary": "Lists 15 portable old RedCap designs and risk/no-promote items that the acceptance design must cover."
    },
    {
      "kind": "runtime",
      "reference": "runtime/core/e2e_trace.py",
      "summary": "Existing RedCap 1.0 trace proves lower-level hook, session, FSM, and completion semantics but is not enough for full workflow acceptance."
    },
    {
      "kind": "contract",
      "reference": "assets/evidence/lifecycle/complete-revival-e2e-acceptance-design-lifecycle.json",
      "summary": "Lifecycle packet for this design task."
    }
  ],
  "review_mode": "architecture_and_completion_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "Do not claim RedCap complete revival is terminally complete.",
    "Do not make the design depend on Norven running mechanical local tests.",
    "Do not let Cap self-testing become the only evidence of completion.",
    "Do not bulk-read the old RedCap repository.",
    "Keep human-facing wording Chinese-first when the final design is written."
  ],
  "proposed_design_summary": {
    "acceptance_harness": "A future command should create a temporary external project workspace outside the RedCap root, drive a small but real engineering task from idea intake to closeout, and collect structured evidence.",
    "workflow_coverage": [
      "idea_intake",
      "architecture_design",
      "implementation",
      "quality_assurance",
      "review_and_acceptance",
      "change_intake",
      "closeout",
      "blocked"
    ],
    "objective_evidence": [
      "filesystem diff in the external sandbox",
      "test command results",
      "lifecycle packet",
      "FSM transitions",
      "Prism review and Cap resolution",
      "terminal-goal guard result",
      "negative probes that must fail"
    ],
    "human_role": "Norven is not required to execute the local harness, but remains required for release, policy overrides, irreversible external actions, and final terminal acceptance if evidence leaves a strategic ambiguity."
  }
}

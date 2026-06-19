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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260609-redcap-design-philosophy-html/redcap-design-philosophy-html-prism-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Review the proposed RedCap design philosophy visualization before implementation.",
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
  "task": "Review the proposed RedCap design philosophy visualization before implementation.",
  "user_intent": "Norven asked Cap to create a high-quality visual HTML page that explains the newly revived RedCap design philosophy.",
  "main_claim": "A single human-facing HTML page can safely summarize current RedCap design philosophy if it clearly separates philosophy, current migration-usable state, executable guards, Loom workflow, and unfinished complete-revival status.",
  "changed_reality": [
    "No visualization page exists yet for the current revived RedCap design philosophy.",
    "Current contracts state that minimum kernel completion is not allowed.",
    "Current Loom workflow contract defines the role-based engineering workflow that must appear in the visualization.",
    "The page will be a human-facing asset under assets/docs, not runtime authority."
  ],
  "evidence": [
    {
      "kind": "document",
      "reference": "assets/docs/redcap-revival-doctrine.md",
      "summary": "Compact doctrine for current RedCap design philosophy."
    },
    {
      "kind": "document",
      "reference": "assets/docs/redcap-revival-map.md",
      "summary": "Detailed map of old RedCap ideas to keep, redesign, or discard."
    },
    {
      "kind": "contract",
      "reference": "assets/contracts/full-revival-amendment.json",
      "summary": "Machine-readable rule that complete revival requires a complete workflow machine, not a minimum kernel."
    },
    {
      "kind": "contract",
      "reference": "assets/contracts/loom-workflow.json",
      "summary": "Role workflow contract for product manager, architect, developer, tester, reviewer, and Cap orchestrator."
    },
    {
      "kind": "contract",
      "reference": "assets/contracts/terminal-goals.json",
      "summary": "Current terminal goal state: RedCap complete revival is still open."
    }
  ],
  "review_mode": "architecture_and_completion_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "Do not let the page imply RedCap complete revival is done.",
    "Do not turn a human-facing diagram into completion evidence for runtime capability.",
    "Do not bulk-read the old RedCap repository.",
    "Keep the page local and self-contained.",
    "The page should be Chinese-first and explain necessary technical terms."
  ]
}

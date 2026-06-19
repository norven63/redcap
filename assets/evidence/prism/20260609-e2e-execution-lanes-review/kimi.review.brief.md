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

/Users/norven/workspace/AI Era/redcap/assets/contracts/e2e-execution-lanes-prism-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Review the execution lanes for the RedCap complete-revival end-to-end acceptance test.",
  "review_mode": "design_review",
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
  "task": "Review the execution lanes for the RedCap complete-revival end-to-end acceptance test.",
  "user_intent": "Norven proposed two possible execution directions for the complete-revival E2E acceptance: one where an external AI develops the sandbox project and RedCap evaluates it, and one where Codex/Cap executes the test while Prism supervises and evaluates the evidence. Norven also asked whether Codex CLI can reuse the current Codex hook path.",
  "main_claim": "The acceptance design should use a hybrid execution model: the current Codex host lane is the primary terminal candidate because it exercises the actual RedCap host hooks and workflow machine; the external AI lane is useful as an adversarial control lane but cannot by itself close terminal acceptance; Codex CLI may become an executor lane only after a dedicated hook-parity probe proves that project hooks fire in that environment.",
  "changed_reality": [
    "The previous E2E acceptance design already says Cap may execute local mechanical tests but may not grade terminal acceptance by narration alone.",
    "The current project-local Codex hooks are present for SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, and Stop, but this evidence applies to the current Codex host and does not prove cross-host hook parity.",
    "Codex CLI is installed and supports non-interactive execution, working-directory selection, JSONL event output, and writing the last message to a file.",
    "Claude Code and Kimi can be launched through Prism-style delegation, but their ordinary execution is not currently proven to trigger the Codex project hooks.",
    "RedCap complete revival remains terminally open; no execution-lane decision may claim complete revival is finished."
  ],
  "evidence": [
    {
      "kind": "contract",
      "reference": "assets/contracts/complete-revival-e2e-acceptance-design.json",
      "summary": "Current E2E acceptance design, including the anti-self-grading rule and independent bootstrapper requirement."
    },
    {
      "kind": "document",
      "reference": "assets/docs/complete-revival-e2e-acceptance-design.md",
      "summary": "Human-readable E2E acceptance design."
    },
    {
      "kind": "contract",
      "reference": ".codex/hooks.json",
      "summary": "Current project-local Codex hook configuration."
    },
    {
      "kind": "log",
      "reference": "runtime/bin/redcap host-hook-audit",
      "summary": "Host hook audit passes for the current Codex host and records unsupported cross-host events."
    },
    {
      "kind": "log",
      "reference": "codex exec --help",
      "summary": "Codex CLI supports non-interactive execution but help output alone does not prove project hook parity."
    }
  ],
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "Do not claim RedCap complete revival is terminally complete.",
    "Do not let an external AI lane bypass the RedCap hook, lifecycle, FSM, and terminal-goal guards.",
    "Do not promote Codex CLI to a main executor until a hook-parity probe proves the same project hooks fire.",
    "Do not treat Prism approval as terminal acceptance; Prism challenges evidence and Cap must still resolve concerns.",
    "Keep human-facing outputs Chinese-first when the reviewed decision is reported to Norven."
  ]
}

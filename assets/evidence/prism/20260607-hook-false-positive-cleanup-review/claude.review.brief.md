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

/private/tmp/20260607-hook-false-positive-cleanup-review.request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Review the RedCap hook false-positive cleanup patch.",
  "review_mode": "implementation_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 5,
  "known_constraint_count": 0
}

--- REVIEW REQUEST JSON ---

{
  "task": "Review the RedCap hook false-positive cleanup patch.",
  "user_intent": "Norven authorized bypassing hook false positives only to repair hook misfires while preserving anti-idle enforcement and restoring Prism visibility.",
  "main_claim": "Cap changed Stop Hook mode handling, prompt intent classification for explicit authorization/status questions, Prism raw-read guard segmentation, and human-facing output term enforcement so normal work is not blocked while anti-idle guards remain active.",
  "changed_reality": [
    "Stop hook mode file can override enforcement and hooks.json no longer hard-codes REDCAP_STOP_HOOK_MODE=enforce.",
    "Prompt intent now treats explicit authorization/permission as implementation authority and keeps status confirmation questions answer-only.",
    "Assistant reply human-output policy no longer blocks common project terms such as 棱镜 or Stop Hook, but still blocks unexplained English technical terms and machine-like English replies.",
    "Prism raw-read guard now splits multiline shell commands before detecting broad raw reads, so prism-dispatch --raw-out is not misclassified as a raw read.",
    "Targeted self-checks, host-hook-audit, and runtime/bin/redcap check passed after refreshing live hook markers."
  ],
  "review_mode": "implementation_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence": [
    {
      "kind": "command",
      "reference": "python3 runtime/core/intent_judge.py self-check",
      "summary": "passed"
    },
    {
      "kind": "command",
      "reference": "python3 runtime/core/human_output_policy.py self-check",
      "summary": "passed"
    },
    {
      "kind": "command",
      "reference": "python3 runtime/host-adapters/codex/codex-hook.py --self-check-intent-judge",
      "summary": "passed"
    },
    {
      "kind": "command",
      "reference": "python3 runtime/host-adapters/host-hook-audit.py",
      "summary": "passed"
    },
    {
      "kind": "command",
      "reference": "runtime/bin/redcap check",
      "summary": "passed before raw-read segmentation patch; targeted hook self-check passed after the patch"
    }
  ],
  "questions": [
    "Does this preserve anti-idle enforcement rather than disabling hooks?",
    "Is there any new false-positive or false-negative risk in the intent classifier or raw-read guard?",
    "Is the common-term relaxation for assistant replies too broad?"
  ],
  "non_goals": [
    "Do not request more documentation as a substitute for behavior-level fixes.",
    "Do not require reading raw provider output directly."
  ]
}

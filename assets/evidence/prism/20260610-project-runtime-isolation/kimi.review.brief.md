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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260610-project-runtime-isolation/project-runtime-isolation-prism-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Review the RedCap project-runtime isolation repair before implementation.",
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 7,
  "known_constraint_count": 6
}

--- REVIEW REQUEST JSON ---

{
  "task": "Review the RedCap project-runtime isolation repair before implementation.",
  "user_intent": "Norven asked Cap to confirm whether the previous Codex CLI probe pollution is cleared, then repair RedCap so runtime artifacts for managed external projects are isolated from RedCap's own code and live under the managed project, such as <project>/.redcap/. Norven also asked Cap to re-scan old RedCap runtime/workspace boundary designs and revive the relevant strong ideas completely.",
  "main_claim": "RedCap should keep its own runtime implementation in the RedCap repository, keep user-private identity under ~/.cap, and default every managed external project's RedCap runtime artifacts to <project_workspace>/.redcap/. Self-development remains the explicit exception where the project workspace is the RedCap repository and RedCap's own local evidence may remain under assets/evidence.",
  "changed_reality": [
    "The previous Codex CLI hook probe process is no longer running and the latest UserPromptSubmit marker now belongs to the current Cap session.",
    "Two untracked route-review contract files from the previous unfinished lane review remain in the worktree and should be removed as stale task-local artifacts.",
    "The current runtime boundary kernel discovers external project workspaces correctly, but its external evidence_root defaults to user-private ~/.cap/redcap-runtime/evidence/<project_hash> and explicitly rejects evidence_root inside the project workspace.",
    "Old RedCap exact sources confirm the runtime root, project workspace, task file, and user-private state separation. They also show project-local workflow state through .dev-task.md and Loom .workflow, plus older hashed runtime project state under temporary runtime roots.",
    "Norven's desired complete-revival target is stronger than the current kernel: project-specific RedCap runtime artifacts must be project-scoped under .redcap instead of leaking into the RedCap repository or a shared opaque runtime bucket."
  ],
  "evidence": [
    {
      "kind": "log",
      "reference": "ps -axo ... | rg 'codex exec|CODEX_CLI_HOOK_PARITY_PROBE'",
      "summary": "No previous Codex CLI hook-parity probe process remains running."
    },
    {
      "kind": "log",
      "reference": "assets/evidence/host-hooks/codex/latest-UserPromptSubmit.json",
      "summary": "The latest prompt marker belongs to the current Cap session and current Norven request."
    },
    {
      "kind": "contract",
      "reference": "assets/archaeology/extractions/runtime-workspace-boundary-v1.json",
      "summary": "Bounded extraction of old RedCap runtime/workspace/user boundary guarantees."
    },
    {
      "kind": "contract",
      "reference": "/Users/norven/workspace/redcap/assets/references/runtime-workspace-boundary-policy.json",
      "summary": "Exact old RedCap policy: runtime implementation root, managed project workspace, task file, and user layer must be separated."
    },
    {
      "kind": "other",
      "reference": "/Users/norven/workspace/redcap/compass/tools/redcap-runtime-state.sh",
      "summary": "Exact old RedCap runtime state helper: project root is normalized and used to derive project-scoped runtime state paths."
    },
    {
      "kind": "other",
      "reference": "/Users/norven/workspace/redcap/loom/dispatcher/state-machine.md",
      "summary": "Old Loom workflow state uses project-local workflow files such as project_dir/.workflow/state.yaml."
    },
    {
      "kind": "other",
      "reference": "runtime/core/runtime_boundary.py",
      "summary": "Current new RedCap boundary kernel to be repaired."
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
    "Do not bulk-read the old RedCap repository; use exact source files named by archaeology maps.",
    "Do not put external project runtime artifacts into RedCap's own repository.",
    "Do not put user-private identity text or ~/.cap state inside managed project .redcap.",
    "Do not treat .redcap project runtime state as source code; it should be project-local generated state and normally ignored by the managed project.",
    "Keep self-development as an explicit exception: when RedCap develops RedCap, project_workspace may equal runtime_root."
  ]
}

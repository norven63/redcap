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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260610-redcap-design-layout-review/redcap-design-layout-review-prism-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Review the current new RedCap design thinking and directory structure.",
  "review_mode": "architecture_and_directory_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 9,
  "known_constraint_count": 6
}

--- REVIEW REQUEST JSON ---

{
  "task": "Review the current new RedCap design thinking and directory structure.",
  "user_intent": "Norven wants Cap and Prism to perform a highly detailed review of the current new RedCap workspace, especially whether the design philosophy, running unit / asset unit split, and directory layout need optimization before moving into later complete-revival work.",
  "main_claim": "The current new RedCap is intentionally split into runtime/ as the executable unit and assets/ as the durable non-executable asset unit, with .codex/ as host configuration. Recent work added known issue queues, project-level .redcap runtime isolation, and legacy evidence policy checks. The review must decide whether this design is coherent enough or whether structural adjustments are needed.",
  "changed_reality": [
    "The workspace root is intended to remain closed: README.md, AGENTS.md, .codex/, runtime/, assets/, and .gitignore.",
    "runtime/bin/redcap is the single command surface that dispatches checks and workflow helpers.",
    "runtime/core contains many small Python checkers and kernels for lifecycle, task facts, terminal goals, boundaries, knowledge, Loom workflow, and known-issue queues.",
    "runtime/prism contains the Prism review engine, provider dispatch, schemas, prompts, rules, examples, and provider-agent instructions.",
    "assets/contracts now contains many JSON contracts, including directory policy, terminal goals, known issue queues, legacy evidence policy, E2E acceptance design, and lifecycle packets.",
    "assets/docs contains human-facing doctrine and architecture notes.",
    "assets/archaeology contains bounded old-RedCap extraction results and no-promote records.",
    "assets/evidence is generated evidence and ignored from ordinary git status, while external managed projects are expected to use <project>/.redcap for runtime artifacts.",
    "The known issue queue currently marks items 1-4 verified and items 5-6 deferred for Norven-supervised execution.",
    "The RedCap complete-revival terminal parent remains open with terminal_verified=false."
  ],
  "evidence": [
    {
      "kind": "command",
      "reference": "find . -maxdepth 3 -type d ...",
      "summary": "Shows current top-level and second-level directory layout: .codex, assets, runtime, and their major subdirectories."
    },
    {
      "kind": "command",
      "reference": "find . -maxdepth 2 -type f ...",
      "summary": "Shows root-adjacent files, including .DS_Store, .codex/hooks.json, .gitignore, AGENTS.md, README.md, assets/README.md, and runtime/README.md."
    },
    {
      "kind": "file",
      "reference": "README.md",
      "summary": "Defines runtime/ as executable unit, assets/ as non-executable asset unit, .codex/ as host-entry config, and root as an index rather than a dumping ground."
    },
    {
      "kind": "file",
      "reference": "assets/contracts/directory-structure.json",
      "summary": "Machine-readable directory policy for root entries, direct children, required paths, functional directories, and placement rules."
    },
    {
      "kind": "command",
      "reference": "runtime/bin/redcap layout-check",
      "summary": "Current layout check passes."
    },
    {
      "kind": "command",
      "reference": "runtime/bin/redcap known-issues-queue check --require-1-4-verified",
      "summary": "Known issue queue check passes; items 1-4 are verified and items 5-6 are deferred_user_supervised."
    },
    {
      "kind": "command",
      "reference": "runtime/bin/redcap boundary-consumers check",
      "summary": "External project probe passes; task-facts and status use project-level .redcap runtime evidence paths."
    },
    {
      "kind": "command",
      "reference": "runtime/bin/redcap terminal-goal check",
      "summary": "Terminal parent remains open; terminal_verified=false."
    },
    {
      "kind": "command",
      "reference": "git status --short --branch",
      "summary": "Worktree has several tracked modifications and untracked review/queue/runtime files; branch develop is ahead of origin/develop by 3 commits."
    }
  ],
  "review_mode": "architecture_and_directory_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "Do not claim RedCap complete revival is terminally complete.",
    "Do not bulk-read the old RedCap repository.",
    "Review current new RedCap and evaluate whether optimization or adjustment is needed.",
    "Prioritize real structural risks over documentation polish.",
    "Call out whether an issue should be fixed before E2E acceptance or can wait.",
    "Treat passing checks as evidence only for the scope they actually cover."
  ],
  "questions_for_reviewers": [
    "Is the runtime/ plus assets/ plus .codex/ root model still coherent, or is it becoming too contract-heavy?",
    "Are contracts, lifecycle packets, evidence, docs, and runtime-owned Prism assets placed in the right units?",
    "Does the current directory policy catch real root sprawl and boundary drift, or are there blind spots?",
    "Are task facts, known issue queue, terminal goal, and lifecycle packets overlapping in a way that may cause duplicate truth surfaces?",
    "Are there any structural changes that should happen before the end-to-end acceptance harness is started?",
    "Which findings are blocking, high priority, medium priority, or acceptable tradeoffs?"
  ]
}

# RedCap

RedCap is being rebuilt from a clean workspace.

This repository is not a continuation of the old RedCap runtime. It is a new
home for the parts worth saving: reliable AI engineering collaboration,
heterogeneous review, task continuity, and reality-based completion.

The first revived component is Prism.

## Prism First

Prism is the heterogeneous AI opposition layer for the main executing AI.
Its job is not to produce ceremony, reports, receipts, or extra governance.
Its job is to prevent the main AI from replacing real completion with a
self-consistent story.

Prism exists to ask:

- Did the user's real-world target actually change?
- Is the main AI hiding behind documents, ledgers, receipts, or plans?
- What is the strongest objection from a different model family?
- What is the smallest correction before the work can honestly continue?

## Provider Policy

Prism only uses two providers:

- Kimi
- Claude Code

All other providers are intentionally excluded from the new Prism design. They
are not fallback candidates, not degraded quorum members, and not part of the
revival surface.

## Current Structure

```text
docs/
  prism-philosophy.md
  prism-capabilities.md
  prism-protocol.md
  prism-review-modes.md
  prism-provider-policy.md
  prism-anti-patterns.md
  prism-integration-with-redcap.md
schemas/
  prism-request.schema.json
  prism-review.schema.json
  prism-session.schema.json
bin/
  prism
  prism-dispatch
  completion-semantics-check
  enforcement-check
  hook-coverage-check
prompts/
  prism-shared-brief.md
  kimi-prism-review.md
  claude-code-prism-review.md
examples/
  prism-request.example.json
  prism-session.example.json
  completion-block.example.json
  design-concern.example.json
```

## Task Sessions

Full Prism tasks use file-backed task sessions under
`assets/evidence/prism/<task-id>/`. The session manifest records the Kimi resume
id and the Claude Code session id so follow-up rounds for one delegated Prism
task stay in the same provider conversations.

Use `runtime/prism/bin/prism-dispatch` for provider calls. The dispatcher runs
`session-check --require-existing-session` before follow-up rounds, generates
the provider brief, preserves provider session handles, extracts review JSON,
and updates the task session manifest. Provider calls default to a 300-second
timeout and retry timeout exits up to 5 times before recording a provider-timeout
failure with all attempt metadata.

`prism-dispatch --self-check` uses synthetic subprocess fixtures to keep the
test fast: it validates the 300-second and 5-retry defaults, five timeout retry
attempts followed by success, retry command rebuilding with a captured provider
handle, exhausted-timeout raw evidence writing, and markdown review extraction.
It does not intentionally hang a real Kimi or Claude Code network call.

`runtime/prism/bin/prism session-check` remains the lower-level guard. It exits
non-zero when the task or provider has reached a terminal state, a follow-up is
missing its saved provider session handle, or the provider has reached the
configured round cap.

`runtime/prism/bin/prism brief` prints only a compact request summary by default.
Use `--inline-request` only for bounded manual calls where the provider cannot
read the request file.

## Enforcement Matrix

`runtime/prism/bin/enforcement-check` validates
`assets/contracts/enforcement-matrix.json` and runs command probes for every
currently claimed enforcement point. It is part of `runtime/bin/redcap check`.

`runtime/prism/bin/hook-coverage-check` validates
`assets/contracts/hook-coverage.json` so required guardrails cannot be claimed
without deployed hook coverage or an explicit unsupported-event audit.

## Non-Goals

- Do not run or import the old RedCap closeout chain.
- Do not copy old `prism/runs` evidence.
- Do not migrate historical report piles.
- Do not create background follow-up tasks outside a Prism task session.
- Do not let Prism become an approval stamp.
- Do not add providers beyond Kimi and Claude Code.

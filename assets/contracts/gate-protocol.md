# Prism Gate Protocol

The Prism gate is the first deterministic rule review for RedCap tasks.

It does not always call Kimi or Claude Code. It always evaluates the task
against machine-readable rules and returns one of three decisions:

- `required`: run full Prism before implementation or official completion.
- `optional`: continue if risk is understood; escalate to Prism if uncertainty
  rises.
- `skipped`: provider review is not needed after this rule review.

## Invocation

```bash
runtime/bin/redcap gate --task "Design the runtime directory structure" --risk-level high
runtime/prism/bin/prism gate --request runtime/prism/examples/gate-required-architecture.json
```

`runtime/bin/redcap intake` runs the same gate with `--fail-when-required`; it exits
with code 2 when full Prism is required so a caller can halt before work starts.

## Enforcement Boundary

The gate is RedCap-owned intake infrastructure: it is executable,
deterministic, and discoverable outside conversation memory.

Codex project-local `UserPromptSubmit` runs the gate and records a live marker.
`PreToolUse`, `PostToolUse`, and `Stop` provide the current tool-action and
closeout guardrails. Provider-call interception is handled by
`runtime/prism/bin/prism-dispatch`, which enforces Prism task-session checks
before Kimi or Claude Code follow-up rounds.

Events not exposed as verified project hooks in this workspace are tracked by
`runtime/bin/redcap host-hook-audit`; they are not treated as implemented.

## Rule Source

- Rules: `runtime/prism/rules/prism-gate-rules.json`
- Request schema: `assets/contracts/prism-gate-request.schema.json`
- Response schema: `assets/contracts/prism-gate-response.schema.json`
- Checker: `runtime/prism/bin/prism check`

# Prism Protocol

## Review Inputs

A Prism request must provide:

- `task`: what the main AI is trying to do.
- `user_intent`: the user's real-world goal or pain.
- `main_claim`: what the main AI currently believes.
- `changed_reality`: what actually changed in files, behavior, or user-facing
  state.
- `evidence`: relevant tests, diffs, references, or screenshots.
- `risk_level`: low, medium, high, or critical.
- `review_mode`: one of the review modes in `prism-review-modes.md`.

If `user_intent` or `changed_reality` is missing, Prism should treat completion
claims as suspect.

## Provider Flow

1. Create a task run directory under `assets/evidence/prism/<task-id>/`.
2. Create `session.json` with `runtime/prism/bin/prism session-init`.
3. Send the shared brief to Claude Code through `prism-dispatch`.
4. Claude Code challenges intent alignment, implementation, correctness, tests,
   and operational risk.
5. Record the task-scoped Claude Code session handle in `session.json`.
6. Cap accepts, rejects, or escalates the review using a machine-checkable
   resolution trace; Claude Code is opposition, not authority.
7. A prior `concern` or `block` remains open until that trace and its referenced
   implementation evidence pass.

Formal Prism requests, reviews, merges, and session manifests are file-based.
stdout is only a bounded command/status channel unless `--inline-request` is
used explicitly for a manual provider call.

## Verdicts

| Verdict | Meaning |
|---|---|
| `pass` | No blocking issue found. The main AI may proceed, but still owns the work. |
| `concern` | A material risk exists. The main AI must respond before claiming completion. |
| `block` | The current claim or action is unsafe, false, or incomplete. The main AI must stop or fix. |

## Required Review Output

Each provider returns:

- `verdict`
- `confidence`
- `reality_delta`
- `main_concern`
- `top_risks`
- `missing_evidence`
- `minimum_fix`
- `anti_loop_signal`
- `user_intent_alignment`

The response must be short. Prism is not allowed to bury judgment inside a long
essay.

## Main AI Response Rule

After Prism returns `concern` or `block`, the main AI must produce a response
with:

- `accepted`: concerns it accepts.
- `rejected`: concerns it rejects, with evidence.
- `changed_plan`: what changes now.
- `completion_claim`: the narrowed or corrected claim.

The main AI may not say "noted" and proceed unchanged.

The main AI also may not blindly obey Prism. If a provider concern is wrong, the
main AI must reject it with concrete evidence and a Cap resolution trace. If a
concern needs clarification, the main AI may continue in the same task-scoped
Claude Code session. That discussion is bounded to the round cap in
`assets/contracts/prism-session-protocol.md`.
Before each follow-up provider call, the main AI must run `session-check` against
the task's `session.json`; a non-zero result means it must decide or escalate
instead of calling the provider again.

## Stop Conditions

The main AI must stop and ask the user if Prism identifies:

- Irreversible deletion without a rollback path.
- Publication, registry, license, or secret handling.
- User-value tradeoffs rather than engineering facts.
- A mismatch between task card and user original intent.
- Repeated anti-loop signals after one correction attempt.
- A provider concern that remains unresolved after the configured round cap.

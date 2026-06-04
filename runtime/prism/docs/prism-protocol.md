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
3. Send the same shared brief to Kimi and Claude Code.
4. Kimi focuses on long-context, intent drift, and narrative failure.
5. Claude Code focuses on implementation, correctness, tests, and operational
   risk.
6. Record each provider's task-scoped session handle in `session.json`.
7. The main AI compares both outputs without averaging them away.
8. The stricter completion verdict wins for completion, release, deletion,
   secrets, migration, and irreversible decisions.

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
main AI must reject it with concrete evidence. If providers disagree materially,
the main AI must discuss the conflict in the same task-scoped provider sessions.
That discussion is bounded to the round cap in
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
- Provider disagreement that remains unresolved after the configured round cap.

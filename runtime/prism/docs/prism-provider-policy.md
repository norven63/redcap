# Prism Provider Policy

## Allowed Providers

Prism has exactly two allowed providers:

| Provider | Role | Primary Strength |
|---|---|---|
| Kimi | Long-context challenger | Archaeology, synthesis, intent drift, narrative gaps |
| Claude Code | Engineering challenger | Code review, implementation risk, test gaps, concrete fixes |

## Excluded Providers

All other providers are excluded by design.

Excluded providers are not:

- Fallbacks.
- Emergency quorum members.
- Degraded review sources.
- Future default candidates.
- Silent participants.

Adding a provider requires a new human-approved policy change. It must not be
introduced as an automatic fallback.

## Why Only Two

Prism failed when review became ceremony. More providers can increase ceremony
without increasing opposition.

The new rule is:

> Use the smallest pair that reliably disagrees with the main AI in useful ways.

Kimi and Claude Code are enough because their failure modes and strengths are
different:

- Kimi challenges context, intent, and hidden narrative drift.
- Claude Code challenges engineering reality, implementation details, and
  verification gaps.

## Quorum

Prism has three valid quorum shapes:

| Quorum | Meaning |
|---|---|
| `kimi-only` | Advisory review; useful for intent, archaeology, and strategy |
| `claude-code-only` | Advisory review; useful for code, tests, and implementation |
| `kimi-plus-claude-code` | Full Prism review |

No review may claim "full Prism" unless both Kimi and Claude Code participated.

## Disagreement Rule

If Kimi and Claude Code disagree, the result is not averaged.

The main AI must:

1. State the disagreement plainly.
2. Identify which claim is about user intent and which is about engineering
   reality.
3. Apply the stricter verdict when the disagreement concerns completion,
   deletion, release, secrets, or irreversible change.
4. Ask the user when both positions are plausible and the decision is
   value-laden.


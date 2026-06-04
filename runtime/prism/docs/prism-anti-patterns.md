# Prism Anti-Patterns

## Approval Stamp

Bad:

> Prism says pass, so the work is complete.

Correct:

> Prism found no blocker. The main AI still owns proof that the user's reality
> changed.

## Report Spiral

Bad:

> Prism found a concern, so create another report, then another gate, then
> another receipt.

Correct:

> Prism found a concern. Fix the smallest real issue or ask the user.

## Provider Inflation

Bad:

> Add more providers when Kimi and Claude Code disagree.

Correct:

> Preserve the disagreement. Apply the stricter verdict for high-risk actions or
> ask the user.

## Completion Laundering

Bad:

> The task is complete because a receipt says the task is complete.

Correct:

> The task is complete only if the real-world target changed. A receipt can only
> support that claim.

## Archaeology Flood

Bad:

> Read every old report, every Prism run, and every historical artifact before
> deciding.

Correct:

> Read only the smallest evidence set needed for the current risk.

## Concern Dilution

Bad:

> Kimi blocked, Claude Code passed, so average to concern and continue.

Correct:

> Disagreement is evidence. For completion, deletion, release, and secrets, the
> stricter verdict wins unless the user overrides.

## Self-Review Masquerade

Bad:

> The main AI writes a Prism-style critique of itself and calls it Prism.

Correct:

> Prism requires a heterogenous provider: Kimi, Claude Code, or both.

## Governance Substitution

Bad:

> The user wanted a behavior fixed. The system added a policy explaining why it
> is risky.

Correct:

> If the task is to fix behavior, only behavior change can complete it. Policy is
> supporting evidence.


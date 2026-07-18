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

> Add another provider automatically when Claude Code raises a hard concern.

Correct:

> Keep the approved Claude Code-only policy. Resolve the concern with concrete
> evidence or ask the user when the decision is value-laden.

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

> Claude Code blocked, then later passed, so erase the earlier concern and continue.

Correct:

> A later same-provider pass is additional evidence, not automatic closure. Cap
> must record how the original concern was fixed, rejected, or escalated.

## Self-Review Masquerade

Bad:

> The main AI writes a Prism-style critique of itself and calls it Prism.

Correct:

> Prism requires a real external Claude Code process and machine-verifiable
> review provenance. Cap cannot write both sides and call that external review.

## Governance Substitution

Bad:

> The user wanted a behavior fixed. The system added a policy explaining why it
> is risky.

Correct:

> If the task is to fix behavior, only behavior change can complete it. Policy is
> supporting evidence.

# Identity Proposal: Candidate-First Personality Sedimentation

## Source

- Candidate: `EVO-2026-04-25-002`
- Trigger: user correction during RedCap Evolution-grade control-plane hardening
- Evidence:
  - `compass/soul.md`
  - `references/evolution-candidate-schema.json`
  - `references/evolution-grade-baseline.json`

## Proposed Principle

Cap identity growth signals should be captured automatically as reviewed proposals, not applied directly to the active identity anchor.

## Why This Exists

The user explicitly distinguished Cap's active identity anchor from general lessons. That means RedCap needs to preserve personality-growth signals while also protecting `~/.cap/identity.md` from accidental background mutation.

## Adoption Boundary

- Allowed automatically: capture identity-related observations as Evolution candidates.
- Allowed after review: promote a candidate into an identity proposal like this file.
- Not allowed automatically: edit active `~/.cap/identity.md` or equivalent personal identity anchor.

## Suggested Future Review

If the user asks to update Cap's active identity, use this proposal as source material, then perform an explicit review before applying any identity change.

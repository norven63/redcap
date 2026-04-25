# RedCap Evolution Factory

RedCap Evolution Factory is the sidecar governance layer that turns runtime traces into reusable assets without letting self-modification become another source of drift.

## Purpose

- Collect evolution candidates from task cards, task reports, Prism verdicts, receipts, tests, user corrections, and closeout failures.
- Require every candidate to explain at least: problem source, solution, and final effect.
- Promote reviewed candidates into lessons, identity proposals, skills, rules, validators, backlog items, or explicit no-promote decisions.
- Keep active rules and identity files protected: discovery can be automatic, but promotion must be reviewed and evidence-backed.

## First-Read Rule

Do not bulk-read future candidate pools. Start from:

1. `references/evolution-grade-baseline.json`
2. `references/evolution-candidate-schema.json`
3. `compass/evolution/candidates.json`
4. `compass/tools/redcap-evolution-grade-check.sh`
5. `compass/tools/redcap-evolution-candidate-check.sh --strict`

## Lifecycle

```text
runtime trace
→ evolution candidate
→ schema check
→ Prism / independent review
→ promotion or no-promote-with-reason
→ closeout receipt may proceed only when candidates are handled
```

The first implementation is intentionally sidecar-first. It audits and gates RedCap-owned flows before any broader host-level automation is claimed.

## Closeout Gate

`redcap-layerb-closeout-runtime.sh complete` runs the candidate checker in strict mode before it can write a receipt. Any candidate still in `candidate` or `reviewing` blocks closeout until it is promoted, explicitly marked `no-promote` with a reason, or archived by policy.

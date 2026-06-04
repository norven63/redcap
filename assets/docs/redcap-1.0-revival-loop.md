# RedCap Revival 1.0 Loop

> Status: active loop contract, not a completion claim.

The loop exists to keep Cap and Prism moving until RedCap revival reaches a
verified 1.0 state. It is intentionally not a new runtime subsystem and not a
new CLI. The machine-readable contract is
`assets/contracts/redcap-1.0-loop.json`, and the existing `runtime/bin/redcap
check` path validates it.

## Cycle

Each cycle selects exactly one current queue item. Cap creates a lifecycle
packet for that item, runs the RedCap gate, dispatches Prism when required,
implements or extracts only that item, verifies changed reality, resolves every
Prism concern, and advances only after verification.

Extraction is never completion by itself. A pathology shard cycle must consume
the extraction into an executable guardrail, a contract rule, a checker, or an
explicit no-promote decision in the same cycle.

## Stop Lines

- Two consecutive cycles with only documents, extraction summaries, reports,
  ledgers, or receipts stop the loop and escalate.
- An item that cannot advance after two attempts must be skipped with
  no-promote evidence or escalated.
- Ambiguous Prism concern triage after one additional cycle escalates to
  Norven.
- Human decisions remain required for identity, secrets, release, provider
  policy, irreversible migration, destructive migration, and value-laden
  choices.

## Exit

RedCap 1.0 is not old-RedCap parity and not public release. The loop exits only
when the contract's final claim item is proven by current-state evidence:
temporary usable check passes, RedCap check passes, the end-to-end trace passes,
all seven kernel verification items have probe evidence, and all blocking Prism
concerns are resolved.

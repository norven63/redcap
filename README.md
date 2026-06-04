# RedCap

This is the clean revival workspace for RedCap.

The old RedCap repository is reference material only. This workspace should
grow by bounded components, not by scattering governance assets across the root.

## Top-Level Units

- [`runtime/`](./runtime/) - executable and operational RedCap unit: CLI
  entrypoints, Prism gate/review engine, bootstrap, and host adapters.
- [`assets/`](./assets/) - persistent non-executable asset unit: contracts,
  docs, knowledge, evidence, and archaeology references.
- [`.codex/`](./.codex/) - Codex host-entry config for project-local hooks.

## Pre-Task Gate

All RedCap work starts with deterministic Prism rule review:

```bash
runtime/bin/redcap gate --task "<task summary>" --risk-level medium
```

The gate returns `required`, `optional`, or `skipped`. A `required` verdict means
full Prism must run before implementation or official completion. Codex
project-local hooks run the gate on prompt intake and record action/closeout
evidence; provider calls go through the Prism dispatcher so follow-up rounds
cannot bypass task-session checks.

## Temporary Usability Check

The current scaffold has a bounded "usable enough for revival work" check:

```bash
runtime/bin/redcap temporary-usable-check
```

It requires the executable Prism/session-ownership/FSM/knowledge/layout checks,
provider dispatcher self-check, host hook audit, hook coverage check, and
enforcement matrix probes to pass. The check currently allows no known rough
edges.

## Revival Doctrine

- [`assets/docs/redcap-revival-doctrine.md`](./assets/docs/redcap-revival-doctrine.md) -
  compact extraction of the old RedCap's intended design philosophy. It is a
  constraint for future rebuilding, not proof that any RedCap capability has
  been rebuilt.
- [`assets/docs/redcap-revival-map.md`](./assets/docs/redcap-revival-map.md) - detailed
  extraction map of what old RedCap got right, what should be redesigned
  smaller, and what must not be carried forward.
- [`assets/docs/directory-architecture.md`](./assets/docs/directory-architecture.md) -
  responsibility-based layout for execution, Prism, contracts, adapters,
  knowledge, evidence, archaeology, bootstrap, and human reading layers.

## Root Rule

The repository root is an index, not a dumping ground. The closed root set is
`README.md`, `AGENTS.md`, `.codex/`, `runtime/`, and `assets/`.
`runtime/bin/redcap layout-check` rejects new root entries and runtime/assets
boundary drift.

# RedCap

This is the clean revival workspace for RedCap.

The old RedCap repository is reference material only. This workspace should
grow by bounded components, not by scattering governance assets across the root.

Current release posture: RedCap has a project-level installation package,
runtime boundary checks, Loom workflow checks, Prism review routing, knowledge
and self-purification guards, and long-run external sample observation tooling.
It is prepared as a 1.0 production baseline for controlled project use.

Boundary: this does not claim RedCap complete revival is terminally closed.
OL-11, the long-term external project sample, must still pass the long-run
observer before the broader complete-revival parent goal can close.

## Top-Level Units

- [`runtime/`](./runtime/) - executable and operational RedCap unit: CLI
  entrypoints, Prism gate/review engine, bootstrap, and host adapters.
- [`assets/`](./assets/) - persistent non-executable asset unit: contracts,
  docs, knowledge, evidence-boundary markers, and archaeology references.
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

## Release Readiness Checks

For quick local confidence:

```bash
runtime/bin/redcap temporary-usable-check
```

For package and production baseline checks:

```bash
runtime/bin/redcap check --profile release
runtime/bin/redcap project-install production-readiness-check
runtime/bin/redcap longrun-observer self-check
```

Runtime output must go to `.redcap/evidence/` in this source workspace, or to
`<project>/.redcap/evidence/` in an installed project. `assets/evidence/` is a
source-tree boundary marker only.

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

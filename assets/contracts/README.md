# Contracts Layer

Purpose: shared machine-readable protocols, schemas, and policy contracts.

Belongs here:

- input/output schemas
- protocol documents
- cross-component contracts
- policy files consumed by executable checks

Does not belong here:

- live task state
- private identity material
- old evidence dumps
- prose-only rules with no consumer

Rule: a contract should name the component that consumes it.

Current contracts:

- `directory-structure.json`: consumed by `runtime/core/layout_guard.py`,
  `runtime/bin/redcap layout-check`, and `runtime/bin/redcap check`.
- `directory-structure.schema.json`: schema for the directory structure policy.
- `enforcement-matrix.json`: consumed by
  `runtime/prism/bin/enforcement-check` and `runtime/bin/redcap check`.
- `enforcement-matrix.schema.json`: schema for the enforcement matrix contract.
- `gate-protocol.md`: consumed by `runtime/prism/bin/prism gate`.
- `process-artifact-placement.json`: consumed by
  `runtime/core/process_artifact_placement.py`,
  `runtime/bin/redcap process-artifacts`, and `runtime/bin/redcap check`.
- `prism-session-protocol.md`: consumed by `runtime/prism/bin/prism session-init`,
  `session-update`, `brief`, and `merge`.

Process files such as lifecycle packets and Prism requests are evidence, not
stable contracts. Files matching `*-lifecycle.json` or `*-prism-request.json`
belong under `assets/evidence/`. Historical process files were migrated out of
this directory by the migration recorded in
`assets/evidence/migrations/20260611-process-artifact-migration-map.json`;
new process files under `assets/contracts/` are a hard placement violation.

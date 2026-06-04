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
- `prism-session-protocol.md`: consumed by `runtime/prism/bin/prism session-init`,
  `session-update`, `brief`, and `merge`.

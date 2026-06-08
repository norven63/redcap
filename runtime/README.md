# Runtime Layer

Purpose: executable RedCap core.

Belongs here:

- task identity and workspace boundary code
- session ownership kernel
- FSM foundation kernel and full Loom role workflow contract checks
- completion semantics validator
- index-first knowledge gateway
- temporary usability verifier
- runtime-facing CLI helpers

Does not belong here:

- old reports or receipts
- raw Prism runs
- long-form design docs
- host-specific rule copies

Rule: runtime code must be testable without importing old RedCap paths.

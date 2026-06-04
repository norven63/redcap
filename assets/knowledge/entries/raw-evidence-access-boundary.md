# Raw Evidence Access Boundary

Raw evidence is proof material, not default context. RedCap 1.0 keeps raw
Prism runs, provider raw output, and evidence archives behind explicit task
need instead of loading them into normal retrieval.

## Six Boundary Rules

- Default context: raw evidence and raw archives are not loaded by default.
- Package candidate: `prism/reports` and `prism/runs` style raw evidence
  surfaces must stay absent from package or public candidate surfaces unless a
  future public/private evidence policy explicitly changes that boundary.
- Physical cleanup: evidence is not moved, deleted, or physically cleaned
  without explicit future approval and lifecycle proof.
- Cleanup apply: cleanup or prune apply actions stay forbidden by default.
- Minimum run count: historical run-count integrity must not drop without a
  cleanup receipt or equivalent lifecycle proof.
- Release blocker: release-readiness claims stay blocked while evidence
  retention and public/private split rules are unresolved.

## 1.0 Mapping

- Enforced now: the knowledge gateway requires `raw_archive_default=forbidden`
  and validates this entry remains searchable.
- Recorded now: this entry and the raw-evidence no-promote decision preserve
  the package candidate, physical cleanup, cleanup apply, minimum run count,
  and release blocker rules.
- Not promoted now: old Prism evidence-retention runtime, old raw run
  lifecycle machinery, old package split machinery, and raw evidence cleanup
  operations.

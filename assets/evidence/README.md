# Evidence Layer

Purpose: bounded proof artifacts for high-risk decisions.

Belongs here:

- formal Prism review summaries
- Prism task session manifests
- lifecycle packets for one bounded development task
- Prism request files for one bounded review task
- verification traces
- acceptance outputs
- release or migration proof records

Does not belong here:

- raw provider transcripts by default
- local caches
- `.env` files
- completion claims without changed reality

Rule: evidence supports a claim; it is not the claim.

Placement rule: one-turn process files must be written here, not to
`assets/contracts/`. The executable guard for this rule is
`runtime/bin/redcap process-artifacts check`.

Boundary rule: when RedCap develops RedCap itself, bounded runtime evidence can
live here because this repository is the project workspace. When RedCap is
deployed into another project, runtime output belongs under that project's
`.redcap/` directory, not in this repository.

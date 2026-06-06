# Prism Shard Accounts

Prism shard accounts split long RedCap review tasks into bounded, auditable
units before provider work begins.

Runtime entrypoint:

```bash
runtime/bin/redcap prism-shard check --account path/to/account.json
runtime/bin/redcap prism-shard merge --account path/to/account.json --out path/to/merge.json
runtime/bin/redcap prism-shard self-check
```

Account rules:

- Every shard must name an exact question, scope, stop condition, acceptance
  criteria, provider set, provider-session records, and output schema.
- `candidate_sources` must be exact files. Directories and globs are rejected.
- A verified shard must point to a valid `prism-shard-output` JSON file.
- Shard output may only claim it read files listed in that shard's
  `candidate_sources`.
- `ready_for_merge` and `merged` accounts cannot contain non-terminal shards.
- Cap arbitration must define a bounded discussion round limit and require a Cap
  decision when the limit is exhausted.

This is the pre-revival long-task foundation for the later 360 old-RedCap scan.
It is not a provider scheduler by itself; provider calls still run through
`prism-dispatch` and the Prism session manifest.

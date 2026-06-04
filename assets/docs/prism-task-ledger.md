# Prism Task Ledger

The Prism task ledger is an append-only health record for Prism sessions. It
records task execution facts from real session manifests, then derives a compact
health summary for routine observation.

## Runtime

- Entrypoint: `runtime/prism/bin/prism-ledger`
- Library: `runtime/prism/lib/prism_ledger.py`
- Ledger: `assets/evidence/prism/task-ledger.jsonl`
- Health summary: `assets/evidence/prism/task-health.json`

`runtime/prism/bin/prism session-init` and `session-update` append session
records after writing the session manifest. `runtime/prism/bin/prism gate`
appends a separate gate-evaluation record after printing the normal gate JSON to
stdout, so hook parsers still see the same leading JSON object.

## Record Shape

Session JSONL events use `schema_id: prism-task-execution-record` and include:

- task id, session manifest path, run directory, trigger, executor
- created and updated timestamps plus computed duration
- session status, convergence state, convergence reason
- provider snapshots for Kimi and Claude Code
- round counts, session-handle presence, review hash, last verdict, confidence
- merge verdict, success boolean, and outcome classification

Gate JSONL events use `schema_id: prism-gate-evaluation-record` and include:

- gate event id, trigger, executor, start/end time, duration
- task fingerprint only: length and SHA-256, not the full prompt text
- optional task id, risk level, tags, changed path count
- decision, review mode, matched rules, required providers, planned exit code

The health summary uses `schema_id: prism-task-health-summary` and includes task
count, event count, success count, success rate, active count, attention count,
operational active count, operational success rate, self-check task count,
average duration, provider verdict distribution, and recent attention tasks.
Self-check sessions remain in the append-only event stream, but the operational
fields keep routine health observation from being dominated by internal probes.
Gate events are aggregated separately with gate event count, success rate,
decision counts, trigger counts, and average gate duration.

## Commands

```bash
runtime/prism/bin/prism-ledger record --manifest path/to/session.json
runtime/prism/bin/prism-ledger record-gate --request request.json --result result.json
runtime/prism/bin/prism-ledger summary
runtime/prism/bin/prism-ledger self-check
runtime/bin/redcap prism-ledger summary
```

`runtime/prism/bin/prism check` runs the isolated self-check so RedCap cannot
claim Prism is healthy while the ledger machinery is broken.

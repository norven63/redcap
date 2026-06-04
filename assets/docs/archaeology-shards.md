# Archaeology Shards

Old RedCap archaeology is bounded by exact shard questions and exact source
files. Directory-wide bulk reads are not a valid shard source.

The first extracted shard is `runtime-workspace-boundary`. It reads only the old
runtime workspace boundary policy and checker files, extracts their guarantees,
and classifies portable rules for the new runtime boundary kernel.

The shard index also carries planned pathology shards before formal revival:

- `pathology-report-as-progress`
- `pathology-receipt-as-completion`
- `pathology-closeout-recursion`
- `pathology-raw-evidence-default`

These are definitions, not completed extractions. Each one names exact old
source files, a stop condition, and acceptance criteria so future archaeology
does not become a bulk-read loop.

Commands:

```bash
runtime/bin/redcap archaeology extract-boundary
runtime/bin/redcap archaeology seed
runtime/bin/redcap archaeology check
runtime/bin/redcap archaeology self-check
```

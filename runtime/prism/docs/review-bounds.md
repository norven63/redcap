# Prism Review Bounds

Prism reviews are bounded opposition tasks, not open-ended research sessions.

Default bounds for a single Prism request:

- Evidence excerpt budget: at most 250 referenced lines or compact evidence
  bullets.
- Question budget: at most 4 review questions.
- Active provider set: Claude Code only. Historical Kimi evidence is read-only.
- Old RedCap access: exact source paths only; no directory-wide content reads.
- Completion rule: a missing or timed-out provider result is never acceptance.

When a request exceeds those bounds, split it manually before dispatch:

1. Assign a shard id such as `archaeology-closeout-recursion` or
   `preflight-lifecycle-enforcement`.
2. Give the shard one question, exact candidate sources, a stop condition, and
   acceptance checks.
3. Dispatch each shard through `runtime/prism/bin/prism-dispatch`.
4. Merge only same-shard reviews; do not average unrelated shards together.
5. The main RedCap agent must accept, reject, or implement each shard result
   before using it as revival guidance.

Do not build a separate long-task ledger until a concrete task repeatedly
breaks these manual bounds.

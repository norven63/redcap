# Full LLM-wiki

Full LLM-wiki is RedCap's private long-term memory product surface.

It is not a source of truth. It organizes stable concepts, repeated failure
patterns, decision frameworks, and terminology explanations so an Agent can
load durable context progressively instead of bulk-reading reports.

The operating rule is simple:

- Source files, receipts, task ledgers and Prism verdicts remain authoritative.
- Wiki entries are derived, source-anchored, review-gated memory aids.
- The worker may create candidates, but it must not rewrite source truth or
  publish to `redcap-arsenal` directly.
- RAG and GraphRAG are represented only by a disabled-by-default boundary until
  a separate task enables a real backend.

Start with `index.json`, then open exact entries only when the task asks for a
stable concept or a repeated engineering pattern.

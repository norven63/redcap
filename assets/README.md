# Assets Unit

Purpose: persistent non-executable RedCap assets.

Belongs here:

- contracts and schemas consumed by runtime
- first-read docs and architecture notes
- reviewed knowledge
- bounded evidence
- controlled archaeology references into old RedCap

Does not belong here:

- executable runtime code
- host hook shims
- bootstrap commands
- local secrets or caches
- raw old RedCap dumps by default

Rule: assets are durable inputs, records, or explanations. If it runs, put it
under `runtime/`.

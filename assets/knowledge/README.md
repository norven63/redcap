# Knowledge Layer

Purpose: reviewed, reusable RedCap knowledge.

Belongs here:

- concise lessons
- stable terminology
- reviewed private wiki entries
- source-anchored design concepts

Does not belong here:

- current task state
- raw reports
- private identity text
- Prism raw output
- public arsenal entries before Forge review

Rule: index first, exact body second, raw archive never by default.

Current executable gateway:

```bash
runtime/bin/redcap knowledge-gateway check
runtime/bin/redcap knowledge-gateway search session
runtime/bin/redcap knowledge-gateway draft --id stable-idea --title "Stable idea" --summary "..." --tags doctrine,workflow --body "..."
runtime/bin/redcap knowledge-gateway review --draft assets/evidence/knowledge/drafts/stable-idea.json --decision approve --reviewer redcap --reason "..."
runtime/bin/redcap knowledge-gateway promote --review assets/evidence/knowledge/reviews/stable-idea.review.json
runtime/bin/redcap knowledge-gateway self-check
```

Drafts and review records belong under `assets/evidence/knowledge/`. Only
approved reviews may promote body files into `assets/knowledge/entries/` and add
them to `index.json`.

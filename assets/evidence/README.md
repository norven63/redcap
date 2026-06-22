# Evidence Boundary

This directory is not a runtime evidence store.

It is kept only as a source-tree boundary marker:

- `README.md` explains the rule.
- `.gitignore` prevents new runtime evidence from being committed here.

Runtime evidence belongs in one of these places:

- source self-development: `.redcap/evidence/`
- installed project: `<project>/.redcap/evidence/`
- disposable validation run: an explicit temporary run directory

Do not write task packets, Prism review outputs, lifecycle markers, hook logs,
provider transcripts, E2E artifacts, or cache files under `assets/evidence/`.

Evidence can support a completion claim, but it is never the completion itself.

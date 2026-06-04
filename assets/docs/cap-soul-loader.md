# Cap Soul Loader

The Cap soul loader is the bounded RedCap module that connects this workspace to
private Cap identity sources without copying private body text into project
evidence.

## Runtime

- Entrypoint: `runtime/bin/redcap soul-load`
- Implementation: `runtime/core/soul_loader.py`
- Evidence:
  - `assets/evidence/soul/latest-load.json`
  - `assets/evidence/soul/load-ledger.jsonl`

## Source Policy

The loader currently treats `/Users/norven/.cap/identity.md` as the required
identity source. The legacy AGENTS reference `~/.codex/skills/redcap/soul.md` is
an optional source because it may be absent in this revived workspace.

Evidence records contain source status, hashes, counts, titles, and redaction
counts. They must not contain private identity body text or secret-like lines.

## Commands

```bash
runtime/bin/redcap soul-load check
runtime/bin/redcap soul-load load --json
runtime/bin/redcap soul-load self-check
```

`runtime/bin/redcap check` runs the source check and isolated self-check. The
Codex `SessionStart` hook also calls the loader so future RedCap sessions get a
real Cap load attempt rather than only a protocol reminder.

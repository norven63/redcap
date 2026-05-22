# Prism Review: LLM-wiki-lite Lifecycle Implementation

## Scope

This run reviewed the `P4-2h-3` implementation of RedCap's minimal private LLM-wiki-lite semantic memory lifecycle.

It reviewed whether the implementation stayed private, non-authoritative, source-anchored, digest-staleness-checkable, candidate-type-limited, Forge-gated, and non-RAG/non-GraphRAG.

## Roster

- Kimi / Moonshot family: challenger
- Claude Code / Claude family: reviewer

## Verdict

Pass with non-blocking notes.

Both reviewers found no blocking issues. They agreed that the implementation delivers the intended minimum lifecycle and does not cross into a complete LLM-wiki product, public writeback, RAG, GraphRAG, vector store, or background auto-generation.

## Boundary Assessment

- Entries are enforced as `visibility=private` and `authority=non-authoritative-derived-context`.
- Source anchors require `sha256:` digests and are checked against current file contents.
- Candidate allow/deny is inherited from `references/llm-wiki-asset-stratification-policy.json`.
- Denied layers and secret-like material are blocked through candidate denial, source-path denial, raw excerpt rules, and entry-body scanning.
- Public promotion requires RedCap Forge and keeps `public_write_allowed=false`.
- `spec-check`, `diagnose`, acceptance, execution guarantees, and the file lookup dictionary now consume the new gate.
- The legacy-asset checker excludes only the new `compass/knowledge/llm-wiki/` active store from historical migration counts; it does not hide old assets.

## Notes And Follow-up

- Kimi noted that the first sample entry has only one source anchor. That is acceptable for the minimum schema; future production entries should use multiple anchors when the concept depends on multiple sources.
- Kimi suggested a future taxonomy improvement for a dedicated semantic-memory guarantee category. This is non-blocking because the current registry category is still checked and visible.
- Claude Code noted that the first implementation hardcoded local leak-detection strings. RedCap addressed this after review by deriving the home path and Feishu profile dynamically instead of embedding those host-specific literals in the checker.

## Evidence

- `prism/runs/20260506-llm-wiki-lite-lifecycle-review/collect/challenger/parsed.json`
- `prism/runs/20260506-llm-wiki-lite-lifecycle-review/collect/reviewer/parsed.json`
- `references/llm-wiki-lite-policy.json`
- `references/llm-wiki-lite-entry.schema.json`
- `compass/tools/redcap-llm-wiki-lite-check.py`
- `compass/tools/redcap-multi-session-acceptance.sh`

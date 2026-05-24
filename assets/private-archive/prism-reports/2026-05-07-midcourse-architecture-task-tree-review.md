# Prism Review: Midcourse Architecture And Task Tree Review

## Scope

This run reviewed `P2-7 RedCap 中途架构与任务树一致性审计`.

The review focused on three questions:

- whether the File Lookup Dictionary checker now enforces short Chinese script purpose headers plus `Dictionary:` backlinks without turning script heads into long prose;
- whether the midcourse review artifact honestly separates completed, deferred, blocked and future work;
- whether the changes create regression risk in `spec-check`, acceptance, parent ledger or the release task tree.

## Roster

- Claude Code / Claude family: reviewer
- Kimi / Moonshot family: challenger attempt, timed out after 90 seconds

Copilot was not used. It remains protected fallback only when Claude Code and Kimi are both unavailable.

## Verdict

Resource-limited pass.

Claude Code found one first-pass review material issue: the first prompt omitted untracked new files, so it could not fully review the new midcourse checker. It also suggested tightening the `用途：` matcher so a random mention inside a comment cannot satisfy the header requirement.

After the fix, Claude Code returned no blockers. It recommended two hardening actions: avoid using runtime cache files as midcourse evidence and broaden the file-header acceptance fixture beyond `.sh`. Both were applied before this report was written.

Kimi did not return within the bounded 90-second window, so this run is intentionally recorded as resource-limited rather than full quorum.

## Accepted Result

- Critical script-like File Lookup Dictionary entries now require a short Chinese purpose marker near the file head.
- The same entries also require a `Dictionary:` backlink near the file head.
- The midcourse review artifact records seven review dimensions and three deferred/blocked boundaries.
- `LLM-wiki-lite` is kept distinct from full LLM-wiki / RAG / GraphRAG / vector store / background generator work.
- `spec-check` now executes the midcourse architecture check.
- The targeted acceptance case verifies missing script headers fail and `.sh` / `.py` / no-suffix CLI entries with proper headers are accepted.

## Evidence

- `prism/runs/20260507-midcourse-architecture-task-tree-review/collect/reviewer/raw.txt`
- `prism/runs/20260507-midcourse-architecture-task-tree-review/collect/reviewer/postfix-raw.txt`
- `prism/runs/20260507-midcourse-architecture-task-tree-review/collect/reviewer/parsed.json`
- `prism/runs/20260507-midcourse-architecture-task-tree-review/collect/challenger/postfix-stderr.txt`
- `prism/runs/20260507-midcourse-architecture-task-tree-review/artifacts/resource-limited.json`
- `references/midcourse-architecture-task-tree-review.json`
- `references/file-lookup-dictionary-policy.json`
- `compass/tools/redcap-file-lookup-dictionary-check.py`
- `compass/tools/redcap-midcourse-architecture-check.py`
- `compass/tools/redcap-multi-session-acceptance.sh`

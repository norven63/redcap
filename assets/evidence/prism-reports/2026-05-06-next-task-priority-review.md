# Prism Review: Next Task Priority After LLM-wiki Stratification

## Scope

Norven asked RedCap and Prism to continue the unfinished parent task line and let Prism help choose the next safe engineering slice.

This review compared the remaining `P4-2` family work and chose the next implementable task. It did not approve npm publication, public arsenal population, public history migration, RAG, GraphRAG, or a complete LLM-wiki product.

## Roster

- Kimi / Moonshot family: challenger
- Claude Code / Claude family: reviewer

## Verdict

Pass: proceed with `P4-2h-3 LLM-wiki-lite semantic memory lifecycle implementation`.

The accepted rationale was:

- `P4-2h-2` had already completed asset stratification and registered `P4-2h-3`.
- Public release remained blocked by release-boundary decisions and was not the next safe task.
- Public distillation remained deferred and should not start before the private semantic-memory boundary exists.
- `P4-2h-3` had clear dependencies, narrow scope, and machine-checkable acceptance gates.

## Accepted Minimum Scope

- Private LLM-wiki-lite entry schema.
- Source anchors and digest-based staleness checking.
- Candidate allowlist/denylist inherited from `references/llm-wiki-asset-stratification-policy.json`.
- Forge-gated public promotion boundary.
- `diagnose`, `spec-check`, `acceptance`, execution guarantees, file lookup dictionary, Prism review, report, and closeout integration.

## Evidence

- `prism/runs/20260506-next-task-priority-review/collect/challenger/parsed.json`
- `prism/runs/20260506-next-task-priority-review/collect/reviewer/parsed.json`
- `.dev-task.md`
- `references/pre-release-structure-refactor-task-tree.json`
- `references/redcap-parent-task-ledger.md`

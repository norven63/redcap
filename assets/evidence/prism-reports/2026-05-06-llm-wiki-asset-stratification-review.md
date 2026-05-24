# Prism Review: LLM-wiki Asset Stratification

## Scope

Norven asked RedCap and Prism to assess the whole RedCap asset surface and decide which assets are suitable for an LLM-wiki semantic-memory layer, and which must remain in other storage or governance layers.

This run reviewed only the asset stratification and requirement-registration boundary. It did not approve a complete LLM-wiki implementation, public writeback, RAG, GraphRAG, or raw private evidence export.

## Roster

- Kimi / Moonshot family: challenger
- Claude Code / Claude family: reviewer

Kimi's first review identified blocking gaps in the initial classification: control policies, host entry surfaces, Prism formal reports, privacy classification, and refresh/staleness boundaries were not explicit enough. After the policy was corrected, Kimi passed the revised boundary with low-severity follow-up risks only.

Claude Code passed the revised boundary and confirmed the remaining risks are observable and non-blocking.

## Verdict

Pass after corrections.

The accepted boundary is:

- LLM-wiki is a private, non-authoritative semantic-memory cache for AI and human maintainers.
- Control truth remains in `.dev-task.md`, promise ledgers, closeout receipts, commits, source policies, and Prism acceptance.
- Raw private reports, Prism runs, identity, runtime evidence, and secrets are never wiki content.
- Wiki entries require source anchors and staleness rules.
- Public promotion remains gated by RedCap Forge.
- RAG and GraphRAG remain deferred to the retrieval escalation policy.
- `P4-2h-3` is registered as the future implementation task, not claimed complete.

## Evidence

- `prism/runs/20260506-llm-wiki-asset-stratification-review/collect/challenger/parsed.json`
- `prism/runs/20260506-llm-wiki-asset-stratification-review/collect/reviewer/parsed.json`
- `prism/runs/20260506-llm-wiki-asset-stratification-review/artifacts/acceptance-binding.json`
- `references/llm-wiki-asset-stratification-policy.json`
- `compass/tools/redcap-llm-wiki-asset-stratification-check.py`

# RedCap knowledge log

本文件是 `compass/knowledge/` 的 append-only 时间线入口，用来记录长期记忆层发生过的关键吸收、晋升、no-promote、lint 和架构边界决策。它不是原始证据仓库；原始报告、运行痕迹和私有身份信息仍必须留在各自受控位置，并通过索引按需读取。

## [2026-05-06] policy | agent-reading-absorption

- Source: `/Users/norven/workspace/AI Era/docs/agent-reading-guide.md` and related source documents.
- Decision: absorb `ai-engineer.md` as engineering discipline and `llm-wiki.md` as long-term-memory architecture guidance.
- Boundary: no new unconstrained LLM-owned Wiki layer, no direct public redcap-arsenal writeback, no RAG/GraphRAG enablement, no production use of noisy `ai-professor-mode.md`.
- Evidence: `references/agent-reading-absorption-policy.json`.

## [2026-05-17] lesson | self-check-recursion-guard

- Source: `compass/docs/task-reports/2026-05-17-historical-asset-physical-cleanup-release-hard-gate.md` and live `human-product-surface` recursion review.
- Decision: self-checkers that call aggregate diagnostics must declare recursion guards and clean timeout descendants by process group.
- Boundary: keep raw process listings and private runtime evidence out of the long-term knowledge log; store only the reusable rule and source anchor.
- Evidence: `compass/knowledge/lessons/l-162.md`.

# RedCap knowledge index

本文件是 `assets/knowledge/` 的首读导航。旧 `compass/knowledge/` 只是兼容入口。本索引不替代任何原文，只帮助新会话按需找到正确知识入口，避免为了找规则而批量打开整个目录。

## 首读顺序

1. `assets/knowledge/lessons.md`：活跃经验库索引；先看开头的“热点主题速览”和 L-编号短锚点，再按命中的 L-编号打开 `assets/knowledge/lessons/<l-id>.md` 精读正文；旧 `compass/knowledge/**` 仅为兼容入口。
2. `assets/knowledge/design-principles.md`：RedCap 设计元原则，适合做架构/治理取舍前置检查。
3. `assets/knowledge/long-task-context-defense.md`：长任务 / 长对话上下文对抗策略，说明当前防线、行业常见方案与未完成边界。
4. `assets/knowledge/runtime-memory-architecture.md`：人话词典，解释真相源、镜像、闭环证据、跨会话考古/追踪层与长期沉淀层。
5. `assets/knowledge/log.md`：长期记忆层的 append-only 时间线；只记录吸收、晋升、no-promote、lint 与边界决策，不存原始证据。
6. `assets/knowledge/llm-wiki/`：私有、非权威、source-anchor 驱动的 LLM-wiki-lite 语义记忆层；只读 index 后按需打开精确 entry。
7. `assets/knowledge/llm-wiki-full/`：私有、非权威、review-gated 的 full LLM-wiki 产品层；用于稳定概念、决策框架、反复失败模式和术语解释，不接管权威源。
8. `assets/knowledge/governance-debt-register.md`：治理债务登记，说明哪些规则还没有完全变成可执行保障。
9. `assets/knowledge/host-reliability.md`：宿主可靠性与 Hook 分层策略。

## 宿主与 Hook

- `assets/knowledge/hooks-claude-code.md`：Claude Code Hook 行为与部署记录。
- `assets/knowledge/hooks-codex-cli.md`：Codex CLI / Codex.app 的入口导入、非交互 runner 与 host-limited 边界。
- `assets/knowledge/hooks-copilot-cli.md`：Copilot CLI Hook 行为与限制。
- `assets/knowledge/hooks-gemini-cli.md`：Gemini CLI Hook 行为与验证记录。
- `assets/knowledge/hooks-kimi-cli.md`：Kimi CLI Hook 行为与验证记录。
- `assets/knowledge/hooks-vscode-copilot.md`：VS Code Copilot 相关 Hook / skill 加载边界。
- `assets/knowledge/layerA-hook-deploy.md`：Layer A 项目 Hook 部署说明。
- `assets/knowledge/DEPLOYMENT_STATUS.md`：多宿主部署状态概览。

## 协作与历史

- `assets/knowledge/a2a-communication.md`：Agent-to-Agent 通信与 session 恢复约束。
- `assets/knowledge/explore-notes.md`：早期探索记录，仅在追溯原始讨论时按需读取。
- `assets/knowledge/lessons-archive.md`：已降温经验归档；优先读 `lessons.md`，只有需要历史根因时再打开。

## 使用规则

- 不要默认 bulk-read `assets/knowledge/**`；旧 `compass/knowledge/**` 仅用于兼容历史引用。
- 先读本索引，再按问题打开 1-3 个精确文件。
- 若新增、移动或删除 `assets/knowledge/*.md`、`assets/knowledge/lessons/*.md` 或首读子目录，必须同步更新本索引 / lessons 索引并让 `redcap-knowledge-index-check.sh` 通过；若改动 LLM-wiki-full，还必须让 `redcap-full-llm-wiki-check.sh` 通过。

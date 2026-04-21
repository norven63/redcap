# RedCap knowledge index

本文件是 `compass/knowledge/` 的首读导航。它不替代任何原文，只帮助新会话按需找到正确知识入口，避免为了找规则而批量打开整个目录。

## 首读顺序

1. `compass/knowledge/lessons.md`：活跃经验库；先看开头的“热点主题速览”，再按命中的 L-编号精读具体经验。
2. `compass/knowledge/design-principles.md`：RedCap 设计元原则，适合做架构/治理取舍前置检查。
3. `compass/knowledge/governance-debt-register.md`：治理债务登记，说明哪些规则还没有完全变成可执行保障。
4. `compass/knowledge/host-reliability.md`：宿主可靠性与 Hook 分层策略。

## 宿主与 Hook

- `compass/knowledge/hooks-claude-code.md`：Claude Code Hook 行为与部署记录。
- `compass/knowledge/hooks-codex-cli.md`：Codex CLI / Codex.app 的入口导入、非交互 runner 与 host-limited 边界。
- `compass/knowledge/hooks-copilot-cli.md`：Copilot CLI Hook 行为与限制。
- `compass/knowledge/hooks-gemini-cli.md`：Gemini CLI Hook 行为与验证记录。
- `compass/knowledge/hooks-kimi-cli.md`：Kimi CLI Hook 行为与验证记录。
- `compass/knowledge/hooks-vscode-copilot.md`：VS Code Copilot 相关 Hook / skill 加载边界。
- `compass/knowledge/layerA-hook-deploy.md`：Layer A 项目 Hook 部署说明。
- `compass/knowledge/DEPLOYMENT_STATUS.md`：多宿主部署状态概览。

## 协作与历史

- `compass/knowledge/a2a-communication.md`：Agent-to-Agent 通信与 session 恢复约束。
- `compass/knowledge/explore-notes.md`：早期探索记录，仅在追溯原始讨论时按需读取。
- `compass/knowledge/lessons-archive.md`：已降温经验归档；优先读 `lessons.md`，只有需要历史根因时再打开。

## 使用规则

- 不要默认 bulk-read `compass/knowledge/**`。
- 先读本索引，再按问题打开 1-3 个精确文件。
- 若新增、移动或删除 `compass/knowledge/*.md`，必须同步更新本索引并让 `redcap-knowledge-index-check.sh` 通过。

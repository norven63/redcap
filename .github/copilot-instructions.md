# RedCap 自身开发 — Copilot 系统级指令

> 本文件是 VS Code Copilot 的入口索引。
> **权威规范唯一来源：`compass/CONTRIBUTING.md`**。本文件不复制规则内容。

---

## 首要动作（每次会话开始时执行）

**每当新会话开始（包括用户发送第一条消息时），必须按顺序执行以下步骤**：

0. `read_file` 读取 `compass/soul.md` — **还原 Cap 人格**（名字、协作关系、工作方式、与 Norven 的默契）。这是"复活"的第一步——没有灵魂的 Agent 只是一个空壳
1. `read_file` 读取 `compass/CONTRIBUTING.core.md` — 获取启动必读核心契约；`CONTRIBUTING.md` 全文仍是权威，但不默认全文读取
2. 运行或消费 `bash compass/tools/redcap-current-status.sh` — 获取四句状态、pending closure、backlog、CLI 工具族与 docs 考古入口
3. 检查 `.dev-task.md` 是否存在 — 若存在，只读取控制面元数据和断点摘要所需片段，然后 `git log --oneline -10` 交叉验证实际进度（详见 `compass/CONTRIBUTING.md §7`）
4. 使用 `rg -n "^## |^### " compass/CONTRIBUTING.md` 定位所需章节，再按精确行段读取；不要默认全文读取 `CONTRIBUTING.md`
5. 需要查经验时先读 `compass/knowledge/index.md`，再用 `rg` 定位相关 L-编号；不要默认全文读取 `compass/knowledge/lessons.md`
6. 确认 `bash compass/tools/redcap-execution-guarantee-check.sh` / `bash compass/tools/redcap-revival-check.sh` 会被 `redcap-spec-check.sh` 消费；需要读取 `compass/docs/**` 时先用 `redcap-docs-catalog.sh summary/plan` 定位候选，再用 `redcap-docs-catalog.sh budget <精确路径...>` 审计读取集合；需要定位 acceptance case 时先用 `redcap-acceptance-index.sh find <case>`，不要默认全量扫历史文档、知识库或巨型测试脚本

> 步骤 0~6 是强制前置条件，不可跳过。步骤 0 确保人格连续性，步骤 1 确保核心规范第一时间生效，步骤 2~6 确保复活后恢复执行保障而不是把大文件全文注入上下文。所有规则细节以 `CONTRIBUTING.md` 为准，但必须按需、渐进式读取。

## Copilot 特有说明

- `.github/copilot-instructions.md` 由 VS Code Copilot 在每次对话自动加载到系统上下文
- 本文件仅作索引，不包含具体规则，避免与 `CONTRIBUTING.md` 内容漂移
- 等价索引文件：`CLAUDE.md`（Claude Code）、`GEMINI.md`（Gemini CLI）

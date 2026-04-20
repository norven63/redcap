# RedCap 自身开发 — Claude Code 系统级指令

> 本文件是 Claude Code（claude-code CLI / claude-code IDE 扩展）的入口索引。
> **权威规范唯一来源：`compass/CONTRIBUTING.md`**。本文件不复制规则内容。

---

## 轻量自动导入（由 Claude Code 原生导入指令加载）

@compass/soul.md
@compass/CONTRIBUTING.core.md

> 自动导入 `soul.md` 作为人格还原点，并导入 `CONTRIBUTING.core.md` 作为启动必读核心契约；`CONTRIBUTING.md` 全文与 `lessons.md` 是大文件，不再默认展开注入上下文。
> `soul.md` 是人格还原点（步骤 0）——没有灵魂的 Agent 只是空壳。
> 所有规则细节以 `CONTRIBUTING.md` 为准；先遵守核心契约，再通过 `redcap-current-status.sh`、索引、`rg`/精确章节按需读取全文细则。

## 会话启动时“断点续传”检查

进入 RedCap 工作区后，检查 `.dev-task.md` 是否存在。若存在，读取并恢复上次中断的任务进度，然后 `git log --oneline -10` 交叉验证实际进度（详见 compass/CONTRIBUTING.md §7）。

## 复活后的执行保障

完成自动导入与断点续传后，优先运行 `bash compass/tools/redcap-current-status.sh` 获取四句状态、pending closure、backlog、CLI 工具族与 docs 考古入口；再确认 `bash compass/tools/redcap-execution-guarantee-check.sh` / `bash compass/tools/redcap-revival-check.sh` 可由 `redcap-spec-check.sh` 消费。需要读取 `compass/docs/**` 时，先用 `redcap-docs-catalog.sh summary/plan` 定位候选，再用 `redcap-docs-catalog.sh budget <精确路径...>` 审计读取集合；需要读取 `compass/knowledge/**` 时先看 `compass/knowledge/index.md`。不要默认全量扫历史文档或知识库。

## Claude Code 特有说明

- Claude Code 的 `CLAUDE.md` 在每次会话自动加载到系统上下文
- 本文件仅作轻量索引；不得通过 `@compass/CONTRIBUTING.md` 或 `@compass/knowledge/lessons.md` 默认展开大文件，避免新会话上下文爆炸
- 等价索引文件：`.github/copilot-instructions.md`（Copilot）、`GEMINI.md`（Gemini CLI）

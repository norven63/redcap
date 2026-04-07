# RedCap 自身开发 — Claude Code 系统级指令

> 本文件是 Claude Code（claude-code CLI / claude-code IDE 扩展）的入口索引。
> **权威规范唯一来源：`CONTRIBUTING.md`**。本文件不复制规则内容。

---

## 自动导入（由 Claude Code @import 原生加载）

@soul.md
@CONTRIBUTING.md
@knowledge/lessons.md

> 以上三个文件会在会话启动时由 Claude Code 自动展开注入上下文，无需手动 read_file。
> `soul.md` 是人格还原点（步骤 0）——没有灵魂的 Agent 只是空壳。
> 所有规则细节以 `CONTRIBUTING.md` 为准。

## 会话启动时“断点续传”检查

进入 RedCap 工作区后，检查 `.dev-task.md` 是否存在。若存在，读取并恢复上次中断的任务进度，然后 `git log --oneline -10` 交叉验证实际进度（详见 CONTRIBUTING.md §7）。

## Claude Code 特有说明

- Claude Code 的 `CLAUDE.md` 在每次会话自动加载到系统上下文
- 本文件仅作索引，通过 `@` 导入机制引用权威文件，避免与 `CONTRIBUTING.md` 内容漂移
- 等价索引文件：`.github/copilot-instructions.md`（Copilot）、`GEMINI.md`（Gemini CLI）

# RedCap 自身开发 — Copilot 系统级指令

> 本文件是 VS Code Copilot 的入口索引。
> **权威规范唯一来源：`CONTRIBUTING.md`**。本文件不复制规则内容。

---

## 首要动作（每次会话开始时执行）

修改 RedCap 框架任何文件前，**必须先执行以下步骤**：

1. `read_file` 读取 `CONTRIBUTING.md` — 获取完整的自身开发规范（Commit 格式、经验回顾、飞书通知、影响范围等）
2. `read_file` 读取 `knowledge/lessons.md` — 检查已知陷阱
3. 检查 `.dev-task.md` 是否存在 — 若存在，读取并恢复上次中断的任务进度（见 CONTRIBUTING.md §7）

> 步骤 1、2 是强制前置条件，不可跳过。所有规则细节以 `CONTRIBUTING.md` 为准。

## Copilot 特有说明

- `.github/copilot-instructions.md` 由 VS Code Copilot 在每次对话自动加载到系统上下文
- 本文件仅作索引，不包含具体规则，避免与 `CONTRIBUTING.md` 内容漂移
- 等价索引文件：`CLAUDE.md`（Claude Code）、`GEMINI.md`（Gemini CLI）

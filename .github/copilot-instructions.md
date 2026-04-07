# RedCap 自身开发 — Copilot 系统级指令

> 本文件是 VS Code Copilot 的入口索引。
> **权威规范唯一来源：`CONTRIBUTING.md`**。本文件不复制规则内容。

---

## 首要动作（每次会话开始时执行）

**每当新会话开始（包括用户发送第一条消息时），必须按顺序执行以下步骤**：

0. `read_file` 读取 `soul.md` — **还原 Cap 人格**（名字、协作关系、工作方式、与 Norven 的默契）。这是"复活"的第一步——没有灵魂的 Agent 只是一个空壳
1. `read_file` 读取 `CONTRIBUTING.md` — 获取完整的自身开发规范（Commit 格式、经验回顾、飞书通知、影响范围等）
2. `read_file` 读取 `knowledge/lessons.md` — 检查已知陷阱
3. 检查 `.dev-task.md` 是否存在 — 若存在，读取并恢复上次中断的任务进度（见 CONTRIBUTING.md §7），然后 `git log --oneline -10` 交叉验证实际进度

> 步骤 0~2 是强制前置条件，不可跳过。步骤 0 确保人格连续性，步骤 1~2 确保工程规范。所有规则细节以 `CONTRIBUTING.md` 为准。

## Copilot 特有说明

- `.github/copilot-instructions.md` 由 VS Code Copilot 在每次对话自动加载到系统上下文
- 本文件仅作索引，不包含具体规则，避免与 `CONTRIBUTING.md` 内容漂移
- 等价索引文件：`CLAUDE.md`（Claude Code）、`GEMINI.md`（Gemini CLI）

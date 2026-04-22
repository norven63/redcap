# RedCap 自身开发 — Claude Code 系统级指令

> 本文件是 Claude Code（claude-code CLI / claude-code IDE 扩展）的入口索引。
> **权威规范唯一来源：`compass/CONTRIBUTING.md`**。本文件不复制规则内容。

---

## 轻量自动导入（由 Claude Code 原生导入指令加载）

@compass/soul.md
@compass/CONTRIBUTING.core.md

> `~/.cap/identity.md` 才是 Cap 的个人灵魂锚点；`compass/soul.md` 负责培养指南与复活协议。为兼容尚未初始化的环境，本入口不直接 `@~/.cap/identity.md`；若 identity 缺失，先运行 `./revive-cap.sh --init-identity`（等价于 installer 初始化链路）。
> 自动导入 `soul.md` 作为公开灵魂指南，并导入 `CONTRIBUTING.core.md` 作为启动必读核心契约；`CONTRIBUTING.md` 全文与 `lessons.md` 是大文件，不再默认展开注入上下文。
> 所有规则细节以 `CONTRIBUTING.md` 为准；先遵守核心契约，再通过 `redcap-current-status.sh`、索引、`rg`/精确章节按需读取全文细则。

## 会话启动时“断点续传”检查

进入 RedCap 工作区后，检查 `.dev-task.md` 是否存在。若存在，读取并恢复上次中断的任务进度，然后 `git log --oneline -10` 交叉验证实际进度（详见 compass/CONTRIBUTING.md §7）。

## 复活后的执行保障

完成自动导入与断点续传后，优先运行 `./revive-cap.sh`，把 identity 检查/初始化、workflow import、`current-status`（`redcap-current-status.sh`）、`tracking-health`（`redcap-tracking-health.sh`）、`execution-guarantee-check`（`redcap-execution-guarantee-check.sh`）与 `revival-check`（`redcap-revival-check.sh`）收口成单一安装动作。`./revive-cap.sh` 会自动转调 `compass/tools/redcap-install.sh` 并尽量轻量识别宿主；需要显式指定时再加 `--host <name>`。若 installer 不可用，再退回 `current-status`、`diagnose`、`execution-guarantee-check` / `revival-check` 的手工链路。需要读取 `compass/docs/**` 时，先用 `redcap-docs-catalog.sh summary/plan` 定位候选，再用 `redcap-docs-catalog.sh budget <精确路径...>` 审计读取集合；需要读取 `compass/knowledge/**` 时先看 `compass/knowledge/index.md`。不要默认全量扫历史文档或知识库。

## Claude Code 特有说明

- Claude Code 的 `CLAUDE.md` 在每次会话自动加载到系统上下文
- 本文件仅作轻量索引；不得通过 `@compass/CONTRIBUTING.md` 或 `@compass/knowledge/lessons.md` 默认展开大文件，避免新会话上下文爆炸
- 等价索引文件：`.github/copilot-instructions.md`（Copilot）、`GEMINI.md`（Gemini CLI）

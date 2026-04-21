# RedCap 自身开发 — Copilot 系统级指令

> 本文件是 VS Code Copilot 的入口索引。
> **权威规范唯一来源：`compass/CONTRIBUTING.md`**。本文件不复制规则内容。

---

## 首要动作（每次会话开始时执行）

**每当新会话开始（包括用户发送第一条消息时），必须按顺序执行以下步骤**：

0. 若 `~/.cap/identity.md` 存在，优先 `read_file` 读取它 — **还原 Cap 的个人灵魂锚点**；若不存在，先运行 `bash compass/tools/redcap-install.sh --host copilot --task-file .dev-task.md --init-identity`
1. `read_file` 读取 `compass/soul.md` — 载入培养指南与复活协议；它不能替代 identity，但负责把执行纪律拉回当前会话
2. `read_file` 读取 `compass/CONTRIBUTING.core.md` — 获取启动必读核心契约；`CONTRIBUTING.md` 全文仍是权威，但不默认全文读取
3. 优先运行或消费 `bash compass/tools/redcap-install.sh --host copilot --task-file .dev-task.md` — 将 workflow import、`current-status`（`redcap-current-status.sh`）、`tracking-health`（`redcap-tracking-health.sh`）、`execution-guarantee-check`（`redcap-execution-guarantee-check.sh`）、`revival-check`（`redcap-revival-check.sh`）收口为单一安装/复活动作
4. 若 installer 不可用，再退回：运行或消费 `bash compass/tools/redcap-current-status.sh`，检查 `.dev-task.md` 是否存在，必要时 `git log --oneline -10` 交叉验证实际进度（详见 `compass/CONTRIBUTING.md §7`）
5. 使用 `rg -n "^## |^### " compass/CONTRIBUTING.md` 定位所需章节，再按精确行段读取；不要默认全文读取 `CONTRIBUTING.md`
6. 需要查经验时先读 `compass/knowledge/index.md`，再用 `rg` 定位相关 L-编号；不要默认全文读取 `compass/knowledge/lessons.md`
7. 需要读取 `compass/docs/**` 时先用 `redcap-docs-catalog.sh summary/plan` 定位候选，再用 `redcap-docs-catalog.sh budget <path...>` 审计读取集合；需要定位 acceptance case 时先用 `redcap-acceptance-index.sh find <case>`，不要默认全量扫历史文档、知识库或巨型测试脚本

> 步骤 0~7 是强制前置条件，不可跳过。步骤 0~2 还原人格与核心契约，步骤 3 把“Cap 复活 + 导入 RedCap 工作流”统一成单一安装动作，步骤 4~7 保证后续只按需、渐进式加载。

## Copilot 特有说明

- `.github/copilot-instructions.md` 由 VS Code Copilot 在每次对话自动加载到系统上下文
- 本文件仅作索引，不包含具体规则，避免与 `CONTRIBUTING.md` 内容漂移
- 等价索引文件：`CLAUDE.md`（Claude Code）、`GEMINI.md`（Gemini CLI）

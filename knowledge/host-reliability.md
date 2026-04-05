# 宿主 Agent 可靠性调研报告

> **调研日期**：2026-04  
> **调研背景**：RedCap E2E 测试中 `on_ALL_DONE` 飞书通知被遗漏（L-9 复现），需评估宿主 Agent 的指令持久性和可靠性保障机制，为 RedCap 的关键动作防遗漏策略提供决策依据。  
> **核心发现**：指令注入物理上每轮都在，但 LLM attention 衰减使执行率随对话长度下降。唯一 100% 保证的是 Hooks（绕过 LLM 的 shell 命令）。4 个宿主工具中 Claude Code 和 Kimi CLI 支持 Hooks。

---

## 0. Hook 两层架构

RedCap 既是开发工具，也是被开发的对象。因此 Hook 体系分为两层：

| | Layer A — RedCap 开发用户项目 | Layer B — 开发 RedCap 自身 |
|---|---|---|
| **工作区** | 用户项目 repo | RedCap 自身 repo |
| **Hook 本质** | Dispatcher 状态机内的逻辑事件（`on_QA_PASS`、`on_ALL_DONE` 等） | 宿主工具原生 shell Hook |
| **定义位置** | SKILL.md §5.10 + `dispatcher/state-machine.md` | 工程级配置（`.claude/settings.json`、`config.toml` + dispatcher） |
| **可移植性** | 跟随 RedCap 框架，适用于所有项目 | 仅对 RedCap 自身 repo 生效 |
| **执行保证** | `on_ALL_DONE`: Layer 0（用户级 Stop hook）；其他: Layer 2-3 | 100% 确定性（Layer 0） |

> 本文件及其子文档（`hooks-*.md`）记录的**宿主 Hook 能力**同时服务于两层。§3 的四层防御策略以 Layer A 场景为主，Layer B 的具体部署见各 `hooks-*.md` 的"部署现状"章节及 `CONTRIBUTING.md` §4-§5。Layer A 的用户级 Hook 脚本见 `tools/redcap-layerA-*.sh`。

---

## 1. 宿主工具总览

| 宿主工具 | 指令注入频率 | 注入位置 | Hooks 状态 | 详情文档 |
|----------|------------|----------|-----------|---------|
| VS Code Copilot | 每轮对话 | Context 附件 | ⚠️ 有限（无 onTaskComplete） | [hooks-vscode-copilot.md](hooks-vscode-copilot.md) |
| Claude Code | 会话开始 + compact 后重读 | User message | ✅ Stop hook（100%） | [hooks-claude-code.md](hooks-claude-code.md) |
| Gemini CLI | 每次 prompt | 与 prompt 拼接 | ❌ 已实现但未集成（v0.36.0） | [hooks-gemini-cli.md](hooks-gemini-cli.md) |
| Kimi CLI | N/A（无指令文件） | N/A | ✅ 13 种事件（v1.30.0 实测） | [hooks-kimi-cli.md](hooks-kimi-cli.md) |

---

## 2. 执行可靠性的真正瓶颈

### 2.1 注入 vs 执行的区别

| 层面 | 表现 | 100% 保证？ |
|------|------|------------|
| **物理注入**（文本是否在 LLM 输入中） | 各工具均做到每轮/每次重注入 | ✅ 是 |
| **LLM 执行**（是否遵从指令） | 受 attention 衰减影响 | ❌ 不可能 |

### 2.2 Attention 衰减效应

虽然指令每轮物理存在，但 LLM 在长对话中遵从度下降：

1. **Context window 稀释**：对话越长，指令在 context 中的相对权重越低
2. **Lost in the Middle**：LLM 对 context 中间位置内容的 attention 最低（首尾效应）
3. **任务聚焦偏移**：LLM 越来越关注近期对话内容，远处的指令"淡化"

**经验估算**（基于 RedCap E2E 测试观察）：

| 对话长度 | 指令遵从率（估算） |
|---------|-------------------|
| 1-5 轮 | ~95%+ |
| 6-15 轮 | ~85-90% |
| 15-30 轮 | ~70-80% |
| 30+ 轮 | ~60% 以下 |

> RedCap 完整流程通常在 20-40 轮，恰好处于遵从率显著下降的区间。

---

## 3. 对 RedCap 的部署建议

### 3.1 防遗漏策略（四层防御）

| 层 | 机制 | 可靠性 | 说明 |
|----|------|--------|------|
| **Layer 0** | **宿主 Hooks**（如有） | **100%** | 绕过 LLM，确定性执行 |
| **Layer 1** | 系统级指令提醒（copilot-instructions.md / CLAUDE.md） | 补救率 ~30-50% | 每轮都在但可能被忽视 |
| **Layer 2** | SKILL.md `on_ALL_DONE` hooks | ~60-70% | 长任务中 attention 衰减 |
| **Layer 3** | 下次启动审计 | ~95-100% | 新会话第一轮，attention 最强 |

### 3.2 各环境 Hook 可用性

| 环境 | Layer 0 可用？ | 部署方式 | 详见 |
|------|--------------|---------|------|
| Claude Code | ✅ | 工程级 `.claude/settings.json` Stop hook | [hooks-claude-code.md §3](hooks-claude-code.md) |
| Kimi CLI | ✅ | 全局 Dispatcher 路由（**必须遵守协议**） | [hooks-kimi-cli.md §3](hooks-kimi-cli.md) |
| VS Code Copilot | ❌ | 退守 Layer 1-3 | [hooks-vscode-copilot.md §3](hooks-vscode-copilot.md) |
| Gemini CLI | ❌ | 退守 Layer 1-3 | [hooks-gemini-cli.md §3](hooks-gemini-cli.md) |

### 3.3 收尾脚本封装（已实现）

关键 hook 的多步动作已封装为确定性 shell 脚本：

| 脚本 | 对应 Hook | 封装的动作 | 调用示例 |
|------|----------|-----------|---------|
| `tools/redcap-on-complete.sh` | `on_ALL_DONE` | ① 清除 .workflow/ 临时文件（§5.9）② 输出交付摘要 ③ 飞书通知（§5.11） | `bash tools/redcap-on-complete.sh <project_dir> <initial_head> <project_name>` |
| `tools/redcap-on-qa-pass.sh` | `on_QA_PASS` | ① git add -A && git commit（按 commit-standards.md）② 检查 lesson 字段 | `bash tools/redcap-on-qa-pass.sh <project_dir> <type> <scope> <message> [body]` |
| `tools/redcap-on-stop-review.sh` | Stop Hook（Layer B） | 提取 git diff → 拉起新 Agent 独立架构评审 → PASS/FAIL + 飞书告警 | 由 `.claude/settings.json` Stop hook 自动触发 |

**好处**：Dispatcher 只需记住"调一个脚本"，而不是"记住 N 个步骤每步的细节"。

### 3.4 下次启动审计（Layer 3）

在 §5.1 启动流程中增加检查（已实现为 §5.1 步骤 2.5）：
- 若 `pending_actions` 非空 → 说明上次会话遗漏了收尾动作 → 立即补执行
- 这一层在新会话第一轮执行，attention 最强，最可靠

### 3.5 工作流节点→防护措施映射

基于系统性梳理，将 RedCap 所有工作流节点按可靠性风险分类：

#### Category 1 — 关键节点（必须 100% 执行）

| 节点 | 风险 | 已有防护 | 剩余风险 |
|------|------|---------|---------|
| `on_ALL_DONE`（清理+摘要+飞书） | E2E 已实际遗漏（L-9） | ✅ Layer B: 项目级 Stop hook + 独立架构评审 + Layer A: 用户级 Stop hook（三重过滤）+ 脚本封装 + pending_actions + 启动审计 | 低（前提：已按 `layerA-hook-deploy.md` 部署用户级 Hook）：Layer A/B 均有 Layer 0 保护（Claude/Kimi）。VS Code/Gemini 退守 Layer 2+3 |
| `on_QA_PASS`（git commit） | 遗漏则代码可能丢失 | ✅ 脚本封装 + pending_actions | 低：pending_actions 原子写入保障 |
| `§5.13 pending_actions 写入` | 递归遗忘问题 | ✅ 原子写入铁律（与 current_state 同一次写入） | 中：仍为 LLM 执行，但降为单一操作 |

#### Category 2 — 可恢复节点（遗漏可补救）

| 节点 | 恢复方式 |
|------|---------|
| §5.7 交付物校验 | 下轮 QA 会发现 |
| §5.5 Fallback 路由 | Agent 失败自动触发 |
| §5.8 经验沉淀 | 手动补录，不阻塞流程 |

#### Category 3 — 已天然安全的节点

| 节点 | 安全原因 |
|------|---------|
| §5.2 步骤 1 读 state.yaml | 事件循环首步，attention 最强 |
| §5.3 状态解析 | 机械操作，不依赖记忆 |
| §5.6 Session 管理 | 查询型操作，幂等 |

---

## 4. 总结

| 结论 | 详情 |
|------|------|
| **指令注入是可靠的** | 各工具都做到了每轮/每次物理注入 |
| **LLM 执行是概率性的** | 随对话长度必然衰减，无法 100% |
| **唯一 100% 保证是 Hooks** | 绕过 LLM，宿主程序直接执行 shell（Claude Code、Kimi CLI 均支持） |
| **RedCap 最佳策略** | 用脚本封装关键动作 + 宿主 Hooks（如有）+ 下次启动审计 |
| **Hook 覆盖率** | 4 个宿主中 2 个有 Hooks（Claude Code: Stop; Kimi CLI: Stop+SessionEnd 等 13 种），2 个无（VS Code Copilot、Gemini CLI） |

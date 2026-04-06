# RedCap 自身开发规范

> 本文件约束 **RedCap 框架自身** 的变更流程。项目 Agent 在开发用户项目时遵守的规范见 `references/` 目录。

---

## 1. 变更前：经验回顾

修改框架文件前，**必须先阅读以下两个文件**：

1. **`knowledge/design-principles.md`**（元原则）— 确认本次变更不违背 P-1 至 P-5 五项战略层原则
2. **`knowledge/lessons.md`**（经验库）— 检查本次变更是否涉及已知陷阱

重点关注：
- L-4（Fallback 深度不足）：修改路由/降级逻辑时
- L-7（gemini headless 挂起）：修改 Agent 适配器时
- L-8（先测再改）：涉及 Agent 调用方式变更时，必须先实测再改文档
- L-16（设计≠部署≠生效）：修改 Hook 配置或 Dispatcher 路由时，必须端到端验证
- L-17（Agent 信息茧房）：编写提示词时，确保关键资产文件有显式引用路径
- L-18（A2A 讨论优于指令）：Agent 间协作采用讨论共识模式，而非单向命令模式

## 2. Commit 规范

采用中文 Conventional Commit 格式：

```
type(scope): 简要描述

正文（可选，说明动机和关键变更）
```

**type 取值**：

| type | 用途 |
|------|------|
| `feat` | 新功能、新机制 |
| `fix` | 缺陷修复、行为修正 |
| `refactor` | 重构（不改变外部行为） |
| `docs` | 仅文档变更 |
| `chore` | 构建、工具、配置等杂务 |

**scope 取值**（框架自身常用）：

| scope | 对应目录/文件 |
|-------|-------------|
| `框架` | SKILL.md 核心流程 |
| `状态机` | dispatcher/state-machine.md |
| `适配器` | dispatcher/agent-adapters.md |
| `模板` | dispatcher/prompt-templates/ |
| `角色` | roles/ 下的角色手册 |
| `规范` | references/ 下的规范文件 |
| `feishu` | tools/feishu-notifier.py + 相关配置 |
| `经验` | knowledge/lessons.md |
| `铁律` | 涉及安全铁律的变更 |

**示例**：
```
feat(feishu): 前台阻塞模式+中断恢复
fix(框架): 修正Git规范 — commit由Dispatcher执行
refactor(状态机): PAUSED 伪代码更新为前台阻塞
docs(经验): 新增 L-9 飞书架构局限性
```

## 3. 变更后：经验沉淀检查

每轮变更完成后，执行以下自检（同 `knowledge/lessons.md` 中的归档触发检查点）：

1. 本轮是否发现了**新的失败模式或反直觉行为**？→ 归档为 Lesson
2. 本轮是否验证了一个**之前文档中写错的假设**？→ 归档为 Lesson
3. 本轮使用的**工作方法本身**是否值得复用？→ 归档为方法论 Lesson

## 4. 独立架构评审（Stop Hook 自动触发）

> **本节属于 Layer B（开发 RedCap 自身）**。Layer A 的评审由状态机 `REVIEW_WORKING` 节点驱动，当 LLM 跳过 Review 直接进入 ALL_DONE 时，Layer A Stop Hook 会检测缺失并拉起新 Agent 兜底执行项目级 Review（`tools/redcap-layerA-review-fallback.sh`）。两层共享同一设计模式：Hook 100% 触发 + 新 Agent 生命周期保证认知能力（详见 L-15）。

**问题**：开发 Agent 在长对话末期注意力衰减，可能遗漏规范检查、文件联动、经验沉淀等收尾动作。即使 §3 写了自检清单，长任务末期的 LLM 也可能"忘记"执行。

**解法**：Layer 0（物理 Hook）+ 全新 Agent 生命周期。

- **触发机制**：Claude Code Stop Hook → `tools/redcap-on-stop-review.sh`
- **执行方式**：脚本提取 `git diff`，拉起一个全新的、无历史上下文污染的 Agent（`kimi -p` / `claude -p`）执行独立评审
- **评审维度**：Commit 规范、经验回顾、文件联动（§6 影响范围表）、内容质量、经验沉淀遗漏
- **结果处理**：
  - `PASS` → 静默通过
  - `FAIL`（含 P0 问题）→ 飞书告警 + 写标记文件 `/tmp/redcap-stop-review-result`
  - 评审日志始终保存到 `/tmp/redcap-stop-review-log.md`

> ⚠ Claude Code 的 Stop hook 退出码非零不会阻塞 Agent 退出。FAIL 时通过飞书告警通知用户，下次会话的 init hook 也可检查未解决的评审标记。

**宿主适配**：

| 宿主 | 触发方式 | 状态 |
|------|---------|------|
| Claude Code | `.claude/settings.json` Stop hook | ✅ 已部署 |
| Kimi CLI | `dispatcher` Stop 事件路由 | ⏳ 待适配 |
| VS Code Copilot | 无原生 Hook | ❌ 不支持 |
| Gemini CLI | Hook 机制待集成 | ❌ 不支持 |

## 5. 飞书通知

> **本节属于 Layer B（开发 RedCap 自身）**。Layer A（RedCap 开发用户项目）的 Hook 由 SKILL.md §5.10 定义，通过 Dispatcher 状态机触发。两层架构详见 `knowledge/host-reliability.md` §0。

RedCap 自身变更不走 Dispatcher 流程，飞书 hook 不会自动触发。**编辑 RedCap 的 AI Agent 必须在流程中自动执行以下通知**：

**完成通知（必须，自动执行）**：每轮变更全部完成并 git commit 后、结束任务前，**必须自动执行**以下命令（仅通知，不等待回复）：

```bash
# 消息中须附带本次 commit 记录
python3 tools/feishu-notifier.py notify "RedCap 框架变更完成: <简要描述>\n\nCommits:\n$(git log --oneline <初始commit>..HEAD)" --project "redcap"
```

> ⚠ 这是强制步骤，不可跳过。通知失败（如 feishu-config.json 不存在）时记录警告但不阻塞任务完成。

**过程中通知（按需）**：长时间等待用户确认方案等场景：

```bash
python3 tools/feishu-notifier.py ask "方案A还是方案B？" --project "redcap"
```

## 6. 文件变更影响范围提示

| 修改的文件 | 可能需要同步更新的文件 |
|-----------|---------------------|
| SKILL.md §5.2 事件循环 | dispatcher/state-machine.md 伪代码 |
| SKILL.md §5.10 Hooks | dispatcher/state-machine.md 对应触发点 |
| references/communication-protocol.md | roles/ 下各角色手册中的状态返回说明 + knowledge/a2a-communication.md §5.4 |
| dispatcher/agent-adapters.md | SKILL.md §5.5 路由表 + knowledge/a2a-communication.md §2 |
| dispatcher/state-machine.md 状态枚举 | knowledge/a2a-communication.md §4（NEGOTIATING 状态同步） |
| SKILL.md §5.10 Hooks 表 | dispatcher/state-machine.md `populate_pending_actions` + SKILL.md §5.13 映射表 |
| CONTRIBUTING.md 自身 | .github/copilot-instructions.md + CLAUDE.md + GEMINI.md 均为索引，通过 `@` 导入指向本文件；修改本文件即全局生效，无需手动同步 |
| references/agent-constraints.md | 项目级 CLAUDE.md / GEMINI.md 通过 `@` 导入此文件；修改此文件影响所有子 Agent 行为 |
| knowledge/design-principles.md | README.md 设计哲学章节 + CONTRIBUTING.md §1（元原则引用） |
| knowledge/a2a-communication.md | README.md 通信协议章节 + dispatcher/state-machine.md（前瞻标注） |
| 任何 Agent 调用方式 | 先实测（L-8），再改文档 |
| CONTRIBUTING.md §7 | .github/copilot-instructions.md + CLAUDE.md + GEMINI.md（入口索引中的断点续传检查指令）|
| tools/ 下 Hook 脚本 | .claude/settings.json（Hook 注册）+ knowledge/host-reliability.md（防线文档）|
| tools/redcap-layerA-*.sh | ~/.claude/settings.json（用户级 Hook 注册）+ knowledge/host-reliability.md §3.3/§3.5 + CONTRIBUTING.md §4 |
| references/communication-protocol.md §2 | SKILL.md §5.3 + dispatcher/state-machine.md 伪代码 5e-5f + 全部 prompt-templates + README.md 通信协议节 |
| tools/redcap-check-state.sh | tools/redcap-on-qa-pass.sh（集成调用）|

## 7. Layer B 大型任务断点续传

> **本节属于 Layer B（开发 RedCap 自身）**。Layer A 的断点续传由 `.workflow/state.yaml` 状态机自动保证。

**问题**：Layer B 无状态机保护，会话中断（坏死、超时、主动关闭）后，任务进度仅存在于 LLM 上下文中，无法结构化恢复。

**解法**：触发式轻状态文件 `.dev-task.md`。

### 触发条件

仅在以下情况创建：

> **预计超过 2 个独立阶段、且单次会话大概率无法完成** → 创建 `.dev-task.md`

单次 fix、docs 更新、单个 Lesson 沉淀等简单任务不需要。

### 文件格式

```markdown
# 当前任务：<任务名称>

## 目的（为什么做）
<一句话描述>

## 完成标准
- [ ] Phase 1: ...
- [ ] Phase 2: ...
- [x] Phase N: ... ← 已完成的打勾

## 断点备注
<当前进度、下一步、已知阻塞项>
```

### 生命周期

| 时机 | 动作 |
|------|------|
| 大型任务启动 | 在 RedCap 工作区根目录创建 `.dev-task.md` |
| 每完成一个阶段 | 更新 checklist + 断点备注（通常和 commit 是同一个认知时机，顺手打勾） |
| 新会话启动 | 入口索引检查该文件是否存在 → 存在则读取，然后 `git log --oneline -10` 交叉验证实际进度（可能最后一次更新后又做了几个 commit） |
| 任务全部完成 | 删除文件（或移至 `docs/` 归档） |

> 该文件已加入 `.gitignore`——它是临时过程状态，不应进入版本控制。

---

### 跨工具指令文件位置参考（经官方文档验证 2026-04）

| 工具 | 指令文件 | 有效路径 | 导入机制 |
|------|---------|---------|---------|
| VS Code Copilot | `.github/copilot-instructions.md` | 项目 `.github/` 下 | 无原生导入；使用 `read_file` 指令 |
| Claude Code | `CLAUDE.md` | `./CLAUDE.md` 或 `./.claude/CLAUDE.md` | `@file` 原生自动导入 |
| Gemini CLI | `GEMINI.md` | 项目根目录（及父目录层级） | `@file.md` 原生自动导入 |

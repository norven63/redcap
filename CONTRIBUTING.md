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
- L-24（前置对抗缺失）：设计方案中出现"不可行"判断时，必须执行 §1.1 Pre-mortem 挑战

### 1.1 设计自检：前置对抗（Red Team Self-Check）

> **触发时机**：设计方案成型、准备动手实现之前。
> **问题根因**：Layer B 无多角色制衡，Cap 独自设计容易产生"浅层判断即收手"的偷懒倾向（L-24）。

对设计方案中的**每一条"不可行/无法做到/暂不实现"的判断**，执行以下 Pre-mortem 挑战：

```
对每条"不可行"判断：
  1. 假设这个判断是错的 — 尝试找到至少一种实现方式
  2. 如果找到 → 评估成本，决定是否纳入
  3. 如果确实找不到 → 记录尝试过的方案，标注为"已验证的不可行"
  4. 禁止出现无尝试记录的"不可行"结论
```

对设计方案中的**覆盖范围声明**（如"覆盖 X 个功能点"），执行完备性挑战：

```
  1. 列出完整的功能点全集（从权威来源获取，如状态机所有路径）
  2. 逐项标记：已覆盖 / 未覆盖
  3. 对每个"未覆盖"项执行上述 Pre-mortem
```

> 这不是形式主义——L-24 的教训是：5 条"无法覆盖"中 3 条一经追问就发现完全可做。Pre-mortem 的成本（多想 5 分钟）远低于遗漏的修复成本。

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

## 3.1 E2E 验证：触发条件与最小产出物

**触发条件**——以下任一情况满足时，必须在真实项目中做端到端验证：

| 变更类型 | 示例 | 为什么需要 E2E |
|---------|------|---------------|
| 状态机转移逻辑变更 | 新增/修改状态、转移条件 | 静态审查无法验证运行时行为 |
| 通信协议变更 | `__redcap_status` 传递方式、JSON Schema | Agent 是否遵从只有实测才知道（L-23） |
| Prompt 模板结构性改动 | 新增变量、改变角色指令格式 | Agent 对 Prompt 变化的响应不可预测 |
| Agent 适配器/路由逻辑变更 | CLI 参数、降级策略 | CLI 行为只有调用才确定（L-8） |

单纯的文档措辞修正、经验沉淀、注释更新等不需要 E2E。

**变更登记（强制）**——commit 命中上表任一触发类型时，**必须**在 `testing/pending-validations.md` 追加一条 V-编号条目，格式见该文件头部说明。这是防止"待验证黑洞"的核心机制——不登记就会遗忘。

> ⚠ Stop Hook 评审（§4）会检查：本次 commit 是否涉及触发类型但未登记 pending-validation。

**最小产出物**——E2E 不要求写完整报告，但必须产出以下内容并融入框架：

1. **经验条目**（L-编号）：每个新发现的失败模式/反直觉行为 → 沉淀到 `knowledge/lessons.md`
2. **Bug 修复**：发现的问题当场修复并 commit
3. **E2E 报告更新**：更新 `testing/latest-e2e-report.md`（覆盖范围、核心发现、遗留问题）
4. **消费 pending-validations**：验证通过的条目标记 ✅ 并移入归档区
5. **一句话结论**：在 commit message 正文中记录 E2E 范围和核心结论（如 "E2E(trpg-web): 5 步正向流转 100%，回退路径 0%"）

> E2E 执行使用 `testing/benchmark-scenario.md` 定义的固定场景，保证跨版本可比性。

### E2E 后置处理流程

E2E 验证产生原始发现后，按以下流程处理：

```
E2E 执行完毕
    │
    ▼
① 提取问题清单
    从 E2E 过程中收集所有发现（失败、异常、反直觉行为）
    每条记录：现象、根因分析、影响范围
    │
    ▼
② 分类定性
    每条发现标记类别：
    · BUG — 逻辑错误、功能不符合设计（必须修复）
    · GAP — 设计假设与实际不符（必须修正设计或沉淀经验）
    · OBSERVATION — 值得记录但不需立即行动（仅沉淀经验）
    │
    ▼
③ 排序
    BUG 按影响度排序：
    · P0 — 流程阻断（状态机卡死、交付物丢失）→ 立即修复
    · P1 — 功能降级（降级路径失效、通信协议部分失效）→ 本轮修复
    · P2 — 体验/效率问题 → 记录到 backlog，不阻塞本轮
    GAP 全部在本轮处理（修正设计或沉淀经验）
    │
    ▼
④ 逐项修复（BUG + GAP）
    对每个 P0/P1 BUG 和每个 GAP：
    a. 修复代码/文档
    b. 检查 §6 影响范围表 — 联动更新受影响的文件
    c. 单独 commit（commit message 标注来源，如 "fix(框架): 修复xxx — 源自 E2E(项目名)"）
    │
    ▼
⑤ 经验沉淀
    对每条发现执行 §3 的三项自检：
    · 新的失败模式？→ 新增 L-编号
    · 验证了错误假设？→ 新增 L-编号
    · 工作方法可复用？→ 新增方法论 L-编号
    已有 L-编号覆盖的发现 → 更新复现次数和最后命中日期
    │
    ▼
⑥ 回归确认
    修复涉及 §3.1 触发条件中的变更类型（状态机、通信协议、Prompt 模板、路由）？
    · 是 → 需要在同一 E2E 项目中回归验证修复效果（不必全量重跑，只验证修复点）
    · 否 → 静态审查即可
    │
    ▼
⑦ 汇总 commit
    所有修复完成后，在最后一个 commit message 中附带 E2E 汇总：
    "E2E({项目名}): {覆盖范围}, {核心结论}, BUG={P0数}P0/{P1数}P1/{P2数}P2, GAP={数量}, L-{新增编号列表}"
```

> **防止链路断裂的关键点**：步骤④要求每个修复都检查 §6 影响范围表。这是 E2E 后置流程依赖的唯一外部机制——如果 §6 的表不完整，联动更新就会遗漏。因此每次新增框架文件时，必须同步更新 §6。

## 4. 独立架构评审（Stop Hook 自动触发）

> **本节属于 Layer B（开发 RedCap 自身）**。Layer A 的评审由状态机 `REVIEW_WORKING` 节点驱动，当 LLM 跳过 Review 直接进入 ALL_DONE 时，Layer A Stop Hook 会检测缺失并拉起新 Agent 兜底执行项目级 Review（`tools/redcap-layerA-review-fallback.sh`）。两层共享同一设计模式：Hook 100% 触发 + 新 Agent 生命周期保证认知能力（详见 L-15）。

**问题**：开发 Agent 在长对话末期注意力衰减，可能遗漏规范检查、文件联动、经验沉淀等收尾动作。即使 §3 写了自检清单，长任务末期的 LLM 也可能"忘记"执行。

**解法**：Layer 0（物理 Hook）+ 全新 Agent 生命周期。

- **触发机制**：Claude Code Stop Hook → `tools/redcap-on-stop-review.sh`
- **执行方式**：脚本提取 `git diff`，拉起一个全新的、无历史上下文污染的 Agent（`kimi -p` / `claude -p`）执行独立评审
- **评审维度**：Commit 规范、经验回顾、文件联动（§6 影响范围表）、内容质量、经验沉淀遗漏、设计完备性（§1.1 Pre-mortem 是否执行——含"不可行"判断和覆盖范围声明）
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
| 涉及 §3.1 触发类型的任何变更 | testing/pending-validations.md（登记待验证条目）|
| testing/benchmark-scenario.md | testing/pending-validations.md（验证矩阵变更可能影响待验证项的验证方法）|
| testing/latest-e2e-report.md | testing/pending-validations.md（报告产出后消费待验证条目）+ knowledge/lessons.md（经验沉淀）|

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
| 任务全部完成 | 删除文件 |

> 该文件已加入 `.gitignore`——它是临时过程状态，不应进入版本控制。

---

### 跨工具指令文件位置参考（经官方文档验证 2026-04）

| 工具 | 指令文件 | 有效路径 | 导入机制 |
|------|---------|---------|---------|
| VS Code Copilot | `.github/copilot-instructions.md` | 项目 `.github/` 下 | 无原生导入；使用 `read_file` 指令 |
| Claude Code | `CLAUDE.md` | `./CLAUDE.md` 或 `./.claude/CLAUDE.md` | `@file` 原生自动导入 |
| Gemini CLI | `GEMINI.md` | 项目根目录（及父目录层级） | `@file.md` 原生自动导入 |

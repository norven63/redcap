# RedCap — 架构总览与治理模型

> **一句话定义**：RedCap 是一个由 Loom 执行平面、Compass 自演化控制面、Prism 分析裁决平面与 References 共约层组成的多 Agent 软件工程框架。
>
> **阅读方式**：本文件负责解释“系统现在是如何设计的”；`redcap-knowledge/traces/architecture-capability-trace.yaml` 负责冻结旧能力锚点并承载后续 `旧架构 -> 新架构 -> runtime evidence` 的回归审查。

---

## 目录

- [1. 设计哲学](#1-设计哲学)
- [2. 三体分层与 authority chain](#2-三体分层与-authority-chain)
- [3. Loom — Layer A 执行平面](#3-loom--layer-a-执行平面)
- [4. Compass — Layer B 自演化控制面](#4-compass--layer-b-自演化控制面)
- [5. Runtime isolation、兼容桥与证明层](#5-runtime-isolation兼容桥与证明层)
- [6. Prism — 分析与裁决平面](#6-prism--分析与裁决平面)
- [7. References 共约层](#7-references-共约层)
- [8. 能力追踪与回归审查模型](#8-能力追踪与回归审查模型)

---

## 1. 设计哲学

RedCap 的架构不是“写一套文档给 Agent 看”，而是把关键边界变成**可重锚、可审计、可证明**的系统。五项元原则在当前架构中的落点如下：

| 原则 | 当前架构体现 |
| --- | --- |
| **角色分离** | Loom 的 Dispatcher 只调度；角色手册、Prompt 模板、Prism 视角、Compass 控制面各司其职 |
| **状态外部化** | `state.yaml`、`.dev-task.md`、runtime project state、Prism run state 都以外部文件持久化 |
| **确定性优先** | 关键闭环优先走 shell 脚本、Hook、task report、acceptance，而不是依赖模型“应该会记得” |
| **经验积累** | lessons、explore-notes、task report、trace matrix 共同承担“避免长任务漂移”的记忆层 |
| **层次清晰** | Loom 负责用户项目交付，Compass 负责 RedCap 自身演化，Prism 负责高风险分析，References 负责跨层共约 |

当前版本额外强调三条架构纪律：

1. **authority chain 必须显式**：谁是 canonical truth、谁是 derived state、谁只是 mirror，必须可说明、可检查。
2. **closure 必须物理可见**：review、task report、notify、cleanup 不能只存在于“应该发生”的叙述里。
3. **证明层必须独立存在**：文档说明不是完成，runtime evidence 与 acceptance harness 才是完成的物理证据。

---

## 2. 三体分层与 authority chain

### 2.1 三体分层总览

```text
RedCap
├── Loom        — Layer A 执行平面，负责把用户需求编织成代码与交付物
├── Compass     — Layer B 自演化控制面，负责 RedCap 自身开发、治理与闭环
├── Prism       — 分析与裁决平面，负责独立取样、对抗评审与多轮议事
└── References  — 共约层，沉淀跨层共享的协议、约束、模板与安全边界
```

四层关系不是“谁调用谁”的简单树状结构，而是：

- **Loom** 管理面向用户项目的状态机、Prompt 装配、交付物与 Hook。
- **Compass** 管理 RedCap 自身开发的 canonical ledger、PM Gate、anti-drift、hook 链与知识库。
- **Prism** 不直接取代 Loom/Compass 的 authority，只在高风险场景提供独立验证或议事能力。
- **References** 不拥有运行状态，但定义所有平面都必须遵守的最小共约。

### 2.2 authority chain 与 truth surfaces

RedCap 当前把状态面划分为三类：

| 表面 | 类型 | owner | 作用 | 约束 |
| --- | --- | --- | --- | --- |
| `loom/**/state.yaml` | canonical truth | Loom | Layer A 流程状态与回退依据 | 只能由 Dispatcher / Layer A 工具推进 |
| `.dev-task.md` | canonical truth | Compass | Layer B 需求、slice、边界、原始输入、已确认需求 | 宿主面板不得替代它 |
| `references/backlogs/*.json` | canonical long-route truth | References | 跨会话长期路线、阶段状态、当前焦点与证据锚点 | 不替代 `.dev-task.md`；当前任务必须显式锚定到具体 backlog 条目 |
| `references/spec-registry.json` + `references/spec-lifecycle-policy.json` | canonical governance index | References | 给 `compass/docs/specs/*.md` / `compass/docs/archive/specs/*.md` 做机器登记与生命周期约束，说明每份 spec 的角色、状态、归档位置与执行链绑定 | 用于治理和校验，不把 spec 重新抬成 runtime authority |
| `prism` run state | run-scoped truth | Prism | 每次 Prism 运行的 run_id、registry、collect、resolve/archive 记录 | 以 run 为隔离边界 |
| runtime project state | derived state | runtime tools | session/capability/binding/process claim、compat、audit、pending closure、closure-ledger | 不能反向篡改 canonical truth |
| 宿主 `plan.md` / workboard | mirror state | host surface | 展示当前 pointer/hash，辅助长任务导航 | **mirror-only** |
| 宿主通用 skill（brainstorming / planning / visual） | overlay protocol | host skill | 提供分解、表达、展示与设计建议 | **advisory-only**，不得覆盖 `.dev-task.md`、PM Gate、自主执行授权，也不得默认升级成人工审批门；其自带的下游 handoff（如 writing-plans）也不能反向接管 RedCap-native 主流程 |
| task report / acceptance report | closure evidence | reports | 证明“某个闭环真的发生了” | 缺失时不得伪装成完成 |

### 2.2.1 artifact lifecycle 分类

文件不只按“内容主题”分，还必须按 **authority / 生命周期 / 共享必要性** 分层：

| 类别 | 典型载体 | 是否进 git | 说明 |
| --- | --- | --- | --- |
| **repo-tracked canonical / evidence** | `ARCHITECTURE.md`、`references/**`、`compass/docs/specs/**`、`compass/docs/traces/**`、`compass/docs/task-reports/**`、`prism/reports/**`、`loom/test-reports/latest-e2e-report.md`、`loom/test-reports/pending-validations.md` | 是 | 这些文件要么是正式规范，要么是跨会话共享的历史证据，必须可审计、可考古 |
| **session-isolated process state** | `.dev-task.md`、`prism/runs/**`、宿主 `plan.md` / workboard mirror | 否 | 它们服务于当前会话或当前机器的推进，不应伪装成共享真相 |
| **local-only host assets** | `.env.local`、`compass/tools/feishu-config.json`、`compass/.workflow/agent-registry.yaml`、宿主 CLI / hook 配置、机型/路径探测缓存 | 否 | 它们绑定本地环境、凭证或宿主能力，不适合作为 repo 历史的一部分 |
| **temporary runtime outputs** | `/tmp/redcap-*`、临时 prompt / review 输出、`__pycache__/` | 否 | 只为当前执行服务，任务结束后应清理或自动覆盖 |

这也是本次 docs 重整的基本原则：**不要把 process state 塞进 history 层，也不要把历史证据误删成“临时文件”。**

当前这条边界已经形成 **分类器 + 提交前闸门 + 收尾审计** 三层链路：`compass/tools/redcap-artifact-classifier.sh` 统一按 docs 根目录索引与生命周期规则给路径分类；仓库内 `.githooks/pre-commit` 通过 `compass/tools/redcap-artifact-lifecycle-check.sh ... pre-commit` 在提交前直接拦住 staged set 里的 session-isolated / local-only / temporary artifact，并在 repo-tracked 与非 repo-tracked 产物混提时显式报出 mixed-lifecycle；`stop-review`、`redcap-on-complete.sh` 与 `session-end` 继续审计整个 commit 区间里所有曾进入历史的路径，而不是只看最终 net diff。

### 2.2.2 `docs / knowledge / continuity assets` 的职责分层

更完整的运行时记忆分层与 Layer B 生命周期定义，见：

- [references/runtime-memory-architecture.md](references/runtime-memory-architecture.md)
- [compass/knowledge/runtime-memory-architecture.md](compass/knowledge/runtime-memory-architecture.md)

文件放哪一层，不取决于“看起来像不像记录”，而取决于它承担的是哪种记忆职责：

| 层 | 典型载体 | 职责 | 是否可直接当作长期 evidence |
| --- | --- | --- | --- |
| **frozen evidence** | `compass/docs/specs/**`、`research/**`、`traces/**`、`task-reports/**` | 冻结后的设计、审计、研究与 closure 证据 | 是 |
| **canonical long-route truth** | `references/backlogs/*.json` | 机器可读的长期路线、阶段状态、当前焦点与人类说明锚点 | 是，但只负责长期路线，不接管 live task |
| **live knowledge** | `compass/knowledge/lessons.md`、`host-reliability.md`、`hooks-*.md`、模型矩阵 | 活的经验、heuristics、宿主差异与操作知识 | 只作为规则与经验，不直接替代 closure evidence |
| **continuity assets** | `.dev-task.md`、`compass/knowledge/explore-notes.md`、宿主 `plan.md` / workboard、导入的 session artifacts | 防偏航、防上下文稀释、断点恢复、显式继承 | 否 |

因此：

1. `compass/docs/` 与 `compass/knowledge/` 是**平级不同职**，不是父子关系。
2. continuity assets 不是“第三个 docs”，而是围绕 canonical truth 运行的连续性状态链。
3. backlog 这类“长期路线”如果要进入执行保障，机器权威应放在 `references/backlogs/*.json`，给人看的解释继续留在 `compass/docs/specs/**`；不要反过来把 spec 文档当运行时 authority。
4. spec 文档若想继续保留在 `compass/docs/specs/**`，必须在 `references/spec-registry.json` 里登记自己的角色、当前状态和配套控制面；否则就只是匿名材料，应迁出或补登记。
5. 若某类资产要从 continuity 层升级为 evidence，必须经过**显式发布**，而不是因为“写成了 markdown”就自动变成 docs。
6. `compass/docs/index.yaml` 负责冻结 docs collection 的 retention / archive 规则，避免 docs 根目录再次回到大杂烩状态。
7. `compass/CONTRIBUTING.core.md` 是**首读压缩层**，不是第二权威；它只负责把“新会话立刻必须遵守的规则”压到小体积入口里，权威解释仍回到 `compass/CONTRIBUTING.md`。

### 2.3 host-agent interop governance

多会话隔离之后，RedCap 显式承认宿主 Agent 与 RedCap-native 机制之间存在长期张力，因此当前采用**控制面收口型治理**：

| 治理规则 | 含义 |
| --- | --- |
| **mirror-only** | 宿主 `plan.md` / workboard 只能镜像 canonical pointer，不得承载 Layer B 执行真相 |
| **re-anchor first** | 新会话进入时，先恢复 soul / canonical pointer / runtime binding，再谈推进动作 |
| **fail-closed on RedCap state** | 当 authority 不明确或 closure 未闭合时，RedCap 自有状态不得被静默推进为“已完成” |
| **evidence-only audit** | project-shared interop audit 只记录证据，不反向长成第二个 authority |
| **strong-hook vs weak-hook** | 强 Hook 宿主走实时 closure transaction；弱 Hook / 无 Hook 宿主通过 pending closure 做 deferred reconcile |
| **overlay-skill subordinate** | 宿主通用 skill 只能提供建议流程；若与 RedCap-native PM Gate / autonomy 冲突，必须让位给 RedCap 控制面 |

当前 interop contract 的核心不是“阻止宿主存在”，而是**阻止宿主表面越权成为 RedCap 的真相源**。

这也意味着，RedCap 的执行保障不能再被当成单一强度的“统一护盾”。当前正式采用三档口径：

1. **物理强保障**：脚本、validator、closure chain、Hook 已直接接管触发点。
2. **宿主耦合保障**：RedCap 已有接线，但是否成立取决于宿主能力矩阵。
3. **人工/宿主边界保障**：规则已被登记、审计、诊断，但当前没有 repo-owned reply veto 一类的物理拦截点。

具体解释见 [execution-guarantee-tiers.md](references/execution-guarantee-tiers.md)；机器权威仍以 `references/execution-guarantees.json` 为准。

这里还要额外加一条资产边界：**共享宿主 skill 是 carrier-owned overlay，不是 RedCap 的 patch surface**。  
RedCap 可以消费它们的能力，但不能把“修改宿主 shared skill 原始文件”当成自身能力成立的前提；若不改宿主 skill 就无法稳定工作，该路径只能被标记为 **degraded / unsupported overlay**。

同时，宿主入口文件需要拆成两类看待，也就是 RedCap 的 **carrier-required shims** 与本地可选 carrier shim：

- `CLAUDE.md`、`GEMINI.md`、`.github/copilot-instructions.md` 是 **repo-tracked carrier shims**；
- `AGENTS.md` 是 **Codex 本地 carrier shim**，可以存在于工作区，但当前不再被 RedCap 当成 fresh clone 必备输入。

这些 shims 的共同原则仍然是：

- 它们分名存在，是因为各宿主只会自动加载自己的固定文件名；
- 它们的职责只是把会话导向同一套 `soul + CONTRIBUTING.core + current-status + index` 首读链；
- 它们不得长成第二份规范正文，也不得各自维护不同版本的规则。

---

## 3. Loom — Layer A 执行平面

Loom 负责用户项目从需求到交付的执行闭环。它不接管 Compass 的自演化控制面，但会复用 References 共约与部分可靠性原语。

### 3.1 Dispatcher 事件循环

Dispatcher 是纯调度器，不写业务代码、不替角色做设计判断。它负责：

1. 读取 `state.yaml` 与 `pending_actions`
2. 按状态机与路由规则选择下一角色和 Agent CLI
3. 组装 Prompt 模板并发起调用
4. 读取 `__redcap_status` / deliverables / outbox
5. 校验交付物完整性并触发 Hook
6. 原子推进状态与待办

这保证了“流程推进”与“角色产出”解耦：角色负责交付物，Dispatcher 负责状态。

### 3.2 状态机

Layer A 主状态机以 `INIT -> PM -> ARCH -> DEV -> QA -> REVIEW -> ALL_DONE` 为主线，并显式支持：

- `PAUSED`：等待用户回复
- `SCAN_WORKING / SCAN_DONE`：已有项目纳管与增量扫描
- `need_revision`：按 `root_cause=code|design|requirement` 精准回退
- 多次失败后的级联升级：先 PM/L1，再用户/L2

这里的关键不是状态数量，而是**回退责任明确**：问题属于谁，就退回谁。

### 3.3 通信协议

Loom 与子 Agent 的主通信方式仍然是**文件系统协定**：

- 主通道：`{role}/outbox/__redcap_status.json`
- 兼容通道：从回复文本中提取 JSON
- 兜底通道：读取 `.workflow/last-result.json`

`__redcap_status` 至少负责表达：

- `status`
- `summary`
- `deliverables`
- `lesson`（可选）
- `escalation` / `revision`（按状态必填）

其设计目标不是“让模型输出漂亮 JSON”，而是让 Dispatcher 有一个**可以做物理校验**的协议对象。

### 3.4 角色系统与 Prompt 装配

Loom 保留五角色分工：

| 角色 | 职责 |
| --- | --- |
| PM | 澄清需求、锁定范围 |
| ARCH | 设计方案、画边界 |
| DEV | 实现代码 |
| QA | 验证与根因归类 |
| REVIEW | 总体验收与审查 |

Prompt 装配遵循“模板 + 场景变量 + 恢复态注入”的方式，至少覆盖：

- 全新需求
- 中断恢复
- QA 回退
- REVIEW 回退
- 迭代开发

这保证角色身份与场景上下文不被混写进单个巨型 Prompt。

### 3.5 模型路由

RedCap 的路由不是写死到单一模型，而是通过：

- agent registry
- capability matrix
- 角色适配度
- fallback 链

动态决定实际执行者。Reviewer 还允许跨家族加权，以增加独立性。  
这一层的目标是**把“当前机子上真正可用的工具”与“理论上最适配的模型”联合建模**。

### 3.6 可靠性工程

Loom 的可靠性工程面向“长任务 + 宿主差异 + LLM 遗忘”三类问题，当前主要由四类机制组成：

| 机制 | 作用 |
| --- | --- |
| **Hook / shell 脚本** | 把关键副作用从对话记忆中拿出来 |
| **reload rules** | 在关键检查点重读规则，抵抗上下文压缩 |
| **pending_actions 原子写入** | 防止“状态更新了，但后续动作忘了执行” |
| **fallback / degraded 路径** | 在宿主能力不足或会话恢复异常时，保留可恢复性而不是伪成功 |
| **execution guarantees** | 用 `references/execution-guarantees.json` 登记哪些规则必须有复活、Hook、validator 或 manual-only 保障，避免规则只停在自然语言文档里 |

其中 `pending_actions` 的原则仍然成立：**状态推进与后续动作必须同批次固化**，否则就会产生递归遗忘。

---

## 4. Compass — Layer B 自演化控制面

Compass 是 RedCap 的自我开发平面。这里管理的不是用户项目，而是框架本身的身份、边界、任务、治理与闭环。

### 4.1 框架自身开发流程

Layer B 的核心执行序列是：

1. 读取 `compass/soul.md`，恢复人格与协作默契
2. 读取 `compass/CONTRIBUTING.md` 与 `compass/knowledge/lessons.md`
3. 恢复 `.dev-task.md`、plan mirror 与最近工作停点
4. PM Gate 锁定需求，再进入实现
5. 变更后执行影响范围检查、任务报告、棱镜独立验收，再交给统一 closeout runtime 完成通知与收尾

Layer B **不走 Layer A 那种单一 `state.yaml` FSM**，但它并不是“无状态控制面”。
当前 Layer B 采用的是**分布式控制面生命周期**：由 `.dev-task.md`、PM Gate、
anti-drift、stop-review、pending closure、closure-ledger 与 session-end 共同表达
状态与转移。正式定义见 [references/runtime-memory-architecture.md](references/runtime-memory-architecture.md)。

### 4.2 PM Gate（需求确认门）

PM Gate 是 Layer B 的第一道强约束，核心由两段组成：

- **原始输入**：逐字固化，禁止概括改写
- **已确认需求**：经过澄清和用户确认后的执行依据

执行期要求：

1. 没有明确确认，不进入实现
2. 每次只追一个澄清点，避免需求同时漂移
3. 执行前重读对应 Q，不把记忆当真相
4. 完成后要能把结果对回已确认需求
5. 宿主通用 skill 的澄清/审批循环只能作为建议；若已满足自主执行条件，必须由 RedCap-native PM Gate 内化吸收，而不是重新 ask_user

### 4.3 Layer B canonical ledger 与 anti-drift 控制面

`.dev-task.md` 是 Layer B 的 canonical ledger。围绕它已经形成一套物理控制面：

| 资产 | 职责 |
| --- | --- |
| `redcap-dev-task.sh` | 解析 canonical metadata 与已确认需求 |
| `redcap-pm-gate-check.sh` | 对 `.dev-task.md` 执行 session-start / stop-review / session-end 级 gate |
| `redcap-drift-check.sh` | 检查 active_slice、允许修改范围、authority 漂移 |
| `redcap-host-workboard-sync.sh` | 仅同步 pointer/hash 到宿主面板，不提升宿主 authority |

当前 Layer B 的控制面不再依赖“Agent 应该记得当前在做哪一刀”，而是依赖
**显式 metadata + gate 脚本 + drift 审计**。`.dev-task.md` 只是其中一个真相源，
不是全部生命周期本身；完整状态链见 [references/runtime-memory-architecture.md](references/runtime-memory-architecture.md)。

### 4.4 宿主 workboard mirror-only 边界

宿主 `plan.md` / workboard 的职责只有两个：

1. 展示当前 `task_id / active_slice / confirmed_hash`
2. 帮助宿主界面在长任务中不丢导航

它们**不能**：

- 代替 `.dev-task.md` 承载执行真相
- 擅自修改 top goal 或 slice 含义
- 让宿主自己的 todo 面板凌驾于 Layer B canonical ledger 之上

这条边界是防 authority inversion 的第一道隔离带。

但 mirror-only 不等于“只能显示 pointer”。在当前实现里，宿主 workboard 还会追加一块 **Session Mirror**：

- `session_handle`
- `runtime_session_id`
- `session_binding_key`
- 当前 `task_id / confirmed_hash`
- `continuity_authority`
- `isolation_mode`（`full` / `degraded` / `unsupported`）
- `resume_gate_reason / resume_gate_profile / resume_gate_evidence`
- continuity_state（`fresh-session` / `self-recorded` / `import-suggested` / `imported`）
- `import_protocol / next_action`
- `import_ready_signal / import_ready_summary / import_success_summary`（`blocked-no-runtime` / `not-needed-own-record` / `not-ready-no-compatible-source` / `ready` / `completed`）

这块信息仍然只是 mirror，不会反向成为 authority；真正的 continuity authority 现在先由 `redcap-session-continuity.sh` 发布到 `compass/.runtime/sessions/<runtime_session_id>/manifest.yaml` / `provenance.yaml`，然后再把结果渲染回宿主 workboard。它存在的目的，是让新会话进入时能**看见**自己是否已有连续性记录、是否存在兼容历史会话、当前是否 ready to import，以及导入完成后的一句话摘要。

同理，宿主侧的通用 brainstorming / planning / visual skill 也只能是 **advisory overlay**：它们可以帮助拆解问题、组织设计表达，但不能重开已锁定 tranche，不能把可自治决策升级为默认 ask_user / user approval，也不能替代 RedCap-native PM Gate 的最终锁定动作。

### 4.5 书记协议（Scribe Protocol）

书记协议覆盖 PM Gate 之前的探讨阶段。它解决的不是“需求已锁定后的执行漂移”，而是“方向尚未确定时的讨论蒸发”。

满足以下任一条件即触发：

- 同主题连续多轮讨论仍无正式记录
- 存在多个互斥选项
- 用户明确指出分歧或风险预警

记录载体是 `compass/knowledge/explore-notes.md`。  
当 PM Gate 真正开始时，书记笔记是前情底稿，不是可忽略的“聊天记录”。

### 4.6 指挥棒（Baton）

Baton 是 Layer B 的调度能力。它与 Loom/Dispatcher 共享一些调度原语，但职责不同：

| Dispatcher | Baton |
| --- | --- |
| 固定角色序列 | 自由编排、动态任务图 |
| 面向 Layer A 交付 | 面向 Layer B 治理、裂变、外包 |
| 状态机驱动 | 条件分支与并行聚合驱动 |

Baton 主要承担三类能力：

- **并行裂变**：将无耦合研究任务并发拆开
- **条件分支**：根据 Prism 或运行结果决定下一步
- **Skill 外包**：通过文件边界把子任务委托给专精能力

### 4.7 Hook 基础设施

RedCap 当前存在两套 Hook 层：

| 层 | 面向对象 | 典型触发点 | 目标 |
| --- | --- | --- | --- |
| **Layer A Hook** | 用户项目 | SessionStart / Stop / SessionEnd / on_ALL_DONE | 保护用户项目交付闭环 |
| **Layer B Hook** | RedCap 自身 | SessionStart / InstructionsLoaded / Stop / SessionEnd | 保护框架演化闭环 |

不同宿主的 Hook 能力并不一致，因此架构上明确区分：

- **强 Hook 宿主**：可在 Stop / SessionEnd 实时完成 closure transaction
- **弱 Hook / 无 Hook 宿主**：必须通过补偿式 contract 把缺口延续到下一次 re-anchor

### 4.8 closure transaction 与任务报告物理审计

Layer B 的“完成”不是一句自然语言，而是一个 closure transaction。当前至少包括：

1. PM Gate / anti-drift 审计
2. stop-review 或独立评审兜底
3. task report 按模板登记与校验
4. `closeout runtime` 核对承诺账本、棱镜验收、生成 summary / receipt、必要时执行 rescue audit
5. 飞书通知 / 告警
6. session-end cleanup

本轮治理之后，这条链新增了显式的 **pending closure obligation** 与 **closure ledger**：

- `redcap-interop-governance.sh`：统一维护 `audit/`、`pending-closure/`、`closure-ledger/` 三类治理状态；其中 `closure-ledger/` 是 append-only 事务日志，`pending-closure/` 是当前尚未清偿的义务
- `redcap-task-report-register.sh`：报告在 **process claim 可用且登记成功** 时创建 pending closure；若 claim 缺失则记录 degraded mode 并拒绝注册
- `redcap-task-report-check.sh`：可从 pending closure 回读 `artifact_path`，支持无新 diff 的补偿式 reconcile；并强制检查报告开头摘要与术语对照节是否存在
- `redcap-on-complete.sh`：对 RedCap 自身 on-complete fail-closed 校验 commit proof / task report / artifact lifecycle，并把关键阶段追加到 closure ledger
- `redcap-layerB-session-end.sh`：成功则清 obligation 并记账；失败或缺 claim 则把缺口重新写回 pending closure，并显式记录 blocked redlines
- `redcap-layerB-session-start.sh`：在成功 re-anchor 后以 advisory 方式触发 pending closure auto-reconcile；它负责记录/尝试消费确定性 blocker，但不把 SessionStart 变成新的 blocking gate

在此基础上，Layer B 终态现在新增了一个**统一 closeout runtime**：

- `redcap-layerb-closeout-runtime.py/.sh`：把 Agent 自追加承诺、`redcap-on-complete.sh`、`redcap-layerB-session-end.sh`、summary、receipt 与 rescue audit 收到同一条 runtime 里
- `redcap-prism-acceptance-check.sh/.py`：把棱镜验收变成 Layer B completed 的默认前置门，没有有效验收就不能正式完成
- `closeout-cap.sh`：仓库根目录短入口。以后 Layer B 的人类/Agent 收尾优先走这里，而不是自己拼接 on-complete / session-end
- `promise-ledger`：从 `.dev-task.md` 的 `## 执行承诺账本` 派生，专门锁住“用户原始需求之外，Agent 自己后来承诺还要做的事”
- `redcap-diagnose.sh`：当前已接上一条 diagnose-rescue 强入口；一旦检测到 terminal closeout 已开始但 receipt 缺失，就会优先尝试 `audit-open`
- `closeout-receipt`：machine-readable 终态收据，证明 closeout 不是口头完成
- `closeout-audit`：receipt 丢失或终态半闭环时，负责补写 receipt 或补写 blocker 的 rescue 证据

这条 runtime 的含义不是“又多了一套状态机”，而是：**把 Layer B 终态收口从多脚本分散执行，升级成由棱镜验收 + receipt 共同约束的统一闭环。**

与此同时，task report 本身不再只是“归档路径”：

- 模板必须显式提供 `当前已完成 / 上一步完成的是 / 下一步计划做的是 / 整体计划脉络图与当前位置`
- 模板必须显式提供 `术语对照（按文件/功能解释）`，避免任务报告再次退回黑话堆叠
- `redcap-notify-format.sh` 会从报告中优先抽取这四段，直接进入 stdout 收尾摘要与飞书通知；`人工审核要点 / 人工验证项` 则作为补充提醒
- 这样 Norven 在不打开完整报告时，也能先看到真正需要介入或关注的点

这意味着弱宿主即使没有完整 Hook，也不能再把“收尾链没发生”静默吞掉。

### 4.9 经验库机制

经验库仍然分两层：

- `lessons.md`：活跃层，保持短小、常驻启动上下文
- `lessons-archive.md`：归档层，按需检索
- `shared-knowledge/`：未来独立团队共享库的本地模板，负责按用户隔离、append-only 沉淀、索引优先读取和 exact duplicate 拒绝

高影响 lesson 不允许自动淡出。  
它的职责不是“做知识管理”，而是**把曾经出现过的失败模式保留为下一次执行的边界条件**。

shared knowledge 的职责不同：它不是当前任务真相源，也不默认进入启动上下文；它是团队长期沉淀的候选外部库，只有索引命中且任务确实需要证据时才读取正文。

### 4.10 soul / revive / re-anchor

`compass/soul.md`、`CLAUDE.md`、`GEMINI.md`、`.github/copilot-instructions.md` 共同构成 RedCap 的“身份恢复层”。

这里的核心不是人格化表达，而是三个工程含义：

1. **revive**：新会话先恢复协作方式与原则
2. **re-anchor**：把身份恢复与 canonical ledger / runtime binding 绑定起来
3. **anti-drift**：避免“像 RedCap，但其实已脱离 RedCap 控制面”的伪连续性

---

## 5. Runtime isolation、兼容桥与证明层

### 5.1 runtime session / capability / binding / process claim

多会话隔离主线已经把 runtime 原语正式沉淀为系统级能力：

| 原语 | 含义 |
| --- | --- |
| `session_handle` | 宿主工作区中的可读会话别名，用于在 workboard / continuity import 中定位当前宿主会话 |
| `runtime_session_id` | 当前会话在 runtime 层的唯一标识 |
| `capability` | 当前附着的宿主能力/上下文能力类型 |
| `binding_key` | 宿主会话与 runtime project state 的绑定键 |
| `process claim` | 当前进程对 runtime state 的临时占有与恢复依据 |

这四件套共同解决：

- 同仓库多会话并存
- 同宿主 / 跨宿主恢复
- Hook 与脚本之间的状态接力
- 运行时“谁在写这份 derived state”的可追踪性

其中：

- `session_handle` 解决“人类如何在 host workboard 与导入清单里识别这是哪一个会话”
- `binding_key` 解决“恢复后的同一逻辑会话如何重新绑回原 runtime 目录”
- `task metadata`（`task_id / top_goal / confirmed_hash`）解决“导入时如何判断两个会话是否兼容”
- `runtime_session_id + capability + process claim` 解决“真正读写 session 私有态时，谁被允许附着到这份 runtime state”

### 5.1.1 repo-owned continuity manifest 与 explicit import protocol

RedCap 当前把“最近会话继承”落成了**显式导入协议**，而不是默认自动恢复：

1. `redcap-layerB-session-start.sh` 会先调用 `redcap-session-resume-gate.sh`，按 `references/host-session-capability-matrix.json` 把当前宿主判定到 `full / degraded / unsupported`
2. 只有 `full` 才允许 attach/create runtime session；`degraded / unsupported` 只能继续 safe advisory sync
3. SessionStart 再同步 canonical pointer，然后由 `redcap-session-continuity.sh` 把当前会话 continuity authority 发布到 `compass/.runtime/sessions/<runtime_session_id>/manifest.yaml`
4. manifest 同目录还会维护 `provenance.yaml`；跨会话导入时，再追加 `compass/.runtime/continuity/import-registry.jsonl` 与 `audit-log.jsonl`
5. 宿主 workboard 的 `Session Mirror` 只读取这些 repo-local continuity 账本，不再以 sibling `plan.md` 或 `files/imported-sessions/*/metadata.json` 反向充当 authority
6. `continuity_state` 与 `isolation_mode` 分字段维护：前者回答“有没有连续性记录/导入建议”，后者回答“当前宿主是否具备 full isolation 能力”
7. 若当前缺少**经过 capability 校验**的 `runtime_session_id`，Session Mirror 只能停在 `fresh-session` 并显式标记 `continuity_authority: degraded-no-runtime-manifest`；此时 `isolation_mode` 只能来自 resume gate，不得伪造 `self-recorded / import-suggested / imported`
8. repo-local manifest 只能描述 continuity authority，不能反向“复活”缺失的 active runtime binding；这里的 verified runtime binding 指当前 live process claim 重新校验通过的 binding，而不是 shell 里残留的导出环境变量。`sync` 在没有 verified runtime binding 时只能降级输出 no-runtime mirror，而 `import` 则必须同时满足：当前 verified runtime binding 存在、target workboard 的 Session Mirror runtime 与之匹配、target manifest 已存在
9. `sync` 会把导入建议显式发布成 `import_ready_signal / import_ready_summary`；真正导入时，`redcap-session-continuity.sh import` 还会输出一段 machine-readable success summary
10. `import` 的 source authority 优先来自 source manifest，而不是 source workboard pointer；source manifest 必须是 `continuity_state=self-recorded` 的 self-recorded source，带有完整 task metadata 且 `own_record_present=1`，同时 source 当前 Session Mirror/runtime 也必须仍绑定到这份 manifest。缺失 source manifest、缺关键 metadata、`continuity_state!=self-recorded`、`own_record_present!=1`、source 当前 mirror/runtime 已退化失绑，或 source/target task metadata mismatch 时都必须 fail-closed
11. cross-host compatibility 没有第二套隐藏协议：**唯一 host-specific 输入**是 `host-session-capability-matrix.json` 对各宿主给出的 `full / degraded / unsupported` 判定与恢复路径；一旦 source/target 两侧都拿到 verified runtime binding 并满足上述 preconditions，后续 continuity manifest / explicit import contract 在 claude、gemini、copilot 等受支持宿主之间保持同一套 host-agnostic 语义。也就是说，cross-host import 只是“两个 full session 之间执行同一套 explicit import protocol”，而不是 per-host special case
12. 真正导入时，`redcap-session-continuity.sh import` 只复制 continuity artifacts：
    - `plan.md` 快照
    - `files/`（排除二次嵌套的 imported-sessions）
    - `checkpoints/`
13. 源会话目录保持原样保留；目标会话把导入内容放进 `files/imported-sessions/<source_handle>/`
14. 导入完成后，target manifest / provenance 会先更新，再由宿主 workboard 把 continuity_state 渲染成 `imported`，并记录来源 session handle / source plan / import root

这条协议的重点不是“方便”，而是**在不偷换 authority 的前提下，为新会话提供可见、可审计、可保留来源的 continuity bridge**。

### 5.2 safe degraded / compat bridge / legacy quarantine

当 runtime claim 缺失、宿主 Hook 不完整、旧标记文件残留或兼容链尚未迁移完时，系统允许进入**safe degraded**，但不允许伪造成功。

当前成熟策略包括：

- 记录 degraded mode 事件
- compat bridge 保持旧路径可恢复
- legacy hit 被显式记录
- 旧状态文件在安全路径中 quarantine，而不是直接静默覆盖

此外，当前 closure obligation 的清理不是“谁先跑到谁算数”，而是走**task-scoped lock + compare-and-swap(CAS) 风格保护**：

- session-end 先获取 pending-closure lock
- 只在 `updated_at` 仍与自己最初读取到的一致时，才允许清 obligation
- 若另一个更新过的新会话已经改写 obligation，旧会话的清理会被拒绝

所以你此前提到的“CSA 锁”，在当前架构里更准确的说法是：**CAS 风格的状态比对 + task-scoped lock**。它的目标不是做系统级互斥玩具，而是防止旧会话把新义务误删掉。

这条线的目标是：**允许降级，但降级也必须可见、可回收、可审计**。

### 5.3 acceptance harness 作为物理证明层

本轮多会话隔离重构之后，acceptance harness 已从“验证脚本”升级为正式架构能力：

- 它覆盖 Loom / Compass / Prism 三条主线
- 它验证的不只是功能存在，还验证隔离、恢复、compat、degraded 与 report/register claim
- 它是区分“文档里说有”与“系统里真的跑通”的证据层

因此，RedCap 当前把 acceptance 定义为**架构证明层**，而不是补充材料。

---

## 6. Prism — 分析与裁决平面

Prism 负责高风险分析，不接管 Loom 或 Compass 的 canonical truth，但必须有自己的 run-scoped truth 与隔离边界。

### 6.1 两族协议

Prism 当前保留两类协议：

| 协议族 | 场景 | 目标 |
| --- | --- | --- |
| **独立取样** | explore / redteam / test | 在结论互不污染的前提下收集多个独立视角 |
| **议事协议** | council | 在多轮交互中逐步收敛复杂分歧 |

它们的差异不是“提示词不同”，而是**信息是否允许跨轮共享**。

### 6.2 run-scoped truth

Prism 当前已经不仅是“发几次子任务”，而是形成了 run-scoped truth：

- run_id
- registry
- collect record
- resolve handle
- archive check

这让一次 Prism 运行本身成为可恢复、可审计、可归档的独立实体，而不是对话里的临时分支。

### 6.3 Dispatch Firewall

独立取样协议依赖 Dispatch Firewall：

- agent 之间不得互看中间结论
- collect 之前不得串线
- adjudication 必须在冻结过的 frame 上进行
- dispatch 之前必须通过 `prism-availability` 可用性清单；清单 1 小时内有效，过期先真实嗅探
- roster 必须写明 `provider&model:role`，让本地 CLI 可用性和模型能力画像不再混成一团

这是一条显式的架构声明，而不是实现细节。  
如果后续实现出现折衷，也必须在 capability trace 中显式标注，而不是在重写文档时抹掉。

`prism-availability` 只证明“这个 provider 当前可被 RedCap-owned headless 调度使用”，不证明“这个模型一定适合当前问题”。模型适配仍由能力画像、任务风险和 Prism 角色设计决定。

### 6.4 Skill-Delegation 模式

Prism 与 Cap 都可以通过 Skill-Delegation 协议把子任务外包给专精能力。其关键不在“谁来做”，而在**边界必须文件化**：

- 请求文件
- 输入路径
- 结果文件
- blocked / timeout 透传
- resume/continue 协议

这使 skill 外包仍然处于 RedCap-native delegation boundary 内，而不是退回宿主黑箱。

### 6.5 多轮接力协议

Prism 的多轮接力明确区分不同宿主的 resume 能力。  
目标不是统一所有 CLI 的参数，而是统一“**一轮运行如何在下一轮被接续**”这件事。

当前要求至少做到：

- 首轮启动与续接方式可区分
- session_id / run_id 有显式登记
- 恢复时带摘要，而不是把旧上下文当成默认存在

---

## 7. References 共约层

### 7.1 References 共约层

References 是三体共享的协议层，承载：

- 安全规则
- 代码规范
- commit 规范
- 通信协议
- hook 规范
- agent 约束
- task report 模板

它不拥有流程状态，但决定所有平面最低必须遵守什么。

### 7.2 关键协议文件索引

| 文件/目录 | 作用 |
| --- | --- |
| `SKILL.md` | Loom/Dispatcher 入口协议 |
| `compass/CONTRIBUTING.md` | Layer B 唯一权威规范 |
| `compass/soul.md` | 人格连续性与 revive 基线 |
| `redcap-knowledge/traces/architecture-capability-trace.yaml` | 旧能力锚点与全量 trace matrix |
| `loom/dispatcher/state-machine.md` | Layer A 状态转移定义 |
| `loom/dispatcher/agent-adapters.md` | 路由、适配、会话接力 |
| `prism/protocol.md` | Prism 协议全文 |
| `references/communication-protocol.md` | `__redcap_status` 完整协议 |
| `references/execution-guarantees.json` | 执行保障目录，说明哪些规则必须被脚本、Hook、validator 或人工边界保护 |
| `references/task-report-template.md` | 任务完成报告模板 |
| `compass/knowledge/lessons.md` | 活跃经验库 |

### 7.3 设计决策速查

| 维度 | 当前决策 |
| --- | --- |
| 架构分层 | Loom / Compass / Prism / References 四层协同 |
| Layer B 真相源 | `.dev-task.md` 是 canonical ledger |
| 宿主面板 | mirror-only，不承载执行真相 |
| host/native 治理 | 控制面收口型治理，fail-closed on RedCap state |
| runtime 隔离 | session/capability/binding/process claim 四件套 |
| closure 定义 | review + drift + task-report + notify + cleanup 的事务闭环 |
| 弱宿主策略 | pending closure + deferred reconcile |
| degraded 策略 | safe degraded / compat bridge / quarantine，可降级但不可伪成功 |
| Prism 隔离 | Dispatch Firewall + run-scoped truth |
| 证明层 | acceptance harness + task report + runtime audit |

---

## 8. 能力追踪与回归审查模型

本文件不再单独承担“列出所有能力然后希望读者自己脑补是否还在”的职责。  
从本版本开始，架构审查采用**文档 + trace matrix + runtime evidence** 三件套：

1. `ARCHITECTURE.md`：解释当前系统为什么这样设计
2. `redcap-knowledge/traces/architecture-capability-trace.yaml`：冻结旧能力锚点，映射新架构锚点，记录 runtime evidence
3. task report / acceptance / audit logs：提供物理证据

当前 trace matrix 至少覆盖以下能力簇：

| 能力簇 | 代表 trace ids | 主要证据面 |
| --- | --- | --- |
| 架构总纲 | `design-philosophy`, `triad-overview` | 本文件、设计原则、trace matrix |
| Loom 执行链 | `loom-dispatcher-event-loop`, `loom-state-machine`, `loom-communication-protocol`, `loom-role-prompt-assembly`, `loom-model-routing`, `loom-reliability-engineering` | Loom 文档、脚本、状态机、E2E |
| Compass 控制面 | `compass-framework-dev-flow`, `compass-pm-gate`, `compass-scribe-protocol`, `compass-baton`, `compass-hook-infrastructure`, `compass-lessons-system` | CONTRIBUTING、knowledge、tools |
| Layer B 新治理资产 | `control-plane-canonical-ledger`, `host-workboard-mirror-only`, `closure-transaction-and-task-report-audit`, `soul-revive-reanchor` | `.dev-task.md`、pm-gate、drift-check、interop helper、task reports |
| 多会话隔离基础设施 | `runtime-session-isolation-model`, `safe-degraded-and-compat-bridge`, `acceptance-harness-as-proof` | runtime-state、acceptance harness、主线任务报告 |
| Prism 能力族 | `prism-two-family-protocol`, `prism-run-scoped-truth`, `prism-dispatch-firewall`, `prism-skill-delegation`, `prism-multi-turn-relay` | Prism 协议、tools、设计文档 |
| 共约层 | `references-layer`, `protocol-index`, `design-decisions` | references、索引、决策表 |

后续每个能力项必须至少给出以下结论之一：

- `intact`
- `behavior_changed_but_acceptable`
- `critically_regressed`
- `deferred_follow_up`

也就是说，RedCap 现在评估架构完整性时，不再只问“文档里还有没有这个标题”，而是同时问：

1. 语义是否还成立
2. 多会话重构后是否被削弱或漂移
3. 是否有 runtime / acceptance 级正向证据
4. 哪些宿主受保护，哪些仍需补偿式治理

---

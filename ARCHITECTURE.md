# RedCap — 架构总览与治理模型

> **一句话定义**：RedCap 是一个由 Loom 执行平面、Compass 自演化控制面、Prism 分析裁决平面与 References 共约层组成的多 Agent 软件工程框架。
>
> **阅读方式**：本文件负责解释“系统现在是如何设计的”；`compass/docs/traces/architecture-capability-trace.yaml` 负责冻结旧能力锚点并承载后续 `旧架构 -> 新架构 -> runtime evidence` 的回归审查。

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
| `prism` run state | run-scoped truth | Prism | 每次 Prism 运行的 run_id、registry、collect、resolve/archive 记录 | 以 run 为隔离边界 |
| runtime project state | derived state | runtime tools | session/capability/binding/process claim、compat、audit、pending closure、closure-ledger | 不能反向篡改 canonical truth |
| 宿主 `plan.md` / workboard | mirror state | host surface | 展示当前 pointer/hash，辅助长任务导航 | **mirror-only** |
| 宿主通用 skill（brainstorming / planning / visual） | overlay protocol | host skill | 提供分解、表达、展示与设计建议 | **advisory-only**，不得覆盖 `.dev-task.md`、PM Gate、自主执行授权，也不得默认升级成人工审批门 |
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

当前这条边界已由 `compass/tools/redcap-artifact-lifecycle-check.sh` 进入收尾链：对 **RedCap 自身工作区**，`stop-review` 与 `redcap-on-complete.sh` 会检查本轮 commit 区间内所有曾进入历史的路径，而不是只看最终 net diff；一旦命中 session-isolated / local-only / temporary artifact 或 `compass/docs/` 根目录未分类条目，就会阻断当前收尾通过并显式暴露该违规路径。它目前还不是 pre-commit 阶段的物理阻断器。

### 2.2.2 `docs / knowledge / continuity assets` 的职责分层

文件放哪一层，不取决于“看起来像不像记录”，而取决于它承担的是哪种记忆职责：

| 层 | 典型载体 | 职责 | 是否可直接当作长期 evidence |
| --- | --- | --- | --- |
| **frozen evidence** | `compass/docs/specs/**`、`research/**`、`traces/**`、`task-reports/**` | 冻结后的设计、审计、研究与 closure 证据 | 是 |
| **live knowledge** | `compass/knowledge/lessons.md`、`host-reliability.md`、`hooks-*.md`、模型矩阵 | 活的经验、heuristics、宿主差异与操作知识 | 只作为规则与经验，不直接替代 closure evidence |
| **continuity assets** | `.dev-task.md`、`compass/knowledge/explore-notes.md`、宿主 `plan.md` / workboard、导入的 session artifacts | 防偏航、防上下文稀释、断点恢复、显式继承 | 否 |

因此：

1. `compass/docs/` 与 `compass/knowledge/` 是**平级不同职**，不是父子关系。
2. continuity assets 不是“第三个 docs”，而是围绕 canonical truth 运行的连续性状态链。
3. 若某类资产要从 continuity 层升级为 evidence，必须经过**显式发布**，而不是因为“写成了 markdown”就自动变成 docs。
4. `compass/docs/index.yaml` 负责冻结 docs collection 的 retention / archive 规则，避免 docs 根目录再次回到大杂烩状态。

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

这里还要额外加一条资产边界：**共享宿主 skill 是 carrier-owned overlay，不是 RedCap 的 patch surface**。  
RedCap 可以消费它们的能力，但不能把“修改宿主 shared skill 原始文件”当成自身能力成立的前提；若不改宿主 skill 就无法稳定工作，该路径只能被标记为 **degraded / unsupported overlay**。

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
5. 变更后执行影响范围检查、任务报告、独立审查、通知与收尾

Layer B 不走 Loom 的 Dispatcher 状态机，但它同样遵守“先澄清、再执行、后闭环”的工程节奏。

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

当前 Layer B 的控制面不再依赖“Agent 应该记得当前在做哪一刀”，而是依赖**显式 metadata + gate 脚本 + drift 审计**。

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
- continuity_state（`fresh-session` / `self-recorded` / `import-suggested` / `imported`）

这块信息仍然只是 mirror，不会反向成为 authority；它存在的目的，是让新会话进入时能**看见**自己是否已有连续性记录、是否存在兼容历史会话，以及显式导入命令是什么。

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
4. 飞书通知 / 告警
5. session-end cleanup

本轮治理之后，这条链新增了显式的 **pending closure obligation** 与 **closure ledger**：

- `redcap-interop-governance.sh`：统一维护 `audit/`、`pending-closure/`、`closure-ledger/` 三类治理状态；其中 `closure-ledger/` 是 append-only 事务日志，`pending-closure/` 是当前尚未清偿的义务
- `redcap-task-report-register.sh`：报告在 **process claim 可用且登记成功** 时创建 pending closure；若 claim 缺失则记录 degraded mode 并拒绝注册
- `redcap-task-report-check.sh`：可从 pending closure 回读 `artifact_path`，支持无新 diff 的补偿式 reconcile
- `redcap-on-complete.sh`：对 RedCap 自身 on-complete fail-closed 校验 commit proof / task report / artifact lifecycle，并把关键阶段追加到 closure ledger
- `redcap-layerB-session-end.sh`：成功则清 obligation 并记账；失败或缺 claim 则把缺口重新写回 pending closure，并显式记录 blocked redlines
- `redcap-layerB-session-start.sh`：记录 re-anchor 时是否仍带着未闭环义务

与此同时，task report 本身不再只是“归档路径”：

- 模板必须显式提供 `需你确认 / 人工验证 / 后续动作`
- `redcap-notify-format.sh` 会从报告中抽取这三段，直接进入 stdout 收尾摘要与飞书通知
- 这样 Norven 在不打开完整报告时，也能先看到真正需要介入或关注的点

这意味着弱宿主即使没有完整 Hook，也不能再把“收尾链没发生”静默吞掉。

### 4.9 经验库机制

经验库仍然分两层：

- `lessons.md`：活跃层，保持短小、常驻启动上下文
- `lessons-archive.md`：归档层，按需检索

高影响 lesson 不允许自动淡出。  
它的职责不是“做知识管理”，而是**把曾经出现过的失败模式保留为下一次执行的边界条件**。

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

### 5.1.1 explicit import protocol

RedCap 当前把“最近会话继承”落成了**显式导入协议**，而不是默认自动恢复：

1. SessionStart 先同步 canonical pointer，再把 `session_handle + binding_key + task metadata` 镜像到宿主 workboard
2. 若当前会话没有自己的 continuity record，系统只会给出 `import-suggested` 与明确的导入命令
3. 真正导入时，`redcap-session-continuity.sh import` 只复制 continuity artifacts：
   - `plan.md` 快照
   - `files/`（排除二次嵌套的 imported-sessions）
   - `checkpoints/`
4. 源会话目录保持原样保留；目标会话把导入内容放进 `files/imported-sessions/<source_handle>/`
5. 导入完成后，宿主 workboard 会把 continuity_state 切到 `imported`，并记录来源 session handle / source plan / import root

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

这是一条显式的架构声明，而不是实现细节。  
如果后续实现出现折衷，也必须在 capability trace 中显式标注，而不是在重写文档时抹掉。

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
| `compass/docs/traces/architecture-capability-trace.yaml` | 旧能力锚点与全量 trace matrix |
| `loom/dispatcher/state-machine.md` | Layer A 状态转移定义 |
| `loom/dispatcher/agent-adapters.md` | 路由、适配、会话接力 |
| `prism/protocol.md` | Prism 协议全文 |
| `references/communication-protocol.md` | `__redcap_status` 完整协议 |
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
2. `compass/docs/traces/architecture-capability-trace.yaml`：冻结旧能力锚点，映射新架构锚点，记录 runtime evidence
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

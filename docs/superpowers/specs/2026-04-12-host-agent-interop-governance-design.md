# Host-Agent Interop Governance 与架构能力回归审查设计

> 状态：已完成设计讨论，待实现
> 日期：2026-04-12
> 主题：在多会话隔离主线收口后，为 RedCap 建立 host/native 互操作治理，并以重构后的 `ARCHITECTURE.md` 为基线，逐项审查全部设计思路与能力点是否被长任务改造破坏。

---

## 1. 背景与问题

多会话隔离主线已经收口，但本轮长任务暴露出的根因并不只是“隔离实现缺口”，而是更深层的 **authority inversion**：

1. RedCap 已经有 `.dev-task.md`、runtime state、Prism run registry、task report、lessons 等持久化载体，但这些载体没有在 host/native 边界上被硬执行为唯一 authority。
2. 宿主 Agent 自带的 `plan.md`、session 目录、直接 skill/tool 路径，在长任务里天然更顺手；如果 RedCap 不主动收回控制面，它们就会逐渐变成事实真相源。
3. 约束 hook、收尾链、治理脚本若只以“文档规则”存在，而没有物理门禁与审计，就会在长任务上下文压缩、生命周期错位、宿主能力差异下静默失效。

用户在中途 review 中明确指出两类问题：

1. **宿主 × RedCap-native 边界治理缺失**：需要把 lifecycle / state / transaction boundary 从“规范”提升为“可执行治理”。
2. **能力资产回归风险**：不仅要保护红线约束 hook，还要基于 `ARCHITECTURE.md` 梳理出的全部设计思想与功能点，逐项评估是否被本轮多会话隔离长任务破坏、削弱或静默失效。

此外，当前还有一个需要优先纳入本 tranche 的关键回归信号：

- 用户确认本轮最终没有出现 **整体 review / 代码提交 / 飞书通知** 等收尾结果；
- 具体故障形态未知，但可以确定“结果没有发生”，因此必须把这类收尾链提升为**可审计的 closure transaction**，禁止继续以 silent failure 形态存在。

---

## 2. 目标与非目标

### 2.1 目标

本设计的目标是同时完成四件事：

1. 为 RedCap 建立 **host-agent interop governance**，在宿主承载面与 RedCap 原生 authority 之间加上可执行的边界规则。
2. 将 RedCap 对自身状态的默认策略明确为 **fail-closed on RedCap state**：
   - 不强拦宿主本身；
   - 但 RedCap 自有状态、once-only 语义、报告登记、委托结果接纳、收尾推进等不得在越界状态下继续推进。
3. 重构 `ARCHITECTURE.md`，把 RedCap 当前已经成熟的设计思想、功能点、治理资产、红线约束、运行时边界全部整理成正式架构资产。
4. 先冻结一份 **旧架构能力锚点表**，再重构 `ARCHITECTURE.md`，最后基于 **旧架构 -> 新架构 -> runtime evidence** 三向映射做一次 **全量架构能力回归审查**：
   - 审查对象是全部设计思路与能力点；
   - 红线 hook 是其中必须重点保全的一层；
   - 关键回归本 tranche 直接修复，低优先级问题进入后续 todo / lesson / task report。

### 2.2 非目标

本 tranche 明确不做以下事情：

1. **不尝试全面接管宿主自身 tool/skill 生命周期**。不做宿主级防火墙，不与宿主抢“系统主控权”。
2. **不新建第二套控制面或 ledger**。`.dev-task.md` 仍是 Layer B canonical ledger；宿主工作面板继续 mirror-only。
3. **不把 architecture audit 缩成 hook 健康检查**。审查范围是全量能力；hook 只是更硬的一组资产。
4. **不以“文档写了”冒充“治理已生效”**。能力存在、配置已部署、运行已生效三者必须分层陈述。

---

## 3. 设计原则与约束来源

本设计直接受以下元原则与 lessons 约束：

- **P-1 整体自洽优先**：本变更不是补单点脚本，而是要做全局 authority chain 收口。
- **P-2 文档即传承**：`ARCHITECTURE.md` 必须成为完整蓝图，而不是零散历史记录。
- **P-3 全局视角**：治理边界必须覆盖 Loom / Compass / Prism、宿主差异、resume/recover、委托路由与收尾链。
- **P-4 人机共治**：人类负责方向确认，AI 负责设计闭环、细节审查与全量回归检查。
- **P-5 持续体检**：本 tranche 完成后必须做全量能力体检，而非只看改动文件。

与本设计直接相关的经验条目：

- **L-9**：长任务上下文压缩会导致规则退化，必须用文件与物理检查点对冲。
- **L-12**：指令注入不等于执行保证，关键动作必须尽量走脚本 / hook。
- **L-15**：需要认知的关键动作必须通过 `Hook -> 新 Agent` 保证触发与认知质量。
- **L-16**：Hook 设计 ≠ 部署 ≠ 生效，必须有端到端证据。
- **L-41**：能力存在、已部署、已生效三层结论必须分开写。
- **L-43**：在宿主 Agent 中运行 RedCap 时，必须防 authority inversion。
- **L-44**：binding 只负责定位，不等于能力恢复；定位与授权必须分离。

---

## 4. 方案对比与最终选择

讨论阶段考虑过三种方案：

### 方案 A：轻治理叠层

仅补文档、协议说明、审查矩阵与少量守门脚本。

- **优点**：改动面最小。
- **缺点**：只能减少“忘记规则”，无法阻止运行时继续越界推进。

### 方案 B：控制面收口型治理（采纳）

在不接管宿主本体的前提下，把 host/native boundary、mirror-only、re-anchor、delegation contract、closure transaction、drift/audit 都收口到现有 RedCap 控制面中。

- **优点**：
  - 与用户确认的默认策略一致：`fail-closed on RedCap state`
  - 与已落地的 `.dev-task.md` / PM Gate / drift check / host workboard sync / delegation boundary 直接兼容
  - 不新增第二套 authority，也不与宿主生命周期正面冲突
- **缺点**：
  - 需要补齐多个入口脚本的治理 checkpoint
  - 需要对 `ARCHITECTURE.md` 做结构性重写

### 方案 C：宿主防火墙型治理

尝试进一步阻断宿主自身的 direct skill/tool 行为。

- **优点**：理论上最强。
- **缺点**：
  - 极易与宿主生命周期与权限系统冲突；
  - 不同宿主能力差异极大，容易引入新的 authority inversion；
  - 实际可验证性与可维护性都最差。

### 最终决策

采纳 **方案 B**。  
RedCap 负责把自己的 authority、checkpoint 与审计做硬；宿主继续负责承载与触发，但不再能绕过 RedCap 原生边界去推进 RedCap 自有状态。

---

## 5. 核心边界模型

### 5.1 三类职责

1. **宿主（carrier surface）**
   - 负责：显示工作面板、触发 hook、提供 session 设施、运行 tool/skill
   - 不负责：定义 RedCap 真相、推进 RedCap 授权事务、认定治理成功

2. **RedCap 原生控制面（canonical authority）**
   - 包括：`.dev-task.md`、runtime session/capability、Prism run registry、delegation contract、task report contract、治理审计结论
   - 负责：决定什么能推进、什么时候 fail-closed、哪些结果可被接纳

3. **共享审计面（project-shared audit）**
   - 用于记录 interop violation、closure blocker、drift evidence、degraded evidence
   - 仅承载证据，不承载真相
   - 必须是 evidence-only，禁止反向充当 authority 或恢复入口

### 5.2 核心不变量

1. `.dev-task.md` 仍是 Layer B canonical ledger。
2. 宿主工作面板只允许 mirror-only，不得承载实施真相。
3. 宿主 resume/recover 必须先 **re-anchor** 回 RedCap canonical truth，才能继续推进 RedCap 自有状态。
4. 宿主 direct skill/tool 路径不等于 RedCap-native delegation。
5. 任一入口一旦发现 authority 缺失、claim 缺失、re-anchor 缺失、pointer 漂移或 contract 不成立，RedCap 必须对自己的状态 **fail-closed**。

---

## 6. 治理组件设计

### 6.1 新增一个薄的共享治理 helper

计划新增一个专门的共享 helper，暂定位置：

- `compass/tools/redcap-interop-governance.sh`

该 helper 的职责是：

1. 统一计算与校验 host/native boundary 所需的前置条件；
2. 提供标准化的 fail-closed 判定；
3. 统一记录 interop violation / closure blocker / recovery refusal 等审计事件；
4. 将现有 PM Gate、drift、host workboard、runtime attach、delegation contract 收束成一组一致的治理入口。

该 helper **不是新的真相源**，只负责执法；真实状态继续由现有控制面持有。

### 6.2 关键 checkpoint

治理 checkpoint 至少覆盖以下几类入口：

1. **Start / Resume / Recover checkpoint**
   - `redcap-layerB-session-start.sh`
   - 与 runtime attach / binding / capability gate / PM Gate / host mirror sync 串接
   - 没有 re-anchor 成功前，不允许恢复 RedCap 自有写权限

2. **运行中状态推进 checkpoint**
   - `redcap-task-report-register.sh`
   - `redcap-task-report-check.sh`
   - `redcap-on-stop-review.sh`
   - 任何推进 task report、once-only、review gating、session-private marker 的行为都必须先过 authority gate

3. **收尾事务 checkpoint**
   - `redcap-layerB-session-end.sh`
   - `redcap-on-complete.sh`
   - 必须把整体 review / commit / notify 以及其他红线收尾动作纳入统一 closure transaction

4. **宿主承载面 checkpoint**
   - `redcap-host-workboard-sync.sh`
   - 明确从“同步工具”升级为“mirror-only 守门人”

5. **委托路由 checkpoint**
   - `baton-delegate.sh`
   - request/result 文件边界继续作为协议内 delegation 唯一入口
   - 宿主 direct skill 不得被误记为 RedCap-native delegation 成功

### 6.3 审计载体

新增一组 project-shared 的治理审计载体，用于记录：

1. boundary violation
2. re-anchor refusal
3. no-claim / no-capability refusal
4. closure transaction 阻断
5. host direct path 被拒绝推进

这些载体的职责是：

- 提供“发生了什么”的物理证据；
- 支撑 `ARCHITECTURE.md` 的回归矩阵；
- 防止再次出现“结果没发生，但系统没有留下确定性线索”的情况。

具体文件名可在实现阶段结合现有 runtime/project-shared 目录结构收口，但必须保证：

1. 有稳定物理路径；
2. 有类别化记录；
3. 每条记录都能标识最小作用域（如 task / runtime session / prism run / host / lifecycle stage / hook name）；
4. 仅作为 evidence 被 SessionEnd / task report / architecture audit 引用，不能反向成为新的控制面。

---

## 7. 事务流与失败语义

### 7.1 Start / Resume / Recover

执行顺序应变成：

1. 读取当前 host context
2. 对齐 canonical pointer
3. 执行 re-anchor
4. 验证 runtime claim / binding / capability 恢复条件
5. 成功后才允许推进 RedCap 自有状态

若失败：

- 宿主继续存在；
- RedCap 进入 fail-closed；
- 记录明确审计事件；
- 不允许继续推进 session-private / once-only / canonical state。

### 7.2 运行中推进

运行中所有能改变 RedCap 事实状态的动作，都必须视为“治理事务”：

- task report register/check
- stop review 前置登记
- delegation result accept
- host mirror update
- once-only marker 推进

这些动作不能再以“best effort 辅助脚本”对待；它们要么被 authority checkpoint 接纳，要么被明确拒绝并留下证据。

### 7.3 Stop / Review / SessionEnd / Complete

收尾链必须升级为 **closure transaction**：

1. 整体 review
2. 代码提交
3. 飞书通知
4. 其他红线性质的收尾约束 hook

本设计要求：

1. 这些动作不能静默丢失；
2. 如果因为 no-anchor / no-claim / context mismatch / degraded mode 等原因无法推进，必须留下明确 blocker；
3. 对话里“口头汇报已完成”不得再被接受为可审计完成态；
4. 对所有红线约束 hook，不仅要求“有能力”，还要求“已部署、已生效、可验证”。

### 7.4 fail-closed 的边界

本 design 采纳如下失败策略：

- **对宿主本身**：不尝试全面阻断；
- **对 RedCap 自有状态**：fail-closed；
- **对审计**：必须显式落盘，而不是仅在终端输出一句解释。

### 7.5 弱 hook / 无 hook 宿主的补偿式 closure contract

强 hook 宿主可以直接依赖 SessionEnd / Stop / on-complete 链路执行 closure transaction；  
弱 hook / 无 hook 宿主则必须有一条**补偿式 closure contract**，否则“不能静默丢失”只会停留在强宿主。

该 contract 明确为：

1. **触发点**
   - 任何即将把控制权交还给宿主、且按架构应进入收尾事务链的时刻
   - 例如：任务报告已登记、review 已通过、准备宣告本 tranche 完成，但宿主没有可靠 closure hook

2. **owner**
   - 当前 RedCap-native 入口负责先写入一条 canonical 的 pending-closure obligation
   - 下一次成功 `re-anchor` 到同一 task / canonical pointer 的 RedCap-native 入口负责消费这条 obligation

3. **blocked RedCap states**
   - 未完成 closure reconcile 前，不允许：
     - 宣告任务真正完成
     - 清空或归档仍待闭环的任务报告
     - 将需要收尾审计的 canonical state 推进为“已闭合”

4. **evidence artifacts**
   - canonical 侧：记录 pending-closure obligation（属于真相的一部分）
   - audit 侧：记录 host / lifecycle / task / applicable redline set / 当前决策 / reconcile 结果

5. **pass / fail rule**
   - pass：所有适用的红线收尾项都被记录为 `done` 或 `governed_skip`
   - fail：下一次 re-anchor 时仍发现 unresolved obligation，则 RedCap 对相关状态 fail-closed，并留下明确 blocker

6. **适用边界**
   - 这不是“弱宿主特殊宽容”，而是“弱宿主必须多一条补偿式治理路径”
   - 强宿主走实时 closure transaction；弱宿主走 deferred closure reconcile；两者都必须留下物理证据

---

## 8. `ARCHITECTURE.md` 重构方案

`ARCHITECTURE.md` 本次将从“局部更新过的旧总览”升级为“可作为回归基线的架构资产总图”。

但为了避免“新文档删掉旧能力，随后审查基于删减后的新基线而误判通过”的循环风险，本设计要求先做一份 **旧架构能力锚点表**：

1. 以当前 `ARCHITECTURE.md` 的一级/二级主题为起点；
2. 补入当前文档未充分表达、但仓库中已存在的成熟设计能力；
3. 为每个能力项记录：
   - 旧文档锚点
   - 新文档锚点
   - runtime / script / acceptance / task-report 证据
   - 审查结论

后续审查必须基于这张 **旧 -> 新 -> runtime** trace matrix，而不是只基于新文档本身。

目标结构：

1. **系统目标与三体分层**
   - Loom / Compass / Prism 的职责边界
   - references 作为共约层

2. **控制面与 authority chain**
   - canonical ledger
   - mirror-only surfaces
   - runtime session / capability / binding
   - Prism run-scoped truth
   - delegation contract

3. **host-agent interop governance**
   - host/native boundary
   - re-anchor 机制
   - fail-closed 语义
   - closure transaction
   - 为什么宿主 direct path 不能提升为 RedCap authority

4. **治理资产与红线 hook**
   - 约束 hook 的类型、职责、触发点
   - “能力存在 / 已部署 / 已生效”三层模型

5. **能力清单与回归矩阵**
   - 全量设计思想 / 功能点 / 边界语义
   - 每项能力的当前状态、依赖、验证方式、回归结论

6. **兼容 / degraded / audit 模型**
   - safe degraded 的边界
   - compat bridge 的角色
   - 治理审计为何必须 project-shared 落盘

这次改写不会只补“多会话隔离”章节，而是要把 RedCap 已成熟的优秀设计思想完整收束进一个当前版本的一致性总图。

---

## 9. 全量能力回归审查范围

本 tranche 的审查范围是 **`ARCHITECTURE.md` 重构后梳理出的全部能力与设计思路**，不是只看 hook。

### 9.1 审查维度

每项能力至少从以下维度判断：

1. **是否仍存在**
2. **是否仍按原设计语义工作**
3. **是否在多会话隔离长任务中被削弱、漂移或静默失效**
4. **是否具备物理证据**
5. **是否需要纳入红线 hook 子集**
6. **按哪些宿主生效 / 失效**
7. **影响哪些角色 / 层次 / 生命周期阶段**
8. **属于哪一层 enforcement tier**（文档约束 / hook 触发 / 脚本门禁 / acceptance 证明）
9. **正向成功证据是否存在**，而不仅是失败时能否报错

### 9.2 结论分类

每项能力在回归矩阵中标记为：

- `intact`
- `behavior_changed_but_acceptable`
- `critically_regressed`
- `deferred_follow_up`

### 9.3 红线 hook 只是能力全集的一个子集

本设计明确区分：

1. **全量能力层**
   - 所有架构理念、边界模型、功能点、治理机制

2. **红线约束层**
   - 必须保全、不可静默丢失的约束 hook 与治理动作

也就是说，后续审查既会检查 hook 存活，也会检查所有非 hook 的设计资产是否被本轮长任务破坏。

### 9.4 能力全集的来源

能力全集不能靠临时回忆拼凑，必须直接从重构后的 `ARCHITECTURE.md` 反推生成。

换句话说，`ARCHITECTURE.md` 的每个一级/二级主题都要转成审查项。以当前文档结构为起点，至少要覆盖：

1. 设计哲学
2. 三体架构总览
3. Loom / Dispatcher 事件循环
4. 状态机
5. 通信协议
6. 角色系统与 Prompt 组装
7. 模型路由
8. 可靠性工程
9. Compass / 框架自身开发流程
10. PM Gate
11. 书记协议
12. 指挥棒 / delegation
13. Hook 基础设施
14. 经验库机制
15. Prism 两族协议
16. Skill-delegation 模式
17. 多轮接力协议
18. references 共约层
19. 关键协议文件索引与设计决策速查
20. 本次新增并重构出的 authority chain / interop governance / audit matrix 章节

此外，凡是当前 `ARCHITECTURE.md` 尚未充分展开、但仓库中已经沉淀为成熟机制的能力，也必须补入旧架构能力锚点表，例如：

1. task-tracking control plane
2. host workboard alignment
3. runtime session isolation model
4. safe degraded / compat bridge 语义
5. closure transaction 与任务报告物理归档
6. Prism 的高风险治理资产（含 run-scoped truth、relay、以及架构中声明的 firewall / gate 类能力）
7. soul / revive / re-anchor 一类的人格连续性与恢复治理语义

这些主题在实现时会进一步拆成更细的能力点；但审查必须先保证“主题全集无遗漏”，然后再做子项下钻。

### 9.5 首批必须重点核验的能力族

在全量能力之上，本 tranche 至少优先核验以下高风险能力族：

1. 三体分层边界
2. PM Gate / drift / canonical ledger
3. host workboard mirror-only
4. runtime session / capability / binding / degraded model
5. Layer A ownership / review fallback / stop chain
6. Layer B task report / stop review / session-end / on-complete
7. Prism run-scoped registry / collect / resolve / archive bridge
8. delegation contract / request-result boundary
9. lessons / task report / audit artifact 归档机制
10. 所有红线 hook 与 closure transaction

---

## 10. 关键回归处理策略

用户已确认本 tranche 的默认策略为：

- **关键回归直接修**
- **低优先级问题列入后续 todo**

因此本 design 规定：

1. 与 authority chain、mirror-only、re-anchor、closure transaction、红线 hook 存活性相关的问题，一律按关键回归处理；
2. 会导致“系统表面成功、实际约束失效”的问题，一律按关键回归处理；
3. 纯结构整理、命名统一、文档措辞优化等低优先级项，可进入 follow-up。

---

## 11. Pre-mortem 自检

### 11.1 对“不做宿主级强拦截”的挑战

本设计明确不做宿主防火墙，必须给出可检验理由，而不是“感觉麻烦”。

尝试过的可行路径包括：

1. 在宿主入口全面 deny tool/skill
2. 为所有宿主建立统一路由壳层，强制所有动作先经过 RedCap
3. 让 RedCap 反向接管宿主工作面板与 session store

结论：这些路径理论上可部分实现，但当前代价与风险过高：

1. 不同宿主的生命周期与权限模型不统一；
2. 很容易引入新的 authority duplication；
3. 对“本轮必须先补治理缺口并止损”的目标而言，收益不如把 RedCap 自己的 authority gate 做硬。

因此，本轮将“物理阻断宿主本体”记为**已挑战但不采纳**，不是未经思考的省略。

### 11.2 对“审查范围完整性”的挑战

本设计不接受“只审最容易想到的 hook”。  
完整性挑战的结果是：回归清单必须由重构后的 `ARCHITECTURE.md` 反推生成，确保**全量能力先枚举，再逐项审查**。

---

## 12. 验证与审查策略

### 12.1 设计阶段

1. 先写本设计文档
2. 做 spec 自检：
   - 无 TBD / TODO
   - 无内部矛盾
   - 范围足够完整
   - 关键非目标已有挑战记录
3. 做独立红队审查：
   - 重点挑战“是否遗漏能力族”
   - 重点挑战“是否低估宿主冲突风险”

### 12.2 实现阶段

1. 用 targeted smoke 覆盖 interop checkpoint
2. 复用现有 multi-session acceptance harness 证明隔离主线没有被治理改坏
3. 新增/补强“红线 hook 存活性”验证
4. 先冻结旧架构能力锚点表，再重写 `ARCHITECTURE.md`
5. 基于 `旧架构 -> 新架构 -> runtime evidence` trace matrix 做逐项人工 + AI 回归审查
6. 对弱 hook / 无 hook 宿主实现补偿式 closure contract，并验证其 trigger / owner / blocked states / evidence / pass-fail 规则

### 12.3 完成态要求

只有当以下条件同时满足，才可认为本 tranche 完成：

1. `host-agent-interop-governance` 已落地为可执行治理，而非纯文档规则
2. `ARCHITECTURE.md` 已重构为全量能力蓝图
3. 全量能力回归审查已完成
4. 关键回归已修复
5. 红线 hook 的能力存在 / 已部署 / 已生效状态有物理证据

---

## 13. 实施产物预期

本 design 对应的交付物预期包括：

1. 一个共享 interop governance helper（或等价收口层）
2. 多个关键入口脚本的治理 checkpoint 接线
3. 一组 project-shared 的 interop / closure 审计载体
4. 一份旧架构能力锚点表
5. 一份 per-host closure contract 说明与弱宿主补偿路径
6. 完整重构后的 `ARCHITECTURE.md`
7. 一份基于 `旧架构 -> 新架构 -> runtime evidence` 的回归矩阵
8. 关键回归修复与必要的 lessons / task report 更新

---

## 14. 决策摘要

本设计的最终口径是：

1. **采用控制面收口型治理**，不做宿主防火墙。
2. **默认 fail-closed on RedCap state**，宿主不强拦，但 RedCap 自有状态不得越界推进。
3. **先冻结旧架构能力锚点表，再重构 `ARCHITECTURE.md`，最后做三向 trace 审查**。
4. **红线 hook 是重点子集，但审查对象是全部设计思路与能力点，不止 hook。**
5. **关键回归当场修复**，尤其优先处理收尾链与其他红线治理资产的静默失效问题。
6. **弱 hook / 无 hook 宿主也必须有补偿式 closure contract**，不能把治理保证只建立在强宿主上。

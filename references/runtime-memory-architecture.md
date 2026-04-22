# Runtime Memory Architecture

> **定位**：说明 RedCap 的“运行时记忆系统”如何分层，以及 Layer B 的分布式控制面生命周期如何与脚本、账本和收尾链绑定。
>
> **一句话先看懂**：Layer A 用单一显式 FSM 驱动；Layer B 用 `.dev-task.md + validator-chain + pending closure + closure-ledger + session-start/stop-review/on-complete/session-end` 组成分布式控制面状态机。

## 1. 为什么需要这份文档

RedCap 过去容易在两个表述之间打架：

1. **正确但不完整**：Layer A 有显式 `state.yaml` 状态机，Layer B 没有这一类单一 FSM 文件。
2. **因此容易误导**：把“Layer B 没有单一 FSM”说成“Layer B 没有状态机 / 没有状态控制面”。

这份文档的职责，就是把 Layer B 已经存在的分布式控制面正式收口成一份权威协议，避免实现持续演化、文档却停留在旧说法。

## 2. RedCap 的三层运行时记忆

运行时记忆不是一个东西，而是三层分工：

| 层 | 它回答的问题 | 典型载体 | 是否是当前任务真相源 |
| --- | --- | --- | --- |
| **当前任务流状态** | 我现在在做什么、做到哪、下一步去哪 | Layer A: `loom/**/.workflow/state.yaml`；Layer B: `.dev-task.md`、runtime stamp、validator result | 是 |
| **跨会话考古 / 追踪层** | 上次发生了什么、为什么会卡在这里、证据在哪里 | task report、pending closure、closure-ledger、`current-status`、`diagnose`、Prism run/report | 部分是证据真相，部分只是视图 |
| **长期知识和项目资产的持续沉淀** | 哪些经验、路线、设计与研究要持续复用 | `compass/knowledge/**`、`references/backlogs/*.json`、`compass/docs/specs/**`、`research/**` | 否；它服务长期，不替代当前任务流 |

这三层的边界不能混：

- 任务正在做什么，不该只写进 task report。
- 某次 closeout 是否真的发生过，不该只靠 `.dev-task.md`。
- 跨任务通用经验，不该塞进当前任务卡。

## 3. truth surfaces 与去重规则

| 表面 | 类型 | 用途 | 禁止越权的方向 |
| --- | --- | --- | --- |
| `.dev-task.md` | **Layer B 当前任务真相源** | 锁定 `task_id / top_goal / active_slice / confirmed_hash / 允许修改范围 / 已确认需求` | 不能被宿主 plan、task report、explore-notes 反向替代 |
| `pending-closure/*.state` | **未清义务真相源** | 记录当前 confirmed hash 下仍未闭合的 blocker | 不能被“口头说已经完成”覆盖 |
| `closure-ledger/*.log` | **闭环事务日志** | 记录什么时候因为什么进入 blocked / cleared | 不能被 current-status 摘要替代 |
| `compass/docs/task-reports/*.md` | **闭环证据** | 说明“这轮到底改了什么、验证了什么、还剩什么” | 不能回头承载当前 live task state |
| `compass/knowledge/explore-notes.md` | **PM Gate 前的讨论底稿** | 保留未锁定阶段的探讨和分歧 | 不能升级成 canonical task ledger |
| `compass/knowledge/lessons.md` | **长期可复用经验** | 沉淀失败模式和工作方法 | 不能承载单轮任务状态 |
| `references/backlogs/*.json` | **长期路线真相源** | 承载跨会话 backlog / tranche / focus | 不能替代 `.dev-task.md` 的当前任务锚点 |
| `redcap-current-status.sh` / `redcap-diagnose.sh` | **状态面 / 体检面** | 把分散真相源汇总成可读视图 | 只是视图，不能自封 authority |

判断某条信息放哪一层时，只问三件事：

1. 这条信息是在回答“**我现在在做什么**”？
2. 还是在回答“**我怎么证明这轮真的收口了**”？
3. 还是在回答“**以后都该记住什么**”？

回答不同，载体就不同。

## 4. Layer B 分布式控制面生命周期

Layer B 没有 Layer A 那种单一 `state.yaml` FSM，但已经形成了一个分布式控制面生命周期。

### 4.1 状态枚举

| 状态 | 人话含义 | 主要载体 |
| --- | --- | --- |
| `REANCHORED` | 新会话已完成复活、身份恢复和当前任务锚点恢复 | `redcap-install.sh`、`redcap-layerB-session-start.sh`、会话绑定/runtime stamp |
| `TASK_LOCKED` | 当前任务边界、需求、slice 和允许修改范围已锁定 | `.dev-task.md`、`redcap-pm-gate-check.sh` |
| `EXECUTING` | 正在实现、修改、验证；所有改动必须受 drift / scope 审计约束 | `.dev-task.md`、`redcap-drift-check.sh` |
| `REVIEW_PENDING` | 已进入独立评审或 stop-review 闸门，尚不能宣布完成 | `redcap-on-stop-review.sh`、`redcap-review-proof-check.sh` |
| `CLOSEOUT_PENDING` | 代码可能已改完，但 task report / notify / ledger / pending closure 还没完成闭环 | `redcap-task-report-check.sh`、`redcap-on-complete.sh`、`pending-closure` |
| `CLOSED` | 当前 confirmed hash 的收尾红线已清，闭环事务完整落盘 | `redcap-layerB-session-end.sh`、`closure-ledger` |
| `BLOCKED` | 当前 hash 仍有 blocker，必须保留/重写 pending closure，不能伪装成已清 | `pending-closure/*.state`、`closure-ledger/*.log` |

### 4.2 主要转移

| 当前状态 | 触发事件 | 下一状态 | 绑定脚本 / 账本 |
| --- | --- | --- | --- |
| `REANCHORED` | PM Gate 通过、`.dev-task.md` 边界完整 | `TASK_LOCKED` | `redcap-pm-gate-check.sh` |
| `TASK_LOCKED` | 开始实现、允许修改范围内出现实际变更 | `EXECUTING` | `.dev-task.md` + `redcap-drift-check.sh` |
| `EXECUTING` | stop-review / 独立评审被触发 | `REVIEW_PENDING` | `redcap-on-stop-review.sh` |
| `REVIEW_PENDING` | 评审通过 | `CLOSEOUT_PENDING` | `redcap-review-proof-check.sh` + `redcap-task-report-check.sh` |
| `TASK_LOCKED` | PM Gate 失败、任务边界不完整或 authority 不一致 | `BLOCKED` | `redcap-pm-gate-check.sh` + `pending-closure` |
| `EXECUTING` | drift 失败、范围越界或阶段性 validator 失败 | `BLOCKED` | `redcap-drift-check.sh` + `redcap-validator-chain.sh` + `pending-closure` |
| `REVIEW_PENDING` | 评审失败、review proof 不成立 | `BLOCKED` | `redcap-review-proof-check.sh` + `pending-closure` |
| `CLOSEOUT_PENDING` | on-complete + session-end 全绿并成功清账 | `CLOSED` | `redcap-on-complete.sh` + `redcap-layerB-session-end.sh` |
| `CLOSEOUT_PENDING` | notify / task report / closure rewrite 任一步失败 | `BLOCKED` | `pending-closure` + `closure-ledger` |
| `BLOCKED` | 后续 SessionStart / reconcile 证明 blocker 已清且 authority 一致 | `REANCHORED` 或 `CLOSED` | `redcap-pending-closure-reconcile.sh` + `redcap-layerB-session-start.sh` |

## 5. 脚本绑定表

| 脚本 | 它在生命周期里的职责 |
| --- | --- |
| `compass/tools/redcap-install.sh` | 统一完成 Cap 复活、入口导入、current-status、tracking-health 和执行保障检查 |
| `compass/tools/redcap-layerB-session-start.sh` | 物理进入 `REANCHORED`，补跑 installer、会话绑定、pending closure advisory reconcile |
| `compass/tools/redcap-pm-gate-check.sh` | 把任务从“只是会话理解”提升成 `TASK_LOCKED` |
| `compass/tools/redcap-drift-check.sh` | 在 `EXECUTING` 期间持续检查 active slice / scope / authority 漂移 |
| `compass/tools/redcap-on-stop-review.sh` | 把 `EXECUTING` 推进到 `REVIEW_PENDING`，并要求独立评审有物理证据 |
| `compass/tools/redcap-validator-chain.sh` | 把分散检查组合成可消费的阶段性 verdict |
| `compass/tools/redcap-task-report-check.sh` | 要求 closeout 具备 task report 物理证据 |
| `compass/tools/redcap-on-complete.sh` | 执行 closeout 前置 gate，并在必要时写回 blocker |
| `compass/tools/redcap-layerB-session-end.sh` | 最终 authority reconcile；负责清账或保留 blocker |
| `compass/tools/redcap-interop-governance.sh` | 维护 pending closure / closure-ledger / current-report identity 等治理账本 |
| `compass/tools/redcap-current-status.sh` | 汇总当前状态观测面，但不取代任何 canonical truth，也不是生命周期 authority 载体 |
| `compass/tools/redcap-tracking-health.sh` | 汇总任务卡、报告、explore-notes 等 tracking 健康面 |

## 6. 哪些地方可以合并，哪些不能

本轮架构判断如下：

### 应合并或收口

- **Layer B 生命周期口径**：应收口到本文件，避免 `README`、`ARCHITECTURE.md`、`CONTRIBUTING.md` 各说一版。
- **运行时记忆术语**：应收口到 `compass/knowledge/runtime-memory-architecture.md`，避免以后再临时创造近义词。
- **状态面说明**：`current-status` / `diagnose` / `tracking-health` 应只负责展示，不重复定义 authority。

### 不应强行合并

- `.dev-task.md` 与 task report：一个是 live task truth，一个是 closure evidence。
- `pending-closure` 与 `closure-ledger`：一个记录“现在还欠什么”，一个记录“历史上发生过什么”。
- `explore-notes` 与 `lessons`：一个记录某次探讨底稿，一个沉淀跨任务经验。
- `references/backlogs/*.json` 与 `.dev-task.md`：一个服务长期路线，一个服务当前这一刀。

## 7. 这份文档与其它文件的关系

- **权威协议面**：本文件
- **人话词典面**：`compass/knowledge/runtime-memory-architecture.md`
- **架构总览**：`ARCHITECTURE.md`
- **执行规范**：`compass/CONTRIBUTING.md`
- **机器检查**：`compass/tools/redcap-layerb-lifecycle-check.sh`

换句话说：

- 本文件定义“Layer B 这台机器如何运转”
- `runtime-memory-architecture.md` 负责解释“这些词到底是什么意思”
- 其它入口文档只做摘要和引用，不再各自复制一份完整定义

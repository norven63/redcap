# Runtime Memory Architecture

> **定位**：说明 RedCap 的“运行时记忆系统”如何分层，以及 Layer B 的分布式控制面生命周期如何与脚本、账本和收尾链绑定。
>
> **一句话先看懂**：Layer A 用单一显式 FSM 驱动；Layer B 用 `.dev-task.md + 承诺账本 + closeout runtime + pending closure + closure-ledger + session-start/stop-review/on-complete/session-end` 组成分布式控制面状态机。

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
| `closeout-runtime/promise-ledger/*.json` | **执行承诺派生账本** | 把 `.dev-task.md` 中 `## 执行承诺账本` 转成可核对状态 | 不能脱离 `.dev-task.md` 自己发明承诺 |
| `pending-closure/*.state` | **未清义务真相源** | 记录当前 confirmed hash 下仍未闭合的 blocker | 不能被“口头说已经完成”覆盖 |
| `closure-ledger/*.log` | **闭环事务日志** | 记录什么时候因为什么进入 blocked / cleared | 不能被 current-status 摘要替代 |
| `closeout-runtime/receipts/*.json` | **终态收据** | 证明这次 closeout 真的闭环并留下 summary / promise / hash 证据 | 不能被“session-end 绿了”口头替代 |
| `closeout-runtime/audits/*.json` | **rescue 审计证据** | 记录 receipt 修补或 blocker 重写是否发生 | 不能被 diagnose 摘要替代 |
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
| `PLANNING` | 任务已经锁定，正在制定执行方案、切片、承诺账本与验证路径 | `.dev-task.md`、`redcap-drift-check.sh`、任务报告方案段 |
| `PLANNING_REVIEW` | 计划本身进入独立审核；复杂任务不得只靠作者或 Norven 做细节 plan 审稿 | Prism planning review、`redcap-prism-acceptance-bind.sh`、`redcap-prism-acceptance-check.sh` |
| `EXECUTING` | 正在实现、修改、验证；所有改动必须受 drift / scope 审计约束 | `.dev-task.md`、`redcap-drift-check.sh` |
| `REVIEW_PENDING` | 已进入独立评审 / 棱镜验收闸门，作者自检已不足以继续推进；验收 run 必须绑定到当前 `task_id + confirmed_hash` | `redcap-on-stop-review.sh`、`redcap-review-proof-check.sh`、`redcap-prism-acceptance-bind.sh`、`redcap-prism-acceptance-check.sh` |
| `CLOSEOUT_PENDING` | 代码可能已改完，但承诺账本、绑定后的棱镜验收、task report、notify、receipt、ledger、pending closure 还没完成闭环 | `redcap-layerb-closeout-runtime.sh`、`redcap-prism-acceptance-bind.sh`、`redcap-prism-acceptance-check.sh`、`redcap-task-report-check.sh`、`pending-closure` |
| `CLOSED` | 当前 confirmed hash 的收尾红线已清，绑定后的棱镜验收通过，闭环事务完整落盘，且已有 receipt | `redcap-layerb-closeout-runtime.sh`、`redcap-prism-acceptance-bind.sh`、`redcap-prism-acceptance-check.sh`、`closeout-receipts`、`closure-ledger` |
| `BLOCKED` | 当前 hash 仍有 blocker，必须保留/重写 pending closure，不能伪装成已清 | `pending-closure/*.state`、`closure-ledger/*.log` |

### 4.2 主要转移

| 当前状态 | 触发事件 | 下一状态 | 绑定脚本 / 账本 |
| --- | --- | --- | --- |
| `REANCHORED` | PM Gate 通过、`.dev-task.md` 边界完整 | `TASK_LOCKED` | `redcap-pm-gate-check.sh` |
| `TASK_LOCKED` | 进入执行方案制定，形成切片、承诺账本和验证路径 | `PLANNING` | `.dev-task.md` + task report / plan section |
| `PLANNING` | 计划需要独立审核，或任务风险达到棱镜验收门槛 | `PLANNING_REVIEW` | Prism planning review |
| `PLANNING_REVIEW` | 计划审核通过，且计划产物已回写任务账本 | `EXECUTING` | Prism verdict + `.dev-task.md` |
| `TASK_LOCKED` | 小型轻量任务不需要独立计划审核，并已具备明确执行路径 | `EXECUTING` | `.dev-task.md` + `redcap-drift-check.sh` |
| `EXECUTING` | stop-review / 独立评审被触发 | `REVIEW_PENDING` | `redcap-on-stop-review.sh` |
| `REVIEW_PENDING` | 评审 / 棱镜验收通过，且 acceptance run 已绑定到当前 `task_id + confirmed_hash` | `CLOSEOUT_PENDING` | `redcap-review-proof-check.sh` + `redcap-prism-acceptance-bind.sh` + `redcap-prism-acceptance-check.sh` + `redcap-task-report-check.sh` |
| `TASK_LOCKED` | PM Gate 失败、任务边界不完整或 authority 不一致 | `BLOCKED` | `redcap-pm-gate-check.sh` + `pending-closure` |
| `EXECUTING` | drift 失败、范围越界或阶段性 validator 失败 | `BLOCKED` | `redcap-drift-check.sh` + `redcap-validator-chain.sh` + `pending-closure` |
| `REVIEW_PENDING` | 评审失败、review proof 不成立 | `BLOCKED` | `redcap-review-proof-check.sh` + `pending-closure` |
| `CLOSEOUT_PENDING` | `closeout runtime complete` 成功，承诺已兑现、绑定后的棱镜验收已通过、receipt 已生成、session-end 已清账 | `CLOSED` | `redcap-layerb-closeout-runtime.sh` + `redcap-prism-acceptance-bind.sh` + `redcap-prism-acceptance-check.sh` + `closeout-cap.sh` |
| `CLOSEOUT_PENDING` | 承诺未兑现、棱镜验收缺失、notify / task report / receipt / closure rewrite 任一步失败 | `BLOCKED` | `redcap-layerb-closeout-runtime.sh` + `redcap-prism-acceptance-bind.sh` + `redcap-prism-acceptance-check.sh` + `pending-closure` + `closure-ledger` |
| `BLOCKED` | 后续 SessionStart / reconcile 证明 blocker 已清且 authority 一致 | `REANCHORED` 或 `CLOSED` | `redcap-pending-closure-reconcile.sh` + `redcap-layerB-session-start.sh` |

## 5. 脚本绑定表

| 脚本 | 它在生命周期里的职责 |
| --- | --- |
| `compass/tools/redcap-install.sh` | 统一完成 Cap 复活、入口导入、current-status、tracking-health 和执行保障检查 |
| `compass/tools/redcap-layerB-session-start.sh` | 物理进入 `REANCHORED`，补跑 installer、会话绑定、pending closure advisory reconcile |
| `compass/tools/redcap-pm-gate-check.sh` | 把任务从“只是会话理解”提升成 `TASK_LOCKED` |
| `compass/tools/redcap-drift-check.sh` | 在 `EXECUTING` 期间持续检查 active slice / scope / authority 漂移 |
| `compass/tools/redcap-on-stop-review.sh` | 把 `EXECUTING` 推进到 `REVIEW_PENDING`，并要求独立评审有物理证据 |
| `compass/tools/redcap-prism-acceptance-bind.sh` | 把当前 Prism run 绑定到 `task_id + confirmed_hash`，防止旧 run 被复用成当前任务的独立验收 |
| `compass/tools/redcap-prism-acceptance-check.sh` | Layer B completed 的默认独立验收 gate；没有有效且已绑定的棱镜验收，不得进入正式完成态 |
| `compass/tools/redcap-validator-chain.sh` | 把分散检查组合成可消费的阶段性 verdict |
| `compass/tools/redcap-task-report-check.sh` | 要求 closeout 具备 task report 物理证据 |
| `compass/tools/redcap-layerb-closeout-runtime.py` | Layer B closeout runtime 的确定性载体；同步承诺账本、执行 on-complete + session-end、生成 receipt / summary、执行 rescue audit |
| `compass/tools/redcap-layerb-closeout-runtime.sh` | closeout runtime 的 shell 入口；供 hook、acceptance 和宿主脚本调用 |
| `closeout-cap.sh` | 人类 / Agent 的根目录短收尾入口；不再要求调用方自己拼接棱镜验收 + on-complete + session-end |
| `compass/tools/redcap-diagnose.sh` | 当前 diagnose-rescue 强入口；terminal closeout 已开始但 receipt 缺失时，优先尝试 `audit-open --mode diagnose` |
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
- `promise-ledger` 与 `.dev-task.md`：一个是派生账本，一个是承诺源文本。
- `pending-closure` 与 `closure-ledger`：一个记录“现在还欠什么”，一个记录“历史上发生过什么”。
- `closeout-receipt` 与 task report：一个是终态收据，一个是人类可读闭环报告。
- `棱镜验收` 与 `stop-review`：前者是 Layer B completed 的默认独立验收 gate，后者是 review / reviewer 证据入口；两者不能互相口头替代。
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

# RedCap 运行时记忆架构词典

> **用途**：把 RedCap 里经常会说、但容易越说越散的概念固定成一套人话词典。
>
> **对应协议**：更严格的工程定义见 [`references/runtime-memory-architecture.md`](../../references/runtime-memory-architecture.md)。

## 一句话先看懂

RedCap 的“记性”不是一个大脑，而是三层东西一起工作：

1. **当前任务流状态**：现在在干什么、下一步去哪
2. **跨会话考古 / 追踪层**：上次发生过什么、证据在哪里
3. **长期知识和项目资产的持续沉淀**：以后类似任务该记住什么

## 常用术语

| 术语 | 人话解释 | 典型载体 |
| --- | --- | --- |
| **真相源** | 当前最有权威、能拍板“事实是什么”的地方 | `.dev-task.md`、`pending-closure/*.state`、`references/backlogs/*.json` |
| **镜像** | 只是把真相源显示出来，方便看，但自己不能改口径 | 宿主 `plan.md` / workboard |
| **闭环证据** | 证明“这轮真的做完了 / 审过了 / 记账了”的物理证据 | task report、closure-ledger、Prism report |
| **当前任务流状态** | 当前这一刀在做什么、做到哪、下一步去哪 | `.dev-task.md`、Layer A `state.yaml` |
| **跨会话考古 / 追踪层** | 回头追“为什么会走到这、上次卡在哪、证据在哪” | `current-status`、`diagnose`、task report、pending closure |
| **长期知识和项目资产的持续沉淀** | 跨任务、跨会话长期要保留的经验、路线、设计、研究 | `lessons.md`、`references/backlogs/*.json`、specs、research |
| **连续性资产** | 为了接盘和防上下文蒸发而存在的辅助记忆层 | `.dev-task.md`、`explore-notes.md`、runtime session manifest |
| **闭环事务** | 一次任务从“开始做”到“审完、记账、清账”的完整收尾过程 | stop-review → task report → on-complete → session-end |
| **分布式控制面状态机** | 没有单一 `state.yaml`，但由多份账本和 gate 共同表达状态与转移 | Layer B 生命周期 |
| **长期路线真相源** | 不管当前会话怎么变，长期 tranche/backlog 还是以它为准 | `references/backlogs/*.json` |

## 最容易混淆的 4 组概念

### 1. `.dev-task.md` vs task report

- `.dev-task.md`：回答“**现在**这轮在做什么”
- task report：回答“**刚才那轮**到底做成了什么”

不要把 task report 当 live task card，也不要把 `.dev-task.md` 当 closure evidence。

### 2. pending closure vs closure ledger

- `pending closure`：回答“现在还欠什么没闭环”
- `closure ledger`：回答“历史上发生过哪些闭环事务”

一个是现在的债，一个是过去的账。

### 3. explore-notes vs lessons

- `explore-notes`：某次讨论还没锁定前的草稿本
- `lessons`：未来类似任务都要复用的经验

一个偏“当时怎么讨论”，一个偏“以后别再踩坑”。

### 4. backlog vs 当前任务卡

- backlog：长期路线，回答“整体大图走到哪”
- 当前任务卡：当前 tranche / active slice，回答“这一刀正在砍哪”

一个看地图，一个看当前脚下。

## 如果只记住一条判断规则

当你犹豫某条信息该写哪时，只问一句：

> 这条信息是在描述“我现在做什么”、还是“我怎么证明刚做完”、还是“以后都该记住什么”？

答案不同，落点就不同。

# 2026-04-22 Layer B 生命周期与运行时记忆架构收口

## 0. 状态总览

### 0.1 当前已完成
- 已把 Layer B 从“散落在各处的状态逻辑”正式收口成一份单一协议面：[runtime-memory-architecture.md](/Users/norven/.claude/skills/redcap/references/runtime-memory-architecture.md)。
- 已新增一份给人直接复用的术语词典：[runtime-memory-architecture.md](/Users/norven/.claude/skills/redcap/compass/knowledge/runtime-memory-architecture.md)，把“真相源”“跨会话考古 / 追踪层”“长期知识和项目资产的持续沉淀”等概念固定下来。
- 已新增机器检查 [redcap-layerb-lifecycle-check.sh](/Users/norven/.claude/skills/redcap/compass/tools/redcap-layerb-lifecycle-check.sh)，并接入 [redcap-diagnose.sh](/Users/norven/.claude/skills/redcap/compass/tools/redcap-diagnose.sh) 与执行保障，防止 Layer B 生命周期协议、入口口径和基础脚本绑定再次漂移。
- 已修正入口与规范中的旧口径：Layer A 仍是单一显式 FSM；Layer B 不是“无状态机”，而是“分布式控制面状态机”。

### 0.2 上一步完成的是
- 上一步已经把 Layer A / Layer B 的事实考古清楚：Layer A 的显式状态机一直都在，Layer B 则在多轮迭代里逐渐长出了 `.dev-task.md + pending closure + closure-ledger + validator-chain + session-*` 这套控制面，只是文档还停留在旧表述。

### 0.3 下一步计划做的是
- 无当前任务级 blocker；本轮协议、词典、机器检查与独立审视均已收口完成。

### 0.4 整体计划脉络图与当前位置
- 路线：考古 Layer A / Layer B 真相 → 抽象运行时记忆三层 → 显性化 Layer B 生命周期 → 用机器检查绑定协议、入口口径与基础脚本 → 外部独立审视。
- 当前位置：协议、词典、机器检查、入口口径与独立审视 follow-up 已全部落盘；当前处于已完成 closeout 状态。

## 1. 这轮在解决什么

用户这轮的真实问题不是“再写一份解释文档”，而是三件事一起发生：

1. Layer B 明明已经有很多状态逻辑，却还在被口头说成“没有状态机”。
2. RedCap 的“当前任务流状态 / 跨会话考古 / 长期沉淀”三层，虽然都存在，但边界和术语没有被固定下来。
3. 这些解释如果继续只留在对话里，下次还是会散掉，既不利于 Cap 复活，也不利于 Norven 和 Agent 用同一套语言沟通。

所以这轮的目标不是发明一个新系统，而是把已经存在的 Layer B 控制面和运行时记忆架构正式命名、去重、收口，并把它变成能被检查的协议，而不是只靠人记住。

## 2. 架构判断

### 2.1 Layer A 与 Layer B 的准确关系

- **Layer A**：仍然是单一显式 FSM，权威状态表在 [loom/dispatcher/state-machine.md](/Users/norven/.claude/skills/redcap/loom/dispatcher/state-machine.md)。
- **Layer B**：没有 Layer A 那种单一 `state.yaml`，但已经形成了分布式控制面状态机。它的关键部件是：
  - 当前任务卡 `.dev-task.md`
  - `pending-closure`
  - `closure-ledger`
  - `validator-chain`
  - `session-start / stop-review / on-complete / session-end`

旧说法的问题不在于它完全错误，而在于它把“没有单一 FSM”偷换成了“没有状态控制面”。这会误导后续设计和沟通。

### 2.2 RedCap 的运行时记忆三层

这轮把 RedCap 的运行时记忆明确拆成三层：

1. **当前任务流状态**：回答“现在在做什么、做到哪、下一步去哪”
2. **跨会话考古 / 追踪层**：回答“上次发生了什么、为什么卡在这里、证据在哪”
3. **长期知识和项目资产的持续沉淀**：回答“以后类似问题都该记住什么”

这三层不能乱混。比如：
- 当前 live task state 不能只写进 task report
- 这轮是否真正收口，不能只靠 `.dev-task.md`
- 跨任务经验不能回写到当前任务卡里

### 2.3 合并与去重结论

本轮的工程判断是：

- **应该收口合并的**
  - Layer B 生命周期定义
  - 运行时记忆术语词典
  - 入口文档对 Layer B 的摘要口径

- **不应该强行合并的**
  - `.dev-task.md` 与 task report
  - `pending-closure` 与 `closure-ledger`
  - `explore-notes` 与 `lessons`
  - `references/backlogs/*.json` 与 `.dev-task.md`

换句话说，这轮不是“把文件并少”，而是“把职责讲清、把重复口径收掉、把真正的真相源保留下来”。

## 3. 本轮落地结果

| 文件 | 变更 | 作用 |
| --- | --- | --- |
| [references/runtime-memory-architecture.md](/Users/norven/.claude/skills/redcap/references/runtime-memory-architecture.md) | 新增 | 定义三层运行时记忆与 Layer B 分布式生命周期协议 |
| [compass/knowledge/runtime-memory-architecture.md](/Users/norven/.claude/skills/redcap/compass/knowledge/runtime-memory-architecture.md) | 新增 | 提供人话词典，方便后续与 Norven/Agent 对话 |
| [compass/tools/redcap-layerb-lifecycle-check.sh](/Users/norven/.claude/skills/redcap/compass/tools/redcap-layerb-lifecycle-check.sh) | 新增 | 机器检查协议、入口口径、术语词典与脚本绑定是否一致 |
| [compass/CONTRIBUTING.md](/Users/norven/.claude/skills/redcap/compass/CONTRIBUTING.md) | 修改 | 改掉“Layer B 无状态机保护”的旧表述 |
| [ARCHITECTURE.md](/Users/norven/.claude/skills/redcap/ARCHITECTURE.md) | 修改 | 把 Layer B 定位修正为分布式控制面生命周期 |
| [README.md](/Users/norven/.claude/skills/redcap/README.md) | 修改 | 在入口层显式挂出协议与词典 |
| [compass/knowledge/index.md](/Users/norven/.claude/skills/redcap/compass/knowledge/index.md) | 修改 | 把词典接入首读导航 |
| [compass/tools/redcap-diagnose.sh](/Users/norven/.claude/skills/redcap/compass/tools/redcap-diagnose.sh) | 修改 | 把新检查接入体检链 |
| [references/execution-guarantees.json](/Users/norven/.claude/skills/redcap/references/execution-guarantees.json) | 修改 | 将 Layer B lifecycle contract 纳入执行保障 |
| [compass/knowledge/lessons.md](/Users/norven/.claude/skills/redcap/compass/knowledge/lessons.md) | 修改 | 沉淀一条关于“分布式控制面必须升格为协议面”的经验 |

## 4. 新术语的人话解释

这轮最值得长期复用的词，我先用一句话固定下来：

- **真相源**：真正能拍板“事实是什么”的地方
- **镜像**：只是把真相源展示出来，方便看，但自己不能改口径
- **闭环证据**：证明“这轮真的做完了、审过了、记账了”的物理证据
- **跨会话考古 / 追踪层**：帮你回头追“上次发生了什么、为什么走到这里、证据在哪”
- **长期知识和项目资产的持续沉淀**：跨任务长期要留下来的经验、路线、设计和研究
- **分布式控制面状态机**：没有单一 `state.yaml`，但由多份账本、gate 和 hook 共同表达状态与转移的工作流

后续 Norven 和 Cap 对话时，如果说“这条信息该放真相源、镜像还是闭环证据”，就不需要每次重新铺长篇背景了。

## 5. 验证

当前已通过的本地验证：

- `bash compass/tools/redcap-layerb-lifecycle-check.sh`
- `bash compass/tools/redcap-execution-guarantee-check.sh`

已完成的外部独立审视：

- `prism/runs/review-layerb-lifecycle-20260422/session-registry.yaml`
  - `copilot_review=responded`：首轮抓出 3 个真实问题
    1. 生命周期转移表把 PM Gate / drift 失败误写到了 `REVIEW_PENDING -> BLOCKED`
    2. `current-status` 被写进 `REANCHORED` 主要载体，authority 与观测面混线
    3. `redcap-layerb-lifecycle-check.sh` 对“基础脚本绑定”的检查说得太满、查得太浅
  - `kimi_review=absent`：首轮大 prompt 未形成结构化结果
- `prism/runs/review-layerb-lifecycle-followup-20260422/session-registry.yaml`
  - `kimi_review=responded`
  - `copilot_review=responded`
  - 两席 follow-up 均给出 `无 blocker`，结论是：三处问题已在当前材料中被修正

最终 closeout 已完成并通过：

- `bash compass/tools/redcap-tracking-health.sh .dev-task.md`
- `bash compass/tools/redcap-diagnose.sh .dev-task.md`
- `bash compass/tools/redcap-docs-catalog.sh generate`
- `bash compass/tools/redcap-docs-catalog.sh check`
- `git diff --check`

## 6. 诚实残留

- 这轮先解决的是“Layer B 生命周期与运行时记忆架构的协议化表达”，不是一刀清理掉整个 RedCap 的所有 archaeology / tracking 资产。
- 本轮形成的是 **轻量独立审视证据**，不是 formal Prism quorum；`prism/runs/...` 已有本地运行证据，但没有新的 formal report / archived quorum。
- 本轮不会把 Layer B 伪装成“和 Layer A 完全同型的单一 FSM”；它仍然是分布式控制面，只是现在终于有了统一协议面和机器检查。

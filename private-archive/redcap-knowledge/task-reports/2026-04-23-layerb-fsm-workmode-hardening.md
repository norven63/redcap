# 任务完成报告：Layer B 状态机工作模式重构

**报告日期**：2026-04-23
**执行者**：Cap（Codex 宿主）
**报告版本**：v0.4

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：Layer B FSM 的状态面、Prism acceptance gate、acceptance binding、closeout runtime 终态事务与相关 checks/acceptance 已经接到同一条工作模式主线上。
- 详情：当前任务的 closeout retry Prism run 已达到 2 席 responded/schema_ok、2 个模型家族且 blocker-free；当前 live 任务已经真实执行 `complete`，`pending closure` 已清，且已写出 closeout receipt。

### 0.2 上一步完成的是

- 上一步完成的是：上一 tranche 已把 Layer B 生命周期协议、closeout runtime、承诺账本、receipt 和 rescue audit 初步接到位，但仍未把“工作模式本体”和“默认独立验收门”真正做成硬门。

### 0.3 下一步计划做的是

- 下一步计划做的是：无当前 tranche 级下一步；后续仅保留长期治理项的独立演进，不再属于本任务的未完成项。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：重新锚定任务 → 落 FSM 状态面 → 落 Prism acceptance gate → 收紧 closeout runtime → 同步入口与模板 → acceptance / 棱镜验收 → 真实 complete 收尾。
- 当前所在位置：FSM 工作模式、默认独立验收门、closeout runtime 终态事务与真实 live closeout 都已闭环完成，当前 confirmed_hash 已进入正式完成态。

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

见 `.dev-task.md` 中的 `Q1~Q5`。

### 1.2 触发背景

本 tranche 直接来自一次真实事故：作者在 live 任务未 formal closeout 的情况下，用接近“已完成”的口径汇报，最终依靠用户人工嗅探与盘问才暴露真相。本次任务的目标不是继续补局部脚本，而是把 Layer B 的工作模式本体重构成更真实的 FSM。

## 二、方案讨论

### 2.1 问题分析

- 旧 Layer B 更像“分散控制面 + 尾段 runtime”，不是“整条工作模式都由 FSM 主骨架统一解释”。
- 独立验收此前只是建议动作，不是 completed 的默认前置门。
- closeout runtime 虽已存在，但如果 acceptance run 不绑定当前 `task_id + confirmed_hash`，旧 run 仍可能被错当成当前任务的验收证据。
- rescue / audit-open 如果覆盖旧 blocker，而不是在旧 blocker 上追加新 blocker，就会破坏 pending closure 的真实性。

### 2.2 决策结果

- 主轴：以 `Layer B FSM 工作模式` 为主，不再以单个 closeout 补丁为主。
- 独立验收：默认交给棱镜，不再依赖作者自证或用户法医式验收。
- 完成判据：必须是承诺账本、棱镜验收、pending closure、receipt 四者同时满足。

## 三、落地结果

### 3.1 当前 tranche 已落地的核心文件

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `compass/tools/redcap-prism-acceptance-bind.py` | 新建 | 把 Prism run 强绑定到当前 `task_id + confirmed_hash + run_id` |
| `compass/tools/redcap-prism-acceptance-bind.sh` | 新建 | shell 入口 |
| `compass/tools/redcap-prism-acceptance-check.py` | 新建 | 新增 Prism acceptance 独立验收 gate |
| `compass/tools/redcap-prism-acceptance-check.sh` | 新建 | shell 入口 |
| `compass/tools/redcap-layerb-fsm.py` | 新建 | 新增 Layer B machine-readable FSM 状态面 |
| `compass/tools/redcap-layerb-fsm.sh` | 新建 | shell 入口 |
| `compass/tools/redcap-layerb-fsm-check.sh` | 新建 | FSM 工作模式接线检查 |
| `compass/tools/redcap-layerb-closeout-runtime.py` | 修改 | 将 Prism acceptance 接入 completed gate，并把 pending 写回默认收紧为 preserve-blockers 语义 |
| `compass/tools/redcap-current-status.py` | 修改 | 输出 `## Layer B FSM` |
| `compass/tools/redcap-diagnose.sh` | 修改 | 接入 `layerb-fsm-check` |
| `references/runtime-memory-architecture.md` 等入口 | 修改 | 把 acceptance binding / preserve-blockers / completed fail-closed 口径同步成权威表达 |

### 3.2 技术实现要点

当前 tranche 的技术主线不是“多补几个检查脚本”，而是把 Layer B 的工作模式主骨架补齐成四层：

1. **状态层**：`redcap-layerb-fsm.py/.sh` 输出 machine-readable 的 Layer B 生命周期状态，避免 `current-status` 只能靠零散账本拼接现状。  
2. **gate 层**：`redcap-prism-acceptance-bind.py/.sh` 与 `redcap-prism-acceptance-check.py/.sh` 把棱镜独立验收变成 completed 的前置门，而且必须绑定当前 `task_id + confirmed_hash + run_id`。  
3. **终态事务层**：`redcap-layerb-closeout-runtime.py` 不再只是“独立子系统”，而是 Layer B 从 `CLOSEOUT_PENDING` 进入 `CLOSED/BLOCKED` 的统一终态事务。  
4. **状态面/检查链消费层**：`redcap-current-status.py`、`redcap-diagnose.sh`、`redcap-layerb-fsm-check.sh` 和相关 acceptance 开始共同消费这套工作模式，而不是只在文档里引用它。

这轮真正解决的，是“FSM 只有尾段像 runtime、独立验收不是硬门、完成态还能被作者口头越权”这三类结构性问题。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| Layer B FSM | `compass/tools/redcap-layerb-fsm.py` | Layer B 当前任务流的机器可读状态面，用来明确现在到底在执行、评审、待收尾还是阻塞 |
| Prism acceptance binding | `compass/tools/redcap-prism-acceptance-bind.py` | 把一轮棱镜验收结果锁定到“这条任务、这个 hash、这次 run”，防止旧 run 被误复用 |
| Prism acceptance gate | `compass/tools/redcap-prism-acceptance-check.py` | completed 前的独立验收闸门；没有有效棱镜验收，就不能走正式完成 |
| closeout runtime | `compass/tools/redcap-layerb-closeout-runtime.py` | Layer B 的终态事务引擎，负责从待收尾进入正式完成或阻塞 |
| preserve-blockers | `bridge_write_pending(..., redline_mode=\"merge\")` | 写入新的 pending closure 时保留旧 blocker，避免新写回把旧红线覆盖掉 |

### 3.3 关联变更

- `references/spec-registry.json` / `references/execution-guarantees.json` 现已把 acceptance binding 纳入 paired/guarantee paths，避免“代码有新 gate，registry 仍按旧 gate 记账”的 authority 漂移。
- `references/runtime-memory-architecture.md` 与 `compass/knowledge/runtime-memory-architecture.md` 补进了 acceptance binding 与 preserve-blockers 语义，避免再把“run 有结果”误说成“当前任务验收已通过”。
- 当前 tranche 的任务报告模板、anchor 与 docs catalog 已对齐到同一版，避免 formal closeout 继续被“多份有效报告并列”或 catalog 漂移卡住。
- 当前 tranche 已完成真实 live closeout，报告、receipt、summary、current-status 与 diagnose 已开始按 completed 态对齐。

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 棱镜默认独立验收是否仍被维持为 completed 前置门 | 这是本 tranche 的主目标，不允许后续再退回作者自证完成 | P0 |
| 2 | acceptance binding 是否持续要求 `task_id + confirmed_hash + run_id` 三重绑定 | 这是防止旧 run 复用的关键物理门 | P0 |
| 3 | audit-open/pending closure 是否继续保留旧 blocker 集合 | 若回退成覆盖式写回，会再次破坏 closeout 真相源 | P0 |
| 4 | live closeout 完成后，report / receipt / current-status 是否保持一致 | 本 tranche 已完成这条一致性收口；后续若再变更报告，需要同步重刷 receipt/summary | P1 |

## 五、验证结果

### 5.1 当前已完成的验证

| 验证项 | 结果 |
|--------|------|
| `redcap-layerb-lifecycle-check.sh` | ✅ |
| `redcap-layerb-fsm-check.sh` | ✅ |
| `redcap-layerb-closeout-runtime-check.sh .dev-task.md` | ✅ |
| `redcap-prism-acceptance-check.sh --task-file .dev-task.md` | ✅（`review-layerb-fsm-workmode-closeout-retry-20260423`，2 席 responded，2 家族，无 blocker） |
| `prism-acceptance-binding-required` acceptance | ✅ |
| `review-proof-check-accepts-prism-acceptance` acceptance | ✅ |
| `pending-closure-clear-locked-mode` acceptance | ✅ |
| `session-end-clears-closeout-runtime-pending` acceptance | ✅ |
| `layerb-closeout-runtime-audit-open-preserves-existing-blockers` acceptance | ✅ |
| `redcap-spec-check.sh "$PWD"` | ✅ |
| `redcap-current-status.sh .dev-task.md` | ✅ 已诚实显示 independent-acceptance=pass / receipt=present |

### 5.2 当前 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已完成（6/6） |
| 棱镜验收 | 已通过（`review-layerb-fsm-workmode-closeout-retry-20260423`） |
| closeout receipt | 已生成（`/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/layerb-fsm-workmode-hardening-73fc9acfaeb64441f5e48277fe536c985424f4f56109de2538b26190f42a0657.json`） |

### 5.3 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是（以棱镜 follow-up 为准） |
| 已正式完成 | 是（receipt 已生成，live closeout 已执行） |

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 无当前 tranche 级遗留问题 | 当前 confirmed_hash 已正式完成；剩余仅是独立长期治理项，不属于本任务未完成项 | P2 |

### 6.2 触发的新问题

- 本轮额外修掉了两条真实 runtime 断路：一是 `session-end` 在持有 pending-closure 锁时再次调用 clear 导致自锁；二是 live closeout 未导出 `REDCAP_SESSION_BINDING_KEY`，让 `session-end` 误入 `missing-runtime-claim` 降级分支。

### 6.3 推荐的下一步行动

1. 无当前 tranche 级下一步
2. 后续若继续治理长期项，需新开独立 tranche，并保持“先独立验收、再 receipt 完成”的同一 FSM 口径

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-111 | Layer B FSM 的 completed 必须晚于 receipt | 工作模式重构、检查链和独立验收都落地后，仍只有 receipt 能把“已实现/已验收”与“已正式完成”真正分开 |
| L-112 | Prism acceptance 必须绑定当前 task 与 hash | 默认独立验收如果不绑定 `task_id + confirmed_hash + run_id`，旧 run 就可能被误复用，completed gate 会失真 |
| L-113 | live closeout 必须显式携带 runtime binding key | 只传 runtime session/capability 不够，`session-end` 仍会因拿不到 binding key 而误降级成 missing-runtime-claim |
| L-114 | session-end 成功路径不能在持锁状态下调用会再次拿锁的 clear 函数 | 否则 validator 全绿也会因为运行时自锁而卡成 unresolved |

### 7.2 流程改进建议

- Layer B FSM 的 machine-readable 状态面、Prism acceptance gate 与 closeout runtime 必须一起演进；只改其中一层会再次出现“协议领先于实现”。
- 任务报告模板要优先兼容机器审计，再谈表达优化；否则 formal closeout 会被结构门禁卡住。

## 八、附录

### 8.1 相关文档索引

- 任务锚点：[.dev-task.md](/Users/norven/.claude/skills/redcap/.dev-task.md)
- 方案设计：[2026-04-23-layerb-fsm-workmode-rebuild.md](/Users/norven/.claude/skills/redcap/compass/docs/specs/2026-04-23-layerb-fsm-workmode-rebuild.md)
- 补充设计：[2026-04-22-layerb-closeout-runtime-and-promise-ledger-design.md](/Users/norven/.claude/skills/redcap/compass/docs/specs/2026-04-22-layerb-closeout-runtime-and-promise-ledger-design.md)
- 协议面：[runtime-memory-architecture.md](/Users/norven/.claude/skills/redcap/references/runtime-memory-architecture.md)

### 8.2 棱镜记录

- closeout retry run：[review-layerb-fsm-workmode-closeout-retry-20260423/session-registry.yaml](/Users/norven/.claude/skills/redcap/prism/runs/review-layerb-fsm-workmode-closeout-retry-20260423/session-registry.yaml)
- acceptance binding：[acceptance-binding.json](/Users/norven/.claude/skills/redcap/prism/runs/review-layerb-fsm-workmode-closeout-retry-20260423/artifacts/acceptance-binding.json)
- closeout receipt：[/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/layerb-fsm-workmode-hardening-73fc9acfaeb64441f5e48277fe536c985424f4f56109de2538b26190f42a0657.json](/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/layerb-fsm-workmode-hardening-73fc9acfaeb64441f5e48277fe536c985424f4f56109de2538b26190f42a0657.json)

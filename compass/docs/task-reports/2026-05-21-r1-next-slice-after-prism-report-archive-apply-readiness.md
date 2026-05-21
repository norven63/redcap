# 任务完成报告：P4-14 发布前下一小切片选择

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-14 已通过 Claude Code 与 Kimi 的棱镜路线评审，选定下一条正式发布前安全小切片：`Prism report archive churn/freeze guard`。
- 人话解释：下一步先解决“每新增一份正式 Prism 报告，归档计划就过期”的问题；还不是开始真实复制报告。

### 0.2 上一步完成的是

- 上一步完成的是：P4-13 已完成 Prism report archive apply readiness / rehearsal。它证明未来 copy-first apply 可以先演练，但仍没有真实复制、移动、删除报告，没有退休旧锚点，也没有清理 raw evidence。

### 0.3 下一步计划做的是

- 下一步计划做的是：进入 P4-15，只做 Prism report archive 的 churn/freeze guard，让后续 live copy-first apply 有稳定的报告集合规则。
- 关键边界：P4-15 仍然不执行物理复制、移动、删除，不清理 raw evidence，不关闭整个 `prism-layer-and-evidence` blocker。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：正式发布准备路线 → 控制面与 Prism 预检 → runtime facade → Prism package-visible support → Prism report archive 预检 → 迁移规划 → apply readiness / rehearsal → **P4-14 下一切片选择** → P4-15 churn/freeze guard → 后续 live copy-first apply。
- 当前所在位置：`framework-upgrade / P4-14`，属于路线选择与后续锚点登记，不是具体迁移实现，也不是正式发布。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触碰许可证、registry、凭据、发布开关、私密文件、旧锚点删除、raw evidence cleanup 或 Layer A 产品范围裁决。

## 一、需求背景

P4-13 之后，技术上已经可以讨论 live copy-first apply。但这条路线还有一个刚刚反复出现的风险：每做一次正式 Prism 评审，就会新增一份 `prism/reports` 报告；而 P4-12/P4-13 的计划和演练都绑定当前报告集合、数量与 hash。

如果不先定义 churn/freeze 规则，未来 live apply 很容易变成“每推进一步都先修一次快照漂移”。P4-14 的价值就是先选清楚：下一步先补这个稳定性 guard，再进入真实 copy-first apply。

## 二、方案讨论

### 2.1 棱镜分歧

| Agent | 建议 | 理由 |
| --- | --- | --- |
| Claude Code | 选择 A：live copy-first apply | P4-12/P4-13 已完成 plan 和 rehearsal，copy-first 不删除旧锚点，理论上可继续推进。 |
| Kimi | 选择 B：churn/freeze guard | 新增正式 Prism report 会持续让 report_count/hash 过期，应先把这个风险机制化。 |

Cap 裁决选择 B。原因不是否定 A，而是把 A 延后一步：先让计划稳定，再做真实复制。

### 2.2 边界裁决

本轮不执行真实发布，不改许可证、registry、凭据或发布开关，也不读取 `.env`。本轮只完成路线评审、路线资产、后续任务登记和派生账本刷新。

## 三、落地结果

### 3.1 当前效果

RedCap 的长期路线现在从“P4-13 后可能直接 live apply”变成“先补 churn/freeze guard，再考虑 live apply”。这降低了后续真实复制时的快照漂移风险，也避免把 readiness 直接升级成真实迁移。

### 3.2 已验证

- Claude Code 已完成独立评审，建议 live copy-first apply。
- Kimi 已完成独立评审，建议 churn/freeze guard。
- Cap 已记录分歧并裁决更保守的小切片。
- Copilot 未调用，符合 protected fallback 策略。
- Gemini 未加入 quorum，原因是当前可用性检查返回 Operation not permitted；Claude Code 与 Kimi 已满足双视角评审。
- `references/r1-next-slice-after-prism-report-archive-apply-readiness.json` 已记录候选矩阵、边界与下一切片。
- 因本轮新增任务报告导致活跃 task report 收件箱超过上限，已把旧报告 `2026-05-19-r1-control-plane-runtime-public-support-copy-first-apply.md` 转入私有冷归档，并刷新 cold archive inventory；这只降低活跃入口压力，不删除考古证据。

### 3.2.1 术语对照（按文件/功能解释）

| 文件/功能 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| churn/freeze guard | 报告集合变化的防漂移规则 | 让后续归档计划知道哪些新增报告是计划内，哪些是异常漂移。 |
| live copy-first apply | 真实创建归档副本，但不删除旧文件 | 是合理后续方向，但本轮不直接进入。 |
| report_count/hash drift | 报告数量或文件哈希变了 | 会让旧计划失效，必须被显式处理。 |
| 路线决策资产 | 一份机器可读的下一步选择记录 | 记录为什么 P4-14 选择 P4-15，而不是直接进入真实复制。 |

## 四、人工审核要点

| 审核项 | 说明 |
| --- | --- |
| 无需本轮人工审核 | 本轮只完成路线评审、后续锚点登记与报告归档，不触碰人工保留决策。 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 当前结果 |
| --- | --- |
| PM Gate | 通过 |
| change-intake | 通过 |
| intent coverage | 通过 |
| Prism review | Claude Code + Kimi 已返回，无 blocker |
| Prism acceptance | 通过 |
| report archive plan / readiness checks | 通过 |
| package surface / runtime contract checks | 通过 |
| information architecture / cold archive inventory | 通过 |
| spec-check | 通过 |
| diagnose | closeout receipt 生成前仍显示 pending closure，符合当前阶段 |
| clean workspace E2E | 待提交当前账本后复跑 |

### 5.3 closeout runtime / receipt

| 项目 | 当前结果 |
| --- | --- |
| 执行承诺账本 | 待 closeout runtime 最终核对 |
| closeout receipt | 待生成 |

### 5.4 完成等级（禁止混报）

| 层级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 是 | 路线评审、路线资产、Prism 报告已落地。 |
| 已自检 | 进行中 | PM Gate、change-intake、intent coverage 已通过；full spec/diagnose/clean E2E 待最终复跑。 |
| 已独立验收 | 是 | Claude Code 与 Kimi 均已返回，无 blocker，存在路线分歧但已裁决。 |
| 已正式完成 | 否 | 需要最终 Prism acceptance、spec-check、diagnose、clean workspace E2E 与 closeout receipt。 |

## 六、遗留问题与下一步

| 问题 | 当前处理 | 建议优先级 |
| --- | --- | --- |
| Prism report archive churn/freeze guard | 已选为 P4-15 | P0-before-release |
| live copy-first apply | 等 P4-15 后重新评审 | future-after-guard |
| old-anchor retirement | 必须等待 live copy-first apply、alias proof、archive-check 和单独 delete-last receipt | future-after-apply |
| raw evidence cleanup | 仍需保存证明和按需人工批准 | manual-boundary-if-destructive |
| `prism-layer-and-evidence` blocker | 仍然开放 | P0-before-release |

## 七、经验沉淀

### 7.1 新增 Lesson 候选

| 标题 | 问题源 | 解决方案 | 最后效果 |
| --- | --- | --- | --- |
| 正式审查报告会改变被审查集合 | Prism report archive 计划绑定 `prism/reports` 集合，而每次 formal Prism review 又会新增报告 | 先建立 churn/freeze guard，再进入 live copy-first apply | 防止后续每一步都因 report_count/hash 漂移而临时补账。 |

### 7.2 是否晋升正式 lesson

暂不晋升正式 lesson。P4-15 会把这个候选直接固化成机器策略；若未来其他资产集合也出现“审查产物改变被审查集合”的问题，再晋升为跨任务 lesson。

### 7.3 Evolution Factory 候选处理

no-promote

本轮已经识别出一个高价值模式：审查产物本身会改变被审查集合，从而导致计划快照反复漂移。处理方式不是直接新增长期经验条目，而是把它作为 P4-15 的机器策略输入：先建立 churn/freeze guard，再决定是否晋升为跨场景 lesson。owner=RedCap Forge；trigger=P4-15 完成后复查是否存在同类资产集合漂移。

## 八、附录

- 当前任务卡：`.dev-task.md`
- 路线决策资产：`references/r1-next-slice-after-prism-report-archive-apply-readiness.json`
- Prism review 报告：`prism/reports/2026-05-21-r1-next-slice-after-prism-report-archive-apply-readiness.md`
- Prism 运行目录：`prism/runs/20260521-r1-next-slice-after-prism-report-archive-apply-readiness/`
- 长期路线权威：`references/backlogs/framework-upgrade.json`

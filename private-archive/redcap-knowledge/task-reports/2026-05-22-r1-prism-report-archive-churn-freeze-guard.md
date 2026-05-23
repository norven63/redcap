# 任务完成报告：P4-15 Prism 报告归档漂移冻结

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-15 已把 Prism 报告归档迁移集合从“实时目录数量”改成“冻结集合 + 后冻结报告登记”。
- 人话解释：以前每新增一份正式 Prism 审查报告，P4-12/P4-13 的迁移计划就会被判定为过期；现在已验证的 55 份报告被固定为当前迁移集合，新报告必须单独登记，不能偷偷改变旧计划。

### 0.2 上一步完成的是

- 上一步完成的是：P4-14 通过 Claude Code 与 Kimi 的路线评审，选择先做 churn/freeze guard，而不是直接进入 live copy-first apply。

### 0.3 下一步计划做的是

- 下一步计划做的是：在 P4-15 收口后，重新评审是否进入 Prism report archive live copy-first apply。
- 关键边界：下一步即使进入 live apply，也仍应保持 copy-first / delete-last：先复制、先验收、旧锚点后删，且 raw evidence cleanup 仍需单独批准。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：正式发布准备路线 → Prism 证据保留拆分 → Prism 报告归档预检 → 迁移规划 → apply readiness / rehearsal → 下一切片选择 → **P4-15 漂移冻结** → 后续 live copy-first apply。
- 当前所在位置：`framework-upgrade / P4-15`，属于发布前 Prism 报告归档治理，不是正式发布，也不是旧锚点退休。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触碰许可证、registry、凭据、发布开关、私密文件、旧锚点删除、raw evidence cleanup 或 Layer A 产品范围裁决。

## 一、需求背景

P4-12/P4-13 已经完成了报告归档规划与临时目录演练，但它们有一个结构性坏味：计划把 `prism/reports/*.md` 的实时数量当成当前迁移集合。Prism 的正式评审本身又会新增报告，于是“审查动作”会改变“被审查集合”，导致 report_count、mapping、hash 和 package candidate 快照反复漂移。

本轮要解决的不是“把报告搬走”，而是先让迁移集合稳定下来。这样后续真实 copy-first apply 不会每推进一步都先修一次快照账本。

## 二、方案讨论

### 2.1 最终方案

采用独立 freeze/churn guard：

- 已验证的 P4-12/P4-13 `archive_plan.mappings` 是当前冻结迁移集合。
- 新增正式 Prism 报告允许继续留在 `prism/reports`，但必须登记为 `post_freeze_reports`。
- 未登记的新报告会让检查器失败，避免 silent drift。
- 未来如果要把后冻结报告吸收到新的迁移集合，必须另开路线决策、Prism 评审与 closeout receipt。

### 2.2 为什么不是直接 live apply

live copy-first apply 是合理后续方向，但在没有 freeze guard 前，它会继续受报告自增影响。P4-15 先修“集合边界”，再讨论“真实复制”，风险更低，也更符合小切片推进原则。

## 三、落地结果

### 3.1 当前效果

- P4-12/P4-13 的当前迁移集合被固定为 55 份报告。
- 本轮新增的正式 Prism 报告已登记为 post-freeze report，不再进入当前迁移计划。
- 未登记新增报告的负例已在隔离副本中验证：检查器会失败。
- package candidate 数量从 288 更新为 291，原因是新增 3 个 package-visible control-plane readiness 资产；这仍然只是发布前 readiness 支撑，不是正式发布授权。

### 3.2 已验证

- Claude Code 评审结论：pass。
- Kimi 评审结论：pass。
- Prism acceptance binding：pass。
- 未登记新增报告负例：pass，检查器按预期 fail-closed。
- `redcap-spec-check.sh`：已通过。
- `redcap-r1-prism-report-archive-*` 相关局部检查：已通过。

### 3.2.1 术语对照（按文件/功能解释）

| 文件/功能 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| freeze/churn guard | 防止报告集合自增扰动旧计划的规则 | 把旧迁移集合冻结，要求新增报告单独登记。 |
| frozen mappings | 已验证的 55 份迁移候选 | 当前真实 copy-first apply 未来应先围绕这批报告推进。 |
| post-freeze report | 冻结后新增的正式报告 | 可以存在，但不能自动混入当前迁移计划。 |
| silent drift | 没有记录、没有评审、没有收口的隐性漂移 | 本轮通过差集检查和 hash 锁定阻断。 |

## 四、人工审核要点

| 审核项 | 说明 |
| --- | --- |
| 无需本轮人工审核 | 本轮是机器规则、评审和账本同步，不触碰人工保留决策。 |
| 未来需要人工介入的边界 | raw evidence 物理清理、旧锚点删除导致历史损失、许可证、registry、正式公开发布动作、Layer A 产品边界。 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 当前结果 |
| --- | --- |
| PM Gate | 通过 |
| change-intake | 通过 |
| intent coverage | 通过 |
| Prism review | Claude Code + Kimi 已返回 pass |
| Prism acceptance | 通过 |
| 未登记 post-freeze 报告负例 | 通过，隔离副本新增未登记报告会失败 |
| report archive preflight / plan / readiness / guard | 通过 |
| package surface / runtime contract / R1 派生快照 | 通过 |
| docs catalog / cold archive inventory | 通过 |
| spec-check | 通过 |

### 5.3 closeout runtime / receipt

| 项目 | 当前结果 |
| --- | --- |
| 执行承诺账本 | 待最终 closeout 核对 |
| closeout receipt | 待最终 closeout 生成 |

### 5.4 完成等级（禁止混报）

| 层级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 是 | freeze guard、checker、plan checker 接入、spec/diagnose 接入已完成。 |
| 已自检 | 是 | 局部检查、负例、spec-check 已通过。 |
| 已独立验收 | 是 | Claude Code 与 Kimi 均 pass，无 blocker。 |
| 已正式完成 | 待 closeout | 还需 full diagnose、clean workspace E2E 和 closeout receipt。 |

## 六、遗留问题与下一步

| 问题 | 当前处理 | 建议优先级 |
| --- | --- | --- |
| live copy-first apply | P4-15 后重新评审 | P0-before-release |
| old-anchor retirement | 必须等待 copy-first apply、alias proof、archive-check 和单独 delete-last receipt | future-after-apply |
| raw evidence cleanup | 仍需保存证明和按需人工批准 | manual-boundary-if-destructive |
| guard checker 与 plan checker 有重复逻辑 | 棱镜认为非阻塞 | future-maintenance |
| guard-aware 模式是隐式的 | 已通过 guard 资产和字典说明补偿 | future-maintenance |

## 七、经验沉淀

### 7.1 新增 Lesson 候选

| 标题 | 问题源 | 解决方案 | 最后效果 |
| --- | --- | --- | --- |
| 审查产物不能无控制地改变被审查集合 | Formal Prism review 会新增报告，旧计划又把实时报告数量当真相 | 建立冻结集合与 post-freeze 登记规则，并用负例证明未登记新增会失败 | 后续新增审查报告不再反复打爆旧迁移计划。 |

### 7.2 是否晋升正式 lesson

no-promote

本轮已经把经验直接固化为机器规则和检查器，暂不再复制成一条长期 lesson，避免知识库重复。若未来在非 Prism 报告集合中再次出现“产物改变被审查集合”的同类问题，再晋升为跨场景 lesson。

### 7.3 Evolution Factory 候选处理

no-promote

原因：高价值信号已经在本轮以机器策略形式落地到 `references/r1-prism-report-archive-churn-freeze-guard.json` 和对应检查器；继续新增 Evolution candidate 会造成重复入口。owner=RedCap Forge；trigger=未来若第二类资产集合出现同类 churn 时，将本经验晋升为通用集合冻结模式。

## 八、附录

- 当前任务卡：`.dev-task.md`
- Guard 资产：`references/r1-prism-report-archive-churn-freeze-guard.json`
- Guard 检查器：`compass/tools/redcap-r1-prism-report-archive-churn-freeze-guard-check.sh`
- Prism review 报告：`prism/reports/2026-05-22-r1-prism-report-archive-churn-freeze-guard.md`
- Prism 运行目录：`prism/runs/20260522-r1-prism-report-archive-churn-freeze-guard/`
- 冷归档调整：`private-archive/redcap-knowledge/task-reports/2026-05-19-r1-control-plane-physical-split-dry-run.md`

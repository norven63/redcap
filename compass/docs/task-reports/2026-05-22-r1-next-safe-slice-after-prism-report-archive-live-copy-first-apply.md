# 任务完成报告：P4-17 Prism 报告归档后的下一安全切片选择

**报告日期**：2026-05-22
**执行者**：Cap（Codex.app 主执行，Prism 使用 Claude Code + Kimi）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-16 之后的下一安全切片已经选定；下一步先做正式发布就绪差距地图，而不是直接删除旧报告、清理原始证据、裁决 Layer A 或进入正式发布。
- 详情：Claude Code 和 Kimi 都完成了独立路线评审。两边对下一刀有分歧：Claude Code 建议先恢复全局发布视角，Kimi 建议顺着 copy-first 链路做旧锚点 delete-last 预检。Cap 选择更保守的全局收敛评估，防止长时间局部推进后遗漏其他 blocker。

### 0.2 上一步完成的是

- 上一步完成的是：P4-16 已把冻结的 55 份 Prism 报告复制到私有归档区，并继续保留旧 `prism/reports` 锚点。
- 详情：P4-16 只证明“已有安全副本且旧锚点还在”，不证明旧路径已经可以删除，也不证明 `prism/runs` raw evidence 可以清理，更不证明 RedCap 已经具备正式发布条件。

### 0.3 下一步计划做的是

- 下一步计划做的是：P4-18 将做正式发布就绪收敛评估，把 internal-control-plane、prism-layer-and-evidence、Layer A 产品边界和包面状态整理成一张剩余差距地图。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-12 规划报告归档集合 → P4-13 临时演练 → P4-15 冻结集合防漂移 → P4-16 真实 copy-first 副本 → P4-17 选择下一安全切片 → P4-18 汇总正式发布前剩余差距。
- 当前所在位置：framework-upgrade / P4-17，处在 release-route-selection 的最终收口前阶段；路线评审、manifest、Prism 报告和 backlog 更新已完成，receipt 还需最终 closeout 生成。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要
- 说明：本轮没有触碰 Norven 保留决策。Layer A 产品范围、raw evidence cleanup、正式发布开关和旧锚点真实 delete-last 都继续保持禁止；后续若要执行这些动作，再进入人工决策。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，那你们按照自己的规划去继续稳步推进吧

### 1.2 触发背景

P4-16 完成后，RedCap 面前至少有四条可能路线：旧报告锚点 delete-last、`prism/runs` raw evidence 治理、Layer A 产品边界、正式发布就绪收敛。它们的风险类型完全不同。如果不先做路线选择，“继续推进”很容易被误解成直接删除旧报告、清理证据或进入发布。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | route-only |
| 原始意图 | 继续推进 RedCap 主线，不中断等待人工决策 |
| 已覆盖 | 完成 P4-17 路线评审、棱镜分歧记录、Cap 裁决、下一任务登记和报告归档 |
| 未覆盖/延期 | 未执行旧锚点退休、raw evidence cleanup、Layer A 产品裁决、许可证选择、registry 操作或正式公开发布动作 |
| 用户可见边界 | 只能声明“下一条安全切片已选定”；不能声明“旧报告路径已下线”“证据已清理”“Layer A 已裁决”或“已可正式公开发布” |
| 后续路径 | P4-18 进入正式发布就绪收敛评估，再按差距地图选择后续执行切片 |

---

## 二、方案讨论

### 2.1 问题分析

P4-17 的核心不是实现某个功能，而是防止下一步走错。P4-16 已经完成一条局部链路的重要节点，如果继续只沿着 Prism 报告归档链路前进，可能会忽略更上层的发布差距；如果直接进入 raw evidence cleanup 或 Layer A 产品裁决，又会越过人工保留边界。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 旧锚点 delete-last 预检 | 为未来退休旧 `prism/reports` 锚点准备证明和回滚方案 | 延续 copy-first 链路，Kimi 推荐 | 仍然锁在局部报告归档链路 |
| Q1 | raw evidence 保全/清理 | 处理 `prism/runs` 原始证据生命周期 | 直面证据堆积 | cleanup apply 需要人工批准，风险高 |
| Q1 | Layer A 产品边界 | 决定 Layer A 是否进入公开产品 | 能解除产品边界疑问 | 属于 Norven 保留产品决策 |
| Q1 | 正式发布就绪收敛评估 | 合成剩余 blocker、人工决策点和下一步排序 | 零破坏、无需人工决策、恢复全局视角 | 不直接关闭 blocker |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 正式发布就绪收敛评估 | 它不删除文件、不清理证据、不替用户做产品选择，可以在不越界的前提下恢复全局发布视角 | CAP_DECIDE + Prism review |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `references/r1-next-safe-slice-after-prism-report-archive-live-copy-first-apply.json` | 新建 | 记录候选矩阵、棱镜分歧、Cap 裁决和 P4-18 边界 |
| `references/backlogs/framework-upgrade.json` | 修改 | P4-17 标记完成，P4-18 登记为下一条 pending |
| `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` | 修改 | 同步人类可读长期路线视图 |
| `prism/reports/2026-05-22-r1-next-safe-slice-after-prism-report-archive-live-copy-first-apply.md` | 新建 | 保存本轮 Prism 路线评审结论 |
| `prism/reports/index.yaml` | 修改 | 把 P4-17 Prism 报告加入正式报告索引 |
| `references/r1-prism-report-archive-churn-freeze-guard.json` | 修改 | 把 P4-17 报告登记为 post-freeze，避免冻结集合被新报告扰动 |
| `references/r1-prism-report-archive-live-copy-first-apply.json` | 修改 | 同步 P4-15 guard hash 和 post-freeze 报告边界 |
| `compass/docs/catalog.json` | 修改 | 刷新 docs 首读索引 |

### 3.2 技术实现要点

本轮把“继续推进”转成可审计的路线选择，而不是直接执行下一步。机器 manifest 明确写出四个候选方向、每个方向的风险、是否需要人工决策、是否破坏性，以及 Cap 为什么选择 release readiness convergence。

新增 Prism 报告后，P4-15/P4-16 的报告归档守卫必须同步知道它是 post-freeze 报告。这样新评审报告不会被误纳入 P4-12/P4-15 冻结的 55 份归档集合，也不会让旧检查器因为报告数量增加而误炸。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| route selection | `references/r1-next-safe-slice-after-prism-report-archive-live-copy-first-apply.json` | 只决定下一步先做什么，不等于把下一步已经做完 |
| release readiness convergence | P4-18 下一切片 | 把所有发布前剩余差距整理成一张地图，避免只盯局部问题 |
| delete-last | 旧锚点退休后续任务 | copy-first 后可能删除旧位置，但必须单独证明、单独收口 |
| post-freeze report | `references/r1-prism-report-archive-churn-freeze-guard.json` | 冻结归档集合后新增的评审报告；它不能自动进入已冻结的迁移集合 |
| Prism acceptance | `prism/runs/20260522-r1-next-safe-slice-after-prism-report-archive-live-copy-first-apply/session-registry.yaml` | Claude Code 与 Kimi 的独立评审证据，用来防止 Cap 单视角裁决 |

### 3.3 关联变更

新增 P4-17 正式 Prism 报告后，runtime package candidate 数从 294 增加到 295。增加的是路线评审报告本身；私有归档、旧报告锚点和 raw evidence 仍保持包面排除。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无必须人工审核项 | 本轮只做路线选择，不触碰用户保留决策；进入真实 delete-last、raw evidence cleanup、Layer A 裁决或正式发布时才需要人工介入 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| PM Gate | `bash compass/tools/redcap-pm-gate-check.sh strict codex .dev-task.md` | 通过 |
| 意图覆盖 | `bash compass/tools/redcap-intent-coverage-check.sh .dev-task.md` | 通过 |
| P4-15 冻结守卫 | `bash compass/tools/redcap-r1-prism-report-archive-churn-freeze-guard-check.sh` | 通过 |
| P4-16 live apply 检查 | `bash compass/tools/redcap-r1-prism-report-archive-live-copy-first-apply-check.sh` | 通过 |
| Prism archive 报告归档 | `bash prism/tools/prism-archive-check.sh --report prism/reports/2026-05-22-r1-next-safe-slice-after-prism-report-archive-live-copy-first-apply.md` | 通过 |
| docs catalog | `bash compass/tools/redcap-docs-catalog.sh check` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无必须人工验证项；本轮没有执行会改变用户产品决策或删除证据的动作。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 收口前待最终核对 |
| 棱镜验收 | Claude Code 与 Kimi 已完成，split decision 后由 Cap 保守裁决 |
| closeout summary | 收口前待生成 |
| closeout receipt | 收口前待生成 |
| rescue audit（如有） | 当前无 rescue audit |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Claude Code 与 Kimi 已完成路线评审 |
| 已正式完成 | 否，closeout receipt 还需最终生成 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 旧 `prism/reports` 锚点退休 | 需要 delete-last 专项证明和回滚方案，不能和路线选择混做 | P0 |
| `prism/runs` raw evidence cleanup | 涉及证据保全与可能的人类授权边界，不能在本轮执行 | P0 |
| Layer A 产品范围裁决 | 属于 Norven 产品边界，不由 Cap 或棱镜裁决 | P1 |
| 正式公开发布动作 | 仍需许可证、发布开关、registry、版本等人工保留决策 | P0 |

### 6.2 触发的新问题

本轮暴露了一个路线治理提醒：当某条局部链路已经连续推进多刀后，下一刀不一定继续沿局部链路推进，可能应该先做全局收敛，防止局部优化掩盖整体发布差距。

### 6.3 推荐的下一步行动

1. 完成本轮 closeout runtime，生成 P4-17 receipt。
2. 进入 P4-18：正式发布就绪收敛评估。
3. P4-18 后再决定是否进入旧锚点 delete-last 预检、raw evidence 治理或人工产品决策。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| no-promote | 局部链路完成关键节点后，优先考虑全局收敛评估 | 本轮经验已写入报告与路线 manifest；暂不写入全局 lessons，避免把一次路线裁决升级成通用硬规则 |

### 7.2 流程改进建议

路线选择任务的输出不应只是“下一步做什么”，还必须写清楚“不做什么”。这能防止后续任务把路线选择误读成执行授权。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| no-promote | P4-17 路线裁决 | 不新增 Evolution candidate；本轮属于 release-readiness 局部路线治理，不沉淀为公共 skill 或长期知识 | `references/r1-next-safe-slice-after-prism-report-archive-live-copy-first-apply.json` |

---

## 八、附录

### 附录 A：Commits

```
本报告生成时尚未提交；最终 commit 会在 closeout 后记录。
```

### 附录 B：棱镜调用记录（如有）

| Agent | 角色 | 状态 | 结论 |
|------|------|------|------|
| Claude Code | reviewer | responded | 推荐正式发布就绪收敛评估 |
| Kimi | challenger | responded | 推荐旧锚点 delete-last 预检 |
| Copilot | fallback | absent | Claude Code 与 Kimi 可用，按策略未调用 |

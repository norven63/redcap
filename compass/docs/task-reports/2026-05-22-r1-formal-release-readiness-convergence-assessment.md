# 任务完成报告：P4-18 正式发布就绪收敛评估

**报告日期**：2026-05-22
**执行者**：Cap（Codex.app 主执行，Prism 使用 Claude Code + Kimi）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：正式发布前剩余差距已经整理成一张地图。结论很明确：RedCap 还不能正式公开发布，但现在知道还卡在哪里、哪些已经不用反复怀疑、下一刀应该先做什么。
- 详情：Claude Code 和 Kimi 都确认 P4-18 没有越权授权发布、删除证据或裁决 Layer A。两边都认为 release 仍然 blocked，主要差距集中在控制面物理拆分、Prism 证据层、Layer A 产品边界、发布授权/许可证、历史资产清理硬门和外部机器验证。

### 0.2 上一步完成的是

- 上一步完成的是：P4-17 已经选择“先做正式发布就绪收敛评估”作为 P4-18，而不是直接进入旧锚点退休、raw evidence cleanup、Layer A 裁决或正式发布。

### 0.3 下一步计划做的是

- 下一步计划做的是：P4-19 将先做旧 `prism/reports` 锚点 delete-last 预检。注意这是预检，不是真实删除；它只回答“未来是否具备安全退休旧锚点的条件”。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-16 完成 Prism 报告 copy-first → P4-17 选择先做全局差距地图 → P4-18 完成正式发布差距地图 → P4-19 做旧报告锚点退休预检。
- 当前所在位置：framework-upgrade / P4-18 已完成主体落地，等待 closeout receipt 最终生成；P4-19 已登记为下一步。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要
- 说明：本轮只做评估和排序，没有触碰人工保留决策。许可证、发布开关、registry、Layer A 产品边界、真实删除和 raw evidence cleanup 都继续保持禁止。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，那你们按照自己的规划去继续稳步推进吧

### 1.2 触发背景

P4-17 裁决后，如果继续只沿着某条局部链路前进，RedCap 可能再次出现“局部任务做了很多，但不知道离正式发布还差什么”的问题。P4-18 的目的就是先停在工程层面做一次全局收敛：把 blocker、人工决策、已满足证据和下一步顺序放到同一张图里。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | route-only |
| 原始意图 | 继续推进 RedCap 主线，不中断等待人工决策 |
| 已覆盖 | 完成正式发布前差距地图、棱镜评审、Cap 裁决、下一任务登记和报告归档 |
| 未覆盖/延期 | 未执行真实发布、旧锚点退休、raw evidence cleanup、Layer A 产品裁决、许可证选择或 registry 操作 |
| 用户可见边界 | 只能声明“正式发布前差距已整理并排序”；不能声明“已经可正式发布”或“所有 blocker 已关闭” |

---

## 二、方案讨论

### 2.1 问题分析

P4-18 把 release readiness 拆成四类信息：仍然阻塞正式发布的事项、只能由 Norven 决策的事项、已经满足不该反复怀疑的事项、以及后续可以由 Cap/Prism 自主推进的小切片。

这个划分很重要，因为它避免两个错误：一是把 preflight 冒充成 blocker 已关闭；二是把每个已完成的基础能力都重新当成 open blocker，导致任务永远无法前进。

### 2.2 收敛结论

| 分类 | 结论 |
|---|---|
| 发布硬阻塞 | internal-control-plane、prism-layer-and-evidence、internal-layer-a、发布授权/许可证、历史资产清理硬门、外部机器验证 |
| 人工保留决策 | 许可证、是否公开发布、release level、registry/account、Layer A 产品边界、真实删除或证据清理 |
| 已满足证据 | 包安全扫描、clean workspace E2E、workspace-state 包面排除、CLI/runtime 基线、R1 preflight analysis、Prism 报告 copy-first |
| 需要继续看住的风险 | package candidate 计数政策语言存在 280/295 不一致；clean workspace E2E 不能冒充多 OS 外部验证 |

### 2.3 下一步裁决

| 选项 | 结论 | 原因 |
|---|---|---|
| old `prism/reports` anchor delete-last preflight | 采纳为 P4-19 | 范围最小，只做预检，不真实删除；可以闭合 P4-16 copy-first 生命周期的下一步证明 |
| internal-control-plane physical split | 排名第二 | 影响最大，但 blast radius 更大，需要更谨慎的 copy-first 任务 |
| package policy wording reconciliation | 排名第三 | 有必要，但不是下一条最高价值 release blocker 切片 |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `references/r1-formal-release-readiness-convergence-assessment.json` | 新建 | 记录正式发布差距地图、人工决策、已满足证据、风险与 P4-19 推荐 |
| `references/backlogs/framework-upgrade.json` | 修改 | P4-18 标记完成，P4-19 登记为下一条 pending |
| `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` | 修改 | 同步人类可读长期路线 |
| `prism/reports/2026-05-22-r1-formal-release-readiness-convergence-assessment.md` | 新建 | 保存本轮 Prism 评审结论 |
| `prism/reports/index.yaml` | 修改 | 把 P4-18 Prism 报告加入正式报告索引 |
| `compass/docs/catalog.json` | 修改 | 刷新 docs 首读索引 |

### 3.2 技术实现要点

本轮没有做任何发布动作，也没有关闭 release blocker。真正落地的是“正式发布前差距地图”：它把“还卡住什么”“哪些必须 Norven 决策”“哪些已经满足”“下一刀先做什么”固定成机器可追踪资产。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮作用 |
|---|---|---|
| 正式发布差距地图 | 一张“离公开发布还差什么”的清单，避免局部任务完成后误以为 RedCap 已经可以发布。 | 本轮主产物 |
| 发布硬阻塞 | 不解决就不能正式公开发布的问题，例如控制面拆分、旧证据边界、许可证和真实发布授权。 | 用来判断还不能发布 |
| 人工保留决策 | Cap 和棱镜不能替 Norven 拍板的事项，例如许可证、registry、是否真正公开发布、是否执行破坏性删除。 | 用来避免越权 |
| P4-19 旧锚点退休预检 | 下一步只检查旧 `prism/reports` 路径未来能不能安全下线；它不是删除动作。 | 下一条任务 |
| 棱镜评审 | 让 Claude Code 与 Kimi 从不同角度检查本轮结论有没有越权、遗漏或误判。 | 本轮独立验收 |
| closeout receipt | 任务完成凭证；只有生成 receipt 后，才能说本轮任务正式完成。 | 最终收口证明 |

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无必须人工审核项 | 本轮只做 release gap map，不触碰人工保留决策；进入真实发布、许可证、registry、Layer A 裁决或 destructive apply 时才需要人工介入 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| PM Gate | `bash compass/tools/redcap-pm-gate-check.sh strict codex .dev-task.md` | 通过 |
| change-intake | `bash compass/tools/redcap-change-intake-check.sh .dev-task.md` | 通过 |
| 意图覆盖 | `bash compass/tools/redcap-intent-coverage-check.sh .dev-task.md` | 通过 |
| Prism availability | `bash prism/tools/prism-availability.sh status --report-rejected --verbose` | 通过；Claude Code + Kimi 可用，Copilot 未调用 |
| runtime package manifest | `bash compass/tools/redcap-runtime-package-manifest.sh --check --npm-pack-dry-run` | 通过 |
| public package surface | `bash compass/tools/redcap-public-package-surface.sh` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无必须人工验证项；本轮没有执行真实发布、删除或产品裁决。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 收口前待最终核对 |
| 棱镜验收 | Claude Code 与 Kimi 已完成，split recommendation 后由 Cap 保守裁决 |
| closeout summary | 收口前待生成 |
| closeout receipt | 收口前待生成 |

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
| 旧 `prism/reports` 锚点退休 | P4-19 只先做 preflight，真实 delete-last 仍需后续独立任务和授权 | P0 |
| internal-control-plane 物理拆分 | 是最大工程 blocker，但 blast radius 大，排在 P4-19 之后 | P0 |
| Prism raw evidence cleanup | 涉及证据保全和人工边界，本轮不执行 | P0 |
| Layer A 产品范围裁决 | 属于 Norven 产品边界，不由 Cap 或棱镜裁决 | P1 |
| 正式公开发布 | 仍需许可证、发布开关、registry、版本和最终 release authorization | P0 |

### 6.2 推荐的下一步行动

1. 完成本轮 closeout runtime，生成 P4-18 receipt。
2. 进入 P4-19：旧 `prism/reports` 锚点 delete-last 预检。
3. P4-19 之后再回到 internal-control-plane physical split copy-first 任务。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| no-promote | release readiness map 不能冒充 release readiness | 本轮经验已写入 report 与 manifest；它是本任务的边界提醒，不提升为全局 lesson |

### 7.2 流程改进建议

正式发布差距地图不能只写“还不能发布”，还必须写清楚“为什么不能”“哪些已经满足”“下一步先做什么”。否则后续任务会在同一批 release blocker 上反复考古，或者把局部 preflight 误读成全局 release-ready 证明。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| no-promote | P4-18 release gap map | 不新增 Evolution candidate；本轮属于 release-readiness 路线治理，不沉淀为公共 skill 或长期知识 | `references/r1-formal-release-readiness-convergence-assessment.json` |

---

## 八、附录

### 附录 A：Commits

```
本报告生成时尚未提交；最终 commit 会在 closeout 后记录。
```

### 附录 B：棱镜调用记录

| Agent | 角色 | 状态 | 结论 |
|------|------|------|------|
| Claude Code | reviewer | responded | pass；推荐 internal-control-plane physical split |
| Kimi | challenger | responded | pass；推荐 old `prism/reports` anchor delete-last preflight |
| Gemini | optional | unavailable | availability cache marked unavailable |
| Copilot | fallback | absent | Claude Code 与 Kimi 可用，按策略未调用 |

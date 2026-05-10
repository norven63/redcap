# 任务完成报告：Root-level 信息架构坏味登记

**报告日期**：2026-05-10
**执行者**：Cap（Codex + Prism advisory: Kimi + Claude Code）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已把“根目录直接父级目录过散、知识/报告/证据/模板语义重叠”登记为新的历史债务 `RASG-017`。
- 关键结论：之前的 RASG-001..016 并不是“假的完成”；它们解决的是索引、生命周期、token 风险、包面安全和具体子域治理。`RASG-017` 是更高一层的产品工程形态债务：RedCap 根目录本身是否足够清爽、集中、语义稳定。

### 0.2 上一步完成的是

- 上一步完成的是：三分 RedCap 前进刻度表已经落地并 closeout；它暴露出当前历史债务账面仍有治理项，也让这次根目录坏味可以被正式纳入“历史债务坏味”桶。

### 0.3 下一步计划做的是

- 下一步计划做的是：后续另开 `RASG-017` 实现任务，先做根目录资产 inventory、目标父级模型、消费者影响矩阵、别名兼容方案和回滚计划；只有这些通过后，才允许讨论真实目录迁移。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：发现账面/物理现实不一致 -> 回顾用户“举一反三”要求 -> 扫描根目录资产分布 -> 棱镜 advisory 评审 -> 登记 RASG-017 -> 后续另开整合实现任务。
- 当前所在位置：坏味已进入需求树；本轮不是物理整理目录。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮不移动、不删除、不发布、不改变包面白名单，只登记历史债务并接入机器检查。

---

## 一、问题源

Norven 指出：虽然 RedCap 已经多次声明信息架构和历史坏味治理完成，但实际根目录下仍能看到多个直接父级目录承载相近语义：`compass/docs`、`compass/knowledge`、`redcap-knowledge`、`shared-knowledge`、`prism/reports`、`prism/runs`、`loom/test-reports`、`references`、`runtime` 等。

这个问题不是“所有文件必须放在一个目录下”。真正的坏味是：RedCap 已经逐步走向 runtime / CLI / 多层系统，但工程根目录还保留了历史生长出来的多父级知识、报告、证据、模板和控制面入口。它们现在有索引和边界，但物理形态还不像一个足够干净的产品化工程。

---

## 二、是否曾经要求“举一反三”

确认有。此前 `2026-05-04-redcap-information-architecture-and-artifact-governance.md` 覆盖的原始对话中，Norven 明确要求不要只解释 report/knowledge 为什么分散，而要从健康完善的工程目录、运行时产物治理、CLI/runtime 发布准备和目录语义规范角度整体审视 RedCap。

本轮复盘结论是：之前确实做过一轮“举一反三”，但验收口径偏窄。它把问题治理成了“有规则、有索引、有生命周期、有发布过滤”，没有进一步追踪“根目录父级模型是否仍然过散”。

---

## 三、落地结果

| 项目 | 结果 |
|---|---|
| 新需求编号 | `RASG-017` |
| 新需求标题 | `Consolidate root-level information architecture before product release` |
| 所属桶 | 历史债务坏味 |
| 优先级 | `P1-before-public-release` |
| 状态 | `planned` |
| 当前完成边界 | 完成登记、评估、任务定义和 checker 接入 |
| 当前未完成边界 | 未做根目录真实迁移、删除、合并、外置或发布 |

---

## 四、工程化需求摘要

`RASG-017` 的后续实现任务至少要交付五件事：

1. 根目录资产 inventory：列出每个直接父级目录的职责和资产类型。
2. 目标父级模型：决定哪些根目录应保留，哪些应合并、移入内部目录、外置，或仅保留兼容 shim。
3. 消费者影响矩阵：找出所有引用这些路径的脚本、检查器、入口文档、host adapter、package manifest、receipt/report anchor。
4. 兼容与回滚方案：在任何路径移动前，设计 alias、import map、symlink 或 resolver，保证考古和收尾证据不断链。
5. 验收链：dry-run、Prism review、package safety、clean workspace E2E、spec-check、diagnose 和 closeout receipt。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| root-level 信息架构 | RedCap 工程根目录下的直接子目录布局 | 人打开仓库第一眼看到的“产品骨架”，例如哪些东西放在根目录，哪些应收进内部目录或外置。 |
| 直接父级目录 | `compass`、`prism`、`redcap-knowledge` 等根目录直属目录 | 不是多层目录本身有问题，而是太多根目录直属目录承担相近职责，会让产品边界不清。 |
| 历史债务坏味 | `references/backlogs/redcap-architecture-smell-governance.json` | 已知影响可维护性、可信度或产品形态，但不一定立刻阻塞当前使用的问题。 |
| RASG-017 | 新增的根目录信息架构债务 | 本轮登记的新历史债务条目，后续要先规划再迁移，不能直接动目录。 |
| inventory | 后续 RASG-017 实现任务的第一步 | 先把每个根目录直属目录是什么、给谁用、能不能移动查清楚。 |
| alias / compatibility shim | 未来迁移时的兼容策略 | 如果路径要变，需要用别名、映射或过渡入口保证旧报告、receipt、脚本不断链。 |

---

## 五、棱镜评审

Kimi advisory review 给出 pass，核心意见如下：

- 这是一个合法的未解决架构坏味，不应被 RASG-001..016 的完成态覆盖。
- 它更适合作为 `historical debt / product-shape / information-architecture`，优先级为 `P1-before-public-release`。
- 它不应被称为 P0 当前 release blocker，因为现有索引、知识网关和 package safety 仍然能工作。
- 它不应直接移动或删除目录；首个任务必须是 inventory、分类、目标模型、别名策略和影响分析。

Claude Code 随后返回有效 JSON 评审，同样给出 pass 且无 blocker；它补充强调：这不是“为了美观清爽而收目录”，而是发布前必须避免把偶然形成的根目录分类冻结为公共产品契约。

本轮可以声明“双路 advisory review 已绑定为 Prism acceptance 证据”。但它们评审通过的是“把坏味登记为历史债务并要求后续 inventory-first”，不是评审通过真实目录迁移。

---

## 六、验证结果

| 验证项 | 结果 |
|---|---|
| 用户原始“举一反三”要求回顾 | 通过 |
| 根目录资产扫描 | 通过 |
| RASG-017 写入需求树 | 通过 |
| checker 识别 RASG-017 | 通过 |
| `require-complete` 对 planned 项阻断 | 通过，`RASG-017: not done` |
| progress meter 展示 open historical debt | 通过 |
| current-status acceptance | 通过 |
| active task-report inbox 生命周期 | 通过，已把 1 份较旧报告移入私有冷归档，活跃报告数回到 12 份政策上限 |
| spec / diagnose | 通过 |
| closeout | 待最终 receipt 收口 |

### 5.4 完成等级（禁止混报）

| 等级 | 本轮结论 |
|---|---|
| 已识别 | 是，根目录父级目录过散被确认为独立坏味。 |
| 已评估 | 是，完成本地扫描与 Kimi、Claude Code 双路 advisory review；两路均无 blocker。 |
| 已登记 | 是，已新增 `RASG-017`，状态为 `planned`。 |
| 已实现 | 是，本轮实现的是“历史债务登记与机器检查接入”；不是根目录物理迁移。 |
| 已自检 | 是，已用架构坏味 checker、progress meter、人类输出质量、Evolution harvest 与 Prism acceptance 做收口自检。 |
| 已独立验收 | 是，Kimi 与 Claude Code 两路 Prism advisory 均为 pass 且无 blocker。 |
| 已实现治理 | 否，本轮没有做根目录物理整合、迁移、删除或外置。 |
| 已正式完成 | 否，本轮完成的是债务 intake；`RASG-017` 本体仍需后续规划/实现/receipt。 |

---

## 七、经验沉淀

### 7.1 新增 Lesson

| 编号 | 标题 | 核心内容 |
|---|---|---|
| L-163 | 信息架构治理不能只看索引是否能用，还要看产品骨架是否可解释 | 索引、字典、生命周期和包面安全能降低 token 与误读风险，但不能自动证明根目录物理形态已经产品化。发布前需要单独审判“人第一眼看到的工程骨架是否清晰”。 |

### 7.2 流程改进建议

后续凡是声明“坏味治理完成”，必须区分三层完成口径：内容级治理、入口/索引级治理、物理产品形态治理。三层任意一层未覆盖，都不能用一个“已完成”概括全部。

### 7.3 Evolution Factory 候选处理

no-promote：本轮已经把问题作为 `RASG-017` 写入架构坏味需求树，并补充为具体历史债务条目；不再新增 Evolution candidate，避免同一问题同时进入两个长期账本。

---

## 八、不能误报

- 不能说根目录已经整理干净。
- 不能说 RASG-001..016 完成态无效。
- 不能把 `RASG-017` 登记完成冒充为物理治理完成。
- 不能启动 npm publish。
- 不能移动、删除、合并、外置任何目录。

---

## 九、后续建议

下一步不应直接“搬目录”，而应启动 `RASG-017` 的规划实现任务。那个任务应该先产出一个可审查的 root-level target model，再决定是否做小批量迁移。

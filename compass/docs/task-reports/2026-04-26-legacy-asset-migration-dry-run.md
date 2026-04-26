# 任务完成报告：历史资产迁移 dry-run

**报告日期**：2026-04-26
**执行者**：Cap（Codex.app 主执行，Codex CLI Prism reviewer；Kimi/Gemini 超时）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P1-2 已完成历史资产迁移 dry-run，不执行真实搬迁或删除。
- 详情：新增 `references/legacy-asset-migration-dry-run.json`，把 task reports、docs catalog、runtime working dirs、research、specs、traces、docs archive、knowledge、prism/runs 分成可审计集合。新增 checker 并接入 spec-check、diagnose、acceptance，能拒绝危险迁移计划。

### 0.2 上一步完成的是

- 上一步完成的是：P1-1 执行层物理拆分 dry-run，明确 root 入口、hooks、`compass/tools`、`prism/tools` 和历史资产的迁移边界。
- 详情：P1-2 接在 P1-1 之后，专门处理 docs、reports、knowledge 和 runtime evidence 的考古/追踪层迁移问题。

### 0.3 下一步计划做的是

- 下一步计划做的是：P1-3 shared-knowledge 远端绑定；若要真实移动历史资产，需要另开 file-level apply 任务并先通过 broken-link / receipt-anchor 检查。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P0-1 Prism cache → P0-2 R0-R22 registry → P1-1 执行层拆分 dry-run → P1-2 历史资产迁移 dry-run → P1-3 shared-knowledge 远端绑定 → P2 runtime/CLI/package。
- 当前所在位置：P1-2 已完成实现与独立审查，等待 closeout runtime 写入正式 receipt。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 继续

### 1.2 触发背景

用户反复指出 RedCap 的 docs/report/考古材料有淤积风险，但又不能因为“瘦身”损坏历史追踪、任务报告、receipt 和知识沉淀能力。P1-2 的目标不是马上搬文件，而是先把每类历史资产的处置策略、风险、断链检查和回滚计划写成机器可读清单。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 解决 docs / reports / historical assets 长期淤积，但不牺牲考古、追踪和 closeout 证据能力。 |
| 已覆盖 | 已生成 dry-run manifest、checker、spec/diagnose/acceptance 接线、父任务账本更新、文件字典更新、执行保障登记、lesson 和 Prism review。 |
| 未覆盖/延期 | 本轮不执行真实 move/delete，不重写历史报告链接，不搬迁 shared-knowledge 远端仓库。 |
| 用户可见边界 | P1-2 完成只说明历史资产迁移计划可审计，不说明历史资产已经物理迁出。 |
| 后续路径 | file-level apply 任务必须先生成精确文件清单，再跑 catalog、broken-link、receipt-anchor 和 rollback 检查。 |

---

## 二、方案讨论

### 2.1 问题分析

历史资产不是一种东西。task reports 是 closeout 证据，specs 是 active authority，research 是低频人类阅读材料，knowledge 是运行时指南，prism/runs 是 ignored runtime evidence。它们应该进入不同生命周期，而不是被一个“大清理”动作统一移动。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 直接移动 docs | 把历史报告和研究材料搬到新目录 | 目录立刻变瘦 | 极易破坏 receipt、catalog 和历史链接 |
| Q1 | collection-level dry-run | 先按集合分类，写动作、风险、断链计划和回滚 | 安全、可审计、能作为 apply 输入 | 不产生物理迁移结果 |
| Q1 | 只依赖现有 legacy policy | 不新增迁移 manifest，只保留生命周期原则 | 成本低 | 缺少数量、目标、断链计划和 apply 边界 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | collection-level dry-run | 它能把历史资产治理从“泛泛而谈”变成可检查的迁移计划，同时不破坏当前考古链路。 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `references/legacy-asset-migration-dry-run.json` | 新建 | 历史资产迁移 dry-run manifest，登记集合、计数、风险、动作、断链计划和回滚计划。 |
| `compass/tools/redcap-legacy-asset-migration-check.py` | 新建 | 校验 manifest 的计数、动作、风险、apply 状态、catalog/link/rollback 计划和 Prism retention summary。 |
| `compass/tools/redcap-legacy-asset-migration-check.sh` | 新建 | checker shell 入口。 |
| `compass/tools/redcap-spec-check.sh` | 修改 | 接入 legacy asset migration checker。 |
| `compass/tools/redcap-diagnose.sh` | 修改 | 诊断总入口新增 legacy asset migration checker。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增 `legacy-asset-migration-check` acceptance 和危险 fixture。 |
| `references/file-lookup-dictionary.md` | 修改 | 新增 manifest 和 checker 的人类可读定位。 |
| `references/file-lookup-dictionary-policy.json` | 修改 | 新增 manifest 和 checker 的机器 coverage。 |
| `references/execution-guarantees.json` | 修改 | 新增 `legacy-asset-migration-dry-run` 保障项。 |
| `references/redcap-parent-task-ledger.md` | 修改 | 标记 P1-2 dry-run 完成，保留真实 apply 边界。 |
| `compass/knowledge/lessons.md` | 修改 | 新增 L-128，沉淀历史资产迁移经验。 |
| `compass/docs/catalog.json` | 修改 | 生成新报告索引。 |

### 3.2 技术实现要点

manifest 记录了 9 类集合：task reports 36 个、docs catalog 1 个、runtime working dirs 47 个、research 3 个、specs 13 个、traces 1 个、docs archive 2 个、knowledge 19 个、prism/runs 25 个运行目录。每类都必须有 `catalog_update_plan`、`link_check_plan` 和 `rollback_plan`，避免“清理目录”时损坏考古链路。

checker 会重新数文件和行数，并用 `prism-runs-lifecycle.sh summary` 校验 `prism/runs` 的运行目录数量与 purgeable acceptance residue。它不允许 `apply_allowed=true`，也不允许缺少断链计划或回滚计划的迁移建议进入 spec-check，并强制 retain/archive/move/prune/ignore 五类动作都出现。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| collection-level dry-run | `references/legacy-asset-migration-dry-run.json` | 先按目录/资产类型分类，不直接列每个文件；用于判断哪些集合能动、哪些必须保留。 |
| file-level apply | 后续真实迁移任务 | 真正搬文件前必须生成的精确文件清单；本轮没有执行。 |
| link_check_plan | manifest 每个集合的字段 | 搬迁前要检查哪些链接、引用或锚点，防止考古断链。 |
| receipt-anchor | closeout runtime / task reports | 完成凭证与报告之间的引用关系；迁移 task reports 时必须保护。 |
| ignore-runtime | `prism/runs` | 运行证据目录不进入 docs catalog，也不默认 bulk-read；只按 retention 策略处理。 |

### 3.3 关联变更

父任务账本同步把 P1-2 标为 dry-run completed，并明确真实 apply 仍是后续任务。文件字典和执行保障同步新增条目，防止新 manifest/checker 变成孤儿机制。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 是否接受 P1-2 只做 dry-run | 真实搬迁会改变历史资产路径，必须另开 apply 并跑 broken-link/receipt-anchor 验证。 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 语法检查 | `python3 -m py_compile compass/tools/redcap-legacy-asset-migration-check.py` | 通过 |
| targeted checker | `bash compass/tools/redcap-legacy-asset-migration-check.sh` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh legacy-asset-migration-check` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | resource-limited-pass |
| 文件字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| 总回归 | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| 诊断总入口 | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无必须人工验证项；真实历史资产搬迁尚未开始。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 预计 closeout 前清零 |
| 棱镜验收 | `20260426-legacy-asset-migration-dry-run-review` resource-limited-pass |
| closeout summary | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/summaries/redcap-legacy-asset-migration-dry-run-ac79c271ae1a36761494a0a41e95fec171830be2db979a6b491733ab4938781f.md` |
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-legacy-asset-migration-dry-run-ac79c271ae1a36761494a0a41e95fec171830be2db979a6b491733ab4938781f.json` |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，resource-limited Prism 通过 |
| 已正式完成 | 是；提交后由 closeout runtime 生成上方 receipt |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 历史资产真实搬迁 | 需要 file-level manifest、broken-link 检查、receipt-anchor 检查和 rollback 命令。 | P1 |
| shared-knowledge 远端绑定 | 需要用户提供远端仓库与权限。 | P1 |
| 正式 runtime / CLI / package 发布 | 依赖执行层与历史资产边界稳定。 | P2 |

### 6.2 触发的新问题

Kimi 首次审查在任务报告创建前发现 `execution-guarantees` 会因 report path 不存在而 fail，这是正确 fail-closed 行为。本轮补报告后再收口，未绕过 gate。

### 6.3 推荐的下一步行动

1. P1-3：绑定 shared-knowledge 远端仓库。
2. 历史资产真实 apply：在后续任务中从本 manifest 生成 file-level manifest。
3. P2-1：设计正式 runtime / CLI / package 发布形态。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-128 | 历史资产迁移要先按集合分类，再生成文件级 apply 清单 | 不同历史资产有不同权威性和风险，必须先分类、校验计数和断链计划。 |

### 7.2 流程改进建议

目录治理任务应默认分成 collection-level dry-run 和 file-level apply 两阶段；前者建立治理边界，后者才允许真实移动或删除。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 本轮 review 和回归 | no-promote；已沉淀为 L-128，不新增 Evolution candidate | `compass/knowledge/lessons.md` |

---

## 八、附录

### 附录 A：Commits

```
本报告随 P1-2 实现提交一起进入 git；closeout receipt 将记录最终 HEAD。
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| single-reviewer / resource-limited | 历史资产分类是否完整、是否过度乐观、checker 是否挡住危险计划 | Kimi/Gemini 超时；Codex CLI reviewer 先抓到 docs catalog 与 prune 分类 blocker，修复后复验 pass | `prism/runs/20260426-legacy-asset-migration-dry-run-review/collect/reviewer/parsed.json` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- dry-run manifest：`references/legacy-asset-migration-dry-run.json`
- 父任务账本：`references/redcap-parent-task-ledger.md`
- 文件字典：`references/file-lookup-dictionary.md`

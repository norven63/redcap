# 任务完成报告：RASG-022 私有冷归档根目录迁移

**报告日期**：2026-05-15
**执行者**：Cap（Codex App + Prism Kimi resource-limited 评审）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RASG-022 的第一批高风险根目录迁移已落地，`redcap-knowledge/` 已从工程根目录迁入 `private-archive/redcap-knowledge/`。
- 详情：这一步解决的是“私有历史知识资产直接暴露在 RedCap 工程根目录”的结构坏味。迁移后，旧路径仍可通过别名解析找回，新路径被包发布安全规则排除，历史报告不需要被批量改写。它让后续 npm/CLI 发布准备少一个明显的私有资产暴露点。

### 0.2 上一步完成的是

- 上一步完成的是：shared-knowledge 模板根目录迁移已经收口，剩余高风险根目录曾被显式延期；本轮是在该延期清单中先执行 private archive 这一刀。

### 0.3 下一步计划做的是

- 下一步计划做的是：生成 closeout receipt；之后剩余高风险根目录仍按后续 tranche 处理，不能在本轮冒充全部完成。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：发现根目录坏味 -> 先迁移低耦合私有归档 -> 保留旧锚点与安全排除 -> 再处理控制面、Prism、Layer A 与 workspace-local 边界。
- 当前所在位置：RASG-022 / private archive tranche 已实现，并已通过 targeted checks、Prism resource-limited 验收、全量 acceptance 与 closeout runtime。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要
- 说明：本轮不涉及新的产品取舍或外部账号动作；Cap 与 Prism 可继续完成验收、receipt 和提交。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 我要求你们现在就开始执行

### 1.2 触发背景

RASG-022 已经把 shared-knowledge 迁移完成，但 `redcap-knowledge/` 仍作为高风险根目录留在工程根下。它存放的是私有冷归档、历史报告和研究材料；从 CLI/发布视角看，这类资产不应该直接与执行层入口并列。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 启动 RASG-022 剩余高风险根目录物理迁移，不再只停留在延期说明。 |
| 已覆盖 | 第一批 private archive tranche 已覆盖：`redcap-knowledge/` 迁移、别名解析、冷归档清单、包安全排除、信息架构检查与回归用例。 |
| 未覆盖/延期 | `compass/references` 控制面拆分、`prism` 工具/证据拆分、`loom` Layer A 边界、workspace-local 发布排除证明仍是后续 tranche。 |
| 用户可见边界 | 本轮不是“所有根目录治理完成”；只能声明 private archive 第一批迁移完成。 |
| 后续路径 | 后续按风险顺序进入 Prism evidence split 或 internal control-plane contract split。 |

---

## 二、方案讨论

### 2.1 问题分析

根目录坏味不能通过简单删除解决，因为 `redcap-knowledge/` 里有历史报告、receipt 线索和考古价值。真正要解决的是“私有资产不应占据执行层根目录，同时不能破坏旧路径考古”的双重约束。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 保持不动 | 继续把 `redcap-knowledge/` 留在根目录 | 风险最低，改动少 | 继续污染 CLI/发布结构，坏味不消失 |
| Q1 | 建 symlink | 根目录保留软链，真实内容迁走 | 旧路径看似兼容 | 容易制造双入口和包发布误判 |
| Q1 | 物理迁移并用 alias 兼容 | 移到 `private-archive/redcap-knowledge/`，旧路径只作为解析别名 | 根目录更干净，考古能力保留，发布排除更明确 | 需要同步多处策略与验收 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 物理迁移并用 alias 兼容 | 这是唯一同时满足“根目录减污”和“历史考古不断链”的方案；Prism 也认为它比先动 `compass/references` 或 `prism` 更安全。 | CAP_DECIDE + Prism review |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `private-archive/redcap-knowledge/**` | 移动 | 承接原 `redcap-knowledge/**` 私有冷归档内容。 |
| `.npmignore` | 修改 | 排除 `private-archive/`，避免未来包发布携带私有冷归档。 |
| `compass/tools/redcap-legacy-asset-alias-resolver.py` | 修改 | 让旧 `redcap-knowledge/**` 锚点解析到新 canonical 路径。 |
| `compass/tools/redcap-cold-archive-inventory.py` | 修改 | 冷归档清单改以 `private-archive/redcap-knowledge/` 为真实根。 |
| `references/root-information-architecture-consolidation-plan.json` | 修改 | 记录 private archive tranche 的迁移结果和剩余延期范围。 |
| `references/root-ia-remaining-root-groups-deferral.json` | 修改 | 从延期组中移除 private archive，并保留其他组延期。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 更新迁移、别名、状态面和 stop-review 验收夹具。 |
| `references/root-ia-private-archive-tranche-manifest.json` | 修改 | 记录 86 个实际迁移文件，包括从活跃报告入口归档的 `2026-05-04` 报告。 |
| `prism/runs/20260515-rasg022-private-archive-physical-migration/**` | 新增 | 保存本轮 resource-limited Prism 验收证据、Kimi verdict、不可用模型族证据和 acceptance binding。 |

### 3.2 技术实现要点

本轮没有把历史报告全文批量改写。原因是历史报告本身也是证据，粗暴替换路径会破坏过去 receipt 与哈希线索；更安全的做法是让活跃入口、索引和 alias resolver 指向新路径。

包发布安全同时覆盖新旧两个口径：新路径 `private-archive/redcap-knowledge/**` 是真实私有归档根，旧路径 `redcap-knowledge/**` 是兼容别名，二者都不能进入 public package。这样未来发布检测不会因为旧锚点或新目录遗漏而漏放私有内容。

验收中发现的几处失败已同步修正：任务卡 `scope_status` 必须使用机器认可枚举；session-resume acceptance 需要清理上一用例残留 runtime；stop-review 负面用例的模拟 reviewer 超时不能过短；当前状态面验收必须跟随 RASG-022，而不是继续锚定已关闭的 GD-008。

后续复核又补了两处关键一致性问题：manifest 原先只统计原 `redcap-knowledge/` 的 85 个文件，漏掉一份从 `compass/docs/task-reports` 归档到 private archive 的旧报告；alias resolver 原先只覆盖 54 条旧锚点，未覆盖新增的 32 条私有冷归档旧路径。现在 manifest 已同步为 86 条，旧 `redcap-knowledge/**` 与被归档的旧 `compass/docs/task-reports/2026-05-04...` 锚点都可解析到新路径。

全量 acceptance 还反向抓出两个测试夹具落后于真实门禁的问题：`redcap-prism-degradation-check.sh` 与 `redcap-progress-meter-check.sh` 没有被 spec-check fixture 同步带入，导致正例临时仓库被误判为缺门禁。现在这两个夹具缺口已补入回归体系，避免后续新增门禁时测试自身再次落后。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| private archive | `private-archive/redcap-knowledge/` | 私有冷归档区，保存不该暴露在工程根目录或发布包里的历史知识资产。 |
| alias resolver | `compass/tools/redcap-legacy-asset-alias-resolver.py` | 旧路径导航器：有人或脚本查旧路径时，它告诉对方现在应该去哪个新路径。 |
| tranche | RASG-022 分批迁移策略 | 一次只迁一组高风险根目录，降低大规模目录手术的并发风险。 |
| closeout receipt | `references/receipts/**` | RedCap 正式完工凭证；没有 receipt 不能宣称 completed。 |

### 3.3 关联变更

- 冷归档清单已重新生成，迁移后的私有归档数量与哈希由 `references/redcap-knowledge-cold-archive-inventory.json` 记录。
- 文件查阅字典、包安全策略、知识网关、信息架构策略均已改为理解新 canonical 路径。
- 旧 active task report 数量超上限时，已将最旧的活跃报告移入 private archive，并同步相关索引。

---

## 四、人工审核要点

### 4.1 棱镜评审

| Agent | 结论 | 关键条件 |
|---|---|---|
| Kimi | pass-with-concerns | 认可迁移技术方向，但指出 Prism registry 缺失、manifest 漏记文件、closeout 未闭环；前两项已修复，closeout 在本节继续收口。 |
| Claude Code | unavailable | 600 秒完整评审和 60 秒短重试均超时，未产出可用 verdict。 |
| Gemini | unavailable | 返回交互式浏览器登录提示，未产出可用 verdict。 |
| Codex CLI | fallback-timeout | 兜底评审过程中发现 alias 覆盖缺口；修复后复评超时，未产出最终 JSON verdict。 |

### 4.2 人工介入状态

| 项 | 结论 |
|---|---|
| 是否需要 Norven 立即决策 | 不需要 |
| 原因 | 本轮不涉及发布、凭据、不可逆删除或产品取舍；剩余动作是机器收口与 receipt 生成。 |
| 人工审核建议 | 只需关注本报告是否清楚说明“完成的是 private archive 第一批，不是全部 RASG-022 高风险根目录”。 |

---

## 五、验证结果

### 5.1 已执行检查

| 检查 | 结果 |
|---|---|
| `bash compass/tools/redcap-spec-check.sh "$PWD"` | pass |
| `bash compass/tools/redcap-multi-session-acceptance.sh all` | pass |
| `bash compass/tools/redcap-multi-session-acceptance.sh legacy-asset-alias-resolver` | pass |
| `bash compass/tools/redcap-multi-session-acceptance.sh package-publish-safety-check` | pass |
| `bash compass/tools/redcap-multi-session-acceptance.sh clean-workspace-e2e-check` | pass |
| `bash compass/tools/redcap-multi-session-acceptance.sh prism-acceptance-binding-required` | pass |
| `bash compass/tools/redcap-information-architecture-check.sh` | pass |
| `bash compass/tools/redcap-public-package-surface.sh` | pass |
| `bash compass/tools/redcap-package-publish-safety-check.sh` | pass |
| `bash compass/tools/redcap-public-distillation-preflight.sh` | pass |
| `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | resource-limited-pass |

### 5.2 全量回归状态

全量 `redcap-multi-session-acceptance.sh all` 已通过。回归过程中暴露的 spec-check fixture 同步缺口已修复，并已通过 targeted rerun 与最终全量回归验证。

### 5.3 closeout runtime / receipt

| 项 | 结果 |
|---|---|
| closeout receipt | 已生成 |
| receipt path | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/rasg-022-private-archive-physical-migration-tranche-b62ccb04b1151602b0455578ebcdadf192807912469a5b7e2ee3fbb3e5f0fb25.json` |
| summary path | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/summaries/rasg-022-private-archive-physical-migration-tranche-b62ccb04b1151602b0455578ebcdadf192807912469a5b7e2ee3fbb3e5f0fb25.md` |
| 说明 | closeout runtime 已生成 receipt；若后续报告或证明文件再次提交，需重新运行 closeout runtime 刷新 current_head。 |

### 5.4 完成等级（禁止混报）

| 项 | 结论 |
|---|---|
| 已实现 | 是，private archive 第一批迁移与配套策略已实现。 |
| 已自检 | 是，相关单项检查和 spec-check 已通过。 |
| 已独立验收 | 是，Kimi 给出 pass-with-concerns 且无 blocker；其他模型族不可用/超时，按 resource-limited Prism 证据收口。 |
| 已正式完成 | 是，closeout receipt 已生成；禁止扩大为 RASG-022 全部高风险根目录完成。 |

---

## 六、遗留问题与下一步

| 项 | 状态 | 处理方式 |
|---|---|---|
| 剩余高风险根目录 | 未在本轮执行 | 后续按 tranche 继续处理 `compass/references`、`prism`、`loom` 与 workspace-local 边界。 |
| 正式 npm/CLI 发布 | 未进入 | 本轮只减少私有资产暴露风险，不启动发布。 |
| Prism provider 稳定性 | resource-limited | 本轮已记录 Claude/Gemini/Codex 不可用证据；不因此阻塞 private archive tranche。 |

---

## 七、经验沉淀

| 经验 | 问题源 | 解决方案 | 最后效果 |
|---|---|---|---|
| 高风险根目录迁移必须分 tranche | 根目录资产耦合不同，整体搬迁容易破坏运行时与考古链 | 先迁低耦合私有冷归档，并保留旧路径 alias | 降低发布面污染，同时不切断历史锚点 |
| 历史报告不能靠批量改写制造干净 | 历史报告本身是证据，批量替换会破坏过去语境 | 活跃入口切 canonical，旧报告由 alias resolver 兼容 | 考古能力保留，当前入口变清晰 |
| 全量回归也要审计自身残留 | acceptance 曾留下 `acceptance-prism-*` 临时 run | 为 Prism 并发用例增加显式清理，并复跑生命周期门禁 | 全量回归不再污染真实 `prism/runs` |

---

## 八、附录

### 8.1 关键证据文件

| 证据 | 路径 |
|---|---|
| 迁移 manifest | `references/root-ia-private-archive-tranche-manifest.json` |
| Prism 报告 | `prism/reports/2026-05-15-rasg-022-private-archive-physical-migration.md` |
| Prism run | `prism/runs/20260515-rasg022-private-archive-physical-migration/` |
| 当前任务卡 | `.dev-task.md` |

### 8.2 禁止扩大声明

- 不得声明 RASG-022 全部高风险根目录已经完成。
- 不得声明正式 npm/CLI 发布准备已经完成。
- 不得声明 private archive 可以进入 public arsenal；它仍是私有冷归档。

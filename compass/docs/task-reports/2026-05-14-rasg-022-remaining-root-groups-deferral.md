# 任务完成报告：RASG-022 剩余高风险根目录显式延期收口

**报告日期**：2026-05-14
**执行者**：Cap（Codex 主执行，Claude Code / Kimi Prism 验收）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RASG-022 已从“只完成一个迁移切片、其余靠口头说明”升级为“一个低风险迁移已完成，其余高风险根目录都有显式延期收据、机器检查和棱镜验收”。
- 详情：上一刀已经把 `shared-knowledge` 模板源移到 `templates/shared-knowledge`。这次解决的是剩余高风险根目录容易再次被遗忘的问题：`compass`、`references`、`prism`、`redcap-knowledge`、`loom` 和本地状态文件暂不搬迁，但每一类都写清了为什么不搬、未来什么时候必须重审、将来真的要搬时必须具备哪些安全门。这样 RASG-022 可以诚实收口，同时不会把“延期”冒充成“全部搬完”。

### 0.2 上一步完成的是

- 上一步完成的是：RASG-022 的第一批低风险物理迁移已经完成，模板源从根目录散点迁入 `templates/shared-knowledge`，并通过包候选面、兼容策略、棱镜复核和 closeout receipt。

### 0.3 下一步计划做的是

- 下一步计划做的是：回到发布前主线，继续检查是否还有非发布类产品化治理项；若没有阻塞项，再进入正式 release readiness / npm 发布准备。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：历史债务与坏味治理 → 当前主推进任务集 → 正式发布准备 → 长期演进专项。
- 当前所在位置：历史债务与坏味治理中的 RASG-022 收口切片；本轮处理的是 remaining-root-groups deferral，不是正式发布。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要
- 说明：本轮没有触及发布、许可证、凭据、大规模删除、公开远端写入或不可逆历史改写。后续是否继续物理迁移高风险根目录，可以等真正进入对应发布准备或目录重排任务时再由任务流评估。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “好的，你们继续按照自己评估的优先级来稳步推进吧”

### 1.2 触发背景

上一轮 RASG-022 只完成了最小风险的 `shared-knowledge` 模板迁移，并明确留下“剩余高风险根目录继续切片评估或显式延期判断”。如果这一步不补，状态面会重新出现旧病：人类看到一个迁移成功报告，Agent 可能误以为整个根目录治理都完成了。

本轮选择显式延期，而不是继续移动高风险根目录。原因很简单：这些根目录承载控制面、证据链、私有归档、Layer A 兼容和宿主入口，任何一刀都可能破坏历史锚点或发布边界。正确做法是先把“暂不搬”变成可检查的工程事实。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-apply-with-explicit-deferral |
| 原始意图 | 继续推进 RASG-022，防止 shared-knowledge 切片完成后任务再次漂移。 |
| 已覆盖 | 建立 remaining-root deferral receipt、机器检查、backlog 状态收口和验收入口。 |
| 未覆盖/延期 | 不移动 `compass`、`references`、`prism`、`redcap-knowledge`、`loom` 等高风险根目录；不进入正式 npm 发布。 |
| 用户可见边界 | 可以说 RASG-022 当前阶段已收口；不能说所有根目录都已物理合并。 |
| 后续路径 | 发布准备或未来目录重排任务触发时，按延期收据里的 gate 重新评估。 |

---

## 二、方案讨论

### 2.1 问题分析

RASG-022 的目标不是为了“把目录搬得更漂亮”而搬目录，而是让 RedCap 的执行层、证据链、知识库、模板和发布面边界更清楚。shared-knowledge 是低风险样本，已经适合搬；但剩余根目录里有大量运行时、历史锚点、检查器和私有资产，直接搬迁可能制造比坏味更严重的兼容事故。

所以本轮的工程重点是把“延期”设计成一个受控状态：延期项必须有当前根、未来形态、延期原因、风险等级、重审触发、未来验收门槛和禁止冒充完成的 claim boundary。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 继续物理迁移高风险根 | 继续移动 `compass`、`references`、`prism` 等根目录 | 结构变化更明显 | 破坏面太大，容易伤到 closeout、Prism、历史锚点和包发布面 |
| Q1 | 只在报告里说明延期 | 报告写“剩余部分以后做” | 成本低 | 仍然依赖人类记忆，无法被机器检查 |
| Q1 | 显式延期收据 + 检查器 | 不移动高风险根，但登记延期边界并接入检查链 | 能安全收口，也能防止冒充完成 | 需要增加一个治理收据和检查器 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 显式延期收据 + 检查器 | 它能同时满足安全性和可追踪性：不冒险移动高风险根，也不让延期变成口头债务。 | CAP_DECIDE，Claude Code / Kimi Prism 验收无 blocker |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 当前任务从 shared-knowledge 迁移切片重锚到 remaining-root-groups deferral 收口切片。 |
| `references/root-ia-remaining-root-groups-deferral.json` | 新建 | 记录剩余高风险根目录的延期边界、重审触发和未来移动硬门。 |
| `compass/tools/redcap-root-ia-deferral-check.py` / `.sh` | 新建 | 校验 RASG-022 不能在缺少延期收据时关闭，也不能把延期说成全量迁移完成。 |
| `references/backlogs/redcap-architecture-smell-governance.json` | 修改 | 将 RASG-022 更新为当前阶段 done，并登记 shared tranche 与 explicit deferral。 |
| `references/root-information-architecture-consolidation-plan.json` | 修改 | 为 RASG-017 目标模型补充 RASG-022 当前收口状态。 |
| `references/root-ia-shared-knowledge-tranche-manifest.json` | 修改 | 将上一刀状态更新为 completed-closeout-receipted。 |
| `compass/tools/redcap-diagnose.sh` | 修改 | 让诊断链执行 root IA deferral 检查。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 增加 root-ia-deferral acceptance 正负例。 |
| `references/execution-guarantees.json` | 修改 | 登记“剩余根目录延期收据”是受保障规则，不是口头约定。 |
| `references/file-lookup-dictionary.md` | 修改 | 增加新收据和检查器的查阅入口。 |
| `references/runtime-package-readiness-policy.json` | 修改 | 将新检查器标为维护期检查，不直接扩张公开运行包候选面。 |
| `references/pre-release-product-architecture-review.json` | 修改 | 同步包候选数量，避免发布前产品架构审计使用旧计数。 |
| `references/reference-asset-lifecycle.json` | 修改 | 刷新新增报告、Prism 报告和迁移报告后的引用资产生命周期索引。 |
| `references/redcap-knowledge-cold-archive-inventory.json` | 修改 | 刷新 cold archive 清单，确保历史报告迁移后索引仍可审计。 |
| `redcap-knowledge/task-reports/2026-05-09-feishu-human-readable-node-report.md` | 移动 | 将过期 active report 迁入私有归档，保持 active task-reports 不继续膨胀。 |
| `prism/runs/20260514-rasg022-remaining-root-groups-deferral/**` | 新建 | 保存 Claude Code / Kimi 的原始输出、结构化结论和 acceptance binding。 |
| `prism/reports/2026-05-14-rasg-022-remaining-root-groups-deferral.md` | 新建 | 归档本轮棱镜验收结论。 |
| `prism/reports/index.yaml` | 修改 | 将本轮 formal Prism 报告纳入轻量索引。 |

### 3.2 技术实现要点

这次的核心设计是“延期也要有收据”。收据把剩余根目录分成三类：已经完成迁移的模板源、应该继续留在根目录的入口/契约文件、暂不迁移但必须未来重审的高风险根。这样 current-status、diagnose 和后续任务都能知道 RASG-022 为什么能当前收口，又为什么不能宣称所有根都搬完。

新的检查器做三件事。第一，确认 shared-knowledge 的迁移已经有报告和棱镜证据；第二，确认每个高风险根目录都有延期理由、未来触发条件和安全门；第三，确认 backlog 中 RASG-022 的状态、证据和延期收据一致。任何一个缺口都会失败。acceptance 还补了负例，防止把“延期”冒充成“全量搬迁完成”或“已经发布就绪”。

本轮没有继续搬目录，是有意克制。RedCap 当前更需要“可信状态面”而不是“看起来更整齐的目录树”。高风险根目录的物理迁移会留到 release readiness 或专门目录重排任务中，用单独 tranche 处理。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| RASG-022 | `references/backlogs/redcap-architecture-smell-governance.json` | “根目录信息架构真实物理合并”这条历史债务。 |
| deferral receipt | `references/root-ia-remaining-root-groups-deferral.json` | 不是简单说“以后再做”，而是把为何延期、何时重审、未来怎么做写成机器可检查的收据。 |
| claim boundary | deferral receipt 中的 `claim_boundary` | 防止汇报时把“当前阶段可收口”说成“所有根目录都搬完”。 |
| keep-at-root boundary | deferral receipt 中的 `keep_at_root_boundaries` | 说明有些根目录内容本来就应该留在根，例如 README、host entry、package 控制文件。 |
| explicit deferral | backlog 中的 `explicit_deferrals` | 让 RASG-022 的未搬迁部分有正式登记，不再靠人类记忆。 |

### 3.3 关联变更

本轮触发了诊断链、验收链、执行保障登记和文件查阅字典的同步更新。这样新增能力不会只停留在 report 里，而是能被后续 revive、diagnose、acceptance 和 closeout 链路发现。

棱镜复核提出的非 blocker 也已处理：包候选计数已同步，引用资产生命周期和 cold archive 清单已刷新，Prism 报告和 binding 已落盘，任务报告已从占位状态更新为真实验证结果。

最终回归又抓到并修复了四类二阶漂移。第一，部分 acceptance 仍锚定已经迁入私有归档的旧 active report，现在已改为当前 active report。第二，progress-meter 过去写死 `/tmp/redcap/project`，在 acceptance 隔离项目里会误判 receipt，现在改为尊重 `REDCAP_RUNTIME_PROJECT_BASE_DIR`。第三，root IA 检查过去会把 `.acceptance-*` 和 `.tmp-*` 这类临时夹具当成真实根目录污染，现在已加入忽略规则并补了验收样例。第四，CLI 产品面验收仍在检查旧英文输出，现在已同步到当前中文、人类可读输出。

---

## 四、人工审核要点

> 以下是 Norven 需要重点确认的内容，其他部分 Cap 已自行验证。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无必须人工介入项 | 本轮没有触及用户保留决策；后续是否继续搬高风险根目录，会在对应任务中重新评估。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| deferral checker | `bash compass/tools/redcap-root-ia-deferral-check.sh` | 通过，applied=1 / kept=4 / deferred=5 |
| acceptance 正负例 | `bash compass/tools/redcap-multi-session-acceptance.sh root-ia-deferral-check` | 通过 |
| 架构坏味账本 | `bash compass/tools/redcap-architecture-smell-governance-check.sh` | 通过，done=23 |
| root IA 目标模型 | `bash compass/tools/redcap-root-information-architecture-check.sh` | 通过，inventory=30 |
| 文件查阅字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过，required_paths=263 |
| 执行保障 | `bash compass/tools/redcap-execution-guarantee-check.sh` | 通过 |
| runtime package manifest | `bash compass/tools/redcap-runtime-package-manifest.sh --check --json` | 通过，candidate_count=189，publish_allowed=false |
| package publish safety | `bash compass/tools/redcap-package-publish-safety-check.sh` | 通过，files_scanned=189 |
| public package surface | `bash compass/tools/redcap-public-package-surface.sh` | 通过，private=true，publish_allowed=false |
| pre-release product architecture | `bash compass/tools/redcap-pre-release-product-architecture-check.sh` | 通过，recommendation=not-ready-before-human-release-decisions |
| reference asset lifecycle | `bash compass/tools/redcap-reference-asset-lifecycle.sh check` | 通过，entries=14 |
| cold archive inventory | `bash compass/tools/redcap-cold-archive-inventory.sh check` | 通过，files=84 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过，2 agents / 2 families / 0 blockers |
| docs catalog | `bash compass/tools/redcap-docs-catalog.sh generate && bash compass/tools/redcap-docs-catalog.sh check` | 通过 |
| task report template | `bash compass/tools/redcap-task-report-check.sh "$PWD" fd22df395d874875f1266898df051ad7d1ab45f2` | 通过 |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| 全局诊断关键链 | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过，DIAGNOSE_OK |
| diagnose-overview acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh diagnose-overview` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 无必须人工验证项。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已在 `.dev-task.md` 勾选，待 closeout runtime 生成正式 receipt |
| 棱镜验收 | 已归档并通过 acceptance binding |
| closeout summary | 无 |
| closeout receipt | 无 |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是，延期收据、检查器、状态面、验收入口均已落地 |
| 已自检 | 是，核心检查链、docs catalog、task report、spec-check、diagnose 和 diagnose-overview acceptance 均已通过 |
| 已独立验收 | 是，Claude Code / Kimi Prism 验收无 blocker，acceptance binding 已通过 |
| 已正式完成 | 否，receipt 是唯一正式完工凭证，将由 closeout runtime 生成 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 高风险根目录实际物理迁移 | 风险较高，必须等 release readiness 或专门 tranche 再做。 | P1 |
| 正式 npm 发布 | 本轮只关闭 RASG-022 当前阶段，不进入发布。 | P1 |

### 6.2 触发的新问题

无新增长期问题；本轮是对上一刀遗留边界的收口。

### 6.3 推荐的下一步行动

1. 提交后运行 closeout runtime 生成 receipt。
2. 若 receipt 通过，回到发布前主线，判断是否进入 release readiness。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| 无 | 无新增 lesson | 本轮是既有 RASG-022 收口，不新增通用经验。 |

### 7.2 流程改进建议

显式延期要被视为一种正式工程状态，而不是报告里的备注。未来凡是“计划完成但物理执行延期”的任务，都应该有机器可读延期收据或 durable backlog item。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 本轮没有新的用户偏好、技能候选或反复失败模式 | 无新增候选 | `.dev-task.md` |

---

## 八、附录

### 附录 A：Commits

```
待提交
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| acceptance-review | RASG-022 remaining-root deferral 是否足以当前阶段收口 | pass-after-fixes，无 blocker | `prism/reports/2026-05-14-rasg-022-remaining-root-groups-deferral.md` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- deferral receipt：`references/root-ia-remaining-root-groups-deferral.json`
- root IA 目标模型：`references/root-information-architecture-consolidation-plan.json`
- shared tranche manifest：`references/root-ia-shared-knowledge-tranche-manifest.json`

# 任务完成报告：Historical asset migration apply preflight

**报告日期**：2026-04-29  
**执行者**：Cap（Codex.app + Prism: Kimi CLI / Claude Code）  
**报告版本**：v1.1

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-1 已从“只有 collection-level dry-run”推进到“文件级 apply preflight 已具备”，但真实历史资产仍未移动、未删除、未写入公共库。
- 详情：本轮解决的是历史资产迁移前缺少精确施工清单的问题。现在每个候选文件都有来源、目标、动作、风险和守卫条件；校验器会拒绝删除、移动、路径逃逸、重复目标、公共库直写、缺 receipt anchor、缺知识索引守卫等危险计划。棱镜评审和全量回归还抓出了两个旁路缺口：运行证据目录不能用静态 exact count 管理；飞书降噪时 SessionEnd 仍必须写本地终止标记。两者都已转成补丁与回归。

### 0.2 上一步完成的是

- 上一步完成的是：P1-2 只完成了历史资产 collection-level dry-run，能看出哪些集合可复制、哪些应保留、哪些必须阻塞，但没有到每个文件级别。

### 0.3 下一步计划做的是

- 下一步计划做的是：真实迁移仍需另开风险窗口，在 throwaway worktree 中先做 apply rehearsal，再验证旧路径 alias/link map、docs catalog、receipt anchor 和回滚命令；本轮不直接执行物理迁移。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：collection dry-run → file-level preflight → throwaway apply rehearsal → catalog/link/receipt/rollback 复验 → main-tree apply。
- 当前所在位置：P4-1 `historical-asset-migration-apply-preflight` 已完成 preflight 切片，父任务仍因真实 apply、public release、clean workspace E2E 保持 incomplete。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，那么请继续推进主任务线，务必要和棱镜团队之间配合好，稳步迭代、谨慎评审与验收

### 1.2 触发背景

父任务账本显示当前最高优先级、非外部阻塞的主线是 P4-1：历史资产迁移真实 apply。上一轮只做到目录集合级 dry-run，如果继续推进真实迁移，必须先知道每个文件要如何处理、哪些动作被禁止、哪些证据链不能断。本轮因此只做安全 preflight，先把风险门补齐，不抢跑真实迁移。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 继续推进主任务线，并使用棱镜协作、评审与回归保证质量。 |
| 已覆盖 | 已定位 P4-1 为主线下一刀，生成文件级 preflight manifest，接入 checker、acceptance、spec、diagnose、字典、执行保障、父任务账本和 Prism acceptance。 |
| 未覆盖/延期 | 不执行真实物理迁移，不发布 package，不把历史报告 bulk-copy 到 `redcap-arsenal`，不关闭父任务。 |
| 用户可见边界 | “preflight 已具备”不等于“历史资产已迁移”。 |
| 后续路径 | 另开 throwaway-worktree apply rehearsal，先验证 alias/link map、receipt anchor、docs catalog 和 rollback，再讨论 main-tree apply。 |

---

## 二、方案讨论

### 2.1 问题分析

历史资产不是同一种东西：task reports 是 closeout 证据，research 是低频人类阅读材料，specs 是 active authority，knowledge 是运行时指导，`prism/runs` 和 `compass/.workflow` 是本地运行证据。如果粗暴移动，会同时破坏考古、检索、receipt anchor、知识首读和运行态隔离。正确方式不是“先搬再说”，而是让真实 apply 之前必须先通过文件级 preflight。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 直接真实迁移 | 立刻把历史报告和研究材料搬到新目录 | 表面进度快 | 风险不可接受，容易断链、泄漏公共库、破坏 receipt |
| Q1 | 仅保留 dry-run | 不再推进，只保留集合级说明 | 安全 | 无法继续靠近真实 apply |
| Q1 | 文件级 preflight | 先生成每个文件的计划和强门，真实迁移另开窗口 | 风险可审计、可回滚、可评审 | 仍不是最终物理迁移 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 文件级 preflight | 这是唯一同时满足“继续主线”和“不折损考古/追踪/安全质量”的路径。 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 切换为 P4-1 apply preflight 任务卡，锁定边界、验收、漂移哨兵和承诺账本。 |
| `references/legacy-asset-migration-apply-plan.json` | 新建 | 文件级 preflight manifest，登记 86 个文件级条目和 runtime summary-only 集合。 |
| `compass/tools/redcap-legacy-asset-migration-apply-plan.py` | 新建 | 生成和校验 preflight manifest，拒绝危险 apply 计划。 |
| `compass/tools/redcap-legacy-asset-migration-apply-plan.sh` | 新建 | preflight checker shell 入口。 |
| `compass/tools/redcap-legacy-asset-migration-check.py` | 修改 | 将 `prism-runs`、`runtime-working-dirs` 这类动态运行证据改为 snapshot 计数语义。 |
| `compass/tools/redcap-layerB-session-end.sh` | 修改 | 保证飞书 audit-gap 通知被降噪时，SessionEnd 仍写入本地终止标记，避免并发收尾无法证明已到终态。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 增加 preflight acceptance，并补齐 move、collection-level move、knowledge guard、runtime snapshot、parent receipt pre-receipt fixture、spec-check 新强门传播回归。 |
| `compass/tools/redcap-spec-check.sh` / `compass/tools/redcap-diagnose.sh` | 修改 | 将 apply preflight checker 纳入总回归和诊断。 |
| `references/file-lookup-dictionary.md` / `references/file-lookup-dictionary-policy.json` | 修改 | 登记新 manifest 和 checker，保证后续能按需发现而不是全文考古。 |
| `references/execution-guarantees.json` | 修改 | 新增 apply-preflight 执行保障项。 |
| `references/redcap-parent-task-ledger.md` / `references/parent-receipt-aggregation-policy.json` | 修改 | 父任务视图更新为“preflight 已具备，但真实迁移仍 deferred”。 |
| `compass/knowledge/lessons.md` | 修改 | 沉淀运行时证据目录不能用静态 exact count 当迁移门的经验。 |
| `prism/runs/20260429-historical-asset-migration-apply-preflight/**` | 新建 | Kimi 与 Claude Code 的评审、复验、binding 和风险修复证据。 |

### 3.2 技术实现要点

本轮的核心不是“多一个 JSON 文件”，而是把真实迁移前的安全条件变成可执行门禁。preflight manifest 明确区分了 file-level 历史资产和 collection-summary-only 运行证据；前者继续做精确计数和逐文件计划，后者只保留快照和 retention/check-only 语义，避免运行态变化污染迁移门。

公共库边界也被显性化：`redcap-arsenal` 只接受经过脱敏、去重、append-only 流程的 curated 条目，不承接 raw 历史报告、trace 或 runtime evidence。checker 会拒绝任何指向 `redcap-arsenal` / `shared-knowledge` 的 preflight target，防止把公共能力库误当成历史资产垃圾桶。

棱镜评审不是走过场。第一轮发现 acceptance 对 move 和 knowledge guard 的覆盖不够细；复验又发现 runtime summary-only 计数语义和 collection-level forbidden operation 回归可以更严。两轮意见都已经转为代码和 acceptance，而不是留作报告风险。

全量 acceptance 随后又暴露出两个和本次质量门相关的老夹具问题。第一，飞书降噪后，SessionEnd 在 audit-gap 分支没有写本地终止标记，导致并发用例无法证明会话已到稳定终态；修复方式是只补本地 runtime marker，不重新放开飞书噪声。第二，parent receipt 与 spec-check 的部分验收夹具依赖真实 `.dev-task.md` 或漏掉新增强门 stub；修复方式是让夹具自带任务卡和完整强门依赖，避免验收结果受当前活跃任务污染。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| apply preflight | `references/legacy-asset-migration-apply-plan.json` | 真实迁移前的施工许可清单；它只证明“可以安全准备下一步”，不代表已经搬迁。 |
| copy-first | manifest item operation | 未来如果迁移，先复制到候选目标并保留旧路径；通过 link/receipt/catalog 后才可能进入 delete-last。 |
| collection-summary-only | runtime evidence 集合 | `prism/runs`、`compass/.workflow` 这类运行态目录只做保留/清理策略检查，不逐文件迁移。 |
| receipt anchor | task reports / closeout runtime | 历史报告和 closeout receipt 之间的路径证据链；不能因为迁移导致旧报告引用失效。 |
| redcap-arsenal raw-history block | target authority | 公共知识库不能直接接收原始历史报告或本地运行证据，只能接收脱敏后的沉淀条目。 |

### 3.3 关联变更

父任务账本和 parent receipt aggregation policy 已同步表达当前真实状态：P4-1 preflight 已推进，但 P4-1 真实 apply 仍是 deferred。这样后续状态面不会把“安全门已具备”误写成“资产已迁移”。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 真实迁移目标根目录 | 下一轮如果要执行物理迁移，需要决定私有知识根继续叫 `redcap-knowledge`，还是另建非公共 worktree。 | P1 |
| 2 | 真实 apply 时间窗口 | main-tree apply 前应先在 throwaway worktree 里 rehearsal；是否进入这个风险窗口需要单独立项。 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 语法检查 | `python3 -m py_compile compass/tools/redcap-legacy-asset-migration-check.py compass/tools/redcap-legacy-asset-migration-apply-plan.py` | 通过 |
| dry-run checker | `bash compass/tools/redcap-legacy-asset-migration-check.sh` | 通过 |
| apply preflight checker | `bash compass/tools/redcap-legacy-asset-migration-apply-plan.sh` | 通过 |
| dry-run acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh legacy-asset-migration-check` | 通过 |
| apply preflight acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh legacy-asset-migration-apply-preflight` | 通过 |
| SessionEnd 并发回归 | `bash compass/tools/redcap-multi-session-acceptance.sh layerb-concurrency` | 通过 |
| parent receipt 聚合回归 | `bash compass/tools/redcap-multi-session-acceptance.sh parent-receipt-aggregation-check` | 通过 |
| spec-check 强门传播回归 | `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures` | 通过 |
| spec lifecycle 夹具回归 | `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-accepts-archived-superseded && bash compass/tools/redcap-multi-session-acceptance.sh spec-check-rejects-superseded-outside-archive && bash compass/tools/redcap-multi-session-acceptance.sh spec-check-requires-replaced-by && bash compass/tools/redcap-multi-session-acceptance.sh spec-check-rejects-invalid-role && bash compass/tools/redcap-multi-session-acceptance.sh spec-check-rejects-replacement-cycle` | 通过 |
| full acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过 |
| 文件字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| Prism acceptance binding | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过，6 reviewers，2 families，无 blocker |
| 总规范检查 | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| 诊断总览 | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过，`DIAGNOSE_OK` |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 下一轮真实迁移前，确认私有迁移目标根目录。
- [ ] 下一轮真实迁移前，确认是否进入 throwaway-worktree rehearsal 风险窗口。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 收尾前将由 closeout runtime 核对 |
| 棱镜验收 | 已通过：`20260429-historical-asset-migration-apply-preflight` |
| closeout summary | 无，待 closeout runtime 生成 |
| closeout receipt | 无，待 closeout runtime 生成 |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Kimi 与 Claude Code 双路评审 + 双路复验通过 |
| 已正式完成 | 否，receipt 仍需 closeout runtime 生成 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 真实历史资产物理迁移 | 本轮只做 preflight；真实迁移需要 throwaway rehearsal、alias/link map、receipt anchor 和 rollback 复验。 | P1 |
| 正式 runtime / CLI package public release | 需要 registry、包名、凭证和发布边界决策。 | P2 |
| 跨机器 / clean workspace 安装 E2E | 需要干净目标环境。 | P2 |

### 6.2 触发的新问题

棱镜评审触发了一个经验沉淀：运行时证据目录不能用静态 exact count 当迁移门。该经验已写入 `compass/knowledge/lessons.md` 的 L-140。

全量 acceptance 还暴露出两个通用治理经验：通知降噪不能等于本地终态证据缺失；spec/receipt 夹具不能依赖真实当前任务卡。它们已落成回归用例，不再只停留在文字提醒。

### 6.3 推荐的下一步行动

1. 另开 P4-1 apply rehearsal 任务，在 throwaway worktree 执行真实迁移预演。
2. 在预演中生成 old-path alias/link map，并验证 docs catalog、receipt anchor、task-report-check 与 rollback。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-140 | 运行时证据目录不能用静态 exact count 当迁移门 | 运行态证据会被评审/复活/诊断持续写入，应按 snapshot + retention gate 管理；真正历史资产才做逐文件 exact count。 |
| L-141 | 通知降噪不能删除本地终态证据 | 飞书降噪只影响人类消息，不得影响 SessionEnd 的本地 terminal marker、pending closure 或 receipt 证据。 |
| L-142 | acceptance fixture 不能依赖真实当前任务卡 | 验收夹具必须自带最小任务卡和完整强门 stub，避免当前活跃任务或新增强门污染失败原因。 |

### 7.2 流程改进建议

真实迁移类任务应继续沿用“dry-run → file-level preflight → throwaway rehearsal → main-tree apply”的四段式，不允许直接从 collection manifest 跳到物理移动。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 本轮问题已转成 lesson 与回归门禁 | 无需新增 Evolution candidate | `compass/knowledge/lessons.md` |

---

## 八、附录

### 附录 A：Commits

```text
待提交
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| test | 首轮审查 preflight 安全边界和接线 | Kimi pass；Claude Code pass；发现 report 未生成和测试覆盖改进点 | `prism/runs/20260429-historical-asset-migration-apply-preflight/collect/*-reviewer/parsed.json` |
| test | 复验评审后增量修复 | Kimi pass；Claude Code pass；低风险观察项已转成补丁 | `prism/runs/20260429-historical-asset-migration-apply-preflight/collect/*-followup/parsed.json` |
| test | full acceptance 后最终增量复审 | Kimi pass；Claude Code pass；无 blocker；Claude 记录一个原有静默路径观察项，非本轮阻断 | `prism/runs/20260429-historical-asset-migration-apply-preflight/collect/*-final/parsed.json` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 文件级 preflight：`references/legacy-asset-migration-apply-plan.json`
- 父任务视图：`references/redcap-parent-task-ledger.md`
- 棱镜证据：`prism/runs/20260429-historical-asset-migration-apply-preflight/`

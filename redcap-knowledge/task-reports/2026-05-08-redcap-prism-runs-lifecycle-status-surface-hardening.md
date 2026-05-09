# 任务完成报告：P2-8 Prism runs 生命周期状态面与清理边界加固

**报告日期**：2026-05-08  
**执行者**：Cap（Codex.app + Claude Code / Kimi Prism 复核）  
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：`prism/runs` 的状态面提示已经从“模糊建议清理”改成“先只读审查、再 dry-run 计划、物理删除必须显式批准”的安全口径。
- 详情：本轮没有删除任何运行证据，也没有把 10 个清理候选当成可直接删除结论。现在 Cap 或其他 Agent 看到 current-status 时，会先拿到可复制的真实命令路径，并清楚知道 `prune-local --apply` 是需要 Norven 明确批准的破坏性动作。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2h 已把公共 `redcap-arsenal` 从 template-only 推进到首批 reviewed-substantive 条目，并完成 receipt 收口。

### 0.3 下一步计划做的是

- 下一步计划做的是：若继续自动推进，只能做非发布、非破坏性治理项；正式 npm/public release、许可证、发布凭据、`private=false`、以及真正物理清理 `prism/runs` 都仍需要单独任务和明确边界。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：信息架构治理 → 运行证据生命周期可视化 → 公共知识库首批晋升 → 状态面清理边界加固 → 后续 release readiness / 显式物理清理任务。
- 当前所在位置：P2-8 `redcap-prism-runs-lifecycle-status-surface-hardening`，这是一个非破坏性的状态面治理切片。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮只做提示与策略口径加固，不执行物理删除。若未来要真正运行 `bash prism/tools/prism-runs-lifecycle.sh prune-local --apply`，那时才需要 Norven 明确批准。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，现在请你和棱镜继续稳步推进未完成的任务，完成时序和优先级由你们内部讨论评审和决策即可。另外，我看你已经推进到开始“真实修改项目目录”、“蒸馏知识库到redcap-arsenal”等操作了，这部分的工作请务必做好严格的棱镜评审和把关工作。如果有必要，可以每次执行一步，都做一次阶段性的项目全局扫描和评审。

### 1.2 触发背景

上一轮 closeout 后，`current-status` 暴露出 `prism/runs` 有 10 个超过本地保留阈值的 named-local-evidence。直接物理清理会碰到 RedCap 核心契约红线：运行证据目录默认不 bulk-read，也不能未经明确批准删除。更稳妥的下一步，是先修状态面提示，让未来接盘者不会把候选列表误认为“现在可以删”。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 继续推进未完成任务，并对目录变更、知识蒸馏等高风险动作加强 Prism 评审。 |
| 已覆盖 | 选取一个 current-status 暴露出的可自动推进治理点，修正 `prism/runs` 生命周期提示和物理清理边界。 |
| 未覆盖/延期 | 不执行 npm/public release；不做完整 LLM-wiki/RAG；不批量迁移或删除历史资产；不物理清理 `prism/runs`。 |
| 用户可见边界 | 本轮完成的是“别误删证据”的状态面治理，不是“已经把 prism/runs 清空”。 |
| 后续路径 | 若要真正删除 10 个候选目录，需要单开物理清理任务并取得显式批准。 |

---

## 二、方案讨论

### 2.1 问题分析

`prism/runs` 里的内容不是普通缓存，而是 Prism 评审、运行状态和历史追踪证据。当前生命周期工具已经能分出 formal-run、named-local-evidence、acceptance-fixture 和 `.locks`，但状态面旧提示只写了一个不完整命令名，缺少真实路径和 `--apply` 权限边界。这个缺口不会立刻造成测试失败，但会在长任务接盘时诱导 Agent 把“审查清理候选”理解成“可以直接清理”。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 选项 A | 直接执行 `prune-local --apply` 清理 10 个候选 | 目录数量立刻下降 | 违反显式批准红线，可能误删仍有考古价值的证据 |
| Q1 | 选项 B | 只修状态面和策略提示，把清理动作留给显式任务 | 避免破坏证据，同时提升后续接盘安全性 | 目录数量不会立刻下降 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 选项 B | 用户授权继续推进，但 RedCap 核心契约把物理清理列为需要显式批准的动作；因此本轮只做无破坏治理。 | CAP_DECIDE + Prism review |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `compass/tools/redcap-current-status.py` | 修改 | `prism/runs` warning 现在展示真实命令路径，标注 `inventory` 只读、`prune-local` dry-run，并明确 `--apply` 禁止未批准执行。 |
| `references/token-structural-governance.json` | 修改 | token 风险治理策略同步为 dry-run-first / explicit-approval-before-apply 口径。 |
| `references/redcap-parent-task-ledger.md` | 修改 | 登记 P2-8 已完成，并明确“不等于已经物理清理运行证据”。 |
| `compass/docs/task-reports/2026-05-06-llm-wiki-asset-stratification.md` | 移出活跃 inbox | 因新增本报告后 active task-reports 超过 12 个上限，按信息架构规则把一份不被父任务 receipt 聚合引用的报告归档到私有知识库。 |
| `redcap-knowledge/task-reports/2026-05-06-llm-wiki-asset-stratification.md` | 新归档位置 | 保留历史报告考古能力，不进入公共库，也不被默认首读。 |
| `prism/reports/2026-05-08-prism-runs-lifecycle-status-surface-hardening.md` | 新建 | 保存本轮 Prism 复核摘要。 |
| `prism/reports/index.yaml` | 修改 | 登记本轮 Prism run。 |
| `prism/runs/20260508-prism-runs-lifecycle-status-surface-hardening/**` | 新建 | 保存 Claude Code 与 Kimi 的原始和结构化评审证据。 |

### 3.2 技术实现要点

这次的核心不是“清理目录”，而是把清理路径从一个模糊提醒变成一个安全操作阶梯。第一步是 `inventory` 只读查看；第二步是 `prune-local` dry-run 生成计划；第三步 `prune-local --apply` 才是物理删除，必须等 Norven 明确批准。这样既保留了运行证据的考古价值，也减少了未来 Agent 因提示不清而越权执行的概率。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| `prism/runs` | `prism/runs/**` | 棱镜每次运行留下的本地证据，不是普通垃圾目录。 |
| `inventory` | `bash prism/tools/prism-runs-lifecycle.sh inventory` | 只读列出每个 run 的类型、年龄、是否活跃、是否可作为清理候选。 |
| `prune-local` | `bash prism/tools/prism-runs-lifecycle.sh prune-local` | 只生成本地命名证据的清理计划；不带 `--apply` 时不删除文件。 |
| `prune-local --apply` | `bash prism/tools/prism-runs-lifecycle.sh prune-local --apply` | 真正物理删除候选目录的动作，本轮禁止执行，未来也需要显式批准。 |

### 3.3 关联变更

父任务账本同步新增 P2-8，避免未来状态概览只看到 warning，却不知道本轮已经完成提示边界加固。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 是否要真正物理清理 10 个 named-local-evidence 候选 | 这会删除本地运行证据，必须单独批准；本轮没有执行。 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| Prism runs lifecycle | `bash prism/tools/prism-runs-lifecycle.sh check` | ✅ |
| Prism runs summary | `bash prism/tools/prism-runs-lifecycle.sh summary` | ✅：acceptance-fixture=0，formal-run=44/45，named-local-evidence=13，pruneable_local=10 |
| Token risk audit | `bash compass/tools/redcap-token-risk-audit.sh` | ✅ |
| Current status surface | `bash compass/tools/redcap-current-status.sh .dev-task.md` | ✅：显示只读 / dry-run / `--apply` 禁区 |
| Targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh current-status-overview` | ✅ |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | ✅：2 reviewers，2 families，0 blocker |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 若未来要删除候选目录，需要 Norven 明确批准 `prune-local --apply`。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已清 |
| 棱镜验收 | 通过 |
| closeout summary | closeout 时生成 |
| closeout receipt | closeout 时生成 |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是 |
| 已正式完成 | 否；等待 closeout runtime 生成 receipt |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 10 个 named-local-evidence 候选是否要物理删除 | 删除运行证据需要显式批准，不能混在提示修复里偷做。 | P1 |
| 正式 npm/public release | 仍涉及许可证、发布凭据、`private=false` 等人工边界。 | P0-before-release |
| full LLM-wiki / RAG / GraphRAG | 属于阈值型未来工作，不由本轮触发。 | P2-thresholded |

### 6.2 触发的新问题

无新增必须立刻处理的问题。Claude Code 提到 tracking-health 的 explore_notes 噪音与本补丁无关，未作为 blocker。

### 6.3 推荐的下一步行动

1. 若 Norven 明确批准，再单开 `prism/runs` physical prune apply 任务。
2. 否则继续推进父任务中非发布、非破坏性的治理项；正式 release 仍等待人工边界。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| 无 | 无新增私有 lesson | 本轮是既有 L-99 的执行口径加固，不需要新增重复 lesson。 |

### 7.2 流程改进建议

状态面只要提到可能 destructive 的命令，就要同时写清“只读 / dry-run / apply”的三段边界；否则后续 Agent 容易把治理建议误当执行许可。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | Prism runs lifecycle 状态面加固 | no-promote；既有 lesson 已覆盖，未重复沉淀 | `compass/knowledge/lessons.md` L-99 |

---

## 八、附录

### 附录 A：Commits

```
待提交
```

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|----------|
| test | 状态面是否足以防止误删 `prism/runs` 证据 | Claude Code pass；Kimi pass；0 blocker | `prism/reports/2026-05-08-prism-runs-lifecycle-status-surface-hardening.md` |

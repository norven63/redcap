# 任务完成报告：三分 RedCap 前进刻度表结论补棱镜评审

**报告日期**：2026-05-10
**执行者**：Cap（Codex + Prism: Kimi / Claude Code）
**报告版本**：v1.1

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：之前由 Cap 单人提出的“三分 RedCap 前进刻度表”已经补做棱镜评审；Kimi 与 Claude Code 均给出 pass，且无 blocker。
- 详情：棱镜共同认可三分法方向，但要求它只能是“聚合视图”，不能变成新的任务真相源。也就是说，它负责让人和 AI 看懂 RedCap 当前处在什么阶段，而不是替代 `.dev-task.md`、backlog、receipt、evolution candidates、legacy lifecycle 等已有权威记录。

### 0.2 上一步完成的是

- 上一步完成的是：`redcap-change-intent-continuity-gate` 已修好“继续/接下来/按计划推进”类指令的任务锚点硬门，并生成 closeout receipt。

### 0.3 下一步计划做的是

- 下一步计划做的是：按棱镜通过的结论，进入第 3 步实现：把 RedCap 前进刻度表与棱镜使用场景优化逐项落地。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：续接不跑偏 -> 三分法结论补棱镜评审 -> 三分进度仪与棱镜使用优化落地。
- 当前所在位置：第二步“结论补棱镜评审”已完成；下一步是把评审通过的任务树转为实现任务。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮只做架构结论复核与任务树准入，不涉及发布、公开迁移、物理删除、许可证、凭据或不可逆操作。

---

## 一、需求背景

Norven 指出：前面关于“三分法 / RedCap 前进刻度表”的结论是 Cap 单人建议，缺少棱镜评审，不能直接作为 RedCap 官方结论落盘。本轮目标就是补齐这次评审，并把通过后的内容转成后续可执行任务树。

---

## 二、方案讨论

### 2.1 共同通过的结论

| 结论 | 棱镜意见 |
|---|---|
| RedCap 需要“前进刻度表” | 通过；它能把历史债务、当前聚焦任务、长期演进清楚分开。 |
| 中间桶不应叫“npm 发布” | 通过；“当前专注任务集”更通用，机器层仍应映射到 `active_slice/current_focus`。 |
| 机制归属 | 通过；三分法本身属于 RedCap 公共治理，具体 Norven 私有条目留在本地任务报告/知识里。 |
| 人类入口和 AI 入口分开 | 通过；人类看短叙事和当前位置，AI 看机器锚点、receipt、backlog、验收状态。 |
| 三个例子分类 | 通过；公共库大迁移是长期演进，历史资产物理删除是被 destructive gate 阻塞的历史债务清理，Codex.app 100% hook 证明是宿主受限长期演进。 |

### 2.2 必须遵守的边界

- 前进刻度表是视图层，不是新真相源。
- 不新增第四个大桶；“阻塞中 / 待评审 / 待 receipt”是状态，不是新类别。
- 默认 `current-status` 不应更吵；人类默认只看简明全景，完整细节应按需展开。
- 已解决债务不能无限留在 active meter，必须归档或总结。

---

## 三、落地结果

| 任务 | 分类 | 准入结果 | 下一步 |
|---|---|---|---|
| 建立 RedCap 前进刻度表策略 | 当前专注任务集 | 通过 | 进入第 3 步实现 |
| 前进刻度表聚合现有真相源 | 当前专注任务集 | 通过 | 从 `.dev-task.md`、backlog、evolution candidates、governance debt、legacy lifecycle、Prism lifecycle 聚合 |
| 人类/AI 双入口 | 当前专注任务集 | 通过 | 默认人类短摘要，AI 侧机器可读 |
| 债务条目生命周期字段 | 当前专注任务集 | 通过 | 最小字段：owner/status/reason/expiry-review/closeout/archive |
| 公共 arsenal 大规模迁移 | 长期演进专项 | 不进入当前实现 | 需要脱敏、去重、隐私审查和公共仓库策略 |
| 历史资产大规模物理删除 | 历史债务坏味，但阻塞 | 不自动执行 | 需要 destructive cleanup / receipt anchor 风险评审 |
| Codex.app 交互式 hook 100% 宿主级证明 | 长期演进专项 | 不进入当前实现 | 受宿主能力证明约束 |

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| 前进刻度表 | 后续待实现的 progress-meter policy/status surface | 让人一眼知道 RedCap 当前是在还历史债、推进当前任务，还是规划长期演进。 |
| 历史债务坏味 | `governance-debt-register`、legacy/prism lifecycle 类资产 | 已知不够优雅、过时、冗余或有风险的旧机制/旧资产，需要治理但不一定阻塞当前任务。 |
| 当前专注任务集 | `.dev-task.md`、backlog current focus、Layer B FSM | RedCap 现在正在推进、需要完成和收口的任务范围。 |
| 长期演进专项 | evolution candidates、长期路线、host-limited proof | 有价值但不应抢占当前任务的未来增强方向。 |
| 聚合视图 | current-status/report 这类展示面 | 它只读取和归纳已有权威记录，不自己发明新的事实。 |

---

## 四、人工审核要点

- 本轮不需要 Norven 人工介入；它只补齐此前缺失的棱镜评审，不触发发布、删除、公开迁移或凭据相关决策。
- 本轮不能被理解为“三分进度仪已经实现”；它完成的是“结论可以进入实现任务树”的前置认证。
- 后续实现时，验收重点是检查进度仪是否只聚合既有真相源，不能新增一个和现有账本竞争的事实来源。

---

## 五、验证结果

| 验证项 | 结果 |
|---|---|
| PM Gate / intent / change-intake | 通过 |
| Kimi 架构评审 | pass，无 blocker |
| Claude Code 架构评审 | pass，无 blocker |
| Prism acceptance binding | pass，2 个 distinct families |
| Prism 真实任务默认超时 | 通过，acceptance 断言 baton 默认等待为 600 秒 |
| redcap-diagnose | 通过 |

### 5.4 完成等级（禁止混报）

| 等级 | 本轮结论 |
|---|---|
| 已实现 | 是，本轮已实现“补棱镜评审与任务树准入”；不是实现三分进度仪本体。 |
| 已自检 | 是，PM Gate、intent、change-intake、Prism acceptance 与报告质量门禁已进入验证链。 |
| 已独立验收 | 是，Kimi 与 Claude Code 均完成架构评审并给出 pass、无 blocker。 |
| 已正式完成 | 否，仍待本报告提交后执行 closeout receipt；receipt 生成前不能宣称正式完成。 |

---

## 六、遗留问题与下一步

下一步不是继续讨论三分法是否合理，而是进入实现：增加 progress-meter policy/checker/status surface/report summary，并把棱镜使用场景优化一并按任务树推进。实现时仍要遵守本轮边界：三分进度仪只能聚合现有真相源，不能另建一个和现有账本打架的新账本。

---

## 七、经验沉淀

### 7.1 新增 Lesson

| 编号 | 标题 | 核心内容 |
|---|---|---|
| L-160 | 进度仪只能是聚合视图，不能成为新真相源 | 多视角进度表的价值是降低人类认知负担，但权威仍应来自已有账本、receipt、backlog 和生命周期文件。 |

### 7.2 流程改进建议

下一步实现前进刻度表时，先建立 policy/checker，明确每个桶的来源映射和禁止重复存储规则；再接入 current-status/report 模板，避免默认输出变得更吵。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|---|---|---|---|
| RedCap 前进刻度表 | Norven Q1 + Prism 双路评审 | promoted：进入第 3 步实现任务 | 本报告 §2-§3 |
| “进度仪只能是聚合视图” | Kimi / Claude Code 共同约束 | promoted：沉淀为 L-160 | `compass/knowledge/lessons/l-160.md` |
| 公共 arsenal 大规模迁移 | 三分法示例分类 | defer：长期演进专项，不进入当前实现 | 本报告 §3 |

no-promote：本轮没有新增 Evolution candidate pool 条目；通过项直接进入第 3 步实现任务树，延期项留在长期演进/历史债务分类中等待后续正式立项。

---

## 八、附录

### 附录 A：棱镜调用记录

| Agent | 结论 | 证据 |
|---|---|---|
| Kimi | pass，无 blocker | `prism/runs/20260510-progress-meter-prism-review/collect/kimi-reviewer.txt` |
| Claude Code | pass，无 blocker | `prism/runs/20260510-progress-meter-prism-review/collect/claude-reviewer.json` |

### 附录 B：Commits

```
待提交
```

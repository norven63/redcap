# 任务完成报告：LLM-wiki 资产分层评估与需求登记

**报告日期**：2026-05-06
**执行者**：Cap（Codex + Prism: Kimi, Claude Code）
**报告版本**：v0.1

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已完成一次全局资产分层评估，明确哪些内容适合进入未来的 LLM-wiki-lite 语义记忆层，哪些必须留在控制面、原始证据层、公共库、索引层或可执行流程层。
- 详情：本轮解决的是“长期记忆应该吸收什么、不能吸收什么”的边界问题。最终结论是：LLM-wiki 可以服务 AI 和人类的长期理解，但只能作为私有、非权威、带来源锚点的语义记忆缓存；它不能替代任务账本、承诺账本、receipt、Prism 验收、原始报告、运行证据或发布安全门禁。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2h-1 已把 AI Era 导读资料中的长期记忆和工程纪律思想吸收到 RedCap 契约中，但没有直接建设完整 Wiki、RAG、GraphRAG 或公共写回能力。

### 0.3 下一步计划做的是

- 下一步计划做的是：完成本轮 closeout runtime 收口后，主任务线新增并保留 P4-2h-3，用于后续实现 LLM-wiki-lite 的最小生命周期：私有语义记忆 schema、来源锚点、过期检测、Forge 公共晋升边界和控制面接线。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-2h-0 公共蒸馏预检 → P4-2h-1 行业资料吸收 → P4-2h-2 LLM-wiki 资产分层评估 → P4-2h-3 LLM-wiki-lite 生命周期实现 → P4-2h 真实公共蒸馏与 P4-2 release 主线。
- 当前所在位置：P4-2h-2 已完成资产评估、棱镜评审、主任务线登记和机器检查；正式完成凭证仍等待 closeout runtime receipt。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要
- 说明：本轮没有遇到必须由 Norven 决策的事项。是否建设完整 LLM-wiki、是否启用 RAG/GraphRAG、是否把公共 arsenal 变成实质知识库，均已作为后续独立任务边界处理，不阻塞本轮收口。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，那么你和棱镜执行一次全局redcap的各资产评估，看看哪些是适合用LLM-wiki存储的，哪些是其他层或者方式存储的。然后列一个独立的新增需求，加入到主任务线中。至于执行的优先级，完全由你和棱镜团队内部自行按照正确的工程规范和模式来评估和决策即可。

### 1.2 触发背景

RedCap 已经进入长期记忆、公共知识库和发布前工程结构治理的深水区。此前我们刚讨论过 LLM-wiki、GraphRAG、公共 arsenal、RedCap Forge 和运行时产物治理的关系；如果不先分清资产归属，就容易把“语义记忆”误建成一个新的大仓库，把控制面、证据面、公共知识和运行缓存混在一起，最终重新引发 token 爆炸、隐私泄漏和权威不清。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 由 Cap 与 Prism 评估 RedCap 当前各类资产是否适合进入 LLM-wiki 或其他存储治理层，并把结论形成独立新增需求接入主任务线。 |
| 已覆盖 | 已覆盖控制面、宿主入口、策略文件、可执行脚本、当前报告、私有知识、冷归档、Prism 报告、Prism 原始运行、Evolution/Forge 候选、公共模板、外部 arsenal、索引字典和 package surface。 |
| 未覆盖/延期 | 不实现完整 LLM-wiki 系统；不启用后台自动蒸馏；不启用 RAG、GraphRAG 或向量库；不把私有原文导出到公共 arsenal。 |
| 用户可见边界 | 可以声明“RedCap 已知道哪些资产适合进入 LLM-wiki-lite，并已登记实现需求”；不能声明“RedCap 已经拥有完整 LLM-wiki 长期记忆系统”。 |
| 后续路径 | P4-2h-3 负责后续最小实现，且必须继续保持私有、非权威、来源锚定和 Forge 公共晋升边界。 |

---

## 二、方案讨论

### 2.1 问题分析

LLM-wiki 对 RedCap 有价值，因为它可以把跨报告、跨任务、跨长期对话中反复出现的稳定概念沉淀为 AI 和人类都能读懂的语义记忆。但它也很危险：如果把活任务、运行证据、Prism 原始输出、identity 或策略 JSON 直接塞进 Wiki，就会让一个“帮助理解的层”变成新的真相源，甚至变成新的上下文炸弹。

因此本轮采取分层路线：控制面继续负责“什么是真的、什么完成了”；原始证据层负责“当时发生了什么”；索引层负责“如何按需找到资料”；公共 arsenal 负责“经安全审查后的共享知识”；LLM-wiki-lite 只负责“对稳定概念和经验进行私有语义缓存”。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| 长期记忆路线 | 直接建设完整 LLM-wiki | 立刻实现 Wiki、自动写回和检索层 | 目标完整 | 范围过大，容易绕过 Forge、安全审查和控制面 |
| 长期记忆路线 | 暂不处理 | 继续只靠报告、索引和 rg | 风险低 | RedCap 仍缺少稳定语义记忆边界 |
| 长期记忆路线 | 先做资产分层和需求登记 | 先明确什么能进 Wiki、什么不能进，再登记实现任务 | 可验证、低风险、便于后续实现 | 还不是完整 LLM-wiki 实现 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| 长期记忆路线 | 先做资产分层和需求登记 | Kimi 首轮指出控制策略、宿主入口、隐私分类和过期边界不足；修正后 Kimi 与 Claude Code 均认可该边界，认为剩余风险可进入后续实现任务处理。 | CAP_DECIDE + PRISM_REVIEW |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `references/llm-wiki-asset-stratification-policy.json` | 新建 | 记录 RedCap 资产分层、LLM-wiki 候选类型、禁止内容、来源锚点、隐私边界和 P4-2h-3 后续需求。 |
| `compass/tools/redcap-llm-wiki-asset-stratification-check.py` / `.sh` | 新建 | 校验分层策略是否保持私有、非权威、来源锚定，不冒充完整实现，不默认启用 RAG/GraphRAG。 |
| `references/pre-release-structure-refactor-task-tree.json` | 修改 | 登记 P4-2h-2 已完成，并新增 P4-2h-3 planned。 |
| `references/redcap-parent-task-ledger.md` | 修改 | 把 LLM-wiki 资产分层和未来实现需求接入父任务线。 |
| `references/file-lookup-dictionary.md` / `.json` | 修改 | 让策略和检查器进入可发现索引，避免后续 Agent 不知道它们存在。 |
| `references/execution-guarantees.json` | 修改 | 把 LLM-wiki 资产分层加入执行保障清单。 |
| `compass/tools/redcap-spec-check.sh` / `redcap-diagnose.sh` | 修改 | 把新增检查器接入总体验证和诊断。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 增加定向 acceptance 和 spec-check 失败传播回归。 |
| `prism/reports/2026-05-06-llm-wiki-asset-stratification-review.md` / `index.yaml` | 新建/修改 | 记录 Kimi 与 Claude Code 的评审结论。 |

### 3.2 技术实现要点

本轮没有把 LLM-wiki 做成新的“总仓库”。真正落地的是一份分层政策和一组机器检查：它们规定 Wiki 只能吸收稳定概念、设计哲学、术语解释、反复失败后的经验模式和决策框架；活任务状态、原始私有对话、可执行代码、Prism raw、identity 原文、索引和包发布契约都不能被 Wiki 接管。

这套边界的核心效果是：未来建设 LLM-wiki-lite 时，Agent 不需要重新争论“哪些东西该进 Wiki”，而是先按这份政策筛选候选，再通过来源锚点、过期规则和 Forge 晋升边界逐步推进。它保护的是长期记忆质量，也保护 RedCap 的真相源不被语义摘要污染。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| LLM-wiki-lite | P4-2h-3 planned follow-up | 面向 AI 和人类的私有语义记忆最小实现，不是完整 Wiki/RAG 系统。 |
| source anchor | `source_anchor_contract` | 每条语义记忆都必须能追溯到来源文件、来源类型、版本或摘要指纹和最近复核时间。 |
| control-plane truth | `.dev-task.md`、承诺账本、receipt、策略文件 | 负责判断任务边界、完成状态和机器事实的权威层。 |
| raw evidence | 原始报告、Prism runs、runtime receipt、冷归档 | 记录事实发生过程的证据层，只能按需读取或蒸馏，不能直接变成 Wiki 正文。 |
| RedCap Forge | 公共知识晋升流程 | 负责把私有候选经过脱敏、去重、安全审查后追加到公共 arsenal。 |
| retrieval escalation | 检索升级策略 | 默认先用 catalog、rg 和 metadata；只有规模和复杂度跨阈值时，才评估 RAG/GraphRAG。 |

### 3.3 关联变更

新增报告后，`compass/docs/task-reports` 的活跃窗口会继续保持小规模；最旧的活跃报告被移到 `redcap-knowledge/task-reports` 冷归档，避免当前任务入口再次堆积。这个动作只改变“默认可见位置”，不删除考古证据。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 当前无必须人工介入项 | 本轮只是资产分层和需求登记，不要求 Norven 决定完整 LLM-wiki、RAG/GraphRAG 或公共知识发布策略。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| LLM-wiki 分层策略检查 | `bash compass/tools/redcap-llm-wiki-asset-stratification-check.sh` | 通过 |
| 定向 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh llm-wiki-asset-stratification-check` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过 |
| 文件查找字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| 后续综合回归 | `spec-check` / `diagnose` / `full acceptance` | 等待 closeout 前最终重跑 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [x] 当前无必须人工验证项；完整 LLM-wiki、GraphRAG 或公共 arsenal 实质内容建设均已作为后续独立任务边界处理。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 等待最终 closeout 前同步 |
| 棱镜验收 | 通过，Kimi challenger + Claude Code reviewer，2 个模型家族，无 blocker |
| closeout summary | 无，等待 closeout runtime 收口 |
| closeout receipt | 无，等待 closeout runtime 收口 |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是，定向检查与 Prism acceptance 已通过 |
| 已独立验收 | 是，Kimi + Claude Code 评审已归档 |
| 已正式完成 | 否，等待 closeout runtime receipt |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| P4-2h-3 LLM-wiki-lite 生命周期实现 | 本轮只负责分层评估与需求登记；实现私有 Wiki schema、source anchor 和过期检测需要独立任务。 | P1 |
| RAG / GraphRAG / 向量库 | 当前仍应先遵守 catalog + rg + metadata 的渐进式检索路线，跨阈值后再评估升级。 | P3 |
| 公共 arsenal 实质内容迁移 | 公共写入必须经过 RedCap Forge，不应由本轮直接导出。 | P1 |

### 6.2 触发的新问题

本轮没有触发必须立即扩大范围的新问题。Kimi 首轮提出的资产覆盖、隐私分类和过期边界已被吸收到当前策略；剩余内容已经落到 P4-2h-3 的后续实现范围。

### 6.3 推荐的下一步行动

1. 完成本轮 closeout runtime receipt，确保 P4-2h-2 只以“评估与需求登记”身份关闭。
2. 回到父任务线，按 P4-2g 的结构重构任务树继续推进 P4-2h-3 或其他优先子任务。
3. 若推进 P4-2h-3，优先实现私有 schema、source anchor、过期检测和 Forge 边界，再讨论自动后台蒸馏或 RAG/GraphRAG。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| 无 | 本轮不直接写 lessons | 本轮是策略和需求登记，已由机器政策和父任务线承载；是否转为 lesson 可由后续 Evolution/Forge 候选流程判断。 |

### 7.2 流程改进建议

长期记忆建设不应从“先建 Wiki”开始，而应从资产分层开始。先确定真相源、证据源、索引源、公共输出源和语义缓存源的边界，才能避免 Wiki 变成新的混乱总仓。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | LLM-wiki 资产分层任务 | 本轮直接作为 P4-2h-2 已授权任务落地，不另建候选 | `references/llm-wiki-asset-stratification-policy.json` |

---

## 八、附录

### 附录 A：Commits

```
待提交：LLM-wiki 资产分层评估与需求登记
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|----------|
| challenger | 初版资产分层是否覆盖控制策略、宿主入口、隐私和过期边界 | 首轮阻塞，修正后通过 | `prism/reports/2026-05-06-llm-wiki-asset-stratification-review.md` |
| reviewer | 修正后的 LLM-wiki 边界是否可接受 | 通过，剩余风险为低风险后续实现项 | `prism/reports/2026-05-06-llm-wiki-asset-stratification-review.md` |

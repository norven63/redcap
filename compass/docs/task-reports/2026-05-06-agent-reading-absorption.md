# 任务完成报告：AI Era agent-reading 吸收与长期记忆对齐

**报告日期**：2026-05-06
**执行者**：Cap（Codex + Prism: Kimi, Claude Code）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已把 AI Era 导读资料中适合当前阶段的工程纪律和长期记忆设计，吸收成可机器检查的契约。
- 详情：本轮解决的是“看到业内长期记忆 / LLM Wiki 思路后，RedCap 应该怎么吸收，而不是盲目照搬”的问题。最终做法是：保留 RedCap 现有 Forge、安全边界和检索阈值，只吸收显式假设、简单优先、外科式修改、可验证循环，以及 Raw/Wiki/Schema、Ingest/Query/Lint 这些可对齐的设计。现在 RedCap 有了 append-only 知识时间线和专门检查器，可以阻断“直接公共写入”“默认启用 RAG”“冒充完整 Wiki”等过度声明。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2h-0 只建立了历史资产进入公共蒸馏前的 dry-run 预检强门。本轮接着把外部行业资料吸收到长期记忆和工程纪律层，但仍不进入真实公共蒸馏、不写公共 arsenal。

### 0.3 下一步计划做的是

- 下一步计划做的是：本轮吸收契约完成后，主线仍回到 P4-2 的发布前整改与 P4-2h 的后续真实公共蒸馏；是否建设完整 LLM Wiki、独立 Schema 层、RAG/GraphRAG 或学习教练能力，都必须另开架构任务。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-2h-0 公共蒸馏预检 → P4-2h-1 行业资料吸收 → P4-2h 真实公共蒸馏候选 → P4-2 正式 release 任务。
- 当前所在位置：P4-2h-1 已实现、已通过定向验收与 closeout runtime 收口；父任务仍回到 P4-2/P4-2h 后续边界。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要
- 说明：本轮没有遇到必须由 Norven 决策的冲突。需要人工保留的更大选择已经显式延期：是否建设完整 LLM Wiki、是否启用 RAG/GraphRAG、是否把 query 答案直接沉淀成公共条目、是否把 `ai-professor-mode` 产品化。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> /Users/norven/workspace/AI Era/docs/agent-reading-guide.md
>
> 这里有一份导读文档，可能对于你接下来的任务推进和设计有所帮助。你可以和棱镜团队自行决策应该如何根据导读文档去评估应该修改和完善redcap的相关设计（我强烈建议要高度吸收相关资料中的设计，因为这些资料都是当下业内比较认可与流行的方案）。并且你和棱镜团队可以自行把这个“吸收”的过程和方案融入到当前主任务线中合适的位置和优先级。
> 之所以我现在提出这个需求，是因为我觉得你正在执行的任务内容和这个是强相关的，尤其是涉及到长期记忆的功能。
> 另外，【重点提一下】，如果你和棱镜团队发现评估过程中遇到了无法抉择的问题，需要我人工介入，可以立即中断并告知我，让我立即加入到评估决策环节中。因为我有预感，这次的新需求和你之前的方案设计可能发生冲突，当然这是我的预感，并不代表一定就有，你不用被我暗示和误导，一切以你与棱镜的评估为准。

### 1.2 触发背景

RedCap 刚完成公共蒸馏 preflight，正处在长期记忆、公共知识库和 RedCap Forge 边界逐步成形的阶段。AI Era 导读资料中提到的工程执行纪律和 LLM Wiki 模式，与当前 RedCap 的长期记忆路线高度相关；但如果直接照搬，会和 RedCap 已有的私有/公共边界、candidate-only 晋升、检索阈值策略发生冲突。因此本轮采用“吸收原则，不偷换架构边界”的方式推进。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 由 Cap 和棱镜团队评估 AI Era 导读及源文档，决定如何吸收进 RedCap 当前主任务线，尤其长期记忆设计。 |
| 已覆盖 | 已阅读导读、`ai-engineer.md`、`llm-wiki.md` 和 `ai-professor-mode.md`；完成 Kimi + Claude Code 棱镜评审；落地吸收策略、知识日志、检查器、执行保障、索引、父任务线和 acceptance。 |
| 未覆盖/延期 | 不建设完整 LLM-owned Wiki；不启用 RAG/GraphRAG/向量库；不直接写公共 arsenal；不把 `ai-professor-mode` 做成生产能力；不真实执行 P4-2h 公共蒸馏。 |
| 用户可见边界 | 可以声明“RedCap 已将外部行业资料吸收为可审计长期记忆契约”；不能声明“RedCap 已实现完整 LLM Wiki 系统”或“公共知识库已有新增实质内容”。 |
| 后续路径 | 若以后要建设完整 Wiki/Schema/RAG/学习教练能力，需要单独立项并通过 Prism 架构评审。 |

---

## 二、方案讨论

### 2.1 问题分析

`ai-engineer.md` 更像工程执行纪律，对 RedCap 当前工作流是低冲突增强；`llm-wiki.md` 提供的是长期记忆系统的结构模式，对 RedCap 很有价值，但不能直接变成一个由 LLM 全权维护的 Wiki 层，因为 RedCap 已经有私有证据、受控知识、公共 Arsenal、Forge 安全审查和检索升级阈值。`ai-professor-mode.md` 目前只是学习教练提示草稿，和本轮长期记忆主线相关性较弱，直接写入核心会扩大范围。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| 外部资料吸收 | 全量照搬 LLM Wiki | 新增完整 Wiki/Schema/自动维护层 | 未来能力完整 | 当前边界太大，容易绕过 Forge 和隐私审查 |
| 外部资料吸收 | 完全不吸收 | 只记录“看过了” | 风险最低 | 浪费行业资料价值，也不能改善长期记忆设计 |
| 外部资料吸收 | 低冲突契约吸收 | 只吸收工程原则、记忆分层和操作模型，并接入机器检查 | 能立即增强 RedCap，又不突破安全边界 | 完整 Wiki/RAG 能力仍需后续任务 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| 外部资料吸收 | 低冲突契约吸收 | Kimi 与 Claude Code 均认为资料有价值，但完整 Wiki/Schema/RAG 需要单独架构决策；当前最安全的是把它们映射进现有 RedCap 控制面。 | CAP_DECIDE + PRISM_REVIEW |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `references/agent-reading-absorption-policy.json` | 新建 | 记录源资料处置、已吸收原则、长期记忆映射、延期边界和禁止声明。 |
| `compass/tools/redcap-agent-reading-absorption-check.py` / `.sh` | 新建 | 校验吸收策略是否保持 candidate-only、禁止公共直写、禁止默认 RAG/GraphRAG、要求知识日志和索引可见。 |
| `compass/knowledge/log.md` | 新建 | 新增 append-only 知识时间线，用来记录外部资料吸收这类 durable memory 事件。 |
| `compass/knowledge/index.md` | 修改 | 把知识日志加入首读索引，避免后续 Agent 不知道它的存在。 |
| `compass/tools/redcap-spec-check.sh` / `redcap-diagnose.sh` | 修改 | 把吸收检查器纳入总体验证和诊断。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 增加定向 acceptance 和 spec-check 失败传播回归。 |
| `references/execution-guarantees.json` | 修改 | 把外部资料吸收登记为执行保障项。 |
| `references/file-lookup-dictionary.md` / `.json` | 修改 | 把策略、检查器、知识日志加入文件查找字典。 |
| `references/redcap-parent-task-ledger.md` | 修改 | 登记 P4-2h-1，并明确它不等于 P4-2h 真实公共蒸馏。 |
| `references/pre-release-structure-refactor-task-tree.json` | 修改 | 把 P4-2h-1 加入发布前结构重构任务树。 |
| `references/legacy-asset-migration-dry-run.json` / `legacy-asset-migration-apply-plan.json` | 修改 | 同步新增 `compass/knowledge/log.md` 后的历史资产治理计数和预检项。 |
| `references/pre-release-product-architecture-review.json` | 修改 | 同步 runtime package 候选文件数量，保持发布前架构审判事实面不漂移。 |
| `prism/runs/20260506-agent-reading-absorption-review/**` | 新建 | 归档 Kimi / Claude Code 的有效评审与 Claude 首次无效尝试边界。 |
| `prism/reports/2026-05-06-agent-reading-absorption-review.md` / `index.yaml` | 新建/修改 | 记录本轮 Prism 结论。 |

### 3.2 技术实现要点

本轮没有新增一个“更大的 Wiki 系统”，而是把外部资料转译进 RedCap 现有的三层记忆结构。Raw evidence 对应私有报告、Prism runs、runtime receipt 和外部资料；synthesis 对应知识索引、知识日志、lessons、Evolution candidates 和经 Forge 晋升后的 Arsenal 条目；schema 对应 `references/*.json` 和 shared-knowledge schema。这样做的好处是：长期记忆能力增强了，但不会越过已有安全门禁。

检查器刻意验证“不能做什么”：不能允许 ingest 直接公共写入，不能允许 query 答案直接写公共库，不能默认打开 RAG/GraphRAG，也不能把 ai-professor 草稿说成核心能力。这个方向和 `ai-engineer.md` 的简单优先、外科式修改一致：先补最小可验证闭环，不把新资料变成复杂度炸弹。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| Raw evidence | 私有报告、Prism runs、receipt、外部源资料 | 原始证据，只能按需读取和蒸馏，不能直接公开。 |
| synthesis layer | `compass/knowledge/index.md`、`log.md`、`lessons.md`、Evolution candidates | 经过整理的知识层，用来让后续 Agent 更快理解，但仍受 RedCap 规则约束。 |
| schema layer | `references/*.json`、`shared-knowledge/schemas/*.json` | 机器可检查的规则和数据结构。 |
| candidate-only writeback | Evolution / Forge 候选流程 | 好答案可以成为候选，但不能绕过审查直接写公共库。 |
| agent-reading absorption | `references/agent-reading-absorption-policy.json` | 本轮“吸收外部资料”的边界契约。 |

### 3.3 关联变更

新增知识日志后，旧资产迁移 dry-run 和 apply-plan 的知识文件计数必须同步，否则历史资产治理门禁会认为 RedCap 的知识资产清单过期。本轮已同步这部分计数和预检项，避免新机制把旧资产治理打破。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 当前无必须人工介入项 | 完整 Wiki / RAG / 学习教练这些都是后续产品决策，本轮已明确延期，不阻塞当前收口。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 吸收策略检查 | `bash compass/tools/redcap-agent-reading-absorption-check.sh` | 通过 |
| 定向 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh agent-reading-absorption-check` | 通过 |
| spec-check 传播回归 | `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures` | 通过 |
| 执行保障 | `bash compass/tools/redcap-execution-guarantee-check.sh` | 通过 |
| 文件查找字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| 历史资产 dry-run | `bash compass/tools/redcap-legacy-asset-migration-check.sh` | 通过 |
| 历史资产 apply preflight | `bash compass/tools/redcap-legacy-asset-migration-apply-plan.sh` | 通过 |
| package manifest | `bash compass/tools/redcap-runtime-package-manifest.sh --check` | 通过 |
| 发布前产品架构事实面 | `bash compass/tools/redcap-pre-release-product-architecture-check.sh` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-bind.sh --run-id 20260506-agent-reading-absorption-review` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [x] 当前无必须人工验证项；后续是否建设完整 Wiki/RAG/学习教练能力，需要另开产品/架构任务。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已清，7/7 完成 |
| 棱镜验收 | 通过，Kimi challenger + Claude Code reviewer，2 个模型家族，无 blocker |
| closeout summary | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/summaries/redcap-agent-reading-absorption-6e44be8e8d9d463fd1aa6cf8fa3a032050c0580f82a6e108d9ddd8d952265fa1.md` |
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-agent-reading-absorption-6e44be8e8d9d463fd1aa6cf8fa3a032050c0580f82a6e108d9ddd8d952265fa1.json` |
| rescue audit（如有） | 首次 closeout 因 drift scope 未登记历史资产连锁修复而 blocked；第二次因当前报告后置更新未列入 clean workspace E2E 安全漂移而 blocked。两项均已补齐并重跑通过。审计：`/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/audits/20260506T115708Z-redcap-agent-reading-absorption-6e44be8e8d9d463fd1aa6cf8fa3a032050c0580f82a6e108d9ddd8d952265fa1-on-complete-failed.json`；`/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/audits/20260506T120017Z-redcap-agent-reading-absorption-6e44be8e8d9d463fd1aa6cf8fa3a032050c0580f82a6e108d9ddd8d952265fa1-on-complete-failed.json` |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是，定向门禁已通过 |
| 已独立验收 | 是，Kimi + Claude Code 评审已归档 |
| 已正式完成 | 是，以上 closeout receipt 是正式完工凭证 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 完整 LLM Wiki / Schema root | 这会改变 RedCap 知识所有权模型，需要单独架构评审。 | P2 |
| RAG / GraphRAG / 向量库 | 当前已有检索升级阈值策略，未跨阈值前不应为了潮流启用。 | P3 |
| ai-professor-mode 学习教练能力 | 源文档只是短草稿，不适合未经清洗进入核心。 | P3 |
| P4-2h 真实公共蒸馏 | 本轮只做资料吸收，不生产公共条目。 | P1 |

### 6.2 触发的新问题

新增 `compass/knowledge/log.md` 后，历史资产治理清单和 package candidate 数量必须同步更新。本轮已经作为连锁修复处理，后续凡是新增长期知识面文件，都应同时检查旧资产治理和 package surface。

### 6.3 推荐的下一步行动

1. 继续 P4-2 主线，不要把本轮吸收误当成 P4-2h 真实公共蒸馏。
2. 若下一轮要推进公共知识内容，必须走 RedCap Forge 候选、脱敏、去重、安全审查和 append-only 输出。
3. 若要建设完整 LLM Wiki / RAG / 学习教练能力，应先让 Prism 做架构评审，而不是在当前任务中扩大范围。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| 无 | 本轮不直接写 lessons | 外部资料吸收已先落在 `compass/knowledge/log.md` 和机器策略中；是否转成 lesson 可由后续 Evolution/Forge 候选流程判断。 |

### 7.2 流程改进建议

外部行业资料进入 RedCap 时，不应该只写“我看过了”，也不应该全量照搬。更稳的做法是：先判定资料角色，再映射到现有记忆层，最后用 must-not-claim 和 checker 把延期边界锁住。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 外部资料吸收 | 本轮直接作为 P4-2h-1 已授权任务落地，不另建候选 | `references/agent-reading-absorption-policy.json` |

---

## 八、附录

### 附录 A：Commits

```
89dc9f7 feat(memory): 吸收 agent reading 长期记忆契约
bdea252 test(e2e): 刷新 agent reading 安装验收
da8062b docs(report): 收口 agent reading 完成报告
1b9ad85 test(e2e): 允许 agent reading 报告漂移
0d2fbd6 test(e2e): 刷新最终安装验收
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|----------|
| test | AI Era 导读资料是否应吸收到 RedCap 长期记忆设计 | 通过，但只能作为受控契约吸收，不启用完整 Wiki/RAG/公共直写 | `prism/reports/2026-05-06-agent-reading-absorption-review.md` |

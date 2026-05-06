# 任务完成报告：LLM-wiki-lite 语义记忆生命周期实现

**报告日期**：2026-05-06
**执行者**：Cap（Codex.app 主执行，Prism 使用 Kimi + Claude Code）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已有一个最小可用的私有 LLM-wiki-lite 生命周期，不再只是“以后可以做”的规划。
- 详情：本轮把 LLM-wiki-lite 固定为私有、非权威、必须带来源锚点的语义记忆层。每条 entry 都要能回到原始来源，并用 `sha256` 摘要判断是否过期；如果来源变了、来源不可读、候选类型越界、想直接写公共库或启用 RAG/GraphRAG，检查器会 fail closed。这样它可以帮助理解长期概念，但不会抢走 `.dev-task.md`、policy、receipt、Prism acceptance 等控制面真相源的位置。

### 0.2 上一步完成的是

- 上一步完成的是：`P4-2h-2` 完成了“哪些资产适合进入 LLM-wiki，哪些绝对不能进入”的分层评估，并登记了 `P4-2h-3`。

### 0.3 下一步计划做的是

- 下一步计划做的是：本轮收口后无同任务内下一刀；父任务线仍保持 `P4-2h` 公共蒸馏 deferred、`P4-2` 正式公开发布 blocked。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：外部资料吸收 → 资产分层 → 私有语义记忆最小生命周期 → 未来 RedCap Forge 公共蒸馏或正式 release 决策。
- 当前所在位置：`P4-2h-3` 已实现、已提交、已通过独立 Prism 复审与 closeout runtime receipt。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮不涉及 npm 发布、许可证选择、公共库真实写入、RAG/GraphRAG 启用或历史资产公开迁移，因此没有需要 Norven 保留决策的事项。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 了解，那我放心了。现在请你和棱镜继续稳步推进未完成的任务，完成时序和优先级由你们内部讨论评审和决策即可。

### 1.2 触发背景

`P4-2h-2` 只回答了“哪些资产可以作为未来 LLM-wiki-lite 的候选来源”，但还没有让 RedCap 真正拥有 entry schema、私有 store、过期检测和控制面接线。本轮由 Kimi + Claude Code 先做下一任务优先级评审，结论是先完成 `P4-2h-3`，因为它依赖已满足、边界清楚，而且能为后续长期记忆治理提供更安全的底座。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 在当前父任务线内继续推进未完成任务，并由 RedCap/Prism 自行决定优先级。 |
| 已覆盖 | 已完成 `P4-2h-3` 的最小私有 schema、entry store、source-anchor/staleness checker、继承式 allowlist/denylist、Forge public promotion boundary、spec/diagnose/acceptance/执行保障/文件字典接线和 Prism 实现复审。 |
| 未覆盖/延期 | 不覆盖完整 LLM-wiki 产品、后台自动生成、RAG、GraphRAG、向量库、公共 wiki 发布、公共 arsenal 实质内容迁移或正式 npm/public release。 |
| 用户可见边界 | 只能说“RedCap 有了私有 LLM-wiki-lite 最小生命周期和过期检测”；不能说“RedCap 已有完整 LLM-wiki/RAG 系统或公共知识库已填充”。 |
| 后续路径 | 若未来要公共化，必须另走 RedCap Forge 脱敏、去重、安全审查和 append-only 晋升；若要 RAG/GraphRAG，必须先过 retrieval escalation policy。 |

---

## 二、方案讨论

### 2.1 问题分析

本轮的核心风险不是“能不能写一个 wiki 文件夹”，而是 wiki 一旦被误当成真相源，就会污染 RedCap 的控制面。安全的做法是把 LLM-wiki-lite 做成“语义记忆缓存”：它可以解释概念、辅助检索和复盘，但必须从属于来源文件、控制策略、receipt 和 Prism verdict。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 只登记需求 | 继续把 LLM-wiki-lite 留在 planned 状态 | 风险低 | 无法验证长期记忆机制是否可用 |
| Q1 | 最小私有生命周期 | 实现 schema、index、entry、source digest 检查和控制面接线 | 价值可验证，边界可机器审计 | 仍不是完整 wiki 产品 |
| Q1 | 直接做完整 Wiki/RAG | 同时引入后台生成、语义检索和公共输出 | 愿景最大 | 范围失控，隐私和真相源风险太高 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 最小私有生命周期 | 它能把 `P4-2h-2` 的分层评估变成可运行门禁，又不会越界成完整 Wiki/RAG/公共写回。 | Prism + Cap |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `references/llm-wiki-lite-policy.json` | 新建 | 定义 LLM-wiki-lite 的私有、非权威、source-anchored、Forge-gated 生命周期边界。 |
| `references/llm-wiki-lite-entry.schema.json` | 新建 | 定义 entry 必填字段、私有 visibility、非权威 authority 和 source anchor 结构。 |
| `compass/knowledge/llm-wiki/README.md` | 新建 | 给人类和 Agent 的私有 store 使用说明。 |
| `compass/knowledge/llm-wiki/index.json` | 新建 | 元数据优先的 entry 索引。 |
| `compass/knowledge/llm-wiki/entries/llm-wiki-lite-boundary.json` | 新建 | 第一条边界型 seed entry，用来验证生命周期闭环。 |
| `compass/tools/redcap-llm-wiki-lite-check.py` / `.sh` | 新建 | fail-closed 检查器，验证 policy、schema、index、entry、source digest、候选类型、禁入路径、隐私和 Forge 边界。 |
| `compass/tools/redcap-spec-check.sh` | 修改 | umbrella validator 接入 LLM-wiki-lite gate。 |
| `compass/tools/redcap-diagnose.sh` | 修改 | 诊断面接入 LLM-wiki-lite gate。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 增加通过、stale digest、authority 越界、public write 越界和 spec-check 传播回归。 |
| `references/llm-wiki-asset-stratification-policy.json` | 修改 | 将 `P4-2h-3` 从 planned 更新为 completed-with-evidence，避免旧策略和新事实打架。 |
| `references/pre-release-structure-refactor-task-tree.json` | 修改 | 父任务树标记 `P4-2h-3` completed，并保留不得冒充完整 LLM-wiki/RAG/public release 的边界。 |
| `references/redcap-parent-task-ledger.md` | 修改 | 父任务状态面同步 `P4-2h-3` 已完成及不可声明范围。 |
| `references/execution-guarantees.json` | 修改 | 新增 LLM-wiki-lite 生命周期执行保障。 |
| `references/file-lookup-dictionary.md` / policy | 修改 | 文件字典收录新策略、schema、store 和检查器。 |
| `compass/knowledge/index.md` | 修改 | 把 LLM-wiki-lite store 纳入知识入口，但仍要求 metadata-first 读取。 |
| `compass/tools/redcap-legacy-asset-migration-check.py` / apply-plan.py | 修改 | 旧资产迁移计数不再把新建的 active LLM-wiki store 误判为历史知识淤积。 |
| `references/pre-release-product-architecture-review.json` | 修改 | 同步 npm pack candidate count。 |
| `prism/reports/2026-05-06-next-task-priority-review.md` | 新建 | 记录下一任务优先级评审。 |
| `prism/reports/2026-05-06-llm-wiki-lite-lifecycle-review.md` | 新建 | 记录 Kimi + Claude Code 实现复审。 |
| `prism/reports/index.yaml` | 修改 | 登记两份 Prism 报告。 |
| `redcap-knowledge/task-reports/2026-05-05-redcap-public-arsenal-claim-boundary.md` | 迁移 | 将一份旧报告移入私有冷归档，保持 active report inbox 不超过 12 份。 |

### 3.2 技术实现要点

本轮把 LLM-wiki-lite 拆成三个可审计层次：策略层决定什么能进、schema 层决定 entry 长什么样、checker 层决定是否能通过控制面。这样即使未来出现更多条目，RedCap 也不需要靠 Agent 记忆来判断边界，而是由脚本按同一套规则审。

source anchor 是本轮最关键的约束。每条 entry 必须写明来源路径、来源类型、`sha256` 摘要、最后复核时间和隐私级别；checker 会重新计算当前文件摘要，摘要不一致就判定 entry stale。这让语义记忆“可用但不独裁”：它可以解释，但不能脱离来源自说自话。

另一个关键点是公共晋升边界。LLM-wiki-lite 自己不能写 `redcap-arsenal`、shared knowledge 或公共 wiki；未来任何公共化都必须交给 RedCap Forge 做脱敏、去重、安全审查和 append-only 晋升。本轮只把这个边界接进机器检查，不做公共导出。

执行中还发现一个联动问题：新建 `compass/knowledge/llm-wiki/` 会被旧资产迁移检查误当成历史 `compass/knowledge` 淤积。修复后，新 store 被识别为 active store，不参与历史资产迁移计数；旧资产迁移检查仍继续覆盖原有历史材料。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| LLM-wiki-lite | `compass/knowledge/llm-wiki/` | 一个私有语义记忆缓存，帮助理解稳定概念，但不是任务真相源。 |
| source anchor | entry 的 `source_anchors` 字段 | 每条记忆必须指向原始来源，方便过期检测和考古。 |
| staleness checker | `redcap-llm-wiki-lite-check.py` | 判断 entry 是否因为来源变化、digest 不一致、隐私或边界错误而失效。 |
| Forge promotion | `forge_promotion` 字段 | 表示 entry 未来如果要公开，必须先过 RedCap Forge，不能直接写公共库。 |
| candidate allow/deny | `llm-wiki-asset-stratification-policy.json` | 继承上一轮资产分层结果，决定哪些类型的内容可以变成私有语义记忆。 |
| active store | `compass/knowledge/llm-wiki/` | 当前运行需要的私有 store，不是历史资产迁移对象。 |

### 3.3 关联变更

旧资产迁移检查器被同步调整，是因为新 LLM-wiki store 出现在 `compass/knowledge` 下，但它不是老的 `lessons` 或历史材料；如果不区分，会导致 spec-check 被新增的正常运行资产误炸。

报告归档也被同步处理：本轮新报告写入 active inbox 后，active report 数量超过信息架构上限，因此将一份旧报告迁入 `redcap-knowledge/task-reports/` 私有冷归档。这样新任务仍从 active inbox 暴露，旧任务继续可考古，但不会让当前报告入口无限增长。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无必须人工审核项 | 本轮没有公共发布、许可证、账号凭据、公共内容迁移或 RAG/GraphRAG 启用决策。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| LLM-wiki-lite checker | `bash compass/tools/redcap-llm-wiki-lite-check.sh` | 通过 |
| LLM-wiki-lite acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh llm-wiki-lite-lifecycle-check` | 通过 |
| Asset stratification acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh llm-wiki-asset-stratification-check` | 通过 |
| spec-check gate propagation | `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures` | 通过 |
| file lookup dictionary | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| execution guarantees | `bash compass/tools/redcap-execution-guarantee-check.sh` | 通过 |
| pre-release structure task tree | `bash compass/tools/redcap-pre-release-structure-task-tree-check.sh` | 通过 |
| legacy migration dry-run | `bash compass/tools/redcap-legacy-asset-migration-check.sh` | 通过 |
| legacy migration apply preflight | `bash compass/tools/redcap-legacy-asset-migration-apply-plan.sh` | 通过 |
| umbrella spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |
| full acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过 |
| clean workspace E2E | `bash compass/tools/redcap-clean-workspace-e2e.sh --write-result --check-result` | 通过 |
| Prism evidence | `bash prism/tools/prism-evidence-check.sh` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已核对：7/7 完成，0 pending |
| 棱镜验收 | 已通过：`20260506-llm-wiki-lite-lifecycle-review` |
| closeout summary | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/summaries/redcap-llm-wiki-lite-lifecycle-75e709777559593d2b4a82d0301b62f1a0cf98edbc1ab18548deb478d666aad6.md` |
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-llm-wiki-lite-lifecycle-75e709777559593d2b4a82d0301b62f1a0cf98edbc1ab18548deb478d666aad6.json` |
| rescue audit（如有） | 曾因未提交与 drift 范围登记不完整 blocked；已补边界、提交、刷新 clean workspace E2E 并重新 closeout 通过。 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Kimi + Claude Code 无 blocking finding |
| 已正式完成 | 是，closeout runtime receipt 已生成 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 完整 LLM-wiki 产品、后台自动生成、RAG/GraphRAG、向量库 | 明确超出本轮最小私有生命周期范围，且需要单独架构评审和隐私/检索升级门禁。 | P2 |
| 公共 redcap-arsenal 实质内容迁移 | 必须走 RedCap Forge，且本轮没有执行公共蒸馏。 | P1 |
| 正式 npm/public release | 仍是单独 release task，涉及发布目标、许可证、凭据和人工边界。 | P2 |

### 6.2 触发的新问题

Prism 提醒未来可以考虑把 `llm-wiki-lite-lifecycle` 从 `lessons-knowledge` 进一步细分到“semantic-memory / knowledge-governance”类别。本轮不新增该 taxonomy 任务，因为当前分类已可检查且不会影响功能正确性。

### 6.3 推荐的下一步行动

1. 保持 `P4-2h` 公共蒸馏 deferred，等需要真实公共知识条目时再由 RedCap Forge 立项。
2. 正式 release 前仍需单独进入 release readiness，而不是把本轮完成冒充为发布完成。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-candidate | 新 store 不应被旧资产迁移计数误伤 | 在治理历史资产时，要区分“历史淤积”和“新机制运行资产”，否则新增正确能力也会触发旧计数误报。 |

### 7.2 流程改进建议

未来若继续建设 semantic memory，可以考虑给执行保障 registry 增加更明确的 semantic-memory 分类，但不应在本轮为分类洁癖扩大工程范围。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | Prism notes / 回归发现 | no-promote：本轮问题已在任务内修复或记录为非阻塞 taxonomy 建议，不需要新增候选池条目 | `prism/reports/2026-05-06-llm-wiki-lite-lifecycle-review.md` |

---

## 八、附录

### 附录 A：Commits

```
f8b8228 feat: 实现 LLM-wiki-lite 生命周期
778624b test: 刷新 clean workspace E2E 证据
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| test | 下一步应该推进哪个父任务子项 | 选择 `P4-2h-3`，不启动发布或公共蒸馏 | `prism/reports/2026-05-06-next-task-priority-review.md` |
| test | LLM-wiki-lite 实现是否越界或缺口 | Kimi pass_with_notes、Claude Code pass，无 blocking finding | `prism/reports/2026-05-06-llm-wiki-lite-lifecycle-review.md` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 私有语义记忆策略：`references/llm-wiki-lite-policy.json`
- 私有语义记忆入口：`compass/knowledge/llm-wiki/index.json`
- 实现复审：`prism/reports/2026-05-06-llm-wiki-lite-lifecycle-review.md`

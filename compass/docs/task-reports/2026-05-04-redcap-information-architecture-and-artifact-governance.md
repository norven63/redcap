# 任务完成报告：RedCap 信息架构与运行时产物治理

**报告日期**：2026-05-04
**执行者**：Cap（Codex + Prism: Kimi, Claude Code）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 现在把任务报告、私有知识、运行时证据、公共模板、外部 arsenal 和 RedCap Forge 的职责边界正式分清，并接入了机器门禁与棱镜复审。
- 详情：本轮解决的是“报告和知识文档越积越散、用户很难判断哪些该读、哪些可公开、哪些只是运行痕迹”的信息架构问题。新的治理规则先定义每类资产的生命周期和出口边界，再让检查器阻断报告 inbox 膨胀、私有材料误进公共库、Forge/Arsenal 命名混淆和 P4 顺序误读。最终效果是：RedCap 可以继续保留考古与追踪能力，但默认不会把旧报告、身份信息、运行证据或私有知识直接推向公共沉淀库。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2a 发布前产品架构审判确认 RedCap 不能只靠 npm pack 证明自己适合发布，随后用户进一步指出报告、知识、运行时产物和公共知识库之间的边界已经变成发布前的前置隐患。

### 0.3 下一步计划做的是

- 下一步计划做的是：本轮信息架构治理已完成；如果继续 public CLI/runtime 主线，下一步应回到 P4-2b/P4-2c/P4-2d 这类发布前整改，而不是直接 npm publish。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-2a 产品架构审判 → P4-2f 信息架构与运行时产物治理 → P4-2b/c/d 发布前整改 → release readiness → npm publish。
- 当前所在位置：P4-2f 已完成实现与棱镜验收，父任务仍处在 public release 之前的整改阶段。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 借助这次任务完成的报告，有几个问题想讨论一下：
> 1. 目前每次任务完成都有一个报告存到本地，这个是redcap的某个门禁能力，还是当前Agent宿主的能力？
> 2. 我看report的存放路径很分散，有在/Users/norven/.claude/skills/redcap/compass/docs/task-reports/ 下的，也有在/Users/norven/.claude/skills/redcap/redcap-knowledge/ 下的，这个是刻意而为之的区分存放吗？如果是的话，用意是什么？另外，不觉得这样存放的方式很分散、不易于维护吗？
> 3. 你每次中断后的汇报，是否可以基于“概述这些report”为目的来写呢？并且注意人类可读（我发现“人类可读”已经三令五申很多次了，但最终都没生效），像你刚才那些类似“接入 diagnose / spec-check / acceptance / parent ledger / execution guarantees / file lookup dictionary”、“缺 npm PATH 的 hook 环境误炸、spec-check fixture 漏接新 gate、stop-review 内部审计失败默认刷飞书”等等描述，都充斥着大量的工程命名术语名词（特别是redcap自身的工程设计命名），阅读起来很吃力。我记得不是有一个对照表吗？如果你实在认为汇报的时候追加太多解释太过冗余，那是否至少可以把各个专有术语名词的解释链接附带到汇报中？另外，还有一个很大的问题隐患，我在工作报告文件reeport.md中看到了需要人工介入的点，而你的中途汇报中却丝毫没有提到，这可能会导致我忽略了你需要我协助的请求
> 4. P4-3 clean workspace E2E是在之前的节点（虽然它的编号数字是3，比后面正在进行和即将进行的2要大），但是它已经执行完毕了吗？我好像没印象咱们已经做过这个了吧？并且，如果这个问题缺失存在，那么是否会引发另一个更底层的问题：即redcap的工作流是否有发生错乱的隐患？
> 5. 基于上述问题，其实除了一方面要回答和解决具体case外，我更想发起一个和你对redcap当前工作流的整体审视和review：当前redcap的目录结构定义合理和科学吗？不仅仅是说要为了发布CLI做准备考虑，还要从一个健康完善且符合工程科学目录划分规范哲学的角度考虑。工程目录应该具备简洁化、模块化、语义化，而不是散乱、无章法可循的现象。尤其是我发现还有很多的是运行时产物（即开发工程时的产物，本次是开发redcap自身这个工程而生成的产物）
> 6. 基于第5点+第2点两个问题综合考虑，目前运行时产物已经（不是有隐患，而是“已经”）呈现出了膨胀坏味，并且大量产物文档归类于knowledge、doc两个大类（只能说2个大类，不能说是两个目录，因为这个大类同名目录多个，且不在同一个路径下），除了冗余之外，就是对于redcap-arsenal的收敛和蒸馏是怎样的一个关系？这个目前有相信设计过吗？或者说之前有过讨论吗？如果什么都没有的话，是否有必要单独拎出来做一个需求评审并严格落地呢？因为这个问题如果不解决，我理解CLI的节点是缺失前序节点的，对吧？

> 好的，可以，以上所有你说的我都赞同，而且批准你在你认为合适的时机执行对应的任务。
>
> 另外，我想确认一个点，你上述的工作会涉及到Evolution Factory、redcap-arsenal一起联动和开发吧？并且，我觉得既然公共知识库叫arsenal，那负责执行蒸馏、去重、安全审查的“Evolution Factory”是否也可以起一个和它对应统一的名字呢？比如也叫arsenal creator，或者叫军火商之类的？你对此有什么建议吗？或者还是说，你认为无需改名字，当前Evolution Factory足够用了。

> 好的，你建议我都认可，并且正式启用RedCap Forge 这个命名。那么，可以开始继续推进任务了吗？你可以和棱镜按需自由的分配和设计“RedCap 信息架构与运行时产物治理”执行优先级与切割任务点，这是你们的“工程推进”

### 1.2 触发背景

这次任务不是简单回答“报告为什么分散”，而是把 RedCap 发布前暴露出的信息架构坏味正式治理掉。用户指出 report、knowledge、runtime artifact、shared knowledge 和 arsenal 的边界既影响可维护性，也影响 token 风险、隐私安全和未来 CLI/runtime 产品形态，因此本轮必须进入工程实现，而不是只给解释。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 正式治理 RedCap 的信息架构、运行时产物、报告生命周期、公共知识库蒸馏链路和 CLI 发布前目录健康边界。 |
| 已覆盖 | 已覆盖报告机制边界、目录角色分类、RedCap Forge 命名和职责、redcap-arsenal 入口边界、人类可读汇报派生规则、P4-3 顺序语义、机器检查、执行保障登记与 Prism 验收。 |
| 未覆盖/延期 | 未执行 npm publish；未批量迁移所有历史私有知识到公共库；未启用 GraphRAG 或向量库；未删除历史资产大规模内容。 |
| 用户可见边界 | 可以声明“信息架构和产物治理规则/门禁已落地”；不能声明公共 arsenal 已有实质知识内容，也不能声明 RedCap 已 public release ready。 |
| 后续路径 | 回到 P4-2b/P4-2c/P4-2d 等发布前整改；RedCap Forge 后续可在单独任务中处理真实公共候选生产。 |

---

## 二、方案讨论

### 2.1 问题分析

用户的问题表面上是 report 放在哪、为什么路径分散、汇报为什么难读；底层问题是 RedCap 已经从一个 skill 现场演化为更像 agent runtime 的系统，却还没有把“执行层、私有知识层、运行证据层、公共沉淀层、人类阅读层”分成清晰边界。若继续让所有材料混在 docs/knowledge 口径里，后续 Agent 会为了考古而过度读取历史内容，公共库也可能误收私有报告或身份信息。

本轮因此采用“先定义边界，再治理目录”的做法。RedCap Forge 的命名也在这个逻辑下成立：Evolution Factory 是自进化总系统，Forge 是实际锻造流水线，redcap-arsenal 是成品公共库；三者不能再混成一个模糊概念。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1-Q2 | 只解释现有路径 | 保留现状，用报告说明哪些路径是什么 | 成本低 | 仍靠口头约定，后续会继续分叉 |
| Q1-Q6 | 建立信息架构 policy 和检查器 | 给各类产物定义生命周期、可见性、出口边界，并接入门禁 | 能机器化阻断分裂和误公开 | 需要新增治理面并维护 |
| Forge 命名 | 改名为 arsenal creator | 与 arsenal 呼应 | 容易让人误以为只服务公共库 |
| Forge 命名 | 启用 RedCap Forge | 表达“锻造流水线”，可覆盖脱敏、去重、安全审查、索引和候选生产 | 需要明确它隶属于 Evolution Factory，而不是替代总系统 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1-Q6 | 建立信息架构 policy、Forge policy 与机器检查链 | 这能把目录边界从解释变成可审计契约，也能服务未来 CLI/runtime 发布前治理。 | NORVEN_DECIDE + CAP_IMPLEMENT |
| Forge 命名 | 正式启用 RedCap Forge | 用户明确批准该命名；它比 arsenal creator 更准确，因为 Forge 不只是写公共库，还负责脱敏、去重、结构化、索引和安全审查。 | NORVEN_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 新建 P4-2f 当前任务卡，锁定原始需求、完成标准、漂移哨兵和 Prism 验收要求。 |
| `references/information-architecture-artifact-governance-policy.json` | 新建 | 定义当前任务报告、私有归档、活动知识、运行证据、公共模板和外部 arsenal 的根分类、生命周期和出口规则。 |
| `compass/tools/redcap-information-architecture-check.py` / `.sh` | 新建 | 校验信息架构 policy、report inbox 上限、私有/公共出口边界、P4 编号语义和跨 policy 一致性。 |
| `references/redcap-forge-policy.json` | 新建 | 定义 Evolution Factory、RedCap Forge、redcap-arsenal 三者关系，以及 Forge 公共候选生产的安全门。 |
| `compass/tools/redcap-forge-check.py` / `.sh` | 新建 | 校验 Forge 命名、职责、禁止原始私有材料进入公共库、公共候选门禁和文档交叉引用。 |
| `references/human-communication-policy.json` / `compass/tools/redcap-human-communication-check.py` | 修改 | 要求最终或中断汇报优先概述报告 0.1-0.4，并显式提示人工审核/验证项。 |
| `references/execution-guarantees.json` / `compass/tools/redcap-execution-guarantee-check.py` | 修改 | 把信息架构、RedCap Forge、report-led 人类汇报边界登记进执行保障体系。 |
| `references/shared-knowledge-policy.json` / `references/shared-knowledge-remote-binding.json` | 修改 | 明确 shared-knowledge 只承载模板/候选，公共库内容必须先过 RedCap Forge，私有路径禁止外推。 |
| `references/legacy-asset-lifecycle.json` | 修改 | 把私有报告归档、shared-knowledge 模板、Forge policy、信息架构 policy 纳入资产生命周期。 |
| `references/redcap-parent-task-ledger.md` | 修改 | 说明 P4 编号是依赖/状态图，不是严格时间顺序；补 P4-2f 当前状态。 |
| `references/file-lookup-dictionary.md` / `references/file-lookup-dictionary-policy.json` | 修改 | 增加信息架构和 RedCap Forge 入口，帮助后续 Agent 渐进式定位而不是全文考古。 |
| `README.md` / `ARCHITECTURE.md` / `references/runtime-memory-architecture.md` | 修改 | 用人类可读方式说明 RedCap Forge、private archive、public arsenal 和 runtime evidence 的关系。 |
| `compass/evolution/README.md` / `shared-knowledge/README.md` | 修改 | 说明 Evolution Factory 是总系统，RedCap Forge 是执行流水线，redcap-arsenal 是通过审查后的公共成品库。 |
| `compass/tools/redcap-diagnose.sh` / `compass/tools/redcap-spec-check.sh` / `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 将新门禁接入诊断、总体验证和 targeted acceptance。 |
| `compass/knowledge/lessons.md` / `compass/evolution/candidates.json` | 修改 | 沉淀本轮“先定义边界，再治理目录”的经验。 |
| `prism/runs/20260504-redcap-information-architecture-governance/**` | 新建 | 保存 Kimi 与 Claude Code 的独立复审、解析结果和 acceptance binding。 |

### 3.2 技术实现要点

这次最重要的技术选择，是把目录治理从“文件夹搬家”提升为“资产生命周期治理”。报告文件不是宿主自动生成的副产品，而是 RedCap 的任务结案证据；receipt 是机器正式完工凭证；Prism runs 是运行时证据；私有知识归档不能直接变成公共知识库内容。

RedCap Forge 被设计为 Evolution Factory 内部的锻造流水线：它把私有对话、报告、经验和候选材料经过脱敏、去重、结构化、索引和安全审查，才允许成为 redcap-arsenal 的公共候选。这样可以避免把“公共库为空”误说成“公共沉淀已完成”，也避免把“共享模板目录”误当成可发布知识库。

人类汇报规则也被收进本轮治理：终态或中断汇报应先概述任务报告里的“当前已完成、上一步、下一步、当前位置”，再谈内部实现细节。棱镜指出这个规则属于 live reply 的宿主边界，不能诚实宣称 100% 物理强制；因此本轮把它登记为执行保障里的 manual-only 边界，同时让报告和 policy 检查器保障源材料存在。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| task report | `compass/docs/task-reports/*.md` | 给人看的任务结案报告，说明本轮做了什么、为什么做、验证了什么、还有什么边界。 |
| receipt | closeout runtime receipt | 给机器看的正式完成凭证；只有 receipt 生成后，任务才算正式 completed。 |
| private archive | `redcap-knowledge/**` | 私有历史归档区，用于考古和追踪，不是默认注入上下文，也不能直接公开。 |
| runtime evidence | `prism/runs/**`、`/tmp/redcap/**` | 执行过程证据，帮助验证和审计，但不是产品文档，也不应进入 git 主体或公共库。 |
| shared-knowledge template | `shared-knowledge/**` | 公共知识库的模板源和安全结构，不代表已经有实质公共知识内容。 |
| redcap-arsenal | 外部公共库 | 通过 RedCap Forge 审查后沉淀的公共能力库/知识库/skill 候选仓库。 |
| RedCap Forge | `references/redcap-forge-policy.json` | Evolution Factory 里面负责脱敏、去重、安全审查、索引和候选产出的“锻造流水线”。 |
| Evolution Factory | `compass/evolution/README.md` | RedCap 的自进化总系统，Forge 是其中的执行管线，不是同义词。 |
| P4 编号 | `references/redcap-parent-task-ledger.md` | 父任务分解编号，表示依赖和状态，不表示严格时间顺序。 |

### 3.3 关联变更

棱镜复审后，Claude Code 提出两个非阻塞但有价值的修正：第一，人类可读汇报规则需要在执行保障中诚实标注为宿主边界；第二，report inbox 超限失败时应该提示归档路径和生命周期流程。本轮已经同时补入，避免把 review 只当备案。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 当前无必须人工介入项 | 本轮 P4-2f 可以由 Cap 和 Prism 完成收口；是否继续 public release 后续整改属于下一阶段战略选择，不阻塞本轮。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 信息架构门禁 | `bash compass/tools/redcap-information-architecture-check.sh` | 通过 |
| RedCap Forge 门禁 | `bash compass/tools/redcap-forge-check.sh` | 通过 |
| 人类汇报策略 | `bash compass/tools/redcap-human-communication-check.sh` | 通过 |
| 文件查找字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| 历史资产生命周期 | `bash compass/tools/redcap-legacy-asset-lifecycle-check.sh` | 通过 |
| 执行保障登记 | `bash compass/tools/redcap-execution-guarantee-check.sh` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh information-architecture-check` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh redcap-forge-check` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh shared-knowledge-remote-binding-check` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过，Kimi + Claude Code |
| 总体验证 | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [x] 当前无必须人工验证项；后续是否推进真实 public release 整改，不属于本轮完成条件。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已清，7/7 完成 |
| 棱镜验收 | 通过，Kimi reviewer + Claude Code challenger，2 个模型家族，无 blocker |
| closeout summary | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/summaries/redcap-information-architecture-and-artifact-governance-2a5b7808cea57a0761d4aa3a120ef55413ce16a7eb4aa034278b785e95ab403b.md` |
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-information-architecture-and-artifact-governance-2a5b7808cea57a0761d4aa3a120ef55413ce16a7eb4aa034278b785e95ab403b.json` |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是，信息架构、Forge、汇报边界和机器检查已实现 |
| 已自检 | 是，targeted checks 与 spec-check 已通过 |
| 已独立验收 | 是，Prism acceptance 已通过 |
| 已正式完成 | 是，以 5.3 中 closeout receipt 为正式凭证 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 真实 npm publish | 用户已明确要求先完成主线开发，发布是最后一步；本轮只治理发布前信息架构。 | P0-before-public-release |
| 真实批量迁移私有知识到 redcap-arsenal | 这需要 RedCap Forge 逐条脱敏、去重、审查和索引，不应在目录治理任务里批量搬运。 | P1 |
| GraphRAG 或向量库 | 当前规模仍应使用 catalog + rg + metadata；是否升级需由检索阈值策略触发。 | P2 |

### 6.2 触发的新问题

本轮确认：报告和公共沉淀之间不能再靠“knowledge/doc”粗分类维持，需要显式区分私有归档、公共模板和公共成品库。该问题已通过信息架构 policy 与 RedCap Forge policy 收口。

棱镜还提醒：live reply 的人类可读质量不能被仓库脚本 100% 物理强制，所以必须诚实标成 host-limited/manual-only，并用报告模板与执行保障登记降低遗漏概率。本轮已按这个建议修正。

### 6.3 推荐的下一步行动

1. 回到 P4-2b/P4-2c/P4-2d，继续处理 public release 前的 runtime/project/user boundary、CLI 产品面和 package 身份/license。
2. 后续任何要进入 redcap-arsenal 的内容，都先走 RedCap Forge，不能直接搬运本轮 report 或私有归档。
3. 若 active report inbox 接近上限，另开历史报告归档任务，不要在当前任务里随手搬文件。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-150 | 信息架构治理要先定义边界，再谈目录清理 | 报告、私有知识、运行证据、公共模板和公共库必须先按生命周期和出口边界建模，再决定如何归档、蒸馏或发布。 |

### 7.2 流程改进建议

今后处理目录膨胀、token 风险、公共知识库和 CLI 发布准备时，应优先问“这份资产属于哪个生命周期、是否允许公开、谁会读取、是否需要 Forge 处理”，而不是直接讨论文件搬迁。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| EVO-2026-05-04-002 | 用户对 report/knowledge/runtime/arsenal 边界的系统性质疑 + Prism 非阻塞建议 | promoted | `compass/knowledge/lessons.md` |

---

## 八、附录

### 附录 A：Commits

```
本报告生成时尚未提交；最终提交见本任务 closeout 后的 git log。
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| test | Kimi 信息架构复核 | pass，无 blocker | `prism/runs/20260504-redcap-information-architecture-governance/collect/kimi-review/parsed.json` |
| test | Claude Code 挑战式审查 | pass-with-fix，无 blocker；2 个非阻塞建议已处理，1 个未来优化保留 | `prism/runs/20260504-redcap-information-architecture-governance/collect/claude-challenge/parsed.json` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 信息架构策略：`references/information-architecture-artifact-governance-policy.json`
- RedCap Forge 策略：`references/redcap-forge-policy.json`
- 执行保障登记：`references/execution-guarantees.json`
- 父任务账本：`references/redcap-parent-task-ledger.md`

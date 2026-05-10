# 任务完成报告：RedCap 中途架构与任务树一致性审计

**报告日期**：2026-05-07  
**执行者**：Cap（Codex.app 主执行，Prism 使用 Claude Code；Kimi 复审 90 秒超时）  
**报告版本**：v1.2

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：本轮把“脚本头中文短说明、LLM-wiki-lite 边界、中途任务树对账”从口头讨论升级成了机器可查的治理闭环。
- 详情：关键脚本现在不只依赖字典条目，也必须在文件头有一句短中文用途说明和 `Dictionary:` 反链，方便人类检索时快速判断文件作用。`LLM-wiki-lite` 被明确固定为私有、非权威、带来源锚点的最小语义记忆层；完整 LLM-wiki、后台生成、RAG/GraphRAG、向量库和公共写回仍是未来任务，不能被当前完成态冒充。中途审计产物会横向对齐已完成、近期中插、尚未完成、deferred 和 blocked-external 的任务边界。

### 0.2 上一步完成的是

- 上一步完成的是：`P2-6 Copilot protected fallback` 已有 closeout receipt，父账本也已记录完成。
- 本轮不是继续 public release，也不是把历史知识写入 redcap-arsenal，而是处理你指出的治理缺口：脚本头不清晰、LLM-wiki-lite 边界可见性不足、结构调整前缺少一次全景复核。

### 0.3 下一步计划做的是

- 下一步计划做的是：无自动可继续推进的发布主线任务。`P4-2` 正式 public release 仍 blocked-external；`P4-2h` 历史资产公共蒸馏仍 deferred。若后续继续，应另开明确 release / public distillation / full LLM-wiki 任务。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：父任务迁移与发布准备 → 用户发现治理缺口 → 立项 `P2-7` → 文件头规则机器化 → LLM-wiki 边界显性化 → 中途审计 → Prism 复核 → closeout。
- 当前所在位置：`P2-7` 已实现、已自检、已完成 Prism resource-limited 复核、通过 full acceptance，并已由 closeout runtime 生成最终 receipt。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮不涉及 npm 发布、许可证、凭据、公共知识库写入、历史资产删除或是否启用完整 LLM-wiki 的保留决策。下一步只有在你明确授权 public release、公共蒸馏或完整 LLM-wiki 产品化时，才需要重新进入人工决策。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 1. 现在脚本的文件头似乎没有"中文的注释”来说明这个脚本是干嘛的，这个记得说是要做的吧？方便人在检索的时候快速理解该文件的作用  
> 2. 目前llm-wiki-lite的定位是什么？它是临时协助redcap推进任务的工具吗，并且会等到其他任务推进差不多的时候，再把llm-wiki-lite做成完整的产物吗（但是我似乎没有看到你把完整的llm-wiki实现写进本次报告的“遗留问题与下一步”小节里，并且之前我问过你是否有把llm-wiki的完整技术实现要点写入需求中，你的回答是“有，且分了三层”,现在是矛盾了吗？因为我没看到报告中有写到）？如果是的话，那它的“临时性”会有风险隐患吗？需要在它工作的过程中，为它添加多处审核守卫，以防止风险的发生吗？  
> 3. 项目推进到现在，已经有很多的目录结构性的调整动作，以及后续还有多个大型调整，这些都时刻会有审核动作协同跟进吗？或者说，你和棱镜现在是否需要停一下，基于“历史已经完成的需求、近期中途新加的需求、尚未完成的计划中需求、整体任务需求树”这几个维度，做一个中途整体的check和review呢？
>
> 好的，结合上述讨论，现在请你和棱镜继续稳步推进未完成的任务、计划新增的任务，这些任务的完成时序和优先级由你们内部讨论评审和决策即可

### 1.2 触发背景

这次问题暴露的不是某一个脚本缺注释，而是“治理承诺有了，但执行不一致”。文件解释原本设计成“字典集中解释 + 文件头短反链”，但很多关键脚本没有短中文说明，也没有被机器检查。LLM-wiki-lite 的技术边界虽然在专门报告里写过，但父任务视图不够显性，容易让人误以为完整 LLM-wiki 已经进入当前完成范围。再加上近期目录结构和运行时产物治理动作较多，继续推进前需要一次横向对账。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 继续推进未完成与计划新增任务，并补齐文件头、LLM-wiki-lite 定位、中途总审计的工程闭环。 |
| 已覆盖 | 文件头短中文用途 + 字典反链规则已机器化；已登记并验证中途审计 JSON；父账本和任务树显性保留 full LLM-wiki / RAG / GraphRAG / 向量库 / 后台生成的 deferred 边界；已用 Prism 做 resource-limited 复核。 |
| 未覆盖/延期 | 不实现完整 LLM-wiki 产品；不启用 RAG/GraphRAG/向量库；不 public publish；不迁移历史私有知识到 redcap-arsenal；不删除历史资产。 |
| 用户可见边界 | 不能宣称 RedCap 已 public-release-ready；不能宣称 LLM-wiki-lite 等于完整 LLM-wiki；不能宣称公共 arsenal 已有实质历史知识内容。 |
| 后续路径 | 若要继续，需要单独立项 public release、P4-2h 公共蒸馏，或 full LLM-wiki 产品化。 |

---

## 二、方案讨论

### 2.1 问题分析

Q1 的核心不是“注释要不要中文”，而是人类查文件时需要快速知道脚本用途，同时又不能把每个文件头写成大段说明制造 token 污染。因此正确做法是短中文用途 + 字典反链，详细解释仍集中到 File Lookup Dictionary。

Q2 的核心是“最小生命周期”和“完整产品”不能混账。LLM-wiki-lite 是可工作的最小私有语义记忆层，但它不是完整 LLM-wiki，也不负责后台自动蒸馏、RAG、GraphRAG、向量库或公共库写回。

Q3 的核心是结构性重构已经进入深水区，需要在继续动目录或发布路径前做一次横向对账，避免旧任务已完成、新需求插入、deferred 项、blocked 项在不同文档里各说各话。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|---|---|---|---|
| Q1 | 只补注释 | 给脚本加中文文件头，不改检查器 | 快 | 仍靠人记，后续还会漏 |
| Q1 | 字典 + 文件头强门 | 字典解释职责，文件头放短中文用途和反链，由 checker 检查 | 可持续、低 token、可机器验收 | 需要补一次历史关键脚本 |
| Q2 | 把 LLM-wiki-lite 当临时工具 | 后续再整体重做 | 简单 | 容易让临时层污染真相源 |
| Q2 | 固定为最小私有语义记忆层 | 明确非权威、source anchor、过期检测和 Forge 晋升边界 | 边界清楚，能长期安全运行 | 完整 LLM-wiki 仍需另开任务 |
| Q3 | 继续主线不审计 | 直接推进后续任务 | 表面速度快 | 高风险，容易再次任务漂移 |
| Q3 | 做中途总审计 | 横向核对完成/中插/计划/deferred/blocked | 降低漂移风险 | 多一个治理产物 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---|---|---|
| Q1 | 字典 + 文件头强门 | 符合“渐进式披露”：短头帮人定位，长解释集中在字典，机器负责防漏。 | CAP_DECIDE |
| Q2 | LLM-wiki-lite 固定为最小私有语义记忆层 | 它不是临时草稿，但也不是完整产品；必须靠边界守卫长期运行。 | CAP_DECIDE |
| Q3 | 中途总审计 | 结构调整继续前需要全景对账，避免任务漂移和报告口径误导。 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|---|---|---|
| `.dev-task.md` | 修改 | 将本轮任务正式立项为 `P2-7`，锁定文件头、LLM-wiki、任务树中途审计三类需求。 |
| `references/file-lookup-dictionary-policy.json` | 修改 | 增加 `script_header_policy`，要求关键脚本文件头有中文用途和 `Dictionary:` 反链。 |
| `compass/tools/redcap-file-lookup-dictionary-check.py` | 修改 | 增加脚本头检查，并收紧 `用途：/作用：` 必须出现在注释行开头附近。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 增加文件头检查回归，覆盖 `.sh`、`.py` 和无后缀 CLI 入口。 |
| `compass/tools/redcap-on-stop-review.sh` | 修改 | 修复 full acceptance 暴露的空 reviewer 候选数组问题，并保留 prompt-only reviewer 被跳过时的 `insufficient-evidence` 证据。 |
| `references/midcourse-architecture-task-tree-review.json` | 新建 | 记录本轮中途架构审计七个维度和三个 deferred/blocked 边界。 |
| `compass/tools/redcap-midcourse-architecture-check.sh` / `.py` | 新建 | 校验中途审计产物的维度、证据、延期边界和 must-not-claim。 |
| `compass/tools/redcap-spec-check.sh` | 修改 | 将中途审计检查接入全局 spec-check。 |
| `references/redcap-parent-task-ledger.md` | 修改 | 登记 `P2-7`，并显性列出 full LLM-wiki / RAG / GraphRAG 的 deferred future 边界。 |
| `references/pre-release-structure-refactor-task-tree.json` | 修改 | 增加 `P4-2h-full-llm-wiki` deferred 节点，避免把 LLM-wiki-lite 冒充完整产品。 |
| `references/pre-release-product-architecture-review.json` | 修改 | 同步新增治理文件后的 npm pack candidate count。 |
| `references/execution-guarantees.json` / checker | 修改 | 把文件头治理和中途审计登记为执行保障能力。 |
| `references/file-lookup-dictionary.md` | 修改 | 增加中途审计相关文件的人类定位条目。 |
| `compass/tools/**` / `prism/tools/**` / `bin/redcap` | 修改 | 为字典登记的关键脚本补短中文用途和 `Dictionary:` 反链。 |
| `prism/reports/2026-05-07-midcourse-architecture-task-tree-review.md` | 新建 | 归档本轮 Prism resource-limited 复核结论。 |

### 3.2 技术实现要点

文件头治理现在不再靠“我记得应该补”。`redcap-file-lookup-dictionary-check` 会读取字典 policy，凡是被登记为关键脚本的路径，都要在文件头前若干行出现短中文用途和 `Dictionary:`。详细解释仍在字典里，所以不会让每个脚本变成小型说明书。

中途审计不是又新写一篇长报告，而是一份机器可校验的状态对账表。它要求覆盖已完成需求、近期中插需求、计划中开放项、文件头治理、LLM-wiki-lite 边界、运行时产物与目录治理、Prism provider 策略。这样后续如果某一层缺证据，spec-check 会失败。

LLM-wiki-lite 的位置被固定为“私有语义记忆层”。它可以帮助 RedCap 长期理解稳定概念和设计决策，但不能接管任务真相源、不能写公共库、不能代表完整 LLM-wiki，也不能绕过 Forge 的公共晋升审查。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| File Lookup Dictionary | `references/file-lookup-dictionary.md` | RedCap 的文件地图。人先看这里，而不是默认翻完整目录。 |
| Dictionary 反链 | 脚本头 `Dictionary:` | 文件头的一条短链接，告诉人和 Agent 去字典看完整解释。 |
| 中途架构审计 | `references/midcourse-architecture-task-tree-review.json` | 在大重构中途做一次横向对账，确认任务树没有漂移。 |
| LLM-wiki-lite | `compass/knowledge/llm-wiki/**` | 私有、非权威、带来源锚点的最小语义记忆层。 |
| full LLM-wiki | `P4-2h-full-llm-wiki` | 未来完整产品方向，包括后台生成、RAG/GraphRAG、向量库等；当前没实现。 |
| resource-limited pass | Prism 复核结果 | 独立审查至少一路无 blocker，另一路因资源/超时无法完成，不能冒充 full quorum。 |

### 3.3 关联变更

本轮新增文件进入了 npm pack candidate surface，因此发布前架构审判里的文件数量从 231 更新为 234。这不是发布准备完成，只是保持“当前包面事实”与机器检查一致。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|---|---|---|---|
| 1 | 当前无必须人工介入项 | 本轮只处理治理缺口，不触发发布、凭据、许可证、公共写入或历史资产删除。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| 文件头/字典检查 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| 中途架构审计 | `bash compass/tools/redcap-midcourse-architecture-check.sh` | 通过 |
| 发布前任务树检查 | `bash compass/tools/redcap-pre-release-structure-task-tree-check.sh` | 通过 |
| 文件头 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh file-lookup-dictionary-check` | 通过 |
| 执行保障检查 | `bash compass/tools/redcap-execution-guarantee-check.sh` | 通过 |
| Prism evidence | `bash prism/tools/prism-evidence-check.sh` | 通过 |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh` | 通过 |
| stop-review Bash 3 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-skips-prompt-only-reviewer-when-repo-inspection-required` | 通过 |
| spec-check gate 传播回归 | `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures` | 通过 |
| full acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无必须人工验证项。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| 执行承诺账本 | 待 closeout runtime 核对 |
| 棱镜验收 | `20260507-midcourse-architecture-task-tree-review`，resource-limited-pass |
| closeout summary | 已生成 |
| closeout receipt | 已生成 |
| rescue audit（如有） | 当前无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是 |
| 已自检 | 是，targeted checks 已通过 |
| 已独立验收 | 是，Claude Code 复核无 blocker；Kimi 90 秒超时，按 resource-limited 记录 |
| 已正式完成 | 是，closeout runtime receipt 已生成，pending closure 已清 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|---|---|---|
| `P4-2` 正式 runtime / CLI package public release | 需要显式 release 任务、发布目标、凭据、许可证和 `private=false` 决策 | P2 / blocked-external |
| `P4-2h` 历史资产公共蒸馏 | 需要 RedCap Forge 安全审查、去重、脱敏和 append-only 公共写入边界 | P1 / deferred |
| 完整 LLM-wiki 产品 | 当前只实现 lite；完整产品含后台生成、RAG/GraphRAG、向量库和公共写回，需另开设计任务 | P2 / thresholded future |

### 6.2 触发的新问题

| 问题源 | 解决方案 | 最后效果 |
|---|---|---|
| 关键脚本头规则只在规约里，历史执行不一致 | 把规则接入 File Lookup Dictionary checker，并批量补齐已登记关键脚本 | 后续新增关键脚本缺短中文用途或反链会 fail-closed |
| LLM-wiki-lite 与完整 LLM-wiki 容易被读成同一件事 | 在父账本、任务树和中途审计中显性列出 deferred/full-product 边界 | 完成态不再误导为 full LLM-wiki / RAG 已完成 |
| 大重构过程中“已完成/中插/deferred/blocked”容易散落 | 新增中途审计 JSON + checker + spec-check 接线 | 继续结构调整前有机器化横向对账 |
| stop-review 在空 reviewer 候选数组下会因 Bash 3 `set -u` 提前炸掉 | 空数组先判断长度，且在 prompt-only reviewer 因需要仓库检查被跳过时写入 `insufficient-evidence` | full acceptance 暴露的旧缺口被补平，评审不可用日志恢复可读 |
| spec-check 新门禁接入后，旧 control-gate fixture 没有同步 stub | 将 `midcourse-architecture` 加入 spec-check failure propagation 矩阵，并补 fixture stub | 新门禁不再遮蔽 runtime workspace boundary 等后续门禁的失败信号 |

### 6.3 推荐的下一步行动

1. 若要继续发布方向：另开 `P4-2 formal release readiness`，先处理许可证、`private=false`、凭据、registry 和发布边界。
2. 若要继续知识库方向：另开 `P4-2h RedCap Forge public distillation apply`，只做安全蒸馏，不碰 raw 私有材料。
3. 若要继续长期记忆方向：另开完整 LLM-wiki 产品设计，不把 LLM-wiki-lite 直接升级成 RAG/GraphRAG。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|---|---|---|
| 待 Forge 判断 | 文件头治理要短头 + 字典，不要长注释 | 人类检索需要短中文用途，但长期解释必须集中到字典，避免脚本头变成 token 污染源。 |
| 待 Forge 判断 | Lite 能力必须显性保留 full-product 边界 | 最小可用层完成后，要在父账本和任务树里写清完整产品仍 deferred，否则报告会制造能力幻觉。 |

### 7.2 流程改进建议

后续任何“治理规则已存在但执行不一致”的问题，应优先判断是否能进入已有 checker / spec-check，而不是只追加报告文字。RedCap 当前真正有价值的改进不是多写文档，而是让关键规则变成失败会阻断的机器门禁。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|---|---|---|---|
| script-header-dictionary-boundary | 用户指出脚本头缺中文说明 | no-promote，本轮已作为机器规则落地，暂不写公共 arsenal | `references/file-lookup-dictionary-policy.json` |
| lite-vs-full-product-boundary | 用户指出 LLM-wiki-lite 报告边界可见性不足 | no-promote，本轮已进入父账本/任务树/中途审计 | `references/midcourse-architecture-task-tree-review.json` |

---

## 八、附录

### 附录 A：Commits

当前任务报告生成时尚未 commit；最终提交以本轮 closeout 后 git log 为准。

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|---|---|---|---|
| test / resource-limited | 审查 P2-7 文件头治理和中途审计是否可靠 | Claude Code 无 blocker；Kimi 90 秒超时；未使用 Copilot | `prism/reports/2026-05-07-midcourse-architecture-task-tree-review.md` |

### 附录 C：活跃报告 inbox 控制

为保持 active task-report inbox 不超过 12 份，本轮先尝试迁移 `2026-04-30-historical-asset-migration-main-tree-copy-apply.md`，但回归发现它仍是 receipt 聚合与旧 acceptance 的锚点，因此已恢复原位。最终迁移的是无父账本/测试引用的 `2026-05-05-redcap-public-package-identity-surface.md`，从 `compass/docs/task-reports/` 移入 `redcap-knowledge/task-reports/` 私有冷归档。该动作不删除考古证据，只降低默认上下文暴露面。

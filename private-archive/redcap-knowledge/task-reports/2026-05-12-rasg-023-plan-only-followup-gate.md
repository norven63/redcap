# 任务完成报告：RASG-023 计划型完成后续登记门

**报告日期**：2026-05-12  
**执行者**：Cap（Codex.app + Prism：Claude Code / Kimi）  
**报告版本**：v0.1

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已把“计划已经做完，但真实执行还没做”的情况纳入机器门禁，防止后续任务只留在报告文字里而没有登记成可追踪待办项。
- 详情：本轮解决的是 RASG-017 暴露出的流程漏洞：根目录信息架构目标模型已经完成，但真实物理合并没有同步成为后续任务。现在，类似 `plan-complete`、`design-complete`、`route-only`、`partial-with-explicit-defer` 的结论，都必须登记后续任务、责任面、验收边界和复查触发条件，或者明确说明为什么不需要后续任务。

### 0.2 上一步完成的是

- 上一步完成的是：前一轮已经把 RASG-022 和 RASG-023 登记进历史债务队列，避免根目录物理合并和本次流程缺口继续靠 Norven 人工记忆兜底。

### 0.3 下一步计划做的是

- 下一步计划做的是：完成提交与 clean workspace E2E receipt 刷新后，转入 RASG-021，治理 Prism 降级频率和结论韧性。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：RASG-017 根目录目标模型 -> RASG-022 物理合并后续登记 -> RASG-023 计划型完成后续登记门 -> RASG-021 Prism 降级韧性 -> RASG-022 分批物理迁移。
- 当前所在位置：RASG-023 已完成实现、自检和 Prism 验收，正在等待提交、clean workspace E2E 刷新与 closeout receipt。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮不涉及许可证、npm 发布、凭据、公开仓库写入、不可逆删除或物理目录迁移；下一步可由 Cap 继续推进。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “好的，赞同，你们继续按照自己评估的优先级来稳步推进吧”

### 1.2 触发背景

在 RASG-017 中，RedCap 完成了根目录信息架构目标模型，但真实的物理目录合并没有同步登记成开放任务。这个缺口不是代码实现小问题，而是工作流问题：如果一个任务只是完成“设计/计划/路线”，它仍可能在报告里显得已经完成，从而吞掉后续真实执行。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 继续按已评估优先级推进发布前历史债务治理。 |
| 已覆盖 | 完成 RASG-023 的规则、机器门、正负例回归、spec/diagnose 接线、字典/执行保障、Prism 验收和状态面同步。 |
| 未覆盖/延期 | RASG-021 Prism 降级频率治理、RASG-022 根目录物理合并、正式 npm 发布。 |
| 用户可见边界 | 本轮只能声明“计划型完成后续登记门已固化”，不能声明根目录物理迁移、Prism 降级治理或正式发布已完成。 |
| 后续路径 | 完成本轮 receipt 后进入 RASG-021；RASG-022 仍保持开放，等待更安全的分批物理迁移。 |

---

## 二、方案讨论

### 2.1 问题分析

问题核心是“完成态过于乐观”。如果一个报告说“目标模型完成”，但没有强制要求把“还没做的物理迁移”登记成后续任务，那么系统就会逐渐依赖人类记忆。RedCap 需要把这种后续登记变成检查项，而不是靠 Cap 或 Norven 临场提醒。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 只在报告模板里提醒 | 要求报告写清延期项 | 成本低 | 仍可能被遗漏，不能拦住假完成 |
| Q1 | 增加专门机器门 | 用 checker 和负例夹具检查后续登记是否存在 | 可回归、可接入 spec/diagnose | 需要维护少量 policy 和 fixture |
| Q1 | 直接提前做 RASG-022 | 先执行物理目录迁移 | 看似更快清债 | 绕过了流程缺口，后续仍可能复发 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 增加专门机器门 | 当前最重要的是先修“计划型完成吞掉后续任务”的系统性漏洞，再进入 RASG-021/RASG-022。 | CAP_DECIDE + Prism Review |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `compass/tools/redcap-plan-only-followup-registration-check.py` / `.sh` | 新建 | 新增 RASG-023 专门检查器，验证计划型完成必须登记后续任务或给出明确无需后续的理由。 |
| `references/plan-only-followup-registration-fixtures.json` | 新建 | 新增正负例夹具：正例覆盖 RASG-017 -> RASG-022，负例证明缺登记字段会失败。 |
| `compass/tools/redcap-spec-check.sh` / `compass/tools/redcap-diagnose.sh` | 修改 | 将 RASG-023 检查接入全局规范检查和源码诊断链。 |
| `references/conclusion-prism-policy.json` / `references/execution-guarantees.json` | 修改 | 把计划型完成后续登记规则登记为正式执行保障。 |
| `references/file-lookup-dictionary.md` / `references/file-lookup-dictionary-policy.json` | 修改 | 为新增检查器和夹具补齐查阅入口，并修正一个根目录信息架构检查脚本名。 |
| `references/pre-release-product-architecture-review.json` / `references/redcap-parent-task-ledger.md` | 修改 | 同步 npm 候选包面从 181 到 184，并明确 RASG-023 不等于正式发布。 |
| `references/reference-asset-lifecycle.json` | 修改 | 刷新引用资产生命周期登记。 |
| `prism/reports/2026-05-12-rasg-023-plan-only-followup-gate.md` | 新建 | 记录 Claude Code 与 Kimi 的独立复核结论。 |
| `redcap-knowledge/task-reports/2026-05-10-progress-meter-implementation.md` | 移动 | 将无活跃外部引用的旧报告迁入私有冷归档，恢复 active task report 上限。 |

### 3.2 技术实现要点

本轮新增的检查器只盯一个问题：如果结论属于“计划/设计/路线完成，但还有后续动作”，那后续动作必须有可追踪的记录。每条延期项至少要写明它是什么、追踪在哪里、谁负责、怎么验收、何时复查、是否阻塞当前主线。

RASG-017 -> RASG-022 被固定为正例回归：目标模型可以完成，但真实物理合并仍必须作为 RASG-022 开放存在。负例则模拟“报告说 plan-complete，但只写了一句还有后续，没有 tracking surface / owner / acceptance boundary / revisit trigger”，这类情况现在会失败。

Claude Code 指出两个边界：检查器硬编码 RASG 编号会让回归锚点更脆，但这是本轮为了锁住真实事故链路的有意设计；“无需后续任务”的理由只能做结构校验，语义是否诚实仍需要 Prism 复核。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| plan-only completion | `redcap-plan-only-followup-registration-check.py` | 只完成了计划、设计或路线，不代表真实执行已经完成。 |
| durable follow-up | `references/plan-only-followup-registration-fixtures.json` | 后续任务必须登记到 backlog、任务树或 receipt 这类可追踪位置，而不是藏在自然语言段落里。 |
| revisit trigger | fixture 字段 | 后续任务什么时候必须重新被看见，例如进入 RASG-022 前、release readiness 前。 |
| acceptance boundary | fixture 字段 | 后续任务怎样才算完成，防止“做了一点”又被说成全部完成。 |

### 3.3 关联变更

本轮没有启动 RASG-022 的物理目录迁移，也没有启动正式 npm 发布。由于新增 3 个会被纳入包候选面的文件，发布前产品架构审判和父任务账本的候选包计数同步从 181 更新到 184。

为保持活跃任务报告入口不过载，本轮还把无活跃外部引用的 `2026-05-10-progress-meter-implementation.md` 移入 `redcap-knowledge/task-reports/`。这是冷归档，不是删除；需要考古时仍可按知识归档读取。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无必须人工审核项 | 本轮是流程与检查器加固，不触碰 Norven 保留决策。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| JSON 语法 | `python3 -m json.tool references/pre-release-product-architecture-review.json >/dev/null` | ✅ |
| RASG-023 正负例门 | `bash compass/tools/redcap-plan-only-followup-registration-check.sh` | ✅ |
| Prism 结论政策 | `bash compass/tools/redcap-conclusion-prism-check.sh` | ✅ |
| 文件查阅字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | ✅ |
| 执行保障 | `bash compass/tools/redcap-execution-guarantee-check.sh` | ✅ |
| 引用资产生命周期 | `bash compass/tools/redcap-reference-asset-lifecycle.sh check` | ✅ |
| 根目录信息架构 | `bash compass/tools/redcap-root-information-architecture-check.sh` | ✅ |
| 发布前产品架构 | `bash compass/tools/redcap-pre-release-product-architecture-check.sh` | ✅ |
| runtime package manifest | `bash compass/tools/redcap-runtime-package-manifest.sh --check` | ✅ |
| change-intake | `bash compass/tools/redcap-change-intake-check.sh .dev-task.md` | ✅ |
| Layer B FSM | `bash compass/tools/redcap-layerb-fsm-check.sh .dev-task.md` | ✅ |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | ✅ |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | ⏳ 只剩 clean workspace E2E receipt 待提交后刷新 |

### 5.2 Prism 评审

| Provider | 角色 | 状态 | 结论 |
|---|---|---|---|
| Claude Code | reviewer | responded | `pass`，无 blocker；两个 low concern 已记录为边界 |
| Kimi | challenger | responded | `pass`，无 blocker、无 concern |
| Copilot / Codex CLI | - | 未调用 | 按保护策略，本轮 Claude Code 与 Kimi 可用，不调用 Copilot 或 Codex CLI |

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 待 closeout 核对 |
| 棱镜验收 | 已绑定并通过 |
| closeout summary | 待生成 |
| closeout receipt | 待生成 |
| rescue audit | 暂无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是 |
| 已正式完成 | 否，仍需提交、刷新 clean workspace E2E 和 closeout receipt |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| RASG-021 Prism 降级频率与结论韧性 | 独立历史债务，需基于 Prism 报告/registry 做统计和阈值。 | P1 |
| RASG-022 根目录信息架构真实物理合并 | 高风险物理迁移，需要在 RASG-021 后分批执行。 | P1 |
| 正式 npm 发布 | 仍需要许可证、registry、凭据、发布开关等 Norven 保留决策。 | 人工边界 |

### 6.2 触发的新问题

| 问题 | 处理 |
|------|------|
| 文件查阅字典中根目录信息架构检查脚本名写错 | 已顺手修正为真实脚本名，避免后续人或 AI 被误导。 |
| Claude Code 首次复核预算过低 | 已重跑，给足预算并限制只读工具；最终取得有效 pass verdict。 |

### 6.3 推荐的下一步行动

1. 提交 RASG-023 实现。
2. 刷新 clean workspace E2E receipt。
3. 运行最终 spec/diagnose/closeout。
4. 转入 RASG-021。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| 无新增 Lesson | 无 | 本轮是把已识别的 RASG-023 流程缺口机器化，不新增独立经验条目。 |

### 7.2 流程改进建议

后续所有“设计完成、计划完成、路线完成、部分完成但延期”的任务，都应该先回答：哪些事没有做完？它们登记在哪里？谁负责？怎样验收？什么时候重新出现？如果这些答案不存在，就不能把任务写成完成。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | RASG-023 已是既有历史债务项 | no-promote | `references/backlogs/redcap-architecture-smell-governance.json` |

---

## 八、附录

### 附录 A：Commits

```
待提交
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| acceptance-review | RASG-023 是否已形成可接受的计划型完成后续登记门 | Claude Code + Kimi 均 pass，无 blocker | `prism/reports/2026-05-12-rasg-023-plan-only-followup-gate.md` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 历史债务登记：`references/backlogs/redcap-architecture-smell-governance.json`
- 回归夹具：`references/plan-only-followup-registration-fixtures.json`
- 棱镜证据：`prism/runs/20260512-rasg023-plan-only-followup-gate/`

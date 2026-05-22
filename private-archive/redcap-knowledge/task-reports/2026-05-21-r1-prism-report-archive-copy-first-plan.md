# 任务完成报告：P4-12 Prism 报告归档迁移规划

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-12 已把 Prism 报告归档从“路线已选定”推进到“迁移规划可机器检查”。
- 人话解释：我们现在知道当前正式 Prism 报告将来应该复制到哪里、旧路径必须如何继续可用、失败如何回滚、未来真正执行前要通过哪些验证。
- 关键边界：本轮没有复制、移动、删除、重命名任何 Prism 报告；没有创建正式归档副本；没有清理 `prism/runs` 原始证据；没有关闭 release blocker。

### 0.2 上一步完成的是

- 上一步完成的是：P4-11 路线选择。Claude Code 与 Kimi 共同建议先做 Prism 报告归档的 copy-first / alias-first 规划桥，而不是直接搬文件、清理证据或推进更大的控制面批次。

### 0.3 下一步计划做的是

- 下一步计划做的是：P4-13 “copy-first apply readiness / rehearsal”，先验证未来真实执行的顺序、别名兼容、回滚和包面证明。
- 仍然不能做的事：退休旧锚点、清理 raw evidence、宣布 RedCap release-ready。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：正式发布准备路线 → 控制面与 Prism 预检 → runtime facade → Prism package-visible support → Prism report archive 预检 → 下一切片选择 → **P4-12 迁移规划** → P4-13 apply readiness / rehearsal。
- 当前所在位置：`framework-upgrade / P4-12`，属于发布前 R1 的安全小切片，不是正式发布任务。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触碰许可证、registry、npm 发布、凭据、secret、raw evidence cleanup、旧锚点删除或 Layer A 产品范围裁决。

## 一、需求背景

P4-10 只是证明 Prism 报告归档方向“可以继续设计”，P4-11 只是选定下一步“应该先做规划”。如果直接进入物理迁移，风险是把预检误当成迁移完成，或者意外破坏旧报告路径和历史考古能力。

P4-12 的目标就是补上中间这层安全桥：先让计划本身可审计、可回滚、可被机器阻止越界，再谈未来 apply。

## 二、方案讨论

### 2.1 如何解决

本轮把规划写成三层保护：

| 层 | 作用 | 结果 |
| --- | --- | --- |
| 迁移清单 | 列出每份当前 Prism 正式报告和未来归档目标 | 当前报告集合已覆盖，且每项绑定 source hash。 |
| 边界声明 | 明确本轮只能规划，不能 copy/delete/cleanup/release-ready | 越界字段一旦被改成 true，checker 会失败。 |
| 验收门 | 接入 spec-check、diagnose 和 targeted acceptance | 后续不能只靠口头承诺说“没越界”。 |

### 2.2 棱镜评审结论

Claude Code 结论是通过，并提醒 plan 会绑定当前报告集合；如果未来新增报告，必须更新计划。

Kimi 结论是带关注通过，关注点集中在 closeout 仍未完成：需要提交、clean workspace E2E、任务卡勾选和 receipt。

两边没有提出阻塞性 bug。Claude Code 建议补强的 acceptance 负例，本轮已补齐到 targeted acceptance 中。

## 三、落地结果

### 3.1 当前效果

RedCap 现在不会再只靠“我们计划以后安全迁移”这种软承诺。它已经有一个机器可检查的计划资产，会阻止以下错误：

- 少覆盖某份当前报告。
- 来源报告 hash 过期。
- 提前声明复制、删除、清理证据或 release-ready。
- 本轮偷偷创建 `private-archive/prism-reports/*.md` 正式归档副本。
- 把 `prism/reports`、`prism/runs` 或未来私有归档路径放进公开 npm 包候选面。

### 3.2 已验证

| 验证项 | 当前结果 |
| --- | --- |
| plan checker | 通过 |
| targeted acceptance | 通过 |
| Prism review | Claude Code + Kimi 已完成；Copilot 未调用；Gemini 本轮不可用 |
| package surface | 已保持 `prism/reports`、`prism/runs`、`private-archive/prism-reports` 不进入候选面 |
| closeout runtime | 待最终 receipt 更新 |

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| copy-first | 先证明新位置能安全承接，再考虑旧位置怎么处理。 | 未来迁移必须先复制和验证，不能直接搬走旧报告。 |
| alias-first | 旧路径不能突然断掉，必须先有兼容入口或可解析证明。 | 保护历史报告链接和考古路径。 |
| delete-last | 删除或退休旧锚点永远是最后一步，而且必须单独验收。 | 防止把规划任务升级成删除任务。 |
| raw evidence | Prism CLI 调用留下的原始运行证据，和正式报告不是一类东西，不能顺手清理。 | 明确 `prism/runs` 不在本轮处理范围。 |
| release blocker | 发布前仍未解决的阻塞项，不能因为完成了规划就宣布关闭。 | P4-12 完成后 blocker 仍保持开放。 |

## 四、人工审核要点

| 审核项 | 说明 |
| --- | --- |
| 无需本轮人工审核 | 本轮只做规划和验收门，不触碰人工保留决策。 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 当前结果 |
| --- | --- | --- |
| plan checker | `bash compass/tools/redcap-r1-prism-report-archive-copy-first-plan-check.sh` | 通过；53 份报告、53 条 mapping，blocker 仍开放 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh r1-prism-report-archive-copy-first-plan-check` | 通过 |
| full spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过；当前仅剩 closeout receipt 未生成 |
| clean workspace E2E | `bash compass/tools/redcap-clean-workspace-e2e.sh --write-result --timeout 180` | 通过；干净工作区 HEAD `c3535f8`，候选数 284，npm pack dry-run 已执行 |

### 5.3 closeout runtime / receipt

| 项目 | 当前结果 |
| --- | --- |
| 执行承诺账本 | 已由 closeout runtime 核对通过，11 项承诺无 pending |
| closeout receipt | 已生成：`/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-r1-prism-report-archive-copy-first-plan-9c56280c8e2f640ad370dc8473f3ffae9350046d57720ee5cb07e9e5098eee36.json` |

### 5.4 完成等级（禁止混报）

| 层级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 是 | plan-only 迁移清单、机器检查、targeted acceptance 和 Prism 报告已落地。 |
| 已自检 | 是 | plan checker、targeted acceptance、spec-check、diagnose 与 clean workspace E2E 已通过。 |
| 已独立验收 | 是 | Claude Code 与 Kimi 已完成棱镜评审，无 blocker。 |
| 已正式完成 | 是 | closeout runtime 已生成 receipt，承诺账本 11/11 完成。 |

## 六、遗留问题与下一步

| 问题 | 当前处理 | 建议优先级 |
| --- | --- | --- |
| 真实 report archive copy-first apply | 本轮只规划，不执行 | P0-before-release |
| 旧锚点退休 | 必须等待 copy-first apply、alias proof、archive-check 和单独 delete-last receipt | future-after-apply |
| raw evidence cleanup | 仍需保存证明和按需人工批准 | manual-boundary-if-destructive |
| `prism-layer-and-evidence` blocker | 仍然开放 | P0-before-release |

### 6.1 推荐下一步

启动 P4-13：先做 copy-first apply readiness / rehearsal，继续保持“小步、可回滚、不越界”的节奏。

## 七、经验沉淀

### 7.1 新增 Lesson 候选

| 标题 | 问题源 | 解决方案 | 最后效果 |
| --- | --- | --- | --- |
| report archive plan 必须跟随报告集合变化 | 规划文件如果静态绑定当前报告集合，新增报告会让计划过期 | checker 强制 report_count、mapping、source hash 与当前报告集合一致 | 任何新增报告都会迫使计划刷新，避免遗漏。 |

### 7.2 是否晋升正式 lesson

暂不晋升为正式 lesson。本轮已经把规则直接固化到 checker 和 acceptance；若未来新增报告导致同类失配再次出现，再晋升为跨任务经验。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
| --- | --- | --- | --- |
| Prism 报告集合变化必须刷新迁移计划 | 本轮 P4-12 新增正式 Prism report 后，plan 从 52 份更新到 53 份 | no-promote；已直接固化到 checker 与 acceptance，暂不重复沉淀为公共经验 | `references/r1-prism-report-archive-copy-first-plan.json`；`compass/tools/redcap-r1-prism-report-archive-copy-first-plan-check.sh` |

## 八、附录

- 当前任务卡：`.dev-task.md`
- 规划资产：`references/r1-prism-report-archive-copy-first-plan.json`
- Prism review 报告：`prism/reports/2026-05-21-r1-prism-report-archive-copy-first-plan.md`
- Prism 运行目录：`prism/runs/20260521-r1-prism-report-archive-copy-first-plan/`
- 长期路线权威：`references/backlogs/framework-upgrade.json`

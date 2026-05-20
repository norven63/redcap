# 任务完成报告：R1 下一发布前 blocker 切片选择

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-7 已通过 Claude Code 与 Kimi 的棱镜路线评审，选出下一条可自主推进的小切片：`prism-layer-and-evidence batch-1`，也就是 package-visible Prism support 与 provider-routing contract。
- 详情：这只是路线选择和任务锚点登记，不是实际执行 Prism 物理拆分，也不是关闭 release blocker。

### 0.2 上一步完成的是

- 上一步完成的是：P4-6 已为 `internal-control-plane` 的 batch-1 runtime-public-support 建立 runtime facade；旧 `compass/tools` 仍是权威实现，R1 blocker 仍未关闭。

### 0.3 下一步计划做的是

- 下一步计划做的是：进入 P4-8，围绕 Prism 的 package-visible support 和 provider-routing contract 做非破坏性 copy-first / alias-first 实施；不清理证据、不移动旧锚点、不做真实发布。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：正式发布准备路线 → R1 延期根目录分类 → 控制面与 Prism 预检 → 控制面 runtime facade → 下一 blocker 切片选择 → Prism package-visible support 小切片 → 后续控制面 batch-2 / Prism report archive / Layer A 人工边界。
- 当前所在位置：`framework-upgrade / P4-7`，处于 P4-6 收口后的“下一条安全切片选择”阶段。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有命中许可证、registry、发布开关、凭据、旧锚点删除、Prism evidence cleanup 或 Layer A 产品范围裁决；下一步 P4-8 也被限制在非破坏性 copy-first / alias-first 范围内。

## 一、需求背景

P4-6 已把控制面 batch-1 推进到 runtime facade，但正式发布前仍有三类 R1 blocker：`internal-control-plane`、`prism-layer-and-evidence`、`internal-layer-a`。

如果直接继续实现，很容易出现两类风险：一是主 Agent 只沿着刚完成的控制面路线惯性推进，直接进入 53 个候选的 batch-2 大任务；二是误把需要 Norven 裁决的 Layer A 产品边界当成可自主推进项。

本轮的目标就是在动手前先做路线评审：用棱镜多视角选择下一条足够小、能实质减少发布债务、又不会跨越人工保留边界的切片。

## 二、方案讨论

### 2.1 如何解决

本轮把剩余候选拆成六类让棱镜审查：控制面 batch-2、控制面 batch-3、Prism batch-1、Prism batch-2、Prism batch-3、Layer A 产品边界。

Claude Code 建议继续做控制面 batch-2，因为它最直接延续 P4-6；Kimi 建议做 Prism batch-1，因为它只有 8 个候选，是当前最小的非破坏性 blocker 切片。

最终裁决采用 Kimi 的路线：下一步先做 Prism batch-1。理由是它更符合 P4-7 的任务目标：先选择一个能安全落地的小切片，而不是把路线直接推进到 53 个候选的大批量任务。

### 2.2 边界裁决

本轮不执行任何真实发布动作，也不执行任何旧锚点移动、删除、替换或证据清理。控制面 batch-2 没有被否定，只是被放到后续更适合拆分的大切片里。

Layer A 产品边界仍保留为 Norven 人工决策，不允许由 Cap 或棱镜代替决定。

## 三、落地结果

### 3.1 当前效果

现在 RedCap 的长期路线已经登记 P4-7 和 P4-8：P4-7 负责路线选择，P4-8 负责未来实施 Prism package-visible support 小切片。

这让父任务线从“P4-6 已完成，但下一步未知”变成“下一步已被棱镜审查并登记”，降低了任务漂移风险。

### 3.2 已验证

- Claude Code 已返回路线建议。
- Kimi 已返回路线建议。
- Gemini 未调用，原因是可用性嗅探失败。
- Copilot 未调用，原因是 Claude Code 与 Kimi 可用，按保护性 fallback 策略不消耗 Copilot。
- Prism session registry 已记录本轮 quorum。
- `references/backlogs/framework-upgrade.json` 已登记 P4-7 与 P4-8。
- 人类可读 backlog 说明已同步。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 / 文件 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| P4-7 | 本轮路线选择任务 | 只决定下一步做哪条安全切片 |
| P4-8 | 下一条待执行任务 | 未来实施 Prism package-visible support 小切片 |
| Prism batch-1 | Prism 的第一批 package-visible 支撑资产 | 被选为下一步，因为它小、可自主推进、非破坏性 |
| 控制面 batch-2 | 控制面 policy / contract 分类批次 | 仍是后续任务，但 53 个候选较大，本轮不直接进入 |
| Layer A 产品边界 | `loom` 是否进入公共产品范围的问题 | 仍需要 Norven 人工裁决 |

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
| --- | --- | --- | --- |
| 1 | 无需本轮人工审核 | 本轮只做路线选择与后续锚点登记，不触碰发布、许可证、凭据、旧锚点删除或产品边界裁决。 | P1 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 当前结果 |
| --- | --- | --- |
| change-intake | `bash compass/tools/redcap-change-intake-check.sh .dev-task.md` | 通过 |
| backlog sync | `bash compass/tools/redcap-backlog-check.sh strict .dev-task.md` | 通过 |
| Prism availability | `bash prism/tools/prism-availability.sh status` | Claude Code / Kimi 可用；Gemini 不可用；Copilot 被策略压制 |
| Prism raw collection | `claude -p ...` / `kimi -y -p ...` | 已返回 |
| full spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |

### 5.2 人工验证项

- 无。本轮结论不需要 Norven 做发布、许可证、registry、删除、清理或产品范围决策。

### 5.3 closeout runtime / receipt

| 项目 | 当前结果 |
| --- | --- |
| 执行承诺账本 | 已勾选，待 closeout runtime 最终核对 |
| 棱镜验收 | 已完成路线评审；Claude Code 与 Kimi 均返回 proceed，但推荐切片不同 |
| closeout receipt | 待生成 |

### 5.4 完成等级（禁止混报）

| 层级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 是 | P4-7 路线评审、Prism 报告、session registry、P4-8 后续锚点已落地。 |
| 已自检 | 是 | change-intake、backlog、human-output、archive-check、full spec-check 与 diagnose 均已通过。 |
| 已独立验收 | 是 | Claude Code 与 Kimi 已完成独立路线评审；Gemini 不可用，Copilot 按策略未调用。 |
| 已正式完成 | 否 | closeout receipt 尚未生成。 |

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
| --- | --- | --- |
| Prism batch-1 真实实施 | 本轮只做路线选择；实施应另开 P4-8，避免混报。 | P0-before-release |
| 控制面 batch-2 | 53 个候选较大，需要后续拆分或独立切片。 | P0-before-release |
| Prism report archive / local evidence | 仍是后续独立任务，尤其 evidence cleanup 需要更严格边界。 | P0-before-release |
| Layer A 产品边界 | 需要 Norven 人工裁决，不能由 Agent 自主决定。 | manual-boundary |

### 6.2 触发的新问题

- 无新增 blocker。棱镜分歧被记录为路线判断差异，不是失败。

### 6.3 推荐的下一步行动

1. 完成 P4-7 closeout。
2. 启动 Prism package-visible support copy-first 小切片。

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
| --- | --- | --- |
| 无 | 无新增 lesson | 本轮是路线选择，未发现新的可复用工程陷阱；棱镜分歧已写入 Prism review 证据。 |

### 7.2 流程改进建议

当两个可行路线都能推进时，优先选择“候选更少、边界更硬、能独立验收”的小切片；更大的直接路线应保留，但不要用惯性压过安全切片。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
| --- | --- | --- | --- |
| 无新增候选 | 本轮 P4-7 路线选择 | no-promote；已有机制可覆盖本轮模式 | 本报告与 Prism route-review 报告 |

## 八、附录

### 附录 A：相关文档索引

- 当前任务卡：`.dev-task.md`
- Prism route-review 报告：`prism/reports/2026-05-20-r1-next-slice-after-runtime-facade-review.md`
- Prism 运行目录：`prism/runs/20260520-r1-next-slice-after-runtime-facade/`
- 长期路线权威：`references/backlogs/framework-upgrade.json`
- 人类路线说明：`compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md`

## 九、剩余边界

本轮不可声明：

- P4-8 已实施。
- `prism-layer-and-evidence` blocker 已关闭。
- `internal-control-plane` batch-2 已解决。
- Layer A 产品边界已裁决。
- RedCap 已 release-ready。
- 可以进入真实 registry publication。

## 十、棱镜状态

Claude Code 与 Kimi 均返回 `proceed`，但推荐路线不同。最终采用 weak-consensus 裁决：先推进 Prism batch-1 小切片。Gemini 因可用性错误未调用，Copilot 因保护性 fallback 策略未调用。

## 十一、旁路归档说明

本轮为了维持活跃 task-report 区的上限，将旧报告 `compass/docs/task-reports/2026-05-17-formal-release-r1-root-group-disposition-preflight.md` 迁入 `private-archive/redcap-knowledge/task-reports/2026-05-17-formal-release-r1-root-group-disposition-preflight.md`，并同步更新长期 backlog 证据路径、docs catalog 与 cold archive inventory。

这不是 P4-7 的功能目标，也没有删除历史证据；它只是把低频考古材料移出活跃首读区，避免 task-report 区再次膨胀。

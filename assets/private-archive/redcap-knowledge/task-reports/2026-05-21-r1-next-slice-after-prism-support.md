# 任务完成报告：P4-9 发布前下一小切片选择

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-9 已通过 Claude Code 与 Kimi 的棱镜路线评审，选定下一条正式发布前安全小切片：`Prism tracked report archive copy-first / report-index migration preflight`。
- 人话解释：下一步先证明 Prism 报告归档和索引迁移怎么安全做，而不是直接清理 `prism/runs` 运行证据，也不是进入 Layer A 产品裁决。

### 0.2 上一步完成的是

- 上一步完成的是：P4-8 已为 Prism package-visible support 和 provider-routing contract 建立 8 个 runtime facade；旧 `prism/*` 锚点继续是权威来源。

### 0.3 下一步计划做的是

- 下一步计划做的是：进入 P4-10，只做 Prism 报告归档 copy-first / 索引迁移预检；保留旧报告锚点，不删除、不移动、不清理 raw run evidence，不宣称 release blocker 关闭。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：正式发布准备路线 → R1 延期根目录分类 → 控制面与 Prism 预检 → 控制面 runtime facade → P4-7 下一切片选择 → P4-8 Prism package-visible support → **P4-9 下一切片选择** → P4-10 Prism report archive 预检。
- 当前所在位置：`framework-upgrade / P4-9`，属于路线选择与后续锚点登记，不是具体迁移实现，也不是正式发布。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触碰许可证、registry、凭据、发布开关、私密文件、旧锚点删除、raw evidence cleanup 或 Layer A 产品范围裁决。

## 一、需求背景

P4-8 完成后，剩余发布前 blocker 仍有多条路：继续做 Prism 报告归档、清理本地运行证据、推进控制面 batch-2，或者处理 Layer A 产品边界。

这些方向的风险差异很大。如果直接凭惯性进入实现，容易出现两个问题：把路线选择误报成 blocker 已关闭，或者绕过 Norven 保留的人工作业边界。本轮先做 P4-9，就是为了在动手前把下一步选清楚。

## 二、方案讨论

### 2.1 如何解决

本轮把候选拆成四类交给棱镜评审：

| 候选 | 评审结论 | 原因 |
| --- | --- | --- |
| Prism report archive copy-first / index preflight | 选为下一步 | 小、非破坏性、不需要人工裁决，且为未来证据清理打基础。 |
| Prism local run evidence cleanup | 暂不选 | 涉及 raw evidence，若清理或剪枝需要人工批准。 |
| internal control-plane batch-2 | 暂不选 | 规模更大，约 53 个候选，适合后续再拆小。 |
| Layer A product boundary | 不由本轮处理 | 属于 Norven 保留产品决策。 |

Claude Code 与 Kimi 最终都建议选择 Prism report archive 方向。这个结论不是说 Prism blocker 已关闭，而是说下一步应该先处理“报告归档和索引迁移的安全证明”。

### 2.2 边界裁决

本轮不执行真实发布，不改许可证、registry、凭据或发布开关，也不读取 `.env`。本轮创建的 P4-10 也不允许删除、移动或清理 `prism/runs` raw evidence；任何未来证据清理都必须单独证明并按需取得人工批准。

## 三、落地结果

### 3.1 当前效果

RedCap 的长期路线现在从“P4-8 后下一步未知”变成“下一步已由棱镜评审并登记为 P4-10”。这降低了任务漂移风险，也避免主线突然跳进更大的控制面 batch 或人工产品决策。

### 3.2 已验证

- Claude Code 已完成独立评审，建议选择 A。
- Kimi 已完成独立评审，建议选择 A。
- Copilot 未调用，符合 protected fallback 策略。
- Gemini 未加入 quorum，原因是当前状态面显示它在本工作区不稳定；Claude Code 与 Kimi 已满足双模型族评审。
- `references/r1-next-slice-after-prism-support.json` 已记录候选矩阵、边界与下一切片。
- `references/backlogs/framework-upgrade.json` 已把 P4-9 标为完成，并登记 P4-10。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 / 文件 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| P4-9 | 本轮路线选择任务 | 只决定下一步做哪条小切片，不实现迁移。 |
| P4-10 | 下一条待执行任务 | 未来证明 Prism 报告归档与索引迁移可以安全做。 |
| report archive | 报告归档 | 处理已追踪的 Prism 报告，不等于清理 raw run evidence。 |
| raw run evidence | 原始运行证据 | `prism/runs` 下的本地运行材料，本轮和下一步都不能清理。 |
| old anchor | 旧锚点 | 旧路径必须继续可访问，避免破坏历史考古。 |

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
| --- | --- | --- | --- |
| 1 | 无需本轮人工审核 | 本轮只完成路线评审、后续锚点登记与报告归档，不触碰人工保留决策。 | P1 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 当前结果 |
| --- | --- | --- |
| change-intake | `bash compass/tools/redcap-change-intake-check.sh .dev-task.md --mode closeout` | 通过 |
| PM Gate | `bash compass/tools/redcap-pm-gate-check.sh strict codex .dev-task.md` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过 |
| clean workspace E2E | `bash compass/tools/redcap-clean-workspace-e2e.sh --write-result --timeout 180` | 通过 |
| full spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |

### 5.2 人工验证项

- 无。本轮不需要 Norven 做发布、许可证、registry、凭据、删除、清理或产品范围决策。

### 5.3 closeout runtime / receipt

| 项目 | 当前结果 |
| --- | --- |
| 执行承诺账本 | 已由 closeout runtime 核对通过，8 项承诺无 pending |
| 棱镜验收 | Claude Code 与 Kimi 已返回，无 blocker |
| closeout receipt | 已生成：`/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-r1-next-slice-after-prism-support-92b9cac82691b546621169e5ed09879ffdd9f01008a69a41886aca47ed7259d9.json` |

### 5.4 完成等级（禁止混报）

| 层级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 是 | P4-9 路线评审、Prism 报告、候选矩阵与 P4-10 后续锚点已落地。 |
| 已自检 | 是 | change-intake、PM Gate、Prism acceptance、clean workspace E2E、full spec-check 与 diagnose 均已通过。 |
| 已独立验收 | 是 | Claude Code 与 Kimi 均选择 A，无 blocker。 |
| 已正式完成 | 是 | closeout runtime 已生成 receipt，承诺账本 8/8 完成。 |

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
| --- | --- | --- |
| Prism report archive 真实预检 | 本轮只做路线选择，实施应进入 P4-10。 | P0-before-release |
| Prism local run evidence cleanup | 涉及 raw evidence，不可顺手清理。 | manual-boundary-if-destructive |
| control-plane batch-2 | 规模更大，需要后续拆小。 | P0-before-release |
| Layer A 产品边界 | 需要 Norven 人工裁决。 | manual-boundary |

### 6.2 触发的新问题

- 无新增 blocker。Claude Code 输出里出现 Layer A SessionEnd hook 失败提示，但这来自 Claude Code 宿主退出阶段，不影响本轮 P4-9 路线结论；后续若反复出现，应归入宿主 hook 健康专项观察。

### 6.3 推荐的下一步行动

1. 启动 P4-10：Prism report archive copy-first / index migration preflight。
2. 下一步继续保持非破坏性、可审计、可回滚节奏。

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
| --- | --- | --- |
| 无 | 无新增 lesson | 本轮没有发现新的通用工程陷阱；“先归档报告索引，再谈运行证据清理”已写入 P4-10 边界。 |

### 7.2 流程改进建议

路线选择任务完成时，必须明确区分“下一步已选定”和“下一步已实现”。否则长期 backlog 标记 done 后，容易被误读为 blocker 已关闭。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
| --- | --- | --- | --- |
| Prism 报告先于 raw evidence 清理 | 本轮 P4-9 | no-promote；当前已进入 P4-10 任务边界，不需要单独晋升为公共经验 | 本报告与 `references/r1-next-slice-after-prism-support.json` |

## 八、附录

### 附录 A：相关文档索引

- 当前任务卡：`.dev-task.md`
- 路线决策资产：`references/r1-next-slice-after-prism-support.json`
- Prism review 报告：`prism/reports/2026-05-21-r1-next-slice-after-prism-support.md`
- Prism 运行目录：`prism/runs/20260521-r1-next-slice-after-prism-support/`
- 长期路线权威：`references/backlogs/framework-upgrade.json`

## 九、剩余边界

本轮不可声明：

- P4-10 已实现。
- Prism report archive 已迁移。
- `prism-layer-and-evidence` blocker 已关闭。
- `prism/runs` raw evidence 已清理。
- 旧 `prism/reports` 锚点已退休。
- Layer A 产品边界已裁决。
- RedCap 已 release-ready。

## 十、棱镜状态

Claude Code verdict：pass，推荐 A。Kimi verdict：pass，推荐 A。两者形成 consensus-select-prism-report-archive-copy-first-preflight。Gemini 未加入 quorum，Copilot 按策略未调用。

## 十一、旁路归档说明

本轮新增 P4-9 任务报告后，活跃 task-report 区会超过机器上限。为保持首读区健康，已将旧报告 `compass/docs/task-reports/2026-05-19-r1-prism-evidence-retention-split-dry-run.md` 迁入 `private-archive/redcap-knowledge/task-reports/2026-05-19-r1-prism-evidence-retention-split-dry-run.md`，并同步更新长期 backlog 与 Prism report index 的证据路径。

这不是 P4-9 的功能目标，也没有删除历史证据；只是把低频考古材料移出活跃首读区。

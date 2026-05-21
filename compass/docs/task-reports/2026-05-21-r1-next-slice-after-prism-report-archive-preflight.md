# 任务完成报告：P4-11 发布前下一小切片选择

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-11 已通过 Claude Code 与 Kimi 的棱镜路线评审，选定下一条正式发布前安全小切片：`Prism report archive copy-first / alias-first migration planning`。
- 人话解释：下一步先写清楚 Prism 报告将来如何安全归档、旧报告路径如何继续可访问、失败如何回滚；不是现在就搬文件。

### 0.2 上一步完成的是

- 上一步完成的是：P4-10 已完成 Prism 报告归档与索引迁移的预检，证明这个方向可以继续推进，但仍保留旧 `prism/reports` 锚点，且未清理 `prism/runs` 原始运行证据。

### 0.3 下一步计划做的是

- 下一步计划做的是：进入 P4-12，只做 Prism 报告归档 copy-first / alias-first 的迁移规划、清单、别名草案、回滚与验证方案。
- 关键边界：P4-12 仍然不执行物理复制、移动、删除，不清理 raw evidence，不关闭整个 `prism-layer-and-evidence` blocker。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：正式发布准备路线 → 控制面与 Prism 预检 → 控制面 runtime facade → P4-8 Prism package-visible support → P4-10 Prism report archive 预检 → **P4-11 下一切片选择** → P4-12 Prism report archive 迁移规划。
- 当前所在位置：`framework-upgrade / P4-11`，属于路线选择与后续锚点登记，不是具体迁移实现，也不是正式发布。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触碰许可证、registry、凭据、发布开关、私密文件、旧锚点删除、raw evidence cleanup 或 Layer A 产品范围裁决。

## 一、需求背景

P4-10 完成后，剩余发布前方向仍有多条路：继续处理 Prism 报告归档、推进更大的控制面 batch、处理 raw evidence cleanup，或者回到 Layer A 产品边界。

这些方向风险差异很大。若直接进入实现，很容易把“预检已完成”误报成“迁移已完成”，或绕过 Norven 保留的人工作业边界。本轮先做 P4-11，就是为了把下一步选清楚。

## 二、方案讨论

### 2.1 如何解决

本轮把候选拆成五类交给棱镜评审：

| 候选 | 评审结论 | 原因 |
| --- | --- | --- |
| Prism report archive 迁移规划 | 选为下一步 | 小、非破坏性、不需要人工裁决，且直接续接 P4-10。 |
| 直接 report archive apply | 暂不选 | 当前仍不允许物理复制、移动或删除。 |
| internal control-plane batch-2 / batch-3 | 暂不选 | 规模更大，不适合作为 P4-10 后的下一小步。 |
| Prism raw run evidence cleanup | 不自主推进 | 涉及 raw evidence，若清理或剪枝必须先做保存证明并按需人工批准。 |
| Layer A product boundary | 不由本轮处理 | 属于 Norven 保留产品决策。 |

Claude Code 与 Kimi 最终都建议选择 Prism report archive 迁移规划桥。这个结论不是说报告已经迁移，而是说下一步应该先把未来迁移计划写成可检查资产。

### 2.2 边界裁决

本轮不执行真实发布，不改许可证、registry、凭据或发布开关，也不读取 `.env`。本轮创建的 P4-12 也不允许删除、移动、复制或清理报告和 raw evidence；任何未来证据清理都必须单独证明并按需取得人工批准。

## 三、落地结果

### 3.1 当前效果

RedCap 的长期路线现在从“P4-10 后下一步未知”变成“下一步已由棱镜评审并登记为 P4-12”。这降低了任务漂移风险，也避免主线突然跳进更大的控制面批次、证据清理或人工产品决策。

### 3.2 已验证

- Claude Code 已完成独立评审，建议选择 Prism report archive 规划桥。
- Kimi 已完成独立评审，建议选择 Prism report archive 规划桥。
- Copilot 未调用，符合 protected fallback 策略。
- Gemini 未加入 quorum，原因是当前可用性清单显示它在本工作区不稳定；Claude Code 与 Kimi 已满足双视角评审。
- `references/r1-next-slice-after-prism-report-archive-preflight.json` 已记录候选矩阵、边界与下一切片。
- `references/backlogs/framework-upgrade.json` 已把 P4-11 标为完成，并登记 P4-12。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 / 文件 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| P4-11 | 本轮路线选择任务 | 只决定下一步做哪条小切片，不实现迁移。 |
| P4-12 | 下一条待执行任务 | 未来产出 Prism 报告归档迁移计划和验证/回滚清单。 |
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
| PM Gate | `bash compass/tools/redcap-pm-gate-check.sh strict codex .dev-task.md` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过 |
| backlog sync | `bash compass/tools/redcap-backlog-check.sh sync .dev-task.md` | 通过 |
| package surface | `bash compass/tools/redcap-public-package-surface.sh` | 通过，候选数 281 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh r1-prism-report-archive-copy-first-preflight-check` | 通过 |
| clean workspace E2E | `bash compass/tools/redcap-clean-workspace-e2e.sh --check-result` | 通过；正式写入版需提交后在 clean worktree 复跑 |
| full spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |

### 5.2 人工验证项

- 无。本轮不需要 Norven 做发布、许可证、registry、凭据、删除、清理或产品范围决策。

### 5.3 closeout runtime / receipt

| 项目 | 当前结果 |
| --- | --- |
| 执行承诺账本 | 待 closeout runtime 核对 |
| 棱镜验收 | Claude Code 与 Kimi 已返回，无 blocker |
| closeout receipt | 待生成 |

### 5.4 完成等级（禁止混报）

| 层级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 是 | P4-11 路线评审、Prism 报告、候选矩阵与 P4-12 后续锚点已落地。 |
| 已自检 | 是 | PM Gate、Prism acceptance、package surface、targeted acceptance、spec-check 与 diagnose 均已通过。 |
| 已独立验收 | 是 | Claude Code 与 Kimi 均选择 Prism report archive 规划桥，无 blocker。 |
| 已正式完成 | 待 closeout | closeout runtime 尚未生成 receipt。 |

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
| --- | --- | --- |
| Prism report archive 迁移规划 | 本轮只做路线选择，实施应进入 P4-12。 | P0-before-release |
| Prism report archive 物理迁移 | 规划完成前不能直接 apply。 | future-after-plan |
| Prism local run evidence cleanup | 涉及 raw evidence，不可顺手清理。 | manual-boundary-if-destructive |
| control-plane batch-2 / batch-3 | 规模更大，需要后续拆小。 | P0-before-release |
| Layer A 产品边界 | 需要 Norven 人工裁决。 | manual-boundary |

### 6.2 触发的新问题

- Kimi raw 输出中误把 JSON 的 `provider` 写成 `claude-code`。本轮已按调用路径和 `session-registry.yaml` 归一化为 Kimi 结论，并保留原始输出。这不是 blocker，但说明 Prism 报告里需要明确区分 raw 字段和运行注册事实。

### 6.3 推荐的下一步行动

1. 启动 P4-12：Prism report archive copy-first / alias-first migration planning。
2. 下一步继续保持 plan-only、非破坏性、可审计、可回滚节奏。

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
| --- | --- | --- |
| 无 | 无新增 lesson | 本轮没有发现新的通用工程陷阱；“raw 输出字段可能误填 provider，运行注册表才是 provider 真相源”已写入本报告，若后续重复出现再晋升为正式 lesson。 |

### 7.2 流程改进建议

路线选择任务完成时，必须明确区分“下一步已选定”和“下一步已实现”。否则长期 backlog 标记 done 后，容易被误读为 blocker 已关闭。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
| --- | --- | --- | --- |
| 先规划再迁移报告归档 | 本轮 P4-11 | no-promote；当前已进入 P4-12 任务边界，不需要单独晋升为公共经验 | 本报告与 `references/r1-next-slice-after-prism-report-archive-preflight.json` |

## 八、附录

### 附录 A：相关文档索引

- 当前任务卡：`.dev-task.md`
- 路线决策资产：`references/r1-next-slice-after-prism-report-archive-preflight.json`
- Prism review 报告：`prism/reports/2026-05-21-r1-next-slice-after-prism-report-archive-preflight.md`
- Prism 运行目录：`prism/runs/20260521-r1-next-slice-after-prism-report-archive-preflight/`
- 长期路线权威：`references/backlogs/framework-upgrade.json`

## 九、剩余边界

本轮不可声明：

- P4-12 已实现。
- Prism report archive 已物理迁移。
- `prism-layer-and-evidence` blocker 已关闭。
- `prism/runs` raw evidence 已清理。
- 旧 `prism/reports` 锚点已退休。
- Layer A 产品边界已裁决。
- RedCap 已 release-ready。

## 十、棱镜状态

Claude Code verdict：pass，推荐 Prism report archive 规划桥。Kimi verdict：pass-with-concerns，也推荐同一方向。两者形成 consensus-select-prism-report-archive-planning-bridge。Gemini 未加入 quorum，Copilot 按策略未调用。

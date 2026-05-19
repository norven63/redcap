# 任务完成报告：R1 控制面物理拆分干跑清单

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：`internal-control-plane` 的未来物理拆分已有 dry-run 地图，覆盖 `compass/**` 与 `references/**` 中当前 package-visible 的 184 个控制面候选。
- 详情：本轮只生成未来目标分层、别名/回滚计划和机器检查；没有移动、复制、删除或重命名任何 `compass` / `references` 文件。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2r 已把 `internal-layer-a / loom` 做成产品边界预检，并保留 Layer A 产品范围仍需未来裁决的事实。

### 0.3 下一步计划做的是

- 下一步计划做的是：继续处理 R1 中仍未解决的物理拆分 / 证据保留 / 产品范围裁决问题；正式 registry 发布、许可证和发布开关仍留到未来人工授权任务。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：正式发布准备路线 → R1 延期根目录分类 → 控制面契约拆分预检 → Prism 证据保留拆分预检 → Layer A 产品边界预检 → 控制面物理拆分 dry-run → 后续真实拆分 / 产品范围裁决 / 最终发布授权。
- 当前所在位置：`framework-upgrade / P4-2s`，处于 `internal-control-plane` 未来物理拆分的 dry-run 地图阶段。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮不触碰许可证、发布开关、registry 凭据、真实发布、目录物理迁移、Prism 证据清理或 Layer A 产品范围裁决。

## 一、需求背景

### 1.1 当前结论

R1 的 `internal-control-plane` blocker 已经有第一层契约预检，但那份预检只说明“为什么还阻塞、未来要满足哪些门禁”。本轮把它推进到下一层：为所有当前进入 package candidates 的 `compass/**` 与 `references/**` 控制面文件生成 dry-run 迁移地图，明确每类文件未来应该进入 runtime 支持层、内部控制面、公开契约、内部契约或人类发布 handoff。

本轮仍不解除 release blocker。它只是把未来真正拆分前最容易出错的“文件去哪里、谁会断、怎么回滚”提前变成机器可审计事实。

### 1.2 解决了什么问题

之前的风险是：`compass` 与 `references` 体量大、消费者多，如果直接进入物理迁移，很容易打断 revive/status/diagnose/closeout、发布安全检查、知识索引和 Prism acceptance。现在这些风险被拆成可验证问题：

- 当前到底有哪些 control-plane package candidates。
- 每个候选文件未来应该落到哪一层。
- 未来迁移时哪些消费者必须先有别名、wrapper、import map 或 resolver。
- 如果迁移失败，如何先恢复旧锚点和 package candidate 数量。

## 二、方案讨论

### 2.1 如何解决

本轮在 `references/r1-control-plane-contract-split-preflight.json` 中新增 dry-run manifest。它实时对齐 package manifest，将 184 个控制面候选分成五类：

- runtime public support：未来仍可能支撑外部用户首次安装、诊断和状态查看的工具。
- internal control-plane：维护者治理、validator、release-readiness 与任务控制工具。
- public contract：未来可被高级用户理解的公开契约与 handoff 文档。
- internal contract：维护者内部策略、治理门禁与发布前控制面事实。
- human handoff：面向人类的发布交接说明。

同时扩展 control-plane checker，让它拒绝：

- 缺失 dry-run manifest。
- dry-run 覆盖不完整或候选数量过期。
- 声称已经物理拆分、删除、复制或解除 blocker。
- 缺少目标分层、别名计划或回滚计划。

### 2.2 棱镜分歧与裁决

本轮先让 Claude Code 与 Kimi 做下一切片选择评审。Claude 建议先做 `internal-control-plane`，Kimi 建议先做 `prism-layer-and-evidence`。最终裁决选择 control-plane dry-run，原因是它是最大工程 blocker，且本轮只做地图和护栏，不做物理迁移；Kimi 对 Prism evidence 的风险提醒被写进漂移哨兵：不清理、不移动、不删除 Prism evidence。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 / 文件 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| control-plane | RedCap 的维护者控制面，包括检查器、策略、发布前门禁和任务治理工具 | 当前仍大量位于 `compass` / `references` |
| dry-run manifest | 只做模拟地图，不搬文件 | 告诉未来每个文件应该去哪一层 |
| alias / rollback plan | 未来迁移时的兼容入口与撤回办法 | 防止移动后旧路径断链或无法回滚 |
| package candidate | 未来 npm 包可能包含的文件 | 本轮用来确认控制面候选覆盖完整 |
| release blocker | 正式发布前必须解决或裁决的问题 | 本轮不解除 blocker，只让下一步更可执行 |

## 三、落地结果

### 3.1 当前效果

`internal-control-plane` 从“有拆分前置条件”升级为“有逐文件 dry-run 地图”。未来如果要真的移动 `compass` / `references`，不需要再凭感觉开刀，而是可以基于这份 manifest 做 copy-first、alias-first、verify、delete-last 的安全迁移。

### 3.2 已验证

- `bash compass/tools/redcap-r1-control-plane-contract-split-check.sh`
- targeted acceptance、spec-check、diagnose、clean workspace E2E 与 full acceptance 已通过。
- 全量 acceptance 曾抓到 backlog guide / docs catalog / legacy asset dry-run 快照联动过期；本轮已同步人类 backlog guide、刷新 catalog，并更新 legacy asset dry-run 行数快照后复验通过。

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
| --- | --- | --- | --- |
| 1 | 无需本轮人工审核 | 本轮不触碰真实发布、许可证、registry、目录迁移、证据删除或产品范围裁决。 | P1 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| 控制面 dry-run checker | `bash compass/tools/redcap-r1-control-plane-contract-split-check.sh` | 通过 |
| 发布计划检查 | `bash compass/tools/redcap-formal-release-readiness-plan-check.sh` | 通过 |
| 产品架构检查 | `bash compass/tools/redcap-pre-release-product-architecture-check.sh` | 通过 |
| docs catalog / reference lifecycle / cold archive | `redcap-docs-catalog.sh check` / `redcap-reference-asset-lifecycle.sh check` / `redcap-cold-archive-inventory.sh check` | 通过 |
| targeted acceptance | `r1-control-plane-contract-split-check` / `formal-release-readiness-plan-check` / `pre-release-product-architecture-check` / `on-stop-review-falls-back-after-timeout` | 通过 |
| clean workspace E2E | `bash compass/tools/redcap-clean-workspace-e2e.sh --write-result --result references/clean-workspace-install-e2e.json --timeout 180` | 通过，head=`21ab7f6`，package candidates=208 |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过，Claude Code + Kimi full-quorum |
| full acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无。本轮不要求 Norven 人工做产品、发布或删除决策。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
| --- | --- |
| 执行承诺账本 | 待 closeout runtime 最终核对 |
| 棱镜验收 | 通过，run=`20260519-r1-control-plane-physical-split-dry-run` |
| closeout summary | 待生成 |
| closeout receipt | 待生成 |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 层级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 是 | dry-run manifest、目标分层、别名/回滚计划、checker、acceptance、报告与 Prism report 已落地。 |
| 已自检 | 是 | targeted checks、spec-check、diagnose、clean workspace E2E 与 full acceptance 已通过。 |
| 已独立验收 | 是 | Claude Code 与 Kimi 完成 Prism 验收，无 blocker。 |
| 已正式完成 | 否 | closeout receipt 尚未生成。 |

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
| --- | --- | --- |
| 控制面真实物理拆分 | 需要独立 apply tranche，且必须 copy-first、alias-first、verify、delete-last。 | P0-before-release |
| Prism evidence 物理边界 | Kimi 提醒先稳证据层，本轮只记录风险，不处理证据。 | P0-before-release |
| Layer A 产品范围 | 需要 Norven 产品裁决。 | P0-before-release |

### 6.2 触发的新问题

无新增需要独立立项的问题。全量 acceptance 暴露的 backlog guide / docs catalog / legacy asset dry-run 快照联动过期已在本轮内修复并复验通过。

### 6.3 推荐的下一步行动

1. 完成本轮 closeout receipt。
2. 后续可选择：控制面真实 apply tranche，或 Prism evidence retention split dry-run / apply tranche。

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
| --- | --- | --- |
| 无新增 Lesson | 物理迁移前先做逐文件 dry-run | 本轮已将该经验固化到 R1 控制面检查器与 dry-run manifest。 |

### 7.2 流程改进建议

大规模目录迁移不要从 `mv` 开始，而要从 package-visible 候选、消费者矩阵、目标层、别名/回滚和 dry-run 覆盖开始。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
| --- | --- | --- | --- |
| 物理迁移前先做逐文件 dry-run | 本轮 control-plane blocker | no-promote-with-reason | 已固化到 `references/r1-control-plane-contract-split-preflight.json` 与 checker |

## 八、附录

### 附录 A：Commits

```
21ab7f6 feat(release): 增加 R1 控制面拆分干跑清单
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
| --- | --- | --- | --- |
| route-review | R1 下一工程切片选择 | Claude 建议 control-plane；Kimi 建议 Prism evidence；Cap 裁决先做 control-plane dry-run，并保留 no evidence cleanup 边界 | `prism/runs/20260519-r1-next-engineering-slice-selection/` |
| acceptance-review | P4-2s dry-run manifest 是否可接受 | Claude Code + Kimi full-quorum；无 blocker | `prism/runs/20260519-r1-control-plane-physical-split-dry-run/` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 预检真相源：`references/r1-control-plane-contract-split-preflight.json`
- 棱镜选择证据：`prism/runs/20260519-r1-next-engineering-slice-selection/`

## 九、剩余边界

本轮不解决 R1，也不发布 npm。仍不可声明：

- `compass` / `references` 已经物理拆分。
- `internal-control-plane` blocker 已解决。
- RedCap 已 public-release-ready。
- 可以进入真实 registry 发布。

## 十、棱镜状态

下一切片选择评审与正式验收 Prism acceptance 均已完成；无 blocker。

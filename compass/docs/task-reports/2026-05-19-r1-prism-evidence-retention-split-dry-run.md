# 任务完成报告：R1 Prism 证据保留拆分干跑清单

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：`prism-layer-and-evidence` 从“只有预检结论”推进到“有 dry-run 地图”的状态。
- 详情：本轮区分了可打包 Prism 支撑工具、源码审计报告归档、本地 raw run evidence、provider routing 规则四类资产；没有删除、移动或清理任何 Prism 证据，也没有关闭 release blocker。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2s 已把 `internal-control-plane` 的未来物理拆分做成 dry-run 地图，并修复了收口重验中的 zero-diff 报告锚点与自动补救并发堆叠缺口。

### 0.3 下一步计划做的是

- 下一步计划做的是：继续完成 P4-3e 的 clean workspace E2E 与 closeout receipt；之后再进入 Prism evidence apply tranche 或 control-plane physical apply tranche。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：正式发布准备路线 → R1 延期根目录分类 → 控制面契约拆分预检 → Prism 证据保留拆分预检 → Layer A 产品边界预检 → 控制面物理拆分 dry-run → Prism evidence dry-run → 后续真实拆分 / 产品范围裁决 / 最终发布授权。
- 当前所在位置：`framework-upgrade / P4-3e`，处于 `prism-layer-and-evidence` 未来拆分/清理的 dry-run 地图阶段。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮不触碰许可证、发布开关、registry 凭据、真实发布、Prism 证据删除、目录物理迁移或 Layer A 产品范围裁决。

## 一、需求背景

### 1.1 当前结论

`prism-layer-and-evidence` 原本只有 evidence-retention preflight：它说明 Prism 工具、报告和 raw evidence 为什么仍然是 release blocker，但还没有下一步执行地图。本轮把它推进到 dry-run：让 RedCap 知道哪些 Prism 文件可作为维护者支撑进入包面，哪些报告只属于源码审计归档，哪些 raw evidence 只属于本机运行证据。

### 1.2 解决了什么问题

之前的风险是：`prism/` 同时包含可执行工具、报告索引、正式评审摘要、raw run evidence 和 provider 调度策略。如果不拆清楚，未来 npm/CLI 发布前可能把“不该进包的证据”误当作工具，或把“只能预览的清理候选”误当成可以删除。

本轮把风险改成可检查问题：

- `prism/tools` 与 `prism/README.md` 是否仍是唯一 package-visible Prism 资产。
- `prism/reports` 与 `prism/runs` 是否仍保持 package candidate count 为 0。
- 清理候选是否只是 preview，不能执行 `--apply`。
- 后续真实拆分时哪些消费者必须先有别名、索引迁移或回滚计划。

## 二、方案讨论

### 2.1 如何解决

本轮在 `references/r1-prism-evidence-retention-split-preflight.json` 中新增 `evidence_split_dry_run_manifest`。它把 Prism 资产分成四层：

- package-visible Prism support：可随 alpha 包保留的 Prism 支撑工具与说明。
- tracked report archive：只作为源码审计摘要存在的 Prism 报告归档。
- local run evidence store：只留在本机、不得进包、不得默认读取的 raw run evidence。
- provider routing contract：影响棱镜调度独立性的 provider routing 规则。

同时扩展 checker，让它拒绝：

- 缺失 dry-run manifest。
- package-visible Prism 文件未被完整覆盖。
- `prism/reports` 或 `prism/runs` 进入包面。
- 错误允许 cleanup apply。
- 声称 Prism evidence 已清理或 blocker 已关闭。

### 2.2 棱镜分歧与裁决

下一步选择评审中出现分歧：

- Claude Code 建议优先推进 control-plane 真实物理拆分，因为 P4-2s 刚完成 control-plane dry-run。
- Kimi 建议先推进 Prism evidence，因为它风险更局部，更适合先跑通 release-blocker 的工程闭环。
- Gemini 本轮触发登录网页，不计入有效评审。

主执行裁决采纳 Kimi 的保守路线：先做 Prism evidence dry-run，不做 evidence 删除或目录移动。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 / 文件 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| Prism evidence | 棱镜评审留下的报告、索引、raw run 证据和 provider 调度信息 | 本轮要把它们分清层级 |
| dry-run manifest | 只做模拟地图，不搬文件、不删证据 | 告诉未来 Prism evidence 应该如何拆分 |
| package candidate | 未来 npm 包可能包含的文件 | 本轮确保只包含 Prism 工具和 README，不包含 raw evidence |
| cleanup preview | 只展示“未来可能清理什么”，不执行删除 | 防止 `prism/runs` 被误清理 |
| release blocker | 正式发布前必须解决或明确保留的问题 | 本轮不解除 blocker，只让下一步更可执行 |

## 三、落地结果

### 3.1 当前效果

`prism-layer-and-evidence` 现在已有 dry-run 地图和 no-apply 护栏。后续如果要真正迁移、归档或清理 Prism 证据，不再需要凭感觉开刀，而是必须先满足报告索引迁移、别名/回滚、archive check、clean workspace E2E 和 Prism review。

### 3.2 已验证

- `bash compass/tools/redcap-r1-prism-evidence-retention-split-check.sh`
- `bash compass/tools/redcap-multi-session-acceptance.sh r1-prism-evidence-retention-split-check`
- `bash prism/tools/prism-archive-check.sh --report prism/reports/2026-05-19-r1-next-release-blocker-selection-review.md`

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
| --- | --- | --- | --- |
| 1 | 无需本轮人工审核 | 本轮不触碰真实发布、许可证、registry、证据删除、目录迁移或产品范围裁决。 | P1 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| Prism evidence dry-run checker | `bash compass/tools/redcap-r1-prism-evidence-retention-split-check.sh` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh r1-prism-evidence-retention-split-check` | 通过 |
| release plan check | `bash compass/tools/redcap-formal-release-readiness-plan-check.sh` | 通过 |
| Prism route review archive check | `bash prism/tools/prism-archive-check.sh --report prism/reports/2026-05-19-r1-next-release-blocker-selection-review.md` | 通过 |
| Prism acceptance binding | `bash compass/tools/redcap-prism-acceptance-bind.sh --run-id 20260519-r1-prism-evidence-retention-split-dry-run --task-file .dev-task.md && bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过 |
| Prism implementation review archive check | `bash prism/tools/prism-archive-check.sh --report prism/reports/2026-05-19-r1-prism-evidence-retention-split-dry-run-review.md` | 通过 |
| Prism evidence check | `bash prism/tools/prism-evidence-check.sh` | 通过 |
| clean workspace E2E | `bash compass/tools/redcap-clean-workspace-e2e.sh --write-result --result references/clean-workspace-install-e2e.json --timeout 180` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无。本轮不要求 Norven 人工做产品、发布、许可证、registry 或删除决策。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
| --- | --- |
| 执行承诺账本 | 待 closeout 同步 |
| 棱镜验收 | 已通过：Claude Code 与 Kimi 均给出 `pass`，并已绑定到当前任务哈希 |
| closeout summary | 待生成 |
| closeout receipt | 待生成 |

### 5.4 完成等级（禁止混报）

| 层级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 已完成 | dry-run manifest、checker、targeted acceptance、任务报告已落地。 |
| 已自检 | 已通过 | targeted checks、spec-check、diagnose 与相关索引检查已通过。 |
| 已独立验收 | 已通过 | Claude Code 与 Kimi 均给出 `pass`；Gemini 本轮未调用且不影响 2-family quorum。 |
| 已正式完成 | 否 | closeout receipt 尚未生成。 |

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
| --- | --- | --- |
| Prism evidence 真实 apply / 清理 | 需要独立 apply tranche，且必须有明确 no-delete 或人工批准删除边界。 | P0-before-release |
| 控制面真实物理拆分 | 需要独立 apply tranche，且必须 copy-first、alias-first、verify、delete-last。 | P0-before-release |
| Layer A 产品范围 | 需要 Norven 产品裁决。 | P0-before-release |

### 6.2 触发的新问题

新增 task report 后，active task-report inbox 超过 12 份；本轮已按信息架构门禁要求，把最旧的一份任务报告迁入 `private-archive/redcap-knowledge/task-reports/`，避免默认任务报告入口继续膨胀。

### 6.3 推荐的下一步行动

1. 生成 closeout receipt。

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
| --- | --- | --- |
| 待定 | 证据清理前先把 preview 和 apply 物理隔离 | `prism/runs` 这类 raw evidence 可以预览清理候选，但真实 `--apply` 必须有人工批准、引用证明、回滚方案和 archive check。 |

### 7.2 流程改进建议

证据治理不要从“删除旧目录”开始，而要先把资产分成 package-visible 工具、源码报告归档、本地 raw evidence 和 provider routing contract。只有分层可验后，才允许讨论真实清理。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
| --- | --- | --- | --- |
| 证据清理前先把 preview 和 apply 物理隔离 | 本轮 Prism evidence dry-run | no-promote-with-reason；本轮已直接固化为 release-readiness 控制面规则和回归，不再单独进入 Evolution candidate 池 | 已固化到 `references/r1-prism-evidence-retention-split-preflight.json` 的 `cleanup_preview.apply_allowed_now=false` 与 acceptance 反例 |

## 八、附录

### 附录 A：Commits

```
ddc6a1c feat(release): 增加 Prism 证据保留拆分干跑清单
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
| --- | --- | --- | --- |
| route-review | P4-2s 后下一 release blocker 选择 | Claude 建议 control-plane；Kimi 建议 Prism evidence；Gemini 登录阻塞；Cap 裁决先做 Prism evidence dry-run | `prism/reports/2026-05-19-r1-next-release-blocker-selection-review.md` |
| formal-acceptance | P4-3e Prism evidence dry-run 实现是否安全可提交 | Claude Code 与 Kimi 均 `pass`；无 blocker；要求 closeout 前完成 receipt 和承诺账本核对 | `prism/reports/2026-05-19-r1-prism-evidence-retention-split-dry-run-review.md` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 预检真相源：`references/r1-prism-evidence-retention-split-preflight.json`
- 棱镜选择证据：`prism/runs/20260519-r1-next-release-blocker-selection/`

## 九、剩余边界

本轮不解决 R1，也不发布 npm。仍不可声明：

- Prism evidence 已经清理。
- `prism-layer-and-evidence` blocker 已解决。
- `internal-control-plane` blocker 已解决。
- RedCap 已 public-release-ready。
- 可以进入真实 registry 发布。

## 十、棱镜状态

下一步选择评审已完成；正式 Prism acceptance 已完成并通过。

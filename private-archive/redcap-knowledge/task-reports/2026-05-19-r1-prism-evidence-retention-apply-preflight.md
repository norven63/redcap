# 任务完成报告：R1 Prism 证据保留 apply 预检

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：`prism-layer-and-evidence` 从“只有 dry-run 地图”推进到“有 apply 前置护栏”的状态。
- 详情：本轮没有移动、删除、重命名、清理或替换任何 `prism/` 证据，也没有关闭 release blocker；只是把未来真正动手前必须满足的 copy-first、alias-first、证据保留、旧锚点保留、回滚和验收条件做成机器可检查清单。

### 0.2 上一步完成的是

- 上一步完成的是：P4-4 已把 `internal-control-plane` 推进到 apply preflight 状态，并完成 clean workspace E2E、Prism 复核和 closeout receipt。

### 0.3 下一步计划做的是

- 下一步计划做的是：P4-5 已正式收口后，继续沿正式发布 R1 路线处理仍开放的 blockers；真实 Prism evidence split / cleanup、control-plane batch apply、Layer A 产品范围、许可证和 registry 决策都仍是独立后续项。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：正式发布准备路线 → R1 延期根目录分类 → 控制面契约拆分预检 → Layer A / Prism 边界预检 → 控制面 dry-run 地图 → Prism evidence dry-run → 控制面 apply 预检 → Prism evidence apply 预检 → 后续真实 apply / 产品范围裁决 / 最终发布授权。
- 当前所在位置：`framework-upgrade / P4-5`，处于 `prism-layer-and-evidence` 未来 copy-first / alias-first apply 的前置护栏阶段。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮不触碰许可证、发布开关、registry 凭据、真实发布、证据物理迁移、证据清理、旧锚点删除或 Layer A 产品范围裁决。

## 一、需求背景

### 1.1 当前结论

P4-3e 已经证明：Prism 工具、报告和运行证据不能混在一个模糊的 `prism/` 概念里处理。它们分别承担 package-visible 支撑、provider routing contract、tracked report archive 和 local run evidence store 等职责。但 dry-run 地图只回答“哪些东西属于哪一层”，还没有回答“未来真正开始 apply 前，哪些动作是允许的、哪些动作必须禁止、旧证据路径怎么保留、失败后怎么回滚”。

本轮把这个缺口补成 apply preflight：未来如果要真正复制、建立别名、迁移报告索引或处理本地运行证据，必须先通过这组护栏；否则仍然不能进入发布动作或清理动作。

### 1.2 解决了什么问题

之前的风险是：有了 Prism evidence dry-run 后，后续任务可能误以为“可以直接清理 `prism/runs` 或迁移 `prism/reports`”。这会造成三类事故：

- raw evidence 被提前删除或 prune，导致历史 Prism 审计断链。
- 正式评审报告索引被移动但没有 alias / archive check，导致 receipt 和考古引用失效。
- apply 预检被误报成 physical split 或 blocker closure，导致 release readiness 被错误推进。

本轮把风险改成可检查问题：只允许未来规划安全动作，明确禁止 delete、move、rename、replace-old-anchor、cleanup-apply、prune-local-apply、public-publish 和 release-switch-change。

## 二、方案讨论

### 2.1 如何解决

本轮新增 `references/r1-prism-evidence-retention-apply-preflight.json`，并让它绑定 P4-3e 的 dry-run 真相源 hash、10 个 package-visible targets 和 2 个 source-evidence targets。这样后续如果 P4-3e 地图变化，本轮 apply 预检会因为 source hash 或 count stale 而失败，不会复用过期计划。

预检被拆成三批：

- package-visible Prism support：未来面向 runtime/package 的 Prism 支撑层，只能 copy-first / alias-first。
- report archive index migration：未来报告归档索引迁移必须先有 archive check、acceptance binding proof 和 Prism review。
- local run evidence store：`prism/runs` 仍是本地运行证据，任何 cleanup apply 都必须先证明 inactive、unreferenced，并获得显式批准。

### 2.2 棱镜分歧与裁决

P4-4 收口后的下一步选择已由 Claude Code 与 Kimi 共同评审。Claude Code 建议进入 control-plane batch-1 copy-first apply；Kimi 建议先做 Prism evidence apply preflight。裁决选择 Kimi 的更保守路线，因为本轮只补安全护栏，不进行真实文件复制或证据清理。

## 三、落地结果

### 3.1 当前效果

`prism-layer-and-evidence` 现在有了 apply 前置护栏：未来真实 apply 任务不能直接移动、删除或清理 Prism 证据，必须先证明 source map 未过期、旧锚点仍可访问、copy-first / alias-first 路线明确、报告索引和本地证据保留策略完整，并通过 clean workspace E2E 与 Prism review。

### 3.2 已验证

- `bash compass/tools/redcap-r1-prism-evidence-retention-apply-preflight-check.sh`
- `bash compass/tools/redcap-multi-session-acceptance.sh r1-prism-evidence-retention-apply-preflight-check`
- `bash compass/tools/redcap-formal-release-readiness-plan-check.sh`
- `bash compass/tools/redcap-file-lookup-dictionary-check.sh`
- `bash prism/tools/prism-archive-check.sh --report prism/reports/2026-05-19-r1-next-slice-after-control-plane-apply-preflight-review.md`
- `bash prism/tools/prism-archive-check.sh --report prism/reports/2026-05-19-r1-prism-evidence-retention-apply-preflight-review.md`
- `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md`

### 3.2.1 术语对照（按文件/功能解释）

| 术语 / 文件 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| apply preflight | 真正动手前的安全检查清单 | 规定未来怎么动手，哪些动作现在绝对不能做 |
| Prism evidence | 棱镜评审留下的报告、原始输出和运行证据 | 防止未来发布或清理时把审计证据误删 |
| copy-first | 先复制到新位置，旧位置继续可用 | 防止一上来移动文件导致历史引用断链 |
| alias-first | 先建立兼容入口或别名，再切换消费者 | 防止新旧路径并存期间工具找不到文件 |
| old anchor | 旧的 `prism/tools`、`prism/reports`、`prism/runs` 路径 | 本轮仍保留为权威证据位置，不能删除或替换 |
| source hash | 上游 dry-run 地图的指纹 | 防止拿过期地图继续推进后续任务 |
| blocker | 阻止正式发布的未解决问题 | 本轮只增加护栏，不关闭 `prism-layer-and-evidence` blocker |

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
| --- | --- | --- | --- |
| 1 | 无需本轮人工审核 | 本轮不执行真实发布、许可证选择、registry 操作、证据物理迁移、证据清理、旧锚点删除或 Layer A 产品裁决。 | P1 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| Prism evidence apply preflight checker | `bash compass/tools/redcap-r1-prism-evidence-retention-apply-preflight-check.sh` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh r1-prism-evidence-retention-apply-preflight-check` | 通过 |
| formal release plan check | `bash compass/tools/redcap-formal-release-readiness-plan-check.sh` | 通过 |
| file lookup dictionary check | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| route review archive check | `bash prism/tools/prism-archive-check.sh --report prism/reports/2026-05-19-r1-next-slice-after-control-plane-apply-preflight-review.md` | 通过 |
| implementation review archive check | `bash prism/tools/prism-archive-check.sh --report prism/reports/2026-05-19-r1-prism-evidence-retention-apply-preflight-review.md` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无。本轮不要求 Norven 做产品、发布、许可证、registry、删除或清理决策。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
| --- | --- |
| 执行承诺账本 | 9/9 已兑现 |
| 棱镜验收 | 已通过：Claude Code 与 Kimi 均给出 `pass`，并已绑定到当前任务哈希 |
| closeout summary | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/summaries/redcap-r1-prism-evidence-retention-apply-preflight-ebdafb53a4b40186ccb07f55fba3e85fc8a1b1789948cdede0d70478a93d320a.md` |
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-r1-prism-evidence-retention-apply-preflight-ebdafb53a4b40186ccb07f55fba3e85fc8a1b1789948cdede0d70478a93d320a.json` |

### 5.4 完成等级（禁止混报）

| 层级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 已完成 | apply preflight manifest、checker、targeted acceptance、release plan 接线、backlog 接线已落地。 |
| 已自检 | 已通过 | targeted checks、Prism acceptance、full spec-check、diagnose 与 clean workspace E2E 均已通过。 |
| 已独立验收 | 已通过 | Claude Code 与 Kimi 均无 blocker。 |
| 已正式完成 | 是 | closeout receipt 已生成，pending closure 已清零，承诺账本 9/9。 |

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
| --- | --- | --- |
| Prism evidence 真实 copy-first / alias-first apply | 本轮只做 apply 前置护栏，不复制、不移动、不删除旧锚点。 | P0-before-release |
| Prism evidence cleanup apply | 涉及 raw evidence 删除或 prune，必须先证明 inactive/unreferenced，并需要显式批准。 | P0-before-release |
| control-plane batch apply | Claude Code 建议的 batch-1 仍是后续较大切片，本轮不执行。 | P0-before-release |
| Layer A 产品范围 | 仍需要 Norven 产品裁决。 | P0-before-release |

### 6.2 触发的新问题

- 无新的 P0/P1 工程 blocker。
- Gemini 在路线评审阶段返回交互式登录提示，未形成有效 verdict；本轮 Prism quorum 由 Claude Code 与 Kimi 两个不同模型族满足。

### 6.3 推荐的下一步行动

1. 根据正式发布路线，选择下一个仍可自主推进的 release-readiness 小切片。
2. 如果触碰 Prism evidence cleanup、Layer A 产品边界、许可证、registry 或真实发布，必须进入人工决策点。

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
| --- | --- | --- |
| 待定 | 证据层 apply preflight 必须把“保留证据”和“清理证据”分成两件事 | Prism raw evidence、report archive 和 package-visible tools 不是同一类资产；apply preflight 必须先证明旧证据仍可访问，cleanup apply 必须另起任务并经过授权。 |

### 7.2 流程改进建议

以后类似“证据类目录治理”的任务都应分四段：先 dry-run map，再 apply preflight，再 copy-first / alias-first apply，最后才考虑 delete-last 或 cleanup apply。这样可以把“知道如何分层”和“允许清理证据”分开，避免发布前证据链被误删。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
| --- | --- | --- | --- |
| 证据层 apply preflight 必须把保留和清理分开 | 本轮 Prism evidence apply preflight | no-promote-with-reason；本轮已直接固化为 release-readiness 控制面规则和回归，不再单独进入 Evolution candidate 池 | `references/r1-prism-evidence-retention-apply-preflight.json` 与 acceptance 反例 |

## 八、附录

### 附录 A：Commits

```
fe9148d feat(release): 增加 Prism evidence apply 预检
487fcc8 test(release): 刷新 P4-5 clean workspace E2E
```

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
| --- | --- | --- | --- |
| route-review | P4-4 后下一 release blocker 切片选择 | Claude Code 建议 control-plane batch-1；Kimi 建议 Prism evidence apply preflight；Cap 采用更保守的小切片 | `prism/reports/2026-05-19-r1-next-slice-after-control-plane-apply-preflight-review.md` |
| formal-acceptance | P4-5 Prism evidence apply preflight 是否安全可提交 | Claude Code 与 Kimi 均 `pass`；无 P0/P1 blocker；要求 closeout 前完成报告、binding、clean E2E 与 receipt | `prism/reports/2026-05-19-r1-prism-evidence-retention-apply-preflight-review.md` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 预检真相源：`references/r1-prism-evidence-retention-apply-preflight.json`
- 上游 dry-run 地图：`references/r1-prism-evidence-retention-split-preflight.json`
- 下一步选择证据：`prism/runs/20260519-r1-next-slice-after-control-plane-apply-preflight/`
- 本轮验收证据：`prism/runs/20260519-r1-prism-evidence-retention-apply-preflight/`

## 九、剩余边界

本轮不解决 R1，也不发布包。仍不可声明：

- Prism evidence 已物理拆分。
- `prism/tools`、`prism/reports` 或 `prism/runs` 已迁移、删除、清理或替换。
- `prism-layer-and-evidence` blocker 已解决。
- RedCap 已 public-release-ready。
- 可以进入真实 registry publication。

## 十、棱镜状态

下一步选择评审已完成；正式 Prism acceptance 已完成并通过。

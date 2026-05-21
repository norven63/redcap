# 任务完成报告：R1 控制面物理拆分 apply 预检

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：`internal-control-plane` 从“有 dry-run 地图”推进到“有 apply 前置护栏”的状态。
- 详情：本轮没有复制、移动、删除或替换任何旧 `compass/` / `references/` 锚点，也没有关闭 release blocker；只是把未来真正动手前必须满足的 copy-first、alias-first、回滚和验收条件做成机器可检查清单。

### 0.2 上一步完成的是

- 上一步完成的是：P4-3e 已把 Prism 证据保留拆分推进到 dry-run / no-apply 状态，并完成 clean workspace E2E、Prism 复核和 closeout receipt。

### 0.3 下一步计划做的是

- 下一步计划做的是：P4-4 已正式收口；后续要根据正式发布路线决定是否进入 control-plane 真实 copy-first apply、Prism evidence apply，或等待 Layer A 产品范围裁决。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：正式发布准备路线 → R1 延期根目录分类 → 控制面契约拆分预检 → Layer A / Prism 边界预检 → 控制面 dry-run 地图 → Prism evidence dry-run → 控制面 apply 预检 → 后续真实 apply / 产品范围裁决 / 最终发布授权。
- 当前所在位置：`framework-upgrade / P4-4`，处于 `internal-control-plane` 未来 copy-first / alias-first apply 的前置护栏阶段。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮不触碰许可证、发布开关、registry 凭据、真实发布、目录物理迁移、旧锚点删除、Prism evidence 清理或 Layer A 产品范围裁决。

## 一、需求背景

### 1.1 当前结论

P4-2s 已经证明：`compass/` 和 `references/` 中存在一组 package-visible control-plane candidates，并给出未来拆分方向。本轮新增控制面 apply 预检支撑文件后，这组候选已同步为 187 个。但 dry-run 地图只回答“哪些东西可能要拆”，还没有回答“未来真正开始 apply 前，什么动作是允许的、什么动作必须禁止、旧路径怎么保留、失败怎么回滚”。

本轮把这个缺口补成 apply preflight：未来如果要真正复制控制面文件、建立别名或导入映射，必须先通过这组护栏；否则仍然不能进入发布动作。

### 1.2 解决了什么问题

之前的风险是：有了 dry-run 地图后，后续任务可能误以为“可以直接开始搬目录”。这会造成三类事故：

- 旧 `compass/` / `references/` 路径被提前移动或删除，破坏历史 receipt、脚本引用和考古锚点。
- copy-first / alias-first / wrapper / import-map 的顺序没有机器约束，真实 apply 变成凭感觉开刀。
- apply 预检被误报成 physical split 已完成，导致 release blocker 被错误关闭。

本轮把风险改成可检查问题：只允许未来规划安全动作，明确禁止 delete、move、rename、replace-old-anchor、prune、public-publish 和 release-switch-change。

## 二、方案讨论

### 2.1 如何解决

本轮新增 `references/r1-control-plane-physical-apply-preflight.json`，并让它绑定 P4-2s 的 dry-run 真相源 hash 和 187 个候选数量。这样后续如果 P4-2s 地图变化，本轮 apply 预检会因为 source hash stale 而失败，不会复用过期计划。

预检被拆成三批：

- runtime-public-support facades：未来面向运行时的公开支撑层，只能 copy-first / alias-first。
- policy-contract classification：未来契约和人类交接层，必须先有 import-map、file lookup aliases 和 token-risk audit。
- maintainer-control-plane tools：未来内部维护工具层，必须先有 validator / diagnose / spec-check / closeout 证明。

### 2.2 棱镜分歧与裁决

P4-3e 收口后的下一步选择已由 Claude Code 与 Kimi 共同评审。两者均建议优先推进 `control-plane-physical-apply-preflight`，因为它是当前剩余 blockers 中唯一不需要人工产品裁决、不会触碰发布凭据、也不会执行删除或真实迁移的纯工程切片。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 / 文件 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| apply preflight | 真正动手前的安全检查清单 | 规定未来可以怎样开始，哪些动作现在绝对不能做 |
| copy-first | 先复制新位置，旧位置继续可用 | 防止一移动就把历史引用和脚本打断 |
| alias-first | 先建立兼容入口或别名，再切换消费者 | 防止新旧路径交替期间断链 |
| old anchor | 旧的 `compass/` / `references/` 路径 | 本轮仍是权威路径，不能删除或替换 |
| source hash | 上游 dry-run 地图的指纹 | 防止使用过期拆分地图继续推进 |

## 三、落地结果

### 3.1 当前效果

`internal-control-plane` 现在有了 apply 前置护栏：未来真实 apply 任务不能直接移动或删除旧目录，必须先证明 source map 未过期、旧锚点仍可访问、copy-first / alias-first 路线明确、回滚条件完整，并通过 clean workspace E2E 与 Prism review。

### 3.2 已验证

- `bash compass/tools/redcap-r1-control-plane-physical-apply-preflight-check.sh`
- `bash compass/tools/redcap-multi-session-acceptance.sh r1-control-plane-physical-apply-preflight-check`
- `bash compass/tools/redcap-formal-release-readiness-plan-check.sh`
- `bash compass/tools/redcap-backlog-check.sh strict .dev-task.md`
- `bash compass/tools/redcap-spec-check.sh "$PWD"`
- `bash compass/tools/redcap-clean-workspace-e2e.sh --check-result`
- `bash compass/tools/redcap-diagnose.sh .dev-task.md`

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
| --- | --- | --- | --- |
| 1 | 无需本轮人工审核 | 本轮不执行真实发布、许可证选择、registry 操作、目录物理迁移、旧锚点删除或 Layer A 产品裁决。 | P1 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| control-plane apply preflight checker | `bash compass/tools/redcap-r1-control-plane-physical-apply-preflight-check.sh` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh r1-control-plane-physical-apply-preflight-check` | 通过 |
| formal release plan check | `bash compass/tools/redcap-formal-release-readiness-plan-check.sh` | 通过 |
| backlog strict | `bash compass/tools/redcap-backlog-check.sh strict .dev-task.md` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无。本轮不要求 Norven 做产品、发布、许可证、registry、删除或迁移决策。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
| --- | --- |
| 执行承诺账本 | 8/8 已兑现 |
| 棱镜验收 | 已通过：Claude Code 与 Kimi 均给出 `pass`，并已绑定到当前任务哈希 |
| closeout summary | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/summaries/redcap-r1-control-plane-physical-apply-preflight-2954936d6abb21687b3784ceeb35956e89759498d1d8c52967cedd6cf54536e3.md` |
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-r1-control-plane-physical-apply-preflight-2954936d6abb21687b3784ceeb35956e89759498d1d8c52967cedd6cf54536e3.json` |

### 5.4 完成等级（禁止混报）

| 层级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 已完成 | apply preflight manifest、checker、targeted acceptance、release plan 接线、backlog 接线已落地。 |
| 已自检 | 已通过 | targeted checks、spec-check、diagnose、clean workspace E2E、backlog strict 均已通过。 |
| 已独立验收 | 已通过 | Claude Code 与 Kimi 均无 blocker；clean workspace E2E 已刷新。 |
| 已正式完成 | 是 | closeout receipt 已生成，pending closure 已清零，承诺账本 8/8。 |

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
| --- | --- | --- |
| control-plane 真实 copy-first apply | 本轮只做 apply 前置护栏，不复制、不移动、不删除旧锚点。 | P0-before-release |
| Prism evidence 真实 apply / 清理 | 需要独立 apply tranche，且必须有 no-delete 边界或人工批准。 | P0-before-release |
| Layer A 产品范围 | 仍需要 Norven 产品裁决。 | P0-before-release |

### 6.2 触发的新问题

- 收口时发现 `.dev-task.md` 的 `baseline_head` 使用了错误的完整 SHA，导致 commit proof 和 artifact lifecycle 无法解析基线；已修正为真实提交 `678c6ad1b66205d4b54f4ec1037715c8a7b0eb51`。
- 收口时发现允许修改范围漏登记部分派生清单与归档清单，导致 drift-check 阻断；已补齐范围并重新通过 closeout。

### 6.3 推荐的下一步行动

1. 根据正式发布路线，选择下一个仍可自主推进的 release-readiness 切片。
2. 如果进入真实 apply，必须继续保持 copy-first / alias-first，不允许直接删除或替换旧锚点。
3. 如果触碰 Prism evidence apply、Layer A 产品边界、许可证、registry 或真实发布，必须进入人工决策点。

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
| --- | --- | --- |
| 待定 | dry-run 之后必须先补 apply preflight，不能直接真实迁移 | 当目录治理进入真实 apply 前，先把 copy-first、alias-first、旧锚点保留、回滚和禁止动作做成机器检查，避免把 dry-run 地图误当成迁移授权。 |

### 7.2 流程改进建议

以后类似“从地图到动手”的任务都应分三段：先 dry-run map，再 apply preflight，最后才是小批量 copy-first apply。这样可以把“知道要改哪里”和“允许动手改”分开，避免发布前结构治理变成大爆炸迁移。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
| --- | --- | --- | --- |
| dry-run 之后必须先补 apply preflight | 本轮 control-plane apply preflight | no-promote-with-reason；本轮已直接固化为 release-readiness 控制面规则和回归，不再单独进入 Evolution candidate 池 | `references/r1-control-plane-physical-apply-preflight.json` 与 acceptance 反例 |

## 八、附录

### 附录 A：Commits

```
4760509 feat(release): 增加控制面 apply 预检
012092f test(release): 刷新 P4-4 clean workspace E2E
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
| --- | --- | --- | --- |
| route-review | P4-3e 后下一 release blocker 切片选择 | Claude Code 与 Kimi 均建议优先推进 control-plane physical apply preflight | `prism/reports/2026-05-19-r1-next-slice-after-prism-dry-run-review.md` |
| formal-acceptance | P4-4 control-plane apply preflight 是否安全可提交 | Claude Code 与 Kimi 均 `pass`；无 P0/P1 blocker；要求 closeout 前刷新 clean workspace E2E 并生成 receipt | `prism/reports/2026-05-19-r1-control-plane-physical-apply-preflight-review.md` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 预检真相源：`references/r1-control-plane-physical-apply-preflight.json`
- 上游 dry-run 地图：`references/r1-control-plane-contract-split-preflight.json`
- 下一步选择证据：`prism/runs/20260519-r1-next-slice-after-prism-dry-run/`

## 九、剩余边界

本轮不解决 R1，也不发布 npm。仍不可声明：

- control-plane 已物理拆分。
- `compass/` 或 `references/` 旧锚点已迁移、删除或替换。
- `internal-control-plane` blocker 已解决。
- RedCap 已 public-release-ready。
- 可以进入真实 registry 发布。

## 十、棱镜状态

下一步选择评审已完成；正式 Prism acceptance 已完成并通过。

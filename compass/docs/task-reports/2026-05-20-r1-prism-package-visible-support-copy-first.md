# 任务完成报告：R1 Prism package-visible support 小切片

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-8 已为 Prism 的 package-visible support 与 provider-routing contract 建立 8 个 runtime facade。
- 人话解释：未来包面和 CLI 可以从 `runtime/redcap-core/prism-tools` 找到 Prism 支撑入口，但真正逻辑仍委托旧 `prism/*` 锚点，避免一次性搬动证据层。

### 0.2 上一步完成的是

- 上一步完成的是：P4-7 路线选择。Claude Code 与 Kimi 评审后，选择 P4-8 这个更小、更安全的 Prism 小切片，而不是直接进入更大的控制面 batch-2。

### 0.3 下一步计划做的是

- 下一步计划做的是：继续按 R1 blocker 小切片推进；Prism report archive、local run evidence、control-plane batch-2 或 Layer A 产品边界都必须另开任务、单独评审，不能直接进入正式发布动作。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：正式发布准备路线 → R1 延期根目录分类 → 控制面与 Prism 预检 → 控制面 runtime facade → P4-7 选择下一小切片 → **P4-8 Prism package-visible support facade** → 后续 Prism report archive / local run evidence / 控制面 batch-2 / Layer A 人工边界。
- 当前所在位置：`framework-upgrade / P4-8`，属于 release-readiness 前的非破坏性支撑实现，不是正式发布。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触碰许可证、registry、凭据、发布开关、旧锚点删除、Prism evidence cleanup 或 Layer A 产品范围裁决。

## 一、需求背景

Prism 相关资产之前混在 `prism/tools`、`prism/reports`、`prism/runs` 中。正式发布前，RedCap 需要把“可被包面看见的运行支撑入口”和“本地证据/历史运行记录”逐步分开。

但直接搬动 `prism/*` 风险很高：会破坏旧报告、运行证据、Provider 路由和考古锚点。所以 P4-8 只做最安全的一步：先新增 runtime facade，让新入口存在，同时保留旧锚点权威性。

## 二、方案讨论

### 2.1 如何解决

本轮从既有 Prism apply preflight 里精确取出 batch-1 的 8 个候选：5 个 package-visible support，3 个 provider-routing contract。实现方式是 copy-first / alias-first：新增入口，但不移动旧入口。

这相当于先架桥，不拆旧桥。新桥能让未来包面、CLI 和 runtime 路径逐渐稳定；旧桥继续保证历史证据和旧调用不被打断。

### 2.2 边界裁决

本轮严格禁止把 facade 说成物理拆分，也禁止把 provider review 说成全局 provider 重构。Copilot 仍是 protected fallback，只能在 Claude Code 与 Kimi 都不可用时降级；Codex CLI 仍是 last-resort。

Kimi 在评审时质疑过一个 coverage 统计项，复核后确认不是缺陷：该统计包含 package-visible targets 和 source-evidence targets 的合计，现有 apply-preflight checker 已经会重算并校验。

## 三、落地结果

### 3.1 当前效果

现在 RedCap 多了一个更清晰的 Prism 运行支撑层：包面能看到 `runtime/redcap-core/prism-tools`，但旧 `prism/*` 仍是权威来源。

这一步减少了未来 CLI/package 化时的路径混乱，也为后续真正拆分 Prism report archive 与 local run evidence 提供了安全过渡点。

### 3.2 已验证

- 8 个 runtime facade 已创建并通过语法检查。
- `bin/redcap prism-availability` 已通过 runtime facade 路径转调。
- import-map 已记录 Prism support contract。
- 包候选数量从 264 增加到 272，增长只来自 8 个 facade。
- `.env`、identity、飞书配置、Prism raw evidence、私有知识和本机路径仍不进入包面。
- Claude Code 与 Kimi 已完成独立评审；Copilot 未调用，符合 protected fallback 策略。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| facade | 新入口的薄包装 | 让 runtime/package 可以找到 Prism 支撑入口，但不复制旧逻辑 |
| old anchor | 旧路径和旧证据锚点 | 本轮必须保留，避免破坏历史考古和旧调用 |
| provider routing | 调用哪个 Agent/CLI 的策略 | 保证优先用 Claude Code/Kimi，保护 Copilot 配额 |
| package surface | 未来 npm 包里可能包含的文件集合 | 证明新增内容可解释、无私密泄漏 |
| release blocker | 阻止正式发布的未解问题 | 本轮没有关闭整个 blocker，只削减其中一小段 |

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
| --- | --- | --- | --- |
| 1 | 无需本轮人工审核 | 本轮没有命中 Norven 保留决策。 | P1 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 当前结果 |
| --- | --- | --- |
| P4-8 专项检查 | `bash compass/tools/redcap-r1-prism-package-visible-support-copy-first-apply-check.sh` | 通过 |
| Prism apply preflight | `bash compass/tools/redcap-r1-prism-evidence-retention-apply-preflight-check.sh` | 通过 |
| package manifest dry-run | `bash compass/tools/redcap-runtime-package-manifest.sh --check --npm-pack-dry-run` | 通过 |
| package publish safety | `bash compass/tools/redcap-package-publish-safety-check.sh` | 通过 |
| public package surface | `bash compass/tools/redcap-public-package-surface.sh` | 通过 |
| runtime contract surface | `bash compass/tools/redcap-runtime-contract-surface-check.sh` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh r1-prism-package-visible-support-copy-first-apply-check` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过 |

### 5.2 人工验证项

- 无。本轮不需要 Norven 选择许可证、发布目标、registry、凭据、删除策略或 Layer A 产品边界。

### 5.3 closeout runtime / receipt

| 项目 | 当前结果 |
| --- | --- |
| 执行承诺账本 | 已由 closeout runtime 核对通过，8 项承诺无 pending |
| 棱镜验收 | Claude Code 与 Kimi 已完成；acceptance binding 已生成 |
| closeout receipt | 已生成：`/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-r1-prism-package-visible-support-copy-first-a2d45b90c5ccdc4ce67f1ebfd9b09c0ab6d217eb7799f4d3389f4a1972e61949.json` |

### 5.4 完成等级（禁止混报）

| 层级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 是 | 8 个 Prism runtime facade 与 provider-routing contract proof 已落地。 |
| 已自检 | 是 | 专项检查、包面检查、full acceptance、spec-check、diagnose 与 clean workspace E2E 均已通过。 |
| 已独立验收 | 是 | Claude Code 与 Kimi 均无 blocker。 |
| 已正式完成 | 是 | 功能提交、clean workspace E2E 刷新提交与 closeout receipt 均已完成。 |

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
| --- | --- | --- |
| Prism report archive migration | 不是 batch-1 范围，需要独立任务避免动到历史报告锚点。 | P0-before-release |
| local run evidence cleanup | 涉及证据清理和潜在历史损失，必须单独证明并按需取得人工批准。 | manual-boundary-if-destructive |
| control-plane batch-2 | 候选数量更大，适合后续拆小批次推进。 | P0-before-release |
| Layer A 产品边界 | 是否纳入公开产品范围属于 Norven 保留决策。 | manual-boundary |

### 6.2 触发的新问题

- 无新增 blocker。Kimi 的 coverage 疑问已由现有 checker 复核为非缺陷。

### 6.3 推荐的下一步行动

1. 进入 P4-9 路线选择，从剩余 R1 blocker 中选择下一条小切片。
2. 后续仍优先保持“非破坏性、可回归、可棱镜验收”的节奏。

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
| --- | --- | --- |
| 无 | 无新增 lesson | 本轮没有发现新的通用工程陷阱；“先架桥、不拆旧桥”已是当前 copy-first 策略的一部分。 |

### 7.2 流程改进建议

当 reviewer 质疑统计口径时，不要立刻修改清单；先查机器 checker 的真实定义。若 checker 已覆盖该口径，应把质疑记录为已复核风险，而不是引入无意义改动。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
| --- | --- | --- | --- |
| Prism facade copy-first 小切片 | 本轮 P4-8 | no-promote；属于既有 copy-first / alias-first 策略复用，不新增独立经验 | 本报告与 Prism review 报告 |

## 八、附录

### 附录 A：相关文档索引

- 当前任务卡：`.dev-task.md`
- 实施清单：`references/r1-prism-package-visible-support-copy-first-apply.json`
- Prism review 报告：`prism/reports/2026-05-20-r1-prism-package-visible-support-copy-first-review.md`
- Prism 运行目录：`prism/runs/20260520-r1-prism-package-visible-support-copy-first/`
- P4-7 路线报告：`private-archive/redcap-knowledge/task-reports/2026-05-20-r1-next-slice-after-runtime-facade.md`

## 九、剩余边界

本轮不可声明：

- Prism layer 已物理拆分。
- Prism report archive 已迁移。
- local run evidence 已清理。
- 旧 `prism/*` 锚点已退休。
- `prism-layer-and-evidence` blocker 已关闭。
- RedCap 已 public-release-ready。
- 可以进入真实 registry release action。

## 十、棱镜状态

Claude Code verdict：pass。Kimi verdict：pass-with-notes。两者均无 blocker，形成 consensus-pass-with-notes。Gemini 未调用，Copilot 按策略未调用。

## 十一、旁路归档说明

本轮新增 P4-8 任务报告后，活跃 task-report 区触发机器上限：最多 12 个，实际 13 个。为保持首读区健康，已将旧报告 `compass/docs/task-reports/2026-05-18-r1-control-plane-contract-split-preflight.md` 迁入 `private-archive/redcap-knowledge/task-reports/2026-05-18-r1-control-plane-contract-split-preflight.md`，并同步长期 backlog 证据路径。

这不是 P4-8 的功能目标，也没有删除历史证据；它只是把低频考古材料移出活跃首读区，避免 task-report 区再次膨胀。

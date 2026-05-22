# 任务完成报告：R1 Layer A 产品边界预检

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：R1 的 `internal-layer-a` blocker 已被拆成可机器检查的“Layer A 产品边界预检”，但它仍然阻塞正式发布。
- 详情：本轮证明 `loom` 当前不进入 npm/package 候选面，并记录了 `loom/dispatcher`、`loom/roles`、`loom/tools`、`loom/test-reports`、`loom/fixtures` 的职责、消费者和未来决策门禁。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2q 已把 `prism-layer-and-evidence` 做成证据保留拆分预检，并保留 R1 仍未关闭的事实。

### 0.3 下一步计划做的是

- 下一步计划做的是：继续处理 R1 中仍未解决的物理拆分 / 产品范围裁决问题；正式 registry 发布、许可证和发布开关仍留到未来人工授权任务。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：正式发布准备路线 → R1 延期根目录分类 → 控制面契约拆分预检 → Prism 证据保留拆分预检 → Layer A 产品边界预检 → 剩余物理拆分 / 产品范围裁决 / 最终发布授权。
- 当前所在位置：`framework-upgrade / P4-2r`，处于 `internal-layer-a` 产品边界预检完成点。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮只做预检、检查器、账本、报告、Prism 复核和回归，不触碰许可证、发布开关、registry 凭据、真实发布、`loom` 物理迁移或 Layer A 产品范围裁决。

## 一、需求背景

### 1.1 当前结论

本轮任务把正式发布 R1 中仍未专项化的 `internal-layer-a` blocker 拆成了可机器检查的边界预检。现在 RedCap 能明确证明：`loom` 当前不进入 npm/package 候选面，但这只能说明“不会误打包”，不能替代 Norven 对 Layer A 是否作为公开产品、内部兼容层、退休资产或私有考古资产的最终裁决。

本轮没有执行真实发布，没有移动、删除或重命名 `loom`，没有修改 Layer A 运行逻辑，也没有把 Layer A 声称为已公开纳入、已退休或 release-ready。

### 1.2 解决了什么问题

之前 R1 已有 `internal-control-plane` 和 `prism-layer-and-evidence` 两条专项预检，但 `internal-layer-a` 仍停留在总矩阵里的粗粒度 blocker 描述。这会导致一个发布前风险：包面虽然没有包含 `loom`，但系统没有足够证据说明 `loom` 的职责、消费者、未来纳入或排除条件，也容易把“暂时不进包”误读为“产品边界已经裁决”。

本轮把这个风险拆成四个可验证问题：

- `loom` 现在到底包含哪些资产，是否进入包候选。
- 哪些现有脚本、文档和边界检查仍引用 Layer A / `loom`。
- 未来若要公开纳入、排除、退休或物理迁移 Layer A，需要哪些前置门禁。
- 发布计划和总校验链能否阻止把预检冒充最终产品决策。

## 二、方案讨论

### 2.1 如何解决

新增的 Layer A product boundary preflight 记录了 `loom/dispatcher`、`loom/roles`、`loom/tools`、`loom/test-reports`、`loom/fixtures` 五类资产的职责边界，并把消费者矩阵覆盖到 Layer A 状态机、角色手册、hooks/tools、E2E 队列、人类文档和 Layer B fallback 检查。

新增检查器会实时重新计算 package candidates 和 `loom` 文件清单，拒绝以下错误状态：

- 声称 Layer A 已公开纳入或已退休。
- 声称 `loom` 已物理迁移。
- 声称 `internal-layer-a` 已不再阻塞 R1。
- 缺失消费者矩阵、未来决策门禁或包面/文件清单证据。

发布准备计划也已把该预检列为 required source，因此正式发布路线不能跳过 Layer A 边界问题。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 / 文件 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| `loom` | Layer A 旧 Dispatcher 工作流资产所在目录 | 当前证明它不进包，但不替用户裁决它未来是否公开 |
| product boundary preflight | 产品边界预检 | 先把事实、风险、消费者和未来门禁写清，不做最终产品决策 |
| package candidate | 未来 npm 包可能包含的文件 | 用来证明 `loom` 当前不会被误打包 |
| consumer matrix | 消费者矩阵 | 说明哪些脚本、文档或流程仍依赖 `loom`，防止未来移动时断链 |
| future decision gate | 未来决策门禁 | 说明纳入、排除、退休或迁移 Layer A 前必须满足哪些条件 |

## 三、落地结果

### 3.1 当前效果

`internal-layer-a` 的状态从“只有粗粒度 blocker 描述”升级为“有可复验的 product-boundary preflight”。这让正式发布前的下一步更清楚：要么未来由 Norven 明确裁决 Layer A 是否进入公开产品；要么另开边界解决任务，完成兼容测试、host-entry review、包面安全、clean workspace E2E、Prism review 和 closeout receipt。

同时，pre-release 架构评审已从“只剩 license / publish switch 两个发布 blocker”的旧说法修正为：除了人工发布决策，R1 仍有 `internal-control-plane`、`prism-layer-and-evidence`、`internal-layer-a` 三条边界 blocker。

### 3.2 已验证

- `bash compass/tools/redcap-r1-layera-product-boundary-check.sh`
- `bash compass/tools/redcap-formal-release-readiness-plan-check.sh`
- `bash compass/tools/redcap-multi-session-acceptance.sh r1-layera-product-boundary-check`
- `bash compass/tools/redcap-multi-session-acceptance.sh formal-release-readiness-plan-check`
- `bash compass/tools/redcap-multi-session-acceptance.sh pre-release-product-architecture-check`
- `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures`
- `bash compass/tools/redcap-spec-check.sh "$PWD"`

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
| --- | --- | --- | --- |
| 1 | 无需本轮人工审核 | 本轮不触碰发布、许可证、registry、`loom` 迁移或 Layer A 产品范围裁决；这些仍是未来任务的人类边界。 | P1 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| Layer A 边界预检 | `bash compass/tools/redcap-r1-layera-product-boundary-check.sh` | 通过 |
| 发布计划接线 | `bash compass/tools/redcap-formal-release-readiness-plan-check.sh` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh r1-layera-product-boundary-check` | 通过 |
| Prism / report / docs 回归 | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| 全量 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无。本轮不要求 Norven 人工选择 Layer A 产品范围。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
| --- | --- |
| 执行承诺账本 | 已清 |
| 棱镜验收 | 通过 |
| closeout summary | 待 closeout runtime 生成 |
| closeout receipt | 待 closeout runtime 生成 |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 层级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 是 | P4-2r 的预检 JSON、checker、formal release plan 接线、acceptance、报告与 Prism report 已落地。 |
| 已自检 | 是 | targeted acceptance、spec-check propagation、file lookup、human output、information architecture 等检查已执行或纳入回归。 |
| 已独立验收 | 是 | Claude Code 与 Kimi 完成 Prism 复核，无 blocker。 |
| 已正式完成 | 否 | closeout receipt 尚未生成；生成 receipt 后才允许改为正式完成。 |

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
| --- | --- | --- |
| Layer A 是否进入公开产品 | 这是 Norven 保留产品范围裁决，本轮只能做 preflight。 | P0-before-release |
| `loom` 是否迁移、退休或归档 | 需要未来产品范围裁决、兼容测试、别名和 rollback 方案。 | P0-before-release |

### 6.2 触发的新问题

无新增需要独立立项的问题；Claude Code 提出的 acceptance sad-path 与 catalog 摘要空缺已在本轮修复。

### 6.3 推荐的下一步行动

1. 继续处理 R1 中仍未解决的物理拆分 / 产品范围裁决问题。
2. 在正式发布任务前，保持许可证、发布开关和 registry 凭据为人工决策边界。

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
| --- | --- | --- |
| 无新增 Lesson | 包面缺席不等于产品裁决 | 本轮已直接固化到可执行 preflight 与 checker，不另写 lesson。 |

### 7.2 流程改进建议

同类 R1 blocker 以后应优先做 preflight：先证明边界、消费者和 future gate，再决定是否进入物理迁移或产品范围裁决。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
| --- | --- | --- | --- |
| 无新增候选 | Prism verdict / release blocker | no-promote-with-reason | `references/r1-layera-product-boundary-preflight.json` |

## 八、附录

### 附录 A：Commits

```
待提交
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
| --- | --- | --- | --- |
| review | P4-2r 是否保持 Layer A 产品边界预检 | 无 blocker，pass-with-concerns；concerns 已处理或纳入 closeout | `prism/reports/2026-05-19-r1-layera-product-boundary-preflight-review.md` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 预检真相源：`references/r1-layera-product-boundary-preflight.json`
- 棱镜报告：`prism/reports/2026-05-19-r1-layera-product-boundary-preflight-review.md`

## 九、剩余边界

本轮不解决 R1，也不发布 npm。仍不可声明：

- Layer A 已属于公开 RedCap 产品。
- Layer A 已退休、删除或迁移。
- `loom` 已经被物理归位。
- R1 已关闭或 RedCap 已 public-release-ready。

正式发布前仍需要处理或裁决三条 R1 blocker：`internal-control-plane`、`prism-layer-and-evidence`、`internal-layer-a`。

## 十、棱镜状态

Prism 复核已完成，Claude Code 与 Kimi 均无 blocker。Claude Code 提出的 acceptance sad-path 与 catalog 摘要问题已在本轮修复；Kimi 提醒的 report、binding、完成勾选与 Evolution harvest 会在 closeout 流程中继续收口。

- Prism report: `prism/reports/2026-05-19-r1-layera-product-boundary-preflight-review.md`
- Prism run: `prism/runs/20260519-r1-layera-product-boundary-preflight/`

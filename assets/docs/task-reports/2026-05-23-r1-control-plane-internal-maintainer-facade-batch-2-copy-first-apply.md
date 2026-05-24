# 任务完成报告：P4-23 internal-control-plane 第二小批次 facade 实施

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-23 已实施第二个 internal-control-plane 维护工具 facade 小批次，新增 8 个兼容入口。
- 详情：这些新入口不复制业务逻辑，只把调用转给旧 `compass/tools` 脚本。这样做的效果是继续把维护者控制面从旧目录向更清晰的 internal/control-plane 结构过渡，同时避免破坏旧锚点或误报发布准备完成。

### 0.2 上一步完成的是

- 上一步完成的是：P4-22 已经通过 Claude Code 与 Kimi 评审，选择“继续 internal-control-plane 小批次 facade”作为下一条安全切片。

### 0.3 下一步计划做的是

- 下一步计划做的是：P4-24 重新做下一安全切片选择，判断是继续 internal-control-plane 小批次，还是转向 Prism 报告入口、contract mirror 等其他发布前治理方向。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-21 完成第一批 facade → P4-22 选择继续小批次 → P4-23 完成第二批 facade → P4-24 再次选择下一条安全切片。
- 当前所在位置：P4-23 已完成工程实施，RedCap 仍处于正式发布前治理阶段，不是正式发布阶段。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触碰发布、许可证、registry、凭据、私密文件、破坏性删除、raw evidence 清理或 Layer A 产品边界。下一步如果仍只是路线评审或非破坏性小切片，可由 Cap 和棱镜继续推进。

## 一、需求背景

P4-22 已经选定“继续 internal-control-plane 小批次 facade”路线。用户同时明确指出，RedCap 不应在没有人工硬门时反复等待“好的，继续”这种机械确认。

本轮因此要完成两件事：第一，真正实施第二个小批次；第二，继续证明自动续跑不会变成无脑扩大范围。

## 二、方案讨论

Claude Code 与 Kimi 均审查了 8 个候选脚本。它们都来自现有 dry-run 清单，数量与 P4-21 相同，属于维护、检查、索引或发布前预检入口。

评审结论是可以实施，但必须保留旧 `compass/tools` 权威；新增入口只能是 thin facade，不能复制或改写旧逻辑。

## 三、落地结果

本轮新增了 8 个 internal-control-plane facade。它们的共同行为是：先定位 RedCap 根目录，再检查旧脚本是否存在，最后 `exec bash` 调用旧脚本。

这让目录结构朝“维护者内部控制面”继续收敛，但没有改变运行语义，也没有关闭任何正式发布 blocker。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| thin facade | 薄薄的一层兼容入口，不实现业务逻辑 | 让新目录可调用旧权威脚本 |
| old anchor | 旧的 `compass/tools` 脚本路径 | 本轮继续保留为真实权威 |
| release blocker | 阻止正式发布的结构、安全或体验问题 | 本轮保持 open，不能误报关闭 |
| parent-autocontinue | 父任务线自动续跑规则 | 当前无人工硬门，所以 P4-23 自动接上 |

## 四、人工审核要点

本轮不需要 Norven 人工介入。需要避免的误读是：P4-23 只完成第二个小批次 facade，不代表 internal-control-plane 已完全解决，也不代表 RedCap 可以正式发布。

## 五、验证结果

| 验证项 | 结果 | 说明 |
| --- | --- | --- |
| Prism acceptance | 已绑定 | Claude Code 与 Kimi 均建议实施提议批次 |
| P4-23 manifest | 已生成 | 记录 8 个新增 facade、禁止声明和仍 open 的 blocker |
| P4-23 checker | 已生成 | 验证批次不重叠、旧锚点保留、禁止发布/删除/证据清理 |
| backlog 同步 | 已完成 | P4-23 标记 done，P4-24 登记 pending |

### 5.3 closeout runtime / receipt

| 项目 | 当前值 |
| --- | --- |
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-r1-control-plane-internal-maintainer-facade-batch-2-copy-first-apply-7772beb8c2a35a513e09a49aa8f8d5ad49a16a6ba081145876089c7970c1c596.json` |
| 当前状态 | 已完成正式 closeout 收口 |
| 人工介入 | 不需要 |

### 5.4 完成等级（禁止混报）

| 等级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 是 | 8 个 facade、manifest、checker、Prism 报告和 backlog 更新已落地 |
| 已自检 | 是 | 专项 checker 已通过 |
| 已独立验收 | 是 | Claude Code 与 Kimi 两路评审已绑定 |
| 已正式完成 | 是 | closeout runtime 已生成 receipt |

## 六、遗留问题与下一步

P4-24 是下一条任务：重新选择 P4-23 之后的下一条 release-readiness 安全切片。

只要 P4-24 不触碰发布、删除、证据清理、凭据或 Layer A 产品裁决，RedCap 应继续自动续跑。

## 七、经验沉淀

本轮经验是：自动续跑不是把任务“一口气做到底”，而是在每个小切片收口后用父任务线和棱镜重新确认下一步是否安全。这样可以减少机械等待，同时避免长任务失控扩大。

### 7.3 Evolution Factory 候选处理

本轮命中了高价值沉淀信号，因为它再次验证了“parent-autocontinue + Prism + 小批次边界”的组合。

处理结论：no-promote。

原因：经验已经被当前任务卡、P4-23 manifest、P4-24 backlog 和 closeout runtime 承接；暂不新增独立 Evolution 候选，避免把局部执行策略过早提升为通用技能。

## 八、附录

- 任务卡：`.dev-task.md`
- P4-23 manifest：`references/r1-control-plane-internal-maintainer-facade-batch-2-copy-first-apply.json`
- P4-23 checker：`compass/tools/redcap-r1-control-plane-internal-maintainer-facade-batch-2-copy-first-apply-check.sh`
- Prism 报告：`prism/reports/2026-05-23-r1-control-plane-internal-maintainer-facade-batch-2-copy-first-apply.md`

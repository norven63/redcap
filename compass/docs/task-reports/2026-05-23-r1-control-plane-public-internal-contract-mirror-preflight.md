# 任务完成报告：P4-25 控制面 public/internal contract mirror 预检

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-25 已完成 internal-control-plane 的 public/internal contract mirror preflight。
- 详情：本轮把 225 条控制面候选按未来边界分成公开合同、内部合同、运行时公开支撑、维护控制面和人工交接面，并建立了机器检查。它没有实施合同镜像，也没有移动或删除旧锚点。

### 0.2 上一步完成的是

- 上一步完成的是：P4-24 已完成路线裁决，选择 P4-25 作为下一条安全切片。

### 0.3 下一步计划做的是

- 下一步计划做的是：P4-26 只做“P4-25 后下一安全切片选择”。它可以继续自动推进，但不能直接跳进物理迁移、删除、发布或 Layer A 产品裁决。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-21 第一批 facade → P4-22 选继续 → P4-23 第二批 facade → P4-24 选 contract preflight → P4-25 完成合同镜像预检 → P4-26 选择下一安全切片。
- 当前所在位置：RedCap 仍处于正式发布前治理阶段，不是正式发布阶段。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触碰发布、许可证、registry、凭据、私密文件、破坏性删除、raw evidence 清理或 Layer A 产品边界。

## 一、需求背景

P4-24 选择了 contract mirror preflight。这个任务的目的不是搬目录，而是先把未来哪些内容属于公开合同、哪些属于内部合同、哪些只是运行时支撑或维护控制面说清楚。这样后续如果真的要迁移，就不会靠猜测移动文件。

## 二、方案讨论

Claude Code 认为 P4-25 可自主完成，交付物应包括 preflight manifest、checker、Prism 证据、spec-check、diagnose、clean workspace E2E 和 receipt。

Kimi 抓到一个关键误报风险：不能因为已有 dry-run map 或 apply-preflight 文件，就声称物理实施已经解锁。P4-25 只能完成预检，不能自动升级成 physical apply。

Cap 采纳合并方案：本轮做完预检；下一步只自动进入路线选择，不直接进入迁移。

## 三、落地结果

本轮完成了三件事：

- 把 225 条控制面候选归纳成 5 类边界：运行时公开支撑、公开合同、内部合同、人工交接面、维护控制面。
- 建立机器检查，确保分层计数、目标前缀、消费者绑定、禁止声明和 release blocker 状态不会漂移。
- 把“自动续跑”的边界写清楚：可以自动进入下一条路线选择，不能自动进入物理迁移。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| contract mirror preflight | 先把未来公开/内部边界列清楚，但不搬文件 | P4-25 的核心交付 |
| public contract | 将来可能面向普通安装用户的规则或说明 | 本轮识别为 11 项 |
| internal contract | 维护者和发布治理用的内部规则 | 本轮识别为 55 项 |
| runtime-public-support | CLI 能跑起来需要的公开支撑能力 | 本轮识别为 47 项 |
| internal-control-plane | 维护者内部工具，不是稳定公开 API | 本轮识别为 111 项 |

## 四、人工审核要点

本轮不需要 Norven 人工介入。需要避免的误读是：P4-25 完成不等于控制面已经物理拆分，也不等于 release blocker 已解决。

## 五、验证结果

| 验证项 | 结果 | 说明 |
| --- | --- | --- |
| Prism acceptance | 已绑定 | Claude Code 与 Kimi 双路评审 |
| P4-25 manifest | 已生成 | 记录分层、边界和自动续跑限制 |
| P4-25 checker | 已生成 | 证明本轮只做预检，不实施迁移 |
| backlog 同步 | 已完成 | P4-25 标记 done，P4-26 登记 pending |

### 5.3 closeout runtime / receipt

| 项目 | 当前值 |
| --- | --- |
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-r1-control-plane-public-internal-contract-mirror-preflight-0c91526732ba37084e4bc7c9497ed8c4e43e22c74d0c8c083bbc8487588a9f65.json` |
| 当前状态 | 已完成正式 closeout 收口 |
| 人工介入 | 不需要 |

### 5.4 完成等级（禁止混报）

| 等级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 是 | preflight manifest、checker、Prism 报告和 backlog 更新已落地 |
| 已自检 | 是 | 专项 checker、spec-check、diagnose、包面安全和 clean workspace E2E 已通过 |
| 已独立验收 | 是 | Claude Code 与 Kimi 两路评审已绑定 |
| 已正式完成 | 是 | closeout runtime 已生成 receipt |

## 六、遗留问题与下一步

P4-26 是下一条任务：P4-25 后下一安全切片选择。

P4-26 可以自动推进，但只能先做路线选择。若下一步试图进入真实迁移、发布、删除、凭据处理、raw evidence cleanup 或 Layer A 产品裁决，才需要人工硬门。

## 七、经验沉淀

本轮经验是：自动续跑不等于自动升级风险等级。预检任务完成后，可以自动进入下一次路线选择，但不能自动跳到物理实施。

### 7.3 Evolution Factory 候选处理

本轮命中了高价值沉淀信号，因为它把“机械续接”和“风险升级”分开了。

处理结论：no-promote。

原因：当前先由 P4-25 manifest、P4-26 backlog 和 closeout runtime 承接；暂不新增独立 Evolution 候选。

## 八、附录

- 任务卡：`.dev-task.md`
- P4-25 manifest：`references/r1-control-plane-public-internal-contract-mirror-preflight.json`
- P4-25 checker：`compass/tools/redcap-r1-control-plane-public-internal-contract-mirror-preflight-check.sh`
- Prism 报告：`prism/reports/2026-05-23-r1-control-plane-public-internal-contract-mirror-preflight.md`

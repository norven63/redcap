# 任务完成报告：P4-21 internal-control-plane 小批次镜像

## 0.1 当前已完成

- 当前已完成：P4-21 已完成一小批 internal-control-plane 维护工具镜像。RedCap 新增了 8 个内部维护入口，它们只把调用转交给旧的权威脚本，不改变旧位置、不删除旧资产，也不宣称发布 blocker 已关闭。

## 0.2 上一步完成的是

- 上一步完成的是：P4-20 已选择下一条安全路线，结论是先回到 internal-control-plane，用小批次、可回滚、非破坏的方式继续拆正式发布前的结构风险。

## 0.3 下一步计划做的是

- 下一步计划做的是：P4-22 将重新比较下一条安全切片，判断是继续扩大 internal-control-plane 镜像、推进 public/internal contract mirror，还是先补旧报告入口别名或查询网关。

## 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-18 处理发布前旧资产预检，P4-19 处理旧报告入口，P4-20 选择下一条安全切片，P4-21 完成 internal-control-plane 小批次镜像，P4-22 再选择下一条安全切片。
- 当前所在位置：P4-21 已完成实现、棱镜评审和主要机器验收，正在进入正式 closeout 收口；RedCap 仍处于发布前治理阶段，不是 npm 正式发布阶段。

## 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触碰发布、许可证、registry、凭据、私密文件、破坏性删除、raw evidence 清理或 Layer A 产品边界；因此应由 RedCap 自动续跑到 closeout，而不是等待机械的“继续”。

## 1. 这次解决什么问题

P4-20 已经选定下一条路线：回到 internal-control-plane，继续拆正式发布前的大 blocker。这个区域有 111 个候选条目，不能一次性搬迁，也不能在没有证据的情况下说它已经解决。

本轮只解决一件小而关键的事：先做一批可回滚的镜像入口，证明 RedCap 可以在不破坏旧锚点的前提下，把内部控制面的工具逐步迁到更清晰的位置。

## 2. 如何解决问题

新增的 8 个入口都放在 `internal/control-plane/tools/`。它们本身不重新实现业务逻辑，只把执行转交给旧的 `compass/tools/` 权威脚本。

这让新目录结构开始具备真实可执行入口，同时旧位置仍然保持稳定。换句话说，本轮是“先复制入口、保留旧权威、证明可验收”，不是“搬家完成”。

本轮覆盖的入口包括：

- `redcap-agent-health-probe.sh`
- `redcap-architecture-smell-governance-check.sh`
- `redcap-arsenal-version-binding-check.sh`
- `redcap-change-intake-check.sh`
- `redcap-conclusion-prism-check.sh`
- `redcap-detect-agents.sh`
- `redcap-dev-task.sh`
- `redcap-drift-check.sh`

## 3. 评审与验收

Claude Code 和 Kimi 都参与了棱镜评审。两个审查视角一致建议选择“小批次 internal-control-plane 维护工具 facade”路线，并且明确要求不要批量处理 111 个候选、不要删除旧锚点、不要越过发布和证据清理边界。

机器验收也围绕这个边界执行：P4-21 专项 checker 证明本轮只新增小批次镜像；Prism acceptance 证明独立评审证据已绑定；包公开面检查证明这些内部治理文件没有被误纳入当前公开包候选面。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| facade | 一个很薄的入口脚本，自己不做业务，只转交给旧权威脚本 | 让新目录可以先跑起来，同时不破坏旧位置 |
| internal/control-plane/tools | RedCap 内部控制面维护工具的新候选位置 | 本轮先放入 8 个镜像入口，作为小批次试点 |
| release blocker | 阻止正式发布的结构、安全或体验问题 | 本轮只降低风险，不宣称 blocker 已全部关闭 |
| post-freeze report | 冻结规则后新增的 Prism 审查报告 | 本轮新增评审报告并同步到报告归档治理清单 |

## 4. 解决后的效果

RedCap 现在有了第一批 internal-control-plane copy-first 镜像证据。后续可以沿着这条路线继续拆分，但每一步都仍需机器检查和棱镜评审。

可以对外表达的是：P4-21 已完成一小批内部控制面 facade 支撑。

不能表达的是：internal-control-plane 已经整体解决、RedCap 已经可以正式公开发布、旧 `compass/tools` 可以删除、Prism 报告或 raw evidence 可以清理。

## 5. 完成状态

### 5.1 已完成的验证

| 验证项 | 结果 | 说明 |
| --- | --- | --- |
| P4-21 专项 checker | 已通过 | 证明本轮是小批次、非破坏、非发布切片 |
| Prism acceptance | 已通过 | Claude Code 与 Kimi 均无 blocker |
| 根目录信息架构检查 | 已通过 | 新 `internal/` 根目录已登记为内部控制面候选区 |
| 文件查阅字典检查 | 已通过 | 新入口和新证据已进入可检索索引 |
| 公开包面检查 | 已通过 | 本轮内部治理文件未扩大公开包候选面 |

### 5.2 本轮明确没有做的事

- 没有批量镜像全部 111 个 internal-control-plane 条目。
- 没有删除、移动、重命名、替换或 symlink 切换旧 `compass/tools`。
- 没有清理 `prism/runs` raw evidence。
- 没有修改 npm 发布开关、许可证、registry 或凭据。
- 没有触碰 Layer A 产品边界。

### 5.3 closeout runtime / receipt

| 项目 | 当前值 |
| --- | --- |
| closeout receipt | 无 |
| 当前状态 | 正在执行正式 closeout 收口前验证 |
| 人工介入 | 不需要 |

### 5.4 完成等级（禁止混报）

| 等级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 是 | 8 个内部维护 facade、manifest、checker 和报告索引已落地 |
| 已自检 | 是 | 专项 checker、包面、字典和目录结构检查已通过 |
| 已独立验收 | 是 | Claude Code 与 Kimi 的 Prism acceptance 已绑定 |
| 已正式完成 | 否 | 等待 closeout runtime 生成 receipt 后才能声明正式完成 |

## 6. 下一步

P4-22 已登记为下一条任务：在 P4-21 小批次完成后，重新选择下一条安全切片。

只要没有命中发布、删除、证据清理或 Layer A 产品裁决等人工硬门，RedCap 应继续自动续跑，而不是停下来等待机械的“继续”。

## 7.3 Evolution Factory 候选处理

本轮命中了高价值沉淀信号，因为它同时涉及发布前结构治理、棱镜评审、closeout 收口和回归验收。

处理结论：no-promote。

原因：这次经验仍然是 P4-21 具体实施过程的一部分，最有价值的规则已经由现有门禁承接，包括小批次 copy-first、旧锚点保留、公开包面不扩大、以及无人工硬门时自动续跑。当前不新增独立 Evolution 候选，避免把一次局部执行经验过早提升为通用规则。

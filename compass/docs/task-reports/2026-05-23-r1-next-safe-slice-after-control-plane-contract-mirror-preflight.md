# 任务完成报告：P4-26 P4-25 后下一安全切片选择

**报告日期**：2026-05-23
**执行者**：Cap（Codex 主执行，Claude Code + Kimi 棱镜评审）
**报告版本**：v1.0

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-26 已完成下一安全切片选择。
- 详情：本轮解决的是“P4-25 完成合同镜像预检后，下一步该做哪一刀”。Claude Code 和 Kimi 独立评审后形成共识：下一步应登记 P4-27，但 P4-26 本身只做路线裁决，不实施迁移、不关闭 release blocker。

### 0.2 上一步完成的是

- 上一步完成的是：P4-25 已完成 internal-control-plane 的 public/internal contract mirror preflight，也就是把未来公开给用户看的规则与内部维护规则先分清楚。

### 0.3 下一步计划做的是

- 下一步计划做的是：P4-27 只做“小范围合同镜像 apply 预检”。它可以继续自动推进，但不能直接跳进物理迁移、删除、发布、raw evidence cleanup 或 Layer A 产品裁决。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-21 第一批 facade → P4-22 选继续 → P4-23 第二批 facade → P4-24 选 contract preflight → P4-25 完成合同镜像预检 → P4-26 选择下一安全切片 → P4-27 小范围 apply 预检。
- 当前所在位置：RedCap 仍处于正式发布前治理阶段，不是正式发布阶段。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触碰发布、许可证、registry、凭据、私密文件、破坏性删除、raw evidence 清理或 Layer A 产品边界；下一步 P4-27 仍可由 Cap 与棱镜继续自动推进。

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “就是现在的状态是，你总是中途停顿下来，需要我人工机械的回复“好的，请你们继续”，但其实这根本不需要中断，完全可以由你和棱镜自动续上。并且，我经常会不在电脑旁，导致无法及时响应来回复这段机械的指令，你就会等很久才会继续推进，极大的延缓了项目推进速度”

### 1.2 触发背景

P4-25 已经收口，但父任务线仍有 P4-26/P4-27 这类非人工硬门的后续任务。如果每完成一个子任务都停下来等待 Norven 机械回复“继续”，RedCap 的父任务自动续跑规则就没有发挥作用。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | route-only |
| 原始意图 | 无人工硬门时自动续上父任务线，不再等待机械“继续”。 |
| 已覆盖 | 自动进入 P4-26，完成下一安全切片选择，并登记 P4-27。 |
| 未覆盖/延期 | P4-26 不实施 P4-27；P4-27 由后续任务继续。 |
| 用户可见边界 | 只能说“P4-26 选出了下一刀”，不能说“已经完成迁移”或“release blocker 已关闭”。 |
| 后续路径 | P4-27 小范围 public/internal contract apply preflight。 |

## 二、方案讨论

### 2.1 问题分析

P4-26 的关键不是“多做一点”，而是避免越权：P4-25 之后可以继续收窄合同镜像范围，但不能跳过预检直接进入真实迁移或发布动作。因此本轮需要棱镜先评估下一安全切片，再把边界写入可机器复验的路线裁决。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | A | 选择 P4-27 小范围合同镜像 apply 预检 | 承接 P4-25，风险可控，不触碰人工硬门 | 仍不能关闭 release blocker |
| Q1 | B | 直接进入更大范围物理迁移 | 推进速度快 | 风险高，越过预检边界 |
| Q1 | C | 暂停等待 Norven 回复继续 | 最保守 | 与父任务自动续跑规则冲突，拖慢长任务 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | A | Claude Code 与 Kimi 都支持先做小范围 apply 预检；它能继续推进，又不会触碰发布、删除、凭据或产品边界。 | Prism + Cap |

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `references/r1-next-safe-slice-after-control-plane-contract-mirror-preflight.json` | 新建 | 记录 P4-26 路线裁决、边界和下一条 P4-27。 |
| `compass/tools/redcap-r1-next-safe-slice-after-control-plane-contract-mirror-preflight-check.*` | 新建 | 证明 P4-26 只做路线选择，不实施下一切片。 |
| `references/backlogs/framework-upgrade.json` | 修改 | P4-26 标记 done，P4-27 登记 pending。 |
| `prism/reports/2026-05-23-r1-next-safe-slice-after-control-plane-contract-mirror-preflight.md` | 新建 | 记录 Claude Code 与 Kimi 的独立评审。 |
| `compass/tools/*previous-slice*check.py` | 修改 | 让旧 checker 支持 P4-26 已完成、P4-27 已 pending 的前进状态。 |

### 3.2 技术实现要点

本轮把“自动续跑”落成了一个受限的路线裁决：父任务线可以继续，但下一步只能是预检，不能借自动续跑绕过人工硬门。为避免旧检查器把世界冻结在“P4-26 pending”，同步修正了若干历史 checker，使它们允许任务线自然前进到 P4-27。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| 下一安全切片 | `references/r1-next-safe-slice-after-control-plane-contract-mirror-preflight.json` | 下一步最小、可验证、不会越过人工硬门的工作包。 |
| apply preflight | P4-27 任务类型 | 真正动手前，先验证范围、风险、回滚和验收条件。 |
| public/internal contract | P4-25/P4-26 路线 | 把对外公开规则和内部维护规则分清楚，防止未来发布面混乱。 |
| release blocker | 发布前阻塞项 | 正式发布前必须解决或明确豁免的问题；本轮没有关闭它。 |
| raw evidence cleanup | Prism 原始证据清理 | 高风险动作，需要 Norven 明确批准，本轮不碰。 |

### 3.3 关联变更

为了让全量回归通过，本轮还更新了索引、冷归档清单、包公开面排除规则和 Prism 报告归档索引。这些是证据链随 P4-26 新增文件产生的联动更新，不改变任务边界。

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无 | 本轮不需要 Norven 人工决策；下一步 P4-27 仍是预检类任务，可自动推进。 | P2 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过 |
| P4-26 checker | `bash compass/tools/redcap-r1-next-safe-slice-after-control-plane-contract-mirror-preflight-check.sh` | 通过 |
| 报告质量 | `bash compass/tools/redcap-human-output-quality-check.sh` | 通过 |
| 文件字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| 包公开面 | `bash compass/tools/redcap-public-package-surface.sh` | 通过 |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已清 |
| 棱镜验收 | 通过 |
| closeout summary | 待 closeout runtime 生成 |
| closeout receipt | 待 closeout runtime 生成 |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Claude Code 与 Kimi 已形成棱镜共识 |
| 已正式完成 | 否，receipt 待生成 |

## 六、遗留问题与下一步

P4-27 是下一条任务：小范围 public/internal contract apply preflight。

P4-27 可以自动推进，但只能先做预检。若下一步试图进入真实迁移、发布、删除、凭据处理、raw evidence cleanup 或 Layer A 产品裁决，才需要人工硬门。

## 七、经验沉淀

本轮是路线裁决，结论为无新增候选（no-promote）。

原因：当前先由 P4-26 manifest、P4-27 backlog 和 closeout runtime 承接；暂不新增独立 Evolution 候选。若 P4-27 的 apply 预检发现可复用的方法论，再由 Evolution/Forge 另行候选化。

### 7.3 Evolution Factory 候选处理

| 项目 | 结论 |
| --- | --- |
| 是否形成新候选 | 否，no-promote |
| 原因 | 本轮是发布前路线裁决，核心知识已经由 P4-26 manifest、Prism 报告和 backlog 承接 |
| 后续动作 | 若 P4-27 的 apply 预检发现可复用的方法论，再由 Evolution/Forge 另行候选化 |

## 八、附录

- P4-26 manifest：`references/r1-next-safe-slice-after-control-plane-contract-mirror-preflight.json`
- P4-26 checker：`compass/tools/redcap-r1-next-safe-slice-after-control-plane-contract-mirror-preflight-check.sh`
- Prism 报告：`prism/reports/2026-05-23-r1-next-safe-slice-after-control-plane-contract-mirror-preflight.md`

# 任务完成报告：P4-28 P4-27 后下一安全切片路线选择

**报告日期**：2026-05-23
**执行者**：Cap（Codex + Claude Code / Kimi 棱镜评审）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-28 已完成路线选择，决定把 P4-29 登记为下一条安全切片；本轮不实施 P4-29。
- 详情：P4-28 没有创建 `contracts/**` 文件，也没有复制、移动、删除、替换旧锚点。它只是把“下一刀”确定为一个后续的 bounded copy-first apply 任务：只复制 P4-27 已预检的 7 个 contract 文件，并继续保留旧 `references/**` 锚点。

### 0.2 上一步完成的是

- 上一步完成的是：P4-27 完成 7 条 public/internal contract 的小范围 apply 预检。P4-27 没有实施迁移，只证明未来可以安全地讨论这 7 个文件的 copy-first apply。

### 0.3 下一步计划做的是

- 下一步计划做的是：P4-29 执行一个独立的 bounded copy-first apply 任务。它必须单独立项、单独评审、单独验证，且只能创建 7 个目标副本；不得删除旧锚点、发布、清理 raw evidence、关闭 release blocker 或裁决 Layer A 产品边界。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-25 合同分类预检 → P4-26 选择下一刀 → P4-27 小范围 apply 预检 → P4-28 再次选择下一刀 → P4-29 后续 copy-first apply。
- 当前所在位置：P4-28 已完成，长期路线焦点已推进到 P4-29。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮只做路线选择，没有触碰发布、许可证、registry、凭据、真实删除、raw evidence cleanup 或 Layer A 产品边界。P4-29 若后续执行，也仍然是非破坏性的 copy-first 任务；只有出现删除、发布、凭据、许可证、证据清理或产品裁决时才需要 Norven 决策。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “就是现在的状态是，你总是中途停顿下来，需要我人工机械的回复“好的，请你们继续”，但其实这根本不需要中断，完全可以由你和棱镜自动续上。并且，我经常会不在电脑旁，导致无法及时响应来回复这段机械的指令，你就会等很久才会继续推进，极大的延缓了项目推进速度”

### 1.2 触发背景

P4-27 closeout 后，父任务线已经明确给出 `PARENT_AUTOCONTINUE_OK`：下一步是 P4-28。
因此本轮不应该停下来等 Norven 机械回复“继续”，而应该在没有人工硬门的前提下自动进入 P4-28。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 用户要求 RedCap 在无人工硬门时自动续上父任务线，不再等待机械“继续”。 |
| 已覆盖 | 已从 P4-27 自动续入 P4-28，并完成下一安全切片选择、棱镜评审、状态面推进。 |
| 未覆盖/延期 | P4-29 的真实 copy-first apply、删除旧锚点、raw evidence cleanup、正式发布、凭据/许可证/registry、Layer A 产品裁决均继续延期到独立任务或人工硬门。 |
| 用户可见边界 | 只能说“P4-28 选出下一安全切片”，不能说“P4-29 已实施”或“RedCap 已可正式发布”。 |
| 后续路径 | P4-29 后续可在不跨人工硬门时继续自动推进；只有命中人工硬门才停止。 |

---

## 二、方案讨论

### 2.1 问题分析

P4-28 的核心风险是“把选路误说成执行”。如果 P4-28 一边说路线选择、一边创建 `contracts/**`，就会绕过 P4-29 的独立评审和验证。因此本轮只允许登记下一任务，不允许执行下一任务。

### 2.2 方案选项

| 选项 | 描述 | 结论 |
|---|---|---|
| A | 登记 P4-29 为 7 个 contract 文件的 bounded copy-first apply | 采纳 |
| B | 重复或扩大 P4-27 预检 | 不采纳，收益低 |
| C | 回到 Prism evidence/report 路线 | 不采纳，当前合同镜像链路更直接 |
| D | 清理 Prism raw evidence | 不采纳，人工硬门 |
| E | 裁决 Layer A 产品边界 | 不采纳，人工硬门 |
| F | 进入正式发布 | 不采纳，人工硬门且仍有 blocker |
| G | 停下来问 Norven | 不采纳，当前不存在缺失的人工事实 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---|---|---|
| Q1 | A：登记 P4-29 bounded copy-first apply | 承接 P4-27 的预检成果，同时不跨真实迁移、删除、发布、证据清理和产品裁决硬门。 | CAP_DECIDE + Prism REVIEW |

---

## 三、落地结果

### 3.1 本轮完成了什么

本轮把 P4-28 落成一份机器可审计的路线选择：下一步可以是 P4-29，但 P4-29 必须作为独立任务执行。这样既不会让父任务线卡在“等你说继续”，也不会让自动续跑越权跨过人工硬门。

### 3.2 解决后的效果

- 父任务线从 P4-28 推进到 P4-29。
- Claude Code 与 Kimi 都同意选择路线 A。
- Copilot 没有被调用。
- 没有创建 `contracts/**` 文件。
- 没有删除、移动、替换旧锚点。
- 没有关闭任何 release blocker。
- 没有改变发布、凭据、许可证、registry 或 package privacy。

### 3.2.1 术语对照（按文件/功能解释）

| 文件/功能 | 术语 | 人话解释 |
|---|---|---|
| 本轮 P4-28 任务 | route selection | 只决定下一步做什么，不执行下一步。 |
| 后续 P4-29 任务 | bounded copy-first apply | 后续只创建明确范围内的新副本，旧文件继续保留。 |
| `references/**` | old anchor | 旧路径上的权威文件，例如当前的 `references/**`。 |
| RedCap 工作流 | human hard gate | 必须 Norven 决策的动作，比如发布、许可证、凭据、删除、证据清理或产品范围。 |

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|---|---|---|---|
| 1 | 无必须人工审核项 | 本轮未触碰发布、凭据、许可证、真实删除、raw evidence cleanup 或产品裁决。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| P4-28 自检 | `bash compass/tools/redcap-r1-next-safe-slice-after-contract-mirror-apply-preflight-subset-check.sh` | 通过 |
| 文件查阅索引 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| 包发布安全 | `bash compass/tools/redcap-package-publish-safety-check.sh` | 通过 |
| runtime 包面清单 | `bash compass/tools/redcap-runtime-package-manifest.sh --check` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过 |
| 人类可读报告质量 | `python3 compass/tools/redcap-human-output-quality-check.py --report compass/docs/task-reports/2026-05-23-r1-next-safe-slice-after-contract-mirror-apply-preflight-subset.md` | 通过 |
| 全量规范检查 | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| 深入诊断 | `bash compass/tools/redcap-diagnose.sh` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 无。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| 执行承诺账本 | 待 closeout runtime 核对 |
| 棱镜验收 | 待 acceptance binding |
| closeout summary | 待生成 |
| closeout receipt | 待生成 |
| rescue audit（如有） | 待确认 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Claude Code / Kimi 共识 |
| 已正式完成 | 待 closeout receipt |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|---|---|---|
| P4-29 copy-first apply | 这是下一独立任务，不能由 P4-28 直接实施。 | P0 |
| release blocker 关闭 | 仍需更多证据，P4-28 不能关闭。 | P0 |
| 正式 npm 发布 | 仍涉及许可证、registry、凭据和发布授权硬门。 | P0 |

### 6.2 触发的新问题

无新增问题。

### 6.3 推荐的下一步行动

1. 收口 P4-28 并生成 receipt。
2. 若 P4-29 仍未命中人工硬门，则自动进入 P4-29 的独立任务卡与评审。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|---|---|---|
| 无 | 无新增候选 | 本轮属于既有“路线选择不能冒充实施”的模式复用，不需要新增 lesson。 |

### 7.2 流程改进建议

继续强化 parent-autocontinue：无人工硬门时，下一安全切片应自动续跑，不应等待 Norven 机械回复“继续”。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|---|---|---|---|
| 无新增候选 | P4-28 路线选择 | no-promote | `prism/reports/2026-05-23-r1-next-safe-slice-after-contract-mirror-apply-preflight-subset.md` |

---

## 八、附录

### 附录 A：Commits

```text
待提交
```

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|---|---|---|---|
| review | P4-28 是否可选择 P4-29 | Claude Code / Kimi 共识选择 A，未跨人工硬门 | `prism/reports/2026-05-23-r1-next-safe-slice-after-contract-mirror-apply-preflight-subset.md` |

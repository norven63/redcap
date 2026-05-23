# 任务完成报告：P4-29 合同镜像 copy-first 实施

**报告日期**：2026-05-23
**执行者**：Cap（Codex + Claude Code / Kimi 棱镜评审）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-29 已把 7 个已预检合同文件复制到新的 `contracts/public/**` 与 `contracts/internal/**` 位置。
- 详情：这些新文件是副本，不是迁移。旧 `references/**` 文件继续保留、可读、被 git 跟踪，仍是当前权威锚点。

### 0.2 上一步完成的是

- 上一步完成的是：P4-28 已选择 P4-29 作为下一条安全切片。P4-28 只做路线选择，没有创建 `contracts/**` 文件。

### 0.3 下一步计划做的是

- 下一步计划做的是：进入 P4-30 正式发布人工授权硬门。这个阶段不属于机械“继续”，因为许可证、发布开关、registry/npm 登录态、版本号和发布级别必须由 Norven 决定。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-25 合同分类预检 → P4-26 选择下一刀 → P4-27 小范围 apply 预检 → P4-28 选择 copy-first → P4-29 创建 7 个副本 → P4-30 发布人工授权硬门。
- 当前所在位置：P4-29 实施完成，等待 closeout receipt；父任务线焦点已推进到 P4-30。

### 0.5 是否需要 Norven 人工介入

- 人工介入：当前 P4-29 不需要 Norven 人工介入。
- 说明：本轮只做非破坏性副本创建；下一步 P4-30 需要 Norven 人工介入，因为正式发布授权不能由 Cap 或棱镜自动代替 Norven 决定。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “就是现在的状态是，你总是中途停顿下来，需要我人工机械的回复“好的，请你们继续”，但其实这根本不需要中断，完全可以由你和棱镜自动续上。并且，我经常会不在电脑旁，导致无法及时响应来回复这段机械的指令，你就会等很久才会继续推进，极大的延缓了项目推进速度”

### 1.2 触发背景

P4-28 closeout 后，父任务线明确给出下一项 P4-29。P4-29 是非破坏性 copy-first，不涉及删除、发布、凭据、许可证、registry、证据清理或产品边界，因此不应停下来等 Norven 机械回复“继续”。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 无人工硬门时自动续上父任务线，不再等待机械“继续”。 |
| 已覆盖 | 已自动进入 P4-29，并完成 7 个合同文件的 copy-first 实施、棱镜评审、checker 和包面安全验证。 |
| 未覆盖/延期 | 删除旧锚点、raw evidence cleanup、正式发布、凭据/许可证/registry、release blocker 关闭、Layer A 产品裁决。 |
| 用户可见边界 | 只能说“7 个合同副本已创建且旧锚点保留”，不能说“旧锚点已退休”或“RedCap 已可正式发布”。 |
| 后续路径 | P4-30 是真实人工发布授权硬门，不能自动绕过。 |

---

## 二、方案讨论

### 2.1 问题分析

P4-29 的核心风险不是复制本身，而是“把复制副本误说成迁移完成”。如果本轮删除旧锚点、清理证据、关闭 blocker 或修改发布开关，就会绕过后续人工硬门。因此本轮只允许做 7 个精确副本。

### 2.2 方案选项

| 选项 | 描述 | 结论 |
|---|---|---|
| A | 只创建 P4-27 已预检的 7 个合同副本 | 采纳 |
| B | 顺手删除旧 `references/**` 锚点 | 不采纳，破坏性动作，属于人工硬门 |
| C | 关闭 release blocker 或进入发布 | 不采纳，属于人工发布授权硬门 |
| D | 清理 Prism raw evidence | 不采纳，属于人工硬门 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---|---|---|
| Q1 | A：只做 7 文件 copy-first | 范围最小、可验证、可回滚，不跨人工硬门。 | CAP_DECIDE + Prism REVIEW |

---

## 三、落地结果

### 3.1 本轮完成了什么

本轮创建了 7 个新合同副本，并为这次 copy-first 建立了机器可审计的 manifest 与 checker。旧 `references/**` 锚点没有被删除、移动、替换或重定向。

### 3.2 解决后的效果

- 父任务线不再卡在“等 Norven 说继续”的机械状态。
- 7 个合同文件有了更接近未来 runtime/CLI 结构的新位置。
- 旧锚点继续保留，后续可以再用独立任务决定是否进入 delete-last。
- 包发布安全策略仍保持 fail-closed：本轮新增的内部 checker 和 manifest 不进入公开包。
- release blocker 仍保持打开，避免把 copy-first 误报成可发布。

### 3.2.1 术语对照（按文件/功能解释）

| 文件/功能 | 术语 | 人话解释 |
|---|---|---|
| `contracts/public/**` | public contract mirror | 给未来公开 runtime/CLI 使用的新合同副本位置。 |
| `contracts/internal/**` | internal contract mirror | 给内部控制面使用的新合同副本位置。 |
| `references/**` | old anchor | 旧路径上的权威文件，本轮继续保留。 |
| `references/r1-contract-mirror-bounded-copy-first-apply.json` | apply manifest | 本轮“到底复制了什么、没做什么”的机器账本。 |
| P4-30 | human authorization gate | 发布前必须由 Norven 做决定的人工门。 |

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|---|---|---|---|
| 1 | P4-29 无必须人工审核项 | 本轮未触碰发布、删除、凭据、许可证、registry、raw evidence cleanup 或产品裁决。 | P2 |
| 2 | P4-30 需要人工发布授权 | 许可证、发布开关、npm 登录态、版本号和发布级别不能自动决定。 | P0 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| P4-29 自检 | `bash compass/tools/redcap-r1-contract-mirror-bounded-copy-first-apply-check.sh` | 通过 |
| P4-27 桥接回归 | `bash compass/tools/redcap-r1-contract-mirror-apply-preflight-subset-check.sh` | 通过 |
| P4-28 桥接回归 | `bash compass/tools/redcap-r1-next-safe-slice-after-contract-mirror-apply-preflight-subset-check.sh` | 通过 |
| 文件查阅索引 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| 包发布安全 | `bash compass/tools/redcap-package-publish-safety-check.sh` | 通过 |
| runtime 包面清单 | `bash compass/tools/redcap-runtime-package-manifest.sh --check` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] P4-30 正式发布授权：许可证、发布开关、npm 登录态、版本号、发布级别。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| 执行承诺账本 | 待 closeout 前最终同步 |
| 棱镜验收 | 通过，run=`20260523-r1-contract-mirror-bounded-copy-first-apply` |
| closeout summary | 待生成 |
| closeout receipt | 待生成 |
| rescue audit（如有） | 待 closeout 后判断 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Claude Code / Kimi 共识 |
| 已正式完成 | 待 closeout receipt 生成后更新 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|---|---|---|
| 正式发布授权 | 这是 P4-30 人工硬门，不能自动绕过。 | P0 |
| 旧锚点 delete-last | 破坏性/兼容性动作，需要后续独立任务和更强回归。 | P0 |
| raw evidence cleanup | 证据清理需要显式批准。 | P0 |

### 6.2 触发的新问题

| 问题 | 处理 |
|---|---|
| 旧预检 checker 会把后续授权创建的目标文件误判为违规 | 已补桥接逻辑：只有存在 P4-29 manifest 且 copy/hash/旧锚点边界正确时才允许通过。 |

### 6.3 推荐的下一步行动

1. 完成 P4-29 closeout 并生成 receipt。
2. 进入 P4-30 前停止自动续跑，因为 P4-30 是正式发布人工授权硬门。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|---|---|---|
| L-P4-29 | 预检 checker 必须识别后续 apply 桥接 | 预检阶段要求“目标不存在”是当时状态，不应在后续授权 apply 后继续硬炸；需要用 successor manifest 显式桥接。 |

### 7.2 流程改进建议

后续所有“preflight → route selection → copy-first apply”链路，都应在 apply 任务中同步更新前置 checker，让历史预检资产能区分“越权创建目标”和“后续任务已授权创建目标”。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|---|---|---|---|
| preflight-successor-bridge | P4-29 实施回归 | deferred-with-owner owner=RedCap-Forge trigger=next-evolution-harvest-cycle | `compass/tools/redcap-r1-contract-mirror-apply-preflight-subset-check.py` |

---

## 八、附录

### 附录 A：Commits

```text
待提交
```

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|---|---|---|---|
| review | P4-29 是否可执行 7 文件 copy-first | Claude Code / Kimi 共识 approve；Copilot 未调用 | `prism/reports/2026-05-23-r1-contract-mirror-bounded-copy-first-apply.md` |

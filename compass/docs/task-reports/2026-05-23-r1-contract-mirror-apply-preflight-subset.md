# 任务完成报告：P4-27 小范围合同镜像 apply 预检

**报告日期**：2026-05-23  
**执行者**：Cap（Codex + Claude Code / Kimi 棱镜评审）  
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-27 已把 7 条 public/internal contract 候选整理成“未来 apply 前的安全预检”，并通过 Claude Code 与 Kimi 独立评审。
- 详情：这次没有实施迁移，也没有复制、移动、删除旧文件。它解决的是“如果后面要把合同类资产镜像到更清晰的位置，第一小组应该选哪些、未来要满足哪些条件、出问题怎么回滚、哪些动作必须立刻停下”。这样后续不会把“计划/预检”误报成“已经迁移完成”。

### 0.2 上一步完成的是

- 上一步完成的是：P4-26 只做路线裁决，选择 P4-27 作为下一条安全切片。P4-26 没有实施 P4-27，它只是决定“下一刀应该先做小范围 apply 预检”。

### 0.3 下一步计划做的是

- 下一步计划做的是：P4-28 继续做路线选择，判断 P4-27 后最安全的下一刀是什么。P4-28 仍不得自动升级为真实迁移、删除、发布、凭据处理或 Layer A 产品裁决。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-25 合同分类预检 → P4-26 选择下一刀 → P4-27 小范围 apply 预检 → P4-28 再次选择下一刀。
- 当前所在位置：P4-27 已完成，长期路线焦点已推进到 P4-28。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触碰发布、许可证、registry、凭据、真实删除、raw evidence cleanup 或 Layer A 产品边界。下一步仍可由 Cap 与棱镜继续做路线选择；只有后续命中这些硬门时才需要 Norven 决策。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “就是现在的状态是，你总是中途停顿下来，需要我人工机械的回复“好的，请你们继续”，但其实这根本不需要中断，完全可以由你和棱镜自动续上。并且，我经常会不在电脑旁，导致无法及时响应来回复这段机械的指令，你就会等很久才会继续推进，极大的延缓了项目推进速度”

### 1.2 触发背景

P4-26 closeout 后，父任务线已经明确给出 `PARENT_AUTOCONTINUE_OK`：下一步是 P4-27。  
因此本轮不应该停下来等 Norven 机械回复“继续”，而应该在没有人工硬门的前提下自动进入 P4-27。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 用户要求 RedCap 在无人工硬门时自动续上父任务线，不再等待机械“继续”。 |
| 已覆盖 | 已从 P4-26 自动续入 P4-27，并完成 P4-27 小范围 apply 预检、棱镜评审、状态面推进。 |
| 未覆盖/延期 | 真实 apply、删除旧锚点、raw evidence cleanup、正式发布、凭据/许可证/registry、Layer A 产品裁决均继续延期到独立硬门任务。 |
| 用户可见边界 | 只能说“P4-27 预检完成”，不能说“合同镜像已实施”或“RedCap 已可正式发布”。 |
| 后续路径 | P4-28 继续做下一安全切片路线选择。 |

---

## 二、方案讨论

### 2.1 问题分析

P4-27 的核心风险不是“技术上能不能写一份清单”，而是防止清单被误读成真实迁移。  
所以本轮把边界拆成三层：第一层选择小范围 subset，第二层写清未来 apply 前置条件，第三层用 checker 与棱镜阻止过度声明。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 直接实施合同镜像 | 立即把选中文件复制到 `contracts/**` | 推进快 | 会跨过真实迁移硬门，风险过高 |
| Q1 | 小范围 apply 预检 | 只选 7 个条目，记录未来目标和门禁 | 不破坏旧锚点，可评审、可回滚 | 还不解决真实迁移 |
| Q1 | 回到路线选择 | 不做 P4-27，重新选路 | 最保守 | 浪费 P4-26 已形成的共识 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 小范围 apply 预检 | 承接 P4-26 共识，同时不跨真实迁移、删除、发布和产品裁决硬门。 | CAP_DECIDE + Prism REVIEW |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `references/r1-contract-mirror-apply-preflight-subset.json` | 新建 | 记录 7 条小范围合同镜像预检候选、未来目标、回滚条件和禁止边界。 |
| `compass/tools/redcap-r1-contract-mirror-apply-preflight-subset-check.py` | 新建 | 校验 P4-27 仍是预检，不允许目标文件已存在、哈希过期、blocker 关闭或报告过度声明。 |
| `compass/tools/redcap-r1-contract-mirror-apply-preflight-subset-check.sh` | 新建 | P4-27 checker 的 shell 入口。 |
| `compass/tools/redcap-spec-check.sh` | 修改 | 把 P4-27 checker 接入全仓 spec-check。 |
| `package.json` / `references/runtime-package-readiness-policy.json` / `references/package-publish-safety-policy.json` | 修改 | 明确 P4-27 预检资产不属于未来公开 npm 包面。 |
| `references/file-lookup-dictionary-policy.json` / `references/file-lookup-dictionary.md` | 修改 | 把 P4-27 manifest 和 checker 纳入查阅索引。 |
| `references/backlogs/framework-upgrade.json` / `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` | 修改 | P4-27 标记完成，当前焦点推进到 P4-28。 |
| `prism/reports/2026-05-23-r1-contract-mirror-apply-preflight-subset.md` | 新建 | Claude Code / Kimi 评审结论报告。 |

### 3.2 技术实现要点

本轮采用“预检清单 + 机器校验 + 棱镜评审”的组合。预检清单负责说明未来想怎么做；机器校验负责阻止哈希漂移、目标路径已存在、blocker 被误关；棱镜评审负责独立判断是否跨过人工硬门。

这个设计的效果是：P4-27 能推进 release-readiness 的结构治理，但不会悄悄变成真实迁移，也不会污染未来 npm 包面。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| apply preflight | `references/r1-contract-mirror-apply-preflight-subset.json` | 未来真正执行前的安全演练清单；它不是执行本身。 |
| future target | `contracts/public/**` / `contracts/internal/**` | 将来可能复制到的新位置；本轮要求这些路径现在必须不存在。 |
| release blocker | `internal-control-plane` / `prism-layer-and-evidence` / `internal-layer-a` | 正式发布前仍没完全解决的阻断项；P4-27 不能关闭它们。 |
| route-selection-only | P4-28 | 下一步只判断走哪条路，不直接动文件或发布。 |

### 3.3 关联变更

P4-27 新增的 manifest 和 checker 会被包面规则排除，避免它们作为维护控制面证据误进入未来公开包。  
同时它们被加入文件查阅字典，保证后续 Agent 能按需定位，而不是全局扫历史文档。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无必须人工审核项 | 本轮未触碰发布、凭据、许可证、真实迁移、删除或产品裁决。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| P4-27 自检 | `bash compass/tools/redcap-r1-contract-mirror-apply-preflight-subset-check.sh` | 通过 |
| 文件查阅索引 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| 包发布安全 | `bash compass/tools/redcap-package-publish-safety-check.sh` | 通过 |
| runtime 包面清单 | `bash compass/tools/redcap-runtime-package-manifest.sh --check` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 无。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已清，7/7 完成 |
| 棱镜验收 | 通过 |
| closeout summary | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/summaries/redcap-r1-contract-mirror-apply-preflight-subset-2f0247a5f113533bc95d6a1e96f3b90407ade3b933c388fbb10acf2d780b78ea.md` |
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-r1-contract-mirror-apply-preflight-subset-2f0247a5f113533bc95d6a1e96f3b90407ade3b933c388fbb10acf2d780b78ea.json` |
| rescue audit（如有） | `无` |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是 |
| 已正式完成 | 是；closeout receipt 已生成 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 真实合同镜像 apply | 会复制/迁移文件，属于后续独立任务，不能由预检自动升级。 | P0 |
| release blocker 关闭 | 仍需更多证据，P4-27 不能关闭。 | P0 |
| 正式 npm 发布 | 仍涉及许可证、registry、凭据和发布授权硬门。 | P0 |

### 6.2 触发的新问题

无新增问题。执行中发现的大小写敏感误报已在 P4-27 checker 内修正。

### 6.3 推荐的下一步行动

1. 进入 P4-28，继续做下一安全切片路线选择。
2. 继续禁止自动升级到真实迁移、删除、发布或产品裁决。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| 无 | 无新增候选 | 本轮属于既有“预检不能冒充实施”的模式复用，不需要新增 lesson。 |

### 7.2 流程改进建议

继续强化 parent-autocontinue：无人工硬门时，下一安全切片应自动续跑，不应等待 Norven 机械回复“继续”。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | P4-27 预检 | no-promote | `prism/reports/2026-05-23-r1-contract-mirror-apply-preflight-subset.md` |

---

## 八、附录

### 附录 A：Commits

```text
da75ff9 feat(release): 完成合同镜像小范围预检
43e8c06 test(release): 刷新合同镜像预检干净工作区证据
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| review | P4-27 是否可作为预检收口 | Claude Code / Kimi 共识通过，未跨人工硬门 | `prism/reports/2026-05-23-r1-contract-mirror-apply-preflight-subset.md` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- P4-27 manifest：`references/r1-contract-mirror-apply-preflight-subset.json`
- Prism 报告：`prism/reports/2026-05-23-r1-contract-mirror-apply-preflight-subset.md`

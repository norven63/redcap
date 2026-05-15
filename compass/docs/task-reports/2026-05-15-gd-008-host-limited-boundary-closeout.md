# 任务完成报告：GD-008 host-limited 边界收口

**报告日期**：2026-05-15
**执行者**：Cap（Codex 主执行，Claude Code / Kimi Prism 验收）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：GD-008 已从“开放治理债务”收口为“已建模的 host-limited 宿主边界”。这表示 RedCap 已经把自己能控制的部分做好：执行保障、宿主画像、诊断、状态面和边界说明都在；但它没有、也不能冒充拥有完整 reply-time veto。

### 0.2 上一步完成的是

- 上一步完成的是：RASG-022 剩余高风险根目录已用显式延期收据完成当前阶段收口，架构坏味账本 open=0。

### 0.3 下一步计划做的是

- 下一步计划做的是：如果后续状态面没有新的非发布类治理债务，可进入正式 release readiness / npm 发布准备；正式发布仍需要许可证、发布开关、registry 权限和发布窗口等人工决策。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：历史债务与坏味治理 → 当前主推进任务集 → 正式发布准备 → 长期演进专项。
- 当前所在位置：历史债务与坏味治理中的 GD-008 收口切片；本轮处理的是 host-limited 边界，不是正式发布。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要
- 说明：本轮没有触及发布、许可证、凭据、大规模删除、公开远端写入或不可逆历史改写。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “好的，你们继续按照自己评估的优先级来稳步推进吧”

### 1.2 触发背景

RASG-022 closeout 后，RedCap 状态面显示架构坏味账本已清零，但治理债务仍有 1 项开放：GD-008。继续保留这个 open 项会让前进刻度表显得永远没法清零；但直接删掉又会遮蔽一个真实边界：当前宿主并没有提供完整的 repo-owned reply-time veto。

所以本轮目标不是“实现 100% 拦截”，而是把这个限制从开放债务改成明确边界：RedCap 已经完成诚实建模；未来如果宿主真的提供新能力，再新开升级任务。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 继续推进父任务线，不停在 RASG-022。 |
| 已覆盖 | GD-008 状态改为 design-complete / done，补充 host-limited resolution 和 reactivation sentinel。 |
| 未覆盖/延期 | 不实现完整 reply-time veto；不证明 Codex.app interactive ready；不进入 npm 发布。 |
| 用户可见边界 | 可以说治理债务 open=0；不能说所有宿主行为都已 100% 物理可控。 |
| 后续路径 | 未来宿主提供 pre-reply/pre-send Hook 时，新开 host-adapter upgrade task。 |

---

## 二、方案讨论

### 2.1 问题分析

GD-008 的剩余问题不是“RedCap 还没写完某个脚本”，而是“宿主是否给 RedCap 一个能在 live reply 发出前拦截的物理控制点”。没有这个控制点，RedCap 能做的是：启动导入、状态提醒、诊断、任务报告、closeout、Prism、hook candidate 和 host capability matrix；不能诚实承诺每句话都能被仓库脚本 veto。

把 GD-008 保持为 `in-progress` 会造成另一种不诚实：它暗示 RedCap 再努力一点就能在仓库内解决这个物理边界。更准确的状态是：仓库内治理已完成，宿主能力边界仍然存在。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 继续保持 in-progress | 把 GD-008 继续算作开放治理债务 | 保守 | 造成永远无法清零的假债务 |
| Q1 | 直接标 done | 改成 done，不解释边界 | 进度清晰 | 容易误导为 reply-veto 已实现 |
| Q1 | done + host-limited resolution + reactivation sentinel | 标 done，同时写清物理边界和未来触发器 | 诚实、可持续、可检查 | 需要补矩阵和检查器 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | done + host-limited resolution + reactivation sentinel | 这是唯一同时避免“假未完成”和“假 100%”的方案。 | CAP_DECIDE，Claude Code / Kimi Prism 验收无 blocker |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 重锚当前任务到 GD-008 host-limited boundary closeout。 |
| `compass/knowledge/governance-debt-register.md` | 修改 | 将 GD-008 更新为 design-complete / done，并解释 done 的真实含义。 |
| `references/host-session-capability-matrix.json` | 修改 | 增加 GD-008 reactivation sentinel 与各宿主 reply-veto 状态字段。 |
| `compass/tools/redcap-hook-contract-check.sh` | 修改 | 校验 host capability matrix 必须保留 GD-008 sentinel。 |
| `prism/reports/2026-05-15-gd-008-host-limited-boundary-closeout.md` | 新建 | 归档 Claude Code / Kimi 的 Prism 结论。 |

### 3.2 技术实现要点

这次的关键不是新增一个拦截器，而是把“不能拦截”从模糊失败改成清晰契约。GD-008 的 `done` 只表示 RedCap-owned 工作已经完成：相关文档、执行保障、状态面、诊断链都能诚实说明边界。宿主是否有 pre-reply/pre-send Hook，仍由宿主能力决定。

新增的 reactivation sentinel 让未来升级有明确触发条件：如果某个宿主真的提供并验证了 repo-owned reply veto，RedCap 不需要把 GD-008 翻旧账，而是开一个新的 host-adapter upgrade task，把该宿主从 G3/manual-only 升到更强的保障层级。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| GD-008 | `compass/knowledge/governance-debt-register.md` | 一条治理债务，记录“RedCap 目前不能在宿主发出每一句回复前物理拦截”的边界。 |
| host-limited | 宿主能力边界 | 不是 RedCap 不想做，而是 Codex.app 等宿主没有开放可由仓库控制的回复前拦截接口。 |
| reply-time veto | pre-reply / pre-send 拦截能力 | 如果宿主未来提供这个能力，RedCap 才可能在回复发出前做更强的自动阻断。 |
| reactivation sentinel | `references/host-session-capability-matrix.json` | 一个未来升级触发器：一旦宿主证明有回复前拦截能力，就新开宿主适配升级任务。 |
| hook contract | `compass/tools/redcap-hook-contract-check.sh` | 防止上面这个未来触发器被后续改动无意删除的机器检查。 |

### 3.3 关联变更

状态面会从 `governance debt open=1` 变为 `governance debt open=0`。但 Codex.app interactive 未验证、无完整 reply-veto 的边界仍留在宿主画像、执行保障和 hook readiness 文案中，不会被清零。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无必须人工介入项 | 本轮只是把宿主能力边界从开放债务转成已建模边界，不触碰发布或凭据。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| Prism dispatch gate | `bash prism/tools/prism-dispatch-check.sh --mode test --agents "claude-code&claude-code:reviewer,kimi&kimi:challenger"` | 通过 |
| Prism acceptance binding | `bash compass/tools/redcap-prism-acceptance-bind.sh --run-id 20260515-gd008-host-limited-boundary-closeout --task-file .dev-task.md && bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过：2 个 agent / 2 个模型族 / 0 blocker |
| hook contract | `bash compass/tools/redcap-hook-contract-check.sh` | 通过 |
| progress meter / current-status | `bash compass/tools/redcap-current-status.sh .dev-task.md` | 通过：governance debt open=0，Codex.app full reply-veto 仍显示为未证明边界 |
| docs catalog | `bash compass/tools/redcap-docs-catalog.sh generate && bash compass/tools/redcap-docs-catalog.sh check` | 通过 |
| cold archive inventory | `bash compass/tools/redcap-cold-archive-inventory.sh update && bash compass/tools/redcap-cold-archive-inventory.sh check` | 通过：将最旧活跃报告归入私有冷归档后刷新清单 |
| reference asset lifecycle | `bash compass/tools/redcap-reference-asset-lifecycle.sh update && bash compass/tools/redcap-reference-asset-lifecycle.sh check` | 通过 |
| human output quality | `python3 compass/tools/redcap-human-output-quality-check.py --report compass/docs/task-reports/2026-05-15-gd-008-host-limited-boundary-closeout.md` | 通过 |
| task-report check | `bash compass/tools/redcap-task-report-check.sh "$PWD" 59ae72b0d2d34463b116c979145d52d69e9fd182` | 通过 |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 无必须人工验证项。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已勾选，等待 closeout runtime 最终核验 |
| 棱镜验收 | Claude Code / Kimi 已归档并通过 acceptance binding，无 blocker |
| closeout summary | 无 |
| closeout receipt | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Claude Code / Kimi 无 blocker |
| 已正式完成 | 否，receipt 将由 closeout runtime 生成 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 完整 reply-time veto | 宿主未提供 repo-owned pre-reply/pre-send Hook，仓库内不能物理实现。 | 长期演进 |
| 正式 npm 发布 | 本轮只关闭 GD-008 边界，不进入发布。 | P1 |

### 6.2 触发的新问题

无新增开放问题；本轮新增的是未来宿主能力升级触发器。

### 6.3 推荐的下一步行动

1. 提交本轮变更并执行正式 closeout。
2. 若 receipt 生成且状态面继续确认历史债务与治理债务均清零，则转入正式 release readiness 前的最终判断。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| 无 | 无新增 lesson | 本轮是既有宿主边界的诚实收口，不新增通用经验。 |

### 7.2 流程改进建议

不能物理实现的宿主限制不应永远占据 open debt；应在证据充分后收口为 host-limited boundary，并保留未来 reactivation trigger。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 本轮只是将已登记宿主边界收口 | 无新增候选 | `.dev-task.md` |

---

## 八、附录

### 附录 A：Commits

```
待提交；本报告对应提交生成后以 `git log -1` 为准。
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| test | GD-008 是否可标为 done-with-host-limited-boundary | pass-with-concerns，无 blocker | `prism/reports/2026-05-15-gd-008-host-limited-boundary-closeout.md` |

### 附录 C：相关文档索引

- 任务卡：`.dev-task.md`
- 治理债务：`compass/knowledge/governance-debt-register.md`
- 宿主能力矩阵：`references/host-session-capability-matrix.json`

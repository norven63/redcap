# 任务完成报告：执行层物理拆分 dry-run

**报告日期**：2026-04-26
**执行者**：Cap（Codex.app 主执行，Kimi CLI Prism reviewer）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P1-1 已完成执行层物理拆分 dry-run，不执行真实搬迁。
- 详情：新增 `references/execution-layer-split-dry-run.json`，把 `bin/redcap`、`revive-cap.sh`、`closeout-cap.sh`、`compass/tools`、`prism/tools`、`references`、`AGENTS.md` 和历史 task reports 的迁移边界写成机器可读计划。新增 checker 并接入 spec-check、diagnose、acceptance，能拒绝危险 dry-run 计划。

### 0.2 上一步完成的是

- 上一步完成的是：P0-2 建立了 R0-R22 机器可读 registry，让父任务编号、证据、延期边界和完成声明不再靠记忆。
- 详情：P1-1 接在 P0-2 之后，开始把“RedCap 要从 skill-root 走向 runtime / CLI / 多层系统”这个父任务拆成可审计的物理迁移前置步骤。

### 0.3 下一步计划做的是

- 下一步计划做的是：P1-2 历史资产迁移 dry-run/apply，重点处理 task reports、docs、research、catalog 与 receipt 证据链，先生成 retain/archive/move/prune manifest，再决定是否 apply。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P0-1 Prism cache 修复 → P0-2 R0-R22 registry → P1-1 执行层拆分 dry-run → P1-2 历史资产迁移 → P1-3 shared-knowledge 远端绑定 → P2 runtime/CLI/package。
- 当前所在位置：P1-1 已完成实现与独立审查，等待 closeout runtime 写入正式 receipt。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 继续

### 1.2 触发背景

RedCap 的长期父任务已经从“继续补 skill”转为“演进为独立 Agent runtime / CLI / 多层系统”。但当前根目录入口、宿主导入文件、hooks、`compass/tools`、`prism/tools`、docs catalog 和历史报告仍深度耦合，不能直接搬迁。本轮先做 dry-run，是为了把迁移边界、风险和回滚条件写成机器可读计划。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 开始推进执行层物理拆分，但先以 dry-run 形式明确风险与可迁移边界，避免直接搬迁破坏现有 hook、revive、closeout。 |
| 已覆盖 | 已生成 dry-run manifest、checker、spec/diagnose/acceptance 接线、父任务账本更新、文件字典更新、执行保障登记、lesson 和 Prism review。 |
| 未覆盖/延期 | 本轮不执行真实 move/copy/link，不修改宿主 hook 指向，不发布 runtime/package。 |
| 用户可见边界 | P1-1 完成只说明迁移计划可审计，不说明执行层已经物理拆出。 |
| 后续路径 | P1-2 处理历史资产迁移；P2-1 才能进入正式 runtime / CLI / package 发布设计与实现。 |

---

## 二、方案讨论

### 2.1 问题分析

执行层拆分不是普通目录整理。`revive-cap.sh`、`closeout-cap.sh`、`AGENTS.md` 这类入口被宿主或人类直接调用；`compass/tools` 和 `prism/tools` 又被 validators、hooks、acceptance、closeout runtime 调用。一旦真实移动，就可能让新会话复活、完成收口、git hooks 和 Prism 审查同时断裂。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 直接迁移 | 立刻把 runtime 文件移入新目录 | 看起来变化明显 | 风险最高，容易破坏 hook 和 closeout |
| Q1 | dry-run manifest | 先做机器可读迁移蓝图并接入回归 | 可审计、可回滚、不会破坏当前工作区 | 不能直接产出物理拆分效果 |
| Q1 | 只写路线图 | 写文档说明未来要迁移 | 成本最低 | 仍会回到“路线图冒充完成”的坏味 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | dry-run manifest | 这是唯一能同时满足安全、可审计、可继续推进的方案；真实迁移必须另开 apply 任务。 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `references/execution-layer-split-dry-run.json` | 新建 | 执行层物理拆分 dry-run manifest，登记候选迁移、风险、阻塞原因、影响和回滚计划。 |
| `compass/tools/redcap-execution-layer-split-check.py` | 新建 | 校验 dry-run manifest，拒绝危险 apply、缺失字段、不安全路径、已存在 target 和缺 rollback。 |
| `compass/tools/redcap-execution-layer-split-check.sh` | 新建 | checker shell 入口。 |
| `compass/tools/redcap-spec-check.sh` | 修改 | 接入 execution-layer split dry-run checker。 |
| `compass/tools/redcap-diagnose.sh` | 修改 | 诊断总入口新增 dry-run checker。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增 `execution-layer-split-check` acceptance，覆盖危险 fixture。 |
| `references/file-lookup-dictionary.md` | 修改 | 新增 manifest 和 checker 的人类可读定位。 |
| `references/file-lookup-dictionary-policy.json` | 修改 | 新增 manifest 和 checker 的机器 coverage。 |
| `references/execution-guarantees.json` | 修改 | 新增 `execution-layer-split-dry-run` 保障项。 |
| `references/redcap-parent-task-ledger.md` | 修改 | 标记 P1-1 完成，下一步转入 P1-2。 |
| `compass/knowledge/lessons.md` | 修改 | 新增 L-127，沉淀“先 dry-run、再 apply”的迁移经验。 |
| `compass/docs/catalog.json` | 修改 | 生成新报告索引。 |

### 3.2 技术实现要点

manifest 采用 fail-closed 口径：顶层 `apply_allowed` 固定为 `false`，每个 high-risk plan 都必须是 blocked 或 deferred。对 `revive-cap.sh`、`closeout-cap.sh`、`compass/tools`、`prism/tools`、`AGENTS.md` 这类强入口，manifest 只允许 copy / shim / rewire 计划，不允许直接 move。

checker 不只检查 JSON 能否解析，还会验证 source 是否存在、target 是否安全且当前不存在、operation/risk/apply_status 是否在白名单内、影响列表和 rollback_plan 是否非空。Kimi review 指出的 `.githooks` 和 root shim 跨路径依赖已补进 manifest，并新增 target 已存在的回归 fixture。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| dry-run manifest | `references/execution-layer-split-dry-run.json` | 只做迁移蓝图，不搬文件；让后续 apply 任务知道哪些路径能动、哪些必须等 shim 或 path map。 |
| apply_allowed | manifest 顶层字段 | 当前是否允许真实执行迁移；本轮固定为 `false`。 |
| rollback_plan | manifest 每个 plan 的字段 | 如果未来 apply 失败，应如何撤回；没有回滚计划的迁移建议一律不合格。 |
| target-not-exists | `redcap-execution-layer-split-check.py` | dry-run target 当前不应已经存在，避免旧残留污染“还没迁移”的判断。 |
| resource-limited Prism | `prism/runs/20260426-execution-layer-split-dry-run-review` | 本轮只有 Kimi 真实返回审查，其他 provider 不满足 formal quorum；因此是资源受限通过，不冒充多模型 quorum。 |

### 3.3 关联变更

父任务账本同步把 P1-1 标为 completed，但仍保留 P1-2/P1-3/P2 后续项。文件字典和执行保障登记同步更新，避免新增关键 manifest/checker 后又变成“没人知道该看哪里”的孤儿文件。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 是否接受 P1-1 只做 dry-run | 这是为了保护 revive、closeout、hooks 和 docs catalog；真实迁移要等 P1-2/P2 apply。 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 语法检查 | `python3 -m py_compile compass/tools/redcap-execution-layer-split-check.py` | 通过 |
| targeted checker | `bash compass/tools/redcap-execution-layer-split-check.sh` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh execution-layer-split-check` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | resource-limited-pass |
| 文件字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| 总回归 | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| 诊断总入口 | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无必须人工验证项；真实迁移 apply 尚未开始。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 预计 closeout 前清零 |
| 棱镜验收 | `20260426-execution-layer-split-dry-run-review` resource-limited-pass |
| closeout summary | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/summaries/redcap-execution-layer-split-dry-run-f0356fb471718b9a97d61ebe7f2acdb2374f01af93c3aa9cc330bceb78ec32ee.md` |
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-execution-layer-split-dry-run-f0356fb471718b9a97d61ebe7f2acdb2374f01af93c3aa9cc330bceb78ec32ee.json` |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，resource-limited Prism 通过 |
| 已正式完成 | 是；提交后由 closeout runtime 生成上方 receipt |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 历史资产物理迁移 | 属于 P1-2，需要单独 retain/archive/move/prune manifest 和断链检查。 | P1 |
| 正式 runtime / CLI / package 发布 | 依赖 P1-1/P1-2 边界清晰后再设计 apply 和发布包面。 | P2 |
| Formal Prism quorum 恢复 | 本轮仅 Kimi 稳定返回，其他 provider 仍未形成稳定双模型审查。 | P2 |

### 6.2 触发的新问题

Kimi review 暴露 `.githooks`、root shim 与 `bin/redcap` 对 `compass/tools` / `prism/tools` 的跨路径依赖容易被后续迁移遗漏。本轮已把它们补入 manifest 和 L-127；P1-2/P2 apply 时必须继续复验。

### 6.3 推荐的下一步行动

1. 执行 P1-2：历史资产迁移 dry-run/apply，先做 manifest 和断链检查，再决定是否真实搬迁。
2. 执行 P1-3：用户提供远端仓库后绑定 shared-knowledge。
3. 执行 P2-1：设计正式 runtime / CLI / package 形态，并用 package safety gate 审包面。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-127 | 执行层物理拆分要先 dry-run 化，不能把路线图当迁移结果 | 先用 manifest 和 checker 锁住路径、风险、影响、回滚，再进入真实 apply。 |

### 7.2 流程改进建议

后续涉及目录物理迁移的任务，应默认采用 dry-run manifest → independent review → targeted acceptance → apply task 的两阶段模式，不能把“写了迁移路线”当成“完成迁移”。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 本轮 review 和回归 | no-promote；已沉淀为 L-127，不新增 Evolution candidate | `compass/knowledge/lessons.md` |

---

## 八、附录

### 附录 A：Commits

```
本报告随 P1-1 实现提交一起进入 git；closeout receipt 将记录最终 HEAD。
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| single-reviewer / resource-limited | dry-run 是否过度乐观、checker 是否挡住危险计划、接线是否完整 | Kimi 判定 pass；指出 `.githooks`、root shim、target existence 风险，本轮已吸收 | `prism/runs/20260426-execution-layer-split-dry-run-review/collect/reviewer/parsed.json` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- dry-run manifest：`references/execution-layer-split-dry-run.json`
- 父任务账本：`references/redcap-parent-task-ledger.md`
- 文件字典：`references/file-lookup-dictionary.md`

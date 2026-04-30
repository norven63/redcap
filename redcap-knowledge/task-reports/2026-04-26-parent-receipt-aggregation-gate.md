# 任务完成报告：父任务 receipt 聚合 gate

**报告日期**：2026-04-26
**执行者**：Cap（Codex.app 主执行，Codex CLI + Kimi Prism reviewers）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P2-2 已完成父任务 receipt 聚合 gate，但父任务仍不可声明 complete。
- 详情：新增 `references/parent-receipt-aggregation-policy.json`，把 P0-1/P0-2/P1-1/P1-2 作为已完成子任务，把 P1-3/P2-1/P2-3 作为 not-complete 边界。新增 checker 并接入 spec-check、diagnose、acceptance，阻止“子任务 receipt 冒充父任务完成”。

### 0.2 上一步完成的是

- 上一步完成的是：P1-2 历史资产迁移 dry-run，建立了 docs/reports/knowledge/runtime evidence 的集合级迁移计划。
- 详情：P2-2 接在 P1-2 后，把多个子任务 closeout 变成父任务层可审计状态面。

### 0.3 下一步计划做的是

- 下一步计划做的是：P1-3 shared-knowledge 远端绑定需要外部仓库与权限；P2-1 runtime/CLI/package 仍需继续推进；P2-3 等待 provider quorum 恢复。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P0/P1 dry-run 与治理子任务 → P2-2 父任务聚合 gate → P1-3/P2-1/P2-3 继续收口 → 父任务才可能 complete。
- 当前所在位置：P2-2 gate 已实现，父任务状态由 `not-eligible` 明确表示。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 继续

### 1.2 触发背景

用户多次指出 RedCap 长任务容易出现“做完一个子任务就像做完整个父任务”的幻觉。P2-2 的目标是把这个风险变成机器可检查的父任务聚合 gate。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 建立父任务级完成证明，避免多个子任务 closeout 后继续发生局部完成冒充整体完成。 |
| 已覆盖 | 已生成 aggregation policy、checker、spec/diagnose/acceptance 接线、父任务账本更新、文件字典更新、执行保障登记、lesson 和 Prism review。 |
| 未覆盖/延期 | 本轮不把父任务标记为 complete，不强依赖外部远端和 provider 恢复。 |
| 用户可见边界 | P2-2 完成只说明父任务完成判断有 gate，不说明 RedCap 长父任务已经全部完成。 |
| 后续路径 | P1-3、P2-1、P2-3 继续推进或显式关闭后，aggregation policy 才能允许父任务 complete。 |

---

## 二、方案讨论

### 2.1 问题分析

子任务 receipt 是局部事实，父任务完成是聚合事实。二者不能混用，否则 closeout runtime 越可靠，越容易被误读成“整体已完成”。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 手写总结 | 在报告里说明父任务未完成 | 简单 | 仍靠人工阅读，不能阻断混报 |
| Q1 | 聚合 policy + checker | 用机器表登记 completed/not-complete 边界 | 可审计、可回归、能 fail-closed | 需要维护 policy |
| Q1 | 直接父任务 receipt | 尝试生成父级 receipt | 看似完整 | 当前仍有 open/blocked/resource-limited 项，会制造假完成 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 聚合 policy + checker | 它能保护父任务完成语义，同时不伪造父级 completion。 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `references/parent-receipt-aggregation-policy.json` | 新建 | 父任务聚合策略，登记 completed children、not-complete children 和 allowed claim。 |
| `compass/tools/redcap-parent-receipt-aggregation-check.py` | 新建 | 校验父任务不可 complete、子任务报告存在、未完成项有原因和下一步。 |
| `compass/tools/redcap-parent-receipt-aggregation-check.sh` | 新建 | checker shell 入口。 |
| `compass/tools/redcap-spec-check.sh` | 修改 | 接入 parent receipt aggregation checker。 |
| `compass/tools/redcap-diagnose.sh` | 修改 | 诊断总入口新增 parent receipt aggregation checker。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增 `parent-receipt-aggregation-check` acceptance。 |
| `references/file-lookup-dictionary.md` | 修改 | 新增 policy 和 checker 的人类可读定位。 |
| `references/file-lookup-dictionary-policy.json` | 修改 | 新增 policy 和 checker 的机器 coverage。 |
| `references/execution-guarantees.json` | 修改 | 新增 `parent-receipt-aggregation-gate` 保障项。 |
| `references/token-structural-governance.json` | 修改 | 将增长后的 `compass/docs/catalog.json` 登记为大文件结构治理对象，避免 token-risk audit fail。 |
| `references/legacy-asset-migration-dry-run.json` | 修改 | 同步新增报告、Prism run 与 lesson 后的 dry-run 资产计数，保持历史资产迁移 gate 自洽。 |
| `references/redcap-parent-task-ledger.md` | 修改 | 标记 P2-2 gate 完成，但父任务仍 incomplete。 |
| `compass/knowledge/lessons.md` | 修改 | 新增 L-129。 |
| `compass/docs/catalog.json` | 修改 | 生成新报告索引。 |

### 3.2 技术实现要点

policy 固定 `parent_completion_allowed=false`，并把 `gate_outputs.parent_receipt_status` 写成 `not-eligible`。checker 要求 completed children 至少包含 P0-1/P0-2/P1-1/P1-2，not-complete children 至少包含 P1-3/P2-1/P2-3，且每个未完成项必须有状态、原因和下一步，同时要求 allowed claim 明确包含 “parent task is still incomplete”。

本轮 gate 的边界是“防止父任务完成混报”，不是“重新证明每个子任务 receipt 的运行时内容”。completed child 的 receipt 证据当前以 `receipt_glob` 元数据表达，checker 校验其形态；真实 runtime receipt 内容对应关系留给后续更专门的 receipt evidence hardening。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| parent receipt aggregation | `references/parent-receipt-aggregation-policy.json` | 把多个子任务的完成和未完成边界聚合成父任务状态。 |
| completed_children | aggregation policy | 已完成且有报告/receipt 证据的子任务清单。 |
| not_complete_children | aggregation policy | 仍 open、blocked-external、resource-limited 或 deferred 的子任务清单。 |
| not-eligible | gate output | 当前父任务还不能生成或声明完成 receipt。 |

### 3.3 关联变更

父任务账本现在明确 P2-2 gate 已完成，但父任务仍因 P1-3、P2-1、P2-3 未满足而不可 complete。

回归过程中还发现两处控制面派生资产漂移：`compass/docs/catalog.json` 超过 token-risk 结构治理阈值、P1-2 legacy dry-run manifest 的 task report / prism run / knowledge line counts 因本轮新增资产变化。两者均已同步，避免旧机制资产与新机制工作流打架。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 是否接受父任务仍 incomplete | 当前还有 blocked/open/resource-limited 子项，gate 正确拒绝父级完成声明。 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 语法检查 | `python3 -m py_compile compass/tools/redcap-parent-receipt-aggregation-check.py` | 通过 |
| targeted checker | `bash compass/tools/redcap-parent-receipt-aggregation-check.sh` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh parent-receipt-aggregation-check` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | pass（Codex CLI + Kimi，2 families） |
| 总回归 | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| 诊断总入口 | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无必须人工验证项；父任务当前应保持 incomplete。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 预计 closeout 前清零 |
| 棱镜验收 | `20260426-parent-receipt-aggregation-gate-review` pass（Codex CLI + Kimi，2 families） |
| closeout summary | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/summaries/redcap-parent-receipt-aggregation-gate-4dac6fca157a51003c05ee0bea528d3bce5e5ce889abb49e1133339ab72a30c8.md` |
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-parent-receipt-aggregation-gate-4dac6fca157a51003c05ee0bea528d3bce5e5ce889abb49e1133339ab72a30c8.json` |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Codex CLI + Kimi 双 reviewer Prism 通过 |
| 已正式完成 | 是；提交后由 closeout runtime 生成上方 receipt |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| P1-3 shared-knowledge 远端绑定 | 需要外部仓库和权限。 | P1 |
| P2-1 runtime / CLI / package | 仍需后续设计与实现。 | P2 |
| P2-3 formal Prism quorum | provider 仍不稳定。 | P2 |
| P3-2 runtime receipt evidence correspondence hardening | P2-2 的目标是父任务 fail-closed，不在本轮证明 receipt 内容对应关系。 | P3 |

### 6.2 触发的新问题

无新增 blocker；本轮把“父任务仍 incomplete”从口头说明变成机器 gate。

非阻塞边界：receipt evidence 当前校验到 `receipt_glob` 元数据形态，不校验 runtime receipt 文件内容对应关系。该问题不影响本 gate 的父任务 fail-closed 语义，但可在后续 receipt evidence hardening 中增强。

### 6.3 推荐的下一步行动

1. 等用户提供 shared-knowledge 远端后执行 P1-3。
2. 推进 P2-1 runtime / CLI / package 设计实现。
3. provider 稳定后复验 P2-3 formal Prism quorum。
4. 在 receipt root 可稳定定位后，推进 P3-2 receipt evidence correspondence hardening。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-129 | 父任务完成必须由聚合 gate 判断，不能由子任务 receipt 推断 | 子任务 receipt 是局部事实；父任务完成必须聚合 completed 与 not-complete 边界。 |

### 7.2 流程改进建议

所有长父任务都应维护 parent aggregation policy，防止多次 closeout 后丢失整体未完成边界。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 本轮实现与回归 | no-promote；已沉淀为 L-129，不新增 Evolution candidate | `compass/knowledge/lessons.md` |

---

## 八、附录

### 附录 A：Commits

```
本报告随 P2-2 实现提交一起进入 git；closeout receipt 将记录最终 HEAD。
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| reviewer / openai | 父任务聚合 gate 是否防止子任务冒充父任务完成 | Codex CLI reviewer pass；提示 receipt glob 是非阻塞证据深度风险 | `prism/runs/20260426-parent-receipt-aggregation-gate-review/collect/reviewer/parsed.json` |
| reviewer / moonshot | 父任务聚合 gate 是否防止子任务冒充父任务完成 | Kimi reviewer pass；建议补 gate_outputs 负例，已转成 acceptance | `prism/runs/20260426-parent-receipt-aggregation-gate-review/collect/kimi_review/parsed.json` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- aggregation policy：`references/parent-receipt-aggregation-policy.json`
- 父任务账本：`references/redcap-parent-task-ledger.md`
- 文件字典：`references/file-lookup-dictionary.md`

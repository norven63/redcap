# 任务完成报告：原始意图覆盖审计硬门

**报告日期**：2026-04-26  
**执行者**：Cap（Codex.app 宿主）  
**报告版本**：v0.1

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：已把本轮故障修复单独重锚成新任务，避免继续用上一轮 receipt 证明新需求。
- 已新增 `redcap-intent-coverage-check.sh`，要求真实 Layer B 任务写明 `scope_status`、原始意图、已覆盖、未覆盖/延期、用户可见边界和后续路径。
- 已把该检查接入 PM Gate 和 diagnose，并登记到 execution guarantees，避免它只停留在自然语言规则。
- 已补任务报告模板、文件查阅字典、acceptance fixture、Evolution candidate 和 lessons。

### 0.2 上一步完成的是

- 上一步完成的是：上一轮任务报告已经修正为 receipt 后状态，但这只能证明“产品形态路线图 + 控制面加固”完成，不能证明 RedCap 物理目录迁移或独立 CLI 化完成。

### 0.3 下一步计划做的是

- 下一步计划做的是：无当前任务内必需动作；后续若推进物理目录迁移或独立 CLI 化，应另立迁移任务并先通过本硬门。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：失败复盘 → 重锚新任务 → 新增原始意图覆盖硬门 → 接入 PM Gate / diagnose / guarantees → 补模板和 acceptance → 沉淀 lessons → 回归与提交。
- 当前所在位置：实现、targeted 回归、full acceptance、spec-check 与 diagnose 已完成，等待提交后收口。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 我不是很理解，这也没经过几轮对话，你怎么对我的要求就漂移了呢？导致一共执行了6个多小时的任务只是半吊子，问题到底出在哪里？

> 你还能通过回归前面几轮对话，回忆出完整的需求吗？以及如果你说加一个“原始意图覆盖审计”硬门，实质上是不是类似于LayerA中的产品经理那层职责？这个什么时候加？

### 1.2 触发背景

本次问题的根因不是对话轮数太多，而是任务卡形成时发生了范围降级。用户想推进的是系统级演进，而任务卡把其中一部分写成“路线图 + 控制面加固”，后续所有回归、receipt 和承诺账本都只验证了这个窄范围。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 找出为什么需求被降级、判断硬门职责归属，并立即补上防线 |
| 已覆盖 | 已复盘根因、明确 PM Gate 职责、实现机器硬门并接入诊断/回归 |
| 未覆盖/延期 | RedCap 物理目录迁移和独立 CLI 化仍是后续系统迁移任务 |
| 用户可见边界 | 本轮只修任务范围降级防线，不冒充完成独立 runtime / CLI 迁移 |
| 后续路径 | 后续系统迁移任务必须先通过该硬门 |

## 二、方案讨论

### 2.1 问题分析

完整需求可以回忆出来：用户要求 RedCap 从 skill-root 逐步演进为独立 runtime / CLI / 多层系统，并且治理目录结构、知识库、证据层、人类报告层、人格层、Prism、FSM、飞书通知、经验沉淀和长上下文对抗能力。上一轮真正漏的是“物理迁移 / 系统结构真实落地”与“路线图任务”的边界没有显性写清。

“原始意图覆盖审计”本质上就是产品经理职责：把用户的战略目标翻译成可执行需求时，必须审有没有缩水、有没有延期、有没有把方案当实现。区别是，Layer B 不能只靠一个 PM 角色名，而要把这件事写进 `.dev-task.md`、PM Gate、Planning Review 和 closeout 证据链。

### 2.2 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---|---|---|
| Q1 | 把漂移定位为“任务卡范围降级” | 后续机制都在验证被降级后的任务卡，所以根因必须前移到 PM Gate | CAP_DECIDE |
| Q2 | 立即加入原始意图覆盖硬门 | 这是 P0 防线，不能等下一次大任务再补 | CAP_DECIDE |

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|---|---|---|
| `.dev-task.md` | 修改 | 重锚为当前原始意图覆盖硬门任务 |
| `compass/tools/redcap-intent-coverage-check.sh` | 新建 | 校验 scope_status、覆盖/延期/边界/后续路径 |
| `compass/tools/redcap-pm-gate-check.sh` | 修改 | strict PM Gate 消费原始意图覆盖审计 |
| `compass/tools/redcap-diagnose.sh` | 修改 | 诊断面新增 intent-coverage 门 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 增加覆盖审计正反例 |
| `compass/CONTRIBUTING.md` | 修改 | PM Gate 新增 Phase 2.5 |
| `references/task-report-template.md` | 修改 | 报告必须披露原始意图覆盖审计 |
| `references/execution-guarantees.json` | 修改 | 登记 P0 control gate |
| `references/file-lookup-dictionary.md` | 修改 | 增加新硬门说明 |
| `compass/evolution/candidates.json` / `compass/knowledge/lessons.md` | 修改 | 沉淀 EVO-2026-04-26-001 / L-118 |

### 3.2 技术实现要点

`redcap-intent-coverage-check.sh` 不假装能完美理解自然语言，但它能强制任务卡显式回答最容易被偷换的几个问题：原始意图是什么、当前任务是否 full implementation、哪些延期了、用户最终能看到什么边界。对 `route-only` 或 `partial-with-explicit-defer`，它要求写出未覆盖/延期和后续路径。

PM Gate strict 模式现在会调用该检查；diagnose 也会显示它。这意味着后续如果任务卡缺少覆盖审计，不能只靠承诺账本和 receipt 自证完成。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| 原始意图覆盖审计 | `redcap-intent-coverage-check.sh` | 检查任务卡有没有说明“用户原本想要什么”和“本轮到底覆盖到什么程度” |
| scope_status | `.dev-task.md` 覆盖审计段 | 明确本轮是完整实现、只做路线图、部分实现延期，还是不适用 |
| PM Gate Phase 2.5 | `compass/CONTRIBUTING.md` | 需求锁定后、执行前的范围覆盖检查 |

## 五、验证结果

### 5.1 已通过

- `bash compass/tools/redcap-intent-coverage-check.sh .dev-task.md`
- `bash compass/tools/redcap-pm-gate-check.sh strict codex .dev-task.md`
- `bash compass/tools/redcap-multi-session-acceptance.sh intent-coverage-check`
- `bash compass/tools/redcap-execution-guarantee-check.sh`
- `bash compass/tools/redcap-mechanism-vitality-check.sh`
- `bash compass/tools/redcap-diagnose.sh .dev-task.md`
- `bash compass/tools/redcap-spec-check.sh "$PWD"`
- `bash compass/tools/redcap-multi-session-acceptance.sh all`

### 5.4 完成等级（禁止混报）

| 层级 | 状态 | 说明 |
|---|---|---|
| 已实现 | 是 | 硬门、文档、模板、诊断、回归入口已落地 |
| 已自检 | 是 | targeted acceptance 与 spec/diagnose 已跑 |
| 已独立验收 | 否 | 本轮是小范围控制面补丁，未单独启动 Prism quorum |
| 已正式完成 | 否 | full acceptance、spec-check 已通过；仍待提交后生成 closeout receipt |

## 七、经验沉淀

### 7.3 Evolution Factory 候选处理

| 候选 | 状态 | 处理结果 |
|---|---|---|
| `EVO-2026-04-26-001` 原始意图覆盖审计 | promoted | 已晋升为 `compass/knowledge/lessons.md` 的 L-118 |

## 八、附录

### 8.1 关键证据路径

| 证据 | 路径 |
|---|---|
| 任务卡 | `.dev-task.md` |
| 本报告 | `compass/docs/task-reports/2026-04-26-original-intent-coverage-gate.md` |
| 硬门脚本 | `compass/tools/redcap-intent-coverage-check.sh` |
| PM Gate 接入 | `compass/tools/redcap-pm-gate-check.sh` |
| 经验沉淀 | `compass/knowledge/lessons.md` |

## 六、遗留问题与下一步

- 该硬门能阻断“没有声明覆盖关系”的任务卡，但不能单独替代 Prism Planning Review 对复杂计划做语义审查。
- RedCap 物理目录迁移、独立 runtime / CLI 化仍未执行；后续要另立迁移任务。

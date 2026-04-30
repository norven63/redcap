# 任务完成报告：Layer B 中插需求重排决策可见化

**报告日期**：2026-04-27
**执行者**：Cap（Codex.app）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：Layer B 的中插需求账本新增“重排决策摘要”强门。
- 详情：只要 `.dev-task.md` 中存在 `## 中插需求账本`，就必须同时存在 `## 中插需求重排决策摘要`，并为每个 `U<n>` 写明处置、决策理由、全景影响和用户可见表达。

### 0.2 上一步完成的是

- 上一步完成的是：P1-4 将公共库从临时推送工作区补成 `/Users/norven/.claude/skills/redcap-arsenal` 耐久本地仓库，并初始化 `users/Norven/`。
- 本轮补齐的是：P1-4 的处理本身合理，但当时对用户没有显式展示“为什么这个中插需求应立即执行、对父任务全景有什么影响”，因此需要把这个解释升级成机器检查项。

### 0.3 下一步计划做的是

- 下一步计划做的是：本轮只完成 P2-5，不推进 P2-4 首启用户/Agent 初始化，也不推进 P3-1/P3-2 长期治理项。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：中插需求入账 → 重排决策摘要 → checker fail-closed → acceptance → Prism review → closeout receipt。
- 当前所在位置：`redcap-system-migration-parent / P2-5 / change-intake-replan-visibility`。

---

## 一、需求背景

### 1.1 原始问题

用户追问 P1-4 公共库中插需求时指出：如果 Cap 只是执行了最新插入项，却没有说明它是否经过父任务全景重排，就会看起来像“中插了就无脑高优执行”。本轮目标不是补一段对话解释，而是让后续任务卡必须留下可审计的重排判断。

### 1.2 根因

上一轮 `## 中插需求账本` 已经能记录 U 项的类型、优先级、处理方式和状态，但它没有强制写出“为什么这样排”。因此机器能知道“处理方式是什么”，用户和后续 Agent 却不一定能看到“决策依据是什么、影响了哪些父任务项、应该如何对用户表达”。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 用户认可先加固“中插需求重排可见化”机制，再继续主线 |
| 已覆盖 | policy、checker、acceptance、工作流说明、文件字典、执行保障、父任务账本、报告和 lesson |
| 未覆盖/延期 | 不处理 P2-4 首启身份初始化；不处理 P3-1/P3-2；不迁移历史资产 |
| 用户可见边界 | 本轮能阻止“有中插表格但没有解释为什么这样排”；不能物理拦截宿主 Agent 每一句实时回复 |

---

## 二、方案讨论

### 2.1 可选方案

| 方案 | 描述 | 优点 | 缺点 | 结论 |
|---|---|---|---|---|
| A | 只在对话里解释 P1-4 为什么立即执行 | 最快 | 无法被后续任务卡、checker 或 closeout 审计 | 拒绝 |
| B | 只在 `## 中插需求账本` 里继续扩字段 | 改动较小 | 表格会越来越臃肿，且不适合写用户可见表达 | 不足 |
| C | 保留账本负责结构化状态，新增重排决策摘要负责解释依据 | 机器可查，人类可读，边界清晰 | 需要补 checker 和 acceptance | 采纳 |

### 2.2 采纳决策

账本继续回答“这个 U 项是什么状态”，重排决策摘要回答“为什么这样处理、对全景有什么影响、应该如何向用户说清”。这两层分开后，既不会把表格变成散文，也不会让用户只能通过追问来判断 Cap 是否真的做了全景重排。

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更摘要 |
|---|---|
| `references/layerb-change-intake-policy.json` | 新增 `replan_decision_section` 与必填字段 |
| `compass/tools/redcap-change-intake-check.py` | 检查每个 U 项都有对应重排决策摘要，并校验 `处置` 与账本处理方式一致 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 补完整样例、缺少摘要、缺少/错配摘要等回归 |
| `references/runtime-memory-architecture.md` | 将“重排决策摘要”纳入 `REPLAN_REVIEW → EXECUTING` 转移条件 |
| `references/execution-guarantees.json` | 将用户可见重排解释纳入执行保障规则 |
| `references/file-lookup-dictionary.md` / policy | 更新 change-intake 文件索引语义 |
| `references/redcap-parent-task-ledger.md` | 登记 P2-5 子任务完成边界 |
| `references/parent-receipt-aggregation-policy.json` | 将 P2-5 纳入父任务聚合策略，但父任务仍 incomplete |
| `compass/knowledge/lessons.md` | 新增 L-135，沉淀中插需求必须解释重排依据 |

### 3.2 强门规则

如果任务卡出现 `## 中插需求账本`：

- 必须同时出现 `## 中插需求重排决策摘要`。
- 每个 `U<n>` 必须有 `### U<n>` 小节。
- 每个小节必须写 `处置`、`决策理由`、`全景影响`、`用户可见表达`。
- `处置` 必须和账本里的 `处理方式` 一致。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| 中插需求账本 | `.dev-task.md` 的 `## 中插需求账本` | 长任务执行中用户追加的新要求、纠偏或约束变化，必须先写成可检查表格 |
| U 项 | `U1 / U2 / ...` | 执行期用户插入项的编号，方便和原始 Q/R 需求区分 |
| 重排决策摘要 | `.dev-task.md` 的 `## 中插需求重排决策摘要` | 解释每个 U 项为什么立即合并、拆子任务、延期或拒绝，以及它影响了哪些父任务范围 |
| change-intake checker | `redcap-change-intake-check.sh` | 机器检查器，负责阻止“只填了处理方式但没解释决策依据”的任务卡继续收口 |
| 父任务聚合策略 | `parent-receipt-aggregation-policy.json` | 判断子任务完成后父任务是否仍 incomplete；本轮 P2-5 完成但父任务仍不可宣称完成 |

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|---|---|---|---|
| 1 | 父任务完成边界 | P2-5 只是子任务完成；P2-4/P3-1/P3-2 仍 deferred，父任务仍 incomplete | P1 |
| 2 | 宿主物理拦截边界 | 本轮是 repo-owned gate，不是 Codex.app 每句回复的物理 veto hook | P1 |
| 3 | 棱镜建议处理 | Kimi/Claude 的 acceptance 覆盖建议已补回归，无 blocker 遗留 | P1 |

---

## 五、验证结果

| 验证项 | 命令 | 结果 |
|---|---|---|
| policy JSON | `python3 -m json.tool references/layerb-change-intake-policy.json` | 通过 |
| checker 编译 | `python3 -m py_compile compass/tools/redcap-change-intake-check.py` | 通过 |
| 当前任务 change-intake | `bash compass/tools/redcap-change-intake-check.sh .dev-task.md` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh change-intake-check` | 通过 |
| PM Gate / intent / 字典 / 父任务聚合 / execution guarantee | `redcap-pm-gate-check`、`redcap-intent-coverage-check`、`redcap-file-lookup-dictionary-check`、`redcap-parent-receipt-aggregation-check`、`redcap-execution-guarantee-check` | 通过 |
| legacy asset migration dry-run | `bash compass/tools/redcap-legacy-asset-migration-check.sh` | 通过，已同步 task-reports 与 prism-runs 计数 |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |
| Prism review | `20260427-layerb-change-intake-replan-visibility-gate` | Kimi + Claude Code 双路通过，0 blocker；低风险 acceptance 覆盖建议已采纳 |

---

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| 执行承诺账本 | 6/6 已完成，closeout complete 时再由 runtime 绑定当前提交 |
| 棱镜验收 | 通过：`20260427-layerb-change-intake-replan-visibility-gate`，Kimi + Claude Code，2 family，0 blocker |
| closeout summary | 提交后生成 |
| closeout receipt | 提交后生成 |

### 5.4 完成等级（禁止混报）

| 项 | 结论 |
|---|---|
| 已实现 | 是，核心 policy/checker/acceptance/docs 已落地 |
| 已自检 | 是，targeted acceptance、spec-check、diagnose 均通过 |
| 已独立验收 | 是，Kimi + Claude Code 双路 Prism review 通过 |
| 已正式完成 | 待提交与 closeout receipt |

---

## 六、遗留问题与下一步

| 问题 | 状态 |
|---|---|
| P2-4 首次启动初始化用户与 AI Agent 信息 | deferred，未在本轮推进 |
| P3-1 GraphRAG / 向量检索阈值研究 | deferred，未在本轮推进 |
| P3-2 runtime receipt evidence correspondence hardening | deferred，未在本轮推进 |

---

## 七、经验沉淀

新增 lesson：L-135《中插需求不能只入账，还要显性说明重排理由》。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|---|---|---|---|
| 中插需求重排决策可见化 | 用户追问 P1-4 是否“中插即无脑高优”暴露的信任缺口 | no-promote：已直接晋升为 change-intake policy、checker、acceptance 与 L-135；无新增候选需要进入候选池 | `references/layerb-change-intake-policy.json`、`compass/tools/redcap-change-intake-check.py`、`compass/knowledge/lessons.md` |

---

## 八、附录

### 附录 A：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|---|---|---|---|
| review | change-intake replan visibility gate | Kimi + Claude Code 双路通过，0 blocker；发现的 acceptance 覆盖建议已补回归 | `prism/runs/20260427-layerb-change-intake-replan-visibility-gate/` |

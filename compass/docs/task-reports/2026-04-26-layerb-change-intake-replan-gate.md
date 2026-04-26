# 任务完成报告：Layer B 中插需求重计划强门

**报告日期**：2026-04-26
**执行者**：Cap（Codex.app 主 Agent）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：Layer B 已新增中插需求账本、重计划状态、父子任务完成边界和机器检查器，并接入 PM Gate、diagnose、spec-check、execution guarantees、FSM、自检、current-status 与 acceptance。
- 详情：长任务执行期如果用户新增需求、纠偏、约束或优先级变化，必须先写入 `U<n>` 与 `## 中插需求账本`，再重排确认需求、计划和验收；子任务只能声明自己完成，不能冒充父任务完成。

### 0.2 上一步完成的是

- 上一步完成的是：发布/打包前安全 gate 已 closeout 并提交到 `cc9b484`；本轮是用户针对“中插需求打乱长任务流程”的更高层治理任务，不能复用发布安全 gate 的完成态。

### 0.3 下一步计划做的是

- 下一步计划做的是：提交本轮变更，并由 closeout runtime 生成正式 receipt。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：重新立项 → 设计 `CHANGE_INTAKE / REPLAN_REVIEW` → 新增 policy/checker → 接入 PM Gate / diagnose / spec / FSM / status / guarantees → acceptance → 报告与 lesson → Prism → closeout receipt。
- 当前所在位置：实现、targeted acceptance、full acceptance、spec-check、diagnose 与 Kimi resource-limited Prism review 均已完成，处于提交和 closeout receipt 收口点。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 我发现几个问题，我挨个说：
> 1. 刚才我问的“是不是不在LayerB”里，是指你前面开始执行“R0-R22”的时候，因为我觉得你至少应该全部完成后才会汇报才对，但是中途却突然打断向我汇报阶段性成果。加上你似乎没有完整的立项、写需求（我不知道是不是“没有写”，可能是我看漏了，这点你可以仔细谨慎的审核），所以我才说是不是“不在LayerB里执行任务”
> 2. 在一个超长任务没有完成之前，我加入了新需求（例如你现在这种“非预期的中途打断”动作，给了我中插新需求的机会；再例如之前你汇报R0-R20计划的时候，我在评审时新增了2个需求）时，你会优先把新需求独立完成，并且幻觉成“所有任务已完毕“的假象（至少我认为你这属于幻觉假象行为，但是你可能会解释说这是xxx原因导致的任务中断），然后中断向我汇报。我记得你说过，这种中插需求的场景，应该是先把需求融合到整体需求清单中，并按照当前已经完成的进度，重新评估执行优先级，然后接着继续执行未完成的任务。说白了，LayerB现在是不是缺乏一个成熟的“中插任务”流程，这个成熟的流程应该包括多个核心节点，例如需求整个、优先级重排等等（我说的不全，你可以从工程规范角度进行专业而详细的补全），而不是现在这样，来的新需求后就直接去最高优先级立即完成，然后假装所有任务都完成并中断向我汇报
> 3. 感觉目前的需求进度有点被“我多次中插任务”给打乱和污染了，你看看是否需要先把“LayerB成熟安全的中插任务流程体系”设计和开发完毕，然后重新评估整个计划体系，是否因为被我的中插行为而引发了哪些bug和需要调整的地方
>
> 好的，那么你能独立完成这些规划吗？还需要我人工介入什么决策吗
>
> 那么，开始吧

### 1.2 本次问题的表层现象

| 现象 | 说明 |
|------|------|
| 阶段性汇报像终局汇报 | 长任务未全部完成时，局部成果或子任务成果被讲得像“全部完成” |
| 最新中插项抢占父任务 | 用户插入一个新要求后，系统容易先完成最新要求，再忽略父任务剩余范围 |
| 任务卡和对话不同步 | 新需求如果只在对话里存在，后续回归只能验证旧任务卡，而不是验证真实用户意图 |
| 父子任务边界不清 | 子任务 closeout 生成 receipt 后，状态面容易被误读成父任务也完成 |

### 1.3 更底层的根因

根因不是“某个脚本少一行”，而是 Layer B 原来只有 PM Gate 的文字规则：“新增需求要补原始输入和确认需求”。它没有对应的执行期状态、账本格式、重计划审核、父子任务完成声明、diagnose/spec-check 消费链。也就是说，规则存在，但没有被提升为可阻断的控制面。

R0-R22 本身有 `.dev-task.md`、任务报告、回归和 receipt，因此不能简单说它完全不在 Layer B；真正的问题是：当 R0-R22 后续又发生发布安全 gate、再发生本轮中插流程治理时，系统缺少“新要求进入父任务还是拆子任务”的机器化决策与可见状态面。

### 1.4 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 先把成熟安全的中插任务流程体系设计并开发完毕，再评估计划体系是否被此前中插污染 |
| 已覆盖 | 中插账本、重计划状态、父子任务完成声明、机器 checker、PM Gate/diagnose/spec/FSM/status/guarantee/acceptance 接线、R0-R22 污染边界复盘 |
| 未覆盖/延期 | 不删除历史资产、不重写 R0-R22 旧 receipt、不执行远端发布 |
| 用户可见边界 | 本轮修的是“未来和当前任务流如何防复发”；旧报告仍作为历史证据保留 |

---

## 二、方案讨论

### 2.1 可选方案

| 方案 | 描述 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 继续只在 CONTRIBUTING 里补规则 | 快 | 仍靠 Agent 记忆，无法阻断复发 | 拒绝 |
| B | 新增中插账本 + checker，但不接 FSM | 能挡一部分漏记 | 状态面仍看不见 CHANGE_INTAKE / REPLAN_REVIEW | 不足 |
| C | 账本 + checker + FSM 状态 + PM Gate/diagnose/spec/acceptance 接线 | 能记录、重计划、回归和状态展示 | 改动面更广，需要回归 | 采纳 |

### 2.2 本轮设计

中插需求不再被当成“顺手做个新任务”。它必须经过三步：

1. `CHANGE_INTAKE`：把执行期新增需求、纠偏、约束变更或优先级变化写成 `U<n>`，并登记类型、阻塞性和优先级。
2. `REPLAN_REVIEW`：决定 U 项是合并当前任务、拆成子任务、替换范围、延期跟进，还是拒绝出界；同时更新确认需求、计划和验收。
3. `RESUME_EXECUTING`：重计划通过后才恢复执行；若 U 项未收口、阻塞项被延期、或子任务声称父任务完成，则 fail-closed。

### 2.3 R0-R22 与发布安全 gate 的复盘结论

| 对象 | 状态 | 本轮判断 |
|------|------|----------|
| R0-R22 执行层治理 | 有任务报告、回归和 receipt，提交为 `7c57451` | 已完成它声明的本地控制面范围，但它不是后续所有新需求的永久完成证明 |
| 发布/打包安全 gate | 独立任务，提交为 `ce01a30` / `cc9b484` | 作为后续新增需求处理是合理的，但当时缺少“从父任务拆出子任务”的显式账本 |
| 本轮中插治理 | 新任务卡 `layerb-change-intake-replan-gate` | 用来修复上述流程缺口，防止之后再靠人工盘问发现遗漏 |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更摘要 |
|------|---------|
| `references/layerb-change-intake-policy.json` | 新增中插需求处理策略、合法状态、处理方式和父子任务完成声明 |
| `compass/tools/redcap-change-intake-check.py` / `.sh` | 新增 fail-closed checker，校验 U 项账本、未收口状态、重计划更新和父任务冒充风险 |
| `compass/tools/redcap-pm-gate-check.sh` | PM Gate 消费 change-intake checker，立项/重读时挡漏账 |
| `compass/tools/redcap-diagnose.sh` / `redcap-spec-check.sh` | 全局诊断和 spec 回归消费 change-intake gate |
| `compass/tools/redcap-layerb-closeout-runtime-check.sh` | closeout runtime 自检显式消费 `change-intake --mode closeout`，不只依赖 diagnose 间接覆盖 |
| `compass/tools/redcap-layerb-fsm.py` / `redcap-layerb-fsm-check.sh` | 新增 `CHANGE_INTAKE` / `REPLAN_REVIEW` 状态与契约自检 |
| `compass/tools/redcap-current-status.py` | 状态面新增“中插需求 / 重计划”摘要 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 新增 targeted acceptance，覆盖缺账本、未收口、父任务冒充完成 |
| `references/execution-guarantees.json` / checker | 新增 P0 执行保障 `layerb-change-intake-replan-gate` |
| `compass/CONTRIBUTING.md` / `.core.md` / `references/agent-constraints.md` | 更新中插需求、重计划、父子任务边界和中途汇报纪律 |
| `references/runtime-memory-architecture.md` | 将中插流程纳入 Layer B FSM 全景 |
| `references/file-lookup-dictionary.md` / policy | 补入新 policy/checker 的查阅入口 |
| `bin/redcap` | 新增 `change-intake` CLI facade |
| `compass/knowledge/lessons.md` | 新增 L-124，沉淀问题源、解决方案和最后效果 |

### 3.2 技术实现要点

`redcap-change-intake-check.sh` 会读取 `.dev-task.md` 的 `## 中插需求账本`。如果原始输入出现 `### U1` 这类执行期追加项，或 active slice 进入中插相关状态，但没有账本，检查会失败。

账本行必须说明 U 项的处理方式：合并当前任务、拆成子任务、替换范围、延期跟进、拒绝出界。对于合并或替换范围，确认需求、计划和验收都必须更新。对于拆子任务，必须留下子任务证据。terminal 阶段仍有 `captured / replanning / blocked` 状态会失败。

父子任务边界通过 `parent_completion_claim` 明确表达。子任务可写 `child-only`，表示只完成自己；`parent-complete` 目前会 fail-closed，因为 RedCap 还没有专门的父任务 receipt gate 能证明父任务也已闭环。

Kimi reviewer 建议把 change-intake 也显式接入 `layerb-closeout-runtime-check`，避免只靠 diagnose 间接兜底。本轮已采纳并回归通过。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| 中插需求账本 | `.dev-task.md` 的 `## 中插需求账本` | 长任务执行中用户新插入的要求，不再只留在聊天里，而是写成可检查表格 |
| U 项 | `U1 / U2 / ...` | User-inserted change，表示执行期间新增的用户变化项 |
| `CHANGE_INTAKE` | Layer B FSM 状态 | 暂停直接实现，先把新变化入账 |
| `REPLAN_REVIEW` | Layer B FSM 状态 | 审核新变化如何影响原计划、验收和优先级 |
| `parent_completion_claim` | `.dev-task.md` 元数据 | 子任务完成时，明确它是否只是子任务完成；默认不能宣称父任务完成 |
| change-intake checker | `redcap-change-intake-check.sh` | 机器检查器，负责挡漏账、未收口 U 项和父任务冒充完成 |

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 旧历史 receipt | 本轮不重写旧 receipt；旧 receipt 仍只证明对应 confirmed hash 已完成 | P1 |
| 2 | 父任务 receipt gate | 未来如果需要“子任务完成自动推进父任务完成”，应另立父任务 receipt 聚合 gate；本轮先 fail-closed | P1 |

---

## 五、验证结果

| 验证项 | 命令 | 结果 |
|--------|------|------|
| Change-intake 当前任务卡 | `bash compass/tools/redcap-change-intake-check.sh .dev-task.md --mode closeout` | 通过 |
| Change-intake targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh change-intake-check` | 通过 |
| Layer B FSM contract | `bash compass/tools/redcap-layerb-fsm-check.sh` | 通过 |
| Execution guarantees | `bash compass/tools/redcap-execution-guarantee-check.sh` | 通过 |
| Drift scope reanchor | `bash compass/tools/redcap-drift-check.sh reanchor/strict codex .dev-task.md` | 通过 |
| 全局 spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |
| full acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过，最终 `ACCEPTANCE_OK` |
| Prism review | Kimi resource-limited review + `redcap-prism-acceptance-check.sh` | `resource-limited-pass` |

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已由 closeout runtime check 同步，正式 complete 时再核对 |
| 棱镜验收 | `resource-limited-pass`，run=`20260426-layerb-change-intake-resource-limited` |
| closeout summary | 待提交后生成 |
| closeout receipt | 待提交后生成 |
| rescue audit（如有） | 暂无 blocker |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是，核心 gate 与接线已完成 |
| 已自检 | 是，targeted / full acceptance、spec-check、diagnose 均通过 |
| 已独立验收 | 是，Kimi resource-limited Prism review 通过 |
| 已正式完成 | 否，待提交与 closeout receipt |

### 5.5 回归中发现并修复的问题

| 问题 | 根因 | 修复 |
|------|------|------|
| full acceptance 首次失败：`bin/redcap` drift 超范围 | `.dev-task.md` 允许修改范围漏了 `bin/**` | 补入允许范围并执行 drift reanchor |
| full acceptance 第二次失败：spec-check fixture 缺新强门依赖 | 最小 spec fixture 没复制 package safety / change-intake 依赖 | 更新 `create_spec_registry_fixture`，补最小 package policy 与 checker 文件 |
| Kimi review 建议 closeout runtime 自检直连 gate | 原实现通过 diagnose 间接覆盖，语义不够同构 | `redcap-layerb-closeout-runtime-check.sh` 显式调用 `redcap-change-intake-check.sh --mode closeout` |

---

## 六、遗留问题与下一步

| 问题 | 说明 |
|------|------|
| 父任务聚合 gate | 当前只有子任务不得冒充父任务完成；未来如需自动聚合父任务，应另设父任务 receipt 聚合机制 |
| 宿主实时打断能力 | Codex.app 仍没有 repo-owned reply veto hook；本 gate 能在任务卡、diagnose、spec、closeout 阶段挡错，不能物理阻止每一句回复 |

---

## 七、经验沉淀

新增 lesson：L-124《执行期中插需求必须先重计划，不能让最新子任务覆盖父任务》。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 中插需求重计划强门 | 用户多轮追问暴露的 Layer B 流程暗疾 | 无新增候选：直接晋升为 execution guarantee 与 lesson，无未处理 candidate | `references/execution-guarantees.json`、`compass/knowledge/lessons.md` |

---

## 八、附录

### 附录 A：Commits

```text
待提交本轮最终变更
```

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| resource-limited | 中插需求重计划 gate 是否存在 fail-open blocker | Kimi pass，无 blockers；Gemini timeout，Copilot frozen，Codex unsupported，Claude-code timeout | `prism/runs/20260426-layerb-change-intake-resource-limited/` |

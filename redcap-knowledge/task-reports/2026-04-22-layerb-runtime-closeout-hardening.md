# 任务完成报告：Layer B 统一 runtime / 承诺账本 / receipt 收口 / rescue 审计

**报告日期**：2026-04-22  
**执行者**：Cap（Codex 宿主 + RedCap-native 控制面）  
**报告版本**：v1.0

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：Layer B 已从“协议写清楚但终态收口仍靠多脚本分散执行”，升级到“统一 closeout runtime + 承诺账本 + receipt + rescue audit”的可检查闭环。

### 0.2 上一步完成的是

- 上一步完成的是：上一刀已把 Layer B 生命周期和运行时记忆架构显性化；本轮是在此基础上把终态收口真正接进 runtime，而不再只停留在文档口径。

### 0.3 下一步计划做的是

- 下一步计划做的是：无当前 tranche 级 blocker；后续若继续治理，重点会转到宿主 reply-path 边界与更大范围的 archaeology/tracking authority 审判。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图：根因审计 → closeout runtime 设计 → promise ledger / receipt / rescue audit 实现 → 旧资产处置策略收口 → 回归与独立审视 → 终局报告。
- 当前所在位置：本 tranche 已收口完成，进入可审可接盘状态。

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 见 [.dev-task.md](/Users/norven/.claude/skills/redcap/.dev-task.md) 中 `## 原始输入（用户原文）` 段。

### 1.2 触发背景

这轮不是在修一个“飞书偶尔漏发”的点状 bug，而是在修一条结构性断裂：

- RedCap 对“用户原始需求”约束很强；
- 但对“Agent 在执行中自己追加的承诺”约束不够强；
- 同时 Layer B 的终态收口虽然已有 `on-complete / session-end / pending closure / closure-ledger / task report / notify` 这些零件，却没有被统一 runtime 物理收口。

这正是“部分兑现 + 过早收口”会发生的根本原因。

## 二、方案讨论

### 2.1 问题分析

本轮把根因收敛成 4 条：

1. **承诺只活在对话里**：Agent 自追加承诺没有进入控制面账本。  
2. **终态收口分散**：`on-complete / session-end / notify / pending closure / receipt` 没有被单一 runtime 驱动。  
3. **完成不是 receipt-driven**：没有 receipt 时，系统仍可能“看起来已完成”。  
4. **rescue 不够强**：漏收尾时，没有至少一条强入口负责补 receipt 或补 blocker。

### 2.2 方案选项

- **方案 A：继续给现有脚本打补丁**  
  不采用。因为这只能继续累积“零件越来越多，但谁在主导终态收口仍不清楚”的复杂度。

- **方案 B：新增统一 closeout runtime，同时保留旧账本分层**  
  采用。把 `on-complete / session-end / promise ledger / receipt / rescue audit` 收进同一条 runtime，但不抹掉 `.dev-task.md`、`pending-closure`、`closure-ledger`、task report 之间原本合理的分层。

### 2.3 决策结果

最终采用 **“统一 runtime + 承诺账本 + receipt 收口 + rescue 审计”**：

- `closeout-cap.sh` / `redcap-layerb-closeout-runtime.sh` 成为 Layer B 终态统一入口
- `.dev-task.md` 的 `## 执行承诺账本` 成为 Agent 自追加承诺的真相源
- `promise-ledger/*.json` 成为可核对派生账本
- `receipt / summary / audit` 成为终态物理证据
- `redcap-diagnose.sh` 成为当前 tranche 的 rescue 强入口

## 三、落地结果

### 3.1 变更区域

这轮主要改了 4 组东西：

- **runtime 入口与实现**
  - [closeout-cap.sh](/Users/norven/.claude/skills/redcap/closeout-cap.sh)
  - [redcap-layerb-closeout-runtime.sh](/Users/norven/.claude/skills/redcap/compass/tools/redcap-layerb-closeout-runtime.sh)
  - [redcap-layerb-closeout-runtime.py](/Users/norven/.claude/skills/redcap/compass/tools/redcap-layerb-closeout-runtime.py)
  - [redcap-layerb-closeout-runtime-bridge.sh](/Users/norven/.claude/skills/redcap/compass/tools/redcap-layerb-closeout-runtime-bridge.sh)
  - [redcap-layerb-closeout-runtime-check.sh](/Users/norven/.claude/skills/redcap/compass/tools/redcap-layerb-closeout-runtime-check.sh)

- **runtime 接线**
  - [redcap-layerB-task-complete-guard.sh](/Users/norven/.claude/skills/redcap/compass/tools/redcap-layerB-task-complete-guard.sh)
  - [redcap-diagnose.sh](/Users/norven/.claude/skills/redcap/compass/tools/redcap-diagnose.sh)
  - [redcap-spec-check.sh](/Users/norven/.claude/skills/redcap/compass/tools/redcap-spec-check.sh)
  - [redcap-execution-guarantee-check.py](/Users/norven/.claude/skills/redcap/compass/tools/redcap-execution-guarantee-check.py)
  - [redcap-hook-contract-check.sh](/Users/norven/.claude/skills/redcap/compass/tools/redcap-hook-contract-check.sh)
  - [redcap-current-status.py](/Users/norven/.claude/skills/redcap/compass/tools/redcap-current-status.py)

- **回归与验收**
  - [redcap-multi-session-acceptance.sh](/Users/norven/.claude/skills/redcap/compass/tools/redcap-multi-session-acceptance.sh)

- **权威入口与设计说明**
  - [README.md](/Users/norven/.claude/skills/redcap/README.md)
  - [ARCHITECTURE.md](/Users/norven/.claude/skills/redcap/ARCHITECTURE.md)
  - [CONTRIBUTING.core.md](/Users/norven/.claude/skills/redcap/compass/CONTRIBUTING.core.md)
  - [CONTRIBUTING.md](/Users/norven/.claude/skills/redcap/compass/CONTRIBUTING.md)
  - [2026-04-22-layerb-closeout-runtime-and-promise-ledger-design.md](/Users/norven/.claude/skills/redcap/compass/docs/specs/2026-04-22-layerb-closeout-runtime-and-promise-ledger-design.md)
  - [runtime-memory-architecture.md](/Users/norven/.claude/skills/redcap/references/runtime-memory-architecture.md)
  - [runtime-memory-architecture.md](/Users/norven/.claude/skills/redcap/compass/knowledge/runtime-memory-architecture.md)
  - [execution-guarantees.json](/Users/norven/.claude/skills/redcap/references/execution-guarantees.json)
  - [task-report-template.md](/Users/norven/.claude/skills/redcap/references/task-report-template.md)

### 3.2 技术实现要点

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| closeout runtime | `compass/tools/redcap-layerb-closeout-runtime.py` | Layer B 终态的统一收尾引擎，负责决定任务能否正式完成 |
| 执行承诺账本 | `.dev-task.md` 的 `## 执行承诺账本` | Agent 在执行中自己追加答应要做的事，closeout 前必须逐项核对 |
| promise ledger | `promise-ledger/*.json` | 由 runtime 从 Markdown 承诺清单同步出的机器可读派生账本 |
| receipt | `receipts/*.json` | 正式完工凭证；没有它，就不能说 completed |
| rescue audit | `audit-open` + `redcap-diagnose.sh` | 收尾漏掉时的补救路径，能补收据就补，不能补就补 blocker |

#### 3.2.2 统一 runtime

`closeout-cap.sh` 是人类和 Agent 的根目录短入口；真正的确定性逻辑在 `redcap-layerb-closeout-runtime.py`：

- `sync-promises`
- `status`
- `complete`
- `audit-open`

其中 `complete` 的标准路径是：

1. 从 `.dev-task.md` 读取 task identity
2. 同步 `## 执行承诺账本` 到 `promise-ledger`
3. 先检查承诺是否已全部兑现
4. 调 `redcap-on-complete.sh`
5. 调 `redcap-layerB-session-end.sh`
6. 只有在 **承诺已清 + pending closure 已清 + receipt 已写成** 时才标记 completed

#### 3.2.3 承诺账本

承诺不再只活在对话里，而是被拆成两层：

- `.dev-task.md`：人类/Agent 可编辑的真相源
- `promise-ledger/*.json`：runtime 每次同步出来的派生账本

closeout runtime 会在 `complete` 和 `status` 前先同步 promise ledger；只要还有未勾选承诺，就会 block，不给 receipt。

#### 3.2.4 receipt / summary

完成时会写两份物理资产：

- `summaries/*.md`
- `receipts/*.json`

这样“完成”不再依赖最终回复或 task report 的口头措辞，而是依赖 receipt 是否真实落盘。

#### 3.2.5 rescue 审计

`audit-open` 只做两件事：

- **repair-receipt**：如果终态已经实际完成，只是 receipt 丢了，就补写 receipt / summary
- **block-and-audit**：如果终态并未真正闭环，就补 blocker / audit，而不是补假 receipt

当前 tranche 选择的强入口是：

- [redcap-diagnose.sh](/Users/norven/.claude/skills/redcap/compass/tools/redcap-diagnose.sh)

当 diagnose 发现：

- receipt 缺失
- 且 runtime state / active_slice 已进入 terminal 区域

就会主动执行：

```bash
bash compass/tools/redcap-layerb-closeout-runtime.sh audit-open --mode diagnose
```

这就是现在的 diagnose-rescue 路径。

### 3.3 本轮通过 review 实际补掉的真问题

这轮不是一把改完，而是被独立审视逼出了 3 个真修补：

1. **最初没有强 rescue 入口**  
   首轮轻量独立审视指出：`audit-open` 只存在于手动入口，没真正挂到 stop/session-end/diagnose 其中之一。  
   修复：把 `redcap-diagnose.sh` 升级成 diagnose-rescue 强入口。

2. **`session-end` 失败时只写 audit/ledger，不显式写回 pending closure**  
   这会让 blocker 缺少未清义务真相源。  
   修复：`command_complete` 在 `session-end` 非零返回或 pending 仍存在时，先 `bridge_write_pending(...)` 再写 ledger / audit。

3. **`audit-open` 修 receipt 时对成功证明过窄**  
   原先只认 `session-end pass`，而真实成功路径里最后一个相关 proof 往往是 `closeout-runtime pass`。  
   修复：`can_repair_receipt(...)` 现在同时接受 `session-end pass` 和 `closeout-runtime pass`。

### 3.4 旧资产处置结论

这轮没有搞“推倒重来”，而是按分层处理。

### 4.1 保留

这些继续保留为历史证据，不批量迁移、不重写：

- 历史 task report
- `pending-closure/*.state`
- `closure-ledger/*.log`
- 既有 Prism report / run evidence

### 4.2 翻译

这些权威入口必须翻译到新机制口径：

- `README.md`
- `ARCHITECTURE.md`
- `CONTRIBUTING.core.md`
- `CONTRIBUTING.md`
- `runtime-memory-architecture` 两份
- `task-report-template.md`
- `execution-guarantees.json`

翻译的核心，不是说旧脚本消失了，而是把它们从“用户/Agent 自己拼接的主入口”降级成“统一 runtime 内部阶段”。

### 4.3 删除/降级

本 tranche **没有物理删除历史证据类资产**。  
只做了两种更安全的动作：

- 把旧口径降级成 internal phase / historical note
- 用新入口覆盖旧说法，避免权威入口继续漂移

也就是说，这轮旧资产处置的原则是：

**保留证据、翻译入口、谨慎降级，不搞一锅端删除。**

## 四、人工审核要点

这轮最值得人工盯的 4 件事：

1. `closeout runtime` 是否真的成为 Layer B 终态主入口，而不是只是又多了一层壳
2. `.dev-task.md` 的 `执行承诺账本` 是否会在后续任务里被稳定使用，而不是再次退回只活在对话里
3. diagnose-rescue 是否仍保持“能补收据时补收据，不能补时补 blocker”，而不是偷偷把未闭环任务写成 completed
4. 旧资产处置是否持续遵守“证据保留、入口翻译、不大删”的策略

## 五、验证结果

### 6.1 自动化验证

实际跑过并通过：

```bash
bash compass/tools/redcap-docs-catalog.sh generate
bash compass/tools/redcap-docs-catalog.sh check
bash compass/tools/redcap-spec-check.sh "$PWD"
bash compass/tools/redcap-diagnose.sh .dev-task.md
git diff --check

bash compass/tools/redcap-multi-session-acceptance.sh task-complete-guard-triggers-closeout-runtime
bash compass/tools/redcap-multi-session-acceptance.sh layerb-closeout-runtime-promise-ledger-blocks
bash compass/tools/redcap-multi-session-acceptance.sh layerb-closeout-runtime-complete-writes-receipt
bash compass/tools/redcap-multi-session-acceptance.sh layerb-closeout-runtime-session-end-failure-writes-pending
bash compass/tools/redcap-multi-session-acceptance.sh layerb-closeout-runtime-audit-open-repairs-receipt
bash compass/tools/redcap-multi-session-acceptance.sh layerb-closeout-runtime-audit-open-blocks-unresolved
bash compass/tools/redcap-multi-session-acceptance.sh diagnose-auto-repairs-closeout-receipt
bash compass/tools/redcap-multi-session-acceptance.sh diagnose-overview
bash compass/tools/redcap-multi-session-acceptance.sh current-status-overview
bash compass/tools/redcap-multi-session-acceptance.sh hook-contract-check
```

### 6.2 独立审视 / 棱镜记录

本轮做的是 **轻量独立审视**，不是 formal Prism quorum。

#### 第一轮：`review-layerb-closeout-runtime-20260422`

- `kimi`：返回了非 JSON 但有价值的审查内容，指出 **rescue audit 还没接入强入口**，同时暴露出“大 diff 截断让 reviewer 半盲审”的问题
- `copilot`：长 prompt 超时，记为 absent

#### 第二轮：`review-layerb-closeout-runtime-followup-20260422`

- 先用更完整、更聚焦的材料包复审
- `kimi` 和 `copilot` 都返回了 **无 blocker** 的 verdict
- `copilot` 额外指出一个 blind spot：`diagnose-auto-repairs-closeout-receipt` 还在用手工 ledger 夹具  
  该盲点随后已被我改成“真实 complete 成功 → 删除 receipt → diagnose 修复”的端到端路径，并重新跑绿 acceptance

相关证据：

- [review-layerb-closeout-runtime-20260422/session-registry.yaml](/Users/norven/.claude/skills/redcap/prism/runs/review-layerb-closeout-runtime-20260422/session-registry.yaml)
- [review-layerb-closeout-runtime-followup-20260422/session-registry.yaml](/Users/norven/.claude/skills/redcap/prism/runs/review-layerb-closeout-runtime-followup-20260422/session-registry.yaml)
- [kimi_review/parsed.json](/Users/norven/.claude/skills/redcap/prism/runs/review-layerb-closeout-runtime-followup-20260422/collect/kimi_review/parsed.json)
- [copilot_review/parsed.json](/Users/norven/.claude/skills/redcap/prism/runs/review-layerb-closeout-runtime-followup-20260422/collect/copilot_review/parsed.json)

### 6.3 人工验证项

- [x] 旧资产未被批量误删，历史证据仍保留
- [x] diagnosis-rescue 已成为真实强入口，而不是停留在手动命令
- [x] receipt 修复路径已覆盖真实成功 ledger，而不是只靠伪造夹具

## 六、遗留问题与下一步

### 7.1 本次未处理的问题

这轮没有留下 tranche 级 blocker。  
但仍有两条长期边界不应伪装成“也一起解决了”：

1. **宿主 reply-path 仍然 host-limited**  
   当前还做不到在 Codex.app 这类宿主上对 final reply / ask_user 做 repo-owned 物理 veto。

2. **更大范围的 archaeology / tracking authority 审判还没展开**  
   本轮收的是 Layer B closeout/control-plane 一圈，不是整仓 docs/knowledge/tracking 的全域治理。

### 7.2 推荐下一步

若继续下一 tranche，建议按顺序做：

1. RedCap 全仓 runtime-memory / archaeology / tracking authority 审判
2. 宿主 reply-path / closeout receipt 进一步向 wrapper / runtime 层推进

## 七、经验沉淀

本轮已新增两条长期经验：

- [L-109](/Users/norven/.claude/skills/redcap/compass/knowledge/lessons.md): 终态收口一旦涉及 Agent 自追加承诺，就必须升级成 receipt-driven runtime
- [L-110](/Users/norven/.claude/skills/redcap/compass/knowledge/lessons.md): 运行时重构的独立评审必须提供完整可审材料包

## 八、附录

### 9.1 相关文档索引

- 任务锚点：[.dev-task.md](/Users/norven/.claude/skills/redcap/.dev-task.md)
- 设计文档：[2026-04-22-layerb-closeout-runtime-and-promise-ledger-design.md](/Users/norven/.claude/skills/redcap/compass/docs/specs/2026-04-22-layerb-closeout-runtime-and-promise-ledger-design.md)
- 协议面：[runtime-memory-architecture.md](/Users/norven/.claude/skills/redcap/references/runtime-memory-architecture.md)
- 人话词典：[runtime-memory-architecture.md](/Users/norven/.claude/skills/redcap/compass/knowledge/runtime-memory-architecture.md)

### 9.2 本轮一句话结论

这轮真正落地的不是“又多了几个脚本”，而是：

**Layer B 现在终于有了一条 receipt-driven 的终态 runtime，能把承诺、收尾、补救和证据收成同一条可审计闭环。**

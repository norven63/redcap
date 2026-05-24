# 任务完成报告：Layer B closeout 状态一致性修复

**报告日期**：2026-05-10  
**执行者**：Cap（Codex.app + Claude Code / Kimi Prism reviewer）  
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已修复“receipt 已生成后，SessionEnd 仍可能因为缺 runtime binding 重新写 pending closure”的状态漂移。
- 详情：这次解决的是完成态被后续 hook 反向污染的问题。现在 SessionEnd 在缺少 runtime claim 时，会先检查当前任务是否已经有 receipt、承诺账本是否已清、验收是否不阻塞；若满足，就清掉同任务 stale pending closure 并退出，不再把已完成任务重新挂成待收口。current-status 也会优先展示实时 receipt/pending 状态，不再沿用报告里 closeout 前的“等待 receipt”旧句子。

### 0.2 上一步完成的是

- 上一步完成的是：RedCap 已把“结论性输出必须 Prism-backed”和“新增能力优先固化保障”落成机制，并完成 receipt；随后复核时发现状态面仍有 pending closure 残留和摘要滞后。

### 0.3 下一步计划做的是

- 下一步计划做的是：本轮完成后无新的非发布类阻塞任务；后续如果继续推进，应进入正式发布专项或长期演进专项，并按结论 gate 让架构/路线判断先过 Prism。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：历史坏味治理 -> 结论/保障机制补强 -> closeout 状态一致性修复 -> 正式发布专项 / 长期演进专项。
- 当前所在位置：closeout 状态一致性修复已实现，Claude Code + Kimi 棱镜复核、targeted acceptance、完整 acceptance、spec-check 与 diagnose 均已通过；等待提交和 closeout receipt。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触及 npm 发布、许可证、registry 凭据、公共仓库写入、不可恢复删除或安全边界决策。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “可以，你们先把计划要执行的都执行干净吧”

### 1.2 触发背景

在回答“以上结论到底是 Cap 单人还是棱镜共同评审”时，Claude Code 与 Kimi 的只读复核共同指出：RedCap 的结论 gate 已完成，但当前状态面出现了新的不一致。receipt 已经存在，承诺账本也已清，但 pending closure 又被 SessionEnd 写回；同时 current-status 顶部仍复用旧报告里的“等待 receipt”句子。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 把已识别的状态一致性修复执行干净，而不是继续口头解释。 |
| 已覆盖 | SessionEnd receipt 后防重开 pending、current-status 实时状态优先、acceptance 复发回归、lesson 沉淀。 |
| 未覆盖/延期 | 不处理正式 npm 发布，不证明 Codex.app 每一句即时回复的物理 pre-send veto。 |
| 用户可见边界 | 可以声明“同一任务 receipt 后 missing runtime 不再重开 pending closure”；不能声明所有宿主 hook 已完全等价。 |

---

## 二、方案讨论

### 2.1 问题分析

问题不是“没有收尾”，而是 RedCap 把几个层次混在一起了：receipt 是终态收据，pending closure 是未清义务，任务报告是人类历史记录，SessionEnd 是宿主事件。receipt 已存在时，SessionEnd 缺 runtime binding 应该被视作已完成任务的后验噪声，而不是重新创造一个 blocker。

### 2.2 方案选项

| 选项 | 描述 | 结论 |
|---|---|---|
| 手动删除 pending closure | 快速把当前状态清掉 | 不采纳；会掩盖复发路径 |
| 只改报告文案 | 让 current-status 不再难读 | 不采纳；SessionEnd 仍会复发 |
| 修 SessionEnd + 修 current-status + 补 acceptance | 同时修根因、状态面和回归 | 采纳 |

### 2.3 决策结果

| 采纳方案 | 决策理由 | 决策方 |
|---|---|---|
| 修 SessionEnd + 修 current-status + 补 acceptance | 只有这条路径能防止完成态再次被缺 runtime binding 污染，也能让新会话看懂当前真实状态。 | CAP_DECIDE + Claude Code/Kimi Prism 复核通过 |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|---|---|---|
| `compass/tools/redcap-layerB-session-end.sh` | 修改 | 支持 `REDCAP_TASK_FILE`，并在 receipt 已存在、承诺已清、验收不阻塞时忽略 missing runtime claim，安全清理同任务 stale pending closure。 |
| `compass/tools/redcap-current-status.py` | 修改 | 顶层摘要优先使用实时 closeout facts；pending 与 receipt 分开展示，避免复用旧报告“等待 receipt”口径。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增/补齐复发回归：SessionEnd receipt 后不重开 pending、resource-limited receipt 可识别、非 SessionEnd pending 不被误删、current-status receipt 后不展示 stale plan；同时修复两个旧 spec-check fixture，使它们跟上新增硬门禁。 |
| `compass/knowledge/lessons/l-158.md` / `lessons.md` | 新建 / 修改 | 沉淀“receipt 与 pending closure 必须分开判定”的经验。 |
| `redcap-knowledge/task-reports/2026-05-09-prism-runs-evidence-preservation-boundary.md` | 归档 | 为保持 active task-reports inbox 不膨胀，把旧报告移入知识归档区；考古能力仍由 catalog/冷归档索引保留。 |
| `references/*.json` / `compass/docs/catalog.json` | 更新 | 同步文档目录、冷归档清单、引用资产生命周期和历史资产迁移计划。 |

### 3.2 技术实现要点

SessionEnd 现在遇到缺 runtime binding 时，不会立刻写 pending closure，而是先读取 closeout runtime 状态：如果 receipt 已存在、承诺账本无 pending、Prism acceptance / resource-limited-pass / not-required 不阻塞，就把这个事件视为完成任务后的宿主噪声。

安全边界是：它只清理 trigger 为 `layerB-session-end-missing-runtime-claim` 的同任务 stale pending closure。若 pending closure 来自 stop-review 等其他来源，它会保留这张欠条并只记录“没有新增 missing-runtime closure”，避免为了修状态面而擦掉真实 blocker。

current-status 现在不再把任务报告里的历史计划句当作当前状态真相。若 receipt 已存在，它会明确说明 receipt 已生成；若 pending closure 仍存在，它会说明“receipt 与 pending closure 分开判断，以 pending closure 为准”。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人类可读解释 | 本轮为什么重要 |
|---|---|---|
| receipt | 一张“任务已经正式收口”的机器收据。 | 它是判断任务是否完成的终态凭证，不能被后续噪声覆盖。 |
| pending closure | 一张“还有事没补完”的欠条。 | 如果是真欠条必须保留；如果只是 receipt 后的 stale missing-runtime 噪声，才允许清理。 |
| SessionEnd | Agent 宿主在会话结束时触发的收尾动作。 | 本轮 bug 就是它在缺少 runtime binding 时，把已完成任务重新挂成待收口。 |
| runtime binding | 会话和 RedCap 收尾状态之间的临时连接信息。 | 连接缺失不能直接等价为任务没完成，需要先检查 receipt 和承诺账本。 |
| current-status | 给人和 Agent 看的“当前到底在哪一步”的状态面。 | 它必须优先展示实时事实，而不是旧报告里的历史计划句。 |

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|---|---|---|---|
| 1 | 无必须人工审核项 | 本轮是内部状态一致性修复，不触及用户保留决策。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| Python / Shell 语法 | `python3 -m py_compile ... && bash -n ...` | 通过 |
| SessionEnd 防复发 | `bash compass/tools/redcap-multi-session-acceptance.sh session-end-missing-runtime-ignores-completed-receipt` | 通过 |
| resource-limited receipt 防复发 | `bash compass/tools/redcap-multi-session-acceptance.sh session-end-missing-runtime-accepts-resource-limited-receipt` | 通过 |
| 非 matching pending 保留 | `bash compass/tools/redcap-multi-session-acceptance.sh session-end-missing-runtime-preserves-nonmatching-pending` | 通过 |
| current-status 防旧摘要 | `bash compass/tools/redcap-multi-session-acceptance.sh current-status-receipt-overrides-stale-report-plan` | 通过 |
| spec-check fixture 老化修复 | `spec-check-propagates-control-gate-failures` + spec registry 五条定向 case | 通过 |
| Prism 复核 | Claude Code + Kimi，只读复核，run=`20260510-closeout-status-consistency-repair` | 通过 |
| Prism acceptance 绑定 | `redcap-prism-acceptance-bind.sh` + `redcap-prism-acceptance-check.sh` | 通过 |
| 文档/资产治理 | docs catalog、cold archive inventory、reference asset lifecycle、legacy asset migration、information architecture | 通过 |
| 发布安全面 | runtime package manifest、public package surface、package publish safety | 通过 |
| 完整 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过 |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD" 7b15d36df6d0284e9ece6cace8c4dfa21e19ff8b` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh` | 通过 |

### 5.2 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| 执行承诺账本 | 已完成，等待 closeout runtime 最终核对 |
| 棱镜验收 | 通过，Claude Code + Kimi 两个模型族均 blocker-free |
| closeout summary | 待 closeout 命令生成 |
| closeout receipt | 待 closeout 命令生成 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是；Claude Code + Kimi 复核通过，完整 acceptance 通过 |
| 已正式完成 | 否；当前报告提交后由 closeout receipt 作为唯一正式完工凭证 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|---|---|---|
| Codex.app 每一句即时回复的物理 pre-send veto | 仍取决于宿主是否提供可证明 hook。 | 长期演进 |
| 历史 pending closure 存量治理 | 本轮只处理当前任务和同任务 receipt 后复发路径；历史任务 pending 存量需要单独治理。 | P2 |

### 6.2 触发的新问题

无新的阻塞问题。历史 pending closure 存量已显性化，但不应混入本轮根因修复。

### 6.3 推荐的下一步行动

1. 提交本轮修复。
2. 执行 closeout，生成正式 receipt。

---

## 七、经验沉淀

### 7.1 新增 Lesson

| 编号 | 标题 | 核心内容 |
|---|---|---|
| L-158 | receipt 与 pending closure 必须分开判定 | 终态收据、未清义务、历史报告和宿主事件是不同事实源，不能互相覆盖。 |

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|---|---|---|---|
| candidate id: L-158 | 本轮状态一致性修复 | 已 promoted 为 lesson | `compass/knowledge/lessons/l-158.md` |
| 无新增候选 | 本轮候选池复核 | 除 L-158 已直接沉淀外，无需追加 EVO 候选；no-promote | `.dev-task.md` |

---

## 八、附录

### 附录 A：Commits

```
待提交
```

### 附录 B：棱镜调用记录（如有）

```
run_id: 20260510-closeout-status-consistency-repair
agents: Claude Code, Kimi
verdict: pass
blockers: none
important followups fixed: task_id identity sanitization, resource-limited-pass handling, non-matching pending preservation, cleanup visibility
```

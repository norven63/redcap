# 任务完成报告：历史资产物理清理与高价值经验候选化发布硬门

**报告日期**：2026-05-17
**执行者**：Cap（Codex，Prism 已验收）
**报告版本**：v0.4

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已把两个正式发布前硬门落地：历史资产必须安全归位，以及高价值经验必须先完成候选判断。
- 详情：本轮先解决一个发布风险：不能只证明私密内容“不进入包”，就把它冒充成“历史资产已经搬干净”；随后补上一个控制面缺口：重大 bug、用户纠偏、评审缺口、递归/进程风暴等经验，不能再靠人工提醒才进入沉淀流程。现在这两类硬门都已写入发布计划、授权矩阵、handoff、backlog 和检查脚本。

### 0.2 上一步完成的是

- 上一步完成的是：正式发布准备计划与人工授权矩阵已经落盘，但旧计划仍允许部分高风险根目录在发布前保持“延期”口径。

### 0.3 下一步计划做的是

- 下一步计划做的是：进入正式发布任务时，先处理历史资产物理清理 tranche，并确认当前 release task 的高价值经验候选判断已通过；不能直接跳到发布授权或真实发布。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：发布准备计划落盘 -> 历史资产物理清理硬门升级 -> 高价值经验候选化硬门升级 -> formal release task 分 tranche 处理历史资产与发布授权 -> 最终发布前全量门禁。
- 当前所在位置：P4-2n / historical-asset-physical-cleanup-release-hard-gate；本轮是发布前控制面加固，不是真实发布。

### 0.5 是否需要 Norven 人工介入

- 人工介入：当前不需要。
- 说明：本轮不做不可逆删除、不选择许可证、不触碰 registry。若后续某个物理迁移会造成历史损失，才需要 Norven 决策。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “1. 先把“所有历史资产都物理搬干净”升级为正式发布前硬门，明确写进 release-readiness 父任务
> 2. 然后，再根据最新的任务清单，稳步推进”

### 1.2 触发背景

此前 RedCap 已经把正式发布路线整理成 10 个阶段，但历史资产清理仍偏“计划中处置”。用户要求把它升级为发布前硬门，避免后续在正式发布时把“包面排除”误当成“历史资产已物理清理”。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 把历史资产物理清理升级为正式发布前硬门，并继续按最新任务清单推进 |
| 已覆盖 | 硬门策略文件、正式发布计划、授权矩阵、handoff、backlog、父任务账本、字典、Evolution 候选池和检查脚本 |
| 未覆盖/延期 | 真实 npm 发布、许可证选择、registry 操作、无证据删除、大规模不可逆物理迁移 |
| 用户可见边界 | 本轮不能说“所有历史资产已经全部物理搬迁完成”，只能说“正式发布前硬门已经建立并会阻断未清理资产” |

## 二、方案讨论

### 2.1 问题分析

发布安全分两层。第一层是“不会把私密内容打进包”，这由 package safety 负责；第二层是“历史资产不会继续污染 RedCap 的产品化运行面”，这需要历史资产生命周期和物理清理硬门负责。两者不能互相替代。

### 2.2 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---|---|---|
| Q1 | 新增历史资产物理清理发布硬门 | 符合“不要口头协议，要可检查拦截”的 RedCap 准则 | NORVEN_DECIDE + CAP_DECIDE |
| Q2 | 默认不做无证据删除 | 保护 receipt、考古锚点和回滚能力 | CAP_DECIDE |

## 三、落地结果

### 3.1 变更摘要

| 变更 | 人话解释 |
|---|---|
| 新增发布硬门策略 | 正式发布前必须证明历史资产已经安全归位；否则发布继续阻断 |
| 更新发布计划 | R1/R4/R5/R6 都会检查或引用这个硬门 |
| 更新授权矩阵 | 条件授权新增“历史资产物理清理硬门通过”这一条 |
| 更新发布交接 | 告诉后续任务：未过硬门时不能索要或使用发布授权 |
| 更新回归检查 | `spec-check`、`diagnose` 和 acceptance 能发现硬门缺失或弱化 |
| 修复验证递归风暴 | 产品表面检查不再递归触发完整 diagnose；超时子进程会按进程组清理 |
| 补上经验候选化硬门 | review / release / bugfix / 用户纠偏 / 进程风暴等高价值信号会强制进入候选判断 |

### 3.2 关键边界

- “硬门已建立”不等于“历史资产已经全部搬完”。
- “包面排除通过”不等于“历史资产物理清理完成”。
- “物理搬干净”不等于“删除历史证据”；默认必须保留 alias、rollback、receipt 和 Prism review。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| historical asset physical cleanup gate | `references/historical-asset-physical-cleanup-release-gate.json` | 发布前硬门：历史资产没安全归位时，正式发布必须停止 |
| Evolution harvest signal gate | `references/evolution-harvest-signal-policy.json` | 经验候选化硬门：高价值任务没判断是否要沉淀经验时，收尾或发布必须停止 |
| package safety | `redcap-package-publish-safety-check.sh` | 检查哪些文件不会被打进候选包，负责防泄漏，不负责证明历史资产已搬完 |
| root IA deferral | `references/root-ia-remaining-root-groups-deferral.json` | 记录哪些高风险根目录之前被允许延期；现在这些延期在正式发布前会变成 blocker |
| release blocker | 本轮新增硬门 | 不是“任务失败”，而是“没解决前不能继续发布” |

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|---|---|---|---|
| 1 | 是否接受硬门口径 | 本轮把未清理历史资产定义为正式发布前 blocker | P0 |
| 2 | 后续是否允许不可逆删除 | 当前默认不允许；若未来确需删除，需要 Norven 决策 | P0 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 当前结果 |
|---|---|---|
| 发布计划硬门检查 | `bash compass/tools/redcap-formal-release-readiness-plan-check.sh` | 通过 |
| Release E2E 矩阵 | `bash compass/tools/redcap-release-e2e-matrix-check.sh` | 通过 |
| Evolution harvest signal gate | `bash compass/tools/redcap-evolution-harvest-check.sh .dev-task.md` | 通过，required=true |
| Evolution candidate strict | `bash compass/tools/redcap-evolution-candidate-check.sh --strict` | 通过，promoted=12 |
| backlog 严格检查 | `bash compass/tools/redcap-backlog-check.sh strict .dev-task.md` | 通过 |
| 新增 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh evolution-harvest-check` | 通过 |
| 新增 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh formal-release-readiness-plan-check` | 通过 |
| package safety | `bash compass/tools/redcap-package-publish-safety-check.sh` | 通过，files_scanned=196 |
| package manifest dry-run | `bash compass/tools/redcap-runtime-package-manifest.sh --check --npm-pack-dry-run` | 通过，candidate_count=196 |
| public package surface | `bash compass/tools/redcap-public-package-surface.sh` | 通过，candidate_count=196 |

### 5.2 独立评审与完整回归

- [x] Prism 独立评审：Claude Code 与 Kimi 均返回 `pass`，无 blocker；新增复核报告 `prism/reports/2026-05-17-evolution-harvest-signal-gate-review.md`。
- [x] `redcap-spec-check.sh "$PWD"`：通过。
- [x] `redcap-diagnose.sh .dev-task.md`：通过。
- [x] 本轮必要子集 acceptance：`evolution-harvest-check`、`formal-release-readiness-plan-check` 通过。
- [x] closeout runtime harvest 链路：`layerb-closeout-runtime-evolution-harvest-blocks` 通过。
- [ ] full acceptance：本轮不计为通过。重新执行时在 `prism-concurrency` 附近长时间无输出，并生成 `sleep 600` 夹具进程；为避免回归套件本身制造进程风暴，已中断并清理相关进程。当前以 targeted acceptance、closeout runtime 链路和 Prism 双路评审作为本轮验收依据。
- [x] 验证递归风暴回归：`redcap-human-product-surface-check.sh`、正常 `redcap-diagnose.sh .dev-task.md` 和进程残留检查均通过；临时夹具残留进程为 0。
- [x] deferred-with-owner 防空壳：缺 owner / trigger 的 deferred 结果会被拒绝。

### 5.4 完成等级（禁止混报）

| 等级 | 当前结果 |
|---|---|
| 已实现 | 是，硬门登记与检查链已落地 |
| 已自检 | 是，spec-check / diagnose / targeted acceptance 通过 |
| 已独立验收 | 是，Claude Code 与 Kimi 均 pass |
| 已正式完成 | 否，等待 closeout runtime 生成正式 receipt；预期路径为 `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-release-readiness-historical-asset-hard-gate-538240ff3046cc86a48fa1b43b8e400de01d3886280bfd97177fc4e1437097bd.json` |

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|---|---|---|
| 真实历史资产分 tranche 物理迁移 | 这是后续 formal release task 的执行内容；本轮先建立硬门和拦截 | P0-before-release |
| 正式发布授权问卷 | 仍需 Norven 后续回答许可证、版本、账号和发布开关 | P0-before-publish |

### 6.2 推荐下一步

1. 下一阶段进入 formal release task 时，先执行 R1 历史资产物理清理 tranche，而不是直接问发布授权。
2. 后续如果触发真实物理迁移，必须继续分 tranche、保留 alias/rollback/receipt，并先走 Prism 评审。

## 七、经验沉淀

| 问题源 | 解决方案 | 最后效果 |
|---|---|---|
| 发布计划中“延期处置”容易被误读成发布可继续 | 把历史资产物理清理单独做成硬门策略并接入检查 | 后续 release task 未解决历史资产时会 fail-closed |
| 包面安全容易被误当成历史资产治理完成 | 明确“包面排除”和“物理清理”是两层不同证据 | 汇报和检查都不能混报 |
| 物理清理可能被误解成删除 | 默认要求 alias、rollback、receipt、Prism review | 保护考古链和回滚能力 |
| 产品表面检查调用 diagnose 时递归触发自己 | diagnose 支持受控跳过该检查，Python 超时按进程组清理 | 完整 diagnose 不再留下临时子进程 |
| 递归风暴修复最初没有自动沉淀 | 把 Evolution harvest 从只看 governance 扩展到 review / bugfix / release / 安全等高价值信号 | 后续同类问题必须先做候选判断，不能等用户提醒 |
| full acceptance 在 Prism 并发段可能拖出长睡眠夹具 | 本轮不把 full acceptance 中断冒充为通过，并记录为 deferred-with-owner 候选处理 | 后续若要把 full acceptance 作为 release 硬门，需要先治理该套件的进程生命周期 |

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| EVO-2026-05-17-001 | 用户纠偏：重要 bug 经验没有自动候选化 | promoted；沉淀为 L-163，并接入 harvest signal gate | `compass/knowledge/lessons/l-163.md`、`references/evolution-harvest-signal-policy.json` |
| deferred-with-owner | full acceptance 在 Prism 并发段出现长时间 sleep 夹具 | deferred-with-owner；owner=未来 acceptance lifecycle 治理任务；trigger=正式把 full acceptance 作为 release 硬门前 | 本报告；本轮进程清理记录 |
| 无新增候选 | 历史资产发布硬门本身 | no-promote；本轮已作为 release-readiness 计划和检查脚本落地，不额外新增 Evolution candidate | `references/formal-release-readiness-plan.json`、`references/historical-asset-physical-cleanup-release-gate.json` |

## 八、附录

### 8.1 关键证据入口

- 发布硬门策略：`references/historical-asset-physical-cleanup-release-gate.json`
- 正式发布计划：`references/formal-release-readiness-plan.json`
- 授权矩阵：`references/release-authorization-matrix.json`
- Prism 评审报告：`prism/reports/2026-05-17-historical-asset-physical-cleanup-release-hard-gate-review.md`
- Prism acceptance binding：`prism/runs/20260517-historical-asset-physical-cleanup-release-hard-gate/artifacts/acceptance-binding.json`

### 8.2 本轮禁止外推的结论

- 不能外推为“所有历史资产已经全部物理迁移完成”。
- 不能外推为“RedCap 已经 release-ready”。
- 不能外推为“Norven 已授权真实发布”。

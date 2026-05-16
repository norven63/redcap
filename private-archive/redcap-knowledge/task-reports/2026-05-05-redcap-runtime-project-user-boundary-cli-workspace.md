# 任务完成报告：P4-2b runtime/project/user 边界与 CLI workspace context

**报告日期**：2026-05-05
**执行者**：Cap（Codex.app + Prism: Kimi / Claude Code）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap CLI 的任务类命令已经从“默认读 RedCap 包根目录任务卡”改为“默认读调用者所在项目 workspace 的任务卡”，并有机器门禁证明不会再静默回退到 package-root。
- 详情：这次解决的是 public CLI 发布前最危险的一类错位：工具本体、用户项目、用户身份状态三层混在一起。现在 `status`、`diagnose`、`change-intake`、`closeout status` 都会先解析 workspace 和 task file；外部项目默认读外部项目的 `.dev-task.md`，RedCap 自身开发仍能在仓库根目录或子目录正常读自己的任务卡。诊断输出也会直接展示 runtime root、workspace root、task file 和 user state 边界，让人能看懂当前 CLI 到底在操作谁。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2g 已完成 npm 白名单预检与结构重构任务树重锚定，把“先拍片再手术”的顺序固定下来，并确认 P4-2b 是当前最优先的发布前 P0 blocker。

### 0.3 下一步计划做的是

- 下一步计划做的是：继续推进 P4-2c，补齐面向外部用户的 CLI doctor / debug / trace / error / help 产品面；本轮不继续扩张到 npm 发布或 license/package identity 定稿。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-2g 白名单预检与任务树重锚定 → P4-2b runtime/workspace 边界 → P4-2c CLI 诊断产品面 → P4-2d public package identity/license/surface → P4-2 正式 release readiness。
- 当前所在位置：P4-2b 已进入实现收口；public release 仍保持 blocked，剩余 release blockers 还有 runtime layout、CLI debug surface、package identity/license。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，那么请你和棱镜团队继续稳步推进下面的任务

### 1.2 触发背景

P4-2a 发布前产品架构审判指出，RedCap 虽然已经具备 npm pack、安全扫描和 clean workspace E2E 的基础，但 CLI 仍把 RedCap 自身仓库当成默认项目状态目录。这个问题如果不先修，后续即使能发布 npm 包，也会让新用户在自己的项目里运行 `redcap status` 时读到包内部状态，形成“能安装但不像一个独立工具”的产品级缺陷。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 接续 P4-2g 后的下一主线，稳步推进 P4-2b，并让 Prism 参与设计与风险审查。 |
| 已覆盖 | CLI workspace/task-file 解析、self-development 兼容、closeout status 路由、边界策略、机器检查器、diagnose/spec/execution guarantees/acceptance 接线、Prism 双路审查。 |
| 未覆盖/延期 | 未完成 P4-2c doctor/debug/trace/help；未完成 P4-2d public package identity/license/surface；未执行真实 npm publish；未做大规模物理目录迁移。 |
| 用户可见边界 | 可以说 CLI workspace context 已有最小闭环；不能说 RedCap 已 release-ready，也不能说 runtime 目录布局和 package identity 已定稿。 |
| 后续路径 | 下一步推荐 P4-2c；P4-2d 仍需 public 包名、license、package surface 的独立决策与回归。 |

---

## 二、方案讨论

### 2.1 问题分析

问题本质不是“脚本少传了一个参数”，而是 RedCap 作为未来 CLI/runtime 时必须区分三层对象：工具本体在哪里、当前管理哪个项目、用户和 Agent 的本地身份状态在哪里。如果三层不分，任何诊断、收尾、任务追踪都可能读错对象；读错对象之后再跑再多回归，也只是证明错对象很稳定。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 立刻物理大迁移 | 批量移动 runtime、tools、prism 等目录，重建 package layout | 结构更接近最终形态 | 风险高，容易断 receipt、历史锚点、hook 路径和 Prism 证据 |
| Q1 | CLI workspace 先行 | 保持 runtime 文件不大搬家，先让 CLI 明确解析 runtime root、workspace root、task file | 风险低，可快速解除 CLI 读错项目状态的 blocker | 不能宣称最终 runtime layout 已完成 |
| Q1 | 只改文档 | 声明使用者要手动传 task file | 实现成本最低 | 不能防错，也不符合 public CLI 产品预期 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | CLI workspace 先行 | 本轮目标是 P4-2b 的最小安全闭环：先消除“默认读包根任务卡”的真实产品 bug，并保留 RedCap 自身开发兼容；大规模物理迁移留给后续独立任务。 | CAP_DECIDE + Prism review |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `bin/redcap` | 修改 | 新增 workspace/task-file 解析，支持 `--workspace`、`--task-file`、环境变量 fallback、外部项目向上发现 `.dev-task.md`，并把 `closeout` 也纳入 workspace 路由。 |
| `compass/tools/redcap-current-status.sh` / `compass/tools/redcap-current-status.py` | 修改 | status 输出新增 runtime/workspace/user 边界段，解释当前 CLI 操作对象。 |
| `compass/tools/redcap-diagnose.sh` | 修改 | diagnose 顶部输出 runtime root、workspace root、task file，并接入新的边界检查器。 |
| `compass/tools/redcap-layerb-closeout-runtime.py` | 修改 | closeout status 输出 task_file 和 repo_root，便于检查 CLI 是否把 workspace task file 传入收尾 runtime。 |
| `references/runtime-workspace-boundary-policy.json` | 新建 | 记录 P4-2b 的三层边界策略、解析规则和不可回退保证。 |
| `compass/tools/redcap-runtime-workspace-boundary-check.py` / `.sh` | 新建 | 用静态检查和临时外部 workspace smoke test 验证 CLI 不再默认读 package-root。 |
| `references/pre-release-product-architecture-review.json` | 修改 | 把 `cli-workspace-context-not-separated` 从 release blocker 更新为 pass；剩余 release blockers 从 5 个降为 4 个。 |
| `references/pre-release-structure-refactor-task-tree.json` / `references/redcap-parent-task-ledger.md` | 修改 | P4-2g 改为 completed，P4-2b 改为当前进行中。 |
| `references/execution-guarantees.json` / `compass/tools/redcap-execution-guarantee-check.py` | 修改 | 把 runtime/workspace boundary 纳入执行保障强门。 |
| `compass/tools/redcap-spec-check.sh` / `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 将边界检查器接入总体验收与失败传播回归。 |
| `references/file-lookup-dictionary.md` / `references/file-lookup-dictionary-policy.json` | 修改 | 将新增策略和检查器纳入文件查找字典。 |
| `prism/runs/20260505-runtime-project-user-boundary-review/**` | 新建 | 保存 Kimi 与 Claude Code 的独立审查、解析结果和 acceptance binding。 |

### 3.2 技术实现要点

CLI 现在先把“工具所在位置”和“要管理的项目位置”分开：`REDCAP_RUNTIME_ROOT` 指 RedCap 工具本体，`REDCAP_WORKSPACE_ROOT` 指调用者项目。如果用户没有显式传入 workspace，CLI 会优先保护 RedCap 自开发模式；若在外部项目子目录中运行，会向上寻找 `.dev-task.md`；找不到时才使用当前目录作为 workspace 并明确显示 task file missing，而不是偷偷回到 RedCap 包根。

这次还把 `closeout status` 纳入同一套规则。原因是 closeout 是任务收尾总控，如果它仍默认读包根任务卡，就会出现 status 看的是项目 A、closeout 收的是 RedCap 自己的荒诞分裂。现在 `bin/redcap closeout status` 会先解析 workspace task file，再把绝对 task file 传给 `closeout-cap.sh`。

机器检查器不是只查字符串。它会创建一个临时外部 workspace，写入独立 `.dev-task.md`，再从项目根和子目录分别运行 `redcap status`，确认输出的是外部 fixture 的 task_id；同时跑 `redcap closeout status`，确认 closeout runtime 收到了同一个 workspace task file。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| runtime root | `bin/redcap` / `REDCAP_RUNTIME_ROOT` | RedCap 工具本体所在位置，也就是 npm 包或当前仓库里的脚本实现位置。 |
| workspace root | `bin/redcap` / `REDCAP_WORKSPACE_ROOT` | 当前被 RedCap 管理的项目目录；外部用户运行 CLI 时默认应该指向他们自己的项目。 |
| task file | `.dev-task.md` | 当前任务卡和承诺账本；必须属于 workspace，而不是无条件属于 RedCap 包根。 |
| self-development mode | `bin/redcap` 路径判断 | 当 CLI 从 RedCap 仓库内部运行时，允许 workspace=root，以免破坏 RedCap 自己开发 RedCap 的工作流。 |
| closeout status | `bin/redcap closeout status` | 收尾 runtime 的只读状态查询；现在同样使用 workspace task file，避免读错任务。 |

### 3.3 关联变更

本轮同步更新了发布前产品架构审判结果：CLI workspace blocker 已修复并变成 pass，但 runtime layout、CLI debug surface、public package identity/license 仍然阻塞公开发布。也同步更新了文件字典和执行保障 registry，避免新增能力只存在于实现里却不能被后续 Agent 找到或复验。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无必须人工审核项 | 本轮没有触及 npm publish、license、包名或真实物理大迁移；这些仍留在后续 P4-2c/P4-2d 阶段。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| runtime/workspace 边界检查 | `bash compass/tools/redcap-runtime-workspace-boundary-check.sh` | 通过：`RUNTIME_WORKSPACE_BOUNDARY_OK` |
| 发布前产品架构复核 | `bash compass/tools/redcap-pre-release-product-architecture-check.sh` | 通过：release blockers 从 5 降为 4 |
| 结构任务树检查 | `bash compass/tools/redcap-pre-release-structure-task-tree-check.sh` | 通过：`PRE_RELEASE_STRUCTURE_TASK_TREE_OK` |
| 文件查找字典检查 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过：`FILE_LOOKUP_DICTIONARY_OK` |
| 执行保障检查 | `bash compass/tools/redcap-execution-guarantee-check.sh` | 通过：`EXECUTION_GUARANTEES_OK` |
| acceptance：边界专项 | `bash compass/tools/redcap-multi-session-acceptance.sh runtime-workspace-boundary-check` | 通过：`ACCEPTANCE_OK` |
| acceptance：spec-check 失败传播 | `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures` | 通过：`ACCEPTANCE_OK` |
| full acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过：`ACCEPTANCE_OK` |
| Prism acceptance 残留清理回归 | `bash compass/tools/redcap-multi-session-acceptance.sh prism-concurrency` + `bash prism/tools/prism-runs-lifecycle.sh summary` | 通过：acceptance-fixture=0，purgeable_acceptance=0 |
| diagnose 总诊断 | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过：`DIAGNOSE_OK` |
| repo spec umbrella | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 无必须人工验证项；后续如果进入 P4-2d，需要 Norven 对 license、public package identity、发布渠道作保留决策。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已全部勾选；最终以 closeout runtime receipt 为准 |
| 棱镜验收 | Kimi + Claude Code 双路审查已完成并绑定 `prism/runs/20260505-runtime-project-user-boundary-review/artifacts/acceptance-binding.json` |
| closeout summary | closeout 后由 runtime 生成 |
| closeout receipt | closeout 后由 runtime 生成 |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Prism 双路审查和专项 acceptance 已通过 |
| 已正式完成 | 否，本报告生成时尚未执行最终 closeout receipt；正式完成以 receipt 为唯一凭证 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| P4-2c CLI doctor/debug/trace/error/help | 属于外部用户诊断产品面，不应和 workspace 边界混做 | P0 |
| P4-2d public package identity/license/surface | 涉及公开包名、license、发布口径和 package surface 定稿，需要单独任务 | P0 |
| 真实 npm publish | 仍需先完成 P4-2c/P4-2d，并保留用户发布决策 | P2 |
| 真实物理 runtime 大迁移 | 本轮选择低风险 CLI workspace 先行；大迁移仍需独立拍片、审查和回归 | P1 |

### 6.2 触发的新问题

Prism 指出 closeout 也属于 task-file 操作面；如果不纳入 workspace 路由，会形成 status 与 closeout 读不同任务的分裂。本轮已把该问题直接纳入修复范围，没有留下新 blocker。

### 6.3 推荐的下一步行动

1. 进入 P4-2c：把 `doctor`、`debug`、`trace`、错误解释和 help 变成外部用户能读懂、能排障的 CLI 产品面。
2. 随后进入 P4-2d：处理 `@norven63/redcap` 包名、license、public package surface 和 source visibility 的最终发布前决策。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-152 | CLI 化时必须先拆“工具位置”和“项目位置” | CLI 发布前不能只证明脚本能跑，还要证明默认读的是用户项目状态，而不是工具包自己的开发现场。 |

### 7.2 流程改进建议

P4-2 后续所有 public CLI 任务都应先问一句：这个命令是在操作 runtime、project 还是 user state？如果答案不清楚，先补边界输出和机器检查，再继续做产品面。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 本轮问题已直接晋升为 L-152 lesson 和 runtime/workspace boundary gate | 无新增候选 | `compass/knowledge/lessons.md`、`references/runtime-workspace-boundary-policy.json` |

---

## 八、附录

### 附录 A：Commits

```
待提交；本报告随实现一起提交
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| test | P4-2b runtime/workspace 边界方案审查 | 方向通过，但要求补 closeout、self-development、解析优先级和专项回归 | `prism/runs/20260505-runtime-project-user-boundary-review/` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 设计策略：`references/runtime-workspace-boundary-policy.json`
- 机器检查：`compass/tools/redcap-runtime-workspace-boundary-check.sh`
- 父任务账本：`references/redcap-parent-task-ledger.md`

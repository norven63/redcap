# 任务完成报告：multi-session isolation mainline

**报告日期**：2026-04-12  
**执行者**：Cap（Copilot CLI / GPT-5.4）  
**报告版本**：v1.0

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 给 RedCap 做成可证明的多会话隔离系统，覆盖 Layer A、Layer B、A↔B、Prism run 级状态与兼容迁移。
>
> 第一版的错误是其次的，最重要的是，为什么会导致你犯这个错误，因为这可能暴露了一个底层的核心问题，就是redcap的任务跟踪模块失效了，如果没有人工介入强行为你提醒和摆正，你可能会不自知的继续执行偏航下去。我的这个表述你可以和棱镜团队自行分析与复盘，可以尝试反驳我，但如果无法反驳，就要正视这个问题，并深刻分析彻底100%解决的方案。
>
> 1. 考虑沉淀这个经验，并且记一手“如果在宿主Agent中执行我们自己设计的Agent，没有处理好生命周期等事务流，可能会遇到体系冲突的问题”（我不知道我这么描述是否正确，你可以和棱镜团队评估一下，但我想传达的意思是，我们开发的redcap正在逐渐完善一个身位Agent体的能力，它会逐渐与宿主Agent发生冲突，而这个冲突我认为是可以化解的，但需要精心的设计，并且值得后续单独拎出一个命题或者hook点，作为每次升级迭代时必须要考量到的要素）
> 2. 刚才你作的修复，是否会因为接下来要继续完成的todo给破坏和冲突？请仔细深度的评估这个问题
>
> 好的，我作为人类只能帮你把控方向和高层级的风险预警，至于工程的实际底层落地细节我已经无法胜任review的角色了。现在我很庆幸能够在这几个身位人类而能协助到你的点上帮助到你了，你也因此梳理出了很多细节与风险问题，现在要做的是：1. 把你目前根据我的指引而扫描评估发现到的问题与风险全部进行fix和解决，由你和棱镜团队独立执行，不用向我请示（除非遇到必须要人工介入的环节）  2. 继续没有完成的任务，我这轮中途review开展很久了，加油，Cap！

### 1.2 触发背景

本轮主线一开始是多会话隔离：把 Layer A、Layer B、A↔B、Prism 的运行态从宿主级 `/tmp` marker、项目共享状态和 run 级状态里彻底拆分。  
推进过程中，用户指出另一个更底层的风险：即使隔离代码在变好，只要 Layer B 的 canonical truth / anti-drift control plane 失守，任务仍可能在错误真相源上继续推进。  
因此本次收口不是单纯补几个 runtime helper，而是同时把 **隔离主线** 与 **authority inversion 治理** 结合成一条可证明的迁移链。

---

## 二、方案讨论

### 2.1 问题分析

Q1 的本质是“运行时身份”和“状态作用域”长期混淆：Layer A / Layer B / Prism 把 session 私有态、run 共享态、project 兼容态写在同一类宿主路径里，多会话时天然串号。  
Q2 的本质是“真相源反转”：如果 `.dev-task.md` 没有真正成为 Layer B canonical ledger，宿主 `plan.md` 和宿主 skill 机制就会反客为主，把人类提醒当成最后的纠偏手段。  
Q3 的本质是“验收口径失真”：没有 acceptance harness，就会把零散 smoke、子线 review、个别宿主验证误当成“主线已证明完成”。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 选项 A | 继续在各脚本上逐点修 `/tmp` / marker 冲突 | 改动表面较小 | 真相层继续分散，无法证明并发隔离 |
| Q1 | 选项 B | 建立统一 runtime session / capability / binding 原语，再迁移 Layer A/B/Prism | 作用域清晰，可做 safe degraded 与 compat quarantine | 需要同时改 helper、hooks、acceptance |
| Q2 | 选项 A | 沿用宿主 `plan.md` / skill 作为事实控制面 | 宿主侧使用顺手 | 会再次 authority inversion，验收结论不可信 |
| Q2 | 选项 B | `.dev-task.md` 接管 canonical truth，宿主面板只保留 pointer/hash 镜像 | 可执行 anti-drift、PM Gate、delegation boundary | 需要补 Hook/脚本门禁 |
| Q3 | 选项 A | 继续靠零散 smoke + 人工 review 收口 | 开发成本低 | 很难覆盖同宿主并发 / 跨层 / Prism 多 run / recovery |
| Q3 | 选项 B | 把设计文档里的矩阵落成 acceptance harness | 可重复、可证明、可回归 | 需要先把 compat/degraded/legacy 语义补齐 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 选项 B | 只有统一 runtime session / run-scoped registry / project compat 三层边界，才能真正消除多会话串号 | CAP_DECIDE |
| Q2 | 选项 B | 用户指出的核心问题不是“忘了什么”，而是 canonical truth 失守；必须用 `.dev-task.md` + PM Gate / drift / host-workboard sync 实体化控制面 | NORVEN_DECIDE + CAP_DECIDE |
| Q3 | 选项 B | 只有 acceptance harness 才能把 same-host / cross-layer / Prism / degraded / recovery 这些高风险场景从文档变成物理断言 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `compass/tools/redcap-runtime-state.sh` | 新建 / 修改 | 建立 runtime session/binding/capability/process-claim/helper 真相层，并收紧 capability recovery gate |
| `compass/tools/redcap-layerB-session-start.sh` | 修改 | Layer B runtime attach、safe degraded、control-plane start sync、移除 unmanaged Copilot pseudo-session fallback |
| `compass/tools/redcap-layerB-session-end.sh` | 修改 | Layer B runtime收尾、legacy quarantine、drift/PM Gate/report audit、恢复 unmanaged Copilot safe degraded |
| `compass/tools/redcap-task-report-register.sh` | 修改 | 无 process claim 时不再 silent succeed |
| `compass/tools/redcap-task-report-check.sh` | 修改 | 按 runtime marker / staged diff 审计任务报告模板 |
| `compass/tools/redcap-on-stop-review.sh` | 修改 | review 前加入 control-plane 审计与 degraded 记账 |
| `compass/tools/redcap-dev-task.sh` | 新建 | `.dev-task.md` parser/helper |
| `compass/tools/redcap-pm-gate-check.sh` | 新建 | Layer B canonical ledger / PM Gate 校验 |
| `compass/tools/redcap-drift-check.sh` | 新建 | active_slice / scope / confirmed-hash drift 审计 |
| `compass/tools/redcap-host-workboard-sync.sh` | 新建 | 宿主 workboard mirror-only pointer/hash 同步 |
| `compass/tools/baton-delegate.sh` | 修改 | Skill delegation request/result 文件边界与 task_id 绑定 |
| `loom/tools/redcap-layerA-session-start.sh` | 修改 | Layer A runtime session / owner claim / safe degraded 起始链 |
| `loom/tools/redcap-layerA-session-end.sh` | 修改 | Layer A legacy marker quarantine、disk recovery cleanup、双路径 owner 兼容清理 |
| `loom/tools/redcap-layerA-stop.sh` | 修改 | Layer A ownership-check / safe degraded / on-complete 收口 |
| `loom/tools/redcap-layerA-review-fallback.sh` | 修改 | review-fallback 结果 / 日志切到 session 私有路径 |
| `prism/tools/prism-run-state.sh` | 新建 / 修改 | Prism per-run registry / owner / exact-match legacy bridge helper |
| `prism/tools/prism-coordinator.sh` | 新建 | start-run / register-agent / record-collect / resolve-handle coordinator Phase A |
| `prism/tools/prism-archive-check.sh` | 修改 | archive gate 绑定 run_id 并支持 exact-match legacy bridge |
| `compass/tools/redcap-multi-session-acceptance.sh` | 新建 | 多会话隔离 acceptance harness（same-host / cross-layer / Prism / degraded / recovery / legacy bridge） |
| `compass/CONTRIBUTING.md` | 修改 | `.dev-task.md` canonical ledger、PM Gate、authority inversion、防 drift 规范 |
| `ARCHITECTURE.md` | 修改 | authority chain / canonical truth / mirror-only workboard 说明 |
| `prism/protocol.md` | 修改 | Prism run-scoped registry 与 Skill-Delegation boundary 对齐 |
| `compass/knowledge/lessons.md` | 修改 | 新增 L-43、L-44 经验沉淀 |

### 3.2 技术实现要点

第一，runtime identity 被统一成 `runtime_session_id + capability + session_binding_key` 三件套：binding 只负责定位，capability 负责写权限，process claim 负责宿主侧回连。这样 Layer A / Layer B / Prism 才能共享“如何定位 / 如何授权 / 如何降级”的同一套原语。  
第二，Layer B 的 control plane 被从“文档约束”升级成“物理门禁”：`.dev-task.md` 现在是 canonical ledger，`redcap-pm-gate-check.sh` / `redcap-drift-check.sh` / `redcap-host-workboard-sync.sh` 让 PM Gate、drift sentinel、mirror-only workboard 都变成可执行逻辑。  
第三，compat/degraded/legacy 语义被显式收紧：unmanaged Copilot 不再写 project-scoped pseudo-session marker，而是回到真正的 safe degraded mode；Layer A / Layer B 命中旧路径时走 `legacy_hit + quarantine`，不再 silent delete。  
第四，Prism 迁移从“全局 registry 猜当前 run”切到 `prism/runs/<run_id>/session-registry.yaml`，并通过 `prism-coordinator.sh` 把 start-run / register-agent / collect / resolve-handle 的写回链统一到 run-scoped helper。  
第五，验收从零散 smoke 升级为 `compass/tools/redcap-multi-session-acceptance.sh`：它现在覆盖 binding recovery gate、same-host Layer B 并发、cross-layer A↔B 可见性边界、Layer A legacy quarantine、Prism multi-run collect/handle 隔离、legacy bridge exact-match、report-register claim gate 与 unmanaged Copilot safe degraded。

### 3.3 关联变更

本轮为了避免再次 authority inversion，连带更新了 `.dev-task.md`、session `plan.md` pointer/hash、SQL todos 的真实停点。  
此外，任务报告登记链也被收紧：如果没有 runtime process claim，`redcap-task-report-register.sh` 现在会显式失败，而不是继续制造“好像登记成功”的假象。  
最后，acceptance harness 本身也成了迁移设计的一部分——以后扩 matrix 时，不再需要重新靠人工回忆“上次哪些 case 已覆盖”。

---

## 四、人工审核要点

> ⚠️ 以下是 Norven 需要重点确认的内容，其他部分 Cap 已自行验证。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 观察真实宿主流量中的 `legacy-hit` / `degraded-mode` 走势 | acceptance harness 已覆盖脚本级语义，但真实 Claude/Gemini/Copilot 流量中的 compat 命中率仍需实际运行窗口观察，才能决定后续 legacy bridge 移除时机 | P1 |
| 2 | `host-agent-interop-governance` 是否升级为独立主线 | 当前多会话隔离主线已把 authority inversion 收敛到非阻塞治理项，但宿主 direct skill / lifecycle boundary 仍值得单独立题 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 关键脚本语法检查 | `bash -n compass/tools/redcap-runtime-state.sh compass/tools/redcap-layerB-session-start.sh compass/tools/redcap-layerB-session-end.sh compass/tools/redcap-task-report-register.sh loom/tools/redcap-layerA-session-start.sh loom/tools/redcap-layerA-session-end.sh compass/tools/redcap-multi-session-acceptance.sh` | ✅ |
| 多会话 acceptance harness | `env -u REDCAP_RUNTIME_ALLOW_DISK_RECOVERY -u REDCAP_RUNTIME_ALLOW_CAPABILITY_FILE_RECOVERY -u REDCAP_RUNTIME_CAPABILITY bash compass/tools/redcap-multi-session-acceptance.sh all` | ✅ |
| control-plane 独立复审 | `control-plane-rereview` | ✅ |
| acceptance/compat 独立复审 | `acceptance-fix-review` | ✅ |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 在真实多宿主会话流量下观察 `compat/legacy-hit.*` 与 `compat/degraded-mode.*` 的一段窗口，再决定 legacy bridge 缩减顺序
- [ ] 若要继续推进 `host-agent-interop-governance`，需在真实宿主 direct skill / resume 生命周期下做一次专项回归

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| `host-agent-interop-governance` 仍是 pending | 这是 authority inversion 的长期治理议题，已从本轮多会话隔离主线中剥离为非阻塞项 | P1 |
| Prism synthesize/audit 的更深层物理接线未纳入本轮批准边界 | 当前批准范围止于 coordinator Phase A 与 run-scoped acceptance；不在本轮继续扩火线/lease/firewall | P1 |

### 6.2 触发的新问题

本轮 acceptance 扩展过程中确认了一个新的 durable lesson：`session_binding_key` 只负责 locate，恢复写权限必须显式经过 capability gate；否则 very easy 会把 safe degraded 与 full isolation 语义混成一套。  
此外，也再次验证了用户指出的 authority inversion 命题：如果没有 `.dev-task.md` + PM Gate / drift / workboard sync 这组物理门禁，长任务里再正确的实现也会被错误的控制面叙事带偏。

### 6.3 推荐的下一步行动

1. 在真实宿主流量里观察 `legacy-hit` / `degraded-mode` 指标，决定 legacy bridge 的移除窗口。
2. 以独立议题推进 `host-agent-interop-governance`，把宿主 direct skill / lifecycle / transaction boundary 设计完整。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-43 | 宿主 Agent 内运行 RedCap 时，必须防 authority inversion | `.dev-task.md` 必须接管 Layer B canonical truth；宿主面板只能镜像 pointer/hash；acceptance 不能在错误 control plane 上宣称完成 |
| L-44 | `session_binding_key` 只负责定位，恢复写权限必须显式过 capability gate | binding ≠ capability；unmanaged/no-bind 宿主必须停留在 safe degraded mode，禁止写 pseudo-session marker |

### 7.2 流程改进建议

以后凡是涉及 runtime recovery / degraded mode / legacy bridge 的迁移，都应同步补 acceptance harness case，而不是先落代码、再靠事后 smoke 补洞。  
同时，主线级任务在切 slice 时应立即更新 `.dev-task.md` 的 `active_slice` 与 `允许修改范围`，否则 control plane 虽在，但会失去足够精细的 drift sentinel。

---

## 八、附录

### 附录 A：Commits

```text
664333f (HEAD -> main) docs(spec): add prism coordinator phase a design
31fa41d docs(spec): add multi-session isolation design
cd3027d docs(report): clarify smoke env flags
5aa15d7 fix(hooks): close host smoke gaps
21bfd4a docs(report): finalize hook-chain closure
9bae831 fix(hooks): harden layer-b completion chain
6df3418 docs(spec): add hook-chain investigation design
6fa1591 fix(prism): harden e2e archive and dispatch gates
aaa4882 fix: resolve 5 blocking issues found by multi-round duck review
a091730 feat(prism+loom): synthesize去重 / copilot-session修正 / r3调研验证
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| explore | `acceptance-gap-audit`：compat/acceptance 还差哪些真实落地点 | 收敛出 4 个高价值缺口：Copilot degraded 语义、capability recovery gate、Layer A silent delete、acceptance harness 缺失 | `N/A` |
| review | `control-plane-rereview`：control-plane hardening 最新修复是否干净 | No significant issues found | `N/A` |
| review | `acceptance-fix-review`：acceptance/compat 最新修复是否干净 | No significant issues found | `N/A` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 设计文档：`compass/docs/multi-session-isolation-design.md`
- 主线宿主面板：`/Users/norven/.copilot/session-state/c73ce3b2-e124-49d2-a1f8-770a2e08cb7a/plan.md`
- 既有基础报告：`compass/docs/task-reports/2026-04-11-multi-session-isolation-foundation.md`

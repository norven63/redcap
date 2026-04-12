# 任务完成报告：host-agent interop governance

**报告日期**：2026-04-12  
**执行者**：Cap（Copilot CLI / GPT-5.4）  
**报告版本**：v1.0

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 第一版的错误是其次的，最重要的是，为什么会导致你犯这个错误，因为这可能暴露了一个底层的核心问题，就是redcap的任务跟踪模块失效了，如果没有人工介入强行为你提醒和摆正，你可能会不自知的继续执行偏航下去。我的这个表述你可以和棱镜团队自行分析与复盘，可以尝试反驳我，但如果无法反驳，就要正视这个问题，并深刻分析彻底100%解决的方案。
>
> 1. 考虑沉淀这个经验，并且记一手“如果在宿主Agent中执行我们自己设计的Agent，没有处理好生命周期等事务流，可能会遇到体系冲突的问题”（我不知道我这么描述是否正确，你可以和棱镜团队评估一下，但我想传达的意思是，我们开发的redcap正在逐渐完善一个身位Agent体的能力，它会逐渐与宿主Agent发生冲突，而这个冲突我认为是可以化解的，但需要精心的设计，并且值得后续单独拎出一个命题或者hook点，作为每次升级迭代时必须要考量到的要素）
> 2. 刚才你作的修复，是否会因为接下来要继续完成的todo给破坏和冲突？请仔细深度的评估这个问题
>
> 很棒！现在请完成host-agent-interop-governance的能力，然后重构 @ARCHITECTURE.md 的内容，它应该要更新了。redcap在做过重构后，它的优秀设计思想已经积累了的非常多了，我们不要遗留和落下一个，都要记录和展示出来。再然后，根据这个记录内容，逐个review每个能力是否因为本次多会话隔离的长任务重构动作而破坏和影响。
>
> 1. 没有触发commit  2. 没有触发飞书  
> 这2个可能只是最显眼的表征被我察觉到，还有多少没触发的不知道。刚才不是说的，要整体reivew有没有影响吗？

### 1.2 触发背景

本 tranche 来自多会话隔离主线收口后的二次暴露问题：技术逻辑虽然逐步闭合，但宿主 workboard / session / direct skill 机制仍可能反客为主，导致 Layer B 任务真相源漂移。  
用户进一步指出“没有 commit、没有飞书”后，问题被确认不只是两个漏动作，而是整个交付闭环没有被当成系统级控制面来审计。  
因此本次任务的目标不是补几个 hook，而是把 **host/native authority boundary、closure contract、架构能力回归矩阵、最终交付闭环** 一起做成可证明系统。

---

## 二、方案讨论

### 2.1 问题分析

Q1 的根问题是 **authority inversion**：如果 `.dev-task.md` 只是名义上的要求，而宿主 `plan.md`、宿主 session、宿主 skill 仍在事实上主导叙事，那么长任务就会在错误的真相源上继续推进。  
Q2 的根问题是 **closure pseudo-success**：review、task report、notify、commit 等红线链路只要有一处把“尝试过”误当成“完成了”，去重 marker 就会提前熄火，后续不会再补偿。  
Q3 的根问题是 **架构记忆漂移**：如果先重写 `ARCHITECTURE.md` 再自我审查，就可能把旧能力锚点删掉后再宣布“没回归”；必须先冻结旧基线再做 trace。  
Q4 的根问题是 **边界实现与协议表述脱节**：workboard sync、delegation 文件边界、Prism registry 解析、Dispatch Firewall 口径，只要有一处是“看起来像有约束”，系统就会在弱宿主上退化成伪保障。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 选项 A | 继续让宿主 workboard / session 充当事实控制面 | 接入顺手 | 长任务里极易再次 authority inversion |
| Q1 | 选项 B | `.dev-task.md` 作为唯一 canonical ledger，宿主面板只镜像 canonical pointer | 真相源单一，可做 PM Gate / drift / mirror-only 审计 | 需要补一整套 helper 与 hook 接线 |
| Q2 | 选项 A | 依赖宿主 hook best-effort 完成 review / report / notify / commit | 改动面小 | 弱 hook / 无 hook 宿主上没有补偿式 closure contract |
| Q2 | 选项 B | 建立 pending-closure contract，把 review / report / notify / commit proof 都变成 fail-closed 审计链 | 可延续、可重试、可解释 | 需要跨 Layer A / Layer B / Prism 联动修复 |
| Q3 | 选项 A | 直接重写 `ARCHITECTURE.md`，再用新文档回顾新实现 | 效率高 | 容易把旧能力静默抹掉 |
| Q3 | 选项 B | 先冻结旧架构能力锚点，再做 `旧架构 -> 新架构 -> runtime evidence` trace audit | 回归可证明，可发现真正的语义变化 | 需要补 trace matrix 与证据链 |
| Q4 | 选项 A | 延续字符串前缀校验 / `eval` 解析 / 模糊“强隔离”口径 | 实现成本低 | 安全面、协议面、审计面都存在伪成功风险 |
| Q4 | 选项 B | realpath 边界校验 + 显式字段解析 + 口径与 runtime evidence 对齐 | 安全性高，文档真实 | 需要额外修补历史兼容路径 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 选项 B | 用户指出的问题不是单次失误，而是任务跟踪失效；必须让 `.dev-task.md` 真正接管 Layer B canonical truth | NORVEN_DECIDE + CAP_DECIDE |
| Q2 | 选项 B | review / report / notify / commit 都必须纳入可延续 pending closure，而不是继续依赖“宿主也许会做” | CAP_DECIDE |
| Q3 | 选项 B | 只有冻结旧锚点后再做 trace，才不会把旧能力先删掉再自证无回归 | CAP_DECIDE |
| Q4 | 选项 B | host-agent interop 的真实风险来自边界与生命周期事务流，必须用物理校验替代表面约束 | NORVEN_DECIDE + CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `ARCHITECTURE.md` | 修改 | 重写为三体分层、authority chain、host-agent interop governance、能力矩阵与证明层 |
| `compass/docs/architecture-capability-trace.yaml` | 新建 | 冻结旧架构能力锚点，并完成 `24 intact / 5 behavior_changed_but_acceptable / 0 deferred_follow_up` 的 trace audit |
| `compass/tools/redcap-interop-governance.sh` | 新建 | 提供 evidence-only interop audit 与 pending-closure contract helper |
| `compass/tools/redcap-dev-task.sh` | 新建 | 为 `.dev-task.md` 提供 canonical pointer / confirmed hash / active slice 解析能力 |
| `compass/tools/redcap-pm-gate-check.sh` | 新建 | 把 Layer B PM Gate 变成可执行门禁 |
| `compass/tools/redcap-drift-check.sh` | 新建 | 审计 active_slice / scope / confirmed hash 漂移 |
| `compass/tools/redcap-host-workboard-sync.sh` | 新建 | 宿主 workboard 改为 mirror-only，并校验整块 canonical pointer |
| `compass/tools/redcap-layerB-session-start.sh` | 修改 | Layer B 进入时接入 runtime attach、pending closure 审计与 safe degraded 语义 |
| `compass/tools/redcap-task-report-register.sh` | 修改 | task report 先满足 closure obligation 再允许写 marker，拒绝伪登记成功 |
| `compass/tools/redcap-task-report-check.sh` | 修改 | task report 校验切到真实模板关键章节与 diff 证据审计 |
| `compass/tools/redcap-on-stop-review.sh` | 修改 | stop-review 接入 control-plane / pending closure / degraded 记账 |
| `compass/tools/redcap-layerB-session-end.sh` | 修改 | SessionEnd 必须同时满足 review / pm-gate / drift / report / notify，且 review 仅 `PASS` 才放行 |
| `compass/tools/redcap-on-complete.sh` | 修改 | 新增 commit proof gate：无 `INITIAL_HEAD`、worktree 脏、无新 commit 均 fail-closed |
| `loom/tools/redcap-layerA-stop.sh` | 修改 | Layer A owner lease 改为 `EXIT trap` 清理，避免失败路径残留僵尸 lease |
| `compass/tools/baton-delegate.sh` | 修改 | delegation request/result 强制 realpath 边界校验，拒绝 symlink 越界 |
| `prism/tools/prism-run-state.sh` | 新建 | 建立 run-scoped registry / owner / legacy resolve helper |
| `prism/tools/prism-coordinator.sh` | 新建 | Coordinator Phase A 统一 start-run / register-agent / collect / resolve-handle |
| `prism/tools/prism-archive-check.sh` | 修改 | 去掉 `eval`，改为显式 TSV 解析 registry 字段，并绑定报告 run_id 校验 |
| `prism/protocol.md` | 修改 | 将 Dispatch Firewall 明确收口为 prompt 级隔离 + dispatch gate，而非伪装成物理强制 |
| `compass/CONTRIBUTING.md` | 修改 | 强化 §10 / §12 / §13，使 `.dev-task.md`、书记协议、任务级完成复盘形成闭环 |
| `compass/knowledge/explore-notes.md` | 修改 | 归档 Q7，并显式把结果链到 run-state / coordinator / protocol / 本任务报告 |
| `compass/knowledge/lessons.md` | 修改 | 沉淀 L-45 / L-46 / L-47，固化 closure marker、owner lease、delegation boundary 经验 |

### 3.2 技术实现要点

第一，Layer B 现在有了真正的 **canonical control plane**：`.dev-task.md` 是唯一真相源，宿主 `plan.md` / workboard 只允许镜像 canonical pointer，不再允许把宿主侧叙事冒充执行真相。  
第二，host/native 边界被做成 **pending-closure contract**：task report、stop-review、SessionEnd、on-complete 不再各自零散判断，而是统一把“缺 review / 缺 report / 缺 notify / 缺 commit”转成可延续的 obligation。  
第三，closure chain 改成 **proof-based**：`redcap-layerB-session-end.sh` 只有在 review 显式 `PASS` 时才视为通过；`redcap-on-complete.sh` 只有在 worktree 干净且本轮确有新 commit 时才允许收尾；notify 失败不再写成功 marker。`redcap-on-stop-review.sh` 也不再在 `PASS` 后删除证明文件，保证 SessionEnd 能消费到持久化 review proof。  
第四，Layer A 的跨会话事务资源被收紧：`workflow-owner-session` 不再只在成功路径释放，而是提升为 `EXIT` 级清理，避免失败路径把 owner lease 卡死。  
第五，宿主镜像面与 delegation 边界都补成了物理校验：`redcap-host-workboard-sync.sh` 不再只看 `confirmed_hash`，而是校验整块 canonical pointer；`baton-delegate.sh` 改成 realpath 边界，堵住 symlink request/result 旁路。  
第六，Prism 的 run 级真相层从全局模糊 registry 迁到 `prism/runs/<run_id>/session-registry.yaml`，并通过 `prism-run-state.sh` / `prism-coordinator.sh` 统一入口；`prism-archive-check.sh` 也去掉了 `eval` 这一层命令执行面。  
第七，pending-closure 现在会持久化 `baseline_head / audited_head`，并按同一 `task_id` 的未清 state 持续继承，不会因为 confirmed hash 改变或同一路径重复登记而把旧 proof window 覆盖掉。  
第八，pending-closure 的读改写与清理现在都经过 task-scoped lock；清理还要求 `updated_at` CAS 匹配，防止旧会话删掉别的会话刚写入的新 state。  
第九，架构层不再靠“我觉得没坏”来审查：`ARCHITECTURE.md` 重写后，以 `architecture-capability-trace.yaml` 对旧能力做三向追踪，最终结论为 `24 intact / 5 behavior_changed_but_acceptable / 0 deferred_follow_up`。

### 3.3 关联变更

本次 tranche 的后半段由用户的中途 review 强制纠偏：当技术逻辑已经收口时，用户指出“没有 commit、没有飞书”，从而暴露出 **任务完成 ≠ 技术 tranche 收口** 这一更深层问题。  
因此本次不仅修技术链，还补了 §13 Task Completion Review Gate：文档一致性扫描、`explore-notes.md` 全量归档、任务级 rereview、最终任务报告纳管，都被重新纳入闭环。  
同时，Q7 的归档条目和本报告路径互相引用，防止未来再次出现“讨论已沉淀，但没有最终报告落点”的断链。

---

## 四、人工审核要点

> ⚠️ 以下是 Norven 需要重点确认的内容，其他部分 Cap 已自行验证。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | `host-agent-interop-governance` 后续是否继续上升为长期治理主线 | 本 tranche 已把批准范围内的 authority / closure / trace 闭合，但宿主 direct skill / resume / lifecycle 更深层冲突仍值得单独立题 | P1 |
| 2 | Prism Dispatch Firewall 是否未来需要升级为物理强制隔离 | 当前结论是 prompt-level hard limitation + dispatch gate，已真实记录为 `behavior_changed_but_acceptable`，是否继续物理化属于后续方向决策 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| closure 脚本语法检查 | `bash -n compass/tools/redcap-on-complete.sh && bash -n compass/tools/redcap-layerB-session-end.sh && bash -n prism/tools/prism-archive-check.sh` | ✅ |
| on-complete 脏 worktree 阻断 | `REDCAP_SKIP_FEISHU=1 bash compass/tools/redcap-on-complete.sh <tmp-project> <initial_head> test`（dirty worktree） | ✅ |
| on-complete 新 commit 放行 | `REDCAP_SKIP_FEISHU=1 bash compass/tools/redcap-on-complete.sh <tmp-project> <initial_head> test`（clean + new commit） | ✅ |
| Layer B `INCONCLUSIVE` review 阻断 | `REDCAP_SESSION_BINDING_KEY=... REDCAP_SKIP_FEISHU=1 bash compass/tools/redcap-layerB-session-end.sh claude` | ✅ |
| stop-review `PASS` 证明持久化 | `PATH=<stubbed-agent-path> ... bash compass/tools/redcap-on-stop-review.sh` | ✅ |
| Claude deferred reconcile 可补跑 review | `PATH=<stubbed-agent-path> REDCAP_SESSION_BINDING_KEY=... bash compass/tools/redcap-layerB-session-end.sh claude` | ✅ |
| Prism archive registry 注入回归 | `bash prism/tools/prism-archive-check.sh --report <tmp-report>`（恶意 role 不触发命令执行） | ✅ |
| 非法 `task_id` 路径字符拒绝 | `redcap_interop_pending_closure_file <project> <bad-task-file>` | ✅ |
| re-anchor 后 pending closure 仍可见 | `redcap_interop_write_pending_closure <task-v1> ...` + `redcap_interop_pending_closure_file <task-v2>` | ✅ |
| 同路径重复登记不覆盖旧 proof window | `redcap_interop_write_pending_closure ... base-old/head-old` → `... base-new/head-new` | ✅ |
| stale `updated_at` 不可清除新 state | `redcap_interop_clear_pending_closure <...> <old_updated_at>` | ✅ |
| 文档一致性扫描 | `rg 'Dispatch Firewall|prompt-level hard limitation|2026-04-12-host-agent-interop-governance\\.md' ...` | ✅ |
| 任务级 closure rereview | `task-closure-rereview` | ✅（No significant issues found in the reviewed changes） |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 在真实宿主 direct skill / resume 生命周期下再观察一段窗口，确认 host/native 边界不会出现新的 authority inversion 旁路
- [ ] 若未来考虑把 Dispatch Firewall 升格为物理强制隔离，需要在真实多 Agent 调度链上补专项回归

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| Prism Dispatch Firewall 仍非物理强制隔离 | 当前批准边界只要求“口径真实 + gate 存在 + trace 可审计”，不要求本轮继续扩大为硬隔离系统 | P1 |
| 宿主 direct skill / resume 生命周期的更深层互操作治理 | 这是长期治理议题，已被本 tranche 明确识别，但不在当前批准落地范围内 | P1 |

### 6.2 触发的新问题

本次最终确认了一个新的流程性结论：**技术 tranche 收口绝不能等价于任务完成**。  
如果 §13 Task Completion Review Gate 没有被当成一等公民，系统就会再次出现“逻辑对了，但 commit / 飞书 / 任务报告 / 全量 rereview 都没发生”的伪完成。  
同时，用户关于“宿主 Agent 中执行我们自己设计的 Agent 会出现生命周期事务冲突”的判断也被证实是成立命题，后续每次升级都必须显式评估这条边界。

### 6.3 推荐的下一步行动

1. 在后续真实宿主流量中持续观察 direct skill / resume / SessionEnd 的 authority 边界，决定是否需要新增专门 hook 面。
2. 若未来要提升 Prism 隔离等级，再开独立 tranche，把 Dispatch Firewall 从 prompt-level hard limitation 推进到物理强制隔离。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-45 | closure/notified 成功标记必须绑定到关键副作用真正完成 | `notified` / `current-*` / success marker 只能在副作用真正完成后写入，`MISSING` / `INCONCLUSIVE` 也要视为 closure 缺口 |
| L-46 | 跨会话 owner lease 必须在 EXIT 级清理 | owner claim 是事务资源，不是成功路径附属清理项；否则失败路径会遗留僵尸 lease |
| L-47 | delegation 文件边界必须校验真实路径 | request/result 不能只看字符串前缀，必须用 realpath 杜绝 symlink 越界 |

### 7.2 流程改进建议

以后凡是长任务进入“看起来已经收口”的阶段，都必须把 §13 Task Completion Review Gate 当成主流程，而不是事后补丁。  
同时，只要是在宿主 Agent 里运行 RedCap 自有 Agent，就必须把生命周期事务流、authority 边界、弱宿主补偿式 closure contract 当成每次迭代的固定审查项，而不是遇到事故后再回想。

---

## 八、附录

### 附录 A：Commits

```text
d1c8a57 (HEAD -> main) docs(框架): 新增 host-agent 互操作治理设计
664333f docs(spec): add prism coordinator phase a design
31fa41d docs(spec): add multi-session isolation design
cd3027d docs(report): clarify smoke env flags
5aa15d7 fix(hooks): close host smoke gaps
21bfd4a docs(report): finalize hook-chain closure
9bae831 fix(hooks): harden layer-b completion chain
6df3418 docs(spec): add hook-chain investigation design
6fa1591 fix(prism): harden e2e archive and dispatch gates
aaa4882 fix: resolve 5 blocking issues found by multi-round duck review
```

### 附录 B：独立评审记录

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| review | `closure-review`：closure chain 的 owner lease / notify / report marker 还有没有伪成功路径 | 发现 Layer A owner lease 仅在成功路径释放，已修为 `EXIT trap` 清理 | `N/A` |
| review | `task-closure-review`：整批任务级交付闭环还有没有 blocking 缺口 | 发现 3 个高优问题：零 commit 仍可完成、`INCONCLUSIVE` 误判为成功、archive-check 存在 `eval` 注入面；本报告对应修复已落盘 | `N/A` |
| review | `task-closure-rereview`：连续修复后的整批 diff 是否仍有 blocking/high severity 问题 | No significant issues found in the reviewed changes | `N/A` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 设计文档：`docs/superpowers/specs/2026-04-12-host-agent-interop-governance-design.md`
- 能力追踪矩阵：`compass/docs/architecture-capability-trace.yaml`
- 书记归档：`compass/knowledge/explore-notes.md`（Q7 已归档）
- 主线阶段报告：`compass/docs/task-reports/2026-04-12-multi-session-isolation-mainline.md`

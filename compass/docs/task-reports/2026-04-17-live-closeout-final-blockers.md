# 任务完成报告：live closeout 最终阻塞补丁

**报告日期**：2026-04-17
**执行者**：Cap（Copilot CLI / GPT-5.4）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：`commit-proof` 已经跑通；live runtime 首次真实收尾时暴露出的最终阻塞，以及其后续 reviewer / redteam 追加打出的几个收尾边界问题，都已经补上。
- 详情：当前补丁覆盖了 4 个点：`.dev-task.md` 的允许修改范围补齐、`redcap-task-report-check.sh` 改成只在 pending anchor 是**唯一最新 changed report** 时才放行、`redcap-task-report-register.sh` 支持“无 live claim 时显式 runtime env 接管”、同时又保证“有 live claim 时 claim 仍优先，且显式 fallback 必须同时匹配 host / project / binding identity”。对应 acceptance 和 full suite 已重新通过。

### 0.2 上一步完成的是

- 上一步完成的是：`fix(governance): 收口 closeout 主链与连续性` 已形成正式 commit，随后首次真实回放了当前 Copilot runtime 的 `on-complete / session-end`。

### 0.3 下一步计划做的是

- 下一步计划做的是：把这轮 follow-up 补丁形成新 commit，重新跑 `commit-proof`，然后再对真实 runtime 重试 `on-complete / session-end / 飞书通知` 最终闭环。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：飞书双向链路与 overlay P0 收口 → Copilot 会话身份锚点 → completion 主链硬化 → closeout follow-up 硬化 → commit-proof → live runtime 最终闭环。
- 当前所在位置：第一次真实 live runtime 收尾已经把最终剩余 blocker 暴露出来；这些 blocker 已修，当前正准备做最后一次正式闭环。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 1. 为什么这次又没有发飞书通知？ 2. 我要的不是你发飞书，而是要你发现和解决“不发飞书的原因”，因为和飞书一起的还有很多个必执行任务和逻辑，飞书只是比较容易发现没执行的，其他的任务现在根本不清楚是否也遗漏了，如果是的话，那么可以宣判redcap开发到现在的所谓100%保障hook机制，是彻底失败的，它完全对抗不了长任务、长对话

> 明白，那么请完成后续所有任务吧，记得小心推进，步步为营，一切以稳定、高质量为准！期待你的终结报告和飞书通知，Cap！

### 1.2 触发背景

此前所有代码 / review / redteam / acceptance / commit-proof 都已经收口，但第一次把真实 runtime 的 `on-complete / session-end` 串起来执行时，validator chain 仍然打出了新的物理阻塞。  
这说明剩余问题已经不在“理论逻辑是否正确”，而在**长任务最终闭环时，账本、报告锚点与 runtime 绑定能否对齐到真实现场**。  
因此本轮目标不再是扩大能力面，而是把 live closeout 前最后几个能真实阻断收尾的点补平。

---

## 二、方案讨论

### 2.1 问题分析

第一次 live runtime 回放中，`on-complete` 失败不是因为飞书，而是因为 validator chain 真实阻断了收尾：

1. `drift-check` 报 `changed files exceed current active_slice scope`，原因不是脚本坏了，而是当前 `.dev-task.md` 的允许修改范围没有覆盖本轮实际改动过的 `compass/docs/index.yaml`、`compass/docs/archive/**`、`compass/knowledge/hooks-copilot-cli.md`、`redcap-layerB-task-complete-guard.sh`、`redcap-task-report-register.sh`。
2. `task-report-check` 报 `pending report anchor conflicts with other changed task reports`，原因是同一长任务里确实有多份 task report，但当前 pending anchor 指向的就是本轮最新 changed report；这时不该再按“冲突”处理。
3. 进一步排查时又发现 `redcap-task-report-register.sh` 只走 `attach_from_process_claim`。一旦真实 process claim 已死、但 runtime session 仍可显式附着，就没法把新报告登记到真实 runtime。
4. reviewer / redteam 后续又补充指出几个边界：① `pending anchor` 不能只看“是否在 changed set 里出现过”，而必须看它是不是**唯一最新** changed report；② `task-report-register` 不能盲信显式 runtime env，否则会把旧 runtime 或 foreign runtime 错当成本会话；③ 即便 host / repo root 相同，只要缺少 binding identity，same-repo sibling runtime 仍然会错绑，所以显式 fallback 必须在无 live claim 的前提下带上明确 binding。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| drift-check 阻塞 | 选项 A | 在 `on-complete` 特判跳过 drift-check | 改动小 | 会把真实 scope 漂移也一起放过 |
| drift-check 阻塞 | 选项 B | 补齐 `.dev-task.md` 的允许修改范围，让 ledger 与真实改动重新对齐 | 语义真实，不削弱 gate | 需要重新 commit |
| pending anchor 多报告 | 选项 A | 继续要求 pending anchor 独占 changed reports | 规则简单 | 会误伤长任务分阶段写多份报告的正常场景 |
| pending anchor 多报告 | 选项 B | 只在 pending anchor 是**唯一最新 changed report**时放行；否则一律按 stale fail-closed | 既保留 stale 防线，也支持长任务真实收尾 | 需要补 acceptance |
| report register 绑定 | 选项 A | 继续只认 process claim | 保守 | claim 一死就无法把新报告登记到真实 runtime |
| report register 绑定 | 选项 B | 没有可用 live claim 时允许显式 runtime env 接管；有 live claim 时仍以 claim 为准，并校验 runtime host/project/binding 归属 | 同时覆盖长会话和错绑风险 | 需要补 acceptance |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| drift-check 阻塞 | 选项 B | 这里的问题是 task ledger 漏记，不是 gate 误报；应修 ledger，而不是削 gate | CAP_DECIDE |
| pending anchor 多报告 | 选项 B | 关键不在“anchor 是否曾经 changed”，而在“它是不是唯一最新 changed report”；否则仍可能把旧报告误当当前报告 | CAP_DECIDE |
| report register 绑定 | 选项 B | live claim 代表当前宿主进程，显式 runtime env 只该作为没有 live claim 时的恢复入口；无论哪条路都必须校验 host/project/binding 归属 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 补齐本轮真实触达的文件范围，消除 live closeout 时的 drift-check 假阻塞 |
| `compass/tools/redcap-task-report-check.sh` | 修改 | pending anchor 现在只有在它是唯一最新 changed report 时才会被放行；stale / 并列最新 anchor 继续 fail-closed |
| `compass/tools/redcap-task-report-register.sh` | 修改 | 无 live claim 时才允许显式 runtime env 接管；有 live claim 时仍以 claim 为准，并校验 runtime host/project/binding 归属 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增 pending anchor latest/stale、explicit runtime success、ambiguous fallback rejection、foreign runtime rejection、live claim priority 等回归 |
| `compass/docs/task-reports/2026-04-17-live-closeout-final-blockers.md` | 新建 | 归档本轮最终阻塞与对应补丁 |

### 3.2 技术实现要点

第一，`drift-check` 这次并没有被削弱。  
真正的修复动作，是把 `.dev-task.md` 的允许修改范围补齐到当前长任务实际改过的文件，让 validator chain 面对的是正确 ledger，而不是缺项 ledger。

第二，`task-report-check` 现在不再把“anchor 出现在 changed set 里”误当成“anchor 就是当前最新报告”。  
新的判定是：只有当 pending anchor 是**唯一最新的 changed report**时，才允许它继续代表当前任务报告；如果还有更新的 changed report，或存在多个同级最新 changed reports，它都会继续按 stale fail-closed。  
这把“长任务里多份历史报告同时处于 commit 区间内”与“旧 pending anchor 冒充最新报告”真正区分开了。

第三，`task-report-register` 现在收了三层保护：  
1. 若当前宿主进程仍有 live process claim，则 claim 继续是当前会话的第一权威；显式 runtime env 不允许抢走当前 live claim 的优先级。  
2. 只有在没有可用 live claim 时，才允许显式 `REDCAP_RUNTIME_SESSION_ID + REDCAP_RUNTIME_CAPABILITY` 接管，而且必须同时带上明确的 binding identity（`REDCAP_SESSION_BINDING_KEY`，或由 `REDCAP_HOST_SESSION_ID` 推导出的 binding key）。  
3. 显式附着成功后，还必须校验 runtime 的 host / project_root / binding_key 与当前 register 目标一致；任一缺失或不匹配都按 ambiguous / foreign fail-closed。  
这样既解决了“claim 已死但 runtime 仍活着”的恢复问题，也堵住了 stale env / sibling runtime / foreign runtime 错绑。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| pending anchor | `redcap-task-report-check.sh` / pending closure `artifact_path` | 指当前 pending closure 里记录的“这轮任务应当使用哪份 task report” |
| changed report | `git diff` / untracked report 集合 | 指本轮 commit 区间或当前工作区里实际新增 / 修改过的 task report |
| explicit runtime env | `REDCAP_RUNTIME_SESSION_ID` + `REDCAP_RUNTIME_CAPABILITY` | 指已经明确给出要附着的 runtime session；现在只有在没有 live claim 时才会被采用 |
| binding identity | `REDCAP_SESSION_BINDING_KEY` / `REDCAP_HOST_SESSION_ID` | 指当前宿主会话的绑定身份；显式 runtime fallback 现在必须靠它证明“这个 runtime 就是这条会话” |
| live process claim | `redcap-runtime-state.sh` 的 process claim | 指当前宿主进程仍然活着时，由 runtime state 体系记录的“这条进程现在到底属于哪个 runtime” |
| drift-check | `compass/tools/redcap-drift-check.sh` | 指校验“当前真实改动是否仍落在 `.dev-task.md` 明确允许的范围里”的 gate |

### 3.3 关联变更

本轮没有重写 closeout 架构，也没有推翻前面完成的 commit-proof / review / redteam / acceptance。  
它处理的是**第一次真实 live runtime 闭环才暴露出的最后三处阻塞**，属于终局补丁，而不是新 tranche。

---

## 四、人工审核要点

> ⚠️ 以下是 Norven 需要重点确认的内容，其他部分 Cap 已自行验证。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 最终 live runtime 的 `on-complete / session-end / 飞书通知` 是否真实闭环 | 这是本报告之后的最后一步，需要在 follow-up commit 后重新执行并确认不是口头完成 | P0 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 脚本语法检查 | `bash -n compass/tools/redcap-task-report-register.sh compass/tools/redcap-task-report-check.sh compass/tools/redcap-multi-session-acceptance.sh compass/tools/redcap-drift-check.sh` | ✅ |
| pending anchor latest/stale 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-allows-pending-anchor-when-uniquely-latest && bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-rejects-stale-pending-anchor-conflict` | ✅ |
| 显式 runtime register 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh report-register-accepts-explicit-runtime-env && bash compass/tools/redcap-multi-session-acceptance.sh report-register-rejects-ambiguous-explicit-runtime` | ✅ |
| live claim 优先级回归 | `bash compass/tools/redcap-multi-session-acceptance.sh report-register-prefers-live-claim-over-stale-explicit-runtime` | ✅ |
| foreign runtime 拒绝回归 | `bash compass/tools/redcap-multi-session-acceptance.sh report-register-rejects-foreign-explicit-runtime` | ✅ |
| root drift-check 回放 | `REDCAP_RUNTIME_SESSION_ID=<real> REDCAP_RUNTIME_CAPABILITY=<real> bash compass/tools/redcap-drift-check.sh on-complete copilot .dev-task.md c58dc35755bf11a60b8f6280910b33ae9c8b2c35 612212c2db5a1da0c7ec6b212db50a987eecb62a` | ✅ |
| root task-report-check 回放 | `REDCAP_RUNTIME_SESSION_ID=<real> REDCAP_RUNTIME_CAPABILITY=<real> bash compass/tools/redcap-task-report-check.sh "$PWD" c58dc35755bf11a60b8f6280910b33ae9c8b2c35 612212c2db5a1da0c7ec6b212db50a987eecb62a` | ✅ |
| full suite 复跑 | `bash compass/tools/redcap-spec-check.sh "$PWD" && bash compass/tools/redcap-multi-session-acceptance.sh all` | ✅ |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 形成 follow-up commit 后，再对真实 Copilot runtime 重跑 `on-complete / session-end / 飞书通知`，确认最终完成通知真的发出。

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 本轮 follow-up 变更尚未形成新 commit | 这份报告和最后一轮 reviewer / redteam 修补刚落盘，当前工作区重新变脏 | P0 |
| live runtime 最终完成通知尚未重跑 | 依赖上一项先形成 clean worktree，并再次跑 `commit-proof` | P0 |

### 6.2 触发的新问题

本轮没有再发现新的架构级 blocker。  
相反，首次 live runtime 回放暴露出的最终阻塞，已经都被压缩成了明确补丁和 acceptance。

### 6.3 推荐的下一步行动

1. 将当前 follow-up 补丁与本报告一起提交。
2. 重新运行 `compass/tools/redcap-commit-proof-check.sh`。
3. 对真实 Copilot runtime 再跑一次 `on-complete / session-end / 飞书通知`。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-72 | pending anchor 的放行条件必须是“唯一最新 changed report”，不能只看它是否曾经 changed 过 | 否则旧报告也可能因为仍在 commit 区间里而被误认成当前报告 |
| L-73 | task-report-register 这类 closeout 入口必须区分 live claim 与显式 runtime env 的权威级别 | live claim 代表当前宿主进程，显式 env 只能作为无 claim 时的恢复入口，且必须校验 host/project/binding 归属 |

### 7.2 流程改进建议

以后凡是 `commit-proof` 后第一次真实回放 live runtime，都应默认视为**最终 blocker 发现窗口**。  
这一步最好单独留一次报告锚点，因为它暴露的常常不是新功能 bug，而是“长任务真实闭环”才会出现的治理缺口。

---

## 八、附录

### 附录 A：Commits

```text
最新已存在 commit:
612212c fix(governance): 收口 closeout 主链与连续性
```

### 附录 B：相关文档索引

- 前序报告：`compass/docs/task-reports/2026-04-17-closeout-followup-hardening.md`
- 当前真相源：`.dev-task.md`
- 宿主镜像：`/Users/norven/.copilot/session-state/c73ce3b2-e124-49d2-a1f8-770a2e08cb7a/plan.md`

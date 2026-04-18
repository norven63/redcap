# 任务完成报告：live closeout 最终阻塞补丁

**报告日期**：2026-04-17
**执行者**：Cap（Copilot CLI / GPT-5.4；Codex 接盘续修）
**报告版本**：v1.4

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：首次真实 live runtime 收尾暴露出的最终阻塞，以及其后 reviewer / redteam / final sweep 继续挖出的 marker anchor 漏网、acceptance 脆弱性、真实工作区删除风险、独立评审执行器失效、stop-review 结果判定边界问题、`on-complete` 校验宿主误传问题、`session-end` 清 pending 时的陈旧 `updated_at` 竞态问题、Codex CLI reviewer fallback 缺失问题、以及 reviewer timeout 子进程逃逸问题，都已经补上。
- 详情：当前补丁最终覆盖了 closeout 主链最后一批关键点：`.dev-task.md` 的允许修改范围补齐、`redcap-task-report-check.sh` 改成只在 pending / marker anchor 是**唯一最新 changed report** 时才放行、`redcap-task-report-register.sh` 支持“无 live claim 时显式 runtime env 接管”、同时又保证“有 live claim 时 claim 仍优先，且显式 fallback 必须同时匹配 host / project / binding identity”、`redcap-multi-session-acceptance.sh` 里一批 root-history 敏感 case 已改成 fixture repo / 稳定隔离断言、误删真实 `compass/docs/task-reports` 的危险 cleanup helper 已被移除，以及 `redcap-on-stop-review.sh` / `redcap-layerB-session-end.sh` 现在会按健康 fallback 执行独立评审、透传真实宿主身份、把 reviewer stdout/stderr 分离处理、仅在成功退出时直接接受结构化评审结果、成功但不可解析时继续 fallback、把 JSON `result` 做大小写归一化、兼容 bare / uppercase fenced JSON、优先选择**真正能 parse 成 JSON 的 fence candidate**，并把 transport failure detector 收紧到**整行 CLI 错误形状**；最后又把“stdout 已拿到结构化结果”这条路径做成非对称语义：stderr 允许用 `failure-block` 识别“错误行 + hint/note”这类真实 transport failure，而 stdout residual 继续保持更严格的纯错误块判定，从而既不漏掉 stderr 里的真实 failure block，也不把 review 正文里原样引用的错误块误杀成 transport failure。接盘补丁又把 `task-complete guard -> redcap-on-complete.sh -> validator-chain` 这段链路的宿主身份补实：guard 会用当前 `HOST` 覆盖旧环境，`on-complete` 解析校验宿主时按“显式 host → 绑定身份 → runtime host → redcap 兜底”的顺序选择，并把同一个 host 同步写入 validator chain 的位置参数和 `REDCAP_RUNTIME_HOST` 环境变量，避免 Copilot 场景被项目名 `redcap` 或陈旧 `claude` 环境污染。再次 live `session-end` 时又暴露出最后一层收口竞态：长耗时 validator / review 窗口中 pending closure 可能被兼容路径或重试路径改写，导致旧 `updated_at` 的 CAS 清理被正确拒绝；现在 `session-end` 会在全绿后重新读取当前 pending，并且只有在同一任务身份、head 区间仍被本次 validator 覆盖、redline 属于本次成功可清集合时，才用最新 `updated_at` 清理。最新 live `session-end` 又暴露出独立评审 fallback 列表仍少了当前可用的 Codex CLI：`gemini / copilot / claude / kimi` 全部不可用时，runner 现在会尝试 `codex exec`，并优先消费 `--output-last-message` 结果文件，避免 stdout/stderr 的 banner 或 warning 污染评审 payload。

### 0.2 上一步完成的是

- 上一步完成的是：`ce38d7e fix(governance): 修复 session-end pending 刷新` 已形成正式 commit，spec-check、full acceptance、commit-proof 和真实 `on-complete` 都已通过；随后真实 `session-end` 又暴露出新的 `required_redlines=review`，根因是四个旧 reviewer CLI 全部不可用，而 runner 没有 Codex fallback。

### 0.3 下一步计划做的是

- 下一步计划做的是：形成 Codex reviewer fallback follow-up commit，再以本报告为锚点执行最后一轮 live runtime 收尾闭环，确认 `commit-proof` 与真实 `on-complete / session-end / 飞书通知` 在这版补丁上再次对齐。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：飞书双向链路与 overlay P0 收口 → Copilot 会话身份锚点 → completion 主链硬化 → closeout follow-up 硬化 → commit-proof → live runtime 最终闭环。
- 当前所在位置：第一次真实 live runtime 收尾已经把最终剩余 blocker 暴露出来；stop-review 边界、on-complete 校验宿主、session-end pending refresh、以及 Codex reviewer fallback 都已修，当前正准备形成最后一个 follow-up commit 并做正式闭环。

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
5. 在准备最终汇报前又做了一次 final sweep，发现 `task-report-check` 的 marker 分支仍残留旧条件：marker 报告如果在 commit 区间里“曾经 changed 过”，就可能在出现更新报告后仍被误判为当前报告。与此同时，`layerb-concurrency`、`sessionstart-auto-reconcile-*`、`task-report-check-prefers-anchor` 等 acceptance 也暴露出对当前 repo HEAD / root worktree 残留过于敏感的脆弱断言。
6. 在最后一轮 code review 中又发现，acceptance 脚本残留了一个危险的 cleanup helper：它会对真实仓库 `compass/docs/task-reports` 下的 `zz-acceptance-*` / `zz-review-*` 报告做 glob delete。这个 helper 即便不再是主路径，也会让回归脚本具备误删真实工作区文件的能力，因此必须直接移除。
7. 真正再次回放 live runtime `session-end` 时，又暴露出一条新的物理阻塞：独立评审执行器当前只要检测到 `kimi` 存在，就会优先硬撞 `kimi`，既不区分“命令存在”和“当前已登录/可用”，也没有 timeout / auth failure fallback；同时它仍把宿主身份写死成 `claude`，导致 Copilot 场景下的 review gap 记录与日志宿主也会失真。进一步修补 review runner 后，最终 code review 又追出一个同域问题：transport failure 检测若只按 `FAIL` / `unauthorized` 之类的裸子串匹配，也会把**合法评审结果正文**误判成执行器失败。随后 red team 与下一轮 code review 又继续把边界推实：如果 reviewer CLI 非零退出、或成功退出但结果不可解析，旧逻辑仍可能停在当前 agent 而不继续 fallback；同时若把 stdout/stderr 混在一起处理，structured JSON、stderr 警告、以及 plain-text `PASS` + `fail-closed` 这类正常输出也会互相污染，继续制造假失败或假通过。再往后，fence 兼容性和 residual prose 也被继续压实：parser 只认小写 ` ```json `，不认 bare ` ``` ` / ` ```JSON `，会把合法 structured PASS/FAIL 错打成 fallback；而如果 transport detector 继续按残余 prose 的宽子串匹配，像 `The authentication failed path remains fail-closed.` 这种 JSON fence 外说明句，也会再次把合法 structured PASS 误杀成 CLI failure。最后一轮 red team 又把 structured-review transport 边界推到最终形态：如果沿用“任意一行命中”，quoted error line in prose 会误杀 structured PASS；如果把 stdout residual 也按 `failure-block` 放大，又会把 reviewer 原样引用的错误块误杀成 transport failure。因此最终实现不能把 stderr 与 stdout residual 混成一条规则：stderr 可以识别 `error line + hint` 这类真实 failure block，而 stdout residual 必须继续保持更严格的纯错误块语义。
8. stop-review 边界收口后，code review 又抓到 `on-complete` 的真实物理根因：`redcap-layerB-task-complete-guard.sh` 虽然知道当前宿主是 `copilot`，但旧链路只把项目名 `redcap` 作为 `redcap-on-complete.sh` 的第三个参数传入；而 `redcap-on-complete.sh` 又把 validator chain 的 host 固定成 `redcap`，或可能被外层残留的 `REDCAP_RUNTIME_HOST=claude` 污染。这样就会出现“当前任务实际来自 Copilot，但 validator / report register 认为它来自 redcap 或 claude”的分裂。
9. `on-complete` host follow-up commit 形成后，真实 `session-end` 再次回放时出现“validator 全部 PASS，但 pending closure 仍被写回”的矛盾状态。排查后确认不是 review / PM Gate / drift / task report 任一校验失败，而是 `session-end` 在脚本开头读取了旧 pending 的 `updated_at`，随后长耗时 review / validator 窗口中 pending 被兼容路径或重试路径改写；最后脚本仍拿旧 `updated_at` 做 CAS 清理，被保护机制正确拒绝，于是写回 `required_redlines=pending-closure`。这类情况下不能粗暴跳过 CAS，也不能无条件清掉当前 pending；必须先重新读取当前 pending，并证明它仍是同一任务身份、同一 head 覆盖窗口内、且 redline 已被本次成功 session-end 覆盖。
10. `session-end` pending refresh commit 形成后，真实 `session-end` 再次回放，reanchor / PM Gate / drift / backlog / spec / task-report / artifact-lifecycle / notify 全部 PASS，但最终留下 `required_redlines=review`。这次根因不在 validator，而在独立评审 fallback 列表：`gemini` exit-1、`copilot` timeout、`claude` timeout、`kimi` exit-1 后，runner 没有继续尝试本机已经可用的 `codex exec`。同时 Codex CLI 会输出 banner / warning，必须通过 `--output-last-message` 取得干净 payload。第一次把 Codex 插到 Gemini 后面再 live 回放时，又暴露出 Gemini CLI timeout 会留下 node 子进程并让 Bash runner 高 CPU 自旋；因此 timeout 必须杀整个进程组，且当前环境应优先尝试健康的 Codex，再降级到 Gemini。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| drift-check 阻塞 | 选项 A | 在 `on-complete` 特判跳过 drift-check | 改动小 | 会把真实 scope 漂移也一起放过 |
| drift-check 阻塞 | 选项 B | 补齐 `.dev-task.md` 的允许修改范围，让 ledger 与真实改动重新对齐 | 语义真实，不削弱 gate | 需要重新 commit |
| pending anchor 多报告 | 选项 A | 继续要求 pending anchor 独占 changed reports | 规则简单 | 会误伤长任务分阶段写多份报告的正常场景 |
| pending anchor 多报告 | 选项 B | 只在 pending anchor 是**唯一最新 changed report**时放行；否则一律按 stale fail-closed | 既保留 stale 防线，也支持长任务真实收尾 | 需要补 acceptance |
| marker anchor 多报告 | 选项 A | marker 继续沿用“只要它在 changed set 里出现过就算当前报告” | 兼容旧逻辑 | 会把 commit 区间里较早 changed 的旧 marker 误当成当前报告 |
| marker anchor 多报告 | 选项 B | marker 与 pending 同步：只有它是**唯一最新 changed report**时才放行 | 语义统一，能真正挡住 stale marker 冒充 | 需要补 allow/reject 双向 acceptance |
| report register 绑定 | 选项 A | 继续只认 process claim | 保守 | claim 一死就无法把新报告登记到真实 runtime |
| report register 绑定 | 选项 B | 没有可用 live claim 时允许显式 runtime env 接管；有 live claim 时仍以 claim 为准，并校验 runtime host/project/binding 归属 | 同时覆盖长会话和错绑风险 | 需要补 acceptance |
| acceptance 稳定性 | 选项 A | 继续让 root-based case 隐式共享当前 root worktree 的 acceptance 临时报告与“只看 alerted-head”之类的脆弱断言 | 改动少 | 会随着 HEAD 演化和前序 case 残留不断出现假失败 |
| acceptance 稳定性 | 选项 B | 改成 fixture repo / validator stub，并把并发 case 改为断言 runtime 终态 marker 隔离；禁止再对真实 root task-report 目录做通配删除 | 真实覆盖目标性质，降低时序/历史污染，也不会误伤工作区 | 需要补 case |
| 独立评审执行器 | 选项 A | 继续沿用“有 kimi/claude 命令就直接调用”的单路由脚本 | 改动小 | 一旦首选 CLI 未登录、超时或空输出，真实 session-end 会持续假失败 |
| 独立评审执行器 | 选项 B | 区分“命令存在”与“当前可用”，按 `codex → gemini → copilot → claude → kimi` 做 timeout / auth failure fallback，并透传真实宿主身份 | 既保住独立评审强约束，也能在宿主切换时维持真实 review 证据；Copilot 限流时可由 Codex 接管 OpenAI 族 reviewer，并避开当前 Gemini timeout 逃逸风险 | 需要补 acceptance |
| on-complete 校验宿主 | 选项 A | 继续把 project_name / `REDCAP_RUNTIME_HOST` 当作 validator host | 改动小 | 会把项目名 `redcap` 或陈旧 `claude` 环境误当成当前宿主 |
| on-complete 校验宿主 | 选项 B | task-complete guard 显式传当前 `HOST`，on-complete 再按“显式 host → 绑定身份 → runtime host → redcap 兜底”解析，并同步覆盖 validator 的参数与环境 | 避免当前宿主与 validator 环境分裂，可覆盖 stale env | 需要补 host passthrough acceptance |
| session-end pending 清理 | 选项 A | CAS 清理失败后直接忽略 pending 或无条件重试清理 | 改动小 | 可能误清并发新写入的真实 blocker，破坏 fail-closed |
| session-end pending 清理 | 选项 B | 全绿后刷新读取当前 pending；只有同一任务身份、head 区间被本次 validator 覆盖、redline 属于本次成功可清集合时，才用最新 `updated_at` 清理 | 保留 CAS 防线，同时允许兼容/重试路径的等价改写被安全核销 | 需要补兼容刷新 acceptance |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| drift-check 阻塞 | 选项 B | 这里的问题是 task ledger 漏记，不是 gate 误报；应修 ledger，而不是削 gate | CAP_DECIDE |
| pending anchor 多报告 | 选项 B | 关键不在“anchor 是否曾经 changed”，而在“它是不是唯一最新 changed report”；否则仍可能把旧报告误当当前报告 | CAP_DECIDE |
| marker anchor 多报告 | 选项 B | pending 与 marker 不应出现两套 stale 语义；只修 pending、不修 marker，仍会把旧报告从另一条入口放进来 | CAP_DECIDE |
| report register 绑定 | 选项 B | live claim 代表当前宿主进程，显式 runtime env 只该作为没有 live claim 时的恢复入口；无论哪条路都必须校验 host/project/binding 归属 | CAP_DECIDE |
| acceptance 稳定性 | 选项 B | acceptance 要锁定的是目标性质，不是当前仓库某一时刻碰巧出现的 blocker/成功路径；fixture repo / stub 隔离也比对真实 task-report 目录做 glob cleanup 更安全 | CAP_DECIDE |
| 独立评审执行器 | 选项 B | stop-review 不能把“binary exists”误当成“runner healthy”，也不能在 Copilot session-end 中继续写死 `claude` 身份；必须做可用性 fallback、host 透传，并纳入当前可用的 Codex CLI | CAP_DECIDE |
| on-complete 校验宿主 | 选项 B | `project_name` 是飞书/展示用项目名，不是 runtime host；validator chain 必须拿到当前真实宿主，否则 report register / runtime fallback 会继续错绑 | CAP_DECIDE |
| session-end pending 清理 | 选项 B | 旧 `updated_at` 被拒绝是正确保护；修复点应是“刷新后证明当前 pending 仍可由本次成功覆盖”，而不是削掉 CAS | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 补齐本轮真实触达的文件范围，消除 live closeout 时的 drift-check 假阻塞 |
| `compass/tools/redcap-task-report-check.sh` | 修改 | pending / marker anchor 现在都只有在它是唯一最新 changed report 时才会被放行；stale / 并列最新 anchor 继续 fail-closed |
| `compass/tools/redcap-task-report-register.sh` | 修改 | 无 live claim 时才允许显式 runtime env 接管；有 live claim 时仍以 claim 为准，并校验 runtime host/project/binding 归属 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增 marker allow/reject 回归，把 `layerb-concurrency`、`sessionstart-auto-reconcile-*`、`task-report-check-prefers-anchor` 等 case 从 root-history 脆弱断言中解耦，移除会误删真实 root task report 的 cleanup helper，并补上 session-end pending refresh 与 Codex reviewer fallback 回归 |
| `compass/tools/redcap-on-stop-review.sh` | 修改 | stop-review 现在按 `codex → gemini → copilot → claude → kimi` 做 timeout / auth failure fallback，不再把“命令存在”误当成“评审 CLI 可用”；Codex 路径优先读 `--output-last-message`，timeout 路径会杀整个 reviewer 进程组 |
| `compass/tools/redcap-detect-agents.sh` | 修改 | agent 嗅探加入 Codex CLI，记录 `~/.codex/config.toml` mtime 与默认模型 |
| `compass/tools/redcap-layerB-session-end.sh` | 修改 | 调用独立评审时透传真实宿主身份；session-end 全绿后会安全刷新 pending closure，再按同一任务身份 / head 覆盖窗口 / 可清 redline 集合决定是否用最新 `updated_at` 清理 |
| `compass/tools/redcap-on-complete.sh` | 修改 | validator host 不再硬编码为 `redcap`；显式 host / 绑定身份会压过陈旧 runtime host，并同步写入 validator 参数与环境 |
| `compass/tools/redcap-layerB-task-complete-guard.sh` | 修改 | 调用 `redcap-on-complete.sh` 时用当前 `HOST` 覆盖旧 `REDCAP_ON_COMPLETE_HOST` 环境，避免 stale env 抢权 |
| `loom/dispatcher/agent-adapters.md` | 修改 | 记录 Codex CLI 的 headless 调用模板和 stdout/stderr 噪声隔离约束 |
| `loom/test-reports/pending-validations.md` | 修改 | 登记 Codex CLI reviewer fallback 的路由逻辑待验证项 |
| `README.md` | 修改 | 快速开始中补充 Codex CLI 作为可用宿主 / AI CLI |
| `compass/docs/task-reports/2026-04-17-live-closeout-final-blockers.md` | 修改 | 同步归档本轮最终阻塞、最新 review/redteam 结论与最后一轮 acceptance 安全修补 |

### 3.2 技术实现要点

第一，`drift-check` 这次并没有被削弱。  
真正的修复动作，是把 `.dev-task.md` 的允许修改范围补齐到当前长任务实际改过的文件，让 validator chain 面对的是正确 ledger，而不是缺项 ledger。

第二，`task-report-check` 现在不再把“anchor 出现在 changed set 里”误当成“anchor 就是当前最新报告”。  
新的判定是：只有当 pending / marker anchor 是**唯一最新的 changed report**时，才允许它继续代表当前任务报告；如果还有更新的 changed report，或存在多个同级最新 changed reports，它都会继续按 stale fail-closed。
这把“长任务里多份历史报告同时处于 commit 区间内”与“旧 pending / marker anchor 冒充最新报告”真正区分开了。

第三，`task-report-register` 现在收了三层保护：  
1. 若当前宿主进程仍有 live process claim，则 claim 继续是当前会话的第一权威；显式 runtime env 不允许抢走当前 live claim 的优先级。  
2. 只有在没有可用 live claim 时，才允许显式 `REDCAP_RUNTIME_SESSION_ID + REDCAP_RUNTIME_CAPABILITY` 接管，而且必须同时带上明确的 binding identity（`REDCAP_SESSION_BINDING_KEY`，或由 `REDCAP_HOST_SESSION_ID` 推导出的 binding key）。  
3. 显式附着成功后，还必须校验 runtime 的 host / project_root / binding_key 与当前 register 目标一致；任一缺失或不匹配都按 ambiguous / foreign fail-closed。  
这样既解决了“claim 已死但 runtime 仍活着”的恢复问题，也堵住了 stale env / sibling runtime / foreign runtime 错绑。

第四，acceptance 现在锁定的是“要保证什么”，而不是“碰巧走哪条路径”。
`layerb-concurrency` 不再假定 session-end 一定落到 blocker-alert 路径，而是断言每个 runtime 都会各自写出属于自己的终态 marker（`notified-head` 或 `alerted-head`）；`sessionstart-auto-reconcile-*` 与 `task-report-check-prefers-anchor` 这类 root-sensitive case 则迁移到 fixture repo / validator stub，避免前序 case 留下的 `zz-acceptance-*` 报告把后序 case 污染成假红。
本轮接盘时还把 `session-end-notify-timeout-releases-lock` 的通知超时窗口从 `1s sleep 3s` 调整为 `2s sleep 5s`：它仍然验证“通知超时后锁会释放”，但避免全量 suite 高负载时 Python 子进程刚启动就被 1 秒窗口误杀成假红。

第五，acceptance 清理逻辑现在也收回到 fail-safe。
此前最后一轮 review 又挖出一个遗留 helper，会对真实仓库 `compass/docs/task-reports` 直接执行 glob delete。这个 helper 已被移除，当前回归路径不再具备“为了清 acceptance 痕迹而误删真实 task report”的能力。

第六，独立评审执行器现在也不再把“CLI 二进制存在”误当成“当前健康可用”。
`redcap-on-stop-review.sh` 现在按 `codex → gemini → copilot → claude → kimi` 顺序尝试独立评审；对 timeout、auth failure、空输出会自动 fallback，而不是像旧逻辑那样一旦命中未登录的 `kimi` 就把整个真实 `session-end` 误判成 review P0。与此同时，`redcap-layerB-session-end.sh` 会透传真实宿主身份，避免 Copilot 场景下的 review log / review gap 继续写死成 `claude`。Codex 路径使用 `codex exec -C <repo> --sandbox read-only --ephemeral --output-last-message <file> --color never`，并优先读取 last-message 文件作为 review payload；stdout/stderr 里的 banner、插件预热 warning、网络重连提示只按 transport noise 处理。timeout 路径现在用独立进程组启动 reviewer CLI，并在超时时对整个进程组发送终止信号，避免 Gemini / Node 这类子进程在父进程被杀后继续逃逸。在 runner 判定顺序上，也把 structured review payload 和 transport noise 分离处理：结构化 `PASS/FAIL` 只从主 review output 中解析，stderr 与 JSON 外残余文本才参与 transport failure 识别；非零退出即使夹带 `result: PASS/FAIL` token 也不会被当成合法评审，成功退出但不可解析的输出会继续 fallback 到下一个 reviewer，而文本兜底也只认独立的 `PASS/FAIL` 结果行，避免把 `fail-closed` 之类正常说明句误打成 FAIL。对于 fenced JSON，parser 现在同时接受 bare fence、` ```json `、以及 ` ```JSON ` 这类大小写变体；更重要的是，不再“见到第一个 bare fence 就吃掉”，而是扫描所有候选 block，优先 `json` tag，其次 bare fence，并只接受**真正能 parse 成 JSON** 的候选。对于 transport failure detector，则只认**整行** CLI 错误形状，而不再对 residual prose 做宽子串命中，避免 JSON fence 外的正常说明句反过来误杀合法 structured review。最后，detector 采用了非对称语义：纯错误流仍按任意行命中；只要 stdout 已拿到 structured `PASS/FAIL`，stderr 就允许用 `failure-block` 识别 `error line + Hint:` 这类真实 transport failure，而 stdout residual 继续保持更严格的纯错误块判定，因此 `Observed failing path:` 或原样引用的错误块不会被轻易误杀。

第七，`on-complete` 的 validator host 现在不再由项目名或陈旧环境变量隐式决定。
`redcap-layerB-task-complete-guard.sh` 调用 `redcap-on-complete.sh` 时，会把当前 guard 收到的宿主参数写成 `REDCAP_ON_COMPLETE_HOST="$HOST"`，并覆盖外层可能残留的旧值。`redcap-on-complete.sh` 自己再按“显式 host → `host/<宿主>/session/<会话>` 绑定身份 → `REDCAP_RUNTIME_HOST` → `redcap` 兜底”的顺序解析 validator host，然后同时传给 validator chain 的第二个参数和 `REDCAP_RUNTIME_HOST` 环境变量。这样即使外层残留 `REDCAP_RUNTIME_HOST=claude`，Copilot 的 `task-complete` 收尾也会继续以 `copilot` 身份进入 validator / report register 链。

第八，`session-end` 现在不会再把“旧 `updated_at` 清理失败”直接等价成新的业务 blocker。
全绿路径里，`redcap-layerB-session-end.sh` 会先重新读取当前 pending closure。若当前 pending 已被长耗时窗口中的兼容路径或重试路径改写，它不会绕过 CAS，而是先证明三件事：任务身份仍是当前 `.dev-task.md` 的 confirmed hash；pending 的 baseline/audited head 仍落在本次 session-end validator 已覆盖的区间；当前 redline 只包含本次成功路径能够核销的 `review / pending-closure / pm-gate / drift / backlog / spec / artifact-lifecycle / task-report / notify`。三者都成立时，脚本才用最新 `updated_at` 调 `redcap_interop_clear_pending_closure()`；否则继续 fail-closed 并写回 pending。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| pending anchor | `redcap-task-report-check.sh` / pending closure `artifact_path` | 指当前 pending closure 里记录的“这轮任务应当使用哪份 task report” |
| changed report | `git diff` / untracked report 集合 | 指本轮 commit 区间或当前工作区里实际新增 / 修改过的 task report |
| explicit runtime env | `REDCAP_RUNTIME_SESSION_ID` + `REDCAP_RUNTIME_CAPABILITY` | 指已经明确给出要附着的 runtime session；现在只有在没有 live claim 时才会被采用 |
| binding identity | `REDCAP_SESSION_BINDING_KEY` / `REDCAP_HOST_SESSION_ID` | 指当前宿主会话的绑定身份；显式 runtime fallback 现在必须靠它证明“这个 runtime 就是这条会话” |
| live process claim | `redcap-runtime-state.sh` 的 process claim | 指当前宿主进程仍然活着时，由 runtime state 体系记录的“这条进程现在到底属于哪个 runtime” |
| drift-check | `compass/tools/redcap-drift-check.sh` | 指校验“当前真实改动是否仍落在 `.dev-task.md` 明确允许的范围里”的 gate |
| validator host | `redcap-on-complete.sh` 传给 `redcap-validator-chain.sh` 的宿主参数 | 指当前收尾动作到底来自哪个宿主，例如 `copilot`；它不能和飞书展示用项目名 `redcap` 混用 |
| CAS / updated_at | `pending-closure/*.state` 的 `updated_at` 字段 | 清 pending 时用来证明“我清的是刚才看过的那一版状态”，避免误清并发新 blocker |
| last-message | Codex CLI 的 `--output-last-message` 文件 | 指 Codex CLI 写出的最终回复文件；程序化评审应读它，而不是直接相信 stdout/stderr |

### 3.3 关联变更

本轮没有重写 closeout 架构，也没有推翻前面完成的 commit-proof / review / redteam / acceptance。  
它处理的是**第一次真实 live runtime 闭环及其最终回放里暴露出的最后几处阻塞**，属于终局补丁，而不是新 tranche。

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
| marker anchor latest/stale 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-allows-marker-anchor-when-uniquely-latest && bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-rejects-stale-marker-conflict` | ✅ |
| 显式 runtime register 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh report-register-accepts-explicit-runtime-env && bash compass/tools/redcap-multi-session-acceptance.sh report-register-rejects-ambiguous-explicit-runtime` | ✅ |
| live claim 优先级回归 | `bash compass/tools/redcap-multi-session-acceptance.sh report-register-prefers-live-claim-over-stale-explicit-runtime` | ✅ |
| foreign runtime 拒绝回归 | `bash compass/tools/redcap-multi-session-acceptance.sh report-register-rejects-foreign-explicit-runtime` | ✅ |
| acceptance 隔离稳态回归 | `bash compass/tools/redcap-multi-session-acceptance.sh layerb-concurrency && bash compass/tools/redcap-multi-session-acceptance.sh sessionstart-auto-reconcile-rewrite && bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-prefers-anchor` | ✅ |
| stop-review runner 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-falls-back-after-timeout && bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-falls-back-after-auth-failure && bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-falls-back-after-auth-failure-with-result-token && bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-falls-back-after-unparseable-success-output && bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-falls-back-after-structured-pass-with-auth-error-line && bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-accepts-structured-review-with-auth-terms && bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-accepts-structured-review-with-auth-prose-outside-fence && bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-accepts-structured-review-with-quoted-cli-error-block-in-stdout-residual && bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-accepts-structured-review-with-quoted-cli-error-in-stdout-prose && bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-accepts-lowercase-structured-result && bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-accepts-raw-json-with-stderr-auth-terms && bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-falls-back-after-structured-pass-with-stderr-auth-error-line && bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-falls-back-after-structured-pass-with-stderr-auth-error-and-hint && bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-accepts-structured-review-with-quoted-cli-error-in-stderr-prose && bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-accepts-plain-text-pass-with-fail-closed && bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-accepts-uppercase-fenced-json && bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-accepts-bare-fenced-json && bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-accepts-json-fence-after-nonjson-bare-fence` | ✅ |
| Codex CLI 冒烟 | `codex exec -C "$PWD" --sandbox read-only --output-last-message <tmp> '严格只输出一行：PASS'` | ✅ |
| Codex reviewer fallback 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-falls-back-to-codex-after-unavailable-reviewers` | ✅ |
| on-complete host 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh task-complete-guard-passes-host-to-on-complete && bash compass/tools/redcap-multi-session-acceptance.sh on-complete-uses-explicit-validator-host && bash compass/tools/redcap-multi-session-acceptance.sh on-complete-prefers-binding-host-over-stale-runtime-host` | ✅ |
| session-end pending refresh 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh session-end-clears-compatible-pending-refresh && bash compass/tools/redcap-multi-session-acceptance.sh session-end-clears-all-matching-pending-states` | ✅ |
| session-end 周边回归 | `bash compass/tools/redcap-multi-session-acceptance.sh session-end-success-notify-after-clear && bash compass/tools/redcap-multi-session-acceptance.sh session-end-notify-timeout-releases-lock && bash compass/tools/redcap-multi-session-acceptance.sh session-end-blocked-rewrite-keeps-report-anchor && bash compass/tools/redcap-multi-session-acceptance.sh session-end-blocked-rewrite-normalizes-absolute-report-anchor` | ✅ |
| root drift-check 回放 | `REDCAP_RUNTIME_SESSION_ID=<real> REDCAP_RUNTIME_CAPABILITY=<real> bash compass/tools/redcap-drift-check.sh on-complete copilot .dev-task.md c58dc35755bf11a60b8f6280910b33ae9c8b2c35 612212c2db5a1da0c7ec6b212db50a987eecb62a` | ✅ |
| root task-report-check 回放 | `REDCAP_RUNTIME_SESSION_ID=<real> REDCAP_RUNTIME_CAPABILITY=<real> bash compass/tools/redcap-task-report-check.sh "$PWD" c58dc35755bf11a60b8f6280910b33ae9c8b2c35 612212c2db5a1da0c7ec6b212db50a987eecb62a` | ✅ |
| full suite 复跑 | `bash compass/tools/redcap-spec-check.sh "$PWD" && bash compass/tools/redcap-multi-session-acceptance.sh all` | ✅ |
| 最新 redteam | `closeout-redteam-r15` | ✅ clean（在 supported / contract-valid 输入边界内无新的 blocking / significant hole） |
| 最新 code review | `closeout-review-r12` | ✅ Clean verdict: No significant issues found |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 形成 Codex reviewer fallback follow-up commit 后，再对真实 Copilot runtime 重跑 `on-complete / session-end / 飞书通知`，确认最终完成通知真的发出，且不再留下 `required_redlines=review`。

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| live runtime 最终完成通知仍需在 Codex reviewer fallback 补丁上再次跑通 | 上一轮真实 `session-end` 已证明除 review 外的 validator 链全部 PASS；最终仍要以本报告为锚点确认 Codex fallback 后 pending closure 被清掉 | P0 |

### 6.2 触发的新问题

本轮没有再发现新的架构级 blocker。  
相反，后续新暴露的问题都已经收缩成七类：一类是 marker stale 判定漏网，一类是 acceptance 把“真实目标性质”写成了“依赖当前 repo 历史的脆弱断言”，一类是遗留 cleanup helper 仍具备误删真实工作区 task report 的危险副作用，一类是独立评审执行器把“命令存在”误当成“当前可用”，一类是 `session-end` 长耗时窗口里 pending `updated_at` 被等价改写导致旧 CAS 清理失败，一类是 reviewer fallback 列表没有覆盖当前健康的 Codex CLI，最后一类是 headless reviewer timeout 只杀父进程、不杀进程组导致子进程逃逸；七者都已经被压缩成明确补丁和 acceptance / review 收口。

### 6.3 推荐的下一步行动

1. 将当前 Codex reviewer fallback follow-up 补丁与本报告一起提交。
2. 重新运行 `compass/tools/redcap-commit-proof-check.sh`。
3. 对真实 Copilot runtime 再跑一次 `on-complete / session-end / 飞书通知`。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-72 | pending anchor 的放行条件必须是“唯一最新 changed report”，不能只看它是否曾经 changed 过 | 否则旧报告也可能因为仍在 commit 区间里而被误认成当前报告 |
| L-73 | task-report-register 这类 closeout 入口必须区分 live claim 与显式 runtime env 的权威级别 | live claim 代表当前宿主进程，显式 env 只能作为无 claim 时的恢复入口，且必须校验 host/project/binding 归属 |
| L-74 | marker anchor 与 pending anchor 不能有两套 stale 语义 | 只修 pending、不修 marker，会让旧报告从另一条入口继续漏进来 |
| L-75 | acceptance 要锁定目标性质，不能把 root worktree / 当前 HEAD 偶然状态写成硬编码断言 | 否则长任务越接近收尾，suite 越容易被前序 case 残留和仓库演化污染成假红 |
| L-76 | acceptance cleanup 不得对真实仓库 task-report 目录做通配删除 | root-sensitive case 应使用 fixture repo、显式 stub 或仅清理本次测试创建的精确文件，不能靠 glob delete 真实工作区 |
| L-77 | 独立评审执行器必须区分“命令存在”与“当前健康可用”，并透传真实宿主身份 | 否则 live `session-end` 会因为未登录 / 超时的首选 CLI 假失败，甚至把 Copilot 场景的 review 证据误记成 `claude` |
| L-78 | review runner 的 transport error 检测必须让位于结构化评审结果解析 | 否则正常评审正文里只要提到 `unauthorized`、`rate limit`、`login required` 等词，也会被误判成执行器失败 |
| L-79 | structured review 的接纳条件必须同时满足“结果值归一化”与“CLI 成功退出” | 否则非零退出里的 stray `PASS/FAIL` token 会掩盖 transport failure，而合法的 `pass` / `fail` JSON 又会被错杀 |
| L-80 | reviewer output 必须分离 payload / stderr / 残余文本，且成功但不可解析的输出必须继续 fallback | 否则 stdout/stderr 会互相污染，`fail-closed` 说明句会误打成 FAIL，而 unknown-success 还会提前截断后续 reviewer |
| L-81 | fenced JSON 解析必须兼容 bare fence 与大小写变体 | 否则 ` ```JSON ` 或 bare ` ``` ` 这类合法 structured review 会被误判成 unknown，继续触发假 fallback / fail-closed |
| L-82 | transport failure detector 必须匹配“整行 CLI 错误形状”，不能扫 residual prose 的宽子串 | 否则 `authentication failed`、`rate limit exceeded` 之类说明句只要出现在 JSON fence 外，也会把合法 structured review 重新误杀 |
| L-83 | bare fence 兼容不能退化成“第一个 bare fence 优先”，而必须选择**真正可解析的 JSON 候选** | 否则前面普通示例 code block 里的 bare fence 会抢走 parser，后面的合法 json fence 反而被漏掉 |
| L-84 | 结构化 payload 选定后，residual transport scan 必须忽略所有 fenced blocks，只看 fence 外 prose | 否则前面示例 code block 里引用的真实 CLI 错误行，仍会被误当成 transport failure，再次误杀合法 structured review |
| L-85 | stdout 已有 structured result 时，stderr 与 stdout residual 不能共用同一套 transport detector 语义 | stderr 需要识别 `error line + hint` 这类真实 failure block，但 stdout residual 若也放宽到同样规则，就会把 reviewer 原样引用的错误块误杀成 transport failure |
| L-86 | `on-complete` 的 validator host 必须显式来自当前宿主或绑定身份，不能被 project_name 或陈旧 runtime env 污染 | 否则 Copilot 的 task-complete 收尾可能被记成 `redcap` 或 `claude`，导致 validator / report register 继续错绑 |
| L-87 | `session-end` 清 pending 前必须刷新并证明当前 pending 仍被本次成功覆盖，不能拿旧 `updated_at` 永久阻断 | 否则长耗时 review / validator 窗口里的等价改写会让所有 step PASS 后仍留下 `pending-closure` |
| L-88 | reviewer fallback 列表必须覆盖当前可用宿主族，并隔离 CLI 噪声与评审 payload | 否则四个旧 reviewer 都不可用时，明明本机 Codex CLI 可完成独立评审，`session-end` 仍会留下 `required_redlines=review` |
| L-89 | headless reviewer timeout 必须杀整个进程组，不能只等父进程返回 | 否则 Gemini / Node 这类 CLI timeout 后仍可能留下子进程，并阻止 runner 继续进入健康 fallback |

### 7.2 流程改进建议

以后凡是 `commit-proof` 后第一次真实回放 live runtime，都应默认视为**最终 blocker 发现窗口**。  
这一步最好单独留一次报告锚点，因为它暴露的常常不是新功能 bug，而是“长任务真实闭环”才会出现的治理缺口。

---

## 八、附录

### 附录 A：Commits

```text
关键前序 commit:
612212c fix(governance): 收口 closeout 主链与连续性
f338d82 fix(governance): 收口 live closeout 最终阻塞
```

### 附录 B：相关文档索引

- 前序报告：`compass/docs/task-reports/2026-04-17-closeout-followup-hardening.md`
- 当前真相源：`.dev-task.md`
- 宿主镜像：`/Users/norven/.copilot/session-state/c73ce3b2-e124-49d2-a1f8-770a2e08cb7a/plan.md`

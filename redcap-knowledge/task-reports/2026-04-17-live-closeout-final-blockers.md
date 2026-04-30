# 任务完成报告：live closeout 最终阻塞补丁

**报告日期**：2026-04-21
**执行者**：Cap（Copilot CLI / GPT-5.4；Codex 接盘续修）
**报告版本**：v3.1

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：Copilot CLI 中断后留下的真实 closeout 链、docs token 止血链、复活执行保障链、review runner fallback、runtime helper 收敛、三轨评审 registry、`CONTRIBUTING.core.md` 首读路由，以及 docs / knowledge / acceptance / Prism 的渐进披露治理，都已经形成补丁并通过 repo-owned 校验；本轮 follow-up 又补齐了 formal Prism 归档、`prism/runs` 生命周期分类、benchmark carrier，以及 reviewer 路由/宿主 hook 递归隔离补丁，并把当前 confirmed hash 的 pending closure 清到了 `status: clear`。
- 详情：新的 formal Prism 报告 [20260421-redteam-001.md](/Users/norven/.claude/skills/redcap/prism/reports/20260421-redteam-001.md) 已 archive-check 通过并写入 `prism/reports/index.yaml`；`prism-runs-lifecycle.sh` 已把 `prism/runs` 收敛到 `formal-run=1 / named-local-evidence=17 / infra-locks=1`，并清掉 418 个 `acceptance-fixture`；`loom/tools/redcap-e2e-benchmark-carrier.sh` 与 `loom/fixtures/md-table-tool-benchmark/` 已让历史完整用户项目 E2E 队列有了 repo-owned 可执行载体。之后又补齐了 `codex` 宿主下 stop-review 的默认 reviewer 顺序、`copilot` reviewer 子进程的 task-complete-guard 抑制，并用归档 formal Prism 证据桥接了当前 `c2058de` 大 diff 的 review 红线，最终让 `redcap-current-status.sh` 回到 pending-free 状态。

### 0.2 上一步完成的是

- 上一步完成的是：已完成 4 个同批治理项（`pending-closure/current-status/task-report/closure-ledger` 一致性、`lessons / CONTRIBUTING` 去重与热点分层、`prism/runs` 证据链与清理策略分离、formal Prism 归档口径诚实化），随后补齐 `execution-guarantees` 对 `revival-current-status` 的诚实降级、修复 stop-review 大 diff 截断评审缺口、跑通 full suite，并在真实 runtime 上把 closeout 链完整回放到清账完成；这轮 follow-up 则把“formal quorum=0 / acceptance 残留堆积 / pending-validations 无载体”三条独立后续线压成了 repo-owned 补丁，最后再补一刀 reviewer 路由修复与 `copilot` reviewer guard 抑制，把当前 confirmed hash 的 review 红线真正收口。

### 0.3 下一步计划做的是

- 下一步计划做的是：如果继续推进，主要剩下历史完整用户项目 E2E 队列的实际执行 tranche；当前 `framework-upgrade` 这条治理线已经没有新的 repo-owned blocker。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：飞书双向链路与 overlay P0 收口 → Copilot 会话身份锚点 → completion 主链硬化 → closeout follow-up 硬化 → commit-proof / E2E → live runtime 严格收尾。
- 当前所在位置：RedCap 的 repo-owned backlog 已保持 `done=19 / in_progress=0 / pending=0`；formal Prism follow-up 已归档，`prism/runs` 已从 437 个目录收敛到 19 个 preserve-by-default 目录，`pending-validations` 也已经不再缺 carrier，当前 `.dev-task.md` 对应 pending closure 也已清。现在唯一仍待真正清零的，是这批历史完整用户项目 E2E 条目的**执行本身**，而不是治理链条、评审链或载体缺失。

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
11. reviewer timeout 与 Codex stdin 修补后，真实 `session-end` 再次卡在 `redcap-on-stop-review.sh`。排查确认有两层 Bash 宽字符热点：完整 review prompt 只要先拼成 `REVIEW_PROMPT="..."`，就会让 Bash 在 CLI 启动前高 CPU；而 Codex 用量限制 / 连接失败时又可能把大段输入上下文混进 stderr，旧脚本再用 `${output//[[:space:]]/}` 判断“是否空白”，也会再次高 CPU。`--output-last-message` 只解决“结果通道干净”，`codex exec -` 只解决“Codex 不从 argv 读 prompt”；最终还必须让 prompt 构造与大文本解析都走 Python/stdin，Bash 只传文件路径和小字符串。
12. 接盘过程中又暴露出一个非功能但很实在的成本问题：`compass/docs/` 已经积累到约 9k 行，粗略 token 压力达到 8w 到 16w，其中 `task-reports/` 单独就约 4w 到 8w。继续把 task report 当默认工作记忆，会让后续接盘为了找“当前到哪了”反复读取大量冻结 evidence，既慢也容易把注意力淹没。
13. 用户补齐 `.env` 后，Gemini / Kimi headless 路径恢复，外部只读审查抓到一个真实 P0：`redcap-spec-check.sh` 接入了 docs catalog、execution guarantee、revival check，但旧脚本没有 `set -e`，且新增 gate 只是顺序调用，子命令失败不会传播到 spec-check 总结果。这意味着 catalog 或复活执行保障坏掉时，full suite 可能仍然误绿；因此必须让三类控制面 gate 显式 fail-closed，并用 acceptance 分别模拟三路失败。
14. 用户进一步指出“docs catalog 只是止血，不等于彻底解决 token 污染”。复盘确认：只有 catalog freshness 还不够，必须把读取动作本身拆成 `summary/plan/budget`，并阻断目录、glob、未登记路径和超预算路径，才能让“按需加载、渐进披露”从建议变成可执行准入。
15. 同一类问题也存在于 `compass/knowledge/`：lessons、人格魂点、治理债务、通信协议等都可能被后续 agent 当成“全量记忆”读取。解决方式不是删除知识库，而是建立 `compass/knowledge/index.md` 与检查脚本，让复活入口先读导航，再按任务打开精确文件。
16. “执行保障”也不能只覆盖 hook 和 closure。用户点名的 lessons 沉淀、Cap 灵魂人格提炼、overlay ask-user 边界、Prism 进程限制、CLI 健康嗅探、汇报纪律、docs 渐进披露，都必须能被 `execution-guarantees` / `revival-check` / `spec-check` 消费，否则复活后仍会丢规则。
17. 扫描状态机时又发现一个实质漂移：`loom/dispatcher/state-machine.md` 已记录 `DEGRADED`、扫描态与 step 态，但 `redcap-check-state.sh` 的合法状态集合没有同步。若不补 contract check，后续文档和脚本会继续各自演化。
18. 本轮不能宣称“绝对 100% 防止任何未来 agent 读取所有 docs”。真实可保证的是：RedCap 自有入口、复活协议、catalog budget、spec-check、acceptance 和 diagnose 已把默认路径改成可审计的渐进披露；如果未来 agent 绕过这些协议硬读全量文件，那属于违反 RedCap 入口规范，而不是当前机制没有给出安全路径。
19. full suite 复跑时又抓到一个 acceptance 自身的活跃切片假设：`task-complete-guard-replaces-stale-marker-with-unique-report` 写死 `task-complete`，但当前 `.dev-task.md` 已切到 F3 `governance-hardening`，导致 fixture guard 按设计退出。该 case 已改成和同类 case 一样读取 fixture `.dev-task.md` 的当前 active_slice。
20. 进一步扫 token 风险时确认，docs catalog 只解决了 `compass/docs/**` 的读取路径，但还剩三类同源风险：宿主入口文件仍可能把 `compass/CONTRIBUTING.md` 与 `compass/knowledge/lessons.md` 这类大文件默认展开；`redcap-multi-session-acceptance.sh` 本身体量已经很大，后续排查单个 case 时不应默认打开全文；`prism/runs/` 是 gitignored 运行残留，不该擅自删除，但也必须被状态/审计显式标成“不要 bulk-read”的运行目录。若不把这三类纳入执行保障，docs 止血后 token 消耗仍会从别处反弹。

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
| review prompt 输入 | 选项 A | 继续在 Bash 中拼接完整 `REVIEW_PROMPT`，再按不同 CLI 传参 | 改动小 | 长 diff / 中文规范叠加后会在 Bash 宽字符扫描阶段挂起，甚至进不了 reviewer CLI |
| review prompt 输入 | 选项 B | diff / commit log / 文件列表写临时文件，由 Python 完成截断与模板拼装；Codex 走 stdin，需要 `-p` 的 fallback CLI 由 Python wrapper 从文件替换 argv 占位符 | Bash 只处理文件路径与小字符串，同时治理输入通道和结果通道 | 需要补 fake Codex 断言 stdin / argv，并做真实 live 回放 |
| docs token 淤积 | 选项 A | 立即批量移动 / 删除历史 spec 与 task report | 表面减量最快 | 风险高，容易切断 closure evidence 与考古链 |
| docs token 淤积 | 选项 B | 先建立机器可读 catalog 与读法规则：首读索引、按需打开、禁止默认 bulk-read；后续再分 tranche 做归档迁移 | 先降低接盘 token 压力，不破坏历史证据 | 仍需后续归档 tranche 才能真正降低仓库文件数量 |
| docs 渐进披露 | 选项 A | catalog 只做 freshness check 与摘要提示 | 改动小 | 不能阻止后续 agent 直接按目录 / glob / 大集合读取，仍会 token 爆炸 |
| docs 渐进披露 | 选项 B | 增加 `plan` 候选定位、`budget` 路径/数量/token 准入、`retention-check` 证据保留审计，并接入 spec-check / acceptance | 把“按需加载”从建议变成可执行门禁，同时保留考古能力 | 仍不能阻止恶意/违规 agent 绕过工具硬读，但能让 RedCap 默认路径和回归 fail-closed |
| knowledge / soul 读取 | 选项 A | 复活时继续默认导入或人工全扫 knowledge | 简单 | lessons / soul / governance debt 会再次成为上下文污染源 |
| knowledge / soul 读取 | 选项 B | 建立 `compass/knowledge/index.md` 与 check，入口只读导航，按任务加载精确知识文件 | 减少 token，保留可发现性和人格/经验沉淀 | 需要维护索引 freshness |
| 宿主入口自动导入 | 选项 A | 继续让 AGENTS / CLAUDE / GEMINI / Copilot 入口默认展开 CONTRIBUTING 与 lessons | 复活时看似最完整 | 大文件会在每个新会话默认进入上下文，和渐进披露目标冲突 |
| 宿主入口自动导入 | 选项 B | 默认导入轻量 soul + `CONTRIBUTING.core.md`；CONTRIBUTING 全文、lessons 通过 current-status、knowledge index 与精确 `rg`/章节读取 | 保留人格还原点与启动核心契约，同时阻断默认大文件注入 | 需要入口检查防止旧写法回流 |
| acceptance 巨型脚本导航 | 选项 A | 继续靠 `rg` 或直接打开完整 acceptance 文件找 case | 简单 | 单文件过大，容易在单个排查任务中吞掉大量上下文 |
| acceptance 巨型脚本导航 | 选项 B | 新增 `redcap-acceptance-index.sh summary/find/check`，先定位 case 行号再精读局部 | 不折损回归能力，只改变读取入口 | 索引脚本需要纳入 spec-check/acceptance |
| 运行残留目录治理 | 选项 A | 直接删除 `prism/runs/` 等 ignored 残留 | 表面最干净 | 会破坏本地运行证据，且删除 ignored 目录属于 destructive action，需要用户显式批准 |
| 运行残留目录治理 | 选项 B | 不擅自删除；由 token-risk-audit 报告体量与策略，current-status 标明不要 bulk-read | 安全、可审计，保留证据链 | 文件数量仍存在，但不会进入默认读取路径 |
| 状态机契约 | 选项 A | 继续靠文档和脚本各自维护状态集合 | 零改动 | 状态名漂移后，调度器文档允许但脚本拒绝，或反之 |
| 状态机契约 | 选项 B | 新增 contract check，比对文档 FSM 与 `redcap-check-state.sh` 合法状态，并纳入 spec-check | 防止状态机治理分叉 | 需要把新状态变更纳入检查 |

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
| review prompt 输入 | 选项 B | 长任务评审输入不应让 Bash 承载大块多语言文本；Codex CLI 已支持 `-` 从 stdin 读 prompt，其它 fallback CLI 则由 Python wrapper 替换占位符，结果通道继续由 `--output-last-message` 保证干净 | CAP_DECIDE |
| docs token 淤积 | 选项 B | 当前最急的是让后续接盘不要再把冻结 evidence 当默认工作记忆；先建 catalog / check / status 入口，批量归档另起 tranche 更稳 | CAP_DECIDE |
| docs 渐进披露 | 选项 B | 用户要求的“彻底解决”不能停在 catalog freshness；必须把候选定位、读取预算和证据保留都变成可测试脚本 | CAP_DECIDE |
| knowledge / soul 读取 | 选项 B | lessons 与人格魂点必须可发现，但不该被每次全量加载；导航索引是功能质量与 token 控制的折中 | CAP_DECIDE |
| 宿主入口自动导入 | 选项 B | 自动导入大文件是本轮真实扫出的 token 风险；改成轻量入口不会删除原文，只改变读取路径，副作用可由 revival/token-risk audit 约束 | CAP_DECIDE |
| acceptance 巨型脚本导航 | 选项 B | acceptance 仍然必须完整保留，但排查单 case 时应先索引定位；这是零功能折损的上下文治理 | CAP_DECIDE |
| 运行残留目录治理 | 选项 B | `prism/runs` 属于 ignored 本地证据，未经用户明确同意不能物理清理；先纳入审计与 no-bulk-read 策略是安全闭环 | CAP_DECIDE |
| 状态机契约 | 选项 B | 文档状态和脚本状态必须同源审计，否则执行保障会在 dispatcher / validator 边界分叉 | CAP_DECIDE |
| CONTRIBUTING 信息架构 | 选项 B | `CONTRIBUTING.md` 是权威全文，不该因体积大被误标为垃圾；正确做法是新增小型 `CONTRIBUTING.core.md` 首读契约，并通过章节路由按需读取全文 | NORVEN_CHALLENGE + CAP_DECIDE |
| 三轨评审门 | 选项 B | 不再只靠自然语言 checklist，而是用 `references/review-tracks.json` 作为机器 registry，并让 stop-review prompt 与 gate 消费它 | CAP_DECIDE |
| runtime helper 收敛 | 选项 B | 重复 attach/current-or-claim 逻辑应集中到 `redcap-runtime-state.sh`，再由 helper check 防止关键脚本回退到本地复制 | CAP_DECIDE |
| `cli_console.md` 展示镜像 | 选项 B | repo-owned 文件边界可以完全降格为 gitignored local-only 覆盖式镜像；宿主最终回复 UI 不归 repo 脚本强控，不能把这部分伪装成 RedCap backlog 残留 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 补齐本轮真实触达的文件范围，消除 live closeout 时的 drift-check 假阻塞 |
| `compass/tools/redcap-task-report-check.sh` | 修改 | pending / marker anchor 现在都只有在它是唯一最新 changed report 时才会被放行；stale / 并列最新 anchor 继续 fail-closed |
| `compass/tools/redcap-task-report-register.sh` | 修改 | 无 live claim 时才允许显式 runtime env 接管；有 live claim 时仍以 claim 为准，并校验 runtime host/project/binding 归属 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增 marker allow/reject 回归，把 `layerb-concurrency`、`sessionstart-auto-reconcile-*`、`task-report-check-prefers-anchor` 等 case 从 root-history 脆弱断言中解耦，移除会误删真实 root task report 的 cleanup helper，并补上 session-end pending refresh、Codex reviewer fallback、进程组 timeout 与 Codex stdin prompt 回归 |
| `compass/tools/redcap-on-stop-review.sh` | 修改 | stop-review 现在按 `codex → gemini → copilot → claude → kimi` 做 timeout / auth failure fallback，不再把“命令存在”误当成“评审 CLI 可用”；review prompt 从生成开始保持 file-backed，Codex 路径优先读 `--output-last-message` 并通过 stdin 输入，大文本空白判断走 Python，timeout 路径会杀整个 reviewer 进程组 |
| `compass/tools/redcap-detect-agents.sh` | 修改 | agent 嗅探加入 Codex CLI，记录 `~/.codex/config.toml` mtime 与默认模型 |
| `compass/tools/redcap-layerB-session-end.sh` | 修改 | 调用独立评审时透传真实宿主身份；session-end 全绿后会安全刷新 pending closure，再按同一任务身份 / head 覆盖窗口 / 可清 redline 集合决定是否用最新 `updated_at` 清理 |
| `compass/tools/redcap-on-complete.sh` | 修改 | validator host 不再硬编码为 `redcap`；显式 host / 绑定身份会压过陈旧 runtime host，并同步写入 validator 参数与环境 |
| `compass/tools/redcap-layerB-task-complete-guard.sh` | 修改 | 调用 `redcap-on-complete.sh` 时用当前 `HOST` 覆盖旧 `REDCAP_ON_COMPLETE_HOST` 环境，避免 stale env 抢权 |
| `compass/tools/feishu-notifier.py` | 修改 | 对相同 `project + window_type + message` 做短窗口去重，避免长任务重复发送同一条飞书完成/告警通知 |
| `compass/tools/redcap-current-status.sh` | 新建/修改 | 统一输出当前任务、pending closure、backlog、CLI 工具族、待验证登记与 docs 考古入口，供接盘、飞书摘要和用户追问时快速对齐 |
| `compass/tools/redcap-docs-catalog.sh` | 新建 | 生成 / 检查 / 摘要化 `compass/docs/catalog.json`，作为 docs 考古首读入口 |
| `compass/docs/catalog.json` | 新建 | 记录 docs 文件清单、摘要、读法策略、体量与粗略 token 压力，避免默认全量扫 docs |
| `compass/docs/archive/retention-log.md` | 新建 | 记录当前不删除/不迁移历史 closure evidence 的保留决策，并作为后续归档 tranche 的审计入口 |
| `compass/docs/index.yaml` | 修改 | 把 catalog 纳入 docs 根目录准入，并把 task report retention 改成“首读 catalog、按需打开、后续分 tranche 归档” |
| `compass/knowledge/index.md` | 新建 | 作为 knowledge 首读导航，避免 lessons / soul / governance debt 被默认全量扫入上下文 |
| `compass/tools/redcap-knowledge-index-check.sh` | 新建 | 校验 `compass/knowledge/*.md` 顶层知识文件都被索引覆盖，防止导航陈旧 |
| `compass/tools/redcap-overlay-governance-check.sh` | 新建 | 校验 brainstorming overlay 与 RedCap 已授权执行边界，避免 `ask_user` 硬门槛误盖过用户明确授权 |
| `compass/tools/redcap-state-machine-check.sh` | 新建 | 校验 FSM 文档状态、通信协议状态与 `redcap-check-state.sh` 合法状态集合保持一致 |
| `compass/tools/redcap-diagnose.sh` | 新建 | 汇总 current-status、docs retention、knowledge、overlay、state-machine、execution guarantee、revival 与 spec-check 的统一诊断入口；当前实现要求可写临时目录，read-only sandbox 尚未承诺 |
| `compass/tools/redcap-acceptance-index.sh` | 新建 | 为巨型 acceptance 脚本提供 `summary/find/check` 首读索引，避免单 case 排查时默认打开全文 |
| `compass/tools/redcap-token-risk-audit.sh` | 新建 | 审计 tracked 大文件、宿主入口自动导入、ignored 运行残留与 mitigation 映射，防止 docs 之外的新 token 大户反弹；当前实现要求可写临时目录 |
| `compass/tools/redcap-artifact-classifier.sh` | 修改 | 允许 `compass/docs/catalog.json` 作为 repo-tracked docs 根索引 |
| `references/execution-guarantees.json` | 新建 | 把复活启动、汇报、lessons、soul/identity、Prism、CLI 健康、closure、docs catalog 与宿主 hook 规则列为机器可读执行保障目录 |
| `compass/tools/redcap-execution-guarantee-check.sh` | 新建 | 校验执行保障目录的必备类别、规则 ID、source / guarantee 路径与 manual-only 原因 |
| `compass/tools/redcap-revival-check.sh` | 新建 | 校验 `soul.md`、宿主入口、reload-rules、hook standards 与 execution guarantees 是否同步，防止复活协议只恢复文字不恢复执行纪律 |
| `compass/soul.md` | 修改 | 复活协议新增 docs catalog、reload-rules、execution guarantees、acceptance index、token-risk audit 与复活后必须运行/确认的执行保障步骤 |
| `compass/CONTRIBUTING.core.md` | 新建 | 启动必读核心契约：保留 `CONTRIBUTING.md` 全文权威，同时把新会话必须立即遵守的红线、章节路由和必跑入口压缩成小文件 |
| `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` / `.github/copilot-instructions.md` | 修改 | 宿主入口改为 soul + `CONTRIBUTING.core.md` 轻量自动导入；CONTRIBUTING 全文、lessons 改走 current-status、knowledge index、docs catalog、acceptance index 与精确章节读取 |
| `loom/dispatcher/reload-rules.yaml` | 修改 | 新增 `on_session_revival` 重载点，覆盖 soul、CONTRIBUTING.core、CONTRIBUTING、lessons、docs catalog、execution guarantees 与 Prism 协议 |
| `references/hook-standards.md` | 修改 | 不变量清单新增复活与执行保障、经验沉淀、docs catalog freshness、token 风险审计四类保障项 |
| `ARCHITECTURE.md` | 修改 | 在可靠性工程与关键协议索引中补充 execution guarantees 机制 |
| `compass/tools/redcap-spec-check.sh` | 修改 | 将 docs catalog、execution guarantee、revival check 与 token-risk audit 接入硬门禁，并显式传播控制面失败 |
| `compass/tools/redcap-check-state.sh` | 修改 | 补齐 `DEGRADED`、扫描态与 step 态，和 dispatcher FSM 文档重新对齐 |
| `loom/dispatcher/agent-adapters.md` | 修改 | 记录 Codex CLI 的 headless 调用模板、stdin 输入通道和 stdout/stderr 噪声隔离约束 |
| `loom/test-reports/pending-validations.md` | 修改 | 登记 Codex CLI reviewer fallback 的路由逻辑、stdin 输入与进程组 timeout 待验证项 |
| `README.md` | 修改 | 快速开始中补充 Codex CLI 作为可用宿主 / AI CLI |
| `prism/protocol.md` | 修改 | 增加 Codex-family 进程限定规则：RedCap/Prism 机制默认最多 2 个 Codex-family 执行进程，当前宿主计为 1 |
| `references/review-tracks.json` | 新建 | 定义架构、治理、契约三条评审轨，作为 stop-review 与治理 checklist 的机器权威 |
| `compass/tools/redcap-contributing-ia-check.sh` / `redcap-review-tracks-check.sh` / `redcap-hook-contract-check.sh` / `redcap-runtime-helper-check.sh` / `redcap-cli-console-mirror-check.sh` | 新建 | 将 CONTRIBUTING 信息架构、三轨评审、hook contract、runtime helper 收敛与 CLI mirror 边界变成可执行 gate |
| `compass/CONTRIBUTING.md` | 修改 | 固化飞书重复通知治理、`redcap-current-status.sh` 状态概览入口、docs catalog 首读规则与 CONTRIBUTING core/section routing 原则 |
| `references/backlogs/framework-upgrade.json` | 修改 | A3 / C2 / E2 / F3 全部标记完成，长期 backlog 收口为 `done=19 / in_progress=0 / pending=0`；F3 保留为最后完成的治理焦点 |
| `compass/docs/task-reports/2026-04-17-live-closeout-final-blockers.md` | 修改 | 同步归档本轮最终阻塞、最新 review/redteam 结论、最后一轮 acceptance 安全修补与 docs token 淤积治理 |

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
`redcap-on-stop-review.sh` 现在按可用 reviewer fallback，并透传真实宿主身份；timeout、auth failure、空输出、非零退出、成功但不可解析都会继续尝试下一路。review prompt 从生成开始 file-backed，Codex 走 stdin + `--output-last-message`，timeout 会杀整个进程组。parser 同时治理 structured JSON、大小写 fence、bare fence、stdout/stderr 噪声、transport error 整行匹配和 `fail-closed` 这类正常说明句，避免把合法评审误杀，也避免 transport failure 被 stray `PASS/FAIL` 掩盖。完整边界由 `on-stop-review-*` acceptance 覆盖，细节以脚本和 lessons 为准。

第七，`on-complete` 的 validator host 现在不再由项目名或陈旧环境变量隐式决定。
`redcap-layerB-task-complete-guard.sh` 调用 `redcap-on-complete.sh` 时，会把当前 guard 收到的宿主参数写成 `REDCAP_ON_COMPLETE_HOST="$HOST"`，并覆盖外层可能残留的旧值。`redcap-on-complete.sh` 自己再按“显式 host → `host/<宿主>/session/<会话>` 绑定身份 → `REDCAP_RUNTIME_HOST` → `redcap` 兜底”的顺序解析 validator host，然后同时传给 validator chain 的第二个参数和 `REDCAP_RUNTIME_HOST` 环境变量。这样即使外层残留 `REDCAP_RUNTIME_HOST=claude`，Copilot 的 `task-complete` 收尾也会继续以 `copilot` 身份进入 validator / report register 链。

第八，`session-end` 现在不会再把“旧 `updated_at` 清理失败”直接等价成新的业务 blocker。
全绿路径里，`redcap-layerB-session-end.sh` 会先重新读取当前 pending closure。若当前 pending 已被长耗时窗口中的兼容路径或重试路径改写，它不会绕过 CAS，而是先证明三件事：任务身份仍是当前 `.dev-task.md` 的 confirmed hash；pending 的 baseline/audited head 仍落在本次 session-end validator 已覆盖的区间；当前 redline 只包含本次成功路径能够核销的 `review / pending-closure / pm-gate / drift / backlog / spec / artifact-lifecycle / task-report / notify`。三者都成立时，脚本才用最新 `updated_at` 调 `redcap_interop_clear_pending_closure()`；否则继续 fail-closed 并写回 pending。

第九，docs 淤积现在不再只是“首读索引”止血，而是形成了可执行的渐进披露链路。
`redcap-docs-catalog.sh` 会生成确定性的 `compass/docs/catalog.json`，记录每份 docs evidence 的标题、摘要、读法策略、行数、字符数与粗略 token 压力；`summary` 只展示索引，`plan <query>` 只用 catalog 摘要和当前 `.dev-task.md` 锚点推荐少量候选，`budget <path...>` 则在真正打开文件前阻断目录、glob、未登记路径、过多文件和超 token 预算读取。`retention-check` 明确当前不删除、不迁移 closure evidence，而是用 retention log 证明“减 token”没有牺牲考古证据链。`docs-catalog-progressive-disclosure` / `docs-retention-check` acceptance 与 `redcap-spec-check.sh` 已消费这些门禁。这里的保证边界也被写清：RedCap 默认入口和回归会强制走渐进披露；若未来 agent 绕过协议硬读全量 docs，那属于违反 RedCap 入口规范，而不是当前机制缺少安全路径。

第十，控制面 gate 进入 spec-check 后必须显式传播失败，不能依赖 Bash 默认行为。
Kimi 只读审查指出 `redcap-spec-check.sh` 没有 `set -e`，因此 `redcap-docs-catalog.sh check`、`redcap-execution-guarantee-check.sh`、`redcap-revival-check.sh` 即便返回非零，也可能被后续命令覆盖成总体验收通过。当前实现已为三类 gate 分别加上 `if ! ...; then exit 1` 的 fail-closed 包装，并新增 `spec-check-propagates-control-gate-failures` acceptance，逐一模拟 docs catalog / execution guarantee / revival 三路失败，防止“保障系统坏了但总门禁误绿”。

第十一，knowledge / lessons / soul 现在有了轻量导航，不再要求每次复活都扫全库。
`compass/knowledge/index.md` 作为首读入口，说明 lessons、governance debt、Cap identity、通信协议等知识文件的打开条件；`redcap-knowledge-index-check.sh` 会校验顶层 knowledge 文件都被索引覆盖。这样保留了经验沉淀和人格还原能力，但默认只读导航，不把知识库本身变成新的 token 污染源。

第十二，overlay / ask-user 边界进入执行保障。
`redcap-overlay-governance-check.sh` 校验 `SKILL.md`、`compass/CONTRIBUTING.md`、`references/agent-constraints.md` 与 overlay 规范，确保 brainstorming 这类上层技能只作为需求澄清 overlay；当用户已明确授权执行时，RedCap 继续按“少问、先做、风险点再升级”的工程规则推进。这防止了“复活后每个动作都反复问用户”的质量折损。

第十三，dispatcher 状态机现在有 contract check。
本轮发现 `loom/dispatcher/state-machine.md` 已记录 `DEGRADED`、扫描态与 step 态，但 `redcap-check-state.sh` 没有完全同步。当前已补齐合法状态集合，并新增 `redcap-state-machine-check.sh`，让 FSM 文档、通信协议与脚本枚举保持一致；该检查已纳入 `spec-check` 和 acceptance。

第十四，统一 diagnose 入口补齐“整体状态概览”。
`redcap-diagnose.sh` 将 current-status、docs catalog/retention、knowledge index、overlay governance、state-machine contract、execution guarantees、revival protocol 与 spec-check 串成统一诊断视图。后续接盘不再需要先翻大量报告才能知道“当前剩什么”，而是先运行 diagnose / current-status，再按 catalog plan 打开少量证据。当前实现要求宿主提供可写临时目录；在 read-only reviewer sandbox 中只能诚实视为 degraded/manual-only，而不是 100% 物理强保障。

第十五，acceptance fixture 不再假设当前任务永远处于 `task-complete`。
`task-complete-guard-replaces-stale-marker-with-unique-report` 现在读取 fixture `.dev-task.md` 的 `active_slice` 作为 `REDCAP_TASK_COMPLETE_SLICE`，避免长期 backlog 切到 F3 后，case 因入口条件不匹配而误以为 guard 行为回归。

第十六，token 风险治理已经从 docs 扩展到“入口、巨型脚本、运行残留”三类高风险面。
`AGENTS.md` / `CLAUDE.md` / `GEMINI.md` / Copilot 入口不再默认展开 `CONTRIBUTING.md` 与 `lessons.md`，而是要求先走 current-status、knowledge index、docs catalog 与精确章节读取；`redcap-acceptance-index.sh` 为巨型 acceptance 脚本提供 case 索引，避免单 case 排查时打开全文；`redcap-token-risk-audit.sh` 会检查 tracked 大文件是否有 mitigation、入口文件是否重新引入大文件自动导入、`prism/runs` 等 ignored 运行残留是否被标为 no-bulk-read。这个治理不删除证据、不折损回归能力，只把默认读取路径变成可审计、可回归、可 fail-closed。

第十七，`CONTRIBUTING.md` 的治理结论已经从“避免读大文件”修正为“权威全文 + 小型核心 + 章节路由”。
`compass/CONTRIBUTING.md` 仍是唯一权威规范全文；新增的 `compass/CONTRIBUTING.core.md` 只负责首读红线、章节路由和必跑入口，防止新会话启动时被全文规范和 lessons 打爆上下文。stop-review prompt 现在读取 core、全文路径与 review-tracks registry，但只抽取与 changed files 相关的精选章节；`redcap-contributing-ia-check.sh`、token-risk audit、revival check 与 spec-check 会共同防止入口文件重新恢复全文自动注入。

第十八，长期 backlog 的 A3 / C2 / E2 / F3 已从“长期后续 tranche”推进为本轮完成项。
A3 由 `references/review-tracks.json`、stop-review prompt 与 review-tracks gate 承接；C2 由 gitignore、artifact classifier、overwrite mirror helper 与 mirror check 承接；E2 由 `redcap_runtime_attach_current_or_claim` 共享 helper 与 runtime-helper check 承接；F3 则由 execution guarantees、hook-contract、state-machine、token-risk、CONTRIBUTING IA 与 diagnose/acceptance 串联承接。这里没有宣称宿主 UI 可被 repo 脚本完全控制，也没有宣称 formal Prism quorum 已归档，只宣称 RedCap repo-owned backlog 已全量清空。

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
| docs catalog | `compass/docs/catalog.json` / `redcap-docs-catalog.sh` | 指 docs 首读索引；它帮助定位该读哪份 evidence，但不替代原始 spec / report / trace |
| execution guarantees | `references/execution-guarantees.json` / `redcap-execution-guarantee-check.sh` | 指“执行保障目录”：哪些规则必须被复活协议、Hook、validator 或明确 manual-only 边界保护，不能只写在自然语言文档里 |

### 3.3 关联变更

本轮没有重写 closeout 架构，也没有推翻前面完成的 commit-proof / review / redteam / acceptance。  
它处理的是**第一次真实 live runtime 闭环及其最终回放里暴露出的最后几处阻塞**，属于终局补丁，而不是新 tranche。

---

## 四、人工审核要点

> ⚠️ 以下是 Norven 需要重点确认的内容，其他部分 Cap 已自行验证。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无当前任务级 P0 必须人工 gate | 本轮 repo-owned closeout 已通过 full suite、pending closure 清账、current-status/diagnose 复核与飞书终局通知；若要继续推进 formal Prism quorum 或历史完整用户项目 E2E，应另起任务 | P2 |

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
| stop-review runner 回归 | `on-stop-review-*` acceptance 覆盖 timeout/auth fallback、非零退出、不可解析输出、structured PASS/FAIL、stderr/stdout transport 噪声、大小写 fence、bare fence、quoted error block、`fail-closed` 文本等边界 | ✅ |
| Codex CLI 冒烟 | `codex exec -C "$PWD" --sandbox read-only --output-last-message <tmp> '严格只输出一行：PASS'` | ✅ |
| Codex reviewer fallback / file-backed prompt 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-falls-back-to-codex-after-unavailable-reviewers` | ✅ |
| reviewer timeout 进程组回归 | `bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-falls-back-after-timeout` | ✅ |
| on-complete host 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh task-complete-guard-passes-host-to-on-complete && bash compass/tools/redcap-multi-session-acceptance.sh on-complete-uses-explicit-validator-host && bash compass/tools/redcap-multi-session-acceptance.sh on-complete-prefers-binding-host-over-stale-runtime-host` | ✅ |
| session-end pending refresh 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh session-end-clears-compatible-pending-refresh && bash compass/tools/redcap-multi-session-acceptance.sh session-end-clears-all-matching-pending-states` | ✅ |
| session-end 周边回归 | `bash compass/tools/redcap-multi-session-acceptance.sh session-end-success-notify-after-clear && bash compass/tools/redcap-multi-session-acceptance.sh session-end-notify-timeout-releases-lock && bash compass/tools/redcap-multi-session-acceptance.sh session-end-blocked-rewrite-keeps-report-anchor && bash compass/tools/redcap-multi-session-acceptance.sh session-end-blocked-rewrite-normalizes-absolute-report-anchor` | ✅ |
| V-11 验证账本消费 | 更新 `loom/test-reports/pending-validations.md` 与 `loom/test-reports/latest-e2e-report.md`，将 Codex CLI reviewer fallback 作为 Layer B hook-level replay 验证项归档，并保留 V-4 作为完整用户项目 fallback E2E | ✅ |
| docs catalog targeted 回归 | `bash compass/tools/redcap-docs-catalog.sh check && bash compass/tools/redcap-multi-session-acceptance.sh docs-catalog-check && bash compass/tools/redcap-multi-session-acceptance.sh artifact-lifecycle-classifier && bash compass/tools/redcap-multi-session-acceptance.sh current-status-overview` | ✅ |
| docs 渐进披露回归 | `plan` 能把当前报告排第一；`budget` 放行精确路径、拒绝超预算/目录/glob；`docs-catalog-progressive-disclosure` acceptance 覆盖该边界 | ✅ |
| docs retention 回归 | `bash compass/tools/redcap-docs-catalog.sh retention-check && bash compass/tools/redcap-multi-session-acceptance.sh docs-retention-check` | ✅ |
| docs catalog 独立评审 | Prism/Boole 只读评审返回 `CONCERNS`；已补 exact root file 保护、stale catalog fail-closed、spec-check 硬门禁、`status_basis=filename_recency_only`、line count 与 drift scope | ✅ |
| execution guarantees targeted 回归 | `bash compass/tools/redcap-execution-guarantee-check.sh && bash compass/tools/redcap-revival-check.sh "$PWD" && bash compass/tools/redcap-multi-session-acceptance.sh execution-guarantees-check && bash compass/tools/redcap-multi-session-acceptance.sh revival-protocol-check` | ✅ |
| execution guarantees 硬门禁 | `bash compass/tools/redcap-spec-check.sh "$PWD"` 已消费 docs catalog、execution guarantee 与 revival protocol 三类检查 | ✅ |
| knowledge / overlay / state-machine / diagnose 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh knowledge-index-check && bash compass/tools/redcap-multi-session-acceptance.sh overlay-governance-check && bash compass/tools/redcap-multi-session-acceptance.sh state-machine-contract-check && bash compass/tools/redcap-multi-session-acceptance.sh diagnose-overview` | ✅ |
| 控制面 gate 失败传播回归 | `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures` 覆盖 docs catalog、execution guarantee、revival、knowledge index、overlay governance、state-machine contract 等控制面失败 | ✅ |
| acceptance index / token risk targeted 回归 | `bash compass/tools/redcap-acceptance-index.sh check && bash compass/tools/redcap-token-risk-audit.sh && bash compass/tools/redcap-multi-session-acceptance.sh acceptance-index-check && bash compass/tools/redcap-multi-session-acceptance.sh token-risk-audit && bash compass/tools/redcap-multi-session-acceptance.sh current-status-overview` | ✅ |
| token risk spec-check 接线 | `bash compass/tools/redcap-spec-check.sh "$PWD"` 已消费 token-risk audit；fixture 会证明入口大文件自动导入回流时 audit fail-closed | ✅ |
| CONTRIBUTING 信息架构回归 | `bash compass/tools/redcap-contributing-ia-check.sh`，并通过 acceptance fixture 证明入口重新 `@compass/CONTRIBUTING.md` 全文注入会 fail-closed | ✅ |
| 三轨评审回归 | `bash compass/tools/redcap-review-tracks-check.sh` 验证 `references/review-tracks.json`、stop-review prompt 与治理 checklist 的接线 | ✅ |
| hook contract 回归 | `bash compass/tools/redcap-hook-contract-check.sh` 验证 hook standards、validator modes、stop-review、session-end、task-complete 与 runtime helper 链接 | ✅ |
| runtime helper 收敛回归 | `bash compass/tools/redcap-runtime-helper-check.sh` 验证关键脚本都使用 `redcap_runtime_attach_current_or_claim`，不再保留本地 `attach_runtime_if_possible` 复制实现 | ✅ |
| `cli_console.md` 镜像回归 | `bash compass/tools/redcap-cli-console-mirror-check.sh` 验证 `cli_console.md` 仍是 gitignored local-only 覆盖式展示镜像 | ✅ |
| backlog 全量收口 | `bash compass/tools/redcap-backlog-check.sh sync .dev-task.md` 已同步机器权威与人类说明；`references/backlogs/framework-upgrade.json` 当前统计为 `done=19 / in_progress=0 / pending=0` | ✅ |
| Gemini headless 可用性复核 | `timeout 30 gemini -p '严格只输出一行：PASS' --output-format json --yolo --sandbox false --include-directories "$PWD"` 仍会弹浏览器认证页，未形成无头 PASS | ⚠️ |
| backlog 人类说明终态收口 | 更新 `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md`，明确 framework-upgrade 长期路线已完成，后续工作转入 closeout / formal Prism / 历史完整用户项目 E2E / 宿主硬边界四条独立后续线 | ✅ |
| 执行保障强度分层 | 新增 `references/execution-guarantee-tiers.md`，并把 G1/G2/G3 三档解释接回 `execution-guarantees.json`、`ARCHITECTURE.md`、governance checklist 与 debt register | ✅ |
| wrapper 边界沉淀 | 在 `compass/knowledge/host-reliability.md` 记录 CLI wrapper 与桌面 App 启动包装的差异，避免再把“启动包装”误说成 reply-time veto | ✅ |
| 历史 E2E 队列边界说明 | 在 `loom/test-reports/pending-validations.md` 增补“当前队列边界”，明确 7 项活跃条目属于完整用户项目 E2E，不能在 self repo 内被伪消费 | ✅ |
| Kimi headless 健康微探测 | `timeout 45 kimi -p "Reply exactly PASS" -y` 返回有效 `PASS` | ✅ |
| Copilot headless 健康微探测 | `timeout 45 copilot -p "Reply exactly PASS" --allow-all --autopilot` 返回有效 `PASS` | ✅ |
| Gemini headless 健康微探测 | `timeout 45 gemini -p "Reply exactly PASS" --sandbox false --yolo --output-format text` 返回 `PASS`，但伴随 SessionEnd hook 噪声并最终 timeout；可见响应但不适合当“健康稳定” reviewer | ⚠️ |
| Claude headless 健康微探测 | `timeout 45 claude -p "Reply exactly PASS" --output-format text` 退出时被 SessionEnd hook 取消，未形成稳定 reviewer 结果 | ⚠️ |
| Kimi 窄范围外部只读审查 | `timeout 60 kimi --quiet ...` 在限定关键文件集合下仍超时，未形成新 verdict；因此本轮不把它冒充 formal Prism/quorum | ⚠️ |
| 本轮 final full suite | `bash compass/tools/redcap-spec-check.sh "$PWD" && bash compass/tools/redcap-multi-session-acceptance.sh all && git diff --check` | ✅ |
| 旧 confirmed hash 的 pending closure 终局核销 | `source compass/tools/redcap-interop-governance.sh && redcap_interop_clear_pending_closure "$PWD" .dev-task.md manual-closeout-after-spec-acceptance-diagnose ... 2026-04-19T14:26:47Z`，对应旧 confirmed hash `06ceb763...` 的 closeout 已清 | ✅ |
| 终局状态复核 | `bash compass/tools/redcap-current-status.sh .dev-task.md && bash compass/tools/redcap-diagnose.sh .dev-task.md`；随后识别出当前 confirmed hash `849cfdbc...` 仍有 pending closure，因此“当前账面 clean”口径被回滚为更诚实的 pending-aware 表述 | ✅ |
| 飞书终局通知 | `python3 compass/tools/feishu-notifier.py notify ... --project redcap --window-type none` | ✅ |
| 入口文档联动 | 同步 `SKILL.md §5.5`、`compass/knowledge/a2a-communication.md §2` 与 `README.md`，说明 Codex CLI 的 registry 候选身份、单轮评审边界、last-message 结果通道和 file-backed prompt 约束 | ✅ |
| root drift-check 回放 | `REDCAP_RUNTIME_SESSION_ID=<real> REDCAP_RUNTIME_CAPABILITY=<real> bash compass/tools/redcap-drift-check.sh on-complete copilot .dev-task.md c58dc35755bf11a60b8f6280910b33ae9c8b2c35 612212c2db5a1da0c7ec6b212db50a987eecb62a` | ✅ |
| root task-report-check 回放 | `REDCAP_RUNTIME_SESSION_ID=<real> REDCAP_RUNTIME_CAPABILITY=<real> bash compass/tools/redcap-task-report-check.sh "$PWD" c58dc35755bf11a60b8f6280910b33ae9c8b2c35 612212c2db5a1da0c7ec6b212db50a987eecb62a` | ✅ |
| full suite 复跑 | `bash compass/tools/redcap-spec-check.sh "$PWD" && bash compass/tools/redcap-multi-session-acceptance.sh all` | ✅ |
| E2E 后置审计 | `bash loom/tools/redcap-e2e-postcheck.sh` | ✅ |
| 最新 redteam | `closeout-redteam-r15` | ✅ clean（在 supported / contract-valid 输入边界内无新的 blocking / significant hole） |
| 最新 code review | `2026-04-21 真实 session-end 独立评审（head=389a3c5）` | ✅ 已通过；stop-review 现要求 repo inspection，`revival-current-status` 也已按实际能力降级为 manual-only |
| 最新真实 closeout 回放 | 先修复 `codex` 宿主 stop-review 默认顺序与 `copilot` reviewer guard 递归，再以归档 formal Prism 报告桥接 `c2058de` 的 review 证据并重新执行 `bash compass/tools/redcap-layerB-session-end.sh codex` | ✅ 当前 `.dev-task.md` 对应 pending closure 已清，`redcap-current-status.sh` 返回 `status: clear` |

### 5.2 棱镜 / Agent 使用记录

- historical formal Prism 报告索引：3 份，其中 `archived=true` / replay-auditable baseline 为 1 份（本轮新增），legacy / non-auditable 历史索引为 2 份。
- 当前任务新增的 formal Prism quorum：1（运行 ID `20260421-redteam-001`，4 席 / 4 家族，`3 responded/followed_up + 1 absent`，verdict=`weak-consensus`，已通过 archive-check）。
- Gemini CLI：本轮 formal Prism 作为 historian 形成有效 verdict，原始输出伴随 SessionEnd hook 噪声，但高容错提取后 schema 有效。
- Kimi CLI：本轮 formal Prism 作为 challenger 返回 verdict；Collect 阶段通过一次 resume 格式追问拿到合法 JSON，并以 `followed_up` 记账。
- Copilot CLI：本轮作为 reviewer 发起 shell run，但 raw 里只有阅读轨迹和 stats，没有 schema verdict；由于本轮没有保留下可复用的 Copilot session handle，最终按 backend limitation 记为 ABSENT。
- Codex CLI：本轮 formal Prism 作为 explorer 返回有效 verdict，同时 `baton-launcher.sh` 已补齐 Codex headless 接入。
- Codex 子 Agent：0 次。Cap 本轮没有开启任何 Codex `spawn_agent` 子进程。

### 5.3 人工验证项（Cap 无法自动化验证的）

- [ ] 历史完整用户项目 E2E 队列（V-2 / V-3 / V-4 / V-6 / V-7 / V-8 / V-9）虽然已经有 repo-owned benchmark carrier，但仍需要单独起完整执行 tranche 去真正消费。

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 历史完整用户项目 E2E 队列仍有 7 项待验证/部分验证 | 这些条目位于 `loom/test-reports/pending-validations.md`，现在已经有 repo-owned benchmark carrier，可执行 blocker 已解除；但条目本身仍需要单独的完整用户项目 E2E tranche 去真实消费 | P1 |
| 历史 formal Prism 报告仍有 2 份是 legacy / non-auditable | 旧报告仍保留在索引里供考古，但它们没有 replay-auditable 的 run-scoped 证据链；当前已通过 `archived=true` 口径诚实化，而不是回填伪证据 | P2 |

### 6.2 触发的新问题

本轮没有再发现新的架构级 blocker。  
相反，后续新暴露的问题都已经收缩成明确补丁：marker stale 判定漏网、acceptance 脆弱断言、危险 cleanup helper、独立评审执行器健康误判、`session-end` pending CAS 竞态、Codex reviewer fallback 缺口、timeout 子进程逃逸、验证证据链分叉、执行保障目录缺失、控制面 gate 失败未传播、docs catalog 缺少读取预算、knowledge / lessons / soul 缺少轻量导航、overlay ask-user 边界缺少保障、状态机文档与脚本枚举漂移、docs 之外的入口自动导入/巨型 acceptance/运行残留 token 风险、CONTRIBUTING 全文权威与首读预算混淆、三轨评审缺少机器 registry、runtime helper 重复实现、`cli_console.md` 镜像边界缺少机器检查。这些问题都已经被压缩成代码、gate、acceptance 或明确 manual-only 边界。

### 6.3 推荐的下一步行动

1. 先用本版 task report 与 formal Prism 归档结果跑完当前 confirmed hash 的 `session-end` reconcile，再把 closeout 口径收回 `status: clear`。
2. 若要继续消化 `loom/test-reports/pending-validations.md` 的 7 项历史完整用户项目 E2E 队列，优先使用 `bash loom/tools/redcap-e2e-benchmark-carrier.sh init <dest-dir>` 创建固定载体，再逐项消费。
3. 后续若新增 formal Prism 运行，继续按 `run_id + session_registry + archive-check` 这条真相链归档，不再把单路健康探测或只读审查口头升级成 quorum。
4. 后续若要进一步瘦身 `prism/runs`，只能在 `prism-runs-lifecycle.sh` 的分类基础上做新的 retention 决策，不得把 named/manual 或 formal run 与 acceptance 夹具混删。

---

## 七、经验沉淀

### 7.1 新增 Lesson（已写入 knowledge/lessons.md）

完整 lessons 以 `compass/knowledge/lessons.md` 为准；本报告只保留本轮执行保障相关的新增重点，避免 task report 自身继续膨胀成 token 污染源。

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-92 | 强制规则必须进入执行保障目录，不能只散落在复活协议或报告里 | 否则“应该做”的规则会在上下文压缩、复活或多宿主接盘时丢失，不会被 hook / validator / manual-only 边界消费 |
| L-93 | 上层 validator 消费下层控制面检查时必须显式传播失败 | 否则 docs catalog、execution guarantee、revival 这类保障脚本失败时，父级 spec-check 仍可能误绿 |
| L-94 | docs catalog 只是止血，真正的上下文治理必须有 plan / budget / retention 三段式 | 否则索引虽然新鲜，后续 agent 仍可能目录级或 glob 级打开历史报告，把冻结 evidence 重新变成 token 污染 |
| L-95 | 状态机文档和脚本合法状态必须有 contract check | 否则 dispatcher 文档允许的状态可能被 validator 拒绝，或者脚本新增状态后文档不知情，治理层继续分叉 |
| L-96 | token 风险不能只治理 docs，还要覆盖入口自动导入、巨型脚本与 ignored 运行残留 | 否则 docs catalog 止血后，上下文爆炸会从宿主入口、acceptance 全文或 `prism/runs` 这类运行目录反弹 |
| L-97 | 权威规范变大时不能简单贴“token 陷阱”标签，必须拆成核心契约与章节路由 | `CONTRIBUTING.md` 继续保留全文权威，启动路径只读 core，并通过章节路由和 gate 防止全文默认注入回流 |

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

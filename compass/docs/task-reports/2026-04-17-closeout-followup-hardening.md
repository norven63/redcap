# 任务完成报告：closeout follow-up 硬化收口

**报告日期**：2026-04-17
**执行者**：Cap（Copilot CLI / GPT-5.4）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：closeout 尾链的高风险边界已经补成 repo-owned 硬约束，最后一轮独立 code review、redteam 和 ultimate full suite 都已收口。
- 详情：`compass/tools/redcap-interop-governance.sh`、`redcap-task-report-check.sh`、`redcap-task-report-register.sh`、`redcap-layerB-task-complete-guard.sh`、`redcap-layerB-session-end.sh`、`redcap-pending-closure-reconcile.sh` 与 Copilot session-context helper 现在都统一走 canonical 报告锚点、PID-reuse-safe / legacy-compatible 锁判活、fail-closed 的 session 绑定与 closeout 账本语义。新增的 traversal、symlink、absolute anchor、legacy 2-field live lock、source-load 等回归也已全部纳入 acceptance。

### 0.2 上一步完成的是

- 上一步完成的是：飞书双向链路与 overlay P0、Copilot 会话身份锚点、Copilot completion 主链硬化已经分别收口；本轮是在这些成果之上，把最后一批 closeout follow-up 风险逐个打穿。

### 0.3 下一步计划做的是

- 下一步计划做的是：完成 commit-proof，并在 clean worktree 上触发 live runtime 的最终 `on-complete / session-end / 飞书通知` 收尾。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：飞书双向链路与 overlay P0 收口 → Copilot 会话身份锚点收口 → completion 主链硬化 → closeout follow-up 硬化 → commit-proof / live runtime 最终收尾。
- 当前所在位置：closeout follow-up 硬化已完成，仍待执行的是 `commit-proof` 与 live runtime 最终闭环。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 我想说的是，没有这个skill是什么意思？我们现在不是在redcap里吗？writing-plans是什么skill？它是谁让你去调用的？它和redcap什么关系？为什么在redcap的开发流程里突然蹦出一个莫名其妙的skill？你能明白我现在的混乱吗？

> 记录一个需求“把本次skill混乱的问题当作P0高危红线bug接触，并且要回归通过验证”，你先继续完成剩下任务步骤

> 既然讨论到这里了，就完成这个任务吧，之后我们开始专心回归主线任务

> 1. 为什么这次又没有发飞书通知？ 2. 我要的不是你发飞书，而是要你发现和解决“不发飞书的原因”，因为和飞书一起的还有很多个必执行任务和逻辑，飞书只是比较容易发现没执行的，其他的任务现在根本不清楚是否也遗漏了，如果是的话，那么可以宣判redcap开发到现在的所谓100%保障hook机制，是彻底失败的，它完全对抗不了长任务、长对话

### 1.2 触发背景

前面几轮已经把飞书链路、overlay skill 边界、Copilot 会话身份锚点和 `task-complete -> on-complete` 主链补齐，但 closeout 真正进入终段后，独立审查又连续打出一批“只会在长任务、脏 worktree、旧 runtime 状态、旧锁格式、路径污染场景里出现”的尾部风险。  
这些问题如果不继续收口，就会让前面宣称已经补好的 completion / session-end / 飞书闭环重新失真。  
所以本轮目标不是再做新能力，而是把最后的 closeout follow-up 风险逐条硬化到**写入层、读取层、锁语义、宿主绑定层和 acceptance 层**。

---

## 二、方案讨论

### 2.1 问题分析

本轮问题的共同特征，是它们都不属于“主链不存在”，而属于**主链存在但尾部边界不够硬**。  
典型表现包括：报告锚点虽然从 `../` traversal 改成了 canonical 路径，但 git 发现的 report file 仍可能被 symlink 逃逸污染；锁虽然已经带 `process_started_at`，但 legacy 两列锁的升级兼容又可能误杀旧活锁；Copilot session-context helper 虽已落地，但 `source` 场景下若还用 `$0` 定位脚本目录，就会让 acceptance 变成假绿。  
因此，本轮不能靠“补一个 if”收口，必须把**canonicalization、fail-closed、legacy 兼容、runtime load 校验、acceptance 回归**作为一套统一治理动作落地。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| 报告锚点校验 | 选项 A | 继续在各脚本里散落使用 glob / `-f` / 目录前缀判断 | 改动少 | traversal、absolute path、symlink、root symlink 都容易漏 |
| 报告锚点校验 | 选项 B | 在 interop 底座集中 canonicalize，并要求读写两端都只接受 canonical repo-relative report path | 约束统一、下游脚本可共享 | 需要补一批回归，触及面广 |
| legacy 锁兼容 | 选项 A | 旧两列锁一律当 stale prune | 最干净 | 会误杀升级期仍活着的旧锁持有者 |
| legacy 锁兼容 | 选项 B | 仅靠 grace window 保活 legacy 锁 | 实现简单 | 时间久了仍会误杀活锁，或无法区分 PID reuse |
| legacy 锁兼容 | 选项 C | 优先用 live process started_at 与 legacy created_at 做“同一进程 / PID reuse”判定，无法取值时再退回 grace window | 兼顾活锁兼容与 PID reuse | 需要跨脚本统一判活语义 |
| Copilot session helper | 选项 A | 继续用 `$0` 推脚本目录，并在 acceptance 里吞掉 source 错误 | 看起来最省事 | 很容易出现 helper 根本没加载却假绿 |
| Copilot session helper | 选项 B | 改用 `BASH_SOURCE[0]`，并在 acceptance 明确断言 source/load 成功 | source 场景稳定、假绿更难发生 | 需要补测试 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| 报告锚点校验 | 选项 B | 只有把 canonicalization 下沉到 interop 底座，并让 checker / register / guard / session-end / reconcile 共用，才能真正把 traversal / symlink / absolute anchor 一次性收口 | CAP_DECIDE |
| legacy 锁兼容 | 选项 C | 这条线既不能误杀升级期的 live legacy holder，也不能重新放开 PID reuse；必须用 live process started_at + legacy created_at 做兼容判定 | CAP_DECIDE |
| Copilot session helper | 选项 B | 当前问题不是 helper 有没有逻辑，而是 source 场景下能不能真的加载成功；因此必须同时修实现和 acceptance | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.github/hooks/scripts/redcap-copilot-session-context.sh` | 新建 / 修改 | Copilot session-context helper 改用 `BASH_SOURCE[0]`，并在多命中时 fail-closed |
| `compass/tools/redcap-interop-governance.sh` | 修改 | 集中提供 canonical 报告路径 helper；pending closure 写入层统一 canonicalize；legacy 2-field lock 兼容与 PID reuse 判定下沉到底座 |
| `compass/tools/redcap-task-report-check.sh` | 修改 | marker / pending / git-discovered report 全部先 canonicalize；symlink escape 与 root symlink escape fail-closed |
| `compass/tools/redcap-task-report-register.sh` | 修改 | register 只接受真实位于 `compass/docs/task-reports/` 下的 canonical report 文件 |
| `compass/tools/redcap-layerB-task-complete-guard.sh` | 新建 / 修改 | pending artifact 读取后先 canonicalize，避免 absolute/raw anchor 让 auto-register 或重试逻辑失真 |
| `compass/tools/redcap-layerB-session-end.sh` | 修改 | blocked rewrite / success 路径只回写 canonical repo-relative report artifact |
| `compass/tools/redcap-pending-closure-reconcile.sh` | 修改 | 通过写入层 canonicalization，旧 absolute artifact 在 reconcile rewrite 时不再被原样写回 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增 traversal / symlink / absolute anchor / legacy 2-field lock / source-load 等回归 |
| `compass/docs/task-reports/2026-04-17-closeout-followup-hardening.md` | 新建 | 归档本轮 closeout follow-up 硬化结果 |

### 3.2 技术实现要点

第一，**报告锚点现在只有一种合法形态：canonical repo-relative 的真实 task report 文件**。  
`redcap_interop_resolve_report_abs_path / redcap_interop_resolve_report_rel_path` 会拒绝 `../` traversal、绝对路径污染、symlink report file，以及整个 `compass/docs/task-reports` 根目录本身是 symlink 的情况。  
之后无论是 register、task-report-check、session-end 还是 pending closure 写入，都只能消费这套 canonical 输出。

第二，**canonicalization 被下沉到了写入层，而不是停留在读的一侧**。  
`redcap_interop_write_pending_closure()` 现在会在落盘前统一 canonicalize `artifact_path`，因此 `pending-closure-reconcile`、`session-end blocked rewrite`、后续 marker / guard / checker 再读到的都是 repo-relative 规范值，而不是 legacy absolute path 或诊断字符串。

第三，**legacy 两列锁的兼容不再是“最近 10 分钟算活着，过了就算死”**。  
当前实现会先读取 live process 的 `started_at`，再和 legacy lock 里的 `created_at` 比较：如果进程启动时间早于或等于锁创建时间，就视为同一活进程；如果进程启动时间晚于锁创建时间，就视为 PID reuse / stale。  
只有拿不到 `started_at` 解析值时，才退回 grace window 作为保守兜底。

第四，**Copilot session-context helper 的 source-load 现在也有物理校验了**。  
`.github/hooks/scripts/redcap-copilot-session-context.sh` 现在用 `BASH_SOURCE[0]` 定位自身目录，acceptance 则显式断言 `loaded=1`，不再允许“helper 其实没 source 成功，但测试因为吞 stderr 误判为绿”。

第五，**本轮不是只修代码，也把审查与回归体系补成了终局质量门**。  
独立 code review `closeout-review-r7` 最终给出 “No significant issues found in the reviewed changes.”；独立 redteam `closeout-redteam-r10` 最终给出 clean verdict。  
同时，ultimate full suite 把 traversal、symlink、absolute anchor、legacy live lock、PID reuse、session-context source-load 这几条全都纳入了同一轮 acceptance。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| canonical 报告锚点 | `compass/tools/redcap-interop-governance.sh` | 指“真实落在 `compass/docs/task-reports/` 下、并被归一成仓库相对路径的报告文件路径”，后续所有 closeout 逻辑都只认它 |
| pending closure | `compass/tools/redcap-interop-governance.sh` / `redcap-pending-closure-reconcile.sh` | 指还没完全收尾、需要下次会话继续补的 closeout 义务账本 |
| task-complete guard | `compass/tools/redcap-layerB-task-complete-guard.sh` | 指 Copilot 在 `task-complete` 时自动尝试登记报告并触发 `redcap-on-complete.sh` 的守门脚本 |
| legacy 2-field lock | `redcap-interop-governance.sh` / `redcap-layerB-task-complete-guard.sh` | 指老版本只写了 `pid + created_at` 的锁文件；本轮新增了升级期兼容判活逻辑 |
| Copilot session-context helper | `.github/hooks/scripts/redcap-copilot-session-context.sh` | 指从 `session-state/*/inuse.<pid>.lock` 推导当前 Copilot session/workboard 绑定信息的脚本 |

### 3.3 关联变更

本轮没有重新定义飞书链路、overlay handoff、Copilot continuity 或 completion 主链本身，而是把这些已落地能力的**尾链边界**补到足够硬。  
换句话说，前面几份报告解决的是“主链有没有”，这份报告解决的是“主链最后 5% 的边角条件会不会在长任务里重新把整条链弄假”。

---

## 四、人工审核要点

> ⚠️ 以下是 Norven 需要重点确认的内容，其他部分 Cap 已自行验证。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | commit 后的 live runtime 最终 `on-complete / session-end / 飞书通知` | 这不是代码决策问题，而是收尾执行问题；需要在 clean worktree 上真实跑一遍，确认最终通知按预期发出 | P0 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 壳脚本语法检查 | `bash -n .github/hooks/scripts/redcap-copilot-session-context.sh compass/tools/redcap-interop-governance.sh compass/tools/redcap-task-report-check.sh compass/tools/redcap-task-report-register.sh compass/tools/redcap-layerB-task-complete-guard.sh compass/tools/redcap-layerB-session-end.sh compass/tools/redcap-pending-closure-reconcile.sh compass/tools/redcap-multi-session-acceptance.sh` | ✅ |
| 目录 / spec 一致性检查 | `bash compass/tools/redcap-spec-check.sh "$PWD"` | ✅ |
| symlink / absolute / legacy-lock 关键回归 | `bash compass/tools/redcap-multi-session-acceptance.sh report-register-rejects-symlinked-report-root && bash compass/tools/redcap-multi-session-acceptance.sh task-report-check-rejects-symlink-report-escape && bash compass/tools/redcap-multi-session-acceptance.sh task-complete-guard-normalizes-absolute-pending-anchor && bash compass/tools/redcap-multi-session-acceptance.sh sessionstart-auto-reconcile-normalizes-absolute-artifact && bash compass/tools/redcap-multi-session-acceptance.sh pending-closure-lock-keeps-live-legacy-lock && bash compass/tools/redcap-multi-session-acceptance.sh task-complete-guard-keeps-live-legacy-lock` | ✅ |
| ultimate full suite | `bash compass/tools/redcap-spec-check.sh "$PWD" && bash compass/tools/redcap-multi-session-acceptance.sh all` | ✅ |
| 独立 code review | `closeout-review-r7` | ✅ clean（No significant issues found in the reviewed changes.） |
| 独立 redteam | `closeout-redteam-r10` | ✅ clean |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 在形成 commit-proof 后，真实触发本次 live runtime 的最终 `on-complete / session-end / 飞书通知` 闭环。

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 当前 worktree 仍未满足 commit-proof | 这不是代码缺陷，而是因为本轮超长任务的累计改动尚未形成 commit | P0 |
| live runtime 最终完成通知尚未执行 | 依赖上一项先让 worktree 进入 clean + `HEAD != INITIAL_HEAD` 的 commit-proof 状态 | P0 |

### 6.2 触发的新问题

本轮没有留下新的代码 blocker。  
相反，独立 review 与 redteam 在 closeout 尾段连续打出的 traversal、symlink、absolute anchor、legacy live lock、Copilot helper source-load 这些风险，都已经被纳入 repo-owned 回归。

### 6.3 推荐的下一步行动

1. 将当前工作区整理为一个正式 commit，满足 `commit-proof-check`。
2. 以这份报告作为当前报告锚点，执行 live runtime 的最终 `on-complete / session-end / 飞书通知` 闭环。
3. 完成后回到长期主线 `F2 规范到 gate 的翻译链`。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-70 | 报告锚点校验不能停留在 glob / `-f` 层 | 只要 closeout 要消费“任务报告路径”，就必须统一 canonicalize，并且显式拒绝 traversal、absolute path、symlink file、symlinked root |
| L-71 | 锁格式升级不能只做 stale prune，还要考虑 live legacy holder 与 PID reuse 的并存 | 对旧锁格式的兼容必须同时保护升级期活锁，并继续防止 PID reuse 误认领 |

### 7.2 流程改进建议

以后凡是 closeout 主链进入“最后 5% 边角硬化”阶段，都应默认追加一轮**独立 code review + 独立 redteam + ultimate full suite**。  
原因很简单：尾链问题往往不是主链断了，而是只有在脏 worktree、旧状态、旧锁、symlink、source-load 这种组合场景下才会暴露，单一路径自测很难一次看全。

---

## 八、附录

### 附录 A：Commits

```text
（当前报告写入时，本轮改动仍在工作区，尚未形成新的 commit）
```

### 附录 B：棱镜调用记录（如有）

本轮没有新增 Prism 报告；独立审查主要通过 code review agent `closeout-review-r7` 与 redteam agent `closeout-redteam-r10` 完成。

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md` 中的 `U31 / U32 / U38 / U39`
- 前序任务报告：`compass/docs/task-reports/2026-04-16-feishu-duplex-and-overlay-p0.md`
- 前序任务报告：`compass/docs/task-reports/2026-04-16-copilot-session-anchor.md`
- 前序任务报告：`compass/docs/task-reports/2026-04-16-completion-hook-hardening.md`
- 当前真相源：`.dev-task.md`

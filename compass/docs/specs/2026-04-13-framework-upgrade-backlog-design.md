# RedCap 框架升级路线说明

> **机器权威**：`references/backlogs/framework-upgrade.json`
>  
> **本文作用**：给 Norven 直接看懂“这条长期路线是什么、现在做到哪、接下来怎么走”。
>  
> **边界提醒**：这份文档不替代 `.dev-task.md`，也不替代脚本 / gate / validator。它只负责把路线说清楚。

---

## 一句话先看懂

这份 backlog 现在已经不是“单份设计稿”，而是一套**长期路线机制**：

1. `references/backlogs/framework-upgrade.json` 负责给脚本读，保存阶段状态、条目状态和当前焦点。
2. `.dev-task.md` 继续负责给执行链读，保存当前任务的原始输入、确认需求和当前切片。
3. 本文负责给你读，把术语、人话解释、推进顺序和当前状态说明白。

简单说：**`.dev-task.md` 管“现在这刀”，backlog 管“后面几阶段”，本文管“把这条路线讲明白”。**

## 这份机制管什么 / 不管什么

### 管什么

1. 管跨会话的长期路线：哪些阶段已经完成，哪些还没做，当前重点是什么。
2. 管当前任务和长期路线的锚定关系：`.dev-task.md` 里会写 `backlog_source / backlog_id / backlog_item`。
3. 管人类可读说明的同步：如果机器权威改了，但本文没同步，收尾门会直接报错。

### 不管什么

1. 不接管当前 live task 的执行真相源；那仍然是 `.dev-task.md`。
2. 不把 spec 文档重新抬成运行时权威；运行保障仍然落在 hook、gate、runtime state、脚本和校验器。
3. 不替你决定优先级；如果后续阶段要改顺序，仍然要由你和我明确确认。

## 使用方式

1. **开始做某个长期条目时**：在 `.dev-task.md` 里写明 `backlog_source / backlog_id / backlog_item`，把当前任务锚到这条长期路线。
2. **更新路线状态时**：先改 `references/backlogs/framework-upgrade.json`，再执行  
   `bash compass/tools/redcap-backlog-check.sh sync .dev-task.md`
3. **准备收尾时**：现有 PM Gate / drift / validator chain 会自动检查三件事：
   - `.dev-task.md` 里的 backlog 锚点是否真的存在
   - 当前任务绑定的 backlog 条目是否能在机器权威里找到
   - 本文里的自动同步区块是否和机器权威一致

如果你看到“human-readable backlog guide is out of sync”，意思不是代码坏了，而是**路线状态已经改了，但给人看的说明还没同步**。

<!-- redcap:backlog-generated:start -->
## 当前状态总览（自动同步）

### 这份机制对应哪里
- 机器权威：`references/backlogs/framework-upgrade.json`
- 人类说明：`compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md`
- 当前焦点：`F2 规范到 gate 的翻译链`
- 当前焦点说明：D1 已完成：spec 生命周期门已补齐；当前继续推进 F2，把更广泛的治理规范继续翻译成可执行 gate。

### 阶段顺序
| 阶段 | 状态 | 主要条目 | 说明 |
|---|---|---|---|
| 阶段 0：长期路线机制化 | 已完成 | F4 | 长期路线已升级成机器权威 + 人类说明 + 门禁接线的正式机制。 |
| 阶段 1：权威核心加固 | 已完成 | A1 / A2 / E1 / F1 | 权威核心、制品生命周期门与治理基建已经完成。 |
| 阶段 2：连续性权威中心化 | 已完成 | B1 / B2 / B3 / C1 | 连续性权威、恢复门、显式导入反馈和宿主镜像边界都已落地。 |
| 阶段 3：治理可执行化 | 进行中 | D1 / F2 / F3 / A3 | D1 已收口；当前继续推进 F2 / F3 / A3，把更多治理规范补成可执行 gate 与审计轨。 |
| 阶段 4：宿主体验与操作反馈 | 进行中 | C2 / C3 | `cli_console.md` 已补上覆盖式镜像 helper，下一步仍要继续收口 overlay / ask_user 的诚实降级。 |
| 阶段 5：信息架构与运行时收敛 | 待推进 | D2 / D3 / E2 / E3 | 清理知识导航、docs 保留策略、runtime helper 收敛与统一诊断。 |

### 条目状态
| 条目 | 所属能力 | 状态 | 优先级 | 一句话说明 |
|---|---|---|---|---|
| A1 收尾账本与义务生命周期统一 | 权威与收尾收口 | 已完成 | P0 | pending closure、收尾账本、陈旧义务核销与 fail-closed 收尾已经并入同一条权威链。 |
| A2 统一校验链与 PM Gate 加固 | 权威与收尾收口 | 已完成 | P0 | session-start、stop-review、on-complete、session-end 已统一走 validator chain，不再分散漂移。 |
| A3 三轨评审门（架构 / 治理 / 契约） | 权威与收尾收口 | 待推进 | P1 | 目前已有统一 stop-review 入口，但还没有拆成架构、治理、契约三条专门审计轨。 |
| B1 RedCap 自持的连续性清单 | 会话隔离与连续性 | 已完成 | P0 | 连续性权威已收口到 `compass/.runtime/sessions/<runtime_session_id>/manifest.yaml`，宿主只读镜像不再冒充真相源。 |
| B2 会话恢复门与宿主能力矩阵 | 会话隔离与连续性 | 已完成 | P1 | 不同宿主已统一进入 full / degraded / unsupported 模式，恢复门与能力矩阵都已落地。 |
| B3 显式导入反馈与端到端验收 | 会话隔离与连续性 | 已完成 | P1 | import-ready / import-success 反馈、跨宿主验收与 runtime mismatch fail-closed 都已接通。 |
| C1 宿主面板只读镜像化 | 宿主适配与交互面 | 已完成 | P1 | 宿主 workboard 已由单一脚本生成 canonical pointer，只能镜像 RedCap 状态，不能反推真相源。 |
| C2 `cli_console.md` 彻底降格为展示镜像 | 宿主适配与交互面 | 进行中 | P1 | 已补上覆盖式镜像 helper 与规范约束，但由于最终对话输出不归仓库脚本控制，仍未形成完全自动的宿主级强制。 |
| C3 宿主 overlay / ask_user 诚实降级 | 宿主适配与交互面 | 待推进 | P1 | shared skill 资产边界和 ask_user 规则已写进规范，但还缺机器可审计的诚实降级标记。 |
| D1 spec 生命周期权威收紧 | 文档与证据分层 | 已完成 | P0 | spec 生命周期策略、归档根目录、replaced_by 关系与命名/role 准入都已接入 spec-check，旧 spec 不再能留在 active specs 根目录里假装当前入口。 |
| D2 knowledge / docs 边界导航 | 文档与证据分层 | 待推进 | P2 | knowledge 目录已有内容，但还没有统一导航入口，后续仍容易让人不清楚该去哪里找规则。 |
| D3 docs 保留策略执行化 | 文档与证据分层 | 待推进 | P2 | 保留策略已经写在 docs 索引里，但还缺自动审计、归档日志与 check-only 门。 |
| E1 制品生命周期提交前闸门 | 运行时资产与文件收敛 | 已完成 | P0 | 分类器、repo-owned pre-commit、mixed-lifecycle 提示与收尾历史审计都已补齐。 |
| E2 session / runtime helper 收敛 | 运行时资产与文件收敛 | 待推进 | P2 | 运行时 helper 已很多，后续还要再收口共享 API，减少重复读写和脚本体积。 |
| E3 统一诊断与可观测性 | 运行时资产与文件收敛 | 待推进 | P1 | 目前理解 authority / continuity / drift 状态还要手查多个脚本，缺一条统一 diagnose 入口。 |
| F1 治理主线制度化与债务表 | 治理与规范可执行化 | 已完成 | P0 | governance_tranche 标记、治理评审清单和治理债务表都已落地，治理已成为独立主线。 |
| F2 规范到 gate 的翻译链 | 治理与规范可执行化 | 进行中 | P1 | spec-registry + spec-lifecycle-policy + spec-check 已把 spec 维度推进到第二层翻译链，但 hook / lesson / contract 等更广泛的治理映射还没做完。 |
| F3 hook / lesson / contract / 状态机治理硬化 | 治理与规范可执行化 | 待推进 | P1 | 这些真正保运行的机制还要继续变成脚本化、校验化、可审计化的硬约束。 |
| F4 backlog 长期路线机制化 | 治理与规范可执行化 | 已完成 | P0 | 机器可读 backlog 权威、人类说明文档自动同步、backlog 门禁与宿主镜像锚点都已落地。 |

### 术语对照
| 术语 | 人话解释 |
|---|---|
| backlog（长期路线） | 用来保存“这轮之后还要继续做什么”的跨会话路线表。它不接管当前任务执行细节，只负责长期保持。 |
| active_slice（当前执行切片） | `.dev-task.md` 里的当前这一刀；它告诉脚本“现在正在做哪部分”，不等于整个长期路线。 |
| validator chain（统一校验链） | 把 PM Gate、漂移检查、任务报告检查、制品生命周期检查等串成一条 fail-closed（失败即阻断）执行链。 |
| mirror-only（只读镜像面） | 宿主 plan.md / workboard 只能展示 RedCap 当前指针和状态，不能反向改写真相源。 |
| spec（设计说明文档） | 负责给人看清设计意图、边界和证据，不负责替代脚本或 gate 成为运行时权威。 |
<!-- redcap:backlog-generated:end -->








## 后续推进顺序

1. **先做“阶段 0：长期路线机制化”**  
   先把 backlog 本身变成正式机制，后面阶段才不会再次退回“只靠一份说明文档记忆路线”。

2. **阶段 1 和阶段 2 目前都已完成**  
   权威核心、制品生命周期门、连续性权威、恢复门、显式导入反馈和宿主只读镜像边界，都已经有脚本和验收支撑，不是停留在文档层。

3. **下一批真正待做的重点，是阶段 3 与阶段 4**  
   - 阶段 3：继续把 spec / governance / hook / lesson / contract 这些规则翻成 gate 和 validator  
   - 阶段 4：解决 `cli_console.md`、overlay / ask_user 这类宿主体验和诚实降级问题

4. **阶段 5 是长期维护层**  
   knowledge 导航、docs 保留策略、runtime helper 收敛、统一诊断都很重要，但应晚于前面的权威与治理硬化。

## 为什么现在要先补这套机制

因为你已经明确指出两个真实问题：

1. **旧 backlog 太像普通说明文档，缺执行保障**  
   这会导致“路线有价值，但状态容易陈旧”，久了又回到靠人脑记忆。

2. **旧 backlog 对人不够友好**  
   就算里面有路线，如果写法还是黑话堆叠，阅读成本依旧高，人类很难持续 review。

所以这次不是单纯“再写一份新文档”，而是把 backlog 分成三层：

1. **机器权威**：`references/backlogs/framework-upgrade.json`
2. **执行锚点**：`.dev-task.md`
3. **人类说明**：本文

这样才同时满足“可执行”“可追踪”“可读”三件事。

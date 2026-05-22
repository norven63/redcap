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
- 当前焦点：`P4-16 R1 Prism report archive live copy-first apply after freeze guard`
- 当前焦点说明：P4-16 待推进：在 P4-15 已稳定 Prism 报告归档集合边界后，重新评审并推进 Prism report archive 的 live copy-first apply；仍不得执行旧锚点退休、raw evidence cleanup 或正式发布动作。

### 阶段顺序
| 阶段 | 状态 | 主要条目 | 说明 |
|---|---|---|---|
| 阶段 0：长期路线机制化 | 已完成 | F4 | 长期路线已升级成机器权威 + 人类说明 + 门禁接线的正式机制。 |
| 阶段 1：权威核心加固 | 已完成 | A1 / A2 / E1 / F1 | 权威核心、制品生命周期门与治理基建已经完成。 |
| 阶段 2：连续性权威中心化 | 已完成 | B1 / B2 / B3 / C1 | 连续性权威、恢复门、显式导入反馈和宿主镜像边界都已落地。 |
| 阶段 3：治理可执行化 | 已完成 | D1 / F2 / F3 / A3 | D1 / F2 / F3 / A3 均已收口：spec、docs、knowledge、hook、contract、FSM、三轨评审与 token 风险均已进入可执行 gate。 |
| 阶段 4：宿主体验与操作反馈 | 已完成 | C2 / C3 | C2 / C3 均已收口：`cli_console.md` 降格为 local-only 覆盖式展示镜像，overlay / ask_user 诚实降级也已接入审计。 |
| 阶段 5：信息架构与运行时收敛 | 已完成 | D2 / D3 / E2 / E3 | D2 / D3 / E2 / E3 均已收口：docs/knowledge 渐进披露、docs 保留策略、runtime helper 收敛与统一诊断均已接入检查。 |
| 阶段 6：发布准备控制面 | 已完成 | P4-2l / P4-2m / P4-2n / P4-2o / P4-2p / P4-2q / P4-2r / P4-2s | 正式发布动作之前，R1 延期根目录处置预检、三类 blocker 的专项预检，以及 internal-control-plane 的物理拆分 dry-run 均已进入可审计控制面；当前仍不执行真实发布。 |
| 阶段 7：发布准备证据边界 | 已完成 | P4-3e | 正式发布动作之前，先把 Prism 证据层拆分推进到 dry-run / no-apply 级别，避免 raw evidence、报告归档和 package-visible Prism 工具继续混成一个不可审计边界。 |
| 阶段 8：发布准备控制面 apply 预检 | 已完成 | P4-4 | 正式发布动作之前，已把控制面未来 copy-first / alias-first apply 的前置护栏、旧锚点保留策略、回滚门禁和验证计划做成机器可检查状态；当前仍不执行真实复制、移动、删除或发布。 |
| 阶段 9：发布准备 Prism evidence apply 预检 | 已完成 | P4-5 | 正式发布动作之前，已把 Prism evidence 未来 copy-first / alias-first apply 的前置护栏、证据保留策略、回滚门禁和验证计划做成机器可检查状态；当前仍不执行真实移动、删除、清理或发布。 |
| 阶段 10：发布准备控制面 runtime facade | 已完成 | P4-6 | 正式发布动作之前，已把可公开运行时需要调用的控制面工具做成 copy-first facade，让 runtime 包面具备稳定入口；旧 compass/tools 仍保留为权威实现。 |
| 阶段 11：发布准备下一 blocker 切片选择 | 已完成 | P4-7 | 正式发布动作之前，先对 P4-6 后的剩余 R1 blocker 做多视角路线评审，选出下一条可自主推进且不会破坏旧锚点、证据链或人工保留决策的切片。 |
| 阶段 12：发布准备 Prism package-visible support | 已完成 | P4-8 | 正式发布动作之前，按 P4-7 路线评审推进 Prism package-visible support 与 provider-routing contract 的非破坏性 copy-first / alias-first 小切片。 |
| 阶段 13：发布准备下一 blocker 切片选择 | 已完成 | P4-9 | 正式发布动作之前，在 P4-8 收口后已重新评审剩余 R1 blocker，并选定 Prism tracked report archive copy-first / report-index migration preflight 作为下一条安全小切片。 |
| 阶段 14：发布准备 Prism report archive 预检 | 已完成 | P4-10 | 正式发布动作之前，已证明 Prism tracked report archive 与 report index 可以进入 copy-first / alias-first 迁移预检；旧报告锚点保留，raw run evidence 未清理。 |
| 阶段 15：发布准备下一 blocker 切片选择 | 已完成 | P4-11 | 正式发布动作之前，在 P4-10 收口后已重新评审剩余 R1 blocker，并选定 Prism report archive copy-first / alias-first migration planning 作为下一条安全小切片。 |
| 阶段 16：发布准备 Prism report archive 迁移规划 | 已完成 | P4-12 | 正式发布动作之前，只规划 Prism 报告归档的 copy-first / alias-first 清单、旧锚点 alias、回滚和验证方案；当前仍不执行物理复制、移动、删除或证据清理。 |
| 阶段 17：发布准备 Prism report archive apply readiness | 已完成 | P4-13 | 正式发布动作之前，已基于 P4-12 plan 完成 Prism report archive apply readiness / rehearsal：临时目录演练、alias 兼容、archive/package proof 与回滚路径已可机器检查；仍不退休旧锚点、不清理 raw evidence、不执行正式发布。 |
| 阶段 18：发布准备下一 blocker 切片选择 | 已完成 | P4-14 | P4-14 已由 Claude Code 与 Kimi 完成路线评审；Cap 采纳保守路径，选定先做 Prism report archive churn/freeze guard。 |
| 阶段 19：发布准备 Prism report archive 漂移冻结 | 已完成 | P4-15 | 正式发布动作之前，已冻结/隔离 Prism 报告归档演练与后续 live apply 之间的报告自增、索引和哈希漂移，避免把审查本身变成反复改变迁移目标的噪声源。 |
| 阶段 20：发布准备 Prism report archive live copy-first apply | 待推进 | P4-16 | 正式发布动作之前，在 P4-15 的冻结集合保护下推进 Prism 报告归档 live copy-first apply；旧锚点、raw evidence cleanup 和正式发布动作仍保持禁止。 |

### 条目状态
| 条目 | 所属能力 | 状态 | 优先级 | 一句话说明 |
|---|---|---|---|---|
| A1 收尾账本与义务生命周期统一 | 权威与收尾收口 | 已完成 | P0 | pending closure、收尾账本、陈旧义务核销与 fail-closed 收尾已经并入同一条权威链。 |
| A2 统一校验链与 PM Gate 加固 | 权威与收尾收口 | 已完成 | P0 | session-start、stop-review、on-complete、session-end 已统一走 validator chain，不再分散漂移。 |
| A3 三轨评审门（架构 / 治理 / 契约） | 权威与收尾收口 | 已完成 | P1 | 三轨评审已收口为 `references/review-tracks.json` 机器 registry，并由 stop-review prompt、治理 checklist 与 review-tracks gate 消费。 |
| B1 RedCap 自持的连续性清单 | 会话隔离与连续性 | 已完成 | P0 | 连续性权威已收口到 `compass/.runtime/sessions/<runtime_session_id>/manifest.yaml`，宿主只读镜像不再冒充真相源。 |
| B2 会话恢复门与宿主能力矩阵 | 会话隔离与连续性 | 已完成 | P1 | 不同宿主已统一进入 full / degraded / unsupported 模式，恢复门与能力矩阵都已落地。 |
| B3 显式导入反馈与端到端验收 | 会话隔离与连续性 | 已完成 | P1 | import-ready / import-success 反馈、跨宿主验收与 runtime mismatch fail-closed 都已接通。 |
| C1 宿主面板只读镜像化 | 宿主适配与交互面 | 已完成 | P1 | 宿主 workboard 已由单一脚本生成 canonical pointer，只能镜像 RedCap 状态，不能反推真相源。 |
| C2 `cli_console.md` 彻底降格为展示镜像 | 宿主适配与交互面 | 已完成 | P1 | `cli_console.md` 已被固定为 gitignored local-only 覆盖式展示镜像，并由 artifact classifier 与 mirror check 审计；宿主最终回复 UI 不归 repo 脚本强控，不再冒充 RedCap backlog 残留。 |
| C3 宿主 overlay / ask_user 诚实降级 | 宿主适配与交互面 | 已完成 | P1 | shared skill 资产边界、ask_user 人工介入门与下游 skill 不可阻断规则已由 overlay governance check 审计。 |
| D1 spec 生命周期权威收紧 | 文档与证据分层 | 已完成 | P0 | spec 生命周期策略、归档根目录、replaced_by 关系与命名/role 准入都已接入 spec-check，旧 spec 不再能留在 active specs 根目录里假装当前入口。 |
| D2 knowledge / docs 边界导航 | 文档与证据分层 | 已完成 | P2 | docs 侧通过 catalog / plan / budget 首读，knowledge 侧通过 index.md 首读导航，二者都已接入检查。 |
| D3 docs 保留策略执行化 | 文档与证据分层 | 已完成 | P2 | docs 保留策略已补 check-only retention 审计、归档日志、progressive disclosure 预算门与 spec-check 接线。 |
| E1 制品生命周期提交前闸门 | 运行时资产与文件收敛 | 已完成 | P0 | 分类器、repo-owned pre-commit、mixed-lifecycle 提示与收尾历史审计都已补齐。 |
| E2 session / runtime helper 收敛 | 运行时资产与文件收敛 | 已完成 | P2 | runtime attach/load 重复逻辑已收敛到 `redcap_runtime_attach_current_or_claim` 共享 helper，并由 runtime-helper check 防止关键脚本重新复制本地 attach helper。 |
| E3 统一诊断与可观测性 | 运行时资产与文件收敛 | 已完成 | P1 | 已新增 redcap-diagnose.sh，统一汇总 current-status、docs、knowledge、overlay、execution、revival 与 spec-check。 |
| F1 治理主线制度化与债务表 | 治理与规范可执行化 | 已完成 | P0 | governance_tranche 标记、治理评审清单和治理债务表都已落地，治理已成为独立主线。 |
| F2 规范到 gate 的翻译链 | 治理与规范可执行化 | 已完成 | P1 | spec、docs、knowledge、overlay、execution guarantees、revival 与 diagnostics 均已从自然语言规则接入脚本 / gate / acceptance；更专门的 hook / contract / FSM 深水区交给 F3。 |
| F3 hook / lesson / contract / 状态机治理硬化 | 治理与规范可执行化 | 已完成 | P1 | hook、lesson、contract、状态机、CONTRIBUTING 信息架构、token-risk、runtime helper 与 CLI mirror 均已登记到执行保障并接入 spec-check / diagnose / acceptance。 |
| F4 backlog 长期路线机制化 | 治理与规范可执行化 | 已完成 | P0 | 机器可读 backlog 权威、人类说明文档自动同步、backlog 门禁与宿主镜像锚点都已落地。 |
| P4-2l 正式发布准备计划与人工授权矩阵 | 发布前路线与授权边界 | 已完成 | P0 | 已把正式发布前 10 阶段路线、Norven 必须决策、Cap/Prism 可自主决策和条件授权模板落成机器可审计控制面；本项不执行真实发布、不改发布开关、不选择许可证。 |
| P4-2m 历史资产物理清理发布硬门 | 发布前路线与授权边界 | 已完成 | P0 | 已把“所有历史资产正式发布前必须物理清理或安全归位”升级为 release-readiness 硬门；本项不执行真实发布，也不做无证据删除。 |
| P4-2n 高价值经验发现与候选化发布硬门 | 发布前路线与授权边界 | 已完成 | P0 | 已把 review / bugfix / release / 安全 / 用户纠偏等高价值信号接入 Evolution harvest；正式发布前不能用候选池当前干净冒充候选发现已完成。 |
| P4-2o 正式发布 R1 延期根目录处置预检 | 发布前路线与授权边界 | 已完成 | P0 | 已把 4 组 deferred root groups 做成机器可查 disposition preflight：workspace-state 是本地状态且包面排除，internal-control-plane / prism-layer-and-evidence / internal-layer-a 仍是 release blockers；本项不关闭 R1、不执行发布、不移动目录。 |
| P4-2p R1 控制面契约拆分预检 | 发布前路线与授权边界 | 已完成 | P0 | 已把 internal-control-plane blocker 拆成可机器检查的控制面契约、消费者矩阵、包面边界和后续物理拆分门禁；本项不关闭 R1、不执行发布、不移动目录。 |
| P4-2q R1 Prism 证据保留拆分预检 | 发布前路线与授权边界 | 已完成 | P0 | 已把 prism-layer-and-evidence blocker 拆成可机器检查的 Prism 工具、报告、运行证据、包面边界和后续物理拆分/清理门禁；本项不关闭 R1、不执行发布、不移动或删除 Prism 证据。 |
| P4-2r R1 Layer A 产品边界预检 | 发布前路线与授权边界 | 已完成 | P0 | 把 internal-layer-a blocker 拆成可机器检查的 Layer A/loom 产品边界、包面缺席证明、消费者矩阵和未来公开纳入/排除门禁；本项不关闭 R1、不执行发布、不移动或删除 loom、不替 Norven 裁决产品范围。 |
| P4-2s R1 控制面物理拆分干跑清单 | 发布前路线与授权边界 | 已完成 | P0 | 已把 internal-control-plane 的下一步物理拆分准备成可机器检查的 dry-run manifest、目标分层、别名/回滚计划和验收门禁；本项不关闭 R1、不执行发布、不移动 compass/references。 |
| P4-3e R1 Prism 证据保留拆分干跑清单 | 发布前路线与授权边界 | 已完成 | P0 | 已把 prism-layer-and-evidence 的下一步拆成可机器检查的 dry-run manifest、证据保留分层、no-apply 清理预览边界、别名/回滚计划和验收门禁；本项不关闭 R1、不执行发布、不移动或删除 Prism 证据。 |
| P4-4 R1 控制面物理拆分 apply 预检 | 发布前路线与授权边界 | 已完成 | P0 | 已把 internal-control-plane 的 dry-run 地图升级为可机器检查的 copy-first / alias-first apply 前置护栏；本项未复制、未移动、未删除旧 compass/references 锚点，不关闭 R1，不执行发布。 |
| P4-5 R1 Prism 证据保留 apply 预检 | 发布前路线与授权边界 | 已完成 | P0 | 已把 prism-layer-and-evidence 的 dry-run 证据边界升级为可机器检查的 copy-first / alias-first apply 前置护栏；本项未移动、未删除、未清理 prism 证据，不关闭 R1，不执行发布。 |
| P4-6 R1 控制面 runtime facade copy-first | 发布前路线与授权边界 | 已完成 | P0 | 已把 internal-control-plane batch-1 runtime-public-support 条目推进为 runtime/redcap-core/tools 下的 copy-first facade；旧 compass/tools 仍保持权威锚点，本项不关闭 R1，不执行发布。 |
| P4-7 R1 下一发布前 blocker 切片选择 | 发布前路线与授权边界 | 已完成 | P0 | P4-6 收口后先由 Claude Code 与 Kimi 评审下一条可自主推进、非破坏性的 R1 blocker 切片；本项只产出路线结论和后续锚点，不关闭 blocker、不执行发布、不清理证据、不移动旧锚点。 |
| P4-8 R1 Prism package-visible support copy-first | 发布前路线与授权边界 | 已完成 | P0 | 已按 P4-7 路线评审完成 prism-layer-and-evidence batch-1：新增 8 个 runtime Prism facade，保留旧 prism 锚点权威性，保持 provider fallback 保护；本项不清理证据、不移动旧锚点、不关闭整个 blocker。 |
| P4-9 R1 下一发布前 blocker 切片选择 after Prism package-visible support | 发布前路线与授权边界 | 已完成 | P0 | P4-8 收口后，已由 Claude Code 与 Kimi 评审剩余 R1 blocker 并选定下一条安全小切片：Prism tracked report archive copy-first / report-index migration preflight；本项只完成路线选择与锚点登记，不关闭 blocker、不执行发布、不清理证据。 |
| P4-10 R1 Prism report archive copy-first / index migration preflight | 发布前路线与授权边界 | 已完成 | P0 | 已按 P4-9 路线评审完成 Prism tracked report archive 的 copy-first / report-index migration preflight：报告索引与归档边界已可机器检查，旧 prism/reports 锚点保留，prism/runs raw evidence 未删除、未移动、未清理；本项不关闭整个 prism-layer-and-evidence blocker。 |
| P4-11 R1 下一发布前 blocker 切片选择 after Prism report archive preflight | 发布前路线与授权边界 | 已完成 | P0 | P4-10 收口后，已由 Claude Code 与 Kimi 评审剩余 R1 blocker，并选定下一条安全小切片：Prism report archive copy-first / alias-first migration planning；本项只完成路线选择与锚点登记，不执行物理迁移、不清理证据、不关闭 blocker。 |
| P4-12 R1 Prism report archive copy-first / alias-first migration planning | 发布前路线与授权边界 | 已完成 | P0 | 已基于 P4-11 路线评审产出 Prism report archive 的 plan-only 迁移清单、旧锚点兼容要求、回滚方案与验证清单；本项未执行物理复制、移动、删除、旧锚点退休或 raw evidence cleanup。 |
| P4-13 R1 Prism report archive copy-first apply readiness / rehearsal | 发布前路线与授权边界 | 已完成 | P0 | 已基于 P4-12 plan 完成 Prism report archive 的 apply readiness / rehearsal：临时目录复制演练、checksum、archive index 草案、alias 兼容、包面排除和回滚门已可机器检查；本项未执行真实归档复制、旧锚点退休或 raw evidence cleanup。 |
| P4-14 R1 下一发布前 blocker 切片选择 after Prism report archive apply readiness | 发布前路线与授权边界 | 已完成 | P0 | P4-14 已完成：Claude Code 建议 live copy-first apply，Kimi 建议先做 churn/freeze guard；Cap 采纳保守路径，选定 P4-15 先稳定报告归档账本漂移，不执行 live apply、旧锚点退休、raw evidence cleanup 或 release。 |
| P4-15 R1 Prism report archive churn/freeze guard | 发布前路线与授权边界 | 已完成 | P0 | P4-15 已完成：Prism report archive 已从实时目录扫描改为冻结迁移集合 + 后冻结正式报告登记，copy-first plan、apply readiness、index 与包面候选计数不再被本轮审查报告反复扰动。 |
| P4-16 R1 Prism report archive live copy-first apply after freeze guard | 发布前路线与授权边界 | 待推进 | P0 | P4-15 收口后的下一安全切片：基于已冻结的报告归档集合推进 live copy-first apply，并证明旧锚点、索引、包面排除、回滚路径和 post-freeze 报告登记仍一致；本项不退休旧锚点、不清理 raw evidence、不执行正式发布动作。 |

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

这条 **framework-upgrade 长期路线本身已经完成**。
也就是说，阶段 0 到阶段 5 的 backlog 条目都已经收口到脚本、gate、validator、docs 导航或诊断链里，不再存在“下一批继续做阶段 3 / 4”这种说法。

现在真正剩下的，已经不是 backlog 本体，而是 backlog 之外的四类后续动作：

1. **当前 live task 的收尾账面**
   当前 `.dev-task.md` 对应的 confirmed hash 若仍有 `pending closure`，要继续走 review / validator / notify 链，把“当前任务已 clean”这句话真正做实。

2. **formal Prism 新运行是否真的归档**
   历史 formal Prism 报告存在，不等于当前任务已经形成新的 quorum。后续若要补 formal Prism，必须按 `prism/runs` + `prism/reports` 协议真实归档。

3. **历史完整用户项目 E2E 队列**
   `loom/test-reports/pending-validations.md` 里的条目属于另一条长期验证线，它们不再算 framework-upgrade backlog 未完成项，但仍是独立 backlog。

4. **宿主硬边界债务**
   像“主 Agent 回复前 reply-veto”这类能力，不是再做一轮 repo 内治理就能补齐，而要等宿主暴露更强控制点，或另起 wrapper / host 适配 tranche。

简单说：**framework-upgrade 已完成；后续工作转入 closeout、Prism、历史 E2E 和宿主边界治理四条独立后续线。**

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

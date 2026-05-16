# 任务完成报告：Human Communication And Feishu Noise Hardening

**报告日期**：2026-04-29
**执行者**：Cap（Codex.app）
**报告版本**：v0.2

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已把终端中途汇报与飞书节点通知统一成同一套人类可读状态面，并把 SessionEnd 内部审核缺口改为默认只落账、不刷飞书。
- 详情：新增了 human communication policy、状态面 formatter、机器检查器和 acceptance 用例；飞书 formatter 现在会输出“人工协助、阻塞状态、下一步可直接开始、任务全景图、当前位置”等字段。旧 Claude Stop hook 的自动通知路径被降为本地状态卫生提醒，不再绕过正式通知策略。

### 0.2 上一步完成的是

- 上一步完成的是：完成 P3-1 检索阈值门禁后，用户指出中途汇报缺少固定状态面，且飞书在 SessionEnd 内部审核失败时多次发送干扰性通知。

### 0.3 下一步计划做的是

- 下一步计划做的是：提交本轮变更并执行 repo-owned closeout receipt；在 receipt 生成前，本报告不声明正式完成。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：立项与追踪恢复 -> 状态面与飞书降噪实现 -> 目标回归 -> Prism 独立验收 -> closeout receipt。
- 当前所在位置：Prism 独立验收与全局回归已通过；正在进入提交和 closeout receipt 节点。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，有需要我人工审核的地方吗？另外，我发现你每次中途汇报的内容，好像不是按照模版来的，当然我觉得现在这种内容格式也能读懂，但是你最好结合之前的模版（我记得是有的），重新再优化一下内容格式，至少你得告诉我要不要提供人工协助、下一步可以直接开始还是有什么阻塞、任务全景图是什么、当前在哪一个节点了，对吧？
>
> 另外，我发现飞书的通知不仅仅在最终完成后、你中断并向我通知时才发通知，而是中途会陆续发好几次“Layer B审核失败”的通知，这样极度干扰我通过飞书通知来验收你工作结果的动作。还有，飞书通知的内容格式和刚才让你优化报告内容格式保持一致，现在的飞书通知内容有些杂乱，可用信息有限。

### 1.2 触发背景

本轮问题不是单纯“消息文案不好看”，而是 RedCap 的人类可见状态面没有被机器约束，飞书通知也把内部审计缺口当成面向 Norven 的干扰性告警。用户需要通过飞书判断节点结果，但多次“Layer B审核失败”会把真正的节点汇报淹没。此任务因此同时修复终端汇报字段、飞书格式和内部 audit gap 的默认触发策略。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 回答当前是否需要人工审核，并优化中途汇报与飞书通知的格式/触发时机。 |
| 已覆盖 | 新增状态面策略、formatter、检查器、acceptance；收敛 SessionEnd 内部审核失败通知噪声；旧 Claude Stop hook 不再绕过策略发通知。 |
| 未覆盖/延期 | 不重做所有历史报告，不改变飞书 profile / secret，不改变 closeout receipt 的真实性要求。 |
| 用户可见边界 | 真正需要人工决策时仍可发送 manual-intervention；内部审核缺口默认只进入 pending closure / ledger / diagnostics。 |
| 后续路径 | closeout receipt 通过后，本任务才可正式收口。 |

---

## 二、方案讨论

### 2.1 问题分析

Q1 的根因是终端中途汇报没有一个机器可检查的最小字段集合，导致每次靠 Agent 自由发挥。Q2 的根因是飞书通道承担了两种不该混在一起的职责：节点汇报和内部控制面审计日志。正确做法是让人类可见通知只表达“现在到哪了、是否要人介入、下一步能不能继续”，而把可由 Cap 自修复的内部 audit gap 留在账本与诊断面。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 只改口头汇报 | 以后 Cap 自觉带上人工协助/阻塞/下一步字段 | 改动小 | 无法对抗长任务稀释，无法回归 |
| Q1 | 策略 + formatter + checker | 用 policy 定义字段，用 formatter 渲染，用 checker 接入 spec/diagnose/acceptance | 可复验、可复活、可防回归 | 需要新增少量控制面文件 |
| Q2 | 保留所有审核失败飞书 | 继续把 SessionEnd audit gap 发给 Norven | 风险可见 | 噪声巨大，误把内部可修复缺口当成人工介入 |
| Q2 | 内部 gap 默认落账 | 内部审核缺口只写 pending closure / ledger / diagnostics，只有 true manual-intervention 才发飞书 | 低噪、职责清楚 | 需要确保诊断和 receipt 仍 fail-closed |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 策略 + formatter + checker | 用户要求的是稳定模板，不是一次性文案；必须进机器检查链。 | CAP_DECIDE |
| Q2 | 内部 gap 默认落账 | 飞书应服务节点验收和真实人工介入；内部审计失败不能刷屏干扰验收。 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `references/human-communication-policy.json` | 新建 | 定义终端汇报与飞书通知共享的人类状态面字段和噪声边界。 |
| `compass/tools/redcap-status-report-format.py` / `.sh` | 新建 | 渲染固定字段状态面，供中途汇报和后续节点报告复用。 |
| `compass/tools/redcap-human-communication-check.py` / `.sh` | 新建 | 检查状态面字段、飞书 formatter 字段、SessionEnd audit-gap 默认静默、旧 hook 静默。 |
| `compass/tools/redcap-notify-format.sh` | 修改 | 飞书 node-report message 复用状态面字段，并从任务报告抽取 0.1-0.4 摘要。 |
| `compass/tools/redcap-layerB-session-end.sh` | 修改 | 增加 `REDCAP_SESSION_END_NOTIFY_AUDIT_GAP` 显式开关，内部 audit gap 默认不发飞书。 |
| `compass/tools/redcap-claude-hook-stop.sh` | 修改 | 旧 Stop hook 改为 notification-muted legacy hygiene，不再发送自动飞书提醒。 |
| `references/feishu-notification-policy.json` | 修改 | 补充 internal audit gap 默认 ledger-only，明确节点汇报/人工介入两类事件。 |
| `compass/tools/redcap-feishu-notification-policy-check.py` | 修改 | 校验 SessionEnd audit-gap guard、旧 hook 静默和飞书状态面字段。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增 `human-communication-check` acceptance，并纳入 all。 |
| `compass/tools/redcap-spec-check.sh` / `redcap-diagnose.sh` | 修改 | 把 human communication checker 接入全局检查链。 |
| `references/execution-guarantees.json` | 修改 | 新增 human-communication-surface 执行保障登记。 |
| `references/file-lookup-dictionary.md` / `.json` | 修改 | 把新增状态面和检查入口纳入文件字典。 |
| `compass/knowledge/explore-notes.md` | 修改 | 归档上一轮 stale explore note，恢复 tracking-health 前置条件。 |

### 3.2 技术实现要点

这次把“人类可读状态面”定义为一组固定字段，而不是某个自然语言模板。终端中途汇报可以直接用 formatter 的结构，飞书通知则从任务报告的 0.1-0.4 摘要抽取同一套语义，避免两个通道各说各话。

SessionEnd 的 audit gap 仍会进入 pending closure / ledger / diagnostics，因此不会削弱 RedCap 的 fail-closed 保护；改变的是默认不再把这类内部控制面信号推送到飞书。只有设置 `REDCAP_SESSION_END_NOTIFY_AUDIT_GAP=1` 且确认为真实人工介入阻塞时，才允许走 manual-intervention 通道。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| 人类状态面 | `references/human-communication-policy.json` | 给 Norven 看的最小状态卡片：是否要人工协助、是否阻塞、下一步能不能开始、全景图和当前位置。 |
| formatter | `compass/tools/redcap-status-report-format.py` / `redcap-notify-format.sh` | 把同一套状态信息渲染给终端或飞书，避免两个渠道格式漂移。 |
| internal audit gap | `compass/tools/redcap-layerB-session-end.sh` | SessionEnd 发现的内部收口缺口；它应该先由 RedCap 自己记录、诊断和修复，不默认打扰 Norven。 |
| notification-muted legacy hook | `compass/tools/redcap-claude-hook-stop.sh` | 旧 Claude Stop hook 只保留本地状态卫生提醒，不再拥有官方飞书发送权。 |

### 3.3 关联变更

本轮触发了文件字典、执行保障 registry、spec-check、diagnose 和 acceptance 的联动更新。`compass/knowledge/explore-notes.md` 中上一轮遗留 active 记录被归档，否则 tracking-health 会把这次任务卡在“旧探讨未沉淀”的状态。

---

## 四、人工审核要点

> 以下是 Norven 需要重点确认的内容，其他部分 Cap 已自行验证。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无强制人工审核项 | 当前任务不需要 Norven 做代码或策略决策；如果后续真实飞书收不到节点汇报，那属于外部 profile 可用性问题，应另按通知通道排障。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| Python 语法检查 | `python3 -m py_compile compass/tools/redcap-human-communication-check.py compass/tools/redcap-status-report-format.py compass/tools/redcap-feishu-notification-policy-check.py` | 通过 |
| Shell 语法检查 | `bash -n compass/tools/redcap-multi-session-acceptance.sh compass/tools/redcap-layerB-session-end.sh compass/tools/redcap-claude-hook-stop.sh compass/tools/redcap-status-report-format.sh compass/tools/redcap-human-communication-check.sh compass/tools/redcap-notify-format.sh` | 通过 |
| 人类状态面检查 | `bash compass/tools/redcap-human-communication-check.sh` | 通过：`HUMAN_COMMUNICATION_OK` |
| 飞书策略检查 | `bash compass/tools/redcap-feishu-notification-policy-check.sh` | 通过：`FEISHU_NOTIFICATION_POLICY_OK` |
| 文件字典检查 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过：`FILE_LOOKUP_DICTIONARY_OK required_paths=141` |
| acceptance：状态面 | `bash compass/tools/redcap-multi-session-acceptance.sh human-communication-check` | 通过 |
| acceptance：飞书禁用旧 transport/profile | `bash compass/tools/redcap-multi-session-acceptance.sh feishu-webhook-notify` | 通过 |
| acceptance：SessionEnd closeout runtime 不重复成功通知 | `bash compass/tools/redcap-multi-session-acceptance.sh session-end-success-notify-skip-for-closeout-runtime` | 通过 |
| acceptance：SessionEnd clear 后成功通知路径 | `bash compass/tools/redcap-multi-session-acceptance.sh session-end-success-notify-after-clear` | 通过 |
| Prism acceptance 绑定 | `bash compass/tools/redcap-prism-acceptance-bind.sh --run-id 20260429-human-communication-feishu-noise-hardening --task-file .dev-task.md` | 通过 |
| Prism acceptance 检查 | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过：2 个 provider、2 个模型家族、0 blocker |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 无强制人工验证项；最终 closeout 会走 RedCap 官方节点汇报通道，若外部飞书账号或网络不可用，会按现有 fail-closed 策略记录。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已清；待 closeout runtime 同步 |
| 棱镜验收 | 通过：Kimi + Claude Code 两路 review，0 blocker |
| closeout summary | 无 |
| closeout receipt | 无 |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是，核心代码和目标回归已完成 |
| 已自检 | 是，新增 checker 与目标 acceptance 已通过 |
| 已独立验收 | 是，Prism acceptance 已通过 |
| 已正式完成 | 否，receipt 尚未生成 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 全历史飞书消息格式回填 | 历史消息无法改写；本轮只保证后续生成路径。 | P2 |

### 6.2 触发的新问题

执行中确认旧 Claude Stop hook 仍保留了本地 explore-notes 提醒，这不应再进入飞书通道；本轮已将其限制为 stderr 本地提醒。未发现需要另开任务的 P0/P1 新问题。

### 6.3 推荐的下一步行动

1. 提交本轮变更。
2. 执行 `./closeout-cap.sh complete --host codex` 生成 receipt。
3. 复验 closeout status / diagnose / git status。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-139 | 飞书不是内部审计日志 | 节点通知和内部 audit gap 必须分层：前者给人验收，后者进账本和诊断。 |

### 7.2 流程改进建议

后续所有面向 Norven 的中途汇报都应至少包含“人工协助、阻塞状态、下一步可直接开始、任务全景图、当前位置”。如果是需要打断的 manual-intervention，也要先说明为什么这个问题无法由 RedCap 自行推断或修复。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| EVO-2026-04-29-001 | 用户指出飞书噪声和中途汇报状态面缺失 | promoted | `references/human-communication-policy.json`、`compass/tools/redcap-human-communication-check.py` |

---

## 八、附录

### 附录 A：Commits

```text
待提交；当前任务尚未生成 commit。
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| review | Human communication / Feishu noise hardening | Kimi pass，0 blocker | `prism/runs/20260429-human-communication-feishu-noise-hardening/collect/kimi-reviewer/parsed.json` |
| review | Human communication / Feishu noise hardening | Claude Code pass，0 blocker | `prism/runs/20260429-human-communication-feishu-noise-hardening/collect/claude-reviewer/parsed.json` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 策略文档：`references/human-communication-policy.json`、`references/feishu-notification-policy.json`
- 回归入口：`compass/tools/redcap-human-communication-check.sh`、`compass/tools/redcap-multi-session-acceptance.sh human-communication-check`

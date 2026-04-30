# 任务完成报告：飞书双向链路与 overlay handoff P0 收口

**报告日期**：2026-04-16
**执行者**：Cap（Copilot CLI / GPT-5.4）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 的飞书主链已经从“webhook + 多维表格”切到“`lark-cli + bot + 固定单聊 + 窗口式接收 + 最小待处理入口`”，并把本次 `brainstorming → writing-plans` 混入主流程的问题按 P0 红线收口。
- 详情：`compass/tools/feishu-notifier.py` 现在负责 bot 单聊发送、等待答复窗口、任务完成回访窗口、待处理入口与补扫历史；`redcap-on-complete.sh`、`redcap-layerB-session-end.sh`、`redcap-layerB-session-start.sh` 已接入这条新链。与此同时，`SKILL.md`、`compass/CONTRIBUTING.md`、`ARCHITECTURE.md`、`references/agent-constraints.md` 明确补上了“overlay skill 的宿主下游 handoff 不得阻断 RedCap-native 主流程”，并新增回归验证。

### 0.2 上一步完成的是

- 上一步完成的是：飞书双向交流方案的 design / spec 已经完成并过审，问题边界、窗口模型、待处理入口、CLI 主控制面原则都已经锁定；本轮是在这个设计基础上把代码、规范、回归与本机配置全部接起来。

### 0.3 下一步计划做的是

- 下一步计划做的是：无必须收尾项；如果回到长期路线主线，优先继续 `F2 规范到 gate 的翻译链`，然后推进 `A3 + F3`。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：backlog / D1 / 模板链收口 → 飞书双向链路落地 → overlay downstream handoff P0 收口 → 回到 F2 / A3 / F3 主线。
- 当前所在位置：飞书链路与 overlay handoff P0 已收口，`.dev-task.md` 已回到 `task-complete`；长期路线的下一焦点重新回到 `F2`。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 1要做，但是2不是补一个，而是把现有的飞书发送逻辑改造成demo里的实现，因为这个里面的飞书机器人开通权限，并可以发送消息，我能收到通知

> 做成可以用飞书与我交流的风格，你可以发通知给我，我也能用飞书回消息给你。但是这个要看能否支持和实现，demo里不知道有没有文档链接。如果调研后发现不能实现，请告诉我

> 多维表格的沟通方式很低效，我需要去建立表格，编辑表格，不是一个良好的人类通信模式，当时的方案算是临时折中的，现在既然有更优质的方案，建议直接一步到位。

> 记录一个需求“把本次skill混乱的问题当作P0高危红线bug接触，并且要回归通过验证”，你先继续完成剩下任务步骤

> （飞书回复）收到，另外，请把发送人写成Cap

### 1.2 触发背景

之前 RedCap 的飞书链路虽然“能用过”，但核心仍是 webhook + 多维表格，用户已经明确觉得交互形态很差，而且最近完成态通知也没有稳定到达。  
同时，我在设计阶段错误地把宿主通用 `brainstorming` 的默认后继链当成了 RedCap 自己的流程，甚至一度把 `writing-plans` 缺失说成 blocker，这直接触发了用户对控制面混乱的 P0 质疑。  
因此，本轮必须同时解决两个问题：一是把飞书链路切到真实可达、能双向接收的 bot 单聊通道；二是把 overlay skill 的从属边界补成更硬的 repo-owned 规则与回归。

---

## 二、方案讨论

### 2.1 问题分析

飞书问题的本质不是“发一条消息”这么简单。  
如果只把 webhook 改成 `lark-cli`，完成通知也许能收到，但等待答复、任务完成回访、窗口外消息、待处理提醒这些链路还是断的；而如果直接追求“实时聊天”，又会落到事件订阅 / 回调服务 / 常驻监听这类明显超出本轮范围的重方案。

overlay P0 的本质也不是“某个 skill 没装”。  
真正的问题是：宿主 overlay skill 的默认工作流越权了，把本应回到 RedCap-native `.dev-task.md` / `plan.md` / PM Gate 的后续动作，错误升级成了必须依赖宿主下游 skill 的强制步骤。这个问题无法靠修改 shared host skill 本体来解决，只能在 RedCap 自己可拥有的 repo-owned 边界里补规则、补回归。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| 飞书链路 | 选项 A | 只修完成通知，把 webhook 改到 `lark-cli` | 改动小 | 双向协作、待处理、回访窗口都缺失 |
| 飞书链路 | 选项 B | 切到 bot 单聊 + 窗口式接收 + 最小待处理入口 | 与用户目标一致，边界清晰，能一步替代多维表格 | 需要补窗口状态、补扫历史、回归 |
| 飞书链路 | 选项 C | 直接做实时事件订阅 / 长连接桥 | 交互最像即时聊天 | 明显超出当前 repo-owned 范围 |
| overlay P0 | 选项 A | 只补文档解释 | 成本最低 | 不能防止再次把宿主下游 handoff 误判成 blocker |
| overlay P0 | 选项 B | 去改 shared host skill 本体 | 表面触发点最直接 | 违反宿主资产边界，不是修 RedCap 自身 |
| overlay P0 | 选项 C | 在 RedCap 自身补规则、补回归、补诚实降级口径 | 符合 repo-owned 边界，也能长期保留 | 不能物理改造宿主层工具行为 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| 飞书链路 | 选项 B | 这是唯一同时满足“真实可达 + 半实时 + 不常驻监听 + 待处理入口”的方案，也能一步替换掉多维表格主链 | NORVEN_DECIDE + CAP_DECIDE |
| overlay P0 | 选项 C | 共享宿主 skill 不是 RedCap 的 patch surface；正确修复面只能是 RedCap 自己的规范、控制面与回归 | NORVEN_DECIDE + CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `compass/tools/feishu-notifier.py` | 重写 | 主链改为 bot 单聊、窗口状态、待处理入口、补扫历史 |
| `compass/tools/redcap-on-complete.sh` | 修改 | 完成通知默认打开 `followup` 回访窗口 |
| `compass/tools/redcap-layerB-session-end.sh` | 修改 | SessionEnd 成功通知默认打开 `followup` 回访窗口 |
| `compass/tools/redcap-layerB-session-start.sh` | 修改 | SessionStart 会补扫飞书历史并提醒待处理消息 |
| `compass/tools/redcap-notify-format.sh` | 修改 | 飞书通知头部固定写 `发送人：Cap` |
| `SKILL.md` | 修改 | 明确 overlay skill 的宿主下游 handoff 不能阻断主流程；同步飞书新 CLI 接口 |
| `compass/CONTRIBUTING.md` | 修改 | 同步飞书新接口与 overlay handoff 约束 |
| `ARCHITECTURE.md` | 修改 | 在 truth surface / governance 口径中补充 downstream handoff 边界 |
| `references/agent-constraints.md` | 修改 | 子 Agent 约束新增“缺少宿主下游 skill 不是 blocker” |
| `loom/dispatcher/state-machine.md` | 修改 | 把 `feishu_record_id` 口径改为窗口 ID，同步新接收模型 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增 `feishu-duplex-window-queue` 与 `overlay-skill-handoff-stays-native` 回归 |
| `.dev-task.md` | 修改 | 追加 U31/U32/U33 与 Q19/Q20/Q21，并把完成标准切到本轮目标 |
| `plan.md` | 修改 | 宿主镜像同步到完成态 |
| `compass/docs/task-reports/2026-04-16-feishu-duplex-and-overlay-p0.md` | 新建 | 归档本轮终局报告 |

### 3.2 技术实现要点

第一，飞书主链不再依赖多维表格。  
`compass/tools/feishu-notifier.py` 现在直接通过 `lark-cli` 调固定单聊：`notify` 用于单向发送，`ask / resume / confirm` 用于前台阻塞等待回复，`pending-scan / pending-list / pending-promote / pending-dismiss` 用于窗口外消息和待处理入口管理。`FEISHU_RECORD_ID` 仍然保留，但它现在表示“等待窗口 ID”，不是旧的表格记录 ID。

第二，窗口模型被拆成两类。  
“等待答复窗口”用于当前真的卡在用户输入上；脚本在窗口期内按 10 秒 / 60 秒节奏轮询，命中用户回复后就关闭窗口并把内容返回给调用方。“任务完成回访窗口”用于 on-complete / session-end 收尾后给用户保留短时 follow-up 入口；这类窗口不会偷偷恢复执行，而是把回复记入待处理入口，并在下次 CLI 会话提醒。

第三，待处理入口是最小闭环，而不是第二套总账。  
窗口外消息、或回访窗口里收到但当前没有活跃控制面的消息，会进入 `compass/.workflow/feishu/` 下的本地状态文件。`redcap-layerB-session-start.sh` 每次启动都会先 `pending-scan`，再把未处理项简短提醒到 CLI；真正要不要继续展开，仍然回到 RedCap-native 主控制面，而不是让飞书自己抢执行权。

第四，overlay P0 修的是“主从关系”，不是“宿主 skill 缺失”。  
`SKILL.md`、`compass/CONTRIBUTING.md`、`ARCHITECTURE.md`、`references/agent-constraints.md` 现在都明确写出：宿主通用 skill 如果自带“设计完成后继续交给 writing-plans / planning”的默认后继链，Cap 必须在设计产出落盘后回到 RedCap-native `.dev-task.md` / `plan.md` / PM Gate 继续；缺少宿主下游 skill 不是合法 blocker。这样，即使未来再叠加宿主 overlay，也不会再把这类 handoff 误说成 RedCap 主流程的一部分。

第五，用户的新飞书回执也被真正吃进实现。  
真实回执“请把发送人写成 Cap”已经落到 `compass/tools/redcap-notify-format.sh`，现在所有完成态飞书通知头部都会直接写 `发送人：Cap`，同时保留 `来源` 字段说明是 on-complete 还是 session-end。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| 等待答复窗口 | `compass/tools/feishu-notifier.py` | 指当前任务真的卡在“等你回答”，脚本会持续轮询这段时间内的新飞书回复 |
| 任务完成回访窗口 | `compass/tools/feishu-notifier.py` + `redcap-on-complete.sh` / `redcap-layerB-session-end.sh` | 指任务已经做完，但给你留一个短时入口，允许你直接回“继续下一步”等 follow-up |
| 待处理入口 | `compass/.workflow/feishu/*` + `pending-scan/pending-list` | 指那些没命中有效窗口、但也不能静默丢掉的飞书消息会先记在这里，等下次会话提醒 |
| overlay downstream handoff | `SKILL.md` / `compass/CONTRIBUTING.md` / `ARCHITECTURE.md` | 指宿主通用 skill 自带的“下一步交给别的宿主 skill”默认动作；现在明确不能反向接管 RedCap-native 主流程 |

### 3.3 关联变更

为了让这次飞书改造不只停在脚本本身，本轮还同步更新了规范、伪代码和回归脚本；否则最容易出现“实现已经换成窗口式接收，但 SKILL / CONTRIBUTING / dispatcher 伪代码还在写多维表格”的断链。  
另外，本机 `compass/tools/feishu-config.json` 已切到新的 `lark_cli_*` 配置项，确保这台机器上的真实 RedCap 收尾入口会直接走新通道。

---

## 四、人工审核要点

> ⚠️ 以下是 Norven 需要重点确认的内容，其他部分 Cap 已自行验证。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无必须人工裁决项；若要抽查，优先看 `compass/tools/feishu-notifier.py` 和 `compass/tools/redcap-multi-session-acceptance.sh` 的两条新回归 | 本轮没有依赖你手动操作才能闭环的 blocker | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 脚本语法检查 | `python3 -m py_compile compass/tools/feishu-notifier.py && bash -n compass/tools/redcap-layerB-session-start.sh && bash -n compass/tools/redcap-on-complete.sh && bash -n compass/tools/redcap-layerB-session-end.sh && bash -n compass/tools/redcap-multi-session-acceptance.sh` | ✅ |
| 飞书本机通道校验 | `python3 compass/tools/feishu-notifier.py setup` | ✅ |
| 真实飞书发送 | `python3 compass/tools/feishu-notifier.py notify 'RedCap 飞书主链已切换到 bot 单聊窗口方案。' --project redcap --window-type followup` | ✅ |
| 新增飞书回归 | `bash compass/tools/redcap-multi-session-acceptance.sh feishu-duplex-window-queue` | ✅ |
| 新增 overlay 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh overlay-skill-handoff-stays-native` | ✅ |
| spec / registry 一致性 | `bash compass/tools/redcap-spec-check.sh "$PWD"` | ✅ |
| 全量 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | ✅ |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [x] 无必须人工验证项；当前 repo-owned 改动已经全部在本地自动验证通过。

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| CLI 本地输入优先的“物理监控”仍不可能只靠 repo 脚本实现 | 宿主没有提供“用户在 CLI 发了下一条消息”这种可被仓库脚本订阅的事件；当前已用“回访窗口只记待处理、不自动恢复”避开主要冲突，并提供 `close-window` 兜底命令 | P2 |
| 更广范围的 F2 / A3 / F3 治理硬化仍未推进 | 这超出本轮飞书与 overlay P0 收口范围 | P1 |

### 6.2 触发的新问题

本轮没有留下新的未处理 blocker。  
唯一新增要求是飞书回执“请把发送人写成 Cap”，该要求已经在本轮内吸收并核销。

### 6.3 推荐的下一步行动

1. 回到 `F2` 主线，继续把 hook / lesson / contract / 状态机等治理规范翻译成 gate。
2. 再推进 `A3 + F3`，把三轨评审门和治理硬化补成更可执行的运行链。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-68 | 宿主 overlay 的下游 handoff 也要算越权面 | 不仅 ask_user/approval 会越权，连“设计完成后必须继续交给宿主 planning skill”这类默认后继链也会越权；缺少宿主下游 skill 不是合法 blocker |
| L-69 | 飞书回执本身也要进 canonical ledger | 既然飞书已经变成正式输入桥，来自飞书的新增要求也必须像 CLI 对话一样写进 `.dev-task.md` 并在本轮内处理或核销 |

### 7.2 流程改进建议

以后凡是开启真实回访窗口，都应在任务结束前看一眼待处理入口是否有新增回执；如果有，就应像这次一样直接吸收到 `.dev-task.md`，不要让它停留在本地 runtime 状态里。

---

## 八、附录

### 附录 A：Commits

```text
（本轮改动当前仍在工作区，尚未形成新的 commit）
```

### 附录 B：棱镜调用记录（如有）

本轮没有新增独立 Prism 报告；主要依赖 repo-owned 回归与全量 acceptance 收口。

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md` 中的 `U11-U33`
- 设计文档：`compass/docs/specs/2026-04-15-feishu-duplex-communication-design.md`
- 终局账本：`.dev-task.md`

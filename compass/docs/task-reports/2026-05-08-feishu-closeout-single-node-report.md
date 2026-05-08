# 任务完成报告：飞书完成通知单出口收敛

**报告日期**：2026-05-08  
**执行者**：Cap（Codex.app）  
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap Layer B 完成通知已从“双出口”收敛成 closeout runtime 单出口。
- 详情：closeout runtime 调用 `on-complete` 时会强制设置 `REDCAP_SKIP_FEISHU=1`，避免提前发送；receipt 写入后，再由 closeout runtime 统一发送一次 `node-report`。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2i 已新增 package-visible 的最小 runtime 物理布局，并完成 closeout receipt。

### 0.3 下一步计划做的是

- 下一步计划做的是：确认飞书单出口修复稳定后，再回到 RedCap 父任务线；public release 仍需单独 release task。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：通知噪声定位 → 完成通知单出口 → targeted 回归 → closeout receipt → 回到父任务线。
- 当前所在位置：P2-9 `redcap-feishu-closeout-single-node-report`，这是人类可见节点通知质量修复，不是 npm 发布任务。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮只修 RedCap 自己的通知出口和回归用例，不改变飞书账号、发布策略或人工决策边界。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，再执行下一步之前，先解决一个问题：我发现每次你任务完成的时候，不是在你准备汇报的时候（但其实已经接近了，每次发飞书通知，我看电脑，发现你还在执行，但很快就执行完毕了），并且我会收到2条飞书消息

### 1.2 触发背景

检查 `compass/.workflow/feishu/recent-notifications.json` 后确认，上一次任务收尾时确实有两条不同内容的 `node-report`：一条来自 `on-complete`，另一条来自 closeout 后的手工节点汇报。这不是飞书平台重复推送，而是 RedCap 生产路径有两个完成通知出口。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | exact |
| 已覆盖 | 修掉完成节点的重复 node-report，并把发送时机推到 receipt 生成之后。 |
| 延期 | 不重构飞书双向通信、不改 lark-cli profile、不处理飞书平台自身延迟。 |
| 用户可见边界 | 未来最终终端回复仍可能晚于飞书几秒，因为 Agent 还要写回对话；但同一完成节点不应再收到两条 RedCap node-report。 |

---

## 二、方案讨论

### 2.1 问题分析

`closeout-cap.sh` 会调用统一 closeout runtime，而 closeout runtime 内部又调用 `redcap-on-complete.sh`。旧逻辑里 `on-complete` 会自己发送一次“Layer B 收尾完成”；如果主 Agent 后续又按节点汇报再发一次，就会形成两条不同内容、无法被简单去重的飞书消息。

### 2.2 决策结果

| 问题 | 决策 | 理由 |
|---|---|---|
| 谁发送最终完成通知 | closeout runtime | 它最接近 receipt 真相源，可以避免 on-complete 过早声明完成。 |
| on-complete 怎么处理 | closeout 内部静音，standalone 保持兼容 | 既修复重复，也不破坏旧调用路径。 |
| 失败如何处理 | notify 失败进入 pending closure / audit | 通知失败不能被伪装成完成。 |

---

## 三、落地结果

### 3.1 完成内容

- closeout runtime 调用 `on-complete` 时设置 `REDCAP_SKIP_FEISHU=1`。
- closeout runtime 在 receipt / summary 写入后构建人类可读 node-report，并调用同一个 `feishu-notifier.py` 单通道发送。
- 若 closeout node-report 失败，会写入 `notify,closeout-runtime` pending closure 和 audit，而不是静默吞掉。
- 飞书策略与人类沟通策略已更新为：Layer B final node-report 由 closeout runtime 拥有。
- acceptance 加入回归：验证 `on-complete skip=1`、closeout 只调用一次 notifier、通知发生时 receipt/summary 已存在。

### 3.2 人话解释

以前像是“验收员说完成了”和“总控台说完成了”各给你发了一次消息。现在改成只有总控台发：验收员仍然工作，但在总控台流程里不再喊话；总控台等收据写好后，再发一条最终节点汇报。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| on-complete | `compass/tools/redcap-on-complete.sh` | 原来的“任务完成后收尾动作”，现在在 closeout 流程里只做检查和清理，不负责最终飞书喊话。 |
| closeout runtime | `compass/tools/redcap-layerb-closeout-runtime.py` | Layer B 收尾总控台，负责承诺账本、验收、receipt 和最终节点通知。 |
| node-report | `feishu-notifier.py notify --window-type node-report` | 给 Norven 的节点汇报消息，只应该在真正完成一个可见节点时发送一次。 |
| receipt | closeout runtime 的收口收据 | 机器可审计的“这条任务正式完成了”的证明，飞书最终通知必须在它生成后发送。 |

---

## 四、人工审核要点

- 目前不需要 Norven 人工介入。
- 这次不改变飞书账号，仍只允许 `cli_a9579f5b12219bb5`。
- 这次不恢复 SessionEnd 成功通知，也不允许内部审计 gap 自动刷飞书。
- 完成 closeout 时仍会有一条飞书 node-report；区别是只保留一条，并且来自 closeout runtime。

---

## 五、验证结果

### 5.1 已通过验证

| 验证项 | 结果 |
|---|---|
| Python 编译检查 | 通过 |
| Bash 语法检查 | 通过 |
| closeout runtime receipt 用例 | 通过：on-complete 被静音，closeout notifier 调用一次 |
| SessionEnd 成功通知顺序用例 | 通过 |
| SessionEnd closeout 静音用例 | 通过 |
| 飞书策略检查 | 通过 |

### 5.2 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| 执行承诺账本 | closeout 时核对 |
| closeout receipt | closeout 时生成 |
| rescue audit | 如有则记录在 runtime 审计路径 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | targeted acceptance 已覆盖 |
| 已正式完成 | 否；等待最终 spec-check、diagnose、commit 与 closeout receipt |

---

## 六、遗留问题与下一步

| 问题 | 当前边界 | 下一步 |
|---|---|---|
| 飞书到终端最终回复之间仍有几秒差 | 这是宿主对话写回延迟，不是重复通知 | 最终汇报不再额外手工发第二条飞书 |
| 飞书平台或 lark-cli 自身失败 | RedCap 只能 fail-closed 并写 pending/audit | 若真实失败，再单独修 lark-cli 登录态或 profile |
| public release | 不在本轮范围 | 回到父任务线时另开 release task |

---

## 七、经验沉淀

| 维度 | 内容 |
|---|---|
| 问题源 | 完成通知被分散在 `on-complete` 和主 Agent 手工汇报两个出口，且消息内容不同，短窗口去重无法识别为同一节点。 |
| 解决方案 | 让 closeout runtime 独占 Layer B final node-report，并在内部调用 on-complete 时设置 `REDCAP_SKIP_FEISHU=1`。 |
| 最后效果 | 完成通知从“双出口、可重复”变为“closeout receipt 后单出口、可回归验证”。 |

### 7.3 Evolution Factory 候选处理

- 处理：no-promote。
- 理由：这是已有“飞书通知低噪声 / closeout runtime 单通道”经验的缺口修复，已经直接进入机制和回归；不需要新增重复 Evolution 候选。

---

## 八、附录

### 附录 A：关键文件

- `compass/tools/redcap-layerb-closeout-runtime.py`
- `compass/tools/redcap-multi-session-acceptance.sh`
- `compass/tools/redcap-feishu-notification-policy-check.py`
- `references/feishu-notification-policy.json`
- `references/human-communication-policy.json`

### 附录 B：Commits

```
待提交
```

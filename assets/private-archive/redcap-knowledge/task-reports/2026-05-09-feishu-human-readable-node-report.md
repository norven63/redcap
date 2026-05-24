# 任务完成报告：飞书节点汇报人类可读化

**报告日期**：2026-05-09  
**执行者**：Cap（Codex.app）  
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：飞书 node-report 已从“状态字段堆叠”改成更像聊天阶段汇报的六段式结构。
- 详情：飞书正文现在优先展示结论、任务位置、下一步、是否需要 Norven、阻塞状态和关键证据，不再重复输出三段路线信息。

### 0.2 上一步完成的是

- 上一步完成的是：P2-9 已把飞书完成通知从双出口收敛为 closeout runtime 单出口，并验证同一完成节点只发一条飞书。

### 0.3 下一步计划做的是

- 下一步计划做的是：确认新飞书模板稳定后，回到 RedCap 父任务线继续推进结构治理和发布前准备；public release 仍需单独 release task。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：双通知修复 → 飞书内容可读化 → 回归/棱镜验收 → closeout → 回到父任务线。
- 当前所在位置：P2-10 `redcap-feishu-human-readable-node-report`，这是人类可见汇报质量修复，不是发布任务。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮只改变飞书文本结构与对应检查，不改变飞书账号、发送通道、closeout 单出口或 manual-intervention 语义。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，你们（以后“你们”默认就是特质你+棱镜团队）现在对比一下飞书通知的内容，和之前你回到我“任务总纲是什么，当前已经完成了哪些，下一步是什么，需要我人工做什么”时的内容，哪个更加详细完整、符合人类可读性呢？

> 可以，顺便把飞书报告里的一些冗余内容也清理一下

### 1.2 触发背景

对比后确认：飞书通知字段完整，但人类阅读体验不如聊天阶段汇报。主要问题不是信息少，而是模板把路线信息重复拆成“任务全景图 / 当前位置 / 整体计划脉络图与当前位置”三块，还默认铺开提交信息，导致正文像机器状态面而不是节点总结。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 已覆盖 | 飞书 node-report 新增独立 compact 字段面，删除重复路线段落，并把提交细节降级为关键证据摘要。 |
| 延期 | 不重构终端状态面、不改飞书账号、不改变 closeout 单出口和发送时机。 |
| 用户可见边界 | 飞书仍保留必要证据链接和提交摘要，但不再把工程字段重复铺满正文。 |

---

## 二、方案讨论

### 2.1 问题分析

旧模板把终端状态面直接复用到飞书。终端状态面适合诊断和机器校验，字段细一些可以接受；但飞书是移动端节点提醒，应该让 Norven 快速判断“完成了什么、下一步是什么、是否需要我”。同一段路线信息连续出现三次，会制造阅读噪声。

### 2.2 决策结果

| 问题 | 决策 | 理由 |
|---|---|---|
| 飞书和终端是否共用字段 | 不再完全共用 | 终端保留诊断字段；飞书改用 compact 汇报字段。 |
| 路线信息如何展示 | 合并为一个“任务位置” | 既保留全局感，又避免重复三连。 |
| 提交信息如何展示 | 放进“关键证据”摘要 | 保留可追溯性，但不让 commit 清单变成主内容。 |

---

## 三、落地结果

### 3.1 完成内容

- `redcap-notify-format.sh` 的飞书正文改为：结论、任务位置、下一步、需要 Norven、阻塞状态、关键证据。
- `human-communication-policy.json` 增加 `required_feishu_fields`，把飞书字段面与终端状态面解耦。
- `redcap-human-communication-check.py` 现在会检查飞书 compact 字段，并禁止重复输出旧的路线三连与提交清单段落。
- acceptance 已覆盖新字段和去冗余要求。

### 3.2 人话解释

以前飞书像把后台仪表盘复制给你看；现在飞书更像我站在你旁边做一句阶段汇报：先说结论，再说当前在任务树哪里，接着说下一步和需不需要你，最后把证据链接放在底部。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| 飞书 node-report | `feishu-notifier.py notify --window-type node-report` | RedCap 在一个节点完成时发给 Norven 的阶段汇报。 |
| compact 字段面 | `references/human-communication-policy.json` 的 `required_feishu_fields` | 飞书专用的短汇报结构，不再照搬终端诊断字段。 |
| 终端状态面 | `redcap-status-report-format.py` / `required_status_fields` | 给终端和诊断用的完整状态字段，保留更多工程上下文。 |
| 关键证据 | 飞书模板底部的报告和提交摘要 | 让消息可追溯，但不把 commit 清单变成正文主角。 |

### 3.3 新飞书样例摘要

```text
结论：飞书 node-report 已从字段堆叠改成六段式阶段汇报。
任务位置：双通知修复 → 飞书内容可读化 → 回归/棱镜验收 → closeout。
下一步：回到 RedCap 父任务线继续推进。
需要 Norven：不需要。
阻塞状态：无。
关键证据：任务报告、提交数、最新提交。
```

---

## 四、人工审核要点

- 当前不需要 Norven 人工介入。
- 这次不会发送真实测试飞书；只在最终 closeout 时由单出口发送一条真实节点汇报。
- 若后续你觉得“任务位置”仍然偏长，可以继续收紧为一行摘要，但不影响本轮机制正确性。

---

## 五、验证结果

### 5.1 已通过验证

| 验证项 | 结果 |
|---|---|
| Bash 语法检查 | 通过 |
| Python 编译检查 | 通过 |
| 飞书格式样例渲染 | 通过，旧重复段落已删除 |
| human-communication-check | 通过 |
| acceptance: human-communication-check | 通过 |

### 5.2 最终收口验证

| 验证项 | 状态 |
|---|---|
| 棱镜独立评审 | 通过，Claude Code 与 Kimi 均无 blocker |
| spec-check / diagnose | 通过 |
| closeout receipt | 通过 |

### 5.3 closeout runtime / receipt

| 项 | 证据 |
|---|---|
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-feishu-human-readable-node-report-7cce16953330aa7aafd7b93c78111d676188939858f0b376d71584658d028fa5.json` |
| Prism acceptance | `20260509-feishu-human-readable-node-report`，2 个角色响应，无 blocker |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Claude Code 与 Kimi 均无 blocker |
| 已正式完成 | 是；已完成 commit、回归、棱镜验收与 closeout receipt |

---

## 六、遗留问题与下一步

| 问题 | 当前边界 | 下一步 |
|---|---|---|
| 终端状态面仍保留“任务全景图/当前位置” | 这是终端诊断字段，不属于飞书冗余 | 若以后要重构终端状态面，另开任务评估 |
| 飞书正文仍包含工程证据 | 保留在“关键证据”底部，避免丢失追溯能力 | 后续可按你的反馈继续压缩 |
| public release | 不在本轮范围 | 回到父任务线后另开 release task |

---

## 七、经验沉淀

| 维度 | 内容 |
|---|---|
| 问题源 | 把终端诊断状态面直接复用到飞书，导致飞书正文被重复路线字段和提交清单污染。 |
| 解决方案 | 为飞书建立独立 compact 字段面，只保留节点汇报需要的结论、位置、下一步、人工协助、阻塞和证据。 |
| 最后效果 | 飞书从“机器字段面”转向“人类阶段汇报”，同时保留机器检查，防止旧冗余模板回潮。 |

### 7.3 Evolution Factory 候选处理

- 处理：no-promote。
- 理由：这是既有“人类沟通质量保障”机制的直接修正，已经进入策略和回归，不需要新增重复候选。

---

## 八、附录

### 附录 A：关键文件

- `compass/tools/redcap-notify-format.sh`
- `compass/tools/redcap-human-communication-check.py`
- `compass/tools/redcap-multi-session-acceptance.sh`
- `references/human-communication-policy.json`

### 附录 B：Commits

```text
3efb587 fix: 优化飞书节点汇报可读性
980e35a test: 刷新飞书可读化后的 E2E 证据
```

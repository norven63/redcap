# 角色分配指南

> 棱镜的 Agent 角色分配原则。

---

## 核心原则

棱镜中的"角色"分两类：**分析视角**（描述关注什么）和**对抗职能**（描述怎么攻击）。两者组合使用，才能避免同质偏见。

- 每个 Agent 都是独立的"分析员"，视角分配在 Frame 步骤完成
- 模型选择比视角分配更重要——不同家族模型 = 不同训练偏见 = 真正独立的视角
- **对抗职能（下方三种）在 redteam/council 模式中是强制角色，不可省略**

---

## 核心对抗角色（redteam/council 前三者必须存在）

| 角色 | 职责 | System Prompt 文件 |
|------|------|-------------------|
| **挑战者（Challenger）** | 主动攻击每一个假设，找缺陷/漏洞/边界条件违反 | [`challenger/system-prompt.md`](challenger/system-prompt.md) |
| **审查员（Reviewer）** | 逐条对照规范与实现，找执行偏差和空洞承诺 | [`reviewer/system-prompt.md`](reviewer/system-prompt.md) |
| **旧错者（Historian）** | 逐条引用 lessons.md，判断本次是否重演历史错误 | [`historian/system-prompt.md`](historian/system-prompt.md) |
| **探索者（Explorer）** | 挖掘被忽视的替代方案和设计盲点（推荐第 4 席） | [`explorer/system-prompt.md`](explorer/system-prompt.md) |

挑战者 / 审查员 / 旧错者这三类角色必须由 **不同 Agent** 担任（即不同模型实例），不可合并到同一个 Agent。Explorer 为推荐补充角色，redteam 第 4 席优先使用。

**Dispatch 拼装规则**：每个角色的完整 Prompt = 角色 System Prompt + [`universal-constraints.md`](universal-constraints.md) + Frame 问题包 + 待审查材料。historian 额外追加 `compass/knowledge/lessons.md` 全文。

详见：[`redteam-prompts.md`](redteam-prompts.md)（完整设计文档含 Schema）

---

## 收敛角色（Adjudicate 阶段使用）

分析团队完成后，由以下角色将问题转化为可执行方案：

| 角色 | 职责 | 触发时机 |
|------|------|---------|
| **运筹者（Strategist）** | 接收分析团队所有发现，为每个问题设计最优解；标注 `[CAP_DECIDE]` 或 `[HUMAN_DECIDE]`；只有 `[HUMAN_DECIDE]` 问题阻塞任务等待 Norven | 分析团队全部返回后，Adjudicate 阶段启动前 |

**运筹者工作原则：**
- 最稳妥：优先选择破坏面最小的方案
- 最优雅：不用 shim/symlink 等临时补丁，一次做对
- 最合理：符合业内通用实践
- `[HUMAN_DECIDE]` 判断标准：涉及架构取舍、方向性选择、或用户使用习惯改变时才阻塞

**运筹者方案须经内部评审**：方案输出后，至少由一个分析角色（通常是 Challenger）快速挑战，无 BLOCKING 反对则采纳。

---

## 可用模型阵容（按家族分类）

| 家族 | 强力模型 | 轻量模型 | 备注 |
|------|---------|---------|------|
| Claude | claude-opus-4.6 | claude-haiku-4.5 | 本地 Copilot CLI |
| Claude | claude-sonnet-4.6 | — | 本地 Copilot CLI |
| GPT | gpt-5.4 | gpt-4.1 | 本地 Copilot CLI |
| Gemini | gemini-2.5-pro（CLI） | gemini-2.5-flash | 本地 Gemini CLI |
| Kimi | kimi-k2.5（CLI） | — | 本地 Kimi CLI（若可用） |

**redteam 三家族红线**：≥3 个不同家族（Claude + GPT + Gemini）。同家族模型共享训练偏见，无法真正独立挑战彼此假设。

---

## 推荐组合

| 场景 | 组合 | 说明 |
|------|------|------|
| 标准探索（3人） | Sonnet + Haiku + GPT-5.4 | 跨两家族 |
| 深度红队（4人） | Opus + GPT-5.4 + Gemini-Pro + Sonnet | 三家族，含三对抗角色 |
| 深度议事（4人） | Opus + Sonnet + GPT-5.4 + Gemini-Pro | 三家族，多轮收敛 |
| 复活测试（4人） | Sonnet + Haiku + GPT-5.4 + Gemini-Flash | 跨三家族 |

**GPT 模型特别提醒**：发送大文件（>1000行）前必须分段，GPT 系模型会静默截断而不报错（L-11）。

---

## 分析视角库（explore/test 模式使用）

按需从以下视角中选 3~5 个分配：

- **架构师**：可扩展性、模块边界、依赖关系
- **实践者**：落地难度、实现代价、已知坑
- **用户**：调用方体验、文档完整性、心智负担
- **批评者**：假设前提合理性、遗漏场景
- **综合者**：跨方案对比、最优路径

---

## 重要提醒

- 一个 Agent 只分配一个视角或一个对抗职能
- 所有 Agent 收到的**问题陈述完全相同**（角色/视角偏重不同）
- council 模式第一轮遵循 Dispatch Firewall，后续轮可共享前轮摘要
- redteam 模式：挑战者 + 审查员 + 旧错者 三个对抗角色必须齐备，否则不得 Dispatch

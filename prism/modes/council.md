# 议事模式（Council）

> 多轮交互讨论，迭代收敛。存在分歧、需要迭代议事时使用。

---

## 适用场景
- 存在 ≥2 个互斥方案，无法独立取样解决
- redteam/explore 已产出 OPEN_QUESTION，需深度讨论
- 连续 2 轮卡壳，需要 Agent 之间互相挑战才能推进

## 协议族
议事协议（见 `../protocol.md §二`）

## 与独立取样模式的关键区别

| 维度 | 独立取样（explore/redteam/test） | 议事（council） |
|------|-------------------------------|---------------|
| Agent 间可见性 | 全程隔离（Dispatch Firewall） | 第2轮起共享前轮摘要 |
| 用途 | 独立视角发现问题 | 迭代讨论收敛分歧 |
| 终止条件 | Collect 完成即终止 | 收敛阈值或 N 轮上限 |

## Frame 额外内容

```
最大轮数  ：N（推荐 3 轮，最多 5 轮）
收敛阈值  ：≥70% 参与者同意核心行动项
议题类型  ：open-ended（探索）| decision（选方案）| critique（审查）
禁止项    ：哪些决策已被 PM Gate 锁定，不得重开
```

## 角色分配

council 模式的强制对抗角色同 redteam：
- **挑战者**：每轮必须提出反对意见
- **审查员**：每轮评估前轮摘要的忠实度
- **旧错者**：每轮对照 lessons.md 判断是否重演历史错误

## 成功标准

- **收敛（consensus）**：≥70% Agent 同意核心行动项 → Adjudicate → Archive
- **有限共识（weak-consensus）**：60%~70% 同意 → Adjudicate → Archive（标注风险）
- **僵局（deadlock）**：连续 N 轮无法达到 60% → 【硬终态】生成 OPEN_QUESTION 等待 Norven
- **强制结束**：达到最大轮数 N，按当轮共识率判断结果

## 摘要提炼规则（轮间共享）

第 N 轮结束后，Cap 提炼摘要再发给第 N+1 轮的 Agent：
```
摘要格式：
  - 当前主流观点（≥60% Agent 支持的立场）
  - 主要分歧点（<60% 支持的争议项）
  - 已排除的方案（多数 Agent 明确反对的选项）
```
注意：摘要是"提炼"而非"原文"——Synthesis Audit 规则同样适用（见 protocol.md）。

## 典型流程

```
Round 1：各 Agent 独立提交初始观点（Dispatch Firewall 生效）
          所有 agent_id 记入 session_registry
          ↓ Cap 提炼摘要（Synthesis Audit 规则适用）
Round 2：用 write_agent(agent_id) 向【同一批 Agent 的原有 session】发送：
          - 前轮摘要（主流观点 + 主要分歧 + 已排除方案）
          - 请求：更新或维持立场，填写 dissent 字段
          注意：必须复用 session_registry 中的 agent_id，不得重新 Dispatch 新 Agent
          ↓ 检查收敛
          if 收敛 → Adjudicate
          if 未收敛 → Round 3
Round 3：同 Round 2（继续 write_agent 到同一 session）
          ↓ 强制进入 Adjudicate（无论收敛与否）
```

**Session 复用规则**：
- Round 2 及之后，必须用 `write_agent(agent_id)` 向 Round 1 的原 session 追发摘要
- 禁止在 Round 2+ 重新 `task(mode="background")` 创建新 Agent 实例
- Agent session 在 council 全程保持活跃（agent 在最后一轮结束后方可视为完成）
- 若某 Agent session 已超时不可达，标记 ABSENT，但 quorum 分母仍按该 run Frame 阶段锁定的原始 Agent 数计算（遵循 `protocol.md` 的固定分母规则）

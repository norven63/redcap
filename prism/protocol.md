# 棱镜协议（Prism Protocol）

> 棱镜分两个协议族。选对协议族，是运行成功的前提。

---

## 协议族选择

```
需要独立视角，结论不相互影响？
  ├─ YES → 独立取样协议（explore / redteam / test）
  └─ NO，需要多轮交互讨论？
        └─ YES → 议事协议（council）
```

---

## 一、独立取样协议（Independent Sampling Protocol）

> 适用模式：`explore` / `redteam` / `test`  
> 核心原则：**各 Agent 全程独立，Dispatch Firewall 强制隔离**

### Step 1 · Frame（冻结任务）

在 Dispatch 前冻结以下内容，写入运行内存（不落盘）：

```
问题陈述    ：本次分析的核心问题是什么？
禁止项      ：哪些结论/方案不在考虑范围？（对齐 PM Gate 已锁定决策）
输出 Schema ：每个 Agent 必须按此格式输出：
              {
                "agent": "<model>",
                "conclusion": "<核心结论，50字内>",
                "confidence": "high|medium|low",
                "blockers": ["<问题1>", ...],  // 阻塞项，没有则 []
                "actions": ["<行动1>", ...],   // 建议行动
                "dissent": "<异议，无则 null>" // 对其他主流观点的反对意见
              }
验收标准    ：Adjudicate 阶段，什么条件算"可继续"？
与 PM Gate 的关系：
              - 若 PM Gate 已锁定需求 → Prism 运行"验证模式"：只验证方案可行性，不重开需求决策
              - 若 PM Gate 未锁定 → Prism 可探索，但不能代替 PM Gate 做决策
```

### Step 2 · Dispatch（分发，含防火墙）

**Dispatch Firewall（强制）**：在执行阶段，所有 Agent 不得：
- 读取 `prism/reports/` 下的任何文件
- 读取其他 Agent 的中间产出
- 访问 `.dev-task.md` 或其他状态文件（Frame 内容除外）

分发方式：为每个 Agent 发送完全相同的问题包（Frame 内容 + 具体分析任务）。

Agent 数量：
- explore：3~5 个
- redteam：≥3 个，其中 ≥1 个跨家族模型（如 Claude + GPT）
- test：2~4 个，按评分维度分工

### Step 3 · Collect（收集，含超时治理）

```
超时限制：单个 Agent 超过 30min 无响应 → 重试 1 次
重试失败：标记为 ABSENT，继续流程
法定人数（quorum）：≥60% Agent 完成（含重试），否则中止本次运行，记录原因
收集完成：所有 Agent 均提交符合 Schema 的结果（ABSENT 视为弃权）
```

### Step 4 · Synthesize（提炼）

从各 Agent 的 Schema 输出中提炼：
- **共识行动**：≥75% Agent 支持的行动项
- **弱共识**：60%~75% 支持，附少数意见
- **开放争议**：<60% 支持，双方论点均列出
- **ABSENT 说明**：记录哪个模型缺席及原因

### Step 5 · Adjudicate（裁决）

```
consensus     ：共识行动 ≥1 条，无阻塞项 → 可继续执行
weak-consensus：有弱共识但无严重阻塞 → 可继续，标注风险
deadlock      ：核心议题无共识（<60%） → 生成 OPEN_QUESTION 列表，暂停执行，等待 Norven 决策
escalate      ：发现 PM Gate 已锁定需求的边界问题 → 必须回到 §10 PM Gate 重新锁定，不得自行决定
```

**Adjudicate 权威规则**：Prism 无权推翻已 PM Gate 锁定的决策。若 Prism 结论与锁定需求冲突，结论 = escalate，不是 override。

### Step 6 · Archive（归档）

```
1. 写入运行报告：
   prism/reports/YYYYMMDD-{mode}-NNN.md
   （NNN 为当天流水号，从 001 起）

2. 更新索引：
   prism/reports/index.yaml
   （格式见下方 Index Schema）

3. 若 Adjudicate = consensus 或 weak-consensus，且产出可被后续决策引用：
   将核心结论（1~3 条）沉淀至 knowledge/lessons.md
   （理由：复活协议必读 lessons.md，这是棱镜结论进入"长期记忆"的唯一通道）

4. git add + commit（prism/reports/ 全部 git 追踪，作为架构演进的审计轨迹）
```

报告保留策略：
- 活跃期（90天内）：直接存放于 `reports/`
- 90天后：移至 `reports/archive/`，index.yaml 保留摘要
- 永不 gitignore：所有报告均 git 追踪

---

## 二、议事协议（Council Protocol）

> 适用模式：`council`  
> 核心原则：**共享前轮摘要，多轮收敛，有终点**

### Step 1 · Frame（同上，额外冻结）

在独立取样协议的 Frame 基础上，额外冻结：
```
最大轮数：N（推荐 3 轮）
收敛阈值：≥70% 参与者同意核心行动项
议题类型：open-ended（探索）| decision（选方案）| critique（审查）
```

### Step 2 · Round 1（独立意见轮）

各 Agent **独立**提交初始观点（此轮适用 Dispatch Firewall）。
输出 Schema 同独立取样协议。

### Step 3 · Round N（讨论轮，N=2,3,...）

各 Agent 收到前一轮**所有参与者的摘要**（非原始输出，由 Cap 提炼摘要再分发），
基于此更新或维持自己的立场。

每轮结束后检查收敛：
```
if 核心行动项同意率 ≥ 70%：
    进入 Adjudicate（提前结束）
elif 当前轮数 == N：
    进入 Adjudicate（强制结束）
else：
    继续下一轮
```

### Step 4 · Adjudicate + Archive（同独立取样协议）

---

## 三、Index Schema（报告索引格式）

```yaml
# prism/reports/index.yaml
reports:
  - id: "20260407-explore-001"
    mode: explore
    date: "2026-04-07"
    topic: "棱镜 v0.1 架构设计评审"
    agents: ["claude-sonnet-4.6", "claude-haiku-4.5"]
    verdict: "weak-consensus"          # consensus | weak-consensus | deadlock | escalate
    consensus_actions:
      - "拆分两个协议族"
      - "加入 Frame + Adjudicate 步骤"
    open_questions: []                  # deadlock 时填写
    lessons_updated: true              # 是否已沉淀至 lessons.md
    files_affected: ["prism/protocol.md", "prism/modes/"]
    archived: false                    # 是否已移至 archive/
```

---

## 四、触发条件（风险信号驱动）

不按文件数量触发，按**风险信号**触发：

| 风险信号 | 触发模式 |
|---------|---------|
| 改动核心协议/状态机（CONTRIBUTING.md §1-§10、SKILL.md §5.x） | redteam |
| 改动身份资产（soul.md、identity.md）| test |
| 存在 ≥2 个互斥方案，无法独立决策 | council |
| 已有明确不确定性或反对意见 | explore |
| 跨模型/跨框架验证需求 | redteam |
| 无法在 2 轮内自行解决的卡壳 | council |

**与 §10 PM Gate 的关系**：
```
需求不清晰 → §10 PM Gate 先行（Prism 不运行）
需求已锁定 + 方案有高风险信号 → Prism 运行（验证模式）
Prism 发现需求边界问题 → escalate → 回到 §10 PM Gate 重新锁定
```

**"Norven 不在"的可观测定义**：
- `.dev-task.md` 中显式标记 `absent: true`，或
- 当前会话中 Norven 已超过 2 个来回未回应 Cap 的澄清请求

---

## 五、与 §8/§9 的关系（迁移矩阵）

| 场景 | 推荐路径 | 说明 |
|------|---------|------|
| ≥5 个独立模块快速并行分析 | §8（保留） | 速度优先，无需多模型共识 |
| 提交前简单架构检查 | §9（保留） | 轻量 pre-commit，单模型即可 |
| 核心协议设计决策 | Prism redteam | 多家族模型，有 Adjudicate |
| soul/identity 大改验证 | Prism test | 结构化评分，有失败标准 |
| 方案分歧需迭代收敛 | Prism council | 多轮议事，有收敛终点 |
| 架构探索，方向未定 | Prism explore | 开放取样，提炼共识 |

§8/§9 是轻量快速路径，Prism 是高后果决策的系统化路径。两者并存，不替代。

# Agent-to-Agent（A2A）通信机制

> **定位**：定义 RedCap 框架中 Agent 之间直接通信的能力、协议和最佳实践。
> 本文件覆盖所有支持的 Agent CLI 工具，遵循 P-3（全局视角）原则。
> **依赖**：[Agent 适配器](../dispatcher/agent-adapters.md)（CLI 参数规范）、[通信协议](../references/communication-protocol.md)（Dispatcher⇄Agent 协议）

---

## 1. 概述

### 1.1 什么是 A2A 通信？

传统 RedCap 架构中，Agent 之间不直接对话——所有通信通过 Dispatcher 中转：

```
Agent A → __redcap_status → Dispatcher → Prompt → Agent B
```

A2A 通信是指**一个 Agent 直接调用另一个 Agent CLI 进行多轮对话**，跳过 Dispatcher 中转：

```
Agent A ──── CLI 调用（-S session_id） ────→ Agent B
Agent A ←── 响应文本 ←──────────────────── Agent B
Agent A ──── 追加 Prompt（同一 session） ──→ Agent B
Agent A ←── 响应文本 ←──────────────────── Agent B
...（多轮收敛）
```

### 1.2 何时使用 A2A？

| 场景 | 是否适合 A2A | 说明 |
|------|:---:|------|
| 正常角色流转（PM→ARCH→DEV→QA） | ❌ | 通过 Dispatcher 中转即可，保持流程可审计 |
| Agent 之间的技术方案讨论/Review | ✅ | 需要多轮交互达成共识 |
| 跨项目经验传递/咨询 | ✅ | 一方有知识，另一方需要理解和评估 |
| Hook 中拉起新 Agent 执行评审 | ⚠️ | 单向调用（非对话），用 `-p` 即可，不需要 session resume |
| 紧急修复需要两个 Agent 协商 | ✅ | 讨论模式比单向指令更可靠（L-18） |

### 1.3 核心原则（源自 L-18）

> **讨论驱动，非命令驱动**。A2A 通信中，发起方提出方案和发现，接收方独立评估——可以接受、反驳或补充。双方以共识收敛为目标，而非单方面执行。

---

## 2. 各 CLI 的 A2A 能力矩阵

| 能力维度 | Kimi CLI | Claude Code | Gemini CLI | VS Code Copilot |
|---------|:--------:|:-----------:|:----------:|:---------------:|
| Session 创建 | `--session "<id>"` | `--session-id "<uuid>"` | 自动生成 | ❌ |
| Session 恢复 | `-S "<id>"` / `--continue` | `--resume <id>` | `--resume latest\|<uuid>` | ❌ |
| 非交互多轮 | ✅ `--print -p` | ✅ `-p` | ✅ `-p --yolo` | ❌ |
| 返回格式 | text / stream-json | JSON (`result` 字段) | JSON (`response` 字段) | N/A |
| 只取最终回复 | `--final-message-only` | 解析 JSON `.result` | 解析 JSON `.response` | N/A |
| 自动审批 | `--yolo` / `-y` | `--permission-mode bypassPermissions` | `--yolo` | N/A |
| 实测验证 | ✅ 2026-04-04 | ✅ 2026-03+ | ⚠️ 部分 | ❌ |
| A2A 可用性 | **推荐** | **可用** | **受限** | **不可用** |

### 2.1 Kimi CLI — A2A 通信命令

```bash
# 首次发起对话
kimi --print -p "你的方案提议..." --session "a2a-copilot-kimi-$(date +%s)" -y

# 后续多轮（同一 session）
kimi -S "<session_id>" --print --final-message-only -y -p "收到你的反馈，关于第 2 点..."

# 只获取最终回复（适合程序化解析）
kimi -S "<session_id>" --print --final-message-only -y -p "请总结我们达成的共识"
```

**关键参数**：
- `-S` / `--session`：指定或恢复 session（自定义 ID 或已有 ID）
- `--print`：非交互模式（必须，否则等待 stdin）
- `--final-message-only`：只输出最终回复文本（去掉思考过程等噪音）
- `-y` / `--yolo`：自动审批（A2A 对话通常不需要工具操作，但加上防止意外阻塞）
- `-p`：传入 prompt（必须放在最后或明确跟值，避免 L-18 实测中的参数吞并问题）

**注意事项**：
- `--print` 模式下 Stop hook 不触发（直接跳到 SessionEnd），`-p` 模式正常触发
- Session 可在交互式和非交互式之间切换——用户在交互式 session 中工作时，其他 Agent 仍可通过 `-S` 向同一 session 发消息

### 2.2 Claude Code — A2A 通信命令

```bash
# 首次发起对话
claude -p "你的方案提议..." \
  --output-format json \
  --session-id "<uuid>" \
  --permission-mode acceptEdits

# 后续多轮（恢复 session）
claude -p "收到你的反馈，关于第 2 点..." \
  --output-format json \
  --resume "<session_id>"

# 解析回复
echo "$response" | jq -r '.result'
```

**关键参数**：
- `--session-id`：首次调用时指定自定义 UUID
- `--resume`：后续调用恢复已有 session
- `--output-format json`：返回结构化 JSON（`.result` 字段含回复文本）
- `--permission-mode acceptEdits`：A2A 讨论通常只读代码+写文档，用 `acceptEdits` 即可

**注意事项**：
- Claude Code 的底层模型可能是 Kimi K2.5（SiliconFlow 代理），不一定是原生 Claude
- `num_turns` 字段可追踪对话轮次

### 2.3 Gemini CLI — A2A 通信命令

```bash
# 首次对话
gemini -p "你的方案提议..." \
  --output-format json \
  --yolo \
  --sandbox false

# 恢复 session
gemini -p "收到你的反馈..." \
  --output-format json \
  --yolo \
  --sandbox false \
  --resume latest   # 或 --resume <uuid>

# 解析回复
echo "$response" | jq -r '.response'
```

**⚠️ 限制**：
- Gemini CLI 的 Hooks 机制尚未集成到 agent loop（v0.36.0），无法通过 Hook 自动触发 A2A
- `--resume latest` 恢复最近 session，但无法指定自定义 session ID（不如 Kimi/Claude 灵活）
- 长任务可能出现进程不退出问题（L-11）

### 2.4 VS Code Copilot — 不支持 A2A

VS Code Copilot 无 CLI 调用接口，无 session resume 机制，**不可用于 A2A 通信链路中的被调用方**。

但 Copilot 可以作为 **A2A 的发起方**——通过在终端中执行其他 CLI 命令（如 `kimi -S ...`）来发起对话。本次 Copilot × Kimi 的 A2A 协作即采用此模式。

---

## 3. A2A 讨论协议

### 3.1 讨论流程

```
发起方 Agent A                              接收方 Agent B
    │                                           │
    │──── Round 1: 方案提议 ───────────────────→│
    │     "我发现 3 个问题，请独立评估..."       │
    │                                           │
    │←── Round 1 回复: 逐点评估 ────────────────│
    │     "问题 1 同意；问题 2 有补充；          │
    │      另外我发现了第 4 个问题..."           │
    │                                           │
    │──── Round 2: 回应反馈 ───────────────────→│
    │     "关于你发现的第 4 个问题，              │
    │      我建议用方案 X 解决..."               │
    │                                           │
    │←── Round 2 回复: 确认或继续讨论 ──────────│
    │     "同意方案 X，已执行修复"               │
    │                                           │
    │──── Round 3（可选）: 验证 ───────────────→│
    │     "请执行 E2E 验证并报告结果"            │
    │                                           │
    │←── Round 3 回复: 验证报告 ────────────────│
    │     "10 项检查全部通过"                    │
    │                                           │
    ▼ 共识达成，讨论结束                         ▼
```

### 3.2 讨论 Prompt 规范

**发起方首轮 Prompt 必须包含**：

```
1. 身份声明："我是 {Agent 名称}，来自 {项目名称}"
2. 意图声明："这不是指令，我希望你独立评估"
3. 具体发现/提议（编号，方便逐点回应）
4. 明确请求："如果你不同意某个点，请明确反驳并说明理由"
```

**接收方回复应包含**：

```
1. 逐点评估（同意/反驳/补充）
2. 新发现（如果有）
3. 建议的下一步
```

### 3.3 收敛条件

讨论在以下条件之一满足时结束：
- 双方对所有分歧点达成一致
- 发起方确认接收方的修复/执行结果通过验证
- 超过 5 轮仍未收敛 → 升级给人类搭档决策（P-4 原则）

### 3.4 讨论记录

A2A 讨论的结果应以以下方式留痕：
- **经验层**：如果发现有复用价值的模式 → 沉淀为 Lesson
- **变更层**：如果讨论导致了文件修改 → 正常 git commit（附带讨论背景）
- **不需要**：完整的对话记录（session 本身保留在各 CLI 的 session 存储中）

---

## 4. A2A 在 RedCap 状态机中的定位

### 4.1 当前架构：Dispatcher 中转

```
PM ──→ Dispatcher ──→ ARCH ──→ Dispatcher ──→ DEV ──→ ...
```

所有角色之间的信息传递通过 Dispatcher 中转完成。具体传递方式采用三级优先级（L-23）：
1. **outbox 文件**（主通道）：Agent 将 `__redcap_status` 写入 `{role}/outbox/__redcap_status.json`，Dispatcher 读取后归档到 `.workflow/last-result.json` 并删除 outbox 副本
2. **stdout 正则**（辅助通道）：Dispatcher 从 Agent 回复文本中正则提取 `__redcap_status` JSON 块
3. **last-result.json**（兜底通道）：Agent 将状态写入 `.workflow/last-result.json`

三个通道保证流程可审计、可恢复、可追踪。

### 4.2 A2A 扩展：协商通道

A2A 为以下场景提供**辅助通道**：

```
                    ┌─────── A2A 协商 ───────┐
                    │                         │
                    ▼                         ▼
DEV_WORKING ──→ DEV Agent ←──讨论──→ ARCH Agent
                    │
                    ▼
             __redcap_status
             (status: need_revision 或 completed)
```

**关键约束**：
- A2A 是辅助通道，不替代 Dispatcher 中转——状态流转仍由 Dispatcher 驱动
- A2A 讨论的最终结果仍需通过 `__redcap_status` 回报给 Dispatcher
- Dispatcher 不感知 A2A 对话的内部过程，只看最终状态

### 4.3 未来方向：NEGOTIATING 状态

当 RedCap 的协商机制成熟后，状态机可新增 `NEGOTIATING` 状态：

```
REVIEW_FAIL  ──→ NEGOTIATING ──→ DEV_WORKING（仅修确认需修的）
need_revision ──→ NEGOTIATING ──→ ARCH_WORKING（仅修确认有误的）
```

`NEGOTIATING` 状态下，Dispatcher 编排两个 Agent 之间的讨论轮次，直至双方收敛或超时升级。此设计在 §5 协商协议中详细定义。

---

## 5. 协商协议（Negotiation Protocol）

> **状态**：设计完成，待首次实际项目中验证后正式纳入状态机。

### 5.1 动机

当前 RedCap 的回退机制是**单向的**：

```
QA 说"代码有 bug"  →  DEV 无条件修复  →  可能 QA 误判
Reviewer 说"架构问题" →  ARCH 无条件修改  →  可能 Reviewer 理解有偏差
```

协商协议引入**双向验证**：接收回退的 Agent 有权评估反馈的正确性，避免无效回退。

### 5.2 适用场景

| 触发条件 | 发起方 | 接收方 | 协商内容 |
|---------|--------|--------|---------|
| `REVIEW_FAIL` | Reviewer | Programmer | Review 发现是否为真实问题 |
| `REVIEW_FAIL(root=design)` | Reviewer | Architect | 架构改进建议是否合理 |
| `QA_FAIL(root=code)` | QA | Programmer | Bug 是实现问题还是测试用例问题 |
| `QA_FAIL(root=design)` | QA | Architect | 设计缺陷 vs 需求理解偏差 |
| `need_revision(arch)` | Programmer | Architect | 设计不可行 vs 实现方式不对 |

**不适用**（直接走原有流程）：
- `QA_FAIL(root=requirement)` → PM 回退，需求层面不由技术 Agent 协商
- `need_user` → 用户决策，不是 Agent 间协商
- `blocked(L2)` → 超出 Agent 权限

### 5.3 协商状态转移

```
原触发状态 → NEGOTIATING
                │
        ┌───────┼───────┐
        ▼       ▼       ▼
     AGREED  PARTIAL  DEADLOCK
        │       │       │
        ▼       ▼       ▼
     执行修复  部分修复  升级人类
     (原流程)  (缩小范围)  (PAUSED)
```

**收敛事件**：

| 事件 | 含义 | 后续 |
|------|------|------|
| `AGREED` | 接收方完全同意发起方的发现 | 按原有流程修复所有问题 |
| `PARTIAL` | 接收方同意部分发现，反驳其余 | 只修双方确认的问题，反驳的问题标注为"已评估-非问题" |
| `DEADLOCK` | 双方无法在 5 轮内收敛 | 升级给人类搭档决策（PAUSED） |

### 5.4 `__redcap_status` 扩展

协商结果通过新增 `negotiation` 字段传递：

```json
{
  "__redcap_status": {
    "status": "completed",
    "summary": "协商完成，3 项中 2 项同意修复，1 项确认为 QA 测试用例问题",
    "negotiation": {
      "outcome": "PARTIAL",
      "rounds": 3,
      "agreed_items": ["BUG-1: 空指针检查缺失", "BUG-3: 错误码不一致"],
      "rejected_items": [
        {
          "id": "BUG-2",
          "description": "返回值格式不匹配",
          "rejection_reason": "QA 测试用例基于旧版 API 文档，当前实现符合最新设计"
        }
      ]
    }
  }
}
```

### 5.5 Dispatcher 协商编排伪代码

```python
def handle_negotiation(initiator_role, receiver_role, findings):
    """Dispatcher 编排两个 Agent 之间的协商"""
    
    session_id = f"negotiate-{initiator_role}-{receiver_role}-{uuid4()}"
    
    # Round 1: 将发起方的发现发送给接收方
    prompt = format_negotiation_prompt(
        findings=findings,
        instruction="请逐条评估以下发现，可以接受、反驳或补充"
    )
    response = call_agent(receiver_role, prompt, session_id)
    
    for round in range(2, MAX_ROUNDS + 1):  # MAX_ROUNDS = 5
        evaluation = parse_evaluation(response)
        
        if evaluation.all_agreed():
            return NegotiationResult(outcome="AGREED", items=evaluation.agreed)
        
        if evaluation.has_new_findings():
            # 接收方发现了新问题，发回给发起方评估
            prompt = format_counter_prompt(evaluation)
            response = call_agent(initiator_role, prompt, session_id)
        else:
            # 仍有分歧，请发起方回应反驳
            prompt = format_rebuttal_prompt(evaluation.disagreements)
            response = call_agent(initiator_role, prompt, session_id)
        
        # 交换角色继续
        initiator_role, receiver_role = receiver_role, initiator_role
    
    # 超过 MAX_ROUNDS
    return NegotiationResult(outcome="DEADLOCK", escalate_to="user")
```

### 5.6 协商与现有 Prompt 模板的集成

各角色的 prompt 模板需新增协商相关的变量：

```
{{negotiation_mode}}       → "none" | "initiator" | "receiver"
{{negotiation_findings}}   → 对方提出的发现列表（JSON）
{{negotiation_round}}      → 当前协商轮次
{{negotiation_history}}    → 前几轮的讨论摘要
```

协商模式下，角色手册中的"工作流程"会被替换为"评估流程"——Agent 不执行完整的角色职责，只评估和回应对方的具体发现。

---

## 6. 实施路线图

| 阶段 | 内容 | 状态 |
|------|------|------|
| **Phase 0: 经验沉淀** | L-18 记录 + A2A 文档（本文件） | ✅ 已完成 |
| **Phase 1: 手动 A2A** | Dispatcher 外手动发起 A2A 对话（如本次 Copilot×Kimi） | ✅ 已验证 |
| **Phase 2: 协商协议设计** | `NEGOTIATING` 状态 + `__redcap_status` 扩展 + 伪代码 | ✅ 设计完成（本文件 §5） |
| **Phase 3: 状态机集成** | 修改 `state-machine.md` + `communication-protocol.md` | ⏳ 待前置条件满足 |
| **Phase 4: Prompt 模板** | 各角色添加协商模式 prompt + 变量映射 | ⏳ 待 Phase 3 |
| **Phase 5: 全 Agent 适配** | 确保 Kimi/Claude/Gemini 三个 CLI 都能作为协商参与方 | ⏳ 待 Phase 4 |

> **Phase 3 启动的前置条件**：至少 2 个不同的 Agent CLI 能在 headless 模式下稳定完成各自角色任务（当前 3/4 个 CLI 存在挂起/超时/阻塞问题，见 L-4/L-5/L-7/L-11）。在此之前，协商的双方实际是同一个 Dispatcher 模型，不存在"独立视角分歧"的协商需求。回退路径的验证可通过刻意注入缺陷来测试（见 smoke-test-backlog #11-#15），不必等待自然触发。

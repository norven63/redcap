# Agent 适配器（CLI 参数映射）

> **用途**：定义各 Agent CLI 工具的调用参数规范，供 Dispatcher 组装命令使用。

---

## 1. Agent 路由表

### 1.1 Agent 标识格式

Agent 使用 `{cli}&{model}` 格式标识，解耦 CLI 工具与底层模型：

```
claude-code&Kimi-K2.5     — Claude Code CLI + Kimi K2.5 (SiliconFlow)
claude-code&claude-sonnet — Claude Code CLI + Claude Sonnet 原生
gemini&gemini-3-flash      — Gemini CLI + Gemini 3 Flash
kimi&kimi-for-coding       — Kimi CLI + Kimi Code 原生
copilot&claude-opus-4.6    — Copilot CLI + Claude Opus 4.6（默认）
copilot&gpt-5.4            — Copilot CLI + GPT-5.4
codex&gpt-5.4              — Codex CLI + GPT-5.4
```

### 1.2 模型嗅探与缓存

> 嗅探逻辑已封装为脚本，Dispatcher 只需调用一行命令（L-12: 关键动作用脚本而非纯文本指令）。

**嗅探脚本**：`bash compass/tools/redcap-detect-agents.sh [output_path] [--agent <name>] [--probe]`

**两层检测机制**：

| 层级 | 做什么 | 耗时 | 触发时机 |
|------|--------|------|---------|
| **轻检测** | `command -v` + 配置文件 mtime 对比 | < 1s | 每次 RedCap 会话启动 |
| **全量检测** | 读配置文件解析模型 + 写 registry | 2-5s | 首次 / registry 不存在 / 配置 mtime 变化 / Agent 失败 |
| **探测模式** | 实际调用 CLI 获取精确模型（`--probe`） | 10s+ | 用户手动触发 / 诊断问题时 |

**运行逻辑**：
1. 脚本自动比较已缓存 registry 中各 Agent 的 `config_mtime` 与当前磁盘 mtime
2. 若全部一致 → 输出 "fresh"，跳过检测
3. 若有变化 → 全量重检，覆盖 registry
4. `--agent <name>` → 只重检指定 Agent（故障恢复时使用）

**缓存位置**：`compass/.workflow/agent-registry.yaml`（由脚本自动生成的 runtime cache，local-only，勿手动编辑，也不要提交到 git）

**registry 示例**（以本设备 2026-04 实际嗅探结果为例）：
```yaml
detected_at: "2026-04-06T09:41:38Z"
agents:
  claude-code:
    available: true
    cli_path: "/Users/norven/bin/claude"
    version: "2.1.81"
    model_alias: "sonnet"          # settings.json 中配置的别名
    actual_model: "kimi-k2.5"      # 实际模型（由 base_url 推断）
    api_provider: "kimi-siliconflow"
    config_mtime: "2026-04-06T00:32:07"
    supports_model_switch: true
  gemini:
    available: true
    actual_model: "gemini-3-flash"
    known_issues: ["L-7", "L-11"]
  kimi:
    available: true
    actual_model: "kimi-code/kimi-for-coding"
  copilot:
    available: true
    actual_model: "claude-opus-4.6"
    supports_model_switch: true
    switchable_models: ["claude-opus-4.6", "gpt-5.4", "claude-sonnet-4.6"]
  codex:
    available: true
    actual_model: "gpt-5.4"
    supports_model_switch: true
```

> ⚠ **关键发现**：Claude Code CLI 的 `settings.json` 中 `"model": "sonnet"` 并不代表使用 Claude Sonnet。当 `ANTHROPIC_BASE_URL` 指向第三方代理（如 `api.kimi.com`）时，model 别名无意义，实际模型由代理方决定。嗅探脚本通过 `base_url` + `api_key` 前缀推断真实模型。

### 1.3 动态路由算法

> **设计原则**：路由决策 = 动态可用性（嗅探脚本）× 静态适配度经验（能力矩阵）。
> 排名是参考，落地逻辑依托本地实际部署。

**能力矩阵**：[`knowledge/model-capability-matrix.yaml`](../knowledge/model-capability-matrix.yaml)

**算法步骤**（Dispatcher 在每个新步骤开始时执行）：

```
输入: role, agent-registry.yaml, model-capability-matrix.yaml, dev_agent(仅 reviewer)
输出: 有序候选列表 [{cli}&{model}, ...]

1. 从 registry 筛选 available=true 的 Agent
2. 展开可切换模型的 Agent
   例: copilot (switchable) → copilot&claude-opus-4.6, copilot&gpt-5.4, copilot&claude-sonnet-4.6
3. 对每个候选 {cli}&{model}:
   a. 查矩阵获取能力评分（未收录模型按 all=3 兜底处理）
   b. role_req = matrix.role_requirements[role]
   c. score = model[role_req.primary] × 2 + model[role_req.secondary] × 1
   d. Reviewer 特殊: model.family ≠ dev_agent.family → score += 2
   e. agent.known_issues 非空 → score -= 1
4. 找出 top_score，并把满足“已过最低门槛且 score >= top_score - 1”的候选视为**能力相当带**
5. 在能力相当带内，优先 cost_efficiency 更高的候选；若 Gemini CLI 位于该带内且无阻塞性 known_issues，则优先于更高成本宿主
6. 若仍并列，再按 score 降序；同分优先: 专用 CLI > 通用 CLI 代理（如 kimi > claude-code 代理 kimi-k2.5）
7. 输出有序候选列表
```

**锁定规则**（原子性保证）：
- 某步骤选定 Agent 后，写入 `state.yaml`：
  ```yaml
  current_role:
    role: architect
    agent: "copilot&claude-opus-4.6"
    locked: true
    candidates: ["copilot&claude-opus-4.6", "gemini&gemini-3-flash", ...]
  ```
- 该步骤内持续使用此 Agent，不因外部变化而切换
- 仅当**连续 2 次失败**时，从 `candidates` 取下一个（Fallback），并更新 `agent` 字段
- **新步骤开始**时：失败计数归零，重新执行路由算法（重读 registry + 矩阵）

**示例**（基于本设备 2026-04 实际嗅探结果）：

| 角色 | 算法计算过程 | 首选结果 |
|------|------------|---------|
| 产品经理 | kimi-for-coding: IF=4×2 + R=3 = 11; kimi-k2.5: 4×2+3=11; opus: 4×2+5=13 → **但 copilot 是通用 CLI，kimi 是专用 CLI** | `kimi&kimi-for-coding` |
| 架构师 | opus: R=5×2 + C=5 = 15; flash: 4×2+4=12; k2.5: 3×2+4=10 | `copilot&claude-opus-4.6` |
| 程序员 | opus: C=5×2 + TU=4 = 14; flash: 4×2+3=11; kimi-coding: 4×2+4=12 | `copilot&claude-opus-4.6` |
| 测试QA | kimi-coding: TU=4×2 + IF=4 = 12; gpt-5.4: 5×2+5=15 → **但 copilot 通用 CLI vs kimi 专用** | `copilot&gpt-5.4` |
| Reviewer | 假设 Dev 用了 copilot&opus(anthropic族): gpt-5.4(openai族): R=5×2+C=4=14 +2(跨族)=16；若 Copilot 限流，Codex CLI 可作为同 OpenAI 族 fallback | `copilot&gpt-5.4` / `codex&gpt-5.4` |

> 注意：示例中 copilot 频繁出现是因为它可切换 Premium 模型。若 copilot 不可用，Budget/Standard 层自动接管。

用户可在项目 `.workflow/state.yaml` 中通过 `agent_routing_override` 字段覆盖算法结果。

---

## 2. Claude Code CLI（Kimi K2.5）

### 2.1 基本信息

- **可执行文件**：`claude`（路径：`/opt/homebrew/bin/claude`）
- **底层模型**：Pro/moonshotai/Kimi-K2.5（经 SiliconFlow 代理）
- **版本**：2.1.86+

### 2.2 命令模板

```bash
# 产品经理（只读写文档）
claude -p "$(cat .workflow/{role}-prompt-step{N}.txt)" \
  --append-system-prompt "$(cat .workflow/{role}-system-prompt.txt)" \
  --output-format json \
  --add-dir "<项目根目录>" \
  --permission-mode acceptEdits \
  --session-id "<UUID>"

# 程序员 / 测试QA（需要执行 Shell 命令）
claude -p "$(cat .workflow/{role}-prompt-step{N}.txt)" \
  --append-system-prompt "$(cat .workflow/{role}-system-prompt.txt)" \
  --output-format json \
  --add-dir "<项目根目录>" \
  --permission-mode bypassPermissions \
  --session-id "<UUID>"
```

> Dispatcher 始终先将 prompt 和 system-prompt 写入 `.workflow/` 下的文件，再用 `$(cat ...)` 读取传入 CLI，避免 Shell 中文引号截断问题。
> Claude Code 优先使用 `--append-system-prompt`，避免 `--system-prompt` 覆盖默认系统提示。
> `--session-id` 首次调用时传入调用方生成的 UUID，后续通过 `--resume` 恢复。
> `--permission-mode bypassPermissions` 跳过所有权限检查（程序员/QA 需要执行 Shell），防止 `-p` 管道模式下权限弹窗导致挂起（与 L-7 Gemini `--yolo` 同理）；`acceptEdits` 仅审批文件编辑（PM/架构师）。

### 2.3 参数说明

| 参数 | 用途 | 取值 |
|------|------|------|
| `-p` | 非交互模式，传入 prompt | Dispatcher 组装的完整任务指令 |
| `--append-system-prompt` | 角色身份设定 | 对应角色手册.md 的核心摘要（追加，不覆盖默认系统提示） |
| `--output-format json` | 返回 JSON 格式 | 固定 `json` |
| `--add-dir` | 授权访问的项目目录 | 项目根目录路径 |
| `--permission-mode` | 权限模式 | PM/架构师: `acceptEdits`；程序员/QA: `bypassPermissions` |
| `--session-id` | 指定 Session ID | 首次调用时传入 Dispatcher 生成的 UUID |
| `--resume` | 恢复已有 Session | 传入 session_id 恢复上下文 |
| `--name` | Session 命名 | `"redcap-{role}-step{N}"` 便于人工识别 |
| `--max-budget-usd` | 成本上限 | 可选，防止单次调用失控 |

### 2.4 返回格式

```json
{
  "type": "result",
  "session_id": "uuid-string",
  "result": "Agent 的回复文本（包含 __redcap_status）",
  "cost_usd": 0.0,
  "duration_ms": 12345,
  "num_turns": 3
}
```

**注意**：Claude Code 的回复文本在 `result` 字段（非 `response`）。

---

## 3. Gemini CLI（Gemini 3 Flash）

### 3.1 基本信息

- **可执行文件**：`gemini`（路径：`/opt/homebrew/bin/gemini`）
- **底层模型**：gemini-3-flash-preview（路由层 gemini-2.5-flash-lite）
- **版本**：0.35.3+

### 3.2 命令模板

```bash
gemini -p "$(cat .workflow/{role}-prompt-step{N}.txt)" \
  --output-format json \
  --sandbox false \
  --yolo \
  --include-directories "<项目根目录>"
```

> ⚠️ `-p` 参数必须存在，否则 Gemini 进入交互模式导致终端不可用。
> `--sandbox false` 避免沙盒确认弹窗。
> `--yolo` 自动审批所有工具操作（含 Shell 命令）。⚠️ 不要用 `--approval-mode auto_edit`，那只审批文件编辑，Shell 命令仍会弹确认导致 headless 模式永久挂起。

### 3.3 参数说明

| 参数 | 用途 | 取值 |
|------|------|------|
| `-p` | 非交互模式，传入 prompt | Dispatcher 组装的完整任务指令 |
| `--output-format json` | 返回 JSON 格式 | 固定 `json` |
| `--sandbox false` | 禁用沙盒 | 避免沙盒确认弹窗 |
| `--yolo` | 自动审批所有操作 | 固定，避免 Shell 命令确认挂起（⚠️ 不要用 `--approval-mode auto_edit`） |
| `--include-directories` | 授权访问的项目目录 | 项目根目录路径 |
| `--model` | 指定模型 | 可选，如 `gemini-2.5-pro`（默认由 Google 路由选择） |
| `--resume` | 恢复已有 Session | `latest` 或 session index 或 UUID |
| `--list-sessions` | 列出可恢复的 Session | 查询用，不含 prompt |

### 3.4 返回格式

```json
{
  "session_id": "uuid-string",
  "response": "Agent 的回复文本（包含 __redcap_status）",
  "stats": {
    "total_tokens": 1234,
    "duration_ms": 5678
  }
}
```

**注意**：Gemini 的回复文本在 `response` 字段。

---

## 4. 角色 × 权限配置

### 4.1 Claude Code `--permission-mode` 映射

| 角色 | permission-mode | 说明 |
|------|-----------------|------|
| 产品经理 | `acceptEdits` | 只读写文档，不执行代码 |
| 架构师 | `acceptEdits` | 可读写文档，不需要 Shell |
| 程序员 | `bypassPermissions` | 跳过所有权限检查（含 Shell 命令），防止管道模式挂起 |
| 测试QA | `bypassPermissions` | 跳过所有权限检查（含测试执行），防止管道模式挂起 |
| Reviewer | `acceptEdits` | 只读代码和写 Review 报告 |

### 4.2 Gemini `--yolo` 映射

| 角色 | 模式 | 说明 |
|------|------|------|
| 所有角色 | `--yolo` | 自动审批所有操作。⚠️ `--approval-mode auto_edit` 仅审批文件编辑，Shell 命令仍会弹确认导致 headless 挂起 |

### 4.3 Kimi `--yolo` 映射

| 角色 | 模式 | 说明 |
|------|------|------|
| 所有角色 | `--yolo` | 自动审批所有操作（Kimi CLI 不区分角色级权限，通过 Prompt 约束） |

### 4.4 Copilot `--allow-all` 映射

| 角色 | 模式 | 说明 |
|------|------|------|
| 所有角色 | `--allow-all --autopilot` | 全授权 + 自动驾驶（Copilot CLI 不区分角色级权限，通过 Prompt 约束） |

### 4.5 目录访问限制

Dispatcher 通过 Prompt 中的行为约束实现目录级权限控制（CLI 参数不支持细粒度目录授权）：

```
在 Prompt 中明确指示：
- "你的工作目录是 开发手册/{角色目录}/"
- "你只能写入 开发手册/{角色目录}/ 和 开发手册/{角色目录}/outbox/"
- "你可以读取但不能修改 开发手册/shared/ 和上游角色的 outbox/"
```

---

## 5. 返回值标准化

Dispatcher 从三种 CLI 获得的输出结构不同，需要统一提取：

```
Claude Code (--output-format json):
  session_id = result["session_id"]
  response_text = result["result"]

Gemini (--output-format json):
  session_id = result["session_id"]
  response_text = result["response"]

Kimi (--print --output-format text):
  response_text = 完整文本输出（Kimi 不返回结构化 JSON wrapper）
  session_id = 从 CLI 日志或 sessions 目录提取

Copilot CLI (--output-format=json):
  response_text = 从 JSONL assistant 行提取 assistant.message.data.content（见 §3C.5）
  session_id = 从 .workflow/.copilot-session-id 读取（由 JSONL 最终 result 行的 sessionId 字段写入，见 §3C.5）

统一后:
  从 response_text 中正则提取 __redcap_status JSON 块
  由 Dispatcher 写入 .workflow/last-result.json（Agent 不再负责写入此文件）
```

---

## 6. Agent Fallback 策略

### 6.1 Fallback 候选列表

Fallback 候选列表由 §1.3 动态路由算法在每个新步骤开始时计算，输出格式为 `{cli}&{model}` 有序列表（存入 `state.yaml` 的 `current_role.candidates`）。

> ⚠ 不再使用静态 CLI 级别的路由表。同一 CLI 下的不同 Model 作为独立候选参与排序。

**示例**（architect 角色，基于 2026-04 实际环境）：
```yaml
current_role:
  role: architect
  agent: "copilot&claude-opus-4.6"    # 当前使用
  locked: true
  candidates:                          # 有序 Fallback 列表
    - "copilot&claude-opus-4.6"       # 首选
    - "copilot&gpt-5.4"              # 同 CLI 不同 Model
    - "gemini&gemini-3-flash"         # 不同 CLI
    - "copilot&claude-sonnet-4.6"     # 同 CLI 低层级 Model
    - "kimi&kimi-for-coding"          # 不同 CLI
    - "claude-code&kimi-k2.5"         # 不同 CLI
```

### 6.2 触发条件

- 首选 Agent 连续 **2 次**返回失败（含 HTTP 429 频控、CLI 进程非零退出码）
- CLI 进程超时（无响应超过合理阈值，见 §8）
- CLI 进入交互模式（未正常返回 JSON）

### 6.3 两层降级切换流程

降级分两层：**Model 降级**（换同 CLI 下的其他 Model）和 **CLI 降级**（换不同 CLI）。优先 Model 降级，因为参数体系不变、成本最低。

```
当前 Agent = {cli}&{model} 失败

Layer 1: Model 降级（同 CLI 内）
  1. 首选 Agent 第 1 次失败 → 重试同一 Agent
  2. 第 2 次仍失败 → 从 candidates 中找同一 CLI 的下一个 Model
     条件：该 Model 的角色适配分 ≥ 角色最低门槛（见 §6.3.1）
  3. 找到 → 切换 Model，更新 state.yaml，重置失败计数
  4. 未找到（同 CLI 无其他可用 Model）→ 进入 Layer 2

Layer 2: CLI 降级（换 CLI）
  5. 从 candidates 中找不同 CLI 的下一个候选
     条件：该候选的角色适配分 ≥ 角色最低门槛
  6. 找到 → 切换 CLI+Model，按目标 CLI 的参数映射（§2/§3/§3B）重新组装命令
  7. 未找到（所有候选均已失败或不达标）→ 进入 §6.5 用户降级决策

每次切换后：
  · 更新 state.yaml 的 current_role.agent
  · 新 Agent 享有独立的 2 次重试机会
  · 记录切换原因到 agent_health
```

#### 6.3.1 角色最低能力门槛

降级后的 Model 必须满足角色最低能力要求，否则宁可继续降级到下一个候选，也不用一个不够格的 Model 硬撑：

```yaml
# 在 model-capability-matrix.yaml 中定义
role_minimum_thresholds:
  product-manager:
    instruction_following: 3    # PM 必须能准确采集需求
    reasoning: 2
  architect:
    reasoning: 4                # 架构师必须有强推理能力
    coding: 3
  programmer:
    coding: 4                   # 程序员必须能写高质量代码
    tool_use: 3
  qa:
    tool_use: 3                 # QA 必须能执行测试
    instruction_following: 3
  reviewer:
    reasoning: 4                # Reviewer 必须能独立判断
    coding: 3
```

**门槛检查逻辑**：
```
对候选 {cli}&{model}:
  model_caps = matrix.models[model]
  role_min = matrix.role_minimum_thresholds[role]
  对 role_min 中每个 {capability}: {min_score}:
    若 model_caps[capability] < min_score → 不合格，跳过
  全部通过 → 合格，可作为降级目标
```

### 6.4 Agent 可用性追踪

Dispatcher 在 `state.yaml` 中维护 `agent_health` 字段，粒度为 `{cli}&{model}`：

```yaml
agent_health:
  "copilot&claude-opus-4.6":
    consecutive_failures: 2
    last_failure_at: "2026-04-07T15:00:00+08:00"
    last_failure_reason: "timeout (>120s)"
    blacklisted: true
  "copilot&gpt-5.4":
    consecutive_failures: 0
    last_failure_at: null
    last_failure_reason: null
    blacklisted: false
  "gemini&gemini-3-flash":
    consecutive_failures: 2
    last_failure_at: "2026-04-07T15:10:00+08:00"
    last_failure_reason: "interactive mode (L-7)"
    blacklisted: true
  "kimi&kimi-for-coding":
    consecutive_failures: 0
    last_failure_at: null
    last_failure_reason: null
    blacklisted: false
```

**重置规则**：
- **新步骤开始时**：所有 Agent 的 `consecutive_failures` 重置为 0，`blacklisted` 重置为 false（Agent/Model 可能已恢复）
- **用户显式告知**（如 "gemini 已恢复"）：立即重置指定 Agent 的健康状态
- **失败计数仅在当前步骤内累积**
- **同 CLI 不同 Model 独立追踪**：`copilot&claude-opus-4.6` 失败不影响 `copilot&gpt-5.4` 的健康状态

### 6.5 用户降级决策（替代原"铁律"的绝对禁令）

当所有 Fallback Agent 均不可用时，Dispatcher **立即暂停任务并通知用户**，提供以下选项：

```
⚠️ 所有 Agent 不可用（原因：{failures_summary}）

请选择：
(a) 授权降级 — 由当前对话 AI（Dispatcher）代为执行本步骤任务
    ⚠ 风险：上下文压缩，失去多视角交叉验证
(b) 指定 Agent — 告知要使用的 Agent（如 "用 kimi-cli"）
```

**降级执行规则**：
- 用户选择 (a) 后，`state.yaml` 记录 `degraded_mode: true`，`degraded_approved_by: user`
- 降级模式下产出的交付物标记来源为 `dispatcher-degraded`
- 降级模式仅对**当前步骤**有效，下一步骤开始时自动退出降级（重新尝试 Agent）

### 6.6 Dispatcher 铁律（修订版）

> ⚠️ **Dispatcher 默认不得直接修改项目源代码或代为生成任何交付物。**
> 所有 Agent 均不可用时，Dispatcher 必须暂停流程并向用户报告，由用户决定是否授权降级。
> **未经用户授权，Dispatcher 绝不代劳。**

---

## 7. Prompt 传参规范

### 7.1 文件传参模式（标准）

Dispatcher 始终使用文件传参，避免 Shell 中文引号截断问题：

```bash
# 1. Dispatcher 将组装好的 prompt 写入文件
#    .workflow/{role}-prompt-step{N}.txt

# 2. CLI 调用时用 $(cat ...) 读取

# Claude Code（PM/架构师：acceptEdits）:
claude -p "$(cat .workflow/{role}-prompt-step{N}.txt)" \
  --append-system-prompt "$(cat .workflow/{role}-system-prompt.txt)" \
  --output-format json \
  --add-dir "<项目根目录>" \
  --permission-mode acceptEdits \
  --session-id "<UUID>" \
  --name "redcap-{role}-step{N}"

# Claude Code（程序员/QA：auto）:
claude -p "$(cat .workflow/{role}-prompt-step{N}.txt)" \
  --append-system-prompt "$(cat .workflow/{role}-system-prompt.txt)" \
  --output-format json \
  --add-dir "<项目根目录>" \
  --permission-mode auto \
  --session-id "<UUID>" \
  --name "redcap-{role}-step{N}"

# Gemini:
gemini -p "$(cat .workflow/{role}-prompt-step{N}.txt)" \
  --output-format json \
  --sandbox false \
  --yolo \
  --include-directories "<项目根目录>"

# Kimi:
kimi --print \
  -p "$(cat .workflow/{role}-prompt-step{N}.txt)" \
  --output-format text \
  --work-dir "<项目根目录>" \
  --yolo \
  --session "redcap-{role}-step{N}-{uuid}" \
  --max-steps-per-turn 50

# Copilot:
copilot -p "$(cat .workflow/{role}-prompt-step{N}.txt)" \
  --allow-all \
  --autopilot \
  --model "{model_id}"
```

### 7.2 Gemini CLI 安全措施

- **强制非交互**：命令中必须包含 `-p` 参数
- **禁用沙盒交互**：`--sandbox false` 避免 sandbox 确认弹窗
- **全工具自动审批**：`--yolo`（⚠️ 不要用 `--approval-mode auto_edit`，Shell 命令仍会弹确认导致 headless 挂起）
- **超时保护**：Dispatcher 设置合理超时，CLI 超时后 kill 进程并按 Fallback 策略处理
- **内建重试**：gemini 遇到 429 频控时会自动重试（实测约 10-22 秒间隔），超时阈值需留出此裕量

### 7.3 Kimi CLI 安全措施

- **强制非交互**：命令必须包含 `--print` 参数（隐含 `--yolo`）
- **自动审批**：`--yolo` 避免操作确认弹窗
- **步骤限制**：`--max-steps-per-turn 50` 防止无限循环（配置默认 100）
- **超时保护**：同 §8 统一超时策略
- **Session 管理**：优先使用 `--session` 指定自定义 ID，便于恢复和追踪

### 7.4 Claude Code 安全措施

- **强制非交互**：`-p` 参数强制 print 模式
- **按角色授权**：PM/架构师用 `--permission-mode acceptEdits`；程序员/QA 用 `--permission-mode auto`
- **Session 指定**：`--session-id <UUID>` 首次调用时指定，便于后续 `--resume` 恢复
- **成本控制**：可选 `--max-budget-usd <N>` 限制单次调用成本上限

---

## 3B. Kimi CLI（Kimi Code）

### 3B.1 基本信息

- **可执行文件**：`kimi`（路径：`/Users/norven/.local/bin/kimi`）
- **底层模型**：kimi-code/kimi-for-coding（Moonshot AI 原生）
- **版本**：1.30.0+

### 3B.2 命令模板

```bash
kimi --print \
  -p "$(cat .workflow/{role}-prompt-step{N}.txt)" \
  --output-format stream-json \
  --work-dir "<项目根目录>" \
  --add-dir "<开发手册目录>" \
  --yolo \
  --session "<session_id>" \
  --max-steps-per-turn 50
```

> `--print` 模式强制非交互，隐含 `--yolo`（自动审批所有操作）。
> `--output-format stream-json` 返回流式 JSON。若需单次完整结果，可使用 `text` 后自行解析 `__redcap_status`。
> `--max-steps-per-turn 50` 防止无限循环（配置默认 100，此处保守限制）。

### 3B.3 参数说明

| 参数 | 用途 | 取值 |
|------|------|------|
| `--print` | 非交互模式（print and exit） | 固定，代替 `-p` 的交互后立即退出行为 |
| `-p` / `--prompt` | 传入 prompt | Dispatcher 组装的完整任务指令 |
| `--output-format` | 输出格式 | `text`（默认）或 `stream-json`（流式） |
| `--work-dir` / `-w` | 工作目录 | 项目根目录路径 |
| `--add-dir` | 额外目录授权 | 可多次指定，授权读写额外目录 |
| `--yolo` / `-y` | 自动审批所有操作 | 固定，避免交互确认 |
| `--session` / `-S` | 指定 Session ID | 传入自定义 Session ID 或已有 Session ID 恢复 |
| `--continue` / `-C` | 恢复上一 Session | 恢复当前工作目录的最近一次 Session |
| `--model` / `-m` | 指定模型 | 可选，覆盖配置文件中的默认模型 |
| `--max-steps-per-turn` | 单轮最大步骤数 | `50`（配置默认 100，此处保守限制防止无限循环） |
| `--thinking` | 启用思考模式 | 可选，复杂推理任务启用 |
| `--config` | 内联配置 | TOML/JSON 格式字符串 |

### 3B.4 返回格式

**`--print --output-format text` 模式**（推荐用于 RedCap）：

返回纯文本，Dispatcher 从中正则提取 `__redcap_status` JSON 块（与其他 Agent 统一）。

**`--print --output-format stream-json` 模式**：

逐行返回 JSON 事件流，最终 `assistant_message` 包含回复文本。

### 3B.5 Session 管理

Kimi CLI 支持自定义 Session ID（优于 claude-code 和 gemini 的 Session 管理）：

```bash
# 首次调用：指定 Session ID
kimi --print -p "..." --session "architect-step1-uuid"

# 恢复调用：使用相同 Session ID
kimi --print -p "..." --session "architect-step1-uuid"

# 或使用 --continue 恢复最近 Session
kimi --print -p "..." --continue

# 导出 Session 数据
kimi export <session_id> -o session-backup.zip
```

### 3B.6 Kimi CLI 安全措施

- **强制非交互**：命令必须包含 `--print` 参数
- **自动审批**：`--yolo` 避免操作确认弹窗
- **超时保护**：同 §8 统一超时策略

---

## 3C. Copilot CLI（GitHub Copilot）

> **来源**：基于 Copilot CLI 自身实测验证的集成方案。
> **状态**：文档集成完成，Hook 脚本待实测后部署（遵循 L-8 先测再改 + L-16 部署链验证）。

### 3C.1 基本信息

- **可执行文件**：`copilot`（路径：需检测，通常 `/opt/homebrew/bin/copilot` 或 `~/.local/bin/copilot`）
- **底层模型**：多模型可选（14 种），默认 Claude Opus 4.6
- **版本**：1.0.18+
- **独特优势**：唯一同时支持 Claude 系列和 GPT 系列的 CLI；仓库级 Hook 配置（`.github/hooks/*.json`）

### 3C.2 命令模板

```bash
# ── 标准调用（所有角色通用） ──
copilot -p "$(cat .workflow/{role}-prompt-step{N}.txt)" \
  --allow-all \
  --autopilot \
  --model "{model_id}"

# ── 恢复调用（同角色同步骤的后续轮次） ──
copilot -p "$(cat .workflow/{role}-prompt-step{N}.txt)" \
  --allow-all \
  --autopilot \
  --resume="{session_id}" \
  --model "{model_id}"
```

> `--allow-all` 跳过所有权限确认（等价 claude 的 `bypassPermissions`、gemini/kimi 的 `--yolo`）。
> `--autopilot` 持续执行直至完成，不暂停询问。
> Copilot CLI 不支持 `--system-prompt`，角色身份通过 Prompt 前缀或 `.github/copilot-instructions.md` 注入。
> Copilot CLI **支持** `--output-format=json`，程序化场景应开启 JSONL 输出并从结果行提取 `sessionId`。

### 3C.3 参数说明

| 参数 | 用途 | 取值 |
|------|------|------|
| `-p` | 非交互模式，传入 prompt | Dispatcher 组装的完整任务指令 |
| `--allow-all` | 全授权 | 固定，跳过所有权限确认 |
| `--autopilot` | 自动驾驶 | 固定，持续执行不暂停 |
| `--model` | 指定模型 | 按路由表选择（如 `claude-opus-4.6`、`gpt-5.4`） |
| `--resume=<id>` | 恢复 Session | 执行后从 JSONL 输出解析的 session ID（见 §3C.5） |

### 3C.4 返回格式

**JSONL 输出**（`--output-format=json`）：

```
Copilot CLI (--output-format=json, JSONL):
  session_id = 解析 JSONL 末行或 session 字段（见 §3C.5）
  response_text = 从 JSONL 提取 response 字段
```

纯文本回退（不加 `--output-format=json`）：
```
Copilot CLI (-p 纯文本):
  session_id = 不可获取（不支持续接）
  response_text = 完整文本输出（包含 __redcap_status JSON 块）
```

### 3C.5 Session 管理

Copilot CLI 的 Session ID 为自动生成的 UUID，不支持自定义。**重要**：官方 sessionStart Hook 不暴露 sessionId 字段（已验证），须改用 `--output-format=json` 从 JSONL 输出提取。

**JSONL 实际结构**（经 rubber-duck 实测验证）：
```
# 每轮 assistant 回复行（可能多行）
{"type": "assistant", "message": {"data": {"content": "...回复正文..."}}}

# 最终 result 行（仅在成功完成时存在，中断/超时时无此行）
{"type": "result", "sessionId": "uuid-xxx", ...}
```

```bash
# 首次调用：加 --output-format=json，tee 保存完整 JSONL
copilot -p "..." --allow-all --autopilot --output-format=json 2>&1 \
  | tee /tmp/copilot-response-${STEP}.jsonl > /dev/null

# 提取 session ID（仅在成功完成时可用；中断/超时时文件可能无 result 行）
python3 -c "
import json, sys
for line in open('/tmp/copilot-response-\${STEP}.jsonl'):
    line = line.strip()
    if not line: continue
    try:
        obj = json.loads(line)
        # sessionId 只在最终 result 行存在
        if obj.get('type') == 'result' and obj.get('sessionId'):
            print(obj['sessionId'])
    except: pass
" > .workflow/.copilot-session-id

# 提取模型回复正文（从 assistant.message.data.content 收集）
RESPONSE_TEXT=$(python3 -c "
import json, sys
parts = []
for line in open('/tmp/copilot-response-\${STEP}.jsonl'):
    try:
        obj = json.loads(line.strip())
        if obj.get('type') == 'assistant':
            content = obj.get('message', {}).get('data', {}).get('content', '')
            if content: parts.append(content)
    except: pass
sys.stdout.write(''.join(parts))
")

# 恢复调用（仅当 .copilot-session-id 非空时使用 --resume）
SESSION_ID=$(cat .workflow/.copilot-session-id 2>/dev/null)
if [ -n "$SESSION_ID" ]; then
  copilot -p "..." --allow-all --autopilot --output-format=json \
    --resume="$SESSION_ID" | tee /tmp/copilot-response-${STEP}.jsonl > /dev/null
else
  # 无 session ID（上次中断/超时），新建 session
  copilot -p "..." --allow-all --autopilot --output-format=json \
    | tee /tmp/copilot-response-${STEP}.jsonl > /dev/null
fi
```

> ⚠️ **中断/超时时的 session 降级**：`sessionId` 只在成功完成的最终 result 行存在。若上次调用被中断，`.copilot-session-id` 为空，下次自动新建 session（与 Kimi/Gemini 超时降级行为一致）。
>
> ⚠️ **已知限制（L-39）**：`sessionStart` Hook 不暴露 `sessionId`（官方文档确认），旧方案已废弃。

### 3C.6 Copilot CLI 安全措施

- **强制非交互**：命令必须包含 `-p` 参数
- **全授权**：`--allow-all` 避免权限确认挂起
- **自动驾驶**：`--autopilot` 避免中途暂停
- **超时保护**：同 §8 统一超时策略
- **Git 仓库要求**：Hook 机制依赖 `.github/hooks/*.json` 配置文件，项目必须是 git 仓库

### 3C.7 可选模型（14 种）

```
claude-opus-4.6          # premium — 深度推理、架构设计（默认）
claude-sonnet-4.6        # standard — 通用编码
gpt-5.4                  # standard — OpenAI 阵营
gpt-5.3-codex            # standard — 代码专精
claude-haiku-4.5         # fast/cheap — 轻量任务
```

> 完整列表可通过 `copilot --help` 查看。

---

## 3D. Codex CLI（OpenAI Codex）

> **来源**：2026-04-18 live closeout 中，Copilot / Claude / Kimi / Gemini reviewer 链路不可用时的本机实测。Codex CLI 可作为独立评审 fallback，但必须使用干净结果文件隔离 CLI banner / warning。

### 3D.1 基本信息

- **可执行文件**：`codex`（路径：需检测，通常 `/opt/homebrew/bin/codex`）
- **底层模型**：默认 `gpt-5.4`，可通过 `--model` 切换
- **适用角色**：Reviewer fallback 优先；常规角色可纳入动态路由，但仍按能力矩阵和健康状态排序

### 3D.2 命令模板

```bash
codex exec -C "$PROJECT_ROOT" \
  --sandbox read-only \
  --ephemeral \
  --output-last-message "$RESULT_FILE" \
  --color never \
  - < "$PROMPT_FILE"
```

### 3D.3 调用约束

- **结果通道**：程序化消费必须优先读取 `--output-last-message` 文件；stdout/stderr 可能包含 banner、插件预热 warning、网络重连提示，不可直接当作评审 payload。
- **输入通道**：长 prompt 必须先写入临时文件，再通过 `codex exec ... -` 的 stdin 输入；不得把包含规范正文 / diff / 中文说明的大 prompt 作为末尾 argv 传入。
- **权限边界**：独立评审默认用 `--sandbox read-only`，避免 reviewer 修改工作区。
- **超时保护**：同 §8 统一超时策略；stop-review 默认可通过 `REDCAP_REVIEW_AGENT_TIMEOUT_CODEX_SEC` 单独调整。runner 必须用进程组级 timeout，避免 Gemini / Node 这类 CLI 的子进程逃逸后阻塞 fallback。

---

## 8. Agent 超时策略与排查

### 8.1 超时原因排查（优先从自身调用方式排查）

Agent 超时多数并非 Agent 工具质量问题，常见自身原因：

| 排查方向 | 具体问题 | 解决方案 |
|---------|---------|---------|
| **Prompt 过长** | 将完整手册 + 上下文 + 模板全部注入，超过 Agent 高效处理阈值 | 精简 Prompt：只注入当前步骤必要的上下文，手册用摘要而非全文 |
| **文件传参格式** | `$(cat ...)` 读取的文件含特殊字符（中文引号、Shell 元字符）导致解析异常 | 确保文件内容 UTF-8 无 BOM，无未转义的 Shell 特殊字符 |
| **交互式阻塞** | Agent 进入确认等待（sandbox 确认、权限确认、trust 确认） | claude: `--permission-mode auto`；gemini: `--yolo --sandbox false`；kimi: `--yolo`；copilot: `--allow-all --autopilot`；codex: `exec --sandbox read-only --ephemeral` |
| **工作目录错误** | Agent 在错误目录执行导致找不到文件，反复重试超时 | 确保 `--add-dir` / `--work-dir` / `--include-directories` 指向正确的项目根目录 |
| **Session 恢复失败** | `--resume` 传入过期 Session ID，Agent 报错但未正常退出 | 调用前检查 Session 有效性，失败后 fallback 到新建 Session |
| **网络代理延迟** | SiliconFlow 等中间代理增加 RTT | 优先使用原生 CLI（kimi-cli > claude-code&kimi-2.5） |

### 8.2 超时阈值设置

```yaml
timeout_config:
  product-manager: 300   # 5 分钟（需求文档，相对简单）
  architect: 600         # 10 分钟（设计文档，需要推理）
  programmer: 900        # 15 分钟（编码实现，工作量最大）
  qa: 600                # 10 分钟（测试执行）
  health_check: 30       # 30 秒（健康检查探测）
```

Dispatcher 在调用 CLI 时设置超时。超时后：
1. 向 CLI 进程发送 SIGTERM
2. 等待 5 秒优雅退出
3. 若仍存活发送 SIGKILL
4. 记录超时到 `agent_health`，按 Fallback 策略处理

---

## 9. Session 管理最佳实践

### 9.1 各 CLI 的 Session 能力对比

| 能力 | claude-code | gemini | kimi | copilot |
|------|------------|--------|------|--------|
| 自定义 Session ID | ✅ `--session-id <UUID>`（必须为合法 UUID） | ❌（自动生成） | ✅ `--session <任意字符串>` | ❌（自动生成 UUID） |
| 恢复指定 Session | ✅ `--resume <UUID>` | ✅ `--resume latest/index/UUID` | ✅ `--session <同一ID>` 或 `--continue` | ✅ `--resume=<UUID>` |
| 恢复效果（实测） | ⚠️ 部分恢复（历史消息列出但模型可能声称“新会话”） | ✅ 完整恢复（正确回忆上轮内容） | ✅ 完整恢复（最佳） | ⚠️ 待独立验证 |
| 列出 Sessions | ✅ `/resume` 交互命令 | ✅ `--list-sessions` | ✅ `kimi export` | ❌ |
| Fork Session | ✅ `--fork-session` | ❌ | ❌ | ❌ |
| 禁用持久化 | ✅ `--no-session-persistence` | ❌ | ❌ | ❌ |
| Session 导出 | ❌ | ❌ | ✅ `kimi export <id>` | ❌ |
| Session 命名 | ✅ `--name "xxx"` | ❌ | ❌ | ❌ |

### 9.2 Session 策略

**优先使用各 CLI 原生 Session 管理**，不自建上下文传递：

```
claude-code:
  1. 首次调用：--session-id <Dispatcher生成的UUID>，从返回 JSON 确认 session_id
  2. 恢复调用：--resume <session_id>
  3. 恢复失败：新建 Session（标记旧 Session 为 expired）
  4. 命名标记：--name "redcap-{role}-step{N}" 便于人工识别
  ⚠ 实测恢复效果一般：历史消息列出但模型可能认为是"新会话"，Prompt 需包含足够上下文

gemini:
  1. 首次调用：正常执行，从返回 JSON 提取 session_id
  2. 恢复调用：--resume <UUID>（支持 latest、索引号、UUID 三种方式）
  3. 恢复失败：新建 Session
  4. 列出可用 Sessions：--list-sessions
  ✅ 实测恢复效果好：能完整回忆上轮对话内容
  ⚠ gemini 内建 429 重试（约 10-22 秒间隔），超时阈值需留出此裕量

kimi:
  1. 首次调用：--session "redcap-{role}-step{N}-{uuid}" 自定义有意义的 Session ID
  2. 恢复调用：--session "<同一 ID>" 即可恢复
  3. 导出备份：kimi export <session_id> 保存完整会话
  ✅ 实测恢复效果最佳：Session ID 可自定义，恢复完美

copilot:
  1. 首次调用：--output-format=json 执行，从 JSONL 提取 session_id 写入 .workflow/.copilot-session-id
  2. 恢复调用：--resume="$(cat .workflow/.copilot-session-id)"
  3. 恢复失败：新建 Session（标记旧 Session 为 expired）
  ⚠ Session ID 自动生成（UUID），不支持自定义；需通过 JSONL 输出提取（sessionStart Hook 不暴露 sessionId）
```

### 9.3 Prompt 精简原则（减少 Session 依赖）

即使 Session 恢复成功，也不应假设 Agent 保有完整上下文。每次 Prompt 应包含：
- 当前步骤的关键上下文（设计文档摘要、上游交付物要点）
- 明确的文件路径和目标
- 但**不重复注入**完整手册全文（使用摘要版）

---

## 10. Agent CLI 调用安全规范

### 10.1 Shell 命令构造安全

> ⚠️ 以下规范适用于 Dispatcher 构造 CLI 命令以及 Agent 在执行过程中的 Shell 操作。

**严禁事项**（Shell 特殊字符相关）：

| 禁止行为 | 风险 | 替代方案 |
|---------|------|---------|
| 使用 `>` 重定向写文件 | `>` 与路径拼接后可能被解析为目录名，创建异常目录 | 使用 Agent 内建 Write/Edit 工具写文件 |
| 使用 `>>` 追加写文件 | 同上，且无法保证原子性 | 使用 Agent 内建工具 |
| 在命令中拼接未转义的用户输入 | Shell 注入风险 | 文件传参（`$(cat file)`），或对变量严格引号包裹 |
| 使用 `\|` 管道处理文件内容后写入 | 管道中断导致数据丢失 | 先写临时文件再 mv |
| 使用 `` `...` `` 反引号命令替换 | 嵌套转义困难 | 使用 `$(...)` 替代 |
| 在 prompt 字符串中直接嵌入中文引号"" | Shell 解析异常 | 文件传参模式（标准做法） |

**必须遵守**：

1. **文件写入一律使用 Agent 内建工具**（Read/Write/Edit），不使用 Shell 重定向
2. **变量一律双引号包裹**：`"$var"`，不使用 `$var`
3. **路径中含空格或特殊字符时使用引号**：`"$project_dir/开发手册/"`
4. **命令替换使用 `$(...)`** 而非反引号
5. **Prompt 内容始终通过文件传参**（写入 `.workflow/*.txt` 再 `$(cat ...)`），不在命令行中直接嵌入
6. **重定向符与路径之间必须有空格**：`> file.txt` 而非 `>file.txt`（虽然正确做法是不用重定向）

### 10.2 文件路径安全

1. **项目内文件**：使用从项目根目录起算的**相对路径**，不使用绝对路径
2. **CLI 参数中的目录路径**：使用绝对路径（`--add-dir`、`--work-dir`、`--include-directories`）
3. **路径拼接时使用 `/` 连接**，不依赖 Shell 展开
4. **禁止路径中出现 Shell 元字符**（`>`, `<`, `|`, `&`, `;`, `$` 等）

### 10.3 环境隔离

1. Agent CLI 调用前，确保 `$PWD` 为项目根目录
2. 不依赖 Agent 自行推断工作目录（显式传参）
3. 不使用 `cd && cmd` 链式调用（可能因 `cd` 失败导致后续命令在错误目录执行）

---

## 11. CLI 工具级项目配置

> Dispatcher 在项目初始化时为每种 Agent CLI 创建对应的指令文件。
> 所有子 Agent 共享 `references/agent-constraints.md` 中的强制约束（通过 `@` 导入）。
> 修改约束只需编辑该共享文件，无需逐个同步各 CLI 的配置。

### 11.1 Gemini `settings.json` 最佳实践

Dispatcher 在项目初始化时检查 `~/.gemini/settings.json`，确保以下配置存在：

```json
{
  "tools": {
    "run_shell_command": {
      "tokenBudget": 4000
    }
  }
}
```

- `tokenBudget`：限制 Shell 命令输出的 Token 消耗（防止 `npm install` 等输出占满上下文窗口）

### 11.2 Gemini `GEMINI.md` 项目规则

Dispatcher 在项目初始化时于项目根目录创建 `GEMINI.md`（如不存在），通过 `@` 导入共享约束：

```markdown
# GEMINI.md — RedCap 项目规则

@references/agent-constraints.md

## 当前任务上下文
- 角色：{{role}}
- 步骤：{{step_id}}
- 交付目录：{{deliverable_dir}}
```

> Gemini CLI 启动时自动读取项目根目录的 `GEMINI.md`，`@` 导入的文件会被原生展开注入上下文。
> 共享约束文件 `references/agent-constraints.md` 包含安全铁律、文件操作约束、通信协议和防退化检查点。

### 11.3 Kimi 配置最佳实践

Kimi CLI 的 `~/.kimi/config.toml` 中以下配置与 RedCap 相关：

```toml
[loop_control]
max_steps_per_turn = 100          # 全局默认，RedCap 通过 CLI 参数覆盖为 50
max_retries_per_step = 3          # 单步最大重试
reserved_context_size = 50000     # 保留上下文空间
compaction_trigger_ratio = 0.85   # 上下文压缩触发比例
```

> Dispatcher 不修改用户的全局配置，通过 `--max-steps-per-turn` 参数在调用时覆盖。

### 11.4 Claude Code 项目规则

Claude Code 在项目根目录自动读取 `CLAUDE.md`。Dispatcher 在项目初始化时创建（如不存在），通过 `@` 导入共享约束：

```markdown
# CLAUDE.md — RedCap 项目规则

@references/agent-constraints.md

## 当前任务上下文
- 角色：{{role}}
- 步骤：{{step_id}}
- 交付目录：{{deliverable_dir}}
```

> Claude Code 支持 `@file` 原生导入，启动时自动展开注入上下文。
> 共享约束文件包含安全铁律、文件操作约束、通信协议和防退化检查点（L-9 子 Agent 级对策）。

### 11.5 Copilot CLI 项目规则

Copilot CLI 在项目根目录自动读取 `.github/copilot-instructions.md`。Dispatcher 在项目初始化时创建（如不存在）：

```markdown
# .github/copilot-instructions.md — RedCap 项目规则

<!-- Copilot CLI 不支持 @file 导入，共享约束需内联或通过 Prompt 注入 -->

## 强制约束
- 参考 references/agent-constraints.md 中的安全铁律
- 文件写入一律使用内建工具，不使用 Shell 重定向

## 当前任务上下文
- 角色：{{role}}
- 步骤：{{step_id}}
- 交付目录：{{deliverable_dir}}
```

> ⚠️ Copilot CLI 不支持 `@file` 原生导入（与 Claude Code、Gemini 不同）。
> 共享约束需通过 Prompt 前缀注入或在 `.github/copilot-instructions.md` 中内联关键规则。
> Hook 脚本（由 `.github/hooks/*.json` 注册）提供另一层约束注入机制（见 `knowledge/hooks-copilot-cli.md`）。

---

## §12 多轮接力协议（Multi-turn Relay Protocol）

> **用途**：定义棱镜（Prism）及其他需要多轮对话场景下，各 Agent CLI 工具的 session 续接标准化操作。
> 解决"各工具 session 机制不统一"导致上下文丢失的问题。

### 12.1 各工具续接能力对比

| 工具 | 首次启动 session | 续接方式 | 自定义 ID | 限制 |
|------|---------------|---------|---------|------|
| **Claude Code** | `--session-id <UUID>` | `--resume <UUID>` | ✅ 任意 UUID | 无 |
| **Gemini CLI** | 自动生成（返回 session_id） | `--resume <session_id>` | ❌ | L-7：不同工作目录可能创建新 session |
| **Kimi CLI** | `--session "<str>"` | `-S <session_id>` 或 `--session` | ✅ 任意字符串 | session 在 kimi 服务端保存 |
| **Copilot CLI** | 通过 `--output-format=json` JSONL 输出提取，写入 `.workflow/.copilot-session-id` | `--resume="$(cat .workflow/.copilot-session-id)"` | ❌（UUID 自动生成） | sessionStart Hook 不暴露 sessionId；不支持列举 sessions；不支持自定义 ID |

> `session_handle` 是宿主 workboard / continuity import 中给人类看的会话别名；它不等于 CLI 原生 sessionId。
> RedCap 记录两者的目的不同：`session_handle` 负责定位来源会话，原生 sessionId / `runtime_session_id` 负责续接与隔离。

> ⚠️ **session 续接能力 ≠ Collect 追问能力**：只有当本轮运行同时满足「已落盘可复用的 session handle」+「适配层已定义补充 prompt 后继续同一 session 的命令模板」时，Prism 才能把该 backend 视为 `supports_follow_up=true`。若 CLI 理论上支持 `--resume`，但当前调用未保留 session handle，或 Dispatcher 尚无对应续接模板，必须按 backend limitation 直接记为 `absent`。

### 12.2 棱镜多轮接力流程

棱镜运行中可能需要多轮对话（如 Council 模式需要多方讨论收敛）。标准接力流程：

```
第1轮：启动 Agent → 记录 session_id → 写入 .workflow/prism-sessions.yaml
第2轮：读取 session_id → --resume/续接 → 追加 context（上一轮摘要 + 新问题）
第N轮：持续续接 → 直到 __redcap_status completed/blocked 收到
```

**context 携带规则**：续接时必须在 prompt 开头附加：
```
[续接轮次 N，摘要：<上轮核心结论1-2句话>]
<新的问题/追加内容>
```

### 12.3 BLOCKED 信号物理锚点

当棱镜雇佣兵或任何子 Agent 遇到需要人工决策的阻塞点时：

**写入位置**：`{任务工作目录}/.workflow/blocked-{role}-{timestamp}.md`

**格式**：
```markdown
# BLOCKED: {问题一句话标题}

**阻塞方**：{role名称}（如 prism-council, architect）
**时间戳**：{ISO8601}
**上下文**：{当前任务和进度，2-3句话}
**阻塞问题**：
> {用户必须决策的具体问题，禁止模糊描述}

**选项**：
- 选项 A：{描述} — {影响}
- 选项 B：{描述} — {影响}

**Cap 推荐**：{推荐选项及理由，1句话}

**状态**：PENDING / RESOLVED
```

**Cap 读取方式**：每轮任务开始时扫描 `find .workflow -name "blocked-*.md" -newer ...`，发现 PENDING 文件则读取并向 Norven 透传，等待决策后在文件追加 `**状态**：RESOLVED\n**决策**：{Norven 的决定}` 后重启 Agent 续接。

### 12.4 Copilot CLI Session 续接注意事项

Copilot CLI 支持 `--resume`，正确获取 Session ID 的方式：

1. **sessionStart Hook 不能用于拿 sessionId**：官方 sessionStart Hook 输入不含 sessionId 字段（已验证），但仍可用于会话级基线捕获
2. **正确方案**：首次调用时加 `--output-format=json`，从 JSONL 输出解析 session_id（见 §3C.5）
3. 续接时读取：`copilot -p "..." --output-format=json --resume="$(cat .workflow/.copilot-session-id)"`
4. 限制：不支持自定义 Session ID，不支持列举所有 sessions

> ⚠️ **L-7 警告（Gemini）**：Gemini CLI 在不同工作目录调用时可能创建新 session 而非续接。
> 解决方案：始终在项目根目录执行 Gemini 续接调用，或显式传入 `--resume` 参数。

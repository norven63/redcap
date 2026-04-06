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
```

### 1.2 模型检测与缓存

**检测时机**：
- 项目初始化时（`INIT` 状态）一次性检测所有已安装 CLI 的底层模型
- Agent 调用失败时，触发对该 Agent 的重新检测
- 用户显式告知某 Agent 可用/恢复时，触发重新检测

**检测方法**：
```bash
# claude-code: 从 --print 模式返回的 JSON 中提取 modelUsage 字段
claude -p "echo test" --output-format json 2>/dev/null | python3 -c "
import sys,json; d=json.load(sys.stdin)
print(list(d.get('modelUsage',{}).keys())[0] if d.get('modelUsage') else 'unknown')
"

# gemini: 从 --output-format json 返回的 stats.models 字段提取主模型
gemini -p "echo test" --output-format json --yolo 2>/dev/null | python3 -c "
import sys,json; d=json.load(sys.stdin)
models = d.get('stats',{}).get('models',{})
main = [k for k,v in models.items() if 'main' in v.get('roles',{})]
print(main[0] if main else 'unknown')
"

# kimi: 从配置文件读取默认模型
grep 'default_model' ~/.kimi/config.toml 2>/dev/null | cut -d'"' -f2 || echo "kimi-for-coding"

# copilot: 从 --version 确认可用，默认模型为 claude-opus-4.6
copilot --version 2>/dev/null && echo "claude-opus-4.6" || echo "unavailable"
```

**缓存位置** `.workflow/agent-registry.yaml`：
```yaml
agents:
  claude-code:
    cli_path: "/opt/homebrew/bin/claude"
    model: "Pro/moonshotai/Kimi-K2.5"
    detected_at: "2026-03-29T19:25:00+08:00"
    available: true
  gemini:
    cli_path: "/opt/homebrew/bin/gemini"
    model: "gemini-3-flash-preview"
    detected_at: "2026-03-29T19:25:00+08:00"
    available: true
  kimi:
    cli_path: "/Users/norven/.local/bin/kimi"
    model: "kimi-code/kimi-for-coding"
    detected_at: "2026-03-29T19:25:00+08:00"
    available: true
  copilot:
    cli_path: "/opt/homebrew/bin/copilot"  # 或 which copilot 检测
    model: "claude-opus-4.6"               # 默认，可通过 --model 切换
    detected_at: "2026-03-29T19:25:00+08:00"
    available: true
```

### 1.3 优先级路由表（带 Model 维度）

**核心规则**：
1. 同一模型下，**专用 CLI > 通用 CLI 代理**（如 `kimi&kimi-k2` > `claude-code&kimi-2.5`）
2. 按角色需求匹配最佳模型能力
3. 近期失败的 Agent 降权

```yaml
agent_priority:
  product-manager:
    - "kimi&kimi-for-coding"         # Kimi 原生 CLI 优先
    - "claude-code&Kimi-K2.5"        # 同模型但通用 CLI 备选
    - "copilot&claude-opus-4.6"      # Copilot CLI + Claude 深度推理
    - "claude-code&claude-sonnet"    # 不同模型备选
    - "gemini&gemini-3-flash"        # Google 模型备选
  architect:
    - "gemini&gemini-3-flash"        # 推理能力强
    - "copilot&claude-opus-4.6"      # Copilot + Claude 架构设计
    - "kimi&kimi-for-coding"
    - "claude-code&claude-sonnet"
    - "claude-code&Kimi-K2.5"
  programmer:
    - "gemini&gemini-3-flash"        # 编码能力强
    - "kimi&kimi-for-coding"
    - "copilot&claude-opus-4.6"      # Copilot + Claude 编码
    - "claude-code&Kimi-K2.5"
    - "claude-code&claude-sonnet"
  qa:
    - "kimi&kimi-for-coding"         # 工具使用/指令遵从
    - "claude-code&Kimi-K2.5"
    - "copilot&gpt-5.4"              # Copilot + GPT 测试视角
    - "claude-code&claude-sonnet"
    - "gemini&gemini-3-flash"
  reviewer:
    - "copilot&gpt-5.4"              # GPT-5.4 独立视角 Review（首选）
    - "gemini&gemini-3-flash"        # Gemini 强推理 Review
    - "kimi&kimi-for-coding"
    - "claude-code&claude-sonnet"
    - "claude-code&Kimi-K2.5"
```

用户可在项目 `.workflow/state.yaml` 中通过 `agent_routing_override` 字段覆盖默认配置。

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
  --system-prompt "$(cat .workflow/{role}-system-prompt.txt)" \
  --output-format json \
  --add-dir "<项目根目录>" \
  --permission-mode acceptEdits \
  --session-id "<UUID>"

# 程序员 / 测试QA（需要执行 Shell 命令）
claude -p "$(cat .workflow/{role}-prompt-step{N}.txt)" \
  --system-prompt "$(cat .workflow/{role}-system-prompt.txt)" \
  --output-format json \
  --add-dir "<项目根目录>" \
  --permission-mode bypassPermissions \
  --session-id "<UUID>"
```

> Dispatcher 始终先将 prompt 和 system-prompt 写入 `.workflow/` 下的文件，再用 `$(cat ...)` 读取传入 CLI，避免 Shell 中文引号截断问题。
> `--session-id` 首次调用时传入调用方生成的 UUID，后续通过 `--resume` 恢复。
> `--permission-mode bypassPermissions` 跳过所有权限检查（程序员/QA 需要执行 Shell），防止 `-p` 管道模式下权限弹窗导致挂起（与 L-7 Gemini `--yolo` 同理）；`acceptEdits` 仅审批文件编辑（PM/架构师）。

### 2.3 参数说明

| 参数 | 用途 | 取值 |
|------|------|------|
| `-p` | 非交互模式，传入 prompt | Dispatcher 组装的完整任务指令 |
| `--system-prompt` | 角色身份设定 | 对应角色手册.md 的核心摘要 |
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

Copilot CLI (-p 纯文本):
  response_text = 完整文本输出（与 Kimi text 模式等价）
  session_id = 从 .workflow/.copilot-session-id 读取（由 sessionStart Hook 写入）

统一后:
  从 response_text 中正则提取 __redcap_status JSON 块
  由 Dispatcher 写入 .workflow/last-result.json（Agent 不再负责写入此文件）
```

---

## 6. Agent Fallback 策略

### 6.1 Fallback 路由表

按 §1.3 的优先级路由表顺序切换。同一模型下专用 CLI 始终优先于通用 CLI 代理：

```yaml
fallback_routing:
  product-manager: ["kimi", "copilot", "claude-code", "gemini"]
  architect:       ["gemini", "copilot", "kimi", "claude-code"]
  programmer:      ["gemini", "kimi", "copilot", "claude-code"]
  qa:              ["kimi", "copilot", "claude-code", "gemini"]
  reviewer:        ["copilot", "gemini", "kimi", "claude-code"]
```

### 6.2 触发条件

- 首选 Agent 连续 **2 次**返回失败（含 HTTP 429 频控、CLI 进程非零退出码）
- CLI 进程超时（无响应超过合理阈值，见 §8）
- CLI 进入交互模式（未正常返回 JSON）

### 6.3 切换流程

```
1. 首选 Agent 第 1 次失败 → 重试同一 Agent
2. 第 2 次仍失败 → 切换到下一 Fallback Agent
3. 更新 state.yaml 的 current_role.agent 为实际使用的 Agent
4. 组装适配 Fallback Agent 的 CLI 命令（参数映射见 §2/§3/§3B）
5. 所有 Fallback Agent 均失败 → 进入 §6.5 用户降级决策
```

### 6.4 Agent 可用性追踪

Dispatcher 在 `state.yaml` 中维护 `agent_health` 字段：

```yaml
agent_health:
  gemini:
    consecutive_failures: 2
    last_failure_at: "2026-03-29T15:00:00+08:00"
    last_failure_reason: "rate-limited (429)"
    blacklisted: true
  claude-code:
    consecutive_failures: 1
    last_failure_at: "2026-03-29T15:10:00+08:00"
    last_failure_reason: "hallucinated completion"
    blacklisted: false
  kimi:
    consecutive_failures: 0
    last_failure_at: null
    last_failure_reason: null
    blacklisted: false
  copilot:
    consecutive_failures: 0
    last_failure_at: null
    last_failure_reason: null
    blacklisted: false
```

**重置规则**：
- **新步骤开始时**：所有 Agent 的 `consecutive_failures` 重置为 0，`blacklisted` 重置为 false（Agent 可能已恢复）
- **用户显式告知**（如 "gemini 已恢复"）：立即重置指定 Agent 的健康状态
- **失败计数仅在当前步骤内累积**

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
  --system-prompt "$(cat .workflow/{role}-system-prompt.txt)" \
  --output-format json \
  --add-dir "<项目根目录>" \
  --permission-mode acceptEdits \
  --session-id "<UUID>" \
  --name "redcap-{role}-step{N}"

# Claude Code（程序员/QA：auto）:
claude -p "$(cat .workflow/{role}-prompt-step{N}.txt)" \
  --system-prompt "$(cat .workflow/{role}-system-prompt.txt)" \
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

> **来源**：基于 Copilot CLI 自身实测验证的集成方案，详见 `round-table/copilot-cli_integration_proposal.md`。
> **状态**：文档集成完成，Hook 脚本待实测后部署（遵循 L-8 先测再改 + L-16 部署链验证）。

### 3C.1 基本信息

- **可执行文件**：`copilot`（路径：需检测，通常 `/opt/homebrew/bin/copilot` 或 `~/.local/bin/copilot`）
- **底层模型**：多模型可选（14 种），默认 Claude Opus 4.6
- **版本**：1.0.18+
- **独特优势**：唯一同时支持 Claude 系列和 GPT 系列的 CLI；仓库级 Hook 配置（`.github/hooks/`）

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
> 不支持 `--output-format json`，输出为纯文本（解析逻辑与 Kimi text 模式统一）。

### 3C.3 参数说明

| 参数 | 用途 | 取值 |
|------|------|------|
| `-p` | 非交互模式，传入 prompt | Dispatcher 组装的完整任务指令 |
| `--allow-all` | 全授权 | 固定，跳过所有权限确认 |
| `--autopilot` | 自动驾驶 | 固定，持续执行不暂停 |
| `--model` | 指定模型 | 按路由表选择（如 `claude-opus-4.6`、`gpt-5.4`） |
| `--resume=<id>` | 恢复 Session | 执行后从 sessionStart Hook 获取的 session ID |

### 3C.4 返回格式

**纯文本输出**（无 JSON wrapper）：

```
Copilot CLI (-p 纯文本):
  session_id = 从 .workflow/.copilot-session-id 读取（由 sessionStart Hook 写入）
  response_text = 完整文本输出（包含 __redcap_status JSON 块）
```

与 Kimi CLI `--output-format text` 模式解析逻辑完全等价，无需新增解析器。

### 3C.5 Session 管理

Copilot CLI 的 Session ID 为自动生成的 UUID，不支持自定义：

```bash
# 首次调用：正常执行，session ID 由 sessionStart Hook 捕获写入
# .workflow/.copilot-session-id
copilot -p "..." --allow-all --autopilot

# 恢复调用：从标记文件读取 session ID
copilot -p "..." --allow-all --autopilot --resume="$(cat .workflow/.copilot-session-id)"
```

### 3C.6 Copilot CLI 安全措施

- **强制非交互**：命令必须包含 `-p` 参数
- **全授权**：`--allow-all` 避免权限确认挂起
- **自动驾驶**：`--autopilot` 避免中途暂停
- **超时保护**：同 §8 统一超时策略
- **Git 仓库要求**：Hook 机制依赖 `.github/hooks/` 目录，项目必须是 git 仓库

### 3C.7 可选模型（14 种）

```
claude-opus-4.6          # premium — 深度推理、架构设计（默认）
claude-sonnet-4.6        # standard — 通用编码
gpt-5.4                  # standard — OpenAI 阵营
gpt-5.3-codex            # standard — 代码专精
claude-haiku-4.5         # fast/cheap — 轻量任务
```

> 完整列表见 `round-table/copilot-cli_integration_proposal.md §1.2`。

---

## 8. Agent 超时策略与排查

### 8.1 超时原因排查（优先从自身调用方式排查）

Agent 超时多数并非 Agent 工具质量问题，常见自身原因：

| 排查方向 | 具体问题 | 解决方案 |
|---------|---------|---------|
| **Prompt 过长** | 将完整手册 + 上下文 + 模板全部注入，超过 Agent 高效处理阈值 | 精简 Prompt：只注入当前步骤必要的上下文，手册用摘要而非全文 |
| **文件传参格式** | `$(cat ...)` 读取的文件含特殊字符（中文引号、Shell 元字符）导致解析异常 | 确保文件内容 UTF-8 无 BOM，无未转义的 Shell 特殊字符 |
| **交互式阻塞** | Agent 进入确认等待（sandbox 确认、权限确认、trust 确认） | claude: `--permission-mode auto`；gemini: `--yolo --sandbox false`；kimi: `--yolo`；copilot: `--allow-all --autopilot` |
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
  1. 首次调用：正常执行，Session ID 由 sessionStart Hook 捕获写入 .workflow/.copilot-session-id
  2. 恢复调用：--resume="$(cat .workflow/.copilot-session-id)"
  3. 恢复失败：新建 Session（标记旧 Session 为 expired）
  ⚠ Session ID 自动生成（UUID），不支持自定义；需依赖 Hook 捕获
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
> Hook 脚本（`.github/hooks/`）提供另一层约束注入机制（见 `knowledge/hooks-copilot-cli.md`）。

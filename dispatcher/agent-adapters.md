# Agent 适配器（CLI 参数映射）

> **用途**：定义各 Agent CLI 工具的调用参数规范，供 Dispatcher 组装命令使用。

---

## 1. Agent 路由表（MVP 默认配置）

```yaml
agent_routing:
  product-manager: "claude-code"   # 底层模型: Kimi 2.5 (SiliconFlow)
  architect: "gemini"              # 底层模型: Gemini 3 Pro
  programmer: "gemini"             # 底层模型: Gemini 3 Pro
  qa: "claude-code"                # 底层模型: Kimi 2.5 (SiliconFlow)
```

用户可在项目 `.workflow/state.yaml` 中通过 `agent_routing_override` 字段覆盖默认配置。

---

## 2. Claude Code CLI（Kimi 2.5）

### 2.1 基本信息

- **可执行文件**：`claude`（路径：`/opt/homebrew/bin/claude`）
- **底层模型**：Kimi 2.5（Moonshot AI，通过 SiliconFlow 代理）
- **版本**：2.1.86+

### 2.2 命令模板

```bash
claude -p "$(cat .workflow/{role}-prompt-step{N}.txt)" \
  --system-prompt "$(cat .workflow/{role}-system-prompt.txt)" \
  --output-format json \
  --add-dir "<项目根目录>" \
  --permission-mode acceptEdits \
  --allowedTools "Read,Write,Bash(test:*)"
```

> Dispatcher 始终先将 prompt 和 system-prompt 写入 `.workflow/` 下的文件，再用 `$(cat ...)` 读取传入 CLI，避免 Shell 中文引号截断问题。

### 2.3 参数说明

| 参数 | 用途 | 取值 |
|------|------|------|
| `-p` | 非交互模式，传入 prompt | Dispatcher 组装的完整任务指令 |
| `--system-prompt` | 角色身份设定 | 对应角色手册.md 的核心摘要 |
| `--output-format json` | 返回 JSON 格式 | 固定 `json` |
| `--add-dir` | 授权访问的项目目录 | 项目根目录路径 |
| `--permission-mode` | 权限模式 | `acceptEdits`（允许文件编辑） |
| `--allowedTools` | 允许的工具列表 | 按角色需求配置（见 §4） |
| `--session-id` | 指定 Session ID | 首次调用时指定，用于后续恢复 |
| `--resume` | 恢复已有 Session | 传入 session_id 恢复上下文 |

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

## 3. Gemini CLI（Gemini 3 Pro）

### 3.1 基本信息

- **可执行文件**：`gemini`（路径：`/opt/homebrew/bin/gemini`）
- **底层模型**：Gemini 3 Pro
- **版本**：0.35.2+

### 3.2 命令模板

```bash
gemini -p "$(cat .workflow/{role}-prompt-step{N}.txt)" \
  --output-format json \
  --sandbox false \
  --include-directories "<项目根目录>" \
  --approval-mode auto_edit
```

> ⚠️ `-p` 参数必须存在，否则 Gemini 进入交互模式导致终端不可用。`--sandbox false` 避免沙盒确认弹窗。

### 3.3 参数说明

| 参数 | 用途 | 取值 |
|------|------|------|
| `-p` | 非交互模式，传入 prompt | Dispatcher 组装的完整任务指令 |
| `--output-format json` | 返回 JSON 格式 | 固定 `json` |
| `--include-directories` | 授权访问的项目目录 | 项目根目录路径 |
| `--approval-mode` | 权限模式 | `auto_edit`（自动审批编辑） |
| `--resume` | 恢复已有 Session | `latest` 或 session index |
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

### 4.1 Claude Code `--allowedTools` 映射

| 角色 | allowedTools | 说明 |
|------|-------------|------|
| 产品经理 | `Read,Write` | 只读写文档，不执行代码 |
| 测试QA | `Read,Write,Bash(test:*),Bash(curl:*)` | 可读写文档 + 执行测试命令 |

### 4.2 Gemini `--approval-mode` 映射

| 角色 | approval-mode | 说明 |
|------|--------------|------|
| 架构师 | `auto_edit` | 可读写文档，自动审批文件操作 |
| 程序员 | `auto_edit` | 可读写代码和文档，自动审批 |

### 4.3 目录访问限制

Dispatcher 通过 Prompt 中的行为约束实现目录级权限控制（CLI 参数不支持细粒度目录授权）：

```
在 Prompt 中明确指示：
- "你的工作目录是 开发手册/{角色目录}/"
- "你只能写入 开发手册/{角色目录}/ 和 开发手册/{角色目录}/outbox/"
- "你可以读取但不能修改 开发手册/shared/ 和上游角色的 outbox/"
```

---

## 5. 返回值标准化

Dispatcher 从两种 CLI 获得的 JSON 结构不同，需要统一提取：

```
Claude Code:
  session_id = result["session_id"]
  response_text = result["result"]

Gemini:
  session_id = result["session_id"]
  response_text = result["response"]

统一后:
  从 response_text 中正则提取 __redcap_status JSON 块
  由 Dispatcher 写入 .workflow/last-result.json（Agent 不再负责写入此文件）
```

---

## 6. Agent Fallback 策略

### 6.1 Fallback 路由表

当首选 Agent 不可用时，按备选顺序切换：

```yaml
fallback_routing:
  product-manager: ["claude-code", "gemini"]
  architect:       ["gemini", "claude-code"]
  programmer:      ["gemini", "claude-code"]
  qa:              ["claude-code", "gemini"]
```

### 6.2 触发条件

- 首选 Agent 连续 **2 次**返回失败（含 HTTP 429 频控、CLI 进程非零退出码）
- CLI 进程超时（无响应超过合理阈值）
- CLI 进入交互模式（未正常返回 JSON）

### 6.3 切换流程

```
1. 首选 Agent 第 1 次失败 → 重试同一 Agent
2. 第 2 次仍失败 → 切换到 Fallback Agent
3. 更新 state.yaml 的 current_role.agent 为实际使用的 Agent
4. 组装适配 Fallback Agent 的 CLI 命令（参数映射见 §2/§3）
5. Fallback Agent 也失败 → 向用户报告，暂停流程（PAUSED）
```

### 6.4 Dispatcher 铁律

> ⚠️ **在任何情况下，Dispatcher 都不得直接修改项目源代码或代为生成任何交付物。**
> 即使所有 Agent 均不可用，Dispatcher 也只能暂停流程（PAUSED）并向用户报告，不得"代劳"。

---

## 7. Prompt 传参规范

### 7.1 文件传参模式（标准）

Dispatcher 始终使用文件传参，避免 Shell 中文引号截断问题：

```bash
# 1. Dispatcher 将组装好的 prompt 写入文件
#    .workflow/{role}-prompt-step{N}.txt

# 2. CLI 调用时用 $(cat ...) 读取

# Claude Code:
claude -p "$(cat .workflow/{role}-prompt-step{N}.txt)" \
  --system-prompt "$(cat .workflow/{role}-system-prompt.txt)" \
  --output-format json \
  --add-dir "<项目根目录>" \
  --permission-mode acceptEdits \
  --allowedTools "Read,Write,Bash(test:*)"

# Gemini:
gemini -p "$(cat .workflow/{role}-prompt-step{N}.txt)" \
  --output-format json \
  --sandbox false \
  --include-directories "<项目根目录>" \
  --approval-mode auto_edit
```

### 7.2 Gemini CLI 安全措施

- **强制非交互**：命令中必须包含 `-p` 参数
- **禁用沙盒交互**：增加 `--sandbox false` 避免 sandbox 确认弹窗
- **超时保护**：Dispatcher 设置合理超时，CLI 超时后 kill 进程并按 Fallback 策略处理

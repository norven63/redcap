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
claude -p "<prompt>" \
  --system-prompt "<角色身份 + 手册核心摘要>" \
  --output-format json \
  --add-dir "<项目根目录>" \
  --permission-mode acceptEdits \
  --allowedTools "Read,Write,Bash(test:*)"
```

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
gemini -p "<prompt>" \
  --output-format json \
  --include-directories "<项目根目录>" \
  --approval-mode auto_edit
```

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
  若提取失败，读取 .workflow/last-result.json（Fallback）
```
